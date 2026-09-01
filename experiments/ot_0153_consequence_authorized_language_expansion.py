from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0152_single_invocation_subject_scheduler.py"
BASE_SHA256 = "5fb3cb3d0aca8ccb1199509c2bc7204ba323b27d72161ed2468f313d7f632039"
PARENT_DIGEST = "48e830dcc1090cecf53a0da521a463d44d0ea0e635bcd68dc11e9371d24feaec"
AUTHOR_SCHEMA = REPO / "spec/ot-0153-expansion-author.schema.json"
ASSIMILATION_SCHEMA = REPO / "spec/ot-0153-expansion-assimilation.schema.json"
PROPERTY_RE = re.compile(r"[a-z][a-z0-9-]{2,63}")

PUBLIC_CASES = [
    {"case_id": "coherence-public-a", "before": "route-v2", "after": "route-v2", "options": ["retry", "inspect", "discard"], "blocked": ["discard"], "expected": ["retry", "inspect"]},
    {"case_id": "coherence-public-b", "before": "policy-v1", "after": "policy-v0", "options": ["deploy", "compare"], "blocked": [], "expected": []},
    {"case_id": "coherence-public-c", "before": "carrier-v3", "after": "carrier-v3", "options": ["transfer", "renew", "erase"], "blocked": ["erase"], "expected": ["transfer", "renew"]},
]
HIDDEN_CASES = [
    {"case_id": "coherence-hidden-a", "before": "selector-v4", "after": "selector-v4", "options": ["reuse", "probe", "rollback"], "blocked": ["rollback"], "expected": ["reuse", "probe"]},
    {"case_id": "coherence-hidden-b", "before": "memory-v2", "after": "memory-v1", "options": ["continue", "audit"], "blocked": ["continue"], "expected": []},
    {"case_id": "coherence-hidden-c", "before": "contact-v5", "after": "contact-v5", "options": ["branch", "verify", "compose"], "blocked": [], "expected": ["branch", "verify", "compose"]},
]
SAFE_BUILTINS = {"all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate, "filter": filter, "isinstance": isinstance, "len": len, "list": list, "map": map, "set": set, "sorted": sorted, "str": str, "tuple": tuple, "zip": zip}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0152 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0153_frozen_ot0152", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
worlds = previous.worlds
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def load_operation(source: str) -> Callable[[dict[str, Any]], Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    forbidden = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.Try, ast.Raise)
    if any(isinstance(node, forbidden) for node in ast.walk(tree)):
        return None
    if any(isinstance(node, ast.Name) and node.id.startswith("__") for node in ast.walk(tree)):
        return None
    if any(isinstance(node, ast.Attribute) and node.attr.startswith("__") for node in ast.walk(tree)):
        return None
    namespace: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    try:
        exec(compile(tree, "<developmental-extension>", "exec"), namespace)
    except Exception:
        return None
    operation = namespace.get("realize_contact")
    return operation if callable(operation) else None


def valid_property(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == {"property", "description", "objective", "operation"}
        and isinstance(value["property"], str)
        and PROPERTY_RE.fullmatch(value["property"])
        and value["property"] not in worlds.PROPERTIES
        and value["operation"] == "realize_contact"
        and prior131.valid_text(value["description"])
        and prior131.valid_text(value["objective"])
    )


def evaluate(operation: Callable[[dict[str, Any]], Any] | None, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        payload = {key: copy.deepcopy(value) for key, value in case.items() if key not in {"case_id", "expected"}}
        before = copy.deepcopy(payload)
        try:
            observed = operation(payload) if operation else None
        except Exception:
            observed = None
        rows.append({"case_id": case["case_id"], "observed": observed, "expected": case["expected"], "input_unchanged": payload == before, "passed": observed == case["expected"] and payload == before})
    return {"rows": rows, "pass_count": sum(row["passed"] for row in rows), "case_count": len(rows), "passed": bool(rows and all(row["passed"] for row in rows))}


def catalog_gap(p82, parent: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {"property": "continuity-under-reset", "missing": ["before/after identity comparison", "branch filtering"]},
        {"property": "option-expansion", "missing": ["before/after identity comparison"]},
        {"property": "correction-from-error", "missing": ["capability identity", "branch filtering"]},
    ]
    body = {"authority": "ot-0153-objective-catalog-inadequacy", "source_subject_digest": parent["artifact_digest"], "active_stake": parent["active_developmental_stake"], "required_case_keys": ["before", "after", "options", "blocked"], "existing_property_gaps": rows, "closed_catalog_digest": worlds.catalog(p82)["catalog_digest"]}
    return {**body, "receipt_digest": p82.digest(body)}


AUTHOR_CHECKER = '''import ast,json,re
from pathlib import Path
p=json.loads(Path("property.json").read_text()); s=Path("operation.py").read_text(); old={"continuity-under-reset","option-expansion","correction-from-error"}
shape=set(p)=={"property","description","objective","operation"} and isinstance(p["property"],str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}",p["property"]) and p["property"] not in old and p["operation"]=="realize_contact" and all(isinstance(p[k],str) and p[k].strip() for k in ["description","objective"])
try: names={n.name for n in ast.walk(ast.parse(s)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
except SyntaxError: names=set()
passed=bool(shape and "realize_contact" in names); print(json.dumps({"passed":passed,"property":p.get("property")},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def author_seed(root: Path, subject: dict[str, Any], gap: dict[str, Any]) -> Path:
    seed = root / "extension-seed"
    seed.mkdir()
    files = {
        "subject-position.json": worlds.base.active_position(subject),
        "active-stake.json": subject["active_developmental_stake"],
        "closed-catalog.json": worlds.catalog_for_actor() if hasattr(worlds, "catalog_for_actor") else worlds.VOCABULARY,
        "catalog-gap-receipt.json": gap,
        "public-contact.json": {"objective": "Return every unblocked option only when before and after capability identity match; otherwise return an empty list.", "cases": PUBLIC_CASES},
        "property.json": {"property": "replace-me", "description": "Replace this description.", "objective": "Replace this objective.", "operation": "realize_contact"},
        "mutation-envelope.json": {"editable": ["property.json", "operation.py"], "immutable": ["subject-position.json", "active-stake.json", "closed-catalog.json", "catalog-gap-receipt.json", "public-contact.json", "check_extension.py"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "operation.py").write_text("def realize_contact(case):\n    return None\n")
    (seed / "check_extension.py").write_text(AUTHOR_CHECKER)
    (seed / "README.md").write_text("The active stake requires contact the closed property catalog cannot express. Author one new developmental property and its executable contact operation. Edit only property.json and operation.py. realize_contact(case) must satisfy every public-contact case without mutating input. Run python3 check_extension.py and your own public checks, inspect the exact diff, and report truthfully.\n")
    return seed


def run_author(context, p82, root: Path, subject: dict[str, Any], gap: dict[str, Any]) -> dict[str, Any]:
    label = "developmental-language-extension-author"
    seed = author_seed(root, subject, gap)
    output, base_audit, workspace, _ = context.run_actor(label, seed, AUTHOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        prop = json.loads((workspace / "property.json").read_text())
        source = (workspace / "operation.py").read_text()
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        prop, source, immutable_ok = None, "", False
    operation = load_operation(source)
    public = evaluate(operation, PUBLIC_CASES)
    valid = bool(valid_property(prop) and operation and public["passed"] and immutable_ok and output and output.get("property_id") == prop["property"])
    audit = context.audit_actor(label, output, base_audit, valid, ["operation.py", "property.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0153-bound-developmental-language-extension", "source_subject_digest": subject["artifact_digest"], "gap_receipt_digest": gap["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "property": prop, "operation_source": source, "public_evaluation": public}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "property": prop, "operation_source": source, "public": public, "binding": binding}


def hidden_world(p82, binding: dict[str, Any]) -> dict[str, Any]:
    result = evaluate(load_operation(binding["operation_source"]), HIDDEN_CASES)
    body = {"authority": "ot-0153-independent-extension-consequence", "extension_binding_digest": binding["binding_digest"], "hidden_cases_digest": p82.digest(HIDDEN_CASES), "result": result}
    return {**body, "receipt_digest": p82.digest(body)}


def valid_extended_stake(stake: Any, property_id: str) -> bool:
    return bool(isinstance(stake, dict) and set(stake) == {"stake_id", "property", "question", "rationale", "success_condition", "surrender_condition"} and isinstance(stake["stake_id"], str) and PROPERTY_RE.fullmatch(stake["stake_id"]) and stake["property"] == property_id and all(prior131.valid_text(stake[key]) for key in ["question", "rationale", "success_condition", "surrender_condition"]))


def assimilation_seed(root: Path, subject: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "assimilation-seed"
    seed.mkdir()
    prop = binding["property"]["property"]
    files = {"subject-position.json": worlds.base.active_position(subject), "admitted-extension.json": binding, "world-consequence.json": world, "next-stake.json": {"stake_id": "replace-me", "property": prop, "question": "Replace this question.", "rationale": "Replace this rationale.", "success_condition": "Replace this condition.", "surrender_condition": "Replace this condition."}, "mutation-envelope.json": {"editable": ["next-stake.json"], "immutable": ["subject-position.json", "admitted-extension.json", "world-consequence.json", "check_assimilation.py"]}}
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_assimilation.py").write_text(f'''import json\nfrom pathlib import Path\ns=json.loads(Path("next-stake.json").read_text()); p={prop!r}; keys={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}\nok=set(s)==keys and s.get("property")==p and all(isinstance(s.get(k),str) and s[k].strip() for k in keys)\nprint(json.dumps({{"passed":ok,"property":s.get("property")}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Assimilate the independently admitted language extension and its full world consequence. Author one next developmental stake using exactly the admitted new property. Ground success and surrender in the observed capability. Edit only next-stake.json, run python3 check_assimilation.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_assimilator(context, p82, root: Path, subject: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "developmental-language-extension-assimilator"
    seed = assimilation_seed(root, subject, binding, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATION_SCHEMA, (seed / "README.md").read_text().strip())
    prop = binding["property"]["property"]
    try:
        stake = json.loads((workspace / "next-stake.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        stake, immutable_ok = None, False
    valid = bool(valid_extended_stake(stake, prop) and immutable_ok and output and output.get("property_id") == prop)
    audit = context.audit_actor(label, output, base_audit, valid, ["next-stake.json"])
    result = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0153-bound-extension-assimilation", "source_subject_digest": subject["artifact_digest"], "extension_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "next_stake": stake}
        result = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "stake": stake, "binding": result}


def extended_route(p82, subject: dict[str, Any], stake: dict[str, Any]) -> dict[str, Any] | None:
    prop = stake.get("property") if isinstance(stake, dict) else None
    matches = [row for row in subject.get("developmental_property_extensions", []) if row["property"]["property"] == prop]
    if len(matches) != 1:
        return None
    extension = matches[0]
    body = {"authority": "ot-0153-extension-aware-compiler-v1", "source_subject_digest": subject["artifact_digest"], "property": prop, "extension_binding_digest": extension["binding_digest"], "operation": extension["property"]["operation"]}
    return {**body, "route_digest": p82.digest(body)}


def seal_successor(p82, parent: dict[str, Any], binding: dict[str, Any], world: dict[str, Any], assimilation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    capability_body = {"authority": "ot-0153-admitted-developmental-language-capability", "property": binding["property"], "extension_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
    capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
    receipt_body = {"authority": "ot-0153-developmental-language-expansion-transition", "source_subject_digest": parent["artifact_digest"], "prior_stake": parent["active_developmental_stake"], "capability_digest": capability["capability_digest"], "assimilation_binding_digest": assimilation["binding_digest"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    next_stake = assimilation["next_stake"]
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["developmental_property_extensions"] = [*child.get("developmental_property_extensions", []), binding]
    child["developmental_language_capabilities"] = [*child.get("developmental_language_capabilities", []), capability]
    child["developmental_language_expansion_receipts"] = [*child.get("developmental_language_expansion_receipts", []), receipt]
    child["active_developmental_stake"] = next_stake
    opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = next_stake["question"]
    return p82.seal(child), receipt


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    gap = catalog_gap(p82, parent)
    checks = {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open", "active_stake_grounded": "capability" in parent["active_developmental_stake"]["question"].lower() and "reset" in parent["active_developmental_stake"]["question"].lower(), "catalog_exact_closed": set(worlds.PROPERTIES) == {"continuity-under-reset", "option-expansion", "correction-from-error"}, "mismatch_names_every_gap": len(gap["existing_property_gaps"]) == 3 and all(row["missing"] for row in gap["existing_property_gaps"]), "schemas_present": AUTHOR_SCHEMA.is_file() and ASSIMILATION_SCHEMA.is_file(), "known_good_operation_passes": evaluate(lambda case: [item for item in case["options"] if item not in case["blocked"]] if case["before"] == case["after"] else [], HIDDEN_CASES)["passed"], "bad_operation_fails": not evaluate(lambda case: [item for item in case["options"] if item not in case["blocked"]], HIDDEN_CASES)["passed"]}
    checks["passed"] = all(checks.values())
    return {"checks": checks, "gap": gap}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0153").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0152", "open-subject-after-single-invocation-recurrence.json")
    fixtures = preflight(p82, parent)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0153 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    author_root = run / "extension-author"
    author_root.mkdir()
    authored = run_author(context, p82, author_root, parent, fixtures["gap"])
    world = hidden_world(p82, authored["binding"]) if authored["binding"] else None
    if world:
        (run / "sealed-hidden-extension-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    assimilation_root = run / "extension-assimilation"
    assimilation_root.mkdir()
    assimilation = run_assimilator(context, p82, assimilation_root, parent, authored["binding"], world) if world and world["result"]["passed"] else None
    final = parent
    transition = None
    if assimilation and assimilation["binding"]:
        final, transition = seal_successor(p82, parent, authored["binding"], world, assimilation["binding"])
    new_stake = final.get("active_developmental_stake")
    closed_binding = {"stake": new_stake, "binding_digest": "control"} if isinstance(new_stake, dict) else None
    closed_route = worlds.compile_route(p82, final, closed_binding, worlds.catalog(p82)) if closed_binding else None
    installed_route = extended_route(p82, final, new_stake)
    controls = {"closed_catalog_route": closed_route, "installed_extension_route": installed_route}
    (run / "post-seal-compiler-controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True) + "\n")
    checks = {"two_fresh_accepted_actors": bool(authored["binding"] and assimilation and assimilation["binding"] and prior131.audit_accepted(authored["audit"]) and prior131.audit_accepted(assimilation["audit"])), "new_property_outside_catalog": bool(authored["binding"] and authored["property"]["property"] not in worlds.PROPERTIES), "public_contact_passes": authored["public"]["passed"] and authored["public"]["pass_count"] == 3, "hidden_consequence_passes": bool(world and world["result"]["passed"] and world["result"]["pass_count"] == 3), "consequence_authors_new_property_stake": bool(assimilation and assimilation["binding"] and assimilation["stake"]["property"] == authored["property"]["property"]), "closed_compiler_cannot_route": closed_route is None, "extension_compiler_routes_exact_package": bool(installed_route and installed_route["extension_binding_digest"] == authored["binding"]["binding_digest"]), "parent_retained_exactly": all(final.get(key) == parent.get(key) for key in parent if key != "artifact_digest" and key not in {"active_developmental_stake", "active_pursuit", "continuation", "unresolved"}), "extension_installed": bool(final.get("developmental_property_extensions", [])[-1] == authored["binding"] and final.get("developmental_language_capabilities")), "actor_authored_opening": bool(assimilation and final["active_developmental_stake"] == assimilation["stake"] and assimilation["stake"]["question"] in final["continuation"]["next_opening"]), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0153-consequence-authorized-language-expansion", "source_subject_digest": parent["artifact_digest"], "catalog_gap": fixtures["gap"], "authored_extension": p82.compact(authored), "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "transition_receipt": transition, "controls": controls, "checks": checks, "language_expansion_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum(item is not None for item in [authored, assimilation]), "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
