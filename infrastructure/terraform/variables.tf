variable "aws_region" {
  description = "AWS region for the GovernAI data lake."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Short environment label used in names and tags."
  type        = string
  default     = "portfolio"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.environment))
    error_message = "environment must contain lowercase letters, numbers, or hyphens only."
  }
}

variable "bucket_name_override" {
  description = "Optional globally unique bucket name; null uses a deterministic account-based name."
  type        = string
  default     = null
}

variable "snowflake_iam_user_arn" {
  description = "STORAGE_AWS_IAM_USER_ARN returned by DESC INTEGRATION; leave null during bootstrap."
  type        = string
  default     = null
}

variable "snowflake_external_id" {
  description = "STORAGE_AWS_EXTERNAL_ID returned by DESC INTEGRATION; required with snowflake_iam_user_arn."
  type        = string
  default     = null

  validation {
    condition     = (var.snowflake_iam_user_arn == null) == (var.snowflake_external_id == null)
    error_message = "Set snowflake_iam_user_arn and snowflake_external_id together."
  }
}
