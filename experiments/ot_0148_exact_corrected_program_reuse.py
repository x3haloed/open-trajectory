from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0147_cross_world_selector_program_correction.py"
BASE_SHA256 = "4a67f2200d04ec12de324e6e86ed1dc7fb5357a8496b5b73b7f60f9bd286238c"
PARENT_DIGEST = "7b07e2aa41054f09807fc5fb408c6de63d60aeaa15d29e561b9c37eb9b3fce49"
PROJECTION_VERSION = "ot-0148-throughput-candidate-semantic-projection-v1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0147 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0148_frozen_ot0147", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
p82base = previous.p82base
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def reconstruct(p82, subject: dict[str, Any], retained: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    later = retained.get("later_portfolio")
    if not isinstance(later, dict) or later.get("binding") is not None:
        return None, None
    audit = later.get("audit", {})
    raw = later.get("portfolio")
    if not (audit.get("exact_changes") and audit.get("truthful") and audit.get("changed_paths") == ["throughput-portfolio.json"] and audit.get("trace_regime", {}).get("accepted") and audit.get("denial_classification_v2", {}).get("accepted")):
        return None, None
    if not isinstance(raw, dict) or set(raw) != {"question", "candidates"} or not isinstance(raw.get("candidates"), list) or len(raw["candidates"]) != 2:
        return None, None
    if not all(set(item) == {"candidate_id", "strategy", "rationale", "surrender_condition", "amendment"} and prior131.valid_text(item["amendment"]) for item in raw["candidates"]):
        return None, None
    projected = {"question": raw["question"], "candidates": [{key: item[key] for key in ["candidate_id", "strategy", "rationale", "surrender_condition"]} for item in raw["candidates"]]}
    valid, evaluations = previous.validate_portfolio(projected, previous.throughput_cases("public-c", [24, 56]))
    if not valid:
        return None, None
    removed = [{"candidate_id": item["candidate_id"], "amendment": item["amendment"]} for item in raw["candidates"]]
    receipt_body = {"authority": PROJECTION_VERSION, "source_subject_digest": subject["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "raw_portfolio_digest": p82.digest(raw), "removed_explanatory_fields": removed, "removed_fields_digest": p82.digest(removed), "preserved_semantic_portfolio_digest": p82.digest(projected)}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    body = {"authority": "ot-0148-bound-reconstructed-throughput-portfolio", "source_subject_digest": subject["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "projection_receipt_digest": receipt["receipt_digest"], "portfolio": projected, "public_candidates": [{"candidate": candidate, "public_evaluation": evaluation} for candidate, evaluation in zip(projected["candidates"], evaluations)]}
    binding = {**body, "binding_digest": p82.digest(body)}
    return binding, receipt


def deadline_floor(corrected: dict[str, Any], prior_result: dict[str, Any]) -> dict[str, Any]:
    portfolio = prior_result["later_portfolio"]["binding"]
    decision = previous.select(corrected, portfolio, previous.DEADLINE_CONTEXT)
    candidate = decision["selected_candidate"]
    result = previous.ot145.evaluate(candidate, previous.ot145.cases("deadline-floor", [96, 128, 160, 64]))
    return {"decision": decision, "evaluation": result}


def preflight(p82, parent: dict[str, Any], retained: dict[str, Any], prior_result: dict[str, Any]) -> dict[str, Any]:
    binding, receipt = reconstruct(p82, parent, retained)
    corrected = parent["constitutional_selector_program_capabilities"][-1]["program"]
    inherited = parent["constitutional_selector_program_capabilities"][-2]["program"]
    active = previous.select(corrected, binding, previous.THROUGHPUT_CONTEXT) if binding else None
    control = previous.select(inherited, binding, previous.THROUGHPUT_CONTEXT) if binding else None
    hidden = {item["candidate"]["candidate_id"]: previous.evaluate_throughput(item["candidate"], previous.throughput_cases("fixture", [72, 104, 136, 64])) for item in binding["public_candidates"]} if binding else {}
    reserve, recovery = previous.ot145.floors(p82, parent)
    deadline = deadline_floor(corrected, prior_result)
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "exact_projection": bool(binding and receipt and receipt["actor_patch_digest"] == retained["later_portfolio"]["audit"]["patch_digest"]),
        "active_passes": bool(active and hidden[active["selected_candidate"]["candidate_id"]]["passed"]),
        "control_fails": bool(control and not hidden[control["selected_candidate"]["candidate_id"]]["passed"]),
        "floors": reserve["passed"] and reserve["distinguishing_count"] == 9 and recovery["passed"] and recovery["shifted_pass_count"] == 3 and deadline["evaluation"]["passed"],
        "reuse_schema_present": previous.previous.REUSE_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "projection_receipt": receipt, "binding": binding, "active": active, "control": control, "reserve_floor": reserve, "ordinary_recovery_floor": recovery, "deadline_floor": deadline}


def seal_final(p82, subject: dict[str, Any], projection: dict[str, Any], reuse: dict[str, Any], selection: dict[str, Any], world: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {"authority": "ot-0148-exact-corrected-program-reuse-transition", "source_subject_digest": subject["artifact_digest"], "projection_receipt_digest": projection["receipt_digest"], "reuse_binding_digest": reuse["binding_digest"], "selection_binding_digest": selection["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["cross_world_selector_program_reuse_receipts"] = [*child.get("cross_world_selector_program_reuse_receipts", []), receipt]
    question = "Which materially different world should the continuing subject choose next without experiment-specific researcher selection remains unresolved."
    opening = "Open subject-selected-world-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = question
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
    run = (args.evidence_root or store / "runs/OT-0148").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0147", "open-subject-pending-corrected-program-reuse.json")
    retained = load_artifact(p82, repo, store, "OT-0147", "cross-world-selector-program-correction-aggregate.json")
    prior_result = load_artifact(p82, repo, store, "OT-0146", "actor-authored-selector-program-aggregate.json")
    fixtures = preflight(p82, parent, retained, prior_result)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0148 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    portfolio = fixtures["binding"]
    projection = fixtures["projection_receipt"]
    (run / "semantic-projection-receipt.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (run / "bound-reconstructed-portfolio.json").write_text(json.dumps(portfolio, indent=2, sort_keys=True) + "\n")
    capability = parent["constitutional_selector_program_capabilities"][-1]
    old_capability = parent["constitutional_selector_program_capabilities"][-2]
    reuse_root = run / "program-reuse"
    reuse_root.mkdir()
    reuse = previous.previous.run_reuse_actor(context, p82, reuse_root, parent, capability, portfolio)
    active = active_world = control = control_world = None
    final = parent
    transition = None
    if reuse["binding"]:
        active = previous.bind_selection(p82, parent, capability["program_binding_digest"], capability["program"], portfolio, "reused-corrected-program")
        active_world = previous.world_receipt(p82, portfolio, [active], previous.throughput_cases("reuse", [72, 104, 136, 64]), "ot-0148-active-reconstructed-program-world")
        (reuse_root / "sealed-active-world.json").write_text(json.dumps(active_world, indent=2, sort_keys=True) + "\n")
        if active_world["selected_results"]["reused-corrected-program"]["passed"]:
            final, transition = seal_final(p82, parent, projection, reuse["binding"], active, active_world)
        control = previous.bind_selection(p82, parent, old_capability["program_binding_digest"], old_capability["program"], portfolio, "unchanged-program-control")
        control_world = previous.world_receipt(p82, portfolio, [control], previous.throughput_cases("reuse", [72, 104, 136, 64]), "ot-0148-post-seal-unchanged-program-control")
        (run / "post-seal-control.json").write_text(json.dumps(control_world, indent=2, sort_keys=True) + "\n")
    checks = {
        "one_fresh_reuse_actor": bool(reuse["binding"]),
        "exact_semantic_projection": projection["actor_patch_digest"] == retained["later_portfolio"]["audit"]["patch_digest"],
        "active_passes": bool(active_world and active_world["selected_results"]["reused-corrected-program"]["passed"] and active_world["selected_results"]["reused-corrected-program"]["shifted_pass_count"] == 3),
        "post_seal_control_fails": bool(control_world and not control_world["selected_results"]["unchanged-program-control"]["passed"] and control_world["selected_results"]["unchanged-program-control"]["shifted_pass_count"] == 0),
        "program_history_retained": final.get("constitutional_selector_program_capabilities") == parent.get("constitutional_selector_program_capabilities"),
        "all_capability_roles_retained": bool(final.get("adaptive_contact_strategy_capabilities") and final.get("recovery_cadence_capabilities") and final.get("deadline_recovery_capabilities")),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open" and "subject-selected-world" in final["continuation"]["next_opening"],
    }
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0148-exact-corrected-program-reuse-driver", "source_subject_digest": parent["artifact_digest"], "projection_receipt": projection, "reconstructed_portfolio": portfolio, "reuse": p82.compact(reuse), "active_selection": active, "active_world": active_world, "reuse_transition": transition, "post_seal_unchanged_selection": control, "post_seal_unchanged_world": control_world, "checks": checks, "exact_corrected_program_reuse_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1, "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
