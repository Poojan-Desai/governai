"""Snowflake warehouse adapter. All methods execute real Snowflake SQL."""

from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .models import BatchManifest, LoadResult


class SnowflakeConfigurationError(RuntimeError):
    pass


class SnowflakeLoadError(RuntimeError):
    pass


DATASETS: dict[str, dict[str, Any]] = {
    "customers": {
        "table": "CUSTOMERS",
        "key": "CUSTOMER_ID",
        "columns": (
            "CUSTOMER_ID",
            "FULL_NAME",
            "EMAIL",
            "PHONE",
            "STATE",
            "CUSTOMER_SINCE",
            "SEGMENT",
        ),
        "expressions": (
            "$1::STRING",
            "$2::STRING",
            "$3::STRING",
            "$4::STRING",
            "$5::STRING",
            "$6::DATE",
            "$7::STRING",
        ),
    },
    "accounts": {
        "table": "ACCOUNTS",
        "key": "ACCOUNT_ID",
        "columns": (
            "ACCOUNT_ID",
            "CUSTOMER_ID",
            "OPENED_DATE",
            "ACCOUNT_STATUS",
            "CREDIT_LIMIT",
        ),
        "expressions": (
            "$1::STRING",
            "$2::STRING",
            "$3::DATE",
            "$4::STRING",
            "$5::NUMBER(18,2)",
        ),
    },
    "transactions": {
        "table": "TRANSACTIONS",
        "key": "TRANSACTION_ID",
        "columns": (
            "TRANSACTION_ID",
            "ACCOUNT_ID",
            "TRANSACTION_TS",
            "AMOUNT",
            "MERCHANT_CATEGORY",
            "CHANNEL",
            "COUNTRY_CODE",
            "IS_FRAUD",
            "CONFIRMED_LOSS",
        ),
        "expressions": (
            "$1::STRING",
            "$2::STRING",
            "$3::TIMESTAMP_TZ",
            "$4::NUMBER(18,2)",
            "$5::STRING",
            "$6::STRING",
            "$7::STRING",
            "$8::BOOLEAN",
            "$9::NUMBER(18,2)",
        ),
    },
}


class SnowflakeWarehouse:
    def __init__(
        self,
        *,
        connection_factory: Callable[[], Any],
        database: str = "GOVERNAI",
        validated_stage: str = "GOVERNAI.GOVERNANCE.S3_VALIDATED_STAGE",
    ):
        self.connection_factory = connection_factory
        self.database = self._identifier(database)
        self.validated_stage = self._qualified_identifier(validated_stage)

    @classmethod
    def from_environment(cls) -> "SnowflakeWarehouse":
        try:
            import snowflake.connector  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SnowflakeConfigurationError(
                "Install the 'cloud' extra to use Snowflake: pip install -e '.[cloud]'"
            ) from exc
        required = {
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "user": os.getenv("SNOWFLAKE_USER"),
            "role": os.getenv("SNOWFLAKE_ROLE", "GOVAI_PIPELINE_ROLE"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "GOVAI_INGEST_WH"),
            "database": os.getenv("SNOWFLAKE_DATABASE", "GOVERNAI"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise SnowflakeConfigurationError(
                "Missing Snowflake configuration: " + ", ".join(sorted(missing))
            )
        password = os.getenv("SNOWFLAKE_PASSWORD")
        private_key_file = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
        if not password and not private_key_file:
            raise SnowflakeConfigurationError(
                "Set SNOWFLAKE_PASSWORD or SNOWFLAKE_PRIVATE_KEY_PATH"
            )

        def connect() -> Any:
            kwargs: dict[str, Any] = dict(required)
            kwargs["schema"] = "GOVERNANCE"
            kwargs["session_parameters"] = {
                "QUERY_TAG": "governai_phase2_pipeline",
                "STATEMENT_TIMEOUT_IN_SECONDS": 300,
            }
            if password:
                kwargs["password"] = password
            else:
                kwargs["private_key_file"] = private_key_file
            return snowflake.connector.connect(**kwargs)

        return cls(
            connection_factory=connect,
            database=str(required["database"]),
        )

    @staticmethod
    def _identifier(value: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(f"Unsafe Snowflake identifier: {value!r}")
        return value.upper()

    @classmethod
    def _qualified_identifier(cls, value: str) -> str:
        return ".".join(cls._identifier(part) for part in value.split("."))

    @staticmethod
    def _stage_path(key: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_./=\-]+", key):
            raise ValueError("Unsafe S3 object key for Snowflake stage")
        return key

    @staticmethod
    def _literal(value: str) -> str:
        """Quote a value embedded in COPY transformation SQL after escaping it."""
        return "'" + value.replace("'", "''") + "'"

    def load_validated_csv(
        self, *, dataset: str, s3_key: str, manifest: BatchManifest
    ) -> LoadResult:
        if dataset not in DATASETS:
            raise ValueError(f"Unsupported Snowflake dataset: {dataset}")
        spec = DATASETS[dataset]
        connection = self.connection_factory()
        cursor = connection.cursor()
        try:
            raw_table = f"{self.database}.RAW.{spec['table']}"
            cursor.execute(
                f"""
                SELECT loads.STATUS, loads.ROW_COUNT, loads.SOURCE_SHA256,
                       COUNT(raw.{spec['key']}), MIN(raw.SOURCE_SHA256), MAX(raw.SOURCE_SHA256)
                FROM {self.database}.GOVERNANCE.BATCH_LOADS loads
                LEFT JOIN {raw_table} raw ON raw.BATCH_ID=loads.BATCH_ID
                WHERE loads.BATCH_ID=%s
                GROUP BY loads.STATUS, loads.ROW_COUNT, loads.SOURCE_SHA256
                """,
                (manifest.batch_id, ),
            )
            existing = cursor.fetchone()
            if existing and str(existing[0]).upper() == "SUCCEEDED":
                if (
                    int(existing[1]) != manifest.row_count
                    or str(existing[2]) != manifest.source_sha256
                    or int(existing[3]) != manifest.row_count
                    or str(existing[4]) != manifest.source_sha256
                    or str(existing[5]) != manifest.source_sha256
                ):
                    raise SnowflakeLoadError(
                        "Existing batch audit or persisted RAW rows conflict with local manifest"
                    )
                return LoadResult(
                    manifest.batch_id,
                    dataset,
                    False,
                    int(existing[1]),
                    str(existing[2]),
                )

            temporary = f"{self.database}.RAW.TMP_{spec['table']}_{uuid.uuid4().hex[:12].upper()}"
            columns = tuple(spec["columns"])
            expressions = tuple(spec["expressions"])
            governance = f"{self.database}.GOVERNANCE.BATCH_LOADS"
            connection.autocommit(False)
            cursor.execute("BEGIN")
            cursor.execute(
                f"""
                MERGE INTO {governance} target
                USING (SELECT %s BATCH_ID) source
                ON target.BATCH_ID=source.BATCH_ID
                WHEN NOT MATCHED THEN INSERT
                  (BATCH_ID, DATASET, ASSET_ID, SOURCE_KEY, SOURCE_SHA256,
                   EXPECTED_ROW_COUNT, ROW_COUNT, STATUS, STARTED_AT)
                VALUES (%s,%s,%s,%s,%s,%s,0,'RUNNING',CURRENT_TIMESTAMP())
                """,
                (
                    manifest.batch_id,
                    manifest.batch_id,
                    dataset,
                    manifest.asset_id,
                    s3_key,
                    manifest.source_sha256,
                    manifest.row_count,
                ),
            )
            cursor.execute(f"CREATE TEMP TABLE {temporary} LIKE {raw_table}")
            select_list = ",".join(expressions) + "," + ",".join(
                (
                    self._literal(manifest.batch_id),
                    self._literal(manifest.source_sha256),
                    "CURRENT_TIMESTAMP()",
                )
            )
            cursor.execute(
                f"""
                COPY INTO {temporary} ({','.join(columns)},BATCH_ID,SOURCE_SHA256,LOADED_AT)
                FROM (
                  SELECT {select_list}
                  FROM @{self.validated_stage}/{self._stage_path(s3_key)}
                )
                FILE_FORMAT=(FORMAT_NAME={self.database}.GOVERNANCE.CSV_V1)
                ON_ERROR='ABORT_STATEMENT'
                FORCE=FALSE
                """
            )
            cursor.execute(f"SELECT COUNT(*) FROM {temporary}")
            copied_rows = int(cursor.fetchone()[0])
            if copied_rows != manifest.row_count:
                raise SnowflakeLoadError(
                    f"COPY row count {copied_rows} does not match manifest {manifest.row_count}"
                )
            update_columns = [
                column for column in columns if column != str(spec["key"])
            ] + ["BATCH_ID", "SOURCE_SHA256", "LOADED_AT"]
            cursor.execute(
                f"""
                MERGE INTO {raw_table} target
                USING {temporary} source
                ON target.{spec['key']}=source.{spec['key']}
                WHEN MATCHED THEN UPDATE SET
                  {','.join(f'target.{column}=source.{column}' for column in update_columns)}
                WHEN NOT MATCHED THEN INSERT
                  ({','.join(columns)},BATCH_ID,SOURCE_SHA256,LOADED_AT)
                VALUES
                  ({','.join(f'source.{column}' for column in columns)},source.BATCH_ID,source.SOURCE_SHA256,source.LOADED_AT)
                """
            )
            cursor.execute(
                f"SELECT COUNT(*) FROM {raw_table} WHERE BATCH_ID=%s AND SOURCE_SHA256=%s",
                (manifest.batch_id, manifest.source_sha256),
            )
            persisted_rows = int(cursor.fetchone()[0])
            if persisted_rows != manifest.row_count:
                raise SnowflakeLoadError(
                    f"Persisted RAW row count {persisted_rows} does not match manifest {manifest.row_count}"
                )
            cursor.execute(
                f"""
                UPDATE {governance}
                SET STATUS='SUCCEEDED', ROW_COUNT=%s, COMPLETED_AT=CURRENT_TIMESTAMP()
                WHERE BATCH_ID=%s
                """,
                (persisted_rows, manifest.batch_id),
            )
            connection.commit()
            return LoadResult(
                manifest.batch_id,
                dataset,
                True,
                persisted_rows,
                manifest.source_sha256,
            )
        except Exception as exc:
            try:
                connection.rollback()
                cursor.execute(
                    f"""
                    MERGE INTO {self.database}.GOVERNANCE.BATCH_LOADS target
                    USING (SELECT %s BATCH_ID) source ON target.BATCH_ID=source.BATCH_ID
                    WHEN MATCHED THEN UPDATE SET STATUS='FAILED', ERROR_MESSAGE=%s,
                      COMPLETED_AT=CURRENT_TIMESTAMP()
                    """,
                    (manifest.batch_id, str(exc)[:1000]),
                )
                connection.commit()
            except Exception:
                connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def batch_evidence(self, manifest: BatchManifest) -> Mapping[str, object] | None:
        if manifest.dataset not in DATASETS:
            raise ValueError(f"Unsupported Snowflake dataset: {manifest.dataset}")
        spec = DATASETS[manifest.dataset]
        connection = self.connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                SELECT COUNT(raw.{spec['key']}), MIN(raw.SOURCE_SHA256), MAX(raw.SOURCE_SHA256)
                FROM {self.database}.GOVERNANCE.BATCH_LOADS loads
                INNER JOIN {self.database}.RAW.{spec['table']} raw
                  ON raw.BATCH_ID=loads.BATCH_ID
                WHERE loads.BATCH_ID=%s AND loads.STATUS='SUCCEEDED'
                HAVING COUNT(raw.{spec['key']}) > 0
                """,
                (manifest.batch_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            source_sha = str(row[1]) if row[1] == row[2] else "MULTIPLE_SOURCE_HASHES"
            return {"row_count": int(row[0]), "source_sha256": source_sha}
        finally:
            cursor.close()
            connection.close()

    def record_event(
        self, *, run_id: str, event_type: str, status: str, details: Mapping[str, object]
    ) -> None:
        connection = self.connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                INSERT INTO {self.database}.GOVERNANCE.PIPELINE_EVENTS
                  (EVENT_ID,RUN_ID,EVENT_TYPE,STATUS,EVENT_AT,ACTOR,DETAILS)
                SELECT %s,%s,%s,%s,CURRENT_TIMESTAMP(),CURRENT_USER(),PARSE_JSON(%s)
                """,
                (
                    f"event-{uuid.uuid4().hex[:16]}",
                    run_id,
                    event_type,
                    status,
                    json.dumps(details, sort_keys=True),
                ),
            )
            connection.commit()
        finally:
            cursor.close()
            connection.close()

    def record_reconciliation(self, *, run_id: str, result: Mapping[str, object]) -> None:
        connection = self.connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                INSERT INTO {self.database}.GOVERNANCE.RECONCILIATION_RESULTS
                  (RECONCILIATION_ID,RUN_ID,BATCH_ID,DATASET,EXPECTED_ROWS,ACTUAL_ROWS,
                   EXPECTED_SHA256,ACTUAL_SHA256,STATUS,DETAILS,RECONCILED_AT)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())
                """,
                (
                    f"recon-{uuid.uuid4().hex[:16]}",
                    run_id,
                    result["batch_id"],
                    result["dataset"],
                    result["expected_rows"],
                    result["actual_rows"],
                    result["expected_sha256"],
                    result["actual_sha256"],
                    result["status"],
                    result["details"],
                ),
            )
            connection.commit()
        finally:
            cursor.close()
            connection.close()

    def publish_lineage(self, edges: Sequence[Mapping[str, str]]) -> int:
        connection = self.connection_factory()
        cursor = connection.cursor()
        try:
            for edge in edges:
                cursor.execute(
                    f"""
                    MERGE INTO {self.database}.GOVERNANCE.LINEAGE_EDGES target
                    USING (SELECT %s EDGE_ID) source ON target.EDGE_ID=source.EDGE_ID
                    WHEN MATCHED THEN UPDATE SET UPSTREAM_ASSET_ID=%s,DOWNSTREAM_ASSET_ID=%s,
                      TRANSFORMATION_TYPE=%s,TRANSFORMATION_DESCRIPTION=%s,UPDATED_AT=CURRENT_TIMESTAMP()
                    WHEN NOT MATCHED THEN INSERT
                      (EDGE_ID,UPSTREAM_ASSET_ID,DOWNSTREAM_ASSET_ID,TRANSFORMATION_TYPE,
                       TRANSFORMATION_DESCRIPTION,UPDATED_AT)
                    VALUES (%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())
                    """,
                    (
                        edge["edge_id"],
                        edge["upstream_asset_id"],
                        edge["downstream_asset_id"],
                        edge["transformation_type"],
                        edge["transformation_description"],
                        edge["edge_id"],
                        edge["upstream_asset_id"],
                        edge["downstream_asset_id"],
                        edge["transformation_type"],
                        edge["transformation_description"],
                    ),
                )
            connection.commit()
            return len(edges)
        finally:
            cursor.close()
            connection.close()
