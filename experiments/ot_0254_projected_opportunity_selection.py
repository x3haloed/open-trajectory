from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0253_actor_visible_opportunity_projection.py"
BASE_SHA256 = "06f9d5d1484cdb90570122887bfe0b246607410440028ba67de3aea345a890ea"
PARENT_DIGEST = "0c3b42bb0af51a6eea8be37505fcbdc63229182e6315455f48f53d860b269e68"
OT253_RECEIPT = "801a69eeedce32ec02ca6227fefd615b027ce780c3f7673a0f8828a80ba01115"
AUTHORITY = "ot-0254-projected-opportunity-selection"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0253 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0254_frozen_ot0253", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base253 = load_base()
base252 = base253.base252
base250 = base252.base250
base248 = base252.base248
base245 = base252.base245
base244 = base252.base244
base242 = base252.base242
authority_base = base253.authority_base
base_selection_seed = base252.selection_seed


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def projected_seed(root, subject, decision):
    seed = base_selection_seed(root, subject, decision)
    projection = subject["active_opportunity_projection"]
    write_json(seed / "active-opportunity-projection.json", projection)
    envelope_path = seed / "mutation-envelope.json"
    envelope = json.loads(envelope_path.read_text())
    envelope["immutable"] = [
        *[
            path
            for path in envelope["immutable"]
            if path != "mutation-envelope.json" and path != "README.md"
        ],
        "active-opportunity-projection.json",
        "mutation-envelope.json",
        "README.md",
    ]
    write_json(envelope_path, envelope)
    (seed / "README.md").write_text(
        "Continue from the exact subject position under the content-free "
        "expanded-selection pulse. active-opportunity-projection.json is a "
        "state-derived index with no selection, world, scoring, admission, or "
        "mutation authority. Verify its opportunity against the retained source "
        "and ledger, then bind one coherent eligible contact if it is real. No "
        "task or target is assigned; do not reopen a completed contact or invent "
        "one merely to avoid stopping. Edit only expanded-selection.json, run "
        "python3 check_selection.py, and inspect the exact diff. Hidden "
        "consequence is unavailable.\n"
    )
    return seed


base252.selection_seed = projected_seed
base245.seed_actor = projected_seed
base245.run_actor = base252.run_selection


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
    run = (args.evidence_root or store / "runs/OT-0254").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0253",
        "open-subject-with-active-opportunity-projection.json",
    )
    result253 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0253",
        "actor-visible-opportunity-projection-aggregate.json",
    )
    result252 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0252",
        "symmetric-epoch-suffix-partial-rejection-aggregate.json",
    )
    projection = parent["active_opportunity_projection"]
    opportunity = projection["opportunities"][0]
    target = opportunity["target_symbol"]
    path = opportunity["target_path"]
    baseline = result252["transitions"][-1]
    fixture = run.parent / "OT-0254-preflight"
    if fixture.exists():
        import shutil

        shutil.rmtree(fixture)
    decision = base245.fixture_decision(target)
    seed = projected_seed(fixture, parent, decision)
    prompt = (seed / "README.md").read_text()
    checker = subprocess.run(
        ["python3", "check_selection.py"], cwd=seed, capture_output=True
    )
    evaluated = base252.evaluate_selection_workspace(seed, seed, parent)
    action = {
        "decision": decision,
        "binding": {"binding_digest": "a" * 64, "contact_identity": "b" * 64},
    }
    intermediate = base245.compile_intermediate(parent, action, p82)
    world = base245.sealed_world(intermediate, action, p82, fixture / "world")
    prospective = base245.compile_world(intermediate, world, p82)
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
        "parent_exact_open_selection": parent["artifact_digest"] == PARENT_DIGEST
        and parent["fixed_g6_recurrence_driver"]["phase"] == "assimilate"
        and base248.operation_for(parent) == "expanded-select"
        and runtime.identity_conforms(parent),
        "ot0253_exact_promotion": result253["observer_disposition"] == "promoted"
        and result253["receipt_digest"] == OT253_RECEIPT
        and result253["final_subject_digest"] == PARENT_DIGEST,
        "matched_baseline_nonmove": baseline["source_subject_digest"]
        == projection["source_subject_digest"]
        and baseline["operation"] == "expanded-select"
        and not baseline["actor"]["accepted"]
        and baseline["actor"]["audit"]["changed_paths"] == []
        and baseline["actor"]["public"] is None,
        "projection_exact_one_non_authoritative": projection["status"] == "active"
        and projection["opportunity_count"] == 1
        and all(
            projection[key] is False
            for key in (
                "selection_authority",
                "world_authority",
                "scoring_authority",
                "admission_authority",
            )
        ),
        "prompt_names_no_target_or_path": target not in prompt and path not in prompt,
        "projection_immutable": "active-opportunity-projection.json"
        in json.loads((seed / "mutation-envelope.json").read_text())["immutable"],
        "fixture_checker_and_public_pass": checker.returncode == 0
        and evaluated["semantic"]
        and evaluated["public"]["all_valid"],
        "fixture_hidden_2_of_6": world["result"]["all_valid"]
        and world["result"]["matches"] == 2,
        "prospective_open_correct": prospective["continuation"]["status"] == "open"
        and prospective["fixed_g6_recurrence_driver"]["phase"] == "correct"
        and runtime.identity_conforms(prospective),
        "target_not_hardcoded": target not in Path(__file__).read_text(),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "matched_baseline": {
            "source_subject_digest": baseline["source_subject_digest"],
            "actor_accepted": baseline["actor"]["accepted"],
            "changed_paths": baseline["actor"]["audit"]["changed_paths"],
            "public": baseline["actor"]["public"],
        },
        "projection_receipt_digest": projection["projection_receipt_digest"],
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0254 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    row, final = base248.continue_once(
        runtime, base, base130, repo, p82, run / "pulse-1", parent
    )
    actor = row["actor"]
    hidden = row["world"]
    selected = (
        actor["decision"]["next_contact"] if actor and actor.get("decision") else None
    )
    gates = {
        "preflight_passed": checks["passed"],
        "one_content_free_pulse": row["pulse"]["content"] is None
        and row["operation"] == "expanded-select",
        "one_fresh_actor": row["fresh_actor_count"] == 1,
        "fresh_actor_accepted": bool(actor and actor["accepted"]),
        "selected_exact_projection_pair": bool(
            selected
            and selected["target_symbol"] == target
            and selected["target_path"] == path
        ),
        "g10_accepted": bool(actor and actor["g10_disposition"]),
        "public_executable": bool(
            actor and actor["public"] and actor["public"]["all_valid"]
        ),
        "independent_2_of_6": bool(
            hidden
            and hidden["result"]["all_valid"]
            and hidden["result"]["matches"] == 2
        ),
        "projection_remained_non_authoritative": all(
            final["active_opportunity_projection"][key] is False
            for key in (
                "selection_authority",
                "world_authority",
                "scoring_authority",
                "admission_authority",
            )
        ),
        "prior_epoch_preserved": final["actor_authored_environment_epochs"][0]
        == parent["actor_authored_environment_epochs"][0],
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
        "matched_baseline": fixtures["matched_baseline"],
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
