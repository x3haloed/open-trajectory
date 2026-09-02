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
BASE_PATH = ROOT / "ot_0251_retained_streamed_correction_consequence.py"
BASE_SHA256 = "ee28ea8a0c7e1f3e928861d5a8055edae550cacbc34d2c8c4d4fe7ee223375f4"
PARENT_DIGEST = "e749515af3b09ef4c2f2221667f62c3f4eeb6dbadb718e1e53384a4b2a07cf34"
OT251_RECEIPT = "088047aab84e140413390522a86406d73fa23854d5de643957da746dc077a865"
AUTHORITY = "ot-0252-symmetric-descriptor-complete-epoch-suffix"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0251 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0252_frozen_ot0251", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base251 = load_base()
base250 = base251.base250
base249 = base251.base249
base248 = base251.base248
base247 = base248.base247
base245 = base248.base245
base244 = base248.base244
base243 = base249.base243
base242 = base248.base242
base236 = base249.base236
authority_base = base251.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def package_initializers(subject):
    epoch = subject["actor_authored_environment_epochs"][-1]
    return sorted(
        {
            str(Path(relative).parent / "__init__.py")
            for relative in epoch["visible_sources"]
        }
    )


def selection_seed(root, subject, decision):
    seed = root / "seed"
    seed.mkdir(parents=True)
    base245.write_world(seed, subject)
    epoch = subject["actor_authored_environment_epochs"][-1]
    write_json(seed / "exact-subject.json", subject)
    projection = base242.base234.base224.base217.projection(subject)
    write_json(seed / "subject-position.json", projection)
    write_json(seed / "local-frontier-ledger.json", subject["local_frontier_ledger"])
    write_json(
        seed / "expansion-contract.json",
        {
            "authority": AUTHORITY + "-descriptor-selection-contract",
            "contact_fields": sorted(base242.CONTACT_CORE),
            "predicates": base242.PREDICATES,
        },
    )
    write_json(seed / "expanded-selection.json", decision)
    (seed / "check_selection.py").write_text(base245.CHECKER)
    immutable = [
        "exact-subject.json",
        "subject-position.json",
        "local-frontier-ledger.json",
        "expansion-contract.json",
        "check_selection.py",
        *package_initializers(subject),
        *sorted(epoch["visible_sources"]),
        "mutation-envelope.json",
        "README.md",
    ]
    write_json(
        seed / "mutation-envelope.json",
        {
            "authority": AUTHORITY + "-descriptor-selection-mutation-envelope",
            "descriptor_source_subject_digest": subject["artifact_digest"],
            "editable": ["expanded-selection.json"],
            "immutable": immutable,
        },
    )
    (seed / "README.md").write_text(
        "Continue from the exact subject position under the content-free "
        "expanded-selection pulse. Inspect the retained executable environment "
        "and bind one coherent contact not already present in the ledger. No task "
        "or target is assigned; do not reopen a completed contact or invent one "
        "merely to avoid stopping. Edit only expanded-selection.json, run python3 "
        "check_selection.py, and inspect the exact diff. Hidden consequence is "
        "unavailable.\n"
    )
    return seed


def evaluate_selection_workspace(seed, workspace, subject):
    try:
        decision = json.loads((workspace / "expanded-selection.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())[
            "immutable"
        ]
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in immutable
        )
        structural = base242.structural(
            decision, workspace, subject["local_frontier_ledger"]
        )
        contact = decision["next_contact"] if structural else None
        target = contact["target_symbol"] if contact else None
        path = contact["target_path"] if contact else None
        eligible = {
            (row["target_path"], row["target_symbol"])
            for row in base244.remaining_epoch(subject)
        }
        semantic = bool(immutable_ok and structural and (path, target) in eligible)
        public = base242.execute_public(workspace, decision) if semantic else None
        semantic = bool(semantic and public and public["all_valid"])
        return {
            "decision": decision,
            "public": public,
            "target": target,
            "path": path,
            "semantic": semantic,
            "immutable_ok": immutable_ok,
            "error_type": None,
        }
    except (OSError, json.JSONDecodeError, KeyError, SyntaxError) as error:
        return {
            "decision": None,
            "public": None,
            "target": None,
            "path": None,
            "semantic": False,
            "immutable_ok": False,
            "error_type": type(error).__name__,
        }


def selection_schema_valid(output):
    return (
        isinstance(output, dict)
        and set(output) == {"action", "files_changed", "selected_target"}
        and output.get("action") == "select-expanded-opportunity"
        and isinstance(output.get("files_changed"), list)
        and all(isinstance(row, str) for row in output["files_changed"])
        and isinstance(output.get("selected_target"), str)
        and bool(output["selected_target"].strip())
    )


def run_selection(context, p82, root, subject):
    seed = selection_seed(root, subject, base245.template())
    label = "expanded-epoch-selection-actor"
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, base245.SCHEMA, (seed / "README.md").read_text().strip()
    )
    evaluated = evaluate_selection_workspace(seed, workspace, subject)
    schema = selection_schema_valid(output)
    audit = context.audit_actor(
        label,
        output,
        base_audit,
        evaluated["semantic"] and schema,
        ["expanded-selection.json"],
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(evaluated["semantic"] and schema and base236.g10(normalized))
    fidelity = (
        base242.base234.claim_fidelity(
            output, evaluated["target"], evaluated["path"]
        )
        if evaluated["target"] and evaluated["path"]
        else "inconsistent"
    )
    binding = None
    if accepted:
        decision = evaluated["decision"]
        contact = decision["next_contact"]
        body = {
            "authority": AUTHORITY + "-actor-authored-selection-binding",
            "source_subject_digest": subject["artifact_digest"],
            "pulse_content": None,
            "derived_operation": "expanded-select",
            "g10_transition_receipt_digest": subject["active_effect_audit_regime"][
                "transition_receipt_digest"
            ],
            "actor_patch_digest": audit["patch_digest"],
            "decision": decision,
            "contact_identity": p82.digest(
                {
                    "target_path": contact["target_path"],
                    "target_symbol": contact["target_symbol"],
                    "abi": contact["abi"],
                    "cases": contact["cases"],
                    "predicates": contact["predicates"],
                }
            ),
            "public_result": evaluated["public"],
            "denial_provenance": normalized["provenance"],
            "target_claim_fidelity": fidelity,
            "path_claim_authority": "provenance-only",
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-expanded-contact.json", binding)
    return {
        "accepted": binding is not None,
        "binding": binding,
        "decision": evaluated["decision"],
        "public": evaluated["public"],
        "audit": audit,
        "g10_disposition": accepted,
        "output": output,
        "target_claim_fidelity": fidelity,
        "workspace_evaluation": {
            "immutable_ok": evaluated["immutable_ok"],
            "error_type": evaluated["error_type"],
        },
    }


def run_correction(context, p82, root, subject):
    seed = base249.seed_actor(root, subject, base243.decision_template(subject))
    extension, pending, world, _, _ = base248.selected(subject)
    label = "expanded-world-corrector"
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, base243.SCHEMA, (seed / "README.md").read_text().strip()
    )
    evaluated = base249.evaluate_workspace(seed, workspace, subject)
    decision = evaluated["decision"]
    schema = base250.schema_valid(output)
    expected = (
        ["correction-decision.json", extension["target_path"]]
        if decision and decision.get("disposition") == "revise"
        else ["correction-decision.json"]
    )
    audit = context.audit_actor(
        label,
        output,
        base_audit,
        evaluated["semantic"] and schema,
        expected,
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(evaluated["semantic"] and schema and base236.g10(normalized))
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
            "path_claim_authority": "provenance-only",
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-correction.json", binding)
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


base245.seed_actor = selection_seed
base245.run_actor = run_selection
base243.run_corrector = run_correction


def selection_fixture_workspace(root, subject, target):
    decision = base245.fixture_decision(target)
    seed = selection_seed(root, subject, decision)
    evaluated = evaluate_selection_workspace(seed, seed, subject)
    envelope = json.loads((seed / "mutation-envelope.json").read_text())
    initializers = package_initializers(subject)
    return {
        "source_subject_digest": subject["artifact_digest"],
        "package_initializers": initializers,
        "all_immutable_paths_exist": all(
            (seed / relative).exists() for relative in envelope["immutable"]
        ),
        "only_descriptor_initializers": sorted(
            relative
            for relative in envelope["immutable"]
            if relative.endswith("/__init__.py")
        )
        == initializers,
        "workspace_evaluator_passed": evaluated["semantic"]
        and evaluated["immutable_ok"]
        and evaluated["error_type"] is None,
        "public_valid": bool(
            evaluated["public"] and evaluated["public"]["all_valid"]
        ),
    }


def fixture_suffix(root, parent, order, p82):
    subject = parent
    steps = []
    for index, target in enumerate(order, 1):
        selection = base248.fixture_selection(
            root / f"select-{index}", subject, target, p82
        )
        steps.append(selection)
        subject = selection["final"]
        correction = base248.fixture_correction(
            root / f"correct-{index}", subject, p82
        )
        steps.append(correction)
        subject = correction["final"]
    return {"order": list(order), "steps": steps, "final": subject}


def live_checks(transitions, subject, parent, runtime, route, identity):
    expected = [
        "expanded-select",
        "outward-correct",
        "expanded-select",
        "outward-correct",
        "expanded-select",
        "outward-correct",
    ]
    selections = [row for row in transitions if row["operation"] == "expanded-select"]
    corrections = [row for row in transitions if row["operation"] == "outward-correct"]
    targets = [
        row["actor"]["decision"]["next_contact"]["target_symbol"]
        for row in selections
        if row.get("actor")
        and row["actor"].get("decision")
        and row["actor"]["decision"].get("next_contact")
    ]
    checks = {
        "six_identical_null_pulses": len(transitions) == 6
        and all(row["pulse"]["content"] is None for row in transitions),
        "derived_sequence": [row["operation"] for row in transitions] == expected,
        "six_fresh_actors": sum(row["fresh_actor_count"] for row in transitions) == 6,
        "all_g10_accepted": len(transitions) == 6
        and all(
            row.get("actor")
            and row["actor"].get("accepted")
            and row["actor"].get("g10_disposition")
            for row in transitions
        ),
        "selections_2_of_6": len(selections) == 3
        and all(
            row["actor"].get("public", {}).get("all_valid")
            and row.get("world")
            and row["world"]["result"]["matches"] == 2
            for row in selections
        ),
        "corrections_4_6_2": len(corrections) == 3
        and all(
            row["actor"].get("public", {}).get("matches") == 4
            and row.get("world")
            and row["world"]["result"]["matches"] == 6
            and row["world"]["unchanged_control"]["matches"] == 2
            for row in corrections
        ),
        "three_distinct_state_selections": len(targets) == 3
        and len(set(targets)) == 3,
        "active_epoch_saturated": len(base244.remaining_epoch(subject)) == 0,
        "next_operation_expansion": base248.operation_for(subject)
        == "expand-environment",
        "provider_stream_empty": base247.next_world(subject) is None,
        "authority_propagation_preserved": subject[
            "active_streamed_correction_output_regime"
        ]["authority"]
        == base250.AUTHORITY,
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
    run = (args.evidence_root or store / "runs/OT-0252").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0251",
        "open-subject-after-retained-streamed-correction.json",
    )
    result251 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0251",
        "retained-streamed-correction-consequence-aggregate.json",
    )
    landscape = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0244",
        "open-subject-at-expanded-selection.json",
    )
    fixture = run.parent / "OT-0252-preflight"
    shutil.rmtree(fixture, ignore_errors=True)
    fixture.mkdir(parents=True)
    remaining = [row["target_symbol"] for row in base244.remaining_epoch(parent)]
    landscape_target = base244.remaining_epoch(landscape)[0]["target_symbol"]
    selection_workspaces = [
        selection_fixture_workspace(
            fixture / "selection-landscape", landscape, landscape_target
        ),
        selection_fixture_workspace(
            fixture / "selection-resilience", parent, remaining[0]
        ),
    ]
    branches = [
        fixture_suffix(
            fixture / ("branch-" + "-".join(order)), parent, order, p82
        )
        for order in itertools.permutations(remaining)
    ]
    branch_checks = []
    for branch in branches:
        selections = branch["steps"][::2]
        corrections = branch["steps"][1::2]
        branch_checks.append(
            {
                "order": branch["order"],
                "all_checkers": all(row["checker"] for row in branch["steps"]),
                "selections_2_of_6": all(
                    row["public"]["all_valid"]
                    and row["world"]["result"]["matches"] == 2
                    for row in selections
                ),
                "corrections_4_6_2": all(
                    row["public"]["matches"] == 4
                    and row["followup"]["result"]["matches"] == 6
                    and row["followup"]["unchanged_control"]["matches"] == 2
                    for row in corrections
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
        "operation": "expanded-select",
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
        "parent_exact_expanded_select": parent["artifact_digest"] == PARENT_DIGEST
        and parent["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and base248.operation_for(parent) == "expanded-select"
        and runtime.identity_conforms(parent),
        "ot0251_exact_promotion": result251["observer_disposition"] == "promoted"
        and result251["receipt_digest"] == OT251_RECEIPT
        and result251["final_subject_digest"] == PARENT_DIGEST,
        "both_selection_descriptors_pass": len(selection_workspaces) == 2
        and all(
            all(value for key, value in row.items() if key != "source_subject_digest")
            for row in selection_workspaces
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
        "active_authority_present": parent[
            "active_streamed_correction_output_regime"
        ]["authority"]
        == base250.AUTHORITY,
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "selection_workspaces": selection_workspaces,
        "remaining": remaining,
        "branches": branch_checks,
        "rejection_reporter_checks": rejection_checks,
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0252 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    subject = parent
    transitions = []
    for index in range(1, 7):
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
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", subject)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
