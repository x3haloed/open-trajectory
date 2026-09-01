from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0155_contradiction_corrected_developmental_extension.py"
BASE_SHA256 = "4f6cbc55944e352dc1d12855017539e6fc38446c25cc68aa4960f70473628bc7"
PARENT_DIGEST = "f785946d2ad17df2ce81f7efb3effed0cb9c66da8577dc297e1f7100f649af96"
ASSIMILATION_SCHEMA = REPO / "spec/ot-0153-expansion-assimilation.schema.json"

PUBLIC_CASES = [
    {"case_id": "corrected-reuse-public-a", "before": "selector-v10", "after": "selector-v11", "compatible": True, "options": ["reuse", "inspect", "discard"], "blocked": ["discard"], "expected": ["reuse", "inspect"]},
    {"case_id": "corrected-reuse-public-b", "before": "carrier-v12", "after": "carrier-v12", "compatible": False, "options": ["continue", "audit"], "blocked": [], "expected": []},
    {"case_id": "corrected-reuse-public-c", "before": "contact-v13", "after": "contact-v13", "options": ["probe", "renew", "erase"], "blocked": ["erase"], "expected": ["probe", "renew"]},
]
HIDDEN_CASES = [
    {"case_id": "corrected-reuse-hidden-a", "before": "program-v14", "after": "program-v15", "compatible": True, "options": ["transfer", "verify", "rollback"], "blocked": ["rollback"], "expected": ["transfer", "verify"]},
    {"case_id": "corrected-reuse-hidden-b", "before": "memory-v16", "after": "memory-v16", "compatible": False, "options": ["retain", "branch"], "blocked": [], "expected": []},
    {"case_id": "corrected-reuse-hidden-c", "before": "route-v17", "after": "route-v17", "options": ["left", "right", "blocked"], "blocked": ["blocked"], "expected": ["left", "right"]},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0155 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0156_frozen_ot0155", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
reuse_base = previous.previous
extension_base = previous.extension_base
worlds = previous.worlds
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def accumulated_floor() -> list[dict[str, Any]]:
    return [*previous.floor_cases(), *copy.deepcopy(previous.PUBLIC_CONTRADICTIONS), *copy.deepcopy(previous.HIDDEN_CONTRADICTIONS)]


def bind_reuse(p82, subject: dict[str, Any], route: dict[str, Any], public: dict[str, Any], floor: dict[str, Any]) -> dict[str, Any]:
    extension = subject["developmental_property_extensions"][0]
    body = {"authority": "ot-0156-bound-exact-corrected-extension-reuse", "source_subject_digest": subject["artifact_digest"], "active_stake": subject["active_developmental_stake"], "route_digest": route["route_digest"], "corrected_extension_binding_digest": extension["binding_digest"], "parent_extension_binding_digest": extension["parent_extension_binding_digest"], "operation_source_sha256": hashlib.sha256(extension["operation_source"].encode()).hexdigest(), "public_cases_digest": p82.digest(PUBLIC_CASES), "public_evaluation": public, "accumulated_floor_evaluation": floor}
    return {**body, "binding_digest": p82.digest(body)}


def hidden_world(p82, subject: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    extension = subject["developmental_property_extensions"][0]
    operation = extension_base.load_operation(extension["operation_source"])
    hidden = extension_base.evaluate(operation, HIDDEN_CASES)
    floor = extension_base.evaluate(operation, accumulated_floor())
    body = {"authority": "ot-0156-independent-corrected-extension-reuse-consequence", "reuse_binding_digest": binding["binding_digest"], "hidden_cases_digest": p82.digest(HIDDEN_CASES), "accumulated_floor_digest": p82.digest(accumulated_floor()), "hidden_result": hidden, "accumulated_floor_result": floor}
    return {**body, "receipt_digest": p82.digest(body)}


def assimilation_seed(root: Path, subject: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "assimilation-seed"
    seed.mkdir()
    current = subject["active_developmental_stake"]["property"]
    extension = subject["developmental_property_extensions"][0]
    vocabulary = {**worlds.VOCABULARY, extension["property"]["property"]: extension["property"]["description"]}
    files = {"subject-position.json": worlds.base.active_position(subject), "completed-stake.json": subject["active_developmental_stake"], "corrected-reuse-binding.json": binding, "world-consequence.json": world, "developmental-property-vocabulary.json": vocabulary, "next-stake.json": {"stake_id": "replace-me", "property": "option-expansion", "question": "Replace this question.", "rationale": "Replace this rationale.", "success_condition": "Replace this condition.", "surrender_condition": "Replace this condition."}, "mutation-envelope.json": {"editable": ["next-stake.json"], "immutable": ["subject-position.json", "completed-stake.json", "corrected-reuse-binding.json", "world-consequence.json", "developmental-property-vocabulary.json", "check_assimilation.py"]}}
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    allowed = sorted(vocabulary)
    (seed / "check_assimilation.py").write_text(f'''import json,re\nfrom pathlib import Path\ns=json.loads(Path("next-stake.json").read_text()); allowed=set({allowed!r}); current={current!r}; keys={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}\nok=set(s)==keys and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and s.get("property") in allowed and s.get("property")!=current and all(isinstance(s.get(k),str) and s[k].strip() for k in ["question","rationale","success_condition","surrender_condition"])\nprint(json.dumps({{"passed":bool(ok),"property":s.get("property")}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Assimilate the exact corrected extension's later consequence. Retire the completed extension stake and author one different routeable stake grounded in new compatibility reuse and preservation of the full accumulated floor. Edit only next-stake.json, run python3 check_assimilation.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_assimilator(context, p82, root: Path, subject: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "exact-corrected-extension-reuse-assimilator"
    seed = assimilation_seed(root, subject, binding, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATION_SCHEMA, (seed / "README.md").read_text().strip())
    current = subject["active_developmental_stake"]["property"]
    allowed = set(worlds.PROPERTIES) | {current}
    try:
        stake = json.loads((workspace / "next-stake.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        stake, immutable_ok = None, False
    valid = bool(reuse_base.valid_next_stake(stake, current, allowed) and immutable_ok and output and output.get("property_id") == stake["property"])
    audit = context.audit_actor(label, output, base_audit, valid, ["next-stake.json"])
    result = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0156-bound-corrected-extension-reuse-assimilation", "source_subject_digest": subject["artifact_digest"], "reuse_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "next_stake": stake}
        result = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "stake": stake, "binding": result}


def seal_successor(p82, parent: dict[str, Any], binding: dict[str, Any], world: dict[str, Any], assimilation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    extension = parent["developmental_property_extensions"][0]
    capability_body = {"authority": "ot-0156-exact-corrected-extension-reuse-capability", "property": extension["property"]["property"], "corrected_extension_binding_digest": extension["binding_digest"], "reuse_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
    capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
    receipt_body = {"authority": "ot-0156-exact-corrected-extension-reuse-transition", "source_subject_digest": parent["artifact_digest"], "capability_digest": capability["capability_digest"], "assimilation_binding_digest": assimilation["binding_digest"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    next_stake = assimilation["next_stake"]
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["corrected_extension_reuse_capabilities"] = [*child.get("corrected_extension_reuse_capabilities", []), capability]
    child["corrected_extension_reuse_receipts"] = [*child.get("corrected_extension_reuse_receipts", []), receipt]
    child["active_developmental_stake"] = next_stake
    opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = next_stake["question"]
    return p82.seal(child), receipt


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    extension = parent["developmental_property_extensions"][0]
    corrected = extension_base.load_operation(extension["operation_source"])
    ancestor = parent["developmental_property_extension_corrections"][-1]["parent"]
    old = extension_base.load_operation(ancestor["operation_source"])
    route = extension_base.extended_route(p82, parent, parent["active_developmental_stake"])
    corrected_public = extension_base.evaluate(corrected, PUBLIC_CASES)
    corrected_hidden = extension_base.evaluate(corrected, HIDDEN_CASES)
    corrected_floor = extension_base.evaluate(corrected, accumulated_floor())
    ancestor_hidden = extension_base.evaluate(old, HIDDEN_CASES)
    ancestor_floor = extension_base.evaluate(old, previous.floor_cases())
    checks = {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open", "active_stake_selects_corrected_extension": bool(route and route["extension_binding_digest"] == extension["binding_digest"]), "correction_ancestry_exact": ancestor["binding_digest"] == extension["parent_extension_binding_digest"], "corrected_new_public_passes": corrected_public["passed"], "corrected_new_hidden_passes": corrected_hidden["passed"], "corrected_accumulated_floor_passes": corrected_floor["passed"] and corrected_floor["pass_count"] == 18, "ancestor_fails_new_hidden": not ancestor_hidden["passed"] and ancestor_hidden["pass_count"] <= 1, "ancestor_preserves_legitimate_floor": ancestor_floor["passed"] and ancestor_floor["pass_count"] == 12, "assimilation_schema_present": ASSIMILATION_SCHEMA.is_file()}
    checks["passed"] = all(checks.values())
    return {"checks": checks, "route": route, "corrected_public": corrected_public, "corrected_hidden": corrected_hidden, "corrected_floor": corrected_floor, "ancestor_hidden": ancestor_hidden, "ancestor_floor": ancestor_floor}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0156").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0155", "open-subject-with-corrected-developmental-extension.json")
    fixtures = preflight(p82, parent)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0156 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    extension = parent["developmental_property_extensions"][0]
    operation = extension_base.load_operation(extension["operation_source"])
    public = extension_base.evaluate(operation, PUBLIC_CASES)
    floor = extension_base.evaluate(operation, accumulated_floor())
    binding = bind_reuse(p82, parent, fixtures["route"], public, floor)
    (run / "bound-exact-corrected-reuse.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    world = hidden_world(p82, parent, binding)
    (run / "sealed-hidden-corrected-reuse-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    assimilation_root = run / "reuse-assimilation"
    assimilation_root.mkdir()
    assimilation = run_assimilator(context, p82, assimilation_root, parent, binding, world) if world["hidden_result"]["passed"] and world["accumulated_floor_result"]["passed"] else None
    final = parent
    transition = None
    if assimilation and assimilation["binding"]:
        final, transition = seal_successor(p82, parent, binding, world, assimilation["binding"])
    erased = copy.deepcopy(parent); erased["developmental_property_extensions"] = []
    erased_route = extension_base.extended_route(p82, erased, parent["active_developmental_stake"])
    ancestor = parent["developmental_property_extension_corrections"][-1]["parent"]
    ancestor_hidden = extension_base.evaluate(extension_base.load_operation(ancestor["operation_source"]), HIDDEN_CASES)
    ancestor_floor = extension_base.evaluate(extension_base.load_operation(ancestor["operation_source"]), previous.floor_cases())
    next_route = reuse_base.route_any(p82, final, final["active_developmental_stake"])
    controls = {"extension_erased_route": erased_route, "uncorrected_ancestor_hidden": ancestor_hidden, "uncorrected_ancestor_floor": ancestor_floor, "successor_next_route": next_route}
    (run / "post-seal-controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True) + "\n")
    checks = {"exact_corrected_source_reused": binding["corrected_extension_binding_digest"] == extension["binding_digest"] and binding["operation_source_sha256"] == hashlib.sha256(extension["operation_source"].encode()).hexdigest(), "public_reuse_passes": public["passed"] and public["pass_count"] == 3, "hidden_reuse_passes": world["hidden_result"]["passed"] and world["hidden_result"]["pass_count"] == 3, "accumulated_floor_18_of_18": world["accumulated_floor_result"]["passed"] and world["accumulated_floor_result"]["pass_count"] == 18, "one_fresh_accepted_assimilator": bool(assimilation and assimilation["binding"] and prior131.audit_accepted(assimilation["audit"])), "uncorrected_ancestor_still_fails": not ancestor_hidden["passed"] and ancestor_hidden["pass_count"] <= 1, "uncorrected_ancestor_preserves_floor": ancestor_floor["passed"] and ancestor_floor["pass_count"] == 12, "extension_erasure_blocks_route": erased_route is None, "different_next_stake_routes": bool(assimilation and assimilation["stake"]["property"] != parent["active_developmental_stake"]["property"] and next_route), "parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key != "artifact_digest" and key not in {"active_developmental_stake", "active_pursuit", "continuation", "unresolved"}), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0156-exact-corrected-extension-reuse", "source_subject_digest": parent["artifact_digest"], "route": fixtures["route"], "reuse_binding": binding, "public_reuse": public, "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "transition_receipt": transition, "controls": controls, "checks": checks, "exact_corrected_reuse_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1 if assimilation else 0, "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
