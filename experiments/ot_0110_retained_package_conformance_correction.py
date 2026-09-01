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
BASE_PATH = ROOT / "ot_0109_subject_authored_interface_admission.py"
BASE_SHA256 = "f48fc87435983515618bee882534b45c61956ceb4d0ffc8649083a6253e4124c"
RUN_SHA256 = "1f71d70994b16a0dc3e05c9587a1d005defe9a0349c214af48f005bcd2666395"
AGGREGATE_SHA256 = "20f0b370895dad1864798fb2aa367abecd7b486f2e60504b382cef342c6ef9c0"
PATCH_DIGEST = "fa3d8663b034e619d304cb065061ea7dc0bf4948d1c9615ee573db942e884c1a"
CORRECTOR_SCHEMA = REPO / "spec/ot-0110-corrector.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0109 implementation identity changed")
    name = "ot0110_frozen_ot0109"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base = prior.base


def extract_archive(path: Path, destination: Path) -> Path:
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != "OT-0109" or member.name.startswith("/") or ".." in parts:
                raise RuntimeError("unsafe OT-0109 archive member")
            if member.issym() or member.islnk():
                raise RuntimeError("linked OT-0109 archive member")
        archive.extractall(destination, members=members)
    return destination / "OT-0109"


def load_inputs(p82, repo: Path, store: Path, destination: Path):
    run_manifest, run_path = p82.materialize(repo, store, "OT-0109", "rejected-subject-authored-interface-run.json")
    aggregate_manifest, aggregate_path = p82.materialize(repo, store, "OT-0109", "rejected-subject-authored-interface-aggregate.json")
    if run_manifest["sha256"] != RUN_SHA256 or aggregate_manifest["sha256"] != AGGREGATE_SHA256:
        raise RuntimeError("wrong OT-0109 input identity")
    aggregate = json.loads(aggregate_path.read_text())
    raw = extract_archive(run_path, destination)
    workspace = raw / "package-author" / "actor-workspace"
    package = {
        "interface": json.loads((workspace / "interface.json").read_text()),
        "contact": json.loads((workspace / "contact.json").read_text()),
        "operation_source": (workspace / "operation.py").read_text(),
        "conformance_source": (workspace / "conformance.py").read_text(),
    }
    return aggregate, package


def normalized_spec(spec: Any) -> dict[str, Any] | None:
    if not isinstance(spec, dict):
        return None
    declaration = spec.get("reversible_projection")
    if declaration is True:
        return copy.deepcopy(spec)
    if isinstance(declaration, str) and 0 < len(declaration.strip()) <= 500:
        normalized = copy.deepcopy(spec)
        normalized["reversible_projection"] = True
        return normalized
    return None


def bind_exact_package(p82, parent: dict[str, Any], selection: dict[str, Any], aggregate: dict[str, Any], package: dict[str, Any]):
    spec = normalized_spec(package["interface"])
    audit = aggregate["package_author"]["audit"]
    valid = bool(
        spec and prior.valid_spec(spec) and prior.validate_contact(spec, package["contact"])[0]
        and all(prior.source_functions(package["operation_source"], package["conformance_source"]))
        and audit["patch_digest"] == PATCH_DIGEST and audit["exact_changes"] and audit["truthful"]
        and audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["accepted"]
    )
    if not valid:
        return None
    body = {
        "authority": "ot-0110-retained-subject-authored-package",
        "source_subject_digest": parent["artifact_digest"],
        "extension_binding_digest": selection["binding_digest"],
        "source_actor_patch_digest": PATCH_DIGEST,
        **package,
    }
    return {**body, "binding_digest": p82.digest(body)}


def public_disagreement(package: dict[str, Any]) -> dict[str, Any]:
    spec = normalized_spec(package["interface"])
    validator = prior.source_functions(package["operation_source"], package["conformance_source"])[1]
    return prior.public_contract_agreement(spec, package["contact"], validator)


def correction_seed(run: Path, package: dict[str, Any], disagreement: dict[str, Any]) -> Path:
    seed = run / "contract-corrector-seed"
    seed.mkdir()
    (seed / "interface.json").write_text(json.dumps(package["interface"], indent=2, sort_keys=True) + "\n")
    (seed / "contact.json").write_text(json.dumps(package["contact"], indent=2, sort_keys=True) + "\n")
    (seed / "operation.py").write_text(package["operation_source"])
    (seed / "conformance.py").write_text(package["conformance_source"])
    contract = {
        "context_base_bounds": [0, 100], "option_base_bounds": [0, 200],
        "new_bounds": [package["interface"]["minimum"], package["interface"]["maximum"]],
        "ids": "nonempty string or integer excluding bool; consistent and distinct per case",
        "exact_shapes_required": True,
    }
    (seed / "public-meta-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    (seed / "public-contract-disagreement.json").write_text(json.dumps(disagreement, indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({
        "editable": ["conformance.py"], "immutable": ["interface.json", "contact.json", "operation.py"],
    }, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text(
        "Correct the retained package's public validator from the exact machine disagreement. Edit only conformance.py; preserve every other package byte, inspect the diff, and report truthfully.\n"
    )
    return seed


def run_corrector(p82, context, run: Path, parent: dict[str, Any], package: dict[str, Any], disagreement: dict[str, Any]):
    seed = correction_seed(run, package, disagreement)
    prompt = "Correct conformance.py so the public executable contract agrees with every supplied independent fixture. Change no other package file, inspect the exact diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor("contract-corrector", seed, CORRECTOR_SCHEMA, prompt)
    try:
        corrected_source = (workspace / "conformance.py").read_text()
        immutable = bool(
            json.loads((workspace / "interface.json").read_text()) == package["interface"]
            and json.loads((workspace / "contact.json").read_text()) == package["contact"]
            and (workspace / "operation.py").read_text() == package["operation_source"]
        )
    except (OSError, json.JSONDecodeError):
        corrected_source = ""; immutable = False
    spec = normalized_spec(package["interface"])
    validator = prior.source_functions(package["operation_source"], corrected_source)[1]
    agreement = prior.public_contract_agreement(spec, package["contact"], validator) if spec else {"rows": [], "passed": False}
    valid = bool(immutable and validator and agreement["passed"] and corrected_source != package["conformance_source"])
    audit = context.audit_actor("contract-corrector", output, base_audit, valid, ["conformance.py"])
    binding = None
    if audit["conformant"]:
        body = {
            "authority": "ot-0110-consequence-corrected-interface-package",
            "source_subject_digest": parent["artifact_digest"],
            "parent_package_binding_digest": package["binding_digest"],
            "actor_patch_digest": audit["patch_digest"],
            "interface": package["interface"], "contact": package["contact"],
            "operation_source": package["operation_source"], "conformance_source": corrected_source,
            "public_contract": agreement,
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("contract-corrector") / "bound-corrected-package.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    return {"output": output, "audit": audit, "immutable": immutable, "public_contract": agreement, "binding": binding}


def admit_corrected(p82, run: Path, parent: dict[str, Any], package: dict[str, Any]):
    import secrets
    seed = secrets.token_bytes(32)
    (run / "hidden-seed.bin").write_bytes(seed)
    spec = normalized_spec(package["interface"])
    hidden = prior.derive_hidden_cases(spec, seed)
    (run / "hidden-cases.json").write_text(json.dumps(hidden, indent=2, sort_keys=True) + "\n")
    assessment = prior.assess_package(parent, spec, package["contact"], package["operation_source"], package["conformance_source"], hidden)
    body = {
        "authority": "ot-0110-independent-corrected-package-admission",
        "source_subject_digest": parent["artifact_digest"], "package_binding_digest": package["binding_digest"],
        "private_seed_digest": hashlib.sha256(seed).hexdigest(), "derivation_attempt": 1,
        "hidden_cases_digest": p82.digest(hidden), "assessment": assessment, "admitted": assessment["passed"],
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    (run / "admission-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def fixture_conformance(parent: dict[str, Any], aggregate: dict[str, Any], raw_package: dict[str, Any]) -> dict[str, Any]:
    semantic = normalized_spec(raw_package["interface"])
    disagreement = public_disagreement(raw_package)
    failed = [row["fixture"] for row in disagreement["rows"] if not row["passed"]]
    fixture_spec, fixture_contact, fixture_operation, fixture_contract = prior.fixture_package()
    fixture_string = {**fixture_spec, "reversible_projection": "zero boundary recovers retained behavior"}
    result = {
        "source_rejected": not aggregate["operational_transition_passed"],
        "source_parent_unchanged": aggregate["final_subject_digest"] == parent["artifact_digest"],
        "descriptive_declaration_admitted": bool(semantic and prior.valid_spec(semantic)),
        "boolean_declaration_admitted": normalized_spec(fixture_spec) == fixture_spec,
        "empty_declaration_rejected": normalized_spec({**fixture_spec, "reversible_projection": ""}) is None,
        "exact_contact_valid_after_semantic_repair": bool(semantic and prior.validate_contact(semantic, raw_package["contact"])[0]),
        "exact_disagreement_is_upper_bound": failed == ["new-field-out-of-bounds"],
        "reference_contract_passes": prior.public_contract_agreement(fixture_spec, fixture_contact, prior.source_functions(fixture_operation, fixture_contract)[1])["passed"],
        "fixture_string_valid": bool(normalized_spec(fixture_string)),
    }
    result["passed"] = all(result.values())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0110").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = prior.load_parent(p82, repo, store)
    if parent["artifact_digest"] != prior.PARENT_DIGEST or not runtime.identity_conforms(parent):
        raise SystemExit("wrong OT-0108 parent")
    selection = prior.extract_extension(p82, parent)
    with tempfile.TemporaryDirectory() as directory:
        aggregate, raw_package = load_inputs(p82, repo, store, Path(directory))
    fixtures = fixture_conformance(parent, aggregate, raw_package)
    package = bind_exact_package(p82, parent, selection, aggregate, raw_package) if selection else None
    disagreement = public_disagreement(package) if package else None
    if args.preflight_only:
        result = {
            "parent_digest": parent["artifact_digest"], "base_implementation_sha256": BASE_SHA256,
            "run_archive_sha256": RUN_SHA256, "aggregate_sha256": AGGREGATE_SHA256,
            "fixture_conformance": fixtures,
            "retained_package_binding_digest": package["binding_digest"] if package else None,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] and package else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0110 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    (run / "retained-public-disagreement.json").write_text(json.dumps(disagreement, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"] or not package:
        raise SystemExit("pre-actor conformance failed")
    (run / "bound-retained-package.json").write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
    context = prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    correction = run_corrector(p82, context, run, parent, package, disagreement)
    corrected = correction["binding"]
    admission = admit_corrected(p82, run, parent, corrected) if corrected else None
    world = prior.world_contact(p82, corrected, admission) if corrected and admission and admission["admitted"] else None
    if world:
        (run / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    assimilation = prior.run_assimilation(prior89, p82, context, run, parent, corrected, admission, world) if world and world["all_cases_passed"] else None
    current = parent; promotion = None
    if assimilation and assimilation["binding"]:
        current, promotion = prior.promote(p82, parent, selection, corrected, admission, world, assimilation["binding"])
    installed = bool(
        current.get("interface_registry_extensions")
        and current["interface_registry_extensions"][-1].get("package_binding_digest") == (corrected or {}).get("binding_digest")
    )
    operational = bool(
        promotion and installed and runtime.identity_conforms(current)
        and current["runtime"] == "sounding" and current["continuation"]["status"] == "open"
    )
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    result = {
        "authority": "ot-0110-retained-package-conformance-correction-driver",
        "source_subject_digest": parent["artifact_digest"],
        "retained_package_binding": package,
        "retained_public_disagreement": disagreement,
        "correction": p82.compact(correction),
        "admission_receipt": p82.compact(admission) if admission else None,
        "world_receipt": world,
        "assimilation": p82.compact(assimilation) if assimilation else None,
        "promotion_receipt": promotion,
        "correction_bound": bool(corrected), "package_admitted": bool(admission and admission["admitted"]),
        "authored_contact_passed": bool(world and world["all_cases_passed"]),
        "operational_transition_passed": operational,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"],
        "continuation_action": current["actor_originated_pursuit_openings"][-1].get("continuation_action"),
        "next_opening": current["continuation"]["next_opening"],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
