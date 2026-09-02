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
BASE_PATH = ROOT / "ot_0260_cross_epoch_projection_refresh.py"
BASE_SHA256 = "7445a723bbf061e3984d2d82d4d3254c520b06ea2354d78c203dd5679a190d5b"
PARENT_DIGEST = "c319bade11abadb53d78d52098b3b29d4e44911b0d5f09353bbbe0b0a4d1dcd8"
OT260_RECEIPT = "5e4ccee84eecaeec506fc40afb5d7f469cdc598764afee908865729cd74c0802"
AUTHORITY = "ot-0261-correction-before-projection-refresh"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0260 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0261_frozen_ot0260", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base260 = load_base()
base248 = base260.base248
authority_base = base260.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def incumbent(subject, p82):
    return base260.operation_for(subject, p82)


def challenger(subject, p82):
    inherited = base248.operation_for(subject)
    if (
        subject["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and base260.needs_refresh(subject, p82)
    ):
        return "refresh-opportunity-projection"
    return inherited


def variant(parent, p82, phase, stale):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["fixed_g6_recurrence_driver"] = copy.deepcopy(
        child["fixed_g6_recurrence_driver"]
    )
    child["fixed_g6_recurrence_driver"]["phase"] = phase
    if stale:
        child["local_frontier_ledger"] = copy.deepcopy(
            child["local_frontier_ledger"]
        )
        child["local_frontier_ledger"]["precedence-fixture"] = phase
    return p82.seal(child)


def evaluate(parent, p82, fn):
    fixtures = [
        ("assimilate-fresh", "assimilate", False, "expanded-select"),
        (
            "assimilate-stale",
            "assimilate",
            True,
            "refresh-opportunity-projection",
        ),
        ("correct-fresh", "correct", False, "outward-correct"),
        ("correct-stale", "correct", True, "outward-correct"),
        ("contact-stale", "contact", True, "reject"),
        ("widen-stale", "widen", True, "reject"),
        ("unknown-stale", "unknown", True, "reject"),
    ]
    rows = []
    for case_id, phase, stale, expected in fixtures:
        subject = variant(parent, p82, phase, stale)
        observed = fn(subject, p82)
        rows.append(
            {
                "case_id": case_id,
                "phase": phase,
                "stale": stale,
                "expected": expected,
                "observed": observed,
                "passed": observed == expected,
            }
        )
    return {
        "case_count": len(rows),
        "pass_count": sum(row["passed"] for row in rows),
        "results": rows,
    }


def compile_transition(parent, comparison, p82):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    prior = parent["active_opportunity_projection_refresh_policy"]
    body = {
        "authority": AUTHORITY + "-phase-aware-freshness-policy",
        "source_subject_digest": parent["artifact_digest"],
        "prior_policy_receipt_digest": prior["receipt_digest"],
        "heldout_comparison_digest": p82.digest(comparison),
        "precedence": [
            "live-contact-and-correction",
            "projection-refresh-at-assimilation",
            "inherited-content-free-selector",
        ],
        "refresh_phase": "assimilate",
        "stale_operation": "refresh-opportunity-projection",
        "actor_authority": False,
        "selection_authority": False,
        "world_authority": False,
        "correction_authority": False,
    }
    policy = {**body, "receipt_digest": p82.digest(body)}
    child["opportunity_projection_refresh_policy_transitions"] = [
        *child.get("opportunity_projection_refresh_policy_transitions", []),
        policy,
    ]
    child["active_opportunity_projection_refresh_policy"] = policy
    return p82.seal(child)


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base = lineage.selector_base, lineage.base
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0261").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0260",
        "open-post-wait-subject-with-fresh-projection.json",
    )
    result260 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0260",
        "cross-epoch-projection-refresh-aggregate.json",
    )
    old = evaluate(parent, p82, incumbent)
    new = evaluate(parent, p82, challenger)
    successor = compile_transition(parent, new, p82)
    route = (
        base248.base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(
            parent["active_executable_routing_selector"]["route"],
            parent["actor_authored_contact_mechanisms"][-1]["expression"],
        )
    )
    identity = authority_base.reuse.extension_base.evaluate(
        authority_base.reuse.extension_base.load_operation(
            parent["developmental_property_extensions"][0]["operation_source"]
        ),
        authority_base.reuse.accumulated_floor(),
    )
    repaired_ids = {"correct-stale", "contact-stale", "widen-stale", "unknown-stale"}
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_fresh_selection": parent["artifact_digest"] == PARENT_DIGEST
        and parent["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and not base260.needs_refresh(parent, p82)
        and challenger(parent, p82) == "expanded-select"
        and runtime.identity_conforms(parent),
        "ot0260_exact_promotion": result260["observer_disposition"] == "promoted"
        and result260["receipt_digest"] == OT260_RECEIPT
        and result260["final_subject_digest"] == PARENT_DIGEST,
        "challenger_7_of_7": new["pass_count"] == 7,
        "incumbent_3_of_7": old["pass_count"] == 3,
        "four_stale_phase_precedence_repairs": all(
            not next(row for row in old["results"] if row["case_id"] == case_id)[
                "passed"
            ]
            and next(row for row in new["results"] if row["case_id"] == case_id)[
                "passed"
            ]
            for case_id in repaired_ids
        ),
        "three_existing_cases_preserved": all(
            row["passed"]
            for row in new["results"]
            if row["case_id"] not in repaired_ids
        ),
        "operational_state_unchanged": successor["fixed_g6_recurrence_driver"]
        == parent["fixed_g6_recurrence_driver"]
        and successor["local_frontier_ledger"] == parent["local_frontier_ledger"]
        and successor["active_opportunity_projection"]
        == parent["active_opportunity_projection"]
        and successor["active_streamed_world_interface"]
        == parent["active_streamed_world_interface"]
        and successor["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and successor["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"],
        "policy_non_authoritative": all(
            successor["active_opportunity_projection_refresh_policy"][key] is False
            for key in (
                "actor_authority",
                "selection_authority",
                "world_authority",
                "correction_authority",
            )
        ),
        "live_successor_still_selects": challenger(successor, p82)
        == "expanded-select",
        "successor_conforms": runtime.identity_conforms(successor),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "incumbent": old,
        "challenger": new,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": successor["continuation"]["status"],
        "final_subject_digest": successor["artifact_digest"],
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    if args.preflight_only:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0261 evidence")
    run.mkdir(parents=True)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", successor)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
