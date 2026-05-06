#!/usr/bin/env bash
# Bootstrap script for Odoo AI Brain — Milestone 1.
# Run from the repository root. Output is tee'd to docs/bootstrap.log.
set -euo pipefail

LOG=docs/bootstrap.log
mkdir -p docs
exec > >(tee -a "$LOG") 2>&1

echo "========================================"
echo " Odoo AI Brain Bootstrap"
echo " $(date)"
echo "========================================"

# Load .env if present
if [ -f .env ]; then
  set -o allexport
  source .env
  set +o allexport
fi

echo ""
echo "--- Pulling Docker images ---"
docker pull odoo:19.0
docker pull pgvector/pgvector:pg16
docker pull ollama/ollama:latest
docker pull ghcr.io/berriai/litellm:main-stable
docker pull redis:7-alpine
docker pull nginx:alpine

# Optionally pull the default Ollama model (multi-GB — skippable)
if [ "${OLLAMA_SKIP_PULL:-false}" = "true" ]; then
  echo ""
  echo "--- Skipping Ollama model pull (OLLAMA_SKIP_PULL=true) ---"
else
  echo ""
  echo "--- Pulling Ollama model: ${LOCAL_MODEL:-qwen2.5:7b} ---"
  echo "    Set OLLAMA_SKIP_PULL=true to skip this step."
  docker run --rm \
    -v ollama_data:/root/.ollama \
    ollama/ollama:latest \
    pull "${LOCAL_MODEL:-qwen2.5:7b}"
fi

echo ""
echo "--- Starting services ---"
make up

echo ""
echo "--- Waiting for services to become healthy (up to 60s) ---"
for i in $(seq 1 12); do
  sleep 5
  if docker compose -f infra/docker-compose.yml ps | grep -q "healthy"; then
    echo "  Services healthy after $((i * 5))s"
    break
  fi
  echo "  Waiting... ($((i * 5))s)"
done

echo ""
echo "--- Verifying pgvector extension ---"
DB_CONTAINER=$(docker ps -qf "name=db")
docker exec "$DB_CONTAINER" \
  psql -U "${POSTGRES_USER:-odoo}" -d postgres \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"

echo ""
echo "--- Verifying orchestrator health ---"
curl -fsS http://localhost:8088/health
echo ""

echo ""
echo "--- Verifying Odoo is up ---"
HTTP_STATUS=$(curl -o /dev/null -s -w "%{http_code}" http://localhost:8069/web/database/selector)
if [ "$HTTP_STATUS" = "200" ]; then
  echo "  Odoo responded with HTTP 200"
else
  echo "  WARNING: Odoo returned HTTP $HTTP_STATUS — it may still be starting"
fi

echo ""
echo "========================================"
echo " Bootstrap complete — $(date)"
echo " Next: open http://localhost:8069 and create a database named"
echo " '${ODOO_DB_NAME:-ai_brain_dev}', then install the ai_brain module."
echo "========================================"
