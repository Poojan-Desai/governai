from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from governai.generator import TRANSACTION_FIELDS, generate_sources, write_csv
from governai.contracts import result
from governai.pipeline import LocalPipeline, PipelineExecutionError


class TransactionReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.generated = generate_sources(
            self.root / "sources", customer_count=20, account_count=25,
            transactions_per_month=10,
        )
        self.pipeline = LocalPipeline(self.root / "governai.db")
        self.pipeline.initialize()
        self.outcomes = self.pipeline.run_demo(self.generated.base_dir, self.generated.incident_file)
        with (self.generated.base_dir / "transactions.csv").open(newline="") as handle:
            self.existing = next(csv.DictReader(handle))
        self.candidate = {**self.existing, "transaction_id": "TXN-REPLAY-NEW"}

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_batch(self, filename, rows):
        path = self.root / filename
        write_csv(path, TRANSACTION_FIELDS, rows)
        return path

    def products(self):
        with self.pipeline.connect() as connection:
            return {
                table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
                for table in (
                    "raw_transactions", "fct_card_transactions", "feature_account_behavior_30d",
                    "mart_monthly_loss_kpis", "model_loss_forecast",
                )
            }

    def test_mixed_batch_with_existing_ids_is_file_atomically_quarantined(self) -> None:
        before = self.products()
        # Both an exact replay and a conflicting payload must be rejected under
        # a different batch identity, without publishing the otherwise-new row.
        for name, existing in (
            ("exact", self.existing),
            ("changed", {**self.existing, "amount": "123456.78"}),
        ):
            with self.subTest(name=name):
                path = self.write_batch(f"{name}.csv", [self.candidate, existing])
                with patch.object(self.pipeline, "load_transactions") as loader:
                    first = self.pipeline.ingest_transactions(path, name)
                    repeated = self.pipeline.ingest_transactions(path, name)
                    loader.assert_not_called()
                self.assertEqual((first.status, first.source_rows, first.accepted_rows, first.quarantined_rows), ("quarantined", 2, 0, 2))
                self.assertEqual(repeated, first)
                check = next(check for check in first.checks if check.rule_id == "transaction_id_not_previously_loaded")
                self.assertEqual((check.passed, check.failed_rows, check.severity), (False, 1, "critical"))
                self.assertEqual(self.products(), before)
                with self.pipeline.connect() as connection:
                    event = connection.execute("SELECT * FROM audit_events WHERE run_id=?", (first.run_id,)).fetchone()
                    details = json.loads(event["details_json"])
                    self.assertEqual((event["action"], event["outcome"]), ("batch.quarantined", "blocked"))
                    self.assertIn(check.rule_id, details["failed_rules"])
                    self.assertNotIn(self.existing["transaction_id"], event["details_json"])
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM source_manifests WHERE run_id=?", (first.run_id,)).fetchone()[0], 1)

    def test_original_success_rerun_returns_original_outcome_without_loading(self) -> None:
        before = self.products()
        with patch.object(self.pipeline, "load_transactions") as loader:
            repeated = self.pipeline.ingest_transactions(self.generated.base_dir / "transactions.csv")
            loader.assert_not_called()
        self.assertEqual(repeated, self.outcomes["transactions"])
        self.assertEqual(self.products(), before)

    def test_new_label_does_not_bypass_transaction_replay_protection(self) -> None:
        before = self.products()
        result = self.pipeline.ingest_transactions(self.generated.base_dir / "transactions.csv", "explicit-replay")
        self.assertEqual((result.status, result.accepted_rows, result.quarantined_rows), ("quarantined", 0, 60))
        self.assertNotEqual(result.run_id, self.outcomes["transactions"].run_id)
        self.assertEqual(self.products(), before)

    def test_new_transaction_counts_reconcile_with_actual_insertions(self) -> None:
        before = len(self.products()["raw_transactions"])
        path = self.write_batch("new.csv", [self.candidate])
        outcome = self.pipeline.ingest_transactions(path, "new")
        self.assertEqual((outcome.status, outcome.accepted_rows), ("succeeded", 1))
        with self.pipeline.connect() as connection:
            inserted = connection.execute("SELECT COUNT(*) FROM raw_transactions WHERE ingestion_run_id=?", (outcome.run_id,)).fetchone()[0]
            self.assertEqual(inserted, outcome.accepted_rows)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM raw_transactions").fetchone()[0] - before, outcome.accepted_rows)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM fct_card_transactions").fetchone()[0], before + 1)
        self.assertTrue(next(c for c in outcome.checks if c.rule_id == "transaction_id_not_previously_loaded").passed)

    def test_large_batch_collision_uses_bounded_identifier_queries(self) -> None:
        # Exercise more than SQLite's traditional 999 bind-variable limit, with
        # an existing identifier in a later chunk of candidates.
        candidates = [{**self.candidate, "transaction_id": f"AAA-LARGE-{index:05d}"} for index in range(1100)]
        path = self.write_batch("large.csv", [*candidates, self.existing])
        before = self.products()
        original_connect = self.pipeline.connect

        @contextmanager
        def limited_connect():
            with original_connect() as connection:
                connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 999)
                yield connection

        with patch.object(self.pipeline, "connect", limited_connect):
            outcome = self.pipeline.ingest_transactions(path, "large")
        self.assertEqual((outcome.status, outcome.accepted_rows, outcome.quarantined_rows), ("quarantined", 0, 1101))
        self.assertEqual(self.products(), before)

    def test_unique_constraint_is_a_final_guard_against_silent_skips(self) -> None:
        path = self.write_batch("guard.csv", [self.candidate, self.existing])
        before = self.products()
        # Inject a missed quality check: the strict loader must still reject a
        # duplicate, roll back the preceding new row and retain failure evidence.
        with patch.object(self.pipeline, "transaction_replay_check", return_value=result("injected", "Injected pass", 0, "0")):
            with self.assertRaises(PipelineExecutionError) as raised:
                self.pipeline.ingest_transactions(path, "guard")
        self.assertIsInstance(raised.exception.__cause__, sqlite3.IntegrityError)
        self.assertEqual(self.products(), before)
        with self.pipeline.connect() as connection:
            run = connection.execute("SELECT status,accepted_row_count FROM pipeline_runs WHERE run_id=?", (raised.exception.run_id,)).fetchone()
            self.assertEqual(tuple(run), ("failed", 0))

    def concurrent_ingest(self, path, labels):
        barrier = Barrier(2)

        def run(label):
            pipeline = LocalPipeline(self.pipeline.database_path)
            barrier.wait(timeout=5)
            return pipeline.ingest_transactions(path, label)

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, labels))

    def test_concurrent_same_batch_reruns_share_one_success_record(self) -> None:
        path = self.write_batch("concurrent-same.csv", [self.candidate])
        first, second = self.concurrent_ingest(path, ("same", "same"))
        self.assertEqual(first, second)
        self.assertEqual(first.status, "succeeded")
        with self.pipeline.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM pipeline_runs WHERE batch_id=?", (first.batch_id,)).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM audit_events WHERE run_id=?", (first.run_id,)).fetchone()[0], 1)

    def test_concurrent_distinct_batches_cannot_publish_the_same_transaction(self) -> None:
        path = self.write_batch("concurrent-distinct.csv", [self.candidate])
        results = self.concurrent_ingest(path, ("first", "second"))
        self.assertEqual(sorted(result.status for result in results), ["quarantined", "succeeded"])
        success = next(result for result in results if result.status == "succeeded")
        blocked = next(result for result in results if result.status == "quarantined")
        self.assertEqual((success.accepted_rows, blocked.accepted_rows, blocked.quarantined_rows), (1, 0, 1))
        with self.pipeline.connect() as connection:
            stored = connection.execute("SELECT ingestion_run_id FROM raw_transactions WHERE transaction_id=?", (self.candidate["transaction_id"],)).fetchall()
            self.assertEqual([row[0] for row in stored], [success.run_id])


if __name__ == "__main__":
    unittest.main()
