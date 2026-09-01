from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0102_two_cycle_subject_recurrence.py"
BASE_SHA256 = "edf5041cdc207383a038745379510aa4e192bcd5a049fc97ab7535937534aeec"
RUN_ARCHIVE_SHA256 = "0263d499ed2ce6d0c7058e97f5514abbc1adb06076a34f9fabc2ce221ef46042"
AGGREGATE_SHA256 = "6f622ac6eaeea0a5597f498bb9b81c5bf5b46fb30acde80bc78bd8b00fd7cd40"
EXPECTED_PATHS = {"assimilation.json", "successor-opening.json", "next-interface.json"}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0102 implementation identity changed")
    name = "ot0103_frozen_ot0102"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()


def promote(p82, parent: dict[str, Any], selection: dict[str, Any], contact: dict[str, Any], assimilation: dict[str, Any], cycle: int):
    child = json.loads(json.dumps(parent))
    child.pop("artifact_digest", None)
    opening = assimilation["successor_opening"]
    body = {
        "authority": "world-promoted-two-cycle-subject-recurrence",
        "cycle": cycle, "source_subject_digest": parent["artifact_digest"],
        "interface_binding_digest": selection["binding_digest"],
        "contact_binding_digest": contact["binding_digest"],
        "world_receipt_digest": assimilation["world_receipt_digest"],
        "assimilation_binding_digest": assimilation["binding_digest"],
        "next_interface": assimilation["next_interface"],
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child["subject_recurrence_receipts"] = [*child.get("subject_recurrence_receipts", []), receipt]
    child["actor_authored_contacts"] = [*child.get("actor_authored_contacts", []), {
        "interface_id": contact["interface_id"], "binding_digest": contact["binding_digest"],
        "world_receipt_digest": assimilation["world_receipt_digest"],
    }]
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []), {
        "receipt": receipt, "assimilation": assimilation["assimilation"],
    }]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []), {
        "authority": "ot-0102-fresh-consequence-opening", "binding_digest": assimilation["binding_digest"],
        "opening": opening, "next_interface": assimilation["next_interface"],
    }]
    child["active_pursuit"] = {
        "authority": "ot-0102-fresh-consequence-opening",
        "selected_area": assimilation["next_interface"]["interface_id"],
        "next_pursuit": opening["next_opening"],
        "world_receipt_digest": assimilation["world_receipt_digest"],
    }
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["unresolved"] = opening["continuation_after_contact"]
    child["runtime"] = "sounding"
    return p82.seal(child), receipt


base.promote = promote


def extract_archive(path: Path, destination: Path) -> Path:
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != "OT-0102" or member.name.startswith("/") or ".." in parts:
                raise RuntimeError("unsafe OT-0102 archive member")
            if member.issym() or member.islnk():
                raise RuntimeError("linked OT-0102 archive member")
        archive.extractall(destination, members=members)
    return destination / "OT-0102"


def load_inputs(p82, repo: Path, store: Path, destination: Path):
    run_manifest, run_path = p82.materialize(repo, store, "OT-0102", "rejected-two-cycle-subject-recurrence-run.json")
    aggregate_manifest, aggregate_path = p82.materialize(repo, store, "OT-0102", "two-cycle-recurrence-aggregate.json")
    if run_manifest["sha256"] != RUN_ARCHIVE_SHA256 or aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0102 input identity")
    return json.loads(aggregate_path.read_text()), extract_archive(run_path, destination)


def corrected_cycle_one(prior89, p82, runtime, parent: dict[str, Any], aggregate: dict[str, Any], raw: Path, evidence: Path | None = None):
    route = aggregate["initial_route"]
    contact = aggregate["cycle_1"]["contact"]
    inherited_audit = aggregate["cycle_1"]["assimilation"]["audit"]
    inherited_output = aggregate["cycle_1"]["assimilation"]["output"]
    workspace = raw / "cycle-1-assimilation" / "actor-workspace"
    assimilation = json.loads((workspace / "assimilation.json").read_text())
    opening = json.loads((workspace / "successor-opening.json").read_text())
    next_interface = json.loads((workspace / "next-interface.json").read_text())
    position = base.active_position(parent)
    capability = next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == "operations/joint.py")
    allocator_retained = (workspace / "retained-allocator.py").read_text() == parent["allocation_machinery"][-1]["source"]
    joint_retained = (workspace / "retained-joint.py").read_text() == capability["source"]
    artifact_valid = bool(
        base.valid_assimilation(assimilation) and prior89.valid_successor(opening)
        and base.valid_next_interface(next_interface) and allocator_retained and joint_retained
        and opening["next_opening"] != position["continuation"]["next_opening"]
    )
    observed = set(inherited_audit["changed_paths"])
    reported = set(inherited_output["files_changed"])
    normalized_exact = observed == EXPECTED_PATHS
    truthful = reported == observed
    corrected_audit = {
        **inherited_audit,
        "inherited_conformant": inherited_audit["conformant"],
        "comparison_regime": "normalized-changed-path-set-v1",
        "expected_changes": sorted(EXPECTED_PATHS),
        "normalized_exact_changes": normalized_exact,
        "truthful": truthful,
    }
    corrected_audit["conformant"] = bool(
        inherited_audit["trace_regime"]["accepted"]
        and inherited_audit["denial_classification_v2"]["accepted"]
        and normalized_exact and truthful and artifact_valid
        and inherited_audit["command_count"] + inherited_audit["file_change_count"] > 0
    )
    passed_ids = {row["case_id"] for row in contact["world"]["rows"] if row["passed"]}
    cited = set(assimilation["settled_case_ids"])
    grounded = bool(corrected_audit["conformant"] and cited and cited.issubset(passed_ids))
    binding = None
    if grounded:
        body = {
            "authority": "ot-0103-normalized-cycle-one-assimilation",
            "source_subject_digest": parent["artifact_digest"],
            "contact_binding_digest": contact["binding"]["binding_digest"],
            "world_receipt_digest": contact["world"]["receipt_digest"],
            "actor_patch_digest": corrected_audit["patch_digest"],
            "allocator_retention_derived": allocator_retained,
            "joint_retention_derived": joint_retained,
            "assimilation": assimilation, "successor_opening": opening,
            "next_interface": next_interface,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
    current = parent
    promotion = None
    if binding:
        current, promotion = base.promote(p82, parent, route["binding"], contact["binding"], binding, 1)
    operational = bool(
        promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
        and current["continuation"]["status"] == "open"
        and current["continuation"]["next_opening"] == opening["next_opening"]
        and len(current.get("subject_recurrence_receipts", [])) == len(parent.get("subject_recurrence_receipts", [])) + 1
    )
    result = {
        "route": route, "contact": contact, "inherited_output": inherited_output,
        "corrected_audit": corrected_audit, "grounded": grounded,
        "binding": binding, "promotion_receipt": promotion,
        "operational_transition_passed": operational,
    }
    if evidence:
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "corrected-cycle-one-audit.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        if operational:
            (evidence / "sealed-cycle-one-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    return result, current


def normalized_context(context):
    original = context.audit_actor

    def audit(label, output, base_audit, artifact_valid, expected_changes):
        return original(label, output, base_audit, artifact_valid, sorted(set(expected_changes)))

    context.audit_actor = audit
    return context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0103").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = base.load_parent(p82, repo, store)
    if parent["artifact_digest"] != base.PARENT_DIGEST or not runtime.identity_conforms(parent):
        raise SystemExit("wrong OT-0101 parent")
    with tempfile.TemporaryDirectory() as directory:
        aggregate, raw = load_inputs(p82, repo, store, Path(directory))
        repaired, repaired_subject = corrected_cycle_one(prior89, p82, runtime, parent, aggregate, raw)
    preflight = {
        "parent_digest": parent["artifact_digest"],
        "ot0102_aggregate_receipt_digest": aggregate["receipt_digest"],
        "raw_archive_sha256": RUN_ARCHIVE_SHA256,
        "aggregate_sha256": AGGREGATE_SHA256,
        "normalized_path_set_passed": repaired["corrected_audit"]["normalized_exact_changes"],
        "retained_cycle_one_grounded": repaired["grounded"],
        "retained_cycle_one_operational": repaired["operational_transition_passed"],
        "passed": repaired["operational_transition_passed"],
    }
    if args.preflight_only:
        print(json.dumps(preflight, indent=2, sort_keys=True))
        return 0 if preflight["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0103 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n")
    if not preflight["passed"]:
        raise SystemExit("pre-actor normalized audit failed")
    with tempfile.TemporaryDirectory() as directory:
        aggregate, raw = load_inputs(p82, repo, store, Path(directory))
        cycle1, current = corrected_cycle_one(prior89, p82, runtime, parent, aggregate, raw, run / "cycle-1-reaudit")
    started = time.time()
    next_value = cycle1["binding"]["next_interface"]
    body = {
        "authority": "ot-0103-successor-bound-interface",
        "source_subject_digest": current["artifact_digest"],
        "assimilation_binding_digest": cycle1["binding"]["binding_digest"],
        "next_interface": next_value,
    }
    second_selection = {**body, "binding_digest": p82.digest(body)}
    (run / "cycle-2-bound-interface.json").write_text(json.dumps(second_selection, indent=2, sort_keys=True) + "\n")
    context = normalized_context(base.typed.base.make_context(runtime, run, repo))
    cycle2 = base.run_cycle(prior89, p82, runtime, context, run, 2, current, second_selection)
    if cycle2["operational_transition_passed"]:
        current = cycle2["current"]
    two_cycle = bool(cycle1["operational_transition_passed"] and cycle2["operational_transition_passed"])
    erased_control = None
    if two_cycle:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        erased_control = base.run_router(p82, context, run, "opening-erased-router", base.erased_position(p82, parent))
    erased_selected_joint = bool(
        erased_control and erased_control["binding"]
        and erased_control["binding"]["next_interface"]["interface_id"] == "joint-boundary-probe"
    )
    result = {
        "authority": "ot-0103-normalized-recurrence-continuation-driver",
        "source_subject_digest": parent["artifact_digest"],
        "retained_cycle_1": p82.compact(cycle1),
        "cycle_2": p82.compact({key: value for key, value in cycle2.items() if key != "current"}),
        "opening_erased_router": p82.compact(erased_control) if erased_control else None,
        "two_cycle_operational_recurrence_passed": two_cycle,
        "opening_erased_selected_joint": erased_selected_joint,
        "observer_disposition": "promoted" if two_cycle else "conditional",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "completed_cycles": 2 if two_cycle else 1,
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if two_cycle else 2


if __name__ == "__main__":
    raise SystemExit(main())
