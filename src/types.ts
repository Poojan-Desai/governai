export type Asset = { asset_id:string; display_name:string; asset_type:string; layer:string; owner:string; sensitivity:string; freshness_sla:string; description:string; physical_name:string|null; status:string; row_count:number|null; incident_impact:boolean; protected:boolean };
export type Edge = { edge_id:string; upstream_asset_id:string; downstream_asset_id:string; transformation_type:string; transformation_description:string };
export type Column = { asset_id:string; column_name:string; data_type:string; classification:string; taxonomy_term_id:string; masking_policy:string; description:string };
export type Check = { rule_id:string; description:string; severity:string; passed:number; failed_rows:number; observed_value:string; expected_value:string };
export type ExperimentArm = { label:string; units:number; conversions:number; rate:number };
export type ExperimentEvidence = {
  experiment_id:string; name:string; status:string; hypothesis:string;
  design:{ randomization_unit:string; analysis_population:number; treatment_allocation:number; assignment_method:string; assignment_digest:string; sample_ratio_mismatch_p_value:number; sample_ratio_mismatch_detected:boolean; alpha:number };
  metric:{ metric_id:string; name:string; unit:string; direction:string; numerator:string; denominator:string };
  simulation_assumptions:{ control_conversion_probability:number; treatment_conversion_probability:number; outcome_method:string };
  arms:{ control:ExperimentArm; treatment:ExperimentArm };
  analysis:{ absolute_lift:number; relative_lift:number|null; confidence_level:number; confidence_interval_lower:number; confidence_interval_upper:number; confidence_interval_method:string; significance_test:string; z_score:number; p_value:number; statistically_significant:boolean; decision:string };
  impact:{ incremental_enrollments_in_sample:number; annual_value_per_incremental_enrollment:number; gross_annualized_value:number; treatment_cost_per_unit:number; total_treatment_cost:number; net_annualized_value:number; roi:number; currency:string };
  data_notice:string; limitations:string[];
};
export type AssistantExample = {
  question:string; engine:string; status:string; answer:string; reason:string|null;
  intent_id:string|null; metric_id:string|null; approved_query:string|null;
  citation:{asset_id:string;record:string;field:string}|null;
  policy:{read_only:boolean;approved_sources_only:boolean;aggregate_only:boolean;dynamic_sql:boolean};
};
export type AssistantEvidence = {
  status:string; name:string; description:string; engine:string;
  semantic_metrics:{metric_id:string;name:string;definition:string;asset_id:string;format:string}[];
  examples:AssistantExample[]; controls:string[]; data_notice:string; limitations:string[];
};
export type ModelGovernanceEvidence = {
  status:string;
  model_card:{model_id:string;name:string;owner:string;task:string;intended_use:string;prohibited_use:string;target:string;features:string[];training_window:string;data_classification:string};
  backtest:{method:string;minimum_training_points:number;fold_count:number;folds:{month:string;actual:number;baseline_prediction:number;challenger_prediction:number;training_points:number}[];candidates:{model_id:string;method:string;mae:number;rmse:number}[];research_champion:string;mae_improvement:number;decision:string};
  drift:{method:string;watch_threshold:number;alert_threshold:number;baseline_window:string;current_window:string;status:string;metrics:{feature:string;unit:string;baseline_mean:number;current_mean:number;standardized_mean_difference:number;absolute_smd:number;status:string}[]};
  approval_gates:{gate:string;status:string}[]; data_notice:string; limitations:string[];
};
export type Snapshot = {
  schema_version:string; generated_at:string; environment:string; data_notice:string;
  summary:{ governed_assets:number; quality_checks:number; quality_checks_passed:number; classified_columns:number; direct_identifier_columns:number; accepted_transactions:number; quarantined_batches:number; protected_downstream_assets:number };
  freshness:{ last_good_run_id:string; last_good_run_at:string; source_sha256:string; snapshot_generated_at:string; sla:string };
  incident:{ incident_id:string; title:string; run_id:string; source_asset_id:string; source_file:string; source_sha256:string; status:string; policy:string; source_rows:number; accepted_rows:number; quarantined_rows:number; critical_violation_count:number; warehouse_rows_before:number; warehouse_rows_after:number; contamination_prevented:boolean; failed_checks:Check[]; impacted_asset_ids:string[]; explanation:string };
  monthly_kpis:{month:string;transaction_count:number;transaction_value:number;confirmed_loss:number;loss_rate_bps:number;affected_transactions:number}[];
  forecast:{forecast_month:string;model_version:string;method:string;predicted_loss:number;slope:number;intercept:number;training_points:number;trained_at:string}|null;
  experiment:ExperimentEvidence;
  assistant:AssistantEvidence;
  model_governance:ModelGovernanceEvidence;
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
