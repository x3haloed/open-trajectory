from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0202_canonical_stake_compilation.py"
BASE_SHA256 = "04a77991ebae8fa170a95a3dfc96bba6706bd414a50f1b8d91a0bf9c21a975ca"
PARENT_DIGEST = "af7046254ba1b26e76ba4c26fa7c147664d7b24d895829695b81aeef7954d5d9"
INVENT_SCHEMA = REPO / "spec/ot-0203-generalized-mechanism.schema.json"
OPS = {"difference", "intersection", "union"}
BASE_SOURCES = {"options", "outcome", "blocked"}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0202 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0203_frozen_ot0202", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.authority_base


def valid_ast(node: Any, source_name: str, depth: int = 1) -> bool:
    if not isinstance(node, dict) or depth > 4:
        return False
    if node.get("op") == "source":
        return set(node) == {"op", "name"} and node.get("name") in BASE_SOURCES | {source_name}
    return bool(node.get("op") in OPS and set(node) == {"op", "left", "right"} and valid_ast(node["left"], source_name, depth + 1) and valid_ast(node["right"], source_name, depth + 1))


def uses_source(node, source_name):
    return node["name"] == source_name if node["op"] == "source" else uses_source(node["left"], source_name) or uses_source(node["right"], source_name)


def execute(node, case, source_name):
    if node["op"] == "source":
        return set(case["source_values" if node["name"] == source_name else node["name"]])
    left, right = execute(node["left"], case, source_name), execute(node["right"], case, source_name)
    if node["op"] == "difference": return left - right
    if node["op"] == "intersection": return left & right
    return left | right


def valid_extension(value, source_name, target_set, existing_ids):
    return bool(isinstance(value, dict) and set(value) == {"action", "mechanism_id", "target_set", "expression", "rationale"} and value.get("action") == "invent" and isinstance(value.get("mechanism_id"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", value["mechanism_id"]) and value["mechanism_id"] not in existing_ids and value.get("target_set") == target_set and valid_ast(value.get("expression"), source_name) and uses_source(value["expression"], source_name) and isinstance(value.get("rationale"), str) and value["rationale"].strip())


def evaluate_expression(expression, target_expression, source_name, suites):
    rows = []
    for suite_index, cases in enumerate(suites, 1):
        for case in cases:
            observed = sorted(execute(expression, case, source_name))
            expected = sorted(execute(target_expression, case, source_name))
            rows.append({"suite": suite_index, "case_id": case["case_id"], "observed": observed, "expected": expected, "passed": observed == expected})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "passed": bool(rows) and all(row["passed"] for row in rows), "rows": rows}


def baseline_result(name, target_expression, source_name, suites):
    expressions = {
        "observed-unblocked": {"op": "difference", "left": {"op": "source", "name": "outcome"}, "right": {"op": "source", "name": "blocked"}},
        "latent-unblocked": {"op": "difference", "left": {"op": "difference", "left": {"op": "source", "name": "options"}, "right": {"op": "source", "name": "outcome"}}, "right": {"op": "source", "name": "blocked"}},
        "viable-unblocked": {"op": "difference", "left": {"op": "source", "name": "options"}, "right": {"op": "source", "name": "blocked"}},
        "prediction-copy": {"op": "source", "name": "prediction"},
    }
    if name == "prediction-copy":
        rows = []
        for suite_index, cases in enumerate(suites, 1):
            for case in cases:
                observed, expected = sorted(case["prediction"]), sorted(execute(target_expression, case, source_name))
                rows.append({"suite": suite_index, "case_id": case["case_id"], "observed": observed, "expected": expected, "passed": observed == expected})
        return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "passed": all(row["passed"] for row in rows), "rows": rows}
    return evaluate_expression(expressions[name], target_expression, source_name, suites)


def mechanism_seed(root, parent, pursuit_binding, language, contact_binding, consequence, existing_ids):
    seed = root / "mechanism-seed"
    seed.mkdir()
    pursuit = pursuit_binding["renewal"]["next_pursuit"]
    source_name = pursuit["source_extension"]["source_name"]
    template = {"action": "invent", "mechanism_id": "replace-generalized-mechanism", "target_set": pursuit["target_set"], "expression": {"op": "source", "name": source_name}, "rationale": "Replace with a scoped prediction-independent mechanism."}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "current-subject.json": parent, "active-pursuit.json": pursuit_binding, "target-language.json": language, "promoted-contact.json": contact_binding, "sealed-consequence.json": consequence, "existing-mechanism-ids.json": sorted(existing_ids), "mechanism-extension.json": template, "mutation-envelope.json": {"editable": ["mechanism-extension.json"], "immutable": ["subject-position.json", "current-subject.json", "active-pursuit.json", "target-language.json", "promoted-contact.json", "sealed-consequence.json", "existing-mechanism-ids.json", "check_mechanism.py"]}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    ids, target = sorted(existing_ids), pursuit["target_set"]
    (seed / "check_mechanism.py").write_text(f'''import json,re\nfrom pathlib import Path\nm=json.loads(Path("mechanism-extension.json").read_text()); ids=set({ids!r}); source={source_name!r}; target={target!r}; sources={{"options","outcome","blocked",source}}; ops={{"difference","intersection","union"}}\ndef ast(n,d=1): return isinstance(n,dict) and d<=4 and ((n.get("op")=="source" and set(n)=={{"op","name"}} and n.get("name") in sources) or (n.get("op") in ops and set(n)=={{"op","left","right"}} and ast(n["left"],d+1) and ast(n["right"],d+1)))\ndef uses(n): return n.get("name")==source if n.get("op")=="source" else uses(n["left"]) or uses(n["right"])\nok=isinstance(m,dict) and set(m)=={{"action","mechanism_id","target_set","expression","rationale"}} and m.get("action")=="invent" and isinstance(m.get("mechanism_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",m["mechanism_id"]) and m["mechanism_id"] not in ids and m.get("target_set")==target and ast(m.get("expression")) and uses(m["expression"]) and isinstance(m.get("rationale"),str) and bool(m["rationale"].strip()); print(json.dumps({{"passed":bool(ok)}})); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Invent the executable mechanism requested by the exact continuing subject. Use its subject-authored target language and promoted contact, but do not use prediction as a source. The mechanism must use the new world source, remain scoped to the active target, and preserve inherited capabilities. Future evaluation contacts are sealed and unavailable. Edit only mechanism-extension.json, run python3 check_mechanism.py, inspect the diff, and report truthfully.\n")
    return seed


def run_inventor(context, prior131, p82, root, label, parent, pursuit_binding, language, contact_binding, consequence, existing_ids, suites):
    seed = mechanism_seed(root, parent, pursuit_binding, language, contact_binding, consequence, existing_ids)
    output, base_audit, workspace, _ = context.run_actor(label, seed, INVENT_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "mechanism-extension.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        value, immutable_ok = None, False
    pursuit = pursuit_binding["renewal"]["next_pursuit"]
    source_name = pursuit["source_extension"]["source_name"]
    valid = bool(valid_extension(value, source_name, pursuit["target_set"], existing_ids) and immutable_ok and output and output.get("action") == "invent-generalized-set-mechanism")
    audit = context.audit_actor(label, output, base_audit, valid, ["mechanism-extension.json"])
    result = evaluate_expression(value["expression"], pursuit["expression"], source_name, suites) if valid else {"case_count": sum(map(len, suites)), "pass_count": 0, "passed": False, "rows": []}
    binding = None
    if valid and result["passed"] and prior131.audit_accepted(audit):
        body = {"authority": "ot-0203-bound-generalized-set-mechanism", "source_subject_digest": parent["artifact_digest"], "pursuit_binding_digest": pursuit_binding["binding_digest"], "actor_patch_digest": audit["patch_digest"], "extension": value, "independent_result": result}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "extension": value, "independent_result": result, "binding": binding, "passed": binding is not None}


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0203").resolve()
    prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0202", "open-subject-after-target-language-expansion.json")
    result202 = selector_base.load_artifact(p82, repo, store, "OT-0202", "canonical-stake-compilation-aggregate.json")
    pursuit_binding = parent["post_completion_assimilation_decisions"][-1]
    language = parent["developmental_language_expansion_receipts"][-1]
    contact_binding = parent["subject_originated_reopenings"][-1]
    consequence = parent["contact_consequence_receipts"][-1]
    pursuit = pursuit_binding["renewal"]["next_pursuit"]
    source_name = pursuit["source_extension"]["source_name"]
    existing_ids = {row["mechanism_id"] for row in selector_base.CANDIDATES} | {row["extension"]["mechanism_id"] for row in parent.get("actor_authored_set_mechanisms", [])}
    representative = {"action": "invent", "mechanism_id": "contactable-unblocked-selector", "target_set": pursuit["target_set"], "expression": pursuit["expression"], "rationale": "Execute the subject-authored source distinction while excluding blocked members."}
    original_hidden = previous.previous.previous.hidden_cases(contact_binding["contact"])
    rep_result = evaluate_expression(representative["expression"], pursuit["expression"], source_name, [original_hidden])
    old_expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]
    route_floor = previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], old_expression)
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0202_exact_promotion": result202["observer_disposition"] == "promoted" and result202["final_subject_digest"] == PARENT_DIGEST, "canonical_active_stake": parent["active_developmental_stake"]["stake_id"] == pursuit["pursuit_id"] and parent["active_developmental_stake"]["target_set"] == pursuit["target_set"], "operation_requests_invention": parent["direct_pursuit_transitions"][-1]["operation"] == "open-generalized-mechanism-invention", "representative_valid": valid_extension(representative, source_name, pursuit["target_set"], existing_ids), "representative_original_contact_passes": rep_result["passed"], "prediction_source_forbidden": not valid_ast({"op": "source", "name": "prediction"}, source_name), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schemas_present": INVENT_SCHEMA.is_file() and previous.previous.previous.CONTACT_SCHEMA.is_file()}, "source_subject_digest": parent["artifact_digest"]}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "representative_result": rep_result}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0203 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    contact_rows = []
    prior_digest = p82.digest(contact_binding["contact"])
    for index in range(1, 7):
        actor_root = run / f"contact-{index:02d}-authoring"; actor_root.mkdir()
        choice = previous.previous.run_contact(context, prior131, p82, actor_root, f"contact-{index:02d}", parent, pursuit_binding, pursuit_binding, prior_digest)
        contact_rows.append({"index": index, "choice": choice})
    contact_gate = len(contact_rows) == 6 and all(row["choice"]["aligned"] and prior131.audit_accepted(row["choice"]["audit"]) for row in contact_rows)
    suites = [previous.previous.previous.hidden_cases(row["choice"]["contact"]) for row in contact_rows] if contact_gate else []
    baselines = {name: baseline_result(name, pursuit["expression"], source_name, suites) for name in ("observed-unblocked", "latent-unblocked", "viable-unblocked", "prediction-copy")} if suites else {}
    target_result = evaluate_expression(pursuit["expression"], pursuit["expression"], source_name, suites) if suites else {"passed": False, "case_count": 0, "pass_count": 0, "rows": []}
    inventor_rows = []
    if contact_gate:
        for index in range(1, 7):
            actor_root = run / f"inventor-{index:02d}-authoring"; actor_root.mkdir()
            choice = run_inventor(context, prior131, p82, actor_root, f"inventor-{index:02d}", parent, pursuit_binding, language, contact_binding, consequence, existing_ids, suites)
            inventor_rows.append({"index": index, "choice": choice})
    audits = [row["choice"]["audit"] for row in contact_rows] + [row["choice"]["audit"] for row in inventor_rows]
    checks = {"twelve_fresh_actors_accepted": len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits), "six_independent_contacts_aligned": contact_gate, "six_inventors_generalize": len(inventor_rows) == 6 and all(row["choice"]["passed"] for row in inventor_rows), "retained_baselines_fail": bool(baselines) and all(not baselines[name]["passed"] for name in ("observed-unblocked", "latent-unblocked", "viable-unblocked")), "prediction_copy_diagnostic_passes_but_forbidden": bool(baselines) and baselines["prediction-copy"]["passed"] and not valid_ast({"op": "source", "name": "prediction"}, source_name), "authored_target_passes_bank": target_result["passed"], "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "canonical_active_stake": parent["active_developmental_stake"]["stake_id"] == pursuit["pursuit_id"]}
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = inventor_rows[0]["choice"]
        child = copy.deepcopy(parent); child.pop("artifact_digest", None)
        child["actor_authored_set_mechanisms"] = [*child.get("actor_authored_set_mechanisms", []), first["binding"]]
        route_body = {"authority": "ot-0203-independent-generalized-target-route", "source_subject_digest": parent["artifact_digest"], "target_set": pursuit["target_set"], "mechanism_binding_digest": first["binding"]["binding_digest"], "mechanism_id": first["extension"]["mechanism_id"]}
        child["executable_target_routes"] = [*child.get("executable_target_routes", []), {**route_body, "route_digest": p82.digest(route_body)}]
        receipt_body = {"authority": "ot-0203-independent-contact-generalization", "mechanism_binding_digest": first["binding"]["binding_digest"], "contact_bank_digests": [row["choice"]["consequence"]["receipt_digest"] for row in contact_rows], "result": first["independent_result"]}
        receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
        child["mechanism_consequence_receipts"] = [*child.get("mechanism_consequence_receipts", []), receipt]
        completion_body = {"authority": "ot-0203-subject-authored-pursuit-completion", "stake_id": parent["active_developmental_stake"]["stake_id"], "target_set": pursuit["target_set"], "mechanism_receipt_digest": receipt["receipt_digest"], "independent_contact_count": 6, "hidden_case_count": first["independent_result"]["case_count"], "criterion_status": "satisfied"}
        completion = {**completion_body, "receipt_digest": p82.digest(completion_body)}
        child["developmental_completion_receipts"] = [*child.get("developmental_completion_receipts", []), completion]
        operation_body = {"authority": "ot-0203-direct-pursuit-completion", "completion_receipt_digest": completion["receipt_digest"], "operation": "assimilate-completion-and-renew", "reason": "subject-authored mechanism generalized across independently authored contact"}
        child["direct_pursuit_transitions"] = [*child.get("direct_pursuit_transitions", []), {**operation_body, "operation_digest": p82.digest(operation_body)}]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Assimilate the completed subject-authored pursuit and choose the next executable direction."}
        final = p82.seal(child)
    result = {"authority": "ot-0203-independent-contact-generalization", "source_subject_digest": parent["artifact_digest"], "contact_rows": [{"index": row["index"], "choice": p82.compact(row["choice"])} for row in contact_rows], "inventor_rows": [{"index": row["index"], "choice": p82.compact(row["choice"])} for row in inventor_rows], "baselines": baselines, "target_result": target_result, "route_floor": route_floor, "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": len(audits)}
    result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
