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
BASE_PATH = ROOT / "ot_0154_exact_developmental_extension_reuse.py"
BASE_SHA256 = "5920fab1ccaf647aaf7a57bbfe6e63623cfaddfec2c76b0b6e59a8ed3c9b53f7"
PARENT_DIGEST = "7e82de5d4e26787fa4962ff587381c8222e39cdad6c3ebe833584cd5abb89675"
CORRECTION_SCHEMA = REPO / "spec/ot-0155-extension-correction.schema.json"
ASSIMILATION_SCHEMA = REPO / "spec/ot-0153-expansion-assimilation.schema.json"

PUBLIC_CONTRADICTIONS = [
    {"case_id": "compat-public-a", "before": "selector-v1", "after": "selector-v2", "compatible": True, "options": ["reuse", "inspect", "discard"], "blocked": ["discard"], "expected": ["reuse", "inspect"]},
    {"case_id": "compat-public-b", "before": "carrier-v3", "after": "carrier-v3", "compatible": False, "options": ["continue", "audit"], "blocked": [], "expected": []},
    {"case_id": "compat-public-c", "before": "contact-v4", "after": "contact-v4", "compatible": True, "options": ["probe", "renew", "erase"], "blocked": ["erase"], "expected": ["probe", "renew"]},
]
HIDDEN_CONTRADICTIONS = [
    {"case_id": "compat-hidden-a", "before": "program-v5", "after": "program-v6", "compatible": True, "options": ["transfer", "verify", "rollback"], "blocked": ["rollback"], "expected": ["transfer", "verify"]},
    {"case_id": "compat-hidden-b", "before": "memory-v7", "after": "memory-v7", "compatible": False, "options": ["retain", "branch"], "blocked": [], "expected": []},
    {"case_id": "compat-hidden-c", "before": "route-v8", "after": "route-v9", "compatible": True, "options": ["left", "right", "blocked"], "blocked": ["blocked"], "expected": ["left", "right"]},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0154 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0155_frozen_ot0154", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
extension_base = previous.previous
worlds = previous.worlds
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def floor_cases() -> list[dict[str, Any]]:
    return [
        *copy.deepcopy(extension_base.PUBLIC_CASES),
        *copy.deepcopy(extension_base.HIDDEN_CASES),
        *copy.deepcopy(previous.PUBLIC_CASES),
        *copy.deepcopy(previous.HIDDEN_CASES),
    ]


def corrected_example(case: dict[str, Any]) -> list[Any]:
    compatible = case["compatible"] if "compatible" in case else case["before"] == case["after"]
    return [item for item in case["options"] if item not in case["blocked"]] if compatible else []


CORRECTION_CHECKER = '''import ast,json
from pathlib import Path
s=Path("operation.py").read_text()
try: names={n.name for n in ast.walk(ast.parse(s)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
except SyntaxError: names=set()
ok="realize_contact" in names
print(json.dumps({"passed":ok},sort_keys=True)); raise SystemExit(0 if ok else 2)
'''


def correction_seed(root: Path, subject: dict[str, Any], extension: dict[str, Any], retained_public: dict[str, Any]) -> Path:
    seed = root / "correction-seed"
    seed.mkdir()
    files = {
        "subject-position.json": worlds.base.active_position(subject),
        "active-correction-stake.json": subject["active_developmental_stake"],
        "retained-property.json": extension["property"],
        "retained-source-identity.json": {"binding_digest": extension["binding_digest"], "source_sha256": hashlib.sha256(extension["operation_source"].encode()).hexdigest()},
        "prior-floor.json": {"cases": floor_cases(), "retained_evaluation": extension_base.evaluate(extension_base.load_operation(extension["operation_source"]), floor_cases())},
        "public-contradiction.json": {"authority": "ot-0155-public-compatibility-contradiction", "cases": PUBLIC_CONTRADICTIONS, "retained_evaluation": retained_public},
        "mutation-envelope.json": {"editable": ["operation.py"], "immutable": ["subject-position.json", "active-correction-stake.json", "retained-property.json", "retained-source-identity.json", "prior-floor.json", "public-contradiction.json", "check_correction.py"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "operation.py").write_text(extension["operation_source"])
    (seed / "check_correction.py").write_text(CORRECTION_CHECKER)
    (seed / "README.md").write_text("Correct the retained extension from the public compatibility contradiction while preserving every prior floor case. When compatible is present it is authoritative; otherwise preserve the old exact-identity rule. Edit only operation.py, run python3 check_correction.py and your own public/floor checks, inspect the exact diff, and report truthfully.\n")
    return seed


def run_corrector(context, p82, root: Path, subject: dict[str, Any], extension: dict[str, Any], retained_public: dict[str, Any]) -> dict[str, Any]:
    label = "developmental-extension-contradiction-corrector"
    seed = correction_seed(root, subject, extension, retained_public)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        source = (workspace / "operation.py").read_text()
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        source, immutable_ok = "", False
    operation = extension_base.load_operation(source)
    public = extension_base.evaluate(operation, PUBLIC_CONTRADICTIONS)
    floor = extension_base.evaluate(operation, floor_cases())
    valid = bool(operation and source != extension["operation_source"] and public["passed"] and public["pass_count"] == 3 and floor["passed"] and floor["pass_count"] == 12 and immutable_ok and output and output.get("action") == "correct-retained-extension")
    audit = context.audit_actor(label, output, base_audit, valid, ["operation.py"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0155-bound-corrected-developmental-extension", "source_subject_digest": subject["artifact_digest"], "parent_extension_binding_digest": extension["binding_digest"], "actor_patch_digest": audit["patch_digest"], "property": extension["property"], "operation_source": source, "public_contradiction_evaluation": public, "prior_floor_evaluation": floor}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "operation_source": source, "public": public, "floor": floor, "binding": binding}


def hidden_world(p82, binding: dict[str, Any]) -> dict[str, Any]:
    operation = extension_base.load_operation(binding["operation_source"])
    contradiction = extension_base.evaluate(operation, HIDDEN_CONTRADICTIONS)
    floor = extension_base.evaluate(operation, floor_cases())
    body = {"authority": "ot-0155-independent-corrected-extension-consequence", "correction_binding_digest": binding["binding_digest"], "hidden_cases_digest": p82.digest(HIDDEN_CONTRADICTIONS), "floor_cases_digest": p82.digest(floor_cases()), "contradiction_result": contradiction, "prior_floor_result": floor}
    return {**body, "receipt_digest": p82.digest(body)}


def assimilation_seed(root: Path, subject: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "assimilation-seed"
    seed.mkdir()
    current = subject["active_developmental_stake"]["property"]
    vocabulary = {**worlds.VOCABULARY, binding["property"]["property"]: binding["property"]["description"]}
    files = {"subject-position.json": worlds.base.active_position(subject), "completed-correction-stake.json": subject["active_developmental_stake"], "corrected-extension.json": binding, "world-consequence.json": world, "developmental-property-vocabulary.json": vocabulary, "next-stake.json": {"stake_id": "replace-me", "property": binding["property"]["property"], "question": "Replace this question.", "rationale": "Replace this rationale.", "success_condition": "Replace this condition.", "surrender_condition": "Replace this condition."}, "mutation-envelope.json": {"editable": ["next-stake.json"], "immutable": ["subject-position.json", "completed-correction-stake.json", "corrected-extension.json", "world-consequence.json", "developmental-property-vocabulary.json", "check_assimilation.py"]}}
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    allowed = sorted(vocabulary)
    (seed / "check_assimilation.py").write_text(f'''import json,re\nfrom pathlib import Path\ns=json.loads(Path("next-stake.json").read_text()); allowed=set({allowed!r}); current={current!r}; keys={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}\nok=set(s)==keys and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and s.get("property") in allowed and s.get("property")!=current and all(isinstance(s.get(k),str) and s[k].strip() for k in ["question","rationale","success_condition","surrender_condition"])\nprint(json.dumps({{"passed":bool(ok),"property":s.get("property")}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Assimilate the corrected extension's independent hidden consequence. Retire correction-from-error and author one different routeable next stake grounded in both the new compatibility result and the preserved prior floor. Edit only next-stake.json, run python3 check_assimilation.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_assimilator(context, p82, root: Path, subject: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "corrected-developmental-extension-assimilator"
    seed = assimilation_seed(root, subject, binding, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATION_SCHEMA, (seed / "README.md").read_text().strip())
    allowed = set(worlds.PROPERTIES) | {binding["property"]["property"]}
    current = subject["active_developmental_stake"]["property"]
    try:
        stake = json.loads((workspace / "next-stake.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        stake, immutable_ok = None, False
    valid = bool(previous.valid_next_stake(stake, current, allowed) and immutable_ok and output and output.get("property_id") == stake["property"])
    audit = context.audit_actor(label, output, base_audit, valid, ["next-stake.json"])
    result = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0155-bound-corrected-extension-assimilation", "source_subject_digest": subject["artifact_digest"], "correction_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "next_stake": stake}
        result = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "stake": stake, "binding": result}


def seal_successor(p82, parent: dict[str, Any], old: dict[str, Any], corrected: dict[str, Any], world: dict[str, Any], assimilation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    capability_body = {"authority": "ot-0155-contradiction-corrected-extension-capability", "property": corrected["property"]["property"], "parent_extension_binding_digest": old["binding_digest"], "corrected_extension_binding_digest": corrected["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
    capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
    receipt_body = {"authority": "ot-0155-corrected-extension-transition", "source_subject_digest": parent["artifact_digest"], "capability_digest": capability["capability_digest"], "assimilation_binding_digest": assimilation["binding_digest"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    next_stake = assimilation["next_stake"]
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["developmental_property_extensions"] = [corrected if row["binding_digest"] == old["binding_digest"] else row for row in child["developmental_property_extensions"]]
    child["developmental_property_extension_corrections"] = [*child.get("developmental_property_extension_corrections", []), {"parent": old, "corrected": corrected, "world_receipt_digest": world["receipt_digest"]}]
    child["developmental_extension_correction_capabilities"] = [*child.get("developmental_extension_correction_capabilities", []), capability]
    child["developmental_extension_correction_receipts"] = [*child.get("developmental_extension_correction_receipts", []), receipt]
    child["active_developmental_stake"] = next_stake
    opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = next_stake["question"]
    return p82.seal(child), receipt


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    extension = parent["developmental_property_extensions"][0]
    retained = extension_base.load_operation(extension["operation_source"])
    retained_public = extension_base.evaluate(retained, PUBLIC_CONTRADICTIONS)
    retained_hidden = extension_base.evaluate(retained, HIDDEN_CONTRADICTIONS)
    retained_floor = extension_base.evaluate(retained, floor_cases())
    corrected_public = extension_base.evaluate(corrected_example, PUBLIC_CONTRADICTIONS)
    corrected_hidden = extension_base.evaluate(corrected_example, HIDDEN_CONTRADICTIONS)
    corrected_floor = extension_base.evaluate(corrected_example, floor_cases())
    checks = {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open", "active_correction_stake": parent["active_developmental_stake"]["property"] == "correction-from-error", "retained_extension_exact": len(parent["developmental_property_extensions"]) == 1 and extension["property"]["property"] == "identity-gated-branch-filtering", "retained_fails_new_public": not retained_public["passed"] and retained_public["pass_count"] <= 1, "retained_fails_new_hidden": not retained_hidden["passed"] and retained_hidden["pass_count"] <= 1, "retained_preserves_floor": retained_floor["passed"] and retained_floor["pass_count"] == 12, "correction_target_sufficient": corrected_public["passed"] and corrected_hidden["passed"] and corrected_floor["passed"], "schemas_present": CORRECTION_SCHEMA.is_file() and ASSIMILATION_SCHEMA.is_file()}
    checks["passed"] = all(checks.values())
    return {"checks": checks, "retained_public": retained_public, "retained_hidden": retained_hidden, "retained_floor": retained_floor, "corrected_fixture": {"public": corrected_public, "hidden": corrected_hidden, "floor": corrected_floor}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0155").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0154", "open-subject-after-exact-extension-reuse.json")
    fixtures = preflight(p82, parent)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0155 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    old = parent["developmental_property_extensions"][0]
    correction_root = run / "extension-correction"
    correction_root.mkdir()
    correction = run_corrector(context, p82, correction_root, parent, old, fixtures["retained_public"])
    world = hidden_world(p82, correction["binding"]) if correction["binding"] else None
    if world:
        (run / "sealed-hidden-correction-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    assimilation_root = run / "correction-assimilation"
    assimilation_root.mkdir()
    assimilation = run_assimilator(context, p82, assimilation_root, parent, correction["binding"], world) if world and world["contradiction_result"]["passed"] and world["prior_floor_result"]["passed"] else None
    final = parent
    transition = None
    if assimilation and assimilation["binding"]:
        final, transition = seal_successor(p82, parent, old, correction["binding"], world, assimilation["binding"])
    control_hidden = extension_base.evaluate(extension_base.load_operation(old["operation_source"]), HIDDEN_CONTRADICTIONS)
    control_floor = extension_base.evaluate(extension_base.load_operation(old["operation_source"]), floor_cases())
    next_route = previous.route_any(p82, final, final["active_developmental_stake"])
    controls = {"unchanged_hidden": control_hidden, "unchanged_prior_floor": control_floor, "successor_next_route": next_route}
    (run / "post-seal-unchanged-controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True) + "\n")
    checks = {"two_fresh_accepted_actors": bool(correction["binding"] and assimilation and assimilation["binding"] and prior131.audit_accepted(correction["audit"]) and prior131.audit_accepted(assimilation["audit"])), "corrected_source_differs": bool(correction["binding"] and correction["operation_source"] != old["operation_source"]), "public_correction_and_floor_pass": correction["public"]["passed"] and correction["floor"]["passed"], "hidden_correction_and_floor_pass": bool(world and world["contradiction_result"]["passed"] and world["prior_floor_result"]["passed"]), "unchanged_control_fails_new_hidden": not control_hidden["passed"] and control_hidden["pass_count"] <= 1, "unchanged_control_preserves_floor": control_floor["passed"] and control_floor["pass_count"] == 12, "correction_ancestry_retained": bool(final.get("developmental_property_extension_corrections") and final["developmental_property_extension_corrections"][-1]["parent"] == old), "corrected_extension_installed": bool(correction["binding"] and final["developmental_property_extensions"][0] == correction["binding"]), "parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key != "artifact_digest" and key not in {"developmental_property_extensions", "active_developmental_stake", "active_pursuit", "continuation", "unresolved"}), "different_next_stake_routes": bool(assimilation and assimilation["stake"]["property"] != parent["active_developmental_stake"]["property"] and next_route), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0155-contradiction-corrected-developmental-extension", "source_subject_digest": parent["artifact_digest"], "retained_extension_binding_digest": old["binding_digest"], "correction": p82.compact(correction), "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "transition_receipt": transition, "post_seal_controls": controls, "checks": checks, "extension_correction_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum(item is not None for item in [correction, assimilation]), "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
