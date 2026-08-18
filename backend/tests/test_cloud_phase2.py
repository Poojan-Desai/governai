from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from governai.cloud.models import BatchManifest, LoadResult, ObjectWriteResult
from governai.cloud.orchestrator import CloudPipeline, ReconciliationMismatch
from governai.cloud.s3 import S3DataLake, S3IdempotencyConflict
from governai.cloud.snowflake import SnowflakeWarehouse
from governai.cloud.status import build_readiness
from governai.generator import generate_sources


class MemoryObjectStore:
    bucket = "unit-test-bucket"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.created = 0
        self.operations: list[str] = []

    def _put(self, zone: str, dataset: str, manifest: BatchManifest, filename: str, body: bytes) -> ObjectWriteResult:
        key = f"{zone}/{dataset}/batch_id={manifest.batch_id}/{filename}"
        digest = hashlib.sha256(body).hexdigest()
        self.operations.append(key)
        if key in self.objects:
            if hashlib.sha256(self.objects[key]).hexdigest() != digest:
                raise RuntimeError("idempotency conflict")
            return ObjectWriteResult(self.bucket, key, False, digest)
        self.objects[key] = body
        self.created += 1
        return ObjectWriteResult(self.bucket, key, True, digest)

    def put_file(self, *, zone: str, dataset: str, manifest: BatchManifest, path: Path) -> ObjectWriteResult:
        return self._put(zone, dataset, manifest, path.name, path.read_bytes())

    def put_json(self, *, zone: str, dataset: str, manifest: BatchManifest, filename: str, content: str) -> ObjectWriteResult:
        return self._put(zone, dataset, manifest, filename, content.encode())


class MemoryWarehouse:
    def __init__(self, *, corrupt_evidence: bool = False) -> None:
        self.evidence: dict[str, dict[str, object]] = {}
        self.loads: list[str] = []
        self.events: list[dict[str, object]] = []
        self.reconciliations: list[dict[str, object]] = []
        self.edges: dict[str, dict[str, str]] = {}
        self.corrupt_evidence = corrupt_evidence

    def load_validated_csv(self, *, dataset: str, s3_key: str, manifest: BatchManifest) -> LoadResult:
        self.loads.append(manifest.batch_id)
        existing = self.evidence.get(manifest.batch_id)
        if existing:
            return LoadResult(manifest.batch_id, dataset, False, int(existing["row_count"]), str(existing["source_sha256"]))
        self.evidence[manifest.batch_id] = {
            "row_count": manifest.row_count + (1 if self.corrupt_evidence and dataset == "transactions" else 0),
            "source_sha256": manifest.source_sha256,
        }
        return LoadResult(manifest.batch_id, dataset, True, manifest.row_count, manifest.source_sha256)

    def batch_evidence(self, manifest: BatchManifest):
        return self.evidence.get(manifest.batch_id)

    def record_event(self, **event) -> None:
        self.events.append(event)

    def record_reconciliation(self, *, run_id: str, result: dict[str, object]) -> None:
        self.reconciliations.append({"run_id": run_id, **result})

    def publish_lineage(self, edges) -> int:
        for edge in edges:
            self.edges[edge["edge_id"]] = dict(edge)
        return len(edges)


class RecordingDbt:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def build(self, *, select: str) -> tuple[str, ...]:
        self.calls.append(select)
        return ("dbt", "build", "--select", select, "--fail-fast")


class FailingDbt(RecordingDbt):
    def build(self, *, select: str) -> tuple[str, ...]:
        self.calls.append(select)
        raise RuntimeError("dbt data test failed")


class MissingObject(Exception):
    response = {"Error": {"Code": "404"}}


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, object]] = {}

    def head_object(self, *, Bucket: str, Key: str):
        try:
            return self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise MissingObject() from exc

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = {
            "Metadata": kwargs["Metadata"],
            "Body": kwargs["Body"],
            "ServerSideEncryption": kwargs["ServerSideEncryption"],
            "SSEKMSKeyId": kwargs["SSEKMSKeyId"],
        }


class CloudPhase2Tests(unittest.TestCase):
    def _fixture(self, root: Path):
        return generate_sources(root / "sources", seed=42, customer_count=20, account_count=25, transactions_per_month=10)

    def test_valid_pipeline_orders_zones_load_dbt_lineage_and_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = self._fixture(Path(directory))
            store, warehouse, dbt = MemoryObjectStore(), MemoryWarehouse(), RecordingDbt()
            report = CloudPipeline(object_store=store, warehouse=warehouse, dbt=dbt).run_base(source_dir=generated.base_dir)
        self.assertEqual(report.status, "SUCCEEDED")
        self.assertEqual([batch.manifest.dataset for batch in report.batches], ["customers", "accounts", "transactions"])
        self.assertEqual(len(warehouse.loads), 3)
        self.assertEqual(dbt.calls, ["+mart_monthly_loss_kpis"])
        self.assertTrue(report.dbt_executed)
        self.assertTrue(all(result.status == "MATCHED" for result in report.reconciliation))
        self.assertGreaterEqual(report.lineage_edges_published, 3)
        self.assertTrue(all(batch.raw_object.key.startswith("raw/") for batch in report.batches))
        self.assertTrue(all(batch.validated_object and batch.validated_object.key.startswith("validated/") for batch in report.batches))

    def test_incident_is_quarantined_without_warehouse_or_dbt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = self._fixture(Path(directory))
            store, warehouse, dbt = MemoryObjectStore(), MemoryWarehouse(), RecordingDbt()
            report = CloudPipeline(object_store=store, warehouse=warehouse, dbt=dbt).run_incident(
                incident_file=generated.incident_file,
                known_account_ids={f"ACC-{index:05d}" for index in range(1, 26)},
            )
        batch = report.batches[0]
        self.assertEqual(report.status, "QUARANTINED")
        self.assertEqual(len([check for check in batch.checks if not check.passed]), 4)
        self.assertIsNone(batch.validated_object)
        self.assertIsNone(batch.load)
        self.assertEqual(warehouse.loads, [])
        self.assertEqual(dbt.calls, [])
        self.assertTrue(any(key.startswith("raw/") for key in store.objects))
        self.assertTrue(any(key.startswith("quarantined/") and key.endswith("quality-evidence.json") for key in store.objects))

    def test_repeated_batch_is_idempotent_and_skips_dbt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = self._fixture(Path(directory))
            store, warehouse, dbt = MemoryObjectStore(), MemoryWarehouse(), RecordingDbt()
            pipeline = CloudPipeline(object_store=store, warehouse=warehouse, dbt=dbt)
            first = pipeline.run_base(source_dir=generated.base_dir)
            object_count = len(store.objects)
            second = pipeline.run_base(source_dir=generated.base_dir)
        self.assertTrue(first.dbt_executed)
        self.assertFalse(second.dbt_executed)
        self.assertEqual(len(store.objects), object_count)
        self.assertTrue(all(not batch.raw_object.created and not batch.validated_object.created for batch in second.batches if batch.validated_object))
        self.assertEqual(len(warehouse.evidence), 3)
        self.assertTrue(all(result.matched for result in second.reconciliation))

    def test_reconciliation_mismatch_is_surfaced_and_fails_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = self._fixture(Path(directory))
            pipeline = CloudPipeline(object_store=MemoryObjectStore(), warehouse=MemoryWarehouse(corrupt_evidence=True), dbt=RecordingDbt())
            with self.assertRaises(ReconciliationMismatch) as raised:
                pipeline.run_base(source_dir=generated.base_dir)
        report = raised.exception.report
        self.assertEqual(report.status, "RECONCILIATION_FAILED")
        self.assertEqual([result.status for result in report.reconciliation], ["MATCHED", "MATCHED", "MISMATCH"])

    def test_dbt_failure_stops_lineage_and_reconciliation_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = self._fixture(Path(directory))
            warehouse, dbt = MemoryWarehouse(), FailingDbt()
            pipeline = CloudPipeline(object_store=MemoryObjectStore(), warehouse=warehouse, dbt=dbt)
            with self.assertRaisesRegex(RuntimeError, "dbt data test failed"):
                pipeline.run_base(source_dir=generated.base_dir)
        self.assertEqual(dbt.calls, ["+mart_monthly_loss_kpis"])
        self.assertEqual(warehouse.edges, {})
        self.assertEqual(warehouse.reconciliations, [])
        self.assertEqual(warehouse.events[-1]["event_type"], "PIPELINE_FAILED")

    def test_s3_adapter_uses_kms_metadata_and_rejects_overwrite(self) -> None:
        manifest = BatchManifest("2.0", "batch-abc", "source.test", "transactions", "x.csv", "a" * 64, 1, ("id",))
        client = FakeS3Client()
        lake = S3DataLake(client=client, bucket="governai-test", kms_key_arn="arn:aws:kms:us-east-1:123:key/test")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.csv"
            path.write_text("id\n1\n", encoding="utf-8")
            first = lake.put_file(zone="raw", dataset="transactions", manifest=manifest, path=path)
            second = lake.put_file(zone="raw", dataset="transactions", manifest=manifest, path=path)
            path.write_text("id\n2\n", encoding="utf-8")
            with self.assertRaises(S3IdempotencyConflict):
                lake.put_file(zone="raw", dataset="transactions", manifest=manifest, path=path)
        stored = client.objects[("governai-test", first.key)]
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(stored["ServerSideEncryption"], "aws:kms")
        self.assertEqual(stored["Metadata"]["source-sha256"], "a" * 64)

    def test_manifest_is_deterministic_and_snowflake_paths_are_constrained(self) -> None:
        manifest = BatchManifest("2.0", "batch-abc", "source.test", "transactions", "x.csv", "b" * 64, 3, ("b", "a"))
        self.assertEqual(manifest.canonical_json(), manifest.canonical_json())
        self.assertEqual(json.loads(manifest.canonical_json())["columns"], ["b", "a"])
        self.assertEqual(SnowflakeWarehouse._stage_path("validated/transactions/batch_id=batch-abc/x.csv"), "validated/transactions/batch_id=batch-abc/x.csv")
        with self.assertRaises(ValueError):
            SnowflakeWarehouse._stage_path("validated/x.csv'; drop table raw.transactions;--")

    def test_rbac_masking_dbt_and_terraform_security_contracts(self) -> None:
        root = Path(__file__).parents[2]
        rbac = (root / "snowflake/sql/002_rbac.sql").read_text()
        masks = (root / "snowflake/sql/005_masking_policies.sql").read_text()
        terraform = (root / "infrastructure/terraform/main.tf").read_text()
        models = "\n".join(path.read_text() for path in (root / "dbt/models").rglob("*.*") if path.is_file())
        self.assertIn("GOVAI_RESTRICTED_ANALYST", rbac)
        self.assertNotIn("SCHEMA GOVERNAI.RAW TO ROLE GOVAI_ANALYST", rbac)
        self.assertIn("IS_ROLE_IN_SESSION('GOVAI_RESTRICTED_ANALYST')", masks)
        self.assertIn("SET MASKING POLICY", masks)
        self.assertIn("aws_s3_bucket_public_access_block", terraform)
        self.assertIn("aws_s3_bucket_server_side_encryption_configuration", terraform)
        self.assertIn('values   = ["false"]', terraform)
        self.assertIn("source('governai_raw', 'transactions')", models)
        self.assertIn("ref('stg_transactions')", models)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", rbac + masks + terraform + models)

    def test_readiness_is_honest_without_credentials_or_live_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True):
            status = build_readiness(Path(directory))
        self.assertEqual(status["implementation_status"], "IMPLEMENTED_LOCALLY")
        self.assertEqual(status["live_verification_status"], "NOT_RUN")
        self.assertFalse(status["credentials"]["values_exposed"])
        self.assertFalse(status["credentials"]["aws_configured"])
        self.assertFalse(status["credentials"]["snowflake_configured"])


if __name__ == "__main__":
    unittest.main()
