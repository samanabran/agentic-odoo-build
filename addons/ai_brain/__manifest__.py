{
    "name": "AI Brain",
    "version": "19.0.1.0.0",
    "summary": "In-app AI assistant — chat panel, audit log, approval flow, and RAG",
    "author": "AI Brain Project",
    "category": "Productivity",
    "depends": [
        "base",
        "web",
        "mail",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
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
