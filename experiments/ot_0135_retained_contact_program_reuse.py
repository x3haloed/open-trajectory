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
BASE_PATH = ROOT / "ot_0134_exact_contact_program_reconstruction.py"
BASE_SHA256 = "d3f12a9cdf5979ebbe50e79e6eebf823e17d6f16201deb6837376aaed39f917b"
PARENT_DIGEST = "7cc630ed46b2da021439e6688e0b5cea65deccbb753ec8b98c2e2f21aad70f78"
COMPOSITION_VERSION = "ot-0135-joint-v1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0134 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0135_frozen_ot0134", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base134 = load_base()
prior133 = base134.prior
prior131 = prior133.prior
base130 = base134.base130
base = base134.base


JOINT_BASES = [
    {"base_id": "joint-saffron", "context": "saffron", "insert_at": [1, 3], "demands": [16, 24, 20, 16]},
    {"base_id": "joint-teal", "context": "teal", "insert_at": [2, 4], "demands": [13, 18, 23, 17, 13]},
    {"base_id": "joint-violet", "context": "violet", "insert_at": [1, 5], "demands": [15, 21, 26, 22, 18, 15]},
]


def load_json_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    _, path = p82.materialize(repo, store, experiment, manifest)
    return json.loads(path.read_text())


def capability_from_aggregate(p82, aggregate: dict[str, Any]) -> dict[str, Any]:
    binding = aggregate["program_binding"]
    program = binding["program"]
    program_digest = binding["public_receipt"]["program_digest"]
    body = {
        "authority": "ot-0135-admitted-contact-program-capability",
        "capability_id": "contact-program-" + program_digest[:16],
        "program_digest": program_digest,
        "program": program,
        "target": program["target"],
        "source_binding_digest": binding["binding_digest"],
        "source_world_receipt_digest": aggregate["hidden_world"]["receipt_digest"],
        "public_conformance_passed": binding["public_receipt"]["passed"],
        "hidden_conformance_passed": aggregate["hidden_world"]["selected_branch"]["passed"],
        "composition_interface": COMPOSITION_VERSION,
    }
    return {**body, "capability_digest": p82.digest(body)}


def enrich_subject(p82, parent: dict[str, Any], capability: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["contact_program_capabilities"] = [*child.get("contact_program_capabilities", []), capability]
    receipt_body = {
        "authority": "ot-0135-contact-program-retention",
        "source_subject_digest": parent["artifact_digest"],
        "capability_id": capability["capability_id"],
        "capability_digest": capability["capability_digest"],
        "source_binding_digest": capability["source_binding_digest"],
        "source_world_receipt_digest": capability["source_world_receipt_digest"],
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child["contact_program_retention_receipts"] = [*child.get("contact_program_retention_receipts", []), receipt]
    return p82.seal(child), receipt


def capability_valid(p82, capability: dict[str, Any]) -> bool:
    body = {key: value for key, value in capability.items() if key != "capability_digest"}
    return bool(
        capability.get("capability_digest") == p82.digest(body)
        and capability.get("program_digest") == p82.digest(capability.get("program"))
        and base134.corrected_valid_program(capability.get("program"))
        and capability.get("target") == prior131.ACTIVE_TARGET
        and capability.get("public_conformance_passed") is True
        and capability.get("hidden_conformance_passed") is True
        and capability.get("composition_interface") == COMPOSITION_VERSION
    )


def bind_reuse(p82, subject: dict[str, Any], output: Path | None = None) -> dict[str, Any] | None:
    opening = subject["continuation"]["next_opening"]
    capabilities = subject.get("contact_program_capabilities", [])
    eligible = [capability for capability in capabilities if capability_valid(p82, capability)]
    opening_matches = all(term in opening.lower() for term in ("multiple", "foreign-context", "reserve"))
    if not opening_matches or len(eligible) != 1:
        return None
    capability = eligible[0]
    body = {
        "authority": "ot-0135-continuation-owned-capability-reuse",
        "source_subject_digest": subject["artifact_digest"],
        "opening": opening,
        "capability_id": capability["capability_id"],
        "capability_digest": capability["capability_digest"],
        "program_digest": capability["program_digest"],
        "composition_version": COMPOSITION_VERSION,
    }
    binding = {**body, "binding_digest": p82.digest(body)}
    if output is not None:
        (output / "bound-capability-reuse.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return binding


def local_events(base_case: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"context": base_case["context"], "demand": demand} for demand in base_case["demands"]]


def insert_two(events: list[dict[str, Any]], positions: list[int], additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = list(events)
    for position, addition in sorted(zip(positions, additions), reverse=True):
        result.insert(position, addition)
    return result


def joint_variants(program: dict[str, Any], base_case: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    events = local_events(base_case)
    low, high = min(base_case["demands"]), max(base_case["demands"])
    prefix = program["foreign_context_prefix"]
    contexts = [f"{prefix}-a-{base_case['context']}", f"{prefix}-b-{base_case['context']}"]
    extremes = [
        {"context": contexts[0], "demand": high + program["high_offset"]},
        {"context": contexts[1], "demand": low - program["low_offset"]},
    ]
    highs = [
        {"context": contexts[0], "demand": high + program["high_offset"]},
        {"context": contexts[1], "demand": high + program["high_offset"]},
    ]
    midpoint = (low + high) // 2
    controls = [
        {"context": contexts[0], "demand": midpoint},
        {"context": contexts[1], "demand": midpoint},
    ]
    return {
        "joint-extremes": insert_two(events, base_case["insert_at"], extremes),
        "joint-high": insert_two(events, base_case["insert_at"], highs),
        "joint-control": insert_two(events, base_case["insert_at"], controls),
    }


def evaluate_joint_program(p82, capability: dict[str, Any], bases: list[dict[str, Any]]) -> dict[str, Any]:
    program = capability["program"]
    rows = []
    for base_case in bases:
        reference = prior131.reference_value(program["target"], local_events(base_case), base_case["context"])
        for variant, events in joint_variants(program, base_case).items():
            installed = prior131.installed_value(program["target"], events, base_case["context"])
            local = prior131.reference_value(program["target"], events, base_case["context"])
            rows.append({
                "case_id": f"{base_case['base_id']}-{variant}",
                "variant": variant,
                "installed_output": installed,
                "reference_output": local,
                "base_reference_output": reference,
                "distinguishes": installed != local,
                "reference_invariant": local == reference,
                "foreign_insertion_count": 2,
            })
    adversarial = [row for row in rows if row["variant"] != "joint-control"]
    controls = [row for row in rows if row["variant"] == "joint-control"]
    passed = bool(len(adversarial) == 6 and len(controls) == 3 and all(row["distinguishes"] and row["reference_invariant"] for row in adversarial) and all(not row["distinguishes"] and row["reference_invariant"] for row in controls))
    return {
        "target": program["target"],
        "capability_id": capability["capability_id"],
        "program_digest": capability["program_digest"],
        "composition_version": COMPOSITION_VERSION,
        "cases": rows,
        "adversarial_count": len(adversarial),
        "confirmation_count": len(controls),
        "passed": passed,
        "bases_digest": p82.digest(bases),
    }


def open_world(p82, run: Path, binding: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    evaluation = evaluate_joint_program(p82, capability, JOINT_BASES)
    body = {
        "authority": "ot-0135-sealed-joint-program-world",
        "reuse_binding_digest": binding["binding_digest"],
        "selected_contact_id": "reuse-" + capability["capability_id"] + "-joint",
        "selected_branch": evaluation,
        "expected_route": "extend" if evaluation["passed"] else "surrender",
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    (run / "selected-world-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def route_seed(root: Path, subject: dict[str, Any], selector: str, binding: dict[str, Any], capability: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "route-seed"
    seed.mkdir()
    actor_receipt = {key: value for key, value in world.items() if key != "expected_route"}
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(subject), indent=2, sort_keys=True) + "\n")
    (seed / "retained-contact-program.json").write_text(json.dumps(capability, indent=2, sort_keys=True) + "\n")
    (seed / "bound-selected-contact.json").write_text(json.dumps({"binding": binding, "selected_contact": capability}, indent=2, sort_keys=True) + "\n")
    (seed / "selected-world-consequence.json").write_text(json.dumps(actor_receipt, indent=2, sort_keys=True) + "\n")
    (seed / "selector.py").write_text(selector)
    (seed / "route-assimilation.json").write_text(json.dumps(prior133.prior22.route_template(), indent=2, sort_keys=True) + "\n")
    (seed / "route-only-compiler-contract.json").write_text(json.dumps({
        "compiler_version": base130.COMPILER_VERSION,
        "actor_authored_file": "route-assimilation.json",
        "required_exact_case_ids": sorted(row["case_id"] for row in world["selected_branch"]["cases"]),
        "route_exact": "extend",
        "compiled_action_target": "continuation-6-<sha256(remaining_uncertainty)[0:12]>",
        "compiled_action_expected_information": "exact remaining_uncertainty",
        "selector_and_contact_program_are_immutable": True,
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({
        "editable": ["route-assimilation.json"],
        "immutable": ["selector.py", "retained-contact-program.json", "subject-position.json", "bound-selected-contact.json", "selected-world-consequence.json", "route-only-compiler-contract.json"],
    }, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Assimilate the exact consequence generated by the retained contact program. Cite all nine cases, preserve selector.py and retained-contact-program.json, advance the uncertainty, edit only route-assimilation.json, inspect the diff, and report truthfully.\n")
    return seed


def run_route_actor(context, p82, prior89, root: Path, subject: dict[str, Any], selector: str, binding: dict[str, Any], capability: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "consequence-route"
    seed = route_seed(root, subject, selector, binding, capability, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, prior133.ROUTE_SCHEMA, "Assimilate the exact retained-program consequence under the route-only compiler. Cite every case, preserve selector and program bytes, advance the uncertainty, edit one file, inspect the diff, and report truthfully.")
    try:
        route = json.loads((workspace / "route-assimilation.json").read_text())
        selector_retained = (workspace / "selector.py").read_text() == selector
        program_retained = json.loads((workspace / "retained-contact-program.json").read_text()) == capability
    except (OSError, json.JSONDecodeError):
        route = None
        selector_retained = program_retained = False
    expected_ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    checks = {
        "route_exact": bool(route and route.get("route") == world["expected_route"] == "extend"),
        "contact_id_exact": bool(route and route.get("selected_contact_id") == world["selected_contact_id"]),
        "case_ids_exact": bool(route and set(route.get("settled_case_ids", [])) == expected_ids),
        "selector_retained": selector_retained,
        "contact_program_retained": program_retained,
        "remaining_uncertainty_new": bool(route and prior131.valid_text(route.get("remaining_uncertainty")) and len(route["remaining_uncertainty"].strip()) >= 24 and route["remaining_uncertainty"].strip() != subject["continuation"]["next_opening"].strip()),
    }
    checks["passed"] = all(checks.values())
    valid = bool(prior133.prior22.valid_route(route) and checks["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["route-assimilation.json"])
    routed = None
    compiler = {"passed": False}
    if valid and prior131.audit_accepted(audit):
        actor_body = {"authority": "ot-0135-grounded-retained-program-route", "source_subject_digest": subject["artifact_digest"], "selection_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "actor_checks": checks, "selector_retention_derived": selector_retained, "contact_program_retention_derived": program_retained, "route_assimilation": route}
        actor_binding = {**actor_body, "binding_digest": p82.digest(actor_body)}
        action = base130.compile_action(route, 6)
        opening = base130.previous.compile_opening(route, action)
        compiler = {
            "action_valid": prior133.prior18.previous.previous.repaired_action_valid(action, subject),
            "target_new": action["action_target"] not in prior133.prior22.kernel.registered(subject),
            "expected_information_exact": action["expected_information"] == route["remaining_uncertainty"],
            "opening_structurally_valid": prior89.valid_successor(opening),
            "uncertainty_retained_exactly": opening["unresolved"] == route["remaining_uncertainty"] and route["remaining_uncertainty"] in opening["next_opening"],
            "compiler_deterministic": action == base130.compile_action(route, 6) and opening == base130.previous.compile_opening(route, action),
        }
        compiler["passed"] = all(compiler.values())
        if compiler["passed"]:
            body = {"authority": "ot-0135-retained-program-compiled-continuation", "source_subject_digest": subject["artifact_digest"], "selection_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_binding_digest": actor_binding["binding_digest"], "compiler_version": base130.COMPILER_VERSION, "compiler_checks": compiler, "selector_retention_derived": selector_retained, "contact_program_retention_derived": program_retained, "route_assimilation": route, "successor_opening": opening, "continuation_action": action}
            routed = {**body, "binding_digest": p82.digest(body)}
            for name, value in (("bound-route.json", actor_binding), ("compiled-continuation-action.json", action), ("compiled-successor-opening.json", opening), ("bound-compiled-route.json", routed)):
                (context.evidence(label) / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "actor_checks": checks, "compiler_checks": compiler, "binding": routed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0135").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_json_artifact(p82, repo, store, "OT-0134", "open-subject-after-transferable-contact-program.json")
    aggregate = load_json_artifact(p82, repo, store, "OT-0134", "exact-transferable-contact-program-aggregate.json")
    capability = capability_from_aggregate(p82, aggregate)
    enriched, retention_receipt = enrich_subject(p82, parent, capability)
    fixture = evaluate_joint_program(p82, capability, JOINT_BASES)
    erased = copy.deepcopy(enriched)
    erased.pop("artifact_digest", None)
    erased["contact_program_capabilities"][-1].pop("program", None)
    erased = p82.seal(erased)
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
        "source_aggregate_passed": aggregate["transferable_contact_program_passed"] and aggregate["final_subject_digest"] == parent["artifact_digest"],
        "parent_lacks_program_capability": not parent.get("contact_program_capabilities"),
        "capability_exact_valid": capability_valid(p82, capability),
        "enriched_exact_sounding_open": runtime.identity_conforms(enriched) and enriched["continuation"]["status"] == "open" and enriched["contact_program_capabilities"][-1] == capability,
        "active_scheduler_binds": bind_reuse(p82, enriched) is not None,
        "byte_erased_scheduler_stops": bind_reuse(p82, erased) is None,
        "joint_fixture_passes": fixture["passed"] and len(fixture["cases"]) == 9,
        "route_schema_present": prior133.ROUTE_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "checks": checks, "retention_receipt": retention_receipt, "joint_fixture": fixture}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0135 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps({"checks": checks, "retention_receipt": retention_receipt, "joint_fixture_commitment": p82.digest(fixture)}, indent=2, sort_keys=True) + "\n")
    (run / "retained-program-subject.json").write_text(json.dumps(enriched, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("pre-contact conformance failed")
    started = time.time()
    binding = bind_reuse(p82, enriched, run)
    world = open_world(p82, run, binding, capability)
    current = enriched
    routed = None
    promotion = None
    operational = False
    if world["selected_branch"]["passed"]:
        context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
        route_root = run / "consequence"
        route_root.mkdir()
        selector = enriched["allocation_machinery"][-1]["source"]
        routed = run_route_actor(context, p82, prior89, route_root, enriched, selector, binding, capability, world)
        if routed["binding"]:
            current, promotion = prior133.prior22.promote(p82, enriched, binding, world, routed["binding"])
        operational = bool(promotion and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and current["contact_program_capabilities"][-1] == capability)
    control_binding = bind_reuse(p82, erased) if operational else None
    retention_causal = bool(operational and control_binding is None and binding is not None)
    result = {
        "authority": "ot-0135-retained-contact-program-reuse-driver",
        "source_subject_digest": parent["artifact_digest"],
        "retained_program_subject_digest": enriched["artifact_digest"],
        "retention_receipt": retention_receipt,
        "reuse_binding": binding,
        "hidden_world": world,
        "consequence_route": p82.compact(routed) if routed else None,
        "promotion": promotion,
        "byte_erased_control_binding": control_binding,
        "retained_program_reuse_passed": operational,
        "program_byte_retention_causal_passed": retention_causal,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "fresh_actor_count": 1 if routed else 0,
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational and retention_causal else 2


if __name__ == "__main__":
    raise SystemExit(main())
