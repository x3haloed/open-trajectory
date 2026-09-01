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
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0097_consequence_corrected_allocation.py"
BASE_SHA256 = "cb48ca15612ff193f7eedb22ffc843fef953af94d02664970fe9efe006679c0c"
RAW_RUN_SHA256 = "8a8cef6ecc544fcb82e58e2874c6957d4651055dc5eeaf4944b64ad1dfa1deaf"
CORRECTOR_SCHEMA = REPO / "spec/ot-0098-corrector.schema.json"
CORRECTION_KEYS = {"failed_fixture_ids", "correction_summary", "remaining_uncertainty", "surrender_condition"}
PLACEHOLDER = "__REPLACE__"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0097 implementation identity changed")
    name = "ot0098_frozen_ot0097"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


base = load_base(); typed = base.base; allocation = base.allocation; mechanism = base.mechanism


def read_member(archive: tarfile.TarFile, name: str) -> str:
    member = archive.getmember(name)
    if not member.isfile(): raise RuntimeError(f"not a regular archived file: {name}")
    handle = archive.extractfile(member)
    if handle is None: raise RuntimeError(f"cannot read archived file: {name}")
    return handle.read().decode()


def load_shallow_candidate(p82, repo: Path, store: Path, failed: dict[str, Any]) -> dict[str, Any]:
    manifest, path = p82.materialize(repo, store, "OT-0097", "rejected-consequence-corrected-allocation-run.json")
    if manifest["sha256"] != RAW_RUN_SHA256: raise RuntimeError("wrong OT-0097 run identity")
    prefix = "OT-0097/active-correction/actor-workspace/"
    with tarfile.open(path) as archive:
        source = read_member(archive, prefix + "allocate.py")
        choice = json.loads(read_member(archive, prefix + "choice.json"))
        correction = json.loads(read_member(archive, prefix + "correction.json"))
    original = failed["active_allocation"]["binding"]
    contacts = original["frontier"]["contacts"]
    selected = mechanism.load_allocator(source, Path(tempfile.mkdtemp(prefix="ot0098-shallow-")))(copy.deepcopy(contacts))
    cited = set(correction.get("failed_fixture_ids", []))
    if (source == original["allocator_source"] or selected != choice.get("contact_id") or selected != "joint"
            or not typed.valid_typed_choice(choice, contacts)
            or not {"real-order", "real-reversed", "renamed"}.issubset(cited)):
        raise RuntimeError("OT-0097 shallow candidate does not match frozen event")
    body = {"authority": "ot-0098-derived-shallow-revision-binding", "source_subject_digest": mechanism.PARENT_DIGEST,
            "prior_binding_digest": original["binding_digest"], "frontier": original["frontier"],
            "allocator_source": source, "allocator_digest": p82.digest(source), "choice": choice,
            "correction": {key: value for key, value in correction.items() if key != "disposition"},
            "revision_derived": True}
    return {**body, "binding_digest": p82.digest(body)}


def seal_second_stage(p82, shallow: dict[str, Any], root: Path) -> dict[str, Any]:
    result = base.second_stage_conformance(shallow["allocator_source"], root)
    body = {"authority": "ot-0098-sealed-second-stage-consequence", "shallow_binding_digest": shallow["binding_digest"],
            "fixture_rows": result["fixture_rows"], "generic_source": result["generic_source"], "passed": result["passed"]}
    return {**body, "receipt_digest": p82.digest(body)}


def erase_second_stage(p82, receipt: dict[str, Any]) -> dict[str, Any]:
    removed = {"fixture_rows": receipt["fixture_rows"], "passed": receipt["passed"]}
    return {"authority": receipt["authority"], "shallow_binding_digest": receipt["shallow_binding_digest"],
            "receipt_digest": receipt["receipt_digest"], "generic_source": receipt["generic_source"],
            "fixture_ids": [row["fixture_id"] for row in receipt["fixture_rows"]],
            "fixture_count": len(receipt["fixture_rows"]), "outcome_erasure_digest": p82.digest(removed)}


def contact(contact_id: str, floors: int, expansion: float, regret: float, **overrides) -> dict[str, Any]:
    return {**base.contact(contact_id, floors, expansion, regret), **overrides}


def third_stage_fixtures() -> list[dict[str, Any]]:
    return [
        {"fixture_id": "threshold-over-gain-a", "contacts": [contact("wide", 0, 130, 90), contact("woven", 2, 35, 5)]},
        {"fixture_id": "threshold-over-gain-b", "contacts": [contact("woven", 2, 35, 5), contact("wide", 0, 130, 90)]},
        {"fixture_id": "threshold-expansion", "contacts": [contact("north", 2, 45, 12), contact("south", 2, 70, 12)]},
        {"fixture_id": "threshold-regret", "contacts": [contact("quiet", 2, 55, 8), contact("urgent", 2, 55, 44)]},
        {"fixture_id": "irreversible-threshold", "contacts": [contact("closed", 2, 120, 90, reversible=False), contact("open", 0, 9, 2)]},
        {"fixture_id": "invalid-and-held", "contacts": [contact("invalid", 3, 140, 90, world_valid=False), contact("held", 2, 130, 80, held_repeat=True), contact("live", 0, 8, 2)]},
        {"fixture_id": "threshold-equality", "contacts": [contact("zulu", 2, 60, 20), contact("alpha", 4, 60, 20)]},
        {"fixture_id": "final-stable-id", "contacts": [contact("amber", 2, 60, 20), contact("zephyr", 2, 60, 20)]},
    ]


def third_stage_conformance(source: str, root: Path) -> dict[str, Any]:
    forbidden = ["threshold-over-gain", "threshold-expansion", "threshold-regret", "threshold-equality",
                 "wide", "woven", "urgent", "zephyr", "operations/", "candidate.py"]
    generic = all(token not in source for token in forbidden)
    try:
        select = mechanism.load_allocator(source, root); rows = []
        for fixture in third_stage_fixtures():
            actual = select(copy.deepcopy(fixture["contacts"])); wanted = base.expected(fixture["contacts"])
            rows.append({"fixture_id": fixture["fixture_id"], "expected": wanted, "actual": actual, "passed": actual == wanted})
        passed = generic and all(row["passed"] for row in rows)
    except Exception as error:
        rows, passed = [{"error_type": type(error).__name__, "passed": False}], False
    return {"generic_source": generic, "fixture_rows": rows, "passed": passed}


def correction_template() -> dict[str, Any]:
    return {"failed_fixture_ids": [], "correction_summary": PLACEHOLDER,
            "remaining_uncertainty": PLACEHOLDER, "surrender_condition": PLACEHOLDER}


def valid_correction(value: Any) -> bool:
    return bool(isinstance(value, dict) and set(value) == CORRECTION_KEYS
        and isinstance(value.get("failed_fixture_ids"), list) and all(isinstance(item, str) for item in value["failed_fixture_ids"])
        and all(isinstance(value.get(key), str) and value[key].strip() and PLACEHOLDER not in value[key]
                for key in CORRECTION_KEYS - {"failed_fixture_ids"}))


def corrector_seed(run, label, parent, shallow, receipt, position):
    seed = run / f"{label}-seed"; seed.mkdir(); mechanism.write_world(seed, parent)
    for name, value in (("subject-position.json", position), ("shallow-correction.json", shallow),
                        ("allocator-consequence.json", receipt), ("choice.json", shallow["choice"]),
                        ("correction.json", correction_template())):
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (seed / "allocate.py").write_text(shallow["allocator_source"])
    contract = {"editable": ["allocate.py", "choice.json", "correction.json"], "revision": "derived from allocator byte change",
        "allocator_abi": "select(contacts) -> contact id", "choice_types": "OT-0096 typed choice ABI",
        "instruction": "Use sealed consequence content when present; cite genuinely failed fixtures when revising; make choice equal allocator output."}
    (seed / "correction-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": contract["editable"]}, indent=2) + "\n")
    (seed / "README.md").write_text("Continue the exact subject by assimilating the latest allocator consequence. Revision is derived from changed bytes. Improve the generic rule when warranted, bind its live-frontier choice, run visible checks, inspect the diff, and edit only permitted files.\n")
    return seed


def run_corrector(p82, context, run, label, parent, shallow, receipt, position):
    seed = corrector_seed(run, label, parent, shallow, receipt, position)
    prompt = "Continue the exact subject by assimilating the sealed allocator consequence, improving its generic selection machinery when warranted, binding the resulting choice, running visible checks, inspecting the exact diff, and reporting truthfully."
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTOR_SCHEMA, prompt)
    try:
        source = (workspace / "allocate.py").read_text(); choice = json.loads((workspace / "choice.json").read_text())
        correction = json.loads((workspace / "correction.json").read_text())
    except (OSError, json.JSONDecodeError): source, choice, correction = "", None, None
    contacts = shallow["frontier"]["contacts"]
    try: selected = mechanism.load_allocator(source, workspace / "visible-allocator")(copy.deepcopy(contacts))
    except Exception: selected = None
    changed = set(base_audit["changed_paths"]); allowed = {"allocate.py", "choice.json", "correction.json"}
    artifact_valid = bool(valid_correction(correction) and typed.valid_typed_choice(choice, contacts)
        and selected == choice["contact_id"] and changed and changed.issubset(allowed) and "correction.json" in changed)
    audit = context.audit_actor(label, output, base_audit, artifact_valid, sorted(changed))
    failed_ids = {row["fixture_id"] for row in receipt.get("fixture_rows", []) if row.get("passed") is False}
    cited = set(correction.get("failed_fixture_ids", [])) if isinstance(correction, dict) else set()
    revised = source != shallow["allocator_source"]
    grounded = bool(revised and len(cited) >= 2 and cited.issubset(failed_ids))
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0098-pre-third-stage-correction", "condition": label,
            "source_subject_digest": parent["artifact_digest"], "shallow_binding_digest": shallow["binding_digest"],
            "second_stage_projection_digest": p82.digest(receipt), "actor_patch_digest": audit["patch_digest"],
            "frontier": shallow["frontier"], "allocator_source": source, "allocator_digest": p82.digest(source),
            "choice": choice, "correction": correction, "revision_derived": revised}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-correction.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    stage3 = third_stage_conformance(source, context.evidence(label) / "third-stage") if binding else {"passed": False}
    gate = bool(binding and grounded and stage3["passed"] and choice["contact_id"] == "joint")
    score = {"revision_derived": revised, "grounded_revision": grounded,
             "selected_contact_id": choice.get("contact_id") if isinstance(choice, dict) else None,
             "third_stage": stage3, "correction_gate_passed": gate}
    score["receipt_digest"] = p82.digest(score)
    (context.evidence(label) / "correction-score.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding, "score": score}


def promote(p82, parent, correction, shallow, stage2, implementation, assimilation):
    child, _ = allocation.promote(p82, parent, correction, implementation, assimilation); child.pop("artifact_digest", None)
    body = {"authority": "world-promoted-iterated-allocation-correction", "source_subject_digest": parent["artifact_digest"],
        "shallow_binding_digest": shallow["binding_digest"], "second_stage_receipt_digest": stage2["receipt_digest"],
        "correction_binding_digest": correction["binding_digest"], "third_stage_receipt_digest": correction["third_stage_receipt_digest"],
        "world_receipt_digest": implementation["world"]["receipt_digest"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child["allocation_corrections"] = [*child.get("allocation_corrections", []),
        {"shallow_binding_digest": shallow["binding_digest"], "second_stage_receipt_digest": stage2["receipt_digest"],
         "binding_digest": correction["binding_digest"], "correction": correction["correction"],
         "third_stage_receipt_digest": correction["third_stage_receipt_digest"]}]
    return p82.seal(child), receipt


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(); repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0098").resolve()
    prior92 = mechanism.load_prior(); _, prior90, prior89, p82 = mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store); parent = mechanism.load_parent(p82, repo, store)
    failed = base.load_failed_aggregate(p82, repo, store); shallow = load_shallow_candidate(p82, repo, store, failed)
    if parent["artifact_digest"] != mechanism.PARENT_DIGEST or not runtime.identity_conforms(parent): raise SystemExit("wrong parent")
    if args.preflight_only:
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory); stage2 = seal_second_stage(p82, shallow, d / "stage2")
            reference = third_stage_conformance(mechanism.REFERENCE_ALLOCATOR, d / "reference")
            shallow3 = third_stage_conformance(shallow["allocator_source"], d / "shallow3")
        passed = not stage2["passed"] and reference["passed"] and not shallow3["passed"]
        print(json.dumps({"parent_digest": parent["artifact_digest"], "raw_run_sha256": RAW_RUN_SHA256,
            "shallow_binding_digest": shallow["binding_digest"], "second_stage": stage2,
            "third_stage_reference": reference, "shallow_third_stage": shallow3, "passed": passed}, indent=2, sort_keys=True)); return 0 if passed else 2
    if run.exists(): raise SystemExit("preserve existing OT-0098 evidence")
    run.mkdir(parents=True)
    (run / "bound-shallow-correction.json").write_text(json.dumps(shallow, indent=2, sort_keys=True) + "\n")
    stage2 = seal_second_stage(p82, shallow, run / "second-stage")
    (run / "second-stage-receipt.json").write_text(json.dumps(stage2, indent=2, sort_keys=True) + "\n")
    if stage2["passed"]: raise SystemExit("frozen shallow-failure prediction did not hold")
    erased = erase_second_stage(p82, stage2); position = mechanism.active_position(parent)
    context = typed.base.make_context(runtime, run, repo); started = time.time()
    active = run_corrector(p82, context, run, "active-second-correction", parent, shallow, stage2, position)
    implementation = assimilation = control = None; current = parent; promotion = None
    if active["score"]["correction_gate_passed"]:
        corrected = {**active["binding"], "third_stage_receipt_digest": active["score"]["receipt_digest"]}
        implementation = mechanism.run_implementation(prior89, p82, context, run, parent, corrected)
    else: corrected = None
    if implementation and implementation["world"]["developmentally_admitted"]:
        assimilation = mechanism.run_assimilation(prior89, p82, context, run, parent, corrected, implementation)
    if assimilation and assimilation["binding"]:
        current, promotion = promote(p82, parent, corrected, shallow, stage2, implementation, assimilation)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
        and current["continuation"]["status"] == "open" and len(current.get("allocation_machinery", [])) == len(parent.get("allocation_machinery", [])) + 1
        and len(current.get("allocation_corrections", [])) == len(parent.get("allocation_corrections", [])) + 1)
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control = run_corrector(p82, context, run, "erased-second-correction", parent, shallow, erased, position)
    control_conformant = bool(control and control["audit"]["conformant"] and control["binding"])
    control_reproduced = bool(control and control["score"]["correction_gate_passed"])
    causal = bool(operational and control_conformant and not control_reproduced)
    result = {"authority": "ot-0098-iterated-allocation-correction-driver", "source_subject_digest": parent["artifact_digest"],
        "raw_run_sha256": RAW_RUN_SHA256, "shallow_binding_digest": shallow["binding_digest"], "second_stage_receipt": stage2,
        "active_second_correction": p82.compact(active), "implementation": p82.compact(implementation) if implementation else None,
        "assimilation": p82.compact(assimilation) if assimilation else None, "erased_second_correction": p82.compact(control) if control else None,
        "promotion_receipt": promotion, "operational_transition_passed": operational, "outcome_content_causal_passed": causal,
        "erased_reproduced_correction": control_reproduced,
        "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
