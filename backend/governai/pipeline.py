"""Local pipeline adapter with production-style control semantics."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

from .catalog import bootstrap_catalog, downstream_assets
from .contracts import CheckResult, has_critical_failure, result, validate_accounts, validate_customers, validate_transactions


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SourceSnapshot:
    rows: tuple[dict[str, str], ...]
    columns: tuple[str, ...]
    sha256: str
    byte_size: int


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


class PipelineExecutionError(RuntimeError):
    """A terminal local failure whose run and rollback evidence were retained."""

    def __init__(self, run_id: str, *, repeated: bool = False):
        self.run_id = run_id
        self.repeated = repeated
        description = "Batch previously failed" if repeated else "Batch processing failed"
        super().__init__(
            f"{description}; no records published. Inspect run {run_id}. "
            "Use a new batch label for an explicit retry."
        )


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
    def read_source(path: Path) -> "SourceSnapshot":
        # Parse, hash and measure the same captured bytes. A later filesystem
        # replacement must not rewrite the provenance of already parsed rows.
        payload = Path(path).read_bytes()
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8"), newline=""))
        return SourceSnapshot(tuple(reader), tuple(reader.fieldnames or ()),
                              hashlib.sha256(payload).hexdigest(), len(payload))

    @staticmethod
    def read_csv(path: Path) -> list[dict[str, str]]:
        return list(LocalPipeline.read_source(path).rows)

    @staticmethod
    def read_csv_with_columns(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
        source = LocalPipeline.read_source(path)
        return list(source.rows), source.columns

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
        source = self.read_source(path)
        return self.ingest("source.crm_customers", "validated.customer_profiles", path, label, source, validate_customers(source.rows, columns=source.columns), self.load_customers)

    def ingest_accounts(self, path: Path, label: str = "base") -> RunOutcome:
        source = self.read_source(path)
        checks = validate_accounts(source.rows, self.known_ids("raw_customers", "customer_id"), columns=source.columns)
        return self.ingest("source.card_accounts", "validated.card_accounts", path, label, source, checks, self.load_accounts)

    def ingest_transactions(self, path: Path, label: str = "base") -> RunOutcome:
        source = self.read_source(path)
        checks = validate_transactions(source.rows, self.known_ids("raw_accounts", "account_id"), columns=source.columns)
        return self.ingest("source.card_transactions", "validated.card_transactions", path, label, source, checks, self.load_transactions)

    @staticmethod
    def transaction_replay_check(connection: sqlite3.Connection, rows: Sequence[Mapping[str, str]]) -> CheckResult:
        identifiers = sorted({row["transaction_id"] for row in rows if isinstance(row.get("transaction_id"), str)})
        existing: set[str] = set()
        # Keep queries below SQLite's traditional 999-variable limit and use
        # its primary-key index instead of scanning the entire transaction log.
        for offset in range(0, len(identifiers), 900):
            chunk = identifiers[offset:offset + 900]
            placeholders = ",".join("?" for _ in chunk)
            existing.update(row[0] for row in connection.execute(
                f"SELECT transaction_id FROM raw_transactions WHERE transaction_id IN ({placeholders})", chunk,
            ))
        return result(
            "transaction_id_not_previously_loaded",
            "Transaction IDs have not been published by another batch",
            sum(isinstance(row.get("transaction_id"), str) and row["transaction_id"] in existing for row in rows),
            "0 rows with previously published transaction IDs; replay the original batch identity for idempotency",
        )

    def ingest(self, asset_id: str, validated_id: str, path: Path, label: str, source: SourceSnapshot, checks: Sequence[CheckResult], loader: Callable[[sqlite3.Connection, Sequence[Mapping[str, str]], str], None]) -> RunOutcome:
        rows, source_hash = source.rows, source.sha256
        batch_id = self.batch_id(asset_id, source_hash, label)
        failure: PipelineExecutionError | None = None
        cause: Exception | None = None
        with self.connect() as connection:
            # Serialize identity lookup, replay checks and publication. A second
            # writer observes the first committed outcome rather than passing a
            # stale check or colliding on pipeline_runs.batch_id.
            connection.execute("BEGIN IMMEDIATE")
            if existing := self.existing(connection, batch_id):
                if existing.status == "failed":
                    raise PipelineExecutionError(existing.run_id, repeated=True)
                return existing
            if asset_id == "source.card_transactions":
                checks = [*checks, self.transaction_replay_check(connection, rows)]
            run_id, started = f"run-{uuid.uuid4().hex[:16]}", utc_now()
            connection.execute("INSERT INTO pipeline_runs(run_id,pipeline_name,batch_id,asset_id,source_path,source_sha256,started_at,status,source_row_count) VALUES(?,'governed_batch_ingestion',?,?,?,?,?,'running',?)", (run_id,batch_id,asset_id,path.name,source_hash,started,len(rows)))
            connection.execute("INSERT INTO source_manifests VALUES(?,?,?,?,?,?,?,?)", (f"manifest-{uuid.uuid4().hex[:16]}",run_id,asset_id,path.name,source_hash,source.byte_size,len(rows),started))
            connection.executemany("INSERT INTO quality_results(run_id,asset_id,rule_id,description,severity,passed,failed_rows,observed_value,expected_value) VALUES(?,?,?,?,?,?,?,?,?)", [(run_id,asset_id,c.rule_id,c.description,c.severity,int(c.passed),c.failed_rows,c.observed_value,c.expected_value) for c in checks])
            if has_critical_failure(checks):
                ended, impacted = utc_now(), tuple(downstream_assets(connection, asset_id))
                connection.execute("INSERT INTO quarantine_batches VALUES(?,?,?,?,?,?,?,?,?)", (f"quarantine-{uuid.uuid4().hex[:16]}",run_id,asset_id,path.name,source_hash,len(rows),sum(not c.passed for c in checks),"FAIL_CLOSED_FILE_ATOMIC_V1",ended))
                connection.execute("UPDATE pipeline_runs SET status='quarantined',ended_at=?,accepted_row_count=0,quarantined_row_count=? WHERE run_id=?", (ended,len(rows),run_id))
                self.audit(connection,"batch.quarantined",asset_id,run_id,"blocked",{"policy":"FAIL_CLOSED_FILE_ATOMIC_V1","failed_rules":[c.rule_id for c in checks if not c.passed],"impacted_assets":impacted})
                return RunOutcome(run_id,batch_id,asset_id,"quarantined",len(rows),0,len(rows),source_hash,tuple(checks),impacted)
            # Preserve control-plane evidence while rolling back every raw and
            # derived data change if either loading or rebuilding fails.
            connection.execute("SAVEPOINT publish_batch")
            try:
                loader(connection, rows, run_id)
                self.rebuild_products(connection)
                ended = utc_now()
                connection.execute("UPDATE pipeline_runs SET status='succeeded',ended_at=?,accepted_row_count=? WHERE run_id=?", (ended,len(rows),run_id))
                self.audit(connection,"batch.published",validated_id,run_id,"succeeded",{"accepted_rows":len(rows),"source_sha256":source_hash})
            except Exception as exc:
                connection.execute("ROLLBACK TO SAVEPOINT publish_batch")
                connection.execute("RELEASE SAVEPOINT publish_batch")
                connection.execute("UPDATE pipeline_runs SET status='failed',ended_at=?,accepted_row_count=0,quarantined_row_count=0 WHERE run_id=?", (utc_now(),run_id))
                # Exception messages can contain source values. Retain a type
                # and a safe operational explanation rather than raw payloads.
                self.audit(connection,"batch.failed",asset_id,run_id,"failed",{
                    "error_type":type(exc).__name__,
                    "message":"Load or product rebuild failed; all data writes rolled back.",
                    "stage":"load_and_rebuild",
                    "rollback_confirmed":True,
                    "source_sha256":source_hash,
                    "retry_policy":"Explicit retry requires a new batch label.",
                })
                failure, cause = PipelineExecutionError(run_id), exc
            else:
                connection.execute("RELEASE SAVEPOINT publish_batch")
                return RunOutcome(run_id,batch_id,asset_id,"succeeded",len(rows),len(rows),0,source_hash,tuple(checks))
        # Raising inside the outer transaction would erase the failure record.
        if failure is not None:
            raise failure from cause
        raise RuntimeError("Pipeline finished without an outcome")

    @staticmethod
    def load_customers(connection: sqlite3.Connection, rows: Sequence[Mapping[str, str]], run_id: str) -> None:
        connection.executemany("INSERT INTO raw_customers VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(customer_id) DO UPDATE SET full_name=excluded.full_name,email=excluded.email,phone=excluded.phone,state=excluded.state,customer_since=excluded.customer_since,segment=excluded.segment,ingestion_run_id=excluded.ingestion_run_id", [(r["customer_id"],r["full_name"],r["email"],r["phone"],r["state"],r["customer_since"],r["segment"],run_id) for r in rows])

    @staticmethod
    def load_accounts(connection: sqlite3.Connection, rows: Sequence[Mapping[str, str]], run_id: str) -> None:
        connection.executemany("INSERT INTO raw_accounts VALUES(?,?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET customer_id=excluded.customer_id,opened_date=excluded.opened_date,account_status=excluded.account_status,credit_limit=excluded.credit_limit,ingestion_run_id=excluded.ingestion_run_id", [(r["account_id"],r["customer_id"],r["opened_date"],r["account_status"],float(r["credit_limit"]),run_id) for r in rows])

    @staticmethod
    def load_transactions(connection: sqlite3.Connection, rows: Sequence[Mapping[str, str]], run_id: str) -> None:
        # The quality gate handles known IDs. Retain a strict unique constraint
        # as a final guard: no silent skips may inflate accepted-row counts.
        connection.executemany("INSERT INTO raw_transactions VALUES(?,?,?,?,?,?,?,?,?,?)", [(r["transaction_id"],r["account_id"],r["transaction_ts"],float(r["amount"]),r["merchant_category"],r["channel"],r["country_code"],int(r["is_fraud"]),float(r["confirmed_loss"]),run_id) for r in rows])

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
