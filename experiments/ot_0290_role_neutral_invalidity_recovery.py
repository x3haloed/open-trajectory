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
BASE_PATH = ROOT / "ot_0289_target_scoped_disclosure_recurrence.py"
BASE_SHA256 = "1a92dfc6b0e7b1d3c5bad3f78aaa7369ca9e3929403e9979574c986de5f8752f"
PARENT_DIGEST = "23cce12c6b6d9330f668c204842f006003c8f8611d1dd59f8916533f046d0dd7"
OT289_REJECTED_RECEIPT = "ea0434d008b5aab685f4060e27ae57cbe457dccc3e6bfb721fb647fe072a948b"
OT285_REJECTED_RECEIPT = "ef57212e0566dbdf40381a123bc3ac39c9c8f9c9c4282e240e15279aef912354"
AUTHORITY = "ot-0290-role-neutral-invalidity-recovery"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0289 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0290_frozen_ot0289", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base289 = load_base()
b = base289.b
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def write_json(path, value):
    base289.write_json(path, value)


def setup(args):
    lineage = b.authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0290").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0289", "open-subject-at-seventh-wait.json"
    )
    rejected289 = selector.load_artifact(
        p82, repo, store, "OT-0289", "rejected-post-invalidity-renewal-invocation.json"
    )
    rejected285 = selector.load_artifact(
        p82, repo, store, "OT-0285", "rejected-tideglass-correction-invocation.json"
    )
    return repo, run, p82, runtime, parent, rejected289, rejected285, core, base130


def valid_invalid_encounter(subject, rejected):
    actor = rejected.get("actor") or {}
    denial = actor.get("audit", {}).get("denial_classification_v2", {})
    return bool(
        rejected.get("source_subject_digest") == subject["artifact_digest"]
        and rejected.get("final_subject_digest") == subject["artifact_digest"]
        and rejected.get("checks", {}).get("passed") is False
        and actor.get("accepted") is False
        and actor.get("g10_disposition") is False
        and rejected.get("world") is None
        and rejected.get("feedback") is None
        and denial.get("classification") == "contained-denied-operation"
        and denial.get("sandbox_violation_retained") is True
        and not denial.get("outside_file_changes")
        and denial.get("protected_path_named") is False
    )


def operational_projection(subject):
    keys = (
        "active_world_stream_wait",
        "world_stream_wait_receipts",
        "world_stream_wait_discharge_receipts",
        "actor_authored_environment_epochs",
        "local_frontier_ledger",
        "active_standing_world_renewal",
        "fixed_g6_recurrence_driver",
    )
    return {key: subject.get(key) for key in keys}


def compile_scar(subject, rejected, p82):
    if not valid_invalid_encounter(subject, rejected):
        return None, None
    operation = rejected["pulse"]["derived_operation"]
    body = {
        "authority": AUTHORITY + "-role-neutral-rejection-scar",
        "source_subject_digest": subject["artifact_digest"],
        "failed_invocation_receipt_digest": rejected["receipt_digest"],
        "attempted_operation": operation,
        "audit_digest": p82.digest(rejected["actor"]["audit"]),
        "classification": "contained-denied-operation",
        "provenance": "unattributed",
        "disposition": "no-content-admitted",
        "world_consequence": "not-opened",
        "next_operation": operation,
        "actor_authority": False,
        "world_authority": False,
        "admission_authority": False,
    }
    scar = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["invalid_encounter_scars"] = [
        *child.get("invalid_encounter_scars", []),
        scar,
    ]
    child["active_invalid_encounter_reopening"] = {
        "authority": AUTHORITY + "-active-reopening",
        "scar_receipt_digest": scar["receipt_digest"],
        "operation": operation,
        "status": "awaiting-recovery",
        "candidate_authority": False,
        "receipt_digest": p82.digest(
            {
                "scar_receipt_digest": scar["receipt_digest"],
                "operation": operation,
                "status": "awaiting-recovery",
            }
        ),
    }
    return p82.seal(child), scar


def derive(subject):
    active = subject.get("active_invalid_encounter_reopening")
    return active["operation"] if active else None


def compile_recovery(subject, actor, p82):
    active = subject["active_invalid_encounter_reopening"]
    evaluation = actor["evaluation"]
    body = {
        "authority": AUTHORITY + "-recovery-receipt",
        "source_subject_digest": subject["artifact_digest"],
        "scar_receipt_digest": active["scar_receipt_digest"],
        "recovered_operation": active["operation"],
        "actor_audit_digest": p82.digest(actor["audit"]),
        "public_package_digest": evaluation["public_package_digest"],
        "full_package_digest": evaluation["full_package_digest"],
        "world_id": evaluation["world_id"],
        "disposition": "recovered-content-external",
        "package_source_retained": False,
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["invalid_encounter_recovery_receipts"] = [
        *child.get("invalid_encounter_recovery_receipts", []),
        receipt,
    ]
    child["active_invalid_encounter_reopening"] = None
    return p82.seal(child), receipt


def invalidity_controls(subject, rejected):
    controls = {}
    mutations = {
        "actor_accepted": ("actor", "accepted", True),
        "g10_accepted": ("actor", "g10_disposition", True),
        "world_present": ("world", None, {"outcome": "success"}),
        "feedback_present": ("feedback", None, {"receipt": "present"}),
        "subject_changed": ("final_subject_digest", None, "f" * 64),
    }
    for name, (path, field, value) in mutations.items():
        row = copy.deepcopy(rejected)
        if path == "actor":
            row[path][field] = value
        else:
            row[path] = value
        controls[name] = not valid_invalid_encounter(subject, row)
    return controls


def preflight(root, p82, runtime, parent, rejected289, rejected285):
    root.mkdir(parents=True, exist_ok=True)
    scarred, scar = compile_scar(parent, rejected289, p82)
    prior_parent = json.loads(
        (REPO / ".evidence/runs/OT-0285/checkpoint-subject.json").read_text()
    )
    prior_qualifies = valid_invalid_encounter(prior_parent, rejected285)
    controls = invalidity_controls(parent, rejected289)
    example = b.base268.evaluate_package(b.base268.EXAMPLE, p82.digest)
    fixture_actor = {
        "audit": {"fixture": "clean"},
        "evaluation": example,
    }
    recovered, receipt = compile_recovery(scarred, fixture_actor, p82)
    scan = b.base267.scan_feed(
        recovered, [example["public_package"]], p82.digest
    )
    scar_corpus = json.dumps(scar, sort_keys=True)
    route, identity = b.base272.base265.floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_seventh_wait": parent["artifact_digest"] == PARENT_DIGEST
        and b.base272.derive(parent, p82) == "wait-provider"
        and len(parent["world_stream_wait_receipts"]) == 7
        and len(parent["world_stream_wait_discharge_receipts"]) == 6
        and runtime.identity_conforms(parent),
        "ot0289_exact_invalidity": rejected289["receipt_digest"]
        == OT289_REJECTED_RECEIPT
        and valid_invalid_encounter(parent, rejected289),
        "ot0285_cross_role_qualifies": rejected285["receipt_digest"]
        == OT285_REJECTED_RECEIPT
        and prior_qualifies,
        "invalidity_controls_reject": all(controls.values()),
        "scar_preserves_operational_state": operational_projection(scarred)
        == operational_projection(parent),
        "scar_excludes_candidate": rejected289["actor"]["audit"]["patch_digest"]
        not in scar_corpus
        and json.dumps(rejected289["actor"]["output"], sort_keys=True)
        not in scar_corpus
        and json.dumps(rejected289["actor"]["package"], sort_keys=True)
        not in scar_corpus,
        "rederives_rejected_operation": derive(scarred) == "renew-world-feed",
        "fixture_recovery_discharges_active": recovered[
            "active_invalid_encounter_reopening"
        ]
        is None
        and receipt["package_source_retained"] is False
        and operational_projection(recovered) == operational_projection(parent),
        "fixture_recovery_scanner_visible": scan["status"] == "world-available",
        "successor_open_conformant": runtime.identity_conforms(recovered)
        and recovered["continuation"]["status"] == "open",
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "rejected_invocation_receipt_digest": rejected289["receipt_digest"],
        "invalidity_controls": controls,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def finalize(run, fixtures, p82, runtime, parent, final, provider):
    rows = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "two_content_free_openings": len(rows) == 2
        and all(row["pulse"]["content"] is None for row in rows),
        "scar_then_provider_recovery": [
            row["pulse"]["derived_operation"] for row in rows
        ]
        == ["assimilate-invalid-encounter", "renew-world-feed"],
        "one_fresh_provider": sum(row["fresh_actor_count"] for row in rows) == 1,
        "provider_promoted": provider["accepted"],
        "active_reopening_discharged": final[
            "active_invalid_encounter_reopening"
        ]
        is None,
        "operational_wait_preserved": operational_projection(final)
        == operational_projection(parent),
        "final_open_conformant": runtime.identity_conforms(final)
        and final["continuation"]["status"] == "open",
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
        "next_world_id": provider["evaluation"]["world_id"],
        "next_world_full_package_digest": provider["evaluation"][
            "full_package_digest"
        ],
        "next_world_public_package_digest": provider["evaluation"][
            "public_package_digest"
        ],
        "fresh_actor_count": 1,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    write_json(run / "next-world-package.json", provider["package"])
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, rejected289, rejected285, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(
            run / "preflight", p82, runtime, parent, rejected289, rejected285
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0290 unavailable")
    results = sorted(run.glob("invocation-*-result.json"))
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0290 invocation")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    index = len(results) + 1
    if index not in {1, 2} or not runtime.identity_conforms(subject):
        raise SystemExit("invalid OT-0290 checkpoint")
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    operation = "assimilate-invalid-encounter" if index == 1 else derive(subject)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = None
    if index == 1:
        final, scar = compile_scar(subject, rejected289, p82)
        checks = {
            "content_free": True,
            "zero_fresh_actors": True,
            "rejection_only": scar["disposition"] == "no-content-admitted",
            "operational_state_exact": operational_projection(final)
            == operational_projection(subject),
            "next_is_provider": derive(final) == "renew-world-feed",
        }
    else:
        workspace_root = (root / "actor").resolve()
        actor = b.run_provider(
            b.base274.context_for(core, base130, runtime, root, repo),
            p82,
            root,
            subject,
        )
        if actor["accepted"]:
            final, recovery = compile_recovery(subject, actor, p82)
        else:
            final, recovery = subject, None
        seed_corpus = "\n".join(
            path.read_text(errors="replace")
            for path in (root / "actor" / "seed").rglob("*")
            if path.is_file()
        )
        scan = (
            b.base267.scan_feed(
                final,
                [actor["evaluation"]["public_package"]],
                p82.digest,
            )
            if actor["accepted"]
            else None
        )
        checks = {
            "content_free": True,
            "workspace_outside_repo": not workspace_root.is_relative_to(repo),
            "actor_accepted": actor["accepted"],
            "g10_accepted": actor["g10_disposition"],
            "exact_one_file_effect": actor["audit"]["exact_changes"]
            and actor["audit"]["changed_paths"] == ["world-package.json"],
            "rejected_candidate_absent": rejected289["actor"]["audit"][
                "patch_digest"
            ]
            not in seed_corpus
            and json.dumps(rejected289["actor"]["package"], sort_keys=True)
            not in seed_corpus,
            "new_valid_package": bool(
                actor["evaluation"].get("valid")
                and len(actor["evaluation"]["targets"]) == 3
                and all(
                    sum(row["matches"] for row in rows) == 2
                    for rows in actor["evaluation"]["rows"].values()
                )
                and not actor["target_collision"]
                and not actor["world_collision"]
            ),
            "scanner_visible": bool(scan and scan["status"] == "world-available"),
            "recovery_bound": bool(
                recovery
                and recovery["scar_receipt_digest"]
                == subject["active_invalid_encounter_reopening"][
                    "scar_receipt_digest"
                ]
            ),
            "operational_wait_preserved": operational_projection(final)
            == operational_projection(parent),
        }
    checks["final_open_conformant"] = final["continuation"]["status"] == "open"
    checks["identity_conformant"] = runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "transition": operation,
        "actor": copy.deepcopy(actor),
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
    return finalize(run, fixtures, p82, runtime, parent, final, actor)


if __name__ == "__main__":
    raise SystemExit(main())
