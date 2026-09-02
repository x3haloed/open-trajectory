from __future__ import annotations

import argparse
import json
import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0262_registry_free_projected_admission.py"
BASE_SHA256 = "a9076bcbb202dbfeb8102119d66f476c004a59ae5ffd9bf5b2c0887f18c6e6b1"
PARENT_DIGEST = "be14db5a0b5dd0e2af2ea673e9781235f8a89e90e3215488705227df68db931b"
OT262_RECEIPT = "1620a826497473b075fc85b1fe63353a8f3b9b7d7c0b30acfe7bcd0d31cc1536"
AUTHORITY = "ot-0263-live-registry-free-projected-selection"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0262 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0263_frozen_ot0262", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base262 = load_base()
base261 = base262.base261
base260 = base261.base260
base259 = base260.base259
base252 = base259.base252
base248 = base259.base248
base245 = base252.base245
base244 = base252.base244
base242 = base252.base242
authority_base = base262.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def registry_free_evaluate(seed, workspace, subject):
    try:
        decision = json.loads((workspace / "expanded-selection.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())[
            "immutable"
        ]
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in immutable
        )
        structural = base262.challenger(decision, workspace, subject)
        contact = decision["next_contact"] if structural else None
        target = contact["target_symbol"] if contact else None
        path = contact["target_path"] if contact else None
        public = base242.execute_public(workspace, decision) if structural else None
        semantic = bool(immutable_ok and public and public["all_valid"])
        return {
            "decision": decision,
            "public": public,
            "target": target,
            "path": path,
            "semantic": semantic,
            "immutable_ok": immutable_ok,
            "error_type": None,
        }
    except (OSError, json.JSONDecodeError, KeyError, SyntaxError) as error:
        return {
            "decision": None,
            "public": None,
            "target": None,
            "path": None,
            "semantic": False,
            "immutable_ok": False,
            "error_type": type(error).__name__,
        }


# The promoted regime requires the exact subject, not the legacy ledger-only
# structural signature. Patch the live module adapter, not a target registry.
base252.evaluate_selection_workspace = registry_free_evaluate


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
    run = (args.evidence_root or store / "runs/OT-0263").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0262",
        "open-subject-with-registry-free-projected-admission.json",
    )
    result262 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0262",
        "registry-free-projected-admission-aggregate.json",
    )
    projection = parent["active_opportunity_projection"]
    projected_pairs = {
        (row["target_path"], row["target_symbol"])
        for row in projection["opportunities"]
    }
    eligible_pairs = {
        (row["target_path"], row["target_symbol"])
        for row in base244.remaining_epoch(parent)
    }
    fixture = run.parent / "OT-0263-preflight"
    shutil.rmtree(fixture, ignore_errors=True)
    fixture.mkdir(parents=True)
    rows = {}
    prompts = []
    for path, target in sorted(projected_pairs):
        decision = base245.fixture_decision(target)
        seed = base252.selection_seed(fixture / target, parent, decision)
        prompt = (seed / "README.md").read_text()
        prompts.append(prompt)
        checker = subprocess.run(
            ["python3", "check_selection.py"], cwd=seed, capture_output=True
        )
        evaluated = base252.evaluate_selection_workspace(seed, seed, parent)
        action = {
            "decision": decision,
            "binding": {"binding_digest": "a" * 64, "contact_identity": "b" * 64},
        }
        intermediate = base245.compile_intermediate(parent, action, p82)
        world = base245.sealed_world(
            intermediate, action, p82, fixture / f"world-{target}"
        )
        final = base245.compile_world(intermediate, world, p82)
        envelope = json.loads((seed / "mutation-envelope.json").read_text())
        rows[target] = {
            "path": path,
            "projection_immutable": "active-opportunity-projection.json"
            in envelope["immutable"],
            "checker": checker.returncode == 0,
            "registry_free_semantic": evaluated["semantic"],
            "public": bool(evaluated["public"] and evaluated["public"]["all_valid"]),
            "hidden_matches": world["result"]["matches"],
            "conformant": runtime.identity_conforms(intermediate)
            and runtime.identity_conforms(final),
            "projection_stale": base260.needs_refresh(final, p82),
            "correction_first": base261.challenger(final, p82) == "outward-correct",
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
        "parent_exact_fresh_selection": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and parent["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and not base260.needs_refresh(parent, p82)
        and base261.challenger(parent, p82) == "expanded-select"
        and runtime.identity_conforms(parent),
        "ot0262_exact_promotion": result262["observer_disposition"] == "promoted"
        and result262["receipt_digest"] == OT262_RECEIPT
        and result262["final_subject_digest"] == PARENT_DIGEST,
        "active_registry_free_regime": parent[
            "active_expanded_selection_admission_regime"
        ]["authority"]
        == base262.AUTHORITY
        and parent["active_expanded_selection_admission_regime"][
            "world_specific_target_registry"
        ]
        is False,
        "exact_two_projected_eligible_pairs": len(projected_pairs) == 2
        and projected_pairs == eligible_pairs,
        "prompts_name_no_candidate_or_path": not any(
            token in prompt
            for prompt in prompts
            for pair in projected_pairs
            for token in pair
        ),
        "all_pair_preflights_pass": all(
            row["projection_immutable"]
            and row["checker"]
            and row["registry_free_semantic"]
            and row["public"]
            and row["hidden_matches"] == 2
            and row["conformant"]
            and row["projection_stale"]
            and row["correction_first"]
            for row in rows.values()
        ),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "projected_pairs": [
            {"target_path": path, "target_symbol": target}
            for path, target in sorted(projected_pairs)
        ],
        "rows": rows,
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0263 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    row, final = base248.continue_once(
        runtime, base, base130, repo, p82, run / "pulse-1", parent
    )
    actor = row["actor"]
    world = row["world"]
    selected = (
        actor["decision"]["next_contact"]
        if actor and actor.get("decision") and actor["decision"].get("next_contact")
        else None
    )
    selected_pair = (
        (selected["target_path"], selected["target_symbol"]) if selected else None
    )
    gates = {
        "preflight_passed": checks["passed"],
        "one_content_free_selection_pulse": row["pulse"]["content"] is None
        and row["operation"] == "expanded-select",
        "one_fresh_actor": row["fresh_actor_count"] == 1,
        "fresh_actor_accepted": bool(actor and actor["accepted"]),
        "selected_projected_eligible_pair": selected_pair in projected_pairs,
        "g10_accepted": bool(actor and actor["g10_disposition"]),
        "public_executable": bool(
            actor and actor["public"] and actor["public"]["all_valid"]
        ),
        "independent_2_of_6": bool(
            world and world["result"]["all_valid"] and world["result"]["matches"] == 2
        ),
        "active_epoch_preserved": final["actor_authored_environment_epochs"]
        == parent["actor_authored_environment_epochs"],
        "wait_wake_history_preserved": final["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and final["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"],
        "projection_now_stale": base260.needs_refresh(final, p82),
        "correction_precedes_refresh": base261.challenger(final, p82)
        == "outward-correct",
        "final_open_correct": final["continuation"]["status"] == "open"
        and final["fixed_g6_recurrence_driver"]["phase"] == "correct"
        and runtime.identity_conforms(final),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "pulse_transition": row,
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
