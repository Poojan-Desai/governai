# JPMorganChase Data & AI capability map

Reference: the official [Data & AI opportunities page](https://www.jpmorganchase.com/careers/explore-opportunities/programs/data-analytics-opportunities),
reviewed 2026-08-10. The mapping emphasizes demonstrated engineering judgment;
it is not a keyword checklist.

| Program-relevant capability | GovernAI evidence | Honest status |
| --- | --- | --- |
| Python | Deterministic generator, contracts, orchestration, cloud ports, reconciliation | Implemented + locally tested |
| SQL and data modeling | SQLite foundation; Snowflake RAW/control DDL; dbt dimensions, fact, features, KPI mart | Local SQL verified; Snowflake execution not run |
| Data pipelines | Stable manifests, fail-closed gates, transactional loader, fail-fast dbt, audit events | Local orchestration contracts verified; cloud run pending |
| Data quality | Named rules, quarantine evidence, contamination prevention, mismatch gate | Implemented + locally tested |
| Metadata and lineage | Stable asset IDs, stored directed edges, dbt refs/exposure, blast radius | Phase 1 verified; cloud publication pending |
| Governance and privacy | Taxonomy, classification, job-function roles, dynamic mask definitions, audit layer | Local/static verified; Snowflake roles pending |
| AWS and IaC | Private/versioned/KMS S3 design, lifecycle, IAM policies, external-role trust | Terraform authored/tested statically; no resources created |
| Snowflake and dbt | Layered warehouse, COPY/MERGE, tests/docs/freshness, small dependency DAG | Implemented; not executed against account |
| KPI communication | Evidence-backed monthly loss dashboard and cloud status controls | Implemented + build/contract tested |
| ML judgment | Explainable OLS lineage baseline with displayed limitations | Implemented + locally tested |
| Experimentation | Control/treatment CIs, significance, impact, ROI | Phase 3 planned; not implemented |
| Responsible LLM analytics | Governed NL-to-SQL, citations, limitations | Later phase planned; not implemented |

Databricks is not included just because it appears in job descriptions.
Snowflake plus dbt serves the current batch-analytics need; Spark would be added
only for a real scale/streaming reason.
