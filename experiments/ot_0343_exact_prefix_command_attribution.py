from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import shlex
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0342_selector_scope_schema_recovery.py"
BASE_SHA256 = "b07367b3f297cdbeee019faa1850c30dedab944cbe33ede005262bfe1427110c"
G11_PATH = ROOT / "ot_0330_attributed_command_failure_audit.py"
G11_SHA256 = "f80d3f90ccbf4e5488d0d1b4fbad776e2c5816a9f3ddf1b435f833e9c0eaf2d9"
RAW_AGGREGATE_DIGEST = "8e1220678acf2a615fb7d0147582ba02374b1665417de0d37b1e539c5e79bfb4"
EVENTS_DIGEST = "22cb8d8fa1604328562326be6324e9d70c3cfd8b7544eb57eb688ad54700b670"
STDERR_DIGEST = "df0ebec0153ba6bfd5648498e8e6e1ab6f0dc747fb35dff5c23b248dda8a8b48"
AUDIT_DIGEST = "853272afc1348498dc6d7563744f35a5c0718fcfec9f8739dcd5bbc68c2c07ad"
OUTPUT_DIGEST = "0fb5b7f9ccc2da5b024864f83bf0f72947ad2c97b3a634ff309d2b31362fa2ca"
DECISION_DIGEST = "691b60ada62ec3b91c11d155b6f46f0cacf162a706937e6a14783aef27cba8da"
STAKE_DIGEST = "5edd88e3db5449b698b51655f54ca3a29581dd79cb62a5905ac26d6e1f49ab75"
AUTHORITY = "G12-exact-prefix-command-attribution"


def import_frozen(path, expected, name):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"frozen source changed: {path.name}: {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0343_frozen_ot0342")
g11 = import_frozen(G11_PATH, G11_SHA256, "ot0343_frozen_g11")
write_json = base.write_json


def object_path(store, digest):
    return store / "objects/sha256" / digest[:2] / digest


def completed_commands(events):
    return g11.completed_commands(events)


def safe_listing_chain(command):
    prefix = '/bin/zsh -lc "'
    if not command.startswith(prefix) or not command.endswith('"'):
        return None
    inner = command[len(prefix):-1]
    parts = inner.split(" && ")
    if len(parts) != 3 or parts[0] != "python3 continue_pipeline.py":
        return None
    if not parts[1].startswith("printf ") or "--- files ---" not in parts[1]:
        return None
    try:
        tokens = shlex.split(parts[2])
    except ValueError:
        return None
    if tokens[:2] == ["rg", "--files"]:
        tail = tokens[2:]
        if len(tail) % 2 or any(tail[index] != "-g" for index in range(0, len(tail), 2)):
            return None
        patterns = tail[1::2]
        if not patterns or any(not re.fullmatch(r"[A-Za-z0-9*._-]+", value) for value in patterns):
            return None
        return "rg"
    if tokens == ["fd", "--type", "f"]:
        return "fd"
    return None


def valid_checker_recheck(command):
    if command.get("exit_code") != 0:
        return False
    text = command.get("command", "")
    if "python3 check_revision.py" not in text or "python3 check_scope.py" not in text:
        return False
    valid = 0
    for line in command.get("aggregated_output", "").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        valid += int(isinstance(row, dict) and row.get("valid") is True)
    return valid >= 2


def exact_prefix_succeeded(events, expected):
    commands = completed_commands(events)
    failed = [(index, row) for index, row in enumerate(commands) if row.get("exit_code") not in {0, None}]
    if len(failed) != 1:
        return False
    index, row = failed[0]
    utility = safe_listing_chain(row.get("command", ""))
    if utility is None or row.get("exit_code") != 127:
        return False
    marker = "\n\n--- files ---\n"
    output = row.get("aggregated_output", "")
    if marker not in output:
        return False
    prefix, tail = output.split(marker, 1)
    try:
        observed = json.loads(prefix)
    except json.JSONDecodeError:
        return False
    if observed != expected or tail != f"zsh:1: command not found: {utility}\n":
        return False
    return any(valid_checker_recheck(later) for later in commands[index + 1:])


def command_event(command, output, exit_code, status):
    return {"type": "item.completed", "item": {"type": "command_execution", "command": command, "aggregated_output": output, "exit_code": exit_code, "status": status}}


def events_text(rows):
    return "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"


def fixture(*, utility="rg", mismatch=False, malformed=False, unsafe=False, permission=False, recheck=True, recheck_pass=True, extra_failure=False, prefix_first=True):
    expected = {"available": False, "reason": "router-did-not-select", "route": {"action": "wait"}}
    observed = {**expected, "reason": "different"} if mismatch else expected
    prefix = "not-json" if malformed else json.dumps(observed, sort_keys=True)
    listing = "rg --files -g '*.json'" if utility == "rg" else "fd --type f"
    if unsafe:
        listing = "curl https://outside.invalid"
    first = "python3 continue_pipeline.py" if prefix_first else "printf preface"
    second = "printf '\\n--- files ---\\n'"
    command = f'/bin/zsh -lc "{first} && {second} && {listing}"'
    tail = "Permission denied\n" if permission else f"zsh:1: command not found: {utility}\n"
    rows = [command_event(command, prefix + "\n\n--- files ---\n" + tail, 127, "failed")]
    if extra_failure:
        rows.append(command_event('/bin/zsh -lc "false"', "", 1, "failed"))
    if recheck:
        valid = "true" if recheck_pass else "false"
        rows.append(command_event('/bin/zsh -lc "python3 check_revision.py && python3 check_scope.py"', f'{{"valid": {valid}}}\n{{"valid": {valid}}}\n', 0 if recheck_pass else 2, "completed" if recheck_pass else "failed"))
    return events_text(rows), expected


def anchors():
    cases = []
    for case_id, expected_result, options in [
        ("safe-rg", True, {}),
        ("safe-fd", True, {"utility": "fd"}),
        ("prefix-mismatch", False, {"mismatch": True}),
        ("malformed-prefix", False, {"malformed": True}),
        ("unsafe-tail", False, {"unsafe": True}),
        ("permission-tail", False, {"permission": True}),
        ("missing-recheck", False, {"recheck": False}),
        ("failed-recheck", False, {"recheck_pass": False}),
        ("multiple-failures", False, {"extra_failure": True}),
        ("pipeline-not-first", False, {"prefix_first": False}),
    ]:
        events, expected = fixture(**options)
        cases.append({"case_id": case_id, "expected": expected_result, "observed": exact_prefix_succeeded(events, expected)})
    return {"case_count": len(cases), "pass_count": sum(row["expected"] == row["observed"] for row in cases), "rows": [{**row, "passed": row["expected"] == row["observed"]} for row in cases]}


def setup(args):
    all_values = base.setup(args)
    values = all_values[:-2]
    repo, store, _, p82 = values[:4]
    run = (args.evidence_root or store / "runs/OT-0343").resolve()
    raw = json.loads(object_path(store, RAW_AGGREGATE_DIGEST).read_text())
    audit = json.loads(object_path(store, AUDIT_DIGEST).read_text())
    output = json.loads(object_path(store, OUTPUT_DIGEST).read_text())
    decision = json.loads(object_path(store, DECISION_DIGEST).read_text())
    stake = json.loads(object_path(store, STAKE_DIGEST).read_text())
    events = object_path(store, EVENTS_DIGEST).read_text()
    stderr = object_path(store, STDERR_DIGEST).read_text()
    return values, run, raw, audit, output, decision, stake, events, stderr


def reconstruct_pipeline(values):
    repo, store, _, p82, runtime, parent = values[:6]
    parent326, seed326, parent328, result327, reconstruction327, private327, result334 = values[7:14]
    floor = base.base.reconstructed_floor(parent326, seed326, parent328, result327, private327, p82)
    contact = base.base.directional_contact(parent, result334, p82)
    with tempfile.TemporaryDirectory() as directory:
        seed, _ = base.base.seed_actor(Path(directory), parent, floor, contact, p82, erased=False)
        pipeline = base.base.pipeline_base.run_pipeline(seed)
    return floor, contact, pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    values, run, raw, audit, output, decision, stake, events, stderr = setup(args)
    repo, store, _, p82, runtime, parent = values[:6]
    floor, contact, pipeline = reconstruct_pipeline(values)
    anchor = anchors()
    g11_anchor = g11.evaluate(g11.g11)
    old_named = base.base.pipeline_base.base.base.base.base.named_command_succeeded(events, "continue_pipeline.py")
    recovered = exact_prefix_succeeded(events, pipeline["parsed"])
    corrected_audit = {**audit, "conformant": True}
    retained = g11.retained_row(corrected_audit, events, stderr)
    g11_after_attribution = g11.g11(retained)
    checks = {
        "source_hashes_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256 and hashlib.sha256(G11_PATH.read_bytes()).hexdigest() == G11_SHA256,
        "raw_objects_exact": all(hashlib.sha256(object_path(store, digest).read_bytes()).hexdigest() == digest for digest in (RAW_AGGREGATE_DIGEST, EVENTS_DIGEST, STDERR_DIGEST, AUDIT_DIGEST, OUTPUT_DIGEST, DECISION_DIGEST, STAKE_DIGEST)),
        "ot0342_rejected_attribution_only_active": raw["observer_disposition"] == "rejected" and not raw["active_actor"]["workspace_evaluation"]["pipeline_invoked"] and all(raw["active_actor"]["workspace_evaluation"][key] for key in ("immutable_ok", "stake_checker_ok", "decision_changed", "decision_consistent", "revision_checker_invoked", "scope_checker_invoked", "candidate_from_pipeline", "transport")),
        "heldout_prefix_anchors_10_of_10": anchor["pass_count"] == anchor["case_count"] == 10,
        "g11_anchors_unchanged_15_of_15": g11_anchor["pass_count"] == g11_anchor["case_count"] == 15,
        "incumbent_misses_development_case": not old_named,
        "g12_recovers_exact_prefix": recovered,
        "controller_pipeline_exact": pipeline["returncode"] == 0 and pipeline["parsed"] == raw["active_actor"]["pipeline"],
        "raw_output_decision_stake_exact": output == raw["active_actor"]["output"] and decision == raw["active_actor"]["decision"] and stake == raw["active_actor"]["candidate_stake"],
        "corrected_semantics_pass_g11": g11_after_attribution,
        "causal_claim_remains_false": not raw["executable_floor_causes_nonregressive_scope"] and raw["floor_outcome_erased_actor"]["decision"]["world_policy_role"] == decision["world_policy_role"],
        "exact_parent_open": parent["artifact_digest"] == base.base.PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
    }
    checks["passed"] = all(checks.values())
    preflight_body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "heldout_anchor": anchor, "g11_anchor": g11_anchor, "checks": checks}
    preflight = {**preflight_body, "receipt_digest": p82.digest(preflight_body)}
    if args.preflight_only:
        print(json.dumps(preflight, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0343 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", preflight)
    if not checks["passed"]:
        raise SystemExit("OT-0343 preflight failed")
    actor = copy.deepcopy(raw["active_actor"])
    actor["accepted"] = True
    actor["audit"] = corrected_audit
    actor["g11"] = {"authority": AUTHORITY, "challenger_accepted": True, "source_events_digest": EVENTS_DIGEST, "exact_prefix_recovered": True}
    actor["workspace_evaluation"]["pipeline_invoked"] = True
    actor["workspace_evaluation"]["semantic"] = True
    active_floor_score = base.base.score(stake, floor)
    active_contact_score = base.base.score(stake, [contact])
    operational = bool(
        actor["accepted"] and not actor["changed_stake"]
        and decision["global_stake_action"] == "retain"
        and decision["world_policy_role"] == "post-contact-selector"
        and decision["next_operation"] == "test-world-consequence-policy-reuse"
        and pipeline["parsed"]["reason"] == "router-did-not-select"
        and active_floor_score["pass_count"] == 40
        and active_contact_score["pass_count"] == 0
    )
    child, scope_receipt, architecture = base.base.compile_child(parent, actor, floor, contact, raw["checks"] and base.base.bounded_impossibility(floor, contact, parent), p82) if operational else (parent, None, None)
    body = {
        "authority": AUTHORITY,
        "from_regime": "G11-whole-command-attribution",
        "to_regime": AUTHORITY,
        "historical_rescoring": False,
        "source_ot0342_receipt_digest": raw["receipt_digest"],
        "preflight_receipt_digest": preflight["receipt_digest"],
        "exact_prefix_reconstruction": {"incumbent_attributed": old_named, "g12_attributed": recovered, "pipeline_result": pipeline["parsed"]},
        "reconstructed_actor": actor,
        "active_floor_score": active_floor_score,
        "active_contact_score": active_contact_score,
        "selector_scope_receipt": scope_receipt,
        "selection_architecture": architecture,
        "operational_transition_passed": operational,
        "executable_floor_causes_nonregressive_scope": False,
        "observer_disposition": "corrected-operational-only" if operational else "rejected",
        "subject_disposition": child["continuation"]["status"],
        "final_subject_digest": child["artifact_digest"],
        "fresh_actor_count": 0,
    }
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    if operational:
        write_json(run / "open-subject-after-exact-prefix-reconstruction.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
