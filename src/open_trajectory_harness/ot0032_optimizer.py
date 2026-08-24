from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .ot0002 import canonical_json, git_output, load_json, sha256_bytes, sha256_file
from .ot0003 import write_sealed_json
from .ot0005_world import deterministic_predictions


EXPERIMENT_ID = "OT-0032"
ACCEPTANCE_PATH = Path("spec/ot-0032-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0032-run-lock.json")
PREDECESSOR_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0031/ot-0031-propose-score-revise-pilot-001.json"
)
SELECTION_LIMIT = 6
PATTERN_COUNT = 16
DEFAULT_RUN_ID = "ot-0032-optimizer-walking-skeleton-001"


@dataclass(frozen=True)
class OptimizerSnapshot:
    revision: int
    parent_sha256: str | None
    proposal_sha256: str
    sha256: str
    patterns: tuple[int, ...]

    def public_identity(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "parent_sha256": self.parent_sha256,
            "proposal_sha256": self.proposal_sha256,
            "sha256": self.sha256,
        }


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "optimizer_core_sha256": Path(
            "src/open_trajectory_harness/ot0032_optimizer.py"
        ),
        "entrypoint_sha256": Path("experiments/ot_0032_harness.py"),
        "predictor_world_sha256": Path(
            "src/open_trajectory_harness/ot0005_world.py"
        ),
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


def _pattern(features: list[int]) -> int:
    if len(features) != 4 or any(value not in (0, 1) for value in features):
        raise ValueError("OT-0032 features are not a four-bit pattern")
    return sum(value << index for index, value in enumerate(features))


def _features(pattern: int) -> list[int]:
    return [(pattern >> index) & 1 for index in range(4)]


def _outcome(features: list[int]) -> int:
    return features[1] ^ features[2] ^ features[3]


def build_split(prefix: str, corrupted_patterns: set[int] | None = None) -> dict[str, Any]:
    corrupted = corrupted_patterns or set()
    queries = [_features(pattern) for pattern in range(PATTERN_COUNT)]
    outcomes = [_outcome(features) for features in queries]
    archive = [
        {
            "event_id": f"{prefix}-event-{pattern}",
            "sequence": pattern,
            "features": list(features),
            "label": outcome ^ (pattern in corrupted),
        }
        for pattern, (features, outcome) in enumerate(zip(queries, outcomes))
    ]
    return {"archive": archive, "queries": queries, "outcomes": outcomes}


def _initial_snapshot() -> OptimizerSnapshot:
    patterns = tuple(range(SELECTION_LIMIT))
    proposal_sha256 = sha256_bytes(canonical_json({"patterns": patterns}))
    identity = {
        "revision": 0,
        "parent_sha256": None,
        "proposal_sha256": proposal_sha256,
        "patterns": patterns,
    }
    return OptimizerSnapshot(
        revision=0,
        parent_sha256=None,
        proposal_sha256=proposal_sha256,
        sha256=sha256_bytes(canonical_json(identity)),
        patterns=patterns,
    )


def _restore(value: dict[str, Any]) -> OptimizerSnapshot:
    if set(value) != {
        "revision",
        "parent_sha256",
        "proposal_sha256",
        "sha256",
        "patterns",
    }:
        raise ValueError("OT-0032 snapshot projection has invalid authority")
    patterns = tuple(value["patterns"])
    if (
        type(value["revision"]) is not int
        or value["revision"] < 0
        or not isinstance(value["parent_sha256"], (str, type(None)))
        or not isinstance(value["proposal_sha256"], str)
        or not isinstance(value["sha256"], str)
        or len(patterns) != SELECTION_LIMIT
        or tuple(sorted(set(patterns))) != patterns
        or any(type(item) is not int or not 0 <= item < PATTERN_COUNT for item in patterns)
    ):
        raise ValueError("OT-0032 snapshot projection is malformed")
    identity = {
        "revision": value["revision"],
        "parent_sha256": value["parent_sha256"],
        "proposal_sha256": value["proposal_sha256"],
        "patterns": patterns,
    }
    if sha256_bytes(canonical_json(identity)) != value["sha256"]:
        raise ValueError("OT-0032 snapshot projection identity differs")
    return OptimizerSnapshot(
        revision=value["revision"],
        parent_sha256=value["parent_sha256"],
        proposal_sha256=value["proposal_sha256"],
        sha256=value["sha256"],
        patterns=patterns,
    )


def _project(snapshot: OptimizerSnapshot) -> dict[str, Any]:
    return {**snapshot.public_identity(), "patterns": list(snapshot.patterns)}


def selected_events(snapshot: OptimizerSnapshot, archive: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pattern = {_pattern(event["features"]): event for event in archive}
    if len(by_pattern) != PATTERN_COUNT:
        raise ValueError("OT-0032 archive does not cover each feature pattern")
    return [by_pattern[pattern] for pattern in snapshot.patterns]


def score_snapshot(snapshot: OptimizerSnapshot, split: dict[str, Any]) -> dict[str, Any]:
    retained = selected_events(snapshot, split["archive"])
    predictions = deterministic_predictions(retained, split["queries"])
    errors = sum(
        prediction != outcome
        for prediction, outcome in zip(predictions, split["outcomes"])
    )
    body = {
        "snapshot_sha256": snapshot.sha256,
        "selected_event_ids_sha256": sha256_bytes(
            canonical_json([event["event_id"] for event in retained])
        ),
        "predictions_sha256": sha256_bytes(canonical_json(predictions)),
        "errors": errors,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def optimize(
    current: OptimizerSnapshot, completed: dict[str, Any]
) -> tuple[OptimizerSnapshot, dict[str, Any]]:
    candidates = []
    for patterns in combinations(range(PATTERN_COUNT), SELECTION_LIMIT):
        proposal_sha256 = sha256_bytes(canonical_json({"patterns": patterns}))
        identity = {
            "revision": current.revision + 1,
            "parent_sha256": current.sha256,
            "proposal_sha256": proposal_sha256,
            "patterns": patterns,
        }
        snapshot = OptimizerSnapshot(
            revision=current.revision + 1,
            parent_sha256=current.sha256,
            proposal_sha256=proposal_sha256,
            sha256=sha256_bytes(canonical_json(identity)),
            patterns=patterns,
        )
        candidates.append((score_snapshot(snapshot, completed)["errors"], patterns, snapshot))
    best_errors, _, best = min(candidates, key=lambda item: (item[0], item[1]))
    current_score = score_snapshot(current, completed)
    body = {
        "source_snapshot_sha256": current.sha256,
        "candidate_count": len(candidates),
        "current_errors": current_score["errors"],
        "best_errors": best_errors,
        "best_proposal_sha256": best.proposal_sha256,
        "committed_snapshot_sha256": best.sha256,
        "changed": best.sha256 != current.sha256,
    }
    return best, {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def control_scores(clean: dict[str, Any], shift: dict[str, Any]) -> dict[str, Any]:
    controls = {
        "earliest": (0, 1, 2, 3, 4, 5),
        "latest": (10, 11, 12, 13, 14, 15),
        "extremes": (0, 1, 2, 13, 14, 15),
        "even": (0, 2, 4, 6, 8, 10),
        "odd": (1, 3, 5, 7, 9, 11),
    }
    result = {}
    initial = _initial_snapshot()
    for name, patterns in controls.items():
        proposal = sha256_bytes(canonical_json({"patterns": patterns}))
        identity = {
            "revision": 0,
            "parent_sha256": None,
            "proposal_sha256": proposal,
            "patterns": patterns,
        }
        snapshot = OptimizerSnapshot(
            revision=0,
            parent_sha256=None,
            proposal_sha256=proposal,
            sha256=sha256_bytes(canonical_json(identity)),
            patterns=patterns,
        )
        clean_errors = score_snapshot(snapshot, clean)["errors"]
        shift_errors = score_snapshot(snapshot, shift)["errors"]
        result[name] = {
            "clean_errors": clean_errors,
            "shift_errors": shift_errors,
            "aggregate_errors": clean_errors + shift_errors,
        }
    result["no_persistence"] = {
        "clean_errors": score_snapshot(initial, clean)["errors"],
        "shift_errors": score_snapshot(initial, shift)["errors"],
        "aggregate_errors": score_snapshot(initial, clean)["errors"]
        + score_snapshot(initial, shift)["errors"],
    }
    return result


def run_protocol() -> dict[str, Any]:
    clean_encounter = build_split("clean-encounter")
    clean_canary = build_split("clean-canary")
    initial = _initial_snapshot()
    initial_score = score_snapshot(initial, clean_encounter)
    learned, clean_update = optimize(initial, clean_encounter)
    projected_learned = _restore(_project(learned))
    clean_canary_score = score_snapshot(projected_learned, clean_canary)

    corrupted = set(projected_learned.patterns)
    shift_encounter = build_split("shift-encounter", corrupted)
    shift_canary = build_split("shift-canary", corrupted)
    contradicted_score = score_snapshot(projected_learned, shift_encounter)
    corrected, shift_update = optimize(projected_learned, shift_encounter)
    projected_corrected = _restore(_project(corrected))
    shift_canary_score = score_snapshot(projected_corrected, shift_canary)
    ablated_shift_score = score_snapshot(projected_learned, shift_canary)
    controls = control_scores(clean_canary, shift_canary)
    best_fixed_aggregate = min(
        item["aggregate_errors"] for item in controls.values()
    )
    candidate_aggregate = clean_canary_score["errors"] + shift_canary_score["errors"]
    acceptance = load_json(ACCEPTANCE_PATH)
    gates = {
        "initial_pressure": initial_score["errors"]
        >= acceptance["minimum_initial_errors"],
        "learned_change": learned.sha256 != initial.sha256,
        "learned_canary": clean_canary_score["errors"]
        <= acceptance["maximum_canary_errors"],
        "later_contradiction": contradicted_score["errors"]
        >= acceptance["minimum_contradicted_errors"],
        "corrected_change": corrected.sha256 != learned.sha256,
        "corrected_canary": shift_canary_score["errors"]
        <= acceptance["maximum_canary_errors"],
        "selector_change_ablation": ablated_shift_score["errors"]
        - shift_canary_score["errors"]
        >= acceptance["minimum_ablation_gap"],
        "fixed_control_margin": best_fixed_aggregate - candidate_aggregate
        >= acceptance["minimum_fixed_control_margin"],
        "candidate_enumeration": clean_update["candidate_count"] == 8008
        and shift_update["candidate_count"] == 8008,
        "fresh_projection_replay": projected_learned == learned
        and projected_corrected == corrected,
        "receipt_identity": all(
            isinstance(receipt["receipt_sha256"], str)
            for receipt in (
                initial_score,
                clean_update,
                clean_canary_score,
                contradicted_score,
                shift_update,
                shift_canary_score,
                ablated_shift_score,
            )
        ),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "claim_limit": acceptance["claim_limit"],
        "initial": {"snapshot": _project(initial), "score": initial_score},
        "learned": {
            "snapshot": _project(learned),
            "update": clean_update,
            "canary": clean_canary_score,
        },
        "contradiction": contradicted_score,
        "corrected": {
            "snapshot": _project(corrected),
            "update": shift_update,
            "canary": shift_canary_score,
        },
        "selector_change_ablation": ablated_shift_score,
        "controls": controls,
        "best_fixed_aggregate_errors": best_fixed_aggregate,
        "candidate_aggregate_errors": candidate_aggregate,
        "gates": gates,
        "pilot_pass": all(gates.values()),
    }


def validate_run_lock(repo: Path, execution_commit: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0032 run lock omits implementation commit")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution_commit],
        cwd=repo,
    ).returncode:
        raise RuntimeError("OT-0032 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0032 fixed input identity differs")
    return lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0032-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0032 execution requires a clean commit")
    execution_commit = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution_commit)
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("OT-0032 output already exists")
    result = run_protocol()
    raw = {
        **result,
        "run_id": args.run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution_commit,
    }
    write_sealed_json(output, raw)
    manifest = record_artifact(
        repo=repo,
        input_path=output,
        experiment_id=EXPERIMENT_ID,
        artifact_id=args.run_id,
        kind="deterministic-learned-selector-walking-skeleton",
        evidence_class="public-reconstructible",
        recipe=(
            "PYTHONPATH=src python3 experiments/ot_0032_harness.py "
            "--output $EVIDENCE/ot-0032-result.json"
        ),
        public_url=None,
        limitations=[
            "This is a deterministic public mechanism feasibility result, not OT-1 evidence.",
            "The optimizer family and public world are researcher-authored; only pattern state is learned.",
            "The result has no E4 or target-promotion authority.",
        ],
        input_manifests=[str(PREDECESSOR_MANIFEST_PATH)],
    )
    print(
        json.dumps(
            {"manifest": str(manifest.relative_to(repo)), "summary": result},
            indent=2,
            sort_keys=True,
        )
    )
    return 0
