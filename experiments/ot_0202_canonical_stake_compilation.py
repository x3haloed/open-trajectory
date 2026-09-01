from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0201_suite_level_target_novelty.py"
BASE_SHA256 = "6a865acce7ba49f8674005b4232d1b1833410f2bcdc63913f1823238cb76b531"
CONSUMER_PATH = ROOT / "ot_0184_capability_scoped_selector_repair.py"
CONSUMER_SHA256 = "f280505aa25804f9670732add5e3e4e602b864ad51463fc28d53c7c7d39982d8"
PARENT_DIGEST = "08c877ff66213187fa23330847a3d40b77568644e5a0f3923a6bf2426bb31fd0"
RENEWAL_DIGEST = "ee6e0a23ea2b1b85f75a4ce3c7fac561d0821a4da5342a3f75cec81498644573"
STAKE_KEYS = {"stake_id", "property", "target_set", "question", "rationale", "success_condition", "surrender_condition"}


def load_module(path, expected, name):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"{path.name} changed")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_module(BASE_PATH, BASE_SHA256, "ot0202_frozen_ot0201")
consumer = load_module(CONSUMER_PATH, CONSUMER_SHA256, "ot0202_frozen_ot0184")
authority_base = previous.authority_base


def compile_candidate(p82, parent, binding):
    child = previous.previous.compile_candidate(p82, parent, binding)
    child = copy.deepcopy(child)
    child.pop("artifact_digest", None)
    stake = child["active_developmental_stake"]
    stake["stake_id"] = stake.pop("pursuit_id")
    child["active_developmental_stake"] = stake
    return p82.seal(child)


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
    run = (args.evidence_root or store / "runs/OT-0202").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0199", "open-subject-after-latent-mechanism-invention.json")
    result200 = selector_base.load_artifact(p82, repo, store, "OT-0200", "subject-authored-target-language-expansion-aggregate.json")
    result201 = selector_base.load_artifact(p82, repo, store, "OT-0201", "suite-level-target-novelty-aggregate.json")
    binding = result200["renewal"]["binding"]
    candidate = compile_candidate(p82, parent, binding)
    control = previous.previous.erased_binding(binding)
    pursuit = binding["renewal"]["next_pursuit"]
    representative = binding["renewal"]["representative_contact"]
    expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]
    route_floor = previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression)
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    downstream = False
    with tempfile.TemporaryDirectory() as temp:
        seed = consumer.repair_seed(Path(temp), candidate, {"observer_disposition": "fixture"}, selector_base.CANDIDATES, candidate["active_mechanism_authority_projection"])
        downstream = json.loads((seed / "active-stake.json").read_text()) == candidate["active_developmental_stake"]
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0201_behavior_exact_but_nonpromotable": result201["active_pass_count"] == 6 and result201["control_pass_count"] == 0 and result201["final_subject_digest"] != parent["artifact_digest"], "renewal_exact": binding["binding_digest"] == RENEWAL_DIGEST and prior131.audit_accepted(result200["renewal"]["audit"]), "canonical_stake_keys": set(candidate["active_developmental_stake"]) == STAKE_KEYS and "pursuit_id" not in candidate["active_developmental_stake"], "canonical_stake_identity": candidate["active_developmental_stake"]["stake_id"] == pursuit["pursuit_id"], "candidate_runtime_conforms": runtime.identity_conforms(candidate) and candidate["continuation"]["status"] == "open", "production_downstream_consumer_constructs": downstream, "representative_suite_novel": previous.evaluate_suite(representative, pursuit)["passed"], "representative_hidden_suite_novel": previous.evaluate_suite({**representative, "cases": previous.previous.hidden_cases(representative)}, pursuit)["passed"], "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schema_present": previous.previous.CONTACT_SCHEMA.is_file()}, "candidate_subject_digest": candidate["artifact_digest"], "renewal_binding_digest": binding["binding_digest"]}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "consumer_sha256": CONSUMER_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0202 evidence")
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
        choice = previous.run_contact(context, prior131, p82, actor_root, f"{branch}-{index:02d}", candidate if branch == "active" else parent, binding if branch == "active" else control, binding, prior_digest)
        rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["aligned"] for row in rows if row["branch"] == "active")
    control_pass = sum(row["choice"]["aligned"] for row in rows if row["branch"] == "control")
    audits = [row["choice"]["audit"] for row in rows]
    checks = {"twelve_fresh_actors_accepted": len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits), "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "renewal_binding_exact": binding["binding_digest"] == RENEWAL_DIGEST, "canonical_stake_compiled": set(candidate["active_developmental_stake"]) == STAKE_KEYS, "production_downstream_consumer_constructs": downstream, "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1)
        child = copy.deepcopy(candidate)
        child.pop("artifact_digest", None)
        child["subject_originated_reopenings"] = [*child.get("subject_originated_reopenings", []), first["choice"]["binding"]]
        child["contact_consequence_receipts"] = [*child.get("contact_consequence_receipts", []), first["choice"]["consequence"]]
        operation_body = {"authority": "ot-0202-direct-canonical-expanded-pursuit-operation", "renewal_binding_digest": binding["binding_digest"], "contact_receipt_digest": first["choice"]["consequence"]["receipt_digest"], "operation": "open-generalized-mechanism-invention", "reason": "canonical subject-authored target function is suite-novel and contactable"}
        child["direct_pursuit_transitions"] = [*child.get("direct_pursuit_transitions", []), {**operation_body, "operation_digest": p82.digest(operation_body)}]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Invent and consequence-test a mechanism for the subject-authored {pursuit['target_set']} pursuit."}
        final = p82.seal(child)
    result = {"authority": "ot-0202-canonical-stake-compilation", "source_subject_digest": parent["artifact_digest"], "candidate_subject_digest": candidate["artifact_digest"], "renewal_binding_digest": binding["binding_digest"], "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "route_floor": route_floor, "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 12}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
