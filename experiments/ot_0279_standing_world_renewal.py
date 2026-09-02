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
BASE_PATH = ROOT / "ot_0278_asterfall_complete_recurrence.py"
BASE_SHA256 = "c88314bc70fd2d6005568ee42f0446943e4435b2f6fcb6ec36aa529bce9595ff"
PARENT_DIGEST = "645c525e317d885ae7f622b35a400bd37b2fd2d7162c29082f6de389f6b20c55"
OT278_RECEIPT = "ad124a8a2e83bebb05a0701c57a5415b383d90753384bcd0a5dac471fa141d10"
AUTHORITY = "ot-0279-standing-world-renewal"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0278 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0279_frozen_ot0278", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base278 = load_base()
base268 = base278.base268
base267 = base268.base267
base236 = base268.base236
base272 = base278.base272
authority_base = base278.authority_base
SCHEMA = base268.SCHEMA


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector, core, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0279").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(
        p82, repo, store, "OT-0278", "open-subject-at-fifth-standing-feed-wait.json"
    )
    result278 = selector.load_artifact(
        p82, repo, store, "OT-0278", "asterfall-complete-recurrence-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result278, core, base130


def seen_world_ids(subject):
    return sorted(
        {
            row["world_id"]
            for row in subject.get("environment_stream_receipts", [])
            if isinstance(row, dict) and isinstance(row.get("world_id"), str)
        }
    )


def install(subject, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    body = {
        "authority": AUTHORITY + "-policy",
        "source_subject_digest": subject["artifact_digest"],
        "trigger": {
            "subject_operation": "wait-provider",
            "standing_feed_observation": "empty",
        },
        "derived_operation": "renew-world-feed",
        "actor_context": "subject-blind-restricted-world-author",
        "selection_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
        "subject_actor_authority": False,
    }
    policy = {**body, "transition_receipt_digest": p82.digest(body)}
    child["standing_world_renewal_transitions"] = [
        *child.get("standing_world_renewal_transitions", []),
        policy,
    ]
    child["active_standing_world_renewal"] = policy
    return p82.seal(child)


def derive(subject, packages, p82, enabled=True):
    observation = base267.scan_feed(subject, packages, p82.digest)
    if observation["status"] == "world-available":
        return "wake-world"
    policy = subject.get("active_standing_world_renewal") if enabled else None
    if (
        observation["status"] == "empty"
        and base272.derive(subject, p82) == "wait-provider"
        and isinstance(policy, dict)
        and policy.get("derived_operation") == "renew-world-feed"
    ):
        return "renew-world-feed"
    return "wait-provider"


def operational_core(subject):
    ignored = {
        "artifact_digest",
        "active_standing_world_renewal",
        "standing_world_renewal_transitions",
    }
    return {key: value for key, value in subject.items() if key not in ignored}


def preflight(root, p82, runtime, parent, result278):
    root.mkdir(parents=True, exist_ok=True)
    installed = install(parent, p82)
    seed = base268.seed_actor(root / "actor", base268.EXAMPLE)
    checker = subprocess.run(
        ["python3", "check_package.py"], cwd=seed, capture_output=True
    )
    evaluation = base268.evaluate_package(base268.EXAMPLE, p82.digest)
    scan = base267.scan_feed(installed, [evaluation["public_package"]], p82.digest)
    route, identity = base272.base265.floors(installed)
    corpus = "\n".join(
        path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file()
    )
    seen = seen_world_ids(parent)
    ledger = sorted(parent["local_frontier_ledger"]["targets"])
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_fifth_wait": parent["artifact_digest"] == PARENT_DIGEST
        and base272.derive(parent, p82) == "wait-provider"
        and len(parent["world_stream_wait_receipts"]) == 5
        and len(parent["world_stream_wait_discharge_receipts"]) == 4
        and runtime.identity_conforms(parent),
        "ot0278_exact_promotion": result278["receipt_digest"] == OT278_RECEIPT
        and result278["observer_disposition"] == "promoted"
        and result278["final_subject_digest"] == PARENT_DIGEST,
        "renewal_preserves_subject": operational_core(installed)
        == operational_core(parent)
        and installed["active_world_stream_wait"] == parent["active_world_stream_wait"]
        and runtime.identity_conforms(installed),
        "empty_feed_derives_renewal": derive(installed, [], p82)
        == "renew-world-feed",
        "disabled_control_waits": derive(installed, [], p82, enabled=False)
        == "wait-provider",
        "nonempty_feed_wakes": derive(
            installed, [evaluation["public_package"]], p82
        )
        == "wake-world",
        "published_interface_executes": checker.returncode == 0
        and evaluation["valid"]
        and scan["status"] == "world-available",
        "negative_controls_reject": all(
            not row["valid"] for row in base268.negative_controls(p82.digest)
        ),
        "seed_excludes_lineage_state": PARENT_DIGEST not in corpus
        and all(world_id not in corpus for world_id in seen)
        and all(target not in corpus for target in ledger),
        "template_requires_authorship": p82.digest(base268.TEMPLATE)
        != p82.digest(base268.EXAMPLE),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "seen_world_count": len(seen),
        "ledger_target_count": len(ledger),
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result, installed, route, identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result278, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    if retained.exists():
        fixtures = json.loads(retained.read_text())
        installed = install(parent, p82)
        route, identity = base272.base265.floors(installed)
    else:
        fixtures, installed, route, identity = preflight(
            run / "preflight", p82, runtime, parent, result278
        )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0279 unavailable")
    run.mkdir(parents=True, exist_ok=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": None,
        "source_subject_digest": installed["artifact_digest"],
        "derived_operation": derive(installed, [], p82),
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    label = "standing-world-renewal-scout"
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        core.typed.base.make_context(runtime, run / "runtime", repo)
    )
    seed = base268.seed_actor(run / "actor", base268.TEMPLATE)
    write_json(run / "fixture-conformance.json", fixtures)
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, SCHEMA, (seed / "README.md").read_text().strip()
    )
    try:
        package = json.loads((workspace / "world-package.json").read_text())
        evaluation = base268.evaluate_package(package, p82.digest)
        checker = subprocess.run(
            ["python3", "check_package.py"], cwd=workspace, capture_output=True
        )
        public = evaluation.get("public_package") if evaluation["valid"] else None
        scan = base267.scan_feed(installed, [public], p82.digest) if public else None
        target_collision = bool(
            evaluation["valid"]
            and set(evaluation["targets"])
            & set(parent["local_frontier_ledger"]["targets"])
        )
        semantic = bool(
            checker.returncode == 0
            and evaluation["valid"]
            and p82.digest(package)
            not in {p82.digest(base268.TEMPLATE), p82.digest(base268.EXAMPLE)}
            and scan
            and scan["status"] == "world-available"
            and not target_collision
        )
    except (OSError, json.JSONDecodeError, KeyError):
        package, evaluation, scan, target_collision, semantic = (
            None,
            {"valid": False},
            None,
            True,
            False,
        )
    transport = base268.output_valid(output, package)
    audit = context.audit_actor(
        label, output, base_audit, semantic and transport, ["world-package.json"]
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(semantic and transport and base236.g10(normalized))
    if package is not None:
        write_json(run / "world-package.json", package)
    disabled_scan = base267.scan_feed(installed, [], p82.digest)
    actor = {
        "accepted": accepted,
        "output": output,
        "audit": audit,
        "g10_disposition": base236.g10(normalized),
        "evaluation": evaluation,
        "scanner_observation": scan,
        "target_collision": target_collision,
    }
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "content_free_derived_renewal": pulse["content"] is None
        and pulse["derived_operation"] == "renew-world-feed",
        "one_fresh_world_actor": True,
        "world_actor_accepted": accepted,
        "exact_one_file_effect": audit["exact_changes"]
        and audit["changed_paths"] == ["world-package.json"],
        "truthful_g10": audit["truthful"]
        and base236.g10(normalized)
        and normalized["outside"] == [],
        "three_distinct_novel_targets": bool(
            evaluation["valid"]
            and len(evaluation["targets"]) == 3
            and not target_collision
        ),
        "all_three_exact_2_of_6": bool(
            evaluation["valid"]
            and all(
                sum(row["matches"] for row in rows) == 2
                for rows in evaluation["rows"].values()
            )
        ),
        "standing_scanner_admits": bool(
            scan
            and scan["status"] == "world-available"
            and not any(
                scan[key]
                for key in (
                    "selection_authority",
                    "scoring_authority",
                    "admission_authority",
                    "outcome_authority",
                    "actor_authority",
                )
            )
        ),
        "disabled_control_exact_wait": disabled_scan["status"] == "empty"
        and derive(installed, [], p82, enabled=False) == "wait-provider",
        "subject_exact_open_wait": installed["continuation"]["status"] == "open"
        and installed["active_world_stream_wait"]["status"] == "waiting"
        and len(installed["world_stream_wait_receipts"]) == 5
        and runtime.identity_conforms(installed),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "pulse": pulse,
        "actor": actor,
        "disabled_control": {
            "fresh_actor_count": 0,
            "operation": "wait-provider",
            "scanner_observation": disabled_scan,
            "final_subject_digest": installed["artifact_digest"],
        },
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": installed["continuation"]["status"],
        "final_subject_digest": installed["artifact_digest"],
        "world_id": package.get("world_id") if package else None,
        "public_package_digest": evaluation.get("public_package_digest"),
        "full_package_digest": evaluation.get("full_package_digest"),
        "fresh_actor_count": 1,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", installed)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
