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
BASE_PATH = ROOT / "ot_0317_provenance_bound_selection_error.py"
BASE_SHA256 = "a3a7729280513d8247ca164c75dc7530ebe35ab99ce4662428d730cad593b692"
PARENT_DIGEST = "0a48ab16cb92833cdf9a9e02ddc6207d236b8f79d577d12d38ac348adacd9e49"
OT317_RECEIPT = "eb5d0d29d488f5b70561ef15959983f21d1d6acafac09a24b7f700a401ff6b66"
AUTHORITY = "ot-0318-counterfactual-revision-workbench"
SCHEMA = REPO / "spec" / "ot-0314-stake-revision.schema.json"

WORKBENCH = '''import json
from pathlib import Path
features=("branch_nodes","call_nodes","comparison_nodes","loop_nodes","source_bytes")
stake=json.loads(Path("stake-revision.json").read_text())
contacts=json.loads(Path("completed-selection-contacts.json").read_text())
weights=stake.get("weights")
valid=isinstance(weights,dict) and set(weights)==set(features) and all(isinstance(v,int) and -20<=v<=20 for v in weights.values()) and isinstance(stake.get("minimum_score_gap"),int) and 0<=stake["minimum_score_gap"]<=100
if not valid:
    print(json.dumps({"available":False,"reason":"invalid-candidate"},sort_keys=True)); raise SystemExit(2)
available=all(row.get("outcome",{}).get("outcome_authority") is True and isinstance(row["outcome"].get("option_value"),dict) and isinstance(row["outcome"].get("best_world_id"),str) for row in contacts)
if not available:
    print(json.dumps({"available":False,"reason":"authoritative-outcomes-unavailable"},sort_keys=True)); raise SystemExit(0)
rows=[]
for contact in contacts:
    ranked=[]
    for item in contact["catalog"]:
        score=sum(weights[name]*item["features"][name] for name in features)
        ranked.append({"world_id":item["world_id"],"public_package_digest":item["public_package_digest"],"score":score})
    ranked.sort(key=lambda row:(-row["score"],row["public_package_digest"]))
    gap=ranked[0]["score"]-ranked[1]["score"]
    supported=gap>=stake["minimum_score_gap"]
    selected=ranked[0]["world_id"] if supported else None
    rows.append({"selection_receipt_digest":contact["selection"]["receipt_digest"],"selected_world_id":selected,"best_world_id":contact["outcome"]["best_world_id"],"score_gap":gap,"supported":supported,"repaired":supported and selected==contact["outcome"]["best_world_id"]})
result={"available":True,"case_count":len(rows),"pass_count":sum(row["repaired"] for row in rows),"rows":rows}
print(json.dumps(result,sort_keys=True)); raise SystemExit(0)
'''


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0317 changed")
    spec = importlib.util.spec_from_file_location("ot0318_frozen_ot0317", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
b = base.b
base314 = base.base314
base315 = base.base315
base316 = base.base
base236 = base.base236
write_json = base.write_json


def setup(args):
    repo, store, run, p82, runtime, parent, _, selector, core, base130 = base.setup(args)
    result317 = selector.load_artifact(
        p82, repo, store, "OT-0317", "provenance-bound-selection-error-aggregate.json"
    )
    return repo, store, run, p82, runtime, parent, result317, selector, core, base130


def sealed(body: dict[str, Any], p82) -> dict[str, Any]:
    return {**body, "receipt_digest": p82.digest(body)}


def training_receipts(stake, training, p82, *, erased):
    rows = []
    for episode in training:
        choice = base316.select(stake, episode)
        selection_body = {
            "authority": AUTHORITY + "-bound-selection",
            "episode_id": episode["episode_id"],
            "catalog_digest": p82.digest(episode["catalog"]),
            "selected_world_id": choice["selected_world_id"],
            "supported": choice["supported"],
            "selection_precedes_outcome": True,
        }
        selection = sealed(selection_body, p82)
        outcome_body = {
            "authority": AUTHORITY + ("-outcome-erased" if erased else "-option-value-world"),
            "selection_receipt_digest": selection["receipt_digest"],
            "episode_id": episode["episode_id"],
            "catalog_digest": selection["catalog_digest"],
            "outcome_authority": not erased,
            "option_value": None if erased else episode["option_value"],
            "best_world_id": None if erased else episode["best_world_id"],
            "selected_option_value": None
            if erased
            else episode["option_value"].get(choice["selected_world_id"]),
            "directional_error": None
            if erased
            else choice["selected_world_id"] != episode["best_world_id"],
        }
        rows.append(
            {
                "catalog": episode["catalog"],
                "selection": selection,
                "outcome": sealed(outcome_body, p82),
            }
        )
    return rows


def evidence_provenance(parent, p82):
    active = parent["active_world_seeking_stake"]
    body = {
        "authority": AUTHORITY + "-stake-evidence-provenance",
        "active_stake_binding_digest": active["binding_digest"],
        "rationale_role": "historical-support-not-current-outcome",
        "historical_training_outcome_receipt_digests": active[
            "training_outcome_receipt_digests"
        ],
        "current_contacts_require_separate_receipt_identity": True,
    }
    return sealed(body, p82)


def active_error(parent, contacts, p82, *, erased):
    violations = []
    if not erased:
        for row in contacts:
            selection, outcome = row["selection"], row["outcome"]
            violations.append(
                {
                    "selection_receipt_digest": selection["receipt_digest"],
                    "outcome_receipt_digest": outcome["receipt_digest"],
                    "selected_world_id": selection["selected_world_id"],
                    "best_world_id": outcome["best_world_id"],
                    "selected_option_value": outcome["selected_option_value"],
                    "best_option_value": max(outcome["option_value"].values()),
                }
            )
    body = {
        "authority": AUTHORITY + "-active-selection-error",
        "source_stake_binding_digest": parent["active_world_seeking_stake"]["binding_digest"],
        "selection_receipt_digests": [row["selection"]["receipt_digest"] for row in contacts],
        "status": "active-current-selection-error" if not erased else "unavailable-erased-outcomes",
        "current_selection_fitness_failed": bool(not erased and len(violations) == len(contacts)),
        "reassessment_open": bool(not erased and violations),
        "violations": violations,
        "prescribed_edit": None,
    }
    return sealed(body, p82)


def valid_projection(parent, contacts, provenance, error, p82, *, erased):
    expected_provenance = evidence_provenance(parent, p82)
    expected_error = active_error(parent, contacts, p82, erased=erased)
    historical = set(provenance["historical_training_outcome_receipt_digests"])
    current = {
        row["outcome"]["receipt_digest"]
        for row in contacts
        if row["outcome"]["outcome_authority"]
    }
    return bool(
        provenance == expected_provenance
        and error == expected_error
        and historical.isdisjoint(current)
        and ((not erased and error["current_selection_fitness_failed"] and len(error["violations"]) == 3)
             or (erased and not error["current_selection_fitness_failed"] and not error["violations"]))
    )


def training_replay(stake, contacts):
    available = all(
        row["outcome"].get("outcome_authority") is True
        and isinstance(row["outcome"].get("option_value"), dict)
        and isinstance(row["outcome"].get("best_world_id"), str)
        for row in contacts
    )
    if not available:
        return {"available": False, "reason": "authoritative-outcomes-unavailable"}
    rows = []
    for contact in contacts:
        choice = base316.select(stake, {"catalog": contact["catalog"]})
        selected = choice["selected_world_id"]
        best = contact["outcome"]["best_world_id"]
        rows.append(
            {
                "selection_receipt_digest": contact["selection"]["receipt_digest"],
                "selected_world_id": selected,
                "best_world_id": best,
                "score_gap": choice["score_gap"],
                "supported": choice["supported"],
                "repaired": choice["supported"] and selected == best,
            }
        )
    return {
        "available": True,
        "case_count": len(rows),
        "pass_count": sum(row["repaired"] for row in rows),
        "rows": rows,
    }


def run_workbench(stake, contacts):
    with tempfile.TemporaryDirectory(prefix="ot0318-workbench-") as temporary:
        root = Path(temporary)
        write_json(root / "stake-revision.json", stake)
        write_json(root / "completed-selection-contacts.json", contacts)
        (root / "evaluate_revision.py").write_text(WORKBENCH)
        completed = subprocess.run(
            [sys.executable, "evaluate_revision.py"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = None
    return {"returncode": completed.returncode, "parsed": parsed, "stderr": completed.stderr}


def named_command_succeeded(trace: str, name: str) -> bool:
    for line in trace.splitlines():
        try:
            item = json.loads(line).get("item", {})
        except json.JSONDecodeError:
            continue
        if (
            item.get("type") == "command_execution"
            and item.get("status") == "completed"
            and item.get("exit_code") == 0
            and name in item.get("command", "")
        ):
            return True
    return False


def seed_actor(root, parent, contacts, provenance, error):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "stake-revision.json", base316.stake_of(parent))
    write_json(seed / "completed-selection-contacts.json", contacts)
    write_json(seed / "stake-evidence-provenance.json", provenance)
    write_json(seed / "active-selection-error.json", error)
    write_json(seed / "stake-revision-contract.json", base315.contract_for(parent))
    write_json(
        seed / "subject-position.json",
        {
            "source_subject_digest": parent["artifact_digest"],
            "active_stake_binding_digest": parent["active_world_seeking_stake"]["binding_digest"],
            "counterfactual_workbench_digest": hashlib.sha256(WORKBENCH.encode()).hexdigest(),
        },
    )
    (seed / "check_revision.py").write_text(base315.CORRECTED_CHECKER)
    (seed / "evaluate_revision.py").write_text(WORKBENCH)
    immutable = [
        "completed-selection-contacts.json",
        "stake-evidence-provenance.json",
        "active-selection-error.json",
        "stake-revision-contract.json",
        "subject-position.json",
        "check_revision.py",
        "evaluate_revision.py",
        "mutation-envelope.json",
        "README.md",
    ]
    write_json(seed / "mutation-envelope.json", {"editable": ["stake-revision.json"], "immutable": immutable})
    (seed / "README.md").write_text(
        "Continue from the exact active stake and provenance-bound current consequence. "
        "evaluate_revision.py evaluates the current stake-revision.json only against the "
        "revealed contacts; you may edit the stake and rerun it to test your own proposals. "
        "It contains no held-out worlds or prescribed edit and reports unavailable when outcomes "
        "lack authority. Decide whether to revise or retain. Future catalogs, private identities, "
        "scores, prior private worlds, evaluator, and sibling are unavailable. Edit only "
        "stake-revision.json. You must successfully run both python3 evaluate_revision.py and "
        "python3 check_revision.py and inspect the exact diff before returning the report.\n"
    )
    return seed


def run_actor(context, root, parent, contacts, provenance, error, label):
    seed = seed_actor(root, parent, contacts, provenance, error)
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
        tool_result = run_workbench(candidate, contacts)
        tool_matches = tool_result["returncode"] == 0 and tool_result["parsed"] == training_replay(candidate, contacts)
        checker_invoked = named_command_succeeded(trace, "check_revision.py")
        workbench_invoked = named_command_succeeded(trace, "evaluate_revision.py")
        changed = candidate != base316.stake_of(parent)
    except (OSError, ValueError, KeyError, TypeError):
        candidate, immutable_ok, checker_ok, tool_result = None, False, False, None
        tool_matches, checker_invoked, workbench_invoked, changed = False, False, False, False
    semantic = bool(
        immutable_ok
        and checker_ok
        and tool_matches
        and checker_invoked
        and workbench_invoked
        and base314.valid_candidate(parent, candidate)
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


def compile_child(parent, actor, contacts, provenance, error, evaluation, p82):
    old = parent["active_world_seeking_stake"]
    replay = training_replay(actor["candidate_stake"], contacts)
    replay_body = {
        "authority": AUTHORITY + "-candidate-training-replay",
        "stake_digest": p82.digest(actor["candidate_stake"]),
        "contact_outcome_receipt_digests": [row["outcome"]["receipt_digest"] for row in contacts],
        "workbench_digest": hashlib.sha256(WORKBENCH.encode()).hexdigest(),
        "replay": replay,
    }
    replay_receipt = {**replay_body, "receipt_digest": p82.digest(replay_body)}
    body = {
        "authority": AUTHORITY + "-stake-revision-binding",
        "source_subject_digest": parent["artifact_digest"],
        "prior_binding_digest": old["binding_digest"],
        "actor_patch_digest": actor["audit"]["patch_digest"],
        "stake": actor["candidate_stake"],
        "training_outcome_receipt_digests": [row["outcome"]["receipt_digest"] for row in contacts],
        "stake_evidence_provenance_receipt_digest": provenance["receipt_digest"],
        "active_selection_error_receipt_digest": error["receipt_digest"],
        "candidate_training_replay_receipt_digest": replay_receipt["receipt_digest"],
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
    child["stake_evidence_provenance_receipts"] = [*child.get("stake_evidence_provenance_receipts", []), provenance]
    child["selection_error_receipts"] = [*child.get("selection_error_receipts", []), error]
    child["machinery_counterfactual_receipts"] = [*child.get("machinery_counterfactual_receipts", []), replay_receipt]
    return p82.seal(child), binding, replay_receipt


def preflight(root, p82, runtime, parent, result317):
    root.mkdir(parents=True, exist_ok=True)
    training, heldout = base316.episodes("00" * 32, p82)
    incumbent = base316.stake_of(parent)
    contacts = training_receipts(incumbent, training, p82, erased=False)
    erased_contacts = training_receipts(incumbent, training, p82, erased=True)
    representative = copy.deepcopy(incumbent)
    representative["weights"]["source_bytes"] = -1
    current_tool = run_workbench(incumbent, contacts)
    representative_tool = run_workbench(representative, contacts)
    erased_tool = run_workbench(incumbent, erased_contacts)
    provenance = evidence_provenance(parent, p82)
    error = active_error(parent, contacts, p82, erased=False)
    fixture_trace = "\n".join(
        json.dumps({"item": {"type": "command_execution", "status": "completed", "exit_code": 0, "command": f"python3 {name}"}})
        for name in ("evaluate_revision.py", "check_revision.py")
    )
    fixture_actor = {
        "candidate_stake": representative,
        "audit": {"patch_digest": "fixture-patch"},
    }
    child, binding, replay_receipt = compile_child(
        parent, fixture_actor, contacts, provenance, error,
        base316.score(representative, heldout), p82
    )
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_rejected_parent": parent["artifact_digest"] == PARENT_DIGEST
        and result317["receipt_digest"] == OT317_RECEIPT
        and result317["observer_disposition"] == "rejected"
        and result317["final_subject_digest"] == PARENT_DIGEST,
        "active_projection_valid": valid_projection(parent, contacts, provenance, error, p82, erased=False),
        "current_tool_matches_0_of_3": current_tool["returncode"] == 0
        and current_tool["parsed"] == training_replay(incumbent, contacts)
        and current_tool["parsed"]["pass_count"] == 0,
        "representative_tool_matches_3_of_3": representative_tool["returncode"] == 0
        and representative_tool["parsed"] == training_replay(representative, contacts)
        and representative_tool["parsed"]["pass_count"] == 3,
        "erased_tool_unavailable": erased_tool["returncode"] == 0
        and erased_tool["parsed"] == training_replay(incumbent, erased_contacts)
        and not erased_tool["parsed"]["available"],
        "tool_contains_no_private_or_target_material": all(
            term not in WORKBENCH for term in ("heldout", "private", "source_bytes=-1", "target_weight")
        ),
        "trace_gate_requires_both": named_command_succeeded(fixture_trace, "evaluate_revision.py")
        and named_command_succeeded(fixture_trace, "check_revision.py")
        and not named_command_succeeded(fixture_trace, "missing.py"),
        "representative_child_retains_workbench_path": binding["candidate_training_replay_receipt_digest"]
        == replay_receipt["receipt_digest"]
        and child["machinery_counterfactual_receipts"][-1] == replay_receipt
        and child["selection_error_receipts"][-1] == error
        and runtime.identity_conforms(child),
        "incumbent_0_of_5": base316.score(incumbent, heldout)["pass_count"] == 0,
        "representative_5_of_5": base316.score(representative, heldout)["pass_count"] == 5,
        "exact_open_conformant": parent["continuation"]["status"] == "open"
        and runtime.identity_conforms(parent),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "fixture_seed_digest": p82.digest("00" * 32),
        "workbench_digest": hashlib.sha256(WORKBENCH.encode()).hexdigest(),
        "current_training_replay": current_tool["parsed"],
        "representative_training_replay": representative_tool["parsed"],
        "erased_training_replay": erased_tool["parsed"],
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
    repo, store, run, p82, runtime, parent, result317, selector, core, base130 = setup(args)
    retained = run / "preflight" / "fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(
        run / "preflight", p82, runtime, parent, result317
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0318 unavailable")

    seed = secrets.token_hex(32)
    write_json(run / "private-world-seed.json", {"seed": seed, "seed_digest": p82.digest(seed)})
    training, heldout = base316.episodes(seed, p82)
    incumbent = base316.stake_of(parent)
    contacts = training_receipts(incumbent, training, p82, erased=False)
    erased_contacts = training_receipts(incumbent, training, p82, erased=True)
    provenance = evidence_provenance(parent, p82)
    error = active_error(parent, contacts, p82, erased=False)
    erased_error = active_error(parent, erased_contacts, p82, erased=True)
    if not valid_projection(parent, contacts, provenance, error, p82, erased=False):
        raise RuntimeError("active projection invalid")

    context = b.base274.context_for(core, base130, runtime, run / "actors", repo)
    actor = run_actor(
        context, run / "candidate", parent, contacts, provenance, error,
        "counterfactual-workbench-stake-reviser"
    )
    candidate_score = base316.score(actor["candidate_stake"], heldout) if actor["accepted"] else None
    incumbent_score = base316.score(incumbent, heldout)
    training_score = training_replay(actor["candidate_stake"], contacts) if actor["accepted"] else None
    operational = bool(
        actor["accepted"] and actor["changed"] and training_score["pass_count"] == 3
        and candidate_score["pass_count"] == 5 and incumbent_score["pass_count"] == 0
    )
    child, binding, replay_receipt = (
        compile_child(parent, actor, contacts, provenance, error, candidate_score, p82)
        if operational else (parent, None, None)
    )
    write_json(run / "candidate-operational-subject.json", child)

    erased_actor = run_actor(
        context, run / "erased", parent, erased_contacts, provenance, erased_error,
        "counterfactual-workbench-stake-reviser-erased"
    )
    erased_score = base316.score(erased_actor["candidate_stake"], heldout) if erased_actor["accepted"] else None
    causal = bool(
        operational
        and erased_actor["accepted"]
        and erased_actor["training_replay"] == {"available": False, "reason": "authoritative-outcomes-unavailable"}
        and not (erased_actor["changed"] and erased_score["pass_count"] == 5)
    )

    prior_seed = selector.load_artifact(
        p82, repo, store, "OT-0314", "private-option-value-world-seed.json"
    )
    _, prior_heldout = base314.episodes(prior_seed["seed"], p82)
    prior_regime = {
        "candidate_score": base314.score(actor["candidate_stake"], prior_heldout)
        if actor["accepted"] else None,
        "exact_parent_score": base314.score(incumbent, prior_heldout),
        "promotion_authority": False,
    }
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "private_seed_postfreeze": True,
        "candidate_actor_clean": actor["accepted"],
        "candidate_training_repair": training_score is not None and training_score["pass_count"] == 3,
        "candidate_beats_incumbent": operational,
        "operational_child_sealed_before_control": (run / "candidate-operational-subject.json").exists(),
        "erased_actor_clean": erased_actor["accepted"],
        "erased_workbench_unavailable": erased_actor["training_replay"]
        == {"available": False, "reason": "authoritative-outcomes-unavailable"},
        "outcome_erasure_removes_advantage": causal,
        "child_retains_counterfactual_path": not operational
        or (
            binding["candidate_training_replay_receipt_digest"] == replay_receipt["receipt_digest"]
            and child["machinery_counterfactual_receipts"][-1] == replay_receipt
        ),
        "child_open_conformant": child["continuation"]["status"] == "open"
        and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_rejection_receipt": OT317_RECEIPT,
        "private_world_seed_digest": p82.digest(seed),
        "workbench_digest": hashlib.sha256(WORKBENCH.encode()).hexdigest(),
        "stake_evidence_provenance": provenance,
        "active_selection_error": error,
        "training_contacts": contacts,
        "candidate_actor": actor,
        "candidate_training_replay": training_score,
        "candidate_score": candidate_score,
        "incumbent_score": incumbent_score,
        "stake_revision_binding": binding,
        "counterfactual_replay_receipt": replay_receipt,
        "erased_selection_error": erased_error,
        "erased_actor": erased_actor,
        "erased_score": erased_score,
        "prior_regime_diagnostic": prior_regime,
        "checks": checks,
        "operational_transition_passed": operational,
        "counterfactual_workbench_correction_supported": causal,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
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
