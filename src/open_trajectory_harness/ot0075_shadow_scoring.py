"""Independent shadow scorer for completed OT-0075 traces.

This implementation deliberately imports no OT-0075 protocol or primary
scoring code.  It repeats schema, metric, and promotion arithmetic so agreement
can detect a defect in either implementation rather than merely exercising a
shared helper twice.
"""

from __future__ import annotations

import re
from typing import Any


_EXPERIMENT = "OT-0075"
_SCHEMA = 1
_HORIZON = 242
_ANCHORS = 8
_DESIGN = 16
_DWELLS = (32, 35, 39, 43, 45, 48)
_EPISODES = 6
_NEW = (0, 1, 3)
_RETURNING = (2, 4, 5)

_REFERENCES = (
    "compact-cached-affine-version-space",
    "lossless-epistemic-log-linear-bank",
)
_CONTROLS = (
    "no-persistence",
    "immutable-seed",
    "encounter-index-clock",
    "offline-best-fixed-rule",
)
_COMPARATORS = (
    "recent-verbatim-world-row-window",
    "lossless-log-naive-nearest-retrieval",
)
_INTERVENTIONS = (
    "consequence-withholding",
    "one-step-stale-consequence",
    "update-without-projection",
    "projection-without-update",
    "wrong-lineage-projection",
)
_RESET = "cross-episode-state-reset"
_PLACEBO = "identical-state-projection-placebo"

_DEFECTS = (
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
_PATH_GATES = (
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
_REPLAY_GATES = (
    "rewind_to_checkpoint",
    "same_suffix_byte_exact_replay",
    "alternate_suffix_branch_isolated",
    "inactive_sibling_cannot_affect_active_projection",
    "cross_branch_substitution_rejected",
)
_RUN_GATES = (
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
_HEX = re.compile(r"[0-9a-f]{64}")


class ShadowScoringError(ValueError):
    """The shadow scorer received a trace outside its frozen contract."""


def _dictionary(raw: object, names: tuple[str, ...] | set[str], what: str) -> dict[str, Any]:
    expected = set(names)
    if type(raw) is not dict or set(raw.keys()) != expected:
        raise ShadowScoringError(f"{what} keys differ from the frozen schema")
    return raw


def _flags(raw: object, names: tuple[str, ...], what: str) -> dict[str, bool]:
    flags = _dictionary(raw, names, what)
    for name in names:
        if type(flags[name]) is not bool:
            raise ShadowScoringError(f"{what} values must be exact booleans")
    return flags


def _inventory() -> tuple[tuple[str, str, str | None, str | None], ...]:
    rows: list[tuple[str, str, str | None, str | None]] = []
    for name in _REFERENCES:
        rows.append(("positive-reference", name, name, None))
    for name in _CONTROLS:
        rows.append(("required-control", name, None, None))
    for name in _COMPARATORS:
        rows.append(("adaptive-comparator", name, None, None))
    for parent in _REFERENCES:
        for name in _INTERVENTIONS:
            rows.append(("causal-intervention", name, parent, name))
        rows.append(("recurrence-intervention", _RESET, parent, _RESET))
    rows.append(("identity-placebo", _PLACEBO, None, None))
    return tuple(rows)


_EXPECTED_CONDITIONS = _inventory()


def _metric(
    trace: dict[str, Any],
    episodes: list[dict[str, int]],
) -> dict[str, Any]:
    mistakes: list[int] = []
    status_counts = {"valid": 0, "invalid": 0, "timeout": 0, "missing": 0}
    for position in range(_HORIZON):
        status = trace["prediction_statuses"][position]
        prediction = trace["predictions"][position]
        outcome = trace["outcomes"][position]
        status_counts[status] += 1
        mistakes.append(0 if status == "valid" and prediction == outcome else 1)

    prefix = [0]
    for mistake in mistakes:
        prefix.append(prefix[-1] + mistake)
    cumulative = prefix[1:]
    rolling = [
        prefix[end] - prefix[end - 16]
        for end in range(16, _HORIZON + 1)
    ]

    per_episode: list[dict[str, Any]] = []
    start = 0
    for episode in episodes:
        dwell = episode["dwell"]
        segment = mistakes[start : start + dwell]
        recovery = dwell
        for offset in range(dwell - 7):
            if not any(segment[offset:]):
                recovery = offset
                break
        index = episode["episode_index"]
        error_count = sum(segment)
        per_episode.append(
            {
                "episode_index": index,
                "dwell": dwell,
                "episode_kind": "new" if index in _NEW else "recurring",
                "errors": error_count,
                "recovery": recovery,
                "late_window_errors": sum(segment[dwell - 16 :]),
                "post_change_excess_errors": None if index == 0 else error_count,
            }
        )
        start += dwell

    return {
        "denominator": _HORIZON,
        "errors": prefix[-1],
        "valid_predictions": status_counts["valid"],
        "invalid_predictions": status_counts["invalid"],
        "timeout_predictions": status_counts["timeout"],
        "missing_predictions": status_counts["missing"],
        "cumulative_errors": cumulative,
        "rolling_errors": rolling,
        "episode_metrics": per_episode,
    }


def _validate_case(raw: object) -> tuple[
    dict[str, Any],
    dict[tuple[str, str, str | None, str | None], dict[str, Any]],
    dict[tuple[str, str, str | None, str | None], dict[str, Any]],
]:
    case = _dictionary(
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
    if type(case["case_id"]) is not str or _HEX.fullmatch(case["case_id"]) is None:
        raise ShadowScoringError("case identity is malformed")
    if type(case["case_index"]) is not int or case["case_index"] < 0:
        raise ShadowScoringError("case index is malformed")
    if type(case["placebo_projection_bytes_identical"]) is not bool:
        raise ShadowScoringError("placebo byte identity must be an exact boolean")

    episodes = case["episodes"]
    if type(episodes) is not list or len(episodes) != _EPISODES:
        raise ShadowScoringError("case episodes differ from the frozen schedule")
    normalized_episodes: list[dict[str, int]] = []
    for index in range(_EPISODES):
        episode = _dictionary(episodes[index], {"episode_index", "dwell"}, "episode")
        if (
            type(episode["episode_index"]) is not int
            or episode["episode_index"] != index
            or type(episode["dwell"]) is not int
            or episode["dwell"] not in _DWELLS
        ):
            raise ShadowScoringError("episode identity differs")
        normalized_episodes.append(episode)
    if sorted(item["dwell"] for item in normalized_episodes) != list(_DWELLS):
        raise ShadowScoringError("episode dwell schedule differs")
    if sum(item["dwell"] for item in normalized_episodes) != _HORIZON:
        raise ShadowScoringError("episode horizon differs")

    world_queries = case["world_query_ids"]
    world_outcomes = case["world_outcomes"]
    if type(world_queries) is not list or len(world_queries) != _HORIZON:
        raise ShadowScoringError("world query denominator differs")
    if type(world_outcomes) is not list or len(world_outcomes) != _HORIZON:
        raise ShadowScoringError("world outcome denominator differs")
    seen_queries: set[str] = set()
    for query in world_queries:
        if type(query) is not str or _HEX.fullmatch(query) is None or query in seen_queries:
            raise ShadowScoringError("world query identities differ")
        seen_queries.add(query)
    for outcome in world_outcomes:
        if type(outcome) is not int or outcome not in (0, 1):
            raise ShadowScoringError("world outcomes are not exact bits")

    conditions = case["conditions"]
    if type(conditions) is not dict or len(conditions) != len(_EXPECTED_CONDITIONS):
        raise ShadowScoringError("condition inventory cardinality differs")
    traces: dict[tuple[str, str, str | None, str | None], dict[str, Any]] = {}
    for opaque_id, raw_trace in conditions.items():
        if type(opaque_id) is not str or _HEX.fullmatch(opaque_id) is None:
            raise ShadowScoringError("condition identity is not opaque SHA-256")
        trace = _dictionary(
            raw_trace,
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
        if type(trace["role"]) is not str or type(trace["mechanism_id"]) is not str:
            raise ShadowScoringError("condition classification is malformed")
        if trace["reference_id"] is not None and type(trace["reference_id"]) is not str:
            raise ShadowScoringError("condition reference identity is malformed")
        if trace["intervention_id"] is not None and type(trace["intervention_id"]) is not str:
            raise ShadowScoringError("condition intervention identity is malformed")
        if trace["query_ids"] != world_queries:
            raise ShadowScoringError("condition queries do not bind the controller world")
        if trace["outcomes"] != world_outcomes:
            raise ShadowScoringError("condition outcomes do not bind independent reality")
        predictions = trace["predictions"]
        statuses = trace["prediction_statuses"]
        if type(predictions) is not list or len(predictions) != _HORIZON:
            raise ShadowScoringError("prediction denominator differs")
        if type(statuses) is not list or len(statuses) != _HORIZON:
            raise ShadowScoringError("prediction status denominator differs")
        for position in range(_HORIZON):
            status = statuses[position]
            prediction = predictions[position]
            if status not in ("valid", "invalid", "timeout", "missing") or type(status) is not str:
                raise ShadowScoringError("prediction status is unavailable")
            if status == "valid":
                if type(prediction) is not int or prediction not in (0, 1):
                    raise ShadowScoringError("valid prediction is not an exact bit")
            elif prediction is not None:
                raise ShadowScoringError("failed prediction slot must be null")
        key = (
            trace["role"],
            trace["mechanism_id"],
            trace["reference_id"],
            trace["intervention_id"],
        )
        if key in traces:
            raise ShadowScoringError("condition descriptor is duplicated")
        traces[key] = trace
    if set(traces) != set(_EXPECTED_CONDITIONS):
        raise ShadowScoringError("condition descriptors differ from the frozen inventory")
    metrics = {
        descriptor: _metric(traces[descriptor], normalized_episodes)
        for descriptor in _EXPECTED_CONDITIONS
    }
    return case, traces, metrics


def _reference_result(
    name: str,
    metrics: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
) -> dict[str, Any]:
    live = metrics[("positive-reference", name, name, None)]
    episode_metrics = live["episode_metrics"]
    new_sum = 0
    recurring_sum = 0
    for index in _NEW:
        new_sum += episode_metrics[index]["recovery"]
    for index in _RETURNING:
        recurring_sum += episode_metrics[index]["recovery"]

    comparisons = []
    for control in _CONTROLS:
        other_errors = metrics[("required-control", control, None, None)]["errors"]
        delta = other_errors - live["errors"]
        comparisons.append(
            {
                "control_id": control,
                "control_errors": other_errors,
                "reference_errors": live["errors"],
                "error_difference": delta,
                "margin_pass": 20 * delta >= _HORIZON,
            }
        )

    immutable_errors = metrics[("required-control", "immutable-seed", None, None)][
        "errors"
    ]
    lift = immutable_errors - live["errors"]
    intervention_rows = []
    for intervention in _INTERVENTIONS:
        errors = metrics[
            ("causal-intervention", intervention, name, intervention)
        ]["errors"]
        residual = immutable_errors - errors
        if residual < 0:
            residual = 0
        intervention_rows.append(
            {
                "intervention_id": intervention,
                "intervention_errors": errors,
                "surviving_advantage": residual,
                "causal_loss_pass": lift > 0 and 10 * residual <= lift,
            }
        )

    reset = metrics[("recurrence-intervention", _RESET, name, _RESET)]
    live_returning = sum(episode_metrics[index]["errors"] for index in _RETURNING)
    reset_returning = sum(
        reset["episode_metrics"][index]["errors"] for index in _RETURNING
    )
    gate_values = {
        "cumulative_error": live["errors"] * 6 <= _HORIZON,
        "rolling_error": max(live["rolling_errors"] or [0]) <= 12,
        "new_recovery": all(
            episode_metrics[index]["recovery"] <= 12 for index in _NEW
        ),
        "recurring_recovery": all(
            episode_metrics[index]["recovery"] <= 8 for index in _RETURNING
        ),
        "late_episode": all(
            item["late_window_errors"] == 0 for item in episode_metrics
        ),
        "relearning_savings": new_sum - recurring_sum >= 12,
        "control_margins": all(item["margin_pass"] for item in comparisons),
        "live_advantage": lift > 0,
        "causal_interventions": all(
            item["causal_loss_pass"] for item in intervention_rows
        ),
        "cross_episode_reset": reset_returning - live_returning >= 8,
    }
    return {
        "reference_id": name,
        "new_recovery_sum": new_sum,
        "recurring_recovery_sum": recurring_sum,
        "relearning_savings": new_sum - recurring_sum,
        "live_advantage": lift,
        "control_margins": comparisons,
        "causal_interventions": intervention_rows,
        "live_recurring_errors": live_returning,
        "reset_recurring_errors": reset_returning,
        "gates": gate_values,
        "pass": all(gate_values.values()),
    }


def _score_one(raw: object) -> dict[str, Any]:
    case, traces, metrics = _validate_case(raw)
    rows = []
    for descriptor in _EXPECTED_CONDITIONS:
        role, mechanism, reference, intervention = descriptor
        rows.append(
            {
                "role": role,
                "mechanism_id": mechanism,
                "reference_id": reference,
                "intervention_id": intervention,
                "metrics": metrics[descriptor],
            }
        )
    references = [_reference_result(name, metrics) for name in _REFERENCES]
    immutable_trace = traces[("required-control", "immutable-seed", None, None)]
    placebo_trace = traces[("identity-placebo", _PLACEBO, None, None)]
    placebo_gates = {
        "projection_bytes_identical": case["placebo_projection_bytes_identical"],
        "prediction_trace_identical": (
            immutable_trace["predictions"] == placebo_trace["predictions"]
            and immutable_trace["prediction_statuses"]
            == placebo_trace["prediction_statuses"]
        ),
        "score_identical": (
            metrics[("required-control", "immutable-seed", None, None)]
            == metrics[("identity-placebo", _PLACEBO, None, None)]
        ),
    }
    return {
        "case_id": case["case_id"],
        "case_index": case["case_index"],
        "lineage_metrics": rows,
        "reference_gates": references,
        "identity_placebo_gate": placebo_gates,
        "case_pass": all(item["pass"] for item in references)
        and all(placebo_gates.values()),
    }


def score_bundle_shadow(bundle: object) -> dict[str, Any]:
    """Independently validate and score a complete OT-0075 trace bundle."""

    root = _dictionary(
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
    purpose = root["purpose"]
    if purpose == "design":
        expected_cases = _DESIGN
    elif purpose == "anchor":
        expected_cases = _ANCHORS
    else:
        raise ShadowScoringError("trace bundle purpose is unavailable")
    if root["schema_version"] != _SCHEMA or root["experiment_id"] != _EXPERIMENT:
        raise ShadowScoringError("trace bundle identity differs")
    if type(root["case_count"]) is not int or root["case_count"] != expected_cases:
        raise ShadowScoringError("trace bundle case count differs")
    if type(root["cases"]) is not list or len(root["cases"]) != expected_cases:
        raise ShadowScoringError("trace bundle cases differ")

    defects = _flags(root["authority_defect_rejections"], _DEFECTS, "authority defect rejections")
    causal = _flags(root["causal_path_gates"], _PATH_GATES, "causal path gates")
    replay = _flags(root["rollback_replay_gates"], _REPLAY_GATES, "rollback replay gates")
    execution = _flags(root["execution_gates"], _RUN_GATES, "execution gates")

    cases = [_score_one(case) for case in root["cases"]]
    global_queries: list[str] = []
    global_conditions: list[str] = []
    for raw_case in root["cases"]:
        global_queries.extend(raw_case["world_query_ids"])
        global_conditions.extend(raw_case["conditions"])
    if len(set(global_queries)) != expected_cases * _HORIZON:
        raise ShadowScoringError("world query identities are not unique across cases")
    if len(set(global_conditions)) != expected_cases * len(_EXPECTED_CONDITIONS):
        raise ShadowScoringError("condition identities are not unique across cases")

    indices = [case["case_index"] for case in cases]
    identities = [case["case_id"] for case in cases]
    if set(indices) != set(range(expected_cases)) or len(set(identities)) != expected_cases:
        raise ShadowScoringError("bundle case identities differ")
    cases = sorted(cases, key=lambda item: item["case_index"])

    families = []
    for reference in _REFERENCES:
        for control in _CONTROLS:
            win_count = 0
            for case in cases:
                indexed = {}
                for item in case["lineage_metrics"]:
                    key = (
                        item["role"],
                        item["mechanism_id"],
                        item["reference_id"],
                        item["intervention_id"],
                    )
                    indexed[key] = item["metrics"]
                reference_errors = indexed[
                    ("positive-reference", reference, reference, None)
                ]["errors"]
                control_errors = indexed[("required-control", control, None, None)][
                    "errors"
                ]
                if reference_errors < control_errors:
                    win_count += 1
            families.append(
                {
                    "reference_id": reference,
                    "control_id": control,
                    "wins": win_count,
                    "streams": expected_cases,
                    "all_streams_win": win_count == expected_cases,
                }
            )

    numerator = len(_REFERENCES) * len(_CONTROLS)
    denominator = 2**expected_cases
    aggregate = {
        "stream_count": expected_cases,
        "paired_families": families,
        "paired_win_pass": all(item["all_streams_win"] for item in families),
        "familywise_sign_numerator": numerator,
        "familywise_sign_denominator": denominator,
        "familywise_sign_bound_pass": numerator * 20 <= denominator,
        "every_stream_pass": all(case["case_pass"] for case in cases),
        "adaptive_comparators_reported": all(
            len(
                [
                    item
                    for item in case["lineage_metrics"]
                    if item["role"] == "adaptive-comparator"
                ]
            )
            == len(_COMPARATORS)
            for case in cases
        ),
    }
    gates = {
        "every_stream": aggregate["every_stream_pass"],
        "paired_control_wins": aggregate["paired_win_pass"],
        "familywise_sign_bound": aggregate["familywise_sign_bound_pass"],
        "adaptive_comparators_reported": aggregate[
            "adaptive_comparators_reported"
        ],
        "authority_defects_rejected": all(defects.values()),
        "causal_path": all(causal.values()),
        "rollback_replay": all(replay.values()),
        "execution": all(execution.values()),
    }
    trace_pass = all(gates.values())
    promoted = purpose == "anchor" and trace_pass
    return {
        "schema_version": _SCHEMA,
        "experiment_id": _EXPERIMENT,
        "purpose": purpose,
        "case_count": expected_cases,
        "cases": cases,
        "aggregate": aggregate,
        "authority_defect_rejections": {name: defects[name] for name in _DEFECTS},
        "causal_path_gates": {name: causal[name] for name in _PATH_GATES},
        "rollback_replay_gates": {name: replay[name] for name in _REPLAY_GATES},
        "execution_gates": {name: execution[name] for name in _RUN_GATES},
        "promotion_gates": gates,
        "trace_gate_pass": trace_pass,
        "anchor_promotion_pass": promoted,
        "authorized_actor_candidate_count": 1 if promoted else 0,
        "claim_limit": "candidate-free evaluator-visible surrogate calibration only",
    }
