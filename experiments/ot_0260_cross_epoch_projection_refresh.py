from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0259_post_wait_generic_correction.py"
BASE_SHA256 = "1bfa16e8915f062b5b4bb7a3c926fd84baf776e4ded7a1db79f5ccf4238e19cf"
PARENT_DIGEST = "5c680025854492770e9e39bd9996959fc3a1a9129955c17edede3999fb7ff54f"
OT259_RECEIPT = "f8e789758f22e9c8ac74f6371c516c835095a6bc3ea4d2cb73aa9d795803be2e"
AUTHORITY = "ot-0260-cross-epoch-projection-refresh"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0259 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0260_frozen_ot0259", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base259 = load_base()
base258 = base259.base258
base255 = base259.base255
base253 = base255.base253
base252 = base259.base252
base248 = base259.base248
base244 = base259.base244
authority_base = base259.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def descriptor(subject, p82):
    epoch = subject["actor_authored_environment_epochs"][-1]
    return {
        "active_epoch_id": epoch["environment_id"],
        "active_epoch_sources_digest": p82.digest(epoch["visible_sources"]),
        "ledger_digest": p82.digest(subject["local_frontier_ledger"]),
    }


def needs_refresh(subject, p82):
    projection = subject.get("active_opportunity_projection")
    if not isinstance(projection, dict):
        return True
    expected = descriptor(subject, p82)
    return any(projection.get(key) != value for key, value in expected.items())


def operation_for(subject, p82):
    if needs_refresh(subject, p82):
        return "refresh-opportunity-projection"
    return base248.operation_for(subject)


def refresh(subject, p82):
    derived = base253.derive(subject)
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    current = subject.get("active_opportunity_projection") or {}
    resolver_source = inspect.getsource(base253.derive)
    body = {
        "authority": AUTHORITY + "-projection-refresh",
        "source_subject_digest": subject["artifact_digest"],
        "prior_projection_receipt_digest": current.get(
            "projection_receipt_digest"
        ),
        **descriptor(subject, p82),
        "resolver_source": resolver_source,
        "resolver_source_digest": p82.digest(resolver_source),
        "status": derived["status"],
        "opportunities": derived["opportunities"],
        "opportunity_count": len(derived["opportunities"]),
        "source_errors": derived["source_errors"],
        "selection_authority": False,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
    }
    receipt = {**body, "projection_receipt_digest": p82.digest(body)}
    policy_body = {
        "authority": AUTHORITY + "-freshness-policy",
        "source_subject_digest": subject["artifact_digest"],
        "inputs": [
            "latest-epoch-id",
            "latest-epoch-visible-sources-digest",
            "exact-ledger-digest",
        ],
        "stale_operation": "refresh-opportunity-projection",
        "fresh_operation_authority": subject[
            "active_content_free_operation_selector"
        ]["authority"],
        "actor_authority": False,
        "selection_authority": False,
    }
    policy = {**policy_body, "receipt_digest": p82.digest(policy_body)}
    child["opportunity_projection_refresh_policy_transitions"] = [
        *child.get("opportunity_projection_refresh_policy_transitions", []),
        policy,
    ]
    child["active_opportunity_projection_refresh_policy"] = policy
    child["opportunity_projection_transitions"] = [
        *child.get("opportunity_projection_transitions", []),
        receipt,
    ]
    child["active_opportunity_projection"] = receipt
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": (
            "Select one unledgered public surface from the freshly projected "
            "active coordination epoch."
        ),
    }
    child["continuation_liveness"] = {
        "authority": AUTHORITY,
        "status": "fresh-active-epoch-opportunities",
        "projection_receipt_digest": receipt["projection_receipt_digest"],
        "opportunity_count": receipt["opportunity_count"],
        "next_operation": "expanded-select",
    }
    child["unresolved"] = (
        "Use the fresh non-authoritative opportunity projection in the next "
        "content-free selection encounter."
    )
    return p82.seal(child)


def operational_core_preserved(parent, child):
    keys = (
        "fixed_g6_recurrence_driver",
        "local_frontier_ledger",
        "actor_authored_environment_epochs",
        "actor_authored_environment_extensions",
        "pending_contact_bearing_continuations",
        "active_pursuit",
        "active_content_free_operation_selector",
        "active_streamed_world_interface",
        "world_stream_wait_receipts",
        "world_stream_wait_discharge_receipts",
    )
    return all(parent[key] == child[key] for key in keys)


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
    run = (args.evidence_root or store / "runs/OT-0260").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0259",
        "open-post-wait-subject-after-generic-correction.json",
    )
    result259 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0259",
        "post-wait-generic-correction-aggregate.json",
    )
    prospective = refresh(parent, p82)
    fresh_copy = copy.deepcopy(prospective)
    ledger_changed = copy.deepcopy(prospective)
    ledger_changed.pop("artifact_digest", None)
    ledger_changed["local_frontier_ledger"] = copy.deepcopy(
        ledger_changed["local_frontier_ledger"]
    )
    ledger_changed["local_frontier_ledger"]["refresh-fixture"] = True
    ledger_changed = p82.seal(ledger_changed)
    source_changed = copy.deepcopy(prospective)
    source_changed.pop("artifact_digest", None)
    source_changed["actor_authored_environment_epochs"] = copy.deepcopy(
        source_changed["actor_authored_environment_epochs"]
    )
    source_changed["actor_authored_environment_epochs"][-1]["visible_sources"] = {
        **source_changed["actor_authored_environment_epochs"][-1]["visible_sources"],
        "coordination/new.py": {
            "source": "def new_surface(case):\n    return []\n",
            "source_digest": "fixture",
        },
    }
    source_changed = p82.seal(source_changed)
    missing = copy.deepcopy(prospective)
    missing.pop("artifact_digest", None)
    missing.pop("active_opportunity_projection", None)
    missing = p82.seal(missing)
    malformed = copy.deepcopy(parent)
    malformed.pop("artifact_digest", None)
    malformed["actor_authored_environment_epochs"] = copy.deepcopy(
        malformed["actor_authored_environment_epochs"]
    )
    first_path = sorted(
        malformed["actor_authored_environment_epochs"][-1]["visible_sources"]
    )[0]
    malformed["actor_authored_environment_epochs"][-1]["visible_sources"][first_path] = {
        "source": "def broken(:\n",
        "source_digest": "fixture-malformed",
    }
    malformed = p82.seal(malformed)
    malformed_projection = refresh(malformed, p82)
    expected = {
        (row["target_path"], row["target_symbol"])
        for row in base244.remaining_epoch(parent)
    }
    observed = {
        (row["target_path"], row["target_symbol"])
        for row in prospective["active_opportunity_projection"]["opportunities"]
    }
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
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_open_assimilate": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and parent["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and runtime.identity_conforms(parent),
        "ot0259_exact_promotion": result259["observer_disposition"] == "promoted"
        and result259["receipt_digest"] == OT259_RECEIPT
        and result259["final_subject_digest"] == PARENT_DIGEST,
        "stale_parent_detected": needs_refresh(parent, p82)
        and operation_for(parent, p82) == "refresh-opportunity-projection",
        "exact_fresh_not_detected": not needs_refresh(fresh_copy, p82),
        "ledger_change_detected": needs_refresh(ledger_changed, p82),
        "source_change_detected": needs_refresh(source_changed, p82),
        "missing_projection_detected": needs_refresh(missing, p82),
        "malformed_fails_closed": malformed_projection[
            "active_opportunity_projection"
        ]["status"]
        == "invalid-descriptor"
        and malformed_projection["active_opportunity_projection"][
            "opportunity_count"
        ]
        == 0,
        "exact_resolver_agreement": observed == expected and len(observed) == 2,
        "projection_non_authoritative": all(
            prospective["active_opportunity_projection"][key] is False
            for key in (
                "selection_authority",
                "world_authority",
                "scoring_authority",
                "admission_authority",
            )
        ),
        "operational_core_preserved": operational_core_preserved(
            parent, prospective
        ),
        "next_operation_selection": operation_for(prospective, p82)
        == "expanded-select",
        "prospective_open_conformant": prospective["continuation"]["status"]
        == "open"
        and runtime.identity_conforms(prospective),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "prior_projection_epoch": parent["active_opportunity_projection"][
            "active_epoch_id"
        ],
        "active_epoch": parent["actor_authored_environment_epochs"][-1][
            "environment_id"
        ],
        "refreshed_projection_receipt_digest": prospective[
            "active_opportunity_projection"
        ]["projection_receipt_digest"],
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": prospective["continuation"]["status"],
        "final_subject_digest": prospective["artifact_digest"],
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    if args.preflight_only:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0260 evidence")
    run.mkdir(parents=True)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", prospective)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
