from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from open_trajectory_evidence.audit import _local_identity_tokens, audit_repository


class AuditTests(unittest.TestCase):
    def test_clean_tree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "README.md").write_text("portable research\n", encoding="utf-8")
            self.assertEqual(audit_repository(repo), [])

    def test_home_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "report.md").write_text(
                "input lived under /" + "Users/example/private-data\n", encoding="utf-8"
            )
            errors = audit_repository(repo)
            self.assertTrue(any("home path" in error for error in errors), errors)

    def test_heavy_research_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "model.safetensors").write_bytes(b"not actually a model")
            errors = audit_repository(repo)
            self.assertTrue(any("heavyweight extension" in error for error in errors), errors)

    def test_secret_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "notes.txt").write_text(
                "credential=" + "sk-" + "examplecredential123456789\n", encoding="utf-8"
            )
            errors = audit_repository(repo)
            self.assertTrue(any("secret" in error for error in errors), errors)

    def test_local_identity_fails_without_persisting_the_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "report.md").write_text("private-person ran this\n", encoding="utf-8")
            with patch(
                "open_trajectory_evidence.audit._local_identity_tokens",
                return_value=[b"private-person"],
            ):
                errors = audit_repository(repo)
            self.assertTrue(any("local identity token" in error for error in errors), errors)

    def test_generic_ci_account_is_not_an_identity_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            with (
                patch(
                    "open_trajectory_evidence.audit.Path.home",
                    return_value=Path("/") / "home" / "runner",
                ),
                patch("open_trajectory_evidence.audit.getpass.getuser", return_value="runner"),
                patch("open_trajectory_evidence.audit.platform.node", return_value="runner"),
                patch(
                    "open_trajectory_evidence.audit.subprocess.run",
                    side_effect=subprocess.CalledProcessError(1, ["git", "config"]),
                ),
            ):
                self.assertEqual(_local_identity_tokens(repo), [])


if __name__ == "__main__":
    unittest.main()
