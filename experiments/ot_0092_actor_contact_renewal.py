from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
PRIOR_PATH = ROOT / "ot_0091_post_consequence_assimilation.py"
PRIOR_SHA256 = "93f1c625e1eee7ecb0b1c96a5255f3dda0e52ca1e145a5848af92a67d874ae5c"
PARENT_DIGEST = "b1940ef7a434b60ac02436ea1e75f22179b83be096ec71075736eedcabe3f769"
INHERITED_OPENING = (
    "Verify multi-way tie reporting with three or more options, including reordered input and "
    "non-string numeric score values, while preserving greatest-id selection."
)
VERIFIER_DIGEST = "72c84133124b134044662f3047850614afeeb510bfc946484ce840df6b61f287"
COVERAGE_DIGEST = "0eeedd10d43508a69a6eafa0531eccb37f6058f153988b52c70cde89e3443fa3"
CONTACT_SCHEMA = REPO / "spec/ot-0092-contact-designer.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0091-assimilator.schema.json"
PLACEHOLDER = "__REPLACE__"
REQUIRED_REORDERED = {"hidden-four-order-a", "hidden-four-order-b"}
SECONDARY_HIDDEN = {"hidden-fraction-order-a", "hidden-fraction-order-b", "hidden-near-tie"}


def load_prior():
    if hashlib.sha256(PRIOR_PATH.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0091 implementation identity changed")
    name = "ot0092_frozen_ot0091"
    spec = importlib.util.spec_from_file_location(name, PRIOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_parent(prior91, p82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = p82.materialize(repo, store, "OT-0091", "reopened-parent-after-assimilation-rejection.json")
    return json.loads(path.read_text())


def capability(parent: dict[str, Any], target: str) -> dict[str, Any]:
    return next(row for row in reversed(parent["environmental_capabilities"]) if row.get("target_path") == target)


def option(option_id: str, base: float, coverage: float, cost: float = 0.0) -> dict[str, Any]:
    return {"id": option_id, "base_value": base, "coverage_units": coverage, "coordination_cost": cost}


def case(case_id: str, weight: float, options: list[dict[str, Any]]) -> dict[str, Any]:
    return {"case_id": case_id, "context": {"coverage_weight": weight}, "options": options}


FOUR_TIE = [option("amber", 9, 4, 0), option("cobalt", 11, 3, 0), option("jade", 13, 2, 0), option("zinc", 7, 5, 0)]
FRACTION_TIE = [option("alpha", 1.25, 2.5, .5), option("mango", .75, 3.5, .5), option("violet", 1.5, 2.0, .5)]
NEAR_TIE = [option("zulu", 10.0, 0), option("alpha", 10.1, 0), option("omega", 9.9, 0), option("beta", 9.8, 0)]
HIDDEN_CASES = [
    case("hidden-four-order-a", 2.0, FOUR_TIE),
    case("hidden-four-order-b", 2.0, [FOUR_TIE[i] for i in (3, 1, 0, 2)]),
    case("hidden-four-order-c", 2.0, [FOUR_TIE[i] for i in (2, 0, 3, 1)]),
    case("hidden-fraction-order-a", .5, FRACTION_TIE),
    case("hidden-fraction-order-b", .5, [FRACTION_TIE[i] for i in (2, 0, 1)]),
    case("hidden-near-tie", 1.0, NEAR_TIE),
]


RUN_PROBE_SOURCE = '''import json
from pathlib import Path
from studio.world import score_coverage
from verify_coverage import assess

cases = json.loads(Path("probe-cases.json").read_text())["cases"]
for case in cases:
    context, options = case["context"], case["options"]
    report = assess(context, options)
    print(json.dumps({"case_id": case["case_id"], "input_order": [item["id"] for item in options],
                      "scores": {item["id"]: score_coverage(context, item) for item in options},
                      "report": report}, sort_keys=True))
'''

EVALUATOR_SOURCE = '''import json
from pathlib import Path
from studio.coverage import choose_coverage
from studio.world import score_coverage
from verify_coverage import assess

cases = json.loads(Path("_cases.json").read_text())
rows = []
for case in cases:
    context, options = case["context"], case["options"]
    scores = {item["id"]: score_coverage(context, item) for item in options}
    maximum = max(scores.values())
    maximizing = sorted(key for key, value in scores.items() if abs(value - maximum) < 1e-12)
    oracle = maximizing[-1]
    try:
        report = assess(context, options)
        valid = (set(report) == {"selected_id", "max_score", "maximizing_ids", "tie_rule_preserved"}
                 and report["selected_id"] == choose_coverage(context, options) == oracle
                 and isinstance(report["max_score"], (int, float)) and abs(report["max_score"] - maximum) < 1e-12
                 and report["maximizing_ids"] == maximizing and report["tie_rule_preserved"] is True)
        rows.append({"case_id": case["case_id"], "input_order": [item["id"] for item in options],
                     "selected_id": report.get("selected_id"), "max_score": report.get("max_score"),
                     "maximizing_ids": report.get("maximizing_ids"),
                     "tie_rule_preserved": report.get("tie_rule_preserved"), "valid": valid})
    except Exception as error:
        rows.append({"case_id": case["case_id"], "input_order": [item["id"] for item in options],
                     "error_type": type(error).__name__, "valid": False})
print(json.dumps({"valid": all(row["valid"] for row in rows), "rows": rows}, sort_keys=True))
'''


def score_value(case_value: dict[str, Any], item: dict[str, Any]) -> float:
    return item["base_value"] + case_value["context"]["coverage_weight"] * item["coverage_units"] - item["coordination_cost"]


def valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def valid_case(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"case_id", "context", "options"} or not isinstance(value["case_id"], str) or not value["case_id"].strip():
        return False
    if not isinstance(value["context"], dict) or set(value["context"]) != {"coverage_weight"} or not valid_number(value["context"]["coverage_weight"]):
        return False
    options = value["options"]
    if not isinstance(options, list) or len(options) < 3:
        return False
    ids = []
    for item in options:
        if not isinstance(item, dict) or set(item) != {"id", "base_value", "coverage_units", "coordination_cost"}:
            return False
        if not isinstance(item["id"], str) or not item["id"].strip() or not all(valid_number(item[key]) for key in ("base_value", "coverage_units", "coordination_cost")):
            return False
        ids.append(item["id"])
    return len(ids) == len(set(ids))


def option_multiset(case_value: dict[str, Any]) -> str:
    return json.dumps(sorted(case_value["options"], key=lambda row: row["id"]), sort_keys=True)


def contact_conformance(value: Any) -> dict[str, Any]:
    cases = value.get("cases", []) if isinstance(value, dict) and set(value) == {"cases"} else []
    exact = bool(cases) and len(cases) >= 3 and all(valid_case(row) for row in cases) and len({row["case_id"] for row in cases}) == len(cases)
    reorder_group = False
    tied_group = False
    if exact:
        groups: dict[tuple[str, float], list[dict[str, Any]]] = {}
        for row in cases:
            groups.setdefault((option_multiset(row), float(row["context"]["coverage_weight"])), []).append(row)
        for rows in groups.values():
            orders = {tuple(item["id"] for item in row["options"]) for row in rows}
            if len(rows[0]["options"]) >= 3 and len(orders) >= 2:
                reorder_group = True
                scores = [score_value(rows[0], item) for item in rows[0]["options"]]
                if max(scores) - min(scores) < 1e-9:
                    tied_group = True
    unique_nonlexical = False
    if exact:
        for row in cases:
            scores = {item["id"]: score_value(row, item) for item in row["options"]}
            maximum = max(scores.values())
            winners = [key for key, score in scores.items() if abs(score - maximum) < 1e-9]
            if len(winners) == 1 and winners[0] != max(scores):
                unique_nonlexical = True
    result = {"exact_case_shape": exact, "reordered_multiway_group": reorder_group,
              "equal_score_reordered_group": tied_group, "unique_nonlexical_score_winner": unique_nonlexical}
    result["passed"] = all(result.values())
    return result


def write_environment(root: Path, parent: dict[str, Any]) -> None:
    files = {"studio/__init__.py": "", "studio/world.py": load_prior().load_prior().WORLD_SOURCE,
             "studio/coverage.py": capability(parent, "studio/coverage.py")["source"],
             "verify_coverage.py": capability(parent, "verify_coverage.py")["source"],
             "probe-cases.json": json.dumps({"cases": []}, indent=2) + "\n", "run_probe.py": RUN_PROBE_SOURCE}
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def evaluate(p82, parent: dict[str, Any], cases: list[dict[str, Any]], evidence: Path, label: str) -> dict[str, Any]:
    root = evidence / label
    write_environment(root, parent)
    (root / "_cases.json").write_text(json.dumps(cases, sort_keys=True) + "\n")
    (root / "_evaluate.py").write_text(EVALUATOR_SOURCE)
    completed = subprocess.run(["python3", "_evaluate.py"], cwd=root, text=True, capture_output=True, timeout=30)
    try:
        output = json.loads(completed.stdout)
    except json.JSONDecodeError:
        output = {"valid": False, "rows": []}
    body = {"authority": "ot-0092-complete-verifier-consequence", "cases_digest": p82.digest(cases),
            "returncode": completed.returncode, "stderr_digest": hashlib.sha256(completed.stderr.encode()).hexdigest(),
            "valid": completed.returncode == 0 and bool(output.get("valid")), "rows": output.get("rows", [])}
    return {**body, "receipt_digest": p82.digest(body)}


def contact_seed(run: Path, parent: dict[str, Any]) -> Path:
    seed = run / "contact-seed"
    seed.mkdir()
    write_environment(seed, parent)
    position = {"subject_digest": parent["artifact_digest"], "continuation": parent["continuation"],
                "active_pursuit": parent["active_pursuit"], "unresolved": parent["unresolved"],
                "retained_verifier_digest": capability(parent, "verify_coverage.py")["source_digest"]}
    (seed / "subject-position.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    contract = {"root_exact_keys": ["cases"], "minimum_cases": 3,
        "case_exact_keys": ["case_id", "context", "options"], "context_exact_keys": ["coverage_weight"],
        "option_exact_keys": ["id", "base_value", "coverage_units", "coordination_cost"],
        "structural_contact": ["same three-or-more-option multiset under at least two orders with all realized scores tied",
                               "one three-or-more-option unique realized winner whose id is not lexically greatest"],
        "instruction": "Author concrete finite numeric cases that settle the current opening; no values or preferred ids are supplied."}
    (seed / "probe-case-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "example-option.json").write_text(json.dumps(option("example", 1.0, 2.0, .5), indent=2) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["probe-cases.json"]}, indent=2) + "\n")
    (seed / "README.md").write_text("Continue the exact subject by designing the missing objective contact. Author probe-cases.json under the visible structural contract, run run_probe.py, inspect the exact diff, and report truthfully. Edit nothing else.\n")
    return seed


def run_contact(p82, context, run: Path, parent: dict[str, Any]) -> dict[str, Any]:
    seed = contact_seed(run, parent)
    prompt = "Continue the current opening by authoring the concrete multi-way and reordered contact it requires. Use ordinary tools, edit exactly probe-cases.json, exercise the retained verifier, inspect the exact diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor("contact", seed, CONTACT_SCHEMA, prompt)
    try:
        value = json.loads((workspace / "probe-cases.json").read_text())
    except (OSError, json.JSONDecodeError):
        value = None
    conformance = contact_conformance(value)
    immutable = p82.digest((workspace / "studio/coverage.py").read_text()) == COVERAGE_DIGEST and p82.digest((workspace / "verify_coverage.py").read_text()) == VERIFIER_DIGEST
    audit = context.audit_actor("contact", output, base_audit, bool(conformance["passed"] and immutable), ["probe-cases.json"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0092-pre-consequence-actor-contact", "source_subject_digest": parent["artifact_digest"],
                "actor_patch_digest": audit["patch_digest"], "cases": value["cases"], "case_conformance": conformance}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("contact") / "bound-contact.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding, "conformance": conformance}


def assimilation_projection(parent: dict[str, Any], contact: dict[str, Any], world: dict[str, Any], outcomes: bool, p82) -> dict[str, Any]:
    common = {"subject_digest": parent["artifact_digest"], "continuation": copy.deepcopy(parent["continuation"]),
        "active_pursuit": copy.deepcopy(parent["active_pursuit"]), "unresolved": parent["unresolved"],
        "latest_actor_opening": copy.deepcopy(parent["actor_originated_pursuit_openings"][-1]),
        "bound_contact": {"binding_digest": contact["binding_digest"], "cases_digest": p82.digest(contact["cases"]),
                          "case_ids": [row["case_id"] for row in contact["cases"]]},
        "consequence_identity": {"receipt_digest": world["receipt_digest"], "actor_case_count": len(world["actor_authored"]["rows"]),
                                 "hidden_case_count": len(world["hidden"]["rows"])}}
    if outcomes:
        return {**common, "consequence_outcomes": copy.deepcopy(world)}
    removed = {"actor_authored": world["actor_authored"], "hidden": world["hidden"], "developmentally_admitted": world["developmentally_admitted"]}
    return {**common, "consequence_outcomes": None, "outcome_erasure_receipt": {
        "authority": "ot-0092-complete-outcome-erasure", "removed_content_digest": p82.digest(removed),
        "removed_fields": sorted(removed), "receipt_digest": world["receipt_digest"]}}


def assimilation_score(prior91, value: dict[str, Any], opening: dict[str, Any], world: dict[str, Any], content_available: bool) -> dict[str, Any]:
    rows = {row["case_id"]: row for row in world["actor_authored"]["rows"] + world["hidden"]["rows"]}
    cited = value.get("settled_case_ids", []) if isinstance(value, dict) else []
    cited_valid = bool(cited) and all(case_id in rows and rows[case_id].get("valid") is True for case_id in cited)
    required = REQUIRED_REORDERED.issubset(cited) and bool(SECONDARY_HIDDEN.intersection(cited))
    stake = value.get("settled_stake", "").lower() if isinstance(value, dict) else ""
    stake_ok = all(token in stake for token in ("score", "maximizing")) and "tie" in stake and any(token in stake for token in ("reorder", "order"))
    disposition = value.get("disposition") in {"revise", "retire"} if isinstance(value, dict) else False
    remaining = bool(value.get("remaining_uncertainty", "").strip()) if isinstance(value, dict) and isinstance(value.get("remaining_uncertainty"), str) else False
    distinct = isinstance(opening, dict) and opening.get("next_opening") != INHERITED_OPENING
    grounded = bool(content_available and cited_valid and required)
    passed = bool(grounded and stake_ok and disposition and remaining and distinct)
    return {"content_available": content_available, "cited_valid": cited_valid, "required_hidden_citations": required,
            "stake_matches": stake_ok, "disposition_revision": disposition, "remaining_uncertainty": remaining,
            "distinct_opening": distinct, "receipt_grounded": grounded, "passed": passed}


def assimilation_seed(prior89, run: Path, label: str, projection: dict[str, Any]) -> Path:
    seed = run / f"{label}-seed"
    seed.mkdir()
    (seed / "subject-contact-consequence.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "assimilation.json").write_text(json.dumps(load_prior().assimilation_template(), indent=2, sort_keys=True) + "\n")
    (seed / "assimilation-contract.json").write_text(json.dumps(load_prior().assimilation_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(prior89.successor_template(), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["assimilation.json", "successor-opening.json"]}, indent=2) + "\n")
    (seed / "README.md").write_text("Assimilate available complete consequence into the exact pursuit. Distinguish settled from unresolved stakes, author what should be carried next, edit exactly the two permitted files, inspect the exact diff, and do not invent unavailable outcomes.\n")
    return seed


def run_assimilation(prior91, prior89, p82, context, run: Path, label: str, projection: dict[str, Any], world: dict[str, Any], content_available: bool) -> dict[str, Any]:
    seed = assimilation_seed(prior89, run, label, projection)
    prompt = "Assimilate available consequence into the current pursuit. Use ordinary tools, distinguish settled from unresolved stakes, author the substantive opening that should now be carried, edit exactly the two permitted files, inspect the diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATOR_SCHEMA, prompt)
    try:
        value = json.loads((workspace / "assimilation.json").read_text())
        opening = json.loads((workspace / "successor-opening.json").read_text())
    except (OSError, json.JSONDecodeError):
        value, opening = None, None
    valid = bool(prior91.valid_assimilation(value) and prior89.valid_successor(opening)
                 and (value["disposition"] == "retain" or opening["next_opening"] != INHERITED_OPENING))
    audit = context.audit_actor(label, output, base_audit, valid, ["assimilation.json", "successor-opening.json"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0092-pre-score-consequence-assimilation", "condition": label,
                "source_subject_digest": projection["subject_digest"], "projection_digest": p82.digest(projection),
                "actor_patch_digest": audit["patch_digest"], "assimilation": value, "successor_opening": opening}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-assimilation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    score = assimilation_score(prior91, value or {}, opening or {}, world, content_available) if binding else {"passed": False}
    score = {**score, "binding_digest": binding["binding_digest"] if binding else None, "condition": label}
    score["receipt_digest"] = p82.digest(score)
    (context.evidence(label) / "assimilation-score.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "binding": binding, "score": score}


def promote(p82, parent: dict[str, Any], contact: dict[str, Any], world: dict[str, Any], active: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    binding, opening = active["binding"], active["binding"]["successor_opening"]
    body = {"authority": "world-promoted-actor-contact-consequence-renewal", "source_subject_digest": parent["artifact_digest"],
        "contact_binding_digest": contact["binding_digest"], "world_receipt_digest": world["receipt_digest"],
        "assimilation_binding_digest": binding["binding_digest"], "assimilation_score_digest": active["score"]["receipt_digest"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["actor_authored_contacts"] = [*child.get("actor_authored_contacts", []), {"binding_digest": contact["binding_digest"], "cases_digest": p82.digest(contact["cases"]), "world_receipt_digest": world["receipt_digest"]}]
    child["pursuit_assimilations"] = [*child.get("pursuit_assimilations", []), {"receipt": receipt, "assimilation": binding["assimilation"]}]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []),
        {"authority": "fresh-complete-consequence-opening", "binding_digest": binding["binding_digest"], "opening": opening}]
    child["active_pursuit"] = {"authority": "fresh-complete-consequence-opening", "selected_area": "actor-designed-contact",
        "next_pursuit": opening["next_opening"], "world_receipt_digest": world["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["runtime"] = "sounding"
    child["unresolved"] = opening["continuation_after_contact"]
    return p82.seal(child), receipt


def fixture_conformance(prior91, prior89, p82, parent: dict[str, Any]) -> dict[str, Any]:
    reference_cases = [case("ref-tie-a", 2, FOUR_TIE), case("ref-tie-b", 2, list(reversed(FOUR_TIE))), case("ref-unique", 1, NEAR_TIE)]
    contact = contact_conformance({"cases": reference_cases})
    with tempfile.TemporaryDirectory() as directory:
        hidden = evaluate(p82, parent, HIDDEN_CASES, Path(directory), "hidden-reference")
    assimilation = {"disposition": "revise", "settled_case_ids": ["hidden-four-order-a", "hidden-four-order-b", "hidden-fraction-order-a"],
        "settled_stake": "Reordered multi-way tie score, maximizing set, and greatest-id selection all passed.",
        "remaining_uncertainty": "Whether mixed identifier types need a declared ordering policy.",
        "receipt_use": "Complete rows satisfy the retained opening.", "surrender_condition": "Restore it if later rows contradict the receipt."}
    opening = prior89.representative_successor(); opening["next_opening"] = "Test a declared ordering policy for mixed identifier types."
    world = {"actor_authored": hidden, "hidden": hidden, "developmentally_admitted": True, "receipt_digest": "fixture"}
    active = assimilation_score(prior91, assimilation, opening, world, True)
    erased = assimilation_score(prior91, assimilation, opening, world, False)
    result = {"parent_bound": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["next_opening"] == INHERITED_OPENING,
        "capabilities_bound": capability(parent, "verify_coverage.py")["source_digest"] == VERIFIER_DIGEST and capability(parent, "studio/coverage.py")["source_digest"] == COVERAGE_DIGEST,
        "contact_reference": contact, "hidden_reference": hidden,
        "active_assimilation_reference": active, "erased_assimilation_rejected": not erased["passed"]}
    result["passed"] = bool(result["parent_bound"] and result["capabilities_bound"] and contact["passed"] and hidden["valid"] and active["passed"] and result["erased_assimilation_rejected"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0092").resolve()
    prior91 = load_prior(); prior90 = prior91.load_prior(); prior89 = prior90.load_prior(); p82 = prior90.prior82(prior89)
    runtime = p82.load_runtime(repo, store); parent = load_parent(prior91, p82, repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent) or parent["artifact_digest"] != PARENT_DIGEST or parent["continuation"]["next_opening"] != INHERITED_OPENING:
        raise SystemExit("wrong OT-0091 reopened parent")
    fixtures = fixture_conformance(prior91, prior89, p82, parent)
    if args.preflight_only:
        print(json.dumps({"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "fixture_conformance": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0092 evidence")
    run.mkdir(parents=True); (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"]: raise SystemExit("pre-actor conformance failed")
    context = runtime.Context(run, repo); started = time.time(); contact_result = run_contact(p82, context, run, parent)
    world = None
    if contact_result["binding"]:
        public = evaluate(p82, parent, contact_result["binding"]["cases"], context.evidence("contact"), "actor-authored")
        hidden = evaluate(p82, parent, HIDDEN_CASES, context.evidence("contact"), "hidden")
        admitted = bool(public["valid"] and hidden["valid"])
        body = {"authority": "ot-0092-sealed-complete-contact", "source_subject_digest": parent["artifact_digest"],
            "contact_binding_digest": contact_result["binding"]["binding_digest"], "actor_authored": public, "hidden": hidden, "developmentally_admitted": admitted}
        world = {**body, "receipt_digest": p82.digest(body)}; (context.evidence("contact") / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    active = erased = None; current = parent; promotion = None
    if world and world["developmentally_admitted"]:
        active_projection = assimilation_projection(parent, contact_result["binding"], world, True, p82)
        erased_projection = assimilation_projection(parent, contact_result["binding"], world, False, p82)
        (run / "bound-assimilation-projections.json").write_text(json.dumps({"active_digest": p82.digest(active_projection), "erased_digest": p82.digest(erased_projection)}, indent=2) + "\n")
        active = run_assimilation(prior91, prior89, p82, context, run, "active", active_projection, world, True)
        if active["score"]["passed"]:
            current, promotion = promote(p82, parent, contact_result["binding"], world, active)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding" and current["continuation"]["status"] == "open" and current["continuation"]["next_opening"] == active["binding"]["successor_opening"]["next_opening"])
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        erased = run_assimilation(prior91, prior89, p82, context, run, "erased", erased_projection, world, False)
    causal = bool(operational and erased and not erased["score"]["passed"])
    result = {"authority": "ot-0092-actor-contact-renewal-driver", "source_subject_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256,
        "fixture_conformance": fixtures, "contact": p82.compact(contact_result), "world": world,
        "active": p82.compact(active) if active else None, "erased": p82.compact(erased) if erased else None, "promotion_receipt": promotion,
        "operational_transition_passed": operational, "consequence_content_causal_passed": causal,
        "observer_disposition": "promoted" if operational and causal else "conditional" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"], "elapsed_seconds": round(time.time()-started,3)}
    result["receipt_digest"] = p82.digest(result); (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n"); (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
