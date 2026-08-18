# Minimal Phase 2 AWS infrastructure

Terraform defines one private, versioned S3 bucket; one rotating KMS key; public
access and insecure transport blocks; zone retention rules; one pipeline policy;
and an optional Snowflake read-only role restricted to `validated/`. It does not
add Lambda, Step Functions, networking, or a container platform because the Phase
2 pipeline runs from a developer/CI runner and those resources would be unused.

The Snowflake role uses a two-pass handshake:

1. Apply with both Snowflake trust variables unset. This creates the bucket, KMS
   key, and policies and prints the predictable storage-role ARN.
2. Use that ARN in `snowflake/sql/004_storage_integration.template.sql`, run the
   rendered SQL, and execute `DESC INTEGRATION GOVERNAI_S3_INTEGRATION`.
3. Copy only the returned IAM user ARN and external ID into an untracked
   `terraform.tfvars`, then apply again. Terraform creates the role with that
   exact trusted principal and external-ID condition.

No credentials belong in Terraform variables or state for this design.
