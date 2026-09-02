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
BASE_PATH = ROOT / "ot_0310_state_driven_multi_operation_continuation.py"
BASE_SHA256 = "df069b4382ce2bbef7d9bab3dd469b7a7da121fef7c69922d3ddbbe02464ca1e"
PARENT_DIGEST = "59a1f68c39d64a3b968d02fbdc8d3d8e1be82b581b69f8b235d59999d0ddfe3d"
OT310_RECEIPT = "ac4e911a51b9c45fd048aa483d7766804471ac3aa268f6ee7cbf84d56c37c221"
AUTHORITY = "ot-0311-remaining-catalog-priority-wake"
PROVIDER_COUNT = 4
REMAINING_COUNT = 3
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0310 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0311_frozen_ot0310", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base310 = load_base()
base309 = base310.base309
base307 = base310.base307
base305 = base307.base305
b = base310.b
base270 = b.base281.base270
base256 = b.base272.base256
PRIOR_DERIVE = base310.derive

base310.AUTHORITY = AUTHORITY
base309.AUTHORITY = AUTHORITY
base305.AUTHORITY = AUTHORITY
base270.AUTHORITY = AUTHORITY
base256.AUTHORITY = AUTHORITY


def write_json(path, value):
    base310.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core = lineage.selector_base, lineage.base
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0311").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0310",
        "open-subject-after-state-driven-continuation.json",
    )
    result310 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0310",
        "state-driven-multi-operation-aggregate.json",
    )
    result305 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0305",
        "subject-priority-world-selection-aggregate.json",
    )
    packages = [
        selector.load_artifact(
            p82,
            repo,
            store,
            "OT-0305",
            f"subject-blind-provider-{index:02d}-world-package.json",
        )
        for index in range(1, PROVIDER_COUNT + 1)
    ]
    return repo, run, p82, runtime, parent, result310, result305, packages


def active_stake_valid(subject, p82):
    binding = subject.get("active_world_seeking_stake") or {}
    body = {key: value for key, value in binding.items() if key != "binding_digest"}
    return bool(
        binding.get("binding_digest") == p82.digest(body)
        and base305.valid_stake(binding.get("stake"))
        and binding.get("future_world_identity_available") is False
        and binding.get("selection_authority") is True
        and binding.get("world_authority") is False
        and binding.get("scoring_authority") is False
        and binding.get("admission_authority") is False
        and binding.get("outcome_authority") is False
    )


def package_evaluation(package, p82):
    return b.base281.with_evaluator(b.base268.evaluate_package, package, p82.digest)


def seen_world_ids(subject):
    return set(b.base279.seen_world_ids(subject))


def remaining_packages(subject, packages):
    seen = seen_world_ids(subject)
    return sorted(
        (package for package in packages if package.get("world_id") not in seen),
        key=lambda package: package["world_id"],
    )


def descriptors_for(packages, p82):
    return [
        base305.descriptor(package, package_evaluation(package, p82))
        for package in packages
    ]


def install_wait(subject, p82):
    observation = b.base272.empty_feed_observation(subject, p82)
    waiting, reused = base256.compile_wait(subject, observation, p82)
    return observation, waiting, reused


def priority_body(subject, binding, selection, p82, consequence, next_operation):
    return {
        "authority": AUTHORITY + "-priority-contact",
        "source_subject_digest": subject["artifact_digest"],
        "stake_binding_digest": binding["binding_digest"],
        "catalog_digest": p82.digest(selection["rows"]),
        "selected_world_id": selection["selected_world_id"],
        "blind_control_world_id": selection["blind_world_id"],
        "score_gap": selection["score_gap"],
        "provider_consequence": consequence,
        "next_operation": next_operation,
        "selection_authority": "subject-stake",
        "world_authority": "independent-provider-catalog",
    }


def compile_supported(subject, binding, selection, package, p82):
    if not (
        active_stake_valid(subject, p82)
        and binding == subject["active_world_seeking_stake"]
        and selection.get("supported")
        and selection.get("selected_world_id") == package.get("world_id")
    ):
        raise RuntimeError("unsupported priority offer authority")
    observation, offered, reused = b.base281.wake(subject, package, p82)
    if reused or observation.get("status") != "world-available":
        raise RuntimeError("selected provider package did not discharge wait")
    body = priority_body(
        subject, binding, selection, p82, "support", "expanded-select"
    )
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(offered)
    child.pop("artifact_digest", None)
    child["subject_priority_contact_receipts"] = [
        *child.get("subject_priority_contact_receipts", []),
        receipt,
    ]
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": (
            "Select contact inside the independently supplied world chosen by "
            "the active world-seeking stake."
        ),
    }
    child["unresolved"] = binding["stake"]["question"]
    return observation, p82.seal(child), receipt


def compile_contradiction(subject, binding, selection, p82):
    if not (
        active_stake_valid(subject, p82)
        and binding == subject["active_world_seeking_stake"]
        and not selection.get("supported")
        and selection.get("selected_world_id") is None
    ):
        raise RuntimeError("invalid priority contradiction authority")
    body = priority_body(
        subject,
        binding,
        selection,
        p82,
        "contradiction",
        "revise-world-seeking-stake",
    )
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["subject_priority_contact_receipts"] = [
        *child.get("subject_priority_contact_receipts", []),
        receipt,
    ]
    child["active_world_seeking_stake_revision_due"] = receipt
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": (
            "Revise the active world-seeking stake after the remaining catalog "
            "failed its bound support condition."
        ),
    }
    child["unresolved"] = binding["stake"]["contradiction_condition"]
    return p82.seal(child), receipt


def derive(subject, p82):
    if isinstance(subject.get("active_world_seeking_stake_revision_due"), dict):
        return "revise-world-seeking-stake"
    return PRIOR_DERIVE(subject, p82)


b.base272.derive = derive


def fixture_binding(subject, stake, p82):
    body = {
        "authority": AUTHORITY + "-fixture-bound-world-seeking-stake",
        "source_subject_digest": subject["artifact_digest"],
        "actor_patch_digest": "0" * 64,
        "stake": stake,
        "future_world_identity_available": False,
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    return {**body, "binding_digest": p82.digest(body)}


def with_active_stake(subject, stake, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    binding = fixture_binding(subject, stake, p82)
    child["active_world_seeking_stake"] = binding
    return p82.seal(child), binding


def synthetic_supported_branch(waiting, p82, runtime):
    packages = base305.example_variants(b.base268)
    descriptors = descriptors_for(packages, p82)
    candidate = next(
        (stake, base305.choose(stake, descriptors))
        for feature in base305.FEATURES
        for stake in [base305.fixture_stake(feature)]
        if base305.choose(stake, descriptors)["supported"]
        and base305.choose(stake, descriptors)["selected_world_id"]
        != base305.choose(stake, descriptors)["blind_world_id"]
    )
    stake, selection = candidate
    fixture_subject, binding = with_active_stake(waiting, stake, p82)
    selected = next(
        package
        for package in packages
        if package["world_id"] == selection["selected_world_id"]
    )
    observation, final, receipt = compile_supported(
        fixture_subject, binding, selection, selected, p82
    )
    permutations = {
        base305.choose(stake, list(order))["selected_world_id"]
        for order in itertools.permutations(descriptors)
    }
    wrong_package_rejected = False
    wrong = next(
        package for package in packages if package["world_id"] != selected["world_id"]
    )
    try:
        compile_supported(fixture_subject, binding, selection, wrong, p82)
    except RuntimeError:
        wrong_package_rejected = True
    return {
        "supported": selection["supported"],
        "changes_blind_choice": selection["selected_world_id"]
        != selection["blind_world_id"],
        "permutation_invariant": permutations == {selection["selected_world_id"]},
        "wait_discharged": observation["status"] == "world-available"
        and final.get("active_world_stream_wait") is None,
        "offer_matches_selection": final["active_streamed_world_offer"]["world_id"]
        == selection["selected_world_id"],
        "receipt_exact": receipt["stake_binding_digest"]
        == binding["binding_digest"],
        "stake_not_duplicated": final.get("world_seeking_stakes")
        == fixture_subject.get("world_seeking_stakes"),
        "next_is_selection": derive(final, p82) == "expanded-select",
        "wrong_package_rejected": wrong_package_rejected,
        "conformant": runtime.identity_conforms(final),
    }


def synthetic_contradiction_branch(waiting, p82, runtime):
    packages = base305.example_variants(b.base268)
    stake = base305.fixture_stake(base305.FEATURES[0])
    stake["minimum_score_gap"] = 100
    fixture_subject, binding = with_active_stake(waiting, stake, p82)
    selection = base305.choose(stake, descriptors_for(packages, p82))
    final, receipt = compile_contradiction(
        fixture_subject, binding, selection, p82
    )
    return {
        "unsupported": not selection["supported"]
        and selection["selected_world_id"] is None,
        "wait_retained": final["active_world_stream_wait"]
        == fixture_subject["active_world_stream_wait"],
        "stake_retained": final["active_world_seeking_stake"] == binding,
        "receipt_exact": final["active_world_seeking_stake_revision_due"][
            "receipt_digest"
        ]
        == receipt["receipt_digest"],
        "next_is_revision": derive(final, p82) == "revise-world-seeking-stake",
        "conformant": runtime.identity_conforms(final),
    }


def preflight(root, p82, runtime, parent, result310, result305, packages):
    root.mkdir(parents=True, exist_ok=True)
    evaluations = [package_evaluation(package, p82) for package in packages]
    remaining = remaining_packages(parent, packages)
    empty_observation, waiting, reused = install_wait(parent, p82)
    supported = synthetic_supported_branch(waiting, p82, runtime)
    contradicted = synthetic_contradiction_branch(waiting, p82, runtime)
    changed = copy.deepcopy(parent)
    changed.pop("artifact_digest", None)
    changed["active_world_seeking_stake"]["stake"]["weights"][
        base305.FEATURES[0]
    ] += 1
    changed = p82.seal(changed)
    live_selection_unopened = {
        "catalog_count": len(remaining),
        "selection_computed": False,
        "selected_world_id": None,
        "blind_world_id": None,
    }
    route, identity = b.base272.base265.floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "exact_ot0310_parent": parent["artifact_digest"] == PARENT_DIGEST
        and result310["receipt_digest"] == OT310_RECEIPT
        and result310["observer_disposition"] == "promoted"
        and result310["boundary"]["operation"] == "expand-environment"
        and derive(parent, p82) == "expand-environment"
        and runtime.identity_conforms(parent),
        "active_stake_exact_and_untuned": active_stake_valid(parent, p82)
        and parent["active_world_seeking_stake"]
        == result305["stake_actor"]["binding"],
        "objective_remaining_catalog_unopened": len(packages) == PROVIDER_COUNT
        and len({package["world_id"] for package in packages}) == PROVIDER_COUNT
        and all(evaluation["valid"] for evaluation in evaluations)
        and len(remaining) == REMAINING_COUNT
        and all(
            package["world_id"] not in seen_world_ids(parent)
            for package in remaining
        )
        and live_selection_unopened["selection_computed"] is False,
        "empty_release_installs_wait": empty_observation["result"] == "empty"
        and not reused
        and waiting["continuation"]["status"] == "open"
        and derive(waiting, p82) == "wait-provider"
        and runtime.identity_conforms(waiting),
        "synthetic_support_branch_passes": all(supported.values()),
        "synthetic_contradiction_branch_passes": all(contradicted.values()),
        "tampered_stake_rejected": not active_stake_valid(changed, p82),
        "prior_negative_verdict_preserved": result305["observer_disposition"]
        == "rejected"
        and result305["e11"]
        == {
            "operational_contact": True,
            "subject_conditioned_choice": False,
            "priority_bearing_contact": False,
        },
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0310_receipt_digest": result310["receipt_digest"],
        "provider_count": PROVIDER_COUNT,
        "remaining_count": REMAINING_COUNT,
        "live_selection_unopened": live_selection_unopened,
        "supported_fixture": supported,
        "contradiction_fixture": contradicted,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


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
        result310,
        result305,
        packages,
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
            result310,
            result305,
            packages,
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0311 unavailable")
    run.mkdir(parents=True, exist_ok=True)
    empty_observation, waiting, reused = install_wait(parent, p82)
    remaining = remaining_packages(waiting, packages)
    descriptors = descriptors_for(remaining, p82)
    binding = waiting["active_world_seeking_stake"]
    selection = base305.choose(binding["stake"], descriptors)
    observation = priority_receipt = None
    if selection["supported"]:
        selected = next(
            package
            for package in remaining
            if package["world_id"] == selection["selected_world_id"]
        )
        observation, final, priority_receipt = compile_supported(
            waiting, binding, selection, selected, p82
        )
        transition = "supported-to-expanded-selection"
    else:
        final, priority_receipt = compile_contradiction(
            waiting, binding, selection, p82
        )
        transition = "contradicted-to-stake-revision"
    operational = bool(
        not reused
        and final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final)
        and derive(final, p82)
        == (
            "expanded-select"
            if selection["supported"]
            else "revise-world-seeking-stake"
        )
    )
    condition_effect = bool(
        selection["supported"]
        and selection["selected_world_id"] != selection["blind_world_id"]
    )
    episode = base305.base304.complete_episode(
        episode_id="OT-0311-live-remaining-catalog-priority-wake",
        valid_contact=operational and selection["supported"],
        condition_changes_move=condition_effect,
    )
    e11 = base305.base304.challenger_e11(episode)
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "two_content_free_actor_free_operations": PULSE is None
        and not reused,
        "exact_objective_remaining_catalog": len(remaining) == REMAINING_COUNT
        and all(
            package["world_id"] not in seen_world_ids(parent)
            for package in remaining
        ),
        "active_stake_unchanged": binding == parent["active_world_seeking_stake"]
        and final["active_world_seeking_stake"] == binding,
        "selection_supported": selection["supported"],
        "stake_changes_blind_world_choice": condition_effect,
        "same_catalog_for_stake_and_blind": bool(descriptors)
        and selection["blind_world_id"]
        in {row["world_id"] for row in descriptors},
        "selected_world_enters_standing_offer": bool(
            observation
            and observation["status"] == "world-available"
            and final["active_streamed_world_offer"]["world_id"]
            == selection["selected_world_id"]
        ),
        "e11_priority_bearing_contact": e11
        == {
            "operational_contact": True,
            "subject_conditioned_choice": True,
            "priority_bearing_contact": True,
        },
        "final_open_conformant": operational,
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0310_receipt_digest": result310["receipt_digest"],
        "operations": ["expand-environment", "wait-provider"],
        "empty_provider_observation": empty_observation,
        "public_descriptors": descriptors,
        "selection": selection,
        "provider_observation": observation,
        "priority_contact_receipt": priority_receipt,
        "transition": transition,
        "e11": e11,
        "checks": checks,
        "operational_transition_passed": operational,
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


if __name__ == "__main__":
    raise SystemExit(main())
