# ADR 0001 — Stack Choices

**Date:** 2026-05-06
**Status:** Accepted

## Context

Initial infrastructure decisions before the first line of production code is written.

---

## Decision 1 — Odoo 19 Community

**Chosen:** Odoo 19 Community Edition (`odoo:19.0` Docker image)

**Alternative rejected:** Odoo 18.0 — safer given Apexive's active branch, but client explicitly chose 19.

**Rationale:**
- Odoo 19 is the current stable release (shipped October 2025)
- Community Edition gives full source access at zero license cost; swap to Enterprise by changing the Docker image
- Odoo 19 ships the native `productivity.ai` module, one of our two required foundations

**Risk accepted:** Apexive's `odoo-llm` has no 19.0 branch as of May 2026. Managed via the vendor-patch strategy (ADR 0002).

---

## Decision 2 — LiteLLM as the LLM gateway

**Chosen:** LiteLLM sidecar (`ghcr.io/berriai/litellm:main-stable`); orchestrator never calls providers directly.

**Alternative rejected:** Direct `openai` / `anthropic` SDK calls inside the orchestrator.

**Rationale:**
- Provider swap is a single line in `infra/litellm/config.yaml`, not a code change
- Built-in spend tracking, fallback routing, and request logging
- Orchestrator holds no provider API keys; isolation limits blast radius of a key leak
- `PRIVATE_MODE=true` routing to Ollama requires no orchestrator code path changes

---

## Decision 3 — Apexive odoo-llm as git submodule, not a fork

**Chosen:** Submodule pinned to a specific SHA; Odoo 19 compatibility delivered as `.patch` files in `patches/vendor/`, applied during bootstrap via `make patch-vendor`.

**Alternative rejected:** Full fork of the repo.

**Rationale:**
- Vendor diff inside the submodule stays at zero — upstream bug fixes available via `git submodule update` + re-running patches
- Patches are explicit, auditable, and bounded; when Apexive ships a 19.0 branch the patches are deleted and the pin is updated
- A fork creates an unbounded maintenance burden with no upstream merge path

---

## Decision 4 — pgvector co-located with Odoo's PostgreSQL

**Chosen:** `pgvector` extension on the same PostgreSQL 16 instance Odoo uses.

**Alternatives rejected:** Qdrant, Chroma, Weaviate as separate services.

**Rationale:**
- Eliminates a service: fewer moving parts, same backup/restore covers relational and vector data
- Joins between Odoo records and their chunk embeddings incur no network hop
- pgvector with HNSW indexing on pg16 handles tens of millions of vectors — sufficient for our expected record count
- Revisit if we exceed ~10 M chunks or require approximate-nearest-neighbour throughput beyond pg16's capability
