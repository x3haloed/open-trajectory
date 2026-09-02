from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0338_exact_comparison_response_reconstruction.py"
BASE_SHA256 = "d10dd7d137619f2a5aa02548faf98c180e6efdd94465eee5fd0feb2a1cb9e47c"
CONTACT_PATH = ROOT / "ot_0334_scoped_provider_collision_recovery.py"
CONTACT_SHA256 = "7f7a5f69e5116cdf73124e1e8761c97fc5fb501535e74cced1cb6075068487f0"
PARENT_DIGEST = "37ebb69afe6038a46cf7e94594e12c47723bc5bc05e24d0afee18cea4230fd13"
OT338_RECEIPT = "004b2581daafa2bec1d548b0259d77fa52ead61e582f335f4557da8b8e620e3c"
AUTHORITY = "ot-0339-subject-authored-world-consequence-policy"
SCHEMA = REPO / "spec/ot-0339-world-consequence-policy.schema.json"
METRICS = ["viable_contact_count", "mean_match_basis_points", "minimum_match_basis_points"]


def import_frozen(path, expected, name):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"frozen source changed: {path.name}: {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0339_frozen_ot0338")
contact = import_frozen(CONTACT_PATH, CONTACT_SHA256, "ot0339_frozen_ot0334")
write_json = base.write_json


def setup(args):
    values = contact.setup(args)
    repo, store, _, p82, runtime = values[:5]
    result330, result280, core, base130 = values[7:11]
    run = (args.evidence_root or store / "runs/OT-0339").resolve()
    selector = contact.base.base.base.base.base.b.authority_base.guide_base.load_base().selector_base
    load = lambda experiment, name: selector.load_artifact(p82, repo, store, experiment, name)
    parent = load("OT-0338", "open-subject-awaiting-extended-comparison.json")
    result338 = load("OT-0338", "exact-comparison-response-reconstruction-aggregate.json")
    result334 = load("OT-0334", "scoped-provider-collision-recovery-rejected-aggregate.json")
    return repo, store, run, p82, runtime, result330, result280, core, base130, parent, result338, result334


def fixture_policy():
    return {"policy_id": "viable-options-first", "requirements": ["floor-preserved", "all-counted-contacts-viable"], "priority_order": list(METRICS), "directions": {metric: "higher" for metric in METRICS}, "on_tie": "retain-open", "rationale": "Prefer more independently viable continuation contacts while preserving the floor."}


def valid_policy(policy):
    return bool(
        isinstance(policy, dict)
        and set(policy) == {"policy_id", "requirements", "priority_order", "directions", "on_tie", "rationale"}
        and isinstance(policy["policy_id"], str)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", policy["policy_id"])
        and policy["requirements"] == ["floor-preserved", "all-counted-contacts-viable"]
        and sorted(policy["priority_order"]) == sorted(METRICS)
        and len(policy["priority_order"]) == len(METRICS)
        and set(policy["directions"]) == set(METRICS)
        and all(value in {"higher", "lower"} for value in policy["directions"].values())
        and policy["on_tie"] == "retain-open"
        and isinstance(policy["rationale"], str)
        and 1 <= len(policy["rationale"]) <= 2000
    )


def choose(policy, rows):
    if not valid_policy(policy):
        return {"supported": False, "selected_world_id": None, "reason": "invalid-policy"}
    admitted = [row for row in rows if row["admissible"]]
    if not admitted:
        return {"supported": False, "selected_world_id": None, "reason": "no-admissible-world"}
    def key(row):
        return tuple(row["metrics"][metric] * (1 if policy["directions"][metric] == "higher" else -1) for metric in policy["priority_order"])
    best_key = max(key(row) for row in admitted)
    winners = [row for row in admitted if key(row) == best_key]
    return {"supported": len(winners) == 1, "selected_world_id": winners[0]["world_id"] if len(winners) == 1 else None, "reason": "unique-policy-winner" if len(winners) == 1 else "policy-tie", "ranking": [{"world_id": row["world_id"], "key": key(row)} for row in sorted(admitted, key=lambda row: (key(row), row["world_id"]), reverse=True)]}


def expansion_anchor(policy):
    cases = []
    for index, (low_count, high_count, reverse) in enumerate([(1, 2, False), (2, 4, True), (3, 5, False), (1, 5, True)]):
        low = {"world_id": f"anchor-{index}-low", "admissible": True, "metrics": {"viable_contact_count": low_count, "mean_match_basis_points": 3333, "minimum_match_basis_points": 3333}}
        high = {"world_id": f"anchor-{index}-high", "admissible": True, "metrics": {"viable_contact_count": high_count, "mean_match_basis_points": 3333, "minimum_match_basis_points": 3333}}
        rows = [high, low] if reverse else [low, high]
        selected = choose(policy, rows)
        cases.append({"case_id": f"anchor-{index}", "expected_world_id": high["world_id"], "selected_world_id": selected["selected_world_id"], "passed": selected["selected_world_id"] == high["world_id"]})
    regressive = {"world_id": "anchor-regressive-high", "admissible": False, "metrics": {"viable_contact_count": 9, "mean_match_basis_points": 9000, "minimum_match_basis_points": 9000}}
    preserved = {"world_id": "anchor-preserved", "admissible": True, "metrics": {"viable_contact_count": 2, "mean_match_basis_points": 3333, "minimum_match_basis_points": 3333}}
    selected = choose(policy, [regressive, preserved])
    cases.append({"case_id": "anchor-floor", "expected_world_id": preserved["world_id"], "selected_world_id": selected["selected_world_id"], "passed": selected["selected_world_id"] == preserved["world_id"]})
    return {"pass_count": sum(row["passed"] for row in cases), "case_count": len(cases), "rows": cases}


CHECKER = '''import json,re\nfrom pathlib import Path\np=json.loads(Path("world-consequence-policy.json").read_text()); c=json.loads(Path("policy-contract.json").read_text()); ok=isinstance(p,dict) and set(p)==set(c["required_keys"]) and isinstance(p.get("policy_id"),str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}",p["policy_id"])) and p.get("requirements")==c["requirements"] and sorted(p.get("priority_order",[]))==sorted(c["metrics"]) and len(p.get("priority_order",[]))==len(c["metrics"]) and set(p.get("directions",{}))==set(c["metrics"]) and all(v in ["higher","lower"] for v in p["directions"].values()) and p.get("on_tie")=="retain-open" and isinstance(p.get("rationale"),str) and 1<=len(p["rationale"])<=2000; print(json.dumps({"valid":ok})); raise SystemExit(0 if ok else 2)\n'''


def actor_projection(parent, result334, erased):
    common = {"source_subject_digest": parent["artifact_digest"], "comparison_extension": parent["active_comparative_world_contact_extension"], "prior_world_consequences": parent["comparative_world_consequence_receipts"], "public_candidate_catalog": result334["selection_history"][-1]["rows"]}
    if erased:
        common["subject_priorities"] = None
        common["continuation"] = {"status": "open", "next_opening": "Author a world-consequence comparison policy."}
    else:
        common["subject_priorities"] = {"active_developmental_stake": parent["active_developmental_stake"], "active_pursuit": parent["active_pursuit"], "world_seeking_question": parent["active_world_seeking_stake"]["stake"]["question"], "world_seeking_anchors": parent["active_world_seeking_stake"]["stake"]["subject_anchors"]}
        common["continuation"] = parent["continuation"]
    return common


def seed_actor(root, parent, result334, erased):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "subject-position.json", actor_projection(parent, result334, erased))
    write_json(seed / "policy-contract.json", {"required_keys": ["policy_id", "requirements", "priority_order", "directions", "on_tie", "rationale"], "requirements": ["floor-preserved", "all-counted-contacts-viable"], "metrics": METRICS, "metric_meanings": {"viable_contact_count": "Number of distinct contacts that preserve the inherited floor and pass the full unresolved-contact-to-open-correction fixture.", "mean_match_basis_points": "Mean current public-program match rate across counted contacts; 10000 is complete local agreement.", "minimum_match_basis_points": "Worst current public-program match rate among counted contacts; 10000 is complete local agreement."}, "directions": ["higher", "lower"], "tie_action": "retain-open"})
    write_json(seed / "world-consequence-policy.json", {"policy_id": "replace-me", "requirements": ["floor-preserved", "all-counted-contacts-viable"], "priority_order": METRICS, "directions": {metric: "higher" for metric in METRICS}, "on_tie": "retain-open", "rationale": "Replace this placeholder from the inherited position."})
    (seed / "check_policy.py").write_text(CHECKER)
    immutable = ["subject-position.json", "policy-contract.json", "check_policy.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["world-consequence-policy.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue from the supplied subject position by authoring how world-level consequence should compare catalogued worlds before the remaining world's consequence is available. Choose a complete lexicographic metric order and direction under the fixed viability and floor requirements. You may not name a world in the policy. Sealed targets, cases, reference sources, future outcome, sibling output, evaluator fixtures, and the expected policy are unavailable. Edit only world-consequence-policy.json, run python3 check_policy.py, inspect the exact diff, then return the required JSON summary.\n")
    return seed


def run_actor(context, root, parent, result334, erased):
    label = "world-consequence-policy-author-erased" if erased else "world-consequence-policy-author"
    seed = seed_actor(root, parent, result334, erased)
    output, base_audit, workspace, _ = context.run_actor(label, seed, SCHEMA, (seed / "README.md").read_text().strip())
    try:
        policy = json.loads((workspace / "world-consequence-policy.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        checker = subprocess.run(["python3", "check_policy.py"], cwd=workspace, capture_output=True)
        semantic = immutable_ok and checker.returncode == 0 and valid_policy(policy)
    except (OSError, ValueError, KeyError, TypeError):
        policy, semantic, immutable_ok = None, False, False
    output_ok = output == {"action": "author-world-consequence-policy", "files_changed": ["world-consequence-policy.json"]}
    audit = context.audit_actor(label, output, base_audit, semantic and output_ok, ["world-consequence-policy.json"])
    certificate = contact.base.certify_g11(context, label, audit)
    return {"accepted": bool(semantic and output_ok and certificate["challenger_accepted"]), "policy": policy, "output": output, "audit": audit, "g11": certificate, "priority_erased": erased, "immutable_ok": immutable_ok}


def bind_policy(parent, actor, p82):
    body = {"authority": AUTHORITY + "-bound-policy", "source_subject_digest": parent["artifact_digest"], "comparison_extension_binding_digest": parent["active_comparative_world_contact_extension"]["binding_digest"], "actor_patch_digest": actor["audit"]["patch_digest"], "policy": actor["policy"], "selection_authority": True, "world_authority": False, "scoring_authority": True, "outcome_authority": False, "admission_authority": False}
    return {**body, "binding_digest": p82.digest(body)}


def world_row(root, parent, policy_binding, provider, result280, p82, runtime):
    package, evaluation = provider["package"], provider["evaluation"]
    observation, offered, reused = contact.b.base281.wake(parent, package, p82)
    fixture_rows = []
    for index, target in enumerate(sorted(provider["eligible_targets"]), 1):
        row = contact.contact_fixture(root / f"target-{index:02d}", offered, package, evaluation, result280, target, p82, runtime)
        decision = contact.contact_base.base270.fixture_decision(package, evaluation, target)
        action = {"decision": decision, "binding": {"binding_digest": "a" * 64, "contact_identity": "b" * 64}}
        pulse = {"authority": AUTHORITY + "-fixture-pulse", "content": None, "source_subject_digest": offered["artifact_digest"], "derived_operation": "expanded-select"}
        pulse["pulse_digest"] = p82.digest(pulse)
        intermediate = contact.contact_base.base270.compile_intermediate(offered, action, pulse, p82)
        world = contact.contact_base.base270.sealed_world(intermediate, action, package, result280, p82)
        final = contact.contact_base.base270.compile_world(intermediate, world, p82)
        inherited_targets = parent["local_frontier_ledger"]["targets"]
        full_floor_preserved = all(final["local_frontier_ledger"]["targets"].get(name) == value for name, value in inherited_targets.items())
        viable = all([row["checker"], row["semantic"], row["public"], row["public_only"], row["world_matches"] == 2, row["world_outcome"] == "unresolved", row["offer_consumed"], row["new_epoch"], row["conformant"], row["routes_correction"], row["old_assign_berth_floor_exact"], full_floor_preserved])
        fixture_rows.append({"target": target, "matches": row["world_matches"], "case_count": len(evaluation["rows"][target]), "viable": viable, "floor_preserved": full_floor_preserved})
    total_cases = sum(row["case_count"] for row in fixture_rows)
    scores = [row["matches"] * 10000 // row["case_count"] for row in fixture_rows]
    floor_preserved = bool(fixture_rows and all(row["floor_preserved"] for row in fixture_rows))
    metrics = {"viable_contact_count": sum(row["viable"] for row in fixture_rows), "mean_match_basis_points": sum(row["matches"] for row in fixture_rows) * 10000 // total_cases if total_cases else 0, "minimum_match_basis_points": min(scores) if scores else 0}
    admissible = bool(policy_binding and observation["status"] == "world-available" and not reused and evaluation["valid"] and evaluation["full_package_digest"] == p82.digest(package) and floor_preserved and fixture_rows and all(row["viable"] for row in fixture_rows))
    body = {"authority": AUTHORITY + "-viability-world-consequence", "source_subject_digest": parent["artifact_digest"], "policy_binding_digest": policy_binding["binding_digest"] if policy_binding else None, "world_id": package["world_id"], "package_digest": evaluation["full_package_digest"], "contact_rows": fixture_rows, "metrics": metrics, "floor_preserved": floor_preserved, "admissible": admissible, "world_authority": True, "scoring_authority": True, "outcome_authority": True, "actor_authority": False}
    return {**body, "receipt_digest": p82.digest(body)}


def compile_child(parent, binding, receipts, decision, p82):
    body = {"authority": AUTHORITY + "-policy-consequence-decision", "source_subject_digest": parent["artifact_digest"], "policy_binding_digest": binding["binding_digest"], "world_consequence_receipt_digests": [row["receipt_digest"] for row in receipts], "selection": decision, "incumbent_descriptor_selected_world_id": "harbor-of-three-seals", "directional_error": bool(decision["supported"] and decision["selected_world_id"] != "harbor-of-three-seals"), "selection_authority": True, "outcome_authority": False}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["world_consequence_policy_bindings"] = [*child.get("world_consequence_policy_bindings", []), binding]
    child["active_world_consequence_policy"] = binding
    child["viability_world_consequence_receipts"] = [*child.get("viability_world_consequence_receipts", []), *receipts]
    child["world_consequence_policy_decisions"] = [*child.get("world_consequence_policy_decisions", []), receipt]
    if receipt["directional_error"]:
        child["active_world_seeking_stake_revision_due"] = receipt
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Revise or retain the world-seeking stake under the subject-authored consequence policy's directional result."}
    else:
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Retain the world-seeking stake and seek a consequence that distinguishes the subject-authored world policy."}
    child["unresolved"] = parent["active_world_seeking_stake"]["stake"]["question"]
    return p82.seal(child), receipt


def preflight(root, p82, runtime, parent, result338, result334, result330):
    root.mkdir(parents=True, exist_ok=True)
    policy = fixture_policy()
    rows = [{"world_id": "two", "admissible": True, "metrics": {"viable_contact_count": 2, "mean_match_basis_points": 3333, "minimum_match_basis_points": 3333}}, {"world_id": "three", "admissible": True, "metrics": {"viable_contact_count": 3, "mean_match_basis_points": 3333, "minimum_match_basis_points": 3333}}]
    regressive = [{"world_id": "nine-bad", "admissible": False, "metrics": {"viable_contact_count": 9, "mean_match_basis_points": 9000, "minimum_match_basis_points": 9000}}, rows[0]]
    active_seed = seed_actor(root / "active", parent, result334, False)
    erased_seed = seed_actor(root / "erased", parent, result334, True)
    active_corpus = "\n".join(path.read_text(errors="replace") for path in active_seed.rglob("*") if path.is_file())
    erased_corpus = "\n".join(path.read_text(errors="replace") for path in erased_seed.rglob("*") if path.is_file())
    third = next(provider for provider in result334["providers"] if provider["package"]["world_id"] == "morrowmere-lantern-01")
    sealed = list(third["package"]["sealed_reference_sources"].values())
    anchor = expansion_anchor(policy)
    inverse = copy.deepcopy(policy)
    inverse["directions"]["viable_contact_count"] = "lower"
    checks = {"source_hashes_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256 and hashlib.sha256(CONTACT_PATH.read_bytes()).hexdigest() == CONTACT_SHA256, "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST and result338["receipt_digest"] == OT338_RECEIPT and result338["observer_disposition"] == "promoted" and runtime.identity_conforms(parent), "exact_extension_requests_third_world": parent["active_comparative_world_contact_extension"]["world_ids"] == ["morrowmere-lantern-01"], "prior_pair_exactly_tied": len(parent["comparative_world_consequence_receipts"]) == 2 and not base.base.directionally_distinguishes(parent["comparative_world_consequence_receipts"]), "policy_language_valid": valid_policy(policy), "lexicographic_widening_fixture": choose(policy, rows)["selected_world_id"] == "three", "five_of_five_expansion_anchor": anchor["pass_count"] == anchor["case_count"] == 5, "inverse_widening_direction_fails_anchor": expansion_anchor(inverse)["pass_count"] < 5, "floor_regression_never_wins": choose(policy, regressive)["selected_world_id"] == "two", "invalid_policy_rejects": not valid_policy({**policy, "priority_order": [METRICS[0]] * 3}), "policy_erasure_has_no_authority": choose({}, rows)["reason"] == "invalid-policy", "active_seed_has_priorities_erased_seed_does_not": "preserved-contact-ledger" in active_corpus and "preserved-contact-ledger" not in erased_corpus, "both_actor_seeds_hide_third_consequence": all(source not in active_corpus and source not in erased_corpus for source in sealed) and "clear_route" not in active_corpus and "open_lock" not in active_corpus, "g11_exact_active": result330["checks"]["passed"]}
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "source_ot0338_receipt_digest": result338["receipt_digest"], "checks": checks}
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
    repo, store, run, p82, runtime, result330, result280, core, base130, parent, result338, result334 = setup(args)
    with tempfile.TemporaryDirectory() as directory:
        frozen = preflight(Path(directory), p82, runtime, parent, result338, result334, result330)
    if args.preflight_only:
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0339 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", frozen)
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0339 preflight failed")
    context = contact.base305.actor_context(runtime, core, base130, run, repo)
    active = run_actor(context, run / "active", parent, result334, False)
    erased = run_actor(context, run / "erased", parent, result334, True)
    active_anchor = expansion_anchor(active["policy"]) if active["accepted"] else None
    erased_anchor = expansion_anchor(erased["policy"]) if erased["accepted"] else None
    binding = bind_policy(parent, active, p82) if active["accepted"] and active_anchor["pass_count"] == active_anchor["case_count"] else None
    providers = result334["providers"]
    receipts = [world_row(run / f"world-{index:02d}", parent, binding, provider, result280, p82, runtime) for index, provider in enumerate(providers, 1)] if binding else []
    decision = choose(active["policy"], receipts) if binding and all(row["admissible"] for row in receipts) else {"supported": False, "selected_world_id": None, "reason": "invalid-world-receipt"}
    erased_decision = choose(erased["policy"], receipts) if erased["accepted"] and receipts else None
    final, consequence = compile_child(parent, binding, receipts, decision, p82) if binding and receipts else (parent, None)
    operational = bool(active["accepted"] and binding and len(receipts) == 3 and all(row["admissible"] for row in receipts) and runtime.identity_conforms(final) and final["continuation"]["status"] == "open")
    causal = bool(operational and erased["accepted"] and erased_anchor and (erased["policy"] != active["policy"] or erased_decision != decision or erased_anchor != active_anchor))
    checks = {"preflight_passed": frozen["checks"]["passed"], "active_policy_actor_clean": active["accepted"], "active_policy_passes_expansion_anchor": bool(active_anchor and active_anchor["pass_count"] == active_anchor["case_count"] == 5), "policy_bound_before_third_consequence": bool(binding and all(row["policy_binding_digest"] == binding["binding_digest"] for row in receipts)), "three_viable_world_receipts": len(receipts) == 3 and all(row["admissible"] for row in receipts), "policy_erasure_cannot_select": choose({}, receipts)["reason"] == "invalid-policy", "stake_byte_exact": final["active_world_seeking_stake"] == parent["active_world_seeking_stake"], "open_operational_successor": operational}
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "source_ot0338_receipt_digest": result338["receipt_digest"], "active_actor": active, "priority_erased_actor": erased, "active_expansion_anchor": active_anchor, "priority_erased_expansion_anchor": erased_anchor, "policy_binding": binding, "world_receipts": receipts, "active_decision": decision, "priority_erased_decision": erased_decision, "policy_consequence_receipt": consequence, "checks": checks, "operational_transition_passed": operational, "priority_causal_claim_supported": causal, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 2}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    if operational:
        write_json(run / "open-subject-after-world-consequence-policy.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
