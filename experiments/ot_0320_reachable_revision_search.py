from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path


sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0319_cumulative_stake_integration.py"
BASE_SHA256 = "f91195225623290784b6daaddef3a0f1892696fd5e5eefb435ac824ea204d204"
PARENT_DIGEST = "21e90d4729e9d6d64d5e816b7301141affd2ddbb16502e30f963c0ba83b4d3c4"
OT319_RECEIPT = "03492917d76bde98f6e5b12352818ed02436d0c466a3f84c8ed43f7a557de1a7"
AUTHORITY = "ot-0320-reachable-revision-search"
SCHEMA = REPO / "spec" / "ot-0314-stake-revision.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0319 changed")
    spec = importlib.util.spec_from_file_location("ot0320_frozen_ot0319", BASE_PATH)
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
write_json = base.write_json


SEARCH_TOOL = '''import itertools
import json
from pathlib import Path
features=("branch_nodes","call_nodes","comparison_nodes","loop_nodes","source_bytes")
stake=json.loads(Path("stake-revision.json").read_text())
contacts=json.loads(Path("completed-selection-contacts.json").read_text())
contract=json.loads(Path("stake-revision-contract.json").read_text())
available=[row for row in contacts if row["outcome"].get("outcome_authority") is True and isinstance(row["outcome"].get("best_world_id"),str)]
def fitness(weights):
    passed=0
    for contact in available:
        ranked=[]
        for item in contact["catalog"]:
            value=sum(weights[name]*item["features"][name] for name in features)
            ranked.append((value,item["public_package_digest"],item["world_id"]))
        ranked.sort(key=lambda row:(-row[0],row[1]))
        gap=ranked[0][0]-ranked[1][0]
        selected=ranked[0][2] if gap>=stake["minimum_score_gap"] else None
        passed+=selected==contact["outcome"]["best_world_id"]
    return passed
current=stake["weights"]
active=[name for name in features if any(row["catalog"][0]["features"][name]!=row["catalog"][1]["features"][name] for row in available)]
low,high=contract["weight_integer_range"]
current_pass=fitness(current)
best_pass=current_pass
best=[]
for values in itertools.product(range(low,high+1),repeat=len(active)):
    weights=dict(current)
    for name,value in zip(active,values): weights[name]=value
    count=fitness(weights)
    distance=sum(abs(weights[name]-current[name]) for name in active)
    row={"weights":weights,"pass_count":count,"distance_from_current":distance}
    if count>best_pass: best_pass=count; best=[row]
    elif count==best_pass and count>current_pass: best.append(row)
best.sort(key=lambda row:(row["distance_from_current"],tuple(row["weights"][name] for name in features)))
result={"search_complete":True,"available_count":len(available),"active_dimensions":active,"current_pass_count":current_pass,"best_pass_count":best_pass,"improvement_found":best_pass>current_pass,"best_candidate_count":len(best),"candidates":best[:8]}
print(json.dumps(result,sort_keys=True)); raise SystemExit(0)
'''


def setup(args):
    (
        repo, store, _, p82, runtime, parent, result318, result315, raw314,
        selector, core, base130,
    ) = base.setup(args)
    run = (args.evidence_root or store / "runs" / "OT-0320").resolve()
    result319 = selector.load_artifact(
        p82, repo, store, "OT-0319", "cumulative-stake-integration-aggregate.json"
    )
    return repo, store, run, p82, runtime, parent, result318, result315, raw314, result319, selector, core, base130


def search(stake, contacts):
    with tempfile.TemporaryDirectory(prefix="ot0320-search-") as temporary:
        root = Path(temporary)
        write_json(root / "stake-revision.json", stake)
        write_json(root / "completed-selection-contacts.json", contacts)
        write_json(root / "stake-revision-contract.json", {"weight_integer_range": [-20, 20]})
        (root / "search_revisions.py").write_text(SEARCH_TOOL)
        completed = subprocess.run(
            [sys.executable, "search_revisions.py"], cwd=root, text=True,
            capture_output=True, timeout=30, check=False,
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = None
    return {"returncode": completed.returncode, "parsed": parsed, "stderr": completed.stderr}


def search_error(parent, result319, p82, *, erased):
    body = {
        "authority": AUTHORITY + ("-search-error-erased" if erased else "-search-error"),
        "source_subject_digest": parent["artifact_digest"],
        "source_rejection_receipt": result319["receipt_digest"],
        "status": "unavailable-earlier-outcome-erased" if erased else "unresolved-reachable-successor-search",
        "available_training_count": 3 if erased else 6,
        "incumbent_pass_count": 3,
        "prior_actor_tested_successor_count": 0,
        "prior_surface_exhaustion_claim_authoritative": False,
        "prescribed_edit": None,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def seed_actor(root, parent, contacts, contact_projection, error):
    seed = base.seed_actor(root, parent, contacts, contact_projection)
    write_json(seed / "proposal-search-error.json", error)
    (seed / "search_revisions.py").write_text(SEARCH_TOOL)
    envelope = json.loads((seed / "mutation-envelope.json").read_text())
    envelope["immutable"] = [
        *envelope["immutable"][:-2],
        "proposal-search-error.json",
        "search_revisions.py",
        *envelope["immutable"][-2:],
    ]
    write_json(seed / "mutation-envelope.json", envelope)
    (seed / "README.md").write_text(
        "Continue from the exact active stake after OT-0319 retained a 3/6 rule without testing "
        "a successor. proposal-search-error.json records that unresolved non-authoritative claim. "
        "search_revisions.py exhaustively searches the already public bounded weights over only "
        "available authoritative outcomes and reports nearest best improving candidates or a "
        "complete no-improvement result. evaluate_revision.py tests the current stake in detail. "
        "No private world, held-out score, target weights, evaluator, sibling, or prescribed edit "
        "is supplied. Decide whether to revise or retain. Edit only stake-revision.json. You must "
        "successfully run python3 search_revisions.py, python3 evaluate_revision.py, and python3 "
        "check_revision.py, then inspect the exact diff before returning the report.\n"
    )
    return seed


def named_command_succeeded(trace, name):
    return base.base.named_command_succeeded(trace, name)


def run_actor(context, root, parent, contacts, contact_projection, error, label):
    seed = seed_actor(root, parent, contacts, contact_projection, error)
    output, audit0, workspace, _ = context.run_actor(
        label, seed, SCHEMA, (seed / "README.md").read_text().strip()
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    try:
        candidate = json.loads((workspace / "stake-revision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        checker_ok = base315.corrected_accepts(
            base315.run_checker(base315.CORRECTED_CHECKER, candidate, base315.contract_for(parent))
        )
        replayed = base.replay(candidate, contacts)
        searched = search(base316.stake_of(parent), contacts)
        search_matches = searched["returncode"] == 0 and searched["parsed"] is not None
        checker_invoked = named_command_succeeded(trace, "check_revision.py")
        workbench_invoked = named_command_succeeded(trace, "evaluate_revision.py")
        search_invoked = named_command_succeeded(trace, "search_revisions.py")
        changed = candidate != base316.stake_of(parent)
        candidate_from_search = (
            not changed or candidate["weights"] in [row["weights"] for row in searched["parsed"]["candidates"]]
        )
    except (OSError, ValueError, KeyError, TypeError):
        candidate, immutable_ok, checker_ok, replayed, searched = None, False, False, None, None
        search_matches = checker_invoked = workbench_invoked = search_invoked = changed = candidate_from_search = False
    semantic = bool(
        immutable_ok and checker_ok and search_matches and checker_invoked and workbench_invoked
        and search_invoked and candidate_from_search
        and base314.valid_candidate(parent, candidate) and base314.output_valid(output, changed)
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
            "search_matches_controller": search_matches,
            "candidate_from_search": candidate_from_search,
            "checker_invoked": checker_invoked,
            "workbench_invoked": workbench_invoked,
            "search_invoked": search_invoked,
            "semantic": semantic,
        },
    }


def compile_child(parent, actor, contacts, contact_projection, error, evaluation, p82):
    search_body = {
        "authority": AUTHORITY + "-search-receipt",
        "source_subject_digest": parent["artifact_digest"],
        "projection_receipt_digest": contact_projection["receipt_digest"],
        "search_error_receipt_digest": error["receipt_digest"],
        "search_tool_digest": hashlib.sha256(SEARCH_TOOL.encode()).hexdigest(),
        "result": actor["search_result"],
    }
    search_receipt = {**search_body, "receipt_digest": p82.digest(search_body)}
    child, binding, replay_receipt = base.compile_child(
        parent, actor, contacts, contact_projection, evaluation, p82
    )
    child.pop("artifact_digest", None)
    binding["proposal_search_receipt_digest"] = search_receipt["receipt_digest"]
    binding.pop("binding_digest", None)
    binding["binding_digest"] = p82.digest(binding)
    child["world_seeking_stake_revisions"][-1] = binding
    child["active_world_seeking_stake"] = binding
    child["proposal_search_errors"] = [*child.get("proposal_search_errors", []), error]
    child["proposal_search_receipts"] = [*child.get("proposal_search_receipts", []), search_receipt]
    child = p82.seal(child)
    return child, binding, replay_receipt, search_receipt


def preflight(root, p82, runtime, parent, result319, raw314, result318):
    root.mkdir(parents=True, exist_ok=True)
    contacts = base.retained_contacts(raw314, result318)
    erased = base.erase_earlier_outcomes(contacts, p82)
    incumbent = base316.stake_of(parent)
    full = search(incumbent, contacts)["parsed"]
    absent = search(incumbent, erased)["parsed"]
    fixture_seed = "00" * 32
    mixed = base314.episodes(fixture_seed, p82)[1] + base316.episodes(fixture_seed, p82)[1]
    candidate_scores = []
    for row in full["candidates"]:
        candidate = copy.deepcopy(incumbent)
        candidate["weights"] = row["weights"]
        candidate["rationale"] = "Candidate-free search conformance fixture."
        candidate_scores.append(base.score(candidate, mixed, p82)["pass_count"])
    trace = "\n".join(
        json.dumps({"item": {"type": "command_execution", "status": "completed", "exit_code": 0, "command": f"python3 {name}"}})
        for name in ("search_revisions.py", "evaluate_revision.py", "check_revision.py")
    )
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_rejected_parent": parent["artifact_digest"] == PARENT_DIGEST
        and result319["receipt_digest"] == OT319_RECEIPT
        and result319["observer_disposition"] == "rejected"
        and result319["final_subject_digest"] == PARENT_DIGEST,
        "full_search_finds_improvement": full["search_complete"] and full["available_count"] == 6
        and full["current_pass_count"] == 3 and full["best_pass_count"] == 6
        and full["improvement_found"] and bool(full["candidates"]),
        "reported_candidates_replay_6": all(row["pass_count"] == 6 for row in full["candidates"]),
        "reported_candidate_reaches_10": 10 in candidate_scores,
        "erased_search_complete_without_improvement": absent["search_complete"]
        and absent["available_count"] == 3 and absent["current_pass_count"] == 3
        and absent["best_pass_count"] == 3 and not absent["improvement_found"]
        and not absent["candidates"],
        "trace_requires_all_tools": all(
            named_command_succeeded(trace, name)
            for name in ("search_revisions.py", "evaluate_revision.py", "check_revision.py")
        ),
        "search_contains_no_private_target": all(
            term not in SEARCH_TOOL
            for term in ("heldout", "private", '"branch_nodes": -20', '"source_bytes": 1', "target_weight")
        ),
        "reported_candidates_checker_valid": all(
            base315.corrected_accepts(
                base315.run_checker(
                    base315.CORRECTED_CHECKER,
                    {**copy.deepcopy(incumbent), "weights": row["weights"], "rationale": "Conformance fixture."},
                    base315.contract_for(parent),
                )
            )
            for row in full["candidates"]
        ),
        "exact_open_conformant": parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "source_rejection_receipt": result319["receipt_digest"],
        "fixture_seed_digest": p82.digest(fixture_seed),
        "search_tool_digest": hashlib.sha256(SEARCH_TOOL.encode()).hexdigest(),
        "full_search_result": full,
        "erased_search_result": absent,
        "reported_candidate_mixed_scores": candidate_scores,
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
        repo, store, run, p82, runtime, parent, result318, result315, raw314,
        result319, selector, core, base130,
    ) = setup(args)
    retained = run / "preflight" / "fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(
        run / "preflight", p82, runtime, parent, result319, raw314, result318
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0320 unavailable")

    contacts = base.retained_contacts(raw314, result318)
    erased_contacts = base.erase_earlier_outcomes(contacts, p82)
    full_projection = base.projection(parent, contacts, p82, erased=False)
    erased_projection = base.projection(parent, erased_contacts, p82, erased=True)
    error = search_error(parent, result319, p82, erased=False)
    erased_error = search_error(parent, result319, p82, erased=True)
    incumbent = base316.stake_of(parent)
    prior = base.prior_stake(parent)

    seed = secrets.token_hex(32)
    write_json(run / "private-search-world-seed.json", {"seed": seed, "seed_digest": p82.digest(seed)})
    mixed = base314.episodes(seed, p82)[1] + base316.episodes(seed, p82)[1]
    current_score = base.score(incumbent, mixed, p82)
    prior_score = base.score(prior, mixed, p82)
    if current_score["pass_count"] != 5 or prior_score["pass_count"] != 5:
        raise RuntimeError("private trajectory does not preserve complementary baselines")

    context = b.base274.context_for(core, base130, runtime, run / "actors", repo)
    actor = run_actor(
        context, run / "candidate", parent, contacts, full_projection, error,
        "reachable-revision-search-user",
    )
    candidate_score = base.score(actor["candidate_stake"], mixed, p82) if actor["accepted"] else None
    operational = bool(
        actor["accepted"] and actor["changed"]
        and actor["search_result"]["best_pass_count"] == 6
        and actor["training_replay"]["pass_count"] == 6
        and candidate_score is not None and candidate_score["pass_count"] == 10
        and current_score["pass_count"] == 5 and prior_score["pass_count"] == 5
    )
    child, binding, replay_receipt, search_receipt = (
        compile_child(parent, actor, contacts, full_projection, error, candidate_score, p82)
        if operational else (parent, None, None, None)
    )
    write_json(run / "candidate-operational-subject.json", child)

    erased_actor = run_actor(
        context, run / "erased", parent, erased_contacts, erased_projection, erased_error,
        "reachable-revision-search-user-earlier-erased",
    )
    erased_score = base.score(erased_actor["candidate_stake"], mixed, p82) if erased_actor["accepted"] else None
    causal = bool(
        operational and erased_actor["accepted"]
        and erased_actor["search_result"]["search_complete"]
        and erased_actor["search_result"]["available_count"] == 3
        and not erased_actor["search_result"]["improvement_found"]
        and not (
            erased_actor["changed"] and erased_score is not None
            and erased_score["pass_count"] == 10
        )
    )
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "private_seed_postfreeze": True,
        "candidate_actor_clean": actor["accepted"],
        "candidate_adopts_search_witness": actor["accepted"] and actor["workspace_evaluation"]["candidate_from_search"],
        "candidate_integrates_training": actor["accepted"] and actor["training_replay"]["pass_count"] == 6,
        "candidate_beats_both_baselines": operational,
        "operational_child_sealed_before_control": (run / "candidate-operational-subject.json").exists(),
        "erased_actor_clean": erased_actor["accepted"],
        "erased_search_finds_no_improvement": erased_actor["accepted"]
        and not erased_actor["search_result"]["improvement_found"],
        "earlier_outcome_erasure_removes_cumulative_advantage": causal,
        "child_retains_search_path": not operational or (
            binding["proposal_search_receipt_digest"] == search_receipt["receipt_digest"]
            and child["proposal_search_receipts"][-1] == search_receipt
            and child["cumulative_stake_integration_receipts"][-1] == replay_receipt
        ),
        "child_open_conformant": child["continuation"]["status"] == "open" and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_rejection_receipt": result319["receipt_digest"],
        "private_world_seed_digest": p82.digest(seed),
        "proposal_search_error": error,
        "candidate_actor": actor,
        "candidate_score": candidate_score,
        "current_score": current_score,
        "prior_score": prior_score,
        "stake_integration_binding": binding,
        "training_replay_receipt": replay_receipt,
        "proposal_search_receipt": search_receipt,
        "erased_search_error": erased_error,
        "erased_actor": erased_actor,
        "erased_score": erased_score,
        "checks": checks,
        "operational_transition_passed": operational,
        "proposal_search_cumulative_integration_supported": causal,
        "observer_disposition": "promoted" if checks["passed"] else ("conditional" if operational else "rejected"),
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
