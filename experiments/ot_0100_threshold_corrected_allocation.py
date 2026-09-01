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


ROOT = Path(__file__).parent; REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0099_third_consequence_allocation_correction.py"
BASE_SHA256 = "1115144202c71d898ffcdc347a1d5939416a2323b7abe4ddfce810374d50baa0"
RAW_RUN_SHA256 = "50a03d5a5e4d5b361f4a8f95388d6520bfecb91db005e4d8fb7956079adc2037"
AGGREGATE_SHA256 = "b8245e313ff102c75f2e7b7ba319b4f420920723f42e9327eb2ba4a6df550f58"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256: raise RuntimeError("OT-0099 implementation identity changed")
    name = "ot0100_frozen_ot0099"; spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


base = load_base(); previous = base.base; prior = base.prior; typed = base.typed; allocation = base.allocation; mechanism = base.mechanism


def load_third_revision(p82, repo, store):
    manifest, path = p82.materialize(repo, store, "OT-0099", "rejected-third-consequence-correction-run.json")
    if manifest["sha256"] != RAW_RUN_SHA256: raise RuntimeError("wrong OT-0099 run identity")
    prefix = "OT-0099/active-third-correction/actor-workspace/"
    with tarfile.open(path) as archive:
        source = previous.read_member(archive, prefix + "allocate.py")
        choice = json.loads(previous.read_member(archive, prefix + "choice.json"))
        correction = json.loads(previous.read_member(archive, prefix + "correction.json"))
    manifest_a, aggregate_path = p82.materialize(repo, store, "OT-0099", "third-consequence-correction-aggregate.json")
    if manifest_a["sha256"] != AGGREGATE_SHA256: raise RuntimeError("wrong OT-0099 aggregate identity")
    aggregate = json.loads(aggregate_path.read_text()); score = aggregate["active_third_correction"]["score"]
    second, _ = base.load_second_revision(p82, repo, store); contacts = second["frontier"]["contacts"]
    with tempfile.TemporaryDirectory() as directory:
        selected = mechanism.load_allocator(source, Path(directory))(copy.deepcopy(contacts))
    if selected != "joint" or not typed.valid_typed_choice(choice, contacts) or not score["grounded_revision"]:
        raise RuntimeError("invalid OT-0099 third revision")
    body = {"authority": "ot-0100-derived-third-revision-binding", "source_subject_digest": mechanism.PARENT_DIGEST,
        "prior_binding_digest": second["binding_digest"], "frontier": second["frontier"],
        "allocator_source": source, "allocator_digest": p82.digest(source), "choice": choice,
        "correction": correction, "revision_derived": True}
    binding = {**body, "binding_digest": p82.digest(body)}
    receipt_body = {"authority": "ot-0099-sealed-fourth-stage-consequence", "third_revision_binding_digest": binding["binding_digest"],
        "fixture_rows": score["fourth_stage"]["fixture_rows"], "generic_source": score["fourth_stage"]["generic_source"],
        "passed": score["fourth_stage"]["passed"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    if {row["fixture_id"] for row in receipt["fixture_rows"] if not row["passed"]} != {"boolean-threshold-a", "boolean-threshold-b"}:
        raise RuntimeError("wrong fourth-stage receipt")
    return binding, receipt


def erase_receipt(p82, receipt):
    removed = {"fixture_rows": receipt["fixture_rows"], "passed": receipt["passed"]}
    return {"authority": receipt["authority"], "third_revision_binding_digest": receipt["third_revision_binding_digest"],
        "receipt_digest": receipt["receipt_digest"], "generic_source": receipt["generic_source"],
        "fixture_ids": [row["fixture_id"] for row in receipt["fixture_rows"]], "fixture_count": len(receipt["fixture_rows"]),
        "outcome_erasure_digest": p82.digest(removed)}


def fifth_stage_fixtures():
    c = previous.contact
    return [
        {"fixture_id": "threshold-final-a", "contacts": [c("zenith", 2, 52, 19), c("apex", 7, 52, 19)]},
        {"fixture_id": "threshold-final-b", "contacts": [c("apex", 7, 52, 19), c("zenith", 2, 52, 19)]},
        {"fixture_id": "composition-final", "contacts": [c("instant", 1, 210, 120), c("synthesis", 2, 31, 4)]},
        {"fixture_id": "expansion-final", "contacts": [c("lower", 2, 63, 15), c("higher", 2, 88, 15)]},
        {"fixture_id": "regret-final", "contacts": [c("minor", 2, 72, 13), c("major", 2, 72, 49)]},
        {"fixture_id": "filters-final", "contacts": [c("invalid", 3, 220, 130, world_valid=False), c("held", 2, 215, 125, held_repeat=True), c("closed", 2, 205, 115, reversible=False), c("viable", 0, 5, 1)]},
        {"fixture_id": "stable-final-a", "contacts": [c("gamma", 2, 77, 23), c("sigma", 2, 77, 23)]},
        {"fixture_id": "stable-final-b", "contacts": [c("sigma", 2, 77, 23), c("gamma", 2, 77, 23)]},
    ]


def fifth_stage_conformance(source, root):
    forbidden = ["threshold-final", "composition-final", "regret-final", "zenith", "sigma", "operations/", "candidate.py"]
    generic = all(token not in source for token in forbidden)
    try:
        select = mechanism.load_allocator(source, root); rows = []
        for fixture in fifth_stage_fixtures():
            actual = select(copy.deepcopy(fixture["contacts"])); wanted = prior.expected(fixture["contacts"])
            rows.append({"fixture_id": fixture["fixture_id"], "expected": wanted, "actual": actual, "passed": actual == wanted})
        passed = generic and all(row["passed"] for row in rows)
    except Exception as error: rows, passed = [{"error_type": type(error).__name__, "passed": False}], False
    return {"generic_source": generic, "fixture_rows": rows, "passed": passed}


def run_corrector(p82, context, run, label, parent, third, receipt, position):
    seed = previous.corrector_seed(run, label, parent, third, receipt, position)
    prompt = "Continue the exact subject by assimilating the latest sealed allocator consequence, improving its generic selection machinery when warranted, binding the resulting choice, running visible checks, inspecting the exact diff, and reporting truthfully."
    output, base_audit, workspace, _ = context.run_actor(label, seed, previous.CORRECTOR_SCHEMA, prompt)
    try:
        source = (workspace / "allocate.py").read_text(); choice = json.loads((workspace / "choice.json").read_text()); correction = json.loads((workspace / "correction.json").read_text())
    except (OSError, json.JSONDecodeError): source, choice, correction = "", None, None
    contacts = third["frontier"]["contacts"]
    try: selected = mechanism.load_allocator(source, workspace / "visible-allocator")(copy.deepcopy(contacts))
    except Exception: selected = None
    changed = set(base_audit["changed_paths"]); allowed = {"allocate.py", "choice.json", "correction.json"}
    artifact_valid = bool(previous.valid_correction(correction) and typed.valid_typed_choice(choice, contacts)
        and selected == choice["contact_id"] and changed and changed.issubset(allowed) and "correction.json" in changed)
    audit = context.audit_actor(label, output, base_audit, artifact_valid, sorted(changed))
    failed_ids = {row["fixture_id"] for row in receipt.get("fixture_rows", []) if row.get("passed") is False}; cited = set(correction.get("failed_fixture_ids", [])) if isinstance(correction, dict) else set()
    revised = source != third["allocator_source"]; grounded = bool(revised and len(cited) >= 2 and cited.issubset(failed_ids))
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0100-pre-fifth-stage-correction", "condition": label,
            "source_subject_digest": parent["artifact_digest"], "third_revision_binding_digest": third["binding_digest"],
            "fourth_stage_projection_digest": p82.digest(receipt), "actor_patch_digest": audit["patch_digest"],
            "frontier": third["frontier"], "allocator_source": source, "allocator_digest": p82.digest(source),
            "choice": choice, "correction": correction, "revision_derived": revised}
        binding = {**body, "binding_digest": p82.digest(body)}; (context.evidence(label) / "bound-correction.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    stage5 = fifth_stage_conformance(source, context.evidence(label) / "fifth-stage") if binding else {"passed": False}
    gate = bool(binding and grounded and stage5["passed"] and choice["contact_id"] == "joint")
    score = {"revision_derived": revised, "grounded_revision": grounded, "selected_contact_id": choice.get("contact_id") if isinstance(choice, dict) else None,
        "fifth_stage": stage5, "correction_gate_passed": gate}; score["receipt_digest"] = p82.digest(score)
    (context.evidence(label) / "correction-score.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding, "score": score}


def promote(p82, parent, correction, third, receipt4, implementation, assimilation):
    child, _ = allocation.promote(p82, parent, correction, implementation, assimilation); child.pop("artifact_digest", None)
    body = {"authority": "world-promoted-threshold-corrected-allocation", "source_subject_digest": parent["artifact_digest"],
        "third_revision_binding_digest": third["binding_digest"], "fourth_stage_receipt_digest": receipt4["receipt_digest"],
        "correction_binding_digest": correction["binding_digest"], "fifth_stage_receipt_digest": correction["fifth_stage_receipt_digest"],
        "world_receipt_digest": implementation["world"]["receipt_digest"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"]}
    promotion = {**body, "receipt_digest": p82.digest(body)}
    child["allocation_corrections"] = [*child.get("allocation_corrections", []), {"third_revision_binding_digest": third["binding_digest"],
        "fourth_stage_receipt_digest": receipt4["receipt_digest"], "binding_digest": correction["binding_digest"],
        "correction": correction["correction"], "fifth_stage_receipt_digest": correction["fifth_stage_receipt_digest"]}]
    return p82.seal(child), promotion


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0100").resolve()
    prior92 = mechanism.load_prior(); _, prior90, prior89, p82 = mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = mechanism.load_parent(p82, repo, store); third, receipt4 = load_third_revision(p82, repo, store)
    if parent["artifact_digest"] != mechanism.PARENT_DIGEST or not runtime.identity_conforms(parent): raise SystemExit("wrong parent")
    if args.preflight_only:
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory); reference = fifth_stage_conformance(mechanism.REFERENCE_ALLOCATOR, d / "reference"); prior_result = fifth_stage_conformance(third["allocator_source"], d / "prior")
        passed = reference["passed"] and not prior_result["passed"] and not receipt4["passed"]
        print(json.dumps({"parent_digest": parent["artifact_digest"], "third_revision_binding_digest": third["binding_digest"],
            "fourth_stage_receipt": receipt4, "fifth_stage_reference": reference, "prior_fifth_stage": prior_result, "passed": passed}, indent=2, sort_keys=True)); return 0 if passed else 2
    if run.exists(): raise SystemExit("preserve existing OT-0100 evidence")
    run.mkdir(parents=True); (run / "bound-third-revision.json").write_text(json.dumps(third, indent=2, sort_keys=True) + "\n"); (run / "fourth-stage-receipt.json").write_text(json.dumps(receipt4, indent=2, sort_keys=True) + "\n")
    erased = erase_receipt(p82, receipt4); position = mechanism.active_position(parent); context = typed.base.make_context(runtime, run, repo); started = time.time()
    active = run_corrector(p82, context, run, "active-fourth-correction", parent, third, receipt4, position)
    implementation = assimilation = control = None; current = parent; promotion = None
    if active["score"]["correction_gate_passed"]:
        corrected = {**active["binding"], "fifth_stage_receipt_digest": active["score"]["receipt_digest"]}; implementation = mechanism.run_implementation(prior89, p82, context, run, parent, corrected)
    else: corrected = None
    if implementation and implementation["world"]["developmentally_admitted"]: assimilation = mechanism.run_assimilation(prior89, p82, context, run, parent, corrected, implementation)
    if assimilation and assimilation["binding"]: current, promotion = promote(p82, parent, corrected, third, receipt4, implementation, assimilation)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open"
        and len(current.get("allocation_machinery", [])) == len(parent.get("allocation_machinery", [])) + 1 and len(current.get("allocation_corrections", [])) == len(parent.get("allocation_corrections", [])) + 1)
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n"); control = run_corrector(p82, context, run, "erased-fourth-correction", parent, third, erased, position)
    control_conformant = bool(control and control["audit"]["conformant"] and control["binding"]); control_reproduced = bool(control and control["score"]["correction_gate_passed"]); causal = bool(operational and control_conformant and not control_reproduced)
    result = {"authority": "ot-0100-threshold-corrected-allocation-driver", "source_subject_digest": parent["artifact_digest"], "third_revision_binding_digest": third["binding_digest"],
        "fourth_stage_receipt": receipt4, "active_fourth_correction": p82.compact(active), "implementation": p82.compact(implementation) if implementation else None,
        "assimilation": p82.compact(assimilation) if assimilation else None, "erased_fourth_correction": p82.compact(control) if control else None,
        "promotion_receipt": promotion, "operational_transition_passed": operational, "outcome_content_causal_passed": causal,
        "erased_reproduced_correction": control_reproduced, "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost", "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time() - started, 3)}; result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n"); (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
