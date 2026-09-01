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
BASE_PATH = ROOT / "ot_0160_complete_selector_runtime_reconstruction.py"
BASE_SHA256 = "c990cacfbda3299107ebe13dc76729306fbc8e021ee26312f9d6850d714467c4"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
SELECTOR_SCHEMA = REPO / "spec/ot-0158-selector-correction.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0160 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0161_frozen_ot0160", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
selector_base = previous.selector_base
base = previous.base
prior131 = selector_base.prior131
base130 = selector_base.base130


def hidden_portfolios() -> list[dict[str, Any]]:
    candidates = selector_base.CANDIDATES
    stake = selector_base.stake
    return [
        {
            "case_id": "corrected-hidden-restart-learned-gate",
            "stake": stake(
                "restart-learned-gate",
                "continuity-under-reset",
                "After restart, restore the learned compatibility gate and replay every previously certified check.",
            ),
            "candidates": [candidates[0], candidates[2], candidates[1], candidates[3]],
            "expected": "corrected-identity-gated-extension",
        },
        {
            "case_id": "corrected-hidden-amended-identity-logic",
            "stake": stake(
                "amended-identity-logic",
                "correction-from-error",
                "Use the amended branch identity logic to supersede the stale choice without dropping earlier guarantees.",
            ),
            "candidates": [candidates[2], candidates[3], candidates[0], candidates[1]],
            "expected": "corrected-identity-gated-extension",
        },
        {
            "case_id": "corrected-hidden-learned-identity-screen",
            "stake": stake(
                "learned-identity-screen",
                "option-expansion",
                "Enumerate viable choices through the learned identity screen and keep the established regression suite intact.",
            ),
            "candidates": [candidates[1], candidates[0], candidates[3], candidates[2]],
            "expected": "corrected-identity-gated-extension",
        },
        {
            "case_id": "corrected-hidden-restore-amended-filter",
            "stake": stake(
                "restore-amended-filter",
                "continuity-under-reset",
                "After a reset, restore the amended filter and all behavior it had already earned.",
            ),
            "candidates": [candidates[3], candidates[1], candidates[2], candidates[0]],
            "expected": "corrected-identity-gated-extension",
        },
        {
            "case_id": "corrected-hidden-ordinary-retained-token",
            "stake": stake(
                "retained-token",
                "continuity-under-reset",
                "Carry one retained opaque token through process reset.",
            ),
            "candidates": [candidates[2], candidates[3], candidates[0], candidates[1]],
            "expected": "reset-carrier",
        },
        {
            "case_id": "corrected-hidden-ordinary-exits",
            "stake": stake(
                "permitted-exits",
                "option-expansion",
                "List every currently permitted exit from the option set.",
            ),
            "candidates": [candidates[0], candidates[1], candidates[3], candidates[2]],
            "expected": "viable-branch-carrier",
        },
        {
            "case_id": "corrected-hidden-ordinary-latency",
            "stake": stake(
                "measured-latency",
                "correction-from-error",
                "Update a numerical forecast to the measured latency.",
            ),
            "candidates": [candidates[3], candidates[0], candidates[2], candidates[1]],
            "expected": "prediction-corrector",
        },
        {
            "case_id": "corrected-hidden-ordinary-compatibility-prediction",
            "stake": stake(
                "compatibility-prediction",
                "correction-from-error",
                "Replace the stale compatibility prediction with the observed boolean.",
            ),
            "candidates": [candidates[1], candidates[2], candidates[0], candidates[3]],
            "expected": "prediction-corrector",
        },
    ]


RUNTIME_SOURCE = '''import ast
import re

SAFE_BUILTINS = {"all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate, "isinstance": isinstance, "len": len, "list": list, "max": max, "min": min, "next": next, "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip}

def _import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "re" and level == 0 and not fromlist:
        return re
    raise ImportError("selector source may import only re")

def load_selector(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    exact = len(imports) == 1 and isinstance(imports[0], ast.Import) and len(imports[0].names) == 1 and imports[0].names[0].name == "re" and imports[0].names[0].asname is None
    forbidden = (ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.Try, ast.Raise)
    if not exact or any(isinstance(node, forbidden) for node in ast.walk(tree)):
        return None
    if any(isinstance(node, ast.Name) and node.id.startswith("__") for node in ast.walk(tree)) or any(isinstance(node, ast.Attribute) and node.attr.startswith("__") for node in ast.walk(tree)):
        return None
    namespace = {"__builtins__": {**SAFE_BUILTINS, "__import__": _import}}
    try:
        exec(compile(tree, "<mechanism-selector>", "exec"), namespace)
    except Exception:
        return None
    function = namespace.get("choose_mechanism")
    return function if callable(function) else None
'''


CHECKER_SOURCE = '''import copy,json
from pathlib import Path
from selector_runtime import load_selector

cases=json.loads(Path("correction-portfolios.json").read_text())
selector=load_selector(Path("selector.py").read_text())
rows=[]
for case in cases:
    before=copy.deepcopy(case)
    try: observed=selector(copy.deepcopy(case["stake"]),copy.deepcopy(case["candidates"])) if selector else None
    except Exception: observed=None
    ids={row["mechanism_id"] for row in case["candidates"]}
    rows.append({"case_id":case["case_id"],"observed":observed,"expected":case["expected"],"presented_id":observed in ids,"input_unchanged":case==before,"passed":observed==case["expected"] and case==before})
result={"rows":rows,"pass_count":sum(row["passed"] for row in rows),"case_count":len(rows)}
result["passed"]=bool(rows and result["pass_count"]==len(rows))
print(json.dumps(result,indent=2,sort_keys=True)); raise SystemExit(0 if result["passed"] else 2)
'''


def seed_workspace(
    root: Path,
    parent: dict[str, Any],
    source: str,
    binding: dict[str, Any],
    consequence: dict[str, Any],
    cases: list[dict[str, Any]],
) -> Path:
    seed = root / "selector-seed"
    seed.mkdir()
    files: dict[str, Any] = {
        "subject-position.json": selector_base.worlds.base.active_position(parent),
        "prior-selector-binding.json": binding,
        "selector-consequence.json": consequence,
        "candidate-mechanisms.json": selector_base.CANDIDATES,
        "correction-portfolios.json": cases,
        "mutation-envelope.json": {
            "editable": ["selector.py"],
            "immutable": [
                "subject-position.json",
                "prior-selector-binding.json",
                "selector-consequence.json",
                "candidate-mechanisms.json",
                "correction-portfolios.json",
                "selector_runtime.py",
                "check_selector.py",
            ],
        },
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "selector.py").write_text(source)
    (seed / "selector_runtime.py").write_text(RUNTIME_SOURCE)
    (seed / "check_selector.py").write_text(CHECKER_SOURCE)
    (seed / "README.md").write_text(
        "Correct the exact retained mechanism selector from its objective 4/6 consequence. "
        "It over-relies on exact capability phrases and misses paraphrased dependencies. "
        "Edit only selector.py. The published runtime admits exactly import re and the listed safe builtins, including next. "
        "choose_mechanism(stake,candidates) must return one presented mechanism_id, preserve inputs, and pass all 10 correction portfolios. "
        "Run python3 check_selector.py, inspect the exact diff, and report truthfully.\n"
    )
    return seed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0161").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    failed = selector_base.load_artifact(p82, repo, store, "OT-0160", "complete-selector-runtime-reconstruction-aggregate.json")
    source = failed["reconstructed_binding"]["selector_source"]
    binding = failed["reconstructed_binding"]
    known_public, known_hidden = selector_base.portfolios(parent["active_developmental_stake"])
    correction_cases = [*known_public, *known_hidden]
    hidden = hidden_portfolios()
    old_known = selector_base.evaluate(previous.load_selector(source), correction_cases)
    old_hidden = selector_base.evaluate(previous.load_selector(source), hidden)
    property_hidden = selector_base.evaluate(selector_base.property_only, hidden)
    fixtures = {
        "checks": {
            "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
            "exact_failed_binding": binding["binding_digest"] == failed["hidden_world"]["selector_binding_digest"],
            "sealed_consequence_4_of_6": failed["hidden_world"]["result"]["pass_count"] == 4 and not failed["hidden_world"]["result"]["passed"],
            "known_floor_8_of_10": old_known["pass_count"] == 8 and not old_known["passed"],
            "old_hidden_4_of_8": old_hidden["pass_count"] == 4 and not old_hidden["passed"],
            "property_hidden_4_of_8": property_hidden["pass_count"] == 4 and not property_hidden["passed"],
            "schema_present": SELECTOR_SCHEMA.is_file(),
        }
    }
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "old_known": old_known, "old_hidden": old_hidden, "property_hidden": property_hidden}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0161 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    actor_root = run / "selector-correction"
    actor_root.mkdir()
    seed = seed_workspace(actor_root, parent, source, binding, failed["hidden_world"], correction_cases)
    label = "consequence-corrected-mechanism-selector"
    output, base_audit, workspace, _ = context.run_actor(label, seed, SELECTOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        corrected_source = (workspace / "selector.py").read_text()
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        corrected_source, immutable_ok = "", False
    corrected_selector = previous.load_selector(corrected_source)
    corrected_known = selector_base.evaluate(corrected_selector, correction_cases)
    valid = bool(corrected_selector and corrected_source != source and corrected_known["passed"] and immutable_ok and output and output.get("action") == "correct-mechanism-selector")
    audit = context.audit_actor(label, output, base_audit, valid, ["selector.py"])
    corrected_binding = None
    if valid and prior131.audit_accepted(audit):
        body = {
            "authority": "ot-0161-bound-consequence-corrected-mechanism-selector",
            "source_subject_digest": parent["artifact_digest"],
            "parent_selector_binding_digest": binding["binding_digest"],
            "contradiction_receipt_digest": failed["hidden_world"]["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "selector_source": corrected_source,
            "known_result": corrected_known,
        }
        corrected_binding = {**body, "binding_digest": p82.digest(body)}
    corrected_hidden = selector_base.evaluate(corrected_selector, hidden) if corrected_binding else None
    world = None
    if corrected_hidden:
        body = {
            "authority": "ot-0161-independent-corrected-selector-consequence",
            "selector_binding_digest": corrected_binding["binding_digest"],
            "hidden_portfolios_digest": p82.digest(hidden),
            "result": corrected_hidden,
        }
        world = {**body, "receipt_digest": p82.digest(body)}
        (run / "sealed-hidden-corrected-selector-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")

    final = parent
    capability = correction = None
    if world and world["result"]["passed"]:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        correction_body = {"authority": "ot-0161-selector-correction-ancestry", "parent_selector": binding, "corrected_selector_binding_digest": corrected_binding["binding_digest"], "contradiction_receipt_digest": failed["hidden_world"]["receipt_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0161-consequence-corrected-selector-capability", "selector_binding_digest": corrected_binding["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = corrected_binding
        final = p82.seal(child)

    erased = copy.deepcopy(final)
    erased["active_developmental_mechanism_selector"] = None
    erased_choice = previous.installed_choice(erased, parent["active_developmental_stake"], selector_base.CANDIDATES)
    installed_choice = previous.installed_choice(final, parent["active_developmental_stake"], selector_base.CANDIDATES)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "developmental_mechanism_selector_capabilities", "developmental_mechanism_selector_corrections"}
    checks = {
        "fresh_corrector_accepted": bool(corrected_binding and prior131.audit_accepted(audit)),
        "source_changed": corrected_source != source,
        "known_floor_10_of_10": corrected_known["passed"] and corrected_known["pass_count"] == 10,
        "hidden_8_of_8": bool(world and world["result"]["passed"] and world["result"]["pass_count"] == 8),
        "unchanged_selector_4_of_8": old_hidden["pass_count"] == 4 and not old_hidden["passed"],
        "property_selector_4_of_8": property_hidden["pass_count"] == 4 and not property_hidden["passed"],
        "selector_erasure_blocks_dependency_route": erased_choice is None,
        "installed_selector_routes_current_stake": installed_choice == "corrected-identity-gated-extension",
        "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"],
        "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized),
        "correction_ancestry_installed": correction is not None and final.get("developmental_mechanism_selector_corrections", [])[-1] == correction,
        "selector_capability_installed": capability is not None and final.get("developmental_mechanism_selector_capabilities", [])[-1] == capability,
        "selector_installed": corrected_binding is not None and final.get("active_developmental_mechanism_selector") == corrected_binding,
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0161-consequence-corrected-mechanism-selector",
        "source_subject_digest": parent["artifact_digest"],
        "parent_selector_binding_digest": binding["binding_digest"],
        "correction": {"output": output, "audit": audit, "binding": corrected_binding, "known_result": corrected_known},
        "hidden_world": world,
        "post_seal_unchanged_selector_control": old_hidden,
        "post_seal_property_only_control": property_hidden,
        "selector_erasure_control": {"observed": erased_choice, "passed": erased_choice is None},
        "checks": checks,
        "selector_correction_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": 1,
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
