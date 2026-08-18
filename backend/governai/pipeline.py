"""Local pipeline adapter with production-style control semantics."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

from .catalog import bootstrap_catalog, downstream_assets
from .contracts import CheckResult, has_critical_failure, validate_accounts, validate_customers, validate_transactions
from .generator import sha256_file


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RunOutcome:
    run_id: str
    batch_id: str
    asset_id: str
    status: str
    source_rows: int
    accepted_rows: int
    quarantined_rows: int
    source_sha256: str
    checks: tuple[CheckResult, ...]
    impacted_assets: tuple[str, ...] = ()


class LocalPipeline:
    def __init__(self, database_path: Path, schema_path: Path | None = None):
        self.database_path = Path(database_path)
        self.schema_path = schema_path or Path(__file__).parents[1] / "sql" / "schema.sql"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(self.schema_path.read_text(encoding="utf-8"))
            bootstrap_catalog(connection)

    @staticmethod
    def read_csv(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def batch_id(asset_id: str, source_hash: str, label: str) -> str:
        return "batch-" + hashlib.sha256(f"{asset_id}:{source_hash}:{label}".encode()).hexdigest()[:16]

    def known_ids(self, table: str, column: str) -> set[str]:
        if (table, column) not in {("raw_customers", "customer_id"), ("raw_accounts", "account_id")}:
            raise ValueError("Unsupported identifier lookup")
        with self.connect() as connection:
            return {row[0] for row in connection.execute(f"SELECT {column} FROM {table}")}

    def existing(self, connection: sqlite3.Connection, batch_id: str) -> RunOutcome | None:
        row = connection.execute("SELECT * FROM pipeline_runs WHERE batch_id=?", (batch_id,)).fetchone()
        if row is None:
            return None
        checks = tuple(CheckResult(
            check["rule_id"], check["description"], check["severity"], bool(check["passed"]),
            check["failed_rows"], check["observed_value"], check["expected_value"]
        ) for check in connection.execute("SELECT * FROM quality_results WHERE run_id=? ORDER BY quality_result_id", (row["run_id"],)))
        impacted = tuple(downstream_assets(connection, row["asset_id"])) if row["status"] == "quarantined" else ()
        return RunOutcome(row["run_id"], row["batch_id"], row["asset_id"], row["status"], row["source_row_count"], row["accepted_row_count"], row["quarantined_row_count"], row["source_sha256"], checks, impacted)

    def ingest_customers(self, path: Path, label: str = "base") -> RunOutcome:
        rows = self.read_csv(path)
        return self.ingest("source.crm_customers", "validated.customer_profiles", path, label, rows, validate_customers(rows), self.load_customers)

    def ingest_accounts(self, path: Path, label: str = "base") -> RunOutcome:
        rows = self.read_csv(path)
        checks = validate_accounts(rows, self.known_ids("raw_customers", "customer_id"))
        return self.ingest("source.card_accounts", "validated.card_accounts", path, label, rows, checks, self.load_accounts)

    def ingest_transactions(self, path: Path, label: str = "base") -> RunOutcome:
        rows = self.read_csv(path)
        checks = validate_transactions(rows, self.known_ids("raw_accounts", "account_id"))
        return self.ingest("source.card_transactions", "validated.card_transactions", path, label, rows, checks, self.load_transactions)

    def ingest(self, asset_id: str, validated_id: str, path: Path, label: str, rows: Sequence[Mapping[str, str]], checks: Sequence[CheckResult], loader: Callable[[sqlite3.Connection, Sequence[Mapping[str, str]], str], None]) -> RunOutcome:
        source_hash = sha256_file(path)
        batch_id = self.batch_id(asset_id, source_hash, label)
        with self.connect() as connection:
            if existing := self.existing(connection, batch_id):
                return existing
            run_id, started = f"run-{uuid.uuid4().hex[:16]}", utc_now()
            connection.execute("INSERT INTO pipeline_runs(run_id,pipeline_name,batch_id,asset_id,source_path,source_sha256,started_at,status,source_row_count) VALUES(?,'governed_batch_ingestion',?,?,?,?,?,'running',?)", (run_id,batch_id,asset_id,path.name,source_hash,started,len(rows)))
            connection.execute("INSERT INTO source_manifests VALUES(?,?,?,?,?,?,?,?)", (f"manifest-{uuid.uuid4().hex[:16]}",run_id,asset_id,path.name,source_hash,path.stat().st_size,len(rows),started))
            connection.executemany("INSERT INTO quality_results(run_id,asset_id,rule_id,description,severity,passed,failed_rows,observed_value,expected_value) VALUES(?,?,?,?,?,?,?,?,?)", [(run_id,asset_id,c.rule_id,c.description,c.severity,int(c.passed),c.failed_rows,c.observed_value,c.expected_value) for c in checks])
            if has_critical_failure(checks):
                ended, impacted = utc_now(), tuple(downstream_assets(connection, asset_id))
                connection.execute("INSERT INTO quarantine_batches VALUES(?,?,?,?,?,?,?,?,?)", (f"quarantine-{uuid.uuid4().hex[:16]}",run_id,asset_id,path.name,source_hash,len(rows),sum(not c.passed for c in checks),"FAIL_CLOSED_FILE_ATOMIC_V1",ended))
                connection.execute("UPDATE pipeline_runs SET status='quarantined',ended_at=?,accepted_row_count=0,quarantined_row_count=? WHERE run_id=?", (ended,len(rows),run_id))
                self.audit(connection,"batch.quarantined",asset_id,run_id,"blocked",{"policy":"FAIL_CLOSED_FILE_ATOMIC_V1","failed_rules":[c.rule_id for c in checks if not c.passed],"impacted_assets":impacted})
                return RunOutcome(run_id,batch_id,asset_id,"quarantined",len(rows),0,len(rows),source_hash,tuple(checks),impacted)
            loader(connection, rows, run_id)
            self.rebuild_products(connection)
            ended = utc_now()
            connection.execute("UPDATE pipeline_runs SET status='succeeded',ended_at=?,accepted_row_count=? WHERE run_id=?", (ended,len(rows),run_id))
            self.audit(connection,"batch.published",validated_id,run_id,"succeeded",{"accepted_rows":len(rows),"source_sha256":source_hash})
            return RunOutcome(run_id,batch_id,asset_id,"succeeded",len(rows),len(rows),0,source_hash,tuple(checks))

    @staticmethod
    def load_customers(connection: sqlite3.Connection, rows: Sequence[Mapping[str, str]], run_id: str) -> None:
        connection.executemany("INSERT INTO raw_customers VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(customer_id) DO UPDATE SET full_name=excluded.full_name,email=excluded.email,phone=excluded.phone,state=excluded.state,customer_since=excluded.customer_since,segment=excluded.segment,ingestion_run_id=excluded.ingestion_run_id", [(r["customer_id"],r["full_name"],r["email"],r["phone"],r["state"],r["customer_since"],r["segment"],run_id) for r in rows])

    @staticmethod
    def load_accounts(connection: sqlite3.Connection, rows: Sequence[Mapping[str, str]], run_id: str) -> None:
        connection.executemany("INSERT INTO raw_accounts VALUES(?,?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET customer_id=excluded.customer_id,opened_date=excluded.opened_date,account_status=excluded.account_status,credit_limit=excluded.credit_limit,ingestion_run_id=excluded.ingestion_run_id", [(r["account_id"],r["customer_id"],r["opened_date"],r["account_status"],float(r["credit_limit"]),run_id) for r in rows])

    @staticmethod
    def load_transactions(connection: sqlite3.Connection, rows: Sequence[Mapping[str, str]], run_id: str) -> None:
        connection.executemany("INSERT INTO raw_transactions VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(transaction_id) DO NOTHING", [(r["transaction_id"],r["account_id"],r["transaction_ts"],float(r["amount"]),r["merchant_category"],r["channel"],r["country_code"],int(r["is_fraud"]),float(r["confirmed_loss"]),run_id) for r in rows])

    @staticmethod
    def token(customer_id: str) -> str:
        return hashlib.sha256(f"governai-local-v1:{customer_id}".encode()).hexdigest()[:20]

    @staticmethod
    def mask_email(email: str) -> str:
        local, domain = email.split("@",1)
        return f"{local[0]}***@{domain}"

    def rebuild_products(self, connection: sqlite3.Connection) -> None:
        for table in ("model_loss_forecast","mart_monthly_loss_kpis","feature_account_behavior_30d","fct_card_transactions","dim_account","dim_customer"):
            connection.execute(f"DELETE FROM {table}")
        customers = connection.execute("SELECT * FROM raw_customers ORDER BY customer_id").fetchall()
        connection.executemany("INSERT INTO dim_customer VALUES(?,?,?,?,?,?)", [(self.token(r["customer_id"]),r["customer_id"],self.mask_email(r["email"]),r["state"],r["segment"],r["customer_since"]) for r in customers])
        connection.execute("INSERT INTO dim_account SELECT a.account_id,c.customer_token,a.opened_date,a.account_status,a.credit_limit FROM raw_accounts a JOIN dim_customer c ON c.customer_id=a.customer_id ORDER BY a.account_id")
        connection.execute("INSERT INTO fct_card_transactions SELECT t.transaction_id,t.account_id,t.transaction_ts,substr(t.transaction_ts,1,10),substr(t.transaction_ts,1,7),t.amount,t.merchant_category,t.channel,CASE WHEN t.country_code<>'US' THEN 1 ELSE 0 END,t.is_fraud,t.confirmed_loss FROM raw_transactions t JOIN dim_account a ON a.account_id=t.account_id ORDER BY t.transaction_ts,t.transaction_id")
        max_date = connection.execute("SELECT MAX(transaction_date) FROM fct_card_transactions").fetchone()[0]
        if max_date:
            connection.execute("INSERT INTO feature_account_behavior_30d SELECT account_id,?,COUNT(*),ROUND(AVG(amount),2),ROUND(AVG(is_cross_border),4),ROUND(SUM(confirmed_loss),2) FROM fct_card_transactions WHERE transaction_date>=date(?,'-29 days') GROUP BY account_id", (max_date,max_date))
        connection.execute("INSERT INTO mart_monthly_loss_kpis SELECT month,COUNT(*),ROUND(SUM(amount),2),ROUND(SUM(confirmed_loss),2),CASE WHEN SUM(amount)=0 THEN 0 ELSE ROUND(SUM(confirmed_loss)*10000.0/SUM(amount),2) END,SUM(CASE WHEN confirmed_loss>0 THEN 1 ELSE 0 END) FROM fct_card_transactions GROUP BY month ORDER BY month")
        self.fit_forecast(connection)

    @staticmethod
    def fit_forecast(connection: sqlite3.Connection) -> None:
        rows = connection.execute("SELECT month,confirmed_loss FROM mart_monthly_loss_kpis ORDER BY month").fetchall()
        if len(rows) < 2: return
        xs, ys = list(range(len(rows))), [float(r["confirmed_loss"]) for r in rows]
        xm, ym = sum(xs)/len(xs), sum(ys)/len(ys)
        slope = sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs)
        intercept, predicted = ym-slope*xm, max(0.0, ym-slope*xm+slope*len(rows))
        last = datetime.strptime(rows[-1]["month"],"%Y-%m")
        year, month = (last.year+1,1) if last.month == 12 else (last.year,last.month+1)
        connection.execute("INSERT INTO model_loss_forecast VALUES(?,'ols-loss-v1','ordinary_least_squares',?,?,?,?,?)", (f"{year:04d}-{month:02d}",round(predicted,2),round(slope,6),round(intercept,6),len(rows),utc_now()))

    @staticmethod
    def audit(connection: sqlite3.Connection, action: str, resource: str, run_id: str, outcome: str, details: Mapping[str, object]) -> None:
        connection.execute("INSERT INTO audit_events VALUES(?,?,'system:pipeline',?,?,?,?,?)", (f"event-{uuid.uuid4().hex[:16]}",utc_now(),action,resource,run_id,outcome,json.dumps(details,sort_keys=True)))

    def run_demo(self, base_dir: Path, incident_file: Path) -> dict[str, RunOutcome]:
        outcomes = {
            "customers": self.ingest_customers(base_dir / "customers.csv"),
            "accounts": self.ingest_accounts(base_dir / "accounts.csv"),
            "transactions": self.ingest_transactions(base_dir / "transactions.csv"),
        }
        outcomes["incident"] = self.ingest_transactions(incident_file,"quality-incident-001")
        return outcomes
