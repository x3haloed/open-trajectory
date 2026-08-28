from __future__ import annotations

import copy
import unittest

from open_trajectory_harness.ot0076_receipts import (
    ENVIRONMENT_KEYS,
    POST_STATE_PROJECTION,
    SEEDED_AUTHORITY_DEFECTS,
    UPDATE_WITHOUT_PROJECTION,
    ReceiptChainBuilder,
    ReceiptError,
    authoritative_update_ancestry,
    causal_path_gates,
    chain_causal_evidence,
    checkpoint,
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
    validate_rewind_replay,
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


def consumer(label: str) -> dict[str, object]:
    return make_consumer_facts(
        process_instance_id=derive_identity("test-process", label),
        workspace_instance_id=derive_identity("test-workspace", label),
        environment_fingerprint=environment(),
        sentinel_nonce_sha256=derive_identity("test-sentinel-nonce", label),
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
) -> dict[str, object]:
    if condition_id is None:
        condition_id = derive_identity("test-condition", "shared")
    if outcomes is None:
        outcomes = tuple(index & 1 for index in range(horizon))
    builder = ReceiptChainBuilder(
        task_sha256=derive_identity("test-task"),
        case_id=derive_identity("test-case"),
        case_index=0,
        horizon=horizon,
        condition_id=condition_id,
        display_label=label,
        lineage_class=lineage_class,
        branch_token=branch_token,
        surface=strict_online_surface(),
        initial_state=initial_state,
        initial_projection=initial_projection,
        first_consumer_facts=consumer(f"{label}-0"),
        projection_mode=projection_mode,
        branch_role=branch_role,
        fork_parent_state_sha256=fork_parent_state_sha256,
        fork_parent_projection_sha256=fork_parent_projection_sha256,
        encounter_start=encounter_start,
        encounter_count=encounter_count,
    )
    authoritative_state = initial_state
    for index, outcome in enumerate(outcomes):
        post_state = f"state-{index + 1}".encode()
        next_projection = (
            initial_projection
            if freeze_projection
            else post_state
        )
        builder.append_encounter(
            public_query=query(index, episode_start=index == 0),
            episode_index=0,
            prediction=outcome,
            outcome=outcome,
            update_decision="update",
            authoritative_pre_state=authoritative_state,
            update_payload=f"update-{index}".encode(),
            post_state=post_state,
            next_projection=next_projection,
            next_consumer_facts=consumer(f"{label}-{index + 1}"),
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
        chain = build_chain()
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

    def test_missing_invalid_and_timed_out_predictions_retain_denominator(self) -> None:
        builder = ReceiptChainBuilder(
            task_sha256=derive_identity("test-task", "invalid"),
            case_id=derive_identity("test-case", "invalid"),
            case_index=0,
            horizon=1,
            condition_id=derive_identity("test-condition", "invalid"),
            display_label="invalid prediction",
            lineage_class="online-positive-surrogate",
            branch_token="genesis",
            surface=strict_online_surface(),
            initial_state=b"",
            initial_projection=b"",
            first_consumer_facts=consumer("invalid-0"),
        )
        builder.append_encounter(
            public_query=query(8, episode_start=True),
            episode_index=0,
            prediction=None,
            prediction_status="timeout",
            outcome=1,
            update_decision="update",
            authoritative_pre_state=b"",
            update_payload=b"timeout",
            post_state=b"after-timeout",
            next_projection=b"after-timeout",
            next_consumer_facts=consumer("invalid-1"),
        )
        result = validate_chain(builder.finish(), require_online_admissible=True)
        self.assertEqual(result.encounter_count, 1)
        self.assertEqual(result.errors, 1)

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
        chain = build_chain()
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
        ][0]["observed"] = True
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
        chain = build_chain()
        mutant = copy.deepcopy(chain)
        first = mutant["receipt_order"][5]["payload"]["facts"]
        second = mutant["receipt_order"][14]["payload"]["facts"]
        second["process_instance_id"] = first["process_instance_id"]
        with self.assertRaises(ReceiptError) as raised:
            validate_chain(mutant)
        self.assertEqual(raised.exception.code, "fresh-consumer")


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
        first = build_chain(label="collection-a", branch_token="a")
        second = build_chain(
            label="collection-b",
            branch_token="b",
            condition_id=derive_identity("test-condition", "collection-b"),
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
            condition_id=derive_identity("test-condition", "reused"),
        )
        self.assertNotEqual(first["trace_sha256"], reused["trace_sha256"])
        with self.assertRaises(ReceiptError) as raised:
            validate_chain_collection([first, reused])
        self.assertEqual(raised.exception.code, "fresh-consumer")


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
            outcomes=(0,),
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
            outcomes=(1,),
        )
        receipt = validate_branch_isolation(
            parent, rewind, alternate, checkpoint_index=0
        )
        self.assertTrue(receipt["sibling_projection_rejected"])
        self.assertNotEqual(
            validate_chain(rewind).branch_id, validate_chain(alternate).branch_id
        )
        gates = rollback_gates(
            parent,
            copy.deepcopy(parent),
            rewind,
            alternate,
            checkpoint_index=0,
        )
        self.assertEqual(len(gates), 5)
        self.assertTrue(all(gates.values()))


if __name__ == "__main__":
    unittest.main()
