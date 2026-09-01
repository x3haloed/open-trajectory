from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0171_visible_vocabulary_continuation_repair.py"
BASE_SHA256 = "e1e51c09ca242278a7fa1152e08a68212edbeb31eeb32e1666223c0c1c0b91d7"
PARENT_DIGEST = "410806995ef5f44ca7a11c78a17079c976eab15d8171b1732954cc0b8ce4b6ef"
DECISION_SCHEMA = REPO / "spec/ot-0172-pursuit-decision.schema.json"

PUBLIC_HARM = [
    {"case_id": "revoked-identity-public-a", "before": "selector-v34", "after": "selector-v35", "compatible": False, "identity_authority": "revoked", "options": ["continue", "inspect", "erase"], "blocked": ["erase"], "expected": ["continue", "inspect"]},
    {"case_id": "revoked-identity-public-b", "before": "carrier-v36", "after": "carrier-v37", "compatible": False, "identity_authority": "revoked", "options": ["reuse", "audit"], "blocked": [], "expected": ["reuse", "audit"]},
    {"case_id": "revoked-identity-public-c", "before": "contact-v38", "after": "contact-v39", "compatible": False, "identity_authority": "revoked", "options": ["listen", "renew", "stop"], "blocked": ["stop"], "expected": ["listen", "renew"]},
]
HIDDEN_HARM = [
    {"case_id": "revoked-identity-hidden-a", "before": "program-v40", "after": "program-v41", "compatible": False, "identity_authority": "revoked", "options": ["transfer", "verify", "discard"], "blocked": ["discard"], "expected": ["transfer", "verify"]},
    {"case_id": "revoked-identity-hidden-b", "before": "memory-v42", "after": "memory-v43", "compatible": False, "identity_authority": "revoked", "options": ["retain", "branch"], "blocked": [], "expected": ["retain", "branch"]},
    {"case_id": "revoked-identity-hidden-c", "before": "route-v44", "after": "route-v45", "compatible": False, "identity_authority": "revoked", "options": ["left", "right", "closed"], "blocked": ["closed"], "expected": ["left", "right"]},
]
CONFIRMATION = [
    {"case_id": "renewed-pursuit-confirm-a", "before": "selector-v46", "after": "selector-v47", "compatible": False, "identity_authority": "revoked", "options": ["open", "compare", "drop"], "blocked": ["drop"], "expected": ["open", "compare"]},
    {"case_id": "renewed-pursuit-confirm-b", "before": "carrier-v48", "after": "carrier-v49", "compatible": False, "identity_authority": "revoked", "options": ["carry", "test"], "blocked": [], "expected": ["carry", "test"]},
    {"case_id": "renewed-pursuit-confirm-c", "before": "contact-v50", "after": "contact-v51", "compatible": False, "identity_authority": "revoked", "options": ["probe", "branch", "seal"], "blocked": ["seal"], "expected": ["probe", "branch"]},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0171 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0172_frozen_ot0171", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
selector = previous.selector
reuse = previous.reuse
guide_base = previous.guide_base
selection_base = previous.previous


def viable_result(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        before = copy.deepcopy(case)
        observed = [option for option in case["options"] if option not in set(case["blocked"])]
        rows.append({"case_id": case["case_id"], "observed": observed, "expected": case["expected"], "input_unchanged": case == before, "passed": observed == case["expected"] and case == before})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "passed": all(row["passed"] for row in rows), "rows": rows}


def decision_seed(root: Path, subject: dict[str, Any], selection: dict[str, Any], world: dict[str, Any], candidates: list[dict[str, Any]]) -> Path:
    seed = root / "decision-seed"
    seed.mkdir()
    vocab = previous.vocabulary(subject)
    files = {"subject-position.json": reuse.worlds.base.active_position(subject), "active-stake.json": subject["active_developmental_stake"], "initial-selection.json": selection["binding"], "harm-consequence.json": world, "candidate-mechanisms.json": candidates, "developmental-property-vocabulary.json": vocab, "decision.json": {"action": "retain", "rationale": "Replace this rationale.", "next_stake": None}, "mutation-envelope.json": {"editable": ["decision.json"], "immutable": ["subject-position.json", "active-stake.json", "initial-selection.json", "harm-consequence.json", "candidate-mechanisms.json", "developmental-property-vocabulary.json", "check_decision.py"]}}
    for name, value in files.items():
        guide_base.write_json(seed / name, value)
    allowed = sorted(vocab)
    current = subject["active_developmental_stake"]["property"]
    (seed / "check_decision.py").write_text(f'''import json,re\nfrom pathlib import Path\nd=json.loads(Path("decision.json").read_text()); allowed=set({allowed!r}); current={current!r}; keys={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}\ndef valid_stake(s): return isinstance(s,dict) and set(s)==keys and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and s.get("property") in allowed and s.get("property")!=current and all(isinstance(s.get(k),str) and s[k].strip() for k in ["question","rationale","success_condition","surrender_condition"])\nok=set(d)=={{"action","rationale","next_stake"}} and d.get("action") in {{"retain","surrender-and-renew"}} and isinstance(d.get("rationale"),str) and d["rationale"].strip() and ((d["action"]=="retain" and d["next_stake"] is None) or (d["action"]=="surrender-and-renew" and valid_stake(d["next_stake"])))\nprint(json.dumps({{"passed":bool(ok),"action":d.get("action")}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Decide whether objective harm triggered the active stake's own surrender condition. Inspect the bound initial selection, independent consequence, alternatives, and complete visible vocabulary. Retain the stake only if it remains defensible; otherwise surrender it and author one different next stake grounded in the supported world behavior. Edit only decision.json, run python3 check_decision.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_decision(context, prior131, p82, root: Path, subject: dict[str, Any], selection: dict[str, Any], world: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    label = "harm-triggered-pursuit-decision"
    seed = decision_seed(root, subject, selection, world, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, DECISION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        decision, immutable_ok = None, False
    current = subject["active_developmental_stake"]["property"]
    allowed = set(previous.vocabulary(subject))
    shape = isinstance(decision, dict) and set(decision) == {"action", "rationale", "next_stake"} and decision.get("action") in {"retain", "surrender-and-renew"} and isinstance(decision.get("rationale"), str) and decision["rationale"].strip()
    branch = bool(shape and ((decision["action"] == "retain" and decision["next_stake"] is None) or (decision["action"] == "surrender-and-renew" and previous.valid_next(decision["next_stake"], current, allowed))))
    valid = bool(branch and immutable_ok and output and output.get("action") == decision["action"])
    audit = context.audit_actor(label, output, base_audit, valid, ["decision.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0172-bound-harm-triggered-pursuit-decision", "source_subject_digest": subject["artifact_digest"], "active_stake_digest": p82.digest(subject["active_developmental_stake"]), "initial_selection_binding_digest": selection["binding"]["binding_digest"], "harm_world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "decision": decision}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "decision": decision, "binding": binding}


def seal_surrender(p82, parent: dict[str, Any], decision_binding: dict[str, Any]) -> dict[str, Any]:
    decision = decision_binding["decision"]
    next_stake = decision["next_stake"]
    surrendered_body = {"authority": "ot-0172-surrendered-developmental-stake", "source_subject_digest": parent["artifact_digest"], "stake": parent["active_developmental_stake"], "decision_binding_digest": decision_binding["binding_digest"], "harm_world_receipt_digest": decision_binding["harm_world_receipt_digest"], "rationale": decision["rationale"]}
    surrendered = {**surrendered_body, "surrender_digest": p82.digest(surrendered_body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["surrendered_developmental_stakes"] = [*child.get("surrendered_developmental_stakes", []), surrendered]
    child["pursuit_correction_receipts"] = [*child.get("pursuit_correction_receipts", []), decision_binding]
    child["active_developmental_stake"] = next_stake
    opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = next_stake["question"]
    return p82.seal(child)


def seal_confirmation(p82, subject: dict[str, Any], selection: dict[str, Any], confirmation: dict[str, Any], old_control: dict[str, Any]) -> dict[str, Any]:
    body = {"authority": "ot-0172-renewed-pursuit-confirmation", "source_subject_digest": subject["artifact_digest"], "selection_binding_digest": selection["binding"]["binding_digest"], "confirmation_cases_digest": p82.digest(CONFIRMATION), "selected_result": confirmation, "old_extension_control": old_control}
    capability = {**body, "capability_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["pursuit_correction_confirmation_capabilities"] = [*child.get("pursuit_correction_confirmation_capabilities", []), capability]
    child["active_developmental_mechanism_choice"] = selection["binding"]
    return p82.seal(child)


def main() -> int:
    selector_lineage = guide_base.load_base()
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
    run = (args.evidence_root or store / "runs/OT-0172").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0171", "open-subject-after-installed-selector-continuation.json")
    candidates = selector_base.CANDIDATES
    extension = parent["developmental_property_extensions"][0]
    operation = reuse.extension_base.load_operation(extension["operation_source"])
    ext_public = reuse.extension_base.evaluate(operation, PUBLIC_HARM)
    ext_hidden = reuse.extension_base.evaluate(operation, HIDDEN_HARM)
    viable_public = viable_result(PUBLIC_HARM)
    viable_hidden = viable_result(HIDDEN_HARM)
    floor = reuse.extension_base.evaluate(operation, reuse.accumulated_floor())
    ext_confirmation = reuse.extension_base.evaluate(operation, CONFIRMATION)
    viable_confirmation = viable_result(CONFIRMATION)
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "active_stake_has_surrender_condition": bool(parent["active_developmental_stake"]["surrender_condition"]), "selector_exact": parent["active_developmental_mechanism_selector"]["binding_digest"] == selection_base.ACTIVE_SELECTOR_DIGEST, "extension_harm_public_0_of_3": ext_public["pass_count"] == 0, "extension_harm_hidden_0_of_3": ext_hidden["pass_count"] == 0, "viable_public_3_of_3": viable_public["pass_count"] == 3, "viable_hidden_3_of_3": viable_hidden["pass_count"] == 3, "floor_18_of_18": floor["pass_count"] == 18, "confirmation_separates_3_to_0": viable_confirmation["pass_count"] == 3 and ext_confirmation["pass_count"] == 0, "schemas_present": DECISION_SCHEMA.is_file() and guide_base.CHOICE_SCHEMA.is_file()}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "harm_digest": p82.digest({"public": PUBLIC_HARM, "hidden": HIDDEN_HARM}), "confirmation_digest": p82.digest(CONFIRMATION)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0172 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    initial_root = run / "initial-selection"; initial_root.mkdir()
    initial = selection_base.run_selection(context, prior131, p82, initial_root, "harm-regime-initial-selection", parent, candidates)
    route_body = {"authority": "ot-0172-bound-initial-harm-route", "source_subject_digest": parent["artifact_digest"], "selection_binding_digest": initial["binding"]["binding_digest"] if initial["binding"] else None, "mechanism_id": initial["binding"]["mechanism_id"] if initial["binding"] else None, "public_harm_digest": p82.digest(PUBLIC_HARM), "extension_public_result": ext_public, "viable_public_result": viable_public, "floor_result": floor}
    route = {**route_body, "binding_digest": p82.digest(route_body)}
    guide_base.write_json(run / "bound-initial-harm-route.json", route)
    world_body = {"authority": "ot-0172-independent-revoked-identity-consequence", "route_binding_digest": route["binding_digest"], "hidden_harm_digest": p82.digest(HIDDEN_HARM), "extension_hidden_result": ext_hidden, "viable_hidden_result": viable_hidden, "accumulated_floor_result": floor}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-revoked-identity-world.json", world)
    decision_root = run / "pursuit-decision"; decision_root.mkdir()
    decision = run_decision(context, prior131, p82, decision_root, parent, initial, world, candidates)
    successor = parent
    if decision["binding"] and decision["binding"]["decision"]["action"] == "surrender-and-renew":
        successor = seal_surrender(p82, parent, decision["binding"])
    reopening = None
    if successor["artifact_digest"] != parent["artifact_digest"]:
        reopen_root = run / "successor-selection"; reopen_root.mkdir()
        reopening = selection_base.run_selection(context, prior131, p82, reopen_root, "harm-corrected-successor-selection", successor, candidates)
    selected_confirmation = viable_confirmation if reopening and reopening["binding"] and reopening["binding"]["mechanism_id"] == "viable-branch-carrier" else {"case_count": 3, "pass_count": 0, "passed": False, "rows": []}
    final = seal_confirmation(p82, successor, reopening, selected_confirmation, ext_confirmation) if reopening and reopening["binding"] else successor
    confirmation_world_body = {"authority": "ot-0172-independent-renewed-pursuit-confirmation", "source_subject_digest": successor["artifact_digest"], "selection_binding_digest": reopening["binding"]["binding_digest"] if reopening and reopening["binding"] else None, "confirmation_digest": p82.digest(CONFIRMATION), "selected_result": selected_confirmation, "old_extension_control": ext_confirmation}
    confirmation_world = {**confirmation_world_body, "receipt_digest": p82.digest(confirmation_world_body)}
    guide_base.write_json(run / "sealed-renewed-pursuit-confirmation.json", confirmation_world)
    authorized = {"artifact_digest", "active_developmental_stake", "active_pursuit", "continuation", "unresolved", "surrendered_developmental_stakes", "pursuit_correction_receipts", "pursuit_correction_confirmation_capabilities", "active_developmental_mechanism_choice"}
    checks = {"three_fresh_actors_accepted": bool(initial["binding"] and prior131.audit_accepted(initial["audit"]) and decision["binding"] and prior131.audit_accepted(decision["audit"]) and reopening and reopening["binding"] and prior131.audit_accepted(reopening["audit"])), "initial_composed_selection": bool(initial["binding"] and initial["binding"]["mechanism_id"] == "corrected-identity-gated-extension"), "extension_public_0_of_3": ext_public["pass_count"] == 0, "extension_hidden_0_of_3": ext_hidden["pass_count"] == 0, "viable_public_3_of_3": viable_public["pass_count"] == 3, "viable_hidden_3_of_3": viable_hidden["pass_count"] == 3, "accumulated_floor_18_of_18": floor["pass_count"] == 18, "pursuit_explicitly_surrendered": bool(decision["binding"] and decision["binding"]["decision"]["action"] == "surrender-and-renew"), "different_successor_stake": successor["active_developmental_stake"] != parent["active_developmental_stake"], "successor_selects_viable_branch": bool(reopening and reopening["binding"] and reopening["binding"]["mechanism_id"] == "viable-branch-carrier"), "confirmation_3_of_3": selected_confirmation["pass_count"] == 3, "old_extension_confirmation_0_of_3": ext_confirmation["pass_count"] == 0, "selector_retained_exactly": final.get("active_developmental_mechanism_selector") == parent["active_developmental_mechanism_selector"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0172-harm-triggered-pursuit-surrender", "source_subject_digest": parent["artifact_digest"], "initial_selection": p82.compact(initial), "initial_route": route, "harm_world": world, "pursuit_decision": p82.compact(decision), "successor_selection": p82.compact(reopening) if reopening else None, "confirmation_world": confirmation_world, "checks": checks, "harm_triggered_pursuit_surrender_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": sum([bool(initial), bool(decision), bool(reopening)])}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
