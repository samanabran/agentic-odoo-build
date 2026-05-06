#!/usr/bin/env bash
# scripts/provision_litellm_keys.sh
#
# Generates two scoped LiteLLM virtual keys and:
#   1. Exports them to .env (appends LITELLM_VKEY_CLOUD_DEV and LITELLM_VKEY_LOCAL)
#   2. Updates the Apexive provider records in Odoo via JSON-RPC
#
# Run ONCE after `make up` and before running eval harness or chats.
# Safe to re-run — regenerates keys and updates provider records.
#
# Prerequisites:
#   - LiteLLM stack running with LITELLM_MASTER_KEY set in .env
#   - Odoo running with ai_brain module installed (llm_providers.xml loaded)
#
# Usage:
#   bash scripts/provision_litellm_keys.sh
#
# Env vars (all optional — defaults shown):
#   LITELLM_URL      http://localhost:4000
#   ODOO_URL         http://localhost:8069
#   ODOO_ADMIN_PASS  admin
#   DOTENV_FILE      .env

set -euo pipefail

LITELLM_URL="${LITELLM_URL:-http://localhost:4000}"
ODOO_URL="${ODOO_URL:-http://localhost:8069}"
ODOO_ADMIN_PASS="${ODOO_ADMIN_PASS:-admin}"
DOTENV_FILE="${DOTENV_FILE:-.env}"

# Read master key from .env
if [ -f "$DOTENV_FILE" ]; then
  # shellcheck disable=SC2046
  export $(grep -E '^LITELLM_MASTER_KEY=' "$DOTENV_FILE" | xargs) 2>/dev/null || true
fi

if [ -z "${LITELLM_MASTER_KEY:-}" ]; then
  echo "ERROR: LITELLM_MASTER_KEY is not set."
  echo "  Generate one: openssl rand -hex 32"
  echo "  Add to .env:  LITELLM_MASTER_KEY=<value>"
  exit 1
fi

echo "==> Generating LiteLLM virtual keys..."

# Generate scoped key for cloud-dev (github-dev model only)
CLOUD_DEV_KEY=$(curl -sf -X POST \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"models":["github-dev"],"metadata":{"purpose":"apexive-cloud-dev"}}' \
  "${LITELLM_URL}/key/generate" \
  | python -c "import json,sys; print(json.load(sys.stdin)['key'])")

echo "    cloud-dev key: ${CLOUD_DEV_KEY:0:16}..."

# Generate scoped key for local (prod-local/Ollama model only)
LOCAL_KEY=$(curl -sf -X POST \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"models":["prod-local"],"metadata":{"purpose":"apexive-local"}}' \
  "${LITELLM_URL}/key/generate" \
  | python -c "import json,sys; print(json.load(sys.stdin)['key'])")

echo "    local key:     ${LOCAL_KEY:0:16}..."

# Persist keys to .env
echo "--> Writing keys to ${DOTENV_FILE}..."
# Remove old entries if present
grep -v '^LITELLM_VKEY_' "$DOTENV_FILE" > "${DOTENV_FILE}.tmp" && mv "${DOTENV_FILE}.tmp" "$DOTENV_FILE"
{
  echo "LITELLM_VKEY_CLOUD_DEV=${CLOUD_DEV_KEY}"
  echo "LITELLM_VKEY_LOCAL=${LOCAL_KEY}"
} >> "$DOTENV_FILE"

# Update Odoo provider records via JSON-RPC
echo "--> Updating Odoo llm.provider records..."

odoo_write() {
  local model="$1" domain="$2" field="$3" value="$4"
  curl -sf -X POST \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"id\":1,\"params\":{
         \"model\":\"${model}\",
         \"method\":\"search_read\",
         \"args\":[[${domain}],[\"id\",\"name\"]],
         \"kwargs\":{}
        }}" \
    "${ODOO_URL}/web/dataset/call_kw" \
  | python -c "
import json,sys
d=json.load(sys.stdin)
for r in d.get('result',[]):
    print(r['id'])
"
}

CLOUD_ID=$(odoo_write "llm.provider" '"name","=","litellm-cloud-dev"' "" "")
LOCAL_ID=$(odoo_write "llm.provider" '"name","=","litellm-local"' "" "")

if [ -z "$CLOUD_ID" ] || [ -z "$LOCAL_ID" ]; then
  echo "WARNING: Could not find llm.provider records in Odoo."
  echo "  Keys are saved to .env. Re-run after ai_brain module is installed."
  exit 0
fi

# Write cloud-dev key
curl -sf -X POST \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"id\":2,\"params\":{
       \"model\":\"llm.provider\",
       \"method\":\"write\",
       \"args\":[[${CLOUD_ID}],{\"api_key\":\"${CLOUD_DEV_KEY}\"}],
       \"kwargs\":{}
      }}" \
  "${ODOO_URL}/web/dataset/call_kw" > /dev/null

# Write local key
curl -sf -X POST \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"id\":3,\"params\":{
       \"model\":\"llm.provider\",
       \"method\":\"write\",
       \"args\":[[${LOCAL_ID}],{\"api_key\":\"${LOCAL_KEY}\"}],
       \"kwargs\":{}
      }}" \
  "${ODOO_URL}/web/dataset/call_kw" > /dev/null

echo ""
echo "==> Done. Provider keys updated in Odoo."
echo "    Dev Assistant  → litellm-cloud-dev → github-dev  (GitHub Models)"
echo "    Local Assistant → litellm-local    → prod-local  (Ollama qwen2.5:7b)"
echo ""
echo "    To verify scope enforcement, run: make eval --filter task_007"
