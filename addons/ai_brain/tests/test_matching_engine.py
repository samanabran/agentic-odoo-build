from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
import importlib.util

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "services" / "matching_engine.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location("matching_engine", MODULE_PATH)
MATCHING_ENGINE_MODULE = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(MATCHING_ENGINE_MODULE)
MatchingEngine = MATCHING_ENGINE_MODULE.MatchingEngine


def _line(**overrides):
    base = {
        "id": 1,
        "amount": 100.0,
        "date": date(2026, 5, 12),
        "partner_id": 10,
        "ref": "INV 001",
        "currency_id": 1,
    }
    base.update(overrides)
    return base


def test_exact_match_scores_high():
    engine = MatchingEngine()
    score, reason = engine.score_pair(_line(), _line(id=2))

    assert score >= 90
    assert reason == "exact_amount_partner_ref"


def test_amount_within_tolerance_and_same_partner_scores_partner_band():
    engine = MatchingEngine(tolerance_pct=2.0)
    stmt = _line(amount=100.0)
    move = _line(id=2, amount=98.5, ref="different reference")

    score, reason = engine.score_pair(stmt, move)

    assert score >= 70
    assert reason == "amount_partner"


def test_amount_within_tolerance_and_close_date_scores_mid_band():
    engine = MatchingEngine(tolerance_pct=4.0, date_range_days=2)
    stmt = _line(amount=100.0, partner_id=10)
    move = _line(
        id=2,
        amount=96.0,
        partner_id=99,
        ref="unrelated",
        date=date(2026, 5, 14),
    )

    score, reason = engine.score_pair(stmt, move)

    assert 60 <= score <= 75
    assert reason == "amount_date"


def test_amount_outside_tolerance_scores_zero():
    engine = MatchingEngine(tolerance_pct=2.0)
    score, reason = engine.score_pair(_line(amount=100.0), _line(id=2, amount=90.0))

    assert score == 0
    assert reason == "amount_out_of_tolerance"


def test_currency_mismatch_returns_explicit_reason():
    engine = MatchingEngine()
    result = engine.score_pair(_line(currency_id=1), _line(id=2, currency_id=2))

    assert result == (0, "currency_mismatch")


def test_empty_references_do_not_crash():
    engine = MatchingEngine(tolerance_pct=2.0)
    score, reason = engine.score_pair(
        _line(ref="", amount=100.0),
        _line(id=2, ref="", amount=101.0, partner_id=999, date=date(2026, 5, 30)),
    )

    assert score == 45
    assert reason == "amount_only"


def test_find_candidates_returns_empty_for_no_move_lines():
    engine = MatchingEngine()

    assert engine.find_candidates({}, [_line()], []) == []


def test_jaccard_similarity_partial_overlap_matches_expected_ratio():
    engine = MatchingEngine()
    similarity = engine._jaccard_similarity("INV 001", "INV 002")

    assert similarity == pytest.approx(1 / 3, rel=1e-2)


def test_find_candidates_performance_guard():
    engine = MatchingEngine(tolerance_pct=2.0, date_range_days=5)
    base_date = date(2026, 5, 12)
    stmt_lines = [
        _line(
            id=index,
            amount=100.0 + (index % 7),
            date=base_date + timedelta(days=index % 5),
            partner_id=index % 9,
            ref=f"INV {index}",
        )
        for index in range(100)
    ]
    move_lines = [
        _line(
            id=1000 + index,
            amount=100.0 + (index % 7),
            date=base_date + timedelta(days=index % 5),
            partner_id=index % 9,
            ref=f"INV {index % 100}",
        )
        for index in range(200)
    ]

    started = perf_counter()
    results = engine.find_candidates({}, stmt_lines, move_lines)
    elapsed = perf_counter() - started

    assert results
    assert elapsed < 2.0
