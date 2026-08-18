output "data_lake_bucket" {
  description = "Bucket supplied to GOVERNAI_S3_BUCKET and the Snowflake stage template."
  value       = aws_s3_bucket.data_lake.id
}

output "data_lake_kms_key_arn" {
  description = "KMS key supplied to GOVERNAI_KMS_KEY_ARN."
  value       = aws_kms_key.data_lake.arn
}

output "pipeline_policy_arn" {
  description = "Attach this policy to the CI or developer principal that runs the pipeline."
  value       = aws_iam_policy.pipeline.arn
}

output "snowflake_storage_role_arn" {
  description = "Role ARN used by the Snowflake storage integration, even before trust is enabled."
  value       = local.snowflake_role_arn
}

output "snowflake_trust_enabled" {
  description = "True only after Snowflake's generated principal and external ID are configured."
  value       = local.enable_snowflake_trust
}
