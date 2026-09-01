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
BASE_PATH = ROOT / "ot_0168_exact_semantic_guide_correction_continuation.py"
BASE_SHA256 = "b53ed3d68e7fce7d52db1478ca3dc66305c48848a4a965bc4a448aa09ea0738a"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
CORRECTED_GUIDE_SHA256 = "3a14153250902aba9aac85fc7b8adf7b2950ed9599729ed3ffc4bca4e791c0af"
CORRECTED_BINDING_DIGEST = "179fb4de1039d2d682b828f8f02b16f37010190d2690edc2fd8a2fc7a7b9d0f0"
ORIGINAL_BINDING_DIGEST = "ebb819e30399dfce72457aa45c8af6a723e9952341b554c92b24ad26f96a02c2"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0168 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0169_frozen_ot0168", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
guide_base = previous.guide_base
choice_base = previous.previous


def cases(parent: dict[str, Any], selector_base) -> list[dict[str, Any]]:
    c = selector_base.CANDIDATES
    stake = selector_base.stake
    return [
        {"case_id": "replicate-current-stake", "class": "dependency", "stake": parent["active_developmental_stake"], "candidates": [c[1], c[3], c[0], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "replicate-accepted-history", "class": "dependency", "stake": stake("replicate-accepted-history", "option-expansion", "Widen the admitted set through the prior identity filter while keeping its complete accepted history in force."), "candidates": [c[0], c[2], c[3], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "replicate-proven-history", "class": "dependency", "stake": stake("replicate-proven-history", "correction-from-error", "Repair the stale classification with the established equivalence rule and preserve that rule's proven history."), "candidates": [c[2], c[1], c[0], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "replicate-established-behavior", "class": "dependency", "stake": stake("replicate-established-behavior", "continuity-under-reset", "Restore the composed compatibility gate after reset with all of its established behavior intact."), "candidates": [c[3], c[0], c[2], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "replicate-prior-passes", "class": "dependency", "stake": stake("replicate-prior-passes", "option-expansion", "Use the previously admitted membership operation to extend the choices without losing any of its prior passes."), "candidates": [c[1], c[2], c[3], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "replicate-regression-count", "class": "dependency", "stake": stake("replicate-regression-count", "correction-from-error", "Amend the stale result through the corrected admissibility boundary while retaining its 27-case regression history."), "candidates": [c[0], c[3], c[1], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "replicate-replay-certified-filter", "class": "dependency", "stake": stake("replicate-replay-certified-filter", "continuity-under-reset", "Replay the learned filter after restart and keep every check already certified for that filter."), "candidates": [c[2], c[0], c[1], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "replicate-corrected-extension-floor", "class": "dependency", "stake": stake("replicate-corrected-extension-floor", "option-expansion", "Continue the corrected identity-gated extension while preserving all accepted and blocked cases it has already established."), "candidates": [c[3], c[1], c[2], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "replicate-ordinary-accepted-token", "class": "ordinary", "stake": stake("replicate-ordinary-accepted-token", "continuity-under-reset", "Carry one accepted identity token across reset."), "candidates": [c[0], c[3], c[2], c[1]], "expected": "reset-carrier"},
        {"case_id": "replicate-ordinary-proven-labels", "class": "ordinary", "stake": stake("replicate-ordinary-proven-labels", "option-expansion", "List every proven equivalence label currently permitted."), "candidates": [c[1], c[0], c[3], c[2]], "expected": "viable-branch-carrier"},
        {"case_id": "replicate-ordinary-filter-boolean", "class": "ordinary", "stake": stake("replicate-ordinary-filter-boolean", "correction-from-error", "Replace one filter boolean with its observed value."), "candidates": [c[2], c[3], c[0], c[1]], "expected": "prediction-corrector"},
        {"case_id": "replicate-ordinary-regression-checksum", "class": "ordinary", "stake": stake("replicate-ordinary-regression-checksum", "continuity-under-reset", "Preserve one regression-history checksum after restart."), "candidates": [c[3], c[2], c[1], c[0]], "expected": "reset-carrier"},
        {"case_id": "replicate-ordinary-established-options", "class": "ordinary", "stake": stake("replicate-ordinary-established-options", "option-expansion", "Return every established option that is unblocked by the current check."), "candidates": [c[0], c[1], c[2], c[3]], "expected": "viable-branch-carrier"},
        {"case_id": "replicate-ordinary-membership-forecast", "class": "ordinary", "stake": stake("replicate-ordinary-membership-forecast", "correction-from-error", "Correct one membership forecast to match the observation."), "candidates": [c[1], c[3], c[0], c[2]], "expected": "prediction-corrector"},
        {"case_id": "replicate-ordinary-prior-pass-token", "class": "ordinary", "stake": stake("replicate-ordinary-prior-pass-token", "continuity-under-reset", "Carry one token naming the prior pass across reset."), "candidates": [c[2], c[0], c[3], c[1]], "expected": "reset-carrier"},
        {"case_id": "replicate-ordinary-admissible-branches", "class": "ordinary", "stake": stake("replicate-ordinary-admissible-branches", "option-expansion", "Enumerate all presently admissible branches."), "candidates": [c[3], c[2], c[0], c[1]], "expected": "viable-branch-carrier"},
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
    run = (args.evidence_root or store / "runs/OT-0169").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    result_166 = selector_base.load_artifact(p82, repo, store, "OT-0166", "single-authority-semantic-guide-test-aggregate.json")
    result_168 = selector_base.load_artifact(p82, repo, store, "OT-0168", "exact-semantic-guide-correction-continuation-aggregate.json")
    corrected_manifest, corrected_path = p82.materialize(repo, store, "OT-0168", "exact-known-and-hidden-10-of-10-corrected-semantic-guide.json")
    corrected_guide = corrected_path.read_text()
    corrected_binding = result_168["correction"]["binding"]
    original_binding = result_166["guide_binding"]
    original_guide = original_binding["guide_text"]
    portfolio = cases(parent, selector_base)
    projections = [choice_base.previous.subject_projection(parent, case) for case in portfolio]
    fixtures = {"checks": {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "exact_corrected_guide": corrected_manifest["sha256"] == CORRECTED_GUIDE_SHA256 and hashlib.sha256(corrected_guide.encode()).hexdigest() == CORRECTED_GUIDE_SHA256 and len(corrected_guide.encode()) == 2999 and corrected_binding["binding_digest"] == CORRECTED_BINDING_DIGEST and corrected_binding["guide_text"] == corrected_guide,
        "exact_original_guide": original_binding["binding_digest"] == ORIGINAL_BINDING_DIGEST,
        "ot0168_narrow_advantage_exact": result_168["world"]["corrected_result"]["pass_count"] == 10 and result_168["world"]["unchanged_result"]["pass_count"] == 9 and not result_168["semantic_guide_correction_passed"],
        "portfolio_balanced_16": len(portfolio) == 16 and sum(row["class"] == "dependency" for row in portfolio) == 8 and sum(row["class"] == "ordinary" for row in portfolio) == 8,
        "case_ids_unique": len({row["case_id"] for row in portfolio}) == 16,
        "one_stake_per_projection": all(projection["active_developmental_stake"] == case["stake"] and projection["unresolved"] == case["stake"]["question"] for projection, case in zip(projections, portfolio)),
        "choice_schema_present": guide_base.CHOICE_SCHEMA.is_file(),
    }}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "portfolio_digest": p82.digest(portfolio), "projections_digest": p82.digest(projections)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0169 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    choices, audits = choice_base.run_choices(context, prior131, p82, run, "choice-staging", "replication-choice", selector_base, parent, portfolio, [("corrected", corrected_guide, corrected_binding["binding_digest"]), ("original", original_guide, original_binding["binding_digest"])])
    corrected_result = choice_base.score_choices(choices, "corrected", portfolio)
    original_result = choice_base.score_choices(choices, "original", portfolio)
    world_body = {"authority": "ot-0169-independent-exact-guide-replication-consequence", "corrected_guide_binding_digest": corrected_binding["binding_digest"], "original_guide_binding_digest": original_binding["binding_digest"], "portfolio_digest": p82.digest(portfolio), "projections_digest": p82.digest(projections), "corrected_result": corrected_result, "original_result": original_result}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-exact-guide-replication-world.json", world)
    advantage = corrected_result["pass_count"] - original_result["pass_count"]
    all_bound = all(choices[branch].get(row["case_id"], {}).get("binding") for branch in ["corrected", "original"] for row in portfolio)
    promoted = bool(all_bound and len(audits) == 32 and all(prior131.audit_accepted(audit) for audit in audits) and corrected_result["pass_count"] == 16 and corrected_result["dependency_pass_count"] == 8 and corrected_result["ordinary_pass_count"] == 8 and original_result["pass_count"] <= 13 and advantage >= 3)
    final = parent
    if promoted:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**corrected_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digests": [result_168["world"]["receipt_digest"], world["receipt_digest"]]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        correction_body = {"authority": "ot-0169-replicated-semantic-guide-correction-ancestry", "corrected_guide_binding_digest": corrected_binding["binding_digest"], "parent_guide_binding_digest": corrected_binding["parent_guide_binding_digest"], "original_guide_binding_digest": original_binding["binding_digest"], "contradiction_receipt_digest": corrected_binding["contradiction_receipt_digest"], "selection_world_receipt_digests": [result_168["world"]["receipt_digest"], world["receipt_digest"]]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0169-replicated-semantic-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), corrected_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "developmental_semantic_selection_guides", "developmental_mechanism_selector_capabilities", "developmental_mechanism_selector_corrections"}
    current = next((row for row in corrected_result["rows"] if row["case_id"] == "replicate-current-stake"), None)
    checks = {"exact_corrected_guide_reused": corrected_binding["binding_digest"] == CORRECTED_BINDING_DIGEST, "thirty_two_fresh_choices_bound": all_bound and len(audits) == 32 and all(prior131.audit_accepted(audit) for audit in audits), "corrected_16_of_16": corrected_result["pass_count"] == 16, "corrected_dependencies_8_of_8": corrected_result["dependency_pass_count"] == 8, "corrected_ordinary_8_of_8": corrected_result["ordinary_pass_count"] == 8, "original_at_most_13_of_16": original_result["pass_count"] <= 13, "corrected_advantage_at_least_3": advantage >= 3, "current_stake_routes_to_extension": bool(current and current["passed"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "corrected_semantic_selector_installed": bool(promoted and final.get("active_developmental_mechanism_selector", {}).get("binding_digest") == active_selector["binding_digest"]), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0169-exact-corrected-guide-replication", "source_subject_digest": parent["artifact_digest"], "corrected_guide_binding": corrected_binding, "original_guide_binding": original_binding, "choice_bindings": choices, "world": world, "checks": checks, "exact_corrected_guide_replication_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 32}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
