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

## Phase 3A experimentation gate

| ID | Criterion | Evidence | Status |
| --- | --- | --- | --- |
| P3-01 | Assignment is stable for an account and independent of input order | Assignment digest + repeat test | VERIFIED LOCALLY |
| P3-02 | Primary KPI, direction, alpha, interval, and test are predeclared | Versioned experiment contract | VERIFIED LOCALLY |
| P3-03 | Seeded arm counts and rates match fixed reference values | Independent count assertions | VERIFIED LOCALLY |
| P3-04 | Confidence limits and p-value match independent formulas | Reference calculation test | VERIFIED LOCALLY |
| P3-05 | Impact is bounded to the treatment sample and ROI exposes assumptions | Independent impact/ROI test | VERIFIED LOCALLY |
| P3-06 | Aggregate evidence contains no account-level assignments | Snapshot privacy assertion | VERIFIED LOCALLY |
| P3-07 | Dashboard labels the result as simulated and blocks a production claim | Frontend contract + browser verification | VERIFIED LOCALLY |

No Phase 3A status authorizes a production rollout. A governed live pilot,
guardrails, approvals, power analysis, and exposure/outcome evidence remain not
run.

## Phase 4A governed analytics gate

| ID | Criterion | Evidence | Status |
| --- | --- | --- | --- |
| P4-01 | Supported questions resolve only through versioned intents | Intent registry tests | VERIFIED LOCALLY |
| P4-02 | Every executed query is fixed, read-only, and aggregate | Template allow-list assertions | VERIFIED LOCALLY |
| P4-03 | Answer values reconcile to governed tables | Independent database queries | VERIFIED LOCALLY |
| P4-04 | Successful answers include metric and asset citations | Snapshot contract | VERIFIED LOCALLY |
| P4-05 | Unsafe instructions are blocked before execution | Adversarial no-mutation test | VERIFIED LOCALLY |
| P4-06 | Unsupported questions abstain | Explicit abstention test | VERIFIED LOCALLY |
| P4-07 | UI states that no external LLM is called | Frontend contract + build | VERIFIED LOCALLY |

Phase 4A proves the policy and semantic boundary. Identity-aware authorization,
external-model evaluation, cost controls, and production audit retention are not
implemented or claimed.

## Phase 5A responsible-ML gate

| ID | Criterion | Evidence | Status |
| --- | --- | --- | --- |
| P5-01 | Baseline and challenger use identical time-ordered folds | Fold assertions | VERIFIED LOCALLY |
| P5-02 | MAE/RMSE reconcile from published fold predictions | Independent calculation test | VERIFIED LOCALLY |
| P5-03 | Drift statistics match an independent SMD formula | Reference calculation test | VERIFIED LOCALLY |
| P5-04 | Model card includes intended and prohibited use | Snapshot contract | VERIFIED LOCALLY |
| P5-05 | Limitations remain attached to performance evidence | Public snapshot test | VERIFIED LOCALLY |
| P5-06 | Missing model-risk/business approvals block production | Hard gate assertion | VERIFIED LOCALLY |
| P5-07 | UI labels all results research-only | Frontend contract + build | VERIFIED LOCALLY |

Phase 5A does not approve a model. More history, stress/fairness analysis,
independent validation, monitoring ownership, and rollback evidence remain not
run.

## Phase 6 portfolio-release gate

| ID | Criterion | Evidence | Status |
| --- | --- | --- | --- |
| P6-01 | Default view explains problem, build, proof, and honest status | Recruiter overview | VERIFIED LOCALLY |
| P6-02 | Guided walkthrough links every evidence chapter | Interactive navigation | VERIFIED LOCALLY |
| P6-03 | Public evidence excludes raw identifiers and secrets | Privacy/security scans | VERIFIED LOCALLY |
| P6-04 | Keyboard focus, skip link, labels, and reduced-motion rules exist | Accessibility contracts | VERIFIED LOCALLY |
| P6-05 | Production build and CI workflow pass | Local build + GitHub Actions | VERIFIED |
| P6-06 | Hosted URL serves the release | Sites deployment record | PRIVATE DEPLOYED; PUBLIC ACCESS NOT ENABLED |
