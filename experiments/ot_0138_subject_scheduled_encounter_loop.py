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
BASE_PATH = ROOT / "ot_0137_structured_continuation_projection.py"
BASE_SHA256 = "e80313386b7a8037af1b70a3c4442bccd89b26e0bc88f0a256b05f8894ab014f"
PARENT_DIGEST = "8ed20a053a3663570a94b551c1d44e5dac9ddb6e8447853b6c1862bc4769b367"
SCHEDULER_VERSION = "ot-0138-scheduler-v1"
ACTION_SCHEMA = REPO / "spec/ot-0138-encounter-action.schema.json"
ENCOUNTER_LIMIT = 4


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0137 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0138_frozen_ot0137", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior136 = previous.prior
prior135 = prior136.prior135
prior131 = prior136.prior131
base130 = previous.base130
base = previous.base


def seal(p82, value: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(value)
    value.pop("artifact_digest", None)
    return p82.seal(value)


def seed_scheduler(p82, parent: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    state = {
        "scheduler_version": SCHEDULER_VERSION,
        "cycle": 0,
        "admitted_quantum": 4,
        "next_quantum": 4,
        "pending_failure": None,
        "verification_due": False,
        "status": "open",
    }
    receipt_body = {
        "authority": "ot-0138-prospective-encounter-scheduler-installation",
        "source_subject_digest": parent["artifact_digest"],
        "scheduler_version": SCHEDULER_VERSION,
        "initial_state": state,
        "transition_rule": [
            "reuse-only-without-pending-failure",
            "success-widens-quantum",
            "failure-retained-at-same-quantum",
            "failure-authorizes-minimal-revision",
            "revision-requires-same-regime-and-prior-floor",
            "verification-reuses-without-repair-before-widening",
        ],
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["encounter_scheduler"] = state
    child["encounter_scheduler_installation"] = receipt
    child["encounter_history"] = []
    return p82.seal(child), receipt


def valid_program(program: Any) -> bool:
    return bool(
        isinstance(program, dict)
        and prior136.base134.corrected_valid_program(program)
        and isinstance(program.get("high_offset"), int)
        and isinstance(program.get("low_offset"), int)
        and 1 <= program["high_offset"] <= 16
        and 1 <= program["low_offset"] <= 16
    )


def bases_for(cycle: int, quantum: int, public: bool = False) -> list[dict[str, Any]]:
    count = 2 if public else 3
    prefix = "public" if public else "sealed"
    names = ("amber", "blue", "cedar")
    bases = []
    for index in range(count):
        low = 11 + cycle * 7 + index * 5
        high = low + 2 * quantum
        middle = low + quantum
        demands = [low, middle, high, middle, low]
        bases.append({
            "base_id": f"{prefix}-cycle-{cycle}-{names[index]}-q{quantum}",
            "context": f"context-{cycle}-{names[index]}",
            "insert_at": [1, 4],
            "demands": demands,
        })
    return bases


def quantized_value(events: list[dict[str, Any]], context: str, local: bool, quantum: int) -> int:
    selected = [event for event in events if not local or event["context"] == context]
    demands = [event["demand"] for event in selected]
    return (max(demands) - min(demands)) // quantum


def evaluate(p82, program: dict[str, Any], bases: list[dict[str, Any]], quantum: int) -> dict[str, Any]:
    rows = []
    for base_case in bases:
        local_events = prior135.local_events(base_case)
        base_reference = quantized_value(local_events, base_case["context"], True, quantum)
        for variant, events in prior135.joint_variants(program, base_case).items():
            installed = quantized_value(events, base_case["context"], False, quantum)
            reference = quantized_value(events, base_case["context"], True, quantum)
            rows.append({
                "case_id": f"{base_case['base_id']}-{variant}",
                "variant": variant,
                "installed_output": installed,
                "reference_output": reference,
                "base_reference_output": base_reference,
                "distinguishes": installed != reference,
                "reference_invariant": reference == base_reference,
            })
    adversarial = [row for row in rows if row["variant"] != "joint-control"]
    controls = [row for row in rows if row["variant"] == "joint-control"]
    return {
        "quantum": quantum,
        "program_digest": p82.digest(program),
        "bases_digest": p82.digest(bases),
        "cases": rows,
        "adversarial_count": len(adversarial),
        "distinguishing_count": sum(row["distinguishes"] for row in adversarial),
        "confirmation_count": sum(not row["distinguishes"] for row in controls),
        "passed": bool(
            adversarial and controls
            and all(row["distinguishes"] and row["reference_invariant"] for row in adversarial)
            and all(not row["distinguishes"] and row["reference_invariant"] for row in controls)
        ),
    }


def authorization(p82, subject: dict[str, Any]) -> dict[str, Any]:
    state = subject["encounter_scheduler"]
    capability = subject["contact_program_capabilities"][-1]
    if state["pending_failure"] is not None:
        allowed = "revise"
        reason = "retained-objective-failure"
    else:
        allowed = "reuse"
        reason = "verification-due" if state["verification_due"] else "open-probe"
    body = {
        "authority": "ot-0138-subject-scheduled-encounter-authorization",
        "scheduler_version": SCHEDULER_VERSION,
        "source_subject_digest": subject["artifact_digest"],
        "cycle": state["cycle"] + 1,
        "quantum": state["next_quantum"],
        "allowed_action": allowed,
        "authorization_reason": reason,
        "capability_digest": capability["capability_digest"],
        "program_digest": capability["program_digest"],
        "pending_failure_receipt_digest": state["pending_failure"]["receipt_digest"] if state["pending_failure"] else None,
    }
    return {**body, "binding_digest": p82.digest(body)}


def action_template(capability: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": "surrender",
        "rationale": "Replace with the authorized action after inspecting exact subject state.",
        "program": capability["program"],
    }


def checker_source(quantum: int) -> str:
    return f'''import json
from pathlib import Path

QUANTUM = {quantum}
action = json.loads(Path("encounter-action.json").read_text())
program = action["program"]
bases = json.loads(Path("public-bases.json").read_text())

def value(events, context, local):
    selected = [event for event in events if not local or event["context"] == context]
    demands = [event["demand"] for event in selected]
    return (max(demands) - min(demands)) // QUANTUM

rows = []
for base in bases:
    events = [{{"context": base["context"], "demand": demand}} for demand in base["demands"]]
    low, high = min(base["demands"]), max(base["demands"])
    midpoint = (low + high) // 2
    additions = {{
        "joint-extremes": [{{"context": "foreign-a", "demand": high + program["high_offset"]}}, {{"context": "foreign-b", "demand": low - program["low_offset"]}}],
        "joint-high": [{{"context": "foreign-a", "demand": high + program["high_offset"]}}, {{"context": "foreign-b", "demand": high + program["high_offset"]}}],
        "joint-control": [{{"context": "foreign-a", "demand": midpoint}}, {{"context": "foreign-b", "demand": midpoint}}],
    }}
    for variant, inserted in additions.items():
        changed = list(events)
        for position, event in sorted(zip(base["insert_at"], inserted), reverse=True):
            changed.insert(position, event)
        installed = value(changed, base["context"], False)
        reference = value(changed, base["context"], True)
        rows.append({{"variant": variant, "distinguishes": installed != reference}})
passed = action["action"] == "revise" and all(row["distinguishes"] for row in rows if row["variant"] != "joint-control") and all(not row["distinguishes"] for row in rows if row["variant"] == "joint-control")
print(json.dumps({{"passed": passed, "rows": rows}}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def actor_seed(root: Path, subject: dict[str, Any], binding: dict[str, Any]) -> Path:
    seed = root / "actor-seed"
    seed.mkdir()
    capability = subject["contact_program_capabilities"][-1]
    state = subject["encounter_scheduler"]
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(subject), indent=2, sort_keys=True) + "\n")
    (seed / "scheduler-state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    (seed / "retained-capability.json").write_text(json.dumps(capability, indent=2, sort_keys=True) + "\n")
    (seed / "encounter-authorization.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    (seed / "encounter-action.json").write_text(json.dumps(action_template(capability), indent=2, sort_keys=True) + "\n")
    immutable = ["subject-position.json", "scheduler-state.json", "retained-capability.json", "encounter-authorization.json"]
    if binding["allowed_action"] == "revise":
        failure = state["pending_failure"]
        public = bases_for(binding["cycle"], binding["quantum"], public=True)
        (seed / "pending-failure.json").write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
        (seed / "public-bases.json").write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
        (seed / "check_action.py").write_text(checker_source(binding["quantum"]))
        immutable += ["pending-failure.json", "public-bases.json", "check_action.py"]
        prompt = "The subject retained an objective failure. Select revise, minimally correct only the two offsets in encounter-action.json, run python3 check_action.py, inspect the exact diff, and report truthfully."
    else:
        prompt = "The subject authorizes reuse. Select reuse in encounter-action.json, preserve the retained program exactly, inspect the exact diff, and report truthfully."
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["encounter-action.json"], "immutable": immutable, "offset_range": [1, 16]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(prompt + "\n")
    return seed


def minimal_revision(parent: dict[str, Any], candidate: dict[str, Any]) -> bool:
    if not valid_program(candidate):
        return False
    immutable = set(parent) - {"high_offset", "low_offset"}
    return bool(
        all(candidate[key] == parent[key] for key in immutable)
        and (candidate["high_offset"], candidate["low_offset"]) != (parent["high_offset"], parent["low_offset"])
    )


def run_actor(context, p82, root: Path, subject: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    label = f"encounter-{binding['cycle']}-{binding['allowed_action']}"
    seed = actor_seed(root, subject, binding)
    prompt = (seed / "README.md").read_text().strip()
    output, base_audit, workspace, _ = context.run_actor(label, seed, ACTION_SCHEMA, prompt)
    try:
        action = json.loads((workspace / "encounter-action.json").read_text())
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        )
    except (OSError, json.JSONDecodeError, KeyError):
        action = None
        immutable_ok = False
    capability = subject["contact_program_capabilities"][-1]
    program = action.get("program") if isinstance(action, dict) else None
    if binding["allowed_action"] == "reuse":
        contract = bool(action and action.get("action") == "reuse" and program == capability["program"])
    else:
        contract = bool(action and action.get("action") == "revise" and minimal_revision(capability["program"], program))
    action_valid = bool(
        action and set(action) == {"action", "rationale", "program"}
        and isinstance(action.get("rationale"), str) and action["rationale"].strip()
        and valid_program(program) and contract and immutable_ok
    )
    audit = context.audit_actor(label, output, base_audit, action_valid, ["encounter-action.json"])
    accepted = bool(action_valid and prior131.audit_accepted(audit))
    actor_binding = None
    if accepted:
        body = {
            "authority": "ot-0138-bound-encounter-action",
            "authorization_binding_digest": binding["binding_digest"],
            "source_subject_digest": subject["artifact_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "action": action,
        }
        actor_binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-encounter-action.json").write_text(json.dumps(actor_binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "action_valid": action_valid, "action": action, "binding": actor_binding}


def world_receipt(p82, binding: dict[str, Any], actor_binding: dict[str, Any], evaluation: dict[str, Any], bases: list[dict[str, Any]]) -> dict[str, Any]:
    body = {
        "authority": "ot-0138-sealed-scheduled-encounter-world",
        "authorization_binding_digest": binding["binding_digest"],
        "actor_binding_digest": actor_binding["binding_digest"],
        "cycle": binding["cycle"],
        "quantum": binding["quantum"],
        "bases_digest": p82.digest(bases),
        "selected_branch": evaluation,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def revised_capability(p82, parent: dict[str, Any], program: dict[str, Any], failure: dict[str, Any], action: dict[str, Any], current_eval: dict[str, Any], floor_eval: dict[str, Any]) -> dict[str, Any]:
    program_digest = p82.digest(program)
    body = {
        "authority": "ot-0138-scheduled-consequence-corrected-capability",
        "capability_id": "contact-program-" + program_digest[:16],
        "program_digest": program_digest,
        "program": program,
        "target": program["target"],
        "parent_capability_digest": parent["capability_digest"],
        "failure_receipt_digest": failure["receipt_digest"],
        "correction_binding_digest": action["binding_digest"],
        "failed_regime_repair_digest": p82.digest(current_eval),
        "prior_floor_receipt_digest": p82.digest(floor_eval),
        "public_conformance_passed": True,
        "hidden_conformance_passed": current_eval["passed"] and floor_eval["passed"],
        "composition_interface": prior135.COMPOSITION_VERSION,
    }
    return {**body, "capability_digest": p82.digest(body)}


def continuation_for(p82, state: dict[str, Any]) -> dict[str, Any]:
    phase = "correct retained failure at" if state["pending_failure"] else ("verify corrected capability at" if state["verification_due"] else "test retained capability at")
    question = f"Whether the subject can {phase} reserve band {state['next_quantum']} while preserving prior contact remains unresolved."
    suffix = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:12]
    opening = f"Open encounter-{state['cycle'] + 1}-{suffix}: {question}"
    return {"question": question, "next_opening": opening}


def transition(p82, subject: dict[str, Any], auth: dict[str, Any], actor_binding: dict[str, Any], world: dict[str, Any], floor_eval: dict[str, Any] | None = None, unchanged_eval: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    state = copy.deepcopy(subject["encounter_scheduler"])
    action = actor_binding["action"]
    evaluation = world["selected_branch"]
    old_capability = subject["contact_program_capabilities"][-1]
    new_capability = None
    disposition = ""
    if action["action"] == "reuse" and evaluation["passed"]:
        if state["verification_due"]:
            state["verification_due"] = False
            state["admitted_quantum"] = auth["quantum"]
            state["next_quantum"] = auth["quantum"] * 2
            disposition = "verified-and-widened"
        else:
            state["admitted_quantum"] = auth["quantum"]
            state["next_quantum"] = auth["quantum"] * 2
            disposition = "passed-and-widened"
    elif action["action"] == "reuse" and not evaluation["passed"]:
        state["pending_failure"] = world
        state["next_quantum"] = auth["quantum"]
        disposition = "failure-retained"
    elif action["action"] == "revise" and evaluation["passed"] and floor_eval and floor_eval["passed"] and unchanged_eval and not unchanged_eval["passed"]:
        new_capability = revised_capability(p82, old_capability, action["program"], state["pending_failure"], actor_binding, evaluation, floor_eval)
        state["pending_failure"] = None
        state["verification_due"] = True
        state["next_quantum"] = auth["quantum"]
        disposition = "revision-admitted-verification-due"
    else:
        state["status"] = "surrendered"
        disposition = "surrendered"
    state["cycle"] += 1
    receipt_body = {
        "authority": "ot-0138-encounter-state-transition",
        "source_subject_digest": subject["artifact_digest"],
        "authorization_binding_digest": auth["binding_digest"],
        "actor_binding_digest": actor_binding["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "prior_floor_digest": p82.digest(floor_eval) if floor_eval else None,
        "unchanged_parent_digest": p82.digest(unchanged_eval) if unchanged_eval else None,
        "disposition": disposition,
        "successor_state": state,
        "new_capability_digest": new_capability["capability_digest"] if new_capability else None,
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["encounter_scheduler"] = state
    child["encounter_history"] = [*child.get("encounter_history", []), receipt]
    if new_capability:
        child["contact_program_capabilities"][-1] = new_capability
    continuation = continuation_for(p82, state)
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": continuation["next_opening"]}
    child["continuation"] = {**child["continuation"], "status": "open" if state["status"] == "open" else "surrendered", "next_opening": continuation["next_opening"]}
    child["unresolved"] = continuation["question"]
    return p82.seal(child), receipt


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    seeded, install = seed_scheduler(p82, parent)
    program4 = seeded["contact_program_capabilities"][-1]["program"]
    program8 = {**program4, "high_offset": 8, "low_offset": 8}
    q4 = evaluate(p82, program4, bases_for(1, 4), 4)
    q8_old = evaluate(p82, program4, bases_for(2, 8), 8)
    q8_new = evaluate(p82, program8, bases_for(2, 8), 8)
    q4_floor = evaluate(p82, program8, bases_for(3, 4), 4)
    auth = authorization(p82, seeded)
    with tempfile.TemporaryDirectory() as directory:
        seed = actor_seed(Path(directory), seeded, auth)
        names = sorted(path.name for path in seed.iterdir() if path.is_file())
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "seeded_sounding_open": seeded["encounter_scheduler"]["status"] == "open",
        "initial_authorization_reuse": auth["allowed_action"] == "reuse" and auth["quantum"] == 4,
        "q4_prediction_exact": q4["passed"] and q4["distinguishing_count"] == 6 and q4["confirmation_count"] == 3,
        "q8_failure_exact": not q8_old["passed"] and q8_old["distinguishing_count"] == 3 and q8_old["confirmation_count"] == 3,
        "q8_revision_exact": q8_new["passed"] and q8_new["distinguishing_count"] == 6,
        "q4_floor_exact": q4_floor["passed"] and q4_floor["distinguishing_count"] == 6,
        "reuse_seed_exact": names == ["README.md", "encounter-action.json", "encounter-authorization.json", "mutation-envelope.json", "retained-capability.json", "scheduler-state.json", "subject-position.json"],
        "schema_present": ACTION_SCHEMA.is_file(),
        "install_receipted": install["initial_state"] == seeded["encounter_scheduler"],
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "q4": q4, "q8_old": q8_old, "q8_new": q8_new, "q4_floor": q4_floor}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0138").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = prior135.load_json_artifact(p82, repo, store, "OT-0137", "open-subject-with-structured-continuation.json")
    fixtures = preflight(p82, parent)
    seeded, installation = seed_scheduler(p82, parent)
    fixtures["checks"]["parent_sounding_open"] = runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open"
    fixtures["checks"]["seeded_identity_conforms"] = runtime.identity_conforms(seeded)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "seeded_subject_digest": seeded["artifact_digest"]}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0138 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    (run / "scheduler-installation.json").write_text(json.dumps(installation, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    current = seeded
    encounters = []
    started = time.time()
    for _ in range(ENCOUNTER_LIMIT):
        cycle = current["encounter_scheduler"]["cycle"] + 1
        cycle_root = run / f"encounter-{cycle}"
        cycle_root.mkdir()
        auth = authorization(p82, current)
        (cycle_root / "bound-authorization.json").write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n")
        acted = run_actor(context, p82, cycle_root, current, auth)
        if not acted["binding"]:
            encounters.append({"cycle": cycle, "authorization": auth, "actor": p82.compact(acted), "transition_passed": False})
            break
        program = acted["action"]["program"]
        hidden_bases = bases_for(cycle, auth["quantum"])
        evaluation = evaluate(p82, program, hidden_bases, auth["quantum"])
        world = world_receipt(p82, auth, acted["binding"], evaluation, hidden_bases)
        (cycle_root / "sealed-world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
        floor_eval = unchanged_eval = None
        if acted["action"]["action"] == "revise":
            failure = current["encounter_scheduler"]["pending_failure"]
            failure_bases = bases_for(failure["cycle"], failure["quantum"])
            evaluation = evaluate(p82, program, failure_bases, failure["quantum"])
            world = world_receipt(p82, auth, acted["binding"], evaluation, failure_bases)
            unchanged_eval = failure["selected_branch"]
            floor_eval = evaluate(p82, program, bases_for(cycle, current["encounter_scheduler"]["admitted_quantum"]), current["encounter_scheduler"]["admitted_quantum"])
            (cycle_root / "sealed-world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
            (cycle_root / "prior-floor-receipt.json").write_text(json.dumps(floor_eval, indent=2, sort_keys=True) + "\n")
        prior_subject = current
        current, transition_receipt = transition(p82, current, auth, acted["binding"], world, floor_eval, unchanged_eval)
        transition_ok = runtime.identity_conforms(current) and current["encounter_scheduler"]["cycle"] == cycle and current["continuation"]["status"] == "open"
        encounters.append({
            "cycle": cycle,
            "source_subject_digest": prior_subject["artifact_digest"],
            "authorization": auth,
            "actor": p82.compact(acted),
            "world": world,
            "prior_floor": floor_eval,
            "unchanged_parent": unchanged_eval,
            "transition": transition_receipt,
            "transition_passed": transition_ok,
            "successor_subject_digest": current["artifact_digest"],
        })
        if not transition_ok or current["encounter_scheduler"]["status"] != "open":
            break
    state = current["encounter_scheduler"]
    actions = [item.get("actor", {}).get("action", {}).get("action") for item in encounters]
    worlds = [item.get("world", {}).get("selected_branch", {}) for item in encounters]
    scheduler_erased = copy.deepcopy(current)
    scheduler_erased.pop("artifact_digest", None)
    scheduler_erased.pop("encounter_scheduler", None)
    scheduler_erased = p82.seal(scheduler_erased)
    checks = {
        "four_fresh_encounters": len(encounters) == 4 and all(item["transition_passed"] for item in encounters),
        "actions_derived_exact": actions == ["reuse", "reuse", "revise", "reuse"],
        "first_reuse_passed": len(worlds) == 4 and worlds[0]["passed"] and worlds[0]["distinguishing_count"] == 6,
        "failure_retained_exact": len(worlds) == 4 and not worlds[1]["passed"] and worlds[1]["distinguishing_count"] == 3 and encounters[1]["transition"]["disposition"] == "failure-retained",
        "revision_beats_unchanged": len(worlds) == 4 and worlds[2]["passed"] and encounters[2]["unchanged_parent"] == worlds[1] and not encounters[2]["unchanged_parent"]["passed"],
        "prior_floor_preserved": bool(len(encounters) == 4 and encounters[2]["prior_floor"] and encounters[2]["prior_floor"]["passed"]),
        "later_reuse_without_repair": len(worlds) == 4 and worlds[3]["passed"] and encounters[3]["actor"]["action"]["program"] == current["contact_program_capabilities"][-1]["program"],
        "scheduler_points_beyond_observer": state["cycle"] == 4 and state["next_quantum"] == 16 and state["admitted_quantum"] == 8 and state["pending_failure"] is None and not state["verification_due"] and state["status"] == "open",
        "final_subject_sounding_open": runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and "reserve band 16" in current["continuation"]["next_opening"],
        "scheduler_erased_has_no_next_encounter": "encounter_scheduler" not in scheduler_erased,
        "distinct_actor_bindings": len({item["actor"]["binding"]["binding_digest"] for item in encounters if item.get("actor", {}).get("binding")}) == 4,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0138-subject-scheduled-encounter-loop-driver",
        "source_subject_digest": parent["artifact_digest"],
        "seeded_subject_digest": seeded["artifact_digest"],
        "scheduler_version": SCHEDULER_VERSION,
        "encounters": encounters,
        "checks": checks,
        "subject_scheduled_loop_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "observer_stopped_after": len(encounters),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    (run / "scheduler-erased-control.json").write_text(json.dumps(scheduler_erased, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
