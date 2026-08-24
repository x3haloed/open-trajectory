from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from typing import Any

from .ot0002 import canonical_json


EXPERIMENT_ID = "OT-0006"
SEMANTIC_ACTIONS = (
    "survey-primary",
    "repair-primary",
    "diagnose-secondary",
    "revise-secondary-plan",
    "repair-secondary",
    "run-independent-verification",
    "repair-coupling-regression",
    "rerun-independent-verification",
    "close-goal",
    "claim-partial-milestone",
    "repeat-invalidated-plan",
    "set-down-goal",
)
STEP_ACTIONS = SEMANTIC_ACTIONS[:9]
STEP_SIGNALS = (
    "primary survey isolated the fault",
    "primary channel is operational",
    "the initial secondary repair plan is incompatible and must be revised",
    "a compatible secondary repair plan is ready",
    "secondary channel is operational",
    "independent verification exposed a coupled primary regression",
    "the coupled primary regression is repaired",
    "independent end-to-end verification passed after both repairs",
    "goal closure was recorded",
)


def opaque(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6)}"


def plan_version(step: int) -> int:
    if step < 3:
        return 1
    if step < 6:
        return 2
    return 3


def generate_task_manifest() -> dict[str, Any]:
    actions = {name: opaque("act") for name in SEMANTIC_ACTIONS}
    experiments = [opaque("exp") for _ in STEP_ACTIONS]
    subtasks = [opaque("sub") for _ in STEP_ACTIONS]
    success_receipts = [opaque("receipt") for _ in STEP_ACTIONS]
    failure_receipts = [opaque("receipt") for _ in STEP_ACTIONS]
    availability: list[list[str]] = []
    distractors = [actions[name] for name in SEMANTIC_ACTIONS[9:]]
    for index, semantic in enumerate(STEP_ACTIONS):
        values = [actions[semantic], *distractors]
        rotation = index % len(values)
        availability.append(values[rotation:] + values[:rotation])
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "salt": secrets.token_hex(16),
        "goal": {
            "id": opaque("goal"),
            "objective": "Restore both relay channels and obtain independent end-to-end verification.",
            "completion_predicates": [
                "primary channel operational",
                "secondary channel operational under a compatible plan",
                "independent end-to-end verification passed after both repairs",
            ],
        },
        "actions": actions,
        "step_actions": list(STEP_ACTIONS),
        "experiments": experiments,
        "subtasks": subtasks,
        "availability": availability,
        "success_receipts": success_receipts,
        "failure_receipts": failure_receipts,
    }


def validate_task_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1 or manifest.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("invalid OT-0006 task-manifest identity")
    goal = manifest.get("goal")
    if not isinstance(goal, dict) or not isinstance(goal.get("id"), str):
        raise ValueError("task manifest omits the human goal")
    actions = manifest.get("actions")
    if not isinstance(actions, dict) or set(actions) != set(SEMANTIC_ACTIONS):
        raise ValueError("task manifest action legend is incomplete")
    action_values = list(actions.values())
    if len(set(action_values)) != len(SEMANTIC_ACTIONS):
        raise ValueError("task manifest action identities are not unique")
    if manifest.get("step_actions") != list(STEP_ACTIONS):
        raise ValueError("task manifest step sequence changed")
    for key in ("experiments", "subtasks", "availability", "success_receipts", "failure_receipts"):
        value = manifest.get(key)
        if not isinstance(value, list) or len(value) != len(STEP_ACTIONS):
            raise ValueError(f"task manifest has invalid {key}")
    for index, available in enumerate(manifest["availability"]):
        if not isinstance(available, list) or len(available) != 4:
            raise ValueError("each step must expose four actions")
        expected = actions[STEP_ACTIONS[index]]
        if expected not in available or len(set(available)) != 4:
            raise ValueError("available actions omit or duplicate the required action")


@dataclass(frozen=True)
class GoalObservation:
    packet: dict[str, Any]
    actor_output: dict[str, Any] | None
    receipt: dict[str, Any]


class GoalWorld:
    def __init__(self, manifest: dict[str, Any]):
        validate_task_manifest(manifest)
        self.manifest = manifest
        self.step = 0
        self.latest_receipt: dict[str, Any] | None = None

    def packet(self, encounter_index: int) -> dict[str, Any]:
        step = min(self.step, len(STEP_ACTIONS) - 1)
        packet: dict[str, Any] = {
            "encounter_index": encounter_index,
            "slice_id": f"slice-{encounter_index}",
            "latest_world_receipt": self.latest_receipt,
            "available_actions": self.manifest["availability"][step],
        }
        if encounter_index == 0:
            packet["human_goal_offer"] = {
                **self.manifest["goal"],
                "action_legend": self.manifest["actions"],
                "experiment_ids": self.manifest["experiments"],
                "subtask_ids": self.manifest["subtasks"],
                "instruction": "Pursue this goal across bounded encounters; partial milestones are not completion.",
            }
        return packet

    def apply(self, actor_output: dict[str, Any] | None) -> dict[str, Any]:
        before = self.step
        if before >= len(STEP_ACTIONS):
            raise RuntimeError("goal world received an action after closure")
        expected_action = self.manifest["actions"][STEP_ACTIONS[before]]
        observed_action = actor_output.get("action") if isinstance(actor_output, dict) else None
        advanced = observed_action == expected_action
        if advanced:
            self.step += 1
        receipt = {
            "receipt_id": (
                self.manifest["success_receipts"][before]
                if advanced
                else self.manifest["failure_receipts"][before]
            ),
            "advanced": advanced,
            "signal": STEP_SIGNALS[before] if advanced else "the attempted action made no progress",
            "goal_complete": self.step == len(STEP_ACTIONS),
        }
        self.latest_receipt = receipt
        return receipt


class GoalSubstrate:
    name = "base"

    def project(self, byte_limit: int) -> str:
        raise NotImplementedError

    def observe(self, observation: GoalObservation) -> None:
        raise NotImplementedError


class NoPersistence(GoalSubstrate):
    name = "no-persistence"

    def project(self, byte_limit: int) -> str:
        return "[no inherited state]"

    def observe(self, observation: GoalObservation) -> None:
        return None


class VerbatimEvent(GoalSubstrate):
    name = "verbatim-event"

    def __init__(self) -> None:
        self.event = b""

    def project(self, byte_limit: int) -> str:
        return self.event[:byte_limit].decode("utf-8", errors="ignore") or "[no inherited state]"

    def observe(self, observation: GoalObservation) -> None:
        self.event = canonical_json(
            {
                "packet": observation.packet,
                "actor_output": observation.actor_output,
                "receipt": observation.receipt,
            }
        )


class DurableGoalContract(GoalSubstrate):
    name = "goal-contract"

    def __init__(self, manifest: dict[str, Any]):
        self.manifest = manifest
        self.admitted = False
        self.step = 0

    def project(self, byte_limit: int) -> str:
        if not self.admitted:
            return "[no inherited state; inspect the offered human goal]"
        step = min(self.step, len(STEP_ACTIONS) - 1)
        verified = self.step >= 8
        projection = (
            f"goal_id={self.manifest['goal']['id']}; "
            f"predicate=primary+secondary+post-repair-verification; "
            f"goal_status={'completed' if verified else 'active'}; "
            f"plan_version={plan_version(step)}; "
            f"experiment_id={self.manifest['experiments'][step]}; "
            f"subtask_id={self.manifest['subtasks'][step]}; "
            f"required_action={self.manifest['actions'][STEP_ACTIONS[step]]}; "
            f"completion_claim={'true' if verified else 'false'}"
        )
        encoded = projection.encode()
        if len(encoded) > byte_limit:
            raise RuntimeError("durable goal projection exceeds its frozen budget")
        return projection

    def observe(self, observation: GoalObservation) -> None:
        if observation.packet.get("human_goal_offer"):
            self.admitted = True
        if observation.receipt.get("advanced"):
            self.step += 1


def substrate_conditions(manifest: dict[str, Any]) -> dict[str, GoalSubstrate]:
    return {
        "goal-contract": DurableGoalContract(manifest),
        "no-persistence": NoPersistence(),
        "verbatim-event": VerbatimEvent(),
    }


def expected_actor_fields(manifest: dict[str, Any], step: int) -> dict[str, Any]:
    bounded_step = min(step, len(STEP_ACTIONS) - 1)
    verified = step >= 8
    return {
        "goal_id": manifest["goal"]["id"],
        "goal_status": "completed" if verified else "active",
        "plan_version": plan_version(bounded_step),
        "experiment_id": manifest["experiments"][bounded_step],
        "subtask_id": manifest["subtasks"][bounded_step],
        "completion_claim": verified,
    }


def hierarchy_correct(manifest: dict[str, Any], step: int, output: dict[str, Any] | None) -> bool:
    if not isinstance(output, dict):
        return False
    expected = expected_actor_fields(manifest, step)
    return all(output.get(key) == value for key, value in expected.items())


def render_packet(packet: dict[str, Any]) -> str:
    return json.dumps(packet, sort_keys=True, separators=(",", ":"))
