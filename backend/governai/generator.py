"""Deterministic, clearly simulated banking source generation."""

from __future__ import annotations

import csv
import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

CUSTOMER_FIELDS = ("customer_id", "full_name", "email", "phone", "state", "customer_since", "segment")
ACCOUNT_FIELDS = ("account_id", "customer_id", "opened_date", "account_status", "credit_limit")
TRANSACTION_FIELDS = ("transaction_id", "account_id", "transaction_ts", "amount", "merchant_category", "channel", "country_code", "is_fraud", "confirmed_loss")


@dataclass(frozen=True)
class GeneratedSources:
    base_dir: Path
    incident_file: Path
    hashes: dict[str, str]
    counts: dict[str, int]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def generate_sources(output_dir: Path, seed: int = 20270810, customer_count: int = 240, account_count: int = 320, transactions_per_month: int = 600) -> GeneratedSources:
    rng = random.Random(seed)
    base_dir, incident_dir = output_dir / "base", output_dir / "incident"
    states = ("PA", "NJ", "NY", "DE", "OH", "IL", "TX", "CA")
    segments = ("everyday", "premier", "student", "small_business")
    categories = ("grocery", "fuel", "dining", "travel", "retail", "utilities", "digital_goods")
    channels = ("card_present", "ecommerce", "digital_wallet")

    customers = []
    for index in range(1, customer_count + 1):
        customers.append({
            "customer_id": f"CUS-{index:05d}",
            "full_name": f"Synthetic Customer {index:05d}",
            "email": f"customer{index:05d}@example.test",
            "phone": f"+1-555-{100 + index // 100:03d}-{index % 10000:04d}",
            "state": states[(index - 1) % len(states)],
            "customer_since": (datetime(2017, 1, 1) + timedelta(days=rng.randint(0, 3200))).date().isoformat(),
            "segment": segments[(index - 1) % len(segments)],
        })

    accounts = []
    for index in range(1, account_count + 1):
        customer_index = ((index * 37) % customer_count) + 1
        accounts.append({
            "account_id": f"ACC-{index:05d}",
            "customer_id": f"CUS-{customer_index:05d}",
            "opened_date": (datetime(2019, 1, 1) + timedelta(days=rng.randint(0, 2400))).date().isoformat(),
            "account_status": "active" if index % 29 else "restricted",
            "credit_limit": f"{rng.choice((1500, 2500, 5000, 7500, 10000, 15000)):.2f}",
        })

    transactions = []
    number = 1
    for month_offset in range(6):
        start = datetime(2026, 2 + month_offset, 1, 9, 0, tzinfo=timezone.utc)
        for row_index in range(transactions_per_month):
            account_index = rng.randint(1, account_count)
            timestamp = start + timedelta(days=rng.randint(0, 26), hours=rng.randint(0, 14), minutes=rng.randint(0, 59))
            amount = round(max(1.0, rng.lognormvariate(3.65, .85)), 2)
            is_fraud = rng.random() < (.008 + month_offset * .0025)
            loss = round(amount * rng.uniform(.55, 1.0), 2) if is_fraud else 0.0
            transactions.append({
                "transaction_id": f"TXN-{number:08d}", "account_id": f"ACC-{account_index:05d}",
                "transaction_ts": timestamp.isoformat(), "amount": f"{amount:.2f}",
                "merchant_category": categories[(row_index + month_offset) % len(categories)],
                "channel": channels[(account_index + row_index) % len(channels)],
                "country_code": "US" if rng.random() < .94 else rng.choice(("CA", "GB", "IN")),
                "is_fraud": "1" if is_fraud else "0", "confirmed_loss": f"{loss:.2f}",
            })
            number += 1

    customer_file, account_file, transaction_file = base_dir / "customers.csv", base_dir / "accounts.csv", base_dir / "transactions.csv"
    counts = {
        "customers": write_csv(customer_file, CUSTOMER_FIELDS, customers),
        "accounts": write_csv(account_file, ACCOUNT_FIELDS, accounts),
        "transactions": write_csv(transaction_file, TRANSACTION_FIELDS, transactions),
    }

    incident = []
    start = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    for index in range(120):
        amount = round(max(1.0, rng.lognormvariate(3.7, .8)), 2)
        incident.append({
            "transaction_id": f"TXN-INC-{index + 1:05d}", "account_id": f"ACC-{(index * 17) % account_count + 1:05d}",
            "transaction_ts": (start + timedelta(minutes=index * 11)).isoformat(), "amount": f"{amount:.2f}",
            "merchant_category": categories[index % len(categories)], "channel": channels[index % len(channels)],
            "country_code": "US", "is_fraud": "0", "confirmed_loss": "0.00",
        })
    incident[17]["amount"] = "-842.19"
    incident[43]["account_id"] = "ACC-DOES-NOT-EXIST"
    incident[71]["transaction_ts"] = "2026-99-41 27:61"
    incident[119]["transaction_id"] = incident[0]["transaction_id"]
    incident_file = incident_dir / "transactions_corrupt.csv"
    counts["incident_transactions"] = write_csv(incident_file, TRANSACTION_FIELDS, incident)
    files = (customer_file, account_file, transaction_file, incident_file)
    return GeneratedSources(base_dir, incident_file, {str(p.relative_to(output_dir)): sha256_file(p) for p in files}, counts)
