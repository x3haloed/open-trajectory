from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0339_subject_authored_world_consequence_policy.py"
BASE_SHA256 = "7eefb10969af89322522f4c08c5d44b4294be3a720bf9eda33fe87bff5a1aff3"
RAW_RECEIPT = "521ac8cabf93f3677c84a4487f4e90c1b96f5234cc2c2125851348d6c0740a8d"
CHILD_DIGEST = "32ac5ab0d95221ecfce05580d96448fe3e1af72ac9747bad11e496dd19d267c5"
AUTHORITY = "ot-0340-priority-causal-interpretation-correction"


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"frozen OT-0339 source changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0340_frozen_ot0339", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()
write_json = base.write_json


def operative_policy(policy):
    return {key: copy.deepcopy(policy[key]) for key in ("requirements", "priority_order", "directions", "on_tie")}


def behavioral_difference(raw):
    active = operative_policy(raw["active_actor"]["policy"])
    erased = operative_policy(raw["priority_erased_actor"]["policy"])
    return bool(active != erased or raw["active_expansion_anchor"] != raw["priority_erased_expansion_anchor"] or raw["active_decision"] != raw["priority_erased_decision"])


def setup(args):
    values = base.setup(args)
    repo, store, _, p82, runtime = values[:5]
    run = (args.evidence_root or store / "runs/OT-0340").resolve()
    selector = base.contact.base.base.base.base.base.b.authority_base.guide_base.load_base().selector_base
    load = lambda experiment, name: selector.load_artifact(p82, repo, store, experiment, name)
    raw = load("OT-0339", "subject-authored-world-consequence-policy-raw-aggregate.json")
    child = load("OT-0339", "open-subject-after-world-consequence-policy.json")
    parent = load("OT-0338", "open-subject-awaiting-extended-comparison.json")
    return repo, store, run, p82, runtime, raw, child, parent


def preflight(run, p82, runtime, raw, child, parent):
    active = operative_policy(raw["active_actor"]["policy"])
    erased = operative_policy(raw["priority_erased_actor"]["policy"])
    counterfeit = copy.deepcopy(raw)
    counterfeit["priority_erased_actor"]["policy"]["directions"]["viable_contact_count"] = "lower"
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_raw_and_child": raw["receipt_digest"] == RAW_RECEIPT and raw["final_subject_digest"] == child["artifact_digest"] == CHILD_DIGEST,
        "raw_operational_gates_pass": raw["operational_transition_passed"] and raw["checks"]["passed"] and raw["observer_disposition"] == "promoted",
        "raw_causal_flag_is_true": raw["priority_causal_claim_supported"] is True,
        "labels_differ_but_operative_policy_matches": raw["active_actor"]["policy"] != raw["priority_erased_actor"]["policy"] and active == erased,
        "anchors_and_live_decisions_match": raw["active_expansion_anchor"] == raw["priority_erased_expansion_anchor"] and raw["active_decision"] == raw["priority_erased_decision"],
        "corrected_causal_result_false": behavioral_difference(raw) is False,
        "counterfeit_operative_change_detected": behavioral_difference(counterfeit) is True,
        "operational_child_stake_exact": child["active_world_seeking_stake"] == parent["active_world_seeking_stake"],
        "operational_child_open_conformant": child["continuation"]["status"] == "open" and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_ot0339_receipt_digest": raw["receipt_digest"], "source_subject_digest": child["artifact_digest"], "active_operative_policy": active, "priority_erased_operative_policy": erased, "checks": checks}
    result = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "fixture-conformance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, raw, child, parent = setup(args)
    if args.preflight_only:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            frozen = preflight(Path(directory), p82, runtime, raw, child, parent)
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0340 evidence")
    run.mkdir(parents=True)
    frozen = preflight(run, p82, runtime, raw, child, parent)
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0340 preflight failed")
    body = {"authority": AUTHORITY, "source_ot0339_receipt_digest": raw["receipt_digest"], "source_subject_digest": child["artifact_digest"], "raw_priority_causal_claim_supported": raw["priority_causal_claim_supported"], "corrected_priority_causal_claim_supported": False, "operative_policy_equal": operative_policy(raw["active_actor"]["policy"]) == operative_policy(raw["priority_erased_actor"]["policy"]), "anchor_equal": raw["active_expansion_anchor"] == raw["priority_erased_expansion_anchor"], "live_decision_equal": raw["active_decision"] == raw["priority_erased_decision"], "operational_transition_preserved": True, "observer_disposition": "corrected-operational-only", "final_subject_digest": child["artifact_digest"], "fresh_actor_count": 0}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    write_json(run / "open-subject-after-causal-interpretation-correction.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
