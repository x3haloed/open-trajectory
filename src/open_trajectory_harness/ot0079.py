"""Deterministic controller and evidence builder for OT-0079."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

from . import ot0079_protocol as protocol


class SelectorError(RuntimeError):
    """The proposed selector is outside the frozen carrier or failed execution."""


_FORBIDDEN_NODES: Final = (
    ast.Import,
    ast.ImportFrom,
    ast.AsyncFunctionDef,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)
_ALLOWED_CALLS: Final = {
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "range",
    "reversed",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
}
_ALLOWED_METHODS: Final = {
    "add",
    "append",
    "copy",
    "count",
    "difference",
    "discard",
    "extend",
    "get",
    "index",
    "intersection",
    "issubset",
    "items",
    "keys",
    "pop",
    "remove",
    "reverse",
    "sort",
    "symmetric_difference",
    "union",
    "update",
    "values",
}

_WORKER = r'''import json, sys
scope = {"__builtins__": {name: getattr(__builtins__, name) for name in %s}}
request = json.loads(sys.stdin.readline())
exec(request["source"], scope, scope)
result = scope["select"](request["candidates"], request["budget"])
sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")))
''' % (repr(sorted(_ALLOWED_CALLS)),)


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_selector(source: str) -> str:
    encoded = source.encode("utf-8")
    if not encoded or len(encoded) > protocol.SELECTOR_BYTE_LIMIT:
        raise SelectorError("selector byte bound differs")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise SelectorError("selector syntax is invalid") from error
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(tree.body) != 1 or len(functions) != 1:
        raise SelectorError("selector must contain exactly one function")
    function = functions[0]
    if function.name != "select" or [arg.arg for arg in function.args.args] != [
        "candidates",
        "budget",
    ]:
        raise SelectorError("selector signature differs")
    if function.decorator_list or function.args.vararg or function.args.kwarg:
        raise SelectorError("selector signature differs")
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_NODES):
            raise SelectorError(f"forbidden selector syntax: {type(node).__name__}")
        if isinstance(node, ast.Attribute) and (
            node.attr not in _ALLOWED_METHODS or node.attr.startswith("_")
        ):
            raise SelectorError("selector attribute is forbidden")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise SelectorError("dunder name is forbidden")
        if isinstance(node, ast.Call) and not (
            (isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_CALLS)
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _ALLOWED_METHODS
            )
        ):
                raise SelectorError("selector call is forbidden")
    compile(tree, "<ot0079-selector>", "exec")
    return source


def run_selector(source: str, world_name: str) -> list[str]:
    validate_selector(source)
    public = protocol.public_world(world_name)
    request = canonical_json(
        {"source": source, "candidates": public["candidates"], "budget": public["budget"]}
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", _WORKER],
            input=request,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=protocol.SELECTOR_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise SelectorError("selector timed out") from error
    if completed.returncode != 0:
        raise SelectorError("selector execution failed")
    try:
        selected = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SelectorError("selector output is invalid") from error
    world = protocol.authority_world(world_name)
    known = {item["id"] for item in world["candidates"]}
    if (
        type(selected) is not list
        or any(type(item) is not str for item in selected)
        or len(selected) != len(set(selected))
        or not set(selected).issubset(known)
    ):
        raise SelectorError("selector IDs are invalid")
    return selected


def evaluate(source: str, world_name: str) -> dict[str, Any]:
    world = protocol.authority_world(world_name)
    selected = run_selector(source, world_name)
    by_id = {item["id"]: item for item in world["candidates"]}
    covered = sorted({signal for item_id in selected for signal in by_id[item_id]["signals"]})
    total_effort = sum(by_id[item_id]["effort"] for item_id in selected)
    security_pass = set(world["required"]).issubset(covered)
    motion_pass = total_effort <= world["budget"]
    completed = security_pass and motion_pass
    utility = 10 if completed else (-8 if motion_pass and not security_pass else 0)
    public = protocol.public_world(world_name)
    return {
        "experiment_id": protocol.EXPERIMENT_ID,
        "world": world_name,
        "selector_sha256": sha256_bytes(source.encode()),
        "public_input": public,
        "selected": selected,
        "total_effort": total_effort,
        "security_pass": security_pass,
        "motion_pass": motion_pass,
        "completed": completed,
        "utility": utility,
    }


CONTROL_SELECTORS: Final[dict[str, str]] = {
    "seed-risk-first": protocol.SEED_SELECTOR,
    "effort-first": '''def select(candidates, budget):
    ranked = sorted(candidates, key=lambda item: (item["effort"], item["id"]))
    return [item["id"] for item in ranked[:2]]
''',
    "certainty-first": '''def select(candidates, budget):
    ranked = sorted(candidates, key=lambda item: (-item["certainty"], item["id"]))
    return [item["id"] for item in ranked[:2]]
''',
    "signal-count-first": '''def select(candidates, budget):
    ranked = sorted(candidates, key=lambda item: (-len(item["signals"]), item["id"]))
    return [item["id"] for item in ranked[:2]]
''',
}


def contact_prompt(parent_source: str, receipt: dict[str, Any], *, second: bool) -> str:
    orientation = protocol.CHILD2_PROMPT if second else protocol.CHILD1_PROMPT
    actor_receipt = {
        key: receipt[key]
        for key in (
            "world",
            "public_input",
            "selected",
            "total_effort",
            "security_pass",
            "motion_pass",
            "completed",
        )
    }
    return (
        orientation
        + "\n\nPARENT SOURCE\n"
        + parent_source
        + "\nCOMPLETED CONTACT RECEIPT\n"
        + canonical_json(actor_receipt).decode()
    )


def complete_evaluation(child1: str, child2: str) -> dict[str, Any]:
    selectors = {
        "seed": protocol.SEED_SELECTOR,
        "child1": validate_selector(child1),
        "child2": validate_selector(child2),
    }
    if child1.encode() == protocol.SEED_SELECTOR.encode() or child2.encode() == child1.encode():
        raise SelectorError("child selector equals parent")
    receipts = {
        "seed_a_train": evaluate(selectors["seed"], "a_train"),
        "seed_a_test": evaluate(selectors["seed"], "a_test"),
        "child1_a_train": evaluate(selectors["child1"], "a_train"),
        "child1_a_test": evaluate(selectors["child1"], "a_test"),
        "child1_b_train": evaluate(selectors["child1"], "b_train"),
        "child1_b_test": evaluate(selectors["child1"], "b_test"),
        "child2_b_train": evaluate(selectors["child2"], "b_train"),
        "child2_b_test": evaluate(selectors["child2"], "b_test"),
    }
    controls = {
        name: {world: evaluate(source, world) for world in protocol.TASK_ORDER}
        for name, source in CONTROL_SELECTORS.items()
    }
    gates = {
        "seed_fails_a_test": not receipts["seed_a_test"]["completed"],
        "child1_completes_a_test": receipts["child1_a_test"]["completed"],
        "child1_b_train_harmful": (
            not receipts["child1_b_train"]["security_pass"]
            and receipts["child1_b_train"]["motion_pass"]
        ),
        "child1_fails_b_test": not receipts["child1_b_test"]["completed"],
        "child2_completes_b_test": receipts["child2_b_test"]["completed"],
        "selector_change_ablation_removes_advantage": (
            receipts["child2_b_test"]["completed"]
            and not receipts["child1_b_test"]["completed"]
        ),
    }
    result = {
        "experiment_id": protocol.EXPERIMENT_ID,
        "selector_identities": {
            name: sha256_bytes(source.encode()) for name, source in selectors.items()
        },
        "receipts": receipts,
        "controls": controls,
        "gates": gates,
        "passed": all(gates.values()),
        "claim_limit": "exploratory-only; no target promotion",
    }
    result["evaluation_sha256"] = sha256_bytes(canonical_json(result))
    return result


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prompt_parser = subparsers.add_parser("prompt")
    prompt_parser.add_argument("--parent", required=True)
    prompt_parser.add_argument("--world", choices=("a_train", "b_train"), required=True)
    prompt_parser.add_argument("--second", action="store_true")
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--child1", required=True)
    evaluate_parser.add_argument("--child2", required=True)
    args = parser.parse_args(argv)
    if args.command == "prompt":
        parent = _read(args.parent)
        print(contact_prompt(parent, evaluate(parent, args.world), second=args.second), end="")
        return 0
    result = complete_evaluation(_read(args.child1), _read(args.child2))
    sys.stdout.buffer.write(canonical_json(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
