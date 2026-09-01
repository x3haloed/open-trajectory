from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0096_typed_choice_self_allocation.py"
BASE_SHA256 = "16a54b0c91163e33efe0a644ec9de81c60b6108aa87b22be9065276746d462ee"
FAILED_AGGREGATE_SHA256 = "2e2b637221abecf8d072a1d33d7a4509a0786c2487bafb7bae3357b4b1cf61f3"
CORRECTOR_SCHEMA = REPO / "spec/ot-0097-corrector.schema.json"
CORRECTION_KEYS = {"disposition", "failed_fixture_ids", "correction_summary", "remaining_uncertainty", "surrender_condition"}
PLACEHOLDER = "__REPLACE__"
FIXTURE_IDS = ["real-order", "real-reversed", "renamed", "world-invalid", "stable-tie"]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0096 implementation identity changed")
    name = "ot0097_frozen_ot0096"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
allocation = base.allocation
mechanism = base.mechanism


def load_failed_aggregate(p82, repo: Path, store: Path) -> dict[str, Any]:
    manifest, path = p82.materialize(repo, store, "OT-0096", "typed-choice-self-allocation-aggregate.json")
    if manifest["sha256"] != FAILED_AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0096 aggregate identity")
    value = json.loads(path.read_text())
    active = value["active_allocation"]
    if (value["source_subject_digest"] != mechanism.PARENT_DIGEST or value["operational_transition_passed"]
            or not active["audit"]["conformant"] or active["binding"]["choice"]["contact_id"] != "recovery"
            or active["score"]["hidden_allocator"]["passed"]):
        raise RuntimeError("OT-0096 aggregate does not contain the frozen failed event")
    return value


def named_receipt(failed: dict[str, Any]) -> dict[str, Any]:
    hidden = failed["active_allocation"]["score"]["hidden_allocator"]
    rows = [{"fixture_id": fixture_id, **row} for fixture_id, row in zip(FIXTURE_IDS, hidden["fixture_outcomes"])]
    return {"authority": "ot-0096-sealed-first-stage-allocator-consequence",
            "source_receipt_digest": failed["active_allocation"]["score"]["receipt_digest"],
            "generic_source": hidden["generic_source"], "fixture_rows": rows,
            "passed": hidden["passed"]}


def erased_receipt(p82, receipt: dict[str, Any]) -> dict[str, Any]:
    removed = {"fixture_rows": receipt["fixture_rows"], "passed": receipt["passed"]}
    return {"authority": receipt["authority"], "source_receipt_digest": receipt["source_receipt_digest"],
            "generic_source": receipt["generic_source"], "fixture_ids": FIXTURE_IDS,
            "fixture_count": len(FIXTURE_IDS), "outcome_erasure_digest": p82.digest(removed)}


def projection_conformance(p82, receipt: dict[str, Any], erased: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(erased, sort_keys=True)
    result = {"same_authority": receipt["authority"] == erased["authority"],
              "same_receipt_identity": receipt["source_receipt_digest"] == erased["source_receipt_digest"],
              "same_fixture_identity": [row["fixture_id"] for row in receipt["fixture_rows"]] == erased["fixture_ids"],
              "outcomes_absent": all(token not in text for token in ('"actual"', '"expected"', '"passed"')),
              "active_digest": p82.digest(receipt), "erased_digest": p82.digest(erased)}
    result["passed"] = all(result[key] for key in ("same_authority", "same_receipt_identity", "same_fixture_identity", "outcomes_absent"))
    return result


def contact(contact_id: str, floors: int, expansion: float, regret: float, **overrides) -> dict[str, Any]:
    row = {"id": contact_id, "completed_floors": [f"floor-{index}" for index in range(floors)],
           "predicted_expansion": expansion, "public_regret": regret, "world_valid": True,
           "reversible": True, "held_repeat": False, "world_contact": True,
           "target_path": "candidate.py", "target_symbol": "choose",
           "surrender_condition": "surrender on contradiction"}
    return {**row, **overrides}


def second_stage_fixtures() -> list[dict[str, Any]]:
    return [
        {"fixture_id": "composition-over-gain", "contacts": [contact("solo", 0, 100, 100), contact("compose", 2, 40, 10)]},
        {"fixture_id": "composition-expansion", "contacts": [contact("low", 2, 40, 20), contact("high", 2, 60, 20)]},
        {"fixture_id": "composition-regret", "contacts": [contact("low-regret", 2, 50, 10), contact("high-regret", 2, 50, 30)]},
        {"fixture_id": "invalid-composition", "contacts": [contact("invalid", 2, 100, 100, world_valid=False), contact("valid", 0, 10, 10)]},
        {"fixture_id": "held-composition", "contacts": [contact("held", 2, 100, 100, held_repeat=True), contact("valid", 0, 10, 10)]},
        {"fixture_id": "threshold-not-count", "contacts": [contact("zeta", 2, 50, 20), contact("alpha", 3, 50, 20)]},
        {"fixture_id": "stable-tie", "contacts": [contact("alpha", 2, 50, 20), contact("zeta", 2, 50, 20)]},
    ]


def expected(rows: list[dict[str, Any]]) -> str:
    live = [row for row in rows if row["world_valid"] and row["reversible"] and not row["held_repeat"]]
    return max(live, key=lambda row: (len(row["completed_floors"]) >= 2,
                                       row["predicted_expansion"], row["public_regret"], row["id"]))["id"]


def second_stage_conformance(source: str, root: Path) -> dict[str, Any]:
    forbidden = ["composition-over-gain", "composition-expansion", "composition-regret", "threshold-not-count",
                 "recovery", "joint", "operations/", "candidate.py", "solo", "compose"]
    generic = all(token not in source for token in forbidden)
    try:
        select = mechanism.load_allocator(source, root)
        rows = []
        for fixture in second_stage_fixtures():
            actual = select(copy.deepcopy(fixture["contacts"])); wanted = expected(fixture["contacts"])
            rows.append({"fixture_id": fixture["fixture_id"], "expected": wanted, "actual": actual, "passed": actual == wanted})
        passed = generic and all(row["passed"] for row in rows)
    except Exception as error:
        rows, passed = [{"error_type": type(error).__name__, "passed": False}], False
    return {"generic_source": generic, "fixture_rows": rows, "passed": passed}


def correction_template() -> dict[str, Any]:
    return {"disposition": PLACEHOLDER, "failed_fixture_ids": [], "correction_summary": PLACEHOLDER,
            "remaining_uncertainty": PLACEHOLDER, "surrender_condition": PLACEHOLDER}


def valid_correction(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != CORRECTION_KEYS or value.get("disposition") not in {"retain", "revise"}:
        return False
    if not isinstance(value.get("failed_fixture_ids"), list) or not all(isinstance(item, str) for item in value["failed_fixture_ids"]):
        return False
    return all(isinstance(value.get(key), str) and value[key].strip() and PLACEHOLDER not in value[key]
               for key in CORRECTION_KEYS - {"failed_fixture_ids", "disposition"})


def corrector_seed(run: Path, label: str, parent: dict[str, Any], failed: dict[str, Any],
                   receipt: dict[str, Any], position: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"; seed.mkdir()
    mechanism.write_world(seed, parent)
    binding = failed["active_allocation"]["binding"]
    (seed / "subject-position.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "failed-allocation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    (seed / "allocator-consequence.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (seed / "allocate.py").write_text(binding["allocator_source"])
    (seed / "choice.json").write_text(json.dumps(binding["choice"], indent=2, sort_keys=True) + "\n")
    (seed / "correction.json").write_text(json.dumps(correction_template(), indent=2, sort_keys=True) + "\n")
    contract = {"editable": ["allocate.py", "choice.json", "correction.json"],
        "allocator_abi": "select(contacts) -> contact id", "choice_types": "OT-0096 typed choice ABI",
        "instruction": "Use the sealed consequence if present. Retain or revise the generic allocator, make choice equal its live-frontier output, and ground revisions in genuinely failed fixture ids."}
    (seed / "correction-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": contract["editable"]}, indent=2) + "\n")
    (seed / "README.md").write_text("Continue the exact subject by assimilating its allocator consequence. Correct selection machinery when warranted, preserve the bound live frontier and world, run useful visible checks, inspect the exact diff, and edit exactly the three permitted files.\n")
    return seed


def run_corrector(p82, context, run: Path, label: str, parent: dict[str, Any], failed: dict[str, Any],
                  receipt: dict[str, Any], position: dict[str, Any]) -> dict[str, Any]:
    seed = corrector_seed(run, label, parent, failed, receipt, position)
    prompt = "Continue the exact subject by assimilating the sealed allocator consequence, retaining or revising its generic selection machinery, binding the resulting live-frontier choice, running useful visible checks, inspecting the exact diff, and reporting truthfully."
    output, base_audit, workspace, _ = context.run_actor(label, seed, CORRECTOR_SCHEMA, prompt)
    original = failed["active_allocation"]["binding"]
    try:
        source = (workspace / "allocate.py").read_text()
        choice = json.loads((workspace / "choice.json").read_text())
        correction = json.loads((workspace / "correction.json").read_text())
    except (OSError, json.JSONDecodeError):
        source, choice, correction = "", None, None
    contacts = original["frontier"]["contacts"]
    try:
        selected = mechanism.load_allocator(source, workspace / "visible-allocator")(copy.deepcopy(contacts))
    except Exception:
        selected = None
    artifact_valid = bool(valid_correction(correction) and base.valid_typed_choice(choice, contacts)
                          and selected == choice["contact_id"] and source)
    audit = context.audit_actor(label, output, base_audit, artifact_valid, ["allocate.py", "choice.json", "correction.json"])
    full_rows = receipt.get("fixture_rows", [])
    truly_failed = {row["fixture_id"] for row in full_rows if row.get("passed") is False}
    cited = set(correction.get("failed_fixture_ids", [])) if isinstance(correction, dict) else set()
    grounded_revision = bool(correction and correction["disposition"] == "revise" and source != original["allocator_source"]
                             and len(cited) >= 2 and cited.issubset(truly_failed))
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0097-pre-second-stage-allocator-correction", "condition": label,
                "source_subject_digest": parent["artifact_digest"], "failed_allocation_binding_digest": original["binding_digest"],
                "consequence_projection_digest": p82.digest(receipt), "actor_patch_digest": audit["patch_digest"],
                "frontier": original["frontier"], "allocator_source": source, "allocator_digest": p82.digest(source),
                "choice": choice, "correction": correction}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-correction.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    stage2 = second_stage_conformance(source, context.evidence(label) / "second-stage") if binding else {"passed": False}
    gate = bool(binding and grounded_revision and stage2["passed"] and choice["contact_id"] == "joint")
    score = {"grounded_revision": grounded_revision, "selected_contact_id": choice.get("contact_id") if isinstance(choice, dict) else None,
             "second_stage": stage2, "correction_gate_passed": gate}
    score["receipt_digest"] = p82.digest(score)
    (context.evidence(label) / "correction-score.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding, "score": score}


def promote(p82, parent, correction, implementation, assimilation):
    child, _ = allocation.promote(p82, parent, correction, implementation, assimilation)
    child.pop("artifact_digest", None)
    body = {"authority": "world-promoted-consequence-corrected-allocation", "source_subject_digest": parent["artifact_digest"],
            "correction_binding_digest": correction["binding_digest"], "first_stage_receipt_digest": correction["failed_allocation_binding_digest"],
            "second_stage_receipt_digest": correction["second_stage_receipt_digest"],
            "world_receipt_digest": implementation["world"]["receipt_digest"],
            "assimilation_binding_digest": assimilation["binding"]["binding_digest"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child["allocation_corrections"] = [*child.get("allocation_corrections", []),
        {"binding_digest": correction["binding_digest"], "correction": correction["correction"],
         "second_stage_receipt_digest": correction["second_stage_receipt_digest"]}]
    return p82.seal(child), receipt


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0097").resolve()
    prior92 = mechanism.load_prior(); _, prior90, prior89, p82 = mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store); parent = mechanism.load_parent(p82, repo, store)
    failed = load_failed_aggregate(p82, repo, store); receipt = named_receipt(failed); erased = erased_receipt(p82, receipt)
    projection = projection_conformance(p82, receipt, erased)
    if parent["artifact_digest"] != mechanism.PARENT_DIGEST or not runtime.identity_conforms(parent) or not projection["passed"]:
        raise SystemExit("wrong parent or correction projection")
    if args.preflight_only:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = allocation.fixture_conformance(prior92, p82, parent, Path(directory) / "world")
            stage2 = second_stage_conformance(mechanism.REFERENCE_ALLOCATOR, Path(directory) / "stage2")
        result = {"parent_digest": parent["artifact_digest"], "failed_aggregate_sha256": FAILED_AGGREGATE_SHA256,
                  "projection_conformance": projection, "fixture_conformance": fixtures["passed"],
                  "second_stage_reference": stage2, "passed": fixtures["passed"] and stage2["passed"]}
        print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0097 evidence")
    run.mkdir(parents=True)
    fixtures = allocation.fixture_conformance(prior92, p82, parent, run / "fixture-conformance")
    if not fixtures["passed"]: raise SystemExit("pre-actor conformance failed")
    (run / "bound-correction-projections.json").write_text(json.dumps({"active": receipt, "erased": erased,
        "conformance": projection}, indent=2, sort_keys=True) + "\n")
    position = mechanism.active_position(parent); context = base.base.make_context(runtime, run, repo); started = time.time()
    active = run_corrector(p82, context, run, "active-correction", parent, failed, receipt, position)
    implementation = assimilation = control = None; current = parent; promotion = None
    if active["score"]["correction_gate_passed"]:
        corrected = {**active["binding"], "second_stage_receipt_digest": active["score"]["receipt_digest"]}
        implementation = mechanism.run_implementation(prior89, p82, context, run, parent, corrected)
    else: corrected = None
    if implementation and implementation["world"]["developmentally_admitted"]:
        assimilation = mechanism.run_assimilation(prior89, p82, context, run, parent, corrected, implementation)
    if assimilation and assimilation["binding"]:
        current, promotion = promote(p82, parent, corrected, implementation, assimilation)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
        and current["continuation"]["status"] == "open" and len(current.get("allocation_machinery", [])) == len(parent.get("allocation_machinery", [])) + 1
        and len(current.get("allocation_corrections", [])) == len(parent.get("allocation_corrections", [])) + 1)
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        control = run_corrector(p82, context, run, "erased-correction", parent, failed, erased, position)
    control_conformant = bool(control and control["audit"]["conformant"] and control["binding"])
    control_reproduced = bool(control and control["score"]["correction_gate_passed"])
    causal = bool(operational and control_conformant and not control_reproduced)
    result = {"authority": "ot-0097-consequence-corrected-allocation-driver", "source_subject_digest": parent["artifact_digest"],
        "failed_aggregate_sha256": FAILED_AGGREGATE_SHA256, "projection_conformance": projection,
        "active_correction": p82.compact(active), "implementation": p82.compact(implementation) if implementation else None,
        "assimilation": p82.compact(assimilation) if assimilation else None, "erased_correction": p82.compact(control) if control else None,
        "promotion_receipt": promotion, "operational_transition_passed": operational,
        "outcome_content_causal_passed": causal, "erased_reproduced_correction": control_reproduced,
        "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
