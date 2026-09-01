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
SELECTOR_PATH = ROOT / "ot_0169_exact_corrected_guide_replication.py"
SELECTOR_SHA256 = "a94af5fd2d9451838a9adc33c11a0a2a2178e7cbcd368326efeb7ad4c6b4d2ca"
REUSE_PATH = ROOT / "ot_0156_exact_corrected_extension_reuse.py"
REUSE_SHA256 = "04e8a95674d9d9cf87cbce74bcfcc4a69a1bef76d0cb633061a5a32d1f7195e7"
PARENT_DIGEST = "9db80e4a3b64291ac7dbf4f0afcc2c2c1166878ccc5280d38c6320a72cacd29d"
ACTIVE_SELECTOR_DIGEST = "cd53bad0bc0dc0d063eefd88a5942bb1cb13cdd804a4ce1b7890b45420f48653"
EXTENSION_DIGEST = "4dee8764e65cd3c49fcdcf3cf9120f002b259e6d9271403f8baa1c7f5af5bc52"

PUBLIC_CASES = [
    {"case_id": "selector-continuation-public-a", "before": "selector-v18", "after": "selector-v19", "compatible": True, "options": ["continue", "inspect", "erase"], "blocked": ["erase"], "expected": ["continue", "inspect"]},
    {"case_id": "selector-continuation-public-b", "before": "carrier-v20", "after": "carrier-v20", "compatible": False, "options": ["reuse", "audit"], "blocked": [], "expected": []},
    {"case_id": "selector-continuation-public-c", "before": "contact-v21", "after": "contact-v21", "options": ["listen", "renew", "stop"], "blocked": ["stop"], "expected": ["listen", "renew"]},
]
HIDDEN_CASES = [
    {"case_id": "selector-continuation-hidden-a", "before": "program-v22", "after": "program-v23", "compatible": True, "options": ["transfer", "verify", "discard"], "blocked": ["discard"], "expected": ["transfer", "verify"]},
    {"case_id": "selector-continuation-hidden-b", "before": "memory-v24", "after": "memory-v24", "compatible": False, "options": ["retain", "branch"], "blocked": [], "expected": []},
    {"case_id": "selector-continuation-hidden-c", "before": "route-v25", "after": "route-v25", "options": ["left", "right", "closed"], "blocked": ["closed"], "expected": ["left", "right"]},
]


def load_module(path: Path, expected: str, name: str):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"{path.name} changed")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


selector = load_module(SELECTOR_PATH, SELECTOR_SHA256, "ot0170_frozen_ot0169")
reuse = load_module(REUSE_PATH, REUSE_SHA256, "ot0170_frozen_ot0156")
guide_base = selector.guide_base


def selection_seed(root: Path, subject: dict[str, Any], candidates: list[dict[str, Any]]) -> Path:
    seed = root / "selection-seed"
    seed.mkdir()
    guide_base.write_json(seed / "subject-position.json", reuse.worlds.base.active_position(subject))
    guide_base.write_json(seed / "candidate-mechanisms.json", candidates)
    (seed / "selection-guide.md").write_text(subject["active_developmental_mechanism_selector"]["guide_text"])
    guide_base.write_json(seed / "choice.json", {"mechanism_id": "__CHOOSE__", "rationale": "__CHOOSE__"})
    guide_base.write_json(seed / "mutation-envelope.json", {"editable": ["choice.json"], "immutable": ["subject-position.json", "candidate-mechanisms.json", "selection-guide.md"]})
    (seed / "README.md").write_text("Continue from the sole active developmental stake in subject-position.json. Use the inherited selection-guide.md to choose the presented mechanism that satisfies the whole stake. Edit only choice.json with exactly mechanism_id and a nonempty rationale, then report the same id truthfully.\n")
    return seed


def run_selection(context, prior131, p82, root: Path, label: str, subject: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    seed = selection_seed(root, subject, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, guide_base.CHOICE_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        choice = json.loads((workspace / "choice.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        choice, immutable_ok = None, False
    ids = {row["mechanism_id"] for row in candidates}
    valid = bool(isinstance(choice, dict) and set(choice) == {"mechanism_id", "rationale"} and choice.get("mechanism_id") in ids and isinstance(choice.get("rationale"), str) and choice["rationale"].strip() and immutable_ok and output and output.get("mechanism_id") == choice["mechanism_id"])
    audit = context.audit_actor(label, output, base_audit, valid, ["choice.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0170-bound-installed-selector-choice", "source_subject_digest": subject["artifact_digest"], "active_stake_digest": p82.digest(subject["active_developmental_stake"]), "selector_binding_digest": subject["active_developmental_mechanism_selector"]["binding_digest"], "actor_patch_digest": audit["patch_digest"], "mechanism_id": choice["mechanism_id"]}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "choice": choice, "binding": binding}


def bind_route(p82, parent: dict[str, Any], selection: dict[str, Any], public: dict[str, Any], floor: dict[str, Any]) -> dict[str, Any] | None:
    if not selection.get("binding") or selection["binding"]["mechanism_id"] != "corrected-identity-gated-extension":
        return None
    extension = parent["developmental_property_extensions"][0]
    body = {"authority": "ot-0170-bound-installed-selector-extension-route", "source_subject_digest": parent["artifact_digest"], "selection_binding_digest": selection["binding"]["binding_digest"], "selector_binding_digest": selection["binding"]["selector_binding_digest"], "extension_binding_digest": extension["binding_digest"], "operation_source_sha256": hashlib.sha256(extension["operation_source"].encode()).hexdigest(), "public_cases_digest": p82.digest(PUBLIC_CASES), "public_evaluation": public, "accumulated_floor_evaluation": floor}
    return {**body, "binding_digest": p82.digest(body)}


def seal_successor(p82, parent: dict[str, Any], route: dict[str, Any], world: dict[str, Any], assimilation: dict[str, Any]) -> dict[str, Any]:
    capability_body = {"authority": "ot-0170-installed-selector-continuation-capability", "selector_binding_digest": parent["active_developmental_mechanism_selector"]["binding_digest"], "selection_binding_digest": route["selection_binding_digest"], "extension_binding_digest": route["extension_binding_digest"], "route_binding_digest": route["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
    capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
    next_stake = assimilation["next_stake"]
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["installed_selector_continuation_capabilities"] = [*child.get("installed_selector_continuation_capabilities", []), capability]
    child["active_developmental_stake"] = next_stake
    opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = next_stake["question"]
    return p82.seal(child)


def main() -> int:
    selector_lineage = guide_base.load_base()
    selector_base = selector_lineage.selector_base
    base = selector_lineage.base
    prior131 = selector_lineage.prior131
    base130 = selector_lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0170").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0169", "open-subject-with-replicated-corrected-semantic-selector.json")
    candidates = selector_base.CANDIDATES
    extension = parent["developmental_property_extensions"][0]
    operation = reuse.extension_base.load_operation(extension["operation_source"])
    public_fixture = reuse.extension_base.evaluate(operation, PUBLIC_CASES)
    hidden_fixture = reuse.extension_base.evaluate(operation, HIDDEN_CASES)
    floor_fixture = reuse.extension_base.evaluate(operation, reuse.accumulated_floor())
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "continuation_matches_stake": parent["continuation"]["next_opening"] == "Open actor-stake-" + parent["active_developmental_stake"]["stake_id"] + ": " + parent["active_developmental_stake"]["question"], "exact_installed_selector": parent["active_developmental_mechanism_selector"]["binding_digest"] == ACTIVE_SELECTOR_DIGEST and len(parent["active_developmental_mechanism_selector"]["guide_text"].encode()) == 2999, "exact_corrected_extension": extension["binding_digest"] == EXTENSION_DIGEST and operation is not None, "new_public_fixture_3_of_3": public_fixture["passed"] and public_fixture["pass_count"] == 3, "new_hidden_fixture_3_of_3": hidden_fixture["passed"] and hidden_fixture["pass_count"] == 3, "accumulated_floor_18_of_18": floor_fixture["passed"] and floor_fixture["pass_count"] == 18, "candidate_set_exact": {row["mechanism_id"] for row in candidates} == {"reset-carrier", "viable-branch-carrier", "prediction-corrector", "corrected-identity-gated-extension"}, "schemas_present": guide_base.CHOICE_SCHEMA.is_file() and reuse.ASSIMILATION_SCHEMA.is_file()}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"selector_sha256": SELECTOR_SHA256, "reuse_sha256": REUSE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0170 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    selection_root = run / "current-selection"
    selection_root.mkdir()
    current_selection = run_selection(context, prior131, p82, selection_root, "installed-selector-current-choice", parent, candidates)
    public = reuse.extension_base.evaluate(operation, PUBLIC_CASES)
    floor = reuse.extension_base.evaluate(operation, reuse.accumulated_floor())
    route = bind_route(p82, parent, current_selection, public, floor)
    guide_base.write_json(run / "bound-installed-selector-route.json", route)
    hidden = reuse.extension_base.evaluate(operation, HIDDEN_CASES) if route else reuse.extension_base.evaluate(lambda _: None, [])
    world_body = {"authority": "ot-0170-independent-installed-selector-continuation-consequence", "route_binding_digest": route["binding_digest"] if route else None, "hidden_cases_digest": p82.digest(HIDDEN_CASES), "accumulated_floor_digest": p82.digest(reuse.accumulated_floor()), "hidden_result": hidden, "accumulated_floor_result": floor}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-installed-selector-continuation-world.json", world)
    assimilation = None
    if route and public["passed"] and hidden["passed"] and floor["passed"]:
        assimilation_root = run / "consequence-assimilation"
        assimilation_root.mkdir()
        assimilation = reuse.run_assimilator(context, p82, assimilation_root, parent, route, world)
    final = seal_successor(p82, parent, route, world, assimilation["binding"]) if assimilation and assimilation["binding"] else parent
    reopening = None
    if final["artifact_digest"] != parent["artifact_digest"]:
        reopening_root = run / "successor-reopening"
        reopening_root.mkdir()
        reopening = run_selection(context, prior131, p82, reopening_root, "installed-selector-successor-reopening", final, candidates)
    authorized = {"artifact_digest", "active_developmental_stake", "active_pursuit", "continuation", "unresolved", "installed_selector_continuation_capabilities"}
    checks = {"current_selector_actor_accepted": bool(current_selection["binding"] and prior131.audit_accepted(current_selection["audit"])), "current_choice_is_composed_extension": bool(current_selection["binding"] and current_selection["binding"]["mechanism_id"] == "corrected-identity-gated-extension"), "exact_selector_authorized_route": bool(route and route["selector_binding_digest"] == ACTIVE_SELECTOR_DIGEST), "exact_corrected_source_reused": bool(route and route["extension_binding_digest"] == EXTENSION_DIGEST and route["operation_source_sha256"] == hashlib.sha256(extension["operation_source"].encode()).hexdigest()), "public_3_of_3": public["passed"] and public["pass_count"] == 3, "hidden_3_of_3": hidden["passed"] and hidden["pass_count"] == 3, "accumulated_floor_18_of_18": floor["passed"] and floor["pass_count"] == 18, "fresh_assimilator_accepted": bool(assimilation and assimilation["binding"] and prior131.audit_accepted(assimilation["audit"])), "different_next_stake": bool(assimilation and assimilation["stake"]["stake_id"] != parent["active_developmental_stake"]["stake_id"] and assimilation["stake"]["property"] != parent["active_developmental_stake"]["property"]), "fresh_reopening_actor_accepted": bool(reopening and reopening["binding"] and prior131.audit_accepted(reopening["audit"])), "reopening_mechanism_available": bool(reopening and reopening["binding"] and reopening["binding"]["mechanism_id"] in {row["mechanism_id"] for row in candidates}), "installed_selector_retained_exactly": final.get("active_developmental_mechanism_selector") == parent["active_developmental_mechanism_selector"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "successor_opening_matches_stake": final["continuation"]["next_opening"] == "Open actor-stake-" + final["active_developmental_stake"]["stake_id"] + ": " + final["active_developmental_stake"]["question"], "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0170-installed-selector-continuation", "source_subject_digest": parent["artifact_digest"], "current_selection": p82.compact(current_selection), "route_binding": route, "public_result": public, "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "reopening_selection": p82.compact(reopening) if reopening else None, "checks": checks, "installed_selector_continuation_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum([bool(current_selection), bool(assimilation), bool(reopening)])}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
