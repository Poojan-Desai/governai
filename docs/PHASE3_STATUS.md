# Phase 3 status record

Date: 2026-08-17

## Phase 3A implemented and locally verified

- Stable account-level assignment using deterministic SHA-256 bucketing.
- Separate assignment and simulated-outcome streams.
- Predeclared primary KPI, direction, alpha, confidence interval, significance
  test, and sample-ratio-mismatch threshold.
- Aggregate arm counts and rates with no account-level assignments in the
  dashboard snapshot.
- Independent reference tests for seeded assignment, confidence limits,
  p-value, impact, and ROI.
- Impact bounded to the observed treatment sample.
- Explicit value/cost assumptions and an `ADVANCE_TO_LIVE_PILOT` decision gate.
- Experiment Lab dashboard with design, inference, economics, and limitations.

## Not implemented or claimed

- No real customer eligibility, assignment, exposure, or outcome data.
- No production randomization or event-logging service.
- No pre-experiment power analysis or minimum detectable effect approval.
- No guardrail metrics, sequential testing policy, or multiple-testing control.
- No privacy, legal, product, or risk approval for a live pilot.
- No real incremental enrollments, annualized benefit, or ROI.

Phase 3 is started, not complete. The current exit evidence proves calculation
and governance mechanics on a seeded simulation. A later Phase 3B must define
and execute a governed live-pilot protocol before any business effect can be
described as observed.
