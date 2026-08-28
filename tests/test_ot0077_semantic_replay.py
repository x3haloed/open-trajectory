from __future__ import annotations

import base64
import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from open_trajectory_harness.ot0002 import canonical_json, sha256_bytes
from open_trajectory_harness.ot0077 import (
    EXPERIMENT_ID,
    PUBLIC_JOURNAL_RELATIVE_PATH,
    _condition_from_chain,
    _consumer_facts,
    _descriptor_identity,
    _encounter_journal_ready,
    _execute_online_condition,
    _logical,
    _online_lineage_ready,
    _scientific_without_journal,
)
from open_trajectory_harness.ot0077_journal import (
    SCOPES,
    SegmentedEncounterJournal,
)
from open_trajectory_harness.ot0077_learning import (
    COMPACT_REFERENCE,
    encode_state,
    initial_state,
    predict,
)
from open_trajectory_harness.ot0077_protocol import build_design_task
from open_trajectory_harness.ot0077_receipts import (
    chain_causal_evidence,
    decode_blob,
    derive_identity,
    encode_blob,
    make_consumer_facts,
    validate_chain,
    validated_episode_resets,
)
from open_trajectory_harness.ot0077_reset_worker import ALLOWED_ENVIRONMENT_NAMES


COMMIT = "1" * 40
DESCRIPTOR = (
    "positive-reference",
    COMPACT_REFERENCE,
    COMPACT_REFERENCE,
    None,
)


def _rebind_chain_receipts(chain: dict[str, Any]) -> None:
    """Recompute every descendant identity after an adversarial rewrite."""

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
        receipt["receipt_sha256"] = sha256_bytes(canonical_json(body))
        identities[old_identity] = receipt["receipt_sha256"]
    for key in (
        "case_receipt_sha256",
        "lineage_receipt_sha256",
        "terminal_audit_receipt_sha256",
    ):
        chain[key] = identities[chain[key]]
    body = {key: item for key, item in chain.items() if key != "trace_sha256"}
    chain["trace_sha256"] = sha256_bytes(canonical_json(body))


def _response_from_facts(facts: dict[str, Any]) -> dict[str, Any]:
    return json.loads(base64.b64decode(facts["response_base64"], validate=True))


def _lineage_ready(lineage: dict[str, Any], case: dict[str, Any]) -> bool:
    return _online_lineage_ready(
        lineage,
        DESCRIPTOR,
        execution_commit=COMMIT,
        task_digest=lineage["chain"]["receipt_order"][0]["payload"][
            "task_sha256"
        ],
        case=case,
    )


def _replace_retained_response(
    lineage: dict[str, Any],
    consumer_index: int,
    **changes: object,
) -> str:
    consumers = [
        receipt
        for receipt in lineage["chain"]["receipt_order"]
        if receipt["kind"] == "consumer"
    ]
    facts = consumers[consumer_index]["payload"]["facts"]
    response = _response_from_facts(facts)
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
    return response_sha256


def _refresh_error_summary(chain: dict[str, Any]) -> None:
    errors = 0
    for offset in range(chain["encounter_count"]):
        base = 6 + 9 * offset
        prediction = chain["receipt_order"][base + 3]["payload"]
        outcome = chain["receipt_order"][base + 4]["payload"]
        errors += int(
            prediction["status"] != "valid"
            or prediction["prediction"] != outcome["outcome"]
        )
    chain["summary"]["errors"] = errors


def _refresh_lineage_summary(lineage: dict[str, Any]) -> None:
    chain = lineage["chain"]
    horizon = chain["receipt_order"][0]["payload"]["horizon"]
    validation = validate_chain(chain, require_online_admissible=True)
    causal = chain_causal_evidence(chain)
    consumers = [
        receipt
        for receipt in chain["receipt_order"]
        if receipt["kind"] == "consumer"
    ]
    projections = [chain["receipt_order"][4]["payload"]["blob"]]
    projections.extend(
        chain["receipt_order"][6 + 9 * offset + 7]["payload"]["blob"]
        for offset in range(horizon)
    )
    lineage["condition"] = _condition_from_chain(chain, DESCRIPTOR)
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
    lineage["episode_reset_evidence"] = validated_episode_resets(chain)
    lineage["initial_projection_sha256"] = projections[0]["sha256"]
    lineage["projection_sha256s"] = causal["consumed_projection_sha256s"]
    lineage["worker_response_sha256s"] = [
        item["payload"]["facts"]["response_sha256"] for item in consumers
    ]
    attempts = []
    for index, consumer in enumerate(consumers):
        facts = consumer["payload"]["facts"]
        terminal = index == horizon
        attempts.append(
            {
                "attempt_status": facts["attempt_status"],
                "descriptor_audit_pass": facts["descriptor_audit_pass"],
                "encounter_index": horizon if terminal else index,
                "failure_code": facts["failure_code"],
                "fresh_process_verified": facts["fresh_process_verified"],
                "mode": "terminal-audit" if terminal else "prediction",
                "process_boundary": facts["process_boundary"],
                "process_started": facts["process_started"],
                "response_sha256": facts["response_sha256"],
                "sentinel_absent": all(
                    item["observed"] is False
                    for item in facts["forbidden_channel_sentinels"]
                ),
                "workspace_empty_after": (
                    facts["workspace_observed"] is True
                    and facts["workspace_entries_after"] == []
                ),
            }
        )
    lineage["consumer_attempts"] = attempts
    lineage["operational_failures"] = []
    lineage["operational_complete"] = True
    lineage["terminal_audit_completed"] = True
    lineage["maximum_projection_bytes"] = max(
        projection["byte_count"] for projection in projections
    )
    responses = [
        _response_from_facts(item["payload"]["facts"])
        for item in consumers
    ]
    lineage["maximum_prediction_operations"] = max(
        response["prediction_operations"] for response in responses
    )
    update_operations = []
    for offset in range(horizon):
        raw = decode_blob(
            chain["receipt_order"][6 + 9 * offset + 5]["payload"][
                "update_payload"
            ],
            limit=2_048,
            label="controller update payload",
        )
        if raw:
            update_operations.append(json.loads(raw)["update_operations"])
    lineage["maximum_update_operations"] = max(update_operations, default=0)
    lineage["fresh_processes"] = True


def _freshen_in_process_lineage(
    lineage: dict[str, Any],
    task: dict[str, Any],
    case: dict[str, Any],
) -> None:
    """Replace in-process facts with exact worker-shaped retained facts."""

    chain = lineage["chain"]
    horizon = case["horizon"]
    task_digest = sha256_bytes(canonical_json(task))
    condition_id = lineage["condition_id"]
    lineage_id = chain["receipt_order"][2]["payload"]["lineage_id"]
    branch_token = chain["receipt_order"][2]["payload"]["branch_token"]
    consumers = [
        receipt
        for receipt in chain["receipt_order"]
        if receipt["kind"] == "consumer"
    ]
    projections = [chain["receipt_order"][4]["payload"]["blob"]]
    projections.extend(
        chain["receipt_order"][6 + 9 * offset + 7]["payload"]["blob"]
        for offset in range(horizon)
    )
    for index, (consumer, projection_blob) in enumerate(
        zip(consumers, projections)
    ):
        terminal = index == horizon
        mode = "terminal-audit" if terminal else "prediction"
        encounter_index = horizon if terminal else index
        public_query = (
            None
            if terminal
            else chain["receipt_order"][6 + 9 * index + 1]["payload"][
                "public_query"
            ]
        )
        projection = decode_blob(
            projection_blob,
            limit=2_048,
            label="semantic replay fixture projection",
        )
        if terminal:
            prediction = None
            prediction_operations = 0
            state_bytes = len(projection)
            candidate_count = 0
        else:
            observed = predict(COMPACT_REFERENCE, projection, public_query)
            prediction = observed.prediction
            prediction_operations = observed.operations
            state_bytes = observed.state_bytes
            candidate_count = observed.candidate_count
        challenge = _consumer_facts(
            execution_commit=COMMIT,
            task_digest=task_digest,
            case_id=case["case_id"],
            condition_id=condition_id,
            branch_token=branch_token,
            encounter_index=encounter_index,
            mode=mode,
        )
        response = {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "mechanism_id": COMPACT_REFERENCE,
            "mode": mode,
            "case_id": case["case_id"],
            "condition_id": condition_id,
            "lineage_id": lineage_id,
            "consumer_id": challenge["process_challenge_sha256"],
            "encounter_index": encounter_index,
            "projection_sha256": sha256_bytes(projection),
            "public_query_sha256": (
                sha256_bytes(canonical_json(public_query))
                if public_query is not None
                else None
            ),
            "prediction": prediction,
            "prediction_operations": prediction_operations,
            "state_bytes": state_bytes,
            "candidate_count": candidate_count,
            "descriptor_audit_pass": True,
            "workspace_empty_before": True,
            "workspace_empty_after": True,
            "environment_names": list(ALLOWED_ENVIRONMENT_NAMES),
            "environment_allowlist_pass": True,
            "response_chain_absent": True,
        }
        response_bytes = canonical_json(response)
        sentinel_results = [
            {
                "channel": item["channel"],
                "checked": True,
                "observed": False,
                "planted": True,
                "sentinel_sha256": item["sentinel_sha256"],
            }
            for item in challenge["sentinel_challenges"]
        ]
        facts = make_consumer_facts(
            process_challenge_sha256=challenge["process_challenge_sha256"],
            workspace_challenge_sha256=challenge["workspace_challenge_sha256"],
            response_bytes=response_bytes,
            descriptor_audit_pass=True,
            attempt_status="completed",
            failure_code=None,
            prediction_status="valid",
            process_boundary="one-exec",
            process_started=True,
            fresh_process_verified=True,
            workspace_observed=True,
            environment_fingerprint=challenge["environment_fingerprint"],
            sentinel_results=sentinel_results,
        )
        consumer["payload"]["facts"] = facts
        if not terminal:
            chain["receipt_order"][6 + 9 * index + 3]["payload"][
                "consumer_response_sha256"
            ] = facts["response_sha256"]
    _rebind_chain_receipts(chain)
    _refresh_lineage_summary(lineage)


def _write_journal_chain(
    stage: SegmentedEncounterJournal,
    scope: str,
    chain: dict[str, Any],
) -> None:
    receipts = chain["receipt_order"]
    validation = validate_chain(chain)
    writer = stage.open_segment(
        scope=scope,
        case_id=validation.case_id,
        case_index=receipts[0]["payload"]["case_index"],
        condition_id=receipts[2]["payload"]["condition_id"],
        lineage_id=validation.lineage_id,
        branch_id=validation.branch_id,
        encounter_start=validation.encounter_start,
        encounter_count=validation.encounter_count,
        initial_receipts=receipts[:5],
    )
    cursor = 5
    for offset in range(validation.encounter_count):
        writer.append_consumer(receipts[cursor])
        cursor += 1
        writer.append_encounter(
            validation.encounter_start + offset,
            receipts[cursor : cursor + 8],
        )
        cursor += 8
    writer.append_consumer(receipts[cursor])
    writer.seal(chain)


class OnlineSemanticReplayRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.task = build_design_task(0)
        cls.case = cls.task["cases"][0]
        lineage = _execute_online_condition(
            Path.cwd(),
            execution_commit=COMMIT,
            task_digest=sha256_bytes(canonical_json(cls.task)),
            case=cls.case,
            descriptor=DESCRIPTOR,
            use_fresh_processes=False,
            deadline=time.monotonic() + 60,
            cancel_event=threading.Event(),
        )
        lineage["case_id"] = cls.case["case_id"]
        lineage["case_index"] = cls.case["case_index"]
        _freshen_in_process_lineage(lineage, cls.task, cls.case)
        if not _lineage_ready(lineage, cls.case):
            raise AssertionError("canonical semantic replay fixture is not ready")
        cls.ready_lineage = lineage

    def assert_structurally_valid_but_not_ready(
        self,
        lineage: dict[str, Any],
    ) -> None:
        validation = validate_chain(
            lineage["chain"],
            require_online_admissible=True,
        )
        self.assertTrue(validation.authority_eligible)
        self.assertFalse(_lineage_ready(lineage, self.case))

    def test_fully_rebound_wrong_prediction_is_rejected(self) -> None:
        lineage = copy.deepcopy(self.ready_lineage)
        chain = lineage["chain"]
        prediction = chain["receipt_order"][9]["payload"]
        wrong_prediction = 1 - prediction["prediction"]
        response_sha256 = _replace_retained_response(
            lineage,
            0,
            prediction=wrong_prediction,
        )
        prediction["prediction"] = wrong_prediction
        prediction["consumer_response_sha256"] = response_sha256
        _refresh_error_summary(chain)
        _rebind_chain_receipts(chain)
        _refresh_lineage_summary(lineage)
        self.assert_structurally_valid_but_not_ready(lineage)

    def test_fully_rebound_prediction_metrics_are_rejected(self) -> None:
        consumers = [
            receipt
            for receipt in self.ready_lineage["chain"]["receipt_order"]
            if receipt["kind"] == "consumer"
        ]
        responses = [
            _response_from_facts(item["payload"]["facts"])
            for item in consumers[:-1]
        ]
        maximum_index = max(
            range(len(responses)),
            key=lambda index: responses[index]["prediction_operations"],
        )
        mutations = (
            (
                maximum_index,
                {
                    "prediction_operations": responses[maximum_index][
                        "prediction_operations"
                    ]
                    + 1
                },
            ),
            (0, {"candidate_count": responses[0]["candidate_count"] + 1}),
            (0, {"state_bytes": responses[0]["state_bytes"] + 1}),
        )
        for consumer_index, changes in mutations:
            with self.subTest(changes=changes):
                lineage = copy.deepcopy(self.ready_lineage)
                chain = lineage["chain"]
                response_sha256 = _replace_retained_response(
                    lineage,
                    consumer_index,
                    **changes,
                )
                chain["receipt_order"][6 + 9 * consumer_index + 3]["payload"][
                    "consumer_response_sha256"
                ] = response_sha256
                _rebind_chain_receipts(chain)
                _refresh_lineage_summary(lineage)
                self.assert_structurally_valid_but_not_ready(lineage)

    def test_exact_task_query_body_is_required_beyond_query_identity(self) -> None:
        mutated_case = copy.deepcopy(self.case)
        event = mutated_case["episodes"][0]["events"][0]
        self.assertEqual(event["public_query"]["feature_bits"], "110010001110")
        original_query_id = event["public_query"]["query_id"]
        original_outcome = event["outcome"]
        event["public_query"]["feature_bits"] = "110110001110"

        lineage = _execute_online_condition(
            Path.cwd(),
            execution_commit=COMMIT,
            task_digest=sha256_bytes(canonical_json(self.task)),
            case=mutated_case,
            descriptor=DESCRIPTOR,
            use_fresh_processes=False,
            deadline=time.monotonic() + 60,
            cancel_event=threading.Event(),
        )
        lineage["case_id"] = mutated_case["case_id"]
        lineage["case_index"] = mutated_case["case_index"]
        _freshen_in_process_lineage(lineage, self.task, mutated_case)

        retained_query = lineage["chain"]["receipt_order"][7]["payload"][
            "public_query"
        ]
        self.assertEqual(retained_query["query_id"], original_query_id)
        self.assertEqual(
            lineage["chain"]["receipt_order"][10]["payload"]["outcome"],
            original_outcome,
        )
        self.assertTrue(_lineage_ready(lineage, mutated_case))
        self.assert_structurally_valid_but_not_ready(lineage)

    def test_valid_but_preloaded_seed_substrate_is_rejected(self) -> None:
        preloaded = {
            "basis": [],
            "models": [3742],
            "schema_version": 1,
        }
        preloaded_bytes = encode_state(COMPACT_REFERENCE, preloaded)
        canonical_seed = encode_state(
            COMPACT_REFERENCE,
            initial_state(COMPACT_REFERENCE),
        )
        self.assertNotEqual(preloaded_bytes, canonical_seed)
        with mock.patch(
            "open_trajectory_harness.ot0077.initial_state",
            return_value=copy.deepcopy(preloaded),
        ):
            lineage = _execute_online_condition(
                Path.cwd(),
                execution_commit=COMMIT,
                task_digest=sha256_bytes(canonical_json(self.task)),
                case=self.case,
                descriptor=DESCRIPTOR,
                use_fresh_processes=False,
                deadline=time.monotonic() + 60,
                cancel_event=threading.Event(),
            )
        lineage["case_id"] = self.case["case_id"]
        lineage["case_index"] = self.case["case_index"]
        _freshen_in_process_lineage(lineage, self.task, self.case)

        retained_seed = decode_blob(
            lineage["chain"]["receipt_order"][3]["payload"]["blob"],
            limit=2_048,
            label="retained preloaded seed",
        )
        self.assertEqual(retained_seed, preloaded_bytes)
        self.assert_structurally_valid_but_not_ready(lineage)

    def test_arbitrary_internal_condition_identity_is_rejected(self) -> None:
        task_digest = sha256_bytes(canonical_json(self.task))
        expected_condition_id = _descriptor_identity(
            task_digest,
            self.case["case_id"],
            DESCRIPTOR,
        )
        arbitrary_condition_id = derive_identity(
            "adversarial-internal-condition"
        )
        self.assertNotEqual(arbitrary_condition_id, expected_condition_id)
        with mock.patch(
            "open_trajectory_harness.ot0077._descriptor_identity",
            return_value=arbitrary_condition_id,
        ):
            lineage = _execute_online_condition(
                Path.cwd(),
                execution_commit=COMMIT,
                task_digest=task_digest,
                case=self.case,
                descriptor=DESCRIPTOR,
                use_fresh_processes=False,
                deadline=time.monotonic() + 60,
                cancel_event=threading.Event(),
            )
        lineage["case_id"] = self.case["case_id"]
        lineage["case_index"] = self.case["case_index"]
        _freshen_in_process_lineage(lineage, self.task, self.case)
        self.assertEqual(
            lineage["chain"]["receipt_order"][2]["payload"]["condition_id"],
            arbitrary_condition_id,
        )
        lineage["condition_id"] = expected_condition_id
        self.assert_structurally_valid_but_not_ready(lineage)

    def test_fully_rebound_wrong_final_candidate_state_is_rejected(self) -> None:
        lineage = copy.deepcopy(self.ready_lineage)
        chain = lineage["chain"]
        horizon = chain["encounter_count"]
        base = 6 + 9 * (horizon - 1)
        update = chain["receipt_order"][base + 5]["payload"]
        post_state = chain["receipt_order"][base + 6]["payload"]
        terminal_projection = chain["receipt_order"][base + 7]["payload"]
        wrong_state = decode_blob(
            chain["receipt_order"][4]["payload"]["blob"],
            limit=2_048,
            label="valid but semantically wrong candidate state",
        )
        wrong_blob = encode_blob(
            wrong_state,
            limit=2_048,
            label="valid but semantically wrong candidate state",
        )
        self.assertNotEqual(wrong_blob["sha256"], post_state["blob"]["sha256"])
        update["state_transition"]["candidate_post_state"] = copy.deepcopy(
            wrong_blob
        )
        post_state["blob"] = copy.deepcopy(wrong_blob)
        terminal_projection["blob"] = copy.deepcopy(wrong_blob)
        control = json.loads(
            decode_blob(
                update["update_payload"],
                limit=2_048,
                label="controller update payload",
            )
        )
        control["candidate_post_sha256"] = wrong_blob["sha256"]
        control["delivered_projection_sha256"] = wrong_blob["sha256"]
        update["update_payload"] = encode_blob(
            canonical_json(control),
            limit=2_048,
            label="controller update payload",
        )
        _replace_retained_response(
            lineage,
            horizon,
            projection_sha256=wrong_blob["sha256"],
            state_bytes=wrong_blob["byte_count"],
        )
        _rebind_chain_receipts(chain)
        _refresh_lineage_summary(lineage)
        self.assert_structurally_valid_but_not_ready(lineage)

    def test_fully_rebound_wrong_update_operations_are_rejected(self) -> None:
        lineage = copy.deepcopy(self.ready_lineage)
        chain = lineage["chain"]
        candidates: list[tuple[int, dict[str, Any]]] = []
        for offset in range(chain["encounter_count"]):
            update = chain["receipt_order"][6 + 9 * offset + 5]["payload"]
            control = json.loads(
                decode_blob(
                    update["update_payload"],
                    limit=2_048,
                    label="controller update payload",
                )
            )
            candidates.append((offset, control))
        offset, control = max(
            candidates,
            key=lambda item: item[1]["update_operations"],
        )
        control["update_operations"] += 1
        update = chain["receipt_order"][6 + 9 * offset + 5]["payload"]
        update["update_payload"] = encode_blob(
            canonical_json(control),
            limit=2_048,
            label="controller update payload",
        )
        _rebind_chain_receipts(chain)
        _refresh_lineage_summary(lineage)
        self.assert_structurally_valid_but_not_ready(lineage)

    def test_journal_is_exactly_cross_bound_to_scientific_core(self) -> None:
        chain = self.ready_lineage["chain"]
        encounter_count = chain["encounter_count"]
        task_sha256 = chain["receipt_order"][0]["payload"]["task_sha256"]
        scientific = {
            "encounter_journal": {},
            "execution_git_commit": COMMIT,
            "lineages": [
                {
                    "chain": chain,
                    "condition": copy.deepcopy(self.ready_lineage["condition"]),
                }
            ],
            "rollback_evidence": {
                "alternate_branch": chain,
                "parent_replay": chain,
                "rewind_branch": chain,
            },
            "task": {"case_count": 1},
            "task_sha256": task_sha256,
        }

        def create_stage(
            root: Path,
            *,
            run_id: str,
            included_scopes: tuple[str, ...],
        ) -> SegmentedEncounterJournal:
            stage = SegmentedEncounterJournal.create(
                root,
                run_id=run_id,
                logical_path=_logical(PUBLIC_JOURNAL_RELATIVE_PATH),
                purpose="design",
                task_sha256=task_sha256,
                execution_git_commit=COMMIT,
                expected_case_count=1,
                expected_scope_counts={
                    scope: {
                        "segments": int(scope in included_scopes),
                        "encounters": (
                            encounter_count if scope in included_scopes else 0
                        ),
                    }
                    for scope in SCOPES
                },
            )
            for scope in included_scopes:
                _write_journal_chain(stage, scope, chain)
            return stage

        with tempfile.TemporaryDirectory() as temporary:
            evidence_root = Path(temporary).resolve()
            complete_root = evidence_root / "complete-journal"
            complete = create_stage(
                complete_root,
                run_id="ot-0077-cross-bind-complete",
                included_scopes=SCOPES,
            )
            core_sha256 = sha256_bytes(
                canonical_json(_scientific_without_journal(scientific))
            )
            scientific["encounter_journal"] = complete.seal(
                scientific_sha256=core_sha256
            )
            with mock.patch(
                "open_trajectory_harness.ot0077._store",
                return_value=evidence_root,
            ):
                self.assertTrue(
                    _encounter_journal_ready(
                        scientific,
                        repo=Path.cwd(),
                        purpose="design",
                        journal_root=complete_root,
                        deadline=None,
                    )
                )

                mutated_chain = copy.deepcopy(scientific)
                mutated_chain["lineages"][0]["chain"]["summary"]["errors"] += 1
                self.assertFalse(
                    _encounter_journal_ready(
                        mutated_chain,
                        repo=Path.cwd(),
                        purpose="design",
                        journal_root=complete_root,
                        deadline=None,
                    )
                )

                mutated_execution = copy.deepcopy(scientific)
                mutated_execution["execution_git_commit"] = "2" * 40
                self.assertFalse(
                    _encounter_journal_ready(
                        mutated_execution,
                        repo=Path.cwd(),
                        purpose="design",
                        journal_root=complete_root,
                        deadline=None,
                    )
                )

                mutated_binding = copy.deepcopy(scientific)
                mutated_binding["encounter_journal"]["journal_sha256"] = (
                    derive_identity("mutated-journal-binding")
                )
                self.assertFalse(
                    _encounter_journal_ready(
                        mutated_binding,
                        repo=Path.cwd(),
                        purpose="design",
                        journal_root=complete_root,
                        deadline=None,
                    )
                )

            missing_scope_root = evidence_root / "missing-scope-journal"
            missing_scope = create_stage(
                missing_scope_root,
                run_id="ot-0077-cross-bind-missing-scope",
                included_scopes=("main",),
            )
            missing_scope_scientific = copy.deepcopy(scientific)
            missing_scope_scientific["encounter_journal"] = missing_scope.seal(
                scientific_sha256=core_sha256
            )
            with mock.patch(
                "open_trajectory_harness.ot0077._store",
                return_value=evidence_root,
            ):
                self.assertFalse(
                    _encounter_journal_ready(
                        missing_scope_scientific,
                        repo=Path.cwd(),
                        purpose="design",
                        journal_root=missing_scope_root,
                        deadline=None,
                    )
                )


if __name__ == "__main__":
    unittest.main()
