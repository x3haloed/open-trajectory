from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path


sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0320_reachable_revision_search.py"
BASE_SHA256 = "040a06bcd82b8343b7e4743caf9d4872b062ce0bc2f8f2ac3be981bc9389a332"
PARENT_DIGEST = "21e90d4729e9d6d64d5e816b7301141affd2ddbb16502e30f963c0ba83b4d3c4"
OT320_RAW_RECEIPT = "53fe475f045138fa1fb707a35d951891f1241f4f60e9d22f78c922a9e00d1886"
AUTHORITY = "ot-0321-exact-weight-bound-reconstruction"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0320 changed")
    spec = importlib.util.spec_from_file_location("ot0321_frozen_ot0320", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
base314 = base.base314
base315 = base.base315
base316 = base.base316
write_json = base.write_json


def setup(args):
    (
        repo, store, _, p82, runtime, parent, result318, result315, raw314,
        result319, selector, core, base130,
    ) = base.setup(args)
    run = (args.evidence_root or store / "runs" / "OT-0321").resolve()
    raw320 = selector.load_artifact(
        p82, repo, store, "OT-0320", "reachable-revision-search-raw-aggregate.json"
    )
    candidate = selector.load_artifact(
        p82, repo, store, "OT-0320", "full-history-search-actor-stake-revision.json"
    )
    erased_stake = selector.load_artifact(
        p82, repo, store, "OT-0320", "earlier-erased-search-actor-stake-revision.json"
    )
    private_seed = selector.load_artifact(
        p82, repo, store, "OT-0320", "private-search-world-seed.json"
    )
    return repo, store, run, p82, runtime, parent, raw314, result318, raw320, candidate, erased_stake, private_seed, selector


def trace_text(p82, repo, store, logical):
    _, path = p82.materialize(repo, store, "OT-0320", logical)
    return path.read_text()


def corrected_accepts(parent, candidate):
    try:
        contract = base315.contract_for(parent)
        return bool(
            isinstance(candidate, dict)
            and set(candidate) == set(contract["required_keys"])
            and set(candidate.get("weights", {})) == set(contract["weight_keys"])
            and all(
                isinstance(value, int)
                and contract["weight_integer_range"][0] <= value <= contract["weight_integer_range"][1]
                for value in candidate["weights"].values()
            )
            and isinstance(candidate.get("minimum_score_gap"), int)
            and contract["minimum_score_gap_range"][0]
            <= candidate["minimum_score_gap"]
            <= contract["minimum_score_gap_range"][1]
            and isinstance(candidate.get("rationale"), str)
            and 1 <= len(candidate["rationale"]) <= 2000
            and all(candidate.get(key) == value for key, value in contract["immutable_values"].items())
        )
    except (KeyError, TypeError):
        return False


def corrected_predicate_digest():
    return hashlib.sha256(inspect.getsource(corrected_accepts).encode()).hexdigest()


def actor_effects_clean(actor):
    audit = actor["audit"]
    return bool(
        audit["changed_paths"] == ["stake-revision.json"]
        and audit["expected_changes"] == ["stake-revision.json"]
        and audit["reported_paths"] == ["stake-revision.json"]
        and audit["truthful"]
        and audit["exact_changes"]
        and audit["denial_classification_v2"]["accepted"]
        and audit["trace_regime"]["accepted"]
        and audit["trace_regime"]["turn_completed"]
    )


def trace_has_tools(trace):
    return all(
        base.named_command_succeeded(trace, name)
        for name in ("search_revisions.py", "evaluate_revision.py", "check_revision.py")
    )


def preflight(root, p82, runtime, parent, raw314, result318, raw320, candidate):
    root.mkdir(parents=True, exist_ok=True)
    lower = copy.deepcopy(base316.stake_of(parent))
    upper = copy.deepcopy(lower)
    lower["weights"]["branch_nodes"] = -20
    upper["weights"]["branch_nodes"] = 20
    too_low = copy.deepcopy(lower)
    too_low["weights"]["branch_nodes"] = -21
    too_high = copy.deepcopy(upper)
    too_high["weights"]["branch_nodes"] = 21
    missing = copy.deepcopy(candidate)
    missing.pop("rationale")
    added = copy.deepcopy(candidate)
    added["extra"] = True
    noninteger = copy.deepcopy(candidate)
    noninteger["weights"]["source_bytes"] = 1.0
    long_rationale = copy.deepcopy(candidate)
    long_rationale["rationale"] = "x" * 2001
    immutable = copy.deepcopy(candidate)
    immutable["question"] = "changed"
    fixture_actor = copy.deepcopy(raw320["candidate_actor"])
    fixture_actor["accepted"] = True
    fixture_actor["audit"]["conformant"] = True
    fixture_actor["workspace_evaluation"]["semantic"] = True
    contacts = base.base.retained_contacts(raw314, result318)
    fixture_projection = base.base.projection(parent, contacts, p82, erased=False)
    fixture_error = base.search_error(
        parent, {"receipt_digest": raw320["source_rejection_receipt"]}, p82, erased=False
    )
    fixture_child, _, _, _ = base.compile_child(
        parent,
        fixture_actor,
        contacts,
        fixture_projection,
        fixture_error,
        {"pass_count": 10, "case_count": 10, "fixture": True},
        p82,
    )
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_raw_observation": raw320["receipt_digest"] == OT320_RAW_RECEIPT
        and raw320["source_subject_digest"] == PARENT_DIGEST
        and raw320["final_subject_digest"] == PARENT_DIGEST,
        "corrected_accepts_parent": corrected_accepts(parent, base316.stake_of(parent)),
        "corrected_accepts_retained_candidate": corrected_accepts(parent, candidate),
        "corrected_accepts_boundaries": corrected_accepts(parent, lower) and corrected_accepts(parent, upper),
        "corrected_rejects_out_of_bounds": not corrected_accepts(parent, too_low) and not corrected_accepts(parent, too_high),
        "corrected_rejects_shape_and_type": all(
            not corrected_accepts(parent, value)
            for value in (missing, added, noninteger, long_rationale, immutable)
        ),
        "legacy_alone_rejects_candidate": not base314.base305.valid_stake(candidate)
        and not base314.valid_candidate(parent, candidate),
        "public_checker_accepts_candidate": base315.corrected_accepts(
            base315.run_checker(base315.CORRECTED_CHECKER, candidate, base315.contract_for(parent))
        ),
        "malformed_output_rejected": not base314.output_valid(
            {"action": "revise-world-seeking-stake", "files_changed": [], "note": "wrong"}, True
        ),
        "fixture_child_open_conformant": fixture_child["continuation"]["status"] == "open"
        and runtime.identity_conforms(fixture_child),
        "exact_open_conformant": parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "source_observation_receipt": raw320["receipt_digest"],
        "corrected_predicate_digest": corrected_predicate_digest(),
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def reconstruct(run, p82, runtime, parent, raw314, result318, raw320, candidate, erased_stake, private_seed, candidate_trace, erased_trace):
    contacts = base.base.retained_contacts(raw314, result318)
    full_projection = base.base.projection(parent, contacts, p82, erased=False)
    error = base.search_error(parent, {"receipt_digest": raw320["source_rejection_receipt"]}, p82, erased=False)
    training = base.base.replay(candidate, contacts)["parsed"]
    searched = base.search(base316.stake_of(parent), contacts)["parsed"]
    mixed = base314.episodes(private_seed["seed"], p82)[1] + base316.episodes(private_seed["seed"], p82)[1]
    candidate_score = base.base.score(candidate, mixed, p82)
    current_score = base.base.score(base316.stake_of(parent), mixed, p82)
    prior_score = base.base.score(base.base.prior_stake(parent), mixed, p82)
    raw_actor = raw320["candidate_actor"]
    actor = copy.deepcopy(raw_actor)
    actor["accepted"] = True
    actor["workspace_evaluation"]["semantic"] = True
    actor["audit"]["conformant"] = True
    child, binding, replay_receipt, search_receipt = base.compile_child(
        parent, actor, contacts, full_projection, error, candidate_score, p82
    )
    erased = raw320["erased_actor"]
    checks = {
        "preflight_passed": True,
        "exact_candidate_bytes": candidate == raw_actor["candidate_stake"],
        "corrected_candidate_valid": corrected_accepts(parent, candidate)
        and base314.output_valid(raw_actor["output"], True),
        "candidate_tools_executed": trace_has_tools(candidate_trace),
        "candidate_effects_clean": actor_effects_clean(raw_actor),
        "search_reconstructed_exact": searched == raw_actor["search_result"]
        and candidate["weights"] in [row["weights"] for row in searched["candidates"]],
        "training_reconstructed_6_of_6": training == raw_actor["training_replay"]
        and training["pass_count"] == 6,
        "private_reconstructed_10_of_10": candidate_score["pass_count"] == 10,
        "baselines_reconstructed_5_of_10": current_score == raw320["current_score"]
        and prior_score == raw320["prior_score"]
        and current_score["pass_count"] == prior_score["pass_count"] == 5,
        "erased_control_exact": erased_stake == erased["candidate_stake"]
        and erased["accepted"] and not erased["changed"]
        and trace_has_tools(erased_trace)
        and erased["search_result"]["search_complete"]
        and not erased["search_result"]["improvement_found"],
        "child_retains_search_and_replay": binding["proposal_search_receipt_digest"] == search_receipt["receipt_digest"]
        and child["proposal_search_receipts"][-1] == search_receipt
        and child["cumulative_stake_integration_receipts"][-1] == replay_receipt,
        "child_open_conformant": child["continuation"]["status"] == "open" and runtime.identity_conforms(child),
        "historical_workflow_still_invalid": not raw_actor["accepted"]
        and not raw_actor["workspace_evaluation"]["semantic"],
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_observation_receipt": raw320["receipt_digest"],
        "corrected_predicate_digest": corrected_predicate_digest(),
        "candidate_stake_digest": p82.digest(candidate),
        "candidate_training_replay": training,
        "candidate_private_score": candidate_score,
        "current_private_score": current_score,
        "prior_private_score": prior_score,
        "proposal_search_error": error,
        "proposal_search_receipt": search_receipt,
        "training_replay_receipt": replay_receipt,
        "stake_integration_binding": binding,
        "checks": checks,
        "hidden_bound_defect_sole_material_obstruction": checks["passed"],
        "historical_ot0320_admission_workflow_conformant": False,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": child["continuation"]["status"],
        "final_subject_digest": child["artifact_digest"] if checks["passed"] else parent["artifact_digest"],
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    final = child if checks["passed"] else parent
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    (
        repo, store, run, p82, runtime, parent, raw314, result318, raw320,
        candidate, erased_stake, private_seed, selector,
    ) = setup(args)
    retained = run / "preflight" / "fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(
        run / "preflight", p82, runtime, parent, raw314, result318, raw320, candidate
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0321 unavailable")
    candidate_trace = trace_text(p82, repo, store, "full-history-search-actor-trace.json")
    erased_trace = trace_text(p82, repo, store, "earlier-erased-search-actor-trace.json")
    result = reconstruct(
        run, p82, runtime, parent, raw314, result318, raw320, candidate,
        erased_stake, private_seed, candidate_trace, erased_trace,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["checks"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
