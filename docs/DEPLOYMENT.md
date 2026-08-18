# Phase 2 live setup and deployment plan

This is the exact boundary not executed in the current environment. Complete it
in a personal AWS account and Snowflake trial/account using only simulated data.
Expect small Snowflake compute charges while warehouses are running; both
warehouses auto-suspend after 60 seconds.

## 1. Install tools locally

Install Terraform 1.6+, Python 3.11+, Node 22+, and an AWS CLI or AWS IAM Identity
Center profile. From the repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[cloud]'
npm install
```

Do not put access keys, passwords, private keys, `.env`, or `terraform.tfstate`
in Git. `.env*` and `.local/` are ignored; remote Terraform state is recommended
before team use.

## 2. Create the AWS lake

Authenticate with a temporary/profile-based AWS identity, copy the example
variables, review the plan, then apply:

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
terraform output
cd ../..
```

The first apply creates the private versioned bucket, rotating KMS key, TLS/public
access controls, zone lifecycle rules, and a pipeline IAM policy. Attach the
printed pipeline policy to a dedicated local/CI role through IAM Identity Center
or IAM; do not create long-lived access keys for the repository.

Record these non-secret outputs:

- `data_lake_bucket`
- `data_lake_kms_key_arn`
- `pipeline_policy_arn`
- `snowflake_storage_role_arn`

## 3. Bootstrap Snowflake

Open a Snowflake worksheet and run the numbered files in this order, switching
roles only as the scripts specify:

1. `snowflake/sql/001_bootstrap.sql`
2. `snowflake/sql/002_rbac.sql`
3. `snowflake/sql/003_tables_and_grants.sql`

Render the stage script using the Terraform outputs:

```bash
python3 scripts/render_snowflake_sql.py \
  --bucket YOUR_BUCKET \
  --aws-role-arn YOUR_SNOWFLAKE_STORAGE_ROLE_ARN
```

Run `.local/cloud/004_storage_integration.sql` in Snowflake. Its `DESC
INTEGRATION` output provides `STORAGE_AWS_IAM_USER_ARN` and
`STORAGE_AWS_EXTERNAL_ID`. These values establish trust; they are not AWS secret
keys.

Put both values in untracked `infrastructure/terraform/terraform.tfvars`, apply
Terraform again, and confirm `snowflake_trust_enabled = true`:

```hcl
snowflake_iam_user_arn = "value from DESC INTEGRATION"
snowflake_external_id  = "value from DESC INTEGRATION"
```

Then run:

4. `snowflake/sql/005_masking_policies.sql`

Create or choose a Snowflake user and grant it both service roles for the
portfolio run; the active role still enforces the boundary:

```sql
USE ROLE USERADMIN;
GRANT ROLE GOVAI_PIPELINE_ROLE TO USER YOUR_USER;
GRANT ROLE GOVAI_DBT_ROLE TO USER YOUR_USER;
```

For CI, use Snowflake key-pair authentication. For a one-time local verification,
an environment-only password is acceptable; never save it in the repository.

## 4. Export configuration to the shell

Use `.env.example` as a name checklist, not as a file to commit. Export the real
values in your terminal or secret manager. Required values are AWS region/profile,
bucket, KMS ARN, Snowflake account/user, and either password or private-key path.
The checked-in dbt profile currently uses `SNOWFLAKE_PASSWORD`; key-pair dbt
authentication is the recommended hardening follow-up.

## 5. Run the live evidence gates

```bash
npm test
npm run cloud:status
npm run cloud:run
npm run cloud:incident
npm run cloud:run
```

Interpretation:

1. First `cloud:run`: three accepted datasets load, dbt builds, and three
   reconciliations must be `MATCHED`.
2. `cloud:incident`: the corrupt transaction file appears in raw/quarantine;
   Snowflake and dbt must not be invoked.
3. Second `cloud:run`: S3 objects and Snowflake batches are reused, and dbt is
   skipped because no accepted input changed.

Only after this sequence succeeds may `src/data/cloud-status.json` display
`VERIFIED`. Keep `.local/cloud/latest-run.json` as local evidence; inspect it for
batch IDs, row counts, hashes, dbt command, and reconciliation status before
sharing screenshots.

## 6. Verify Snowflake controls manually

Run `snowflake/sql/006_verification.sql`. Then open separate sessions or switch
active roles carefully:

- `GOVAI_ANALYST`: query ANALYTICS; RAW access must fail.
- `GOVAI_RESTRICTED_ANALYST`: RAW customer/financial fields should be visible.
- `GOVAI_DATA_ENGINEER`: RAW SELECT works, but direct identifiers/financial
  values follow masking policy.
- `GOVAI_GOVERNANCE_ADMIN`: governance evidence is readable; RAW SELECT is not.

Capture query IDs or worksheet results without copying row-level identifiers.

## Deployment plan after the live gate

Host the static Vite build behind a low-cost static host, run the Python command
from an approved CI job, keep secrets in the host's secret store, and publish
only aggregate dashboard JSON. A managed scheduler, API, alarms, budgets, and
remote Terraform state are production hardening items—not current claims.
