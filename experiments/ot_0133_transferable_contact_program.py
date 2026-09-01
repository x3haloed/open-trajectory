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
BASE_PATH = ROOT / "ot_0131_subject_originated_contact.py"
BASE_SHA256 = "08bf0057b454acb0f382420b7048696728d0f233c6d6dfc7784fbf5d75e59742"
PARENT_DIGEST = "172d512704c47e2ff1f54faf47889229110cd64cbede4ef1ddba7f364e604bb9"
PROGRAM_SCHEMA = REPO / "spec/ot-0133-program.schema.json"
ROUTE_SCHEMA = REPO / "spec/ot-0130-route-only.schema.json"
PLACEHOLDER = "__REPLACE__"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0131 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0133_frozen_ot0131", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base130 = prior.base130
prior22 = prior.prior22
prior18 = prior.prior18
base = prior.base


PUBLIC_BASES = [
    {"base_id": "public-north", "context": "north", "insert_at": 1, "demands": [4, 9, 4]},
    {"base_id": "public-south", "context": "south", "insert_at": 2, "demands": [8, 13, 10, 8]},
]

HIDDEN_BASES = [
    {"base_id": "hidden-copper", "context": "copper", "insert_at": 2, "demands": [12, 19, 15, 12]},
    {"base_id": "hidden-indigo", "context": "indigo", "insert_at": 1, "demands": [14, 22, 18, 16, 14]},
    {"base_id": "hidden-umber", "context": "umber", "insert_at": 3, "demands": [11, 17, 21, 15, 11]},
]


def program_template() -> dict[str, Any]:
    return {
        "question": PLACEHOLDER,
        "rationale": PLACEHOLDER,
        "target": PLACEHOLDER,
        "foreign_context_prefix": PLACEHOLDER,
        "high_offset": 0,
        "low_offset": 0,
        "control_mode": PLACEHOLDER,
        "surrender_condition": PLACEHOLDER,
    }


def program_contract() -> dict[str, Any]:
    return {
        "exact_keys": ["control_mode", "foreign_context_prefix", "high_offset", "low_offset", "question", "rationale", "surrender_condition", "target"],
        "target": "one function actually present in capacity/policy.py",
        "foreign_context_prefix": "lowercase identifier distinct from every requested context after suffixing",
        "high_offset": "integer 1 through 10 added above each base maximum",
        "low_offset": "integer 1 through 10 subtracted below each base minimum",
        "control_mode": "exactly midpoint",
        "public_command": "python3 check_program.py",
        "public_gate": "on both visible bases, high and low insertion change installed output while midpoint insertion does not",
        "instruction": "Replace every placeholder, use the inherited opening to choose a real target, run the public checker, and edit no other file.",
    }


def valid_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and PLACEHOLDER not in value


def valid_program(value: Any) -> bool:
    keys = {"question", "rationale", "target", "foreign_context_prefix", "high_offset", "low_offset", "control_mode", "surrender_condition"}
    if not isinstance(value, dict) or set(value) != keys:
        return False
    if value.get("target") not in prior.TARGETS or value.get("control_mode") != "midpoint":
        return False
    if not all(valid_text(value.get(key)) for key in ("question", "rationale", "surrender_condition")):
        return False
    prefix = value.get("foreign_context_prefix")
    if not isinstance(prefix, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", prefix):
        return False
    for key in ("high_offset", "low_offset"):
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= 10:
            return False
    return True


def base_events(base_case: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"context": base_case["context"], "demand": demand} for demand in base_case["demands"]]


def transformed(program: dict[str, Any], base_case: dict[str, Any], variant: str) -> list[dict[str, Any]]:
    events = base_events(base_case)
    low, high = min(base_case["demands"]), max(base_case["demands"])
    if variant == "high":
        demand = high + program["high_offset"]
    elif variant == "low":
        demand = low - program["low_offset"]
    else:
        demand = (low + high) // 2
    foreign = {"context": f"{program['foreign_context_prefix']}-{base_case['context']}", "demand": demand}
    return [*events[:base_case["insert_at"]], foreign, *events[base_case["insert_at"]:]]


def evaluate_program(p82, program: dict[str, Any], bases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for base_case in bases:
        original = base_events(base_case)
        reference = prior.reference_value(program["target"], original, base_case["context"])
        for variant in ("high", "low", "control"):
            events = transformed(program, base_case, variant)
            installed = prior.installed_value(program["target"], events, base_case["context"])
            local = prior.reference_value(program["target"], events, base_case["context"])
            rows.append({
                "case_id": f"{base_case['base_id']}-{variant}",
                "variant": variant,
                "installed_output": installed,
                "reference_output": local,
                "base_reference_output": reference,
                "distinguishes": installed != local,
                "reference_invariant": local == reference,
            })
    adversarial = [row for row in rows if row["variant"] in {"high", "low"}]
    controls = [row for row in rows if row["variant"] == "control"]
    passed = bool(adversarial and controls and all(row["distinguishes"] and row["reference_invariant"] for row in adversarial) and all(not row["distinguishes"] and row["reference_invariant"] for row in controls))
    return {
        "target": program["target"],
        "cases": rows,
        "adversarial_count": len(adversarial),
        "confirmation_count": len(controls),
        "passed": passed,
        "bases_digest": p82.digest(bases),
        "program_digest": p82.digest(program),
    }


REPRESENTATIVE_PROGRAM = {
    "question": "Does context-local reserve remain invariant to unrelated context extremes?",
    "rationale": "Generate high, low, and midpoint insertions around each local demand range.",
    "target": prior.ACTIVE_TARGET,
    "foreign_context_prefix": "foreign",
    "high_offset": 3,
    "low_offset": 2,
    "control_mode": "midpoint",
    "surrender_condition": "Surrender if unrelated extremes never change installed reserve output.",
}

CHECKER_SOURCE = '''import json
from pathlib import Path
from capacity.policy import recovery_window, reserve_for_context

program = json.loads(Path("contact-program.json").read_text())
bases = json.loads(Path("public-bases.json").read_text())
target = {"reserve_for_context": reserve_for_context, "recovery_window": recovery_window}[program["target"]]
rows = []
for base in bases:
    events = [{"context": base["context"], "demand": value} for value in base["demands"]]
    original = target(events, base["context"])
    low, high = min(base["demands"]), max(base["demands"])
    for variant, demand in (("high", high + program["high_offset"]), ("low", low - program["low_offset"]), ("control", (low + high) // 2)):
        foreign = {"context": program["foreign_context_prefix"] + "-" + base["context"], "demand": demand}
        changed = [*events[:base["insert_at"]], foreign, *events[base["insert_at"]:]]
        output = target(changed, base["context"])
        rows.append({"case_id": base["base_id"] + "-" + variant, "variant": variant, "base_output": original, "transformed_output": output, "changed": output != original})
passed = all(row["changed"] for row in rows if row["variant"] != "control") and all(not row["changed"] for row in rows if row["variant"] == "control")
print(json.dumps({"passed": passed, "rows": rows}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def write_program_seed(root: Path, position: dict[str, Any]) -> Path:
    seed = root / "program-seed"
    (seed / "capacity").mkdir(parents=True)
    (seed / "capacity/__init__.py").write_text("")
    (seed / "capacity/policy.py").write_text(prior.POLICY_SOURCE)
    (seed / "capacity/public_cases.py").write_text(prior.PUBLIC_CASES_SOURCE)
    (seed / "observe.py").write_text(prior.OBSERVE_SOURCE)
    (seed / "check_program.py").write_text(CHECKER_SOURCE)
    (seed / "public-bases.json").write_text(json.dumps(PUBLIC_BASES, indent=2, sort_keys=True) + "\n")
    (seed / "subject-position.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "contact-program-contract.json").write_text(json.dumps(program_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "contact-program.json").write_text(json.dumps(program_template(), indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({
        "editable": ["contact-program.json"],
        "immutable": ["capacity/policy.py", "capacity/public_cases.py", "observe.py", "check_program.py", "public-bases.json", "subject-position.json", "contact-program-contract.json"],
    }, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Continue the inherited opening by authoring contact-program.json. Inspect the complete policy, run python3 check_program.py until the program passes honestly, edit no other file, inspect the exact diff, and report truthfully.\n")
    return seed


def run_program_actor(context, p82, root: Path, parent: dict[str, Any]) -> dict[str, Any]:
    label = "contact-program-author"
    seed = write_program_seed(root, base.active_position(parent))
    output, base_audit, workspace, _ = context.run_actor(
        label,
        seed,
        PROGRAM_SCHEMA,
        "Continue the exact subject. Inspect the complete capacity policy and inherited opening, author one transferable metamorphic contact program, run the declared public checker, edit only contact-program.json, inspect the diff, and report truthfully.",
    )
    try:
        program = json.loads((workspace / "contact-program.json").read_text())
    except (OSError, json.JSONDecodeError):
        program = None
    public = evaluate_program(p82, program, PUBLIC_BASES) if valid_program(program) else None
    valid = bool(program and public and public["passed"] and program["target"] == prior.ACTIVE_TARGET)
    audit = context.audit_actor(label, output, base_audit, valid, ["contact-program.json"])
    binding = None
    if valid and prior.audit_accepted(audit):
        body = {
            "authority": "ot-0133-transferable-contact-program-binding",
            "source_subject_digest": parent["artifact_digest"],
            "opening": parent["continuation"]["next_opening"],
            "actor_patch_digest": audit["patch_digest"],
            "public_receipt": public,
            "program": program,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-contact-program.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "program_valid": valid_program(program), "public_check": public, "binding": binding}


def open_hidden_world(p82, root: Path, binding: dict[str, Any]) -> dict[str, Any]:
    hidden = evaluate_program(p82, binding["program"], HIDDEN_BASES)
    contact_id = "program-" + binding["program"]["target"] + "-" + binding["program_digest"][:12] if "program_digest" in binding else "program-" + hashlib.sha256(json.dumps(binding["program"], sort_keys=True).encode()).hexdigest()[:16]
    body = {
        "authority": "ot-0133-sealed-transfer-world",
        "program_binding_digest": binding["binding_digest"],
        "selected_contact_id": contact_id,
        "selected_branch": hidden,
        "expected_route": "extend" if hidden["passed"] else "surrender",
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    (root / "selected-world-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def route_seed(root: Path, parent: dict[str, Any], selector: str, binding: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "route-seed"
    seed.mkdir()
    actor_receipt = {key: value for key, value in world.items() if key != "expected_route"}
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(parent), indent=2, sort_keys=True) + "\n")
    (seed / "bound-selected-contact.json").write_text(json.dumps({"binding": binding, "selected_contact": binding["program"]}, indent=2, sort_keys=True) + "\n")
    (seed / "selected-world-consequence.json").write_text(json.dumps(actor_receipt, indent=2, sort_keys=True) + "\n")
    (seed / "selector.py").write_text(selector)
    (seed / "route-assimilation.json").write_text(json.dumps(prior22.route_template(), indent=2, sort_keys=True) + "\n")
    (seed / "route-only-compiler-contract.json").write_text(json.dumps({
        "compiler_version": base130.COMPILER_VERSION,
        "actor_authored_file": "route-assimilation.json",
        "required_exact_case_ids": sorted(row["case_id"] for row in world["selected_branch"]["cases"]),
        "route_exact": "extend",
        "compiled_action_target": "continuation-5-<sha256(remaining_uncertainty)[0:12]>",
        "compiled_action_expected_information": "exact remaining_uncertainty",
        "selector_is_immutable": True,
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["route-assimilation.json"], "immutable": ["selector.py", "subject-position.json", "bound-selected-contact.json", "selected-world-consequence.json", "route-only-compiler-contract.json"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Assimilate the exact generated consequence once. Cite all nine cases, advance the settled opening, preserve selector.py, edit only route-assimilation.json, inspect the diff, and report truthfully.\n")
    return seed


def run_route_actor(context, p82, prior89, root: Path, parent: dict[str, Any], selector: str, binding: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "consequence-route"
    seed = route_seed(root, parent, selector, binding, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ROUTE_SCHEMA, "Assimilate the exact generated contact consequence under the route-only compiler. Cite all exact cases, preserve the selector, advance the uncertainty, edit one file, inspect the diff, and report truthfully.")
    try:
        route = json.loads((workspace / "route-assimilation.json").read_text())
        retained = (workspace / "selector.py").read_text() == selector
    except (OSError, json.JSONDecodeError):
        route = None
        retained = False
    expected_ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    checks = {
        "route_exact": bool(route and route.get("route") == world["expected_route"] == "extend"),
        "contact_id_exact": bool(route and route.get("selected_contact_id") == world["selected_contact_id"]),
        "case_ids_exact": bool(route and set(route.get("settled_case_ids", [])) == expected_ids),
        "selector_retained": retained,
        "remaining_uncertainty_new": bool(route and prior.valid_text(route.get("remaining_uncertainty")) and len(route["remaining_uncertainty"].strip()) >= 24 and route["remaining_uncertainty"].strip() != parent["continuation"]["next_opening"].strip()),
    }
    checks["passed"] = all(checks.values())
    valid = bool(prior22.valid_route(route) and checks["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["route-assimilation.json"])
    routed = None
    compiler = {"passed": False}
    if valid and prior.audit_accepted(audit):
        actor_body = {"authority": "ot-0133-grounded-route", "source_subject_digest": parent["artifact_digest"], "selection_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "actor_checks": checks, "selector_retention_derived": retained, "route_assimilation": route}
        actor_binding = {**actor_body, "binding_digest": p82.digest(actor_body)}
        action = base130.compile_action(route, 5)
        opening = base130.previous.compile_opening(route, action)
        compiler = {
            "action_valid": prior18.previous.previous.repaired_action_valid(action, parent),
            "target_new": action["action_target"] not in prior22.kernel.registered(parent),
            "expected_information_exact": action["expected_information"] == route["remaining_uncertainty"],
            "opening_structurally_valid": prior89.valid_successor(opening),
            "uncertainty_retained_exactly": opening["unresolved"] == route["remaining_uncertainty"] and route["remaining_uncertainty"] in opening["next_opening"],
            "compiler_deterministic": action == base130.compile_action(route, 5) and opening == base130.previous.compile_opening(route, action),
        }
        compiler["passed"] = all(compiler.values())
        if compiler["passed"]:
            body = {"authority": "ot-0133-program-contact-compiled-continuation", "source_subject_digest": parent["artifact_digest"], "selection_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_binding_digest": actor_binding["binding_digest"], "compiler_version": base130.COMPILER_VERSION, "compiler_checks": compiler, "selector_retention_derived": retained, "route_assimilation": route, "successor_opening": opening, "continuation_action": action}
            routed = {**body, "binding_digest": p82.digest(body)}
            for name, value in (("bound-route.json", actor_binding), ("compiled-continuation-action.json", action), ("compiled-successor-opening.json", opening), ("bound-compiled-route.json", routed)):
                (context.evidence(label) / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "actor_checks": checks, "compiler_checks": compiler, "binding": routed}


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = p82.materialize(repo, store, "OT-0132", "open-subject-after-originated-contact.json")
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
    run = (args.evidence_root or store / "runs/OT-0133").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    selector = parent["allocation_machinery"][-1]["source"]
    public_fixture = evaluate_program(p82, REPRESENTATIVE_PROGRAM, PUBLIC_BASES)
    hidden_fixture = evaluate_program(p82, REPRESENTATIVE_PROGRAM, HIDDEN_BASES)
    with tempfile.TemporaryDirectory() as directory:
        seed = write_program_seed(Path(directory), base.active_position(parent))
        seed_files = sorted(str(path.relative_to(seed)) for path in seed.rglob("*") if path.is_file())
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
        "parent_opening_exact_frontier": "different context pairs and demand patterns" in parent["continuation"]["next_opening"],
        "schemas_present": PROGRAM_SCHEMA.is_file() and ROUTE_SCHEMA.is_file(),
        "representative_program_valid": valid_program(REPRESENTATIVE_PROGRAM),
        "public_fixture_passes": public_fixture["passed"] and len(public_fixture["cases"]) == 6,
        "hidden_fixture_passes": hidden_fixture["passed"] and len(hidden_fixture["cases"]) == 9,
        "public_hidden_disjoint": {row["base_id"] for row in PUBLIC_BASES}.isdisjoint({row["base_id"] for row in HIDDEN_BASES}),
        "seed_complete": seed_files == ["README.md", "capacity/__init__.py", "capacity/policy.py", "capacity/public_cases.py", "check_program.py", "contact-program-contract.json", "contact-program.json", "mutation-envelope.json", "observe.py", "public-bases.json", "subject-position.json"],
    }
    checks["passed"] = all(checks.values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "checks": checks, "public_fixture": public_fixture, "hidden_fixture": hidden_fixture}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0133 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps({"checks": checks, "public_fixture": public_fixture, "hidden_fixture": hidden_fixture}, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    program_root = run / "program-contact"
    program_root.mkdir()
    authored = run_program_actor(context, p82, program_root, parent)
    world = open_hidden_world(p82, program_root, authored["binding"]) if authored["binding"] else None
    current = parent
    routed = None
    promotion = None
    operational = False
    if world and world["selected_branch"]["passed"]:
        route_root = run / "consequence"
        route_root.mkdir()
        routed = run_route_actor(context, p82, prior89, route_root, parent, selector, authored["binding"], world)
        if routed["binding"]:
            current, promotion = prior22.promote(p82, parent, authored["binding"], world, routed["binding"])
        operational = bool(promotion and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and current["artifact_digest"] != parent["artifact_digest"])
    result = {
        "authority": "ot-0133-transferable-contact-program-driver",
        "source_subject_digest": parent["artifact_digest"],
        "program_author": p82.compact(authored),
        "hidden_world": world,
        "consequence_route": p82.compact(routed) if routed else None,
        "promotion": promotion,
        "transferable_contact_program_passed": operational,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "fresh_actor_count": int(authored is not None) + int(routed is not None),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
