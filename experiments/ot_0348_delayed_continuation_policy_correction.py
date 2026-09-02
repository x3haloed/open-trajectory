from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0347_frontier_exhaustion_recurrence.py"
BASE_SHA256 = "73d7cda2558ac2903c80fd8533e994600c5d1474ad09d0c09652341ded74a014"
PARENT_DIGEST = "708ea5a38b4a6dfc130095483d40e5339623b2d71a884add458118e9c8491cd6"
AUTHORITY = "ot-0348-delayed-continuation-policy-correction"
CORRECTION_SCHEMA = REPO / "spec/ot-0348-policy-correction.schema.json"
SELECTION_SCHEMA = REPO / "spec/ot-0348-heldout-selection.schema.json"
CONTACT_SCHEMA = REPO / "spec/ot-0348-heldout-contact.schema.json"


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


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0348_frozen_ot0347")
carrier = base.carrier
world_base = base.world_base
write_json = base.write_json


INCUMBENT_SOURCE = '''def select_world(rows):
    admitted = [row for row in rows if row.get("admissible") is True and row.get("floor_preserved") is True]
    if not admitted:
        return None
    order = ["viable_contact_count", "minimum_match_basis_points", "mean_match_basis_points"]
    def key(row):
        return tuple(row["metrics"][name] for name in order)
    best = max(key(row) for row in admitted)
    winners = [row for row in admitted if key(row) == best]
    return winners[0]["world_id"] if len(winners) == 1 else None
'''

POLICY_CHECKER = '''import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location("candidate",Path("policy.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
rows=json.loads(Path("consequence.json").read_text())["worlds"]
def valid(rs):
    try:
        a=m.select_world(rs); b=m.select_world(list(reversed(rs))); ids={r["world_id"] for r in rs if r.get("admissible") is True and r.get("floor_preserved") is True}; return a==b and (a is None or a in ids)
    except Exception: return False
dec=json.loads(Path("decision.json").read_text()); ok=valid(rows) and isinstance(dec,dict) and set(dec)=={"decision","rationale"} and dec.get("decision") in {"revise","retain"} and isinstance(dec.get("rationale"),str) and 1<=len(dec["rationale"])<=2000
print(json.dumps({"valid":ok,"selected_world_id":m.select_world(rows) if ok else None},sort_keys=True)); raise SystemExit(0 if ok else 2)
'''

SELECTION_CHECKER = '''import importlib.util,json,re
from pathlib import Path
spec=importlib.util.spec_from_file_location("candidate",Path("policy.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
rows=json.loads(Path("catalog.json").read_text())["worlds"]; selected=m.select_world(rows); row=next((r for r in rows if r["world_id"]==selected),None); d=json.loads(Path("next-contact.json").read_text()); ok=row is not None and isinstance(d,dict) and set(d)=={"decision_id","selected_world_id","contact_id","rationale"} and isinstance(d.get("decision_id"),str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}",d["decision_id"])) and d.get("selected_world_id")==selected and d.get("contact_id") in row["contact_ids"] and isinstance(d.get("rationale"),str) and 1<=len(d["rationale"])<=2000
print(json.dumps({"valid":ok,"selected_world_id":selected,"contact_id":d.get("contact_id")},sort_keys=True)); raise SystemExit(0 if ok else 2)
'''

CONTACT_CHECKER = '''import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location("candidate",Path("source.py")); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); c=json.loads(Path("contact.json").read_text()); rows=[{"value":r["value"],"expected":r["expected"],"observed":m.admits(r["value"]),"passed":m.admits(r["value"])==r["expected"]} for r in c["public_cases"]]; ok=all(r["passed"] for r in rows); print(json.dumps({"valid":ok,"rows":rows},sort_keys=True)); raise SystemExit(0 if ok else 2)
'''


def object_path(store: Path, digest: str) -> Path:
    return store / "objects/sha256" / digest[:2] / digest


def load_parent(repo: Path, store: Path):
    path = repo / "evidence/manifests/OT-0347/open-subject-after-frontier-exhaustion.json"
    manifest = json.loads(path.read_text())
    raw = object_path(store, manifest["sha256"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise RuntimeError("OT-0347 parent object mismatch")
    return json.loads(raw)


def setup(args):
    repo, store, _, p82, runtime, core, base130, _ = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0348").resolve()
    return repo, store, run, p82, runtime, core, base130, load_parent(repo, store)


def opaque(seed: bytes, namespace: str, index: int) -> str:
    return hashlib.sha256(seed + namespace.encode() + index.to_bytes(2, "big")).hexdigest()[:16]


def contact(seed: bytes, namespace: str, index: int, cutoff: int):
    contact_id = f"contact-{opaque(seed, namespace, index)}"
    public_values = [cutoff - 2, cutoff, cutoff + 3]
    hidden_values = [cutoff - 5, cutoff - 1, cutoff, cutoff + 1, cutoff + 7]
    cases = lambda values: [{"value": value, "expected": value >= cutoff} for value in values]
    return {
        "contact_id": contact_id,
        "cutoff": cutoff,
        "interface": "source.py must export admits(value) -> bool",
        "public_cases": cases(public_values),
        "hidden_cases": cases(hidden_values),
    }


def derive_worlds(seed: bytes, *, heldout: bool):
    if heldout:
        roles = [("immediate", 6, 0, 610), ("balanced", 4, 1, 720), ("continuation", 2, 4, 830)]
    else:
        roles = [("immediate", 5, 0, 110), ("balanced", 3, 1, 220), ("continuation", 2, 3, 330)]
    worlds = []
    for role_index, (role, immediate_count, future_count, cutoff) in enumerate(roles, 1):
        world_id = f"world-{opaque(seed, 'world', role_index)}"
        contacts = [contact(seed, f"{role}-current", i, cutoff + i * 3) for i in range(1, immediate_count + 1)]
        future = [contact(seed, f"{role}-future", i, cutoff + 100 + i * 5) for i in range(1, future_count + 1)]
        observation = {
            "probe_id": f"probe-{opaque(seed, role, 0)}",
            "current_contact_completed": True,
            "public_consequence_passed": True,
            "hidden_consequence_passed": True,
            "subject_reopened": bool(future),
            "new_contact_ids": [row["contact_id"] for row in future],
        }
        worlds.append({
            "role": role,
            "world_id": world_id,
            "admissible": True,
            "floor_preserved": True,
            "metrics": {
                "viable_contact_count": immediate_count,
                "minimum_match_basis_points": 5000 + role_index * 111,
                "mean_match_basis_points": 6000 + role_index * 111,
            },
            "contacts": contacts,
            "future_contacts": future,
            "post_contact_observations": [observation],
        })
    order = sorted(range(3), key=lambda i: opaque(seed, "order", i))
    return [worlds[i] for i in order]


def public_rows(worlds, *, erase_outcomes=False):
    rows = []
    for world in worlds:
        rows.append({
            "world_id": world["world_id"],
            "admissible": world["admissible"],
            "floor_preserved": world["floor_preserved"],
            "metrics": copy.deepcopy(world["metrics"]),
            "contact_ids": [row["contact_id"] for row in world["contacts"]],
            "post_contact_observations": [] if erase_outcomes else copy.deepcopy(world["post_contact_observations"]),
        })
    return rows


def load_policy(source: str, name="candidate_policy"):
    namespace = {}
    exec(compile(source, f"<{name}>", "exec"), namespace)
    return namespace["select_world"]


def choose(source: str, rows):
    try:
        selected = load_policy(source)(copy.deepcopy(rows))
    except Exception:
        return None
    admitted = {row["world_id"] for row in rows if row.get("admissible") is True and row.get("floor_preserved") is True}
    return selected if selected in admitted else None


def continuation_yield(row):
    ids = set()
    for observation in row.get("post_contact_observations", []):
        if all(observation.get(key) is True for key in ("current_contact_completed", "public_consequence_passed", "hidden_consequence_passed", "subject_reopened")):
            ids.update(observation.get("new_contact_ids", []))
    return len(ids)


def source_is_generic(source: str, worlds) -> bool:
    return not any(world["world_id"] in source or any(contact["contact_id"] in source for contact in [*world["contacts"], *world["future_contacts"]]) for world in worlds)


def correction_seed(root: Path, parent, worlds, *, erase_outcomes: bool):
    seed = root / "seed"
    seed.mkdir(parents=True)
    rows = public_rows(worlds, erase_outcomes=erase_outcomes)
    incumbent = choose(INCUMBENT_SOURCE, rows)
    write_json(seed / "subject-position.json", {
        "source_subject_digest": parent["artifact_digest"],
        "continuation": parent["continuation"],
        "unresolved": parent["unresolved"],
        "exact_floor": {"pass_count": 40, "case_count": 40},
        "active_policy": parent["active_world_consequence_policy"]["policy"],
    })
    write_json(seed / "consequence.json", {"worlds": rows, "incumbent_selected_world_id": incumbent})
    (seed / "policy.py").write_text(INCUMBENT_SOURCE)
    write_json(seed / "decision.json", {"decision": "retain", "rationale": "Replace with a grounded decision after inspecting completed consequence."})
    (seed / "check_policy.py").write_text(POLICY_CHECKER)
    immutable = ["subject-position.json", "consequence.json", "check_policy.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["policy.py", "decision.json"], "immutable": immutable})
    (seed / "README.md").write_text(
        "Continue from this exact subject position. Inspect the completed world consequence and decide whether the inherited executable selection policy should be retained or revised. The policy must implement select_world(rows) and may use any actor-visible row structure, but must remain deterministic, order-invariant, id-generic, floor-preserving, and return only an admissible world id or None. The checker validates only this contract; it does not encode what should matter. Edit decision.json and edit policy.py only if revising. Run python3 check_policy.py, inspect the exact diff, and return the required report. Future catalogs, hidden contact cases, controls, evaluator, role labels, and expected decision are unavailable.\n"
    )
    return seed


def correction_output_valid(output, decision, changed):
    expected_action = "revise-continuation-policy" if decision == "revise" else "retain-continuation-policy"
    expected_files = ["policy.py", "decision.json"] if changed else ["decision.json"]
    return bool(isinstance(output, dict) and set(output) == {"action", "files_changed", "note"} and output.get("action") == expected_action and output.get("files_changed") == expected_files and isinstance(output.get("note"), str))


def audit_g13(context, label, output, audit0, semantic, files):
    audit = context.audit_actor(label, output, audit0, semantic, files)
    trace = (context.evidence(label) / "events.jsonl").read_text()
    stderr = (context.evidence(label) / "stderr.txt").read_text()
    retained = base.base.g11.retained_row(audit, trace, stderr)
    regime = {
        "challenger_accepted": base.base.g13(retained),
        "g11_accepted": base.base.g11.g11(retained),
        "toolchain_cache_denial_attributed": base.base.attributable_toolchain_cache_denial(retained),
    }
    return audit, regime


def run_corrector(context, root: Path, parent, worlds, *, erased: bool):
    label = "delayed-policy-corrector-erased" if erased else "delayed-policy-corrector"
    seed = correction_seed(root, parent, worlds, erase_outcomes=erased)
    output, audit0, workspace, _ = context.run_actor(label, seed, CORRECTION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        source = (workspace / "policy.py").read_text()
        decision = json.loads((workspace / "decision.json").read_text())
        changed = source != INCUMBENT_SOURCE
        checker = subprocess.run([sys.executable, "check_policy.py"], cwd=workspace, capture_output=True)
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        selected = choose(source, public_rows(worlds, erase_outcomes=erased))
        generic = source_is_generic(source, worlds)
        semantic = bool(immutable_ok and checker.returncode == 0 and generic and isinstance(decision, dict) and set(decision) == {"decision", "rationale"} and decision["decision"] in {"revise", "retain"} and ((decision["decision"] == "revise") == changed) and correction_output_valid(output, decision["decision"], changed))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        source, decision, changed, selected, generic = None, None, False, None, False
        immutable_ok = semantic = False
    files = ["policy.py", "decision.json"] if changed else ["decision.json"]
    audit, regime = audit_g13(context, label, output, audit0, semantic, files)
    return {"accepted": bool(semantic and regime["challenger_accepted"]), "source": source, "source_digest": hashlib.sha256(source.encode()).hexdigest() if source is not None else None, "decision": decision, "changed": changed, "selected_world_id": selected, "selected_yield": next((continuation_yield(row) for row in public_rows(worlds) if row["world_id"] == selected), None), "generic": generic, "immutable_ok": immutable_ok, "output": output, "audit": audit, "g13": regime, "outcomes_erased": erased}


def bind_policy(parent, actor, training_rows, p82):
    body = {"authority": AUTHORITY + "-bound-policy", "source_subject_digest": parent["artifact_digest"], "source_policy_binding_digest": parent["active_world_consequence_policy"]["binding_digest"], "training_consequence_digest": p82.digest(training_rows), "actor_patch_digest": actor["audit"]["patch_digest"], "policy_source": actor["source"], "policy_source_digest": actor["source_digest"], "selection_authority": True, "world_authority": False, "outcome_authority": False, "scoring_authority": False}
    return {**body, "binding_digest": p82.digest(body)}


def selection_seed(root: Path, binding, rows):
    seed = root / "seed"
    seed.mkdir(parents=True)
    (seed / "policy.py").write_text(binding["policy_source"])
    write_json(seed / "catalog.json", {"policy_binding_digest": binding["binding_digest"], "worlds": rows})
    write_json(seed / "next-contact.json", {"decision_id": "replace-me", "selected_world_id": "replace-me", "contact_id": "replace-me", "rationale": "Replace after running the bound policy."})
    (seed / "check_selection.py").write_text(SELECTION_CHECKER)
    immutable = ["policy.py", "catalog.json", "check_selection.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["next-contact.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue the subject by running its bound policy on catalog.json, then choose any current contact belonging to the selected world and record it in next-contact.json. Run python3 check_selection.py, inspect the exact diff, and return the required report. Private seed, role labels, hidden contact cases, unchanged control, evaluator, and expected ids are unavailable. Edit no other file.\n")
    return seed


def run_selector(context, root: Path, binding, worlds):
    label = "delayed-policy-heldout-selector"
    rows = public_rows(worlds)
    seed = selection_seed(root, binding, rows)
    output, audit0, workspace, _ = context.run_actor(label, seed, SELECTION_SCHEMA, (seed / "README.md").read_text().strip())
    expected = choose(binding["policy_source"], rows)
    try:
        decision = json.loads((workspace / "next-contact.json").read_text())
        checker = subprocess.run([sys.executable, "check_selection.py"], cwd=workspace, capture_output=True)
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        selected = next(row for row in worlds if row["world_id"] == expected)
        semantic = bool(immutable_ok and checker.returncode == 0 and decision.get("selected_world_id") == expected and decision.get("contact_id") in [row["contact_id"] for row in selected["contacts"]] and output == {"action": "select-delayed-continuation-contact", "files_changed": ["next-contact.json"], "note": output["note"]})
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        decision, selected, immutable_ok, semantic = None, None, False, False
    audit, regime = audit_g13(context, label, output, audit0, semantic, ["next-contact.json"])
    return {"accepted": bool(semantic and regime["challenger_accepted"]), "decision": decision, "expected_world_id": expected, "selected_role": selected["role"] if selected else None, "output": output, "audit": audit, "g13": regime, "immutable_ok": immutable_ok}


def contact_seed(root: Path, decision, world):
    seed = root / "seed"
    seed.mkdir(parents=True)
    chosen = next(row for row in world["contacts"] if row["contact_id"] == decision["contact_id"])
    write_json(seed / "contact.json", {"binding": decision, "contact_id": chosen["contact_id"], "public_cases": chosen["public_cases"], "interface": chosen["interface"]})
    (seed / "source.py").write_text(world_base.SOURCE_TEMPLATE.format(cutoff=chosen["cutoff"] + 1))
    (seed / "check_contact.py").write_text(CONTACT_CHECKER)
    immutable = ["contact.json", "check_contact.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["source.py"], "immutable": immutable})
    (seed / "README.md").write_text("Continue the selected contact. Repair source.py so admits(value) satisfies every public case. Run python3 check_contact.py, inspect the exact diff, and return the required report. Hidden cases, downstream frontier, private seed, controls, evaluator, and admission result are unavailable. Edit no other file.\n")
    return seed, chosen


def run_contact(context, root: Path, decision, world):
    label = "delayed-policy-heldout-contact"
    seed, chosen = contact_seed(root, decision, world)
    output, audit0, workspace, _ = context.run_actor(label, seed, CONTACT_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        checker = subprocess.run([sys.executable, "check_contact.py"], cwd=workspace, capture_output=True)
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        public = world_base.evaluate_source(workspace / "source.py", chosen["public_cases"])
        hidden = world_base.evaluate_source(workspace / "source.py", chosen["hidden_cases"])
        semantic = bool(immutable_ok and checker.returncode == 0 and public["pass_count"] == public["case_count"] == 3 and hidden["pass_count"] == hidden["case_count"] == 5 and output == {"action": "realize-delayed-continuation-contact", "files_changed": ["source.py"], "note": output["note"]})
    except (OSError, ValueError, KeyError, TypeError):
        public = hidden = None
        immutable_ok = semantic = False
    audit, regime = audit_g13(context, label, output, audit0, semantic, ["source.py"])
    return {"accepted": bool(semantic and regime["challenger_accepted"]), "contact_id": chosen["contact_id"], "public_result": public, "hidden_result": hidden, "output": output, "audit": audit, "g13": regime, "immutable_ok": immutable_ok}


def frontier_body(parent, binding, world, selector, contact_actor, p82):
    contacts = [{key: copy.deepcopy(row[key]) for key in ("contact_id", "cutoff", "interface", "public_cases")} for row in world["future_contacts"]]
    body = {"authority": AUTHORITY + "-verified-downstream-frontier", "source_subject_digest": parent["artifact_digest"], "policy_binding_digest": binding["binding_digest"], "selected_world_id": world["world_id"], "source_contact_id": contact_actor["contact_id"], "source_actor_patch_digest": contact_actor["audit"]["patch_digest"], "contact_ids": [row["contact_id"] for row in contacts], "contacts": contacts, "consumed_contact_ids": [], "remaining_contact_ids": [row["contact_id"] for row in contacts], "active_contact_id": contacts[0]["contact_id"] if contacts else None, "world_authority": True, "outcome_authority": True, "selection_authority": False}
    return {**body, "binding_digest": p82.digest(body)}


def compile_child(parent, binding, training_receipt, heldout_rows, selector, contact_actor, selected_world, p82):
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["world_consequence_policy_bindings"] = [*child.get("world_consequence_policy_bindings", []), binding]
    child["active_world_consequence_policy_program"] = binding
    child["delayed_continuation_consequences"] = [*child.get("delayed_continuation_consequences", []), training_receipt]
    selection_receipt = {"authority": AUTHORITY + "-heldout-selection", "source_subject_digest": parent["artifact_digest"], "policy_binding_digest": binding["binding_digest"], "heldout_rows_digest": p82.digest(heldout_rows), "decision": selector["decision"], "actor_patch_digest": selector["audit"]["patch_digest"], "selection_authority": True, "world_authority": False, "outcome_authority": False}
    selection_receipt["receipt_digest"] = p82.digest(selection_receipt)
    child["delayed_continuation_policy_selections"] = [*child.get("delayed_continuation_policy_selections", []), selection_receipt]
    frontier = frontier_body(parent, binding, selected_world, selector, contact_actor, p82)
    child["world_contact_frontiers"] = [*child.get("world_contact_frontiers", []), frontier]
    child["active_world_contact_frontier"] = frontier
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": f"Continue the verified downstream frontier through contact {frontier['active_contact_id']}."}
    child["unresolved"] = "Can the corrected continuation-yield policy survive a later regime in which delayed yield is itself misleading?"
    return p82.seal(child), selection_receipt, frontier


def materializes(subject):
    frontier = subject.get("active_world_contact_frontier", {})
    active = frontier.get("active_contact_id")
    return bool(active and active in frontier.get("remaining_contact_ids", []) and any(row.get("contact_id") == active and len(row.get("public_cases", [])) == 3 for row in frontier.get("contacts", [])))


def reference_source():
    return '''def select_world(rows):
    admitted=[r for r in rows if r.get("admissible") is True and r.get("floor_preserved") is True]
    def score(r):
        ids=set()
        for o in r.get("post_contact_observations",[]):
            if all(o.get(k) is True for k in ("current_contact_completed","public_consequence_passed","hidden_consequence_passed","subject_reopened")):
                ids.update(o.get("new_contact_ids",[]))
        return len(ids)
    if not admitted: return None
    best=max(score(r) for r in admitted); winners=[r for r in admitted if score(r)==best]
    return winners[0]["world_id"] if len(winners)==1 else None
'''


def preflight(parent, p82, runtime):
    anchors = []
    for index in range(6):
        seed = hashlib.sha256(f"ot0348-anchor-{index}".encode()).digest()
        worlds = derive_worlds(seed, heldout=bool(index % 2))
        rows = public_rows(worlds)
        incumbent = choose(INCUMBENT_SOURCE, rows)
        corrected = choose(reference_source(), rows)
        roles = {world["world_id"]: world["role"] for world in worlds}
        anchors.append({"anchor_id": f"anchor-{index}", "incumbent_role": roles.get(incumbent), "corrected_role": roles.get(corrected), "incumbent_yield": next(continuation_yield(row) for row in rows if row["world_id"] == incumbent), "corrected_yield": next(continuation_yield(row) for row in rows if row["world_id"] == corrected), "passed": roles.get(incumbent) == "immediate" and roles.get(corrected) == "continuation"})
    regressive = public_rows(derive_worlds(hashlib.sha256(b"ot0348-regressive").digest(), heldout=True))
    regressive.append({"world_id": "regressive-decoy", "admissible": False, "floor_preserved": False, "metrics": {"viable_contact_count": 99, "minimum_match_basis_points": 9999, "mean_match_basis_points": 9999}, "contact_ids": ["forbidden"], "post_contact_observations": [{"current_contact_completed": True, "public_consequence_passed": True, "hidden_consequence_passed": True, "subject_reopened": True, "new_contact_ids": [f"bad-{i}" for i in range(99)]}]})
    checks = {
        "source_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and base.next_operation(parent, p82) == "test-world-consequence-policy-reuse",
        "exact_floor_40": parent["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["pass_count"] == parent["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["case_count"] == 40,
        "six_of_six_horizon_anchors": sum(row["passed"] for row in anchors) == len(anchors) == 6,
        "reference_is_order_invariant": all(choose(reference_source(), public_rows(derive_worlds(hashlib.sha256(f"perm-{i}".encode()).digest(), heldout=True))) == choose(reference_source(), list(reversed(public_rows(derive_worlds(hashlib.sha256(f"perm-{i}".encode()).digest(), heldout=True))))) for i in range(4)),
        "regressive_decoy_rejected": choose(reference_source(), regressive) != "regressive-decoy" and choose(INCUMBENT_SOURCE, regressive) != "regressive-decoy",
        "invalid_source_rejects": choose("def select_world(rows):\n raise RuntimeError()\n", regressive) is None,
        "checker_programs_compile": all(compile(source, name, "exec") for name, source in (("check_policy.py", POLICY_CHECKER), ("check_selection.py", SELECTION_CHECKER), ("check_contact.py", CONTACT_CHECKER))),
        "schemas_present": all(path.is_file() for path in (CORRECTION_SCHEMA, SELECTION_SCHEMA, CONTACT_SCHEMA)),
        "g13_12_of_12": base.base.anchors()["pass_count"] == base.base.anchors()["case_count"] == 12,
        "g12_10_of_10": world_base.base.anchors()["pass_count"] == world_base.base.anchors()["case_count"] == 10,
        "g11_15_of_15": base.base.g11.evaluate(base.base.g11.g11)["pass_count"] == base.base.g11.evaluate(base.base.g11.g11)["case_count"] == 15,
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "anchors": anchors, "checks": checks}
    return {**body, "receipt_digest": p82.digest(body)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--training-seed-file", type=Path)
    parser.add_argument("--heldout-seed-output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, core, base130, parent = setup(args)
    report = preflight(parent, p82, runtime)
    if args.preflight_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0348 evidence")
    if args.training_seed_file is None or args.heldout_seed_output is None:
        raise SystemExit("--training-seed-file and --heldout-seed-output are required")
    training_seed = args.training_seed_file.read_bytes()
    if len(training_seed) != 32:
        raise SystemExit("training seed must contain exactly 32 bytes")
    if args.heldout_seed_output.exists():
        raise SystemExit("held-out seed output must not exist before policy binding")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", report)
    if not report["checks"]["passed"]:
        raise SystemExit("OT-0348 preflight failed")
    training_worlds = derive_worlds(training_seed, heldout=False)
    training_rows = public_rows(training_worlds)
    incumbent_training = choose(INCUMBENT_SOURCE, training_rows)
    incumbent_training_yield = next(continuation_yield(row) for row in training_rows if row["world_id"] == incumbent_training)
    training_receipt = {"authority": AUTHORITY + "-training-consequence", "source_subject_digest": parent["artifact_digest"], "private_seed_digest": hashlib.sha256(training_seed).hexdigest(), "worlds": training_rows, "incumbent_selected_world_id": incumbent_training, "incumbent_realized_continuation_yield": incumbent_training_yield, "world_authority": True, "outcome_authority": True, "scoring_authority": True, "actor_authority": False}
    training_receipt["receipt_digest"] = p82.digest(training_receipt)
    write_json(run / "training-consequence.json", training_receipt)
    context = world_base.policy_base.contact.base305.actor_context(runtime, core, base130, run / "actors", repo)
    active = run_corrector(context, run / "active-corrector", parent, training_worlds, erased=False)
    erased = run_corrector(context, run / "erased-corrector", parent, training_worlds, erased=True)
    active_improves = bool(active["accepted"] and active["changed"] and active["selected_yield"] is not None and active["selected_yield"] > incumbent_training_yield)
    binding = bind_policy(parent, active, training_rows, p82) if active_improves else None
    if binding is None:
        heldout_seed = None
        heldout_worlds = []
    else:
        heldout_seed = secrets.token_bytes(32)
        args.heldout_seed_output.parent.mkdir(parents=True, exist_ok=True)
        args.heldout_seed_output.write_bytes(heldout_seed)
        heldout_worlds = derive_worlds(heldout_seed, heldout=True)
    heldout_rows = public_rows(heldout_worlds)
    active_choice = choose(binding["policy_source"], heldout_rows) if binding else None
    unchanged_choice = choose(INCUMBENT_SOURCE, heldout_rows) if binding else None
    active_yield = next((continuation_yield(row) for row in heldout_rows if row["world_id"] == active_choice), None)
    unchanged_yield = next((continuation_yield(row) for row in heldout_rows if row["world_id"] == unchanged_choice), None)
    selector = run_selector(context, run / "heldout-selector", binding, heldout_worlds) if binding and active_yield is not None and active_yield > unchanged_yield else None
    selected_world = next((world for world in heldout_worlds if selector and world["world_id"] == selector["decision"]["selected_world_id"]), None)
    contact_actor = run_contact(context, run / "heldout-contact", selector["decision"], selected_world) if selector and selector["accepted"] and selected_world else None
    if contact_actor and contact_actor["accepted"]:
        child, selection_receipt, frontier = compile_child(parent, binding, training_receipt, heldout_rows, selector, contact_actor, selected_world, p82)
    else:
        child, selection_receipt, frontier = parent, None, None
    erased_equivalent = bool(erased["accepted"] and erased["changed"] and erased["source"] is not None and all(choose(erased["source"], public_rows(derive_worlds(hashlib.sha256(f"erased-anchor-{i}".encode()).digest(), heldout=True))) == choose(active["source"], public_rows(derive_worlds(hashlib.sha256(f"erased-anchor-{i}".encode()).digest(), heldout=True))) for i in range(4)))
    checks = {
        "preflight_passed": report["checks"]["passed"],
        "incumbent_harm_observed": incumbent_training_yield == 0,
        "active_corrector_clean": active["accepted"],
        "active_policy_changed_and_improves_training": active_improves,
        "erased_control_lacks_equivalent_revision": erased["accepted"] and not erased_equivalent,
        "policy_bound_before_heldout_derivation": bool(binding and heldout_seed and binding["training_consequence_digest"] == p82.digest(training_rows)),
        "heldout_ids_absent_from_bound_source": bool(binding and source_is_generic(binding["policy_source"], heldout_worlds)),
        "changed_beats_unchanged_heldout": active_yield is not None and unchanged_yield is not None and active_yield > unchanged_yield and active_choice != unchanged_choice,
        "machinery_erasure_reproduces_immediate_choice": unchanged_choice is not None and next(world["role"] for world in heldout_worlds if world["world_id"] == unchanged_choice) == "immediate",
        "heldout_selector_clean": bool(selector and selector["accepted"]),
        "selected_contact_clean": bool(contact_actor and contact_actor["accepted"]),
        "selected_contact_public_3_of_3": bool(contact_actor and contact_actor["public_result"]["pass_count"] == contact_actor["public_result"]["case_count"] == 3),
        "selected_contact_hidden_5_of_5": bool(contact_actor and contact_actor["hidden_result"]["pass_count"] == contact_actor["hidden_result"]["case_count"] == 5),
        "exact_floor_40_preserved": child.get("active_world_seeking_stake") == parent["active_world_seeking_stake"],
        "subject_only_actionable_frontier": child is not parent and child.get("continuation", {}).get("status") == "open" and materializes(child) and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "training_seed_digest": hashlib.sha256(training_seed).hexdigest(), "training_consequence_receipt_digest": training_receipt["receipt_digest"], "incumbent_training_selection": incumbent_training, "incumbent_training_yield": incumbent_training_yield, "active_corrector": active, "outcome_erased_corrector": erased, "policy_binding": binding, "heldout_seed_digest": hashlib.sha256(heldout_seed).hexdigest() if heldout_seed else None, "heldout_rows_digest": p82.digest(heldout_rows) if heldout_rows else None, "changed_heldout_selection": active_choice, "unchanged_heldout_selection": unchanged_choice, "changed_heldout_yield": active_yield, "unchanged_heldout_yield": unchanged_yield, "heldout_selector": selector, "heldout_contact_actor": contact_actor, "selection_receipt": selection_receipt, "frontier_binding": frontier, "checks": checks, "operational_transition_passed": checks["subject_only_actionable_frontier"], "machinery_refinement_causal_claim_supported": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else ("conditional" if checks["subject_only_actionable_frontier"] else "rejected"), "subject_disposition": child.get("continuation", {}).get("status") if child is not parent else "quarantined", "final_subject_digest": child["artifact_digest"], "fresh_actor_count": 2 + int(selector is not None) + int(contact_actor is not None)}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    if checks["subject_only_actionable_frontier"]:
        write_json(run / "open-subject-after-delayed-policy-correction.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
