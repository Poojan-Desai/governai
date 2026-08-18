# Interview guide

## 30-second answer

“GovernAI is a simulated banking data platform that makes analytical trust
visible. Phase 1 proves deterministic Python/SQL ingestion, fail-closed data
quality, metadata, lineage, privacy, audit, KPIs, and a transparent baseline.
Phase 2 adds real S3 and Snowflake adapters, a small dbt DAG, least-privilege
roles/masks, Terraform, and manifest reconciliation. Phase 3A adds deterministic
experiment assignment, a predeclared KPI, independently tested inference, and
transparent ROI assumptions. Phase 4A adds cited, policy-bounded analytical
answers, and Phase 5A adds time-aware model comparison, drift, and approval
gates. I verified the local contracts and frontend build; cloud execution,
customer experimentation, external LLM use, and production model approval are
not claimed.”

## Explain Phase 3A in plain English

1. Governed synthetic accounts are assigned to control or treatment using a
   stable SHA-256 bucket, so reruns produce the same assignment.
2. Outcomes use a separate deterministic stream with declared probabilities;
   they are simulation inputs, not observed customer behavior.
3. The primary KPI, direction, alpha, confidence interval, significance test,
   and sample-ratio check are versioned before analysis.
4. Independent tests recompute arm counts, lift, confidence limits, p-value,
   impact, and ROI rather than trusting a dashboard rendering.
5. The positive seeded result can only advance to a governed live-pilot review;
   it cannot authorize a production rollout.

## Explain Phase 4A in plain English

1. A question first passes an input policy that blocks unsafe instructions.
2. Supported questions map to fixed, reviewed aggregate SQL; user text is never
   turned into SQL.
3. The answer cites its semantic metric, governed asset, record scope, and field.
4. Unknown questions abstain instead of producing a likely-sounding response.
5. No external LLM is called; this phase proves the governance boundary first.

## Explain Phase 5A in plain English

1. A previous-month baseline and OLS challenger use the same expanding time
   folds, avoiding random-split leakage.
2. MAE and RMSE are recomputed from published fold predictions in tests.
3. Aggregate feature windows are compared with standardized mean difference.
4. Intended use, prohibited use, ownership, limitations, and thresholds stay
   attached to the result.
5. Better research performance cannot override missing model-risk and business
   approvals; production remains blocked.

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

You can explain and show the locally verified data foundation, Phase 2 adapter
code, tests, dbt DAG, SQL RBAC/masks, Terraform, seeded experiment, governed
assistant controls, research model backtest, drift, and dashboard honesty state.
You cannot say “deployed on AWS,” “loaded Snowflake,” “dbt passed in Snowflake,”
“live customer lift,” “LLM-powered,” or “production model approved” until the
corresponding external evidence exists.

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
  model lineage and a governance workflow, not production performance. Three
  backtest folds are explicitly insufficient.
- **Why no LLM in the assistant?** The policy, semantic, authorization, citation,
  and abstention boundary should be deterministic and testable before adding a
  probabilistic model. A future model cannot bypass that boundary.

Recommended walkthrough: `generator.py` → `pipeline.py` → `catalog.py` →
`experiment.py` → `analytics_assistant.py` → `model_governance.py` → cloud
orchestrator/dbt/Terraform → tests → dashboard.
