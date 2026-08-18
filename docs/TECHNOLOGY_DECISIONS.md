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

## Deterministic assignment before a live experimentation service

Phase 3A uses SHA-256 bucketing over experiment ID, stream name, and account ID.
It is order-independent, dependency-free, and easy to reproduce in tests. A
production randomization service would additionally need eligibility snapshots,
exposure logging, concurrency controls, and operational monitoring; none are
claimed by the local simulation.

## Simple proportion inference with visible assumptions

The first experiment uses a binary completion KPI, an unpooled 95% Wald interval,
and a pooled two-sided two-proportion z-test. These methods are intentionally
compact and independently reproducible. A live protocol must revisit power,
small-sample behavior, covariate adjustment, sequential looks, guardrails, and
multiple testing before launch.

## Fixed semantic queries before probabilistic SQL generation

Phase 4A routes a small supported question set to code-owned aggregate SELECT
templates. This makes authorization, abstention, citations, and numeric
reconciliation testable before a model is introduced. A future LLM may classify
intent or explain results, but it must not bypass the same metric registry,
read-only validator, identity policy, and audit boundary.

## Time-based evaluation before model complexity

The responsible-ML chapter compares a previous-month baseline with the existing
OLS trend using identical expanding-window folds. Random train/test splitting
would leak future information into a forecasting task. The model remains simple
because six synthetic months cannot justify a complex learner; the value is the
evaluation and approval workflow, not algorithm novelty.

## Standardized mean difference for transparent drift

Aggregate SMD is dependency-free, directional, and comparable across numeric
and binary features. Published watch/alert thresholds make status explainable.
It is not a complete production monitor: real tolerances require risk validation,
seasonality analysis, outcome drift, alert ownership, and rollback policy.
