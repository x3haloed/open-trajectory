"""Independent shadow scorer for completed OT-0076 traces.

This module intentionally imports neither the primary scorer nor the task
protocol.  It repeats the frozen schema and arithmetic so byte-equal normalized
results are evidence from two separately implemented decision paths.
"""

from __future__ import annotations

import re
from typing import Any


_EXPERIMENT = "OT-0076"
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
_MATCHED = tuple(f"{name}--matched-frozen-initial" for name in _REFERENCES)
_MATCHED_FOR = dict(zip(_REFERENCES, _MATCHED, strict=True))
_COMPARATORS = (
    "recent-verbatim-world-row-window",
    "lossless-log-naive-nearest-retrieval",
)
_HARD = (
    "consequence-withholding",
    "update-without-projection",
    "projection-without-update",
)
_STALE = "one-step-stale-consequence"
_WRONG = "wrong-lineage-projection"
_INTERVENTIONS = (
    "consequence-withholding",
    _STALE,
    "update-without-projection",
    "projection-without-update",
    _WRONG,
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
    "next_projection_binds_exact_post_state_or_declared_update_without_projection_cut",
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
_EVIDENCE_KEYS = {
    "consumed_projection_sha256s",
    "terminal_projection_sha256",
    "accepted_updates",
    "candidate_state_changed",
    "active_projection_changed",
}
_HEX = re.compile(r"[0-9a-f]{64}")


class ShadowScoringError(ValueError):
    """The shadow scorer received a trace outside its frozen contract."""


def _dictionary(raw: object, names: tuple[str, ...] | set[str], what: str) -> dict[str, Any]:
    if type(raw) is not dict or set(raw) != set(names):
        raise ShadowScoringError(f"{what} keys differ from the frozen schema")
    return raw


def _flags(raw: object, names: tuple[str, ...], what: str) -> dict[str, bool]:
    flags = _dictionary(raw, names, what)
    if any(type(flags[name]) is not bool for name in names):
        raise ShadowScoringError(f"{what} values must be exact booleans")
    return flags


def _inventory() -> tuple[tuple[str, str, str | None, str | None], ...]:
    rows: list[tuple[str, str, str | None, str | None]] = []
    rows.extend(("positive-reference", name, name, None) for name in _REFERENCES)
    rows.extend(("required-control", name, None, None) for name in _CONTROLS)
    rows.extend(
        ("matched-frozen-control", _MATCHED_FOR[name], name, None)
        for name in _REFERENCES
    )
    rows.extend(("adaptive-comparator", name, None, None) for name in _COMPARATORS)
    for parent in _REFERENCES:
        rows.extend(
            ("causal-intervention", name, parent, name)
            for name in _INTERVENTIONS
        )
        rows.append(("recurrence-intervention", _RESET, parent, _RESET))
    rows.append(("identity-placebo", _PLACEBO, None, None))
    return tuple(rows)


_EXPECTED_CONDITIONS = _inventory()


def _evidence(raw: object) -> dict[str, Any]:
    value = _dictionary(raw, _EVIDENCE_KEYS, "causal evidence")
    consumed = value["consumed_projection_sha256s"]
    if (
        type(consumed) is not list
        or len(consumed) != _HORIZON
        or any(type(item) is not str or _HEX.fullmatch(item) is None for item in consumed)
    ):
        raise ShadowScoringError("consumed projection identities differ")
    if (
        type(value["terminal_projection_sha256"]) is not str
        or _HEX.fullmatch(value["terminal_projection_sha256"]) is None
    ):
        raise ShadowScoringError("terminal projection identity differs")
    count = value["accepted_updates"]
    if type(count) is not int or count < 0 or count > _HORIZON:
        raise ShadowScoringError("accepted update count differs")
    if type(value["candidate_state_changed"]) is not bool:
        raise ShadowScoringError("candidate change evidence differs")
    if type(value["active_projection_changed"]) is not bool:
        raise ShadowScoringError("active projection evidence differs")
    return value


def _metric(trace: dict[str, Any], episodes: list[dict[str, int]]) -> dict[str, Any]:
    mistakes: list[int] = []
    counts = {"valid": 0, "invalid": 0, "timeout": 0, "missing": 0}
    for index in range(_HORIZON):
        status = trace["prediction_statuses"][index]
        prediction = trace["predictions"][index]
        outcome = trace["outcomes"][index]
        counts[status] += 1
        mistakes.append(int(status != "valid" or prediction != outcome))
    prefix = [0]
    for mistake in mistakes:
        prefix.append(prefix[-1] + mistake)
    rolling = [prefix[end] - prefix[end - 16] for end in range(16, _HORIZON + 1)]
    per_episode = []
    start = 0
    for episode in episodes:
        dwell = episode["dwell"]
        segment = mistakes[start : start + dwell]
        last_error = -1
        for offset, mistake in enumerate(segment):
            if mistake:
                last_error = offset
        possible = last_error + 1
        recovery = possible if possible <= dwell - 8 else dwell
        episode_index = episode["episode_index"]
        per_episode.append(
            {
                "episode_index": episode_index,
                "dwell": dwell,
                "episode_kind": "new" if episode_index in _NEW else "recurring",
                "errors": sum(segment),
                "recovery": recovery,
                "late_window_errors": sum(segment[dwell - 16 :]),
                "post_change_excess_errors": None if episode_index == 0 else sum(segment),
            }
        )
        start += dwell
    return {
        "denominator": _HORIZON,
        "errors": prefix[-1],
        "valid_predictions": counts["valid"],
        "invalid_predictions": counts["invalid"],
        "timeout_predictions": counts["timeout"],
        "missing_predictions": counts["missing"],
        "cumulative_errors": prefix[1:],
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
        raise ShadowScoringError("placebo byte identity differs")
    episodes = case["episodes"]
    if type(episodes) is not list or len(episodes) != _EPISODES:
        raise ShadowScoringError("case episodes differ")
    normalized_episodes = []
    for index, raw_episode in enumerate(episodes):
        episode = _dictionary(raw_episode, {"episode_index", "dwell"}, "episode")
        if (
            type(episode["episode_index"]) is not int
            or episode["episode_index"] != index
            or type(episode["dwell"]) is not int
            or episode["dwell"] not in _DWELLS
        ):
            raise ShadowScoringError("episode identity differs")
        normalized_episodes.append(episode)
    if sorted(item["dwell"] for item in normalized_episodes) != list(_DWELLS):
        raise ShadowScoringError("episode schedule differs")
    if sum(item["dwell"] for item in normalized_episodes) != _HORIZON:
        raise ShadowScoringError("episode horizon differs")
    queries = case["world_query_ids"]
    outcomes = case["world_outcomes"]
    if type(queries) is not list or len(queries) != _HORIZON:
        raise ShadowScoringError("world query denominator differs")
    if type(outcomes) is not list or len(outcomes) != _HORIZON:
        raise ShadowScoringError("world outcome denominator differs")
    if any(type(item) is not str or _HEX.fullmatch(item) is None for item in queries):
        raise ShadowScoringError("world query identity differs")
    if len(set(queries)) != _HORIZON:
        raise ShadowScoringError("world query identities repeat")
    if any(type(item) is not int or item not in (0, 1) for item in outcomes):
        raise ShadowScoringError("world outcomes differ")
    raw_conditions = case["conditions"]
    if type(raw_conditions) is not dict or len(raw_conditions) != len(_EXPECTED_CONDITIONS):
        raise ShadowScoringError("condition inventory cardinality differs")
    traces: dict[tuple[str, str, str | None, str | None], dict[str, Any]] = {}
    for opaque_id, raw_trace in raw_conditions.items():
        if type(opaque_id) is not str or _HEX.fullmatch(opaque_id) is None:
            raise ShadowScoringError("condition identity differs")
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
                "causal_evidence",
            },
            "condition",
        )
        if type(trace["role"]) is not str or type(trace["mechanism_id"]) is not str:
            raise ShadowScoringError("condition classification differs")
        if trace["reference_id"] is not None and type(trace["reference_id"]) is not str:
            raise ShadowScoringError("condition reference differs")
        if trace["intervention_id"] is not None and type(trace["intervention_id"]) is not str:
            raise ShadowScoringError("condition intervention differs")
        if trace["query_ids"] != queries or trace["outcomes"] != outcomes:
            raise ShadowScoringError("condition world binding differs")
        predictions = trace["predictions"]
        statuses = trace["prediction_statuses"]
        if type(predictions) is not list or len(predictions) != _HORIZON:
            raise ShadowScoringError("prediction denominator differs")
        if type(statuses) is not list or len(statuses) != _HORIZON:
            raise ShadowScoringError("prediction status denominator differs")
        for prediction, status in zip(predictions, statuses, strict=True):
            if type(status) is not str or status not in ("valid", "invalid", "timeout", "missing"):
                raise ShadowScoringError("prediction status differs")
            if status == "valid":
                if type(prediction) is not int or prediction not in (0, 1):
                    raise ShadowScoringError("valid prediction differs")
            elif prediction is not None:
                raise ShadowScoringError("failed prediction must be null")
        _evidence(trace["causal_evidence"])
        descriptor = (
            trace["role"],
            trace["mechanism_id"],
            trace["reference_id"],
            trace["intervention_id"],
        )
        if descriptor in traces:
            raise ShadowScoringError("condition descriptor repeats")
        traces[descriptor] = trace
    if set(traces) != set(_EXPECTED_CONDITIONS):
        raise ShadowScoringError("condition descriptors differ")
    metrics = {
        descriptor: _metric(traces[descriptor], normalized_episodes)
        for descriptor in _EXPECTED_CONDITIONS
    }
    return case, traces, metrics


def _matched_gate(
    name: str,
    traces: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
) -> dict[str, Any]:
    live = traces[("positive-reference", name, name, None)]["causal_evidence"]
    control_id = _MATCHED_FOR[name]
    frozen = traces[("matched-frozen-control", control_id, name, None)]["causal_evidence"]
    projections = frozen["consumed_projection_sha256s"]
    initial_equal = live["consumed_projection_sha256s"][0] == projections[0]
    trace_frozen = all(item == projections[0] for item in projections)
    trace_frozen = trace_frozen and frozen["terminal_projection_sha256"] == projections[0]
    no_op = (
        frozen["accepted_updates"] == 0
        and frozen["candidate_state_changed"] is False
        and frozen["active_projection_changed"] is False
    )
    return {
        "control_id": control_id,
        "initial_projection_equal": initial_equal,
        "frozen_projection_trace": trace_frozen,
        "no_op_evidence": no_op,
        "pass": initial_equal and trace_frozen and no_op,
    }


def _hard_result(
    name: str,
    intervention: str,
    traces: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
    metrics: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
) -> dict[str, Any]:
    matched_descriptor = ("matched-frozen-control", _MATCHED_FOR[name], name, None)
    cut_descriptor = ("causal-intervention", intervention, name, intervention)
    matched = traces[matched_descriptor]
    cut = traces[cut_descriptor]
    matched_evidence = matched["causal_evidence"]
    evidence = cut["causal_evidence"]
    baseline_errors = metrics[matched_descriptor]["errors"]
    cut_errors = metrics[cut_descriptor]["errors"]
    surviving = max(0, baseline_errors - cut_errors)
    trace_equal = (
        cut["predictions"] == matched["predictions"]
        and cut["prediction_statuses"] == matched["prediction_statuses"]
    )
    projections_equal = (
        evidence["consumed_projection_sha256s"]
        == matched_evidence["consumed_projection_sha256s"]
    )
    terminal_equal = (
        evidence["terminal_projection_sha256"]
        == matched_evidence["terminal_projection_sha256"]
    )
    if intervention == "update-without-projection":
        operation = (
            evidence["accepted_updates"] >= 1
            and evidence["candidate_state_changed"] is True
            and evidence["active_projection_changed"] is False
        )
    else:
        operation = (
            evidence["accepted_updates"] == 0
            and evidence["candidate_state_changed"] is False
            and evidence["active_projection_changed"] is False
        )
    gates = {
        "zero_surviving_lift": surviving == 0,
        "prediction_status_trace_equal": trace_equal,
        "consumed_projection_trace_equal": projections_equal,
        "terminal_projection_equal": terminal_equal,
        "operation_evidence": operation,
    }
    return {
        "intervention_id": intervention,
        "matched_frozen_errors": baseline_errors,
        "intervention_errors": cut_errors,
        "surviving_lift": surviving,
        "accepted_updates": evidence["accepted_updates"],
        "candidate_state_changed": evidence["candidate_state_changed"],
        "active_projection_changed": evidence["active_projection_changed"],
        "gates": gates,
        "pass": all(gates.values()),
    }


def _stale_result(
    name: str,
    live_lift: int,
    traces: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
    metrics: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
) -> dict[str, Any]:
    live_descriptor = ("positive-reference", name, name, None)
    matched_descriptor = ("matched-frozen-control", _MATCHED_FOR[name], name, None)
    stale_descriptor = ("causal-intervention", _STALE, name, _STALE)
    live_errors = metrics[live_descriptor]["errors"]
    baseline_errors = metrics[matched_descriptor]["errors"]
    stale = metrics[stale_descriptor]
    stale_errors = stale["errors"]
    residual = max(0, baseline_errors - stale_errors)
    evidence = traces[stale_descriptor]["causal_evidence"]
    gates = {
        "two_thirds_lift_lost": 3 * residual <= live_lift,
        "worse_than_live_by_practical_margin": 20 * (stale_errors - live_errors) >= _HORIZON,
        "accepted_update": evidence["accepted_updates"] >= 1,
        "active_projection_changed": evidence["active_projection_changed"] is True,
    }
    return {
        "intervention_id": _STALE,
        "matched_frozen_errors": baseline_errors,
        "live_errors": live_errors,
        "stale_errors": stale_errors,
        "stale_valid_predictions": stale["valid_predictions"],
        "residual_lift": residual,
        "accepted_updates": evidence["accepted_updates"],
        "candidate_state_changed": evidence["candidate_state_changed"],
        "active_projection_changed": evidence["active_projection_changed"],
        "gates": gates,
        "pass": all(gates.values()),
    }


def _wrong_result(
    name: str,
    traces: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
    metrics: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
) -> dict[str, Any]:
    descriptor = ("causal-intervention", _WRONG, name, _WRONG)
    metric = metrics[descriptor]
    evidence = traces[descriptor]["causal_evidence"]
    gates = {
        "all_predictions_rejected": (
            metric["invalid_predictions"] == _HORIZON
            and metric["valid_predictions"] == 0
            and metric["errors"] == _HORIZON
        ),
        "no_update_or_change": (
            evidence["accepted_updates"] == 0
            and evidence["candidate_state_changed"] is False
            and evidence["active_projection_changed"] is False
        ),
    }
    return {
        "intervention_id": _WRONG,
        "errors": metric["errors"],
        "invalid_predictions": metric["invalid_predictions"],
        "gates": gates,
        "pass": all(gates.values()),
    }


def _reference_result(
    name: str,
    traces: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
    metrics: dict[tuple[str, str, str | None, str | None], dict[str, Any]],
) -> dict[str, Any]:
    live_descriptor = ("positive-reference", name, name, None)
    matched_descriptor = ("matched-frozen-control", _MATCHED_FOR[name], name, None)
    live = metrics[live_descriptor]
    episodes = live["episode_metrics"]
    new_sum = sum(episodes[index]["recovery"] for index in _NEW)
    returning_sum = sum(episodes[index]["recovery"] for index in _RETURNING)
    margins = []
    for control in _CONTROLS:
        control_errors = metrics[("required-control", control, None, None)]["errors"]
        difference = control_errors - live["errors"]
        margins.append(
            {
                "control_id": control,
                "control_errors": control_errors,
                "reference_errors": live["errors"],
                "error_difference": difference,
                "margin_pass": 20 * difference >= _HORIZON,
            }
        )
    matched_errors = metrics[matched_descriptor]["errors"]
    lift = matched_errors - live["errors"]
    margin_pass = 20 * lift >= _HORIZON
    matched_gate = _matched_gate(name, traces)
    hard = [_hard_result(name, intervention, traces, metrics) for intervention in _HARD]
    stale = _stale_result(name, lift, traces, metrics)
    wrong = _wrong_result(name, traces, metrics)
    reset = metrics[("recurrence-intervention", _RESET, name, _RESET)]
    live_returning = sum(episodes[index]["errors"] for index in _RETURNING)
    reset_returning = sum(reset["episode_metrics"][index]["errors"] for index in _RETURNING)
    gates = {
        "cumulative_error": live["errors"] * 6 <= _HORIZON,
        "rolling_error": max(live["rolling_errors"] or [0]) <= 12,
        "new_recovery": all(episodes[index]["recovery"] <= 12 for index in _NEW),
        "recurring_recovery": all(episodes[index]["recovery"] <= 8 for index in _RETURNING),
        "late_episode": all(item["late_window_errors"] == 0 for item in episodes),
        "relearning_savings": new_sum - returning_sum >= 12,
        "control_margins": all(item["margin_pass"] for item in margins),
        "matched_live_lift": margin_pass,
        "matched_control": matched_gate["pass"],
        "hard_severings": all(item["pass"] for item in hard),
        "stale_binding": stale["pass"],
        "wrong_lineage_rejected": wrong["pass"],
        "cross_episode_reset": reset_returning - live_returning >= 8,
    }
    return {
        "reference_id": name,
        "new_recovery_sum": new_sum,
        "recurring_recovery_sum": returning_sum,
        "relearning_savings": new_sum - returning_sum,
        "matched_frozen_control_id": _MATCHED_FOR[name],
        "matched_frozen_errors": matched_errors,
        "live_errors": live["errors"],
        "matched_live_lift": lift,
        "matched_margin_pass": margin_pass,
        "control_margins": margins,
        "matched_control_gate": matched_gate,
        "hard_severings": hard,
        "stale_binding": stale,
        "wrong_lineage_gate": wrong,
        "live_recurring_errors": live_returning,
        "reset_recurring_errors": reset_returning,
        "gates": gates,
        "pass": all(gates.values()),
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
    references = [_reference_result(name, traces, metrics) for name in _REFERENCES]
    immutable_descriptor = ("required-control", "immutable-seed", None, None)
    placebo_descriptor = ("identity-placebo", _PLACEBO, None, None)
    immutable = traces[immutable_descriptor]
    placebo = traces[placebo_descriptor]
    immutable_evidence = immutable["causal_evidence"]
    placebo_evidence = placebo["causal_evidence"]
    placebo_gate = {
        "projection_bytes_identical": case["placebo_projection_bytes_identical"],
        "consumed_projection_trace_identical": (
            immutable_evidence["consumed_projection_sha256s"]
            == placebo_evidence["consumed_projection_sha256s"]
        ),
        "terminal_projection_identical": (
            immutable_evidence["terminal_projection_sha256"]
            == placebo_evidence["terminal_projection_sha256"]
        ),
        "prediction_trace_identical": (
            immutable["predictions"] == placebo["predictions"]
            and immutable["prediction_statuses"] == placebo["prediction_statuses"]
        ),
        "score_identical": metrics[immutable_descriptor] == metrics[placebo_descriptor],
    }
    return {
        "case_id": case["case_id"],
        "case_index": case["case_index"],
        "lineage_metrics": rows,
        "reference_gates": references,
        "identity_placebo_gate": placebo_gate,
        "case_pass": all(item["pass"] for item in references) and all(placebo_gate.values()),
    }


def _metrics_by_descriptor(case: dict[str, Any]) -> dict[tuple[str, str, str | None, str | None], dict[str, Any]]:
    result = {}
    for item in case["lineage_metrics"]:
        descriptor = (
            item["role"],
            item["mechanism_id"],
            item["reference_id"],
            item["intervention_id"],
        )
        result[descriptor] = item["metrics"]
    return result


def score_bundle_shadow(bundle: object) -> dict[str, Any]:
    """Independently validate and score a complete OT-0076 trace bundle."""

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
    cases = [_score_one(raw_case) for raw_case in root["cases"]]
    all_queries = [item for raw_case in root["cases"] for item in raw_case["world_query_ids"]]
    all_conditions = [item for raw_case in root["cases"] for item in raw_case["conditions"]]
    if len(set(all_queries)) != expected_cases * _HORIZON:
        raise ShadowScoringError("world query identities repeat across cases")
    if len(set(all_conditions)) != expected_cases * len(_EXPECTED_CONDITIONS):
        raise ShadowScoringError("condition identities repeat across cases")
    indices = [case["case_index"] for case in cases]
    identities = [case["case_id"] for case in cases]
    if set(indices) != set(range(expected_cases)) or len(set(identities)) != expected_cases:
        raise ShadowScoringError("bundle case identities differ")
    cases.sort(key=lambda item: item["case_index"])
    families = []
    for reference in _REFERENCES:
        controls = [*_CONTROLS, _MATCHED_FOR[reference]]
        for control in controls:
            wins = 0
            for case in cases:
                metrics = _metrics_by_descriptor(case)
                reference_errors = metrics[("positive-reference", reference, reference, None)]["errors"]
                if control in _CONTROLS:
                    control_errors = metrics[("required-control", control, None, None)]["errors"]
                    kind = "global-required"
                else:
                    control_errors = metrics[("matched-frozen-control", control, reference, None)]["errors"]
                    kind = "matched-frozen"
                if reference_errors < control_errors:
                    wins += 1
            families.append(
                {
                    "reference_id": reference,
                    "control_id": control,
                    "control_kind": kind,
                    "wins": wins,
                    "streams": expected_cases,
                    "all_streams_win": wins == expected_cases,
                }
            )
    numerator = len(_REFERENCES) * (len(_CONTROLS) + 1)
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
            sum(item["role"] == "adaptive-comparator" for item in case["lineage_metrics"])
            == len(_COMPARATORS)
            for case in cases
        ),
    }
    gates = {
        "every_stream": aggregate["every_stream_pass"],
        "paired_control_wins": aggregate["paired_win_pass"],
        "familywise_sign_bound": aggregate["familywise_sign_bound_pass"],
        "adaptive_comparators_reported": aggregate["adaptive_comparators_reported"],
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
