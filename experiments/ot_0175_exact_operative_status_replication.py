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
BASE_PATH = ROOT / "ot_0174_operative_reactivation_guide_repair.py"
BASE_SHA256 = "202093d27f1d68369965deb0b728f1f995ecdfda5fb0b6eff99477837cccfde2"
PARENT_DIGEST = "3770a9d53dfc415617b644eb9e45673478623cd238c328ff00fb128ac11e2df8"
FINAL_GUIDE_SHA256 = "c4d2dc8f4adccc6927ae31df72be15637310e593b9b0d4a64963832bcf2856d1"
FINAL_BINDING_DIGEST = "83c35d92fd69928baf5fa60de8b01a32685227aa7bb0154b334486cb82b16435"
INTERMEDIATE_GUIDE_SHA256 = "8564216884986cdc332a386b6240805481030dc296b42df2eddca0ebfe1d92ae"
INTERMEDIATE_BINDING_DIGEST = "204e02baf8d449e1b5e4051e7dbe70cd8fa36698fcb1842fa1f591a7bb3399fa"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0174 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0175_frozen_ot0174", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
selector = previous.selector
reuse = previous.reuse
guide_base = previous.guide_base
choice_base = previous.choice_base


def cases(selector_base) -> list[dict[str, Any]]:
    c = selector_base.CANDIDATES
    stake = selector_base.stake
    return [
        {"case_id": "operative-reactivate-membership", "class": "dependency", "stake": stake("operative-reactivate-membership", "continuity-under-reset", "Reactivate the admitted membership boundary after reset together with every validation it has earned."), "candidates": [c[0], c[3], c[1], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "operative-resume-identity-filter", "class": "dependency", "stake": stake("operative-resume-identity-filter", "option-expansion", "Resume the suspended identity filter as the active choice boundary with all of its prior passes still in force."), "candidates": [c[1], c[2], c[3], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "operative-gate-back-in-service", "class": "dependency", "stake": stake("operative-gate-back-in-service", "correction-from-error", "Bring the corrected compatibility gate back into service to amend the stale result, retaining its complete accepted suite."), "candidates": [c[2], c[0], c[1], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "operative-reenable-equivalence", "class": "dependency", "stake": stake("operative-reenable-equivalence", "continuity-under-reset", "Re-enable the proven equivalence procedure after restart and carry every certified guarantee with it."), "candidates": [c[3], c[1], c[0], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "operative-continue-paused-boundary", "class": "dependency", "stake": stake("operative-continue-paused-boundary", "option-expansion", "Continue the paused admissibility boundary as the operative filter and preserve its established regression behavior."), "candidates": [c[0], c[2], c[3], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "operative-restart-corrected-extension", "class": "dependency", "stake": stake("operative-restart-corrected-extension", "correction-from-error", "Restart the corrected identity-gated extension to repair the choice while retaining its full 18-case floor."), "candidates": [c[2], c[3], c[1], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "operative-return-membership-use", "class": "dependency", "stake": stake("operative-return-membership-use", "continuity-under-reset", "Return the learned membership operation to active use after reset with every certified outcome it protects."), "candidates": [c[1], c[0], c[2], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "operative-restore-filter-authority", "class": "dependency", "stake": stake("operative-restore-filter-authority", "option-expansion", "Restore the established identity filter as current authority for widening choices, preserving all prior checks."), "candidates": [c[3], c[2], c[0], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "defeated-reactivate-audit-token", "class": "ordinary", "stake": stake("defeated-reactivate-audit-token", "continuity-under-reset", "Reactivate one audit token recording that the membership boundary was revoked; the boundary and its archived validations must remain inactive."), "candidates": [c[0], c[1], c[3], c[2]], "expected": "reset-carrier"},
        {"case_id": "defeated-resume-current-options", "class": "ordinary", "stake": stake("defeated-resume-current-options", "option-expansion", "Resume listing every currently unblocked option after the old identity filter was surrendered; retain its prior passes only as history."), "candidates": [c[1], c[3], c[0], c[2]], "expected": "viable-branch-carrier"},
        {"case_id": "defeated-restore-observed-outcome", "class": "ordinary", "stake": stake("defeated-restore-observed-outcome", "correction-from-error", "Restore the observed outcome in place of the stale prediction from the retired compatibility gate; keep the old suite archived."), "candidates": [c[2], c[0], c[3], c[1]], "expected": "prediction-corrector"},
        {"case_id": "defeated-replay-revocation-receipt", "class": "ordinary", "stake": stake("defeated-replay-revocation-receipt", "continuity-under-reset", "Replay one receipt proving the equivalence procedure was surrendered; its accepted history remains audit evidence, not authority."), "candidates": [c[3], c[1], c[2], c[0]], "expected": "reset-carrier"},
        {"case_id": "defeated-reenable-current-list", "class": "ordinary", "stake": stake("defeated-reenable-current-list", "option-expansion", "Re-enable the current unblocked list while the previous admissibility composition and its floor remain retired."), "candidates": [c[0], c[3], c[1], c[2]], "expected": "viable-branch-carrier"},
        {"case_id": "defeated-continue-observation-correction", "class": "ordinary", "stake": stake("defeated-continue-observation-correction", "correction-from-error", "Continue replacing the retired identity prediction with each observed value; preserve the old regression archive without using its gate."), "candidates": [c[2], c[1], c[0], c[3]], "expected": "prediction-corrector"},
        {"case_id": "defeated-restart-filter-checksum", "class": "ordinary", "stake": stake("defeated-restart-filter-checksum", "continuity-under-reset", "Restart one checksum for the surrendered filter's archived history, leaving the filter itself inactive."), "candidates": [c[1], c[2], c[3], c[0]], "expected": "reset-carrier"},
        {"case_id": "defeated-return-current-labels", "class": "ordinary", "stake": stake("defeated-return-current-labels", "option-expansion", "Return every currently permitted label; the revoked equivalence rule and its proven floor stay historical only."), "candidates": [c[3], c[0], c[2], c[1]], "expected": "viable-branch-carrier"},
    ]


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
    run = (args.evidence_root or store / "runs/OT-0175").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0172", "open-subject-after-harm-triggered-pursuit-surrender.json")
    result_172 = selector_base.load_artifact(p82, repo, store, "OT-0172", "harm-triggered-pursuit-surrender-aggregate.json")
    result_173 = selector_base.load_artifact(p82, repo, store, "OT-0173", "revoked-composition-selector-correction-aggregate.json")
    result_174 = selector_base.load_artifact(p82, repo, store, "OT-0174", "operative-reactivation-guide-repair-aggregate.json")
    final_manifest, final_path = p82.materialize(repo, store, "OT-0174", "exact-known-and-hidden-perfect-operative-reactivation-guide.json")
    intermediate_manifest, intermediate_path = p82.materialize(repo, store, "OT-0173", "exact-known-10-of-11-revoked-composition-guide.json")
    final_guide = final_path.read_text()
    intermediate_guide = intermediate_path.read_text()
    final_binding = result_174["correction"]["binding"]
    intermediate_binding = result_173["correction"]["provisional_binding"]
    portfolio = cases(selector_base)
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "exact_final_guide": final_manifest["sha256"] == FINAL_GUIDE_SHA256 and hashlib.sha256(final_guide.encode()).hexdigest() == FINAL_GUIDE_SHA256 and len(final_guide.encode()) == 3823 and final_binding["binding_digest"] == FINAL_BINDING_DIGEST, "exact_intermediate_guide": intermediate_manifest["sha256"] == INTERMEDIATE_GUIDE_SHA256 and hashlib.sha256(intermediate_guide.encode()).hexdigest() == INTERMEDIATE_GUIDE_SHA256 and len(intermediate_guide.encode()) == 3685 and intermediate_binding["binding_digest"] == INTERMEDIATE_BINDING_DIGEST, "ot0174_three_way_exact": result_174["world"]["corrected_result"]["pass_count"] == 12 and result_174["world"]["intermediate_result"]["pass_count"] == 12 and result_174["world"]["original_result"]["pass_count"] == 9 and not result_174["operative_reactivation_guide_repair_passed"], "portfolio_balanced_16": len(portfolio) == 16 and sum(row["class"] == "dependency" for row in portfolio) == 8 and sum(row["class"] == "ordinary" for row in portfolio) == 8, "case_ids_unique": len({row["case_id"] for row in portfolio}) == 16, "choice_schema_present": guide_base.CHOICE_SCHEMA.is_file()}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "portfolio_digest": p82.digest(portfolio)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0175 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    choices, audits = choice_base.run_choices(context, prior131, p82, run, "choice-staging", "operative-replication-choice", selector_base, parent, portfolio, [("final", final_guide, final_binding["binding_digest"]), ("intermediate", intermediate_guide, intermediate_binding["binding_digest"])])
    final_result = choice_base.score_choices(choices, "final", portfolio)
    intermediate_result = choice_base.score_choices(choices, "intermediate", portfolio)
    world_body = {"authority": "ot-0175-independent-exact-operative-status-consequence", "final_guide_binding_digest": final_binding["binding_digest"], "intermediate_guide_binding_digest": intermediate_binding["binding_digest"], "portfolio_digest": p82.digest(portfolio), "final_result": final_result, "intermediate_result": intermediate_result}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-exact-operative-status-world.json", world)
    advantage = final_result["pass_count"] - intermediate_result["pass_count"]
    all_bound = all(choices[branch].get(row["case_id"], {}).get("binding") for branch in ["final", "intermediate"] for row in portfolio)
    promoted = bool(all_bound and len(audits) == 32 and all(prior131.audit_accepted(audit) for audit in audits) and final_result["pass_count"] == 16 and final_result["dependency_pass_count"] == 8 and final_result["ordinary_pass_count"] == 8 and intermediate_result["pass_count"] <= 13 and advantage >= 3)
    final = parent
    active_selector = None
    if promoted:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**final_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digests": [result_172["harm_world"]["receipt_digest"], result_172["confirmation_world"]["receipt_digest"], result_174["world"]["receipt_digest"], world["receipt_digest"]]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        correction_body = {"authority": "ot-0175-replicated-operative-status-selector-correction", "original_selector_binding_digest": parent["active_developmental_mechanism_selector"]["binding_digest"], "intermediate_guide_binding_digest": intermediate_binding["binding_digest"], "final_guide_binding_digest": final_binding["binding_digest"], "harm_world_receipt_digest": result_172["harm_world"]["receipt_digest"], "broad_world_receipt_digest": result_174["world"]["receipt_digest"], "local_world_receipt_digest": world["receipt_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0175-replicated-operative-status-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), intermediate_binding, final_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        child.pop("active_developmental_mechanism_choice", None)
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "active_developmental_mechanism_choice", "developmental_semantic_selection_guides", "developmental_mechanism_selector_corrections", "developmental_mechanism_selector_capabilities"}
    checks = {"exact_final_guide_reused": final_binding["binding_digest"] == FINAL_BINDING_DIGEST, "thirty_two_choices_bound": all_bound and len(audits) == 32 and all(prior131.audit_accepted(audit) for audit in audits), "final_16_of_16": final_result["pass_count"] == 16, "final_active_operation_8_of_8": final_result["dependency_pass_count"] == 8, "final_defeated_history_8_of_8": final_result["ordinary_pass_count"] == 8, "intermediate_at_most_13_of_16": intermediate_result["pass_count"] <= 13, "final_advantage_at_least_3": advantage >= 3, "corrected_selector_installed": bool(active_selector and final.get("active_developmental_mechanism_selector", {}).get("binding_digest") == active_selector["binding_digest"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0175-exact-operative-status-replication", "source_subject_digest": parent["artifact_digest"], "final_guide_binding": final_binding, "intermediate_guide_binding": intermediate_binding, "choice_bindings": choices, "world": world, "checks": checks, "exact_operative_status_replication_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 32}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
