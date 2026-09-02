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
BASE_PATH = ROOT / "ot_0254_projected_opportunity_selection.py"
BASE_SHA256 = "23955cd1921ebc877d3f0a78477d3cf5177a34b0658a8d081ae2c6f43171df79"
PARENT_DIGEST = "340a7fb51ba924797ebd0c98795e409e5f4929e3c5e52e196b2462f70135cd20"
OT254_RECEIPT = "a34309f952e282bca2772e30f6988c6078b5988f6f5a811bb3efd699ae6c347a"
AUTHORITY = "ot-0255-final-projected-correction-and-saturation"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0254 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0255_frozen_ot0254", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base254 = load_base()
base253 = base254.base253
base252 = base254.base252
base250 = base254.base250
base248 = base254.base248
base247 = base248.base247
base244 = base254.base244
base243 = base252.base243
authority_base = base254.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def refresh_projection(subject, p82):
    projection = base253.derive(subject)
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    resolver_source = inspect.getsource(base253.derive)
    prior = subject["active_opportunity_projection"]
    body = {
        "authority": AUTHORITY + "-projection-refresh",
        "source_subject_digest": subject["artifact_digest"],
        "prior_projection_receipt_digest": prior["projection_receipt_digest"],
        "active_epoch_id": subject["actor_authored_environment_epochs"][-1][
            "environment_id"
        ],
        "active_epoch_sources_digest": p82.digest(
            subject["actor_authored_environment_epochs"][-1]["visible_sources"]
        ),
        "ledger_digest": p82.digest(subject["local_frontier_ledger"]),
        "resolver_source": resolver_source,
        "resolver_source_digest": p82.digest(resolver_source),
        "status": projection["status"],
        "opportunities": projection["opportunities"],
        "opportunity_count": len(projection["opportunities"]),
        "source_errors": projection["source_errors"],
        "selection_authority": False,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
    }
    receipt = {**body, "projection_receipt_digest": p82.digest(body)}
    child["opportunity_projection_transitions"] = [
        *child.get("opportunity_projection_transitions", []),
        receipt,
    ]
    child["active_opportunity_projection"] = receipt
    return p82.seal(child)


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = (
        lineage.selector_base,
        lineage.base,
        lineage.base130,
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0255").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0254",
        "open-subject-at-projected-opportunity-contradiction.json",
    )
    result254 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0254",
        "projected-opportunity-selection-aggregate.json",
    )
    extension, _, world, _, target = base248.selected(parent)
    fixture = run.parent / "OT-0255-preflight"
    if fixture.exists():
        import shutil

        shutil.rmtree(fixture)
    correction = base248.fixture_correction(fixture / "correction", parent, p82)
    prospective = refresh_projection(correction["final"], p82)
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
        "parent_exact_correct": parent["artifact_digest"] == PARENT_DIGEST
        and parent["fixed_g6_recurrence_driver"]["phase"] == "correct"
        and base248.operation_for(parent) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0254_exact_promotion": result254["observer_disposition"] == "promoted"
        and result254["receipt_digest"] == OT254_RECEIPT
        and result254["final_subject_digest"] == PARENT_DIGEST,
        "selected_state_aligned": extension["target_symbol"] == target
        and world["target_symbol"] == target
        and world["result"]["matches"] == 2,
        "target_not_hardcoded": target not in Path(__file__).read_text(),
        "fixture_checker_and_public_4": correction["checker"]
        and correction["public"]["matches"] == 4,
        "fixture_6_vs_2": correction["followup"]["result"]["matches"] == 6
        and correction["followup"]["unchanged_control"]["matches"] == 2,
        "prospective_projection_saturated": prospective[
            "active_opportunity_projection"
        ]["status"]
        == "saturated"
        and prospective["active_opportunity_projection"]["opportunity_count"] == 0
        and all(
            prospective["active_opportunity_projection"][key] is False
            for key in (
                "selection_authority",
                "world_authority",
                "scoring_authority",
                "admission_authority",
            )
        ),
        "prospective_epoch_saturated": len(base244.remaining_epoch(prospective)) == 0
        and base248.operation_for(prospective) == "expand-environment",
        "prospective_open_conformant": prospective["continuation"]["status"]
        == "open"
        and prospective["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and runtime.identity_conforms(prospective),
        "prior_epoch_preserved": prospective["actor_authored_environment_epochs"][0]
        == parent["actor_authored_environment_epochs"][0],
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0255 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    row, corrected = base248.continue_once(
        runtime, base, base130, repo, p82, run / "pulse-1", parent
    )
    actor = row["actor"]
    followup = row["world"]
    final = refresh_projection(corrected, p82) if actor and actor["accepted"] and followup else parent
    gates = {
        "preflight_passed": checks["passed"],
        "one_content_free_correction_pulse": row["pulse"]["content"] is None
        and row["operation"] == "outward-correct",
        "one_fresh_actor": row["fresh_actor_count"] == 1,
        "fresh_corrector_accepted": bool(actor and actor["accepted"]),
        "g10_accepted": bool(actor and actor["g10_disposition"]),
        "public_4_of_4": bool(
            actor and actor["public"] and actor["public"]["matches"] == 4
        ),
        "sealed_6_of_6": bool(
            followup
            and followup["result"]["all_valid"]
            and followup["result"]["matches"] == 6
        ),
        "unchanged_2_of_6": bool(
            followup
            and followup["unchanged_control"]["all_valid"]
            and followup["unchanged_control"]["matches"] == 2
        ),
        "final_target_verified": bool(
            followup
            and final["actor_authored_environment_extensions"][-1]["status"]
            == "corrected-and-world-verified"
        ),
        "projection_refreshed_saturated": final[
            "active_opportunity_projection"
        ]["status"]
        == "saturated"
        and final["active_opportunity_projection"]["opportunity_count"] == 0,
        "projection_remained_non_authoritative": all(
            final["active_opportunity_projection"][key] is False
            for key in (
                "selection_authority",
                "world_authority",
                "scoring_authority",
                "admission_authority",
            )
        ),
        "active_epoch_saturated": len(base244.remaining_epoch(final)) == 0,
        "next_operation_expansion": base248.operation_for(final)
        == "expand-environment",
        "provider_stream_empty": base247.next_world(final) is None,
        "prior_epoch_preserved": final["actor_authored_environment_epochs"][0]
        == parent["actor_authored_environment_epochs"][0],
        "final_open_assimilate": final["continuation"]["status"] == "open"
        and final["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and runtime.identity_conforms(final),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "pulse_transition": row,
        "projection_refresh_receipt_digest": final[
            "active_opportunity_projection"
        ]["projection_receipt_digest"],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
