from __future__ import annotations

import hashlib
import inspect
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0070 import (
    ACCEPTANCE_PATH,
    CASE_INDICES,
    DEFAULT_RUN_ID,
    DISTRACTOR_COUNT,
    MAXIMUM_RAW_ARTIFACT_BYTES,
    MINIMUM_FULL_TRAJECTORY_BYTES,
    PROJECTION_BYTE_LIMIT,
    RECONSTRUCTION_RECIPE,
    PointerController,
    _bounded_calibration,
    _bounded_command,
    _calibration_failure_summary,
    _quarantine_failed_publication,
    _reset_operational_failure,
    _validate_acceptance,
    assemble_calibration_result,
    build_fixture_history,
    build_raw_artifact,
    consumer_output,
    evaluate_case,
    expected_manifest_path,
    expected_output_path,
    fixed_input_paths,
    opaque_token,
    reconstruct,
    run_calibration,
    validate_output_contract,
    validate_run_lock,
)
from open_trajectory_harness.trajectory import TrajectoryStore


PASSED_TESTS = {"status": "passed", "returncode": 0, "within_bound": True}
PASSED_AUDIT = {"status": "passed", "returncode": 0, "within_bound": True}


def _assert_no_floats(test: unittest.TestCase, value: object) -> None:
    if type(value) is dict:
        for key, child in value.items():
            test.assertNotIn(
                key,
                {
                    "maximum_reset_seconds",
                    "calibration_wall_seconds",
                    "complete_run_wall_seconds",
                    "stdout_sha256",
                    "stderr_sha256",
                },
            )
            _assert_no_floats(test, child)
    elif type(value) is list:
        for child in value:
            _assert_no_floats(test, child)
    else:
        test.assertIsNot(type(value), float)


class OT0070Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path(__file__).resolve().parents[1]
        cls.acceptance = load_json(cls.repo / ACCEPTANCE_PATH)
        cls.result = evaluate_case(0, repo=cls.repo)

    def _complete_runs(self) -> list[dict[str, object]]:
        normalized = [
            {"case_index": index, "role": "fixture", "result": {"pass": True}}
            for index in CASE_INDICES
        ]
        normalized_sha256 = sha256_bytes(canonical_json(normalized))
        runs = []
        for label in self.acceptance["run_order"]:
            order = (
                self.acceptance["forward_case_order"]
                if label.startswith("forward")
                else self.acceptance["reverse_case_order"]
            )
            runs.append(
                {
                    "run": label,
                    "case_order": list(order),
                    "passing_case_count": len(CASE_INDICES),
                    "case_receipts": [
                        [index, sha256_bytes(f"case:{index}".encode())]
                        for index in sorted(order)
                    ],
                    "normalized": normalized,
                    "normalized_sha256": normalized_sha256,
                    "reset_within_bound": True,
                    "operational_failures": [],
                }
            )
        return runs

    def test_exact_fixture_derivation_and_all_sixteen_cases_exist(self) -> None:
        expected = hashlib.sha256(b"ot-0070:0:case:0").hexdigest()[:16]
        self.assertEqual(opaque_token(0, "case", 0), expected)
        self.assertEqual(CASE_INDICES, tuple(range(16)))
        for case_index in CASE_INDICES:
            history = build_fixture_history(case_index)
            self.assertEqual(len(history.ids["distractors"]), DISTRACTOR_COUNT)

    def test_complete_causal_slice_passes_with_real_fresh_reset(self) -> None:
        result = self.result
        self.assertTrue(result["pass"])
        self.assertGreaterEqual(
            result["full_trajectory_bytes"], MINIMUM_FULL_TRAJECTORY_BYTES
        )
        self.assertLessEqual(result["projection_bytes"], PROJECTION_BYTE_LIMIT)
        self.assertEqual(result["distractor_count"], 16)
        self.assertEqual(
            result["pointer_replay"],
            {
                "sequences": [0, 1, 2, 3],
                "active_roles": [
                    "active_parent",
                    "active_parent",
                    "proposal",
                    "active_parent",
                ],
                "actions": ["initialize", "set_down", "adopt", "rollback"],
            },
        )
        self.assertEqual(result["reset"]["status"], "passed")
        self.assertTrue(result["reset"]["within_bound"])
        self.assertTrue(result["reset"]["workspace_empty_before"])
        self.assertTrue(result["reset"]["workspace_empty_after"])
        self.assertFalse(result["reset"]["external_parent_lookup"])
        self.assertFalse(result["reset"]["unrelated_lookup"])
        _assert_no_floats(self, result)

    def test_binding_provenance_and_pointer_failures_preserve_authority(self) -> None:
        self.assertTrue(all(self.result["decision_controls"].values()))
        self.assertTrue(all(self.result["provenance_controls"].values()))
        self.assertTrue(all(self.result["pointer_controls"].values()))
        self.assertTrue(self.result["pointer_controls"]["no_direct_write_api"])

        public_controller_api = {
            name
            for name, member in inspect.getmembers(PointerController)
            if not name.startswith("_") and callable(member)
        }
        self.assertEqual(public_controller_api, {"initialize", "apply", "replay"})
        for name in ("set_active", "active", "inject", "append_pointer"):
            self.assertFalse(hasattr(PointerController, name))
        for name in ("actor_channel", "world_channel", "controller_channel"):
            self.assertFalse(hasattr(TrajectoryStore, name))

        history = build_fixture_history(0, include_distractors=False)
        actor_capability = history._actor._capability
        world_capability = history._world._capability
        controller_capability = history.controller._capability
        self.assertEqual(
            len({id(actor_capability), id(world_capability), id(controller_capability)}),
            3,
        )
        self.assertIs(history._actor_interventions._capability, actor_capability)
        self.assertIs(history._world_interventions._capability, world_capability)
        self.assertIs(
            history._controller_interventions._capability,
            controller_capability,
        )

    def test_quality_is_not_protocol_authority(self) -> None:
        placebo = self.result["quality_placebo"]
        self.assertTrue(placebo["pass"])
        self.assertTrue(placebo["same_protocol_verdict"])
        self.assertEqual(
            placebo["matching_protocol"], placebo["nonmatching_protocol"]
        )
        self.assertEqual(placebo["matching_row_count"], 3)
        self.assertEqual(placebo["nonmatching_row_count"], 0)
        self.assertTrue(placebo["distinct_trial_identities"])
        self.assertTrue(placebo["effective_intervention"])

    def test_alpha_and_append_order_are_structural_placebos(self) -> None:
        self.assertTrue(self.result["alpha_placebo"])
        self.assertTrue(self.result["order_placebo"])
        self.assertNotEqual(
            opaque_token(0, "case", 0), opaque_token(0, "case", 0, alpha=True)
        )

    def test_consumer_call_path_cannot_read_trials_or_replay_state(self) -> None:
        source = inspect.getsource(consumer_output).lower()
        self.assertNotIn("trial", source)
        self.assertNotIn("replay_pointer", consumer_output.__code__.co_names)
        self.assertTrue(self.result["consumer_trial_unreachable"])

    def test_incomplete_and_overbudget_projection_interventions_fail(self) -> None:
        projection = self.result["projection"]
        self.assertTrue(projection["proposal_exclusion_rejected"])
        self.assertTrue(projection["trial_exclusion_rejected"])
        self.assertTrue(projection["overbudget_rejected"])
        self.assertEqual(projection["external_parent_count"], 1)

    def test_acceptance_and_every_runtime_authority_are_explicit(self) -> None:
        _validate_acceptance(self.acceptance)
        fixed = fixed_input_paths(self.repo)
        required = {
            "acceptance_spec_sha256",
            "experiment_record_sha256",
            "evaluation_epoch_sha256",
            "program_sha256",
            "target_sha256",
            "red_lines_sha256",
            "evidence_contract_sha256",
            "workflow_contract_sha256",
            "trajectory_core_sha256",
            "procedural_harness_sha256",
            "reset_worker_sha256",
            "entrypoint_sha256",
            "canonical_helper_sha256",
            "sealed_helper_sha256",
            "dependency_lock_sha256",
            "evidence_recorder_sha256",
            "evidence_audit_sha256",
            "evidence_cli_sha256",
        }
        self.assertLessEqual(required, set(fixed))
        expected_tests = {
            path.relative_to(self.repo)
            for path in (self.repo / "tests").glob("test_*.py")
        }
        self.assertLessEqual(expected_tests, set(fixed.values()))
        self.assertTrue(all((self.repo / path).is_file() for path in fixed.values()))

    def test_complete_raw_artifact_is_byte_deterministic(self) -> None:
        first_summary = assemble_calibration_result(
            self.acceptance, self._complete_runs(), wall_within_bound=True
        )
        second_summary = assemble_calibration_result(
            self.acceptance, self._complete_runs(), wall_within_bound=True
        )
        first = build_raw_artifact(
            run_id=DEFAULT_RUN_ID,
            implementation_commit="a" * 40,
            execution_commit="b" * 40,
            summary=first_summary,
            tests=PASSED_TESTS,
            audit=PASSED_AUDIT,
            complete_run_within_bound=True,
        )
        second = build_raw_artifact(
            run_id=DEFAULT_RUN_ID,
            implementation_commit="a" * 40,
            execution_commit="b" * 40,
            summary=second_summary,
            tests=dict(PASSED_TESTS),
            audit=dict(PASSED_AUDIT),
            complete_run_within_bound=True,
        )
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(first["evidence_class"], "public-reconstructible")
        self.assertEqual(first["summary"]["disposition"], "promoted")
        self.assertEqual(first["raw_artifact_bytes"], len(canonical_json(first)))
        _assert_no_floats(self, first)

    def test_operational_failures_have_compact_allowlisted_artifacts(self) -> None:
        reset_summary = _calibration_failure_summary(
            self.acceptance, "reset_timeout", wall_within_bound=True
        )
        reset_raw = build_raw_artifact(
            run_id=DEFAULT_RUN_ID,
            implementation_commit="a" * 40,
            execution_commit="b" * 40,
            summary=reset_summary,
            tests=PASSED_TESTS,
            audit=PASSED_AUDIT,
            complete_run_within_bound=True,
        )
        self.assertEqual(reset_raw["evidence_class"], "exploratory-only")
        self.assertEqual(reset_raw["summary"]["disposition"], "invalidated")
        self.assertEqual(reset_raw["summary"]["operational_failure"], "reset_timeout")
        self.assertFalse(reset_raw["summary"]["partial_results_retained"])
        self.assertEqual(reset_raw["summary"]["runs"], [])

        complete = assemble_calibration_result(
            self.acceptance, self._complete_runs(), wall_within_bound=True
        )
        tests_timeout = {
            "status": "tests_timeout",
            "returncode": None,
            "within_bound": False,
        }
        tests_raw = build_raw_artifact(
            run_id=DEFAULT_RUN_ID,
            implementation_commit="a" * 40,
            execution_commit="b" * 40,
            summary=complete,
            tests=tests_timeout,
            audit=PASSED_AUDIT,
            complete_run_within_bound=False,
        )
        self.assertEqual(
            tests_raw["summary"]["operational_failure"], "tests_timeout"
        )
        self.assertEqual(tests_raw["summary"]["case_evaluation_count"], 0)
        self.assertEqual(tests_raw["summary"]["runs"], [])
        _assert_no_floats(self, reset_raw)
        _assert_no_floats(self, tests_raw)

    def test_overbudget_raw_is_replaced_by_artifact_size_invalidation(self) -> None:
        summary = assemble_calibration_result(
            self.acceptance, self._complete_runs(), wall_within_bound=True
        )
        summary["padding"] = "x" * (MAXIMUM_RAW_ARTIFACT_BYTES + 1)
        raw = build_raw_artifact(
            run_id=DEFAULT_RUN_ID,
            implementation_commit="a" * 40,
            execution_commit="b" * 40,
            summary=summary,
            tests=PASSED_TESTS,
            audit=PASSED_AUDIT,
            complete_run_within_bound=True,
        )
        self.assertEqual(raw["summary"]["operational_failure"], "artifact_size")
        self.assertFalse(raw["summary"]["gates"]["artifact_size"])
        self.assertEqual(raw["evidence_class"], "exploratory-only")
        self.assertNotIn("padding", raw["summary"])
        self.assertLessEqual(raw["raw_artifact_bytes"], MAXIMUM_RAW_ARTIFACT_BYTES)

    def test_bounded_commands_emit_only_stable_stage_receipts(self) -> None:
        completed = subprocess.CompletedProcess(["command"], 0, "timing text", "")
        with patch(
            "open_trajectory_harness.ot0070.time.monotonic", return_value=0.0
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run", return_value=completed
        ):
            passed = _bounded_command(
                ["command"], self.repo, 1.0, stage="tests"
            )
        self.assertEqual(passed, PASSED_TESTS)

        failed_process = subprocess.CompletedProcess(["command"], 7, "private", "")
        with patch(
            "open_trajectory_harness.ot0070.time.monotonic", return_value=0.0
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run",
            return_value=failed_process,
        ):
            failed = _bounded_command(
                ["command"], self.repo, 1.0, stage="tests"
            )
        self.assertEqual(
            failed,
            {"status": "tests_failed", "returncode": 7, "within_bound": True},
        )

        with patch(
            "open_trajectory_harness.ot0070.time.monotonic", return_value=0.0
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["command"], 1.0),
        ):
            timed_out = _bounded_command(
                ["command"], self.repo, 1.0, stage="audit"
            )
        self.assertEqual(
            timed_out,
            {"status": "audit_timeout", "returncode": None, "within_bound": False},
        )
        self.assertNotIn("stdout", passed)
        self.assertNotIn("stderr", failed)

    def test_calibration_watchdog_discards_timeout_and_malformed_output(self) -> None:
        complete = assemble_calibration_result(
            self.acceptance, self._complete_runs(), wall_within_bound=True
        )
        process = subprocess.CompletedProcess(
            ["worker"], 0, canonical_json(complete), b""
        )
        with patch(
            "open_trajectory_harness.ot0070.time.monotonic", return_value=0.0
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run", return_value=process
        ):
            observed = _bounded_calibration(self.repo, self.acceptance, 1.0)
        self.assertEqual(observed, complete)

        with patch(
            "open_trajectory_harness.ot0070.time.monotonic", return_value=0.0
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["worker"], 1.0),
        ):
            timed_out = _bounded_calibration(self.repo, self.acceptance, 1.0)
        self.assertEqual(timed_out["operational_failure"], "calibration_timeout")
        self.assertEqual(timed_out["runs"], [])

        malformed_process = subprocess.CompletedProcess(
            ["worker"], 0, b"not-json", b""
        )
        with patch(
            "open_trajectory_harness.ot0070.time.monotonic", return_value=0.0
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run",
            return_value=malformed_process,
        ):
            malformed = _bounded_calibration(self.repo, self.acceptance, 1.0)
        self.assertEqual(malformed["operational_failure"], "calibration_failed")
        self.assertEqual(malformed["runs"], [])

    def test_reset_failures_map_to_stable_public_codes(self) -> None:
        self.assertIsNone(
            _reset_operational_failure({"status": "passed", "within_bound": True})
        )
        self.assertEqual(
            _reset_operational_failure({"status": "timeout", "within_bound": False}),
            "reset_timeout",
        )
        self.assertEqual(
            _reset_operational_failure({"status": "rejected", "within_bound": True}),
            "calibration_failed",
        )
        self.assertEqual(
            _reset_operational_failure({"status": "passed", "within_bound": False}),
            "reset_timeout",
        )

    def test_output_contract_enforces_exact_location_and_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            evidence_root = repo / ".evidence"
            with patch.dict(
                os.environ, {"OT_EVIDENCE_ROOT": str(evidence_root)}, clear=False
            ):
                output = expected_output_path(repo)
                contract = validate_output_contract(repo, DEFAULT_RUN_ID, output)
                self.assertEqual(contract["output"], output)
                self.assertEqual(contract["manifest"], expected_manifest_path(repo))
                with self.assertRaises(RuntimeError):
                    validate_output_contract(repo, "wrong-run", output)
                with self.assertRaises(RuntimeError):
                    validate_output_contract(
                        repo, DEFAULT_RUN_ID, output.with_name("other.json")
                    )

                manifest = expected_manifest_path(repo)
                manifest.parent.mkdir(parents=True)
                manifest.write_text("{}\n", encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    validate_output_contract(repo, DEFAULT_RUN_ID, output)
                validate_output_contract(
                    repo,
                    DEFAULT_RUN_ID,
                    output,
                    allow_existing_manifest=True,
                )

                output.parent.mkdir(parents=True)
                output.write_text("{}\n", encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    validate_output_contract(
                        repo,
                        DEFAULT_RUN_ID,
                        output,
                        allow_existing_manifest=True,
                    )

            with patch.dict(
                os.environ,
                {"OT_EVIDENCE_ROOT": str(repo / "tracked-evidence")},
                clear=False,
            ):
                with self.assertRaises(RuntimeError):
                    validate_output_contract(
                        repo, DEFAULT_RUN_ID, expected_output_path(repo)
                    )

    def test_lock_validation_uses_the_supplied_repo_and_fixed_inputs(self) -> None:
        repo = Path("logical/repo")
        implementation = "a" * 40
        protocol = "b" * 40
        execution = "c" * 40
        implementation_tree = "d" * 40
        lock = {
            "schema_version": 1,
            "experiment_id": "OT-0070",
            "implementation_git_commit": implementation,
            "implementation_git_tree": implementation_tree,
            "protocol_origin_git_commit": protocol,
            "fixed_inputs": {"one_sha256": "digest"},
        }

        def fake_git_output(_repo: Path, *arguments: str) -> str:
            if arguments[0] == "rev-parse":
                if arguments[1] == f"{execution}^":
                    return implementation
                return (
                    implementation_tree
                    if arguments[1] == f"{implementation}^{{tree}}"
                    else protocol
                )
            if arguments[0] == "diff":
                return (
                    "A\tspec/ot-0070-run-lock.json"
                    if arguments[1] == "--name-status"
                    else ""
                )
            raise AssertionError(arguments)

        with patch(
            "open_trajectory_harness.ot0070.load_json", return_value=lock
        ), patch(
            "open_trajectory_harness.ot0070.fixed_input_paths",
            return_value={"one_sha256": Path("one.py")},
        ) as paths, patch(
            "open_trajectory_harness.ot0070.sha256_file", return_value="digest"
        ), patch(
            "open_trajectory_harness.ot0070.git_output",
            side_effect=fake_git_output,
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ):
            self.assertEqual(validate_run_lock(repo, execution), lock)
        paths.assert_called_once_with(repo)

        bad_lock = {**lock, "fixed_inputs": {"one_sha256": "changed"}}
        with patch(
            "open_trajectory_harness.ot0070.load_json", return_value=bad_lock
        ), patch(
            "open_trajectory_harness.ot0070.fixed_input_paths",
            return_value={"one_sha256": Path("one.py")},
        ), patch(
            "open_trajectory_harness.ot0070.sha256_file", return_value="digest"
        ), patch(
            "open_trajectory_harness.ot0070.git_output",
            side_effect=fake_git_output,
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ):
            with self.assertRaises(RuntimeError):
                validate_run_lock(repo, execution)

        def changed_protocol(_repo: Path, *arguments: str) -> str:
            if arguments[0] == "rev-parse":
                if arguments[1] == f"{execution}^":
                    return implementation
                return (
                    implementation_tree
                    if arguments[1] == f"{implementation}^{{tree}}"
                    else protocol
                )
            if arguments[:2] == ("diff", "--name-only"):
                return "spec/ot-0070-acceptance.json"
            if arguments[:2] == ("diff", "--name-status"):
                return "A\tspec/ot-0070-run-lock.json"
            raise AssertionError(arguments)

        with patch(
            "open_trajectory_harness.ot0070.load_json", return_value=lock
        ), patch(
            "open_trajectory_harness.ot0070.git_output",
            side_effect=changed_protocol,
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ):
            with self.assertRaises(RuntimeError):
                validate_run_lock(repo, execution)

        def changed_tree(_repo: Path, *arguments: str) -> str:
            if arguments[0] == "rev-parse":
                if arguments[1] == f"{execution}^":
                    return implementation
                return (
                    implementation_tree
                    if arguments[1] == f"{implementation}^{{tree}}"
                    else protocol
                )
            if arguments[:2] == ("diff", "--name-only"):
                return ""
            if arguments[:2] == ("diff", "--name-status"):
                return "M\tsrc/open_trajectory_harness/app_server.py"
            raise AssertionError(arguments)

        with patch(
            "open_trajectory_harness.ot0070.load_json", return_value=lock
        ), patch(
            "open_trajectory_harness.ot0070.fixed_input_paths",
            return_value={"one_sha256": Path("one.py")},
        ), patch(
            "open_trajectory_harness.ot0070.sha256_file", return_value="digest"
        ), patch(
            "open_trajectory_harness.ot0070.git_output",
            side_effect=changed_tree,
        ), patch(
            "open_trajectory_harness.ot0070.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ):
            with self.assertRaises(RuntimeError):
                validate_run_lock(repo, execution)

    def test_failed_post_manifest_audit_removes_public_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "evidence" / "manifest.json"
            failed_manifest = root / ".evidence" / "failed-manifest.json"
            failure_receipt = root / ".evidence" / "post-audit.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"public":true}\n', encoding="utf-8")
            _quarantine_failed_publication(
                manifest=manifest,
                failed_manifest=failed_manifest,
                failure_receipt=failure_receipt,
                run_id=DEFAULT_RUN_ID,
                post_manifest_audit={
                    "status": "audit_failed",
                    "returncode": 1,
                    "within_bound": True,
                },
            )
            self.assertFalse(manifest.exists())
            self.assertTrue(failed_manifest.exists())
            self.assertTrue(failure_receipt.exists())
            failed_manifest.chmod(0o600)
            failure_receipt.chmod(0o600)
            self.assertEqual(
                failed_manifest.read_text(encoding="utf-8"),
                '{"public":true}\n',
            )
            receipt = load_json(failure_receipt)
            self.assertEqual(receipt["operational_failure"], "audit_failed")
            self.assertFalse(receipt["public_manifest_retained"])

    def test_reconstruction_path_skips_publication_side_effects(self) -> None:
        output = Path("logical/evidence/runs/OT-0070") / f"{DEFAULT_RUN_ID}.json"
        raw = {"summary": {"disposition": "promoted"}}
        with patch(
            "open_trajectory_harness.ot0070.validate_output_contract",
            return_value={
                "store": Path("logical/evidence"),
                "output": output,
                "manifest": Path("logical/manifest.json"),
            },
        ) as output_contract, patch(
            "open_trajectory_harness.ot0070._locked_execution_context",
            return_value=(
                "b" * 40,
                {"implementation_git_commit": "a" * 40},
                self.acceptance,
            ),
        ), patch(
            "open_trajectory_harness.ot0070._execute_locked_raw",
            return_value=(raw, 1.0),
        ), patch(
            "open_trajectory_harness.ot0070.write_sealed_json"
        ) as writer, patch(
            "open_trajectory_harness.ot0070.record_artifact"
        ) as recorder:
            observed, summary = reconstruct(self.repo, DEFAULT_RUN_ID, output)
        self.assertEqual(observed, output)
        self.assertEqual(summary, raw["summary"])
        output_contract.assert_called_once_with(
            self.repo.resolve(),
            DEFAULT_RUN_ID,
            output,
            allow_existing_manifest=True,
        )
        writer.assert_called_once_with(output, raw)
        recorder.assert_not_called()

    def test_recipe_and_calibration_entrypoints_are_exact_but_not_executed(self) -> None:
        self.assertEqual(
            RECONSTRUCTION_RECIPE,
            "At the exact Git commit named by environment.git.commit and with a fresh "
            "$EVIDENCE, run OT_EVIDENCE_ROOT=$EVIDENCE PYTHONPATH=src python3 "
            "experiments/ot_0070_harness.py "
            "--reconstruct-only --output $EVIDENCE/runs/OT-0070/"
            "ot-0070-trajectory-authority-calibration-001.json",
        )
        source = inspect.getsource(run_calibration)
        self.assertIn('for run_label in acceptance["run_order"]', source)
        self.assertIn("evaluate_case", source)
        self.assertNotIn("record_artifact", source)
        self.assertLess(len(canonical_json(self.result)), MAXIMUM_RAW_ARTIFACT_BYTES)

    def test_unknown_case_and_invalid_raw_identity_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            build_fixture_history(16)
        with self.assertRaises(ValueError):
            evaluate_case(-1, repo=self.repo, execute_reset=False)
        summary = assemble_calibration_result(
            self.acceptance, self._complete_runs(), wall_within_bound=True
        )
        with self.assertRaises(ValueError):
            build_raw_artifact(
                run_id="not-the-default",
                implementation_commit="a" * 40,
                execution_commit="b" * 40,
                summary=summary,
                tests=PASSED_TESTS,
                audit=PASSED_AUDIT,
                complete_run_within_bound=True,
            )


if __name__ == "__main__":
    unittest.main()
