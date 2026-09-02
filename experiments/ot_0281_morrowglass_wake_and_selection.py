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
BASE_PATH = ROOT / "ot_0280_import_stable_world_evaluator.py"
BASE_SHA256 = "39728886eab7754d0f8febb412b9a93fb2aa6a03f3434dc712e1701a39915913"
PARENT_DIGEST = "cfab2a5071046cced4e48e732c4735461ebc7a2149c82e25331ca3d608127e51"
OT280_RECEIPT = "15d39db31b2031e2dd3e0c1f1917e4b4125ce2924cc3fcffc3f62710980d847c"
AUTHORITY = "ot-0281-morrowglass-wake-and-selection"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0280 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0281_frozen_ot0280", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base280 = load_base()
base279 = base280.base279
base278 = base279.base278
base272 = base278.base272
base270 = base272.base270
base268 = base280.base268
base244 = base278.base244
authority_base = base280.authority_base
base270.OT268_RECEIPT = OT280_RECEIPT
base272.OT268_RECEIPT = OT280_RECEIPT


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0281").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0280", "open-subject-at-renewed-fifth-wait.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0280", "independent-morrowglass-world-package.json"
    )
    result280 = selector.load_artifact(
        p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json"
    )
    return repo, run, p82, runtime, parent, package, result280, core, base130


def wake(subject, package, p82):
    observation = base270.scan(subject, package, p82)
    final, reused = base270.compile_offer(subject, observation, p82)
    return observation, final, reused


def with_evaluator(function, *args):
    return base280.with_corrected_evaluator(function, *args)


def preflight(root, p82, runtime, parent, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    legacy = base268.evaluate_package(package, p82.digest)
    corrected = with_evaluator(base268.evaluate_package, package, p82.digest)
    observation, offered, reused = wake(parent, package, p82)
    targets = sorted(corrected["targets"])
    branches = [
        with_evaluator(
            base270.prospective_path,
            root / f"offer-selection-{index}",
            offered,
            package,
            corrected,
            result280,
            target,
            p82,
            runtime,
        )
        for index, target in enumerate(targets)
    ]
    route, identity = base272.base265.floors(offered)
    script = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_renewed_wait": parent["artifact_digest"] == PARENT_DIGEST
        and base272.derive(parent, p82) == "wait-provider"
        and base279.derive(parent, [], p82) == "renew-world-feed"
        and runtime.identity_conforms(parent),
        "ot0280_exact_promotion": result280["receipt_digest"] == OT280_RECEIPT
        and result280["observer_disposition"] == "promoted"
        and result280["final_subject_digest"] == PARENT_DIGEST,
        "evaluator_boundary_exact": legacy
        == {"valid": False, "reason": "execution"}
        and corrected == result280["corrected_evaluation"],
        "wake_exact": observation["status"] == "world-available"
        and observation["available_world"]["world_id"] == package["world_id"]
        and not reused
        and offered["active_world_stream_wait"] is None
        and len(offered["world_stream_wait_receipts"]) == 5
        and len(offered["world_stream_wait_discharge_receipts"]) == 5
        and offered["active_standing_world_renewal"]
        == parent["active_standing_world_renewal"]
        and base270.derive(offered, p82) == "expand-environment"
        and runtime.identity_conforms(offered),
        "wake_preserves_preselection_state": offered["local_frontier_ledger"]
        == parent["local_frontier_ledger"]
        and offered["actor_authored_environment_epochs"]
        == parent["actor_authored_environment_epochs"],
        "three_complete_choice_branches": len(branches) == 3
        and all(
            branch["checker"]
            and branch["semantic"]
            and branch["public"]
            and branch["sealed_matches"] == 2
            and branch["world_outcome"] == "unresolved"
            and branch["routes_correction"]
            and branch["intermediate_conformant"]
            and branch["final_conformant"]
            for branch in branches
        ),
        "dynamic_targets_not_hardcoded": all(
            target not in script and path not in script
            for target, path in corrected["targets"].items()
        ),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "choice_count": len(branches),
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result, offered


def finalize_aggregate(run, fixtures, p82, runtime, parent, package, final):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    actor = rows[-1]["actor"] if rows else None
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "two_content_free_openings": len(rows) == 2
        and all(row["pulse"]["content"] is None for row in rows),
        "wake_then_selection": [row["transition"] for row in rows]
        == ["wake-world", "expanded-select"],
        "one_fresh_subject_actor": sum(row["fresh_actor_count"] for row in rows)
        == 1,
        "all_invocations_passed": all(row["checks"]["passed"] for row in rows),
        "morrowglass_epoch_live": final["actor_authored_environment_epochs"][-1][
            "environment_id"
        ]
        == package["world_id"]
        and len(base244.remaining_epoch(final)) == 2
        and base270.derive(final, p82) == "outward-correct",
        "renewal_preserved": final["active_standing_world_renewal"]
        == parent["active_standing_world_renewal"],
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    gates["passed"] = all(gates.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [row["receipt_digest"] for row in rows],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
        "selected_target": actor["output"].get("selected_target") if actor else None,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, package, result280, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    if retained.exists():
        fixtures = json.loads(retained.read_text())
    else:
        fixtures, _ = preflight(
            run / "preflight", p82, runtime, parent, package, result280
        )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0281 unavailable")
    results = sorted(run.glob("invocation-*-result.json"))
    checkpoint = run / "checkpoint-subject.json"
    if len(results) == 2 and checkpoint.exists():
        retained_final = json.loads(checkpoint.read_text())
        return finalize_aggregate(
            run, fixtures, p82, runtime, parent, package, retained_final
        )
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index not in {1, 2} or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0281 checkpoint")
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    operation = "wake-world" if index == 1 else base270.derive(subject, p82)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = None
    if index == 1:
        world, final, reused = wake(subject, package, p82)
        checks = {
            "content_free": True,
            "zero_fresh_actors": True,
            "scanner_found_only_world": world["status"] == "world-available"
            and len(world["catalog"]) == 1
            and world["available_world"]["world_id"] == package["world_id"],
            "fifth_wait_discharged": not reused
            and final["active_world_stream_wait"] is None
            and len(final["world_stream_wait_discharge_receipts"]) == 5,
            "renewal_preserved": final["active_standing_world_renewal"]
            == parent["active_standing_world_renewal"],
            "next_is_expansion": base270.derive(final, p82)
            == "expand-environment",
            "final_open_conformant": final["continuation"]["status"] == "open"
            and runtime.identity_conforms(final),
        }
        transition = "wake-world"
    else:
        context = base278.base274.context_for(core, base130, runtime, root, repo)
        actor = base270.run_actor(context, p82, root / "actor", subject)
        intermediate = (
            base270.compile_intermediate(subject, actor, pulse, p82)
            if actor["accepted"]
            else subject
        )
        world = (
            with_evaluator(
                base270.sealed_world,
                intermediate,
                actor,
                package,
                result280,
                p82,
            )
            if actor["accepted"]
            else None
        )
        final = (
            base270.compile_world(intermediate, world, p82)
            if world
            else intermediate
        )
        selected = actor.get("decision", {}).get("next_contact")
        checks = {
            "content_free": True,
            "actor_accepted": actor["accepted"],
            "g10_accepted": actor["g10_disposition"],
            "public_executable": bool(actor["public"] and actor["public"]["all_valid"]),
            "selected_offered_target": bool(
                selected
                and (selected["target_path"], selected["target_symbol"])
                in base270.offered_pairs(subject)
            ),
            "workspace_public_only": base270.seed_excludes_sealed(
                root / "actor" / "seed", package, result280
            ),
            "retained_package_2_of_6": bool(
                world
                and world["result"]["matches"] == 2
                and world["ot0268_aggregate_receipt_digest"] == OT280_RECEIPT
            ),
            "offer_consumed_new_epoch": final.get("active_streamed_world_offer") is None
            and len(final["actor_authored_environment_epochs"])
            == len(parent["actor_authored_environment_epochs"]) + 1,
            "renewal_preserved": final["active_standing_world_renewal"]
            == parent["active_standing_world_renewal"],
            "next_is_correction": base270.derive(final, p82) == "outward-correct",
            "final_open_conformant": final["continuation"]["status"] == "open"
            and runtime.identity_conforms(final),
        }
        transition = "expanded-select"
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": transition,
        "actor": actor,
        "world": world,
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
    if index == 1:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return finalize_aggregate(run, fixtures, p82, runtime, parent, package, final)


if __name__ == "__main__":
    raise SystemExit(main())
