# Phase 2 status record

Date: 2026-08-10

## Implemented and locally verified

- Real boto3 S3 adapter with four zones, SSE-KMS parameters, SHA metadata,
  deterministic immutable keys, and overwrite conflict handling.
- Real Snowflake connector boundary with staged COPY, count gate, transactional
  MERGE, idempotent batch audit, event/reconciliation/lineage writes.
- Fail-closed Python orchestration and incident path.
- Manifest reconciliation with `MATCHED`, `MISSING`, and `MISMATCH` outcomes.
- dbt DAG, source freshness, documentation, generic tests, and two singular
  business tests.
- Snowflake layer/RBAC/masking/storage-integration/verification SQL.
- Minimal S3/KMS/IAM Terraform definitions.
- Cloud dashboard honesty state and frontend contract.
- Phase 1 regression tests preserved.

## Not verified live

- Terraform format/validate/plan/apply.
- AWS bucket, KMS, IAM policy, storage role, object uploads, or IAM behavior.
- Snowflake database, schemas, warehouses, roles, tables, stage, policies, COPY,
  MERGE, query history, or role-session masking behavior.
- dbt parse/build/test/docs against Snowflake.
- Live row-count/SHA reconciliation, live quarantine, or live retry.
- Browser interaction or hosted deployment.

The RAW loader uses upsert semantics and does not delete business keys missing
from a later file. A future full-snapshot source needs explicit soft-delete or
snapshot-diff semantics. Concurrent same-batch runners are also outside the
current single-runner assumption because standard Snowflake primary keys are not
enforced.

This document must be updated from captured output after the steps in
`DEPLOYMENT.md`; planned or locally mocked behavior is never sufficient.
