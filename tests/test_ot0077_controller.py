from __future__ import annotations

import base64
import copy
import json
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from open_trajectory_harness.ot0002 import canonical_json, sha256_bytes
from open_trajectory_harness.ot0077 import (
    EXPERIMENT_ID,
    _consumer_facts,
    _controller_absence,
    _execute_all_conditions,
    _execute_online_condition,
    _online_lineage_ready,
    _run_in_process_consumer,
    _worker_environment,
    _wrong_lineage_condition,
    run_calibration,
    run_fresh_consumer,
)
from open_trajectory_harness.ot0077_learning import (
    COMPACT_REFERENCE,
    LOG_REFERENCE,
    encode_state,
    initial_state,
)
from open_trajectory_harness.ot0077_protocol import build_design_task
from open_trajectory_harness.ot0077_receipts import (
    decode_blob,
    derive_identity,
    validate_chain,
    validated_episode_resets,
)


COMMIT = "1" * 40
DESCRIPTOR = (
    "positive-reference",
    COMPACT_REFERENCE,
    COMPACT_REFERENCE,
    None,
)


def _rebind_chain_receipts(chain: dict[str, object]) -> None:
    """Recompute a mutated chain's complete ancestry and trace identities."""

    identities: dict[str, str] = {}

    def rebind(value: object) -> object:
        if type(value) is dict:
            return {key: rebind(item) for key, item in value.items()}
        if type(value) is list:
            return [rebind(item) for item in value]
        if type(value) is str:
            return identities.get(value, value)
        return value

    for receipt in chain["receipt_order"]:
        old_identity = receipt["receipt_sha256"]
        receipt["context"] = rebind(receipt["context"])
        receipt["parents"] = rebind(receipt["parents"])
        receipt["payload"] = rebind(receipt["payload"])
        body = {
            key: item
            for key, item in receipt.items()
            if key != "receipt_sha256"
        }
        new_identity = sha256_bytes(canonical_json(body))
        receipt["receipt_sha256"] = new_identity
        identities[old_identity] = new_identity
    for key in (
        "case_receipt_sha256",
        "lineage_receipt_sha256",
        "terminal_audit_receipt_sha256",
    ):
        chain[key] = identities[chain[key]]
    body = {key: item for key, item in chain.items() if key != "trace_sha256"}
    chain["trace_sha256"] = sha256_bytes(canonical_json(body))


def _refresh_lineage_chain_summary(lineage: dict[str, object]) -> None:
    validation = validate_chain(lineage["chain"], require_online_admissible=True)
    lineage["chain_validation"] = {
        "authority_eligible": validation.authority_eligible,
        "encounter_count": validation.encounter_count,
        "errors": validation.errors,
        "terminal_audit_receipt_sha256": (
            validation.terminal_audit_receipt_sha256
        ),
        "trace_sha256": validation.trace_sha256,
        "episode_reset_count": validation.episode_reset_count,
    }
    lineage["episode_reset_evidence"] = validated_episode_resets(lineage["chain"])


def _mutate_first_retained_response(
    lineage: dict[str, object],
    **changes: object,
) -> None:
    chain = lineage["chain"]
    consumer = chain["receipt_order"][5]
    facts = consumer["payload"]["facts"]
    response = json.loads(base64.b64decode(facts["response_base64"], validate=True))
    response.update(changes)
    response_bytes = canonical_json(response)
    response_sha256 = sha256_bytes(response_bytes)
    facts["response_base64"] = base64.b64encode(response_bytes).decode("ascii")
    facts["response_sha256"] = response_sha256
    facts["process_instance_id"] = derive_identity(
        "observed-process-instance",
        facts["process_challenge_sha256"],
        response_sha256,
        facts["process_boundary"],
        facts["process_started"],
        facts["fresh_process_verified"],
    )
    facts["workspace_instance_id"] = derive_identity(
        "observed-workspace-instance",
        facts["workspace_challenge_sha256"],
        response_sha256,
        facts["workspace_observed"],
    )
    chain["receipt_order"][9]["payload"][
        "consumer_response_sha256"
    ] = response_sha256
    lineage["worker_response_sha256s"][0] = response_sha256
    lineage["consumer_attempts"][0]["response_sha256"] = response_sha256
    _rebind_chain_receipts(chain)
    _refresh_lineage_chain_summary(lineage)


def _execute_with_absence(*, terminal_only: bool) -> dict[str, object]:
    task = build_design_task(0)
    case = task["cases"][0]

    def consumer(_repo: Path, **kwargs: object) -> dict[str, object]:
        mode = str(kwargs["mode"])
        encounter_index = int(kwargs["encounter_index"])
        projection = kwargs["projection"]
        should_timeout = mode == "terminal-audit" if terminal_only else (
            mode == "prediction" and encounter_index == 0
        )
        if should_timeout:
            return _controller_absence(
                projection=projection,
                condition_id=str(kwargs["condition_id"]),
                encounter_index=encounter_index,
                mode=mode,
                status="timeout",
                failure_code="consumer-timeout",
            )
        return _run_in_process_consumer(
            mechanism=str(kwargs["mechanism"]),
            projection=projection,
            public_query=kwargs["public_query"],
            mode=mode,
        )

    with mock.patch(
        "open_trajectory_harness.ot0077.run_fresh_consumer",
        side_effect=consumer,
    ):
        return _execute_online_condition(
            Path.cwd(),
            execution_commit=COMMIT,
            task_digest=sha256_bytes(canonical_json(task)),
            case=case,
            descriptor=DESCRIPTOR,
            use_fresh_processes=True,
            deadline=time.monotonic() + 60,
            cancel_event=threading.Event(),
        )


class ConsumerTimeoutTests(unittest.TestCase):
    def test_real_worker_prediction_and_terminal_audit_smoke(self) -> None:
        task = build_design_task(0)
        case = task["cases"][0]
        event = case["episodes"][0]["events"][0]
        task_sha = sha256_bytes(canonical_json(task))
        condition_id = "2" * 64
        lineage_id = derive_identity("lineage", case["case_id"], condition_id)
        projection = encode_state(COMPACT_REFERENCE, initial_state(COMPACT_REFERENCE))
        for mode, encounter_index, public_query in (
            ("prediction", 0, event["public_query"]),
            ("terminal-audit", 242, None),
        ):
            facts = _consumer_facts(
                execution_commit=COMMIT,
                task_digest=task_sha,
                case_id=case["case_id"],
                condition_id=condition_id,
                branch_token="genesis",
                encounter_index=encounter_index,
                mode=mode,
            )
            result = run_fresh_consumer(
                Path.cwd(),
                mechanism=COMPACT_REFERENCE,
                case_id=case["case_id"],
                condition_id=condition_id,
                lineage_id=lineage_id,
                encounter_index=encounter_index,
                mode=mode,
                public_query=public_query,
                projection=projection,
                facts=facts,
                deadline=time.monotonic() + 10,
                cancel_event=threading.Event(),
            )
            self.assertEqual(result["attempt_status"], "completed")
            self.assertIsNone(result["failure_code"])
            self.assertTrue(result["sentinel_absent"])

    def test_real_stale_rejections_are_typed_for_both_references(self) -> None:
        command = "\n".join(
            (
                "import json, threading, time",
                "from pathlib import Path",
                "from open_trajectory_harness.ot0002 import canonical_json, sha256_bytes",
                "from open_trajectory_harness.ot0077 import _execute_online_condition",
                "from open_trajectory_harness.ot0077_learning import COMPACT_REFERENCE, LOG_REFERENCE",
                "from open_trajectory_harness.ot0077_protocol import build_design_task",
                "task = build_design_task(0)",
                "case = task['cases'][0]",
                "digest = sha256_bytes(canonical_json(task))",
                "summary = {}",
                "for reference in (COMPACT_REFERENCE, LOG_REFERENCE):",
                "    result = _execute_online_condition(Path.cwd(), execution_commit='1' * 40, task_digest=digest, case=case, descriptor=('causal-intervention', 'one-step-stale-consequence', reference, 'one-step-stale-consequence'), use_fresh_processes=True, deadline=time.monotonic() + 60, cancel_event=threading.Event())",
                "    statuses = result['condition']['prediction_statuses']",
                "    summary[reference] = {'valid': statuses.count('valid'), 'invalid': statuses.count('invalid'), 'failures': len(result['operational_failures']), 'complete': result['operational_complete']}",
                "print(json.dumps(summary, sort_keys=True, separators=(',', ':')))",
            )
        )
        process = subprocess.run(
            [sys.executable, "-S", "-c", command],
            cwd=Path.cwd(),
            env=_worker_environment(Path.cwd()),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        self.assertEqual(
            json.loads(process.stdout),
            {
                COMPACT_REFERENCE: {
                    "valid": 221,
                    "invalid": 21,
                    "failures": 0,
                    "complete": True,
                },
                LOG_REFERENCE: {
                    "valid": 14,
                    "invalid": 228,
                    "failures": 0,
                    "complete": True,
                },
            },
        )

    def test_forkserver_lifecycle_is_race_free_at_frozen_concurrency(self) -> None:
        command = "\n".join(
            (
                "import json, threading, time",
                "from concurrent.futures import ThreadPoolExecutor",
                "from pathlib import Path",
                "import open_trajectory_harness.ot0077 as ot0077",
                "from open_trajectory_harness.ot0002 import canonical_json, sha256_bytes",
                "from open_trajectory_harness.ot0077_learning import COMPACT_REFERENCE, encode_state, initial_state",
                "from open_trajectory_harness.ot0077_protocol import build_design_task",
                "from open_trajectory_harness.ot0077_receipts import derive_identity",
                "repo = Path.cwd()",
                "task = build_design_task(0)",
                "case = task['cases'][0]",
                "event = case['episodes'][0]['events'][0]",
                "digest = sha256_bytes(canonical_json(task))",
                "condition_id = '2' * 64",
                "lineage_id = derive_identity('lineage', case['case_id'], condition_id)",
                "projection = encode_state(COMPACT_REFERENCE, initial_state(COMPACT_REFERENCE))",
                "context = ot0077._payload_blind_forkserver(repo)",
                "if context is None: raise SystemExit(77)",
                "environment = ot0077._worker_environment(repo)",
                "cancel = threading.Event()",
                "def run_chunk(worker_index):",
                "    chunk = []",
                "    for index in range(worker_index, 512, 24):",
                "        facts = ot0077._consumer_facts(execution_commit='1' * 40, task_digest=digest, case_id=case['case_id'], condition_id=condition_id, branch_token=f'race-{index}', encounter_index=0, mode='prediction')",
                "        chunk.append(ot0077.run_fresh_consumer(repo, mechanism=COMPACT_REFERENCE, case_id=case['case_id'], condition_id=condition_id, lineage_id=lineage_id, encounter_index=0, mode='prediction', public_query=event['public_query'], projection=projection, facts=facts, deadline=time.monotonic() + 20, cancel_event=cancel, fork_context=context, worker_environment=environment))",
                "    return chunk",
                "with ThreadPoolExecutor(max_workers=24) as executor:",
                "    results = [result for chunk in executor.map(run_chunk, range(24)) for result in chunk]",
                "summary = {'count': len(results), 'completed': sum(result['attempt_status'] == 'completed' for result in results), 'clean': sum(result['failure_code'] is None and result['process_started'] is True and result['workspace_empty_after'] is True and result['sentinel_absent'] is True for result in results), 'prediction_bits': sum(type(result['prediction']) is int and result['prediction'] in {0, 1} for result in results), 'unique_responses': len({result['response_sha256'] for result in results})}",
                "print(json.dumps(summary, sort_keys=True, separators=(',', ':')))",
            )
        )
        process = subprocess.run(
            [sys.executable, "-S", "-c", command],
            cwd=Path.cwd(),
            env=_worker_environment(Path.cwd()),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if process.returncode == 77:
            self.skipTest("payload-blind forkserver is unavailable")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        self.assertEqual(
            json.loads(process.stdout),
            {
                "clean": 512,
                "completed": 512,
                "count": 512,
                "prediction_bits": 512,
                "unique_responses": 512,
            },
        )

    def test_fresh_child_timeout_returns_a_retained_slot_result(self) -> None:
        task = build_design_task(0)
        case = task["cases"][0]
        projection = encode_state(COMPACT_REFERENCE, initial_state(COMPACT_REFERENCE))
        condition_id = "2" * 64
        facts = _consumer_facts(
            execution_commit=COMMIT,
            task_digest=sha256_bytes(canonical_json(task)),
            case_id=case["case_id"],
            condition_id=condition_id,
            branch_token="genesis",
            encounter_index=0,
            mode="prediction",
        )
        with mock.patch(
            "open_trajectory_harness.ot0077._run_exec_consumer",
            return_value={
                "status": "timeout",
                "returncode": None,
                "stdout": b"",
                "stderr": b"",
            },
        ):
            result = run_fresh_consumer(
                Path.cwd(),
                mechanism=COMPACT_REFERENCE,
                case_id=case["case_id"],
                condition_id=condition_id,
                lineage_id="3" * 64,
                encounter_index=0,
                mode="prediction",
                public_query=case["episodes"][0]["events"][0]["public_query"],
                projection=projection,
                facts=facts,
                deadline=time.monotonic() + 10,
                cancel_event=threading.Event(),
            )
        self.assertEqual(result["attempt_status"], "timeout")
        self.assertEqual(result["prediction_status"], "timeout")
        self.assertEqual(result["failure_code"], "consumer-timeout")
        self.assertIsNone(result["prediction"])

    def test_prediction_timeout_is_exact_noop_and_next_slot_still_runs(self) -> None:
        result = _execute_with_absence(terminal_only=False)
        self.assertEqual(result["condition"]["prediction_statuses"][0], "timeout")
        self.assertEqual(result["condition"]["prediction_statuses"][1], "valid")
        self.assertFalse(result["operational_complete"])
        self.assertTrue(result["terminal_audit_completed"])
        self.assertFalse(result["chain_validation"]["authority_eligible"])
        self.assertEqual(len(result["operational_failures"]), 1)

        receipts = result["chain"]["receipt_order"]
        initial_state = receipts[3]["payload"]["blob"]
        initial_projection = receipts[4]["payload"]["blob"]
        update = receipts[11]["payload"]
        post_state = receipts[12]["payload"]["blob"]
        delivered_projection = receipts[13]["payload"]["blob"]
        self.assertEqual(update["decision"], "no-op")
        self.assertEqual(update["consequence_binding"], "withheld")
        self.assertIsNone(update["delivered_outcome"])
        self.assertEqual(
            decode_blob(
                update["update_payload"],
                limit=2_048,
                label="timeout update payload",
            ),
            b"",
        )
        self.assertEqual(post_state["sha256"], initial_state["sha256"])
        self.assertEqual(delivered_projection["sha256"], initial_projection["sha256"])

    def test_terminal_audit_timeout_preserves_all_predictions_but_removes_authority(
        self,
    ) -> None:
        result = _execute_with_absence(terminal_only=True)
        self.assertEqual(len(result["condition"]["prediction_statuses"]), 242)
        self.assertNotIn("timeout", result["condition"]["prediction_statuses"])
        self.assertFalse(result["terminal_audit_completed"])
        self.assertFalse(result["operational_complete"])
        self.assertFalse(result["chain_validation"]["authority_eligible"])
        self.assertEqual(result["operational_failures"][0]["mode"], "terminal-audit")


class OnlineLineageReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.task = build_design_task(0)
        cls.case = cls.task["cases"][0]
        cls.task_digest = sha256_bytes(canonical_json(cls.task))
        lineage = _execute_online_condition(
            Path.cwd(),
            execution_commit=COMMIT,
            task_digest=cls.task_digest,
            case=cls.case,
            descriptor=DESCRIPTOR,
            use_fresh_processes=True,
            deadline=time.monotonic() + 60,
            cancel_event=threading.Event(),
        )
        # _execute_all_conditions supplies these envelope fields around the
        # direct condition body before readiness is evaluated.
        lineage["case_id"] = cls.case["case_id"]
        lineage["case_index"] = cls.case["case_index"]
        if not _online_lineage_ready(
            lineage,
            DESCRIPTOR,
            execution_commit=COMMIT,
            task_digest=cls.task_digest,
            case=cls.case,
        ):
            raise AssertionError("canonical fresh readiness fixture is not ready")
        cls.fresh_lineage = lineage

    def test_in_process_lineage_cannot_be_rescued_by_copied_fresh_summaries(
        self,
    ) -> None:
        lineage = _execute_online_condition(
            Path.cwd(),
            execution_commit=COMMIT,
            task_digest=self.task_digest,
            case=self.case,
            descriptor=DESCRIPTOR,
            use_fresh_processes=False,
            deadline=time.monotonic() + 60,
            cancel_event=threading.Event(),
        )
        lineage["case_id"] = self.case["case_id"]
        lineage["case_index"] = self.case["case_index"]
        self.assertFalse(
            _online_lineage_ready(
                lineage,
                DESCRIPTOR,
                execution_commit=COMMIT,
                task_digest=self.task_digest,
                case=self.case,
            )
        )

        lineage["fresh_processes"] = True
        lineage["worker_response_sha256s"] = copy.deepcopy(
            self.fresh_lineage["worker_response_sha256s"]
        )
        lineage["consumer_attempts"] = copy.deepcopy(
            self.fresh_lineage["consumer_attempts"]
        )
        self.assertFalse(
            _online_lineage_ready(
                lineage,
                DESCRIPTOR,
                execution_commit=COMMIT,
                task_digest=self.task_digest,
                case=self.case,
            )
        )

    def test_rebound_retained_mechanism_mismatch_is_not_ready(self) -> None:
        lineage = copy.deepcopy(self.fresh_lineage)
        original_trace = lineage["chain"]["trace_sha256"]
        _mutate_first_retained_response(
            lineage,
            mechanism_id=LOG_REFERENCE,
        )
        self.assertNotEqual(lineage["chain"]["trace_sha256"], original_trace)
        validate_chain(lineage["chain"], require_online_admissible=True)
        self.assertFalse(
            _online_lineage_ready(
                lineage,
                DESCRIPTOR,
                execution_commit=COMMIT,
                task_digest=self.task_digest,
                case=self.case,
            )
        )

    def test_rebound_over_budget_prediction_operations_are_not_ready(self) -> None:
        lineage = copy.deepcopy(self.fresh_lineage)
        _mutate_first_retained_response(
            lineage,
            prediction_operations=131_073,
        )
        lineage["maximum_prediction_operations"] = 131_073
        validate_chain(lineage["chain"], require_online_admissible=True)
        self.assertFalse(
            _online_lineage_ready(
                lineage,
                DESCRIPTOR,
                execution_commit=COMMIT,
                task_digest=self.task_digest,
                case=self.case,
            )
        )

    def test_arbitrary_and_reused_sentinel_challenges_are_not_ready(self) -> None:
        for mutation in ("arbitrary", "reused"):
            with self.subTest(mutation=mutation):
                lineage = copy.deepcopy(self.fresh_lineage)
                consumers = [
                    receipt
                    for receipt in lineage["chain"]["receipt_order"]
                    if receipt["kind"] == "consumer"
                ]
                sentinels = consumers[0]["payload"]["facts"][
                    "forbidden_channel_sentinels"
                ]
                if mutation == "arbitrary":
                    sentinels[0]["sentinel_sha256"] = derive_identity(
                        "arbitrary-sentinel-challenge"
                    )
                else:
                    sentinels[0]["sentinel_sha256"] = consumers[1]["payload"][
                        "facts"
                    ]["forbidden_channel_sentinels"][0]["sentinel_sha256"]
                _rebind_chain_receipts(lineage["chain"])
                _refresh_lineage_chain_summary(lineage)
                validate_chain(
                    lineage["chain"],
                    require_online_admissible=True,
                )
                self.assertFalse(
                    _online_lineage_ready(
                        lineage,
                        DESCRIPTOR,
                        execution_commit=COMMIT,
                        task_digest=self.task_digest,
                        case=self.case,
                    )
                )

    def test_summary_maxima_cannot_underreport_retained_work(self) -> None:
        for key in (
            "maximum_projection_bytes",
            "maximum_prediction_operations",
            "maximum_update_operations",
        ):
            with self.subTest(key=key):
                lineage = copy.deepcopy(self.fresh_lineage)
                self.assertGreater(lineage[key], 0)
                lineage[key] -= 1
                self.assertFalse(
                    _online_lineage_ready(
                        lineage,
                        DESCRIPTOR,
                        execution_commit=COMMIT,
                        task_digest=self.task_digest,
                        case=self.case,
                    )
                )


class DeadlinePropagationTests(unittest.TestCase):
    def test_expired_scheduler_drains_and_retains_missing_denominators(self) -> None:
        task = copy.deepcopy(build_design_task(0))
        task["cases"] = task["cases"][:1]
        task["case_count"] = 1
        before = {thread.ident for thread in threading.enumerate()}
        with mock.patch("open_trajectory_harness.ot0077.validate_task"):
            cases, lineages = _execute_all_conditions(
                Path.cwd(),
                execution_commit=COMMIT,
                task=task,
                use_fresh_processes=False,
                max_workers=2,
                deadline=time.monotonic() - 1,
            )
        after = {thread.ident for thread in threading.enumerate()}
        self.assertEqual(len(cases), 1)
        self.assertEqual(len(lineages), 23)
        positive = next(
            item
            for item in lineages
            if item["condition"]["role"] == "positive-reference"
        )
        self.assertEqual(positive["condition"]["prediction_statuses"], ["missing"] * 242)
        self.assertFalse(positive["operational_complete"])
        self.assertTrue(after <= before)

    def test_run_calibration_passes_one_absolute_deadline_to_work_and_rollback(
        self,
    ) -> None:
        task = build_design_task(0)
        deadline = time.monotonic() + 60
        observed: list[float] = []

        def conditions(*_args: object, **kwargs: object) -> tuple[list[object], list[object]]:
            observed.append(kwargs["deadline"])
            return [], []

        def rollback(*_args: object, **kwargs: object) -> object:
            observed.append(kwargs["deadline"])
            raise RuntimeError("stop after deadline capture")

        with (
            mock.patch(
                "open_trajectory_harness.ot0077._execute_all_conditions",
                side_effect=conditions,
            ),
            mock.patch(
                "open_trajectory_harness.ot0077._execute_rollback_suite",
                side_effect=rollback,
            ),
            self.assertRaisesRegex(RuntimeError, "deadline capture"),
        ):
            run_calibration(
                Path.cwd(),
                task,
                {"experiment_id": EXPERIMENT_ID},
                execution_commit=COMMIT,
                use_fresh_processes=False,
                clean_private_reconstruction=False,
                run_verification_commands=False,
                deadline=deadline,
            )
        self.assertEqual(observed, [deadline, deadline])


class ControllerCausalIntegrationTests(unittest.TestCase):
    def test_recurrence_condition_resets_exactly_at_task_episode_boundaries(self) -> None:
        task = build_design_task(0)
        case = task["cases"][0]
        descriptor = (
            "recurrence-intervention",
            "cross-episode-state-reset",
            COMPACT_REFERENCE,
            "cross-episode-state-reset",
        )
        result = _execute_online_condition(
            Path.cwd(),
            execution_commit=COMMIT,
            task_digest=sha256_bytes(canonical_json(task)),
            case=case,
            descriptor=descriptor,
            use_fresh_processes=False,
            deadline=time.monotonic() + 60,
            cancel_event=threading.Event(),
        )
        resets = result["episode_reset_evidence"]["resets"]
        cursor = 0
        expected_indices = []
        for episode in case["episodes"][:-1]:
            cursor += episode["dwell"]
            expected_indices.append(cursor - 1)
        self.assertEqual(
            [reset["encounter_index"] for reset in resets],
            expected_indices,
        )
        self.assertEqual(
            [reset["target_episode_index"] for reset in resets],
            [1, 2, 3, 4, 5],
        )

    def test_wrong_lineage_controller_attempts_real_substitution_and_rejects_it(
        self,
    ) -> None:
        task = build_design_task(0)
        case = task["cases"][0]
        task_sha = sha256_bytes(canonical_json(task))
        active = _execute_online_condition(
            Path.cwd(),
            execution_commit=COMMIT,
            task_digest=task_sha,
            case=case,
            descriptor=DESCRIPTOR,
            use_fresh_processes=False,
            deadline=time.monotonic() + 60,
            cancel_event=threading.Event(),
        )
        matched_descriptor = (
            "matched-frozen-control",
            f"{COMPACT_REFERENCE}--matched-frozen-initial",
            COMPACT_REFERENCE,
            None,
        )
        donor = _execute_online_condition(
            Path.cwd(),
            execution_commit=COMMIT,
            task_digest=task_sha,
            case=case,
            descriptor=matched_descriptor,
            use_fresh_processes=False,
            deadline=time.monotonic() + 60,
            cancel_event=threading.Event(),
        )
        wrong_descriptor = (
            "causal-intervention",
            "wrong-lineage-projection",
            COMPACT_REFERENCE,
            "wrong-lineage-projection",
        )
        result = _wrong_lineage_condition(
            task_sha,
            case,
            wrong_descriptor,
            active_chain=active["chain"],
            donor_chain=donor["chain"],
        )
        self.assertTrue(result["wrong_lineage_rejection"]["substitution_rejected"])
        self.assertEqual(
            result["wrong_lineage_rejection"]["observed_rejection_code"],
            "sibling-branch-substitution",
        )
        self.assertEqual(result["condition"]["prediction_statuses"], ["invalid"] * 242)


if __name__ == "__main__":
    unittest.main()
