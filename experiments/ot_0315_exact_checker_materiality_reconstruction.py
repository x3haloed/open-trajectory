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
from typing import Any

from open_trajectory_evidence.evidence import load_manifest, object_path, verify_artifact


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0314_directional_option_value_stake_revision.py"
BASE_SHA256 = "72475f691ca84c23f0c6c1095d28b94c2315a6ff6894e07163364a53b9e4101d"
AUTHORITY = "ot-0315-exact-checker-materiality-reconstruction"
RAW_RECEIPT = "945bd6b5298047c32ad837fa222b51ce9a695a37e3d5ee24bfb303d742194af8"
CANDIDATE_DIGEST = "0a48ab16cb92833cdf9a9e02ddc6207d236b8f79d577d12d38ac348adacd9e49"
MANIFEST_HASHES = {
    "private-option-value-world-seed": "a516fd79d69ccf814c76fede5521be541fba7882d9f5b9de6a0d4e99a7b9b65b",
    "directional-option-value-stake-revision-raw-aggregate": "de54c7119fc64b5ec6a82ca73e9592c252b6b5c5fb9832d8a028f770031f0ff6",
    "consequence-actor-trace": "74ca7203fea58362c6db3c620774c9164978fd6d4cdfbccfbd56bb68079fe52e",
    "consequence-actor-completed-contacts": "3b3139bd62a5ed1f788642f8166b51b4438e6bc797c2f7cfbec7a1a4b4dd2d58",
    "consequence-actor-stake-revision": "c8dad79d42c82a74af97f2d0d1d70e5884d1dab1f77eac10985ec549da678429",
    "outcome-erased-actor-trace": "9fd7ab9430e3265977cf838ed750784d1d44b7d789783eb1cf6ed219763633c3",
    "outcome-erased-actor-completed-contacts": "0a4dcf90f23a36d3093b93a08893b6e2645633e44acf6cd052cbf7efa616fab4",
    "outcome-erased-actor-stake-revision": "b1ac592c44ba13b97de990e8b6ba59f0a29b6d3468274fe9d99737b38bc0f293",
    "checker-invalidated-candidate-subject": "1e05268405e598e06d255d573f243ca615d9de97003d27129ae4b70a1c7c2b50",
}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0314 changed")
    spec = importlib.util.spec_from_file_location("ot0315_frozen_ot0314", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
write_json = base.write_json
CORRECTED_CHECKER = base.CHECKER.replace("{{", "{").replace("}}", "}")


def contract_for(parent: dict[str, Any]) -> dict[str, Any]:
    incumbent = base.stake_of(parent)
    mutable = {"weights", "minimum_score_gap", "rationale"}
    return {
        "required_keys": sorted(incumbent),
        "weight_keys": sorted(incumbent["weights"]),
        "mutable": sorted(mutable),
        "immutable_values": {key: value for key, value in incumbent.items() if key not in mutable},
        "weight_integer_range": [-20, 20],
        "minimum_score_gap_range": [0, 100],
    }


def run_checker(source: str, stake: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ot0315-checker-") as temporary:
        workspace = Path(temporary)
        write_json(workspace / "stake-revision.json", stake)
        write_json(workspace / "stake-revision-contract.json", contract)
        (workspace / "check_revision.py").write_text(source)
        completed = subprocess.run(
            [sys.executable, "check_revision.py"],
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    parsed = None
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        pass
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "parsed": parsed,
    }


def corrected_accepts(result: dict[str, Any]) -> bool:
    return result["returncode"] == 0 and result["parsed"] == {"valid": True}


def corrected_rejects(result: dict[str, Any]) -> bool:
    return result["returncode"] == 2 and result["parsed"] == {"valid": False}


def preflight(root: Path, parent: dict[str, Any], p82) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    incumbent = base.stake_of(parent)
    representative = copy.deepcopy(incumbent)
    representative["weights"]["source_bytes"] = 0
    immutable = copy.deepcopy(representative)
    immutable["question"] = "mutated"
    missing_weight = copy.deepcopy(representative)
    missing_weight["weights"].pop("loop_nodes")
    extra_key = {**representative, "extra": True}
    out_of_range = copy.deepcopy(representative)
    out_of_range["weights"]["source_bytes"] = 21
    contract = contract_for(parent)
    original = run_checker(base.CHECKER, incumbent, contract)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_parent": parent["artifact_digest"] == base.PARENT_DIGEST,
        "correction_only_deescapes_braces": CORRECTED_CHECKER
        == base.CHECKER.replace("{{", "{").replace("}}", "}")
        and CORRECTED_CHECKER != base.CHECKER,
        "original_checker_reproduces_failure": original["returncode"] != 0
        and "unhashable type" in original["stderr"],
        "representative_accepted": corrected_accepts(
            run_checker(CORRECTED_CHECKER, representative, contract)
        ),
        "incumbent_accepted": corrected_accepts(run_checker(CORRECTED_CHECKER, incumbent, contract)),
        "immutable_mutation_rejected": corrected_rejects(
            run_checker(CORRECTED_CHECKER, immutable, contract)
        ),
        "missing_weight_rejected": corrected_rejects(
            run_checker(CORRECTED_CHECKER, missing_weight, contract)
        ),
        "extra_key_rejected": corrected_rejects(run_checker(CORRECTED_CHECKER, extra_key, contract)),
        "out_of_range_rejected": corrected_rejects(
            run_checker(CORRECTED_CHECKER, out_of_range, contract)
        ),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "corrected_checker_digest": p82.digest(CORRECTED_CHECKER),
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def materialize(repo: Path, store: Path, artifact_id: str, *, text: bool = False):
    path = repo / "evidence" / "manifests" / "OT-0314" / f"{artifact_id}.json"
    manifest = load_manifest(path)
    if manifest["sha256"] != MANIFEST_HASHES[artifact_id]:
        raise RuntimeError(f"unexpected manifest hash for {artifact_id}")
    valid, message = verify_artifact(repo=repo, manifest_path=path, store=store)
    if not valid:
        raise RuntimeError(message)
    content = object_path(store, manifest["sha256"]).read_text()
    return content if text else json.loads(content)


def digest_valid(value: dict[str, Any], p82) -> bool:
    claimed = value.get("receipt_digest")
    body = {key: child for key, child in value.items() if key != "receipt_digest"}
    return claimed == p82.digest(body)


def reconstruct(repo: Path, store: Path, run: Path, parent: dict[str, Any], p82, runtime):
    fixtures = json.loads((run / "preflight" / "fixture-conformance.json").read_text())
    if not fixtures["checks"]["passed"]:
        raise RuntimeError("preflight failed")

    seed_record = materialize(repo, store, "private-option-value-world-seed")
    raw = materialize(repo, store, "directional-option-value-stake-revision-raw-aggregate")
    candidate_trace = materialize(repo, store, "consequence-actor-trace", text=True)
    candidate_contacts = materialize(repo, store, "consequence-actor-completed-contacts")
    candidate_stake = materialize(repo, store, "consequence-actor-stake-revision")
    erased_trace = materialize(repo, store, "outcome-erased-actor-trace", text=True)
    retained_erased_contacts = materialize(repo, store, "outcome-erased-actor-completed-contacts")
    erased_stake = materialize(repo, store, "outcome-erased-actor-stake-revision")
    retained_child = materialize(repo, store, "checker-invalidated-candidate-subject")

    training, heldout = base.episodes(seed_record["seed"], p82)
    incumbent = base.stake_of(parent)
    contacts = base.training_receipts(incumbent, training, p82)
    erased_contacts = base.training_receipts(incumbent, training, p82, True)
    candidate_score = base.score(candidate_stake, heldout)
    incumbent_score = base.score(incumbent, heldout)
    erased_score = base.score(erased_stake, heldout)
    contract = contract_for(parent)
    original_candidate = run_checker(base.CHECKER, candidate_stake, contract)
    original_erased = run_checker(base.CHECKER, erased_stake, contract)
    corrected_candidate = run_checker(CORRECTED_CHECKER, candidate_stake, contract)
    corrected_erased = run_checker(CORRECTED_CHECKER, erased_stake, contract)
    rebuilt_child, rebuilt_binding = base.compile_child(
        parent, raw["candidate_actor"], contacts, candidate_score, p82
    )

    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "raw_receipt_exact_and_valid": raw["receipt_digest"] == RAW_RECEIPT
        and digest_valid(raw, p82),
        "private_seed_exact": seed_record["seed_digest"] == p82.digest(seed_record["seed"])
        and raw["private_world_seed_digest"] == seed_record["seed_digest"],
        "training_contacts_exact": contacts == raw["training_contacts"]
        and contacts == candidate_contacts,
        "candidate_stake_exact": candidate_stake == raw["candidate_actor"]["candidate_stake"],
        "erased_stake_exact": erased_stake == raw["erased_actor"]["candidate_stake"],
        "heldout_scores_exact": candidate_score == raw["candidate_score"]
        and incumbent_score == raw["incumbent_score"]
        and erased_score == raw["erased_score"],
        "directional_delta_exact": candidate_score["pass_count"] == 5
        and incumbent_score["pass_count"] == 0
        and erased_score["pass_count"] == 0,
        "outcome_erasure_exact": erased_contacts == retained_erased_contacts
        and erased_stake == incumbent,
        "original_checker_fails_symmetrically": original_candidate["returncode"] != 0
        and original_erased["returncode"] != 0
        and "unhashable type" in original_candidate["stderr"]
        and "unhashable type" in original_erased["stderr"],
        "traces_observe_checker_failure": "python3 check_revision.py" in candidate_trace
        and "unhashable type" in candidate_trace
        and "check_revision.py" in erased_trace
        and "unhashable type" in erased_trace,
        "corrected_checker_accepts_exact_outputs": corrected_accepts(corrected_candidate)
        and corrected_accepts(corrected_erased),
        "actor_effects_clean_and_contract_validated": raw["candidate_actor"]["audit"]["conformant"]
        and raw["candidate_actor"]["workspace_evaluation"]["semantic"]
        and raw["erased_actor"]["audit"]["conformant"]
        and raw["erased_actor"]["workspace_evaluation"]["semantic"]
        and base.valid_candidate(parent, candidate_stake)
        and base.valid_candidate(parent, erased_stake),
        "binding_reconstructed_exactly": rebuilt_binding == raw["stake_revision_binding"],
        "child_reconstructed_byte_exactly": rebuilt_child == retained_child
        and rebuilt_child["artifact_digest"] == CANDIDATE_DIGEST
        and raw["final_subject_digest"] == CANDIDATE_DIGEST,
        "child_open_and_identity_conformant": rebuilt_child["continuation"]["status"] == "open"
        and runtime.identity_conforms(rebuilt_child),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_observation_receipt": RAW_RECEIPT,
        "source_subject_digest": parent["artifact_digest"],
        "candidate_subject_digest": rebuilt_child["artifact_digest"],
        "corrected_checker_digest": p82.digest(CORRECTED_CHECKER),
        "candidate_score": candidate_score,
        "incumbent_score": incumbent_score,
        "outcome_erased_score": erased_score,
        "checks": checks,
        "checker_defect_causally_material": not checks["passed"],
        "historical_actor_checker_workflow_conformant": False,
        "bounded_causal_machinery_refinement_supported": checks["passed"],
        "observer_disposition": "promoted-exact-reconstruction" if checks["passed"] else "rejected",
        "subject_disposition": rebuilt_child["continuation"]["status"] if checks["passed"] else parent["continuation"]["status"],
        "final_subject_digest": rebuilt_child["artifact_digest"] if checks["passed"] else parent["artifact_digest"],
        "fresh_actor_count": 0,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "promoted-exact-subject.json", rebuilt_child if checks["passed"] else parent)
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs" / "OT-0315").resolve()
    base_args = argparse.Namespace(repo=repo, store=store, evidence_root=run / "unused")
    _, _, p82, runtime, parent, _, _, _ = base.setup(base_args)
    retained = run / "preflight" / "fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(
        run / "preflight", parent, p82
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if (run / "aggregate.json").exists():
        raise SystemExit("OT-0315 unavailable")
    aggregate = reconstruct(repo, store, run, parent, p82, runtime)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if aggregate["checks"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
