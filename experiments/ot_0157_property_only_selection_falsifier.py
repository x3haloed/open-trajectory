from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0156_exact_corrected_extension_reuse.py"
BASE_SHA256 = "04e8a95674d9d9cf87cbce74bcfcc4a69a1bef76d0cb633061a5a32d1f7195e7"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"

COMPATIBILITY_CASES = [
    {"case_id": "selection-a", "before": "program-v20", "after": "program-v21", "compatible": True, "options": ["reuse", "verify", "drop"], "blocked": ["drop"], "expected": ["reuse", "verify"]},
    {"case_id": "selection-b", "before": "memory-v22", "after": "memory-v22", "compatible": False, "options": ["continue", "audit"], "blocked": [], "expected": []},
    {"case_id": "selection-c", "before": "route-v23", "after": "route-v23", "options": ["left", "right", "blocked"], "blocked": ["blocked"], "expected": ["left", "right"]},
]
RESET_CASES = [{"case_id": "selection-reset-a", "signal": "corrected-extension-bytes"}, {"case_id": "selection-reset-b", "signal": "compatibility-receipts"}, {"case_id": "selection-reset-c", "signal": "accumulated-floor"}]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0156 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0157_frozen_ot0156", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
extension_base = previous.extension_base
worlds = previous.worlds
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def bind_stake(p82, subject: dict[str, Any], stake: dict[str, Any]) -> dict[str, Any]:
    body = {"authority": "ot-0157-bound-carried-stake", "source_subject_digest": subject["artifact_digest"], "stake": stake}
    return {**body, "binding_digest": p82.digest(body)}


def endpoint(reset: dict[str, Any], compatibility: dict[str, Any], floor: dict[str, Any]) -> dict[str, Any]:
    checks = {"reset_available": reset["passed"] and reset["pass_count"] == 3, "compatibility_3_of_3": compatibility["passed"] and compatibility["pass_count"] == 3, "accumulated_floor_18_of_18": floor["passed"] and floor["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0157").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    extension = parent["developmental_property_extensions"][0]
    operation = extension_base.load_operation(extension["operation_source"])
    reset_result = worlds.evaluate("continuity-under-reset", worlds.SURFACES["continuity-under-reset"]["passing_policy"], RESET_CASES)
    compatibility_result = extension_base.evaluate(operation, COMPATIBILITY_CASES)
    floor_result = extension_base.evaluate(operation, previous.accumulated_floor())
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open", "stake_names_reset_and_extension_floor": parent["active_developmental_stake"]["property"] == "continuity-under-reset" and "corrected extension" in parent["active_developmental_stake"]["question"] and "18" in parent["active_developmental_stake"]["success_condition"], "both_mechanisms_executable": reset_result["passed"] and compatibility_result["passed"] and floor_result["passed"], "parent_identity": runtime.identity_conforms(parent)}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0157 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    binding = bind_stake(p82, parent, parent["active_developmental_stake"])
    selected_route = worlds.compile_route(p82, parent, binding, worlds.catalog(p82))
    reset_compatibility = {"passed": False, "pass_count": 0, "case_count": 3, "reason": "reset-carrier has no compatibility operation"}
    reset_floor = {"passed": False, "pass_count": 0, "case_count": 18, "reason": "reset-carrier does not execute accumulated floor"}
    selected_endpoint = endpoint(reset_result, reset_compatibility, reset_floor)
    extension_endpoint = endpoint(reset_result, compatibility_result, floor_result)
    erased = copy.deepcopy(binding); erased["stake"].pop("property", None)
    erased_route = worlds.compile_route(p82, parent, erased, worlds.catalog(p82))
    changed_stake = copy.deepcopy(parent["active_developmental_stake"]); changed_stake["property"] = extension["property"]["property"]
    changed_route = extension_base.extended_route(p82, parent, changed_stake)
    checks = {"property_compiler_selects_reset": selected_route["selected_surface"]["surface_id"] == "reset-carrier", "selected_reset_passes_transport": reset_result["passed"] and reset_result["pass_count"] == 3, "selected_reset_fails_full_stake": not selected_endpoint["passed"], "corrected_extension_passes_full_stake": extension_endpoint["passed"], "property_erasure_blocks_fixed_route": erased_route is None, "property_change_selects_extension": bool(changed_route and changed_route["extension_binding_digest"] == extension["binding_digest"]), "subject_unchanged_sounding_open": runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0157-property-only-selection-falsifier", "source_subject_digest": parent["artifact_digest"], "stake_binding": binding, "selected_route": selected_route, "selected_mechanism": {"reset": reset_result, "compatibility": reset_compatibility, "floor": reset_floor, "endpoint": selected_endpoint}, "available_corrected_extension": {"reset": reset_result, "compatibility": compatibility_result, "floor": floor_result, "endpoint": extension_endpoint}, "controls": {"property_erased_route": erased_route, "changed_property_route": changed_route}, "checks": checks, "property_only_selection_falsified": checks["passed"], "observer_disposition": "selection-mechanism-rejected" if checks["passed"] else "falsifier-failed", "subject_disposition": parent["continuation"]["status"], "final_subject_digest": parent["artifact_digest"]}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(parent, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
