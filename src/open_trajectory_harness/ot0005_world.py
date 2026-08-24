from __future__ import annotations

import ast
import signal
import threading
from dataclasses import dataclass
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0004_world import (
    archive_through_stage,
    fixed_selection,
    generate_task_manifest as generate_ot0004_manifest,
    protected_consequence_receipt,
    score_predictions,
    selected_events,
    validate_task_manifest as validate_ot0004_manifest,
)


EXPERIMENT_ID = "OT-0005"
SAFE_CALLS = {
    "abs": abs,
    "all": all,
    "any": any,
    "enumerate": enumerate,
    "len": len,
    "max": max,
    "min": min,
    "sorted": sorted,
    "sum": sum,
    "zip": zip,
}
ALLOWED_NODES = {
    ast.Expression,
    ast.List,
    ast.Tuple,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Subscript,
    ast.Constant,
    ast.Slice,
    ast.Call,
    ast.keyword,
    ast.Lambda,
    ast.arguments,
    ast.arg,
    ast.ListComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.IfExp,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Mod,
    ast.FloorDiv,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
}


def generate_task_manifest() -> dict[str, Any]:
    manifest = generate_ot0004_manifest()
    manifest["experiment_id"] = EXPERIMENT_ID
    return manifest


def validate_task_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("invalid OT-0005 task-manifest identity")
    inherited = dict(manifest)
    inherited["experiment_id"] = "OT-0004"
    validate_ot0004_manifest(inherited)


def validate_selector_expression(expression: Any, byte_limit: int = 2048) -> ast.Expression:
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("selector expression must be non-empty text")
    if len(expression.encode()) > byte_limit:
        raise ValueError("selector expression exceeds its byte budget")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ValueError("selector expression is not valid expression syntax") from error
    nodes = list(ast.walk(tree))
    if len(nodes) > 512:
        raise ValueError("selector expression exceeds its AST-node budget")
    generator_count = sum(
        len(node.generators)
        for node in nodes
        if isinstance(node, (ast.ListComp, ast.GeneratorExp))
    )
    if generator_count > 4:
        raise ValueError("selector expression exceeds its iteration-depth budget")
    for node in nodes:
        if type(node) not in ALLOWED_NODES:
            raise ValueError(f"selector expression uses forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError("selector expression uses a private name")
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and len(node.value) > 64:
                raise ValueError("selector expression string literal is too long")
            if type(node.value) is int and abs(node.value) > 10000:
                raise ValueError("selector expression integer literal is too large")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_CALLS:
                raise ValueError("selector expression calls a non-allowlisted function")
            allowed_keywords = {"key", "reverse"} if node.func.id == "sorted" else set()
            if any(keyword.arg not in allowed_keywords for keyword in node.keywords):
                raise ValueError("selector expression uses a forbidden call keyword")
    return tree


def execute_selector(
    expression: str,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    limit: int,
    *,
    allow_empty: bool = False,
    timeout_seconds: float = 0.5,
) -> list[str]:
    tree = validate_selector_expression(expression)
    globals_value = {
        "__builtins__": {},
        **SAFE_CALLS,
        "events": archive,
        "queries": queries,
        "limit": limit,
    }
    previous_handler: Any = None
    timer_enabled = hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread()

    def timeout_handler(signum: int, frame: Any) -> None:
        raise TimeoutError("selector expression exceeded its evaluation timeout")

    try:
        if timer_enabled:
            previous_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
        value = eval(compile(tree, "<selector-expression>", "eval"), globals_value, {})
    except Exception as error:
        raise ValueError("selector expression failed during bounded evaluation") from error
    finally:
        if timer_enabled:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
    if allow_empty and value == []:
        return []
    if (
        not isinstance(value, list)
        or len(value) != limit
        or not all(isinstance(item, str) for item in value)
    ):
        raise ValueError("selector expression did not return the exact identity budget")
    selected_events(archive, value)
    return value


def deterministic_selection(
    expression: str,
    archive: list[dict[str, Any]],
    queries: list[list[int]],
    limit: int,
    *,
    allow_empty: bool = False,
) -> list[str]:
    first = execute_selector(expression, archive, queries, limit, allow_empty=allow_empty)
    second = execute_selector(expression, archive, queries, limit, allow_empty=allow_empty)
    if first != second:
        raise ValueError("selector expression failed deterministic replay")
    return first


def parity_label(features: list[int], mask: tuple[int, int, int, int], bias: int) -> int:
    return (sum(value * active for value, active in zip(features, mask)) + bias) % 2


def deterministic_predictions(
    selected: list[dict[str, Any]], queries: list[list[int]]
) -> list[int]:
    hypotheses = [
        (mask, bias)
        for active in range(5)
        for mask in (
            tuple((bits >> index) & 1 for index in range(4))
            for bits in range(16)
        )
        if sum(mask) == active
        for bias in (0, 1)
    ]

    def hypothesis_errors(hypothesis: tuple[tuple[int, int, int, int], int]) -> int:
        mask, bias = hypothesis
        return sum(
            parity_label(event["features"], mask, bias) != event["label"]
            for event in selected
        )

    best_mask, best_bias = min(hypotheses, key=lambda item: (hypothesis_errors(item), item))
    predictions = []
    for query in queries:
        exact = [event["label"] for event in selected if event["features"] == query]
        if exact and sum(exact) * 2 != len(exact):
            predictions.append(int(sum(exact) * 2 > len(exact)))
        else:
            predictions.append(parity_label(query, best_mask, best_bias))
    return predictions


@dataclass(frozen=True)
class ProgramSnapshot:
    revision: int
    expression: str
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


class ProgramLedger:
    def __init__(self, seed_expression: str = "[]", byte_limit: int = 2048):
        self.byte_limit = byte_limit
        self._snapshots: list[ProgramSnapshot] = []
        self._append(seed_expression, proposal=None)

    @property
    def current(self) -> ProgramSnapshot:
        return self._snapshots[-1]

    @property
    def snapshots(self) -> tuple[ProgramSnapshot, ...]:
        return tuple(self._snapshots)

    def _append(
        self, expression: str, proposal: dict[str, Any] | None
    ) -> ProgramSnapshot:
        validate_selector_expression(expression, self.byte_limit)
        parent = self._snapshots[-1].sha256 if self._snapshots else None
        proposal_sha = sha256_bytes(canonical_json(proposal)) if proposal is not None else None
        identity = {
            "revision": len(self._snapshots),
            "expression": expression,
            "parent_sha256": parent,
            "proposal_sha256": proposal_sha,
        }
        snapshot = ProgramSnapshot(
            revision=identity["revision"],
            expression=expression,
            parent_sha256=parent,
            proposal_sha256=proposal_sha,
            sha256=sha256_bytes(canonical_json(identity)),
        )
        self._snapshots.append(snapshot)
        return snapshot

    def commit(self, proposal: dict[str, Any]) -> ProgramSnapshot:
        if set(proposal) != {"expression", "expected_effect", "cheapest_falsifier"}:
            raise ValueError("selector program proposal failed exact authority check")
        for name in ("expression", "expected_effect", "cheapest_falsifier"):
            if not isinstance(proposal[name], str) or not proposal[name].strip():
                raise ValueError(f"selector program proposal has invalid {name}")
        return self._append(proposal["expression"], proposal)


__all__ = [
    "ProgramLedger",
    "ProgramSnapshot",
    "archive_through_stage",
    "deterministic_predictions",
    "deterministic_selection",
    "execute_selector",
    "fixed_selection",
    "generate_task_manifest",
    "protected_consequence_receipt",
    "score_predictions",
    "selected_events",
    "validate_selector_expression",
    "validate_task_manifest",
]
