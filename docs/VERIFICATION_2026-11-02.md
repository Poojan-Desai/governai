# Verification — November 2, 2026

The public repository and recovered local history both started at
`5eb60e94ef45db36eda30036a138a2e8746788c0`. No later local source changes were
missing from GitHub. The existing Netlify dashboard still used an older manual
deployment, so this release adds explicit static-host configuration and a safe
commit/version record, and refreshes the generated synthetic evidence.

## Fresh local execution

- `npm run demo` regenerated the local aggregate pipeline snapshot from
  deterministic simulated records. No bank data or cloud account was used.
- `npm run controls` executed all seven isolated control procedures and refreshed
  their sanitized report/checksum. Reconciliation again matched 60 transactions
  and 508.86 in synthetic confirmed loss across raw, curated and analytics layers.
- `npm test` passed 58 Python tests and 13 Node tests, followed by ESLint,
  TypeScript and the Vite production build.
- The production build emits browser assets into `dist/client`, including
  `version.json` with only the project name, source commit and build timestamp.
  Runtime databases, source CSVs, credentials, tests and the Sites worker are
  outside the Netlify publish directory.

The seven control procedures, browser assertions and automated test counts are
separate evidence categories; repeated runs are not added together. The
[October source review](VERIFICATION_2026-10-28.md) records the original safeguards.

## Deployment boundary

Use the [existing-site deployment guide](STATIC_DEPLOYMENT.md). Confirm the live
version metadata and asset hashes against the production build, independently of
GitHub commit/CI status. The site uses manual deployments and is not connected
to automatic GitHub publishing. No site/account permissions need to change.

This remains a static, synthetic dashboard. It does not execute live ingestion
in the browser or establish AWS/Snowflake/dbt deployment. The cloud source-path
race and cloud cross-batch replay parity remain open. Local masking is not
anonymization or local-file access control, and checksums are not signatures.
