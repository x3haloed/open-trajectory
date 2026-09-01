from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0208_cost_corrected_pursuit_selector.py"
BASE_SHA256 = "e677feeaac11deb5426f888d3d8dff7642b5ed976cce0a15621d32673a1ddca6"
INVALID_PATH = ROOT / "ot_0209_subject_authored_code_pursuit.py"
INVALID_SHA256 = "90356cf24281d82e446a0c3fd28e8eb7dffcdafec69ccbbc9be9acf9bcb90dc9"
LAST_INVALID_PATH = ROOT / "ot_0210_typed_schema_code_pursuit.py"
LAST_INVALID_SHA256 = "b9b93af2c1ab1bf14a97b245d0ad2654767ae1dd09d9276015633959a76394b0"
WORLD_PATH = ROOT / "ot_0086_behavior_discovery.py"
WORLD_SHA256 = "1c1c060a29a86f63bc520c66fb2709817a804fcc0e1def248bf60c1fb7a69d70"
PARENT_DIGEST = "ab119b11ef04c93812c2a67efe66bbdf09b623b42ec69f7d6d7f4fd1172b2e0e"
CORRECTED_SELECTOR_DIGEST = "ea5d27fe65d8dfa49609c4219a04aeb558c504422088d942dea4eaed48f7308f"
LEDGER_DIGEST = "6565a30d8bc35b3f86ccffcc4698f8451204f50a7d471a969217e799f597aa80"
LEDGER_COMPLETION_DIGEST = "fa64fd10f7c4457dacf129a790c8693bc75ad8f8d23ec93a9d540efc40bd2407"
AUTHOR_SCHEMA = REPO / "spec/ot-0211-pursuit-author.schema.json"
EXECUTOR_SCHEMA = REPO / "spec/ot-0211-pursuit-executor.schema.json"
PROPOSAL_PATHS = [f"proposals/policy-{index}.py" for index in range(1, 4)]
EDITABLE_AUTHOR = ["frontier.json", *PROPOSAL_PATHS]
TARGET_PATH = "dispatch/policy.py"
MIN_HIDDEN_GAIN = 25.0
MIN_ORACLE_FRACTION = 0.95
MIN_CONTROL_GAP = 25.0


def load_module(path: Path, expected: str, name: str):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"frozen implementation changed: {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base208 = load_module(BASE_PATH, BASE_SHA256, "ot0211_frozen_ot0208")
world86 = load_module(WORLD_PATH, WORLD_SHA256, "ot0211_frozen_ot0086")
authority_base = base208.authority_base


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def frontier_template() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "candidate_id": f"policy-{index}",
                "policy_path": path,
                "rationale": "replace-with-observed-rationale",
                "implementation_opening": "replace-with-executable-opening",
            }
            for index, path in enumerate(PROPOSAL_PATHS, 1)
        ],
        "next_pursuit": "replace-with-next-pursuit",
    }


def valid_frontier(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"candidates", "next_pursuit"}:
        return False
    if not isinstance(value["next_pursuit"], str) or not value["next_pursuit"].strip() or value["next_pursuit"].startswith("replace-"):
        return False
    rows = value.get("candidates")
    if not isinstance(rows, list) or len(rows) != 3:
        return False
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {"candidate_id", "policy_path", "rationale", "implementation_opening"}:
            return False
        if row.get("candidate_id") != f"policy-{index}" or row.get("policy_path") != PROPOSAL_PATHS[index - 1]:
            return False
        for key in ("rationale", "implementation_opening"):
            if not isinstance(row.get(key), str) or not row[key].strip() or row[key].startswith("replace-") or len(row[key]) > 2000:
                return False
    return True


def source_has_abi(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "choose_worker" for node in tree.body)


def derive_features(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, int | bool]:
    baseline_rows = {row["case_id"]: row for row in baseline.get("rows", [])}
    candidate_rows = candidate.get("rows", [])
    valid = bool(candidate.get("valid") and candidate.get("floor", {}).get("passed") and len(candidate_rows) == len(world86.PUBLIC_CASES))
    if not valid:
        return {"blocked": True, "decision_ready_signal": 0, "checkpoint_cost": 9, "independent_contacts": 0, "reversible_branches": 0}
    changes = regressions = oracle_hits = nonregressions = 0
    for row in candidate_rows:
        prior = baseline_rows[row["case_id"]]
        changes += row.get("selected_worker") != prior.get("selected_worker")
        regressed = row.get("score", float("-inf")) + 1e-9 < prior.get("score", float("inf"))
        regressions += regressed
        nonregressions += not regressed
        oracle_hits += row.get("selected_worker") == row.get("oracle_worker")
    return {
        "blocked": False,
        "decision_ready_signal": changes,
        "checkpoint_cost": 1 + regressions,
        "independent_contacts": oracle_hits,
        "reversible_branches": nonregressions,
    }


def net_value(row: dict[str, Any]) -> int:
    return int(row["independent_contacts"] + row["reversible_branches"] - row["decision_ready_signal"] * row["checkpoint_cost"])


def extrema(rows: list[dict[str, Any]], scorer) -> list[dict[str, Any]]:
    live = [row for row in rows if not row["blocked"]]
    if not live:
        return []
    best = max(scorer(row) for row in live)
    return [row for row in live if scorer(row) == best]


def corrected_score(parent: dict[str, Any], row: dict[str, Any]) -> int:
    program = parent["pursuit_selector_capabilities"][-1]["selector"]["score_program"]
    return base208.execute_ast(program, row)


def public_candidate(p82, source: str, evidence: Path, label: str, baseline: dict[str, Any]) -> dict[str, Any]:
    receipt = world86.evaluate_source(p82, source, world86.PUBLIC_CASES, evidence, label)
    return {"receipt": receipt, "features": derive_features(baseline, receipt)}


def measure_portfolio(p82, parent: dict[str, Any], workspace: Path, frontier: dict[str, Any], evidence: Path) -> dict[str, Any] | None:
    baseline = world86.evaluate_source(p82, world86.POLICY_SOURCE, world86.PUBLIC_CASES, evidence, "public-baseline")
    rows = []
    sources = []
    for metadata in frontier["candidates"]:
        try:
            source = (workspace / metadata["policy_path"]).read_text()
        except OSError:
            return None
        sources.append(source)
        measured = public_candidate(p82, source, evidence, metadata["candidate_id"], baseline)
        body = {
            **copy.deepcopy(metadata),
            **measured["features"],
            "source": source,
            "source_digest": p82.digest(source),
            "public_receipt_digest": measured["receipt"]["receipt_digest"],
        }
        body["candidate_digest"] = p82.digest(body)
        rows.append(body)
    if len(set(sources)) != 3 or not all(source_has_abi(source) for source in sources):
        return None
    corrected = extrema(rows, lambda row: corrected_score(parent, row))
    inherited = extrema(rows, lambda row: row["decision_ready_signal"])
    separation = bool(
        len(corrected) == len(inherited) == 1
        and corrected[0]["candidate_digest"] != inherited[0]["candidate_digest"]
        and net_value(corrected[0]) > 0
        and net_value(inherited[0]) < 0
    )
    body = {
        "authority": "ot-0211-pre-hidden-executable-pursuit-portfolio",
        "source_subject_digest": parent["artifact_digest"],
        "corrected_selector_binding_digest": CORRECTED_SELECTOR_DIGEST,
        "candidates": rows,
        "corrected_selection": corrected[0]["candidate_digest"] if len(corrected) == 1 else None,
        "inherited_selection": inherited[0]["candidate_digest"] if len(inherited) == 1 else None,
        "next_pursuit": frontier["next_pursuit"],
        "prospective_separation_passed": separation,
    }
    return {**body, "binding_digest": p82.digest(body)}


def checker_source() -> str:
    cases = repr(world86.PUBLIC_CASES)
    baseline = repr(world86.POLICY_SOURCE)
    return f'''import json\nfrom pathlib import Path\nCASES={cases}\nBASELINE={baseline!r}\ndef score(job,w): return job["value"]*w["reliability"]-job["late_penalty"]*max(0.0,job["cost"]/w["speed"]-job["deadline"])\ndef run(source):\n ns={{}}; exec(compile(source,"<policy>","exec"),ns); choose=ns["choose_worker"]; out=[]\n for case in CASES:\n  job,workers=case["job"],case["workers"]; selected=choose(job,workers); ids={{w["id"] for w in workers}}\n  if selected not in ids: raise ValueError("unknown worker")\n  worker=next(w for w in workers if w["id"]==selected); oracle=max(workers,key=lambda w:(score(job,w),w["speed"],w["id"])); out.append((selected,score(job,worker),oracle["id"]))\n return out\nbase=run(BASELINE); rows=[]\ntry:\n for i in range(1,4):\n  src=Path(f"proposals/policy-{{i}}.py").read_text(); obs=run(src); changes=sum(a[0]!=b[0] for a,b in zip(obs,base)); regress=sum(a[1]+1e-9<b[1] for a,b in zip(obs,base)); contacts=sum(a[0]==a[2] for a in obs); reversible=4-regress; rows.append({{"id":f"policy-{{i}}","decision_ready_signal":changes,"checkpoint_cost":1+regress,"independent_contacts":contacts,"reversible_branches":reversible,"net":contacts+reversible-changes*(1+regress)}})\n old=max(r["decision_ready_signal"] for r in rows); net=max(r["net"] for r in rows); olds=[r for r in rows if r["decision_ready_signal"]==old]; nets=[r for r in rows if r["net"]==net]; frontier=json.loads(Path("frontier.json").read_text()); ok=len(olds)==len(nets)==1 and olds[0]["id"]!=nets[0]["id"] and olds[0]["net"]<0<nets[0]["net"] and len({{Path(f"proposals/policy-{{i}}.py").read_text() for i in range(1,4)}})==3 and not str(frontier.get("next_pursuit","")).startswith("replace-")\nexcept Exception as error:\n rows=[]; ok=False\nprint(json.dumps({{"passed":ok,"rows":rows}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''


def author_seed(root: Path, parent: dict[str, Any]) -> Path:
    seed = root / "author-seed"
    seed.mkdir()
    world86.write_environment(seed)
    (seed / "proposals").mkdir()
    for path in PROPOSAL_PATHS:
        (seed / path).write_text('def choose_worker(job, workers):\n    raise NotImplementedError("replace candidate")\n')
    write_json(seed / "frontier.json", frontier_template())
    write_json(seed / "subject-position.json", {
        "subject_digest": parent["artifact_digest"],
        "continuation": parent["continuation"],
        "corrected_selector": parent["pursuit_selector_capabilities"][-1],
        "selector_consequence": parent["selector_correction_receipts"][-1],
    })
    write_json(seed / "mutation-envelope.json", {
        "editable": EDITABLE_AUTHOR,
        "immutable": ["subject-position.json", "mutation-envelope.json", "check_portfolio.py", "README.md", *sorted(world86.ENVIRONMENT_FILES)],
    })
    (seed / "check_portfolio.py").write_text(checker_source())
    (seed / "README.md").write_text(
        "This complete dispatch repository has observed public regret but no requested repair. Inspect it, run python3 observe.py, and author three materially different executable possible pursuits in proposals/policy-1.py through policy-3.py. Complete frontier.json with the rationale and implementation opening for each and a next pursuit worth carrying after this encounter. The world derives selector features from actual public behavior; python3 check_portfolio.py shows those measurements and requires the exact corrected selector to choose a positive-net policy while its inherited checkpoint-maximizing parent uniquely chooses a different negative-net policy. Hidden cases are unavailable. Edit exactly the four allowed files, run checks, and inspect the diff.\n"
    )
    return seed


def run_author(context, prior131, p82, root: Path, parent: dict[str, Any]) -> dict[str, Any]:
    seed = author_seed(root, parent)
    prompt = (seed / "README.md").read_text().strip()
    output, base_audit, workspace, _ = context.run_actor("pursuit-author", seed, AUTHOR_SCHEMA, prompt)
    try:
        frontier = json.loads((workspace / "frontier.json").read_text())
        envelope = json.loads((seed / "mutation-envelope.json").read_text())
        immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in envelope["immutable"])
    except (OSError, json.JSONDecodeError, KeyError):
        frontier, immutable_ok = None, False
    portfolio = measure_portfolio(p82, parent, workspace, frontier, context.evidence("pursuit-author") / "measurement") if valid_frontier(frontier) and immutable_ok else None
    valid = bool(portfolio and portfolio["prospective_separation_passed"] and output and output.get("action") == "author-executable-pursuit-portfolio")
    audit = context.audit_actor("pursuit-author", output, base_audit, valid, EDITABLE_AUTHOR)
    accepted = valid and prior131.audit_accepted(audit)
    if accepted:
        write_json(context.evidence("pursuit-author") / "bound-portfolio.json", portfolio)
    return {"output": output, "audit": audit, "portfolio": portfolio, "accepted": accepted}


def selected_candidate(portfolio: dict[str, Any], key: str) -> dict[str, Any]:
    digest = portfolio[key]
    return next(row for row in portfolio["candidates"] if row["candidate_digest"] == digest)


def executor_seed(root: Path, route: str, parent: dict[str, Any], portfolio: dict[str, Any], candidate: dict[str, Any]) -> Path:
    seed = root / f"{route}-executor-seed"
    seed.mkdir()
    world86.write_environment(seed)
    (seed / "bound-policy.py").write_text(candidate["source"])
    projection = {key: value for key, value in candidate.items() if key != "source"}
    write_json(seed / "selected-pursuit.json", {
        "route": route,
        "source_subject_digest": parent["artifact_digest"],
        "portfolio_binding_digest": portfolio["binding_digest"],
        "candidate": projection,
        "required_source_digest": candidate["source_digest"],
    })
    (seed / "README.md").write_text(
        "The subject's bound selector route chose selected-pursuit.json. Integrate the exact executable pursuit from bound-policy.py into dispatch/policy.py. Preserve the visible ABI, edit no other file, run public observation and floors, and inspect the exact diff. Hidden outcomes remain with the world.\n"
    )
    return seed


def run_executor(context, prior131, p82, root: Path, route: str, parent: dict[str, Any], portfolio: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    label = f"{route}-executor"
    seed = executor_seed(root, route, parent, portfolio, candidate)
    output, base_audit, workspace, _ = context.run_actor(label, seed, EXECUTOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        source = (workspace / TARGET_PATH).read_text()
    except OSError:
        source = ""
    exact = p82.digest(source) == candidate["source_digest"]
    audit = context.audit_actor(label, output, base_audit, exact and output and output.get("action") == "integrate-selected-pursuit", [TARGET_PATH])
    accepted = exact and prior131.audit_accepted(audit)
    binding = None
    if accepted:
        body = {
            "authority": "ot-0211-pre-hidden-integrated-pursuit",
            "route": route,
            "source_subject_digest": parent["artifact_digest"],
            "portfolio_binding_digest": portfolio["binding_digest"],
            "candidate_digest": candidate["candidate_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "source_digest": p82.digest(source),
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-integration.json", binding)
    public = world86.compare_sources(p82, source, context.evidence(label), "public", world86.PUBLIC_CASES, True) if binding else None
    hidden = world86.compare_sources(p82, source, context.evidence(label), "hidden", world86.HIDDEN_CASES, False) if binding else None
    return {"output": output, "audit": audit, "accepted": accepted, "binding": binding, "public": public, "hidden": hidden}


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0211").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0208", "open-subject-after-cost-selector-correction.json")
    result208 = selector_base.load_artifact(p82, repo, store, "OT-0208", "cost-corrected-pursuit-selector-aggregate.json")
    expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]
    route_floor = base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression)
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixture_root = run.parent / "OT-0211-preflight"
    fixture_root.mkdir(parents=True, exist_ok=True)
    fixture_env = fixture_root / "environment"
    if fixture_env.exists():
        import shutil
        shutil.rmtree(fixture_env)
    world86.write_environment(fixture_env)
    reference_public = world86.compare_sources(p82, world86.REFERENCE_POLICY_SOURCE, fixture_root / "reference", "public", world86.PUBLIC_CASES, True)
    reference_hidden = world86.compare_sources(p82, world86.REFERENCE_POLICY_SOURCE, fixture_root / "reference", "hidden", world86.HIDDEN_CASES, False)
    checks = {
        "invalid_harness_exact": hashlib.sha256(INVALID_PATH.read_bytes()).hexdigest() == INVALID_SHA256,
        "last_invalid_harness_exact": hashlib.sha256(LAST_INVALID_PATH.read_bytes()).hexdigest() == LAST_INVALID_SHA256,
        "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "ot0208_exact_promotion": result208["observer_disposition"] == "promoted" and result208["final_subject_digest"] == PARENT_DIGEST,
        "corrected_selector_exact": parent["pursuit_selector_capabilities"][-1]["selector_binding_digest"] == CORRECTED_SELECTOR_DIGEST,
        "ledger_exact": parent["contact_correction_ledger_capabilities"][-1]["binding_digest"] == LEDGER_DIGEST and parent["developmental_completion_receipts"][-1]["receipt_digest"] == LEDGER_COMPLETION_DIGEST,
        "complete_world_floor": world86.floor_test(fixture_env)["passed"] and world86.observe(fixture_env)["returncode"] == 0,
        "reference_public_valid": reference_public["both_valid"] and reference_public["candidate_floor_passed"] and reference_public["no_case_regression"],
        "reference_hidden_admissible": reference_hidden["gain"] >= MIN_HIDDEN_GAIN and reference_hidden["oracle_improvement_fraction"] >= MIN_ORACLE_FRACTION,
        "feature_derivation_fixed": derive_features(
            world86.evaluate_source(p82, world86.POLICY_SOURCE, world86.PUBLIC_CASES, fixture_root / "features", "baseline"),
            world86.evaluate_source(p82, world86.REFERENCE_POLICY_SOURCE, world86.PUBLIC_CASES, fixture_root / "features", "reference"),
        ) == {"blocked": False, "decision_ready_signal": 2, "checkpoint_cost": 1, "independent_contacts": 4, "reversible_branches": 4},
        "installed_route_floor_16_of_16": route_floor["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
        "schemas_present": AUTHOR_SCHEMA.is_file() and EXECUTOR_SCHEMA.is_file(),
        "typed_constant_schema_conforms": all(
            property_schema.get("type") == "string"
            for schema_path in (AUTHOR_SCHEMA, EXECUTOR_SCHEMA)
            for property_schema in json.loads(schema_path.read_text()).get("properties", {}).values()
            if "const" in property_schema
        ),
        "unsupported_unique_items_absent": all(
            "uniqueItems" not in schema_path.read_text()
            for schema_path in (AUTHOR_SCHEMA, EXECUTOR_SCHEMA)
        ),
    }
    checks["passed"] = all(checks.values())
    fixtures = {"authority": "ot-0211-preflight", "source_subject_digest": parent["artifact_digest"], "checks": checks}
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "world_sha256": WORLD_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0211 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    author_root = run / "authoring"
    author_root.mkdir()
    authored = run_author(context, prior131, p82, author_root, parent)
    active = control = None
    if authored["accepted"]:
        portfolio = authored["portfolio"]
        active_candidate = selected_candidate(portfolio, "corrected_selection")
        control_candidate = selected_candidate(portfolio, "inherited_selection")
        active_root = run / "active-execution"
        control_root = run / "control-execution"
        active_root.mkdir(); control_root.mkdir()
        active = run_executor(context, prior131, p82, active_root, "corrected", parent, portfolio, active_candidate)
        control = run_executor(context, prior131, p82, control_root, "inherited", parent, portfolio, control_candidate)
    portfolio = authored.get("portfolio") or {}
    active_hidden = (active or {}).get("hidden") or {}
    active_public = (active or {}).get("public") or {}
    control_hidden = (control or {}).get("hidden") or {}
    gates = {
        "three_fresh_actors_accepted": bool(authored["accepted"] and active and control and active["accepted"] and control["accepted"]),
        "prospective_selector_separation": portfolio.get("prospective_separation_passed") is True,
        "exact_integration_both_routes": bool(active and control and active["binding"] and control["binding"]),
        "corrected_public_no_regression": active_public.get("no_case_regression") is True and active_public.get("candidate_floor_passed") is True,
        "corrected_hidden_admitted": active_hidden.get("gain", float("-inf")) >= MIN_HIDDEN_GAIN and active_hidden.get("oracle_improvement_fraction", float("-inf")) >= MIN_ORACLE_FRACTION,
        "inherited_route_world_valid": control_hidden.get("both_valid") is True and control_hidden.get("candidate_floor_passed") is True,
        "corrected_hidden_control_gap": active_hidden.get("candidate_total", float("-inf")) - control_hidden.get("candidate_total", float("inf")) >= MIN_CONTROL_GAP,
        "ledger_and_selector_exact": parent["contact_correction_ledger_capabilities"][-1]["binding_digest"] == LEDGER_DIGEST and parent["pursuit_selector_capabilities"][-1]["selector_binding_digest"] == CORRECTED_SELECTOR_DIGEST,
        "installed_route_floor_16_of_16": route_floor["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
        "actor_authored_reopening": isinstance(portfolio.get("next_pursuit"), str) and bool(portfolio.get("next_pursuit", "").strip()),
    }
    gates["passed"] = all(gates.values())
    final = parent
    promotion = None
    if gates["passed"]:
        active_candidate = selected_candidate(portfolio, "corrected_selection")
        control_candidate = selected_candidate(portfolio, "inherited_selection")
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        capability = {
            "authority": "ot-0211-world-admitted-subject-authored-code-pursuit",
            "portfolio_binding_digest": portfolio["binding_digest"],
            "selected_candidate_digest": active_candidate["candidate_digest"],
            "integration_binding_digest": active["binding"]["binding_digest"],
            "world_receipt_digest": active_hidden["receipt_digest"],
            "target_path": TARGET_PATH,
            "source": active_candidate["source"],
            "source_digest": active_candidate["source_digest"],
        }
        child["executed_pursuit_capabilities"] = [*child.get("executed_pursuit_capabilities", []), capability]
        receipt_body = {
            "authority": "ot-0211-corrected-selector-cross-world-recurrence",
            "source_subject_digest": parent["artifact_digest"],
            "portfolio_binding_digest": portfolio["binding_digest"],
            "corrected_selector_binding_digest": CORRECTED_SELECTOR_DIGEST,
            "corrected_candidate_digest": active_candidate["candidate_digest"],
            "inherited_candidate_digest": control_candidate["candidate_digest"],
            "corrected_hidden_receipt_digest": active_hidden["receipt_digest"],
            "inherited_hidden_receipt_digest": control_hidden["receipt_digest"],
            "hidden_score_gap": active_hidden["candidate_total"] - control_hidden["candidate_total"],
        }
        promotion = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
        child["pursuit_execution_receipts"] = [*child.get("pursuit_execution_receipts", []), promotion]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": portfolio["next_pursuit"]}
        child["unresolved"] = "Can subject-authored selection and execution recur in another objective world while external opening and admission authority continue to recede?"
        candidate = p82.seal(child)
        if runtime.identity_conforms(candidate):
            final = candidate
        else:
            gates["successor_identity_conforms"] = False
            gates["passed"] = False
    gates.setdefault("successor_identity_conforms", gates["passed"] and final is not parent)
    if not gates["successor_identity_conforms"]:
        gates["passed"] = False
        final = parent
    result = {
        "authority": "ot-0211-subject-authored-code-pursuit",
        "source_subject_digest": parent["artifact_digest"],
        "portfolio_author": p82.compact(authored),
        "corrected_executor": p82.compact(active) if active else None,
        "inherited_executor_control": p82.compact(control) if control else None,
        "promotion_receipt": promotion,
        "checks": gates,
        "route_floor": route_floor,
        "identity_floor": identity,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": 3 if active and control else 1,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
