from __future__ import annotations

import copy
import hashlib
import inspect
import unittest

from open_trajectory_harness.ot0002 import canonical_json
from open_trajectory_harness import ot0077_shadow_scoring
from open_trajectory_harness.ot0077_scoring import (
    ADAPTIVE_COMPARATORS,
    AUTHORITY_DEFECTS,
    CAUSAL_PATH_GATES,
    CONDITION_INVENTORY,
    EXECUTION_GATES,
    HARD_SEVERINGS,
    IDENTITY_PLACEBO,
    MATCHED_FROZEN_BY_REFERENCE,
    POSITIVE_REFERENCES,
    RECURRENCE_INTERVENTION,
    ROLLBACK_REPLAY_GATES,
    STALE_INTERVENTION,
    WRONG_LINEAGE_INTERVENTION,
    ScoringError,
    metamorphic_variants,
    score_bundle,
)
from open_trajectory_harness.ot0077_shadow_scoring import (
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
    return [outcome ^ int(index in errors) for index, outcome in enumerate(outcomes)]


def _projection_evidence(
    label: str,
    *,
    initial: str | None = None,
    active_changed: bool = False,
    accepted_updates: int = 0,
    candidate_changed: bool = False,
) -> dict[str, object]:
    first = initial or _sha(f"projection:{label}:initial")
    consumed = [first]
    consumed.extend(
        _sha(f"projection:{label}:{index}") if active_changed else first
        for index in range(1, HORIZON)
    )
    return {
        "consumed_projection_sha256s": consumed,
        "terminal_projection_sha256": (
            _sha(f"projection:{label}:terminal") if active_changed else first
        ),
        "accepted_updates": accepted_updates,
        "candidate_state_changed": candidate_changed,
        "active_projection_changed": active_changed,
    }


def _reference_errors(reference: str) -> set[int]:
    if reference == POSITIVE_REFERENCES[0]:
        return _episode_prefix_errors((6, 7, 1, 8, 1, 1))
    return _episode_prefix_errors((7, 8, 0, 7, 1, 1))


def _descriptor_errors(
    descriptor: tuple[str, str, str | None, str | None],
) -> set[int]:
    role, mechanism, reference, intervention = descriptor
    if role == "positive-reference":
        return _reference_errors(mechanism)
    if role == "required-control":
        return set(
            range(
                {
                    "no-persistence": 121,
                    "immutable-seed": 120,
                    "encounter-index-clock": 130,
                    "offline-best-fixed-rule": 80,
                }[mechanism]
            )
        )
    if role == "matched-frozen-control":
        return set(range(120))
    if role == "adaptive-comparator":
        stride = 5 if mechanism == ADAPTIVE_COMPARATORS[0] else 6
        return set(range(0, HORIZON, stride))
    if role == "causal-intervention":
        if intervention == STALE_INTERVENTION:
            return set(range(100))
        if intervention == WRONG_LINEAGE_INTERVENTION:
            return set(range(HORIZON))
        return set(range(120))
    if role == "recurrence-intervention":
        result = set(_reference_errors(str(reference)))
        cursor = 0
        for episode_index, dwell in enumerate(DWELLS):
            if episode_index in {2, 4, 5}:
                result.update(range(cursor, cursor + 4))
            cursor += dwell
        return result
    if role == "identity-placebo":
        return set(range(120))
    raise AssertionError(descriptor)


def _causal_evidence(
    descriptor: tuple[str, str, str | None, str | None],
    case_index: int,
) -> dict[str, object]:
    role, mechanism, reference, intervention = descriptor
    reference_initials = {
        name: _sha(f"case:{case_index}:reference:{name}:initial")
        for name in POSITIVE_REFERENCES
    }
    if role == "positive-reference":
        return _projection_evidence(
            f"case:{case_index}:live:{mechanism}",
            initial=reference_initials[mechanism],
            active_changed=True,
            accepted_updates=HORIZON,
            candidate_changed=True,
        )
    if role == "matched-frozen-control":
        return _projection_evidence(
            f"case:{case_index}:matched:{mechanism}",
            initial=reference_initials[str(reference)],
        )
    if role == "causal-intervention" and intervention in HARD_SEVERINGS:
        evidence = _projection_evidence(
            f"case:{case_index}:hard:{reference}",
            initial=reference_initials[str(reference)],
        )
        if intervention == "update-without-projection":
            evidence["accepted_updates"] = HORIZON
            evidence["candidate_state_changed"] = True
        return evidence
    if role == "causal-intervention" and intervention == STALE_INTERVENTION:
        return _projection_evidence(
            f"case:{case_index}:stale:{reference}",
            initial=reference_initials[str(reference)],
            active_changed=True,
            accepted_updates=30,
            candidate_changed=True,
        )
    if role == "causal-intervention" and intervention == WRONG_LINEAGE_INTERVENTION:
        return _projection_evidence(
            f"case:{case_index}:wrong:{reference}",
            initial=reference_initials[str(reference)],
        )
    if role == "recurrence-intervention":
        return _projection_evidence(
            f"case:{case_index}:reset:{reference}",
            initial=reference_initials[str(reference)],
            active_changed=True,
            accepted_updates=HORIZON,
            candidate_changed=True,
        )
    if role in {"required-control", "identity-placebo"} and (
        mechanism == "immutable-seed" or role == "identity-placebo"
    ):
        return _projection_evidence(f"case:{case_index}:immutable")
    if role == "adaptive-comparator":
        return _projection_evidence(
            f"case:{case_index}:comparator:{mechanism}",
            active_changed=True,
            accepted_updates=HORIZON,
            candidate_changed=True,
        )
    return _projection_evidence(f"case:{case_index}:{role}:{mechanism}")


def _case(case_index: int) -> dict[str, object]:
    query_ids = [_sha(f"query:{case_index}:{index}") for index in range(HORIZON)]
    outcomes = [(case_index + index + index // 7) & 1 for index in range(HORIZON)]
    conditions = {}
    for descriptor_index, descriptor in enumerate(CONDITION_INVENTORY):
        role, mechanism, reference, intervention = descriptor
        errors = _descriptor_errors(descriptor)
        if intervention == WRONG_LINEAGE_INTERVENTION:
            predictions: list[int | None] = [None] * HORIZON
            statuses = ["invalid"] * HORIZON
        else:
            predictions = _predictions(outcomes, errors)
            statuses = ["valid"] * HORIZON
        conditions[_sha(f"condition:{case_index}:{descriptor_index}")] = {
            "role": role,
            "mechanism_id": mechanism,
            "reference_id": reference,
            "intervention_id": intervention,
            "query_ids": list(query_ids),
            "outcomes": list(outcomes),
            "predictions": predictions,
            "prediction_statuses": statuses,
            "causal_evidence": _causal_evidence(descriptor, case_index),
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
        "experiment_id": "OT-0077",
        "purpose": purpose,
        "case_count": case_count,
        "cases": [_case(index) for index in range(case_count)],
        "authority_defect_rejections": {name: True for name in AUTHORITY_DEFECTS},
        "causal_path_gates": {name: True for name in CAUSAL_PATH_GATES},
        "rollback_replay_gates": {name: True for name in ROLLBACK_REPLAY_GATES},
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


def _reference_gate(
    summary: dict[str, object], reference: str, *, case_index: int = 0
) -> dict[str, object]:
    for gate in summary["cases"][case_index]["reference_gates"]:
        if gate["reference_id"] == reference:
            return gate
    raise AssertionError(reference)


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


def _set_error_count(trace: dict[str, object], count: int) -> None:
    trace["predictions"] = _predictions(trace["outcomes"], set(range(count)))
    trace["prediction_statuses"] = ["valid"] * HORIZON


def _matched_causal_slice(gate: dict[str, object]) -> dict[str, object]:
    return {
        name: copy.deepcopy(gate[name])
        for name in (
            "matched_frozen_control_id",
            "matched_frozen_errors",
            "live_errors",
            "matched_live_lift",
            "matched_margin_pass",
            "matched_control_gate",
            "hard_severings",
            "stale_binding",
            "wrong_lineage_gate",
        )
    }


class OT0077ScoringTests(unittest.TestCase):
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
        self.assertEqual(len(CONDITION_INVENTORY), 23)
        self.assertEqual(len(self.primary["aggregate"]["paired_families"]), 10)
        self.assertEqual(self.primary["aggregate"]["familywise_sign_numerator"], 10)
        self.assertEqual(self.primary["aggregate"]["familywise_sign_denominator"], 256)

    def test_shadow_has_no_primary_or_protocol_dependency(self) -> None:
        source = inspect.getsource(ot0077_shadow_scoring)
        self.assertNotIn("from .ot0077_scoring", source)
        self.assertNotIn("from .ot0077_protocol", source)
        self.assertNotIn("import ot0077_scoring", source)
        self.assertNotIn("import ot0077_protocol", source)

    def test_matched_live_lift_and_frozen_initial_control_are_exact(self) -> None:
        for reference in POSITIVE_REFERENCES:
            with self.subTest(reference=reference):
                gate = _reference_gate(self.primary, reference)
                self.assertEqual(gate["matched_frozen_errors"], 120)
                self.assertEqual(gate["live_errors"], 24)
                self.assertEqual(gate["matched_live_lift"], 96)
                self.assertTrue(gate["matched_margin_pass"])
                self.assertTrue(gate["matched_control_gate"]["pass"])
                self.assertTrue(gate["gates"]["matched_live_lift"])
        self.assertTrue(
            all(
                family["all_streams_win"]
                for family in self.primary["aggregate"]["paired_families"]
            )
        )

    def test_hard_severings_require_zero_lift_exact_traces_and_operation_evidence(self) -> None:
        reference = POSITIVE_REFERENCES[0]
        for intervention in HARD_SEVERINGS:
            with self.subTest(intervention=intervention):
                gate = next(
                    row
                    for row in _reference_gate(self.primary, reference)["hard_severings"]
                    if row["intervention_id"] == intervention
                )
                self.assertEqual(gate["surviving_lift"], 0)
                self.assertTrue(gate["pass"])

                projection_failure = copy.deepcopy(self.bundle)
                trace = _condition(
                    projection_failure,
                    ("causal-intervention", intervention, reference, intervention),
                )
                trace["causal_evidence"]["consumed_projection_sha256s"][1] = _sha(
                    f"mismatch:{intervention}"
                )
                self.assertFalse(score_bundle(projection_failure)["anchor_promotion_pass"])
                self.assertFalse(
                    score_bundle_shadow(projection_failure)["anchor_promotion_pass"]
                )

                operation_failure = copy.deepcopy(self.bundle)
                evidence = _condition(
                    operation_failure,
                    ("causal-intervention", intervention, reference, intervention),
                )["causal_evidence"]
                if intervention == "update-without-projection":
                    evidence["candidate_state_changed"] = False
                else:
                    evidence["accepted_updates"] = 1
                self.assertFalse(score_bundle(operation_failure)["anchor_promotion_pass"])

    def test_stale_binding_requires_both_loss_rules_and_active_evidence(self) -> None:
        reference = POSITIVE_REFERENCES[0]
        gate = _reference_gate(self.primary, reference)["stale_binding"]
        self.assertEqual(gate["residual_lift"], 20)
        self.assertTrue(gate["gates"]["two_thirds_lift_lost"])
        self.assertTrue(gate["gates"]["worse_than_live_by_practical_margin"])
        self.assertTrue(gate["gates"]["accepted_update"])
        self.assertTrue(gate["gates"]["active_projection_changed"])

        excessive_residual = copy.deepcopy(self.bundle)
        stale = _condition(
            excessive_residual,
            ("causal-intervention", STALE_INTERVENTION, reference, STALE_INTERVENTION),
        )
        _set_error_count(stale, 50)
        result = score_bundle(excessive_residual)
        self.assertFalse(
            _reference_gate(result, reference)["stale_binding"]["gates"][
                "two_thirds_lift_lost"
            ]
        )

        practical_margin = copy.deepcopy(self.bundle)
        matched = _condition(
            practical_margin,
            (
                "matched-frozen-control",
                MATCHED_FROZEN_BY_REFERENCE[reference],
                reference,
                None,
            ),
        )
        _set_error_count(matched, 37)
        for intervention in HARD_SEVERINGS:
            _set_error_count(
                _condition(
                    practical_margin,
                    ("causal-intervention", intervention, reference, intervention),
                ),
                37,
            )
        stale = _condition(
            practical_margin,
            ("causal-intervention", STALE_INTERVENTION, reference, STALE_INTERVENTION),
        )
        _set_error_count(stale, 33)
        stale_gate = _reference_gate(score_bundle(practical_margin), reference)[
            "stale_binding"
        ]
        self.assertTrue(stale_gate["gates"]["two_thirds_lift_lost"])
        self.assertFalse(stale_gate["gates"]["worse_than_live_by_practical_margin"])

        inactive = copy.deepcopy(self.bundle)
        evidence = _condition(
            inactive,
            ("causal-intervention", STALE_INTERVENTION, reference, STALE_INTERVENTION),
        )["causal_evidence"]
        evidence["accepted_updates"] = 0
        evidence["active_projection_changed"] = False
        self.assertFalse(score_bundle(inactive)["anchor_promotion_pass"])

    def test_unrelated_immutable_mutation_cannot_change_matched_causal_disposition(self) -> None:
        changed = copy.deepcopy(self.bundle)
        for case_index in range(8):
            for descriptor in (
                ("required-control", "immutable-seed", None, None),
                ("identity-placebo", IDENTITY_PLACEBO, None, None),
            ):
                trace = _condition(changed, descriptor, case_index=case_index)
                _set_error_count(trace, 150)
                evidence = _projection_evidence(f"changed-immutable:{case_index}")
                trace["causal_evidence"] = evidence
        changed["cases"][0]["placebo_projection_bytes_identical"] = True
        primary = score_bundle(changed)
        shadow = score_bundle_shadow(changed)
        self.assertEqual(canonical_json(primary), canonical_json(shadow))
        for reference in POSITIVE_REFERENCES:
            self.assertEqual(
                _matched_causal_slice(_reference_gate(self.primary, reference)),
                _matched_causal_slice(_reference_gate(primary, reference)),
            )

    def test_wrong_lineage_recurrence_and_placebo_are_decisive(self) -> None:
        reference = POSITIVE_REFERENCES[0]
        wrong = copy.deepcopy(self.bundle)
        trace = _condition(
            wrong,
            (
                "causal-intervention",
                WRONG_LINEAGE_INTERVENTION,
                reference,
                WRONG_LINEAGE_INTERVENTION,
            ),
        )
        trace["predictions"][0] = trace["outcomes"][0]
        trace["prediction_statuses"][0] = "valid"
        self.assertFalse(score_bundle(wrong)["anchor_promotion_pass"])

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
        live = _condition(
            reset_failure,
            ("positive-reference", reference, reference, None),
        )
        reset["predictions"] = list(live["predictions"])
        self.assertFalse(score_bundle(reset_failure)["anchor_promotion_pass"])

        placebo_failure = copy.deepcopy(self.bundle)
        placebo_failure["cases"][0]["placebo_projection_bytes_identical"] = False
        self.assertFalse(score_bundle(placebo_failure)["anchor_promotion_pass"])

    def test_failed_predictions_remain_errors_in_the_full_denominator(self) -> None:
        reference = POSITIVE_REFERENCES[0]
        descriptor = ("positive-reference", reference, reference, None)
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

    def test_exact_condition_and_causal_evidence_schemas_fail_closed(self) -> None:
        missing_condition = copy.deepcopy(self.bundle)
        missing_condition["cases"][0]["conditions"].pop(
            next(iter(missing_condition["cases"][0]["conditions"]))
        )
        with self.assertRaises(ScoringError):
            score_bundle(missing_condition)
        with self.assertRaises(ShadowScoringError):
            score_bundle_shadow(missing_condition)

        malformed_evidence = copy.deepcopy(self.bundle)
        reference = POSITIVE_REFERENCES[0]
        evidence = _condition(
            malformed_evidence,
            ("positive-reference", reference, reference, None),
        )["causal_evidence"]
        evidence.pop("terminal_projection_sha256")
        with self.assertRaises(ScoringError):
            score_bundle(malformed_evidence)
        with self.assertRaises(ShadowScoringError):
            score_bundle_shadow(malformed_evidence)

    def test_trace_metamorphisms_preserve_normalized_scores(self) -> None:
        expected = canonical_json(self.primary)
        for name, variant in metamorphic_variants(self.bundle).items():
            with self.subTest(name=name):
                primary = score_bundle(variant)
                shadow = score_bundle_shadow(variant)
                self.assertEqual(canonical_json(primary), expected)
                self.assertEqual(canonical_json(shadow), expected)

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

    def test_design_can_pass_trace_gate_but_never_authorizes(self) -> None:
        design = passing_bundle(purpose="design")
        primary = score_bundle(design)
        shadow = score_bundle_shadow(design)
        self.assertEqual(canonical_json(primary), canonical_json(shadow))
        self.assertTrue(primary["trace_gate_pass"])
        self.assertFalse(primary["anchor_promotion_pass"])
        self.assertEqual(primary["authorized_actor_candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
