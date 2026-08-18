"""Metadata registry and deterministic lineage traversal."""

from __future__ import annotations

import sqlite3
from collections import deque

ASSETS = (
 ("source.crm_customers","CRM customer extract","dataset","source","Customer Data","restricted","24 hours","Synthetic customer profile source containing direct identifiers.",None),
 ("source.card_accounts","Card account extract","dataset","source","Card Data","confidential","24 hours","Synthetic card-account master source.",None),
 ("source.card_transactions","Card transaction extract","dataset","source","Payments Data","confidential","2 hours","Synthetic posted card transactions and confirmed loss outcomes.",None),
 ("validated.customer_profiles","Validated customer profiles","dataset","validated","Customer Data","restricted","24 hours","Contract-approved customer profile records.","raw_customers"),
 ("validated.card_accounts","Validated card accounts","dataset","validated","Card Data","confidential","24 hours","Contract-approved card-account records.","raw_accounts"),
 ("validated.card_transactions","Validated card transactions","dataset","validated","Payments Data","confidential","2 hours","Contract-approved transaction records.","raw_transactions"),
 ("curated.dim_customer","Customer dimension","table","curated","Customer Analytics","confidential","24 hours","Tokenized customer dimension with masked email.","dim_customer"),
 ("curated.dim_account","Account dimension","table","curated","Card Analytics","confidential","24 hours","Conformed account dimension joined to customer tokens.","dim_account"),
 ("curated.fct_card_transactions","Card transaction fact","table","curated","Payments Analytics","confidential","2 hours","Accepted card transactions at transaction grain.","fct_card_transactions"),
 ("feature.account_behavior_30d","30-day account behavior","feature_set","product","Applied Analytics","confidential","24 hours","Transparent rolling account aggregates used by analytical models.","feature_account_behavior_30d"),
 ("mart.monthly_loss_kpis","Monthly loss KPI mart","mart","product","Risk Strategy","internal","24 hours","Monthly transaction value, confirmed loss, rate, and affected count.","mart_monthly_loss_kpis"),
 ("model.loss_forecast_v1","Monthly loss forecast v1","model","model","Risk Strategy","internal","24 hours","Transparent OLS baseline trained on the monthly KPI mart.","model_loss_forecast"),
 ("dashboard.risk_operations","Risk operations dashboard","dashboard","consumption","Risk Operations","internal","24 hours","Governed operational view of pipeline trust and loss trends.",None),
)
EDGES = (
 ("e01","source.crm_customers","validated.customer_profiles","quality_gate","Validate IDs, unique keys, ISO dates, and reserved synthetic email domain."),
 ("e02","source.card_accounts","validated.card_accounts","quality_gate","Validate account keys, customer referential integrity, and positive limits."),
 ("e03","source.card_transactions","validated.card_transactions","quality_gate","Validate transaction keys, positive amounts, account references, timestamps, and bounded losses."),
 ("e04","validated.customer_profiles","curated.dim_customer","sql_transform","Tokenize customer ID and mask email before analytical use."),
 ("e05","validated.card_accounts","curated.dim_account","sql_transform","Join accounts to tokenized customers and conform account attributes."),
 ("e06","curated.dim_account","curated.fct_card_transactions","sql_transform","Enforce conformed-account join and derive calendar and cross-border fields."),
 ("e07","validated.card_transactions","curated.fct_card_transactions","sql_transform","Publish approved transactions at one-row-per-transaction grain."),
 ("e08","curated.fct_card_transactions","feature.account_behavior_30d","sql_aggregate","Aggregate 30-day count, average amount, cross-border rate, and confirmed loss by account."),
 ("e09","curated.fct_card_transactions","mart.monthly_loss_kpis","sql_aggregate","Aggregate monthly value, confirmed loss, rate, and affected transaction count."),
 ("e10","mart.monthly_loss_kpis","model.loss_forecast_v1","model_training","Fit a versioned ordinary-least-squares baseline to monthly confirmed loss."),
 ("e11","feature.account_behavior_30d","model.loss_forecast_v1","model_context","Register governed contextual features for later challenger analysis."),
 ("e12","mart.monthly_loss_kpis","dashboard.risk_operations","dashboard_query","Render governed monthly KPI aggregates."),
 ("e13","model.loss_forecast_v1","dashboard.risk_operations","dashboard_query","Render forecast value, method, training count, and limitations."),
)
TAXONOMY = (
 ("banking","Banking data",None,"Root business taxonomy for simulated banking assets."),
 ("customer","Customer","banking","Customer identity, segment, and relationship attributes."),
 ("account","Card account","banking","Card account identity, status, and credit attributes."),
 ("payment","Card payment","banking","Posted card-payment event attributes."),
 ("loss","Confirmed loss","payment","Confirmed simulated financial loss outcome."),
)
COLUMNS = (
 ("source.crm_customers","customer_id","TEXT","INTERNAL_IDENTIFIER","customer","tokenize_sha256","Synthetic customer business key."),
 ("source.crm_customers","full_name","TEXT","DIRECT_IDENTIFIER","customer","restricted_raw_only","Synthetic full name."),
 ("source.crm_customers","email","TEXT","DIRECT_IDENTIFIER","customer","mask_email","Synthetic reserved-domain email."),
 ("source.crm_customers","phone","TEXT","DIRECT_IDENTIFIER","customer","restricted_raw_only","Synthetic 555 phone number."),
 ("source.card_accounts","account_id","TEXT","INTERNAL_IDENTIFIER","account","role_scoped","Synthetic account business key."),
 ("source.card_accounts","credit_limit","REAL","FINANCIAL","account","aggregate_only","Synthetic account credit limit."),
 ("source.card_transactions","transaction_id","TEXT","INTERNAL_IDENTIFIER","payment","role_scoped","Synthetic transaction business key."),
 ("source.card_transactions","amount","REAL","FINANCIAL","payment","aggregate_only","Synthetic posted amount."),
 ("source.card_transactions","confirmed_loss","REAL","SENSITIVE_DERIVED","loss","aggregate_only","Synthetic confirmed loss outcome."),
 ("curated.dim_customer","customer_token","TEXT","PSEUDONYMOUS_IDENTIFIER","customer","already_tokenized","Stable local customer token."),
 ("curated.dim_customer","masked_email","TEXT","MASKED_IDENTIFIER","customer","already_masked","Masked synthetic email."),
 ("mart.monthly_loss_kpis","confirmed_loss","REAL","SENSITIVE_DERIVED","loss","aggregate_only","Monthly aggregate confirmed loss."),
)


def bootstrap_catalog(connection: sqlite3.Connection) -> None:
    connection.executemany("INSERT OR REPLACE INTO data_assets(asset_id,display_name,asset_type,layer,owner,sensitivity,freshness_sla,description,physical_name) VALUES(?,?,?,?,?,?,?,?,?)", ASSETS)
    connection.executemany("INSERT OR REPLACE INTO taxonomy_terms VALUES(?,?,?,?)", TAXONOMY)
    connection.executemany("INSERT OR REPLACE INTO data_columns(asset_id,column_name,data_type,classification,taxonomy_term_id,masking_policy,description) VALUES(?,?,?,?,?,?,?)", COLUMNS)
    connection.executemany("INSERT OR REPLACE INTO lineage_edges VALUES(?,?,?,?,?)", EDGES)


def downstream_assets(connection: sqlite3.Connection, source_asset_id: str) -> list[str]:
    adjacency: dict[str, list[str]] = {}
    for upstream, downstream in connection.execute("SELECT upstream_asset_id,downstream_asset_id FROM lineage_edges ORDER BY edge_id"):
        adjacency.setdefault(upstream, []).append(downstream)
    found, seen, queue = [], {source_asset_id}, deque([source_asset_id])
    while queue:
        for downstream in adjacency.get(queue.popleft(), []):
            if downstream not in seen:
                seen.add(downstream); found.append(downstream); queue.append(downstream)
    return found
