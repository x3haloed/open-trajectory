from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes, sha256_file
from open_trajectory_harness.ot0003 import read_sealed_json
from open_trajectory_harness.ot0073 import (
    ACCEPTANCE_PATH,
    ACCEPTANCE_SHA256,
    EXPERIMENT_PATH,
    EXPERIMENT_SHA256,
    PROTOCOL_ORIGIN_COMMIT,
    RAW_RELATIVE_PATH,
    build_raw,
    build_receipt,
    build_task,
    derive,
    ensure_derivation,
    protocol_frozen_paths,
    validate_acceptance,
    verify_fresh_root,
)


class OT0073Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path(__file__).resolve().parents[1]
        cls.implementation = "0" * 40

    def test_protocol_and_scientific_dependency_hashes_are_exact(self) -> None:
        acceptance, scientific = validate_acceptance(self.repo)
        self.assertEqual(sha256_file(self.repo / ACCEPTANCE_PATH), ACCEPTANCE_SHA256)
        self.assertEqual(sha256_file(self.repo / EXPERIMENT_PATH), EXPERIMENT_SHA256)
        self.assertEqual(scientific["experiment_id"], "OT-0071")
        for name in ("acceptance", "harness", "reset_worker"):
            path = self.repo / acceptance["scientific_protocol"][f"{name}_path"]
            self.assertEqual(
                sha256_file(path),
                acceptance["scientific_protocol"][f"{name}_sha256"],
            )

    def test_neutral_receipt_has_no_authority_or_attempt_field(self) -> None:
        task = build_task(self.implementation)
        receipt = build_receipt(self.implementation, canonical_json(task))
        self.assertEqual(
            set(receipt),
            {
                "schema_version",
                "experiment_id",
                "derivation_id",
                "implementation_git_commit",
                "task_path",
                "task_sha256",
                "task_bytes",
            },
        )
        encoded = canonical_json(receipt).lower()
        self.assertNotIn(b"authoritative", encoded)
        self.assertNotIn(b"attempt", encoded)

    def test_empty_roots_regenerate_byte_identical_task_and_receipt(self) -> None:
        artifacts = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as root:
                with mock.patch.dict(os.environ, {"OT_EVIDENCE_ROOT": root}):
                    derive(self.repo, self.implementation)
                    task, task_bytes = read_sealed_json(
                        Path(root) / "tasks/OT-0073/ot-0073-derivation-001.json"
                    )
                    receipt, receipt_bytes = read_sealed_json(
                        Path(root)
                        / "derivations/OT-0073/ot-0073-derivation-001.json"
                    )
                    artifacts.append((task_bytes, receipt_bytes))
                    self.assertEqual(
                        receipt,
                        build_receipt(self.implementation, task_bytes),
                    )
                    self.assertEqual(task, build_task(self.implementation))
        self.assertEqual(artifacts[0], artifacts[1])

    def test_regeneration_fails_closed_on_half_present_derivation(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            task = build_task(self.implementation)
            path = Path(root) / "tasks/OT-0073/ot-0073-derivation-001.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(canonical_json(task))
            with mock.patch.dict(os.environ, {"OT_EVIDENCE_ROOT": root}):
                with self.assertRaises(ValueError):
                    ensure_derivation(
                        self.repo,
                        self.implementation,
                        allow_regeneration=True,
                    )

    def test_invalid_science_cannot_receive_public_authority(self) -> None:
        raw = build_raw(
            self.implementation,
            "1" * 40,
            {
                "experiment_id": "OT-0071",
                "calibration_pass": False,
                "disposition": "invalidated",
            },
            {"status": "passed", "returncode": 0},
            {"status": "passed", "returncode": 0},
            True,
        )
        self.assertEqual(raw["evidence_class"], "exploratory-only")
        self.assertEqual(raw["summary"]["authorized_candidate_count"], 0)

    def test_fresh_root_gate_compares_complete_raw_bytes(self) -> None:
        authoritative = canonical_json({"artifact": "authoritative"})
        with tempfile.TemporaryDirectory() as root:
            authoritative_path = Path(root) / "raw.json"
            authoritative_path.write_bytes(authoritative)

            def reconstruct(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
                del command
                environment = kwargs["env"]
                assert isinstance(environment, dict)
                target = Path(environment["OT_EVIDENCE_ROOT"]) / RAW_RELATIVE_PATH
                target.parent.mkdir(parents=True)
                target.write_bytes(authoritative)
                return subprocess.CompletedProcess([], 0, b"", b"")

            with mock.patch("open_trajectory_harness.ot0073.subprocess.run", side_effect=reconstruct):
                result = verify_fresh_root(self.repo, authoritative_path)
        self.assertTrue(result["pass"])
        self.assertEqual(result["bytes"], len(authoritative))
        self.assertEqual(result["sha256"], sha256_bytes(authoritative))

    def test_protocol_paths_are_unchanged_from_p(self) -> None:
        acceptance = load_json(self.repo / ACCEPTANCE_PATH)
        self.assertEqual(
            protocol_frozen_paths(self.repo),
            tuple(Path(item) for item in acceptance["lock"]["protocol_frozen_paths"]),
        )
        for path in protocol_frozen_paths(self.repo):
            frozen = subprocess.run(
                ["git", "show", f"{PROTOCOL_ORIGIN_COMMIT}:{path.as_posix()}"],
                cwd=self.repo,
                check=True,
                capture_output=True,
            ).stdout
            self.assertEqual(sha256_file(self.repo / path), sha256_bytes(frozen))


if __name__ == "__main__":
    unittest.main()
