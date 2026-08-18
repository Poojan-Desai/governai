# Security and privacy

All records are simulated, but GovernAI treats them as if they were sensitive.

## Implemented controls

| Risk | Control | Verification level |
| --- | --- | --- |
| Secrets in source | SDK/environment discovery; ignored `.env`; storage integration instead of AWS keys | Repository/static tests |
| Public or plaintext objects | S3 public-access block, TLS-only bucket policy, KMS default encryption and requested SSE-KMS writes | Terraform/API contract; live pending |
| Tampered overwrite | Versioning, deterministic key, stored SHA-256, conflict on different bytes | Unit tested; live pending |
| Bad/partial batch | Pre-load critical gate, file-atomic quarantine, COPY abort, transaction, fail-fast dbt | Integration tested; live pending |
| Excess warehouse access | Job-function roles, separate ingest/transform warehouses, schema/table future grants | SQL contract; live pending |
| Direct identifiers | Snowflake name/email/phone masks; curated token and masked email | SQL/dbt contract; role-session test pending |
| Financial values | Numeric masking for credit limit, amount, and confirmed loss | SQL contract; role-session test pending |
| Untraceable processing | Batch load, pipeline event, reconciliation, lineage, and policy-event tables | Adapter tested; live pending |
| PII in dashboard | Aggregate allow-list and public-snapshot pattern tests | Verified locally |
| Analytics prompt injection | Block unsafe instruction/SQL tokens before execution; fixed read-only templates only | Adversarial tests verified locally |
| Hallucinated analytics | Approved intent registry, numeric reconciliation, citations, and explicit abstention | Verified locally |
| Unsafe model promotion | Time-based evaluation, attached limitations, external approval gates, production state `BLOCKED` | Verified locally |

## Role boundaries

| Role | Intended access | Explicit exclusion |
| --- | --- | --- |
| Data Engineer | RAW read, governance evidence, ingest warehouse | Direct identifiers and financial fields remain masked |
| Analyst | CURATED and ANALYTICS read | No RAW schema usage |
| Governance Admin | Mask management and governance evidence | No RAW table SELECT |
| Restricted/PII Analyst | Analyst rights plus approved RAW read and unmask | No load/transform writes |
| Pipeline Role | S3-stage usage, RAW load, pipeline audit writes | No curated modeling ownership |
| dbt Role | RAW read and model creation in governed schemas | No pipeline audit writes or unmasked identifiers |

The policy deployment itself is recorded in `ACCESS_POLICY_EVENTS`. Snowflake's
native query/access history is the source for runtime read access; exporting it
to the GovernAI audit table is a production-hardening task and is not claimed.

## Known limitations

- Simulated data prevents real-customer exposure but does not prove regulatory
  compliance.
- S3 Object Lock is not enabled because it requires bucket-creation choices and
  retention governance beyond a portfolio demo; versioning is not legal hold.
- The checked-in dbt profile uses an environment password. Key-pair auth is
  supported by the pipeline adapter and should also be configured for dbt/CI.
- No AWS CloudTrail, Snowflake Access History ingestion, Secrets Manager,
  network policy, private connectivity, SIEM, or incident alerting is deployed.
- The Phase 4A assistant is a deterministic policy prototype, not a general LLM;
  identity-aware authorization, query budgets, and external-model evaluations
  remain production work.
- Phase 5A model evidence uses simulated aggregates and three backtest folds;
  it does not replace model-risk, fairness, stress, business, or deployment review.
