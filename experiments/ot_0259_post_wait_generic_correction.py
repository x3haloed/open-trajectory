from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0258_post_wait_actor_world_contact.py"
BASE_SHA256 = "4916fefef1bf330a1410322a71a5c4b6e1aad4f8af87b188d86d4f0ae4ec6861"
PARENT_DIGEST = "315be95bfc7030c8b94b88ae0bdcfdad4ed2d43dd597b4c6b95c5b8904bfd7f6"
OT258_RECEIPT = "0e7ae059bfa7e154c4935aaacdbb40f7cc5cc799f937dddfb7ca08b820799026"
AUTHORITY = "ot-0259-post-wait-generic-correction"
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0258 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0259_frozen_ot0258", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base258 = load_base()
base257 = base258.base257
base256 = base258.base256
base255 = base256.base255
base252 = base255.base252
base250 = base252.base250
base249 = base252.base249
base248 = base252.base248
base244 = base252.base244
base243 = base252.base243
base242 = base252.base242
authority_base = base258.authority_base

# Extend the already-promoted generic provider vocabulary with the exact offered
# world. The correction machinery still derives the live target from state.
base242.CANDIDATES = {**base242.CANDIDATES, **base258.CANDIDATES}
base242.REFERENCE_SOURCES = {
    **base242.REFERENCE_SOURCES,
    **base258.REFERENCE_SOURCES,
}
base242.HIDDEN_CASES = {**base242.HIDDEN_CASES, **base258.HIDDEN_CASES}


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def fixture_correction(root, subject, p82):
    extension, _, _, epoch, target = base248.selected(subject)
    source = base243.corrected_fixture(subject)
    decision = base243.decision_template(subject)
    decision.update(
        rationale="Use the consequence-weighted feasible-set rule exposed by the retained world receipt.",
        next_pursuit="Assimilate the corrected post-wait coordination surface and continue.",
    )
    seed = base249.seed_actor(root / "checker", subject, decision)
    (seed / extension["target_path"]).write_text(source)
    checker = subprocess.run(
        ["python3", "check_correction.py"], cwd=seed, capture_output=True
    )
    public = base243.compare(seed, subject, base243.public_cases(target))
    revised = root / "revised"
    unchanged = root / "unchanged"
    base243.write_environment(revised, subject)
    base243.write_environment(unchanged, subject)
    (revised / extension["target_path"]).write_text(source)
    corrected = base243.compare(revised, subject, base243.followup_cases(target))
    control = base243.compare(unchanged, subject, base243.followup_cases(target))
    binding = {
        "binding_digest": "a" * 64,
        "patched_source": source,
        "patched_source_digest": p82.digest(source),
    }
    followup = {"receipt_digest": "b" * 64, "outcome": "success"}
    prospective = base243.compile_correction(
        subject, {"decision": decision, "binding": binding}, followup, p82
    )
    return {
        "extension": extension,
        "epoch": epoch,
        "target": target,
        "source": source,
        "decision": decision,
        "checker": checker.returncode == 0,
        "public": public,
        "corrected": corrected,
        "control": control,
        "prospective": prospective,
        "prompt": (seed / "README.md").read_text(),
        "immutable": json.loads((seed / "mutation-envelope.json").read_text())[
            "immutable"
        ],
        "seed": seed,
    }


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0259").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0258",
        "open-post-wait-subject-at-coordination-contradiction.json",
    )
    result258 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0258",
        "post-wait-actor-world-contact-aggregate.json",
    )
    fixture_root = run.parent / "OT-0259-preflight"
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    fixture = fixture_correction(fixture_root, parent, p82)
    extension, pending, world, epoch, target = base248.selected(parent)
    prospective = fixture["prospective"]
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
        "parent_exact_open_correct": parent["artifact_digest"] == PARENT_DIGEST
        and parent["fixed_g6_recurrence_driver"]["phase"] == "correct"
        and runtime.identity_conforms(parent),
        "ot0258_exact_promotion": result258["observer_disposition"] == "promoted"
        and result258["receipt_digest"] == OT258_RECEIPT
        and result258["final_subject_digest"] == PARENT_DIGEST,
        "selected_state_aligned": pending["package"]["target_symbol"]
        == world["target_symbol"]
        == epoch["selected_target"]
        == extension["target_symbol"]
        == target
        and world["result"]["matches"] == 2,
        "target_not_hardcoded": target not in Path(__file__).read_text(),
        "prompt_names_no_target_or_path": target not in fixture["prompt"]
        and extension["target_path"] not in fixture["prompt"],
        "descriptor_complete_immutable_paths": all(
            (fixture["seed"] / relative).exists() for relative in fixture["immutable"]
        )
        and str(Path(extension["target_path"]).parent / "__init__.py")
        in fixture["immutable"],
        "target_only_fixture_change": base243.base235.base225.target_only_change(
            fixture["source"], extension["installed_source"], target
        ),
        "checker_and_public_4": fixture["checker"]
        and fixture["public"]["all_valid"]
        and fixture["public"]["matches"] == 4,
        "prospective_6_vs_2": fixture["corrected"]["all_valid"]
        and fixture["corrected"]["matches"] == 6
        and fixture["control"]["all_valid"]
        and fixture["control"]["matches"] == 2,
        "prospective_preserves_wait_wake": prospective["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and prospective["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"],
        "prospective_preserves_extended_provider": prospective[
            "active_streamed_world_interface"
        ]
        == parent["active_streamed_world_interface"],
        "prospective_open_assimilate": prospective["continuation"]["status"]
        == "open"
        and prospective["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and runtime.identity_conforms(prospective),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "derived_target": target,
        "derived_path": extension["target_path"],
        "public": fixture["public"],
        "corrected": fixture["corrected"],
        "unchanged": fixture["control"],
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0259 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, run, repo)
    )
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": parent["artifact_digest"],
        "derived_operation": "outward-correct",
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    correction = base252.run_correction(context, p82, run / "correction", parent)
    followup = (
        base243.evaluate(run / "followup", parent, correction, p82)
        if correction["accepted"]
        else None
    )
    final = (
        base243.compile_correction(parent, correction, followup, p82)
        if followup and followup["promotion_gate"]
        else parent
    )
    if followup:
        write_json(run / "correction-world-receipt.json", followup)
    gates = {
        "preflight_passed": checks["passed"],
        "one_null_correction_pulse": pulse["content"] is None
        and pulse["derived_operation"] == "outward-correct",
        "one_fresh_actor": True,
        "fresh_corrector_accepted": correction["accepted"],
        "g10_accepted": correction["g10_disposition"],
        "public_4_of_4": bool(
            correction["public"] and correction["public"]["matches"] == 4
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
        "selected_extension_corrected": bool(
            followup
            and final["actor_authored_environment_extensions"][-1]["status"]
            == "corrected-and-world-verified"
        ),
        "wait_wake_history_preserved": final["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and final["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"],
        "extended_provider_preserved": final["active_streamed_world_interface"]
        == parent["active_streamed_world_interface"],
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
        "pulse": pulse,
        "derived_target": target,
        "derived_path": extension["target_path"],
        "correction": correction,
        "followup_world": followup,
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
