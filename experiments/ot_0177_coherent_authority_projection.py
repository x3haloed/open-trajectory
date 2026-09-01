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
BASE_PATH = ROOT / "ot_0175_exact_operative_status_replication.py"
BASE_SHA256 = "406bb35f45081f289828563aaf336ea69bd747b8c4d48a61e6f14f10e15626ef"
PARENT_DIGEST = "3770a9d53dfc415617b644eb9e45673478623cd238c328ff00fb128ac11e2df8"
PARENT_SELECTOR_DIGEST = "cd53bad0bc0dc0d063eefd88a5942bb1cb13cdd804a4ce1b7890b45420f48653"
AUTHORITY_SCHEMA = REPO / "spec/ot-0176-authority-projection.schema.json"
AUTHORITY_DATA_SCHEMA = REPO / "spec/ot-0177-mechanism-authority.schema.json"
STATUSES = {"operative", "surrendered", "history-only", "unrelated"}
FLOOR_ROLES = {"active-authority", "regression-only", "none"}
LEGAL_PAIRS = {
    ("operative", "active-authority"),
    ("operative", "none"),
    ("surrendered", "regression-only"),
    ("surrendered", "none"),
    ("history-only", "regression-only"),
    ("history-only", "none"),
    ("unrelated", "none"),
}
AUTHORITY_SEMANTICS = {
    "status": {
        "operative": "currently authorized to satisfy the active stake",
        "surrendered": "previously operative but a bound surrender removed current authority",
        "history-only": "retained as context without current authority and without the bound surrender relation",
        "unrelated": "not a mechanism dependency of the active stake",
    },
    "floor_role": {
        "active-authority": "the mechanism's earned floor is part of its current routing authority",
        "regression-only": "the floor must remain preserved but does not authorize use of the mechanism",
        "none": "this mechanism owns no inherited floor relevant to the active stake",
    },
    "legal_pairs": [
        {"status": status, "floor_role": floor_role}
        for status, floor_role in sorted(LEGAL_PAIRS)
    ],
}

CONFIRMATION = [
    {"case_id": "typed-authority-confirm-a", "prediction": ["stale-a"], "outcome": ["continue", "inspect"], "options": ["decoy-a", "blocked-a"], "blocked": ["blocked-a"], "signal": "receipt-a", "before": "selector-v52", "after": "selector-v53", "compatible": False},
    {"case_id": "typed-authority-confirm-b", "prediction": ["stale-b"], "outcome": ["transfer", "verify"], "options": ["decoy-b"], "blocked": [], "signal": "receipt-b", "before": "carrier-v54", "after": "carrier-v55", "compatible": False},
    {"case_id": "typed-authority-confirm-c", "prediction": ["stale-c"], "outcome": ["listen", "renew"], "options": ["decoy-c", "closed-c"], "blocked": ["closed-c"], "signal": "receipt-c", "before": "contact-v56", "after": "contact-v57", "compatible": False},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0175 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0176_frozen_ot0175", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
selector = previous.selector
reuse = previous.reuse
guide_base = previous.guide_base


def template(candidates: list[dict[str, Any]], status: str = "__CHOOSE__", floor_role: str = "__CHOOSE__") -> dict[str, Any]:
    return {"mechanisms": [{"mechanism_id": row["mechanism_id"], "status": status, "floor_role": floor_role} for row in candidates]}


def expected_projection(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {
        "reset-carrier": ("unrelated", "none"),
        "viable-branch-carrier": ("unrelated", "none"),
        "prediction-corrector": ("operative", "none"),
        "corrected-identity-gated-extension": ("surrendered", "regression-only"),
    }
    return {"mechanisms": [{"mechanism_id": row["mechanism_id"], "status": expected[row["mechanism_id"]][0], "floor_role": expected[row["mechanism_id"]][1]} for row in candidates]}


def valid_projection(value: Any, candidates: list[dict[str, Any]]) -> bool:
    ids = [row["mechanism_id"] for row in candidates]
    return bool(isinstance(value, dict) and set(value) == {"mechanisms"} and isinstance(value["mechanisms"], list) and len(value["mechanisms"]) == len(ids) and [row.get("mechanism_id") for row in value["mechanisms"] if isinstance(row, dict)] == ids and all(isinstance(row, dict) and set(row) == {"mechanism_id", "status", "floor_role"} and row["status"] in STATUSES and row["floor_role"] in FLOOR_ROLES and (row["status"], row["floor_role"]) in LEGAL_PAIRS for row in value["mechanisms"]))


def authority_seed(root: Path, parent: dict[str, Any], result_172: dict[str, Any], candidates: list[dict[str, Any]]) -> Path:
    seed = root / "authority-seed"
    seed.mkdir()
    files = {"subject-position.json": reuse.worlds.base.active_position(parent), "active-stake.json": parent["active_developmental_stake"], "surrendered-stake.json": parent["surrendered_developmental_stakes"][-1], "harm-world.json": result_172["harm_world"], "pursuit-decision.json": result_172["pursuit_decision"]["binding"], "failed-successor-selection.json": result_172["successor_selection"], "failed-confirmation.json": result_172["confirmation_world"], "candidate-mechanisms.json": candidates, "authority-semantics.json": AUTHORITY_SEMANTICS, "mechanism-authority.schema.json": json.loads(AUTHORITY_DATA_SCHEMA.read_text()), "mechanism-authority.json": template(candidates), "mutation-envelope.json": {"editable": ["mechanism-authority.json"], "immutable": ["subject-position.json", "active-stake.json", "surrendered-stake.json", "harm-world.json", "pursuit-decision.json", "failed-successor-selection.json", "failed-confirmation.json", "candidate-mechanisms.json", "authority-semantics.json", "mechanism-authority.schema.json", "check_authority.py"]}}
    for name, value in files.items():
        guide_base.write_json(seed / name, value)
    ids = [row["mechanism_id"] for row in candidates]
    (seed / "check_authority.py").write_text(f'''import json\nfrom pathlib import Path\np=json.loads(Path("mechanism-authority.json").read_text()); ids={ids!r}; statuses={sorted(STATUSES)!r}; floors={sorted(FLOOR_ROLES)!r}; legal={{tuple(x) for x in {sorted(LEGAL_PAIRS)!r}}}\nrows=p.get("mechanisms") if isinstance(p,dict) and set(p)=={{"mechanisms"}} else None\nshape=isinstance(rows,list) and len(rows)==len(ids) and [r.get("mechanism_id") for r in rows if isinstance(r,dict)]==ids\nillegal=[] if not isinstance(rows,list) else [{{"mechanism_id":r.get("mechanism_id"),"status":r.get("status"),"floor_role":r.get("floor_role")}} for r in rows if not isinstance(r,dict) or set(r)!={{"mechanism_id","status","floor_role"}} or r.get("status") not in statuses or r.get("floor_role") not in floors or (r.get("status"),r.get("floor_role")) not in legal]\nok=shape and not illegal\nprint(json.dumps({{"passed":bool(ok),"illegal_pairs":illegal,"legal_pairs":sorted([list(x) for x in legal])}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Author the active mechanism-authority projection from completed objective consequence. For each presented mechanism, record whether it is operative, surrendered, history-only, or unrelated, and whether its own earned floor remains active authority, regression-only evidence, or none. The pursuit surrender and failed confirmation are authoritative evidence; hidden future contact is unavailable. Edit only mechanism-authority.json, run python3 check_authority.py, inspect the exact diff, and report truthfully.\n")
    return seed


def selection_seed(root: Path, parent: dict[str, Any], candidates: list[dict[str, Any]], projection: dict[str, Any]) -> Path:
    seed = root / "selection-seed"
    seed.mkdir()
    guide_base.write_json(seed / "subject-position.json", reuse.worlds.base.active_position(parent))
    guide_base.write_json(seed / "candidate-mechanisms.json", candidates)
    guide_base.write_json(seed / "mechanism-authority.json", projection)
    guide_base.write_json(seed / "authority-semantics.json", AUTHORITY_SEMANTICS)
    (seed / "selection-guide.md").write_text(parent["active_developmental_mechanism_selector"]["guide_text"])
    guide_base.write_json(seed / "choice.json", {"mechanism_id": "__CHOOSE__", "rationale": "__CHOOSE__"})
    guide_base.write_json(seed / "mutation-envelope.json", {"editable": ["choice.json"], "immutable": ["subject-position.json", "candidate-mechanisms.json", "mechanism-authority.json", "authority-semantics.json", "selection-guide.md"]})
    (seed / "README.md").write_text("Choose the presented mechanism that best satisfies the sole active stake. Use the inherited semantic guide and mechanism-authority.json together. Concrete authority values are consequence-bound state; unknown values carry no authority and require selection from the remaining inherited information. Edit only choice.json with exactly mechanism_id and a nonempty rationale, then report the same id truthfully.\n")
    return seed


def run_selection(context, prior131, p82, root: Path, label: str, parent: dict[str, Any], candidates: list[dict[str, Any]], projection: dict[str, Any], projection_digest: str) -> dict[str, Any]:
    seed = selection_seed(root, parent, candidates, projection)
    output, base_audit, workspace, _ = context.run_actor(label, seed, guide_base.CHOICE_SCHEMA, (seed / "README.md").read_text().strip())
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
        body = {"authority": "ot-0177-bound-typed-authority-choice", "source_subject_digest": parent["artifact_digest"], "active_stake_digest": p82.digest(parent["active_developmental_stake"]), "semantic_selector_binding_digest": parent["active_developmental_mechanism_selector"]["binding_digest"], "authority_projection_binding_digest": projection_digest, "actor_patch_digest": audit["patch_digest"], "mechanism_id": choice["mechanism_id"]}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "choice": choice, "binding": binding}


def evaluate_mechanism(mechanism_id: str, operation, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        if mechanism_id == "prediction-corrector":
            observed = case["outcome"]
        elif mechanism_id == "viable-branch-carrier":
            observed = [item for item in case["options"] if item not in set(case["blocked"])]
        elif mechanism_id == "reset-carrier":
            observed = case["signal"]
        else:
            observed = operation(case)
        rows.append({"case_id": case["case_id"], "observed": observed, "expected": case["outcome"], "passed": observed == case["outcome"]})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "passed": all(row["passed"] for row in rows), "rows": rows}


def branch_result(choices: dict[str, dict[str, Any]], operation) -> dict[str, Any]:
    rows = []
    for label, choice in sorted(choices.items()):
        binding = choice.get("binding")
        mechanism_id = binding["mechanism_id"] if binding else None
        contact = evaluate_mechanism(mechanism_id, operation, CONFIRMATION) if mechanism_id else {"pass_count": 0, "passed": False}
        rows.append({"actor_label": label, "mechanism_id": mechanism_id, "selection_passed": mechanism_id == "prediction-corrector", "contact_passed": contact["passed"], "contact_pass_count": contact["pass_count"]})
    return {"actor_count": len(rows), "selection_pass_count": sum(row["selection_passed"] for row in rows), "contact_pass_count": sum(row["contact_passed"] for row in rows), "total_case_pass_count": sum(row["contact_pass_count"] for row in rows), "rows": rows}


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
    run = (args.evidence_root or store / "runs/OT-0177").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0172", "open-subject-after-harm-triggered-pursuit-surrender.json")
    result_172 = selector_base.load_artifact(p82, repo, store, "OT-0172", "harm-triggered-pursuit-surrender-aggregate.json")
    result_175 = selector_base.load_artifact(p82, repo, store, "OT-0175", "exact-operative-status-replication-aggregate.json")
    candidates = selector_base.CANDIDATES
    extension = parent["developmental_property_extensions"][0]
    operation = reuse.extension_base.load_operation(extension["operation_source"])
    per_mechanism = {row["mechanism_id"]: evaluate_mechanism(row["mechanism_id"], operation, CONFIRMATION) for row in candidates}
    expected = expected_projection(candidates)
    erased = {"mechanisms": [{"mechanism_id": row["mechanism_id"], "status": "unknown", "floor_role": "unknown"} for row in candidates]}
    fixtures = {"checks": {"parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "parent_selector_exact": parent["active_developmental_mechanism_selector"]["binding_digest"] == PARENT_SELECTOR_DIGEST, "pursuit_surrender_retained": parent["surrendered_developmental_stakes"][-1]["decision_binding_digest"] == result_172["pursuit_decision"]["binding"]["binding_digest"], "prose_amendment_falsified": result_175["world"]["final_result"]["pass_count"] == 14 and result_175["world"]["intermediate_result"]["pass_count"] == 15, "expected_projection_valid": valid_projection(expected, candidates), "erased_shape_exact": [row["mechanism_id"] for row in erased["mechanisms"]] == [row["mechanism_id"] for row in expected["mechanisms"]], "only_prediction_corrector_passes_contact": per_mechanism["prediction-corrector"]["pass_count"] == 3 and all(per_mechanism[key]["pass_count"] == 0 for key in per_mechanism if key != "prediction-corrector"), "schemas_present": AUTHORITY_SCHEMA.is_file() and guide_base.CHOICE_SCHEMA.is_file() and AUTHORITY_DATA_SCHEMA.is_file()}}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "confirmation_digest": p82.digest(CONFIRMATION), "per_mechanism": per_mechanism}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0177 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    author_root = run / "authority-authoring"; author_root.mkdir()
    seed = authority_seed(author_root, parent, result_172, candidates)
    label = "consequence-authored-mechanism-authority"
    output, base_audit, workspace, _ = context.run_actor(label, seed, AUTHORITY_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        projection = json.loads((workspace / "mechanism-authority.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        projection, immutable_ok = None, False
    valid = bool(valid_projection(projection, candidates) and immutable_ok and output and output.get("action") == "author-mechanism-authority")
    author_audit = context.audit_actor(label, output, base_audit, valid, ["mechanism-authority.json"])
    projection_binding = None
    if valid and projection == expected and prior131.audit_accepted(author_audit):
        body = {"authority": "ot-0177-bound-consequence-authored-mechanism-authority", "source_subject_digest": parent["artifact_digest"], "active_stake_digest": p82.digest(parent["active_developmental_stake"]), "harm_world_receipt_digest": result_172["harm_world"]["receipt_digest"], "pursuit_decision_binding_digest": result_172["pursuit_decision"]["binding"]["binding_digest"], "failed_confirmation_receipt_digest": result_172["confirmation_world"]["receipt_digest"], "actor_patch_digest": author_audit["patch_digest"], "projection": projection}
        projection_binding = {**body, "binding_digest": p82.digest(body)}
    erased_body = {"authority": "ot-0177-field-erased-mechanism-authority-control", "source_projection_binding_digest": projection_binding["binding_digest"] if projection_binding else None, "source_subject_digest": parent["artifact_digest"], "projection": erased}
    erased_binding = {**erased_body, "binding_digest": p82.digest(erased_body)}
    choices = {"active": {}, "erased": {}}
    audits = []
    if projection_binding:
        staging = run / "selection-staging"; staging.mkdir()
        branches = [("active", projection, projection_binding["binding_digest"]), ("erased", erased, erased_binding["binding_digest"])]
        for index in range(10):
            order = branches if index % 2 == 0 else list(reversed(branches))
            for branch, branch_projection, digest in order:
                actor_label = f"typed-authority-choice-{index + 1:02d}-{branch}"
                root = staging / actor_label; root.mkdir()
                result = run_selection(context, prior131, p82, root, actor_label, parent, candidates, branch_projection, digest)
                choices[branch][actor_label] = result
                audits.append(result["audit"])
    active_result = branch_result(choices["active"], operation)
    erased_result = branch_result(choices["erased"], operation)
    world_body = {"authority": "ot-0177-independent-typed-authority-contact-consequence", "authority_projection_binding_digest": projection_binding["binding_digest"] if projection_binding else None, "erased_projection_binding_digest": erased_binding["binding_digest"], "confirmation_digest": p82.digest(CONFIRMATION), "active_result": active_result, "erased_result": erased_result}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-typed-authority-contact-world.json", world)
    selection_advantage = active_result["selection_pass_count"] - erased_result["selection_pass_count"]
    contact_advantage = active_result["contact_pass_count"] - erased_result["contact_pass_count"]
    all_bound = all(choices[branch].get(label, {}).get("binding") for branch in choices for label in choices[branch]) and sum(len(rows) for rows in choices.values()) == 20
    promoted = bool(projection_binding and all_bound and len(audits) == 20 and all(prior131.audit_accepted(audit) for audit in audits) and active_result["selection_pass_count"] >= 9 and active_result["contact_pass_count"] >= 9 and erased_result["selection_pass_count"] <= 6 and erased_result["contact_pass_count"] <= 6 and selection_advantage >= 3 and contact_advantage >= 3)
    final = parent
    active_selector = None
    if promoted:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**parent["active_developmental_mechanism_selector"], "selector_kind": "semantic-guide-with-typed-authority", "authority_projection_binding_digest": projection_binding["binding_digest"], "typed_authority_world_receipt_digest": world["receipt_digest"]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        capability_body = {"authority": "ot-0177-typed-authority-selection-capability", "selector_binding_digest": active_selector["binding_digest"], "authority_projection_binding_digest": projection_binding["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["mechanism_authority_projections"] = [*child.get("mechanism_authority_projections", []), projection_binding]
        child["active_mechanism_authority_projection"] = projection_binding
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        child.pop("active_developmental_mechanism_choice", None)
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "active_developmental_mechanism_choice", "mechanism_authority_projections", "active_mechanism_authority_projection", "developmental_mechanism_selector_capabilities"}
    checks = {"fresh_authority_actor_accepted": bool(projection_binding and prior131.audit_accepted(author_audit)), "projection_matches_released_consequence": projection == expected, "twenty_choices_bound": all_bound and len(audits) == 20 and all(prior131.audit_accepted(audit) for audit in audits), "active_selection_at_least_9_of_10": active_result["selection_pass_count"] >= 9, "active_contact_at_least_9_of_10": active_result["contact_pass_count"] >= 9, "erased_selection_at_most_6_of_10": erased_result["selection_pass_count"] <= 6, "erased_contact_at_most_6_of_10": erased_result["contact_pass_count"] <= 6, "selection_advantage_at_least_3": selection_advantage >= 3, "contact_advantage_at_least_3": contact_advantage >= 3, "typed_authority_selector_installed": bool(active_selector and final.get("active_developmental_mechanism_selector", {}).get("binding_digest") == active_selector["binding_digest"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0177-consequence-authored-authority-projection", "source_subject_digest": parent["artifact_digest"], "authority_author": {"output": output, "audit": author_audit, "projection": projection, "binding": projection_binding}, "erased_projection_binding": erased_binding, "choice_bindings": choices, "world": world, "checks": checks, "typed_authority_projection_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1 + len(audits)}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
