from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0157_property_only_selection_falsifier.py"
BASE_SHA256 = "9cad41817d9db7d0597a6def69b703abf761cc7ef5f94f6be3ce7ef4b242c840"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
SELECTOR_SCHEMA = REPO / "spec/ot-0158-selector-correction.schema.json"
SAFE_BUILTINS = {"all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate, "isinstance": isinstance, "len": len, "list": list, "max": max, "min": min, "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0157 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0158_frozen_ot0157", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
reuse = previous.previous
extension_base = previous.extension_base
worlds = previous.worlds
prior131 = reuse.prior131
base130 = reuse.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


CANDIDATES = [
    {"mechanism_id": "reset-carrier", "properties": ["continuity-under-reset"], "capabilities": ["preserve signal across reset"]},
    {"mechanism_id": "viable-branch-carrier", "properties": ["option-expansion"], "capabilities": ["return every unblocked option"]},
    {"mechanism_id": "prediction-corrector", "properties": ["correction-from-error"], "capabilities": ["replace stale prediction with observed outcome"]},
    {"mechanism_id": "corrected-identity-gated-extension", "properties": ["identity-gated-branch-filtering"], "capabilities": ["corrected extension", "compatibility reuse", "identity gated filtering", "preserve accumulated floor"]},
]


def stake(stake_id: str, prop: str, text: str) -> dict[str, Any]:
    return {"stake_id": stake_id, "property": prop, "question": text, "rationale": text, "success_condition": text, "surrender_condition": "Surrender if objective consequence rejects this requirement."}


def portfolios(current: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    public = [
        {"case_id": "selector-public-current", "stake": current, "candidates": CANDIDATES, "expected": "corrected-identity-gated-extension"},
        {"case_id": "selector-public-reset", "stake": stake("carry-signal", "continuity-under-reset", "Preserve one signal across a destructive reset boundary."), "candidates": list(reversed(CANDIDATES)), "expected": "reset-carrier"},
        {"case_id": "selector-public-branch", "stake": stake("open-options", "option-expansion", "Return every unblocked option without premature closure."), "candidates": [CANDIDATES[3], CANDIDATES[1], CANDIDATES[0], CANDIDATES[2]], "expected": "viable-branch-carrier"},
        {"case_id": "selector-public-dependent", "stake": stake("correct-compatible", "correction-from-error", "Correct the compatibility reuse result with the retained corrected extension while preserving the accumulated floor."), "candidates": [CANDIDATES[2], CANDIDATES[0], CANDIDATES[3], CANDIDATES[1]], "expected": "corrected-identity-gated-extension"},
    ]
    hidden = [
        {"case_id": "selector-hidden-extension-a", "stake": stake("carry-learned-suite", "continuity-under-reset", "Carry the compatibility-certified extension through reset and revalidate the full learned floor."), "candidates": [CANDIDATES[0], CANDIDATES[2], CANDIDATES[1], CANDIDATES[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "selector-hidden-extension-b", "stake": stake("expand-with-gate", "option-expansion", "Expand viable branches using identity gated filtering from the corrected extension without losing accumulated evidence."), "candidates": [CANDIDATES[1], CANDIDATES[3], CANDIDATES[2], CANDIDATES[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "selector-hidden-extension-c", "stake": stake("repair-compatible-choice", "correction-from-error", "Repair a stale compatibility choice through the retained extension and preserve its floor."), "candidates": [CANDIDATES[2], CANDIDATES[1], CANDIDATES[0], CANDIDATES[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "selector-hidden-reset", "stake": stake("reset-token", "continuity-under-reset", "Carry one opaque token across reset."), "candidates": [CANDIDATES[3], CANDIDATES[2], CANDIDATES[0], CANDIDATES[1]], "expected": "reset-carrier"},
        {"case_id": "selector-hidden-branch", "stake": stake("branch-set", "option-expansion", "Expose all unblocked members of the option set."), "candidates": [CANDIDATES[0], CANDIDATES[3], CANDIDATES[1], CANDIDATES[2]], "expected": "viable-branch-carrier"},
        {"case_id": "selector-hidden-error", "stake": stake("replace-prediction", "correction-from-error", "Replace the stale prediction with the observed value."), "candidates": [CANDIDATES[1], CANDIDATES[0], CANDIDATES[3], CANDIDATES[2]], "expected": "prediction-corrector"},
    ]
    return public, hidden


def load_selector(source: str) -> Callable[..., Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    forbidden = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.Try, ast.Raise)
    if any(isinstance(node, forbidden) for node in ast.walk(tree)) or any(isinstance(node, ast.Name) and node.id.startswith("__") for node in ast.walk(tree)):
        return None
    namespace: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    try:
        exec(compile(tree, "<mechanism-selector>", "exec"), namespace)
    except Exception:
        return None
    function = namespace.get("choose_mechanism")
    return function if callable(function) else None


def evaluate(selector: Callable[..., Any] | None, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        before = copy.deepcopy(case)
        try:
            observed = selector(copy.deepcopy(case["stake"]), copy.deepcopy(case["candidates"])) if selector else None
        except Exception:
            observed = None
        ids = {row["mechanism_id"] for row in case["candidates"]}
        rows.append({"case_id": case["case_id"], "observed": observed, "expected": case["expected"], "presented_id": observed in ids, "input_unchanged": case == before, "passed": observed == case["expected"] and case == before})
    return {"rows": rows, "pass_count": sum(row["passed"] for row in rows), "case_count": len(rows), "passed": bool(rows and all(row["passed"] for row in rows))}


def property_only(stake_value: dict[str, Any], candidates: list[dict[str, Any]]) -> str | None:
    return next((row["mechanism_id"] for row in candidates if stake_value["property"] in row["properties"]), None)


CHECKER = '''import ast,json\nfrom pathlib import Path\ns=Path("selector.py").read_text()\ntry: names={n.name for n in ast.walk(ast.parse(s)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}\nexcept SyntaxError: names=set()\nok="choose_mechanism" in names; print(json.dumps({"passed":ok},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''


def seed_workspace(root: Path, subject: dict[str, Any], public: list[dict[str, Any]], failure: dict[str, Any]) -> Path:
    seed = root / "selector-seed"
    seed.mkdir()
    files = {"subject-position.json": worlds.base.active_position(subject), "selection-failure.json": failure, "candidate-mechanisms.json": CANDIDATES, "public-portfolios.json": public, "selector.py": "def choose_mechanism(stake, candidates):\n    return next((row['mechanism_id'] for row in candidates if stake['property'] in row['properties']), None)\n", "mutation-envelope.json": {"editable": ["selector.py"], "immutable": ["subject-position.json", "selection-failure.json", "candidate-mechanisms.json", "public-portfolios.json", "check_selector.py"]}}
    for name, value in files.items():
        if name == "selector.py": (seed / name).write_text(value)
        else: (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_selector.py").write_text(CHECKER)
    (seed / "README.md").write_text("Correct the retained property-only mechanism selector so substantive stake dependencies can override a coarse property while ordinary property routes remain intact. Edit only selector.py. choose_mechanism(stake,candidates) must return one presented mechanism_id, preserve inputs, and pass every public portfolio. Run python3 check_selector.py and your own public checks, inspect the exact diff, and report truthfully.\n")
    return seed


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0158").resolve()
    prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    failure = load_artifact(p82, repo, store, "OT-0157", "property-only-selection-falsifier-aggregate.json")
    public, hidden = portfolios(parent["active_developmental_stake"])
    old_public, old_hidden = evaluate(property_only, public), evaluate(property_only, hidden)
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open", "failure_exact": failure["source_subject_digest"] == parent["artifact_digest"] and failure["property_only_selection_falsified"], "old_selector_public_partial": old_public["pass_count"] == 2, "old_selector_hidden_balanced": old_hidden["pass_count"] == 3, "schema_present": SELECTOR_SCHEMA.is_file(), "parent_identity": runtime.identity_conforms(parent)}}; fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "old_public": old_public, "old_hidden": old_hidden}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0158 evidence")
    run.mkdir(parents=True); (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    actor_root = run / "selector-correction"; actor_root.mkdir(); seed = seed_workspace(actor_root, parent, public, failure)
    label = "dependency-aware-mechanism-selector-corrector"; output, base_audit, workspace, _ = context.run_actor(label, seed, SELECTOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        source = (workspace / "selector.py").read_text(); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): source, immutable_ok = "", False
    selector = load_selector(source); public_result = evaluate(selector, public); valid = bool(selector and public_result["passed"] and immutable_ok and output and output.get("action") == "correct-mechanism-selector")
    audit = context.audit_actor(label, output, base_audit, valid, ["selector.py"]); binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0158-bound-dependency-aware-mechanism-selector", "source_subject_digest": parent["artifact_digest"], "failure_receipt_digest": failure["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "selector_source": source, "public_result": public_result}; binding = {**body, "binding_digest": p82.digest(body)}
    hidden_result = evaluate(selector, hidden) if binding else None
    world = None
    if hidden_result:
        body = {"authority": "ot-0158-independent-selector-consequence", "selector_binding_digest": binding["binding_digest"], "hidden_portfolios_digest": p82.digest(hidden), "result": hidden_result}; world = {**body, "receipt_digest": p82.digest(body)}; (run / "sealed-hidden-selector-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    final = parent
    if world and world["result"]["passed"]:
        child = copy.deepcopy(parent); child.pop("artifact_digest", None); capability_body = {"authority": "ot-0158-dependency-aware-selector-capability", "selector_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"]}; capability = {**capability_body, "capability_digest": p82.digest(capability_body)}; child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]; child["active_developmental_mechanism_selector"] = binding; final = p82.seal(child)
    control = evaluate(property_only, hidden)
    checks = {"fresh_actor_accepted": bool(binding and prior131.audit_accepted(audit)), "public_4_of_4": public_result["passed"] and public_result["pass_count"] == 4, "hidden_6_of_6": bool(world and world["result"]["passed"] and world["result"]["pass_count"] == 6), "old_selector_3_of_6": control["pass_count"] == 3 and not control["passed"], "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key != "artifact_digest"), "selector_installed": final.get("active_developmental_mechanism_selector") == binding, "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}; checks["passed"] = all(checks.values())
    result = {"authority": "ot-0158-dependency-aware-mechanism-selector", "source_subject_digest": parent["artifact_digest"], "selector": {"output": output, "audit": audit, "binding": binding, "public": public_result}, "hidden_world": world, "post_seal_property_only_control": control, "checks": checks, "selector_correction_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1}; result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n"); (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n"); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
