from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0335_consequence_before_revision.py"
BASE_SHA256 = "57e954fe6f51da65bbc3ba1ed8e284df7160bae3951002b9803960bc5d2c8c6b"
SCHEMA = REPO / "spec/ot-0336-instability-response.schema.json"
AUTHORITY = "ot-0336-consequence-before-revision-recovery"


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"frozen OT-0335 source changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0336_frozen_ot0335", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()
write_json = base.write_json


def invalid_attempt(store):
    run = store / "runs/OT-0335"
    events_path = run / "runtime/unlabeled-instability-responder/events.jsonl"
    workspace = run / "runtime/unlabeled-instability-responder/actor-workspace"
    seed = run / "responder/seed"
    events_text = events_path.read_text()
    events = [json.loads(line) for line in events_text.splitlines()]
    unchanged = all((workspace / name).read_bytes() == path.read_bytes() for path in seed.iterdir() if path.is_file() for name in [path.name])
    return {
        "events_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
        "event_types": [row["type"] for row in events],
        "invalid_schema_named": "invalid_json_schema" in events_text and "Unexpected constant value" in events_text,
        "no_actor_output": not (run / "runtime/unlabeled-instability-responder/output.json").exists(),
        "workspace_unchanged": unchanged,
    }


def preflight(root, store, p82, runtime, parent, result):
    root.mkdir(parents=True, exist_ok=True)
    inherited = base.preflight(root / "inherited", p82, runtime, parent, result)
    invalid = invalid_attempt(store)
    schema = json.loads(SCHEMA.read_text())
    files = schema["properties"]["files_changed"]
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "inherited_preflight_exact": inherited["receipt_digest"] == "a5db694cc26f38d3bb699df6133aa93f77342f2da53d190b0490ee9faf3d2378" and inherited["checks"]["passed"],
        "ot0335_failed_before_output": invalid["event_types"] == ["thread.started", "turn.started", "error", "turn.failed"] and invalid["invalid_schema_named"] and invalid["no_actor_output"] and invalid["workspace_unchanged"],
        "only_schema_representation_repaired": files.get("items", {}).get("const") == "decision.json" and files.get("minItems") == 1 and files.get("maxItems") == 1 and "const" not in files,
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "source_ot0334_receipt_digest": result["receipt_digest"], "invalid_ot0335": invalid, "checks": checks}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, _, p82, runtime, core, base130, parent, result = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0336").resolve()
    with tempfile.TemporaryDirectory() as directory:
        frozen = preflight(Path(directory), store, p82, runtime, parent, result)
    if args.preflight_only:
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0336 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", frozen)
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0336 preflight failed")
    context = base.base.base305.actor_context(runtime, core, base130, run, repo)
    original_schema = base.SCHEMA
    base.SCHEMA = SCHEMA
    try:
        actor = base.run_actor(context, p82, run / "responder", parent, result)
    finally:
        base.SCHEMA = original_schema
    operational = bool(actor["accepted"] and actor["decision"]["action"] == "acquire-comparative-consequence")
    final, binding = base.compile_comparison(parent, result, actor, p82) if operational else (parent, None)
    checks = {
        "preflight_passed": frozen["checks"]["passed"],
        "fresh_actor_clean": actor["accepted"],
        "actor_requests_consequence_before_revision": operational,
        "actor_identifies_turnover_winners": operational and actor["decision"]["world_ids"] == base.turnover_winners(result["selection_history"]),
        "stake_byte_exact": final["active_world_seeking_stake"] == parent["active_world_seeking_stake"],
        "open_comparison_successor": operational and final["active_comparative_world_contact_request"] == binding and final["continuation"]["status"] == "open" and runtime.identity_conforms(final),
    }
    checks["passed"] = all(checks.values())
    body = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0334_receipt_digest": result["receipt_digest"],
        "invalid_ot0335_events_sha256": frozen["invalid_ot0335"]["events_sha256"],
        "actor": actor,
        "comparison_binding": binding,
        "checks": checks,
        "operational_transition_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
    }
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    if operational:
        write_json(run / "open-subject-awaiting-comparative-consequence.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
