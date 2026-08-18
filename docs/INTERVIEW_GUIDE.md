# Interview guide

## 30-second answer

“GovernAI is a simulated banking data platform that makes analytical trust
visible. Phase 1 proves deterministic Python/SQL ingestion, fail-closed data
quality, metadata, lineage, privacy, audit, KPIs, and a transparent baseline.
Phase 2 adds real S3 and Snowflake adapters, a small dbt DAG, least-privilege
roles/masks, Terraform, and manifest reconciliation. I verified all local
contracts and the frontend build; the live AWS/Snowflake gate is still pending,
so I do not describe it as deployed.”

## Explain the Phase 2 flow in plain English

1. **Generate:** a fixed seed makes the same safe banking records every time.
2. **Manifest:** each file receives a row count, column list, SHA-256 fingerprint,
   and deterministic batch ID.
3. **S3 raw:** preserve exactly what arrived before making a quality decision.
4. **Validate:** critical rules check identifiers, dates, amounts, parent keys,
   and loss bounds.
5. **Route:** passing files go to `validated/`; failures and rule evidence go to
   `quarantined/`. A failure never calls Snowflake or dbt.
6. **Snowflake:** COPY into a temporary table, verify count, MERGE by business
   key, and commit batch evidence together.
7. **dbt:** normalize sources and build only reusable governed models/marts; refs
   create dependency lineage and tests stop on bad outputs.
8. **Reconcile:** compare the exact batch ID, rows, and source hash recorded by
   Snowflake with the local manifest.

## Decisions and trade-offs

### Why S3 zones?

Zones make data state explicit. Raw answers “what arrived?”, validated answers
“what passed?”, quarantine answers “what was blocked and why?”, and curated is a
controlled export boundary. One bucket with prefixes is easier to explain and
cheaper here; multiple buckets are appropriate when separate accounts/policies
are required.

### Why store both batch ID and SHA-256?

The hash proves byte identity. The batch ID combines asset, hash, and purpose so
retries target the same logical work. Row count provides a separate completeness
check. Any one alone is weaker.

### Why COPY into a temporary table before MERGE?

It creates a validation boundary: parsing errors or row-count differences occur
before the governed RAW table changes. The transaction commits RAW changes and
successful audit state together.

### Why dbt?

dbt turns SQL files into a dependency graph with documentation and executable
data tests. Python still orchestrates files and external systems; dbt owns
warehouse transformations. That division keeps each tool focused.

### Why not dozens of dbt models?

Every model adds ownership, runtime, tests, and failure modes. GovernAI creates a
model only to normalize a real source, protect/reuse a governed entity, create a
requested feature, or publish a business mart.

### How does least privilege work?

Analysts never receive RAW usage. Restricted analysts get a deliberate exception
and mask policies reveal values only when that role is active. Pipeline and dbt
roles use separate warehouses and write scopes. Governance admins can manage
masks and inspect evidence without reading RAW rows.

The pipeline role has `CREATE TABLE` only in RAW because Snowflake uses that
schema privilege for session-temporary tables as well; the loader needs a
temporary COPY boundary before MERGE. This is a documented least-privilege
trade-off, not an accidental account-wide DDL grant.

### What does Terraform prove?

The desired AWS state is reviewable and repeatable: one bucket, one KMS key,
public/TLS/versioning/lifecycle controls, and two narrow IAM policies/roles. It
does not prove those resources exist until `plan/apply` and AWS inspection pass.

### Why Python orchestration instead of Step Functions?

The command is already testable from local/CI and no managed runner was deployed.
Adding services only for architecture optics would create unverified complexity.
The same command can later be invoked by a scheduler.

### What can you claim today?

You can explain and show the locally verified Phase 1 platform, Phase 2 adapter
code, tests, dbt DAG, SQL RBAC/masks, Terraform, and dashboard honesty state. You
cannot say “deployed on AWS,” “loaded Snowflake,” “dbt passed in Snowflake,” or
“masking verified” until the live steps succeed.

## Likely follow-ups

- **Could a valid row be delayed by one bad row?** Yes. File-atomic rejection
  favors correctness. A future domain policy could accept bounded row-level
  errors only with explicit thresholds and denominator reconciliation.
- **Does a Snowflake primary key enforce uniqueness?** No; the declarations are
  informational. MERGE logic plus dbt unique tests enforce the contract.
- **What if dbt fails after RAW loads?** RAW remains accepted evidence, but marts
  are not marked current and the pipeline fails. Fix the model/test and rerun;
  deterministic loads are reused.
- **What if S3 already has the key with different bytes?** The adapter raises an
  idempotency conflict rather than overwrite history.
- **Is the OLS model production-ready?** No. Six synthetic months demonstrate
  model lineage and explainability, not forecasting performance.

Recommended walkthrough: `generator.py` → `cloud/orchestrator.py` → `s3.py` →
`snowflake.py` → `dbt/models` → Terraform → Phase 2 tests → cloud dashboard.
