# Recruiter demo script

## 90 seconds before live cloud verification

1. **Overview (0–15s):** explain deterministic simulated data and show run ID,
   freshness, KPI evidence, and the model limitation.
2. **Incident (15–35s):** show four failures, 120 quarantined, zero accepted, and
   identical warehouse before/after counts.
3. **Lineage (35–55s):** select the transaction source and explain computed blast
   radius through feature, mart, model, and dashboard.
4. **Catalog (55–65s):** show owners, SLAs, sensitivity, taxonomy, and masks.
5. **Cloud control plane (65–90s):** walk S3→Snowflake→dbt, RBAC, masking, and
   reconciliation, then point directly to “LIVE RUN NOT PERFORMED.” Say the code
   and local contracts are verified but deployment awaits account credentials.

## After a successful live gate

Replace the last sentence only when the generated page reads `VERIFIED`. Show
the three matching reconciliation records, then the quarantine run and the
repeat run that skips duplicate work. Never screenshot raw customer values,
credentials, private keys, account identifiers, or Terraform state.
