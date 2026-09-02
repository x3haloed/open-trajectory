from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0281_morrowglass_wake_and_selection.py"
BASE_SHA256 = "aab05d5f929cc3bc2117f2ef580b113266f0136f548ffdc9b68507f8c1bf5f7b"
PARENT_DIGEST = "7c78dedafa62091b689414cf448da6baff130ade2a470de44b2b9520c8539174"
OT281_RECEIPT = "f20e5a583bb4555e7b2ca95045014df08d1d0a36204cec04ef9c94556780e5ac"
OT280_RECEIPT = "15d39db31b2031e2dd3e0c1f1917e4b4125ce2924cc3fcffc3f62710980d847c"
AUTHORITY = "ot-0282-morrowglass-recurrence-and-renewal"
MAX_CALLS = 18


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0281 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0282_frozen_ot0281", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base281 = load_base()
base280 = base281.base280
base279 = base281.base279
base278 = base281.base278
base274 = base278.base274
base273 = base274.base273
base272 = base274.base272
base271 = base274.base271
base268 = base274.base268
base267 = base268.base267
base264 = base274.base264
base260 = base274.base260
base256 = base274.base256
base244 = base274.base244
base236 = base268.base236
authority_base = base274.authority_base

base268.safe_module = base280.safe_module
base274.AUTHORITY = AUTHORITY
base274.OT268_RECEIPT = OT280_RECEIPT
base274.MAX_CALLS = MAX_CALLS
base272.OT268_RECEIPT = OT280_RECEIPT
base272.base270.OT268_RECEIPT = OT280_RECEIPT


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0282").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0281", "open-subject-at-morrowglass-contradiction.json"
    )
    result281 = selector.load_artifact(
        p82, repo, store, "OT-0281", "morrowglass-wake-and-selection-aggregate.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0280", "independent-morrowglass-world-package.json"
    )
    result280 = selector.load_artifact(
        p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result281, package, result280, core, base130


def correction_variant(subject, failures, package, result280, p82, runtime):
    return base278.correction_variant(
        subject, failures, package, result280, p82, runtime
    )


def prospective_branch(root, parent, order, depths, package, result280, p82, runtime):
    subject, first = correction_variant(
        parent, depths[0], package, result280, p82, runtime
    )
    corrections = [first]
    subject = base264.refresh_projection_only(subject, p82)
    selections = []
    for index, target in enumerate(order):
        selection = base272.selection_fixture(
            root / f"selection-{index}",
            subject,
            package,
            result280,
            target,
            p82,
            runtime,
        )
        selections.append(
            selection["checker"]
            and selection["semantic"]
            and selection["world"]["result"]["matches"] == 2
            and selection["world"]["ot0268_aggregate_receipt_digest"]
            == OT280_RECEIPT
            and selection["routes_correction"]
        )
        subject, correction = correction_variant(
            selection["final"],
            depths[index + 1],
            package,
            result280,
            p82,
            runtime,
        )
        corrections.append(correction)
        subject = base264.refresh_projection_only(subject, p82)
    observation = base272.empty_feed_observation(subject, p82)
    waiting, reused = base256.compile_wait(subject, observation, p82)
    repeated_observation = base272.empty_feed_observation(waiting, p82)
    repeated, repeated_reused = base256.compile_wait(
        waiting, repeated_observation, p82
    )
    example_evaluation = base268.evaluate_package(base268.EXAMPLE, p82.digest)
    example_scan = base267.scan_feed(
        repeated, [example_evaluation["public_package"]], p82.digest
    )
    return {
        "order": list(order),
        "depths": list(depths),
        "selections_passed": all(selections),
        "corrections_passed": all(
            row["feedback_passed"]
            and row["success_public"]
            and row["success_6_2"]
            and row["conformant"]
            and row["routes_refresh"]
            for row in corrections
        ),
        "saturated": len(base244.remaining_epoch(repeated)) == 0
        and repeated["active_opportunity_projection"]["opportunity_count"] == 0,
        "sixth_wait": not reused
        and repeated_reused
        and len(repeated["world_stream_wait_receipts"]) == 6
        and len(repeated["world_stream_wait_discharge_receipts"]) == 5,
        "exact_reobserve": repeated["artifact_digest"] == waiting["artifact_digest"],
        "renewal_derived": base279.derive(repeated, [], p82)
        == "renew-world-feed",
        "provider_example_visible": example_evaluation["valid"]
        and example_scan["status"] == "world-available",
        "renewal_preserved": repeated["active_standing_world_renewal"]
        == parent["active_standing_world_renewal"],
        "conformant": runtime.identity_conforms(repeated),
    }


def preflight(root, p82, runtime, parent, result281, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    first_corrected, first = correction_variant(
        parent, 0, package, result280, p82, runtime
    )
    first_refreshed = base264.refresh_projection_only(first_corrected, p82)
    remaining = [
        row["target_symbol"]
        for row in first_refreshed["active_opportunity_projection"]["opportunities"]
    ]
    branches = []
    for order in itertools.permutations(remaining):
        for depths in itertools.product(range(3), repeat=3):
            branches.append(
                prospective_branch(
                    root / ("-".join(order) + "-" + "".join(map(str, depths))),
                    parent,
                    order,
                    depths,
                    package,
                    result280,
                    p82,
                    runtime,
                )
            )
    route, identity = base272.base265.floors(parent)
    evaluation = base268.evaluate_package(package, p82.digest)
    script = Path(__file__).read_text()
    seed = base268.seed_actor(root / "provider-seed", base268.EXAMPLE)
    corpus = "\n".join(
        path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file()
    )
    seen = base279.seen_world_ids(parent)
    ledger = sorted(parent["local_frontier_ledger"]["targets"])
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_correction": parent["artifact_digest"] == PARENT_DIGEST
        and base272.derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0281_exact_promotion": result281["receipt_digest"] == OT281_RECEIPT
        and result281["observer_disposition"] == "promoted"
        and result281["final_subject_digest"] == PARENT_DIGEST,
        "ot0280_exact_package": result280["receipt_digest"] == OT280_RECEIPT
        and result280["full_package_digest"] == evaluation["full_package_digest"],
        "fifty_four_complete_branches": len(branches) == 54
        and len(remaining) == 2,
        "all_branches_pass": all(
            row["selections_passed"]
            and row["corrections_passed"]
            and row["saturated"]
            and row["sixth_wait"]
            and row["exact_reobserve"]
            and row["renewal_derived"]
            and row["provider_example_visible"]
            and row["renewal_preserved"]
            and row["conformant"]
            for row in branches
        ),
        "dynamic_surfaces_not_hardcoded": all(
            token not in script
            for target, path in evaluation["targets"].items()
            for token in (target, path)
        ),
        "provider_seed_excludes_lineage": PARENT_DIGEST not in corpus
        and all(world_id not in corpus for world_id in seen)
        and all(target not in corpus for target in ledger),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "branch_count": len(branches),
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def derived_operation(subject, results, p82):
    operation = base272.derive(subject, p82)
    if (
        operation == "wait-provider"
        and results
        and results[-1]["transition"] == "wait-provider"
        and results[-1]["checks"].get("wait_exact_noop") is True
    ):
        return base279.derive(subject, [], p82)
    return operation


def run_provider(context, p82, root, subject):
    label = "standing-world-renewal-scout"
    seed = base268.seed_actor(root / "actor", base268.TEMPLATE)
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, base268.SCHEMA, (seed / "README.md").read_text().strip()
    )
    try:
        package = json.loads((workspace / "world-package.json").read_text())
        evaluation = base268.evaluate_package(package, p82.digest)
        checker = subprocess.run(
            ["python3", "check_package.py"], cwd=workspace, capture_output=True
        )
        public = evaluation.get("public_package") if evaluation["valid"] else None
        scan = base267.scan_feed(subject, [public], p82.digest) if public else None
        target_collision = bool(
            evaluation["valid"]
            and set(evaluation["targets"])
            & set(subject["local_frontier_ledger"]["targets"])
        )
        world_collision = bool(
            package.get("world_id") in set(base279.seen_world_ids(subject))
        )
        semantic = bool(
            checker.returncode == 0
            and evaluation["valid"]
            and scan
            and scan["status"] == "world-available"
            and not target_collision
            and not world_collision
        )
    except (OSError, json.JSONDecodeError, KeyError):
        package, evaluation, scan, target_collision, world_collision, semantic = (
            None,
            {"valid": False},
            None,
            True,
            True,
            False,
        )
    transport = base268.output_valid(output, package)
    audit = context.audit_actor(
        label, output, base_audit, semantic and transport, ["world-package.json"]
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(semantic and transport and base236.g10(normalized))
    return {
        "accepted": accepted,
        "output": output,
        "audit": audit,
        "g10_disposition": base236.g10(normalized),
        "evaluation": evaluation,
        "scanner_observation": scan,
        "target_collision": target_collision,
        "world_collision": world_collision,
        "package": package,
    }


def valid_operation_shape(operations, transitions):
    index = 0
    for group in range(3):
        count = 0
        while index < len(operations) and operations[index] == "outward-correct":
            count += 1
            index += 1
        if not 1 <= count <= 3:
            return False
        if transitions[: count - 1] != ["unresolved-to-more-correction"] * (count - 1):
            return False
        if transitions[count - 1 : count] != ["success-to-refresh"]:
            return False
        transitions = transitions[count:]
        if index >= len(operations) or operations[index] != "refresh-opportunity-projection":
            return False
        index += 1
        if group < 2:
            if index >= len(operations) or operations[index] != "expanded-select":
                return False
            index += 1
    return operations[index:] == [
        "expand-environment",
        "wait-provider",
        "renew-world-feed",
    ] and not transitions


def finalize(run, fixtures, p82, runtime, parent, final):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    operations = [row["pulse"]["derived_operation"] for row in rows]
    corrections = [row for row in rows if row["pulse"]["derived_operation"] == "outward-correct"]
    provider = rows[-1]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "bounded_content_free_cycle": len(rows) <= MAX_CALLS
        and all(row["pulse"]["content"] is None and row["checks"]["passed"] for row in rows),
        "world_routed_operation_shape": valid_operation_shape(
            operations, [row["transition"] for row in corrections]
        ),
        "two_selections": operations.count("expanded-select") == 2,
        "actor_count_matches": sum(row["fresh_actor_count"] for row in rows)
        == 3 + len(corrections),
        "morrowglass_saturated": len(base244.remaining_epoch(final)) == 0
        and final["active_opportunity_projection"]["opportunity_count"] == 0,
        "sixth_wait_exact": len(final["world_stream_wait_receipts"]) == 6
        and len(final["world_stream_wait_discharge_receipts"]) == 5
        and base272.derive(final, p82) == "wait-provider",
        "renewal_provider_promoted": provider["transition"] == "renew-world-feed"
        and provider["actor"]["accepted"]
        and provider["checks"]["next_world_available"],
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    gates["passed"] = all(gates.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [row["receipt_digest"] for row in rows],
        "checks": gates,
        "operations": operations,
        "correction_transitions": [row["transition"] for row in corrections],
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": sum(row["fresh_actor_count"] for row in rows),
        "next_world_id": provider["actor"]["package"].get("world_id"),
        "next_world_full_package_digest": provider["actor"]["evaluation"].get(
            "full_package_digest"
        ),
        "next_world_public_package_digest": provider["actor"]["evaluation"].get(
            "public_package_digest"
        ),
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    write_json(run / "next-world-package.json", provider["actor"]["package"])
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def advance(repo, run, p82, runtime, parent, package, result280, fixtures, core, base130):
    result_paths = sorted(run.glob("invocation-*-result.json"))
    results = [json.loads(path.read_text()) for path in result_paths]
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0282 invocation")
    if (run / "aggregate.json").exists() or not fixtures["checks"]["passed"]:
        raise SystemExit("OT-0282 unavailable")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index > MAX_CALLS or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0282 checkpoint")
    operation = derived_operation(subject, results, p82)
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = feedback = None
    final = subject
    transition = operation
    checks = {"content_free": True}
    if operation == "refresh-opportunity-projection":
        final = base264.refresh_projection_only(subject, p82)
        checks.update(
            zero_fresh_actors=True,
            projection_fresh=not base260.needs_refresh(final, p82),
            next_derived=base272.derive(final, p82)
            in {"expanded-select", "expand-environment"},
        )
    elif operation == "expanded-select":
        actor, world, final = base272.live_selection(
            base274.context_for(core, base130, runtime, root, repo),
            p82,
            root,
            subject,
            package,
            result280,
        )
        checks.update(
            actor_accepted=actor["accepted"],
            g10_accepted=actor["g10_disposition"],
            retained_package_2_of_6=bool(
                world
                and world["result"]["matches"] == 2
                and world["ot0268_aggregate_receipt_digest"] == OT280_RECEIPT
            ),
            next_is_correction=base272.derive(final, p82) == "outward-correct",
        )
    elif operation == "outward-correct":
        mode, actor, world, feedback, final, transition = base274.run_correction(
            base274.context_for(core, base130, runtime, root, repo),
            p82,
            root,
            subject,
            package,
            result280,
        )
        public_count = actor["public"]["case_count"] if actor and actor.get("public") else 0
        checks.update(
            actor_accepted=actor["accepted"],
            g10_accepted=actor["g10_disposition"],
            disclosed_all_pass=bool(
                actor["public"] and actor["public"]["matches"] == public_count
            ),
            unchanged_2_of_6=bool(
                world and world["unchanged_control"]["matches"] == 2
            ),
            consequence_routes=transition
            in {"success-to-refresh", "unresolved-to-more-correction"},
            next_matches_consequence=base272.derive(final, p82)
            == (
                "refresh-opportunity-projection"
                if transition == "success-to-refresh"
                else "outward-correct"
            ),
        )
    elif operation == "expand-environment":
        world = base272.empty_feed_observation(subject, p82)
        final, reused = base256.compile_wait(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            saturated=len(base244.remaining_epoch(subject)) == 0,
            sixth_wait_installed=not reused
            and len(final["world_stream_wait_receipts"]) == 6
            and len(final["world_stream_wait_discharge_receipts"]) == 5,
            next_is_wait=base272.derive(final, p82) == "wait-provider",
        )
    elif operation == "wait-provider":
        world = base272.empty_feed_observation(subject, p82)
        final, reused = base256.compile_wait(subject, world, p82)
        checks.update(
            zero_fresh_actors=True,
            wait_exact_noop=reused and final["artifact_digest"] == subject["artifact_digest"],
            renewal_next=base279.derive(final, [], p82) == "renew-world-feed",
        )
    elif operation == "renew-world-feed":
        actor = run_provider(
            base274.context_for(core, base130, runtime, root, repo),
            p82,
            root,
            subject,
        )
        evaluation = actor["evaluation"]
        checks.update(
            actor_accepted=actor["accepted"],
            g10_accepted=actor["g10_disposition"],
            exact_one_file_effect=actor["audit"]["exact_changes"]
            and actor["audit"]["changed_paths"] == ["world-package.json"],
            three_novel_targets=bool(
                evaluation.get("valid")
                and len(evaluation["targets"]) == 3
                and not actor["target_collision"]
                and not actor["world_collision"]
            ),
            all_three_exact_2_of_6=bool(
                evaluation.get("valid")
                and all(
                    sum(row["matches"] for row in rows) == 2
                    for rows in evaluation["rows"].values()
                )
            ),
            next_world_available=bool(
                actor["scanner_observation"]
                and actor["scanner_observation"]["status"] == "world-available"
            ),
            subject_exact_during_provision=final["artifact_digest"]
            == subject["artifact_digest"],
        )
    else:
        checks["known_operation"] = False
    checks["final_open_conformant"] = final["continuation"]["status"] == "open"
    checks["identity_conformant"] = runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    public_actor = copy.deepcopy(actor)
    if operation == "renew-world-feed" and public_actor:
        package_value = public_actor.pop("package")
        write_json(root / "world-package.json", package_value)
        public_actor["package"] = package_value
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": transition,
        "actor": public_actor,
        "world": world,
        "feedback": feedback,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1 if actor else 0,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if operation != "renew-world-feed":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return finalize(run, fixtures, p82, runtime, parent, final)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result281, package, result280, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(
            run / "preflight",
            p82,
            runtime,
            parent,
            result281,
            package,
            result280,
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return advance(
        repo,
        run,
        p82,
        runtime,
        parent,
        package,
        result280,
        fixtures,
        core,
        base130,
    )


if __name__ == "__main__":
    raise SystemExit(main())
