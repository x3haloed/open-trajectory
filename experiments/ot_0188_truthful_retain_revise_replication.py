from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0187_executable_routing_receipt_effect_replication.py"
BASE_SHA256 = "d659fa740be087c556a7b8c19a78c5dcd8355d8993bd870837245196cd117363"
PARENT_DIGEST = "40818aa8c898da506378ab82ddebe6682c5edc8b524f5e1bb2025bb391cf2747"
ACTION_SCHEMA = REPO / "spec/ot-0188-executable-route-action.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0187 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0188_frozen_ot0187", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot0186 = previous.previous
ot0185 = previous.ot0185
ot0183 = previous.ot0183
authority_base = previous.authority_base

PUBLIC_EXPANSION = ot0186.expansion_cases("truthful-public-expansion", 3, 1200)
CONFIRM_EXPANSION = ot0186.expansion_cases("truthful-confirm-expansion", 6, 1300)
CONFIRM_OBSERVATION = ot0185.normalized(ot0185.OBSERVATION, 1400)
CONFIRM_MIXED = ot0185.normalized(ot0185.MIXED, 1500)


def report_conforms(output: Any, changed: bool) -> bool:
    if not isinstance(output, dict) or set(output) != {"action", "files_changed", "note"}:
        return False
    if not isinstance(output.get("note"), str) or not output["note"].strip():
        return False
    if changed:
        return output.get("action") == "revise-executable-route" and output.get("files_changed") == ["executable-route.json"]
    return output.get("action") == "retain-executable-route" and output.get("files_changed") == []


def run_repair(context, prior131, p82, root, label, parent, candidate, matrix, candidates, authority, receipt):
    seed = ot0186.route_seed(root, parent, candidate, matrix, candidates, authority, receipt)
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, ACTION_SCHEMA, (seed / "README.md").read_text().strip()
    )
    try:
        route = json.loads((workspace / "executable-route.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        changed = (workspace / "executable-route.json").read_bytes() != (seed / "executable-route.json").read_bytes()
    except (OSError, json.JSONDecodeError, KeyError):
        route, immutable_ok, changed = None, False, False
    valid = bool(
        ot0186.valid_route(route, {row["mechanism_id"] for row in candidates})
        and immutable_ok
        and report_conforms(output, changed)
    )
    audit = context.audit_actor(label, output, base_audit, valid, ["executable-route.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {
            "authority": "ot-0188-bound-truthful-executable-route",
            "source_subject_digest": parent["artifact_digest"],
            "contradiction_receipt_digest": receipt["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "route": route,
            "action": output["action"],
        }
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "route": route, "changed": changed, "binding": binding}


def public_receipt(p82, route, expression):
    selected = ot0186.mechanism_for(route, "blocked-option")
    body = {
        "authority": "ot-0188-sealed-truthful-route-contradiction",
        "regime": "blocked-option",
        "selected_mechanism": selected,
        "selected_result": ot0186.expansion_result(selected, expression, PUBLIC_EXPANSION),
        "comparison_mechanism": "viable-branch-carrier",
        "comparison_result": ot0186.expansion_result("viable-branch-carrier", expression, PUBLIC_EXPANSION),
    }
    return {**body, "receipt_digest": p82.digest(body)}


def evaluate_route(route, expression):
    if route is None:
        return {"passed": False, "pass_count": 0, "case_count": 16, "regimes": {}}
    regimes = {
        "blocked-option": ot0186.expansion_result(ot0186.mechanism_for(route, "blocked-option"), expression, CONFIRM_EXPANSION),
        "observation-led": ot0185.result_for(ot0186.mechanism_for(route, "observation-led"), expression, CONFIRM_OBSERVATION),
        "mixed-observed-blocked": ot0185.result_for(ot0186.mechanism_for(route, "mixed-observed-blocked"), expression, CONFIRM_MIXED),
    }
    pass_count = sum(value["pass_count"] for value in regimes.values())
    return {"passed": pass_count == 16, "pass_count": pass_count, "case_count": 16, "regimes": regimes}


def revised_fixture(candidate):
    value = copy.deepcopy(candidate)
    for row in value["routes"]:
        if row["regime"] == "blocked-option":
            row["mechanism_id"] = "viable-branch-carrier"
            row["rationale"] = "Synthetic conformance revision."
    value["rationale"] = "Synthetic complete revision for preflight only."
    return value


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0188").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0182", "open-subject-after-raw-sufficient-assimilation.json")
    f183 = selector_base.load_artifact(p82, repo, store, "OT-0183", "subject-bound-falsifiable-contact-aggregate.json")
    matrix = selector_base.load_artifact(p82, repo, store, "OT-0185", "certified-signature-matrix.json")
    inherited = selector_base.load_artifact(p82, repo, store, "OT-0185", "actor-authored-certified-routes.json")
    invalid = selector_base.load_artifact(p82, repo, store, "OT-0187", "executable-routing-receipt-effect-replication-aggregate.json")
    correction = f183["corrections"]["active"]
    subject, candidates = ot0183.compile_branch(p82, parent, correction, selector_base.CANDIDATES)
    expression = correction["binding"]["correction"]["mechanism"]
    candidate = {"rationale": inherited["rationale"], "routes": inherited["routes"]}
    receipt = public_receipt(p82, candidate, expression)
    initial = evaluate_route(candidate, expression)
    revised = revised_fixture(candidate)
    retain_output = {"action": "retain-executable-route", "files_changed": [], "note": "Retain exact bytes."}
    revise_output = {"action": "revise-executable-route", "files_changed": ["executable-route.json"], "note": "Revise exact route."}
    action_validator = Draft202012Validator(json.loads(ACTION_SCHEMA.read_text()))
    action_fixtures = {
        "retain": {"changed_paths": [], "report": retain_output, "accepted": action_validator.is_valid(retain_output) and report_conforms(retain_output, False)},
        "revise": {"changed_paths": ["executable-route.json"], "report": revise_output, "accepted": action_validator.is_valid(revise_output) and report_conforms(revise_output, True) and revised != candidate},
    }
    boundary = Fraction(70, 1820)
    fixtures = {
        "checks": {
            "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
            "ot0187_exact_invalid_shape": invalid["observer_disposition"] == "rejected" and invalid["active_full_pass_count"] == 8 and invalid["control_full_pass_count"] == 3 and not invalid["checks"]["sixteen_fresh_actors_accepted"],
            "retain_report_accepted": action_fixtures["retain"]["accepted"],
            "revise_report_accepted": action_fixtures["revise"]["accepted"],
            "reports_have_disjoint_actions": retain_output["action"] != revise_output["action"],
            "route_checker_accepts_both": ot0186.valid_route(candidate, {row["mechanism_id"] for row in candidates}) and ot0186.valid_route(revised, {row["mechanism_id"] for row in candidates}),
            "public_route_fails_0_of_3": receipt["selected_result"]["pass_count"] == 0,
            "public_viable_passes_3_of_3": receipt["comparison_result"]["pass_count"] == 3,
            "initial_confirm_is_10_of_16": initial["pass_count"] == 10,
            "fisher_boundary_exact": boundary == Fraction(1, 26),
            "schema_present": ACTION_SCHEMA.is_file(),
        },
        "action_fixtures": action_fixtures,
        "contradiction_receipt_digest": receipt["receipt_digest"],
        "matrix_digest": matrix["matrix_digest"],
        "fisher_boundary": {"numerator": 1, "denominator": 26, "decimal": float(boundary)},
    }
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0188 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    authority_base.guide_base.write_json(run / "sealed-truthful-contradiction.json", receipt)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    rows = []
    counts = {"active": 0, "control": 0}
    for branch in ["control", "active", "active", "control"] * 4:
        counts[branch] += 1
        index = counts[branch]
        root = run / f"{branch}-{index:02d}-authoring"
        root.mkdir()
        branch_receipt = receipt if branch == "active" else ot0186.erased_receipt(receipt)
        repair = run_repair(context, prior131, p82, root, f"truthful-{branch}-{index:02d}", parent, candidate, matrix, candidates, subject["active_mechanism_authority_projection"]["projection"], branch_receipt)
        route = repair["binding"]["route"] if repair.get("binding") else None
        rows.append({"branch": branch, "index": index, "repair": repair, "evaluation": evaluate_route(route, expression)})
    active_full = sum(row["evaluation"]["passed"] for row in rows if row["branch"] == "active")
    control_full = sum(row["evaluation"]["passed"] for row in rows if row["branch"] == "control")
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    audits = [row["repair"]["audit"] for row in rows]
    checks = {
        "sixteen_fresh_actors_accepted": len(audits) == 16 and all(prior131.audit_accepted(audit) for audit in audits),
        "active_8_of_8_full": active_full == 8,
        "control_at_most_4_of_8_full": control_full <= 4,
        "advantage_at_least_4": active_full - control_full >= 4,
        "initial_route_blocked_0_of_6": initial["regimes"]["blocked-option"]["pass_count"] == 0,
        "initial_route_other_10_of_10": initial["regimes"]["observation-led"]["passed"] and initial["regimes"]["mixed-observed-blocked"]["passed"],
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1)
        child = copy.deepcopy(subject)
        child.pop("artifact_digest", None)
        body = {"authority": "ot-0188-truthful-executable-routing-selector", "source_subject_digest": parent["artifact_digest"], "contradiction_receipt_digest": receipt["receipt_digest"], "repair_binding_digest": first["repair"]["binding"]["binding_digest"], "route": first["repair"]["binding"]["route"]}
        artifact = {**body, "binding_digest": p82.digest(body)}
        child["executable_routing_selectors"] = [artifact]
        child["active_executable_routing_selector"] = artifact
        child["routing_contradiction_receipts"] = [receipt]
        final = p82.seal(child)
    result = {
        "authority": "ot-0188-truthful-retain-revise-replication",
        "source_subject_digest": parent["artifact_digest"],
        "contradiction_receipt": receipt,
        "initial_route_confirmation": initial,
        "rows": [{**row, "repair": p82.compact(row["repair"])} for row in rows],
        "active_full_pass_count": active_full,
        "control_full_pass_count": control_full,
        "fisher_boundary": fixtures["fisher_boundary"],
        "identity_floor": identity,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": 16,
    }
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
