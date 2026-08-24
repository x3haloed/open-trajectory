from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .ot0002 import canonical_json, git_output, load_json, sha256_bytes, sha256_file
from .ot0003 import write_sealed_json


EXPERIMENT_ID = "OT-0033"
ACCEPTANCE_PATH = Path("spec/ot-0033-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0033-run-lock.json")
PREDECESSOR_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0032/ot-0032-optimizer-walking-skeleton-001.json"
)
DIMENSION_COUNT = 4
DIRECTIONS = tuple(
    direction
    for direction in product((-1, 0, 1), repeat=DIMENSION_COUNT)
    if any(direction)
)
PATTERN_COUNT = len(DIRECTIONS)
SELECTION_LIMIT = PATTERN_COUNT
MAX_EPOCHS = 1_000
MAX_ABSOLUTE_WEIGHT = 10_000
DEFAULT_RUN_ID = "ot-0033-blind-weighted-selector-001"


@dataclass(frozen=True)
class WeightedSelectorSnapshot:
    revision: int
    parent_sha256: str | None
    update_receipt_sha256: str
    sha256: str
    weights: tuple[int, ...]

    def public_identity(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "parent_sha256": self.parent_sha256,
            "update_receipt_sha256": self.update_receipt_sha256,
            "sha256": self.sha256,
        }


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "weighted_selector_core_sha256": Path(
            "src/open_trajectory_harness/ot0033_weighted_selector.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0033_harness.py"),
        "controller_core_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_evidence_io_sha256": Path(
            "src/open_trajectory_harness/ot0003.py"
        ),
        "evidence_recorder_sha256": Path(
            "src/open_trajectory_evidence/evidence.py"
        ),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "predecessor_manifest_sha256": PREDECESSOR_MANIFEST_PATH,
    }


def _dot(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    return sum(a * b for a, b in zip(left, right, strict=True))


def expected_task_seed(implementation_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise ValueError("OT-0033 implementation identity is malformed")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "implementation_git_commit": implementation_commit,
                "purpose": "post-implementation-controller-task",
            }
        )
    )


def _hidden_weights(task_seed: str) -> tuple[int, ...]:
    if not re.fullmatch(r"[0-9a-f]{64}", task_seed):
        raise ValueError("OT-0033 task seed is malformed")
    digest = hashlib.sha256(bytes.fromhex(task_seed)).digest()
    dimension_order = sorted(range(DIMENSION_COUNT), key=lambda index: digest[index])
    magnitudes = (1, 5, 25, 125)
    weights = [0] * DIMENSION_COUNT
    for rank, dimension in enumerate(dimension_order):
        sign = 1 if digest[DIMENSION_COUNT + dimension] & 1 else -1
        weights[dimension] = sign * magnitudes[rank]
    return tuple(weights)


def _outcome(prefix: str, pattern_id: int) -> int:
    identity = canonical_json({"prefix": prefix, "pattern_id": pattern_id})
    return int(sha256_bytes(identity)[0], 16) % 2


def build_split(
    prefix: str, hidden_weights: tuple[int, ...]
) -> dict[str, Any]:
    archive = []
    outcomes = []
    for pattern_id, direction in enumerate(DIRECTIONS):
        outcome = _outcome(prefix, pattern_id)
        a_correct = _dot(hidden_weights, direction) > 0
        for variant, selector_features, correct in (
            ("a", direction, a_correct),
            ("b", tuple(-value for value in direction), not a_correct),
        ):
            archive.append(
                {
                    "event_id": f"{prefix}-pattern-{pattern_id:03d}-{variant}",
                    "pattern_id": pattern_id,
                    "selector_features": list(selector_features),
                    "label": outcome if correct else 1 - outcome,
                }
            )
        outcomes.append({"pattern_id": pattern_id, "outcome": outcome})
    return {"archive": archive, "outcomes": outcomes}


def build_task(task_seed: str) -> dict[str, Any]:
    initial = _hidden_weights(task_seed)
    regimes = (initial, tuple(-value for value in initial), initial)
    return {
        "task_sha256": sha256_bytes(
            canonical_json(
                [
                    {
                        "contact": build_split(f"regime-{index}-contact", weights),
                        "canary": build_split(f"regime-{index}-canary", weights),
                    }
                    for index, weights in enumerate(regimes, start=1)
                ]
            )
        ),
        "regimes": [
            {
                "contact": build_split(f"regime-{index}-contact", weights),
                "canary": build_split(f"regime-{index}-canary", weights),
            }
            for index, weights in enumerate(regimes, start=1)
        ],
    }


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    update_receipt_sha256: str,
    weights: tuple[int, ...],
) -> WeightedSelectorSnapshot:
    identity = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "update_receipt_sha256": update_receipt_sha256,
        "weights": weights,
    }
    return WeightedSelectorSnapshot(
        revision=revision,
        parent_sha256=parent_sha256,
        update_receipt_sha256=update_receipt_sha256,
        sha256=sha256_bytes(canonical_json(identity)),
        weights=weights,
    )


def initial_snapshot() -> WeightedSelectorSnapshot:
    weights = (0,) * DIMENSION_COUNT
    receipt = sha256_bytes(canonical_json({"kind": "neutral-seed", "weights": weights}))
    return _snapshot(0, None, receipt, weights)


def project(snapshot: WeightedSelectorSnapshot) -> dict[str, Any]:
    return {**snapshot.public_identity(), "weights": list(snapshot.weights)}


def restore(value: dict[str, Any]) -> WeightedSelectorSnapshot:
    if set(value) != {
        "revision",
        "parent_sha256",
        "update_receipt_sha256",
        "sha256",
        "weights",
    }:
        raise ValueError("OT-0033 snapshot projection has invalid authority")
    weights = tuple(value["weights"])
    if (
        type(value["revision"]) is not int
        or value["revision"] < 0
        or not isinstance(value["parent_sha256"], (str, type(None)))
        or not isinstance(value["update_receipt_sha256"], str)
        or not isinstance(value["sha256"], str)
        or len(weights) != DIMENSION_COUNT
        or any(
            type(weight) is not int or abs(weight) > MAX_ABSOLUTE_WEIGHT
            for weight in weights
        )
    ):
        raise ValueError("OT-0033 snapshot projection is malformed")
    snapshot = _snapshot(
        value["revision"],
        value["parent_sha256"],
        value["update_receipt_sha256"],
        weights,
    )
    if snapshot.sha256 != value["sha256"]:
        raise ValueError("OT-0033 snapshot projection identity differs")
    return snapshot


def _pairs(archive: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for event in archive:
        pattern_id = event.get("pattern_id")
        features = event.get("selector_features")
        if (
            type(pattern_id) is not int
            or not 0 <= pattern_id < PATTERN_COUNT
            or not isinstance(event.get("event_id"), str)
            or not isinstance(features, list)
            or len(features) != DIMENSION_COUNT
            or any(type(value) is not int or value not in (-1, 0, 1) for value in features)
            or event.get("label") not in (0, 1)
        ):
            raise ValueError("OT-0033 archive event is malformed")
        grouped.setdefault(pattern_id, []).append(event)
    if set(grouped) != set(range(PATTERN_COUNT)):
        raise ValueError("OT-0033 archive does not cover every pattern")
    result = []
    for pattern_id in range(PATTERN_COUNT):
        pair = sorted(grouped[pattern_id], key=lambda event: event["event_id"])
        if (
            len(pair) != 2
            or pair[0]["selector_features"]
            != [-value for value in pair[1]["selector_features"]]
            or pair[0]["label"] == pair[1]["label"]
        ):
            raise ValueError("OT-0033 archive pair is malformed")
        result.append((pair[0], pair[1]))
    return result


def select_events(
    snapshot: WeightedSelectorSnapshot, archive: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    selected = []
    for first, second in _pairs(archive):
        selected.append(
            min(
                (first, second),
                key=lambda event: (
                    -_dot(snapshot.weights, tuple(event["selector_features"])),
                    event["event_id"],
                ),
            )
        )
    return selected


def _outcome_map(outcomes: list[dict[str, Any]]) -> dict[int, int]:
    result = {}
    for item in outcomes:
        if (
            set(item) != {"pattern_id", "outcome"}
            or type(item["pattern_id"]) is not int
            or not 0 <= item["pattern_id"] < PATTERN_COUNT
            or item["outcome"] not in (0, 1)
            or item["pattern_id"] in result
        ):
            raise ValueError("OT-0033 outcomes are malformed")
        result[item["pattern_id"]] = item["outcome"]
    if set(result) != set(range(PATTERN_COUNT)):
        raise ValueError("OT-0033 outcomes do not cover every pattern")
    return result


def score_snapshot(
    snapshot: WeightedSelectorSnapshot, split: dict[str, Any]
) -> dict[str, Any]:
    outcomes = _outcome_map(split["outcomes"])
    selected = select_events(snapshot, split["archive"])
    decisions = [
        {
            "pattern_id": event["pattern_id"],
            "selected_event_id": event["event_id"],
            "prediction": event["label"],
            "error": event["label"] != outcomes[event["pattern_id"]],
        }
        for event in selected
    ]
    body = {
        "snapshot_sha256": snapshot.sha256,
        "selected_event_ids_sha256": sha256_bytes(
            canonical_json([item["selected_event_id"] for item in decisions])
        ),
        "predictions_sha256": sha256_bytes(
            canonical_json([item["prediction"] for item in decisions])
        ),
        "errors": sum(item["error"] for item in decisions),
    }
    return {
        **body,
        "decisions": decisions,
        "receipt_sha256": sha256_bytes(canonical_json(body)),
    }


def complete_encounter(
    snapshot: WeightedSelectorSnapshot, split: dict[str, Any]
) -> dict[str, Any]:
    score = score_snapshot(snapshot, split)
    body = {
        "source_snapshot_sha256": snapshot.sha256,
        "outcome_credit": True,
        "archive": split["archive"],
        "outcomes": split["outcomes"],
        "decisions": score["decisions"],
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def neutralize_outcome_credit(completed: dict[str, Any]) -> dict[str, Any]:
    body = {
        "source_snapshot_sha256": completed["source_snapshot_sha256"],
        "outcome_credit": False,
        "archive": completed["archive"],
        "outcomes": [],
        "decisions": [
            {
                "pattern_id": decision["pattern_id"],
                "selected_event_id": decision["selected_event_id"],
                "prediction": decision["prediction"],
            }
            for decision in completed["decisions"]
        ],
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def learn(
    current: WeightedSelectorSnapshot, completed: dict[str, Any]
) -> tuple[WeightedSelectorSnapshot, dict[str, Any]]:
    body = {key: value for key, value in completed.items() if key != "receipt_sha256"}
    if sha256_bytes(canonical_json(body)) != completed.get("receipt_sha256"):
        raise ValueError("OT-0033 completed encounter receipt differs")
    if completed.get("source_snapshot_sha256") != current.sha256:
        raise ValueError("OT-0033 completed encounter has the wrong source")
    if completed.get("outcome_credit") is False:
        if completed.get("outcomes"):
            raise ValueError("OT-0033 neutralized credit contains outcomes")
        selected = select_events(current, completed["archive"])
        expected_decisions = [
            {
                "pattern_id": event["pattern_id"],
                "selected_event_id": event["event_id"],
                "prediction": event["label"],
            }
            for event in selected
        ]
        if completed.get("decisions") != expected_decisions:
            raise ValueError("OT-0033 neutralized decisions differ")
        receipt_body = {
            "source_snapshot_sha256": current.sha256,
            "completed_receipt_sha256": completed["receipt_sha256"],
            "training_examples": 0,
            "epochs": 0,
            "changed": False,
            "committed_snapshot_sha256": current.sha256,
        }
        return current, {
            **receipt_body,
            "receipt_sha256": sha256_bytes(canonical_json(receipt_body)),
        }
    if completed.get("outcome_credit") is not True:
        raise ValueError("OT-0033 outcome-credit authority is malformed")

    outcomes = _outcome_map(completed["outcomes"])
    expected_score = score_snapshot(
        current,
        {"archive": completed["archive"], "outcomes": completed["outcomes"]},
    )
    if completed.get("decisions") != expected_score["decisions"]:
        raise ValueError("OT-0033 released decisions differ from replay")
    selected_by_pattern = {
        item["pattern_id"]: item for item in completed["decisions"]
    }
    pairs = _pairs(completed["archive"])
    if set(selected_by_pattern) != set(range(PATTERN_COUNT)):
        raise ValueError("OT-0033 decision projection is malformed")
    examples = []
    for pattern_id, pair in enumerate(pairs):
        decision = selected_by_pattern[pattern_id]
        selected = next(
            (event for event in pair if event["event_id"] == decision["selected_event_id"]),
            None,
        )
        if selected is None:
            raise ValueError("OT-0033 decision selected an unknown event")
        other = pair[1] if selected is pair[0] else pair[0]
        outcome = outcomes[pattern_id]
        if (
            decision.get("prediction") != selected["label"]
            or decision.get("error") is not (selected["label"] != outcome)
            or {selected["label"], other["label"]} != {0, 1}
        ):
            raise ValueError("OT-0033 decision consequence differs")
        preferred = other if decision["error"] else selected
        rejected = selected if decision["error"] else other
        examples.append(
            tuple(
                preferred_value - rejected_value
                for preferred_value, rejected_value in zip(
                    preferred["selector_features"],
                    rejected["selector_features"],
                    strict=True,
                )
            )
        )

    weights = list(current.weights)
    epochs = 0
    for epochs in range(1, MAX_EPOCHS + 1):
        mistakes = 0
        for difference in examples:
            if _dot(tuple(weights), difference) <= 0:
                weights = [
                    weight + delta
                    for weight, delta in zip(weights, difference, strict=True)
                ]
                mistakes += 1
        if mistakes == 0:
            break
    else:
        raise RuntimeError("OT-0033 learner did not converge")
    learned_weights = tuple(weights)
    if any(abs(weight) > MAX_ABSOLUTE_WEIGHT for weight in learned_weights):
        raise RuntimeError("OT-0033 learned weights exceed the carrier")
    receipt_body = {
        "source_snapshot_sha256": current.sha256,
        "completed_receipt_sha256": completed["receipt_sha256"],
        "training_examples": len(examples),
        "epochs": epochs,
        "weights_sha256": sha256_bytes(canonical_json(learned_weights)),
    }
    update_receipt = sha256_bytes(canonical_json(receipt_body))
    learned = _snapshot(
        current.revision + 1,
        current.sha256,
        update_receipt,
        learned_weights,
    )
    final_body = {
        **receipt_body,
        "learning_receipt_sha256": update_receipt,
        "changed": learned.sha256 != current.sha256,
        "committed_snapshot_sha256": learned.sha256,
    }
    return learned, {
        **final_body,
        "receipt_sha256": sha256_bytes(canonical_json(final_body)),
    }


def _control_snapshot(name: str, weights: tuple[int, ...]) -> WeightedSelectorSnapshot:
    receipt = sha256_bytes(canonical_json({"control": name, "weights": weights}))
    return _snapshot(0, None, receipt, weights)


def run_protocol(task_seed: str) -> dict[str, Any]:
    acceptance = load_json(ACCEPTANCE_PATH)
    task = build_task(task_seed)
    current = initial_snapshot()
    regimes = []
    learned_snapshots = []
    for index, regime in enumerate(task["regimes"], start=1):
        source = restore(project(current))
        contact_score = score_snapshot(source, regime["contact"])
        completed = complete_encounter(source, regime["contact"])
        neutralized, neutralized_update = learn(
            source, neutralize_outcome_credit(completed)
        )
        learned, update = learn(source, completed)
        restored = restore(project(learned))
        canary_score = score_snapshot(restored, regime["canary"])
        unchanged_score = score_snapshot(source, regime["canary"])
        regimes.append(
            {
                "index": index,
                "source_snapshot": project(source),
                "contact_score": contact_score,
                "completed_receipt_sha256": completed["receipt_sha256"],
                "neutralized_update": neutralized_update,
                "neutralized_snapshot_sha256": neutralized.sha256,
                "learned_snapshot": project(learned),
                "update": update,
                "canary_score": canary_score,
                "unchanged_canary_score": unchanged_score,
            }
        )
        learned_snapshots.append(learned)
        current = learned

    controls = {
        "zero": _control_snapshot("zero", (0, 0, 0, 0)),
        **{
            f"axis-{dimension}-{sign_name}": _control_snapshot(
                f"axis-{dimension}-{sign_name}",
                tuple(
                    sign if index == dimension else 0
                    for index in range(DIMENSION_COUNT)
                ),
            )
            for dimension in range(DIMENSION_COUNT)
            for sign_name, sign in (("positive", 1), ("negative", -1))
        },
        **{
            f"learned-revision-{index}": snapshot
            for index, snapshot in enumerate(learned_snapshots, start=1)
        },
    }
    control_scores = {}
    for name, snapshot in controls.items():
        errors = [
            score_snapshot(snapshot, regime["canary"])["errors"]
            for regime in task["regimes"]
        ]
        control_scores[name] = {
            "regime_errors": errors,
            "aggregate_errors": sum(errors),
        }
    candidate_aggregate = sum(regime["canary_score"]["errors"] for regime in regimes)
    best_fixed_aggregate = min(
        control["aggregate_errors"] for control in control_scores.values()
    )
    gates = {
        "task_shape": PATTERN_COUNT == acceptance["pattern_count"]
        and SELECTION_LIMIT == acceptance["selection_limit"]
        and len(regimes) == acceptance["regime_count"],
        "initial_pressure": regimes[0]["contact_score"]["errors"]
        >= acceptance["minimum_initial_errors"],
        "learned_change": all(
            regime["learned_snapshot"]["sha256"]
            != regime["source_snapshot"]["sha256"]
            for regime in regimes
        ),
        "fresh_canaries": all(
            regime["canary_score"]["errors"]
            <= acceptance["maximum_canary_errors"]
            for regime in regimes
        ),
        "later_contradictions": all(
            regime["contact_score"]["errors"]
            >= acceptance["minimum_later_contradiction_errors"]
            for regime in regimes[1:]
        ),
        "selector_change_ablation": all(
            regime["unchanged_canary_score"]["errors"]
            - regime["canary_score"]["errors"]
            >= acceptance["minimum_selector_change_ablation_gap"]
            for regime in regimes
        ),
        "outcome_credit_ablation": all(
            not regime["neutralized_update"]["changed"]
            and regime["neutralized_snapshot_sha256"]
            == regime["source_snapshot"]["sha256"]
            for regime in regimes
        ),
        "fixed_control_margin": best_fixed_aggregate - candidate_aggregate
        >= acceptance["minimum_fixed_control_margin"],
        "fresh_projection_replay": all(
            restore(regime["learned_snapshot"]).sha256
            == regime["learned_snapshot"]["sha256"]
            for regime in regimes
        ),
        "receipt_identity": all(
            isinstance(regime["completed_receipt_sha256"], str)
            and isinstance(regime["update"]["receipt_sha256"], str)
            and isinstance(regime["canary_score"]["receipt_sha256"], str)
            and regime["learned_snapshot"]["update_receipt_sha256"]
            == regime["update"]["learning_receipt_sha256"]
            for regime in regimes
        ),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "task_sha256": task["task_sha256"],
        "task_seed_sha256": sha256_bytes(task_seed.encode()),
        "candidate_visible_authority": [
            "paired_raw_events",
            "source_snapshot",
            "prior_selections",
            "released_completed_outcomes",
        ],
        "regimes": regimes,
        "controls": control_scores,
        "candidate_aggregate_errors": candidate_aggregate,
        "best_fixed_aggregate_errors": best_fixed_aggregate,
        "gates": gates,
        "pilot_pass": all(gates.values()),
    }


def validate_run_lock(repo: Path, execution_commit: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0033 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0033 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0033 fixed input identity differs")
    task_seed = lock.get("task_seed", "")
    if task_seed != expected_task_seed(implementation):
        raise RuntimeError("OT-0033 task seed is not mechanically derived")
    if build_task(task_seed)["task_sha256"] != lock.get("task_sha256"):
        raise RuntimeError("OT-0033 controller task identity differs")
    return lock


def record_sealed_result(repo: Path, output: Path, run_id: str) -> Path:
    output.chmod(0o600)
    try:
        return record_artifact(
            repo=repo,
            input_path=output,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="blind-consequence-trained-weighted-selector",
            evidence_class="public-reconstructible",
            recipe=(
                "PYTHONPATH=src python3 experiments/ot_0033_harness.py "
                "--output $EVIDENCE/ot-0033-result.json"
            ),
            public_url=None,
            limitations=[
                "This is public selector-mechanism feasibility, not OT-1 evidence.",
                "The carrier, learner, and task family remain researcher-authored.",
                "The result has no evaluation-epoch or target-promotion authority.",
            ],
            input_manifests=[str(PREDECESSOR_MANIFEST_PATH)],
        )
    finally:
        output.chmod(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0033-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0033 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("OT-0033 output already exists")
    result = run_protocol(lock["task_seed"])
    raw = {
        **result,
        "run_id": args.run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
    }
    write_sealed_json(output, raw)
    manifest = record_sealed_result(repo, output, args.run_id)
    print(
        json.dumps(
            {"manifest": str(manifest.relative_to(repo)), "summary": result},
            indent=2,
            sort_keys=True,
        )
    )
    return 0
