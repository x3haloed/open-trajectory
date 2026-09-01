from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0130_route_only_recurrent_subject.py"
BASE_SHA256 = "1ed3da9c08b6a7cef1509356a6b8abb7891d5c0c9631bd0e589e6f662a75e147"
PARENT_DIGEST = "34c8ce6ded8640e0394578804d6badc08a2fe69b51a852c8fe8bec4624b565f3"
CONTACT_SCHEMA = REPO / "spec/ot-0131-contact.schema.json"
ROUTE_SCHEMA = REPO / "spec/ot-0130-route-only.schema.json"
PLACEHOLDER = "__REPLACE__"
ACTIVE_TARGET = "reserve_for_context"
CONTROL_TARGET = "recovery_window"
CONTROL_OPENING = "Whether recovery latency responds to a regime shift remains unresolved."
TARGETS = {ACTIVE_TARGET, CONTROL_TARGET}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0130 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0131_frozen_ot0130", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base130 = load_base()
prior22 = base130.prior22
prior18 = base130.prior18
base = base130.base


POLICY_SOURCE = '''def reserve_for_context(events, context):
    """Return observed demand spread used as reserve for one context."""
    demands = [event["demand"] for event in events]
    return max(demands) - min(demands)


def recovery_window(events, context):
    """Return observations after peak until demand returns to the initial level."""
    demands = [event["demand"] for event in events]
    peak = max(range(len(demands)), key=lambda index: demands[index])
    baseline = demands[0]
    for index in range(peak + 1, len(demands)):
        if demands[index] <= baseline:
            return index - peak
    return len(demands) - 1 - peak
'''

PUBLIC_CASES_SOURCE = '''CASES = [
    {
        "case_id": "steady-single-context",
        "context": "north",
        "events": [
            {"context": "north", "demand": 4},
            {"context": "north", "demand": 9},
            {"context": "north", "demand": 4}
        ]
    },
    {
        "case_id": "slow-single-context-recovery",
        "context": "south",
        "events": [
            {"context": "south", "demand": 3},
            {"context": "south", "demand": 12},
            {"context": "south", "demand": 8},
            {"context": "south", "demand": 3}
        ]
    }
]
'''

OBSERVE_SOURCE = '''import json
from capacity.policy import recovery_window, reserve_for_context
from capacity.public_cases import CASES

for case in CASES:
    print(json.dumps({
        "case_id": case["case_id"],
        "context": case["context"],
        "reserve": reserve_for_context(case["events"], case["context"]),
        "recovery_window": recovery_window(case["events"], case["context"]),
    }, sort_keys=True))
'''

WORLD_README = '''# Capacity policy observation

This complete policy is already valid on its declared single-context public
examples. Run `python3 observe.py`, inspect the source, and use the inherited
subject position to formulate the next useful world contact.

Edit only `contact-proposal.json`. Author exactly three mixed-context cases for
one real policy function: at least two adversarial interleavings and one
same-behavior control. Do not edit policy code or claim hidden outcomes.
'''


def proposal_template() -> dict[str, Any]:
    event = {"context": PLACEHOLDER, "demand": 0}
    case = {"case_id": PLACEHOLDER, "context": PLACEHOLDER, "events": [copy.deepcopy(event) for _ in range(5)]}
    return {
        "question": PLACEHOLDER,
        "rationale": PLACEHOLDER,
        "target": PLACEHOLDER,
        "cases": [copy.deepcopy(case) for _ in range(3)],
        "surrender_condition": PLACEHOLDER,
    }


def proposal_contract() -> dict[str, Any]:
    return {
        "exact_top_level_keys": ["cases", "question", "rationale", "surrender_condition", "target"],
        "target": "exactly one function actually present in capacity/policy.py",
        "case_count": 3,
        "case_exact_keys": ["case_id", "context", "events"],
        "case_id": "unique lowercase hyphenated identifier",
        "event_exact_keys": ["context", "demand"],
        "event_count": "5 through 10",
        "context": "lowercase identifier; requested context occurs at least three times and another context occurs at least twice",
        "demand": "integer from 0 through 30; booleans are invalid",
        "design": "at least two intended adversarial interleavings and one intended same-behavior control",
        "instruction": "Replace every placeholder, choose one real function from source, and bind cases before unseen reference outcomes.",
    }


def valid_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and PLACEHOLDER not in value


def valid_proposal(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"question", "rationale", "target", "cases", "surrender_condition"}:
        return False
    if value.get("target") not in TARGETS or not all(valid_text(value.get(key)) for key in ("question", "rationale", "surrender_condition")):
        return False
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        return False
    ids = []
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"case_id", "context", "events"}:
            return False
        case_id, context, events = case["case_id"], case["context"], case["events"]
        if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case_id):
            return False
        if not isinstance(context, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", context):
            return False
        if not isinstance(events, list) or not 5 <= len(events) <= 10:
            return False
        contexts = []
        for event in events:
            if not isinstance(event, dict) or set(event) != {"context", "demand"}:
                return False
            if not isinstance(event["context"], str) or not re.fullmatch(r"[a-z][a-z0-9-]*", event["context"]):
                return False
            demand = event["demand"]
            if isinstance(demand, bool) or not isinstance(demand, int) or not 0 <= demand <= 30:
                return False
            contexts.append(event["context"])
        if contexts.count(context) < 3 or len(contexts) - contexts.count(context) < 2:
            return False
        ids.append(case_id)
    return len(set(ids)) == 3


def installed_value(target: str, events: list[dict[str, Any]], context: str) -> int:
    demands = [event["demand"] for event in events]
    if target == ACTIVE_TARGET:
        return max(demands) - min(demands)
    peak = max(range(len(demands)), key=lambda index: demands[index])
    baseline = demands[0]
    for index in range(peak + 1, len(demands)):
        if demands[index] <= baseline:
            return index - peak
    return len(demands) - 1 - peak


def reference_value(target: str, events: list[dict[str, Any]], context: str) -> int:
    local = [event for event in events if event["context"] == context]
    return installed_value(target, local, context)


def evaluate_proposal(p82, proposal: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for case in proposal["cases"]:
        installed = installed_value(proposal["target"], case["events"], case["context"])
        reference = reference_value(proposal["target"], case["events"], case["context"])
        rows.append({
            "case_id": case["case_id"],
            "installed_output": installed,
            "reference_output": reference,
            "distinguishes": installed != reference,
        })
    mismatch_count = sum(row["distinguishes"] for row in rows)
    confirmation_count = len(rows) - mismatch_count
    decisive = mismatch_count >= 2 and confirmation_count >= 1
    return {
        "target": proposal["target"],
        "cases": rows,
        "mismatch_count": mismatch_count,
        "confirmation_count": confirmation_count,
        "decisive": decisive,
        "case_digest": p82.digest(proposal["cases"]),
    }


REPRESENTATIVE_ACTIVE = {
    "question": "Does mixed context history inflate context-local demand volatility?",
    "rationale": "Contrast context-local stability with unrelated volatility and retain a matched control.",
    "target": ACTIVE_TARGET,
    "cases": [
        {"case_id": "north-stable-south-volatile", "context": "north", "events": [
            {"context": "north", "demand": 5}, {"context": "south", "demand": 1},
            {"context": "north", "demand": 5}, {"context": "south", "demand": 15},
            {"context": "north", "demand": 5}]},
        {"case_id": "south-stable-north-volatile", "context": "south", "events": [
            {"context": "south", "demand": 10}, {"context": "north", "demand": 0},
            {"context": "south", "demand": 10}, {"context": "north", "demand": 20},
            {"context": "south", "demand": 10}]},
        {"case_id": "matched-context-range-control", "context": "north", "events": [
            {"context": "north", "demand": 2}, {"context": "south", "demand": 2},
            {"context": "north", "demand": 8}, {"context": "south", "demand": 8},
            {"context": "north", "demand": 2}]},
    ],
    "surrender_condition": "Surrender if mixed histories never differ from context-local reference behavior.",
}

REPRESENTATIVE_CONTROL = {
    "question": "Does unrelated context activity distort context-local recovery latency?",
    "rationale": "Interleave a later unrelated peak around local recovery and retain one aligned control.",
    "target": CONTROL_TARGET,
    "cases": [
        {"case_id": "north-recovery-late-south-peak", "context": "north", "events": [
            {"context": "north", "demand": 4}, {"context": "north", "demand": 12},
            {"context": "south", "demand": 20}, {"context": "south", "demand": 18},
            {"context": "north", "demand": 4}]},
        {"case_id": "south-recovery-early-north-floor", "context": "south", "events": [
            {"context": "south", "demand": 3}, {"context": "north", "demand": 1},
            {"context": "south", "demand": 14}, {"context": "north", "demand": 20},
            {"context": "south", "demand": 3}]},
        {"case_id": "matched-recovery-control", "context": "north", "events": [
            {"context": "north", "demand": 3}, {"context": "south", "demand": 3},
            {"context": "north", "demand": 12}, {"context": "south", "demand": 12},
            {"context": "north", "demand": 3}, {"context": "south", "demand": 3}]},
    ],
    "surrender_condition": "Surrender if mixed histories never differ from context-local recovery reference behavior.",
}


def write_contact_seed(root: Path, position: dict[str, Any]) -> Path:
    seed = root / "contact-seed"
    (seed / "capacity").mkdir(parents=True)
    (seed / "capacity/__init__.py").write_text("")
    (seed / "capacity/policy.py").write_text(POLICY_SOURCE)
    (seed / "capacity/public_cases.py").write_text(PUBLIC_CASES_SOURCE)
    (seed / "observe.py").write_text(OBSERVE_SOURCE)
    (seed / "README.md").write_text(WORLD_README)
    (seed / "subject-position.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "contact-contract.json").write_text(json.dumps(proposal_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "contact-proposal.json").write_text(json.dumps(proposal_template(), indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({
        "editable": ["contact-proposal.json"],
        "immutable": ["capacity/policy.py", "capacity/public_cases.py", "observe.py", "README.md", "subject-position.json", "contact-contract.json"],
    }, indent=2, sort_keys=True) + "\n")
    return seed


def audit_accepted(audit: dict[str, Any]) -> bool:
    denial = audit["denial_classification_v2"]
    return bool(
        audit["conformant"]
        and audit["trace_regime"]["accepted"]
        and denial["accepted"]
        and not denial["protected_path_named"]
        and not denial["outside_file_changes"]
    )


def run_contact_actor(context, p82, root: Path, label: str, position: dict[str, Any]) -> dict[str, Any]:
    seed = write_contact_seed(root, position)
    prompt = (
        "Continue from the inherited subject position. Inspect and run the complete capacity repository, then author one decisive three-case world contact in contact-proposal.json. "
        "Choose the real function that best follows the inherited opening, include two adversarial mixed-context interleavings and one same-behavior control, edit no other file, inspect the diff, and report truthfully."
    )
    output, base_audit, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, prompt)
    try:
        proposal = json.loads((workspace / "contact-proposal.json").read_text())
    except (OSError, json.JSONDecodeError):
        proposal = None
    valid = valid_proposal(proposal)
    audit = context.audit_actor(label, output, base_audit, valid, ["contact-proposal.json"])
    binding = None
    if valid and audit_accepted(audit):
        body = {
            "authority": "ot-0131-actor-originated-contact-binding",
            "source_subject_digest": position.get("artifact_digest", PARENT_DIGEST),
            "opening": position["continuation"]["next_opening"],
            "actor_patch_digest": audit["patch_digest"],
            "proposal": proposal,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-contact-proposal.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "proposal_valid": valid, "binding": binding}


def open_world(p82, root: Path, binding: dict[str, Any]) -> dict[str, Any]:
    evaluation = evaluate_proposal(p82, binding["proposal"])
    contact_id = "originated-" + hashlib.sha256(json.dumps(binding["proposal"], sort_keys=True).encode()).hexdigest()[:16]
    body = {
        "authority": "ot-0131-independent-context-local-world",
        "contact_binding_digest": binding["binding_digest"],
        "selected_contact_id": contact_id,
        "selected_branch": evaluation,
        "expected_route": "extend" if evaluation["decisive"] else "surrender",
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    (root / "selected-world-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def route_seed(root: Path, parent: dict[str, Any], selector: str, binding: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "route-seed"
    seed.mkdir()
    actor_receipt = {key: value for key, value in world.items() if key != "expected_route"}
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(parent), indent=2, sort_keys=True) + "\n")
    (seed / "bound-selected-contact.json").write_text(json.dumps({"binding": binding, "selected_contact": binding["proposal"]}, indent=2, sort_keys=True) + "\n")
    (seed / "selected-world-consequence.json").write_text(json.dumps(actor_receipt, indent=2, sort_keys=True) + "\n")
    (seed / "selector.py").write_text(selector)
    (seed / "route-assimilation.json").write_text(json.dumps(prior22.route_template(), indent=2, sort_keys=True) + "\n")
    (seed / "route-only-compiler-contract.json").write_text(json.dumps({
        "compiler_version": base130.COMPILER_VERSION,
        "actor_authored_file": "route-assimilation.json",
        "required_exact_case_ids": sorted(row["case_id"] for row in world["selected_branch"]["cases"]),
        "route_exact": "extend",
        "compiled_action_target": "continuation-4-<sha256(remaining_uncertainty)[0:12]>",
        "compiled_action_expected_information": "exact remaining_uncertainty",
        "compiled_opening": "ot-0129-v1 projection of route and compiled action",
        "selector_is_immutable": True,
        "remaining_uncertainty": "must be substantive and may not repeat the inherited opening verbatim",
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({
        "editable": ["route-assimilation.json"],
        "immutable": ["selector.py", "subject-position.json", "bound-selected-contact.json", "selected-world-consequence.json", "route-only-compiler-contract.json"],
    }, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Assimilate the exact selected consequence once. Cite all exact cases, advance rather than repeat the settled opening, preserve selector.py, edit only route-assimilation.json, inspect the diff, and report truthfully.\n")
    return seed


def run_route_actor(context, p82, root: Path, parent: dict[str, Any], selector: str, contact_binding: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "consequence-route"
    seed = route_seed(root, parent, selector, contact_binding, world)
    output, base_audit, workspace, _ = context.run_actor(
        label,
        seed,
        ROUTE_SCHEMA,
        "Assimilate the exact originated contact consequence once under the route-only compiler contract. Cite every exact case, preserve the selector, advance the remaining uncertainty, inspect the one-file diff, and report truthfully.",
    )
    try:
        route = json.loads((workspace / "route-assimilation.json").read_text())
        retained = (workspace / "selector.py").read_text() == selector
    except (OSError, json.JSONDecodeError):
        route = None
        retained = False
    expected_ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    cited = set(route.get("settled_case_ids", [])) if isinstance(route, dict) else set()
    actor_checks = {
        "route_exact": bool(route and route.get("route") == world["expected_route"] == "extend"),
        "contact_id_exact": bool(route and route.get("selected_contact_id") == world["selected_contact_id"]),
        "case_ids_exact": cited == expected_ids,
        "selector_retained": retained,
        "remaining_uncertainty_new": bool(route and valid_text(route.get("remaining_uncertainty")) and len(route["remaining_uncertainty"].strip()) >= 24 and route["remaining_uncertainty"].strip() != parent["continuation"]["next_opening"].strip()),
    }
    actor_checks["passed"] = all(actor_checks.values())
    valid = bool(prior22.valid_route(route) and actor_checks["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["route-assimilation.json"])
    routed = None
    action = None
    opening = None
    compiler_checks = {"passed": False}
    if valid and audit_accepted(audit):
        actor_body = {
            "authority": "ot-0131-grounded-route",
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": contact_binding["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "actor_checks": actor_checks,
            "selector_retention_derived": retained,
            "route_assimilation": route,
        }
        actor_binding = {**actor_body, "binding_digest": p82.digest(actor_body)}
        action = base130.compile_action(route, 4)
        opening = base130.previous.compile_opening(route, action)
        compiler_checks = {
            "action_valid": prior18.previous.previous.repaired_action_valid(action, parent),
            "target_new": action["action_target"] not in prior22.kernel.registered(parent),
            "expected_information_exact": action["expected_information"] == route["remaining_uncertainty"],
            "opening_structurally_valid": base130.previous.prior89.valid_successor(opening),
            "uncertainty_retained_exactly": opening["unresolved"] == route["remaining_uncertainty"] and route["remaining_uncertainty"] in opening["next_opening"] and route["remaining_uncertainty"] in opening["continuation_after_contact"],
            "compiler_deterministic": action == base130.compile_action(route, 4) and opening == base130.previous.compile_opening(route, action),
        }
        compiler_checks["passed"] = all(compiler_checks.values())
        (context.evidence(label) / "bound-route.json").write_text(json.dumps(actor_binding, indent=2, sort_keys=True) + "\n")
        (context.evidence(label) / "compiled-continuation-action.json").write_text(json.dumps(action, indent=2, sort_keys=True) + "\n")
        (context.evidence(label) / "compiled-successor-opening.json").write_text(json.dumps(opening, indent=2, sort_keys=True) + "\n")
        if compiler_checks["passed"]:
            body = {
                "authority": "ot-0131-route-only-compiled-continuation",
                "source_subject_digest": parent["artifact_digest"],
                "selection_binding_digest": contact_binding["binding_digest"],
                "world_receipt_digest": world["receipt_digest"],
                "actor_binding_digest": actor_binding["binding_digest"],
                "compiler_version": base130.COMPILER_VERSION,
                "compiler_checks": compiler_checks,
                "selector_retention_derived": retained,
                "route_assimilation": route,
                "successor_opening": opening,
                "continuation_action": action,
            }
            routed = {**body, "binding_digest": p82.digest(body)}
            (context.evidence(label) / "bound-compiled-route.json").write_text(json.dumps(routed, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "actor_checks": actor_checks, "compiler_checks": compiler_checks, "compiled_action": action, "compiled_opening": opening, "binding": routed}


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = p82.materialize(repo, store, "OT-0130", "open-route-only-recurrent-subject.json")
    return json.loads(path.read_text())


def control_position(parent: dict[str, Any]) -> dict[str, Any]:
    position = base.active_position(parent)
    position["continuation"]["next_opening"] = CONTROL_OPENING
    position["active_pursuit"]["next_pursuit"] = CONTROL_OPENING
    position["unresolved"] = CONTROL_OPENING
    return position


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0131").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    selector = parent["allocation_machinery"][-1]["source"]
    active_fixture = evaluate_proposal(p82, REPRESENTATIVE_ACTIVE)
    control_fixture = evaluate_proposal(p82, REPRESENTATIVE_CONTROL)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        seed = write_contact_seed(root, base.active_position(parent))
        seed_files = sorted(str(path.relative_to(seed)) for path in seed.rglob("*") if path.is_file())
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
        "parent_opening_contextual_transfer": "demand-volatility" in parent["continuation"]["next_opening"] and "contexts" in parent["continuation"]["next_opening"],
        "contact_schema_present": CONTACT_SCHEMA.is_file(),
        "route_schema_present": ROUTE_SCHEMA.is_file(),
        "policy_source_compiles": bool(compile(POLICY_SOURCE, "capacity/policy.py", "exec")),
        "representative_active_valid_decisive": valid_proposal(REPRESENTATIVE_ACTIVE) and active_fixture["decisive"] and active_fixture["target"] == ACTIVE_TARGET,
        "representative_control_valid_decisive": valid_proposal(REPRESENTATIVE_CONTROL) and control_fixture["decisive"] and control_fixture["target"] == CONTROL_TARGET,
        "contact_seed_complete": seed_files == ["README.md", "capacity/__init__.py", "capacity/policy.py", "capacity/public_cases.py", "contact-contract.json", "contact-proposal.json", "mutation-envelope.json", "observe.py", "subject-position.json"],
        "fixed_compiler_available": base130.COMPILER_VERSION == "ot-0130-v1",
    }
    checks["passed"] = all(checks.values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "checks": checks, "active_fixture": active_fixture, "control_fixture": control_fixture}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0131 evidence")
    run.mkdir(parents=True)
    commitment = {
        "authority": "ot-0131-sealed-world-commitment",
        "reference_semantics_digest": p82.digest({"reserve": "context-local demand range", "recovery": "context-local post-peak return to initial demand"}),
        "decisive_rule": {"minimum_distinguishing_cases": 2, "minimum_confirmation_cases": 1},
    }
    commitment["commitment_digest"] = p82.digest(commitment)
    (run / "fixture-conformance.json").write_text(json.dumps({"checks": checks, "active_fixture": active_fixture, "control_fixture": control_fixture}, indent=2, sort_keys=True) + "\n")
    (run / "sealed-world-commitment.json").write_text(json.dumps(commitment, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    active_root = run / "active-contact"
    active_root.mkdir()
    active = run_contact_actor(context, p82, active_root, "active-contact-author", base.active_position(parent))
    world = open_world(p82, active_root, active["binding"]) if active["binding"] else None
    active_aligned_decisive = bool(world and world["selected_branch"]["decisive"] and world["selected_branch"]["target"] == ACTIVE_TARGET)
    current = parent
    routed = None
    promotion = None
    operational = False
    control = None
    control_world = None
    if active_aligned_decisive:
        route_root = run / "consequence"
        route_root.mkdir()
        routed = run_route_actor(context, p82, route_root, parent, selector, active["binding"], world)
        if routed["binding"]:
            current, promotion = prior22.promote(p82, parent, active["binding"], world, routed["binding"])
        operational = bool(
            promotion
            and runtime.identity_conforms(current)
            and current["continuation"]["status"] == "open"
            and current["artifact_digest"] != parent["artifact_digest"]
        )
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control_root = run / "control-contact"
        control_root.mkdir()
        control = run_contact_actor(context, p82, control_root, "control-contact-author", control_position(parent))
        control_world = open_world(p82, control_root, control["binding"]) if control["binding"] else None
    pursuit_conditioned = bool(
        operational
        and world["selected_branch"]["decisive"]
        and world["selected_branch"]["target"] == ACTIVE_TARGET
        and control_world
        and control_world["selected_branch"]["decisive"]
        and control_world["selected_branch"]["target"] == CONTROL_TARGET
    )
    result = {
        "authority": "ot-0131-subject-originated-contact-driver",
        "source_subject_digest": parent["artifact_digest"],
        "active_contact": p82.compact(active),
        "active_world": world,
        "consequence_route": p82.compact(routed) if routed else None,
        "promotion": promotion,
        "control_contact": p82.compact(control) if control else None,
        "control_world": control_world,
        "operational_transition_passed": operational,
        "pursuit_conditioned_contact_passed": pursuit_conditioned,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "fresh_actor_count": int(active is not None) + int(routed is not None) + int(control is not None),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
