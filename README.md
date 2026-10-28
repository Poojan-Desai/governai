# GovernAI

[![CI](https://github.com/Poojan-Desai/governai/actions/workflows/ci.yml/badge.svg)](https://github.com/Poojan-Desai/governai/actions/workflows/ci.yml)

A data governance and controls engineering portfolio built with Python, SQL,
React and TypeScript. GovernAI traces simulated banking data from source CSVs
through validation, quarantine, lineage and KPI reconciliation, then exposes
sanitized evidence in a dashboard.

[Architecture](docs/ARCHITECTURE.md) · [Control evidence](docs/CONTROL_EVIDENCE.md) ·
[Walkthrough](docs/PORTFOLIO_WALKTHROUGH.md) · [Verification](docs/VERIFICATION_2026-10-28.md)

![Control evidence dashboard](docs/images/control-evidence-desktop.png)

## Capabilities

- **Reliable ingestion:** ordered CSV contracts reject malformed, missing and
  nonfinite values; invalid files are quarantined before publication.
- **Source integrity:** the local pipeline derives rows, headers, SHA-256 and
  byte size from one captured source. SQLite writer serialization protects batch
  identity and cross-batch duplicate checks; savepoints roll back partial writes.
- **Inspectable controls:** seven executable procedures cover quarantine,
  idempotent replay, duplicate rejection, reconciliation, masking, unsafe
  assistant input and rollback. The dashboard exports the same sanitized JSON.
- **Governed analytics:** approved read-only SQL templates provide cited aggregate
  answers and abstain on unsupported questions. Seeded experiment analysis and a
  time-based model comparison expose assumptions and approval gates.
- **Cloud integration code:** S3/Snowflake adapters, dbt models, Terraform and
  RBAC/masking SQL are included with credential-free contract tests.

## Verification

Fresh local verification on **October 28, 2026** passed **58 Python tests and
13 Node tests**, ESLint, TypeScript and the production build. All **7 control
procedures** passed; their synthetic fixture reconciled **60 transactions and
508.86 in confirmed loss** across raw, curated and KPI layers. Desktop/mobile
browser checks exercised procedure selection, JSON download, overflow and focus.

Tests include real process termination before commit, concurrent batch replay,
source replacement after capture, injected rebuild failures, deliberately broken
loss reconciliation and unsafe assistant requests. See the
[verification record](docs/VERIFICATION_2026-10-28.md) for commands and scope.

## Run locally

Requirements: Python 3.11+, Node.js 22+ and npm. The local path needs no credentials.

```sh
npm ci
npm test
npm run demo
npm run controls
npm run dev
```

Open the printed loopback URL. The UI reads generated aggregate snapshots;
it does not execute Python ingestion in the browser. `npm run controls`
regenerates an isolated synthetic report and its checksum.

With the local server running, verify the browser workflow in another terminal:

```sh
npx playwright install chromium
npm run test:browser
```

Installed Chrome can be used with `PLAYWRIGHT_CHANNEL=chrome npm run test:browser`.

## Scope and limitations

All data is simulated. No live AWS, Snowflake or dbt execution, customer
experiment, external LLM call, regulatory certification or production model
approval is claimed. Model results use a small synthetic dataset.

The local source-capture and cross-batch replay protections do **not** yet have
cloud parity: the cloud orchestrator reopens source paths between validation,
hashing and upload. Immutable cloud staging and cloud replay conflict handling
remain required before production use. Cloud definitions are implementation
artifacts tested with fakes/static contracts, not a deployed platform.

Local database access is not protected by the cloud RBAC definitions. Email
masking is pseudonymization, and report checksums are not authenticated signatures.
See [security and privacy](docs/SECURITY_PRIVACY.md) and
[control boundaries](docs/CONTROL_EVIDENCE.md#security-boundary-and-remaining-work).

## Repository

| Path | Purpose |
| --- | --- |
| `backend/governai`, `backend/tests` | Pipeline, controls, analytics, cloud adapters and regression tests |
| `src`, `tests` | Dashboard, aggregate evidence and web contracts |
| `dbt`, `snowflake/sql`, `infrastructure/terraform` | Cloud models, warehouse policies and infrastructure definitions |
| `docs` | Architecture, decisions, evidence and operating instructions |
