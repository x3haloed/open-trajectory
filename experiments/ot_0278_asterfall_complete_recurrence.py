from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0274_world_routed_correction_recurrence.py"
BASE_SHA256 = "f179ead38f9e6cb831f2ece428db0752bec56d3d66176df7784352d33df1d2aa"
PARENT_DIGEST = "bbebeb5338b415f2ccc25c3152364417d214ee4b16ca0c9a92e24e942bf28fa9"
OT277_RECEIPT = "702f9fed8c9744f5aba74f9084612a4cdade355fe31439f24f7f33d94edb9a12"
OT275_RECEIPT = "fdee3f2f1b3152bbafe25341317658d25ce5812d0d2bb6436d5e5170c1ede265"
AUTHORITY = "ot-0278-asterfall-complete-recurrence"
MAX_CALLS = 16


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0274 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0278_frozen_ot0274", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base274 = load_base()
base274.AUTHORITY = AUTHORITY
base274.OT268_RECEIPT = OT275_RECEIPT
base274.MAX_CALLS = MAX_CALLS
base273 = base274.base273
base272 = base274.base272
base271 = base274.base271
base268 = base274.base268
base264 = base274.base264
base244 = base274.base244
base256 = base274.base256
authority_base = base274.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0278").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0277", "open-subject-at-asterfall-contradiction.json"
    )
    result277 = selector.load_artifact(
        p82, repo, store, "OT-0277", "asterfall-subject-selection-aggregate.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0275", "independent-asterfall-world-package.json"
    )
    result275 = selector.load_artifact(
        p82, repo, store, "OT-0275", "post-mechanism-independent-world-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result277, package, result275, core, base130


def correction_variant(subject, failures, package, result275, p82, runtime):
    reference = package["sealed_reference_sources"][base274.selected(subject)[5]]
    feedback = []
    for offset in range(failures):
        examples = base274.all_examples(subject, package, p82)
        source = base274.sabotage(reference, examples[4 + offset]["input"])
        actor = base274.fixture_action(subject, source, p82)
        public_cases = (
            subject["active_correction_disclosure"]["cases"]
            if base274.feedback_mode(subject)
            else examples[:4]
        )
        public = base271.compare_source(source, base274.selected(subject)[4], public_cases)
        world = base271.sealed_followup(subject, actor, package, result275, p82)
        subject, receipt = base274.compile_unresolved_feedback(
            subject, actor, world, package, p82
        )
        feedback.append(
            public["matches"] == len(public_cases)
            and world["result"]["matches"] < 6
            and runtime.identity_conforms(subject)
            and receipt["counterexample_selection"]
            == "lowest-canonical-undisclosed-mismatch"
        )
    actor = base274.fixture_action(subject, reference, p82)
    public_cases = (
        subject["active_correction_disclosure"]["cases"]
        if base274.feedback_mode(subject)
        else base274.all_examples(subject, package, p82)[:4]
    )
    public = base271.compare_source(reference, base274.selected(subject)[4], public_cases)
    world = base271.sealed_followup(subject, actor, package, result275, p82)
    corrected = (
        base273.compile_success(subject, actor, world, p82)
        if base274.feedback_mode(subject)
        else base271.compile_correction(subject, actor, world, p82)
    )
    return corrected, {
        "failures": failures,
        "feedback_passed": all(feedback),
        "success_public": public["matches"] == len(public_cases),
        "success_6_2": world["result"]["matches"] == 6
        and world["unchanged_control"]["matches"] == 2,
        "conformant": runtime.identity_conforms(corrected),
        "routes_refresh": base272.derive(corrected, p82)
        == "refresh-opportunity-projection",
    }


def prospective_branch(root, parent, order, depths, package, result275, p82, runtime):
    subject, first = correction_variant(
        parent, depths[0], package, result275, p82, runtime
    )
    corrections = [first]
    subject = base264.refresh_projection_only(subject, p82)
    selections = []
    for index, target in enumerate(order):
        selection = base272.selection_fixture(
            root / f"selection-{index}",
            subject,
            package,
            result275,
            target,
            p82,
            runtime,
        )
        selections.append(
            selection["checker"]
            and selection["semantic"]
            and selection["world"]["result"]["matches"] == 2
            and selection["routes_correction"]
        )
        subject, correction = correction_variant(
            selection["final"], depths[index + 1], package, result275, p82, runtime
        )
        corrections.append(correction)
        subject = base264.refresh_projection_only(subject, p82)
    observation = base272.empty_feed_observation(subject, p82)
    waiting, reused = base256.compile_wait(subject, observation, p82)
    repeated_observation = base272.empty_feed_observation(waiting, p82)
    repeated, repeated_reused = base256.compile_wait(
        waiting, repeated_observation, p82
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
        "fifth_wait": not reused
        and repeated_reused
        and len(repeated["world_stream_wait_receipts"]) == 5
        and len(repeated["world_stream_wait_discharge_receipts"]) == 4,
        "exact_reobserve": repeated["artifact_digest"] == waiting["artifact_digest"],
        "conformant": runtime.identity_conforms(repeated),
    }


def preflight(root, p82, runtime, parent, result277, package, result275):
    root.mkdir(parents=True, exist_ok=True)
    first_corrected, first = correction_variant(parent, 0, package, result275, p82, runtime)
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
                    result275,
                    p82,
                    runtime,
                )
            )
    route, identity = base272.base265.floors(parent)
    evaluation = base268.evaluate_package(package, p82.digest)
    script = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_correction": parent["artifact_digest"] == PARENT_DIGEST
        and base272.derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0277_exact_promotion": result277["receipt_digest"] == OT277_RECEIPT
        and result277["observer_disposition"] == "promoted"
        and result277["final_subject_digest"] == PARENT_DIGEST,
        "ot0275_exact_package": result275["receipt_digest"] == OT275_RECEIPT
        and result275["full_package_digest"] == evaluation["full_package_digest"],
        "fifty_four_complete_branches": len(branches) == 54
        and len(remaining) == 2,
        "all_branches_pass": all(
            row["selections_passed"]
            and row["corrections_passed"]
            and row["saturated"]
            and row["fifth_wait"]
            and row["exact_reobserve"]
            and row["conformant"]
            for row in branches
        ),
        "dynamic_surfaces_not_hardcoded": all(
            token not in script
            for target, path in evaluation["targets"].items()
            for token in (target, path)
        ),
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
    return result, route, identity


def valid_operation_shape(operations, transitions):
    index = 0
    for group in range(3):
        count = 0
        while index < len(operations) and operations[index] == "outward-correct":
            count += 1
            index += 1
        if not 1 <= count <= 3:
            return False
        if transitions[: count - 1] != ["unresolved-to-more-correction"] * (count - 1) or transitions[count - 1 : count] != ["success-to-refresh"]:
            return False
        transitions = transitions[count:]
        if index >= len(operations) or operations[index] != "refresh-opportunity-projection":
            return False
        index += 1
        if group < 2:
            if index >= len(operations) or operations[index] != "expanded-select":
                return False
            index += 1
    return operations[index:] == ["expand-environment", "wait-provider"] and not transitions


def finalize_wait(run, p82, runtime, parent, fixtures):
    results = sorted(run.glob("invocation-*-result.json"))
    subject = json.loads((run / "checkpoint-subject.json").read_text())
    index = len(results) + 1
    world = base272.empty_feed_observation(subject, p82)
    final, reused = base256.compile_wait(subject, world, p82)
    checks = {
        "content_free": True,
        "zero_fresh_actors": True,
        "wait_exact_noop": reused and final["artifact_digest"] == subject["artifact_digest"],
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": "wait-provider",
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": "wait-provider",
        "actor": None,
        "world": world,
        "feedback": None,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    write_json(run / "checkpoint-subject.json", final)
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    operations = [row["pulse"]["derived_operation"] for row in rows]
    corrections = [row for row in rows if row["pulse"]["derived_operation"] == "outward-correct"]
    transitions = [row["transition"] for row in corrections]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "bounded_content_free_recurrence": len(rows) <= MAX_CALLS
        and all(row["pulse"]["content"] is None and row["checks"]["passed"] for row in rows),
        "world_routed_operation_shape": valid_operation_shape(operations, transitions),
        "two_selections": operations.count("expanded-select") == 2,
        "actor_count_matches": sum(row["fresh_actor_count"] for row in rows)
        == 2 + len(corrections),
        "asterfall_saturated": len(base244.remaining_epoch(final)) == 0
        and final["active_opportunity_projection"]["opportunity_count"] == 0,
        "fifth_wait_exact": len(final["world_stream_wait_receipts"]) == 5
        and len(final["world_stream_wait_discharge_receipts"]) == 4
        and base272.derive(final, p82) == "wait-provider",
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
        "correction_transitions": transitions,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": sum(row["fresh_actor_count"] for row in rows),
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
    repo, run, p82, runtime, parent, result277, package, result275, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    if retained.exists():
        fixtures = json.loads(retained.read_text())
        route, identity = base272.base265.floors(parent)
    else:
        fixtures, route, identity = preflight(
            run / "preflight", p82, runtime, parent, result277, package, result275
        )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0278 unavailable")
    checkpoint = run / "checkpoint-subject.json"
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    if base272.derive(subject, p82) == "wait-provider":
        return finalize_wait(run, p82, runtime, parent, fixtures)
    return base274.advance(
        repo,
        run,
        p82,
        runtime,
        parent,
        package,
        result275,
        fixtures,
        core,
        base130,
    )


if __name__ == "__main__":
    raise SystemExit(main())
