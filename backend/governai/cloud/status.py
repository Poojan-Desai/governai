"""Credential-safe readiness report for the dashboard and handoff."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _present(name: str) -> bool:
    return bool(os.getenv(name))


def _module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, AttributeError):
        return False


def build_readiness(project_root: Path) -> dict[str, Any]:
    aws_configured = (
        (_present("AWS_ACCESS_KEY_ID") and _present("AWS_SECRET_ACCESS_KEY"))
        or _present("AWS_PROFILE")
    ) and (_present("AWS_REGION") or _present("AWS_DEFAULT_REGION"))
    snowflake_configured = all(
        _present(name)
        for name in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER")
    ) and (_present("SNOWFLAKE_PASSWORD") or _present("SNOWFLAKE_PRIVATE_KEY_PATH"))
    required_files = {
        "terraform": project_root / "infrastructure" / "terraform" / "main.tf",
        "dbt_project": project_root / "dbt" / "dbt_project.yml",
        "snowflake_bootstrap": project_root / "snowflake" / "sql" / "001_bootstrap.sql",
        "cloud_orchestrator": project_root / "backend" / "governai" / "cloud" / "orchestrator.py",
    }
    live_report = project_root / ".local" / "cloud" / "latest-run.json"
    latest_live_run = None
    live_verified = False
    if live_report.exists():
        try:
            candidate = json.loads(live_report.read_text(encoding="utf-8"))
            reconciliations = candidate.get("reconciliation", [])
            live_verified = (
                candidate.get("status") == "SUCCEEDED"
                and len(reconciliations) == 3
                and all(item.get("status") == "MATCHED" for item in reconciliations)
            )
            latest_live_run = candidate if live_verified else None
        except (OSError, json.JSONDecodeError, AttributeError):
            live_verified = False
    return {
        "schema_version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "Phase 2",
        "implementation_status": "IMPLEMENTED_LOCALLY",
        "live_verification_status": "VERIFIED" if live_verified else "NOT_RUN",
        "truth_notice": "No AWS/Snowflake deployment is claimed unless a live run report exists and all reconciliations match.",
        "credentials": {
            "aws_configured": bool(aws_configured),
            "snowflake_configured": bool(snowflake_configured),
            "values_exposed": False,
        },
        "tools": {
            "terraform": bool(shutil.which("terraform")),
            "dbt": bool(shutil.which("dbt")),
            "aws_cli": bool(shutil.which("aws")),
            "snowflake_connector": _module_present("snowflake.connector"),
            "boto3": _module_present("boto3"),
        },
        "artifacts": {name: path.exists() for name, path in required_files.items()},
        "s3_zones": [
            {"name": "raw", "purpose": "Immutable source files and canonical manifests"},
            {"name": "validated", "purpose": "Contract-approved source files only"},
            {"name": "quarantined", "purpose": "Blocked files and rule evidence"},
            {"name": "curated", "purpose": "Optional governed exports from Snowflake marts"},
        ],
        "snowflake_layers": ["RAW", "STAGING", "CURATED", "ANALYTICS", "GOVERNANCE"],
        "rbac_roles": [
            "GOVAI_DATA_ENGINEER",
            "GOVAI_ANALYST",
            "GOVAI_GOVERNANCE_ADMIN",
            "GOVAI_RESTRICTED_ANALYST",
            "GOVAI_PIPELINE_ROLE",
            "GOVAI_DBT_ROLE",
        ],
        "cloud_lineage": [
            {"from": "Generated CSV + manifest", "to": "S3 raw", "status": "DEFINED_NOT_EXECUTED"},
            {"from": "S3 raw", "to": "Quality contract", "status": "VERIFIED_LOCALLY"},
            {"from": "Quality contract", "to": "S3 validated/quarantined", "status": "DEFINED_NOT_EXECUTED"},
            {"from": "S3 validated", "to": "Snowflake RAW", "status": "DEFINED_NOT_EXECUTED"},
            {"from": "Snowflake RAW", "to": "dbt STAGING/CURATED/ANALYTICS", "status": "DEFINED_NOT_EXECUTED"},
            {"from": "Snowflake audit", "to": "Reconciliation evidence", "status": "DEFINED_NOT_EXECUTED"},
        ],
        "latest_live_run": latest_live_run,
    }


def write_readiness(project_root: Path, output_path: Path) -> dict[str, Any]:
    result = build_readiness(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
