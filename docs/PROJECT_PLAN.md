# Incremental project plan

| Phase | Scope | Exit evidence | Status |
| --- | --- | --- | --- |
| 0 — Design | Architecture, model, controls, acceptance criteria | Explicit decisions and non-goals | Complete |
| 1 — Trusted foundation | Local pipeline, contracts, quarantine, catalog, lineage, baseline, UI, CI | Full local tests and build | Complete + verified |
| 2 — Cloud warehouse | S3/KMS/IAM, Snowflake layers/RBAC/masking, dbt, orchestration, reconciliation, Terraform, UI | Live golden batch + incident + repeat run, all reconciled | Implemented locally; live gate pending |
| 3 — Experimentation | Stable assignment, KPI definitions, CIs, significance, impact, ROI | Seeded calculations match independent references | Phase 3A implemented + locally verified; live pilot not run |
| 4 — Governed analytics assistant | Semantic metrics, fixed SQL, citations, limitations, injection defenses | Adversarial evals and numeric reconciliation | Phase 4A implemented + locally verified; no external LLM |
| 5 — Responsible ML | Challenger, feature contract, model card, drift monitoring, approvals | Time-based evaluation and hard production block | Phase 5A implemented + locally verified; external approvals not run |
| 6 — Portfolio release | Recruiter overview, guided demo, responsive UI, metadata, release evidence | Clean build, CI, privacy/security scan, hosted release record | Private hosted release complete; public access not enabled |

Phase 2 intentionally uses a Python entry point instead of adding Step Functions,
Glue, Lambda, or containers before a deployed scheduling need exists. A future
hosted runner can invoke the same command without changing quality semantics.
