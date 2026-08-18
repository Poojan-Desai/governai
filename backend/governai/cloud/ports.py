"""Narrow ports keep orchestration testable without pretending test doubles are cloud."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol, Sequence

from .models import BatchManifest, LoadResult, ObjectWriteResult


class ObjectStore(Protocol):
    bucket: str

    def put_file(
        self,
        *,
        zone: str,
        dataset: str,
        manifest: BatchManifest,
        path: Path,
    ) -> ObjectWriteResult: ...

    def put_json(
        self,
        *,
        zone: str,
        dataset: str,
        manifest: BatchManifest,
        filename: str,
        content: str,
    ) -> ObjectWriteResult: ...


class Warehouse(Protocol):
    def load_validated_csv(
        self, *, dataset: str, s3_key: str, manifest: BatchManifest
    ) -> LoadResult: ...

    def batch_evidence(self, manifest: BatchManifest) -> Mapping[str, object] | None: ...

    def record_event(
        self, *, run_id: str, event_type: str, status: str, details: Mapping[str, object]
    ) -> None: ...

    def record_reconciliation(
        self, *, run_id: str, result: Mapping[str, object]
    ) -> None: ...

    def publish_lineage(self, edges: Sequence[Mapping[str, str]]) -> int: ...


class TransformationRunner(Protocol):
    def build(self, *, select: str) -> tuple[str, ...]: ...
