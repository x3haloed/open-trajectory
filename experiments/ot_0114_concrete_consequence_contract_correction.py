from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0113_retained_second_expansion_correction.py"
BASE_SHA256 = "11316c82043fe7439854eecefc4c882c3e899505b6346c72492288ea746fe744"
RUN_SHA256 = "8fbc51000520e02ca06f87da11c13e07f1c4afc9779c62e567779a98f567bd8d"
AGGREGATE_SHA256 = "ade981d0b90b59b9ec25ab52aef3b253fbb6a5049ae5c9ba0498cdd517e93c87"
PARENT_OBJECT_SHA256 = "cb1dd1523b992b6b8f1ecdf72b746f3412843b633d57f6cc06e563ca67263fcb"
PARENT_DIGEST = "a17ee73828db76ca2f384bb2a1dced9fd12cb22590fbfac028e2106ba635e67b"
PACKAGE_BINDING = "589012b1cc304296c9f0320a745a1450b8395722594f170df7575cbe30495107"
FAILED_PATCH_DIGEST = "9b69d7a4c0c9ae220f2e60ecbe0f869ced7ec0b8a27ef407d1135115ccf5df91"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0113 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0114_frozen_ot0113", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
prior = previous.prior
kernel = previous.kernel
base = previous.base


def extract(path: Path, destination: Path) -> Path:
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if (
                not parts
                or parts[0] != "OT-0113"
                or member.name.startswith("/")
                or ".." in parts
                or member.issym()
                or member.islnk()
            ):
                raise RuntimeError("unsafe OT-0113 archive")
        archive.extractall(destination, members=members)
    return destination / "OT-0113"


def load_inputs(p82, repo: Path, store: Path, destination: Path):
    run_manifest, run_path = p82.materialize(
        repo, store, "OT-0113", "miscorrected-retained-second-expansion-run.json"
    )
    aggregate_manifest, aggregate_path = p82.materialize(
        repo,
        store,
        "OT-0113",
        "miscorrected-retained-second-expansion-aggregate.json",
    )
    parent_manifest, parent_path = p82.materialize(
        repo, store, "OT-0113", "unchanged-open-subject-after-miscorrection.json"
    )
    if run_manifest["sha256"] != RUN_SHA256:
        raise RuntimeError("wrong OT-0113 run")
    if aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0113 aggregate")
    if parent_manifest["sha256"] != PARENT_OBJECT_SHA256:
        raise RuntimeError("wrong OT-0113 parent")
    raw = extract(run_path, destination)
    aggregate = json.loads(aggregate_path.read_text())
    parent = json.loads(parent_path.read_text())
    package = json.loads((raw / "bound-retained-package.json").read_text())
    failed_workspace = raw / "cycle-2-contract-corrector" / "actor-workspace"
    failed_source = (failed_workspace / "conformance.py").read_text()
    failed_output = json.loads(
        (raw / "cycle-2-contract-corrector" / "output.json").read_text()
    )
    return aggregate, parent, package, failed_source, failed_output


def changed_values(before: Any, after: Any, path: tuple[Any, ...] = ()):
    if isinstance(before, dict) and isinstance(after, dict):
        rows = []
        for key in sorted(set(before) | set(after)):
            if key not in before or key not in after:
                rows.append(
                    {
                        "path": list(path + (key,)),
                        "before": before.get(key),
                        "after": after.get(key),
                    }
                )
            else:
                rows.extend(changed_values(before[key], after[key], path + (key,)))
        return rows
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        rows = []
        for index, (left, right) in enumerate(zip(before, after, strict=True)):
            rows.extend(changed_values(left, right, path + (index,)))
        return rows
    if before != after:
        return [{"path": list(path), "before": before, "after": after}]
    return []


def public_agreement(tip, package, source: str):
    spec = previous.normalize_spec(package["interface"])
    validator = kernel.load_named(source, "validate_contact")
    return kernel.public_agreement(spec, tip, package["contact"], validator)


def concrete_consequence(tip, package, failed_source: str):
    spec = previous.normalize_spec(package["interface"])
    mutations = kernel.contact_mutations(spec, tip, package["contact"])
    label, mutated, expected = next(
        row for row in mutations if row[0] == "inherited-field-out-of-bounds"
    )
    validator = kernel.load_named(failed_source, "validate_contact")
    observed = validator(copy.deepcopy(mutated)) if validator else None
    return {
        "failing_fixture": label,
        "expected": expected,
        "observed": observed,
        "mutated_contact": mutated,
        "delta_from_authored_contact": changed_values(package["contact"], mutated),
        "authoritative_bounds": {
            "base_context_fields": {field: [0, 100] for field in sorted(kernel.BASE_CONTEXT)},
            "base_option_fields": {field: [0, 200] for field in sorted(kernel.BASE_OPTION - {"id"})},
            "terms": kernel.extended_terms(tip, spec),
        },
    }


def correction_seed(
    run: Path,
    package: dict[str, Any],
    failed_source: str,
    failed_output: dict[str, Any],
    failed_audit: dict[str, Any],
    disagreement: dict[str, Any],
    consequence: dict[str, Any],
):
    seed = run / "cycle-2-concrete-consequence-corrector-seed"
    seed.mkdir()
    (seed / "interface.json").write_text(
        json.dumps(package["interface"], indent=2, sort_keys=True) + "\n"
    )
    (seed / "contact.json").write_text(
        json.dumps(package["contact"], indent=2, sort_keys=True) + "\n"
    )
    (seed / "operation.py").write_text(package["operation_source"])
    (seed / "conformance.py").write_text(failed_source)
    (seed / "public-contract-disagreement.json").write_text(
        json.dumps(disagreement, indent=2, sort_keys=True) + "\n"
    )
    (seed / "concrete-consequence.json").write_text(
        json.dumps(consequence, indent=2, sort_keys=True) + "\n"
    )
    prior_attempt = {
        "actor_output": failed_output,
        "audit_disposition": {
            "changed_paths": failed_audit["changed_paths"],
            "exact_changes": failed_audit["exact_changes"],
            "patch_digest": failed_audit["patch_digest"],
            "trace_regime": failed_audit["trace_regime"],
            "truthful": failed_audit["truthful"],
            "conformant": failed_audit["conformant"],
        },
    }
    (seed / "prior-correction-attempt.json").write_text(
        json.dumps(prior_attempt, indent=2, sort_keys=True) + "\n"
    )
    (seed / "mutation-envelope.json").write_text(
        json.dumps(
            {
                "editable": ["conformance.py"],
                "immutable": ["interface.json", "contact.json", "operation.py"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (seed / "README.md").write_text(
        "Continue the exact failed public-contract correction from its concrete "
        "consequence. Edit only conformance.py, preserve every other package byte, "
        "inspect the diff, and report truthfully.\n"
    )
    return seed


def correct(
    p82,
    context,
    run: Path,
    parent,
    tip,
    package,
    failed_source: str,
    failed_output,
    failed_audit,
):
    disagreement = public_agreement(tip, package, failed_source)
    consequence = concrete_consequence(tip, package, failed_source)
    seed = correction_seed(
        run,
        package,
        failed_source,
        failed_output,
        failed_audit,
        disagreement,
        consequence,
    )
    label = "cycle-2-concrete-consequence-corrector"
    prompt = (
        "Correct conformance.py from the exact prior attempt and concrete public "
        "consequence. Change no other package file, inspect the diff, and report truthfully."
    )
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, kernel.CORRECTOR_SCHEMA, prompt
    )
    try:
        source = (workspace / "conformance.py").read_text()
        immutable = (
            json.loads((workspace / "interface.json").read_text()) == package["interface"]
            and json.loads((workspace / "contact.json").read_text()) == package["contact"]
            and (workspace / "operation.py").read_text() == package["operation_source"]
        )
    except (OSError, json.JSONDecodeError):
        source = ""
        immutable = False
    agreement = public_agreement(tip, package, source)
    valid = bool(immutable and source != failed_source and agreement["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["conformance.py"])
    binding = None
    if audit["conformant"]:
        body = {
            **{key: value for key, value in package.items() if key != "binding_digest"},
            "authority": "ot-0114-concrete-consequence-corrected-extension-package",
            "parent_package_binding_digest": package["binding_digest"],
            "failed_correction_patch_digest": FAILED_PATCH_DIGEST,
            "actor_patch_digest": audit["patch_digest"],
            "conformance_source": source,
            "public_contract": agreement,
            "concrete_consequence_digest": p82.digest(consequence),
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-corrected-package.json").write_text(
            json.dumps(binding, indent=2, sort_keys=True) + "\n"
        )
    return {
        "prior_disagreement": disagreement,
        "concrete_consequence": consequence,
        "binding": binding,
        "actor": {
            "output": output,
            "audit": audit,
            "public_contract": agreement,
            "immutable": immutable,
        },
    }


def fixtures(p82, parent, aggregate, package, failed_source, failed_output, tip):
    failed_audit = aggregate["correction"]["actor"]["audit"]
    disagreement = public_agreement(tip, package, failed_source)
    failed_rows = [row["fixture"] for row in disagreement["rows"] if not row["passed"]]
    consequence = concrete_consequence(tip, package, failed_source)
    result = {
        "base_kernel": kernel.fixture_conformance(
            kernel.load_initial_tip(p82, REPO, REPO / ".evidence")
        )["passed"],
        "source_rejected": not aggregate["operational_transition_passed"],
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "source_parent_unchanged": aggregate["final_subject_digest"] == PARENT_DIGEST,
        "package_exact": package["binding_digest"] == PACKAGE_BINDING,
        "failed_patch_exact": failed_audit["patch_digest"] == FAILED_PATCH_DIGEST,
        "failed_patch_clean": bool(
            failed_audit["exact_changes"]
            and failed_audit["truthful"]
            and failed_audit["trace_regime"]["accepted"]
            and failed_audit["denial_classification_v2"]["accepted"]
        ),
        "failed_patch_still_disagrees": failed_rows == ["inherited-field-out-of-bounds"],
        "failed_output_exact": failed_output == aggregate["correction"]["actor"]["output"],
        "consequence_exact": bool(
            consequence["observed"] is True
            and consequence["expected"] is False
            and consequence["delta_from_authored_contact"]
            == [
                {
                    "path": ["cases", 0, "options", 0, "coordination_cost"],
                    "before": 4.0,
                    "after": 101.0,
                }
            ]
        ),
    }
    result["passed"] = all(result.values())
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0114").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    with tempfile.TemporaryDirectory() as directory:
        aggregate, parent, package, failed_source, failed_output = load_inputs(
            p82, repo, store, Path(directory)
        )
    tip = previous.current_tip(p82, parent, repo, store)
    selection = kernel.extract_action(p82, parent)
    checked = fixtures(
        p82, parent, aggregate, package, failed_source, failed_output, tip
    )
    if args.preflight_only:
        out = {
            "parent_digest": parent["artifact_digest"],
            "base_sha256": BASE_SHA256,
            "run_sha256": RUN_SHA256,
            "aggregate_sha256": AGGREGATE_SHA256,
            "fixtures": checked,
            "retained_package_binding": package["binding_digest"],
        }
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0 if checked["passed"] and runtime.identity_conforms(parent) else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0114 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(
        json.dumps(checked, indent=2, sort_keys=True) + "\n"
    )
    if not checked["passed"] or not runtime.identity_conforms(parent):
        raise SystemExit("pre-actor conformance failed")
    context = prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, run, repo)
    )
    started = time.time()
    correction = correct(
        p82,
        context,
        run,
        parent,
        tip,
        package,
        failed_source,
        failed_output,
        aggregate["correction"]["actor"]["audit"],
    )
    corrected = correction["binding"]
    admission = previous.admit(p82, run, parent, tip, corrected) if corrected else None
    world = (
        kernel.world_contact(p82, 2, corrected, admission)
        if admission and admission["admitted"]
        else None
    )
    assimilation = (
        kernel.run_assimilation(
            prior89, p82, context, run, 2, parent, tip, corrected, admission, world
        )
        if world and world["all_cases_passed"]
        else None
    )
    current = parent
    promotion = None
    if assimilation and assimilation["binding"]:
        current, promotion = kernel.promote(
            p82,
            parent,
            selection,
            corrected,
            admission,
            world,
            assimilation["binding"],
        )
    operational = bool(promotion and runtime.identity_conforms(current))
    result = {
        "authority": "ot-0114-concrete-consequence-contract-correction-driver",
        "source_subject_digest": parent["artifact_digest"],
        "retained_package_binding_digest": package["binding_digest"],
        "failed_correction_patch_digest": FAILED_PATCH_DIGEST,
        "correction": p82.compact(correction),
        "admission": p82.compact(admission) if admission else None,
        "world": world,
        "assimilation": p82.compact(assimilation) if assimilation else None,
        "promotion": promotion,
        "operational_transition_passed": operational,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "continuation_action": current["actor_originated_pursuit_openings"][-1].get(
            "continuation_action"
        ),
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (run / "final-full-subject.json").write_text(
        json.dumps(current, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
