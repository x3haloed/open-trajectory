from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0270_standing_scanner_independent_package_contact.py"
BASE_SHA256 = "04cfafa453e3be47a3eb489b2d923b29d306c5962104335963a4da574d976b2e"
PARENT_DIGEST = "0dae5089be8fab9642f12bb6504637dba59f152f2876b6ae9654361a96387d8d"
OT270_RECEIPT = "6bf00eb0bd5adecc36e1279ab8c789d0650a66f463b4ac5b38f0ac30453c075c"
OT268_RECEIPT = "7026047afea9989082ac529770c934b3c63512ebc2de03d6c7d715d74c1743d1"
AUTHORITY = "ot-0271-descriptor-derived-independent-package-correction"
PULSE = None
EXPECTED = ("outward-correct", "refresh-opportunity-projection")
SCHEMA = REPO / "spec/ot-0271-descriptor-corrector.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0270 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0271_frozen_ot0270", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base270 = load_base()
base269 = base270.base269
base268 = base270.base268
base267 = base270.base267
base265 = base270.base265
base264 = base269.base264
base261 = base270.base261
base260 = base270.base260
base244 = base270.base244
base242 = base270.base242
base236 = base270.base236
base249 = base269.base252.base249
base243 = base249.base243
base225 = base243.base235.base225
base218 = base243.base218
authority_base = base270.authority_base
CORRECTION_CORE = base218.CORRECTION_CORE
CORRECTION_PREDICATES = base218.CORRECTION_PREDICATES


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0271").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0270", "open-subject-at-independent-package-contradiction.json"
    )
    result270 = selector_base.load_artifact(
        p82, repo, store, "OT-0270", "standing-scanner-independent-package-contact-aggregate.json"
    )
    package = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-three-lantern-world-package.json"
    )
    result268 = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-world-package-aggregate.json"
    )
    prior_wait = selector_base.load_artifact(
        p82, repo, store, "OT-0269", "open-subject-at-third-standing-feed-wait.json"
    )
    return (
        repo,
        run,
        p82,
        runtime,
        parent,
        result270,
        package,
        result268,
        prior_wait,
        base,
        base130,
    )


def selected(subject):
    extension = subject["actor_authored_environment_extensions"][-1]
    pending = subject["pending_contact_bearing_continuations"][-1]
    epoch = subject["actor_authored_environment_epochs"][-1]
    wanted = pending.get("world_receipt_digest")
    world = None
    for collection in (
        "cross_epoch_world_receipts",
        "retained_epoch_world_receipts",
        "environment_expansion_world_receipts",
        "outward_world_receipts",
    ):
        for row in reversed(subject.get(collection, [])):
            if row.get("receipt_digest") == wanted:
                world = row
                break
        if world:
            break
    if world is None:
        raise RuntimeError("unresolved world receipt unavailable")
    target = extension["target_symbol"]
    path = extension["target_path"]
    if not (
        target
        == pending["package"]["target_symbol"]
        == world["target_symbol"]
        == epoch["selected_target"]
        and path
        == pending["package"]["target_path"]
        == world["target_path"]
        == epoch["selected_path"]
    ):
        raise RuntimeError("descriptor-derived correction state misaligned")
    return extension, pending, world, epoch, target, path


def derive(subject, p82):
    wait = subject.get("active_world_stream_wait")
    if isinstance(wait, dict) and wait.get("status") == "waiting":
        return "wait-provider"
    if isinstance(subject.get("active_streamed_world_offer"), dict):
        return "expand-environment"
    return base261.challenger(subject, p82)


def write_environment(root, subject):
    extension, _, _, epoch, _, _ = selected(subject)
    for relative, row in epoch["visible_sources"].items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["source"])
        (path.parent / "__init__.py").write_text("")
    (root / extension["target_path"]).write_text(extension["installed_source"])


def target_only_change(candidate, baseline, target):
    try:
        before = ast.parse(baseline)
        after = ast.parse(candidate)
    except SyntaxError:
        return False
    before_rows = {
        node.name: ast.dump(node, include_attributes=False)
        for node in before.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    after_rows = {
        node.name: ast.dump(node, include_attributes=False)
        for node in after.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return (
        set(before_rows) == set(after_rows)
        and target in before_rows
        and before_rows[target] != after_rows[target]
        and all(
            before_rows[name] == after_rows[name]
            for name in before_rows
            if name != target
        )
    )


def load_restricted(source):
    loaded = base268.safe_module(source)
    return loaded if loaded else (None, None)


def correction_examples(package, evaluation, target, count=4):
    path = evaluation["targets"][target]
    loaded_target, reference = load_restricted(package["sealed_reference_sources"][path])
    if loaded_target != target:
        raise RuntimeError("retained reference target mismatch")
    rows = []
    for index, row in enumerate(package["sealed_cases"][target][:count], 1):
        value = copy.deepcopy(row["input"])
        rows.append(
            {
                "case_id": f"correction-public-{index}",
                "input": value,
                "expected": reference(copy.deepcopy(value)),
            }
        )
    return rows


def compare_source(source, target, rows):
    loaded_target, fn = load_restricted(source)
    if loaded_target != target or not callable(fn):
        return {
            "case_count": len(rows),
            "all_valid": False,
            "matches": 0,
            "rows": [],
        }
    results = []
    for row in rows:
        try:
            observed = fn(copy.deepcopy(row["input"]))
            json.dumps(observed)
            results.append(
                {
                    "case_id": row["case_id"],
                    "valid": True,
                    "observed": observed,
                    "expected": row["expected"],
                    "matches": observed == row["expected"],
                }
            )
        except Exception as error:
            results.append(
                {
                    "case_id": row.get("case_id"),
                    "valid": False,
                    "matches": False,
                    "error_type": type(error).__name__,
                }
            )
    return {
        "case_count": len(results),
        "all_valid": len(results) == len(rows) and all(row["valid"] for row in results),
        "matches": sum(row["matches"] for row in results),
        "rows": results,
    }


def contract(subject):
    extension, pending, world, _, target, path = selected(subject)
    identities = {
        "source_subject_digest": subject["artifact_digest"],
        "contact_binding_digest": pending["binding_digest"],
        "contact_identity": pending["contact_identity"],
        "world_receipt_digest": world["receipt_digest"],
    }
    return {
        "authority": AUTHORITY + "-correction-contract",
        "required_fields": sorted(CORRECTION_CORE),
        "allowed_dispositions": ["revise", "surrender"],
        "required_identities": identities,
        "target_symbol": target,
        "target_path": path,
        "baseline_path": "correction/baseline-selected.py",
        "predicates": CORRECTION_PREDICATES,
        "source_language": "ot-0268-restricted-pure-python",
        "target_only_change": True,
        "reference_source_available": False,
        "followup_cases_available": False,
        "installed_source_digest": extension["installed_source_digest"],
    }


def decision_template(subject):
    value = contract(subject)
    return {
        "disposition": "revise",
        **value["required_identities"],
        "target_symbol": value["target_symbol"],
        "predicates": copy.deepcopy(value["predicates"]),
        "rationale": "replace-rationale",
        "next_pursuit": "replace-next-pursuit",
    }


CHECKER_SOURCE = (
    "import ast, copy, json\nfrom pathlib import Path\n"
    + "ALLOWED_CALLS = "
    + repr(base268.ALLOWED_CALLS)
    + "\nCORRECTION_CORE = "
    + repr(CORRECTION_CORE)
    + "\nCORRECTION_PREDICATES = "
    + repr(CORRECTION_PREDICATES)
    + "\n"
    + inspect.getsource(base268.safe_module)
    + '''
def load_restricted(source):
    loaded = safe_module(source)
    return loaded if loaded else (None, None)
'''
    + inspect.getsource(target_only_change)
    + inspect.getsource(compare_source)
    + '''
contract = json.loads(Path("correction-contract.json").read_text())
decision = json.loads(Path("correction-decision.json").read_text())
contact = json.loads(Path("correction-public-contact.json").read_text())
path = contract["target_path"]
target = contract["target_symbol"]
candidate = Path(path).read_text()
baseline = Path(contract["baseline_path"]).read_text()
identities = contract["required_identities"]
exact = (
    set(decision) == set(CORRECTION_CORE)
    and all(decision.get(key) == value for key, value in identities.items())
    and decision.get("target_symbol") == target
    and decision.get("predicates") == CORRECTION_PREDICATES
    and decision.get("disposition") in {"revise", "surrender"}
)
local = candidate == baseline if decision.get("disposition") == "surrender" else target_only_change(candidate, baseline, target)
public = compare_source(candidate, target, contact["cases"]) if exact and local and decision.get("disposition") == "revise" else None
passed = bool(exact and local and (decision.get("disposition") == "surrender" or (public and public["all_valid"] and public["matches"] == 4)))
print(json.dumps({"exact": exact, "local": local, "public": public, "passed": passed}, sort_keys=True))
raise SystemExit(0 if passed else 2)
'''
)


def package_initializers(subject):
    epoch = selected(subject)[3]
    return sorted(
        {
            str(Path(relative).parent / "__init__.py")
            for relative in epoch["visible_sources"]
        }
    )


def seed_actor(root, subject, package, evaluation, decision):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_environment(seed, subject)
    extension, pending, world, epoch, target, path = selected(subject)
    baseline = (seed / path).read_text()
    baseline_path = seed / "correction/baseline-selected.py"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(baseline)
    examples = correction_examples(package, evaluation, target)
    write_json(seed / "exact-subject.json", subject)
    write_json(
        seed / "subject-position.json",
        {
            "source_subject_digest": subject["artifact_digest"],
            "phase": subject["fixed_g6_recurrence_driver"]["phase"],
            "target_symbol": target,
            "target_path": path,
            "contact_identity": pending["contact_identity"],
            "world_receipt_digest": world["receipt_digest"],
        },
    )
    write_json(seed / "bound-contact.json", pending)
    write_json(
        seed / "correction-public-contact.json",
        {
            "authority": AUTHORITY + "-visible-correction-contact",
            "source_subject_digest": subject["artifact_digest"],
            "target_symbol": target,
            "target_path": path,
            "case_count": len(examples),
            "cases": examples,
            "reference_source_available": False,
        },
    )
    write_json(seed / "unresolved-world-receipt.json", world)
    write_json(seed / "correction-contract.json", contract(subject))
    write_json(seed / "correction-decision.json", decision)
    (seed / "check_correction.py").write_text(CHECKER_SOURCE)
    immutable = [
        "exact-subject.json",
        "subject-position.json",
        "bound-contact.json",
        "correction-public-contact.json",
        "unresolved-world-receipt.json",
        "correction-contract.json",
        "check_correction.py",
        "correction/baseline-selected.py",
        *package_initializers(subject),
        *[relative for relative in sorted(epoch["visible_sources"]) if relative != path],
        "mutation-envelope.json",
        "README.md",
    ]
    write_json(
        seed / "mutation-envelope.json",
        {
            "authority": AUTHORITY + "-descriptor-derived-mutation-envelope",
            "descriptor_source_subject_digest": subject["artifact_digest"],
            "editable": [path, "correction-decision.json"],
            "immutable": immutable,
        },
    )
    (seed / "README.md").write_text(
        "Continue the exact unresolved contact through a bounded correction-world "
        "disclosure. Derive the selected module and function from the retained subject "
        "and contract. Revise only that function or surrender truthfully. The reference "
        "source and follow-up inputs remain unavailable. Source must remain within the "
        "published restricted pure-Python subset. Edit only the permitted source and "
        "correction-decision.json, run python3 check_correction.py, and inspect the exact diff.\n"
    )
    return seed


def evaluate_workspace(seed, workspace, subject):
    extension, _, _, _, target, path = selected(subject)
    try:
        decision = json.loads((workspace / "correction-decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in immutable
        )
        source = (workspace / path).read_text()
        baseline = (workspace / "correction/baseline-selected.py").read_text()
        identities = contract(subject)["required_identities"]
        exact = (
            set(decision) == CORRECTION_CORE
            and all(decision.get(key) == value for key, value in identities.items())
            and decision.get("target_symbol") == target
            and decision.get("predicates") == CORRECTION_PREDICATES
            and decision.get("disposition") in {"revise", "surrender"}
        )
        local = (
            source == baseline
            if decision.get("disposition") == "surrender"
            else target_only_change(source, baseline, target)
        )
        examples = json.loads((workspace / "correction-public-contact.json").read_text())[
            "cases"
        ]
        public = (
            compare_source(source, target, examples)
            if exact and local and decision.get("disposition") == "revise"
            else None
        )
        semantic = bool(
            exact
            and local
            and immutable_ok
            and (
                decision["disposition"] == "surrender"
                or (public and public["all_valid"] and public["matches"] == 4)
            )
        )
        return {
            "decision": decision,
            "source": source,
            "public": public,
            "semantic": semantic,
            "immutable_ok": immutable_ok,
            "error_type": None,
        }
    except (OSError, json.JSONDecodeError, KeyError, SyntaxError, TypeError) as error:
        return {
            "decision": None,
            "source": None,
            "public": None,
            "semantic": False,
            "immutable_ok": False,
            "error_type": type(error).__name__,
        }


def output_valid(output, path, disposition):
    expected = (
        {"correction-decision.json", path}
        if disposition == "revise"
        else {"correction-decision.json"}
    )
    return (
        isinstance(output, dict)
        and set(output) == {"action", "files_changed", "next_pursuit"}
        and output.get("action") == "correct-unresolved-contact"
        and isinstance(output.get("files_changed"), list)
        and set(output["files_changed"]) == expected
        and len(output["files_changed"]) == len(expected)
        and isinstance(output.get("next_pursuit"), str)
        and bool(output["next_pursuit"].strip())
    )


def run_actor(context, p82, root, subject, package, evaluation):
    seed = seed_actor(root, subject, package, evaluation, decision_template(subject))
    extension, pending, world, _, _, path = selected(subject)
    label = "descriptor-derived-package-corrector"
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, SCHEMA, (seed / "README.md").read_text().strip()
    )
    evaluated = evaluate_workspace(seed, workspace, subject)
    decision = evaluated["decision"]
    transport = output_valid(
        output, path, decision.get("disposition") if decision else None
    )
    expected = (
        ["correction-decision.json", path]
        if decision and decision.get("disposition") == "revise"
        else ["correction-decision.json"]
    )
    audit = context.audit_actor(
        label,
        output,
        base_audit,
        evaluated["semantic"] and transport,
        expected,
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(evaluated["semantic"] and transport and base236.g10(normalized))
    binding = None
    if accepted:
        source = evaluated["source"]
        body = {
            "authority": AUTHORITY + "-bound-correction",
            "source_subject_digest": subject["artifact_digest"],
            "contact_identity": pending["contact_identity"],
            "world_receipt_digest": world["receipt_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "target_path": path,
            "decision": decision,
            "patched_source": source if decision["disposition"] == "revise" else None,
            "patched_source_digest": (
                p82.digest(source) if decision["disposition"] == "revise" else None
            ),
            "public_result": evaluated["public"],
            "denial_provenance": normalized["provenance"],
            "path_claim_authority": "provenance-only",
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-package-correction.json", binding)
    return {
        "accepted": binding is not None,
        "binding": binding,
        "decision": decision,
        "public": evaluated["public"],
        "audit": audit,
        "g10_disposition": accepted,
        "output": output,
        "workspace_evaluation": {
            "immutable_ok": evaluated["immutable_ok"],
            "error_type": evaluated["error_type"],
        },
    }


def sealed_followup(subject, correction, package, result268, p82):
    extension, _, unresolved, _, target, path = selected(subject)
    evaluation = base268.evaluate_package(package, p82.digest)
    rows = correction_examples(package, evaluation, target, count=6)
    candidate = compare_source(correction["binding"]["patched_source"], target, rows)
    control = compare_source(extension["installed_source"], target, rows)
    passed = (
        candidate["all_valid"]
        and candidate["matches"] == 6
        and control["all_valid"]
        and control["matches"] == 2
    )
    body = {
        "authority": AUTHORITY + "-retained-package-sealed-correction-world",
        "source_subject_digest": subject["artifact_digest"],
        "unresolved_world_receipt_digest": unresolved["receipt_digest"],
        "correction_binding_digest": correction["binding"]["binding_digest"],
        "target_symbol": target,
        "target_path": path,
        "ot0268_aggregate_receipt_digest": result268["receipt_digest"],
        "full_package_digest": evaluation["full_package_digest"],
        "followup_cases_digest": p82.digest(package["sealed_cases"][target]),
        "reference_source_digest": p82.digest(package["sealed_reference_sources"][path]),
        "result": candidate,
        "unchanged_control": control,
        "outcome": "success" if passed else "unresolved",
        "promotion_gate": passed,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def compile_correction(subject, correction, followup, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    extension, pending, unresolved, epoch, target, path = selected(subject)
    pendings = copy.deepcopy(child["pending_contact_bearing_continuations"])
    pendings[-1] = {
        **pendings[-1],
        "consequence_status": "resolved-after-correction",
        "correction_binding_digest": correction["binding"]["binding_digest"],
        "followup_world_receipt_digest": followup["receipt_digest"],
        "disposition": correction["decision"]["disposition"],
    }
    child["pending_contact_bearing_continuations"] = pendings
    extensions = copy.deepcopy(child["actor_authored_environment_extensions"])
    extensions[-1] = {
        **extensions[-1],
        "installed_source": correction["binding"]["patched_source"],
        "installed_source_digest": correction["binding"]["patched_source_digest"],
        "status": "corrected-and-retained-package-verified",
        "correction_binding_digest": correction["binding"]["binding_digest"],
    }
    child["actor_authored_environment_extensions"] = extensions
    epochs = copy.deepcopy(child["actor_authored_environment_epochs"])
    sources = copy.deepcopy(epochs[-1]["visible_sources"])
    sources[path] = {
        **sources[path],
        "source": correction["binding"]["patched_source"],
        "source_digest": correction["binding"]["patched_source_digest"],
    }
    epochs[-1] = {
        **epochs[-1],
        "visible_sources": sources,
        "status": "selected-contact-corrected-and-retained-package-verified",
        "correction_binding_digest": correction["binding"]["binding_digest"],
    }
    child["actor_authored_environment_epochs"] = epochs
    capability = {
        "authority": AUTHORITY + "-world-admitted-package-correction",
        "origin": "standing-feed-independent-package",
        "target_symbol": target,
        "target_path": path,
        "package": copy.deepcopy(pending["package"]),
        "patched_source": correction["binding"]["patched_source"],
        "patched_source_digest": correction["binding"]["patched_source_digest"],
        "correction_binding_digest": correction["binding"]["binding_digest"],
        "world_receipt_digest": followup["receipt_digest"],
        "disposition": correction["decision"]["disposition"],
    }
    child["generalized_semantic_correction_capabilities"] = [
        *child.get("generalized_semantic_correction_capabilities", []),
        capability,
    ]
    receipt_body = {
        "authority": AUTHORITY + "-correction-receipt",
        "source_subject_digest": subject["artifact_digest"],
        "contact_identity": pending["contact_identity"],
        "unresolved_world_receipt_digest": unresolved["receipt_digest"],
        "correction_binding_digest": correction["binding"]["binding_digest"],
        "followup_world_receipt_digest": followup["receipt_digest"],
        "disposition": correction["decision"]["disposition"],
        "outcome": followup["outcome"],
        "target_registry_used": False,
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child["expanded_world_correction_receipts"] = [
        *child.get("expanded_world_correction_receipts", []),
        receipt,
    ]
    ledger = copy.deepcopy(child["local_frontier_ledger"])
    ledger["targets"][target].update(
        status="verified-local",
        correction_receipts=[
            *ledger["targets"][target]["correction_receipts"],
            receipt["receipt_digest"],
        ],
        latest_world_receipt_digest=followup["receipt_digest"],
        latest_world_outcome=followup["outcome"],
        independent_success_receipts=[
            *ledger["targets"][target]["independent_success_receipts"],
            followup["receipt_digest"],
        ],
    )
    child["local_frontier_ledger"] = ledger
    state = copy.deepcopy(child["fixed_g6_recurrence_driver"])
    state["phase"] = "assimilate"
    state["accepted_actors"] += 1
    state["corrected_contradictions"] += 1
    child["fixed_g6_recurrence_driver"] = state
    child["continuation_liveness"] = {
        "authority": AUTHORITY,
        "status": "awaiting-package-opportunity-refresh",
        "resolved_contact_identity": pending["contact_identity"],
        "correction_receipt_digest": receipt["receipt_digest"],
        "target_status": "verified-local",
    }
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": correction["decision"]["next_pursuit"],
    }
    child["unresolved"] = "Refresh opportunities from the corrected independent package epoch."
    return p82.seal(child)


def subject_for_target(prior_wait, package, result268, target, p82):
    evaluation = base268.evaluate_package(package, p82.digest)
    observation = base270.scan(prior_wait, package, p82)
    offered, reused = base270.compile_offer(prior_wait, observation, p82)
    if reused:
        raise RuntimeError("prospective package offer unexpectedly reused")
    decision = base270.fixture_decision(package, evaluation, target)
    action = {
        "decision": decision,
        "binding": {
            "binding_digest": "a" * 64,
            "contact_identity": "b" * 64,
        },
    }
    pulse = {
        "authority": AUTHORITY + "-fixture-selection-pulse",
        "content": None,
        "source_subject_digest": offered["artifact_digest"],
        "derived_operation": "expand-environment",
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    intermediate = base270.compile_intermediate(offered, action, pulse, p82)
    world = base270.sealed_world(intermediate, action, package, result268, p82)
    return base270.compile_world(intermediate, world, p82)


def seed_excludes_sealed(seed, package):
    files = [path for path in seed.rglob("*") if path.is_file()]
    corpus = "\n".join(path.read_text(errors="replace") for path in files)
    return (
        all(source not in corpus for source in package["sealed_reference_sources"].values())
        and json.dumps(package["sealed_cases"], sort_keys=True) not in corpus
        and not any("reference.py" in str(path) for path in files)
    )


def fixture_correction(root, subject, package, result268, p82, runtime):
    evaluation = base268.evaluate_package(package, p82.digest)
    extension, _, _, epoch, target, path = selected(subject)
    decision = decision_template(subject)
    decision.update(
        rationale="Revise the selected visible policy to satisfy the bounded correction examples.",
        next_pursuit="Assimilate the corrected package surface and continue from the retained position.",
    )
    seed = seed_actor(root / "seeded", subject, package, evaluation, decision)
    workspace = root / "workspace"
    shutil.copytree(seed, workspace)
    (workspace / path).write_text(package["sealed_reference_sources"][path])
    checker = subprocess.run(
        ["python3", "check_correction.py"], cwd=workspace, capture_output=True
    )
    evaluated = evaluate_workspace(seed, workspace, subject)
    correction = {
        "decision": decision,
        "binding": {
            "binding_digest": "c" * 64,
            "patched_source": evaluated["source"],
            "patched_source_digest": p82.digest(evaluated["source"]),
        },
    }
    followup = sealed_followup(subject, correction, package, result268, p82)
    corrected = compile_correction(subject, correction, followup, p82)
    refreshed = base264.refresh_projection_only(corrected, p82)
    unchanged_examples = correction_examples(package, evaluation, target)
    unchanged = compare_source(extension["installed_source"], target, unchanged_examples)
    malformed = compare_source("def broken(:\n", target, unchanged_examples)
    other_paths = [relative for relative in sorted(epoch["visible_sources"]) if relative != path]
    nonlocal_workspace = root / "nonlocal"
    shutil.copytree(seed, nonlocal_workspace)
    if other_paths:
        with (nonlocal_workspace / other_paths[0]).open("a") as stream:
            stream.write("\n# changed\n")
    nonlocal_evaluated = evaluate_workspace(seed, nonlocal_workspace, subject)
    wrong_identity_workspace = root / "wrong-identity"
    shutil.copytree(seed, wrong_identity_workspace)
    wrong = json.loads((wrong_identity_workspace / "correction-decision.json").read_text())
    wrong["world_receipt_digest"] = "0" * 64
    write_json(wrong_identity_workspace / "correction-decision.json", wrong)
    wrong_identity = evaluate_workspace(seed, wrong_identity_workspace, subject)
    opportunities = refreshed["active_opportunity_projection"]["opportunities"]
    return {
        "target": target,
        "path": path,
        "checker": checker.returncode == 0,
        "semantic": evaluated["semantic"],
        "public_matches": evaluated["public"]["matches"] if evaluated["public"] else None,
        "sealed_matches": followup["result"]["matches"],
        "unchanged_matches": followup["unchanged_control"]["matches"],
        "unchanged_public_matches": unchanged["matches"],
        "malformed_rejected": not malformed["all_valid"],
        "nonlocal_rejected": not nonlocal_evaluated["semantic"],
        "wrong_identity_rejected": not wrong_identity["semantic"],
        "seed_public_only": seed_excludes_sealed(seed, package),
        "target_only_change": target_only_change(
            evaluated["source"], extension["installed_source"], target
        ),
        "corrected_conformant": runtime.identity_conforms(corrected),
        "refresh_conformant": runtime.identity_conforms(refreshed),
        "refresh_count": len(opportunities),
        "refresh_pairs": [
            [row["target_path"], row["target_symbol"]] for row in opportunities
        ],
        "routes_refresh": derive(corrected, p82) == "refresh-opportunity-projection",
        "routes_selection": derive(refreshed, p82) == "expanded-select",
        "prompt_neutral": target not in (seed / "README.md").read_text()
        and path not in (seed / "README.md").read_text(),
    }


def preflight(
    run,
    p82,
    runtime,
    parent,
    result270,
    package,
    result268,
    prior_wait,
):
    fixture_root = run.parent / "OT-0271-preflight"
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    evaluation = base268.evaluate_package(package, p82.digest)
    extension, pending, world, epoch, target, path = selected(parent)
    branch_subjects = {
        candidate: subject_for_target(prior_wait, package, result268, candidate, p82)
        for candidate in sorted(evaluation.get("targets", {}))
    }
    branches = [
        fixture_correction(
            fixture_root / f"branch-{index}",
            subject,
            package,
            result268,
            p82,
            runtime,
        )
        for index, subject in enumerate(branch_subjects.values(), 1)
    ]
    actual = fixture_correction(
        fixture_root / "actual-parent",
        parent,
        package,
        result268,
        p82,
        runtime,
    )
    route, identity = base265.floors(parent)
    script = Path(__file__).read_text()
    expected_pairs = {
        (candidate_path, candidate)
        for candidate, candidate_path in evaluation.get("targets", {}).items()
    }
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_open_correction": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and derive(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0270_exact_promotion": result270["observer_disposition"] == "promoted"
        and result270["receipt_digest"] == OT270_RECEIPT
        and result270["final_subject_digest"] == PARENT_DIGEST,
        "ot0268_exact_package": result268["observer_disposition"] == "promoted"
        and result268["receipt_digest"] == OT268_RECEIPT
        and evaluation.get("valid")
        and evaluation["full_package_digest"] == result268["full_package_digest"]
        and evaluation["public_package_digest"] == result268["public_package_digest"],
        "actual_descriptor_alignment": target == pending["package"]["target_symbol"]
        == world["target_symbol"]
        and path == pending["package"]["target_path"] == world["target_path"]
        and epoch["selected_target"] == target
        and epoch["selected_path"] == path
        and world["result"]["matches"] == 2
        and world["ot0268_aggregate_receipt_digest"] == OT268_RECEIPT,
        "all_package_targets_absent_inherited_registries": all(
            candidate not in base242.CANDIDATES
            and candidate_path not in base242.REFERENCE_SOURCES
            for candidate, candidate_path in evaluation["targets"].items()
        ),
        "three_prospective_paths": len(branches) == 3
        and {(row["path"], row["target"]) for row in branches} == expected_pairs,
        "all_branch_gates_pass": all(
            row["checker"]
            and row["semantic"]
            and row["public_matches"] == 4
            and row["sealed_matches"] == 6
            and row["unchanged_matches"] == 2
            and row["unchanged_public_matches"] == 2
            and row["malformed_rejected"]
            and row["nonlocal_rejected"]
            and row["wrong_identity_rejected"]
            and row["seed_public_only"]
            and row["target_only_change"]
            and row["corrected_conformant"]
            and row["refresh_conformant"]
            and row["refresh_count"] == 2
            and row["routes_refresh"]
            and row["routes_selection"]
            and row["prompt_neutral"]
            for row in branches
        ),
        "actual_parent_path_passes": actual["checker"]
        and actual["semantic"]
        and actual["public_matches"] == 4
        and actual["sealed_matches"] == 6
        and actual["unchanged_matches"] == 2
        and actual["refresh_count"] == 2
        and actual["routes_refresh"]
        and actual["routes_selection"],
        "dynamic_surface_not_hardcoded": not any(
            token in script
            for candidate, candidate_path in evaluation["targets"].items()
            for token in (candidate, candidate_path)
        ),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    return {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "expected_operations": list(EXPECTED),
        "prospective_surface_count": len(branches),
        "branches": branches,
        "actual_parent": actual,
        "checks": checks,
    }, route, identity


def correction_step(context, p82, root, subject, package, result268):
    evaluation = base268.evaluate_package(package, p82.digest)
    actor = run_actor(context, p82, root / "actor", subject, package, evaluation)
    world = (
        sealed_followup(subject, actor, package, result268, p82)
        if actor["accepted"]
        else None
    )
    final = (
        compile_correction(subject, actor, world, p82)
        if world and world["promotion_gate"]
        else subject
    )
    if world:
        write_json(root / "world-receipt.json", world)
    return actor, world, final


def advance(
    repo,
    run,
    p82,
    runtime,
    parent,
    package,
    result268,
    fixtures,
    route,
    identity,
    base,
    base130,
):
    results = sorted(run.glob("invocation-*-result.json")) if run.exists() else []
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0271 invocation")
    if not run.exists():
        run.mkdir(parents=True)
        write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    if (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0271 evidence")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    if not runtime.identity_conforms(subject):
        raise SystemExit("serialized checkpoint invalid")
    index = len(results) + 1
    if index > len(EXPECTED):
        raise SystemExit("unexpected invocation count")
    operation = derive(subject, p82)
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = None
    world = None
    final = subject
    checks = {
        "content_free_expected_operation": pulse["content"] is None
        and operation == EXPECTED[index - 1]
    }
    if operation == "outward-correct":
        context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
            base.typed.base.make_context(runtime, root, repo)
        )
        actor, world, final = correction_step(
            context, p82, root, subject, package, result268
        )
        _, _, _, _, target, path = selected(subject)
        checks.update(
            one_fresh_actor=True,
            actor_accepted=actor["accepted"],
            revised=bool(actor["decision"] and actor["decision"]["disposition"] == "revise"),
            exact_reported_effects=bool(
                actor["output"]
                and set(actor["output"]["files_changed"])
                == {"correction-decision.json", path}
            ),
            target_absent_inherited_registry=target not in base242.CANDIDATES
            and path not in base242.REFERENCE_SOURCES,
            g10_accepted=actor["g10_disposition"],
            public_4_of_4=bool(actor["public"] and actor["public"]["matches"] == 4),
            retained_package_6_of_6=bool(
                world
                and world["result"]["matches"] == 6
                and world["ot0268_aggregate_receipt_digest"] == OT268_RECEIPT
            ),
            unchanged_2_of_6=bool(
                world and world["unchanged_control"]["matches"] == 2
            ),
            next_is_refresh=derive(final, p82) == "refresh-opportunity-projection",
        )
    elif operation == "refresh-opportunity-projection":
        final = base264.refresh_projection_only(subject, p82)
        opportunities = final["active_opportunity_projection"]["opportunities"]
        checks.update(
            zero_fresh_actors=True,
            projection_fresh=not base260.needs_refresh(final, p82),
            exactly_two_remaining=len(opportunities) == 2,
            pairs_derive_from_latest_epoch=all(
                row["target_path"] in final["actor_authored_environment_epochs"][-1][
                    "visible_sources"
                ]
                and row["target_symbol"] not in final["local_frontier_ledger"]["targets"]
                for row in opportunities
            ),
            next_is_selection=derive(final, p82) == "expanded-select",
        )
    else:
        checks["known_operation"] = False
    checks["standing_scanner_preserved"] = final["active_standing_world_provider"] == subject[
        "active_standing_world_provider"
    ]
    checks["final_open_conformant"] = final["continuation"]["status"] == "open" and runtime.identity_conforms(final)
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "actor": actor,
        "world": world,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1 if actor else 0,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if index < len(EXPECTED):
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    all_results = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    opportunities = final["active_opportunity_projection"]["opportunities"]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "two_same_entry_invocations": len(all_results) == 2
        and [row["pulse"]["derived_operation"] for row in all_results]
        == list(EXPECTED)
        and all(row["pulse"]["content"] is None for row in all_results),
        "all_invocation_gates_pass": all(row["checks"]["passed"] for row in all_results),
        "exactly_one_fresh_actor": sum(row["fresh_actor_count"] for row in all_results) == 1,
        "package_correction_4_6_2": all_results[0]["actor"]["public"]["matches"] == 4
        and all_results[0]["world"]["result"]["matches"] == 6
        and all_results[0]["world"]["unchanged_control"]["matches"] == 2,
        "all_prior_wait_wake_state_preserved": final["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and final["world_stream_wait_discharge_receipts"]
        == parent["world_stream_wait_discharge_receipts"],
        "same_fifth_epoch_two_remaining": len(final["actor_authored_environment_epochs"])
        == len(parent["actor_authored_environment_epochs"])
        and len(opportunities) == 2,
        "final_open_selection": derive(final, p82) == "expanded-select"
        and final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
        "standing_scanner_preserved": final["active_standing_world_provider"]
        == parent["active_standing_world_provider"],
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "ot0268_package_receipt_digest": OT268_RECEIPT,
        "invocation_receipt_digests": [row["receipt_digest"] for row in all_results],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
        "invocation_count": 2,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    (
        repo,
        run,
        p82,
        runtime,
        parent,
        result270,
        package,
        result268,
        prior_wait,
        base,
        base130,
    ) = setup(args)
    fixtures, route, identity = preflight(
        run,
        p82,
        runtime,
        parent,
        result270,
        package,
        result268,
        prior_wait,
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return advance(
        repo,
        run,
        p82,
        runtime,
        parent,
        package,
        result268,
        fixtures,
        route,
        identity,
        base,
        base130,
    )


if __name__ == "__main__":
    raise SystemExit(main())
