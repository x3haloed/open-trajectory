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
BASE_PATH = ROOT / "ot_0144_exact_recovery_portfolio_reconstruction.py"
BASE_SHA256 = "2c7ce88af8652659473cf7710c137556c7e7f9bcf07ed83ebf8a85ad4dac5026"
PARENT_DIGEST = "e61e5291641c54e0ec4ce1794c1fa43e5a0ac968f73f1cb31be0c3e2ff3e3510"
LANGUAGE_VERSION = "ot-0145-deadline-recovery-v1"
SELECTOR_VERSION = "ot-0145-constraint-aware-selector-v3"
DEADLINE = 64
FEATURES = ["public_pass", "constraint_compatible", "scale_invariant", "lower_mutation_surface", "stable_id"]
SELECTOR_SCHEMA = REPO / "spec/ot-0145-selector-correction.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0144 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0145_frozen_ot0144", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior = previous.prior
ot142 = prior.prior
prior131 = prior.prior.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return prior.load_artifact(p82, repo, store, experiment, manifest)


def cases(prefix: str, maxima: list[int]) -> list[dict[str, Any]]:
    return [{
        "case_id": f"{prefix}-{index + 1}-max-{maximum}",
        "observed_latencies": [maximum // 4, maximum // 2, (3 * maximum) // 4, maximum],
        "deadline": DEADLINE,
        "required_delay": min(maximum, DEADLINE),
        "shifted": maximum > DEADLINE,
    } for index, maximum in enumerate(maxima)]


def valid_candidate(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or set(candidate) != {"candidate_id", "strategy", "rationale", "surrender_condition"}:
        return False
    if not isinstance(candidate["candidate_id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", candidate["candidate_id"]):
        return False
    if not prior131.valid_text(candidate["rationale"]) or not prior131.valid_text(candidate["surrender_condition"]):
        return False
    strategy = candidate["strategy"]
    kind = strategy.get("kind") if isinstance(strategy, dict) else None
    if kind == "latency-relative":
        return set(strategy) == {"kind", "factor"} and strategy["factor"] == 1
    if kind == "deadline-capped":
        return set(strategy) == {"kind", "factor", "deadline"} and strategy["factor"] == 1 and strategy["deadline"] == DEADLINE
    return False


def scheduled(candidate: dict[str, Any], case: dict[str, Any]) -> int:
    observed = candidate["strategy"]["factor"] * max(case["observed_latencies"])
    return min(observed, candidate["strategy"]["deadline"]) if candidate["strategy"]["kind"] == "deadline-capped" else observed


def evaluate(candidate: dict[str, Any], world_cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [{
        "case_id": case["case_id"],
        "shifted": case["shifted"],
        "scheduled_delay": scheduled(candidate, case),
        "required_delay": case["required_delay"],
        "deadline": case["deadline"],
        "passed": scheduled(candidate, case) == case["required_delay"],
    } for case in world_cases]
    shifted = [row for row in rows if row["shifted"]]
    controls = [row for row in rows if not row["shifted"]]
    return {
        "candidate_id": candidate["candidate_id"],
        "strategy": candidate["strategy"],
        "cases": rows,
        "shifted_count": len(shifted),
        "shifted_pass_count": sum(row["passed"] for row in shifted),
        "control_count": len(controls),
        "control_pass_count": sum(row["passed"] for row in controls),
        "passed": all(row["passed"] for row in rows),
    }


def validate_portfolio(portfolio: Any, public_cases: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    if not isinstance(portfolio, dict) or set(portfolio) != {"question", "candidates"} or not prior131.valid_text(portfolio.get("question")):
        return False, []
    candidates = portfolio.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2 or not all(valid_candidate(item) for item in candidates):
        return False, []
    if len({item["candidate_id"] for item in candidates}) != 2 or {item["strategy"]["kind"] for item in candidates} != {"latency-relative", "deadline-capped"}:
        return False, []
    evaluations = [evaluate(item, public_cases) for item in candidates]
    return all(item["passed"] for item in evaluations), evaluations


def derived_features(candidate: dict[str, Any], public_pass: bool) -> dict[str, Any]:
    capped = candidate["strategy"]["kind"] == "deadline-capped"
    return {
        "public_pass": public_pass,
        "constraint_compatible": capped,
        "scale_invariant": not capped,
        "mutation_surface": 2 if capped else 1,
        "candidate_id": candidate["candidate_id"],
    }


def select(selector: dict[str, Any], portfolio: dict[str, Any]) -> dict[str, Any]:
    ranked = []
    for item in portfolio["public_candidates"]:
        feature = derived_features(item["candidate"], item["public_evaluation"]["passed"])
        values = {
            "public_pass": 0 if feature["public_pass"] else 1,
            "constraint_compatible": 0 if feature["constraint_compatible"] else 1,
            "scale_invariant": 0 if feature["scale_invariant"] else 1,
            "lower_mutation_surface": feature["mutation_surface"],
            "stable_id": feature["candidate_id"],
        }
        ranked.append({"candidate": item["candidate"], "features": feature, "rank_key": [values[key] for key in selector["priority"]]})
    selected = min(ranked, key=lambda row: tuple(row["rank_key"]))
    return {"selected_candidate": selected["candidate"], "selected_features": selected["features"], "ranked": sorted(ranked, key=lambda row: tuple(row["rank_key"]))}


PORTFOLIO_CHECKER = '''import json
from pathlib import Path

portfolio = json.loads(Path("amendment-portfolio.json").read_text())
candidates = portfolio.get("candidates", [])
ids = [item.get("candidate_id") for item in candidates]
pure = next((item for item in candidates if item.get("strategy", {}).get("kind") == "latency-relative"), None)
capped = next((item for item in candidates if item.get("strategy", {}).get("kind") == "deadline-capped"), None)
passed = bool(len(candidates) == 2 and len(set(ids)) == 2 and pure and capped and pure["strategy"].get("factor") == 1 and capped["strategy"].get("factor") == 1 and capped["strategy"].get("deadline") == 64 and all(isinstance(item.get("rationale"), str) and item["rationale"].strip() and isinstance(item.get("surrender_condition"), str) and item["surrender_condition"].strip() for item in candidates))
print(json.dumps({"passed": passed, "candidate_ids": ids}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def portfolio_seed(root: Path, subject: dict[str, Any], public_cases: list[dict[str, Any]], ordinal: int) -> Path:
    seed = root / "portfolio-seed"
    seed.mkdir()
    files = {
        "subject-position.json": base.active_position(subject),
        "constitutional-selector.json": subject["constitutional_amendment_selector"],
        "deadline-recovery-language.json": {
            "language_version": LANGUAGE_VERSION,
            "hard_deadline": DEADLINE,
            "required_families": ["latency-relative", "deadline-capped"],
            "derived_features": {"latency-relative": {"scale_invariant": True, "constraint_compatible": False, "mutation_surface": 1}, "deadline-capped": {"scale_invariant": False, "constraint_compatible": True, "mutation_surface": 2}},
            "actor_does_not_author_features": True,
        },
        "public-deadline-cases.json": public_cases,
        "amendment-portfolio.json": {"question": f"Which deadline recovery amendment should govern portfolio {ordinal}?", "candidates": []},
        "mutation-envelope.json": {"editable": ["amendment-portfolio.json"], "immutable": ["subject-position.json", "constitutional-selector.json", "deadline-recovery-language.json", "public-deadline-cases.json", "check_portfolio.py"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_portfolio.py").write_text(PORTFOLIO_CHECKER)
    (seed / "README.md").write_text("Author one factor-one amendment in each deadline recovery family. Run python3 check_portfolio.py, edit only amendment-portfolio.json, inspect the exact diff, and report truthfully.\n")
    return seed


def run_portfolio_actor(context, p82, root: Path, subject: dict[str, Any], public_cases: list[dict[str, Any]], ordinal: int) -> dict[str, Any]:
    label = f"deadline-portfolio-{ordinal}-author"
    seed = portfolio_seed(root, subject, public_cases, ordinal)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ot142.PORTFOLIO_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        portfolio = json.loads((workspace / "amendment-portfolio.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        portfolio = None
        immutable_ok = False
    valid, evaluations = validate_portfolio(portfolio, public_cases)
    audit = context.audit_actor(label, output, base_audit, bool(valid and immutable_ok), ["amendment-portfolio.json"])
    binding = None
    if valid and immutable_ok and prior131.audit_accepted(audit):
        body = {"authority": "ot-0145-bound-deadline-amendment-portfolio", "source_subject_digest": subject["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "portfolio": portfolio, "public_candidates": [{"candidate": candidate, "public_evaluation": evaluation} for candidate, evaluation in zip(portfolio["candidates"], evaluations)]}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-deadline-portfolio.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "portfolio": portfolio, "binding": binding}


def bind_selection(p82, subject: dict[str, Any], selector: dict[str, Any], portfolio: dict[str, Any], role: str) -> dict[str, Any]:
    decision = select(selector, portfolio)
    body = {"authority": "ot-0145-bound-deadline-constitutional-selection", "role": role, "source_subject_digest": subject["artifact_digest"], "selector_digest": selector["selector_digest"], "portfolio_binding_digest": portfolio["binding_digest"], "decision": decision}
    return {**body, "binding_digest": p82.digest(body)}


def world_receipt(p82, portfolio: dict[str, Any], selections: list[dict[str, Any]], world_cases: list[dict[str, Any]], authority: str) -> dict[str, Any]:
    evaluations = {candidate["candidate_id"]: evaluate(candidate, world_cases) for candidate in portfolio["portfolio"]["candidates"]}
    body = {"authority": authority, "portfolio_binding_digest": portfolio["binding_digest"], "selection_binding_digests": [item["binding_digest"] for item in selections], "cases_digest": p82.digest(world_cases), "candidate_evaluations": evaluations, "selected_results": {item["role"]: evaluations[item["decision"]["selected_candidate"]["candidate_id"]] for item in selections}}
    return {**body, "receipt_digest": p82.digest(body)}


def retain_failure(p82, subject: dict[str, Any], portfolio: dict[str, Any], selection: dict[str, Any], world: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected_id = selection["decision"]["selected_candidate"]["candidate_id"]
    body = {"authority": "ot-0145-retained-transferred-priority-contradiction", "source_subject_digest": subject["artifact_digest"], "portfolio_binding_digest": portfolio["binding_digest"], "selection_binding_digest": selection["binding_digest"], "world_receipt_digest": world["receipt_digest"], "selected_candidate_id": selected_id, "selected_result": world["candidate_evaluations"][selected_id], "alternative_results": {key: value for key, value in world["candidate_evaluations"].items() if key != selected_id}}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["transferred_priority_contradictions"] = [*child.get("transferred_priority_contradictions", []), receipt]
    child["pending_constitutional_selector_correction"] = receipt
    question = "Whether deadline compatibility should constrain the transferred scale-invariance priority remains unresolved."
    opening = "Open constraint-selector-correction-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening}
    child["unresolved"] = question
    return p82.seal(child), receipt


SELECTOR_CHECKER = '''import json
from pathlib import Path

priority = json.loads(Path("selector-semantics.json").read_text()).get("priority", [])
portfolio = json.loads(Path("bound-portfolio.json").read_text())
world = json.loads(Path("comparative-consequence.json").read_text())
features = []
for item in portfolio["public_candidates"]:
    candidate = item["candidate"]
    capped = candidate["strategy"]["kind"] == "deadline-capped"
    features.append({"candidate_id": candidate["candidate_id"], "public_pass": item["public_evaluation"]["passed"], "constraint_compatible": capped, "scale_invariant": not capped, "mutation_surface": 2 if capped else 1})
valid = len(priority) == 5 and set(priority) == {"public_pass", "constraint_compatible", "scale_invariant", "lower_mutation_surface", "stable_id"}
def key(row):
    values = {"public_pass": 0 if row["public_pass"] else 1, "constraint_compatible": 0 if row["constraint_compatible"] else 1, "scale_invariant": 0 if row["scale_invariant"] else 1, "lower_mutation_surface": row["mutation_surface"], "stable_id": row["candidate_id"]}
    return tuple(values[item] for item in priority)
selected = min(features, key=key)["candidate_id"] if valid else None
passed = bool(valid and world["candidate_evaluations"][selected]["passed"])
print(json.dumps({"passed": passed, "selected": selected}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def selector_seed(root: Path, subject: dict[str, Any], portfolio: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "selector-seed"
    seed.mkdir()
    files = {"subject-position.json": base.active_position(subject), "inherited-selector.json": subject["constitutional_amendment_selector"], "bound-portfolio.json": portfolio, "comparative-consequence.json": world, "selector-semantics.json": {"priority": subject["constitutional_amendment_selector"]["priority"]}, "mutation-envelope.json": {"editable": ["selector-semantics.json"], "immutable": ["subject-position.json", "inherited-selector.json", "bound-portfolio.json", "comparative-consequence.json", "check_selector.py"]}}
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_selector.py").write_text(SELECTOR_CHECKER)
    (seed / "README.md").write_text("Correct only selector priority from the exact deadline contradiction. The published feature vocabulary now includes constraint_compatible. Run python3 check_selector.py, inspect the exact diff, and report truthfully.\n")
    return seed


def make_selector(p82, priority: list[str], parent: dict[str, Any], cause: str) -> dict[str, Any]:
    body = {"selector_version": SELECTOR_VERSION, "priority": priority, "feature_authority": "mechanically-derived-from-bound-amendment-strategy-and-deadline", "parent_selector_digest": parent["selector_digest"], "cause_receipt_digest": cause}
    return {**body, "selector_digest": p82.digest(body)}


def run_selector_actor(context, p82, root: Path, subject: dict[str, Any], portfolio: dict[str, Any], world: dict[str, Any], inherited: dict[str, Any]) -> dict[str, Any]:
    label = "constraint-selector-corrector"
    seed = selector_seed(root, subject, portfolio, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, SELECTOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        semantics = json.loads((workspace / "selector-semantics.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        semantics = None
        immutable_ok = False
    priority = semantics.get("priority") if isinstance(semantics, dict) and set(semantics) == {"priority"} else None
    compiled = make_selector(p82, priority, inherited, world["receipt_digest"]) if isinstance(priority, list) and len(priority) == 5 and set(priority) == set(FEATURES) else None
    new_decision = select(compiled, portfolio) if compiled else None
    old_decision = select(inherited, portfolio)
    valid = bool(compiled and immutable_ok and world["candidate_evaluations"][new_decision["selected_candidate"]["candidate_id"]]["passed"] and not world["candidate_evaluations"][old_decision["selected_candidate"]["candidate_id"]]["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["selector-semantics.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0145-constraint-corrected-selector-binding", "source_subject_digest": subject["artifact_digest"], "parent_selector_digest": inherited["selector_digest"], "cause_world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "actor_semantics": semantics, "compiled_selector": compiled, "retrospective_decision": new_decision, "unchanged_decision": old_decision}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-constraint-selector.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "semantics": semantics, "binding": binding}


def install_selector(p82, subject: dict[str, Any], binding: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {"authority": "ot-0145-selector-feature-expansion", "source_subject_digest": subject["artifact_digest"], "binding_digest": binding["binding_digest"], "parent_selector_digest": binding["parent_selector_digest"], "corrected_selector_digest": binding["compiled_selector"]["selector_digest"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["constitutional_amendment_selector"] = binding["compiled_selector"]
    child["constitutional_amendment_selector_history"] = [*child["constitutional_amendment_selector_history"], receipt]
    child["pending_constitutional_selector_correction"] = None
    return p82.seal(child), receipt


def install_capped(p82, subject: dict[str, Any], portfolio: dict[str, Any], selection: dict[str, Any], world: dict[str, Any], reserve_floor: dict[str, Any], recovery_floor: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = selection["decision"]["selected_candidate"]
    parent_constitution = subject["developmental_constitution"]
    constitution_body = {key: value for key, value in parent_constitution.items() if key != "constitution_digest"}
    constitution_body.update({"constitution_version": "ot-0145-contextual-recovery-constitution-v1", "active_deadline_recovery_strategy": candidate["strategy"], "parent_constitution_digest": parent_constitution["constitution_digest"], "cause_receipt_digest": world["receipt_digest"]})
    constitution = {**constitution_body, "constitution_digest": p82.digest(constitution_body)}
    body = {"authority": "ot-0145-deadline-recovery-capability", "language_version": LANGUAGE_VERSION, "candidate_id": candidate["candidate_id"], "strategy": candidate["strategy"], "portfolio_binding_digest": portfolio["binding_digest"], "selection_binding_digest": selection["binding_digest"], "world_receipt_digest": world["receipt_digest"], "reserve_floor_digest": p82.digest(reserve_floor), "ordinary_recovery_floor_digest": p82.digest(recovery_floor), "selector_digest": subject["constitutional_amendment_selector"]["selector_digest"], "constitution_digest": constitution["constitution_digest"]}
    capability = {**body, "capability_digest": p82.digest(body)}
    receipt_body = {"authority": "ot-0145-contextual-recovery-installation", "source_subject_digest": subject["artifact_digest"], "capability_digest": capability["capability_digest"], "constitution_digest": constitution["constitution_digest"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["developmental_constitution"] = constitution
    child["deadline_recovery_capabilities"] = [*child.get("deadline_recovery_capabilities", []), capability]
    child["contextual_recovery_installation_receipts"] = [*child.get("contextual_recovery_installation_receipts", []), receipt]
    question = "Whether deadline-capped recovery remains valid on new constrained histories while ordinary recovery stays available remains unresolved."
    opening = "Open deadline-recovery-reuse-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening}
    child["unresolved"] = question
    return p82.seal(child), receipt


def reuse_seed(root: Path, subject: dict[str, Any], capability: dict[str, Any]) -> Path:
    seed = root / "reuse-seed"
    seed.mkdir()
    files = {"subject-position.json": base.active_position(subject), "deadline-recovery-capability.json": capability, "developmental-constitution.json": subject["developmental_constitution"], "reuse-action.json": {"action": "surrender", "strategy": capability["strategy"], "rationale": "Inspect exact retained constrained strategy."}, "mutation-envelope.json": {"editable": ["reuse-action.json"], "immutable": ["subject-position.json", "deadline-recovery-capability.json", "developmental-constitution.json"]}}
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Reuse the exact deadline recovery strategy. Preserve strategy and constitution bytes, edit only reuse-action.json, inspect the exact diff, and report truthfully.\n")
    return seed


def run_reuse_actor(context, p82, root: Path, subject: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    label = "deadline-recovery-reuse"
    seed = reuse_seed(root, subject, capability)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ot142.REUSE_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        action = json.loads((workspace / "reuse-action.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        action = None
        immutable_ok = False
    valid = bool(action and set(action) == {"action", "strategy", "rationale"} and action["action"] == "reuse" and action["strategy"] == capability["strategy"] and prior131.valid_text(action["rationale"]) and immutable_ok)
    audit = context.audit_actor(label, output, base_audit, valid, ["reuse-action.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0145-bound-deadline-recovery-reuse", "source_subject_digest": subject["artifact_digest"], "capability_digest": capability["capability_digest"], "actor_patch_digest": audit["patch_digest"], "action": action}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "action": action, "binding": binding}


def seal_final(p82, subject: dict[str, Any], binding: dict[str, Any], evaluation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {"authority": "ot-0145-contextual-recovery-reuse-transition", "source_subject_digest": subject["artifact_digest"], "reuse_binding_digest": binding["binding_digest"], "evaluation_digest": p82.digest(evaluation)}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["contextual_recovery_reuse_receipts"] = [*child.get("contextual_recovery_reuse_receipts", []), receipt]
    question = "Which materially different world should the continuing subject contact next, while retaining corrigible constitutional selection, remains unresolved."
    opening = "Open cross-world-frontier-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = question
    return p82.seal(child), receipt


def representative_portfolio() -> dict[str, Any]:
    return {"question": "Which constrained recovery amendment should govern?", "candidates": [
        {"candidate_id": "pure-relative", "strategy": {"kind": "latency-relative", "factor": 1}, "rationale": "Continue proportional recovery.", "surrender_condition": "Surrender if deadline violated."},
        {"candidate_id": "deadline-capped", "strategy": {"kind": "deadline-capped", "factor": 1, "deadline": DEADLINE}, "rationale": "Respect the independent deadline.", "surrender_condition": "Surrender if capped recovery fails."},
    ]}


def floors(p82, parent: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    adaptive = parent["adaptive_contact_strategy_capabilities"][-1]
    reserve_candidate = {"candidate_id": adaptive["candidate_id"], "strategy": adaptive["strategy"], "rationale": "retained", "surrender_condition": "retained"}
    reserve = ot142.candidate_evaluation(p82, parent["contact_program_capabilities"][-1]["program"], reserve_candidate, ot142.prior.previous.bases_for(12, 256), 256)
    recovery_cap = parent["recovery_cadence_capabilities"][-1]
    recovery_candidate = {"candidate_id": recovery_cap["candidate_id"], "strategy": recovery_cap["strategy"], "rationale": "retained", "surrender_condition": "retained"}
    recovery = prior.evaluate(recovery_candidate, prior.recovery_cases("ordinary-floor", [160, 192, 224, 32]))
    return reserve, recovery


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    portfolio = representative_portfolio()
    public = cases("public", [32, 64])
    valid, evaluations = validate_portfolio(portfolio, public)
    binding = {"public_candidates": [{"candidate": candidate, "public_evaluation": evaluation} for candidate, evaluation in zip(portfolio["candidates"], evaluations)]}
    inherited = parent["constitutional_amendment_selector"]
    corrected = make_selector(p82, ["public_pass", "constraint_compatible", "scale_invariant", "lower_mutation_surface", "stable_id"], inherited, "fixture")
    old = select(inherited, binding)
    new = select(corrected, binding)
    hidden = {item["candidate_id"]: evaluate(item, cases("hidden", [96, 128, 160, 64])) for item in portfolio["candidates"]}
    reserve, recovery = floors(p82, parent)
    with tempfile.TemporaryDirectory() as directory:
        seed = portfolio_seed(Path(directory), parent, public, 1)
        files = sorted(path.name for path in seed.iterdir() if path.is_file())
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "portfolio_valid": valid and all(item["passed"] for item in evaluations),
        "inherited_selects_harmful_pure": old["selected_candidate"]["strategy"]["kind"] == "latency-relative" and not hidden[old["selected_candidate"]["candidate_id"]]["passed"],
        "corrected_selects_capped": new["selected_candidate"]["strategy"]["kind"] == "deadline-capped" and hidden[new["selected_candidate"]["candidate_id"]]["passed"],
        "reserve_floor": reserve["passed"] and reserve["distinguishing_count"] == 9,
        "ordinary_recovery_floor": recovery["passed"] and recovery["shifted_pass_count"] == 3,
        "schemas_present": ot142.PORTFOLIO_SCHEMA.is_file() and SELECTOR_SCHEMA.is_file() and ot142.REUSE_SCHEMA.is_file(),
        "seed_complete": files == ["README.md", "amendment-portfolio.json", "check_portfolio.py", "constitutional-selector.json", "deadline-recovery-language.json", "mutation-envelope.json", "public-deadline-cases.json", "subject-position.json"],
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "old": old, "new": new, "hidden": hidden, "reserve_floor": reserve, "recovery_floor": recovery}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0145").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0144", "open-subject-with-cross-domain-recovery-capability.json")
    fixtures = preflight(p82, parent)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0145 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    inherited = parent["constitutional_amendment_selector"]
    first_root = run / "first-contradiction"
    first_root.mkdir()
    first = run_portfolio_actor(context, p82, first_root, parent, cases("public-a", [32, 64]), 1)
    first_selection = first_world = failure_receipt = None
    failure_subject = parent
    if first["binding"]:
        first_selection = bind_selection(p82, parent, inherited, first["binding"], "active")
        first_world = world_receipt(p82, first["binding"], [first_selection], cases("hidden-a", [96, 128, 160, 64]), "ot-0145-first-deadline-contradiction-world")
        (first_root / "sealed-contradiction-world.json").write_text(json.dumps(first_world, indent=2, sort_keys=True) + "\n")
        if not first_world["selected_results"]["active"]["passed"] and any(value["passed"] for key, value in first_world["candidate_evaluations"].items() if key != first_world["selected_results"]["active"]["candidate_id"]):
            failure_subject, failure_receipt = retain_failure(p82, parent, first["binding"], first_selection, first_world)
    correction_root = run / "selector-correction"
    correction_root.mkdir()
    correction = run_selector_actor(context, p82, correction_root, failure_subject, first["binding"], first_world, inherited) if failure_receipt else None
    corrected_subject = failure_subject
    correction_receipt = None
    if correction and correction["binding"]:
        corrected_subject, correction_receipt = install_selector(p82, failure_subject, correction["binding"])
    second_root = run / "held-out-contradiction"
    second_root.mkdir()
    second = run_portfolio_actor(context, p82, second_root, corrected_subject, cases("public-b", [48, 64]), 2) if correction_receipt else None
    active = control = held_world = None
    installed = corrected_subject
    installation = None
    reserve_floor, recovery_floor = floors(p82, parent)
    if second and second["binding"]:
        active = bind_selection(p82, corrected_subject, corrected_subject["constitutional_amendment_selector"], second["binding"], "active")
        control = bind_selection(p82, corrected_subject, inherited, second["binding"], "unchanged-control")
        held_world = world_receipt(p82, second["binding"], [active, control], cases("hidden-b", [80, 112, 144, 64]), "ot-0145-held-out-deadline-world")
        (second_root / "sealed-matched-world.json").write_text(json.dumps(held_world, indent=2, sort_keys=True) + "\n")
        (run / "reserve-floor.json").write_text(json.dumps(reserve_floor, indent=2, sort_keys=True) + "\n")
        (run / "ordinary-recovery-floor.json").write_text(json.dumps(recovery_floor, indent=2, sort_keys=True) + "\n")
        if held_world["selected_results"]["active"]["passed"] and not held_world["selected_results"]["unchanged-control"]["passed"] and reserve_floor["passed"] and recovery_floor["passed"]:
            installed, installation = install_capped(p82, corrected_subject, second["binding"], active, held_world, reserve_floor, recovery_floor)
    reuse_root = run / "later-deadline-reuse"
    reuse_root.mkdir()
    capability = installed.get("deadline_recovery_capabilities", [None])[-1]
    reuse = run_reuse_actor(context, p82, reuse_root, installed, capability) if installation else None
    reuse_world = None
    final = installed
    reuse_transition = None
    if reuse and reuse["binding"]:
        candidate = {"candidate_id": capability["candidate_id"], "strategy": capability["strategy"], "rationale": "retained", "surrender_condition": "retained"}
        reuse_world = evaluate(candidate, cases("reuse", [72, 104, 136, 64]))
        (reuse_root / "sealed-reuse-world.json").write_text(json.dumps(reuse_world, indent=2, sort_keys=True) + "\n")
        if reuse_world["passed"]:
            final, reuse_transition = seal_final(p82, installed, reuse["binding"], reuse_world)
    pure_control = evaluate(control["decision"]["selected_candidate"], cases("reuse", [72, 104, 136, 64])) if control else None
    if pure_control:
        (run / "post-seal-pure-relative-control.json").write_text(json.dumps(pure_control, indent=2, sort_keys=True) + "\n")
    checks = {
        "four_fresh_actors": bool(first["binding"] and correction and correction["binding"] and second and second["binding"] and reuse and reuse["binding"]),
        "transferred_priority_contradicted": bool(first_world and not first_world["selected_results"]["active"]["passed"] and first_selection["decision"]["selected_candidate"]["strategy"]["kind"] == "latency-relative"),
        "new_feature_compiled": bool(correction_receipt and "constraint_compatible" in corrected_subject["constitutional_amendment_selector"]["priority"] and corrected_subject["constitutional_amendment_selector"]["priority"].index("constraint_compatible") < corrected_subject["constitutional_amendment_selector"]["priority"].index("scale_invariant")),
        "held_out_active_beats_control": bool(held_world and held_world["selected_results"]["active"]["passed"] and held_world["selected_results"]["active"]["shifted_pass_count"] == 3 and not held_world["selected_results"]["unchanged-control"]["passed"] and held_world["selected_results"]["unchanged-control"]["shifted_pass_count"] == 0),
        "both_prior_floors": reserve_floor["passed"] and reserve_floor["distinguishing_count"] == 9 and recovery_floor["passed"] and recovery_floor["shifted_pass_count"] == 3,
        "contextual_capability_added": bool(installation and runtime.identity_conforms(installed) and capability["strategy"]["kind"] == "deadline-capped"),
        "later_reuse": bool(reuse_world and reuse_world["passed"] and reuse_world["shifted_pass_count"] == 3),
        "post_seal_pure_control_fails": bool(pure_control and not pure_control["passed"] and pure_control["shifted_pass_count"] == 0),
        "selector_erasure_reproduces_control": bool(second and select(inherited, second["binding"])["selected_candidate"] == control["decision"]["selected_candidate"]),
        "all_capability_roles_retained": bool(final.get("adaptive_contact_strategy_capabilities") and final.get("recovery_cadence_capabilities") and final.get("deadline_recovery_capabilities")),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open" and "materially different world" in final["continuation"]["next_opening"],
    }
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0145-contradiction-corrected-transferred-priority-driver", "source_subject_digest": parent["artifact_digest"], "first_portfolio": p82.compact(first), "first_selection": first_selection, "first_world": first_world, "failure_receipt": failure_receipt, "selector_correction": p82.compact(correction) if correction else None, "selector_correction_receipt": correction_receipt, "held_out_portfolio": p82.compact(second) if second else None, "active_selection": active, "unchanged_control_selection": control, "held_out_world": held_world, "reserve_floor": reserve_floor, "ordinary_recovery_floor": recovery_floor, "installation_receipt": installation, "later_reuse": p82.compact(reuse) if reuse else None, "later_reuse_world": reuse_world, "later_reuse_transition": reuse_transition, "post_seal_pure_control": pure_control, "checks": checks, "transferred_priority_correction_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum(item is not None for item in [first, correction, second, reuse]), "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
