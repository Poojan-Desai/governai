"""Manifest-based local-to-Snowflake reconciliation."""

from __future__ import annotations

from .models import BatchManifest, ReconciliationResult
from .ports import Warehouse


class Reconciler:
    def __init__(self, warehouse: Warehouse):
        self.warehouse = warehouse

    def reconcile(self, manifest: BatchManifest) -> ReconciliationResult:
        evidence = self.warehouse.batch_evidence(manifest)
        if evidence is None:
            return ReconciliationResult(
                manifest.batch_id,
                manifest.dataset,
                manifest.row_count,
                None,
                manifest.source_sha256,
                None,
                "MISSING",
                "Snowflake governance audit contains no successful load for this batch",
            )
        actual_rows = int(evidence["row_count"])
        actual_sha = str(evidence["source_sha256"])
        if actual_rows != manifest.row_count or actual_sha != manifest.source_sha256:
            return ReconciliationResult(
                manifest.batch_id,
                manifest.dataset,
                manifest.row_count,
                actual_rows,
                manifest.source_sha256,
                actual_sha,
                "MISMATCH",
                "Row count or source manifest SHA-256 differs",
            )
        return ReconciliationResult(
            manifest.batch_id,
            manifest.dataset,
            manifest.row_count,
            actual_rows,
            manifest.source_sha256,
            actual_sha,
            "MATCHED",
            "Batch ID, accepted row count, and source SHA-256 match",
        )
