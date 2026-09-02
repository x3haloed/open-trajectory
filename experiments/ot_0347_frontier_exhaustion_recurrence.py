from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0346_toolchain_cache_denial_attribution.py"
BASE_SHA256 = "9017622d414b11669e07ab2e32a96e63c201f0233f43b439723c8d77a5b49858"
PARENT_DIGEST = "94399d16be3bbaab15dbc977e69787a8c94740a90c18fb5a61e5f346c0c14bbf"
PRIVATE_SEED_DIGEST = "f61bf1f790d415248c3e1799f702c5ac8d8e322973278d518acc8e65cc6d5b94"
AUTHORITY = "ot-0347-frontier-exhaustion-recurrence"
SCHEMA = REPO / "spec/ot-0347-frontier-recurrence.schema.json"


def import_frozen(path: Path, expected: str, name: str):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"frozen source changed: {path.name}: {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0347_frozen_ot0346")
carrier = base.base
world_base = carrier.base
write_json = carrier.write_json


def object_path(store: Path, digest: str) -> Path:
    return store / "objects/sha256" / digest[:2] / digest


def load_parent(repo: Path, store: Path):
    manifest = json.loads((repo / "evidence/manifests/OT-0346/open-subject-after-toolchain-denial-reconstruction.json").read_text())
    raw = object_path(store, manifest["sha256"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise RuntimeError("OT-0346 parent object mismatch")
    return json.loads(raw)


def setup(args):
    repo, store, _, p82, runtime, core, base130, _, _ = carrier.setup(args)
    run = (args.evidence_root or store / "runs/OT-0347").resolve()
    return repo, store, run, p82, runtime, core, base130, load_parent(repo, store)


CHECK = '''import importlib.util,json,re\nfrom pathlib import Path\nspec=importlib.util.spec_from_file_location("candidate",Path("source.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); c=json.loads(Path("contact.json").read_text()); n=json.loads(Path("next-opening.json").read_text()); rows=[{"value":row["value"],"expected":row["expected"],"observed":m.admits(row["value"]),"passed":m.admits(row["value"])==row["expected"]} for row in c["public_cases"]]; remaining=c["remaining_after_active"]; continuation=isinstance(n,dict) and set(n)=={"opening_id","next_operation","contact_id","rationale"} and isinstance(n["opening_id"],str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}",n["opening_id"])) and isinstance(n["rationale"],str) and 1<=len(n["rationale"])<=2000 and ((bool(remaining) and n["next_operation"]=="continue-world-contact" and n["contact_id"] in remaining) or (not remaining and n["next_operation"]=="test-world-consequence-policy-reuse" and n["contact_id"] is None)); ok=all(row["passed"] for row in rows) and continuation; print(json.dumps({"valid":ok,"rows":rows,"remaining_count":len(remaining),"next_operation":n.get("next_operation"),"next_contact_id":n.get("contact_id")},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''


def next_operation(subject, p82):
    if carrier.valid_frontier(subject, p82):
        return "continue-world-contact"
    exhausted = subject.get("exhausted_world_contact_frontiers", [])
    architecture = subject.get("active_selection_architecture", {})
    if (
        exhausted
        and exhausted[-1].get("status") == "exhausted"
        and not exhausted[-1].get("remaining_contact_ids")
        and set(exhausted[-1].get("consumed_contact_ids", [])) == set(exhausted[-1].get("contact_ids", []))
        and architecture.get("next_operation") == "test-world-consequence-policy-reuse"
        and "fresh consequence catalog" in subject.get("continuation", {}).get("next_opening", "")
    ):
        return "test-world-consequence-policy-reuse"
    return None


def materialize(subject, p82, root: Path):
    if next_operation(subject, p82) != "continue-world-contact":
        return None
    frontier = subject["active_world_contact_frontier"]
    active = next(row for row in frontier["contacts"] if row["contact_id"] == frontier["active_contact_id"])
    remaining = [value for value in frontier["remaining_contact_ids"] if value != active["contact_id"]]
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "contact.json", {"frontier_binding_digest": frontier["binding_digest"], "contact_id": active["contact_id"], "public_cases": active["public_cases"], "remaining_after_active": remaining, "interface": active["interface"], "on_exhaustion": "test-world-consequence-policy-reuse"})
    (seed / "source.py").write_text(world_base.SOURCE_TEMPLATE.format(cutoff=active["cutoff"]))
    write_json(seed / "next-opening.json", {"opening_id": "replace-me", "next_operation": "continue-world-contact", "contact_id": None, "rationale": "Replace after completing the active contact."})
    (seed / "check_contact.py").write_text(CHECK)
    immutable = ["contact.json", "check_contact.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["source.py", "next-opening.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue the active contact carried by the subject. Repair source.py, then follow the typed continuation rule in contact.json: choose one remaining contact when present; otherwise route to test-world-consequence-policy-reuse with a null contact_id. Run python3 check_contact.py, inspect the exact diff, and return the required report. Hidden cases, private world state, controls, evaluator, and admission result are unavailable. Edit no other file.\n")
    return seed


def valid_choice(choice, remaining):
    return bool(
        isinstance(choice, dict)
        and set(choice) == {"opening_id", "next_operation", "contact_id", "rationale"}
        and isinstance(choice["opening_id"], str)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", choice["opening_id"])
        and isinstance(choice["rationale"], str)
        and 1 <= len(choice["rationale"]) <= 2000
        and (
            (bool(remaining) and choice["next_operation"] == "continue-world-contact" and choice["contact_id"] in remaining)
            or (not remaining and choice["next_operation"] == "test-world-consequence-policy-reuse" and choice["contact_id"] is None)
        )
    )


def run_actor(context, root: Path, subject, world, p82, index):
    label = f"frontier-recurrence-{index:02d}"
    seed = materialize(subject, p82, root)
    if seed is None:
        raise RuntimeError("subject did not materialize active contact")
    output, audit0, workspace, _ = context.run_actor(label, seed, SCHEMA, (seed / "README.md").read_text().strip())
    trace = (context.evidence(label) / "events.jsonl").read_text()
    stderr = (context.evidence(label) / "stderr.txt").read_text()
    frontier = subject["active_world_contact_frontier"]
    active_id = frontier["active_contact_id"]
    external = next(row for row in world["contacts"] if row["contact_id"] == active_id)
    public = next(row for row in frontier["contacts"] if row["contact_id"] == active_id)
    remaining = [value for value in frontier["remaining_contact_ids"] if value != active_id]
    try:
        choice = json.loads((workspace / "next-opening.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        public_result = world_base.evaluate_source(workspace / "source.py", public["public_cases"])
        hidden_result = world_base.evaluate_source(workspace / "source.py", external["hidden_cases"])
        checker_invoked = world_base.named_command_succeeded(trace, "check_contact.py")
        semantic = bool(immutable_ok and public == carrier.public_spec(external) and public_result["pass_count"] == public_result["case_count"] == 3 and hidden_result["pass_count"] == hidden_result["case_count"] == 5 and checker_invoked and valid_choice(choice, remaining) and world_base.output_valid(output, "realize-frontier-contact", ["source.py", "next-opening.json"]))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        choice = None
        public_result = hidden_result = None
        immutable_ok = checker_invoked = semantic = False
    audit = context.audit_actor(label, output, audit0, semantic, ["source.py", "next-opening.json"])
    retained = base.g11.retained_row(audit, trace, stderr)
    regime = {"authority": base.AUTHORITY, "challenger_accepted": base.g13(retained), "g11_accepted": base.g11.g11(retained), "toolchain_cache_denial_attributed": base.attributable_toolchain_cache_denial(retained)}
    return {"accepted": bool(semantic and regime["challenger_accepted"]), "active_contact_id": active_id, "choice": choice, "public_result": public_result, "hidden_result": hidden_result, "output": output, "audit": audit, "g13": regime, "workspace_evaluation": {"immutable_ok": immutable_ok, "checker_invoked": checker_invoked, "semantic": semantic}}


def compile_cycle(subject, actor, p82):
    old = subject["active_world_contact_frontier"]
    current = old["active_contact_id"]
    remaining = [value for value in old["remaining_contact_ids"] if value != current]
    consequence_body = {"authority": AUTHORITY + "-contact-consequence", "source_subject_digest": subject["artifact_digest"], "source_frontier_binding_digest": old["binding_digest"], "actor_patch_digest": actor["audit"]["patch_digest"], "active_contact_id": current, "public_result": actor["public_result"], "hidden_result": actor["hidden_result"], "choice": actor["choice"], "world_authority": True, "outcome_authority": True, "scoring_authority": True, "actor_authority": False}
    consequence = {**consequence_body, "receipt_digest": p82.digest(consequence_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["completed_contact_consequences"] = [*child.get("completed_contact_consequences", []), consequence]
    body = {key: copy.deepcopy(value) for key, value in old.items() if key != "binding_digest"}
    body["consumed_contact_ids"] = [*body["consumed_contact_ids"], current]
    body["remaining_contact_ids"] = remaining
    if remaining:
        body["active_contact_id"] = actor["choice"]["contact_id"]
        frontier = {**body, "binding_digest": p82.digest(body)}
        child["world_contact_frontiers"] = [*child.get("world_contact_frontiers", []), frontier]
        child["active_world_contact_frontier"] = frontier
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Continue the selected world through contact {frontier['active_contact_id']}."}
    else:
        child.pop("active_world_contact_frontier", None)
        exhausted = {"authority": AUTHORITY + "-exhausted-contact-frontier", "source_frontier_binding_digest": old["binding_digest"], "contact_ids": [row["contact_id"] for row in old["contacts"]], "consumed_contact_ids": body["consumed_contact_ids"], "remaining_contact_ids": [], "status": "exhausted", "next_operation": actor["choice"]["next_operation"]}
        exhausted["receipt_digest"] = p82.digest(exhausted)
        child["exhausted_world_contact_frontiers"] = [*child.get("exhausted_world_contact_frontiers", []), exhausted]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Test the retained world-consequence policy on a fresh consequence catalog without sacrificing the global 40/40 floor."}
    return p82.seal(child), consequence


def preflight(parent, p82, runtime):
    g13_anchor = base.anchors()
    g12_anchor = world_base.base.anchors()
    g11_anchor = base.g11.evaluate(base.g11.g11)
    with __import__("tempfile").TemporaryDirectory() as directory:
        seeded = materialize(parent, p82, Path(directory))
    first_remaining = [value for value in parent["active_world_contact_frontier"]["remaining_contact_ids"] if value != parent["active_world_contact_frontier"]["active_contact_id"]]
    checks = {
        "source_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent),
        "two_remaining_contacts": len(parent["active_world_contact_frontier"]["remaining_contact_ids"]) == 2 and len(first_remaining) == 1,
        "subject_only_materialization": seeded is not None,
        "premature_expansion_rejects": not valid_choice({"opening_id": "premature-expand", "next_operation": "test-world-consequence-policy-reuse", "contact_id": None, "rationale": "fixture"}, first_remaining),
        "one_remaining_contact_accepts": valid_choice({"opening_id": "continue-one", "next_operation": "continue-world-contact", "contact_id": first_remaining[0], "rationale": "fixture"}, first_remaining),
        "exhaustion_requires_policy_reuse": valid_choice({"opening_id": "expand-after-exhaustion", "next_operation": "test-world-consequence-policy-reuse", "contact_id": None, "rationale": "fixture"}, []) and not valid_choice({"opening_id": "invalid-contact", "next_operation": "continue-world-contact", "contact_id": first_remaining[0], "rationale": "fixture"}, []),
        "g13_12_of_12": g13_anchor["pass_count"] == g13_anchor["case_count"] == 12,
        "g12_10_of_10": g12_anchor["pass_count"] == g12_anchor["case_count"] == 10,
        "g11_15_of_15": g11_anchor["pass_count"] == g11_anchor["case_count"] == 15,
        "schema_explicit": set(json.loads(SCHEMA.read_text())["required"]) == {"action", "files_changed", "note"},
        "checker_compiles": bool(compile(CHECK, "check_contact.py", "exec")),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "g13_anchor": g13_anchor, "g12_anchor": g12_anchor, "g11_anchor": g11_anchor, "checks": checks}
    return {**body, "receipt_digest": p82.digest(body)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--private-seed-file", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, core, base130, parent = setup(args)
    report = preflight(parent, p82, runtime)
    if args.preflight_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0347 evidence")
    if args.private_seed_file is None:
        raise SystemExit("--private-seed-file is required for exact hidden outcomes")
    private_seed = args.private_seed_file.read_bytes()
    if hashlib.sha256(private_seed).hexdigest() != PRIVATE_SEED_DIGEST:
        raise SystemExit("private seed does not match the retained world")
    world = next(row for row in world_base.derive_worlds(private_seed) if row["world_id"] == parent["active_world_contact_frontier"]["selected_world_id"])
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", report)
    if not report["checks"]["passed"]:
        raise SystemExit("OT-0347 preflight failed")
    context = world_base.policy_base.contact.base305.actor_context(runtime, core, base130, run / "actors", repo)
    subject = parent
    actors = []
    consequences = []
    for index in (1, 2):
        actor = run_actor(context, run / f"cycle-{index:02d}", subject, world, p82, index)
        actors.append(actor)
        if not actor["accepted"]:
            break
        subject, consequence = compile_cycle(subject, actor, p82)
        consequences.append(consequence)
        write_json(run / f"subject-after-cycle-{index:02d}.json", subject)
    write_json(run / "active-subject-before-controls.json", subject)
    erased = copy.deepcopy(parent)
    erased.pop("active_world_contact_frontier", None)
    checks = {
        "preflight_passed": report["checks"]["passed"],
        "two_fresh_actors_clean": len(actors) == 2 and all(actor["accepted"] for actor in actors),
        "both_public_3_of_3": len(actors) == 2 and all(actor["public_result"]["pass_count"] == actor["public_result"]["case_count"] == 3 for actor in actors),
        "both_hidden_5_of_5": len(actors) == 2 and all(actor["hidden_result"]["pass_count"] == actor["hidden_result"]["case_count"] == 5 for actor in actors),
        "first_actor_selects_second_cycle": len(actors) == 2 and actors[0]["choice"]["contact_id"] == actors[1]["active_contact_id"],
        "all_four_contacts_consumed": len(consequences) == 2 and len(subject.get("exhausted_world_contact_frontiers", [])[-1]["consumed_contact_ids"]) == 4,
        "frontier_erasure_cannot_continue": next_operation(erased, p82) is None,
        "exhaustion_routes_policy_reuse": next_operation(subject, p82) == "test-world-consequence-policy-reuse",
        "open_conformant_subject": subject["continuation"]["status"] == "open" and runtime.identity_conforms(subject),
        "exact_floor_40_preserved": subject["active_world_seeking_stake"] == parent["active_world_seeking_stake"] and subject["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["pass_count"] == 40,
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "preflight_receipt_digest": report["receipt_digest"], "actors": actors, "contact_consequence_receipts": consequences, "controls": {"frontier_erased_next_operation": next_operation(erased, p82)}, "checks": checks, "operational_recurrence_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": subject["continuation"]["status"] if checks["passed"] else "quarantined", "final_subject_digest": subject["artifact_digest"], "fresh_actor_count": len(actors)}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", subject)
    if checks["passed"]:
        write_json(run / "open-subject-after-frontier-exhaustion.json", subject)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
