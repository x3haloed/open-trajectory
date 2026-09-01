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
BASE_PATH = ROOT / "ot_0167_consequence_corrected_semantic_guide.py"
BASE_SHA256 = "87ce00a54ec163817cbd1086efbbca4975e85564d6d95145b8d884769e7a0baf"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
GUIDE_SHA256 = "f73334652d169d601728919a01aff42e20e5a812ab72233eb62356703b0768c5"
GUIDE_BINDING_DIGEST = "599f8cd4270f1b971aec824a85c8b1e9b1a0d2695a0e2663479202461fdca162"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0167 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0168_frozen_ot0167", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
guide_base = previous.guide_base
comparison_base = previous.comparison_base


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
    run = (args.evidence_root or store / "runs/OT-0168").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    result_166 = selector_base.load_artifact(p82, repo, store, "OT-0166", "single-authority-semantic-guide-test-aggregate.json")
    result_167 = selector_base.load_artifact(p82, repo, store, "OT-0167", "consequence-corrected-semantic-guide-aggregate.json")
    lexical_result = selector_base.load_artifact(p82, repo, store, "OT-0162", "relational-dependency-selector-correction-aggregate.json")
    guide_manifest, guide_path = p82.materialize(repo, store, "OT-0167", "exact-known-9-of-10-corrected-semantic-guide.json")
    parent_guide = guide_path.read_text()
    parent_binding = result_167["correction"]["provisional_binding"]
    original_binding = result_166["guide_binding"]
    original_guide = original_binding["guide_text"]
    known = previous.previous.cases(parent, selector_base)
    hidden = previous.hidden_cases(selector_base)
    missed = [row for row in result_167["correction"]["known_result"]["rows"] if not row["passed"]]
    fixtures = {"checks": {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "exact_parent_guide": guide_manifest["sha256"] == GUIDE_SHA256 and hashlib.sha256(parent_guide.encode()).hexdigest() == GUIDE_SHA256 and len(parent_guide.encode()) == 2809 and parent_binding["binding_digest"] == GUIDE_BINDING_DIGEST,
        "known_9_of_10_exact": result_167["correction"]["known_result"]["pass_count"] == 9 and result_167["correction"]["known_result"]["ordinary_pass_count"] == 5 and result_167["correction"]["known_result"]["dependency_pass_count"] == 4,
        "sole_miss_exact": len(missed) == 1 and missed[0]["case_id"] == "sole-enumerate-through-filter",
        "hidden_still_unopened": result_167["world"]["corrected_result"]["case_count"] == 0 and result_167["world"]["hidden_digest"] == p82.digest(hidden),
        "original_control_exact": original_binding["binding_digest"] == "ebb819e30399dfce72457aa45c8af6a723e9952341b554c92b24ad26f96a02c2",
        "schemas_present": previous.CORRECTION_SCHEMA.is_file() and guide_base.CHOICE_SCHEMA.is_file(),
    }}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "known_digest": p82.digest(known), "hidden_digest": p82.digest(hidden)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0168 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))

    correction_root = run / "guide-correction-staging"
    correction_root.mkdir()
    prior_choices = result_167["correction"]["known_choices"]["corrected"]
    choice_evidence = {"active": prior_choices, "erased": {}}
    consequence = {"authority": "ot-0168-known-guide-correction-consequence", "known_result": result_167["correction"]["known_result"], "missed_rows": missed, "source_receipt_digest": result_167["receipt_digest"]}
    seed = previous.correction_seed(correction_root, parent, parent_guide, known, consequence, choice_evidence)
    (seed / "README.md").write_text(
        "Correct the exact 2,809-byte semantic guide from its sole known miss. Edit only selection-guide.md and keep it at most 5,000 UTF-8 bytes. "
        "Preserve the restored ordinary 5/5 boundary. Amend only explicit earned-floor evidence: accepted or proven history, established behavior, prior passes, and regression history count when the same active stake explicitly names a prior composed mechanism. "
        "Continue to forbid inventing an unstated composition or floor from cue words, single values, tokens, flags, checksums, or ordinary lists. Inspect the exact diff and report truthfully.\n"
    )
    label = "accepted-history-guide-corrector"
    output, base_audit, workspace, _ = context.run_actor(label, seed, previous.CORRECTION_SCHEMA, (seed / "README.md").read_text().strip())
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
        body = {"authority": "ot-0168-provisional-accepted-history-guide", "source_subject_digest": parent["artifact_digest"], "parent_guide_binding_digest": parent_binding["binding_digest"], "contradiction_receipt_digest": result_167["receipt_digest"], "actor_patch_digest": correction_audit["patch_digest"], "guide_text": corrected_guide}
        provisional = {**body, "binding_digest": p82.digest(body)}

    public_choices, public_audits = ({"corrected": {}}, [])
    public_result = comparison_base.scored([])
    corrected_binding = None
    if provisional:
        public_choices, public_audits = previous.run_choices(context, prior131, p82, run, "known-choice-staging", "known-guide-choice", selector_base, parent, known, [("corrected", corrected_guide, provisional["binding_digest"])])
        public_result = previous.score_choices(public_choices, "corrected", known)
        if public_result["pass_count"] == 10 and len(public_audits) == 10 and all(prior131.audit_accepted(audit) for audit in public_audits):
            body = {"authority": "ot-0168-bound-accepted-history-semantic-guide", "provisional_binding_digest": provisional["binding_digest"], "source_subject_digest": parent["artifact_digest"], "parent_guide_binding_digest": parent_binding["binding_digest"], "contradiction_receipt_digest": result_167["receipt_digest"], "actor_patch_digest": correction_audit["patch_digest"], "guide_text": corrected_guide, "known_result": public_result}
            corrected_binding = {**body, "binding_digest": p82.digest(body)}

    hidden_choices = {"corrected": {}, "unchanged": {}}
    hidden_audits = []
    corrected_hidden = unchanged_hidden = comparison_base.scored([])
    if corrected_binding:
        hidden_choices, hidden_audits = previous.run_choices(context, prior131, p82, run, "hidden-choice-staging", "hidden-guide-choice", selector_base, parent, hidden, [("corrected", corrected_guide, corrected_binding["binding_digest"]), ("unchanged", original_guide, original_binding["binding_digest"])])
        corrected_hidden = previous.score_choices(hidden_choices, "corrected", hidden)
        unchanged_hidden = previous.score_choices(hidden_choices, "unchanged", hidden)
    world_body = {"authority": "ot-0168-independent-accepted-history-guide-consequence", "corrected_guide_binding_digest": corrected_binding["binding_digest"] if corrected_binding else None, "unchanged_guide_binding_digest": original_binding["binding_digest"], "hidden_digest": p82.digest(hidden), "corrected_result": corrected_hidden, "unchanged_result": unchanged_hidden}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-accepted-history-guide-world.json", world)
    advantage = corrected_hidden["pass_count"] - unchanged_hidden["pass_count"]
    promoted = bool(corrected_binding and corrected_hidden["pass_count"] == 10 and corrected_hidden["dependency_pass_count"] == 5 and corrected_hidden["ordinary_pass_count"] == 5 and unchanged_hidden["pass_count"] <= 8 and advantage >= 2 and len(hidden_audits) == 20 and all(prior131.audit_accepted(audit) for audit in hidden_audits))
    final = parent
    if promoted:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**corrected_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digest": world["receipt_digest"]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        correction_body = {"authority": "ot-0168-semantic-guide-correction-ancestry", "parent_guide": parent_binding, "original_guide_binding_digest": original_binding["binding_digest"], "corrected_guide_binding_digest": corrected_binding["binding_digest"], "contradiction_receipt_digest": result_167["receipt_digest"], "failed_lexical_parent_binding_digest": lexical_result["correction"]["binding"]["binding_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0168-accepted-history-semantic-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), corrected_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "developmental_semantic_selection_guides", "developmental_mechanism_selector_capabilities", "developmental_mechanism_selector_corrections"}
    current_public = next((row for row in public_result["rows"] if row["case_id"] == "sole-current-stake"), None)
    checks = {"fresh_guide_corrector_accepted": bool(provisional and prior131.audit_accepted(correction_audit)), "guide_changed": corrected_guide != parent_guide, "known_10_of_10": public_result["pass_count"] == 10, "known_dependency_5_of_5": public_result["dependency_pass_count"] == 5, "known_ordinary_5_of_5": public_result["ordinary_pass_count"] == 5, "ten_known_actors_accepted": len(public_audits) == 10 and all(prior131.audit_accepted(audit) for audit in public_audits), "corrected_hidden_10_of_10": corrected_hidden["pass_count"] == 10, "corrected_dependencies_5_of_5": corrected_hidden["dependency_pass_count"] == 5, "corrected_ordinary_5_of_5": corrected_hidden["ordinary_pass_count"] == 5, "unchanged_at_most_8_of_10": unchanged_hidden["pass_count"] <= 8, "corrected_advantage_at_least_2": advantage >= 2, "twenty_hidden_actors_accepted": len(hidden_audits) == 20 and all(prior131.audit_accepted(audit) for audit in hidden_audits), "current_stake_routes_to_extension": bool(current_public and current_public["passed"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "corrected_semantic_selector_installed": final.get("active_developmental_mechanism_selector", {}).get("selector_kind") == "fresh-actor-semantic-guide", "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0168-exact-semantic-guide-correction-continuation", "source_subject_digest": parent["artifact_digest"], "correction": {"output": output, "audit": correction_audit, "provisional_binding": provisional, "binding": corrected_binding, "known_choices": public_choices, "known_result": public_result}, "hidden_choices": hidden_choices, "world": world, "checks": checks, "semantic_guide_correction_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 31}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
