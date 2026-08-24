from __future__ import annotations

import json
import random
import secrets
from dataclasses import dataclass
from typing import Any

from .ot0002 import canonical_json, sha256_bytes


EXPERIMENT_ID = "OT-0004"
FEATURE_VECTORS = tuple(
    (a, b, c, d)
    for a in (0, 1)
    for b in (0, 1)
    for c in (0, 1)
    for d in (0, 1)
)
STAGE_KINDS = (
    "stable",
    "exceptions",
    "drift",
    "drift-confirmation",
    "noisy-contact",
    "capacity-canary",
)


def parity(features: tuple[int, int, int, int], mask: tuple[int, int, int, int], bias: int) -> int:
    return (sum(value * active for value, active in zip(features, mask)) + bias) % 2


def rule_label(
    features: tuple[int, int, int, int],
    *,
    mask: tuple[int, int, int, int],
    bias: int,
    exceptions: set[tuple[int, int, int, int]] | None = None,
) -> int:
    value = parity(features, mask, bias)
    return 1 - value if exceptions and features in exceptions else value


def choose_distinct_masks(rng: random.Random) -> list[tuple[int, int, int, int]]:
    masks = [vector for vector in FEATURE_VECTORS if any(vector)]
    rng.shuffle(masks)
    return masks[:3]


def shuffled_queries(rng: random.Random, required: list[tuple[int, int, int, int]]) -> list[list[int]]:
    remaining = [vector for vector in FEATURE_VECTORS if vector not in required]
    rng.shuffle(remaining)
    values = (required + remaining)[:8]
    rng.shuffle(values)
    return [list(vector) for vector in values]


def generate_task_manifest() -> dict[str, Any]:
    salt = secrets.token_hex(16)
    rng = random.Random(int(salt, 16))
    masks = choose_distinct_masks(rng)
    biases = [rng.randrange(2) for _ in range(3)]
    exceptions = set(rng.sample(list(FEATURE_VECTORS), 2))
    stages: list[dict[str, Any]] = []
    sequence = 0
    for stage_index, kind in enumerate(STAGE_KINDS):
        if kind in {"stable", "exceptions"}:
            mask_index = 0
        elif kind in {"drift", "drift-confirmation", "noisy-contact"}:
            mask_index = 1
        else:
            mask_index = 2
        active_exceptions = exceptions if kind == "exceptions" else set()
        feature_sequence = list(FEATURE_VECTORS)
        feature_sequence.extend(rng.choices(list(FEATURE_VECTORS), k=8))
        rng.shuffle(feature_sequence)
        noisy_positions = set(rng.sample(range(24), 9)) if kind == "noisy-contact" else set()
        events: list[dict[str, Any]] = []
        for local_index, features in enumerate(feature_sequence):
            clean = rule_label(
                features,
                mask=masks[mask_index],
                bias=biases[mask_index],
                exceptions=active_exceptions,
            )
            observed = 1 - clean if local_index in noisy_positions else clean
            events.append(
                {
                    "event_id": f"event-{secrets.token_hex(6)}",
                    "sequence": sequence,
                    "features": list(features),
                    "label": observed,
                }
            )
            sequence += 1
        required = list(exceptions) if kind == "exceptions" else []
        contact_queries = shuffled_queries(rng, required)
        heldout_queries = shuffled_queries(rng, required)

        def outcomes(queries: list[list[int]]) -> list[int]:
            return [
                rule_label(
                    tuple(query),
                    mask=masks[mask_index],
                    bias=biases[mask_index],
                    exceptions=active_exceptions,
                )
                for query in queries
            ]

        stages.append(
            {
                "stage": stage_index,
                "kind": kind,
                "events": events,
                "contact": {
                    "queries": contact_queries,
                    "outcomes": outcomes(contact_queries),
                },
                "heldout": {
                    "queries": heldout_queries,
                    "outcomes": outcomes(heldout_queries),
                },
            }
        )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "salt": salt,
        "rules": {
            "masks": [list(mask) for mask in masks],
            "biases": biases,
            "exceptions": [list(value) for value in sorted(exceptions)],
        },
        "stages": stages,
    }


def validate_binary_vector(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(type(item) is int and item in (0, 1) for item in value)
    )


def validate_task_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1 or manifest.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("invalid OT-0004 task-manifest identity")
    rules = manifest.get("rules")
    if not isinstance(rules, dict):
        raise ValueError("task manifest omits private rules")
    masks = rules.get("masks")
    biases = rules.get("biases")
    exceptions_raw = rules.get("exceptions")
    if (
        not isinstance(masks, list)
        or len(masks) != 3
        or not all(validate_binary_vector(mask) and any(mask) for mask in masks)
        or len({tuple(mask) for mask in masks}) != 3
        or not isinstance(biases, list)
        or len(biases) != 3
        or not all(type(value) is int and value in (0, 1) for value in biases)
        or not isinstance(exceptions_raw, list)
        or len(exceptions_raw) != 2
        or not all(validate_binary_vector(value) for value in exceptions_raw)
    ):
        raise ValueError("task manifest has invalid private rules")
    stages = manifest.get("stages")
    if not isinstance(stages, list) or len(stages) != len(STAGE_KINDS):
        raise ValueError("task manifest must contain six stages")
    seen_ids: set[str] = set()
    expected_sequence = 0
    exceptions = {tuple(value) for value in exceptions_raw}
    for stage_index, (stage, kind) in enumerate(zip(stages, STAGE_KINDS)):
        if stage.get("stage") != stage_index or stage.get("kind") != kind:
            raise ValueError("task stage identity or order changed")
        events = stage.get("events")
        if not isinstance(events, list) or len(events) != 24:
            raise ValueError("each task stage requires 24 events")
        mask_index = 0 if stage_index < 2 else (1 if stage_index < 5 else 2)
        stage_exceptions = exceptions if kind == "exceptions" else set()
        noisy_count = 0
        for event in events:
            event_id = event.get("event_id")
            if not isinstance(event_id, str) or event_id in seen_ids:
                raise ValueError("event identities must be unique")
            seen_ids.add(event_id)
            if event.get("sequence") != expected_sequence or not validate_binary_vector(
                event.get("features")
            ):
                raise ValueError("event sequence or features are invalid")
            expected_sequence += 1
            clean = rule_label(
                tuple(event["features"]),
                mask=tuple(masks[mask_index]),
                bias=biases[mask_index],
                exceptions=stage_exceptions,
            )
            if event.get("label") not in (0, 1):
                raise ValueError("event label is not binary")
            noisy_count += event["label"] != clean
        if (kind == "noisy-contact" and noisy_count != 9) or (
            kind != "noisy-contact" and noisy_count != 0
        ):
            raise ValueError("stage noise schedule changed")
        for split_name in ("contact", "heldout"):
            split = stage.get(split_name)
            if not isinstance(split, dict):
                raise ValueError("task stage split is absent")
            queries = split.get("queries")
            outcomes = split.get("outcomes")
            if (
                not isinstance(queries, list)
                or len(queries) != 8
                or not all(validate_binary_vector(query) for query in queries)
                or not isinstance(outcomes, list)
                or len(outcomes) != 8
            ):
                raise ValueError("task split shape is invalid")
            expected = [
                rule_label(
                    tuple(query),
                    mask=tuple(masks[mask_index]),
                    bias=biases[mask_index],
                    exceptions=stage_exceptions,
                )
                for query in queries
            ]
            if outcomes != expected:
                raise ValueError("task split outcomes differ from private world truth")


def archive_through_stage(manifest: dict[str, Any], stage_index: int) -> list[dict[str, Any]]:
    return [
        dict(event)
        for stage in manifest["stages"][: stage_index + 1]
        for event in stage["events"]
    ]


def hamming(left: list[int], right: list[int]) -> int:
    return sum(a != b for a, b in zip(left, right))


def fixed_selection(
    condition: str,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    limit: int,
) -> list[str]:
    if condition == "no-persistence":
        return []
    if limit <= 0 or len(archive) < limit:
        raise ValueError("fixed selector budget exceeds available archive")
    if condition == "fixed-most-recent":
        selected = sorted(archive, key=lambda item: item["sequence"], reverse=True)[:limit]
    elif condition == "fixed-first-seen-verbatim":
        selected = sorted(archive, key=lambda item: item["sequence"])[:limit]
    elif condition == "fixed-naive-nearest":
        selected = sorted(
            archive,
            key=lambda item: (
                min(hamming(item["features"], query) for query in queries),
                -item["sequence"],
            ),
        )[:limit]
    else:
        raise ValueError(f"unknown fixed selector: {condition}")
    return [item["event_id"] for item in selected]


def selected_events(archive: list[dict[str, Any]], event_ids: list[str]) -> list[dict[str, Any]]:
    by_id = {event["event_id"]: event for event in archive}
    if len(event_ids) != len(set(event_ids)) or any(event_id not in by_id for event_id in event_ids):
        raise ValueError("selection contains duplicate or unknown event identities")
    return [by_id[event_id] for event_id in event_ids]


def score_predictions(predictions: Any, outcomes: list[int]) -> tuple[int, str | None]:
    if (
        not isinstance(predictions, list)
        or len(predictions) != len(outcomes)
        or not all(type(value) is int and value in (0, 1) for value in predictions)
    ):
        return len(outcomes), "prediction vector failed exact binary shape validation"
    return sum(prediction != outcome for prediction, outcome in zip(predictions, outcomes)), None


def protected_consequence_receipt(
    *,
    stage_index: int,
    policy_sha256: str,
    archive: list[dict[str, Any]],
    selected_ids: list[str],
    queries: list[list[int]],
    predictions: list[int],
    outcomes: list[int],
    rejected_sample_size: int = 6,
) -> dict[str, Any]:
    selected = set(selected_ids)
    rejected = [event for event in archive if event["event_id"] not in selected]
    rejected.sort(key=lambda item: sha256_bytes(item["event_id"].encode()))
    errors, parse_error = score_predictions(predictions, outcomes)
    return {
        "stage": stage_index,
        "policy_sha256": policy_sha256,
        "selected_event_ids": selected_ids,
        "selected_events": selected_events(archive, selected_ids),
        "rejected_event_sample": rejected[:rejected_sample_size],
        "queries": queries,
        "predictions": predictions,
        "outcomes": outcomes,
        "errors": errors,
        "parse_error": parse_error,
    }


@dataclass(frozen=True)
class PolicySnapshot:
    revision: int
    policy: str
    parent_sha256: str | None
    proposal_sha256: str | None
    sha256: str

    def public_identity(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "parent_sha256": self.parent_sha256,
            "proposal_sha256": self.proposal_sha256,
            "sha256": self.sha256,
        }


class PolicyLedger:
    def __init__(self, seed_policy: str, byte_limit: int):
        self.byte_limit = byte_limit
        self._snapshots: list[PolicySnapshot] = []
        self._append(seed_policy, proposal=None)

    @property
    def current(self) -> PolicySnapshot:
        return self._snapshots[-1]

    @property
    def snapshots(self) -> tuple[PolicySnapshot, ...]:
        return tuple(self._snapshots)

    def _append(self, policy: str, proposal: dict[str, Any] | None) -> PolicySnapshot:
        if not isinstance(policy, str) or not policy.strip():
            raise ValueError("policy must be non-empty text")
        if len(policy.encode()) > self.byte_limit:
            raise ValueError("policy exceeds its frozen byte budget")
        parent = self._snapshots[-1].sha256 if self._snapshots else None
        proposal_sha = sha256_bytes(canonical_json(proposal)) if proposal is not None else None
        identity = {
            "revision": len(self._snapshots),
            "policy": policy,
            "parent_sha256": parent,
            "proposal_sha256": proposal_sha,
        }
        snapshot = PolicySnapshot(
            revision=identity["revision"],
            policy=policy,
            parent_sha256=parent,
            proposal_sha256=proposal_sha,
            sha256=sha256_bytes(canonical_json(identity)),
        )
        self._snapshots.append(snapshot)
        return snapshot

    def commit(self, proposal: dict[str, Any]) -> PolicySnapshot:
        if set(proposal) != {"policy", "expected_effect", "cheapest_falsifier"}:
            raise ValueError("selector proposal failed exact schema authority check")
        for name in ("policy", "expected_effect", "cheapest_falsifier"):
            if not isinstance(proposal[name], str) or not proposal[name].strip():
                raise ValueError(f"selector proposal has invalid {name}")
        return self._append(proposal["policy"], proposal=proposal)


def render_events(events: list[dict[str, Any]]) -> str:
    return json.dumps(events, sort_keys=True, separators=(",", ":"))


def render_queries(queries: list[list[int]]) -> str:
    return json.dumps(queries, separators=(",", ":"))
