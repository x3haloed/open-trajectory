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
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0180_actor_chosen_correction_layer.py"
BASE_SHA256 = "35b0aa2a2697c55804538546e37131c36c0909ebe1421ba76bc58e4f1732447c"
PARENT_DIGEST = "5044e9d6c3f5fbf58dfc0dc2b67a9798b49c203a37b4521bcd1ad23c71f4779c"
SELECTOR_DIGEST = "2e8052eb037710fcc225baa0496e73619d59342043991a3b9f2873b82ab0e4dd"
PROJECTION_DIGEST = "ea40f4af68afe92b79b232cf3531240ecfef8b9ba515028eae7e9adc6f393d3b"
ASSIMILATION_SCHEMA = REPO / "spec/ot-0181-pursuit-assimilation.schema.json"

WORLD_BY_PROPERTY = {
    "continuity-under-reset": [
        {"case_id": "next-reset-a", "prediction": ["old-a"], "outcome": ["outcome-a"], "options": ["option-a"], "blocked": [], "signal": "carried-a", "expected": "carried-a", "before": "reset-v90", "after": "reset-v91", "compatible": False},
        {"case_id": "next-reset-b", "prediction": ["old-b"], "outcome": ["outcome-b"], "options": ["option-b"], "blocked": [], "signal": "carried-b", "expected": "carried-b", "before": "reset-v92", "after": "reset-v93", "compatible": False},
        {"case_id": "next-reset-c", "prediction": ["old-c"], "outcome": ["outcome-c"], "options": ["option-c"], "blocked": [], "signal": "carried-c", "expected": "carried-c", "before": "reset-v94", "after": "reset-v95", "compatible": False},
    ],
    "option-expansion": [
        {"case_id": "next-viable-a", "prediction": ["old-a"], "outcome": ["open-a", "blocked-a"], "options": ["open-a", "blocked-a"], "blocked": ["blocked-a"], "signal": "reset-a", "expected": ["open-a"], "before": "viable-v90", "after": "viable-v91", "compatible": False},
        {"case_id": "next-viable-b", "prediction": ["old-b"], "outcome": ["open-b", "blocked-b"], "options": ["open-b", "blocked-b"], "blocked": ["blocked-b"], "signal": "reset-b", "expected": ["open-b"], "before": "viable-v92", "after": "viable-v93", "compatible": False},
        {"case_id": "next-viable-c", "prediction": ["old-c"], "outcome": ["open-c", "blocked-c"], "options": ["open-c", "blocked-c"], "blocked": ["blocked-c"], "signal": "reset-c", "expected": ["open-c"], "before": "viable-v94", "after": "viable-v95", "compatible": False},
    ],
    "correction-from-error": [
        {"case_id": "next-correction-a", "prediction": ["old-a"], "outcome": ["observed-a"], "options": ["decoy-a"], "blocked": [], "signal": "reset-a", "expected": ["observed-a"], "before": "correct-v90", "after": "correct-v91", "compatible": False},
        {"case_id": "next-correction-b", "prediction": ["old-b"], "outcome": ["observed-b"], "options": ["decoy-b"], "blocked": [], "signal": "reset-b", "expected": ["observed-b"], "before": "correct-v92", "after": "correct-v93", "compatible": False},
        {"case_id": "next-correction-c", "prediction": ["old-c"], "outcome": ["observed-c"], "options": ["decoy-c"], "blocked": [], "signal": "reset-c", "expected": ["observed-c"], "before": "correct-v94", "after": "correct-v95", "compatible": False},
    ],
    "identity-gated-branch-filtering": [
        {"case_id": "next-identity-a", "prediction": ["old-a"], "outcome": ["observed-a"], "options": ["candidate-a"], "blocked": [], "signal": "reset-a", "expected": [], "before": "identity-v90", "after": "identity-v91", "compatible": False},
        {"case_id": "next-identity-b", "prediction": ["old-b"], "outcome": ["observed-b"], "options": ["candidate-b"], "blocked": [], "signal": "reset-b", "expected": [], "before": "identity-v92", "after": "identity-v93", "compatible": False},
        {"case_id": "next-identity-c", "prediction": ["old-c"], "outcome": ["observed-c"], "options": ["candidate-c"], "blocked": [], "signal": "reset-c", "expected": [], "before": "identity-v94", "after": "identity-v95", "compatible": False},
    ],
}

MECHANISM_BY_PROPERTY = {
    "continuity-under-reset": "reset-carrier",
    "option-expansion": "viable-branch-carrier",
    "correction-from-error": "prediction-corrector",
    "identity-gated-branch-filtering": "corrected-identity-gated-extension",
}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0180 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0181_frozen_ot0180", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.authority_base


def valid_stake(value: Any, current: dict[str, Any], allowed: set[str], action: str) -> bool:
    keys = {"stake_id", "property", "question", "rationale", "success_condition", "surrender_condition"}
    if not (isinstance(value, dict) and set(value) == keys and isinstance(value.get("stake_id"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", value["stake_id"]) and value.get("property") in allowed and all(isinstance(value.get(key), str) and value[key].strip() for key in keys - {"stake_id", "property"}) and value != current):
        return False
    return (action == "refine-current" and value["property"] == current["property"]) or (action == "retire-and-renew" and value["property"] != current["property"])


def valid_assimilation(value: Any, current: dict[str, Any], allowed: set[str], receipts: list[str]) -> bool:
    return bool(isinstance(value, dict) and set(value) == {"action", "rationale", "evidence_receipt_digests", "next_stake"} and value.get("action") in {"refine-current", "retire-and-renew"} and isinstance(value.get("rationale"), str) and value["rationale"].strip() and value.get("evidence_receipt_digests") == receipts and valid_stake(value.get("next_stake"), current, allowed, value["action"]))


def assimilation_seed(root: Path, parent: dict[str, Any], ordered: list[dict[str, Any]], correction: dict[str, Any], candidates: list[dict[str, Any]]) -> Path:
    seed = root / "assimilation-seed"
    seed.mkdir()
    receipts = [row["receipt_digest"] for row in ordered]
    current = parent["active_developmental_stake"]
    allowed = sorted(MECHANISM_BY_PROPERTY)
    template = {"action": "refine-current", "rationale": "Replace this rationale from the complete ordered consequence.", "evidence_receipt_digests": receipts, "next_stake": {**current, "stake_id": current["stake_id"] + "-refined", "question": "Replace with the specific missing contact question."}}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "active-stake.json": current, "mechanism-authority.json": parent["active_mechanism_authority_projection"], "correction-decision.json": correction, "ordered-consequences.json": ordered, "candidate-mechanisms.json": candidates, "developmental-property-vocabulary.json": allowed, "assimilation.json": template, "mutation-envelope.json": {"editable": ["assimilation.json"], "immutable": ["subject-position.json", "active-stake.json", "mechanism-authority.json", "correction-decision.json", "ordered-consequences.json", "candidate-mechanisms.json", "developmental-property-vocabulary.json", "check_assimilation.py"]}}
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    current_json = json.dumps(current, sort_keys=True)
    (seed / "check_assimilation.py").write_text(f'''import json,re\nfrom pathlib import Path\na=json.loads(Path("assimilation.json").read_text()); current=json.loads({current_json!r}); allowed=set({allowed!r}); receipts={receipts!r}; keys={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}\ndef valid_stake(s,action):\n base=isinstance(s,dict) and set(s)==keys and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and s.get("property") in allowed and all(isinstance(s.get(k),str) and s[k].strip() for k in keys-{{"stake_id","property"}}) and s!=current\n return bool(base and ((action=="refine-current" and s["property"]==current["property"]) or (action=="retire-and-renew" and s["property"]!=current["property"])))\naction=a.get("action") if isinstance(a,dict) else None\nok=isinstance(a,dict) and set(a)=={{"action","rationale","evidence_receipt_digests","next_stake"}} and action in {{"refine-current","retire-and-renew"}} and isinstance(a.get("rationale"),str) and bool(a["rationale"].strip()) and a.get("evidence_receipt_digests")==receipts and valid_stake(a.get("next_stake"),action)\nprint(json.dumps({{"passed":bool(ok),"action":action}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Assimilate the complete ordered correction consequence into the next developmental position. Exact retention is unavailable: either refine the current property by naming a materially changed, specific missing contact, or retire the fulfilled pursuit and author a complete stake with a different visible property. Cite all receipt digests in their visible order. Hidden future worlds are unavailable. Edit only assimilation.json, run python3 check_assimilation.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_assimilation(context, prior131, p82, root: Path, parent: dict[str, Any], ordered: list[dict[str, Any]], correction: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    label = "post-confirmation-pursuit-assimilation"
    seed = assimilation_seed(root, parent, ordered, correction, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        assimilation = json.loads((workspace / "assimilation.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        assimilation, immutable_ok = None, False
    receipts = [row["receipt_digest"] for row in ordered]
    valid = bool(valid_assimilation(assimilation, parent["active_developmental_stake"], set(MECHANISM_BY_PROPERTY), receipts) and immutable_ok and output and output.get("action") == "assimilate-confirmed-correction")
    audit = context.audit_actor(label, output, base_audit, valid, ["assimilation.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0181-bound-post-confirmation-assimilation", "source_subject_digest": parent["artifact_digest"], "active_stake_digest": p82.digest(parent["active_developmental_stake"]), "active_selector_binding_digest": parent["active_developmental_mechanism_selector"]["binding_digest"], "active_projection_binding_digest": parent["active_mechanism_authority_projection"]["binding_digest"], "evidence_receipt_digests": receipts, "actor_patch_digest": audit["patch_digest"], "assimilation": assimilation}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "assimilation": assimilation, "binding": binding}


def compile_successor(p82, parent: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    assimilation = binding["assimilation"]
    next_stake = assimilation["next_stake"]
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    history_body = {"authority": "ot-0181-assimilated-developmental-stake", "source_subject_digest": parent["artifact_digest"], "prior_stake": parent["active_developmental_stake"], "disposition": assimilation["action"], "assimilation_binding_digest": binding["binding_digest"], "evidence_receipt_digests": binding["evidence_receipt_digests"]}
    history = {**history_body, "history_digest": p82.digest(history_body)}
    child["assimilated_developmental_stakes"] = [*child.get("assimilated_developmental_stakes", []), history]
    child["pursuit_assimilation_decisions"] = [*child.get("pursuit_assimilation_decisions", []), binding]
    child["active_developmental_stake"] = next_stake
    opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = next_stake["question"]
    child.pop("active_developmental_mechanism_choice", None)
    return p82.seal(child)


def run_selection(context, prior131, p82, root: Path, label: str, subject: dict[str, Any], candidates: list[dict[str, Any]], latest: Any) -> dict[str, Any]:
    result = previous.run_selection(context, prior131, p82, root, label, subject, candidates, latest)
    binding = result.get("binding")
    if binding:
        body = {key: value for key, value in binding.items() if key not in {"authority", "binding_digest"}}
        body["authority"] = "ot-0181-bound-assimilated-pursuit-selection"
        result["binding"] = {**body, "binding_digest": p82.digest(body)}
    return result


def control_subject(p82, operational: dict[str, Any], parent_stake: dict[str, Any]) -> dict[str, Any]:
    child = copy.deepcopy(operational)
    child.pop("artifact_digest", None)
    child.pop("active_developmental_mechanism_choice", None)
    child["active_developmental_stake"] = parent_stake
    opening = "Open actor-stake-" + parent_stake["stake_id"] + ": " + parent_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = parent_stake["question"]
    return p82.seal(child)


def main() -> int:
    selector_lineage = authority_base.guide_base.load_base()
    selector_base = selector_lineage.selector_base
    base = selector_lineage.base
    prior131 = selector_lineage.prior131
    base130 = selector_lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0181").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0180", "open-subject-after-actor-chosen-authority-correction.json")
    result_178 = selector_base.load_artifact(p82, repo, store, "OT-0178", "consequence-admitted-live-authority-aggregate.json")
    result_179 = selector_base.load_artifact(p82, repo, store, "OT-0179", "live-authority-later-use-aggregate.json")
    result_180 = selector_base.load_artifact(p82, repo, store, "OT-0180", "actor-chosen-correction-layer-aggregate.json")
    candidates = selector_base.CANDIDATES
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    ordered = [
        {"stage": "initial-live-authority", "receipt_digest": result_178["world"]["receipt_digest"], "world": result_178["world"]},
        {"stage": "exact-later-use", "receipt_digest": result_179["world"]["receipt_digest"], "world": result_179["world"]},
        {"stage": "later-harm", "receipt_digest": result_180["harm_world"]["receipt_digest"], "world": result_180["harm_world"]},
        {"stage": "corrected-confirmation", "receipt_digest": result_180["confirmation_world"]["receipt_digest"], "world": result_180["confirmation_world"]},
    ]
    representative = {"action": "retire-and-renew", "rationale": "The completed correction retires this pursuit and opens viable filtering as the next contact.", "evidence_receipt_digests": [row["receipt_digest"] for row in ordered], "next_stake": {"stake_id": "filter-observed-branches", "property": "option-expansion", "question": "Can the subject return every currently viable observed branch without admitting blocked outcomes?", "rationale": "The complete correction separates raw replacement from viable filtering.", "success_condition": "Every returned set contains all and only viable observed branches.", "surrender_condition": "Surrender if any viable branch is omitted or any blocked branch is admitted."}}
    checker_accepts_representative = checker_rejects_exact_retention = False
    with tempfile.TemporaryDirectory() as temp:
        seed = assimilation_seed(Path(temp), parent, ordered, result_180["correction"]["binding"], candidates)
        authority_base.guide_base.write_json(seed / "assimilation.json", representative)
        check = subprocess.run([sys.executable, "check_assimilation.py"], cwd=seed, capture_output=True, text=True, check=False)
        checker_accepts_representative = check.returncode == 0 and json.loads(check.stdout)["passed"]
        invalid = copy.deepcopy(representative)
        invalid["action"] = "refine-current"
        invalid["next_stake"] = parent["active_developmental_stake"]
        authority_base.guide_base.write_json(seed / "assimilation.json", invalid)
        check = subprocess.run([sys.executable, "check_assimilation.py"], cwd=seed, capture_output=True, text=True, check=False)
        checker_rejects_exact_retention = check.returncode == 2 and not json.loads(check.stdout)["passed"]
    per_world = {}
    for prop, cases in WORLD_BY_PROPERTY.items():
        per_world[prop] = {row["mechanism_id"]: previous.evaluate_mechanism(row["mechanism_id"], operation, cases) for row in candidates}
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "selector_exact": parent["active_developmental_mechanism_selector"]["binding_digest"] == SELECTOR_DIGEST, "projection_exact": parent["active_mechanism_authority_projection"]["binding_digest"] == PROJECTION_DIGEST, "ordered_receipts_exact": [row["receipt_digest"] for row in ordered] == ["37f032bbd74ae87e49212feb69c31f681f7fe9ce2fb47ba67212304856cfcf6f", "c5004347f82efcdea81f3e631601d78cfe0d17d9f8d9d4401236f782c017a0a7", "af50d81e055d1a0fd7e3f529d45313ea4923bbf2dec2f304d82909896bce9af3", "0a95e6c2d881f169aa03ff0a15793c9b6e04df1806c35a11549c6308831c65f5"], "worlds_uniquely_separate": all(rows[MECHANISM_BY_PROPERTY[prop]]["passed"] and all(not value["passed"] for key, value in rows.items() if key != MECHANISM_BY_PROPERTY[prop]) for prop, rows in per_world.items()), "all_properties_routable": set(WORLD_BY_PROPERTY) == set(MECHANISM_BY_PROPERTY) == {prop for row in candidates for prop in row.get("properties", [])}, "representative_assimilation_valid": valid_assimilation(representative, parent["active_developmental_stake"], set(MECHANISM_BY_PROPERTY), [row["receipt_digest"] for row in ordered]), "public_checker_accepts_representative": checker_accepts_representative, "public_checker_rejects_exact_retention": checker_rejects_exact_retention, "schema_present": ASSIMILATION_SCHEMA.is_file() and authority_base.guide_base.CHOICE_SCHEMA.is_file()}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "world_digests": {prop: p82.digest(cases) for prop, cases in WORLD_BY_PROPERTY.items()}, "per_world": per_world}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0181 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    assimilation_root = run / "assimilation-authoring"
    assimilation_root.mkdir()
    assimilation = run_assimilation(context, prior131, p82, assimilation_root, parent, ordered, result_180["correction"]["binding"], candidates)
    candidate = compile_successor(p82, parent, assimilation["binding"]) if assimilation["binding"] else parent
    next_property = candidate["active_developmental_stake"]["property"]
    selected_cases = WORLD_BY_PROPERTY[next_property]
    expected_mechanism = MECHANISM_BY_PROPERTY[next_property]
    active_root = run / "active-successor-selection"
    active_root.mkdir()
    active = run_selection(context, prior131, p82, active_root, "assimilated-pursuit-successor-selection", candidate, candidates, ordered)
    active_mechanism = active["binding"]["mechanism_id"] if active["binding"] else None
    active_contact = previous.evaluate_mechanism(active_mechanism, operation, selected_cases)
    world_body = {"authority": "ot-0181-independent-actor-authored-next-contact", "source_subject_digest": candidate["artifact_digest"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"] if assimilation["binding"] else None, "selected_property": next_property, "selected_world_digest": p82.digest(selected_cases), "selection_binding_digest": active["binding"]["binding_digest"] if active["binding"] else None, "expected_mechanism": expected_mechanism, "selected_mechanism": active_mechanism, "selected_result": active_contact}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    authority_base.guide_base.write_json(run / "sealed-actor-authored-next-contact-world.json", world)
    operational_passed = bool(assimilation["binding"] and prior131.audit_accepted(assimilation["audit"]) and active["binding"] and prior131.audit_accepted(active["audit"]) and active_mechanism == expected_mechanism and active_contact["passed"])
    operational = parent
    if operational_passed:
        child = copy.deepcopy(candidate)
        child.pop("artifact_digest", None)
        capability_body = {"authority": "ot-0181-post-confirmation-pursuit-handoff", "source_subject_digest": parent["artifact_digest"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"], "selection_binding_digest": active["binding"]["binding_digest"], "world_receipt_digest": world["receipt_digest"], "selected_property": next_property}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["pursuit_assimilation_capabilities"] = [*child.get("pursuit_assimilation_capabilities", []), capability]
        child["active_developmental_mechanism_choice"] = active["binding"]
        operational = p82.seal(child)

    control = None
    control_contact = None
    control_valid = False
    if operational_passed:
        projected = control_subject(p82, operational, parent["active_developmental_stake"])
        control_root = run / "post-seal-old-pursuit-control"
        control_root.mkdir()
        control = run_selection(context, prior131, p82, control_root, "post-seal-old-pursuit-selection", projected, candidates, ordered)
        control_mechanism = control["binding"]["mechanism_id"] if control["binding"] else None
        control_contact = previous.evaluate_mechanism(control_mechanism, operation, selected_cases)
        control_valid = bool(control["binding"] and prior131.audit_accepted(control["audit"]))
    pursuit_content_causal = bool(operational_passed and control_valid and (control["binding"]["mechanism_id"] != active_mechanism or not control_contact["passed"]))
    control_body = {"authority": "ot-0181-post-seal-old-pursuit-control", "operational_subject_digest": operational["artifact_digest"], "active_selection_binding_digest": active["binding"]["binding_digest"] if active["binding"] else None, "selected_world_digest": p82.digest(selected_cases), "control_selection_binding_digest": control["binding"]["binding_digest"] if control and control["binding"] else None, "control_result": control_contact, "control_valid": control_valid, "pursuit_content_causal": pursuit_content_causal}
    control_world = {**control_body, "receipt_digest": p82.digest(control_body)}
    authority_base.guide_base.write_json(run / "post-seal-old-pursuit-control-world.json", control_world)
    authorized = {"artifact_digest", "active_developmental_stake", "active_pursuit", "continuation", "unresolved", "active_developmental_mechanism_choice", "assimilated_developmental_stakes", "pursuit_assimilation_decisions", "pursuit_assimilation_capabilities"}
    checks = {"assimilation_actor_accepted": bool(assimilation["binding"] and prior131.audit_accepted(assimilation["audit"])), "developmental_position_changed": candidate["active_developmental_stake"] != parent["active_developmental_stake"], "active_successor_actor_accepted": bool(active["binding"] and prior131.audit_accepted(active["audit"])), "actor_authored_property_selected_world": next_property == assimilation["binding"]["assimilation"]["next_stake"]["property"] if assimilation["binding"] else False, "active_selection_matches_property": active_mechanism == expected_mechanism, "active_contact_3_of_3": active_contact["pass_count"] == 3, "operational_successor_sealed": operational_passed and operational["artifact_digest"] != parent["artifact_digest"], "revised_authority_retained_exactly": operational.get("active_mechanism_authority_projection") == parent["active_mechanism_authority_projection"], "unauthorized_parent_state_retained": all(operational.get(key) == parent.get(key) for key in parent if key not in authorized), "operational_subject_sounding_open": runtime.identity_conforms(operational) and operational["continuation"]["status"] == "open", "post_seal_control_recorded": bool(not operational_passed or control_world["operational_subject_digest"] == operational["artifact_digest"])}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0181-post-confirmation-pursuit-assimilation", "source_subject_digest": parent["artifact_digest"], "assimilation": p82.compact(assimilation), "candidate_subject_digest": candidate["artifact_digest"], "active_selection": p82.compact(active), "next_contact_world": world, "operational_subject_digest": operational["artifact_digest"], "post_seal_control": p82.compact(control) if control else None, "post_seal_control_world": control_world, "checks": checks, "operational_transition_passed": checks["passed"], "pursuit_content_causal": pursuit_content_causal, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": operational["continuation"]["status"], "final_subject_digest": operational["artifact_digest"], "next_opening": operational["continuation"]["next_opening"], "fresh_actor_count": 2 + int(control is not None)}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", operational)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
