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
BASE_PATH = ROOT / "ot_0191_subject_originated_post_repair_reopening.py"
BASE_SHA256 = "57a24ac9c50f677d3e4d93201217bb0e3037237a591627e35663313010aa33c1"
PARENT_DIGEST = "8f29e6a86c23f30e73378f222827a109f08a1f6d5eafc9766d0d9b43e44e6a35"
REPAIR_SCHEMA = REPO / "spec/ot-0192-predicate-repair.schema.json"
SUCCESSOR_SCHEMA = REPO / "spec/ot-0192-successor-operation.schema.json"
SETS = {"world-expected", "observed-unblocked", "latent-unblocked", "predicted-output"}
RELATIONS = {"includes-all", "excludes-all", "equals", "not-equals"}
QUANTIFIERS = {"all-cases", "any-case"}
OPERATIONS = {"surrender-or-revise", "retain-and-advance", "open-route-correction", "open-mechanism-invention", "open-unresolved-contact", "evaluate-machinery"}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0191 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0192_frozen_ot0191", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
ot0183 = previous.ot0183
authority_base = previous.authority_base


def valid_condition(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == {"left", "relation", "right", "quantifier", "on_true", "rationale"}
        and value.get("left") in SETS
        and value.get("right") in SETS
        and value.get("relation") in RELATIONS
        and value.get("quantifier") in QUANTIFIERS
        and value.get("on_true") in OPERATIONS
        and isinstance(value.get("rationale"), str)
        and value["rationale"].strip()
    )


def valid_projection(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"action", "rationale", "surrender", "success", "unresolved"}:
        return False
    if value.get("action") not in {"retain", "revise"} or not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        return False
    if value["action"] == "retain":
        return value.get("surrender") is None and value.get("success") is None and value.get("unresolved") is None
    unresolved = value.get("unresolved")
    return bool(
        valid_condition(value.get("surrender"))
        and valid_condition(value.get("success"))
        and isinstance(unresolved, dict)
        and set(unresolved) == {"operation", "rationale"}
        and unresolved.get("operation") in OPERATIONS - {"evaluate-machinery"}
        and isinstance(unresolved.get("rationale"), str)
        and unresolved["rationale"].strip()
    )


def case_sets(contact, consequence, predicted_id):
    hidden = ot0183.hidden_cases(contact)
    rows_by_id = {row["mechanism_id"]: row["result"]["rows"] for row in consequence["hidden_rows"]}
    predicted_rows = rows_by_id.get(predicted_id, [])
    values = []
    for index, case in enumerate(hidden):
        expected = set(next(iter(rows_by_id.values()))[index]["expected"])
        predicted = set(predicted_rows[index]["observed"] or []) if predicted_rows else set()
        observed = set(case["outcome"]) - set(case["blocked"])
        latent = set(case["options"]) - set(case["outcome"]) - set(case["blocked"])
        values.append({"world-expected": expected, "observed-unblocked": observed, "latent-unblocked": latent, "predicted-output": predicted})
    return values


def evaluate_condition(condition, values) -> bool:
    outcomes = []
    for row in values:
        left, right = row[condition["left"]], row[condition["right"]]
        relation = condition["relation"]
        outcomes.append(
            right <= left if relation == "includes-all"
            else left.isdisjoint(right) if relation == "excludes-all"
            else left == right if relation == "equals"
            else left != right
        )
    return all(outcomes) if condition["quantifier"] == "all-cases" else any(outcomes)


def machinery_operation(package, consequence):
    predicted = package["routing_hypothesis"]["mechanism_id"] if package["routing_hypothesis"]["classification"] == "installed" else None
    passing = sorted(row["mechanism_id"] for row in consequence["hidden_rows"] if row["result"]["passed"])
    if predicted and predicted in passing:
        return {"operation": "retain-and-advance", "failed_mechanism": None, "surviving_mechanism": predicted}
    if passing:
        return {"operation": "open-route-correction", "failed_mechanism": predicted, "surviving_mechanism": passing[0]}
    return {"operation": "open-mechanism-invention", "failed_mechanism": predicted, "surviving_mechanism": None}


def direct_operation(operation, package, consequence):
    if operation == "evaluate-machinery":
        return machinery_operation(package, consequence)
    machinery = machinery_operation(package, consequence)
    if operation == "open-route-correction":
        return {"operation": operation, "failed_mechanism": machinery["failed_mechanism"], "surviving_mechanism": machinery["surviving_mechanism"]}
    if operation == "retain-and-advance":
        return {"operation": operation, "failed_mechanism": None, "surviving_mechanism": machinery["surviving_mechanism"]}
    return {"operation": operation, "failed_mechanism": machinery["failed_mechanism"] if operation == "surrender-or-revise" else None, "surviving_mechanism": None}


def evaluate_projection(projection, package, consequence):
    predicted = package["routing_hypothesis"]["mechanism_id"] if package["routing_hypothesis"]["classification"] == "installed" else None
    values = case_sets(package["contact"], consequence, predicted)
    surrender = evaluate_condition(projection["surrender"], values)
    success = evaluate_condition(projection["success"], values)
    if surrender:
        terminal, source = projection["surrender"]["on_true"], "surrender"
    elif success:
        terminal, source = projection["success"]["on_true"], "success"
    else:
        terminal, source = projection["unresolved"]["operation"], "unresolved"
    body = {"surrender": surrender, "success": success, "nonoverlap": not (surrender and success), "source": source, **direct_operation(terminal, package, consequence)}
    return body


def repair_seed(root, parent, ot0191, package, consequence):
    seed = root / "predicate-seed"
    seed.mkdir()
    template = {"action": "retain", "rationale": "Replace after evaluating the prose-only ambiguity.", "surrender": None, "success": None, "unresolved": None}
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(parent),
        "reopening-package.json": package,
        "contact-consequence.json": consequence,
        "endpoint-rejection.json": ot0191,
        "pursuit-predicates.json": template,
        "mutation-envelope.json": {"editable": ["pursuit-predicates.json"], "immutable": ["subject-position.json", "reopening-package.json", "contact-consequence.json", "endpoint-rejection.json", "check_predicates.py"]},
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    (seed / "check_predicates.py").write_text(
        '''import json\nfrom pathlib import Path\np=json.loads(Path("pursuit-predicates.json").read_text()); sets={"world-expected","observed-unblocked","latent-unblocked","predicted-output"}; rel={"includes-all","excludes-all","equals","not-equals"}; quant={"all-cases","any-case"}; ops={"surrender-or-revise","retain-and-advance","open-route-correction","open-mechanism-invention","open-unresolved-contact","evaluate-machinery"}\ndef cond(c): return isinstance(c,dict) and set(c)=={"left","relation","right","quantifier","on_true","rationale"} and c.get("left") in sets and c.get("right") in sets and c.get("relation") in rel and c.get("quantifier") in quant and c.get("on_true") in ops and isinstance(c.get("rationale"),str) and bool(c["rationale"].strip())\na=p.get("action") if isinstance(p,dict) else None; u=p.get("unresolved") if isinstance(p,dict) else None; ok=isinstance(p,dict) and set(p)=={"action","rationale","surrender","success","unresolved"} and a in {"retain","revise"} and isinstance(p.get("rationale"),str) and bool(p["rationale"].strip()) and ((a=="retain" and p.get("surrender") is None and p.get("success") is None and u is None) or (a=="revise" and cond(p.get("surrender")) and cond(p.get("success")) and isinstance(u,dict) and set(u)=={"operation","rationale"} and u.get("operation") in ops-{"evaluate-machinery"} and isinstance(u.get("rationale"),str) and bool(u["rationale"].strip()))); print(json.dumps({"passed":bool(ok),"action":a})); raise SystemExit(0 if ok else 2)\n'''
    )
    (seed / "README.md").write_text(
        "Repair the prose-only pursuit authority by binding ordered executable predicates. Surrender is evaluated before success; unresolved owns the remainder. Use only the visible set expressions, relations, quantifiers, and operations in the template checker. Predicates must not make success and surrender overlap on the retained consequence. Edit only pursuit-predicates.json, run python3 check_predicates.py, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_repair(context, prior131, p82, root, parent, ot0191, package, consequence):
    label = "executable-pursuit-predicate-repair"
    seed = repair_seed(root, parent, ot0191, package, consequence)
    output, base_audit, workspace, _ = context.run_actor(label, seed, REPAIR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        projection = json.loads((workspace / "pursuit-predicates.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        projection, immutable_ok = None, False
    evaluation = evaluate_projection(projection, package, consequence) if isinstance(projection, dict) and projection.get("action") == "revise" and valid_projection(projection) else None
    valid = bool(valid_projection(projection) and projection["action"] == "revise" and evaluation and evaluation["nonoverlap"] and immutable_ok and output and output.get("action") == "author-executable-pursuit-predicates")
    audit = context.audit_actor(label, output, base_audit, valid, ["pursuit-predicates.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0192-bound-executable-pursuit-predicates", "source_subject_digest": parent["artifact_digest"], "ot0191_receipt_digest": ot0191["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "projection": projection}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "projection": projection, "evaluation": evaluation, "binding": binding}


def erased_projection(binding):
    return {"authority": binding["authority"], "source_subject_digest": binding["source_subject_digest"], "ot0191_receipt_digest": binding["ot0191_receipt_digest"], "actor_patch_digest": None, "projection": None, "binding_digest": None}


def successor_seed(root, parent, package, consequence, predicates):
    seed = root / "successor-seed"
    seed.mkdir()
    template = {"operation": "retain-and-advance", "failed_mechanism": None, "surviving_mechanism": None, "rationale": "Replace from raw consequence and inherited predicates.", "next_opening": "Replace with an actionable opening."}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "reopening-package.json": package, "contact-consequence.json": consequence, "pursuit-predicates.json": predicates, "successor-action.json": template, "mutation-envelope.json": {"editable": ["successor-action.json"], "immutable": ["subject-position.json", "reopening-package.json", "contact-consequence.json", "pursuit-predicates.json"]}}
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    (seed / "README.md").write_text(
        "Bind the next operation from raw consequence and inherited pursuit predicates. A populated predicate projection is executable developmental authority; null predicate fields carry no authority. Choose surrender-or-revise, retain-and-advance, open-route-correction, open-mechanism-invention, or open-unresolved-contact. Edit only successor-action.json and report truthfully.\n"
    )
    return seed


def valid_successor(value: Any, ids: set[str]) -> bool:
    return bool(isinstance(value, dict) and set(value) == {"operation", "failed_mechanism", "surviving_mechanism", "rationale", "next_opening"} and value.get("operation") in OPERATIONS - {"evaluate-machinery"} and value.get("failed_mechanism") in ids | {None} and value.get("surviving_mechanism") in ids | {None} and isinstance(value.get("rationale"), str) and value["rationale"].strip() and isinstance(value.get("next_opening"), str) and value["next_opening"].strip())


def run_successor(context, prior131, p82, root, label, parent, package, consequence, predicates, ids, expected):
    seed = successor_seed(root, parent, package, consequence, predicates)
    output, base_audit, workspace, _ = context.run_actor(label, seed, SUCCESSOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "successor-action.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        value, immutable_ok = None, False
    valid = bool(valid_successor(value, ids) and immutable_ok and output and output.get("action") == "bind-predicate-derived-operation")
    audit = context.audit_actor(label, output, base_audit, valid, ["successor-action.json"])
    appropriate = bool(value and value["operation"] == expected["operation"] and value["failed_mechanism"] == expected["failed_mechanism"] and value["surviving_mechanism"] == expected["surviving_mechanism"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0192-bound-predicate-derived-operation", "source_subject_digest": parent["artifact_digest"], "predicate_binding_digest": predicates.get("binding_digest"), "actor_patch_digest": audit["patch_digest"], "successor_action": value}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "successor_action": value, "binding": binding, "appropriate": appropriate and binding is not None}


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
    run = (args.evidence_root or store / "runs/OT-0192").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0190", "open-subject-after-executable-route-repair.json")
    ot0191 = selector_base.load_artifact(p82, repo, store, "OT-0191", "subject-originated-post-repair-reopening-aggregate.json")
    package = selector_base.load_artifact(p82, repo, store, "OT-0191", "actor-authored-reopening-package.json")
    consequence = selector_base.load_artifact(p82, repo, store, "OT-0191", "sealed-subject-originated-contact.json")
    ids = {row["mechanism_id"] for row in consequence["hidden_rows"]}
    representative = {
        "action": "revise",
        "rationale": "Let the world decide whether the latent-expansion stake survives before correcting machinery.",
        "surrender": {"left": "world-expected", "relation": "excludes-all", "right": "latent-unblocked", "quantifier": "all-cases", "on_true": "surrender-or-revise", "rationale": "Surrender when world-required output excludes every latent option in all cases."},
        "success": {"left": "world-expected", "relation": "includes-all", "right": "latent-unblocked", "quantifier": "all-cases", "on_true": "evaluate-machinery", "rationale": "Only evaluate route correctness when the world requires every latent option."},
        "unresolved": {"operation": "open-unresolved-contact", "rationale": "Seek more contact when neither terminal condition holds."},
    }
    representative_eval = evaluate_projection(representative, package, consequence)
    novel_candidate = parent["actor_authored_contact_mechanisms"][-1]
    route_floor = previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], novel_candidate["expression"])
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0191_exact_rejection": ot0191["observer_disposition"] == "rejected" and ot0191["active_pass_count"] == 4 and ot0191["control_pass_count"] == 0, "representative_valid": valid_projection(representative), "representative_nonoverlap": representative_eval["nonoverlap"], "representative_surrenders": representative_eval["operation"] == "surrender-or-revise", "deterministic_replay": representative_eval == evaluate_projection(representative, package, consequence), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "schemas_present": REPAIR_SCHEMA.is_file() and SUCCESSOR_SCHEMA.is_file()}, "representative_digest": p82.digest(representative)}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0192 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    root = run / "predicate-repair-authoring"
    root.mkdir()
    repair = run_repair(context, prior131, p82, root, parent, ot0191, package, consequence)
    if not repair.get("binding"):
        result = {"authority": "ot-0192-executable-pursuit-consequence", "repair": p82.compact(repair), "checks": {"repair_accepted": False, "passed": False}, "observer_disposition": "rejected", "final_subject_digest": parent["artifact_digest"], "fresh_actor_count": 1}
        result["receipt_digest"] = p82.digest(result)
        authority_base.guide_base.write_json(run / "aggregate.json", result)
        authority_base.guide_base.write_json(run / "final-full-subject.json", parent)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    evaluation_body = {"authority": "ot-0192-evaluated-pursuit-consequence", "predicate_binding_digest": repair["binding"]["binding_digest"], **repair["evaluation"]}
    evaluation = {**evaluation_body, "receipt_digest": p82.digest(evaluation_body)}
    authority_base.guide_base.write_json(run / "evaluated-pursuit-consequence.json", evaluation)
    active_predicates = {**repair["binding"], "evaluation_receipt_digest": evaluation["receipt_digest"]}
    control_predicates = erased_projection(repair["binding"])
    expected = {key: evaluation[key] for key in ("operation", "failed_mechanism", "surviving_mechanism")}
    rows = []
    counts = {"active": 0, "control": 0}
    for branch in ["control", "active", "active", "control"] * 3:
        counts[branch] += 1
        index = counts[branch]
        actor_root = run / f"{branch}-{index:02d}-authoring"
        actor_root.mkdir()
        choice = run_successor(context, prior131, p82, actor_root, f"{branch}-{index:02d}", parent, package, consequence, active_predicates if branch == "active" else control_predicates, ids, expected)
        rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["appropriate"] for row in rows if row["branch"] == "active")
    control_pass = sum(row["choice"]["appropriate"] for row in rows if row["branch"] == "control")
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    audits = [repair["audit"], *[row["choice"]["audit"] for row in rows]]
    checks = {"thirteen_fresh_actors_accepted": len(audits) == 13 and all(prior131.audit_accepted(audit) for audit in audits), "predicate_nonoverlap": evaluation["nonoverlap"], "deterministic_predicate_replay": repair["evaluation"] == evaluate_projection(repair["projection"], package, consequence), "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1)
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        child["executable_pursuit_predicates"] = [*child.get("executable_pursuit_predicates", []), repair["binding"]]
        child["pursuit_consequence_receipts"] = [*child.get("pursuit_consequence_receipts", []), evaluation]
        child["post_repair_operations"] = [*child.get("post_repair_operations", []), first["choice"]["binding"]]
        if evaluation["operation"] == "surrender-or-revise":
            child["pending_stake_revisions"] = [*child.get("pending_stake_revisions", []), {"surrendered_candidate_stake": package["next_stake"], "evaluation_receipt_digest": evaluation["receipt_digest"]}]
        else:
            child["active_developmental_stake"] = package["next_stake"]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": first["choice"]["successor_action"]["next_opening"]}
        final = p82.seal(child)
    result = {"authority": "ot-0192-executable-pursuit-consequence", "source_subject_digest": parent["artifact_digest"], "repair": p82.compact(repair), "evaluation": evaluation, "expected_operation": expected, "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "route_floor": route_floor, "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 13}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
