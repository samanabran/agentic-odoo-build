#!/usr/bin/env bash
# scripts/deploy_addons_to_prod.sh
#
# Rsyncs ai_brain and the required Apexive vendor modules to the production
# server's extra-addons directory. Idempotent — safe to run multiple times.
# Does NOT restart Odoo; restart is a separate explicit step.
#
# Usage:
#   bash scripts/deploy_addons_to_prod.sh          # real deploy
#   bash scripts/deploy_addons_to_prod.sh -n        # dry-run (no changes)
#
# Environment variables:
#   PROD_HOST      — SSH host           (default: 80.241.218.108)
#   PROD_USER      — SSH user           (default: root)
#   PROD_ADDONS    — Remote addons path (default: /opt/odoo-prod/extra-addons)
#   SSH_KEY        — Path to SSH identity file (optional)

set -euo pipefail

PROD_HOST="${PROD_HOST:-80.241.218.108}"
PROD_USER="${PROD_USER:-root}"
PROD_ADDONS="${PROD_ADDONS:-/opt/odoo-prod/extra-addons}"
SSH_KEY="${SSH_KEY:-}"

DRY_RUN=false
if [[ "${1:-}" == "-n" || "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Vendor modules to deploy (plan D5 — held-back modules excluded)
VENDOR_MODULES=(
  llm
  llm_thread
  llm_tool
  llm_store
  llm_training
  web_json_editor
  llm_assistant
  llm_openai
  llm_mistral
  llm_knowledge
  llm_tool_knowledge
)
# NOT included: llm_ollama (private mode only), llm_pgvector (M5, needs pgvector ext)
# NOT included: llm_mcp_server (M7), llm_tool_account (M7)
# Added (transitive deps): llm_store, llm_training, web_json_editor, llm_mistral

VENDOR_SRC="${REPO_ROOT}/addons/vendor/odoo-llm"
BRAIN_SRC="${REPO_ROOT}/addons/ai_brain"

SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=10)
if [[ -n "${SSH_KEY}" ]]; then
  SSH_OPTS+=(-i "${SSH_KEY}")
fi

RSYNC_OPTS=(-avz --delete --exclude='.git' --exclude='__pycache__' --exclude='*.pyc')
if $DRY_RUN; then
  RSYNC_OPTS+=(--dry-run)
  echo "==> DRY-RUN mode — no changes will be made"
fi

RSYNC_SSH="ssh ${SSH_OPTS[*]}"

echo "==> Deploying addons to ${PROD_USER}@${PROD_HOST}:${PROD_ADDONS}"
echo ""

# Assert vendor submodule is clean (CLAUDE.md B2 zero-diff policy)
if ! git -C "${VENDOR_SRC}" diff --quiet HEAD 2>/dev/null; then
  echo "ERROR: Vendor submodule has uncommitted changes. Vendor diff must be zero."
  echo "       Run: git -C addons/vendor/odoo-llm diff HEAD"
  exit 1
fi

# Deploy each vendor module
for MODULE in "${VENDOR_MODULES[@]}"; do
  MODULE_PATH="${VENDOR_SRC}/${MODULE}"
  if [[ ! -d "${MODULE_PATH}" ]]; then
    echo "ERROR: Vendor module directory not found: ${MODULE_PATH}"
    echo "       Run: git submodule update --init addons/vendor/odoo-llm"
    exit 1
  fi
  echo "--> ${MODULE}"
  rsync "${RSYNC_OPTS[@]}" \
    -e "${RSYNC_SSH}" \
    "${MODULE_PATH}/" \
    "${PROD_USER}@${PROD_HOST}:${PROD_ADDONS}/${MODULE}/"
done

# Deploy ai_brain
echo "--> ai_brain"
rsync "${RSYNC_OPTS[@]}" \
  -e "${RSYNC_SSH}" \
  "${BRAIN_SRC}/" \
  "${PROD_USER}@${PROD_HOST}:${PROD_ADDONS}/ai_brain/"

echo ""
if $DRY_RUN; then
  echo "==> Dry-run complete. Re-run without -n to apply."
else
  echo "==> Deploy complete."
  echo ""
  echo "    Next steps:"
  echo "    1. Verify:        ssh ${PROD_USER}@${PROD_HOST} ls ${PROD_ADDONS}/"
  echo "    2. Install (first time):"
  echo "         docker exec odoo-prod odoo -d odoo19-sgc \\"
  echo "           -i llm,llm_thread,llm_tool,llm_store,llm_training,web_json_editor,llm_assistant,llm_openai,llm_mistral,llm_knowledge,llm_tool_knowledge,ai_brain \\"
  echo "           --stop-after-init"
  echo "    3. Restart:       docker restart odoo-prod"
  echo "    4. Health check:  curl -sf https://sgctech.ai/web/health"
fi
