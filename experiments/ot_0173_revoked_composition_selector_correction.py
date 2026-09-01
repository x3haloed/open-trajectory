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
BASE_PATH = ROOT / "ot_0172_harm_triggered_pursuit_surrender.py"
BASE_SHA256 = "7657681f071b10f34d138c9abf1af4f3fefd843a9b771c1b286d4be6d4bfe48b"
PARENT_DIGEST = "3770a9d53dfc415617b644eb9e45673478623cd238c328ff00fb128ac11e2df8"
PARENT_SELECTOR_DIGEST = "cd53bad0bc0dc0d063eefd88a5942bb1cb13cdd804a4ce1b7890b45420f48653"
CORRECTION_SCHEMA = REPO / "spec/ot-0167-semantic-guide-correction.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0172 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0173_frozen_ot0172", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
selector = previous.selector
reuse = previous.reuse
guide_base = previous.guide_base
choice_base = selector.choice_base
known_base = choice_base.previous


def current_case(parent: dict[str, Any], selector_base) -> dict[str, Any]:
    c = selector_base.CANDIDATES
    return {"case_id": "revoked-current-correction-stake", "class": "ordinary", "stake": parent["active_developmental_stake"], "candidates": [c[3], c[1], c[2], c[0]], "expected": "prediction-corrector"}


def hidden_cases(selector_base) -> list[dict[str, Any]]:
    c = selector_base.CANDIDATES
    stake = selector_base.stake
    return [
        {"case_id": "revoked-replace-stale-gate-prediction", "class": "ordinary", "stake": stake("replace-stale-gate-prediction", "correction-from-error", "Replace the stale prediction from the revoked identity gate with the observed outcome; retain its 18 prior passes only as regression history."), "candidates": [c[3], c[0], c[2], c[1]], "expected": "prediction-corrector"},
        {"case_id": "revoked-current-authorized-branches", "class": "ordinary", "stake": stake("current-authorized-branches", "option-expansion", "The old membership filter is surrendered. Return every branch authorized by the current world, while keeping the old filter tests as historical regression evidence only."), "candidates": [c[1], c[3], c[0], c[2]], "expected": "viable-branch-carrier"},
        {"case_id": "revoked-carry-surrender-receipt", "class": "ordinary", "stake": stake("carry-surrender-receipt", "continuity-under-reset", "Carry one receipt recording that the prior compatibility composition was revoked; preserve its accepted history for audit, but do not let it govern after reset."), "candidates": [c[2], c[0], c[3], c[1]], "expected": "reset-carrier"},
        {"case_id": "revoked-observed-viable-set", "class": "ordinary", "stake": stake("observed-viable-set", "correction-from-error", "Correct the formerly identity-gated choice to the observed viable set now that the composition is retired, without deleting its proven history."), "candidates": [c[0], c[2], c[1], c[3]], "expected": "prediction-corrector"},
        {"case_id": "revoked-unblocked-options", "class": "ordinary", "stake": stake("revoked-unblocked-options", "option-expansion", "List all currently unblocked options. The previous admissibility boundary and its complete floor remain archived after surrender, not active."), "candidates": [c[3], c[1], c[2], c[0]], "expected": "viable-branch-carrier"},
        {"case_id": "revoked-retain-audit-token", "class": "ordinary", "stake": stake("retain-audit-token", "continuity-under-reset", "Preserve one token identifying the surrendered equivalence rule and its prior-pass archive across reset."), "candidates": [c[1], c[0], c[3], c[2]], "expected": "reset-carrier"},
        {"case_id": "active-amended-identity-boundary", "class": "dependency", "stake": stake("active-amended-identity-boundary", "correction-from-error", "Use the amended identity boundary to revise the stale choice and keep every guarantee still earned by that active boundary."), "candidates": [c[2], c[3], c[0], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "active-restore-compatibility-gate", "class": "dependency", "stake": stake("active-restore-compatibility-gate", "continuity-under-reset", "Restore the corrected compatibility gate after reset with its complete accepted history still in force."), "candidates": [c[0], c[1], c[3], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "active-enumerate-through-filter", "class": "dependency", "stake": stake("active-enumerate-through-filter", "option-expansion", "Enumerate choices through the operative learned filter while preserving all of its established regression behavior."), "candidates": [c[3], c[2], c[1], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "active-corrected-equivalence", "class": "dependency", "stake": stake("active-corrected-equivalence", "correction-from-error", "Apply the corrected equivalence procedure that remains authoritative to the stale result and retain all prior passes."), "candidates": [c[1], c[3], c[2], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "active-membership-replay", "class": "dependency", "stake": stake("active-membership-replay", "continuity-under-reset", "Replay the admitted membership operation after restart with every certified outcome it continues to protect."), "candidates": [c[2], c[1], c[0], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "active-extend-admissible-set", "class": "dependency", "stake": stake("active-extend-admissible-set", "option-expansion", "Extend the admissible set through the current identity-gated operation without surrendering its proven floor."), "candidates": [c[0], c[3], c[1], c[2]], "expected": "corrected-identity-gated-extension"},
    ]


def correction_seed(root: Path, parent: dict[str, Any], guide: str, known: list[dict[str, Any]], result_172: dict[str, Any]) -> Path:
    seed = root / "guide-seed"
    seed.mkdir()
    files = {"subject-position.json": reuse.worlds.base.active_position(parent), "selection-guide.md": guide, "known-cases.json": known, "harm-world.json": result_172["harm_world"], "pursuit-surrender.json": result_172["pursuit_decision"]["binding"], "failed-successor-selection.json": result_172["successor_selection"], "failed-confirmation.json": result_172["confirmation_world"], "mutation-envelope.json": {"editable": ["selection-guide.md"], "immutable": ["subject-position.json", "known-cases.json", "harm-world.json", "pursuit-surrender.json", "failed-successor-selection.json", "failed-confirmation.json"]}}
    for name, value in files.items():
        if name == "selection-guide.md":
            (seed / name).write_text(value)
        else:
            guide_base.write_json(seed / name, value)
    (seed / "README.md").write_text("Correct the inherited semantic selection guide from the exact harmful consequence. Edit only selection-guide.md and keep it at most 5,000 UTF-8 bytes. Distinguish an active composed dependency from a stale, revoked, retired, or surrendered composition retained only as history or a regression floor. When the active stake asks to replace that defeated prediction with observed outcome, use the ordinary correction route. Preserve genuine amended or corrected compositions that remain operative and preserve all prior ordinary boundaries. Inspect the exact diff and report truthfully.\n")
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
    run = (args.evidence_root or store / "runs/OT-0173").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0172", "open-subject-after-harm-triggered-pursuit-surrender.json")
    old_parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    result_172 = selector_base.load_artifact(p82, repo, store, "OT-0172", "harm-triggered-pursuit-surrender-aggregate.json")
    parent_selector = parent["active_developmental_mechanism_selector"]
    parent_guide = parent_selector["guide_text"]
    prior_known = known_base.cases(old_parent, selector_base)
    known = [current_case(parent, selector_base), *prior_known]
    hidden = hidden_cases(selector_base)
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "parent_selector_exact": parent_selector["binding_digest"] == PARENT_SELECTOR_DIGEST and len(parent_guide.encode()) == 2999, "pursuit_surrender_exact": result_172["pursuit_decision"]["binding"]["decision"]["action"] == "surrender-and-renew" and result_172["pursuit_decision"]["binding"]["decision"]["next_stake"] == parent["active_developmental_stake"], "selector_harm_exact": result_172["successor_selection"]["binding"]["mechanism_id"] == "corrected-identity-gated-extension" and result_172["confirmation_world"]["selected_result"]["pass_count"] == 0, "known_11_exact": len(known) == 11 and len({row["case_id"] for row in known}) == 11, "hidden_balanced_12": len(hidden) == 12 and sum(row["class"] == "ordinary" for row in hidden) == 6 and sum(row["class"] == "dependency" for row in hidden) == 6, "hidden_ids_fresh": not ({row["case_id"] for row in hidden} & {row["case_id"] for row in known}), "schemas_present": CORRECTION_SCHEMA.is_file() and guide_base.CHOICE_SCHEMA.is_file()}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "known_digest": p82.digest(known), "hidden_digest": p82.digest(hidden)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0173 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    correction_root = run / "guide-correction"; correction_root.mkdir()
    seed = correction_seed(correction_root, parent, parent_guide, known, result_172)
    label = "revoked-composition-guide-corrector"
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        corrected_guide = (workspace / "selection-guide.md").read_text()
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        corrected_guide, immutable_ok = "", False
    valid = bool(200 <= len(corrected_guide.encode()) <= 5000 and corrected_guide != parent_guide and immutable_ok and output and output.get("action") == "correct-semantic-selection-guide")
    correction_audit = context.audit_actor(label, output, base_audit, valid, ["selection-guide.md"])
    provisional = None
    if valid and prior131.audit_accepted(correction_audit):
        body = {"authority": "ot-0173-provisional-revoked-composition-guide", "source_subject_digest": parent["artifact_digest"], "parent_selector_binding_digest": parent_selector["binding_digest"], "contradiction_receipt_digest": result_172["confirmation_world"]["receipt_digest"], "actor_patch_digest": correction_audit["patch_digest"], "guide_text": corrected_guide}
        provisional = {**body, "binding_digest": p82.digest(body)}
    known_choices, known_audits = ({"corrected": {}}, [])
    known_result = choice_base.score_choices(known_choices, "corrected", known)
    corrected_binding = None
    if provisional:
        known_choices, known_audits = choice_base.run_choices(context, prior131, p82, run, "known-choice-staging", "revoked-known-choice", selector_base, parent, known, [("corrected", corrected_guide, provisional["binding_digest"])])
        known_result = choice_base.score_choices(known_choices, "corrected", known)
        if known_result["pass_count"] == 11 and len(known_audits) == 11 and all(prior131.audit_accepted(audit) for audit in known_audits):
            body = {"authority": "ot-0173-bound-revoked-composition-guide", "provisional_binding_digest": provisional["binding_digest"], "source_subject_digest": parent["artifact_digest"], "parent_selector_binding_digest": parent_selector["binding_digest"], "contradiction_receipt_digest": result_172["confirmation_world"]["receipt_digest"], "actor_patch_digest": correction_audit["patch_digest"], "guide_text": corrected_guide, "known_result": known_result}
            corrected_binding = {**body, "binding_digest": p82.digest(body)}
    hidden_choices = {"corrected": {}, "unchanged": {}}
    hidden_audits = []
    corrected_hidden = choice_base.score_choices(hidden_choices, "corrected", hidden)
    unchanged_hidden = choice_base.score_choices(hidden_choices, "unchanged", hidden)
    if corrected_binding:
        hidden_choices, hidden_audits = choice_base.run_choices(context, prior131, p82, run, "hidden-choice-staging", "revoked-hidden-choice", selector_base, parent, hidden, [("corrected", corrected_guide, corrected_binding["binding_digest"]), ("unchanged", parent_guide, parent_selector["binding_digest"])])
        corrected_hidden = choice_base.score_choices(hidden_choices, "corrected", hidden)
        unchanged_hidden = choice_base.score_choices(hidden_choices, "unchanged", hidden)
    world_body = {"authority": "ot-0173-independent-revoked-composition-selector-consequence", "corrected_guide_binding_digest": corrected_binding["binding_digest"] if corrected_binding else None, "unchanged_selector_binding_digest": parent_selector["binding_digest"], "hidden_digest": p82.digest(hidden), "corrected_result": corrected_hidden, "unchanged_result": unchanged_hidden}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-revoked-composition-selector-world.json", world)
    advantage = corrected_hidden["pass_count"] - unchanged_hidden["pass_count"]
    promoted = bool(corrected_binding and corrected_hidden["pass_count"] == 12 and corrected_hidden["ordinary_pass_count"] == 6 and corrected_hidden["dependency_pass_count"] == 6 and unchanged_hidden["pass_count"] <= 9 and advantage >= 3 and len(hidden_audits) == 24 and all(prior131.audit_accepted(audit) for audit in hidden_audits))
    final = parent
    active_selector = None
    if promoted:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**corrected_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digests": [result_172["harm_world"]["receipt_digest"], result_172["confirmation_world"]["receipt_digest"], world["receipt_digest"]]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        correction_body = {"authority": "ot-0173-revoked-composition-selector-correction", "parent_selector_binding_digest": parent_selector["binding_digest"], "corrected_guide_binding_digest": corrected_binding["binding_digest"], "harm_world_receipt_digest": result_172["harm_world"]["receipt_digest"], "failed_confirmation_receipt_digest": result_172["confirmation_world"]["receipt_digest"], "selection_world_receipt_digest": world["receipt_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0173-revoked-composition-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), corrected_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        child.pop("active_developmental_mechanism_choice", None)
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "active_developmental_mechanism_choice", "developmental_semantic_selection_guides", "developmental_mechanism_selector_corrections", "developmental_mechanism_selector_capabilities"}
    current_row = next((row for row in known_result["rows"] if row["case_id"] == "revoked-current-correction-stake"), None)
    checks = {"fresh_corrector_accepted": bool(provisional and prior131.audit_accepted(correction_audit)), "guide_changed": corrected_guide != parent_guide, "known_11_of_11": known_result["pass_count"] == 11, "current_stake_selects_prediction_corrector": bool(current_row and current_row["passed"]), "eleven_known_actors_accepted": len(known_audits) == 11 and all(prior131.audit_accepted(audit) for audit in known_audits), "corrected_hidden_12_of_12": corrected_hidden["pass_count"] == 12, "corrected_revoked_6_of_6": corrected_hidden["ordinary_pass_count"] == 6, "corrected_active_composition_6_of_6": corrected_hidden["dependency_pass_count"] == 6, "unchanged_at_most_9_of_12": unchanged_hidden["pass_count"] <= 9, "corrected_advantage_at_least_3": advantage >= 3, "twenty_four_hidden_actors_accepted": len(hidden_audits) == 24 and all(prior131.audit_accepted(audit) for audit in hidden_audits), "corrected_selector_installed": bool(active_selector and final.get("active_developmental_mechanism_selector", {}).get("binding_digest") == active_selector["binding_digest"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0173-revoked-composition-selector-correction", "source_subject_digest": parent["artifact_digest"], "correction": {"output": output, "audit": correction_audit, "provisional_binding": provisional, "binding": corrected_binding, "known_choices": known_choices, "known_result": known_result}, "hidden_choices": hidden_choices, "world": world, "checks": checks, "revoked_composition_selector_correction_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 36}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
