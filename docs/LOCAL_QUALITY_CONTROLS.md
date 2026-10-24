# Local quality and processing failures

This October 2026 increment hardens the existing Python pipeline. It does not
add a hosted execution API or make AWS/Snowflake live-verification claims.

## Shared input contract

Customer, account and transaction CSVs must contain the canonical fields from
`backend/governai/generator.py` in the declared order. Missing, unknown,
duplicated or reordered headers fail before loading. The order is required
because the Snowflake COPY adapter uses reviewed positional expressions.
Short rows, surplus cells, non-string/missing values and blank required fields
produce critical check results. An empty file or header-only file is rejected;
its source row count remains zero rather than inventing a failing row.

Identifiers must be present and unique within the batch. Parent references must
exist. Money must be finite; account limits and transaction amounts must be
positive, and confirmed loss must be between zero and amount. Fraud flags must
be exactly `0` or `1`. Dates, timestamps and reserved synthetic email addresses
are checked before downstream conversions or masking.

The local and cloud orchestrators use the same validators, with file headers
passed explicitly. Recording-port cloud tests verify that an invalid dataset
has no validated object or warehouse load and that dbt is not invoked. Earlier
valid datasets may already have been loaded: this is file-atomic, not a
three-dataset distributed transaction. No live cloud service is called by tests.

## Outcome and retry policy

| Outcome | Data writes | Retained local evidence | Same batch rerun |
| --- | --- | --- | --- |
| `succeeded` | Raw and derived changes committed | Run, manifest, checks, published audit event | Original successful outcome |
| `quarantined` | No loader call | Run, manifest, checks, quarantine and blocked audit event | Original quarantined outcome |
| `failed` | Load/rebuild changes rolled back | Run with start/end, manifest, checks and `batch.failed` audit event | `PipelineExecutionError` with original run ID |

The batch identity is derived from asset, source hash and label. A failed batch
is terminal under that identity. An explicit retry with a new label creates a
new run; it does not rewrite the failed record. `PipelineExecutionError.run_id`
links both the initial exception and subsequent failed reruns to evidence.

A SQLite savepoint encloses loading, product rebuilding and the success event.
An ordinary processing exception rolls that savepoint back. The outer metadata
transaction marks the run failed, records the exception class and a fixed safe
rollback message, then commits before raising the run-linked error. Raw error
messages are excluded because they may contain source values. Failed processing
is not reported as quarantine: its accepted and quarantined counts are both zero.

## Cross-batch transaction replay control — October 24

Transaction IDs represent immutable events in the local adapter. Replaying the
original asset/hash/label identity returns its stored outcome. A different batch
identity that includes any already-published ID fails the critical
`transaction_id_not_previously_loaded` rule and quarantines the entire file.
Both identical records and changed payloads are blocked; a new label cannot
override this policy. Customer and account dimension upserts retain their
existing update semantics.

This closes a silent accounting defect: the previous `ON CONFLICT DO NOTHING`
loader could report every input row accepted even when existing IDs were skipped.
The loader now uses strict inserts. If the quality gate ever misses a conflict,
the unique constraint raises a processing error and the existing savepoint
rolls back all writes, retaining a failed run instead of a false success.

`BEGIN IMMEDIATE` serializes the identity lookup, database-backed replay check
and publication on one SQLite connection. Concurrent attempts for the same batch
receive the same stored outcome; distinct overlapping batches produce one
success and one quarantine. Identifier lookups use the transaction primary key
and chunks of at most 900 parameters. Checks and audit events report counts and
rule IDs without including the conflicting transaction values.

Eight regression tests cover exact/conflicting replays, mixed-file isolation,
original-identity reruns, label changes, acceptance-versus-insertion counts,
an enforced 999-parameter SQLite limit, concurrent reruns/overlaps and a missed
quality-gate failure injection. They reproduced the accounting and concurrent
identity failures before the fix. These controls apply to the local SQLite path;
the Snowflake adapter's cross-batch conflict policy still needs separate work.

## Inspect and verify

Run the local regression suite and frontend checks with:

```bash
npm ci
npm test
```

The focused behavioral suite is:

```bash
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -p 'test_contract_hardening.py' -v
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -p 'test_cloud_phase2.py' -v
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -p 'test_transaction_replays.py' -v
```

Run, manifest, quality and audit evidence remains in the local SQLite database
selected by `LocalPipeline`; `audit_events.details_json` stores the structured
failure explanation. The public snapshot still excludes row-level source data
and raw failure messages. No new browser run-history inspector is claimed.

## Remaining boundaries

- Failures before registration, such as unreadable source files or an unavailable
  database, are raised without a durable run record. Process termination and
  operating-system crashes are not covered by this ordinary-exception path.
- The static web interface shows stored evidence. Scenario selection, a bounded
  local execution bridge, run-history inspection and record previews remain work.
- The existing snapshot reconstructs its incident before/after display from the
  current warehouse count; persisting measurements at incident time is still work.
- The Snowflake adapter does not yet implement the local cross-batch transaction
  replay rule. File hashes are not captured with CSV parsing in one immutable
  read, so concurrent source-file mutation remains outside the tested contract.
- A writer that cannot acquire SQLite's lock within its connection timeout raises
  before registration. Durable retry scheduling and crash recovery remain work.
- Local audit evidence is mutable SQLite state, not an immutable compliance log.
  AWS/Snowflake/RBAC/dbt execution and production controls remain unverified live.
