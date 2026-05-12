from __future__ import annotations

from datetime import date, datetime


class MatchingEngine:
    def __init__(self, tolerance_pct: float = 2.0, date_range_days: int = 5):
        self.tolerance_pct = tolerance_pct
        self.date_range_days = date_range_days

    def score_pair(self, stmt_line: dict, move_line: dict) -> tuple[int, str]:
        if stmt_line.get("currency_id") != move_line.get("currency_id"):
            return (0, "currency_mismatch")

        stmt_amount = self._coerce_amount(stmt_line.get("amount"))
        move_amount = self._coerce_amount(move_line.get("amount"))
        amount_diff_pct = self._amount_diff_pct(stmt_amount, move_amount)
        partner_match = stmt_line.get("partner_id") == move_line.get("partner_id")
        date_within_range = self._date_within_range(
            stmt_line.get("date"), move_line.get("date")
        )
        ref_overlap = self._jaccard_similarity(
            stmt_line.get("ref", ""), move_line.get("ref", "")
        ) >= 0.3

        if stmt_amount == move_amount and partner_match and ref_overlap:
            return (95, "exact_amount_partner_ref")
        if amount_diff_pct <= self.tolerance_pct and partner_match:
            return (80, "amount_partner")
        if amount_diff_pct <= self.tolerance_pct and date_within_range:
            return (65, "amount_date")
        if amount_diff_pct <= self.tolerance_pct:
            return (45, "amount_only")
        return (0, "amount_out_of_tolerance")

    def find_candidates(
        self,
        session_vals: dict,
        stmt_lines: list[dict],
        move_lines: list[dict],
    ) -> list[dict]:
        del session_vals
        results = []
        for stmt in stmt_lines:
            for move in move_lines:
                score, reason = self.score_pair(stmt, move)
                if score > 0:
                    results.append(
                        {
                            "stmt_line_id": stmt.get("id"),
                            "move_line_id": move.get("id"),
                            "confidence": score,
                            "match_reason": reason,
                        }
                    )
        return sorted(results, key=lambda x: x["confidence"], reverse=True)

    def _jaccard_similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        tokens_a = set(str(a).lower().split())
        tokens_b = set(str(b).lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    def _amount_diff_pct(self, stmt_amount: float, move_amount: float) -> float:
        denominator = max(abs(stmt_amount), abs(move_amount))
        if denominator == 0:
            return 0.0
        return abs(stmt_amount - move_amount) / denominator * 100

    def _coerce_amount(self, value: object) -> float:
        if value is None:
            return 0.0
        return float(value)

    def _date_within_range(self, stmt_date: object, move_date: object) -> bool:
        stmt_value = self._coerce_date(stmt_date)
        move_value = self._coerce_date(move_date)
        if stmt_value is None or move_value is None:
            return False
        return abs((stmt_value - move_value).days) <= self.date_range_days

    def _coerce_date(self, value: object) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        return None
