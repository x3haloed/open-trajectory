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
BASE_PATH = ROOT / "ot_0140_compiled_constitutional_provenance.py"
BASE_SHA256 = "3c898d932ef193ed623413688b10a1ce3e083530288faf6bc627c6e73e962bf7"
PARENT_DIGEST = "e5e5338ae4f15f37ac2f6c7c243206e067e28dda439bbf1460f1fd0bf4448afe"
PROJECTION_VERSION = "ot-0141-transition-view-v1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0140 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0141_frozen_ot0140", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior = previous.prior
prior135 = previous.prior135
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return prior135.load_json_artifact(p82, repo, store, experiment, manifest)


def transition_view(p82, binding: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    constitution = binding["compiled_constitution"]
    view = {**binding, "constitution": constitution}
    receipt_body = {
        "authority": "ot-0141-constitutional-transition-view",
        "projection_version": PROJECTION_VERSION,
        "source_binding_digest": binding["binding_digest"],
        "source_field": "compiled_constitution",
        "consumer_field": "constitution",
        "constitution_digest": constitution["constitution_digest"],
        "bytes_equal": view["constitution"] == binding["compiled_constitution"],
        "binding_identity_unchanged": view["binding_digest"] == binding["binding_digest"],
    }
    return view, {**receipt_body, "receipt_digest": p82.digest(receipt_body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0141").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0139", "open-subject-with-retained-q16-failure.json")
    binding = load_artifact(p82, repo, store, "OT-0140", "compiled-constitutional-binding.json")
    hidden = load_artifact(p82, repo, store, "OT-0140", "sealed-corrected-constitutional-world.json")
    floor = load_artifact(p82, repo, store, "OT-0140", "compiled-constitution-prior-floor.json")
    view, projection = transition_view(p82, binding)
    auth = prior.authorization(p82, parent)
    failure = parent["encounter_scheduler"]["pending_failure"]
    installed, install_transition = prior.transition(p82, parent, auth, view, hidden, floor, failure["selected_branch"])
    installation_checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
        "authorization_reconstructed_exact": auth["binding_digest"] == binding["source_authorization_binding_digest"] and auth["allowed_action"] == "revise-constitution",
        "binding_source_exact": binding["compiler_version"] == previous.COMPILER_VERSION and binding["source_subject_digest"] == parent["artifact_digest"],
        "unprojected_reproduces_failure": "constitution" not in binding,
        "projection_exact": projection["bytes_equal"] and projection["binding_identity_unchanged"] and view["constitution"] == binding["compiled_constitution"],
        "hidden_exact": hidden["selected_branch"]["passed"] and hidden["selected_branch"]["distinguishing_count"] == 9 and hidden["selected_branch"]["confirmation_count"] == 3 and hidden["actor_binding_digest"] == binding["binding_digest"],
        "unchanged_failure_exact": not failure["selected_branch"]["passed"] and failure["selected_branch"]["distinguishing_count"] == 3,
        "floor_exact": floor["passed"] and floor["distinguishing_count"] == 9 and floor["confirmation_count"] == 3,
        "installation_identity": runtime.identity_conforms(installed),
        "compiled_constitution_installed": installed["developmental_constitution"] == binding["compiled_constitution"],
        "compiled_program_installed": installed["contact_program_capabilities"][-1]["program"] == binding["action"]["program"],
        "verification_due_exact": installed["encounter_scheduler"]["cycle"] == 6 and installed["encounter_scheduler"]["verification_due"] and installed["encounter_scheduler"]["pending_failure"] is None,
    }
    installation_checks["passed"] = all(installation_checks.values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "installation_checks": installation_checks, "projection": projection, "installed_subject_digest": installed["artifact_digest"]}, indent=2, sort_keys=True))
        return 0 if installation_checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0141 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps({"installation_checks": installation_checks}, indent=2, sort_keys=True) + "\n")
    (run / "transition-projection-receipt.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (run / "installed-before-verification.json").write_text(json.dumps(installed, indent=2, sort_keys=True) + "\n")
    if not installation_checks["passed"]:
        raise SystemExit("pre-actor installation conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    verification_root = run / "encounter-7"
    verification_root.mkdir()
    verification_auth = prior.authorization(p82, installed)
    verification = prior.run_actor(context, p82, verification_root, installed, verification_auth)
    final = installed
    world = None
    final_transition = None
    if verification["binding"]:
        bases = prior.previous.bases_for(7, verification_auth["quantum"])
        evaluation = prior.evaluate(p82, verification["action"]["program"], bases, verification_auth["quantum"])
        world = prior.world_receipt(p82, verification_auth, verification["binding"], evaluation, bases)
        (verification_root / "sealed-world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
        final, final_transition = prior.transition(p82, installed, verification_auth, verification["binding"], world)
    erased = copy.deepcopy(final)
    erased.pop("artifact_digest", None)
    erased.pop("developmental_constitution", None)
    erased = p82.seal(erased)
    state = final["encounter_scheduler"]
    checks = {
        "installation_passed": installation_checks["passed"],
        "one_fresh_verification_actor": bool(verification["binding"] and verification["action"]["action"] == "reuse"),
        "program_and_constitution_retained": bool(verification["binding"] and verification["action"]["program"] == binding["action"]["program"] and verification["constitution"] == binding["compiled_constitution"]),
        "later_reuse_without_repair": bool(world and world["selected_branch"]["passed"] and world["selected_branch"]["distinguishing_count"] == 9 and world["selected_branch"]["confirmation_count"] == 3),
        "scheduler_points_beyond_observer": state["cycle"] == 7 and state["admitted_quantum"] == 16 and state["next_quantum"] == 32 and not state["verification_due"] and state["pending_failure"] is None,
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open" and "reserve band 32" in final["continuation"]["next_opening"],
        "constitution_erased_has_no_authority": "developmental_constitution" not in erased,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0141-constitutional-transition-projection-driver",
        "source_subject_digest": parent["artifact_digest"],
        "source_compiled_binding_digest": binding["binding_digest"],
        "projection": projection,
        "installation_transition": install_transition,
        "verification": p82.compact(verification),
        "verification_world": world,
        "verification_transition": final_transition,
        "checks": checks,
        "constitutional_transition_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": 1,
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    (run / "constitution-erased-control.json").write_text(json.dumps(erased, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
