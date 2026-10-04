"""Run the three MVP queries on the Compose database and check fixtures."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def query(sql):
    command = [
        "docker", "compose", "exec", "-T", "db", "sh", "-c",
        'exec psql -X -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
    ]
    wrapped = "SELECT COALESCE(json_agg(result), '[]'::json)::text FROM (\n" + sql.rstrip().removesuffix(";") + "\n) result;"
    result = subprocess.run(command, cwd=ROOT, input=wrapped, text=True,
                            capture_output=True, check=True)
    return json.loads(result.stdout)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest = json.loads((ROOT / "data" / "synthetic" / "manifest.json").read_text(encoding="utf-8"))
    counts = {}
    for table in ("customers", "accounts", "transactions", "risk_scores", "alerts"):
        counts[table] = query(f"SELECT COUNT(*)::int AS count FROM {table}")[0]["count"]
    require(counts == manifest["row_counts"], f"Fixture counts differ: {counts}")
    extensions = query("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    require(len(extensions) == 1, "pgvector extension is missing")
    results = {}
    for name in ("high_value_customers", "incomplete_kyc_active", "customer_review_evidence"):
        sql = (ROOT / "app" / "sql" / "queries" / f"{name}.sql").read_text(encoding="utf-8")
        results[name] = query(sql)
    require([row["customer_id"] for row in results["high_value_customers"]]
            == manifest["expected_high_value_customers"], "High-value results differ")
    kyc = results["incomplete_kyc_active"]
    require([row["customer_id"] for row in kyc] == manifest["expected_incomplete_kyc_active_customers"],
            "Incomplete-KYC results differ")
    require(kyc[0]["transaction_count"] == 24, "Expected 24 transactions for C002")
    evidence = results["customer_review_evidence"]
    require(len(evidence) == 1, "Expected exactly one review customer")
    row = evidence[0]
    require(row["customer_id"] == manifest["review_customer"]
            and row["kyc_status"] == "expired" and row["aml_risk_score"] == 85
            and row["cross_border_count"] == 2 and row["unresolved_alert_count"] == 1,
            "Review evidence differs")
    print(json.dumps(dict(row_counts=counts, pgvector=extensions[0]["extversion"], results=results), indent=2))
    print("PASS: local PostgreSQL fixtures, pgvector, MVP queries, and time-window boundaries.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        raise SystemExit(1)
