PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pipeline_runs (
  run_id TEXT PRIMARY KEY, pipeline_name TEXT NOT NULL, batch_id TEXT NOT NULL UNIQUE,
  asset_id TEXT NOT NULL, source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL,
  started_at TEXT NOT NULL, ended_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('running','succeeded','quarantined','failed')),
  source_row_count INTEGER NOT NULL DEFAULT 0, accepted_row_count INTEGER NOT NULL DEFAULT 0,
  quarantined_row_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS quality_results (
  quality_result_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id),
  asset_id TEXT NOT NULL, rule_id TEXT NOT NULL, description TEXT NOT NULL, severity TEXT NOT NULL,
  passed INTEGER NOT NULL CHECK(passed IN (0,1)), failed_rows INTEGER NOT NULL,
  observed_value TEXT NOT NULL, expected_value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantine_batches (
  quarantine_id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES pipeline_runs(run_id), asset_id TEXT NOT NULL,
  source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL, record_count INTEGER NOT NULL,
  critical_violation_count INTEGER NOT NULL, policy TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_manifests (
  manifest_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id), asset_id TEXT NOT NULL,
  source_path TEXT NOT NULL, sha256 TEXT NOT NULL, byte_size INTEGER NOT NULL, row_count INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS data_assets (
  asset_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, asset_type TEXT NOT NULL, layer TEXT NOT NULL,
  owner TEXT NOT NULL, sensitivity TEXT NOT NULL, freshness_sla TEXT NOT NULL,
  description TEXT NOT NULL, physical_name TEXT, status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS taxonomy_terms (
  term_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, parent_term_id TEXT REFERENCES taxonomy_terms(term_id), definition TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS data_columns (
  asset_id TEXT NOT NULL REFERENCES data_assets(asset_id), column_name TEXT NOT NULL, data_type TEXT NOT NULL,
  classification TEXT NOT NULL, taxonomy_term_id TEXT REFERENCES taxonomy_terms(term_id), masking_policy TEXT,
  description TEXT NOT NULL, PRIMARY KEY(asset_id,column_name)
);
CREATE TABLE IF NOT EXISTS lineage_edges (
  edge_id TEXT PRIMARY KEY, upstream_asset_id TEXT NOT NULL REFERENCES data_assets(asset_id),
  downstream_asset_id TEXT NOT NULL REFERENCES data_assets(asset_id), transformation_type TEXT NOT NULL,
  transformation_description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id TEXT PRIMARY KEY, event_ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
  resource_id TEXT NOT NULL, run_id TEXT REFERENCES pipeline_runs(run_id), outcome TEXT NOT NULL, details_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_customers (
  customer_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL,
  state TEXT NOT NULL, customer_since TEXT NOT NULL, segment TEXT NOT NULL,
  ingestion_run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id)
);
CREATE TABLE IF NOT EXISTS raw_accounts (
  account_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, opened_date TEXT NOT NULL, account_status TEXT NOT NULL,
  credit_limit REAL NOT NULL, ingestion_run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id)
);
CREATE TABLE IF NOT EXISTS raw_transactions (
  transaction_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, transaction_ts TEXT NOT NULL, amount REAL NOT NULL,
  merchant_category TEXT NOT NULL, channel TEXT NOT NULL, country_code TEXT NOT NULL, is_fraud INTEGER NOT NULL,
  confirmed_loss REAL NOT NULL, ingestion_run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id)
);
CREATE TABLE IF NOT EXISTS dim_customer (
  customer_token TEXT PRIMARY KEY, customer_id TEXT NOT NULL UNIQUE, masked_email TEXT NOT NULL,
  state TEXT NOT NULL, segment TEXT NOT NULL, customer_since TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_account (
  account_id TEXT PRIMARY KEY, customer_token TEXT NOT NULL REFERENCES dim_customer(customer_token), opened_date TEXT NOT NULL,
  account_status TEXT NOT NULL, credit_limit REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS fct_card_transactions (
  transaction_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES dim_account(account_id), transaction_ts TEXT NOT NULL,
  transaction_date TEXT NOT NULL, month TEXT NOT NULL, amount REAL NOT NULL, merchant_category TEXT NOT NULL,
  channel TEXT NOT NULL, is_cross_border INTEGER NOT NULL, is_fraud INTEGER NOT NULL, confirmed_loss REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feature_account_behavior_30d (
  account_id TEXT NOT NULL, as_of_date TEXT NOT NULL, transaction_count_30d INTEGER NOT NULL,
  average_amount_30d REAL NOT NULL, cross_border_rate_30d REAL NOT NULL, confirmed_loss_30d REAL NOT NULL,
  PRIMARY KEY(account_id,as_of_date)
);
CREATE TABLE IF NOT EXISTS mart_monthly_loss_kpis (
  month TEXT PRIMARY KEY, transaction_count INTEGER NOT NULL, transaction_value REAL NOT NULL,
  confirmed_loss REAL NOT NULL, loss_rate_bps REAL NOT NULL, affected_transactions INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS model_loss_forecast (
  forecast_month TEXT NOT NULL, model_version TEXT NOT NULL, method TEXT NOT NULL, predicted_loss REAL NOT NULL,
  slope REAL NOT NULL, intercept REAL NOT NULL, training_points INTEGER NOT NULL, trained_at TEXT NOT NULL,
  PRIMARY KEY(forecast_month,model_version)
);
