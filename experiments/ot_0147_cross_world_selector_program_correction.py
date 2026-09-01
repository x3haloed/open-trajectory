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
BASE_PATH = ROOT / "ot_0146_actor_authored_selector_program.py"
BASE_SHA256 = "26964ce0b04427a949bc33633b771970ea7edcd9e05a24ec0340682507f6e6a5"
PARENT_DIGEST = "d300f2d5fb158a7650eab45e8d3a2c0c3445b216e2f4f9aef830a6bdebbef54c"
PORTFOLIO_SCHEMA = REPO / "spec/ot-0147-throughput-portfolio.schema.json"
CORRECTION_SCHEMA = REPO / "spec/ot-0147-selector-program-correction.schema.json"
GRAMMAR_VERSION = "ot-0147-bounded-output-selector-expression-v2"
THROUGHPUT_CONTEXT = {"admissible_observed_maximum": 256, "minimum_required_output": 256, "maximum_allowed_output": 1024}
DEADLINE_CONTEXT = {"admissible_observed_maximum": 256, "minimum_required_output": 0, "maximum_allowed_output": 64}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0146 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0147_frozen_ot0146", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot145 = previous.previous
p82base = previous.p82base
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def throughput_cases(prefix: str, demands: list[int]) -> list[dict[str, Any]]:
    return [{"case_id": f"{prefix}-{index + 1}-demand-{demand}", "observed_demand": demand, "required_output": demand, "shifted": demand > 64} for index, demand in enumerate(demands)]


def valid_throughput_candidate(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or set(candidate) != {"candidate_id", "strategy", "rationale", "surrender_condition"}:
        return False
    if not isinstance(candidate["candidate_id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", candidate["candidate_id"]):
        return False
    if not prior131.valid_text(candidate["rationale"]) or not prior131.valid_text(candidate["surrender_condition"]):
        return False
    strategy = candidate["strategy"]
    if not isinstance(strategy, dict):
        return False
    if strategy.get("kind") == "throughput-relative":
        return set(strategy) == {"kind", "factor"} and strategy["factor"] == 1
    if strategy.get("kind") == "throughput-capped":
        return set(strategy) == {"kind", "factor", "cap"} and strategy["factor"] == 1 and strategy["cap"] == 64
    return False


def simulate(candidate: dict[str, Any], maximum: int) -> int:
    strategy = candidate["strategy"]
    raw = strategy["factor"] * maximum
    if strategy["kind"] == "deadline-capped":
        return min(raw, strategy["deadline"])
    if strategy["kind"] == "throughput-capped":
        return min(raw, strategy["cap"])
    return raw


def evaluate_throughput(candidate: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [{"case_id": case["case_id"], "shifted": case["shifted"], "produced_output": simulate(candidate, case["observed_demand"]), "required_output": case["required_output"], "passed": simulate(candidate, case["observed_demand"]) >= case["required_output"]} for case in cases]
    shifted = [row for row in rows if row["shifted"]]
    controls = [row for row in rows if not row["shifted"]]
    return {"candidate_id": candidate["candidate_id"], "strategy": candidate["strategy"], "cases": rows, "shifted_count": len(shifted), "shifted_pass_count": sum(row["passed"] for row in shifted), "control_count": len(controls), "control_pass_count": sum(row["passed"] for row in controls), "passed": all(row["passed"] for row in rows)}


def validate_portfolio(portfolio: Any, public_cases: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    if not isinstance(portfolio, dict) or set(portfolio) != {"question", "candidates"} or not prior131.valid_text(portfolio.get("question")):
        return False, []
    candidates = portfolio.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2 or not all(valid_throughput_candidate(item) for item in candidates):
        return False, []
    if len({item["candidate_id"] for item in candidates}) != 2 or {item["strategy"]["kind"] for item in candidates} != {"throughput-relative", "throughput-capped"}:
        return False, []
    evaluations = [evaluate_throughput(item, public_cases) for item in candidates]
    return all(item["passed"] for item in evaluations), evaluations


def valid_expression(expr: Any, depth: int = 0) -> bool:
    if depth > 8 or not isinstance(expr, dict) or not isinstance(expr.get("op"), str):
        return False
    op = expr["op"]
    if op in {"public-pass", "simulated-at-envelope-maximum", "strategy-field-count", "candidate-id"}:
        return set(expr) == {"op"}
    if op == "context":
        return set(expr) == {"op", "key"} and expr["key"] in {"admissible_observed_maximum", "minimum_required_output", "maximum_allowed_output"}
    if op == "not":
        return set(expr) == {"op", "arg"} and valid_expression(expr["arg"], depth + 1)
    return op in {"gt", "lt", "eq"} and set(expr) == {"op", "left", "right"} and valid_expression(expr["left"], depth + 1) and valid_expression(expr["right"], depth + 1)


def valid_program(program: Any) -> bool:
    return bool(isinstance(program, dict) and set(program) == {"program_id", "score", "rationale", "surrender_condition"} and isinstance(program["program_id"], str) and program["program_id"].startswith("selector-") and isinstance(program["score"], list) and 1 <= len(program["score"]) <= 6 and all(valid_expression(item) for item in program["score"]) and prior131.valid_text(program["rationale"]) and prior131.valid_text(program["surrender_condition"]))


def expression_value(expr: dict[str, Any], candidate: dict[str, Any], public_pass: bool, context: dict[str, int]) -> Any:
    op = expr["op"]
    if op == "public-pass": return public_pass
    if op == "simulated-at-envelope-maximum": return simulate(candidate, context["admissible_observed_maximum"])
    if op == "strategy-field-count": return len(candidate["strategy"])
    if op == "candidate-id": return candidate["candidate_id"]
    if op == "context": return context[expr["key"]]
    if op == "not": return not bool(expression_value(expr["arg"], candidate, public_pass, context))
    left = expression_value(expr["left"], candidate, public_pass, context)
    right = expression_value(expr["right"], candidate, public_pass, context)
    return left > right if op == "gt" else left < right if op == "lt" else left == right


def select(program: dict[str, Any], portfolio: dict[str, Any], context: dict[str, int]) -> dict[str, Any]:
    ranked = []
    for item in portfolio["public_candidates"]:
        candidate = item["candidate"]
        key = [expression_value(expr, candidate, item["public_evaluation"]["passed"], context) for expr in program["score"]]
        ranked.append({"candidate": candidate, "rank_key": key})
    ranked.sort(key=lambda row: tuple(row["rank_key"]))
    return {"selected_candidate": ranked[0]["candidate"], "ranked": ranked}


GRAMMAR = {"version": GRAMMAR_VERSION, "selection": "ascending lexicographic score; false sorts before true", "leaf_operations": ["public-pass", "simulated-at-envelope-maximum", "strategy-field-count", "candidate-id"], "context_operation": {"op": "context", "keys": ["admissible_observed_maximum", "minimum_required_output", "maximum_allowed_output"]}, "unary_operations": ["not"], "binary_operations": ["gt", "lt", "eq"], "limits": {"maximum_depth": 8, "maximum_score_terms": 6}, "named_derived_features": []}


PORTFOLIO_CHECKER = '''import json
from pathlib import Path
p = json.loads(Path("throughput-portfolio.json").read_text())
c = p.get("candidates", [])
kinds = {item.get("strategy", {}).get("kind") for item in c}
passed = bool(len(c) == 2 and len({item.get("candidate_id") for item in c}) == 2 and kinds == {"throughput-relative", "throughput-capped"} and all(item.get("strategy", {}).get("factor") == 1 for item in c) and next(item for item in c if item["strategy"]["kind"] == "throughput-capped")["strategy"].get("cap") == 64 and all(isinstance(item.get("rationale"), str) and item["rationale"].strip() and isinstance(item.get("surrender_condition"), str) and item["surrender_condition"].strip() for item in c))
print(json.dumps({"passed": passed, "candidate_count": len(c)}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''


def portfolio_seed(root: Path, subject: dict[str, Any], public_cases: list[dict[str, Any]], ordinal: int) -> Path:
    seed = root / "portfolio-seed"
    seed.mkdir()
    files = {"subject-position.json": base.active_position(subject), "throughput-language.json": {"required_families": ["throughput-relative", "throughput-capped"], "factor": 1, "cap": 64, "objective": "produced_output must meet observed demand", "named_derived_features": []}, "public-throughput-cases.json": public_cases, "throughput-portfolio.json": {"question": f"Which throughput amendment should govern portfolio {ordinal}?", "candidates": []}, "mutation-envelope.json": {"editable": ["throughput-portfolio.json"], "immutable": ["subject-position.json", "throughput-language.json", "public-throughput-cases.json", "check_portfolio.py"]}}
    for name, value in files.items(): (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "check_portfolio.py").write_text(PORTFOLIO_CHECKER)
    (seed / "README.md").write_text("Author one factor-one throughput-relative and one factor-one throughput-capped-at-64 amendment. Run python3 check_portfolio.py, edit only throughput-portfolio.json, inspect the exact diff, and report truthfully.\n")
    return seed


def run_portfolio_actor(context, p82, root: Path, subject: dict[str, Any], public_cases: list[dict[str, Any]], ordinal: int) -> dict[str, Any]:
    label = f"throughput-portfolio-{ordinal}-author"
    seed = portfolio_seed(root, subject, public_cases, ordinal)
    output, base_audit, workspace, _ = context.run_actor(label, seed, PORTFOLIO_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        portfolio = json.loads((workspace / "throughput-portfolio.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        portfolio, immutable_ok = None, False
    valid, evaluations = validate_portfolio(portfolio, public_cases)
    audit = context.audit_actor(label, output, base_audit, bool(valid and immutable_ok), ["throughput-portfolio.json"])
    binding = None
    if valid and immutable_ok and prior131.audit_accepted(audit):
        body = {"authority": "ot-0147-bound-throughput-portfolio", "source_subject_digest": subject["artifact_digest"], "actor_patch_digest": audit["patch_digest"], "portfolio": portfolio, "public_candidates": [{"candidate": candidate, "public_evaluation": evaluation} for candidate, evaluation in zip(portfolio["candidates"], evaluations)]}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "portfolio": portfolio, "binding": binding}


def bind_selection(p82, subject: dict[str, Any], program_binding_digest: str, program: dict[str, Any], portfolio: dict[str, Any], role: str) -> dict[str, Any]:
    decision = select(program, portfolio, THROUGHPUT_CONTEXT)
    body = {"authority": "ot-0147-bound-throughput-program-selection", "role": role, "source_subject_digest": subject["artifact_digest"], "program_binding_digest": program_binding_digest, "portfolio_binding_digest": portfolio["binding_digest"], "context": THROUGHPUT_CONTEXT, "decision": decision}
    return {**body, "binding_digest": p82.digest(body)}


def world_receipt(p82, portfolio: dict[str, Any], selections: list[dict[str, Any]], cases: list[dict[str, Any]], authority: str) -> dict[str, Any]:
    evaluations = {candidate["candidate_id"]: evaluate_throughput(candidate, cases) for candidate in portfolio["portfolio"]["candidates"]}
    body = {"authority": authority, "portfolio_binding_digest": portfolio["binding_digest"], "selection_binding_digests": [item["binding_digest"] for item in selections], "cases_digest": p82.digest(cases), "candidate_evaluations": evaluations, "selected_results": {item["role"]: evaluations[item["decision"]["selected_candidate"]["candidate_id"]] for item in selections}}
    return {**body, "receipt_digest": p82.digest(body)}


def retain_failure(p82, subject: dict[str, Any], portfolio: dict[str, Any], selection: dict[str, Any], world: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = selection["decision"]["selected_candidate"]["candidate_id"]
    body = {"authority": "ot-0147-retained-cross-world-program-contradiction", "source_subject_digest": subject["artifact_digest"], "portfolio_binding_digest": portfolio["binding_digest"], "selection_binding_digest": selection["binding_digest"], "world_receipt_digest": world["receipt_digest"], "selected_candidate_id": selected, "selected_result": world["candidate_evaluations"][selected], "alternative_results": {key: value for key, value in world["candidate_evaluations"].items() if key != selected}}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject); child.pop("artifact_digest", None)
    child["selector_program_contradictions"] = [*child.get("selector_program_contradictions", []), receipt]
    child["pending_selector_program_correction"] = receipt
    opening = "Open selector-program-correction-" + receipt["receipt_digest"][:12] + ": Whether the actor-authored selector program can reconcile lower and upper output requirements remains unresolved."
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}; child["continuation"] = {**child["continuation"], "next_opening": opening}; child["unresolved"] = opening.split(": ", 1)[1]
    return p82.seal(child), receipt


CORRECTION_CHECKER = r'''import json
from pathlib import Path
program = json.loads(Path("selector-program.json").read_text())
grammar = json.loads(Path("expression-grammar.json").read_text())
throughput = json.loads(Path("failed-throughput-portfolio.json").read_text())
tworld = json.loads(Path("throughput-consequence.json").read_text())
deadline = json.loads(Path("deadline-floor-portfolio.json").read_text())
dworld = json.loads(Path("deadline-floor-world.json").read_text())
contexts = json.loads(Path("operating-contexts.json").read_text())
def valid(e, depth=0):
    if depth > 8 or not isinstance(e, dict) or not isinstance(e.get("op"), str): return False
    op=e["op"]
    if op in {"public-pass","simulated-at-envelope-maximum","strategy-field-count","candidate-id"}: return set(e)=={"op"}
    if op=="context": return set(e)=={"op","key"} and e["key"] in {"admissible_observed_maximum","minimum_required_output","maximum_allowed_output"}
    if op=="not": return set(e)=={"op","arg"} and valid(e["arg"],depth+1)
    return op in {"gt","lt","eq"} and set(e)=={"op","left","right"} and valid(e["left"],depth+1) and valid(e["right"],depth+1)
def sim(c,m):
    s=c["strategy"]; raw=s["factor"]*m
    if s["kind"]=="deadline-capped": return min(raw,s["deadline"])
    if s["kind"]=="throughput-capped": return min(raw,s["cap"])
    return raw
def val(e,c,p,ctx):
    op=e["op"]
    if op=="public-pass": return p
    if op=="simulated-at-envelope-maximum": return sim(c,ctx["admissible_observed_maximum"])
    if op=="strategy-field-count": return len(c["strategy"])
    if op=="candidate-id": return c["candidate_id"]
    if op=="context": return ctx[e["key"]]
    if op=="not": return not bool(val(e["arg"],c,p,ctx))
    l,r=val(e["left"],c,p,ctx),val(e["right"],c,p,ctx)
    return l>r if op=="gt" else l<r if op=="lt" else l==r
def choose(portfolio,ctx):
    rows=[]
    for item in portfolio["public_candidates"]:
        c=item["candidate"]; rows.append((tuple(val(e,c,item["public_evaluation"]["passed"],ctx) for e in program["score"]),c["candidate_id"]))
    return min(rows)[1]
shape=set(program)=={"program_id","score","rationale","surrender_condition"} and isinstance(program.get("program_id"),str) and program["program_id"].startswith("selector-") and isinstance(program.get("score"),list) and 1<=len(program["score"])<=6 and all(valid(e) for e in program["score"]) and all(isinstance(program.get(k),str) and program[k].strip() for k in ["rationale","surrender_condition"])
t=choose(throughput,contexts["throughput"]) if shape else None; d=choose(deadline,contexts["deadline"]) if shape else None
passed=bool(shape and tworld["candidate_evaluations"][t]["passed"] and dworld["candidate_evaluations"][d]["passed"])
print(json.dumps({"passed":passed,"throughput_selected":t,"deadline_selected":d,"grammar":grammar["version"]},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def correction_seed(root: Path, subject: dict[str, Any], inherited: dict[str, Any], portfolio: dict[str, Any], world: dict[str, Any], deadline_portfolio: dict[str, Any], deadline_world: dict[str, Any]) -> Path:
    seed = root / "correction-seed"; seed.mkdir()
    files = {"subject-position.json": base.active_position(subject), "inherited-selector-program.json": inherited, "failed-throughput-portfolio.json": portfolio, "throughput-consequence.json": world, "deadline-floor-portfolio.json": deadline_portfolio, "deadline-floor-world.json": deadline_world, "operating-contexts.json": {"throughput": THROUGHPUT_CONTEXT, "deadline": DEADLINE_CONTEXT}, "expression-grammar.json": GRAMMAR, "selector-program.json": inherited, "mutation-envelope.json": {"editable": ["selector-program.json"], "immutable": ["subject-position.json","inherited-selector-program.json","failed-throughput-portfolio.json","throughput-consequence.json","deadline-floor-portfolio.json","deadline-floor-world.json","operating-contexts.json","expression-grammar.json","check_program.py"]}}
    for name,value in files.items(): (seed/name).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
    (seed/"check_program.py").write_text(CORRECTION_CHECKER)
    (seed/"README.md").write_text("Correct only selector-program.json from the exact throughput failure while preserving the deadline floor. Compose raw lower/upper output relations in the total grammar; no named feature is supplied. Run python3 check_program.py, inspect the exact diff, and report truthfully.\n")
    return seed


def deadline_world(portfolio: dict[str, Any]) -> dict[str, Any]:
    evaluations = {item["candidate"]["candidate_id"]: ot145.evaluate(item["candidate"], ot145.cases("deadline-floor", [96,128,160,64])) for item in portfolio["public_candidates"]}
    return {"candidate_evaluations": evaluations}


def run_correction_actor(context, p82, root: Path, subject: dict[str, Any], inherited: dict[str, Any], portfolio: dict[str, Any], world: dict[str, Any], deadline_portfolio: dict[str, Any]) -> dict[str, Any]:
    label="cross-world-program-corrector"; dworld=deadline_world(deadline_portfolio); seed=correction_seed(root,subject,inherited,portfolio,world,deadline_portfolio,dworld)
    output,base_audit,workspace,_=context.run_actor(label,seed,CORRECTION_SCHEMA,(seed/"README.md").read_text().strip())
    try:
        program=json.loads((workspace/"selector-program.json").read_text()); immutable=json.loads((seed/"mutation-envelope.json").read_text())["immutable"]; immutable_ok=all((workspace/name).read_bytes()==(seed/name).read_bytes() for name in immutable)
    except (OSError,json.JSONDecodeError,KeyError): program,immutable_ok=None,False
    tdecision=select(program,portfolio,THROUGHPUT_CONTEXT) if valid_program(program) else None; ddecision=select(program,deadline_portfolio,DEADLINE_CONTEXT) if valid_program(program) else None
    tselected=tdecision["selected_candidate"]["candidate_id"] if tdecision else None; dselected=ddecision["selected_candidate"]["candidate_id"] if ddecision else None
    valid=bool(tdecision and ddecision and immutable_ok and world["candidate_evaluations"][tselected]["passed"] and dworld["candidate_evaluations"][dselected]["passed"])
    audit=context.audit_actor(label,output,base_audit,valid,["selector-program.json"]); binding=None
    if valid and prior131.audit_accepted(audit):
        body={"authority":"ot-0147-bound-cross-world-corrected-program","source_subject_digest":subject["artifact_digest"],"parent_program_digest":p82.digest(inherited),"cause_world_receipt_digest":world["receipt_digest"],"actor_patch_digest":audit["patch_digest"],"grammar_version":GRAMMAR_VERSION,"program":program,"retrospective_throughput_decision":tdecision,"deadline_floor_decision":ddecision}; binding={**body,"binding_digest":p82.digest(body)}
    return {"output":output,"audit":audit,"program":program,"throughput_decision":tdecision,"deadline_decision":ddecision,"binding":binding}


def install_program(p82, subject: dict[str, Any], parent_capability: dict[str, Any], binding: dict[str, Any], selection: dict[str, Any], world: dict[str, Any], floors: dict[str, Any]) -> tuple[dict[str, Any],dict[str, Any],dict[str, Any]]:
    body={"authority":"ot-0147-cross-world-corrected-selector-program-capability","program_binding_digest":binding["binding_digest"],"program":binding["program"],"parent_capability_digest":parent_capability["capability_digest"],"held_out_selection_digest":selection["binding_digest"],"held_out_world_receipt_digest":world["receipt_digest"],"floor_digests":{key:p82.digest(value) for key,value in floors.items()}}
    capability={**body,"capability_digest":p82.digest(body)}; rb={"authority":"ot-0147-corrected-program-installation","source_subject_digest":subject["artifact_digest"],"capability_digest":capability["capability_digest"],"parent_capability_digest":parent_capability["capability_digest"]}; receipt={**rb,"receipt_digest":p82.digest(rb)}
    child=copy.deepcopy(subject); child.pop("artifact_digest",None); child["constitutional_selector_program_capabilities"]=[*child["constitutional_selector_program_capabilities"],capability]; child["constitutional_selector_program_installation_receipts"]=[*child["constitutional_selector_program_installation_receipts"],receipt]; child["pending_selector_program_correction"]=None
    opening="Open corrected-program-reuse-"+receipt["receipt_digest"][:12]+": Whether corrected cross-world selector semantics survive later exact reuse remains unresolved."; child["active_pursuit"]={**child["active_pursuit"],"next_pursuit":opening}; child["continuation"]={**child["continuation"],"next_opening":opening}; child["unresolved"]=opening.split(": ",1)[1]
    return p82.seal(child),receipt,capability


def seal_final(p82,subject:dict[str,Any],reuse:dict[str,Any],selection:dict[str,Any],world:dict[str,Any])->tuple[dict[str,Any],dict[str,Any]]:
    body={"authority":"ot-0147-corrected-program-reuse-transition","source_subject_digest":subject["artifact_digest"],"reuse_binding_digest":reuse["binding_digest"],"selection_binding_digest":selection["binding_digest"],"world_receipt_digest":world["receipt_digest"]}; receipt={**body,"receipt_digest":p82.digest(body)}; child=copy.deepcopy(subject); child.pop("artifact_digest",None); child["cross_world_selector_program_reuse_receipts"]=[*child.get("cross_world_selector_program_reuse_receipts",[]),receipt]
    question="Which materially different world should the continuing subject choose next without experiment-specific researcher selection remains unresolved."; opening="Open subject-selected-world-"+receipt["receipt_digest"][:12]+": "+question; child["active_pursuit"]={**child["active_pursuit"],"next_pursuit":opening}; child["continuation"]={**child["continuation"],"next_opening":opening,"status":"open"}; child["unresolved"]=question
    return p82.seal(child),receipt


def fixture_program()->dict[str,Any]:
    return {"program_id":"selector-output-bounds","score":[{"op":"not","arg":{"op":"public-pass"}},{"op":"lt","left":{"op":"simulated-at-envelope-maximum"},"right":{"op":"context","key":"minimum_required_output"}},{"op":"gt","left":{"op":"simulated-at-envelope-maximum"},"right":{"op":"context","key":"maximum_allowed_output"}},{"op":"strategy-field-count"},{"op":"candidate-id"}],"rationale":"Prefer public-valid candidates whose simulated output remains within the operating bounds.","surrender_condition":"Surrender when sealed consequence contradicts the bounded-output relation."}


def representative_portfolio()->dict[str,Any]:
    candidates=[{"candidate_id":"a-throughput-capped","strategy":{"kind":"throughput-capped","factor":1,"cap":64},"rationale":"Bound output.","surrender_condition":"Surrender if demand exceeds cap."},{"candidate_id":"z-throughput-relative","strategy":{"kind":"throughput-relative","factor":1},"rationale":"Meet observed demand.","surrender_condition":"Surrender if proportional output fails."}]; cases=throughput_cases("public",[32,64]); return {"portfolio":{"question":"fixture","candidates":candidates},"public_candidates":[{"candidate":c,"public_evaluation":evaluate_throughput(c,cases)} for c in candidates],"binding_digest":"fixture"}


def preflight(p82,parent:dict[str,Any],deadline_portfolio:dict[str,Any])->dict[str,Any]:
    portfolio=representative_portfolio(); inherited=parent["constitutional_selector_program_capabilities"][-1]["program"]; corrected=fixture_program(); old=select(inherited,portfolio,THROUGHPUT_CONTEXT); new=select(corrected,portfolio,THROUGHPUT_CONTEXT); hidden={c["candidate_id"]:evaluate_throughput(c,throughput_cases("hidden",[96,128,160,64])) for c in portfolio["portfolio"]["candidates"]}; dnew=select(corrected,deadline_portfolio,DEADLINE_CONTEXT); dworld=deadline_world(deadline_portfolio); reserve,recovery=ot145.floors(p82,parent)
    with tempfile.TemporaryDirectory() as directory: files=sorted(path.name for path in portfolio_seed(Path(directory),parent,throughput_cases("public",[32,64]),1).iterdir() if path.is_file())
    checks={"parent_exact_sounding_open":parent["artifact_digest"]==PARENT_DIGEST and parent["continuation"]["status"]=="open","inherited_program_harmful":not hidden[old["selected_candidate"]["candidate_id"]]["passed"],"corrected_program_passes":hidden[new["selected_candidate"]["candidate_id"]]["passed"],"deadline_floor":dworld["candidate_evaluations"][dnew["selected_candidate"]["candidate_id"]]["passed"],"prior_floors":reserve["passed"] and reserve["distinguishing_count"]==9 and recovery["passed"] and recovery["shifted_pass_count"]==3,"no_named_features":GRAMMAR["named_derived_features"]==[],"schemas_present":PORTFOLIO_SCHEMA.is_file() and CORRECTION_SCHEMA.is_file() and previous.REUSE_SCHEMA.is_file(),"seed_complete":files==["README.md","check_portfolio.py","mutation-envelope.json","public-throughput-cases.json","subject-position.json","throughput-language.json","throughput-portfolio.json"]}; checks["passed"]=all(checks.values()); return {"checks":checks,"old":old,"new":new,"deadline":dnew,"reserve_floor":reserve,"ordinary_recovery_floor":recovery}


def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args(); repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0147").resolve()
    prior92=base.mechanism.load_prior(); _,_,_,p82=base.mechanism.prior_chain(prior92); runtime=p82.load_runtime(repo,store); parent=load_artifact(p82,repo,store,"OT-0146","open-subject-with-actor-authored-selector-program.json"); prior_result=load_artifact(p82,repo,store,"OT-0146","actor-authored-selector-program-aggregate.json"); deadline_portfolio=prior_result["later_portfolio"]["binding"]; fixtures=preflight(p82,parent,deadline_portfolio); fixtures["checks"]["parent_identity"]=runtime.identity_conforms(parent); fixtures["checks"]["passed"]=all(value for key,value in fixtures["checks"].items() if key!="passed")
    if args.preflight_only: print(json.dumps({"base_sha256":BASE_SHA256,"fixtures":fixtures},indent=2,sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0147 evidence")
    run.mkdir(parents=True); (run/"fixture-conformance.json").write_text(json.dumps(fixtures,indent=2,sort_keys=True)+"\n");
    if not fixtures["checks"]["passed"]: raise SystemExit("pre-actor conformance failed")
    context=base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime,run,repo)); started=time.time(); parent_cap=parent["constitutional_selector_program_capabilities"][-1]; inherited=parent_cap["program"]
    first_root=run/"first-throughput"; first_root.mkdir(); first=run_portfolio_actor(context,p82,first_root,parent,throughput_cases("public-a",[32,64]),1); first_selection=first_world=failure_receipt=None; failure_subject=parent
    if first["binding"]:
        first_selection=bind_selection(p82,parent,parent_cap["program_binding_digest"],inherited,first["binding"],"active"); first_world=world_receipt(p82,first["binding"],[first_selection],throughput_cases("hidden-a",[96,128,160,64]),"ot-0147-first-throughput-contradiction-world"); (first_root/"sealed-world.json").write_text(json.dumps(first_world,indent=2,sort_keys=True)+"\n")
        if not first_world["selected_results"]["active"]["passed"] and any(value["passed"] for key,value in first_world["candidate_evaluations"].items() if key!=first_selection["decision"]["selected_candidate"]["candidate_id"]): failure_subject,failure_receipt=retain_failure(p82,parent,first["binding"],first_selection,first_world)
    correction_root=run/"program-correction"; correction_root.mkdir(); correction=run_correction_actor(context,p82,correction_root,failure_subject,inherited,first["binding"],first_world,deadline_portfolio) if failure_receipt else None
    held_root=run/"held-out-throughput"; held_root.mkdir(); held=run_portfolio_actor(context,p82,held_root,failure_subject,throughput_cases("public-b",[40,64]),2) if correction and correction["binding"] else None; active=control=held_world=None; reserve,recovery=ot145.floors(p82,parent); dworld=deadline_world(deadline_portfolio); ddecision=select(correction["program"],deadline_portfolio,DEADLINE_CONTEXT) if correction and correction["binding"] else None; deadline_floor=dworld["candidate_evaluations"][ddecision["selected_candidate"]["candidate_id"]] if ddecision else None; installed=failure_subject; installation=None; capability=None
    if held and held["binding"]:
        active=bind_selection(p82,failure_subject,correction["binding"]["binding_digest"],correction["program"],held["binding"],"corrected-program"); control=bind_selection(p82,failure_subject,parent_cap["program_binding_digest"],inherited,held["binding"],"unchanged-program"); held_world=world_receipt(p82,held["binding"],[active,control],throughput_cases("hidden-b",[80,112,144,64]),"ot-0147-held-out-throughput-world"); (held_root/"sealed-world.json").write_text(json.dumps(held_world,indent=2,sort_keys=True)+"\n"); floors={"reserve":reserve,"ordinary_recovery":recovery,"deadline_recovery":deadline_floor}; (run/"floors.json").write_text(json.dumps(floors,indent=2,sort_keys=True)+"\n")
        if held_world["selected_results"]["corrected-program"]["passed"] and not held_world["selected_results"]["unchanged-program"]["passed"] and reserve["passed"] and recovery["passed"] and deadline_floor and deadline_floor["passed"]: installed,installation,capability=install_program(p82,failure_subject,parent_cap,correction["binding"],active,held_world,floors)
    later_root=run/"later-throughput"; later_root.mkdir(); later=run_portfolio_actor(context,p82,later_root,installed,throughput_cases("public-c",[24,56]),3) if installation else None; reuse_root=run/"program-reuse"; reuse_root.mkdir(); reuse=previous.run_reuse_actor(context,p82,reuse_root,installed,capability,later["binding"]) if later and later["binding"] else None; reuse_selection=reuse_world=control_world=None; final=installed; transition=None
    if reuse and reuse["binding"]:
        reuse_selection=bind_selection(p82,installed,capability["program_binding_digest"],capability["program"],later["binding"],"reused-corrected-program"); old_control=bind_selection(p82,installed,parent_cap["program_binding_digest"],inherited,later["binding"],"unchanged-program-control"); reuse_world=world_receipt(p82,later["binding"],[reuse_selection],throughput_cases("hidden-c",[72,104,136,64]),"ot-0147-later-corrected-program-world"); (reuse_root/"sealed-world.json").write_text(json.dumps(reuse_world,indent=2,sort_keys=True)+"\n")
        if reuse_world["selected_results"]["reused-corrected-program"]["passed"]: final,transition=seal_final(p82,installed,reuse["binding"],reuse_selection,reuse_world)
        control_world=world_receipt(p82,later["binding"],[old_control],throughput_cases("hidden-c",[72,104,136,64]),"ot-0147-post-seal-unchanged-program-control"); (run/"post-seal-control.json").write_text(json.dumps(control_world,indent=2,sort_keys=True)+"\n")
    checks={"five_fresh_actors":bool(first["binding"] and correction and correction["binding"] and held and held["binding"] and later and later["binding"] and reuse and reuse["binding"]),"inherited_program_contradicted":bool(first_world and not first_world["selected_results"]["active"]["passed"]),"corrected_program_bound":bool(correction and correction["binding"] and valid_program(correction["program"])),"held_out_corrected_beats_unchanged":bool(held_world and held_world["selected_results"]["corrected-program"]["passed"] and held_world["selected_results"]["corrected-program"]["shifted_pass_count"]==3 and not held_world["selected_results"]["unchanged-program"]["passed"] and held_world["selected_results"]["unchanged-program"]["shifted_pass_count"]==0),"all_prior_floors":reserve["passed"] and reserve["distinguishing_count"]==9 and recovery["passed"] and recovery["shifted_pass_count"]==3 and bool(deadline_floor and deadline_floor["passed"]),"corrected_program_installed":bool(installation and runtime.identity_conforms(installed) and capability["parent_capability_digest"]==parent_cap["capability_digest"]),"later_exact_reuse":bool(reuse_world and reuse_world["selected_results"]["reused-corrected-program"]["passed"] and reuse_world["selected_results"]["reused-corrected-program"]["shifted_pass_count"]==3),"post_seal_unchanged_fails":bool(control_world and not control_world["selected_results"]["unchanged-program-control"]["passed"] and control_world["selected_results"]["unchanged-program-control"]["shifted_pass_count"]==0),"program_history_retained":bool(len(final.get("constitutional_selector_program_capabilities",[]))>=2 and final["constitutional_selector_program_capabilities"][-2]["capability_digest"]==parent_cap["capability_digest"]),"all_capability_roles_retained":bool(final.get("adaptive_contact_strategy_capabilities") and final.get("recovery_cadence_capabilities") and final.get("deadline_recovery_capabilities")),"final_subject_sounding_open":runtime.identity_conforms(final) and final["continuation"]["status"]=="open" and "subject-selected-world" in final["continuation"]["next_opening"]}; checks["passed"]=all(checks.values())
    result={"authority":"ot-0147-cross-world-selector-program-correction-driver","source_subject_digest":parent["artifact_digest"],"first_portfolio":p82.compact(first),"first_selection":first_selection,"first_world":first_world,"failure_receipt":failure_receipt,"program_correction":p82.compact(correction) if correction else None,"held_out_portfolio":p82.compact(held) if held else None,"active_selection":active,"unchanged_selection":control,"held_out_world":held_world,"reserve_floor":reserve,"ordinary_recovery_floor":recovery,"deadline_recovery_floor":deadline_floor,"installation_receipt":installation,"later_portfolio":p82.compact(later) if later else None,"reuse":p82.compact(reuse) if reuse else None,"reuse_selection":reuse_selection,"reuse_world":reuse_world,"reuse_transition":transition,"post_seal_unchanged_control":control_world,"checks":checks,"cross_world_program_correction_passed":checks["passed"],"observer_disposition":"promoted" if checks["passed"] else "rejected","subject_disposition":final["continuation"]["status"],"final_subject_digest":final["artifact_digest"],"next_opening":final["continuation"]["next_opening"],"fresh_actor_count":sum(item is not None for item in [first,correction,held,later,reuse]),"elapsed_seconds":round(time.time()-started,3)}; result["receipt_digest"]=p82.digest(result); (run/"aggregate.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); (run/"final-full-subject.json").write_text(json.dumps(final,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
