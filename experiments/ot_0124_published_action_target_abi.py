from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, tarfile, tempfile, time
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0123_authoritative_extension_coherence.py"
BASE_SHA256 = "c703085a72bf39947cb4b6f5fddccc04d084328fffa00138744f7549e65d38a2"
RUN_SHA256 = "49a2120fad05b00063d441aa223d20af1a6f3d4abe9aa7a87776006410f46854"
AGGREGATE_SHA256 = "d624d9e4073319109fcc997fb1aa76b5831552a22c81f4924c0591f10db84cb7"
PARENT_DIGEST = "1d309731183215aaa650f20a46164415ba6ca0348453ac383acdf45b18609aa5"
CORRECTOR_SCHEMA = REPO / "spec/ot-0124-action-corrector.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0123 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0124_frozen_ot0123", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior22 = previous.previous
base = previous.base
prior17 = previous.prior17
prior18 = previous.prior18


def extract(path, destination):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != "OT-0123" or member.name.startswith("/") or ".." in parts or member.issym() or member.islnk():
                raise RuntimeError("unsafe OT-0123 archive")
        archive.extractall(destination, members=members)
    return destination / "OT-0123"


def load_inputs(p82, repo, store, destination):
    run_manifest, run_path = p82.materialize(repo, store, "OT-0123", "authoritative-extension-coherence-run.json")
    aggregate_manifest, aggregate_path = p82.materialize(repo, store, "OT-0123", "authoritative-extension-coherence-aggregate.json")
    if run_manifest["sha256"] != RUN_SHA256 or aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0123 evidence")
    raw = extract(run_path, destination / "run23")
    aggregate = json.loads(aggregate_path.read_text())
    parent, corrected, selection, world, _, _, _, _ = previous.load_inputs(p82, repo, store, destination / "inputs22")
    workspace = raw / "coherent-router/actor-workspace"
    route = json.loads((workspace / "route-assimilation.json").read_text())
    opening = json.loads((workspace / "successor-opening.json").read_text())
    action = json.loads((workspace / "continuation-action.json").read_text())
    audit = json.loads((raw / "coherent-router/actor-audit.json").read_text())
    return parent, corrected, selection, world, route, opening, action, audit, aggregate


def retained_checks(parent, corrected, selection, world, route, opening, action, audit, aggregate):
    other_fields = {key: action[key] for key in action if key != "action_target"}
    checks = {
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "ot0123_rejected": not aggregate["operational_transition_passed"] and aggregate["coherent_route"]["binding"] is None,
        "all_semantic_coherence_passed": aggregate["coherent_route"]["coherence"]["passed"] and all(aggregate["coherent_route"]["coherence"].values()),
        "trace_clean_exact_truthful": bool(audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["accepted"] and audit["exact_changes"] and audit["truthful"]),
        "route_exact": route["route"] == "extend" and set(route["settled_case_ids"]) == previous.exact_case_ids(world),
        "opening_coherent": previous.has_resource_scarcity(opening["next_opening"]) and opening["next_opening"] != parent["continuation"]["next_opening"],
        "selector_exact": hashlib.sha256(corrected.encode()).hexdigest() == prior22.CORRECTED_SOURCE_SHA256,
        "selection_exact": selection["active_selection"]["selected_id"] == "joint-boundary",
        "invalid_target_is_only_action_issue": action["action_kind"] == "registry-extension" and not prior18.previous.previous.repaired_action_valid(action, parent) and all(isinstance(value, str) and value.strip() for value in other_fields.values()),
        "invalid_target_has_required_concepts": previous.has_resource_scarcity(action["action_target"]),
    }
    checks["passed"] = all(checks.values())
    return checks


def corrector_seed(run, parent, selection, world, route, opening, action):
    seed = run / "action-corrector-seed"
    seed.mkdir()
    (seed / "continuation-action.json").write_text(json.dumps(action, indent=2, sort_keys=True) + "\n")
    (seed / "retained-route-assimilation.json").write_text(json.dumps(route, indent=2, sort_keys=True) + "\n")
    (seed / "retained-successor-opening.json").write_text(json.dumps(opening, indent=2, sort_keys=True) + "\n")
    (seed / "retained-receipts.json").write_text(json.dumps({"source_subject_digest": parent["artifact_digest"], "selection_binding_digest": selection["binding_digest"], "world_receipt_digest": world["receipt_digest"]}, indent=2, sort_keys=True) + "\n")
    (seed / "action-target-contract.json").write_text(json.dumps({
        "action_kind_exact": "registry-extension",
        "action_target_fullmatch_regex": "[a-z][a-z0-9-]{2,127}",
        "action_target_required_concepts": ["resource", "scarcity"],
        "action_target_must_differ_from": parent["actor_originated_pursuit_openings"][-1]["continuation_action"]["action_target"],
        "immutable_action_fields": ["expected_information", "rationale", "surrender_condition"],
    }, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["continuation-action.json"], "immutable": ["retained-route-assimilation.json", "retained-successor-opening.json", "retained-receipts.json", "action-target-contract.json"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Correct only action_target so continuation-action.json satisfies the complete published ABI. Preserve every other action field and every retained file exactly, inspect the diff, and report truthfully.\n")
    return seed


def run_corrector(p82, context, run, parent, selection, world, route, opening, action):
    seed = corrector_seed(run, parent, selection, world, route, opening, action)
    output, base_audit, workspace, _ = context.run_actor("action-corrector", seed, CORRECTOR_SCHEMA, "Correct only action_target under the published ABI. Preserve all other bytes, inspect the exact diff, and report truthfully.")
    try:
        corrected = json.loads((workspace / "continuation-action.json").read_text())
        immutable = (workspace / "retained-route-assimilation.json").read_text() == (seed / "retained-route-assimilation.json").read_text() and (workspace / "retained-successor-opening.json").read_text() == (seed / "retained-successor-opening.json").read_text()
    except (OSError, json.JSONDecodeError):
        corrected = None
        immutable = False
    unchanged_fields = bool(corrected and all(corrected.get(key) == action[key] for key in action if key != "action_target"))
    valid = bool(corrected and immutable and unchanged_fields and corrected["action_target"] != action["action_target"] and previous.has_resource_scarcity(corrected["action_target"]) and prior18.previous.previous.repaired_action_valid(corrected, parent))
    audit = context.audit_actor("action-corrector", output, base_audit, valid, ["continuation-action.json"])
    binding = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0124-published-action-target-correction",
            "source_subject_digest": parent["artifact_digest"],
            "selection_binding_digest": selection["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "route_assimilation": route,
            "successor_opening": opening,
            "continuation_action": corrected,
            "other_action_fields_retained": unchanged_fields,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("action-corrector") / "bound-route.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "other_action_fields_retained": unchanged_fields, "binding": binding}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0124").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    with tempfile.TemporaryDirectory() as directory:
        inputs = load_inputs(p82, repo, store, Path(directory))
    parent, corrected, selection, world, route, opening, action, audit, aggregate = inputs
    checks = retained_checks(*inputs)
    checks["parent_sounding"] = runtime.identity_conforms(parent)
    checks["passed"] = all(value for key, value in checks.items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "run_sha256": RUN_SHA256, "aggregate_sha256": AGGREGATE_SHA256, "checks": checks}, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0124 evidence")
    run.mkdir(parents=True)
    (run / "retained-input-checks.json").write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n")
    if not checks["passed"]:
        raise SystemExit("retained input conformance failed")
    context = prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    correction = run_corrector(p82, context, run, parent, selection, world, route, opening, action)
    current = parent
    promotion = None
    if correction["binding"]:
        current, promotion = prior22.promote(p82, parent, selection, world, correction["binding"])
    operational = bool(promotion and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and previous.has_resource_scarcity(current["continuation"]["next_opening"]))
    result = {
        "authority": "ot-0124-published-action-target-abi-driver",
        "source_subject_digest": parent["artifact_digest"],
        "selection_binding_digest": selection["binding_digest"],
        "world_receipt_digest": world["receipt_digest"],
        "retained_input_checks": checks,
        "action_correction": p82.compact(correction),
        "promotion": promotion,
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
