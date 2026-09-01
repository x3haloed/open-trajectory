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
BASE_PATH = ROOT / "ot_0141_constitutional_transition_projection.py"
BASE_SHA256 = "515d9f2827604a5b7d25c7611ad67a06f33714938cba7d0b18c491a223afdb70"
PARENT_DIGEST = "11064b5e2a318b3acb78a3785f8de634e43c92dd4a23b22df6811449194fd6f6"
SELECTOR_VERSION = "ot-0142-constitutional-selector-v1"
CORRECTED_SELECTOR_VERSION = "ot-0142-constitutional-selector-v2"
STRATEGY_VERSION = "ot-0142-offset-strategy-v1"
PORTFOLIO_SCHEMA = REPO / "spec/ot-0142-amendment-portfolio.schema.json"
SELECTOR_SCHEMA = REPO / "spec/ot-0142-selector-correction.schema.json"
REUSE_SCHEMA = REPO / "spec/ot-0142-adaptive-reuse.schema.json"
FEATURES = ["public_pass", "scale_invariant", "lower_mutation_surface", "stable_id"]
INITIAL_PRIORITY = ["public_pass", "lower_mutation_surface", "scale_invariant", "stable_id"]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0141 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0142_frozen_ot0141", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior = previous.prior
prior135 = previous.prior135
prior131 = prior.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return prior135.load_json_artifact(p82, repo, store, experiment, manifest)


def make_selector(p82, priority: list[str], version: str, parent: str | None = None, cause: str | None = None) -> dict[str, Any]:
    body = {
        "selector_version": version,
        "priority": priority,
        "feature_authority": "mechanically-derived-from-bound-amendment-strategy",
        "parent_selector_digest": parent,
        "cause_receipt_digest": cause,
    }
    return {**body, "selector_digest": p82.digest(body)}


def install_selector(p82, parent: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selector = make_selector(p82, INITIAL_PRIORITY, SELECTOR_VERSION)
    receipt_body = {
        "authority": "ot-0142-prospective-constitutional-selector-installation",
        "source_subject_digest": parent["artifact_digest"],
        "selector_digest": selector["selector_digest"],
        "researcher_designed_seed": True,
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["constitutional_amendment_selector"] = selector
    child["constitutional_amendment_selector_history"] = [receipt]
    child["constitutional_selection_failures"] = []
    return p82.seal(child), receipt


def strategy_features(candidate: dict[str, Any], public_pass: bool) -> dict[str, Any]:
    kind = candidate["strategy"]["kind"]
    return {
        "public_pass": public_pass,
        "scale_invariant": kind == "quantum-relative",
        "mutation_surface": 1 if kind == "absolute" else 2,
        "candidate_id": candidate["candidate_id"],
    }


def selection_key(features: dict[str, Any], priority: list[str]) -> tuple[Any, ...]:
    values = {
        "public_pass": 0 if features["public_pass"] else 1,
        "scale_invariant": 0 if features["scale_invariant"] else 1,
        "lower_mutation_surface": features["mutation_surface"],
        "stable_id": features["candidate_id"],
    }
    return tuple(values[item] for item in priority)


def select(selector: dict[str, Any], portfolio_receipt: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in portfolio_receipt["public_candidates"]:
        features = strategy_features(item["candidate"], item["public_evaluation"]["passed"])
        rows.append({"candidate": item["candidate"], "features": features, "rank_key": list(selection_key(features, selector["priority"]))})
    selected = min(rows, key=lambda row: tuple(row["rank_key"]))
    return {"selected_candidate": selected["candidate"], "selected_features": selected["features"], "ranked": sorted(rows, key=lambda row: tuple(row["rank_key"]))}


def materialize_program(parent_program: dict[str, Any], candidate: dict[str, Any], quantum: int) -> dict[str, Any]:
    strategy = candidate["strategy"]
    if strategy["kind"] == "absolute":
        offset = strategy["offset"]
    else:
        offset = strategy["factor"] * quantum
    return {**parent_program, "high_offset": offset, "low_offset": offset}


def candidate_evaluation(p82, parent_program: dict[str, Any], candidate: dict[str, Any], bases: list[dict[str, Any]], quantum: int) -> dict[str, Any]:
    program = materialize_program(parent_program, candidate, quantum)
    evaluation = prior.evaluate(p82, program, bases, quantum)
    return {**evaluation, "candidate_id": candidate["candidate_id"], "strategy": candidate["strategy"], "materialized_program": program}


def valid_candidate(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or set(candidate) != {"candidate_id", "strategy", "rationale", "surrender_condition"}:
        return False
    if not isinstance(candidate["candidate_id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", candidate["candidate_id"]):
        return False
    if not prior131.valid_text(candidate["rationale"]) or not prior131.valid_text(candidate["surrender_condition"]):
        return False
    strategy = candidate["strategy"]
    if not isinstance(strategy, dict) or strategy.get("kind") not in {"absolute", "quantum-relative"}:
        return False
    if strategy["kind"] == "absolute":
        return set(strategy) == {"kind", "offset"} and isinstance(strategy["offset"], int) and not isinstance(strategy["offset"], bool) and 1 <= strategy["offset"] <= 256
    return set(strategy) == {"kind", "factor"} and isinstance(strategy["factor"], int) and not isinstance(strategy["factor"], bool) and 1 <= strategy["factor"] <= 8


def validate_portfolio(p82, portfolio: Any, parent_program: dict[str, Any], bases: list[dict[str, Any]], quantum: int) -> tuple[bool, list[dict[str, Any]]]:
    if not isinstance(portfolio, dict) or set(portfolio) != {"question", "candidates"} or not prior131.valid_text(portfolio.get("question")):
        return False, []
    candidates = portfolio.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2 or not all(valid_candidate(item) for item in candidates):
        return False, []
    if len({item["candidate_id"] for item in candidates}) != 2 or {item["strategy"]["kind"] for item in candidates} != {"absolute", "quantum-relative"}:
        return False, []
    evaluations = [candidate_evaluation(p82, parent_program, item, bases, quantum) for item in candidates]
    absolute = next(item for item in candidates if item["strategy"]["kind"] == "absolute")
    relative = next(item for item in candidates if item["strategy"]["kind"] == "quantum-relative")
    valid = bool(all(item["passed"] for item in evaluations) and absolute["strategy"]["offset"] == quantum and relative["strategy"]["factor"] == 1)
    return valid, evaluations


PORTFOLIO_CHECKER = '''import json
from pathlib import Path

portfolio = json.loads(Path("amendment-portfolio.json").read_text())
contract = json.loads(Path("amendment-language.json").read_text())
quantum = contract["quantum"]
candidates = portfolio.get("candidates", [])
kinds = [item.get("strategy", {}).get("kind") for item in candidates]
ids = [item.get("candidate_id") for item in candidates]
absolute = next((item for item in candidates if item.get("strategy", {}).get("kind") == "absolute"), None)
relative = next((item for item in candidates if item.get("strategy", {}).get("kind") == "quantum-relative"), None)
passed = bool(len(candidates) == 2 and len(set(ids)) == 2 and set(kinds) == {"absolute", "quantum-relative"} and absolute["strategy"].get("offset") == quantum and relative["strategy"].get("factor") == 1 and all(isinstance(item.get("rationale"), str) and item["rationale"].strip() and isinstance(item.get("surrender_condition"), str) and item["surrender_condition"].strip() for item in candidates))
print(json.dumps({"passed": passed, "candidate_ids": ids, "kinds": kinds}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def portfolio_seed(root: Path, subject: dict[str, Any], quantum: int, public_bases: list[dict[str, Any]], ordinal: int) -> Path:
    seed = root / "portfolio-seed"
    seed.mkdir()
    capability = subject["contact_program_capabilities"][-1]
    files = {
        "subject-position.json": base.active_position(subject),
        "retained-capability.json": capability,
        "developmental-constitution.json": subject["developmental_constitution"],
        "constitutional-selector.json": subject["constitutional_amendment_selector"],
        "amendment-language.json": {
            "language_version": STRATEGY_VERSION,
            "quantum": quantum,
            "required_families": ["absolute", "quantum-relative"],
            "absolute_rule": "least symmetric integer offset passing current public quantum",
            "quantum_relative_rule": "least positive symmetric integer factor passing current public quantum",
            "derived_features": {"absolute": {"mutation_surface": 1, "scale_invariant": False}, "quantum-relative": {"mutation_surface": 2, "scale_invariant": True}},
            "actor_does_not_author_features_or_scores": True,
        },
        "public-bases.json": public_bases,
        "amendment-portfolio.json": {"question": f"Which constitutional amendment should carry contact beyond q{quantum}?", "candidates": []},
        "mutation-envelope.json": {"editable": ["amendment-portfolio.json"], "immutable": ["subject-position.json", "retained-capability.json", "developmental-constitution.json", "constitutional-selector.json", "amendment-language.json", "public-bases.json", "check_portfolio.py"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_portfolio.py").write_text(PORTFOLIO_CHECKER)
    (seed / "README.md").write_text(f"Author portfolio {ordinal} with exactly one materially distinct candidate from each published amendment family. Derive the least passing current-quantum values, run python3 check_portfolio.py, edit only amendment-portfolio.json, inspect the exact diff, and report truthfully.\n")
    return seed


def run_portfolio_actor(context, p82, root: Path, subject: dict[str, Any], quantum: int, public_bases: list[dict[str, Any]], ordinal: int) -> dict[str, Any]:
    label = f"portfolio-{ordinal}-author"
    seed = portfolio_seed(root, subject, quantum, public_bases, ordinal)
    output, base_audit, workspace, _ = context.run_actor(label, seed, PORTFOLIO_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        portfolio = json.loads((workspace / "amendment-portfolio.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        portfolio = None
        immutable_ok = False
    parent_program = subject["contact_program_capabilities"][-1]["program"]
    valid, evaluations = validate_portfolio(p82, portfolio, parent_program, public_bases, quantum)
    audit = context.audit_actor(label, output, base_audit, bool(valid and immutable_ok), ["amendment-portfolio.json"])
    accepted = bool(valid and immutable_ok and prior131.audit_accepted(audit))
    binding = None
    if accepted:
        body = {
            "authority": "ot-0142-bound-actor-authored-amendment-portfolio",
            "source_subject_digest": subject["artifact_digest"],
            "quantum": quantum,
            "actor_patch_digest": audit["patch_digest"],
            "portfolio": portfolio,
            "public_candidates": [{"candidate": candidate, "public_evaluation": evaluation} for candidate, evaluation in zip(portfolio["candidates"], evaluations)],
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-amendment-portfolio.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "portfolio": portfolio, "public_evaluations": evaluations, "binding": binding}


def bind_selection(p82, subject: dict[str, Any], selector: dict[str, Any], portfolio: dict[str, Any], role: str) -> dict[str, Any]:
    decision = select(selector, portfolio)
    body = {
        "authority": "ot-0142-bound-constitutional-selection",
        "role": role,
        "source_subject_digest": subject["artifact_digest"],
        "selector_digest": selector["selector_digest"],
        "portfolio_binding_digest": portfolio["binding_digest"],
        "decision": decision,
    }
    return {**body, "binding_digest": p82.digest(body)}


def future_world(p82, parent_program: dict[str, Any], portfolio: dict[str, Any], selections: list[dict[str, Any]], quantum: int, bases: list[dict[str, Any]], authority: str) -> dict[str, Any]:
    evaluations = {candidate["candidate_id"]: candidate_evaluation(p82, parent_program, candidate, bases, quantum) for candidate in portfolio["portfolio"]["candidates"]}
    body = {
        "authority": authority,
        "portfolio_binding_digest": portfolio["binding_digest"],
        "selection_binding_digests": [item["binding_digest"] for item in selections],
        "quantum": quantum,
        "bases_digest": p82.digest(bases),
        "candidate_evaluations": evaluations,
        "selected_results": {item["role"]: evaluations[item["decision"]["selected_candidate"]["candidate_id"]] for item in selections},
    }
    return {**body, "receipt_digest": p82.digest(body)}


def retain_selector_failure(p82, subject: dict[str, Any], portfolio: dict[str, Any], selection: dict[str, Any], world: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected_id = selection["decision"]["selected_candidate"]["candidate_id"]
    alternatives = [key for key in world["candidate_evaluations"] if key != selected_id]
    body = {
        "authority": "ot-0142-retained-constitutional-selection-failure",
        "source_subject_digest": subject["artifact_digest"],
        "portfolio_binding_digest": portfolio["binding_digest"],
        "selection_binding_digest": selection["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "selected_candidate_id": selected_id,
        "selected_result": world["candidate_evaluations"][selected_id],
        "alternative_results": {key: world["candidate_evaluations"][key] for key in alternatives},
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["constitutional_selection_failures"] = [*child["constitutional_selection_failures"], receipt]
    child["pending_constitutional_selector_correction"] = receipt
    question = "Whether the constitutional amendment selector should prefer scale transfer over the smaller immediate mutation surface remains unresolved."
    opening = "Open selector-correction-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening}
    child["unresolved"] = question
    return p82.seal(child), receipt


SELECTOR_CHECKER = '''import json
from pathlib import Path

semantics = json.loads(Path("selector-semantics.json").read_text())
portfolio = json.loads(Path("bound-portfolio.json").read_text())
world = json.loads(Path("comparative-consequence.json").read_text())
features = []
for item in portfolio["public_candidates"]:
    candidate = item["candidate"]
    kind = candidate["strategy"]["kind"]
    features.append({"candidate_id": candidate["candidate_id"], "public_pass": item["public_evaluation"]["passed"], "scale_invariant": kind == "quantum-relative", "mutation_surface": 1 if kind == "absolute" else 2})
priority = semantics.get("priority", [])
def key(row):
    values = {"public_pass": 0 if row["public_pass"] else 1, "scale_invariant": 0 if row["scale_invariant"] else 1, "lower_mutation_surface": row["mutation_surface"], "stable_id": row["candidate_id"]}
    return tuple(values[item] for item in priority)
valid_priority = len(priority) == 4 and set(priority) == {"public_pass", "scale_invariant", "lower_mutation_surface", "stable_id"}
selected = min(features, key=key)["candidate_id"] if valid_priority else None
passed = bool(valid_priority and world["candidate_evaluations"][selected]["passed"])
print(json.dumps({"passed": passed, "selected": selected, "priority": priority}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def selector_seed(root: Path, subject: dict[str, Any], portfolio: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "selector-seed"
    seed.mkdir()
    semantics = {"priority": subject["constitutional_amendment_selector"]["priority"]}
    files = {
        "subject-position.json": base.active_position(subject),
        "inherited-selector.json": subject["constitutional_amendment_selector"],
        "bound-portfolio.json": portfolio,
        "comparative-consequence.json": world,
        "selector-semantics.json": semantics,
        "mutation-envelope.json": {"editable": ["selector-semantics.json"], "immutable": ["subject-position.json", "inherited-selector.json", "bound-portfolio.json", "comparative-consequence.json", "check_selector.py"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_selector.py").write_text(SELECTOR_CHECKER)
    (seed / "README.md").write_text("Correct only the constitutional selector priority from the exact comparative consequence. Run python3 check_selector.py, inspect the exact one-file diff, and report truthfully.\n")
    return seed


def run_selector_corrector(context, p82, root: Path, subject: dict[str, Any], portfolio: dict[str, Any], world: dict[str, Any], initial: dict[str, Any]) -> dict[str, Any]:
    label = "constitutional-selector-corrector"
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
    provisional = make_selector(p82, priority, CORRECTED_SELECTOR_VERSION, initial["selector_digest"], world["receipt_digest"]) if isinstance(priority, list) else None
    corrected_decision = select(provisional, portfolio) if provisional and set(priority) == set(FEATURES) and len(priority) == 4 else None
    old_decision = select(initial, portfolio)
    corrected_result = world["candidate_evaluations"].get(corrected_decision["selected_candidate"]["candidate_id"]) if corrected_decision else None
    old_result = world["candidate_evaluations"][old_decision["selected_candidate"]["candidate_id"]]
    valid = bool(provisional and immutable_ok and priority != initial["priority"] and corrected_result and corrected_result["passed"] and not old_result["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["selector-semantics.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {
            "authority": "ot-0142-consequence-corrected-constitutional-selector-binding",
            "source_subject_digest": subject["artifact_digest"],
            "parent_selector_digest": initial["selector_digest"],
            "cause_world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "actor_semantics": semantics,
            "compiled_selector": provisional,
            "retrospective_corrected_decision": corrected_decision,
            "unchanged_decision": old_decision,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-corrected-selector.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "semantics": semantics, "binding": binding}


def install_corrected_selector(p82, subject: dict[str, Any], binding: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt_body = {
        "authority": "ot-0142-constitutional-selector-correction",
        "source_subject_digest": subject["artifact_digest"],
        "binding_digest": binding["binding_digest"],
        "parent_selector_digest": binding["parent_selector_digest"],
        "corrected_selector_digest": binding["compiled_selector"]["selector_digest"],
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["constitutional_amendment_selector"] = binding["compiled_selector"]
    child["constitutional_amendment_selector_history"] = [*child["constitutional_amendment_selector_history"], receipt]
    child["pending_constitutional_selector_correction"] = None
    question = "Which held-out constitutional amendment preserves current contact while widening future contact remains unresolved."
    opening = "Open amendment-portfolio-2-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening}
    child["unresolved"] = question
    return p82.seal(child), receipt


def adaptive_constitution(p82, parent: dict[str, Any], strategy: dict[str, Any], cause: str) -> dict[str, Any]:
    body = {key: value for key, value in parent.items() if key != "constitution_digest"}
    body.update({
        "constitution_version": "ot-0142-adaptive-constitution-v1",
        "program_validator_version": "ot-0142-offset-strategy-v1",
        "active_offset_strategy": strategy,
        "parent_constitution_digest": parent["constitution_digest"],
        "cause_receipt_digest": cause,
    })
    return {**body, "constitution_digest": p82.digest(body)}


def install_adaptive_strategy(p82, subject: dict[str, Any], portfolio: dict[str, Any], selection: dict[str, Any], world: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = selection["decision"]["selected_candidate"]
    strategy = candidate["strategy"]
    constitution = adaptive_constitution(p82, subject["developmental_constitution"], strategy, world["receipt_digest"])
    body = {
        "authority": "ot-0142-adaptive-contact-strategy-capability",
        "strategy_version": STRATEGY_VERSION,
        "strategy": strategy,
        "candidate_id": candidate["candidate_id"],
        "portfolio_binding_digest": portfolio["binding_digest"],
        "selection_binding_digest": selection["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "selector_digest": subject["constitutional_amendment_selector"]["selector_digest"],
        "constitution_digest": constitution["constitution_digest"],
    }
    capability = {**body, "capability_digest": p82.digest(body)}
    receipt_body = {
        "authority": "ot-0142-adaptive-strategy-installation",
        "source_subject_digest": subject["artifact_digest"],
        "capability_digest": capability["capability_digest"],
        "constitution_digest": constitution["constitution_digest"],
        "selected_world_result_digest": p82.digest(world["selected_results"]["active"]),
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["developmental_constitution"] = constitution
    child["encounter_scheduler"] = {**child["encounter_scheduler"], "cycle": 8, "admitted_quantum": 64, "next_quantum": 128, "constitution_digest": constitution["constitution_digest"], "pending_failure": None, "verification_due": False}
    child["adaptive_contact_strategy_capabilities"] = [*child.get("adaptive_contact_strategy_capabilities", []), capability]
    child["adaptive_strategy_installation_receipts"] = [*child.get("adaptive_strategy_installation_receipts", []), receipt]
    question = "Whether the retained quantum-relative contact strategy continues to transfer at reserve band 128 remains unresolved."
    opening = "Open encounter-9-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening}
    child["unresolved"] = question
    return p82.seal(child), receipt


def reuse_seed(root: Path, subject: dict[str, Any], capability: dict[str, Any]) -> Path:
    seed = root / "reuse-seed"
    seed.mkdir()
    files = {
        "subject-position.json": base.active_position(subject),
        "adaptive-strategy-capability.json": capability,
        "developmental-constitution.json": subject["developmental_constitution"],
        "reuse-authorization.json": {"authority": "ot-0142-subject-owned-adaptive-reuse", "source_subject_digest": subject["artifact_digest"], "quantum": subject["encounter_scheduler"]["next_quantum"], "capability_digest": capability["capability_digest"], "constitution_digest": subject["developmental_constitution"]["constitution_digest"], "allowed_action": "reuse"},
        "reuse-action.json": {"action": "surrender", "strategy": capability["strategy"], "rationale": "Inspect exact retained strategy and authorization."},
        "mutation-envelope.json": {"editable": ["reuse-action.json"], "immutable": ["subject-position.json", "adaptive-strategy-capability.json", "developmental-constitution.json", "reuse-authorization.json"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Reuse the exact retained adaptive strategy. Preserve strategy and constitution bytes, edit only reuse-action.json, inspect the exact diff, and report truthfully.\n")
    return seed


def run_reuse_actor(context, p82, root: Path, subject: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    label = "adaptive-strategy-reuse"
    seed = reuse_seed(root, subject, capability)
    output, base_audit, workspace, _ = context.run_actor(label, seed, REUSE_SCHEMA, (seed / "README.md").read_text().strip())
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
        body = {
            "authority": "ot-0142-bound-adaptive-strategy-reuse",
            "source_subject_digest": subject["artifact_digest"],
            "capability_digest": capability["capability_digest"],
            "constitution_digest": subject["developmental_constitution"]["constitution_digest"],
            "quantum": subject["encounter_scheduler"]["next_quantum"],
            "actor_patch_digest": audit["patch_digest"],
            "action": action,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-adaptive-reuse.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "action": action, "binding": binding}


def final_transition(p82, subject: dict[str, Any], binding: dict[str, Any], evaluation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt_body = {
        "authority": "ot-0142-adaptive-reuse-transition",
        "source_subject_digest": subject["artifact_digest"],
        "reuse_binding_digest": binding["binding_digest"],
        "world_evaluation_digest": p82.digest(evaluation),
        "quantum": evaluation["quantum"],
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["encounter_scheduler"] = {**child["encounter_scheduler"], "cycle": 9, "admitted_quantum": evaluation["quantum"], "next_quantum": evaluation["quantum"] * 2}
    child["adaptive_strategy_reuse_receipts"] = [*child.get("adaptive_strategy_reuse_receipts", []), receipt]
    question = f"Whether the retained adaptive strategy continues to widen coherent contact at reserve band {evaluation['quantum'] * 2} remains unresolved."
    opening = "Open encounter-10-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = question
    return p82.seal(child), receipt


def representative_portfolio() -> dict[str, Any]:
    return {
        "question": "Which amendment carries contact beyond the current quantum?",
        "candidates": [
            {"candidate_id": "absolute-minimum", "strategy": {"kind": "absolute", "offset": 32}, "rationale": "Use the least fixed offset that passes now.", "surrender_condition": "Surrender if fixed contact fails later."},
            {"candidate_id": "relative-minimum", "strategy": {"kind": "quantum-relative", "factor": 1}, "rationale": "Scale contact with the encountered quantum.", "surrender_condition": "Surrender if proportional contact fails later."},
        ],
    }


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    subject, installation = install_selector(p82, parent)
    parent_program = parent["contact_program_capabilities"][-1]["program"]
    portfolio = representative_portfolio()
    public_bases = prior.previous.bases_for(8, 32, public=True)
    valid, evaluations = validate_portfolio(p82, portfolio, parent_program, public_bases, 32)
    receipt = {"public_candidates": [{"candidate": candidate, "public_evaluation": evaluation} for candidate, evaluation in zip(portfolio["candidates"], evaluations)]}
    initial = subject["constitutional_amendment_selector"]
    corrected = make_selector(p82, ["public_pass", "scale_invariant", "lower_mutation_surface", "stable_id"], CORRECTED_SELECTOR_VERSION, initial["selector_digest"], "fixture")
    initial_decision = select(initial, receipt)
    corrected_decision = select(corrected, receipt)
    future = {item["candidate_id"]: candidate_evaluation(p82, parent_program, item, prior.previous.bases_for(8, 64), 64) for item in portfolio["candidates"]}
    later = {item["candidate_id"]: candidate_evaluation(p82, parent_program, item, prior.previous.bases_for(9, 128), 128) for item in portfolio["candidates"]}
    with tempfile.TemporaryDirectory() as directory:
        seed = portfolio_seed(Path(directory), subject, 32, public_bases, 1)
        files = sorted(path.name for path in seed.iterdir() if path.is_file())
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "seed_selector_installed": installation["selector_digest"] == initial["selector_digest"],
        "representative_portfolio_valid": valid and all(item["passed"] for item in evaluations),
        "initial_selects_absolute": initial_decision["selected_candidate"]["strategy"]["kind"] == "absolute",
        "corrected_selects_relative": corrected_decision["selected_candidate"]["strategy"]["kind"] == "quantum-relative",
        "future_separates": not future["absolute-minimum"]["passed"] and future["absolute-minimum"]["distinguishing_count"] == 3 and future["relative-minimum"]["passed"] and future["relative-minimum"]["distinguishing_count"] == 9,
        "later_separates_more": not later["absolute-minimum"]["passed"] and later["absolute-minimum"]["distinguishing_count"] == 0 and later["relative-minimum"]["passed"] and later["relative-minimum"]["distinguishing_count"] == 9,
        "portfolio_seed_complete": files == ["README.md", "amendment-language.json", "amendment-portfolio.json", "check_portfolio.py", "constitutional-selector.json", "developmental-constitution.json", "mutation-envelope.json", "public-bases.json", "retained-capability.json", "subject-position.json"],
        "schemas_present": PORTFOLIO_SCHEMA.is_file() and SELECTOR_SCHEMA.is_file() and REUSE_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "initial_decision": initial_decision, "corrected_decision": corrected_decision, "future": future, "later": later}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0142").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0141", "open-subject-with-revised-developmental-constitution.json")
    subject, selector_installation = install_selector(p82, parent)
    fixtures = preflight(p82, parent)
    fixtures["checks"]["seeded_identity"] = runtime.identity_conforms(subject)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "seeded_subject_digest": subject["artifact_digest"]}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0142 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    (run / "selector-installation.json").write_text(json.dumps(selector_installation, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    parent_program = subject["contact_program_capabilities"][-1]["program"]
    first_root = run / "first-portfolio"
    first_root.mkdir()
    first_actor = run_portfolio_actor(context, p82, first_root, subject, 32, prior.previous.bases_for(8, 32, public=True), 1)
    initial_selector = subject["constitutional_amendment_selector"]
    first_selection = bind_selection(p82, subject, initial_selector, first_actor["binding"], "active") if first_actor["binding"] else None
    first_world = None
    failure_subject = subject
    failure_receipt = None
    if first_selection:
        first_world = future_world(p82, parent_program, first_actor["binding"], [first_selection], 64, prior.previous.bases_for(8, 64), "ot-0142-first-constitutional-selection-future-world")
        (first_root / "sealed-future-world.json").write_text(json.dumps(first_world, indent=2, sort_keys=True) + "\n")
        selected = first_world["selected_results"]["active"]
        alternatives = [value for key, value in first_world["candidate_evaluations"].items() if key != selected["candidate_id"]]
        if not selected["passed"] and any(item["passed"] for item in alternatives):
            failure_subject, failure_receipt = retain_selector_failure(p82, subject, first_actor["binding"], first_selection, first_world)
    correction_root = run / "selector-correction"
    correction_root.mkdir()
    correction = run_selector_corrector(context, p82, correction_root, failure_subject, first_actor["binding"], first_world, initial_selector) if failure_receipt else None
    corrected_subject = failure_subject
    correction_receipt = None
    if correction and correction["binding"]:
        corrected_subject, correction_receipt = install_corrected_selector(p82, failure_subject, correction["binding"])
    second_root = run / "held-out-portfolio"
    second_root.mkdir()
    second_actor = run_portfolio_actor(context, p82, second_root, corrected_subject, 32, prior.previous.bases_for(9, 32, public=True), 2) if correction_receipt else None
    active_selection = control_selection = second_world = None
    adaptive_subject = corrected_subject
    adaptive_receipt = None
    if second_actor and second_actor["binding"]:
        active_selection = bind_selection(p82, corrected_subject, corrected_subject["constitutional_amendment_selector"], second_actor["binding"], "active")
        control_selection = bind_selection(p82, corrected_subject, initial_selector, second_actor["binding"], "unchanged-control")
        second_world = future_world(p82, parent_program, second_actor["binding"], [active_selection, control_selection], 64, prior.previous.bases_for(9, 64), "ot-0142-held-out-matched-constitutional-world")
        (second_root / "sealed-matched-world.json").write_text(json.dumps(second_world, indent=2, sort_keys=True) + "\n")
        if second_world["selected_results"]["active"]["passed"] and not second_world["selected_results"]["unchanged-control"]["passed"]:
            adaptive_subject, adaptive_receipt = install_adaptive_strategy(p82, corrected_subject, second_actor["binding"], active_selection, second_world)
    reuse_root = run / "later-reuse"
    reuse_root.mkdir()
    adaptive_capability = adaptive_subject.get("adaptive_contact_strategy_capabilities", [None])[-1]
    reuse = run_reuse_actor(context, p82, reuse_root, adaptive_subject, adaptive_capability) if adaptive_receipt else None
    reuse_eval = None
    final = adaptive_subject
    reuse_transition = None
    if reuse and reuse["binding"]:
        reuse_candidate = {"candidate_id": adaptive_capability["candidate_id"], "strategy": adaptive_capability["strategy"], "rationale": "retained", "surrender_condition": "retained"}
        reuse_eval = candidate_evaluation(p82, parent_program, reuse_candidate, prior.previous.bases_for(10, 128), 128)
        (reuse_root / "sealed-reuse-world.json").write_text(json.dumps(reuse_eval, indent=2, sort_keys=True) + "\n")
        if reuse_eval["passed"]:
            final, reuse_transition = final_transition(p82, adaptive_subject, reuse["binding"], reuse_eval)
    absolute_control = None
    if second_actor and second_actor["binding"]:
        control_candidate = control_selection["decision"]["selected_candidate"]
        absolute_control = candidate_evaluation(p82, parent_program, control_candidate, prior.previous.bases_for(10, 128), 128)
        (run / "post-seal-unchanged-selector-q128-control.json").write_text(json.dumps(absolute_control, indent=2, sort_keys=True) + "\n")
    checks = {
        "four_fresh_actors": bool(first_actor["binding"] and correction and correction["binding"] and second_actor and second_actor["binding"] and reuse and reuse["binding"]),
        "first_selector_harmed": bool(first_world and not first_world["selected_results"]["active"]["passed"] and first_selection["decision"]["selected_candidate"]["strategy"]["kind"] == "absolute" and any(item["passed"] for key, item in first_world["candidate_evaluations"].items() if key != first_world["selected_results"]["active"]["candidate_id"])),
        "failure_retained": bool(failure_receipt and runtime.identity_conforms(failure_subject)),
        "selector_corrected": bool(correction_receipt and corrected_subject["constitutional_amendment_selector"]["priority"].index("scale_invariant") < corrected_subject["constitutional_amendment_selector"]["priority"].index("lower_mutation_surface")),
        "held_out_selection_differs": bool(active_selection and control_selection and active_selection["decision"]["selected_candidate"]["strategy"]["kind"] == "quantum-relative" and control_selection["decision"]["selected_candidate"]["strategy"]["kind"] == "absolute"),
        "matched_active_beats_control": bool(second_world and second_world["selected_results"]["active"]["passed"] and second_world["selected_results"]["active"]["distinguishing_count"] == 9 and not second_world["selected_results"]["unchanged-control"]["passed"] and second_world["selected_results"]["unchanged-control"]["distinguishing_count"] == 3),
        "adaptive_strategy_installed": bool(adaptive_receipt and runtime.identity_conforms(adaptive_subject) and adaptive_capability["strategy"]["kind"] == "quantum-relative"),
        "later_reuse_without_amendment": bool(reuse_eval and reuse_eval["passed"] and reuse_eval["distinguishing_count"] == 9 and reuse["action"]["strategy"] == adaptive_capability["strategy"]),
        "post_seal_control_fails": bool(absolute_control and not absolute_control["passed"] and absolute_control["distinguishing_count"] == 0),
        "selector_erasure_reproduces_control": bool(second_actor and select(initial_selector, second_actor["binding"])["selected_candidate"] == control_selection["decision"]["selected_candidate"]),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open" and final["encounter_scheduler"]["next_quantum"] == 256 and "reserve band 256" in final["continuation"]["next_opening"],
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0142-consequence-corrected-constitutional-selection-driver",
        "source_subject_digest": parent["artifact_digest"],
        "seeded_subject_digest": subject["artifact_digest"],
        "first_portfolio": p82.compact(first_actor),
        "first_selection": first_selection,
        "first_world": first_world,
        "failure_receipt": failure_receipt,
        "selector_correction": p82.compact(correction) if correction else None,
        "selector_correction_receipt": correction_receipt,
        "held_out_portfolio": p82.compact(second_actor) if second_actor else None,
        "active_selection": active_selection,
        "unchanged_control_selection": control_selection,
        "held_out_world": second_world,
        "adaptive_installation_receipt": adaptive_receipt,
        "later_reuse": p82.compact(reuse) if reuse else None,
        "later_reuse_world": reuse_eval,
        "later_reuse_transition": reuse_transition,
        "post_seal_absolute_control": absolute_control,
        "checks": checks,
        "constitutional_selection_correction_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": sum(item is not None for item in [first_actor, correction, second_actor, reuse]),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
