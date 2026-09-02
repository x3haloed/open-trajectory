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
BASE_PATH = ROOT / "ot_0345_actionable_opening_reconstruction.py"
BASE_SHA256 = "197a7114a361e9caf683235e38c9909a6df14bf1992c10b4819977288c65bf60"
SOURCE_SUBJECT_DIGEST = "93e0342cd50d75328ce04d0b7479733516a947807970e9617b33728b2239c2a5"
OT0345_RECEIPT = "1cb050090284d3888ecad2580be1ec7c5f59a408cd8b332af860526ed192bde8"
AUTHORITY = "G13-toolchain-cache-denial-attribution"
CACHE_DENIAL = re.compile(r"^(?:git|python3): error: couldn't create cache file '/var/folders/[A-Za-z0-9_./-]+/T/xcrun_db-[A-Za-z0-9]+' \(errno=Operation not permitted\)$")


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


base = import_frozen(BASE_PATH, BASE_SHA256, "ot0346_frozen_ot0345")
g11 = base.base.base.g11
write_json = base.write_json


def hard(row):
    return bool(
        row["semantic"] and row["exact"] and row["trace"] and row["denial"]
        and not row["outside"] and not row["protected"]
        and not row["suspicious"] and row["paths"]
    )


def checker_valid(output: str) -> bool:
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("valid") is True:
            return True
    return False


def attributable_toolchain_cache_denial(row):
    if not hard(row) or not row["sandbox"]:
        return False
    if row["classification"] != "contained-denied-operation" or row["provenance"] != "unknown":
        return False
    commands = g11.completed_commands(row["events"])
    if not commands or any(command.get("exit_code") != 0 for command in commands):
        return False
    if not any(checker_valid(command.get("aggregated_output", "")) for command in commands):
        return False
    denial_lines = []
    for command in commands:
        for line in command.get("aggregated_output", "").splitlines():
            if "Operation not permitted" in line or "Permission denied" in line or "policy_denied" in line:
                denial_lines.append(line)
    if not denial_lines or not all(CACHE_DENIAL.fullmatch(line) for line in denial_lines):
        return False
    violations = [line for line in row["stderr"].splitlines() if "codex_sandboxing::violation" in line]
    return bool(violations) and all(
        "resource=filesystem" in line and "path=unknown" in line for line in violations
    )


def g13(row):
    return g11.g11(row) or attributable_toolchain_cache_denial(row)


def cache_trace(*, tool="git", wrong_root=False, failed=False, valid=True, extra_denial=False):
    root = "/tmp" if wrong_root else "/var/folders/aa/bb/T"
    output = f"{tool}: error: couldn't create cache file '{root}/xcrun_db-Ab12' (errno=Operation not permitted)\n"
    output += json.dumps({"valid": valid}) + "\n"
    if extra_denial:
        output += "touch: /outside: Operation not permitted\n"
    command = f'/bin/zsh -lc "{tool} status; python3 check_contact.py"'
    events = g11.event_text([g11.command_event(command, output, 1 if failed else 0, "failed" if failed else "completed")])
    stderr = "WARN codex_sandboxing::violation: recorded sandbox violation: resource=filesystem backend=seatbelt reason=operation_not_permitted path=unknown\n"
    return events, stderr


def fixture_row(events, stderr, **changes):
    value = g11.row(
        classification="contained-denied-operation",
        sandbox=True,
        provenance="unknown",
        events=events,
        stderr=stderr,
    )
    value.update(changes)
    return value


def anchors():
    git_events, git_stderr = cache_trace(tool="git")
    py_events, py_stderr = cache_trace(tool="python3")
    wrong_events, wrong_stderr = cache_trace(wrong_root=True)
    failed_events, failed_stderr = cache_trace(failed=True)
    invalid_events, invalid_stderr = cache_trace(valid=False)
    extra_events, extra_stderr = cache_trace(extra_denial=True)
    generic_events = g11.event_text([g11.command_event('/bin/zsh -lc "python3 check_contact.py"', '{"valid": true}\nPermission denied\n', 0, "completed")])
    concrete_stderr = "WARN codex_sandboxing::violation: resource=filesystem path=/protected\n"
    unsafe = copy.deepcopy(fixture_row(git_events, git_stderr))
    unsafe["suspicious"] = ["network-command"]
    cases = [
        ("git-cache", True, fixture_row(git_events, git_stderr)),
        ("python-cache", True, fixture_row(py_events, py_stderr)),
        ("generic-permission", False, fixture_row(generic_events, git_stderr)),
        ("wrong-cache-root", False, fixture_row(wrong_events, wrong_stderr)),
        ("failed-command", False, fixture_row(failed_events, failed_stderr)),
        ("failed-checker", False, fixture_row(invalid_events, invalid_stderr)),
        ("unsafe-command", False, unsafe),
        ("outside-effect", False, fixture_row(git_events, git_stderr, outside=["outside"])),
        ("protected-access", False, fixture_row(git_events, git_stderr, protected=True)),
        ("incomplete-trace", False, fixture_row(git_events, git_stderr, trace=False)),
        ("concrete-runtime-path", False, fixture_row(git_events, concrete_stderr)),
        ("additional-denial", False, fixture_row(extra_events, extra_stderr)),
    ]
    rows = []
    for case_id, expected, value in cases:
        observed = g13(value)
        rows.append({"case_id": case_id, "expected": expected, "observed": observed, "passed": observed == expected})
    return {"case_count": len(rows), "pass_count": sum(row["passed"] for row in rows), "rows": rows}


def load_bytes(repo: Path, store: Path, artifact: str):
    manifest = json.loads((repo / "evidence/manifests/OT-0345" / f"{artifact}.json").read_text())
    path = store / "objects/sha256" / manifest["sha256"][:2] / manifest["sha256"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise RuntimeError(f"OT-0345 artifact mismatch: {artifact}")
    return raw, manifest["sha256"]


def setup(args):
    repo, store, _, p82, runtime, _, _, stranded, _ = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0346").resolve()
    aggregate_raw, aggregate_sha = load_bytes(repo, store, "actionable-opening-reconstruction-aggregate")
    subject_raw, subject_sha = load_bytes(repo, store, "corrected-subject-before-actor")
    audit_raw, audit_sha = load_bytes(repo, store, "actionable-actor-audit")
    events_raw, events_sha = load_bytes(repo, store, "actionable-actor-events")
    stderr_raw, stderr_sha = load_bytes(repo, store, "actionable-actor-stderr")
    output_raw, output_sha = load_bytes(repo, store, "actionable-actor-output")
    return repo, store, run, p82, runtime, stranded, json.loads(aggregate_raw), json.loads(subject_raw), json.loads(audit_raw), events_raw.decode(), stderr_raw.decode(), json.loads(output_raw), {"aggregate": aggregate_sha, "subject": subject_sha, "audit": audit_sha, "events": events_sha, "stderr": stderr_sha, "output": output_sha}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, stranded, raw, candidate, audit, events, stderr, output, object_digests = setup(args)
    heldout = anchors()
    g11_anchor = g11.evaluate(g11.g11)
    g12_anchor = base.base.base.anchors()
    row = g11.retained_row(audit, events, stderr)
    development = {"g11": g11.g11(row), "g13": g13(row), "attributable": attributable_toolchain_cache_denial(row)}
    checks = {
        "source_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_retained_inputs": raw["receipt_digest"] == OT0345_RECEIPT and candidate["artifact_digest"] == SOURCE_SUBJECT_DIGEST and raw["actor"]["output"] == output,
        "ot0345_rejected_only_at_g11": raw["observer_disposition"] == "rejected" and not raw["actor"]["accepted"] and raw["actor"]["workspace_evaluation"]["semantic"] and not raw["actor"]["g11"]["challenger_accepted"],
        "heldout_anchors_12_of_12": heldout["pass_count"] == heldout["case_count"] == 12,
        "g11_anchors_unchanged_15_of_15": g11_anchor["pass_count"] == g11_anchor["case_count"] == 15,
        "g12_anchors_unchanged_10_of_10": g12_anchor["pass_count"] == g12_anchor["case_count"] == 10,
        "development_case_discriminated": development == {"g11": False, "g13": True, "attributable": True},
        "candidate_materializes": base.can_materialize(candidate, p82),
    }
    checks["passed"] = all(checks.values())
    preflight_body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": candidate["artifact_digest"], "source_ot0345_receipt_digest": raw["receipt_digest"], "heldout_anchor": heldout, "g11_anchor": g11_anchor, "g12_anchor": g12_anchor, "development_case": development, "checks": checks}
    preflight = {**preflight_body, "receipt_digest": p82.digest(preflight_body)}
    if args.preflight_only:
        print(json.dumps(preflight, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0346 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", preflight)
    if not checks["passed"]:
        raise SystemExit("OT-0346 preflight failed")
    actor = copy.deepcopy(raw["actor"])
    actor["accepted"] = True
    actor["g11"] = {"authority": AUTHORITY, "challenger_accepted": True, "source_events_digest": object_digests["events"], "toolchain_cache_denial_attributed": True}
    child, consequence = base.compile_successor(candidate, actor, p82)
    operational = bool(
        actor["workspace_evaluation"]["semantic"]
        and actor["public_result"]["pass_count"] == actor["public_result"]["case_count"] == 3
        and actor["hidden_result"]["pass_count"] == actor["hidden_result"]["case_count"] == 5
        and base.can_materialize(child, p82)
        and child["active_world_seeking_stake"] == stranded["active_world_seeking_stake"]
        and child["active_world_seeking_stake"]["heldout_score"]["all_regimes"]["pass_count"] == 40
        and runtime.identity_conforms(child)
    )
    body = {"authority": AUTHORITY, "from_regime": "G12-plus-G11", "to_regime": AUTHORITY, "historical_rescoring": False, "source_ot0345_receipt_digest": raw["receipt_digest"], "preflight_receipt_digest": preflight["receipt_digest"], "source_object_digests": object_digests, "exact_denial_attribution": development, "reconstructed_actor": actor, "contact_consequence_receipt": consequence, "operational_transition_passed": operational, "observer_disposition": "corrected-operational-only" if operational else "rejected", "subject_disposition": child["continuation"]["status"] if operational else "lost", "final_subject_digest": child["artifact_digest"], "fresh_actor_count": 0}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    if operational:
        write_json(run / "open-subject-after-toolchain-denial-reconstruction.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
