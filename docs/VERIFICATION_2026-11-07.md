# Portfolio verification — November 7, 2026

Base: `c5ba9a80b7821e1268ce0446ecf4edaf3f6806ab` (public `main`).
Local review branch: `codex/portfolio-audit-2026-11-07`.
No cloud deployment, production data or credentials were used.

## Correctness finding and repair

The cloud orchestrator previously reopened the original source path for CSV
parsing, hashing, raw upload and validated/quarantine upload. A replacement after
parsing could therefore pass validation using the old rows while uploading new,
unvalidated bytes. A baseline local reproduction returned `SUCCEEDED`, with a
manifest count of four customer rows but an uploaded replacement CSV containing
one row and the headers `replacement,bytes`. This was a provenance defect, not a
measured production incident.

The orchestrator now reads each file once into a byte capture. Rows, columns,
SHA-256, deterministic batch ID and every data-zone upload derive from the same
captured payload. The new object-store port accepts captured CSV bytes. The S3
adapter additionally rejects a manifest/content hash mismatch before any client
call. Base and incident paths both use the capture.

Five new regression test methods cover base-source replacement/removal,
incident-source replacement/removal, mutation during upload, rejection of a
mismatched capture before any S3 call, and exact CRLF-byte preservation with
idempotent replay at the adapter boundary. Parameterized cases are not counted
as separate test methods. Test doubles do not establish actual AWS behavior.

## Fresh execution

- Baseline Python discovery: **61 passing tests**.
- Modified `npm test`: **66 Python tests**, **13 Node tests**, ESLint,
  TypeScript and the Vite production build passed.
- A fresh synthetic demo in an isolated evidence directory accepted **240
  customers, 320 accounts and 3,600 transactions**, and quarantined the entire
  **120-row** deliberately corrupted incident before publication.
- All **7** isolated control procedures passed. Raw, curated and analytics
  layers each reconciled **60 transactions and 508.86 in synthetic confirmed
  loss**, with zero orphan facts.
- Existing browser checks passed using installed Chrome at desktop 1440×1100
  and mobile 390×844: seven control selections, JSON download equality, catalog
  filter/detail consistency, empty-result behavior, mobile overflow/table
  scrolling, keyboard button focus and no uncaught page errors.

Commands: `PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v`,
`npm ci`, `npm test`, and
`BASE_URL=http://127.0.0.1:5179 PLAYWRIGHT_CHANNEL=chrome npm run test:browser`.
The demo was invoked through `governai.cli.run_demo` in a separate evidence
root, and controls through `write_control_evidence`; committed snapshots were
not refreshed merely to change timestamps or run IDs.

## Boundaries and remaining work

This repairs the source-path consistency defect in the cloud orchestration
code. It does not establish a live cloud deployment, cloud cross-batch duplicate
protection, concurrent S3-writer conflict safety, or a transaction across all
cloud datasets and services. S3's existing head-then-put behavior still needs a
conditional-write review for competing writers. Captures are memory-resident;
a production path needs explicit input-size limits or bounded immutable staging.
No external source signature is validated. The original source can still change
before or during the initial read, but the captured bytes, parsed rows and upload
remain internally consistent.

The new `put_csv` port must be implemented by custom object-store adapters.
The existing `S3DataLake.put_file` convenience method is retained for
compatibility, while cloud orchestration uses only the captured-byte method.

Synthetic model comparisons and experiment results are existing demonstrations,
not gains caused by this repair. No real business savings, regulatory assurance,
Workday integration, general-purpose LLM, or production model approval is claimed.

A fresh npm audit returned **10 moderate development/lint findings, zero high or
critical**, and a separate `npm audit --omit=dev --json` returned **zero
production findings**. The full audit exits nonzero while these known tooling
findings remain. No forced major override/downgrade was applied. This is a
point-in-time dependency check, not a general security certification.
