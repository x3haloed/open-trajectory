from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path


sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0323_applicability_routed_search_invocation.py"
BASE_SHA256 = "a9f1d40c521b178583f3751aacd6b27c2f22da2d063ac2cae08036c637b79b4e"
PARENT_DIGEST = "aba1513fd7cada11bef697a58b3e389d74f9939e197d178447ea2b3beaed2e5e"
OT323_RECEIPT = "ebb7336da0510bc7b84fa2190f3c865bdab1b775e78934359a58090712130ece"
ROUTER_RECEIPT = "dab133c2e7eb5f928664b6130ff46ac640c284e328190fa01b2a9a0001793eaa"
AUTHORITY = "ot-0324-consequence-revised-search-routing"
ROUTER_SCHEMA = REPO / "spec" / "ot-0324-router-revision.schema.json"
STAKE_SCHEMA = REPO / "spec" / "ot-0314-stake-revision.schema.json"


FIXTURE_ROUTER = '''import json
from pathlib import Path
state=json.loads(Path("applicability-state.json").read_text())
fronts=json.loads(Path("front-search-summaries.json").read_text())
eligible=[row for row in fronts if row.get("improvement_found") is True and row["best_pass_count"]>row["current_pass_count"]]
if eligible:
    chosen=min(eligible,key=lambda row:(-(row["best_pass_count"]-row["current_pass_count"]),row["front_id"]))
    result={"action":"invoke-search","selected_front_id":chosen["front_id"],"reason":"reachable-search-improvement","applicability_rule":state.get("invoke_when")}
else:
    result={"action":"wait","selected_front_id":None,"reason":"no-reachable-search-improvement","applicability_rule":state.get("invoke_when")}
print(json.dumps(result,sort_keys=True)); raise SystemExit(0)
'''


CHECKER_SOURCE = '''import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path
source=Path("route_search.py").read_text()
contract=json.loads(Path("router-contract.json").read_text())
fixtures=json.loads(Path("router-fixtures.json").read_text())
safe=len(source.encode())<=contract["maximum_source_bytes"] and all(term not in source for term in contract["forbidden_source_terms"])
try:
    tree=ast.parse(source)
    imports={node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node,(ast.ImportFrom,)) and node.module}
    imports|={alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names}
    safe=safe and imports<=set(contract["allowed_import_roots"])
except (SyntaxError,TypeError): safe=False
passed=safe
rows=[]
if safe:
    for fixture in fixtures:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/"route_search.py").write_text(source)
            (root/"applicability-state.json").write_text(json.dumps(fixture["applicability"],sort_keys=True))
            (root/"front-search-summaries.json").write_text(json.dumps(fixture["fronts"],sort_keys=True))
            completed=subprocess.run([sys.executable,"-I","route_search.py"],cwd=root,text=True,capture_output=True,timeout=5)
            try: result=json.loads(completed.stdout)
            except json.JSONDecodeError: result=None
            ok=completed.returncode==0 and result is not None and result.get("action")==fixture["expected_action"] and result.get("selected_front_id")==fixture["expected_front_id"]
            rows.append({"fixture_id":fixture["fixture_id"],"passed":ok}); passed=passed and ok
print(json.dumps({"valid":passed,"safe":safe,"rows":rows},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0323 changed")
    spec = importlib.util.spec_from_file_location("ot0324_frozen_ot0323", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
base322 = base.base
b = base.b
base236 = base.base236
base314 = base.base314
base315 = base.base315
base316 = base.base316
base319 = base.base319
write_json = base.write_json


def setup(args):
    (
        repo, store, _, p82, runtime, _, _, selector, raw314, result318, core,
        base130,
    ) = base.setup(args)
    run = (args.evidence_root or store / "runs" / "OT-0324").resolve()
    parent = selector.load_artifact(
        p82, repo, store, "OT-0323", "open-subject-after-applicability-routed-invocation.json"
    )
    result323 = selector.load_artifact(
        p82, repo, store, "OT-0323", "applicability-routed-search-invocation-aggregate.json"
    )
    return repo, store, run, p82, runtime, parent, result323, core, base130


def token(seed, label):
    return hashlib.sha256(bytes.fromhex(seed) + label.encode()).hexdigest()


def pad_sources(*sources):
    target = max(len(source.encode()) for source in sources) + 2
    result = []
    for source in sources:
        missing = target - len(source.encode())
        result.append(source + ("#" * (missing - 1)) + "\n")
    if len({len(source.encode()) for source in result}) != 1:
        raise RuntimeError("source padding failed")
    return tuple(result)


def diagnostic_sources():
    low_useful = 'def route(case):\n    return ("harbor","shelter","clinic","relay")[case["signal"]]\n'
    high_decoy = 'def route(case):\n    return (lambda value:"harbor")((lambda value:"harbor")((lambda value:"harbor")(case)))\n'
    low_decoy = 'def route(case):\n    return ("harbor",)[0]\n'
    high_useful = 'def route(case):\n    return (lambda value:value)((lambda value:value)((lambda value:value)(("harbor","shelter","clinic","relay")[case["signal"]])))\n'
    return pad_sources(low_useful, high_decoy, low_decoy, high_useful)


def gain_sources():
    useful = 'def route(case):\n    return ("harbor","shelter","clinic","relay")[case["signal"]]\n'
    decoy = 'def route(case):\n    return (lambda value:"harbor")(case)\n'
    return pad_sources(useful, decoy)


def descriptor(seed, label, source):
    return {
        "world_id": "w-" + token(seed, label)[:16],
        "public_package_digest": hashlib.sha256(
            source.encode() + bytes.fromhex(token(seed, label))
        ).hexdigest(),
        "features": base314.base305.source_features(source),
    }


def episode(seed, label, low_source, high_source, p82):
    contexts = [{"signal": value} for value in (0, 1, 2, 3)]
    low = descriptor(seed, label + "-low", low_source)
    high = descriptor(seed, label + "-high", high_source)
    catalog = sorted([low, high], key=lambda row: row["world_id"])
    option = {
        low["world_id"]: base314.executable_option_value(low_source, contexts),
        high["world_id"]: base314.executable_option_value(high_source, contexts),
    }
    return {
        "episode_id": "e-" + token(seed, label)[:16],
        "catalog": catalog,
        "sealed_contexts_digest": p82.digest(contexts),
        "option_value": option,
        "best_world_id": max(option, key=option.get),
    }


def dead_end_episodes(seed, p82):
    low_useful, high_decoy, low_decoy, high_useful = diagnostic_sources()
    return [
        episode(seed, "dead-0", low_useful, high_decoy, p82),
        episode(seed, "dead-1", low_useful, high_decoy, p82),
        episode(seed, "dead-2", low_decoy, high_useful, p82),
    ]


def gain_episodes(seed, p82):
    useful, decoy = gain_sources()
    rows = [episode(seed, f"gain-{index}", useful, decoy, p82) for index in range(8)]
    return rows[:3], rows[3:]


def fronts(seed, stake, p82, *, heldout):
    dead = {
        "front_id": "front-0-" + token(seed, "dead-front")[:12],
        "contacts": base322.selection_contacts(stake, dead_end_episodes(seed, p82), p82),
        "offer_index": 1 if heldout else 0,
    }
    gain_training, _ = gain_episodes(seed, p82)
    gain = {
        "front_id": "front-1-" + token(seed, "gain-front")[:12],
        "contacts": base322.selection_contacts(stake, gain_training, p82),
        "offer_index": 0 if heldout else 1,
    }
    return [gain, dead] if heldout else [dead, gain]


def summaries(front_rows, search_source, stake):
    return base.front_summaries(front_rows, search_source, stake)


def router_contract():
    return {
        "maximum_source_bytes": 5000,
        "allowed_import_roots": ["json", "pathlib"],
        "forbidden_source_terms": [
            "subprocess", "socket", "urllib", "requests", "http", "eval(",
            "exec(", "compile(", "open(", "__", "/" + "Users/", "/" + "home/",
        ],
        "required_output": ["action", "selected_front_id"],
        "allowed_actions": ["invoke-search", "wait"],
    }


def router_safe(source):
    contract = router_contract()
    if len(source.encode()) > contract["maximum_source_bytes"]:
        return False
    if any(term in source for term in contract["forbidden_source_terms"]):
        return False
    try:
        tree = ast.parse(source)
    except (SyntaxError, TypeError):
        return False
    imports = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imports |= {
        alias.name.split(".")[0]
        for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    }
    return imports <= set(contract["allowed_import_roots"])


def run_router_source(source, applicability, front_summaries):
    with tempfile.TemporaryDirectory(prefix="ot0324-router-") as temporary:
        root = Path(temporary)
        write_json(root / "applicability-state.json", applicability)
        write_json(root / "front-search-summaries.json", front_summaries)
        (root / "route_search.py").write_text(source)
        completed = subprocess.run(
            [sys.executable, "-I", "route_search.py"], cwd=root, text=True,
            capture_output=True, timeout=5, check=False,
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = None
    return {"returncode": completed.returncode, "parsed": parsed, "stderr": completed.stderr}


def public_fixtures(applicability, diagnostic):
    dead, gain = diagnostic
    renamed_dead = {**dead, "front_id": "zeta-opaque"}
    renamed_gain = {**gain, "front_id": "alpha-opaque"}
    saturated = {**dead, "front_id": "only-saturated"}
    return [
        {
            "fixture_id": "diagnostic-order",
            "applicability": applicability,
            "fronts": diagnostic,
            "expected_action": "invoke-search",
            "expected_front_id": gain["front_id"],
        },
        {
            "fixture_id": "renamed-reversed",
            "applicability": applicability,
            "fronts": [renamed_gain, renamed_dead],
            "expected_action": "invoke-search",
            "expected_front_id": renamed_gain["front_id"],
        },
        {
            "fixture_id": "no-reachable-gain",
            "applicability": applicability,
            "fronts": [saturated],
            "expected_action": "wait",
            "expected_front_id": None,
        },
    ]


def router_conforms(source, fixtures):
    rows = []
    for fixture in fixtures:
        result = run_router_source(source, fixture["applicability"], fixture["fronts"])
        parsed = result["parsed"]
        passed = bool(
            router_safe(source) and result["returncode"] == 0
            and isinstance(parsed, dict)
            and parsed.get("action") == fixture["expected_action"]
            and parsed.get("selected_front_id") == fixture["expected_front_id"]
        )
        rows.append({"fixture_id": fixture["fixture_id"], "passed": passed})
    return {"safe": router_safe(source), "rows": rows, "passed": all(row["passed"] for row in rows)}


def route_receipt(subject, front_summaries, route, p82, label):
    body = {
        "authority": AUTHORITY + "-" + label,
        "source_subject_digest": subject["artifact_digest"],
        "search_capability_receipt_digest": subject["active_proposal_search_capability"]["receipt_digest"],
        "router_capability_receipt_digest": subject["active_proposal_search_router"]["receipt_digest"],
        "front_summary_digests": [p82.digest(row) for row in front_summaries],
        "route": route,
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def router_actor_seed(root, parent, diagnostic, consequence, fixtures):
    seed = root / "seed"
    seed.mkdir(parents=True)
    (seed / "route_search.py").write_text(parent["active_proposal_search_router"]["source"])
    write_json(seed / "front-search-summaries.json", diagnostic)
    write_json(seed / "completed-route-consequence.json", consequence)
    write_json(seed / "router-contract.json", router_contract())
    write_json(seed / "router-fixtures.json", fixtures)
    write_json(seed / "subject-position.json", {
        "source_subject_digest": parent["artifact_digest"],
        "active_router_receipt_digest": parent["active_proposal_search_router"]["receipt_digest"],
        "active_search_receipt_digest": parent["active_proposal_search_capability"]["receipt_digest"],
    })
    (seed / "check_router.py").write_text(CHECKER_SOURCE)
    immutable = [
        "front-search-summaries.json", "completed-route-consequence.json",
        "router-contract.json", "router-fixtures.json", "subject-position.json",
        "check_router.py", "mutation-envelope.json", "README.md",
    ]
    write_json(seed / "mutation-envelope.json", {
        "editable": ["route_search.py"], "immutable": immutable,
    })
    (seed / "README.md").write_text(
        "Continue from the exact subject after its active router selected one of two available "
        "failure-bearing fronts. completed-route-consequence.json records what happened; both "
        "pre-route search summaries remain available. Decide whether the router should change. "
        "If so, edit only route_search.py within the visible contract. No private held-out fronts, "
        "target source, evaluator, sibling, or prescribed edit is supplied. Run python3 "
        "check_router.py and inspect the exact diff before returning the report.\n"
    )
    return seed


def run_router_actor(context, root, parent, diagnostic, consequence, fixtures):
    label = "proposal-search-router-reviser"
    seed = router_actor_seed(root, parent, diagnostic, consequence, fixtures)
    output, audit0, workspace, _ = context.run_actor(
        label, seed, ROUTER_SCHEMA, (seed / "README.md").read_text().strip()
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    try:
        source = (workspace / "route_search.py").read_text()
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in immutable
        )
        conformance = router_conforms(source, fixtures)
        checker_invoked = base.named_command_succeeded(trace, "check_router.py")
        changed = source != parent["active_proposal_search_router"]["source"]
        transport = bool(
            isinstance(output, dict)
            and output.get("action") == "revise-proposal-search-router"
            and output.get("files_changed") == ["route_search.py"]
        )
    except (OSError, ValueError, KeyError, TypeError):
        source = None
        immutable_ok = checker_invoked = changed = transport = False
        conformance = {"safe": False, "rows": [], "passed": False}
    semantic = bool(immutable_ok and conformance["passed"] and checker_invoked and changed and transport)
    audit = context.audit_actor(label, output, audit0, semantic, ["route_search.py"])
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(semantic and base236.g10(normalized))
    return {
        "accepted": accepted,
        "source": source,
        "source_digest": hashlib.sha256(source.encode()).hexdigest() if source else None,
        "changed": changed,
        "output": output,
        "audit": audit,
        "conformance": conformance,
        "workspace_evaluation": {
            "immutable_ok": immutable_ok,
            "checker_invoked": checker_invoked,
            "transport": transport,
            "semantic": semantic,
        },
    }


def compile_router_branches(parent, actor, diagnostic, consequence, p82):
    correction_body = {
        "authority": AUTHORITY + "-router-correction-proposal",
        "source_subject_digest": parent["artifact_digest"],
        "prior_router_receipt_digest": parent["active_proposal_search_router"]["receipt_digest"],
        "diagnostic_summary_digests": [p82.digest(row) for row in diagnostic],
        "failed_route_receipt_digest": consequence["route_receipt_digest"],
        "actor_patch_digest": actor["audit"]["patch_digest"],
        "proposed_source": actor["source"],
        "proposed_source_digest": actor["source_digest"],
    }
    correction = {**correction_body, "receipt_digest": p82.digest(correction_body)}
    capability_body = {
        "authority": AUTHORITY + "-actor-authored-router-capability",
        "source_subject_digest": parent["artifact_digest"],
        "correction_receipt_digest": correction["receipt_digest"],
        "search_capability_receipt_digest": parent["active_proposal_search_capability"]["receipt_digest"],
        "source": actor["source"],
        "source_digest": actor["source_digest"],
        "interface": parent["active_proposal_search_router"]["interface"],
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    capability = {**capability_body, "receipt_digest": p82.digest(capability_body)}
    common = copy.deepcopy(parent)
    common.pop("artifact_digest", None)
    common["proposal_search_router_corrections"] = [
        *common.get("proposal_search_router_corrections", []), correction
    ]
    common["proposal_search_router_capabilities"] = [
        *common.get("proposal_search_router_capabilities", []), capability
    ]
    changed = copy.deepcopy(common)
    changed["active_proposal_search_router"] = capability
    unchanged = copy.deepcopy(common)
    return p82.seal(changed), p82.seal(unchanged), correction, capability


def cumulative_score(stake, seed, p82):
    prior = (
        base314.episodes(seed, p82)[1]
        + base316.episodes(seed, p82)[1]
        + base322.episodes(seed, p82)[1]
        + base.loop_episodes(seed, p82)[1]
    )
    new = gain_episodes(seed, p82)[1]
    return {
        "prior_floor": base319.score(stake, prior, p82),
        "new_regime": base319.score(stake, new, p82),
        "all_regimes": base319.score(stake, prior + new, p82),
    }


def preflight(root, p82, runtime, parent, result323):
    root.mkdir(parents=True, exist_ok=True)
    seed = "00" * 32
    stake = base316.stake_of(parent)
    diagnostic_fronts = fronts(seed, stake, p82, heldout=False)
    diagnostic = summaries(diagnostic_fronts, parent["active_proposal_search_capability"]["source"], stake)
    current_route = base.run_router(parent, diagnostic)["parsed"]
    consequence = {
        "route_receipt_digest": p82.digest(current_route),
        "selected_front_id": current_route["selected_front_id"],
        "selected_improvement_found": diagnostic[0]["improvement_found"],
        "alternative_improvement_found": diagnostic[1]["improvement_found"],
    }
    fixtures = public_fixtures(parent["active_proposal_search_capability"]["applicability"], diagnostic)
    current_conformance = router_conforms(parent["active_proposal_search_router"]["source"], fixtures)
    fixture_conformance = router_conforms(FIXTURE_ROUTER, fixtures)
    changed, unchanged, _, _ = compile_router_branches(
        parent,
        {"source": FIXTURE_ROUTER, "source_digest": hashlib.sha256(FIXTURE_ROUTER.encode()).hexdigest(), "audit": {"patch_digest": p82.digest("fixture")}},
        diagnostic, consequence, p82,
    )
    heldout_fronts = fronts(seed, stake, p82, heldout=True)
    heldout = summaries(heldout_fronts, parent["active_proposal_search_capability"]["source"], stake)
    changed_route = run_router_source(FIXTURE_ROUTER, changed["active_proposal_search_capability"]["applicability"], heldout)["parsed"]
    unchanged_route = base.run_router(unchanged, heldout)["parsed"]
    gain_front = heldout_fronts[0]
    searched = base322.run_search(parent["active_proposal_search_capability"]["source"], stake, gain_front["contacts"])["parsed"]
    candidate = copy.deepcopy(stake)
    candidate["weights"] = searched["candidates"][0]["weights"]
    candidate["rationale"] = "Candidate-free router refinement fixture."
    candidate_score = cumulative_score(candidate, seed, p82)
    incumbent_score = cumulative_score(stake, seed, p82)
    all_sources = diagnostic_sources() + gain_sources()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_parent_and_receipt": parent["artifact_digest"] == PARENT_DIGEST
        and result323["receipt_digest"] == OT323_RECEIPT
        and result323["observer_disposition"] == "promoted",
        "exact_router_bound": parent["active_proposal_search_router"]["receipt_digest"] == ROUTER_RECEIPT,
        "source_features_call_only": all(
            base314.base305.source_features(source)[name] == 0
            for source in all_sources for name in ("branch_nodes", "comparison_nodes", "loop_nodes")
        ),
        "diagnostic_dead_end_2_of_3_best_2": diagnostic[0]["current_pass_count"] == 2
        and diagnostic[0]["best_pass_count"] == 2 and not diagnostic[0]["improvement_found"],
        "diagnostic_gain_0_of_3_best_3": diagnostic[1]["current_pass_count"] == 0
        and diagnostic[1]["best_pass_count"] == 3 and diagnostic[1]["improvement_found"],
        "incumbent_routes_to_dead_end": current_route["selected_front_id"] == diagnostic[0]["front_id"],
        "current_fails_public_fixtures": not current_conformance["passed"],
        "fixture_router_safe_and_passes": fixture_conformance["safe"] and fixture_conformance["passed"],
        "branch_common_information": changed["proposal_search_router_corrections"][-1]
        == unchanged["proposal_search_router_corrections"][-1]
        and changed["proposal_search_router_capabilities"][-1]
        == unchanged["proposal_search_router_capabilities"][-1],
        "active_binding_only_differs": changed["active_proposal_search_router"]
        != unchanged["active_proposal_search_router"],
        "new_identity_order_separates_routes": changed_route["selected_front_id"] == heldout[0]["front_id"]
        and unchanged_route["selected_front_id"] == heldout[1]["front_id"],
        "candidate_reaches_25_and_preserves_20": candidate_score["prior_floor"]["pass_count"] == 20
        and candidate_score["new_regime"]["pass_count"] == 5
        and candidate_score["all_regimes"]["pass_count"] == 25,
        "incumbent_preserves_20_and_fails_new": incumbent_score["prior_floor"]["pass_count"] == 20
        and incumbent_score["new_regime"]["pass_count"] == 0
        and incumbent_score["all_regimes"]["pass_count"] == 20,
        "exact_open_conformant": parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "fixture_seed_digest": p82.digest(seed),
        "diagnostic_summaries": diagnostic,
        "incumbent_route": current_route,
        "current_router_conformance": current_conformance,
        "fixture_router_conformance": fixture_conformance,
        "changed_heldout_route": changed_route,
        "unchanged_heldout_route": unchanged_route,
        "fixture_candidate_score": candidate_score,
        "incumbent_score": incumbent_score,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, parent, result323, core, base130 = setup(args)
    retained = run / "preflight" / "fixture-conformance.json"
    fixtures_report = json.loads(retained.read_text()) if retained.exists() else preflight(
        run / "preflight", p82, runtime, parent, result323
    )
    if args.preflight_only:
        print(json.dumps(fixtures_report, indent=2, sort_keys=True))
        return 0 if fixtures_report["checks"]["passed"] else 2
    if not fixtures_report["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0324 unavailable")

    seed = secrets.token_hex(32)
    write_json(run / "private-router-refinement-world-seed.json", {
        "seed": seed, "seed_digest": p82.digest(seed),
    })
    stake = base316.stake_of(parent)
    diagnostic_fronts = fronts(seed, stake, p82, heldout=False)
    diagnostic = summaries(diagnostic_fronts, parent["active_proposal_search_capability"]["source"], stake)
    incumbent_route_result = base.run_router(parent, diagnostic)
    incumbent_route = route_receipt(
        parent, diagnostic, incumbent_route_result["parsed"], p82,
        "diagnostic-incumbent-route",
    )
    dead = diagnostic[0]
    gain = diagnostic[1]
    consequence = {
        "authority": AUTHORITY + "-diagnostic-route-consequence",
        "route_receipt_digest": incumbent_route["receipt_digest"],
        "selected_front_id": incumbent_route["route"]["selected_front_id"],
        "selected_current_pass_count": dead["current_pass_count"],
        "selected_best_pass_count": dead["best_pass_count"],
        "selected_improvement_found": dead["improvement_found"],
        "alternative_front_id": gain["front_id"],
        "alternative_current_pass_count": gain["current_pass_count"],
        "alternative_best_pass_count": gain["best_pass_count"],
        "alternative_improvement_found": gain["improvement_found"],
        "outcome_authority": True,
    }
    consequence["receipt_digest"] = p82.digest(consequence)
    write_json(run / "diagnostic-fronts.json", diagnostic_fronts)
    write_json(run / "diagnostic-front-summaries.json", diagnostic)
    write_json(run / "diagnostic-incumbent-route.json", incumbent_route)
    write_json(run / "diagnostic-route-consequence.json", consequence)

    public = public_fixtures(parent["active_proposal_search_capability"]["applicability"], diagnostic)
    context = b.base274.context_for(core, base130, runtime, run / "actors", repo)
    router_actor = run_router_actor(
        context, run / "router-revision", parent, diagnostic, consequence, public
    )
    if router_actor["accepted"]:
        changed, unchanged, correction, capability = compile_router_branches(
            parent, router_actor, diagnostic, consequence, p82
        )
    else:
        changed = unchanged = parent
        correction = capability = None
    write_json(run / "changed-router-subject.json", changed)
    write_json(run / "unchanged-active-router-subject.json", unchanged)

    heldout_fronts = fronts(seed, stake, p82, heldout=True)
    heldout = summaries(heldout_fronts, parent["active_proposal_search_capability"]["source"], stake)
    changed_route_result = run_router_source(
        changed["active_proposal_search_router"]["source"],
        changed["active_proposal_search_capability"]["applicability"], heldout,
    )
    unchanged_route_result = base.run_router(unchanged, heldout)
    changed_route = route_receipt(
        changed, heldout, changed_route_result["parsed"], p82, "changed-router-route"
    )
    unchanged_route = route_receipt(
        unchanged, heldout, unchanged_route_result["parsed"], p82, "unchanged-router-route"
    )
    write_json(run / "heldout-fronts.json", heldout_fronts)
    write_json(run / "heldout-front-summaries.json", heldout)
    write_json(run / "changed-router-route.json", changed_route)
    write_json(run / "unchanged-router-route.json", unchanged_route)

    changed_front = base.selected_front(heldout_fronts, changed_route["route"])
    changed_actor = base.run_actor(
        context, run / "changed-successor", changed, changed_front["contacts"],
        changed_route, "changed-router-search-successor",
    )
    changed_score = cumulative_score(changed_actor["candidate_stake"], seed, p82) if changed_actor["accepted"] else None
    operational = bool(
        router_actor["accepted"] and changed_actor["accepted"] and changed_actor["changed"]
        and changed_route["route"]["selected_front_id"] == heldout[0]["front_id"]
        and changed_actor["training_replay"]["pass_count"] == 3
        and changed_score["prior_floor"]["pass_count"] == 20
        and changed_score["new_regime"]["pass_count"] == 5
        and changed_score["all_regimes"]["pass_count"] == 25
    )
    child, stake_binding, replay, invocation = (
        base.compile_child(
            changed, changed_actor, changed_front["contacts"], changed_score,
            changed_route, p82,
        ) if operational else (parent, None, None, None)
    )
    write_json(run / "candidate-operational-subject.json", child)

    unchanged_front = base.selected_front(heldout_fronts, unchanged_route["route"])
    unchanged_actor = base.run_actor(
        context, run / "unchanged-successor", unchanged,
        unchanged_front["contacts"], unchanged_route,
        "unchanged-router-search-successor",
    )
    unchanged_score = cumulative_score(unchanged_actor["candidate_stake"], seed, p82) if unchanged_actor["accepted"] else None
    causal = bool(
        operational and unchanged_actor["accepted"] and not unchanged_actor["changed"]
        and unchanged_route["route"]["selected_front_id"] == heldout[1]["front_id"]
        and not unchanged_actor["search_result"]["improvement_found"]
        and unchanged_score["prior_floor"]["pass_count"] == 20
        and unchanged_score["new_regime"]["pass_count"] == 0
        and unchanged_score["all_regimes"]["pass_count"] == 20
    )
    checks = {
        "preflight_passed": fixtures_report["checks"]["passed"],
        "private_seed_postfreeze": True,
        "diagnostic_incumbent_selects_dead_end": incumbent_route["route"]["selected_front_id"] == dead["front_id"]
        and dead["current_pass_count"] == dead["best_pass_count"] == 2,
        "diagnostic_alternative_has_reachable_gain": gain["current_pass_count"] == 0
        and gain["best_pass_count"] == 3 and gain["improvement_found"],
        "router_actor_clean_and_changed": router_actor["accepted"] and router_actor["changed"],
        "router_actor_public_conformance": router_actor["accepted"] and router_actor["conformance"]["passed"],
        "branches_retain_same_proposal": correction is not None
        and changed["proposal_search_router_corrections"][-1]
        == unchanged["proposal_search_router_corrections"][-1]
        and changed["proposal_search_router_capabilities"][-1]
        == unchanged["proposal_search_router_capabilities"][-1],
        "only_active_router_binding_separates_branches": changed["active_proposal_search_router"]
        != unchanged["active_proposal_search_router"],
        "changed_router_selects_reachable_gain": changed_route["route"]["selected_front_id"] == heldout[0]["front_id"],
        "changed_successor_clean": changed_actor["accepted"],
        "changed_successor_adopts_search_witness": changed_actor["accepted"]
        and changed_actor["workspace_evaluation"]["candidate_from_search"],
        "changed_successor_reaches_25_and_preserves_floor": operational,
        "operational_child_sealed_before_control": (run / "candidate-operational-subject.json").exists(),
        "unchanged_router_selects_dead_end": unchanged_route["route"]["selected_front_id"] == heldout[1]["front_id"],
        "unchanged_successor_clean": unchanged_actor["accepted"],
        "unchanged_successor_finds_no_improvement": unchanged_actor["accepted"]
        and not unchanged_actor["search_result"]["improvement_found"],
        "active_binding_ablation_removes_expansion": causal,
        "child_retains_actor_authored_router": not operational or (
            child["active_proposal_search_router"] == capability
            and child["proposal_search_router_corrections"][-1] == correction
            and child["proposal_search_invocation_receipts"][-1] == invocation
        ),
        "child_open_conformant": child["continuation"]["status"] == "open"
        and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_causal_receipt": result323["receipt_digest"],
        "private_world_seed_digest": p82.digest(seed),
        "diagnostic_front_summaries": diagnostic,
        "diagnostic_incumbent_route": incumbent_route,
        "diagnostic_route_consequence": consequence,
        "router_actor": router_actor,
        "router_correction": correction,
        "router_capability": capability,
        "heldout_front_summaries": heldout,
        "changed_route": changed_route,
        "changed_successor_actor": changed_actor,
        "changed_score": changed_score,
        "stake_binding": stake_binding,
        "training_replay_receipt": replay,
        "invocation_receipt": invocation,
        "unchanged_route": unchanged_route,
        "unchanged_successor_actor": unchanged_actor,
        "unchanged_score": unchanged_score,
        "checks": checks,
        "operational_transition_passed": operational,
        "consequence_revised_routing_supported": causal,
        "observer_disposition": "promoted" if checks["passed"] else (
            "conditional" if operational else "rejected"
        ),
        "subject_disposition": child["continuation"]["status"],
        "final_subject_digest": child["artifact_digest"],
        "fresh_actor_count": 3,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
