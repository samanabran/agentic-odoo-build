# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

import pytest

odoo = pytest.importorskip("odoo")

try:
    from odoo.tests.common import TransactionCase
except Exception:
    TransactionCase = None


@pytest.mark.skipif(TransactionCase is None, reason="Odoo ORM not available")
class TestAmlHeuristics(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.finance = cls.env["ai.brain.finance"]

    def test_structuring_flags_only_85_to_99_percent_band(self):
        lines = [
            {"amount": 8500.0},
            {"amount": 9000.0},
            {"amount": 9900.0},
            {"amount": 10000.0},
        ]

        result = self.finance._detect_structuring(lines, 10000.0)

        self.assertEqual(result["transaction_count"], 3)
        self.assertEqual(result["total_amount"], 27400.0)

    def test_high_frequency_requires_more_than_ten_transactions_in_24h(self):
        start = datetime(2026, 5, 12, 9, 0, 0)
        ten_in_23h = [
            {"timestamp": start + timedelta(hours=index * 2 + 1), "amount": 100.0}
            for index in range(10)
        ]
        eleven_in_23h = ten_in_23h + [{"timestamp": start + timedelta(hours=23), "amount": 100.0}]

        self.assertIsNone(self.finance._detect_high_frequency(ten_in_23h))

        result = self.finance._detect_high_frequency(eleven_in_23h)
        self.assertEqual(result["transaction_count"], 11)
        self.assertEqual(result["total_amount"], 1100.0)

    def test_round_number_requires_at_least_three_multiples_of_1000(self):
        two_round = [{"amount": 1000.0}, {"amount": 5000.0}]
        three_round = two_round + [{"amount": 7000.0}]

        self.assertIsNone(self.finance._detect_round_number(two_round))

        result = self.finance._detect_round_number(three_round)
        self.assertEqual(result["transaction_count"], 3)
        self.assertEqual(result["total_amount"], 13000.0)
