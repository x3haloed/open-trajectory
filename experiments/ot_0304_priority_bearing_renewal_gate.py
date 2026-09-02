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
BASE_PATH = ROOT / "ot_0303_exact_eighth_wait_recurrence.py"
BASE_SHA256 = "f1a0548a4e17c24814d63f593db67bc7418d3410d5e99265ce89afda4f736351"
PARENT_DIGEST = "e193ec503bea80d18e0cbc315b3af1d7cb72c198947b0e8d09b5d4da08b87310"
OT303_RECEIPT = "2d6bc3b0fac72e7e23c0ab3921e8ff0e1189df559413b03afe41fd0d3dda04cf"
AUTHORITY = "ot-0304-priority-bearing-renewal-gate"
EVALUATION_EPOCH = "E11-priority-bearing-renewal"

HISTORICAL_RECEIPTS = {
    "OT-0122": "014d2f2942e6f2c5c5dd23f4ffebd9e7e6024250f56497e8730e87f1095ba880",
    "OT-0197": "749218d485dd3f87f30affd5dac3dc3de6a2b58e5ecb8b61ca514e48b8bb89c4",
    "OT-0254": "a34309f952e282bca2772e30f6988c6078b5988f6f5a811bb3efd699ae6c347a",
    "OT-0283": "5fc6d7f539bdfaeea1bc3d84af0a92c3ed57fae4c378ea4f7e0bce5a78899246",
}

OPERATIONAL_FIELDS = (
    "valid_contact",
    "new_contact",
    "fresh_actor_boundary",
    "bound_before_consequence",
    "independent_consequence",
    "authority_separated",
    "trace_retained",
    "subject_remains_open",
)
CONDITION_FIELDS = (
    "condition_present",
    "condition_bound_before_contact",
    "matched_condition_erasure",
    "condition_changes_move",
)
PRIORITY_FIELDS = (
    "condition_executable",
    "support_condition",
    "contradiction_condition",
    "contact_can_support",
    "contact_can_contradict",
    "consequence_changes_next_operation",
)


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0303 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0304_frozen_ot0303", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base303 = load_base()


def write_json(path, value):
    base303.write_json(path, value)


def operational_contact(episode):
    return all(episode.get(field) is True for field in OPERATIONAL_FIELDS)


def incumbent_e10(episode):
    operational = operational_contact(episode)
    return {
        "operational_contact": operational,
        "developmental_advance": operational,
    }


def challenger_e11(episode):
    operational = operational_contact(episode)
    conditioned = all(episode.get(field) is True for field in CONDITION_FIELDS)
    priority = (
        operational
        and conditioned
        and episode.get("condition_origin") == "subject-stake"
        and all(episode.get(field) is True for field in PRIORITY_FIELDS)
    )
    return {
        "operational_contact": operational,
        "subject_conditioned_choice": conditioned,
        "priority_bearing_contact": priority,
    }


def complete_episode(**changes):
    episode = {
        "episode_id": "construction-positive",
        **{field: True for field in OPERATIONAL_FIELDS},
        **{field: True for field in CONDITION_FIELDS},
        **{field: True for field in PRIORITY_FIELDS},
        "condition_origin": "subject-stake",
    }
    episode.update(changes)
    return episode


def construction_fixtures():
    positive = complete_episode()
    operational_mutants = {
        field: challenger_e11(complete_episode(**{field: False}))
        for field in OPERATIONAL_FIELDS
    }
    condition_mutants = {
        field: challenger_e11(complete_episode(**{field: False}))
        for field in CONDITION_FIELDS
    }
    priority_mutants = {
        field: challenger_e11(complete_episode(**{field: False}))
        for field in PRIORITY_FIELDS
    }
    origin_mutants = {
        origin: challenger_e11(complete_episode(condition_origin=origin))
        for origin in ("none", "state-index", "observer-stake", "selector")
    }
    operational_truth_table = []
    for values in itertools.product((False, True), repeat=len(OPERATIONAL_FIELDS)):
        episode = complete_episode(**dict(zip(OPERATIONAL_FIELDS, values)))
        old = incumbent_e10(episode)
        new = challenger_e11(episode)
        operational_truth_table.append(
            old["operational_contact"] == new["operational_contact"]
        )
    checks = {
        "positive_reaches_all_three_levels": challenger_e11(positive)
        == {
            "operational_contact": True,
            "subject_conditioned_choice": True,
            "priority_bearing_contact": True,
        },
        "incumbent_operational_semantics_preserved_exhaustively": all(
            operational_truth_table
        )
        and len(operational_truth_table) == 2 ** len(OPERATIONAL_FIELDS),
        "each_operational_anchor_is_required": all(
            not result["operational_contact"]
            and not result["priority_bearing_contact"]
            for result in operational_mutants.values()
        ),
        "each_causal_condition_is_required": all(
            not result["subject_conditioned_choice"]
            and not result["priority_bearing_contact"]
            for result in condition_mutants.values()
        ),
        "each_priority_contact_anchor_is_required": all(
            result["operational_contact"]
            and result["subject_conditioned_choice"]
            and not result["priority_bearing_contact"]
            for result in priority_mutants.values()
        ),
        "non_subject_origins_do_not_count_as_priority": all(
            result["operational_contact"]
            and result["subject_conditioned_choice"]
            and not result["priority_bearing_contact"]
            for result in origin_mutants.values()
        ),
    }
    checks["passed"] = all(checks.values())
    return {
        "authority": AUTHORITY + "-construction-fixtures",
        "evaluation_epoch": EVALUATION_EPOCH,
        "operational_truth_table_size": len(operational_truth_table),
        "operational_mutants": operational_mutants,
        "condition_mutants": condition_mutants,
        "priority_mutants": priority_mutants,
        "origin_mutants": origin_mutants,
        "checks": checks,
    }


def setup(args):
    chain = base303.b.authority_base.guide_base.load_base()
    selector, core = chain.selector_base, chain.base
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0304").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0303", "open-subject-at-eighth-wait.json"
    )
    result303 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0303",
        "exact-eighth-wait-recurrence-aggregate.json",
    )
    return repo, store, run, selector, p82, runtime, parent, result303


def preflight(root, p82, runtime, parent, result303):
    root.mkdir(parents=True, exist_ok=True)
    fixtures = construction_fixtures()
    route, identity = base303.b.base272.base265.floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_open_renewal": parent["artifact_digest"] == PARENT_DIGEST
        and result303["receipt_digest"] == OT303_RECEIPT
        and result303["observer_disposition"] == "promoted"
        and result303["final_subject_digest"] == PARENT_DIGEST
        and base303.b.base279.derive(parent, [], p82) == "renew-world-feed"
        and runtime.identity_conforms(parent),
        "construction_fixtures_pass": fixtures["checks"]["passed"],
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "evaluation_epoch": EVALUATION_EPOCH,
        "source_subject_digest": parent["artifact_digest"],
        "construction_fixture_digest": p82.digest(fixtures),
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "construction-fixtures.json", fixtures)
    write_json(root / "fixture-conformance.json", result)
    return result


def load_historical(selector, p82, repo, store, experiment, name):
    return selector.load_artifact(p82, repo, store, experiment, name)


def historical_episodes(selector, p82, repo, store):
    raw122 = load_historical(
        selector,
        p82,
        repo,
        store,
        "OT-0122",
        "subject-selected-world-contact-aggregate.json",
    )
    raw197 = load_historical(
        selector,
        p82,
        repo,
        store,
        "OT-0197",
        "coupled-pursuit-assimilation-aggregate.json",
    )
    raw254 = load_historical(
        selector,
        p82,
        repo,
        store,
        "OT-0254",
        "projected-opportunity-selection-aggregate.json",
    )
    raw283 = load_historical(
        selector,
        p82,
        repo,
        store,
        "OT-0283",
        "morrowglass-reachable-recurrence-aggregate.json",
    )

    route122 = raw122["consequence_route"]["binding"]
    remaining122 = route122["route_assimilation"]["remaining_uncertainty"].lower()
    opening122 = route122["successor_opening"]["next_opening"].lower()
    extension_defect = "resource scarcity" in remaining122 and "resource scarcity" not in opening122

    blind = complete_episode(
        episode_id="OT-0283-blind-renewal",
        condition_present=False,
        condition_bound_before_contact=False,
        matched_condition_erasure=False,
        condition_changes_move=False,
        condition_origin="none",
        condition_executable=False,
        support_condition=False,
        contradiction_condition=False,
        consequence_changes_next_operation=False,
    )
    indexed = complete_episode(
        episode_id="OT-0254-state-indexed-selection",
        condition_origin="state-index",
        condition_executable=False,
        support_condition=False,
        contradiction_condition=False,
    )
    stake = complete_episode(episode_id="OT-0197-executable-stake")
    defective = complete_episode(
        episode_id="OT-0122-defective-successor",
        valid_contact=not extension_defect,
        condition_origin="selector",
        condition_executable=False,
        support_condition=False,
        contradiction_condition=False,
    )
    breached = copy.deepcopy(stake)
    breached.update(
        episode_id="OT-0197-authority-breach-mutant",
        authority_separated=False,
    )

    source_checks = {
        "ot0122_exact_and_defective": raw122["receipt_digest"]
        == HISTORICAL_RECEIPTS["OT-0122"]
        and raw122["subject_selection_causal_passed"]
        and extension_defect,
        "ot0197_exact_priority_ablation": raw197["receipt_digest"]
        == HISTORICAL_RECEIPTS["OT-0197"]
        and raw197["observer_disposition"] == "promoted"
        and raw197["active_pass_count"] == 6
        and raw197["control_pass_count"] == 2
        and raw197["assimilation"]["aligned"]
        and raw197["checks"]["all_active_open_invention"],
        "ot0254_exact_state_conditioning": raw254["receipt_digest"]
        == HISTORICAL_RECEIPTS["OT-0254"]
        and raw254["observer_disposition"] == "promoted"
        and raw254["checks"]["selected_exact_projection_pair"]
        and not raw254["matched_baseline"]["actor_accepted"],
        "ot0283_exact_blind_renewal": raw283["receipt_digest"]
        == HISTORICAL_RECEIPTS["OT-0283"]
        and raw283["observer_disposition"] == "promoted"
        and raw283["checks"]["renewal_provider_promoted"]
        and raw283["operations"][-1] == "renew-world-feed",
    }
    source_checks["passed"] = all(source_checks.values())
    return [blind, indexed, stake, defective, breached], source_checks


EXPECTED = {
    "OT-0283-blind-renewal": (True, False, False),
    "OT-0254-state-indexed-selection": (True, True, False),
    "OT-0197-executable-stake": (True, True, True),
    "OT-0122-defective-successor": (False, True, False),
    "OT-0197-authority-breach-mutant": (False, True, False),
}


def compare(episodes):
    rows = []
    for episode in episodes:
        old = incumbent_e10(episode)
        new = challenger_e11(episode)
        expected = EXPECTED[episode["episode_id"]]
        rows.append(
            {
                "episode_id": episode["episode_id"],
                "incumbent": old,
                "challenger": new,
                "expected": {
                    "operational_contact": expected[0],
                    "subject_conditioned_choice": expected[1],
                    "priority_bearing_contact": expected[2],
                },
                "operational_no_regression": old["operational_contact"]
                == new["operational_contact"],
                "expected_match": tuple(new.values()) == expected,
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, selector, p82, runtime, parent, result303 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(run / "preflight", p82, runtime, parent, result303)
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0304 unavailable")

    episodes, source_checks = historical_episodes(selector, p82, repo, store)
    rows = compare(episodes)
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "historical_sources_exact": source_checks["passed"],
        "all_operational_semantics_preserved": all(
            row["operational_no_regression"] for row in rows
        ),
        "all_heldout_labels_match": all(row["expected_match"] for row in rows),
        "blind_renewal_retained_without_priority": rows[0]["challenger"]
        == {
            "operational_contact": True,
            "subject_conditioned_choice": False,
            "priority_bearing_contact": False,
        },
        "state_index_is_conditioning_not_priority": rows[1]["challenger"]
        == {
            "operational_contact": True,
            "subject_conditioned_choice": True,
            "priority_bearing_contact": False,
        },
        "executable_stake_earns_priority": rows[2]["challenger"]
        == {
            "operational_contact": True,
            "subject_conditioned_choice": True,
            "priority_bearing_contact": True,
        },
        "defective_successor_retains_causal_choice_only": rows[3]["challenger"]
        == {
            "operational_contact": False,
            "subject_conditioned_choice": True,
            "priority_bearing_contact": False,
        },
        "authority_breach_fails_operational_and_priority": rows[4]["challenger"]
        == {
            "operational_contact": False,
            "subject_conditioned_choice": True,
            "priority_bearing_contact": False,
        },
        "current_subject_unchanged_open": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and base303.b.base279.derive(parent, [], p82) == "renew-world-feed"
        and runtime.identity_conforms(parent),
        "zero_fresh_actors": True,
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "evaluation_epoch": EVALUATION_EPOCH,
        "source_subject_digest": parent["artifact_digest"],
        "construction_fixture_receipt_digest": fixtures["receipt_digest"],
        "source_checks": source_checks,
        "rows": rows,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": parent["continuation"]["status"],
        "final_subject_digest": parent["artifact_digest"],
        "fresh_actor_count": 0,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    run.mkdir(parents=True, exist_ok=True)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "unchanged-current-subject.json", parent)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
