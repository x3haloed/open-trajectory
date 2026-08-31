from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0088_unseen_pursuit_selection.py"
BASE_SHA256 = "65a9cb562fd0d1f95166a4012c2a758b04aa28e902a4ab7fca1553024fd9dce1"
SUCCESSOR_KEYS = {
    "contact_made",
    "continuation_after_contact",
    "next_opening",
    "surrender_condition",
    "unresolved",
}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0088 inherited apparatus identity changed")
    name = "ot0089_frozen_ot0088"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()

# Re-export the frozen world and comparison surface for conformance tests.
PARENT_DIGEST = base.PARENT_DIGEST
INHERITED_OPENING = base.INHERITED_OPENING
TARGETS = base.TARGETS
ALIGNED_TARGET = base.ALIGNED_TARGET
ORDERS = base.ORDERS
SAMPLES_PER_CONDITION = base.SAMPLES_PER_CONDITION
MIN_ORACLE_FRACTION = base.MIN_ORACLE_FRACTION
PLACEHOLDER = base.PLACEHOLDER
load_prior = base.load_prior
load_parent = base.load_parent
active_projection = base.active_projection
erased_projection = base.erased_projection
projection_conformance = base.projection_conformance
fisher_enrichment = base.fisher_enrichment


def successor_template() -> dict[str, str]:
    return {key: PLACEHOLDER for key in SUCCESSOR_KEYS}


def successor_contract() -> dict[str, Any]:
    return {
        "exact_keys": sorted(SUCCESSOR_KEYS),
        "lifecycle_authority": "The harness derives canonical open only after hidden admission; do not add status.",
        "instruction": "Replace every __REPLACE__ value with one actionable continuation and falsifiable surrender condition grounded in contact.",
    }


def valid_successor(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == SUCCESSOR_KEYS
        and all(
            isinstance(value[key], str)
            and value[key].strip()
            and PLACEHOLDER not in value[key]
            and len(value[key]) <= 3000
            for key in SUCCESSOR_KEYS
        )
    )


# The inherited seed and implementation functions resolve these names in the
# OT-0088 module. Replace only the frozen carrier boundary, not world behavior.
base.SUCCESSOR_KEYS = SUCCESSOR_KEYS
base.successor_template = successor_template
base.successor_contract = successor_contract
base.valid_successor = valid_successor


def representative_successor() -> dict[str, str]:
    return {
        "contact_made": "One selected policy improved under public contact.",
        "continuation_after_contact": "Seek the next disconfirming boundary case.",
        "next_opening": "inspect the next unresolved transfer boundary",
        "surrender_condition": "Stop if later world contact contradicts the retained policy.",
        "unresolved": "Transfer remains bounded to one world contact.",
    }


def fixture_conformance(prior82, parent: dict[str, Any], root: Path) -> dict[str, Any]:
    result = base.fixture_conformance(prior82, parent, root)
    representative = representative_successor()
    with_status = {**representative, "status": "open"}
    missing = dict(representative)
    missing.pop("unresolved")
    result["successor_seed_rejected"] = not valid_successor(successor_template())
    result["successor_representative_passed"] = valid_successor(representative)
    result["actor_lifecycle_rejected"] = not valid_successor(with_status)
    result["missing_substance_rejected"] = not valid_successor(missing)
    required = (
        "complete_source",
        "six_orders",
        "all_observations_passed",
        "equal_public_regret",
        "all_reference_gates_passed",
        "choice_seed_rejected",
        "choice_representative_passed",
        "successor_seed_rejected",
        "successor_representative_passed",
        "actor_lifecycle_rejected",
        "missing_substance_rejected",
    )
    result["passed"] = all(result[key] for key in required) and result["projection_conformance"]["passed"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0089").resolve()
    prior87 = load_prior(repo)
    prior86 = prior87.load_prior(repo)
    prior85 = prior86.load_prior(repo)
    prior84 = prior85.load_prior(repo)
    prior83 = prior84.load_prior(repo)
    prior82 = prior83.load_prior(repo)
    runtime = prior82.load_runtime(repo, store)
    parent = load_parent(prior82, repo, store)
    if (
        runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"]
        or not runtime.identity_conforms(parent)
        or parent["artifact_digest"] != PARENT_DIGEST
        or parent["continuation"]["next_opening"] != INHERITED_OPENING
    ):
        raise SystemExit("wrong OT-0087 open parent")
    if args.preflight_only:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_conformance(prior82, parent, Path(directory))
        result = {
            "parent_digest": parent["artifact_digest"],
            "inherited_ot0088_sha256": BASE_SHA256,
            "fixture_conformance": fixtures,
            "fisher_gate_examples": {
                "five_vs_one": fisher_enrichment(5, 1),
                "six_vs_one": fisher_enrichment(6, 1),
            },
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] and fisher_enrichment(5, 1) <= 0.05 else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0089 evidence")
    run.mkdir(parents=True)
    fixtures = fixture_conformance(prior82, parent, run / "fixture-conformance")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    active = active_projection(parent)
    erased = erased_projection(prior82, parent)
    (run / "bound-projections.json").write_text(
        json.dumps(
            {
                "active": {"digest": prior82.digest(active)},
                "erased": {"digest": prior82.digest(erased)},
                "conformance": fixtures["projection_conformance"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    context = runtime.Context(run, repo)
    started = time.time()
    routes = {"active": [], "erased": []}
    primary_route = base.run_route(prior82, context, run, "route-active-01", "active", active, ORDERS[0])
    routes["active"].append(primary_route)
    primary_impl = base.run_implementation(prior82, context, run, "implementation-active-primary", primary_route) if primary_route["binding"] else None
    current, promoted = parent, None
    if primary_impl and primary_impl["audit"]["conformant"] and primary_impl["binding"] and primary_impl["world"]["developmentally_admitted"]:
        current, promoted = base.promote(prior82, parent, primary_route, primary_impl)
    operational_passed = bool(
        promoted
        and runtime.identity_conforms(current)
        and current["runtime"] == "sounding"
        and current["continuation"]["status"] == "open"
        and current["continuation"]["next_opening"] == primary_impl["binding"]["successor_opening"]["next_opening"]
        and len(current["tool_world_capabilities"]) == len(parent["tool_world_capabilities"]) + 1
    )
    erased_impl = None
    if operational_passed:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        first_erased = base.run_route(prior82, context, run, "route-erased-01", "erased", erased, ORDERS[0])
        routes["erased"].append(first_erased)
        erased_impl = base.run_implementation(prior82, context, run, "implementation-erased-primary", first_erased) if first_erased["binding"] else None
        for index in range(1, SAMPLES_PER_CONDITION):
            pair_number = index + 1
            sequence = ("erased", "active") if pair_number % 2 == 0 else ("active", "erased")
            for condition in sequence:
                projection = active if condition == "active" else erased
                label = f"route-{condition}-{index + 1:02d}"
                routes[condition].append(base.run_route(prior82, context, run, label, condition, projection, ORDERS[index]))
    route_conformant = all(
        len(routes[condition]) == SAMPLES_PER_CONDITION
        and all(row["audit"]["conformant"] and row["binding"] for row in routes[condition])
        for condition in base.CONDITIONS
    )
    active_targets = [row["binding"]["choice"]["chosen_target_path"] for row in routes["active"] if row["binding"]]
    erased_targets = [row["binding"]["choice"]["chosen_target_path"] for row in routes["erased"] if row["binding"]]
    active_reserve = active_targets.count(ALIGNED_TARGET)
    erased_reserve = erased_targets.count(ALIGNED_TARGET)
    fisher_p = fisher_enrichment(active_reserve, erased_reserve) if route_conformant else 1.0
    erased_admitted = bool(erased_impl and erased_impl["audit"]["conformant"] and erased_impl["binding"] and erased_impl["world"]["developmentally_admitted"])
    causal_passed = bool(
        operational_passed
        and route_conformant
        and active_reserve >= 5
        and erased_reserve <= 1
        and fisher_p <= 0.05
        and erased_admitted
        and erased_targets[0] != ALIGNED_TARGET
    )
    observer = "promoted" if operational_passed and causal_passed else "conditional" if operational_passed else "rejected"
    result = {
        "authority": "ot-0089-derived-liveness-unseen-world-pursuit-selection-driver",
        "source_subject_digest": parent["artifact_digest"],
        "inherited_ot0088_sha256": BASE_SHA256,
        "fixture_conformance": fixtures,
        "projection_digests": {"active": prior82.digest(active), "erased": prior82.digest(erased)},
        "routes": {condition: [prior82.compact(row) for row in routes[condition]] for condition in base.CONDITIONS},
        "active_targets": active_targets,
        "erased_targets": erased_targets,
        "primary_implementation": prior82.compact(primary_impl) if primary_impl else None,
        "erased_implementation": prior82.compact(erased_impl) if erased_impl else None,
        "promotion_receipt": promoted,
        "operational_transition_passed": operational_passed,
        "derived_liveness": bool(operational_passed and current["continuation"]["status"] == "open"),
        "route_conformant": route_conformant,
        "active_reserve_count": active_reserve,
        "erased_reserve_count": erased_reserve,
        "fisher_one_sided_p": fisher_p,
        "pursuit_content_causal_passed": causal_passed,
        "observer_disposition": observer,
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = prior82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
