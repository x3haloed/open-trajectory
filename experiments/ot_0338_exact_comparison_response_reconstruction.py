from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0337_nondiscriminating_consequence_expansion.py"
BASE_SHA256 = "5a85227e2127c27f932b5743b6ca08c20790e2f298bc6f7fe12ae2bb96e9c8b7"
OT337_PREFLIGHT = "f173526ef004f3a02d09421d2869a47dc41044efbf2e0ceb26c5b401a59242da"
AUTHORITY = "ot-0338-exact-comparison-response-reconstruction"


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"frozen OT-0337 source changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0338_frozen_ot0337", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()
write_json = base.write_json


def valid_receipt_set(parent, receipts, p82):
    request = parent["active_comparative_world_contact_request"]
    if [row.get("world_id") for row in receipts] != request["world_ids"]:
        return False
    for receipt in receipts:
        body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
        if not (
            receipt.get("valid") is True
            and receipt.get("selection_precedes_outcome") is True
            and receipt.get("world_authority") is True
            and receipt.get("scoring_authority") is True
            and receipt.get("outcome_authority") is True
            and receipt.get("actor_authority") is False
            and receipt.get("comparison_request_binding_digest") == request["binding_digest"]
            and receipt.get("source_subject_digest") == parent["artifact_digest"]
            and receipt.get("receipt_digest") == p82.digest(body)
        ):
            return False
    return True


def retained_actor(store, parent, result334, receipts):
    run = store / "runs/OT-0337"
    root = run / "runtime/comparative-consequence-responder"
    seed = run / "responder/seed"
    workspace = root / "actor-workspace"
    output = json.loads((root / "output.json").read_text())
    decision = json.loads((workspace / "decision.json").read_text())
    audit = json.loads((root / "actor-audit.json").read_text())
    events = (root / "events.jsonl").read_text()
    stderr = (root / "stderr.txt").read_text()
    immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
    immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    checker = subprocess.run(["python3", "check_decision.py"], cwd=workspace, capture_output=True)
    request = parent["active_comparative_world_contact_request"]
    compared = request["world_ids"]
    remaining = [row["world_id"] for row in result334["selection_history"][-1]["rows"] if row["world_id"] not in compared]
    semantic = immutable_ok and checker.returncode == 0 and base.decision_semantic(decision, compared, remaining, receipts)
    output_ok = output == {"action": "submit-comparative-consequence-response", "files_changed": ["decision.json"]}
    g11 = base.p35.base.base.g11
    row = g11.retained_row(audit, events, stderr)
    certificate = {"authority": g11.AUTHORITY, "event_trace_sha256": hashlib.sha256(events.encode()).hexdigest(), "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(), "incumbent_accepted": g11.incumbent(row), "challenger_accepted": g11.g11(row)}
    accepted = bool(semantic and output_ok and certificate["challenger_accepted"])
    return {"accepted": accepted, "actor_resampled": False, "decision": decision, "output": output, "audit": audit, "g11": certificate, "immutable_ok": immutable_ok, "semantic": semantic, "turn_completed": '"type":"turn.completed"' in events}


def preflight(root, store, p82, runtime, parent, result336, result334):
    root.mkdir(parents=True, exist_ok=True)
    inherited, receipts = base.preflight(root / "inherited", p82, runtime, parent, result336, result334)
    actor = retained_actor(store, parent, result334, receipts)
    actor["accepted"] = bool(actor["accepted"] and valid_receipt_set(parent, receipts, p82))
    counterfeit = copy.deepcopy(actor["decision"])
    counterfeit["world_ids"] = parent["active_comparative_world_contact_request"]["world_ids"]
    compared = parent["active_comparative_world_contact_request"]["world_ids"]
    remaining = inherited["remaining_world_ids"]
    bad_receipts = copy.deepcopy(receipts)
    bad_receipts[0]["outcome_authority"] = False
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "ot0337_preflight_exact": inherited["receipt_digest"] == OT337_PREFLIGHT and inherited["checks"]["passed"],
        "observer_helper_failure_localized": not hasattr(base.p35.base, "certify_g11") and hasattr(base.p35.base.base, "certify_g11"),
        "exact_actor_not_resampled": actor["accepted"] and actor["actor_resampled"] is False and actor["turn_completed"],
        "exact_remaining_world_decision": actor["decision"]["action"] == "extend-comparative-consequence" and actor["decision"]["world_ids"] == remaining,
        "counterfeit_decision_rejects": not base.decision_semantic(counterfeit, compared, remaining, receipts),
        "exact_receipt_set_authorized": valid_receipt_set(parent, receipts, p82),
        "counterfeit_outcome_authority_rejects_receipt_set": not valid_receipt_set(parent, bad_receipts, p82),
        "g11_exact_accepts": actor["g11"]["challenger_accepted"],
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "source_ot0336_receipt_digest": result336["receipt_digest"], "retained_actor": actor, "world_consequence_receipts": receipts, "checks": checks}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", receipt)
    return receipt, actor, receipts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, _, p82, runtime, core, base130, parent, result336, result334 = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0338").resolve()
    with tempfile.TemporaryDirectory() as directory:
        frozen, actor, receipts = preflight(Path(directory), store, p82, runtime, parent, result336, result334)
    if args.preflight_only:
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0338 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", frozen)
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0338 preflight failed")
    final, binding = base.compile_extension(parent, actor, receipts, p82)
    checks = {
        "preflight_passed": frozen["checks"]["passed"],
        "exact_actor_reconstructed_without_resample": actor["accepted"] and actor["actor_resampled"] is False,
        "exact_g11_certificate": actor["g11"]["challenger_accepted"],
        "tie_does_not_trigger_revision": actor["decision"]["action"] == "extend-comparative-consequence",
        "stake_byte_exact": final["active_world_seeking_stake"] == parent["active_world_seeking_stake"],
        "open_extension_successor": final["active_comparative_world_contact_extension"] == binding and runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "source_ot0336_receipt_digest": result336["receipt_digest"], "source_ot0337_preflight_receipt_digest": OT337_PREFLIGHT, "retained_actor": actor, "world_consequence_receipts": receipts, "extension_binding": binding, "checks": checks, "operational_transition_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 0}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    write_json(run / "open-subject-awaiting-extended-comparison.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
