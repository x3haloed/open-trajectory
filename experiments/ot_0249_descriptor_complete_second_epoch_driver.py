from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0248_descriptor_neutral_second_epoch_driver.py"
BASE_SHA256 = "aeea65c3e125c113d3c92b366143ff392e119dc1c2cd02876bc9af9f481dc93f"
PARENT_DIGEST = "aab064d0c14b67c57e6d89e3ed8e4faac6e03cc3c666b0f6aadab3cee1b4070a"
OT248_RECEIPT = "cef1d9700a8ce2ab82f3f7ea4783f85f51201c8b9566ea377785947619b3ccc5"
AUTHORITY = "ot-0249-descriptor-complete-second-epoch-driver"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0248 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0249_frozen_ot0248", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base248 = load_base()
base247 = base248.base247
base245 = base248.base245
base244 = base248.base244
base243 = base248.base243
base236 = base248.base236
base218 = base243.base218
authority_base = base248.authority_base


def package_initializers(epoch):
    return sorted(
        {
            str(Path(relative).parent / "__init__.py")
            for relative in epoch["visible_sources"]
        }
    )


def seed_actor(root, subject, decision):
    seed = root / "seed"
    seed.mkdir(parents=True)
    base243.write_environment(seed, subject)
    extension, pending, world, epoch, target = base248.selected(subject)
    baseline = (seed / extension["target_path"]).read_text()
    (seed / "correction/baseline-selected.py").write_text(baseline)
    base248.write_json(seed / "exact-subject.json", subject)
    projection = base243.base242.base234.base224.base217.projection(subject)
    base248.write_json(seed / "subject-position.json", projection)
    base248.write_json(seed / "bound-contact.json", pending)
    correction_contact = copy.deepcopy(pending)
    correction_contact["authority"] = AUTHORITY + "-visible-correction-contact"
    correction_contact["package"] = {
        **correction_contact["package"],
        "cases": base243.public_cases(target),
    }
    correction_contact["package_digest"] = (
        base243.base242.base234.base224.base219.digest(correction_contact["package"])
    )
    base248.write_json(seed / "correction-public-contact.json", correction_contact)
    base248.write_json(seed / "unresolved-world-receipt.json", world)
    base248.write_json(seed / "correction-contract.json", base243.contract(subject))
    base248.write_json(seed / "correction-decision.json", decision)
    (seed / "check_correction.py").write_text(base243.CHECKER)
    immutable = [
        "exact-subject.json",
        "subject-position.json",
        "bound-contact.json",
        "correction-public-contact.json",
        "unresolved-world-receipt.json",
        "correction-contract.json",
        "check_correction.py",
        "correction/reference.py",
        "correction/baseline-selected.py",
        *package_initializers(epoch),
        *[
            relative
            for relative in sorted(epoch["visible_sources"])
            if relative != extension["target_path"]
        ],
        "mutation-envelope.json",
        "README.md",
    ]
    envelope = {
        "authority": AUTHORITY + "-descriptor-derived-mutation-envelope",
        "descriptor_source_subject_digest": subject["artifact_digest"],
        "editable": [extension["target_path"], "correction-decision.json"],
        "immutable": immutable,
    }
    base248.write_json(seed / "mutation-envelope.json", envelope)
    (seed / "README.md").write_text(
        "Continue the exact unresolved expanded-world contact through its retained "
        "interface and world receipt. Derive the selected module and function from "
        "state. Revise only that function or surrender under correction-contract.json. "
        "Edit only the permitted source and correction-decision.json, run python3 "
        "check_correction.py, and inspect the exact diff. Follow-up cases are unavailable.\n"
    )
    return seed


def evaluate_workspace(seed, workspace, subject):
    extension, _, _, _, target = base248.selected(subject)
    try:
        decision = json.loads((workspace / "correction-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())[
            "immutable"
        ]
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in immutable
        )
        source = (workspace / extension["target_path"]).read_text()
        baseline = (workspace / "correction/baseline-selected.py").read_text()
        identities = base243.contract(subject)["required_identities"]
        exact = (
            set(decision) == base218.CORRECTION_CORE
            and all(decision.get(key) == value for key, value in identities.items())
            and decision.get("target_symbol") == target
            and decision.get("predicates") == base218.CORRECTION_PREDICATES
            and decision.get("disposition") in {"revise", "surrender"}
        )
        local = (
            source == baseline
            if decision.get("disposition") == "surrender"
            else base243.base235.base225.target_only_change(source, baseline, target)
        )
        public = (
            base243.compare(workspace, subject, base243.public_cases(target))
            if exact and local and decision.get("disposition") == "revise"
            else None
        )
        semantic = bool(
            exact
            and local
            and immutable_ok
            and (
                decision["disposition"] == "surrender"
                or (public and public["all_valid"] and public["matches"] == 4)
            )
        )
        return {
            "decision": decision,
            "source": source,
            "public": public,
            "semantic": semantic,
            "immutable_ok": immutable_ok,
            "error_type": None,
        }
    except (OSError, json.JSONDecodeError, KeyError, SyntaxError) as error:
        return {
            "decision": None,
            "source": None,
            "public": None,
            "semantic": False,
            "immutable_ok": False,
            "error_type": type(error).__name__,
        }


def run_corrector(context, p82, root, subject):
    seed = seed_actor(root, subject, base243.decision_template(subject))
    extension, pending, world, _, _ = base248.selected(subject)
    label = "expanded-world-corrector"
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, base243.SCHEMA, (seed / "README.md").read_text().strip()
    )
    evaluated = evaluate_workspace(seed, workspace, subject)
    decision = evaluated["decision"]
    transport = (
        isinstance(output, dict)
        and output.get("action") == "correct-unresolved-contact"
        and output.get("files_changed")
        in (
            ["correction-decision.json", extension["target_path"]],
            [extension["target_path"], "correction-decision.json"],
        )
        and isinstance(output.get("next_pursuit"), str)
        and bool(output["next_pursuit"].strip())
    )
    expected = (
        ["correction-decision.json", extension["target_path"]]
        if decision and decision.get("disposition") == "revise"
        else ["correction-decision.json"]
    )
    audit = context.audit_actor(
        label,
        output,
        base_audit,
        evaluated["semantic"] and transport,
        expected,
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(
        evaluated["semantic"] and transport and base236.g10(normalized)
    )
    binding = None
    if accepted:
        source = evaluated["source"]
        body = {
            "authority": AUTHORITY + "-bound-correction",
            "source_subject_digest": subject["artifact_digest"],
            "contact_identity": pending["contact_identity"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "target_path": extension["target_path"],
            "decision": decision,
            "patched_source": source if decision["disposition"] == "revise" else None,
            "patched_source_digest": (
                p82.digest(source) if decision["disposition"] == "revise" else None
            ),
            "public_result": evaluated["public"],
            "denial_provenance": normalized["provenance"],
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        base248.write_json(context.evidence(label) / "bound-correction.json", binding)
    return {
        "accepted": binding is not None,
        "binding": binding,
        "decision": decision,
        "public": evaluated["public"],
        "audit": audit,
        "g10_disposition": accepted,
        "output": output,
        "workspace_evaluation": {
            "immutable_ok": evaluated["immutable_ok"],
            "error_type": evaluated["error_type"],
        },
    }


base243.seed_actor = seed_actor
base243.run_corrector = run_corrector


def fixture_workspace(root, subject, p82):
    decision = base243.decision_template(subject)
    decision.update(
        rationale="Use the consequence-weighted feasible-set rule exposed by the active descriptor.",
        next_pursuit="Assimilate this corrected surface and continue.",
    )
    seed = seed_actor(root, subject, decision)
    workspace = root / "workspace"
    shutil.copytree(seed, workspace)
    extension, _, _, epoch, _ = base248.selected(subject)
    (workspace / extension["target_path"]).write_text(base243.corrected_fixture(subject))
    evaluated = evaluate_workspace(seed, workspace, subject)
    envelope = json.loads((seed / "mutation-envelope.json").read_text())
    roots = package_initializers(epoch)
    return {
        "source_subject_digest": subject["artifact_digest"],
        "package_initializers": roots,
        "all_immutable_paths_exist": all(
            (seed / relative).exists() for relative in envelope["immutable"]
        ),
        "only_descriptor_initializers": sorted(
            relative
            for relative in envelope["immutable"]
            if relative.endswith("/__init__.py")
        )
        == roots,
        "workspace_evaluator_passed": evaluated["semantic"]
        and evaluated["immutable_ok"]
        and evaluated["error_type"] is None,
        "public_4_of_4": bool(
            evaluated["public"] and evaluated["public"]["matches"] == 4
        ),
        "corrected_source_digest": p82.digest(evaluated["source"]),
    }


def live_checks(transitions, subject, parent, runtime, route, identity):
    expected = [
        "outward-correct",
        "expanded-select",
        "outward-correct",
        "expanded-select",
        "outward-correct",
        "expanded-select",
        "outward-correct",
    ]
    corrections = [row for row in transitions if row["operation"] == "outward-correct"]
    selections = [row for row in transitions if row["operation"] == "expanded-select"]
    selected_targets = [
        row["actor"]["decision"]["next_contact"]["target_symbol"]
        for row in selections
        if row.get("actor")
        and row["actor"].get("decision")
        and row["actor"]["decision"].get("next_contact")
    ]
    checks = {
        "seven_identical_null_pulses": len(transitions) == 7
        and all(row["pulse"]["content"] is None for row in transitions),
        "derived_sequence": [row["operation"] for row in transitions] == expected,
        "seven_fresh_actors": sum(row["fresh_actor_count"] for row in transitions)
        == 7,
        "all_g10_accepted": len(transitions) == 7
        and all(
            row.get("actor")
            and row["actor"].get("accepted")
            and row["actor"].get("g10_disposition")
            for row in transitions
        ),
        "corrections_4_6_2": len(corrections) == 4
        and all(
            row.get("actor")
            and row["actor"].get("public")
            and row["actor"]["public"]["matches"] == 4
            and row.get("world")
            and row["world"]["result"]["matches"] == 6
            and row["world"]["unchanged_control"]["matches"] == 2
            for row in corrections
        ),
        "selections_2_of_6": len(selections) == 3
        and all(
            row.get("actor")
            and row["actor"].get("public", {}).get("all_valid")
            and row.get("world")
            and row["world"]["result"]["matches"] == 2
            for row in selections
        ),
        "three_distinct_state_selections": len(selected_targets) == 3
        and len(set(selected_targets)) == 3,
        "active_epoch_saturated": len(base244.remaining_epoch(subject)) == 0,
        "next_operation_expansion": base248.operation_for(subject)
        == "expand-environment",
        "provider_stream_empty": base247.next_world(subject) is None,
        "interface_installed": subject.get("active_streamed_world_interface", {}).get(
            "authority"
        )
        == base248.AUTHORITY + "-provider-interface",
        "prior_epoch_preserved": subject["actor_authored_environment_epochs"][0]
        == parent["actor_authored_environment_epochs"][0],
        "inherited_registry_unchanged": subject["expanded_semantic_environment"][
            "registry"
        ]
        == parent["expanded_semantic_environment"]["registry"],
        "final_open_assimilate": subject["continuation"]["status"] == "open"
        and subject["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and runtime.identity_conforms(subject),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    return checks


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = (
        lineage.selector_base,
        lineage.base,
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
    run = (args.evidence_root or store / "runs/OT-0249").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0248",
        "unchanged-open-subject-after-descriptor-audit-rejection.json",
    )
    result248 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0248",
        "descriptor-neutral-second-epoch-driver-rejected-aggregate.json",
    )
    landscape = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0242",
        "open-subject-after-environment-expansion.json",
    )
    fixture = run.parent / "OT-0249-preflight"
    shutil.rmtree(fixture, ignore_errors=True)
    fixture.mkdir(parents=True)
    workspace_fixtures = [
        fixture_workspace(fixture / "landscape", landscape, p82),
        fixture_workspace(fixture / "resilience", parent, p82),
    ]
    initial = base248.fixture_correction(fixture / "initial", parent, p82)["final"]
    remaining = [row["target_symbol"] for row in base244.remaining_epoch(initial)]
    branches = [
        base248.fixture_walk(
            fixture / ("branch-" + "-".join(order)), parent, order, p82
        )
        for order in itertools.permutations(remaining)
    ]
    branch_checks = []
    for branch in branches:
        corrections = branch["steps"][::2]
        selections = branch["steps"][1::2]
        branch_checks.append(
            {
                "order": branch["order"],
                "all_checkers": all(row["checker"] for row in branch["steps"]),
                "corrections_4_6_2": all(
                    row["public"]["matches"] == 4
                    and row["followup"]["result"]["matches"] == 6
                    and row["followup"]["unchanged_control"]["matches"] == 2
                    for row in corrections
                ),
                "selections_2_of_6": all(
                    row["public"]["all_valid"]
                    and row["world"]["result"]["matches"] == 2
                    for row in selections
                ),
                "prompts_target_neutral": all(
                    row["target"] not in row["prompt"] for row in branch["steps"]
                ),
                "final_saturated": len(base244.remaining_epoch(branch["final"])) == 0
                and base248.operation_for(branch["final"]) == "expand-environment",
                "final_conforms": runtime.identity_conforms(branch["final"]),
            }
        )
    rejected_row = {
        "operation": "outward-correct",
        "pulse": {"content": None},
        "actor": {"accepted": False, "g10_disposition": False},
        "world": None,
        "fresh_actor_count": 1,
    }
    route = (
        base248.base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(
            parent["active_executable_routing_selector"]["route"],
            parent["actor_authored_contact_mechanisms"][-1]["expression"],
        )
    )
    identity = authority_base.reuse.extension_base.evaluate(
        authority_base.reuse.extension_base.load_operation(
            parent["developmental_property_extensions"][0]["operation_source"]
        ),
        authority_base.reuse.accumulated_floor(),
    )
    rejection_checks = live_checks(
        [rejected_row], parent, parent, runtime, route, identity
    )
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and runtime.identity_conforms(parent),
        "ot0248_exact_rejection": result248["observer_disposition"] == "rejected"
        and result248["receipt_digest"] == OT248_RECEIPT
        and result248["final_subject_digest"] == PARENT_DIGEST,
        "both_descriptor_workspace_evaluators_pass": len(workspace_fixtures) == 2
        and all(
            all(value for key, value in row.items() if key != "source_subject_digest")
            for row in workspace_fixtures
        ),
        "three_remaining_six_orders": len(remaining) == 3
        and len(branches) == 6
        and {tuple(row["order"]) for row in branch_checks}
        == set(itertools.permutations(remaining)),
        "all_branch_controls_pass": all(
            all(value for key, value in row.items() if key != "order")
            for row in branch_checks
        ),
        "selected_targets_not_hardcoded": all(
            target not in Path(__file__).read_text() for target in remaining
        ),
        "rejection_reporter_total": rejection_checks["passed"] is False
        and rejection_checks["all_g10_accepted"] is False,
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "workspace_fixtures": workspace_fixtures,
        "remaining": remaining,
        "branches": branch_checks,
        "rejection_reporter_checks": rejection_checks,
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0249 evidence")
    run.mkdir(parents=True)
    base248.write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    subject = parent
    transitions = []
    for index in range(1, 8):
        row, subject = base248.continue_once(
            runtime,
            base,
            base130,
            repo,
            p82,
            run / f"pulse-{index}",
            subject,
        )
        transitions.append(row)
        if not row.get("actor") or not row["actor"].get("accepted") or not row.get(
            "world"
        ):
            break
    gates = live_checks(transitions, subject, parent, runtime, route, identity)
    gates["preflight_passed"] = checks["passed"]
    gates["passed"] = all(value for key, value in gates.items() if key != "passed")
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "transitions": transitions,
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": subject["continuation"]["status"],
        "final_subject_digest": subject["artifact_digest"],
        "fresh_actor_count": sum(row["fresh_actor_count"] for row in transitions),
    }
    result["receipt_digest"] = p82.digest(result)
    base248.write_json(run / "aggregate.json", result)
    base248.write_json(run / "final-full-subject.json", subject)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
