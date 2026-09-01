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
BASE_PATH = ROOT / "ot_0093_saturation_self_allocation.py"
BASE_SHA256 = "2b8d37b1640ed41469fc428b4da0194e8967c1506531e6c13d4405b0b436bba0"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0093 implementation identity changed")
    name = "ot0094_frozen_ot0093"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()


def live_reference_frontier() -> list[dict[str, Any]]:
    return [row for row in base.reference_frontier() if not row["held_repeat"]]


def validate_live_frontier(value: Any, certificate: dict[str, Any]) -> dict[str, Any]:
    contacts = value.get("contacts", []) if isinstance(value, dict) and set(value) == {"contacts"} else []
    expected = {row["target_path"]: row for row in live_reference_frontier()}
    exact = len(contacts) == 2 and all(isinstance(row, dict) and set(row) == base.CONTACT_KEYS for row in contacts)
    ids_unique = exact and len({row["id"] for row in contacts}) == 2 and all(isinstance(row["id"], str) and row["id"] for row in contacts)
    complete_targets = exact and {row.get("target_path") for row in contacts} == set(expected)
    declarations = complete_targets and all(
        row.get("target_path") in expected
        and all(row.get(key) == expected[row["target_path"]][key]
                for key in ("target_symbol", "completed_floors", "public_regret", "reversible",
                            "held_repeat", "world_valid", "predicted_expansion"))
        for row in contacts
    )
    dead_pursuit_excluded = declarations and certificate["all_cases_passed"] and all(not row["held_repeat"] for row in contacts)
    result = {"exact_shape": exact, "unique_ids": ids_unique, "complete_targets": complete_targets,
              "objective_declarations": declarations, "dead_pursuit_excluded": dead_pursuit_excluded}
    result["passed"] = all(result.values())
    return result


def fixture_conformance(prior92, p82, parent: dict[str, Any], root: Path) -> dict[str, Any]:
    result = base.fixture_conformance(prior92, p82, parent, root)
    result["live_frontier_reference"] = validate_live_frontier(
        {"contacts": live_reference_frontier()}, result["saturation_certificate"]
    )
    result["passed"] = bool(result["passed"] and result["live_frontier_reference"]["passed"])
    return result


def valid_choice(value: Any, contacts: list[dict[str, Any]]) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == base.CHOICE_KEYS
        and value.get("contact_id") in {row["id"] for row in contacts}
        and value.get("current_opening_disposition") in {"retain", "revise", "retire"}
        and all(isinstance(value[key], str) and value[key].strip()
                and base.PLACEHOLDER not in value[key] and len(value[key]) <= 3000
                for key in base.CHOICE_KEYS)
    )


def allocator_seed(run: Path, label: str, parent: dict[str, Any], position: dict[str, Any], p82) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    base.write_world(seed, parent)
    observations = base.public_observations(p82, parent, seed / "observations")
    (seed / "subject-position.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "public-observations.json").write_text(json.dumps(observations, indent=2, sort_keys=True) + "\n")
    (seed / "saturation-certificate.json").write_text(json.dumps(base.saturation_certificate(parent), indent=2, sort_keys=True) + "\n")
    (seed / "frontier.json").write_text(json.dumps(base.frontier_template(), indent=2) + "\n")
    (seed / "allocate.py").write_text(base.ALLOCATOR_SEED)
    (seed / "choice.json").write_text(json.dumps(base.choice_template(), indent=2, sort_keys=True) + "\n")
    contract = {
        "frontier_semantics": "Enumerate exactly the currently actionable live contacts; exclude objectively saturated or held-repeat pursuits.",
        "frontier_root_exact_keys": ["contacts"], "contact_exact_keys": sorted(base.CONTACT_KEYS),
        "choice_exact_keys": sorted(base.CHOICE_KEYS), "current_opening_dispositions": ["retain", "revise", "retire"],
        "allocator_abi": "select(contacts) -> contact id",
        "allocator_rule": "Use only declared fields; do not embed ids, paths, symbols, or hidden facts.",
        "instruction": "Discover and declare the real live contacts exposed by source and public observations; declarations are audited objectively. Record the saturated current pursuit through its disposition, not as a live contact.",
    }
    (seed / "allocation-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["frontier.json", "allocate.py", "choice.json"]}, indent=2) + "\n")
    (seed / "README.md").write_text(
        "Continue the exact subject in this complete environment. Reconcile its local opening with objective saturation, discover the bounded live frontier, embody a generic allocation rule, bind its choice, run useful checks, inspect the exact diff, and edit exactly the three permitted files.\n"
    )
    return seed


def run_allocator(p82, context, run: Path, label: str, parent: dict[str, Any], position: dict[str, Any]) -> dict[str, Any]:
    seed = allocator_seed(run, label, parent, position, p82)
    prompt = "Continue the exact subject by inspecting this complete world, reconciling current pursuit with evidence, authoring its live frontier, embodying a reusable allocation rule, binding one contact, running useful public checks, inspecting the exact diff, and returning the required report."
    output, base_audit, workspace, _ = context.run_actor(label, seed, base.ALLOCATOR_SCHEMA, prompt)
    try:
        frontier = json.loads((workspace / "frontier.json").read_text())
        source = (workspace / "allocate.py").read_text()
        choice = json.loads((workspace / "choice.json").read_text())
    except (OSError, json.JSONDecodeError):
        frontier, source, choice = None, "", None
    certificate = base.saturation_certificate(parent)
    frontier_check = validate_live_frontier(frontier, certificate)
    contacts = frontier.get("contacts", []) if isinstance(frontier, dict) else []
    choice_valid = valid_choice(choice, contacts)
    try:
        public_selected = base.load_allocator(source, workspace / "public-allocator")(json.loads(json.dumps(contacts)))
    except Exception:
        public_selected = None
    artifact_valid = bool(frontier_check["passed"] and choice_valid and public_selected == choice["contact_id"] and source != base.ALLOCATOR_SEED)
    audit = context.audit_actor(label, output, base_audit, artifact_valid, ["allocate.py", "choice.json", "frontier.json"])
    binding = None
    hidden_allocator = {"passed": False}
    if audit["conformant"]:
        body = {"authority": "ot-0094-pre-hidden-live-allocation", "condition": label,
                "source_subject_digest": position["subject_digest"], "projection_digest": p82.digest(position),
                "actor_patch_digest": audit["patch_digest"], "frontier": frontier, "allocator_source": source,
                "allocator_digest": p82.digest(source), "choice": choice, "frontier_conformance": frontier_check}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-allocation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
        hidden_allocator = base.allocator_conformance(source, context.evidence(label) / "hidden-allocator")
    chosen = next((row for row in contacts if row.get("id") == (choice or {}).get("contact_id")), None)
    active_gate = bool(binding and hidden_allocator["passed"] and choice["current_opening_disposition"] == "retire"
                       and chosen and chosen["target_path"] == "operations/joint.py")
    score = {"hidden_allocator": hidden_allocator,
             "current_opening_retired": bool(choice and choice.get("current_opening_disposition") == "retire"),
             "chosen_target_path": chosen["target_path"] if chosen else None, "active_gate_passed": active_gate}
    score["receipt_digest"] = p82.digest(score)
    (context.evidence(label) / "allocation-score.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding, "score": score}


def promote(p82, parent: dict[str, Any], allocation: dict[str, Any], implementation: dict[str, Any], assimilation: dict[str, Any]):
    opening = assimilation["binding"]["successor_opening"]
    body = {"authority": "world-promoted-live-frontier-self-allocation", "source_subject_digest": parent["artifact_digest"],
            "allocation_binding_digest": allocation["binding_digest"], "implementation_binding_digest": implementation["binding"]["binding_digest"],
            "world_receipt_digest": implementation["world"]["receipt_digest"], "assimilation_binding_digest": assimilation["binding"]["binding_digest"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(parent); child.pop("artifact_digest", None)
    child["allocation_machinery"] = [*child.get("allocation_machinery", []), {"source": allocation["allocator_source"],
        "source_digest": allocation["allocator_digest"], "frontier": allocation["frontier"], "choice": allocation["choice"],
        "world_receipt_digest": implementation["world"]["receipt_digest"]}]
    child["environmental_capabilities"] = [*child.get("environmental_capabilities", []), {"target_path": "operations/joint.py",
        "target_symbol": "choose_joint", "source": implementation["binding"]["source"], "source_digest": implementation["binding"]["source_digest"],
        "world_receipt_digest": implementation["world"]["receipt_digest"]}]
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []), {"receipt": receipt, "assimilation": assimilation["binding"]["assimilation"]}]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []),
        {"authority": "fresh-live-frontier-opening", "binding_digest": assimilation["binding"]["binding_digest"], "opening": opening}]
    child["active_pursuit"] = {"authority": "fresh-live-frontier-opening", "selected_area": "allocation-machinery",
        "next_pursuit": opening["next_opening"], "world_receipt_digest": implementation["world"]["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["runtime"] = "sounding"; child["unresolved"] = opening["continuation_after_contact"]
    return p82.seal(child), receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0094").resolve()
    prior92 = base.load_prior(); _, prior90, prior89, p82 = base.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = base.load_parent(p82, repo, store)
    if (runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent)
            or parent["artifact_digest"] != base.PARENT_DIGEST or parent["continuation"]["next_opening"] != base.INHERITED_OPENING
            or parent["developmental_selector"]["selector_digest"] != base.SELECTOR_DIGEST):
        raise SystemExit("wrong OT-0092 parent")
    if args.preflight_only:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_conformance(prior92, p82, parent, Path(directory))
        print(json.dumps({"parent_digest": parent["artifact_digest"], "base_implementation_sha256": BASE_SHA256,
                          "fixture_conformance": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0094 evidence")
    run.mkdir(parents=True)
    fixtures = fixture_conformance(prior92, p82, parent, run / "fixture-conformance")
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    active = base.active_position(parent); erased_position = base.erased_position(p82, parent)
    (run / "bound-projections.json").write_text(json.dumps({"active_digest": p82.digest(active),
        "erased_digest": p82.digest(erased_position), "conformance": fixtures["projection_conformance"]}, indent=2, sort_keys=True) + "\n")
    context = runtime.Context(run, repo); started = time.time()
    allocation = run_allocator(p82, context, run, "active", parent, active)
    implementation = assimilation = erased = None; current = parent; promotion = None
    if allocation["score"]["active_gate_passed"]:
        implementation = base.run_implementation(prior89, p82, context, run, parent, allocation["binding"])
    if implementation and implementation["world"]["developmentally_admitted"]:
        assimilation = base.run_assimilation(prior89, p82, context, run, parent, allocation["binding"], implementation)
    if assimilation and assimilation["binding"]:
        current, promotion = promote(p82, parent, allocation["binding"], implementation, assimilation)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
                       and current["continuation"]["status"] == "open"
                       and current["continuation"]["next_opening"] == assimilation["binding"]["successor_opening"]["next_opening"]
                       and len(current.get("allocation_machinery", [])) == len(parent.get("allocation_machinery", [])) + 1)
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        erased = run_allocator(p82, context, run, "erased", parent, erased_position)
    erased_conformant = bool(erased and erased["audit"]["conformant"] and erased["binding"])
    erased_reproduced = bool(erased and erased["score"]["active_gate_passed"])
    causal = bool(operational and erased_conformant and not erased_reproduced)
    result = {"authority": "ot-0094-live-frontier-self-allocation-driver", "source_subject_digest": parent["artifact_digest"],
        "base_implementation_sha256": BASE_SHA256, "fixture_conformance": fixtures,
        "active_allocation": p82.compact(allocation), "implementation": p82.compact(implementation) if implementation else None,
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
