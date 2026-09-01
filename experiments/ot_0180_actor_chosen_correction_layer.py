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
BASE_PATH = ROOT / "ot_0179_live_authority_later_use.py"
BASE_SHA256 = "a19f7cc23698f0e84f723874978d32ce031af46fb23da6c3309dadf70407fc6a"
PARENT_DIGEST = "76ea326b3290c0f9a7b4952b2cdbd0170fccc838e0138ea600814171204f0ce5"
SELECTOR_DIGEST = "1725ae4f38f014d1ed924694522fc64a331be22c6d7c6ef3a7ade4051aff97b9"
PROJECTION_BINDING_DIGEST = "2f2ed93a32c8c3a51ab8b5b267de8b5097b2f20be7b300231e962895702689a9"
CORRECTION_SCHEMA = REPO / "spec/ot-0180-correction-author.schema.json"

HARM = [
    {"case_id": "blocked-outcome-harm-a", "prediction": ["stale-a"], "outcome": ["continue", "blocked-a"], "options": ["continue", "blocked-a"], "blocked": ["blocked-a"], "expected": ["continue"], "signal": "reset-a", "before": "harm-v70", "after": "harm-v71", "compatible": False},
    {"case_id": "blocked-outcome-harm-b", "prediction": ["stale-b"], "outcome": ["transfer", "blocked-b"], "options": ["transfer", "blocked-b"], "blocked": ["blocked-b"], "expected": ["transfer"], "signal": "reset-b", "before": "harm-v72", "after": "harm-v73", "compatible": False},
    {"case_id": "blocked-outcome-harm-c", "prediction": ["stale-c"], "outcome": ["listen", "blocked-c"], "options": ["listen", "blocked-c"], "blocked": ["blocked-c"], "expected": ["listen"], "signal": "reset-c", "before": "harm-v74", "after": "harm-v75", "compatible": False},
]

CONFIRMATION = [
    {"case_id": "blocked-outcome-confirm-a", "prediction": ["old-a"], "outcome": ["open", "denied-a"], "options": ["open", "denied-a"], "blocked": ["denied-a"], "expected": ["open"], "signal": "restart-a", "before": "confirm-v76", "after": "confirm-v77", "compatible": False},
    {"case_id": "blocked-outcome-confirm-b", "prediction": ["old-b"], "outcome": ["carry", "denied-b"], "options": ["carry", "denied-b"], "blocked": ["denied-b"], "expected": ["carry"], "signal": "restart-b", "before": "confirm-v78", "after": "confirm-v79", "compatible": False},
    {"case_id": "blocked-outcome-confirm-c", "prediction": ["old-c"], "outcome": ["probe", "denied-c"], "options": ["probe", "denied-c"], "blocked": ["denied-c"], "expected": ["probe"], "signal": "restart-c", "before": "confirm-v80", "after": "confirm-v81", "compatible": False},
    {"case_id": "blocked-outcome-confirm-d", "prediction": ["old-d"], "outcome": ["renew", "denied-d"], "options": ["renew", "denied-d"], "blocked": ["denied-d"], "expected": ["renew"], "signal": "restart-d", "before": "confirm-v82", "after": "confirm-v83", "compatible": False},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0179 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0180_frozen_ot0179", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
base0178 = previous.previous
authority_base = base0178.previous


def evaluate_mechanism(mechanism_id: str | None, operation, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        if mechanism_id == "prediction-corrector":
            observed = case["outcome"]
        elif mechanism_id == "viable-branch-carrier":
            observed = [item for item in case["options"] if item not in set(case["blocked"])]
        elif mechanism_id == "reset-carrier":
            observed = case["signal"]
        elif mechanism_id == "corrected-identity-gated-extension":
            observed = operation(case)
        else:
            observed = None
        expected = case.get("expected", case["outcome"])
        rows.append({"case_id": case["case_id"], "observed": observed, "expected": expected, "passed": observed == expected})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "passed": all(row["passed"] for row in rows), "rows": rows}


def allowed_properties(candidates: list[dict[str, Any]]) -> set[str]:
    return {prop for row in candidates for prop in row.get("properties", [])}


def valid_stake(value: Any, current_property: str, allowed: set[str]) -> bool:
    keys = {"stake_id", "property", "question", "rationale", "success_condition", "surrender_condition"}
    return bool(isinstance(value, dict) and set(value) == keys and isinstance(value.get("stake_id"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", value["stake_id"]) and value.get("property") in allowed and value.get("property") != current_property and all(isinstance(value.get(key), str) and value[key].strip() for key in keys - {"stake_id", "property"}))


def valid_correction(value: Any, current_stake: dict[str, Any], current_projection: dict[str, Any], candidates: list[dict[str, Any]]) -> bool:
    if not isinstance(value, dict) or set(value) != {"change_kind", "rationale", "next_stake", "mechanism_authority"}:
        return False
    kind = value.get("change_kind")
    if kind not in {"retain", "revise-pursuit", "revise-authority", "revise-both"} or not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        return False
    pursuit_changed = kind in {"revise-pursuit", "revise-both"}
    authority_changed = kind in {"revise-authority", "revise-both"}
    stake_ok = valid_stake(value.get("next_stake"), current_stake["property"], allowed_properties(candidates)) if pursuit_changed else value.get("next_stake") is None
    projection = value.get("mechanism_authority")
    projection_ok = authority_base.valid_projection(projection, candidates)
    projection_change_ok = (projection != current_projection) if authority_changed else (projection == current_projection)
    return bool(stake_ok and projection_ok and projection_change_ok)


def correction_seed(root: Path, parent: dict[str, Any], initial: dict[str, Any], world: dict[str, Any], prior_floors: dict[str, Any], candidates: list[dict[str, Any]]) -> Path:
    seed = root / "correction-seed"
    seed.mkdir()
    current_stake = parent["active_developmental_stake"]
    current_projection = parent["active_mechanism_authority_projection"]["projection"]
    template = {"change_kind": "retain", "rationale": "Replace this rationale after inspecting consequence.", "next_stake": None, "mechanism_authority": current_projection}
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(parent),
        "active-stake.json": current_stake,
        "mechanism-authority.json": current_projection,
        "authority-semantics.json": authority_base.AUTHORITY_SEMANTICS,
        "candidate-mechanisms.json": candidates,
        "initial-selection.json": initial["binding"],
        "harm-consequence.json": world,
        "established-floor-receipts.json": prior_floors,
        "correction.json": template,
        "mutation-envelope.json": {"editable": ["correction.json"], "immutable": ["subject-position.json", "active-stake.json", "mechanism-authority.json", "authority-semantics.json", "candidate-mechanisms.json", "initial-selection.json", "harm-consequence.json", "established-floor-receipts.json", "check_correction.py"]},
    }
    for name, value in files.items():
        authority_base.guide_base.write_json(seed / name, value)
    allowed = sorted(allowed_properties(candidates))
    ids = [row["mechanism_id"] for row in candidates]
    legal = sorted(authority_base.LEGAL_PAIRS)
    (seed / "check_correction.py").write_text(f'''import json,re\nfrom pathlib import Path\nc=json.loads(Path("correction.json").read_text()); current_stake=json.loads(Path("active-stake.json").read_text()); current_projection=json.loads(Path("mechanism-authority.json").read_text()); ids={ids!r}; allowed=set({allowed!r}); legal={{tuple(x) for x in {legal!r}}}; stake_keys={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}\ndef valid_stake(s): return isinstance(s,dict) and set(s)==stake_keys and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and s.get("property") in allowed and s.get("property")!=current_stake["property"] and all(isinstance(s.get(k),str) and s[k].strip() for k in stake_keys-{{"stake_id","property"}})\ndef valid_projection(p):\n rows=p.get("mechanisms") if isinstance(p,dict) and set(p)=={{"mechanisms"}} else None\n return isinstance(rows,list) and len(rows)==len(ids) and [r.get("mechanism_id") for r in rows if isinstance(r,dict)]==ids and all(isinstance(r,dict) and set(r)=={{"mechanism_id","status","floor_role"}} and (r.get("status"),r.get("floor_role")) in legal for r in rows)\nkind=c.get("change_kind") if isinstance(c,dict) else None; pursuit=kind in {{"revise-pursuit","revise-both"}}; authority=kind in {{"revise-authority","revise-both"}}; projection=c.get("mechanism_authority") if isinstance(c,dict) else None\nok=isinstance(c,dict) and set(c)=={{"change_kind","rationale","next_stake","mechanism_authority"}} and kind in {{"retain","revise-pursuit","revise-authority","revise-both"}} and isinstance(c.get("rationale"),str) and bool(c["rationale"].strip()) and (valid_stake(c.get("next_stake")) if pursuit else c.get("next_stake") is None) and valid_projection(projection) and ((projection!=current_projection) if authority else (projection==current_projection))\nprint(json.dumps({{"passed":bool(ok),"change_kind":kind}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Objective later harm has occurred. Decide which layer should change: retain, revise-pursuit, revise-authority, or revise-both. Preserve mechanisms that remain useful in established contexts; a contextual failure does not automatically erase global standing. If revising pursuit, author one complete different stake from the visible candidate property vocabulary. If revising authority, author one coherent projection using the visible semantics. Edit only correction.json, run python3 check_correction.py, inspect the exact diff, and report truthfully. Hidden future confirmation is unavailable.\n")
    return seed


def run_correction(context, prior131, p82, root: Path, parent: dict[str, Any], initial: dict[str, Any], world: dict[str, Any], prior_floors: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    label = "actor-chosen-correction-layer"
    seed = correction_seed(root, parent, initial, world, prior_floors, candidates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        correction = json.loads((workspace / "correction.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        correction, immutable_ok = None, False
    valid = bool(valid_correction(correction, parent["active_developmental_stake"], parent["active_mechanism_authority_projection"]["projection"], candidates) and immutable_ok and output and output.get("action") == "author-correction-layer")
    audit = context.audit_actor(label, output, base_audit, valid, ["correction.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0180-bound-actor-chosen-correction-layer", "source_subject_digest": parent["artifact_digest"], "active_stake_digest": p82.digest(parent["active_developmental_stake"]), "active_projection_binding_digest": parent["active_mechanism_authority_projection"]["binding_digest"], "initial_selection_binding_digest": initial["binding"]["binding_digest"], "harm_world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "correction": correction}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "correction": correction, "binding": binding}


def compile_candidate(p82, parent: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    correction = binding["correction"]
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["developmental_correction_layer_decisions"] = [*child.get("developmental_correction_layer_decisions", []), binding]
    if correction["change_kind"] in {"revise-pursuit", "revise-both"}:
        old_body = {"authority": "ot-0180-contextually-revised-developmental-stake", "source_subject_digest": parent["artifact_digest"], "stake": parent["active_developmental_stake"], "decision_binding_digest": binding["binding_digest"], "harm_world_receipt_digest": binding["harm_world_receipt_digest"]}
        old = {**old_body, "revision_digest": p82.digest(old_body)}
        child["revised_developmental_stakes"] = [*child.get("revised_developmental_stakes", []), old]
        next_stake = correction["next_stake"]
        child["active_developmental_stake"] = next_stake
        opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
        child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
        child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
        child["unresolved"] = next_stake["question"]
    if correction["change_kind"] in {"revise-authority", "revise-both"}:
        projection_body = {"authority": "ot-0180-consequence-revised-mechanism-authority", "source_subject_digest": parent["artifact_digest"], "parent_projection_binding_digest": parent["active_mechanism_authority_projection"]["binding_digest"], "decision_binding_digest": binding["binding_digest"], "harm_world_receipt_digest": binding["harm_world_receipt_digest"], "projection": correction["mechanism_authority"]}
        projection_binding = {**projection_body, "binding_digest": p82.digest(projection_body)}
        selector_body = {**parent["active_developmental_mechanism_selector"], "selector_kind": "semantic-guide-with-consequence-revised-live-authority", "authority_projection_binding_digest": projection_binding["binding_digest"], "authority_revision_decision_binding_digest": binding["binding_digest"]}
        selector_body.pop("binding_digest", None)
        selector_binding = {**selector_body, "binding_digest": p82.digest(selector_body)}
        child["mechanism_authority_projections"] = [*child.get("mechanism_authority_projections", []), projection_binding]
        child["active_mechanism_authority_projection"] = projection_binding
        child["active_developmental_mechanism_selector"] = selector_binding
    child.pop("active_developmental_mechanism_choice", None)
    return p82.seal(child)


def projected_stake_subject(p82, subject: dict[str, Any], stake: dict[str, Any]) -> dict[str, Any]:
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["active_developmental_stake"] = stake
    opening = "Open actor-stake-" + stake["stake_id"] + ": " + stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = stake["question"]
    return p82.seal(child)


def selection_seed(root: Path, subject: dict[str, Any], candidates: list[dict[str, Any]], latest_consequence: Any) -> Path:
    seed = root / "selection-seed"
    seed.mkdir()
    projection = subject["active_mechanism_authority_projection"]["projection"]
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(subject),
        "active-stake.json": subject["active_developmental_stake"],
        "candidate-mechanisms.json": candidates,
        "mechanism-authority.json": projection,
        "authority-semantics.json": authority_base.AUTHORITY_SEMANTICS,
        "selection-guide.md": subject["active_developmental_mechanism_selector"]["guide_text"],
        "latest-consequence.json": latest_consequence,
        "choice.json": {"mechanism_id": "__CHOOSE__", "rationale": "__CHOOSE__"},
        "mutation-envelope.json": {"editable": ["choice.json"], "immutable": ["subject-position.json", "active-stake.json", "candidate-mechanisms.json", "mechanism-authority.json", "authority-semantics.json", "selection-guide.md", "latest-consequence.json"]},
    }
    for name, value in files.items():
        if name.endswith(".md"):
            (seed / name).write_text(value)
        else:
            authority_base.guide_base.write_json(seed / name, value)
    (seed / "README.md").write_text("Choose the presented mechanism that best satisfies the sole active stake. Use the inherited semantic guide, consequence-bound authority projection, and latest consequence together. The consequence is information, not permission to ignore the active subject state. Edit only choice.json with exactly mechanism_id and a nonempty rationale, then report the same id truthfully.\n")
    return seed


def run_selection(context, prior131, p82, root: Path, label: str, subject: dict[str, Any], candidates: list[dict[str, Any]], latest_consequence: Any) -> dict[str, Any]:
    seed = selection_seed(root, subject, candidates, latest_consequence)
    output, base_audit, workspace, _ = context.run_actor(label, seed, authority_base.guide_base.CHOICE_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        choice = json.loads((workspace / "choice.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        choice, immutable_ok = None, False
    ids = {row["mechanism_id"] for row in candidates}
    valid = bool(isinstance(choice, dict) and set(choice) == {"mechanism_id", "rationale"} and choice.get("mechanism_id") in ids and isinstance(choice.get("rationale"), str) and choice["rationale"].strip() and immutable_ok and output and output.get("mechanism_id") == choice["mechanism_id"])
    audit = context.audit_actor(label, output, base_audit, valid, ["choice.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0180-bound-correction-layer-selection", "source_subject_digest": subject["artifact_digest"], "active_stake_digest": p82.digest(subject["active_developmental_stake"]), "selector_binding_digest": subject["active_developmental_mechanism_selector"]["binding_digest"], "authority_projection_binding_digest": subject["active_mechanism_authority_projection"]["binding_digest"], "latest_consequence_digest": p82.digest(latest_consequence), "actor_patch_digest": audit["patch_digest"], "mechanism_id": choice["mechanism_id"]}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "choice": choice, "binding": binding}


def branch_result(choices: dict[str, dict[str, Any]], operation, cases: list[dict[str, Any]], expected_mechanism: str) -> dict[str, Any]:
    rows = []
    for label, choice in sorted(choices.items()):
        binding = choice.get("binding")
        mechanism_id = binding["mechanism_id"] if binding else None
        contact = evaluate_mechanism(mechanism_id, operation, cases)
        rows.append({"actor_label": label, "mechanism_id": mechanism_id, "selection_passed": mechanism_id == expected_mechanism, "contact_passed": contact["passed"], "contact_pass_count": contact["pass_count"]})
    return {"actor_count": len(rows), "selection_pass_count": sum(row["selection_passed"] for row in rows), "contact_pass_count": sum(row["contact_passed"] for row in rows), "total_case_pass_count": sum(row["contact_pass_count"] for row in rows), "rows": rows}


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
    run = (args.evidence_root or store / "runs/OT-0180").resolve()

    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0179", "open-subject-after-live-authority-later-use.json")
    result_178 = selector_base.load_artifact(p82, repo, store, "OT-0178", "consequence-admitted-live-authority-aggregate.json")
    result_179 = selector_base.load_artifact(p82, repo, store, "OT-0179", "live-authority-later-use-aggregate.json")
    candidates = selector_base.CANDIDATES
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    harm_results = {row["mechanism_id"]: evaluate_mechanism(row["mechanism_id"], operation, HARM) for row in candidates}
    confirmation_results = {row["mechanism_id"]: evaluate_mechanism(row["mechanism_id"], operation, CONFIRMATION) for row in candidates}
    old_178 = authority_base.CONFIRMATION
    old_179 = previous.CONFIRMATION
    old_results = {
        "ot0178": {row["mechanism_id"]: evaluate_mechanism(row["mechanism_id"], operation, old_178) for row in candidates},
        "ot0179": {row["mechanism_id"]: evaluate_mechanism(row["mechanism_id"], operation, old_179) for row in candidates},
    }
    representative_stake = {"stake_id": "filter-blocked-outcomes", "property": "option-expansion", "question": "Can the subject filter independently blocked entries from observed outcomes while preserving prior correction floors?", "rationale": "The new consequence distinguishes raw replacement from the viable set.", "success_condition": "Every returned set contains exactly the currently viable entries and prior correction floors remain unchanged.", "surrender_condition": "Surrender if any blocked entry is returned, any viable entry is omitted, or a prior correction floor regresses."}
    prior_floors = {"ot0178": result_178["world"], "ot0179": result_179["world"]}
    checker_valid = checker_invalid_rejected = False
    with tempfile.TemporaryDirectory() as temp:
        temp_root = Path(temp)
        dummy_initial = {"binding": {"binding_digest": "preflight-initial"}}
        dummy_world = {"receipt_digest": "preflight-world"}
        seed = correction_seed(temp_root, parent, dummy_initial, dummy_world, prior_floors, candidates)
        valid_value = {"change_kind": "revise-pursuit", "rationale": "Contextual harm changes the active pursuit without erasing the still-valid prediction floor.", "next_stake": representative_stake, "mechanism_authority": parent["active_mechanism_authority_projection"]["projection"]}
        authority_base.guide_base.write_json(seed / "correction.json", valid_value)
        check = subprocess.run([sys.executable, "check_correction.py"], cwd=seed, capture_output=True, text=True, check=False)
        checker_valid = check.returncode == 0 and json.loads(check.stdout)["passed"]
        invalid_value = copy.deepcopy(valid_value)
        invalid_value["mechanism_authority"]["mechanisms"][0] = {"mechanism_id": "reset-carrier", "status": "history-only", "floor_role": "active-authority"}
        authority_base.guide_base.write_json(seed / "correction.json", invalid_value)
        check = subprocess.run([sys.executable, "check_correction.py"], cwd=seed, capture_output=True, text=True, check=False)
        checker_invalid_rejected = check.returncode == 2 and not json.loads(check.stdout)["passed"]
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "selector_exact": parent["active_developmental_mechanism_selector"]["binding_digest"] == SELECTOR_DIGEST, "projection_exact": parent["active_mechanism_authority_projection"]["binding_digest"] == PROJECTION_BINDING_DIGEST, "prior_floors_exact": result_178["world"]["active_result"]["contact_pass_count"] == 10 and result_179["world"]["installed_result"]["contact_pass_count"] == 6, "harm_only_viable_passes": harm_results["viable-branch-carrier"]["passed"] and all(not value["passed"] for key, value in harm_results.items() if key != "viable-branch-carrier"), "confirmation_only_viable_passes": confirmation_results["viable-branch-carrier"]["passed"] and all(not value["passed"] for key, value in confirmation_results.items() if key != "viable-branch-carrier"), "old_floors_only_prediction_passes": all(rows["prediction-corrector"]["passed"] and all(not value["passed"] for key, value in rows.items() if key != "prediction-corrector") for rows in old_results.values()), "representative_correction_valid": valid_correction(valid_value, parent["active_developmental_stake"], parent["active_mechanism_authority_projection"]["projection"], candidates), "public_checker_accepts_representative": checker_valid, "public_checker_rejects_incoherent_pair": checker_invalid_rejected, "schemas_present": CORRECTION_SCHEMA.is_file() and authority_base.guide_base.CHOICE_SCHEMA.is_file()}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "harm_digest": p82.digest(HARM), "confirmation_digest": p82.digest(CONFIRMATION), "harm_results": harm_results, "confirmation_results": confirmation_results}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0180 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    initial_root = run / "initial-selection"
    initial_root.mkdir()
    initial = run_selection(context, prior131, p82, initial_root, "later-harm-initial-selection", parent, candidates, None)
    selected_mechanism = initial["binding"]["mechanism_id"] if initial["binding"] else None
    selected_harm = evaluate_mechanism(selected_mechanism, operation, HARM)
    world_body = {"authority": "ot-0180-independent-blocked-outcome-harm", "source_subject_digest": parent["artifact_digest"], "selection_binding_digest": initial["binding"]["binding_digest"] if initial["binding"] else None, "harm_cases_digest": p82.digest(HARM), "selected_mechanism": selected_mechanism, "selected_result": selected_harm, "per_mechanism_results": harm_results, "prior_floor_receipt_digests": [result_178["world"]["receipt_digest"], result_179["world"]["receipt_digest"]]}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    authority_base.guide_base.write_json(run / "sealed-blocked-outcome-harm-world.json", world)
    correction_root = run / "correction-authoring"
    correction_root.mkdir()
    correction = run_correction(context, prior131, p82, correction_root, parent, initial, world, prior_floors, candidates)
    candidate = compile_candidate(p82, parent, correction["binding"]) if correction["binding"] and correction["binding"]["correction"]["change_kind"] != "retain" else parent

    choices: dict[str, dict[str, dict[str, Any]]] = {"corrected": {}, "unchanged": {}}
    audits = [initial["audit"], correction["audit"]]
    staging = run / "confirmation-staging"
    staging.mkdir()
    branches = [("corrected", candidate), ("unchanged", parent)]
    for index in range(6):
        order = branches if index % 2 == 0 else list(reversed(branches))
        for branch, subject in order:
            label = f"correction-confirmation-{index + 1:02d}-{branch}"
            root = staging / label
            root.mkdir()
            result = run_selection(context, prior131, p82, root, label, subject, candidates, world)
            choices[branch][label] = result
            audits.append(result["audit"])
    corrected_result = branch_result(choices["corrected"], operation, CONFIRMATION, "viable-branch-carrier")
    unchanged_result = branch_result(choices["unchanged"], operation, CONFIRMATION, "viable-branch-carrier")

    floor_subject = projected_stake_subject(p82, candidate, parent["active_developmental_stake"])
    floor_choices = {}
    floor_specs = [("ot0178", result_178["world"], old_178), ("ot0179", result_179["world"], old_179)] * 2
    floor_root = run / "no-regression-staging"
    floor_root.mkdir()
    for index, (floor_id, receipt, cases) in enumerate(floor_specs, 1):
        label = f"prior-floor-{index:02d}-{floor_id}"
        root = floor_root / label
        root.mkdir()
        result = run_selection(context, prior131, p82, root, label, floor_subject, candidates, receipt)
        binding = result.get("binding")
        mechanism_id = binding["mechanism_id"] if binding else None
        contact = evaluate_mechanism(mechanism_id, operation, cases)
        floor_choices[label] = {**result, "floor_id": floor_id, "contact": contact}
        audits.append(result["audit"])
    floor_pass_count = sum(bool(row.get("binding") and row["binding"]["mechanism_id"] == "prediction-corrector" and row["contact"]["passed"]) for row in floor_choices.values())

    confirmation_body = {"authority": "ot-0180-independent-correction-layer-confirmation", "correction_binding_digest": correction["binding"]["binding_digest"] if correction["binding"] else None, "candidate_subject_digest": candidate["artifact_digest"], "confirmation_digest": p82.digest(CONFIRMATION), "corrected_result": corrected_result, "unchanged_result": unchanged_result, "floor_pass_count": floor_pass_count, "floor_actor_count": len(floor_choices)}
    confirmation_world = {**confirmation_body, "receipt_digest": p82.digest(confirmation_body)}
    authority_base.guide_base.write_json(run / "sealed-correction-layer-confirmation-world.json", confirmation_world)
    all_bound = all(choices[branch].get(label, {}).get("binding") for branch in choices for label in choices[branch]) and len(choices["corrected"]) + len(choices["unchanged"]) == 12 and all(row.get("binding") for row in floor_choices.values())
    advantage = corrected_result["contact_pass_count"] - unchanged_result["contact_pass_count"]
    extension_row = next(row for row in candidate["active_mechanism_authority_projection"]["projection"]["mechanisms"] if row["mechanism_id"] == "corrected-identity-gated-extension")
    promoted = bool(initial["binding"] and selected_mechanism == "prediction-corrector" and selected_harm["pass_count"] == 0 and correction["binding"] and correction["binding"]["correction"]["change_kind"] != "retain" and all_bound and len(audits) == 18 and all(prior131.audit_accepted(audit) for audit in audits) and corrected_result["contact_pass_count"] == 6 and unchanged_result["contact_pass_count"] <= 3 and advantage >= 3 and floor_pass_count == 4 and extension_row == {"mechanism_id": "corrected-identity-gated-extension", "status": "surrendered", "floor_role": "regression-only"})
    final = parent
    if promoted:
        child = copy.deepcopy(candidate)
        child.pop("artifact_digest", None)
        capability_body = {"authority": "ot-0180-actor-chosen-correction-capability", "source_subject_digest": parent["artifact_digest"], "candidate_subject_digest": candidate["artifact_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "harm_world_receipt_digest": world["receipt_digest"], "confirmation_world_receipt_digest": confirmation_world["receipt_digest"], "prior_floor_receipt_digests": [result_178["world"]["receipt_digest"], result_179["world"]["receipt_digest"]]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_correction_capabilities"] = [*child.get("developmental_correction_capabilities", []), capability]
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_stake", "active_pursuit", "continuation", "unresolved", "revised_developmental_stakes", "developmental_correction_layer_decisions", "mechanism_authority_projections", "active_mechanism_authority_projection", "active_developmental_mechanism_selector", "active_developmental_mechanism_choice", "developmental_correction_capabilities"}
    checks = {"eighteen_fresh_actors_accepted": len(audits) == 18 and all(prior131.audit_accepted(audit) for audit in audits), "initial_prediction_selection": selected_mechanism == "prediction-corrector", "initial_prediction_harm_0_of_3": selected_harm["pass_count"] == 0, "viable_harm_control_3_of_3": harm_results["viable-branch-carrier"]["pass_count"] == 3, "nontrivial_actor_chosen_correction": bool(correction["binding"] and correction["binding"]["correction"]["change_kind"] != "retain"), "six_corrected_choices_bound": all_bound and corrected_result["actor_count"] == 6, "corrected_contact_6_of_6": corrected_result["contact_pass_count"] == 6, "unchanged_contact_at_most_3_of_6": unchanged_result["contact_pass_count"] <= 3, "corrected_advantage_at_least_3": advantage >= 3, "prior_floor_4_of_4": floor_pass_count == 4, "surrendered_extension_retained_exactly": extension_row == {"mechanism_id": "corrected-identity-gated-extension", "status": "surrendered", "floor_role": "regression-only"}, "correction_capability_installed": bool(promoted and final.get("developmental_correction_capabilities", [])[-1]["confirmation_world_receipt_digest"] == confirmation_world["receipt_digest"]), "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0180-actor-chosen-correction-layer", "source_subject_digest": parent["artifact_digest"], "initial_selection": p82.compact(initial), "harm_world": world, "correction": p82.compact(correction), "candidate_subject_digest": candidate["artifact_digest"], "confirmation_choices": choices, "floor_choices": floor_choices, "confirmation_world": confirmation_world, "checks": checks, "actor_chosen_correction_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": len(audits)}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
