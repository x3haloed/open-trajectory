from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0211_supported_schema_code_pursuit.py"
BASE_SHA256 = "5bac277aa823f107adbc435c54e2e3b1344c74f3c92f77e67c4f68a21ffbf390"
REJECTED_PATH = ROOT / "ot_0212_contact_warranted_retention.py"
REJECTED_SHA256 = "11e9a74f5876e29c0ad86cb94aa9a89f522e69fc5b6c743f4bbafdb09af8beae"
PARENT_DIGEST = "9cb26c73df87567ca8abac005b6fa6a8fa944ad57c0db2156a67a0a2901df7a7"
POLICY_SOURCE_DIGEST = "e4679353e2ac6138c091f01a9179ca161e4a324e6143fa5d5e63914fab703497"
CORRECTED_SELECTOR_DIGEST = "ea5d27fe65d8dfa49609c4219a04aeb558c504422088d942dea4eaed48f7308f"
LEDGER_DIGEST = "6565a30d8bc35b3f86ccffcc4698f8451204f50a7d471a969217e799f597aa80"
LEDGER_COMPLETION_DIGEST = "fa64fd10f7c4457dacf129a790c8693bc75ad8f8d23ec93a9d540efc40bd2407"
INHERITED_OPENING = "Carry forward a measured follow-up that tests the consequence-grounded selector on newly observed deadline, value, penalty, speed, and reliability combinations, then revise the threshold or score only when fresh public regret justifies it."
WORLD_SCHEMA = REPO / "spec/ot-0213-world-author.schema.json"
ASSIMILATOR_SCHEMA = REPO / "spec/ot-0213-assimilator.schema.json"
TOKEN = re.compile(r"[a-z][a-z0-9-]{2,47}")


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0211 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0213_frozen_ot0211", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base211 = load_base()
world86 = base211.world86
authority_base = base211.authority_base

RELIABILITY_SOURCE = '''def choose_worker(job, workers):
    """Prefer the worker with the strongest observed reliability."""
    return max(workers, key=lambda worker: (worker["reliability"], worker["id"]))["id"]
'''

CURRENT_SOURCE = '''def choose_worker(job, workers):
    """Choose the worker with the highest visible expected net score."""
    def score(worker):
        completion = job["cost"] / worker["speed"]
        lateness = max(0.0, completion - job["deadline"])
        return job["value"] * worker["reliability"] - job["late_penalty"] * lateness

    return max(workers, key=lambda worker: (score(worker), worker["speed"], worker["id"]))["id"]
'''

HYBRID_SOURCE = '''def choose_worker(job, workers):
    """Use reliability only for especially tight deadlines."""
    if job["deadline"] < 3.5:
        return max(workers, key=lambda worker: (worker["reliability"], worker["id"]))["id"]
    return max(workers, key=lambda worker: (worker["speed"], worker["id"]))["id"]
'''


def write_json(path: Path, value: Any) -> None:
    authority_base.guide_base.write_json(path, value)


def number(value: Any, low: float, high: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high


def expected_score(case: dict[str, Any], worker: dict[str, Any]) -> float:
    job = case["job"]
    lateness = max(0.0, job["cost"] / worker["speed"] - job["deadline"])
    return job["value"] * worker["reliability"] - job["late_penalty"] * lateness


def select(case: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode == "expected":
        key = lambda worker: (expected_score(case, worker), worker["speed"], worker["id"])
    elif mode == "speed":
        key = lambda worker: (worker["speed"], worker["id"])
    else:
        key = lambda worker: (worker["reliability"], worker["id"])
    return max(case["workers"], key=key)


def valid_case(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"case_id", "job", "workers"}:
        return False
    if not isinstance(value.get("case_id"), str) or not TOKEN.fullmatch(value["case_id"]) or value["case_id"].startswith("replace-"):
        return False
    job = value.get("job")
    if not isinstance(job, dict) or set(job) != {"cost", "deadline", "value", "late_penalty"}:
        return False
    if not (number(job["cost"], 8, 120) and number(job["deadline"], 1, 20) and number(job["value"], 20, 300) and number(job["late_penalty"], 5, 120)):
        return False
    workers = value.get("workers")
    if not isinstance(workers, list) or len(workers) not in {2, 3}:
        return False
    for worker in workers:
        if not isinstance(worker, dict) or set(worker) != {"id", "speed", "reliability"}:
            return False
        if not isinstance(worker.get("id"), str) or not TOKEN.fullmatch(worker["id"]):
            return False
        if not number(worker["speed"], 1, 30) or not number(worker["reliability"], 0.2, 1.0):
            return False
    return len({worker["id"] for worker in workers}) == len(workers)


def control_stats(cases: list[dict[str, Any]], mode: str) -> tuple[int, float]:
    misses = 0
    gap = 0.0
    for case in cases:
        oracle = select(case, "expected")
        control = select(case, mode)
        misses += control["id"] != oracle["id"]
        gap += expected_score(case, oracle) - expected_score(case, control)
    return misses, gap


def valid_suite(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"suite_id", "cases"}:
        return False
    if not isinstance(value.get("suite_id"), str) or not TOKEN.fullmatch(value["suite_id"]) or value["suite_id"].startswith("replace-"):
        return False
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 6 or not all(valid_case(case) for case in cases):
        return False
    if len({case["case_id"] for case in cases}) != 6 or {len(case["workers"]) for case in cases} != {2, 3}:
        return False
    if any(len({case["job"][field] for case in cases}) < 4 for field in ("cost", "deadline", "value", "late_penalty")):
        return False
    speed_misses, speed_gap = control_stats(cases, "speed")
    reliability_misses, reliability_gap = control_stats(cases, "reliability")
    return speed_misses >= 2 and reliability_misses >= 2 and speed_gap >= 25.0 and reliability_gap >= 25.0


def valid_world(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == {"world_id", "suites"}
        and isinstance(value.get("world_id"), str)
        and TOKEN.fullmatch(value["world_id"])
        and not value["world_id"].startswith("replace-")
        and isinstance(value.get("suites"), list)
        and len(value["suites"]) == 2
        and all(valid_suite(suite) for suite in value["suites"])
        and len({suite["suite_id"] for suite in value["suites"]}) == 2
    )


def world_template() -> dict[str, Any]:
    return {"world_id": "replace-world", "suites": []}


def world_checker_source() -> str:
    return '''import json,re\nfrom pathlib import Path\nT=re.compile(r"[a-z][a-z0-9-]{2,47}")\ndef num(v,a,b): return isinstance(v,(int,float)) and not isinstance(v,bool) and a<=v<=b\ndef score(c,w):\n j=c["job"]; return j["value"]*w["reliability"]-j["late_penalty"]*max(0.0,j["cost"]/w["speed"]-j["deadline"])\ndef pick(c,m):\n if m=="expected": k=lambda w:(score(c,w),w["speed"],w["id"])\n elif m=="speed": k=lambda w:(w["speed"],w["id"])\n else: k=lambda w:(w["reliability"],w["id"])\n return max(c["workers"],key=k)\ndef case(c):\n if not isinstance(c,dict) or set(c)!={"case_id","job","workers"} or not isinstance(c.get("case_id"),str) or not T.fullmatch(c["case_id"]): return False\n j=c.get("job"); ws=c.get("workers"); return isinstance(j,dict) and set(j)=={"cost","deadline","value","late_penalty"} and num(j["cost"],8,120) and num(j["deadline"],1,20) and num(j["value"],20,300) and num(j["late_penalty"],5,120) and isinstance(ws,list) and len(ws) in {2,3} and all(isinstance(w,dict) and set(w)=={"id","speed","reliability"} and isinstance(w["id"],str) and T.fullmatch(w["id"]) and num(w["speed"],1,30) and num(w["reliability"],.2,1) for w in ws) and len({w["id"] for w in ws})==len(ws)\ndef stats(cs,m):\n rows=[(pick(c,"expected"),pick(c,m),c) for c in cs]; return sum(a["id"]!=b["id"] for a,b,c in rows),sum(score(c,a)-score(c,b) for a,b,c in rows)\ndef suite(s):\n if not isinstance(s,dict) or set(s)!={"suite_id","cases"} or not isinstance(s.get("suite_id"),str) or not T.fullmatch(s["suite_id"]) or s["suite_id"].startswith("replace-"): return False\n cs=s.get("cases");\n if not isinstance(cs,list) or len(cs)!=6 or not all(case(c) for c in cs) or len({c["case_id"] for c in cs})!=6 or {len(c["workers"]) for c in cs}!={2,3} or any(len({c["job"][f] for c in cs})<4 for f in ("cost","deadline","value","late_penalty")): return False\n sm,sg=stats(cs,"speed"); rm,rg=stats(cs,"reliability"); return sm>=2 and rm>=2 and sg>=25 and rg>=25\nw=json.loads(Path("world-contact.json").read_text()); ss=w.get("suites") if isinstance(w,dict) else None; ok=isinstance(w,dict) and set(w)=={"world_id","suites"} and isinstance(w.get("world_id"),str) and T.fullmatch(w["world_id"]) and not w["world_id"].startswith("replace-") and isinstance(ss,list) and len(ss)==2 and all(suite(s) for s in ss) and len({s["suite_id"] for s in ss})==2\nprint(json.dumps({"passed":bool(ok)},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''


def world_seed(root: Path, index: int) -> Path:
    seed = root / "world-seed"
    seed.mkdir()
    write_json(seed / "world-contact.json", world_template())
    write_json(seed / "world-contract.json", {"suite_count": 2, "cases_per_suite": 6, "public_suite": 1, "hidden_suite": 2, "minimum_control_misses_per_suite": 2, "minimum_control_score_gap_per_suite": 25.0})
    write_json(seed / "mutation-envelope.json", {"editable": ["world-contact.json"], "immutable": ["world-contract.json", "mutation-envelope.json", "check_world.py", "README.md"]})
    (seed / "check_world.py").write_text(world_checker_source())
    (seed / "README.md").write_text("Author two independent six-case dispatch contact suites in world-contact.json. The visible expected-score semantics are value times reliability minus lateness penalty; ties use speed then id. Vary every job field and include two- and three-worker cases. Each suite must make speed-only and reliability-only miss at least two oracles and lose at least 25 total score. Suite one becomes public contact and suite two stays hidden from later assimilation actors. Run python3 check_world.py and inspect the exact diff.\n")
    return seed


def run_world(context, prior131, root: Path, index: int) -> dict[str, Any]:
    label = f"world-{index:02d}"
    seed = world_seed(root, index)
    output, base_audit, workspace, _ = context.run_actor(label, seed, WORLD_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        value = json.loads((workspace / "world-contact.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        value, immutable_ok = None, False
    valid = bool(valid_world(value) and immutable_ok and output and output.get("action") == "author-independent-dispatch-contact")
    audit = context.audit_actor(label, output, base_audit, valid, ["world-contact.json"])
    accepted = valid and prior131.audit_accepted(audit)
    local = copy.deepcopy(value) if accepted else None
    if local:
        local_world_id = local["world_id"]
        local["world_id"] = f"sealed-dispatch-world-{index:02d}"
        for position, suite in enumerate(local["suites"], 1):
            suite["local_suite_id"] = suite.pop("suite_id")
            suite["suite_id"] = f"sealed-dispatch-world-{index:02d}-suite-{position}"
            for case_position, case in enumerate(suite["cases"], 1):
                case["local_case_id"] = case.pop("case_id")
                case["case_id"] = f"sealed-dispatch-world-{index:02d}-suite-{position}-case-{case_position}"
    else:
        local_world_id = None
    return {"output": output, "audit": audit, "accepted": accepted, "world": local, "local_world_id": local_world_id}


def flatten(worlds: list[dict[str, Any]], position: int) -> list[dict[str, Any]]:
    return [case for world in worlds for case in world["suites"][position]["cases"]]


def contact_receipt(p82, source: str, cases: list[dict[str, Any]], evidence: Path, label: str) -> dict[str, Any]:
    current = world86.evaluate_source(p82, source, cases, evidence, f"{label}-retained")
    speed = world86.evaluate_source(p82, world86.POLICY_SOURCE, cases, evidence, f"{label}-speed")
    reliability = world86.evaluate_source(p82, RELIABILITY_SOURCE, cases, evidence, f"{label}-reliability")
    def metrics(receipt):
        hits = sum(row.get("selected_worker") == row.get("oracle_worker") for row in receipt["rows"])
        return {"receipt_digest": receipt["receipt_digest"], "valid": receipt["valid"] and receipt["floor"]["passed"], "oracle_hits": hits, "total": receipt["total"], "oracle_total": receipt["oracle_total"]}
    a, b, c = metrics(current), metrics(speed), metrics(reliability)
    body = {"authority": "ot-0213-independent-dispatch-contact", "case_count": len(cases), "cases_digest": p82.digest(cases), "retained": a, "speed_only": b, "reliability_only": c, "speed_gap": a["total"] - b["total"], "reliability_gap": a["total"] - c["total"]}
    return {**body, "receipt_digest": p82.digest(body)}


DECISION_KEYS = {"subject_action", "policy_disposition", "selector_disposition", "policy_source_digest", "selector_binding_digest", "rationale", "next_pursuit"}


def decision_template() -> dict[str, Any]:
    return {"subject_action": "revise", "policy_disposition": "revise", "selector_disposition": "revise", "policy_source_digest": "replace-policy-digest", "selector_binding_digest": "replace-selector-digest", "rationale": "replace-with-contact-grounded-rationale", "next_pursuit": "replace-with-next-pursuit"}


EXTENSION_KEY = re.compile(r"[a-z][a-z0-9_]{2,63}")


def valid_core(value: Any) -> bool:
    dispositions = {"retain", "revise", "surrender"}
    return bool(isinstance(value, dict) and DECISION_KEYS.issubset(value) and value.get("subject_action") in dispositions and value.get("policy_disposition") in dispositions and value.get("selector_disposition") in dispositions and all(isinstance(value.get(key), str) and value[key].strip() and not value[key].startswith("replace-") for key in ("policy_source_digest", "selector_binding_digest", "rationale", "next_pursuit")))


def safe_extension(value: Any, depth: int = 0) -> bool:
    if depth > 4:
        return False
    if value is None or isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, str):
        return len(value) <= 2000
    if isinstance(value, list):
        return len(value) <= 16 and all(safe_extension(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return len(value) <= 16 and all(isinstance(key, str) and EXTENSION_KEY.fullmatch(key) and safe_extension(item, depth + 1) for key, item in value.items())
    return False


def incumbent_valid(value: Any) -> bool:
    return valid_core(value) and set(value) == DECISION_KEYS


def valid_decision(value: Any) -> bool:
    if not valid_core(value):
        return False
    extensions = {key: item for key, item in value.items() if key not in DECISION_KEYS}
    return len(extensions) <= 8 and all(EXTENSION_KEY.fullmatch(key) and safe_extension(item) for key, item in extensions.items()) and len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()) <= 16384


def split_decision(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    return ({key: copy.deepcopy(value[key]) for key in sorted(DECISION_KEYS)}, {key: copy.deepcopy(item) for key, item in value.items() if key not in DECISION_KEYS})


def exact_retention_core(value: dict[str, Any]) -> bool:
    return bool(value["subject_action"] == value["policy_disposition"] == value["selector_disposition"] == "retain" and value["policy_source_digest"] == POLICY_SOURCE_DIGEST and value["selector_binding_digest"] == CORRECTED_SELECTOR_DIGEST)


def evaluation_transition_fixture(result212: dict[str, Any]) -> dict[str, Any]:
    base = decision_template(); base.update({"subject_action": "retain", "policy_disposition": "retain", "selector_disposition": "retain", "policy_source_digest": POLICY_SOURCE_DIGEST, "selector_binding_digest": CORRECTED_SELECTOR_DIGEST, "rationale": "Held-out exact core retention.", "next_pursuit": "held-out-next-contact"})
    novel = {**base, "causal_thread": {"contact": "held-out-public", "reason": "preserve-correct-capability"}}
    missing = {key: item for key, item in base.items() if key != "rationale"}
    too_many = {**base, **{f"extension_{index}": index for index in range(9)}}
    too_deep = {**base, "causal_thread": {"a": {"b": {"c": {"d": {"e": "too-deep"}}}}}}
    too_broad = {**base, "causal_thread": list(range(17))}
    bad_key = {**base, "Bad Key": "invalid"}
    oversized = {**base, "causal_thread": "x" * 17000}
    construction = [row["decision"] for row in result212["assimilation_rows"]]
    checks = {"construction_incumbent_1_of_3": sum(incumbent_valid(row) for row in construction) == 1, "construction_challenger_3_of_3": sum(valid_decision(row) for row in construction) == 3, "exact_core_no_regression": incumbent_valid(base) and valid_decision(base) and exact_retention_core(base), "heldout_extension_improves": not incumbent_valid(novel) and valid_decision(novel) and exact_retention_core(novel), "missing_core_rejected_both": not incumbent_valid(missing) and not valid_decision(missing), "too_many_rejected": not valid_decision(too_many), "too_deep_rejected": not valid_decision(too_deep), "too_broad_rejected": not valid_decision(too_broad), "invalid_key_rejected": not valid_decision(bad_key), "oversized_rejected": not valid_decision(oversized)}
    checks["passed"] = all(checks.values())
    return {"from_regime": "G3-exact-key-decision", "to_regime": "G4-core-plus-bounded-nonauthoritative-extension", "construction_source": "OT-0212 assimilation outputs", "heldout_anchor": "novel causal_thread plus malformed boundaries", "checks": checks}


def assimilator_seed(root: Path, parent: dict[str, Any], public_cases: list[dict[str, Any]], public_receipt: dict[str, Any], index: int) -> Path:
    seed = root / "assimilation-seed"
    seed.mkdir()
    write_json(seed / "subject-position.json", authority_base.reuse.worlds.base.active_position(parent))
    write_json(seed / "current-capabilities.json", {"opening": parent["continuation"]["next_opening"], "installed_policy": parent["executed_pursuit_capabilities"][-1], "corrected_selector": parent["pursuit_selector_capabilities"][-1]})
    write_json(seed / "public-world-contact.json", {"cases": public_cases, "receipt": public_receipt})
    write_json(seed / "continuation-decision.json", decision_template())
    write_json(seed / "mutation-envelope.json", {"editable": ["continuation-decision.json"], "immutable": ["subject-position.json", "current-capabilities.json", "public-world-contact.json", "mutation-envelope.json", "README.md"]})
    (seed / "README.md").write_text("Continue the exact open subject through the newly observed public dispatch contact. Decide independently whether to retain, revise, or surrender the installed policy and corrected pursuit selector. Retention is a substantive action when contact warrants it; revision is allowed but must be justified by actual regret. Preserve the seven existing core fields. You may add up to eight bounded JSON fields when they help carry identity, contact, or other continuity forward; they will be retained as subject-authored non-authoritative content and cannot affect scoring or admission. Record exact retained identities when retaining, and author the next pursuit that should carry the music beyond this encounter. Hidden contact is sealed. Edit only continuation-decision.json and inspect the exact diff.\n")
    return seed


def run_assimilator(context, prior131, p82, root: Path, parent: dict[str, Any], public_cases: list[dict[str, Any]], public_receipt: dict[str, Any], index: int) -> dict[str, Any]:
    label = f"assimilator-{index:02d}"
    seed = assimilator_seed(root, parent, public_cases, public_receipt, index)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATOR_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        decision = json.loads((workspace / "continuation-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / path).read_bytes() == (seed / path).read_bytes() for path in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        decision, immutable_ok = None, False
    valid = bool(valid_decision(decision) and immutable_ok and output and output.get("action") == "assimilate-independent-contact")
    audit = context.audit_actor(label, output, base_audit, valid, ["continuation-decision.json"])
    binding = None
    if valid and prior131.audit_accepted(audit):
        core, extensions = split_decision(decision)
        extension_body = {"authority": "subject-authored-non-authoritative-continuity-content", "content": extensions, "content_digest": p82.digest(extensions)}
        body = {"authority": "ot-0213-pre-hidden-continuation-decision", "source_subject_digest": parent["artifact_digest"], "public_contact_receipt_digest": public_receipt["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "decision_core": core, "subject_authored_extensions": extension_body, "raw_decision_digest": p82.digest(decision)}
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-decision.json", binding)
    return {"output": output, "audit": audit, "decision": decision, "binding": binding, "accepted": binding is not None, "extension_count": len(binding["subject_authored_extensions"]["content"]) if binding else 0}


def helper_repair_fixture(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    (root / "proposals").mkdir()
    for index, source in enumerate((RELIABILITY_SOURCE, CURRENT_SOURCE, HYBRID_SOURCE), 1):
        (root / f"proposals/policy-{index}.py").write_text(source)
    write_json(root / "frontier.json", {"next_pursuit": "continue-after-repaired-helper"})
    broken = base211.checker_source()
    lines = broken.splitlines()
    lines[3] = f"BASELINE={world86.POLICY_SOURCE!r}"
    repaired = "\n".join(lines) + "\n"
    (root / "broken-check.py").write_text(broken)
    (root / "repaired-check.py").write_text(repaired)
    old = subprocess.run(["python3", "broken-check.py"], cwd=root, capture_output=True, text=True)
    new = subprocess.run(["python3", "repaired-check.py"], cwd=root, capture_output=True, text=True)
    try:
        payload = json.loads(new.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {"broken_reproduced": old.returncode != 0, "repaired_executed": new.returncode == 0 and payload.get("passed") is True, "broken_stderr_digest": hashlib.sha256(old.stderr.encode()).hexdigest(), "repaired_stdout_digest": hashlib.sha256(new.stdout.encode()).hexdigest()}


def main() -> int:
    lineage = authority_base.guide_base.load_base()
    selector_base, base, prior131, base130 = lineage.selector_base, lineage.base, lineage.prior131, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve(); store = (args.store or repo / ".evidence").resolve(); run = (args.evidence_root or store / "runs/OT-0213").resolve()
    prior92 = base.mechanism.load_prior(); _, _, _, p82 = base.mechanism.prior_chain(prior92); runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0211", "open-subject-after-code-pursuit.json")
    result211 = selector_base.load_artifact(p82, repo, store, "OT-0211", "subject-authored-code-pursuit-aggregate.json")
    result212 = selector_base.load_artifact(p82, repo, store, "OT-0212", "rejected-contact-warranted-retention.json")
    expression = parent["actor_authored_contact_mechanisms"][-1]["expression"]
    route_floor = base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"], expression)
    operation = authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"])
    identity = authority_base.reuse.extension_base.evaluate(operation, authority_base.reuse.accumulated_floor())
    fixture_root = run.parent / "OT-0213-preflight"
    if fixture_root.exists():
        import shutil
        shutil.rmtree(fixture_root)
    helper = helper_repair_fixture(fixture_root / "helper")
    schema_text = WORLD_SCHEMA.read_text() + ASSIMILATOR_SCHEMA.read_text()
    transition = evaluation_transition_fixture(result212)
    checks = {"parent_exact_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent), "ot0211_exact_promotion": result211["observer_disposition"] == "promoted" and result211["final_subject_digest"] == PARENT_DIGEST, "ot0212_exact_rejection": result212["observer_disposition"] == "rejected" and result212["final_subject_digest"] == PARENT_DIGEST, "rejected_harness_exact": hashlib.sha256(REJECTED_PATH.read_bytes()).hexdigest() == REJECTED_SHA256, "actor_authored_opening_exact": parent["continuation"]["next_opening"] == INHERITED_OPENING, "installed_policy_exact": parent["executed_pursuit_capabilities"][-1]["source_digest"] == POLICY_SOURCE_DIGEST, "corrected_selector_exact": parent["pursuit_selector_capabilities"][-1]["selector_binding_digest"] == CORRECTED_SELECTOR_DIGEST, "ledger_exact": parent["contact_correction_ledger_capabilities"][-1]["binding_digest"] == LEDGER_DIGEST and parent["developmental_completion_receipts"][-1]["receipt_digest"] == LEDGER_COMPLETION_DIGEST, "helper_defect_reproduced": helper["broken_reproduced"], "helper_repair_executes": helper["repaired_executed"], "evaluation_transition_anchor_passed": transition["checks"]["passed"], "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "schemas_supported_shape": WORLD_SCHEMA.is_file() and ASSIMILATOR_SCHEMA.is_file() and "uniqueItems" not in schema_text and all(prop.get("type") == "string" for path in (WORLD_SCHEMA, ASSIMILATOR_SCHEMA) for prop in json.loads(path.read_text())["properties"].values() if "const" in prop)}
    checks["passed"] = all(checks.values())
    fixtures = {"authority": "ot-0213-preflight", "source_subject_digest": parent["artifact_digest"], "helper_repair": helper, "evaluation_transition": transition, "checks": checks}
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True)); return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0213 evidence")
    run.mkdir(parents=True); write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]: raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    world_rows = []
    for index in range(1, 5):
        root = run / f"world-{index:02d}-authoring"; root.mkdir(); world_rows.append(run_world(context, prior131, root, index))
    worlds_ok = len(world_rows) == 4 and all(row["accepted"] for row in world_rows)
    worlds = [row["world"] for row in world_rows] if worlds_ok else []
    public_cases = flatten(worlds, 0) if worlds_ok else []
    hidden_cases = flatten(worlds, 1) if worlds_ok else []
    source = parent["executed_pursuit_capabilities"][-1]["source"]
    public = contact_receipt(p82, source, public_cases, run / "public-evaluation", "public") if worlds_ok else None
    assimilators = []
    if public:
        for index in range(1, 4):
            root = run / f"assimilator-{index:02d}-authoring"; root.mkdir(); assimilators.append(run_assimilator(context, prior131, p82, root, parent, public_cases, public, index))
    decisions_bound = len(assimilators) == 3 and all(row["accepted"] for row in assimilators)
    hidden = contact_receipt(p82, source, hidden_cases, run / "hidden-evaluation", "hidden") if decisions_bound else None
    exact_retention = decisions_bound and all(exact_retention_core(row["decision"]) for row in assimilators)
    gates = {"g4_evaluation_transition_active": transition["checks"]["passed"], "seven_fresh_actors_accepted": worlds_ok and decisions_bound, "four_independent_discriminating_worlds": worlds_ok, "three_contact_warranted_exact_retentions": exact_retention, "lineage_actor_authored_extension": decisions_bound and assimilators[0]["extension_count"] >= 1, "public_retained_all_oracles": bool(public and public["retained"]["valid"] and public["retained"]["oracle_hits"] == public["case_count"]), "hidden_retained_all_oracles": bool(hidden and hidden["retained"]["valid"] and hidden["retained"]["oracle_hits"] == hidden["case_count"]), "public_controls_discriminate": bool(public and public["speed_only"]["oracle_hits"] <= public["case_count"] - 8 and public["reliability_only"]["oracle_hits"] <= public["case_count"] - 8 and public["speed_gap"] >= 100 and public["reliability_gap"] >= 100), "hidden_controls_discriminate": bool(hidden and hidden["speed_only"]["oracle_hits"] <= hidden["case_count"] - 8 and hidden["reliability_only"]["oracle_hits"] <= hidden["case_count"] - 8 and hidden["speed_gap"] >= 100 and hidden["reliability_gap"] >= 100), "ledger_selector_policy_exact": parent["contact_correction_ledger_capabilities"][-1]["binding_digest"] == LEDGER_DIGEST and parent["pursuit_selector_capabilities"][-1]["selector_binding_digest"] == CORRECTED_SELECTOR_DIGEST and parent["executed_pursuit_capabilities"][-1]["source_digest"] == POLICY_SOURCE_DIGEST, "installed_route_floor_16_of_16": route_floor["pass_count"] == 16, "identity_floor_18_of_18": identity["pass_count"] == 18, "actor_authored_new_reopening": decisions_bound and bool(assimilators[0]["decision"]["next_pursuit"].strip()) and assimilators[0]["decision"]["next_pursuit"] != INHERITED_OPENING}
    gates["passed"] = all(gates.values()); final = parent; promotion = None
    if gates["passed"]:
        child = copy.deepcopy(parent); child.pop("artifact_digest", None)
        body = {"authority": "ot-0213-contact-warranted-retention", "source_subject_digest": parent["artifact_digest"], "world_digests": [p82.digest(world) for world in worlds], "public_contact_receipt_digest": public["receipt_digest"], "decision_binding_digests": [row["binding"]["binding_digest"] for row in assimilators], "hidden_contact_receipt_digest": hidden["receipt_digest"], "retained_policy_source_digest": POLICY_SOURCE_DIGEST, "retained_selector_binding_digest": CORRECTED_SELECTOR_DIGEST, "lineage_reopening": assimilators[0]["decision"]["next_pursuit"]}
        promotion = {**body, "receipt_digest": p82.digest(body)}
        child["pursuit_retention_receipts"] = [*child.get("pursuit_retention_receipts", []), promotion]
        child["continuity_extensions"] = [*child.get("continuity_extensions", []), {**assimilators[0]["binding"]["subject_authored_extensions"], "source_decision_binding_digest": assimilators[0]["binding"]["binding_digest"]}]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": assimilators[0]["decision"]["next_pursuit"]}
        child["unresolved"] = "Can the subject carry its actor-authored reopening into a semantically changed world and correct itself without an observer choosing the pursuit?"
        candidate = p82.seal(child)
        if runtime.identity_conforms(candidate): final = candidate
        else: gates["successor_identity_conforms"] = False; gates["passed"] = False
    gates.setdefault("successor_identity_conforms", gates["passed"] and final is not parent)
    if not gates["successor_identity_conforms"]: gates["passed"] = False; final = parent
    result = {"authority": "ot-0213-contact-warranted-retention", "source_subject_digest": parent["artifact_digest"], "world_rows": [p82.compact(row) for row in world_rows], "public_contact": public, "assimilation_rows": [p82.compact(row) for row in assimilators], "hidden_contact": hidden, "promotion_receipt": promotion, "checks": gates, "route_floor": route_floor, "identity_floor": identity, "observer_disposition": "promoted" if gates["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": len(world_rows) + len(assimilators)}
    result["receipt_digest"] = p82.digest(result); write_json(run / "aggregate.json", result); write_json(run / "final-full-subject.json", final); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
