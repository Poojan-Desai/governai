# Technology decisions

## One S3 bucket with governed prefixes

`raw/`, `validated/`, `quarantined/`, and `curated/` are prefixes in one private,
versioned, KMS-encrypted bucket. Separate buckets can offer stronger account- or
policy-level isolation, but one portfolio bucket makes encryption, lifecycle,
cost, and IAM understandable. Snowflake receives read access only to
`validated/`; it cannot read quarantine or raw objects.

## Python orchestration before a managed scheduler

The explicit command makes control flow testable and reproducible from a laptop
or CI runner. It stops on quality, COPY, dbt, or reconciliation failure. Adding
Step Functions/Glue without deploying or operating them would create diagram
complexity instead of evidence. A managed scheduler is a later operational
choice, not a Phase 2 resume checkbox.

## Storage integration instead of AWS keys

Snowflake uses an external storage integration and AWS role trust. AWS access
keys never appear in SQL, Terraform, or source. The two-pass trust handshake
binds the role to Snowflake's generated IAM principal and external ID.

## RAW loading in Python; transformations in dbt

Python owns file validation, COPY/MERGE, batch transactions, and audit evidence.
dbt owns dependency-aware SQL from normalized staging views through curated
models and the KPI mart. This boundary keeps procedural orchestration out of SQL
models and business transformations out of Python.

## Minimal dbt DAG

Three staging views match three actual sources. Curated models exist only where
they remove direct PII, create reusable facts/dimensions, or produce the
requested feature set. The KPI mart references staging directly because an
extra intermediate aggregate would not improve reuse or governance.

## Job-function RBAC and dynamic masks

Analysts see CURATED/ANALYTICS but not RAW. Restricted analysts inherit normal
analytics rights and receive explicit RAW access plus mask exceptions. Pipeline
and dbt roles get separate warehouses and write boundaries. Governance admins
manage masks and inspect evidence without receiving raw SELECT.

## Manifest reconciliation instead of a weak total-count check

The control compares batch ID, per-dataset accepted rows, and source SHA-256.
Global row totals could match even if the wrong file was loaded; the three-part
comparison binds Snowflake evidence to the exact local source.

## Terraform only for resources used now

Terraform defines S3, KMS, bucket controls, lifecycle, and IAM policies/role.
Snowflake SQL stays explicit because it is easier for a beginner to review in
privilege order and the Snowflake Terraform provider would add state/ownership
complexity before repeat deployment is proven.

## Transparent local baseline remains

The Phase 1 ordinary-least-squares loss forecast is retained as explainable model
lineage. Six simulated observations are insufficient for a production forecast;
the dashboard states that limitation. Phase 2 does not add a fraud classifier.
