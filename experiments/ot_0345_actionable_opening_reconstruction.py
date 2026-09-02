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
BASE_PATH = ROOT / "ot_0344_heldout_policy_reuse.py"
BASE_SHA256 = "b5cfd368ac986e7cd0e1418b584de4c4f2e6c6e5b94962427db80a430edb08b0"
STRANDED_DIGEST = "a69c3ffb5ce92aab5ad89e62bce59bc3bc98ac49983668eabb499b6ea29753e1"
OT0344_RECEIPT = "29d0dd27457396e5e1d7d77f7e4f9c8123580f900bbc9f0347f594a7a3649425"
PUBLIC_ROWS_DIGEST = "0353a9ebbae2125d27464e694faf2ad08d4a8616be29fe09e3cabab1be5cfc70"
SELECTED_WORLD_ID = "world-7f06090437d7aa81"
CONSUMED_CONTACT_ID = "contact-31ad140ef6607b72"
ACTIVE_CONTACT_ID = "contact-5ddab6563ce8fa47"
PRIVATE_SEED_DIGEST = "f61bf1f790d415248c3e1799f702c5ac8d8e322973278d518acc8e65cc6d5b94"
AUTHORITY = "ot-0345-actionable-opening-reconstruction"


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


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0345_frozen_ot0344")
write_json = base.write_json


def object_path(store: Path, digest: str) -> Path:
    return store / "objects" / "sha256" / digest[:2] / digest


def load_artifact(repo: Path, store: Path, experiment: str, artifact: str):
    manifest = json.loads((repo / "evidence" / "manifests" / experiment / f"{artifact}.json").read_text())
    raw = object_path(store, manifest["sha256"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise RuntimeError(f"artifact mismatch: {experiment}/{artifact}")
    return json.loads(raw)


def setup(args):
    repo, store, _, p82, runtime, core, base130, _ = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0345").resolve()
    stranded = load_artifact(repo, store, "OT-0344", "open-subject-after-heldout-policy-reuse")
    aggregate = load_artifact(repo, store, "OT-0344", "heldout-policy-reuse-aggregate")
    return repo, store, run, p82, runtime, core, base130, stranded, aggregate


def public_spec(row):
    return {
        "contact_id": row["contact_id"],
        "cutoff": row["cutoff"],
        "interface": "source.py must export admits(value) -> bool",
        "public_cases": copy.deepcopy(row["public_cases"]),
    }


def bind_frontier(stranded, world, aggregate, p82):
    contacts = [public_spec(row) for row in world["contacts"]]
    ids = [row["contact_id"] for row in contacts]
    body = {
        "authority": AUTHORITY + "-public-contact-frontier",
        "source_subject_digest": stranded["artifact_digest"],
        "source_ot0344_receipt_digest": aggregate["receipt_digest"],
        "public_world_receipts_digest": aggregate["derived_world_receipts_digest"],
        "selected_world_id": aggregate["active_selection"]["selected_world_id"],
        "contacts": contacts,
        "consumed_contact_ids": [aggregate["selected_contact_binding"]["decision"]["contact_id"]],
        "remaining_contact_ids": [value for value in ids if value != aggregate["selected_contact_binding"]["decision"]["contact_id"]],
        "active_contact_id": aggregate["contact_actor"]["opening"]["contact_id"],
        "selection_authority": True,
        "world_authority": False,
        "outcome_authority": False,
    }
    return {**body, "binding_digest": p82.digest(body)}


def valid_frontier(subject, p82):
    frontier = subject.get("active_world_contact_frontier")
    if not isinstance(frontier, dict):
        return False
    required = {
        "authority", "source_subject_digest", "source_ot0344_receipt_digest",
        "public_world_receipts_digest", "selected_world_id", "contacts",
        "consumed_contact_ids", "remaining_contact_ids", "active_contact_id",
        "selection_authority", "world_authority", "outcome_authority",
        "binding_digest",
    }
    if set(frontier) != required:
        return False
    body = {key: value for key, value in frontier.items() if key != "binding_digest"}
    contacts = frontier["contacts"]
    if not isinstance(contacts, list) or not contacts:
        return False
    if any(set(row) != {"contact_id", "cutoff", "interface", "public_cases"} for row in contacts):
        return False
    if any(
        not isinstance(row["contact_id"], str)
        or not isinstance(row["cutoff"], int)
        or row["interface"] != "source.py must export admits(value) -> bool"
        or not isinstance(row["public_cases"], list)
        or not row["public_cases"]
        or any(
            set(case) != {"value", "expected"}
            or not isinstance(case["value"], int)
            or not isinstance(case["expected"], bool)
            for case in row["public_cases"]
        )
        for row in contacts
    ):
        return False
    if "hidden_cases" in json.dumps(contacts, sort_keys=True):
        return False
    ids = [row["contact_id"] for row in contacts]
    consumed = frontier["consumed_contact_ids"]
    remaining = frontier["remaining_contact_ids"]
    active = frontier["active_contact_id"]
    return bool(
        frontier["binding_digest"] == p82.digest(body)
        and frontier["source_subject_digest"] == STRANDED_DIGEST
        and frontier["source_ot0344_receipt_digest"] == OT0344_RECEIPT
        and frontier["public_world_receipts_digest"] == PUBLIC_ROWS_DIGEST
        and frontier["selected_world_id"] == SELECTED_WORLD_ID
        and len(ids) == len(set(ids)) == 4
        and set(consumed).isdisjoint(remaining)
        and set(consumed) | set(remaining) == set(ids)
        and active in remaining
        and active not in consumed
        and active in subject.get("continuation", {}).get("next_opening", "")
        and frontier["selection_authority"] is True
        and frontier["world_authority"] is False
        and frontier["outcome_authority"] is False
    )


def materialize(subject, p82, root: Path):
    if not valid_frontier(subject, p82):
        return None
    frontier = subject["active_world_contact_frontier"]
    active = next(row for row in frontier["contacts"] if row["contact_id"] == frontier["active_contact_id"])
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "contact.json", {
        "frontier_binding_digest": frontier["binding_digest"],
        "contact_id": active["contact_id"],
        "public_cases": active["public_cases"],
        "remaining_contact_ids": [value for value in frontier["remaining_contact_ids"] if value != active["contact_id"]],
        "interface": active["interface"],
    })
    (seed / "source.py").write_text(base.SOURCE_TEMPLATE.format(cutoff=active["cutoff"]))
    write_json(seed / "next-opening.json", {"opening_id": "replace-me", "contact_id": "replace-me", "rationale": "Replace after repairing the active contact."})
    (seed / "check_contact.py").write_text(base.CHECK_CONTACT)
    immutable = ["contact.json", "check_contact.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["source.py", "next-opening.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue from the subject-carried active contact. Repair source.py so admits(value) satisfies every public case, then choose one different remaining contact as the next opening in next-opening.json. Run python3 check_contact.py, inspect the exact diff, and return the required report. Hidden cases, private derivation state, controls, evaluator, and admission result are unavailable. Edit no other file.\n")
    return seed


def can_materialize(subject, p82):
    with tempfile.TemporaryDirectory() as directory:
        seed = materialize(subject, p82, Path(directory))
        if seed is None:
            return False
        corpus = "\n".join(path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file())
        return (seed / "source.py").is_file() and (seed / "contact.json").is_file() and "hidden_cases" not in corpus


def fixture_subject(p82):
    contacts = [{"contact_id": f"contact-{index}", "cutoff": index + 2, "interface": "source.py must export admits(value) -> bool", "public_cases": [{"value": index + 2, "expected": True}]} for index in range(4)]
    body = {
        "authority": AUTHORITY + "-public-contact-frontier",
        "source_subject_digest": STRANDED_DIGEST,
        "source_ot0344_receipt_digest": OT0344_RECEIPT,
        "public_world_receipts_digest": PUBLIC_ROWS_DIGEST,
        "selected_world_id": SELECTED_WORLD_ID,
        "contacts": contacts,
        "consumed_contact_ids": ["contact-0"],
        "remaining_contact_ids": ["contact-1", "contact-2", "contact-3"],
        "active_contact_id": "contact-1",
        "selection_authority": True,
        "world_authority": False,
        "outcome_authority": False,
    }
    frontier = {**body, "binding_digest": p82.digest(body)}
    return {"continuation": {"status": "open", "next_opening": "Continue through contact-1."}, "active_world_contact_frontier": frontier}


def anchors(p82):
    good = fixture_subject(p82)
    cases = [{"case_id": "complete", "subject": good, "expected": True}]
    for case_id, mutate in [
        ("missing-frontier", lambda value: value.pop("active_world_contact_frontier")),
        ("missing-spec", lambda value: value["active_world_contact_frontier"]["contacts"].pop()),
        ("duplicate-spec", lambda value: value["active_world_contact_frontier"]["contacts"].__setitem__(3, copy.deepcopy(value["active_world_contact_frontier"]["contacts"][2]))),
        ("consumed-active", lambda value: value["active_world_contact_frontier"].__setitem__("active_contact_id", "contact-0")),
        ("opening-mismatch", lambda value: value["continuation"].__setitem__("next_opening", "Continue elsewhere.")),
        ("altered-ancestry", lambda value: value["active_world_contact_frontier"].__setitem__("source_subject_digest", "0" * 64)),
        ("hidden-leak", lambda value: value["active_world_contact_frontier"]["contacts"][1].__setitem__("hidden_cases", [])),
    ]:
        candidate = copy.deepcopy(good)
        mutate(candidate)
        frontier = candidate.get("active_world_contact_frontier")
        if frontier is not None:
            body = {key: value for key, value in frontier.items() if key != "binding_digest"}
            frontier["binding_digest"] = p82.digest(body)
        cases.append({"case_id": case_id, "subject": candidate, "expected": False})
    rows = []
    for case in cases:
        observed = can_materialize(case["subject"], p82)
        rows.append({"case_id": case["case_id"], "expected": case["expected"], "observed": observed, "passed": observed == case["expected"]})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "rows": rows}


def preflight(stranded, aggregate, p82):
    challenger = anchors(p82)
    g12 = base.base.anchors()
    g11 = base.base.g11.evaluate(base.base.g11.g11)
    checks = {
        "source_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_ot0344_inputs": stranded["artifact_digest"] == STRANDED_DIGEST and aggregate["receipt_digest"] == OT0344_RECEIPT,
        "incumbent_passed_nonactionable_child": aggregate["checks"]["open_actor_authored_successor"] is True and aggregate["checks"]["passed"] is True,
        "direct_audit_finds_missing_carrier": ACTIVE_CONTACT_ID in stranded["continuation"]["next_opening"] and "public_cases" not in json.dumps(stranded) and not can_materialize(stranded, p82),
        "challenger_anchors_8_of_8": challenger["pass_count"] == challenger["case_count"] == 8,
        "g12_anchors_10_of_10": g12["pass_count"] == g12["case_count"] == 10,
        "g11_anchors_15_of_15": g11["pass_count"] == g11["case_count"] == 15,
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": stranded["artifact_digest"], "source_ot0344_receipt_digest": aggregate["receipt_digest"], "materialization_anchor": challenger, "g12_anchor": g12, "g11_anchor": g11, "checks": checks}
    return {**body, "receipt_digest": p82.digest(body)}


def reconstruct(stranded, aggregate, seed: bytes, p82):
    if hashlib.sha256(seed).hexdigest() != PRIVATE_SEED_DIGEST:
        raise RuntimeError("private seed does not match OT-0344")
    worlds = base.derive_worlds(seed)
    rows = base.public_worlds(worlds)
    if p82.digest(rows) != PUBLIC_ROWS_DIGEST or aggregate["derived_world_receipts_digest"] != PUBLIC_ROWS_DIGEST:
        raise RuntimeError("public world reconstruction mismatch")
    world = next(row for row in worlds if row["world_id"] == SELECTED_WORLD_ID)
    frontier = bind_frontier(stranded, world, aggregate, p82)
    child = copy.deepcopy(stranded)
    child.pop("artifact_digest", None)
    child["world_contact_frontiers"] = [*child.get("world_contact_frontiers", []), frontier]
    child["active_world_contact_frontier"] = frontier
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Continue the selected world through contact {frontier['active_contact_id']}."}
    return p82.seal(child), world


def run_actor(context, root: Path, subject, world, p82):
    label = "actionable-opening-fresh-successor"
    seed = materialize(subject, p82, root)
    if seed is None:
        raise RuntimeError("corrected subject did not materialize")
    output, audit0, workspace, _ = context.run_actor(label, seed, base.CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    trace = (context.evidence(label) / "events.jsonl").read_text()
    frontier = subject["active_world_contact_frontier"]
    world_contact = next(row for row in world["contacts"] if row["contact_id"] == frontier["active_contact_id"])
    projected = next(row for row in frontier["contacts"] if row["contact_id"] == frontier["active_contact_id"])
    try:
        opening = json.loads((workspace / "next-opening.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        public = base.evaluate_source(workspace / "source.py", projected["public_cases"])
        hidden = base.evaluate_source(workspace / "source.py", world_contact["hidden_cases"])
        checker_invoked = base.named_command_succeeded(trace, "check_contact.py")
        public_projection_exact = projected == public_spec(world_contact)
        semantic = bool(immutable_ok and public_projection_exact and public["pass_count"] == public["case_count"] == 3 and hidden["pass_count"] == hidden["case_count"] == 5 and checker_invoked and opening["contact_id"] in [value for value in frontier["remaining_contact_ids"] if value != frontier["active_contact_id"]] and base.output_valid(output, "realize-selected-contact", ["source.py", "next-opening.json"]))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        opening = None
        public = hidden = None
        immutable_ok = checker_invoked = public_projection_exact = semantic = False
    audit = context.audit_actor(label, output, audit0, semantic, ["source.py", "next-opening.json"])
    certificate = base.policy_base.contact.base.certify_g11(context, label, audit)
    return {"accepted": bool(semantic and certificate["challenger_accepted"]), "opening": opening, "public_result": public, "hidden_result": hidden, "output": output, "audit": audit, "g11": certificate, "workspace_evaluation": {"immutable_ok": immutable_ok, "public_projection_exact": public_projection_exact, "checker_invoked": checker_invoked, "semantic": semantic}}


def compile_successor(subject, actor, p82):
    old = subject["active_world_contact_frontier"]
    body = {key: copy.deepcopy(value) for key, value in old.items() if key != "binding_digest"}
    completed = body["active_contact_id"]
    body["consumed_contact_ids"] = [*body["consumed_contact_ids"], completed]
    body["remaining_contact_ids"] = [value for value in body["remaining_contact_ids"] if value != completed]
    body["active_contact_id"] = actor["opening"]["contact_id"]
    frontier = {**body, "binding_digest": p82.digest(body)}
    receipt_body = {"authority": AUTHORITY + "-reopened-contact-consequence", "source_frontier_binding_digest": old["binding_digest"], "actor_patch_digest": actor["audit"]["patch_digest"], "public_result": actor["public_result"], "hidden_result": actor["hidden_result"], "next_opening": actor["opening"], "world_authority": True, "outcome_authority": True, "scoring_authority": True, "actor_authority": False}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["world_contact_frontiers"] = [*child.get("world_contact_frontiers", []), frontier]
    child["active_world_contact_frontier"] = frontier
    child["completed_contact_consequences"] = [*child.get("completed_contact_consequences", []), receipt]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Continue the selected world through contact {frontier['active_contact_id']}."}
    return p82.seal(child), receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--private-seed-file", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, core, base130, stranded, aggregate44 = setup(args)
    report = preflight(stranded, aggregate44, p82)
    if args.preflight_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0345 evidence")
    if args.private_seed_file is None:
        raise SystemExit("--private-seed-file is required for exact OT-0344 reconstruction")
    seed = args.private_seed_file.read_bytes()
    corrected, world = reconstruct(stranded, aggregate44, seed, p82)
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", report)
    write_json(run / "corrected-subject-before-actor.json", corrected)
    if not report["checks"]["passed"] or not can_materialize(corrected, p82):
        raise SystemExit("OT-0345 preflight or reconstruction failed")
    context = base.policy_base.contact.base305.actor_context(runtime, core, base130, run / "actors", repo)
    actor = run_actor(context, run / "actor", corrected, world, p82)
    child, consequence = compile_successor(corrected, actor, p82) if actor["accepted"] else (corrected, None)
    write_json(run / "active-subject-before-controls.json", child)
    erased = copy.deepcopy(corrected)
    erased.pop("active_world_contact_frontier", None)
    corrected_interpretation = {
        "source_ot0344_receipt_digest": aggregate44["receipt_digest"],
        "completed_policy_selection_effect_valid": True,
        "completed_contact_transition_valid": True,
        "ot0344_inherited_remaining_openings_valid": False,
        "ot0344_open_subject_valid": False,
        "ot0344_overall_causal_promotion_valid": False,
        "historical_subject_disposition": "lost-before-exact-operational-rescue",
    }
    checks = {
        "preflight_passed": report["checks"]["passed"],
        "exact_reconstruction_materializes": can_materialize(corrected, p82),
        "public_frontier_has_four_no_hidden": len(corrected["active_world_contact_frontier"]["contacts"]) == 4 and "hidden_cases" not in json.dumps(corrected["active_world_contact_frontier"]),
        "fresh_actor_clean": actor["accepted"],
        "fresh_actor_public_3_of_3": actor["public_result"]["pass_count"] == actor["public_result"]["case_count"] == 3,
        "fresh_actor_hidden_5_of_5": actor["hidden_result"]["pass_count"] == actor["hidden_result"]["case_count"] == 5,
        "active_subject_sealed_before_controls": (run / "active-subject-before-controls.json").exists(),
        "id_only_incumbent_rejects": not can_materialize(stranded, p82),
        "frontier_erasure_rejects": not can_materialize(erased, p82),
        "successor_reopens_without_private_state": can_materialize(child, p82),
        "exact_floor_40_preserved": child["active_world_seeking_stake"] == stranded["active_world_seeking_stake"] and child["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["pass_count"] == 40,
        "historical_overclaim_withdrawn": not corrected_interpretation["ot0344_open_subject_valid"] and not corrected_interpretation["ot0344_overall_causal_promotion_valid"],
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "from_gate": "canonical-id-open", "to_gate": "subject-only-workspace-materialization", "source_subject_digest": stranded["artifact_digest"], "source_ot0344_receipt_digest": aggregate44["receipt_digest"], "preflight_receipt_digest": report["receipt_digest"], "corrected_ot0344_interpretation": corrected_interpretation, "frontier_binding": corrected["active_world_contact_frontier"], "actor": actor, "contact_consequence_receipt": consequence, "controls": {"id_only_materializes": can_materialize(stranded, p82), "frontier_erased_materializes": can_materialize(erased, p82)}, "checks": checks, "operational_rescue_passed": checks["passed"], "observer_disposition": "corrected-operational-only" if checks["passed"] else "rejected", "subject_disposition": child["continuation"]["status"] if checks["passed"] else "lost", "final_subject_digest": child["artifact_digest"], "fresh_actor_count": 1}
    result = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", child)
    if checks["passed"]:
        write_json(run / "open-subject-after-actionable-opening-reconstruction.json", child)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
