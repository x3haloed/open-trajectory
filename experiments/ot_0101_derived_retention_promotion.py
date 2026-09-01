from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent; REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0100_threshold_corrected_allocation.py"
BASE_SHA256 = "fecab3e411cd32fb21916fd4bc262d6b7adee23a0a3d109862d8c925be2073e6"
AGGREGATE_SHA256 = "698f1bfd37f47e57f023da83ab3f1d1f007d617a54502ebae528f8cd2527b409"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0101-assimilator.schema.json"
ASSIMILATION_KEYS = {"consequence_summary", "settled_case_ids", "remaining_uncertainty", "selection_rule_update", "surrender_condition"}
PLACEHOLDER = "__REPLACE__"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256: raise RuntimeError("OT-0100 implementation identity changed")
    name = "ot0101_frozen_ot0100"; spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


base = load_base(); previous = base.base; typed = base.typed; allocation = base.allocation; mechanism = base.mechanism


def load_admitted_chain(p82, repo, store):
    manifest, path = p82.materialize(repo, store, "OT-0100", "threshold-corrected-allocation-aggregate.json")
    if manifest["sha256"] != AGGREGATE_SHA256: raise RuntimeError("wrong OT-0100 aggregate identity")
    aggregate = json.loads(path.read_text()); active = aggregate["active_fourth_correction"]; implementation = aggregate["implementation"]
    if (not active["audit"]["conformant"] or not active["score"]["correction_gate_passed"]
            or not implementation["audit"]["conformant"] or not implementation["world"]["developmentally_admitted"]
            or aggregate["operational_transition_passed"]):
        raise RuntimeError("OT-0100 aggregate does not contain exact admitted pre-promotion chain")
    corrected = {**active["binding"], "fifth_stage_receipt_digest": active["score"]["receipt_digest"]}
    return aggregate, corrected, implementation


def assimilation_template():
    return {"consequence_summary": PLACEHOLDER, "settled_case_ids": [], "remaining_uncertainty": PLACEHOLDER,
            "selection_rule_update": PLACEHOLDER, "surrender_condition": PLACEHOLDER}


def valid_assimilation(value: Any) -> bool:
    return bool(isinstance(value, dict) and set(value) == ASSIMILATION_KEYS
        and isinstance(value.get("settled_case_ids"), list) and value["settled_case_ids"]
        and all(isinstance(item, str) and item for item in value["settled_case_ids"])
        and all(isinstance(value.get(key), str) and value[key].strip() and PLACEHOLDER not in value[key]
                for key in ASSIMILATION_KEYS - {"settled_case_ids"}))


def assimilation_seed(prior89, run, parent, corrected, implementation):
    seed = run / "assimilation-seed"; seed.mkdir()
    position = {"subject_digest": parent["artifact_digest"], "continuation": parent["continuation"],
        "developmental_selector": parent["developmental_selector"], "corrected_allocation": corrected,
        "implementation_binding": implementation["binding"], "complete_consequence": implementation["world"]}
    (seed / "subject-allocation-consequence.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "allocate.py").write_text(corrected["allocator_source"])
    (seed / "allocation-assimilation.json").write_text(json.dumps(assimilation_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    contract = {"editable": ["allocation-assimilation.json", "successor-opening.json"], "immutable": ["allocate.py"],
        "retention": "derived from exact unchanged allocator bytes", "settled_ids": "cite passed public and hidden rows; include at least one from each partition"}
    (seed / "assimilation-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": contract["editable"], "immutable": contract["immutable"]}, indent=2) + "\n")
    (seed / "README.md").write_text("Assimilate the complete corrected-allocation consequence. Allocator retention is derived from unchanged bytes. Cite passed rows from both public and hidden partitions, preserve uncertainty, author the substantive opening now worth carrying, edit exactly the two permitted JSON files, and inspect the diff.\n")
    return seed


def run_assimilation(prior89, p82, context, run, parent, corrected, implementation):
    seed = assimilation_seed(prior89, run, parent, corrected, implementation)
    prompt = "Assimilate the complete corrected-allocation consequence with ordinary tools. Keep immutable allocator bytes, cite passed public and hidden cases, preserve uncertainty, author the next substantive opening, edit exactly the two permitted files, inspect the diff, and report truthfully."
    output, base_audit, workspace, _ = context.run_actor("assimilation", seed, ASSIMILATOR_SCHEMA, prompt)
    try:
        value = json.loads((workspace / "allocation-assimilation.json").read_text()); opening = json.loads((workspace / "successor-opening.json").read_text())
        allocator_retained = (workspace / "allocate.py").read_text() == corrected["allocator_source"]
    except (OSError, json.JSONDecodeError): value, opening, allocator_retained = None, None, False
    valid = bool(valid_assimilation(value) and prior89.valid_successor(opening) and allocator_retained
                 and opening["next_opening"] != mechanism.INHERITED_OPENING)
    audit = context.audit_actor("assimilation", output, base_audit, valid, ["allocation-assimilation.json", "successor-opening.json"])
    public_ids = {row["case_id"] for row in implementation["world"]["public"]["rows"] if row["score"] == row["oracle_score"]}
    hidden_ids = {row["case_id"] for row in implementation["world"]["hidden"]["rows"] if row["score"] == row["oracle_score"]}
    cited = set(value["settled_case_ids"]) if isinstance(value, dict) and isinstance(value.get("settled_case_ids"), list) else set()
    grounded = bool(audit["conformant"] and cited.issubset(public_ids | hidden_ids) and cited & public_ids and cited & hidden_ids)
    binding = None
    if grounded:
        body = {"authority": "ot-0101-derived-retention-assimilation", "source_subject_digest": parent["artifact_digest"],
            "correction_binding_digest": corrected["binding_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"], "allocator_retention_derived": allocator_retained,
            "assimilation": value, "successor_opening": opening}
        binding = {**body, "binding_digest": p82.digest(body)}; (context.evidence("assimilation") / "bound-assimilation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "allocator_retention_derived": allocator_retained, "grounded": grounded, "binding": binding}


def correction_history(aggregate, corrected):
    return [{"stage": "initial-failure", "binding_digest": "8a523855dec2b6f4e1056fc78e2cc094c427368b302feca06a7424c6bfbf94ae"},
        {"stage": "shallow-revision", "binding_digest": "29e0780a5f65b27834f65dc1c5ed74e6fb12b739647773a7fb55773b3165b7a8"},
        {"stage": "second-revision", "binding_digest": "b7db8284646198ac3185b59f4e8cc72e04c6c8d525238a523a16ef49279ea0d8"},
        {"stage": "third-revision", "binding_digest": aggregate["third_revision_binding_digest"]},
        {"stage": "fourth-revision", "binding_digest": corrected["binding_digest"],
         "fifth_stage_receipt_digest": corrected["fifth_stage_receipt_digest"]}]


def promote(p82, parent, aggregate, corrected, implementation, assimilation):
    child, _ = allocation.promote(p82, parent, corrected, implementation, assimilation); child.pop("artifact_digest", None)
    history = correction_history(aggregate, corrected)
    body = {"authority": "world-promoted-derived-retention-correction-chain", "source_subject_digest": parent["artifact_digest"],
        "correction_binding_digest": corrected["binding_digest"], "world_receipt_digest": implementation["world"]["receipt_digest"],
        "assimilation_binding_digest": assimilation["binding"]["binding_digest"], "correction_history_digest": p82.digest(history)}
    receipt = {**body, "receipt_digest": p82.digest(body)}; child["allocation_correction_history"] = history
    return p82.seal(child), receipt


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0101").resolve()
    prior92 = mechanism.load_prior(); _, prior90, prior89, p82 = mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = mechanism.load_parent(p82, repo, store); aggregate, corrected, implementation = load_admitted_chain(p82, repo, store)
    third, receipt4 = base.load_third_revision(p82, repo, store); erased = base.erase_receipt(p82, receipt4)
    if parent["artifact_digest"] != mechanism.PARENT_DIGEST or not runtime.identity_conforms(parent): raise SystemExit("wrong parent")
    if args.preflight_only:
        public_ids = {row["case_id"] for row in implementation["world"]["public"]["rows"]}; hidden_ids = {row["case_id"] for row in implementation["world"]["hidden"]["rows"]}
        result = {"parent_digest": parent["artifact_digest"], "aggregate_sha256": AGGREGATE_SHA256,
            "correction_binding_digest": corrected["binding_digest"], "implementation_admitted": implementation["world"]["developmentally_admitted"],
            "public_ids": sorted(public_ids), "hidden_ids": sorted(hidden_ids), "passed": bool(public_ids and hidden_ids)}
        print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0101 evidence")
    run.mkdir(parents=True); (run / "bound-corrected-allocation.json").write_text(json.dumps(corrected, indent=2, sort_keys=True) + "\n")
    (run / "admitted-implementation.json").write_text(json.dumps(implementation, indent=2, sort_keys=True) + "\n")
    context = typed.base.make_context(runtime, run, repo); started = time.time(); assimilation = run_assimilation(prior89, p82, context, run, parent, corrected, implementation)
    current = parent; promotion = control = None
    if assimilation["binding"]: current, promotion = promote(p82, parent, aggregate, corrected, implementation, assimilation)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open"
        and current["continuation"]["next_opening"] == assimilation["binding"]["successor_opening"]["next_opening"]
        and len(current.get("allocation_machinery", [])) == len(parent.get("allocation_machinery", [])) + 1 and len(current.get("allocation_correction_history", [])) == 5)
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        position = mechanism.active_position(parent); control = base.run_corrector(p82, context, run, "erased-fourth-correction", parent, third, erased, position)
    control_conformant = bool(control and control["audit"]["conformant"] and control["binding"]); control_reproduced = bool(control and control["score"]["correction_gate_passed"])
    causal = bool(operational and control_conformant and not control_reproduced)
    result = {"authority": "ot-0101-derived-retention-promotion-driver", "source_subject_digest": parent["artifact_digest"],
        "correction_binding_digest": corrected["binding_digest"], "assimilation": p82.compact(assimilation),
        "erased_fourth_correction": p82.compact(control) if control else None, "promotion_receipt": promotion,
        "operational_transition_passed": operational, "outcome_content_causal_passed": causal, "erased_reproduced_correction": control_reproduced,
        "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost", "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time() - started, 3)}; result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n"); (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
