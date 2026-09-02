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
BASE_PATH = ROOT / "ot_0294_shared_live_isolation_authority.py"
BASE_SHA256 = "4b904b79d159bbcc1b7a5a15e78a0adf7e57c76f26100d91414c4099078911cc"
PARENT_DIGEST = "e09f4f71670bae501656c7c99ec140980a43a1675e68e56b83461f13c2145aa1"
OT294_RECEIPT = "0ec1eb954c5ecf817c725c3b9b29987ecc18a93efe8f4e345e2b2f029d783a30"
AUTHORITY = "ot-0295-recovered-world-target-correction"
MAX_CALLS = 3


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0294 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0295_frozen_ot0294", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base294 = load_base()
base291 = base294.base291
b = base294.b
base291.AUTHORITY = AUTHORITY
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY
b.base274.MAX_CALLS = MAX_CALLS


def write_json(path, value):
    base291.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0295").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0294", "open-subject-after-recovered-world-selection.json"
    )
    result294 = selector.load_artifact(
        p82, repo, store, "OT-0294", "shared-live-isolation-authority-aggregate.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0290", "tideglass-crossings-world-package.json"
    )
    result280 = selector.load_artifact(
        p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result294, package, result280, core, base130


def undisclosed(subject, package, p82):
    return base294.base293.base292.base291.base290.base289.target_scoped_undisclosed(
        subject, package, p82
    )


def lineage_projection(subject):
    return {
        "scars": subject.get("invalid_encounter_scars"),
        "recoveries": subject.get("invalid_encounter_recovery_receipts"),
        "policy": subject.get("active_invalid_encounter_reopening_policy"),
    }


def preflight(root, p82, runtime, parent, result294, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    selected = b.base274.selected(parent)
    target = selected[4]
    disclosure = parent.get("active_correction_disclosure") or {}
    available = undisclosed(parent, package, p82)
    branches = []
    for depth in range(len(available) + 1):
        final, row = b.correction_variant(
            parent, depth, package, result280, p82, runtime
        )
        branches.append(
            {
                **row,
                "lineage_exact": lineage_projection(final)
                == lineage_projection(parent),
                "selected_verified": final["local_frontier_ledger"]["targets"][target][
                    "status"
                ]
                == "verified-local",
            }
        )
    exhausted, _ = b.correction_variant(
        parent, len(available), package, result280, p82, runtime
    )
    exhausted_fails = False
    try:
        b.correction_variant(exhausted, 1, package, result280, p82, runtime)
    except (RuntimeError, TypeError, KeyError):
        exhausted_fails = True
    route, identity = b.base272.base265.floors(parent)
    script = Path(__file__).read_text()
    evaluation = b.base268.evaluate_package(package, p82.digest)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_selected_consequence": parent["artifact_digest"] == PARENT_DIGEST
        and b.base272.derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0294_exact_promotion": result294["receipt_digest"] == OT294_RECEIPT
        and result294["observer_disposition"] == "promoted"
        and result294["final_subject_digest"] == PARENT_DIGEST,
        "stale_disclosure_is_other_resolved_target": disclosure.get("target_symbol")
        != target
        and disclosure.get("status") == "resolved-after-revision"
        and not b.base274.feedback_mode(parent),
        "two_target_scoped_undisclosed_classes": len(available) == 2,
        "zero_one_two_feedback_paths": len(branches) == 3
        and all(
            row["feedback_passed"]
            and row["success_public"]
            and row["success_6_2"]
            and row["conformant"]
            and row["routes_refresh"]
            and row["lineage_exact"]
            and row["selected_verified"]
            for row in branches
        ),
        "exhausted_fails_closed": exhausted_fails,
        "dynamic_target_not_hardcoded": target not in script
        and selected[5] not in script
        and package["world_id"] not in script
        and target in evaluation["targets"],
        "shared_isolation_authority_retained": b.base281.base270.seed_excludes_sealed
        is base294.shared_current_package_public_only,
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "feedback_capacity": len(available),
        "branch_count": len(branches),
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def finalize(run, fixtures, p82, runtime, parent, final):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    transitions = [row["transition"] for row in rows]
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "bounded_content_free_correction": 1 <= len(rows) <= MAX_CALLS
        and all(
            row["pulse"]["content"] is None
            and row["pulse"]["derived_operation"] == "outward-correct"
            and row["checks"]["passed"]
            for row in rows
        ),
        "consequence_selected_depth": transitions[-1:] == ["success-to-refresh"]
        and transitions[:-1]
        == ["unresolved-to-more-correction"] * (len(transitions) - 1),
        "actor_count_matches": sum(row["fresh_actor_count"] for row in rows)
        == len(rows),
        "lineage_exact": lineage_projection(final) == lineage_projection(parent),
        "refresh_derived": b.base272.derive(final, p82)
        == "refresh-opportunity-projection",
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [row["receipt_digest"] for row in rows],
        "checks": checks,
        "correction_transitions": transitions,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": len(rows),
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result294, package, result280, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(run / "preflight", p82, runtime, parent, result294, package, result280)
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0295 unavailable")
    results = sorted(run.glob("invocation-*-result.json"))
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0295 invocation")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    operation = b.base272.derive(subject, p82)
    if index > MAX_CALLS or operation != "outward-correct" or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0295 checkpoint")
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    context = b.base274.context_for(core, base130, runtime, root, repo)
    _, actor, world, feedback, final, transition = b.base274.run_correction(
        context, p82, root, subject, package, result280
    )
    public_count = actor["public"]["case_count"] if actor and actor.get("public") else 0
    checks = {
        "content_free": True,
        "workspace_outside_repo": not (root / "actor").resolve().is_relative_to(repo),
        "actor_accepted": actor["accepted"],
        "g10_accepted": actor["g10_disposition"],
        "disclosed_all_pass": bool(
            actor["public"] and actor["public"]["matches"] == public_count
        ),
        "unchanged_2_of_6": bool(
            world and world["unchanged_control"]["matches"] == 2
        ),
        "consequence_routes": transition
        in {"success-to-refresh", "unresolved-to-more-correction"},
        "next_matches_consequence": b.base272.derive(final, p82)
        == (
            "refresh-opportunity-projection"
            if transition == "success-to-refresh"
            else "outward-correct"
        ),
        "lineage_exact": lineage_projection(final) == lineage_projection(parent),
        "final_open_conformant": final["continuation"]["status"] == "open",
        "identity_conformant": runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": transition,
        "actor": copy.deepcopy(actor),
        "world": world,
        "feedback": feedback,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if transition == "unresolved-to-more-correction":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return finalize(run, fixtures, p82, runtime, parent, final)


if __name__ == "__main__":
    raise SystemExit(main())
