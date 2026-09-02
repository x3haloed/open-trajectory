from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
CURRENT_PATH = ROOT / "ot_0340_priority_causal_interpretation_correction.py"
CURRENT_SHA256 = "f8e6fbe1d769a99ba56a4f5c07f4d495d5349e6d0c69bab767684e40cd8fedc5"
FLOOR_PATH = ROOT / "ot_0328_contextual_selection_machinery_expansion.py"
FLOOR_SHA256 = "fe9f211301ca7ca2ff5a442a4169d615b704847ce92a0f9c587bcfdffe1c2cf3"
PIPELINE_PATH = ROOT / "ot_0326_executable_assessor_retention_reuse.py"
PIPELINE_SHA256 = "d759f2a2a66fc24f3eb59aaf94de039c092614aa5691ada97842d62596c08fe7"
PARENT_DIGEST = "32ac5ab0d95221ecfce05580d96448fe3e1af72ac9747bad11e496dd19d267c5"
OT340_RECEIPT = "fae663226d04435c8b79b4fdf5524646809ef365b2d559f31438d7baa22dcdcf"
AUTHORITY = "ot-0341-cumulative-floor-selector-scope"
SCHEMA = REPO / "spec/ot-0341-selector-scope-decision.schema.json"
FEATURES = ("branch_nodes", "call_nodes", "comparison_nodes", "loop_nodes", "source_bytes")


def import_frozen(path: Path, expected: str, name: str):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"frozen source changed: {path.name}: {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


current_base = import_frozen(CURRENT_PATH, CURRENT_SHA256, "ot0341_frozen_ot0340")
floor_base = import_frozen(FLOOR_PATH, FLOOR_SHA256, "ot0341_frozen_ot0328")
pipeline_base = import_frozen(PIPELINE_PATH, PIPELINE_SHA256, "ot0341_frozen_ot0326")
contact_base = current_base.base
write_json = current_base.write_json


def setup(args):
    repo, store, _, p82, runtime, _, parent, _ = current_base.setup(args)
    selector = contact_base.contact.base.base.base.base.base.b.authority_base.guide_base.load_base().selector_base
    aggregate340 = selector.load_artifact(
        p82, repo, store, "OT-0340", "priority-causal-interpretation-correction-aggregate.json"
    )
    values328 = floor_base.setup(args)
    _, _, _, p82_floor, _, parent326, seed326, parent328, result327, reconstruction327, private327, _, _ = values328
    values339 = contact_base.setup(args)
    result330, result280, core, base130 = values339[5:9]
    result334 = values339[-1]
    run = (args.evidence_root or store / "runs/OT-0341").resolve()
    if p82_floor.digest(parent) != p82.digest(parent):
        raise RuntimeError("evidence helpers disagree")
    return (
        repo, store, run, p82, runtime, parent, aggregate340, parent326,
        seed326, parent328, result327, reconstruction327, private327,
        result334, result330, result280, core, base130,
    )


def reconstructed_floor(parent326, seed326, parent328, result327, private327, p82):
    cases = floor_base.floor40(parent326, seed326, parent328, result327, private327, p82)
    contacts = []
    for row in cases:
        body = {
            "authority": AUTHORITY + "-exact-floor-reconstruction",
            "case_id": row["case_id"],
            "catalog_digest": p82.digest(row["case"]["catalog"]),
            "best_world_id": row["best_world_id"],
            "outcome_authority": True,
        }
        contacts.append({
            "catalog": copy.deepcopy(row["case"]["catalog"]),
            "outcome": {**body, "receipt_digest": p82.digest(body)},
        })
    return contacts


def directional_contact(parent, result334, p82):
    due = parent["active_world_seeking_stake_revision_due"]
    catalog = copy.deepcopy(result334["selection_history"][-1]["rows"])
    body = {
        "authority": AUTHORITY + "-composed-policy-consequence",
        "source_policy_consequence_receipt_digest": due["receipt_digest"],
        "source_policy_binding_digest": due["policy_binding_digest"],
        "source_world_consequence_receipt_digests": due["world_consequence_receipt_digests"],
        "catalog_digest": p82.digest(catalog),
        "best_world_id": due["selection"]["selected_world_id"],
        "outcome_authority": True,
    }
    return {
        "catalog": catalog,
        "selection": {
            "selected_world_id": due["incumbent_descriptor_selected_world_id"],
            "directional_error": due["directional_error"],
        },
        "outcome": {**body, "receipt_digest": p82.digest(body)},
    }


def erase_floor_outcomes(contacts, p82):
    erased = []
    for row in contacts:
        outcome = row["outcome"]
        erased.append({
            "catalog": copy.deepcopy(row["catalog"]),
            "outcome": {
                "authority": AUTHORITY + "-floor-outcome-erasure",
                "source_outcome_digest": p82.digest(outcome),
                "best_world_id": None,
                "outcome_authority": False,
            },
        })
    return erased


def select(stake, catalog):
    ranked = []
    for item in catalog:
        score = sum(stake["weights"][name] * item["features"][name] for name in FEATURES)
        ranked.append((score, item["public_package_digest"], item["world_id"]))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    gap = ranked[0][0] - ranked[1][0]
    return ranked[0][2] if gap >= stake["minimum_score_gap"] else None


def score(stake, contacts):
    rows = []
    for index, contact in enumerate(contacts):
        chosen = select(stake, contact["catalog"])
        best = contact["outcome"].get("best_world_id")
        rows.append({"case_index": index, "selected_world_id": chosen, "best_world_id": best, "passed": chosen == best})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "rows": rows}


def target_deltas(contact):
    best = contact["outcome"]["best_world_id"]
    target = next(item for item in contact["catalog"] if item["world_id"] == best)
    return [
        tuple(target["features"][name] - other["features"][name] for name in FEATURES)
        for other in contact["catalog"] if other["world_id"] != best
    ]


def bounded_impossibility(floor, contact, subject):
    stake = pipeline_base.base.base.base316.stake_of(subject)
    frequencies = Counter(target_deltas(row)[0] for row in floor)
    new = target_deltas(contact)
    upper_floor = (-3, 0, -3, 0, -108)
    lower_floor = (3, 0, 3, 0, 156)
    quay_constraint = (-3, -1, 0, 0, -122)
    low, high = pipeline_base.contract_for(subject)["weight_integer_range"]
    minimum = stake["minimum_score_gap"]
    # The two floor inequalities imply 48*source_bytes >= 2*minimum;
    # integer weights therefore require source_bytes >= 1.  At that value,
    # even the most favorable bounded branch/call weights cannot satisfy the
    # Morrowmere-over-Morrow-Quay inequality.
    minimum_source = (2 * minimum + 48 - 1) // 48
    best_quay_margin = -3 * low - low - 122 * minimum_source
    return {
        "floor_constraint_frequencies": {",".join(map(str, key)): value for key, value in sorted(frequencies.items())},
        "upper_floor_constraint_present": frequencies[upper_floor] > 0,
        "lower_floor_constraint_present": frequencies[lower_floor] > 0,
        "new_constraints": [list(row) for row in new],
        "quay_constraint_present": quay_constraint in new,
        "minimum_source_bytes_from_floor": minimum_source,
        "maximum_quay_margin_at_bounds": best_quay_margin,
        "required_margin": minimum,
        "bounded_41_of_41_impossible": bool(
            frequencies[upper_floor] > 0
            and frequencies[lower_floor] > 0
            and quay_constraint in new
            and minimum_source >= 1
            and best_quay_margin < minimum
            and low == -20 and high == 20
        ),
    }


DECISION_CONTRACT = {
    "required_keys": ["decision_id", "global_stake_action", "world_policy_role", "next_operation", "rationale"],
    "allowed": [
        ["revise", "evidence-only", "test-revised-global-stake"],
        ["retain", "post-contact-selector", "test-world-consequence-policy-reuse"],
        ["retain", "unresolved", "seek-more-stake-evidence"],
    ],
}


CHECK_SCOPE = '''import json,re\nfrom pathlib import Path\nd=json.loads(Path("selector-scope-decision.json").read_text()); c=json.loads(Path("selector-scope-contract.json").read_text()); keys=set(c["required_keys"]); triple=[d.get("global_stake_action"),d.get("world_policy_role"),d.get("next_operation")]; ok=isinstance(d,dict) and set(d)==keys and isinstance(d.get("decision_id"),str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}",d["decision_id"])) and triple in c["allowed"] and isinstance(d.get("rationale"),str) and 1<=len(d["rationale"])<=2000; print(json.dumps({"valid":ok,"triple":triple},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''


def valid_decision(decision):
    if not isinstance(decision, dict) or set(decision) != set(DECISION_CONTRACT["required_keys"]):
        return False
    triple = [decision["global_stake_action"], decision["world_policy_role"], decision["next_operation"]]
    return bool(
        isinstance(decision["decision_id"], str)
        and 3 <= len(decision["decision_id"]) <= 64
        and triple in DECISION_CONTRACT["allowed"]
        and isinstance(decision["rationale"], str)
        and 1 <= len(decision["rationale"]) <= 2000
    )


def front(contact):
    return [{
        "front_id": "world-consequence-directional-error",
        "offer_index": 0,
        "kind": "world-level-consequence-conflict",
        "contacts": [contact],
    }]


def seed_actor(root, subject, floor, contact, p82, *, erased):
    seed = pipeline_base.seed_actor(root, subject, front(contact), floor, p82)
    placeholder = {
        "decision_id": "replace-neutral-decision",
        "global_stake_action": "retain",
        "world_policy_role": "unresolved",
        "next_operation": "seek-more-stake-evidence",
        "rationale": "Replace this neutral placeholder after running the inherited pipeline.",
    }
    write_json(seed / "selector-scope-decision.json", placeholder)
    write_json(seed / "selector-scope-contract.json", DECISION_CONTRACT)
    write_json(seed / "world-consequence-policy-binding.json", subject["active_world_consequence_policy"])
    write_json(seed / "policy-consequence-decision.json", subject["active_world_seeking_stake_revision_due"])
    (seed / "check_scope.py").write_text(CHECK_SCOPE)
    envelope = json.loads((seed / "mutation-envelope.json").read_text())
    envelope["editable"] = ["stake-revision.json", "selector-scope-decision.json"]
    envelope["immutable"] = [
        *envelope["immutable"][:-2],
        "selector-scope-contract.json",
        "world-consequence-policy-binding.json",
        "policy-consequence-decision.json",
        "check_scope.py",
        *envelope["immutable"][-2:],
    ]
    write_json(seed / "mutation-envelope.json", envelope)
    visibility = "The exact 40 historical outcomes are available." if not erased else "The 40 historical catalogs remain, but their outcome answers are unavailable in this branch."
    (seed / "README.md").write_text(
        "Continue from the exact subject after its global descriptor stake and its pre-consequence world policy disagreed. "
        + visibility
        + " Run python3 continue_pipeline.py before editing. Decide whether the consequence warrants a global stake revision, a scoped post-contact role for the already-bound world policy, or more evidence. The alternatives and consistency rules are in selector-scope-contract.json. Edit selector-scope-decision.json and, only if globally revising, stake-revision.json. Run python3 check_revision.py and python3 check_scope.py, inspect the exact diff, and return the required report. No target choice, future catalog, sibling result, hidden score, evaluator, or admission result is supplied.\n"
    )
    return seed, placeholder


def output_valid(output, changed_stake):
    expected = ["selector-scope-decision.json"] + (["stake-revision.json"] if changed_stake else [])
    return bool(
        isinstance(output, dict)
        and set(output) == {"action", "files_changed", "note"}
        and output.get("action") == "resolve-selector-scope"
        and sorted(output.get("files_changed", [])) == sorted(expected)
        and isinstance(output.get("note"), str)
    )


def run_actor(context, root, subject, floor, contact, p82, label, *, erased):
    seed, placeholder = seed_actor(root, subject, floor, contact, p82, erased=erased)
    output, audit0, workspace, _ = context.run_actor(label, seed, SCHEMA, (seed / "README.md").read_text().strip())
    trace = (context.evidence(label) / "events.jsonl").read_text()
    pipeline = pipeline_base.run_pipeline(seed)
    try:
        candidate = json.loads((workspace / "stake-revision.json").read_text())
        decision = json.loads((workspace / "selector-scope-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        checker = pipeline_base.base.base.base315.run_checker(
            pipeline_base.base.base.base315.CORRECTED_CHECKER,
            candidate,
            pipeline_base.contract_for(subject),
        )
        checker_ok = pipeline_base.base.base.base315.corrected_accepts(checker)
        scope_check = subprocess.run([sys.executable, "check_scope.py"], cwd=workspace, capture_output=True, text=True, timeout=5, check=False)
        changed_stake = candidate != pipeline_base.base.base.base316.stake_of(subject)
        decision_changed = decision != placeholder
        consistency = bool(
            valid_decision(decision)
            and ((decision["global_stake_action"] == "revise") == changed_stake)
        )
        pipeline_invoked = pipeline_base.base.base.base.base.named_command_succeeded(trace, "continue_pipeline.py")
        revision_checker_invoked = pipeline_base.base.base.base.base.named_command_succeeded(trace, "check_revision.py")
        scope_checker_invoked = pipeline_base.base.base.base.base.named_command_succeeded(trace, "check_scope.py")
        candidates = pipeline["parsed"].get("search_result", {}).get("candidates", []) if isinstance(pipeline["parsed"], dict) else []
        candidate_from_pipeline = bool(
            not changed_stake or candidate["weights"] in [row["weights"] for row in candidates]
        )
        transport = output_valid(output, changed_stake)
        semantic = bool(
            immutable_ok and checker_ok and scope_check.returncode == 0 and decision_changed
            and consistency and pipeline_invoked and revision_checker_invoked
            and scope_checker_invoked and candidate_from_pipeline and transport
        )
    except (OSError, ValueError, KeyError, TypeError):
        candidate = decision = None
        immutable_ok = checker_ok = changed_stake = decision_changed = consistency = False
        pipeline_invoked = revision_checker_invoked = scope_checker_invoked = False
        candidate_from_pipeline = transport = semantic = False
    expected = ["selector-scope-decision.json"] + (["stake-revision.json"] if changed_stake else [])
    audit = context.audit_actor(label, output, audit0, semantic, expected)
    certificate = contact_base.contact.base.certify_g11(context, label, audit)
    accepted = bool(semantic and certificate["challenger_accepted"])
    return {
        "accepted": accepted,
        "candidate_stake": candidate,
        "decision": decision,
        "changed_stake": changed_stake,
        "pipeline": pipeline["parsed"],
        "output": output,
        "audit": audit,
        "g11": certificate,
        "workspace_evaluation": {
            "immutable_ok": immutable_ok,
            "stake_checker_ok": checker_ok,
            "decision_changed": decision_changed,
            "decision_consistent": consistency,
            "pipeline_invoked": pipeline_invoked,
            "revision_checker_invoked": revision_checker_invoked,
            "scope_checker_invoked": scope_checker_invoked,
            "candidate_from_pipeline": candidate_from_pipeline,
            "transport": transport,
            "semantic": semantic,
        },
    }


def compile_child(parent, actor, floor, contact, impossibility, p82):
    body = {
        "authority": AUTHORITY + "-selector-scope-decision",
        "source_subject_digest": parent["artifact_digest"],
        "actor_patch_digest": actor["audit"]["patch_digest"],
        "prior_stake_binding_digest": parent["active_world_seeking_stake"]["binding_digest"],
        "policy_binding_digest": parent["active_world_consequence_policy"]["binding_digest"],
        "directional_error_receipt_digest": parent["active_world_seeking_stake_revision_due"]["receipt_digest"],
        "floor_digest": p82.digest(floor),
        "directional_contact_digest": p82.digest(contact),
        "pipeline_result_digest": p82.digest(actor["pipeline"]),
        "bounded_impossibility_digest": p82.digest(impossibility),
        "decision": actor["decision"],
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    architecture = {
        "authority": AUTHORITY + "-active-two-stage-selection",
        "source_decision_receipt_digest": receipt["receipt_digest"],
        "pre_contact_proposal_binding_digest": parent["active_world_seeking_stake"]["binding_digest"],
        "post_contact_selection_binding_digest": parent["active_world_consequence_policy"]["binding_digest"],
        "next_operation": actor["decision"]["next_operation"],
        "selection_authority": True,
        "world_authority": False,
        "outcome_authority": False,
    }
    architecture["binding_digest"] = p82.digest(architecture)
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["selector_scope_decisions"] = [*child.get("selector_scope_decisions", []), receipt]
    child["active_selector_scope_decision"] = receipt
    child["selection_architectures"] = [*child.get("selection_architectures", []), architecture]
    child["active_selection_architecture"] = architecture
    child.pop("active_world_seeking_stake_revision_due", None)
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": "Test the retained world-consequence policy on a fresh consequence catalog without sacrificing the global 40/40 floor.",
    }
    return p82.seal(child), receipt, architecture


def preflight(root, p82, runtime, parent, aggregate340, parent326, seed326, parent328, result327, reconstruction327, private327, result334):
    root.mkdir(parents=True, exist_ok=True)
    floor = reconstructed_floor(parent326, seed326, parent328, result327, private327, p82)
    contact = directional_contact(parent, result334, p82)
    stake = pipeline_base.base.base.base316.stake_of(parent)
    fronts = front(contact)
    active = pipeline_base.run_assessor(parent["active_front_assessor_capability"]["source"], stake, pipeline_base.contract_for(parent), fronts, floor)
    erased_floor = erase_floor_outcomes(floor, p82)
    erased = pipeline_base.run_assessor(parent["active_front_assessor_capability"]["source"], stake, pipeline_base.contract_for(parent), fronts, erased_floor)
    with tempfile.TemporaryDirectory() as directory:
        active_seed, _ = seed_actor(Path(directory) / "active", parent, floor, contact, p82, erased=False)
        active_pipeline = pipeline_base.run_pipeline(active_seed)
        erased_seed, _ = seed_actor(Path(directory) / "erased", parent, erased_floor, contact, p82, erased=True)
        erased_pipeline = pipeline_base.run_pipeline(erased_seed)
    impossibility = bounded_impossibility(floor, contact, parent)
    retained_rows = parent["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["rows"]
    policy_anchor = contact_base.expansion_anchor(parent["active_world_consequence_policy"]["policy"])
    active_summary = active["parsed"][0] if active["parsed"] else None
    erased_summary = erased["parsed"][0] if erased["parsed"] else None
    checks = {
        "source_hashes_exact": all([
            hashlib.sha256(CURRENT_PATH.read_bytes()).hexdigest() == CURRENT_SHA256,
            hashlib.sha256(FLOOR_PATH.read_bytes()).hexdigest() == FLOOR_SHA256,
            hashlib.sha256(PIPELINE_PATH.read_bytes()).hexdigest() == PIPELINE_SHA256,
        ]),
        "exact_parent_and_correction": parent["artifact_digest"] == PARENT_DIGEST and aggregate340["receipt_digest"] == OT340_RECEIPT and aggregate340["operational_transition_preserved"],
        "exact_parent_open_conformant": parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "exact_floor_40_reconstructed": len(floor) == 40 and score(stake, floor)["pass_count"] == 40,
        "retained_score_identity_matches": [row["best_world_id"] for row in retained_rows] == [row["outcome"]["best_world_id"] for row in floor],
        "directional_contact_exact": contact["selection"]["selected_world_id"] == "harbor-of-three-seals" and contact["outcome"]["best_world_id"] == "morrowmere-lantern-01" and contact["selection"]["directional_error"],
        "bounded_41_impossible": impossibility["bounded_41_of_41_impossible"],
        "active_assessor_finds_only_regression": active["returncode"] == 0 and active_summary["current_pass_count"] == 0 and active_summary["best_pass_count"] == 1 and active_summary["current_floor_pass_count"] == 40 and active_summary["candidate_floor_pass_count"] == 35 and not active_summary["candidate_preserves_floor"],
        "active_pipeline_waits": active_pipeline["returncode"] == 0 and active_pipeline["parsed"]["reason"] == "router-did-not-select" and active_pipeline["parsed"]["route"]["action"] == "wait",
        "erased_preserves_catalogs": [row["catalog"] for row in erased_floor] == [row["catalog"] for row in floor] and all(not row["outcome"]["outcome_authority"] and row["outcome"]["best_world_id"] is None for row in erased_floor),
        "erasure_makes_revision_vacuously_admissible": erased["returncode"] == 0 and erased_summary["current_floor_pass_count"] == 0 and erased_summary["candidate_floor_pass_count"] == 0 and erased_summary["candidate_preserves_floor"] and erased_pipeline["parsed"]["available"] and erased_pipeline["parsed"]["route"]["action"] == "invoke-search",
        "world_policy_still_passes_anchor": policy_anchor["pass_count"] == policy_anchor["case_count"] == 5,
        "decision_contract_has_three_alternatives": len(DECISION_CONTRACT["allowed"]) == 3 and all(valid_decision({"decision_id": f"fixture-{i}", "global_stake_action": row[0], "world_policy_role": row[1], "next_operation": row[2], "rationale": "Fixture."}) for i, row in enumerate(DECISION_CONTRACT["allowed"])),
        "response_schema_explicit": set(json.loads(SCHEMA.read_text())["required"]) == {"action", "files_changed", "note"},
    }
    checks["passed"] = all(checks.values())
    body = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "floor_digest": p82.digest(floor),
        "directional_contact_digest": p82.digest(contact),
        "active_assessor": active,
        "erased_assessor": erased,
        "active_pipeline": active_pipeline,
        "erased_pipeline": erased_pipeline,
        "bounded_impossibility": impossibility,
        "policy_anchor": policy_anchor,
        "checks": checks,
    }
    result = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", result)
    return result, floor, contact, erased_floor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    values = setup(args)
    repo, store, run, p82, runtime, parent, aggregate340 = values[:7]
    parent326, seed326, parent328, result327, reconstruction327, private327, result334, result330, result280, core, base130 = values[7:]
    with tempfile.TemporaryDirectory() as directory:
        report, floor, contact, erased_floor = preflight(Path(directory), p82, runtime, parent, aggregate340, parent326, seed326, parent328, result327, reconstruction327, private327, result334)
    if args.preflight_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0341 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", report)
    write_json(run / "cumulative-floor-40.json", floor)
    write_json(run / "directional-contact.json", contact)
    write_json(run / "outcome-erased-floor-40.json", erased_floor)
    if not report["checks"]["passed"]:
        raise SystemExit("OT-0341 preflight failed")
    context = contact_base.contact.base305.actor_context(runtime, core, base130, run / "actors", repo)
    active = run_actor(context, run / "active", parent, floor, contact, p82, "cumulative-floor-scope-successor", erased=False)
    active_floor_score = score(active["candidate_stake"], floor) if active["accepted"] else None
    active_contact_score = score(active["candidate_stake"], [contact]) if active["accepted"] else None
    active_scope = active.get("decision") or {}
    operational = bool(
        active["accepted"]
        and not active["changed_stake"]
        and active_scope.get("global_stake_action") == "retain"
        and active_scope.get("world_policy_role") == "post-contact-selector"
        and active_scope.get("next_operation") == "test-world-consequence-policy-reuse"
        and active["pipeline"].get("reason") == "router-did-not-select"
        and active_floor_score["pass_count"] == 40
        and active_contact_score["pass_count"] == 0
    )
    child, scope_receipt, architecture = compile_child(parent, active, floor, contact, report["bounded_impossibility"], p82) if operational else (parent, None, None)
    write_json(run / "active-operational-subject.json", child)
    erased = run_actor(context, run / "erased", parent, erased_floor, contact, p82, "floor-outcome-erased-scope-successor", erased=True)
    erased_true_floor = score(erased["candidate_stake"], floor) if erased["accepted"] else None
    erased_contact = score(erased["candidate_stake"], [contact]) if erased["accepted"] else None
    erased_scope = erased.get("decision") or {}
    causal = bool(
        operational
        and erased["accepted"]
        and erased["changed_stake"]
        and erased_scope.get("global_stake_action") == "revise"
        and erased["pipeline"].get("available") is True
        and erased_true_floor["pass_count"] == 35
        and erased_contact["pass_count"] == 1
    )
    checks = {
        "preflight_passed": report["checks"]["passed"],
        "active_actor_clean": active["accepted"],
        "active_actor_invoked_inherited_pipeline": active["workspace_evaluation"]["pipeline_invoked"],
        "active_retains_nonregressive_global_stake": operational,
        "operational_child_sealed_before_control": (run / "active-operational-subject.json").exists(),
        "erased_actor_clean": erased["accepted"],
        "floor_erasure_changes_scope_decision": causal,
        "child_binds_two_stage_selection": not operational or child["active_selection_architecture"] == architecture,
        "child_open_conformant": child["continuation"]["status"] == "open" and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    disposition = "promoted" if checks["passed"] else ("conditional" if operational else "rejected")
    body = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0340_receipt_digest": aggregate340["receipt_digest"],
        "preflight_receipt_digest": report["receipt_digest"],
        "active_actor": active,
        "active_floor_score": active_floor_score,
        "active_contact_score": active_contact_score,
        "selector_scope_receipt": scope_receipt,
        "selection_architecture": architecture,
        "floor_outcome_erased_actor": erased,
        "erased_actor_true_floor_score": erased_true_floor,
        "erased_actor_contact_score": erased_contact,
        "checks": checks,
        "operational_transition_passed": operational,
        "executable_floor_causes_nonregressive_scope": causal,
        "observer_disposition": disposition,
        "subject_disposition": child["continuation"]["status"],
        "final_subject_digest": child["artifact_digest"],
        "fresh_actor_count": 2,
    }
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    if operational:
        write_json(run / "open-subject-after-selector-scope.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
