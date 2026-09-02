from __future__ import annotations

import argparse
import json
from pathlib import Path

import ot_0248_descriptor_neutral_second_epoch_driver as frozen


def read_json(path: Path):
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=frozen.REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0248").resolve()
    aggregate_path = run / "aggregate.json"
    subject_path = run / "final-full-subject.json"
    if aggregate_path.exists() or subject_path.exists():
        raise SystemExit("preserve existing OT-0248 reconstruction")

    lineage = frozen.authority_base.guide_base.load_base()
    selector_base, base = lineage.selector_base, lineage.base
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0247",
        "open-subject-at-cross-epoch-contradiction.json",
    )
    fixture = read_json(run / "fixture-conformance.json")
    transitions = [
        read_json(run / f"pulse-{index}" / "transition.json")
        for index in range(1, 8)
    ]
    expected = [
        "outward-correct",
        "expanded-select",
        "outward-correct",
        "expanded-select",
        "outward-correct",
        "expanded-select",
        "outward-correct",
    ]
    actual = [row["operation"] for row in transitions]
    rejected_without_change = all(
        row["source_subject_digest"] == frozen.PARENT_DIGEST
        and row["final_subject_digest"] == frozen.PARENT_DIGEST
        and row["actor"] is not None
        and not row["actor"]["accepted"]
        and row["world"] is None
        for row in transitions
    )
    fixed_path_audit_fault = all(
        row["actor"]["audit"]["expected_changes"] == ["correction-decision.json"]
        and "resilience/evacuation.py" in row["actor"]["audit"]["changed_paths"]
        and row["actor"]["decision"] is None
        for row in transitions
    )
    checks = {
        "preflight_passed": fixture["checks"]["passed"],
        "seven_identical_null_pulses": len(transitions) == 7
        and all(row["pulse"]["content"] is None for row in transitions),
        "derived_sequence": actual == expected,
        "seven_fresh_actors": sum(row["fresh_actor_count"] for row in transitions)
        == 7,
        "all_g10_accepted": all(
            row["actor"] and row["actor"]["g10_disposition"]
            for row in transitions
        ),
        "no_transition_admitted": rejected_without_change,
        "repeated_fixed_path_audit_fault": fixed_path_audit_fault,
        "parent_remains_exact_and_open": parent["artifact_digest"]
        == frozen.PARENT_DIGEST
        and parent["continuation"]["status"] == "open",
    }
    result = {
        "authority": frozen.AUTHORITY + "-reconstructed-rejection",
        "source_subject_digest": parent["artifact_digest"],
        "transitions": transitions,
        "observed_operations": actual,
        "expected_operations": expected,
        "checks": checks,
        "observer_disposition": "rejected",
        "subject_disposition": parent["continuation"]["status"],
        "final_subject_digest": parent["artifact_digest"],
        "fresh_actor_count": sum(row["fresh_actor_count"] for row in transitions),
        "reconstruction": {
            "reason": "The frozen reporter assumed an accepted selection after seven rejected correction transitions and raised TypeError.",
            "causal_observation": "The descriptor adapter retained a fixed landscape package initializer in the mutation audit. In the resilience epoch that immutable path was absent, so every otherwise completed correction was rejected before binding and the lineage did not advance.",
            "actor_resampling": False,
        },
    }
    result["receipt_digest"] = p82.digest(result)
    frozen.write_json(aggregate_path, result)
    frozen.write_json(subject_path, parent)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
