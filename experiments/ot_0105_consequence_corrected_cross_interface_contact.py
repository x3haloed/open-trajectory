from __future__ import annotations

import argparse
import copy
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
BASE_PATH = ROOT / "ot_0104_bound_cross_interface_recurrence.py"
BASE_SHA256 = "c8ffeba30bbe9499425548a1e4e4e300f1c500216ca796e14e8ccc9537750d18"
RUN_ARCHIVE_SHA256 = "6629b6e9864405503b713ec7e331cafe1d1fa214c793222396d12954345eb9c9"
AGGREGATE_SHA256 = "93d5e549d05b3fe0332c97b59f3db8c2e361e4a4c7b9c8187aedfbf1fae622b6"
CONTACT_SCHEMA = REPO / "spec/ot-0102-contact.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0104 implementation identity changed")
    name = "ot0105_frozen_ot0104"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
base = previous.base


def extract_archive(path: Path, destination: Path) -> Path:
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != "OT-0104" or member.name.startswith("/") or ".." in parts:
                raise RuntimeError("unsafe OT-0104 archive member")
            if member.issym() or member.islnk():
                raise RuntimeError("linked OT-0104 archive member")
        archive.extractall(destination, members=members)
    return destination / "OT-0104"


def load_inputs(p82, repo: Path, store: Path, destination: Path):
    run_manifest, run_path = p82.materialize(repo, store, "OT-0104", "rejected-bound-cross-interface-recurrence-run.json")
    aggregate_manifest, aggregate_path = p82.materialize(repo, store, "OT-0104", "bound-cross-interface-recurrence-aggregate.json")
    if run_manifest["sha256"] != RUN_ARCHIVE_SHA256 or aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0104 input identity")
    aggregate = json.loads(aggregate_path.read_text())
    raw = extract_archive(run_path, destination)
    artifact = json.loads((raw / "cycle-3-contact" / "actor-workspace" / "contact.json").read_text())
    return aggregate, raw, artifact


def canonical_schema() -> dict[str, Any]:
    return {
        "root": {"exact_keys": ["interface_id", "frontiers"], "interface_id": "allocator-challenge"},
        "frontiers": {"type": "array", "exact_count": 4, "item_type": "array", "contacts_per_item": [2, 8]},
        "contact": {
            "exact_keys": sorted(base.CONTACT_KEYS),
            "number_fields": {"predicted_expansion": [0, 200], "public_regret": [0, 200]},
            "completed_floors": "array of nonempty strings",
            "boolean_fields": ["reversible", "held_repeat", "world_valid", "world_contact"],
            "string_fields": ["id", "target_path", "target_symbol", "surrender_condition"],
        },
        "coverage": ["order reversal", "filtered decoy", "two-floor composition threshold", "expansion", "regret", "stable-id tie"],
        "scoring": "actor-declared coverage and result labels are not used; the world executes retained and reference selectors after binding",
    }


def derive_receipt(p82, artifact: Any) -> dict[str, Any]:
    failures = []
    frontiers = artifact.get("frontiers", []) if isinstance(artifact, dict) else []
    for index, frontier in enumerate(frontiers):
        if not isinstance(frontier, list):
            failures.append({
                "code": "frontier-container-not-array", "path": f"frontiers[{index}]",
                "observed_type": type(frontier).__name__, "required_type": "array",
                "repair": "replace the wrapper with its contacts array; omit case_id, coverage, retained_result, and reference_result from executable contact",
            })
        contacts = frontier.get("contacts", []) if isinstance(frontier, dict) else frontier if isinstance(frontier, list) else []
        for contact_index, contact in enumerate(contacts):
            if not isinstance(contact, dict):
                continue
            for field in ("predicted_expansion", "public_regret"):
                value = contact.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and not 0 <= value <= 200:
                    failures.append({
                        "code": "number-out-of-bounds",
                        "path": f"frontiers[{index}].contacts[{contact_index}].{field}",
                        "observed": value, "inclusive_bounds": [0, 200],
                    })
    body = {
        "authority": "ot-0105-machine-contact-conformance",
        "artifact_digest": p82.digest(artifact),
        "failures": failures,
        "wrapper_failure_count": sum(row["code"] == "frontier-container-not-array" for row in failures),
        "bounds_failure_count": sum(row["code"] == "number-out-of-bounds" for row in failures),
        "passed": not failures,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def erased_receipt(p82, receipt: dict[str, Any]) -> dict[str, Any]:
    body = {
        "authority": receipt["authority"], "artifact_digest": receipt["artifact_digest"],
        "failures": [{"opaque_failure": p82.digest(row)} for row in receipt["failures"]],
        "wrapper_failure_count": None, "bounds_failure_count": None, "passed": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def correction_seed(run: Path, label: str, parent: dict[str, Any], selection: dict[str, Any], artifact: dict[str, Any], receipt: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(parent), indent=2, sort_keys=True) + "\n")
    (seed / "bound-interface.json").write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n")
    (seed / "contact.json").write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    (seed / "contact-conformance-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (seed / "canonical-contact-schema.json").write_text(json.dumps(canonical_schema(), indent=2, sort_keys=True) + "\n")
    (seed / "retained-machinery.py").write_text(parent["allocation_machinery"][-1]["source"])
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["contact.json"], "immutable": ["retained-machinery.py"]}, indent=2) + "\n")
    (seed / "README.md").write_text(
        "Continue the rejected subject-bound allocator contact. Correct the exact retained contact using the public canonical schema and conformance receipt. Preserve the intended four-frontier coverage, edit only contact.json, run useful checks, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_corrector(p82, context, run: Path, label: str, parent: dict[str, Any], selection: dict[str, Any], artifact: dict[str, Any], receipt: dict[str, Any]):
    seed = correction_seed(run, label, parent, selection, artifact, receipt)
    prompt = "Correct this exact rejected allocator contact from its retained artifact and conformance receipt. Produce the canonical four-frontier executable contact, preserve discriminating coverage, edit only contact.json, inspect the diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, prompt)
    try:
        corrected = json.loads((workspace / "contact.json").read_text())
        machinery_retained = (workspace / "retained-machinery.py").read_text() == parent["allocation_machinery"][-1]["source"]
    except (OSError, json.JSONDecodeError):
        corrected, machinery_retained = None, False
    valid, conformance = base.valid_allocator_contact(corrected)
    artifact_valid = bool(valid and machinery_retained and corrected != artifact)
    audit = context.audit_actor(label, output, base_audit, artifact_valid, ["contact.json"])
    binding = world = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0105-consequence-corrected-contact",
            "source_subject_digest": parent["artifact_digest"],
            "interface_binding_digest": selection["binding_digest"],
            "source_contact_digest": p82.digest(artifact),
            "conformance_receipt_digest": receipt["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"], "interface_id": "allocator-challenge",
            "contact": corrected, "conformance": conformance,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        world = base.score_contact(p82, parent, "allocator-challenge", corrected)
        (context.evidence(label) / "bound-corrected-contact.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
        (context.evidence(label) / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    return {
        "output": output, "audit": audit, "machinery_retained": machinery_retained,
        "binding": binding, "world": world,
        "admitted": bool(binding and world and world["all_cases_passed"]),
    }


def fixture_conformance(p82, parent: dict[str, Any], aggregate: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    receipt = derive_receipt(p82, artifact)
    projected = {
        "interface_id": "allocator-challenge",
        "frontiers": [row["contacts"] for row in artifact["frontiers"]],
    }
    projected_valid, _ = base.valid_allocator_contact(projected)
    contact_audit = aggregate["cross_interface_cycle"]["contact"]["audit"]
    result = {
        "source_run_rejected": not aggregate["cross_interface_operational_recurrence_passed"],
        "source_subject_unchanged": aggregate["final_subject_digest"] == parent["artifact_digest"],
        "source_trace_clean": bool(contact_audit["trace_regime"]["accepted"] and contact_audit["denial_classification_v2"]["accepted"]),
        "source_mutation_exact": contact_audit["exact_changes"] and contact_audit["truthful"],
        "source_world_absent": aggregate["cross_interface_cycle"]["contact"]["world"] is None,
        "binding_erasure_stops_action": aggregate["binding_erasure_stops_action"],
        "wrapper_failure_count": receipt["wrapper_failure_count"],
        "bounds_failure_count": receipt["bounds_failure_count"],
        "wrapper_projection_still_invalid": not projected_valid,
        "receipt_digest": receipt["receipt_digest"],
    }
    result["passed"] = bool(
        all(result[key] for key in (
            "source_run_rejected", "source_subject_unchanged", "source_trace_clean",
            "source_mutation_exact", "source_world_absent", "binding_erasure_stops_action",
            "wrapper_projection_still_invalid",
        ))
        and result["wrapper_failure_count"] == 4 and result["bounds_failure_count"] == 16
    )
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
    run = (args.evidence_root or store / "runs/OT-0105").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = previous.load_parent(p82, repo, store)
    if parent["artifact_digest"] != previous.PARENT_DIGEST or not runtime.identity_conforms(parent):
        raise SystemExit("wrong OT-0103 parent")
    with tempfile.TemporaryDirectory() as directory:
        aggregate, _, artifact = load_inputs(p82, repo, store, Path(directory))
    fixtures = fixture_conformance(p82, parent, aggregate, artifact)
    receipt = derive_receipt(p82, artifact)
    selection = previous.extract_action(p82, parent)
    if args.preflight_only:
        result = {
            "parent_digest": parent["artifact_digest"], "base_implementation_sha256": BASE_SHA256,
            "run_archive_sha256": RUN_ARCHIVE_SHA256, "aggregate_sha256": AGGREGATE_SHA256,
            "fixture_conformance": fixtures,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] and selection else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0105 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    (run / "bound-conformance-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"] or not selection:
        raise SystemExit("pre-actor conformance failed")
    context = previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    active = run_corrector(p82, context, run, "active-corrector", parent, selection, artifact, receipt)
    assimilation = None
    current = parent
    promotion = None
    if active["admitted"]:
        contact = {"binding": active["binding"], "world": active["world"], "admitted": True}
        assimilation = base.run_assimilation(prior89, p82, context, run, "active-assimilation", parent, base.active_position(parent), contact)
    if assimilation and assimilation["binding"]:
        current, promotion = base.promote(p82, parent, selection, active["binding"], assimilation["binding"], 3)
    operational = bool(
        promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
        and current["continuation"]["status"] == "open"
        and current["continuation"]["next_opening"] == assimilation["binding"]["successor_opening"]["next_opening"]
    )
    control = None
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control = run_corrector(p82, context, run, "failure-erased-corrector", parent, selection, artifact, erased_receipt(p82, receipt))
    control_reproduced = bool(control and control["admitted"])
    result = {
        "authority": "ot-0105-consequence-corrected-cross-interface-contact-driver",
        "source_subject_digest": parent["artifact_digest"], "conformance_receipt_digest": receipt["receipt_digest"],
        "active_correction": p82.compact(active),
        "assimilation": p82.compact(assimilation) if assimilation else None,
        "promotion_receipt": promotion,
        "failure_erased_control": p82.compact(control) if control else None,
        "cross_interface_operational_recurrence_passed": operational,
        "failure_erased_reproduced_correction": control_reproduced,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"],
        "next_interface": current["actor_originated_pursuit_openings"][-1].get("next_interface"),
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
