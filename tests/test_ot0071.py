from __future__ import annotations

import inspect
import itertools
import subprocess
import unittest
from pathlib import Path

from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0071 import (
    ACCEPTANCE_PATH,
    CASE_INDICES,
    PROJECTION_BYTES,
    PROTOCOL_FROZEN_PATHS,
    PROTOCOL_ORIGIN_COMMIT,
    ProtocolError,
    append_decision,
    build_raw_artifact,
    build_derivation_receipt,
    build_case_runtime,
    build_task,
    decisive_intervention_calibration,
    evaluate_case,
    execute_reference_regime,
    pure_control_calibration,
    validate_contact,
    validate_endpoint,
    validate_locator,
    validate_projection_request,
)
from open_trajectory_harness import ot0071_reset_worker


class OT0071Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path(__file__).resolve().parents[1]
        cls.acceptance = load_json(cls.repo / ACCEPTANCE_PATH)
        cls.implementation = "0" * 40
        cls.task = build_task(cls.implementation)

    def test_task_is_exact_reconstructible_and_domain_separated(self) -> None:
        first = build_task(self.implementation)
        second = build_task(self.implementation)
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(len(first["cases"]), 16)
        tokens = []
        for case in first["cases"]:
            tokens.append(case["case_token"])
            for key in (
                "address_handles_by_semantic_branch",
                "branch_keys_by_semantic_branch",
                "contact_tokens",
                "query_keys_by_semantic_query",
            ):
                tokens.extend(case[key])
        self.assertEqual(len(tokens), len(set(tokens)))
        with self.assertRaises(ProtocolError):
            build_task("short")

    def test_source_bundle_is_future_blind_and_schedule_is_late(self) -> None:
        runtime, digest = build_case_runtime(
            self.task, self.acceptance, 0
        )
        self.assertEqual(runtime.schedule, (0, 1, 2))
        self.assertRegex(digest, r"[0-9a-f]{64}")
        forbidden = {
            "active_output",
            "correction",
            "endpoint",
            "permutation",
            "regime",
            "resolved_output",
            "score",
        }
        for source in runtime.sources:
            locator = validate_locator(runtime.store, source["locator_id"])
            encoded = canonical_json(locator["payload"]).decode().lower()
            self.assertTrue(all(token not in encoded for token in forbidden))
            self.assertEqual(
                set(locator["payload"]["body"]), {"record", "record_id"}
            )

    def test_complete_reference_and_independent_control_lineages_pass(self) -> None:
        result = evaluate_case(
            self.repo,
            self.task,
            self.acceptance,
            0,
            include_independent_controls=True,
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["correction_errors"], [2, 2, 2])
        self.assertEqual(result["successor_trial_errors"], [0, 0, 0])
        self.assertEqual(result["endpoint_errors"], [0, 0, 0])
        self.assertEqual(result["set_down_endpoint_errors"], [4, 4, 4])
        self.assertEqual(result["prior_replay_trial_errors"], [2, 2])
        self.assertEqual(result["prior_replay_endpoint_errors"], [4, 4])
        self.assertEqual(result["practice_row_changes"], [3, 3])
        self.assertLessEqual(result["projection_maximum_bytes"], PROJECTION_BYTES)

    def test_append_order_and_opaque_alpha_renaming_do_not_change_verdicts(self) -> None:
        baseline = evaluate_case(self.repo, self.task, self.acceptance, 0)
        reordered = evaluate_case(
            self.repo,
            self.task,
            self.acceptance,
            0,
            reverse_diagnostics=True,
            source_order=(2, 1, 0),
        )
        alpha = evaluate_case(
            self.repo,
            build_task("1" * 40),
            self.acceptance,
            0,
            reverse_diagnostics=True,
            source_order=(2, 1, 0),
        )
        verdict_keys = {
            "correction_errors",
            "endpoint_errors",
            "pass",
            "practice_row_changes",
            "successor_trial_errors",
        }
        self.assertEqual(
            {key: baseline[key] for key in verdict_keys},
            {key: reordered[key] for key in verdict_keys},
        )
        self.assertEqual(
            {key: baseline[key] for key in verdict_keys},
            {key: alpha[key] for key in verdict_keys},
        )
        self.assertEqual(
            baseline["record_ids_sha256"], reordered["record_ids_sha256"]
        )
        self.assertNotEqual(
            baseline["record_ids_sha256"], alpha["record_ids_sha256"]
        )

    def test_outcome_geometry_and_stale_contact_are_causal(self) -> None:
        runtime, _ = build_case_runtime(self.task, self.acceptance, 1)
        result = execute_reference_regime(self.repo, runtime, 0)
        for outcome_id in result["outcome_ids"]:
            size = len(runtime.store.serialize_projection([outcome_id]))
            self.assertGreaterEqual(size, 1025)
            self.assertLessEqual(size, PROJECTION_BYTES)
        for count in range(2, 7):
            for subset in itertools.combinations(result["outcome_ids"], count):
                with self.assertRaises(ValueError):
                    runtime.store.serialize_projection(subset)
        validate_contact(runtime.store, result["contact_id"])
        validate_projection_request(runtime.store, result["request_id"])
        with self.assertRaises(ProtocolError):
            validate_contact(
                runtime.store, result["contact_id"], require_current=True
            )
        with self.assertRaises(ProtocolError):
            validate_projection_request(
                runtime.store, result["request_id"], require_current=True
            )

    def test_inactive_source_is_not_a_rollback_target(self) -> None:
        runtime, _ = build_case_runtime(self.task, self.acceptance, 2)
        execute_reference_regime(self.repo, runtime, 0)
        decision_id = append_decision(
            self.repo,
            runtime,
            action="rollback",
            decision_occurrence=99,
            rollback_target_id=runtime.sources[0]["proposal_id"],
        )
        with self.assertRaises(ProtocolError):
            runtime.controller.apply(decision_id)

    def test_world_row_identities_are_fresh_across_claim_surfaces(self) -> None:
        runtime, _ = build_case_runtime(self.task, self.acceptance, 3)
        execute_reference_regime(self.repo, runtime, 0)
        source_rows: set[str] = set()
        correction_rows: set[str] = set()
        endpoint_rows: set[str] = set()
        for record_id in runtime.store.record_ids:
            record = runtime.store.get(record_id)
            payload = record["payload"]
            if payload.get("record") == "trial":
                target = source_rows if payload["scope"] == "source" else correction_rows
                target.update(row["trial_id"] for row in payload["trace"])
            elif payload.get("record") == "correction_consequence":
                correction_rows.update(row["trial_id"] for row in payload["trace"])
            elif payload.get("record") == "endpoint":
                validate_endpoint(runtime.store, record_id)
                endpoint_rows.update(row["trial_id"] for row in payload["trace"])
        self.assertTrue(source_rows)
        self.assertTrue(correction_rows)
        self.assertTrue(endpoint_rows)
        self.assertFalse(source_rows & correction_rows)
        self.assertFalse(source_rows & endpoint_rows)
        self.assertFalse(correction_rows & endpoint_rows)

    def test_every_frozen_pure_control_bound_is_exhaustive(self) -> None:
        result = pure_control_calibration(self.task, self.acceptance)
        self.assertTrue(result["pass"])
        self.assertEqual(result["stationary_table_count"], 27)
        self.assertEqual(result["stationary_permutation_count"], 6)
        self.assertGreaterEqual(result["stationary_case_minimum_wrong_regimes"], 2)
        self.assertEqual(result["fixed_clock_count"], 27)
        self.assertGreaterEqual(result["fixed_clock_minimum_wrong"], 30)
        self.assertEqual(result["one_step_count"], 2187)
        self.assertGreaterEqual(result["one_step_minimum_failed_cases"], 13)
        self.assertGreaterEqual(result["one_step_minimum_wrong"], 20)

    def test_decisive_failure_seams_reject_without_quality_rescue(self) -> None:
        result = decisive_intervention_calibration(
            self.repo, self.task, self.acceptance
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["rejection_count"], 13)

    def test_derivation_receipt_binds_exact_canonical_task_bytes(self) -> None:
        task_bytes = canonical_json(self.task)
        receipt = build_derivation_receipt(self.implementation, task_bytes)
        self.assertEqual(receipt["task_sha256"], sha256_bytes(task_bytes))
        self.assertEqual(receipt["task_bytes"], len(task_bytes))
        self.assertEqual(receipt["attempt"], 1)
        with self.assertRaises(ProtocolError):
            build_derivation_receipt(
                self.implementation,
                task_bytes.replace(b'"schema_version":1', b'"schema_version":2'),
            )

    def test_invalidated_result_cannot_receive_public_authority(self) -> None:
        summary = {
            "experiment_id": "OT-0071",
            "disposition": "invalidated",
            "authorized_candidate_count": 0,
        }
        raw = build_raw_artifact(
            "ot-0071-receipted-projection-practice-opportunity-calibration-001",
            "0" * 40,
            "1" * 40,
            summary,
            {"status": "passed", "returncode": 0},
            {"status": "passed", "returncode": 0},
        )
        self.assertEqual(raw["evidence_class"], "exploratory-only")
        self.assertEqual(raw["summary"]["authorized_candidate_count"], 0)

    def test_worker_has_no_store_loader_network_or_tool_surface(self) -> None:
        source = inspect.getsource(ot0071_reset_worker)
        for forbidden in (
            "TrajectoryStore",
            "bootstrap_trajectory_store",
            "requests",
            "socket",
            "subprocess",
        ):
            self.assertNotIn(forbidden, source)

    def test_protocol_paths_are_byte_identical_to_frozen_commit(self) -> None:
        for path in PROTOCOL_FROZEN_PATHS:
            current = (self.repo / path).read_bytes()
            frozen = subprocess.run(
                ["git", "show", f"{PROTOCOL_ORIGIN_COMMIT}:{path.as_posix()}"],
                cwd=self.repo,
                check=True,
                capture_output=True,
            ).stdout
            self.assertEqual(
                sha256_bytes(current),
                sha256_bytes(frozen),
                path.as_posix(),
            )

    def test_all_case_indices_are_frozen(self) -> None:
        self.assertEqual(CASE_INDICES, tuple(range(16)))
        self.assertEqual(
            self.acceptance["scenario_indices"], list(CASE_INDICES)
        )


if __name__ == "__main__":
    unittest.main()
