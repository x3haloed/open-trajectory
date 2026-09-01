from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0115_prospective_generic_expansion.py"
BASE_SHA256 = "869fbc02c1ab6d277c7b341eac420bd3d0641c8352e18c3423852ca951d36358"
RUN_SHA256 = "687ad840998a0ead55bbbb664276f9d9ce6569c204416411b356d9bfb41493d8"
AGGREGATE_SHA256 = "7bd538b92cb365f5ac6a1b2ccb2c72192b4eba119efac2937f325d905c673d62"
PARENT_OBJECT_SHA256 = "75f9f7a00f641c4e2be208ae7aab3499f62731f82e1ea9a4035d4ebb9c12601f"
PARENT_DIGEST = "fb918f194026d60e5cf0af656100efa465fccb56b61c5e219d558cb137db4880"
PACKAGE_BINDING = "063954fe535118ef459036b180164bdeac858763069c295abaf9c917ea09bc8c"
ASSIMILATION_PATCH = "862dc02157253fcb67c9fff1697f1e9c5a39549cdb5f7f5b8e821d2d136cd086"
REPAIRED_TARGET_RE = re.compile(r"[a-z][a-z0-9-]{2,127}")


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0115 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0116_frozen_ot0115", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior14 = previous.prior14
prior = previous.prior
kernel = previous.kernel
base = previous.base


def extract(path: Path, destination: Path):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if (
                not parts
                or parts[0] != "OT-0115"
                or member.name.startswith("/")
                or ".." in parts
                or member.issym()
                or member.islnk()
            ):
                raise RuntimeError("unsafe OT-0115 archive")
        archive.extractall(destination, members=members)
    return destination / "OT-0115"


def load_inputs(p82, repo: Path, store: Path, destination: Path):
    run_manifest, run_path = p82.materialize(
        repo, store, "OT-0115", "stopped-prospective-third-expansion-run.json"
    )
    aggregate_manifest, aggregate_path = p82.materialize(
        repo,
        store,
        "OT-0115",
        "stopped-prospective-third-expansion-aggregate.json",
    )
    parent_manifest, parent_path = p82.materialize(
        repo, store, "OT-0115", "unchanged-open-subject-after-target-abi-stop.json"
    )
    if run_manifest["sha256"] != RUN_SHA256:
        raise RuntimeError("wrong OT-0115 run")
    if aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0115 aggregate")
    if parent_manifest["sha256"] != PARENT_OBJECT_SHA256:
        raise RuntimeError("wrong OT-0115 parent")
    raw = extract(run_path, destination)
    aggregate = json.loads(aggregate_path.read_text())
    parent = json.loads(parent_path.read_text())
    package = json.loads((raw / "cycle-3-package-author" / "bound-package.json").read_text())
    workspace = raw / "cycle-3-assimilation" / "actor-workspace"
    assimilation = json.loads((workspace / "assimilation.json").read_text())
    opening = json.loads((workspace / "successor-opening.json").read_text())
    action = json.loads((workspace / "continuation-action.json").read_text())
    hidden = json.loads((raw / "cycle-3-hidden-cases.json").read_text())
    return raw, aggregate, parent, package, hidden, assimilation, opening, action


def repaired_action_valid(value: Any, subject: dict[str, Any]):
    if (
        not isinstance(value, dict)
        or set(value) != kernel.ACTION_KEYS
        or value.get("action_kind")
        not in {"registered-contact", "registry-extension", "surrender"}
    ):
        return False
    if not all(
        isinstance(value.get(key), str) and value[key].strip() and len(value[key]) <= 3000
        for key in kernel.ACTION_KEYS - {"action_kind"}
    ):
        return False
    if value["action_kind"] == "registered-contact":
        return value["action_target"] in kernel.registered(subject)
    if value["action_kind"] == "surrender":
        return value["action_target"] == "none"
    return (
        value["action_target"] not in kernel.registered(subject)
        and bool(REPAIRED_TARGET_RE.fullmatch(value["action_target"]))
    )


def digest_valid(p82, value: dict[str, Any], field: str):
    body = {key: item for key, item in value.items() if key != field}
    return value.get(field) == p82.digest(body)


def reconstruct(prior89, p82, repo: Path, store: Path, directory: Path):
    raw, aggregate, parent, package, hidden, assimilation, opening, action = load_inputs(
        p82, repo, store, directory
    )
    tip = previous.current_tip(p82, parent, repo, store)
    selection = kernel.extract_action(p82, parent)
    admission = aggregate["admission"]
    world = aggregate["world"]
    author_audit = aggregate["package_author"]["audit"]
    assimilation_audit = aggregate["assimilation"]["audit"]
    workspace = raw / "cycle-3-assimilation" / "actor-workspace"
    retained = (
        (workspace / "retained-parent-operation.py").read_text() == tip["operation_source"]
        and (workspace / "admitted-operation.py").read_text() == package["operation_source"]
        and (workspace / "admitted-conformance.py").read_text()
        == package["conformance_source"]
    )
    spec = prior14.previous.normalize_spec(package["interface"])
    reassessment = kernel.assess(
        spec,
        tip,
        package["contact"],
        package["operation_source"],
        package["conformance_source"],
        hidden,
    )
    extended_subject = {
        **parent,
        "interface_registry_extensions": [
            *parent.get("interface_registry_extensions", []),
            {"interface_id": package["interface"]["interface_id"]},
        ],
    }
    passed_cases = {row["case_id"] for row in world["rows"] if row["passed"]}
    cited_cases = set(assimilation.get("settled_case_ids", []))
    checks = {
        "source_rejected": not aggregate["operational_transition_passed"],
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "package_binding_exact": package["binding_digest"] == PACKAGE_BINDING,
        "package_binding_valid": digest_valid(p82, package, "binding_digest"),
        "package_author_clean": bool(
            author_audit["conformant"]
            and author_audit["exact_changes"]
            and author_audit["truthful"]
            and author_audit["trace_regime"]["accepted"]
            and author_audit["denial_classification_v2"]["accepted"]
        ),
        "public_correction_not_needed": aggregate["correction"]["needed"] is False,
        "independent_reassessment_exact": reassessment == admission["assessment"],
        "admission_valid": bool(
            admission["admitted"]
            and digest_valid(p82, admission, "receipt_digest")
            and admission["package_binding_digest"] == package["binding_digest"]
        ),
        "world_valid": bool(
            world == kernel.world_contact(p82, 3, package, admission)
            and world["all_cases_passed"]
        ),
        "assimilation_patch_exact": assimilation_audit["patch_digest"]
        == ASSIMILATION_PATCH,
        "assimilation_trace_clean": bool(
            assimilation_audit["exact_changes"]
            and assimilation_audit["truthful"]
            and assimilation_audit["trace_regime"]["accepted"]
            and assimilation_audit["denial_classification_v2"]["accepted"]
        ),
        "package_retained": retained,
        "assimilation_valid": base.valid_assimilation(assimilation),
        "opening_valid": prior89.valid_successor(opening),
        "opening_changed": opening["next_opening"]
        != base.active_position(parent)["continuation"]["next_opening"],
        "citations_grounded": bool(cited_cases and cited_cases.issubset(passed_cases)),
        "old_action_rejects": not kernel.valid_action(action, extended_subject),
        "repaired_action_accepts": repaired_action_valid(action, extended_subject),
        "target_exposes_old_boundary": 65 <= len(action["action_target"]) <= 128,
    }
    checks["passed"] = all(checks.values())
    repaired_audit = {**assimilation_audit, "conformant": checks["passed"]}
    body = {
        "authority": "ot-0116-retained-generic-expansion-assimilation",
        "cycle": 3,
        "source_subject_digest": parent["artifact_digest"],
        "package_binding_digest": package["binding_digest"],
        "admission_receipt_digest": admission["receipt_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "actor_patch_digest": assimilation_audit["patch_digest"],
        "package_retention_derived": retained,
        "assimilation": assimilation,
        "successor_opening": opening,
        "continuation_action": action,
        "published_target_length": [3, 128],
    }
    binding = {**body, "binding_digest": p82.digest(body)} if checks["passed"] else None
    return {
        "checks": checks,
        "parent": parent,
        "tip": tip,
        "selection": selection,
        "package": package,
        "admission": admission,
        "world": world,
        "retained_assimilation_audit": repaired_audit,
        "binding": binding,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0116").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    with tempfile.TemporaryDirectory() as directory:
        retained = reconstruct(prior89, p82, repo, store, Path(directory))
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "base_sha256": BASE_SHA256,
                    "run_sha256": RUN_SHA256,
                    "aggregate_sha256": AGGREGATE_SHA256,
                    "parent_digest": retained["parent"]["artifact_digest"],
                    "checks": retained["checks"],
                    "assimilation_binding_digest": retained["binding"]["binding_digest"]
                    if retained["binding"]
                    else None,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if retained["checks"]["passed"] and runtime.identity_conforms(retained["parent"]) else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0116 evidence")
    run.mkdir(parents=True)
    started = time.time()
    (run / "reconstruction-checks.json").write_text(
        json.dumps(retained["checks"], indent=2, sort_keys=True) + "\n"
    )
    if not retained["checks"]["passed"] or not runtime.identity_conforms(retained["parent"]):
        raise SystemExit("retained reconstruction failed")
    (run / "bound-retained-assimilation.json").write_text(
        json.dumps(retained["binding"], indent=2, sort_keys=True) + "\n"
    )
    child, promotion = kernel.promote(
        p82,
        retained["parent"],
        retained["selection"],
        retained["package"],
        retained["admission"],
        retained["world"],
        retained["binding"],
    )
    operational = runtime.identity_conforms(child)
    result = {
        "authority": "ot-0116-retained-assimilation-target-abi-driver",
        "source_subject_digest": retained["parent"]["artifact_digest"],
        "package_binding_digest": retained["package"]["binding_digest"],
        "assimilation_binding_digest": retained["binding"]["binding_digest"],
        "reconstruction_checks": retained["checks"],
        "retained_assimilation_audit": retained["retained_assimilation_audit"],
        "promotion": promotion,
        "operational_transition_passed": operational,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": child["continuation"]["status"],
        "final_subject_digest": child["artifact_digest"],
        "continuation_action": child["actor_originated_pursuit_openings"][-1][
            "continuation_action"
        ],
        "next_opening": child["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (run / "final-full-subject.json").write_text(
        json.dumps(child, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
