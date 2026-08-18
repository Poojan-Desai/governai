# Responsible ML and model governance

Phase 5A demonstrates a research model-governance workflow on six months of
simulated aggregate loss data. It does not approve or deploy a production model.

## Model card

| Field | Value |
| --- | --- |
| Model | `monthly-loss-forecast-challenger-v1` |
| Task | One-month-ahead confirmed-loss forecasting |
| Target | Monthly aggregate `confirmed_loss` |
| Feature contract | Ordered month index only |
| Intended use | Research comparison and governance demonstration |
| Prohibited use | Production forecasts, capital decisions, customer actions, automated approvals |

## Time-based evaluation

The evaluation uses three expanding-window, one-step-ahead folds. A
previous-month baseline is compared with an ordinary-least-squares trend
challenger. On the canonical seeded dataset:

| Candidate | MAE | RMSE |
| --- | ---: | ---: |
| Previous-month baseline | $152.09 | $177.98 |
| OLS trend challenger | $137.48 | $157.76 |

The challenger shows a 9.61% MAE improvement and is labeled the research
champion. Three folds are far too few for production selection, so the decision
is `RESEARCH_CHAMPION_NOT_PRODUCTION_APPROVED`.

## Drift monitoring

The monitor compares the first three months with the last three months for
transaction amount, cross-border rate, and fraud rate. It uses absolute
standardized mean difference (SMD):

- below 0.10: `STABLE`
- 0.10 to below 0.20: `WATCH`
- 0.20 or above: `ALERT`

Thresholds and both window definitions are published with the evidence. These
are demonstration thresholds, not validated banking-risk tolerances.

## Promotion gate

Data-contract and time-backtest checks are locally verified. Model-risk review
and business-owner approval are `NOT_RUN`; production deployment is `BLOCKED`.
The dashboard never converts a better research metric into an implied shipping
decision.

Production work includes more history and folds, stress and stability testing,
fairness analysis where relevant, independent validation, monitoring ownership,
rollback criteria, approvals, and deployment evidence.
