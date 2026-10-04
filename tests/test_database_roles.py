import unittest
from unittest.mock import patch

from app.sql.database import connect


class DatabaseRoleTests(unittest.TestCase):
    def test_runtime_config_never_falls_back_to_admin(self):
        for role in ("query", "audit"):
            with patch("app.sql.database.load_dotenv"), patch.dict("os.environ", {
                "DATABASE_URL": "postgresql://banking_owner:secret@localhost/banking_risk",
                "ADMIN_DATABASE_URL": "postgresql://banking_owner:secret@localhost/banking_risk",
            }, clear=True), patch("app.sql.database.psycopg.connect") as connector:
                with self.assertRaisesRegex(ValueError, "never fall back"):
                    connect(role)
                connector.assert_not_called()

    def test_runtime_url_rejects_owner(self):
        for role, key in (("query", "QUERY_DATABASE_URL"), ("audit", "AUDIT_DATABASE_URL")):
            with patch("app.sql.database.load_dotenv"), patch.dict("os.environ", {
                key: "postgresql://banking_owner:secret@localhost/banking_risk",
            }, clear=True), patch("app.sql.database.psycopg.connect") as connector:
                with self.assertRaises(ValueError) as caught:
                    connect(role)
                self.assertNotIn("secret", str(caught.exception))
                connector.assert_not_called()

    def test_role_specific_config_is_used(self):
        for role, key, user in (("query", "QUERY_DATABASE_URL", "banking_reader"),
                                ("audit", "AUDIT_DATABASE_URL", "banking_audit")):
            url = f"postgresql://{user}:test@localhost/banking_risk"
            with patch("app.sql.database.load_dotenv"), patch.dict("os.environ", {key: url}, clear=True), patch("app.sql.database.psycopg.connect") as connector:
                connect(role)
                self.assertEqual(connector.call_args.args[0], url)

    def test_only_explicit_admin_accepts_legacy_config(self):
        url = "postgresql+psycopg://banking_owner:test@localhost/banking_risk"
        with patch("app.sql.database.load_dotenv"), patch.dict("os.environ", {"DATABASE_URL": url}, clear=True), patch("app.sql.database.psycopg.connect") as connector:
            connect("admin")
            self.assertEqual(connector.call_args.args[0], url.replace("postgresql+psycopg", "postgresql"))

    def test_invalid_role_and_malformed_config_fail_safely(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            connect("invalid")
        with patch("app.sql.database.load_dotenv"), patch.dict("os.environ", {"QUERY_DATABASE_URL": "secret-invalid-dsn"}, clear=True):
            with self.assertRaises(ValueError) as caught:
                connect()
            self.assertNotIn("secret-invalid", str(caught.exception))
