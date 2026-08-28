"""Deterministic online learners and controls for the OT-0075 evaluator.

Every online mechanism in this module is a pure function of a canonical
projection, the current public query, and (for updates only) the just-released
outcome.  There is deliberately no module-level mutable learner state.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from typing import Any, Final, Iterable, Sequence

SCHEMA_VERSION: Final = 1
DIMENSION: Final = 12
HORIZON: Final = 242
MIN_MASK_WEIGHT: Final = 4
MAX_MASK_WEIGHT: Final = 8
STATE_BYTE_LIMIT: Final = 2_048
PREDICTION_OPERATION_LIMIT: Final = 131_072
UPDATE_OPERATION_LIMIT: Final = 131_072
IMMUTABLE_SEED_MASK: Final = 0b000000001111

COMPACT_REFERENCE: Final = "compact-cached-affine-version-space"
LOG_REFERENCE: Final = "lossless-epistemic-log-linear-bank"
NO_PERSISTENCE_CONTROL: Final = "no-persistence"
IMMUTABLE_SEED_CONTROL: Final = "immutable-seed"
CLOCK_CONTROL: Final = "encounter-index-clock"
RECENT_COMPARATOR: Final = "recent-verbatim-world-row-window"
NEAREST_COMPARATOR: Final = "lossless-log-naive-nearest-retrieval"

ONLINE_MECHANISMS: Final = (
    COMPACT_REFERENCE,
    LOG_REFERENCE,
    NO_PERSISTENCE_CONTROL,
    IMMUTABLE_SEED_CONTROL,
    CLOCK_CONTROL,
    RECENT_COMPARATOR,
    NEAREST_COMPARATOR,
)

_QUERY_ID = re.compile(r"[0-9a-f]{64}")
_MASK_LIMIT = 1 << DIMENSION
_ELIGIBLE_MASKS: Final = tuple(
    mask
    for mask in range(1, _MASK_LIMIT)
    if MIN_MASK_WEIGHT <= mask.bit_count() <= MAX_MASK_WEIGHT
)


class LearningError(ValueError):
    """An OT-0075 learner input, state, codec, or budget is invalid."""


@dataclass(frozen=True)
class PredictionResult:
    prediction: int
    operations: int
    state_bytes: int
    candidate_count: int


@dataclass(frozen=True)
class UpdateResult:
    state: dict[str, Any]
    operations: int
    state_bytes: int


@dataclass(frozen=True)
class EpistemicEvent:
    episode_start: bool
    feature: int
    outcome: int


@dataclass(frozen=True)
class FixedRuleResult:
    mask: int
    errors: int
    predictions: tuple[int, ...]
    operations: int


class _Operations:
    def __init__(self, limit: int) -> None:
        self.value = 0
        self.limit = limit

    def add(self, amount: int = 1) -> None:
        self.value += amount
        if self.value > self.limit:
            raise LearningError("OT-0075 operation budget exceeded")


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise LearningError(f"{label} keys differ from the frozen schema")
    return value


def _bit(value: object, label: str) -> int:
    if type(value) is not int or value not in {0, 1}:
        raise LearningError(f"{label} is not a bit")
    return value


def _parse_bits(value: object, label: str) -> int:
    if (
        type(value) is not str
        or len(value) != DIMENSION
        or any(character not in "01" for character in value)
    ):
        raise LearningError(f"{label} is not a {DIMENSION}-bit vector")
    return int(value, 2)


def _parity(mask: int, feature: int) -> int:
    return (mask & feature).bit_count() & 1


def _query(value: object) -> tuple[dict[str, Any], int]:
    query = _exact(
        value,
        {"episode_start", "feature_bits", "query_id", "schema_version"},
        "OT-0075 public query",
    )
    if (
        query["schema_version"] != SCHEMA_VERSION
        or type(query["episode_start"]) is not bool
        or type(query["query_id"]) is not str
        or _QUERY_ID.fullmatch(query["query_id"]) is None
    ):
        raise LearningError("OT-0075 public query identity differs")
    feature = _parse_bits(query["feature_bits"], "query feature")
    if feature == 0:
        raise LearningError("OT-0075 query feature may not be zero")
    return query, feature


def _projection_bytes(state: dict[str, Any]) -> bytes:
    payload = _canonical_json(state)
    if len(payload) > STATE_BYTE_LIMIT:
        raise LearningError("OT-0075 canonical projection exceeds 2048 bytes")
    return payload


def _eligible(mask: int) -> bool:
    return (
        type(mask) is int
        and 0 < mask < _MASK_LIMIT
        and MIN_MASK_WEIGHT <= mask.bit_count() <= MAX_MASK_WEIGHT
    )


def _validate_basis(value: object) -> list[list[int]]:
    if type(value) is not list or len(value) > DIMENSION:
        raise LearningError("OT-0075 affine basis cardinality differs")
    basis: list[list[int]] = []
    pivots: list[int] = []
    for item in value:
        if (
            type(item) is not list
            or len(item) != 2
            or type(item[0]) is not int
            or not 0 < item[0] < _MASK_LIMIT
        ):
            raise LearningError("OT-0075 affine basis row differs")
        outcome = _bit(item[1], "basis outcome")
        basis.append([item[0], outcome])
        pivots.append(item[0].bit_length() - 1)
    if pivots != sorted(pivots, reverse=True) or len(set(pivots)) != len(pivots):
        raise LearningError("OT-0075 affine pivots are not canonically ordered")
    for index, (row, _) in enumerate(basis):
        pivot_bit = 1 << pivots[index]
        if any(
            other_index != index and other_row & pivot_bit
            for other_index, (other_row, _) in enumerate(basis)
        ):
            raise LearningError("OT-0075 affine basis is not reduced")
        if row & pivot_bit == 0:
            raise LearningError("OT-0075 affine pivot is absent")
    return basis


def _add_equation(
    basis: list[list[int]],
    feature: int,
    outcome: int,
    operations: _Operations,
) -> list[list[int]]:
    rows = [[row, bit] for row, bit in basis]
    current_row = feature
    current_outcome = outcome
    for row, bit in rows:
        operations.add()  # pivot-presence comparison
        pivot = row.bit_length() - 1
        if current_row & (1 << pivot):
            current_row ^= row
            current_outcome ^= bit
            operations.add()  # GF(2) row xor
    operations.add()  # dependent/independent comparison
    if current_row == 0:
        if current_outcome:
            raise LearningError("OT-0075 affine evidence is inconsistent")
        return rows

    pivot = current_row.bit_length() - 1
    reduced: list[list[int]] = []
    for row, bit in rows:
        operations.add()  # new-pivot presence comparison
        if row & (1 << pivot):
            row ^= current_row
            bit ^= current_outcome
            operations.add()  # GF(2) row xor
        reduced.append([row, bit])
    reduced.append([current_row, current_outcome])
    reduced.sort(key=lambda item: item[0].bit_length(), reverse=True)
    return _validate_basis(reduced)


def _solved_mask(basis: list[list[int]]) -> int | None:
    if len(basis) != DIMENSION:
        return None
    mask = 0
    for row, outcome in basis:
        if row & (row - 1):
            raise LearningError("OT-0075 full-rank basis is not canonical")
        if outcome:
            mask |= row
    return mask


def _consistent(
    mask: int,
    basis: list[list[int]],
    operations: _Operations,
) -> bool:
    operations.add()  # candidate-mask test
    for row, outcome in basis:
        observed = _parity(mask, row)
        operations.add()  # parity evaluation
        operations.add()  # outcome comparison
        if observed != outcome:
            return False
    return True


def _predict_from_candidates(
    feature: int,
    cached_models: Iterable[int],
    basis: list[list[int]],
    fallback_masks: Sequence[int],
    operations: _Operations,
) -> tuple[int, int]:
    cached = [
        mask for mask in cached_models if _consistent(mask, basis, operations)
    ]
    candidates = cached
    if not candidates:
        candidates = [
            mask
            for mask in fallback_masks
            if _consistent(mask, basis, operations)
        ]
    if not candidates:
        raise LearningError("OT-0075 affine version space is empty")
    ones = 0
    for mask in candidates:
        ones += _parity(mask, feature)
        operations.add()  # parity evaluation
    operations.add()  # strict-majority comparison
    return (int(ones * 2 > len(candidates)), len(candidates))


def compact_initial_state() -> dict[str, Any]:
    return {"basis": [], "models": [], "schema_version": SCHEMA_VERSION}


def _compact_state(value: object) -> dict[str, Any]:
    state = _exact(
        value,
        {"basis", "models", "schema_version"},
        "OT-0075 compact state",
    )
    if state["schema_version"] != SCHEMA_VERSION or type(state["models"]) is not list:
        raise LearningError("OT-0075 compact state identity differs")
    models = state["models"]
    if len(models) > len({item for item in models if type(item) is int}) or any(
        not _eligible(item) for item in models
    ):
        raise LearningError("OT-0075 compact model bank differs")
    normalized = {
        "basis": _validate_basis(state["basis"]),
        "models": list(models),
        "schema_version": SCHEMA_VERSION,
    }
    _projection_bytes(normalized)
    return normalized


def compact_predict(state: object, query: object) -> PredictionResult:
    normalized = _compact_state(state)
    public_query, feature = _query(query)
    basis = [] if public_query["episode_start"] else normalized["basis"]
    operations = _Operations(PREDICTION_OPERATION_LIMIT)
    prediction, candidate_count = _predict_from_candidates(
        feature,
        normalized["models"],
        basis,
        _ELIGIBLE_MASKS,
        operations,
    )
    return PredictionResult(
        prediction,
        operations.value,
        len(_projection_bytes(normalized)),
        candidate_count,
    )


def compact_update(
    state: object,
    query: object,
    outcome: object,
) -> UpdateResult:
    normalized = _compact_state(state)
    public_query, feature = _query(query)
    released = _bit(outcome, "released outcome")
    basis = [] if public_query["episode_start"] else normalized["basis"]
    operations = _Operations(UPDATE_OPERATION_LIMIT)
    basis = _add_equation(basis, feature, released, operations)
    models = list(normalized["models"])
    solved = _solved_mask(basis)
    if solved is not None:
        if not _eligible(solved):
            raise LearningError("OT-0075 solved compact model is ineligible")
        operations.add()  # model-presence comparison
        if solved not in models:
            models.append(solved)
    updated = {"basis": basis, "models": models, "schema_version": SCHEMA_VERSION}
    payload = _projection_bytes(updated)
    return UpdateResult(updated, operations.value, len(payload))


def pack_epistemic_events(events: Sequence[EpistemicEvent]) -> str:
    if len(events) > HORIZON:
        raise LearningError("OT-0075 epistemic log exceeds the frozen horizon")
    accumulator = 0
    for event in events:
        if type(event) is not EpistemicEvent:
            raise LearningError("OT-0075 epistemic event type differs")
        if type(event.episode_start) is not bool or not 0 < event.feature < _MASK_LIMIT:
            raise LearningError("OT-0075 epistemic event query differs")
        outcome = _bit(event.outcome, "epistemic outcome")
        row = (int(event.episode_start) << 13) | (event.feature << 1) | outcome
        accumulator = (accumulator << 14) | row
    bit_count = 14 * len(events)
    byte_count = (bit_count + 7) // 8
    padding = byte_count * 8 - bit_count
    raw = (accumulator << padding).to_bytes(byte_count, "big")
    return base64.b64encode(raw).decode("ascii")


def unpack_epistemic_events(
    event_count: object,
    payload_base64: object,
) -> tuple[EpistemicEvent, ...]:
    if type(event_count) is not int or not 0 <= event_count <= HORIZON:
        raise LearningError("OT-0075 epistemic event count differs")
    if type(payload_base64) is not str:
        raise LearningError("OT-0075 epistemic payload is not base64 text")
    try:
        raw = base64.b64decode(payload_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise LearningError("OT-0075 epistemic payload is invalid base64") from error
    if base64.b64encode(raw).decode("ascii") != payload_base64:
        raise LearningError("OT-0075 epistemic payload is not canonical base64")
    bit_count = 14 * event_count
    expected_bytes = (bit_count + 7) // 8
    if len(raw) != expected_bytes:
        raise LearningError("OT-0075 epistemic payload length differs")
    padding = expected_bytes * 8 - bit_count
    if raw and padding and raw[-1] & ((1 << padding) - 1):
        raise LearningError("OT-0075 epistemic payload has nonzero padding")
    accumulator = int.from_bytes(raw, "big") >> padding if raw else 0
    events: list[EpistemicEvent] = []
    for index in range(event_count):
        shift = 14 * (event_count - index - 1)
        row = (accumulator >> shift) & ((1 << 14) - 1)
        events.append(
            EpistemicEvent(
                bool((row >> 13) & 1),
                (row >> 1) & (_MASK_LIMIT - 1),
                row & 1,
            )
        )
    if any(event.feature == 0 for event in events):
        raise LearningError("OT-0075 epistemic row has a zero feature")
    return tuple(events)


def log_initial_state() -> dict[str, Any]:
    return {"event_count": 0, "payload_base64": "", "schema_version": SCHEMA_VERSION}


def _log_state(value: object) -> tuple[dict[str, Any], tuple[EpistemicEvent, ...]]:
    state = _exact(
        value,
        {"event_count", "payload_base64", "schema_version"},
        "OT-0075 epistemic log state",
    )
    if state["schema_version"] != SCHEMA_VERSION:
        raise LearningError("OT-0075 epistemic log identity differs")
    events = unpack_epistemic_events(state["event_count"], state["payload_base64"])
    normalized = {
        "event_count": len(events),
        "payload_base64": pack_epistemic_events(events),
        "schema_version": SCHEMA_VERSION,
    }
    if normalized != state:
        raise LearningError("OT-0075 epistemic log is not canonical")
    _projection_bytes(normalized)
    return normalized, events


def _replay_models(
    events: Sequence[EpistemicEvent],
    operations: _Operations,
) -> tuple[list[int], list[list[int]]]:
    models: list[int] = []
    basis: list[list[int]] = []
    for event in events:
        operations.add()  # decoded-event visit
        if event.episode_start:
            basis = []
        basis = _add_equation(basis, event.feature, event.outcome, operations)
        solved = _solved_mask(basis)
        if solved is not None:
            operations.add()  # model-presence comparison
            if solved not in models:
                models.append(solved)
    return models, basis


def log_predict(state: object, query: object) -> PredictionResult:
    normalized, events = _log_state(state)
    public_query, feature = _query(query)
    operations = _Operations(PREDICTION_OPERATION_LIMIT)
    models, basis = _replay_models(events, operations)
    if public_query["episode_start"]:
        basis = []
    prediction, candidate_count = _predict_from_candidates(
        feature,
        models,
        basis,
        range(_MASK_LIMIT),
        operations,
    )
    return PredictionResult(
        prediction,
        operations.value,
        len(_projection_bytes(normalized)),
        candidate_count,
    )


def log_update(state: object, query: object, outcome: object) -> UpdateResult:
    _, events = _log_state(state)
    public_query, feature = _query(query)
    released = _bit(outcome, "released outcome")
    if len(events) >= HORIZON:
        raise LearningError("OT-0075 epistemic log exceeds the frozen horizon")
    operations = _Operations(UPDATE_OPERATION_LIMIT)
    operations.add(len(events))  # decoded-event visits needed to validate state
    operations.add()  # decoded append-row visit
    updated_events = (*events, EpistemicEvent(public_query["episode_start"], feature, released))
    updated = {
        "event_count": len(updated_events),
        "payload_base64": pack_epistemic_events(updated_events),
        "schema_version": SCHEMA_VERSION,
    }
    payload = _projection_bytes(updated)
    return UpdateResult(updated, operations.value, len(payload))


def no_persistence_initial_state() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION}


def _no_persistence_state(value: object) -> dict[str, Any]:
    state = _exact(value, {"schema_version"}, "OT-0075 no-persistence state")
    if state["schema_version"] != SCHEMA_VERSION:
        raise LearningError("OT-0075 no-persistence identity differs")
    return {"schema_version": SCHEMA_VERSION}


def no_persistence_predict(state: object, query: object) -> PredictionResult:
    normalized = _no_persistence_state(state)
    _query(query)
    payload = _projection_bytes(normalized)
    return PredictionResult(0, 0, len(payload), 1)


def no_persistence_update(state: object, query: object, outcome: object) -> UpdateResult:
    no_persistence_predict(state, query)
    _bit(outcome, "released outcome")
    updated = no_persistence_initial_state()
    return UpdateResult(updated, 0, len(_projection_bytes(updated)))


def immutable_seed_initial_state() -> dict[str, Any]:
    return {"mask": IMMUTABLE_SEED_MASK, "schema_version": SCHEMA_VERSION}


def _immutable_seed_state(value: object) -> dict[str, Any]:
    state = _exact(value, {"mask", "schema_version"}, "OT-0075 immutable state")
    if state != immutable_seed_initial_state():
        raise LearningError("OT-0075 immutable seed state changed")
    return immutable_seed_initial_state()


def immutable_seed_predict(state: object, query: object) -> PredictionResult:
    normalized = _immutable_seed_state(state)
    _, feature = _query(query)
    payload = _projection_bytes(normalized)
    return PredictionResult(_parity(IMMUTABLE_SEED_MASK, feature), 1, len(payload), 1)


def immutable_seed_update(state: object, query: object, outcome: object) -> UpdateResult:
    immutable_seed_predict(state, query)
    _bit(outcome, "released outcome")
    updated = immutable_seed_initial_state()
    return UpdateResult(updated, 0, len(_projection_bytes(updated)))


def clock_initial_state() -> dict[str, Any]:
    return {"encounter_count": 0, "schema_version": SCHEMA_VERSION}


def _clock_state(value: object) -> dict[str, Any]:
    state = _exact(value, {"encounter_count", "schema_version"}, "OT-0075 clock state")
    if (
        state["schema_version"] != SCHEMA_VERSION
        or type(state["encounter_count"]) is not int
        or not 0 <= state["encounter_count"] <= HORIZON
    ):
        raise LearningError("OT-0075 clock state differs")
    _projection_bytes(state)
    return state


def clock_predict(state: object, query: object) -> PredictionResult:
    normalized = _clock_state(state)
    _query(query)
    return PredictionResult(
        normalized["encounter_count"] % 2,
        1,
        len(_projection_bytes(normalized)),
        1,
    )


def clock_update(state: object, query: object, outcome: object) -> UpdateResult:
    normalized = _clock_state(state)
    _query(query)
    _bit(outcome, "released outcome")
    if normalized["encounter_count"] >= HORIZON:
        raise LearningError("OT-0075 clock exceeds the frozen horizon")
    updated = {
        "encounter_count": normalized["encounter_count"] + 1,
        "schema_version": SCHEMA_VERSION,
    }
    return UpdateResult(updated, 1, len(_projection_bytes(updated)))


def recent_initial_state() -> dict[str, Any]:
    return {"events": [], "schema_version": SCHEMA_VERSION}


def _recent_state(value: object) -> dict[str, Any]:
    state = _exact(value, {"events", "schema_version"}, "OT-0075 recent state")
    if state["schema_version"] != SCHEMA_VERSION or type(state["events"]) is not list:
        raise LearningError("OT-0075 recent state identity differs")
    events: list[dict[str, Any]] = []
    query_ids: set[str] = set()
    for item in state["events"]:
        event = _exact(item, {"outcome", "public_query"}, "OT-0075 recent event")
        query, _ = _query(event["public_query"])
        outcome = _bit(event["outcome"], "recent outcome")
        if query["query_id"] in query_ids:
            raise LearningError("OT-0075 recent state repeats a query")
        query_ids.add(query["query_id"])
        events.append({"outcome": outcome, "public_query": dict(query)})
    normalized = {"events": events, "schema_version": SCHEMA_VERSION}
    _projection_bytes(normalized)
    return normalized


def recent_predict(state: object, query: object) -> PredictionResult:
    normalized = _recent_state(state)
    public_query, feature = _query(query)
    operations = _Operations(PREDICTION_OPERATION_LIMIT)
    epistemic = []
    for item in normalized["events"]:
        _, retained_feature = _query(item["public_query"])
        epistemic.append(
            EpistemicEvent(
                item["public_query"]["episode_start"],
                retained_feature,
                item["outcome"],
            )
        )
    models, basis = _replay_models(epistemic, operations)
    if public_query["episode_start"]:
        basis = []
    prediction, candidate_count = _predict_from_candidates(
        feature,
        models,
        basis,
        _ELIGIBLE_MASKS,
        operations,
    )
    return PredictionResult(
        prediction,
        operations.value,
        len(_projection_bytes(normalized)),
        candidate_count,
    )


def recent_update(state: object, query: object, outcome: object) -> UpdateResult:
    normalized = _recent_state(state)
    public_query, _ = _query(query)
    released = _bit(outcome, "released outcome")
    if any(
        item["public_query"]["query_id"] == public_query["query_id"]
        for item in normalized["events"]
    ):
        raise LearningError("OT-0075 recent update repeats a query")
    events = [*normalized["events"], {"outcome": released, "public_query": dict(public_query)}]
    operations = _Operations(UPDATE_OPERATION_LIMIT)
    operations.add(len(normalized["events"]))  # decoded retained-event visits
    updated = {"events": events, "schema_version": SCHEMA_VERSION}
    while len(_canonical_json(updated)) > STATE_BYTE_LIMIT:
        operations.add()  # oldest-row eviction comparison
        if not events:
            raise LearningError("OT-0075 recent row cannot fit the frozen budget")
        events.pop(0)
        updated = {"events": events, "schema_version": SCHEMA_VERSION}
    payload = _projection_bytes(updated)
    return UpdateResult(updated, operations.value, len(payload))


def nearest_predict(state: object, query: object) -> PredictionResult:
    normalized, events = _log_state(state)
    _, feature = _query(query)
    operations = _Operations(PREDICTION_OPERATION_LIMIT)
    if not events:
        return PredictionResult(0, 0, len(_projection_bytes(normalized)), 0)
    best: tuple[int, int, int, int] | None = None
    for index, event in enumerate(events):
        operations.add()  # decoded-event visit
        key = ((event.feature ^ feature).bit_count(), -index, event.feature, event.outcome)
        operations.add()  # nearest/tie comparison
        if best is None or key[:3] < best[:3]:
            best = key
    if best is None:
        raise LearningError("OT-0075 nearest retrieval produced no event")
    return PredictionResult(best[3], operations.value, len(_projection_bytes(normalized)), 1)


def nearest_update(state: object, query: object, outcome: object) -> UpdateResult:
    return log_update(state, query, outcome)


def _flatten_public_events(value: object) -> list[tuple[int, int]]:
    if type(value) is not list:
        raise LearningError("OT-0075 fixed-rule events are not a list")
    events: list[tuple[int, int]] = []
    for expected_index, item in enumerate(value):
        if type(item) is not dict:
            raise LearningError("OT-0075 fixed-rule event is not an object")
        if set(item) == {"outcome", "public_query"}:
            event = item
        elif set(item) == {"encounter_index", "outcome", "public_query"}:
            event = item
            if event["encounter_index"] != expected_index:
                raise LearningError("OT-0075 fixed-rule event order differs")
        else:
            raise LearningError("OT-0075 fixed-rule event keys differ")
        _, feature = _query(event["public_query"])
        events.append((feature, _bit(event["outcome"], "fixed-rule outcome")))
    if len(events) != HORIZON:
        raise LearningError("OT-0075 fixed-rule stream horizon differs")
    return events


def offline_best_fixed_rule(events: object) -> FixedRuleResult:
    public_events = _flatten_public_events(events)
    best_mask = -1
    best_errors = HORIZON + 1
    best_predictions: tuple[int, ...] = ()
    operations = 0
    for mask in _ELIGIBLE_MASKS:
        predictions = tuple(_parity(mask, feature) for feature, _ in public_events)
        operations += len(public_events)  # parity evaluations
        errors = sum(
            prediction != outcome
            for prediction, (_, outcome) in zip(predictions, public_events, strict=True)
        )
        operations += len(public_events) + 1  # outcome and incumbent comparisons
        if (errors, mask) < (best_errors, best_mask if best_mask >= 0 else _MASK_LIMIT):
            best_mask = mask
            best_errors = errors
            best_predictions = predictions
    if best_mask < 0:
        raise LearningError("OT-0075 fixed-rule search produced no mask")
    return FixedRuleResult(best_mask, best_errors, best_predictions, operations)


def initial_state(mechanism: str) -> dict[str, Any]:
    factories = {
        COMPACT_REFERENCE: compact_initial_state,
        LOG_REFERENCE: log_initial_state,
        NO_PERSISTENCE_CONTROL: no_persistence_initial_state,
        IMMUTABLE_SEED_CONTROL: immutable_seed_initial_state,
        CLOCK_CONTROL: clock_initial_state,
        RECENT_COMPARATOR: recent_initial_state,
        NEAREST_COMPARATOR: log_initial_state,
    }
    if type(mechanism) is not str or mechanism not in factories:
        raise LearningError("OT-0075 online mechanism is unavailable")
    return factories[mechanism]()


def _coerce_state(mechanism: str, state: object) -> object:
    return decode_state(mechanism, state) if type(state) is bytes else state


def predict(
    mechanism: str,
    projection_bytes_or_state: object,
    query: object,
) -> PredictionResult:
    predictors = {
        COMPACT_REFERENCE: compact_predict,
        LOG_REFERENCE: log_predict,
        NO_PERSISTENCE_CONTROL: no_persistence_predict,
        IMMUTABLE_SEED_CONTROL: immutable_seed_predict,
        CLOCK_CONTROL: clock_predict,
        RECENT_COMPARATOR: recent_predict,
        NEAREST_COMPARATOR: nearest_predict,
    }
    if type(mechanism) is not str or mechanism not in predictors:
        raise LearningError("OT-0075 online mechanism is unavailable")
    state = _coerce_state(mechanism, projection_bytes_or_state)
    return predictors[mechanism](state, query)


def update(
    mechanism: str,
    projection_bytes_or_state: object,
    query: object,
    prediction: object,
    released_outcome: object,
) -> UpdateResult:
    updaters = {
        COMPACT_REFERENCE: compact_update,
        LOG_REFERENCE: log_update,
        NO_PERSISTENCE_CONTROL: no_persistence_update,
        IMMUTABLE_SEED_CONTROL: immutable_seed_update,
        CLOCK_CONTROL: clock_update,
        RECENT_COMPARATOR: recent_update,
        NEAREST_COMPARATOR: nearest_update,
    }
    if type(mechanism) is not str or mechanism not in updaters:
        raise LearningError("OT-0075 online mechanism is unavailable")
    state = _coerce_state(mechanism, projection_bytes_or_state)
    sealed_prediction = _bit(prediction, "sealed prediction")
    if predict(mechanism, state, query).prediction != sealed_prediction:
        raise LearningError("OT-0075 sealed prediction differs from the mechanism")
    return updaters[mechanism](state, query, released_outcome)


def encode_state(mechanism: str, state: object) -> bytes:
    validators = {
        COMPACT_REFERENCE: lambda value: _compact_state(value),
        LOG_REFERENCE: lambda value: _log_state(value)[0],
        NO_PERSISTENCE_CONTROL: _no_persistence_state,
        IMMUTABLE_SEED_CONTROL: _immutable_seed_state,
        CLOCK_CONTROL: lambda value: _clock_state(value),
        RECENT_COMPARATOR: lambda value: _recent_state(value),
        NEAREST_COMPARATOR: lambda value: _log_state(value)[0],
    }
    if type(mechanism) is not str or mechanism not in validators:
        raise LearningError("OT-0075 online mechanism is unavailable")
    normalized = validators[mechanism](state)
    return _projection_bytes(normalized)


def decode_state(mechanism: str, payload: object) -> dict[str, Any]:
    if type(payload) is not bytes or len(payload) > STATE_BYTE_LIMIT:
        raise LearningError("OT-0075 encoded projection differs")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LearningError("OT-0075 encoded projection is not JSON") from error
    encoded = encode_state(mechanism, value)
    if encoded != payload:
        raise LearningError("OT-0075 encoded projection is not canonical")
    return value


__all__ = [
    "CLOCK_CONTROL",
    "COMPACT_REFERENCE",
    "EpistemicEvent",
    "FixedRuleResult",
    "IMMUTABLE_SEED_CONTROL",
    "IMMUTABLE_SEED_MASK",
    "LOG_REFERENCE",
    "LearningError",
    "NEAREST_COMPARATOR",
    "NO_PERSISTENCE_CONTROL",
    "ONLINE_MECHANISMS",
    "PREDICTION_OPERATION_LIMIT",
    "PredictionResult",
    "RECENT_COMPARATOR",
    "STATE_BYTE_LIMIT",
    "UPDATE_OPERATION_LIMIT",
    "UpdateResult",
    "clock_initial_state",
    "clock_predict",
    "clock_update",
    "compact_initial_state",
    "compact_predict",
    "compact_update",
    "decode_state",
    "encode_state",
    "immutable_seed_initial_state",
    "immutable_seed_predict",
    "immutable_seed_update",
    "initial_state",
    "log_initial_state",
    "log_predict",
    "log_update",
    "nearest_predict",
    "nearest_update",
    "no_persistence_initial_state",
    "no_persistence_predict",
    "no_persistence_update",
    "offline_best_fixed_rule",
    "pack_epistemic_events",
    "predict",
    "recent_initial_state",
    "recent_predict",
    "recent_update",
    "unpack_epistemic_events",
    "update",
]
