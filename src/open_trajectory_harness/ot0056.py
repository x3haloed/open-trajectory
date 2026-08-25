from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import record_artifact

from .ot0002 import (
    canonical_json,
    child_environment,
    git_output,
    load_json,
    sha256_bytes,
    sha256_file,
)
from .ot0003 import write_sealed_json
from .ot0048 import complete_contact, score, weighted_selections
from .ot0049_world import INITIAL_WEIGHTS


EXPERIMENT_ID = "OT-0056"
ACCEPTANCE_PATH = Path("spec/ot-0056-acceptance.json")
RUN_LOCK_PATH = Path("spec/ot-0056-run-lock.json")
OT55_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0055/ot-0055-descriptive-rule-application-calibration-001.json"
)
OT48_MANIFEST_PATH = Path(
    "evidence/manifests/OT-0048/ot-0048-representation-escape-calibration-001.json"
)
DEFAULT_RUN_ID = "ot-0056-categorical-compression-world-calibration-001"
FLAG_COUNT = 16
CONTACT_PAIRS = 15
CANARY_PAIRS = 8
INHERITANCE_LIMIT = 1024


@dataclass(frozen=True)
class CategoricalSnapshot:
    revision: int
    parent_sha256: str | None
    outcome_receipt_sha256: str
    state: dict[str, Any]
    sha256: str


def fixed_input_paths() -> dict[str, Path]:
    return {
        "acceptance_spec_sha256": ACCEPTANCE_PATH,
        "calibration_harness_sha256": Path("src/open_trajectory_harness/ot0056.py"),
        "entrypoint_sha256": Path("experiments/ot_0056_harness.py"),
        "test_sha256": Path("tests/test_ot0056.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
        "evidence_recorder_sha256": Path("src/open_trajectory_evidence/evidence.py"),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "ot0055_manifest_sha256": OT55_MANIFEST_PATH,
        "ot0048_manifest_sha256": OT48_MANIFEST_PATH,
    }


def _balanced_codes() -> tuple[tuple[int, ...], ...]:
    codes = (
        (0, 0, 0, 0, 1, 1, 1, 1),
        (0, 0, 1, 0, 1, 0, 1, 1),
        (0, 0, 1, 0, 1, 1, 1, 0),
        (0, 0, 1, 1, 0, 1, 0, 1),
        (0, 1, 0, 0, 1, 0, 1, 1),
        (0, 1, 0, 1, 1, 0, 0, 1),
        (0, 1, 0, 1, 1, 0, 1, 0),
        (0, 1, 1, 1, 0, 1, 0, 0),
        (1, 0, 0, 1, 0, 1, 0, 1),
        (1, 0, 0, 1, 0, 1, 1, 0),
        (1, 0, 1, 1, 0, 0, 1, 0),
        (1, 0, 1, 1, 1, 0, 0, 0),
        (1, 1, 0, 0, 0, 1, 0, 1),
        (1, 1, 0, 0, 0, 1, 1, 0),
        (1, 1, 1, 0, 0, 0, 0, 1),
        (1, 1, 1, 0, 1, 0, 0, 0),
    )
    complements = {tuple(1 - value for value in code) for code in codes}
    if (
        len(codes) != FLAG_COUNT
        or len(set(codes)) != FLAG_COUNT
        or any(sum(code) != CANARY_PAIRS // 2 for code in codes)
        or any(
            sum(code[bit] for code in codes) != FLAG_COUNT // 2
            for bit in range(CANARY_PAIRS)
        )
        or any(code in complements for code in codes)
    ):
        raise RuntimeError("OT-0056 balanced code construction is invalid")
    return codes


BALANCED_CODES = _balanced_codes()


def flag_ids(case_index: int) -> tuple[str, ...]:
    return tuple(
        "flag-" + sha256_bytes(f"ot0056:{case_index}:{index}".encode())[:10]
        for index in range(FLAG_COUNT)
    )


def _event(event_id: str, on_flags: list[str]) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "selector_features": [0, 0, 0, 0],
        "on_flags": sorted(on_flags),
    }


def _preferred(pair: dict[str, Any], target: str, polarity: str) -> str:
    desired = polarity == "on"
    return next(
        event["event_id"]
        for event in pair["events"]
        if (target in event["on_flags"]) is desired
    )


def diagnostic_contact(
    flags: tuple[str, ...], target_index: int, polarity: str, regime_index: int
) -> dict[str, Any]:
    target = flags[target_index]
    pairs = []
    for position, diagnostic_index in enumerate(
        index for index in range(FLAG_COUNT) if index != target_index
    ):
        on_a = [flag for index, flag in enumerate(flags) if index != diagnostic_index]
        on_b = [flags[diagnostic_index]]
        pair = {
            "pattern_id": f"r{regime_index}-diagnostic-{position:02d}",
            "diagnostic_flag": flags[diagnostic_index],
            "events": [
                _event(f"r{regime_index}-d{position:02d}-a", on_a),
                _event(f"r{regime_index}-d{position:02d}-b", on_b),
            ],
        }
        pair["preferred_event_id"] = _preferred(pair, target, polarity)
        pairs.append(pair)
    return {"pairs": pairs}


def categorical_canary(
    flags: tuple[str, ...], target_index: int, polarity: str, regime_index: int
) -> dict[str, Any]:
    target = flags[target_index]
    pairs = []
    for bit in range(CANARY_PAIRS):
        on_a = [
            flag for index, flag in enumerate(flags) if BALANCED_CODES[index][bit] == 1
        ]
        on_b = [flag for flag in flags if flag not in on_a]
        pair = {
            "pattern_id": f"r{regime_index}-canary-{bit:02d}",
            "events": [
                _event(f"r{regime_index}-c{bit:02d}-a", on_a),
                _event(f"r{regime_index}-c{bit:02d}-b", on_b),
            ],
        }
        pair["preferred_event_id"] = _preferred(pair, target, polarity)
        pairs.append(pair)
    return {"pairs": pairs}


def build_case(case_index: int) -> dict[str, Any]:
    if case_index not in range(FLAG_COUNT * 2):
        raise ValueError("OT-0056 case index differs")
    flags = flag_ids(case_index)
    first_target = case_index % FLAG_COUNT
    first_polarity = "on" if case_index < FLAG_COUNT else "off"
    third_target = (first_target + 5) % FLAG_COUNT
    regimes_spec = (
        (first_target, first_polarity),
        (first_target, "off" if first_polarity == "on" else "on"),
        (third_target, first_polarity),
    )
    regimes = []
    for offset, (target_index, polarity) in enumerate(regimes_spec):
        index = offset + 1
        regimes.append(
            {
                "index": index,
                "target_flag": flags[target_index],
                "target_index": target_index,
                "polarity": polarity,
                "contact": diagnostic_contact(flags, target_index, polarity, index),
                "canary": categorical_canary(flags, target_index, polarity, index),
            }
        )
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "case_index": case_index,
        "flags": list(flags),
        "regimes": regimes,
    }
    return {**body, "task_sha256": sha256_bytes(canonical_json(body))}


def validate_case(task: dict[str, Any]) -> None:
    if canonical_json(build_case(task.get("case_index", -1))) != canonical_json(task):
        raise ValueError("OT-0056 case differs from mechanical construction")


def public_split(split: dict[str, Any]) -> dict[str, Any]:
    return {
        "pairs": [
            {
                "pattern_id": pair["pattern_id"],
                "events": pair["events"],
            }
            for pair in split["pairs"]
        ]
    }


def _snapshot(
    revision: int,
    parent_sha256: str | None,
    receipt_sha256: str,
    state: dict[str, Any],
) -> CategoricalSnapshot:
    body = {
        "revision": revision,
        "parent_sha256": parent_sha256,
        "outcome_receipt_sha256": receipt_sha256,
        "state": state,
    }
    return CategoricalSnapshot(
        revision=revision,
        parent_sha256=parent_sha256,
        outcome_receipt_sha256=receipt_sha256,
        state=state,
        sha256=sha256_bytes(canonical_json(body)),
    )


def initial_snapshot() -> CategoricalSnapshot:
    receipt = sha256_bytes(canonical_json({"kind": "ot-0056-seed"}))
    return _snapshot(0, None, receipt, {"weights": list(INITIAL_WEIGHTS)})


def reference_snapshot(
    current: CategoricalSnapshot,
    target_flag: str,
    polarity: str,
    receipt: dict[str, Any],
) -> CategoricalSnapshot:
    state = {"description": {"target_flag": target_flag, "polarity": polarity}}
    snapshot = _snapshot(
        current.revision + 1,
        current.sha256,
        receipt["receipt_sha256"],
        state,
    )
    if len(canonical_json(project_snapshot(snapshot))) > INHERITANCE_LIMIT:
        raise ValueError("OT-0056 reference state exceeds inheritance limit")
    return snapshot


def project_snapshot(snapshot: CategoricalSnapshot) -> dict[str, Any]:
    return {
        "revision": snapshot.revision,
        "parent_sha256": snapshot.parent_sha256,
        "outcome_receipt_sha256": snapshot.outcome_receipt_sha256,
        "state": snapshot.state,
        "sha256": snapshot.sha256,
    }


def restore_snapshot(value: dict[str, Any]) -> CategoricalSnapshot:
    if set(value) != {
        "revision",
        "parent_sha256",
        "outcome_receipt_sha256",
        "state",
        "sha256",
    }:
        raise ValueError("OT-0056 snapshot projection authority differs")
    restored = _snapshot(
        value["revision"],
        value["parent_sha256"],
        value["outcome_receipt_sha256"],
        value["state"],
    )
    if restored.sha256 != value["sha256"]:
        raise ValueError("OT-0056 snapshot identity differs")
    if set(restored.state) == {"weights"}:
        if restored.state["weights"] != list(INITIAL_WEIGHTS):
            raise ValueError("OT-0056 seed weights differ")
    elif set(restored.state) == {"description"}:
        description = restored.state["description"]
        if set(description) != {"target_flag", "polarity"} or description[
            "polarity"
        ] not in {"on", "off"}:
            raise ValueError("OT-0056 descriptive state differs")
    else:
        raise ValueError("OT-0056 state shape differs")
    return restored


def snapshot_selections(
    snapshot: CategoricalSnapshot, split: dict[str, Any]
) -> list[str]:
    if "weights" in snapshot.state:
        return weighted_selections(tuple(snapshot.state["weights"]), split)
    description = snapshot.state["description"]
    desired = description["polarity"] == "on"
    target = description["target_flag"]
    return [
        min(
            pair["events"],
            key=lambda event: (
                -int((target in event["on_flags"]) is desired),
                event["event_id"],
            ),
        )["event_id"]
        for pair in split["pairs"]
    ]


def exact_rows(
    contact: dict[str, Any], choices: list[str], receipt: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = []
    for pair, choice, item in zip(
        contact["pairs"], choices, receipt["items"], strict=True
    ):
        rows.append(
            {
                "pair": {
                    "pattern_id": pair["pattern_id"],
                    "events": pair["events"],
                },
                "selected_event_id": choice,
                "success": item["success"],
            }
        )
    return rows


def _projection_bytes(row_bytes: list[int], subset: tuple[int, ...]) -> int:
    return (
        len(b'{"rows":[]}')
        + sum(row_bytes[index] for index in subset)
        + max(0, len(subset) - 1)
    )


def _event_content(event: dict[str, Any]) -> tuple[tuple[int, ...], tuple[str, ...]]:
    return tuple(event["selector_features"]), tuple(event["on_flags"])


def _pair_content(
    pair: dict[str, Any],
) -> tuple[tuple[tuple[int, ...], tuple[str, ...]], ...]:
    return tuple(_event_content(event) for event in pair["events"])


def verbatim_selections(rows: list[dict[str, Any]], split: dict[str, Any]) -> list[str]:
    """Replay only an exact observed pair; use the public fixed tie otherwise."""
    observed = {
        _pair_content(row["pair"]): (
            row["selected_event_id"][-1]
            if row["success"]
            else "b"
            if row["selected_event_id"].endswith("a")
            else "a"
        )
        for row in rows
    }
    choices = []
    for pair in split["pairs"]:
        selected_suffix = observed.get(_pair_content(pair))
        if selected_suffix is None:
            choices.append(min(event["event_id"] for event in pair["events"]))
            continue
        choices.append(
            next(
                event["event_id"]
                for event in pair["events"]
                if event["event_id"].endswith(selected_suffix)
            )
        )
    return choices


def constant_id_selections(split: dict[str, Any], choose_first: bool) -> list[str]:
    return [
        sorted(event["event_id"] for event in pair["events"])[0 if choose_first else 1]
        for pair in split["pairs"]
    ]


def all_real_weight_certificate(split: dict[str, Any]) -> dict[str, Any]:
    feature_deltas = []
    for pair in split["pairs"]:
        left, right = pair["events"]
        feature_deltas.append(
            [
                left_value - right_value
                for left_value, right_value in zip(
                    left["selector_features"],
                    right["selector_features"],
                    strict=True,
                )
            ]
        )
    all_zero = all(delta == [0, 0, 0, 0] for delta in feature_deltas)
    tie_errors = score(split, weighted_selections((0, 0, 0, 0), split))
    body = {
        "feature_deltas": feature_deltas,
        "all_feature_deltas_zero": all_zero,
        "tie_break_errors": tie_errors,
        "all_real_weights_endpoint_equivalent": all_zero,
        "pass": all_zero and tie_errors == 4,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def compression_certificate(
    task: dict[str, Any],
    regime: dict[str, Any],
    rows: list[dict[str, Any]],
    canary: dict[str, Any],
) -> dict[str, Any]:
    row_bytes = [len(canonical_json(row)) for row in rows]
    allowed = []
    for count in range(len(rows) + 1):
        for subset in itertools.combinations(range(len(rows)), count):
            size = _projection_bytes(row_bytes, subset)
            if size <= INHERITANCE_LIMIT:
                allowed.append((subset, size))
    diagnostic_flags = [pair["diagnostic_flag"] for pair in regime["contact"]["pairs"]]
    target = regime["target_flag"]
    flags = task["flags"]
    code_by_flag = {
        flag: tuple(BALANCED_CODES[index]) for index, flag in enumerate(flags)
    }
    minimum_survivors = FLAG_COUNT
    all_nonidentifying = True
    all_diverge = True
    for subset, _ in allowed:
        eliminated = {diagnostic_flags[index] for index in subset}
        survivors = [flag for flag in flags if flag not in eliminated]
        minimum_survivors = min(minimum_survivors, len(survivors))
        all_nonidentifying &= target in survivors and len(survivors) >= 2
        target_code = code_by_flag[target]
        all_diverge &= any(code_by_flag[flag] != target_code for flag in survivors)
    raw_bytes = len(canonical_json({"rows": rows}))
    contact_contents = {_pair_content(row["pair"]) for row in rows}
    no_canary_pair_observed = all(
        _pair_content(pair) not in contact_contents for pair in canary["pairs"]
    )
    full_verbatim_errors = score(canary, verbatim_selections(rows, canary))
    # Exact replay is monotone here: if the complete row set contains no canary
    # pair, no allowed subset can contain one either.
    all_allowed_verbatim_errors_four = (
        no_canary_pair_observed and full_verbatim_errors == 4
    )
    body = {
        "raw_bytes": raw_bytes,
        "row_count": len(rows),
        "minimum_row_bytes": min(row_bytes),
        "maximum_row_bytes": max(row_bytes),
        "allowed_projection_count": len(allowed),
        "maximum_allowed_rows": max(len(subset) for subset, _ in allowed),
        "minimum_surviving_hypotheses": minimum_survivors,
        "all_allowed_nonidentifying": all_nonidentifying,
        "all_allowed_endpoint_divergent": all_diverge,
        "no_canary_pair_observed": no_canary_pair_observed,
        "full_verbatim_errors": full_verbatim_errors,
        "all_allowed_verbatim_errors_four": all_allowed_verbatim_errors_four,
        "pass": raw_bytes > INHERITANCE_LIMIT
        and all_nonidentifying
        and all_diverge
        and all_allowed_verbatim_errors_four,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def evaluate_case(case_index: int) -> dict[str, Any]:
    task = build_case(case_index)
    validate_case(task)
    current = initial_snapshot()
    initial = current
    snapshots = {current.sha256: current}
    first_learned = None
    second_learned = None
    regimes = []
    for regime in task["regimes"]:
        before = current
        contact_choices = snapshot_selections(before, regime["contact"])
        receipt = complete_contact(regime["contact"], contact_choices)
        rows = exact_rows(regime["contact"], contact_choices, receipt)
        canary = regime["canary"]
        certificate = compression_certificate(task, regime, rows, canary)
        corrected = reference_snapshot(
            before, regime["target_flag"], regime["polarity"], receipt
        )
        snapshots[corrected.sha256] = corrected
        parent = restore_snapshot(project_snapshot(snapshots[corrected.parent_sha256]))
        reference_errors = score(canary, snapshot_selections(corrected, canary))
        no_state_errors = score(canary, snapshot_selections(initial, canary))
        digest_errors = no_state_errors
        verbatim_errors = score(canary, verbatim_selections(rows, canary))
        weight_certificate = all_real_weight_certificate(canary)
        fixed_control_errors = {
            "fixed-first": score(canary, constant_id_selections(canary, True)),
            "fixed-second": score(canary, constant_id_selections(canary, False)),
            "fixed-zero-weight": score(
                canary, weighted_selections((0, 0, 0, 0), canary)
            ),
            "fixed-promoted-weight": score(
                canary, weighted_selections(INITIAL_WEIGHTS, canary)
            ),
        }
        pre_errors = score(canary, snapshot_selections(before, canary))
        if regime["index"] == 1:
            first_learned = corrected
        elif regime["index"] == 2:
            second_learned = corrected
        frozen_first_errors = (
            score(canary, snapshot_selections(first_learned, canary))
            if first_learned is not None
            else reference_errors
        )
        frozen_second_errors = (
            score(canary, snapshot_selections(second_learned, canary))
            if second_learned is not None
            else reference_errors
        )
        regimes.append(
            {
                "index": regime["index"],
                "pre_update_errors": pre_errors,
                "reference_errors": reference_errors,
                "no_state_errors": no_state_errors,
                "digest_errors": digest_errors,
                "verbatim_errors": verbatim_errors,
                "frozen_first_errors": frozen_first_errors,
                "frozen_second_errors": frozen_second_errors,
                "all_real_weight_certificate": weight_certificate,
                "fixed_control_errors": fixed_control_errors,
                "reference_bytes": len(canonical_json(project_snapshot(corrected))),
                "compression_certificate": certificate,
                "parent_exact": parent.sha256 == before.sha256,
                "successor_exact": restore_snapshot(project_snapshot(corrected)).sha256
                == corrected.sha256,
                "rollback_errors": score(canary, snapshot_selections(parent, canary)),
                "expected_rollback_errors": pre_errors,
            }
        )
        current = corrected
    body = {
        "case_index": case_index,
        "task_sha256": task["task_sha256"],
        "regimes": regimes,
        "pre_update_errors": [item["pre_update_errors"] for item in regimes],
        "reference_errors": [item["reference_errors"] for item in regimes],
        "no_state_errors": [item["no_state_errors"] for item in regimes],
        "frozen_first_errors": [item["frozen_first_errors"] for item in regimes],
        "frozen_second_errors": [item["frozen_second_errors"] for item in regimes],
    }
    body["pass"] = (
        body["pre_update_errors"][0] == 4
        and body["pre_update_errors"][1] == 8
        and body["pre_update_errors"][2] >= 1
        and body["reference_errors"] == [0, 0, 0]
        and body["no_state_errors"] == [4, 4, 4]
        and body["frozen_first_errors"][1] == 8
        and body["frozen_second_errors"][2] >= 1
        and all(
            item["digest_errors"] == 4
            and item["verbatim_errors"] == 4
            and item["all_real_weight_certificate"]["pass"]
            and all(errors == 4 for errors in item["fixed_control_errors"].values())
            and item["reference_bytes"] <= INHERITANCE_LIMIT
            and item["compression_certificate"]["pass"]
            and item["parent_exact"]
            and item["successor_exact"]
            and item["rollback_errors"] == item["expected_rollback_errors"]
            for item in regimes
        )
    )
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def run_calibration(repo: Path) -> dict[str, Any]:
    acceptance = load_json(repo / ACCEPTANCE_PATH)
    cases = [evaluate_case(index) for index in range(acceptance["scenario_count"])]
    reverse = [
        evaluate_case(index) for index in reversed(range(acceptance["scenario_count"]))
    ]
    reverse_by_index = {item["case_index"]: item for item in reverse}
    order_independent = all(
        canonical_json(
            {key: value for key, value in item.items() if key != "receipt_sha256"}
        )
        == canonical_json(
            {
                key: value
                for key, value in reverse_by_index[item["case_index"]].items()
                if key != "receipt_sha256"
            }
        )
        for item in cases
    )
    body = {
        "case_count": len(cases),
        "passing_case_count": sum(item["pass"] for item in cases),
        "pre_update_error_vectors": sorted(
            {tuple(item["pre_update_errors"]) for item in cases}
        ),
        "reference_error_vectors": sorted(
            {tuple(item["reference_errors"]) for item in cases}
        ),
        "no_state_error_vectors": sorted(
            {tuple(item["no_state_errors"]) for item in cases}
        ),
        "minimum_surviving_hypotheses": min(
            regime["compression_certificate"]["minimum_surviving_hypotheses"]
            for item in cases
            for regime in item["regimes"]
        ),
        "maximum_allowed_rows": max(
            regime["compression_certificate"]["maximum_allowed_rows"]
            for item in cases
            for regime in item["regimes"]
        ),
        "reverse_order_placebo": order_independent,
        "candidate_outputs": False,
        "hosted_model_calls": 0,
        "future_application_authorization": 1,
        "case_receipt_sha256": sha256_bytes(canonical_json(cases)),
    }
    gates = {
        "complete": body["case_count"] == acceptance["scenario_count"]
        and body["passing_case_count"] == acceptance["scenario_count"],
        "hidden_opportunity": body["reference_error_vectors"] == [(0, 0, 0)],
        "old_carrier_failure": body["no_state_error_vectors"] == [(4, 4, 4)],
        "compression": body["minimum_surviving_hypotheses"] >= 2,
        "reverse_order_placebo": order_independent,
        "candidate_free": not body["candidate_outputs"]
        and body["hosted_model_calls"] == 0,
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        **body,
        "gates": gates,
        "disposition": "promoted" if all(gates.values()) else "rejected",
        "pilot_pass": all(gates.values()),
    }


def validate_run_lock(repo: Path, execution: str) -> dict[str, Any]:
    lock = load_json(repo / RUN_LOCK_PATH)
    implementation = lock.get("implementation_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation):
        raise RuntimeError("OT-0056 run lock omits implementation identity")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, execution], cwd=repo
    ).returncode:
        raise RuntimeError("OT-0056 implementation is not an execution ancestor")
    observed = {
        name: sha256_file(repo / path) for name, path in fixed_input_paths().items()
    }
    if observed != lock.get("fixed_inputs"):
        raise RuntimeError("OT-0056 fixed input identity differs")
    protected = [str(path) for path in fixed_input_paths().values()]
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{implementation}..{execution}",
        "--",
        *protected,
    )
    if changed:
        raise RuntimeError(f"OT-0056 implementation changed after lock: {changed}")
    return lock


def run(repo: Path, run_id: str, output: Path) -> tuple[Path, dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0056 execution requires a clean commit")
    execution = git_output(repo, "rev-parse", "HEAD")
    lock = validate_run_lock(repo, execution)
    if output.exists():
        raise RuntimeError("OT-0056 raw output already exists")
    first = run_calibration(repo)
    second = run_calibration(repo)
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
        text=True,
    )
    audit = subprocess.run(
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
        cwd=repo,
        env=child_environment(repo),
        capture_output=True,
        text=True,
    )
    summary = dict(first)
    summary["gates"] = {
        **summary["gates"],
        "deterministic_replay": canonical_json(first) == canonical_json(second),
        "tests": tests.returncode == 0,
        "audit": audit.returncode == 0,
    }
    summary["pilot_pass"] = all(summary["gates"].values())
    summary["disposition"] = "promoted" if summary["pilot_pass"] else "rejected"
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "implementation_git_commit": lock["implementation_git_commit"],
        "execution_git_commit": execution,
        "summary": summary,
        "cases": [
            evaluate_case(index)
            for index in range(load_json(repo / ACCEPTANCE_PATH)["scenario_count"])
        ],
        "verification": {
            "tests_returncode": tests.returncode,
            "tests_stdout_sha256": sha256_bytes(tests.stdout.encode()),
            "tests_stderr_sha256": sha256_bytes(tests.stderr.encode()),
            "audit_returncode": audit.returncode,
            "audit_stdout_sha256": sha256_bytes(audit.stdout.encode()),
            "audit_stderr_sha256": sha256_bytes(audit.stderr.encode()),
        },
    }
    write_sealed_json(output, raw)
    output.chmod(0o600)
    try:
        manifest = record_artifact(
            repo=repo,
            input_path=output,
            experiment_id=EXPERIMENT_ID,
            artifact_id=run_id,
            kind="categorical-compression-world-candidate-free-calibration",
            evidence_class="public-reconstructible",
            recipe="PYTHONPATH=src python3 experiments/ot_0056_harness.py --output $EVIDENCE/runs/OT-0056/ot-0056-categorical-compression-world-calibration-001.json",
            public_url=None,
            limitations=[
                "Candidate output and hosted model calls are forbidden.",
                "Target flags and reference descriptions prove opportunity only and are not candidate evidence.",
                "A pass authorizes at most one OT-0057 application calibration and is not representation escape.",
            ],
            input_manifests=[str(OT55_MANIFEST_PATH), str(OT48_MANIFEST_PATH)],
        )
    finally:
        output.chmod(0)
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0056-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, summary = run(args.repo.resolve(), args.run_id, args.output.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "manifest": str(manifest.relative_to(args.repo.resolve())),
                "summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
