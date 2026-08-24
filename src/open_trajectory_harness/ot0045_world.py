from __future__ import annotations

import re
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0039_world import build_task as build_predecessor_task


EXPERIMENT_ID = "OT-0045"


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0045 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-e10-self-authored-durable-goal-task",
            }
        )
    )


def build_task(task_seed: str) -> dict[str, Any]:
    predecessor = build_predecessor_task(task_seed)
    body = {
        key: value
        for key, value in predecessor.items()
        if key not in {"experiment_id", "task_sha256"}
    }
    body["experiment_id"] = EXPERIMENT_ID
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def validate_task(task: dict[str, Any]) -> None:
    if task.get("schema_version") != 1 or task.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("invalid OT-0045 task identity")
    if canonical_json(build_task(task.get("task_seed", ""))) != canonical_json(task):
        raise ValueError("OT-0045 task differs from mechanical derivation")
