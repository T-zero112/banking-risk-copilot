from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from app.api.auth import AuthStore, COOKIE
from app.api.main import create_app


class AuthTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.auth = AuthStore(Path(temporary.name) / "auth.sqlite3")
        self.auth.initialize()
        for username, role, customers in (("admin", "admin", []), ("alice", "reviewer", ["C003"]), ("bob", "reviewer", ["C004"])):
            self.auth.set_user(username, "test-password-123", role, customers)
        self.id = str(uuid4())
        self.runner = MagicMock(return_value={"request_id":self.id, "audit":{"status":"succeeded"}})
        self.store = MagicMock()
        self.store.read.return_value = dict(request_id=self.id, customer_id="C004", review_mode="deterministic", review_status="succeeded",
            created_at=datetime.now(timezone.utc), finished_at=None, elapsed_ms=1, sql_execution_status="succeeded",
            error_message=None, review_metadata={"secret_evidence":"not-for-alice"}, retrieved_policy_refs=[], final_answer={"secret":"not-for-alice"})
        self.client = TestClient(create_app(self.runner, self.store, self.auth))

    def login(self, username="alice"):
        return self.client.post("/auth/login", json={"username":username, "password":"test-password-123"})

    def test_anonymous_blocked_before_evidence_access(self):
        self.assertEqual(self.client.post("/reviews", json={"customer_id":"C003"}).status_code, 401)
        self.assertEqual(self.client.get(f"/reviews/{self.id}").status_code, 401)
        self.runner.assert_not_called()
        self.store.read.assert_not_called()

    def test_customer_scope_and_actor(self):
        self.login()
        self.assertEqual(self.client.post("/reviews", json={"customer_id":"C004"}).status_code, 403)
        self.runner.assert_not_called()
        self.assertEqual(self.client.post("/reviews", json={"customer_id":"C003"}).status_code, 201)
        self.runner.assert_called_once_with("C003", "deterministic", actor={"username":"alice", "role":"reviewer"})
        response = self.client.get(f"/reviews/{self.id}")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("not-for-alice", response.text)

    def test_admin_can_access_all(self):
        self.login("admin")
        self.assertEqual(self.client.post("/reviews", json={"customer_id":"C004"}).status_code, 201)
        self.assertEqual(self.client.get(f"/reviews/{self.id}").status_code, 200)

    def test_second_reviewer_can_read_assigned_customer(self):
        self.login("bob")
        self.assertEqual(self.client.get(f"/reviews/{self.id}").status_code, 200)
        self.assertEqual(self.client.post("/reviews", json={"customer_id":"C003"}).status_code, 403)

    def test_logout_expiry_and_password_rotation_revoke_session(self):
        self.login()
        token = self.client.cookies.get(COOKIE)
        self.assertEqual(self.client.post("/auth/logout").status_code, 200)
        self.client.cookies.set(COOKIE, token)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.client.cookies.clear()
        self.login()
        with self.auth.connect() as db:
            db.execute("UPDATE sessions SET expires_at=0")
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.login()
        self.auth.set_user("alice", "replacement-password-123", "reviewer", ["C003"])
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_live_assignment_revocation(self):
        self.login()
        with self.auth.connect() as db:
            db.execute("DELETE FROM assignments WHERE username='alice'")
        self.assertEqual(self.client.post("/reviews", json={"customer_id":"C003"}).status_code, 403)
        self.runner.assert_not_called()

    def test_cookie_and_hash_storage(self):
        response = self.login()
        header = response.headers["set-cookie"].lower()
        self.assertIn("httponly", header)
        self.assertIn("samesite=strict", header)
        with self.auth.connect() as db:
            user = dict(db.execute("SELECT * FROM users WHERE username='alice'").fetchone())
            session = dict(db.execute("SELECT * FROM sessions").fetchone())
        self.assertNotIn("test-password-123", str(user))
        self.assertNotEqual(session["token_hash"], self.client.cookies.get(COOKIE))

    def test_bad_login_throttled_and_errors_sanitized(self):
        for _ in range(10):
            response = self.client.post("/auth/login", json={"username":"alice", "password":"wrong-secret"})
            self.assertEqual(response.status_code, 401)
            self.assertNotIn("wrong-secret", response.text)
        self.assertEqual(self.login().status_code, 429)

    def test_paid_consent_not_implied_by_login(self):
        self.login()
        self.assertEqual(self.client.post("/reviews", json={"customer_id":"C003", "mode":"deepseek"}).status_code, 422)
        self.runner.assert_not_called()
        self.assertEqual(self.client.post("/reviews", json={"customer_id":"C003", "mode":"deepseek", "paid_consent":"true"}).status_code, 422)

    def test_revocation_while_review_runs_blocks_response(self):
        self.login()
        def revoke(*args, **kwargs):
            with self.auth.connect() as db:
                db.execute("DELETE FROM assignments WHERE username='alice'")
            return {"request_id":self.id, "audit":{"status":"succeeded"}}
        self.runner.side_effect = revoke
        response = self.client.post("/reviews", json={"customer_id":"C003"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("report", response.json())

    def test_forged_identity_and_cross_site_denied(self):
        self.login()
        self.assertEqual(self.client.post("/reviews", json={"customer_id":"C004", "role":"admin"}).status_code, 422)
        response = self.client.post("/auth/logout", headers={"Origin":"https://evil.example"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/auth/me").status_code, 200)

    def test_missing_auth_database_fails_closed(self):
        client = TestClient(create_app(self.runner, self.store, AuthStore(self.auth.path.parent / "missing.sqlite3")))
        self.assertEqual(client.post("/reviews", json={"customer_id":"C003"}).status_code, 401)
        client.cookies.set(COOKIE, "unverified-token")
        self.assertEqual(client.post("/reviews", json={"customer_id":"C003"}).status_code, 503)
        self.runner.assert_not_called()
