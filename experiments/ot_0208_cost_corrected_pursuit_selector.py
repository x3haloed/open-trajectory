from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0206_selected_ledger_world_contact.py"
BASE_SHA256 = "ceba5d53dfae5c10d74c4fe197468969840d93039e44a2496551c76f803c00cc"
PARENT_DIGEST = "a3bcf6b1505a80338b466088525019cc54cce2b6e4669ab8391eaa6e6b2ad874"
SELECTOR_DIGEST = "eb8053c78554d0821056386e3150a9e3d41d6671a116e1ef59f52e89b3e8f6e9"
LEDGER_DIGEST = "6565a30d8bc35b3f86ccffcc4698f8451204f50a7d471a969217e799f597aa80"
LEDGER_COMPLETION_DIGEST = "fa64fd10f7c4457dacf129a790c8693bc75ad8f8d23ec93a9d540efc40bd2407"
WORLD_SCHEMA = REPO / "spec/ot-0208-cost-world-author.schema.json"
CORRECTOR_SCHEMA = REPO / "spec/ot-0208-selector-corrector.schema.json"
FEATURES = {"decision_ready_signal", "checkpoint_cost", "independent_contacts", "reversible_branches"}
OPS = {"add", "subtract", "multiply"}
TOKEN = re.compile(r"[a-z][a-z0-9-]{2,47}")


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0206 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0208_frozen_runtime_base", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.authority_base


def net_value(candidate: dict[str, Any]) -> int:
    return candidate["independent_contacts"] + candidate["reversible_branches"] - candidate["decision_ready_signal"] * candidate["checkpoint_cost"]


def extrema(portfolio: dict[str, Any], score) -> list[str]:
    live = [candidate for candidate in portfolio["candidates"] if not candidate["blocked"]]
    values = [score(candidate) for candidate in live]
    best = max(values)
    return [candidate["candidate_id"] for candidate in live if score(candidate) == best]


def valid_candidate(value: Any) -> bool:
    keys = {"candidate_id", "blocked", "decision_ready_signal", "checkpoint_cost", "independent_contacts", "reversible_branches"}
    return bool(
        isinstance(value, dict)
        and set(value) == keys
        and isinstance(value.get("candidate_id"), str)
        and TOKEN.fullmatch(value["candidate_id"])
        and not value["candidate_id"].startswith("replace-")
        and isinstance(value.get("blocked"), bool)
        and isinstance(value.get("decision_ready_signal"), int)
        and 1 <= value["decision_ready_signal"] <= 12
        and isinstance(value.get("checkpoint_cost"), int)
        and 1 <= value["checkpoint_cost"] <= 8
        and isinstance(value.get("independent_contacts"), int)
        and 0 <= value["independent_contacts"] <= 24
        and isinstance(value.get("reversible_branches"), int)
        and 0 <= value["reversible_branches"] <= 24
    )


def valid_portfolio(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"portfolio_id", "candidates"} or not isinstance(value.get("portfolio_id"), str) or not TOKEN.fullmatch(value["portfolio_id"]) or value["portfolio_id"].startswith("replace-"):
        return False
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 5 or not all(valid_candidate(candidate) for candidate in candidates):
        return False
    if len({candidate["candidate_id"] for candidate in candidates}) != 5 or sum(candidate["blocked"] for candidate in candidates) != 1:
        return False
    old, optimal = extrema(value, lambda candidate: candidate["decision_ready_signal"]), extrema(value, net_value)
    yield_only = extrema(value, lambda candidate: candidate["independent_contacts"] + candidate["reversible_branches"])
    effort_only = extrema(value, lambda candidate: -(candidate["decision_ready_signal"] * candidate["checkpoint_cost"]))
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    return len(old) == len(optimal) == len(yield_only) == len(effort_only) == 1 and old != optimal and yield_only != optimal and effort_only != optimal and net_value(by_id[old[0]]) < 0 and net_value(by_id[optimal[0]]) > 0


def valid_world(value: Any) -> bool:
    return bool(isinstance(value, dict) and set(value) == {"world_id", "portfolios"} and isinstance(value.get("world_id"), str) and TOKEN.fullmatch(value["world_id"]) and not value["world_id"].startswith("replace-") and isinstance(value.get("portfolios"), list) and len(value["portfolios"]) == 2 and all(valid_portfolio(portfolio) for portfolio in value["portfolios"]) and len({portfolio["portfolio_id"] for portfolio in value["portfolios"]}) == 2)


def valid_ast(node: Any, depth: int = 1) -> bool:
    if not isinstance(node, dict) or depth > 4:
        return False
    if node.get("op") == "feature":
        return set(node) == {"op", "name"} and node.get("name") in FEATURES
    if node.get("op") == "constant":
        return set(node) == {"op", "value"} and isinstance(node.get("value"), int) and -24 <= node["value"] <= 24
    return bool(node.get("op") in OPS and set(node) == {"op", "left", "right"} and valid_ast(node["left"], depth + 1) and valid_ast(node["right"], depth + 1))


def execute_ast(node: dict[str, Any], candidate: dict[str, Any]) -> int:
    if node["op"] == "feature":
        return candidate[node["name"]]
    if node["op"] == "constant":
        return node["value"]
    left, right = execute_ast(node["left"], candidate), execute_ast(node["right"], candidate)
    if node["op"] == "add":
        return left + right
    if node["op"] == "subtract":
        return left - right
    return left * right


CORRECTION_KEYS = {"action", "selector_id", "rationale", "direction", "blocked_policy", "tie_policy", "score_program"}


def valid_correction(value: Any) -> bool:
    return bool(isinstance(value, dict) and set(value) == CORRECTION_KEYS and value.get("action") in {"revise", "surrender-and-replace"} and isinstance(value.get("selector_id"), str) and TOKEN.fullmatch(value["selector_id"]) and value["selector_id"] != "decision-ready-signal-selector" and isinstance(value.get("rationale"), str) and value["rationale"].strip() and value.get("direction") == "maximize" and value.get("blocked_policy") == "exclude" and value.get("tie_policy") == "preserve-all-extrema" and valid_ast(value.get("score_program")))


EXPECTED_PROGRAM = {"op": "subtract", "left": {"op": "add", "left": {"op": "feature", "name": "independent_contacts"}, "right": {"op": "feature", "name": "reversible_branches"}}, "right": {"op": "multiply", "left": {"op": "feature", "name": "decision_ready_signal"}, "right": {"op": "feature", "name": "checkpoint_cost"}}}


def selected(program: dict[str, Any], portfolio: dict[str, Any]) -> list[str]:
    return extrema(portfolio, lambda candidate: execute_ast(program, candidate))


def evaluate(program: Any, portfolios: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    if not valid_ast(program):
        return {"case_count": len(portfolios), "pass_count": 0, "passed": False, "rows": rows}
    for portfolio in portfolios:
        observed, expected = selected(program, portfolio), extrema(portfolio, net_value)
        rows.append({"portfolio_id": portfolio["portfolio_id"], "observed": observed, "expected": expected, "passed": observed == expected})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "passed": bool(rows) and all(row["passed"] for row in rows), "rows": rows}


OLD_PROGRAM = {"op": "feature", "name": "decision_ready_signal"}
YIELD_PROGRAM = {"op": "add", "left": {"op": "feature", "name": "independent_contacts"}, "right": {"op": "feature", "name": "reversible_branches"}}
EFFORT_PROGRAM = {"op": "subtract", "left": {"op": "constant", "value": 0}, "right": {"op": "multiply", "left": {"op": "feature", "name": "decision_ready_signal"}, "right": {"op": "feature", "name": "checkpoint_cost"}}}


def sample_portfolio(prefix: str) -> dict[str, Any]:
    return {"portfolio_id": f"{prefix}-portfolio", "candidates": [
        {"candidate_id": f"{prefix}-checkpoint-heavy", "blocked": False, "decision_ready_signal": 10, "checkpoint_cost": 5, "independent_contacts": 3, "reversible_branches": 2},
        {"candidate_id": f"{prefix}-net-optimum", "blocked": False, "decision_ready_signal": 6, "checkpoint_cost": 1, "independent_contacts": 12, "reversible_branches": 4},
        {"candidate_id": f"{prefix}-yield-only", "blocked": False, "decision_ready_signal": 8, "checkpoint_cost": 3, "independent_contacts": 20, "reversible_branches": 1},
        {"candidate_id": f"{prefix}-effort-only", "blocked": False, "decision_ready_signal": 2, "checkpoint_cost": 1, "independent_contacts": 2, "reversible_branches": 1},
        {"candidate_id": f"{prefix}-blocked-lure", "blocked": True, "decision_ready_signal": 12, "checkpoint_cost": 1, "independent_contacts": 24, "reversible_branches": 24},
    ]}


def world_seed(root: Path, parent: dict[str, Any], index: int) -> Path:
    seed = root / "world-seed"; seed.mkdir()
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "retained-selector.json": parent["pursuit_selector_capabilities"][-1], "completed-ledger-consequence.json": parent["selector_consequence_receipts"][-1], "world-portfolios.json": {"world_id": "replace-world", "portfolios": []}, "mutation-envelope.json": {"editable": ["world-portfolios.json"], "immutable": ["subject-position.json", "retained-selector.json", "completed-ledger-consequence.json", "outcome-contract.json", "check_world.py"]}, "outcome-contract.json": {"authority": "ot-0208-independent-net-continuation-value", "formula": "independent_contacts + reversible_branches - decision_ready_signal * checkpoint_cost", "portfolio_count": 2, "candidate_count": 5, "public_portfolio_index": 1, "hidden_portfolio_index": 2}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    checker = '''import json,re\nfrom pathlib import Path\nT=re.compile(r"[a-z][a-z0-9-]{2,47}")\ndef score(c): return c["independent_contacts"]+c["reversible_branches"]-c["decision_ready_signal"]*c["checkpoint_cost"]\ndef ext(p,f):\n live=[c for c in p["candidates"] if not c["blocked"]]; best=max(f(c) for c in live); return [c["candidate_id"] for c in live if f(c)==best]\ndef cand(c):\n k={"candidate_id","blocked","decision_ready_signal","checkpoint_cost","independent_contacts","reversible_branches"}; return isinstance(c,dict) and set(c)==k and isinstance(c["candidate_id"],str) and T.fullmatch(c["candidate_id"]) and not c["candidate_id"].startswith("replace-") and isinstance(c["blocked"],bool) and isinstance(c["decision_ready_signal"],int) and 1<=c["decision_ready_signal"]<=12 and isinstance(c["checkpoint_cost"],int) and 1<=c["checkpoint_cost"]<=8 and isinstance(c["independent_contacts"],int) and 0<=c["independent_contacts"]<=24 and isinstance(c["reversible_branches"],int) and 0<=c["reversible_branches"]<=24\ndef port(p):\n if not isinstance(p,dict) or set(p)!={"portfolio_id","candidates"} or not isinstance(p["portfolio_id"],str) or not T.fullmatch(p["portfolio_id"]) or p["portfolio_id"].startswith("replace-") or not isinstance(p["candidates"],list) or len(p["candidates"])!=5 or not all(cand(c) for c in p["candidates"]): return False\n cs=p["candidates"]; old=ext(p,lambda c:c["decision_ready_signal"]); opt=ext(p,score); y=ext(p,lambda c:c["independent_contacts"]+c["reversible_branches"]); e=ext(p,lambda c:-(c["decision_ready_signal"]*c["checkpoint_cost"])); by={c["candidate_id"]:c for c in cs}; return len({c["candidate_id"] for c in cs})==5 and sum(c["blocked"] for c in cs)==1 and len(old)==len(opt)==len(y)==len(e)==1 and old!=opt and y!=opt and e!=opt and score(by[old[0]])<0 and score(by[opt[0]])>0\nw=json.loads(Path("world-portfolios.json").read_text()); ps=w.get("portfolios") if isinstance(w,dict) else None; ok=isinstance(w,dict) and set(w)=={"world_id","portfolios"} and isinstance(w.get("world_id"),str) and T.fullmatch(w["world_id"]) and not w["world_id"].startswith("replace-") and isinstance(ps,list) and len(ps)==2 and all(port(p) for p in ps) and len({p["portfolio_id"] for p in ps})==2; print(json.dumps({"passed":bool(ok)},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''
    (seed / "check_world.py").write_text(checker)
    (seed / "README.md").write_text("Author two materially different five-candidate pursuit portfolios for independent selector consequence. Objective net continuation value is contacts plus reversible branches minus checkpoint count times checkpoint cost. In each portfolio the old checkpoint-count maximum must be uniquely harmful and differ from the unique positive net optimum; yield-only and effort-only choices must also differ from the optimum. Exactly one candidate is blocked. Portfolio one will be public correction contact; portfolio two will be sealed hidden consequence. Replace the empty shell in world-portfolios.json, run python3 check_world.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_world(context, prior131, root: Path, label: str, parent: dict[str, Any], index: int) -> dict[str, Any]:
    seed = world_seed(root, parent, index)
    output, base_audit, workspace, _ = context.run_actor(label, seed, WORLD_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        world = json.loads((workspace / "world-portfolios.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): world, immutable_ok = None, False
    valid = bool(valid_world(world) and immutable_ok and output and output.get("action") == "author-selector-cost-world")
    audit = context.audit_actor(label, output, base_audit, valid, ["world-portfolios.json"])
    if valid:
        local_world_id = world["world_id"]; world = copy.deepcopy(world); world["world_id"] = f"sealed-cost-world-{index:02d}"
        for position, portfolio in enumerate(world["portfolios"], 1): portfolio["portfolio_id"] = f"sealed-cost-world-{index:02d}-portfolio-{position}"
    else: local_world_id = None
    return {"output": output, "audit": audit, "world": world, "local_world_id": local_world_id, "accepted": valid and prior131.audit_accepted(audit)}


def public_receipts(portfolios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"portfolio": portfolio, "old_selection": extrema(portfolio, lambda candidate: candidate["decision_ready_signal"]), "net_values": {candidate["candidate_id"]: net_value(candidate) for candidate in portfolio["candidates"]}, "optimal_selection": extrema(portfolio, net_value)} for portfolio in portfolios]


def corrector_seed(root: Path, parent: dict[str, Any], public: list[dict[str, Any]]) -> Path:
    seed = root / "corrector-seed"; seed.mkdir()
    correction = {"action": "revise", "selector_id": "replace-cost-aware-selector", "rationale": "Replace with a consequence-grounded arithmetic selector.", "direction": "maximize", "blocked_policy": "exclude", "tie_policy": "preserve-all-extrema", "score_program": OLD_PROGRAM}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "current-subject.json": parent, "retained-selector.json": parent["pursuit_selector_capabilities"][-1], "completed-ledger-consequence.json": parent["selector_consequence_receipts"][-1], "public-cost-consequence.json": public_receipts(public), "selector-language.json": {"features": sorted(FEATURES), "operators": sorted(OPS), "maximum_depth": 4, "direction": "maximize", "blocked_policy": "exclude", "tie_policy": "preserve-all-extrema"}, "selector-correction.json": correction, "mutation-envelope.json": {"editable": ["selector-correction.json"], "immutable": ["subject-position.json", "current-subject.json", "retained-selector.json", "completed-ledger-consequence.json", "public-cost-consequence.json", "selector-language.json", "check_correction.py"]}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    expected = json.dumps(EXPECTED_PROGRAM, sort_keys=True)
    (seed / "check_correction.py").write_text(f'''import json,re\nfrom pathlib import Path\nc=json.loads(Path("selector-correction.json").read_text()); keys={{"action","selector_id","rationale","direction","blocked_policy","tie_policy","score_program"}}; expected=json.loads({expected!r}); ok=isinstance(c,dict) and set(c)==keys and c.get("action") in {{"revise","surrender-and-replace"}} and isinstance(c.get("selector_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,47}}",c["selector_id"]) and c["selector_id"]!="decision-ready-signal-selector" and isinstance(c.get("rationale"),str) and bool(c["rationale"].strip()) and c.get("direction")=="maximize" and c.get("blocked_policy")=="exclude" and c.get("tie_policy")=="preserve-all-extrema" and c.get("score_program")==expected; print(json.dumps({{"passed":bool(ok)}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Use the independent public consequence to retain, revise, or surrender the exact inherited pursuit selector. Author one generic bounded arithmetic score program over the visible features. It must select objective net continuation value—independent contacts plus reversible branches minus checkpoint effort—while excluding blocked pursuits and preserving ties. Hidden portfolios are sealed and unavailable. Edit only selector-correction.json, run python3 check_correction.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_corrector(context, prior131, p82, root: Path, label: str, parent: dict[str, Any], public: list[dict[str, Any]], hidden: list[dict[str, Any]]) -> dict[str, Any]:
    seed = corrector_seed(root, parent, public)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        correction = json.loads((workspace / "selector-correction.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): correction, immutable_ok = None, False
    valid = bool(valid_correction(correction) and immutable_ok and output and output.get("action") == "correct-harmful-pursuit-selector")
    audit = context.audit_actor(label, output, base_audit, valid, ["selector-correction.json"])
    public_result = evaluate(correction["score_program"], public) if valid else evaluate(None, public)
    hidden_result = evaluate(correction["score_program"], hidden) if valid else evaluate(None, hidden)
    binding = None
    if valid and public_result["passed"] and hidden_result["passed"] and prior131.audit_accepted(audit):
        body = {"authority": "ot-0208-bound-cost-corrected-pursuit-selector", "source_subject_digest": parent["artifact_digest"], "inherited_selector_binding_digest": SELECTOR_DIGEST, "actor_patch_digest": audit["patch_digest"], "correction": correction, "public_result": public_result, "hidden_result": hidden_result}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "correction": correction, "public_result": public_result, "hidden_result": hidden_result, "binding": binding, "passed": binding is not None}


def main() -> int:
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0208").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0207", "open-subject-after-selected-ledger-completion.json"); result207 = selector_base.load_artifact(p82, repo, store, "OT-0207", "encounter-namespaced-ledger-contact-aggregate.json")
    sample_a, sample_b = sample_portfolio("fixture-a"), sample_portfolio("fixture-b"); sample_world = {"world_id": "fixture-cost-world", "portfolios": [sample_a, sample_b]}; expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]
    route_floor = previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression); operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0207_exact_promotion": result207["observer_disposition"] == "promoted" and result207["final_subject_digest"] == PARENT_DIGEST, "selector_exact": parent["pursuit_selector_capabilities"][-1]["selector_binding_digest"] == SELECTOR_DIGEST, "ledger_exact": parent["contact_correction_ledger_capabilities"][-1]["binding_digest"] == LEDGER_DIGEST and parent["developmental_completion_receipts"][-1]["receipt_digest"] == LEDGER_COMPLETION_DIGEST, "sample_world_valid": valid_world(sample_world), "expected_program_valid": valid_ast(EXPECTED_PROGRAM) and evaluate(EXPECTED_PROGRAM, [sample_a, sample_b])["passed"], "three_controls_fail": all(not evaluate(program, [sample_a, sample_b])["passed"] for program in (OLD_PROGRAM, YIELD_PROGRAM, EFFORT_PROGRAM)), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schemas_present": WORLD_SCHEMA.is_file() and CORRECTOR_SCHEMA.is_file()}, "source_subject_digest": parent["artifact_digest"], "selector_binding_digest": SELECTOR_DIGEST}; fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only: print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0208 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    world_rows = []
    for index in range(1, 5):
        actor_root = run / f"world-{index:02d}-authoring"; actor_root.mkdir(); world_rows.append({"index": index, "choice": run_world(context, prior131, actor_root, f"world-{index:02d}", parent, index)})
    worlds_pass = len(world_rows) == 4 and all(row["choice"]["accepted"] for row in world_rows); worlds = [row["choice"]["world"] for row in world_rows] if worlds_pass else []
    public = [world["portfolios"][0] for world in worlds]; hidden = [world["portfolios"][1] for world in worlds]
    controls = {"unchanged": evaluate(OLD_PROGRAM, hidden), "yield_only": evaluate(YIELD_PROGRAM, hidden), "effort_only": evaluate(EFFORT_PROGRAM, hidden)} if worlds_pass else {}
    corrector_rows = []
    if worlds_pass:
        for index in range(1, 5):
            actor_root = run / f"corrector-{index:02d}-authoring"; actor_root.mkdir(); corrector_rows.append({"index": index, "choice": run_corrector(context, prior131, p82, actor_root, f"corrector-{index:02d}", parent, public, hidden)})
    audits = [row["choice"]["audit"] for row in world_rows] + [row["choice"]["audit"] for row in corrector_rows]
    checks = {"eight_fresh_actors_accepted": len(audits) == 8 and all(prior131.audit_accepted(audit) for audit in audits), "four_independent_harmful_worlds": worlds_pass, "four_correctors_public_4_of_4": len(corrector_rows) == 4 and all(row["choice"]["public_result"]["pass_count"] == 4 for row in corrector_rows), "four_correctors_hidden_4_of_4": len(corrector_rows) == 4 and all(row["choice"]["hidden_result"]["pass_count"] == 4 for row in corrector_rows), "unchanged_hidden_0_of_4": controls.get("unchanged", {}).get("pass_count") == 0, "yield_only_hidden_0_of_4": controls.get("yield_only", {}).get("pass_count") == 0, "effort_only_hidden_0_of_4": controls.get("effort_only", {}).get("pass_count") == 0, "correction_structurally_changes_selector": len(corrector_rows) == 4 and all(row["choice"]["correction"]["score_program"] != OLD_PROGRAM for row in corrector_rows), "ledger_and_completion_exact": parent["contact_correction_ledger_capabilities"][-1]["binding_digest"] == LEDGER_DIGEST and parent["developmental_completion_receipts"][-1]["receipt_digest"] == LEDGER_COMPLETION_DIGEST, "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values()); final = parent
    if checks["passed"]:
        binding = corrector_rows[0]["choice"]["binding"]; child = copy.deepcopy(parent); child.pop("artifact_digest", None)
        capability_body = {"authority": "ot-0208-executable-cost-corrected-pursuit-selector", "selector_binding_digest": binding["binding_digest"], "selector": binding["correction"]}; child["pursuit_selector_capabilities"] = [*child.get("pursuit_selector_capabilities", []), capability_body]
        receipt_body = {"authority": "ot-0208-objective-selector-correction", "source_subject_digest": parent["artifact_digest"], "inherited_selector_binding_digest": SELECTOR_DIGEST, "corrected_selector_binding_digest": binding["binding_digest"], "world_digests": [p82.digest(world) for world in worlds], "corrected_hidden_result": binding["hidden_result"], "unchanged_hidden_result": controls["unchanged"], "disposition": binding["correction"]["action"]}; child["selector_correction_receipts"] = [*child.get("selector_correction_receipts", []), {**receipt_body, "receipt_digest": p82.digest(receipt_body)}]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Use the corrected pursuit selector to choose and execute the next subject-authored pursuit."}; child["unresolved"] = "Can the corrected cost-aware selector recur on a subject-authored pursuit outside the ledger world?"; candidate = p82.seal(child)
        if runtime.identity_conforms(candidate): final = candidate
        else: checks["successor_identity_conforms"] = False; checks["passed"] = False
    checks.setdefault("successor_identity_conforms", checks["passed"] and final is not parent)
    if not checks["successor_identity_conforms"]: checks["passed"] = False; final = parent
    result = {"authority": "ot-0208-cost-corrected-pursuit-selector", "source_subject_digest": parent["artifact_digest"], "inherited_selector_binding_digest": SELECTOR_DIGEST, "world_rows": [{"index": row["index"], "choice": p82.compact(row["choice"])} for row in world_rows], "corrector_rows": [{"index": row["index"], "choice": p82.compact(row["choice"])} for row in corrector_rows], "controls": controls, "checks": checks, "route_floor": route_floor, "identity_floor": identity, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": len(audits)}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
