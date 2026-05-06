

## Live verification (PR #7 — 2026-05-07)

Full external dep scan across all vendor modules revealed additional packages beyond pydantic:

`
llm_thread:        emoji, markdown2
llm_tool:          pydantic>=2.0.0, mcp
llm_assistant:     jinja2, pyyaml, jsonschema
llm_openai:        openai
llm_ollama:        ollama
llm_pgvector:      pgvector, numpy
llm_knowledge:     requests, markdownify, PyMuPDF, numpy
`

All installed in one shot: pip install --break-system-packages emoji markdown2 mcp jinja2 pyyaml jsonschema openai ollama pgvector numpy requests markdownify PyMuPDF

make bootstrap-pydantic target updated to cover full dep list (see Makefile).
37 modules loaded in 19.02s — i_brain installed clean on first attempt after full install.
Status: **observed**.
