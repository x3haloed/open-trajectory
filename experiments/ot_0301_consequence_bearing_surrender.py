from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0300_final_surface_to_eighth_wait.py"
BASE_SHA256 = "3fb052299725ff6afc76ffc0107802caba04eb03efeeb932942578f03567f093"
PARENT_DIGEST = "78f2c0e121b543afc46d954cf5d36d572d71bca2d980013f98c92f18c097bdf4"
SURRENDER_BINDING_DIGEST = "4ed5fa203b998ca7cfcf54f19b4b08ba99f0113f8a7fc0b379486f01ce940c9f"
AUTHORITY = "ot-0301-consequence-bearing-surrender"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256: raise RuntimeError("OT-0300 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0301_frozen_ot0300", BASE_PATH); module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


base300 = load_base(); base299 = base300.base299; base297 = base300.base297; base295 = base300.base295; b = base300.b
b.AUTHORITY = AUTHORITY; b.base274.AUTHORITY = AUTHORITY


def write_json(path, value): base300.write_json(path, value)
def lineage(subject): return base295.lineage_projection(subject)


def setup(args):
    chain = b.authority_base.guide_base.load_base(); selector, core = chain.selector_base, chain.base
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0301").resolve()
    prior92 = core.mechanism.load_prior(); _, _, _, p82 = core.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(p82, repo, store, "OT-0300", "retained-final-surface-pre-correction-subject.json")
    binding = selector.load_artifact(p82, repo, store, "OT-0300", "accepted-final-surface-surrender-binding.json")
    audit = selector.load_artifact(p82, repo, store, "OT-0300", "final-surface-surrender-actor-audit.json")
    package = selector.load_artifact(p82, repo, store, "OT-0290", "tideglass-crossings-world-package.json")
    result280 = selector.load_artifact(p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json")
    return repo, run, p82, runtime, parent, binding, audit, package, result280


def actor_from(binding, audit):
    return {"accepted": True, "binding": copy.deepcopy(binding), "decision": copy.deepcopy(binding["decision"]), "public": binding.get("public_result"), "audit": copy.deepcopy(audit), "g10_disposition": True}


def valid_surrender(subject, actor, world, p82):
    _, pending, unresolved, _, target, path = b.base274.selected(subject); binding = actor.get("binding") or {}; decision = actor.get("decision") or {}; denial = actor.get("audit", {}).get("denial_classification_v2", {})
    return bool(
        actor.get("accepted") and actor.get("g10_disposition") and denial.get("accepted") and denial.get("classification") == "clean" and not denial.get("sandbox_violation_retained")
        and binding.get("binding_digest") == SURRENDER_BINDING_DIGEST and binding.get("source_subject_digest") == subject["artifact_digest"] and binding.get("contact_identity") == pending["contact_identity"] and binding.get("world_receipt_digest") == unresolved["receipt_digest"] and binding.get("target_path") == path
        and decision.get("disposition") == "surrender" and decision.get("target_symbol") == target and decision.get("source_subject_digest") == subject["artifact_digest"] and decision.get("contact_identity") == pending["contact_identity"] and decision.get("world_receipt_digest") == unresolved["receipt_digest"]
        and binding.get("patched_source") is None and binding.get("patched_source_digest") is None and binding.get("public_result") is None
        and world.get("source_subject_digest") == subject["artifact_digest"] and world.get("correction_binding_digest") == binding["binding_digest"] and world.get("target_symbol") == target and world.get("target_path") == path and world.get("outcome") == "unresolved" and world.get("promotion_gate") is False and world.get("result", {}).get("all_valid") is False and world.get("unchanged_control", {}).get("matches") == 2
    )


def compile_surrender(subject, actor, world, package, p82):
    if not valid_surrender(subject, actor, world, p82): raise RuntimeError("invalid surrender authority")
    _, pending, _, _, target, path = b.base274.selected(subject); prior = b.base274.all_examples(subject, package, p82)[:4]; disclosed = {row["case_id"] for row in prior}
    mismatches = [row for row in world["unchanged_control"]["rows"] if not row.get("matches") and row.get("case_id") not in disclosed]
    if not mismatches: raise RuntimeError("surrender consequence has no undisclosed counterexample")
    mismatch = sorted(mismatches, key=lambda row: row["case_id"])[0]; examples = b.base274.all_examples(subject, package, p82); index = int(mismatch["case_id"].rsplit("-", 1)[1]) - 1; counterexample = copy.deepcopy(examples[index])
    if counterexample["expected"] != mismatch["expected"]: raise RuntimeError("surrender counterexample mismatch")
    body = {"authority": AUTHORITY + "-surrender-feedback", "source_subject_digest": subject["artifact_digest"], "contact_identity": pending["contact_identity"], "surrender_binding_digest": actor["binding"]["binding_digest"], "world_receipt_digest": world["receipt_digest"], "decision_digest": p82.digest(actor["decision"]), "counterexample_selection": "lowest-canonical-undisclosed-unchanged-mismatch", "counterexample": counterexample, "disposition": "surrender-retained-nonsuccess", "candidate_source_admitted": False, "success_authority": False, "earned_authority": False, "next_operation": "outward-correct"}
    receipt = {**body, "receipt_digest": p82.digest(body)}; cases = [*prior, counterexample]
    disclosure_body = {"authority": AUTHORITY + "-active-correction-disclosure", "source_subject_digest": subject["artifact_digest"], "feedback_receipt_digest": receipt["receipt_digest"], "target_symbol": target, "target_path": path, "cases": cases, "case_count": len(cases), "reference_source_available": False, "remaining_sealed_cases_available": False, "status": "awaiting-revision"}
    child = copy.deepcopy(subject); child.pop("artifact_digest", None); child["retained_surrender_feedback"] = [*child.get("retained_surrender_feedback", []), receipt]; child["active_correction_disclosure"] = {**disclosure_body, "disclosure_digest": p82.digest(disclosure_body)}; child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Continue the surrendered correction from receipted world contact."}; child["unresolved"] = "Surrender remains non-success; continue from the added world counterexample."
    return p82.seal(child), receipt


def controls(subject, actor, world, package, p82):
    mutations = {}
    row = copy.deepcopy(actor); row["binding"]["patched_source"] = "def x():\n    pass\n"; row["binding"]["patched_source_digest"] = p82.digest(row["binding"]["patched_source"]); mutations["source-bearing-surrender"] = not valid_surrender(subject, row, world, p82)
    row = copy.deepcopy(actor); row["decision"]["disposition"] = "revise"; mutations["source-free-revision"] = not valid_surrender(subject, row, world, p82)
    row = copy.deepcopy(actor); row["decision"]["contact_identity"] = "0" * 64; mutations["wrong-contact"] = not valid_surrender(subject, row, world, p82)
    row = copy.deepcopy(actor); row["g10_disposition"] = False; mutations["g10-failure"] = not valid_surrender(subject, row, world, p82)
    changed = copy.deepcopy(world); changed["promotion_gate"] = True; changed["outcome"] = "success"; mutations["success-world"] = not valid_surrender(subject, actor, changed, p82)
    changed = copy.deepcopy(world); changed["unchanged_control"]["matches"] = 3; mutations["changed-control"] = not valid_surrender(subject, actor, changed, p82)
    return mutations


def preflight(root, p82, runtime, parent, binding, audit, package, result280):
    root.mkdir(parents=True, exist_ok=True); actor = actor_from(binding, audit); world = b.base271.sealed_followup(parent, actor, package, result280, p82); final, receipt = compile_surrender(parent, actor, world, package, p82); available = base295.undisclosed(final, package, p82); branches = []
    for depth in range(len(available) + 1):
        corrected, row = b.correction_variant(final, depth, package, result280, p82, runtime); branches.append({**row, "lineage_exact": lineage(corrected) == lineage(parent), "three_earned": len(base297.earned_targets(corrected, package)) == 3})
    route, identity = b.base272.base265.floors(parent); negative = controls(parent, actor, world, package, p82); corpus = json.dumps(receipt, sort_keys=True)
    checks = {"base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256, "parent_exact_final_correction": parent["artifact_digest"] == PARENT_DIGEST and b.base272.derive(parent, p82) == "outward-correct" and runtime.identity_conforms(parent), "exact_clean_surrender": binding["binding_digest"] == SURRENDER_BINDING_DIGEST and valid_surrender(parent, actor, world, p82), "six_controls_reject": all(negative.values()), "surrender_nonauthoritative": not receipt["candidate_source_admitted"] and not receipt["success_authority"] and not receipt["earned_authority"] and binding.get("patched_source") is None and "patched_source" not in corpus, "one_counterexample_added": final["active_correction_disclosure"]["case_count"] == 5 and len(available) == 1, "keeps_correction_open": b.base272.derive(final, p82) == "outward-correct" and len(base297.earned_targets(final, package)) == 2 and lineage(final) == lineage(parent) and runtime.identity_conforms(final), "zero_one_feedback_recovery_paths": len(branches) == 2 and all(row["feedback_passed"] and row["success_6_2"] and row["routes_refresh"] and row["lineage_exact"] and row["three_earned"] for row in branches), "route_floor_16_of_16": route["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "surrender_binding_digest": binding["binding_digest"], "controls": negative, "checks": checks}; result["receipt_digest"] = p82.digest(result); write_json(root / "fixture-conformance.json", result); return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo, run, p82, runtime, parent, binding, audit, package, result280 = setup(args); retained = run / "preflight/fixture-conformance.json"; fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(run / "preflight", p82, runtime, parent, binding, audit, package, result280)
    if args.preflight_only: print(json.dumps(fixtures, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists(): raise SystemExit("OT-0301 unavailable")
    actor = actor_from(binding, audit); world = b.base271.sealed_followup(parent, actor, package, result280, p82); final, receipt = compile_surrender(parent, actor, world, package, p82)
    pulse = {"authority": AUTHORITY + "-pulse", "content": None, "source_subject_digest": parent["artifact_digest"], "derived_operation": "assimilate-surrender"}; pulse["pulse_digest"] = p82.digest(pulse)
    checks = {"preflight_passed": fixtures["checks"]["passed"], "content_free": True, "zero_fresh_actors": True, "exact_surrender_bound": receipt["surrender_binding_digest"] == binding["binding_digest"], "no_candidate_or_success_authority": not receipt["candidate_source_admitted"] and not receipt["success_authority"] and not receipt["earned_authority"], "five_case_disclosure": final["active_correction_disclosure"]["case_count"] == 5, "two_earned_exact": len(base297.earned_targets(final, package)) == 2, "next_is_correction": b.base272.derive(final, p82) == "outward-correct", "lineage_exact": lineage(final) == lineage(parent), "final_open_conformant": final["continuation"]["status"] == "open" and runtime.identity_conforms(final)}; checks["passed"] = all(checks.values())
    result = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "pulse": pulse, "surrender_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "surrender_feedback_receipt_digest": receipt["receipt_digest"], "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 0}; result["receipt_digest"] = p82.digest(result); write_json(run / "aggregate.json", result); write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
