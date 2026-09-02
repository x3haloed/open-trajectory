from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0261_correction_before_projection_refresh.py"
BASE_SHA256 = "1d56678fc0d40f0bd96972f087d4c2a4bcc407a11f3ac76f0fd1c6ec3a2e5408"
PARENT_DIGEST = "088a362817f08beea60c7f7fed58bdf2a0230ed26fd95c98aa2b09b5d4a6f619"
OT261_RECEIPT = "b57aa581341b5e4bbbcc93434cd26eb43a7c80d5e14a14ab48ec8442592960d3"
AUTHORITY = "ot-0262-registry-free-projected-admission"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0261 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0262_frozen_ot0261", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base261 = load_base()
base260 = base261.base260
base259 = base260.base259
base252 = base259.base252
base248 = base259.base248
base245 = base252.base245
base244 = base252.base244
base242 = base252.base242
authority_base = base261.authority_base
incumbent = base242.structural


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def projected_pairs(subject):
    projection = subject.get("active_opportunity_projection", {})
    return {
        (row.get("target_path"), row.get("target_symbol"))
        for row in projection.get("opportunities", [])
        if isinstance(row, dict)
    }


def challenger(decision, root, subject):
    if (
        not isinstance(decision, dict)
        or set(decision)
        != {"environment_id", "region_rationale", "next_pursuit", "next_contact"}
        or not all(
            isinstance(decision.get(key), str)
            and decision[key].strip()
            and not decision[key].startswith("replace-")
            for key in ("environment_id", "region_rationale", "next_pursuit")
        )
    ):
        return False
    contact = decision.get("next_contact")
    if not isinstance(contact, dict) or set(contact) != base242.CONTACT_CORE:
        return False
    if not all(
        isinstance(contact.get(key), str)
        and contact[key].strip()
        and not contact[key].startswith("replace-")
        for key in ("contact_id", "target_path", "target_symbol", "abi", "stake")
    ):
        return False
    path = Path(contact["target_path"])
    target = contact["target_symbol"]
    pair = (contact["target_path"], target)
    latest = {
        (row["target_path"], row["target_symbol"])
        for row in base244.remaining_epoch(subject)
    }
    cases = contact.get("cases")
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.suffix != ".py"
        or target.startswith("_")
        or pair not in projected_pairs(subject)
        or pair not in latest
        or target in subject["local_frontier_ledger"]["targets"]
        or contact.get("predicates") != base242.PREDICATES
        or not isinstance(cases, list)
        or len(cases) != 4
        or len(
            {
                row.get("case_id")
                for row in cases
                if isinstance(row, dict)
                and isinstance(row.get("case_id"), str)
                and row["case_id"].strip()
            }
        )
        != 4
        or not all(
            isinstance(row, dict)
            and set(row) == {"case_id", "input"}
            and isinstance(row.get("case_id"), str)
            and row["case_id"].strip()
            and isinstance(row.get("input"), dict)
            for row in cases
        )
    ):
        return False
    try:
        fn = getattr(base242.load_module(root / path, "projected_admission_"), target)
    except (OSError, AttributeError, SyntaxError):
        return False
    return callable(fn)


def compile_transition(parent, comparison, p82):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    body = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "heldout_comparison_digest": p82.digest(comparison),
        "inputs": [
            "active-opportunity-projection",
            "latest-epoch-visible-source",
            "latest-epoch-ast-opportunities",
            "exact-ledger",
            "actor-workspace-effects",
            "contact-structure",
        ],
        "world_specific_target_registry": False,
        "projection_authority": False,
        "selection_authority": False,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": "mechanical-source-ledger-workspace-only",
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child["expanded_selection_admission_regime_transitions"] = [
        *child.get("expanded_selection_admission_regime_transitions", []),
        receipt,
    ]
    child["active_expanded_selection_admission_regime"] = receipt
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
    run = (args.evidence_root or store / "runs/OT-0262").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0261",
        "open-subject-with-phase-aware-projection-refresh.json",
    )
    result261 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0261",
        "correction-before-projection-refresh-aggregate.json",
    )
    prior = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0253",
        "open-subject-with-active-opportunity-projection.json",
    )
    fixture = run.parent / "OT-0262-preflight"
    shutil.rmtree(fixture, ignore_errors=True)
    fixture.mkdir(parents=True)
    positive_rows = []
    for label, subject in (("current", parent), ("prior", prior)):
        for path, target in sorted(projected_pairs(subject)):
            decision = base245.fixture_decision(target)
            seed = base252.selection_seed(fixture / f"{label}-{target}", subject, decision)
            old = incumbent(decision, seed, subject["local_frontier_ledger"])
            new = challenger(decision, seed, subject)
            public = base242.execute_public(seed, decision) if new else None
            positive_rows.append(
                {
                    "label": label,
                    "path": path,
                    "target": target,
                    "incumbent": old,
                    "challenger": new,
                    "public": bool(public and public["all_valid"]),
                }
            )
    current_path, current_target = sorted(projected_pairs(parent))[0]
    seed = base252.selection_seed(
        fixture / "anchors", parent, base245.fixture_decision(current_target)
    )
    valid = base245.fixture_decision(current_target)
    completed_target = parent["actor_authored_environment_epochs"][-1]["selected_target"]
    completed = base245.fixture_decision(completed_target)
    private = copy.deepcopy(valid)
    private["next_contact"].update(target_symbol="_greedy")
    mismatch = copy.deepcopy(valid)
    other_path, other_target = sorted(projected_pairs(parent))[1]
    mismatch["next_contact"].update(target_path=other_path, target_symbol=current_target)
    absolute = copy.deepcopy(valid)
    absolute["next_contact"]["target_path"] = "/tmp/world.py"
    traversal = copy.deepcopy(valid)
    traversal["next_contact"]["target_path"] = "../world.py"
    wrong_predicates = copy.deepcopy(valid)
    wrong_predicates["next_contact"]["predicates"] = {}
    three_cases = copy.deepcopy(valid)
    three_cases["next_contact"]["cases"] = three_cases["next_contact"]["cases"][:3]
    duplicate = copy.deepcopy(valid)
    duplicate["next_contact"]["cases"][1]["case_id"] = duplicate["next_contact"][
        "cases"
    ][0]["case_id"]
    missing_function = copy.deepcopy(valid)
    missing_function["next_contact"]["target_symbol"] = "not_present"
    template = base245.template()
    anchors = {
        "completed": not challenger(completed, seed, parent),
        "private": not challenger(private, seed, parent),
        "mismatched_path_symbol": not challenger(mismatch, seed, parent),
        "absolute": not challenger(absolute, seed, parent),
        "traversal": not challenger(traversal, seed, parent),
        "wrong_predicates": not challenger(wrong_predicates, seed, parent),
        "three_cases": not challenger(three_cases, seed, parent),
        "duplicate_cases": not challenger(duplicate, seed, parent),
        "missing_function": not challenger(missing_function, seed, parent),
        "template": not challenger(template, seed, parent),
    }
    malformed_seed = base252.selection_seed(
        fixture / "malformed", parent, base245.fixture_decision(current_target)
    )
    (malformed_seed / current_path).write_text("def broken(:\n")
    anchors["malformed_source"] = not challenger(valid, malformed_seed, parent)
    comparison = {"positive_rows": positive_rows, "anchors": anchors}
    successor = compile_transition(parent, comparison, p82)
    current_rows = [row for row in positive_rows if row["label"] == "current"]
    prior_rows = [row for row in positive_rows if row["label"] == "prior"]
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
        and base261.challenger(parent, p82) == "expanded-select"
        and runtime.identity_conforms(parent),
        "ot0261_exact_promotion": result261["observer_disposition"] == "promoted"
        and result261["receipt_digest"] == OT261_RECEIPT
        and result261["final_subject_digest"] == PARENT_DIGEST,
        "incumbent_rejects_two_current": len(current_rows) == 2
        and all(not row["incumbent"] for row in current_rows),
        "challenger_accepts_all_three_positive": len(positive_rows) == 3
        and len(prior_rows) == 1
        and all(row["challenger"] and row["public"] for row in positive_rows),
        "all_hard_anchors_rejected": all(anchors.values()),
        "operational_state_unchanged": successor["fixed_g6_recurrence_driver"]
        == parent["fixed_g6_recurrence_driver"]
        and successor["local_frontier_ledger"] == parent["local_frontier_ledger"]
        and successor["active_opportunity_projection"]
        == parent["active_opportunity_projection"]
        and successor["active_streamed_world_interface"]
        == parent["active_streamed_world_interface"],
        "regime_has_no_external_choice_authority": all(
            successor["active_expanded_selection_admission_regime"][key] is False
            for key in (
                "world_specific_target_registry",
                "projection_authority",
                "selection_authority",
                "world_authority",
                "scoring_authority",
            )
        ),
        "live_successor_still_selects": base261.challenger(successor, p82)
        == "expanded-select",
        "successor_conforms": runtime.identity_conforms(successor),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "comparison": comparison,
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
        raise SystemExit("preserve existing OT-0262 evidence")
    run.mkdir(parents=True)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", successor)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
