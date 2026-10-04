"""Apply the additive audit migration without resetting any business data."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.sql.database import connect


if __name__ == "__main__":
    with connect("admin") as connection:
        connection.execute((ROOT / "app/sql/migrations/003_customer_review_audit.sql").read_text())
    print("Customer review audit migration applied")
