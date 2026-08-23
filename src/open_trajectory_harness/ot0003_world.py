from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from typing import Any, Iterable, Protocol


FEATURES = ("a", "b", "c", "d")


@dataclass(frozen=True)
class ParityRule:
    rule_id: str
    mask: tuple[int, int, int, int]
    bias: int

    def predict(self, features: tuple[int, int, int, int]) -> int:
        return (sum(bit * enabled for bit, enabled in zip(features, self.mask)) + self.bias) % 2

    def description(self) -> str:
        terms = [name for name, enabled in zip(FEATURES, self.mask) if enabled]
        expression = " xor ".join(terms) if terms else "0"
        if self.bias:
            expression += " xor 1"
        return f"label = {expression}"


RULES = tuple(
    ParityRule(f"parity-{mask:01x}-{bias}", tuple((mask >> index) & 1 for index in range(4)), bias)
    for mask in range(1, 16)
    for bias in (0, 1)
)
RULE_BY_ID = {rule.rule_id: rule for rule in RULES}


@dataclass(frozen=True)
class Observation:
    features: tuple[int, int, int, int]
    label: int


class InheritanceSubstrate(Protocol):
    def project(self, queries: tuple[tuple[int, int, int, int], ...], byte_limit: int) -> str: ...

    def observe(self, observations: Iterable[Observation]) -> None: ...


def _bounded(encoded_items: list[str], byte_limit: int, *, prefix: str) -> str:
    selected: list[str] = []
    for item in encoded_items:
        candidate = prefix + "\n".join([*selected, item])
        if len(candidate.encode()) > byte_limit:
            break
        selected.append(item)
    return prefix + "\n".join(selected)


class NoPersistence:
    last_project_operations = 0
    last_observe_operations = 0

    def project(self, queries: tuple[tuple[int, int, int, int], ...], byte_limit: int) -> str:
        return "No inherited observations."

    def observe(self, observations: Iterable[Observation]) -> None:
        return None


class VerbatimEvents:
    def __init__(self) -> None:
        self.events: list[Observation] = []
        self.last_project_operations = 0
        self.last_observe_operations = 0

    def project(self, queries: tuple[tuple[int, int, int, int], ...], byte_limit: int) -> str:
        self.last_project_operations = len(self.events)
        items = [
            json.dumps({"x": event.features, "y": event.label}, separators=(",", ":"))
            for event in reversed(self.events)
        ]
        return _bounded(items, byte_limit, prefix="Recent events:\n")

    def observe(self, observations: Iterable[Observation]) -> None:
        batch = tuple(observations)
        self.last_observe_operations = len(batch)
        self.events.extend(batch)


def hamming(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    return sum(a != b for a, b in zip(left, right))


class NearestEvents(VerbatimEvents):
    def project(self, queries: tuple[tuple[int, int, int, int], ...], byte_limit: int) -> str:
        self.last_project_operations = len(self.events) * max(len(queries), 1)
        ranked = sorted(
            enumerate(self.events),
            key=lambda pair: (
                min((hamming(pair[1].features, query) for query in queries), default=0),
                -pair[0],
            ),
        )
        items = [
            json.dumps({"x": event.features, "y": event.label}, separators=(",", ":"))
            for _, event in ranked
        ]
        return _bounded(items, byte_limit, prefix="Nearest prior events:\n")


class DiscrepancyGatedVersionLedger:
    """A bounded rule ledger whose only reset trigger is independent contradiction."""

    def __init__(self) -> None:
        self.hypotheses = list(RULES)
        self.regime = 0
        self.last_project_operations = 0
        self.last_observe_operations = 0

    @staticmethod
    def _consistent(rule: ParityRule, observations: Iterable[Observation]) -> bool:
        return all(rule.predict(item.features) == item.label for item in observations)

    def project(self, queries: tuple[tuple[int, int, int, int], ...], byte_limit: int) -> str:
        self.last_project_operations = len(self.hypotheses)
        if len(self.hypotheses) == 1:
            text = f"Inherited rule (regime {self.regime}): {self.hypotheses[0].description()}"
        else:
            descriptions = [rule.description() for rule in self.hypotheses]
            text = _bounded(descriptions, byte_limit, prefix=f"Viable rules (regime {self.regime}):\n")
        if len(text.encode()) > byte_limit:
            raise ValueError("rule projection exceeds byte limit")
        return text

    def observe(self, observations: Iterable[Observation]) -> None:
        batch = tuple(observations)
        self.last_observe_operations = len(self.hypotheses) * len(batch)
        survivors = [rule for rule in self.hypotheses if self._consistent(rule, batch)]
        if not survivors:
            self.regime += 1
            self.last_observe_operations += len(RULES) * len(batch)
            survivors = [rule for rule in RULES if self._consistent(rule, batch)]
        self.hypotheses = survivors


def rule_contact_batch() -> tuple[tuple[int, int, int, int], ...]:
    return (
        (0, 0, 0, 0),
        (1, 0, 0, 0),
        (0, 1, 0, 0),
        (0, 0, 1, 0),
        (0, 0, 0, 1),
    )


def structural_holdout_batch() -> tuple[tuple[int, int, int, int], ...]:
    return (
        (1, 1, 0, 0),
        (1, 0, 1, 0),
        (1, 0, 0, 1),
        (0, 1, 1, 0),
        (0, 1, 0, 1),
        (0, 0, 1, 1),
        (1, 1, 1, 0),
        (1, 1, 1, 1),
    )


def eligible_hidden_rules() -> tuple[ParityRule, ...]:
    holdouts = structural_holdout_batch()
    return tuple(
        rule
        for rule in RULES
        if sum(rule.mask) >= 2 and sum(rule.predict(item) for item in holdouts) == len(holdouts) // 2
    )


def generate_task_manifest() -> dict[str, Any]:
    eligible = eligible_hidden_rules()
    first = secrets.choice(eligible)
    second = secrets.choice(tuple(rule for rule in eligible if rule != first))
    batches = {
        "basis": rule_contact_batch(),
        "structural-1": structural_holdout_batch()[:4],
        "structural-2": structural_holdout_batch()[4:],
    }
    return {
        "schema_version": 1,
        "experiment_id": "OT-0003",
        "salt": secrets.token_hex(32),
        "rules": {"regime-a": first.rule_id, "regime-b": second.rule_id},
        "batches": {
            name: [list(features) for features in values] for name, values in batches.items()
        },
        "outcomes": {
            regime: {
                name: [RULE_BY_ID[rule_id].predict(features) for features in values]
                for name, values in batches.items()
            }
            for regime, rule_id in (("regime-a", first.rule_id), ("regime-b", second.rule_id))
        },
    }


def validate_task_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1 or manifest.get("experiment_id") != "OT-0003":
        raise ValueError("invalid task-manifest identity")
    salt = manifest.get("salt")
    if not isinstance(salt, str) or not re.fullmatch(r"[0-9a-f]{64}", salt):
        raise ValueError("task manifest requires a 256-bit salt")
    rules = manifest.get("rules")
    if not isinstance(rules, dict) or set(rules) != {"regime-a", "regime-b"}:
        raise ValueError("task manifest requires two regimes")
    eligible_ids = {rule.rule_id for rule in eligible_hidden_rules()}
    if (
        any(not isinstance(rule_id, str) or rule_id not in eligible_ids for rule_id in rules.values())
        or len(set(rules.values())) != 2
    ):
        raise ValueError("task manifest rules are ineligible or not distinct")
    expected = generate_manifest_for_rules(rules["regime-a"], rules["regime-b"], salt)
    if manifest != expected:
        raise ValueError("task manifest inputs or outcomes differ from the frozen generator")


def generate_manifest_for_rules(first_id: str, second_id: str, salt: str) -> dict[str, Any]:
    batches = {
        "basis": rule_contact_batch(),
        "structural-1": structural_holdout_batch()[:4],
        "structural-2": structural_holdout_batch()[4:],
    }
    return {
        "schema_version": 1,
        "experiment_id": "OT-0003",
        "salt": salt,
        "rules": {"regime-a": first_id, "regime-b": second_id},
        "batches": {
            name: [list(features) for features in values] for name, values in batches.items()
        },
        "outcomes": {
            regime: {
                name: [RULE_BY_ID[rule_id].predict(features) for features in values]
                for name, values in batches.items()
            }
            for regime, rule_id in (("regime-a", first_id), ("regime-b", second_id))
        },
    }


def manifest_batch(
    manifest: dict[str, Any], regime: str, batch: str
) -> tuple[tuple[tuple[int, int, int, int], ...], tuple[int, ...]]:
    features = tuple(tuple(item) for item in manifest["batches"][batch])
    outcomes = tuple(manifest["outcomes"][regime][batch])
    return features, outcomes


def substrate_conditions() -> dict[str, InheritanceSubstrate]:
    return {
        "candidate": DiscrepancyGatedVersionLedger(),
        "no-persistence": NoPersistence(),
        "verbatim-events": VerbatimEvents(),
        "nearest-events": NearestEvents(),
    }


def score_predictions(predictions: Iterable[int], outcomes: Iterable[int]) -> dict[str, int]:
    predicted = tuple(predictions)
    expected = tuple(outcomes)
    if len(predicted) != len(expected):
        raise ValueError("prediction and outcome lengths differ")
    errors = sum(left != right for left, right in zip(predicted, expected))
    return {"predictions": len(expected), "errors": errors, "correct": len(expected) - errors}
