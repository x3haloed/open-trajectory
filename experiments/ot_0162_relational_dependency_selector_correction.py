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
BASE_PATH = ROOT / "ot_0161_consequence_corrected_mechanism_selector.py"
BASE_SHA256 = "522fce8e50ab3068b0c923037c12d1aaee40a6fcf767ce0999b37807bb845b47"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
SELECTOR_SCHEMA = REPO / "spec/ot-0158-selector-correction.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0161 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0162_frozen_ot0161", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
runtime_base = previous.previous
selector_base = previous.selector_base
base = previous.base
prior131 = previous.prior131
base130 = previous.base130


def hidden_portfolios() -> list[dict[str, Any]]:
    c = selector_base.CANDIDATES
    stake = selector_base.stake
    return [
        {"case_id": "relational-hidden-reestablish-admission", "stake": stake("reestablish-admission", "continuity-under-reset", "After restart, reestablish the previously accepted admission test and rerun every guarantee it had earned."), "candidates": [c[0], c[2], c[3], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "relational-hidden-revised-membership", "stake": stake("revised-membership", "correction-from-error", "Apply the revised membership decision instead of the obsolete forecast without sacrificing earlier certified checks."), "candidates": [c[2], c[1], c[0], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "relational-hidden-accepted-equivalence", "stake": stake("accepted-equivalence", "option-expansion", "Widen choices through the accepted equivalence test while retaining every result already established."), "candidates": [c[1], c[3], c[2], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "relational-hidden-revised-admissibility", "stake": stake("revised-admissibility", "continuity-under-reset", "Survive reset with the revised branch admissibility behavior and all of its regression protections."), "candidates": [c[3], c[0], c[1], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "relational-hidden-learned-membership-floor", "stake": stake("learned-membership-floor", "correction-from-error", "Use the learned membership rule to repair the choice while keeping the complete previously passing suite."), "candidates": [c[0], c[2], c[1], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "relational-hidden-ordinary-learned-token", "stake": stake("learned-token", "continuity-under-reset", "Carry one learned opaque token across reset."), "candidates": [c[3], c[1], c[0], c[2]], "expected": "reset-carrier"},
        {"case_id": "relational-hidden-ordinary-gated-options", "stake": stake("gated-options", "option-expansion", "List the options that pass one current gate."), "candidates": [c[0], c[3], c[1], c[2]], "expected": "viable-branch-carrier"},
        {"case_id": "relational-hidden-ordinary-amended-forecast", "stake": stake("amended-forecast", "correction-from-error", "Amend the numerical forecast to the measured value while retaining its units."), "candidates": [c[1], c[0], c[3], c[2]], "expected": "prediction-corrector"},
        {"case_id": "relational-hidden-ordinary-compatibility-boolean", "stake": stake("compatibility-boolean", "correction-from-error", "Correct one compatibility boolean from its observed outcome."), "candidates": [c[3], c[2], c[0], c[1]], "expected": "prediction-corrector"},
        {"case_id": "relational-hidden-ordinary-retained-branches", "stake": stake("retained-branches", "option-expansion", "Return every unblocked retained branch in the present set."), "candidates": [c[2], c[1], c[3], c[0]], "expected": "viable-branch-carrier"},
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0162").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    failed_160 = selector_base.load_artifact(p82, repo, store, "OT-0160", "complete-selector-runtime-reconstruction-aggregate.json")
    failed_161 = selector_base.load_artifact(p82, repo, store, "OT-0161", "consequence-corrected-mechanism-selector-aggregate.json")
    source = failed_161["correction"]["binding"]["selector_source"]
    binding = failed_161["correction"]["binding"]
    original_public, original_hidden = selector_base.portfolios(parent["active_developmental_stake"])
    known = [*original_public, *original_hidden, *previous.hidden_portfolios()]
    hidden = hidden_portfolios()
    old_selector = runtime_base.load_selector(source)
    old_known = selector_base.evaluate(old_selector, known)
    old_hidden = selector_base.evaluate(old_selector, hidden)
    property_hidden = selector_base.evaluate(selector_base.property_only, hidden)
    fixtures = {"checks": {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "exact_correction_parent": binding["binding_digest"] == failed_161["hidden_world"]["selector_binding_digest"],
        "first_consequence_4_of_6": failed_160["hidden_world"]["result"]["pass_count"] == 4,
        "second_consequence_6_of_8": failed_161["hidden_world"]["result"]["pass_count"] == 6 and not failed_161["hidden_world"]["result"]["passed"],
        "known_floor_16_of_18": old_known["pass_count"] == 16 and not old_known["passed"],
        "old_hidden_frozen_4_of_10": old_hidden["pass_count"] == 4 and old_hidden["case_count"] == 10 and not old_hidden["passed"],
        "property_hidden_frozen_5_of_10": property_hidden["pass_count"] == 5 and property_hidden["case_count"] == 10 and not property_hidden["passed"],
        "schema_present": SELECTOR_SCHEMA.is_file(),
    }}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "old_known": old_known, "old_hidden": old_hidden, "property_hidden": property_hidden}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0162 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    actor_root = run / "selector-correction"
    actor_root.mkdir()
    seed = previous.seed_workspace(actor_root, parent, source, binding, failed_161["hidden_world"], known)
    (seed / "README.md").write_text(
        "Correct the exact retained mechanism selector from its objective 6/8 consequence. Edit only selector.py. "
        "The two remaining misses show that broader word overlap is insufficient: infer the relational dependency on revised or accepted machinery plus preservation of its earned floor, while keeping individual cue words harmless in ordinary routes. "
        "The published runtime is exact. choose_mechanism must return one presented id, preserve inputs, and pass all 18 known cases. "
        "Run python3 check_selector.py, inspect the exact diff, and report truthfully.\n"
    )
    label = "relational-dependency-selector-corrector"
    output, base_audit, workspace, _ = context.run_actor(label, seed, SELECTOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        corrected_source = (workspace / "selector.py").read_text()
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        corrected_source, immutable_ok = "", False
    corrected_selector = runtime_base.load_selector(corrected_source)
    corrected_known = selector_base.evaluate(corrected_selector, known)
    valid = bool(corrected_selector and corrected_source != source and corrected_known["passed"] and immutable_ok and output and output.get("action") == "correct-mechanism-selector")
    audit = context.audit_actor(label, output, base_audit, valid, ["selector.py"])
    corrected_binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0162-bound-relational-dependency-selector", "source_subject_digest": parent["artifact_digest"], "parent_selector_binding_digest": binding["binding_digest"], "contradiction_receipt_digest": failed_161["hidden_world"]["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "selector_source": corrected_source, "known_result": corrected_known}
        corrected_binding = {**body, "binding_digest": p82.digest(body)}
    corrected_hidden = selector_base.evaluate(corrected_selector, hidden) if corrected_binding else None
    world = None
    if corrected_hidden:
        body = {"authority": "ot-0162-independent-relational-selector-consequence", "selector_binding_digest": corrected_binding["binding_digest"], "hidden_portfolios_digest": p82.digest(hidden), "result": corrected_hidden}
        world = {**body, "receipt_digest": p82.digest(body)}
        (run / "sealed-hidden-relational-selector-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")

    final = parent
    capability = correction = None
    if world and world["result"]["passed"]:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        correction_body = {"authority": "ot-0162-selector-correction-ancestry", "parent_selector": binding, "corrected_selector_binding_digest": corrected_binding["binding_digest"], "contradiction_receipt_digest": failed_161["hidden_world"]["receipt_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0162-relational-selector-capability", "selector_binding_digest": corrected_binding["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = corrected_binding
        final = p82.seal(child)

    erased = copy.deepcopy(final)
    erased["active_developmental_mechanism_selector"] = None
    erased_choice = runtime_base.installed_choice(erased, parent["active_developmental_stake"], selector_base.CANDIDATES)
    installed_choice = runtime_base.installed_choice(final, parent["active_developmental_stake"], selector_base.CANDIDATES)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "developmental_mechanism_selector_capabilities", "developmental_mechanism_selector_corrections"}
    checks = {
        "fresh_corrector_accepted": bool(corrected_binding and prior131.audit_accepted(audit)),
        "source_changed": corrected_source != source,
        "known_floor_18_of_18": corrected_known["passed"] and corrected_known["pass_count"] == 18,
        "hidden_10_of_10": bool(world and world["result"]["passed"] and world["result"]["pass_count"] == 10),
        "unchanged_selector_4_of_10": old_hidden["pass_count"] == 4 and old_hidden["case_count"] == 10 and not old_hidden["passed"],
        "property_selector_5_of_10": property_hidden["pass_count"] == 5 and property_hidden["case_count"] == 10 and not property_hidden["passed"],
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
    result = {"authority": "ot-0162-relational-dependency-selector-correction", "source_subject_digest": parent["artifact_digest"], "parent_selector_binding_digest": binding["binding_digest"], "correction": {"output": output, "audit": audit, "binding": corrected_binding, "known_result": corrected_known}, "hidden_world": world, "post_seal_unchanged_selector_control": old_hidden, "post_seal_property_only_control": property_hidden, "selector_erasure_control": {"observed": erased_choice, "passed": erased_choice is None}, "checks": checks, "selector_correction_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
