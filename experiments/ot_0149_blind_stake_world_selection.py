from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0148_exact_corrected_program_reuse.py"
BASE_SHA256 = "7994e8146e14b5cffa7fd52af2b7dd9d55c7ca4d3fa9911353d28cbfa0b5310d"
PARENT_DIGEST = "7fa070fde9478fcd83ca2e20c2b94f5db1c5a9f2d5208c675ccf5f7e5d6c5263"
STAKE_SCHEMA = REPO / "spec/ot-0149-stake.schema.json"
CONTACT_SCHEMA = REPO / "spec/ot-0149-contact.schema.json"
ASSIMILATION_SCHEMA = REPO / "spec/ot-0149-assimilation.schema.json"
PROPERTIES = ["continuity-under-reset", "option-expansion", "correction-from-error"]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0148 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0149_frozen_ot0148", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot147 = previous.previous
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


VOCABULARY = {
    "continuity-under-reset": "Preserve a useful signal or commitment across an otherwise destructive boundary.",
    "option-expansion": "Increase the set of viable future moves without preserving blocked branches.",
    "correction-from-error": "Use observed discrepancy to replace a stale prediction with a world-grounded one.",
}

SURFACES = {
    "continuity-under-reset": {
        "surface_id": "reset-carrier",
        "objective": "Return the input signal after a reset boundary.",
        "initial_policy": {"mode": "drop"},
        "passing_policy": {"mode": "carry"},
        "allowed_modes": ["drop", "carry"],
        "public_cases": [{"case_id": "reset-public-a", "signal": "amber"}, {"case_id": "reset-public-b", "signal": "cedar"}],
        "hidden_cases": [{"case_id": "reset-hidden-a", "signal": "violet"}, {"case_id": "reset-hidden-b", "signal": "quartz"}, {"case_id": "reset-hidden-c", "signal": "willow"}],
    },
    "option-expansion": {
        "surface_id": "viable-branch-carrier",
        "objective": "Return every unblocked option rather than prematurely closing to one.",
        "initial_policy": {"mode": "first"},
        "passing_policy": {"mode": "all-viable"},
        "allowed_modes": ["first", "all-viable"],
        "public_cases": [{"case_id": "branch-public-a", "options": ["a", "b", "c"], "blocked": ["b"]}, {"case_id": "branch-public-b", "options": ["d", "e", "f"], "blocked": ["f"]}],
        "hidden_cases": [{"case_id": "branch-hidden-a", "options": ["g", "h", "i", "j"], "blocked": ["h"]}, {"case_id": "branch-hidden-b", "options": ["k", "l", "m"], "blocked": []}, {"case_id": "branch-hidden-c", "options": ["n", "o", "p"], "blocked": ["n"]}],
    },
    "correction-from-error": {
        "surface_id": "prediction-corrector",
        "objective": "Replace a stale prediction with the observed outcome.",
        "initial_policy": {"mode": "ignore"},
        "passing_policy": {"mode": "error-corrected"},
        "allowed_modes": ["ignore", "error-corrected"],
        "public_cases": [{"case_id": "error-public-a", "prediction": 2, "outcome": 5}, {"case_id": "error-public-b", "prediction": 9, "outcome": 4}],
        "hidden_cases": [{"case_id": "error-hidden-a", "prediction": 1, "outcome": 8}, {"case_id": "error-hidden-b", "prediction": 7, "outcome": 3}, {"case_id": "error-hidden-c", "prediction": 6, "outcome": 10}],
    },
}


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def valid_text(value: Any) -> bool:
    return prior131.valid_text(value)


def valid_stake(stake: Any) -> bool:
    return bool(isinstance(stake, dict) and set(stake) == {"stake_id", "property", "question", "rationale", "success_condition", "surrender_condition"} and isinstance(stake["stake_id"], str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", stake["stake_id"]) and stake["property"] in PROPERTIES and all(valid_text(stake[key]) for key in ["question", "rationale", "success_condition", "surrender_condition"]))


STAKE_CHECKER = '''import json,re
from pathlib import Path
s=json.loads(Path("next-stake.json").read_text()); props={"continuity-under-reset","option-expansion","correction-from-error"}
passed=bool(set(s)=={"stake_id","property","question","rationale","success_condition","surrender_condition"} and isinstance(s["stake_id"],str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}",s["stake_id"]) and s["property"] in props and all(isinstance(s[k],str) and s[k].strip() for k in ["question","rationale","success_condition","surrender_condition"]))
print(json.dumps({"passed":passed,"property":s.get("property")},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def stake_seed(root: Path, subject: dict[str, Any]) -> Path:
    seed = root / "stake-seed"
    seed.mkdir()
    files = {
        "subject-position.json": base.active_position(subject),
        "developmental-property-vocabulary.json": VOCABULARY,
        "next-stake.json": {"stake_id": "uncommitted-next-stake", "property": "", "question": "Replace this question.", "rationale": "Replace this rationale.", "success_condition": "Replace this condition.", "surrender_condition": "Replace this condition."},
        "mutation-envelope.json": {"editable": ["next-stake.json"], "immutable": ["subject-position.json", "developmental-property-vocabulary.json", "check_stake.py"], "world_surfaces_exposed": False},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_stake.py").write_text(STAKE_CHECKER)
    (seed / "README.md").write_text("Advance the continuing subject by authoring one developmental stake before any world opportunities are shown. Choose what matters next from the neutral property vocabulary, edit only next-stake.json, run python3 check_stake.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_stake_actor(context, p82, root: Path, subject: dict[str, Any]) -> dict[str, Any]:
    label = "blind-next-stake-author"
    seed = stake_seed(root, subject)
    output, base_audit, workspace, _ = context.run_actor(label, seed, STAKE_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        stake = json.loads((workspace / "next-stake.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        stake, immutable_ok = None, False
    valid = bool(valid_stake(stake) and immutable_ok and output and output.get("selected_property") == stake["property"])
    audit = context.audit_actor(label, output, base_audit, valid, ["next-stake.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0149-bound-blind-developmental-stake", "source_subject_digest": subject["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "stake": stake, "world_catalog_visible_to_actor": False}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "stake": stake, "binding": binding}


def catalog(p82) -> dict[str, Any]:
    rows = [{"property": prop, "surface_id": SURFACES[prop]["surface_id"], "objective": SURFACES[prop]["objective"]} for prop in ["option-expansion", "correction-from-error", "continuity-under-reset"]]
    body = {"authority": "ot-0149-post-stake-world-catalog", "surfaces": rows}
    return {**body, "catalog_digest": p82.digest(body)}


def compile_route(p82, subject: dict[str, Any], stake: dict[str, Any], world_catalog: dict[str, Any]) -> dict[str, Any] | None:
    prop = stake.get("stake", {}).get("property") if isinstance(stake, dict) else None
    matches = [row for row in world_catalog["surfaces"] if row["property"] == prop]
    if len(matches) != 1:
        return None
    body = {"authority": "ot-0149-stake-to-world-compiler-v1", "source_subject_digest": subject["artifact_digest"], "stake_binding_digest": stake["binding_digest"], "catalog_digest": world_catalog["catalog_digest"], "selected_property": prop, "selected_surface": matches[0]}
    return {**body, "route_digest": p82.digest(body)}


def apply_policy(prop: str, policy: dict[str, Any], case: dict[str, Any]) -> Any:
    mode = policy["mode"]
    if prop == "continuity-under-reset":
        return case["signal"] if mode == "carry" else None
    if prop == "option-expansion":
        viable = [item for item in case["options"] if item not in case["blocked"]]
        return viable if mode == "all-viable" else viable[:1]
    return case["outcome"] if mode == "error-corrected" else case["prediction"]


def expected(prop: str, case: dict[str, Any]) -> Any:
    if prop == "continuity-under-reset":
        return case["signal"]
    if prop == "option-expansion":
        return [item for item in case["options"] if item not in case["blocked"]]
    return case["outcome"]


def evaluate(prop: str, policy: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [{"case_id": case["case_id"], "observed": apply_policy(prop, policy, case), "expected": expected(prop, case), "passed": apply_policy(prop, policy, case) == expected(prop, case)} for case in cases]
    return {"property": prop, "surface_id": SURFACES[prop]["surface_id"], "policy": policy, "cases": rows, "pass_count": sum(row["passed"] for row in rows), "case_count": len(rows), "passed": all(row["passed"] for row in rows)}


CONTACT_CHECKER = r'''import json
from pathlib import Path
w=json.loads(Path("selected-world.json").read_text()); p=json.loads(Path("policy.json").read_text()); a=json.loads(Path("contact-action.json").read_text()); prop=w["property"]
shape=set(p)=={"mode"} and p["mode"] in w["allowed_modes"] and set(a)=={"action","property","rationale"} and a["action"]=="apply-policy" and a["property"]==prop and isinstance(a["rationale"],str) and a["rationale"].strip()
def apply(c):
    if prop=="continuity-under-reset": return c["signal"] if p["mode"]=="carry" else None
    if prop=="option-expansion":
        v=[x for x in c["options"] if x not in c["blocked"]]; return v if p["mode"]=="all-viable" else v[:1]
    return c["outcome"] if p["mode"]=="error-corrected" else c["prediction"]
def expected(c):
    if prop=="continuity-under-reset": return c["signal"]
    if prop=="option-expansion": return [x for x in c["options"] if x not in c["blocked"]]
    return c["outcome"]
passed=bool(shape and all(apply(c)==expected(c) for c in w["public_cases"])); print(json.dumps({"passed":passed,"property":prop,"mode":p.get("mode")},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def contact_seed(root: Path, subject: dict[str, Any], stake: dict[str, Any], route: dict[str, Any]) -> Path:
    seed = root / "contact-seed"
    seed.mkdir()
    prop = route["selected_property"]
    surface = SURFACES[prop]
    files = {
        "subject-position.json": base.active_position(subject),
        "bound-stake.json": stake,
        "route-binding.json": route,
        "selected-world.json": {"property": prop, "surface_id": surface["surface_id"], "objective": surface["objective"], "allowed_modes": surface["allowed_modes"], "public_cases": surface["public_cases"]},
        "policy.json": surface["initial_policy"],
        "contact-action.json": {"action": "inspect", "property": prop, "rationale": "Replace after public contact."},
        "mutation-envelope.json": {"editable": ["policy.json", "contact-action.json"], "immutable": ["subject-position.json", "bound-stake.json", "route-binding.json", "selected-world.json", "check_contact.py"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_contact.py").write_text(CONTACT_CHECKER)
    (seed / "README.md").write_text("Realize the bound stake in the selected executable world. Edit only policy.json and contact-action.json, run python3 check_contact.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_contact_actor(context, p82, root: Path, subject: dict[str, Any], stake: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    label = "selected-world-contact-author"
    seed = contact_seed(root, subject, stake, route)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    prop = route["selected_property"]
    try:
        policy = json.loads((workspace / "policy.json").read_text())
        action = json.loads((workspace / "contact-action.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        policy, action, immutable_ok = None, None, False
    public = evaluate(prop, policy, SURFACES[prop]["public_cases"]) if isinstance(policy, dict) and set(policy) == {"mode"} and policy["mode"] in SURFACES[prop]["allowed_modes"] else None
    valid = bool(public and public["passed"] and immutable_ok and isinstance(action, dict) and set(action) == {"action", "property", "rationale"} and action["action"] == "apply-policy" and action["property"] == prop and valid_text(action["rationale"]))
    audit = context.audit_actor(label, output, base_audit, valid, ["contact-action.json", "policy.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0149-bound-selected-world-policy", "source_subject_digest": subject["artifact_digest"], "stake_binding_digest": stake["binding_digest"], "route_digest": route["route_digest"], "actor_patch_digest": audit["patch_digest"], "property": prop, "surface_id": route["selected_surface"]["surface_id"], "policy": policy, "action": action, "public_evaluation": public}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "policy": policy, "action": action, "public": public, "binding": binding}


def hidden_world(p82, binding: dict[str, Any]) -> dict[str, Any]:
    prop = binding["property"]
    result = evaluate(prop, binding["policy"], SURFACES[prop]["hidden_cases"])
    body = {"authority": "ot-0149-independent-selected-world-consequence", "policy_binding_digest": binding["binding_digest"], "hidden_cases_digest": p82.digest(SURFACES[prop]["hidden_cases"]), "result": result}
    return {**body, "receipt_digest": p82.digest(body)}


ASSIMILATION_CHECKER = '''import json
from pathlib import Path
a=json.loads(Path("assimilation.json").read_text()); current=json.loads(Path("bound-stake.json").read_text())["stake"]; world=json.loads(Path("world-consequence.json").read_text()); nxt=a.get("next_stake",{}); props={"continuity-under-reset","option-expansion","correction-from-error"}
stake_ok=set(nxt)=={"stake_id","property","question","rationale","success_condition","surrender_condition"} and nxt.get("property") in props and nxt.get("property")!=current["property"] and all(isinstance(nxt.get(k),str) and nxt[k].strip() for k in ["stake_id","question","rationale","success_condition","surrender_condition"])
passed=bool(set(a)=={"disposition","evidence_receipt_digest","next_stake"} and a["disposition"]=="retire" and a["evidence_receipt_digest"]==world["receipt_digest"] and world["result"]["passed"] and stake_ok)
print(json.dumps({"passed":passed,"disposition":a.get("disposition"),"next_property":nxt.get("property")},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def assimilation_seed(root: Path, subject: dict[str, Any], stake: dict[str, Any], route: dict[str, Any], policy: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "assimilation-seed"
    seed.mkdir()
    files = {"subject-position.json": base.active_position(subject), "bound-stake.json": stake, "route-binding.json": route, "bound-policy.json": policy, "world-consequence.json": world, "developmental-property-vocabulary.json": VOCABULARY, "assimilation.json": {"disposition": "renew", "evidence_receipt_digest": world["receipt_digest"], "next_stake": stake["stake"]}, "mutation-envelope.json": {"editable": ["assimilation.json"], "immutable": ["subject-position.json", "bound-stake.json", "route-binding.json", "bound-policy.json", "world-consequence.json", "developmental-property-vocabulary.json", "check_assimilation.py"]}}
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_assimilation.py").write_text(ASSIMILATION_CHECKER)
    (seed / "README.md").write_text("Assimilate the completed world consequence. Retire the fulfilled stake and author a different next developmental stake. Edit only assimilation.json, run python3 check_assimilation.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_assimilator(context, p82, root: Path, subject: dict[str, Any], stake: dict[str, Any], route: dict[str, Any], policy: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "selected-world-consequence-assimilator"
    seed = assimilation_seed(root, subject, stake, route, policy, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        assimilation = json.loads((workspace / "assimilation.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        assimilation, immutable_ok = None, False
    valid = bool(isinstance(assimilation, dict) and set(assimilation) == {"disposition", "evidence_receipt_digest", "next_stake"} and assimilation["disposition"] == "retire" and assimilation["evidence_receipt_digest"] == world["receipt_digest"] and valid_stake(assimilation["next_stake"]) and assimilation["next_stake"]["property"] != stake["stake"]["property"] and immutable_ok)
    audit = context.audit_actor(label, output, base_audit, valid, ["assimilation.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0149-bound-selected-world-assimilation", "source_subject_digest": subject["artifact_digest"], "stake_binding_digest": stake["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "assimilation": assimilation}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "assimilation": assimilation, "binding": binding}


def seal_successor(p82, subject: dict[str, Any], stake: dict[str, Any], route: dict[str, Any], policy: dict[str, Any], world: dict[str, Any], assimilation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    capability_body = {"authority": "ot-0149-subject-selected-world-capability", "property": policy["property"], "surface_id": policy["surface_id"], "policy": policy["policy"], "stake_binding_digest": stake["binding_digest"], "route_digest": route["route_digest"], "policy_binding_digest": policy["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
    capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
    receipt_body = {"authority": "ot-0149-subject-selected-world-transition", "source_subject_digest": subject["artifact_digest"], "capability_digest": capability["capability_digest"], "assimilation_binding_digest": assimilation["binding_digest"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    next_stake = assimilation["assimilation"]["next_stake"]
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["subject_originated_world_stakes"] = [*child.get("subject_originated_world_stakes", []), stake]
    child["subject_selected_world_routes"] = [*child.get("subject_selected_world_routes", []), route]
    child["subject_selected_world_capabilities"] = [*child.get("subject_selected_world_capabilities", []), capability]
    child["subject_selected_world_transition_receipts"] = [*child.get("subject_selected_world_transition_receipts", []), receipt]
    child["active_developmental_stake"] = next_stake
    opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = next_stake["question"]
    return p82.seal(child), receipt


def representative_stake(prop: str) -> dict[str, Any]:
    return {"stake_id": "fixture-stake", "property": prop, "question": "What should continue next?", "rationale": "Exercise the selected developmental property.", "success_condition": "Independent world contact passes.", "surrender_condition": "Surrender if consequence rejects the property."}


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    world_catalog = catalog(p82)
    routes = {}
    for prop in PROPERTIES:
        stake_body = {"authority": "fixture", "source_subject_digest": parent["artifact_digest"], "actor_patch_digest": "fixture", "stake": representative_stake(prop), "world_catalog_visible_to_actor": False}
        stake = {**stake_body, "binding_digest": p82.digest(stake_body)}
        routes[prop] = compile_route(p82, parent, stake, world_catalog)
    evaluations = {prop: evaluate(prop, SURFACES[prop]["passing_policy"], SURFACES[prop]["hidden_cases"]) for prop in PROPERTIES}
    with tempfile.TemporaryDirectory() as directory:
        files = sorted(path.name for path in stake_seed(Path(directory), parent).iterdir() if path.is_file())
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "blind_seed_has_no_world": files == ["README.md", "check_stake.py", "developmental-property-vocabulary.json", "mutation-envelope.json", "next-stake.json", "subject-position.json"],
        "routes_unique": len({routes[prop]["selected_surface"]["surface_id"] for prop in PROPERTIES}) == 3,
        "all_worlds_executable": all(result["passed"] and result["pass_count"] == 3 for result in evaluations.values()),
        "schemas_present": STAKE_SCHEMA.is_file() and CONTACT_SCHEMA.is_file() and ASSIMILATION_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "catalog": world_catalog, "routes": routes, "evaluations": evaluations}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0149").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0148", "open-subject-with-cross-world-corrected-program.json")
    fixtures = preflight(p82, parent)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0149 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    stake_root = run / "blind-stake"
    stake_root.mkdir()
    stake = run_stake_actor(context, p82, stake_root, parent)
    world_catalog = route = None
    if stake["binding"]:
        world_catalog = catalog(p82)
        route = compile_route(p82, parent, stake["binding"], world_catalog)
        (run / "post-stake-world-catalog.json").write_text(json.dumps(world_catalog, indent=2, sort_keys=True) + "\n")
        (run / "compiled-world-route.json").write_text(json.dumps(route, indent=2, sort_keys=True) + "\n")
    contact_root = run / "selected-world-contact"
    contact_root.mkdir()
    contact = run_contact_actor(context, p82, contact_root, parent, stake["binding"], route) if route else None
    world = hidden_world(p82, contact["binding"]) if contact and contact["binding"] else None
    if world:
        (contact_root / "sealed-hidden-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    assimilation_root = run / "consequence-assimilation"
    assimilation_root.mkdir()
    assimilation = run_assimilator(context, p82, assimilation_root, parent, stake["binding"], route, contact["binding"], world) if world and world["result"]["passed"] else None
    final = parent
    transition = None
    if assimilation and assimilation["binding"]:
        final, transition = seal_successor(p82, parent, stake["binding"], route, contact["binding"], world, assimilation["binding"])
    erased_route = compile_route(p82, parent, {**(stake["binding"] or {}), "stake": {key: value for key, value in (stake["binding"] or {}).get("stake", {}).items() if key != "property"}}, world_catalog) if world_catalog and stake["binding"] else None
    counterfactual_route = None
    if world_catalog and stake["binding"]:
        current = stake["binding"]["stake"]["property"]
        other = PROPERTIES[(PROPERTIES.index(current) + 1) % len(PROPERTIES)]
        counterfactual = copy.deepcopy(stake["binding"])
        counterfactual["stake"]["property"] = other
        counterfactual["binding_digest"] = p82.digest({key: value for key, value in counterfactual.items() if key != "binding_digest"})
        counterfactual_route = compile_route(p82, parent, counterfactual, world_catalog)
    controls = {"property_erased_route": erased_route, "counterfactual_route": counterfactual_route}
    (run / "post-seal-route-controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True) + "\n")
    checks = {
        "three_fresh_actors": bool(stake["binding"] and contact and contact["binding"] and assimilation and assimilation["binding"]),
        "stake_blind_to_worlds": bool(stake["binding"] and not stake["binding"]["world_catalog_visible_to_actor"]),
        "stake_causes_unique_route": bool(route and route["selected_property"] == stake["binding"]["stake"]["property"]),
        "selected_world_contact_passes": bool(world and world["result"]["passed"] and world["result"]["pass_count"] == 3),
        "consequence_changes_next_stake": bool(assimilation and assimilation["binding"] and assimilation["assimilation"]["next_stake"]["property"] != stake["binding"]["stake"]["property"]),
        "erasure_blocks_route": erased_route is None,
        "different_property_changes_world": bool(counterfactual_route and route and counterfactual_route["selected_surface"]["surface_id"] != route["selected_surface"]["surface_id"]),
        "prior_capabilities_retained": bool(final.get("adaptive_contact_strategy_capabilities") and final.get("recovery_cadence_capabilities") and final.get("deadline_recovery_capabilities") and len(final.get("constitutional_selector_program_capabilities", [])) == len(parent.get("constitutional_selector_program_capabilities", []))),
        "new_capability_retained": bool(final.get("subject_selected_world_capabilities") and final["subject_selected_world_capabilities"][-1]["world_receipt_digest"] == world["receipt_digest"]),
        "actor_authored_opening": bool(final.get("active_developmental_stake") == assimilation["assimilation"]["next_stake"] and assimilation["assimilation"]["next_stake"]["question"] in final["continuation"]["next_opening"]),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0149-blind-stake-world-selection-driver", "source_subject_digest": parent["artifact_digest"], "blind_stake": p82.compact(stake), "post_stake_world_catalog": world_catalog, "compiled_route": route, "selected_world_contact": p82.compact(contact) if contact else None, "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "transition_receipt": transition, "post_seal_controls": controls, "checks": checks, "blind_stake_world_selection_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum(item is not None for item in [stake, contact, assimilation]), "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
