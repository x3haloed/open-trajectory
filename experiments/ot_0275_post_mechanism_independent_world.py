from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0268_independent_world_package.py"
BASE_SHA256 = "5f56b2836f779f1bcdcef8b15f11cb751edb369dae094ecbb3cdc6ca88244f41"
PARENT_DIGEST = "ee66f4df4d9970e1c689e16bcabf1d3e6d47e87afd9f2f051298118cc4c1aacc"
OT274_RECEIPT = "9303ada05ca0b1a85302e7ba6025360ce059a122b86677919c7b4a578721d66b"
AUTHORITY = "ot-0275-post-mechanism-independent-world"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0268 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0275_frozen_ot0268", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base268 = load_base()
base267 = base268.base267
base265 = base268.base265
base236 = base268.base236
authority_base = base268.authority_base
SCHEMA = base268.SCHEMA


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0275").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0274", "open-subject-at-fourth-standing-feed-wait.json"
    )
    result274 = selector_base.load_artifact(
        p82, repo, store, "OT-0274", "world-routed-correction-recurrence-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result274, base, base130


def seen_world_ids(subject):
    return sorted(
        {
            row["world_id"]
            for row in subject.get("environment_stream_receipts", [])
            if isinstance(row, dict) and isinstance(row.get("world_id"), str)
        }
    )


def preflight(root, p82, runtime, parent, result274):
    root.mkdir(parents=True, exist_ok=True)
    seed = base268.seed_actor(root / "actor", base268.EXAMPLE)
    checker = subprocess.run(
        ["python3", "check_package.py"], cwd=seed, capture_output=True
    )
    evaluation = base268.evaluate_package(base268.EXAMPLE, p82.digest)
    scan = base267.scan_feed(parent, [evaluation["public_package"]], p82.digest)
    route, identity = base265.floors(parent)
    corpus = "\n".join(
        path.read_text(errors="replace")
        for path in seed.rglob("*")
        if path.is_file()
    )
    seen = seen_world_ids(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_fourth_wait": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and parent["active_world_stream_wait"]["status"] == "waiting"
        and len(parent["world_stream_wait_receipts"]) == 4
        and runtime.identity_conforms(parent),
        "ot0274_exact_promotion": result274["receipt_digest"] == OT274_RECEIPT
        and result274["observer_disposition"] == "promoted"
        and result274["final_subject_digest"] == PARENT_DIGEST,
        "published_interface_executes": checker.returncode == 0
        and evaluation["valid"]
        and scan["status"] == "world-available",
        "seven_negative_controls_reject": all(
            not row["valid"] for row in base268.negative_controls(p82.digest)
        ),
        "seed_excludes_subject_and_prior_worlds": PARENT_DIGEST not in corpus
        and all(world_id not in corpus for world_id in seen),
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
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result, route, identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result274, base, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    if retained.exists():
        fixtures = json.loads(retained.read_text())
        route, identity = base265.floors(parent)
    else:
        fixtures, route, identity = preflight(
            run / "preflight", p82, runtime, parent, result274
        )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists() and (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0275 evidence")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    run.mkdir(parents=True, exist_ok=True)
    label = "post-mechanism-independent-world-author"
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, run / "runtime", repo)
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
        scan = base267.scan_feed(parent, [public], p82.digest) if public else None
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
            and scan["available_world"]["world_id"] == package["world_id"]
            and not target_collision
        )
    except (OSError, json.JSONDecodeError, KeyError):
        package, evaluation, checker, scan, target_collision, semantic = (
            None,
            {"valid": False},
            None,
            None,
            True,
            False,
        )
    transport = base268.output_valid(output, package)
    audit = context.audit_actor(
        label,
        output,
        base_audit,
        semantic and transport,
        ["world-package.json"],
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(semantic and transport and base236.g10(normalized))
    if package is not None:
        write_json(run / "world-package.json", package)
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
        "subject_exact_open_wait": parent["artifact_digest"] == PARENT_DIGEST
        and parent["active_world_stream_wait"]["status"] == "waiting"
        and runtime.identity_conforms(parent),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "actor": actor,
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": parent["continuation"]["status"],
        "final_subject_digest": parent["artifact_digest"],
        "world_id": package.get("world_id") if package else None,
        "public_package_digest": evaluation.get("public_package_digest"),
        "full_package_digest": evaluation.get("full_package_digest"),
        "fresh_actor_count": 1,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", parent)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
