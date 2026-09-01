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
BASE_PATH = ROOT / "ot_0145_contradiction_corrected_transferred_priority.py"
BASE_SHA256 = "f5337d35b0d369e5e22e0866794b47b639d503cae8f8204e49aae74aca3e40c1"
PARENT_DIGEST = "8e4099de425271c78471cdb8d0cfadb335d14a8755d200f6793df427f65edc37"
PROGRAM_SCHEMA = REPO / "spec/ot-0146-selector-program.schema.json"
REUSE_SCHEMA = REPO / "spec/ot-0146-program-reuse.schema.json"
PROGRAM_VERSION = "ot-0146-total-selector-expression-v1"
SELECTION_CONTEXT = {"hard_deadline": 64, "admissible_observed_maximum": 256}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0145 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0146_frozen_ot0145", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
p82base = previous.ot142
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def valid_expression(expr: Any, depth: int = 0) -> bool:
    if depth > 8 or not isinstance(expr, dict) or not isinstance(expr.get("op"), str):
        return False
    op = expr["op"]
    if op in {"public-pass", "simulated-at-envelope-maximum", "strategy-field-count", "candidate-id"}:
        return set(expr) == {"op"}
    if op == "context":
        return set(expr) == {"op", "key"} and expr["key"] in {"hard_deadline", "admissible_observed_maximum"}
    if op == "not":
        return set(expr) == {"op", "arg"} and valid_expression(expr["arg"], depth + 1)
    if op in {"gt", "lt", "eq"}:
        return set(expr) == {"op", "left", "right"} and valid_expression(expr["left"], depth + 1) and valid_expression(expr["right"], depth + 1)
    return False


def valid_program(program: Any) -> bool:
    if not isinstance(program, dict) or set(program) != {"program_id", "score", "rationale", "surrender_condition"}:
        return False
    if not isinstance(program["program_id"], str) or not program["program_id"].startswith("selector-"):
        return False
    if not prior131.valid_text(program["rationale"]) or not prior131.valid_text(program["surrender_condition"]):
        return False
    score = program["score"]
    return isinstance(score, list) and 1 <= len(score) <= 6 and all(valid_expression(item) for item in score)


def simulate(candidate: dict[str, Any], maximum: int) -> int:
    strategy = candidate["strategy"]
    observed = strategy["factor"] * maximum
    return min(observed, strategy["deadline"]) if strategy["kind"] == "deadline-capped" else observed


def expression_value(expr: dict[str, Any], candidate: dict[str, Any], public_pass: bool, context: dict[str, int]) -> Any:
    op = expr["op"]
    if op == "public-pass":
        return public_pass
    if op == "simulated-at-envelope-maximum":
        return simulate(candidate, context["admissible_observed_maximum"])
    if op == "strategy-field-count":
        return len(candidate["strategy"])
    if op == "candidate-id":
        return candidate["candidate_id"]
    if op == "context":
        return context[expr["key"]]
    if op == "not":
        return not bool(expression_value(expr["arg"], candidate, public_pass, context))
    left = expression_value(expr["left"], candidate, public_pass, context)
    right = expression_value(expr["right"], candidate, public_pass, context)
    if op == "gt":
        return left > right
    if op == "lt":
        return left < right
    return left == right


def program_select(program: dict[str, Any], portfolio: dict[str, Any], context: dict[str, int]) -> dict[str, Any]:
    ranked = []
    for item in portfolio["public_candidates"]:
        candidate = item["candidate"]
        key = [expression_value(expr, candidate, item["public_evaluation"]["passed"], context) for expr in program["score"]]
        ranked.append({"candidate": candidate, "rank_key": key})
    ranked.sort(key=lambda row: tuple(row["rank_key"]))
    return {"selected_candidate": ranked[0]["candidate"], "ranked": ranked}


GRAMMAR = {
    "version": PROGRAM_VERSION,
    "selection": "ascending lexicographic score; false sorts before true",
    "leaf_operations": ["public-pass", "simulated-at-envelope-maximum", "strategy-field-count", "candidate-id"],
    "context_operation": {"op": "context", "keys": ["hard_deadline", "admissible_observed_maximum"]},
    "unary_operations": ["not"],
    "binary_operations": ["gt", "lt", "eq"],
    "limits": {"maximum_depth": 8, "maximum_score_terms": 6},
    "named_derived_features": [],
}


PROGRAM_CHECKER = r'''import json
from pathlib import Path

program = json.loads(Path("selector-program.json").read_text())
portfolio = json.loads(Path("bound-training-portfolio.json").read_text())
world = json.loads(Path("comparative-consequence.json").read_text())
context = json.loads(Path("selection-context.json").read_text())

def valid(expr, depth=0):
    if depth > 8 or not isinstance(expr, dict) or not isinstance(expr.get("op"), str): return False
    op = expr["op"]
    if op in {"public-pass", "simulated-at-envelope-maximum", "strategy-field-count", "candidate-id"}: return set(expr) == {"op"}
    if op == "context": return set(expr) == {"op", "key"} and expr["key"] in {"hard_deadline", "admissible_observed_maximum"}
    if op == "not": return set(expr) == {"op", "arg"} and valid(expr["arg"], depth + 1)
    return op in {"gt", "lt", "eq"} and set(expr) == {"op", "left", "right"} and valid(expr["left"], depth + 1) and valid(expr["right"], depth + 1)

def sim(candidate):
    strategy = candidate["strategy"]
    raw = strategy["factor"] * context["admissible_observed_maximum"]
    return min(raw, strategy["deadline"]) if strategy["kind"] == "deadline-capped" else raw

def value(expr, candidate, public_pass):
    op = expr["op"]
    if op == "public-pass": return public_pass
    if op == "simulated-at-envelope-maximum": return sim(candidate)
    if op == "strategy-field-count": return len(candidate["strategy"])
    if op == "candidate-id": return candidate["candidate_id"]
    if op == "context": return context[expr["key"]]
    if op == "not": return not bool(value(expr["arg"], candidate, public_pass))
    left, right = value(expr["left"], candidate, public_pass), value(expr["right"], candidate, public_pass)
    return left > right if op == "gt" else left < right if op == "lt" else left == right

score = program.get("score")
shape = set(program) == {"program_id", "score", "rationale", "surrender_condition"} and isinstance(program.get("program_id"), str) and program["program_id"].startswith("selector-") and isinstance(score, list) and 1 <= len(score) <= 6 and all(valid(item) for item in score) and all(isinstance(program.get(key), str) and program[key].strip() for key in ["rationale", "surrender_condition"])
ranked = []
if shape:
    for item in portfolio["public_candidates"]:
        candidate = item["candidate"]
        ranked.append((tuple(value(expr, candidate, item["public_evaluation"]["passed"]) for expr in score), candidate["candidate_id"]))
selected = min(ranked)[1] if ranked else None
passed = bool(selected and world["candidate_evaluations"][selected]["passed"])
print(json.dumps({"passed": passed, "selected": selected}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def program_seed(root: Path, subject: dict[str, Any], portfolio: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "program-seed"
    seed.mkdir()
    stub = {
        "program_id": "selector-unrevised",
        "score": [{"op": "candidate-id"}],
        "rationale": "Initial stable ordering only.",
        "surrender_condition": "Replace when comparative consequence shows it harmful.",
    }
    files = {
        "subject-position.json": base.active_position(subject),
        "bound-training-portfolio.json": portfolio,
        "comparative-consequence.json": world,
        "selection-context.json": SELECTION_CONTEXT,
        "expression-grammar.json": GRAMMAR,
        "selector-program.json": stub,
        "mutation-envelope.json": {"editable": ["selector-program.json"], "immutable": ["subject-position.json", "bound-training-portfolio.json", "comparative-consequence.json", "selection-context.json", "expression-grammar.json", "check_program.py"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_program.py").write_text(PROGRAM_CHECKER)
    (seed / "README.md").write_text("Author selector-program.json from the retained comparative consequence. No named derived feature is supplied. Use only the total expression grammar, run python3 check_program.py, edit one file, inspect the exact diff, and report truthfully.\n")
    return seed


def run_program_actor(context, p82, root: Path, subject: dict[str, Any], portfolio: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "selector-program-author"
    seed = program_seed(root, subject, portfolio, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, PROGRAM_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        program = json.loads((workspace / "selector-program.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        program = None
        immutable_ok = False
    decision = program_select(program, portfolio, SELECTION_CONTEXT) if valid_program(program) else None
    selected = decision["selected_candidate"]["candidate_id"] if decision else None
    valid = bool(decision and immutable_ok and world["candidate_evaluations"][selected]["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["selector-program.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0146-bound-actor-authored-selector-program", "source_subject_digest": subject["artifact_digest"], "cause_world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "grammar_version": PROGRAM_VERSION, "program": program, "training_decision": decision}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-selector-program.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "program": program, "decision": decision, "binding": binding}


def bind_program_selection(p82, subject: dict[str, Any], binding: dict[str, Any], portfolio: dict[str, Any], role: str) -> dict[str, Any]:
    decision = program_select(binding["program"], portfolio, SELECTION_CONTEXT)
    body = {"authority": "ot-0146-bound-program-selection", "role": role, "source_subject_digest": subject["artifact_digest"], "program_binding_digest": binding["binding_digest"], "portfolio_binding_digest": portfolio["binding_digest"], "context": SELECTION_CONTEXT, "decision": decision}
    return {**body, "binding_digest": p82.digest(body)}


def install_program(p82, subject: dict[str, Any], binding: dict[str, Any], selection: dict[str, Any], world: dict[str, Any], reserve: dict[str, Any], recovery: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {"authority": "ot-0146-selector-program-capability", "program_binding_digest": binding["binding_digest"], "program": binding["program"], "held_out_selection_digest": selection["binding_digest"], "held_out_world_receipt_digest": world["receipt_digest"], "reserve_floor_digest": p82.digest(reserve), "ordinary_recovery_floor_digest": p82.digest(recovery)}
    capability = {**body, "capability_digest": p82.digest(body)}
    receipt_body = {"authority": "ot-0146-selector-program-installation", "source_subject_digest": subject["artifact_digest"], "capability_digest": capability["capability_digest"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["constitutional_selector_program_capabilities"] = [*child.get("constitutional_selector_program_capabilities", []), capability]
    child["constitutional_selector_program_installation_receipts"] = [*child.get("constitutional_selector_program_installation_receipts", []), receipt]
    question = "Whether the actor-authored selector program transfers beyond deadline recovery remains unresolved."
    opening = "Open selector-program-reuse-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening}
    child["unresolved"] = question
    return p82.seal(child), receipt


def reuse_seed(root: Path, subject: dict[str, Any], capability: dict[str, Any], portfolio: dict[str, Any]) -> Path:
    seed = root / "reuse-seed"
    seed.mkdir()
    files = {
        "subject-position.json": base.active_position(subject),
        "selector-program-capability.json": capability,
        "bound-portfolio.json": portfolio,
        "selection-context.json": SELECTION_CONTEXT,
        "program-reuse.json": {"action": "surrender", "program_digest": capability["capability_digest"], "rationale": "Inspect retained program."},
        "mutation-envelope.json": {"editable": ["program-reuse.json"], "immutable": ["subject-position.json", "selector-program-capability.json", "bound-portfolio.json", "selection-context.json"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Authorize reuse of the exact retained selector program on this new portfolio. Edit only program-reuse.json, preserve the exact capability, inspect the diff, and report truthfully.\n")
    return seed


def run_reuse_actor(context, p82, root: Path, subject: dict[str, Any], capability: dict[str, Any], portfolio: dict[str, Any]) -> dict[str, Any]:
    label = "selector-program-reuse"
    seed = reuse_seed(root, subject, capability, portfolio)
    output, base_audit, workspace, _ = context.run_actor(label, seed, REUSE_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        action = json.loads((workspace / "program-reuse.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        action = None
        immutable_ok = False
    valid = bool(action and set(action) == {"action", "program_digest", "rationale"} and action["action"] == "reuse" and action["program_digest"] == capability["capability_digest"] and prior131.valid_text(action["rationale"]) and immutable_ok)
    audit = context.audit_actor(label, output, base_audit, valid, ["program-reuse.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0146-bound-selector-program-reuse", "source_subject_digest": subject["artifact_digest"], "capability_digest": capability["capability_digest"], "portfolio_binding_digest": portfolio["binding_digest"], "actor_patch_digest": audit["patch_digest"], "action": action}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "action": action, "binding": binding}


def seal_final(p82, subject: dict[str, Any], reuse: dict[str, Any], selection: dict[str, Any], world: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {"authority": "ot-0146-selector-program-reuse-transition", "source_subject_digest": subject["artifact_digest"], "reuse_binding_digest": reuse["binding_digest"], "selection_binding_digest": selection["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["constitutional_selector_program_reuse_receipts"] = [*child.get("constitutional_selector_program_reuse_receipts", []), receipt]
    question = "Which materially different world can test transfer of actor-authored selector semantics remains unresolved."
    opening = "Open actor-selector-cross-world-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = question
    return p82.seal(child), receipt


def preflight(p82, parent: dict[str, Any], training: dict[str, Any]) -> dict[str, Any]:
    fixture = {"program_id": "selector-envelope-limit", "score": [
        {"op": "not", "arg": {"op": "public-pass"}},
        {"op": "gt", "left": {"op": "simulated-at-envelope-maximum"}, "right": {"op": "context", "key": "hard_deadline"}},
        {"op": "strategy-field-count"},
        {"op": "candidate-id"},
    ], "rationale": "Prefer passing candidates whose projected output respects the hard limit.", "surrender_condition": "Surrender if this relation fails held-out consequence."}
    decision = program_select(fixture, training["first_portfolio"]["binding"], SELECTION_CONTEXT)
    selected = decision["selected_candidate"]["candidate_id"]
    reserve, recovery = previous.floors(p82, parent)
    with tempfile.TemporaryDirectory() as directory:
        seed = program_seed(Path(directory), parent, training["first_portfolio"]["binding"], training["first_world"])
        files = sorted(path.name for path in seed.iterdir() if path.is_file())
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "training_exact_contradiction": training["transferred_priority_correction_passed"] and not training["first_world"]["selected_results"]["active"]["passed"],
        "grammar_has_no_named_features": GRAMMAR["named_derived_features"] == [],
        "fixture_valid_and_selects_passing": valid_program(fixture) and training["first_world"]["candidate_evaluations"][selected]["passed"],
        "floors": reserve["passed"] and reserve["distinguishing_count"] == 9 and recovery["passed"] and recovery["shifted_pass_count"] == 3,
        "schemas_present": PROGRAM_SCHEMA.is_file() and REUSE_SCHEMA.is_file() and p82base.PORTFOLIO_SCHEMA.is_file(),
        "seed_complete": files == ["README.md", "bound-training-portfolio.json", "check_program.py", "comparative-consequence.json", "expression-grammar.json", "mutation-envelope.json", "selection-context.json", "selector-program.json", "subject-position.json"],
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "fixture_program": fixture, "fixture_decision": decision, "reserve_floor": reserve, "ordinary_recovery_floor": recovery}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0146").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0145", "open-subject-with-corrigible-cross-domain-selector.json")
    training = load_artifact(p82, repo, store, "OT-0145", "contradiction-corrected-transferred-priority-aggregate.json")
    old_subject = load_artifact(p82, repo, store, "OT-0144", "open-subject-with-cross-domain-recovery-capability.json")
    fixtures = preflight(p82, parent, training)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0146 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    program_root = run / "program-authorship"
    program_root.mkdir()
    authored = run_program_actor(context, p82, program_root, parent, training["first_portfolio"]["binding"], training["first_world"])

    held_root = run / "held-out-portfolio"
    held_root.mkdir()
    held = previous.run_portfolio_actor(context, p82, held_root, parent, previous.cases("public-held", [40, 64]), 3) if authored["binding"] else None
    active = current = old = held_world = None
    reserve, recovery = previous.floors(p82, parent)
    installed = parent
    installation = None
    if held and held["binding"]:
        active = bind_program_selection(p82, parent, authored["binding"], held["binding"], "actor-program")
        current = previous.bind_selection(p82, parent, parent["constitutional_amendment_selector"], held["binding"], "current-v3")
        old = previous.bind_selection(p82, parent, old_subject["constitutional_amendment_selector"], held["binding"], "pre-correction-v2")
        held_world = previous.world_receipt(p82, held["binding"], [active, current, old], previous.cases("hidden-held", [88, 120, 152, 64]), "ot-0146-held-out-program-world")
        (held_root / "sealed-held-out-world.json").write_text(json.dumps(held_world, indent=2, sort_keys=True) + "\n")
        (run / "reserve-floor.json").write_text(json.dumps(reserve, indent=2, sort_keys=True) + "\n")
        (run / "ordinary-recovery-floor.json").write_text(json.dumps(recovery, indent=2, sort_keys=True) + "\n")
        if held_world["selected_results"]["actor-program"]["passed"] and held_world["selected_results"]["current-v3"]["passed"] and not held_world["selected_results"]["pre-correction-v2"]["passed"] and reserve["passed"] and recovery["passed"]:
            installed, installation = install_program(p82, parent, authored["binding"], active, held_world, reserve, recovery)

    later_root = run / "later-portfolio"
    later_root.mkdir()
    later = previous.run_portfolio_actor(context, p82, later_root, installed, previous.cases("public-later", [24, 56]), 4) if installation else None
    reuse_root = run / "program-reuse"
    reuse_root.mkdir()
    capability = installed.get("constitutional_selector_program_capabilities", [None])[-1]
    reuse = run_reuse_actor(context, p82, reuse_root, installed, capability, later["binding"]) if later and later["binding"] else None
    reuse_selection = reuse_world = old_control = control_world = None
    final = installed
    transition = None
    if reuse and reuse["binding"]:
        program_binding = {"binding_digest": capability["program_binding_digest"], "program": capability["program"]}
        reuse_selection = bind_program_selection(p82, installed, program_binding, later["binding"], "reused-program")
        old_control = previous.bind_selection(p82, installed, old_subject["constitutional_amendment_selector"], later["binding"], "pre-correction-control")
        reuse_world = previous.world_receipt(p82, later["binding"], [reuse_selection], previous.cases("hidden-reuse", [72, 104, 136, 64]), "ot-0146-later-program-reuse-world")
        (reuse_root / "sealed-reuse-world.json").write_text(json.dumps(reuse_world, indent=2, sort_keys=True) + "\n")
        if reuse_world["selected_results"]["reused-program"]["passed"]:
            final, transition = seal_final(p82, installed, reuse["binding"], reuse_selection, reuse_world)
        control_world = previous.world_receipt(p82, later["binding"], [old_control], previous.cases("hidden-reuse", [72, 104, 136, 64]), "ot-0146-post-seal-old-selector-control")
        (run / "post-seal-old-selector-control.json").write_text(json.dumps(control_world, indent=2, sort_keys=True) + "\n")

    checks = {
        "four_fresh_actors": bool(authored["binding"] and held and held["binding"] and later and later["binding"] and reuse and reuse["binding"]),
        "actor_authored_total_program": bool(authored["binding"] and valid_program(authored["program"])),
        "no_named_feature_vocabulary": GRAMMAR["named_derived_features"] == [],
        "held_out_program_matches_current": bool(held_world and held_world["selected_results"]["actor-program"]["passed"] and held_world["selected_results"]["actor-program"]["shifted_pass_count"] == 3 and held_world["selected_results"]["current-v3"]["passed"]),
        "held_out_beats_old": bool(held_world and not held_world["selected_results"]["pre-correction-v2"]["passed"] and held_world["selected_results"]["pre-correction-v2"]["shifted_pass_count"] == 0),
        "both_prior_floors": reserve["passed"] and reserve["distinguishing_count"] == 9 and recovery["passed"] and recovery["shifted_pass_count"] == 3,
        "program_installed": bool(installation and runtime.identity_conforms(installed) and capability["program"] == authored["program"]),
        "later_exact_reuse": bool(reuse_world and reuse_world["selected_results"]["reused-program"]["passed"] and reuse_world["selected_results"]["reused-program"]["shifted_pass_count"] == 3),
        "post_seal_old_control_fails": bool(control_world and not control_world["selected_results"]["pre-correction-control"]["passed"] and control_world["selected_results"]["pre-correction-control"]["shifted_pass_count"] == 0),
        "capability_roles_retained": bool(final.get("adaptive_contact_strategy_capabilities") and final.get("recovery_cadence_capabilities") and final.get("deadline_recovery_capabilities") and final.get("constitutional_selector_program_capabilities")),
        "readable_selector_retained": final.get("constitutional_amendment_selector") == parent.get("constitutional_amendment_selector"),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open" and "cross-world" in final["continuation"]["next_opening"],
    }
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0146-actor-authored-selector-program-driver", "source_subject_digest": parent["artifact_digest"], "program_authorship": p82.compact(authored), "held_out_portfolio": p82.compact(held) if held else None, "active_program_selection": active, "current_v3_selection": current, "old_v2_selection": old, "held_out_world": held_world, "reserve_floor": reserve, "ordinary_recovery_floor": recovery, "installation_receipt": installation, "later_portfolio": p82.compact(later) if later else None, "reuse": p82.compact(reuse) if reuse else None, "reuse_selection": reuse_selection, "reuse_world": reuse_world, "reuse_transition": transition, "post_seal_old_control": control_world, "checks": checks, "actor_authored_selector_program_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum(item is not None for item in [authored, held, later, reuse]), "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
