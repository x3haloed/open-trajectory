from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0095_normalized_boundary_self_allocation.py"
BASE_SHA256 = "e755827f70bedc42fbf243d95eb8b6b3acad3d34e22a7d6ae6ac7951b30bc57e"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0095 implementation identity changed")
    name = "ot0096_frozen_ot0095"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
allocation = base.base
mechanism = allocation.base
ORIGINAL_SEED = allocation.allocator_seed


def valid_typed_choice(value: Any, contacts: list[dict[str, Any]]) -> bool:
    if not isinstance(value, dict) or set(value) != mechanism.CHOICE_KEYS:
        return False
    chosen = next((row for row in contacts if row["id"] == value.get("contact_id")), None)
    string_keys = ("contact_id", "current_opening_disposition", "intended_consequence", "surrender_condition")
    strings = all(isinstance(value.get(key), str) and value[key].strip() and mechanism.PLACEHOLDER not in value[key]
                  and len(value[key]) <= 3000 for key in string_keys)
    expansion = value.get("predicted_expansion")
    return bool(strings and value["current_opening_disposition"] in {"retain", "revise", "retire"}
                and value.get("observed_saturation") is True and chosen
                and isinstance(expansion, (int, float)) and not isinstance(expansion, bool)
                and math.isfinite(expansion) and expansion == chosen["predicted_expansion"])


def typed_allocator_seed(run: Path, label: str, parent: dict[str, Any], position: dict[str, Any], p82) -> Path:
    seed = ORIGINAL_SEED(run, label, parent, position, p82)
    path = seed / "allocation-contract.json"
    contract = json.loads(path.read_text())
    contract["choice_field_types"] = {
        "contact_id": "nonempty string naming one frontier id",
        "current_opening_disposition": "one of retain, revise, retire",
        "intended_consequence": "nonempty string",
        "observed_saturation": "Boolean equal to the exhaustive certificate",
        "predicted_expansion": "finite number equal to the chosen contact",
        "surrender_condition": "nonempty string",
    }
    path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    return seed


allocation.valid_choice = valid_typed_choice
allocation.allocator_seed = typed_allocator_seed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0096").resolve()
    prior92 = mechanism.load_prior(); _, prior90, prior89, p82 = mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store); parent = mechanism.load_parent(p82, repo, store)
    if (runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent)
            or parent["artifact_digest"] != mechanism.PARENT_DIGEST or parent["continuation"]["next_opening"] != mechanism.INHERITED_OPENING
            or parent["developmental_selector"]["selector_digest"] != mechanism.SELECTOR_DIGEST):
        raise SystemExit("wrong OT-0092 parent")
    if args.preflight_only:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = allocation.fixture_conformance(prior92, p82, parent, Path(directory))
            contacts = allocation.live_reference_frontier()
            choice = {"contact_id": contacts[1]["id"], "current_opening_disposition": "retire",
                      "intended_consequence": "enact contact", "observed_saturation": True,
                      "predicted_expansion": contacts[1]["predicted_expansion"], "surrender_condition": "surrender on contradiction"}
            typed = valid_typed_choice(choice, contacts)
        passed = fixtures["passed"] and typed
        print(json.dumps({"parent_digest": parent["artifact_digest"], "base_implementation_sha256": BASE_SHA256,
                          "fixture_conformance": fixtures, "typed_choice_reference": typed, "passed": passed}, indent=2, sort_keys=True))
        return 0 if passed else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0096 evidence")
    run.mkdir(parents=True)
    fixtures = allocation.fixture_conformance(prior92, p82, parent, run / "fixture-conformance")
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    active = mechanism.active_position(parent); erased_position = mechanism.erased_position(p82, parent)
    (run / "bound-projections.json").write_text(json.dumps({"active_digest": p82.digest(active),
        "erased_digest": p82.digest(erased_position), "conformance": fixtures["projection_conformance"]}, indent=2, sort_keys=True) + "\n")
    context = base.make_context(runtime, run, repo); started = time.time()
    active_allocation = allocation.run_allocator(p82, context, run, "active", parent, active)
    implementation = assimilation = erased = None; current = parent; promotion = None
    if active_allocation["score"]["active_gate_passed"]:
        implementation = mechanism.run_implementation(prior89, p82, context, run, parent, active_allocation["binding"])
    if implementation and implementation["world"]["developmentally_admitted"]:
        assimilation = mechanism.run_assimilation(prior89, p82, context, run, parent, active_allocation["binding"], implementation)
    if assimilation and assimilation["binding"]:
        current, promotion = allocation.promote(p82, parent, active_allocation["binding"], implementation, assimilation)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
                       and current["continuation"]["status"] == "open"
                       and current["continuation"]["next_opening"] == assimilation["binding"]["successor_opening"]["next_opening"]
                       and len(current.get("allocation_machinery", [])) == len(parent.get("allocation_machinery", [])) + 1)
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        erased = allocation.run_allocator(p82, context, run, "erased", parent, erased_position)
    erased_conformant = bool(erased and erased["audit"]["conformant"] and erased["binding"])
    erased_reproduced = bool(erased and erased["score"]["active_gate_passed"])
    causal = bool(operational and erased_conformant and not erased_reproduced)
    result = {"authority": "ot-0096-typed-choice-self-allocation-driver", "source_subject_digest": parent["artifact_digest"],
        "base_implementation_sha256": BASE_SHA256, "fixture_conformance": fixtures,
        "active_allocation": p82.compact(active_allocation), "implementation": p82.compact(implementation) if implementation else None,
        "assimilation": p82.compact(assimilation) if assimilation else None, "erased_allocation": p82.compact(erased) if erased else None,
        "promotion_receipt": promotion, "operational_transition_passed": operational,
        "selector_content_causal_passed": causal, "erased_reproduced_active_allocation": erased_reproduced,
        "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
