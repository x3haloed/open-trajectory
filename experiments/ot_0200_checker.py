from __future__ import annotations

import re
from typing import Any


OPS = {"difference", "intersection", "union"}
BASE_SOURCES = {"options", "outcome", "blocked"}
EARNED = {"observed-unblocked", "latent-unblocked", "viable-unblocked"}


def valid_ast(node: Any, source_name: str, depth: int = 1) -> bool:
    if not isinstance(node, dict) or depth > 4:
        return False
    if node.get("op") == "source":
        return set(node) == {"op", "name"} and node.get("name") in BASE_SOURCES | {source_name}
    return bool(node.get("op") in OPS and set(node) == {"op", "left", "right"} and valid_ast(node["left"], source_name, depth + 1) and valid_ast(node["right"], source_name, depth + 1))


def uses_source(node: dict[str, Any], source_name: str) -> bool:
    return node["name"] == source_name if node["op"] == "source" else uses_source(node["left"], source_name) or uses_source(node["right"], source_name)


def execute(node: dict[str, Any], case: dict[str, Any], source_name: str) -> set[str]:
    if node["op"] == "source":
        return set(case["source_values" if node["name"] == source_name else node["name"]])
    left, right = execute(node["left"], case, source_name), execute(node["right"], case, source_name)
    if node["op"] == "difference":
        return left - right
    if node["op"] == "intersection":
        return left & right
    return left | right


def earned(case: dict[str, Any]) -> dict[str, set[str]]:
    options, outcome, blocked = map(set, (case["options"], case["outcome"], case["blocked"]))
    return {"observed-unblocked": outcome - blocked, "latent-unblocked": options - outcome - blocked, "viable-unblocked": options - blocked}


def valid_case(case: Any) -> bool:
    keys = {"case_id", "prediction", "outcome", "options", "blocked", "source_values"}
    if not isinstance(case, dict) or set(case) != keys or not isinstance(case.get("case_id"), str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", case["case_id"]):
        return False
    if not all(isinstance(case.get(key), list) and len(case[key]) == len(set(case[key])) and all(isinstance(item, str) and item for item in case[key]) for key in keys - {"case_id"}):
        return False
    options = set(case["options"])
    return bool(set(case["outcome"]) <= options and set(case["blocked"]) <= options and set(case["source_values"]) <= options and case["source_values"])


def valid_contact(contact: Any) -> bool:
    return bool(isinstance(contact, dict) and set(contact) == {"contact_id", "source_name", "rationale", "cases"} and isinstance(contact.get("contact_id"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", contact["contact_id"]) and isinstance(contact.get("source_name"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,31}", contact["source_name"]) and contact["source_name"] not in BASE_SOURCES and isinstance(contact.get("rationale"), str) and contact["rationale"].strip() and isinstance(contact.get("cases"), list) and 4 <= len(contact["cases"]) <= 6 and all(valid_case(case) for case in contact["cases"]) and len({case["case_id"] for case in contact["cases"]}) == len(contact["cases"]) and len({tuple(case["source_values"]) for case in contact["cases"]}) >= 2)


def valid_renewal(value: Any, receipt_digest: str) -> bool:
    if not isinstance(value, dict) or set(value) != {"action", "prior_disposition", "completion_receipt_digest", "next_pursuit", "representative_contact", "rationale"}:
        return False
    pursuit = value.get("next_pursuit")
    if not isinstance(pursuit, dict) or set(pursuit) != {"pursuit_id", "property", "question", "rationale", "success_condition", "surrender_condition", "source_extension", "target_set", "expression", "contact_contract"}:
        return False
    source, contract = pursuit.get("source_extension"), pursuit.get("contact_contract")
    source_name = source.get("source_name") if isinstance(source, dict) else None
    if not (value.get("action") == "assimilate-completion-and-expand" and value.get("prior_disposition") == "completed-assimilated" and value.get("completion_receipt_digest") == receipt_digest and isinstance(value.get("rationale"), str) and value["rationale"].strip() and isinstance(pursuit.get("pursuit_id"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", pursuit["pursuit_id"]) and all(isinstance(pursuit.get(key), str) and pursuit[key].strip() for key in {"property", "question", "rationale", "success_condition", "surrender_condition", "target_set"}) and pursuit["target_set"] not in EARNED and isinstance(source, dict) and set(source) == {"source_name", "world_meaning"} and isinstance(source_name, str) and re.fullmatch(r"[a-z][a-z0-9-]{2,31}", source_name) and source_name not in BASE_SOURCES and isinstance(source.get("world_meaning"), str) and source["world_meaning"].strip() and valid_ast(pursuit.get("expression"), source_name) and uses_source(pursuit["expression"], source_name) and isinstance(contract, dict) and set(contract) == {"target_set", "prediction_relation", "world_expected", "on_contact_violation", "on_no_mechanism", "rationale"} and contract.get("target_set") == pursuit["target_set"] and contract.get("prediction_relation") == "equals-target" and contract.get("world_expected") == "execute-target-expression" and contract.get("on_contact_violation") == "reject-contact" and contract.get("on_no_mechanism") == "open-mechanism-invention" and isinstance(contract.get("rationale"), str) and contract["rationale"].strip()):
        return False
    contact = value.get("representative_contact")
    if not valid_contact(contact) or contact["source_name"] != source_name:
        return False
    for case in contact["cases"]:
        target = execute(pursuit["expression"], case, source_name)
        if not (target and target <= set(case["options"]) and not target & set(case["blocked"]) and all(target != prior for prior in earned(case).values()) and set(case["prediction"]) == target):
            return False
    return True
