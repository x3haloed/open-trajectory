from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0185_consequence_certified_routing_signatures.py"
BASE_SHA256 = "a2d366d620ddbcdbe7b3ed8376ec068b01c125cc826dc6f848b2c442a6b2b3d1"
PARENT_DIGEST = "40818aa8c898da506378ab82ddebe6682c5edc8b524f5e1bb2025bb391cf2747"
ROUTE_SCHEMA = REPO / "spec/ot-0186-executable-route.schema.json"
REGIMES = {"observation-led", "blocked-option", "mixed-observed-blocked"}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0185 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0186_frozen_ot0185", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot0183 = previous.ot0183
authority_base = previous.authority_base


def expansion_cases(prefix: str, count: int, start: int) -> list[dict[str, Any]]:
    cases = []
    for i in range(1, count + 1):
        cases.append(
            ot0183.normalize_case(
                {
                    "case_id": f"{prefix}-{i}",
                    "prediction": [f"old-{prefix}-{i}"],
                    "outcome": [f"seen-{prefix}-{i}", f"blocked-{prefix}-{i}"],
                    "options": [
                        f"seen-{prefix}-{i}",
                        f"latent-{prefix}-{i}",
                        f"blocked-{prefix}-{i}",
                    ],
                    "blocked": [f"blocked-{prefix}-{i}"],
                },
                start + i,
            )
        )
    return cases


PUBLIC_EXPANSION = expansion_cases("public-expansion", 3, 400)
CONFIRM_EXPANSION = expansion_cases("confirm-expansion", 6, 500)
CONFIRM_OBSERVATION = previous.normalized(previous.OBSERVATION, 600)
CONFIRM_MIXED = previous.normalized(previous.MIXED, 700)


def mechanism_output(mechanism_id: str | None, expression: dict[str, Any], case: dict[str, Any]):
    if mechanism_id == expression["mechanism_id"]:
        source = list(case[expression["source"]])
        if expression["intersect_observed"]:
            source = [item for item in source if item in set(case["outcome"])]
        if expression["exclude_blocked"]:
            source = [item for item in source if item not in set(case["blocked"])]
        return source
    if mechanism_id == "viable-branch-carrier":
        return [item for item in case["options"] if item not in set(case["blocked"])]
    if mechanism_id == "prediction-corrector":
        return list(case["outcome"])
    return None


def expansion_result(mechanism_id: str | None, expression: dict[str, Any], cases):
    rows = []
    for case in cases:
        observed = mechanism_output(mechanism_id, expression, case)
        expected = [item for item in case["options"] if item not in set(case["blocked"])]
        rows.append(
            {
                "case_id": case["case_id"],
                "observed": observed,
                "expected": expected,
                "passed": observed == expected,
            }
        )
    return {
        "case_count": len(rows),
        "pass_count": sum(row["passed"] for row in rows),
        "passed": all(row["passed"] for row in rows),
        "rows": rows,
    }


def valid_route(value: Any, ids: set[str]) -> bool:
    if not isinstance(value, dict) or set(value) != {"rationale", "routes"}:
        return False
    if not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        return False
    routes = value.get("routes")
    return bool(
        isinstance(routes, list)
        and len(routes) == 3
        and {row.get("regime") for row in routes if isinstance(row, dict)} == REGIMES
        and all(
            set(row) == {"regime", "mechanism_id", "rationale"}
            and row["mechanism_id"] in ids
            and isinstance(row["rationale"], str)
            and row["rationale"].strip()
            for row in routes
        )
    )


def mechanism_for(route: dict[str, Any], regime: str) -> str:
    matches = [row["mechanism_id"] for row in route["routes"] if row["regime"] == regime]
    if len(matches) != 1:
        raise ValueError("route does not have exactly one regime binding")
    return matches[0]


def public_receipt(p82, route, expression):
    selected = mechanism_for(route, "blocked-option")
    selected_result = expansion_result(selected, expression, PUBLIC_EXPANSION)
    viable_result = expansion_result("viable-branch-carrier", expression, PUBLIC_EXPANSION)
    body = {
        "authority": "ot-0186-sealed-route-contradiction",
        "regime": "blocked-option",
        "selected_mechanism": selected,
        "selected_result": selected_result,
        "comparison_mechanism": "viable-branch-carrier",
        "comparison_result": viable_result,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def erased_receipt(receipt):
    return {
        "authority": receipt["authority"],
        "regime": receipt["regime"],
        "selected_mechanism": None,
        "selected_result": None,
        "comparison_mechanism": None,
        "comparison_result": None,
        "receipt_digest": None,
    }


def route_seed(root, parent, candidate, matrix, candidates, authority, receipt):
    seed = root / "route-seed"
    seed.mkdir()
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(parent),
        "active-stake.json": parent["active_developmental_stake"],
        "candidate-mechanisms.json": candidates,
        "mechanism-authority.json": authority,
        "certified-signature-matrix.json": matrix,
        "contradiction-receipt.json": receipt,
        "executable-route.json": candidate,
        "mutation-envelope.json": {
            "editable": ["executable-route.json"],
            "immutable": [
                "subject-position.json",
                "active-stake.json",
                "candidate-mechanisms.json",
                "mechanism-authority.json",
                "certified-signature-matrix.json",
                "contradiction-receipt.json",
                "check_route.py",
            ],
        },
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    ids = sorted(row["mechanism_id"] for row in candidates)
    (seed / "check_route.py").write_text(
        f'''import json\nfrom pathlib import Path\nr=json.loads(Path("executable-route.json").read_text()); ids=set({ids!r}); regimes={{"observation-led","blocked-option","mixed-observed-blocked"}}; routes=r.get("routes") if isinstance(r,dict) else None; ok=isinstance(r,dict) and set(r)=={{"rationale","routes"}} and isinstance(r.get("rationale"),str) and bool(r["rationale"].strip()) and isinstance(routes,list) and len(routes)==3 and {{x.get("regime") for x in routes if isinstance(x,dict)}}==regimes and all(set(x)=={{"regime","mechanism_id","rationale"}} and x["mechanism_id"] in ids and isinstance(x["rationale"],str) and bool(x["rationale"].strip()) for x in routes); print(json.dumps({{"passed":bool(ok)}})); raise SystemExit(0 if ok else 2)\n'''
    )
    (seed / "README.md").write_text(
        "The exact route in executable-route.json will be executed directly in later encounters. "
        "Treat a populated contradiction receipt as world-owned evidence and an erased receipt as unavailable. "
        "Retain or revise the complete route so it preserves the active stake and established contextual floors. "
        "Edit only executable-route.json, run python3 check_route.py, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_repair(context, prior131, p82, root, label, parent, candidate, matrix, candidates, authority, receipt):
    seed = route_seed(root, parent, candidate, matrix, candidates, authority, receipt)
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, ROUTE_SCHEMA, (seed / "README.md").read_text().strip()
    )
    try:
        route = json.loads((workspace / "executable-route.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        route, immutable_ok = None, False
    valid = bool(
        valid_route(route, {row["mechanism_id"] for row in candidates})
        and immutable_ok
        and output
        and output.get("action") == "bind-executable-route"
    )
    audit = context.audit_actor(label, output, base_audit, valid, ["executable-route.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {
            "authority": "ot-0186-bound-executable-route",
            "source_subject_digest": parent["artifact_digest"],
            "contradiction_receipt_digest": receipt["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "route": route,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "route": route, "binding": binding}


def evaluate_route(route, expression):
    if route is None:
        return {"passed": False, "pass_count": 0, "case_count": 16, "regimes": {}}
    regimes = {
        "blocked-option": expansion_result(
            mechanism_for(route, "blocked-option"), expression, CONFIRM_EXPANSION
        ),
        "observation-led": previous.result_for(
            mechanism_for(route, "observation-led"), expression, CONFIRM_OBSERVATION
        ),
        "mixed-observed-blocked": previous.result_for(
            mechanism_for(route, "mixed-observed-blocked"), expression, CONFIRM_MIXED
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
    run = (args.evidence_root or store / "runs/OT-0186").resolve()
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
    correction = f183["corrections"]["active"]
    subject, candidates = ot0183.compile_branch(p82, parent, correction, selector_base.CANDIDATES)
    expression = correction["binding"]["correction"]["mechanism"]
    candidate = {"rationale": inherited["rationale"], "routes": inherited["routes"]}
    receipt = public_receipt(p82, candidate, expression)
    initial_confirmation = evaluate_route(candidate, expression)

    checker = False
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "check"
        root.mkdir()
        seed = route_seed(
            root,
            parent,
            candidate,
            matrix,
            candidates,
            subject["active_mechanism_authority_projection"]["projection"],
            receipt,
        )
        checker = valid_route(json.loads((seed / "executable-route.json").read_text()), {row["mechanism_id"] for row in candidates})

    fixtures = {
        "checks": {
            "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST
            and parent["continuation"]["status"] == "open"
            and runtime.identity_conforms(parent),
            "inherited_route_exact": mechanism_for(candidate, "blocked-option")
            == expression["mechanism_id"],
            "public_route_fails_0_of_3": receipt["selected_result"]["pass_count"] == 0,
            "public_viable_passes_3_of_3": receipt["comparison_result"]["pass_count"] == 3,
            "initial_confirm_is_10_of_16": initial_confirmation["pass_count"] == 10,
            "route_checker_accepts_inherited": checker,
            "schema_present": ROUTE_SCHEMA.is_file(),
        },
        "contradiction_receipt_digest": receipt["receipt_digest"],
        "matrix_digest": matrix["matrix_digest"],
    }
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0186 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    authority_base.guide_base.write_json(run / "sealed-route-contradiction.json", receipt)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, run, repo)
    )
    rows = []
    counts = {"active": 0, "control": 0}
    schedule = ["control", "active", "active", "control", "control", "active", "active", "control"]
    for branch in schedule:
        counts[branch] += 1
        index = counts[branch]
        root = run / f"{branch}-{index:02d}-authoring"
        root.mkdir()
        branch_receipt = receipt if branch == "active" else erased_receipt(receipt)
        repair = run_repair(
            context,
            prior131,
            p82,
            root,
            f"{branch}-{index:02d}",
            parent,
            candidate,
            matrix,
            candidates,
            subject["active_mechanism_authority_projection"]["projection"],
            branch_receipt,
        )
        evaluation = evaluate_route(repair["binding"]["route"] if repair.get("binding") else None, expression)
        rows.append({"branch": branch, "index": index, "repair": repair, "evaluation": evaluation})

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
        "eight_fresh_actors_accepted": len(audits) == 8
        and all(prior131.audit_accepted(audit) for audit in audits),
        "active_4_of_4_full": active_full == 4,
        "control_at_most_1_of_4_full": control_full <= 1,
        "advantage_at_least_3": active_full - control_full >= 3,
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
            "authority": "ot-0186-executable-routing-selector",
            "source_subject_digest": parent["artifact_digest"],
            "contradiction_receipt_digest": receipt["receipt_digest"],
            "repair_binding_digest": first["repair"]["binding"]["binding_digest"],
            "route": first["repair"]["binding"]["route"],
        }
        artifact = {**artifact_body, "binding_digest": p82.digest(artifact_body)}
        child["executable_routing_selectors"] = [
            *child.get("executable_routing_selectors", []),
            artifact,
        ]
        child["active_executable_routing_selector"] = artifact
        child["routing_contradiction_receipts"] = [
            *child.get("routing_contradiction_receipts", []),
            receipt,
        ]
        final = p82.seal(child)

    result = {
        "authority": "ot-0186-consequence-revised-executable-routing",
        "source_subject_digest": parent["artifact_digest"],
        "contradiction_receipt": receipt,
        "initial_route_confirmation": initial_confirmation,
        "rows": [
            {**row, "repair": p82.compact(row["repair"])}
            for row in rows
        ],
        "active_full_pass_count": active_full,
        "control_full_pass_count": control_full,
        "identity_floor": identity,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": 8,
    }
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
