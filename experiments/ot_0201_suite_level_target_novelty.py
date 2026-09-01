from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0200_subject_authored_target_language_expansion.py"
BASE_SHA256 = "e7d3e0bb03211cbb6d3d1185fc2e043ce19f527e60423d4460446aad7fa6cb11"
PARENT_DIGEST = "08c877ff66213187fa23330847a3d40b77568644e5a0f3923a6bf2426bb31fd0"
CANDIDATE_DIGEST = "a2991e6771729eac011077d338c29a700ca94ec52d8e62d2c8a67d3621431a77"
RENEWAL_DIGEST = "ee6e0a23ea2b1b85f75a4ce3c7fac561d0821a4da5342a3f75cec81498644573"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0200 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0201_frozen_ot0200", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.authority_base


def evaluate_suite(contact, pursuit):
    source_name = pursuit["source_extension"]["source_name"]
    rows = []
    for case in contact["cases"]:
        target = previous.execute(pursuit["expression"], case, source_name)
        signatures = previous.earned(case)
        basic = bool(target and target <= set(case["options"]) and not target & set(case["blocked"]) and set(case["prediction"]) == target)
        rows.append({"case_id": case["case_id"], "target": sorted(target), "earned": {key: sorted(value) for key, value in signatures.items()}, "basic_passed": basic})
    matches = {name: all(row["target"] == row["earned"][name] for row in rows) for name in previous.EARNED}
    return {"rows": rows, "all_cases_execute": all(row["basic_passed"] for row in rows), "earned_function_matches": matches, "suite_novel": not any(matches.values()), "passed": all(row["basic_passed"] for row in rows) and not any(matches.values())}


def run_contact(context, prior131, p82, root, label, parent, visible_binding, target_binding, prior_digest):
    seed = previous.contact_seed(root, parent, visible_binding)
    output, base_audit, workspace, _ = context.run_actor(label, seed, previous.CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        contact = json.loads((workspace / "contact.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        contact, immutable_ok = None, False
    structural = bool(contact and previous.valid_contact(contact))
    novel_artifact = bool(structural and p82.digest(contact) != prior_digest)
    valid = bool(structural and novel_artifact and immutable_ok and output and output.get("action") == "author-expanded-pursuit-contact")
    audit = context.audit_actor(label, output, base_audit, valid, ["contact.json"])
    pursuit = target_binding["renewal"]["next_pursuit"]
    source_name = pursuit["source_extension"]["source_name"]
    public = evaluate_suite(contact, pursuit) if structural and contact["source_name"] == source_name else {"rows": [], "all_cases_execute": False, "earned_function_matches": {}, "suite_novel": False, "passed": False}
    hidden = previous.hidden_cases(contact) if public["passed"] else []
    hidden_result = evaluate_suite({**contact, "cases": hidden}, pursuit) if hidden else {"rows": [], "all_cases_execute": False, "earned_function_matches": {}, "suite_novel": False, "passed": False}
    aligned = bool(valid and public["passed"] and hidden_result["passed"])
    binding = consequence = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0201-bound-suite-novel-contact", "source_subject_digest": parent["artifact_digest"], "renewal_binding_digest": visible_binding.get("binding_digest"), "actor_patch_digest": audit["patch_digest"], "contact": contact}
        binding = {**body, "binding_digest": p82.digest(body)}
        cbody = {"authority": "ot-0201-sealed-suite-novel-contact", "contact_binding_digest": binding["binding_digest"], "target_set": pursuit["target_set"], "hidden_contact_digest": p82.digest(hidden), "public_evaluation": public, "hidden_evaluation": hidden_result}
        consequence = {**cbody, "receipt_digest": p82.digest(cbody)}
    return {"output": output, "audit": audit, "contact": contact, "binding": binding, "consequence": consequence, "structural": structural, "novel": novel_artifact, "public_evaluation": public, "hidden_evaluation": hidden_result, "aligned": aligned}


def main() -> int:
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
    run = (args.evidence_root or store / "runs/OT-0201").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0199", "open-subject-after-latent-mechanism-invention.json")
    result200 = selector_base.load_artifact(p82, repo, store, "OT-0200", "subject-authored-target-language-expansion-aggregate.json")
    renewal = result200["renewal"]
    binding = renewal["binding"]
    candidate = previous.compile_candidate(p82, parent, binding)
    control = previous.erased_binding(binding)
    pursuit = binding["renewal"]["next_pursuit"]
    representative = binding["renewal"]["representative_contact"]
    rep_suite = evaluate_suite(representative, pursuit)
    expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]
    route_floor = previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression)
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0200_exact_rejection": result200["observer_disposition"] == "rejected" and result200["active_pass_count"] == 4 and result200["control_pass_count"] == 0, "renewal_exact_clean": binding["binding_digest"] == RENEWAL_DIGEST and authority_base.guide_base.prior131.audit_accepted(renewal["audit"]) if hasattr(authority_base.guide_base, "prior131") else renewal["audit"]["trace_regime"]["accepted"], "candidate_exact": candidate["artifact_digest"] == CANDIDATE_DIGEST, "representative_suite_novel": rep_suite["passed"], "representative_hidden_suite_novel": evaluate_suite({**representative, "cases": previous.hidden_cases(representative)}, pursuit)["passed"], "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schema_present": previous.CONTACT_SCHEMA.is_file()}, "renewal_binding_digest": binding["binding_digest"]}
    fixtures["checks"]["renewal_exact_clean"] = binding["binding_digest"] == RENEWAL_DIGEST and prior131.audit_accepted(renewal["audit"])
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "representative": rep_suite}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0201 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    rows, counts = [], {"active": 0, "control": 0}
    prior_digest = p82.digest(representative)
    for branch in ["control", "active", "active", "control"] * 3:
        counts[branch] += 1
        index = counts[branch]
        actor_root = run / f"{branch}-{index:02d}-authoring"
        actor_root.mkdir()
        choice = run_contact(context, prior131, p82, actor_root, f"{branch}-{index:02d}", candidate if branch == "active" else parent, binding if branch == "active" else control, binding, prior_digest)
        rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["aligned"] for row in rows if row["branch"] == "active")
    control_pass = sum(row["choice"]["aligned"] for row in rows if row["branch"] == "control")
    audits = [row["choice"]["audit"] for row in rows]
    checks = {"twelve_fresh_actors_accepted": len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits), "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "renewal_binding_exact": binding["binding_digest"] == RENEWAL_DIGEST, "candidate_exact": candidate["artifact_digest"] == CANDIDATE_DIGEST, "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1)
        child = copy.deepcopy(candidate)
        child.pop("artifact_digest", None)
        child["subject_originated_reopenings"] = [*child.get("subject_originated_reopenings", []), first["choice"]["binding"]]
        child["contact_consequence_receipts"] = [*child.get("contact_consequence_receipts", []), first["choice"]["consequence"]]
        operation_body = {"authority": "ot-0201-direct-suite-novel-pursuit-operation", "renewal_binding_digest": binding["binding_digest"], "contact_receipt_digest": first["choice"]["consequence"]["receipt_digest"], "operation": "open-generalized-mechanism-invention", "reason": "subject-authored target function is suite-novel and contactable"}
        child["direct_pursuit_transitions"] = [*child.get("direct_pursuit_transitions", []), {**operation_body, "operation_digest": p82.digest(operation_body)}]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Invent and consequence-test a mechanism for the subject-authored {pursuit['target_set']} pursuit."}
        final = p82.seal(child)
    result = {"authority": "ot-0201-suite-level-target-novelty", "source_subject_digest": parent["artifact_digest"], "candidate_subject_digest": candidate["artifact_digest"], "renewal_binding_digest": binding["binding_digest"], "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "route_floor": route_floor, "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 12}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
