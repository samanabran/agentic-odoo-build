# ADR 0014: Matching Engine Approach — Deterministic-First vs LLM Classification

**Status:** Accepted  
**Date:** 2026-05-12  
**Deciders:** Atlas (Orchestrator)  

## Context

M4 (Financial Intelligence Tools) requires a transaction matching engine to pair bank statement lines with open journal items. Two approaches were considered:

1. **LLM Classification**: Send candidate pairs to an LLM with a classification prompt
2. **Deterministic Scoring**: Pure Python algorithm based on amount tolerance, date proximity, partner match, and reference overlap

## Decision

We will use **deterministic Python scoring** for matching decisions. LLM will be used only for generating plain-language rationale on low-confidence pairs (confidence < 65).

## Rationale

| Factor | Deterministic | LLM Classification |
|--------|--------------|-------------------|
| **Auditability** | Fully traceable — same inputs always produce same score | Black-box — prompt changes, model updates change behavior |
| **Cost** | Zero per-call cost | ~$0.001-0.01 per pair evaluated |
| **Latency** | <2ms per pair locally | 500ms-2s per batch (API round-trip) |
| **Testability** | Unit tests guarantee exact scores | Flaky tests due to non-determinism |
| **Regulatory** | Defensible in audit — code is the decision log | Harder to explain "why" to auditors |

For M4's use case (matching thousands of transactions), deterministic scoring is essential for cost control and audit compliance.

## Scoring Algorithm

```python
score = 0
if currency_match:
    if amount_exact and partner_match and reference_overlap:
        score = 95
    elif amount_within_tolerance and partner_match:
        score = 80
    elif amount_within_tolerance and date_within_range:
        score = 65
    elif amount_within_tolerance:
        score = 45
else:
    score = 0  # Currency mismatch disqualifies
```

**Parameters** (configurable per session):
- Amount tolerance: ±2.0% (default)
- Date window: ±5 days (default)
- Reference similarity: Jaccard index ≥ 0.3 for partial credit
- Partner match: Exact partner_id match or fuzzy name match ≥ 80%

## Consequences

### Positive
- Deterministic, reproducible results
- No LLM costs for core matching logic
- Fast execution (100 × 200 pairs in <2 seconds)
- Full test coverage possible
- Audit-friendly: decision logic is visible Python code

### Negative
- Cannot handle semantic similarity (e.g., "ABC Corp" vs "ABC Corporation") without enhancement
- Thresholds require tuning for different transaction volumes
- Edge cases (partial payments, split transactions) require explicit code paths

### Mitigations
- LLM fallback generates narrative for ambiguous pairs (confidence < 65)
- Fuzzy string matching (token-set ratio) handles minor name variations
- Configurable thresholds via `ir.config_parameter`

## Related

- M4 Plan: `docs/plans/2026-05-12-001-feat-m4-financial-intelligence-tools-plan.md`
- Matching Engine: `addons/ai_brain/services/matching_engine.py`
- AML Heuristics: Deterministic rules also used for AML pattern detection
