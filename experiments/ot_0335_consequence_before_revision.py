from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0334_scoped_provider_collision_recovery.py"
BASE_SHA256 = "7f7a5f69e5116cdf73124e1e8761c97fc5fb501535e74cced1cb6075068487f0"
PARENT_DIGEST = "afc02a9dbf73fba01d783501af5cc9adfedb036e89feb47b5b7407b6954eedbd"
OT334_RECEIPT = "7599e2e1bc5d3fc950a8b317132f454629c7e6b34069abef444b10b2914bbc19"
AUTHORITY = "ot-0335-consequence-before-revision"
SCHEMA = REPO / "spec/ot-0335-instability-response.schema.json"


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"frozen OT-0334 source changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0335_frozen_ot0334", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()
b = base.b
g11 = base.g11
write_json = base.write_json


def setup(args):
    values = base.setup(args)
    repo, store, _, p82, runtime = values[:5]
    core, base130 = values[9:11]
    run = (args.evidence_root or store / "runs/OT-0335").resolve()
    selector = base.base.base.base.base.base.b.authority_base.guide_base.load_base().selector_base
    load = lambda experiment, name: selector.load_artifact(p82, repo, store, experiment, name)
    parent = load("OT-0334", "open-subject-after-solicitation-exhaustion.json")
    result334 = load("OT-0334", "scoped-provider-collision-recovery-rejected-aggregate.json")
    return repo, store, run, p82, runtime, core, base130, parent, result334


def turnover_winners(history):
    winners = []
    for row in history:
        winner = row.get("selected_world_id") if row.get("supported") else None
        if winner is not None and winner not in winners:
            winners.append(winner)
    return winners if len(winners) > 1 else []


def revision_evidence(outcomes):
    return any(row.get("outcome_authority") is True and row.get("directional_error") is True for row in outcomes)


def valid_position(parent, result, p82):
    due = parent.get("active_world_seeking_stake_revision_due", {})
    stop = result.get("stop_receipt", {})
    return bool(
        parent.get("artifact_digest") == PARENT_DIGEST
        and result.get("receipt_digest") == OT334_RECEIPT
        and result.get("final_subject_digest") == PARENT_DIGEST
        and due == stop
        and due.get("next_operation") == "revise-world-seeking-stake"
        and due.get("history_digest") == p82.digest(result.get("selection_history"))
        and due.get("policy_binding_digest") == parent.get("active_environment_solicitation_policy", {}).get("binding_digest")
        and due.get("stake_binding_digest") == parent.get("active_world_seeking_stake", {}).get("binding_digest")
    )


def decision_semantic(decision, candidate_ids, history, outcomes):
    if not isinstance(decision, dict) or set(decision) != {"action", "world_ids", "rationale"}:
        return False
    if not isinstance(decision["rationale"], str) or not 1 <= len(decision["rationale"]) <= 2000:
        return False
    if not isinstance(decision["world_ids"], list) or len(decision["world_ids"]) != len(set(decision["world_ids"])):
        return False
    if any(world_id not in candidate_ids for world_id in decision["world_ids"]):
        return False
    if decision["action"] == "request-stake-revision":
        return not decision["world_ids"] and revision_evidence(outcomes)
    if decision["action"] == "acquire-comparative-consequence":
        return not revision_evidence(outcomes) and decision["world_ids"] == turnover_winners(history)
    if decision["action"] == "retain-world-seeking-stake":
        return not decision["world_ids"]
    return False


CHECKER = '''import json\nfrom pathlib import Path\nd=json.loads(Path("decision.json").read_text()); c=json.loads(Path("decision-contract.json").read_text()); ids=d.get("world_ids"); ok=isinstance(d,dict) and set(d)=={"action","world_ids","rationale"} and d.get("action") in c["actions"] and isinstance(ids,list) and len(ids)==len(set(ids)) and all(x in c["candidate_world_ids"] for x in ids) and isinstance(d.get("rationale"),str) and 1<=len(d["rationale"])<=2000; print(json.dumps({"valid":ok})); raise SystemExit(0 if ok else 2)\n'''


def seed_actor(root, parent, result):
    seed = root / "seed"
    seed.mkdir(parents=True)
    history = result["selection_history"]
    candidates = [{"world_id": row["world_id"], "public_package_digest": row["public_package_digest"], "features": row["features"]} for row in history[-1]["rows"]]
    projection = {
        "source_subject_digest": parent["artifact_digest"],
        "active_stake": parent["active_world_seeking_stake"],
        "active_policy": parent["active_environment_solicitation_policy"],
        "revision_due": parent["active_world_seeking_stake_revision_due"],
        "selection_history": history,
        "candidate_descriptors": candidates,
        "outcome_receipts": [],
        "continuation": parent["continuation"],
    }
    write_json(seed / "subject-position.json", projection)
    write_json(seed / "decision-contract.json", {
        "actions": ["request-stake-revision", "acquire-comparative-consequence", "retain-world-seeking-stake"],
        "candidate_world_ids": sorted(row["world_id"] for row in candidates),
        "authority_rule": "Stake revision requires a bound outcome receipt with outcome_authority true and directional_error true. Rank turnover alone is not directional outcome evidence.",
    })
    write_json(seed / "decision.json", {"action": "retain-world-seeking-stake", "world_ids": [], "rationale": "Replace with your decision from the inherited position."})
    (seed / "check_decision.py").write_text(CHECKER)
    immutable = ["subject-position.json", "decision-contract.json", "check_decision.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["decision.json"], "immutable": immutable})
    (seed / "README.md").write_text(
        "Continue from the exact open subject after its solicitation policy exhausted. Decide whether the retained evidence warrants requesting a stake revision now, retaining without a new evidence pursuit, or acquiring comparative consequence first. If comparison is needed, identify the catalogued worlds whose observed selection behavior makes the comparison causally relevant. You have no future or sealed outcomes. Edit only decision.json, run python3 check_decision.py, inspect the exact diff, then return the required JSON summary.\n"
    )
    return seed


def output_valid(output, decision):
    return bool(
        isinstance(output, dict)
        and output == {"action": "submit-instability-response", "files_changed": ["decision.json"]}
        and isinstance(decision, dict)
    )


def run_actor(context, p82, root, parent, result):
    label = "unlabeled-instability-responder"
    seed = seed_actor(root, parent, result)
    output, base_audit, workspace, _ = context.run_actor(label, seed, SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        checker = subprocess.run(["python3", "check_decision.py"], cwd=workspace, capture_output=True)
        candidate_ids = {row["world_id"] for row in result["selection_history"][-1]["rows"]}
        semantic = immutable_ok and checker.returncode == 0 and decision_semantic(decision, candidate_ids, result["selection_history"], [])
    except (OSError, ValueError, KeyError, TypeError):
        decision, semantic, immutable_ok = None, False, False
    audit = context.audit_actor(label, output, base_audit, semantic and output_valid(output, decision), ["decision.json"])
    certificate = base.base.certify_g11(context, label, audit)
    accepted = bool(semantic and output_valid(output, decision) and certificate["challenger_accepted"])
    return {"accepted": accepted, "decision": decision, "output": output, "audit": audit, "g11": certificate, "immutable_ok": immutable_ok}


def compile_comparison(parent, result, actor, p82):
    decision = actor["decision"]
    body = {
        "authority": AUTHORITY + "-comparative-consequence-request-binding",
        "source_subject_digest": parent["artifact_digest"],
        "source_exhaustion_receipt_digest": parent["active_world_seeking_stake_revision_due"]["receipt_digest"],
        "selection_history_digest": p82.digest(result["selection_history"]),
        "actor_patch_digest": actor["audit"]["patch_digest"],
        "world_ids": decision["world_ids"],
        "rationale": decision["rationale"],
        "stake_changed": False,
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    binding = {**body, "binding_digest": p82.digest(body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["comparative_world_contact_requests"] = [*child.get("comparative_world_contact_requests", []), binding]
    child["active_comparative_world_contact_request"] = binding
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Obtain independent consequence for the subject-selected worlds implicated by supported-winner turnover."}
    child["unresolved"] = "Which supported-winner candidate remains preferable after comparable independent world consequence?"
    return p82.seal(child), binding


def preflight(root, p82, runtime, parent, result):
    root.mkdir(parents=True, exist_ok=True)
    history = result["selection_history"]
    candidate_ids = {row["world_id"] for row in history[-1]["rows"]}
    winners = turnover_winners(history)
    acquisition = {"action": "acquire-comparative-consequence", "world_ids": winners, "rationale": "Acquire outcome evidence before changing the selector."}
    revision = {"action": "request-stake-revision", "world_ids": [], "rationale": "Revise after directional error."}
    counterfeit = [{"outcome_authority": False, "directional_error": True}]
    authoritative = [{"outcome_authority": True, "directional_error": True}]
    fake_actor = {"decision": acquisition, "audit": {"patch_digest": "0" * 64}}
    child, binding = compile_comparison(parent, result, fake_actor, p82)
    altered = copy.deepcopy(parent)
    altered.pop("active_world_seeking_stake_revision_due", None)
    seed = seed_actor(root / "seed", parent, result)
    corpus = "\n".join(path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file())
    sealed_fragments = [source for provider in result["providers"] for source in provider["package"]["sealed_reference_sources"].values()]
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_open_parent": valid_position(parent, result, p82) and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "two_supported_winners_turn_over": len(winners) == 2 and history[-2]["selected_world_id"] != history[-1]["selected_world_id"],
        "live_packet_has_no_outcomes": not revision_evidence([]),
        "acquisition_fixture_valid": decision_semantic(acquisition, candidate_ids, history, []),
        "arbitrary_comparison_rejected": not decision_semantic({**acquisition, "world_ids": sorted(candidate_ids)[:2]}, candidate_ids, history, []) if sorted(candidate_ids)[:2] != winners else True,
        "unlabeled_revision_rejected": not decision_semantic(revision, candidate_ids, history, []),
        "counterfeit_outcome_rejected": not decision_semantic(revision, candidate_ids, history, counterfeit),
        "authoritative_directional_error_permits_revision": decision_semantic(revision, candidate_ids, history, authoritative),
        "missing_revision_due_rejects": not valid_position(altered, result, p82),
        "comparison_preserves_stake_and_opens": child["active_world_seeking_stake"] == parent["active_world_seeking_stake"] and binding["stake_changed"] is False and child["continuation"]["status"] == "open" and runtime.identity_conforms(child),
        "actor_seed_excludes_sealed_world": all(fragment not in corpus for fragment in sealed_fragments),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "source_ot0334_receipt_digest": result["receipt_digest"], "turnover_winners": winners, "checks": checks}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, core, base130, parent, result = setup(args)
    with tempfile.TemporaryDirectory() as directory:
        frozen = preflight(Path(directory), p82, runtime, parent, result)
    if args.preflight_only:
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0335 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", frozen)
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0335 preflight failed")
    context = base.base305.actor_context(runtime, core, base130, run, repo)
    actor = run_actor(context, p82, run / "responder", parent, result)
    operational = bool(actor["accepted"] and actor["decision"]["action"] == "acquire-comparative-consequence")
    final, binding = compile_comparison(parent, result, actor, p82) if operational else (parent, None)
    checks = {
        "preflight_passed": frozen["checks"]["passed"],
        "fresh_actor_clean": actor["accepted"],
        "actor_requests_consequence_before_revision": operational,
        "actor_identifies_turnover_winners": operational and actor["decision"]["world_ids"] == turnover_winners(result["selection_history"]),
        "stake_byte_exact": final["active_world_seeking_stake"] == parent["active_world_seeking_stake"],
        "open_comparison_successor": operational and final["active_comparative_world_contact_request"] == binding and final["continuation"]["status"] == "open" and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    body = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0334_receipt_digest": result["receipt_digest"],
        "actor": actor,
        "comparison_binding": binding,
        "checks": checks,
        "operational_transition_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
    }
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    if operational:
        write_json(run / "open-subject-awaiting-comparative-consequence.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
