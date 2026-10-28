# Portfolio release status

Original release: 2026-08-18
Current local verification: 2026-10-28

## Release-ready locally

- Deterministic evidence can be regenerated with one command.
- Python, snapshot-contract, lint, type-check, and production-build gates pass.
- October 28 verification: `npm test` passed 58 Python unit/integration tests
  and 13 frontend/hosting contracts, followed by ESLint and the TypeScript/Vite
  production build. Seven executable control procedures and the desktop/mobile
  browser workflow also passed. See [the verification record](VERIFICATION_2026-10-28.md).
- Local transaction replay protection quarantines overlapping batches, preserves
  original-identity idempotency under concurrent runs, and keeps acceptance
  counts consistent with actual inserts. The Snowflake equivalent remains work.
- The public dashboard snapshot excludes raw identifiers and account-level
  experiment assignments.
- Recruiter overview and guided proof path cover data, cloud, experiments,
  governed analytics, and model risk.
- Page metadata and a project-specific social card describe the actual project.
- Documentation includes architecture, decisions, security, deployment,
  status, walkthrough, and interview material.
- The original August release record used an owner-only Sites preview. The
  current public demonstration is
  [GovernAI on Netlify](https://governai-poojan-desai.netlify.app), observed with
  HTTP 200 and browser checks on October 19. That observation does not establish
  which Git commit was deployed.
- The August record reported passing GitHub Actions for that release. Current
  branch validation is local; no new remote CI run is claimed.

## External gates

- AWS resources and Snowflake objects remain not deployed or live verified.
- No customer experiment has been run.
- No external LLM is called.
- No model-risk or business-owner approval has occurred.
- October quality-contract, durable-failure and transaction-replay changes have
  been prepared for publication with their original local history. Confirm
  publication and remote CI from the GitHub commit and Actions run. No deployment
  is established by local validation. Interactive pipeline execution is not part
  of the existing static public demonstration.
- The cloud source-path race and cloud cross-batch replay parity remain open;
  local ingestion protections must not be described as cloud guarantees.

This file is a release record, not permission to change any external status by
editing documentation. Live states change only from captured execution evidence.
