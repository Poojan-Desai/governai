"""Amazon S3 data-lake adapter. This module performs real boto3 API calls."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .models import BatchManifest, ObjectWriteResult

ZONES = frozenset({"raw", "validated", "quarantined", "curated"})


class S3ConfigurationError(RuntimeError):
    pass


class S3IdempotencyConflict(RuntimeError):
    pass


class S3DataLake:
    """Write immutable, KMS-encrypted objects into governed S3 prefixes."""

    def __init__(self, *, client: object, bucket: str, kms_key_arn: str):
        if not bucket or not kms_key_arn:
            raise S3ConfigurationError("S3 bucket and KMS key ARN are required")
        self.client = client
        self.bucket = bucket
        self.kms_key_arn = kms_key_arn

    @classmethod
    def from_environment(cls) -> "S3DataLake":
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:
            raise S3ConfigurationError(
                "Install the 'cloud' extra to use AWS: pip install -e '.[cloud]'"
            ) from exc
        bucket = os.getenv("GOVERNAI_S3_BUCKET", "")
        kms_key_arn = os.getenv("GOVERNAI_KMS_KEY_ARN", "")
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if not region:
            raise S3ConfigurationError("AWS_REGION or AWS_DEFAULT_REGION is required")
        return cls(
            client=boto3.client("s3", region_name=region),
            bucket=bucket,
            kms_key_arn=kms_key_arn,
        )

    @staticmethod
    def _key(*, zone: str, dataset: str, batch_id: str, filename: str) -> str:
        if zone not in ZONES:
            raise ValueError(f"Unknown data-lake zone: {zone}")
        safe_dataset = dataset.replace("_", "-")
        return f"{zone}/{safe_dataset}/batch_id={batch_id}/{filename}"

    def _put_bytes(
        self,
        *,
        zone: str,
        dataset: str,
        manifest: BatchManifest,
        filename: str,
        body: bytes,
    ) -> ObjectWriteResult:
        body_sha = hashlib.sha256(body).hexdigest()
        key = self._key(
            zone=zone, dataset=dataset, batch_id=manifest.batch_id, filename=filename
        )
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)  # type: ignore[attr-defined]
        except Exception as exc:  # botocore is optional at import time
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if str(error_code) not in {"404", "NoSuchKey", "NotFound"}:
                raise
        else:
            metadata = {str(k).lower(): str(v) for k, v in response.get("Metadata", {}).items()}
            if metadata.get("content-sha256") != body_sha:
                raise S3IdempotencyConflict(
                    f"Existing object {key} has a different SHA-256; refusing overwrite"
                )
            return ObjectWriteResult(self.bucket, key, False, body_sha)

        self.client.put_object(  # type: ignore[attr-defined]
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=self.kms_key_arn,
            ContentType="application/json" if filename.endswith(".json") else "text/csv",
            Metadata={
                "content-sha256": body_sha,
                "source-sha256": manifest.source_sha256,
                "batch-id": manifest.batch_id,
                "asset-id": manifest.asset_id,
                "zone": zone,
                "simulated-data": "true",
            },
        )
        return ObjectWriteResult(self.bucket, key, True, body_sha)

    def put_file(
        self, *, zone: str, dataset: str, manifest: BatchManifest, path: Path
    ) -> ObjectWriteResult:
        return self._put_bytes(
            zone=zone,
            dataset=dataset,
            manifest=manifest,
            filename=path.name,
            body=path.read_bytes(),
        )

    def put_json(
        self,
        *,
        zone: str,
        dataset: str,
        manifest: BatchManifest,
        filename: str,
        content: str,
    ) -> ObjectWriteResult:
        return self._put_bytes(
            zone=zone,
            dataset=dataset,
            manifest=manifest,
            filename=filename,
            body=content.encode("utf-8"),
        )
