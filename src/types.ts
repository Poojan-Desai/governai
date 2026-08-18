export type Asset = { asset_id:string; display_name:string; asset_type:string; layer:string; owner:string; sensitivity:string; freshness_sla:string; description:string; physical_name:string|null; status:string; row_count:number|null; incident_impact:boolean; protected:boolean };
export type Edge = { edge_id:string; upstream_asset_id:string; downstream_asset_id:string; transformation_type:string; transformation_description:string };
export type Column = { asset_id:string; column_name:string; data_type:string; classification:string; taxonomy_term_id:string; masking_policy:string; description:string };
export type Check = { rule_id:string; description:string; severity:string; passed:number; failed_rows:number; observed_value:string; expected_value:string };
export type Snapshot = {
  schema_version:string; generated_at:string; environment:string; data_notice:string;
  summary:{ governed_assets:number; quality_checks:number; quality_checks_passed:number; classified_columns:number; direct_identifier_columns:number; accepted_transactions:number; quarantined_batches:number; protected_downstream_assets:number };
  freshness:{ last_good_run_id:string; last_good_run_at:string; source_sha256:string; snapshot_generated_at:string; sla:string };
  incident:{ incident_id:string; title:string; run_id:string; source_asset_id:string; source_file:string; source_sha256:string; status:string; policy:string; source_rows:number; accepted_rows:number; quarantined_rows:number; critical_violation_count:number; warehouse_rows_before:number; warehouse_rows_after:number; contamination_prevented:boolean; failed_checks:Check[]; impacted_asset_ids:string[]; explanation:string };
  monthly_kpis:{month:string;transaction_count:number;transaction_value:number;confirmed_loss:number;loss_rate_bps:number;affected_transactions:number}[];
  forecast:{forecast_month:string;model_version:string;method:string;predicted_loss:number;slope:number;intercept:number;training_points:number;trained_at:string}|null;
  assets:Asset[]; lineage_edges:Edge[]; column_classifications:Column[];
  audit_events:{event_id:string;event_ts:string;actor:string;action:string;resource_id:string;run_id:string;outcome:string}[];
  limitations:string[];
};

export type CloudStatus = {
  schema_version:string; generated_at:string; phase:string;
  implementation_status:"IMPLEMENTED_LOCALLY"|string;
  live_verification_status:"VERIFIED"|"NOT_RUN"|string;
  truth_notice:string;
  credentials:{aws_configured:boolean;snowflake_configured:boolean;values_exposed:boolean};
  tools:Record<string,boolean>;
  artifacts:Record<string,boolean>;
  s3_zones:{name:string;purpose:string}[];
  snowflake_layers:string[];
  rbac_roles:string[];
  cloud_lineage:{from:string;to:string;status:string}[];
  latest_live_run:null|{run_id:string;status:string;reconciliation:{status:string}[]};
};
