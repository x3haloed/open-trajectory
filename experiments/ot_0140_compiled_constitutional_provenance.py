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
BASE_PATH = ROOT / "ot_0139_consequence_revised_developmental_constitution.py"
BASE_SHA256 = "80ef1a10b8121ab2c458d20bfaa1904856d5c31ea85b55c158dbe9e95577c1a9"
PARENT_DIGEST = "e5e5338ae4f15f37ac2f6c7c243206e067e28dda439bbf1460f1fd0bf4448afe"
COMPILER_VERSION = "ot-0140-constitutional-provenance-v1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0139 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0140_frozen_ot0139", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
prior135 = prior.prior135
base130 = prior.base130
base = prior.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return prior135.load_json_artifact(p82, repo, store, experiment, manifest)


def source_action(aggregate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    rejected = aggregate["encounters"][1]
    return rejected["actor"], rejected["authorization"], aggregate["encounters"][0]["world"]


def compile_binding(p82, subject: dict[str, Any], aggregate: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    actor, auth, failure = source_action(aggregate)
    action = actor["action"]
    candidate = actor["constitution"]
    parent_constitution = subject["developmental_constitution"]
    envelope = auth["envelope_receipt"]
    semantic_fields = set(parent_constitution) - {"program_offset_ceiling", "parent_constitution_digest", "cause_receipt_digest", "constitution_digest"}
    semantic_exact = all(candidate.get(key) == parent_constitution.get(key) for key in semantic_fields)
    ceiling = candidate.get("program_offset_ceiling")
    compiled = prior.make_constitution(
        p82,
        ceiling,
        parent_constitution["constitution_digest"],
        envelope["receipt_digest"],
    ) if isinstance(ceiling, int) else None
    public = prior.evaluate(p82, action["program"], prior.previous.bases_for(auth["cycle"], auth["quantum"], public=True), auth["quantum"])
    checks = {
        "source_actor_rejected_only_at_binding": actor["action_valid"] is False and actor["audit"]["exact_changes"] and actor["audit"]["truthful"] and actor["audit"]["changed_paths"] == ["developmental-constitution.json", "encounter-action.json"],
        "authorization_exact": auth["allowed_action"] == "revise-constitution" and envelope["exhausted"] and envelope["least_passing_symmetric_offset"] == 16,
        "action_exact": action["action"] == "revise-constitution" and action["program"]["high_offset"] == action["program"]["low_offset"] == 16,
        "semantic_ceiling_exact": ceiling == 16 and semantic_exact,
        "public_reconstruction_passed": public["passed"] and public["distinguishing_count"] == 6,
        "compiled_constitution_valid": bool(compiled and prior.program_valid(action["program"], compiled)),
        "compiler_erased_reproduces_rejection": not prior.constitution_revision_valid(p82, parent_constitution, candidate, auth),
        "compiled_binding_would_pass": bool(compiled and prior.constitution_revision_valid(p82, parent_constitution, compiled, auth)),
    }
    checks["passed"] = all(checks.values())
    if not checks["passed"]:
        return None, {"checks": checks, "compiled_constitution": compiled, "public": public}
    body = {
        "authority": "ot-0140-compiled-constitutional-action-binding",
        "compiler_version": COMPILER_VERSION,
        "source_subject_digest": subject["artifact_digest"],
        "source_ot0139_actor_patch_digest": actor["audit"]["patch_digest"],
        "source_authorization_binding_digest": auth["binding_digest"],
        "source_failure_receipt_digest": failure["receipt_digest"],
        "actor_semantic_ceiling": ceiling,
        "action": action,
        "compiled_constitution": compiled,
        "compiler_checks": checks,
    }
    binding = {**body, "binding_digest": p82.digest(body)}
    return binding, {"checks": checks, "compiled_constitution": compiled, "public": public}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0140").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0139", "open-subject-with-retained-q16-failure.json")
    aggregate = load_artifact(p82, repo, store, "OT-0139", "consequence-revised-constitution-aggregate.json")
    binding, compilation = compile_binding(p82, parent, aggregate)
    actor, auth, failure = source_action(aggregate)
    program = actor["action"]["program"]
    corrected = prior.evaluate(p82, program, prior.previous.bases_for(failure["cycle"], failure["quantum"]), failure["quantum"])
    floor = prior.evaluate(p82, program, prior.previous.bases_for(6, parent["encounter_scheduler"]["admitted_quantum"]), parent["encounter_scheduler"]["admitted_quantum"])
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
        "source_aggregate_rejected_exact": not aggregate["constitutional_revision_passed"] and aggregate["final_subject_digest"] == parent["artifact_digest"],
        "compilation_passed": bool(binding and compilation["checks"]["passed"]),
        "unchanged_failure_exact": not failure["selected_branch"]["passed"] and failure["selected_branch"]["distinguishing_count"] == 3,
        "corrected_hidden_prediction": corrected["passed"] and corrected["distinguishing_count"] == 9 and corrected["confirmation_count"] == 3,
        "prior_floor_prediction": floor["passed"] and floor["distinguishing_count"] == 9 and floor["confirmation_count"] == 3,
        "action_schema_present": prior.ACTION_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "checks": checks, "compilation": compilation, "corrected": corrected, "floor": floor}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0140 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps({"checks": checks, "compilation": compilation, "corrected_prediction": corrected, "floor_prediction": floor}, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("pre-consequence conformance failed")
    (run / "compiled-constitutional-binding.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    started = time.time()
    failure_bases = prior.previous.bases_for(failure["cycle"], failure["quantum"])
    hidden_eval = prior.evaluate(p82, program, failure_bases, failure["quantum"])
    hidden = prior.world_receipt(p82, auth, binding, hidden_eval, failure_bases)
    floor_eval = prior.evaluate(p82, program, prior.previous.bases_for(6, parent["encounter_scheduler"]["admitted_quantum"]), parent["encounter_scheduler"]["admitted_quantum"])
    (run / "sealed-corrected-world-receipt.json").write_text(json.dumps(hidden, indent=2, sort_keys=True) + "\n")
    (run / "prior-floor-receipt.json").write_text(json.dumps(floor_eval, indent=2, sort_keys=True) + "\n")
    installed, install_transition = prior.transition(p82, parent, auth, binding, hidden, floor_eval, failure["selected_branch"])
    installation_ok = bool(
        runtime.identity_conforms(installed)
        and installed["encounter_scheduler"]["cycle"] == 6
        and installed["encounter_scheduler"]["verification_due"]
        and installed["developmental_constitution"] == binding["compiled_constitution"]
        and installed["contact_program_capabilities"][-1]["program"] == program
    )
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    verification_root = run / "encounter-7"
    verification_root.mkdir()
    verification_auth = prior.authorization(p82, installed) if installation_ok else None
    verification = prior.run_actor(context, p82, verification_root, installed, verification_auth) if verification_auth else None
    final = installed
    verification_world = None
    verification_transition = None
    if verification and verification["binding"]:
        bases = prior.previous.bases_for(7, verification_auth["quantum"])
        evaluation = prior.evaluate(p82, verification["action"]["program"], bases, verification_auth["quantum"])
        verification_world = prior.world_receipt(p82, verification_auth, verification["binding"], evaluation, bases)
        (verification_root / "sealed-world-receipt.json").write_text(json.dumps(verification_world, indent=2, sort_keys=True) + "\n")
        final, verification_transition = prior.transition(p82, installed, verification_auth, verification["binding"], verification_world)
    erased = copy.deepcopy(final)
    erased.pop("artifact_digest", None)
    erased.pop("developmental_constitution", None)
    erased = p82.seal(erased)
    state = final["encounter_scheduler"]
    result_checks = {
        "compiled_binding_passed": binding is not None and compilation["checks"]["passed"],
        "corrected_beats_identical_parent": hidden_eval["passed"] and hidden_eval["distinguishing_count"] == 9 and failure["selected_branch"]["distinguishing_count"] == 3,
        "prior_floor_preserved": floor_eval["passed"] and floor_eval["distinguishing_count"] == 9,
        "compiled_constitution_installed": installation_ok,
        "fresh_verification_actor": bool(verification and verification["binding"] and verification["action"]["action"] == "reuse"),
        "later_reuse_without_repair": bool(verification_world and verification_world["selected_branch"]["passed"] and verification["action"]["program"] == program),
        "scheduler_points_beyond_observer": state["cycle"] == 7 and state["admitted_quantum"] == 16 and state["next_quantum"] == 32 and not state["verification_due"] and state["pending_failure"] is None,
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open" and "reserve band 32" in final["continuation"]["next_opening"],
        "compiler_erased_control_rejects": compilation["checks"]["compiler_erased_reproduces_rejection"],
        "constitution_erased_has_no_authority": "developmental_constitution" not in erased,
    }
    result_checks["passed"] = all(result_checks.values())
    result = {
        "authority": "ot-0140-compiled-constitutional-provenance-driver",
        "source_subject_digest": parent["artifact_digest"],
        "compiled_binding": binding,
        "hidden_corrected_world": hidden,
        "prior_floor": floor_eval,
        "installation_transition": install_transition,
        "verification": p82.compact(verification) if verification else None,
        "verification_world": verification_world,
        "verification_transition": verification_transition,
        "checks": result_checks,
        "compiled_constitutional_revision_passed": result_checks["passed"],
        "observer_disposition": "promoted" if result_checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": int(verification is not None),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    (run / "constitution-erased-control.json").write_text(json.dumps(erased, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result_checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
