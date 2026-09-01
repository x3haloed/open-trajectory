from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0199_identity_preserving_set_invention.py"
BASE_SHA256 = "7ac4ca384f8fd6c6305b1d15e5712da1e13eaf0c0b0eab42548bf826977b16b3"
PARENT_DIGEST = "08c877ff66213187fa23330847a3d40b77568644e5a0f3923a6bf2426bb31fd0"
RENEWAL_SCHEMA = REPO / "spec/ot-0200-developmental-renewal.schema.json"
CONTACT_SCHEMA = REPO / "spec/ot-0200-contact-author.schema.json"
OPS = {"difference", "intersection", "union"}
BASE_SOURCES = {"options", "outcome", "blocked"}
EARNED = {"observed-unblocked", "latent-unblocked", "viable-unblocked"}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0199 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0200_frozen_ot0199", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.authority_base


def valid_ast(node: Any, source_name: str, depth: int = 1) -> bool:
    sources = BASE_SOURCES | {source_name}
    if not isinstance(node, dict) or depth > 4:
        return False
    if node.get("op") == "source":
        return set(node) == {"op", "name"} and node.get("name") in sources
    return bool(
        node.get("op") in OPS
        and set(node) == {"op", "left", "right"}
        and valid_ast(node["left"], source_name, depth + 1)
        and valid_ast(node["right"], source_name, depth + 1)
    )


def uses_source(node: dict[str, Any], source_name: str) -> bool:
    if node["op"] == "source":
        return node["name"] == source_name
    return uses_source(node["left"], source_name) or uses_source(node["right"], source_name)


def execute(node: dict[str, Any], case: dict[str, Any], source_name: str) -> set[str]:
    if node["op"] == "source":
        key = "source_values" if node["name"] == source_name else node["name"]
        return set(case[key])
    left = execute(node["left"], case, source_name)
    right = execute(node["right"], case, source_name)
    if node["op"] == "difference":
        return left - right
    if node["op"] == "intersection":
        return left & right
    return left | right


def earned(case: dict[str, Any]) -> dict[str, set[str]]:
    options, outcome, blocked = map(set, (case["options"], case["outcome"], case["blocked"]))
    return {
        "observed-unblocked": outcome - blocked,
        "latent-unblocked": options - outcome - blocked,
        "viable-unblocked": options - blocked,
    }


def valid_case(case: Any) -> bool:
    keys = {"case_id", "prediction", "outcome", "options", "blocked", "source_values"}
    if not isinstance(case, dict) or set(case) != keys:
        return False
    if not isinstance(case.get("case_id"), str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", case["case_id"]):
        return False
    if not all(isinstance(case.get(key), list) and len(case[key]) == len(set(case[key])) and all(isinstance(item, str) and item for item in case[key]) for key in keys - {"case_id"}):
        return False
    options = set(case["options"])
    return bool(set(case["outcome"]) <= options and set(case["blocked"]) <= options and set(case["source_values"]) <= options and case["source_values"])


def target_rows(contact: dict[str, Any], expression: dict[str, Any], source_name: str) -> list[dict[str, Any]]:
    rows = []
    for case in contact["cases"]:
        target = execute(expression, case, source_name)
        signatures = earned(case)
        passed = bool(
            target
            and target <= set(case["options"])
            and not target & set(case["blocked"])
            and all(target != value for value in signatures.values())
            and set(case["prediction"]) == target
        )
        rows.append({"case_id": case["case_id"], "target": sorted(target), "earned": {key: sorted(value) for key, value in signatures.items()}, "passed": passed})
    return rows


def valid_contact(contact: Any) -> bool:
    return bool(
        isinstance(contact, dict)
        and set(contact) == {"contact_id", "source_name", "rationale", "cases"}
        and isinstance(contact.get("contact_id"), str)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", contact["contact_id"])
        and isinstance(contact.get("source_name"), str)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,31}", contact["source_name"])
        and contact["source_name"] not in BASE_SOURCES
        and isinstance(contact.get("rationale"), str)
        and contact["rationale"].strip()
        and isinstance(contact.get("cases"), list)
        and 4 <= len(contact["cases"]) <= 6
        and all(valid_case(case) for case in contact["cases"])
        and len({case["case_id"] for case in contact["cases"]}) == len(contact["cases"])
        and len({tuple(case["source_values"]) for case in contact["cases"]}) >= 2
    )


def valid_renewal(value: Any, receipt_digest: str) -> bool:
    if not isinstance(value, dict) or set(value) != {"action", "prior_disposition", "completion_receipt_digest", "next_pursuit", "representative_contact", "rationale"}:
        return False
    pursuit = value.get("next_pursuit")
    if not isinstance(pursuit, dict) or set(pursuit) != {"pursuit_id", "property", "question", "rationale", "success_condition", "surrender_condition", "source_extension", "target_set", "expression", "contact_contract"}:
        return False
    source = pursuit.get("source_extension")
    contract = pursuit.get("contact_contract")
    source_name = source.get("source_name") if isinstance(source, dict) else None
    text_keys = {"property", "question", "rationale", "success_condition", "surrender_condition", "target_set"}
    base = bool(
        value.get("action") == "assimilate-completion-and-expand"
        and value.get("prior_disposition") == "completed-assimilated"
        and value.get("completion_receipt_digest") == receipt_digest
        and isinstance(value.get("rationale"), str) and value["rationale"].strip()
        and isinstance(pursuit.get("pursuit_id"), str) and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", pursuit["pursuit_id"])
        and all(isinstance(pursuit.get(key), str) and pursuit[key].strip() for key in text_keys)
        and pursuit["target_set"] not in EARNED
        and isinstance(source, dict) and set(source) == {"source_name", "world_meaning"}
        and isinstance(source_name, str) and re.fullmatch(r"[a-z][a-z0-9-]{2,31}", source_name) and source_name not in BASE_SOURCES
        and isinstance(source.get("world_meaning"), str) and source["world_meaning"].strip()
        and valid_ast(pursuit.get("expression"), source_name) and uses_source(pursuit["expression"], source_name)
        and isinstance(contract, dict) and set(contract) == {"target_set", "prediction_relation", "world_expected", "on_contact_violation", "on_no_mechanism", "rationale"}
        and contract.get("target_set") == pursuit["target_set"]
        and contract.get("prediction_relation") == "equals-target"
        and contract.get("world_expected") == "execute-target-expression"
        and contract.get("on_contact_violation") == "reject-contact"
        and contract.get("on_no_mechanism") == "open-mechanism-invention"
        and isinstance(contract.get("rationale"), str) and contract["rationale"].strip()
    )
    contact = value.get("representative_contact")
    if not base or not valid_contact(contact) or contact["source_name"] != source_name:
        return False
    rows = target_rows(contact, pursuit["expression"], source_name)
    return all(row["passed"] for row in rows)


def renewal_seed(root: Path, parent: dict[str, Any], pursuit: dict[str, Any], mechanism: dict[str, Any], receipt: dict[str, Any]) -> Path:
    seed = root / "renewal-seed"
    seed.mkdir()
    template = {
        "action": "assimilate-completion-and-expand",
        "prior_disposition": "completed-assimilated",
        "completion_receipt_digest": receipt["receipt_digest"],
        "next_pursuit": {
            "pursuit_id": "replace-with-next-pursuit",
            "property": "replace-with-what-matters-next",
            "question": "Replace with a new executable question.",
            "rationale": "Explain why this opens coherent future contact.",
            "success_condition": "State an executable success boundary.",
            "surrender_condition": "State an executable surrender boundary.",
            "source_extension": {"source_name": "new-signal", "world_meaning": "Define the new set-valued world distinction."},
            "target_set": "new-target",
            "expression": {"op": "difference", "left": {"op": "source", "name": "new-signal"}, "right": {"op": "source", "name": "blocked"}},
            "contact_contract": {"target_set": "new-target", "prediction_relation": "equals-target", "world_expected": "execute-target-expression", "on_contact_violation": "reject-contact", "on_no_mechanism": "open-mechanism-invention", "rationale": "Bind contact to the authored target."},
        },
        "representative_contact": {"contact_id": "replace-new-contact", "source_name": "new-signal", "rationale": "Demonstrate the new distinction.", "cases": [{"case_id": f"renewal-{index}", "prediction": [f"signal-{index}"], "outcome": [f"seen-{index}"], "options": [f"seen-{index}", f"signal-{index}", f"other-{index}"], "blocked": [], "source_values": [f"signal-{index}"]} for index in range(1, 5)]},
        "rationale": "Assimilate the completed pursuit and explain the renewal.",
    }
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(parent),
        "current-subject.json": parent,
        "completed-pursuit.json": pursuit,
        "installed-mechanism.json": mechanism,
        "completion-receipt.json": receipt,
        "earned-targets.json": sorted(EARNED),
        "expression-language.json": {"operations": sorted(OPS), "existing_sources": sorted(BASE_SOURCES), "maximum_depth": 4, "new_source_budget": 1},
        "developmental-renewal.json": template,
        "mutation-envelope.json": {"editable": ["developmental-renewal.json"], "immutable": ["subject-position.json", "current-subject.json", "completed-pursuit.json", "installed-mechanism.json", "completion-receipt.json", "earned-targets.json", "expression-language.json", "check_common.py", "check_renewal.py"]},
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    (seed / "check_common.py").write_bytes((ROOT / "ot_0200_checker.py").read_bytes())
    (seed / "check_renewal.py").write_text("""import json\nfrom pathlib import Path\nimport check_common as h\nv=json.loads(Path('developmental-renewal.json').read_text()); r=json.loads(Path('completion-receipt.json').read_text()); ok=h.valid_renewal(v,r['receipt_digest']); print(json.dumps({'passed':bool(ok)})); raise SystemExit(0 if ok else 2)\n""")
    (seed / "README.md").write_text("The inherited latent pursuit is complete. Assimilate its exact success receipt, then decide what distinction should become contactable next. The current options/outcome/blocked language can express only the already-earned observed, latent, viable, or empty nonblocked sets, so author one new set-valued world source and use it in a new target expression. Do not rename an earned target. Bind success, surrender, and contact to that expression, and demonstrate it on representative cases. Edit only developmental-renewal.json, run python3 check_renewal.py, inspect the diff, and report truthfully.\n")
    return seed


def run_renewal(context, prior131, p82, root, parent, pursuit, mechanism, receipt):
    seed = renewal_seed(root, parent, pursuit, mechanism, receipt)
    output, base_audit, workspace, _ = context.run_actor("post-capability-renewal", seed, RENEWAL_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "developmental-renewal.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        value, immutable_ok = None, False
    valid = bool(valid_renewal(value, receipt["receipt_digest"]) and immutable_ok and output and output.get("action") == "author-post-capability-renewal")
    audit = context.audit_actor("post-capability-renewal", output, base_audit, valid, ["developmental-renewal.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0200-bound-post-capability-renewal", "source_subject_digest": parent["artifact_digest"], "completion_receipt_digest": receipt["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "renewal": value}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "renewal": value, "binding": binding}


def compile_candidate(p82, parent, binding):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    renewal = binding["renewal"]
    next_pursuit = renewal["next_pursuit"]
    prior = child["active_developmental_stake"]
    history = {"authority": "ot-0200-completed-pursuit-assimilation", "prior_stake": prior, "disposition": renewal["prior_disposition"], "completion_receipt_digest": binding["completion_receipt_digest"], "renewal_binding_digest": binding["binding_digest"]}
    history["history_digest"] = p82.digest(history)
    child["assimilated_developmental_stakes"] = [*child.get("assimilated_developmental_stakes", []), history]
    child["post_completion_assimilation_decisions"] = [*child.get("post_completion_assimilation_decisions", []), binding]
    child["developmental_language_expansion_receipts"] = [*child.get("developmental_language_expansion_receipts", []), {"authority": "ot-0200-subject-authored-target-language", "renewal_binding_digest": binding["binding_digest"], "source_extension": next_pursuit["source_extension"], "target_set": next_pursuit["target_set"], "expression": next_pursuit["expression"]}]
    child["active_developmental_stake"] = {key: next_pursuit[key] for key in ("pursuit_id", "property", "question", "rationale", "success_condition", "surrender_condition", "target_set")}
    child["coupled_executable_pursuits"] = [*child.get("coupled_executable_pursuits", []), binding]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": next_pursuit["question"]}
    child["unresolved"] = next_pursuit["question"]
    return p82.seal(child)


def erased_binding(binding):
    return {"authority": binding["authority"], "source_subject_digest": binding["source_subject_digest"], "completion_receipt_digest": binding["completion_receipt_digest"], "actor_patch_digest": None, "renewal": None, "binding_digest": None}


def contact_seed(root, parent, binding):
    seed = root / "contact-seed"
    seed.mkdir()
    template = {"contact_id": "replace-expanded-contact", "source_name": "candidate-signal", "rationale": "Author a falsifiable contact for the inherited pursuit if one is bound.", "cases": [{"case_id": f"expanded-{index}", "prediction": [f"signal-{index}"], "outcome": [f"seen-{index}"], "options": [f"seen-{index}", f"signal-{index}", f"other-{index}"], "blocked": [], "source_values": [f"signal-{index}"]} for index in range(1, 5)]}
    files = {"subject-position.json": authority_base.reuse.worlds.base.active_position(parent), "renewal-binding.json": binding, "contact.json": template, "mutation-envelope.json": {"editable": ["contact.json"], "immutable": ["subject-position.json", "renewal-binding.json", "check_common.py", "check_contact.py"]}}
    for name, data in files.items(): authority_base.guide_base.write_json(seed / name, data)
    (seed / "check_common.py").write_bytes((ROOT / "ot_0200_checker.py").read_bytes())
    (seed / "check_contact.py").write_text("""import json\nfrom pathlib import Path\nimport check_common as h\nc=json.loads(Path('contact.json').read_text()); ok=h.valid_contact(c); print(json.dumps({'passed':bool(ok)})); raise SystemExit(0 if ok else 2)\n""")
    (seed / "README.md").write_text("Author novel falsifiable contact for the continuing subject. A populated renewal binding is inherited authority: use its selected source identity and make every prediction equal the independently executable target expression. Null renewal fields carry no authority; choose a coherent contact from the remaining subject position. The carrier requires four to six cases, unique tokens, a nonempty set-valued source inside options, and exact structural validity. Edit only contact.json, run python3 check_contact.py, inspect the diff, and report truthfully.\n")
    return seed


def hidden_cases(contact: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index, case in enumerate(contact["cases"], 1):
        tokens = sorted(set(case["options"]))
        mapping = {token: f"h{index}-{position}-{hashlib.sha256((case['case_id'] + token).encode()).hexdigest()[:6]}" for position, token in enumerate(tokens, 1)}
        row = {"case_id": f"hidden-{index:02d}"}
        for key in ("prediction", "outcome", "options", "blocked", "source_values"):
            row[key] = [mapping[token] for token in case[key]]
        rows.append(row)
    return rows


def run_contact(context, prior131, p82, root, label, parent, binding, target_binding, prior_digest):
    seed = contact_seed(root, parent, binding)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        contact = json.loads((workspace / "contact.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        contact, immutable_ok = None, False
    structural = bool(contact and valid_contact(contact))
    novel = bool(structural and p82.digest(contact) != prior_digest)
    valid = bool(structural and novel and immutable_ok and output and output.get("action") == "author-expanded-pursuit-contact")
    audit = context.audit_actor(label, output, base_audit, valid, ["contact.json"])
    pursuit = target_binding["renewal"]["next_pursuit"]
    rows = target_rows(contact, pursuit["expression"], pursuit["source_extension"]["source_name"]) if structural and contact["source_name"] == pursuit["source_extension"]["source_name"] else []
    hidden = hidden_cases(contact) if rows and all(row["passed"] for row in rows) else []
    hidden_rows = target_rows({**contact, "cases": hidden}, pursuit["expression"], pursuit["source_extension"]["source_name"]) if hidden else []
    aligned = bool(valid and rows and all(row["passed"] for row in rows) and hidden_rows and all(row["passed"] for row in hidden_rows))
    contact_binding = consequence = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0200-bound-expanded-pursuit-contact", "source_subject_digest": parent["artifact_digest"], "renewal_binding_digest": binding.get("binding_digest"), "actor_patch_digest": audit["patch_digest"], "contact": contact}
        contact_binding = {**body, "binding_digest": p82.digest(body)}
        cbody = {"authority": "ot-0200-sealed-expanded-target-contact", "contact_binding_digest": contact_binding["binding_digest"], "target_set": pursuit["target_set"], "hidden_contact_digest": p82.digest(hidden), "hidden_rows": hidden_rows}
        consequence = {**cbody, "receipt_digest": p82.digest(cbody)}
    return {"output": output, "audit": audit, "contact": contact, "binding": contact_binding, "consequence": consequence, "structural": structural, "novel": novel, "aligned": aligned}


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0200").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0199", "open-subject-after-latent-mechanism-invention.json")
    result199 = selector_base.load_artifact(p82, repo, store, "OT-0199", "identity-preserving-set-invention-aggregate.json")
    pursuit = parent["coupled_executable_pursuits"][-1]
    mechanism = parent["actor_authored_set_mechanisms"][-1]
    receipt = parent["mechanism_consequence_receipts"][-1]
    expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]
    route_floor = previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression)
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    representative = {
        "action": "assimilate-completion-and-expand", "prior_disposition": "completed-assimilated", "completion_receipt_digest": receipt["receipt_digest"],
        "next_pursuit": {"pursuit_id": "preserve-recoverable-options", "property": "recoverability", "question": "Can the subject preserve exactly the options marked recoverable by current world contact?", "rationale": "Completion frees the lineage to distinguish future recoverability rather than repeat observed or latent status.", "success_condition": "Prediction equals the unblocked recoverable set on every contact.", "surrender_condition": "Surrender if recoverability is unavailable, inconsistent, or requires a blocked option.", "source_extension": {"source_name": "recoverable", "world_meaning": "Options the current world marks as recoverable for a later move."}, "target_set": "recoverable-unblocked", "expression": {"op": "difference", "left": {"op": "source", "name": "recoverable"}, "right": {"op": "source", "name": "blocked"}}, "contact_contract": {"target_set": "recoverable-unblocked", "prediction_relation": "equals-target", "world_expected": "execute-target-expression", "on_contact_violation": "reject-contact", "on_no_mechanism": "open-mechanism-invention", "rationale": "Make the new recoverability distinction objectively executable."}},
        "representative_contact": {"contact_id": "recoverable-fixture", "source_name": "recoverable", "rationale": "Separate recoverability from observation and latent status.", "cases": [{"case_id": f"recoverable-{i}", "prediction": [f"r-{i}"], "outcome": [f"seen-{i}"], "options": [f"seen-{i}", f"r-{i}", f"latent-{i}", f"blocked-{i}"], "blocked": [f"blocked-{i}"], "source_values": [f"r-{i}", f"blocked-{i}"]} for i in range(1, 5)]},
        "rationale": "Assimilate direct latent success and open a different contactable distinction."
    }
    checker_valid = False
    with tempfile.TemporaryDirectory() as temp:
        seed = renewal_seed(Path(temp), parent, pursuit, mechanism, receipt)
        authority_base.guide_base.write_json(seed / "developmental-renewal.json", representative)
        checker_valid = valid_renewal(representative, receipt["receipt_digest"])
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0199_exact_promotion": result199["observer_disposition"] == "promoted" and result199["final_subject_digest"] == PARENT_DIGEST, "completion_exact": receipt["result"]["pass_count"] == receipt["result"]["case_count"] == 4 and receipt["mechanism_binding_digest"] == mechanism["binding_digest"], "old_target_language_exhausted": EARNED == {"observed-unblocked", "latent-unblocked", "viable-unblocked"}, "representative_valid": checker_valid, "representative_hidden_valid": all(row["passed"] for row in target_rows({**representative["representative_contact"], "cases": hidden_cases(representative["representative_contact"])}, representative["next_pursuit"]["expression"], "recoverable")), "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schemas_present": RENEWAL_SCHEMA.is_file() and CONTACT_SCHEMA.is_file()}, "completion_receipt_digest": receipt["receipt_digest"]}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0200 evidence")
    run.mkdir(parents=True)
    authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    renewal_root = run / "renewal-authoring"
    renewal_root.mkdir()
    renewal = run_renewal(context, prior131, p82, renewal_root, parent, pursuit, mechanism, receipt)
    if not renewal.get("binding"):
        result = {"authority": "ot-0200-subject-authored-target-language-expansion", "renewal": p82.compact(renewal), "checks": {"renewal_accepted": False, "passed": False}, "observer_disposition": "rejected", "final_subject_digest": parent["artifact_digest"], "fresh_actor_count": 1}
        result["receipt_digest"] = p82.digest(result)
        authority_base.guide_base.write_json(run / "aggregate.json", result)
        authority_base.guide_base.write_json(run / "final-full-subject.json", parent)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    candidate = compile_candidate(p82, parent, renewal["binding"])
    control = erased_binding(renewal["binding"])
    rows = []
    counts = {"active": 0, "control": 0}
    prior_digest = p82.digest(renewal["binding"]["renewal"]["representative_contact"])
    for branch in ["control", "active", "active", "control"] * 3:
        counts[branch] += 1
        index = counts[branch]
        actor_root = run / f"{branch}-{index:02d}-authoring"
        actor_root.mkdir()
        choice = run_contact(context, prior131, p82, actor_root, f"{branch}-{index:02d}", candidate if branch == "active" else parent, renewal["binding"] if branch == "active" else control, renewal["binding"], prior_digest)
        rows.append({"branch": branch, "index": index, "choice": choice})
    active_pass = sum(row["choice"]["aligned"] for row in rows if row["branch"] == "active")
    control_pass = sum(row["choice"]["aligned"] for row in rows if row["branch"] == "control")
    audits = [renewal["audit"], *[row["choice"]["audit"] for row in rows]]
    checks = {"thirteen_fresh_actors_accepted": len(audits) == 13 and all(prior131.audit_accepted(audit) for audit in audits), "renewal_valid": valid_renewal(renewal["renewal"], receipt["receipt_digest"]), "active_6_of_6": active_pass == 6, "control_at_most_2_of_6": control_pass <= 2, "advantage_at_least_4": active_pass - control_pass >= 4, "completion_receipt_exact": renewal["binding"]["completion_receipt_digest"] == receipt["receipt_digest"], "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        first = next(row for row in rows if row["branch"] == "active" and row["index"] == 1)
        child = copy.deepcopy(candidate)
        child.pop("artifact_digest", None)
        child["subject_originated_reopenings"] = [*child.get("subject_originated_reopenings", []), first["choice"]["binding"]]
        child["contact_consequence_receipts"] = [*child.get("contact_consequence_receipts", []), first["choice"]["consequence"]]
        operation_body = {"authority": "ot-0200-direct-expanded-pursuit-operation", "renewal_binding_digest": renewal["binding"]["binding_digest"], "contact_receipt_digest": first["choice"]["consequence"]["receipt_digest"], "operation": "open-generalized-mechanism-invention", "reason": "subject-authored target is contactable and has no installed scoped mechanism"}
        child["direct_pursuit_transitions"] = [*child.get("direct_pursuit_transitions", []), {**operation_body, "operation_digest": p82.digest(operation_body)}]
        target = renewal["renewal"]["next_pursuit"]["target_set"]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Invent and consequence-test a mechanism for the subject-authored {target} pursuit."}
        final = p82.seal(child)
    result = {"authority": "ot-0200-subject-authored-target-language-expansion", "source_subject_digest": parent["artifact_digest"], "candidate_subject_digest": candidate["artifact_digest"], "renewal": p82.compact(renewal), "rows": [{**row, "choice": p82.compact(row["choice"])} for row in rows], "active_pass_count": active_pass, "control_pass_count": control_pass, "route_floor": route_floor, "identity_floor": identity, "checks": checks, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 13}
    result["receipt_digest"] = p82.digest(result)
    authority_base.guide_base.write_json(run / "aggregate.json", result)
    authority_base.guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
