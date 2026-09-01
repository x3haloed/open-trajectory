from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0131_subject_originated_contact.py"
BASE_SHA256 = "08bf0057b454acb0f382420b7048696728d0f233c6d6dfc7784fbf5d75e59742"
PARENT_DIGEST = "34c8ce6ded8640e0394578804d6badc08a2fe69b51a852c8fe8bec4624b565f3"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0131 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0132_frozen_ot0131", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base130 = prior.base130
prior22 = prior.prior22
prior18 = prior.prior18
base = prior.base


def safe_extract(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive) as handle:
        members = handle.getmembers()
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise RuntimeError("unsafe retained archive member")
        handle.extractall(destination, members=members, filter="data")
    return destination / "OT-0131"


def exact_world(p82, binding: dict[str, Any]) -> dict[str, Any]:
    evaluation = prior.evaluate_proposal(p82, binding["proposal"])
    contact_id = "originated-" + hashlib.sha256(json.dumps(binding["proposal"], sort_keys=True).encode()).hexdigest()[:16]
    body = {
        "authority": "ot-0131-independent-context-local-world",
        "contact_binding_digest": binding["binding_digest"],
        "selected_contact_id": contact_id,
        "selected_branch": evaluation,
        "expected_route": "extend" if evaluation["decisive"] else "surrender",
    }
    return {**body, "receipt_digest": p82.digest(body)}


def reconstruct_active(p82, prior89, parent: dict[str, Any], selector: str, retained: Path, output: Path) -> dict[str, Any]:
    contact_binding = json.loads((retained / "active-contact-author/bound-contact-proposal.json").read_text())
    contact_audit = json.loads((retained / "active-contact-author/actor-audit.json").read_text())
    stored_world = json.loads((retained / "active-contact/selected-world-receipt.json").read_text())
    route = json.loads((retained / "consequence-route/actor-workspace/route-assimilation.json").read_text())
    route_audit = json.loads((retained / "consequence-route/actor-audit.json").read_text())
    route_selector = (retained / "consequence-route/actor-workspace/selector.py").read_text()
    world = exact_world(p82, contact_binding)
    expected_ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    actor_checks = {
        "route_exact": route.get("route") == world["expected_route"] == "extend",
        "contact_id_exact": route.get("selected_contact_id") == world["selected_contact_id"],
        "case_ids_exact": set(route.get("settled_case_ids", [])) == expected_ids,
        "selector_retained": route_selector == selector,
        "remaining_uncertainty_new": prior.valid_text(route.get("remaining_uncertainty")) and len(route["remaining_uncertainty"].strip()) >= 24 and route["remaining_uncertainty"].strip() != parent["continuation"]["next_opening"].strip(),
    }
    actor_checks["passed"] = all(actor_checks.values())
    action = base130.compile_action(route, 4)
    opening = base130.previous.compile_opening(route, action)
    compiler_checks = {
        "action_valid": prior18.previous.previous.repaired_action_valid(action, parent),
        "target_new": action["action_target"] not in prior22.kernel.registered(parent),
        "expected_information_exact": action["expected_information"] == route["remaining_uncertainty"],
        "opening_structurally_valid": prior89.valid_successor(opening),
        "uncertainty_retained_exactly": opening["unresolved"] == route["remaining_uncertainty"] and route["remaining_uncertainty"] in opening["next_opening"] and route["remaining_uncertainty"] in opening["continuation_after_contact"],
        "compiler_deterministic": action == base130.compile_action(route, 4) and opening == base130.previous.compile_opening(route, action),
    }
    compiler_checks["passed"] = all(compiler_checks.values())
    contact_body = {key: value for key, value in contact_binding.items() if key != "binding_digest"}
    binding_checks = {
        "contact_binding_exact": contact_binding["binding_digest"] == p82.digest(contact_body),
        "contact_source_exact": contact_binding["source_subject_digest"] == parent["artifact_digest"],
        "contact_opening_exact": contact_binding["opening"] == parent["continuation"]["next_opening"],
        "contact_proposal_valid": prior.valid_proposal(contact_binding["proposal"]),
        "contact_audit_accepted": prior.audit_accepted(contact_audit),
        "world_exact": world == stored_world,
        "active_target_decisive": world["selected_branch"]["target"] == prior.ACTIVE_TARGET and world["selected_branch"]["decisive"],
        "route_valid": prior22.valid_route(route) and actor_checks["passed"],
        "route_audit_accepted": prior.audit_accepted(route_audit),
        "compiler_passed": compiler_checks["passed"],
    }
    binding_checks["passed"] = all(binding_checks.values())
    routed = None
    if binding_checks["passed"]:
        actor_body = {
            "authority": "ot-0131-grounded-route",
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": contact_binding["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": route_audit["patch_digest"],
            "actor_checks": actor_checks,
            "selector_retention_derived": True,
            "route_assimilation": route,
        }
        actor_binding = {**actor_body, "binding_digest": p82.digest(actor_body)}
        body = {
            "authority": "ot-0131-route-only-compiled-continuation",
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": contact_binding["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_binding_digest": actor_binding["binding_digest"],
            "compiler_version": base130.COMPILER_VERSION,
            "compiler_checks": compiler_checks,
            "selector_retention_derived": True,
            "route_assimilation": route,
            "successor_opening": opening,
            "continuation_action": action,
        }
        routed = {**body, "binding_digest": p82.digest(body)}
        (output / "bound-retained-contact.json").write_text(json.dumps(contact_binding, indent=2, sort_keys=True) + "\n")
        (output / "reconstructed-world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
        (output / "bound-retained-route.json").write_text(json.dumps(actor_binding, indent=2, sort_keys=True) + "\n")
        (output / "compiled-continuation-action.json").write_text(json.dumps(action, indent=2, sort_keys=True) + "\n")
        (output / "compiled-successor-opening.json").write_text(json.dumps(opening, indent=2, sort_keys=True) + "\n")
        (output / "bound-compiled-route.json").write_text(json.dumps(routed, indent=2, sort_keys=True) + "\n")
    return {
        "contact_binding": contact_binding,
        "world": world,
        "actor_checks": actor_checks,
        "compiler_checks": compiler_checks,
        "binding_checks": binding_checks,
        "binding": routed,
    }


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = p82.materialize(repo, store, "OT-0130", "open-route-only-recurrent-subject.json")
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0132").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    selector = parent["allocation_machinery"][-1]["source"]
    _, archive = p82.materialize(repo, store, "OT-0131", "subject-originated-contact-apparatus-failure-run.json")
    with tempfile.TemporaryDirectory() as directory:
        retained = safe_extract(archive, Path(directory))
        required = [
            "active-contact-author/bound-contact-proposal.json",
            "active-contact-author/actor-audit.json",
            "active-contact/selected-world-receipt.json",
            "consequence-route/actor-workspace/route-assimilation.json",
            "consequence-route/actor-workspace/selector.py",
            "consequence-route/actor-audit.json",
        ]
        checks = {
            "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
            "retained_files_complete": all((retained / item).is_file() for item in required),
            "no_prior_control": not (retained / "control-contact-author").exists(),
            "correct_validator_available": prior89.valid_successor(base130.previous.compile_opening(prior.REPRESENTATIVE_ACTIVE | {"route": "extend", "selected_contact_id": "fixture", "consequence_summary": "fixture", "settled_case_ids": ["fixture"], "remaining_uncertainty": "Whether a distinct fixture boundary remains unresolved.", "selection_rule_disposition": "preserved", "surrender_condition": "Surrender if absent."}, base130.compile_action({"route": "extend", "selected_contact_id": "fixture", "consequence_summary": "fixture", "settled_case_ids": ["fixture"], "remaining_uncertainty": "Whether a distinct fixture boundary remains unresolved.", "selection_rule_disposition": "preserved", "surrender_condition": "Surrender if absent."}, 4))),
        }
        checks["passed"] = all(checks.values())
        if args.preflight_only:
            print(json.dumps({"base_sha256": BASE_SHA256, "checks": checks}, indent=2, sort_keys=True))
            return 0 if checks["passed"] else 2
        if run.exists():
            raise SystemExit("preserve existing OT-0132 evidence")
        run.mkdir(parents=True)
        (run / "fixture-conformance.json").write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n")
        if not checks["passed"]:
            raise SystemExit("pre-reconstruction conformance failed")
        started = time.time()
        reconstructed = reconstruct_active(p82, prior89, parent, selector, retained, run)
    current = parent
    promotion = None
    operational = False
    if reconstructed["binding"]:
        current, promotion = prior22.promote(p82, parent, reconstructed["contact_binding"], reconstructed["world"], reconstructed["binding"])
        operational = bool(runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and current["artifact_digest"] != parent["artifact_digest"])
    control = None
    control_world = None
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
        control_root = run / "control-contact"
        control_root.mkdir()
        control = prior.run_contact_actor(context, p82, control_root, "control-contact-author", prior.control_position(parent))
        control_world = prior.open_world(p82, control_root, control["binding"]) if control["binding"] else None
    pursuit_conditioned = bool(
        operational
        and reconstructed["world"]["selected_branch"]["decisive"]
        and reconstructed["world"]["selected_branch"]["target"] == prior.ACTIVE_TARGET
        and control_world
        and control_world["selected_branch"]["decisive"]
        and control_world["selected_branch"]["target"] == prior.CONTROL_TARGET
    )
    result = {
        "authority": "ot-0132-exact-contact-reconstruction-driver",
        "source_subject_digest": parent["artifact_digest"],
        "retained_active_reconstruction": p82.compact(reconstructed),
        "promotion": promotion,
        "control_contact": p82.compact(control) if control else None,
        "control_world": control_world,
        "operational_transition_passed": operational,
        "pursuit_conditioned_contact_passed": pursuit_conditioned,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "retained_actor_count": 2,
        "fresh_actor_count": 1 if control is not None else 0,
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
