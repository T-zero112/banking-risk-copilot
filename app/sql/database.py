"""Local PostgreSQL connections shared by policy indexing and retrieval."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]


def connect(role="query"):
    load_dotenv(ROOT / ".env", override=False)
    keys = {"query": "QUERY_DATABASE_URL", "audit": "AUDIT_DATABASE_URL", "admin": "ADMIN_DATABASE_URL"}
    if role not in keys:
        raise ValueError("Unknown database connection role")
    url = os.environ.get(keys[role], "").strip()
    # Legacy DATABASE_URL is accepted only by explicitly requested maintenance connections.
    if role == "admin" and not url:
        url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise ValueError(f"Missing {keys[role]}; runtime connections never fall back to admin")
    dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        config = conninfo_to_dict(dsn)
    except psycopg.Error:
        raise ValueError(f"Invalid {keys[role]} connection configuration") from None
    expected = {"query": "banking_reader", "audit": "banking_audit"}
    if role in expected and config.get("user") != expected[role]:
        raise ValueError(f"{keys[role]} must use {expected[role]}, not a management account")
    return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)
