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
BASE_PATH = ROOT / "ot_0138_subject_scheduled_encounter_loop.py"
BASE_SHA256 = "56b85c87cf55bc637a78f3e99911282f2f68beb4b4fe3178655d969121c6cfe9"
PARENT_DIGEST = "ad3acd37d497840a26c77b8a449571aa1bcaa03f915c882fc0f3924ad47e6b0f"
CONSTITUTION_VERSION = "ot-0139-constitution-v1"
VALIDATOR_VERSION = "ot-0139-parameterized-program-v1"
META_CEILING = 64
ACTION_SCHEMA = REPO / "spec/ot-0139-constitutional-action.schema.json"
ENCOUNTER_LIMIT = 3


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0138 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0139_frozen_ot0138", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior136 = previous.prior136
prior135 = previous.prior135
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


def make_constitution(p82, ceiling: int, parent_digest: str | None = None, cause: str | None = None) -> dict[str, Any]:
    body = {
        "constitution_version": CONSTITUTION_VERSION,
        "program_validator_version": VALIDATOR_VERSION,
        "program_offset_ceiling": ceiling,
        "editable_program_fields": ["high_offset", "low_offset"],
        "ordinary_revision_trigger": "retained-failure-and-public-passing-candidate-within-ceiling",
        "constitutional_revision_trigger": "retained-failure-and-exhaustive-public-envelope-failure",
        "constitutional_revision_policy": "least-passing-symmetric-offset-ceiling",
        "meta_ceiling": META_CEILING,
        "parent_constitution_digest": parent_digest,
        "cause_receipt_digest": cause,
    }
    return {**body, "constitution_digest": p82.digest(body)}


def install_constitution(p82, parent: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    constitution = make_constitution(p82, 10)
    receipt_body = {
        "authority": "ot-0139-prospective-program-authority-unification",
        "source_subject_digest": parent["artifact_digest"],
        "observed_inherited_validator_ceiling": 10,
        "displaced_visible_ot0138_envelope_ceiling": 16,
        "constitution_digest": constitution["constitution_digest"],
        "correction": "one published parameterized validator governs future program admission",
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["developmental_constitution"] = constitution
    child["developmental_constitution_history"] = [receipt]
    child["encounter_scheduler"] = {**child["encounter_scheduler"], "constitution_digest": constitution["constitution_digest"]}
    return p82.seal(child), receipt


PROGRAM_KEYS = {"question", "rationale", "target", "foreign_context_prefix", "high_offset", "low_offset", "control_mode", "surrender_condition"}


def program_valid(program: Any, constitution: dict[str, Any]) -> bool:
    if not isinstance(program, dict) or set(program) != PROGRAM_KEYS:
        return False
    if program.get("target") != "reserve_for_context" or program.get("control_mode") != "exactly midpoint":
        return False
    if not all(prior131.valid_text(program.get(key)) for key in ("question", "rationale", "surrender_condition")):
        return False
    if not isinstance(program.get("foreign_context_prefix"), str) or not re.fullmatch(r"[a-z][a-z0-9-]*", program["foreign_context_prefix"]):
        return False
    ceiling = constitution.get("program_offset_ceiling")
    return bool(
        isinstance(ceiling, int) and 1 <= ceiling <= META_CEILING
        and all(isinstance(program.get(key), int) and not isinstance(program.get(key), bool) and 1 <= program[key] <= ceiling for key in ("high_offset", "low_offset"))
    )


def variants(program: dict[str, Any], base_case: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    events = prior135.local_events(base_case)
    low, high = min(base_case["demands"]), max(base_case["demands"])
    prefix = program["foreign_context_prefix"]
    contexts = [f"{prefix}-a-{base_case['context']}", f"{prefix}-b-{base_case['context']}"]
    midpoint = (low + high) // 2
    additions = {
        "joint-extremes": [{"context": contexts[0], "demand": high + program["high_offset"]}, {"context": contexts[1], "demand": low - program["low_offset"]}],
        "joint-high": [{"context": contexts[0], "demand": high + program["high_offset"]}, {"context": contexts[1], "demand": high + program["high_offset"]}],
        "joint-low": [{"context": contexts[0], "demand": low - program["low_offset"]}, {"context": contexts[1], "demand": low - program["low_offset"]}],
        "joint-control": [{"context": contexts[0], "demand": midpoint}, {"context": contexts[1], "demand": midpoint}],
    }
    return {name: prior135.insert_two(events, base_case["insert_at"], inserted) for name, inserted in additions.items()}


def evaluate(p82, program: dict[str, Any], bases: list[dict[str, Any]], quantum: int) -> dict[str, Any]:
    rows = []
    for base_case in bases:
        local = prior135.local_events(base_case)
        base_reference = previous.quantized_value(local, base_case["context"], True, quantum)
        for variant, events in variants(program, base_case).items():
            installed = previous.quantized_value(events, base_case["context"], False, quantum)
            reference = previous.quantized_value(events, base_case["context"], True, quantum)
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
        "passed": bool(all(row["distinguishes"] and row["reference_invariant"] for row in adversarial) and all(not row["distinguishes"] and row["reference_invariant"] for row in controls)),
    }


def public_envelope(p82, subject: dict[str, Any], cycle: int) -> dict[str, Any]:
    state = subject["encounter_scheduler"]
    constitution = subject["developmental_constitution"]
    quantum = state["next_quantum"]
    parent = subject["contact_program_capabilities"][-1]["program"]
    bases = previous.bases_for(cycle, quantum, public=True)
    ceiling = constitution["program_offset_ceiling"]
    rows = []
    for offset in range(1, META_CEILING + 1):
        candidate = {**parent, "high_offset": offset, "low_offset": offset}
        result = evaluate(p82, candidate, bases, quantum)
        rows.append({"offset": offset, "within_current_ceiling": offset <= ceiling, "passed": result["passed"]})
    passing = [row["offset"] for row in rows if row["passed"]]
    within = [row["offset"] for row in rows if row["passed"] and row["within_current_ceiling"]]
    body = {
        "authority": "ot-0139-exhaustive-public-correction-envelope",
        "source_subject_digest": subject["artifact_digest"],
        "pending_failure_receipt_digest": state["pending_failure"]["receipt_digest"],
        "quantum": quantum,
        "current_ceiling": ceiling,
        "meta_ceiling": META_CEILING,
        "public_bases_digest": p82.digest(bases),
        "rows": rows,
        "passing_within_current_ceiling": within,
        "least_passing_symmetric_offset": min(passing) if passing else None,
        "exhausted": not within,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def authorization(p82, subject: dict[str, Any]) -> dict[str, Any]:
    state = subject["encounter_scheduler"]
    capability = subject["contact_program_capabilities"][-1]
    envelope = None
    if state["pending_failure"] is None:
        action = "reuse"
        reason = "verification-due" if state["verification_due"] else "open-probe"
    else:
        envelope = public_envelope(p82, subject, state["cycle"] + 1)
        action = "revise-constitution" if envelope["exhausted"] else "revise-program"
        reason = "correction-envelope-exhausted" if envelope["exhausted"] else "retained-failure-with-admissible-correction"
    body = {
        "authority": "ot-0139-subject-constitutional-authorization",
        "source_subject_digest": subject["artifact_digest"],
        "cycle": state["cycle"] + 1,
        "quantum": state["next_quantum"],
        "allowed_action": action,
        "authorization_reason": reason,
        "capability_digest": capability["capability_digest"],
        "constitution_digest": subject["developmental_constitution"]["constitution_digest"],
        "envelope_receipt": envelope,
    }
    return {**body, "binding_digest": p82.digest(body)}


def checker_source() -> str:
    return '''import json
from pathlib import Path

action = json.loads(Path("encounter-action.json").read_text())
constitution = json.loads(Path("developmental-constitution.json").read_text())
authorization = json.loads(Path("encounter-authorization.json").read_text())
bases = json.loads(Path("public-bases.json").read_text())
program = action["program"]
quantum = authorization["quantum"]

def value(events, context, local):
    selected = [event for event in events if not local or event["context"] == context]
    demands = [event["demand"] for event in selected]
    return (max(demands) - min(demands)) // quantum

rows = []
for base in bases:
    events = [{"context": base["context"], "demand": demand} for demand in base["demands"]]
    low, high = min(base["demands"]), max(base["demands"])
    midpoint = (low + high) // 2
    additions = {
        "joint-extremes": [{"context": "foreign-a", "demand": high + program["high_offset"]}, {"context": "foreign-b", "demand": low - program["low_offset"]}],
        "joint-high": [{"context": "foreign-a", "demand": high + program["high_offset"]}, {"context": "foreign-b", "demand": high + program["high_offset"]}],
        "joint-low": [{"context": "foreign-a", "demand": low - program["low_offset"]}, {"context": "foreign-b", "demand": low - program["low_offset"]}],
        "joint-control": [{"context": "foreign-a", "demand": midpoint}, {"context": "foreign-b", "demand": midpoint}],
    }
    for variant, inserted in additions.items():
        changed = list(events)
        for position, event in sorted(zip(base["insert_at"], inserted), reverse=True):
            changed.insert(position, event)
        rows.append({"variant": variant, "distinguishes": value(changed, base["context"], False) != value(changed, base["context"], True)})
world_passed = all(row["distinguishes"] for row in rows if row["variant"] != "joint-control") and all(not row["distinguishes"] for row in rows if row["variant"] == "joint-control")
least = authorization["envelope_receipt"]["least_passing_symmetric_offset"]
if authorization["allowed_action"] == "revise-constitution":
    contract = action["action"] == "revise-constitution" and program["high_offset"] == program["low_offset"] == least and constitution["program_offset_ceiling"] == least
else:
    contract = action["action"] == "revise-program" and program["high_offset"] == program["low_offset"] == least
passed = world_passed and contract
print(json.dumps({"passed": passed, "world_passed": world_passed, "contract": contract, "rows": rows}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def actor_seed(root: Path, subject: dict[str, Any], auth: dict[str, Any]) -> Path:
    seed = root / "actor-seed"
    seed.mkdir()
    capability = subject["contact_program_capabilities"][-1]
    constitution = subject["developmental_constitution"]
    action = {"action": "surrender", "rationale": "Inspect exact authorization and select the permitted action.", "program": capability["program"]}
    files = {
        "subject-position.json": base.active_position(subject),
        "scheduler-state.json": subject["encounter_scheduler"],
        "retained-capability.json": capability,
        "developmental-constitution.json": constitution,
        "encounter-authorization.json": auth,
        "encounter-action.json": action,
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    immutable = ["subject-position.json", "scheduler-state.json", "retained-capability.json", "encounter-authorization.json"]
    editable = ["encounter-action.json"]
    if auth["allowed_action"] == "reuse":
        immutable.append("developmental-constitution.json")
        prompt = "Select exact retained program reuse. Preserve the program and developmental constitution, edit only encounter-action.json, inspect the exact diff, and report truthfully."
    else:
        failure = subject["encounter_scheduler"]["pending_failure"]
        public = previous.bases_for(auth["cycle"], auth["quantum"], public=True)
        (seed / "pending-failure.json").write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
        (seed / "public-bases.json").write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
        (seed / "check_action.py").write_text(checker_source())
        immutable += ["pending-failure.json", "public-bases.json", "check_action.py"]
        if auth["allowed_action"] == "revise-constitution":
            editable.append("developmental-constitution.json")
            prompt = "The retained failure exhausts the current public correction envelope. Revise the program and only the authorized constitution ceiling to the least passing symmetric offset, run python3 check_action.py, inspect the exact two-file diff, and report truthfully."
        else:
            immutable.append("developmental-constitution.json")
            prompt = "Correct only the program offsets within the current constitution, run python3 check_action.py, inspect the exact diff, and report truthfully."
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": editable, "immutable": immutable, "meta_ceiling": META_CEILING}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(prompt + "\n")
    return seed


def constitution_revision_valid(p82, parent: dict[str, Any], candidate: dict[str, Any], auth: dict[str, Any]) -> bool:
    least = auth["envelope_receipt"]["least_passing_symmetric_offset"]
    expected = make_constitution(p82, least, parent["constitution_digest"], auth["envelope_receipt"]["receipt_digest"])
    return candidate == expected


def run_actor(context, p82, root: Path, subject: dict[str, Any], auth: dict[str, Any]) -> dict[str, Any]:
    label = f"encounter-{auth['cycle']}-{auth['allowed_action']}"
    seed = actor_seed(root, subject, auth)
    envelope = json.loads((seed / "mutation-envelope.json").read_text())
    output, base_audit, workspace, _ = context.run_actor(label, seed, ACTION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        action = json.loads((workspace / "encounter-action.json").read_text())
        constitution = json.loads((workspace / "developmental-constitution.json").read_text())
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in envelope["immutable"])
    except (OSError, json.JSONDecodeError, KeyError):
        action = constitution = None
        immutable_ok = False
    parent_program = subject["contact_program_capabilities"][-1]["program"]
    parent_constitution = subject["developmental_constitution"]
    allowed = auth["allowed_action"]
    if allowed == "reuse":
        contract = bool(action and action.get("action") == "reuse" and action.get("program") == parent_program and constitution == parent_constitution)
    elif allowed == "revise-program":
        contract = bool(action and action.get("action") == allowed and constitution == parent_constitution and program_valid(action.get("program"), constitution))
    else:
        contract = bool(action and action.get("action") == allowed and constitution_revision_valid(p82, parent_constitution, constitution, auth) and program_valid(action.get("program"), constitution) and action["program"]["high_offset"] == action["program"]["low_offset"] == constitution["program_offset_ceiling"])
    valid = bool(action and set(action) == {"action", "rationale", "program"} and isinstance(action.get("rationale"), str) and action["rationale"].strip() and contract and immutable_ok)
    audit = context.audit_actor(label, output, base_audit, valid, envelope["editable"])
    accepted = bool(valid and prior131.audit_accepted(audit))
    binding = None
    if accepted:
        body = {
            "authority": "ot-0139-bound-constitutional-encounter-action",
            "source_subject_digest": subject["artifact_digest"],
            "authorization_binding_digest": auth["binding_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "action": action,
            "constitution": constitution,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-encounter-action.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "action_valid": valid, "action": action, "constitution": constitution, "binding": binding}


def world_receipt(p82, auth: dict[str, Any], actor: dict[str, Any], evaluation: dict[str, Any], bases: list[dict[str, Any]]) -> dict[str, Any]:
    body = {
        "authority": "ot-0139-sealed-symmetric-contact-world",
        "authorization_binding_digest": auth["binding_digest"],
        "actor_binding_digest": actor["binding_digest"],
        "cycle": auth["cycle"],
        "quantum": auth["quantum"],
        "bases_digest": p82.digest(bases),
        "selected_branch": evaluation,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def revised_capability(p82, parent: dict[str, Any], program: dict[str, Any], constitution: dict[str, Any], failure: dict[str, Any], actor: dict[str, Any], current_eval: dict[str, Any], floor_eval: dict[str, Any]) -> dict[str, Any]:
    program_digest = p82.digest(program)
    body = {
        "authority": "ot-0139-constitutionally-admitted-contact-capability",
        "capability_id": "contact-program-" + program_digest[:16],
        "program_digest": program_digest,
        "program": program,
        "target": program["target"],
        "parent_capability_digest": parent["capability_digest"],
        "failure_receipt_digest": failure["receipt_digest"],
        "revision_binding_digest": actor["binding_digest"],
        "constitution_digest": constitution["constitution_digest"],
        "failed_regime_repair_digest": p82.digest(current_eval),
        "prior_floor_receipt_digest": p82.digest(floor_eval),
        "public_conformance_passed": True,
        "hidden_conformance_passed": current_eval["passed"] and floor_eval["passed"],
        "composition_interface": "ot-0139-symmetric-joint-v1",
    }
    return {**body, "capability_digest": p82.digest(body)}


def transition(p82, subject: dict[str, Any], auth: dict[str, Any], actor: dict[str, Any], world: dict[str, Any], floor_eval: dict[str, Any] | None = None, unchanged: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    state = copy.deepcopy(subject["encounter_scheduler"])
    action = actor["action"]
    evaluation = world["selected_branch"]
    new_capability = None
    new_constitution = None
    disposition = ""
    if action["action"] == "reuse" and evaluation["passed"]:
        state["verification_due"] = False
        state["admitted_quantum"] = auth["quantum"]
        state["next_quantum"] = auth["quantum"] * 2
        disposition = "verified-and-widened" if subject["encounter_scheduler"]["verification_due"] else "passed-and-widened"
    elif action["action"] == "reuse":
        state["pending_failure"] = world
        state["next_quantum"] = auth["quantum"]
        disposition = "failure-retained"
    elif action["action"] in {"revise-program", "revise-constitution"} and evaluation["passed"] and floor_eval and floor_eval["passed"] and unchanged and not unchanged["passed"]:
        new_constitution = actor["constitution"]
        new_capability = revised_capability(p82, subject["contact_program_capabilities"][-1], action["program"], new_constitution, state["pending_failure"], actor, evaluation, floor_eval)
        state["pending_failure"] = None
        state["verification_due"] = True
        state["constitution_digest"] = new_constitution["constitution_digest"]
        disposition = "constitution-revised-verification-due" if action["action"] == "revise-constitution" else "program-revised-verification-due"
    else:
        state["status"] = "surrendered"
        disposition = "surrendered"
    state["cycle"] += 1
    receipt_body = {
        "authority": "ot-0139-constitutional-state-transition",
        "source_subject_digest": subject["artifact_digest"],
        "authorization_binding_digest": auth["binding_digest"],
        "actor_binding_digest": actor["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "disposition": disposition,
        "successor_state": state,
        "new_capability_digest": new_capability["capability_digest"] if new_capability else None,
        "new_constitution_digest": new_constitution["constitution_digest"] if new_constitution else None,
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["encounter_scheduler"] = state
    child["encounter_history"] = [*child.get("encounter_history", []), receipt]
    if new_capability:
        child["contact_program_capabilities"][-1] = new_capability
    if new_constitution and new_constitution != subject["developmental_constitution"]:
        child["developmental_constitution"] = new_constitution
        child["developmental_constitution_history"] = [*child["developmental_constitution_history"], receipt]
    continuation = previous.continuation_for(p82, state)
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": continuation["next_opening"]}
    child["continuation"] = {**child["continuation"], "status": "open" if state["status"] == "open" else "surrendered", "next_opening": continuation["next_opening"]}
    child["unresolved"] = continuation["question"]
    return p82.seal(child), receipt


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    subject, receipt = install_constitution(p82, parent)
    program8 = subject["contact_program_capabilities"][-1]["program"]
    program16 = {**program8, "high_offset": 16, "low_offset": 16}
    constitution10 = subject["developmental_constitution"]
    constitution16 = make_constitution(p82, 16, constitution10["constitution_digest"], "fixture-cause")
    q16_old = evaluate(p82, program8, previous.bases_for(5, 16), 16)
    q16_new = evaluate(p82, program16, previous.bases_for(5, 16), 16)
    q8_floor = evaluate(p82, program16, previous.bases_for(6, 8), 8)
    initial_auth = authorization(p82, subject)
    fake_actor = {"binding_digest": "fixture-reuse-binding"}
    failure = world_receipt(p82, initial_auth, fake_actor, q16_old, previous.bases_for(5, 16))
    failed = copy.deepcopy(subject)
    failed.pop("artifact_digest", None)
    failed["encounter_scheduler"] = {
        **failed["encounter_scheduler"],
        "cycle": 5,
        "pending_failure": failure,
        "next_quantum": 16,
    }
    failed = p82.seal(failed)
    meta_auth = authorization(p82, failed)
    with tempfile.TemporaryDirectory() as directory:
        seed = actor_seed(Path(directory), failed, meta_auth)
        meta_files = sorted(path.name for path in seed.iterdir() if path.is_file())
    expected_constitution = make_constitution(
        p82,
        16,
        constitution10["constitution_digest"],
        meta_auth["envelope_receipt"]["receipt_digest"],
    )
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "prediction_error_reproduced": not previous.valid_program(program16),
        "truthful_initial_constitution": program_valid(program8, constitution10) and not program_valid(program16, constitution10),
        "revised_constitution_admits_16": program_valid(program16, constitution16),
        "q16_failure_exact": not q16_old["passed"] and q16_old["distinguishing_count"] == 3 and q16_old["confirmation_count"] == 3,
        "q16_revision_exact": q16_new["passed"] and q16_new["distinguishing_count"] == 9,
        "q8_floor_exact": q8_floor["passed"] and q8_floor["distinguishing_count"] == 9,
        "meta_authorization_exact": meta_auth["allowed_action"] == "revise-constitution" and meta_auth["envelope_receipt"]["exhausted"] and meta_auth["envelope_receipt"]["least_passing_symmetric_offset"] == 16,
        "meta_seed_complete": meta_files == ["README.md", "check_action.py", "developmental-constitution.json", "encounter-action.json", "encounter-authorization.json", "mutation-envelope.json", "pending-failure.json", "public-bases.json", "retained-capability.json", "scheduler-state.json", "subject-position.json"],
        "constitutional_revision_shape_exact": constitution_revision_valid(p82, constitution10, expected_constitution, meta_auth),
        "installation_receipted": receipt["constitution_digest"] == constitution10["constitution_digest"],
        "schema_present": ACTION_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "q16_old": q16_old, "q16_new": q16_new, "q8_floor": q8_floor}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0139").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = prior135.load_json_artifact(p82, repo, store, "OT-0138", "open-subject-with-encounter-scheduler.json")
    subject, installation = install_constitution(p82, parent)
    fixtures = preflight(p82, parent)
    fixtures["checks"]["parent_sounding_open"] = runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open"
    fixtures["checks"]["seeded_sounding_open"] = runtime.identity_conforms(subject) and subject["continuation"]["status"] == "open"
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "seeded_subject_digest": subject["artifact_digest"]}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0139 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    (run / "constitution-installation.json").write_text(json.dumps(installation, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    current = subject
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
        action = acted["action"]
        hidden_bases = previous.bases_for(cycle, auth["quantum"])
        evaluation = evaluate(p82, action["program"], hidden_bases, auth["quantum"])
        world = world_receipt(p82, auth, acted["binding"], evaluation, hidden_bases)
        floor_eval = unchanged = None
        if action["action"] in {"revise-program", "revise-constitution"}:
            failure = current["encounter_scheduler"]["pending_failure"]
            failure_bases = previous.bases_for(failure["cycle"], failure["quantum"])
            evaluation = evaluate(p82, action["program"], failure_bases, failure["quantum"])
            world = world_receipt(p82, auth, acted["binding"], evaluation, failure_bases)
            unchanged = failure["selected_branch"]
            floor_quantum = current["encounter_scheduler"]["admitted_quantum"]
            floor_eval = evaluate(p82, action["program"], previous.bases_for(cycle, floor_quantum), floor_quantum)
            (cycle_root / "prior-floor-receipt.json").write_text(json.dumps(floor_eval, indent=2, sort_keys=True) + "\n")
        (cycle_root / "sealed-world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
        prior_subject = current
        current, transition_receipt = transition(p82, current, auth, acted["binding"], world, floor_eval, unchanged)
        transition_ok = runtime.identity_conforms(current) and current["encounter_scheduler"]["cycle"] == cycle and current["continuation"]["status"] == "open"
        encounters.append({
            "cycle": cycle,
            "source_subject_digest": prior_subject["artifact_digest"],
            "authorization": auth,
            "actor": p82.compact(acted),
            "world": world,
            "prior_floor": floor_eval,
            "unchanged_parent": unchanged,
            "transition": transition_receipt,
            "transition_passed": transition_ok,
            "successor_subject_digest": current["artifact_digest"],
        })
        if not transition_ok:
            break
    actions = [item.get("actor", {}).get("action", {}).get("action") for item in encounters]
    worlds = [item.get("world", {}).get("selected_branch", {}) for item in encounters]
    state = current["encounter_scheduler"]
    erased = copy.deepcopy(current)
    erased.pop("artifact_digest", None)
    erased.pop("developmental_constitution", None)
    erased = p82.seal(erased)
    checks = {
        "three_fresh_encounters": len(encounters) == 3 and all(item["transition_passed"] for item in encounters),
        "actions_exact": actions == ["reuse", "revise-constitution", "reuse"],
        "failure_exact": len(worlds) == 3 and not worlds[0]["passed"] and worlds[0]["distinguishing_count"] == 3 and encounters[0]["transition"]["disposition"] == "failure-retained",
        "envelope_exhausted_exact": len(encounters) == 3 and encounters[1]["authorization"]["envelope_receipt"]["exhausted"] and encounters[1]["authorization"]["envelope_receipt"]["passing_within_current_ceiling"] == [] and encounters[1]["authorization"]["envelope_receipt"]["least_passing_symmetric_offset"] == 16,
        "constitution_revision_beats_parent": len(worlds) == 3 and worlds[1]["passed"] and worlds[1]["distinguishing_count"] == 9 and encounters[1]["unchanged_parent"] == worlds[0] and not worlds[0]["passed"],
        "prior_floor_preserved": bool(len(encounters) == 3 and encounters[1]["prior_floor"] and encounters[1]["prior_floor"]["passed"]),
        "later_reuse_without_repair": len(worlds) == 3 and worlds[2]["passed"] and encounters[2]["actor"]["action"]["program"] == current["contact_program_capabilities"][-1]["program"],
        "constitution_retained": current["developmental_constitution"]["program_offset_ceiling"] == 16 and current["developmental_constitution"]["constitution_digest"] == state["constitution_digest"],
        "scheduler_points_beyond_observer": state["cycle"] == 7 and state["next_quantum"] == 32 and state["admitted_quantum"] == 16 and state["pending_failure"] is None and not state["verification_due"],
        "final_subject_sounding_open": runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and "reserve band 32" in current["continuation"]["next_opening"],
        "constitution_erased_has_no_authorization": "developmental_constitution" not in erased,
        "distinct_actor_bindings": len({item["actor"]["binding"]["binding_digest"] for item in encounters if item.get("actor", {}).get("binding")}) == 3,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0139-consequence-revised-developmental-constitution-driver",
        "source_subject_digest": parent["artifact_digest"],
        "seeded_subject_digest": subject["artifact_digest"],
        "encounters": encounters,
        "checks": checks,
        "constitutional_revision_passed": checks["passed"],
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
    (run / "constitution-erased-control.json").write_text(json.dumps(erased, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
