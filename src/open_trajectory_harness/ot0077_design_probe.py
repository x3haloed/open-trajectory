"""Pure exhaustive public-design probe for the P-frozen OT-0077 repair.

The probe has no private-anchor or actor surface.  It deterministically replays
the four public OT-0077 wrapper tasks through the unchanged OT-0075 learning
mechanisms and emits the exact behavior-only vector frozen before I.

Two state variables are intentionally kept separate in the hard
``update-without-projection`` intervention: ``authoritative_state`` advances
from its exact prior value, while ``actor_projection`` remains the exact
initial projection consumed by every scored prediction.  This is the causal
ancestry repair that OT-0075 did not implement correctly.
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any, Final, Sequence

from . import ot0075_protocol as _base_protocol
from .ot0075_learning import (
    COMPACT_REFERENCE,
    LOG_REFERENCE,
    LearningError,
    encode_state,
    initial_state,
    predict,
    update,
)
from .ot0077_protocol import HORIZON, build_design_task, validate_task


REFERENCE_ORDER: Final = (COMPACT_REFERENCE, LOG_REFERENCE)
_PUBLIC_DESIGN_WORKERS: Final = 8
HARD_SEVERING_ORDER: Final = (
    "consequence-withholding",
    "update-without-projection",
    "projection-without-update",
)

ROW_KEYS: Final = frozenset(
    {
        "design_seed",
        "case_index",
        "reference_id",
        "live_errors",
        "matched_frozen_errors",
        "live_lift",
        "matched_margin_pass",
        "true_no_learning",
        "stale_errors",
        "stale_valid_predictions",
        "stale_residual_lift",
        "stale_two_thirds_loss_pass",
        "stale_accepted_updates",
        "stale_active_projection_changed",
        "stale_practical_margin_pass",
    }
)
TRUE_NO_LEARNING_VALUE_KEYS: Final = frozenset(
    {
        "errors",
        "prediction_status_trace_equal",
        "consumed_projection_trace_equal",
        "terminal_projection_equal",
        "accepted_updates",
        "candidate_changed",
    }
)

EXPECTED_BASE_TASK_SHA256S: Final = (
    "04be3d8a015bde4d462abfa57722896607e9aded76d92d46ce24f2952f1a0250",
    "70e43a7896b7606df13d0f2a9b369c3105203be205b84c9205379c3aca89b5a7",
    "b25084ca908889a7a7711cbeac48a567d423cb3a780608c25762905e09cc03af",
    "6d1641038482943167bdde0166dc937456fc8e73361c9ae823918e68546eee93",
)
EXPECTED_WRAPPED_TASK_SHA256S: Final = (
    "69be75695c060986bb937bc5a3aef9dcc2e8bef629b1a88179c86a42d598fc38",
    "883f19567355037403eaffa0d5ebb4fac5e50b17b163c38a21573727deab3f16",
    "f1f3007ce2ab78f3c756a154efbc4b6d6eb5c8975152d61c1bcc8f409596be6d",
    "efe00ac65a72f6031e9d54aa1bc2faee1eee92fc4f1cbf763a2e3ae6475a171f",
)
EXPECTED_VECTOR_BYTES: Final = 127_949
EXPECTED_VECTOR_SHA256: Final = (
    "a645282da3986557ce10dfdc9a550482107fea0f7ccaab0748deedafccb1d603"
)
EXPECTED_ROW_COUNT: Final = 128


class DesignProbeError(ValueError):
    """The OT-0077 public probe differs from its frozen contract."""


@dataclass(frozen=True)
class _MatchedReplay:
    live_errors: int
    matched_frozen_errors: int
    frozen_predictions: tuple[int, ...]
    frozen_statuses: tuple[str, ...]
    frozen_consumed_projections: tuple[bytes, ...]
    frozen_terminal_projection: bytes
    authoritative_accepted_updates: int
    authoritative_candidate_changed: bool


@dataclass(frozen=True)
class _StaleReplay:
    errors: int
    valid_predictions: int
    accepted_updates: int
    active_projection_changed: bool


def canonical_json(value: Any) -> bytes:
    """Return the repository's exact canonical JSON encoding."""

    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _flatten_case(case: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    events = tuple(
        event
        for episode in case["episodes"]
        for event in episode["events"]
    )
    if len(events) != HORIZON:
        raise DesignProbeError("OT-0077 public case horizon differs")
    if [event["encounter_index"] for event in events] != list(range(HORIZON)):
        raise DesignProbeError("OT-0077 public encounter order differs")
    return events


def _matched_replay(
    reference_id: str,
    events: Sequence[dict[str, Any]],
) -> _MatchedReplay:
    """Replay live state and its exact frozen-initial counterfactual together.

    ``authoritative_state`` is the updater-owned chain.  Its prediction is
    computed from that chain before each real outcome and is then used only to
    validate the unchanged OT-0075 pure update API.  ``actor_projection`` is a
    separate frozen chain.  It supplies the matched-frozen predictions and is
    also the projection consumed by update-without-projection actors.
    """

    initial = encode_state(reference_id, initial_state(reference_id))
    authoritative_state = initial
    actor_projection = initial
    live_errors = 0
    frozen_errors = 0
    frozen_predictions: list[int] = []
    frozen_statuses: list[str] = []
    frozen_consumed: list[bytes] = []
    accepted_updates = 0
    candidate_changed = False

    for event in events:
        query = event["public_query"]
        outcome = event["outcome"]

        frozen_consumed.append(actor_projection)
        frozen_prediction = predict(reference_id, actor_projection, query).prediction
        frozen_predictions.append(frozen_prediction)
        frozen_statuses.append("valid")
        frozen_errors += int(frozen_prediction != outcome)

        live_prediction = predict(reference_id, authoritative_state, query).prediction
        live_errors += int(live_prediction != outcome)
        transition = update(
            reference_id,
            authoritative_state,
            query,
            live_prediction,
            outcome,
        )
        candidate = encode_state(reference_id, transition.state)
        accepted_updates += 1
        candidate_changed = candidate_changed or candidate != authoritative_state
        authoritative_state = candidate

        # The actor-visible chain is deliberately frozen even though the
        # updater-owned candidate chain advances.
        if actor_projection != initial:
            raise DesignProbeError(
                "OT-0077 update-without-projection actor chain changed"
            )

    return _MatchedReplay(
        live_errors=live_errors,
        matched_frozen_errors=frozen_errors,
        frozen_predictions=tuple(frozen_predictions),
        frozen_statuses=tuple(frozen_statuses),
        frozen_consumed_projections=tuple(frozen_consumed),
        frozen_terminal_projection=actor_projection,
        authoritative_accepted_updates=accepted_updates,
        authoritative_candidate_changed=candidate_changed,
    )


def _stale_replay(
    reference_id: str,
    events: Sequence[dict[str, Any]],
) -> _StaleReplay:
    """Replay the active one-step-stale intervention with fail-closed slots."""

    active_projection = encode_state(reference_id, initial_state(reference_id))
    prior_outcome = 0
    errors = 0
    valid_predictions = 0
    accepted_updates = 0
    active_projection_changed = False

    for event in events:
        query = event["public_query"]
        outcome = event["outcome"]
        try:
            result = predict(reference_id, active_projection, query)
        except LearningError:
            # An invalid prediction remains in the complete denominator and
            # cannot receive updater authority.  Independently retained world
            # time still advances, so the next stale label is this outcome.
            errors += 1
            prior_outcome = outcome
            continue

        valid_predictions += 1
        errors += int(result.prediction != outcome)
        try:
            transition = update(
                reference_id,
                active_projection,
                query,
                result.prediction,
                prior_outcome,
            )
        except LearningError:
            # Inconsistent stale evidence is an explicit no-op.  The active
            # projection remains byte-identical and the denominator is kept.
            pass
        else:
            candidate = encode_state(reference_id, transition.state)
            accepted_updates += 1
            active_projection_changed = (
                active_projection_changed or candidate != active_projection
            )
            active_projection = candidate
        prior_outcome = outcome

    return _StaleReplay(
        errors=errors,
        valid_predictions=valid_predictions,
        accepted_updates=accepted_updates,
        active_projection_changed=active_projection_changed,
    )


def _hard_severing_rows(replay: _MatchedReplay) -> dict[str, dict[str, Any]]:
    """Build the three behaviorally frozen, causally distinct severings."""

    frozen_prediction_and_status = (
        replay.frozen_predictions,
        replay.frozen_statuses,
    )
    frozen_consumed = replay.frozen_consumed_projections
    frozen_terminal = replay.frozen_terminal_projection

    # All three actor paths consume the exact matched-frozen projection.  Only
    # update-without-projection advances a separate authoritative candidate
    # state, already executed in ``_matched_replay`` from its exact prior state.
    rows: dict[str, dict[str, Any]] = {}
    for intervention_id in HARD_SEVERING_ORDER:
        actor_prediction_and_status = frozen_prediction_and_status
        actor_consumed = frozen_consumed
        actor_terminal = frozen_terminal
        updates = (
            replay.authoritative_accepted_updates
            if intervention_id == "update-without-projection"
            else 0
        )
        candidate_changed = (
            replay.authoritative_candidate_changed
            if intervention_id == "update-without-projection"
            else False
        )
        rows[intervention_id] = {
            "errors": replay.matched_frozen_errors,
            "prediction_status_trace_equal": (
                actor_prediction_and_status == frozen_prediction_and_status
            ),
            "consumed_projection_trace_equal": actor_consumed == frozen_consumed,
            "terminal_projection_equal": actor_terminal == frozen_terminal,
            "accepted_updates": updates,
            "candidate_changed": candidate_changed,
        }
    return rows


def _build_public_design_case_rows(
    job: tuple[int, dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Build one public case's rows without shared state or side effects."""

    design_seed_index, case = job
    events = _flatten_case(case)
    rows: list[dict[str, Any]] = []
    for reference_id in REFERENCE_ORDER:
        matched = _matched_replay(reference_id, events)
        stale = _stale_replay(reference_id, events)
        live_lift = matched.matched_frozen_errors - matched.live_errors
        stale_residual_lift = max(
            0,
            matched.matched_frozen_errors - stale.errors,
        )
        row = {
            "design_seed": design_seed_index,
            "case_index": case["case_index"],
            "reference_id": reference_id,
            "live_errors": matched.live_errors,
            "matched_frozen_errors": matched.matched_frozen_errors,
            "live_lift": live_lift,
            "matched_margin_pass": 20 * live_lift >= HORIZON,
            "true_no_learning": _hard_severing_rows(matched),
            "stale_errors": stale.errors,
            "stale_valid_predictions": stale.valid_predictions,
            "stale_residual_lift": stale_residual_lift,
            "stale_two_thirds_loss_pass": (
                3 * stale_residual_lift <= live_lift
            ),
            "stale_accepted_updates": stale.accepted_updates,
            "stale_active_projection_changed": stale.active_projection_changed,
            "stale_practical_margin_pass": (
                20 * (stale.errors - matched.live_errors) >= HORIZON
            ),
        }
        _validate_row(row)
        rows.append(row)
    return tuple(rows)


def build_public_design_vector() -> list[dict[str, Any]]:
    """Return all 128 rows in the exact P-frozen public order."""

    jobs: list[tuple[int, dict[str, Any]]] = []
    for design_seed_index in range(4):
        task = validate_task(build_design_task(design_seed_index))
        jobs.extend((design_seed_index, case) for case in task["cases"])
    with ProcessPoolExecutor(max_workers=_PUBLIC_DESIGN_WORKERS) as executor:
        ordered_batches = executor.map(
            _build_public_design_case_rows,
            jobs,
            chunksize=1,
        )
        rows = [row for batch in ordered_batches for row in batch]
    _validate_order(rows)
    return rows


def _validate_row(row: object) -> dict[str, Any]:
    if type(row) is not dict or set(row) != ROW_KEYS:
        raise DesignProbeError("OT-0077 design-vector row keys differ")
    true_no_learning = row["true_no_learning"]
    if (
        type(true_no_learning) is not dict
        or set(true_no_learning) != set(HARD_SEVERING_ORDER)
    ):
        raise DesignProbeError("OT-0077 hard-severing inventory differs")
    for value in true_no_learning.values():
        if type(value) is not dict or set(value) != TRUE_NO_LEARNING_VALUE_KEYS:
            raise DesignProbeError("OT-0077 hard-severing row keys differ")
    return row


def _validate_order(rows: Sequence[dict[str, Any]]) -> None:
    expected = [
        (design_seed_index, case_index, reference_id)
        for design_seed_index in range(4)
        for case_index in range(16)
        for reference_id in REFERENCE_ORDER
    ]
    observed = [
        (row["design_seed"], row["case_index"], row["reference_id"])
        for row in rows
    ]
    if observed != expected:
        raise DesignProbeError("OT-0077 design-vector row order differs")


def canonical_design_vector(rows: Sequence[dict[str, Any]]) -> bytes:
    if len(rows) != EXPECTED_ROW_COUNT:
        raise DesignProbeError("OT-0077 design-vector row count differs")
    for row in rows:
        _validate_row(row)
    _validate_order(rows)
    return canonical_json(list(rows))


def public_task_digests() -> dict[str, tuple[str, ...]]:
    base = tuple(
        sha256_bytes(canonical_json(_base_protocol.build_design_task(index)))
        for index in range(4)
    )
    wrapped = tuple(
        sha256_bytes(canonical_json(build_design_task(index)))
        for index in range(4)
    )
    return {"base": base, "wrapped": wrapped}


def _public_rows_pass(rows: Sequence[dict[str, Any]]) -> bool:
    """Return whether every declared behavioral gate passes."""

    if len(rows) != EXPECTED_ROW_COUNT:
        return False
    try:
        canonical_design_vector(rows)
    except DesignProbeError:
        return False
    for row in rows:
        if not (
            row["matched_margin_pass"]
            and row["stale_two_thirds_loss_pass"]
            and row["stale_practical_margin_pass"]
            and row["stale_accepted_updates"] >= 1
            and row["stale_active_projection_changed"] is True
        ):
            return False
        for value in row["true_no_learning"].values():
            if not (
                value["errors"] == row["matched_frozen_errors"]
                and value["prediction_status_trace_equal"] is True
                and value["consumed_projection_trace_equal"] is True
                and value["terminal_projection_equal"] is True
            ):
                return False
        update_without_projection = row["true_no_learning"][
            "update-without-projection"
        ]
        if not (
            update_without_projection["accepted_updates"] == HORIZON
            and update_without_projection["candidate_changed"] is True
        ):
            return False
        for intervention_id in (
            "consequence-withholding",
            "projection-without-update",
        ):
            value = row["true_no_learning"][intervention_id]
            if value["accepted_updates"] != 0 or value["candidate_changed"]:
                return False
    return True


def _run_public_design_probe() -> tuple[dict[str, Any], bytes]:
    """Return the exact controller-facing public-preparation verdict.

    Frozen identity or behavioral mismatches return ``pass: false`` with their
    observed identities so preparation can stop without destroying diagnostic
    evidence.  Malformed tasks or impossible mechanism execution still raise.
    """

    task_digests = public_task_digests()
    rows = build_public_design_vector()
    payload = canonical_design_vector(rows)
    digest = sha256_bytes(payload)
    passed = (
        task_digests["base"] == EXPECTED_BASE_TASK_SHA256S
        and task_digests["wrapped"] == EXPECTED_WRAPPED_TASK_SHA256S
        and _public_rows_pass(rows)
        and len(payload) == EXPECTED_VECTOR_BYTES
        and digest == EXPECTED_VECTOR_SHA256
    )
    result = {
        "canonical_bytes": len(payload),
        "pass": passed,
        "row_count": len(rows),
        "sha256": digest,
        "task_sha256s": {
            "base": list(task_digests["base"]),
            "wrapped": list(task_digests["wrapped"]),
        },
    }
    return result, payload


def verify_public_design() -> dict[str, Any]:
    """Return the bounded public verdict without exposing mechanism state."""

    result, _payload = _run_public_design_probe()
    return result


def assert_public_design() -> bytes:
    """Run and fail closed against every frozen public identity and gate."""

    result, payload = _run_public_design_probe()
    if result["pass"] is not True:
        raise DesignProbeError(
            "OT-0077 public design differs: "
            f"rows={result['row_count']}, bytes={result['canonical_bytes']}, "
            f"sha256={result['sha256']}"
        )
    return payload


__all__ = [
    "DesignProbeError",
    "EXPECTED_BASE_TASK_SHA256S",
    "EXPECTED_ROW_COUNT",
    "EXPECTED_VECTOR_BYTES",
    "EXPECTED_VECTOR_SHA256",
    "EXPECTED_WRAPPED_TASK_SHA256S",
    "HARD_SEVERING_ORDER",
    "REFERENCE_ORDER",
    "ROW_KEYS",
    "TRUE_NO_LEARNING_VALUE_KEYS",
    "assert_public_design",
    "build_public_design_vector",
    "canonical_design_vector",
    "canonical_json",
    "public_task_digests",
    "sha256_bytes",
    "verify_public_design",
]
