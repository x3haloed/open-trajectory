from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0048 import (
    build_task as build_calibration_task,
    complete_contact,
    expected_future_task_seed,
    future_task_case,
    score,
    weighted_selections,
)


EXPERIMENT_ID = "OT-0049"
INITIAL_WEIGHTS = (1, 5, 25, 125)
MAX_SOURCE_BYTES = 160
MAX_AST_NODES = 31
MAX_ABSOLUTE_VALUE = 10**12


@dataclass(frozen=True)
class CandidateSnapshot:
    revision: int
    parent_sha256: str | None
    outcome_receipt_sha256: str
    state: dict[str, Any]
    sha256: str


def expected_task_seed(implementation_commit: str) -> str:
    return expected_future_task_seed(implementation_commit)


def build_task(task_seed: str) -> dict[str, Any]:
    calibration = build_calibration_task(future_task_case(task_seed))
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "task_seed": task_seed,
        "regimes": calibration["regimes"],
    }
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def validate_task(task: dict[str, Any]) -> None:
    if (
        task.get("schema_version") != 1
        or task.get("experiment_id") != EXPERIMENT_ID
        or not re.fullmatch(r"[0-9a-f]{64}", task.get("task_seed", ""))
    ):
        raise ValueError("OT-0049 task identity is malformed")
    if canonical_json(build_task(task["task_seed"])) != canonical_json(task):
        raise ValueError("OT-0049 task differs from its mechanical derivation")


def _make_snapshot(
    revision: int,
    parent_sha256: str | None,
    outcome_receipt_sha256: str,
    state: dict[str, Any],
) -> CandidateSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "outcome_receipt_sha256": outcome_receipt_sha256,
        "state": state,
    }
    return CandidateSnapshot(
        revision=revision,
        parent_sha256=parent_sha256,
        outcome_receipt_sha256=outcome_receipt_sha256,
        state=state,
        sha256=sha256_bytes(canonical_json(body)),
    )


def initial_snapshot() -> CandidateSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "ot-0049-seed"}))
    return _make_snapshot(
        0,
        None,
        receipt,
        {"weights": list(INITIAL_WEIGHTS)},
    )


def project_snapshot(snapshot: CandidateSnapshot) -> dict[str, Any]:
    value = {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "outcome_receipt_sha256": snapshot.outcome_receipt_sha256,
        "state": snapshot.state,
        "sha256": snapshot.sha256,
    }
    if len(canonical_json(value)) > 512:
        raise ValueError("OT-0049 projection exceeds its frozen byte budget")
    return value


def restore_snapshot(value: dict[str, Any]) -> CandidateSnapshot:
    if set(value) != {
        "revision",
        "parent_sha256",
        "outcome_receipt_sha256",
        "state",
        "sha256",
    }:
        raise ValueError("OT-0049 projection has unexpected authority")
    if (
        type(value["revision"]) is not int
        or value["revision"] < 0
        or not isinstance(value["parent_sha256"], (str, type(None)))
        or not isinstance(value["outcome_receipt_sha256"], str)
        or not isinstance(value["state"], dict)
        or not isinstance(value["sha256"], str)
    ):
        raise ValueError("OT-0049 projection is malformed")
    restored = _make_snapshot(
        value["revision"],
        value["parent_sha256"],
        value["outcome_receipt_sha256"],
        value["state"],
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("OT-0049 projection identity differs")
    validate_state(restored.state)
    return restored


def _validate_expression_node(node: ast.AST) -> None:
    if isinstance(node, ast.Expression):
        _validate_expression_node(node.body)
        return
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult)
    ):
        _validate_expression_node(node.left)
        _validate_expression_node(node.right)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        _validate_expression_node(node.operand)
        return
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "x"
    ):
        index = node.slice
        if (
            not isinstance(index, ast.Constant)
            or type(index.value) is not int
            or index.value not in range(4)
        ):
            raise ValueError("OT-0049 state uses an invalid raw-coordinate index")
        return
    if (
        isinstance(node, ast.Constant)
        and type(node.value) is int
        and abs(node.value) <= 16
    ):
        return
    raise ValueError("OT-0049 state is outside the bounded expression language")


def parse_expression(source: str) -> ast.Expression:
    if (
        not isinstance(source, str)
        or not source.strip()
        or len(source.encode()) > MAX_SOURCE_BYTES
    ):
        raise ValueError("OT-0049 state source is empty or over budget")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as error:
        raise ValueError("OT-0049 state is not one expression") from error
    if len(list(ast.walk(tree))) > MAX_AST_NODES:
        raise ValueError("OT-0049 state has too many syntax nodes")
    _validate_expression_node(tree)
    return tree


def expression_fingerprint(source: str) -> str:
    tree = parse_expression(source)
    return sha256_bytes(
        ast.dump(tree, annotate_fields=True, include_attributes=False).encode()
    )


def validate_state(state: dict[str, Any]) -> None:
    if set(state) == {"weights"}:
        weights = state["weights"]
        if weights != list(INITIAL_WEIGHTS):
            raise ValueError("OT-0049 old-carrier state differs from its frozen seed")
        return
    if set(state) == {"source", "syntax_sha256"}:
        if expression_fingerprint(state["source"]) != state["syntax_sha256"]:
            raise ValueError("OT-0049 expression identity differs")
        return
    raise ValueError(
        "OT-0049 state is neither the seed carrier nor an authored operation"
    )


def _evaluate(node: ast.AST, x: tuple[int, ...]) -> int:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, x)
    if isinstance(node, ast.Constant):
        return int(node.value)
    if isinstance(node, ast.Subscript):
        assert isinstance(node.slice, ast.Constant)
        return x[int(node.slice.value)]
    if isinstance(node, ast.UnaryOp):
        value = _evaluate(node.operand, x)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _evaluate(node.left, x), _evaluate(node.right, x)
        if isinstance(node.op, ast.Add):
            value = left + right
        elif isinstance(node.op, ast.Sub):
            value = left - right
        else:
            value = left * right
        if abs(value) > MAX_ABSOLUTE_VALUE:
            raise ValueError("OT-0049 expression exceeded its numeric bound")
        return value
    raise AssertionError("validated OT-0049 syntax was not executable")


def expression_value(source: str, features: list[int]) -> int:
    if len(features) != 4 or any(type(value) is not int for value in features):
        raise ValueError("OT-0049 event features are malformed")
    return _evaluate(parse_expression(source), tuple(features))


def snapshot_selections(
    snapshot: CandidateSnapshot, split: dict[str, Any]
) -> list[str]:
    validate_state(snapshot.state)
    if "weights" in snapshot.state:
        return weighted_selections(tuple(snapshot.state["weights"]), split)
    source = snapshot.state["source"]
    return [
        min(
            pair["events"],
            key=lambda event: (
                -expression_value(source, event["selector_features"]),
                event["event_id"],
            ),
        )["event_id"]
        for pair in split["pairs"]
    ]


def validate_actor_output(output: dict[str, Any] | None) -> str:
    if (
        not isinstance(output, dict)
        or set(output) != {"state"}
        or not isinstance(output["state"], str)
    ):
        raise ValueError("OT-0049 actor output has unexpected authority")
    parse_expression(output["state"])
    return output["state"]


def _validate_receipt(receipt: dict[str, Any]) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if sha256_bytes(canonical_json(body)) != receipt.get("receipt_sha256"):
        raise ValueError("OT-0049 outcome receipt identity differs")


def commit_proposal(
    current: CandidateSnapshot,
    receipt: dict[str, Any],
    output: dict[str, Any] | None,
) -> CandidateSnapshot:
    _validate_receipt(receipt)
    if receipt.get("outcome_credit") is False:
        return current
    if receipt.get("outcome_credit") is not True:
        raise ValueError("OT-0049 consequence authority is malformed")
    source = validate_actor_output(output)
    state = {"source": source, "syntax_sha256": expression_fingerprint(source)}
    return _make_snapshot(
        current.revision + 1,
        current.sha256,
        receipt["receipt_sha256"],
        state,
    )


def public_actor_view(
    contact: dict[str, Any],
    current: CandidateSnapshot,
    choices: list[str],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    public_receipt = {
        "outcome_credit": receipt["outcome_credit"],
        "items": receipt["items"],
        "receipt_sha256": receipt["receipt_sha256"],
    }
    return {
        "encounter": {
            "pairs": [
                {"pattern_id": pair["pattern_id"], "events": pair["events"]}
                for pair in contact["pairs"]
            ]
        },
        "current_snapshot": project_snapshot(current),
        "prior_choices": choices,
        "released_receipt": public_receipt,
    }


def counterbalanced_split(split: dict[str, Any], worker: str) -> dict[str, Any]:
    if worker not in {"worker-1", "worker-2"}:
        raise ValueError("OT-0049 worker identity is invalid")
    pairs = list(split["pairs"])
    if worker == "worker-2":
        pairs.reverse()
    result = []
    for position, pair in enumerate(pairs):
        events = list(pair["events"])
        if (position + (worker == "worker-2")) % 2:
            events.reverse()
        result.append({**pair, "events": events})
    return {"pairs": result}


def validate_counterbalance_config(config: dict[str, Any]) -> None:
    expected = {
        "schema_version": 1,
        "workers": {
            "worker-1": {"pair_order": "forward", "first_event_swap_parity": 1},
            "worker-2": {"pair_order": "reverse", "first_event_swap_parity": 0},
        },
    }
    if config != expected:
        raise ValueError(
            "OT-0049 counterbalance differs from its frozen implementation"
        )


def completed_contact_for_snapshot(
    snapshot: CandidateSnapshot, split: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    choices = snapshot_selections(snapshot, split)
    return choices, complete_contact(split, choices)


def score_snapshot(snapshot: CandidateSnapshot, split: dict[str, Any]) -> int:
    return score(split, snapshot_selections(snapshot, split))


def source_absent_before_contact(
    repo: Path, source: str, paths: list[Path]
) -> dict[str, Any]:
    normalized = "".join(source.split())
    collisions = []
    for path in paths:
        text = (repo / path).read_text(encoding="utf-8")
        if normalized and normalized in "".join(text.split()):
            collisions.append(str(path))
    body = {
        "source_sha256": sha256_bytes(source.encode()),
        "syntax_sha256": expression_fingerprint(source),
        "collision_paths": collisions,
    }
    return {
        **body,
        "pass": not collisions,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }
