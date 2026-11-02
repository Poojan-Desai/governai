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

## Subsequent release review

The follow-up review found that Python's permissive ISO parser accepted basic and
week dates and non-UTC offsets, while derived products use the validated UTC text
prefix for calendar keys. The shared transaction contract now quarantines these
representations before local or cloud load. Canonical UTC generated records are
unchanged. Regression coverage includes accepted/rejected representations and
both local and cloud quarantine behavior.

Cloud operational failures now persist safe exception metadata rather than raw
SDK/dbt messages in audit and batch-load records. The originating exception still
reaches the authorized caller; this does not provide cross-batch cloud rollback.

A fresh dependency audit reported zero production findings and 12 moderate
build/lint findings propagated from `minimatch` 10.2.6. The reviewed advisory
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249)
requires 11.0.1. The current upstream lint dependencies request major version 10;
a forced major override or suggested tooling downgrade was not applied. The
static browser bundle does not execute this lint dependency. Builds should use
trusted repository inputs until upstream tooling adopts the fix. An audit is a
point-in-time dependency check, not a guarantee of security.

The catalog now resolves details from the filtered results, clears details when
no asset matches, and names its search control for assistive technology. The
model-governance grid now allows its child panels to shrink on narrow screens;
the comparison table scrolls inside its panel. Browser regression checks cover
catalog selection/empty results and mobile table navigation alongside the seven
control selectors, evidence download, keyboard focus and uncaught errors.

Final local release checks: 61 Python tests, 13 Node tests, ESLint, TypeScript,
production build, regenerated seven-control report, clean dependency installation,
and redacted Git-history secret scan passed. The dependency risk above remains.
