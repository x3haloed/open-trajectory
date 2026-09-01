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
BASE_PATH = ROOT / "ot_0204_subject_authored_pursuit_selector.py"
BASE_SHA256 = "8aebe17f760ab711e5234113d15158abeaab449fbcf1da937f0e0f2dbc5d395f"
PARENT_DIGEST = "cd6118363e23078ce770ca58c08f68c24733f578a55a579eb76e1856c21f438e"
SELECTOR_DIGEST = "eb8053c78554d0821056386e3150a9e3d41d6671a116e1ef59f52e89b3e8f6e9"
CANDIDATE_DIGEST = "7059568ca1a3ec431d45615b7fd3761f5e3e5cc2ac17f0153b15bd46fc5cf52c"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0204 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0205_frozen_ot0204", BASE_PATH)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


previous = load_base()
authority_base = previous.authority_base


def bounded_portfolio(portfolio):
    hidden = copy.deepcopy(portfolio)
    values = sorted({row["measurement"] for row in hidden["candidates"]})
    ranks = [-50, -30, -10, 10, 30, 50]
    mapping = {value: ranks[index] for index, value in enumerate(values)}
    for row in hidden["candidates"]:
        row["measurement"] = mapping[row["measurement"]]
    return hidden


previous.affine_portfolio = bounded_portfolio


def run_portfolio(context, prior131, p82, root, label, parent, visible_binding, target_binding, completion, representative_digest):
    result = previous.run_portfolio(context, prior131, p82, root, label, parent, visible_binding, target_binding, completion, representative_digest)
    binding = result.get("binding")
    if binding:
        body = {key: value for key, value in binding.items() if key not in {"authority", "binding_digest"}}
        body["authority"] = "ot-0205-bound-bounded-normalized-portfolio"
        result["binding"] = {**body, "binding_digest": p82.digest(body)}
        consequence = result.get("consequence")
        if consequence:
            cbody = {key: value for key, value in consequence.items() if key not in {"authority", "receipt_digest", "portfolio_binding_digest"}}
            cbody["authority"] = "ot-0205-bounded-selector-contact"
            cbody["portfolio_binding_digest"] = result["binding"]["binding_digest"]
            result["consequence"] = {**cbody, "receipt_digest": p82.digest(cbody)}
    return result


def main() -> int:
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0205").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0203", "open-subject-after-independent-generalization.json"); result204 = selector_base.load_artifact(p82, repo, store, "OT-0204", "subject-authored-pursuit-selector-aggregate.json"); renewal = result204["renewal"]; binding = renewal["binding"]; completion = parent["developmental_completion_receipts"][-1]; candidate = previous.compile_candidate(p82, parent, binding); control = previous.erased_binding(binding); representative_digest = p82.digest(binding["renewal"]["representative_portfolio"]); selector = binding["renewal"]["selector"]
    miss = next(row["choice"]["portfolio"] for row in result204["rows"] if row["branch"] == "active" and row["index"] == 6); old_hidden = copy.deepcopy(miss)
    for row in old_hidden["candidates"]: row["measurement"] = row["measurement"] * 3 + 7
    bounded_hidden = bounded_portfolio(miss)
    old_expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]; route_floor = previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], old_expression); operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0204_exact_rejection": result204["observer_disposition"] == "rejected" and result204["active_pass_count"] == 5 and result204["control_pass_count"] == 0, "selector_exact_clean": binding["binding_digest"] == SELECTOR_DIGEST and prior131.audit_accepted(renewal["audit"]), "candidate_exact": candidate["artifact_digest"] == CANDIDATE_DIGEST, "active06_public_valid": previous.checker.valid_portfolio(miss, selector), "old_affine_invalid": not previous.checker.valid_portfolio(old_hidden, selector), "bounded_normalization_valid": previous.checker.valid_portfolio(bounded_hidden, selector), "selection_preserved": miss["predicted_selection"] == previous.checker.selected_ids(bounded_hidden, selector), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schema_present": previous.PORTFOLIO_SCHEMA.is_file()}, "selector_binding_digest": binding["binding_digest"]}; fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only: print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0205 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); rows = []; counts = {"active": 0, "control": 0}
    for branch in ["control", "active", "active", "control"] * 3:
        counts[branch] += 1; index = counts[branch]; actor_root = run / f"{branch}-{index:02d}-authoring"; actor_root.mkdir(); choice = run_portfolio(context, prior131, p82, actor_root, f"{branch}-{index:02d}", candidate if branch == "active" else parent, binding if branch == "active" else control, binding, completion, representative_digest); rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["aligned"] and row["choice"]["hidden_stable"] for row in rows if row["branch"] == "active"); control_pass = sum(row["choice"]["aligned"] and row["choice"]["hidden_stable"] for row in rows if row["branch"] == "control"); audits = [row["choice"]["audit"] for row in rows]; first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1); selected_id = first["choice"]["portfolio"]["predicted_selection"][0] if first["choice"]["aligned"] else None; selected_stake = next((row["stake"] for row in first["choice"]["portfolio"]["candidates"] if row["stake"]["stake_id"] == selected_id), None) if selected_id else None
    checks = {"twelve_fresh_actors_accepted": len(audits) == 12 and all(prior131.audit_accepted(audit) for audit in audits), "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "all_active_bounded_stable": all(row["choice"]["hidden_stable"] for row in rows if row["branch"] == "active"), "selector_binding_exact": binding["binding_digest"] == SELECTOR_DIGEST, "selected_stake_canonical": previous.checker.valid_stake(selected_stake), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values()); final = parent
    if checks["passed"]:
        child = copy.deepcopy(candidate); child.pop("artifact_digest", None); child["pursuit_selector_capabilities"] = [*child.get("pursuit_selector_capabilities", []), {"authority": "ot-0205-executable-bounded-pursuit-selector", "selector_binding_digest": binding["binding_digest"], "selector": selector}]; selection_body = {"authority": "ot-0205-subject-selected-pursuit", "selector_binding_digest": binding["binding_digest"], "portfolio_binding_digest": first["choice"]["binding"]["binding_digest"], "consequence_receipt_digest": first["choice"]["consequence"]["receipt_digest"], "selected_stake": selected_stake}; selection = {**selection_body, "receipt_digest": p82.digest(selection_body)}; child["selected_pursuit_receipts"] = [*child.get("selected_pursuit_receipts", []), selection]; child["active_developmental_stake"] = selected_stake; child["continuation"] = {**child["continuation"], "status": "open", "next_opening": selected_stake["question"]}; child["unresolved"] = selected_stake["question"]; final = p82.seal(child)
    result = {"authority": "ot-0205-bounded-selector-normalization", "source_subject_digest": parent["artifact_digest"], "candidate_subject_digest": candidate["artifact_digest"], "selector_binding_digest": binding["binding_digest"], "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "route_floor": route_floor, "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "selected_stake_id": selected_id, "fresh_actor_count": 12}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
