from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0343_exact_prefix_command_attribution.py"
BASE_SHA256 = "9a7d6e2fd322436d07897fd7a810cfed4993c65b9ea1afddeea431234979d774"
PARENT_DIGEST = "2b0d835e514c2a3df2d2d1d5767b26b288ec8d0948106c8525da7bc396a05f68"
POLICY_BINDING = "48da8682f5b9cfdef92182b3aaf9aaac1864137a18088e460f231cab516b11a2"
STAKE_BINDING = "25f70cef4440c22807c352edc009054e0de3349a1439638eb7cfe1c72971396a"
ARCHITECTURE_BINDING = "f2ca5b13c2500b19771834ff3cc31131e8f467dad231321917905b196707a9f6"
AUTHORITY = "ot-0344-heldout-policy-reuse"
SELECTION_SCHEMA = REPO / "spec/ot-0344-policy-reuse-selection.schema.json"
CONTACT_SCHEMA = REPO / "spec/ot-0344-policy-reuse-contact.schema.json"
FEATURES = ("branch_nodes", "call_nodes", "comparison_nodes", "loop_nodes", "source_bytes")


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


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0344_frozen_ot0343")
write_json = base.write_json
policy_base = base.base.base.contact_base


def object_path(store: Path, digest: str) -> Path:
    return store / "objects" / "sha256" / digest[:2] / digest


def load_parent(repo: Path, store: Path):
    manifest = json.loads((repo / "evidence/manifests/OT-0343/open-subject-after-exact-prefix-reconstruction.json").read_text())
    raw = object_path(store, manifest["sha256"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise RuntimeError("OT-0343 parent object does not match its manifest")
    return json.loads(raw)


def setup(args):
    values, _, *_ = base.setup(args)
    repo, store, _, p82, runtime = values[:5]
    run = (args.evidence_root or store / "runs/OT-0344").resolve()
    return repo, store, run, p82, runtime, values[-2], values[-1], load_parent(repo, store)


def opaque(seed: bytes, label: str) -> str:
    return hashlib.sha256(seed + label.encode()).hexdigest()[:16]


ROLE_TEMPLATES = {
    "descriptor": {
        "features": {"branch_nodes": 0, "call_nodes": 4, "comparison_nodes": 2, "loop_nodes": 0, "source_bytes": 280},
        "contact_count": 2,
        "match_basis_points": 8333,
    },
    "middle": {
        "features": {"branch_nodes": 1, "call_nodes": 1, "comparison_nodes": 2, "loop_nodes": 0, "source_bytes": 245},
        "contact_count": 3,
        "match_basis_points": 6666,
    },
    "expansion": {
        "features": {"branch_nodes": 0, "call_nodes": 0, "comparison_nodes": 2, "loop_nodes": 0, "source_bytes": 220},
        "contact_count": 4,
        "match_basis_points": 5000,
    },
}


def contact(seed: bytes, role: str, index: int):
    cutoff = 3 + int(opaque(seed, f"{role}-cutoff-{index}")[:2], 16) % 17
    contact_id = f"contact-{opaque(seed, f'{role}-contact-{index}')}"
    public_values = [cutoff - 1, cutoff, cutoff + 1]
    hidden_values = [cutoff - 3, cutoff - 2, cutoff, cutoff + 2, cutoff + 4]
    expected = lambda value: value >= cutoff
    return {
        "contact_id": contact_id,
        "cutoff": cutoff,
        "public_cases": [{"value": value, "expected": expected(value)} for value in public_values],
        "hidden_cases": [{"value": value, "expected": expected(value)} for value in hidden_values],
    }


def derive_worlds(seed: bytes):
    if len(seed) != 32:
        raise ValueError("private seed must contain exactly 32 bytes")
    worlds = []
    for role, template in ROLE_TEMPLATES.items():
        world_id = f"world-{opaque(seed, role + '-world')}"
        contacts = [contact(seed, role, index) for index in range(template["contact_count"])]
        worlds.append({
            "world_id": world_id,
            "role": role,
            "features": copy.deepcopy(template["features"]),
            "contacts": contacts,
            "metrics": {
                "viable_contact_count": len(contacts),
                "mean_match_basis_points": template["match_basis_points"],
                "minimum_match_basis_points": template["match_basis_points"],
            },
            "admissible": True,
            "floor_preserved": True,
        })
    random.Random(int.from_bytes(hashlib.sha256(seed + b"order").digest()[:8], "big")).shuffle(worlds)
    return worlds


def public_worlds(worlds):
    return [{
        "world_id": world["world_id"],
        "features": world["features"],
        "metrics": world["metrics"],
        "admissible": world["admissible"],
        "floor_preserved": world["floor_preserved"],
        "contact_ids": [row["contact_id"] for row in world["contacts"]],
    } for world in worlds]


def descriptor_choose(stake, rows):
    weights = stake["stake"]["weights"]
    ranked = []
    for row in rows:
        score = sum(weights[key] * row["features"][key] for key in FEATURES)
        ranked.append((score, row["world_id"]))
    ranked.sort(reverse=True)
    gap = ranked[0][0] - ranked[1][0]
    return {"selected_world_id": ranked[0][1] if gap >= stake["stake"]["minimum_score_gap"] else None, "score_gap": gap, "ranking": ranked}


def policy_choose(policy, rows):
    return policy_base.choose(policy, rows)


def select_with_architecture(parent, rows, *, erase_policy=False, policy_override=None):
    if not erase_policy:
        policy = policy_override or parent["active_world_consequence_policy"]["policy"]
        selected = policy_choose(policy, rows)
        if selected["supported"]:
            return {"stage": "post-contact-policy", **selected}
    return {"stage": "pre-contact-descriptor", **descriptor_choose(parent["active_world_seeking_stake"], rows)}


PIPELINE = '''import json\nfrom pathlib import Path\np=json.loads(Path("subject-selection.json").read_text()); rows=json.loads(Path("world-consequence-receipts.json").read_text()); policy=p["policy"]\ndef valid(x): return x.get("admissible") is True and x.get("floor_preserved") is True\ndef key(row): return tuple(row["metrics"][name] * (1 if policy["directions"][name]=="higher" else -1) for name in policy["priority_order"])\nadmitted=[row for row in rows if valid(row)]\nbest=max(key(row) for row in admitted); winners=[row for row in admitted if key(row)==best]\nresult={"stage":"post-contact-policy","selected_world_id":winners[0]["world_id"] if len(winners)==1 else None,"available_contact_ids":winners[0]["contact_ids"] if len(winners)==1 else [],"supported":len(winners)==1}\nprint(json.dumps(result,sort_keys=True))\n'''


CHECK_SELECTION = '''import json,re,subprocess,sys\nfrom pathlib import Path\nd=json.loads(Path("next-contact.json").read_text()); result=json.loads(subprocess.check_output([sys.executable,"continue_pipeline.py"],text=True)); ok=isinstance(d,dict) and set(d)=={"decision_id","selected_world_id","contact_id","rationale"} and isinstance(d["decision_id"],str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}",d["decision_id"])) and d["selected_world_id"]==result["selected_world_id"] and d["contact_id"] in result["available_contact_ids"] and isinstance(d["rationale"],str) and 1<=len(d["rationale"])<=2000; print(json.dumps({"valid":ok,"selected_world_id":result["selected_world_id"],"contact_id":d.get("contact_id")},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''


def seed_selection(root: Path, parent, rows):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "subject-selection.json", {
        "source_subject_digest": parent["artifact_digest"],
        "architecture_binding_digest": parent["active_selection_architecture"]["binding_digest"],
        "policy_binding_digest": parent["active_world_consequence_policy"]["binding_digest"],
        "stake_binding_digest": parent["active_world_seeking_stake"]["binding_digest"],
        "policy": parent["active_world_consequence_policy"]["policy"],
        "next_operation": parent["active_selection_architecture"]["next_operation"],
    })
    write_json(seed / "world-consequence-receipts.json", rows)
    write_json(seed / "next-contact.json", {"decision_id": "replace-me", "selected_world_id": "replace-me", "contact_id": "replace-me", "rationale": "Replace after running the inherited selector."})
    (seed / "continue_pipeline.py").write_text(PIPELINE)
    (seed / "check_selection.py").write_text(CHECK_SELECTION)
    immutable = ["subject-selection.json", "world-consequence-receipts.json", "continue_pipeline.py", "check_selection.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["next-contact.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue the exact subject's requested policy-reuse test. Run python3 continue_pipeline.py before editing. Its selected world is authoritative under the inherited two-stage architecture. Choose any one available contact in that selected world and record it in next-contact.json. Run python3 check_selection.py, inspect the exact diff, and return the required report. The private derivation seed, role labels, hidden contact cases, controls, evaluator, and expected ids are unavailable. Edit no other file.\n")
    return seed


def output_valid(output, action, files):
    return bool(isinstance(output, dict) and set(output) == {"action", "files_changed", "note"} and output.get("action") == action and sorted(output.get("files_changed", [])) == sorted(files) and isinstance(output.get("note"), str))


def named_command_succeeded(trace: str, name: str) -> bool:
    for line in trace.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item", {})
        if (
            event.get("type") == "item.completed"
            and item.get("type") == "command_execution"
            and name in item.get("command", "")
            and item.get("exit_code") == 0
        ):
            return True
    return False


def run_selection_actor(context, root: Path, parent, rows):
    label = "heldout-policy-reuse-selector"
    seed = seed_selection(root, parent, rows)
    output, audit0, workspace, _ = context.run_actor(label, seed, SELECTION_SCHEMA, (seed / "README.md").read_text().strip())
    trace = (context.evidence(label) / "events.jsonl").read_text()
    expected = select_with_architecture(parent, rows)
    try:
        decision = json.loads((workspace / "next-contact.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        checker = subprocess.run([sys.executable, "check_selection.py"], cwd=workspace, capture_output=True, text=True, timeout=5, check=False)
        pipeline_invoked = named_command_succeeded(trace, "continue_pipeline.py")
        checker_invoked = named_command_succeeded(trace, "check_selection.py")
        semantic = bool(immutable_ok and checker.returncode == 0 and pipeline_invoked and checker_invoked and decision["selected_world_id"] == expected["selected_world_id"] and decision["contact_id"] in next(row["contact_ids"] for row in rows if row["world_id"] == expected["selected_world_id"]) and output_valid(output, "select-policy-world-contact", ["next-contact.json"]))
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        decision = None
        immutable_ok = pipeline_invoked = checker_invoked = semantic = False
    audit = context.audit_actor(label, output, audit0, semantic, ["next-contact.json"])
    certificate = policy_base.contact.base.certify_g11(context, label, audit)
    return {"accepted": bool(semantic and certificate["challenger_accepted"]), "decision": decision, "expected_selection": expected, "output": output, "audit": audit, "g11": certificate, "workspace_evaluation": {"immutable_ok": immutable_ok, "pipeline_invoked": pipeline_invoked, "checker_invoked": checker_invoked, "semantic": semantic}}


SOURCE_TEMPLATE = '''def admits(value):\n    return value > {cutoff}\n'''
CHECK_CONTACT = '''import importlib.util,json,re\nfrom pathlib import Path\nspec=importlib.util.spec_from_file_location("candidate",Path("source.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); c=json.loads(Path("contact.json").read_text()); n=json.loads(Path("next-opening.json").read_text()); rows=[{"value":row["value"],"expected":row["expected"],"observed":m.admits(row["value"]),"passed":m.admits(row["value"])==row["expected"]} for row in c["public_cases"]]; ok=all(row["passed"] for row in rows) and isinstance(n,dict) and set(n)=={"opening_id","contact_id","rationale"} and isinstance(n["opening_id"],str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}",n["opening_id"])) and n["contact_id"] in c["remaining_contact_ids"] and isinstance(n["rationale"],str) and 1<=len(n["rationale"])<=2000; print(json.dumps({"valid":ok,"rows":rows,"next_contact_id":n.get("contact_id")},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''


def seed_contact(root: Path, selection, world):
    seed = root / "seed"
    seed.mkdir(parents=True)
    chosen = next(row for row in world["contacts"] if row["contact_id"] == selection["contact_id"])
    remaining = [row["contact_id"] for row in world["contacts"] if row["contact_id"] != chosen["contact_id"]]
    write_json(seed / "contact.json", {"binding": selection, "contact_id": chosen["contact_id"], "public_cases": chosen["public_cases"], "remaining_contact_ids": remaining, "interface": "source.py must export admits(value) -> bool"})
    (seed / "source.py").write_text(SOURCE_TEMPLATE.format(cutoff=chosen["cutoff"]))
    write_json(seed / "next-opening.json", {"opening_id": "replace-me", "contact_id": "replace-me", "rationale": "Replace after repairing the selected contact."})
    (seed / "check_contact.py").write_text(CHECK_CONTACT)
    immutable = ["contact.json", "check_contact.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["source.py", "next-opening.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue from the selected contact. Repair source.py so admits(value) satisfies every public case, then choose one different remaining contact as the next opening in next-opening.json. Run python3 check_contact.py, inspect the exact diff, and return the required report. Hidden cases, the derivation seed, sibling worlds, controls, evaluator, and admission result are unavailable. Edit no other file.\n")
    return seed, chosen


def evaluate_source(path: Path, cases):
    spec = importlib.util.spec_from_file_location("ot0344_candidate", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    rows = [{**case, "observed": module.admits(case["value"]), "passed": module.admits(case["value"]) == case["expected"]} for case in cases]
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "rows": rows}


def run_contact_actor(context, root: Path, selection, world):
    label = "heldout-policy-selected-contact-successor"
    seed, chosen = seed_contact(root, selection, world)
    output, audit0, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    trace = (context.evidence(label) / "events.jsonl").read_text()
    try:
        opening = json.loads((workspace / "next-opening.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        public = evaluate_source(workspace / "source.py", chosen["public_cases"])
        hidden = evaluate_source(workspace / "source.py", chosen["hidden_cases"])
        checker_invoked = named_command_succeeded(trace, "check_contact.py")
        remaining = [row["contact_id"] for row in world["contacts"] if row["contact_id"] != chosen["contact_id"]]
        semantic = bool(immutable_ok and public["pass_count"] == public["case_count"] and hidden["pass_count"] == hidden["case_count"] and checker_invoked and opening["contact_id"] in remaining and output_valid(output, "realize-selected-contact", ["source.py", "next-opening.json"]))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        opening = None
        public = hidden = None
        immutable_ok = checker_invoked = semantic = False
    audit = context.audit_actor(label, output, audit0, semantic, ["source.py", "next-opening.json"])
    certificate = policy_base.contact.base.certify_g11(context, label, audit)
    return {"accepted": bool(semantic and certificate["challenger_accepted"]), "opening": opening, "public_result": public, "hidden_result": hidden, "output": output, "audit": audit, "g11": certificate, "workspace_evaluation": {"immutable_ok": immutable_ok, "checker_invoked": checker_invoked, "semantic": semantic}}


def preflight(parent, p82, runtime):
    anchors = []
    for index in range(5):
        seed = hashlib.sha256(f"ot0344-anchor-{index}".encode()).digest()
        worlds = derive_worlds(seed)
        rows = public_worlds(worlds)
        active = select_with_architecture(parent, rows)
        erased = select_with_architecture(parent, rows, erase_policy=True)
        roles = {world["world_id"]: world["role"] for world in worlds}
        anchors.append({"case_id": f"derived-{index}", "active_role": roles[active["selected_world_id"]], "erased_role": roles[erased["selected_world_id"]], "active_count": len(next(row["contact_ids"] for row in rows if row["world_id"] == active["selected_world_id"])), "erased_count": len(next(row["contact_ids"] for row in rows if row["world_id"] == erased["selected_world_id"])), "passed": roles[active["selected_world_id"]] == "expansion" and roles[erased["selected_world_id"]] == "descriptor"})
    rows = public_worlds(derive_worlds(hashlib.sha256(b"ot0344-counterfeit").digest()))
    inverse = copy.deepcopy(parent["active_world_consequence_policy"]["policy"])
    inverse["directions"]["viable_contact_count"] = "lower"
    active = select_with_architecture(parent, rows)
    reversed_choice = select_with_architecture(parent, rows, policy_override=inverse)
    regressive = copy.deepcopy(rows)
    regressive.append({"world_id": "anchor-regressive", "features": {key: 0 for key in FEATURES}, "metrics": {"viable_contact_count": 99, "mean_match_basis_points": 9999, "minimum_match_basis_points": 9999}, "admissible": False, "floor_preserved": False, "contact_ids": ["forbidden"]})
    checks = {
        "source_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "exact_subject_requested_operation": parent["active_selection_architecture"]["next_operation"] == "test-world-consequence-policy-reuse" and "fresh consequence catalog" in parent["continuation"]["next_opening"],
        "exact_bindings": parent["active_selection_architecture"]["binding_digest"] == ARCHITECTURE_BINDING and parent["active_world_consequence_policy"]["binding_digest"] == POLICY_BINDING and parent["active_world_seeking_stake"]["binding_digest"] == STAKE_BINDING,
        "five_derived_anchors": len(anchors) == 5 and all(row["passed"] and row["active_count"] == 4 and row["erased_count"] == 2 for row in anchors),
        "reversed_policy_changes_selection": reversed_choice["selected_world_id"] != active["selected_world_id"],
        "regressive_high_count_rejected": select_with_architecture(parent, regressive)["selected_world_id"] == active["selected_world_id"],
        "schemas_explicit": all(set(json.loads(path.read_text())["required"]) == {"action", "files_changed", "note"} for path in (SELECTION_SCHEMA, CONTACT_SCHEMA)),
        "actor_programs_compile": all(compile(source, name, "exec") for name, source in (("continue_pipeline.py", PIPELINE), ("check_selection.py", CHECK_SELECTION), ("check_contact.py", CHECK_CONTACT))),
        "floor_still_40": parent["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["pass_count"] == parent["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["case_count"] == 40,
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "derived_anchor_rows": anchors, "checks": checks}
    return {**body, "receipt_digest": p82.digest(body)}


def compile_subject(parent, worlds, selection_actor, contact_actor, p82):
    rows = public_worlds(worlds)
    selected_world = next(world for world in worlds if world["world_id"] == selection_actor["decision"]["selected_world_id"])
    binding_body = {"authority": AUTHORITY + "-selected-contact-binding", "source_subject_digest": parent["artifact_digest"], "architecture_binding_digest": parent["active_selection_architecture"]["binding_digest"], "policy_binding_digest": parent["active_world_consequence_policy"]["binding_digest"], "world_receipts_digest": p82.digest(rows), "actor_patch_digest": selection_actor["audit"]["patch_digest"], "decision": selection_actor["decision"], "selection_authority": True, "world_authority": False, "outcome_authority": False}
    binding = {**binding_body, "binding_digest": p82.digest(binding_body)}
    correction_body = {"authority": AUTHORITY + "-contact-consequence", "source_contact_binding_digest": binding["binding_digest"], "actor_patch_digest": contact_actor["audit"]["patch_digest"], "public_result": contact_actor["public_result"], "hidden_result": contact_actor["hidden_result"], "next_opening": contact_actor["opening"], "world_authority": True, "outcome_authority": True, "scoring_authority": True, "actor_authority": False}
    correction = {**correction_body, "receipt_digest": p82.digest(correction_body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["world_policy_reuse_receipts"] = [*child.get("world_policy_reuse_receipts", []), {"world_receipts_digest": p82.digest(rows), "selection": selection_actor["expected_selection"], "selected_contact_binding_digest": binding["binding_digest"]}]
    child["completed_contact_consequences"] = [*child.get("completed_contact_consequences", []), correction]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Continue the selected world through contact {contact_actor['opening']['contact_id']}."}
    child["unresolved"] = "Can repeated consequence-policy reuse continue widening reachable, non-regressive contact across fresh worlds?"
    return p82.seal(child), binding, correction, selected_world


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
        raise SystemExit("preserve existing OT-0344 evidence")
    if args.private_seed_file is None:
        raise SystemExit("--private-seed-file is required for the one live derivation")
    seed = args.private_seed_file.read_bytes()
    worlds = derive_worlds(seed)
    rows = public_worlds(worlds)
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", report)
    write_json(run / "derived-world-public-receipts.json", rows)
    if not report["checks"]["passed"]:
        raise SystemExit("OT-0344 preflight failed")
    context = policy_base.contact.base305.actor_context(runtime, core, base130, run / "actors", repo)
    selection_actor = run_selection_actor(context, run / "selection", parent, rows)
    if not selection_actor["accepted"]:
        contact_actor = None
        child = parent
        binding = correction = selected_world = None
    else:
        selected_world = next(world for world in worlds if world["world_id"] == selection_actor["decision"]["selected_world_id"])
        contact_actor = run_contact_actor(context, run / "contact", selection_actor["decision"], selected_world)
        child, binding, correction, selected_world = compile_subject(parent, worlds, selection_actor, contact_actor, p82) if contact_actor["accepted"] else (parent, None, None, selected_world)
    write_json(run / "active-subject-before-controls.json", child)
    erased = select_with_architecture(parent, rows, erase_policy=True)
    inverse = copy.deepcopy(parent["active_world_consequence_policy"]["policy"])
    inverse["directions"]["viable_contact_count"] = "lower"
    reversed_choice = select_with_architecture(parent, rows, policy_override=inverse)
    active = selection_actor["expected_selection"] if selection_actor["accepted"] else None
    active_count = len(selected_world["contacts"]) if selected_world else 0
    erased_count = len(next(world["contacts"] for world in worlds if world["world_id"] == erased["selected_world_id"]))
    checks = {
        "preflight_passed": report["checks"]["passed"],
        "one_private_derivation": len(seed) == 32,
        "selection_actor_clean": selection_actor["accepted"],
        "active_policy_selects_four": bool(active and active["stage"] == "post-contact-policy" and active_count == 4),
        "contact_actor_clean": bool(contact_actor and contact_actor["accepted"]),
        "selected_contact_hidden_passes": bool(contact_actor and contact_actor["hidden_result"]["pass_count"] == contact_actor["hidden_result"]["case_count"] == 5),
        "active_subject_sealed_before_controls": child["artifact_digest"] != parent["artifact_digest"] and (run / "active-subject-before-controls.json").exists(),
        "exact_floor_preserved": child.get("active_world_seeking_stake") == parent["active_world_seeking_stake"] and parent["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["pass_count"] == 40,
        "policy_erasure_selects_two": erased["stage"] == "pre-contact-descriptor" and erased_count == 2 and erased["selected_world_id"] != active["selected_world_id"],
        "reversed_policy_changes_selection": reversed_choice["selected_world_id"] != active["selected_world_id"],
        "three_vs_one_remaining_openings": active_count - 1 == 3 and erased_count - 1 == 1,
        "open_actor_authored_successor": child["continuation"]["status"] == "open" and contact_actor and contact_actor["opening"]["contact_id"] in [row["contact_id"] for row in selected_world["contacts"]] and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "private_seed_digest": hashlib.sha256(seed).hexdigest(), "derived_world_receipts_digest": p82.digest(rows), "preflight_receipt_digest": report["receipt_digest"], "selection_actor": selection_actor, "selected_contact_binding": binding, "contact_actor": contact_actor, "contact_consequence_receipt": correction, "active_selection": active, "policy_erased_selection": erased, "reversed_policy_selection": reversed_choice, "active_viable_contact_count": active_count, "policy_erased_viable_contact_count": erased_count, "active_remaining_openings": active_count - 1 if active_count else 0, "policy_erased_remaining_openings": erased_count - 1, "checks": checks, "operational_transition_passed": bool(binding and correction), "heldout_policy_reuse_causal_claim_supported": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else ("conditional" if binding and correction else "rejected"), "subject_disposition": child["continuation"]["status"], "final_subject_digest": child["artifact_digest"], "fresh_actor_count": 2 if contact_actor else 1}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    if binding and correction:
        write_json(run / "open-subject-after-heldout-policy-reuse.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
