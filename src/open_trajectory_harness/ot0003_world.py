from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Protocol


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
    def project(self, queries: tuple[tuple[int, int, int, int], ...], byte_limit: int) -> str:
        return "No inherited observations."

    def observe(self, observations: Iterable[Observation]) -> None:
        return None


class VerbatimEvents:
    def __init__(self) -> None:
        self.events: list[Observation] = []

    def project(self, queries: tuple[tuple[int, int, int, int], ...], byte_limit: int) -> str:
        items = [
            json.dumps({"x": event.features, "y": event.label}, separators=(",", ":"))
            for event in reversed(self.events)
        ]
        return _bounded(items, byte_limit, prefix="Recent events:\n")

    def observe(self, observations: Iterable[Observation]) -> None:
        self.events.extend(observations)


def hamming(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    return sum(a != b for a, b in zip(left, right))


class NearestEvents(VerbatimEvents):
    def project(self, queries: tuple[tuple[int, int, int, int], ...], byte_limit: int) -> str:
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

    @staticmethod
    def _consistent(rule: ParityRule, observations: Iterable[Observation]) -> bool:
        return all(rule.predict(item.features) == item.label for item in observations)

    def project(self, queries: tuple[tuple[int, int, int, int], ...], byte_limit: int) -> str:
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
        survivors = [rule for rule in self.hypotheses if self._consistent(rule, batch)]
        if not survivors:
            self.regime += 1
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


def score_predictions(predictions: Iterable[int], outcomes: Iterable[int]) -> dict[str, int]:
    predicted = tuple(predictions)
    expected = tuple(outcomes)
    if len(predicted) != len(expected):
        raise ValueError("prediction and outcome lengths differ")
    errors = sum(left != right for left, right in zip(predicted, expected))
    return {"predictions": len(expected), "errors": errors, "correct": len(expected) - errors}
