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
BASE_PATH = ROOT / "ot_0098_iterated_allocation_correction.py"
BASE_SHA256 = "18d91c0e260b39e77c9f9882aa923bb547f6f7fe3426941be5128d5ad28fad71"
RAW_RUN_SHA256 = "c8dfca1f535bb362aa5b73a8b386f55fd41a0c00deaa3fbbabd973bb1300fe31"
AGGREGATE_SHA256 = "f44e8a49081964fc9447a79e375659a3869a3822aed735b9db073f020b35d447"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256: raise RuntimeError("OT-0098 implementation identity changed")
    name = "ot0099_frozen_ot0098"; spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


base = load_base(); prior = base.base; typed = base.typed; allocation = base.allocation; mechanism = base.mechanism


def load_second_revision(p82, repo, store):
    manifest, path = p82.materialize(repo, store, "OT-0098", "rejected-iterated-allocation-correction-run.json")
    if manifest["sha256"] != RAW_RUN_SHA256: raise RuntimeError("wrong OT-0098 run identity")
    prefix = "OT-0098/active-second-correction/actor-workspace/"
    with tarfile.open(path) as archive:
        source = base.read_member(archive, prefix + "allocate.py")
        choice = json.loads(base.read_member(archive, prefix + "choice.json"))
        correction = json.loads(base.read_member(archive, prefix + "correction.json"))
    manifest_a, aggregate_path = p82.materialize(repo, store, "OT-0098", "iterated-allocation-correction-aggregate.json")
    if manifest_a["sha256"] != AGGREGATE_SHA256: raise RuntimeError("wrong OT-0098 aggregate identity")
    aggregate = json.loads(aggregate_path.read_text()); score = aggregate["active_second_correction"]["score"]
    if score["correction_gate_passed"] or not score["grounded_revision"] or score["selected_contact_id"] != "joint":
        raise RuntimeError("wrong OT-0098 second revision")
    failed = prior.load_failed_aggregate(p82, repo, store); shallow = base.load_shallow_candidate(p82, repo, store, failed)
    contacts = shallow["frontier"]["contacts"]
    with tempfile.TemporaryDirectory() as directory:
        selected = mechanism.load_allocator(source, Path(directory))(copy.deepcopy(contacts))
    if selected != "joint" or not typed.valid_typed_choice(choice, contacts): raise RuntimeError("invalid second revision")
    body = {"authority": "ot-0099-derived-second-revision-binding", "source_subject_digest": mechanism.PARENT_DIGEST,
        "prior_binding_digest": shallow["binding_digest"], "frontier": shallow["frontier"],
        "allocator_source": source, "allocator_digest": p82.digest(source), "choice": choice,
        "correction": correction, "revision_derived": True}
    binding = {**body, "binding_digest": p82.digest(body)}
    receipt_body = {"authority": "ot-0098-sealed-third-stage-consequence", "second_revision_binding_digest": binding["binding_digest"],
        "fixture_rows": score["third_stage"]["fixture_rows"], "generic_source": score["third_stage"]["generic_source"],
        "passed": score["third_stage"]["passed"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    failed_ids = {row["fixture_id"] for row in receipt["fixture_rows"] if not row["passed"]}
    if failed_ids != {"threshold-regret", "threshold-equality"}: raise RuntimeError("wrong third-stage receipt")
    return binding, receipt


def erase_receipt(p82, receipt):
    removed = {"fixture_rows": receipt["fixture_rows"], "passed": receipt["passed"]}
    return {"authority": receipt["authority"], "second_revision_binding_digest": receipt["second_revision_binding_digest"],
        "receipt_digest": receipt["receipt_digest"], "generic_source": receipt["generic_source"],
        "fixture_ids": [row["fixture_id"] for row in receipt["fixture_rows"]], "fixture_count": len(receipt["fixture_rows"]),
        "outcome_erasure_digest": p82.digest(removed)}


def fourth_stage_fixtures():
    c = base.contact
    return [
        {"fixture_id": "boolean-threshold-a", "contacts": [c("omega", 2, 48, 17), c("alpha", 6, 48, 17)]},
        {"fixture_id": "boolean-threshold-b", "contacts": [c("alpha", 6, 48, 17), c("omega", 2, 48, 17)]},
        {"fixture_id": "positive-regret", "contacts": [c("small", 2, 58, 11), c("large", 2, 58, 41)]},
        {"fixture_id": "composition-dominates", "contacts": [c("immediate", 1, 180, 100), c("relation", 2, 28, 3)]},
        {"fixture_id": "composition-expansion", "contacts": [c("east", 2, 61, 9), c("west", 2, 79, 9)]},
        {"fixture_id": "reject-invalid", "contacts": [c("bad", 2, 190, 100, world_valid=False), c("good", 0, 7, 1)]},
        {"fixture_id": "reject-held-irreversible", "contacts": [c("held", 2, 190, 100, held_repeat=True), c("closed", 2, 180, 90, reversible=False), c("open", 0, 6, 1)]},
        {"fixture_id": "stable-id-a", "contacts": [c("beta", 2, 65, 21), c("theta", 2, 65, 21)]},
        {"fixture_id": "stable-id-b", "contacts": [c("theta", 2, 65, 21), c("beta", 2, 65, 21)]},
    ]


def fourth_stage_conformance(source, root):
    forbidden = ["boolean-threshold", "positive-regret", "composition-dominates", "omega", "theta", "operations/", "candidate.py"]
    generic = all(token not in source for token in forbidden)
    try:
        select = mechanism.load_allocator(source, root); rows = []
        for fixture in fourth_stage_fixtures():
            actual = select(copy.deepcopy(fixture["contacts"])); wanted = prior.expected(fixture["contacts"])
            rows.append({"fixture_id": fixture["fixture_id"], "expected": wanted, "actual": actual, "passed": actual == wanted})
        passed = generic and all(row["passed"] for row in rows)
    except Exception as error: rows, passed = [{"error_type": type(error).__name__, "passed": False}], False
    return {"generic_source": generic, "fixture_rows": rows, "passed": passed}


def run_corrector(p82, context, run, label, parent, second, receipt, position):
    seed = base.corrector_seed(run, label, parent, second, receipt, position)
    prompt = "Continue the exact subject by assimilating the latest sealed allocator consequence, improving its generic selection machinery when warranted, binding the resulting choice, running visible checks, inspecting the exact diff, and reporting truthfully."
    output, base_audit, workspace, _ = context.run_actor(label, seed, base.CORRECTOR_SCHEMA, prompt)
    try:
        source = (workspace / "allocate.py").read_text(); choice = json.loads((workspace / "choice.json").read_text())
        correction = json.loads((workspace / "correction.json").read_text())
    except (OSError, json.JSONDecodeError): source, choice, correction = "", None, None
    contacts = second["frontier"]["contacts"]
    try: selected = mechanism.load_allocator(source, workspace / "visible-allocator")(copy.deepcopy(contacts))
    except Exception: selected = None
    changed = set(base_audit["changed_paths"]); allowed = {"allocate.py", "choice.json", "correction.json"}
    artifact_valid = bool(base.valid_correction(correction) and typed.valid_typed_choice(choice, contacts)
        and selected == choice["contact_id"] and changed and changed.issubset(allowed) and "correction.json" in changed)
    audit = context.audit_actor(label, output, base_audit, artifact_valid, sorted(changed))
    failed_ids = {row["fixture_id"] for row in receipt.get("fixture_rows", []) if row.get("passed") is False}
    cited = set(correction.get("failed_fixture_ids", [])) if isinstance(correction, dict) else set()
    revised = source != second["allocator_source"]; grounded = bool(revised and len(cited) >= 2 and cited.issubset(failed_ids))
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0099-pre-fourth-stage-correction", "condition": label,
            "source_subject_digest": parent["artifact_digest"], "second_revision_binding_digest": second["binding_digest"],
            "third_stage_projection_digest": p82.digest(receipt), "actor_patch_digest": audit["patch_digest"],
            "frontier": second["frontier"], "allocator_source": source, "allocator_digest": p82.digest(source),
            "choice": choice, "correction": correction, "revision_derived": revised}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-correction.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    stage4 = fourth_stage_conformance(source, context.evidence(label) / "fourth-stage") if binding else {"passed": False}
    gate = bool(binding and grounded and stage4["passed"] and choice["contact_id"] == "joint")
    score = {"revision_derived": revised, "grounded_revision": grounded,
        "selected_contact_id": choice.get("contact_id") if isinstance(choice, dict) else None,
        "fourth_stage": stage4, "correction_gate_passed": gate}; score["receipt_digest"] = p82.digest(score)
    (context.evidence(label) / "correction-score.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding, "score": score}


def promote(p82, parent, correction, second, receipt3, implementation, assimilation):
    child, _ = allocation.promote(p82, parent, correction, implementation, assimilation); child.pop("artifact_digest", None)
    body = {"authority": "world-promoted-third-consequence-allocation-correction", "source_subject_digest": parent["artifact_digest"],
        "second_revision_binding_digest": second["binding_digest"], "third_stage_receipt_digest": receipt3["receipt_digest"],
        "correction_binding_digest": correction["binding_digest"], "fourth_stage_receipt_digest": correction["fourth_stage_receipt_digest"],
        "world_receipt_digest": implementation["world"]["receipt_digest"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"]}
    promotion = {**body, "receipt_digest": p82.digest(body)}
    child["allocation_corrections"] = [*child.get("allocation_corrections", []),
        {"second_revision_binding_digest": second["binding_digest"], "third_stage_receipt_digest": receipt3["receipt_digest"],
         "binding_digest": correction["binding_digest"], "correction": correction["correction"],
         "fourth_stage_receipt_digest": correction["fourth_stage_receipt_digest"]}]
    return p82.seal(child), promotion


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0099").resolve()
    prior92 = mechanism.load_prior(); _, prior90, prior89, p82 = mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store); parent = mechanism.load_parent(p82, repo, store); second, receipt3 = load_second_revision(p82, repo, store)
    if parent["artifact_digest"] != mechanism.PARENT_DIGEST or not runtime.identity_conforms(parent): raise SystemExit("wrong parent")
    if args.preflight_only:
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory); reference = fourth_stage_conformance(mechanism.REFERENCE_ALLOCATOR, d / "reference")
            prior_result = fourth_stage_conformance(second["allocator_source"], d / "prior")
        passed = reference["passed"] and not prior_result["passed"] and not receipt3["passed"]
        print(json.dumps({"parent_digest": parent["artifact_digest"], "raw_run_sha256": RAW_RUN_SHA256,
            "aggregate_sha256": AGGREGATE_SHA256, "second_revision_binding_digest": second["binding_digest"],
            "third_stage_receipt": receipt3, "fourth_stage_reference": reference,
            "prior_fourth_stage": prior_result, "passed": passed}, indent=2, sort_keys=True)); return 0 if passed else 2
    if run.exists(): raise SystemExit("preserve existing OT-0099 evidence")
    run.mkdir(parents=True); (run / "bound-second-revision.json").write_text(json.dumps(second, indent=2, sort_keys=True) + "\n")
    (run / "third-stage-receipt.json").write_text(json.dumps(receipt3, indent=2, sort_keys=True) + "\n")
    erased = erase_receipt(p82, receipt3); position = mechanism.active_position(parent); context = typed.base.make_context(runtime, run, repo); started = time.time()
    active = run_corrector(p82, context, run, "active-third-correction", parent, second, receipt3, position)
    implementation = assimilation = control = None; current = parent; promotion = None
    if active["score"]["correction_gate_passed"]:
        corrected = {**active["binding"], "fourth_stage_receipt_digest": active["score"]["receipt_digest"]}
        implementation = mechanism.run_implementation(prior89, p82, context, run, parent, corrected)
    else: corrected = None
    if implementation and implementation["world"]["developmentally_admitted"]:
        assimilation = mechanism.run_assimilation(prior89, p82, context, run, parent, corrected, implementation)
    if assimilation and assimilation["binding"]: current, promotion = promote(p82, parent, corrected, second, receipt3, implementation, assimilation)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
        and current["continuation"]["status"] == "open" and len(current.get("allocation_machinery", [])) == len(parent.get("allocation_machinery", [])) + 1
        and len(current.get("allocation_corrections", [])) == len(parent.get("allocation_corrections", [])) + 1)
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control = run_corrector(p82, context, run, "erased-third-correction", parent, second, erased, position)
    control_conformant = bool(control and control["audit"]["conformant"] and control["binding"]); control_reproduced = bool(control and control["score"]["correction_gate_passed"])
    causal = bool(operational and control_conformant and not control_reproduced)
    result = {"authority": "ot-0099-third-consequence-allocation-correction-driver", "source_subject_digest": parent["artifact_digest"],
        "second_revision_binding_digest": second["binding_digest"], "third_stage_receipt": receipt3,
        "active_third_correction": p82.compact(active), "implementation": p82.compact(implementation) if implementation else None,
        "assimilation": p82.compact(assimilation) if assimilation else None, "erased_third_correction": p82.compact(control) if control else None,
        "promotion_receipt": promotion, "operational_transition_passed": operational, "outcome_content_causal_passed": causal,
        "erased_reproduced_correction": control_reproduced,
        "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3)}; result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n"); (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
