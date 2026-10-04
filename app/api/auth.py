"""Local demo accounts and revocable opaque sessions, separate from bank evidence."""

import hashlib
from contextlib import contextmanager, closing
import hmac
from pathlib import Path
import secrets
import sqlite3
import time

AUTH_PATH = Path(__file__).resolve().parents[2] / "data/auth/accounts.sqlite3"
COOKIE = "banking_session"
SESSION_SECONDS = 2 * 60 * 60


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class AuthStore:
    def __init__(self, path=AUTH_PATH):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('admin','reviewer')),
                    salt TEXT NOT NULL, password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS assignments (
                    username TEXT REFERENCES users(username), customer_id TEXT NOT NULL,
                    PRIMARY KEY(username, customer_id)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, username TEXT REFERENCES users(username), expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS login_attempts (source TEXT PRIMARY KEY, failures INTEGER NOT NULL, reset_at REAL NOT NULL);
            """)

    def set_user(self, username, password, role, customers):
        import re
        if not re.fullmatch(r"[a-zA-Z0-9_-]{3,40}", username) or role not in {"admin", "reviewer"}:
            raise ValueError("Invalid username or role")
        if not 12 <= len(password) <= 256:
            raise ValueError("Password must contain 12-256 characters")
        if any(not re.fullmatch(r"C[0-9]{3}", customer) for customer in customers):
            raise ValueError("Invalid customer assignment")
        salt = secrets.token_hex(16)
        digest = password_hash(password, salt)
        with self.connect() as db:
            db.execute("INSERT INTO users VALUES (?,?,?,?,1) ON CONFLICT(username) DO UPDATE SET role=excluded.role, salt=excluded.salt, password_hash=excluded.password_hash, active=1",
                       (username, role, salt, digest))
            db.execute("DELETE FROM assignments WHERE username=?", (username,))
            db.executemany("INSERT INTO assignments VALUES (?,?)", [(username, customer) for customer in set(customers)])
            db.execute("DELETE FROM sessions WHERE username=?", (username,))

    def login(self, username, password, source):
        now = time.time()
        # Persist the source rate limit across server restarts and process workers.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            attempt = db.execute("SELECT * FROM login_attempts WHERE source=?", (source,)).fetchone()
            if attempt and attempt["reset_at"] > now and attempt["failures"] >= 10:
                return None, "login_throttled"
            user = db.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
            salt = user["salt"] if user else "00" * 16
            digest = password_hash(password, salt)
            valid = user is not None and hmac.compare_digest(digest, user["password_hash"])
            if not valid:
                count = attempt["failures"] + 1 if attempt and attempt["reset_at"] > now else 1
                reset = attempt["reset_at"] if attempt and attempt["reset_at"] > now else now + 900
                db.execute("INSERT INTO login_attempts VALUES (?,?,?) ON CONFLICT(source) DO UPDATE SET failures=excluded.failures, reset_at=excluded.reset_at", (source, count, reset))
                return None, "invalid_credentials"
            db.execute("DELETE FROM login_attempts WHERE source=?", (source,))
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), username, now + SESSION_SECONDS))
            return token, None

    def identity(self, token):
        if not token or len(token) > 100:
            return None
        with self.connect() as db:
            user = db.execute("SELECT u.username,u.role FROM sessions s JOIN users u ON u.username=s.username WHERE s.token_hash=? AND s.expires_at>? AND u.active=1",
                              (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
            if user is None:
                return None
            customers = [row[0] for row in db.execute("SELECT customer_id FROM assignments WHERE username=? ORDER BY customer_id", (user["username"],))]
            return dict(user, customers=customers)

    def logout(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


def can_access(identity, customer):
    return identity["role"] == "admin" or customer in identity["customers"]
