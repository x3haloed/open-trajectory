from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0163_retained_semantic_selection_guide.py"
BASE_SHA256 = "d7eaf061d890fece15c47eda948e94528ce257326abf8fa3c6a3f2aa4966951f"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
GUIDE_SHA256 = "466a845489ee08925b6b38002027f61b5049939541622c5425126c7d8bfb2bc5"
REQUESTS_DIGEST = "a073fe7301c38f940dab6e4fffc4f2fe3b8e631e8e44a44e72c9a1e9f07596e4"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0163 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0164_frozen_ot0163", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()


def scored(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": rows,
        "pass_count": sum(row["passed"] for row in rows),
        "case_count": len(rows),
        "dependency_pass_count": sum(row["passed"] for row in rows if row["class"] == "dependency"),
        "ordinary_pass_count": sum(row["passed"] for row in rows if row["class"] == "ordinary"),
        "passed": bool(rows and all(row["passed"] for row in rows)),
    }


def main() -> int:
    selector_lineage = previous.load_base()
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
    run = (args.evidence_root or store / "runs/OT-0164").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    result_160 = selector_base.load_artifact(p82, repo, store, "OT-0160", "complete-selector-runtime-reconstruction-aggregate.json")
    result_161 = selector_base.load_artifact(p82, repo, store, "OT-0161", "consequence-corrected-mechanism-selector-aggregate.json")
    result_162 = selector_base.load_artifact(p82, repo, store, "OT-0162", "relational-dependency-selector-correction-aggregate.json")
    failure_163 = selector_base.load_artifact(p82, repo, store, "OT-0163", "semantic-guide-driver-failure.json")
    guide_manifest, guide_path = p82.materialize(repo, store, "OT-0163", "exact-clean-semantic-selection-guide.json")
    guide = guide_path.read_text()
    guide_audit = json.loads((store / "runs/OT-0163/semantic-selection-guide-author/actor-audit.json").read_text())
    original_public, original_hidden = selector_base.portfolios(parent["active_developmental_stake"])
    history = [*original_public, *original_hidden, *selector_lineage.previous.hidden_portfolios(), *selector_lineage.hidden_portfolios()]
    requests = previous.selection_requests(parent, selector_base)
    consequences = [result_160["hidden_world"], result_161["hidden_world"], result_162["hidden_world"]]
    guide_body = {"authority": "ot-0163-bound-semantic-selection-guide", "source_subject_digest": parent["artifact_digest"], "consequence_receipt_digests": [row["receipt_digest"] for row in consequences], "history_digest": p82.digest(history), "actor_patch_digest": guide_audit["patch_digest"], "guide_text": guide}
    guide_binding = {**guide_body, "binding_digest": p82.digest(guide_body)}

    with tempfile.TemporaryDirectory() as directory:
        temp_run = Path(directory)
        labels = [f"semantic-choice-{index + 1:02d}-{branch}" for index in range(10) for branch in ["active", "erased"]]
        namespace_disjoint = all(temp_run / "choice-staging" / label != temp_run / label for label in labels)
    fixtures = {"checks": {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "exact_guide_identity": guide_manifest["sha256"] == GUIDE_SHA256 and hashlib.sha256(guide.encode()).hexdigest() == GUIDE_SHA256 and len(guide.encode()) == 2745,
        "guide_audit_clean": guide_audit.get("conformant") and prior131.audit_accepted(guide_audit),
        "ot0163_failed_before_choices": failure_163["fresh_selection_actor_count"] == 0 and not failure_163["hidden_choices_scored"] and not failure_163["semantic_guide_falsified"],
        "history_exact_28": len(history) == 28,
        "requests_exact": p82.digest(requests) == REQUESTS_DIGEST and len(requests) == 10,
        "staging_and_evidence_namespaces_disjoint": namespace_disjoint,
        "schemas_present": previous.GUIDE_SCHEMA.is_file() and previous.CHOICE_SCHEMA.is_file(),
    }}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "guide_binding_digest": guide_binding["binding_digest"], "requests_digest": p82.digest(requests)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0164 evidence")
    run.mkdir(parents=True)
    previous.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    staging = run / "choice-staging"
    staging.mkdir()
    choices: dict[str, dict[str, Any]] = {"active": {}, "erased": {}}
    actor_audits = []
    for index, request in enumerate(requests):
        order = ["active", "erased"] if index % 2 == 0 else ["erased", "active"]
        for branch in order:
            label = f"semantic-choice-{index + 1:02d}-{branch}"
            root = staging / label
            root.mkdir()
            seed = previous.choice_seed(root, selector_base, parent, request, guide if branch == "active" else None)
            output, base_audit, workspace, _ = context.run_actor(label, seed, previous.CHOICE_SCHEMA, (seed / "README.md").read_text().strip())
            try:
                choice = json.loads((workspace / "choice.json").read_text())
                immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
                immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
            except (OSError, json.JSONDecodeError, KeyError):
                choice, immutable_ok = None, False
            ids = {row["mechanism_id"] for row in request["candidates"]}
            valid = bool(isinstance(choice, dict) and set(choice) == {"mechanism_id", "rationale"} and choice.get("mechanism_id") in ids and isinstance(choice.get("rationale"), str) and choice["rationale"].strip() and immutable_ok and output and output.get("mechanism_id") == choice["mechanism_id"])
            audit = context.audit_actor(label, output, base_audit, valid, ["choice.json"])
            actor_audits.append(audit)
            body = {"authority": "ot-0163-bound-semantic-choice", "source_subject_digest": parent["artifact_digest"], "case_digest": p82.digest({key: value for key, value in request.items() if key != "expected"}), "guide_binding_digest": guide_binding["binding_digest"] if branch == "active" else None, "actor_patch_digest": audit.get("patch_digest"), "mechanism_id": choice.get("mechanism_id") if isinstance(choice, dict) else None}
            choices[branch][request["case_id"]] = {"binding": {**body, "binding_digest": p82.digest(body)} if valid and prior131.audit_accepted(audit) else None, "output": output, "audit": audit, "choice": choice}

    all_bound = all(choices[branch].get(row["case_id"], {}).get("binding") for branch in ["active", "erased"] for row in requests)
    active_rows, erased_rows = [], []
    if all_bound:
        for request in requests:
            for branch, rows in [("active", active_rows), ("erased", erased_rows)]:
                observed = choices[branch][request["case_id"]]["binding"]["mechanism_id"]
                rows.append({"case_id": request["case_id"], "class": request["class"], "observed": observed, "expected": request["expected"], "passed": observed == request["expected"]})
    active_result, erased_result = scored(active_rows), scored(erased_rows)
    world_body = {"authority": "ot-0163-independent-semantic-selection-consequence", "guide_binding_digest": guide_binding["binding_digest"], "requests_digest": p82.digest(requests), "active_result": active_result, "erased_result": erased_result}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    previous.write_json(run / "sealed-semantic-selection-world.json", world)
    advantage = active_result["pass_count"] - erased_result["pass_count"]
    causal = bool(active_result["pass_count"] == 10 and active_result["dependency_pass_count"] == 5 and active_result["ordinary_pass_count"] == 5 and erased_result["pass_count"] <= 8 and advantage >= 2)

    final = parent
    if all_bound and causal and all(prior131.audit_accepted(audit) for audit in actor_audits):
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        active_selector_body = {**guide_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digest": world["receipt_digest"]}
        active_selector_body.pop("binding_digest", None)
        active_selector = {**active_selector_body, "binding_digest": p82.digest(active_selector_body)}
        correction_body = {"authority": "ot-0163-semantic-selector-correction-ancestry", "parent_selector_binding_digest": result_162["correction"]["binding"]["binding_digest"], "semantic_guide_binding_digest": guide_binding["binding_digest"], "contradiction_receipt_digest": result_162["hidden_world"]["receipt_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0163-semantic-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), guide_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "developmental_semantic_selection_guides", "developmental_mechanism_selector_capabilities", "developmental_mechanism_selector_corrections"}
    current_row = next((row for row in active_rows if row["case_id"] == "semantic-current-carried-stake"), None)
    checks = {"exact_guide_reconstructed": fixtures["checks"]["exact_guide_identity"] and fixtures["checks"]["guide_audit_clean"], "twenty_fresh_choices_bound": all_bound and len(actor_audits) == 20 and all(prior131.audit_accepted(audit) for audit in actor_audits), "active_10_of_10": active_result["pass_count"] == 10, "active_dependencies_5_of_5": active_result["dependency_pass_count"] == 5, "active_ordinary_5_of_5": active_result["ordinary_pass_count"] == 5, "erased_at_most_8_of_10": erased_result["pass_count"] <= 8, "active_advantage_at_least_2": advantage >= 2, "current_stake_routes_to_extension": bool(current_row and current_row["passed"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "semantic_selector_installed": final.get("active_developmental_mechanism_selector", {}).get("selector_kind") == "fresh-actor-semantic-guide", "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0164-exact-semantic-guide-comparison", "source_subject_digest": parent["artifact_digest"], "guide_binding": guide_binding, "choice_bindings": choices, "world": world, "checks": checks, "semantic_guide_causal_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 20}
    result["receipt_digest"] = p82.digest(result)
    previous.write_json(run / "aggregate.json", result)
    previous.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
