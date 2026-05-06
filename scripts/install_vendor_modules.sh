#!/usr/bin/env bash
# scripts/install_vendor_modules.sh
#
# Idempotently installs the nine Apexive vendor modules in the correct order.
# Safe to run multiple times — already-installed modules are skipped by Odoo.
#
# Usage:
#   DB_NAME=odoo bash scripts/install_vendor_modules.sh
#
# Environment variables:
#   DB_NAME   — Odoo database name (default: odoo)
#   ODOO_URL  — Odoo base URL      (default: http://localhost:8069)
#   ODOO_ADMIN_PASSWD — master password (default: admin)
#
# Requires: curl, jq

set -euo pipefail

DB_NAME="${DB_NAME:-odoo}"
ODOO_URL="${ODOO_URL:-http://localhost:8069}"
ADMIN_PASSWD="${ODOO_ADMIN_PASSWD:-admin}"

# Ordered install list (B1 Tier 2) — llm_mcp_server and llm_tool_account are M7
MODULES=(
  llm
  llm_thread
  llm_tool
  llm_assistant
  llm_openai
  llm_ollama
  llm_pgvector
  llm_knowledge
  llm_tool_knowledge
)

echo "==> Installing Apexive vendor modules on DB '${DB_NAME}' at ${ODOO_URL}"

odoo_rpc() {
  local endpoint="$1"
  local payload="$2"
  curl -sf \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "${ODOO_URL}${endpoint}"
}

# Authenticate
echo "--> Authenticating..."
AUTH_RESPONSE=$(odoo_rpc "/web/dataset/call_kw" \
  "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"params\":{
     \"model\":\"ir.module.module\",
     \"method\":\"search_read\",
     \"args\":[[[ \"name\",\"in\",[\"base\"]]],[\"name\",\"state\"]],
     \"kwargs\":{\"context\":{\"lang\":\"en_US\"}}
  }}")

# Check Odoo is reachable
if ! echo "$AUTH_RESPONSE" | grep -q '"result"'; then
  echo "ERROR: Odoo is not reachable at ${ODOO_URL}. Is the stack running?"
  exit 1
fi

echo "--> Odoo reachable. Proceeding with module installation..."

for MODULE in "${MODULES[@]}"; do
  echo -n "    Installing ${MODULE}... "

  RESULT=$(odoo_rpc "/web/dataset/call_kw" \
    "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"id\":1,\"params\":{
       \"model\":\"ir.module.module\",
       \"method\":\"search_read\",
       \"args\":[[[ \"name\",\"=\",\"${MODULE}\"]]],[\"name\",\"state\"]],
       \"kwargs\":{\"context\":{\"lang\":\"en_US\",\"active_test\":false}}
    }}")

  STATE=$(echo "$RESULT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
recs=d.get('result',[])
print(recs[0]['state'] if recs else 'not_found')
" 2>/dev/null || echo "unknown")

  if [ "$STATE" = "installed" ]; then
    echo "already installed, skipping."
    continue
  fi

  if [ "$STATE" = "not_found" ]; then
    echo ""
    echo "ERROR: Module '${MODULE}' not found in Odoo's module list."
    echo "  Ensure addons/vendor/odoo-llm is checked out and --addons-path is correct."
    exit 1
  fi

  # Trigger install
  INSTALL_RESULT=$(odoo_rpc "/web/dataset/call_kw" \
    "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"id\":2,\"params\":{
       \"model\":\"ir.module.module\",
       \"method\":\"button_immediate_install\",
       \"args\":[[$(echo "$RESULT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d['result'][0]['id'])
")]],
       \"kwargs\":{\"context\":{\"lang\":\"en_US\"}}
    }}")

  if echo "$INSTALL_RESULT" | grep -q '"error"'; then
    echo "FAILED."
    echo "$INSTALL_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('error',{}).get('data',{}).get('message','unknown error'))"
    exit 1
  fi
  echo "done."
done

echo ""
echo "==> All vendor modules installed successfully."
echo "    Verify: http://localhost:8069/odoo/settings/apps (filter: installed)"
