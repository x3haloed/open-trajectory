from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ot0002 import canonical_json, sha256_bytes
from .ot0003_world import DiscrepancyGatedVersionLedger, RULES, structural_holdout_batch
from .ot0033_weighted_selector import (
    _hidden_weights,
    complete_encounter,
    initial_snapshot,
    learn,
    neutralize_outcome_credit,
    project,
    restore,
)
from .ot0035_integration import apply_to_ledger, build_contact
from .ot0036_e6_calibration import controller_predictions, criteria, rule_pairs
from .ot0038_e7_ot2_calibration import oracle_contract, score_contract


EXPERIMENT_ID = "OT-0039"
PHASE_NAMES = (
    "admission",
    "first-repair",
    "first-revision",
    "second-repair",
    "second-revision",
    "third-repair",
    "independent-verification",
    "post-receipt-judgment",
)
PLAN_VERSIONS = (1, 1, 2, 2, 3, 3, 3, 3)
TARGET_COUNT = 3
PROJECTION_LIMIT = 512


def _token(prefix: str, body: Any, length: int = 12) -> str:
    return f"{prefix}-{sha256_bytes(canonical_json(body))[:length]}"


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0039 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "fresh-e7-self-authored-durable-goal-task",
            }
        )
    )


def _rule_outcomes(rule_id: str) -> tuple[int, ...]:
    rule = next(rule for rule in RULES if rule.rule_id == rule_id)
    return tuple(rule.predict(query) for query in structural_holdout_batch())


def build_task(task_seed: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", task_seed):
        raise ValueError("OT-0039 task seed is malformed")
    criterion = _hidden_weights(task_seed)
    criterion_family = criteria()
    criterion_index = criterion_family.index(criterion)
    pairs = rule_pairs()
    pair_digest = sha256_bytes(f"{task_seed}:goal-route-pair".encode())
    pair_index = int(pair_digest, 16) % len(pairs)
    pair = pairs[pair_index]
    if int(pair_digest[0], 16) % 2:
        pair = (pair[1], pair[0])
    queries = structural_holdout_batch()
    initial_routes = _rule_outcomes(pair[0])
    high = [index for index, route in enumerate(initial_routes) if route == 1]
    low = [index for index, route in enumerate(initial_routes) if route == 0]
    high.sort(key=lambda index: sha256_bytes(f"{task_seed}:high:{index}".encode()))
    low.sort(key=lambda index: sha256_bytes(f"{task_seed}:low:{index}".encode()))
    values: dict[int, int] = {}
    for index, value in zip(high, (8, 7, 6, 5), strict=True):
        values[index] = value
    for index, value in zip(low, (4, 3, 2, 1), strict=True):
        values[index] = value
    assets = []
    for index, query in enumerate(queries):
        assets.append(
            {
                "asset_id": _token("svc", (task_seed, "asset", index)),
                "query": query,
                "offline": True,
                "service_value": values[index],
                "reversible_routes": (
                    _token("route", (task_seed, "route", index, 0)),
                    _token("route", (task_seed, "route", index, 1)),
                ),
            }
        )
    raw_packet = {
        "procedural_orientation": {
            "instruction": (
                "Select one bounded worthwhile undertaking from observed service "
                "conditions; state how it can fail; preserve it across plan changes; "
                "and use only sealed receipts for terminal status."
            ),
            "preferred_value": "independently verified service restoration",
        },
        "environment": {
            "assets": [
                {
                    "asset_id": asset["asset_id"],
                    "offline": True,
                    "service_value": asset["service_value"],
                    "reversible_routes": list(asset["reversible_routes"]),
                }
                for asset in assets
            ],
            "intervention_budget": TARGET_COUNT,
            "receipt_types": [
                "controller-repair",
                "route-model-invalidated",
                "independent-end-to-end-verification",
                "sealed-upper-bound",
                "authority-decision",
            ],
        },
    }
    ranked = sorted(
        assets, key=lambda asset: (-asset["service_value"], asset["asset_id"])
    )
    targets = [asset["asset_id"] for asset in ranked[:TARGET_COUNT]]
    revise_actions = [
        _token("act", (task_seed, "revise", index)) for index in (1, 2)
    ]
    special_actions = {
        "verify": _token("act", (task_seed, "verify")),
        "report": _token("act", (task_seed, "report")),
    }
    distractors = [
        _token("act", (task_seed, "distractor", index)) for index in range(8)
    ]
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "task_seed": task_seed,
        "criterion_index": criterion_index,
        "criterion": criterion,
        "pair_index": pair_index,
        "pair": pair,
        "assets": assets,
        "raw_packet": raw_packet,
        "targets": targets,
        "revise_actions": revise_actions,
        "special_actions": special_actions,
        "distractors": distractors,
    }
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def public_evaluator_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "criterion_index": task["criterion_index"],
        "criterion": tuple(task["criterion"]),
        "pair_index": task["pair_index"],
        "pair": tuple(task["pair"]),
        "assets": task["assets"],
        "raw_packet": task["raw_packet"],
        "task_receipt": sha256_bytes(canonical_json(task["raw_packet"])),
    }


def validate_task(task: dict[str, Any]) -> None:
    if task.get("schema_version") != 1 or task.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("invalid OT-0039 task identity")
    rebuilt = build_task(task.get("task_seed", ""))
    if canonical_json(rebuilt) != canonical_json(task):
        raise ValueError("OT-0039 task differs from mechanical derivation")


def selector_route_lineage(task: dict[str, Any]) -> dict[str, Any]:
    selector = initial_snapshot()
    candidate_ledger = DiscrepancyGatedVersionLedger()
    regimes = []
    queries = structural_holdout_batch()
    target_indexes = [
        next(
            index
            for index, asset in enumerate(task["assets"])
            if asset["asset_id"] == target
        )
        for target in task["targets"]
    ]
    for regime_index, orientation in enumerate((0, 1, 0), start=1):
        weights = tuple(task["criterion"])
        if orientation:
            weights = tuple(-value for value in weights)
        rule_id = task["pair"][orientation]
        contact = build_contact(
            f"ot-0039-regime-{regime_index}-contact", weights, rule_id
        )
        source = restore(project(selector))
        completed = complete_encounter(source, contact)
        neutralized, neutralized_receipt = learn(
            source, neutralize_outcome_credit(completed)
        )
        learned, update = learn(source, completed)
        parent = copy.deepcopy(candidate_ledger)
        candidate_ledger, candidate_projection = apply_to_ledger(
            parent, learned, contact, queries
        )
        unchanged_ledger, unchanged_projection = apply_to_ledger(
            parent, source, contact, queries
        )
        outcomes = _rule_outcomes(rule_id)
        candidate_predictions = controller_predictions(candidate_ledger, queries)
        unchanged_predictions = controller_predictions(unchanged_ledger, queries)
        candidate_errors = sum(
            candidate_predictions[index] != outcomes[index]
            for index in target_indexes
        )
        unchanged_errors = sum(
            unchanged_predictions[index] != outcomes[index]
            for index in target_indexes
        )
        regimes.append(
            {
                "index": regime_index,
                "source_snapshot_sha256": source.sha256,
                "learned_snapshot_sha256": learned.sha256,
                "learned_weights": list(learned.weights),
                "changed": source.sha256 != learned.sha256,
                "neutralized_changed": source.sha256 != neutralized.sha256,
                "receipt_identity": learned.parent_sha256 == source.sha256
                and learned.update_receipt_sha256
                == update["learning_receipt_sha256"],
                "completed_receipt_sha256": completed["receipt_sha256"],
                "neutralized_receipt_sha256": neutralized_receipt["receipt_sha256"],
                "candidate_predictions": list(candidate_predictions),
                "unchanged_predictions": list(unchanged_predictions),
                "candidate_target_errors": candidate_errors,
                "unchanged_target_errors": unchanged_errors,
                "candidate_projection_bytes": len(candidate_projection.encode()),
                "unchanged_projection_bytes": len(unchanged_projection.encode()),
            }
        )
        selector = learned
    candidate_errors = [regime["candidate_target_errors"] for regime in regimes]
    unchanged_errors = [regime["unchanged_target_errors"] for regime in regimes]
    body = {
        "regimes": regimes,
        "candidate_route_errors": candidate_errors,
        "unchanged_route_errors": unchanged_errors,
    }
    return {
        **body,
        "pass": candidate_errors == [0, 0, 0]
        and unchanged_errors == [3, 3, 3]
        and all(regime["changed"] for regime in regimes)
        and all(regime["receipt_identity"] for regime in regimes)
        and all(not regime["neutralized_changed"] for regime in regimes)
        and all(
            max(
                regime["candidate_projection_bytes"],
                regime["unchanged_projection_bytes"],
            )
            <= 96
            for regime in regimes
        ),
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def plan_version(step: int) -> int:
    if step < 2:
        return 1
    if step < 4:
        return 2
    return 3


def derived_hierarchy_id(prefix: str, initial_id: str, version: int, step: int) -> str:
    return _token(prefix, (initial_id, version, step))


def expected_hierarchy(
    contract: dict[str, Any], initial_experiment_id: str, initial_subtask_id: str, step: int
) -> dict[str, Any]:
    version = plan_version(step)
    experiment_id = (
        initial_experiment_id
        if version == 1
        else derived_hierarchy_id("exp", initial_experiment_id, version, 0)
    )
    subtask_id = (
        initial_subtask_id
        if step == 0
        else derived_hierarchy_id("sub", initial_subtask_id, version, step)
    )
    completed = step >= 7
    return {
        "goal_id": contract["goal_id"],
        "goal_status": "completed" if completed else "active",
        "plan_version": version,
        "experiment_id": experiment_id,
        "subtask_id": subtask_id,
        "completion_claim": completed,
    }


def true_actions(task: dict[str, Any], lineage: dict[str, Any]) -> tuple[str, ...]:
    asset_by_id = {asset["asset_id"]: asset for asset in task["assets"]}
    repair_actions = []
    for regime, target in zip(lineage["regimes"], task["targets"], strict=True):
        asset = asset_by_id[target]
        index = task["assets"].index(asset)
        repair_actions.append(
            asset["reversible_routes"][regime["candidate_predictions"][index]]
        )
    return (
        "admit-contract",
        repair_actions[0],
        task["revise_actions"][0],
        repair_actions[1],
        task["revise_actions"][1],
        repair_actions[2],
        task["special_actions"]["verify"],
        task["special_actions"]["report"],
    )


def unchanged_actions(task: dict[str, Any], lineage: dict[str, Any]) -> tuple[str, ...]:
    asset_by_id = {asset["asset_id"]: asset for asset in task["assets"]}
    repair_actions = []
    for regime, target in zip(lineage["regimes"], task["targets"], strict=True):
        asset = asset_by_id[target]
        index = task["assets"].index(asset)
        repair_actions.append(
            asset["reversible_routes"][regime["unchanged_predictions"][index]]
        )
    return (
        "admit-contract",
        repair_actions[0],
        task["revise_actions"][0],
        repair_actions[1],
        task["revise_actions"][1],
        repair_actions[2],
        task["special_actions"]["verify"],
        task["special_actions"]["report"],
    )


@dataclass(frozen=True)
class GoalObservation:
    packet: dict[str, Any]
    actor_output: dict[str, Any] | None
    receipt: dict[str, Any]
    admission_valid: bool


class GoalWorld:
    def __init__(self, task: dict[str, Any], lineage: dict[str, Any]):
        self.task = task
        self.lineage = lineage
        self.actions = true_actions(task, lineage)
        self.step = 0
        self.latest_receipt: dict[str, Any] | None = None

    def packet(self, encounter_index: int) -> dict[str, Any]:
        bounded = min(self.step, len(self.actions) - 1)
        correct = self.actions[bounded]
        distractors = [
            action for action in self.task["distractors"] if action != correct
        ][:3]
        available = [correct, *distractors]
        rotation = encounter_index % len(available)
        available = available[rotation:] + available[:rotation]
        packet: dict[str, Any] = {
            "encounter_index": encounter_index,
            "phase": PHASE_NAMES[bounded],
            "latest_world_receipt": self.latest_receipt,
            "available_actions": available,
        }
        if bounded == 0:
            packet["raw_environment"] = self.task["raw_packet"]
        return packet

    def apply(
        self, actor_output: dict[str, Any] | None, admission_valid: bool
    ) -> dict[str, Any]:
        before = self.step
        observed = actor_output.get("action") if isinstance(actor_output, dict) else None
        action_correct = observed == self.actions[before]
        advanced = action_correct and (before != 0 or admission_valid)
        if advanced:
            self.step += 1
        kinds = (
            "contract-admitted",
            "controller-repair+route-model-invalidated",
            "plan-revision-accepted",
            "controller-repair+route-model-invalidated",
            "plan-revision-accepted",
            "controller-repair",
            "independent-end-to-end-verification",
            "status-recorded",
        )
        receipt = {
            "kind": kinds[before] if advanced else "no-progress",
            "advanced": advanced,
            "action_correct": action_correct,
            "goal_complete": self.step >= 7,
            "sealed": True,
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
    def __init__(self, actions: tuple[str, ...], adaptive: bool):
        self.actions = actions
        self.adaptive = adaptive
        self.name = "adaptive-goal-contract" if adaptive else "unchanged-selector"
        self.contract: dict[str, Any] | None = None
        self.initial_experiment_id: str | None = None
        self.initial_subtask_id: str | None = None
        self.step = 0

    def _required_action(self, step: int) -> str:
        return self.actions[min(step, len(self.actions) - 1)]

    def project(self, byte_limit: int) -> str:
        if self.contract is None:
            return "[no admitted goal; inspect the raw environment]"
        assert self.initial_experiment_id is not None
        assert self.initial_subtask_id is not None
        hierarchy = expected_hierarchy(
            self.contract,
            self.initial_experiment_id,
            self.initial_subtask_id,
            self.step,
        )
        body = {
            **hierarchy,
            "targets": self.contract["target_assets"],
            "threshold": self.contract["completion"]["minimum_verified_gain"],
            "constraints": "3-reversible",
            "revise": "route-model-invalidated",
            "surrender": "upper-bound|authority-denied",
            "required_action": self._required_action(self.step),
        }
        text = canonical_json(body).decode()
        if len(text.encode()) > byte_limit:
            raise RuntimeError("OT-0039 durable projection exceeds frozen budget")
        return text

    def observe(self, observation: GoalObservation) -> None:
        if self.contract is not None:
            if observation.receipt.get("advanced"):
                self.step += 1
            return
        if not observation.admission_valid:
            return
        output = observation.actor_output
        if not isinstance(output, dict) or not isinstance(output.get("goal_contract"), dict):
            return
        self.contract = copy.deepcopy(output["goal_contract"])
        self.initial_experiment_id = output["experiment_id"]
        self.initial_subtask_id = output["subtask_id"]
        if observation.receipt.get("advanced"):
            self.step = 1


def substrate_conditions(
    task: dict[str, Any], lineage: dict[str, Any]
) -> dict[str, GoalSubstrate]:
    return {
        "adaptive-goal-contract": DurableGoalContract(
            true_actions(task, lineage), True
        ),
        "no-persistence": NoPersistence(),
        "verbatim-event": VerbatimEvent(),
        "unchanged-selector": DurableGoalContract(
            unchanged_actions(task, lineage), False
        ),
    }


def valid_admission_hierarchy(output: dict[str, Any] | None) -> bool:
    if not isinstance(output, dict) or not isinstance(output.get("goal_contract"), dict):
        return False
    contract = output["goal_contract"]
    return (
        output.get("goal_id") == contract.get("goal_id")
        and output.get("goal_status") == "active"
        and output.get("plan_version") == 1
        and isinstance(output.get("experiment_id"), str)
        and bool(re.fullmatch(r"exp-[0-9a-f]{12}", output["experiment_id"]))
        and isinstance(output.get("subtask_id"), str)
        and bool(re.fullmatch(r"sub-[0-9a-f]{12}", output["subtask_id"]))
        and output.get("completion_claim") is False
    )


def hierarchy_correct(
    contract: dict[str, Any] | None,
    initial_experiment_id: str | None,
    initial_subtask_id: str | None,
    step: int,
    output: dict[str, Any] | None,
) -> bool:
    if step == 0:
        return valid_admission_hierarchy(output)
    if (
        not isinstance(contract, dict)
        or not isinstance(initial_experiment_id, str)
        or not isinstance(initial_subtask_id, str)
        or not isinstance(output, dict)
    ):
        return False
    expected = expected_hierarchy(
        contract, initial_experiment_id, initial_subtask_id, step
    )
    return all(output.get(key) == value for key, value in expected.items())


def admission_score(task: dict[str, Any], output: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(output, dict) or not isinstance(output.get("goal_contract"), dict):
        return {
            "quality_pass": False,
            "ot2_admissible": False,
            "checks": {},
            "receipt_sha256": sha256_bytes(b"invalid-admission"),
        }
    return score_contract(public_evaluator_task(task), output["goal_contract"], "actor-output")


def render_packet(packet: dict[str, Any]) -> str:
    return json.dumps(packet, sort_keys=True, separators=(",", ":"))
