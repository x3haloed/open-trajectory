from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0106_iterated_contact_coverage_correction.py"
BASE_SHA256 = "907ad97ab5e2f8142869e45cdcf6cd6e9ce93380edf71d20ee20a451cdbf2b8a"
PARENT_OBJECT_SHA256 = "9f4e01bd55b475f5283e4235b9a87a6eaef3b301bfce750fa02569b0cabcf205"
PARENT_DIGEST = "db9d56536015a20252811eca59f827c2e96a693c04bf4b54a4ff06bbb67d7d86"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0107-assimilator.schema.json"
ACTION_KEYS = {"action_kind", "action_target", "rationale", "expected_information", "surrender_condition"}
ACTION_KINDS = {"registered-contact", "registry-extension"}
REGISTERED = {"joint-boundary-probe", "allocator-challenge"}
PLACEHOLDER = "__REPLACE__"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0106 implementation identity changed")
    name = "ot0107_frozen_ot0106"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base = prior.base


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    manifest, path = p82.materialize(repo, store, "OT-0106", "open-subject-after-cross-interface-correction.json")
    if manifest["sha256"] != PARENT_OBJECT_SHA256:
        raise RuntimeError("wrong OT-0106 subject object identity")
    return json.loads(path.read_text())


def extract_action(p82, subject: dict[str, Any]) -> dict[str, Any] | None:
    openings = subject.get("actor_originated_pursuit_openings", [])
    retained = openings[-1] if openings else {}
    next_interface = retained.get("next_interface")
    if not base.valid_next_interface(next_interface):
        return None
    if subject.get("active_pursuit", {}).get("selected_area") != next_interface["interface_id"]:
        return None
    if subject.get("continuation", {}).get("next_opening") != retained.get("opening", {}).get("next_opening"):
        return None
    body = {
        "authority": "ot-0107-subject-bound-interface", "source_subject_digest": subject["artifact_digest"],
        "assimilation_binding_digest": retained["binding_digest"], "next_interface": next_interface,
    }
    return {**body, "binding_digest": p82.digest(body)}


def action_template() -> dict[str, str]:
    return {key: PLACEHOLDER for key in sorted(ACTION_KEYS)}


def valid_action(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != ACTION_KEYS or value.get("action_kind") not in ACTION_KINDS:
        return False
    if not all(isinstance(value.get(key), str) and value[key].strip() and PLACEHOLDER not in value[key] and len(value[key]) <= 3000 for key in ACTION_KEYS - {"action_kind"}):
        return False
    target = value["action_target"]
    if value["action_kind"] == "registered-contact":
        return target in REGISTERED
    return target not in REGISTERED and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}", target))


def active_history(parent: dict[str, Any]) -> dict[str, Any]:
    receipts = parent.get("subject_recurrence_receipts", [])
    return {
        "receipt_digests": [row["receipt_digest"] for row in receipts],
        "interface_sequence": [row["next_interface"]["interface_id"] for row in receipts],
        "completed_cycles": len(receipts),
        "registry": sorted(REGISTERED),
    }


def erased_history(p82, parent: dict[str, Any]) -> dict[str, Any]:
    history = active_history(parent)
    return {
        "receipt_digests": [f"opaque:{p82.digest({'receipt': item})}" for item in history["receipt_digests"]],
        "interface_sequence": [f"opaque:{p82.digest({'interface': item, 'index': index})}" for index, item in enumerate(history["interface_sequence"])],
        "completed_cycles": history["completed_cycles"], "registry": history["registry"],
    }


def assimilation_seed(prior89, run: Path, label: str, parent: dict[str, Any], position: dict[str, Any], history: dict[str, Any], contact: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"; seed.mkdir()
    consequence = {
        "subject_position": position, "developmental_history": history,
        "contact_binding": contact["binding"], "world_receipt": contact["world"],
        "registered_interfaces": base.INTERFACE_REGISTRY,
    }
    (seed / "subject-contact-consequence.json").write_text(json.dumps(consequence, indent=2, sort_keys=True) + "\n")
    (seed / "assimilation.json").write_text(json.dumps(base.assimilation_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "continuation-action.json").write_text(json.dumps(action_template(), indent=2, sort_keys=True) + "\n")
    contract = {
        "exact_keys": sorted(ACTION_KEYS), "action_kinds": sorted(ACTION_KINDS),
        "registered_targets": sorted(REGISTERED),
        "registered-contact": "target must be a registered id",
        "registry-extension": "target must be a new lowercase hyphenated id; this binds pursuit of an interface proposal but does not admit it",
        "instruction": "Choose what is worth carrying after consequence. Replace every placeholder and make the opening consistent with the action.",
    }
    (seed / "continuation-action-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "retained-allocator.py").write_text(parent["allocation_machinery"][-1]["source"])
    capability = next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == "operations/joint.py")
    (seed / "retained-joint.py").write_text(capability["source"])
    editable = ["assimilation.json", "successor-opening.json", "continuation-action.json"]
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": editable, "immutable": ["retained-allocator.py", "retained-joint.py"]}, indent=2) + "\n")
    (seed / "README.md").write_text(
        "Assimilate the completed contact and choose the exact continuation worth carrying. You may bind another registered contact or a registry-extension pursuit for a genuinely new interface. Preserve uncertainty and machinery, edit exactly the three permitted JSON files, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_assimilation(prior89, p82, context, run: Path, label: str, parent: dict[str, Any], position: dict[str, Any], history: dict[str, Any], contact: dict[str, Any]):
    seed = assimilation_seed(prior89, run, label, parent, position, history, contact)
    prompt = "Assimilate this exact world consequence and bind the next continuation from the published action space. Preserve immutable machinery, edit exactly assimilation.json, successor-opening.json, and continuation-action.json, inspect the diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATOR_SCHEMA, prompt)
    try:
        assimilation = json.loads((workspace / "assimilation.json").read_text())
        opening = json.loads((workspace / "successor-opening.json").read_text())
        action = json.loads((workspace / "continuation-action.json").read_text())
        allocator_retained = (workspace / "retained-allocator.py").read_text() == parent["allocation_machinery"][-1]["source"]
        capability = next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == "operations/joint.py")
        joint_retained = (workspace / "retained-joint.py").read_text() == capability["source"]
    except (OSError, json.JSONDecodeError):
        assimilation = opening = action = None; allocator_retained = joint_retained = False
    valid = bool(base.valid_assimilation(assimilation) and prior89.valid_successor(opening) and valid_action(action) and allocator_retained and joint_retained and opening["next_opening"] != position["continuation"]["next_opening"])
    allowed = ["assimilation.json", "successor-opening.json", "continuation-action.json"]
    audit = context.audit_actor(label, output, base_audit, valid, allowed)
    passed_ids = {row["case_id"] for row in contact["world"]["rows"] if row["passed"]}
    cited = set(assimilation["settled_case_ids"]) if isinstance(assimilation, dict) and isinstance(assimilation.get("settled_case_ids"), list) else set()
    grounded = bool(audit["conformant"] and cited and cited.issubset(passed_ids))
    binding = None
    if grounded:
        body = {
            "authority": "ot-0107-extension-aware-assimilation", "source_subject_digest": parent["artifact_digest"],
            "contact_binding_digest": contact["binding"]["binding_digest"], "world_receipt_digest": contact["world"]["receipt_digest"],
            "history_projection_digest": p82.digest(history), "actor_patch_digest": audit["patch_digest"],
            "allocator_retention_derived": allocator_retained, "joint_retention_derived": joint_retained,
            "assimilation": assimilation, "successor_opening": opening, "continuation_action": action,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-assimilation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "grounded": grounded, "allocator_retention_derived": allocator_retained, "joint_retention_derived": joint_retained, "binding": binding}


def promote(p82, parent: dict[str, Any], selection: dict[str, Any], contact: dict[str, Any], assimilation: dict[str, Any]):
    child = copy.deepcopy(parent); child.pop("artifact_digest", None)
    action = assimilation["continuation_action"]; opening = assimilation["successor_opening"]
    body = {
        "authority": "world-promoted-registry-exit-continuation", "source_subject_digest": parent["artifact_digest"],
        "interface_binding_digest": selection["binding_digest"], "contact_binding_digest": contact["binding_digest"],
        "world_receipt_digest": assimilation["world_receipt_digest"], "assimilation_binding_digest": assimilation["binding_digest"],
        "continuation_action": action,
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child["subject_recurrence_receipts"] = [*child.get("subject_recurrence_receipts", []), receipt]
    child["actor_authored_contacts"] = [*child.get("actor_authored_contacts", []), {"interface_id": contact["interface_id"], "binding_digest": contact["binding_digest"], "world_receipt_digest": assimilation["world_receipt_digest"]}]
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []), {"receipt": receipt, "assimilation": assimilation["assimilation"]}]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []), {"authority": "ot-0107-extension-aware-opening", "binding_digest": assimilation["binding_digest"], "opening": opening, "continuation_action": action}]
    child["active_pursuit"] = {"authority": "ot-0107-extension-aware-opening", "selected_area": action["action_target"], "next_pursuit": opening["next_opening"], "world_receipt_digest": assimilation["world_receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["unresolved"] = opening["continuation_after_contact"]; child["runtime"] = "sounding"
    return p82.seal(child), receipt


def fixture_conformance(p82, parent: dict[str, Any]) -> dict[str, Any]:
    inherited = base.fixture_conformance(p82, parent); selection = extract_action(p82, parent)
    registered = {"action_kind": "registered-contact", "action_target": "joint-boundary-probe", "rationale": "continue", "expected_information": "more consequence", "surrender_condition": "yield on mismatch"}
    extension = {"action_kind": "registry-extension", "action_target": "cross-regime-probe", "rationale": "escape saturation", "expected_information": "new world relation", "surrender_condition": "yield if inadmissible"}
    invalid_extension = {**extension, "action_target": "joint-boundary-probe"}
    result = {
        "inherited_interfaces": inherited, "active_joint_action_derived": bool(selection and selection["next_interface"]["interface_id"] == "joint-boundary-probe"),
        "registered_action_valid": valid_action(registered), "extension_action_valid": valid_action(extension), "registered_target_rejected_as_extension": not valid_action(invalid_extension),
        "history_projection_distinct": p82.digest(active_history(parent)) != p82.digest(erased_history(p82, parent)),
    }
    result["passed"] = bool(inherited["passed"] and all(result[key] for key in result if key != "inherited_interfaces")); return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, default=REPO); parser.add_argument("--store", type=Path); parser.add_argument("--evidence-root", type=Path); parser.add_argument("--preflight-only", action="store_true"); args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0107").resolve()
    prior92 = base.mechanism.load_prior(); _, _, prior89, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    if parent["artifact_digest"] != PARENT_DIGEST or not runtime.identity_conforms(parent) or parent["continuation"]["status"] != "open": raise SystemExit("wrong OT-0106 parent")
    fixtures = fixture_conformance(p82, parent); selection = extract_action(p82, parent)
    if args.preflight_only:
        result = {"parent_digest": parent["artifact_digest"], "parent_object_sha256": PARENT_OBJECT_SHA256, "base_implementation_sha256": BASE_SHA256, "active_history_digest": p82.digest(active_history(parent)), "erased_history_digest": p82.digest(erased_history(p82, parent)), "fixture_conformance": fixtures}
        print(json.dumps(result, indent=2, sort_keys=True)); return 0 if fixtures["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0107 evidence")
    run.mkdir(parents=True); (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"] or not selection: raise SystemExit("pre-actor conformance failed")
    context = prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo)); position = base.active_position(parent); started = time.time()
    contact = base.run_contact(p82, context, run, "active-joint-contact", parent, position, selection)
    assimilation = None; current = parent; promotion = None
    if contact["admitted"]: assimilation = run_assimilation(prior89, p82, context, run, "active-assimilation", parent, position, active_history(parent), contact)
    if assimilation and assimilation["binding"]: current, promotion = promote(p82, parent, selection, contact["binding"], assimilation["binding"])
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open")
    extension_selected = bool(operational and assimilation["binding"]["continuation_action"]["action_kind"] == "registry-extension")
    control = None
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    if extension_selected: control = run_assimilation(prior89, p82, context, run, "history-erased-assimilation", parent, position, erased_history(p82, parent), contact)
    control_extension = bool(control and control["binding"] and control["binding"]["continuation_action"]["action_kind"] == "registry-extension")
    result = {"authority": "ot-0107-registry-exit-continuation-driver", "source_subject_digest": parent["artifact_digest"], "subject_bound_contact": p82.compact(contact), "active_assimilation": p82.compact(assimilation) if assimilation else None, "promotion_receipt": promotion, "history_erased_control": p82.compact(control) if control else None, "operational_transition_passed": operational, "registry_extension_selected": extension_selected, "history_erased_selected_extension": control_extension, "observer_disposition": "promoted" if operational else "rejected", "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost", "final_subject_digest": current["artifact_digest"], "continuation_action": current["actor_originated_pursuit_openings"][-1].get("continuation_action"), "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time()-started,3)}
    result["receipt_digest"] = p82.digest(result); (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n"); (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True)+"\n"); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
