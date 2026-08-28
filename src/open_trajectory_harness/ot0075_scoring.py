"""Primary trace scorer for the OT-0075 longitudinal evaluator.

The scorer consumes completed controller-owned traces.  It does not execute a
learner, infer hidden world state, or accept condition labels as authority.
Every prediction slot is retained in the frozen 242-encounter denominator.
"""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Final

from .ot0075_protocol import (
    ANCHOR_CASE_COUNT,
    DESIGN_CASE_COUNT,
    DWELL_LENGTHS,
    EPISODE_SCHEDULE,
    EXPERIMENT_ID,
    HORIZON,
    SCHEMA_VERSION,
)


ROLLING_WINDOW: Final = 16
ROLLING_MAX_ERRORS: Final = 12
SUSTAINED_RECOVERY_WINDOW: Final = 8
NEW_RECOVERY_MAX: Final = 12
RECURRING_RECOVERY_MAX: Final = 8
MIN_RELEARNING_SAVINGS: Final = 12
LATE_WINDOW: Final = 16

POSITIVE_REFERENCES: Final = (
    "compact-cached-affine-version-space",
    "lossless-epistemic-log-linear-bank",
)
REQUIRED_CONTROLS: Final = (
    "no-persistence",
    "immutable-seed",
    "encounter-index-clock",
    "offline-best-fixed-rule",
)
ADAPTIVE_COMPARATORS: Final = (
    "recent-verbatim-world-row-window",
    "lossless-log-naive-nearest-retrieval",
)
CAUSAL_INTERVENTIONS: Final = (
    "consequence-withholding",
    "one-step-stale-consequence",
    "update-without-projection",
    "projection-without-update",
    "wrong-lineage-projection",
)
RECURRENCE_INTERVENTION: Final = "cross-episode-state-reset"
IDENTITY_PLACEBO: Final = "identical-state-projection-placebo"

AUTHORITY_DEFECTS: Final = (
    "future-outcome-access",
    "hidden-schedule-access",
    "prediction-after-outcome",
    "reference-label-on-negative-lineage",
    "wrong-pre-state",
    "wrong-post-state",
    "wrong-update-parent",
    "cross-case-state",
    "cross-lineage-prediction",
    "cross-episode-outcome",
    "stale-projection",
    "skipped-encounter",
    "duplicate-encounter",
    "reordered-suffix",
    "sibling-branch-substitution",
    "missing-terminal-consumer",
    "favorable-summary-without-chain",
    "dropped-prediction-or-denominator-change",
    "over-budget-state-or-projection",
)
CAUSAL_PATH_GATES: Final = (
    "prediction_precedes_outcome",
    "outcome_descends_from_exact_prediction",
    "update_descends_from_outcome_and_pre_state",
    "next_projection_binds_exact_post_state",
    "next_fresh_process_consumes_exact_projection",
    "terminal_projection_has_audit_consumer",
    "fresh_process_workspace_receipts",
    "forbidden_continuity_channel_sentinels",
    "online_reference_reachable_surface_audit",
)
ROLLBACK_REPLAY_GATES: Final = (
    "rewind_to_checkpoint",
    "same_suffix_byte_exact_replay",
    "alternate_suffix_branch_isolated",
    "inactive_sibling_cannot_affect_active_projection",
    "cross_branch_substitution_rejected",
)
EXECUTION_GATES: Final = (
    "online_reference_authority",
    "control_authority",
    "adaptive_comparator_authority",
    "state_projection_budgets",
    "operation_budgets",
    "fresh_reset_receipts",
    "metamorphic_dispositions",
    "primary_shadow_agreement",
    "clean_private_reconstruction",
    "tests",
    "evidence_audit",
    "privacy_audit",
    "within_wall_budget",
    "candidate_free",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_STATUS_VALUES = {"valid", "invalid", "timeout", "missing"}
_NEW_EPISODES = (0, 1, 3)
_RECURRING_EPISODES = (2, 4, 5)


class ScoringError(ValueError):
    """Raised when a completed trace differs from the frozen input schema."""


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ScoringError(f"{label} keys differ from the frozen schema")
    return value


def _bool_gate_map(
    value: object,
    expected: tuple[str, ...],
    label: str,
) -> dict[str, bool]:
    result = _exact(value, set(expected), label)
    if any(type(result[name]) is not bool for name in expected):
        raise ScoringError(f"{label} values must be exact booleans")
    return result


def _descriptor_inventory() -> list[tuple[str, str, str | None, str | None]]:
    inventory: list[tuple[str, str, str | None, str | None]] = []
    inventory.extend(
        ("positive-reference", reference, reference, None)
        for reference in POSITIVE_REFERENCES
    )
    inventory.extend(
        ("required-control", control, None, None)
        for control in REQUIRED_CONTROLS
    )
    inventory.extend(
        ("adaptive-comparator", comparator, None, None)
        for comparator in ADAPTIVE_COMPARATORS
    )
    for reference in POSITIVE_REFERENCES:
        inventory.extend(
            ("causal-intervention", intervention, reference, intervention)
            for intervention in CAUSAL_INTERVENTIONS
        )
        inventory.append(
            (
                "recurrence-intervention",
                RECURRENCE_INTERVENTION,
                reference,
                RECURRENCE_INTERVENTION,
            )
        )
    inventory.append(("identity-placebo", IDENTITY_PLACEBO, None, None))
    return inventory


CONDITION_INVENTORY: Final = tuple(_descriptor_inventory())


def _validate_episodes(value: object) -> list[dict[str, int]]:
    if type(value) is not list or len(value) != len(EPISODE_SCHEDULE):
        raise ScoringError("case episodes differ from the frozen schedule")
    result: list[dict[str, int]] = []
    for expected, raw in enumerate(value):
        episode = _exact(raw, {"episode_index", "dwell"}, "episode")
        if (
            type(episode["episode_index"]) is not int
            or episode["episode_index"] != expected
            or type(episode["dwell"]) is not int
            or episode["dwell"] not in DWELL_LENGTHS
        ):
            raise ScoringError("episode identity differs")
        result.append(episode)
    if (
        sorted(episode["dwell"] for episode in result) != list(DWELL_LENGTHS)
        or sum(episode["dwell"] for episode in result) != HORIZON
    ):
        raise ScoringError("episode dwell schedule differs")
    return result


def _validate_world_arrays(
    query_ids: object,
    outcomes: object,
) -> tuple[list[str], list[int]]:
    if (
        type(query_ids) is not list
        or type(outcomes) is not list
        or len(query_ids) != HORIZON
        or len(outcomes) != HORIZON
    ):
        raise ScoringError("world arrays must retain the complete denominator")
    if any(
        type(query_id) is not str or _SHA256.fullmatch(query_id) is None
        for query_id in query_ids
    ) or len(set(query_ids)) != HORIZON:
        raise ScoringError("world query identities differ")
    if any(type(outcome) is not int or outcome not in {0, 1} for outcome in outcomes):
        raise ScoringError("world outcomes are not exact bits")
    return query_ids, outcomes


def _validate_condition(
    raw: object,
    world_query_ids: list[str],
    world_outcomes: list[int],
) -> tuple[
    tuple[str, str, str | None, str | None],
    dict[str, Any],
]:
    condition = _exact(
        raw,
        {
            "role",
            "mechanism_id",
            "reference_id",
            "intervention_id",
            "query_ids",
            "outcomes",
            "predictions",
            "prediction_statuses",
        },
        "condition",
    )
    for name in ("role", "mechanism_id"):
        if type(condition[name]) is not str:
            raise ScoringError(f"condition {name} is malformed")
    for name in ("reference_id", "intervention_id"):
        if condition[name] is not None and type(condition[name]) is not str:
            raise ScoringError(f"condition {name} is malformed")
    if condition["query_ids"] != world_query_ids:
        raise ScoringError("condition queries do not bind the controller world")
    if condition["outcomes"] != world_outcomes:
        raise ScoringError("condition outcomes do not bind independent reality")
    predictions = condition["predictions"]
    statuses = condition["prediction_statuses"]
    if (
        type(predictions) is not list
        or type(statuses) is not list
        or len(predictions) != HORIZON
        or len(statuses) != HORIZON
    ):
        raise ScoringError("prediction arrays must retain the complete denominator")
    for prediction, status in zip(predictions, statuses, strict=True):
        if type(status) is not str or status not in _STATUS_VALUES:
            raise ScoringError("prediction status is unavailable")
        if status == "valid":
            if type(prediction) is not int or prediction not in {0, 1}:
                raise ScoringError("valid prediction is not an exact bit")
        elif prediction is not None:
            raise ScoringError("invalid, timed-out, or missing prediction must be null")
    descriptor = (
        condition["role"],
        condition["mechanism_id"],
        condition["reference_id"],
        condition["intervention_id"],
    )
    return descriptor, condition


def _metric_summary(
    condition: dict[str, Any],
    episodes: list[dict[str, int]],
) -> dict[str, Any]:
    outcomes = condition["outcomes"]
    predictions = condition["predictions"]
    statuses = condition["prediction_statuses"]
    errors = [
        int(status != "valid" or prediction != outcome)
        for prediction, status, outcome in zip(
            predictions,
            statuses,
            outcomes,
            strict=True,
        )
    ]
    cumulative: list[int] = []
    running = 0
    for error in errors:
        running += error
        cumulative.append(running)
    rolling = [
        sum(errors[start : start + ROLLING_WINDOW])
        for start in range(HORIZON - ROLLING_WINDOW + 1)
    ]
    episode_metrics = []
    cursor = 0
    for episode in episodes:
        dwell = episode["dwell"]
        segment = errors[cursor : cursor + dwell]
        last_error = max(
            (offset for offset, error in enumerate(segment) if error),
            default=-1,
        )
        candidate_recovery = last_error + 1
        recovery = (
            candidate_recovery
            if candidate_recovery <= dwell - SUSTAINED_RECOVERY_WINDOW
            else dwell
        )
        episode_index = episode["episode_index"]
        episode_metrics.append(
            {
                "episode_index": episode_index,
                "dwell": dwell,
                "episode_kind": (
                    "new" if episode_index in _NEW_EPISODES else "recurring"
                ),
                "errors": sum(segment),
                "recovery": recovery,
                "late_window_errors": sum(segment[-LATE_WINDOW:]),
                "post_change_excess_errors": (
                    None if episode_index == 0 else sum(segment)
                ),
            }
        )
        cursor += dwell
    counts = {
        status: sum(item == status for item in statuses)
        for status in ("valid", "invalid", "timeout", "missing")
    }
    return {
        "denominator": HORIZON,
        "errors": sum(errors),
        "valid_predictions": counts["valid"],
        "invalid_predictions": counts["invalid"],
        "timeout_predictions": counts["timeout"],
        "missing_predictions": counts["missing"],
        "cumulative_errors": cumulative,
        "rolling_errors": rolling,
        "episode_metrics": episode_metrics,
    }


def _reference_gate(
    reference: str,
    metrics: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
) -> dict[str, Any]:
    live = metrics[("positive-reference", reference, reference, None)]
    episodes = live["episode_metrics"]
    new_recovery = sum(episodes[index]["recovery"] for index in _NEW_EPISODES)
    recurring_recovery = sum(
        episodes[index]["recovery"] for index in _RECURRING_EPISODES
    )
    control_margins = []
    for control in REQUIRED_CONTROLS:
        control_errors = metrics[("required-control", control, None, None)][
            "errors"
        ]
        difference = control_errors - live["errors"]
        control_margins.append(
            {
                "control_id": control,
                "control_errors": control_errors,
                "reference_errors": live["errors"],
                "error_difference": difference,
                "margin_pass": 20 * difference >= HORIZON,
            }
        )
    immutable_errors = metrics[
        ("required-control", "immutable-seed", None, None)
    ]["errors"]
    live_advantage = immutable_errors - live["errors"]
    intervention_gates = []
    for intervention in CAUSAL_INTERVENTIONS:
        intervention_errors = metrics[
            ("causal-intervention", intervention, reference, intervention)
        ]["errors"]
        surviving_advantage = max(0, immutable_errors - intervention_errors)
        intervention_gates.append(
            {
                "intervention_id": intervention,
                "intervention_errors": intervention_errors,
                "surviving_advantage": surviving_advantage,
                "causal_loss_pass": (
                    live_advantage > 0
                    and 10 * surviving_advantage <= live_advantage
                ),
            }
        )
    reset = metrics[
        (
            "recurrence-intervention",
            RECURRENCE_INTERVENTION,
            reference,
            RECURRENCE_INTERVENTION,
        )
    ]
    live_recurring_errors = sum(
        episodes[index]["errors"] for index in _RECURRING_EPISODES
    )
    reset_recurring_errors = sum(
        reset["episode_metrics"][index]["errors"]
        for index in _RECURRING_EPISODES
    )
    gates = {
        "cumulative_error": live["errors"] * 6 <= HORIZON,
        "rolling_error": max(live["rolling_errors"], default=0)
        <= ROLLING_MAX_ERRORS,
        "new_recovery": all(
            episodes[index]["recovery"] <= NEW_RECOVERY_MAX
            for index in _NEW_EPISODES
        ),
        "recurring_recovery": all(
            episodes[index]["recovery"] <= RECURRING_RECOVERY_MAX
            for index in _RECURRING_EPISODES
        ),
        "late_episode": all(
            episode["late_window_errors"] == 0 for episode in episodes
        ),
        "relearning_savings": (
            new_recovery - recurring_recovery >= MIN_RELEARNING_SAVINGS
        ),
        "control_margins": all(item["margin_pass"] for item in control_margins),
        "live_advantage": live_advantage > 0,
        "causal_interventions": all(
            item["causal_loss_pass"] for item in intervention_gates
        ),
        "cross_episode_reset": (
            reset_recurring_errors - live_recurring_errors >= 8
        ),
    }
    return {
        "reference_id": reference,
        "new_recovery_sum": new_recovery,
        "recurring_recovery_sum": recurring_recovery,
        "relearning_savings": new_recovery - recurring_recovery,
        "live_advantage": live_advantage,
        "control_margins": control_margins,
        "causal_interventions": intervention_gates,
        "live_recurring_errors": live_recurring_errors,
        "reset_recurring_errors": reset_recurring_errors,
        "gates": gates,
        "pass": all(gates.values()),
    }


def _score_case(raw: object) -> dict[str, Any]:
    case = _exact(
        raw,
        {
            "case_id",
            "case_index",
            "episodes",
            "world_query_ids",
            "world_outcomes",
            "conditions",
            "placebo_projection_bytes_identical",
        },
        "case",
    )
    if type(case["case_id"]) is not str or _SHA256.fullmatch(case["case_id"]) is None:
        raise ScoringError("case identity is malformed")
    if type(case["case_index"]) is not int or case["case_index"] < 0:
        raise ScoringError("case index is malformed")
    if type(case["placebo_projection_bytes_identical"]) is not bool:
        raise ScoringError("placebo byte identity must be an exact boolean")
    episodes = _validate_episodes(case["episodes"])
    world_query_ids, world_outcomes = _validate_world_arrays(
        case["world_query_ids"],
        case["world_outcomes"],
    )
    raw_conditions = case["conditions"]
    if type(raw_conditions) is not dict or len(raw_conditions) != len(
        CONDITION_INVENTORY
    ):
        raise ScoringError("condition inventory cardinality differs")
    by_descriptor: dict[
        tuple[str, str, str | None, str | None], dict[str, Any]
    ] = {}
    for condition_id, raw_condition in raw_conditions.items():
        if type(condition_id) is not str or _SHA256.fullmatch(condition_id) is None:
            raise ScoringError("condition identity is not opaque SHA-256")
        descriptor, condition = _validate_condition(
            raw_condition,
            world_query_ids,
            world_outcomes,
        )
        if descriptor in by_descriptor:
            raise ScoringError("condition descriptor is duplicated")
        by_descriptor[descriptor] = condition
    if set(by_descriptor) != set(CONDITION_INVENTORY):
        raise ScoringError("condition descriptors differ from the frozen inventory")

    metrics = {
        descriptor: _metric_summary(by_descriptor[descriptor], episodes)
        for descriptor in CONDITION_INVENTORY
    }
    lineage_metrics = []
    for role, mechanism, reference, intervention in CONDITION_INVENTORY:
        lineage_metrics.append(
            {
                "role": role,
                "mechanism_id": mechanism,
                "reference_id": reference,
                "intervention_id": intervention,
                "metrics": metrics[(role, mechanism, reference, intervention)],
            }
        )
    reference_gates = [
        _reference_gate(reference, metrics) for reference in POSITIVE_REFERENCES
    ]
    immutable = by_descriptor[("required-control", "immutable-seed", None, None)]
    placebo = by_descriptor[("identity-placebo", IDENTITY_PLACEBO, None, None)]
    placebo_prediction_identity = (
        immutable["predictions"] == placebo["predictions"]
        and immutable["prediction_statuses"] == placebo["prediction_statuses"]
    )
    placebo_score_identity = (
        metrics[("required-control", "immutable-seed", None, None)]
        == metrics[("identity-placebo", IDENTITY_PLACEBO, None, None)]
    )
    placebo_gate = {
        "projection_bytes_identical": case[
            "placebo_projection_bytes_identical"
        ],
        "prediction_trace_identical": placebo_prediction_identity,
        "score_identical": placebo_score_identity,
    }
    return {
        "case_id": case["case_id"],
        "case_index": case["case_index"],
        "lineage_metrics": lineage_metrics,
        "reference_gates": reference_gates,
        "identity_placebo_gate": placebo_gate,
        "case_pass": (
            all(reference["pass"] for reference in reference_gates)
            and all(placebo_gate.values())
        ),
    }


def score_bundle(bundle: object) -> dict[str, Any]:
    """Validate and score one complete design or private-anchor trace bundle."""

    value = _exact(
        bundle,
        {
            "schema_version",
            "experiment_id",
            "purpose",
            "case_count",
            "cases",
            "authority_defect_rejections",
            "causal_path_gates",
            "rollback_replay_gates",
            "execution_gates",
        },
        "trace bundle",
    )
    purpose = value["purpose"]
    if purpose not in {"design", "anchor"}:
        raise ScoringError("trace bundle purpose is unavailable")
    expected_count = DESIGN_CASE_COUNT if purpose == "design" else ANCHOR_CASE_COUNT
    if (
        value["schema_version"] != SCHEMA_VERSION
        or value["experiment_id"] != EXPERIMENT_ID
        or type(value["case_count"]) is not int
        or value["case_count"] != expected_count
        or type(value["cases"]) is not list
        or len(value["cases"]) != expected_count
    ):
        raise ScoringError("trace bundle identity differs")
    authority = _bool_gate_map(
        value["authority_defect_rejections"],
        AUTHORITY_DEFECTS,
        "authority defect rejections",
    )
    causal = _bool_gate_map(
        value["causal_path_gates"],
        CAUSAL_PATH_GATES,
        "causal path gates",
    )
    rollback = _bool_gate_map(
        value["rollback_replay_gates"],
        ROLLBACK_REPLAY_GATES,
        "rollback replay gates",
    )
    execution = _bool_gate_map(
        value["execution_gates"],
        EXECUTION_GATES,
        "execution gates",
    )
    cases = [_score_case(raw_case) for raw_case in value["cases"]]
    all_world_query_ids = [
        query_id
        for raw_case in value["cases"]
        for query_id in raw_case["world_query_ids"]
    ]
    all_condition_ids = [
        condition_id
        for raw_case in value["cases"]
        for condition_id in raw_case["conditions"]
    ]
    if len(set(all_world_query_ids)) != expected_count * HORIZON:
        raise ScoringError("world query identities are not unique across cases")
    if len(set(all_condition_ids)) != expected_count * len(CONDITION_INVENTORY):
        raise ScoringError("condition identities are not unique across cases")
    case_indices = [case["case_index"] for case in cases]
    case_ids = [case["case_id"] for case in cases]
    if (
        set(case_indices) != set(range(expected_count))
        or len(set(case_ids)) != expected_count
    ):
        raise ScoringError("bundle case identities differ")
    cases.sort(key=lambda case: case["case_index"])

    paired_families = []
    for reference in POSITIVE_REFERENCES:
        for control in REQUIRED_CONTROLS:
            wins = 0
            for case in cases:
                metric_by_descriptor = {
                    (
                        item["role"],
                        item["mechanism_id"],
                        item["reference_id"],
                        item["intervention_id"],
                    ): item["metrics"]
                    for item in case["lineage_metrics"]
                }
                if (
                    metric_by_descriptor[
                        ("positive-reference", reference, reference, None)
                    ]["errors"]
                    < metric_by_descriptor[
                        ("required-control", control, None, None)
                    ]["errors"]
                ):
                    wins += 1
            paired_families.append(
                {
                    "reference_id": reference,
                    "control_id": control,
                    "wins": wins,
                    "streams": expected_count,
                    "all_streams_win": wins == expected_count,
                }
            )
    family_count = len(POSITIVE_REFERENCES) * len(REQUIRED_CONTROLS)
    sign_denominator = 1 << expected_count
    familywise_pass = family_count * 20 <= sign_denominator
    aggregate = {
        "stream_count": expected_count,
        "paired_families": paired_families,
        "paired_win_pass": all(
            family["all_streams_win"] for family in paired_families
        ),
        "familywise_sign_numerator": family_count,
        "familywise_sign_denominator": sign_denominator,
        "familywise_sign_bound_pass": familywise_pass,
        "every_stream_pass": all(case["case_pass"] for case in cases),
        "adaptive_comparators_reported": all(
            sum(
                item["role"] == "adaptive-comparator"
                for item in case["lineage_metrics"]
            )
            == len(ADAPTIVE_COMPARATORS)
            for case in cases
        ),
    }
    promotion_gates = {
        "every_stream": aggregate["every_stream_pass"],
        "paired_control_wins": aggregate["paired_win_pass"],
        "familywise_sign_bound": aggregate["familywise_sign_bound_pass"],
        "adaptive_comparators_reported": aggregate[
            "adaptive_comparators_reported"
        ],
        "authority_defects_rejected": all(authority.values()),
        "causal_path": all(causal.values()),
        "rollback_replay": all(rollback.values()),
        "execution": all(execution.values()),
    }
    trace_gate_pass = all(promotion_gates.values())
    anchor_promotion_pass = purpose == "anchor" and trace_gate_pass
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "purpose": purpose,
        "case_count": expected_count,
        "cases": cases,
        "aggregate": aggregate,
        "authority_defect_rejections": {
            name: authority[name] for name in AUTHORITY_DEFECTS
        },
        "causal_path_gates": {name: causal[name] for name in CAUSAL_PATH_GATES},
        "rollback_replay_gates": {
            name: rollback[name] for name in ROLLBACK_REPLAY_GATES
        },
        "execution_gates": {name: execution[name] for name in EXECUTION_GATES},
        "promotion_gates": promotion_gates,
        "trace_gate_pass": trace_gate_pass,
        "anchor_promotion_pass": anchor_promotion_pass,
        "authorized_actor_candidate_count": 1 if anchor_promotion_pass else 0,
        "claim_limit": "candidate-free evaluator-visible surrogate calibration only",
    }


def query_id_alpha_renamed(bundle: object) -> dict[str, Any]:
    """Return a deterministic completed-trace query-ID alpha renaming."""

    result = copy.deepcopy(bundle)
    if type(result) is not dict or type(result.get("cases")) is not list:
        raise ScoringError("cannot alpha-rename a malformed trace bundle")
    mapping: dict[str, str] = {}
    ordinal = 0
    for case in result["cases"]:
        for query_id in case["world_query_ids"]:
            mapping[query_id] = hashlib.sha256(
                f"ot-0075-alpha:{ordinal}:{query_id}".encode("ascii")
            ).hexdigest()
            ordinal += 1
        case["world_query_ids"] = [
            mapping[query_id] for query_id in case["world_query_ids"]
        ]
        for condition in case["conditions"].values():
            condition["query_ids"] = [
                mapping[query_id] for query_id in condition["query_ids"]
            ]
    return result


def condition_ids_shuffled(bundle: object) -> dict[str, Any]:
    """Permute opaque condition labels without changing completed traces."""

    result = copy.deepcopy(bundle)
    if type(result) is not dict or type(result.get("cases")) is not list:
        raise ScoringError("cannot shuffle a malformed trace bundle")
    for case in result["cases"]:
        condition_ids = sorted(case["conditions"])
        rotated = condition_ids[1:] + condition_ids[:1]
        values = [case["conditions"][condition_id] for condition_id in condition_ids]
        case["conditions"] = {
            condition_id: condition
            for condition_id, condition in reversed(list(zip(rotated, values, strict=True)))
        }
    return result


def labels_complemented(bundle: object) -> dict[str, Any]:
    """Complement completed outcomes and valid predictions without rerunning."""

    result = copy.deepcopy(bundle)
    if type(result) is not dict or type(result.get("cases")) is not list:
        raise ScoringError("cannot complement a malformed trace bundle")
    for case in result["cases"]:
        case["world_outcomes"] = [1 - outcome for outcome in case["world_outcomes"]]
        for condition in case["conditions"].values():
            condition["outcomes"] = [1 - outcome for outcome in condition["outcomes"]]
            condition["predictions"] = [
                1 - prediction if status == "valid" else None
                for prediction, status in zip(
                    condition["predictions"],
                    condition["prediction_statuses"],
                    strict=True,
                )
            ]
    return result


def case_order_reversed(bundle: object) -> dict[str, Any]:
    """Reverse isolated case execution order while retaining case identities."""

    result = copy.deepcopy(bundle)
    if type(result) is not dict or type(result.get("cases")) is not list:
        raise ScoringError("cannot reverse a malformed trace bundle")
    result["cases"].reverse()
    return result


def metamorphic_variants(bundle: object) -> dict[str, dict[str, Any]]:
    """Build the four P-frozen completed-trace metamorphic anchors."""

    return {
        "query-id-alpha-renaming": query_id_alpha_renamed(bundle),
        "condition-id-shuffle": condition_ids_shuffled(bundle),
        "prediction-outcome-label-complement": labels_complemented(bundle),
        "case-order-reversal": case_order_reversed(bundle),
    }
