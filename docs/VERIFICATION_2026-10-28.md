# GovernAI verification — October 28, 2026

Public `main` at review start was `85210b5e0eaeb97ffd794d0cd0958cfd718e199f`.
The three unpublished descendant commits through
`4118e7b16b3b5ec1d5d60aef6327b98a40a1ad55` were recovered from the October 24
local repository with their original ancestry intact. Source and regression
tests were inspected before preparing publication; this review adds documentation.

## Fresh local results

| Verification | Result |
| --- | --- |
| `npm ci` | Lockfile install succeeds; audit reports zero known npm vulnerabilities |
| `npm test` | 58 Python tests + 13 Node tests pass; ESLint, TypeScript and Vite build pass |
| Controls CLI with `.local/publish-control-evidence.json` output | 7/7 procedures pass; 60 transactions / 508.86 synthetic confirmed loss reconcile |
| `PLAYWRIGHT_CHANNEL=chrome npm run test:browser` | All seven selections, JSON/source equality, desktop/mobile layout, keyboard focus and absence of page errors pass |
| Credential-pattern scan and configuration inspection | 111 tracked files scanned; no private-key blocks, GitHub/AWS/OpenAI/Slack token patterns or embedded URL credentials found; `.env.example` contains placeholders |

The default Playwright command first failed because its downloaded Chromium
was absent. The same workflow passed using installed Chrome. Browser dimensions
were 1440×1100 and 390×844. Local execution used the checked-in lockfile; no
credentials, live cloud services or billable resources were needed.

The suite covers malformed headers/rows, nonfinite money, missing identifiers,
concurrent duplicates, replay identity, safe failure evidence, source replacement,
real crash/restart rollback and control-report failure detection. Test counts
are separate from the seven control procedures and browser assertions.

## Boundaries and open work

- The source-capture fix is in `LocalPipeline`. The cloud orchestrator still
  reads rows, hashes and uploads through separate source-path reads. This known
  race and cloud cross-batch replay parity remain open; live cloud use is not
  represented as verified.
- SQL/Terraform/dbt contracts and fake-adapter tests do not establish applied
  cloud permissions or a successful AWS/Snowflake/dbt run.
- Local SQLite file access has no identity-based authorization boundary.
  Masking is pseudonymization; checksums are not signatures.
- Synthetic experiments/model comparisons do not demonstrate customer impact
  or production model fitness. No deployment was performed by this review.

The npm advisory result is dated, registry-scoped evidence. The credential scan
is a bounded pattern check plus inspection, not a guarantee that arbitrary
secrets can never appear. Remote publication and hosted CI must be confirmed
from the eventual commit and Actions run, separately from these local results.
