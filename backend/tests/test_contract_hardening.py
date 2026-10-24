from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from governai.contracts import (
    has_critical_failure,
    validate_accounts,
    validate_customers,
    validate_transactions,
)
from governai.generator import (
    ACCOUNT_FIELDS,
    CUSTOMER_FIELDS,
    TRANSACTION_FIELDS,
    generate_sources,
    write_csv,
)
from governai.pipeline import LocalPipeline, PipelineExecutionError


class ContractHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        generated = generate_sources(
            self.root / "sources", customer_count=20, account_count=25,
            transactions_per_month=10,
        )
        self.cases = []
        for dataset, fields, validator in (
            ("customers", CUSTOMER_FIELDS, validate_customers),
            ("accounts", ACCOUNT_FIELDS, lambda rows, **kwargs: validate_accounts(rows, {"CUS-00001"}, **kwargs)),
            ("transactions", TRANSACTION_FIELDS, lambda rows, **kwargs: validate_transactions(rows, {"ACC-00001"}, **kwargs)),
        ):
            with (generated.base_dir / f"{dataset}.csv").open(newline="") as handle:
                row = next(csv.DictReader(handle))
            if dataset == "accounts":
                row["customer_id"] = "CUS-00001"
            elif dataset == "transactions":
                row["account_id"] = "ACC-00001"
            self.cases.append((dataset, fields, validator, row))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_valid_canonical_rows_pass_all_contracts(self) -> None:
        for dataset, fields, validator, row in self.cases:
            with self.subTest(dataset=dataset):
                self.assertFalse(has_critical_failure(validator([row], columns=fields)))

    def test_every_required_field_rejects_blank_and_missing_values(self) -> None:
        for dataset, fields, validator, row in self.cases:
            for field in fields:
                for value in ("", "   ", None):
                    with self.subTest(dataset=dataset, field=field, value=value):
                        checks = validator([{**row, field: value}], columns=fields)
                        self.assertFalse(next(c for c in checks if c.rule_id.endswith("_required_values")).passed)
                if field.endswith("_id"):
                    checks = validator([{**row, field: ""}], columns=fields)
                    self.assertTrue(has_critical_failure(checks))

    def test_nonfinite_money_cannot_pass_positive_or_bounded_checks(self) -> None:
        for dataset, fields, validator, row in self.cases[1:]:
            money_fields = ("credit_limit",) if dataset == "accounts" else ("amount", "confirmed_loss")
            for field in money_fields:
                for value in ("nan", "NaN", "inf", "Infinity", "-inf", "1e309"):
                    with self.subTest(dataset=dataset, field=field, value=value):
                        checks = validator([{**row, field: value}], columns=fields)
                        failing = {c.rule_id for c in checks if not c.passed}
                        expected = "credit_limit_positive" if field == "credit_limit" else "transaction_amount_positive" if field == "amount" else "confirmed_loss_bounded"
                        self.assertIn(expected, failing)

    def test_fraud_flag_must_be_binary(self) -> None:
        _, fields, validator, row = self.cases[2]
        for value in ("2", "-1", "true", "0.5", "", "NaN", None):
            with self.subTest(value=value):
                checks = validator([{**row, "is_fraud": value}], columns=fields)
                self.assertFalse(next(c for c in checks if c.rule_id == "transaction_fraud_flag_binary").passed)

    def test_empty_batches_are_not_successful_even_with_valid_headers(self) -> None:
        for dataset, fields, validator, _ in self.cases:
            with self.subTest(dataset=dataset):
                checks = validator([], columns=fields)
                empty_check = next(c for c in checks if c.rule_id.endswith("_batch_not_empty"))
                self.assertFalse(empty_check.passed)
                self.assertEqual(empty_check.failed_rows, 0)

    def test_header_contract_preserves_canonical_positional_mapping(self) -> None:
        for dataset, fields, validator, row in self.cases:
            for columns in (fields[:-1], tuple(reversed(fields)), (*fields, "extra"), (*fields[:-1], fields[0])):
                with self.subTest(dataset=dataset, columns=columns):
                    checks = validator([row], columns=columns)
                    self.assertFalse(next(c for c in checks if c.rule_id.endswith("_schema_valid")).passed)

    def test_email_cannot_crash_masking_with_an_empty_local_part(self) -> None:
        _, fields, validator, row = self.cases[0]
        for email in ("@example.test", "name@@example.test", "name @example.test"):
            with self.subTest(email=email):
                self.assertTrue(has_critical_failure(validator([{**row, "email": email}], columns=fields)))


class LocalEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.generated = generate_sources(
            self.root / "sources", customer_count=20, account_count=25,
            transactions_per_month=10,
        )
        self.pipeline = LocalPipeline(self.root / "governai.db")
        self.pipeline.initialize()
        self.pipeline.run_demo(self.generated.base_dir, self.generated.incident_file)
        with (self.generated.base_dir / "transactions.csv").open(newline="") as handle:
            self.candidate = next(csv.DictReader(handle))
        self.candidate["transaction_id"] = "TXN-NEW-QUALITY-TEST"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def products(self):
        with self.pipeline.connect() as connection:
            return {
                table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
                for table in (
                    "raw_transactions", "fct_card_transactions", "feature_account_behavior_30d",
                    "mart_monthly_loss_kpis", "model_loss_forecast",
                )
            }

    def test_invalid_csv_shapes_are_quarantined_without_loader_execution(self) -> None:
        variants = {
            "missing_column": (TRANSACTION_FIELDS[:-1], [self.candidate]),
            "reordered": (tuple(reversed(TRANSACTION_FIELDS)), [self.candidate]),
            "duplicate_header": ((*TRANSACTION_FIELDS[:-1], TRANSACTION_FIELDS[0]), [self.candidate]),
            "unknown_column": ((*TRANSACTION_FIELDS, "extra"), [{**self.candidate, "extra": "x"}]),
        }
        before = self.products()
        for name, (fields, rows) in variants.items():
            path = self.root / f"{name}.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            with self.subTest(name=name), patch.object(self.pipeline, "load_transactions") as loader:
                outcome = self.pipeline.ingest_transactions(path, name)
                loader.assert_not_called()
                self.assertEqual(outcome.status, "quarantined")
                self.assertEqual(outcome.accepted_rows, 0)
                self.assertIn("transaction_schema_valid", {c.rule_id for c in outcome.checks if not c.passed})
                self.assertEqual(self.products(), before)

    def test_short_surplus_and_empty_rows_produce_evidence_instead_of_exceptions(self) -> None:
        header = ",".join(TRANSACTION_FIELDS) + "\n"
        cells = [self.candidate[field] for field in TRANSACTION_FIELDS]
        variants = {
            "short": header + ",".join(cells[:-1]) + "\n",
            "surplus": header + ",".join([*cells, "surplus"]) + "\n",
            "header_only": header,
            "empty_file": "",
        }
        before = self.products()
        for name, contents in variants.items():
            path = self.root / f"{name}.csv"
            path.write_text(contents)
            with self.subTest(name=name), patch.object(self.pipeline, "load_transactions") as loader:
                outcome = self.pipeline.ingest_transactions(path, name)
                loader.assert_not_called()
                self.assertEqual(outcome.status, "quarantined")
                self.assertEqual(outcome.accepted_rows, 0)
                self.assertEqual(self.products(), before)
                with self.pipeline.connect() as connection:
                    self.assertEqual(connection.execute("SELECT outcome FROM audit_events WHERE run_id=?", (outcome.run_id,)).fetchone()[0], "blocked")

    def test_bad_values_quarantine_entire_batch_and_retries_reuse_evidence(self) -> None:
        variants = (
            {"transaction_id": " "}, {"amount": "nan"}, {"amount": "inf"},
            {"confirmed_loss": "nan"}, {"is_fraud": "2"},
            {"account_id": "ACC-MISSING"}, {"merchant_category": ""},
        )
        before = self.products()
        for index, mutation in enumerate(variants):
            path = self.root / f"invalid-{index}.csv"
            write_csv(path, TRANSACTION_FIELDS, [self.candidate, {**self.candidate, "transaction_id": f"TXN-INVALID-{index}", **mutation}])
            with self.subTest(mutation=mutation):
                first = self.pipeline.ingest_transactions(path, str(index))
                repeated = self.pipeline.ingest_transactions(path, str(index))
                self.assertEqual((first.status, first.source_rows, first.accepted_rows, first.quarantined_rows), ("quarantined", 2, 0, 2))
                self.assertEqual(repeated.run_id, first.run_id)
                self.assertEqual(self.products(), before)

    def test_failed_partial_load_retains_run_checks_manifest_and_safe_audit(self) -> None:
        path = self.root / "partial-load.csv"
        write_csv(path, TRANSACTION_FIELDS, [self.candidate])
        before = self.products()
        original_loader = self.pipeline.load_transactions

        def partial_loader(connection, rows, run_id):
            original_loader(connection, rows, run_id)
            # This secret-like message must never enter durable audit evidence.
            raise ValueError("customer00001@example.test should stay out of audit")

        with patch.object(self.pipeline, "load_transactions", side_effect=partial_loader):
            with self.assertRaises(PipelineExecutionError) as raised:
                self.pipeline.ingest_transactions(path, "partial-failure")
        run_id = raised.exception.run_id
        self.assertIsInstance(raised.exception.__cause__, ValueError)
        self.assertEqual(self.products(), before)
        with self.pipeline.connect() as connection:
            run = connection.execute("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
            self.assertEqual((run["status"], run["source_row_count"], run["accepted_row_count"], run["quarantined_row_count"]), ("failed", 1, 0, 0))
            self.assertGreaterEqual(run["ended_at"], run["started_at"])
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM source_manifests WHERE run_id=?", (run_id,)).fetchone()[0], 1)
            self.assertGreater(connection.execute("SELECT COUNT(*) FROM quality_results WHERE run_id=?", (run_id,)).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM quality_results WHERE run_id=? AND passed=0", (run_id,)).fetchone()[0], 0)
            event = connection.execute("SELECT * FROM audit_events WHERE run_id=?", (run_id,)).fetchone()
            self.assertEqual((event["action"], event["outcome"]), ("batch.failed", "failed"))
            details = json.loads(event["details_json"])
            self.assertEqual(details["error_type"], "ValueError")
            self.assertTrue(details["rollback_confirmed"])
            self.assertNotIn("customer00001", event["details_json"])
        # Failure is terminal for this identity; a repeat cannot turn green or
        # silently retry partially executed work.
        with patch.object(self.pipeline, "load_transactions") as loader:
            with self.assertRaises(PipelineExecutionError) as repeated:
                self.pipeline.ingest_transactions(path, "partial-failure")
            loader.assert_not_called()
        self.assertEqual(repeated.exception.run_id, run_id)
        self.assertTrue(repeated.exception.repeated)
        with self.pipeline.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM audit_events WHERE run_id=?", (run_id,)).fetchone()[0], 1)
        retry = self.pipeline.ingest_transactions(path, "explicit-retry")
        self.assertEqual(retry.status, "succeeded")
        self.assertNotEqual(retry.run_id, run_id)

    def test_failed_rebuild_rolls_back_raw_and_derived_changes(self) -> None:
        path = self.root / "rebuild-failure.csv"
        write_csv(path, TRANSACTION_FIELDS, [self.candidate])
        before = self.products()

        def partial_rebuild(connection):
            connection.execute("DELETE FROM mart_monthly_loss_kpis")
            raise RuntimeError("Injected rebuild failure")

        with patch.object(self.pipeline, "rebuild_products", side_effect=partial_rebuild):
            with self.assertRaises(PipelineExecutionError) as raised:
                self.pipeline.ingest_transactions(path, "rebuild-failure")
        self.assertEqual(self.products(), before)
        with self.pipeline.connect() as connection:
            self.assertEqual(connection.execute("SELECT status FROM pipeline_runs WHERE run_id=?", (raised.exception.run_id,)).fetchone()[0], "failed")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM audit_events WHERE action='batch.published' AND run_id=?", (raised.exception.run_id,)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
