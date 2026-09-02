from __future__ import annotations

import argparse
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
BASE_PATH = ROOT / "ot_0322_executable_search_retention_reuse.py"
BASE_SHA256 = "262e4b01bfa10ea884ad9d78e40a9b26e375616c762d9ba94d6096c0f8d36c4d"
PARENT_DIGEST = "09d58f1ad5849a3545f07b43e2b6058328133f4d243020cc591a72f71560e091"
OT322_RECEIPT = "8cd60fd0c90a14357a0b78019e83da083fe7544385064e4fd116ea243a940a3d"
SEARCH_CAPABILITY_RECEIPT = "21cb74fa0f4f505c2e0062b515849185584ac56460a575d58a4c67b8ae43937d"
AUTHORITY = "ot-0323-applicability-routed-search-invocation"
SCHEMA = REPO / "spec" / "ot-0314-stake-revision.schema.json"
INVOKE_RULE = "incumbent fails at least one available selection contact"


ROUTER_SOURCE = '''import json
from pathlib import Path
state=json.loads(Path("applicability-state.json").read_text())
fronts=json.loads(Path("front-search-summaries.json").read_text())
rule=state.get("invoke_when")
selected=None
reason="no-applicable-opening"
if rule=="incumbent fails at least one available selection contact":
    eligible=[row for row in fronts if row["current_pass_count"]<row["available_count"]]
    if eligible:
        selected=min(eligible,key=lambda row:row["front_id"])["front_id"]
        reason="incumbent-contact-failure"
elif rule is None and fronts:
    selected=fronts[0]["front_id"]
    reason="applicability-erased-first-offered-fallback"
result={"action":"invoke-search" if selected else "wait","selected_front_id":selected,"reason":reason,"applicability_rule":rule}
print(json.dumps(result,sort_keys=True)); raise SystemExit(0)
'''


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError("OT-0322 changed")
    spec = importlib.util.spec_from_file_location("ot0323_frozen_ot0322", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
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
    run = (args.evidence_root or store / "runs" / "OT-0323").resolve()
    parent = selector.load_artifact(
        p82, repo, store, "OT-0322", "open-subject-after-executable-search-reuse.json"
    )
    result322 = selector.load_artifact(
        p82, repo, store, "OT-0322", "executable-search-retention-reuse-aggregate.json"
    )
    return (
        repo, store, run, p82, runtime, parent, result322, selector, raw314,
        result318, core, base130,
    )


def token(seed, label):
    return hashlib.sha256(bytes.fromhex(seed) + label.encode()).hexdigest()


def equal_length_loop_sources():
    useful = (
        'def route(case):\n'
        '    values=("harbor","shelter","clinic","relay")\n'
        '    return values[case.get("signal")]\n'
    )
    decoy = (
        'def route(case):\n'
        '    values=[]\n'
        '    for value in ("harbor",):\n'
        '        values.append(value)\n'
        '    return values[0]\n'
    )
    target = max(len(useful.encode()), len(decoy.encode())) + 2

    def pad(source):
        missing = target - len(source.encode())
        return source + ("#" * (missing - 1)) + "\n"

    useful, decoy = pad(useful), pad(decoy)
    if len(useful.encode()) != len(decoy.encode()):
        raise RuntimeError("loop source padding failed")
    return useful, decoy


def loop_descriptor(seed, label, useful):
    useful_source, decoy_source = equal_length_loop_sources()
    source = useful_source if useful else decoy_source
    return {
        "world_id": "w-" + token(seed, label)[:16],
        "public_package_digest": hashlib.sha256(
            source.encode() + bytes.fromhex(token(seed, label))
        ).hexdigest(),
        "features": base314.base305.source_features(source),
    }, source


def loop_episodes(seed, p82):
    rows = []
    contexts = [{"signal": value} for value in (0, 1, 2, 3)]
    for index in range(8):
        useful, useful_source = loop_descriptor(seed, f"{index}-useful", True)
        decoy, decoy_source = loop_descriptor(seed, f"{index}-decoy", False)
        catalog = sorted([useful, decoy], key=lambda row: row["world_id"])
        option = {
            useful["world_id"]: base314.executable_option_value(useful_source, contexts),
            decoy["world_id"]: base314.executable_option_value(decoy_source, contexts),
        }
        rows.append({
            "episode_id": "e-" + token(seed, str(index))[:16],
            "catalog": catalog,
            "sealed_contexts_digest": p82.digest(contexts),
            "option_value": option,
            "best_world_id": max(option, key=option.get),
        })
    return rows[:3], rows[3:]


def front_id(seed, label):
    return "front-" + token(seed, label)[:16]


def offered_fronts(seed, stake, p82):
    stable_training, _ = base.episodes(seed, p82)
    contradicted_training, _ = loop_episodes(seed, p82)
    return [
        {
            "front_id": front_id(seed, "first-offered-saturated"),
            "contacts": base.selection_contacts(stake, stable_training, p82),
            "offer_index": 0,
        },
        {
            "front_id": front_id(seed, "second-offered-contradicted"),
            "contacts": base.selection_contacts(stake, contradicted_training, p82),
            "offer_index": 1,
        },
    ]


def front_summaries(fronts, search_source, stake):
    summaries = []
    for front in fronts:
        searched = base.run_search(search_source, stake, front["contacts"])
        if searched["returncode"] or searched["parsed"] is None:
            raise RuntimeError("front search failed")
        result = searched["parsed"]
        summaries.append({
            "front_id": front["front_id"],
            "offer_index": front["offer_index"],
            "available_count": result["available_count"],
            "current_pass_count": result["current_pass_count"],
            "best_pass_count": result["best_pass_count"],
            "improvement_found": result["improvement_found"],
            "search_result_digest": hashlib.sha256(
                json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        })
    return summaries


def router_capability(parent, p82):
    body = {
        "authority": AUTHORITY + "-retained-router-capability",
        "source_subject_digest": parent["artifact_digest"],
        "search_capability_receipt_digest": parent["active_proposal_search_capability"]["receipt_digest"],
        "source": ROUTER_SOURCE,
        "source_digest": hashlib.sha256(ROUTER_SOURCE.encode()).hexdigest(),
        "interface": {
            "inputs": ["applicability-state.json", "front-search-summaries.json"],
            "output": "one selected front for search invocation or wait",
        },
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def compile_router_subject(parent, p82):
    router = router_capability(parent, p82)
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["proposal_search_router_capabilities"] = [
        *child.get("proposal_search_router_capabilities", []), router
    ]
    child["active_proposal_search_router"] = router
    return p82.seal(child), router


def erase_applicability(subject, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    capability = copy.deepcopy(child["active_proposal_search_capability"])
    capability.pop("receipt_digest", None)
    capability["authority"] = AUTHORITY + "-applicability-erased-control"
    capability["applicability"] = {
        **capability["applicability"],
        "invoke_when": None,
    }
    capability["receipt_digest"] = p82.digest(capability)
    child["proposal_search_capabilities"] = [
        *child["proposal_search_capabilities"][:-1], capability
    ]
    child["active_proposal_search_capability"] = capability
    return p82.seal(child), capability


def run_router(subject, summaries):
    applicability = subject["active_proposal_search_capability"]["applicability"]
    with tempfile.TemporaryDirectory(prefix="ot0323-router-") as temporary:
        root = Path(temporary)
        write_json(root / "applicability-state.json", applicability)
        write_json(root / "front-search-summaries.json", summaries)
        (root / "route_search.py").write_text(
            subject["active_proposal_search_router"]["source"]
        )
        completed = subprocess.run(
            [sys.executable, "route_search.py"], cwd=root, text=True,
            capture_output=True, timeout=30, check=False,
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = None
    return {"returncode": completed.returncode, "parsed": parsed, "stderr": completed.stderr}


def route_receipt(subject, summaries, route, p82, *, erased):
    body = {
        "authority": AUTHORITY + ("-erased-route" if erased else "-subject-route"),
        "source_subject_digest": subject["artifact_digest"],
        "search_capability_receipt_digest": subject["active_proposal_search_capability"]["receipt_digest"],
        "router_capability_receipt_digest": subject["active_proposal_search_router"]["receipt_digest"],
        "front_summary_digests": [p82.digest(row) for row in summaries],
        "route": route,
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def selected_front(fronts, route):
    matches = [front for front in fronts if front["front_id"] == route["selected_front_id"]]
    if len(matches) != 1:
        raise RuntimeError("route did not select exactly one offered front")
    return matches[0]


def score(stake, seed, p82):
    prior = (
        base314.episodes(seed, p82)[1]
        + base316.episodes(seed, p82)[1]
        + base.episodes(seed, p82)[1]
    )
    new = loop_episodes(seed, p82)[1]
    return {
        "prior_floor": base319.score(stake, prior, p82),
        "new_regime": base319.score(stake, new, p82),
        "all_regimes": base319.score(stake, prior + new, p82),
    }


def seed_actor(root, subject, contacts, route):
    seed = base.seed_actor(
        root, subject, contacts,
        subject["active_proposal_search_capability"]["source"],
    )
    write_json(seed / "invocation-route.json", route)
    envelope = json.loads((seed / "mutation-envelope.json").read_text())
    envelope["immutable"] = [
        *envelope["immutable"][:-2],
        "invocation-route.json",
        *envelope["immutable"][-2:],
    ]
    write_json(seed / "mutation-envelope.json", envelope)
    (seed / "README.md").write_text(
        "Continue from the exact subject after its retained applicability rule and router selected "
        "one of multiple available contact fronts. invocation-route.json records that selection; "
        "completed-selection-contacts.json contains only the selected authoritative contact. Use "
        "the executable mechanisms actually available here to decide whether to revise or retain. "
        "No other front, private world, held-out score, target weights, evaluator, sibling, or "
        "prescribed edit is supplied. Edit only stake-revision.json. You must run python3 "
        "search_revisions.py, python3 evaluate_revision.py, and python3 check_revision.py, then "
        "inspect the exact diff before returning the report.\n"
    )
    return seed


def run_actor(context, root, subject, contacts, route, label):
    seed = seed_actor(root, subject, contacts, route)
    output, audit0, workspace, _ = context.run_actor(
        label, seed, SCHEMA, (seed / "README.md").read_text().strip()
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    source = subject["active_proposal_search_capability"]["source"]
    try:
        candidate = json.loads((workspace / "stake-revision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in immutable
        )
        checker_ok = base315.corrected_accepts(
            base315.run_checker(
                base315.CORRECTED_CHECKER, candidate, base315.contract_for(subject)
            )
        )
        replayed = base319.replay(candidate, contacts)
        searched = base.run_search(source, base316.stake_of(subject), contacts)
        search_ok = searched["returncode"] == 0 and searched["parsed"] is not None
        checker_invoked = base.named_command_succeeded(trace, "check_revision.py")
        workbench_invoked = base.named_command_succeeded(trace, "evaluate_revision.py")
        search_invoked = base.named_command_succeeded(trace, "search_revisions.py")
        changed = candidate != base316.stake_of(subject)
        candidates = searched["parsed"]["candidates"] if search_ok else []
        candidate_from_search = bool(
            not changed or candidate["weights"] in [row["weights"] for row in candidates]
        )
    except (OSError, ValueError, KeyError, TypeError):
        candidate = replayed = searched = None
        immutable_ok = checker_ok = search_ok = False
        checker_invoked = workbench_invoked = search_invoked = False
        changed = candidate_from_search = False
    semantic = bool(
        immutable_ok and checker_ok and search_ok and checker_invoked
        and workbench_invoked and search_invoked and candidate_from_search
        and base.corrected_accepts(subject, candidate)
        and base314.output_valid(output, changed)
    )
    expected = ["stake-revision.json"] if changed else []
    audit = context.audit_actor(label, output, audit0, semantic, expected)
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(semantic and base236.g10(normalized))
    return {
        "accepted": accepted,
        "candidate_stake": candidate,
        "changed": changed,
        "output": output,
        "audit": audit,
        "g10_disposition": accepted,
        "search_result": searched["parsed"] if searched else None,
        "training_replay": replayed["parsed"] if replayed else None,
        "workspace_evaluation": {
            "immutable_ok": immutable_ok,
            "checker_ok": checker_ok,
            "search_ok": search_ok,
            "candidate_from_search": candidate_from_search,
            "checker_invoked": checker_invoked,
            "workbench_invoked": workbench_invoked,
            "search_invoked": search_invoked,
            "semantic": semantic,
        },
    }


def compile_child(subject, actor, contacts, evaluation, route, p82):
    child, binding, replay = base.compile_child(
        subject, actor, contacts, evaluation, p82
    )
    invocation_body = {
        "authority": AUTHORITY + "-invocation-receipt",
        "source_subject_digest": subject["artifact_digest"],
        "route_receipt_digest": route["receipt_digest"],
        "proposal_search_capability_receipt_digest": subject["active_proposal_search_capability"]["receipt_digest"],
        "stake_binding_digest": binding["binding_digest"],
        "selected_front_id": route["route"]["selected_front_id"],
        "training_outcome_receipt_digests": [
            row["outcome"]["receipt_digest"] for row in contacts
        ],
    }
    invocation = {**invocation_body, "receipt_digest": p82.digest(invocation_body)}
    child.pop("artifact_digest", None)
    child["proposal_search_invocation_receipts"] = [
        *child.get("proposal_search_invocation_receipts", []), invocation
    ]
    return p82.seal(child), binding, replay, invocation


def preflight(root, p82, runtime, parent, result322):
    root.mkdir(parents=True, exist_ok=True)
    routed, router = compile_router_subject(parent, p82)
    erased, erased_capability = erase_applicability(routed, p82)
    fixture_seed = "00" * 32
    incumbent = base316.stake_of(parent)
    fronts = offered_fronts(fixture_seed, incumbent, p82)
    summaries = front_summaries(
        fronts, routed["active_proposal_search_capability"]["source"], incumbent
    )
    active_route = run_router(routed, summaries)["parsed"]
    erased_route = run_router(erased, summaries)["parsed"]
    active_front = selected_front(fronts, active_route)
    erased_front = selected_front(fronts, erased_route)
    active_search = base.run_search(
        routed["active_proposal_search_capability"]["source"], incumbent,
        active_front["contacts"],
    )["parsed"]
    candidate = copy.deepcopy(incumbent)
    candidate["weights"] = active_search["candidates"][0]["weights"]
    candidate["rationale"] = "Candidate-free applicability routing fixture."
    candidate_score = score(candidate, fixture_seed, p82)
    incumbent_score = score(incumbent, fixture_seed, p82)
    useful_source, decoy_source = equal_length_loop_sources()
    stable_summary, contradicted_summary = summaries
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_parent_and_receipt": parent["artifact_digest"] == PARENT_DIGEST
        and result322["receipt_digest"] == OT322_RECEIPT
        and result322["observer_disposition"] == "promoted",
        "exact_search_capability_retained": parent["active_proposal_search_capability"]["receipt_digest"]
        == SEARCH_CAPABILITY_RECEIPT
        and parent["active_proposal_search_capability"]["source"] == base.SEARCH_SOURCE,
        "router_compiled_and_conformant": routed["active_proposal_search_router"] == router
        and hashlib.sha256(router["source"].encode()).hexdigest() == router["source_digest"]
        and runtime.identity_conforms(routed),
        "erasure_changes_only_applicability_record": erased_capability["source"] == base.SEARCH_SOURCE
        and erased_capability["applicability"]["invoke_when"] is None
        and runtime.identity_conforms(erased),
        "loop_sources_equal_length": len(useful_source.encode()) == len(decoy_source.encode()),
        "loop_world_isolates_loop_feature": all(
            row["catalog"][0]["features"][name] == row["catalog"][1]["features"][name]
            for row in loop_episodes(fixture_seed, p82)[0]
            for name in ("branch_nodes", "call_nodes", "comparison_nodes", "source_bytes")
        ) and all(
            row["catalog"][0]["features"]["loop_nodes"]
            != row["catalog"][1]["features"]["loop_nodes"]
            for row in loop_episodes(fixture_seed, p82)[0]
        ),
        "first_front_saturated": stable_summary["current_pass_count"] == 3
        and stable_summary["best_pass_count"] == 3
        and not stable_summary["improvement_found"],
        "second_front_contradicted_and_improvable": contradicted_summary["current_pass_count"] == 0
        and contradicted_summary["best_pass_count"] == 3
        and contradicted_summary["improvement_found"],
        "active_rule_routes_to_contradiction": active_route["action"] == "invoke-search"
        and active_route["selected_front_id"] == fronts[1]["front_id"]
        and active_route["reason"] == "incumbent-contact-failure",
        "erasure_routes_to_first_saturated_front": erased_route["action"] == "invoke-search"
        and erased_route["selected_front_id"] == fronts[0]["front_id"]
        and erased_route["reason"] == "applicability-erased-first-offered-fallback",
        "candidate_reaches_20_and_preserves_15": candidate_score["prior_floor"]["pass_count"] == 15
        and candidate_score["new_regime"]["pass_count"] == 5
        and candidate_score["all_regimes"]["pass_count"] == 20,
        "incumbent_preserves_15_and_fails_new": incumbent_score["prior_floor"]["pass_count"] == 15
        and incumbent_score["new_regime"]["pass_count"] == 0
        and incumbent_score["all_regimes"]["pass_count"] == 15,
        "router_contains_no_target": all(
            term not in ROUTER_SOURCE
            for term in ("heldout", "private", '"loop_nodes": -3', "target_weight")
        ),
        "exact_open_conformant": parent["continuation"]["status"] == "open"
        and runtime.identity_conforms(parent),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "fixture_seed_digest": p82.digest(fixture_seed),
        "router_source_digest": hashlib.sha256(ROUTER_SOURCE.encode()).hexdigest(),
        "router_capability_receipt_digest": router["receipt_digest"],
        "active_front_summaries": summaries,
        "active_route": active_route,
        "erased_route": erased_route,
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
    (
        repo, store, run, p82, runtime, parent, result322, _, _, _, core,
        base130,
    ) = setup(args)
    retained = run / "preflight" / "fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(
        run / "preflight", p82, runtime, parent, result322
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0323 unavailable")

    routed_subject, router = compile_router_subject(parent, p82)
    erased_subject, erased_capability = erase_applicability(routed_subject, p82)
    write_json(run / "router-capability-subject.json", routed_subject)
    write_json(run / "applicability-erased-subject.json", erased_subject)

    seed = secrets.token_hex(32)
    write_json(run / "private-multi-opening-world-seed.json", {
        "seed": seed, "seed_digest": p82.digest(seed)
    })
    incumbent = base316.stake_of(parent)
    fronts = offered_fronts(seed, incumbent, p82)
    summaries = front_summaries(fronts, base.SEARCH_SOURCE, incumbent)
    write_json(run / "offered-fronts.json", fronts)
    write_json(run / "front-search-summaries.json", summaries)

    active_route_result = run_router(routed_subject, summaries)
    erased_route_result = run_router(erased_subject, summaries)
    if active_route_result["returncode"] or erased_route_result["returncode"]:
        raise RuntimeError("private routing failed")
    active_route = route_receipt(
        routed_subject, summaries, active_route_result["parsed"], p82, erased=False
    )
    erased_route = route_receipt(
        erased_subject, summaries, erased_route_result["parsed"], p82, erased=True
    )
    write_json(run / "active-invocation-route.json", active_route)
    write_json(run / "erased-invocation-route.json", erased_route)

    active_front = selected_front(fronts, active_route["route"])
    erased_front = selected_front(fronts, erased_route["route"])
    context = b.base274.context_for(core, base130, runtime, run / "actors", repo)
    actor = run_actor(
        context, run / "candidate", routed_subject, active_front["contacts"],
        active_route, "applicability-routed-search-user",
    )
    candidate_score = score(actor["candidate_stake"], seed, p82) if actor["accepted"] else None
    operational = bool(
        actor["accepted"] and actor["changed"]
        and active_route["route"]["selected_front_id"] == fronts[1]["front_id"]
        and actor["training_replay"]["pass_count"] == 3
        and candidate_score["prior_floor"]["pass_count"] == 15
        and candidate_score["new_regime"]["pass_count"] == 5
        and candidate_score["all_regimes"]["pass_count"] == 20
    )
    child, binding, replay, invocation = (
        compile_child(
            routed_subject, actor, active_front["contacts"], candidate_score,
            active_route, p82,
        ) if operational else (parent, None, None, None)
    )
    write_json(run / "candidate-operational-subject.json", child)

    erased_actor = run_actor(
        context, run / "erased", erased_subject, erased_front["contacts"],
        erased_route, "applicability-erased-search-user",
    )
    erased_score = score(erased_actor["candidate_stake"], seed, p82) if erased_actor["accepted"] else None
    causal = bool(
        operational and erased_actor["accepted"]
        and erased_route["route"]["selected_front_id"] == fronts[0]["front_id"]
        and not erased_actor["search_result"]["improvement_found"]
        and not erased_actor["changed"]
        and erased_score["all_regimes"]["pass_count"] == 15
    )
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "private_seed_postfreeze": True,
        "router_compiled_before_contact": (run / "router-capability-subject.json").exists(),
        "same_front_summaries_for_both_routes": True,
        "active_rule_routes_to_contradicted_front": active_route["route"]["selected_front_id"]
        == fronts[1]["front_id"],
        "candidate_actor_clean": actor["accepted"],
        "candidate_adopts_inherited_search_witness": actor["accepted"]
        and actor["workspace_evaluation"]["candidate_from_search"],
        "candidate_reaches_20_and_preserves_floor": operational,
        "operational_child_sealed_before_control": (run / "candidate-operational-subject.json").exists(),
        "erased_rule_routes_to_saturated_front": erased_route["route"]["selected_front_id"]
        == fronts[0]["front_id"],
        "erased_actor_clean": erased_actor["accepted"],
        "erased_front_has_no_improvement": erased_actor["accepted"]
        and not erased_actor["search_result"]["improvement_found"],
        "applicability_erasure_removes_expansion": causal,
        "child_retains_router_and_invocation": not operational or (
            child["active_proposal_search_router"] == router
            and child["proposal_search_invocation_receipts"][-1] == invocation
            and binding["proposal_search_capability_receipt_digest"]
            == routed_subject["active_proposal_search_capability"]["receipt_digest"]
        ),
        "child_open_conformant": child["continuation"]["status"] == "open"
        and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_causal_receipt": result322["receipt_digest"],
        "private_world_seed_digest": p82.digest(seed),
        "router_capability": router,
        "front_search_summaries": summaries,
        "active_route": active_route,
        "candidate_actor": actor,
        "candidate_score": candidate_score,
        "stake_binding": binding,
        "training_replay_receipt": replay,
        "invocation_receipt": invocation,
        "erased_capability": erased_capability,
        "erased_route": erased_route,
        "erased_actor": erased_actor,
        "erased_score": erased_score,
        "checks": checks,
        "operational_transition_passed": operational,
        "applicability_routed_invocation_supported": causal,
        "observer_disposition": "promoted" if checks["passed"] else (
            "conditional" if operational else "rejected"
        ),
        "subject_disposition": child["continuation"]["status"],
        "final_subject_digest": child["artifact_digest"],
        "fresh_actor_count": 2,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
