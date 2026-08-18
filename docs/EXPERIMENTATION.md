# Phase 3A experimentation contract

Phase 3A validates an experimentation workflow on deterministic simulated
accounts. It does **not** report a real customer experiment or production lift.

## Predeclared design

| Field | Definition |
| --- | --- |
| Experiment | `card-alert-enrollment-v1` |
| Hypothesis | A simplified alert-enrollment experience increases seven-day enrollment completion without changing eligibility. |
| Randomization unit | One governed `account_id` |
| Allocation | 50% treatment / 50% control target |
| Assignment | SHA-256 of experiment ID, assignment stream, and account ID |
| Primary KPI | Seven-day alert enrollment completion rate |
| Numerator | Assigned eligible accounts completing enrollment within seven days |
| Denominator | All assigned eligible accounts |
| Direction | Increase |
| Significance threshold | Two-sided alpha = 0.05 |
| Confidence interval | 95% unpooled Wald interval for the difference in proportions |
| Significance test | Two-sided pooled two-proportion z-test |
| SRM threshold | Two-sided normal approximation, flag below 0.01 |

Assignment and outcome generation use separate named SHA-256 streams. Sorting
the assignment units before analysis makes the evidence independent of input
order. The snapshot exposes only aggregate arm counts and an assignment digest;
it never publishes account-level assignments.

## Seeded local evidence

The default 320-account simulation produces 172 control and 148 treatment
assignments. The control arm has 47 completions and the treatment arm has 61.
That yields a 13.89 percentage-point observed difference, a 95% confidence
interval of approximately 3.54 to 24.25 points, and a two-sided p-value of
approximately 0.0088. Independent test calculations verify those values.

The result advances only to `ADVANCE_TO_LIVE_PILOT`. It is not approval to ship
the treatment. A live pilot still requires power analysis, eligibility and
exposure logging, guardrail metrics, privacy review, monitoring, and an agreed
stopping rule.

## Impact and ROI assumptions

Impact is bounded to the treatment sample; the code does not scale a result to
an unstated customer population.

- Incremental enrollments = observed absolute lift × treatment assignments.
- Gross annualized value = incremental enrollments × $24 assumed annual value.
- Delivery cost = treatment assignments × $0.75 assumed treatment cost.
- ROI = (gross annualized value − delivery cost) / delivery cost.

The $24 and $0.75 values are portfolio-demo assumptions. They are displayed in
the dashboard, versioned in code, and must not be used for an investment or
production decision.

## Reproducibility and governance

`backend/governai/experiment.py` owns the predeclared contract and calculation.
`backend/tests/test_experiment.py` recomputes assignment counts, confidence
limits, p-value, impact, and ROI from independent formulas. The dashboard reads
only the aggregate experiment object written into the evidence snapshot.

After `npm run demo`, `npm run experiment:status` prints the same aggregate-only
evidence directly from the local governed account population. It never emits
account identifiers or assignment rows.

Known limitations are part of that object so a presentation cannot separate a
positive simulated result from its evidence boundary.
