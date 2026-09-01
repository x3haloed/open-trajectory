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


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0186_consequence_revised_executable_routing.py"
BASE_SHA256 = "87fadb9525b34581e723ea64508a6927ea79334a581f9de6054d2d97af76e892"
PARENT_DIGEST = "40818aa8c898da506378ab82ddebe6682c5edc8b524f5e1bb2025bb391cf2747"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0186 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0187_frozen_ot0186", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot0185 = previous.previous
ot0183 = previous.ot0183
authority_base = previous.authority_base

PUBLIC_EXPANSION = previous.expansion_cases("replication-public-expansion", 3, 800)
CONFIRM_EXPANSION = previous.expansion_cases("replication-confirm-expansion", 6, 900)
CONFIRM_OBSERVATION = ot0185.normalized(ot0185.OBSERVATION, 1000)
CONFIRM_MIXED = ot0185.normalized(ot0185.MIXED, 1100)


def public_receipt(p82, route, expression):
    selected = previous.mechanism_for(route, "blocked-option")
    selected_result = previous.expansion_result(selected, expression, PUBLIC_EXPANSION)
    viable_result = previous.expansion_result(
        "viable-branch-carrier", expression, PUBLIC_EXPANSION
    )
    body = {
        "authority": "ot-0187-sealed-replication-route-contradiction",
        "regime": "blocked-option",
        "selected_mechanism": selected,
        "selected_result": selected_result,
        "comparison_mechanism": "viable-branch-carrier",
        "comparison_result": viable_result,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def evaluate_route(route, expression):
    if route is None:
        return {"passed": False, "pass_count": 0, "case_count": 16, "regimes": {}}
    regimes = {
        "blocked-option": previous.expansion_result(
            previous.mechanism_for(route, "blocked-option"),
            expression,
            CONFIRM_EXPANSION,
        ),
        "observation-led": ot0185.result_for(
            previous.mechanism_for(route, "observation-led"),
            expression,
            CONFIRM_OBSERVATION,
        ),
        "mixed-observed-blocked": ot0185.result_for(
            previous.mechanism_for(route, "mixed-observed-blocked"),
            expression,
            CONFIRM_MIXED,
        ),
    }
    pass_count = sum(result["pass_count"] for result in regimes.values())
    return {
        "passed": pass_count == 16,
        "pass_count": pass_count,
        "case_count": 16,
        "regimes": regimes,
    }


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = (
        lineage.selector_base,
        lineage.base,
        lineage.prior131,
        lineage.base130,
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0187").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)

    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0182", "open-subject-after-raw-sufficient-assimilation.json"
    )
    f183 = selector_base.load_artifact(
        p82, repo, store, "OT-0183", "subject-bound-falsifiable-contact-aggregate.json"
    )
    matrix = selector_base.load_artifact(
        p82, repo, store, "OT-0185", "certified-signature-matrix.json"
    )
    inherited = selector_base.load_artifact(
        p82, repo, store, "OT-0185", "actor-authored-certified-routes.json"
    )
    prior_result = selector_base.load_artifact(
        p82, repo, store, "OT-0186", "consequence-revised-executable-routing-aggregate.json"
    )
    correction = f183["corrections"]["active"]
    subject, candidates = ot0183.compile_branch(
        p82, parent, correction, selector_base.CANDIDATES
    )
    expression = correction["binding"]["correction"]["mechanism"]
    candidate = {"rationale": inherited["rationale"], "routes": inherited["routes"]}
    receipt = public_receipt(p82, candidate, expression)
    initial_confirmation = evaluate_route(candidate, expression)

    checker = False
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "check"
        root.mkdir()
        seed = previous.route_seed(
            root,
            parent,
            candidate,
            matrix,
            candidates,
            subject["active_mechanism_authority_projection"]["projection"],
            receipt,
        )
        checker = previous.valid_route(
            json.loads((seed / "executable-route.json").read_text()),
            {row["mechanism_id"] for row in candidates},
        )

    fisher_boundary = Fraction(70, 1820)
    fixtures = {
        "checks": {
            "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST
            and parent["continuation"]["status"] == "open"
            and runtime.identity_conforms(parent),
            "ot0186_exact_rejection": prior_result["observer_disposition"] == "rejected"
            and prior_result["active_full_pass_count"] == 4
            and prior_result["control_full_pass_count"] == 2,
            "inherited_route_exact": previous.mechanism_for(candidate, "blocked-option")
            == expression["mechanism_id"],
            "replication_public_route_fails_0_of_3": receipt["selected_result"]["pass_count"] == 0,
            "replication_public_viable_passes_3_of_3": receipt["comparison_result"]["pass_count"] == 3,
            "initial_confirm_is_10_of_16": initial_confirmation["pass_count"] == 10,
            "fisher_boundary_exact": fisher_boundary == Fraction(1, 26)
            and float(fisher_boundary) < 0.05,
            "route_checker_accepts_inherited": checker,
            "schema_present": previous.ROUTE_SCHEMA.is_file(),
        },
        "contradiction_receipt_digest": receipt["receipt_digest"],
        "matrix_digest": matrix["matrix_digest"],
        "fisher_boundary": {
            "numerator": fisher_boundary.numerator,
            "denominator": fisher_boundary.denominator,
            "decimal": float(fisher_boundary),
        },
    }
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0187 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    authority_base.guide_base.write_json(run / "sealed-replication-contradiction.json", receipt)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, run, repo)
    )
    rows = []
    counts = {"active": 0, "control": 0}
    schedule = ["control", "active", "active", "control"] * 4
    for branch in schedule:
        counts[branch] += 1
        index = counts[branch]
        root = run / f"{branch}-{index:02d}-authoring"
        root.mkdir()
        branch_receipt = receipt if branch == "active" else previous.erased_receipt(receipt)
        repair = previous.run_repair(
            context,
            prior131,
            p82,
            root,
            f"replication-{branch}-{index:02d}",
            parent,
            candidate,
            matrix,
            candidates,
            subject["active_mechanism_authority_projection"]["projection"],
            branch_receipt,
        )
        bound_route = repair["binding"]["route"] if repair.get("binding") else None
        rows.append(
            {
                "branch": branch,
                "index": index,
                "repair": repair,
                "evaluation": evaluate_route(bound_route, expression),
            }
        )

    active_full = sum(row["evaluation"]["passed"] for row in rows if row["branch"] == "active")
    control_full = sum(row["evaluation"]["passed"] for row in rows if row["branch"] == "control")
    operation = authority_base.reuse.extension_base.load_operation(
        parent["developmental_property_extensions"][0]["operation_source"]
    )
    identity = authority_base.reuse.extension_base.evaluate(
        operation, authority_base.reuse.accumulated_floor()
    )
    audits = [row["repair"]["audit"] for row in rows]
    checks = {
        "sixteen_fresh_actors_accepted": len(audits) == 16
        and all(prior131.audit_accepted(audit) for audit in audits),
        "active_8_of_8_full": active_full == 8,
        "control_at_most_4_of_8_full": control_full <= 4,
        "advantage_at_least_4": active_full - control_full >= 4,
        "initial_route_blocked_0_of_6": initial_confirmation["regimes"]["blocked-option"]["pass_count"] == 0,
        "initial_route_other_10_of_10": initial_confirmation["regimes"]["observation-led"]["passed"]
        and initial_confirmation["regimes"]["mixed-observed-blocked"]["passed"],
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1)
        child = copy.deepcopy(subject)
        child.pop("artifact_digest", None)
        artifact_body = {
            "authority": "ot-0187-replicated-executable-routing-selector",
            "source_subject_digest": parent["artifact_digest"],
            "contradiction_receipt_digest": receipt["receipt_digest"],
            "repair_binding_digest": first["repair"]["binding"]["binding_digest"],
            "route": first["repair"]["binding"]["route"],
        }
        artifact = {**artifact_body, "binding_digest": p82.digest(artifact_body)}
        child["executable_routing_selectors"] = [artifact]
        child["active_executable_routing_selector"] = artifact
        child["routing_contradiction_receipts"] = [receipt]
        final = p82.seal(child)

    result = {
        "authority": "ot-0187-executable-routing-receipt-effect-replication",
        "source_subject_digest": parent["artifact_digest"],
        "contradiction_receipt": receipt,
        "initial_route_confirmation": initial_confirmation,
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
