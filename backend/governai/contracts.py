"""Small executable contracts with structured, auditable evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Sequence


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


def duplicates(rows: Sequence[Mapping[str, str]], key: str) -> int:
    values = [row.get(key, "") for row in rows]
    return len(values) - len(set(values))


def validate_customers(rows: Sequence[Mapping[str, str]]) -> list[CheckResult]:
    bad_dates = 0
    for row in rows:
        try:
            datetime.strptime(row.get("customer_since", ""), "%Y-%m-%d")
        except ValueError:
            bad_dates += 1
    return [
        result("customer_id_required", "Customer ID is present", sum(not r.get("customer_id", "").strip() for r in rows), "0 missing IDs"),
        result("customer_id_unique", "Customer ID is unique within the batch", duplicates(rows, "customer_id"), "0 duplicate IDs"),
        result("synthetic_email_domain", "Email uses the reserved synthetic .test domain", sum("@" not in r.get("email", "") or not r.get("email", "").endswith(".test") for r in rows), "All values end in .test"),
        result("customer_since_valid", "Customer-since date uses ISO format", bad_dates, "YYYY-MM-DD"),
    ]


def validate_accounts(rows: Sequence[Mapping[str, str]], known_customers: Iterable[str]) -> list[CheckResult]:
    known = set(known_customers)
    bad_limits = 0
    for row in rows:
        try:
            bad_limits += float(row.get("credit_limit", "")) <= 0
        except ValueError:
            bad_limits += 1
    return [
        result("account_id_unique", "Account ID is unique within the batch", duplicates(rows, "account_id"), "0 duplicate IDs"),
        result("account_customer_fk", "Every account references a known customer", sum(r.get("customer_id") not in known for r in rows), "0 orphan accounts"),
        result("credit_limit_positive", "Credit limit is a positive number", bad_limits, "Every credit_limit > 0"),
    ]


def validate_transactions(rows: Sequence[Mapping[str, str]], known_accounts: Iterable[str]) -> list[CheckResult]:
    known = set(known_accounts)
    bad_amounts = bad_timestamps = bad_losses = 0
    for row in rows:
        try:
            bad_amounts += float(row.get("amount", "")) <= 0
        except ValueError:
            bad_amounts += 1
        try:
            datetime.fromisoformat(row.get("transaction_ts", ""))
        except ValueError:
            bad_timestamps += 1
        try:
            amount = float(row.get("amount", ""))
            loss = float(row.get("confirmed_loss", ""))
            bad_losses += loss < 0 or loss > max(amount, 0)
        except ValueError:
            bad_losses += 1
    return [
        result("transaction_id_unique", "Transaction ID is unique within the batch", duplicates(rows, "transaction_id"), "0 duplicate IDs"),
        result("transaction_amount_positive", "Transaction amount is positive", bad_amounts, "Every amount > 0"),
        result("transaction_account_fk", "Every transaction references a known account", sum(r.get("account_id") not in known for r in rows), "0 orphan transactions"),
        result("transaction_timestamp_valid", "Transaction timestamp is ISO-8601", bad_timestamps, "Every timestamp parses as ISO-8601"),
        result("confirmed_loss_bounded", "Confirmed loss is between zero and transaction amount", bad_losses, "0 <= confirmed_loss <= amount"),
    ]


def has_critical_failure(checks: Sequence[CheckResult]) -> bool:
    return any(not check.passed and check.severity == "critical" for check in checks)
