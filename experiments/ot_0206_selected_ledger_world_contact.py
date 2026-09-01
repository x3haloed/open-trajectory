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
BASE_PATH = ROOT / "ot_0205_bounded_selector_normalization.py"
BASE_SHA256 = "7fc5e2bcc919ddc4402a7bc48084f5b17f0aa4f7f86ee33584923ebad88b7e80"
PARENT_DIGEST = "3e06b644385565325cd46f159b495f3dd8624f898c17cd30cfd62fe7834fb616"
SELECTOR_DIGEST = "eb8053c78554d0821056386e3150a9e3d41d6671a116e1ef59f52e89b3e8f6e9"
STAKE_ID = "preserve-contact-correction-ledger"
SELECTED_MEASUREMENT = 8
CONTACT_SCHEMA = REPO / "spec/ot-0206-ledger-contact-author.schema.json"
PROGRAM_SCHEMA = REPO / "spec/ot-0206-ledger-program-author.schema.json"
REPLAY_SCHEMA = REPO / "spec/ot-0206-ledger-replay.schema.json"
TOKEN = re.compile(r"[a-z][a-z0-9-]{1,31}")


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0205 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0206_frozen_ot0205", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
authority_base = previous.authority_base


def token(value: Any) -> bool:
    return isinstance(value, str) and TOKEN.fullmatch(value) is not None


def valid_case(value: Any) -> bool:
    keys = {"sequence", "contact_id", "identity_authority", "options", "blocked", "prediction", "outcome"}
    if not isinstance(value, dict) or set(value) != keys:
        return False
    if not isinstance(value["sequence"], int) or not 1 <= value["sequence"] <= 8 or not token(value["contact_id"]) or value["contact_id"].startswith("replace-"):
        return False
    if value["identity_authority"] not in {"active", "revoked"}:
        return False
    for name in ("options", "blocked", "prediction", "outcome"):
        items = value[name]
        if not isinstance(items, list) or any(not token(item) or item.startswith("replace-") for item in items) or len(items) != len(set(items)):
            return False
    options, blocked, prediction, outcome = map(set, (value["options"], value["blocked"], value["prediction"], value["outcome"]))
    if len(options) < 3 or not outcome or not blocked <= options or not prediction <= options or not outcome <= options or not (outcome - blocked):
        return False
    return value["identity_authority"] != "revoked" or (bool(prediction) and prediction != outcome)


def valid_half(cases: list[dict[str, Any]]) -> bool:
    authorities = [case["identity_authority"] for case in cases]
    correction_distinguishes = any(
        case["identity_authority"] == "revoked"
        and [item for item in case["prediction"] if item not in case["blocked"]]
        != [item for item in case["outcome"] if item not in case["blocked"]]
        for case in cases
    )
    blocked_observed = any(set(case["blocked"]) & set(case["outcome"]) for case in cases)
    return authorities.count("active") == 2 and authorities.count("revoked") == 2 and correction_distinguishes and blocked_observed


def valid_suite(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"suite_id", "cases"} or not token(value.get("suite_id")) or value["suite_id"].startswith("replace-"):
        return False
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 8 or not all(valid_case(case) for case in cases):
        return False
    if [case["sequence"] for case in cases] != list(range(1, 9)) or len({case["contact_id"] for case in cases}) != 8:
        return False
    return valid_half(cases[:4]) and valid_half(cases[4:])


PROGRAM_KEYS = {"action", "entry_order", "contact_source", "exclude_blocked", "prediction_policy", "revoked_identity_policy", "active_identity_policy"}


def valid_program(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == PROGRAM_KEYS
        and value.get("action") == "author-contact-correction-ledger"
        and value.get("entry_order") in {"input", "sequence-ascending", "sequence-descending"}
        and value.get("contact_source") in {"options", "prediction", "outcome"}
        and isinstance(value.get("exclude_blocked"), bool)
        and value.get("prediction_policy") in {"exclude", "retain"}
        and value.get("revoked_identity_policy") in {"mark-corrected", "preserve", "omit"}
        and value.get("active_identity_policy") in {"mark-active", "mark-corrected", "omit"}
    )


def render_ledger(program: dict[str, Any], suites: list[dict[str, Any]], public_only: bool = False) -> dict[str, Any]:
    cases = []
    for suite in suites:
        for case in suite["cases"][:4] if public_only else suite["cases"]:
            cases.append({**case, "suite_id": suite["suite_id"]})
    if program["entry_order"] == "sequence-ascending":
        cases.sort(key=lambda case: (case["suite_id"], case["sequence"]))
    elif program["entry_order"] == "sequence-descending":
        cases.sort(key=lambda case: (case["suite_id"], -case["sequence"]))
    entries = []
    for case in cases:
        contacts = list(case[program["contact_source"]])
        if program["exclude_blocked"]:
            contacts = [item for item in contacts if item not in case["blocked"]]
        policy = program["revoked_identity_policy"] if case["identity_authority"] == "revoked" else program["active_identity_policy"]
        if policy == "omit":
            continue
        status = "corrected-revoked" if policy == "mark-corrected" else "active"
        entry = {"suite_id": case["suite_id"], "sequence": case["sequence"], "contact_id": case["contact_id"], "preserved_contacts": contacts, "identity_status": status}
        if program["prediction_policy"] == "retain":
            entry["prediction"] = case["prediction"]
        entries.append(entry)
    return {"entries": entries}


EXPECTED_PROGRAM = {
    "action": "author-contact-correction-ledger",
    "entry_order": "sequence-ascending",
    "contact_source": "outcome",
    "exclude_blocked": True,
    "prediction_policy": "exclude",
    "revoked_identity_policy": "mark-corrected",
    "active_identity_policy": "mark-active",
}


def negative_programs() -> dict[str, dict[str, Any]]:
    programs = {}
    for name, changes in {
        "prediction-copy": {"contact_source": "prediction"},
        "options-copy": {"contact_source": "options"},
        "no-block-exclusion": {"exclude_blocked": False},
        "reversed-order": {"entry_order": "sequence-descending"},
        "mark-all-corrected": {"active_identity_policy": "mark-corrected"},
    }.items():
        programs[name] = {**EXPECTED_PROGRAM, **changes}
    return programs


def evaluate_program(program: Any, suites: list[dict[str, Any]], public_only: bool = False) -> dict[str, Any]:
    if not valid_program(program):
        return {"case_count": sum(4 if public_only else 8 for _ in suites), "pass_count": 0, "passed": False, "rows": [], "properties": {}}
    observed = render_ledger(program, suites, public_only)
    expected = render_ledger(EXPECTED_PROGRAM, suites, public_only)
    expected_by_id = {(row["suite_id"], row["contact_id"]): row for row in expected["entries"]}
    observed_by_id = {(row["suite_id"], row["contact_id"]): row for row in observed["entries"]}
    rows = []
    for key, target in expected_by_id.items():
        got = observed_by_id.get(key)
        rows.append({"suite_id": key[0], "contact_id": key[1], "passed": got == target})
    order_exact = [(row["suite_id"], row["sequence"]) for row in observed["entries"]] == [(row["suite_id"], row["sequence"]) for row in expected["entries"]]
    blocked_excluded = all(not (set(row["preserved_contacts"]) & set(case["blocked"])) for row in observed["entries"] for suite in suites for case in suite["cases"] if suite["suite_id"] == row["suite_id"] and case["contact_id"] == row["contact_id"])
    revocation_exact = all(row["identity_status"] == ("corrected-revoked" if case["identity_authority"] == "revoked" else "active") for row in observed["entries"] for suite in suites for case in suite["cases"] if suite["suite_id"] == row["suite_id"] and case["contact_id"] == row["contact_id"])
    prediction_excluded = all("prediction" not in row for row in observed["entries"])
    complete = len(observed["entries"]) == len(expected["entries"])
    passed = complete and order_exact and blocked_excluded and revocation_exact and prediction_excluded and all(row["passed"] for row in rows)
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "passed": passed, "rows": rows, "properties": {"complete": complete, "order_exact": order_exact, "blocked_excluded": blocked_excluded, "revocation_exact": revocation_exact, "prediction_excluded": prediction_excluded}}


def contact_seed(root: Path, parent: dict[str, Any], stake: dict[str, Any], index: int) -> Path:
    seed = root / "contact-seed"
    seed.mkdir()
    cases = []
    for sequence in range(1, 9):
        authority = "active" if sequence % 2 else "revoked"
        cases.append({"sequence": sequence, "contact_id": f"replace-contact-{sequence}", "identity_authority": authority, "options": [f"replace-{sequence}-a", f"replace-{sequence}-b", f"replace-{sequence}-c"], "blocked": [f"replace-{sequence}-c"], "prediction": [f"replace-{sequence}-b"], "outcome": [f"replace-{sequence}-a", f"replace-{sequence}-c"]})
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(parent),
        "selected-stake.json": stake,
        "contact-suite.json": {"suite_id": f"replace-suite-{index}", "cases": cases},
        "mutation-envelope.json": {"editable": ["contact-suite.json"], "immutable": ["subject-position.json", "selected-stake.json", "check_contact.py"]},
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    checker = '''import json,re\nfrom pathlib import Path\nT=re.compile(r"[a-z][a-z0-9-]{1,31}")\ndef tok(x): return isinstance(x,str) and T.fullmatch(x) is not None\ndef case(c):\n k={"sequence","contact_id","identity_authority","options","blocked","prediction","outcome"}\n if not isinstance(c,dict) or set(c)!=k or not isinstance(c["sequence"],int) or not 1<=c["sequence"]<=8 or not tok(c["contact_id"]) or c["contact_id"].startswith("replace-") or c["identity_authority"] not in {"active","revoked"}: return False\n for n in ("options","blocked","prediction","outcome"):\n  if not isinstance(c[n],list) or any(not tok(v) or v.startswith("replace-") for v in c[n]) or len(c[n])!=len(set(c[n])): return False\n o,b,p,y=map(set,(c["options"],c["blocked"],c["prediction"],c["outcome"])); return len(o)>=3 and bool(y) and b<=o and p<=o and y<=o and bool(y-b) and (c["identity_authority"]!="revoked" or (bool(p) and p!=y))\ndef half(cs):\n a=[c["identity_authority"] for c in cs]; d=any(c["identity_authority"]=="revoked" and [v for v in c["prediction"] if v not in c["blocked"]]!=[v for v in c["outcome"] if v not in c["blocked"]] for c in cs); b=any(set(c["blocked"])&set(c["outcome"]) for c in cs); return a.count("active")==2 and a.count("revoked")==2 and d and b\ns=json.loads(Path("contact-suite.json").read_text()); cs=s.get("cases") if isinstance(s,dict) else None; ok=isinstance(s,dict) and set(s)=={"suite_id","cases"} and tok(s.get("suite_id")) and not s["suite_id"].startswith("replace-") and isinstance(cs,list) and len(cs)==8 and all(case(c) for c in cs) and [c["sequence"] for c in cs]==list(range(1,9)) and len({c["contact_id"] for c in cs})==8 and half(cs[:4]) and half(cs[4:]); print(json.dumps({"passed":bool(ok)},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''
    (seed / "check_contact.py").write_text(checker)
    (seed / "README.md").write_text("Author one independent ordered contact suite for the exact selected ledger pursuit. Replace every placeholder token with your own coherent contact. Both cases 1-4 and 5-8 must contain two active and two revoked identities, at least one blocked observed outcome, and a revoked case whose stale prediction differs from observed outcome after blocking. Preserve at least one observed unblocked contact per case. The later ledger actor will see only cases 1-4; cases 5-8 are sealed consequence. Edit only contact-suite.json, run python3 check_contact.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_contact(context, prior131, root: Path, label: str, parent: dict[str, Any], stake: dict[str, Any], index: int) -> dict[str, Any]:
    seed = contact_seed(root, parent, stake, index)
    output, base_audit, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        suite = json.loads((workspace / "contact-suite.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        suite, immutable_ok = None, False
    valid = bool(valid_suite(suite) and immutable_ok and output and output.get("action") == "author-independent-ledger-contact")
    audit = context.audit_actor(label, output, base_audit, valid, ["contact-suite.json"])
    return {"output": output, "audit": audit, "suite": suite, "accepted": valid and prior131.audit_accepted(audit)}


def program_seed(root: Path, parent: dict[str, Any], stake: dict[str, Any], suites: list[dict[str, Any]]) -> Path:
    seed = root / "program-seed"
    seed.mkdir()
    public = [{"suite_id": suite["suite_id"], "cases": suite["cases"][:4]} for suite in suites]
    template = {**EXPECTED_PROGRAM, "contact_source": "options", "exclude_blocked": False, "prediction_policy": "retain", "revoked_identity_policy": "preserve"}
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(parent),
        "current-subject.json": parent,
        "selected-stake.json": stake,
        "public-contact-bank.json": public,
        "ledger-program.json": template,
        "mutation-envelope.json": {"editable": ["ledger-program.json"], "immutable": ["subject-position.json", "current-subject.json", "selected-stake.json", "public-contact-bank.json", "check_program.py"]},
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    expected = json.dumps(EXPECTED_PROGRAM, sort_keys=True)
    checker = f'''import json\nfrom pathlib import Path\np=json.loads(Path("ledger-program.json").read_text()); suites=json.loads(Path("public-contact-bank.json").read_text()); keys={{"action","entry_order","contact_source","exclude_blocked","prediction_policy","revoked_identity_policy","active_identity_policy"}}; structural=isinstance(p,dict) and set(p)==keys and p.get("action")=="author-contact-correction-ledger" and p.get("entry_order") in {{"input","sequence-ascending","sequence-descending"}} and p.get("contact_source") in {{"options","prediction","outcome"}} and isinstance(p.get("exclude_blocked"),bool) and p.get("prediction_policy") in {{"exclude","retain"}} and p.get("revoked_identity_policy") in {{"mark-corrected","preserve","omit"}} and p.get("active_identity_policy") in {{"mark-active","mark-corrected","omit"}}\nexpected=json.loads({expected!r}); ok=structural and p==expected\nprint(json.dumps({{"passed":bool(ok),"public_case_count":sum(len(s["cases"]) for s in suites)}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''
    (seed / "check_program.py").write_text(checker)
    (seed / "README.md").write_text("Author one generic executable ledger program for the exact subject-selected stake. Preserve observed unblocked contact, exclude stale prediction, mark revoked identities as corrected without mislabeling active identities, and retain sealed sequence order. The public bank contains only the first half of each independently authored suite; hidden halves are unavailable. Edit only ledger-program.json, run python3 check_program.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_program(context, prior131, p82, root: Path, label: str, parent: dict[str, Any], stake: dict[str, Any], suites: list[dict[str, Any]]) -> dict[str, Any]:
    seed = program_seed(root, parent, stake, suites)
    output, base_audit, workspace, _ = context.run_actor(label, seed, PROGRAM_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        program = json.loads((workspace / "ledger-program.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        program, immutable_ok = None, False
    structural = bool(valid_program(program) and immutable_ok and output and output.get("action") == "author-contact-correction-ledger")
    audit = context.audit_actor(label, output, base_audit, structural, ["ledger-program.json"])
    public_result = evaluate_program(program, suites, True)
    hidden_result = evaluate_program(program, [{"suite_id": suite["suite_id"], "cases": suite["cases"][4:]} for suite in suites])
    complete_result = evaluate_program(program, suites)
    binding = None
    if structural and public_result["passed"] and hidden_result["passed"] and prior131.audit_accepted(audit):
        body = {"authority": "ot-0206-bound-contact-correction-ledger", "source_subject_digest": parent["artifact_digest"], "stake_id": stake["stake_id"], "actor_patch_digest": audit["patch_digest"], "program": program, "public_result": public_result, "hidden_result": hidden_result}
        binding = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "program": program, "public_result": public_result, "hidden_result": hidden_result, "complete_result": complete_result, "binding": binding, "passed": binding is not None}


def replay_seed(root: Path, parent: dict[str, Any], stake: dict[str, Any], binding: dict[str, Any], suites: list[dict[str, Any]]) -> Path:
    seed = root / "replay-seed"
    seed.mkdir()
    expected = render_ledger(binding["program"], suites)
    files = {
        "subject-position.json": authority_base.reuse.worlds.base.active_position(parent),
        "selected-stake.json": stake,
        "ledger-binding.json": binding,
        "sealed-contact-bank.json": suites,
        "replay-ledger.json": {"entries": []},
        "mutation-envelope.json": {"editable": ["replay-ledger.json"], "immutable": ["subject-position.json", "selected-stake.json", "ledger-binding.json", "sealed-contact-bank.json", "render_ledger.py", "check_replay.py"]},
    }
    for name, data in files.items():
        authority_base.guide_base.write_json(seed / name, data)
    expected_text = json.dumps(expected, sort_keys=True)
    (seed / "render_ledger.py").write_text(f'''import json\nfrom pathlib import Path\nPath("replay-ledger.json").write_text(json.dumps(json.loads({expected_text!r}),indent=2,sort_keys=True)+"\\n")\n''')
    (seed / "check_replay.py").write_text(f'''import json\nfrom pathlib import Path\nobserved=json.loads(Path("replay-ledger.json").read_text()); expected=json.loads({expected_text!r}); ok=observed==expected; print(json.dumps({{"passed":ok,"entry_count":len(observed.get("entries",[])) if isinstance(observed,dict) else 0}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Reopen the exact selected pursuit through its installed ledger program and full sealed contact bank. Produce the replay ledger by running python3 render_ledger.py, then run python3 check_replay.py. Do not alter the program, bank, renderer, checker, stake, or subject position. Inspect the exact diff and report truthfully.\n")
    return seed


def run_replay(context, prior131, p82, root: Path, label: str, parent: dict[str, Any], stake: dict[str, Any], binding: dict[str, Any], suites: list[dict[str, Any]]) -> dict[str, Any]:
    seed = replay_seed(root, parent, stake, binding, suites)
    output, base_audit, workspace, _ = context.run_actor(label, seed, REPLAY_SCHEMA, (seed / "README.md").read_text().strip())
    expected = render_ledger(binding["program"], suites)
    try:
        ledger = json.loads((workspace / "replay-ledger.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        ledger, immutable_ok = None, False
    valid = bool(ledger == expected and immutable_ok and output and output.get("action") == "replay-contact-correction-ledger")
    audit = context.audit_actor(label, output, base_audit, valid, ["replay-ledger.json"])
    receipt_body = {"authority": "ot-0206-independent-ledger-replay", "source_subject_digest": parent["artifact_digest"], "ledger_binding_digest": binding["binding_digest"], "ledger_digest": p82.digest(ledger) if ledger is not None else None, "entry_count": len(expected["entries"]), "exact": ledger == expected}
    return {"output": output, "audit": audit, "ledger": ledger, "receipt": {**receipt_body, "receipt_digest": p82.digest(receipt_body)}, "passed": valid and prior131.audit_accepted(audit)}


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0206").resolve()
    prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0205", "open-subject-after-selector-renewal.json")
    result205 = selector_base.load_artifact(p82, repo, store, "OT-0205", "bounded-selector-normalization-aggregate.json")
    stake = parent["active_developmental_stake"]
    selector = parent["pursuit_selector_capabilities"][-1]
    selected = parent["selected_pursuit_receipts"][-1]
    expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]
    route_floor = previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression)
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    sample_suite = {"suite_id": "fixture-suite", "cases": []}
    for sequence in range(1, 9):
        authority = "active" if sequence % 2 else "revoked"
        sample_suite["cases"].append({"sequence": sequence, "contact_id": f"fixture-contact-{sequence}", "identity_authority": authority, "options": [f"fixture-{sequence}-a", f"fixture-{sequence}-b", f"fixture-{sequence}-c"], "blocked": [f"fixture-{sequence}-c"], "prediction": [f"fixture-{sequence}-b"], "outcome": [f"fixture-{sequence}-a", f"fixture-{sequence}-c"]})
    with tempfile.TemporaryDirectory() as temp:
        replay_fixture = replay_seed(Path(temp), parent, stake, {"program": EXPECTED_PROGRAM, "binding_digest": "fixture-binding"}, [sample_suite])
        replay_constructs = (replay_fixture / "render_ledger.py").is_file() and (replay_fixture / "check_replay.py").is_file()
    fixture_negative_results = {name: evaluate_program(program, [sample_suite]) for name, program in negative_programs().items()}
    fixtures = {"checks": {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0205_exact_promotion": result205["observer_disposition"] == "promoted" and result205["final_subject_digest"] == PARENT_DIGEST, "selected_stake_exact": stake["stake_id"] == STAKE_ID and selected["selected_stake"] == stake, "selector_exact": selector["selector_binding_digest"] == SELECTOR_DIGEST and selector["selector"]["dimension_name"] == "decision-ready-signal", "selected_measurement_exact": next(row["measurement"] for row in result205["rows"] if row["branch"] == "active" and row["index"] == 1 for row in row["choice"]["portfolio"]["candidates"] if row["stake"]["stake_id"] == STAKE_ID) == SELECTED_MEASUREMENT, "fixture_suite_valid": valid_suite(sample_suite), "expected_program_valid": valid_program(EXPECTED_PROGRAM) and evaluate_program(EXPECTED_PROGRAM, [sample_suite])["passed"], "five_negative_controls_fail_fixture": all(not result["passed"] for result in fixture_negative_results.values()), "replay_fixture_constructs": replay_constructs, "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schemas_present": CONTACT_SCHEMA.is_file() and PROGRAM_SCHEMA.is_file() and REPLAY_SCHEMA.is_file()}, "source_subject_digest": parent["artifact_digest"], "selector_binding_digest": selector["selector_binding_digest"], "selected_stake_id": stake["stake_id"], "selected_measurement": SELECTED_MEASUREMENT, "negative_control_results": fixture_negative_results}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0206 evidence")
    run.mkdir(parents=True); authority_base.guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    contact_rows = []
    for index in range(1, 5):
        actor_root = run / f"contact-{index:02d}-authoring"; actor_root.mkdir()
        contact_rows.append({"index": index, "choice": run_contact(context, prior131, actor_root, f"contact-{index:02d}", parent, stake, index)})
    contact_suites = [row["choice"]["suite"] for row in contact_rows if row["choice"]["accepted"]]
    contacts_globally_distinct = len(contact_suites) == 4 and len({suite["suite_id"] for suite in contact_suites}) == 4 and len({(suite["suite_id"], case["contact_id"]) for suite in contact_suites for case in suite["cases"]}) == 32
    contacts_pass = len(contact_rows) == 4 and all(row["choice"]["accepted"] for row in contact_rows) and contacts_globally_distinct
    suites = [row["choice"]["suite"] for row in contact_rows] if contacts_pass else []
    program_rows = []
    if contacts_pass:
        for index in range(1, 5):
            actor_root = run / f"program-{index:02d}-authoring"; actor_root.mkdir()
            program_rows.append({"index": index, "choice": run_program(context, prior131, p82, actor_root, f"program-{index:02d}", parent, stake, suites)})
    programs_pass = len(program_rows) == 4 and all(row["choice"]["passed"] for row in program_rows)
    replay_rows = []
    if programs_pass:
        binding = program_rows[0]["choice"]["binding"]
        for index in range(1, 3):
            actor_root = run / f"replay-{index:02d}-authoring"; actor_root.mkdir()
            replay_rows.append({"index": index, "choice": run_replay(context, prior131, p82, actor_root, f"replay-{index:02d}", parent, stake, binding, suites)})
    all_results = [row["choice"]["complete_result"] for row in program_rows]
    negative_results = {name: evaluate_program(program, suites) for name, program in negative_programs().items()} if suites else {}
    checkpoints = {
        "01_independent_contact_sealed": contacts_pass,
        "02_ledger_programs_structurally_valid": len(program_rows) == 4 and all(valid_program(row["choice"]["program"]) and prior131.audit_accepted(row["choice"]["audit"]) for row in program_rows),
        "03_public_observed_contact_preserved": len(program_rows) == 4 and all(row["choice"]["public_result"]["passed"] for row in program_rows),
        "04_hidden_observed_contact_preserved": len(program_rows) == 4 and all(row["choice"]["hidden_result"]["passed"] for row in program_rows),
        "05_blocked_contact_excluded": bool(all_results) and all(result["properties"].get("blocked_excluded") for result in all_results),
        "06_revoked_identity_corrected": bool(all_results) and all(result["properties"].get("revocation_exact") for result in all_results),
        "07_sealed_order_preserved": bool(all_results) and all(result["properties"].get("order_exact") for result in all_results),
        "08_two_independent_replays_exact": len(replay_rows) == 2 and all(row["choice"]["passed"] for row in replay_rows),
    }
    audits = [row["choice"]["audit"] for row in contact_rows] + [row["choice"]["audit"] for row in program_rows] + [row["choice"]["audit"] for row in replay_rows]
    checks = {"eight_of_eight_decision_ready_checkpoints": len(checkpoints) == SELECTED_MEASUREMENT and all(checkpoints.values()), "ten_fresh_actors_accepted": len(audits) == 10 and all(prior131.audit_accepted(audit) for audit in audits), "four_programs_generalize": programs_pass, "five_negative_controls_fail_world_bank": len(negative_results) == 5 and all(not result["passed"] for result in negative_results.values()), "replay_ledgers_identical": len(replay_rows) == 2 and replay_rows[0]["choice"]["ledger"] == replay_rows[1]["choice"]["ledger"], "parent_stake_selector_exact": parent["artifact_digest"] == PARENT_DIGEST and stake["stake_id"] == STAKE_ID and selector["selector_binding_digest"] == SELECTOR_DIGEST, "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18}
    checks["passed"] = all(checks.values())
    final = parent
    if checks["passed"]:
        binding = program_rows[0]["choice"]["binding"]
        child = copy.deepcopy(parent); child.pop("artifact_digest", None)
        child["contact_correction_ledger_capabilities"] = [*child.get("contact_correction_ledger_capabilities", []), binding]
        receipt_body = {"authority": "ot-0206-independent-selected-ledger-consequence", "source_subject_digest": parent["artifact_digest"], "stake_id": STAKE_ID, "selector_binding_digest": SELECTOR_DIGEST, "ledger_binding_digest": binding["binding_digest"], "contact_suite_digests": [p82.digest(suite) for suite in suites], "replay_receipt_digests": [row["choice"]["receipt"]["receipt_digest"] for row in replay_rows], "checkpoints": checkpoints, "criterion_status": "satisfied"}
        receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
        child["contact_correction_ledger_receipts"] = [*child.get("contact_correction_ledger_receipts", []), receipt]
        consequence_body = {"authority": "ot-0206-selector-selected-pursuit-consequence", "selector_binding_digest": SELECTOR_DIGEST, "selected_stake_id": STAKE_ID, "selected_measurement": SELECTED_MEASUREMENT, "observed_checkpoint_count": sum(checkpoints.values()), "pursuit_disposition": "completed", "ledger_receipt_digest": receipt["receipt_digest"], "interpretation": "selected pursuit completed; comparative selector utility remains unresolved"}
        child["selector_consequence_receipts"] = [*child.get("selector_consequence_receipts", []), {**consequence_body, "receipt_digest": p82.digest(consequence_body)}]
        completion_body = {"authority": "ot-0206-selected-pursuit-completion", "stake_id": STAKE_ID, "ledger_receipt_digest": receipt["receipt_digest"], "criterion_status": "satisfied", "independent_contact_count": len(suites), "replay_actor_count": len(replay_rows)}
        child["developmental_completion_receipts"] = [*child.get("developmental_completion_receipts", []), {**completion_body, "receipt_digest": p82.digest(completion_body)}]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Assimilate the completed selected pursuit and consequence-test the retained pursuit selector."}
        child["unresolved"] = "Does decision-ready-signal predict better continuation under independent comparative or contradictory consequence?"
        candidate = p82.seal(child)
        if runtime.identity_conforms(candidate):
            final = candidate
        else:
            checks["successor_identity_conforms"] = False; checks["passed"] = False
    checks.setdefault("successor_identity_conforms", checks["passed"] and final is not parent)
    if not checks["successor_identity_conforms"]:
        checks["passed"] = False; final = parent
    result = {"authority": "ot-0206-selected-ledger-world-contact", "source_subject_digest": parent["artifact_digest"], "selector_binding_digest": SELECTOR_DIGEST, "selected_stake_id": STAKE_ID, "selected_measurement": SELECTED_MEASUREMENT, "contact_rows": [{"index": row["index"], "choice": p82.compact(row["choice"])} for row in contact_rows], "program_rows": [{"index": row["index"], "choice": p82.compact(row["choice"])} for row in program_rows], "replay_rows": [{"index": row["index"], "choice": p82.compact(row["choice"])} for row in replay_rows], "negative_control_results": negative_results, "checkpoints": checkpoints, "checks": checks, "route_floor": route_floor, "identity_floor": identity, "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": len(audits)}
    result["receipt_digest"] = p82.digest(result); authority_base.guide_base.write_json(run / "aggregate.json", result); authority_base.guide_base.write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
