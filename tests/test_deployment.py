import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from dotenv import dotenv_values
from scripts import start_project
from scripts.check_release import forbidden


class DeploymentTests(unittest.TestCase):
    def test_release_guard_rejects_private_files(self):
        for path in (".env", "nested/.env.local", "data/auth/accounts.sqlite3", "data/deployment-check/a/result.json", "data/evaluations/live-results.json", "data/runtime/api.log", "../.env"):
            self.assertTrue(forbidden(path), path)
        for path in (".env.example", "README.md", "app/api/auth.py", "requirements-lock.txt"):
            self.assertFalse(forbidden(path), path)

    def test_docker_failure_has_safe_actionable_message(self):
        import subprocess
        with patch.object(start_project, "check_dependencies"), patch.object(start_project, "configuration"), \
             patch.object(start_project.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "docker", stderr="private-test")), \
             patch.object(start_project.sys, "argv", ["start_project.py", "--check-only"]):
            with self.assertRaises(start_project.StartupError) as caught:
                start_project.main()
        self.assertIn("Docker engine unavailable", str(caught.exception))
        self.assertNotIn("private-test", str(caught.exception))

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.patch = patch.object(start_project, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.root / ".env.example").write_text("POSTGRES_PORT=55432\nPOSTGRES_PASSWORD=example\nADMIN_DATABASE_URL=example\nDEEPSEEK_API_KEY=\n")

    def test_daily_start_never_creates_missing_configuration(self):
        with self.assertRaises(start_project.StartupError):
            start_project.configuration(False)
        self.assertFalse((self.root / ".env").exists())

    def test_fresh_configuration_has_random_owner_and_no_provider_key(self):
        with patch.dict(os.environ, {}, clear=True):
            start_project.configuration(True, 55991)
        values = dotenv_values(self.root / ".env")
        self.assertNotEqual(values["POSTGRES_PASSWORD"], "example")
        self.assertEqual(values["POSTGRES_PORT"], "55991")
        self.assertEqual(values["DEEPSEEK_API_KEY"], "")

    def test_existing_configuration_preserved_and_conflicting_port_denied(self):
        path = self.root / ".env"
        path.write_text("POSTGRES_PORT=55432\nADMIN_DATABASE_URL=existing\nDEEPSEEK_API_KEY=private-test\n")
        before = path.read_bytes()
        with patch.dict(os.environ, {}, clear=True):
            start_project.configuration(True)
            with self.assertRaises(start_project.StartupError):
                start_project.configuration(True, 55991)
        self.assertEqual(path.read_bytes(), before)

    def test_lock_mismatch_fails_without_installing_anything(self):
        (self.root / "requirements-lock.txt").write_text("fastapi==0.0.0\n")
        with patch.object(start_project.importlib.metadata, "version", return_value="1.0.0"):
            with self.assertRaises(start_project.StartupError):
                start_project.check_dependencies()
