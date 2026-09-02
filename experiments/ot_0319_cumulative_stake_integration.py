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
from typing import Any


sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0318_counterfactual_revision_workbench.py"
BASE_SHA256 = "62eafa49806738981ca7b3176888fcdeecbb0a608e74e2d88fca941520897a21"
PARENT_DIGEST = "21e90d4729e9d6d64d5e816b7301141affd2ddbb16502e30f963c0ba83b4d3c4"
OT318_RECEIPT = "1b16230dea274b67039d45d73429dd1a3623cde718f7a321e9d8dacda6053b94"
OT315_RECEIPT = "ae2a31a865cbd4272225f9b84c20bc6f9da0fba41b822a6884418638d3693fd0"
OT314_RAW_RECEIPT = "945bd6b5298047c32ad837fa222b51ce9a695a37e3d5ee24bfb303d742194af8"
AUTHORITY = "ot-0319-cumulative-stake-integration"
SCHEMA = REPO / "spec" / "ot-0314-stake-revision.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0318 changed")
    spec = importlib.util.spec_from_file_location("ot0319_frozen_ot0318", BASE_PATH)
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


WORKBENCH = '''import json
from pathlib import Path
features=("branch_nodes","call_nodes","comparison_nodes","loop_nodes","source_bytes")
stake=json.loads(Path("stake-revision.json").read_text())
contacts=json.loads(Path("completed-selection-contacts.json").read_text())
weights=stake.get("weights")
valid=isinstance(weights,dict) and set(weights)==set(features) and all(isinstance(v,int) and -20<=v<=20 for v in weights.values()) and isinstance(stake.get("minimum_score_gap"),int) and 0<=stake["minimum_score_gap"]<=100
if not valid:
    print(json.dumps({"program_valid":False,"reason":"invalid-candidate"},sort_keys=True)); raise SystemExit(2)
rows=[]
for contact in contacts:
    ranked=[]
    for item in contact["catalog"]:
        value=sum(weights[name]*item["features"][name] for name in features)
        ranked.append({"world_id":item["world_id"],"public_package_digest":item["public_package_digest"],"score":value})
    ranked.sort(key=lambda row:(-row["score"],row["public_package_digest"]))
    gap=ranked[0]["score"]-ranked[1]["score"]
    supported=gap>=stake["minimum_score_gap"]
    selected=ranked[0]["world_id"] if supported else None
    outcome=contact["outcome"]
    available=outcome.get("outcome_authority") is True and isinstance(outcome.get("option_value"),dict) and isinstance(outcome.get("best_world_id"),str)
    rows.append({"selection_receipt_digest":contact["selection"]["receipt_digest"],"selected_world_id":selected,"best_world_id":outcome.get("best_world_id") if available else None,"score_gap":gap,"supported":supported,"available":available,"repaired":bool(available and supported and selected==outcome["best_world_id"])})
result={"program_valid":True,"case_count":len(rows),"available_count":sum(row["available"] for row in rows),"pass_count":sum(row["repaired"] for row in rows),"rows":rows}
print(json.dumps(result,sort_keys=True)); raise SystemExit(0)
'''


def setup(args):
    repo, store, _, p82, runtime, _, _, selector, core, base130 = base.setup(args)
    run = (args.evidence_root or store / "runs" / "OT-0319").resolve()
    parent = selector.load_artifact(
        p82, repo, store, "OT-0318", "open-subject-after-counterfactual-workbench-correction.json"
    )
    result318 = selector.load_artifact(
        p82, repo, store, "OT-0318", "counterfactual-revision-workbench-aggregate.json"
    )
    result315 = selector.load_artifact(
        p82, repo, store, "OT-0315", "exact-checker-materiality-reconstruction-aggregate.json"
    )
    raw314 = selector.load_artifact(
        p82, repo, store, "OT-0314", "directional-option-value-stake-revision-raw-aggregate.json"
    )
    return repo, store, run, p82, runtime, parent, result318, result315, raw314, selector, core, base130


def retained_contacts(raw314, result318):
    return copy.deepcopy(raw314["training_contacts"] + result318["training_contacts"])


def erase_earlier_outcomes(contacts, p82):
    erased = copy.deepcopy(contacts)
    for row in erased[:3]:
        old = row["outcome"]
        body = {
            "authority": AUTHORITY + "-earlier-outcome-erased",
            "selection_receipt_digest": row["selection"]["receipt_digest"],
            "episode_id": old["episode_id"],
            "catalog_digest": old["catalog_digest"],
            "outcome_authority": False,
            "option_value": None,
            "best_world_id": None,
            "selected_option_value": None,
            "directional_error": None,
        }
        row["outcome"] = {**body, "receipt_digest": p82.digest(body)}
    return erased


def projection(parent, contacts, p82, *, erased):
    body = {
        "authority": AUTHORITY + ("-earlier-outcome-erased-projection" if erased else "-full-history-projection"),
        "source_subject_digest": parent["artifact_digest"],
        "source_aggregate_receipts": [OT315_RECEIPT, OT318_RECEIPT],
        "selection_receipt_digests": [row["selection"]["receipt_digest"] for row in contacts],
        "outcome_receipt_digests": [row["outcome"]["receipt_digest"] for row in contacts],
        "earlier_outcomes_available": not erased,
        "current_outcomes_available": True,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def replay(stake, contacts):
    with tempfile.TemporaryDirectory(prefix="ot0319-workbench-") as temporary:
        root = Path(temporary)
        write_json(root / "stake-revision.json", stake)
        write_json(root / "completed-selection-contacts.json", contacts)
        (root / "evaluate_revision.py").write_text(WORKBENCH)
        completed = subprocess.run(
            [sys.executable, "evaluate_revision.py"], cwd=root, text=True,
            capture_output=True, timeout=10, check=False,
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = None
    return {"returncode": completed.returncode, "parsed": parsed, "stderr": completed.stderr}


def score(stake, episodes, p82):
    contacts = []
    for episode in episodes:
        selection_body = {
            "authority": AUTHORITY + "-private-bound-selection",
            "episode_id": episode["episode_id"],
            "catalog_digest": p82.digest(episode["catalog"]),
            "selection_precedes_outcome": True,
        }
        selection = {**selection_body, "receipt_digest": p82.digest(selection_body)}
        outcome_body = {
            "authority": AUTHORITY + "-private-option-value-world",
            "selection_receipt_digest": selection["receipt_digest"],
            "episode_id": episode["episode_id"],
            "catalog_digest": selection["catalog_digest"],
            "outcome_authority": True,
            "option_value": episode["option_value"],
            "best_world_id": episode["best_world_id"],
        }
        contacts.append({
            "catalog": episode["catalog"],
            "selection": selection,
            "outcome": {**outcome_body, "receipt_digest": p82.digest(outcome_body)},
        })
    return replay(stake, contacts)["parsed"]


def representative_stake(parent):
    candidate = copy.deepcopy(base316.stake_of(parent))
    candidate["weights"]["branch_nodes"] = -20
    candidate["weights"]["comparison_nodes"] = -20
    candidate["weights"]["source_bytes"] = 1
    candidate["rationale"] = "Integrate both authenticated option-value regimes."
    return candidate


def prior_stake(parent):
    candidate = copy.deepcopy(base316.stake_of(parent))
    candidate["weights"]["branch_nodes"] = 4
    candidate["weights"]["comparison_nodes"] = 4
    candidate["weights"]["source_bytes"] = 0
    return candidate


def global_weight_ceiling(parent, contacts):
    best = -1
    witness = None
    incumbent = base316.stake_of(parent)
    for branch in range(-20, 21):
        for comparison in range(-20, 21):
            for source_bytes in range(-20, 21):
                candidate = copy.deepcopy(incumbent)
                candidate["weights"]["branch_nodes"] = branch
                candidate["weights"]["comparison_nodes"] = comparison
                candidate["weights"]["source_bytes"] = source_bytes
                count = replay(candidate, contacts)["parsed"]["pass_count"]
                if count > best:
                    best = count
                    witness = {
                        "branch_nodes": branch,
                        "comparison_nodes": comparison,
                        "source_bytes": source_bytes,
                    }
                if best == len(contacts):
                    return {"pass_count": best, "case_count": len(contacts), "witness": witness}
    return {"pass_count": best, "case_count": len(contacts), "witness": witness}


def seed_actor(root, parent, contacts, contact_projection):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "stake-revision.json", base316.stake_of(parent))
    write_json(seed / "completed-selection-contacts.json", contacts)
    write_json(seed / "cumulative-contact-projection.json", contact_projection)
    write_json(seed / "stake-revision-contract.json", base315.contract_for(parent))
    write_json(
        seed / "subject-position.json",
        {
            "source_subject_digest": parent["artifact_digest"],
            "active_stake_binding_digest": parent["active_world_seeking_stake"]["binding_digest"],
            "cumulative_contact_projection_receipt": contact_projection["receipt_digest"],
            "workbench_digest": hashlib.sha256(WORKBENCH.encode()).hexdigest(),
        },
    )
    (seed / "check_revision.py").write_text(base315.CORRECTED_CHECKER)
    (seed / "evaluate_revision.py").write_text(WORKBENCH)
    immutable = [
        "completed-selection-contacts.json",
        "cumulative-contact-projection.json",
        "stake-revision-contract.json",
        "subject-position.json",
        "check_revision.py",
        "evaluate_revision.py",
        "mutation-envelope.json",
        "README.md",
    ]
    write_json(seed / "mutation-envelope.json", {"editable": ["stake-revision.json"], "immutable": immutable})
    (seed / "README.md").write_text(
        "Continue from the exact active stake with a projection of six completed contacts from "
        "two regimes. evaluate_revision.py scores the current stake-revision.json against every "
        "authoritative outcome present and identifies unavailable rows without scoring them. You "
        "may edit the stake and rerun the tool to test your own proposals. It contains no private "
        "world, held-out score, target weights, search result, or prescribed edit. Decide whether "
        "to revise or retain. Edit only stake-revision.json. You must successfully run both "
        "python3 evaluate_revision.py and python3 check_revision.py and inspect the exact diff "
        "before returning the report.\n"
    )
    return seed


def run_actor(context, root, parent, contacts, contact_projection, label):
    seed = seed_actor(root, parent, contacts, contact_projection)
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
        tool_result = replay(candidate, contacts)
        tool_matches = tool_result["returncode"] == 0 and tool_result["parsed"] is not None
        checker_invoked = base.named_command_succeeded(trace, "check_revision.py")
        workbench_invoked = base.named_command_succeeded(trace, "evaluate_revision.py")
        changed = candidate != base316.stake_of(parent)
    except (OSError, ValueError, KeyError, TypeError):
        candidate, immutable_ok, checker_ok, tool_result = None, False, False, None
        tool_matches = checker_invoked = workbench_invoked = changed = False
    semantic = bool(
        immutable_ok and checker_ok and tool_matches and checker_invoked and workbench_invoked
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
        "training_replay": tool_result["parsed"] if tool_result else None,
        "workspace_evaluation": {
            "immutable_ok": immutable_ok,
            "checker_ok": checker_ok,
            "workbench_matches_controller": tool_matches,
            "checker_invoked": checker_invoked,
            "workbench_invoked": workbench_invoked,
            "semantic": semantic,
        },
    }


def compile_child(parent, actor, contacts, contact_projection, evaluation, p82):
    replay_body = {
        "authority": AUTHORITY + "-training-replay",
        "stake_digest": p82.digest(actor["candidate_stake"]),
        "projection_receipt_digest": contact_projection["receipt_digest"],
        "contact_outcome_receipt_digests": [row["outcome"]["receipt_digest"] for row in contacts],
        "workbench_digest": hashlib.sha256(WORKBENCH.encode()).hexdigest(),
        "replay": actor["training_replay"],
    }
    replay_receipt = {**replay_body, "receipt_digest": p82.digest(replay_body)}
    old = parent["active_world_seeking_stake"]
    body = {
        "authority": AUTHORITY + "-stake-integration-binding",
        "source_subject_digest": parent["artifact_digest"],
        "prior_binding_digest": old["binding_digest"],
        "actor_patch_digest": actor["audit"]["patch_digest"],
        "stake": actor["candidate_stake"],
        "training_outcome_receipt_digests": [row["outcome"]["receipt_digest"] for row in contacts],
        "cumulative_contact_projection_receipt_digest": contact_projection["receipt_digest"],
        "training_replay_receipt_digest": replay_receipt["receipt_digest"],
        "heldout_score": evaluation,
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    binding = {**body, "binding_digest": p82.digest(body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["world_seeking_stake_revisions"] = [*child.get("world_seeking_stake_revisions", []), binding]
    child["active_world_seeking_stake"] = binding
    child["cumulative_contact_projections"] = [*child.get("cumulative_contact_projections", []), contact_projection]
    child["cumulative_stake_integration_receipts"] = [*child.get("cumulative_stake_integration_receipts", []), replay_receipt]
    return p82.seal(child), binding, replay_receipt


def preflight(root, p82, runtime, parent, result318, result315, raw314):
    root.mkdir(parents=True, exist_ok=True)
    contacts = retained_contacts(raw314, result318)
    erased = erase_earlier_outcomes(contacts, p82)
    current = base316.stake_of(parent)
    prior = prior_stake(parent)
    representative = representative_stake(parent)
    fixture_seed = "00" * 32
    mixed = base314.episodes(fixture_seed, p82)[1] + base316.episodes(fixture_seed, p82)[1]
    ceiling = global_weight_ceiling(parent, contacts)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_current_parent": parent["artifact_digest"] == PARENT_DIGEST
        and result318["receipt_digest"] == OT318_RECEIPT
        and result318["observer_disposition"] == "promoted"
        and result318["final_subject_digest"] == PARENT_DIGEST,
        "prior_contacts_reconstructed": result315["receipt_digest"] == OT315_RECEIPT
        and result315["source_observation_receipt"] == OT314_RAW_RECEIPT
        and result315["bounded_causal_machinery_refinement_supported"]
        and raw314["receipt_digest"] == OT314_RAW_RECEIPT,
        "six_authoritative_disjoint_contacts": len(contacts) == 6
        and len({row["outcome"]["receipt_digest"] for row in contacts}) == 6
        and all(row["outcome"]["outcome_authority"] for row in contacts),
        "current_baseline_3_of_6_and_5_of_10": replay(current, contacts)["parsed"]["pass_count"] == 3
        and score(current, mixed, p82)["pass_count"] == 5,
        "prior_baseline_3_of_6_and_5_of_10": replay(prior, contacts)["parsed"]["pass_count"] == 3
        and score(prior, mixed, p82)["pass_count"] == 5,
        "bounded_global_witness_exists": ceiling["pass_count"] == 6,
        "representative_reaches_6_and_10": replay(representative, contacts)["parsed"]["pass_count"] == 6
        and score(representative, mixed, p82)["pass_count"] == 10,
        "partial_erasure_preserves_current_rows": replay(current, erased)["parsed"]["available_count"] == 3
        and replay(current, erased)["parsed"]["pass_count"] == 3,
        "checker_accepts_representative": base315.corrected_accepts(
            base315.run_checker(base315.CORRECTED_CHECKER, representative, base315.contract_for(parent))
        ),
        "workbench_contains_no_private_target": all(
            term not in WORKBENCH
            for term in (
                "heldout",
                "private",
                '\"branch_nodes\": -20',
                '\"comparison_nodes\": -20',
                '\"source_bytes\": 1',
                "target_weight",
                "search_result",
            )
        ),
        "exact_open_conformant": parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "fixture_seed_digest": p82.digest(fixture_seed),
        "global_weight_ceiling": ceiling,
        "current_training_replay": replay(current, contacts)["parsed"],
        "prior_training_replay": replay(prior, contacts)["parsed"],
        "representative_training_replay": replay(representative, contacts)["parsed"],
        "erased_training_replay": replay(current, erased)["parsed"],
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
        selector, core, base130,
    ) = setup(args)
    retained = run / "preflight" / "fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(
        run / "preflight", p82, runtime, parent, result318, result315, raw314
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0319 unavailable")

    contacts = retained_contacts(raw314, result318)
    erased_contacts = erase_earlier_outcomes(contacts, p82)
    full_projection = projection(parent, contacts, p82, erased=False)
    erased_projection = projection(parent, erased_contacts, p82, erased=True)
    current = base316.stake_of(parent)
    prior = prior_stake(parent)

    seed = secrets.token_hex(32)
    write_json(run / "private-mixed-world-seed.json", {"seed": seed, "seed_digest": p82.digest(seed)})
    mixed = base314.episodes(seed, p82)[1] + base316.episodes(seed, p82)[1]
    current_score = score(current, mixed, p82)
    prior_score = score(prior, mixed, p82)
    if current_score["pass_count"] != 5 or prior_score["pass_count"] != 5:
        raise RuntimeError("private trajectory does not preserve complementary baselines")

    context = b.base274.context_for(core, base130, runtime, run / "actors", repo)
    actor = run_actor(
        context, run / "candidate", parent, contacts, full_projection,
        "cumulative-stake-integrator",
    )
    candidate_score = score(actor["candidate_stake"], mixed, p82) if actor["accepted"] else None
    operational = bool(
        actor["accepted"] and actor["changed"]
        and actor["training_replay"]["available_count"] == 6
        and actor["training_replay"]["pass_count"] == 6
        and candidate_score is not None and candidate_score["pass_count"] == 10
        and current_score["pass_count"] == 5 and prior_score["pass_count"] == 5
    )
    child, binding, replay_receipt = (
        compile_child(parent, actor, contacts, full_projection, candidate_score, p82)
        if operational else (parent, None, None)
    )
    write_json(run / "candidate-operational-subject.json", child)

    erased_actor = run_actor(
        context, run / "erased", parent, erased_contacts, erased_projection,
        "cumulative-stake-integrator-earlier-erased",
    )
    erased_score = score(erased_actor["candidate_stake"], mixed, p82) if erased_actor["accepted"] else None
    causal = bool(
        operational and erased_actor["accepted"]
        and erased_actor["training_replay"]["available_count"] == 3
        and not (
            erased_actor["changed"] and erased_score is not None
            and erased_score["pass_count"] == 10
        )
    )
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "private_seed_postfreeze": True,
        "candidate_actor_clean": actor["accepted"],
        "candidate_integrates_training": actor["accepted"] and actor["training_replay"]["pass_count"] == 6,
        "candidate_beats_both_baselines": operational,
        "operational_child_sealed_before_control": (run / "candidate-operational-subject.json").exists(),
        "erased_actor_clean": erased_actor["accepted"],
        "earlier_outcome_erasure_removes_cumulative_advantage": causal,
        "child_retains_cumulative_path": not operational or (
            binding["training_replay_receipt_digest"] == replay_receipt["receipt_digest"]
            and child["cumulative_stake_integration_receipts"][-1] == replay_receipt
        ),
        "child_open_conformant": child["continuation"]["status"] == "open" and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_aggregate_receipts": [OT315_RECEIPT, OT318_RECEIPT],
        "private_world_seed_digest": p82.digest(seed),
        "cumulative_projection": full_projection,
        "candidate_actor": actor,
        "candidate_score": candidate_score,
        "current_score": current_score,
        "prior_score": prior_score,
        "stake_integration_binding": binding,
        "training_replay_receipt": replay_receipt,
        "erased_projection": erased_projection,
        "erased_actor": erased_actor,
        "erased_score": erased_score,
        "checks": checks,
        "operational_transition_passed": operational,
        "cumulative_consequence_integration_supported": causal,
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
