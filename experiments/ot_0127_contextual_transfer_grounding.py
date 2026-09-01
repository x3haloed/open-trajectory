from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, tarfile, tempfile, time
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0126_continuation_owned_scheduler_recurrence.py"
BASE_SHA256 = "5d4345d40b5c3a2b5d800a7731f5c25889499f27580da3bbbb16123eab3a7d12"
RUN_SHA256 = "d20935f7ca0f61552336ada22c4e1c46208035dde3b9c8571f1e0ad92a5116d5"
AGGREGATE_SHA256 = "880a816736b0658df84e4505d86da767dcf0e8aa1ef3ceb4a0e03bd7d6090adb"
PARENT_OBJECT_SHA256 = "214c8a7a92d155583c7965e6bad1b0ed920df127e115549449176e144e463545"
PARENT_DIGEST = "7055c37a6f29f39e84690ca01c1e9ab78f7aa55798dd073bffd5a879b504cd77"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0126 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0127_frozen_ot0126", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior = previous.prior
prior22 = previous.prior22
base = previous.base
prior18 = previous.prior18


def extract(path, destination):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != "OT-0126" or member.name.startswith("/") or ".." in parts or member.issym() or member.islnk():
                raise RuntimeError("unsafe OT-0126 archive")
        archive.extractall(destination, members=members)
    return destination / "OT-0126"


def contextual_transfer_grounded(value):
    text = value.lower().replace("-", " ") if isinstance(value, str) else ""
    return "context" in text and ("cross" in text or "different" in text)


def load_inputs(p82, repo, store, destination):
    run_manifest, run_path = p82.materialize(repo, store, "OT-0126", "continuation-owned-scheduler-recurrence-run.json")
    aggregate_manifest, aggregate_path = p82.materialize(repo, store, "OT-0126", "continuation-owned-scheduler-recurrence-aggregate.json")
    parent_manifest, parent_path = p82.materialize(repo, store, "OT-0126", "open-subject-after-two-scheduler-cycles.json")
    if run_manifest["sha256"] != RUN_SHA256 or aggregate_manifest["sha256"] != AGGREGATE_SHA256 or parent_manifest["sha256"] != PARENT_OBJECT_SHA256:
        raise RuntimeError("wrong OT-0126 evidence")
    raw = extract(run_path, destination)
    aggregate = json.loads(aggregate_path.read_text())
    parent = json.loads(parent_path.read_text())
    selection = json.loads((raw / "cycle-3/bound-contact-selection.json").read_text())
    world = json.loads((raw / "cycle-3/selected-world-receipt.json").read_text())
    workspace = raw / "cycle-3-router/actor-workspace"
    route = json.loads((workspace / "route-assimilation.json").read_text())
    opening = json.loads((workspace / "successor-opening.json").read_text())
    action = json.loads((workspace / "continuation-action.json").read_text())
    selector = (workspace / "selector.py").read_text()
    audit = json.loads((raw / "cycle-3-router/actor-audit.json").read_text())
    return aggregate, parent, selection, world, route, opening, action, selector, audit


def reconstruct(p82, inputs):
    aggregate, parent, selection, world, route, opening, action, selector, audit = inputs
    cycle_three = aggregate["cycles"][2]
    frozen = cycle_three["route"]["coherence"]
    expected_ids = {row["case_id"] for row in world["selected_branch"]["cases"]}
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "two_cycles_promoted": aggregate["completed_cycle_count"] == 2 and all(aggregate["cycles"][index]["operational_transition_passed"] for index in (0, 1)),
        "third_cycle_rejected": not cycle_three["operational_transition_passed"] and cycle_three["route"]["binding"] is None,
        "active_choice_oracle": selection["active_selection"]["selected_id"] == world["oracle_contact_id"],
        "control_choice_differs": selection["precorrection_control_selection"]["selected_id"] != selection["active_selection"]["selected_id"],
        "route_exact": route["route"] == world["expected_route"] == "extend",
        "case_ids_exact": set(route["settled_case_ids"]) == expected_ids,
        "selector_retained": hashlib.sha256(selector.encode()).hexdigest() == prior.CORRECTED_SOURCE_SHA256,
        "action_valid": prior18.previous.previous.repaired_action_valid(action, parent),
        "opening_valid": prior.base.mechanism.prior_chain(base.mechanism.load_prior())[2].valid_successor(opening),
        "trace_accepted": bool(audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["accepted"] and audit["exact_changes"] and audit["truthful"] and not audit["denial_classification_v2"]["protected_path_named"] and not audit["denial_classification_v2"]["outside_file_changes"]),
        "only_frozen_coherence_failure": not frozen["continuation_grounded"] and all(value for key, value in frozen.items() if key not in {"continuation_grounded", "passed"}),
        "authoritative_opening_contextual": contextual_transfer_grounded(opening["next_opening"]),
        "continuation_equivalence_passes": contextual_transfer_grounded(opening["continuation_after_contact"]),
        "route_uncertainty_contextual": contextual_transfer_grounded(route["remaining_uncertainty"]),
        "expected_information_contextual": contextual_transfer_grounded(action["expected_information"]),
    }
    checks["passed"] = all(checks.values())
    binding = None
    if checks["passed"]:
        body = {
            "authority": "ot-0127-contextual-transfer-equivalence-route",
            "cycle": 3,
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": selection["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "scheduler_authority": "successor_opening.next_opening",
            "contextual_transfer_equivalence": "context and (cross or different)",
            "reaudit_checks": checks,
            "selector_retention_derived": True,
            "route_assimilation": route,
            "successor_opening": opening,
            "continuation_action": action,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
    return checks, binding


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0127").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    with tempfile.TemporaryDirectory() as directory:
        inputs = load_inputs(p82, repo, store, Path(directory))
    aggregate, parent, selection, world, route, opening, action, selector, audit = inputs
    checks, binding = reconstruct(p82, inputs)
    checks["parent_sounding"] = runtime.identity_conforms(parent)
    checks["passed"] = all(value for key, value in checks.items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "run_sha256": RUN_SHA256, "aggregate_sha256": AGGREGATE_SHA256, "checks": checks}, indent=2, sort_keys=True))
        return 0 if checks["passed"] and binding else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0127 evidence")
    run.mkdir(parents=True)
    started = time.time()
    (run / "contextual-transfer-checks.json").write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n")
    current = parent
    promotion = None
    if binding and checks["passed"]:
        (run / "bound-retained-cycle-3-route.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
        current, promotion = prior22.promote(p82, parent, selection, world, binding)
    operational = bool(promotion and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and contextual_transfer_grounded(current["continuation"]["next_opening"]))
    result = {
        "authority": "ot-0127-contextual-transfer-grounding-driver",
        "source_subject_digest": parent["artifact_digest"],
        "selection_binding_digest": selection["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "reconstruction_checks": checks,
        "route_binding_digest": binding["binding_digest"] if binding else None,
        "promotion": promotion,
        "three_cycle_retained_recurrence_passed": operational,
        "operational_transition_passed": operational,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
