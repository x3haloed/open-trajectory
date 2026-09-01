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
BASE_PATH = ROOT / "ot_0105_consequence_corrected_cross_interface_contact.py"
BASE_SHA256 = "dc46e104fbb51f44ad5f8981ffc084df41582fbc4305548df4bc5eca3ca83168"
RUN_ARCHIVE_SHA256 = "ea3314039fc3776aaee4c6ffca8be85add781820f2c05fc1cef2ffcb3cf19edd"
AGGREGATE_SHA256 = "33602c0b5587df3642b01508017b6f03c119eae5c28e21c468c809b93f77f14f"
CONTACT_SCHEMA = REPO / "spec/ot-0102-contact.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0105 implementation identity changed")
    name = "ot0106_frozen_ot0105"
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
            if not parts or parts[0] != "OT-0105" or member.name.startswith("/") or ".." in parts:
                raise RuntimeError("unsafe OT-0105 archive member")
            if member.issym() or member.islnk():
                raise RuntimeError("linked OT-0105 archive member")
        archive.extractall(destination, members=members)
    return destination / "OT-0105"


def load_inputs(p82, repo: Path, store: Path, destination: Path):
    run_manifest, run_path = p82.materialize(repo, store, "OT-0105", "rejected-consequence-corrected-cross-interface-run.json")
    aggregate_manifest, aggregate_path = p82.materialize(repo, store, "OT-0105", "consequence-corrected-cross-interface-aggregate.json")
    if run_manifest["sha256"] != RUN_ARCHIVE_SHA256 or aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0105 input identity")
    aggregate = json.loads(aggregate_path.read_text())
    raw = extract_archive(run_path, destination)
    artifact = json.loads((raw / "active-corrector" / "actor-workspace" / "contact.json").read_text())
    return aggregate, artifact


def coverage_receipt(p82, artifact: dict[str, Any]) -> dict[str, Any]:
    valid, checks = base.valid_allocator_contact(artifact)
    failures = []
    if not checks["filtered_decoy"]:
        failures.append({
            "code": "filtered-decoy-not-dominant",
            "certificate": "At least one ineligible contact must have predicted_expansion and public_regret each >= the selected live contact, while all numbers remain within [0, 200].",
            "why": "Otherwise the case does not require filtering to prevent selection of a numerically dominant decoy.",
        })
    if not checks["composition_threshold"]:
        failures.append({
            "code": "boolean-composition-threshold-uncovered",
            "certificate": "At least one selected eligible contact has exactly two completed_floors and beats an eligible contact with more than two completed_floors because its predicted_expansion is higher.",
            "why": "This distinguishes the Boolean >=2 threshold from ranking raw floor count.",
        })
    body = {
        "authority": "ot-0106-machine-coverage-consequence",
        "artifact_digest": p82.digest(artifact), "checks": checks,
        "failures": failures, "passed": valid,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def erased_receipt(p82, receipt: dict[str, Any]) -> dict[str, Any]:
    body = {
        "authority": receipt["authority"], "artifact_digest": receipt["artifact_digest"],
        "checks": {key: None for key in receipt["checks"]},
        "failures": [{"opaque_failure": p82.digest(row)} for row in receipt["failures"]],
        "passed": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def refined_schema() -> dict[str, Any]:
    value = previous.canonical_schema()
    value["operational_coverage_certificates"] = {
        "filtered_decoy": "An ineligible contact has predicted_expansion and public_regret each >= the selected live contact, within [0, 200].",
        "composition_threshold": "An eligible exactly-two-floor selected contact beats an eligible more-than-two-floor contact because predicted_expansion is higher.",
        "unchanged_requirements": ["order reversal", "expansion", "regret", "stable-id tie"],
    }
    return value


def correction_seed(run: Path, label: str, parent: dict[str, Any], selection: dict[str, Any], artifact: dict[str, Any], receipt: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    (seed / "subject-position.json").write_text(json.dumps(base.active_position(parent), indent=2, sort_keys=True) + "\n")
    (seed / "bound-interface.json").write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n")
    (seed / "contact.json").write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    (seed / "coverage-consequence.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (seed / "canonical-contact-schema.json").write_text(json.dumps(refined_schema(), indent=2, sort_keys=True) + "\n")
    (seed / "retained-machinery.py").write_text(parent["allocation_machinery"][-1]["source"])
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["contact.json"], "immutable": ["retained-machinery.py"]}, indent=2) + "\n")
    (seed / "README.md").write_text(
        "Continue the exact rejected allocator contact. Correct the two machine-reported coverage failures while preserving canonical shape, bounds, order reversal, expansion, regret, and stable ties. Edit only contact.json, run useful checks, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_corrector(p82, context, run: Path, label: str, parent: dict[str, Any], selection: dict[str, Any], artifact: dict[str, Any], receipt: dict[str, Any]):
    seed = correction_seed(run, label, parent, selection, artifact, receipt)
    prompt = "Correct this exact canonical allocator contact from its coverage consequence. Satisfy both operational certificates without regressing the four passing dimensions, edit only contact.json, inspect the diff, and return the required report."
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
            "authority": "ot-0106-iterated-consequence-corrected-contact",
            "source_subject_digest": parent["artifact_digest"],
            "interface_binding_digest": selection["binding_digest"],
            "source_contact_digest": p82.digest(artifact),
            "coverage_receipt_digest": receipt["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"], "interface_id": "allocator-challenge",
            "contact": corrected, "conformance": conformance,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        world = base.score_contact(p82, parent, "allocator-challenge", corrected)
        (context.evidence(label) / "bound-corrected-contact.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
        (context.evidence(label) / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "machinery_retained": machinery_retained, "binding": binding, "world": world, "admitted": bool(binding and world and world["all_cases_passed"])}


def fixture_conformance(parent: dict[str, Any], aggregate: dict[str, Any], artifact: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    checks = receipt["checks"]
    audit = aggregate["active_correction"]["audit"]
    result = {
        "source_rejected": not aggregate["cross_interface_operational_recurrence_passed"],
        "source_subject_unchanged": aggregate["final_subject_digest"] == parent["artifact_digest"],
        "source_trace_clean": audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["accepted"],
        "source_mutation_exact": audit["exact_changes"] and audit["truthful"],
        "canonical_shape_and_bounds": checks["exact_shape"],
        "passing_dimensions_preserved": all(checks[key] for key in ("order_reversal", "expansion", "regret", "stable_tie")),
        "two_expected_failures": {row["code"] for row in receipt["failures"]} == {"filtered-decoy-not-dominant", "boolean-composition-threshold-uncovered"},
        "source_world_absent": aggregate["active_correction"]["world"] is None,
    }
    result["passed"] = all(result.values())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0106").resolve()
    prior92 = base.mechanism.load_prior(); _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = previous.previous.load_parent(p82, repo, store)
    if parent["artifact_digest"] != previous.previous.PARENT_DIGEST or not runtime.identity_conforms(parent):
        raise SystemExit("wrong OT-0103 parent")
    with tempfile.TemporaryDirectory() as directory:
        aggregate, artifact = load_inputs(p82, repo, store, Path(directory))
    receipt = coverage_receipt(p82, artifact)
    fixtures = fixture_conformance(parent, aggregate, artifact, receipt)
    selection = previous.previous.extract_action(p82, parent)
    if args.preflight_only:
        result = {"parent_digest": parent["artifact_digest"], "base_implementation_sha256": BASE_SHA256, "run_archive_sha256": RUN_ARCHIVE_SHA256, "aggregate_sha256": AGGREGATE_SHA256, "coverage_receipt_digest": receipt["receipt_digest"], "fixture_conformance": fixtures}
        print(json.dumps(result, indent=2, sort_keys=True)); return 0 if fixtures["passed"] and selection else 2
    if run.exists(): raise SystemExit("preserve existing OT-0106 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    (run / "bound-coverage-consequence.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"] or not selection: raise SystemExit("pre-actor conformance failed")
    context = previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    active = run_corrector(p82, context, run, "active-second-corrector", parent, selection, artifact, receipt)
    assimilation = None; current = parent; promotion = None
    if active["admitted"]:
        contact = {"binding": active["binding"], "world": active["world"], "admitted": True}
        assimilation = base.run_assimilation(prior89, p82, context, run, "active-assimilation", parent, base.active_position(parent), contact)
    if assimilation and assimilation["binding"]:
        current, promotion = base.promote(p82, parent, selection, active["binding"], assimilation["binding"], 3)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open")
    control = None
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control = run_corrector(p82, context, run, "coverage-erased-corrector", parent, selection, artifact, erased_receipt(p82, receipt))
    control_reproduced = bool(control and control["admitted"])
    result = {
        "authority": "ot-0106-iterated-contact-coverage-correction-driver",
        "source_subject_digest": parent["artifact_digest"], "coverage_receipt_digest": receipt["receipt_digest"],
        "active_second_correction": p82.compact(active), "assimilation": p82.compact(assimilation) if assimilation else None,
        "promotion_receipt": promotion, "coverage_erased_control": p82.compact(control) if control else None,
        "cross_interface_operational_recurrence_passed": operational,
        "coverage_erased_reproduced_correction": control_reproduced,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"], "next_interface": current["actor_originated_pursuit_openings"][-1].get("next_interface"),
        "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
