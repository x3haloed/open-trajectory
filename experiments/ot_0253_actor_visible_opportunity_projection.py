from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0252_symmetric_descriptor_complete_epoch_suffix.py"
BASE_SHA256 = "3684839e10a8e9b6c511cefd8fda3f9e0960715adeaebc9710f971a4fa008c0b"
PARENT_DIGEST = "7965191ae80b56c01bd3acd6e38f8dd07a4be01f6f8d82a75c68ecd98abfe8d3"
OT252_RECEIPT = "76015476165fbb4e6a5c67eb08f01043316d5f4e72ab07dc492a75f67320d4bb"
AUTHORITY = "ot-0253-actor-visible-opportunity-projection"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0252 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0253_frozen_ot0252", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base252 = load_base()
base248 = base252.base248
base244 = base252.base244
authority_base = base252.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def derive(subject):
    epochs = subject.get("actor_authored_environment_epochs", [])
    if not epochs:
        return {"status": "empty", "opportunities": [], "source_errors": []}
    ledger = subject.get("local_frontier_ledger", {}).get("targets", {})
    found = []
    errors = []
    for path, row in sorted(epochs[-1].get("visible_sources", {}).items()):
        try:
            tree = ast.parse(row["source"])
        except (KeyError, SyntaxError, TypeError):
            errors.append(path)
            continue
        for node in tree.body:
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not node.name.startswith("_")
                and node.name not in ledger
            ):
                found.append({"target_path": path, "target_symbol": node.name})
    if errors:
        return {
            "status": "invalid-descriptor",
            "opportunities": [],
            "source_errors": sorted(errors),
        }
    return {
        "status": "active" if found else "saturated",
        "opportunities": sorted(
            found, key=lambda row: (row["target_path"], row["target_symbol"])
        ),
        "source_errors": [],
    }


def fixture_subject(sources=None, ledger=None, prior_sources=None):
    epochs = []
    if prior_sources is not None:
        epochs.append(
            {
                "environment_id": "prior",
                "visible_sources": {
                    path: {"source": source} for path, source in prior_sources.items()
                },
            }
        )
    if sources is not None:
        epochs.append(
            {
                "environment_id": "active",
                "visible_sources": {
                    path: {"source": source} for path, source in sources.items()
                },
            }
        )
    return {
        "actor_authored_environment_epochs": epochs,
        "local_frontier_ledger": {"targets": ledger or {}},
    }


def fixtures():
    one = "def alpha(case):\n    return case\n\ndef _helper(case):\n    return case\n"
    two = "async def beta(case):\n    return case\n"
    return [
        ("no-epoch", fixture_subject(), "empty", []),
        (
            "private-helper-excluded",
            fixture_subject({"world/a.py": one}),
            "active",
            [{"target_path": "world/a.py", "target_symbol": "alpha"}],
        ),
        (
            "completed-excluded",
            fixture_subject({"world/a.py": one}, {"alpha": {"status": "done"}}),
            "saturated",
            [],
        ),
        (
            "two-modules-sorted",
            fixture_subject({"world/b.py": two, "world/a.py": one}),
            "active",
            [
                {"target_path": "world/a.py", "target_symbol": "alpha"},
                {"target_path": "world/b.py", "target_symbol": "beta"},
            ],
        ),
        (
            "async-public",
            fixture_subject({"world/b.py": two}),
            "active",
            [{"target_path": "world/b.py", "target_symbol": "beta"}],
        ),
        (
            "latest-epoch-only",
            fixture_subject(
                {"new/b.py": two},
                prior_sources={"old/a.py": one},
            ),
            "active",
            [{"target_path": "new/b.py", "target_symbol": "beta"}],
        ),
        (
            "malformed-fails-closed",
            fixture_subject({"world/a.py": "def broken("}),
            "invalid-descriptor",
            [],
        ),
        (
            "source-order-invariant",
            fixture_subject({"world/a.py": one, "world/b.py": two}),
            "active",
            [
                {"target_path": "world/a.py", "target_symbol": "alpha"},
                {"target_path": "world/b.py", "target_symbol": "beta"},
            ],
        ),
        (
            "irrelevant-ledger-entry",
            fixture_subject({"world/a.py": one}, {"gamma": {"status": "done"}}),
            "active",
            [{"target_path": "world/a.py", "target_symbol": "alpha"}],
        ),
        (
            "total-saturation",
            fixture_subject(
                {"world/a.py": one, "world/b.py": two},
                {"alpha": {"status": "done"}, "beta": {"status": "done"}},
            ),
            "saturated",
            [],
        ),
    ]


def evaluate():
    rows = []
    for case_id, subject, status, opportunities in fixtures():
        observed = derive(subject)
        passed = (
            observed["status"] == status
            and observed["opportunities"] == opportunities
            and (case_id == "malformed-fails-closed")
            == bool(observed["source_errors"])
        )
        rows.append(
            {
                "case_id": case_id,
                "expected_status": status,
                "expected_opportunities": opportunities,
                "observed": observed,
                "passed": passed,
            }
        )
    return {
        "case_count": len(rows),
        "pass_count": sum(row["passed"] for row in rows),
        "results": rows,
    }


def compile_transition(parent, projection, comparison, p82):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    resolver_source = inspect.getsource(derive)
    body = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "active_epoch_id": parent["actor_authored_environment_epochs"][-1][
            "environment_id"
        ],
        "active_epoch_sources_digest": p82.digest(
            parent["actor_authored_environment_epochs"][-1]["visible_sources"]
        ),
        "ledger_digest": p82.digest(parent["local_frontier_ledger"]),
        "resolver_source": resolver_source,
        "resolver_source_digest": p82.digest(resolver_source),
        "fixture_comparison_digest": p82.digest(comparison),
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
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": "Select one coherent contact from the state-derived active opportunity projection under the content-free pulse.",
    }
    child["unresolved"] = (
        "Test whether the compact state-derived opportunity projection improves "
        "fresh-actor selection from the exact retained position."
    )
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
    run = (args.evidence_root or store / "runs/OT-0253").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0252",
        "open-partial-subject-after-four-suffix-transitions.json",
    )
    result252 = selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0252",
        "symmetric-epoch-suffix-partial-rejection-aggregate.json",
    )
    comparison = evaluate()
    projection = derive(parent)
    incumbent = base244.remaining_epoch(parent)
    successor = compile_transition(parent, projection, comparison, p82)
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
        "ot0252_exact_partial_rejection": result252["observer_disposition"]
        == "rejected"
        and result252["receipt_digest"] == OT252_RECEIPT
        and result252["final_subject_digest"] == PARENT_DIGEST,
        "fixtures_10_of_10": comparison["pass_count"] == 10,
        "projection_matches_promoted_resolver": projection["opportunities"]
        == incumbent,
        "exactly_one_active_opportunity": projection["status"] == "active"
        and len(projection["opportunities"]) == 1,
        "target_not_hardcoded": all(
            row["target_symbol"] not in Path(__file__).read_text()
            for row in projection["opportunities"]
        ),
        "projection_has_no_selection_authority": successor[
            "active_opportunity_projection"
        ]["selection_authority"]
        is False,
        "operational_state_unchanged": successor["fixed_g6_recurrence_driver"]
        == parent["fixed_g6_recurrence_driver"]
        and successor["pending_contact_bearing_continuations"]
        == parent["pending_contact_bearing_continuations"]
        and successor["actor_authored_environment_extensions"]
        == parent["actor_authored_environment_extensions"]
        and successor["actor_authored_environment_epochs"]
        == parent["actor_authored_environment_epochs"]
        and successor["local_frontier_ledger"] == parent["local_frontier_ledger"],
        "successor_open_same_operation": successor["continuation"]["status"]
        == "open"
        and base248.operation_for(successor) == "expanded-select"
        and runtime.identity_conforms(successor),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "comparison": comparison,
        "projection": projection,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": successor["continuation"]["status"]
        if checks["passed"]
        else parent["continuation"]["status"],
        "final_subject_digest": successor["artifact_digest"]
        if checks["passed"]
        else parent["artifact_digest"],
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    if args.preflight_only:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0253 evidence")
    run.mkdir(parents=True)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", successor if checks["passed"] else parent)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
