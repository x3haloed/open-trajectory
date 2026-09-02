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
BASE_PATH = ROOT / "ot_0307_consequence_routed_correction_recurrence.py"
BASE_SHA256 = "b2fdae6f0776c3be5fdefa5bae783a0755a23da7cf0d7a602c9631c30e4ac6a1"
PARENT_DIGEST = "e3c4be5064d880e7bb10afe13b0a907d9798213202d5f7b48a8e9028372a5011"
OT307_RECEIPT = "e9b9b7252a1a3df7259c180363ef1a8a7b515dca1347942ffe027cd2efceb605"
AUTHORITY = "ot-0308-actor-facing-coherence-repair"
REPAIR_OPERATION = "repair-actor-facing-coherence"
INVALID_OPERATION = "reject-actor-facing-incoherence"
PULSE = None


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0307 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0308_frozen_ot0307", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base307 = load_base()
b = base307.b
INHERITED_DERIVE = b.base272.derive


def write_json(path, value):
    base307.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core = lineage.selector_base, lineage.base
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0308").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0307",
        "open-subject-after-consequence-routed-correction.json",
    )
    result307 = selector.load_artifact(
        p82,
        repo,
        store,
        "OT-0307",
        "consequence-routed-correction-aggregate.json",
    )
    return repo, run, p82, runtime, parent, result307


def expected_operation(count):
    return "expanded-select" if count else "expand-environment"


def expected_narrative(count):
    if count == 0:
        return {
            "next_opening": (
                "No projected coordination surface remains; continue through "
                "environment expansion under retained continuation."
            ),
            "unresolved": (
                "No local opportunity remains in the active epoch; continue "
                "through environment expansion."
            ),
        }
    if count == 1:
        return {
            "next_opening": (
                "Select the one remaining projected coordination surface under "
                "registry-free admission."
            ),
            "unresolved": (
                "Use the one refreshed opportunity in the next content-free "
                "selection encounter."
            ),
        }
    return {
        "next_opening": (
            f"Select one of the {count} remaining projected coordination surfaces "
            "under registry-free admission."
        ),
        "unresolved": (
            f"Use one of the {count} refreshed opportunities in the next "
            "content-free selection encounter."
        ),
    }


def coherence_state(subject, p82):
    projection = subject.get("active_opportunity_projection")
    driver = subject.get("fixed_g6_recurrence_driver") or {}
    in_scope = bool(
        isinstance(projection, dict)
        and driver.get("phase") == "assimilate"
        and subject.get("active_streamed_world_offer") is None
        and subject.get("active_world_stream_wait") is None
    )
    if not in_scope:
        return {"in_scope": False, "valid": True, "coherent": True}
    opportunities = projection.get("opportunities")
    count = projection.get("opportunity_count")
    structurally_valid = bool(
        isinstance(opportunities, list)
        and isinstance(count, int)
        and count >= 0
        and count == len(opportunities)
        and projection.get("status") == ("active" if count else "saturated")
    )
    operation = INHERITED_DERIVE(subject, p82)
    machine_valid = structurally_valid and operation == expected_operation(count)
    narrative = expected_narrative(count) if structurally_valid else None
    coherent = bool(
        machine_valid
        and subject.get("continuation", {}).get("next_opening")
        == narrative["next_opening"]
        and subject.get("unresolved") == narrative["unresolved"]
    )
    return {
        "in_scope": True,
        "valid": machine_valid,
        "coherent": coherent,
        "count": count,
        "operation": operation,
        "expected": narrative,
    }


def derive(subject, p82):
    state = coherence_state(subject, p82)
    if state["in_scope"] and not state["valid"]:
        return INVALID_OPERATION
    if state["in_scope"] and not state["coherent"]:
        return REPAIR_OPERATION
    return INHERITED_DERIVE(subject, p82)


b.base272.derive = derive


def repair(subject, p82):
    state = coherence_state(subject, p82)
    if derive(subject, p82) != REPAIR_OPERATION or not state["valid"]:
        raise RuntimeError("subject has no repairable actor-facing incoherence")
    prior = {
        "next_opening": subject["continuation"]["next_opening"],
        "unresolved": subject["unresolved"],
    }
    body = {
        "authority": AUTHORITY + "-repair-receipt",
        "source_subject_digest": subject["artifact_digest"],
        "opportunity_projection_receipt_digest": subject[
            "active_opportunity_projection"
        ]["projection_receipt_digest"],
        "opportunity_count": state["count"],
        "derived_operation": state["operation"],
        "prior_narrative": prior,
        "repaired_narrative": state["expected"],
        "actor_authority": False,
        "selection_authority": False,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["continuation"] = {
        **child["continuation"],
        "next_opening": state["expected"]["next_opening"],
    }
    child["unresolved"] = state["expected"]["unresolved"]
    child["actor_facing_coherence_repairs"] = [
        *child.get("actor_facing_coherence_repairs", []),
        receipt,
    ]
    return p82.seal(child), receipt


def fixture_subject(parent, count, p82, coherent):
    if count not in range(4):
        raise ValueError(count)
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    epoch = child["actor_authored_environment_epochs"][-1]
    targets = sorted(
        (
            symbol,
            path,
        )
        for path, row in epoch["visible_sources"].items()
        for symbol in b.base244.public_symbols(row["source"])
    )
    ledger = copy.deepcopy(child["local_frontier_ledger"])
    exemplar = copy.deepcopy(next(iter(ledger["targets"].values())))
    for symbol, _ in targets:
        ledger["targets"].pop(symbol, None)
    for symbol, path in targets[: len(targets) - count]:
        ledger["targets"][symbol] = {
            **exemplar,
            "target_path": path,
            "target_symbol": symbol,
        }
    child["local_frontier_ledger"] = ledger
    resolved = b.base264.base253.derive(child)
    projection = copy.deepcopy(child["active_opportunity_projection"])
    projection.update(
        **b.base264.base260.descriptor(child, p82),
        status=resolved["status"],
        opportunities=resolved["opportunities"],
        opportunity_count=len(resolved["opportunities"]),
        source_errors=resolved["source_errors"],
    )
    projection.pop("projection_receipt_digest", None)
    projection["projection_receipt_digest"] = p82.digest(projection)
    child["active_opportunity_projection"] = projection
    narrative = expected_narrative(count)
    child["continuation"] = {
        **child["continuation"],
        "next_opening": (
            narrative["next_opening"] if coherent else "Continue from a stale count."
        ),
    }
    child["unresolved"] = (
        narrative["unresolved"] if coherent else "A stale opportunity count remains."
    )
    return p82.seal(child)


def changed_keys(before, after):
    ignored = {"artifact_digest", "actor_facing_coherence_repairs"}
    return sorted(
        key
        for key in set(before) | set(after)
        if key not in ignored and before.get(key) != after.get(key)
    )


def selection_seed_check(root, subject):
    seed = b.base272.base252.selection_seed(
        root, subject, b.base272.base245.template()
    )
    projection = json.loads((seed / "active-opportunity-projection.json").read_text())
    readme = (seed / "README.md").read_text()
    exact = json.loads((seed / "exact-subject.json").read_text())
    position = json.loads((seed / "subject-position.json").read_text())
    expected = expected_narrative(projection["opportunity_count"])
    return {
        "projection_exact": projection == subject["active_opportunity_projection"],
        "readme_cardinality_neutral": "sole remaining" not in readme
        and "two remaining" not in readme,
        "subject_files_repaired": exact["continuation"]["next_opening"]
        == expected["next_opening"]
        and exact["unresolved"] == expected["unresolved"]
        and position["continuation"]["next_opening"]
        == expected["next_opening"],
    }


def preflight(root, p82, runtime, parent, result307):
    root.mkdir(parents=True, exist_ok=True)
    branches = []
    for count in range(4):
        stale = fixture_subject(parent, count, p82, coherent=False)
        coherent = fixture_subject(parent, count, p82, coherent=True)
        repaired, receipt = repair(stale, p82)
        unchanged_control = False
        try:
            repair(coherent, p82)
        except RuntimeError:
            unchanged_control = True
        branches.append(
            {
                "opportunity_count": count,
                "stale_derives_repair": derive(stale, p82) == REPAIR_OPERATION,
                "repair_changes_only_narrative": changed_keys(stale, repaired)
                == ["continuation", "unresolved"],
                "receipt_exact": receipt["source_subject_digest"]
                == stale["artifact_digest"]
                and receipt["opportunity_count"] == count,
                "repair_restores_operation": derive(repaired, p82)
                == expected_operation(count),
                "coherent_control_unchanged": unchanged_control
                and derive(coherent, p82) == expected_operation(count),
                "repaired_conformant": runtime.identity_conforms(repaired),
            }
        )
    malformed = copy.deepcopy(parent)
    malformed.pop("artifact_digest", None)
    malformed["active_opportunity_projection"] = {
        **malformed["active_opportunity_projection"],
        "opportunity_count": 3,
    }
    malformed = p82.seal(malformed)
    parent_repaired, parent_receipt = repair(parent, p82)
    seed = selection_seed_check(root / "next-selection-seed", parent_repaired)
    route, identity = b.base272.base265.floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "exact_ot0307_parent": parent["artifact_digest"] == PARENT_DIGEST
        and result307["receipt_digest"] == OT307_RECEIPT
        and result307["observer_disposition"] == "promoted"
        and INHERITED_DERIVE(parent, p82) == "expanded-select"
        and runtime.identity_conforms(parent),
        "observed_mismatch_reproduced": parent["active_opportunity_projection"][
            "opportunity_count"
        ]
        == 2
        and "sole remaining" in parent["continuation"]["next_opening"]
        and derive(parent, p82) == REPAIR_OPERATION,
        "four_count_branches_pass": len(branches) == 4
        and all(
            all(value for key, value in row.items() if key != "opportunity_count")
            for row in branches
        ),
        "malformed_projection_fails_closed": derive(malformed, p82)
        == INVALID_OPERATION,
        "exact_parent_repair": changed_keys(parent, parent_repaired)
        == ["continuation", "unresolved"]
        and parent_receipt["opportunity_count"] == 2
        and derive(parent_repaired, p82) == "expanded-select"
        and runtime.identity_conforms(parent_repaired),
        "prospective_selection_seed_coherent": all(seed.values()),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0307_receipt_digest": result307["receipt_digest"],
        "branches": branches,
        "selection_seed": seed,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result307 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(run / "preflight", p82, runtime, parent, result307)
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0308 unavailable")
    if derive(parent, p82) != REPAIR_OPERATION:
        raise SystemExit("OT-0308 parent does not derive repair")
    run.mkdir(parents=True, exist_ok=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": parent["artifact_digest"],
        "derived_operation": derive(parent, p82),
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    final, receipt = repair(parent, p82)
    seed = selection_seed_check(run / "prospective-selection-seed", final)
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "one_content_free_zero_actor_opening": pulse["content"] is None,
        "exact_repair_operation": pulse["derived_operation"] == REPAIR_OPERATION,
        "changes_only_narrative": changed_keys(parent, final)
        == ["continuation", "unresolved"],
        "two_opportunities_exact": final["active_opportunity_projection"]
        == parent["active_opportunity_projection"]
        and final["active_opportunity_projection"]["opportunity_count"] == 2,
        "selection_derived_next": derive(final, p82) == "expanded-select",
        "prospective_selection_seed_coherent": all(seed.values()),
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "pulse": pulse,
        "repair_receipt": receipt,
        "selection_seed": seed,
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 0,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "repair-receipt.json", receipt)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
