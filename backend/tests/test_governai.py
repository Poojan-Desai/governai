from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from governai.contracts import validate_transactions
from governai.generator import generate_sources
from governai.pipeline import LocalPipeline
from governai.snapshot import build_snapshot


class GovernAITests(unittest.TestCase):
    def test_generator_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = generate_sources(Path(first), seed=42, customer_count=20, account_count=25, transactions_per_month=20)
            two = generate_sources(Path(second), seed=42, customer_count=20, account_count=25, transactions_per_month=20)
            self.assertEqual(one.hashes, two.hashes)
            self.assertEqual(one.counts, two.counts)

    def test_incident_contains_four_independent_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_sources(Path(directory), customer_count=20, account_count=25, transactions_per_month=10)
            with generated.incident_file.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            failed = {c.rule_id: c.failed_rows for c in validate_transactions(rows, {f"ACC-{i:05d}" for i in range(1,26)}) if not c.passed}
            self.assertEqual(failed, {"transaction_id_unique":1,"transaction_amount_positive":1,"transaction_account_fk":1,"transaction_timestamp_valid":1})

    def test_valid_pipeline_and_atomic_incident(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = generate_sources(root / "sources", seed=2027, customer_count=40, account_count=55, transactions_per_month=40)
            pipeline = LocalPipeline(root / "governai.db"); pipeline.initialize()
            outcomes = pipeline.run_demo(generated.base_dir, generated.incident_file)
            with pipeline.connect() as connection:
                facts = connection.execute("SELECT COUNT(*) FROM fct_card_transactions").fetchone()[0]
                months = connection.execute("SELECT COUNT(*) FROM mart_monthly_loss_kpis").fetchone()[0]
                model = connection.execute("SELECT * FROM model_loss_forecast").fetchone()
            self.assertEqual(facts, 240); self.assertEqual(months, 6)
            self.assertEqual(model["method"], "ordinary_least_squares"); self.assertEqual(model["training_points"], 6)
            incident = outcomes["incident"]
            self.assertEqual((incident.status,incident.accepted_rows,incident.quarantined_rows),("quarantined",0,120))
            self.assertTrue({"feature.account_behavior_30d","mart.monthly_loss_kpis","model.loss_forecast_v1","dashboard.risk_operations"}.issubset(set(incident.impacted_assets)))
            repeat = pipeline.ingest_transactions(generated.incident_file,"quality-incident-001")
            self.assertEqual(repeat.run_id, incident.run_id)
            with pipeline.connect() as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fct_card_transactions").fetchone()[0],240)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM quarantine_batches").fetchone()[0],1)

    def test_public_snapshot_is_evidence_backed_and_contains_no_pii_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); generated=generate_sources(root/"sources",customer_count=30,account_count=40,transactions_per_month=25)
            pipeline=LocalPipeline(root/"db.sqlite"); pipeline.initialize(); pipeline.run_demo(generated.base_dir,generated.incident_file)
            snapshot=build_snapshot(root/"db.sqlite")
        self.assertEqual(snapshot["incident"]["warehouse_rows_before"],snapshot["incident"]["warehouse_rows_after"])
        self.assertEqual(snapshot["incident"]["failed_checks"].__len__(),4)
        text=json.dumps(snapshot).lower()
        self.assertNotIn("synthetic customer 00001",text); self.assertNotIn("customer00001@example.test",text); self.assertNotIn("+1-555-",text)
        self.assertEqual(sum(c["classification"]=="DIRECT_IDENTIFIER" for c in snapshot["column_classifications"]),3)


if __name__ == "__main__": unittest.main()
