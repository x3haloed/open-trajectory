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
BASE_PATH = ROOT / "ot_0285_current_package_isolation_second_cycle.py"
BASE_SHA256 = "e879f01be4635287a30b6a4ae397a3ec9c8d2b8483b861ca46a451539f6ef9e2"
PARENT_DIGEST = "3e0268dad1b734f50d8ec2970ee1af0c1d4e52f8b1872b6a994f44e50449df86"
REJECTED_RECEIPT = "ef57212e0566dbdf40381a123bc3ac39c9c8f9c9c4282e240e15279aef912354"
AUTHORITY = "ot-0286-invalid-encounter-scar-reopening"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0285 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0286_frozen_ot0285", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base285 = load_base()
base284 = base285.base284
b = base284.b
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def write_json(path, value):
    base284.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0286").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0285", "open-subject-at-tideglass-contradiction.json"
    )
    rejected = selector.load_artifact(
        p82, repo, store, "OT-0285", "rejected-tideglass-correction-invocation.json"
    )
    package = selector.load_artifact(
        p82, repo, store, "OT-0283", "subject-blind-tideglass-world-package.json"
    )
    result280 = selector.load_artifact(
        p82, repo, store, "OT-0280", "import-stable-world-evaluator-aggregate.json"
    )
    return repo, run, p82, runtime, parent, rejected, package, result280, core, base130


def valid_invalid_encounter(parent, rejected):
    denial = rejected.get("actor", {}).get("audit", {}).get(
        "denial_classification_v2", {}
    )
    return bool(
        rejected.get("receipt_digest") == REJECTED_RECEIPT
        and rejected.get("source_subject_digest") == parent["artifact_digest"]
        and rejected.get("final_subject_digest") == parent["artifact_digest"]
        and rejected.get("transition") == "rejected"
        and rejected.get("actor", {}).get("accepted") is False
        and rejected.get("actor", {}).get("g10_disposition") is False
        and rejected.get("world") is None
        and rejected.get("feedback") is None
        and denial.get("classification") == "contained-denied-operation"
        and denial.get("sandbox_violation_retained") is True
        and not denial.get("outside_file_changes")
        and denial.get("protected_path_named") is False
    )


def compile_scar(parent, rejected, p82):
    if not valid_invalid_encounter(parent, rejected):
        return None, None
    denial = rejected["actor"]["audit"]["denial_classification_v2"]
    body = {
        "authority": AUTHORITY + "-rejection-scar",
        "source_subject_digest": parent["artifact_digest"],
        "failed_invocation_receipt_digest": rejected["receipt_digest"],
        "attempted_operation": rejected["pulse"]["derived_operation"],
        "audit_digest": p82.digest(rejected["actor"]["audit"]),
        "classification": denial["classification"],
        "provenance": "unknown",
        "disposition": "no-content-admitted",
        "world_consequence": "not-opened",
        "next_operation": "outward-correct",
        "actor_authority": False,
        "world_authority": False,
        "admission_authority": False,
    }
    scar = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["active_invalid_encounter_reopening_policy"] = {
        "authority": AUTHORITY + "-policy",
        "trigger": "valid-invalid-encounter-receipt",
        "invalid_content_authority": False,
        "successor_operation": "preserve-current-operation",
        "policy_receipt_digest": p82.digest(
            {
                "source_subject_digest": parent["artifact_digest"],
                "scar_receipt_digest": scar["receipt_digest"],
            }
        ),
    }
    child["invalid_encounter_scars"] = [
        *child.get("invalid_encounter_scars", []),
        scar,
    ]
    return p82.seal(child), scar


def operational_projection(subject):
    keys = (
        "active_correction",
        "active_correction_disclosure",
        "active_outward_contact",
        "active_outward_world_receipt",
        "actor_authored_environment_epochs",
        "local_frontier_ledger",
        "active_standing_world_renewal",
        "fixed_g6_recurrence_driver",
    )
    return {key: subject.get(key) for key in keys}


def prospective_controls(parent, rejected):
    controls = {}
    mutations = {
        "actor_accepted": ("actor", "accepted", True),
        "g10_accepted": ("actor", "g10_disposition", True),
        "world_present": ("world", None, {"outcome": "success"}),
        "subject_changed": ("final_subject_digest", None, "f" * 64),
        "sandbox_absent": (
            "actor.audit.denial_classification_v2",
            "sandbox_violation_retained",
            False,
        ),
    }
    for name, (path, field, value) in mutations.items():
        row = copy.deepcopy(rejected)
        if path == "actor":
            row[path][field] = value
        elif path == "world" or path == "final_subject_digest":
            row[path] = value
        else:
            row["actor"]["audit"]["denial_classification_v2"][field] = value
        controls[name] = not valid_invalid_encounter(parent, row)
    return controls


def preflight(root, p82, runtime, parent, rejected, package, result280):
    root.mkdir(parents=True, exist_ok=True)
    successor, scar = compile_scar(parent, rejected, p82)
    controls = prospective_controls(parent, rejected)
    correction_branches = [
        b.correction_variant(successor, depth, package, result280, p82, runtime)[1]
        for depth in range(3)
    ]
    scar_corpus = json.dumps(scar, sort_keys=True)
    candidate = rejected["actor"]
    route, identity = b.base272.base265.floors(successor)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_unresolved": parent["artifact_digest"] == PARENT_DIGEST
        and b.base272.derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "rejection_exact_valid": valid_invalid_encounter(parent, rejected),
        "invalidity_controls_reject": all(controls.values()),
        "operational_state_exact": operational_projection(successor)
        == operational_projection(parent),
        "scar_rejection_only": scar["disposition"] == "no-content-admitted"
        and scar["world_consequence"] == "not-opened"
        and candidate["audit"]["patch_digest"] not in scar_corpus
        and json.dumps(candidate["output"], sort_keys=True) not in scar_corpus
        and json.dumps(candidate.get("binding"), sort_keys=True) not in scar_corpus,
        "reopens_same_operation": b.base272.derive(successor, p82)
        == "outward-correct",
        "three_correction_branches_pass": all(
            row["feedback_passed"]
            and row["success_public"]
            and row["success_6_2"]
            and row["conformant"]
            and row["routes_refresh"]
            for row in correction_branches
        ),
        "successor_open_conformant": successor["continuation"]["status"]
        == "open"
        and runtime.identity_conforms(successor),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "rejected_invocation_receipt_digest": rejected["receipt_digest"],
        "invalidity_controls": controls,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    write_json(root / "prospective-scarred-subject.json", successor)
    return result


def finalize(run, fixtures, p82, runtime, parent, final):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    correction = rows[-1]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "two_content_free_openings": len(rows) == 2
        and all(row["pulse"]["content"] is None for row in rows),
        "scar_then_correction": [row["pulse"]["derived_operation"] for row in rows]
        == ["assimilate-invalid-encounter", "outward-correct"],
        "one_fresh_recovery_actor": sum(row["fresh_actor_count"] for row in rows)
        == 1,
        "independent_consequence_reached": correction["world"] is not None
        and correction["transition"]
        in {"success-to-refresh", "unresolved-to-more-correction"},
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
    }
    gates["passed"] = all(gates.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "invocation_receipt_digests": [row["receipt_digest"] for row in rows],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "recovery_transition": correction["transition"],
        "fresh_actor_count": 1,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, rejected, package, result280, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(run / "preflight", p82, runtime, parent, rejected, package, result280)
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0286 unavailable")
    results = sorted(run.glob("invocation-*-result.json"))
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0286 invocation")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index not in {1, 2} or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0286 checkpoint")
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    operation = "assimilate-invalid-encounter" if index == 1 else b.base272.derive(subject, p82)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = world = feedback = None
    transition = operation
    if index == 1:
        final, scar = compile_scar(subject, rejected, p82)
        checks = {
            "content_free": True,
            "zero_fresh_actors": True,
            "rejection_only": scar["disposition"] == "no-content-admitted",
            "operational_state_exact": operational_projection(final)
            == operational_projection(subject),
            "next_is_correction": b.base272.derive(final, p82)
            == "outward-correct",
        }
    else:
        _, actor, world, feedback, final, transition = b.base274.run_correction(
            b.base274.context_for(core, base130, runtime, root, repo),
            p82,
            root,
            subject,
            package,
            result280,
        )
        seed_corpus = "\n".join(
            path.read_text(errors="replace")
            for path in (root / "actor" / "seed").rglob("*")
            if path.is_file()
        )
        checks = {
            "content_free": True,
            "actor_accepted": actor["accepted"],
            "g10_accepted": actor["g10_disposition"],
            "rejected_candidate_absent": rejected["actor"]["audit"]["patch_digest"]
            not in seed_corpus
            and json.dumps(rejected["actor"]["output"], sort_keys=True)
            not in seed_corpus,
            "independent_consequence": world is not None,
            "consequence_routes": transition
            in {"success-to-refresh", "unresolved-to-more-correction"},
        }
    checks["final_open_conformant"] = final["continuation"]["status"] == "open"
    checks["identity_conformant"] = runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": transition,
        "actor": actor,
        "world": world,
        "feedback": feedback,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1 if actor else 0,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if index == 1:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return finalize(run, fixtures, p82, runtime, parent, final)


if __name__ == "__main__":
    raise SystemExit(main())
