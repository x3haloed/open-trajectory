from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0333_subject_sized_environment_search.py"
BASE_SHA256 = "ead875744007bd1e3e5cde32e6efb31c690ec2799b606fb221976965fe816874"
PARENT_DIGEST = "38e9b5dd0311f26b462e48a2e87b7aade4ab2c0b5450335f13d3b098ae380449"
POLICY_SUBJECT_DIGEST = "338c14376c906e4b5e2d1406fffdb3d1d2c29e53b0d30a1e1f735a7d48162139"
OT333_RECEIPT = "2f731b99420c1459df4553d7c6874913d0d13cdadf1640e58ac8fb7917edfffe"
AUTHORITY = "ot-0334-scoped-provider-collision-recovery"
RETAINED_PROVIDER_COUNT = 1
MAX_NEW_PROVIDERS = 2
MINIMUM_ELIGIBLE_SURFACES = 2
PULSE = None


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"frozen OT-0333 source changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0334_frozen_ot0333", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()
b = base.b
driver = base.driver
base305 = base.base305
contact_base = base.contact_base
g11 = base.g11
write_json = base.write_json


def setup(args):
    repo, store, _, p82, runtime, parent, result332, result330, result280, core, base130 = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0334").resolve()
    selector = base.base.base.base.base.b.authority_base.guide_base.load_base().selector_base
    load = lambda experiment, name: selector.load_artifact(p82, repo, store, experiment, name)
    result333 = load("OT-0333", "subject-sized-environment-search-rejected-aggregate.json")
    policy_subject = load("OT-0333", "open-policy-bearing-subject-before-provider-repair.json")
    retained_package = load("OT-0333", "rejected-provider-world-package.json")
    return repo, store, run, p82, runtime, parent, result332, result330, result280, core, base130, result333, policy_subject, retained_package


def eligible_targets(subject, evaluation):
    ledger = subject["local_frontier_ledger"]["targets"]
    return {target: path for target, path in evaluation.get("targets", {}).items() if target not in ledger}


def scoped_semantic(subject, package, evaluation, scan, p82):
    seen = set(b.base279.seen_world_ids(subject))
    eligible = eligible_targets(subject, evaluation)
    return bool(
        evaluation.get("valid")
        and evaluation.get("world_id") == package.get("world_id")
        and evaluation.get("full_package_digest") == p82.digest(package)
        and scan
        and scan.get("status") == "world-available"
        and scan.get("available_world", {}).get("world_id") == package.get("world_id")
        and package.get("world_id") not in seen
        and len(eligible) >= MINIMUM_ELIGIBLE_SURFACES
    )


def reconstructed_retained_provider(repo, run333, subject, package, p82):
    aggregate = json.loads((run333 / "aggregate.json").read_text())
    old = aggregate["providers"][0]
    workspace = run333 / "runtime/subject-blind-provider-01/actor-workspace"
    events = (run333 / "runtime/subject-blind-provider-01/events.jsonl").read_text()
    stderr = (run333 / "runtime/subject-blind-provider-01/stderr.txt").read_text()
    exact_package = json.loads((workspace / "world-package.json").read_text())
    evaluation = b.base281.with_evaluator(b.base268.evaluate_package, exact_package, p82.digest)
    checker = subprocess.run(["python3", "check_package.py"], cwd=workspace, capture_output=True)
    public = evaluation.get("public_package") if evaluation.get("valid") else None
    scan = b.base267.scan_feed(subject, [public], p82.digest) if public else None
    revised_audit = copy.deepcopy(old["audit"])
    revised_audit["conformant"] = True
    classified = g11.retained_row(revised_audit, events, stderr)
    body = {
        "authority": AUTHORITY + "-retained-provider-reconstruction",
        "source_ot0333_receipt_digest": aggregate["receipt_digest"],
        "old_audit_digest": p82.digest(old["audit"]),
        "package_digest": p82.digest(exact_package),
        "changed_predicate": "whole-package-bare-target-collision-to-at-least-two-eligible-targets",
        "old_target_collision": old["target_collision"],
        "eligible_targets": eligible_targets(subject, evaluation),
        "actor_resampled": False,
        "world_resampled": False,
        "checker_passed": checker.returncode == 0,
        "package_exact": exact_package == package,
        "scoped_semantic": scoped_semantic(subject, package, evaluation, scan, p82),
        "exact_clean_effects": old["audit"]["exact_changes"] and old["audit"]["changed_paths"] == ["world-package.json"],
        "trace_clean": old["audit"]["trace_regime"]["accepted"] and old["audit"]["denial_classification_v2"]["accepted"],
        "g11_reconstructed": g11.g11(classified),
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    accepted = all(receipt[key] for key in ("checker_passed", "package_exact", "scoped_semantic", "exact_clean_effects", "trace_clean", "g11_reconstructed"))
    return {
        "accepted": accepted,
        "retained": True,
        "package": package,
        "evaluation": evaluation,
        "scanner_observation": scan,
        "eligible_targets": eligible_targets(subject, evaluation),
        "reconstruction": receipt,
    }


def run_provider(context, p82, root, subject, index):
    label = f"subject-blind-provider-{index:02d}"
    seed = b.base268.seed_actor(root / "actor", b.base268.TEMPLATE)
    output, base_audit, workspace, _ = context.run_actor(label, seed, b.base268.SCHEMA, (seed / "README.md").read_text().strip())
    try:
        package = json.loads((workspace / "world-package.json").read_text())
        evaluation = b.base281.with_evaluator(b.base268.evaluate_package, package, p82.digest)
        checker = subprocess.run(["python3", "check_package.py"], cwd=workspace, capture_output=True)
        public = evaluation.get("public_package") if evaluation.get("valid") else None
        scan = b.base267.scan_feed(subject, [public], p82.digest) if public else None
        semantic = checker.returncode == 0 and scoped_semantic(subject, package, evaluation, scan, p82)
    except (OSError, json.JSONDecodeError, KeyError):
        package, evaluation, scan, semantic = None, {"valid": False}, None, False
    transport = b.base268.output_valid(output, package)
    audit = context.audit_actor(label, output, base_audit, semantic and transport, ["world-package.json"])
    certificate = base.certify_g11(context, label, audit)
    accepted = bool(semantic and transport and certificate["challenger_accepted"])
    return {
        "accepted": accepted,
        "retained": False,
        "output": output,
        "audit": audit,
        "g11": certificate,
        "package": package,
        "evaluation": evaluation,
        "scanner_observation": scan,
        "eligible_targets": eligible_targets(subject, evaluation),
    }


def scope_controls(subject, package, evaluation, scan, p82):
    controls = {}
    for name, mutate in {
        "zero-eligible": lambda value: value.__setitem__("targets", {target: path for target, path in value["targets"].items() if target in subject["local_frontier_ledger"]["targets"]}),
        "one-eligible": lambda value: value.__setitem__("targets", dict(list(eligible_targets(subject, value).items())[:1])),
    }.items():
        changed = copy.deepcopy(evaluation)
        mutate(changed)
        controls[name] = not scoped_semantic(subject, package, changed, scan, p82)
    collision_scan = copy.deepcopy(scan)
    collision_package = copy.deepcopy(package)
    collision_package["world_id"] = next(iter(b.base279.seen_world_ids(subject)))
    controls["world-collision"] = not scoped_semantic(subject, collision_package, evaluation, collision_scan, p82)
    malformed = copy.deepcopy(evaluation)
    malformed["valid"] = False
    controls["malformed-package"] = not scoped_semantic(subject, package, malformed, scan, p82)
    altered = copy.deepcopy(package)
    first_path = sorted(altered["sealed_reference_sources"])[0]
    altered["sealed_reference_sources"][first_path] += "\n"
    controls["altered-sealed-package"] = not scoped_semantic(subject, altered, evaluation, scan, p82)
    return controls


def contact_fixture(root, subject, package, evaluation, result280, target, p82, runtime):
    row = contact_base.fixture_branch(root, subject, package, evaluation, result280, target, p82, runtime)
    decision = contact_base.base270.fixture_decision(package, evaluation, target)
    action = {
        "decision": decision,
        "binding": {"binding_digest": "a" * 64, "contact_identity": "b" * 64},
    }
    pulse = {
        "authority": AUTHORITY + "-fixture-pulse",
        "content": PULSE,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": "expanded-select",
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    intermediate = contact_base.base270.compile_intermediate(subject, action, pulse, p82)
    world = contact_base.base270.sealed_world(intermediate, action, package, result280, p82)
    final = contact_base.base270.compile_world(intermediate, world, p82)
    floor_exact = final["local_frontier_ledger"]["targets"]["assign_berth"] == subject["local_frontier_ledger"]["targets"]["assign_berth"]
    return {**row, "old_assign_berth_floor_exact": floor_exact}


def preflight(root, repo, p82, runtime, parent, result332, result330, result280, result333, policy_subject, retained_package, run333):
    root.mkdir(parents=True, exist_ok=True)
    retained = reconstructed_retained_provider(repo, run333, policy_subject, retained_package, p82)
    evaluation = retained["evaluation"]
    scan = retained["scanner_observation"]
    controls = scope_controls(policy_subject, retained_package, evaluation, scan, p82)
    observation, offered_subject, reused = b.base281.wake(policy_subject, retained_package, p82)
    branches = [contact_fixture(root / f"eligible-{index:02d}", offered_subject, retained_package, evaluation, result280, target, p82, runtime) for index, target in enumerate(sorted(retained["eligible_targets"]), 1)]
    blocked = contact_base.fixture_branch(root / "blocked-collision", offered_subject, retained_package, evaluation, result280, "assign_berth", p82, runtime)
    route, identity = b.base272.base265.floors(parent)
    policy = policy_subject["active_environment_solicitation_policy"]["policy"]
    first_history = base.selection_history(parent["active_world_seeking_stake"]["stake"], [base305.descriptor(retained_package, evaluation)])
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_current_and_retained_inputs": parent["artifact_digest"] == PARENT_DIGEST and result332["observer_disposition"] == "promoted" and result333["receipt_digest"] == OT333_RECEIPT and result333["observer_disposition"] == "rejected" and policy_subject["artifact_digest"] == POLICY_SUBJECT_DIGEST and base.valid_current_stake(policy_subject, p82) and base.valid_policy(policy),
        "retained_provider_reconstructed_without_actor": retained["accepted"] and retained["reconstruction"]["actor_resampled"] is False and retained["reconstruction"]["world_resampled"] is False,
        "exact_collision_scope": sorted(retained["eligible_targets"]) == ["clear_cargo", "issue_ration"] and result333["providers"][0]["target_collision"] is True,
        "five_scope_controls_reject": len(controls) == 5 and all(controls.values()),
        "retained_world_can_offer": observation["status"] == "world-available" and not reused and driver.derive(offered_subject, p82) == "expanded-select",
        "two_eligible_contact_branches_pass": len(branches) == 2 and all(row["checker"] and row["semantic"] and row["public"] and row["public_only"] and row["world_matches"] == 2 and row["world_outcome"] == "unresolved" and row["offer_consumed"] and row["new_epoch"] and row["conformant"] and row["routes_correction"] and row["old_assign_berth_floor_exact"] for row in branches),
        "colliding_target_remains_blocked": not blocked["checker"] and not blocked["semantic"] and not blocked["public"],
        "policy_requests_after_first_provider": base.policy_action(policy, first_history, 1) == "request-world",
        "g11_exact_active": result330["receipt_digest"] == base.G11_RECEIPT and result330["checks"]["passed"],
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    body = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0333_receipt_digest": result333["receipt_digest"],
        "retained_provider_reconstruction": retained["reconstruction"],
        "scope_controls": controls,
        "eligible_targets": retained["eligible_targets"],
        "new_provider_budget": MAX_NEW_PROVIDERS,
        "checks": checks,
    }
    result = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", result)
    return result, retained


def run_contact(repo, root, context, p82, runtime, subject, package, result280, core, base130):
    pulse = {"authority": AUTHORITY + "-contact-pulse", "content": PULSE, "source_subject_digest": subject["artifact_digest"], "derived_operation": "expanded-select"}
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = contact_base.base270.run_actor(context, p82, root / "actor", subject)
    intermediate = contact_base.base270.compile_intermediate(subject, actor, pulse, p82) if actor["accepted"] else subject
    world = contact_base.base270.sealed_world(intermediate, actor, package, result280, p82) if actor["accepted"] and runtime.identity_conforms(intermediate) else None
    final = contact_base.base270.compile_world(intermediate, world, p82) if world else intermediate
    if world:
        write_json(root / "world-receipt.json", world)
    certificate = base.certify_g11(context, "standing-feed-package-contact-actor", actor["audit"])
    selected = actor.get("decision", {}).get("next_contact")
    pair = (selected.get("target_path"), selected.get("target_symbol")) if selected else None
    checks = {
        "content_free": PULSE is None,
        "actor_accepted": actor["accepted"] and certificate["challenger_accepted"],
        "selected_offered_target": pair in contact_base.base270.offered_pairs(subject),
        "public_executable": bool(actor.get("public") and actor["public"]["all_valid"]),
        "independent_2_of_6": bool(world and world["result"]["matches"] == 2 and world["outcome"] == "unresolved"),
        "old_assign_berth_floor_preserved": final["local_frontier_ledger"]["targets"]["assign_berth"] == subject["local_frontier_ledger"]["targets"]["assign_berth"],
        "open_correction": bool(world and driver.derive(final, p82) == "outward-correct" and final["continuation"]["status"] == "open" and runtime.identity_conforms(final)),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-selected-world-contact", "pulse": pulse, "actor": actor, "g11": certificate, "world": world, "checks": checks, "final_subject_digest": final["artifact_digest"]}
    return {**body, "receipt_digest": p82.digest(body)}, final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, parent, result332, result330, result280, core, base130, result333, policy_subject, retained_package = setup(args)
    run333 = store / "runs/OT-0333"
    with tempfile.TemporaryDirectory() as directory:
        frozen, retained = preflight(Path(directory), repo, p82, runtime, parent, result332, result330, result280, result333, policy_subject, retained_package, run333)
    if args.preflight_only:
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0334 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", frozen)
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0334 preflight failed")
    context = base305.actor_context(runtime, core, base130, run, repo)
    providers = [retained]
    packages = [retained_package]
    evaluations = [retained["evaluation"]]
    policy_binding = policy_subject["active_environment_solicitation_policy"]
    policy = policy_binding["policy"]
    selections = base.selection_history(parent["active_world_seeking_stake"]["stake"], base.descriptors(packages, evaluations))
    action = base.policy_action(policy, selections, 1)
    for index in range(2, policy["maximum_provider_count"] + 1):
        if action != "request-world":
            break
        provider = run_provider(context, p82, run / f"provider-{index:02d}", policy_subject, index)
        providers.append(provider)
        if provider.get("package") is not None:
            write_json(run / f"provider-{index:02d}-world-package.json", provider["package"])
        if not provider["accepted"]:
            action = "invalid-provider"
            break
        packages.append(provider["package"])
        evaluations.append(provider["evaluation"])
        if len({package["world_id"] for package in packages}) != len(packages):
            action = "provider-collision"
            break
        selections = base.selection_history(parent["active_world_seeking_stake"]["stake"], base.descriptors(packages, evaluations))
        action = base.policy_action(policy, selections, len(packages))
    final = policy_subject
    stop_receipt = None
    contact = None
    if action == "offer-world":
        selected_id = selections[-1]["selected_world_id"]
        selected_index = next(index for index, package in enumerate(packages) if package["world_id"] == selected_id)
        offered, stop_receipt = base.compile_supported(policy_subject, policy_binding, selections, packages[selected_index], p82)
        contact_root = run / "selected-world-contact"
        contact_root.mkdir()
        contact_context = b.base274.context_for(core, base130, runtime, contact_root, repo)
        contact, final = run_contact(repo, contact_root, contact_context, p82, runtime, offered, packages[selected_index], result280, core, base130)
        write_json(run / "selected-world-contact.json", contact)
        write_json(run / "open-subject-after-selected-world-contact.json", final)
    elif action == "revise-stake":
        final, stop_receipt = base.compile_exhaustion(policy_subject, policy_binding, selections, p82)
        write_json(run / "open-subject-after-solicitation-exhaustion.json", final)
    checks = {
        "preflight_passed": frozen["checks"]["passed"],
        "exact_retained_policy_and_provider": providers[0]["retained"] and providers[0]["accepted"] and policy_subject["artifact_digest"] == POLICY_SUBJECT_DIGEST,
        "two_new_clean_subject_blind_providers": len(providers) == 3 and all(provider["accepted"] for provider in providers[1:]),
        "subject_policy_first_authorized_stop": action == "offer-world" and base.policy_action(policy, selections[:-1], 2) == "request-world" and len(providers) == policy["maximum_provider_count"] < base.OBSERVER_PROVIDER_CEILING,
        "policy_erased_cannot_stop": base.policy_action({}, selections, len(providers)) == "invalid-policy",
        "unique_supported_offer": bool(stop_receipt and action == "offer-world" and selections[-1]["supported"] and stop_receipt["selected_world_id"] == selections[-1]["selected_world_id"]),
        "selected_world_real_contact": bool(contact and contact["checks"]["passed"]),
        "open_correction_successor": bool(contact and driver.derive(final, p82) == "outward-correct" and final["continuation"]["status"] == "open" and runtime.identity_conforms(final)),
    }
    checks["passed"] = all(checks.values())
    body = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0333_receipt_digest": result333["receipt_digest"],
        "retained_provider_reconstruction_receipt_digest": retained["reconstruction"]["receipt_digest"],
        "providers": providers,
        "selection_history": selections,
        "final_policy_action": action,
        "stop_receipt": stop_receipt,
        "contact_receipt_digest": contact.get("receipt_digest") if contact else None,
        "fresh_actor_count": (len(providers) - RETAINED_PROVIDER_COUNT)
        + int(contact is not None),
        "checks": checks,
        "operational_transition_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
    }
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
