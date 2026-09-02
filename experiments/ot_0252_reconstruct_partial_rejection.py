from __future__ import annotations

import argparse
import json
from pathlib import Path

import ot_0252_symmetric_descriptor_complete_epoch_suffix as frozen


def read_json(path: Path):
    return json.loads(path.read_text())


def main():
    lineage = frozen.authority_base.guide_base.load_base()
    selector_base, base = lineage.selector_base, lineage.base
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=frozen.REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0252").resolve()
    aggregate_path = run / "aggregate.json"
    subject_path = run / "final-full-subject.json"
    if aggregate_path.exists() or subject_path.exists():
        raise SystemExit("preserve existing OT-0252 reconstruction")
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
    fixture = read_json(run / "fixture-conformance.json")
    transitions = [
        read_json(run / f"pulse-{index}" / "transition.json")
        for index in range(1, 6)
    ]
    subject = parent
    reconstructed = []
    for row in transitions:
        if row["operation"] == "expanded-select" and row["actor"]["accepted"]:
            intermediate = frozen.base245.compile_intermediate(
                subject, row["actor"], p82
            )
            subject = frozen.base245.compile_world(intermediate, row["world"], p82)
        elif row["operation"] == "outward-correct" and row["actor"]["accepted"]:
            subject = frozen.base248.compile_correction(
                subject, row["actor"], row["world"], p82
            )
        else:
            if row["final_subject_digest"] != subject["artifact_digest"]:
                raise RuntimeError("rejected transition changed exact subject")
        exact = subject["artifact_digest"] == row["final_subject_digest"]
        reconstructed.append(
            {
                "operation": row["operation"],
                "actor_accepted": row["actor"]["accepted"],
                "recorded_final_subject_digest": row["final_subject_digest"],
                "reconstructed_final_subject_digest": subject["artifact_digest"],
                "exact": exact,
            }
        )
        if not exact:
            raise RuntimeError("transition reconstruction mismatch")
    selections = [row for row in transitions if row["operation"] == "expanded-select"]
    corrections = [row for row in transitions if row["operation"] == "outward-correct"]
    accepted_selections = [row for row in selections if row["actor"]["accepted"]]
    accepted_corrections = [row for row in corrections if row["actor"]["accepted"]]
    rejected = transitions[-1]
    checks = {
        "preflight_passed": fixture["checks"]["passed"],
        "five_identical_null_pulses": len(transitions) == 5
        and all(row["pulse"]["content"] is None for row in transitions),
        "observed_prefix": [row["operation"] for row in transitions]
        == [
            "expanded-select",
            "outward-correct",
            "expanded-select",
            "outward-correct",
            "expanded-select",
        ],
        "four_transitions_admitted": all(
            row["actor"]["accepted"] and row["world"] for row in transitions[:4]
        ),
        "fifth_selection_rejected": not rejected["actor"]["accepted"]
        and rejected["world"] is None
        and rejected["actor"]["public"] is None
        and rejected["actor"]["audit"]["changed_paths"] == [],
        "two_selections_2_of_6": len(accepted_selections) == 2
        and all(row["world"]["result"]["matches"] == 2 for row in accepted_selections),
        "two_corrections_4_6_2": len(accepted_corrections) == 2
        and all(
            row["actor"]["public"]["matches"] == 4
            and row["world"]["result"]["matches"] == 6
            and row["world"]["unchanged_control"]["matches"] == 2
            for row in accepted_corrections
        ),
        "all_transition_digests_reconstruct": all(
            row["exact"] for row in reconstructed
        ),
        "one_opportunity_remains": len(frozen.base244.remaining_epoch(subject)) == 1,
        "next_operation_selection": frozen.base248.operation_for(subject)
        == "expanded-select",
        "partial_successor_open": subject["continuation"]["status"] == "open"
        and subject["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and runtime.identity_conforms(subject),
    }
    result = {
        "authority": frozen.AUTHORITY + "-reconstructed-partial-rejection",
        "source_subject_digest": parent["artifact_digest"],
        "transitions": transitions,
        "transition_reconstruction": reconstructed,
        "checks": checks,
        "observer_disposition": "rejected",
        "subject_disposition": subject["continuation"]["status"],
        "final_subject_digest": subject["artifact_digest"],
        "fresh_actor_count": sum(row["fresh_actor_count"] for row in transitions),
        "reconstruction": {
            "reason": "The frozen reporter dereferenced a null public result after the fifth selection actor was rejected.",
            "causal_observation": "Four transitions were admitted exactly. The fifth actor left the selection template unchanged and asserted that no eligible contact existed, so mechanical audit correctly rejected the non-move and the open subject retained one eligible surface.",
            "actor_resampling": False,
        },
    }
    result["receipt_digest"] = p82.digest(result)
    frozen.write_json(aggregate_path, result)
    frozen.write_json(subject_path, subject)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
