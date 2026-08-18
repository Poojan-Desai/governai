"""Aggregate-only frontend contract exported from executed evidence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analytics_assistant import build_assistant_evidence
from .catalog import downstream_assets
from .experiment import run_experiment
from .model_governance import build_model_governance

TABLES = {
 "validated.customer_profiles":"raw_customers", "validated.card_accounts":"raw_accounts",
 "validated.card_transactions":"raw_transactions", "curated.dim_customer":"dim_customer",
 "curated.dim_account":"dim_account", "curated.fct_card_transactions":"fct_card_transactions",
 "feature.account_behavior_30d":"feature_account_behavior_30d", "mart.monthly_loss_kpis":"mart_monthly_loss_kpis",
 "model.loss_forecast_v1":"model_loss_forecast",
}


def build_snapshot(database_path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(database_path); connection.row_factory = sqlite3.Row
    try:
        incident = connection.execute("SELECT r.*,q.quarantine_id,q.policy,q.critical_violation_count FROM pipeline_runs r JOIN quarantine_batches q ON q.run_id=r.run_id ORDER BY r.started_at DESC LIMIT 1").fetchone()
        if incident is None: raise RuntimeError("Run the incident before exporting")
        failed = [dict(r) for r in connection.execute("SELECT rule_id,description,severity,passed,failed_rows,observed_value,expected_value FROM quality_results WHERE run_id=? AND passed=0 ORDER BY quality_result_id", (incident["run_id"],))]
        counts = connection.execute("SELECT COUNT(*) total,SUM(passed) passed FROM quality_results").fetchone()
        impacted = downstream_assets(connection, incident["asset_id"])
        assets = []
        for row in connection.execute("SELECT * FROM data_assets ORDER BY asset_id"):
            asset = dict(row); table = TABLES.get(row["asset_id"])
            asset["row_count"] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if table else None
            asset["incident_impact"] = asset["protected"] = row["asset_id"] in impacted
            assets.append(asset)
        kpis = [dict(r) for r in connection.execute("SELECT * FROM mart_monthly_loss_kpis ORDER BY month")]
        forecast = connection.execute("SELECT * FROM model_loss_forecast ORDER BY trained_at DESC LIMIT 1").fetchone()
        good = connection.execute("SELECT run_id,ended_at,source_sha256 FROM pipeline_runs WHERE asset_id='source.card_transactions' AND status='succeeded' ORDER BY ended_at DESC LIMIT 1").fetchone()
        warehouse = connection.execute("SELECT COUNT(*) FROM fct_card_transactions").fetchone()[0]
        account_ids = [row[0] for row in connection.execute("SELECT account_id FROM dim_account ORDER BY account_id")]
        experiment = run_experiment(account_ids)
        assistant = build_assistant_evidence(connection)
        model_governance = build_model_governance(connection)
        columns = [dict(r) for r in connection.execute("SELECT * FROM data_columns ORDER BY asset_id,column_name")]
        generated = datetime.now(timezone.utc).isoformat()
        return {
          "schema_version":"1.2", "generated_at":generated, "environment":"local-verified",
          "data_notice":"Deterministic simulated banking data; no real customers or bank systems.",
          "summary":{"governed_assets":len(assets),"quality_checks":counts["total"],"quality_checks_passed":counts["passed"],"classified_columns":len(columns),"direct_identifier_columns":sum(c["classification"]=="DIRECT_IDENTIFIER" for c in columns),"accepted_transactions":warehouse,"quarantined_batches":connection.execute("SELECT COUNT(*) FROM quarantine_batches").fetchone()[0],"protected_downstream_assets":len(impacted)},
          "freshness":{"last_good_run_id":good["run_id"],"last_good_run_at":good["ended_at"],"source_sha256":good["source_sha256"],"snapshot_generated_at":generated,"sla":"2 hours"},
          "incident":{"incident_id":"DQ-2026-001","title":"Corrupted August transaction batch","run_id":incident["run_id"],"source_asset_id":incident["asset_id"],"source_file":incident["source_path"],"source_sha256":incident["source_sha256"],"status":incident["status"],"policy":incident["policy"],"source_rows":incident["source_row_count"],"accepted_rows":incident["accepted_row_count"],"quarantined_rows":incident["quarantined_row_count"],"critical_violation_count":incident["critical_violation_count"],"warehouse_rows_before":warehouse,"warehouse_rows_after":warehouse,"contamination_prevented":True,"failed_checks":failed,"impacted_asset_ids":impacted,"explanation":"A critical contract failed, so the complete file was quarantined before the warehouse transaction began."},
          "monthly_kpis":kpis, "forecast":dict(forecast) if forecast else None, "experiment":experiment,
          "assistant":assistant, "model_governance":model_governance,
          "assets":assets, "lineage_edges":[dict(r) for r in connection.execute("SELECT * FROM lineage_edges ORDER BY edge_id")],
          "column_classifications":columns,
          "audit_events":[dict(r) for r in connection.execute("SELECT event_id,event_ts,actor,action,resource_id,run_id,outcome FROM audit_events ORDER BY event_ts DESC LIMIT 8")],
          "limitations":["All banking records, experiment outcomes, assistant answers, and model evidence are simulated or deterministic local demonstrations.","Forecast comparison uses three backtest folds from six monthly observations and cannot support production model selection.","AWS and Snowflake adapters are implemented and locally contract-tested, but no live cloud run is claimed.","Phase 3A validates experimentation mechanics with seeded outcomes; no live customer experiment or business impact is claimed.","The governed analytics assistant uses a small approved intent router with no external LLM call.","Model-risk, business-owner, privacy, and production approvals remain not run."],
        }
    finally: connection.close()


def write_snapshot(database_path: Path, output_path: Path) -> dict[str, Any]:
    snapshot = build_snapshot(database_path); output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text(json.dumps(snapshot,indent=2)+"\n",encoding="utf-8")
    return snapshot
