from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0350_prediction_error_routed_correction.py"
BASE_SHA256 = "35c24f51db95d6ef8e3dac9ce6fa46593726d946f459d0344f37bca67fbc3c13"
PARENT_DIGEST = "263126ebaad8694a03d43adc7cd6823fa1949aebad76a41b7f1ad026783af1bf"
PRIVATE_SEED_DIGEST = "30d8b459ac07a8f1f8741b5c757e4ed8bb9f0bfa347cfb27dbb4f151be00e185"
POLICY_SOURCE_DIGEST = "5587883527f564304cfa4f9dd5ed6b05edba20782cd512c58d4011352b068b3b"
AUTHORITY = "ot-0351-corrected-policy-frontier-recurrence"
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


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0351_frozen_ot0350")
world = base.prior
contact_world = world.world_base
write_json = world.write_json


CHECK = '''import importlib.util,json,re
from pathlib import Path
spec=importlib.util.spec_from_file_location("candidate",Path("source.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); c=json.loads(Path("contact.json").read_text()); n=json.loads(Path("next-opening.json").read_text()); rows=[{"value":r["value"],"expected":r["expected"],"observed":m.admits(r["value"]),"passed":m.admits(r["value"])==r["expected"]} for r in c["public_cases"]]; remaining=c["remaining_after_active"]; continuation=isinstance(n,dict) and set(n)=={"opening_id","next_operation","contact_id","rationale"} and isinstance(n["opening_id"],str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}",n["opening_id"])) and isinstance(n["rationale"],str) and 1<=len(n["rationale"])<=2000 and ((bool(remaining) and n["next_operation"]=="continue-world-contact" and n["contact_id"] in remaining) or (not remaining and n["next_operation"]=="test-world-consequence-policy-reuse" and n["contact_id"] is None)); ok=all(r["passed"] for r in rows) and continuation; print(json.dumps({"valid":ok,"rows":rows,"remaining_count":len(remaining),"next_operation":n.get("next_operation"),"next_contact_id":n.get("contact_id")},sort_keys=True)); raise SystemExit(0 if ok else 2)
'''


def object_path(store: Path, digest: str) -> Path:
    return store / "objects/sha256" / digest[:2] / digest


def load_parent(repo: Path, store: Path):
    manifest = json.loads((repo / "evidence/manifests/OT-0350/open-subject-after-routed-policy-correction.json").read_text())
    raw = object_path(store, manifest["sha256"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise RuntimeError("OT-0350 parent object mismatch")
    return json.loads(raw)


def setup(args):
    repo, store, _, p82, runtime, core, base130, *_ = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0351").resolve()
    return repo, store, run, p82, runtime, core, base130, load_parent(repo, store)


def valid_frontier(subject, p82):
    frontier = subject.get("active_world_contact_frontier")
    if not isinstance(frontier, dict):
        return False
    body = {key: copy.deepcopy(value) for key, value in frontier.items() if key != "binding_digest"}
    contacts = frontier.get("contacts", [])
    ids = frontier.get("contact_ids", [])
    remaining = frontier.get("remaining_contact_ids", [])
    return bool(
        frontier.get("binding_digest") == p82.digest(body)
        and ids == [row.get("contact_id") for row in contacts]
        and len(ids) == len(set(ids))
        and set(remaining).issubset(set(ids))
        and frontier.get("active_contact_id") in remaining
        and all(set(row) == {"contact_id", "cutoff", "interface", "public_cases"} and len(row["public_cases"]) == 3 for row in contacts)
        and valid_program(subject)
    )


def valid_program(subject):
    program = subject.get("active_world_consequence_policy_program", {})
    source = program.get("policy_source")
    expected_bindings = []
    frontier = subject.get("active_world_contact_frontier")
    if isinstance(frontier, dict):
        expected_bindings.append(frontier.get("policy_binding_digest"))
    exhausted = subject.get("exhausted_world_contact_frontiers", [])
    if exhausted and isinstance(exhausted[-1], dict):
        expected_bindings.append(exhausted[-1].get("policy_binding_digest"))
    return bool(
        isinstance(source, str)
        and program.get("policy_source_digest") == POLICY_SOURCE_DIGEST
        and hashlib.sha256(source.encode()).hexdigest() == POLICY_SOURCE_DIGEST
        and program.get("binding_digest") in expected_bindings
    )


def next_operation(subject, p82):
    if valid_frontier(subject, p82):
        return "continue-world-contact"
    exhausted = subject.get("exhausted_world_contact_frontiers", [])
    if not exhausted:
        return None
    last = exhausted[-1]
    complete = bool(last.get("status") == "exhausted" and not last.get("remaining_contact_ids") and set(last.get("contact_ids", [])) == set(last.get("consumed_contact_ids", [])))
    if complete and last.get("next_operation") == "test-world-consequence-policy-reuse" and valid_program(subject) and "fresh consequence catalog" in subject.get("continuation", {}).get("next_opening", ""):
        return "test-world-consequence-policy-reuse"
    return None


def valid_choice(choice, remaining):
    return bool(
        isinstance(choice, dict)
        and set(choice) == {"opening_id", "next_operation", "contact_id", "rationale"}
        and isinstance(choice["opening_id"], str)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", choice["opening_id"])
        and isinstance(choice["rationale"], str)
        and 1 <= len(choice["rationale"]) <= 2000
        and ((remaining and choice["next_operation"] == "continue-world-contact" and choice["contact_id"] in remaining) or (not remaining and choice["next_operation"] == "test-world-consequence-policy-reuse" and choice["contact_id"] is None))
    )


def materialize(subject, p82, root: Path):
    if next_operation(subject, p82) != "continue-world-contact":
        return None
    frontier = subject["active_world_contact_frontier"]
    active = next(row for row in frontier["contacts"] if row["contact_id"] == frontier["active_contact_id"])
    remaining = [cid for cid in frontier["remaining_contact_ids"] if cid != active["contact_id"]]
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "contact.json", {"frontier_binding_digest": frontier["binding_digest"], "policy_binding_digest": frontier["policy_binding_digest"], "contact_id": active["contact_id"], "public_cases": active["public_cases"], "remaining_after_active": remaining, "interface": active["interface"], "on_exhaustion": "test-world-consequence-policy-reuse"})
    (seed / "source.py").write_text(contact_world.SOURCE_TEMPLATE.format(cutoff=active["cutoff"] + 1))
    write_json(seed / "next-opening.json", {"opening_id": "replace-me", "next_operation": "continue-world-contact", "contact_id": None, "rationale": "Replace after completing the active contact."})
    (seed / "check_contact.py").write_text(CHECK)
    immutable = ["contact.json", "check_contact.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["source.py", "next-opening.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue the active contact carried by the subject. Repair source.py, then follow the typed continuation rule in contact.json: choose one remaining contact when present; otherwise route to test-world-consequence-policy-reuse with a null contact_id. Run python3 check_contact.py, inspect the exact diff, and return the required report. Hidden cases, private world state, controls, evaluator, and admission result are unavailable. Edit no other file.\n")
    return seed


def run_actor(context, root, subject, hidden_world, p82, index):
    label = f"corrected-policy-frontier-{index:02d}"
    seed = materialize(subject, p82, root)
    if seed is None:
        raise RuntimeError("subject did not materialize an active contact")
    output, audit0, workspace, _ = context.run_actor(label, seed, SCHEMA, (seed / "README.md").read_text().strip())
    frontier = subject["active_world_contact_frontier"]
    active_id = frontier["active_contact_id"]
    public = next(row for row in frontier["contacts"] if row["contact_id"] == active_id)
    hidden = next(row for row in hidden_world["future_contacts"] if row["contact_id"] == active_id)
    remaining = [cid for cid in frontier["remaining_contact_ids"] if cid != active_id]
    try:
        choice = json.loads((workspace / "next-opening.json").read_text())
        checker = subprocess.run([sys.executable, "check_contact.py"], cwd=workspace, capture_output=True)
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        public_result = contact_world.evaluate_source(workspace / "source.py", public["public_cases"])
        hidden_result = contact_world.evaluate_source(workspace / "source.py", hidden["hidden_cases"])
        semantic = bool(immutable_ok and checker.returncode == 0 and public_result["pass_count"] == public_result["case_count"] == 3 and hidden_result["pass_count"] == hidden_result["case_count"] == 5 and valid_choice(choice, remaining) and output == {"action": "realize-frontier-contact", "files_changed": ["source.py", "next-opening.json"], "note": output["note"]})
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        choice = public_result = hidden_result = None
        immutable_ok = semantic = False
    audit, regime = world.audit_g13(context, label, output, audit0, semantic, ["source.py", "next-opening.json"])
    return {"accepted": bool(semantic and regime["challenger_accepted"]), "active_contact_id": active_id, "choice": choice, "public_result": public_result, "hidden_result": hidden_result, "output": output, "audit": audit, "g13": regime, "immutable_ok": immutable_ok}


def compile_cycle(subject, actor, p82):
    old = subject["active_world_contact_frontier"]
    current = old["active_contact_id"]
    remaining = [cid for cid in old["remaining_contact_ids"] if cid != current]
    consequence = {"authority": AUTHORITY + "-contact-consequence", "source_subject_digest": subject["artifact_digest"], "source_frontier_binding_digest": old["binding_digest"], "actor_patch_digest": actor["audit"]["patch_digest"], "active_contact_id": current, "public_result": actor["public_result"], "hidden_result": actor["hidden_result"], "choice": actor["choice"], "world_authority": True, "outcome_authority": True, "scoring_authority": True, "actor_authority": False}
    consequence["receipt_digest"] = p82.digest(consequence)
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
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Continue the verified downstream frontier through contact {frontier['active_contact_id']}."}
    else:
        child.pop("active_world_contact_frontier", None)
        exhausted = {"authority": AUTHORITY + "-exhausted-frontier", "source_frontier_binding_digest": old["binding_digest"], "policy_binding_digest": old["policy_binding_digest"], "contact_ids": old["contact_ids"], "consumed_contact_ids": body["consumed_contact_ids"], "remaining_contact_ids": [], "status": "exhausted", "next_operation": actor["choice"]["next_operation"]}
        exhausted["receipt_digest"] = p82.digest(exhausted)
        child["exhausted_world_contact_frontiers"] = [*child.get("exhausted_world_contact_frontiers", []), exhausted]
        child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Test the corrected world-consequence policy on a fresh consequence catalog without sacrificing the global 40/40 floor."}
    return p82.seal(child), consequence


def preflight(parent, hidden_world, p82, runtime):
    private_public = [{key: copy.deepcopy(row[key]) for key in ("contact_id", "cutoff", "interface", "public_cases")} for row in hidden_world["future_contacts"]]
    with tempfile.TemporaryDirectory() as directory:
        seeded = materialize(parent, p82, Path(directory))
    remaining = parent["active_world_contact_frontier"]["remaining_contact_ids"][1:]
    erased = copy.deepcopy(parent)
    erased.pop("active_world_contact_frontier", None)
    binding_tampered = copy.deepcopy(parent)
    binding_tampered["active_world_consequence_policy_program"]["binding_digest"] = "0" * 64
    checks = {
        "source_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent),
        "private_world_matches_public_frontier": hidden_world["role"] == "continuation" and private_public == parent["active_world_contact_frontier"]["contacts"],
        "four_unconsumed_contacts": len(parent["active_world_contact_frontier"]["contact_ids"]) == len(parent["active_world_contact_frontier"]["remaining_contact_ids"]) == 4 and not parent["active_world_contact_frontier"]["consumed_contact_ids"],
        "subject_only_materialization": seeded is not None,
        "frontier_erasure_blocks_contact": next_operation(erased, p82) is None,
        "program_binding_tampering_blocks_contact": next_operation(binding_tampered, p82) is None,
        "premature_policy_reuse_rejects": not valid_choice({"opening_id": "too-early", "next_operation": "test-world-consequence-policy-reuse", "contact_id": None, "rationale": "fixture"}, remaining),
        "remaining_contact_accepts": valid_choice({"opening_id": "continue-next", "next_operation": "continue-world-contact", "contact_id": remaining[0], "rationale": "fixture"}, remaining),
        "exhaustion_requires_policy_reuse": valid_choice({"opening_id": "reuse-policy", "next_operation": "test-world-consequence-policy-reuse", "contact_id": None, "rationale": "fixture"}, []),
        "corrected_program_exact": parent["active_world_consequence_policy_program"]["policy_source_digest"] == POLICY_SOURCE_DIGEST and hashlib.sha256(parent["active_world_consequence_policy_program"]["policy_source"].encode()).hexdigest() == POLICY_SOURCE_DIGEST,
        "exact_floor_40": parent["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["pass_count"] == parent["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["case_count"] == 40,
        "g13_12_of_12": world.base.base.anchors()["pass_count"] == world.base.base.anchors()["case_count"] == 12,
        "g12_10_of_10": contact_world.base.anchors()["pass_count"] == contact_world.base.anchors()["case_count"] == 10,
        "g11_15_of_15": world.base.base.g11.evaluate(world.base.base.g11.g11)["pass_count"] == world.base.base.g11.evaluate(world.base.base.g11.g11)["case_count"] == 15,
        "checker_compiles": bool(compile(CHECK, "check_contact.py", "exec")),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "private_seed_digest": PRIVATE_SEED_DIGEST, "checks": checks}
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
    if args.private_seed_file is None:
        if args.preflight_only:
            hidden_world = {"role": None, "future_contacts": []}
        else:
            raise SystemExit("--private-seed-file is required")
    else:
        private_seed = args.private_seed_file.read_bytes()
        if hashlib.sha256(private_seed).hexdigest() != PRIVATE_SEED_DIGEST:
            raise SystemExit("private seed mismatch")
        hidden_world = next(row for row in world.derive_worlds(private_seed, heldout=True) if row["world_id"] == parent["active_world_contact_frontier"]["selected_world_id"])
    if args.preflight_only and args.private_seed_file is None:
        # Exact private/public agreement cannot be claimed without the retained
        # world, so normal preflight callers must supply it.
        raise SystemExit("--private-seed-file is required for preflight")
    report = preflight(parent, hidden_world, p82, runtime)
    if args.preflight_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0351 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", report)
    if not report["checks"]["passed"]:
        raise SystemExit("OT-0351 preflight failed")
    context = contact_world.policy_base.contact.base305.actor_context(runtime, core, base130, run / "actors", repo)
    subject = parent
    actors = []
    consequences = []
    for index in range(1, 5):
        actor = run_actor(context, run / f"cycle-{index:02d}", subject, hidden_world, p82, index)
        actors.append(actor)
        if not actor["accepted"]:
            break
        subject, consequence = compile_cycle(subject, actor, p82)
        consequences.append(consequence)
        write_json(run / f"subject-after-cycle-{index:02d}.json", subject)
    erased_program = copy.deepcopy(subject)
    erased_program.pop("active_world_consequence_policy_program", None)
    tampered_program = copy.deepcopy(subject)
    if "active_world_consequence_policy_program" in tampered_program:
        tampered_program["active_world_consequence_policy_program"]["policy_source"] += "\n# tampered\n"
    tampered_binding = copy.deepcopy(subject)
    if "active_world_consequence_policy_program" in tampered_binding:
        tampered_binding["active_world_consequence_policy_program"]["binding_digest"] = "0" * 64
    exhausted_frontiers = subject.get("exhausted_world_contact_frontiers", [])
    all_contacts_consumed = bool(
        len(consequences) == 4
        and exhausted_frontiers
        and len(exhausted_frontiers[-1].get("consumed_contact_ids", [])) == 4
    )
    checks = {
        "preflight_passed": report["checks"]["passed"],
        "four_fresh_actors_clean": len(actors) == 4 and all(actor["accepted"] for actor in actors),
        "all_public_3_of_3": len(actors) == 4 and all(actor["public_result"]["pass_count"] == actor["public_result"]["case_count"] == 3 for actor in actors),
        "all_hidden_5_of_5": len(actors) == 4 and all(actor["hidden_result"]["pass_count"] == actor["hidden_result"]["case_count"] == 5 for actor in actors),
        "actor_choices_drive_later_cycles": len(actors) == 4 and all(actors[index]["choice"]["contact_id"] == actors[index + 1]["active_contact_id"] for index in range(3)),
        "all_contacts_consumed": all_contacts_consumed,
        "corrected_program_byte_exact": subject.get("active_world_consequence_policy_program") == parent["active_world_consequence_policy_program"],
        "program_erasure_blocks_exhaustion_reopen": next_operation(erased_program, p82) is None,
        "program_tampering_blocks_exhaustion_reopen": next_operation(tampered_program, p82) is None,
        "program_binding_tampering_blocks_exhaustion_reopen": next_operation(tampered_binding, p82) is None,
        "exhaustion_reopens_corrected_policy": next_operation(subject, p82) == "test-world-consequence-policy-reuse",
        "exact_floor_40_preserved": subject["active_world_seeking_stake"] == parent["active_world_seeking_stake"],
        "open_conformant_subject": subject["continuation"]["status"] == "open" and runtime.identity_conforms(subject),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "preflight_receipt_digest": report["receipt_digest"], "actors": actors, "contact_consequences": consequences, "controls": {"program_erased_next_operation": next_operation(erased_program, p82), "program_tampered_next_operation": next_operation(tampered_program, p82), "program_binding_tampered_next_operation": next_operation(tampered_binding, p82)}, "checks": checks, "operational_recurrence_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": subject["continuation"]["status"] if checks["passed"] else "quarantined", "final_subject_digest": subject["artifact_digest"], "fresh_actor_count": len(actors)}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", subject)
    if checks["passed"]:
        write_json(run / "open-subject-after-corrected-policy-frontier-exhaustion.json", subject)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
