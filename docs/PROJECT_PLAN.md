# Incremental project plan

| Phase | Scope | Exit evidence | Status |
| --- | --- | --- | --- |
| 0 — Design | Architecture, model, controls, acceptance criteria | Explicit decisions and non-goals | Complete |
| 1 — Trusted foundation | Local pipeline, contracts, quarantine, catalog, lineage, baseline, UI, CI | Full local tests and build | Complete + verified |
| 2 — Cloud warehouse | S3/KMS/IAM, Snowflake layers/RBAC/masking, dbt, orchestration, reconciliation, Terraform, UI | Live golden batch + incident + repeat run, all reconciled | Implemented locally; live gate pending |
| 3 — Experimentation | Stable assignment, KPI definitions, CIs, significance, impact, ROI | Seeded calculations match independent references | Planned; not started |
| 4 — Governed analytics assistant | Semantic metrics, SQL validation, citations, limitations, injection defenses | Adversarial evals and numeric reconciliation | Planned; not started |
| 5 — Responsible ML | Challenger, feature contracts, model card, drift monitoring, approvals | Time-based evaluation and rollback | Planned; not started |
| 6 — Portfolio release | Hosted demo, observability, screenshots/video, threat model, interview drills | Clean clone and deployment evidence | Planned |

Phase 2 intentionally uses a Python entry point instead of adding Step Functions,
Glue, Lambda, or containers before a deployed scheduling need exists. A future
hosted runner can invoke the same command without changing quality semantics.
