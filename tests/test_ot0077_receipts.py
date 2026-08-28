from __future__ import annotations

import copy
import unittest

from open_trajectory_harness.ot0002 import canonical_json, sha256_bytes
from open_trajectory_harness.ot0077_receipts import (
    AuthoritativeBranchStore,
    EPISODE_RESET_TRANSITION,
    ENVIRONMENT_KEYS,
    NONVALID_PREDICTION_NOOP_CODE,
    POST_STATE_PROJECTION,
    RESET_AUTHORITY,
    SENTINEL_CHANNELS,
    SEEDED_AUTHORITY_DEFECTS,
    UPDATE_WITHOUT_PROJECTION,
    ReceiptChainBuilder,
    ReceiptError,
    authoritative_update_ancestry,
    causal_path_gates,
    chain_causal_evidence,
    checkpoint,
    consumer_runtime_ready,
    decode_blob,
    derive_identity,
    encode_blob,
    expected_mutation_code,
    make_consumer_facts,
    mutate_seeded_defect,
    projection_trace_equal,
    rollback_gates,
    seeded_authority_defect_gates,
    strict_online_surface,
    validate_branch_isolation,
    validate_chain,
    validate_chain_collection,
    validate_projection_consumer_substitution_rejection,
    validate_restored_suffix,
    validate_rewind_replay,
    validated_episode_resets,
)


def environment() -> dict[str, object]:
    value = {
        "architecture": "arm64",
        "git_commit": "a" * 40,
        "git_dirty": False,
        "os_family": "Darwin",
        "python_implementation": "CPython",
        "python_version": "3.13.7",
    }
    assert set(value) == ENVIRONMENT_KEYS
    return value


def _sentinel_results(label: str) -> list[dict[str, object]]:
    sentinel_nonce = derive_identity("test-sentinel-nonce", label)
    return [
        {
            "channel": channel,
            "checked": True,
            "observed": False,
            "planted": True,
            "sentinel_sha256": derive_identity(
                "sentinel", sentinel_nonce, channel
            ),
        }
        for channel in SENTINEL_CHANNELS
    ]


def consumer(
    label: str,
    *,
    prediction_status: str = "valid",
) -> dict[str, object]:
    """Return structurally valid facts that explicitly make no fresh-process claim."""

    attempt_status = (
        prediction_status
        if prediction_status in {"missing", "timeout"}
        else "completed"
    )
    return make_consumer_facts(
        process_challenge_sha256=derive_identity("test-process", label),
        workspace_challenge_sha256=derive_identity("test-workspace", label),
        response_bytes=canonical_json(
            {
                "prediction_status": prediction_status,
                "test_response": label,
            }
        ),
        descriptor_audit_pass=False,
        attempt_status=attempt_status,
        failure_code=(
            None if attempt_status == "completed" else f"consumer-{attempt_status}"
        ),
        prediction_status=prediction_status,
        process_boundary=(
            "unstarted" if attempt_status in {"missing", "timeout"} else "in-process"
        ),
        process_started=False,
        fresh_process_verified=False,
        workspace_observed=True,
        environment_fingerprint=environment(),
        sentinel_results=_sentinel_results(label),
    )


def fresh_consumer(
    label: str,
    *,
    case_id: str,
    condition_id: str,
    lineage_id: str,
    encounter_index: int,
    projection: bytes,
    public_query: dict[str, object] | None,
    prediction: int | None,
    mode: str,
) -> dict[str, object]:
    """Return runtime-ready facts retaining an exact canonical worker response."""

    process_challenge = derive_identity("test-process", label)
    response = {
        "candidate_count": 1,
        "case_id": case_id,
        "condition_id": condition_id,
        "consumer_id": process_challenge,
        "descriptor_audit_pass": True,
        "encounter_index": encounter_index,
        "environment_allowlist_pass": True,
        "environment_names": [
            "LANG",
            "LC_ALL",
            "OT0077_SURFACE",
            "PATH",
            "PYTHONHASHSEED",
            "PYTHONPATH",
            "__CF_USER_TEXT_ENCODING",
        ],
        "experiment_id": "OT-0077",
        "lineage_id": lineage_id,
        "mechanism_id": "test-worker-mechanism",
        "mode": mode,
        "prediction": prediction,
        "prediction_operations": 1,
        "projection_sha256": sha256_bytes(projection),
        "public_query_sha256": (
            sha256_bytes(canonical_json(public_query))
            if public_query is not None
            else None
        ),
        "response_chain_absent": True,
        "schema_version": 1,
        "state_bytes": len(projection),
        "workspace_empty_after": True,
        "workspace_empty_before": True,
    }
    return make_consumer_facts(
        process_challenge_sha256=process_challenge,
        workspace_challenge_sha256=derive_identity("test-workspace", label),
        response_bytes=canonical_json(response),
        descriptor_audit_pass=True,
        attempt_status="completed",
        failure_code=None,
        prediction_status="valid",
        process_boundary="one-exec",
        process_started=True,
        fresh_process_verified=True,
        workspace_observed=True,
        environment_fingerprint=environment(),
        sentinel_results=_sentinel_results(label),
    )


def query(index: int, *, episode_start: bool = False) -> dict[str, object]:
    return {
        "episode_start": episode_start,
        "feature_bits": format(index + 1, "012b"),
        "query_id": derive_identity("test-query", index, episode_start),
        "schema_version": 1,
    }


def build_chain(
    *,
    label: str = "live",
    branch_token: str = "genesis",
    branch_role: str = "genesis",
    horizon: int = 2,
    encounter_start: int = 0,
    encounter_count: int | None = None,
    initial_state: bytes = b"state-0",
    initial_projection: bytes = b"state-0",
    fork_parent_state_sha256: str | None = None,
    fork_parent_projection_sha256: str | None = None,
    condition_id: str | None = None,
    outcomes: tuple[int, ...] | None = None,
    lineage_class: str = "online-positive-surrogate",
    projection_mode: str = POST_STATE_PROJECTION,
    freeze_projection: bool = False,
    post_state_prefix: str = "state",
    runtime_ready: bool = False,
) -> dict[str, object]:
    if condition_id is None:
        condition_id = derive_identity("test-condition", "shared")
    if outcomes is None:
        outcomes = tuple(index & 1 for index in range(horizon))
    if encounter_count is None:
        encounter_count = horizon - encounter_start
    if len(outcomes) != encounter_count:
        raise ValueError("test outcomes must cover the exact branch suffix")
    task_sha256 = derive_identity("test-task")
    case_id = derive_identity("test-case")
    lineage_id = derive_identity("lineage", case_id, condition_id)
    first_query = query(
        encounter_start,
        episode_start=encounter_start == 0,
    )
    first_consumer = (
        fresh_consumer(
            f"{label}-0",
            case_id=case_id,
            condition_id=condition_id,
            lineage_id=lineage_id,
            encounter_index=encounter_start,
            projection=initial_projection,
            public_query=first_query,
            prediction=outcomes[0],
            mode="prediction",
        )
        if runtime_ready
        else consumer(f"{label}-0")
    )
    builder = ReceiptChainBuilder(
        task_sha256=task_sha256,
        case_id=case_id,
        case_index=0,
        horizon=horizon,
        condition_id=condition_id,
        display_label=label,
        lineage_class=lineage_class,
        branch_token=branch_token,
        surface=strict_online_surface(),
        initial_state=initial_state,
        initial_projection=initial_projection,
        first_consumer_facts=first_consumer,
        projection_mode=projection_mode,
        branch_role=branch_role,
        fork_parent_state_sha256=fork_parent_state_sha256,
        fork_parent_projection_sha256=fork_parent_projection_sha256,
        encounter_start=encounter_start,
        encounter_count=encounter_count,
    )
    authoritative_state = initial_state
    for index, outcome in enumerate(outcomes):
        absolute_index = encounter_start + index
        post_state = f"{post_state_prefix}-{absolute_index + 1}".encode()
        next_projection = (
            initial_projection
            if freeze_projection
            else post_state
        )
        current_query = query(
            absolute_index,
            episode_start=absolute_index == 0,
        )
        terminal = index == len(outcomes) - 1
        if runtime_ready:
            next_target = horizon if terminal else absolute_index + 1
            next_query = (
                None
                if terminal
                else query(next_target, episode_start=next_target == 0)
            )
            next_prediction = None if terminal else outcomes[index + 1]
            next_consumer = fresh_consumer(
                f"{label}-{index + 1}",
                case_id=case_id,
                condition_id=condition_id,
                lineage_id=lineage_id,
                encounter_index=next_target,
                projection=next_projection,
                public_query=next_query,
                prediction=next_prediction,
                mode="terminal-audit" if terminal else "prediction",
            )
        else:
            next_consumer = consumer(f"{label}-{index + 1}")
        builder.append_encounter(
            public_query=current_query,
            episode_index=0,
            prediction=outcome,
            outcome=outcome,
            update_decision="update",
            authoritative_pre_state=authoritative_state,
            update_payload=f"update-{absolute_index}".encode(),
            post_state=post_state,
            next_projection=next_projection,
            next_consumer_facts=next_consumer,
        )
        authoritative_state = post_state
    return builder.finish()


def build_frozen_chain(*, label: str = "matched-frozen") -> dict[str, object]:
    initial_state = b"state-0"
    initial_projection = b"state-0"
    builder = ReceiptChainBuilder(
        task_sha256=derive_identity("test-task"),
        case_id=derive_identity("test-case"),
        case_index=0,
        horizon=2,
        condition_id=derive_identity("test-condition", label),
        display_label=label,
        lineage_class="required-nonlearning-control",
        branch_token="genesis",
        surface=strict_online_surface(),
        initial_state=initial_state,
        initial_projection=initial_projection,
        first_consumer_facts=consumer(f"{label}-0"),
    )
    for index, outcome in enumerate((0, 1)):
        builder.append_encounter(
            public_query=query(index, episode_start=index == 0),
            episode_index=0,
            prediction=outcome,
            outcome=outcome,
            update_decision="no-op",
            authoritative_pre_state=initial_state,
            update_payload=f"matched-no-op-{index}".encode(),
            post_state=initial_state,
            next_projection=initial_projection,
            next_consumer_facts=consumer(f"{label}-{index + 1}"),
        )
    return builder.finish()


class ReceiptBlobTests(unittest.TestCase):
    def test_blob_envelope_is_exact_and_bounded(self) -> None:
        envelope = encode_blob(b"opaque\x00bytes", limit=32, label="state")
        self.assertEqual(
            decode_blob(envelope, limit=32, label="state"), b"opaque\x00bytes"
        )
        malformed = copy.deepcopy(envelope)
        malformed["base64"] += "="
        with self.assertRaisesRegex(ReceiptError, "blob-identity"):
            decode_blob(malformed, limit=32, label="state")
        with self.assertRaisesRegex(ReceiptError, "over-budget"):
            encode_blob(b"x" * 33, limit=32, label="state")


class ReceiptChainTests(unittest.TestCase):
    def test_complete_chain_binds_every_causal_stage_and_terminal_audit(self) -> None:
        chain = build_chain(runtime_ready=True)
        result = validate_chain(chain, require_online_admissible=True)
        self.assertTrue(result.authority_eligible)
        self.assertEqual(result.encounter_count, 2)
        self.assertEqual(result.errors, 0)
        self.assertEqual(len(causal_path_gates(chain, require_online_admissible=True)), 9)
        self.assertTrue(all(causal_path_gates(chain).values()))
        self.assertEqual(len(chain["receipt_order"]), 24)
        self.assertEqual(
            [item["kind"] for item in chain["receipt_order"][:6]],
            [
                "case",
                "reachable-surface",
                "lineage",
                "state",
                "projection",
                "consumer",
            ],
        )
        self.assertEqual(
            [item["kind"] for item in chain["receipt_order"][6:15]],
            [
                "encounter",
                "query",
                "pre-state",
                "prediction",
                "outcome",
                "update",
                "state",
                "projection",
                "consumer",
            ],
        )
        terminal = chain["receipt_order"][-1]
        self.assertEqual(terminal["payload"]["mode"], "terminal-audit")
        self.assertEqual(terminal["payload"]["facts"]["workspace_entries_after"], [])

    def test_missing_invalid_and_timed_out_predictions_are_exact_noops_and_retain_denominator(
        self,
    ) -> None:
        for ordinal, status in enumerate(("missing", "invalid", "timeout")):
            with self.subTest(status=status):
                builder = ReceiptChainBuilder(
                    task_sha256=derive_identity("test-task", status),
                    case_id=derive_identity("test-case", status),
                    case_index=0,
                    horizon=1,
                    condition_id=derive_identity("test-condition", status),
                    display_label=f"{status} prediction",
                    lineage_class="online-positive-surrogate",
                    branch_token="genesis",
                    surface=strict_online_surface(),
                    initial_state=b"unchanged",
                    initial_projection=b"unchanged",
                    first_consumer_facts=consumer(
                        f"{status}-0",
                        prediction_status=status,
                    ),
                )
                builder.append_encounter(
                    public_query=query(8 + ordinal, episode_start=True),
                    episode_index=0,
                    prediction=None,
                    prediction_status=status,
                    outcome=1,
                    update_decision="no-op",
                    authoritative_pre_state=b"unchanged",
                    consequence_binding="withheld",
                    delivered_outcome=None,
                    update_payload=b"",
                    post_state=b"unchanged",
                    next_projection=b"unchanged",
                    next_consumer_facts=consumer(f"{status}-1"),
                )
                chain = builder.finish()
                result = validate_chain(
                    chain, require_online_admissible=True
                )
                evidence = chain_causal_evidence(chain)
                update = chain["receipt_order"][11]["payload"]
                self.assertEqual(result.encounter_count, 1)
                self.assertEqual(result.errors, 1)
                self.assertFalse(result.authority_eligible)
                self.assertEqual(result.accepted_updates, 0)
                self.assertFalse(result.candidate_state_changed)
                self.assertFalse(result.active_projection_changed)
                self.assertEqual(update["consequence_binding"], "withheld")
                self.assertIsNone(update["delivered_outcome"])
                self.assertEqual(update["decision"], "no-op")
                self.assertEqual(
                    decode_blob(
                        update["update_payload"],
                        limit=2_048,
                        label="nonvalid no-op payload",
                    ),
                    b"",
                )
                self.assertEqual(evidence["accepted_updates"], 0)

    def test_stale_label_advances_across_an_invalid_prediction_slot(self) -> None:
        def stale_chain(delivered_outcome: int) -> dict[str, object]:
            builder = ReceiptChainBuilder(
                task_sha256=derive_identity("test-task", "stale-invalid-slot"),
                case_id=derive_identity("test-case", "stale-invalid-slot"),
                case_index=0,
                horizon=3,
                condition_id=derive_identity(
                    "test-condition", "stale-invalid-slot"
                ),
                display_label="stale invalid-slot clock",
                lineage_class="causal-intervention",
                branch_token="genesis",
                surface=strict_online_surface(),
                initial_state=b"state-0",
                initial_projection=b"state-0",
                first_consumer_facts=consumer("stale-invalid-slot-0"),
            )
            builder.append_encounter(
                public_query=query(40, episode_start=True),
                episode_index=0,
                prediction=0,
                outcome=0,
                update_decision="update",
                authoritative_pre_state=b"state-0",
                update_payload=b"update-0",
                post_state=b"state-1",
                next_projection=b"state-1",
                next_consumer_facts=consumer(
                    "stale-invalid-slot-1",
                    prediction_status="invalid",
                ),
            )
            builder.append_encounter(
                public_query=query(41),
                episode_index=0,
                prediction=None,
                prediction_status="invalid",
                outcome=1,
                update_decision="no-op",
                authoritative_pre_state=b"state-1",
                consequence_binding="withheld",
                delivered_outcome=None,
                update_payload=b"",
                post_state=b"state-1",
                next_projection=b"state-1",
                next_consumer_facts=consumer("stale-invalid-slot-2"),
            )
            builder.append_encounter(
                public_query=query(42),
                episode_index=0,
                prediction=0,
                outcome=0,
                update_decision="update",
                authoritative_pre_state=b"state-1",
                consequence_binding="one-step-stale",
                delivered_outcome=delivered_outcome,
                update_payload=b"update-2",
                post_state=b"state-2",
                next_projection=b"state-2",
                next_consumer_facts=consumer("stale-invalid-slot-3"),
            )
            return builder.finish()

        validation = validate_chain(stale_chain(1))
        self.assertEqual(validation.encounter_count, 3)
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(stale_chain(0))
        self.assertEqual(raised.exception.code, "wrong-update-parent")

    def test_nonvalid_prediction_cannot_receive_outcome_update_or_state_projection_change(
        self,
    ) -> None:
        invalid_attempts = (
            {
                "consequence_binding": "current",
                "delivered_outcome": 1,
                "update_decision": "no-op",
                "update_payload": b"",
                "post_state": b"same",
                "next_projection": b"same",
            },
            {
                "consequence_binding": "withheld",
                "delivered_outcome": None,
                "update_decision": "update",
                "update_payload": b"candidate",
                "post_state": b"changed",
                "next_projection": b"changed",
            },
            {
                "consequence_binding": "withheld",
                "delivered_outcome": None,
                "update_decision": "no-op",
                "update_payload": b"nonempty",
                "post_state": b"same",
                "next_projection": b"same",
            },
            {
                "consequence_binding": "withheld",
                "delivered_outcome": None,
                "update_decision": "no-op",
                "update_payload": b"",
                "post_state": b"same",
                "next_projection": b"changed",
            },
        )
        for ordinal, attempt in enumerate(invalid_attempts):
            with self.subTest(ordinal=ordinal):
                builder = ReceiptChainBuilder(
                    task_sha256=derive_identity("test-task", "nonvalid", ordinal),
                    case_id=derive_identity("test-case", "nonvalid", ordinal),
                    case_index=0,
                    horizon=1,
                    condition_id=derive_identity(
                        "test-condition", "nonvalid", ordinal
                    ),
                    display_label="nonvalid no-op authority",
                    lineage_class="online-positive-surrogate",
                    branch_token="genesis",
                    surface=strict_online_surface(),
                    initial_state=b"same",
                    initial_projection=b"same",
                    first_consumer_facts=consumer(f"nonvalid-{ordinal}-0"),
                )
                with self.assertRaises(ReceiptError) as raised:
                    builder.append_encounter(
                        public_query=query(20 + ordinal, episode_start=True),
                        episode_index=0,
                        prediction=None,
                        prediction_status="timeout",
                        outcome=1,
                        authoritative_pre_state=b"same",
                        next_consumer_facts=consumer(
                            f"nonvalid-{ordinal}-1"
                        ),
                        **attempt,
                    )
                self.assertEqual(
                    raised.exception.code, NONVALID_PREDICTION_NOOP_CODE
                )

    def test_replay_validation_rejects_update_authority_added_to_nonvalid_prediction(
        self,
    ) -> None:
        chain = build_chain(horizon=1)
        mutant = copy.deepcopy(chain)
        prediction = mutant["receipt_order"][9]["payload"]
        prediction["prediction"] = None
        prediction["status"] = "timeout"
        consumer_facts = mutant["receipt_order"][5]["payload"]["facts"]
        consumer_facts["attempt_status"] = "timeout"
        consumer_facts["failure_code"] = "consumer-timeout"
        consumer_facts["prediction_status"] = "timeout"
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(mutant)
        self.assertEqual(raised.exception.code, NONVALID_PREDICTION_NOOP_CODE)

    def test_noop_is_explicit_and_must_preserve_state(self) -> None:
        builder = ReceiptChainBuilder(
            task_sha256=derive_identity("test-task", "noop"),
            case_id=derive_identity("test-case", "noop"),
            case_index=0,
            horizon=1,
            condition_id=derive_identity("test-condition", "noop"),
            display_label="no-op",
            lineage_class="causal-intervention",
            branch_token="genesis",
            surface=strict_online_surface(),
            initial_state=b"same",
            initial_projection=b"same",
            first_consumer_facts=consumer("noop-0"),
        )
        builder.append_encounter(
            public_query=query(9, episode_start=True),
            episode_index=0,
            prediction=0,
            outcome=1,
            update_decision="no-op",
            authoritative_pre_state=b"same",
            consequence_binding="withheld",
            update_payload=b"withheld",
            post_state=b"same",
            next_projection=b"same",
            next_consumer_facts=consumer("noop-1"),
        )
        result = validate_chain(builder.finish())
        self.assertFalse(result.authority_eligible)
        self.assertEqual(result.errors, 1)

    def test_fresh_workspace_response_chain_environment_and_sentinels_fail_closed(self) -> None:
        chain = build_chain(runtime_ready=True)
        facts = chain["receipt_order"][5]["payload"]["facts"]
        mutations = (
            ("workspace_entries_before", ["unexpected"], "fresh-workspace"),
            ("response_chain_ids", [derive_identity("response")], "response-chain"),
        )
        for key, replacement, code in mutations:
            with self.subTest(key=key):
                mutant = copy.deepcopy(chain)
                mutant["receipt_order"][5]["payload"]["facts"][key] = replacement
                with self.assertRaises(ReceiptError) as raised:
                    validate_chain(mutant)
                self.assertEqual(raised.exception.code, code)
        sentinel = copy.deepcopy(chain)
        sentinel["receipt_order"][5]["payload"]["facts"][
            "forbidden_channel_sentinels"
        ].pop()
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(sentinel)
        self.assertEqual(raised.exception.code, "forbidden-channel-sentinel")
        environment_mutant = copy.deepcopy(chain)
        environment_mutant["receipt_order"][5]["payload"]["facts"][
            "environment_fingerprint"
        ]["executable_path"] = "/private/path"
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(environment_mutant)
        self.assertEqual(raised.exception.code, "environment-allowlist")
        self.assertEqual(facts["workspace_entries_before"], [])

    def test_every_consumer_must_have_fresh_process_and_workspace_identity(self) -> None:
        chain = build_chain(runtime_ready=True)
        mutant = copy.deepcopy(chain)
        first = mutant["receipt_order"][5]["payload"]["facts"]
        second = mutant["receipt_order"][14]["payload"]["facts"]
        second["process_instance_id"] = first["process_instance_id"]
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(mutant)
        self.assertEqual(raised.exception.code, "fresh-consumer")

    def test_retained_worker_response_binds_status_prediction_and_digest(self) -> None:
        chain = build_chain(horizon=1, runtime_ready=True)
        facts = chain["receipt_order"][5]["payload"]["facts"]
        self.assertTrue(consumer_runtime_ready(facts))

        status_mutant = copy.deepcopy(chain)
        status_mutant["receipt_order"][5]["payload"]["facts"][
            "prediction_status"
        ] = "invalid"
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(status_mutant)
        self.assertEqual(raised.exception.code, "fresh-consumer")
        self.assertIn("receipt status differs", str(raised.exception))

        digest_mutant = copy.deepcopy(chain)
        digest_mutant["receipt_order"][9]["payload"][
            "consumer_response_sha256"
        ] = derive_identity("unrelated-consumer-response")
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(digest_mutant)
        self.assertEqual(raised.exception.code, "fresh-consumer")
        self.assertIn("does not bind", str(raised.exception))

        response_mutant = copy.deepcopy(chain)
        case_id = chain["receipt_order"][0]["context"]["case_id"]
        lineage = chain["receipt_order"][2]["payload"]
        wrong_response = fresh_consumer(
            "retained-prediction-mismatch",
            case_id=case_id,
            condition_id=lineage["condition_id"],
            lineage_id=lineage["lineage_id"],
            encounter_index=0,
            projection=b"state-0",
            public_query=query(0, episode_start=True),
            prediction=1,
            mode="prediction",
        )
        response_mutant["receipt_order"][5]["payload"]["facts"] = wrong_response
        response_mutant["receipt_order"][9]["payload"][
            "consumer_response_sha256"
        ] = wrong_response["response_sha256"]
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(response_mutant)
        self.assertEqual(raised.exception.code, "fresh-consumer")
        self.assertIn("worker response identity differs", str(raised.exception))


class AuthoritativeUpdaterProjectionTests(unittest.TestCase):
    def test_update_without_projection_has_two_exact_state_parents_and_frozen_actor_trace(
        self,
    ) -> None:
        chain = build_chain(
            label="update-without-projection",
            lineage_class="causal-intervention",
            projection_mode=UPDATE_WITHOUT_PROJECTION,
            freeze_projection=True,
        )
        validation = validate_chain(chain)
        self.assertEqual(validation.projection_mode, UPDATE_WITHOUT_PROJECTION)
        self.assertEqual(validation.accepted_updates, 2)
        self.assertEqual(validation.episode_reset_count, 0)
        self.assertTrue(validation.candidate_state_changed)
        self.assertFalse(validation.active_projection_changed)

        ancestry = authoritative_update_ancestry(chain)
        first, second = ancestry["updates"]
        self.assertEqual(
            first["authoritative_pre_state_receipt_sha256"],
            chain["receipt_order"][3]["receipt_sha256"],
        )
        self.assertEqual(
            second["authoritative_pre_state_receipt_sha256"],
            first["candidate_post_state_receipt_sha256"],
        )
        self.assertEqual(
            second["authoritative_pre_state_sha256"],
            first["candidate_post_state_sha256"],
        )
        self.assertNotEqual(
            second["authoritative_pre_state_sha256"],
            second["delivered_projection_sha256"],
        )

        evidence = chain_causal_evidence(chain)
        self.assertEqual(
            set(evidence),
            {
                "accepted_updates",
                "active_projection_changed",
                "candidate_state_changed",
                "consumed_projection_sha256s",
                "terminal_projection_sha256",
            },
        )
        self.assertEqual(len(evidence["consumed_projection_sha256s"]), 2)
        self.assertTrue(projection_trace_equal(chain, build_frozen_chain()))

    def test_stale_actor_projection_cannot_be_named_as_second_update_parent(self) -> None:
        builder = ReceiptChainBuilder(
            task_sha256=derive_identity("test-task", "wrong-parent"),
            case_id=derive_identity("test-case", "wrong-parent"),
            case_index=0,
            horizon=2,
            condition_id=derive_identity("test-condition", "wrong-parent"),
            display_label="update without projection",
            lineage_class="causal-intervention",
            branch_token="genesis",
            surface=strict_online_surface(),
            initial_state=b"authoritative-0",
            initial_projection=b"authoritative-0",
            first_consumer_facts=consumer("wrong-parent-0"),
            projection_mode=UPDATE_WITHOUT_PROJECTION,
        )
        builder.append_encounter(
            public_query=query(0, episode_start=True),
            episode_index=0,
            prediction=0,
            outcome=0,
            update_decision="update",
            authoritative_pre_state=b"authoritative-0",
            update_payload=b"first",
            post_state=b"authoritative-1",
            next_projection=b"authoritative-0",
            next_consumer_facts=consumer("wrong-parent-1"),
        )
        with self.assertRaises(ReceiptError) as raised:
            builder.append_encounter(
                public_query=query(1),
                episode_index=0,
                prediction=1,
                outcome=1,
                update_decision="update",
                # This is the rejected OT-0075 pattern: computation resumes
                # from the actor's frozen projection, not authoritative-1.
                authoritative_pre_state=b"authoritative-0",
                update_payload=b"second",
                post_state=b"wrong-child",
                next_projection=b"authoritative-0",
                next_consumer_facts=consumer("wrong-parent-2"),
            )
        self.assertEqual(raised.exception.code, "wrong-update-parent")

    def test_serialized_stale_state_attestation_fails_closed(self) -> None:
        chain = build_chain(
            label="serialized-wrong-parent",
            lineage_class="causal-intervention",
            projection_mode=UPDATE_WITHOUT_PROJECTION,
            freeze_projection=True,
        )
        mutant = copy.deepcopy(chain)
        second_update = mutant["receipt_order"][15 + 5]
        second_update["payload"]["authoritative_pre_state_sha256"] = encode_blob(
            b"state-0", limit=2048, label="stale actor projection"
        )["sha256"]
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(mutant)
        self.assertEqual(raised.exception.code, "wrong-update-parent")

    def test_only_declared_causal_intervention_may_diverge_state_and_projection(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "causal intervention"):
            ReceiptChainBuilder(
                task_sha256=derive_identity("test-task", "mode-authority"),
                case_id=derive_identity("test-case", "mode-authority"),
                case_index=0,
                horizon=1,
                condition_id=derive_identity("test-condition", "mode-authority"),
                display_label="not an intervention",
                lineage_class="online-positive-surrogate",
                branch_token="genesis",
                surface=strict_online_surface(),
                initial_state=b"state",
                initial_projection=b"state",
                first_consumer_facts=consumer("mode-authority-0"),
                projection_mode=UPDATE_WITHOUT_PROJECTION,
            )

        builder = ReceiptChainBuilder(
            task_sha256=derive_identity("test-task", "undeclared-cut"),
            case_id=derive_identity("test-case", "undeclared-cut"),
            case_index=0,
            horizon=1,
            condition_id=derive_identity("test-condition", "undeclared-cut"),
            display_label="ordinary lineage",
            lineage_class="causal-intervention",
            branch_token="genesis",
            surface=strict_online_surface(),
            initial_state=b"state-0",
            initial_projection=b"state-0",
            first_consumer_facts=consumer("undeclared-cut-0"),
        )
        with self.assertRaises(ReceiptError) as raised:
            builder.append_encounter(
                public_query=query(0, episode_start=True),
                episode_index=0,
                prediction=0,
                outcome=0,
                update_decision="update",
                authoritative_pre_state=b"state-0",
                update_payload=b"candidate",
                post_state=b"state-1",
                next_projection=b"state-0",
                next_consumer_facts=consumer("undeclared-cut-1"),
            )
        self.assertEqual(raised.exception.code, "stale-projection")

    def test_collection_enforces_global_freshness_across_lineages(self) -> None:
        first = build_chain(
            label="collection-a",
            branch_token="a",
            runtime_ready=True,
        )
        second = build_chain(
            label="collection-b",
            branch_token="b",
            condition_id=derive_identity("test-condition", "collection-b"),
            runtime_ready=True,
        )
        receipt = validate_chain_collection(
            [first, second],
            online_admissible_trace_ids=[
                first["trace_sha256"],
                second["trace_sha256"],
            ],
        )
        self.assertEqual(receipt["chain_count"], 2)
        self.assertEqual(receipt["fresh_consumer_count"], 6)
        reused = build_chain(
            label="collection-a",
            branch_token="reused",
            runtime_ready=True,
        )
        self.assertNotEqual(first["trace_sha256"], reused["trace_sha256"])
        with self.assertRaises(ReceiptError) as raised:
            validate_chain_collection([first, reused])
        self.assertEqual(raised.exception.code, "fresh-consumer")


class EpisodeResetReceiptTests(unittest.TestCase):
    @staticmethod
    def build_reset_chain() -> dict[str, object]:
        builder = ReceiptChainBuilder(
            task_sha256=derive_identity("test-task", "episode-reset"),
            case_id=derive_identity("test-case", "episode-reset"),
            case_index=0,
            horizon=3,
            condition_id=derive_identity("test-condition", "episode-reset"),
            display_label="cross-episode state reset",
            lineage_class="causal-intervention",
            branch_token="genesis",
            surface=strict_online_surface(),
            initial_state=b"genesis",
            initial_projection=b"genesis",
            first_consumer_facts=consumer("episode-reset-0"),
        )
        builder.append_encounter(
            public_query=query(0, episode_start=True),
            episode_index=0,
            prediction=0,
            outcome=0,
            update_decision="update",
            authoritative_pre_state=b"genesis",
            update_payload=b"ordinary-update",
            post_state=b"state-1",
            next_projection=b"state-1",
            next_consumer_facts=consumer("episode-reset-1"),
        )
        builder.append_encounter(
            public_query=query(1),
            episode_index=0,
            prediction=1,
            outcome=1,
            update_decision="update",
            authoritative_pre_state=b"state-1",
            update_payload=b"candidate-then-controller-reset",
            post_state=b"genesis",
            next_projection=b"genesis",
            next_consumer_facts=consumer("episode-reset-2"),
            state_transition=EPISODE_RESET_TRANSITION,
            candidate_post_state=b"candidate-state-2",
            reset_next_episode_index=1,
        )
        builder.append_encounter(
            public_query=query(2, episode_start=True),
            episode_index=1,
            prediction=0,
            outcome=0,
            update_decision="update",
            authoritative_pre_state=b"genesis",
            update_payload=b"post-reset-update",
            post_state=b"state-3",
            next_projection=b"state-3",
            next_consumer_facts=consumer("episode-reset-3"),
        )
        return builder.finish()

    def test_reset_binds_candidate_controller_authority_root_and_next_episode(self) -> None:
        chain = self.build_reset_chain()
        validation = validate_chain(chain)
        self.assertEqual(validation.episode_reset_count, 1)
        evidence = validated_episode_resets(chain)
        self.assertEqual(evidence["episode_reset_count"], 1)
        reset = evidence["resets"][0]
        self.assertEqual(reset["reset_authority"], RESET_AUTHORITY)
        self.assertEqual(reset["encounter_index"], 1)
        self.assertEqual(reset["target_encounter_index"], 2)
        self.assertEqual(reset["target_episode_index"], 1)
        self.assertNotEqual(
            reset["candidate_post_state_sha256"], reset["post_state_sha256"]
        )
        update = chain["receipt_order"][15 + 5]
        self.assertEqual(
            [parent["role"] for parent in update["parents"]],
            [
                "pre-state",
                "outcome",
                "prediction",
                "reset-target-state",
                "reset-target-projection",
            ],
        )

    def test_reset_target_and_following_episode_mutations_fail_closed(self) -> None:
        chain = self.build_reset_chain()
        target_mutant = copy.deepcopy(chain)
        target_mutant["receipt_order"][15 + 5]["payload"]["state_transition"][
            "reset_target_state_receipt_sha256"
        ] = "0" * 64
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(target_mutant)
        self.assertEqual(raised.exception.code, "episode-reset-transition")

        boundary_mutant = copy.deepcopy(chain)
        boundary_mutant["receipt_order"][24]["payload"]["episode_start"] = False
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(boundary_mutant)
        self.assertEqual(raised.exception.code, "episode-reset-transition")

    def test_builder_rejects_implicit_or_nonroot_reset(self) -> None:
        builder = ReceiptChainBuilder(
            task_sha256=derive_identity("test-task", "bad-reset"),
            case_id=derive_identity("test-case", "bad-reset"),
            case_index=0,
            horizon=2,
            condition_id=derive_identity("test-condition", "bad-reset"),
            display_label="bad reset",
            lineage_class="causal-intervention",
            branch_token="genesis",
            surface=strict_online_surface(),
            initial_state=b"root",
            initial_projection=b"root",
            first_consumer_facts=consumer("bad-reset-0"),
        )
        with self.assertRaisesRegex(ValueError, "candidate post-state"):
            builder.append_encounter(
                public_query=query(0, episode_start=True),
                episode_index=0,
                prediction=0,
                outcome=0,
                update_decision="update",
                authoritative_pre_state=b"root",
                update_payload=b"bad-reset",
                post_state=b"root",
                next_projection=b"root",
                next_consumer_facts=consumer("bad-reset-1"),
                state_transition=EPISODE_RESET_TRANSITION,
                reset_next_episode_index=1,
            )

        with self.assertRaises(ReceiptError) as raised:
            builder.append_encounter(
                public_query=query(0, episode_start=True),
                episode_index=0,
                prediction=0,
                outcome=0,
                update_decision="update",
                authoritative_pre_state=b"root",
                update_payload=b"bad-reset",
                post_state=b"not-root",
                next_projection=b"not-root",
                next_consumer_facts=consumer("bad-reset-1"),
                state_transition=EPISODE_RESET_TRANSITION,
                candidate_post_state=b"candidate",
                reset_next_episode_index=1,
            )
        self.assertEqual(raised.exception.code, "episode-reset-transition")


class SeededAuthorityMutationTests(unittest.TestCase):
    def test_all_and_only_frozen_seeded_defects_are_implemented(self) -> None:
        self.assertEqual(len(SEEDED_AUTHORITY_DEFECTS), 19)
        self.assertEqual(len(set(SEEDED_AUTHORITY_DEFECTS)), 19)
        chain = build_chain(label="active")
        donor = build_chain(
            label="sibling",
            branch_token="sibling",
            condition_id=derive_identity("test-condition", "sibling"),
        )
        for defect in SEEDED_AUTHORITY_DEFECTS:
            with self.subTest(defect=defect):
                mutant = mutate_seeded_defect(chain, defect, donor_chain=donor)
                with self.assertRaises(ReceiptError) as raised:
                    validate_chain(mutant, require_online_admissible=True)
                self.assertEqual(raised.exception.code, expected_mutation_code(defect))
        gates = seeded_authority_defect_gates(chain, donor_chain=donor)
        self.assertEqual(tuple(gates), SEEDED_AUTHORITY_DEFECTS)
        self.assertTrue(all(gates.values()))

    def test_real_cross_lineage_projection_and_consumer_bind_is_rejected(self) -> None:
        active = build_chain(label="wrong-lineage-active")
        donor = build_chain(
            label="wrong-lineage-donor",
            branch_token="donor",
            condition_id=derive_identity("test-condition", "wrong-lineage-donor"),
        )
        receipt = validate_projection_consumer_substitution_rejection(
            active,
            donor,
            producer_encounter_index=0,
        )
        self.assertTrue(receipt["substitution_rejected"])
        self.assertEqual(
            receipt["observed_rejection_code"],
            "sibling-branch-substitution",
        )
        self.assertNotEqual(
            receipt["active_lineage_id"], receipt["donor_lineage_id"]
        )

    def test_negative_reference_label_never_grants_authority(self) -> None:
        chain = build_chain()
        mutant = mutate_seeded_defect(
            chain, "reference-label-on-negative-lineage"
        )
        with self.assertRaisesRegex(ReceiptError, "reference-label-on-negative"):
            validate_chain(mutant, require_online_admissible=True)


class RollbackAndBranchTests(unittest.TestCase):
    def test_same_suffix_replay_is_byte_exact(self) -> None:
        chain = build_chain()
        receipt = validate_rewind_replay(
            chain, copy.deepcopy(chain), checkpoint_index=0
        )
        self.assertEqual(receipt["original_trace_sha256"], chain["trace_sha256"])
        self.assertEqual(receipt["replay_trace_sha256"], chain["trace_sha256"])

    def test_common_checkpoint_forks_are_isolated_and_cross_branch_projection_fails(self) -> None:
        parent = build_chain(label="parent")
        point = checkpoint(parent, 0)
        state = decode_blob(point["state"], limit=2048, label="checkpoint state")
        projection = decode_blob(
            point["projection"], limit=2048, label="checkpoint projection"
        )
        condition_id = derive_identity("test-condition", "shared")
        rewind = build_chain(
            label="rewind",
            branch_token="rewind",
            branch_role="rewind-replay",
            horizon=2,
            encounter_start=1,
            encounter_count=1,
            initial_state=state,
            initial_projection=projection,
            fork_parent_state_sha256=point["state_receipt_sha256"],
            fork_parent_projection_sha256=point["projection_receipt_sha256"],
            condition_id=condition_id,
            outcomes=(1,),
        )
        alternate = build_chain(
            label="alternate",
            branch_token="alternate",
            branch_role="alternate",
            horizon=2,
            encounter_start=1,
            encounter_count=1,
            initial_state=state,
            initial_projection=projection,
            fork_parent_state_sha256=point["state_receipt_sha256"],
            fork_parent_projection_sha256=point["projection_receipt_sha256"],
            condition_id=condition_id,
            outcomes=(0,),
            post_state_prefix="alternate-state",
        )
        restored = validate_restored_suffix(
            parent,
            rewind,
            checkpoint_index=0,
        )
        self.assertEqual(restored["suffix_encounter_count"], 1)
        receipt = validate_branch_isolation(
            parent, rewind, alternate, checkpoint_index=0
        )
        rewind_validation = validate_chain(rewind)
        alternate_validation = validate_chain(alternate)
        self.assertTrue(receipt["sibling_projection_rejected"])
        self.assertTrue(receipt["branches_observationally_distinct"])
        self.assertTrue(receipt["consumer_identities_disjoint"])
        self.assertTrue(receipt["active_branch_unchanged"])
        self.assertTrue(receipt["active_projection_unchanged"])
        self.assertTrue(receipt["active_projection_matches_parent"])
        self.assertEqual(receipt["branch_store_operation_count"], 4)
        self.assertEqual(
            receipt["active_branch_id"], rewind_validation.branch_id
        )
        self.assertNotEqual(
            receipt["active_projection_sha256"],
            alternate_validation.terminal_projection_sha256,
        )
        self.assertNotEqual(
            rewind_validation.branch_id, alternate_validation.branch_id
        )

        # Exercise the same authoritative operation directly.  The alternate
        # is a retained, valid, projection-distinct branch, yet inactive
        # retention cannot implicitly replace the selected rewind projection.
        store = AuthoritativeBranchStore(parent)
        store.retain_inactive(rewind)
        store.activate(rewind_validation.branch_id)
        selected_before = store.active_projection_snapshot()
        retention = store.retain_inactive(alternate)
        selected_after = store.active_projection_snapshot()
        self.assertEqual(selected_after, selected_before)
        self.assertEqual(
            selected_after["active_branch_id"], rewind_validation.branch_id
        )
        self.assertNotEqual(
            selected_after["projection_sha256"],
            alternate_validation.terminal_projection_sha256,
        )
        self.assertEqual(
            retention["payload"]["operation"], "retain-inactive"
        )
        self.assertEqual(len(store.operation_receipts()), 4)

        gates = rollback_gates(
            parent,
            copy.deepcopy(parent),
            rewind,
            alternate,
            checkpoint_index=0,
        )
        self.assertEqual(
            set(gates),
            {
                "rewind_to_checkpoint",
                "same_suffix_byte_exact_replay",
                "alternate_suffix_branch_isolated",
                "inactive_sibling_cannot_affect_active_projection",
                "cross_branch_substitution_rejected",
            },
        )
        self.assertTrue(all(gates.values()))

    def test_rewind_branch_that_only_forks_checkpoint_but_changes_suffix_is_rejected(
        self,
    ) -> None:
        parent = build_chain(label="parent-negative")
        point = checkpoint(parent, 0)
        state = decode_blob(point["state"], limit=2048, label="checkpoint state")
        projection = decode_blob(
            point["projection"], limit=2048, label="checkpoint projection"
        )
        wrong_rewind = build_chain(
            label="wrong-rewind",
            branch_token="wrong-rewind",
            branch_role="rewind-replay",
            horizon=2,
            encounter_start=1,
            encounter_count=1,
            initial_state=state,
            initial_projection=projection,
            fork_parent_state_sha256=point["state_receipt_sha256"],
            fork_parent_projection_sha256=point["projection_receipt_sha256"],
            outcomes=(0,),
        )
        with self.assertRaises(ReceiptError) as raised:
            validate_restored_suffix(parent, wrong_rewind, checkpoint_index=0)
        self.assertEqual(raised.exception.code, "restored-suffix")


if __name__ == "__main__":
    unittest.main()
