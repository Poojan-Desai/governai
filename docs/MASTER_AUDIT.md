# Local engineering audit — 2026-10-24

Inspected Python ingestion, contracts, catalog, snapshot exporter, SQL schema, cloud ports, React views and CI before editing. Baseline: 50 Python tests pass. Source checkout preserves earlier unpublished work at the recorded local baseline; remote main remains separate.

| Area | Observed evidence and assessment | Priority / verification |
| --- | --- | --- |
| Strengths | Strict CSV contracts; file-atomic quarantine; indexed cross-batch transaction replay check under BEGIN IMMEDIATE; savepoint rollback; deterministic synthetic source; lineage and masking; read-only aggregate assistant | Preserve with full regression suite |
| Critical correctness | CSV rows read first, then file reopened for hash and stat. A changed/replaced source can yield a manifest for bytes different from published rows. | P1: one captured byte sequence owns parsing/hash/size. Mutation/failure regression tests. High value, small change, low interface risk |
| Missing control evidence | Individual controls have tests and snapshots, but no reproducible sanitized control-testing report with objective, procedure, result, references and exceptions. | P2: isolated executable control scenario report, static UI and JSON export. High assurance/interview value, medium effort/risk |
| Security | Raw SQLite contains identifiers, catalog describes roles, no local database authorization boundary. Snapshot strips row-level identities. | Report actual control scope; do not assert RBAC for a process that can read the database |
| Data validity | Synthetic six-month data; aggregate forecast is lineage demo with only three backtest folds. Floating-point SQL totals rounded at marts. | No production ML/financial claims. Reconcile counts and rounded loss sums in report |
| Cloud | AWS/Snowflake/dbt ports and Terraform exist; no credentials or executed cloud evidence in this run | Mock/contract evidence only; no automatic cloud execution |
| Product | Existing distinct incident/catalog/lineage/model views; no control evidence view/download | Add a report-backed evidence screen with local/synthetic disclosure |
| Quality / CI | stdlib unittest, Node tests, lint/build; CI contents read only. Mutable action version tags and broad JS ranges remain debt | Run actual checks; no claim CI executed remotely |
| Employer relevance | Source provenance, fault isolation, reconciliation, reproducibility and controls testing demonstrate data engineering and technology assurance | Two concrete engineering stories in implementation report |

Ranked work: capture source bytes (correctness), executable control evidence (auditability), report UI/demo (reviewability). Deferred: full local access-control server, historical quality trend store, externally anchored audit log, production incremental materialization, live cloud verification and broad design overhaul.
