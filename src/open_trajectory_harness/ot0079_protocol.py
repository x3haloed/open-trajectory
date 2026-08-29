"""P-frozen public protocol for the OT-0079 composition-correction pilot."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Final


EXPERIMENT_ID: Final = "OT-0079"
SELECTOR_BYTE_LIMIT: Final = 4096
SELECTOR_TIMEOUT_SECONDS: Final = 2
TASK_ORDER: Final = ("a_train", "a_test", "b_train", "b_test")

SEED_SELECTOR: Final = '''def select(candidates, budget):
    ranked = sorted(candidates, key=lambda item: (-item["risk"], item["id"]))
    return [item["id"] for item in ranked[:2]]
'''

CHILD1_PROMPT: Final = """You are revising one inherited selection program after completed contact with an independently scored world. You receive the parent source, public candidates and budget, its selected IDs, and the independent security and motion receipt. Author one replacement Python function named select(candidates, budget). Return only the source file. The function must be deterministic, use no imports or external capabilities, and return distinct candidate IDs. You will not see hidden requirements, held-out worlds, controls, or final scores. Improve the selection function in response to the completed consequence without assuming candidate IDs recur."""

CHILD2_PROMPT: Final = CHILD1_PROMPT

_WORLDS: Final[dict[str, dict[str, Any]]] = {
    "a_train": {
        "budget": 3,
        "required": ["p"],
        "candidates": [
            {"id": "aegis", "risk": 5, "certainty": 3, "effort": 5, "signals": ["p"]},
            {"id": "watch", "risk": 4, "certainty": 2, "effort": 2, "signals": ["p"]},
            {"id": "receipt", "risk": 3, "certainty": 5, "effort": 2, "signals": ["p"]},
            {"id": "review", "risk": 2, "certainty": 5, "effort": 1, "signals": []}
        ]
    },
    "a_test": {
        "budget": 3,
        "required": ["u"],
        "candidates": [
            {"id": "bastion", "risk": 5, "certainty": 3, "effort": 5, "signals": ["u"]},
            {"id": "monitor", "risk": 4, "certainty": 2, "effort": 2, "signals": ["u"]},
            {"id": "binding", "risk": 3, "certainty": 5, "effort": 2, "signals": ["u"]},
            {"id": "audit", "risk": 2, "certainty": 5, "effort": 1, "signals": []}
        ]
    },
    "b_train": {
        "budget": 3,
        "required": ["p", "q"],
        "candidates": [
            {"id": "receipt", "risk": 4, "certainty": 5, "effort": 2, "signals": ["p"]},
            {"id": "watch", "risk": 3, "certainty": 3, "effort": 2, "signals": ["q"]},
            {"id": "bridge", "risk": 3, "certainty": 3, "effort": 3, "signals": ["p", "q"]},
            {"id": "review", "risk": 2, "certainty": 5, "effort": 1, "signals": []}
        ]
    },
    "b_test": {
        "budget": 3,
        "required": ["u", "v"],
        "candidates": [
            {"id": "binding", "risk": 4, "certainty": 5, "effort": 2, "signals": ["u"]},
            {"id": "monitor", "risk": 3, "certainty": 3, "effort": 2, "signals": ["v"]},
            {"id": "fusion", "risk": 3, "certainty": 3, "effort": 3, "signals": ["u", "v"]},
            {"id": "audit", "risk": 2, "certainty": 5, "effort": 1, "signals": []}
        ]
    }
}


def public_world(name: str) -> dict[str, Any]:
    """Return the actor-visible portion of one frozen world."""
    world = _world(name)
    return {"budget": world["budget"], "candidates": deepcopy(world["candidates"])}


def authority_world(name: str) -> dict[str, Any]:
    """Return a controller-owned copy including hidden required signals."""
    return _world(name)


def _world(name: str) -> dict[str, Any]:
    if name not in TASK_ORDER or name not in _WORLDS:
        raise ValueError("unknown OT-0079 world")
    return deepcopy(_WORLDS[name])


def validate_protocol() -> None:
    """Fail closed if the frozen public task family is malformed."""
    if tuple(_WORLDS) != TASK_ORDER:
        raise ValueError("OT-0079 task order differs")
    for name in TASK_ORDER:
        world = _WORLDS[name]
        if type(world["budget"]) is not int or world["budget"] <= 0:
            raise ValueError("invalid budget")
        ids = [item["id"] for item in world["candidates"]]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate IDs differ")
        for item in world["candidates"]:
            if set(item) != {"id", "risk", "certainty", "effort", "signals"}:
                raise ValueError("candidate surface differs")
            if type(item["signals"]) is not list:
                raise ValueError("candidate signals differ")


validate_protocol()
