"""P-frozen task derivation for the OT-0075 E14 evaluator checkpoint.

This module contains no evaluator, reference learner, control, scorer, evidence
writer, or execution entrypoint.  Its only authority is deterministic expansion
of one 256-bit seed into hidden semi-Markov parity streams and validation of the
resulting private task.  It is frozen before those other components exist.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from pathlib import Path
from typing import Any, Final

from .ot0002 import canonical_json, sha256_bytes


EXPERIMENT_ID: Final = "OT-0075"
ACCEPTANCE_PATH: Final = Path("spec/ot-0075-acceptance.json")
EXPERIMENT_PATH: Final = Path(
    "experiments/OT-0075-e14-longitudinal-evaluator-calibration.md"
)

SCHEMA_VERSION: Final = 1
DIMENSION: Final = 12
SEED_BYTES: Final = 32
ANCHOR_CASE_COUNT: Final = 8
DESIGN_CASE_COUNT: Final = 16
EPISODE_SCHEDULE: Final = (0, 1, 0, 2, 1, 0)
DWELL_LENGTHS: Final = (32, 35, 39, 43, 45, 48)
HORIZON: Final = sum(DWELL_LENGTHS)
MIN_MASK_WEIGHT: Final = 4
MAX_MASK_WEIGHT: Final = 8
RECURRENCE_DISAMBIGUATION_PREFIX: Final = 2

DESIGN_DOMAIN: Final = "open-trajectory/ot-0075/design/v1"
ANCHOR_DOMAIN: Final = "open-trajectory/ot-0075/private-anchor/v1"
FUTURE_CANDIDATE_DOMAIN: Final = "open-trajectory/e14/future-candidate/v1"

_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ProtocolError(ValueError):
    pass


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ProtocolError(f"{label} keys differ from the frozen schema")
    return value


def _seed(value: object) -> bytes:
    if type(value) is not bytes or len(value) != SEED_BYTES:
        raise ProtocolError("OT-0075 derivation seed must be exactly 256 bits")
    return value


def _commit(value: object) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        raise ProtocolError("OT-0075 implementation identity is malformed")
    return value


def _purpose(value: object) -> str:
    if value not in {"design", "anchor"}:
        raise ProtocolError("OT-0075 derivation purpose is unavailable")
    return str(value)


def _domain(purpose: str) -> str:
    return DESIGN_DOMAIN if purpose == "design" else ANCHOR_DOMAIN


def _expand(seed: bytes, purpose: str, *parts: object) -> bytes:
    message = canonical_json(
        {
            "domain": _domain(purpose),
            "parts": list(parts),
            "schema_version": SCHEMA_VERSION,
        }
    )
    return hmac.new(seed, message, hashlib.sha256).digest()


def _implementation_bound_seed(
    seed: bytes,
    purpose: str,
    implementation_commit: str,
) -> bytes:
    """Bind every hidden world choice to the clean implementation identity."""

    message = canonical_json(
        {
            "domain": _domain(purpose),
            "implementation_git_commit": implementation_commit,
            "kind": "implementation-bound-seed",
            "schema_version": SCHEMA_VERSION,
        }
    )
    return hmac.new(seed, message, hashlib.sha256).digest()


def _ranked(
    seed: bytes,
    purpose: str,
    label: str,
    case_index: int,
    episode_index: int,
    values: list[int],
) -> list[int]:
    return sorted(
        values,
        key=lambda value: (
            _expand(
                seed,
                purpose,
                label,
                case_index,
                episode_index,
                value,
            ),
            value,
        ),
    )


def _rank(vectors: list[int]) -> int:
    basis: dict[int, int] = {}
    for value in vectors:
        current = value
        while current:
            pivot = current.bit_length() - 1
            if pivot in basis:
                current ^= basis[pivot]
            else:
                basis[pivot] = current
                break
    return len(basis)


def _bits(value: int) -> str:
    if type(value) is not int or not 0 <= value < (1 << DIMENSION):
        raise ProtocolError("OT-0075 bit vector is out of range")
    return format(value, f"0{DIMENSION}b")


def parse_bits(value: object, label: str) -> int:
    if (
        type(value) is not str
        or len(value) != DIMENSION
        or any(character not in "01" for character in value)
    ):
        raise ProtocolError(f"{label} is not a {DIMENSION}-bit vector")
    return int(value, 2)


def parity(mask: int, feature: int) -> int:
    return (mask & feature).bit_count() & 1


def _eligible_masks(seed: bytes, purpose: str, case_index: int) -> list[int]:
    eligible = [
        mask
        for mask in range(1, 1 << DIMENSION)
        if MIN_MASK_WEIGHT <= mask.bit_count() <= MAX_MASK_WEIGHT
    ]
    ordered = _ranked(seed, purpose, "mask", case_index, -1, eligible)
    selected = ordered[:3]
    if len(selected) != 3 or len(set(selected)) != 3:
        raise ProtocolError("OT-0075 cannot derive three distinct hidden rules")
    return selected


def _dwell_order(seed: bytes, purpose: str, case_index: int) -> list[int]:
    indices = _ranked(
        seed,
        purpose,
        "dwell-order",
        case_index,
        -1,
        list(range(len(DWELL_LENGTHS))),
    )
    return [DWELL_LENGTHS[index] for index in indices]


def _episode_features(
    seed: bytes,
    purpose: str,
    case_index: int,
    episode_index: int,
    dwell: int,
    used: set[int],
    masks: list[int],
) -> list[int]:
    ordered = _ranked(
        seed,
        purpose,
        "feature",
        case_index,
        episode_index,
        list(range(1, 1 << DIMENSION)),
    )
    basis: list[int] = []
    signature_count = 1
    for feature in ordered:
        if feature in used or _rank([*basis, feature]) == len(basis):
            continue
        candidate = [*basis, feature]
        signatures = {
            tuple(parity(mask, item) for item in candidate)
            for mask in masks
        }
        if len(signatures) > signature_count:
            basis.append(feature)
            signature_count = len(signatures)
            if signature_count == len(masks):
                break
    if (
        len(basis) > RECURRENCE_DISAMBIGUATION_PREFIX
        or signature_count != len(masks)
    ):
        raise ProtocolError("OT-0075 cannot derive the recurrence prefix")
    for feature in ordered:
        if feature in used:
            continue
        if _rank([*basis, feature]) > len(basis):
            basis.append(feature)
            if len(basis) == DIMENSION:
                break
    if len(basis) != DIMENSION:
        raise ProtocolError("OT-0075 cannot derive an unused full-rank prefix")
    tail = [
        feature
        for feature in ordered
        if feature not in used and feature not in basis
    ][: dwell - DIMENSION]
    result = [*basis, *tail]
    if len(result) != dwell or len(set(result)) != dwell:
        raise ProtocolError("OT-0075 episode feature derivation collided")
    used.update(result)
    return result


def derive_task(
    seed: bytes,
    implementation_commit: str,
    *,
    purpose: str,
) -> dict[str, Any]:
    """Derive one complete task without rejection sampling or reseeding."""

    seed = _seed(seed)
    implementation_commit = _commit(implementation_commit)
    purpose = _purpose(purpose)
    case_count = (
        DESIGN_CASE_COUNT if purpose == "design" else ANCHOR_CASE_COUNT
    )

    derivation_seed = _implementation_bound_seed(
        seed,
        purpose,
        implementation_commit,
    )

    cases = []
    for case_index in range(case_count):
        masks = _eligible_masks(derivation_seed, purpose, case_index)
        dwell_order = _dwell_order(derivation_seed, purpose, case_index)
        used: set[int] = set()
        episodes = []
        encounter_index = 0
        for episode_index, semantic_rule in enumerate(EPISODE_SCHEDULE):
            dwell = dwell_order[episode_index]
            features = _episode_features(
                derivation_seed,
                purpose,
                case_index,
                episode_index,
                dwell,
                used,
                masks,
            )
            events = []
            for local_index, feature in enumerate(features):
                query_id = _expand(
                    derivation_seed,
                    purpose,
                    "query-id",
                    case_index,
                    episode_index,
                    local_index,
                ).hex()
                public_query = {
                    "episode_start": local_index == 0,
                    "feature_bits": _bits(feature),
                    "query_id": query_id,
                    "schema_version": SCHEMA_VERSION,
                }
                events.append(
                    {
                        "encounter_index": encounter_index,
                        "outcome": parity(masks[semantic_rule], feature),
                        "public_query": public_query,
                    }
                )
                encounter_index += 1
            episodes.append(
                {
                    "dwell": dwell,
                    "episode_index": episode_index,
                    "events": events,
                    "semantic_rule": semantic_rule,
                }
            )
        case_id = _expand(
            derivation_seed,
            purpose,
            "case-id",
            case_index,
        ).hex()
        cases.append(
            {
                "case_id": case_id,
                "case_index": case_index,
                "episodes": episodes,
                "hidden_masks": [_bits(mask) for mask in masks],
                "horizon": encounter_index,
            }
        )

    task = {
        "case_count": case_count,
        "cases": cases,
        "domain": _domain(purpose),
        "experiment_id": EXPERIMENT_ID,
        "implementation_git_commit": implementation_commit,
        "purpose": purpose,
        "schema_version": SCHEMA_VERSION,
        "seed_sha256": hashlib.sha256(seed).hexdigest(),
    }
    validate_task(task)
    return task


def design_seed(index: int) -> bytes:
    if type(index) is not int or not 0 <= index < 4:
        raise ProtocolError("OT-0075 design seed index is unavailable")
    return hashlib.sha256(
        canonical_json(
            {
                "domain": DESIGN_DOMAIN,
                "index": index,
                "kind": "public-design-seed",
            }
        )
    ).digest()


def build_design_task(index: int) -> dict[str, Any]:
    return derive_task(
        design_seed(index),
        "0" * 40,
        purpose="design",
    )


def validate_task(task: object) -> dict[str, Any]:
    value = _exact(
        task,
        {
            "case_count",
            "cases",
            "domain",
            "experiment_id",
            "implementation_git_commit",
            "purpose",
            "schema_version",
            "seed_sha256",
        },
        "OT-0075 task",
    )
    purpose = _purpose(value["purpose"])
    expected_case_count = (
        DESIGN_CASE_COUNT if purpose == "design" else ANCHOR_CASE_COUNT
    )
    if (
        value["schema_version"] != SCHEMA_VERSION
        or value["experiment_id"] != EXPERIMENT_ID
        or value["domain"] != _domain(purpose)
        or type(value["implementation_git_commit"]) is not str
        or _COMMIT.fullmatch(value["implementation_git_commit"]) is None
        or type(value["seed_sha256"]) is not str
        or _SHA256.fullmatch(value["seed_sha256"]) is None
        or type(value["case_count"]) is not int
        or value["case_count"] != expected_case_count
        or type(value["cases"]) is not list
        or len(value["cases"]) != value["case_count"]
    ):
        raise ProtocolError("OT-0075 task identity differs")

    case_ids: set[str] = set()
    query_ids: set[str] = set()
    for expected_case_index, raw_case in enumerate(value["cases"]):
        case = _exact(
            raw_case,
            {
                "case_id",
                "case_index",
                "episodes",
                "hidden_masks",
                "horizon",
            },
            "OT-0075 case",
        )
        if (
            case["case_index"] != expected_case_index
            or type(case["case_id"]) is not str
            or _SHA256.fullmatch(case["case_id"]) is None
            or case["case_id"] in case_ids
            or type(case["hidden_masks"]) is not list
            or len(case["hidden_masks"]) != 3
            or type(case["episodes"]) is not list
            or len(case["episodes"]) != len(EPISODE_SCHEDULE)
            or case["horizon"] != HORIZON
        ):
            raise ProtocolError("OT-0075 case identity differs")
        case_ids.add(case["case_id"])
        masks = [parse_bits(mask, "hidden mask") for mask in case["hidden_masks"]]
        if len(set(masks)) != 3 or any(
            not MIN_MASK_WEIGHT <= mask.bit_count() <= MAX_MASK_WEIGHT
            for mask in masks
        ):
            raise ProtocolError("OT-0075 hidden rule family differs")

        used: set[int] = set()
        observed_dwells: list[int] = []
        encounter_index = 0
        for expected_episode_index, raw_episode in enumerate(case["episodes"]):
            episode = _exact(
                raw_episode,
                {"dwell", "episode_index", "events", "semantic_rule"},
                "OT-0075 episode",
            )
            expected_rule = EPISODE_SCHEDULE[expected_episode_index]
            if (
                episode["episode_index"] != expected_episode_index
                or episode["semantic_rule"] != expected_rule
                or episode["dwell"] not in DWELL_LENGTHS
                or type(episode["events"]) is not list
                or len(episode["events"]) != episode["dwell"]
            ):
                raise ProtocolError("OT-0075 episode identity differs")
            observed_dwells.append(episode["dwell"])
            episode_features = []
            for local_index, raw_event in enumerate(episode["events"]):
                event = _exact(
                    raw_event,
                    {"encounter_index", "outcome", "public_query"},
                    "OT-0075 event",
                )
                query = _exact(
                    event["public_query"],
                    {"episode_start", "feature_bits", "query_id", "schema_version"},
                    "OT-0075 public query",
                )
                feature = parse_bits(query["feature_bits"], "query feature")
                if (
                    event["encounter_index"] != encounter_index
                    or query["schema_version"] != SCHEMA_VERSION
                    or query["episode_start"] is not (local_index == 0)
                    or type(query["query_id"]) is not str
                    or _SHA256.fullmatch(query["query_id"]) is None
                    or query["query_id"] in query_ids
                    or feature == 0
                    or feature in used
                    or event["outcome"] not in {0, 1}
                    or event["outcome"] != parity(masks[expected_rule], feature)
                ):
                    raise ProtocolError("OT-0075 event binding differs")
                query_ids.add(query["query_id"])
                used.add(feature)
                episode_features.append(feature)
                encounter_index += 1
            if _rank(episode_features[:DIMENSION]) != DIMENSION:
                raise ProtocolError("OT-0075 episode prefix is not full rank")
            recurrence_signatures = {
                tuple(
                    parity(mask, feature)
                    for feature in episode_features[
                        :RECURRENCE_DISAMBIGUATION_PREFIX
                    ]
                )
                for mask in masks
            }
            if len(recurrence_signatures) != len(masks):
                raise ProtocolError(
                    "OT-0075 recurrence prefix does not distinguish the rules"
                )
        if (
            sorted(observed_dwells) != list(DWELL_LENGTHS)
            or encounter_index != HORIZON
        ):
            raise ProtocolError("OT-0075 dwell schedule differs")
    return value


def task_sha256(task: dict[str, Any]) -> str:
    validate_task(task)
    return sha256_bytes(canonical_json(task))
