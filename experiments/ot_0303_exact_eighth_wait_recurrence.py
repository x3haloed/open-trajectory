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
BASE_PATH = ROOT / "ot_0302_surrender_recovery_correction.py"
BASE_SHA256 = "e406ccce3a93d5d866f400c7949152ff71ece50b1256516f9a806dd698dd1469"
PARENT_DIGEST = "140e793e1382eafdf46c2a9e76fab9252659d87be35b10b8fe9aadd74d2d8beb"
OT302_RECEIPT = "29fd8f1a6cfdccc304354e92c71347b3f1e4a9707ca5493b89a6935949efcd17"
AUTHORITY = "ot-0303-exact-eighth-wait-recurrence"
MAX_CALLS = 3


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0302 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0303_frozen_ot0302", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base302 = load_base()
b = base302.b
base297 = base302.base297
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def write_json(path, value):
    base302.write_json(path, value)


def preserved(subject):
    return {
        "lineage": base302.lineage(subject),
        "surrender_feedback": subject.get("retained_surrender_feedback"),
        "invalidity_scars": subject.get("invalid_encounter_scars"),
        "invalidity_recoveries": subject.get("invalid_encounter_recovery_receipts"),
    }


def setup(args):
    chain = b.authority_base.guide_base.load_base()
    selector, core = chain.selector_base, chain.base
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0303").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0302", "open-subject-after-surrender-recovery.json"
    )
    result302 = selector.load_artifact(
        p82, repo, store, "OT-0302", "surrender-recovery-correction-aggregate.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0290", "tideglass-crossings-world-package.json"
    )
    return repo, run, p82, runtime, parent, result302, package


def suffix(parent, p82):
    refreshed = b.base264.refresh_projection_only(parent, p82)
    first_observation = b.base272.empty_feed_observation(refreshed, p82)
    waiting, first_reused = b.base256.compile_wait(refreshed, first_observation, p82)
    second_observation = b.base272.empty_feed_observation(waiting, p82)
    repeated, second_reused = b.base256.compile_wait(waiting, second_observation, p82)
    return refreshed, waiting, repeated, first_reused, second_reused


def preflight(root, p82, runtime, parent, result302, package):
    root.mkdir(parents=True, exist_ok=True)
    refreshed, waiting, repeated, first_reused, second_reused = suffix(parent, p82)
    altered = copy.deepcopy(parent)
    altered.pop("artifact_digest", None)
    altered["continuation"] = {**altered["continuation"], "status": "closed"}
    altered = p82.seal(altered)
    controls = {
        "wrong-parent-rejected": altered["artifact_digest"] != PARENT_DIGEST,
        "refresh-is-causal-change": refreshed["artifact_digest"]
        != parent["artifact_digest"],
        "first-wait-is-new": not first_reused,
        "second-wait-is-reuse": second_reused,
        "second-wait-is-exact": repeated["artifact_digest"]
        == waiting["artifact_digest"],
    }
    route, identity = b.base272.base265.floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_recovered_refresh": parent["artifact_digest"] == PARENT_DIGEST
        and result302["receipt_digest"] == OT302_RECEIPT
        and result302["observer_disposition"] == "promoted"
        and result302["final_subject_digest"] == PARENT_DIGEST
        and b.base272.derive(parent, p82) == "refresh-opportunity-projection"
        and len(base297.earned_targets(parent, package)) == 3
        and runtime.identity_conforms(parent),
        "refresh_saturates": refreshed["active_opportunity_projection"][
            "opportunity_count"
        ]
        == 0
        and len(b.base244.remaining_epoch(refreshed)) == 0
        and b.base272.derive(refreshed, p82) == "expand-environment",
        "eighth_wait_installed": len(waiting["world_stream_wait_receipts"]) == 8
        and len(waiting["world_stream_wait_discharge_receipts"]) == 7
        and b.base272.derive(waiting, p82) == "wait-provider",
        "exact_reobservation": repeated["artifact_digest"]
        == waiting["artifact_digest"],
        "renewal_derived": b.base279.derive(repeated, [], p82)
        == "renew-world-feed",
        "state_preserved": preserved(repeated) == preserved(parent)
        and len(base297.earned_targets(repeated, package)) == 3,
        "five_controls_pass": all(controls.values()),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
        "final_open_conformant": repeated["continuation"]["status"] == "open"
        and runtime.identity_conforms(repeated),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "controls": controls,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def finalize(run, fixtures, p82, runtime, parent, package, final):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    operations = [row["pulse"]["derived_operation"] for row in rows]
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "three_content_free_zero_actor_openings": len(rows) == MAX_CALLS
        and all(
            row["pulse"]["content"] is None
            and row["fresh_actor_count"] == 0
            and row["checks"]["passed"]
            for row in rows
        ),
        "exact_operation_sequence": operations
        == ["refresh-opportunity-projection", "expand-environment", "wait-provider"],
        "all_three_earned": len(base297.earned_targets(final, package)) == 3,
        "eighth_wait_exact": len(final["world_stream_wait_receipts"]) == 8
        and len(final["world_stream_wait_discharge_receipts"]) == 7,
        "renewal_derived": b.base279.derive(final, [], p82) == "renew-world-feed",
        "state_preserved": preserved(final) == preserved(parent),
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [row["receipt_digest"] for row in rows],
        "operations": operations,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 0,
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
    repo, run, p82, runtime, parent, result302, package = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(run / "preflight", p82, runtime, parent, result302, package)
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0303 unavailable")
    results = sorted(run.glob("invocation-*-result.json"))
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0303 invocation")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index > MAX_CALLS or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0303 checkpoint")
    operation = b.base272.derive(subject, p82)
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    world = None
    reused = None
    checks = {"content_free": True, "zero_fresh_actors": True}
    if operation == "refresh-opportunity-projection":
        final = b.base264.refresh_projection_only(subject, p82)
        checks.update(
            projection_empty=final["active_opportunity_projection"][
                "opportunity_count"
            ]
            == 0,
            saturated=len(b.base244.remaining_epoch(final)) == 0,
            next_is_expand=b.base272.derive(final, p82) == "expand-environment",
        )
    elif operation == "expand-environment":
        world = b.base272.empty_feed_observation(subject, p82)
        final, reused = b.base256.compile_wait(subject, world, p82)
        checks.update(
            new_wait=not reused,
            eighth_wait=len(final["world_stream_wait_receipts"]) == 8
            and len(final["world_stream_wait_discharge_receipts"]) == 7,
            next_is_wait=b.base272.derive(final, p82) == "wait-provider",
        )
    elif operation == "wait-provider":
        world = b.base272.empty_feed_observation(subject, p82)
        final, reused = b.base256.compile_wait(subject, world, p82)
        checks.update(
            exact_reobservation=reused
            and final["artifact_digest"] == subject["artifact_digest"],
            renewal_next=b.base279.derive(final, [], p82) == "renew-world-feed",
        )
    else:
        final = subject
        checks["known_operation"] = False
    checks.update(
        state_preserved=preserved(final) == preserved(parent),
        final_open_conformant=final["continuation"]["status"] == "open",
        identity_conformant=runtime.identity_conforms(final),
    )
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "world": world,
        "wait_reused": reused,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if operation != "wait-provider":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return finalize(run, fixtures, p82, runtime, parent, package, final)


if __name__ == "__main__":
    raise SystemExit(main())
