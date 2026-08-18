"""Fail-closed S3 -> Snowflake -> dbt -> reconciliation orchestration."""

from __future__ import annotations

import csv
import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from governai.catalog import EDGES
from governai.contracts import CheckResult, has_critical_failure, validate_accounts, validate_customers, validate_transactions
from governai.generator import sha256_file
from governai.pipeline import LocalPipeline

from .models import BatchManifest, BatchReport, CloudRunReport
from .ports import ObjectStore, TransformationRunner, Warehouse
from .reconcile import Reconciler


class QualityGateError(RuntimeError):
    def __init__(self, message: str, report: CloudRunReport):
        super().__init__(message)
        self.report = report


class ReconciliationMismatch(RuntimeError):
    def __init__(self, message: str, report: CloudRunReport):
        super().__init__(message)
        self.report = report


class CloudPipeline:
    DATASETS = (
        ("customers", "source.crm_customers", "customers.csv"),
        ("accounts", "source.card_accounts", "accounts.csv"),
        ("transactions", "source.card_transactions", "transactions.csv"),
    )

    def __init__(
        self,
        *,
        object_store: ObjectStore,
        warehouse: Warehouse,
        dbt: TransformationRunner,
    ):
        self.object_store = object_store
        self.warehouse = warehouse
        self.dbt = dbt

    @staticmethod
    def _rows(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            return rows, tuple(reader.fieldnames or ())

    @staticmethod
    def _manifest(
        *, dataset: str, asset_id: str, path: Path, rows: int, columns: tuple[str, ...], label: str
    ) -> BatchManifest:
        source_sha = sha256_file(path)
        return BatchManifest(
            manifest_version="2.0",
            batch_id=LocalPipeline.batch_id(asset_id, source_sha, label),
            asset_id=asset_id,
            dataset=dataset,
            source_file=path.name,
            source_sha256=source_sha,
            row_count=rows,
            columns=columns,
        )

    @staticmethod
    def _edge_dicts() -> list[dict[str, str]]:
        edges = [
            {
                "edge_id": edge_id,
                "upstream_asset_id": upstream,
                "downstream_asset_id": downstream,
                "transformation_type": transformation_type,
                "transformation_description": description,
            }
            for edge_id, upstream, downstream, transformation_type, description in EDGES
        ]
        edges.extend(
            [
                {
                    "edge_id": "cloud-e01",
                    "upstream_asset_id": "s3.validated.card_transactions",
                    "downstream_asset_id": "snowflake.raw.transactions",
                    "transformation_type": "snowflake_copy",
                    "transformation_description": "COPY an accepted immutable CSV through the governed external stage.",
                },
                {
                    "edge_id": "cloud-e02",
                    "upstream_asset_id": "snowflake.raw.transactions",
                    "downstream_asset_id": "dbt.stg_transactions",
                    "transformation_type": "dbt_source",
                    "transformation_description": "Type, normalize, and document raw transaction columns in a dbt view.",
                },
                {
                    "edge_id": "cloud-e03",
                    "upstream_asset_id": "dbt.stg_transactions",
                    "downstream_asset_id": "snowflake.analytics.mart_monthly_loss_kpis",
                    "transformation_type": "dbt_model",
                    "transformation_description": "Aggregate governed monthly loss KPIs through explicit dbt refs.",
                },
            ]
        )
        return edges

    @staticmethod
    def _checks(
        dataset: str,
        rows: Sequence[Mapping[str, str]],
        known_customers: Iterable[str],
        known_accounts: Iterable[str],
    ) -> list[CheckResult]:
        if dataset == "customers":
            return validate_customers(rows)
        if dataset == "accounts":
            return validate_accounts(rows, known_customers)
        if dataset == "transactions":
            return validate_transactions(rows, known_accounts)
        raise ValueError(f"Unsupported dataset: {dataset}")

    def run_base(self, *, source_dir: Path) -> CloudRunReport:
        run_id = f"cloud-run-{uuid.uuid4().hex[:16]}"
        report = CloudRunReport(run_id=run_id, status="RUNNING")
        customer_rows, _ = self._rows(source_dir / "customers.csv")
        account_rows, _ = self._rows(source_dir / "accounts.csv")
        known_customers = {row["customer_id"] for row in customer_rows}
        known_accounts = {row["account_id"] for row in account_rows}

        try:
            for dataset, asset_id, filename in self.DATASETS:
                path = source_dir / filename
                rows, columns = self._rows(path)
                manifest = self._manifest(
                    dataset=dataset,
                    asset_id=asset_id,
                    path=path,
                    rows=len(rows),
                    columns=columns,
                    label="base",
                )
                raw = self.object_store.put_file(
                    zone="raw", dataset=dataset, manifest=manifest, path=path
                )
                self.object_store.put_json(
                    zone="raw",
                    dataset=dataset,
                    manifest=manifest,
                    filename="manifest.json",
                    content=manifest.canonical_json(),
                )
                checks = self._checks(dataset, rows, known_customers, known_accounts)
                if has_critical_failure(checks):
                    quarantine = self.object_store.put_file(
                        zone="quarantined", dataset=dataset, manifest=manifest, path=path
                    )
                    evidence = json.dumps(
                        {
                            "manifest": asdict(manifest),
                            "policy": "FAIL_CLOSED_FILE_ATOMIC_V1",
                            "checks": [asdict(check) for check in checks],
                        },
                        indent=2,
                        sort_keys=True,
                    ) + "\n"
                    self.object_store.put_json(
                        zone="quarantined",
                        dataset=dataset,
                        manifest=manifest,
                        filename="quality-evidence.json",
                        content=evidence,
                    )
                    report.batches.append(
                        BatchReport(manifest, raw, None, quarantine, tuple(checks), None)
                    )
                    report.status = "QUARANTINED"
                    self.warehouse.record_event(
                        run_id=run_id,
                        event_type="QUALITY_GATE_BLOCKED",
                        status="QUARANTINED",
                        details={
                            "batch_id": manifest.batch_id,
                            "dataset": dataset,
                            "failed_rules": [check.rule_id for check in checks if not check.passed],
                        },
                    )
                    raise QualityGateError(
                        f"Critical quality contract blocked {dataset}", report
                    )

                validated = self.object_store.put_file(
                    zone="validated", dataset=dataset, manifest=manifest, path=path
                )
                self.object_store.put_json(
                    zone="validated",
                    dataset=dataset,
                    manifest=manifest,
                    filename="manifest.json",
                    content=manifest.canonical_json(),
                )
                load = self.warehouse.load_validated_csv(
                    dataset=dataset, s3_key=validated.key, manifest=manifest
                )
                report.batches.append(
                    BatchReport(manifest, raw, validated, None, tuple(checks), load)
                )

            if any(batch.load and batch.load.loaded for batch in report.batches):
                report.dbt_command = self.dbt.build(select="+mart_monthly_loss_kpis")
                report.dbt_executed = True
            report.lineage_edges_published = self.warehouse.publish_lineage(
                self._edge_dicts()
            )
            reconciler = Reconciler(self.warehouse)
            for batch in report.batches:
                reconciliation = reconciler.reconcile(batch.manifest)
                report.reconciliation.append(reconciliation)
                self.warehouse.record_reconciliation(
                    run_id=run_id, result=asdict(reconciliation)
                )
            if not all(result.matched for result in report.reconciliation):
                report.status = "RECONCILIATION_FAILED"
                raise ReconciliationMismatch(
                    "At least one local-to-Snowflake reconciliation check failed", report
                )
            report.status = "SUCCEEDED"
            self.warehouse.record_event(
                run_id=run_id,
                event_type="PIPELINE_COMPLETED",
                status="SUCCEEDED",
                details={
                    "batch_ids": [batch.manifest.batch_id for batch in report.batches],
                    "dbt_executed": report.dbt_executed,
                    "reconciliations": len(report.reconciliation),
                },
            )
            return report
        except (QualityGateError, ReconciliationMismatch):
            raise
        except Exception as exc:
            report.status = "FAILED"
            try:
                self.warehouse.record_event(
                    run_id=run_id,
                    event_type="PIPELINE_FAILED",
                    status="FAILED",
                    details={"error_type": type(exc).__name__, "message": str(exc)[:500]},
                )
            finally:
                raise

    def run_incident(
        self, *, incident_file: Path, known_account_ids: Iterable[str]
    ) -> CloudRunReport:
        """Run only the bad transaction batch; warehouse load and dbt are forbidden."""
        run_id = f"cloud-run-{uuid.uuid4().hex[:16]}"
        rows, columns = self._rows(incident_file)
        manifest = self._manifest(
            dataset="transactions",
            asset_id="source.card_transactions",
            path=incident_file,
            rows=len(rows),
            columns=columns,
            label="quality-incident-001",
        )
        raw = self.object_store.put_file(
            zone="raw", dataset="transactions", manifest=manifest, path=incident_file
        )
        self.object_store.put_json(
            zone="raw",
            dataset="transactions",
            manifest=manifest,
            filename="manifest.json",
            content=manifest.canonical_json(),
        )
        checks = validate_transactions(rows, known_account_ids)
        report = CloudRunReport(run_id=run_id, status="RUNNING")
        if not has_critical_failure(checks):
            raise RuntimeError("Incident fixture unexpectedly passed its quality contract")
        quarantine = self.object_store.put_file(
            zone="quarantined",
            dataset="transactions",
            manifest=manifest,
            path=incident_file,
        )
        self.object_store.put_json(
            zone="quarantined",
            dataset="transactions",
            manifest=manifest,
            filename="quality-evidence.json",
            content=json.dumps(
                {
                    "manifest": asdict(manifest),
                    "policy": "FAIL_CLOSED_FILE_ATOMIC_V1",
                    "checks": [asdict(check) for check in checks],
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
        )
        report.batches.append(
            BatchReport(manifest, raw, None, quarantine, tuple(checks), None)
        )
        report.status = "QUARANTINED"
        self.warehouse.record_event(
            run_id=run_id,
            event_type="QUALITY_GATE_BLOCKED",
            status="QUARANTINED",
            details={
                "batch_id": manifest.batch_id,
                "failed_rules": [check.rule_id for check in checks if not check.passed],
                "downstream_load_attempted": False,
            },
        )
        return report
