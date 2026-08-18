from __future__ import annotations

import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from governai.generator import generate_sources
from governai.model_governance import (
    build_model_governance,
    linear_forecast,
    standardized_mean_difference,
)
from governai.pipeline import LocalPipeline


class ModelGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        generated = generate_sources(root / "sources")
        pipeline = LocalPipeline(root / "governai.db")
        pipeline.initialize()
        pipeline.run_demo(generated.base_dir, generated.incident_file)
        self.connection = sqlite3.connect(root / "governai.db")

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary.cleanup()

    def test_linear_challenger_is_transparent(self) -> None:
        self.assertEqual(linear_forecast([1.0, 2.0, 3.0]), 4.0)
        self.assertEqual(linear_forecast([3.0, 3.0, 3.0]), 3.0)
        with self.assertRaisesRegex(ValueError, "At least two"):
            linear_forecast([1.0])

    def test_standardized_mean_difference_matches_reference(self) -> None:
        baseline, current = [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]
        expected = 1.0 / math.sqrt(2 / 3)
        self.assertAlmostEqual(
            standardized_mean_difference(baseline, current), expected, places=12
        )

    def test_backtest_metrics_reconcile_from_folds(self) -> None:
        evidence = build_model_governance(self.connection)
        folds = evidence["backtest"]["folds"]
        baseline_mae = sum(
            abs(fold["baseline_prediction"] - fold["actual"]) for fold in folds
        ) / len(folds)
        challenger_mae = sum(
            abs(fold["challenger_prediction"] - fold["actual"]) for fold in folds
        ) / len(folds)
        candidates = {row["model_id"]: row for row in evidence["backtest"]["candidates"]}
        self.assertAlmostEqual(candidates["last_observation_baseline"]["mae"], baseline_mae, places=2)
        self.assertAlmostEqual(candidates["ols_trend_challenger"]["mae"], challenger_mae, places=2)
        self.assertEqual(evidence["backtest"]["fold_count"], 3)

    def test_model_cannot_pass_production_gate(self) -> None:
        evidence = build_model_governance(self.connection)
        gates = {gate["gate"]: gate["status"] for gate in evidence["approval_gates"]}
        self.assertEqual(evidence["status"], "RESEARCH_ONLY_LOCALLY_VERIFIED")
        self.assertEqual(evidence["backtest"]["decision"], "RESEARCH_CHAMPION_NOT_PRODUCTION_APPROVED")
        self.assertEqual(gates["Production deployment"], "BLOCKED")
        self.assertEqual(gates["Model risk review"], "NOT_RUN")
        self.assertEqual(len(evidence["drift"]["metrics"]), 3)
        self.assertNotRegex(json.dumps(evidence), r"ACC-\d{5}|CUS-\d{5}|TXN-\d{8}")


if __name__ == "__main__":
    unittest.main()
