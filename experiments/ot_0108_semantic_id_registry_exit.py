from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0107_registry_exit_continuation.py"
BASE_SHA256 = "826b3ada4d21171fbc6c969a5bacdf788f3c7cc641266ff7a691d05bdfbefac9"
RUN_ARCHIVE_SHA256 = "34139f9e1c23c98e682eda7bd5d8db10a0f5632752d488fe22eacf7b448adc50"
AGGREGATE_SHA256 = "ea21bcf1cc92797927ecbcfedef52249d67612bad132494c5273327523f0f4d4"
JOINT_CONTACT_KEYS = {"interface_id", "cases"}
JOINT_CASE_KEYS = {"case_id", "context", "options"}
JOINT_CONTEXT_KEYS = {"risk_penalty", "overload_penalty"}
JOINT_OPTION_KEYS = {"id", "recovery_value", "recovery_risk", "capacity", "overload"}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0107 implementation identity changed")
    name = "ot0108_frozen_ot0107"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base = prior.base


def extract_archive(path: Path, destination: Path) -> Path:
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != "OT-0107" or member.name.startswith("/") or ".." in parts:
                raise RuntimeError("unsafe OT-0107 archive member")
            if member.issym() or member.islnk():
                raise RuntimeError("linked OT-0107 archive member")
        archive.extractall(destination, members=members)
    return destination / "OT-0107"


def load_inputs(p82, repo: Path, store: Path, destination: Path):
    run_manifest, run_path = p82.materialize(repo, store, "OT-0107", "rejected-registry-exit-continuation-run.json")
    aggregate_manifest, aggregate_path = p82.materialize(repo, store, "OT-0107", "registry-exit-continuation-aggregate.json")
    if run_manifest["sha256"] != RUN_ARCHIVE_SHA256 or aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0107 input identity")
    aggregate = json.loads(aggregate_path.read_text())
    raw = extract_archive(run_path, destination)
    artifact = json.loads((raw / "active-joint-contact" / "actor-workspace" / "contact.json").read_text())
    return aggregate, artifact


def finite_number(value: Any, low: float = 0.0, high: float = 200.0) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high


def valid_id(value: Any) -> bool:
    return (isinstance(value, str) and bool(value.strip())) or (isinstance(value, int) and not isinstance(value, bool))


def validate_contact(value: Any) -> tuple[bool, dict[str, bool]]:
    cases = value.get("cases", []) if isinstance(value, dict) else []
    exact = isinstance(value, dict) and set(value) == JOINT_CONTACT_KEYS and value.get("interface_id") == "joint-boundary-probe"
    shapes = bool(exact and len(cases) == 3 and all(
        isinstance(case, dict) and set(case) == JOINT_CASE_KEYS
        and isinstance(case.get("case_id"), str) and bool(case["case_id"].strip())
        and isinstance(case.get("context"), dict) and set(case["context"]) == JOINT_CONTEXT_KEYS
        and all(finite_number(case["context"].get(key), 0, 100) for key in JOINT_CONTEXT_KEYS)
        and isinstance(case.get("options"), list) and len(case["options"]) == 2
        and all(isinstance(option, dict) and set(option) == JOINT_OPTION_KEYS and valid_id(option.get("id"))
                and all(finite_number(option.get(key)) for key in JOINT_OPTION_KEYS - {"id"}) for option in case["options"])
        and type(case["options"][0]["id"]) is type(case["options"][1]["id"])
        and case["options"][0]["id"] != case["options"][1]["id"]
        for case in cases
    ))
    ids_unique = bool(shapes and len({case["case_id"] for case in cases}) == 3)
    cases_unique = bool(shapes and len({base.digest(case) for case in cases}) == 3)
    nonzero = bool(shapes and any(option["recovery_risk"] > 0 and option["overload"] > 0 for case in cases for option in case["options"]))
    winner_flip = near_boundary = False
    if shapes:
        for case in cases:
            oracle = max(case["options"], key=lambda row: (base.joint_score(case["context"], row), row["id"]))
            naive = max(case["options"], key=lambda row: (row["recovery_value"] + row["capacity"], row["id"]))
            scores = sorted((base.joint_score(case["context"], row) for row in case["options"]), reverse=True)
            winner_flip = winner_flip or oracle["id"] != naive["id"]
            near_boundary = near_boundary or 0 < scores[0] - scores[1] <= base.BOUNDARY_WIDTH
    checks = {"exact_shape_and_semantic_ids": shapes, "case_ids_unique": ids_unique, "cases_unique": cases_unique, "nonzero_risk_and_overload": nonzero, "penalty_changes_winner": winner_flip, "near_boundary": near_boundary}
    checks["passed"] = all(checks.values()); return checks["passed"], checks


def score_contact(p82, parent: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    capability = next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == "operations/joint.py")
    namespace: dict[str, Any] = {}; exec(capability["source"], namespace); choose = namespace["choose_joint"]
    rows = []
    for case in artifact["cases"]:
        selected_id = choose(copy.deepcopy(case["context"]), copy.deepcopy(case["options"]))
        oracle = max(case["options"], key=lambda row: (base.joint_score(case["context"], row), row["id"]))
        selected = next((row for row in case["options"] if row["id"] == selected_id), None)
        rows.append({"case_id": case["case_id"], "selected_id": selected_id, "oracle_id": oracle["id"], "selected_score": base.joint_score(case["context"], selected) if selected else None, "oracle_score": base.joint_score(case["context"], oracle), "passed": selected_id == oracle["id"]})
    body = {"authority": "ot-0108-semantic-id-independent-world", "interface_id": "joint-boundary-probe", "contact_digest": p82.digest(artifact), "id_semantics": "nonempty-string-or-integer-consistent-per-case", "rows": rows, "all_cases_passed": bool(rows and all(row["passed"] for row in rows))}
    return {**body, "receipt_digest": p82.digest(body)}


def bind_contact(p82, parent: dict[str, Any], selection: dict[str, Any], artifact: dict[str, Any], aggregate: dict[str, Any]):
    valid, checks = validate_contact(artifact)
    source_audit = aggregate["subject_bound_contact"]["audit"]
    if not (valid and source_audit["trace_regime"]["accepted"] and source_audit["denial_classification_v2"]["accepted"] and source_audit["exact_changes"] and source_audit["truthful"]):
        return None
    body = {"authority": "ot-0108-semantic-id-retained-contact", "source_subject_digest": parent["artifact_digest"], "interface_binding_digest": selection["binding_digest"], "source_actor_patch_digest": source_audit["patch_digest"], "interface_id": "joint-boundary-probe", "contact": artifact, "conformance": checks}
    return {**body, "binding_digest": p82.digest(body)}


def fixture_conformance(p82, parent: dict[str, Any], aggregate: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    integer_valid, _ = validate_contact(artifact)
    strings = copy.deepcopy(artifact)
    for case in strings["cases"]:
        for option in case["options"]: option["id"] = str(option["id"])
    string_valid, _ = validate_contact(strings)
    mixed = copy.deepcopy(artifact); mixed["cases"][0]["options"][0]["id"] = "1"
    mixed_valid, _ = validate_contact(mixed)
    boolean = copy.deepcopy(artifact); boolean["cases"][0]["options"][0]["id"] = True; boolean["cases"][0]["options"][1]["id"] = False
    boolean_valid, _ = validate_contact(boolean)
    score = score_contact(p82, parent, artifact) if integer_valid else {"all_cases_passed": False}
    result = {"source_rejected": not aggregate["operational_transition_passed"], "source_subject_unchanged": aggregate["final_subject_digest"] == parent["artifact_digest"], "integer_ids_valid": integer_valid, "string_ids_valid": string_valid, "mixed_ids_rejected": not mixed_valid, "boolean_ids_rejected": not boolean_valid, "exact_integer_contact_scored": score["all_cases_passed"]}
    result["passed"] = all(result.values()); return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0108").resolve()
    prior92 = base.mechanism.load_prior(); _, _, prior89, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store); parent = prior.load_parent(p82, repo, store)
    if parent["artifact_digest"] != prior.PARENT_DIGEST or not runtime.identity_conforms(parent): raise SystemExit("wrong OT-0106 parent")
    with tempfile.TemporaryDirectory() as directory: aggregate, artifact = load_inputs(p82, repo, store, Path(directory))
    fixtures = fixture_conformance(p82, parent, aggregate, artifact); selection = prior.extract_action(p82, parent); binding = bind_contact(p82, parent, selection, artifact, aggregate) if selection else None
    if args.preflight_only:
        result = {"parent_digest": parent["artifact_digest"], "base_implementation_sha256": BASE_SHA256, "run_archive_sha256": RUN_ARCHIVE_SHA256, "aggregate_sha256": AGGREGATE_SHA256, "fixture_conformance": fixtures, "retained_contact_binding_digest": binding["binding_digest"] if binding else None}
        print(json.dumps(result, indent=2, sort_keys=True)); return 0 if fixtures["passed"] and binding else 2
    if run.exists(): raise SystemExit("preserve existing OT-0108 evidence")
    run.mkdir(parents=True); (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True)+"\n")
    if not fixtures["passed"] or not binding: raise SystemExit("pre-actor conformance failed")
    world = score_contact(p82, parent, artifact); contact = {"binding": binding, "world": world, "admitted": world["all_cases_passed"]}
    (run / "bound-retained-contact.json").write_text(json.dumps(binding, indent=2, sort_keys=True)+"\n"); (run / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True)+"\n")
    context = prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); position = base.active_position(parent); started = time.time()
    assimilation = prior.run_assimilation(prior89, p82, context, run, "active-assimilation", parent, position, prior.active_history(parent), contact)
    current = parent; promotion = None
    if assimilation["binding"]: current, promotion = prior.promote(p82, parent, selection, binding, assimilation["binding"])
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open")
    extension_selected = bool(operational and assimilation["binding"]["continuation_action"]["action_kind"] == "registry-extension")
    control = None
    if operational: (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True)+"\n")
    if extension_selected: control = prior.run_assimilation(prior89, p82, context, run, "history-erased-assimilation", parent, position, prior.erased_history(p82, parent), contact)
    control_extension = bool(control and control["binding"] and control["binding"]["continuation_action"]["action_kind"] == "registry-extension")
    result = {"authority": "ot-0108-semantic-id-registry-exit-driver", "source_subject_digest": parent["artifact_digest"], "retained_contact_binding": binding, "world_receipt": world, "active_assimilation": p82.compact(assimilation), "promotion_receipt": promotion, "history_erased_control": p82.compact(control) if control else None, "operational_transition_passed": operational, "registry_extension_selected": extension_selected, "history_erased_selected_extension": control_extension, "observer_disposition": "promoted" if operational else "rejected", "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost", "final_subject_digest": current["artifact_digest"], "continuation_action": current["actor_originated_pursuit_openings"][-1].get("continuation_action"), "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time()-started,3)}
    result["receipt_digest"] = p82.digest(result); (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n"); (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True)+"\n"); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
