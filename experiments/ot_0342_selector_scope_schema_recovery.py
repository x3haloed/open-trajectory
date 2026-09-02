from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0341_cumulative_floor_selector_scope.py"
BASE_SHA256 = "53e1e0c5a2a5b2a0ee2f7515a547e0f74655bb083d3e101c71da37bab3dfc7ec"
OLD_SCHEMA = REPO / "spec/ot-0341-selector-scope-decision.schema.json"
OLD_SCHEMA_SHA256 = "f642818192eeebd45bf877482e47cc53a933782fb1468a52c3b9c8fab1393cd8"
SCHEMA = REPO / "spec/ot-0342-selector-scope-decision.schema.json"
SCHEMA_SHA256 = "b33497554b72a0281c2bb79a28529e95ac1978eb28553eb57be3dc2175519741"
FAILURE_DIGEST = "a9102bd7ab142bd2b9a2757eced8de6419fafca0ed8cc8226b8c365f89663afc"
EVENTS_DIGEST = "45637915cdc2ca3e41c465cc142c8de077025abebd1d165af49bd13a23d1547f"
AUTHORITY = "ot-0342-selector-scope-schema-recovery"


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"frozen OT-0341 source changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0342_frozen_ot0341", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()
base.SCHEMA = SCHEMA
base.AUTHORITY = AUTHORITY
write_json = base.write_json


def setup(args):
    values = list(base.setup(args))
    repo, store = values[:2]
    values[2] = (args.evidence_root or store / "runs/OT-0342").resolve()
    selector = base.contact_base.contact.base.base.base.base.base.b.authority_base.guide_base.load_base().selector_base
    failure = selector.load_artifact(values[3], repo, store, "OT-0341", "pre-output-schema-failure.json")
    events = (store / "objects/sha256" / EVENTS_DIGEST[:2] / EVENTS_DIGEST).read_text()
    return (*values, failure, events)


def schema_delta():
    old = json.loads(OLD_SCHEMA.read_text())
    expected = copy.deepcopy(old)
    removed = expected["properties"]["files_changed"].pop("uniqueItems")
    new = json.loads(SCHEMA.read_text())
    return {
        "old_schema_digest": hashlib.sha256(OLD_SCHEMA.read_bytes()).hexdigest(),
        "new_schema_digest": hashlib.sha256(SCHEMA.read_bytes()).hexdigest(),
        "removed_keyword": "properties.files_changed.uniqueItems",
        "removed_value": removed,
        "otherwise_exact": new == expected,
        "new_schema": new,
    }


def preflight(root, values, failure, events):
    repo, store, run, p82, runtime, parent, aggregate340 = values[:7]
    parent326, seed326, parent328, result327, reconstruction327, private327, result334 = values[7:14]
    with tempfile.TemporaryDirectory() as directory:
        inherited, floor, contact, erased_floor = base.preflight(
            Path(directory), p82, runtime, parent, aggregate340, parent326,
            seed326, parent328, result327, reconstruction327, private327,
            result334,
        )
    delta = schema_delta()
    failure_object = store / "objects/sha256" / FAILURE_DIGEST[:2] / FAILURE_DIGEST
    events_object = store / "objects/sha256" / EVENTS_DIGEST[:2] / EVENTS_DIGEST
    event_text = events
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "old_schema_hash_exact": hashlib.sha256(OLD_SCHEMA.read_bytes()).hexdigest() == OLD_SCHEMA_SHA256,
        "new_schema_hash_exact": hashlib.sha256(SCHEMA.read_bytes()).hexdigest() == SCHEMA_SHA256,
        "exact_pre_output_failure": failure["error_code"] == "invalid_json_schema" and not failure["actor_output_available"] and failure["editable_files_byte_exact"],
        "failure_object_identity": hashlib.sha256(failure_object.read_bytes()).hexdigest() == FAILURE_DIGEST,
        "events_object_identity": hashlib.sha256(events_object.read_bytes()).hexdigest() == EVENTS_DIGEST,
        "events_prove_no_actor_output": "invalid_json_schema" in event_text and "turn.failed" in event_text and "item.completed" not in event_text,
        "only_unsupported_keyword_removed": delta["removed_value"] is True and delta["otherwise_exact"],
        "repaired_schema_omits_unique_items": "uniqueItems" not in json.dumps(delta["new_schema"], sort_keys=True),
        "ot0341_preflight_still_passes": inherited["checks"]["passed"],
    }
    checks["passed"] = all(checks.values())
    body = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0341_failure_digest": FAILURE_DIGEST,
        "source_ot0341_events_digest": EVENTS_DIGEST,
        "inherited_preflight_receipt_digest": inherited["receipt_digest"],
        "schema_delta": delta,
        "checks": checks,
    }
    report = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", report)
    return report, inherited, floor, contact, erased_floor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    all_values = setup(args)
    values, failure, events = all_values[:-2], all_values[-2], all_values[-1]
    repo, store, run, p82, runtime, parent, aggregate340 = values[:7]
    parent326, seed326, parent328, result327, reconstruction327, private327, result334, result330, result280, core, base130 = values[7:]
    with tempfile.TemporaryDirectory() as directory:
        report, inherited, floor, contact, erased_floor = preflight(Path(directory), values, failure, events)
    if args.preflight_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0342 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", report)
    write_json(run / "cumulative-floor-40.json", floor)
    write_json(run / "directional-contact.json", contact)
    write_json(run / "outcome-erased-floor-40.json", erased_floor)
    if not report["checks"]["passed"]:
        raise SystemExit("OT-0342 preflight failed")
    context = base.contact_base.contact.base305.actor_context(runtime, core, base130, run / "actors", repo)
    active = base.run_actor(context, run / "active", parent, floor, contact, p82, "schema-recovered-floor-scope-successor", erased=False)
    active_floor_score = base.score(active["candidate_stake"], floor) if active["accepted"] else None
    active_contact_score = base.score(active["candidate_stake"], [contact]) if active["accepted"] else None
    decision = active.get("decision") or {}
    operational = bool(
        active["accepted"] and not active["changed_stake"]
        and decision.get("global_stake_action") == "retain"
        and decision.get("world_policy_role") == "post-contact-selector"
        and decision.get("next_operation") == "test-world-consequence-policy-reuse"
        and active["pipeline"].get("reason") == "router-did-not-select"
        and active_floor_score["pass_count"] == 40
        and active_contact_score["pass_count"] == 0
    )
    child, scope_receipt, architecture = base.compile_child(parent, active, floor, contact, inherited["bounded_impossibility"], p82) if operational else (parent, None, None)
    write_json(run / "active-operational-subject.json", child)
    erased = base.run_actor(context, run / "erased", parent, erased_floor, contact, p82, "schema-recovered-floor-erased-successor", erased=True)
    erased_true_floor = base.score(erased["candidate_stake"], floor) if erased["accepted"] else None
    erased_contact = base.score(erased["candidate_stake"], [contact]) if erased["accepted"] else None
    erased_decision = erased.get("decision") or {}
    causal = bool(
        operational and erased["accepted"] and erased["changed_stake"]
        and erased_decision.get("global_stake_action") == "revise"
        and erased["pipeline"].get("available") is True
        and erased_true_floor["pass_count"] == 35
        and erased_contact["pass_count"] == 1
    )
    checks = {
        "preflight_passed": report["checks"]["passed"],
        "active_actor_clean": active["accepted"],
        "active_actor_invoked_inherited_pipeline": active["workspace_evaluation"]["pipeline_invoked"],
        "active_retains_nonregressive_global_stake": operational,
        "operational_child_sealed_before_control": (run / "active-operational-subject.json").exists(),
        "erased_actor_clean": erased["accepted"],
        "floor_erasure_changes_scope_decision": causal,
        "child_binds_two_stage_selection": not operational or child["active_selection_architecture"] == architecture,
        "child_open_conformant": child["continuation"]["status"] == "open" and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    disposition = "promoted" if checks["passed"] else ("conditional" if operational else "rejected")
    body = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_ot0341_failure_digest": FAILURE_DIGEST,
        "preflight_receipt_digest": report["receipt_digest"],
        "active_actor": active,
        "active_floor_score": active_floor_score,
        "active_contact_score": active_contact_score,
        "selector_scope_receipt": scope_receipt,
        "selection_architecture": architecture,
        "floor_outcome_erased_actor": erased,
        "erased_actor_true_floor_score": erased_true_floor,
        "erased_actor_contact_score": erased_contact,
        "checks": checks,
        "operational_transition_passed": operational,
        "executable_floor_causes_nonregressive_scope": causal,
        "observer_disposition": disposition,
        "subject_disposition": child["continuation"]["status"],
        "final_subject_digest": child["artifact_digest"],
        "fresh_actor_count": 2,
    }
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    if operational:
        write_json(run / "open-subject-after-selector-scope.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
