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
BASE_PATH = ROOT / "ot_0135_retained_contact_program_reuse.py"
BASE_SHA256 = "8ce995844d24e23edb9d2b94dcf03c040821da3cd2fb25a3d6c6f04844260057"
PARENT_DIGEST = "32c77eea52c662e9002172131d6e04c02978c151524b1deed942db9ae53f1402"
QUANTUM = 4


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0135 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0136_frozen_ot0135", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior135 = load_base()
prior133 = prior135.prior133
prior131 = prior135.prior131
base130 = prior135.base130
base134 = prior135.base134
base = prior135.base


PUBLIC_BASES = [
    {"base_id": "public-band-amber", "context": "amber", "insert_at": [1, 3], "demands": [12, 20, 16, 12]},
    {"base_id": "public-band-blue", "context": "blue", "insert_at": [2, 4], "demands": [14, 18, 26, 20, 14]},
]

QUANTIZED_BASES = [
    {"base_id": "sealed-band-cedar", "context": "cedar", "insert_at": [1, 3], "demands": [16, 24, 20, 16]},
    {"base_id": "sealed-band-dune", "context": "dune", "insert_at": [2, 4], "demands": [13, 19, 25, 17, 13]},
    {"base_id": "sealed-band-elm", "context": "elm", "insert_at": [1, 5], "demands": [15, 21, 31, 24, 19, 15]},
]

RAW_BASES = [
    {"base_id": "sealed-raw-fir", "context": "fir", "insert_at": [1, 3], "demands": [9, 16, 12, 9]},
    {"base_id": "sealed-raw-gold", "context": "gold", "insert_at": [2, 4], "demands": [11, 17, 21, 15, 11]},
]

REUSE_BASES = [
    {"base_id": "reuse-band-hazel", "context": "hazel", "insert_at": [2, 5], "demands": [18, 23, 30, 26, 21, 18]},
]


def quantized_value(events: list[dict[str, Any]], context: str, local: bool) -> int:
    selected = [event for event in events if not local or event["context"] == context]
    demands = [event["demand"] for event in selected]
    return (max(demands) - min(demands)) // QUANTUM


def evaluate_program(p82, program: dict[str, Any], bases: list[dict[str, Any]], regime: str) -> dict[str, Any]:
    rows = []
    for base_case in bases:
        local_events = prior135.local_events(base_case)
        if regime == "quantized":
            base_reference = quantized_value(local_events, base_case["context"], True)
        else:
            base_reference = prior131.reference_value(program["target"], local_events, base_case["context"])
        for variant, events in prior135.joint_variants(program, base_case).items():
            if regime == "quantized":
                installed = quantized_value(events, base_case["context"], False)
                reference = quantized_value(events, base_case["context"], True)
            else:
                installed = prior131.installed_value(program["target"], events, base_case["context"])
                reference = prior131.reference_value(program["target"], events, base_case["context"])
            rows.append({
                "case_id": f"{base_case['base_id']}-{variant}",
                "regime": regime,
                "variant": variant,
                "installed_output": installed,
                "reference_output": reference,
                "base_reference_output": base_reference,
                "distinguishes": installed != reference,
                "reference_invariant": reference == base_reference,
            })
    adversarial = [row for row in rows if row["variant"] != "joint-control"]
    controls = [row for row in rows if row["variant"] == "joint-control"]
    passed = bool(adversarial and controls and all(row["distinguishes"] and row["reference_invariant"] for row in adversarial) and all(not row["distinguishes"] and row["reference_invariant"] for row in controls))
    return {
        "regime": regime,
        "program_digest": p82.digest(program),
        "cases": rows,
        "adversarial_count": len(adversarial),
        "distinguishing_count": sum(row["distinguishes"] for row in adversarial),
        "confirmation_count": sum(not row["distinguishes"] for row in controls),
        "passed": passed,
        "bases_digest": p82.digest(bases),
    }


def failure_receipt(p82, subject: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    evaluation = evaluate_program(p82, capability["program"], QUANTIZED_BASES, "quantized")
    body = {
        "authority": "ot-0136-bound-retained-program-failure",
        "source_subject_digest": subject["artifact_digest"],
        "capability_id": capability["capability_id"],
        "capability_digest": capability["capability_digest"],
        "opening": subject["continuation"]["next_opening"],
        "regime": "quantized-reserve-band-4",
        "world_evaluation": evaluation,
        "expected_disposition": "correct",
    }
    return {**body, "receipt_digest": p82.digest(body)}


CHECKER_SOURCE = '''import json
from pathlib import Path

QUANTUM = 4
program = json.loads(Path("contact-program.json").read_text())
bases = json.loads(Path("public-bases.json").read_text())

def value(events, context, local):
    selected = [event for event in events if not local or event["context"] == context]
    demands = [event["demand"] for event in selected]
    return (max(demands) - min(demands)) // QUANTUM

rows = []
for base in bases:
    events = [{"context": base["context"], "demand": demand} for demand in base["demands"]]
    low, high = min(base["demands"]), max(base["demands"])
    midpoint = (low + high) // 2
    contexts = [program["foreign_context_prefix"] + "-a-" + base["context"], program["foreign_context_prefix"] + "-b-" + base["context"]]
    additions = {
        "joint-extremes": [{"context": contexts[0], "demand": high + program["high_offset"]}, {"context": contexts[1], "demand": low - program["low_offset"]}],
        "joint-high": [{"context": contexts[0], "demand": high + program["high_offset"]}, {"context": contexts[1], "demand": high + program["high_offset"]}],
        "joint-control": [{"context": contexts[0], "demand": midpoint}, {"context": contexts[1], "demand": midpoint}],
    }
    for variant, inserted in additions.items():
        changed = list(events)
        for position, event in sorted(zip(base["insert_at"], inserted), reverse=True):
            changed.insert(position, event)
        installed = value(changed, base["context"], False)
        reference = value(changed, base["context"], True)
        rows.append({"case_id": base["base_id"] + "-" + variant, "variant": variant, "installed": installed, "reference": reference, "distinguishes": installed != reference})
passed = all(row["distinguishes"] for row in rows if row["variant"] != "joint-control") and all(not row["distinguishes"] for row in rows if row["variant"] == "joint-control")
print(json.dumps({"passed": passed, "rows": rows}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def corrector_seed(root: Path, subject: dict[str, Any], capability: dict[str, Any], failure: dict[str, Any]) -> Path:
    seed = root / "corrector-seed"
    seed.mkdir()
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(subject), indent=2, sort_keys=True) + "\n")
    (seed / "retained-capability.json").write_text(json.dumps(capability, indent=2, sort_keys=True) + "\n")
    (seed / "failure-receipt.json").write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
    (seed / "contact-program.json").write_text(json.dumps(capability["program"], indent=2, sort_keys=True) + "\n")
    (seed / "public-bases.json").write_text(json.dumps(PUBLIC_BASES, indent=2, sort_keys=True) + "\n")
    (seed / "check_program.py").write_text(CHECKER_SOURCE)
    (seed / "correction-contract.json").write_text(json.dumps({
        "editable": "contact-program.json only",
        "mutable_fields": ["high_offset", "low_offset"],
        "immutable_fields": ["question", "rationale", "target", "foreign_context_prefix", "control_mode", "surrender_condition"],
        "offset_range": [1, 10],
        "public_command": "python3 check_program.py",
        "required_disposition": "repair the exact quantized failure while preserving the retained program's meaning",
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["contact-program.json"], "immutable": ["subject-position.json", "retained-capability.json", "failure-receipt.json", "public-bases.json", "check_program.py", "correction-contract.json"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Correct the retained contact program from the exact failure receipt. Change only high_offset and low_offset, run python3 check_program.py, inspect the exact one-file diff, and report truthfully.\n")
    return seed


def minimal_revision(parent: dict[str, Any], candidate: dict[str, Any]) -> bool:
    if not base134.corrected_valid_program(candidate):
        return False
    immutable = set(parent) - {"high_offset", "low_offset"}
    return all(candidate[key] == parent[key] for key in immutable) and (candidate["high_offset"], candidate["low_offset"]) != (parent["high_offset"], parent["low_offset"])


def run_corrector(context, p82, root: Path, subject: dict[str, Any], capability: dict[str, Any], failure: dict[str, Any]) -> dict[str, Any]:
    label = "program-corrector"
    seed = corrector_seed(root, subject, capability, failure)
    output, base_audit, workspace, _ = context.run_actor(label, seed, prior133.PROGRAM_SCHEMA, "Use the exact failure receipt to minimally correct the retained contact program. Change only its two offsets, run the declared checker, edit one file, inspect the diff, and report truthfully.")
    try:
        program = json.loads((workspace / "contact-program.json").read_text())
    except (OSError, json.JSONDecodeError):
        program = None
    public = evaluate_program(p82, program, PUBLIC_BASES, "quantized") if isinstance(program, dict) else None
    valid = bool(program and minimal_revision(capability["program"], program) and public and public["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["contact-program.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {
            "authority": "ot-0136-consequence-corrected-program-binding",
            "source_subject_digest": subject["artifact_digest"],
            "parent_capability_digest": capability["capability_digest"],
            "failure_receipt_digest": failure["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "public_receipt": public,
            "program": program,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-corrected-program.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "minimal_revision": bool(program and minimal_revision(capability["program"], program)), "public_check": public, "binding": binding}


def corrected_capability(p82, parent: dict[str, Any], failure: dict[str, Any], binding: dict[str, Any], quantized: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    program = binding["program"]
    program_digest = p82.digest(program)
    body = {
        "authority": "ot-0136-consequence-corrected-contact-program-capability",
        "capability_id": "contact-program-" + program_digest[:16],
        "program_digest": program_digest,
        "program": program,
        "target": program["target"],
        "parent_capability_digest": parent["capability_digest"],
        "failure_receipt_digest": failure["receipt_digest"],
        "correction_binding_digest": binding["binding_digest"],
        "quantized_world_receipt_digest": quantized["receipt_digest"],
        "raw_no_regression_receipt_digest": raw["receipt_digest"],
        "public_conformance_passed": binding["public_receipt"]["passed"],
        "hidden_conformance_passed": quantized["selected_branch"]["passed"] and raw["selected_branch"]["passed"],
        "composition_interface": prior135.COMPOSITION_VERSION,
    }
    return {**body, "capability_digest": p82.digest(body)}


def world_receipt(p82, authority: str, binding_digest: str, evaluation: dict[str, Any]) -> dict[str, Any]:
    body = {"authority": authority, "correction_binding_digest": binding_digest, "selected_branch": evaluation}
    return {**body, "receipt_digest": p82.digest(body)}


def corrected_subject(p82, parent: dict[str, Any], old: dict[str, Any], new: dict[str, Any], failure: dict[str, Any], binding: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["contact_program_capabilities"][-1] = new
    receipt_body = {
        "authority": "ot-0136-contact-program-correction",
        "source_subject_digest": parent["artifact_digest"],
        "parent_capability_digest": old["capability_digest"],
        "corrected_capability_digest": new["capability_digest"],
        "failure_receipt_digest": failure["receipt_digest"],
        "correction_binding_digest": binding["binding_digest"],
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child["contact_program_correction_receipts"] = [*child.get("contact_program_correction_receipts", []), receipt]
    return p82.seal(child), receipt


def combined_route_world(p82, corrected: dict[str, Any], quantized: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    cases = [*quantized["selected_branch"]["cases"], *raw["selected_branch"]["cases"]]
    selected = {
        "target": "reserve_for_context",
        "corrected_program_digest": corrected["program_digest"],
        "cases": cases,
        "quantized_passed": quantized["selected_branch"]["passed"],
        "raw_no_regression_passed": raw["selected_branch"]["passed"],
        "passed": quantized["selected_branch"]["passed"] and raw["selected_branch"]["passed"],
    }
    body = {"authority": "ot-0136-corrected-program-combined-world", "selected_contact_id": "corrected-" + corrected["capability_id"], "selected_branch": selected, "expected_route": "extend"}
    return {**body, "receipt_digest": p82.digest(body)}


def route_seed(root: Path, subject: dict[str, Any], selector: str, binding: dict[str, Any], capability: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "route-seed"
    seed.mkdir()
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(subject), indent=2, sort_keys=True) + "\n")
    (seed / "corrected-contact-program.json").write_text(json.dumps(capability, indent=2, sort_keys=True) + "\n")
    (seed / "bound-selected-contact.json").write_text(json.dumps({"binding": binding, "selected_contact": capability}, indent=2, sort_keys=True) + "\n")
    (seed / "selected-world-consequence.json").write_text(json.dumps({key: value for key, value in world.items() if key != "expected_route"}, indent=2, sort_keys=True) + "\n")
    (seed / "selector.py").write_text(selector)
    (seed / "route-assimilation.json").write_text(json.dumps(prior133.prior22.route_template(), indent=2, sort_keys=True) + "\n")
    (seed / "route-only-compiler-contract.json").write_text(json.dumps({"compiler_version": base130.COMPILER_VERSION, "actor_authored_file": "route-assimilation.json", "required_exact_case_ids": sorted(row["case_id"] for row in world["selected_branch"]["cases"]), "route_exact": "extend", "compiled_action_target": "continuation-7-<sha256(remaining_uncertainty)[0:12]>", "selector_and_corrected_program_are_immutable": True}, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["route-assimilation.json"], "immutable": ["selector.py", "corrected-contact-program.json", "subject-position.json", "bound-selected-contact.json", "selected-world-consequence.json", "route-only-compiler-contract.json"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Assimilate the exact corrected-program consequence. Cite every quantized and raw no-regression case, preserve selector and corrected program, edit only route-assimilation.json, inspect the diff, and report truthfully.\n")
    return seed


def run_route(context, p82, prior89, root: Path, subject: dict[str, Any], selector: str, binding: dict[str, Any], capability: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "consequence-route"
    seed = route_seed(root, subject, selector, binding, capability, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, prior133.ROUTE_SCHEMA, "Assimilate the corrected program's quantized and no-regression consequence. Cite every case, preserve selector and revised program, advance the uncertainty, edit one file, inspect the diff, and report truthfully.")
    try:
        route = json.loads((workspace / "route-assimilation.json").read_text())
        selector_ok = (workspace / "selector.py").read_text() == selector
        program_ok = json.loads((workspace / "corrected-contact-program.json").read_text()) == capability
    except (OSError, json.JSONDecodeError):
        route = None
        selector_ok = program_ok = False
    ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    checks = {
        "route_exact": bool(route and route.get("route") == "extend"),
        "contact_id_exact": bool(route and route.get("selected_contact_id") == world["selected_contact_id"]),
        "case_ids_exact": bool(route and set(route.get("settled_case_ids", [])) == ids),
        "selector_retained": selector_ok,
        "corrected_program_retained": program_ok,
        "remaining_uncertainty_new": bool(route and prior131.valid_text(route.get("remaining_uncertainty")) and route["remaining_uncertainty"].strip() != subject["continuation"]["next_opening"].strip()),
    }
    checks["passed"] = all(checks.values())
    valid = bool(prior133.prior22.valid_route(route) and checks["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["route-assimilation.json"])
    routed = None
    compiler = {"passed": False}
    if valid and prior131.audit_accepted(audit):
        actor_body = {"authority": "ot-0136-grounded-corrected-program-route", "source_subject_digest": subject["artifact_digest"], "selection_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "actor_checks": checks, "route_assimilation": route}
        actor_binding = {**actor_body, "binding_digest": p82.digest(actor_body)}
        action = base130.compile_action(route, 7)
        opening = base130.previous.compile_opening(route, action)
        compiler = {
            "action_valid": prior133.prior18.previous.previous.repaired_action_valid(action, subject),
            "target_new": action["action_target"] not in prior133.prior22.kernel.registered(subject),
            "expected_information_exact": action["expected_information"] == route["remaining_uncertainty"],
            "opening_structurally_valid": prior89.valid_successor(opening),
            "uncertainty_retained_exactly": opening["unresolved"] == route["remaining_uncertainty"] and route["remaining_uncertainty"] in opening["next_opening"],
            "compiler_deterministic": action == base130.compile_action(route, 7) and opening == base130.previous.compile_opening(route, action),
        }
        compiler["passed"] = all(compiler.values())
        if compiler["passed"]:
            body = {"authority": "ot-0136-corrected-program-compiled-continuation", "source_subject_digest": subject["artifact_digest"], "selection_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_binding_digest": actor_binding["binding_digest"], "compiler_version": base130.COMPILER_VERSION, "compiler_checks": compiler, "route_assimilation": route, "successor_opening": opening, "continuation_action": action}
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
    run = (args.evidence_root or store / "runs/OT-0136").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = prior135.load_json_artifact(p82, repo, store, "OT-0135", "open-subject-with-retained-contact-program.json")
    capability = parent["contact_program_capabilities"][-1]
    failure = failure_receipt(p82, parent, capability)
    representative = copy.deepcopy(capability["program"])
    representative["high_offset"] = representative["low_offset"] = 4
    negative = failure["world_evaluation"]
    corrected_quantized = evaluate_program(p82, representative, QUANTIZED_BASES, "quantized")
    corrected_raw = evaluate_program(p82, representative, RAW_BASES, "raw")
    later_reuse = evaluate_program(p82, representative, REUSE_BASES, "quantized")
    with tempfile.TemporaryDirectory() as directory:
        seed = corrector_seed(Path(directory), parent, capability, failure)
        files = sorted(path.name for path in seed.iterdir() if path.is_file())
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
        "retained_capability_exact": prior135.capability_valid(p82, capability) and capability["program"]["high_offset"] == capability["program"]["low_offset"] == 1,
        "negative_prediction_exact": not negative["passed"] and negative["distinguishing_count"] == 0 and negative["confirmation_count"] == 3,
        "representative_minimal_revision": minimal_revision(capability["program"], representative),
        "representative_quantized_passes": corrected_quantized["passed"] and corrected_quantized["distinguishing_count"] == 6,
        "representative_raw_no_regression": corrected_raw["passed"] and corrected_raw["distinguishing_count"] == 4,
        "representative_later_reuse": later_reuse["passed"] and later_reuse["distinguishing_count"] == 2,
        "corrector_seed_complete": files == ["README.md", "check_program.py", "contact-program.json", "correction-contract.json", "failure-receipt.json", "mutation-envelope.json", "public-bases.json", "retained-capability.json", "subject-position.json"],
        "schemas_present": prior133.PROGRAM_SCHEMA.is_file() and prior133.ROUTE_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "checks": checks, "negative_fixture": negative, "corrected_quantized_fixture": corrected_quantized, "raw_fixture": corrected_raw, "reuse_fixture": later_reuse}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0136 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps({"checks": checks, "negative_fixture_digest": p82.digest(negative), "corrected_fixture_digest": p82.digest(corrected_quantized), "raw_fixture_digest": p82.digest(corrected_raw), "reuse_fixture_digest": p82.digest(later_reuse)}, indent=2, sort_keys=True) + "\n")
    (run / "bound-failure-receipt.json").write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("pre-correction conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    correction_root = run / "correction"
    correction_root.mkdir()
    correction = run_corrector(context, p82, correction_root, parent, capability, failure)
    quant_receipt = raw_receipt = None
    revised_capability = None
    revised_subject = parent
    correction_receipt = None
    routed = None
    promotion = None
    operational = False
    reuse = None
    if correction["binding"]:
        quant_eval = evaluate_program(p82, correction["binding"]["program"], QUANTIZED_BASES, "quantized")
        raw_eval = evaluate_program(p82, correction["binding"]["program"], RAW_BASES, "raw")
        quant_receipt = world_receipt(p82, "ot-0136-sealed-quantized-correction-world", correction["binding"]["binding_digest"], quant_eval)
        raw_receipt = world_receipt(p82, "ot-0136-sealed-raw-no-regression-world", correction["binding"]["binding_digest"], raw_eval)
        (run / "quantized-correction-receipt.json").write_text(json.dumps(quant_receipt, indent=2, sort_keys=True) + "\n")
        (run / "raw-no-regression-receipt.json").write_text(json.dumps(raw_receipt, indent=2, sort_keys=True) + "\n")
        if quant_eval["passed"] and raw_eval["passed"] and not negative["passed"]:
            revised_capability = corrected_capability(p82, capability, failure, correction["binding"], quant_receipt, raw_receipt)
            revised_subject, correction_receipt = corrected_subject(p82, parent, capability, revised_capability, failure, correction["binding"])
            (run / "corrected-program-subject.json").write_text(json.dumps(revised_subject, indent=2, sort_keys=True) + "\n")
            route_world = combined_route_world(p82, revised_capability, quant_receipt, raw_receipt)
            route_root = run / "consequence"
            route_root.mkdir()
            selector = revised_subject["allocation_machinery"][-1]["source"]
            routed = run_route(context, p82, prior89, route_root, revised_subject, selector, correction["binding"], revised_capability, route_world)
            if routed["binding"]:
                revised_subject, promotion = prior133.prior22.promote(p82, revised_subject, correction["binding"], route_world, routed["binding"])
            operational = bool(promotion and runtime.identity_conforms(revised_subject) and revised_subject["continuation"]["status"] == "open" and revised_subject["contact_program_capabilities"][-1] == revised_capability)
            if operational:
                reuse = evaluate_program(p82, revised_capability["program"], REUSE_BASES, "quantized")
                (run / "post-seal-reuse-receipt.json").write_text(json.dumps(reuse, indent=2, sort_keys=True) + "\n")
    full_pass = bool(operational and reuse and reuse["passed"] and negative["distinguishing_count"] == 0 and quant_receipt["selected_branch"]["distinguishing_count"] == 6 and raw_receipt["selected_branch"]["passed"])
    current = revised_subject if operational else parent
    result = {
        "authority": "ot-0136-consequence-corrected-contact-program-driver",
        "source_subject_digest": parent["artifact_digest"],
        "failure_receipt": failure,
        "program_correction": p82.compact(correction),
        "quantized_correction_receipt": quant_receipt,
        "raw_no_regression_receipt": raw_receipt,
        "corrected_capability": revised_capability,
        "correction_receipt": correction_receipt,
        "consequence_route": p82.compact(routed) if routed else None,
        "promotion": promotion,
        "post_seal_reuse": reuse,
        "consequence_corrected_program_passed": full_pass,
        "observer_disposition": "promoted" if full_pass else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "fresh_actor_count": int(correction is not None) + int(routed is not None),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if full_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
