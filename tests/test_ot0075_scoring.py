from __future__ import annotations

import copy
import hashlib
import inspect
import unittest

from open_trajectory_harness.ot0002 import canonical_json
from open_trajectory_harness import ot0075_shadow_scoring
from open_trajectory_harness.ot0075_scoring import (
    ADAPTIVE_COMPARATORS,
    AUTHORITY_DEFECTS,
    CAUSAL_INTERVENTIONS,
    CAUSAL_PATH_GATES,
    CONDITION_INVENTORY,
    EXECUTION_GATES,
    IDENTITY_PLACEBO,
    POSITIVE_REFERENCES,
    RECURRENCE_INTERVENTION,
    REQUIRED_CONTROLS,
    ROLLBACK_REPLAY_GATES,
    ScoringError,
    metamorphic_variants,
    score_bundle,
)
from open_trajectory_harness.ot0075_shadow_scoring import (
    ShadowScoringError,
    score_bundle_shadow,
)


DWELLS = (32, 35, 39, 43, 45, 48)
HORIZON = sum(DWELLS)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _episode_prefix_errors(recoveries: tuple[int, ...]) -> set[int]:
    result: set[int] = set()
    cursor = 0
    for dwell, recovery in zip(DWELLS, recoveries, strict=True):
        result.update(range(cursor, cursor + recovery))
        cursor += dwell
    return result


def _predictions(outcomes: list[int], errors: set[int]) -> list[int]:
    return [
        outcome ^ int(index in errors)
        for index, outcome in enumerate(outcomes)
    ]


def _errors_for_descriptor(
    descriptor: tuple[str, str, str | None, str | None],
) -> set[int]:
    role, mechanism, reference, _intervention = descriptor
    compact = _episode_prefix_errors((6, 7, 1, 8, 1, 1))
    lossless = _episode_prefix_errors((7, 8, 0, 7, 1, 1))
    references = {
        POSITIVE_REFERENCES[0]: compact,
        POSITIVE_REFERENCES[1]: lossless,
    }
    if role == "positive-reference":
        return references[mechanism]
    if role == "required-control":
        counts = {
            "no-persistence": 121,
            "immutable-seed": 120,
            "encounter-index-clock": 130,
            "offline-best-fixed-rule": 80,
        }
        return set(range(counts[mechanism]))
    if role == "adaptive-comparator":
        stride = 5 if mechanism == ADAPTIVE_COMPARATORS[0] else 6
        return set(range(0, HORIZON, stride))
    if role == "causal-intervention":
        return set(range(120))
    if role == "recurrence-intervention":
        result = set(references[str(reference)])
        cursor = 0
        for episode_index, dwell in enumerate(DWELLS):
            if episode_index in {2, 4, 5}:
                result.update(range(cursor, cursor + 4))
            cursor += dwell
        return result
    if role == "identity-placebo":
        return set(range(120))
    raise AssertionError(descriptor)


def _case(case_index: int) -> dict[str, object]:
    query_ids = [_sha(f"query:{case_index}:{index}") for index in range(HORIZON)]
    outcomes = [(case_index + index + index // 7) & 1 for index in range(HORIZON)]
    conditions = {}
    for descriptor_index, descriptor in enumerate(CONDITION_INVENTORY):
        role, mechanism, reference, intervention = descriptor
        errors = _errors_for_descriptor(descriptor)
        conditions[_sha(f"condition:{case_index}:{descriptor_index}")] = {
            "role": role,
            "mechanism_id": mechanism,
            "reference_id": reference,
            "intervention_id": intervention,
            "query_ids": list(query_ids),
            "outcomes": list(outcomes),
            "predictions": _predictions(outcomes, errors),
            "prediction_statuses": ["valid"] * HORIZON,
        }
    return {
        "case_id": _sha(f"case:{case_index}"),
        "case_index": case_index,
        "episodes": [
            {"episode_index": index, "dwell": dwell}
            for index, dwell in enumerate(DWELLS)
        ],
        "world_query_ids": query_ids,
        "world_outcomes": outcomes,
        "conditions": conditions,
        "placebo_projection_bytes_identical": True,
    }


def passing_bundle(*, purpose: str = "anchor") -> dict[str, object]:
    case_count = 8 if purpose == "anchor" else 16
    return {
        "schema_version": 1,
        "experiment_id": "OT-0075",
        "purpose": purpose,
        "case_count": case_count,
        "cases": [_case(index) for index in range(case_count)],
        "authority_defect_rejections": {
            name: True for name in AUTHORITY_DEFECTS
        },
        "causal_path_gates": {name: True for name in CAUSAL_PATH_GATES},
        "rollback_replay_gates": {
            name: True for name in ROLLBACK_REPLAY_GATES
        },
        "execution_gates": {name: True for name in EXECUTION_GATES},
    }


def _condition(
    bundle: dict[str, object],
    descriptor: tuple[str, str, str | None, str | None],
    *,
    case_index: int = 0,
) -> dict[str, object]:
    case = bundle["cases"][case_index]
    for trace in case["conditions"].values():
        observed = (
            trace["role"],
            trace["mechanism_id"],
            trace["reference_id"],
            trace["intervention_id"],
        )
        if observed == descriptor:
            return trace
    raise AssertionError(descriptor)


def _lineage_summary(
    summary: dict[str, object],
    descriptor: tuple[str, str, str | None, str | None],
    *,
    case_index: int = 0,
) -> dict[str, object]:
    for item in summary["cases"][case_index]["lineage_metrics"]:
        observed = (
            item["role"],
            item["mechanism_id"],
            item["reference_id"],
            item["intervention_id"],
        )
        if observed == descriptor:
            return item["metrics"]
    raise AssertionError(descriptor)


class OT0075ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = passing_bundle()
        cls.primary = score_bundle(cls.bundle)
        cls.shadow = score_bundle_shadow(cls.bundle)

    def test_primary_and_independent_shadow_agree_on_complete_pass(self) -> None:
        self.assertEqual(canonical_json(self.primary), canonical_json(self.shadow))
        self.assertTrue(self.primary["trace_gate_pass"])
        self.assertTrue(self.primary["anchor_promotion_pass"])
        self.assertEqual(self.primary["authorized_actor_candidate_count"], 1)
        self.assertEqual(
            self.primary["aggregate"]["familywise_sign_numerator"],
            8,
        )
        self.assertEqual(
            self.primary["aggregate"]["familywise_sign_denominator"],
            256,
        )

    def test_shadow_has_no_primary_or_protocol_dependency(self) -> None:
        source = inspect.getsource(ot0075_shadow_scoring)
        self.assertNotIn("from .ot0075_scoring", source)
        self.assertNotIn("from .ot0075_protocol", source)
        self.assertNotIn("import ot0075_scoring", source)
        self.assertNotIn("import ot0075_protocol", source)

    def test_exact_reference_metrics_and_integer_gates_are_frozen(self) -> None:
        compact = self.primary["cases"][0]["reference_gates"][0]
        lossless = self.primary["cases"][0]["reference_gates"][1]
        compact_metrics = _lineage_summary(
            self.primary,
            (
                "positive-reference",
                POSITIVE_REFERENCES[0],
                POSITIVE_REFERENCES[0],
                None,
            ),
        )
        self.assertEqual(compact["new_recovery_sum"], 21)
        self.assertEqual(compact["recurring_recovery_sum"], 3)
        self.assertEqual(compact["relearning_savings"], 18)
        self.assertEqual(lossless["new_recovery_sum"], 22)
        self.assertEqual(lossless["recurring_recovery_sum"], 2)
        self.assertEqual(lossless["relearning_savings"], 20)
        self.assertTrue(compact["gates"]["cumulative_error"])
        self.assertTrue(compact["gates"]["rolling_error"])
        self.assertTrue(compact["gates"]["late_episode"])
        self.assertTrue(compact["gates"]["control_margins"])
        self.assertEqual(len(compact_metrics["cumulative_errors"]), HORIZON)
        self.assertEqual(len(compact_metrics["rolling_errors"]), HORIZON - 15)
        self.assertIsNone(
            compact_metrics["episode_metrics"][0][
                "post_change_excess_errors"
            ]
        )
        self.assertEqual(
            compact_metrics["episode_metrics"][1][
                "post_change_excess_errors"
            ],
            7,
        )

    def test_invalid_timeout_and_missing_predictions_remain_errors(self) -> None:
        descriptor = (
            "positive-reference",
            POSITIVE_REFERENCES[0],
            POSITIVE_REFERENCES[0],
            None,
        )
        original = _lineage_summary(self.primary, descriptor)
        for status, count_key in (
            ("invalid", "invalid_predictions"),
            ("timeout", "timeout_predictions"),
            ("missing", "missing_predictions"),
        ):
            with self.subTest(status=status):
                bundle = copy.deepcopy(self.bundle)
                trace = _condition(bundle, descriptor)
                trace["predictions"][20] = None
                trace["prediction_statuses"][20] = status
                primary = score_bundle(bundle)
                shadow = score_bundle_shadow(bundle)
                self.assertEqual(canonical_json(primary), canonical_json(shadow))
                metrics = _lineage_summary(primary, descriptor)
                self.assertEqual(metrics["denominator"], HORIZON)
                self.assertEqual(metrics["errors"], original["errors"] + 1)
                self.assertEqual(metrics[count_key], 1)
                self.assertEqual(len(metrics["cumulative_errors"]), HORIZON)

    def test_dropping_a_prediction_cannot_change_the_denominator(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        descriptor = (
            "positive-reference",
            POSITIVE_REFERENCES[0],
            POSITIVE_REFERENCES[0],
            None,
        )
        _condition(bundle, descriptor)["predictions"].pop()
        with self.assertRaises(ScoringError):
            score_bundle(bundle)
        with self.assertRaises(ShadowScoringError):
            score_bundle_shadow(bundle)

    def test_outcome_and_query_bindings_fail_closed(self) -> None:
        descriptor = (
            "positive-reference",
            POSITIVE_REFERENCES[0],
            POSITIVE_REFERENCES[0],
            None,
        )
        for field, replacement in (
            ("outcomes", 1 - self.bundle["cases"][0]["world_outcomes"][0]),
            ("query_ids", _sha("wrong-query")),
        ):
            with self.subTest(field=field):
                bundle = copy.deepcopy(self.bundle)
                _condition(bundle, descriptor)[field][0] = replacement
                with self.assertRaises(ScoringError):
                    score_bundle(bundle)
                with self.assertRaises(ShadowScoringError):
                    score_bundle_shadow(bundle)

        cross_case = copy.deepcopy(self.bundle)
        cross_case["cases"][1]["world_query_ids"][0] = cross_case["cases"][0][
            "world_query_ids"
        ][0]
        for trace in cross_case["cases"][1]["conditions"].values():
            trace["query_ids"][0] = cross_case["cases"][1]["world_query_ids"][0]
        with self.assertRaises(ScoringError):
            score_bundle(cross_case)
        with self.assertRaises(ShadowScoringError):
            score_bundle_shadow(cross_case)

    def test_exact_condition_inventory_and_schema_fail_closed(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        bundle["cases"][0]["conditions"].pop(
            next(iter(bundle["cases"][0]["conditions"]))
        )
        with self.assertRaises(ScoringError):
            score_bundle(bundle)
        with self.assertRaises(ShadowScoringError):
            score_bundle_shadow(bundle)

        extra = copy.deepcopy(self.bundle)
        extra["unexpected"] = True
        with self.assertRaises(ScoringError):
            score_bundle(extra)
        with self.assertRaises(ShadowScoringError):
            score_bundle_shadow(extra)

    def test_all_trace_metamorphisms_preserve_normalized_scores(self) -> None:
        expected = canonical_json(self.primary)
        for name, variant in metamorphic_variants(self.bundle).items():
            with self.subTest(name=name):
                primary = score_bundle(variant)
                shadow = score_bundle_shadow(variant)
                self.assertEqual(canonical_json(primary), expected)
                self.assertEqual(canonical_json(shadow), expected)

    def test_adaptive_comparator_performance_is_reported_not_promotional(self) -> None:
        for perfect in (True, False):
            with self.subTest(perfect=perfect):
                bundle = copy.deepcopy(self.bundle)
                for case_index in range(8):
                    for comparator in ADAPTIVE_COMPARATORS:
                        trace = _condition(
                            bundle,
                            ("adaptive-comparator", comparator, None, None),
                            case_index=case_index,
                        )
                        trace["predictions"] = [
                            outcome if perfect else 1 - outcome
                            for outcome in trace["outcomes"]
                        ]
                primary = score_bundle(bundle)
                shadow = score_bundle_shadow(bundle)
                self.assertEqual(canonical_json(primary), canonical_json(shadow))
                self.assertTrue(primary["anchor_promotion_pass"])

    def test_recovery_control_intervention_reset_and_placebo_each_decide(self) -> None:
        reference = POSITIVE_REFERENCES[0]
        descriptor = ("positive-reference", reference, reference, None)

        late_failure = copy.deepcopy(self.bundle)
        trace = _condition(late_failure, descriptor)
        trace["predictions"][-1] ^= 1
        self.assertFalse(score_bundle(late_failure)["anchor_promotion_pass"])
        self.assertFalse(score_bundle_shadow(late_failure)["anchor_promotion_pass"])

        control_failure = copy.deepcopy(self.bundle)
        control = _condition(
            control_failure,
            ("required-control", "offline-best-fixed-rule", None, None),
        )
        control["predictions"] = _predictions(control["outcomes"], set(range(36)))
        self.assertFalse(score_bundle(control_failure)["anchor_promotion_pass"])

        intervention_failure = copy.deepcopy(self.bundle)
        intervention = _condition(
            intervention_failure,
            (
                "causal-intervention",
                CAUSAL_INTERVENTIONS[0],
                reference,
                CAUSAL_INTERVENTIONS[0],
            ),
        )
        intervention["predictions"] = list(intervention["outcomes"])
        self.assertFalse(score_bundle(intervention_failure)["anchor_promotion_pass"])

        reset_failure = copy.deepcopy(self.bundle)
        reset = _condition(
            reset_failure,
            (
                "recurrence-intervention",
                RECURRENCE_INTERVENTION,
                reference,
                RECURRENCE_INTERVENTION,
            ),
        )
        live = _condition(reset_failure, descriptor)
        reset["predictions"] = list(live["predictions"])
        self.assertFalse(score_bundle(reset_failure)["anchor_promotion_pass"])

        placebo_failure = copy.deepcopy(self.bundle)
        placebo_failure["cases"][0]["placebo_projection_bytes_identical"] = False
        self.assertFalse(score_bundle(placebo_failure)["anchor_promotion_pass"])

    def test_nonmetric_failures_remove_all_authority(self) -> None:
        for map_name, gate_name in (
            ("authority_defect_rejections", AUTHORITY_DEFECTS[0]),
            ("causal_path_gates", CAUSAL_PATH_GATES[0]),
            ("rollback_replay_gates", ROLLBACK_REPLAY_GATES[0]),
            ("execution_gates", EXECUTION_GATES[0]),
        ):
            with self.subTest(gate=gate_name):
                bundle = copy.deepcopy(self.bundle)
                bundle[map_name][gate_name] = False
                primary = score_bundle(bundle)
                shadow = score_bundle_shadow(bundle)
                self.assertEqual(canonical_json(primary), canonical_json(shadow))
                self.assertFalse(primary["trace_gate_pass"])
                self.assertFalse(primary["anchor_promotion_pass"])
                self.assertEqual(primary["authorized_actor_candidate_count"], 0)

    def test_design_bundle_can_pass_trace_gate_but_never_authorizes(self) -> None:
        design = passing_bundle(purpose="design")
        primary = score_bundle(design)
        shadow = score_bundle_shadow(design)
        self.assertEqual(canonical_json(primary), canonical_json(shadow))
        self.assertTrue(primary["trace_gate_pass"])
        self.assertFalse(primary["anchor_promotion_pass"])
        self.assertEqual(primary["authorized_actor_candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
