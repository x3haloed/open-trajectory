from __future__ import annotations

import ast
import base64
import copy
import inspect
import unittest

import open_trajectory_harness.ot0075_learning as learning
from open_trajectory_harness.ot0002 import canonical_json
from open_trajectory_harness.ot0075_learning import (
    CLOCK_CONTROL,
    COMPACT_REFERENCE,
    IMMUTABLE_SEED_CONTROL,
    IMMUTABLE_SEED_MASK,
    LOG_REFERENCE,
    NEAREST_COMPARATOR,
    NO_PERSISTENCE_CONTROL,
    ONLINE_MECHANISMS,
    PREDICTION_OPERATION_LIMIT,
    RECENT_COMPARATOR,
    STATE_BYTE_LIMIT,
    UPDATE_OPERATION_LIMIT,
    EpistemicEvent,
    LearningError,
    clock_initial_state,
    clock_predict,
    clock_update,
    compact_initial_state,
    compact_predict,
    compact_update,
    decode_state,
    encode_state,
    immutable_seed_initial_state,
    immutable_seed_predict,
    initial_state,
    log_initial_state,
    log_predict,
    log_update,
    nearest_predict,
    offline_best_fixed_rule,
    pack_epistemic_events,
    predict,
    recent_initial_state,
    recent_update,
    unpack_epistemic_events,
    update,
)
from open_trajectory_harness.ot0075_protocol import (
    DIMENSION,
    HORIZON,
    build_design_task,
    parity,
    parse_bits,
)


def _case_events(case: dict[str, object]) -> list[dict[str, object]]:
    return [
        event
        for episode in case["episodes"]
        for event in episode["events"]
    ]


def _public_events(case: dict[str, object]) -> list[dict[str, object]]:
    return [
        {"outcome": event["outcome"], "public_query": event["public_query"]}
        for event in _case_events(case)
    ]


def _recovery(errors: list[int]) -> int:
    dwell = len(errors)
    for offset in range(dwell - 7):
        if not any(errors[offset:]):
            return offset
    return dwell


class OT0075LearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.design_tasks = [build_design_task(index) for index in range(4)]

    def test_learning_call_graph_imports_no_authority_bearing_module(self) -> None:
        tree = ast.parse(inspect.getsource(learning))
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertEqual(
            imported_roots,
            {
                "__future__",
                "base64",
                "binascii",
                "dataclasses",
                "json",
                "re",
                "typing",
            },
        )
        self.assertNotIn("derive_task", vars(learning))
        self.assertNotIn("build_design_task", vars(learning))

    def test_epistemic_codec_is_exact_canonical_and_padding_checked(self) -> None:
        rows = (
            EpistemicEvent(True, 1, 1),
            EpistemicEvent(False, 0b101010101010, 0),
            EpistemicEvent(False, 0b111100001111, 1),
        )
        self.assertEqual(pack_epistemic_events(rows[:1]), "gAw=")
        payload = pack_epistemic_events(rows)
        self.assertEqual(unpack_epistemic_events(3, payload), rows)
        self.assertEqual(pack_epistemic_events(()), "")
        self.assertEqual(unpack_epistemic_events(0, ""), ())

        raw = bytearray(base64.b64decode(pack_epistemic_events(rows[:1])))
        raw[-1] |= 1
        with self.assertRaisesRegex(LearningError, "nonzero padding"):
            unpack_epistemic_events(1, base64.b64encode(raw).decode("ascii"))
        with self.assertRaisesRegex(LearningError, "invalid base64"):
            unpack_epistemic_events(1, "not+base64===")
        with self.assertRaisesRegex(LearningError, "length differs"):
            unpack_epistemic_events(2, pack_epistemic_events(rows[:1]))

    def test_compact_reference_learns_and_canonically_resets_only_on_update(
        self,
    ) -> None:
        case = self.design_tasks[0]["cases"][0]
        first_episode = case["episodes"][0]
        state = compact_initial_state()
        for event in first_episode["events"][:DIMENSION]:
            before = copy.deepcopy(state)
            result = compact_predict(state, event["public_query"])
            update_result = compact_update(
                state,
                event["public_query"],
                event["outcome"],
            )
            self.assertEqual(state, before)
            self.assertLessEqual(result.operations, PREDICTION_OPERATION_LIMIT)
            self.assertLessEqual(update_result.operations, UPDATE_OPERATION_LIMIT)
            state = update_result.state
        solved = parse_bits(case["hidden_masks"][0], "hidden mask")
        self.assertEqual(state["models"], [solved])
        self.assertEqual(len(state["basis"]), DIMENSION)

        boundary = case["episodes"][1]["events"][0]
        before = copy.deepcopy(state)
        compact_predict(state, boundary["public_query"])
        self.assertEqual(state, before)
        after = compact_update(state, boundary["public_query"], boundary["outcome"])
        self.assertEqual(len(after.state["basis"]), 1)
        self.assertEqual(after.state["models"], [solved])
        self.assertEqual(state, before)

    def test_compact_basis_and_evidence_fail_closed(self) -> None:
        query = self.design_tasks[0]["cases"][0]["episodes"][0]["events"][0][
            "public_query"
        ]
        malformed = compact_initial_state()
        malformed["basis"] = [[3, 0], [1, 1]]
        with self.assertRaisesRegex(LearningError, "not reduced"):
            compact_predict(malformed, query)

        state = compact_initial_state()
        updated = compact_update(state, query, 0).state
        repeated_query = dict(query)
        repeated_query["episode_start"] = False
        with self.assertRaisesRegex(LearningError, "inconsistent"):
            compact_update(updated, repeated_query, 1)

        duplicate = compact_initial_state()
        duplicate["models"] = [15, 15]
        with self.assertRaisesRegex(LearningError, "model bank"):
            compact_predict(duplicate, query)

    def test_log_reference_projection_contains_only_the_lossless_log(self) -> None:
        case = self.design_tasks[0]["cases"][0]
        state = log_initial_state()
        for event in _case_events(case):
            result = log_predict(state, event["public_query"])
            update_result = log_update(state, event["public_query"], event["outcome"])
            self.assertLessEqual(result.operations, PREDICTION_OPERATION_LIMIT)
            self.assertLessEqual(update_result.operations, UPDATE_OPERATION_LIMIT)
            state = update_result.state
        self.assertEqual(
            set(state),
            {"event_count", "payload_base64", "schema_version"},
        )
        self.assertEqual(state["event_count"], HORIZON)
        self.assertEqual(len(unpack_epistemic_events(HORIZON, state["payload_base64"])), HORIZON)
        self.assertLessEqual(len(canonical_json(state)), STATE_BYTE_LIMIT)

    def test_projection_codec_and_generic_dispatch_are_pure_and_fail_closed(
        self,
    ) -> None:
        query = self.design_tasks[0]["cases"][0]["episodes"][0]["events"][0][
            "public_query"
        ]
        outcome = self.design_tasks[0]["cases"][0]["episodes"][0]["events"][0][
            "outcome"
        ]
        for mechanism in ONLINE_MECHANISMS:
            state = initial_state(mechanism)
            before = copy.deepcopy(state)
            projection = encode_state(mechanism, state)
            self.assertEqual(projection, canonical_json(state))
            self.assertEqual(decode_state(mechanism, projection), state)
            from_state = predict(mechanism, state, query)
            from_bytes = predict(mechanism, projection, query)
            self.assertEqual(from_state, from_bytes)
            next_state = update(
                mechanism,
                projection,
                query,
                from_bytes.prediction,
                outcome,
            ).state
            self.assertEqual(state, before)
            self.assertLessEqual(len(encode_state(mechanism, next_state)), STATE_BYTE_LIMIT)
            with self.assertRaisesRegex(LearningError, "sealed prediction differs"):
                update(
                    mechanism,
                    projection,
                    query,
                    from_bytes.prediction ^ 1,
                    outcome,
                )

            noncanonical = projection[:-1] + b" \n"
            with self.assertRaisesRegex(LearningError, "not canonical"):
                decode_state(mechanism, noncanonical)
        with self.assertRaisesRegex(LearningError, "encoded projection differs"):
            decode_state(COMPACT_REFERENCE, b"x" * (STATE_BYTE_LIMIT + 1))

    def test_required_controls_have_exact_frozen_behavior(self) -> None:
        events = _case_events(self.design_tasks[0]["cases"][0])
        immutable = immutable_seed_initial_state()
        clock = clock_initial_state()
        for index, event in enumerate(events):
            query = event["public_query"]
            feature = parse_bits(query["feature_bits"], "feature")
            self.assertEqual(
                immutable_seed_predict(immutable, query).prediction,
                parity(IMMUTABLE_SEED_MASK, feature),
            )
            self.assertEqual(clock_predict(clock, query).prediction, index % 2)
            immutable_after = update(
                IMMUTABLE_SEED_CONTROL,
                immutable,
                query,
                immutable_seed_predict(immutable, query).prediction,
                event["outcome"],
            ).state
            self.assertEqual(immutable_after, immutable)
            clock = clock_update(clock, query, event["outcome"]).state
            self.assertEqual(
                predict(NO_PERSISTENCE_CONTROL, initial_state(NO_PERSISTENCE_CONTROL), query).prediction,
                0,
            )
        self.assertEqual(clock["encounter_count"], HORIZON)

    def test_recent_window_is_a_complete_canonical_suffix_under_budget(self) -> None:
        events = _case_events(self.design_tasks[0]["cases"][0])
        state = recent_initial_state()
        seen_ids = []
        for event in events:
            seen_ids.append(event["public_query"]["query_id"])
            state = recent_update(
                state,
                event["public_query"],
                event["outcome"],
            ).state
            self.assertLessEqual(len(canonical_json(state)), STATE_BYTE_LIMIT)
        retained_ids = [
            item["public_query"]["query_id"] for item in state["events"]
        ]
        self.assertEqual(retained_ids, seen_ids[-len(retained_ids) :])
        self.assertLess(len(retained_ids), len(seen_ids))

    def test_nearest_retrieval_prefers_most_recent_equal_distance(self) -> None:
        rows = (
            EpistemicEvent(False, 0b000000000001, 0),
            EpistemicEvent(False, 0b000000000100, 1),
        )
        state = {
            "event_count": len(rows),
            "payload_base64": pack_epistemic_events(rows),
            "schema_version": 1,
        }
        query = {
            "episode_start": False,
            "feature_bits": "000000000101",
            "query_id": "a" * 64,
            "schema_version": 1,
        }
        self.assertEqual(nearest_predict(state, query).prediction, 1)

    def test_offline_fixed_rule_uses_smallest_mask_on_equal_error(self) -> None:
        events = []
        for index in range(HORIZON):
            events.append(
                {
                    "encounter_index": index,
                    "outcome": 0,
                    "public_query": {
                        "episode_start": index == 0,
                        "feature_bits": "111111111111",
                        "query_id": format(index, "064x"),
                        "schema_version": 1,
                    },
                }
            )
        fixed = offline_best_fixed_rule(events)
        self.assertEqual(fixed.mask, 15)
        self.assertEqual(fixed.errors, 0)
        self.assertEqual(fixed.predictions, (0,) * HORIZON)

    def test_all_public_design_streams_pass_every_frozen_scoring_prediction(
        self,
    ) -> None:
        new_episode_indices = (0, 1, 3)
        recurring_episode_indices = (2, 4, 5)
        references = (COMPACT_REFERENCE, LOG_REFERENCE)
        online_controls = (
            NO_PERSISTENCE_CONTROL,
            IMMUTABLE_SEED_CONTROL,
            CLOCK_CONTROL,
        )
        stream_count = 0
        for task in self.design_tasks:
            for case in task["cases"]:
                stream_count += 1
                errors_by_mechanism: dict[str, int] = {}
                reference_episode_errors: dict[str, list[list[int]]] = {}
                for mechanism in (*references, *online_controls):
                    state = initial_state(mechanism)
                    all_errors = []
                    episode_errors = []
                    for episode in case["episodes"]:
                        current_errors = []
                        for event in episode["events"]:
                            prediction_result = predict(
                                mechanism,
                                encode_state(mechanism, state),
                                event["public_query"],
                            )
                            error = int(prediction_result.prediction != event["outcome"])
                            current_errors.append(error)
                            all_errors.append(error)
                            update_result = update(
                                mechanism,
                                state,
                                event["public_query"],
                                prediction_result.prediction,
                                event["outcome"],
                            )
                            self.assertLessEqual(
                                prediction_result.operations,
                                PREDICTION_OPERATION_LIMIT,
                            )
                            self.assertLessEqual(update_result.operations, UPDATE_OPERATION_LIMIT)
                            self.assertLessEqual(update_result.state_bytes, STATE_BYTE_LIMIT)
                            state = update_result.state
                        episode_errors.append(current_errors)
                    self.assertEqual(len(all_errors), HORIZON)
                    errors_by_mechanism[mechanism] = sum(all_errors)
                    if mechanism in references:
                        reference_episode_errors[mechanism] = episode_errors

                fixed = offline_best_fixed_rule(_case_events(case))
                errors_by_mechanism["offline-best-fixed-rule"] = fixed.errors

                for reference in references:
                    episode_errors = reference_episode_errors[reference]
                    flattened = [error for episode in episode_errors for error in episode]
                    reference_errors = errors_by_mechanism[reference]
                    self.assertLessEqual(reference_errors * 6, HORIZON)
                    self.assertLessEqual(
                        max(
                            sum(flattened[start : start + 16])
                            for start in range(HORIZON - 15)
                        ),
                        12,
                    )
                    recoveries = [_recovery(errors) for errors in episode_errors]
                    self.assertTrue(
                        all(recoveries[index] <= 12 for index in new_episode_indices)
                    )
                    self.assertTrue(
                        all(recoveries[index] <= 8 for index in recurring_episode_indices)
                    )
                    self.assertTrue(
                        all(sum(errors[-16:]) == 0 for errors in episode_errors)
                    )
                    self.assertGreaterEqual(
                        sum(recoveries[index] for index in new_episode_indices)
                        - sum(recoveries[index] for index in recurring_episode_indices),
                        12,
                    )
                    for control in (*online_controls, "offline-best-fixed-rule"):
                        self.assertGreater(
                            errors_by_mechanism[control],
                            reference_errors,
                        )
                        self.assertGreaterEqual(
                            20 * (errors_by_mechanism[control] - reference_errors),
                            HORIZON,
                        )
        self.assertEqual(stream_count, 4 * 16)


if __name__ == "__main__":
    unittest.main()
