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
BASE_PATH = ROOT / "ot_0165_semantic_guide_interference_replication.py"
BASE_SHA256 = "37f67436603080001c662341f98001faecc2888c76250380170aff7cd84d5346"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
GUIDE_BINDING_DIGEST = "ebb819e30399dfce72457aa45c8af6a723e9952341b554c92b24ad26f96a02c2"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0165 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0166_frozen_ot0165", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
comparison_base = previous.previous
guide_base = previous.guide_base


def cases(parent: dict[str, Any], selector_base) -> list[dict[str, Any]]:
    c = selector_base.CANDIDATES
    stake = selector_base.stake
    return [
        {"case_id": "sole-current-stake", "class": "dependency", "stake": parent["active_developmental_stake"], "candidates": [c[1], c[0], c[2], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "sole-reactivate-membership", "class": "dependency", "stake": stake("reactivate-membership", "continuity-under-reset", "After restart, reactivate the admitted membership boundary together with every validation it has already earned."), "candidates": [c[0], c[3], c[1], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "sole-correct-through-equivalence", "class": "dependency", "stake": stake("correct-through-equivalence", "correction-from-error", "Apply the corrected equivalence procedure to the stale decision while retaining all of its proven cases."), "candidates": [c[2], c[1], c[3], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "sole-enumerate-through-filter", "class": "dependency", "stake": stake("enumerate-through-filter", "option-expansion", "Enumerate choices through the established identity filter and preserve its complete accepted history."), "candidates": [c[3], c[1], c[0], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "sole-carry-composed-behavior", "class": "dependency", "stake": stake("carry-composed-behavior", "continuity-under-reset", "Carry the learned composed compatibility behavior through reset with all regression evidence intact."), "candidates": [c[2], c[0], c[3], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "sole-ordinary-corrected-token", "class": "ordinary", "stake": stake("ordinary-corrected-token", "continuity-under-reset", "Carry one corrected opaque token across reset."), "candidates": [c[3], c[2], c[0], c[1]], "expected": "reset-carrier"},
        {"case_id": "sole-ordinary-retained-options", "class": "ordinary", "stake": stake("ordinary-retained-options", "option-expansion", "Return every retained unblocked option in the present set."), "candidates": [c[0], c[1], c[3], c[2]], "expected": "viable-branch-carrier"},
        {"case_id": "sole-ordinary-compatibility-flag", "class": "ordinary", "stake": stake("ordinary-compatibility-flag", "correction-from-error", "Update one compatibility flag to the observed boolean."), "candidates": [c[1], c[3], c[2], c[0]], "expected": "prediction-corrector"},
        {"case_id": "sole-ordinary-admitted-items", "class": "ordinary", "stake": stake("ordinary-admitted-items", "option-expansion", "List all items admitted by one current check."), "candidates": [c[2], c[0], c[1], c[3]], "expected": "viable-branch-carrier"},
        {"case_id": "sole-ordinary-certified-checksum", "class": "ordinary", "stake": stake("ordinary-certified-checksum", "continuity-under-reset", "Preserve one certified checksum after restart."), "candidates": [c[1], c[0], c[2], c[3]], "expected": "reset-carrier"},
    ]


def subject_projection(parent: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    stake = copy.deepcopy(case["stake"])
    opening = f"Open actor-stake-{stake['stake_id']}: {stake['question']}"
    return {
        "authority": "ot-0166-sole-active-stake-projection",
        "source_subject_digest": parent["artifact_digest"],
        "active_developmental_stake": stake,
        "active_pursuit": {"authority": "ot-0166-projected-active-pursuit", "next_pursuit": opening, "selected_area": f"selection-{stake['stake_id']}"},
        "continuation": {"authority": "continuation-scheduler", "status": "open", "reserve": parent["continuation"]["reserve"], "maximum_reserve": parent["continuation"]["maximum_reserve"], "next_opening": opening},
        "unresolved": stake["question"],
        "retained_developmental_context": {
            "allocation_correction_history": parent["allocation_correction_history"],
            "developmental_selector": parent["developmental_selector"],
            "developmental_property_extensions": parent["developmental_property_extensions"],
        },
    }


def choice_seed(root: Path, selector_base, parent: dict[str, Any], case: dict[str, Any], guide: str | None) -> Path:
    seed = root / "choice-seed"
    seed.mkdir()
    guide_base.write_json(seed / "subject-position.json", subject_projection(parent, case))
    guide_base.write_json(seed / "candidate-mechanisms.json", case["candidates"])
    guide_base.write_json(seed / "choice.json", {"mechanism_id": "__CHOOSE__", "rationale": "__CHOOSE__"})
    immutable = ["subject-position.json", "candidate-mechanisms.json"]
    if guide is not None:
        (seed / "selection-guide.md").write_text(guide)
        immutable.append("selection-guide.md")
    guide_base.write_json(seed / "mutation-envelope.json", {"editable": ["choice.json"], "immutable": immutable})
    (seed / "README.md").write_text(
        "Choose the presented mechanism that best satisfies the sole active_developmental_stake in subject-position.json. "
        "Use selection-guide.md if present. Do not invent candidates or inspect outside this workspace. Edit only choice.json with exactly mechanism_id and a nonempty rationale, then report the same id truthfully.\n"
    )
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
    run = (args.evidence_root or store / "runs/OT-0166").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    result_164 = selector_base.load_artifact(p82, repo, store, "OT-0164", "exact-semantic-guide-comparison-aggregate.json")
    result_165 = selector_base.load_artifact(p82, repo, store, "OT-0165", "semantic-guide-interference-replication-aggregate.json")
    lexical_result = selector_base.load_artifact(p82, repo, store, "OT-0162", "relational-dependency-selector-correction-aggregate.json")
    guide_binding = result_164["guide_binding"]
    guide = guide_binding["guide_text"]
    portfolio = cases(parent, selector_base)
    parent_question = parent["active_developmental_stake"]["question"]
    projections = [subject_projection(parent, case) for case in portfolio]
    fixtures = {"checks": {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "exact_guide_binding": guide_binding["binding_digest"] == GUIDE_BINDING_DIGEST,
        "authority_ambiguity_observed": result_165["world"]["active_result"]["pass_count"] == 10 and result_165["world"]["erased_result"]["pass_count"] == 10,
        "portfolio_balanced": len(portfolio) == 10 and sum(row["class"] == "dependency" for row in portfolio) == 5 and sum(row["class"] == "ordinary" for row in portfolio) == 5,
        "one_stake_per_projection": all(projection["active_developmental_stake"] == case["stake"] and projection["unresolved"] == case["stake"]["question"] for projection, case in zip(projections, portfolio)),
        "no_inherited_question_in_synthetic_projection": all(case["case_id"] == "sole-current-stake" or parent_question not in json.dumps(projection) for projection, case in zip(projections, portfolio)),
        "choice_schema_present": guide_base.CHOICE_SCHEMA.is_file(),
    }}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "portfolio_digest": p82.digest(portfolio), "projections_digest": p82.digest(projections)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0166 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    staging = run / "choice-staging"
    staging.mkdir()
    choices: dict[str, dict[str, Any]] = {"active": {}, "erased": {}}
    audits = []
    for index, case in enumerate(portfolio):
        order = ["active", "erased"] if index % 2 == 0 else ["erased", "active"]
        for branch in order:
            label = f"sole-stake-choice-{index + 1:02d}-{branch}"
            root = staging / label
            root.mkdir()
            seed = choice_seed(root, selector_base, parent, case, guide if branch == "active" else None)
            output, base_audit, workspace, _ = context.run_actor(label, seed, guide_base.CHOICE_SCHEMA, (seed / "README.md").read_text().strip())
            try:
                choice = json.loads((workspace / "choice.json").read_text())
                immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
                immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
            except (OSError, json.JSONDecodeError, KeyError):
                choice, immutable_ok = None, False
            ids = {row["mechanism_id"] for row in case["candidates"]}
            valid = bool(isinstance(choice, dict) and set(choice) == {"mechanism_id", "rationale"} and choice.get("mechanism_id") in ids and isinstance(choice.get("rationale"), str) and choice["rationale"].strip() and immutable_ok and output and output.get("mechanism_id") == choice["mechanism_id"])
            audit = context.audit_actor(label, output, base_audit, valid, ["choice.json"])
            audits.append(audit)
            body = {"authority": "ot-0166-bound-single-authority-choice", "source_subject_digest": parent["artifact_digest"], "projection_digest": p82.digest(subject_projection(parent, case)), "guide_binding_digest": guide_binding["binding_digest"] if branch == "active" else None, "actor_patch_digest": audit.get("patch_digest"), "mechanism_id": choice.get("mechanism_id") if isinstance(choice, dict) else None}
            choices[branch][case["case_id"]] = {"binding": {**body, "binding_digest": p82.digest(body)} if valid and prior131.audit_accepted(audit) else None, "output": output, "audit": audit, "choice": choice}
    all_bound = all(choices[branch].get(row["case_id"], {}).get("binding") for branch in ["active", "erased"] for row in portfolio)
    active_rows, erased_rows = [], []
    if all_bound:
        for case in portfolio:
            for branch, rows in [("active", active_rows), ("erased", erased_rows)]:
                observed = choices[branch][case["case_id"]]["binding"]["mechanism_id"]
                rows.append({"case_id": case["case_id"], "class": case["class"], "observed": observed, "expected": case["expected"], "passed": observed == case["expected"]})
    active_result, erased_result = comparison_base.scored(active_rows), comparison_base.scored(erased_rows)
    world_body = {"authority": "ot-0166-independent-single-authority-guide-consequence", "guide_binding_digest": guide_binding["binding_digest"], "portfolio_digest": p82.digest(portfolio), "projections_digest": p82.digest(projections), "active_result": active_result, "erased_result": erased_result}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-single-authority-guide-world.json", world)
    advantage = active_result["pass_count"] - erased_result["pass_count"]
    causal = bool(active_result["pass_count"] == 10 and active_result["dependency_pass_count"] == 5 and active_result["ordinary_pass_count"] == 5 and erased_result["pass_count"] <= 8 and advantage >= 2)
    final = parent
    if all_bound and causal and all(prior131.audit_accepted(audit) for audit in audits):
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**guide_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digests": [result_164["world"]["receipt_digest"], world["receipt_digest"]]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        correction_body = {"authority": "ot-0166-semantic-selector-correction-ancestry", "parent_selector_binding_digest": lexical_result["correction"]["binding"]["binding_digest"], "semantic_guide_binding_digest": guide_binding["binding_digest"], "contradiction_receipt_digest": lexical_result["hidden_world"]["receipt_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0166-single-authority-semantic-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), guide_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "developmental_semantic_selection_guides", "developmental_mechanism_selector_capabilities", "developmental_mechanism_selector_corrections"}
    current = next((row for row in active_rows if row["case_id"] == "sole-current-stake"), None)
    checks = {"exact_guide_reused": guide_binding["binding_digest"] == GUIDE_BINDING_DIGEST, "twenty_fresh_choices_bound": all_bound and len(audits) == 20 and all(prior131.audit_accepted(audit) for audit in audits), "active_10_of_10": active_result["pass_count"] == 10, "active_dependencies_5_of_5": active_result["dependency_pass_count"] == 5, "active_ordinary_5_of_5": active_result["ordinary_pass_count"] == 5, "erased_at_most_8_of_10": erased_result["pass_count"] <= 8, "active_advantage_at_least_2": advantage >= 2, "current_stake_routes_to_extension": bool(current and current["passed"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "semantic_selector_installed": final.get("active_developmental_mechanism_selector", {}).get("selector_kind") == "fresh-actor-semantic-guide", "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0166-single-authority-semantic-guide-test", "source_subject_digest": parent["artifact_digest"], "guide_binding": guide_binding, "choice_bindings": choices, "world": world, "checks": checks, "semantic_guide_causal_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 20}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
