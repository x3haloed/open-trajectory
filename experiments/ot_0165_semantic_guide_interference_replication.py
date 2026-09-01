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
BASE_PATH = ROOT / "ot_0164_exact_semantic_guide_comparison.py"
BASE_SHA256 = "799383e6fd9bc523d3ba33000161764f4293863dcfe985eb7dc2e10a69d73a1d"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
GUIDE_BINDING_DIGEST = "ebb819e30399dfce72457aa45c8af6a723e9952341b554c92b24ad26f96a02c2"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0164 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0165_frozen_ot0164", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
guide_base = previous.previous


def requests(parent: dict[str, Any], selector_base) -> list[dict[str, Any]]:
    c = selector_base.CANDIDATES
    stake = selector_base.stake
    return [
        {"case_id": "interference-current-stake", "class": "dependency", "stake": parent["active_developmental_stake"], "candidates": [c[2], c[0], c[3], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "interference-restore-admitted-policy", "class": "dependency", "stake": stake("restore-admitted-policy", "continuity-under-reset", "Restore the corrected admission policy after reset together with every guarantee established by its prior trials."), "candidates": [c[0], c[1], c[2], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "interference-revise-membership-result", "class": "dependency", "stake": stake("revise-membership-result", "correction-from-error", "Use the established membership policy to revise the stale result while preserving its complete validation history."), "candidates": [c[2], c[3], c[1], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "interference-expand-through-policy", "class": "dependency", "stake": stake("expand-through-policy", "option-expansion", "Expand branches through the corrected identity policy without losing any behavior already certified for it."), "candidates": [c[1], c[0], c[3], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "interference-retained-options-a", "class": "ordinary", "stake": stake("retained-options-a", "option-expansion", "Return every previously retained unblocked option in the current set."), "candidates": [c[3], c[1], c[0], c[2]], "expected": "viable-branch-carrier"},
        {"case_id": "interference-preserved-branches", "class": "ordinary", "stake": stake("preserved-branches", "option-expansion", "Enumerate all preserved viable branches in this snapshot."), "candidates": [c[2], c[0], c[1], c[3]], "expected": "viable-branch-carrier"},
        {"case_id": "interference-corrected-labels", "class": "ordinary", "stake": stake("corrected-labels", "option-expansion", "List every corrected label that is currently permitted."), "candidates": [c[0], c[3], c[2], c[1]], "expected": "viable-branch-carrier"},
        {"case_id": "interference-certified-members", "class": "ordinary", "stake": stake("certified-members", "option-expansion", "Expose all certified members that are presently unblocked."), "candidates": [c[1], c[2], c[3], c[0]], "expected": "viable-branch-carrier"},
        {"case_id": "interference-certified-token", "class": "ordinary", "stake": stake("certified-token", "continuity-under-reset", "Carry one previously certified opaque token across reset."), "candidates": [c[3], c[2], c[0], c[1]], "expected": "reset-carrier"},
        {"case_id": "interference-corrected-checksum", "class": "ordinary", "stake": stake("corrected-checksum", "continuity-under-reset", "Preserve one corrected checksum after restart."), "candidates": [c[1], c[0], c[3], c[2]], "expected": "reset-carrier"},
        {"case_id": "interference-retained-compatibility-flag", "class": "ordinary", "stake": stake("retained-compatibility-flag", "correction-from-error", "Replace one retained compatibility flag with the observed boolean."), "candidates": [c[0], c[2], c[1], c[3]], "expected": "prediction-corrector"},
        {"case_id": "interference-learned-estimate", "class": "ordinary", "stake": stake("learned-estimate", "correction-from-error", "Amend one learned numerical estimate to the measured value."), "candidates": [c[3], c[1], c[2], c[0]], "expected": "prediction-corrector"},
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
    run = (args.evidence_root or store / "runs/OT-0165").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    prior_result = selector_base.load_artifact(p82, repo, store, "OT-0164", "exact-semantic-guide-comparison-aggregate.json")
    lexical_result = selector_base.load_artifact(p82, repo, store, "OT-0162", "relational-dependency-selector-correction-aggregate.json")
    guide_binding = prior_result["guide_binding"]
    guide = guide_binding["guide_text"]
    cases = requests(parent, selector_base)
    erased_failures = [row for row in prior_result["world"]["erased_result"]["rows"] if not row["passed"]]
    fixtures = {"checks": {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "exact_guide_binding": guide_binding["binding_digest"] == GUIDE_BINDING_DIGEST,
        "prior_active_10_erased_9": prior_result["world"]["active_result"]["pass_count"] == 10 and prior_result["world"]["erased_result"]["pass_count"] == 9,
        "prior_single_interference_failure": len(erased_failures) == 1 and erased_failures[0]["case_id"] == "semantic-ordinary-retained-options",
        "balanced_replication": len(cases) == 12 and sum(row["class"] == "dependency" for row in cases) == 4 and sum(row["class"] == "ordinary" for row in cases) == 8,
        "request_ids_fresh": not ({row["case_id"] for row in cases} & {row["case_id"] for row in prior_result["world"]["active_result"]["rows"]}),
        "lexical_parent_exact": lexical_result["correction"]["binding"]["binding_digest"] == prior_result["guide_binding"]["consequence_receipt_digests"][-1] or lexical_result["hidden_world"]["receipt_digest"] == guide_binding["consequence_receipt_digests"][-1],
        "schema_present": guide_base.CHOICE_SCHEMA.is_file(),
    }}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "requests_digest": p82.digest(cases)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0165 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    staging = run / "choice-staging"
    staging.mkdir()
    choices: dict[str, dict[str, Any]] = {"active": {}, "erased": {}}
    audits = []
    for index, request in enumerate(cases):
        order = ["active", "erased"] if index % 2 == 0 else ["erased", "active"]
        for branch in order:
            label = f"interference-choice-{index + 1:02d}-{branch}"
            root = staging / label
            root.mkdir()
            seed = guide_base.choice_seed(root, selector_base, parent, request, guide if branch == "active" else None)
            output, base_audit, workspace, _ = context.run_actor(label, seed, guide_base.CHOICE_SCHEMA, (seed / "README.md").read_text().strip())
            try:
                choice = json.loads((workspace / "choice.json").read_text())
                immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
                immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
            except (OSError, json.JSONDecodeError, KeyError):
                choice, immutable_ok = None, False
            ids = {row["mechanism_id"] for row in request["candidates"]}
            valid = bool(isinstance(choice, dict) and set(choice) == {"mechanism_id", "rationale"} and choice.get("mechanism_id") in ids and isinstance(choice.get("rationale"), str) and choice["rationale"].strip() and immutable_ok and output and output.get("mechanism_id") == choice["mechanism_id"])
            audit = context.audit_actor(label, output, base_audit, valid, ["choice.json"])
            audits.append(audit)
            body = {"authority": "ot-0165-bound-interference-choice", "source_subject_digest": parent["artifact_digest"], "case_digest": p82.digest({key: value for key, value in request.items() if key != "expected"}), "guide_binding_digest": guide_binding["binding_digest"] if branch == "active" else None, "actor_patch_digest": audit.get("patch_digest"), "mechanism_id": choice.get("mechanism_id") if isinstance(choice, dict) else None}
            choices[branch][request["case_id"]] = {"binding": {**body, "binding_digest": p82.digest(body)} if valid and prior131.audit_accepted(audit) else None, "output": output, "audit": audit, "choice": choice}
    all_bound = all(choices[branch].get(row["case_id"], {}).get("binding") for branch in ["active", "erased"] for row in cases)
    active_rows, erased_rows = [], []
    if all_bound:
        for request in cases:
            for branch, rows in [("active", active_rows), ("erased", erased_rows)]:
                observed = choices[branch][request["case_id"]]["binding"]["mechanism_id"]
                rows.append({"case_id": request["case_id"], "class": request["class"], "observed": observed, "expected": request["expected"], "passed": observed == request["expected"]})
    active_result, erased_result = previous.scored(active_rows), previous.scored(erased_rows)
    world_body = {"authority": "ot-0165-independent-guide-interference-consequence", "guide_binding_digest": guide_binding["binding_digest"], "requests_digest": p82.digest(cases), "active_result": active_result, "erased_result": erased_result}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-guide-interference-world.json", world)
    advantage = active_result["pass_count"] - erased_result["pass_count"]
    causal = bool(active_result["pass_count"] == 12 and active_result["dependency_pass_count"] == 4 and active_result["ordinary_pass_count"] == 8 and erased_result["pass_count"] <= 9 and advantage >= 3)
    final = parent
    if all_bound and causal and all(prior131.audit_accepted(audit) for audit in audits):
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**guide_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digests": [prior_result["world"]["receipt_digest"], world["receipt_digest"]]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        correction_body = {"authority": "ot-0165-semantic-selector-correction-ancestry", "parent_selector_binding_digest": lexical_result["correction"]["binding"]["binding_digest"], "semantic_guide_binding_digest": guide_binding["binding_digest"], "contradiction_receipt_digest": lexical_result["hidden_world"]["receipt_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0165-replicated-semantic-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digests": [prior_result["world"]["receipt_digest"], world["receipt_digest"]]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), guide_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "developmental_semantic_selection_guides", "developmental_mechanism_selector_capabilities", "developmental_mechanism_selector_corrections"}
    current = next((row for row in active_rows if row["case_id"] == "interference-current-stake"), None)
    checks = {"exact_guide_reused": guide_binding["binding_digest"] == GUIDE_BINDING_DIGEST, "twenty_four_fresh_choices_bound": all_bound and len(audits) == 24 and all(prior131.audit_accepted(audit) for audit in audits), "active_12_of_12": active_result["pass_count"] == 12, "active_dependencies_4_of_4": active_result["dependency_pass_count"] == 4, "active_ordinary_8_of_8": active_result["ordinary_pass_count"] == 8, "erased_at_most_9_of_12": erased_result["pass_count"] <= 9, "active_advantage_at_least_3": advantage >= 3, "current_stake_routes_to_extension": bool(current and current["passed"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "semantic_selector_installed": final.get("active_developmental_mechanism_selector", {}).get("selector_kind") == "fresh-actor-semantic-guide", "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0165-semantic-guide-interference-replication", "source_subject_digest": parent["artifact_digest"], "guide_binding": guide_binding, "choice_bindings": choices, "world": world, "checks": checks, "semantic_guide_causal_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 24}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
