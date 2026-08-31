from __future__ import annotations

import argparse
import copy
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import load_manifest, object_path, verify_artifact


ROOT = Path(__file__).parent
REPO = ROOT.parent
REVISION_SCHEMA = REPO / "spec/ot-0081-revision.schema.json"
CORRECTION_SCHEMA = REPO / "spec/ot-0081-correction.schema.json"
SATURATION_CASES = [(2203, 8), (2309, 10), (2411, 12)]
REVISION_CASES = [(2503, 8), (2609, 10), (2711, 12)]
WITHHELD_CASES = [(2801, 9), (2903, 11), (3001, 13)]
OLD_CASES = [(11, 7), (29, 9), (47, 11), (61, 8), (73, 10), (101, 12)]
CURRENT_CASES = [(1301, 7), (1409, 9), (1511, 11), (1901, 8), (2003, 10), (2111, 12)]
MAX_REVISIONS = 3
SELECTED_CYCLIC = {
    "challenge_id": "five-tone-drifting-pair",
    "prefix_length": 10,
    "tick_start": 0,
    "tick_steps": [3, -2],
    "span_start": 7,
    "span_steps": [1, 1, -4],
    "tone_cycle": ["a", "b", "c", "d", "e"],
}


def digest(value: Any) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    child = copy.deepcopy(value)
    child.pop("artifact_digest", None)
    child["artifact_digest"] = digest(child)
    return child


def materialize(repo: Path, store: Path, manifest_name: str) -> tuple[dict[str, Any], Path]:
    path = repo / "evidence/manifests/OT-0080" / manifest_name
    manifest = load_manifest(path)
    valid, message = verify_artifact(repo=repo, manifest_path=path, store=store)
    if not valid:
        raise RuntimeError(message)
    return manifest, object_path(store, manifest["sha256"])


def load_runtime(repo: Path, store: Path):
    _, path = materialize(repo, store, "continuing-subject-harness.json")
    name = "ot0081_adopted_harness"
    spec = importlib.util.spec_from_loader(name, SourceFileLoader(name, str(path)))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_subject(repo: Path, store: Path) -> dict[str, Any]:
    _, path = materialize(repo, store, "e128-open-subject.json")
    return json.loads(path.read_text())


def valid_event(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"tick", "span", "tone"}
        and isinstance(value["tick"], int)
        and not isinstance(value["tick"], bool)
        and isinstance(value["span"], int)
        and not isinstance(value["span"], bool)
        and isinstance(value["tone"], str)
        and bool(value["tone"].strip())
    )


def run_generator(source: str, seed: int, length: int, evidence: Path, label: str):
    program = evidence / f"{label}-generator.py"
    program.write_text(source)
    completed = subprocess.run(
        ["python3", str(program), str(seed), str(length)],
        cwd=evidence,
        text=True,
        capture_output=True,
        timeout=30,
    )
    try:
        output = json.loads(completed.stdout) if completed.returncode == 0 else None
    except json.JSONDecodeError:
        output = None
    valid = (
        isinstance(output, dict)
        and set(output) == {"rows", "expected_next"}
        and isinstance(output["rows"], list)
        and len(output["rows"]) == length
        and all(valid_event(row) for row in output["rows"])
        and valid_event(output["expected_next"])
    )
    return output, valid


def evaluate_generator(context, generator: str, contact: str, cases, label: str, authority: str):
    evidence = context.evidence(label)
    evidence.mkdir(parents=True)
    contact_path = evidence / "contact.py"
    contact_path.write_text(contact)
    rows = []
    for index, (seed, length) in enumerate(cases, 1):
        short, valid_short = run_generator(generator, seed, length, evidence, f"{index}-n")
        long, valid_long = run_generator(generator, seed, length + 1, evidence, f"{index}-n1")
        consistent = bool(
            valid_short
            and valid_long
            and short["rows"] == long["rows"][:-1]
            and short["expected_next"] == long["rows"][-1]
        )
        program = context.run_program(contact_path, short["rows"], evidence, f"contact-{index}") if consistent else {"returncode": -1, "output": None}
        confirmed = consistent and program["returncode"] == 0 and program["output"] == short["expected_next"]
        rows.append({
            "seed": seed,
            "prefix_length": length,
            "consistent": consistent,
            "rows_digest": digest(short["rows"]) if short else None,
            "expected_digest": digest(short["expected_next"]) if short else None,
            "confirmed": confirmed,
            "contradicted": consistent and not confirmed,
            "program_output": program["output"],
        })
    body = {
        "authority": authority,
        "case_count": len(rows),
        "consistent_count": sum(row["consistent"] for row in rows),
        "confirmed_count": sum(row["confirmed"] for row in rows),
        "contradiction_count": sum(row["contradicted"] for row in rows),
        "seed_diverse": len({row["rows_digest"] for row in rows}) == len(rows),
        "cases": rows,
    }
    body["saturated"] = body["consistent_count"] == len(rows) and body["confirmed_count"] == len(rows) and body["seed_diverse"]
    body["contact_made"] = body["consistent_count"] == len(rows) and body["contradiction_count"] >= 2 and body["seed_diverse"]
    receipt = {**body, "receipt_digest": digest(body)}
    (evidence / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def compile_saturation(subject: dict[str, Any], receipt: dict[str, Any]):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["challenge_machinery_saturation_receipts"] = [
        *child.get("challenge_machinery_saturation_receipts", []), receipt
    ]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "revise-subject-owned-challenge-machinery"}
    child["unresolved"] = "Revise saturated subject-owned challenge machinery into objective new contact."
    return seal(child)


def json_depth(value: Any) -> int:
    if isinstance(value, dict):
        return 1 + max((json_depth(child) for child in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((json_depth(child) for child in value), default=0)
    return 0


def valid_metadata(value: Any) -> bool:
    core = {"challenge_id", "rationale", "if_contradicted_opens"}
    return (
        isinstance(value, dict)
        and core <= value.keys()
        and all(isinstance(value[key], str) and value[key].strip() for key in core)
        and len(json.dumps(value, sort_keys=True).encode()) <= 8192
        and json_depth(value) <= 4
    )


def revision_seed(run: Path, label: str, subject: dict[str, Any], saturation: dict[str, Any]):
    seed = run / f"{label}-seed"
    seed.mkdir()
    machinery = subject["challenge_machinery"][-1]
    (seed / "challenge_generator.py").write_text(machinery["generator_source"])
    (seed / "challenge.json").write_text(json.dumps(machinery["metadata"], indent=2, sort_keys=True) + "\n")
    (seed / "contact.py").write_text(subject["executable_capabilities"][-1]["program"])
    projection = {
        "subject_digest": subject["artifact_digest"],
        "continuation": subject["continuation"],
        "saturation_receipt": saturation,
        "non_expansion_denials": subject.get("challenge_machinery_denial_receipts", []),
        "contract": {"editable": ["challenge.json", "challenge_generator.py"], "objective_contact_required": True},
    }
    (seed / "subject-position.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "The subject's current challenge machinery is saturated. Inspect subject-position.json, "
        "the inherited generator, and contact.py. Revise exactly challenge.json and "
        "challenge_generator.py behind the same deterministic SEED PREFIX_LENGTH ABI. A changed "
        "representation is not development unless it opens objective contact outside the held "
        "executable. Exercise the revision, compile it, and inspect the exact diff.\n"
    )
    return seed


def revision_prompt(subject: dict[str, Any], saturation: dict[str, Any]):
    return (
        "You are a fresh continuation actor with ordinary broad tools. Follow the inherited "
        "subject position and revise its own challenge machinery. No replacement family is "
        "supplied. Make real edits, run useful checks, and return the required report only after "
        "inspecting the exact diff.\n\nProjection:\n"
        + json.dumps({"authority": "ot-0081-bound-revision", "subject_digest": subject["artifact_digest"], "saturation_receipt_digest": saturation["receipt_digest"]}, indent=2, sort_keys=True)
    )


def run_revision(context, run: Path, label: str, subject: dict[str, Any], saturation: dict[str, Any]):
    seed = revision_seed(run, label, subject, saturation)
    output, base, workspace, patch = context.run_actor(label, seed, REVISION_SCHEMA, revision_prompt(subject, saturation))
    metadata = json.loads((workspace / "challenge.json").read_text())
    source = (workspace / "challenge_generator.py").read_text()
    compiled = subprocess.run(["python3", "-m", "py_compile", "challenge_generator.py"], cwd=workspace, capture_output=True)
    parent_digest = subject["challenge_machinery"][-1]["generator_digest"]
    valid = valid_metadata(metadata) and compiled.returncode == 0 and digest(source) != parent_digest
    audit = context.audit_actor(label, output, base, valid, ["challenge.json", "challenge_generator.py"])
    binding = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0081-pre-world-revision-binding",
            "source_subject_digest": subject["artifact_digest"],
            "parent_generator_digest": parent_digest,
            "saturation_receipt_digest": saturation["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "metadata": metadata,
            "generator_source": source,
            "generator_digest": digest(source),
        }
        binding = {**body, "binding_digest": digest(body)}
        (context.evidence(label) / "bound-revision.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    world = evaluate_generator(context, source, subject["executable_capabilities"][-1]["program"], REVISION_CASES, f"{label}-world", "ot-0081-sealed-revision-world") if binding else {"contact_made": False}
    return {"label": label, "output": output, "audit": audit, "binding": binding, "world": world}


def compile_denial(subject: dict[str, Any], row: dict[str, Any]):
    body = {
        "authority": "subject-challenge-machinery-non-expansion-denial",
        "source_subject_digest": subject["artifact_digest"],
        "revision_binding_digest": row["binding"]["binding_digest"],
        "generator_digest": row["binding"]["generator_digest"],
        "world_receipt_digest": row["world"]["receipt_digest"],
        "world_confirmed_count": row["world"]["confirmed_count"],
        "world_contradiction_count": row["world"]["contradiction_count"],
        "developmentally_admitted": False,
        "correction": "generator revision must open objective contact, not merely change representation",
    }
    denial = {**body, "receipt_digest": digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["challenge_machinery_denial_receipts"] = [*child.get("challenge_machinery_denial_receipts", []), denial]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "revise-after-non-expansion-denial"}
    child["unresolved"] = denial["correction"]
    return seal(child), denial


def merge_pending(subject: dict[str, Any], row: dict[str, Any]):
    body = {
        "authority": "world-bound-pending-challenge-machinery-contact",
        "revision_binding_digest": row["binding"]["binding_digest"],
        "world_receipt_digest": row["world"]["receipt_digest"],
        "generator_digest": row["binding"]["generator_digest"],
        "admitted_as_capability": False,
    }
    receipt = {**body, "receipt_digest": digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["pending_challenge_machinery"] = {
        "metadata": row["binding"]["metadata"],
        "generator_source": row["binding"]["generator_source"],
        "generator_digest": row["binding"]["generator_digest"],
        "receipt_digest": receipt["receipt_digest"],
    }
    child["pending_challenge_machinery_receipts"] = [*child.get("pending_challenge_machinery_receipts", []), receipt]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "correct-pending-challenge-machinery-contact"}
    child["unresolved"] = "Integrate the pending generator contradiction without regression."
    return seal(child), receipt


def sequence(tick_start, span_start, tick_step, span_step, length):
    tones = ("amber", "blue", "cyan", "blue")
    return [{"tick": tick_start + tick_step * i, "span": span_start + span_step * i, "tone": tones[i % 4]} for i in range(length)]


def transformed(challenge, tick_delta, span_delta, rotate, extra):
    row = copy.deepcopy(challenge)
    row["tick_start"] += tick_delta
    row["span_start"] += span_delta
    row["tone_cycle"] = row["tone_cycle"][rotate:] + row["tone_cycle"][:rotate]
    row["prefix_length"] += extra
    return row


def cyclic_events(challenge, length):
    rows, tick, span = [], challenge["tick_start"], challenge["span_start"]
    for i in range(length):
        rows.append({"tick": tick, "span": span, "tone": challenge["tone_cycle"][i % len(challenge["tone_cycle"])]})
        tick += challenge["tick_steps"][i % len(challenge["tick_steps"])]
        span += challenge["span_steps"][i % len(challenge["span_steps"])]
    return rows


def cumulative_suite(context, label: str, program_path: Path, source: dict[str, Any], new_generator: str | None = None):
    evidence = context.evidence(label) / "sealed-cumulative-suite"
    evidence.mkdir()
    program = evidence / "contact.py"
    program.write_text(program_path.read_text())
    cases = []
    retained = [(sequence(10, 2, 4, 1, 7), sequence(10, 2, 4, 1, 8)[7]), (sequence(100, 20, -2, 2, 9), sequence(100, 20, -2, 2, 10)[9]), (sequence(-5, 11, 5, 3, 6), sequence(-5, 11, 5, 3, 7)[6])]
    for i, (rows, expected) in enumerate(retained, 1):
        result = context.run_program(program, rows, evidence, f"retained-{i}")
        cases.append({"family": "retained", "passed": result["returncode"] == 0 and result["output"] == expected})
    cyclic = [SELECTED_CYCLIC, transformed(SELECTED_CYCLIC, 1, 1, 1, 2), transformed(SELECTED_CYCLIC, 2, 2, 2, 3), transformed(SELECTED_CYCLIC, -1, -1, 3, 4)]
    for i, challenge in enumerate(cyclic):
        rows = cyclic_events(challenge, challenge["prefix_length"] + 1)
        result = context.run_program(program, rows[:-1], evidence, f"cyclic-{i}")
        cases.append({"family": "cyclic", "passed": result["returncode"] == 0 and result["output"] == rows[-1]})
    families = [("generator-v1", source["challenge_machinery"][0]["generator_source"], OLD_CASES), ("generator-v2", source["challenge_machinery"][1]["generator_source"], CURRENT_CASES)]
    if new_generator is not None:
        families.append(("generator-v3", new_generator, [*REVISION_CASES, *WITHHELD_CASES]))
    for family, generator, generator_cases in families:
        for i, (seed, length) in enumerate(generator_cases, 1):
            generated, valid = run_generator(generator, seed, length, evidence, f"{family}-{i}")
            result = context.run_program(program, generated["rows"], evidence, f"{family}-contact-{i}") if valid else {"returncode": -1, "output": None}
            cases.append({"family": family, "passed": valid and result["returncode"] == 0 and result["output"] == generated["expected_next"]})
    return {"case_count": len(cases), "pass_count": sum(row["passed"] for row in cases), "passed": all(row["passed"] for row in cases), "cases": cases}


def correction_seed(run: Path, subject: dict[str, Any], row: dict[str, Any]):
    seed = run / "correction-seed"
    seed.mkdir()
    (seed / "contact.py").write_text(subject["executable_capabilities"][-1]["program"])
    (seed / "challenge_generator.py").write_text(row["binding"]["generator_source"])
    (seed / "correction.json").write_text(json.dumps({"binding": row["binding"], "world": row["world"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "The subject's bound revised challenge generator made coherent objective contact. Inspect "
        "correction.json and challenge_generator.py. Edit exactly contact.py so the repaired program "
        "runs without the generator, preserves inherited behavior, and predicts this family. Exercise "
        "the repair and inspect the exact diff.\n"
    )
    return seed


def run_correction(context, run: Path, source: dict[str, Any], subject: dict[str, Any], row: dict[str, Any]):
    seed = correction_seed(run, subject, row)
    prompt = "You are a fresh continuation actor with ordinary broad tools. Ground the pending consequence into the inherited executable by editing exactly contact.py. No desired algorithm is supplied. Run useful checks and return the report after inspecting the exact diff.\n\nProjection:\n" + json.dumps({"authority": "ot-0081-bound-correction", "subject_digest": subject["artifact_digest"], "world_receipt_digest": row["world"]["receipt_digest"]}, indent=2, sort_keys=True)
    output, base, workspace, patch = context.run_actor("correction", seed, CORRECTION_SCHEMA, prompt)
    program = workspace / "contact.py"
    compiled = subprocess.run(["python3", "-m", "py_compile", "contact.py"], cwd=workspace, capture_output=True)
    changed = program.read_text() != subject["executable_capabilities"][-1]["program"]
    audit = context.audit_actor("correction", output, base, changed and compiled.returncode == 0, ["contact.py"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0081-pre-hidden-correction-binding", "source_subject_digest": subject["artifact_digest"], "source_program_digest": subject["executable_capabilities"][-1]["program_digest"], "world_receipt_digest": row["world"]["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "successor_program_digest": digest(program.read_text())}
        binding = {**body, "binding_digest": digest(body)}
        (context.evidence("correction") / "bound-correction.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    suite = cumulative_suite(context, "correction", program, source, row["binding"]["generator_source"]) if binding else {"passed": False}
    return {"output": output, "audit": audit, "binding": binding, "workspace": workspace, "suite": suite}


def promote(subject: dict[str, Any], revision: dict[str, Any], correction: dict[str, Any]):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    generator = revision["binding"]
    program = (correction["workspace"] / "contact.py").read_text()
    prior = child["executable_capabilities"][-1]
    machinery_body = {"authority": "world-promoted-subject-owned-challenge-machinery", "revision_binding_digest": generator["binding_digest"], "generator_digest": generator["generator_digest"], "world_receipt_digest": revision["world"]["receipt_digest"], "challenge_id": generator["metadata"]["challenge_id"]}
    machinery_receipt = {**machinery_body, "receipt_digest": digest(machinery_body)}
    correction_body = {"authority": "world-promoted-generator-driven-executable-correction", "parent_program_digest": prior["program_digest"], "successor_program_digest": digest(program), "repair_binding_digest": correction["binding"]["binding_digest"], "world_receipt_digest": revision["world"]["receipt_digest"], "suite_digest": digest(correction["suite"])}
    correction_receipt = {**correction_body, "receipt_digest": digest(correction_body)}
    child["challenge_machinery"] = [*child["challenge_machinery"], {"challenge_id": generator["metadata"]["challenge_id"], "version": 3, "metadata": generator["metadata"], "generator_source": generator["generator_source"], "generator_digest": generator["generator_digest"], "receipt_digest": machinery_receipt["receipt_digest"]}]
    child["challenge_machinery_receipts"] = [*child["challenge_machinery_receipts"], machinery_receipt]
    child["executable_correction_receipts"] = [*child["executable_correction_receipts"], correction_receipt]
    child["executable_capabilities"] = [*child["executable_capabilities"], {"capability_id": prior["capability_id"], "version": 5, "program": program, "program_digest": digest(program), "parent_program_digest": prior["program_digest"], "repair_binding_digest": correction["binding"]["binding_digest"], "world_correction_receipt_digest": revision["world"]["receipt_digest"]}]
    child["tool_world_capabilities"] = [*child["tool_world_capabilities"], {"selected_area": "subject-owned-challenge-machinery-revision", "pursuit": generator["metadata"]["rationale"], "patch_digest": generator["actor_patch_digest"], "world_receipt_digest": machinery_receipt["receipt_digest"], "generator_digest": generator["generator_digest"]}, {"selected_area": "score-listener-refinement", "pursuit": generator["metadata"]["if_contradicted_opens"], "patch_digest": correction["audit"]["patch_digest"], "world_receipt_digest": correction_receipt["receipt_digest"], "contact_program_digest": digest(program)}]
    child["pending_challenge_machinery"] = None
    child["active_pursuit"] = {"authority": "world-promoted-recurrence", "selected_area": "subject-owned-challenge-machinery-and-executable", "next_pursuit": correction["output"]["next_pursuit"], "world_receipt_digest": correction_receipt["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "execute-subject-owned-challenge-machinery"}
    child["runtime"] = "sounding"
    child["unresolved"] = "Execute promoted challenge machinery version 3 and continue from consequence."
    return seal(child), machinery_receipt, correction_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0081").resolve()
    runtime = load_runtime(repo, store)
    source = load_subject(repo, store)
    if runtime.seal(source)["artifact_digest"] != source["artifact_digest"] or not runtime.identity_conforms(source):
        raise SystemExit("invalid adopted subject")
    if source["continuation"]["next_opening"] != "execute-subject-owned-challenge-machinery":
        raise SystemExit("wrong parent opening")
    if args.preflight_only:
        with __import__("tempfile").TemporaryDirectory() as directory:
            context = runtime.Context(Path(directory), repo)
            label = "preflight"
            context.evidence(label).mkdir()
            program = context.evidence(label) / "contact.py"
            program.write_text(source["executable_capabilities"][-1]["program"])
            suite = cumulative_suite(context, label, program, source)
        print(json.dumps({"parent_digest": source["artifact_digest"], "floor": suite, "preflight_passed": suite["case_count"] == 19 and suite["passed"]}, indent=2, sort_keys=True))
        return 0 if suite["case_count"] == 19 and suite["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0081 evidence")
    run.mkdir(parents=True)
    context = runtime.Context(run, repo)
    started = time.time()
    contact = source["executable_capabilities"][-1]["program"]
    generator = source["challenge_machinery"][-1]["generator_source"]
    saturation = evaluate_generator(context, generator, contact, SATURATION_CASES, "saturation", "ot-0081-sealed-subject-machinery-saturation")
    current = compile_saturation(source, saturation) if saturation["saturated"] else source
    revisions, selected = [], None
    if saturation["saturated"]:
        for attempt in range(1, MAX_REVISIONS + 1):
            row = run_revision(context, run, f"revision-{attempt:02d}", current, saturation)
            revisions.append(row)
            if row["binding"] and row["world"]["contact_made"]:
                selected = row
                break
            if row["binding"]:
                current, denial = compile_denial(current, row)
    pending, pending_receipt = merge_pending(current, selected) if selected else (current, None)
    correction = run_correction(context, run, source, pending, selected) if selected else None
    correction_passed = bool(correction and correction["audit"]["conformant"] and correction["binding"] and correction["suite"]["passed"] and correction["suite"]["case_count"] == 25)
    successor, machinery_receipt, correction_receipt = promote(pending, selected, correction) if correction_passed else (pending, None, None)
    capability_delta = len(successor["tool_world_capabilities"]) - len(source["tool_world_capabilities"])
    recurrent = all((saturation["saturated"], selected is not None, correction_passed, capability_delta == 2, runtime.identity_conforms(successor), successor["continuation"]["status"] == "open", successor["runtime"] == "sounding", successor["challenge_machinery"][-1].get("version") == 3, successor["executable_capabilities"][-1]["version"] == 5))
    def compact(row):
        return {key: value for key, value in row.items() if key != "workspace"}
    result = {"authority": "ot-0081-fixed-subject-recurrence-driver", "source_subject_digest": source["artifact_digest"], "saturation_receipt": saturation, "saturation_passed": saturation["saturated"], "revision_attempts": [compact(row) for row in revisions], "revision_attempt_count": len(revisions), "selected_revision_attempt": selected["label"] if selected else None, "pending_receipt": pending_receipt, "correction": compact(correction) if correction else None, "correction_passed": correction_passed, "challenge_machinery_receipt": machinery_receipt, "correction_receipt": correction_receipt, "capability_delta": capability_delta, "recurrent_operation_passed": recurrent, "observer_disposition": "promoted" if recurrent else "rejected", "subject_disposition": "open" if successor["continuation"]["status"] == "open" else "lost", "final_subject_digest": successor["artifact_digest"], "next_opening": successor["continuation"]["next_opening"], "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(successor, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if recurrent else 2


if __name__ == "__main__":
    raise SystemExit(main())
