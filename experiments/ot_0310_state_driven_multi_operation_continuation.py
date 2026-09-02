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
BASE_PATH = ROOT / "ot_0309_coherent_two_opportunity_selection.py"
BASE_SHA256 = "e35b9f02a61155aef893bb0ff9d42831317193b9d8aa3baba17f67945cbb48b1"
PARENT_DIGEST = "bf86811032d3b3d24efcfdbe6f21125cf1ba8b47c6f1a1b5a000bc7311130070"
OT309_RECEIPT = "76c9992b94f61b96ef896734c58615e0645a18c65f6b6164411a91919abc2b96"
AUTHORITY = "ot-0310-state-driven-multi-operation-continuation"
MAX_OPERATIONS = 10
MAX_ACTORS = 6
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0309 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0310_frozen_ot0309", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base309 = load_base()
base308 = base309.base308
base307 = base309.base307
b = base309.b
COHERENCE_DERIVE = b.base272.derive
INHERITED_DERIVE = base308.INHERITED_DERIVE
ORIGINAL_CLAIM_FIDELITY = b.base272.base245.base242.base234.claim_fidelity

base309.AUTHORITY = AUTHORITY
base308.AUTHORITY = AUTHORITY
base307.AUTHORITY = AUTHORITY
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY
b.base274.MAX_CALLS = MAX_ACTORS
b.base274.base273.AUTHORITY = AUTHORITY
b.base274.base271.AUTHORITY = AUTHORITY
b.base272.base252.AUTHORITY = AUTHORITY
b.base272.base245.AUTHORITY = AUTHORITY
b.base272.base270.AUTHORITY = AUTHORITY


def write_json(path, value):
    base309.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0310").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0309",
        "open-subject-after-coherent-two-opportunity-selection.json",
    )
    result309 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0309",
        "coherent-two-opportunity-selection-aggregate.json",
    )
    result305 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0305",
        "subject-priority-world-selection-aggregate.json",
    )
    selected_world = result305["selection"]["selected_world_id"]
    provider_index = next(
        index
        for index, provider in enumerate(result305["providers"], 1)
        if provider["package"]["world_id"] == selected_world
    )
    package = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0305",
        f"subject-blind-provider-{provider_index:02d}-world-package.json",
    )
    result280 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0280",
        "import-stable-world-evaluator-aggregate.json",
    )
    return (
        repo,
        run,
        p82,
        runtime,
        parent,
        result309,
        result305,
        package,
        result280,
        core,
        base130,
    )


def projection_receipt_valid(subject, p82):
    projection = subject.get("active_opportunity_projection") or {}
    receipt = projection.get("projection_receipt_digest")
    body = {
        key: value
        for key, value in projection.items()
        if key != "projection_receipt_digest"
    }
    opportunities = projection.get("opportunities")
    count = projection.get("opportunity_count")
    return bool(
        isinstance(receipt, str)
        and receipt == p82.digest(body)
        and isinstance(opportunities, list)
        and isinstance(count, int)
        and count == len(opportunities)
        and projection.get("status") == ("active" if count else "saturated")
    )


def refresh_due(subject, p82):
    driver = subject.get("fixed_g6_recurrence_driver") or {}
    target = driver.get("last_target")
    ledger = subject.get("local_frontier_ledger", {}).get("targets", {})
    target_state = ledger.get(target) if isinstance(target, str) else None
    projection = subject.get("active_opportunity_projection") or {}
    old = projection.get("opportunities") or []
    resolved = b.base264.base253.derive(subject)
    new = resolved.get("opportunities") or []
    old_pairs = {
        (row.get("target_path"), row.get("target_symbol"))
        for row in old
        if isinstance(row, dict)
    }
    new_pairs = {
        (row.get("target_path"), row.get("target_symbol"))
        for row in new
        if isinstance(row, dict)
    }
    removed = old_pairs - new_pairs
    return bool(
        driver.get("phase") == "assimilate"
        and INHERITED_DERIVE(subject, p82) == "refresh-opportunity-projection"
        and projection_receipt_valid(subject, p82)
        and isinstance(target_state, dict)
        and target_state.get("status") == "verified-local"
        and target_state.get("latest_world_outcome") == "success"
        and bool(target_state.get("correction_receipts"))
        and bool(target_state.get("independent_success_receipts"))
        and resolved.get("status") in {"active", "saturated"}
        and not resolved.get("source_errors")
        and len(old_pairs) == len(old)
        and len(new_pairs) == len(new)
        and new_pairs < old_pairs
        and len(removed) == 1
        and next(iter(removed))[1] == target
    )


def derive(subject, p82):
    if refresh_due(subject, p82):
        return "refresh-opportunity-projection"
    return COHERENCE_DERIVE(subject, p82)


b.base272.derive = derive


def canonical_claim_fidelity(output, target, path):
    reported = output.get("selected_target") if isinstance(output, dict) else None
    if reported == target:
        return "exact"
    if reported in {f"{path}:{target}", f"{path}::{target}"}:
        return "qualified-consistent"
    return "inconsistent"


b.base272.base245.base242.base234.claim_fidelity = canonical_claim_fidelity


def fixture_success(subject, package, result280, p82):
    actor, public, world = base307.fixture_revise(
        subject, package, result280, p82, success=True
    )
    final = (
        base307.base273.compile_success(subject, actor, world, p82)
        if base307.base274.feedback_mode(subject)
        else base307.base271.compile_correction(subject, actor, world, p82)
    )
    return actor, public, world, final


def invalid_refresh_controls(subject, p82):
    controls = {}
    changed = copy.deepcopy(subject)
    changed.pop("artifact_digest", None)
    changed["active_opportunity_projection"]["opportunity_count"] += 1
    changed = p82.seal(changed)
    controls["stale-receipt-malformed-count"] = not refresh_due(changed, p82)

    changed = copy.deepcopy(subject)
    changed.pop("artifact_digest", None)
    projection = changed["active_opportunity_projection"]
    projection["opportunities"] = projection["opportunities"][:-1]
    projection["opportunity_count"] = len(projection["opportunities"])
    projection.pop("projection_receipt_digest", None)
    projection["projection_receipt_digest"] = p82.digest(projection)
    changed = p82.seal(changed)
    controls["resealed-wrong-removal"] = not refresh_due(changed, p82)

    changed = copy.deepcopy(subject)
    changed.pop("artifact_digest", None)
    target = changed["fixed_g6_recurrence_driver"]["last_target"]
    changed["local_frontier_ledger"]["targets"][target][
        "independent_success_receipts"
    ] = []
    changed = p82.seal(changed)
    controls["missing-success-authority"] = not refresh_due(changed, p82)
    return controls


def preflight(root, p82, runtime, parent, result309, result305, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    first_actor, first_public, first_world, corrected = fixture_success(
        parent, package, result280, p82
    )
    controls = invalid_refresh_controls(corrected, p82)
    refreshed = b.base264.refresh_projection_only(corrected, p82)
    repaired, repair_receipt = base308.repair(refreshed, p82)
    opportunities = repaired["active_opportunity_projection"]["opportunities"]
    selected_target = opportunities[0]["target_symbol"]
    selection = b.base272.selection_fixture(
        root / "selection",
        repaired,
        package,
        result280,
        selected_target,
        p82,
        runtime,
    )
    selected = selection["final"]
    _, second_public, second_world, corrected_again = fixture_success(
        selected, package, result280, p82
    )
    refreshed_again = b.base264.refresh_projection_only(corrected_again, p82)
    repaired_again, _ = base308.repair(refreshed_again, p82)
    target_path = opportunities[0]["target_path"]
    claim_rows = {
        "bare": canonical_claim_fidelity(
            {"selected_target": selected_target}, selected_target, target_path
        ),
        "single-colon": canonical_claim_fidelity(
            {"selected_target": f"{target_path}:{selected_target}"},
            selected_target,
            target_path,
        ),
        "double-colon": canonical_claim_fidelity(
            {"selected_target": f"{target_path}::{selected_target}"},
            selected_target,
            target_path,
        ),
        "wrong": canonical_claim_fidelity(
            {"selected_target": "wrong"}, selected_target, target_path
        ),
    }
    route, identity = b.base272.base265.floors(parent)
    priority = parent["subject_priority_contact_receipts"][-1]
    source = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "exact_ot0309_parent": parent["artifact_digest"] == PARENT_DIGEST
        and result309["receipt_digest"] == OT309_RECEIPT
        and result309["observer_disposition"] == "promoted"
        and derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "post_correction_refresh_precedence": first_public["matches"]
        == first_public["case_count"]
        and first_world["result"]["matches"] == 6
        and first_world["unchanged_control"]["matches"] == 2
        and refresh_due(corrected, p82)
        and derive(corrected, p82) == "refresh-opportunity-projection"
        and runtime.identity_conforms(corrected),
        "three_invalid_refresh_controls_reject": all(controls.values()),
        "refresh_then_repair_then_selection": derive(refreshed, p82)
        == base308.REPAIR_OPERATION
        and repair_receipt["source_subject_digest"]
        == refreshed["artifact_digest"]
        and derive(repaired, p82) == "expanded-select"
        and len(opportunities) == 1
        and runtime.identity_conforms(repaired),
        "remaining_selection_gets_contradiction": selection["conformant"]
        and selection["world"]["result"]["matches"] == 2
        and selection["world"]["outcome"] == "unresolved"
        and derive(selected, p82) == "outward-correct",
        "second_correction_reaches_expansion": second_public["matches"]
        == second_public["case_count"]
        and second_world["result"]["matches"] == 6
        and second_world["unchanged_control"]["matches"] == 2
        and derive(corrected_again, p82) == "refresh-opportunity-projection"
        and derive(refreshed_again, p82) == base308.REPAIR_OPERATION
        and derive(repaired_again, p82) == "expand-environment"
        and repaired_again["active_opportunity_projection"]["opportunity_count"]
        == 0
        and runtime.identity_conforms(repaired_again),
        "one_new_stake_across_chain": base309.selection_continuity(
            parent, repaired_again
        ),
        "canonical_target_reports": claim_rows
        == {
            "bare": "exact",
            "single-colon": "qualified-consistent",
            "double-colon": "qualified-consistent",
            "wrong": "inconsistent",
        },
        "priority_negative_preserved": result305["observer_disposition"]
        == "rejected"
        and result305["e11"]["priority_bearing_contact"] is False
        and priority["selected_world_id"] == priority["blind_control_world_id"],
        "dynamic_targets_not_hardcoded": all(
            token not in source
            for target, path in b.base268.evaluate_package(
                package, p82.digest
            )["targets"].items()
            for token in (target, path)
        ),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0309_receipt_digest": result309["receipt_digest"],
        "operation_budget": MAX_OPERATIONS,
        "actor_budget": MAX_ACTORS,
        "refresh_controls": controls,
        "claim_fidelity_controls": claim_rows,
        "prospective_operations": [
            "outward-correct",
            "refresh-opportunity-projection",
            "repair-actor-facing-coherence",
            "expanded-select",
            "outward-correct",
            "refresh-opportunity-projection",
            "repair-actor-facing-coherence",
        ],
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def operation_result(index, subject, operation, final, checks, **values):
    result = {
        "authority": AUTHORITY + f"-operation-{index:02d}",
        "operation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": {
            "content": PULSE,
            "derived_operation": operation,
        },
        **values,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
    }
    return result


def run_operation(
    index,
    root,
    subject,
    operation,
    repo,
    p82,
    runtime,
    package,
    result280,
    core,
    base130,
):
    actor = world = feedback = receipt = None
    fresh_actor_count = 0
    if operation == "outward-correct":
        context = base307.base274.context_for(core, base130, runtime, root, repo)
        actor, world, feedback, final, transition = base307.run_correction(
            context, p82, root, subject, package, result280
        )
        disposition = (actor.get("decision") or {}).get("disposition")
        public_count = actor["public"]["case_count"] if actor.get("public") else 0
        checks = {
            "fresh_workspace": not (root / "actor").resolve().is_relative_to(repo),
            "actor_accepted": actor.get("accepted") is True,
            "g10_accepted": actor.get("g10_disposition") is True,
            "disclosed_pass_or_surrender": disposition == "surrender"
            or bool(
                actor.get("public")
                and actor["public"]["matches"] == public_count
            ),
            "unchanged_2_of_6": bool(
                world and world["unchanged_control"]["matches"] == 2
            ),
            "consequence_routed": transition
            in {
                "success-to-refresh",
                "unresolved-to-more-correction",
                "surrender-to-more-correction",
            },
            "protected_exact": base307.protected(final)
            == base307.protected(subject),
            "open_conformant": final["continuation"]["status"] == "open"
            and runtime.identity_conforms(final),
        }
        fresh_actor_count = 1
        values = {
            "transition": transition,
            "actor": actor,
            "world": world,
            "feedback": feedback,
        }
    elif operation == "refresh-opportunity-projection":
        final = b.base264.refresh_projection_only(subject, p82)
        checks = {
            "refresh_due": refresh_due(subject, p82),
            "zero_fresh_actors": True,
            "projection_matches_resolver": final[
                "active_opportunity_projection"
            ]["opportunities"]
            == b.base264.base253.derive(final)["opportunities"],
            "next_is_coherence_repair": derive(final, p82)
            == base308.REPAIR_OPERATION,
            "protected_exact": base307.protected(final)
            == base307.protected(subject),
            "open_conformant": final["continuation"]["status"] == "open"
            and runtime.identity_conforms(final),
        }
        values = {"transition": "refresh-to-coherence-check"}
    elif operation == base308.REPAIR_OPERATION:
        final, receipt = base308.repair(subject, p82)
        checks = {
            "zero_fresh_actors": True,
            "narrative_only": base308.changed_keys(subject, final)
            == ["continuation", "unresolved"],
            "receipt_exact": receipt["source_subject_digest"]
            == subject["artifact_digest"],
            "coherence_restored": derive(final, p82)
            in {"expanded-select", "expand-environment"},
            "protected_exact": base307.protected(final)
            == base307.protected(subject),
            "open_conformant": final["continuation"]["status"] == "open"
            and runtime.identity_conforms(final),
        }
        values = {"transition": "coherence-restored", "repair_receipt": receipt}
    elif operation == "expanded-select":
        context = b.base274.context_for(core, base130, runtime, root, repo)
        actor, world, final = b.base272.live_selection(
            context, p82, root, subject, package, result280
        )
        selected = (actor.get("decision") or {}).get("next_contact") or {}
        checks = {
            "fresh_workspace": not (
                root / "expanded-epoch-selection-actor"
            ).resolve().is_relative_to(repo),
            "actor_accepted": actor.get("accepted") is True,
            "g10_accepted": actor.get("g10_disposition") is True,
            "selected_projected_target": {
                "target_path": selected.get("target_path"),
                "target_symbol": selected.get("target_symbol"),
            }
            in subject["active_opportunity_projection"]["opportunities"],
            "canonical_report": actor.get("target_claim_fidelity")
            in {"exact", "qualified-consistent"},
            "independent_2_of_6": bool(
                world
                and world["result"]["all_valid"]
                and world["result"]["matches"] == 2
                and world["outcome"] == "unresolved"
            ),
            "one_new_stake": base309.selection_continuity(subject, final),
            "next_is_correction": derive(final, p82) == "outward-correct",
            "open_conformant": final["continuation"]["status"] == "open"
            and runtime.identity_conforms(final),
        }
        fresh_actor_count = 1
        values = {
            "transition": "selection-to-correction",
            "actor": actor,
            "world": world,
        }
    else:
        raise RuntimeError(f"unsupported operation: {operation}")
    checks["content_free"] = PULSE is None
    checks["passed"] = all(checks.values())
    result = operation_result(
        index,
        subject,
        operation,
        final,
        checks,
        fresh_actor_count=fresh_actor_count,
        **values,
    )
    result["receipt_digest"] = p82.digest(result)
    return result, final


def ordered_subsequence(values, wanted):
    position = 0
    for value in values:
        if position < len(wanted) and value == wanted[position]:
            position += 1
    return position == len(wanted)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    (
        repo,
        run,
        p82,
        runtime,
        parent,
        result309,
        result305,
        package,
        result280,
        core,
        base130,
    ) = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(
            run / "preflight",
            p82,
            runtime,
            parent,
            result309,
            result305,
            package,
            result280,
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0310 unavailable")
    run.mkdir(parents=True, exist_ok=True)
    subject = parent
    rows = []
    actor_count = 0
    boundary = None
    for index in range(1, MAX_OPERATIONS + 1):
        operation = derive(subject, p82)
        if operation not in {
            "outward-correct",
            "refresh-opportunity-projection",
            base308.REPAIR_OPERATION,
            "expanded-select",
        }:
            boundary = {
                "kind": "unsupported-derived-operation",
                "operation": operation,
                "after_operation_count": len(rows),
            }
            break
        if actor_count + (operation in {"outward-correct", "expanded-select"}) > MAX_ACTORS:
            boundary = {
                "kind": "actor-budget",
                "operation": operation,
                "after_operation_count": len(rows),
            }
            break
        root = run / f"operation-{index:02d}"
        root.mkdir(parents=True)
        result, final = run_operation(
            index,
            root,
            subject,
            operation,
            repo,
            p82,
            runtime,
            package,
            result280,
            core,
            base130,
        )
        rows.append(result)
        actor_count += result["fresh_actor_count"]
        write_json(run / f"operation-{index:02d}-result.json", result)
        write_json(run / f"operation-{index:02d}-subject.json", final)
        subject = final
        if not result["checks"]["passed"]:
            boundary = {
                "kind": "failed-operation",
                "operation": operation,
                "after_operation_count": len(rows),
            }
            break
    if boundary is None:
        boundary = {
            "kind": "operation-budget",
            "operation": derive(subject, p82),
            "after_operation_count": len(rows),
        }
    operations = [row["pulse"]["derived_operation"] for row in rows]
    selection_rows = [
        row for row in rows if row["pulse"]["derived_operation"] == "expanded-select"
    ]
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "all_executed_operations_pass": bool(rows)
        and all(row["checks"]["passed"] for row in rows),
        "state_driven_cross_operation_path": ordered_subsequence(
            operations,
            [
                "outward-correct",
                "refresh-opportunity-projection",
                "repair-actor-facing-coherence",
                "expanded-select",
            ],
        ),
        "selection_received_contradiction": bool(selection_rows)
        and selection_rows[0]["world"]["result"]["matches"] == 2,
        "fresh_actor_budget_respected": 2 <= actor_count <= MAX_ACTORS
        and actor_count
        == sum(row["fresh_actor_count"] for row in rows),
        "one_new_stake": base309.selection_continuity(parent, subject),
        "coherence_repair_preserved_and_extended": subject.get(
            "actor_facing_coherence_repairs", []
        )[: len(parent.get("actor_facing_coherence_repairs", []))]
        == parent.get("actor_facing_coherence_repairs", [])
        and len(subject.get("actor_facing_coherence_repairs", []))
        > len(parent.get("actor_facing_coherence_repairs", [])),
        "boundary_is_censoring_not_failure": boundary["kind"]
        in {"unsupported-derived-operation", "actor-budget", "operation-budget"},
        "final_open_conformant": subject["continuation"]["status"] == "open"
        and runtime.identity_conforms(subject),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0309_receipt_digest": result309["receipt_digest"],
        "operation_receipt_digests": [row["receipt_digest"] for row in rows],
        "operations": operations,
        "fresh_actor_count": actor_count,
        "boundary": boundary,
        "checks": checks,
        "operational_transition_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": subject["continuation"]["status"],
        "final_subject_digest": subject["artifact_digest"],
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", subject)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
