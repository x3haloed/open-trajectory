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
BASE_PATH = ROOT / "ot_0178_consequence_admitted_live_authority.py"
BASE_SHA256 = "bbe6f88106b9edfe8e2caf8b0fd6787d7e28e59eb6096138db90f91aea4b70f7"
PARENT_DIGEST = "c9e406bf0257ab6698adcec71bfc7fa18542a3d7910a82160b9d218c3f762d90"
SELECTOR_DIGEST = "1725ae4f38f014d1ed924694522fc64a331be22c6d7c6ef3a7ade4051aff97b9"
PROJECTION_BINDING_DIGEST = "2f2ed93a32c8c3a51ab8b5b267de8b5097b2f20be7b300231e962895702689a9"

CONFIRMATION = [
    {"case_id": "live-authority-reuse-a", "prediction": ["prior-a"], "outcome": ["observe", "advance"], "options": ["decoy-a", "blocked-a"], "blocked": ["blocked-a"], "signal": "reset-a", "before": "reuse-v60", "after": "reuse-v61", "compatible": False},
    {"case_id": "live-authority-reuse-b", "prediction": ["prior-b"], "outcome": ["transfer", "listen"], "options": ["decoy-b"], "blocked": [], "signal": "reset-b", "before": "reuse-v62", "after": "reuse-v63", "compatible": False},
    {"case_id": "live-authority-reuse-c", "prediction": ["prior-c"], "outcome": ["branch", "verify"], "options": ["decoy-c", "blocked-c"], "blocked": ["blocked-c"], "signal": "reset-c", "before": "reuse-v64", "after": "reuse-v65", "compatible": False},
    {"case_id": "live-authority-reuse-d", "prediction": ["prior-d"], "outcome": ["renew", "continue"], "options": ["decoy-d"], "blocked": [], "signal": "reset-d", "before": "reuse-v66", "after": "reuse-v67", "compatible": False},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0178 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0179_frozen_ot0178", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.previous


def run_selection(context, prior131, p82, root: Path, label: str, parent: dict[str, Any], candidates: list[dict[str, Any]], projection: dict[str, Any], projection_digest: str) -> dict[str, Any]:
    result = previous.run_selection(context, prior131, p82, root, label, parent, candidates, projection, projection_digest)
    binding = result.get("binding")
    if binding:
        body = {key: value for key, value in binding.items() if key not in {"authority", "binding_digest"}}
        body["authority"] = "ot-0179-bound-installed-live-authority-choice"
        result["binding"] = {**body, "binding_digest": p82.digest(body)}
    return result


def branch_result(choices: dict[str, dict[str, Any]], operation) -> dict[str, Any]:
    rows = []
    for label, choice in sorted(choices.items()):
        binding = choice.get("binding")
        mechanism_id = binding["mechanism_id"] if binding else None
        contact = authority_base.evaluate_mechanism(mechanism_id, operation, CONFIRMATION) if mechanism_id else {"pass_count": 0, "passed": False}
        rows.append({"actor_label": label, "mechanism_id": mechanism_id, "selection_passed": mechanism_id == "prediction-corrector", "contact_passed": contact["passed"], "contact_pass_count": contact["pass_count"]})
    return {"actor_count": len(rows), "selection_pass_count": sum(row["selection_passed"] for row in rows), "contact_pass_count": sum(row["contact_passed"] for row in rows), "total_case_pass_count": sum(row["contact_pass_count"] for row in rows), "rows": rows}


def main() -> int:
    selector_lineage = authority_base.guide_base.load_base()
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
    run = (args.evidence_root or store / "runs/OT-0179").resolve()

    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0178", "open-subject-with-consequence-admitted-live-authority.json")
    result_178 = selector_base.load_artifact(p82, repo, store, "OT-0178", "consequence-admitted-live-authority-aggregate.json")
    candidates = selector_base.CANDIDATES
    projection_binding = parent["active_mechanism_authority_projection"]
    projection = projection_binding["projection"]
    extension = parent["developmental_property_extensions"][0]
    operation = authority_base.reuse.extension_base.load_operation(extension["operation_source"])
    per_mechanism = {row["mechanism_id"]: authority_base.evaluate_mechanism(row["mechanism_id"], operation, CONFIRMATION) for row in candidates}
    fixtures = {
        "checks": {
            "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
            "selector_exact": parent["active_developmental_mechanism_selector"]["binding_digest"] == SELECTOR_DIGEST,
            "projection_binding_exact": projection_binding["binding_digest"] == PROJECTION_BINDING_DIGEST,
            "projection_coherent": authority_base.valid_projection(projection, candidates),
            "ot0178_admission_retained": result_178["observer_disposition"] == "promoted" and result_178["world"]["active_result"]["contact_pass_count"] == 10 and result_178["world"]["erased_result"]["contact_pass_count"] == 2,
            "only_prediction_corrector_passes_contact": per_mechanism["prediction-corrector"]["pass_count"] == 4 and all(per_mechanism[key]["pass_count"] == 0 for key in per_mechanism if key != "prediction-corrector"),
        }
    }
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "confirmation_digest": p82.digest(CONFIRMATION), "fixtures": fixtures, "per_mechanism": per_mechanism}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0179 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    erased = {"mechanisms": [{"mechanism_id": row["mechanism_id"], "status": "unknown", "floor_role": "unknown"} for row in candidates]}
    erased_body = {"authority": "ot-0179-field-erased-installed-authority-control", "source_projection_binding_digest": projection_binding["binding_digest"], "source_subject_digest": parent["artifact_digest"], "projection": erased}
    erased_binding = {**erased_body, "binding_digest": p82.digest(erased_body)}
    choices: dict[str, dict[str, dict[str, Any]]] = {"installed": {}, "erased": {}}
    audits = []
    staging = run / "selection-staging"
    staging.mkdir()
    branches = [("installed", projection, projection_binding["binding_digest"]), ("erased", erased, erased_binding["binding_digest"])]
    for index in range(6):
        order = branches if index % 2 == 0 else list(reversed(branches))
        for branch, branch_projection, digest in order:
            actor_label = f"later-live-authority-choice-{index + 1:02d}-{branch}"
            root = staging / actor_label
            root.mkdir()
            result = run_selection(context, prior131, p82, root, actor_label, parent, candidates, branch_projection, digest)
            choices[branch][actor_label] = result
            audits.append(result["audit"])

    installed_result = branch_result(choices["installed"], operation)
    erased_result = branch_result(choices["erased"], operation)
    world_body = {"authority": "ot-0179-independent-installed-live-authority-contact", "projection_binding_digest": projection_binding["binding_digest"], "erased_projection_binding_digest": erased_binding["binding_digest"], "confirmation_digest": p82.digest(CONFIRMATION), "installed_result": installed_result, "erased_result": erased_result}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    authority_base.guide_base.write_json(run / "sealed-live-authority-later-use-world.json", world)
    all_bound = all(choices[branch].get(label, {}).get("binding") for branch in choices for label in choices[branch]) and sum(len(rows) for rows in choices.values()) == 12
    selection_advantage = installed_result["selection_pass_count"] - erased_result["selection_pass_count"]
    contact_advantage = installed_result["contact_pass_count"] - erased_result["contact_pass_count"]
    promoted = bool(all_bound and len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits) and installed_result["selection_pass_count"] == 6 and installed_result["contact_pass_count"] == 6 and erased_result["selection_pass_count"] <= 3 and erased_result["contact_pass_count"] <= 3 and selection_advantage >= 3 and contact_advantage >= 3)

    final = parent
    if promoted:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        reuse_body = {"authority": "ot-0179-exact-live-authority-later-use", "selector_binding_digest": SELECTOR_DIGEST, "projection_binding_digest": PROJECTION_BINDING_DIGEST, "world_receipt_digest": world["receipt_digest"]}
        reuse_receipt = {**reuse_body, "binding_digest": p82.digest(reuse_body)}
        child["developmental_mechanism_selector_reuse_receipts"] = [*child.get("developmental_mechanism_selector_reuse_receipts", []), reuse_receipt]
        final = p82.seal(child)
    authorized = {"artifact_digest", "developmental_mechanism_selector_reuse_receipts"}
    checks = {
        "twelve_choices_bound": all_bound and len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits),
        "installed_selection_6_of_6": installed_result["selection_pass_count"] == 6,
        "installed_contact_6_of_6": installed_result["contact_pass_count"] == 6,
        "erased_selection_at_most_3_of_6": erased_result["selection_pass_count"] <= 3,
        "erased_contact_at_most_3_of_6": erased_result["contact_pass_count"] <= 3,
        "selection_advantage_at_least_3": selection_advantage >= 3,
        "contact_advantage_at_least_3": contact_advantage >= 3,
        "installed_selector_retained_exactly": final["active_developmental_mechanism_selector"] == parent["active_developmental_mechanism_selector"],
        "installed_projection_retained_exactly": final["active_mechanism_authority_projection"] == parent["active_mechanism_authority_projection"],
        "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"],
        "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0179-live-authority-later-use", "source_subject_digest": parent["artifact_digest"], "choice_bindings": choices, "world": world, "checks": checks, "later_use_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": len(audits)}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
