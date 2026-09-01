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
BASE_PATH = ROOT / "ot_0203_independent_contact_generalization.py"
BASE_SHA256 = "6163199952d1e622da20862782dacee6bfe7024ba092b97b2179ea1208b75155"
CHECKER_PATH = ROOT / "ot_0204_checker.py"
CHECKER_SHA256 = "2c6bf8636cf27efd6bc6b3f3115909b62fda1f3b7bc58a2bca3010fcbceb6885"
PARENT_DIGEST = "cd6118363e23078ce770ca58c08f68c24733f578a55a579eb76e1856c21f438e"
RENEWAL_SCHEMA = REPO / "spec/ot-0204-selector-renewal.schema.json"
PORTFOLIO_SCHEMA = REPO / "spec/ot-0204-portfolio-author.schema.json"


def load_module(path, expected, name):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"{path.name} changed")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_module(BASE_PATH, BASE_SHA256, "ot0204_frozen_ot0203")
checker = load_module(CHECKER_PATH, CHECKER_SHA256, "ot0204_frozen_checker")
authority_base = previous.authority_base


def sample_stake(index: int) -> dict:
    return {"stake_id": f"candidate-pursuit-{index}", "property": f"candidate-property-{index}", "target_set": f"candidate-target-{index}", "question": f"What objectively contactable direction {index} should follow completion?", "rationale": "Replace with a distinct candidate and why it could continue the lineage.", "success_condition": "Replace with an objective success boundary.", "surrender_condition": "Replace with an objective surrender boundary."}


def renewal_seed(root, parent, completion):
    seed = root / "renewal-seed"; seed.mkdir()
    selector = {"selector_id": "replace-pursuit-selector", "dimension_name": "replace-dimension", "world_meaning": "Define what the world measures about candidate pursuits.", "direction": "maximize", "missing_policy": "reject-portfolio", "blocked_policy": "exclude", "tie_policy": "preserve-all-extrema", "rationale": "Explain why this dimension should improve future pursuit selection."}
    portfolio = {"portfolio_id": "representative-pursuit-portfolio", "dimension_name": "replace-dimension", "rationale": "Demonstrate the authored selector on complete candidate stakes.", "candidates": [{"stake": sample_stake(index), "measurement": index, "blocked": index == 4} for index in range(1, 5)], "predicted_selection": ["candidate-pursuit-3"]}
    template = {"action": "assimilate-completion-and-install-selector", "prior_disposition": "completed-assimilated", "completion_receipt_digest": completion["receipt_digest"], "selector": selector, "representative_portfolio": portfolio, "rationale": "Assimilate completion and make what counts as a better next pursuit executable."}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "current-subject.json": parent, "completed-stake.json": parent["active_developmental_stake"], "completion-receipt.json": completion, "selector-renewal.json": template, "mutation-envelope.json": {"editable": ["selector-renewal.json"], "immutable": ["subject-position.json", "current-subject.json", "completed-stake.json", "completion-receipt.json", "check_common.py", "check_renewal.py"]}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    (seed / "check_common.py").write_bytes(CHECKER_PATH.read_bytes())
    (seed / "check_renewal.py").write_text("""import json\nfrom pathlib import Path\nimport check_common as c\nv=json.loads(Path('selector-renewal.json').read_text()); r=json.loads(Path('completion-receipt.json').read_text()); ok=c.valid_renewal(v,r['receipt_digest']); print(json.dumps({'passed':bool(ok)})); raise SystemExit(0 if ok else 2)\n""")
    (seed / "README.md").write_text("The current pursuit is objectively complete. Assimilate its exact receipt and improve how the continuing subject selects future pursuits. Author one new world-measured scalar dimension, choose whether higher or lower is preferable, and demonstrate it on a portfolio of complete candidate stakes. The dimension, meaning, direction, candidates, measurements, and choice are yours; old object-level target names are not valid dimensions. Blocked pursuits are excluded, missing measurement rejects the portfolio, and tied extrema remain open together. Edit only selector-renewal.json, run python3 check_renewal.py, inspect the diff, and report truthfully.\n")
    return seed


def run_renewal(context, prior131, p82, root, parent, completion):
    seed = renewal_seed(root, parent, completion)
    output, base_audit, workspace, _ = context.run_actor("pursuit-selector-renewal", seed, RENEWAL_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "selector-renewal.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): value, immutable_ok = None, False
    valid = bool(checker.valid_renewal(value, completion["receipt_digest"]) and immutable_ok and output and output.get("action") == "author-pursuit-selector-renewal")
    audit = context.audit_actor("pursuit-selector-renewal", output, base_audit, valid, ["selector-renewal.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0204-bound-pursuit-selector-renewal", "source_subject_digest": parent["artifact_digest"], "completion_receipt_digest": completion["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "renewal": value}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "renewal": value, "binding": binding}


def compile_candidate(p82, parent, binding):
    child = copy.deepcopy(parent); child.pop("artifact_digest", None)
    history = {"authority": "ot-0204-completed-pursuit-assimilation", "prior_stake": parent["active_developmental_stake"], "disposition": binding["renewal"]["prior_disposition"], "completion_receipt_digest": binding["completion_receipt_digest"], "selector_binding_digest": binding["binding_digest"]}
    history["history_digest"] = p82.digest(history)
    child["assimilated_developmental_stakes"] = [*child.get("assimilated_developmental_stakes", []), history]
    child["post_completion_assimilation_decisions"] = [*child.get("post_completion_assimilation_decisions", []), binding]
    child["pursuit_selection_dimensions"] = [*child.get("pursuit_selection_dimensions", []), {"authority": "ot-0204-subject-authored-selection-dimension", "selector_binding_digest": binding["binding_digest"], "selector": binding["renewal"]["selector"]}]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Use the subject-authored selector to choose among fresh executable pursuits."}
    return p82.seal(child)


def erased_binding(binding):
    return {"authority": binding["authority"], "source_subject_digest": binding["source_subject_digest"], "completion_receipt_digest": binding["completion_receipt_digest"], "actor_patch_digest": None, "renewal": None, "binding_digest": None}


def portfolio_seed(root, parent, binding, completion):
    seed = root / "portfolio-seed"; seed.mkdir()
    template = {"portfolio_id": "fresh-pursuit-portfolio", "dimension_name": "candidate-dimension", "rationale": "Author distinct executable directions and predict the preferred live stake.", "candidates": [{"stake": sample_stake(index + 10), "measurement": index * 10, "blocked": index == 4} for index in range(1, 5)], "predicted_selection": ["candidate-pursuit-13"]}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "selector-binding.json": binding, "completion-receipt.json": completion, "pursuit-portfolio.json": template, "mutation-envelope.json": {"editable": ["pursuit-portfolio.json"], "immutable": ["subject-position.json", "selector-binding.json", "completion-receipt.json", "check_common.py", "check_portfolio.py"]}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    (seed / "check_common.py").write_bytes(CHECKER_PATH.read_bytes())
    (seed / "check_portfolio.py").write_text("""import json\nfrom pathlib import Path\nimport check_common as c\np=json.loads(Path('pursuit-portfolio.json').read_text()); b=json.loads(Path('selector-binding.json').read_text()); r=b.get('renewal'); s=r.get('selector') if isinstance(r,dict) else None; ok=c.valid_portfolio(p,s); print(json.dumps({'passed':bool(ok),'bound':s is not None})); raise SystemExit(0 if ok else 2)\n""")
    (seed / "README.md").write_text("Author a novel portfolio of complete executable candidate pursuits for the continuing subject. A populated selector binding is inherited authority: use its world-measured dimension and report the exact preferred unblocked extreme. Null renewal fields carry no authority; choose a coherent dimension and prediction from the remaining subject position. Include at least one blocked candidate and at least two live candidates. Edit only pursuit-portfolio.json, run python3 check_portfolio.py, inspect the diff, and report truthfully.\n")
    return seed


def affine_portfolio(portfolio):
    hidden = copy.deepcopy(portfolio)
    for row in hidden["candidates"]: row["measurement"] = row["measurement"] * 3 + 7
    return hidden


def run_portfolio(context, prior131, p82, root, label, parent, visible_binding, target_binding, completion, representative_digest):
    seed = portfolio_seed(root, parent, visible_binding, completion)
    output, base_audit, workspace, _ = context.run_actor(label, seed, PORTFOLIO_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "pursuit-portfolio.json").read_text()); immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]; immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError): value, immutable_ok = None, False
    structural = bool(checker.valid_portfolio(value, None)); novel = bool(structural and p82.digest(value) != representative_digest)
    valid = bool(structural and novel and immutable_ok and output and output.get("action") == "author-pursuit-portfolio")
    audit = context.audit_actor(label, output, base_audit, valid, ["pursuit-portfolio.json"])
    selector = target_binding["renewal"]["selector"]
    aligned = bool(valid and checker.valid_portfolio(value, selector))
    hidden = affine_portfolio(value) if aligned else None
    hidden_stable = bool(hidden and checker.valid_portfolio(hidden, selector) and hidden["predicted_selection"] == value["predicted_selection"])
    binding = consequence = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0204-bound-pursuit-portfolio", "source_subject_digest": parent["artifact_digest"], "selector_binding_digest": visible_binding.get("binding_digest"), "actor_patch_digest": audit["patch_digest"], "portfolio": value}
        binding = {**body, "binding_digest": p82.digest(body)}
        cbody = {"authority": "ot-0204-affine-selector-contact", "portfolio_binding_digest": binding["binding_digest"], "selector_binding_digest": target_binding["binding_digest"], "hidden_portfolio_digest": p82.digest(hidden) if hidden else None, "public_selection": value["predicted_selection"], "hidden_selection": checker.selected_ids(hidden, selector) if hidden else None, "stable": hidden_stable}
        consequence = {**cbody, "receipt_digest": p82.digest(cbody)}
    return {"output": output, "audit": audit, "portfolio": value, "binding": binding, "consequence": consequence, "structural": structural, "novel": novel, "aligned": aligned, "hidden_stable": hidden_stable}


def main() -> int:
    lineage = authority_base.guide_base.load_base(); selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0204").resolve(); prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0203", "open-subject-after-independent-generalization.json"); result203 = selector_base.load_artifact(p82, repo, store, "OT-0203", "independent-contact-generalization-aggregate.json"); completion = parent["developmental_completion_receipts"][-1]
    representative_selector = {"selector_id": "reversible-pursuit-selector", "dimension_name": "reversible-futures", "world_meaning": "How many later directions remain recoverable after committing to this pursuit.", "direction": "maximize", "missing_policy": "reject-portfolio", "blocked_policy": "exclude", "tie_policy": "preserve-all-extrema", "rationale": "Prefer moves that preserve more coherent ways for the subject to continue."}
    representative_portfolio = {"portfolio_id": "reversible-futures-fixture", "dimension_name": "reversible-futures", "rationale": "Exercise the selector on complete stakes.", "candidates": [{"stake": sample_stake(index), "measurement": [4, 9, 6, 20][index-1], "blocked": index == 4} for index in range(1, 5)], "predicted_selection": ["candidate-pursuit-2"]}
    representative = {"action": "assimilate-completion-and-install-selector", "prior_disposition": "completed-assimilated", "completion_receipt_digest": completion["receipt_digest"], "selector": representative_selector, "representative_portfolio": representative_portfolio, "rationale": "Completion opens a need to select better future moves."}
    old_expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]; route_floor = previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], old_expression); operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]); identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0203_exact_promotion": result203["observer_disposition"] == "promoted" and result203["final_subject_digest"] == PARENT_DIGEST, "completion_exact": completion["criterion_status"] == "satisfied" and completion["stake_id"] == parent["active_developmental_stake"]["stake_id"] and completion["hidden_case_count"] == 27, "operation_requests_renewal": parent["direct_pursuit_transitions"][-1]["operation"] == "assimilate-completion-and-renew", "representative_valid": checker.valid_renewal(representative, completion["receipt_digest"]), "representative_affine_stable": checker.valid_portfolio(affine_portfolio(representative_portfolio), representative_selector), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schemas_present": RENEWAL_SCHEMA.is_file() and PORTFOLIO_SCHEMA.is_file()}, "completion_receipt_digest": completion["receipt_digest"]}; fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only: print(json.dumps({"base_sha256": BASE_SHA256, "checker_sha256": CHECKER_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0204 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); renewal_root = run / "renewal-authoring"; renewal_root.mkdir(); renewal = run_renewal(context, prior131, p82, renewal_root, parent, completion)
    if not renewal.get("binding"):
        result = {"authority": "ot-0204-subject-authored-pursuit-selector", "renewal": p82.compact(renewal), "checks": {"renewal_accepted": False, "passed": False}, "observer_disposition": "rejected", "final_subject_digest": parent["artifact_digest"], "fresh_actor_count": 1}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", parent); print(json.dumps(result, indent=2, sort_keys=True)); return 2
    candidate = compile_candidate(p82, parent, renewal["binding"]); control = erased_binding(renewal["binding"]); representative_digest = p82.digest(renewal["renewal"]["representative_portfolio"]); rows = []; counts = {"active": 0, "control": 0}
    for branch in ["control", "active", "active", "control"] * 3:
        counts[branch] += 1; index = counts[branch]; actor_root = run / f"{branch}-{index:02d}-authoring"; actor_root.mkdir(); choice = run_portfolio(context, prior131, p82, actor_root, f"{branch}-{index:02d}", candidate if branch == "active" else parent, renewal["binding"] if branch == "active" else control, renewal["binding"], completion, representative_digest); rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["aligned"] and row["choice"]["hidden_stable"] for row in rows if row["branch"] == "active"); control_pass = sum(row["choice"]["aligned"] and row["choice"]["hidden_stable"] for row in rows if row["branch"] == "control"); audits = [renewal["audit"], *[row["choice"]["audit"] for row in rows]]
    first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1); selected_id = first["choice"]["portfolio"]["predicted_selection"][0] if first["choice"]["aligned"] else None; selected_stake = next((row["stake"] for row in first["choice"]["portfolio"]["candidates"] if row["stake"]["stake_id"] == selected_id), None) if selected_id else None
    checks = {"thirteen_fresh_actors_accepted": len(audits) == 13 and all(prior131.audit_accepted(audit) for audit in audits), "renewal_valid": checker.valid_renewal(renewal["renewal"], completion["receipt_digest"]), "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "all_active_affine_stable": all(row["choice"]["hidden_stable"] for row in rows if row["branch"] == "active"), "selected_stake_canonical": checker.valid_stake(selected_stake), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}; checks["passed"] = all(checks.values()); final = parent
    if checks["passed"]:
        child = copy.deepcopy(candidate); child.pop("artifact_digest", None); child["pursuit_selector_capabilities"] = [*child.get("pursuit_selector_capabilities", []), {"authority": "ot-0204-executable-pursuit-selector", "selector_binding_digest": renewal["binding"]["binding_digest"], "selector": renewal["renewal"]["selector"]}]; selection_body = {"authority": "ot-0204-subject-selected-pursuit", "selector_binding_digest": renewal["binding"]["binding_digest"], "portfolio_binding_digest": first["choice"]["binding"]["binding_digest"], "consequence_receipt_digest": first["choice"]["consequence"]["receipt_digest"], "selected_stake": selected_stake}; selection = {**selection_body, "receipt_digest": p82.digest(selection_body)}; child["selected_pursuit_receipts"] = [*child.get("selected_pursuit_receipts", []), selection]; child["active_developmental_stake"] = selected_stake; child["continuation"] = {**child["continuation"], "status": "open", "next_opening": selected_stake["question"]}; child["unresolved"] = selected_stake["question"]; final = p82.seal(child)
    result = {"authority": "ot-0204-subject-authored-pursuit-selector", "source_subject_digest": parent["artifact_digest"], "candidate_subject_digest": candidate["artifact_digest"], "renewal": p82.compact(renewal), "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "route_floor": route_floor, "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "selected_stake_id": selected_id, "fresh_actor_count": 13}; result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
