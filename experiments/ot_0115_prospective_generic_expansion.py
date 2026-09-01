from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import secrets
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0114_concrete_consequence_contract_correction.py"
BASE_SHA256 = "8e02c9c29a7b0a967d8987d9960909819cd47079862dc3d13c91e3a0d81cd8ed"
RUN_SHA256 = "ac6657d630f7ec645371eb6071efbf98508fe574a23c925c29730e905105e729"
AGGREGATE_SHA256 = "57cc87ddfa778352adef060d909fc4ebceb52710ab6c79f3ad21ca5d5acedf77"
PARENT_OBJECT_SHA256 = "75f9f7a00f641c4e2be208ae7aab3499f62731f82e1ea9a4035d4ebb9c12601f"
PARENT_DIGEST = "fb918f194026d60e5cf0af656100efa465fccb56b61c5e219d558cb137db4880"
TARGET = "joint-capability-frontier-coordination-recovery-resilience"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0114 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0115_frozen_ot0114", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior14 = load_base()
previous = prior14.previous
prior = prior14.prior
kernel = prior14.kernel
base = prior14.base


def load_inputs(p82, repo: Path, store: Path):
    run_manifest, _ = p82.materialize(
        repo, store, "OT-0114", "concrete-consequence-second-expansion-run.json"
    )
    aggregate_manifest, aggregate_path = p82.materialize(
        repo,
        store,
        "OT-0114",
        "concrete-consequence-second-expansion-aggregate.json",
    )
    parent_manifest, parent_path = p82.materialize(
        repo, store, "OT-0114", "open-subject-after-second-generic-expansion.json"
    )
    if run_manifest["sha256"] != RUN_SHA256:
        raise RuntimeError("wrong OT-0114 run")
    if aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0114 aggregate")
    if parent_manifest["sha256"] != PARENT_OBJECT_SHA256:
        raise RuntimeError("wrong OT-0114 parent")
    return json.loads(aggregate_path.read_text()), json.loads(parent_path.read_text())


def current_tip(p82, parent, repo: Path, store: Path):
    tip = kernel.load_initial_tip(p82, repo, store)
    for package in parent.get("interface_package_chain", []):
        spec = previous.normalize_spec(package["interface"])
        if not spec or spec["parent_interface_id"] != tip["interface_id"]:
            raise RuntimeError("invalid package-chain ancestry")
        if not kernel.valid_spec(spec, tip, spec["interface_id"]):
            raise RuntimeError("invalid installed package")
        tip = kernel.advance_tip(tip, package)
    return tip


def read_package(workspace: Path):
    try:
        return {
            "interface": json.loads((workspace / "interface.json").read_text()),
            "contact": json.loads((workspace / "contact.json").read_text()),
            "operation_source": (workspace / "operation.py").read_text(),
            "conformance_source": (workspace / "conformance.py").read_text(),
        }
    except (OSError, json.JSONDecodeError):
        return None


def run_author(p82, context, run: Path, parent, tip, selection):
    label = "cycle-3-package-author"
    seed = kernel.package_seed(run, label, parent, tip, selection)
    prompt = (
        "Author the complete extension package from the exact subject opening and "
        "dynamic public contract. Edit exactly interface.json, operation.py, "
        "conformance.py, and contact.json; inspect the diff and report truthfully."
    )
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, kernel.AUTHOR_SCHEMA, prompt
    )
    package = read_package(workspace)
    spec = previous.normalize_spec(package["interface"]) if package else None
    valid = bool(
        package
        and spec
        and kernel.valid_spec(spec, tip, selection["continuation_action"]["action_target"])
        and kernel.validate_contact(spec, tip, package["contact"])[0]
        and kernel.load_named(package["operation_source"], "choose_extension")
        and kernel.load_named(package["conformance_source"], "validate_contact")
        and output.get("interface_id") == selection["continuation_action"]["action_target"]
        and output.get("case_count") == 3
    )
    audit = context.audit_actor(label, output, base_audit, valid, kernel.PACKAGE_FILES)
    binding = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0115-subject-authored-generic-extension-package",
            "cycle": 3,
            "source_subject_digest": parent["artifact_digest"],
            "continuation_binding_digest": selection["binding_digest"],
            "parent_package_binding_digest": tip["binding_digest"],
            "actor_patch_digest": audit["patch_digest"],
            **package,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-package.json").write_text(
            json.dumps(binding, indent=2, sort_keys=True) + "\n"
        )
    return {"output": output, "audit": audit, "binding": binding}


def public_agreement(tip, package, source: str):
    spec = previous.normalize_spec(package["interface"])
    return kernel.public_agreement(
        spec,
        tip,
        package["contact"],
        kernel.load_named(source, "validate_contact"),
    )


def concrete_receipt(tip, package, source: str):
    spec = previous.normalize_spec(package["interface"])
    validator = kernel.load_named(source, "validate_contact")
    failures = []
    for label, mutation, expected in kernel.contact_mutations(
        spec, tip, package["contact"]
    ):
        try:
            observed = validator(copy.deepcopy(mutation)) if validator else None
        except Exception:
            observed = None
        if type(observed) is not bool or observed is not expected:
            failures.append(
                {
                    "fixture": label,
                    "expected": expected,
                    "observed": observed,
                    "mutated_contact": mutation,
                    "delta_from_authored_contact": prior14.changed_values(
                        package["contact"], mutation
                    ),
                }
            )
    return {
        "failures": failures,
        "authoritative_bounds": {
            "base_context_fields": {
                field: [0, 100] for field in sorted(kernel.BASE_CONTEXT)
            },
            "base_option_fields": {
                field: [0, 200] for field in sorted(kernel.BASE_OPTION - {"id"})
            },
            "terms": kernel.extended_terms(tip, spec),
        },
    }


def correction_seed(run: Path, package, disagreement, receipt):
    seed = run / "cycle-3-contract-corrector-seed"
    seed.mkdir()
    (seed / "interface.json").write_text(
        json.dumps(package["interface"], indent=2, sort_keys=True) + "\n"
    )
    (seed / "contact.json").write_text(
        json.dumps(package["contact"], indent=2, sort_keys=True) + "\n"
    )
    (seed / "operation.py").write_text(package["operation_source"])
    (seed / "conformance.py").write_text(package["conformance_source"])
    (seed / "public-contract-disagreement.json").write_text(
        json.dumps(disagreement, indent=2, sort_keys=True) + "\n"
    )
    (seed / "concrete-consequence.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
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
        "Correct the exact public validator from the concrete independent "
        "consequence. Edit only conformance.py, preserve every other package byte, "
        "inspect the diff, and report truthfully.\n"
    )
    return seed


def maybe_correct(p82, context, run: Path, package, tip):
    disagreement = public_agreement(tip, package, package["conformance_source"])
    if disagreement["passed"]:
        return {
            "needed": False,
            "disagreement": disagreement,
            "concrete_consequence": None,
            "binding": package,
            "actor": None,
        }
    receipt = concrete_receipt(tip, package, package["conformance_source"])
    seed = correction_seed(run, package, disagreement, receipt)
    label = "cycle-3-contract-corrector"
    output, base_audit, workspace, _ = context.run_actor(
        label,
        seed,
        kernel.CORRECTOR_SCHEMA,
        "Correct conformance.py from the exact concrete public consequence. "
        "Change no other package file, inspect the diff, and report truthfully.",
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
    valid = bool(immutable and source != package["conformance_source"] and agreement["passed"])
    audit = context.audit_actor(label, output, base_audit, valid, ["conformance.py"])
    binding = None
    if audit["conformant"]:
        body = {
            **{key: value for key, value in package.items() if key != "binding_digest"},
            "authority": "ot-0115-concrete-corrected-generic-extension-package",
            "parent_package_binding_digest": package["binding_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "conformance_source": source,
            "public_contract": agreement,
            "concrete_consequence_digest": p82.digest(receipt),
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence(label) / "bound-corrected-package.json").write_text(
            json.dumps(binding, indent=2, sort_keys=True) + "\n"
        )
    return {
        "needed": True,
        "disagreement": disagreement,
        "concrete_consequence": receipt,
        "binding": binding,
        "actor": {
            "output": output,
            "audit": audit,
            "public_contract": agreement,
            "immutable": immutable,
        },
    }


def admit(p82, run: Path, parent, tip, package):
    seed = secrets.token_bytes(32)
    (run / "cycle-3-hidden-seed.bin").write_bytes(seed)
    spec = previous.normalize_spec(package["interface"])
    hidden = kernel.derive_hidden(spec, tip, seed)
    (run / "cycle-3-hidden-cases.json").write_text(
        json.dumps(hidden, indent=2, sort_keys=True) + "\n"
    )
    assessment = kernel.assess(
        spec,
        tip,
        package["contact"],
        package["operation_source"],
        package["conformance_source"],
        hidden,
    )
    body = {
        "authority": "ot-0115-independent-generic-extension-admission",
        "cycle": 3,
        "source_subject_digest": parent["artifact_digest"],
        "package_binding_digest": package["binding_digest"],
        "private_seed_digest": hashlib.sha256(seed).hexdigest(),
        "derivation_attempt": 1,
        "hidden_cases_digest": p82.digest(hidden),
        "assessment": assessment,
        "admitted": assessment["passed"],
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    (run / "cycle-3-admission-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    return receipt


def fixtures(p82, aggregate, parent, tip, selection, repo: Path, store: Path):
    boolean = {
        "interface_id": TARGET,
        "parent_interface_id": tip["interface_id"],
        "new_context_field": "prospective_penalty",
        "new_option_field": "prospective_burden",
        "minimum": 0,
        "maximum": 10,
        "score_composition": kernel.COMPOSITION,
        "reversible_projection": True,
    }
    structured = {
        **boolean,
        "score_composition": "parent_score - prospective_penalty * prospective_burden",
        "reversible_projection": {"zero_rule": "zero recovers parent"},
    }
    result = {
        "base_kernel": kernel.fixture_conformance(
            kernel.load_initial_tip(p82, repo, store)
        )["passed"],
        "source_promoted": aggregate["operational_transition_passed"],
        "parent_exact": parent["artifact_digest"] == PARENT_DIGEST,
        "parent_sounding": aggregate["final_subject_digest"] == PARENT_DIGEST,
        "two_installed_extensions": len(parent.get("interface_package_chain", [])) == 2,
        "tip_exact": tip["interface_id"] == "joint-capability-frontier-coordination-recovery",
        "selection_exact": bool(
            selection
            and selection["continuation_action"]["action_kind"] == "registry-extension"
            and selection["continuation_action"]["action_target"] == TARGET
        ),
        "boolean_declaration_valid": bool(
            previous.normalize_spec(boolean)
            and kernel.valid_spec(previous.normalize_spec(boolean), tip, TARGET)
        ),
        "structured_declaration_valid": bool(
            previous.normalize_spec(structured)
            and kernel.valid_spec(previous.normalize_spec(structured), tip, TARGET)
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
    run = (args.evidence_root or store / "runs/OT-0115").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    aggregate, parent = load_inputs(p82, repo, store)
    tip = current_tip(p82, parent, repo, store)
    selection = kernel.extract_action(p82, parent)
    checked = fixtures(p82, aggregate, parent, tip, selection, repo, store)
    if args.preflight_only:
        out = {
            "base_sha256": BASE_SHA256,
            "run_sha256": RUN_SHA256,
            "aggregate_sha256": AGGREGATE_SHA256,
            "parent_digest": parent["artifact_digest"],
            "tip_binding_digest": tip["binding_digest"],
            "fixtures": checked,
        }
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0 if checked["passed"] and runtime.identity_conforms(parent) else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0115 evidence")
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
    authored = run_author(p82, context, run, parent, tip, selection)
    correction = (
        maybe_correct(p82, context, run, authored["binding"], tip)
        if authored["binding"]
        else None
    )
    package = correction["binding"] if correction else None
    admission = admit(p82, run, parent, tip, package) if package else None
    world = (
        kernel.world_contact(p82, 3, package, admission)
        if admission and admission["admitted"]
        else None
    )
    assimilation = (
        kernel.run_assimilation(
            prior89, p82, context, run, 3, parent, tip, package, admission, world
        )
        if world and world["all_cases_passed"]
        else None
    )
    current = parent
    promotion = None
    if assimilation and assimilation["binding"]:
        current, promotion = kernel.promote(
            p82, parent, selection, package, admission, world, assimilation["binding"]
        )
    operational = bool(promotion and runtime.identity_conforms(current))
    result = {
        "authority": "ot-0115-prospective-generic-expansion-driver",
        "source_subject_digest": parent["artifact_digest"],
        "source_tip_binding_digest": tip["binding_digest"],
        "source_continuation": selection,
        "package_author": p82.compact(authored),
        "correction": p82.compact(correction) if correction else None,
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
