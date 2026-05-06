## chore: downgrade Odoo 19 → 18, pin image digest, close ADR 0006

### Why

M2 spike (ADR 0006) confirmed Odoo 19's `check_version()` hard-blocks all
`18.0.x` vendor modules at manifest-load time — before any addon code runs.
No override path exists within the B2 zero-diff constraint. Rollback executed
per ADR 0005 plan with explicit owner approval.

### Changes

| File | Change |
|---|---|
| `infra/docker-compose.yml` | `odoo:19.0` → `odoo@sha256:b79d87a4...` (pinned digest) |
| `addons/ai_brain/__manifest__.py` | `19.0.1.0.0` → `18.0.1.0.0` |
| `docs/adr/0004` | Decision 1 superseded footnote |
| `docs/adr/0005` | Odoo row updated; rollback record appended |
| `docs/adr/0006` | Resolution section added — **CLOSED** |
| `docs/adr/0007` | **NEW** — image digest pinning rationale |
| `CLAUDE.md` | Section B Tier 1 + Section C + squash-merge policy |
| `AGENTS.md` | Stack table + Odoo 18 conventions heading |
| `docs/ARCHITECTURE.md`, `scripts/bootstrap.sh`, `.env.example` | 18.0 |
| `.github/workflows/ci.yml` | **NEW** — lint / test / eval on every PR |
| `.github/CODEOWNERS` | **NEW** — owner routing for vendor, ADRs, infra |

### Grep sweep

**Before:** 12 hits for `19.0` outside vendor/git  
**After:** 0 hits (only `kickoff-odoo-ai-brain.html` exempt as historical artifact)

### M1 gate results (post-rollback, odoo:18.0 base)

```
make test  →  19 passed
make lint  →  ruff: All checks passed | mypy: no issues (9 files)
make eval  →  1 passed  7 skipped  0 failed
```

### Image digest pin

```
odoo@sha256:b79d87a4ec1a3806d133e12a07dc06402fc37397eb285663b1acfea2001ae52c
```

Pulled 2026-05-06. See ADR 0007 for rationale and update procedure.

### Vendor diff check

```
git -C addons/vendor/odoo-llm diff --quiet HEAD  →  (zero output — clean)
```

### ADR 0006 resolution

See [docs/adr/0006-m2-spike-findings.md](docs/adr/0006-m2-spike-findings.md#resolution--2026-05-06) — status CLOSED.

### Test plan

- [ ] CI passes (`lint-test-eval` job green)
- [ ] Reviewer confirms `19.0` appears only in `kickoff-odoo-ai-brain.html`
- [ ] Vendor diff is zero: `git -C addons/vendor/odoo-llm diff --quiet HEAD`
- [ ] `make up` starts cleanly with pinned `odoo:18.0` image

### Merge

Squash and merge (project policy per CLAUDE.md A1).