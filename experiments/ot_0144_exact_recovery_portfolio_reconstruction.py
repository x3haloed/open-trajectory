from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0143_cross_domain_constitutional_selector_transfer.py"
BASE_SHA256 = "a919b3362aa07ed9c94b0f9c63bc574c51e27c2cbf1fffa35c5c80065f52c05f"
PARENT_DIGEST = "a66da59648c69b0b963be36da25e37156ad55f12598d749964c02e5bfb8dce4d"
RECONSTRUCTION_VERSION = "ot-0144-effects-reconstruction-v1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0143 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0144_frozen_ot0143", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base130 = prior.base130
base = prior.base


def bind_exact_portfolio(p82, subject: dict[str, Any], portfolio: dict[str, Any], public_cases: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    valid, evaluations = prior.validate_portfolio(portfolio, public_cases)
    checks = {
        "portfolio_public_valid": valid and all(item["passed"] for item in evaluations),
        "families_exact": {item["strategy"]["kind"] for item in portfolio["candidates"]} == {"fixed-delay", "latency-relative"},
        "actual_path_authoritative": True,
        "stale_report_literal_disclosed": True,
    }
    checks["passed"] = all(checks.values())
    if not checks["passed"]:
        return None, checks
    body = {
        "authority": "ot-0144-bound-exact-recovery-portfolio",
        "reconstruction_version": RECONSTRUCTION_VERSION,
        "source_subject_digest": subject["artifact_digest"],
        "source_experiment": "OT-0143",
        "actual_changed_path": "recovery-amendment-portfolio.json",
        "visible_editable_path": "recovery-amendment-portfolio.json",
        "forced_stale_report_path": "amendment-portfolio.json",
        "portfolio": portfolio,
        "public_candidates": [{"candidate": candidate, "public_evaluation": evaluation} for candidate, evaluation in zip(portfolio["candidates"], evaluations)],
        "reconstruction_checks": checks,
    }
    return {**body, "binding_digest": p82.digest(body)}, checks


def preflight(p82, parent: dict[str, Any], portfolio: dict[str, Any], initial_selector: dict[str, Any]) -> dict[str, Any]:
    binding, reconstruction = bind_exact_portfolio(p82, parent, portfolio, prior.recovery_cases("public", [32, 32]))
    active = prior.bind_selection(p82, parent, parent["constitutional_amendment_selector"], binding, "active") if binding else None
    control = prior.bind_selection(p82, parent, initial_selector, binding, "unchanged-control") if binding else None
    world = prior.world_receipt(p82, binding, [active, control], prior.recovery_cases("sealed", [64, 96, 128, 32, 32]), "ot-0144-fixture-recovery-world") if binding else None
    adaptive = parent["adaptive_contact_strategy_capabilities"][-1]
    reserve_candidate = {"candidate_id": adaptive["candidate_id"], "strategy": adaptive["strategy"], "rationale": "retained", "surrender_condition": "retained"}
    reserve_floor = prior.prior.candidate_evaluation(p82, parent["contact_program_capabilities"][-1]["program"], reserve_candidate, prior.prior.prior.previous.bases_for(11, 256), 256)
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "reconstruction_passed": bool(binding and reconstruction["passed"]),
        "active_relative": bool(active and active["decision"]["selected_candidate"]["strategy"]["kind"] == "latency-relative"),
        "control_fixed": bool(control and control["decision"]["selected_candidate"]["strategy"]["kind"] == "fixed-delay"),
        "world_separates": bool(world and world["selected_results"]["active"]["passed"] and world["selected_results"]["active"]["shifted_pass_count"] == 3 and not world["selected_results"]["unchanged-control"]["passed"] and world["selected_results"]["unchanged-control"]["shifted_pass_count"] == 0),
        "reserve_floor": reserve_floor["passed"] and reserve_floor["distinguishing_count"] == 9 and reserve_floor["confirmation_count"] == 3,
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "binding": binding, "active": active, "control": control, "world": world, "reserve_floor": reserve_floor}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0144").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = prior.load_artifact(p82, repo, store, "OT-0142", "open-subject-with-adaptive-constitutional-selector.json")
    portfolio = prior.load_artifact(p82, repo, store, "OT-0143", "retained-recovery-amendment-portfolio.json")
    initial_selector = prior.prior.make_selector(p82, prior.prior.INITIAL_PRIORITY, prior.prior.SELECTOR_VERSION)
    fixtures = preflight(p82, parent, portfolio, initial_selector)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0144 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps({"checks": fixtures["checks"]}, indent=2, sort_keys=True) + "\n")
    (run / "bound-exact-recovery-portfolio.json").write_text(json.dumps(fixtures["binding"], indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor reconstruction conformance failed")
    started = time.time()
    active = fixtures["active"]
    control = fixtures["control"]
    world = prior.world_receipt(p82, fixtures["binding"], [active, control], prior.recovery_cases("sealed", [64, 96, 128, 32, 32]), "ot-0144-sealed-cross-domain-recovery-world")
    reserve_floor = fixtures["reserve_floor"]
    (run / "sealed-matched-recovery-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    (run / "reserve-no-regression-receipt.json").write_text(json.dumps(reserve_floor, indent=2, sort_keys=True) + "\n")
    installed, installation = prior.install_recovery(p82, parent, fixtures["binding"], active, world, reserve_floor)
    installation_ok = bool(runtime.identity_conforms(installed) and installed["recovery_cadence_capabilities"][-1]["strategy"]["kind"] == "latency-relative")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    reuse_root = run / "later-recovery-reuse"
    reuse_root.mkdir()
    capability = installed["recovery_cadence_capabilities"][-1]
    reuse = prior.run_reuse_actor(context, p82, reuse_root, installed, capability) if installation_ok else None
    reuse_world = None
    final = installed
    reuse_transition = None
    if reuse and reuse["binding"]:
        candidate = {"candidate_id": capability["candidate_id"], "strategy": capability["strategy"], "rationale": "retained", "surrender_condition": "retained"}
        reuse_world = prior.evaluate(candidate, prior.recovery_cases("reuse", [160, 192, 224, 32]))
        (reuse_root / "sealed-recovery-reuse-world.json").write_text(json.dumps(reuse_world, indent=2, sort_keys=True) + "\n")
        if reuse_world["passed"]:
            final, reuse_transition = prior.final_subject(p82, installed, reuse["binding"], reuse_world)
    fixed_control = prior.evaluate(control["decision"]["selected_candidate"], prior.recovery_cases("reuse", [160, 192, 224, 32]))
    (run / "post-seal-fixed-delay-control.json").write_text(json.dumps(fixed_control, indent=2, sort_keys=True) + "\n")
    checks = {
        "exact_portfolio_bound": fixtures["binding"]["reconstruction_checks"]["passed"],
        "matched_active_beats_control": world["selected_results"]["active"]["passed"] and world["selected_results"]["active"]["shifted_pass_count"] == 3 and not world["selected_results"]["unchanged-control"]["passed"] and world["selected_results"]["unchanged-control"]["shifted_pass_count"] == 0,
        "reserve_floor_preserved": reserve_floor["passed"] and reserve_floor["distinguishing_count"] == 9,
        "cross_domain_capability_installed": installation_ok,
        "one_fresh_reuse_actor": bool(reuse and reuse["binding"] and reuse["action"]["strategy"] == capability["strategy"]),
        "later_reuse_without_revision": bool(reuse_world and reuse_world["passed"] and reuse_world["shifted_pass_count"] == 3),
        "post_seal_fixed_control_fails": not fixed_control["passed"] and fixed_control["shifted_pass_count"] == 0 and fixed_control["control_pass_count"] == 1,
        "selector_erasure_reproduces_control": prior.select(initial_selector, fixtures["binding"])["selected_candidate"] == control["decision"]["selected_candidate"],
        "both_capability_families_retained": bool(final.get("adaptive_contact_strategy_capabilities") and final.get("recovery_cadence_capabilities")),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open" and final["cross_domain_scheduler"]["cycle"] == 2 and "contradictory operating regime" in final["continuation"]["next_opening"],
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0144-exact-recovery-portfolio-reconstruction-driver",
        "source_subject_digest": parent["artifact_digest"],
        "portfolio_binding": fixtures["binding"],
        "active_selection": active,
        "unchanged_control_selection": control,
        "matched_recovery_world": world,
        "reserve_no_regression": reserve_floor,
        "installation_receipt": installation,
        "later_reuse": p82.compact(reuse) if reuse else None,
        "later_reuse_world": reuse_world,
        "later_reuse_transition": reuse_transition,
        "post_seal_fixed_control": fixed_control,
        "checks": checks,
        "cross_domain_reconstruction_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": int(reuse is not None),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
