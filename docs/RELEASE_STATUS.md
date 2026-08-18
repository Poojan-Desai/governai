# Portfolio release status

Date: 2026-08-18

## Release-ready locally

- Deterministic evidence can be regenerated with one command.
- Python, snapshot-contract, lint, type-check, and production-build gates pass.
- The public dashboard snapshot excludes raw identifiers and account-level
  experiment assignments.
- Recruiter overview and guided proof path cover data, cloud, experiments,
  governed analytics, and model risk.
- Page metadata and a project-specific social card describe the actual project.
- Documentation includes architecture, decisions, security, deployment,
  status, walkthrough, and interview material.
- The release is deployed at
  `https://governai-poojan-desai.mannered.chatgpt.site` with owner-only access.
- GitHub Actions passed for the release branch and pull request.

## External gates

- AWS resources and Snowflake objects remain not deployed or live verified.
- No customer experiment has been run.
- No external LLM is called.
- No model-risk or business-owner approval has occurred.
- Public access is not enabled; changing site access requires an explicit owner
  decision.

This file is a release record, not permission to change any external status by
editing documentation. Live states change only from captured execution evidence.
