from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0234_unregistered_world_outward_opening.py"
BASE_SHA256 = "ddfd3b8d91b0c18570c5c990db3ed4903d92023320c99788105e6386832f1ec8"
PARENT_DIGEST = "053ed81d96362ee3c69ddc8268d145c8fd30a252825805edb2a950ac059fad67"
OT234_RECEIPT = "2a53da8db97c88095a5fa339c908d5569b6d2f490b2ace5ce315d49d2f8961b0"
AUTHORITY = "ot-0235-outward-interface-correction"
SCHEMA = REPO / "spec/ot-0235-outward-corrector.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0234 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0235_frozen_ot0234", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base234 = load_base()
base233 = base234.base233
base226 = base234.base226
base225 = base234.base225
base218 = base225.base218
base213 = base234.base213
authority_base = base234.authority_base


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def selected(subject: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    extension = subject["actor_authored_environment_extensions"][-1]
    pending = subject["pending_contact_bearing_continuations"][-1]
    world = subject["outward_world_receipts"][-1]
    target = extension["target_symbol"]
    if pending["package"]["target_symbol"] != target or world["target_symbol"] != target:
        raise RuntimeError("outward state is not aligned")
    return extension, pending, world, target


def write_environment(root: Path, subject: dict[str, Any]) -> None:
    extension, _, _, _ = selected(subject)
    target_path = root / extension["target_path"]
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(extension["installed_source"])
    (target_path.parent / "__init__.py").write_text("")
    (target_path.parent / "reference.py").write_text(base234.REFERENCE_SOURCE)


def compare(root: Path, target: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    installed = getattr(base234.load_module(root / "field/operations.py", "installed_"), target)
    reference = getattr(base234.load_module(root / "field/reference.py", "reference_"), target)
    results = []
    for row in rows:
        try:
            observed = installed(copy.deepcopy(row["input"]))
            expected = reference(copy.deepcopy(row["input"]))
            results.append({"case_id": row["case_id"], "valid": True, "observed": observed, "expected": expected, "matches": observed == expected})
        except Exception as error:
            results.append({"case_id": row.get("case_id"), "valid": False, "matches": False, "error_type": type(error).__name__})
    return {"case_count": len(results), "all_valid": all(row["valid"] for row in results), "matches": sum(row["matches"] for row in results), "rows": results}


def corrected_fixture(source: str, target: str) -> str:
    order, functions = base225.source_functions(source)
    collection, magnitude, duration, risk = base234.SURFACES[target]
    functions[target] = f'''def {target}(case):
    candidates = []
    for mask in __import__("itertools").product((0, 1), repeat=len(case["{collection}"])):
        chosen = [item for item, take in zip(case["{collection}"], mask) if take]
        if sum(item["effort"] for item in chosen) > case["capacity"]:
            continue
        score = sum(item["{magnitude}"] * item["{duration}"] * item["{risk}"] for item in chosen)
        identities = tuple(sorted(item["id"] for item in chosen))
        candidates.append((score, len(chosen), tuple(reversed(identities)), identities))
    return list(max(candidates)[-1])'''
    return "\n\n\n".join(functions[name] for name in order) + "\n"


def followup_cases(target: str) -> list[dict[str, Any]]:
    collection, magnitude, duration, risk = base234.SURFACES[target]
    values = [
        (3, [(11, 1, .2, 3), (7, 8, .9, 3)]),
        (4, [(12, 1, .2, 4), (8, 7, .8, 2), (7, 6, .9, 2)]),
        (5, [(12, 1, .2, 5), (9, 6, .8, 3), (8, 5, .9, 2)]),
        (2, [(9, 8, .8, 2), (11, 1, .2, 2)]),
        (4, [(10, 5, .9, 2), (6, 2, .5, 2)]),
        (4, [(9, 4, .8, 2), (8, 3, .7, 2)]),
    ]
    rows = []
    for index, (capacity, items) in enumerate(values, 1):
        encoded = [{"id": chr(109 + offset), magnitude: size, duration: span, risk: probability, "effort": effort} for offset, (size, span, probability, effort) in enumerate(items)]
        rows.append({"case_id": f"followup-{index}", "input": {"capacity": capacity, collection: encoded}})
    return rows


def correction_public_cases(target: str) -> list[dict[str, Any]]:
    collection, magnitude, duration, risk = base234.SURFACES[target]
    values = [
        (3, [(13, 1, .2, 3), (8, 9, .9, 3)]),
        (4, [(14, 1, .2, 4), (9, 8, .8, 2), (8, 7, .9, 2)]),
        (5, [(13, 1, .2, 5), (10, 7, .8, 3), (9, 6, .9, 2)]),
        (2, [(10, 9, .8, 2), (12, 1, .2, 2)]),
    ]
    rows = []
    for index, (capacity, items) in enumerate(values, 1):
        encoded = [{"id": chr(115 + offset), magnitude: size, duration: span, risk: probability, "effort": effort} for offset, (size, span, probability, effort) in enumerate(items)]
        rows.append({"case_id": f"correction-public-{index}", "input": {"capacity": capacity, collection: encoded}})
    return rows


def contract(subject: dict[str, Any]) -> dict[str, Any]:
    extension, pending, world, target = selected(subject)
    identities = {"source_subject_digest": subject["artifact_digest"], "contact_binding_digest": pending["binding_digest"], "contact_identity": pending["contact_identity"], "world_receipt_digest": world["receipt_digest"]}
    return {"authority": AUTHORITY, "required_fields": sorted(base218.CORRECTION_CORE), "allowed_dispositions": ["revise", "surrender"], "required_identities": identities, "target_symbol": target, "target_path": extension["target_path"], "reference_path": "field/reference.py", "baseline_path": "field/baseline-selected.py", "predicates": base218.CORRECTION_PREDICATES}


def decision_template(subject: dict[str, Any]) -> dict[str, Any]:
    value = contract(subject)
    return {"disposition": "revise", **value["required_identities"], "target_symbol": value["target_symbol"], "predicates": copy.deepcopy(value["predicates"]), "rationale": "replace-rationale", "next_pursuit": "replace-next-pursuit"}


CHECKER = base225.CHECKER.replace('"bound-contact.json"', '"correction-public-contact.json"')


def seed_actor(root: Path, subject: dict[str, Any], decision: dict[str, Any]) -> Path:
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_environment(seed, subject)
    extension, pending, world, _ = selected(subject)
    target_path = extension["target_path"]
    (seed / "field/baseline-selected.py").write_text((seed / target_path).read_text())
    write_json(seed / "exact-subject.json", subject)
    write_json(seed / "subject-position.json", base234.base224.base217.projection(subject))
    write_json(seed / "bound-contact.json", pending)
    correction_contact = copy.deepcopy(pending)
    correction_contact["authority"] = AUTHORITY + "-visible-correction-world-contact"
    correction_contact["package"] = {**correction_contact["package"], "cases": correction_public_cases(extension["target_symbol"])}
    correction_contact["package_digest"] = base234.base224.base219.digest(correction_contact["package"])
    write_json(seed / "correction-public-contact.json", correction_contact)
    write_json(seed / "unresolved-world-receipt.json", world)
    write_json(seed / "correction-contract.json", contract(subject))
    write_json(seed / "correction-decision.json", decision)
    (seed / "check_correction.py").write_text(CHECKER)
    immutable = ["exact-subject.json", "subject-position.json", "bound-contact.json", "correction-public-contact.json", "unresolved-world-receipt.json", "correction-contract.json", "check_correction.py", "field/__init__.py", "field/reference.py", "field/baseline-selected.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": [target_path, "correction-decision.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue the exact unresolved outward contact through its retained interface and world receipt. Revise only the selected function or surrender it under correction-contract.json. Edit only the permitted source and correction-decision.json, run python3 check_correction.py, and inspect the exact diff. Follow-up cases are unavailable.\n")
    return seed


def run_corrector(context, p82, root: Path, subject: dict[str, Any]) -> dict[str, Any]:
    seed = seed_actor(root, subject, decision_template(subject))
    extension, pending, world, target = selected(subject)
    output, base_audit, workspace, _ = context.run_actor("outward-interface-corrector", seed, SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "correction-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        source = (workspace / extension["target_path"]).read_text()
        baseline = (workspace / "field/baseline-selected.py").read_text()
        identities = contract(subject)["required_identities"]
        exact = set(decision) == base218.CORRECTION_CORE and all(decision.get(key) == value for key, value in identities.items()) and decision.get("target_symbol") == target and decision.get("predicates") == base218.CORRECTION_PREDICATES and decision.get("disposition") in {"revise", "surrender"}
        local = source == baseline if decision.get("disposition") == "surrender" else base225.target_only_change(source, baseline, target)
        public = compare(workspace, target, correction_public_cases(target)) if exact and local and decision.get("disposition") == "revise" else None
        semantic = bool(exact and local and immutable_ok and (decision["disposition"] == "surrender" or (public and public["all_valid"] and public["matches"] == 4)))
    except (OSError, json.JSONDecodeError, KeyError, SyntaxError):
        decision, source, public, semantic = None, None, None, False
    transport = isinstance(output, dict) and output.get("action") == "correct-unresolved-contact" and isinstance(output.get("next_pursuit"), str) and bool(output["next_pursuit"].strip())
    expected = ["correction-decision.json", extension["target_path"]] if decision and decision.get("disposition") == "revise" else ["correction-decision.json"]
    audit = context.audit_actor("outward-interface-corrector", output, base_audit, semantic and transport, expected)
    effect = base226.g8(audit, semantic and transport)
    binding = None
    if effect["causal_effect_accepted"]:
        body = {"authority": AUTHORITY + "-bound-correction", "source_subject_digest": subject["artifact_digest"], "contact_identity": pending["contact_identity"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "target_path": extension["target_path"], "decision": decision, "patched_source": source if decision["disposition"] == "revise" else None, "patched_source_digest": p82.digest(source) if decision["disposition"] == "revise" else None, "public_result": public, "report_fidelity": effect["report_fidelity"]}
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence("outward-interface-corrector") / "bound-correction.json", binding)
    return {"accepted": binding is not None, "binding": binding, "decision": decision, "public": public, "effect_audit": effect, "output": output}


def evaluate(root: Path, subject: dict[str, Any], correction: dict[str, Any], p82) -> dict[str, Any]:
    _, _, world, target = selected(subject)
    revised = root / "revised"
    unchanged = root / "unchanged"
    write_environment(revised, subject)
    write_environment(unchanged, subject)
    rows = followup_cases(target)
    if correction["decision"]["disposition"] == "revise":
        (revised / "field/operations.py").write_text(correction["binding"]["patched_source"])
        observed = compare(revised, target, rows)
        control = compare(unchanged, target, rows)
        passed = observed["all_valid"] and observed["matches"] == 6 and control["all_valid"] and control["matches"] == 2
        outcome = "success" if passed else "unresolved"
    else:
        observed, control, passed, outcome = None, compare(unchanged, target, rows), True, "surrender"
    body = {"authority": AUTHORITY + "-sealed-correction-world", "source_subject_digest": subject["artifact_digest"], "unresolved_world_receipt_digest": world["receipt_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "target_symbol": target, "target_path": "field/operations.py", "followup_cases_digest": p82.digest(rows), "result": observed, "unchanged_control": control, "outcome": outcome, "promotion_gate": passed}
    return {**body, "receipt_digest": p82.digest(body)}


def compile_correction(subject: dict[str, Any], correction: dict[str, Any], followup: dict[str, Any], p82) -> dict[str, Any]:
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    extension, pending, unresolved_world, target = selected(subject)
    pendings = copy.deepcopy(child["pending_contact_bearing_continuations"])
    pendings[-1] = {**pendings[-1], "consequence_status": "resolved-after-correction", "correction_binding_digest": correction["binding"]["binding_digest"], "followup_world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"]}
    child["pending_contact_bearing_continuations"] = pendings
    extensions = copy.deepcopy(child["actor_authored_environment_extensions"])
    if correction["decision"]["disposition"] == "revise":
        extensions[-1] = {**extensions[-1], "installed_source": correction["binding"]["patched_source"], "installed_source_digest": correction["binding"]["patched_source_digest"], "status": "corrected-and-world-verified", "correction_binding_digest": correction["binding"]["binding_digest"]}
    child["actor_authored_environment_extensions"] = extensions
    capability = {"authority": AUTHORITY + "-world-admitted-outward-correction", "origin": "actor-authored-outward-interface", "target_symbol": target, "target_path": extension["target_path"], "package": copy.deepcopy(pending["package"]), "patched_source": correction["binding"]["patched_source"], "patched_source_digest": correction["binding"]["patched_source_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"]}
    child["generalized_semantic_correction_capabilities"] = [*child.get("generalized_semantic_correction_capabilities", []), capability]
    receipt_body = {"authority": AUTHORITY + "-correction-receipt", "source_subject_digest": subject["artifact_digest"], "contact_identity": pending["contact_identity"], "unresolved_world_receipt_digest": unresolved_world["receipt_digest"], "correction_binding_digest": correction["binding"]["binding_digest"], "followup_world_receipt_digest": followup["receipt_digest"], "disposition": correction["decision"]["disposition"], "outcome": followup["outcome"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child["outward_correction_receipts"] = [*child.get("outward_correction_receipts", []), receipt]
    ledger = copy.deepcopy(child["local_frontier_ledger"])
    ledger["targets"][target].update(status="verified-local", correction_receipts=[*ledger["targets"][target]["correction_receipts"], receipt["receipt_digest"]], latest_world_receipt_digest=followup["receipt_digest"], latest_world_outcome=followup["outcome"], independent_success_receipts=[followup["receipt_digest"]] if followup["outcome"] == "success" else [])
    child["local_frontier_ledger"] = ledger
    state = copy.deepcopy(child["fixed_g6_recurrence_driver"])
    state["phase"] = "assimilate"
    state["accepted_actors"] += 1
    state["corrected_contradictions"] += int(followup["outcome"] == "success")
    child["fixed_g6_recurrence_driver"] = state
    child["continuation_liveness"] = {"authority": AUTHORITY, "status": "awaiting-outward-reopening", "resolved_contact_identity": pending["contact_identity"], "correction_receipt_digest": receipt["receipt_digest"], "target_status": "verified-local"}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": correction["decision"]["next_pursuit"]}
    child["unresolved"] = "Assimilate the outward correction and determine the next live operation."
    return p82.seal(child)


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0235").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0234", "open-subject-at-outward-contradiction.json")
    result234 = selector_base.load_artifact(p82, repo, store, "OT-0234", "unregistered-world-outward-opening-aggregate.json")
    extension, pending, world, target = selected(parent)

    fixture_root = run.parent / "OT-0235-preflight"
    import shutil
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    environment = fixture_root / "environment"
    write_environment(environment, parent)
    baseline = (environment / extension["target_path"]).read_text()
    fixture_source = corrected_fixture(baseline, target)
    revised = fixture_root / "revised"
    unchanged = fixture_root / "unchanged"
    write_environment(revised, parent)
    write_environment(unchanged, parent)
    (revised / extension["target_path"]).write_text(fixture_source)
    originating_after = compare(revised, target, pending["package"]["cases"])
    public = compare(revised, target, correction_public_cases(target))
    corrected = compare(revised, target, followup_cases(target))
    control = compare(unchanged, target, followup_cases(target))
    fixture_decision = decision_template(parent)
    fixture_decision.update(rationale="Use the consequence-weighted feasible-set rule exposed by the retained correction interface.", next_pursuit="Assimilate the corrected outward surface and continue from the resulting position.")
    checker_seed = seed_actor(fixture_root / "checker", parent, fixture_decision)
    (checker_seed / extension["target_path"]).write_text(fixture_source)
    checker = subprocess.run(["python3", "check_correction.py"], cwd=checker_seed, capture_output=True)
    fixture_binding = {"binding_digest": "a" * 64, "patched_source": fixture_source, "patched_source_digest": p82.digest(fixture_source)}
    fixture_followup = {"receipt_digest": "b" * 64, "outcome": "success"}
    prospective = compile_correction(parent, {"decision": fixture_decision, "binding": fixture_binding}, fixture_followup, p82)
    route = base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], parent["actor_authored_contact_mechanisms"][-1]["expression"])
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    prompt = (checker_seed / "README.md").read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_correct": parent["artifact_digest"] == PARENT_DIGEST and parent["fixed_g6_recurrence_driver"]["phase"] == "correct" and runtime.identity_conforms(parent),
        "ot0234_exact_promotion": result234["observer_disposition"] == "promoted" and result234["receipt_digest"] == OT234_RECEIPT and result234["final_subject_digest"] == PARENT_DIGEST,
        "derived_outward_state_aligned": target == extension["target_symbol"] == pending["package"]["target_symbol"] == world["target_symbol"] and world["outcome"] == "unresolved" and world["result"]["matches"] == 2,
        "originating_cases_not_correction_complete": not originating_after["all_valid"],
        "target_absent_from_inherited_registry": target not in parent["expanded_semantic_environment"]["registry"],
        "prompt_names_no_target": target not in prompt,
        "target_only_fixture_change": base225.target_only_change(fixture_source, baseline, target),
        "fixture_public_4_of_4": public["all_valid"] and public["matches"] == 4,
        "fixture_followup_6_of_6": corrected["all_valid"] and corrected["matches"] == 6,
        "unchanged_followup_2_of_6": control["all_valid"] and control["matches"] == 2,
        "actor_checker_passed": checker.returncode == 0,
        "prospective_subject_conforms": runtime.identity_conforms(prospective) and prospective["fixed_g6_recurrence_driver"]["phase"] == "assimilate",
        "inherited_registry_unchanged": prospective["expanded_semantic_environment"]["registry"] == parent["expanded_semantic_environment"]["registry"],
        "schema_present": SCHEMA.is_file(),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "derived_interface": {"target_path": extension["target_path"], "target_symbol": target, "binding_digest": extension["binding_digest"]}, "public": public, "corrected_followup": corrected, "unchanged_followup": control, "checks": checks}
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0235 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    correction = run_corrector(context, p82, run / "correction", parent)
    followup = evaluate(run / "followup", parent, correction, p82) if correction["accepted"] else None
    final = compile_correction(parent, correction, followup, p82) if followup and followup["promotion_gate"] else parent
    if followup:
        write_json(run / "correction-world-receipt.json", followup)
    gates = {
        "preflight_passed": checks["passed"],
        "corrector_accepted": correction["accepted"],
        "correction_revised": bool(correction["accepted"] and correction["decision"]["disposition"] == "revise"),
        "g8_effect_accepted": correction["effect_audit"]["causal_effect_accepted"],
        "public_4_of_4": bool(correction["public"] and correction["public"]["matches"] == 4),
        "followup_6_of_6": bool(followup and followup["result"] and followup["result"]["matches"] == 6),
        "unchanged_2_of_6": bool(followup and followup["unchanged_control"]["matches"] == 2),
        "patch_installed_in_actor_extension": bool(followup and final["actor_authored_environment_extensions"][-1]["installed_source"] == correction["binding"]["patched_source"]),
        "inherited_registry_unchanged": final["expanded_semantic_environment"]["registry"] == parent["expanded_semantic_environment"]["registry"],
        "outward_target_verified": bool(followup and final["local_frontier_ledger"]["targets"][target]["status"] == "verified-local"),
        "final_open_assimilate": final["continuation"]["status"] == "open" and final["fixed_g6_recurrence_driver"]["phase"] == "assimilate" and runtime.identity_conforms(final),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    aggregate = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "derived_target": target, "correction": correction, "followup_world": followup, "checks": gates, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1}
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
