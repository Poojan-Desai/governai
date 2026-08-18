from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
from pathlib import Path

from .analytics_assistant import build_assistant_evidence
from .experiment import run_experiment
from .generator import generate_sources
from .model_governance import build_model_governance
from .pipeline import LocalPipeline
from .snapshot import write_snapshot

def run_demo(root: Path, reset: bool) -> dict[str, object]:
    local = root / ".local"
    if reset and local.exists(): shutil.rmtree(local)
    generated = generate_sources(local / "sources")
    pipeline = LocalPipeline(local / "governai.db"); pipeline.initialize()
    outcomes = pipeline.run_demo(generated.base_dir,generated.incident_file)
    snapshot_path = root / "src" / "data" / "demo-snapshot.json"
    snapshot = write_snapshot(local / "governai.db",snapshot_path)
    return {"database":str(local / "governai.db"),"snapshot":str(snapshot_path),"source_hashes":generated.hashes,"runs":{name:{"run_id":r.run_id,"status":r.status,"source_rows":r.source_rows,"accepted_rows":r.accepted_rows,"quarantined_rows":r.quarantined_rows} for name,r in outcomes.items()},"summary":snapshot["summary"]}


def write_cloud_status(root: Path) -> dict[str, object]:
    from .cloud.status import write_readiness

    return write_readiness(root, root / "src" / "data" / "cloud-status.json")


def run_experiment_status(root: Path) -> dict[str, object]:
    database = root / ".local" / "governai.db"
    if not database.exists():
        raise SystemExit("Local evidence database not found; run `npm run demo` first")
    connection = sqlite3.connect(database)
    try:
        account_ids = [
            row[0]
            for row in connection.execute("SELECT account_id FROM dim_account ORDER BY account_id")
        ]
    finally:
        connection.close()
    return run_experiment(account_ids)


def run_local_evidence(root: Path, builder) -> dict[str, object]:
    database = root / ".local" / "governai.db"
    if not database.exists():
        raise SystemExit("Local evidence database not found; run `npm run demo` first")
    connection = sqlite3.connect(database)
    try:
        return builder(connection)
    finally:
        connection.close()


def build_live_pipeline(root: Path):
    from .cloud.dbt_runner import DbtRunner
    from .cloud.orchestrator import CloudPipeline
    from .cloud.s3 import S3DataLake
    from .cloud.snowflake import SnowflakeWarehouse

    return CloudPipeline(
        object_store=S3DataLake.from_environment(),
        warehouse=SnowflakeWarehouse.from_environment(),
        dbt=DbtRunner(project_dir=root / "dbt", profiles_dir=root / "dbt"),
    )


def run_cloud(root: Path) -> dict[str, object]:
    from .cloud.orchestrator import QualityGateError, ReconciliationMismatch

    generated = generate_sources(root / ".local" / "cloud" / "sources")
    pipeline = build_live_pipeline(root)
    try:
        report = pipeline.run_base(source_dir=generated.base_dir)
    except (QualityGateError, ReconciliationMismatch) as exc:
        failed = root / ".local" / "cloud" / f"failed-{exc.report.run_id}.json"
        exc.report.write(failed)
        write_cloud_status(root)
        raise SystemExit(f"Cloud pipeline stopped safely; evidence: {failed}") from exc
    report.write(root / ".local" / "cloud" / "latest-run.json")
    write_cloud_status(root)
    return report.to_dict()


def run_cloud_incident(root: Path) -> dict[str, object]:
    generated = generate_sources(root / ".local" / "cloud" / "sources")
    with (generated.base_dir / "accounts.csv").open(encoding="utf-8", newline="") as handle:
        known_accounts = {row["account_id"] for row in csv.DictReader(handle)}
    report = build_live_pipeline(root).run_incident(
        incident_file=generated.incident_file,
        known_account_ids=known_accounts,
    )
    evidence = root / ".local" / "cloud" / f"incident-{report.run_id}.json"
    report.write(evidence)
    write_cloud_status(root)
    return report.to_dict()

def main() -> None:
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True)
    demo=sub.add_parser("demo"); demo.add_argument("--project-root",type=Path,default=Path.cwd()); demo.add_argument("--reset",action="store_true")
    for name in ("experiment-status", "assistant-status", "model-status", "cloud-status", "cloud-run", "cloud-incident"):
        command = sub.add_parser(name)
        command.add_argument("--project-root", type=Path, default=Path.cwd())
    args=parser.parse_args()
    root = args.project_root.resolve()
    if args.command=="demo":
        result = run_demo(root,args.reset)
    elif args.command == "experiment-status":
        result = run_experiment_status(root)
    elif args.command == "assistant-status":
        result = run_local_evidence(root, build_assistant_evidence)
    elif args.command == "model-status":
        result = run_local_evidence(root, build_model_governance)
    elif args.command == "cloud-status":
        result = write_cloud_status(root)
    elif args.command == "cloud-run":
        result = run_cloud(root)
    else:
        result = run_cloud_incident(root)
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()
