"""Small executable contracts with structured, auditable evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Sequence

from .generator import ACCOUNT_FIELDS, CUSTOMER_FIELDS, TRANSACTION_FIELDS


@dataclass(frozen=True)
class CheckResult:
    rule_id: str
    description: str
    severity: str
    passed: bool
    failed_rows: int
    observed_value: str
    expected_value: str


def result(rule_id: str, description: str, failures: int, expected: str) -> CheckResult:
    return CheckResult(
        rule_id, description, "critical", failures == 0, failures,
        f"{failures} failing rows", expected,
    )


def _text(row: Mapping[str, str], field: str) -> str:
    # DictReader returns None for short rows and a list under the None key for
    # surplus cells. Invalid shapes must become evidence, not parser exceptions.
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _batch_checks(
    prefix: str,
    rows: Sequence[Mapping[str, str]],
    fields: Sequence[str],
    columns: Sequence[str] | None,
) -> list[CheckResult]:
    expected = tuple(fields)
    malformed = sum(
        set(row) != set(expected)
        or any(not isinstance(row.get(field), str) for field in expected)
        for row in rows
    )
    # Snowflake's reviewed COPY expressions are positional. Header order is a
    # shared contract even though SQLite's loader uses names.
    headers_match = columns is None or tuple(columns) == expected
    schema_passed = headers_match and malformed == 0
    missing = sum(any(not _text(row, field).strip() for field in expected) for row in rows)
    return [
        CheckResult(
            f"{prefix}_batch_not_empty", "Batch contains at least one record", "critical",
            bool(rows), 0, f"{len(rows)} source rows", "At least 1 source row",
        ),
        CheckResult(
            f"{prefix}_schema_valid", "CSV uses the canonical schema and row shape", "critical",
            schema_passed, malformed if headers_match else len(rows),
            f"Canonical headers: {headers_match}; malformed rows: {malformed}",
            "Columns in order: " + ", ".join(expected),
        ),
        result(
            f"{prefix}_required_values", "Every required field has a value", missing,
            "0 rows with missing or blank required values",
        ),
    ]


def duplicates(rows: Sequence[Mapping[str, str]], key: str) -> int:
    values = [_text(row, key) for row in rows]
    return len(values) - len(set(values))


def _iso_date(value: str) -> bool:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat() == value
    except ValueError:
        return False


def _finite_number(row: Mapping[str, str], field: str) -> float | None:
    try:
        value = float(_text(row, field))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _synthetic_email(value: str) -> bool:
    local, separator, domain = value.partition("@")
    return bool(local and separator and domain.endswith(".test") and "@" not in domain
                and not any(character.isspace() for character in value))


def validate_customers(
    rows: Sequence[Mapping[str, str]], *, columns: Sequence[str] | None = None,
) -> list[CheckResult]:
    return [
        *_batch_checks("customer", rows, CUSTOMER_FIELDS, columns),
        result("customer_id_required", "Customer ID is present", sum(not _text(r, "customer_id").strip() for r in rows), "0 missing IDs"),
        result("customer_id_unique", "Customer ID is unique within the batch", duplicates(rows, "customer_id"), "0 duplicate IDs"),
        result("synthetic_email_domain", "Email uses the reserved synthetic .test domain", sum(not _synthetic_email(_text(r, "email")) for r in rows), "Nonempty local part and .test domain"),
        result("customer_since_valid", "Customer-since date uses ISO format", sum(not _iso_date(_text(r, "customer_since")) for r in rows), "YYYY-MM-DD"),
    ]


def validate_accounts(
    rows: Sequence[Mapping[str, str]], known_customers: Iterable[str], *,
    columns: Sequence[str] | None = None,
) -> list[CheckResult]:
    known = set(known_customers)
    bad_limits = 0
    for row in rows:
        limit = _finite_number(row, "credit_limit")
        bad_limits += limit is None or limit <= 0
    return [
        *_batch_checks("account", rows, ACCOUNT_FIELDS, columns),
        result("account_id_required", "Account ID is present", sum(not _text(r, "account_id").strip() for r in rows), "0 missing IDs"),
        result("account_id_unique", "Account ID is unique within the batch", duplicates(rows, "account_id"), "0 duplicate IDs"),
        result("account_customer_fk", "Every account references a known customer", sum(_text(r, "customer_id") not in known for r in rows), "0 orphan accounts"),
        result("credit_limit_positive", "Credit limit is a finite positive number", bad_limits, "Every credit_limit is finite and > 0"),
        result("account_opened_date_valid", "Account opened date uses ISO format", sum(not _iso_date(_text(r, "opened_date")) for r in rows), "YYYY-MM-DD"),
    ]


def validate_transactions(
    rows: Sequence[Mapping[str, str]], known_accounts: Iterable[str], *,
    columns: Sequence[str] | None = None,
) -> list[CheckResult]:
    known = set(known_accounts)
    bad_amounts = bad_timestamps = bad_losses = 0
    for row in rows:
        amount = _finite_number(row, "amount")
        loss = _finite_number(row, "confirmed_loss")
        bad_amounts += amount is None or amount <= 0
        try:
            datetime.fromisoformat(_text(row, "transaction_ts"))
        except ValueError:
            bad_timestamps += 1
        bad_losses += amount is None or loss is None or loss < 0 or loss > max(amount, 0)
    return [
        *_batch_checks("transaction", rows, TRANSACTION_FIELDS, columns),
        result("transaction_id_required", "Transaction ID is present", sum(not _text(r, "transaction_id").strip() for r in rows), "0 missing IDs"),
        result("transaction_id_unique", "Transaction ID is unique within the batch", duplicates(rows, "transaction_id"), "0 duplicate IDs"),
        result("transaction_amount_positive", "Transaction amount is finite and positive", bad_amounts, "Every amount is finite and > 0"),
        result("transaction_account_fk", "Every transaction references a known account", sum(_text(r, "account_id") not in known for r in rows), "0 orphan transactions"),
        result("transaction_timestamp_valid", "Transaction timestamp is ISO-8601", bad_timestamps, "Every timestamp parses as ISO-8601"),
        result("confirmed_loss_bounded", "Confirmed loss is finite and bounded by transaction amount", bad_losses, "Finite values with 0 <= confirmed_loss <= amount"),
        result("transaction_fraud_flag_binary", "Fraud flag is 0 or 1", sum(_text(r, "is_fraud") not in {"0", "1"} for r in rows), "Every is_fraud is 0 or 1"),
    ]


def has_critical_failure(checks: Sequence[CheckResult]) -> bool:
    return any(not check.passed and check.severity == "critical" for check in checks)
