"""Bounded read-only execution of allowlisted banking evidence queries."""

from datetime import datetime
from pathlib import Path
import re

from app.sql.database import connect

AS_OF = datetime.fromisoformat("2026-10-01T00:00:00+08:00")
QUERIES = Path(__file__).parent / "queries"


class CustomerNotFound(ValueError):
    pass


class ReviewCapacityExceeded(ValueError):
    pass


def load_customer_evidence(customer_id):
    if not re.fullmatch(r"C[0-9]{3}", customer_id):
        raise ValueError("Customer ID must have the form C003")
    params = dict(customer_id=customer_id, as_of=AS_OF)
    with connect() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '5s'")
        customer = connection.execute((QUERIES / "review_customer.sql").read_text(), params).fetchone()
        if customer is None:
            raise CustomerNotFound("Customer not found")
        transactions = connection.execute((QUERIES / "review_transactions.sql").read_text(), params).fetchall()
        if len(transactions) > 200:
            raise ReviewCapacityExceeded("Review exceeds 200 transactions; refusing a partial analysis")
    return dict(customer=customer, transactions=transactions, as_of=AS_OF)
