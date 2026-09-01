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
BASE_PATH = ROOT / "ot_0101_derived_retention_promotion.py"
BASE_SHA256 = "edff7bb068f1416f5519054b7f2c7db1dc74bcc15ff49bfcb410f8af0396801b"
PARENT_OBJECT_SHA256 = "af7ccc587abda92c4810b39eb9c4a3008800ad6d4d065db1634fd76d4a14fb55"
PARENT_DIGEST = "b7b3494c0a0b8ab99ec35d9ad40250b531bb184bce99d3b5a45310baf00f3886"
ROUTER_SCHEMA = REPO / "spec/ot-0102-router.schema.json"
CONTACT_SCHEMA = REPO / "spec/ot-0102-contact.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0102-assimilator.schema.json"
PLACEHOLDER = "__REPLACE__"
INTERFACE_IDS = {"joint-boundary-probe", "allocator-challenge"}
NEXT_INTERFACE_KEYS = {"interface_id", "rationale", "expected_information", "surrender_condition"}
ASSIMILATION_KEYS = {
    "consequence_summary", "settled_case_ids", "remaining_uncertainty",
    "selection_rule_update", "surrender_condition",
}
JOINT_CONTACT_KEYS = {"interface_id", "cases"}
JOINT_CASE_KEYS = {"case_id", "context", "options"}
JOINT_CONTEXT_KEYS = {"risk_penalty", "overload_penalty"}
JOINT_OPTION_KEYS = {"id", "recovery_value", "recovery_risk", "capacity", "overload"}
ALLOCATOR_CONTACT_KEYS = {"interface_id", "frontiers"}
CONTACT_KEYS = {
    "id", "target_path", "target_symbol", "completed_floors", "public_regret",
    "reversible", "held_repeat", "world_valid", "predicted_expansion",
    "world_contact", "surrender_condition",
}
BOUNDARY_WIDTH = 10.0


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0101 implementation identity changed")
    name = "ot0102_frozen_ot0101"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
mechanism = base.mechanism
typed = base.typed


INTERFACE_REGISTRY = {
    "joint-boundary-probe": {
        "description": "Author three novel joint cases near recovery-risk and overload tradeoffs; compare retained capability with realized-score oracle.",
        "artifact": "contact.json",
        "case_count": 3,
        "boundary_width": BOUNDARY_WIDTH,
    },
    "allocator-challenge": {
        "description": "Author four novel frontiers spanning filters, composition threshold, expansion, regret, order, and stable ties; compare retained allocator with reference semantics.",
        "artifact": "contact.json",
        "case_count": 4,
    },
}


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    manifest, path = p82.materialize(
        repo, store, "OT-0101", "open-subject-after-derived-retention-promotion.json"
    )
    if manifest["sha256"] != PARENT_OBJECT_SHA256:
        raise RuntimeError("wrong OT-0101 subject object identity")
    return json.loads(path.read_text())


def active_position(parent: dict[str, Any]) -> dict[str, Any]:
    allocation = parent["allocation_machinery"][-1]
    capability = next(
        row for row in reversed(parent["environmental_capabilities"])
        if row.get("target_path") == "operations/joint.py"
    )
    return {
        "subject_digest": parent["artifact_digest"],
        "continuation": parent["continuation"],
        "active_pursuit": parent["active_pursuit"],
        "unresolved": parent["unresolved"],
        "developmental_selector": parent["developmental_selector"],
        "allocation_source_digest": allocation["source_digest"],
        "allocation_correction_history": parent["allocation_correction_history"],
        "joint_capability_source_digest": capability["source_digest"],
    }


def erased_position(p82, parent: dict[str, Any]) -> dict[str, Any]:
    position = active_position(parent)
    opening = position["continuation"]["next_opening"]
    opaque = p82.digest({"erased_opening": opening})
    position["continuation"] = {**position["continuation"], "next_opening": f"opaque:{opaque}"}
    position["active_pursuit"] = {
        **position["active_pursuit"], "next_pursuit": f"opaque:{opaque}", "selected_area": "opaque",
    }
    position["unresolved"] = f"opaque:{p82.digest({'erased_unresolved': position['unresolved']})}"
    return position


def next_interface_template() -> dict[str, str]:
    return {key: PLACEHOLDER for key in sorted(NEXT_INTERFACE_KEYS)}


def valid_next_interface(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == NEXT_INTERFACE_KEYS
        and value.get("interface_id") in INTERFACE_IDS
        and all(
            isinstance(value.get(key), str)
            and value[key].strip()
            and PLACEHOLDER not in value[key]
            and len(value[key]) <= 3000
            for key in NEXT_INTERFACE_KEYS - {"interface_id"}
        )
    )


def assimilation_template() -> dict[str, Any]:
    return {
        "consequence_summary": PLACEHOLDER,
        "settled_case_ids": [],
        "remaining_uncertainty": PLACEHOLDER,
        "selection_rule_update": PLACEHOLDER,
        "surrender_condition": PLACEHOLDER,
    }


def valid_assimilation(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == ASSIMILATION_KEYS
        and isinstance(value.get("settled_case_ids"), list)
        and value["settled_case_ids"]
        and len(value["settled_case_ids"]) == len(set(value["settled_case_ids"]))
        and all(isinstance(item, str) and item for item in value["settled_case_ids"])
        and all(
            isinstance(value.get(key), str)
            and value[key].strip()
            and PLACEHOLDER not in value[key]
            and len(value[key]) <= 3000
            for key in ASSIMILATION_KEYS - {"settled_case_ids"}
        )
    )


def finite_number(value: Any, low: float = 0.0, high: float = 200.0) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high


def joint_score(context: dict[str, float], option: dict[str, Any]) -> float:
    return (
        option["recovery_value"] - context["risk_penalty"] * option["recovery_risk"]
        + option["capacity"] - context["overload_penalty"] * option["overload"]
    )


def valid_joint_contact(value: Any) -> tuple[bool, dict[str, Any]]:
    cases = value.get("cases", []) if isinstance(value, dict) else []
    exact = set(value) == JOINT_CONTACT_KEYS and value.get("interface_id") == "joint-boundary-probe"
    shapes = exact and len(cases) == 3 and all(
        isinstance(case, dict)
        and set(case) == JOINT_CASE_KEYS
        and isinstance(case.get("case_id"), str)
        and bool(case["case_id"].strip())
        and isinstance(case.get("context"), dict)
        and set(case["context"]) == JOINT_CONTEXT_KEYS
        and all(finite_number(case["context"].get(key), 0.0, 100.0) for key in JOINT_CONTEXT_KEYS)
        and isinstance(case.get("options"), list)
        and len(case["options"]) == 2
        and all(
            isinstance(option, dict)
            and set(option) == JOINT_OPTION_KEYS
            and isinstance(option.get("id"), str)
            and bool(option["id"].strip())
            and all(finite_number(option.get(key)) for key in JOINT_OPTION_KEYS - {"id"})
            for option in case["options"]
        )
        and len({option["id"] for option in case["options"]}) == 2
        for case in cases
    )
    ids_unique = bool(shapes and len({case["case_id"] for case in cases}) == 3)
    digests_unique = bool(shapes and len({digest(case) for case in cases}) == 3)
    nonzero_tradeoffs = bool(shapes and any(
        option["recovery_risk"] > 0 and option["overload"] > 0
        for case in cases for option in case["options"]
    ))
    winner_flip = False
    near_boundary = False
    if shapes:
        for case in cases:
            oracle = max(case["options"], key=lambda row: (joint_score(case["context"], row), row["id"]))
            naive = max(case["options"], key=lambda row: (row["recovery_value"] + row["capacity"], row["id"]))
            scores = sorted((joint_score(case["context"], row) for row in case["options"]), reverse=True)
            margin = scores[0] - scores[1]
            winner_flip = winner_flip or oracle["id"] != naive["id"]
            near_boundary = near_boundary or 0 < margin <= BOUNDARY_WIDTH
    checks = {
        "exact_shape": bool(shapes),
        "case_ids_unique": ids_unique,
        "cases_unique": digests_unique,
        "nonzero_risk_and_overload": nonzero_tradeoffs,
        "penalty_changes_winner": winner_flip,
        "near_boundary": near_boundary,
    }
    checks["passed"] = all(checks.values())
    return checks["passed"], checks


def eligible(contact: dict[str, Any]) -> bool:
    return bool(
        contact["world_valid"] and contact["world_contact"]
        and not contact["held_repeat"] and contact["reversible"]
    )


def allocator_reference(frontier: list[dict[str, Any]]) -> str:
    live = [row for row in frontier if eligible(row)]
    if not live:
        raise ValueError("no live contacts")
    return max(
        live,
        key=lambda row: (
            len(row["completed_floors"]) >= 2,
            row["predicted_expansion"], row["public_regret"], row["id"],
        ),
    )["id"]


def contact_shape(contact: Any) -> bool:
    return bool(
        isinstance(contact, dict)
        and set(contact) == CONTACT_KEYS
        and isinstance(contact.get("id"), str) and contact["id"]
        and isinstance(contact.get("target_path"), str) and contact["target_path"]
        and isinstance(contact.get("target_symbol"), str) and contact["target_symbol"]
        and isinstance(contact.get("completed_floors"), list)
        and all(isinstance(item, str) and item for item in contact["completed_floors"])
        and finite_number(contact.get("public_regret"))
        and finite_number(contact.get("predicted_expansion"))
        and all(isinstance(contact.get(key), bool) for key in ("reversible", "held_repeat", "world_valid", "world_contact"))
        and isinstance(contact.get("surrender_condition"), str) and contact["surrender_condition"]
    )


def allocator_coverage(frontiers: list[list[dict[str, Any]]]) -> dict[str, bool]:
    canonical: dict[str, list[list[str]]] = {}
    filtered_decoy = threshold = expansion = regret = stable_tie = False
    for frontier in frontiers:
        live = [row for row in frontier if eligible(row)]
        selected_id = allocator_reference(frontier)
        selected = next(row for row in live if row["id"] == selected_id)
        key = digest(sorted(frontier, key=lambda row: row["id"]))
        canonical.setdefault(key, []).append([row["id"] for row in frontier])
        filtered = [row for row in frontier if not eligible(row)]
        filtered_decoy = filtered_decoy or any(
            row["predicted_expansion"] >= selected["predicted_expansion"]
            and row["public_regret"] >= selected["public_regret"] for row in filtered
        )
        threshold = threshold or any(
            len(selected["completed_floors"]) == 2
            and len(row["completed_floors"]) > 2
            and selected["predicted_expansion"] > row["predicted_expansion"]
            for row in live if row["id"] != selected_id
        )
        expansion = expansion or any(
            (len(row["completed_floors"]) >= 2) == (len(selected["completed_floors"]) >= 2)
            and selected["predicted_expansion"] > row["predicted_expansion"]
            for row in live if row["id"] != selected_id
        )
        regret = regret or any(
            (len(row["completed_floors"]) >= 2) == (len(selected["completed_floors"]) >= 2)
            and selected["predicted_expansion"] == row["predicted_expansion"]
            and selected["public_regret"] > row["public_regret"]
            for row in live if row["id"] != selected_id
        )
        stable_tie = stable_tie or any(
            (len(row["completed_floors"]) >= 2) == (len(selected["completed_floors"]) >= 2)
            and selected["predicted_expansion"] == row["predicted_expansion"]
            and selected["public_regret"] == row["public_regret"]
            and selected["id"] > row["id"]
            for row in live if row["id"] != selected_id
        )
    reversal = any(len({tuple(order) for order in orders}) >= 2 for orders in canonical.values())
    return {
        "order_reversal": reversal,
        "filtered_decoy": filtered_decoy,
        "composition_threshold": threshold,
        "expansion": expansion,
        "regret": regret,
        "stable_tie": stable_tie,
    }


def valid_allocator_contact(value: Any) -> tuple[bool, dict[str, Any]]:
    frontiers = value.get("frontiers", []) if isinstance(value, dict) else []
    exact = set(value) == ALLOCATOR_CONTACT_KEYS and value.get("interface_id") == "allocator-challenge"
    shapes = bool(
        exact and len(frontiers) == 4
        and all(isinstance(frontier, list) and 2 <= len(frontier) <= 8 for frontier in frontiers)
        and all(contact_shape(row) for frontier in frontiers for row in frontier)
        and all(len({row["id"] for row in frontier}) == len(frontier) for frontier in frontiers)
        and all(any(eligible(row) for row in frontier) for frontier in frontiers)
    )
    coverage = allocator_coverage(frontiers) if shapes else {
        "order_reversal": False, "filtered_decoy": False, "composition_threshold": False,
        "expansion": False, "regret": False, "stable_tie": False,
    }
    checks = {"exact_shape": shapes, **coverage}
    checks["passed"] = all(checks.values())
    return checks["passed"], checks


def validate_contact(interface_id: str, value: Any) -> tuple[bool, dict[str, Any]]:
    if interface_id == "joint-boundary-probe":
        return valid_joint_contact(value)
    if interface_id == "allocator-challenge":
        return valid_allocator_contact(value)
    return False, {"passed": False, "reason": "unknown interface"}


def score_contact(p82, parent: dict[str, Any], interface_id: str, value: dict[str, Any]) -> dict[str, Any]:
    rows = []
    if interface_id == "joint-boundary-probe":
        capability = next(
            row for row in reversed(parent["environmental_capabilities"])
            if row.get("target_path") == "operations/joint.py"
        )
        namespace: dict[str, Any] = {}
        exec(capability["source"], namespace)
        choose = namespace["choose_joint"]
        for case in value["cases"]:
            selected_id = choose(copy.deepcopy(case["context"]), copy.deepcopy(case["options"]))
            oracle = max(case["options"], key=lambda row: (joint_score(case["context"], row), row["id"]))
            selected = next((row for row in case["options"] if row["id"] == selected_id), None)
            rows.append({
                "case_id": case["case_id"], "selected_id": selected_id,
                "oracle_id": oracle["id"],
                "selected_score": joint_score(case["context"], selected) if selected else None,
                "oracle_score": joint_score(case["context"], oracle),
                "passed": selected_id == oracle["id"],
            })
    else:
        allocation = parent["allocation_machinery"][-1]
        namespace = {}
        exec(allocation["source"], namespace)
        choose = namespace["select"]
        for index, frontier in enumerate(value["frontiers"], start=1):
            selected_id = choose(copy.deepcopy(frontier))
            oracle_id = allocator_reference(frontier)
            rows.append({
                "case_id": f"allocator-{index}", "selected_id": selected_id,
                "oracle_id": oracle_id, "passed": selected_id == oracle_id,
            })
    body = {
        "authority": "ot-0102-independent-world",
        "interface_id": interface_id,
        "contact_digest": p82.digest(value),
        "rows": rows,
        "all_cases_passed": bool(rows and all(row["passed"] for row in rows)),
    }
    return {**body, "receipt_digest": p82.digest(body)}


def router_seed(run: Path, label: str, position: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    (seed / "subject-position.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "interface-registry.json").write_text(json.dumps(INTERFACE_REGISTRY, indent=2, sort_keys=True) + "\n")
    (seed / "next-interface.json").write_text(json.dumps(next_interface_template(), indent=2, sort_keys=True) + "\n")
    (seed / "next-interface-contract.json").write_text(json.dumps({
        "exact_keys": sorted(NEXT_INTERFACE_KEYS), "interface_ids": sorted(INTERFACE_IDS),
        "instruction": "Choose the registered interface that best realizes the subject's inherited opening. Replace every placeholder.",
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["next-interface.json"]}, indent=2) + "\n")
    (seed / "README.md").write_text(
        "Continue the exact subject position. Choose the registered world-contact interface that best realizes its live opening, edit only next-interface.json, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_router(p82, context, run: Path, label: str, position: dict[str, Any]) -> dict[str, Any]:
    seed = router_seed(run, label, position)
    prompt = "Continue this exact subject by routing its live opening to one registered contact interface. Use ordinary tools, edit only next-interface.json, inspect the diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor(label, seed, ROUTER_SCHEMA, prompt)
    try:
        value = json.loads((workspace / "next-interface.json").read_text())
    except (OSError, json.JSONDecodeError):
        value = None
    valid = valid_next_interface(value)
    audit = context.audit_actor(label, output, base_audit, valid, ["next-interface.json"])
    binding = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0102-opening-router", "source_subject_digest": position["subject_digest"],
            "projection_digest": p82.digest(position), "actor_patch_digest": audit["patch_digest"],
            "next_interface": value,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-next-interface.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding}


def contact_template(interface_id: str) -> dict[str, Any]:
    if interface_id == "joint-boundary-probe":
        return {"interface_id": interface_id, "cases": []}
    return {"interface_id": interface_id, "frontiers": []}


def contact_contract(interface_id: str) -> dict[str, Any]:
    if interface_id == "joint-boundary-probe":
        return {
            "exact_root_keys": sorted(JOINT_CONTACT_KEYS), "case_count": 3,
            "case_exact_keys": sorted(JOINT_CASE_KEYS), "context_exact_keys": sorted(JOINT_CONTEXT_KEYS),
            "option_exact_keys": sorted(JOINT_OPTION_KEYS), "two_options_per_case": True,
            "numeric_bounds": [0, 200], "context_penalty_bounds": [0, 100],
            "coverage": ["nonzero recovery risk and overload", "penalty changes a naive winner", f"nonzero oracle margin <= {BOUNDARY_WIDTH}"],
            "oracle": "recovery_value - risk_penalty * recovery_risk + capacity - overload_penalty * overload; greatest id breaks ties",
        }
    return {
        "exact_root_keys": sorted(ALLOCATOR_CONTACT_KEYS), "frontier_count": 4,
        "contact_exact_keys": sorted(CONTACT_KEYS), "contacts_per_frontier": [2, 8],
        "coverage": ["same frontier in two orders", "filtered decoy", "two-floor composition threshold", "expansion", "regret", "greatest-id stable tie"],
        "eligibility": "world_valid and world_contact and not held_repeat and reversible",
        "oracle": "maximize (len(completed_floors) >= 2, predicted_expansion, public_regret, id)",
    }


def contact_seed(run: Path, label: str, parent: dict[str, Any], position: dict[str, Any], selection: dict[str, Any]) -> Path:
    interface_id = selection["next_interface"]["interface_id"]
    seed = run / f"{label}-seed"
    seed.mkdir()
    (seed / "subject-position.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "bound-interface.json").write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n")
    (seed / "contact.json").write_text(json.dumps(contact_template(interface_id), indent=2, sort_keys=True) + "\n")
    (seed / "contact-contract.json").write_text(json.dumps(contact_contract(interface_id), indent=2, sort_keys=True) + "\n")
    if interface_id == "joint-boundary-probe":
        capability = next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == "operations/joint.py")
        (seed / "retained-machinery.py").write_text(capability["source"])
    else:
        (seed / "retained-machinery.py").write_text(parent["allocation_machinery"][-1]["source"])
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["contact.json"], "immutable": ["retained-machinery.py"]}, indent=2) + "\n")
    (seed / "README.md").write_text(
        "Realize the subject's bound next interface by authoring a novel discriminating contact under the complete public contract. Run useful checks, edit only contact.json, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_contact(p82, context, run: Path, label: str, parent: dict[str, Any], position: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    interface_id = selection["next_interface"]["interface_id"]
    seed = contact_seed(run, label, parent, position, selection)
    prompt = "Author the novel objective contact bound by this exact subject and interface. Use ordinary tools, satisfy the public coverage contract, edit only contact.json, inspect the diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, prompt)
    try:
        value = json.loads((workspace / "contact.json").read_text())
    except (OSError, json.JSONDecodeError):
        value = None
    valid, conformance = validate_contact(interface_id, value)
    audit = context.audit_actor(label, output, base_audit, valid, ["contact.json"])
    binding = receipt = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0102-actor-authored-contact", "source_subject_digest": position["subject_digest"],
            "interface_binding_digest": selection["binding_digest"], "interface_id": interface_id,
            "actor_patch_digest": audit["patch_digest"], "contact": value, "conformance": conformance,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        receipt = score_contact(p82, parent, interface_id, value)
        (context.evidence(label) / "bound-contact.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
        (context.evidence(label) / "world-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    admitted = bool(binding and receipt and receipt["all_cases_passed"])
    return {"output": output, "audit": audit, "binding": binding, "world": receipt, "admitted": admitted}


def assimilation_seed(prior89, run: Path, label: str, parent: dict[str, Any], position: dict[str, Any], contact: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    consequence = {
        "subject_position": position, "contact_binding": contact["binding"], "world_receipt": contact["world"],
        "registered_interfaces": INTERFACE_REGISTRY,
    }
    (seed / "subject-contact-consequence.json").write_text(json.dumps(consequence, indent=2, sort_keys=True) + "\n")
    (seed / "assimilation.json").write_text(json.dumps(assimilation_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "next-interface.json").write_text(json.dumps(next_interface_template(), indent=2, sort_keys=True) + "\n")
    (seed / "next-interface-contract.json").write_text(json.dumps({
        "exact_keys": sorted(NEXT_INTERFACE_KEYS), "interface_ids": sorted(INTERFACE_IDS),
        "instruction": "Bind the registered interface worth opening after this consequence; the driver will execute it without researcher selection.",
    }, indent=2, sort_keys=True) + "\n")
    (seed / "retained-allocator.py").write_text(parent["allocation_machinery"][-1]["source"])
    capability = next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == "operations/joint.py")
    (seed / "retained-joint.py").write_text(capability["source"])
    editable = ["assimilation.json", "successor-opening.json", "next-interface.json"]
    immutable = ["retained-allocator.py", "retained-joint.py"]
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": editable, "immutable": immutable}, indent=2) + "\n")
    (seed / "README.md").write_text(
        "Assimilate the completed objective contact into an exact successor. Cite grounded case ids, preserve uncertainty, author a falsifiable opening, and bind the registered interface that should carry the next turn. Edit exactly the three permitted JSON files, keep machinery immutable, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_assimilation(prior89, p82, context, run: Path, label: str, parent: dict[str, Any], position: dict[str, Any], contact: dict[str, Any]) -> dict[str, Any]:
    seed = assimilation_seed(prior89, run, label, parent, position, contact)
    prompt = "Assimilate this exact world consequence, author the continuing opening, and bind its next registered interface. Use ordinary tools, preserve immutable machinery, edit exactly the three permitted JSON files, inspect the diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATOR_SCHEMA, prompt)
    try:
        assimilation = json.loads((workspace / "assimilation.json").read_text())
        opening = json.loads((workspace / "successor-opening.json").read_text())
        next_interface = json.loads((workspace / "next-interface.json").read_text())
        allocator_retained = (workspace / "retained-allocator.py").read_text() == parent["allocation_machinery"][-1]["source"]
        capability = next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == "operations/joint.py")
        joint_retained = (workspace / "retained-joint.py").read_text() == capability["source"]
    except (OSError, json.JSONDecodeError):
        assimilation, opening, next_interface = None, None, None
        allocator_retained = joint_retained = False
    valid = bool(
        valid_assimilation(assimilation) and prior89.valid_successor(opening)
        and valid_next_interface(next_interface) and allocator_retained and joint_retained
        and opening["next_opening"] != position["continuation"]["next_opening"]
    )
    allowed = ["assimilation.json", "successor-opening.json", "next-interface.json"]
    audit = context.audit_actor(label, output, base_audit, valid, allowed)
    passed_ids = {row["case_id"] for row in contact["world"]["rows"] if row["passed"]}
    cited = set(assimilation["settled_case_ids"]) if isinstance(assimilation, dict) and isinstance(assimilation.get("settled_case_ids"), list) else set()
    grounded = bool(audit["conformant"] and cited and cited.issubset(passed_ids))
    binding = None
    if grounded:
        body = {
            "authority": "ot-0102-consequence-assimilation", "source_subject_digest": position["subject_digest"],
            "contact_binding_digest": contact["binding"]["binding_digest"],
            "world_receipt_digest": contact["world"]["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"], "allocator_retention_derived": allocator_retained,
            "joint_retention_derived": joint_retained, "assimilation": assimilation,
            "successor_opening": opening, "next_interface": next_interface,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-assimilation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {
        "output": output, "audit": audit, "grounded": grounded,
        "allocator_retention_derived": allocator_retained, "joint_retention_derived": joint_retained,
        "binding": binding,
    }


def promote(p82, parent: dict[str, Any], selection: dict[str, Any], contact: dict[str, Any], assimilation: dict[str, Any], cycle: int):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    opening = assimilation["successor_opening"]
    body = {
        "authority": "world-promoted-two-cycle-subject-recurrence",
        "cycle": cycle, "source_subject_digest": parent["artifact_digest"],
        "interface_binding_digest": selection["binding_digest"],
        "contact_binding_digest": contact["binding_digest"],
        "world_receipt_digest": contact["world"]["receipt_digest"],
        "assimilation_binding_digest": assimilation["binding_digest"],
        "next_interface": assimilation["next_interface"],
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child["subject_recurrence_receipts"] = [*child.get("subject_recurrence_receipts", []), receipt]
    child["actor_authored_contacts"] = [*child.get("actor_authored_contacts", []), {
        "interface_id": contact["interface_id"], "binding_digest": contact["binding_digest"],
        "world_receipt_digest": contact["world"]["receipt_digest"],
    }]
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []), {
        "receipt": receipt, "assimilation": assimilation["assimilation"],
    }]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []), {
        "authority": "ot-0102-fresh-consequence-opening", "binding_digest": assimilation["binding_digest"],
        "opening": opening, "next_interface": assimilation["next_interface"],
    }]
    child["active_pursuit"] = {
        "authority": "ot-0102-fresh-consequence-opening",
        "selected_area": assimilation["next_interface"]["interface_id"],
        "next_pursuit": opening["next_opening"],
        "world_receipt_digest": contact["world"]["receipt_digest"],
    }
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["unresolved"] = opening["continuation_after_contact"]
    child["runtime"] = "sounding"
    return p82.seal(child), receipt


def representative_contact(interface_id: str) -> dict[str, Any]:
    if interface_id == "joint-boundary-probe":
        return {"interface_id": interface_id, "cases": [
            {"case_id": "fixture-j1", "context": {"risk_penalty": 10, "overload_penalty": 5}, "options": [
                {"id": "a", "recovery_value": 100, "recovery_risk": 2, "capacity": 50, "overload": 1},
                {"id": "b", "recovery_value": 90, "recovery_risk": 0.5, "capacity": 55, "overload": 1}]},
            {"case_id": "fixture-j2", "context": {"risk_penalty": 20, "overload_penalty": 10}, "options": [
                {"id": "a", "recovery_value": 80, "recovery_risk": 1, "capacity": 80, "overload": 2},
                {"id": "b", "recovery_value": 75, "recovery_risk": 0.5, "capacity": 80, "overload": 1.5}]},
            {"case_id": "fixture-j3", "context": {"risk_penalty": 5, "overload_penalty": 5}, "options": [
                {"id": "a", "recovery_value": 60, "recovery_risk": 1, "capacity": 70, "overload": 1},
                {"id": "b", "recovery_value": 58, "recovery_risk": 0.5, "capacity": 68, "overload": 0.5}]},
        ]}
    def row(identifier: str, floors: int, expansion: float, regret: float, **flags: bool) -> dict[str, Any]:
        return {
            "id": identifier, "target_path": f"world/{identifier}.py", "target_symbol": f"run_{identifier}",
            "completed_floors": [f"floor-{index}" for index in range(floors)],
            "public_regret": regret, "reversible": flags.get("reversible", True),
            "held_repeat": flags.get("held_repeat", False), "world_valid": flags.get("world_valid", True),
            "predicted_expansion": expansion, "world_contact": flags.get("world_contact", True),
            "surrender_condition": "Surrender on an independently scored mismatch.",
        }
    first = [row("many", 4, 5, 5), row("threshold", 2, 6, 4)]
    return {"interface_id": interface_id, "frontiers": [
        first, list(reversed(first)),
        [row("a", 2, 10, 2), row("b", 2, 10, 3), row("decoy", 3, 200, 200, held_repeat=True)],
        [row("a", 2, 10, 3), row("b", 2, 10, 3), row("c", 2, 9, 200)],
    ]}


def fixture_conformance(p82, parent: dict[str, Any]) -> dict[str, Any]:
    next_valid = {"interface_id": "joint-boundary-probe", "rationale": "realize the opening", "expected_information": "boundary consequence", "surrender_condition": "surrender on invalid contact"}
    rows = {}
    for interface_id in sorted(INTERFACE_IDS):
        contact = representative_contact(interface_id)
        valid, checks = validate_contact(interface_id, contact)
        score = score_contact(p82, parent, interface_id, contact) if valid else {"all_cases_passed": False}
        invalid = copy.deepcopy(contact)
        invalid.pop("cases" if interface_id == "joint-boundary-probe" else "frontiers")
        rejected, _ = validate_contact(interface_id, invalid)
        rows[interface_id] = {"representative_valid": valid, "representative_scored": score["all_cases_passed"], "malformed_rejected": not rejected, "checks": checks}
    result = {
        "next_interface_seed_rejected": not valid_next_interface(next_interface_template()),
        "next_interface_representative_passed": valid_next_interface(next_valid),
        "interfaces": rows,
    }
    result["passed"] = bool(
        result["next_interface_seed_rejected"] and result["next_interface_representative_passed"]
        and all(row["representative_valid"] and row["representative_scored"] and row["malformed_rejected"] for row in rows.values())
    )
    return result


def run_cycle(prior89, p82, runtime, context, run: Path, cycle: int, parent: dict[str, Any], selection: dict[str, Any]):
    position = active_position(parent)
    contact = run_contact(p82, context, run, f"cycle-{cycle}-contact", parent, position, selection)
    assimilation = None
    current = parent
    promotion = None
    if contact["admitted"]:
        assimilation = run_assimilation(prior89, p82, context, run, f"cycle-{cycle}-assimilation", parent, position, contact)
    if assimilation and assimilation["binding"]:
        current, promotion = promote(p82, parent, selection, contact["binding"], assimilation["binding"], cycle)
    operational = bool(
        promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
        and current["continuation"]["status"] == "open"
        and current["continuation"]["next_opening"] == assimilation["binding"]["successor_opening"]["next_opening"]
        and len(current.get("subject_recurrence_receipts", [])) == len(parent.get("subject_recurrence_receipts", [])) + 1
    )
    return {
        "position": position, "selection": selection, "contact": contact,
        "assimilation": assimilation, "promotion_receipt": promotion,
        "operational_transition_passed": operational, "current": current,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0102").resolve()
    prior92 = mechanism.load_prior()
    _, _, prior89, p82 = mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    if (
        parent["artifact_digest"] != PARENT_DIGEST or not runtime.identity_conforms(parent)
        or parent["runtime"] != "sounding" or parent["continuation"]["status"] != "open"
        or len(parent.get("allocation_correction_history", [])) != 5
    ):
        raise SystemExit("wrong OT-0101 promoted parent")
    fixtures = fixture_conformance(p82, parent)
    if args.preflight_only:
        result = {
            "parent_digest": parent["artifact_digest"], "parent_object_sha256": PARENT_OBJECT_SHA256,
            "base_implementation_sha256": BASE_SHA256, "interface_registry_digest": p82.digest(INTERFACE_REGISTRY),
            "fixture_conformance": fixtures,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0102 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    active = active_position(parent)
    erased = erased_position(p82, parent)
    (run / "bound-driver.json").write_text(json.dumps({
        "source_subject_digest": parent["artifact_digest"], "active_projection_digest": p82.digest(active),
        "erased_projection_digest": p82.digest(erased), "interface_registry": INTERFACE_REGISTRY,
        "interface_registry_digest": p82.digest(INTERFACE_REGISTRY), "cycle_budget": 2,
        "boundary_width": BOUNDARY_WIDTH, "fixture_conformance": fixtures,
    }, indent=2, sort_keys=True) + "\n")
    context = typed.base.make_context(runtime, run, repo)
    started = time.time()
    route = run_router(p82, context, run, "initial-router", active)
    cycle1 = cycle2 = None
    current = parent
    if route["binding"] and route["binding"]["next_interface"]["interface_id"] == "joint-boundary-probe":
        cycle1 = run_cycle(prior89, p82, runtime, context, run, 1, parent, route["binding"])
        current = cycle1["current"]
    if cycle1 and cycle1["operational_transition_passed"]:
        (run / "sealed-cycle-1-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        next_value = cycle1["assimilation"]["binding"]["next_interface"]
        body = {
            "authority": "ot-0102-successor-bound-interface", "source_subject_digest": current["artifact_digest"],
            "assimilation_binding_digest": cycle1["assimilation"]["binding"]["binding_digest"],
            "next_interface": next_value,
        }
        second_selection = {**body, "binding_digest": p82.digest(body)}
        (run / "cycle-2-bound-interface.json").write_text(json.dumps(second_selection, indent=2, sort_keys=True) + "\n")
        cycle2 = run_cycle(prior89, p82, runtime, context, run, 2, current, second_selection)
        current = cycle2["current"]
    two_cycle = bool(cycle1 and cycle1["operational_transition_passed"] and cycle2 and cycle2["operational_transition_passed"])
    erased_control = None
    if two_cycle:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        erased_control = run_router(p82, context, run, "opening-erased-router", erased)
    erased_selected_joint = bool(
        erased_control and erased_control["binding"]
        and erased_control["binding"]["next_interface"]["interface_id"] == "joint-boundary-probe"
    )
    result = {
        "authority": "ot-0102-two-cycle-subject-recurrence-driver",
        "source_subject_digest": parent["artifact_digest"], "interface_registry_digest": p82.digest(INTERFACE_REGISTRY),
        "initial_route": p82.compact(route),
        "cycle_1": p82.compact({key: value for key, value in cycle1.items() if key != "current"}) if cycle1 else None,
        "cycle_2": p82.compact({key: value for key, value in cycle2.items() if key != "current"}) if cycle2 else None,
        "opening_erased_router": p82.compact(erased_control) if erased_control else None,
        "two_cycle_operational_recurrence_passed": two_cycle,
        "opening_erased_selected_joint": erased_selected_joint,
        "observer_disposition": "promoted" if two_cycle else "conditional" if cycle1 and cycle1["operational_transition_passed"] else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "completed_cycles": 2 if two_cycle else 1 if cycle1 and cycle1["operational_transition_passed"] else 0,
        "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if two_cycle else 2


if __name__ == "__main__":
    raise SystemExit(main())
