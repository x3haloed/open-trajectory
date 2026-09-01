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
BASE_PATH = ROOT / "ot_0177_coherent_authority_projection.py"
BASE_SHA256 = "9d31efdf7d67f006e4b4928c7b0d5f8d8567d746410d71e4b679cc8622f71c58"
PARENT_DIGEST = "3770a9d53dfc415617b644eb9e45673478623cd238c328ff00fb128ac11e2df8"
PROJECTION_DIGEST = "e54edfd21d53c3393f3e4f2ebab202d2887469c2ec7d917b48bc2107223d61d1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0177 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0178_frozen_ot0177", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()


def run_selection(context, prior131, p82, root: Path, label: str, parent: dict[str, Any], candidates: list[dict[str, Any]], projection: dict[str, Any], projection_digest: str) -> dict[str, Any]:
    result = previous.run_selection(context, prior131, p82, root, label, parent, candidates, projection, projection_digest)
    binding = result.get("binding")
    if binding:
        body = {key: value for key, value in binding.items() if key not in {"authority", "binding_digest"}}
        body["authority"] = "ot-0178-bound-live-authority-choice"
        result["binding"] = {**body, "binding_digest": p82.digest(body)}
    return result


def main() -> int:
    selector_lineage = previous.guide_base.load_base()
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
    run = (args.evidence_root or store / "runs/OT-0178").resolve()

    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0172", "open-subject-after-harm-triggered-pursuit-surrender.json")
    result_177 = selector_base.load_artifact(p82, repo, store, "OT-0177", "coherent-authority-projection-aggregate.json")
    projection = selector_base.load_artifact(p82, repo, store, "OT-0177", "coherent-live-authority-hypothesis.json")
    candidates = selector_base.CANDIDATES
    extension = parent["developmental_property_extensions"][0]
    operation = previous.reuse.extension_base.load_operation(extension["operation_source"])
    per_mechanism = {row["mechanism_id"]: previous.evaluate_mechanism(row["mechanism_id"], operation, previous.CONFIRMATION) for row in candidates}
    by_id = {row["mechanism_id"]: row for row in projection["mechanisms"]}
    source_audit = result_177["authority_author"]["audit"]
    fixtures = {
        "checks": {
            "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
            "projection_exact": p82.digest(projection) == PROJECTION_DIGEST,
            "projection_coherent": previous.valid_projection(projection, candidates),
            "source_actor_clean": prior131.audit_accepted(source_audit),
            "source_rejection_retained": result_177["observer_disposition"] == "rejected" and result_177["authority_author"]["binding"] is None,
            "prior_confirmation_unopened": result_177["world"]["active_result"]["actor_count"] == 0 and result_177["world"]["erased_result"]["actor_count"] == 0,
            "surrender_exact": by_id["corrected-identity-gated-extension"] == {"mechanism_id": "corrected-identity-gated-extension", "status": "surrendered", "floor_role": "regression-only"},
            "multiple_live_routes": sum(row["status"] == "operative" for row in projection["mechanisms"]) >= 2,
            "only_prediction_corrector_passes_contact": per_mechanism["prediction-corrector"]["pass_count"] == 3 and all(per_mechanism[key]["pass_count"] == 0 for key in per_mechanism if key != "prediction-corrector"),
        }
    }
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "projection_digest": p82.digest(projection), "confirmation_digest": p82.digest(previous.CONFIRMATION), "fixtures": fixtures, "per_mechanism": per_mechanism}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0178 evidence")
    run.mkdir(parents=True)
    previous.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    projection_body = {
        "authority": "ot-0178-prospective-live-authority-hypothesis",
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0177_receipt_digest": result_177["receipt_digest"],
        "source_actor_patch_digest": source_audit["patch_digest"],
        "projection": projection,
    }
    projection_binding = {**projection_body, "binding_digest": p82.digest(projection_body)}
    erased = {"mechanisms": [{"mechanism_id": row["mechanism_id"], "status": "unknown", "floor_role": "unknown"} for row in candidates]}
    erased_body = {
        "authority": "ot-0178-field-erased-live-authority-control",
        "source_projection_binding_digest": projection_binding["binding_digest"],
        "source_subject_digest": parent["artifact_digest"],
        "projection": erased,
    }
    erased_binding = {**erased_body, "binding_digest": p82.digest(erased_body)}

    choices: dict[str, dict[str, dict[str, Any]]] = {"active": {}, "erased": {}}
    audits = []
    staging = run / "selection-staging"
    staging.mkdir()
    branches = [("active", projection, projection_binding["binding_digest"]), ("erased", erased, erased_binding["binding_digest"])]
    for index in range(10):
        order = branches if index % 2 == 0 else list(reversed(branches))
        for branch, branch_projection, digest in order:
            actor_label = f"live-authority-choice-{index + 1:02d}-{branch}"
            root = staging / actor_label
            root.mkdir()
            result = run_selection(context, prior131, p82, root, actor_label, parent, candidates, branch_projection, digest)
            choices[branch][actor_label] = result
            audits.append(result["audit"])

    active_result = previous.branch_result(choices["active"], operation)
    erased_result = previous.branch_result(choices["erased"], operation)
    world_body = {
        "authority": "ot-0178-independent-live-authority-contact-consequence",
        "projection_binding_digest": projection_binding["binding_digest"],
        "erased_projection_binding_digest": erased_binding["binding_digest"],
        "confirmation_digest": p82.digest(previous.CONFIRMATION),
        "active_result": active_result,
        "erased_result": erased_result,
    }
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    previous.guide_base.write_json(run / "sealed-live-authority-contact-world.json", world)
    all_bound = all(choices[branch].get(label, {}).get("binding") for branch in choices for label in choices[branch]) and sum(len(rows) for rows in choices.values()) == 20
    selection_advantage = active_result["selection_pass_count"] - erased_result["selection_pass_count"]
    contact_advantage = active_result["contact_pass_count"] - erased_result["contact_pass_count"]
    promoted = bool(all_bound and len(audits) == 20 and all(prior131.audit_accepted(audit) for audit in audits) and active_result["selection_pass_count"] >= 9 and active_result["contact_pass_count"] >= 9 and erased_result["selection_pass_count"] <= 6 and erased_result["contact_pass_count"] <= 6 and selection_advantage >= 3 and contact_advantage >= 3)

    final = parent
    active_selector = None
    if promoted:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**parent["active_developmental_mechanism_selector"], "selector_kind": "semantic-guide-with-consequence-admitted-live-authority", "authority_projection_binding_digest": projection_binding["binding_digest"], "live_authority_world_receipt_digest": world["receipt_digest"]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        capability_body = {"authority": "ot-0178-consequence-admitted-live-authority-capability", "selector_binding_digest": active_selector["binding_digest"], "authority_projection_binding_digest": projection_binding["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["mechanism_authority_projections"] = [*child.get("mechanism_authority_projections", []), projection_binding]
        child["active_mechanism_authority_projection"] = projection_binding
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        child.pop("active_developmental_mechanism_choice", None)
        final = p82.seal(child)

    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "active_developmental_mechanism_choice", "mechanism_authority_projections", "active_mechanism_authority_projection", "developmental_mechanism_selector_capabilities"}
    checks = {
        "twenty_choices_bound": all_bound and len(audits) == 20 and all(prior131.audit_accepted(audit) for audit in audits),
        "active_selection_at_least_9_of_10": active_result["selection_pass_count"] >= 9,
        "active_contact_at_least_9_of_10": active_result["contact_pass_count"] >= 9,
        "erased_selection_at_most_6_of_10": erased_result["selection_pass_count"] <= 6,
        "erased_contact_at_most_6_of_10": erased_result["contact_pass_count"] <= 6,
        "selection_advantage_at_least_3": selection_advantage >= 3,
        "contact_advantage_at_least_3": contact_advantage >= 3,
        "live_authority_selector_installed": bool(active_selector and final.get("active_developmental_mechanism_selector", {}).get("binding_digest") == active_selector["binding_digest"]),
        "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"],
        "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0178-consequence-admitted-live-authority",
        "source_subject_digest": parent["artifact_digest"],
        "source_projection": projection_binding,
        "erased_projection": erased_binding,
        "choice_bindings": choices,
        "world": world,
        "checks": checks,
        "live_authority_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": len(audits),
    }
    result["receipt_digest"] = p82.digest(result)
    previous.guide_base.write_json(run / "aggregate.json", result)
    previous.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
