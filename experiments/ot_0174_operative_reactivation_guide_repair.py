from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0173_revoked_composition_selector_correction.py"
BASE_SHA256 = "d51f4612f37f0cbdd6dadd335f354ca48041101a2adad5315dd336a4b70f71fa"
PARENT_DIGEST = "3770a9d53dfc415617b644eb9e45673478623cd238c328ff00fb128ac11e2df8"
GUIDE_SHA256 = "8564216884986cdc332a386b6240805481030dc296b42df2eddca0ebfe1d92ae"
GUIDE_BINDING_DIGEST = "204e02baf8d449e1b5e4051e7dbe70cd8fa36698fcb1842fa1f591a7bb3399fa"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0173 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0174_frozen_ot0173", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
selector = previous.selector
reuse = previous.reuse
guide_base = previous.guide_base
choice_base = previous.choice_base


def correction_seed(root: Path, parent: dict, guide: str, known: list[dict], result_173: dict) -> Path:
    seed = root / "guide-seed"
    seed.mkdir()
    missed = [row for row in result_173["correction"]["known_result"]["rows"] if not row["passed"]]
    files = {"subject-position.json": reuse.worlds.base.active_position(parent), "selection-guide.md": guide, "known-cases.json": known, "prior-known-result.json": result_173["correction"]["known_result"], "sole-missed-row.json": missed[0], "prior-known-choices.json": {key: value["choice"] for key, value in result_173["correction"]["known_choices"]["corrected"].items()}, "mutation-envelope.json": {"editable": ["selection-guide.md"], "immutable": ["subject-position.json", "known-cases.json", "prior-known-result.json", "sole-missed-row.json", "prior-known-choices.json"]}}
    for name, value in files.items():
        if name == "selection-guide.md":
            (seed / name).write_text(value)
        else:
            guide_base.write_json(seed / name, value)
    (seed / "README.md").write_text("Correct the exact 3,685-byte semantic guide from its sole known miss. Edit only selection-guide.md and keep it at most 5,000 UTF-8 bytes. Treat restoring, replaying, reactivating, or resuming a named prior composed mechanism together with its earned floor as affirmative operative status. Preserve the defeated-composition rule: stale, revoked, retired, or surrendered composition kept only as history or regression evidence is not active authority. Preserve all ordinary-route boundaries. Inspect the exact diff and report truthfully.\n")
    return seed


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
    run = (args.evidence_root or store / "runs/OT-0174").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0172", "open-subject-after-harm-triggered-pursuit-surrender.json")
    old_parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    result_172 = selector_base.load_artifact(p82, repo, store, "OT-0172", "harm-triggered-pursuit-surrender-aggregate.json")
    result_173 = selector_base.load_artifact(p82, repo, store, "OT-0173", "revoked-composition-selector-correction-aggregate.json")
    guide_manifest, guide_path = p82.materialize(repo, store, "OT-0173", "exact-known-10-of-11-revoked-composition-guide.json")
    intermediate_guide = guide_path.read_text()
    intermediate_binding = result_173["correction"]["provisional_binding"]
    original_selector = parent["active_developmental_mechanism_selector"]
    original_guide = original_selector["guide_text"]
    known = [previous.current_case(parent, selector_base), *previous.known_base.cases(old_parent, selector_base)]
    hidden = previous.hidden_cases(selector_base)
    missed = [row for row in result_173["correction"]["known_result"]["rows"] if not row["passed"]]
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "exact_intermediate_guide": guide_manifest["sha256"] == GUIDE_SHA256 and hashlib.sha256(intermediate_guide.encode()).hexdigest() == GUIDE_SHA256 and len(intermediate_guide.encode()) == 3685 and intermediate_binding["binding_digest"] == GUIDE_BINDING_DIGEST, "known_10_of_11_exact": result_173["correction"]["known_result"]["pass_count"] == 10, "sole_miss_exact": len(missed) == 1 and missed[0]["case_id"] == "sole-reactivate-membership", "hidden_still_unopened": result_173["world"]["corrected_result"]["case_count"] == 0 and result_173["world"]["hidden_digest"] == p82.digest(hidden), "original_selector_exact": original_selector["binding_digest"] == previous.PARENT_SELECTOR_DIGEST, "schemas_present": previous.CORRECTION_SCHEMA.is_file() and guide_base.CHOICE_SCHEMA.is_file()}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "known_digest": p82.digest(known), "hidden_digest": p82.digest(hidden)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0174 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    correction_root = run / "guide-correction"; correction_root.mkdir()
    seed = correction_seed(correction_root, parent, intermediate_guide, known, result_173)
    label = "operative-reactivation-guide-corrector"
    output, base_audit, workspace, _ = context.run_actor(label, seed, previous.CORRECTION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        corrected_guide = (workspace / "selection-guide.md").read_text()
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        corrected_guide, immutable_ok = "", False
    valid = bool(200 <= len(corrected_guide.encode()) <= 5000 and corrected_guide != intermediate_guide and immutable_ok and output and output.get("action") == "correct-semantic-selection-guide")
    correction_audit = context.audit_actor(label, output, base_audit, valid, ["selection-guide.md"])
    provisional = None
    if valid and prior131.audit_accepted(correction_audit):
        body = {"authority": "ot-0174-provisional-operative-reactivation-guide", "source_subject_digest": parent["artifact_digest"], "parent_guide_binding_digest": intermediate_binding["binding_digest"], "parent_selector_binding_digest": original_selector["binding_digest"], "contradiction_receipt_digest": result_173["receipt_digest"], "actor_patch_digest": correction_audit["patch_digest"], "guide_text": corrected_guide}
        provisional = {**body, "binding_digest": p82.digest(body)}
    known_choices, known_audits = ({"corrected": {}}, [])
    known_result = choice_base.score_choices(known_choices, "corrected", known)
    corrected_binding = None
    if provisional:
        known_choices, known_audits = choice_base.run_choices(context, prior131, p82, run, "known-choice-staging", "operative-known-choice", selector_base, parent, known, [("corrected", corrected_guide, provisional["binding_digest"])])
        known_result = choice_base.score_choices(known_choices, "corrected", known)
        if known_result["pass_count"] == 11 and len(known_audits) == 11 and all(prior131.audit_accepted(audit) for audit in known_audits):
            body = {"authority": "ot-0174-bound-operative-reactivation-guide", "provisional_binding_digest": provisional["binding_digest"], "source_subject_digest": parent["artifact_digest"], "parent_guide_binding_digest": intermediate_binding["binding_digest"], "parent_selector_binding_digest": original_selector["binding_digest"], "contradiction_receipt_digest": result_173["receipt_digest"], "actor_patch_digest": correction_audit["patch_digest"], "guide_text": corrected_guide, "known_result": known_result}
            corrected_binding = {**body, "binding_digest": p82.digest(body)}
    hidden_choices = {"corrected": {}, "intermediate": {}, "original": {}}
    hidden_audits = []
    corrected_hidden = choice_base.score_choices(hidden_choices, "corrected", hidden)
    intermediate_hidden = choice_base.score_choices(hidden_choices, "intermediate", hidden)
    original_hidden = choice_base.score_choices(hidden_choices, "original", hidden)
    if corrected_binding:
        hidden_choices, hidden_audits = choice_base.run_choices(context, prior131, p82, run, "hidden-choice-staging", "operative-hidden-choice", selector_base, parent, hidden, [("corrected", corrected_guide, corrected_binding["binding_digest"]), ("intermediate", intermediate_guide, intermediate_binding["binding_digest"]), ("original", original_guide, original_selector["binding_digest"])])
        corrected_hidden = choice_base.score_choices(hidden_choices, "corrected", hidden)
        intermediate_hidden = choice_base.score_choices(hidden_choices, "intermediate", hidden)
        original_hidden = choice_base.score_choices(hidden_choices, "original", hidden)
    world_body = {"authority": "ot-0174-independent-operative-reactivation-guide-consequence", "corrected_guide_binding_digest": corrected_binding["binding_digest"] if corrected_binding else None, "intermediate_guide_binding_digest": intermediate_binding["binding_digest"], "original_selector_binding_digest": original_selector["binding_digest"], "hidden_digest": p82.digest(hidden), "corrected_result": corrected_hidden, "intermediate_result": intermediate_hidden, "original_result": original_hidden}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-operative-reactivation-guide-world.json", world)
    advantage_original = corrected_hidden["pass_count"] - original_hidden["pass_count"]
    advantage_intermediate = corrected_hidden["pass_count"] - intermediate_hidden["pass_count"]
    promoted = bool(corrected_binding and corrected_hidden["pass_count"] == 12 and corrected_hidden["ordinary_pass_count"] == 6 and corrected_hidden["dependency_pass_count"] == 6 and original_hidden["pass_count"] <= 9 and advantage_original >= 3 and intermediate_hidden["pass_count"] <= 11 and advantage_intermediate >= 1 and len(hidden_audits) == 36 and all(prior131.audit_accepted(audit) for audit in hidden_audits))
    final = parent
    active_selector = None
    if promoted:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**corrected_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digests": [result_172["harm_world"]["receipt_digest"], result_172["confirmation_world"]["receipt_digest"], world["receipt_digest"]]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        correction_body = {"authority": "ot-0174-operative-reactivation-selector-correction", "original_selector_binding_digest": original_selector["binding_digest"], "intermediate_guide_binding_digest": intermediate_binding["binding_digest"], "corrected_guide_binding_digest": corrected_binding["binding_digest"], "harm_world_receipt_digest": result_172["harm_world"]["receipt_digest"], "failed_confirmation_receipt_digest": result_172["confirmation_world"]["receipt_digest"], "selection_world_receipt_digest": world["receipt_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0174-operative-reactivation-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), intermediate_binding, corrected_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        child.pop("active_developmental_mechanism_choice", None)
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "active_developmental_mechanism_choice", "developmental_semantic_selection_guides", "developmental_mechanism_selector_corrections", "developmental_mechanism_selector_capabilities"}
    current_row = next((row for row in known_result["rows"] if row["case_id"] == "revoked-current-correction-stake"), None)
    reactivate_row = next((row for row in known_result["rows"] if row["case_id"] == "sole-reactivate-membership"), None)
    checks = {"fresh_corrector_accepted": bool(provisional and prior131.audit_accepted(correction_audit)), "guide_changed": corrected_guide != intermediate_guide, "known_11_of_11": known_result["pass_count"] == 11, "current_stake_selects_prediction_corrector": bool(current_row and current_row["passed"]), "reactivated_membership_selects_composed": bool(reactivate_row and reactivate_row["passed"]), "eleven_known_actors_accepted": len(known_audits) == 11 and all(prior131.audit_accepted(audit) for audit in known_audits), "corrected_hidden_12_of_12": corrected_hidden["pass_count"] == 12, "corrected_revoked_6_of_6": corrected_hidden["ordinary_pass_count"] == 6, "corrected_active_composition_6_of_6": corrected_hidden["dependency_pass_count"] == 6, "original_at_most_9_of_12": original_hidden["pass_count"] <= 9, "corrected_advantage_over_original_at_least_3": advantage_original >= 3, "intermediate_at_most_11_of_12": intermediate_hidden["pass_count"] <= 11, "corrected_advantage_over_intermediate_at_least_1": advantage_intermediate >= 1, "thirty_six_hidden_actors_accepted": len(hidden_audits) == 36 and all(prior131.audit_accepted(audit) for audit in hidden_audits), "corrected_selector_installed": bool(active_selector and final.get("active_developmental_mechanism_selector", {}).get("binding_digest") == active_selector["binding_digest"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0174-operative-reactivation-guide-repair", "source_subject_digest": parent["artifact_digest"], "correction": {"output": output, "audit": correction_audit, "provisional_binding": provisional, "binding": corrected_binding, "known_choices": known_choices, "known_result": known_result}, "hidden_choices": hidden_choices, "world": world, "checks": checks, "operative_reactivation_guide_repair_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 48}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
