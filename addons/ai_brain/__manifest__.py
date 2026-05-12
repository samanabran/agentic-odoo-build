{
    "name": "AI Brain",
    "version": "18.0.1.0.0",
    "summary": "In-app AI assistant — chat panel, audit log, approval flow, and RAG",
    "author": "AI Brain Project",
    "category": "Productivity",
    "depends": [
        "base",
        "web",
        # Apexive vendor modules (M2) — must be installed first via
        # scripts/deploy_addons_to_prod.sh; loaded from addons/vendor/odoo-llm, incl. llm_mistral
        "llm",
        "llm_thread",
        "llm_tool",
        "llm_assistant",
        "llm_openai",
        "llm_mistral",
        "llm_knowledge",
        "llm_tool_knowledge",
        # NOT included: llm_ollama (private mode only), llm_pgvector (M5, needs pgvector ext)
        # NOT included: llm_mcp_server (M7), llm_tool_account (M7)
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/llm_providers.xml",
        "templates/dashboard.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ai_brain/static/src/components/AiBrainPanel.js",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
