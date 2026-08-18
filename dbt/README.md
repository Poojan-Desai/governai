# GovernAI dbt project

This graph deliberately contains only the transformations needed by the Phase 2
business path: three source-normalizing views, three governed dimensions/facts,
one explainable feature table, and one monthly KPI mart. `source()` and `ref()`
calls make dependencies machine-readable. Run `dbt build --select
+mart_monthly_loss_kpis --fail-fast` so any model or data-test failure prevents the
mart from being treated as current.

The checked-in profile contains environment-variable names, never credentials.
