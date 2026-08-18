# Acceptance criteria

Status vocabulary:

- **VERIFIED** — executed evidence exists in this repository/session.
- **IMPLEMENTED** — production code/configuration exists and local contracts pass.
- **NOT RUN** — requires real AWS/Snowflake execution; no success is claimed.

## Phase 1 regression gate

| ID | Criterion | Evidence | Status |
| --- | --- | --- | --- |
| P1-01 | Same seed creates byte-identical sources | SHA-256 determinism test | VERIFIED |
| P1-02 | Valid data builds facts, features, KPIs, and baseline | Integration counts | VERIFIED |
| P1-03 | Four critical defects reject the entire file | 120 rejected, 0 accepted | VERIFIED |
| P1-04 | Rejected file cannot change downstream facts | Before/after equality | VERIFIED |
| P1-05 | Blast radius is derived from lineage | Traversal assertion | VERIFIED |
| P1-06 | UI contains aggregate evidence and no raw PII | Snapshot privacy test | VERIFIED |
| P1-07 | Frontend produces a production build | Vite build | VERIFIED |

## Phase 2 gate

| ID | Criterion | Local evidence | Live status |
| --- | --- | --- | --- |
| P2-01 | Four S3 zones and KMS-encrypted immutable writes | Terraform/static test + fake-client API assertions | NOT RUN |
| P2-02 | Deterministic manifests survive raw and validated paths | Orchestrator integration test | NOT RUN |
| P2-03 | Critical quality failure prevents warehouse/dbt calls | Recording-port integration test | NOT RUN |
| P2-04 | Snowflake RAW/GOVERNANCE load is transactional and idempotent | Connector code + repeat-run contract | NOT RUN |
| P2-05 | dbt DAG, docs, source freshness, and data tests are valid | File/security contracts | NOT RUN (`dbt build`) |
| P2-06 | Roles and masking policies express least privilege | SQL assertions | NOT RUN in role sessions |
| P2-07 | Terraform is minimal and contains encryption/public-access/TLS controls | Static contract | NOT RUN (`plan/apply`) |
| P2-08 | Reconciliation surfaces missing/mismatched count or SHA | MATCHED/MISMATCH integration tests | NOT RUN against Snowflake |
| P2-09 | Repeat input creates no duplicate objects/rows and skips dbt | End-to-end port test | NOT RUN against cloud |
| P2-10 | Dashboard distinguishes code readiness from cloud verification | Frontend JSON contract + build | NOT RUN in browser |

Phase 2 is not complete until the live column can be changed using captured
execution evidence, never by editing this table alone.
