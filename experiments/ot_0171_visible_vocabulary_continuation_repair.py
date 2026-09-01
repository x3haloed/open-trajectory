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
BASE_PATH = ROOT / "ot_0170_installed_selector_continuation.py"
BASE_SHA256 = "5f55b21e45861640965972ec8672e55e52ff85d54dc024a65ced4b9bccad0b0c"
PARENT_DIGEST = "9db80e4a3b64291ac7dbf4f0afcc2c2c1166878ccc5280d38c6320a72cacd29d"

PUBLIC_CASES = [
    {"case_id": "vocabulary-repair-public-a", "before": "selector-v26", "after": "selector-v27", "compatible": True, "options": ["carry", "inspect", "close"], "blocked": ["close"], "expected": ["carry", "inspect"]},
    {"case_id": "vocabulary-repair-public-b", "before": "carrier-v28", "after": "carrier-v28", "compatible": False, "options": ["reuse", "branch"], "blocked": [], "expected": []},
    {"case_id": "vocabulary-repair-public-c", "before": "contact-v29", "after": "contact-v29", "options": ["probe", "extend", "discard"], "blocked": ["discard"], "expected": ["probe", "extend"]},
]
HIDDEN_CASES = [
    {"case_id": "vocabulary-repair-hidden-a", "before": "program-v30", "after": "program-v31", "compatible": True, "options": ["transfer", "audit", "erase"], "blocked": ["erase"], "expected": ["transfer", "audit"]},
    {"case_id": "vocabulary-repair-hidden-b", "before": "memory-v32", "after": "memory-v32", "compatible": False, "options": ["retain", "renew"], "blocked": [], "expected": []},
    {"case_id": "vocabulary-repair-hidden-c", "before": "route-v33", "after": "route-v33", "options": ["listen", "respond", "stop"], "blocked": ["stop"], "expected": ["listen", "respond"]},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0170 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0171_frozen_ot0170", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
selector = previous.selector
reuse = previous.reuse
guide_base = previous.guide_base


def vocabulary(subject: dict[str, Any]) -> dict[str, str]:
    return {**reuse.worlds.VOCABULARY, **{row["property"]["property"]: row["property"]["description"] for row in subject["developmental_property_extensions"]}}


def valid_next(stake: Any, current: str, allowed: set[str]) -> bool:
    return reuse.reuse_base.valid_next_stake(stake, current, allowed)


def assimilation_seed(root: Path, subject: dict[str, Any], route: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "assimilation-seed"
    seed.mkdir()
    current = subject["active_developmental_stake"]["property"]
    vocab = vocabulary(subject)
    files = {"subject-position.json": reuse.worlds.base.active_position(subject), "completed-stake.json": subject["active_developmental_stake"], "installed-selector-route.json": route, "world-consequence.json": world, "developmental-property-vocabulary.json": vocab, "next-stake.json": {"stake_id": "replace-me", "property": "identity-gated-branch-filtering", "question": "Replace this question.", "rationale": "Replace this rationale.", "success_condition": "Replace this condition.", "surrender_condition": "Replace this condition."}, "mutation-envelope.json": {"editable": ["next-stake.json"], "immutable": ["subject-position.json", "completed-stake.json", "installed-selector-route.json", "world-consequence.json", "developmental-property-vocabulary.json", "check_assimilation.py"]}}
    for name, value in files.items():
        guide_base.write_json(seed / name, value)
    allowed = sorted(vocab)
    (seed / "check_assimilation.py").write_text(f'''import json,re\nfrom pathlib import Path\ns=json.loads(Path("next-stake.json").read_text()); allowed=set({allowed!r}); current={current!r}; keys={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}\nok=set(s)==keys and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and s.get("property") in allowed and s.get("property")!=current and all(isinstance(s.get(k),str) and s[k].strip() for k in ["question","rationale","success_condition","surrender_condition"])\nprint(json.dumps({{"passed":bool(ok),"property":s.get("property")}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Assimilate the installed selector's exact later consequence. Retire the completed stake and author one different next developmental stake from the complete visible vocabulary, grounded in world consequence and preservation of the accumulated floor. Edit only next-stake.json, run python3 check_assimilation.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_assimilator(context, prior131, p82, root: Path, subject: dict[str, Any], route: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "visible-vocabulary-consequence-assimilator"
    seed = assimilation_seed(root, subject, route, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, reuse.ASSIMILATION_SCHEMA, (seed / "README.md").read_text().strip())
    allowed = set(vocabulary(subject))
    current = subject["active_developmental_stake"]["property"]
    try:
        stake = json.loads((workspace / "next-stake.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        stake, immutable_ok = None, False
    valid = bool(valid_next(stake, current, allowed) and immutable_ok and output and output.get("property_id") == stake["property"])
    audit = context.audit_actor(label, output, base_audit, valid, ["next-stake.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0171-bound-visible-vocabulary-assimilation", "source_subject_digest": subject["artifact_digest"], "route_binding_digest": route["binding_digest"], "world_receipt_digest": world["receipt_digest"], "visible_vocabulary_digest": p82.digest(vocabulary(subject)), "actor_patch_digest": audit["patch_digest"], "next_stake": stake}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "stake": stake, "binding": binding}


def bind_route(p82, parent: dict[str, Any], selection: dict[str, Any], public: dict[str, Any], floor: dict[str, Any]) -> dict[str, Any] | None:
    if not selection.get("binding") or selection["binding"]["mechanism_id"] != "corrected-identity-gated-extension":
        return None
    extension = parent["developmental_property_extensions"][0]
    body = {"authority": "ot-0171-bound-visible-vocabulary-extension-route", "source_subject_digest": parent["artifact_digest"], "selection_binding_digest": selection["binding"]["binding_digest"], "selector_binding_digest": selection["binding"]["selector_binding_digest"], "extension_binding_digest": extension["binding_digest"], "operation_source_sha256": hashlib.sha256(extension["operation_source"].encode()).hexdigest(), "public_cases_digest": p82.digest(PUBLIC_CASES), "public_evaluation": public, "accumulated_floor_evaluation": floor}
    return {**body, "binding_digest": p82.digest(body)}


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
    run = (args.evidence_root or store / "runs/OT-0171").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0169", "open-subject-with-replicated-corrected-semantic-selector.json")
    candidates = selector_base.CANDIDATES
    extension = parent["developmental_property_extensions"][0]
    operation = reuse.extension_base.load_operation(extension["operation_source"])
    allowed = set(vocabulary(parent))
    representative = {"stake_id": "visible-extension-probe", "property": "identity-gated-branch-filtering", "question": "Can this extension continue?", "rationale": "Probe shared vocabulary.", "success_condition": "The extension remains available.", "surrender_condition": "The extension is unavailable."}
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0170_parent_unchanged": selector_base.load_artifact(p82, repo, store, "OT-0170", "unchanged-open-parent-after-assimilation-abi-mismatch.json")["artifact_digest"] == PARENT_DIGEST, "shared_vocabulary_includes_extension": "identity-gated-branch-filtering" in allowed, "representative_passes_observer_validator": valid_next(representative, parent["active_developmental_stake"]["property"], allowed), "new_public_3_of_3": reuse.extension_base.evaluate(operation, PUBLIC_CASES)["pass_count"] == 3, "new_hidden_3_of_3": reuse.extension_base.evaluate(operation, HIDDEN_CASES)["pass_count"] == 3, "floor_18_of_18": reuse.extension_base.evaluate(operation, reuse.accumulated_floor())["pass_count"] == 18, "schemas_present": guide_base.CHOICE_SCHEMA.is_file() and reuse.ASSIMILATION_SCHEMA.is_file()}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "visible_vocabulary_digest": p82.digest(vocabulary(parent))}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0171 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    selection_root = run / "current-selection"; selection_root.mkdir()
    current_selection = previous.run_selection(context, prior131, p82, selection_root, "visible-vocabulary-current-choice", parent, candidates)
    public = reuse.extension_base.evaluate(operation, PUBLIC_CASES)
    floor = reuse.extension_base.evaluate(operation, reuse.accumulated_floor())
    route = bind_route(p82, parent, current_selection, public, floor)
    guide_base.write_json(run / "bound-visible-vocabulary-route.json", route)
    hidden = reuse.extension_base.evaluate(operation, HIDDEN_CASES) if route else {"passed": False, "pass_count": 0, "case_count": 0, "rows": []}
    world_body = {"authority": "ot-0171-independent-visible-vocabulary-continuation-consequence", "route_binding_digest": route["binding_digest"] if route else None, "hidden_cases_digest": p82.digest(HIDDEN_CASES), "accumulated_floor_digest": p82.digest(reuse.accumulated_floor()), "hidden_result": hidden, "accumulated_floor_result": floor}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-visible-vocabulary-continuation-world.json", world)
    assimilation = None
    if route and public["passed"] and hidden["passed"] and floor["passed"]:
        assimilation_root = run / "consequence-assimilation"; assimilation_root.mkdir()
        assimilation = run_assimilator(context, prior131, p82, assimilation_root, parent, route, world)
    final = previous.seal_successor(p82, parent, route, world, assimilation["binding"]) if assimilation and assimilation["binding"] else parent
    reopening = None
    if final["artifact_digest"] != parent["artifact_digest"]:
        reopening_root = run / "successor-reopening"; reopening_root.mkdir()
        reopening = previous.run_selection(context, prior131, p82, reopening_root, "visible-vocabulary-successor-reopening", final, candidates)
    authorized = {"artifact_digest", "active_developmental_stake", "active_pursuit", "continuation", "unresolved", "installed_selector_continuation_capabilities"}
    checks = {"current_selector_actor_accepted": bool(current_selection["binding"] and prior131.audit_accepted(current_selection["audit"])), "current_choice_is_composed_extension": bool(current_selection["binding"] and current_selection["binding"]["mechanism_id"] == "corrected-identity-gated-extension"), "exact_selector_authorized_route": bool(route and route["selector_binding_digest"] == previous.ACTIVE_SELECTOR_DIGEST), "exact_corrected_source_reused": bool(route and route["extension_binding_digest"] == previous.EXTENSION_DIGEST), "public_3_of_3": public["passed"] and public["pass_count"] == 3, "hidden_3_of_3": hidden["passed"] and hidden["pass_count"] == 3, "accumulated_floor_18_of_18": floor["passed"] and floor["pass_count"] == 18, "fresh_assimilator_accepted": bool(assimilation and assimilation["binding"] and prior131.audit_accepted(assimilation["audit"])), "different_next_stake": bool(assimilation and assimilation["stake"]["stake_id"] != parent["active_developmental_stake"]["stake_id"] and assimilation["stake"]["property"] != parent["active_developmental_stake"]["property"]), "fresh_reopening_actor_accepted": bool(reopening and reopening["binding"] and prior131.audit_accepted(reopening["audit"])), "reopening_mechanism_available": bool(reopening and reopening["binding"] and reopening["binding"]["mechanism_id"] in {row["mechanism_id"] for row in candidates}), "installed_selector_retained_exactly": final.get("active_developmental_mechanism_selector") == parent["active_developmental_mechanism_selector"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "successor_opening_matches_stake": final["continuation"]["next_opening"] == "Open actor-stake-" + final["active_developmental_stake"]["stake_id"] + ": " + final["active_developmental_stake"]["question"], "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0171-visible-vocabulary-continuation-repair", "source_subject_digest": parent["artifact_digest"], "current_selection": p82.compact(current_selection), "route_binding": route, "public_result": public, "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "reopening_selection": p82.compact(reopening) if reopening else None, "checks": checks, "visible_vocabulary_continuation_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum([bool(current_selection), bool(assimilation), bool(reopening)])}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
