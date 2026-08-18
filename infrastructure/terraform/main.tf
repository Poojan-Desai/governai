data "aws_caller_identity" "current" {}

locals {
  bucket_name             = coalesce(var.bucket_name_override, "governai-${var.environment}-${data.aws_caller_identity.current.account_id}")
  snowflake_role_name     = "governai-${var.environment}-snowflake-storage"
  snowflake_role_arn      = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.snowflake_role_name}"
  enable_snowflake_trust  = var.snowflake_iam_user_arn != null
  zones                   = toset(["raw", "validated", "quarantined", "curated"])
}

resource "aws_kms_key" "data_lake" {
  description             = "GovernAI simulated banking data-lake encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "data_lake" {
  name          = "alias/governai-${var.environment}-data-lake"
  target_key_id = aws_kms_key.data_lake.key_id
}

resource "aws_s3_bucket" "data_lake" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_ownership_controls" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket                  = aws_s3_bucket.data_lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data_lake.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  dynamic "rule" {
    for_each = local.zones
    content {
      id     = "${rule.value}-retention"
      status = "Enabled"
      filter { prefix = "${rule.value}/" }
      noncurrent_version_expiration { noncurrent_days = 90 }
      abort_incomplete_multipart_upload { days_after_initiation = 7 }
    }
  }
}

data "aws_iam_policy_document" "require_tls" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.data_lake.arn,
      "${aws_s3_bucket.data_lake.arn}/*"
    ]
    principals { type = "*" identifiers = ["*"] }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "require_tls" {
  bucket = aws_s3_bucket.data_lake.id
  policy = data.aws_iam_policy_document.require_tls.json
}

data "aws_iam_policy_document" "pipeline" {
  statement {
    sid       = "ListGovernAIDataLake"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [aws_s3_bucket.data_lake.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = [for zone in local.zones : "${zone}/*"]
    }
  }
  statement {
    sid       = "ReadWriteGovernedZones"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = [for zone in local.zones : "${aws_s3_bucket.data_lake.arn}/${zone}/*"]
  }
  statement {
    sid       = "UseDataLakeKey"
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.data_lake.arn]
  }
}

resource "aws_iam_policy" "pipeline" {
  name        = "governai-${var.environment}-pipeline"
  description = "Least-privilege data-plane access for the GovernAI orchestrator"
  policy      = data.aws_iam_policy_document.pipeline.json
}

data "aws_iam_policy_document" "snowflake_trust" {
  count = local.enable_snowflake_trust ? 1 : 0
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.snowflake_iam_user_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.snowflake_external_id]
    }
  }
}

resource "aws_iam_role" "snowflake_storage" {
  count              = local.enable_snowflake_trust ? 1 : 0
  name               = local.snowflake_role_name
  assume_role_policy = data.aws_iam_policy_document.snowflake_trust[0].json
}

data "aws_iam_policy_document" "snowflake_storage" {
  statement {
    sid       = "ListValidatedZone"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [aws_s3_bucket.data_lake.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["validated/*"]
    }
  }
  statement {
    sid       = "ReadValidatedObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.data_lake.arn}/validated/*"]
  }
  statement {
    sid       = "DecryptValidatedObjects"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.data_lake.arn]
  }
}

resource "aws_iam_role_policy" "snowflake_storage" {
  count  = local.enable_snowflake_trust ? 1 : 0
  name   = "read-validated-zone"
  role   = aws_iam_role.snowflake_storage[0].id
  policy = data.aws_iam_policy_document.snowflake_storage.json
}
