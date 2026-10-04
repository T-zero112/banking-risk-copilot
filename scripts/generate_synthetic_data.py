"""Generate reproducible SGD fixtures and a PostgreSQL seed transaction."""

import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AS_OF = datetime.fromisoformat("2026-10-01T00:00:00+08:00")


def sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, Decimal)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def generate(seed=42):
    rng = random.Random(seed)
    tables = {name: [] for name in (
        "customers", "accounts", "transactions", "risk_scores", "alerts"
    )}
    for number in range(1, 21):
        customer_id = f"C{number:03}"
        account_id = f"A{number:03}"
        corporate = number % 5 == 0
        kyc = "incomplete" if number == 2 else "expired" if number == 3 else "complete"
        tables["customers"].append(dict(
            customer_id=customer_id, name=f"Synthetic {'Company' if corporate else 'Person'} {number:03}",
            customer_type="corporate" if corporate else "individual",
            nationality=None if corporate else "SG", occupation=None if corporate else "Engineer",
            risk_level="high" if number == 3 else "medium" if number == 2 else "low",
            kyc_status=kyc, onboarding_date="2025-01-01",
            kyc_last_review_date=None if kyc == "incomplete" else "2025-06-01" if kyc == "expired" else "2026-09-01",
            due_diligence_level="enhanced" if number == 3 else "standard",
        ))
        tables["accounts"].append(dict(
            account_id=account_id, customer_id=customer_id,
            account_type="business" if corporate else "savings",
            balance=Decimal("50000.00"), currency="SGD", status="active", opened_date="2025-01-01",
        ))
        tables["risk_scores"].append(dict(
            customer_id=customer_id, aml_risk_score=85 if number == 3 else 60 if number == 2 else 10,
            fraud_risk_score=10, credit_risk_score=15, score_date="2026-09-30",
        ))

        def transaction(timestamp, amount, kind="card_payment", country="SG"):
            # Counterparty identities and risk labels are explicitly synthetic.
            row = dict(
                transaction_id=f"T{len(tables['transactions']) + 1:05}", account_id=account_id,
                transaction_time=timestamp.isoformat(), amount=Decimal(amount), currency="SGD",
                transaction_type=kind, counterparty_name="Synthetic Counterparty",
                counterparty_account=f"SYNTH-{number:03}", counterparty_country=country,
                is_high_risk_country=False, high_risk_country_list_version="synthetic-demo-v1",
                channel="mobile", merchant_category="retail" if kind == "card_payment" else None,
            )
            tables["transactions"].append(row)
            return row["transaction_id"]

        count = 24 if number == 2 else 6
        for index in range(count):
            transaction(AS_OF - timedelta(days=index + 1, hours=1), f"{rng.randint(20, 500)}.00")
        if number == 1:
            transaction(AS_OF - timedelta(days=2), "25000.00", "transfer_in")
        if number == 3:
            related = transaction(AS_OF - timedelta(days=1, hours=2), "18000.00", "transfer_in", "MY")
            transaction(AS_OF - timedelta(days=1, hours=1), "17500.00", "transfer_out", "MY")
            tables["alerts"].append(dict(
                alert_id="AL001", customer_id=customer_id, alert_type="aml_review",
                severity="high", status="open",
                reason="Synthetic scenario: expired KYC and large inbound/outbound cross-border transfers one hour apart.",
                related_transaction_id=related, assigned_to=None,
                created_at=(AS_OF - timedelta(hours=12)).isoformat(), resolved_at=None,
            ))
        if number == 4:
            transaction(AS_OF - timedelta(days=31), "50000.00", "transfer_in")
        if number == 5:
            transaction(AS_OF, "50000.00", "transfer_in")
        if number == 6:
            transaction(AS_OF - timedelta(days=30), "10000.00", "transfer_in")
    return tables


def write_dataset(output, seed):
    tables = generate(seed)
    output.mkdir(parents=True, exist_ok=True)
    sql = ["BEGIN;"]
    for table, rows in tables.items():
        columns = list(rows[0])
        with (output / f"{table}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        values = ["(" + ", ".join(sql_literal(row[column]) for column in columns) + ")" for row in rows]
        sql.append(f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n" + ",\n".join(values) + ";")
    sql.append("COMMIT;")
    (output / "seed.sql").write_text("\n\n".join(sql) + "\n", encoding="utf-8")
    manifest = dict(
        seed=seed, as_of=AS_OF.isoformat(), currency="SGD",
        row_counts={table: len(rows) for table, rows in tables.items()},
        expected_high_value_customers=["C001", "C003", "C006"],
        expected_incomplete_kyc_active_customers=["C002"],
        review_customer="C003",
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "synthetic")
    args = parser.parse_args()
    write_dataset(args.output, args.seed)
