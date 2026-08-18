"""Render the storage-integration SQL without ever accepting AWS credentials."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--aws-role-arn", required=True)
    parser.add_argument("--output", type=Path, default=Path(".local/cloud/004_storage_integration.sql"))
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", args.bucket):
        raise SystemExit("Bucket name format is invalid")
    if not re.fullmatch(r"arn:aws[a-z-]*:iam::\d{12}:role/[A-Za-z0-9+=,.@_/-]+", args.aws_role_arn):
        raise SystemExit("AWS role ARN format is invalid")
    template = Path("snowflake/sql/004_storage_integration.template.sql").read_text(encoding="utf-8")
    rendered = template.replace("__S3_BUCKET__", args.bucket).replace("__AWS_ROLE_ARN__", args.aws_role_arn)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
