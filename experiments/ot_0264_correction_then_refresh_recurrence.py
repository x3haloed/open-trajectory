from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import inspect
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0263_live_registry_free_projected_selection.py"
BASE_SHA256 = "fbd94ec233a984e44fdd20d19557d3fe77356493c71a71e39760e298deaa687d"
PARENT_DIGEST = "cd5444cb1997f03afaaa3a113830e1a092e1afbe2eb543c8567798cbdba9e3e6"
OT263_RECEIPT = "97c026b98b08e4ebc6aad4f84a7777e636223e3f0cef29490082acaf8d42643e"
AUTHORITY = "ot-0264-correction-then-refresh-recurrence"
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0263 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0264_frozen_ot0263", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base263 = load_base()
base262 = base263.base262
base261 = base263.base261
base260 = base263.base260
base259 = base263.base259
base253 = base259.base255.base253
base252 = base263.base252
base248 = base263.base248
base244 = base263.base244
base243 = base259.base243
authority_base = base263.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def refresh_projection_only(subject, p82):
    derived = base253.derive(subject)
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    current = subject["active_opportunity_projection"]
    resolver_source = inspect.getsource(base253.derive)
    body = {
        "authority": AUTHORITY + "-projection-only-refresh",
        "source_subject_digest": subject["artifact_digest"],
        "prior_projection_receipt_digest": current["projection_receipt_digest"],
        **base260.descriptor(subject, p82),
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
    child["opportunity_projection_transitions"] = [
        *child.get("opportunity_projection_transitions", []),
        receipt,
    ]
    child["active_opportunity_projection"] = receipt
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": (
            "Select the sole remaining projected coordination surface under "
            "registry-free admission."
        ),
    }
    child["continuation_liveness"] = {
        "authority": AUTHORITY,
        "status": "fresh-post-correction-opportunity",
        "projection_receipt_digest": receipt["projection_receipt_digest"],
        "opportunity_count": receipt["opportunity_count"],
        "next_operation": "expanded-select",
    }
    child["unresolved"] = (
        "Use the refreshed sole opportunity in the next content-free selection encounter."
    )
    return p82.seal(child)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0264").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0263",
        "open-stale-subject-at-registry-free-contradiction.json",
    )
    result263 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0263",
        "live-registry-free-projected-selection-aggregate.json",
    )
    return repo, store, run, p82, runtime, parent, result263, base, base130


def preflight(repo, run, p82, runtime, parent, result263):
    fixture_root = run.parent / "OT-0264-preflight"
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    fixture = base259.fixture_correction(fixture_root, parent, p82)
    extension, pending, world, _epoch, target = base248.selected(parent)
    corrected = fixture["prospective"]
    refreshed = refresh_projection_only(corrected, p82)
    expected = {
        (row["target_path"], row["target_symbol"])
        for row in base244.remaining_epoch(corrected)
    }
    observed = {
        (row["target_path"], row["target_symbol"])
        for row in refreshed["active_opportunity_projection"]["opportunities"]
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
        "parent_exact_stale_correct": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and parent["fixed_g6_recurrence_driver"]["phase"] == "correct"
        and base260.needs_refresh(parent, p82)
        and base261.challenger(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0263_exact_promotion": result263["observer_disposition"] == "promoted"
        and result263["receipt_digest"] == OT263_RECEIPT
        and result263["final_subject_digest"] == PARENT_DIGEST,
        "selected_correction_state_aligned": pending["package"]["target_symbol"]
        == world["target_symbol"]
        == extension["target_symbol"]
        == target
        and pending["package"]["target_path"]
        == world["target_path"]
        == extension["target_path"]
        and world["result"]["matches"] == 2,
        "target_not_hardcoded": target not in Path(__file__).read_text(),
        "prompt_names_no_target_or_path": target not in fixture["prompt"]
        and extension["target_path"] not in fixture["prompt"],
        "descriptor_complete_public_4": fixture["checker"]
        and fixture["public"]["matches"] == 4,
        "prospective_6_vs_2": fixture["corrected"]["matches"] == 6
        and fixture["control"]["matches"] == 2,
        "corrected_stale_assimilate_routes_refresh": corrected["continuation"][
            "status"
        ]
        == "open"
        and corrected["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and base260.needs_refresh(corrected, p82)
        and base261.challenger(corrected, p82)
        == "refresh-opportunity-projection",
        "refresh_exact_one_opportunity": observed == expected and len(observed) == 1,
        "refresh_preserves_phase_aware_policy": refreshed[
            "active_opportunity_projection_refresh_policy"
        ]
        == parent["active_opportunity_projection_refresh_policy"],
        "refreshed_fresh_selects": not base260.needs_refresh(refreshed, p82)
        and base261.challenger(refreshed, p82) == "expanded-select",
        "prospective_states_conform": runtime.identity_conforms(corrected)
        and runtime.identity_conforms(refreshed),
        "wait_wake_and_provider_preserved": refreshed["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and refreshed["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"]
        and refreshed["active_streamed_world_interface"]
        == parent["active_streamed_world_interface"],
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    return {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "derived_target": target,
        "derived_path": extension["target_path"],
        "checks": checks,
    }, route, identity, target, extension


def correct(run, repo, p82, runtime, parent, fixtures, base, base130, target, extension):
    if run.exists():
        raise SystemExit("preserve existing OT-0264 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, run, repo)
    )
    pulse = {
        "authority": AUTHORITY + "-correction-pulse",
        "content": PULSE,
        "source_subject_digest": parent["artifact_digest"],
        "derived_operation": base261.challenger(parent, p82),
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    correction = base252.run_correction(context, p82, run / "correction", parent)
    followup = (
        base243.evaluate(run / "followup", parent, correction, p82)
        if correction["accepted"]
        else None
    )
    corrected = (
        base243.compile_correction(parent, correction, followup, p82)
        if followup and followup["promotion_gate"]
        else parent
    )
    if followup:
        write_json(run / "correction-world-receipt.json", followup)
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "one_null_correction_pulse": pulse["content"] is None
        and pulse["derived_operation"] == "outward-correct",
        "one_fresh_actor": True,
        "fresh_corrector_accepted": correction["accepted"],
        "g10_accepted": correction["g10_disposition"],
        "public_4_of_4": bool(
            correction["public"] and correction["public"]["matches"] == 4
        ),
        "sealed_6_of_6": bool(
            followup and followup["result"]["matches"] == 6
        ),
        "unchanged_2_of_6": bool(
            followup and followup["unchanged_control"]["matches"] == 2
        ),
        "selected_extension_corrected": bool(
            followup
            and corrected["actor_authored_environment_extensions"][-1]["status"]
            == "corrected-and-world-verified"
        ),
        "corrected_open_stale_assimilate": corrected["continuation"]["status"]
        == "open"
        and corrected["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and base260.needs_refresh(corrected, p82),
        "refresh_is_next": base261.challenger(corrected, p82)
        == "refresh-opportunity-projection",
        "phase_aware_policy_preserved": corrected[
            "active_opportunity_projection_refresh_policy"
        ]
        == parent["active_opportunity_projection_refresh_policy"],
        "corrected_conformant": runtime.identity_conforms(corrected),
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY + "-correction-invocation",
        "source_subject_digest": parent["artifact_digest"],
        "pulse": pulse,
        "derived_target": target,
        "derived_path": extension["target_path"],
        "correction": correction,
        "followup_world": followup,
        "checks": gates,
        "subject_disposition": corrected["continuation"]["status"],
        "corrected_subject_digest": corrected["artifact_digest"],
        "fresh_actor_count": 1,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "correction-result.json", result)
    write_json(run / "corrected-subject.json", corrected)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def refresh(run, p82, runtime, parent, fixtures, route, identity):
    if (run / "aggregate.json").exists():
        raise SystemExit("preserve existing OT-0264 aggregate")
    correction = json.loads((run / "correction-result.json").read_text())
    corrected = json.loads((run / "corrected-subject.json").read_text())
    if (
        not correction["checks"]["passed"]
        or correction["corrected_subject_digest"] != corrected["artifact_digest"]
        or not runtime.identity_conforms(corrected)
    ):
        raise SystemExit("serialized correction state invalid")
    final = refresh_projection_only(corrected, p82)
    opportunities = final["active_opportunity_projection"]["opportunities"]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "exact_serialized_correction_parent": correction[
            "source_subject_digest"
        ]
        == parent["artifact_digest"],
        "correction_preceded_refresh": correction["pulse"]["derived_operation"]
        == "outward-correct",
        "zero_refresh_actors": True,
        "one_remaining_opportunity": len(opportunities) == 1,
        "projection_fresh": not base260.needs_refresh(final, p82),
        "phase_aware_policy_preserved": final[
            "active_opportunity_projection_refresh_policy"
        ]
        == parent["active_opportunity_projection_refresh_policy"],
        "next_operation_selection": base261.challenger(final, p82)
        == "expanded-select",
        "wait_wake_and_provider_preserved": final["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and final["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"]
        and final["active_streamed_world_interface"]
        == parent["active_streamed_world_interface"],
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "correction_invocation_receipt_digest": correction["receipt_digest"],
        "corrected_subject_digest": corrected["artifact_digest"],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
        "invocation_count": 2,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--mode", choices=("correct", "refresh"), default="correct")
    args = parser.parse_args()
    repo, _, run, p82, runtime, parent, result263, base, base130 = setup(args)
    fixtures, route, identity, target, extension = preflight(
        repo, run, p82, runtime, parent, result263
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if args.mode == "correct":
        return correct(
            run,
            repo,
            p82,
            runtime,
            parent,
            fixtures,
            base,
            base130,
            target,
            extension,
        )
    return refresh(run, p82, runtime, parent, fixtures, route, identity)


if __name__ == "__main__":
    raise SystemExit(main())
