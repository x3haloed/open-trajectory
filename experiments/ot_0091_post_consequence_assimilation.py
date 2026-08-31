from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
PRIOR_PATH = ROOT / "ot_0090_confirmation_renewal.py"
PRIOR_SHA256 = "ebfb70b6fded4c5d693bc8b73913caa0f4cd56c1216874b5e9f836d3bde255ee"
PARENT_DIGEST = "b1940ef7a434b60ac02436ea1e75f22179b83be096ec71075736eedcabe3f769"
WORLD_RECEIPT_DIGEST = "2f69d064d4533fda78705ecc3e62b83ba8079b9b14c2df7f4a8ed6b5258c0c4b"
INHERITED_OPENING = (
    "Verify multi-way tie reporting with three or more options, including reordered input and "
    "non-string numeric score values, while preserving greatest-id selection."
)
ACTOR_SCHEMA = REPO / "spec/ot-0091-assimilator.schema.json"
PLACEHOLDER = "__REPLACE__"
ASSIMILATION_KEYS = {
    "disposition",
    "settled_case_ids",
    "settled_stake",
    "remaining_uncertainty",
    "receipt_use",
    "surrender_condition",
}
DISPOSITIONS = {"retain", "revise", "retire"}
REQUIRED_CASE = "hidden-three-way"
SECONDARY_CASES = {"hidden-two-way", "hidden-cost-tie"}


def load_prior():
    if hashlib.sha256(PRIOR_PATH.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0090 implementation identity changed")
    name = "ot0091_frozen_ot0090"
    spec = importlib.util.spec_from_file_location(name, PRIOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_inputs(prior90, p82, repo: Path, store: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    _, subject_path = p82.materialize(repo, store, "OT-0090", "open-subject-after-confirmation-renewal.json")
    _, aggregate_path = p82.materialize(repo, store, "OT-0090", "confirmation-renewal-aggregate.json")
    return json.loads(subject_path.read_text()), json.loads(aggregate_path.read_text())


def consequence(aggregate: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(aggregate["world"])


def common_projection(parent: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    verifier = next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == "verify_coverage.py")
    return {
        "subject_digest": parent["artifact_digest"],
        "runtime": parent["runtime"],
        "continuation": copy.deepcopy(parent["continuation"]),
        "active_pursuit": copy.deepcopy(parent["active_pursuit"]),
        "unresolved": parent["unresolved"],
        "latest_actor_opening": copy.deepcopy(parent["actor_originated_pursuit_openings"][-1]),
        "retained_verifier": {"target_path": verifier["target_path"], "target_symbol": verifier["target_symbol"],
                              "source_digest": verifier["source_digest"], "world_receipt_digest": verifier["world_receipt_digest"]},
        "consequence_identity": {"authority": world["authority"], "binding_digest": world["binding_digest"],
                                 "receipt_digest": world["receipt_digest"], "source_subject_digest": world["source_subject_digest"],
                                 "public_case_count": len(world["public"]["rows"]), "hidden_case_count": len(world["hidden"]["rows"])},
    }


def active_projection(parent: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    return {**common_projection(parent, world), "consequence_outcomes": {
        "developmentally_admitted": world["developmentally_admitted"],
        "public": copy.deepcopy(world["public"]),
        "hidden": copy.deepcopy(world["hidden"]),
    }}


def erased_projection(p82, parent: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    outcomes = active_projection(parent, world)["consequence_outcomes"]
    return {**common_projection(parent, world), "consequence_outcomes": None,
            "consequence_erasure_receipt": {"authority": "ot-0091-outcome-content-erasure",
                "removed_fields": ["developmentally_admitted", "public", "hidden"],
                "removed_content_digest": p82.digest(outcomes), "receipt_digest": world["receipt_digest"]}}


def projection_conformance(p82, parent: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    active = active_projection(parent, world)
    erased = erased_projection(p82, parent, world)
    active_text, erased_text = json.dumps(active, sort_keys=True), json.dumps(erased, sort_keys=True)
    shared = set(common_projection(parent, world))
    result = {
        "parent_bound": active["subject_digest"] == erased["subject_digest"] == PARENT_DIGEST,
        "receipt_bound": active["consequence_identity"]["receipt_digest"] == erased["consequence_identity"]["receipt_digest"] == WORLD_RECEIPT_DIGEST,
        "active_has_three_way": REQUIRED_CASE in active_text,
        "erased_omits_all_case_ids": all(row["case_id"] not in erased_text for row in world["public"]["rows"] + world["hidden"]["rows"]),
        "same_non_outcome": all(active[key] == erased[key] for key in shared),
        "active_digest": p82.digest(active),
        "erased_digest": p82.digest(erased),
    }
    result["passed"] = all(result[key] for key in ("parent_bound", "receipt_bound", "active_has_three_way", "erased_omits_all_case_ids", "same_non_outcome")) and result["active_digest"] != result["erased_digest"]
    return result


def assimilation_template() -> dict[str, Any]:
    return {"disposition": PLACEHOLDER, "settled_case_ids": [], "settled_stake": PLACEHOLDER,
            "remaining_uncertainty": PLACEHOLDER, "receipt_use": PLACEHOLDER, "surrender_condition": PLACEHOLDER}


def assimilation_contract() -> dict[str, Any]:
    return {"exact_keys": sorted(ASSIMILATION_KEYS), "dispositions": sorted(DISPOSITIONS),
            "instruction": "Use only available consequence. Cite case ids only when their outcome rows are visible. Retain may carry the current opening; revise or retire must author a distinct one."}


def valid_assimilation(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != ASSIMILATION_KEYS or value.get("disposition") not in DISPOSITIONS:
        return False
    if not isinstance(value.get("settled_case_ids"), list) or len(value["settled_case_ids"]) > 20 or not all(isinstance(item, str) and item.strip() for item in value["settled_case_ids"]):
        return False
    for key in ASSIMILATION_KEYS - {"disposition", "settled_case_ids"}:
        if not isinstance(value.get(key), str) or not value[key].strip() or PLACEHOLDER in value[key] or len(value[key]) > 3000:
            return False
    return True


def receipt_rows(world: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["case_id"]: row for row in world["public"]["rows"] + world["hidden"]["rows"]}


def score_assimilation(value: dict[str, Any], opening: dict[str, Any], world: dict[str, Any], content_available: bool) -> dict[str, Any]:
    rows = receipt_rows(world)
    cited = value.get("settled_case_ids", []) if isinstance(value, dict) else []
    cited_valid = bool(cited) and all(case_id in rows and rows[case_id].get("valid") is True for case_id in cited)
    required_cases = REQUIRED_CASE in cited and bool(SECONDARY_CASES.intersection(cited))
    stake = value.get("settled_stake", "").lower() if isinstance(value, dict) else ""
    stake_matches = "tie" in stake and any(token in stake for token in ("multi", "three", "reorder"))
    remaining = value.get("remaining_uncertainty", "").lower() if isinstance(value, dict) else ""
    remaining_valid = bool(remaining.strip()) and not any(phrase in remaining for phrase in ("receipt failed", "case failed", "invalid receipt"))
    disposition_revision = value.get("disposition") in {"revise", "retire"} if isinstance(value, dict) else False
    distinct_opening = isinstance(opening, dict) and opening.get("next_opening") != INHERITED_OPENING
    grounded = bool(content_available and cited_valid and required_cases)
    passed = bool(grounded and disposition_revision and stake_matches and remaining_valid and distinct_opening)
    return {"content_available": content_available, "cited_valid_successes": cited_valid, "required_cases_cited": required_cases,
            "stake_matches_settled_contact": stake_matches, "remaining_uncertainty_valid": remaining_valid,
            "disposition_revision": disposition_revision, "distinct_opening": distinct_opening,
            "receipt_grounded": grounded, "passed": passed}


def fixture_conformance(prior90, p82, parent: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    prior89 = prior90.load_prior()
    representative = {"disposition": "revise", "settled_case_ids": ["hidden-three-way", "hidden-two-way"],
        "settled_stake": "The multi-way tie and reordered tie behavior passed.",
        "remaining_uncertainty": "Whether non-string option identifiers require a different stable rule.",
        "receipt_use": "The sealed successes retire the repeated verification request.",
        "surrender_condition": "Restore the opening if a later admitted case contradicts these rows."}
    opening = prior89.representative_successor()
    opening["next_opening"] = "Test whether identifier type changes the stable tie policy."
    active_score = score_assimilation(representative, opening, world, True)
    erased_score = score_assimilation(representative, opening, world, False)
    result = {"projection_conformance": projection_conformance(p82, parent, world),
              "assimilation_seed_rejected": not valid_assimilation(assimilation_template()),
              "representative_assimilation_valid": valid_assimilation(representative),
              "representative_opening_valid": prior89.valid_successor(opening),
              "active_reference_passed": active_score["passed"], "erased_reference_rejected": not erased_score["passed"],
              "world_rows_valid": all(row.get("valid") is True for row in receipt_rows(world).values())}
    result["passed"] = result["projection_conformance"]["passed"] and all(result[key] for key in (
        "assimilation_seed_rejected", "representative_assimilation_valid", "representative_opening_valid",
        "active_reference_passed", "erased_reference_rejected", "world_rows_valid"))
    return result


def actor_seed(prior89, run: Path, label: str, projection: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    (seed / "subject-and-consequence.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "assimilation.json").write_text(json.dumps(assimilation_template(), indent=2, sort_keys=True) + "\n")
    (seed / "assimilation-contract.json").write_text(json.dumps(assimilation_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["assimilation.json", "successor-opening.json"]}, indent=2) + "\n")
    (seed / "README.md").write_text("Assimilate the available sealed consequence into the exact subject's current pursuit. Distinguish settled from unresolved stakes, edit exactly assimilation.json and successor-opening.json, validate JSON, inspect the exact diff, and report truthfully. Do not invent unavailable outcomes.\n")
    return seed


def run_actor(prior89, p82, context, run: Path, label: str, projection: dict[str, Any], world: dict[str, Any], content_available: bool) -> dict[str, Any]:
    seed = actor_seed(prior89, run, label, projection)
    prompt = "Assimilate available sealed consequence into the current pursuit. Use ordinary tools, distinguish settled from unresolved stakes, author the substantive opening that should now be carried, edit exactly the two permitted files, inspect the exact diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor(label, seed, ACTOR_SCHEMA, prompt)
    try:
        assimilation = json.loads((workspace / "assimilation.json").read_text())
        opening = json.loads((workspace / "successor-opening.json").read_text())
    except (OSError, json.JSONDecodeError):
        assimilation, opening = None, None
    artifact_valid = bool(valid_assimilation(assimilation) and prior89.valid_successor(opening)
                          and (assimilation["disposition"] == "retain" or opening["next_opening"] != INHERITED_OPENING))
    audit = context.audit_actor(label, output, base_audit, artifact_valid, ["assimilation.json", "successor-opening.json"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0091-pre-score-assimilation-binding", "condition": label,
                "source_subject_digest": projection["subject_digest"], "projection_digest": p82.digest(projection),
                "actor_patch_digest": audit["patch_digest"], "assimilation": assimilation, "successor_opening": opening}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-assimilation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    score = score_assimilation(assimilation or {}, opening or {}, world, content_available) if binding else {"passed": False}
    scored = {**score, "condition": label, "binding_digest": binding["binding_digest"] if binding else None}
    scored["receipt_digest"] = p82.digest(scored)
    (context.evidence(label) / "assimilation-score.json").write_text(json.dumps(scored, indent=2, sort_keys=True) + "\n")
    return {"label": label, "output": output, "audit": audit, "binding": binding, "score": scored}


def promote(p82, parent: dict[str, Any], active: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    binding, score = active["binding"], active["score"]
    opening = binding["successor_opening"]
    body = {"authority": "world-promoted-post-consequence-assimilation", "source_subject_digest": parent["artifact_digest"],
            "binding_digest": binding["binding_digest"], "score_receipt_digest": score["receipt_digest"],
            "world_receipt_digest": WORLD_RECEIPT_DIGEST}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []),
        {"receipt": receipt, "assimilation": binding["assimilation"]}]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []),
        {"authority": "fresh-post-consequence-opening", "binding_digest": binding["binding_digest"], "opening": opening}]
    child["active_pursuit"] = {"authority": "fresh-post-consequence-opening", "selected_area": "pursuit-assimilation",
        "next_pursuit": opening["next_opening"], "world_receipt_digest": WORLD_RECEIPT_DIGEST}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["runtime"] = "sounding"
    child["unresolved"] = opening["continuation_after_contact"]
    return p82.seal(child), receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0091").resolve()
    prior90 = load_prior()
    prior89 = prior90.load_prior()
    p82 = prior90.prior82(prior89)
    runtime = p82.load_runtime(repo, store)
    parent, aggregate = load_inputs(prior90, p82, repo, store)
    world = consequence(aggregate)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent) or parent["artifact_digest"] != PARENT_DIGEST or parent["continuation"]["next_opening"] != INHERITED_OPENING or world["receipt_digest"] != WORLD_RECEIPT_DIGEST:
        raise SystemExit("wrong OT-0090 parent or consequence")
    fixtures = fixture_conformance(prior90, p82, parent, world)
    if args.preflight_only:
        print(json.dumps({"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "fixture_conformance": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0091 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    active_projection_value = active_projection(parent, world)
    erased_projection_value = erased_projection(p82, parent, world)
    (run / "bound-projections.json").write_text(json.dumps({"active_digest": p82.digest(active_projection_value),
        "erased_digest": p82.digest(erased_projection_value), "conformance": fixtures["projection_conformance"]}, indent=2, sort_keys=True) + "\n")
    context = runtime.Context(run, repo)
    started = time.time()
    active = run_actor(prior89, p82, context, run, "active", active_projection_value, world, True)
    current, promotion = parent, None
    if active["score"]["passed"]:
        current, promotion = promote(p82, parent, active)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
                       and current["continuation"]["status"] == "open"
                       and current["continuation"]["next_opening"] == active["binding"]["successor_opening"]["next_opening"])
    erased = None
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        erased = run_actor(prior89, p82, context, run, "erased", erased_projection_value, world, False)
    causal = bool(operational and erased and not erased["score"]["passed"])
    result = {"authority": "ot-0091-post-consequence-assimilation-driver", "source_subject_digest": parent["artifact_digest"],
        "prior_implementation_sha256": PRIOR_SHA256, "world_receipt_digest": world["receipt_digest"],
        "fixture_conformance": fixtures, "active": p82.compact(active), "erased": p82.compact(erased) if erased else None,
        "promotion_receipt": promotion, "operational_transition_passed": operational,
        "consequence_content_causal_passed": causal,
        "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
