"""Serializable evidence models shared by cloud adapters and tests."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from governai.contracts import CheckResult


@dataclass(frozen=True)
class BatchManifest:
    manifest_version: str
    batch_id: str
    asset_id: str
    dataset: str
    source_file: str
    source_sha256: str
    row_count: int
    columns: tuple[str, ...]

    def canonical_json(self) -> str:
        """Stable JSON: intentionally excludes timestamps and machine-specific paths."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")) + "\n"


@dataclass(frozen=True)
class ObjectWriteResult:
    bucket: str
    key: str
    created: bool
    sha256: str


@dataclass(frozen=True)
class LoadResult:
    batch_id: str
    dataset: str
    loaded: bool
    row_count: int
    source_sha256: str


@dataclass(frozen=True)
class ReconciliationResult:
    batch_id: str
    dataset: str
    expected_rows: int
    actual_rows: int | None
    expected_sha256: str
    actual_sha256: str | None
    status: str
    details: str

    @property
    def matched(self) -> bool:
        return self.status == "MATCHED"


@dataclass(frozen=True)
class BatchReport:
    manifest: BatchManifest
    raw_object: ObjectWriteResult
    validated_object: ObjectWriteResult | None
    quarantine_object: ObjectWriteResult | None
    checks: tuple[CheckResult, ...]
    load: LoadResult | None


@dataclass
class CloudRunReport:
    run_id: str
    status: str
    batches: list[BatchReport] = field(default_factory=list)
    dbt_executed: bool = False
    dbt_command: tuple[str, ...] = ()
    reconciliation: list[ReconciliationResult] = field(default_factory=list)
    lineage_edges_published: int = 0
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
