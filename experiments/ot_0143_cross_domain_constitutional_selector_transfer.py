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
BASE_PATH = ROOT / "ot_0142_consequence_corrected_constitutional_selection.py"
BASE_SHA256 = "305024a440f5c60286c31b0fb3e18b8cac782db6264dbf43fc95550bae89e05f"
PARENT_DIGEST = "a66da59648c69b0b963be36da25e37156ad55f12598d749964c02e5bfb8dce4d"
LANGUAGE_VERSION = "ot-0143-recovery-cadence-v1"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0142 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0143_frozen_ot0142", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
prior131 = prior.prior131
base130 = prior.base130
base = prior.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return prior.load_artifact(p82, repo, store, experiment, manifest)


def recovery_cases(prefix: str, maxima: list[int]) -> list[dict[str, Any]]:
    cases = []
    for index, maximum in enumerate(maxima):
        cases.append({
            "case_id": f"{prefix}-{index + 1}-max-{maximum}",
            "observed_latencies": [maximum // 4, maximum // 2, (3 * maximum) // 4, maximum],
            "required_delay": maximum,
            "shifted": maximum != 32,
        })
    return cases


def valid_candidate(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or set(candidate) != {"candidate_id", "strategy", "rationale", "surrender_condition"}:
        return False
    if not isinstance(candidate["candidate_id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", candidate["candidate_id"]):
        return False
    if not prior131.valid_text(candidate["rationale"]) or not prior131.valid_text(candidate["surrender_condition"]):
        return False
    strategy = candidate["strategy"]
    if not isinstance(strategy, dict) or strategy.get("kind") not in {"fixed-delay", "latency-relative"}:
        return False
    if strategy["kind"] == "fixed-delay":
        return set(strategy) == {"kind", "delay"} and isinstance(strategy["delay"], int) and not isinstance(strategy["delay"], bool) and 1 <= strategy["delay"] <= 1024
    return set(strategy) == {"kind", "factor"} and isinstance(strategy["factor"], int) and not isinstance(strategy["factor"], bool) and 1 <= strategy["factor"] <= 8


def scheduled_delay(candidate: dict[str, Any], case: dict[str, Any]) -> int:
    strategy = candidate["strategy"]
    if strategy["kind"] == "fixed-delay":
        return strategy["delay"]
    return strategy["factor"] * max(case["observed_latencies"])


def evaluate(candidate: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        delay = scheduled_delay(candidate, case)
        rows.append({
            "case_id": case["case_id"],
            "shifted": case["shifted"],
            "scheduled_delay": delay,
            "required_delay": case["required_delay"],
            "passed": delay == case["required_delay"],
        })
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
    if len({item["candidate_id"] for item in candidates}) != 2 or {item["strategy"]["kind"] for item in candidates} != {"fixed-delay", "latency-relative"}:
        return False, []
    fixed = next(item for item in candidates if item["strategy"]["kind"] == "fixed-delay")
    relative = next(item for item in candidates if item["strategy"]["kind"] == "latency-relative")
    evaluations = [evaluate(item, public_cases) for item in candidates]
    valid = bool(fixed["strategy"]["delay"] == 32 and relative["strategy"]["factor"] == 1 and all(item["passed"] for item in evaluations))
    return valid, evaluations


def features(candidate: dict[str, Any], public_pass: bool) -> dict[str, Any]:
    kind = candidate["strategy"]["kind"]
    return {
        "public_pass": public_pass,
        "scale_invariant": kind == "latency-relative",
        "mutation_surface": 1 if kind == "fixed-delay" else 2,
        "candidate_id": candidate["candidate_id"],
    }


def select(selector: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    ranked = []
    for item in binding["public_candidates"]:
        derived = features(item["candidate"], item["public_evaluation"]["passed"])
        values = {
            "public_pass": 0 if derived["public_pass"] else 1,
            "scale_invariant": 0 if derived["scale_invariant"] else 1,
            "lower_mutation_surface": derived["mutation_surface"],
            "stable_id": derived["candidate_id"],
        }
        ranked.append({"candidate": item["candidate"], "features": derived, "rank_key": [values[key] for key in selector["priority"]]})
    selected = min(ranked, key=lambda row: tuple(row["rank_key"]))
    return {"selected_candidate": selected["candidate"], "selected_features": selected["features"], "ranked": sorted(ranked, key=lambda row: tuple(row["rank_key"]))}


PORTFOLIO_CHECKER = '''import json
from pathlib import Path

portfolio = json.loads(Path("recovery-amendment-portfolio.json").read_text())
candidates = portfolio.get("candidates", [])
ids = [item.get("candidate_id") for item in candidates]
fixed = next((item for item in candidates if item.get("strategy", {}).get("kind") == "fixed-delay"), None)
relative = next((item for item in candidates if item.get("strategy", {}).get("kind") == "latency-relative"), None)
passed = bool(len(candidates) == 2 and len(set(ids)) == 2 and fixed and relative and fixed["strategy"].get("delay") == 32 and relative["strategy"].get("factor") == 1 and all(isinstance(item.get("rationale"), str) and item["rationale"].strip() and isinstance(item.get("surrender_condition"), str) and item["surrender_condition"].strip() for item in candidates))
print(json.dumps({"passed": passed, "candidate_ids": ids}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def portfolio_seed(root: Path, subject: dict[str, Any], public_cases: list[dict[str, Any]]) -> Path:
    seed = root / "portfolio-seed"
    seed.mkdir()
    files = {
        "subject-position.json": base.active_position(subject),
        "corrected-constitutional-selector.json": subject["constitutional_amendment_selector"],
        "recovery-amendment-language.json": {
            "language_version": LANGUAGE_VERSION,
            "domain": "recovery-cadence",
            "required_families": ["fixed-delay", "latency-relative"],
            "fixed_rule": "least integer delay passing current public cases",
            "relative_rule": "least positive integer factor over maximum observed latency passing current public cases",
            "derived_features": {"fixed-delay": {"mutation_surface": 1, "scale_invariant": False}, "latency-relative": {"mutation_surface": 2, "scale_invariant": True}},
            "reserve_program_not_part_of_language": True,
        },
        "public-recovery-cases.json": public_cases,
        "recovery-amendment-portfolio.json": {"question": "Which recovery-cadence amendment should govern changing latency histories?", "candidates": []},
        "mutation-envelope.json": {"editable": ["recovery-amendment-portfolio.json"], "immutable": ["subject-position.json", "corrected-constitutional-selector.json", "recovery-amendment-language.json", "public-recovery-cases.json", "check_portfolio.py"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_portfolio.py").write_text(PORTFOLIO_CHECKER)
    (seed / "README.md").write_text("Author one recovery-cadence amendment in each published family. Derive the least public-passing values, run python3 check_portfolio.py, edit only recovery-amendment-portfolio.json, inspect the exact diff, and report truthfully.\n")
    return seed


def run_portfolio_actor(context, p82, root: Path, subject: dict[str, Any], public_cases: list[dict[str, Any]]) -> dict[str, Any]:
    label = "recovery-portfolio-author"
    seed = portfolio_seed(root, subject, public_cases)
    output, base_audit, workspace, _ = context.run_actor(label, seed, prior.PORTFOLIO_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        portfolio = json.loads((workspace / "recovery-amendment-portfolio.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        portfolio = None
        immutable_ok = False
    valid, evaluations = validate_portfolio(portfolio, public_cases)
    audit = context.audit_actor(label, output, base_audit, bool(valid and immutable_ok), ["recovery-amendment-portfolio.json"])
    binding = None
    if valid and immutable_ok and prior131.audit_accepted(audit):
        body = {
            "authority": "ot-0143-bound-actor-authored-recovery-amendment-portfolio",
            "source_subject_digest": subject["artifact_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "portfolio": portfolio,
            "public_candidates": [{"candidate": candidate, "public_evaluation": evaluation} for candidate, evaluation in zip(portfolio["candidates"], evaluations)],
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-recovery-portfolio.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "portfolio": portfolio, "binding": binding}


def bind_selection(p82, subject: dict[str, Any], selector: dict[str, Any], portfolio: dict[str, Any], role: str) -> dict[str, Any]:
    decision = select(selector, portfolio)
    body = {"authority": "ot-0143-bound-cross-domain-constitutional-selection", "role": role, "source_subject_digest": subject["artifact_digest"], "selector_digest": selector["selector_digest"], "portfolio_binding_digest": portfolio["binding_digest"], "decision": decision}
    return {**body, "binding_digest": p82.digest(body)}


def world_receipt(p82, portfolio: dict[str, Any], selections: list[dict[str, Any]], cases: list[dict[str, Any]], authority: str) -> dict[str, Any]:
    evaluations = {candidate["candidate_id"]: evaluate(candidate, cases) for candidate in portfolio["portfolio"]["candidates"]}
    body = {
        "authority": authority,
        "portfolio_binding_digest": portfolio["binding_digest"],
        "selection_binding_digests": [item["binding_digest"] for item in selections],
        "cases_digest": p82.digest(cases),
        "candidate_evaluations": evaluations,
        "selected_results": {item["role"]: evaluations[item["decision"]["selected_candidate"]["candidate_id"]] for item in selections},
    }
    return {**body, "receipt_digest": p82.digest(body)}


def recovery_constitution(p82, parent: dict[str, Any], strategy: dict[str, Any], cause: str) -> dict[str, Any]:
    body = {key: value for key, value in parent.items() if key != "constitution_digest"}
    body.update({"constitution_version": "ot-0143-cross-domain-constitution-v1", "active_recovery_cadence_strategy": strategy, "parent_constitution_digest": parent["constitution_digest"], "cause_receipt_digest": cause})
    return {**body, "constitution_digest": p82.digest(body)}


def install_recovery(p82, subject: dict[str, Any], portfolio: dict[str, Any], selection: dict[str, Any], world: dict[str, Any], reserve_floor: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = selection["decision"]["selected_candidate"]
    constitution = recovery_constitution(p82, subject["developmental_constitution"], candidate["strategy"], world["receipt_digest"])
    body = {
        "authority": "ot-0143-recovery-cadence-strategy-capability",
        "language_version": LANGUAGE_VERSION,
        "candidate_id": candidate["candidate_id"],
        "strategy": candidate["strategy"],
        "portfolio_binding_digest": portfolio["binding_digest"],
        "selection_binding_digest": selection["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "reserve_floor_digest": p82.digest(reserve_floor),
        "selector_digest": subject["constitutional_amendment_selector"]["selector_digest"],
        "constitution_digest": constitution["constitution_digest"],
    }
    capability = {**body, "capability_digest": p82.digest(body)}
    receipt_body = {"authority": "ot-0143-cross-domain-strategy-installation", "source_subject_digest": subject["artifact_digest"], "capability_digest": capability["capability_digest"], "constitution_digest": constitution["constitution_digest"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["developmental_constitution"] = constitution
    child["recovery_cadence_capabilities"] = [*child.get("recovery_cadence_capabilities", []), capability]
    child["cross_domain_installation_receipts"] = [*child.get("cross_domain_installation_receipts", []), receipt]
    child["cross_domain_scheduler"] = {"domain": "recovery-cadence", "cycle": 1, "last_required_delay": 128, "next_required_delay": 224, "status": "open"}
    question = "Whether the retained latency-relative recovery cadence transfers to new latency histories remains unresolved."
    opening = "Open recovery-cadence-2-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening}
    child["unresolved"] = question
    return p82.seal(child), receipt


def reuse_seed(root: Path, subject: dict[str, Any], capability: dict[str, Any]) -> Path:
    seed = root / "reuse-seed"
    seed.mkdir()
    files = {
        "subject-position.json": base.active_position(subject),
        "recovery-capability.json": capability,
        "developmental-constitution.json": subject["developmental_constitution"],
        "reuse-action.json": {"action": "surrender", "strategy": capability["strategy"], "rationale": "Inspect exact retained recovery strategy."},
        "mutation-envelope.json": {"editable": ["reuse-action.json"], "immutable": ["subject-position.json", "recovery-capability.json", "developmental-constitution.json"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Reuse the exact retained recovery-cadence strategy. Preserve strategy and constitution bytes, edit only reuse-action.json, inspect the exact diff, and report truthfully.\n")
    return seed


def run_reuse_actor(context, p82, root: Path, subject: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    label = "recovery-strategy-reuse"
    seed = reuse_seed(root, subject, capability)
    output, base_audit, workspace, _ = context.run_actor(label, seed, prior.REUSE_SCHEMA, (seed / "README.md").read_text().strip())
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
        body = {"authority": "ot-0143-bound-recovery-strategy-reuse", "source_subject_digest": subject["artifact_digest"], "capability_digest": capability["capability_digest"], "actor_patch_digest": audit["patch_digest"], "action": action}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-recovery-reuse.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "action": action, "binding": binding}


def final_subject(p82, subject: dict[str, Any], binding: dict[str, Any], evaluation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt_body = {"authority": "ot-0143-recovery-reuse-transition", "source_subject_digest": subject["artifact_digest"], "reuse_binding_digest": binding["binding_digest"], "evaluation_digest": p82.digest(evaluation)}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["cross_domain_scheduler"] = {"domain": "recovery-cadence", "cycle": 2, "last_required_delay": 224, "next_required_delay": 256, "status": "open"}
    child["recovery_reuse_receipts"] = [*child.get("recovery_reuse_receipts", []), receipt]
    question = "Whether latency-relative recovery cadence remains useful under a later contradictory operating regime remains unresolved."
    opening = "Open recovery-cadence-3-" + receipt["receipt_digest"][:12] + ": " + question
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = question
    return p82.seal(child), receipt


def representative_portfolio() -> dict[str, Any]:
    return {"question": "Which recovery amendment transfers?", "candidates": [
        {"candidate_id": "fixed-retry", "strategy": {"kind": "fixed-delay", "delay": 32}, "rationale": "Use the least delay passing current histories.", "surrender_condition": "Surrender if latency shifts."},
        {"candidate_id": "relative-retry", "strategy": {"kind": "latency-relative", "factor": 1}, "rationale": "Scale delay to observed recovery latency.", "surrender_condition": "Surrender if proportional delay misfires."},
    ]}


def preflight(p82, parent: dict[str, Any], initial_selector: dict[str, Any]) -> dict[str, Any]:
    portfolio = representative_portfolio()
    public = recovery_cases("public", [32, 32])
    valid, evaluations = validate_portfolio(portfolio, public)
    binding = {"public_candidates": [{"candidate": candidate, "public_evaluation": evaluation} for candidate, evaluation in zip(portfolio["candidates"], evaluations)]}
    corrected_decision = select(parent["constitutional_amendment_selector"], binding)
    unchanged_decision = select(initial_selector, binding)
    hidden_cases = recovery_cases("sealed", [64, 96, 128, 32, 32])
    corrected_eval = evaluate(corrected_decision["selected_candidate"], hidden_cases)
    unchanged_eval = evaluate(unchanged_decision["selected_candidate"], hidden_cases)
    adaptive = parent["adaptive_contact_strategy_capabilities"][-1]
    reserve_candidate = {"candidate_id": adaptive["candidate_id"], "strategy": adaptive["strategy"], "rationale": "retained", "surrender_condition": "retained"}
    reserve_floor = prior.candidate_evaluation(p82, parent["contact_program_capabilities"][-1]["program"], reserve_candidate, prior.prior.previous.bases_for(11, 256), 256)
    with tempfile.TemporaryDirectory() as directory:
        seed = portfolio_seed(Path(directory), parent, public)
        files = sorted(path.name for path in seed.iterdir() if path.is_file())
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "portfolio_valid": valid and all(item["passed"] for item in evaluations),
        "corrected_selects_relative": corrected_decision["selected_candidate"]["strategy"]["kind"] == "latency-relative",
        "unchanged_selects_fixed": unchanged_decision["selected_candidate"]["strategy"]["kind"] == "fixed-delay",
        "hidden_separates": corrected_eval["passed"] and corrected_eval["shifted_pass_count"] == 3 and not unchanged_eval["passed"] and unchanged_eval["shifted_pass_count"] == 0 and unchanged_eval["control_pass_count"] == 2,
        "reserve_floor_passes": reserve_floor["passed"] and reserve_floor["distinguishing_count"] == 9 and reserve_floor["confirmation_count"] == 3,
        "seed_complete": files == ["README.md", "check_portfolio.py", "corrected-constitutional-selector.json", "mutation-envelope.json", "public-recovery-cases.json", "recovery-amendment-language.json", "recovery-amendment-portfolio.json", "subject-position.json"],
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "corrected_decision": corrected_decision, "unchanged_decision": unchanged_decision, "corrected_eval": corrected_eval, "unchanged_eval": unchanged_eval, "reserve_floor": reserve_floor}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0143").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0142", "open-subject-with-adaptive-constitutional-selector.json")
    initial_selector = prior.make_selector(p82, prior.INITIAL_PRIORITY, prior.SELECTOR_VERSION)
    fixtures = preflight(p82, parent, initial_selector)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0143 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    portfolio_root = run / "recovery-portfolio"
    portfolio_root.mkdir()
    actor = run_portfolio_actor(context, p82, portfolio_root, parent, recovery_cases("public", [32, 32]))
    active = control = world = None
    reserve_floor = fixtures["reserve_floor"]
    installed = parent
    installation = None
    if actor["binding"]:
        active = bind_selection(p82, parent, parent["constitutional_amendment_selector"], actor["binding"], "active")
        control = bind_selection(p82, parent, initial_selector, actor["binding"], "unchanged-control")
        world = world_receipt(p82, actor["binding"], [active, control], recovery_cases("sealed", [64, 96, 128, 32, 32]), "ot-0143-sealed-cross-domain-recovery-world")
        (portfolio_root / "sealed-matched-recovery-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
        (run / "reserve-no-regression-receipt.json").write_text(json.dumps(reserve_floor, indent=2, sort_keys=True) + "\n")
        if world["selected_results"]["active"]["passed"] and not world["selected_results"]["unchanged-control"]["passed"] and reserve_floor["passed"]:
            installed, installation = install_recovery(p82, parent, actor["binding"], active, world, reserve_floor)
    reuse_root = run / "later-recovery-reuse"
    reuse_root.mkdir()
    capability = installed.get("recovery_cadence_capabilities", [None])[-1]
    reuse = run_reuse_actor(context, p82, reuse_root, installed, capability) if installation else None
    reuse_world = None
    final = installed
    reuse_transition = None
    if reuse and reuse["binding"]:
        candidate = {"candidate_id": capability["candidate_id"], "strategy": capability["strategy"], "rationale": "retained", "surrender_condition": "retained"}
        reuse_world = evaluate(candidate, recovery_cases("reuse", [160, 192, 224, 32]))
        (reuse_root / "sealed-recovery-reuse-world.json").write_text(json.dumps(reuse_world, indent=2, sort_keys=True) + "\n")
        if reuse_world["passed"]:
            final, reuse_transition = final_subject(p82, installed, reuse["binding"], reuse_world)
    fixed_control = None
    if control:
        fixed_control = evaluate(control["decision"]["selected_candidate"], recovery_cases("reuse", [160, 192, 224, 32]))
        (run / "post-seal-fixed-delay-control.json").write_text(json.dumps(fixed_control, indent=2, sort_keys=True) + "\n")
    checks = {
        "two_fresh_actors": bool(actor["binding"] and reuse and reuse["binding"]),
        "matched_selector_choices": bool(active and control and active["decision"]["selected_candidate"]["strategy"]["kind"] == "latency-relative" and control["decision"]["selected_candidate"]["strategy"]["kind"] == "fixed-delay"),
        "active_beats_unchanged_cross_domain": bool(world and world["selected_results"]["active"]["passed"] and world["selected_results"]["active"]["shifted_pass_count"] == 3 and not world["selected_results"]["unchanged-control"]["passed"] and world["selected_results"]["unchanged-control"]["shifted_pass_count"] == 0),
        "reserve_floor_preserved": reserve_floor["passed"] and reserve_floor["distinguishing_count"] == 9,
        "recovery_capability_installed": bool(installation and runtime.identity_conforms(installed) and capability["strategy"]["kind"] == "latency-relative"),
        "later_reuse_without_revision": bool(reuse_world and reuse_world["passed"] and reuse_world["shifted_pass_count"] == 3 and reuse["action"]["strategy"] == capability["strategy"]),
        "post_seal_fixed_control_fails": bool(fixed_control and not fixed_control["passed"] and fixed_control["shifted_pass_count"] == 0 and fixed_control["control_pass_count"] == 1),
        "selector_erasure_reproduces_control": bool(actor["binding"] and select(initial_selector, actor["binding"])["selected_candidate"] == control["decision"]["selected_candidate"]),
        "both_capability_families_retained": bool(final.get("adaptive_contact_strategy_capabilities") and final.get("recovery_cadence_capabilities")),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open" and final["cross_domain_scheduler"]["cycle"] == 2 and "contradictory operating regime" in final["continuation"]["next_opening"],
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0143-cross-domain-constitutional-selector-transfer-driver",
        "source_subject_digest": parent["artifact_digest"],
        "portfolio_actor": p82.compact(actor),
        "active_selection": active,
        "unchanged_control_selection": control,
        "matched_recovery_world": world,
        "reserve_no_regression": reserve_floor,
        "installation_receipt": installation,
        "later_reuse": p82.compact(reuse) if reuse else None,
        "later_reuse_world": reuse_world,
        "later_reuse_transition": reuse_transition,
        "post_seal_fixed_control": fixed_control,
        "checks": checks,
        "cross_domain_selector_transfer_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": int(actor is not None) + int(reuse is not None),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
