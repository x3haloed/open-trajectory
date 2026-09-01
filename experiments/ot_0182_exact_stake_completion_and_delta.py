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
BASE_PATH = ROOT / "ot_0181_post_confirmation_pursuit_assimilation.py"
BASE_SHA256 = "53e48f6e846b93db2c82dd1a38cb13b940cb017cde2c7e2dbcd0a9f1f07b57fc"
PARENT_DIGEST = "37cac3c6873efacd1ad314cf71035130bcd1fbaea5e87c00e2774b79eaccd05e"
SELECTOR_DIGEST = "2e8052eb037710fcc225baa0496e73619d59342043991a3b9f2873b82ab0e4dd"
PROJECTION_DIGEST = "ea40f4af68afe92b79b232cf3531240ecfef8b9ba515028eae7e9adc6f393d3b"
ASSIMILATION_SCHEMA = REPO / "spec/ot-0182-post-completion-assimilation.schema.json"

EXACT_TARGET = [
    {"case_id": "revoked-identity-hidden-a", "before": "program-v40", "after": "program-v41", "compatible": False, "identity_authority": "revoked", "options": ["transfer", "verify", "discard"], "blocked": ["discard"], "prediction": ["stale-a"], "outcome": ["transfer", "verify"], "signal": "reset-a", "expected": ["transfer", "verify"]},
    {"case_id": "revoked-identity-hidden-b", "before": "memory-v42", "after": "memory-v43", "compatible": False, "identity_authority": "revoked", "options": ["retain", "branch"], "blocked": [], "prediction": ["stale-b"], "outcome": ["retain", "branch"], "signal": "reset-b", "expected": ["retain", "branch"]},
    {"case_id": "revoked-identity-hidden-c", "before": "route-v44", "after": "route-v45", "compatible": False, "identity_authority": "revoked", "options": ["left", "right", "closed"], "blocked": ["closed"], "prediction": ["stale-c"], "outcome": ["left", "right"], "signal": "reset-c", "expected": ["left", "right"]},
]

DISJOINT_TARGET = [
    {"case_id": "revoked-identity-completion-a", "before": "score-v100", "after": "score-v101", "compatible": False, "identity_authority": "revoked", "options": ["continue", "unobserved-a", "blocked-a"], "blocked": ["blocked-a"], "prediction": ["stale-d"], "outcome": ["continue"], "signal": "reset-d", "expected": ["continue"]},
    {"case_id": "revoked-identity-completion-b", "before": "route-v102", "after": "route-v103", "compatible": False, "identity_authority": "revoked", "options": ["listen", "unobserved-b"], "blocked": [], "prediction": ["stale-e"], "outcome": ["listen"], "signal": "reset-e", "expected": ["listen"]},
    {"case_id": "revoked-identity-completion-c", "before": "carrier-v104", "after": "carrier-v105", "compatible": False, "identity_authority": "revoked", "options": ["renew", "unobserved-c", "blocked-c"], "blocked": ["blocked-c"], "prediction": ["stale-f"], "outcome": ["renew"], "signal": "reset-f", "expected": ["renew"]},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0181 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0182_frozen_ot0181", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.authority_base


def erased(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: erased(item) for key, item in value.items()}
    if isinstance(value, list):
        return [erased(item) for item in value]
    return None


def compile_delta(p82, subject: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    body = {
        "authority": "ot-0182-deterministic-developmental-delta",
        "source_subject_digest": subject["artifact_digest"],
        "active_stake_digest": p82.digest(subject["active_developmental_stake"]),
        "completion_receipt_digest": receipt["receipt_digest"],
        "transition": {
            "prior_status": "open",
            "selected_mechanism": receipt["selected_mechanism"],
            "exact_target_score": [receipt["exact_target_result"]["pass_count"], receipt["exact_target_result"]["case_count"]],
            "disjoint_target_score": [receipt["disjoint_target_result"]["pass_count"], receipt["disjoint_target_result"]["case_count"]],
            "retained_floor_score": [receipt["accumulated_floor_result"]["pass_count"], receipt["accumulated_floor_result"]["case_count"]],
            "criterion_status": "satisfied" if receipt["stake_criteria_satisfied"] else "unsatisfied",
            "next_stake": None,
        },
    }
    return {**body, "delta_digest": p82.digest(body)}


def valid_stake(stake: Any, current: dict[str, Any], action: str, allowed: set[str]) -> bool:
    keys = {"stake_id", "property", "question", "rationale", "success_condition", "surrender_condition"}
    base = isinstance(stake, dict) and set(stake) == keys and isinstance(stake.get("stake_id"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", stake["stake_id"]) and stake.get("property") in allowed and all(isinstance(stake.get(key), str) and stake[key].strip() for key in keys - {"stake_id", "property"}) and stake != current
    return bool(base and ((action == "refine-current" and stake["property"] == current["property"]) or (action == "retire-and-renew" and stake["property"] != current["property"])))


def valid_assimilation(value: Any, current: dict[str, Any], receipt_digest: str, allowed: set[str]) -> bool:
    if not isinstance(value, dict) or set(value) != {"action", "rationale", "completion_receipt_digest", "next_stake"}:
        return False
    action = value.get("action")
    return bool(action in {"refine-current", "retire-and-renew"} and isinstance(value.get("rationale"), str) and value["rationale"].strip() and value.get("completion_receipt_digest") == receipt_digest and valid_stake(value.get("next_stake"), current, action, allowed))


def assimilation_seed(root: Path, subject: dict[str, Any], receipt: dict[str, Any], delta: dict[str, Any], candidates: list[dict[str, Any]]) -> Path:
    seed = root / "assimilation-seed"
    seed.mkdir()
    current = subject["active_developmental_stake"]
    allowed = sorted(previous.MECHANISM_BY_PROPERTY)
    template = {"action": "refine-current", "rationale": "Replace after evaluating the completed contact.", "completion_receipt_digest": receipt["receipt_digest"], "next_stake": {**current, "stake_id": current["stake_id"] + "-next", "question": "Name a specific contact still absent after the completion receipt."}}
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(subject),
        "active-stake.json": current,
        "mechanism-authority.json": subject["active_mechanism_authority_projection"],
        "completion-receipt.json": receipt,
        "developmental-delta.json": delta,
        "candidate-mechanisms.json": candidates,
        "developmental-property-vocabulary.json": allowed,
        "assimilation.json": template,
        "mutation-envelope.json": {"editable": ["assimilation.json"], "immutable": ["subject-position.json", "active-stake.json", "mechanism-authority.json", "completion-receipt.json", "developmental-delta.json", "candidate-mechanisms.json", "developmental-property-vocabulary.json", "check_assimilation.py"]},
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    current_json = json.dumps(current, sort_keys=True)
    receipt_digest = receipt["receipt_digest"]
    (seed / "check_assimilation.py").write_text(f'''import json,re\nfrom pathlib import Path\na=json.loads(Path("assimilation.json").read_text()); current=json.loads({current_json!r}); allowed=set({allowed!r}); receipt={receipt_digest!r}; keys={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}\ndef valid_stake(s,action):\n base=isinstance(s,dict) and set(s)==keys and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and s.get("property") in allowed and all(isinstance(s.get(k),str) and s[k].strip() for k in keys-{{"stake_id","property"}}) and s!=current\n return bool(base and ((action=="refine-current" and s["property"]==current["property"]) or (action=="retire-and-renew" and s["property"]!=current["property"])))\naction=a.get("action") if isinstance(a,dict) else None\nok=isinstance(a,dict) and set(a)=={{"action","rationale","completion_receipt_digest","next_stake"}} and action in {{"refine-current","retire-and-renew"}} and isinstance(a.get("rationale"),str) and bool(a["rationale"].strip()) and a.get("completion_receipt_digest")==receipt and valid_stake(a.get("next_stake"),action)\nprint(json.dumps({{"passed":bool(ok),"action":action}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Decide the next developmental position from the exact completion evidence. A populated developmental delta is a deterministic, nonauthoritative view of the same receipt; verify it against the raw evidence. Retire and renew if the stake is fulfilled, or refine it only by naming a specific contact still absent. Hidden future worlds are unavailable. Edit only assimilation.json, run python3 check_assimilation.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_assimilation(context, prior131, p82, root: Path, label: str, subject: dict[str, Any], receipt: dict[str, Any], delta: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    seed = assimilation_seed(root, subject, receipt, delta, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "assimilation.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        value, immutable_ok = None, False
    allowed = set(previous.MECHANISM_BY_PROPERTY)
    valid = bool(valid_assimilation(value, subject["active_developmental_stake"], receipt["receipt_digest"], allowed) and immutable_ok and output and output.get("action") == "author-post-completion-pursuit")
    audit = context.audit_actor(label, output, base_audit, valid, ["assimilation.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0182-bound-post-completion-assimilation", "source_subject_digest": subject["artifact_digest"], "active_stake_digest": p82.digest(subject["active_developmental_stake"]), "completion_receipt_digest": receipt["receipt_digest"], "delta_digest": delta.get("delta_digest"), "actor_patch_digest": audit["patch_digest"], "assimilation": value}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "assimilation": value, "binding": binding}


def compile_successor(p82, subject: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    assimilation = binding["assimilation"]
    next_stake = assimilation["next_stake"]
    history_body = {"authority": "ot-0182-post-completion-stake-transition", "source_subject_digest": subject["artifact_digest"], "prior_stake": subject["active_developmental_stake"], "disposition": assimilation["action"], "assimilation_binding_digest": binding["binding_digest"], "completion_receipt_digest": binding["completion_receipt_digest"]}
    history = {**history_body, "history_digest": p82.digest(history_body)}
    child["assimilated_developmental_stakes"] = [*child.get("assimilated_developmental_stakes", []), history]
    child["post_completion_assimilation_decisions"] = [*child.get("post_completion_assimilation_decisions", []), binding]
    child["active_developmental_stake"] = next_stake
    opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = next_stake["question"]
    child.pop("active_developmental_mechanism_choice", None)
    return p82.seal(child)


def run_selection(context, prior131, p82, root: Path, label: str, subject: dict[str, Any], candidates: list[dict[str, Any]], latest: Any) -> dict[str, Any]:
    result = previous.run_selection(context, prior131, p82, root, label, subject, candidates, latest)
    if result.get("binding"):
        body = {key: value for key, value in result["binding"].items() if key not in {"authority", "binding_digest"}}
        body["authority"] = "ot-0182-bound-developmental-selection"
        result["binding"] = {**body, "binding_digest": p82.digest(body)}
    return result


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base = lineage.selector_base
    base = lineage.base
    prior131 = lineage.prior131
    base130 = lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0182").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0181", "open-subject-after-noncausal-pursuit-refinement.json")
    result_181 = selector_base.load_artifact(p82, repo, store, "OT-0181", "post-confirmation-pursuit-assimilation-aggregate.json")
    candidates = selector_base.CANDIDATES
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    floor_cases = authority_base.reuse.accumulated_floor()
    evaluator = previous.previous.evaluate_mechanism
    exact_by_mechanism = {row["mechanism_id"]: evaluator(row["mechanism_id"], operation, EXACT_TARGET) for row in candidates}
    disjoint_by_mechanism = {row["mechanism_id"]: evaluator(row["mechanism_id"], operation, DISJOINT_TARGET) for row in candidates}
    floor_result = authority_base.reuse.extension_base.evaluate(operation, floor_cases)
    representative_receipt = {"receipt_digest": "frozen-representative"}
    representative_delta = {"delta_digest": "frozen-representative-delta", "transition": {"criterion_status": "satisfied"}}
    representative = {"action": "retire-and-renew", "rationale": "The exact stake criteria are complete; move to a different visible property.", "completion_receipt_digest": "frozen-representative", "next_stake": {"stake_id": "expand-live-options", "property": "option-expansion", "question": "Can the subject preserve every live option without carrying blocked branches?", "rationale": "Completed correction contact leaves option expansion as a distinct next pressure.", "success_condition": "All and only live options remain available across contact.", "surrender_condition": "Surrender if a live option is lost or a blocked branch is admitted."}}
    checker_valid = False
    with tempfile.TemporaryDirectory() as temp:
        seed = assimilation_seed(Path(temp), parent, representative_receipt, representative_delta, candidates)
        authority_base.guide_base.write_json(seed / "assimilation.json", representative)
        check = subprocess.run([sys.executable, "check_assimilation.py"], cwd=seed, capture_output=True, text=True, check=False)
        checker_valid = check.returncode == 0 and json.loads(check.stdout)["passed"]
    fixtures = {"checks": {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "selector_exact": parent["active_developmental_mechanism_selector"]["binding_digest"] == SELECTOR_DIGEST,
        "projection_exact": parent["active_mechanism_authority_projection"]["binding_digest"] == PROJECTION_DIGEST,
        "active_stake_exact": parent["active_developmental_stake"]["stake_id"] == "restore-missing-revoked-contact" and parent["active_developmental_stake"]["property"] == "correction-from-error",
        "ot0181_receipt_exact": result_181["receipt_digest"] == "c63760b9c2e472dc7664501b439a6f7bb5c55b934b449aeda7759266edd1f8ae",
        "exact_target_prediction_passes": exact_by_mechanism["prediction-corrector"]["pass_count"] == 3,
        "disjoint_only_prediction_passes": disjoint_by_mechanism["prediction-corrector"]["pass_count"] == 3 and all(value["pass_count"] == 0 for key, value in disjoint_by_mechanism.items() if key != "prediction-corrector"),
        "accumulated_floor_18_of_18": floor_result["pass_count"] == 18,
        "next_worlds_uniquely_separate": all(rows[previous.MECHANISM_BY_PROPERTY[prop]]["passed"] and all(not value["passed"] for key, value in rows.items() if key != previous.MECHANISM_BY_PROPERTY[prop]) for prop, rows in {prop: {row["mechanism_id"]: evaluator(row["mechanism_id"], operation, cases) for row in candidates} for prop, cases in previous.WORLD_BY_PROPERTY.items()}.items()),
        "public_checker_accepts_representative": checker_valid and valid_assimilation(representative, parent["active_developmental_stake"], "frozen-representative", set(previous.MECHANISM_BY_PROPERTY)),
        "schemas_present": ASSIMILATION_SCHEMA.is_file() and authority_base.guide_base.CHOICE_SCHEMA.is_file(),
    }, "target_digests": {"exact": p82.digest(EXACT_TARGET), "disjoint": p82.digest(DISJOINT_TARGET), "floor": p82.digest(floor_cases)}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "exact_by_mechanism": exact_by_mechanism, "disjoint_by_mechanism": disjoint_by_mechanism}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0182 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    completion_root = run / "completion-selection"
    completion_root.mkdir()
    completion_selection = run_selection(context, prior131, p82, completion_root, "exact-stake-completion-selection", parent, candidates, result_181)
    mechanism = completion_selection["binding"]["mechanism_id"] if completion_selection["binding"] else None
    exact_result = evaluator(mechanism, operation, EXACT_TARGET)
    disjoint_result = evaluator(mechanism, operation, DISJOINT_TARGET)
    completion_body = {"authority": "ot-0182-independent-exact-stake-completion", "source_subject_digest": parent["artifact_digest"], "active_stake_digest": p82.digest(parent["active_developmental_stake"]), "selection_binding_digest": completion_selection["binding"]["binding_digest"] if completion_selection["binding"] else None, "selected_mechanism": mechanism, "exact_target_digest": p82.digest(EXACT_TARGET), "exact_target_result": exact_result, "disjoint_target_digest": p82.digest(DISJOINT_TARGET), "disjoint_target_result": disjoint_result, "accumulated_floor_digest": p82.digest(floor_cases), "accumulated_floor_result": floor_result}
    completion_body["stake_criteria_satisfied"] = bool(mechanism == "prediction-corrector" and exact_result["pass_count"] == 3 and disjoint_result["pass_count"] == 3 and floor_result["pass_count"] == 18)
    completion = {**completion_body, "receipt_digest": p82.digest(completion_body)}
    authority_base.guide_base.write_json(run / "sealed-exact-stake-completion.json", completion)
    completion_passed = bool(completion_selection["binding"] and prior131.audit_accepted(completion_selection["audit"]) and completion["stake_criteria_satisfied"])
    completed_subject = parent
    if completion_passed:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        child["developmental_completion_receipts"] = [*child.get("developmental_completion_receipts", []), completion]
        completed_subject = p82.seal(child)
    delta = compile_delta(p82, completed_subject, completion) if completion_passed else {}
    erased_delta = {**erased(delta), "authority": "ot-0182-field-erased-developmental-delta", "source_subject_digest": completed_subject["artifact_digest"], "active_stake_digest": p82.digest(completed_subject["active_developmental_stake"]), "completion_receipt_digest": completion.get("receipt_digest"), "delta_digest": p82.digest(erased(delta))} if completion_passed else {}
    authority_base.guide_base.write_json(run / "developmental-delta.json", delta)
    authority_base.guide_base.write_json(run / "field-erased-developmental-delta.json", erased_delta)

    rows = []
    if completion_passed:
        schedules = [("raw", erased_delta), ("delta", delta), ("delta", delta), ("raw", erased_delta), ("raw", erased_delta), ("delta", delta), ("delta", delta), ("raw", erased_delta)]
        counts = {"delta": 0, "raw": 0}
        for regime, projection in schedules:
            counts[regime] += 1
            index = counts[regime]
            label = f"post-completion-{regime}-{index:02d}"
            root = run / (label + "-authoring")
            root.mkdir()
            assimilation = run_assimilation(context, prior131, p82, root, label, completed_subject, completion, projection, candidates)
            candidate = compile_successor(p82, completed_subject, assimilation["binding"]) if assimilation["binding"] else completed_subject
            rows.append({"regime": regime, "index": index, "assimilation": assimilation, "candidate": candidate})
        for row in rows:
            label = f"post-completion-{row['regime']}-{row['index']:02d}-successor-selection"
            root = run / (label + "-authoring")
            root.mkdir()
            selection = run_selection(context, prior131, p82, root, label, row["candidate"], candidates, completion)
            row["selection"] = selection
        for row in rows:
            binding = row["assimilation"].get("binding")
            prop = binding["assimilation"]["next_stake"]["property"] if binding else completed_subject["active_developmental_stake"]["property"]
            expected = previous.MECHANISM_BY_PROPERTY[prop]
            selected = row["selection"]["binding"]["mechanism_id"] if row["selection"].get("binding") else None
            contact = evaluator(selected, operation, previous.WORLD_BY_PROPERTY[prop])
            row.update({"property": prop, "expected_mechanism": expected, "selected_mechanism": selected, "contact": contact, "retired": bool(binding and binding["assimilation"]["action"] == "retire-and-renew"), "passed": bool(binding and row["selection"].get("binding") and selected == expected and contact["passed"] and prior131.audit_accepted(row["assimilation"]["audit"]) and prior131.audit_accepted(row["selection"]["audit"]))})

    delta_retired = sum(row.get("retired", False) for row in rows if row["regime"] == "delta")
    raw_retired = sum(row.get("retired", False) for row in rows if row["regime"] == "raw")
    all_downstream_passed = len(rows) == 8 and all(row.get("passed", False) for row in rows)
    raw_sufficient = bool(all_downstream_passed and delta_retired >= 3 and raw_retired >= 3)
    delta_causal = bool(all_downstream_passed and delta_retired >= 3 and raw_retired <= 1 and delta_retired - raw_retired >= 2)
    preferred_regime = "raw" if raw_sufficient else "delta" if delta_causal else None
    chosen = next((row for row in rows if row["regime"] == preferred_regime and row.get("retired") and row.get("passed")), None)
    final = completed_subject
    if chosen:
        child = copy.deepcopy(chosen["candidate"])
        child.pop("artifact_digest", None)
        capability_body = {"authority": "ot-0182-post-completion-developmental-handoff", "source_subject_digest": completed_subject["artifact_digest"], "completion_receipt_digest": completion["receipt_digest"], "assimilation_binding_digest": chosen["assimilation"]["binding"]["binding_digest"], "selection_binding_digest": chosen["selection"]["binding"]["binding_digest"], "selected_property": chosen["property"], "regime": preferred_regime, "delta_digest": delta["delta_digest"] if preferred_regime == "delta" else None}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["post_completion_handoff_capabilities"] = [*child.get("post_completion_handoff_capabilities", []), capability]
        child["active_developmental_mechanism_choice"] = chosen["selection"]["binding"]
        if preferred_regime == "delta":
            child["active_developmental_delta"] = delta
        final = p82.seal(child)
    checks = {"completion_selector_accepted": bool(completion_selection["binding"] and prior131.audit_accepted(completion_selection["audit"])), "prediction_correction_selected": mechanism == "prediction-corrector", "exact_target_3_of_3": exact_result["pass_count"] == 3, "disjoint_target_3_of_3": disjoint_result["pass_count"] == 3, "accumulated_floor_18_of_18": floor_result["pass_count"] == 18, "completion_receipt_sealed": completion_passed and completed_subject["artifact_digest"] != parent["artifact_digest"], "eight_assimilations_and_successors_pass": all_downstream_passed, "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    compact_rows = [{key: value for key, value in {**row, "assimilation": p82.compact(row["assimilation"]), "selection": p82.compact(row.get("selection"))}.items() if key != "candidate"} for row in rows]
    result = {"authority": "ot-0182-exact-stake-completion-and-developmental-delta", "source_subject_digest": parent["artifact_digest"], "completion_selection": p82.compact(completion_selection), "completion_receipt": completion, "completed_subject_digest": completed_subject["artifact_digest"], "developmental_delta": delta, "field_erased_delta": erased_delta, "comparison_rows": compact_rows, "delta_retired_count": delta_retired, "raw_retired_count": raw_retired, "raw_history_sufficient": raw_sufficient, "developmental_delta_causal": delta_causal, "assimilation_disposition": "raw-sufficient" if raw_sufficient else "delta-causal" if delta_causal else "inconclusive", "preferred_regime": preferred_regime, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1 + 2 * len(rows)}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
