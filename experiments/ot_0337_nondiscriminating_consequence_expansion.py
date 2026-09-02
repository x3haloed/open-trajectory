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


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0336_consequence_before_revision_recovery.py"
BASE_SHA256 = "86444046ba3298d6364aaa83cfbe96879123f78b4f5fe4c4bf6603e0c0f149dc"
PARENT_DIGEST = "e46bb09123baecc137341417faab8afa053424be94d0b14a8316907d6e347e9c"
OT336_RECEIPT = "f590cf57c6d789e036706cadd79609a58d941f204351ec534f89c09218fbbd35"
REQUEST_DIGEST = "7ac110246950157de7927c529505629c58bc12a8863884f23c7e777be1df159d"
AUTHORITY = "ot-0337-nondiscriminating-consequence-expansion"
SCHEMA = REPO / "spec/ot-0337-comparative-consequence-response.schema.json"


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"frozen OT-0336 source changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0337_frozen_ot0336", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()
p35 = base.base
write_json = base.write_json


def setup(args):
    repo, store, _, p82, runtime, core, base130, _, _ = p35.setup(args)
    run = (args.evidence_root or store / "runs/OT-0337").resolve()
    selector = p35.base.base.base.base.base.base.b.authority_base.guide_base.load_base().selector_base
    load = lambda experiment, name: selector.load_artifact(p82, repo, store, experiment, name)
    parent = load("OT-0336", "open-subject-awaiting-comparative-consequence.json")
    result336 = load("OT-0336", "consequence-before-revision-recovery-aggregate.json")
    result334 = load("OT-0334", "scoped-provider-collision-recovery-rejected-aggregate.json")
    return repo, store, run, p82, runtime, core, base130, parent, result336, result334


def provider_map(result334):
    return {provider["package"]["world_id"]: provider for provider in result334["providers"]}


def consequence_receipt(parent, request, provider, p82):
    package = provider["package"]
    evaluation = provider["evaluation"]
    eligible = sorted(provider["eligible_targets"])
    valid = bool(
        provider["accepted"]
        and request["binding_digest"] == REQUEST_DIGEST
        and package["world_id"] in request["world_ids"]
        and evaluation["valid"]
        and evaluation["world_id"] == package["world_id"]
        and evaluation["full_package_digest"] == p82.digest(package)
        and set(eligible) == set(provider["eligible_targets"])
    )
    targets = []
    for target in eligible:
        rows = evaluation["rows"][target]
        targets.append({"target": target, "matches": sum(row["matches"] for row in rows), "case_count": len(rows), "outcome": "unresolved" if not all(row["matches"] for row in rows) else "matched"})
    signature = {"eligible_count": len(targets), "scores": [row["matches"] for row in targets], "case_counts": [row["case_count"] for row in targets], "outcomes": [row["outcome"] for row in targets]}
    body = {
        "authority": AUTHORITY + "-world-consequence",
        "source_subject_digest": parent["artifact_digest"],
        "comparison_request_binding_digest": request["binding_digest"],
        "world_id": package["world_id"],
        "package_digest": evaluation["full_package_digest"],
        "targets": targets,
        "outcome_signature": signature,
        "valid": valid,
        "selection_precedes_outcome": True,
        "world_authority": True,
        "scoring_authority": True,
        "outcome_authority": True,
        "actor_authority": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def directionally_distinguishes(receipts):
    return len({json.dumps(row["outcome_signature"], sort_keys=True) for row in receipts}) > 1


def decision_semantic(decision, compared, remaining, receipts):
    if not isinstance(decision, dict) or set(decision) != {"action", "world_ids", "rationale"}:
        return False
    if not isinstance(decision["rationale"], str) or not 1 <= len(decision["rationale"]) <= 2000:
        return False
    ids = decision["world_ids"]
    if not isinstance(ids, list) or len(ids) != len(set(ids)):
        return False
    if decision["action"] == "request-stake-revision":
        return not ids and directionally_distinguishes(receipts)
    if decision["action"] == "extend-comparative-consequence":
        return not directionally_distinguishes(receipts) and ids == remaining and not set(ids) & set(compared)
    if decision["action"] == "retain-world-seeking-stake":
        return not ids
    return False


CHECKER = '''import json\nfrom pathlib import Path\nd=json.loads(Path("decision.json").read_text()); c=json.loads(Path("decision-contract.json").read_text()); ids=d.get("world_ids"); ok=isinstance(d,dict) and set(d)=={"action","world_ids","rationale"} and d.get("action") in c["actions"] and isinstance(ids,list) and len(ids)==len(set(ids)) and all(x in c["candidate_world_ids"] for x in ids) and isinstance(d.get("rationale"),str) and 1<=len(d["rationale"])<=2000; print(json.dumps({"valid":ok})); raise SystemExit(0 if ok else 2)\n'''


def seed_actor(root, parent, result334, receipts):
    seed = root / "seed"
    seed.mkdir(parents=True)
    request = parent["active_comparative_world_contact_request"]
    catalog = result334["selection_history"][-1]["rows"]
    projection = {
        "source_subject_digest": parent["artifact_digest"],
        "active_stake": parent["active_world_seeking_stake"],
        "comparison_request": request,
        "authorized_world_consequences": receipts,
        "public_candidate_catalog": catalog,
        "continuation": parent["continuation"],
    }
    write_json(seed / "subject-position.json", projection)
    write_json(seed / "decision-contract.json", {"actions": ["request-stake-revision", "extend-comparative-consequence", "retain-world-seeking-stake"], "candidate_world_ids": sorted(row["world_id"] for row in catalog), "authority_rule": "Stake revision requires authorized compared worlds to have different outcome signatures. A nondiscriminating comparison may be extended only to not-yet-compared catalogued worlds."})
    write_json(seed / "decision.json", {"action": "retain-world-seeking-stake", "world_ids": [], "rationale": "Replace with your decision from the inherited consequence."})
    (seed / "check_decision.py").write_text(CHECKER)
    immutable = ["subject-position.json", "decision-contract.json", "check_decision.py", "mutation-envelope.json", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["decision.json"], "immutable": immutable})
    (seed / "README.md").write_text("Continue from the exact subject after its requested comparative consequence arrived. Decide what this evidence licenses: stake revision, comparison extension, or retention. If extending, derive the relevant not-yet-compared world identities from the public catalog. Sealed cases, reference sources, future outcomes, and the expected decision are unavailable. Edit only decision.json, run python3 check_decision.py, inspect the exact diff, then return the required JSON summary.\n")
    return seed


def run_actor(context, root, parent, result334, receipts):
    label = "comparative-consequence-responder"
    seed = seed_actor(root, parent, result334, receipts)
    output, base_audit, workspace, _ = context.run_actor(label, seed, SCHEMA, (seed / "README.md").read_text().strip())
    request = parent["active_comparative_world_contact_request"]
    compared = request["world_ids"]
    remaining = [row["world_id"] for row in result334["selection_history"][-1]["rows"] if row["world_id"] not in compared]
    try:
        decision = json.loads((workspace / "decision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        checker = subprocess.run(["python3", "check_decision.py"], cwd=workspace, capture_output=True)
        semantic = immutable_ok and checker.returncode == 0 and decision_semantic(decision, compared, remaining, receipts)
    except (OSError, ValueError, KeyError, TypeError):
        decision, semantic, immutable_ok = None, False, False
    output_ok = output == {"action": "submit-comparative-consequence-response", "files_changed": ["decision.json"]}
    audit = context.audit_actor(label, output, base_audit, semantic and output_ok, ["decision.json"])
    certificate = p35.base.certify_g11(context, label, audit)
    return {"accepted": bool(semantic and output_ok and certificate["challenger_accepted"]), "decision": decision, "output": output, "audit": audit, "g11": certificate, "immutable_ok": immutable_ok}


def compile_extension(parent, actor, receipts, p82):
    decision = actor["decision"]
    body = {"authority": AUTHORITY + "-comparison-extension-binding", "source_subject_digest": parent["artifact_digest"], "prior_request_binding_digest": parent["active_comparative_world_contact_request"]["binding_digest"], "consequence_receipt_digests": [row["receipt_digest"] for row in receipts], "actor_patch_digest": actor["audit"]["patch_digest"], "world_ids": decision["world_ids"], "rationale": decision["rationale"], "stake_changed": False, "selection_authority": True, "world_authority": False, "scoring_authority": False, "outcome_authority": False}
    binding = {**body, "binding_digest": p82.digest(body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["comparative_world_consequence_receipts"] = [*child.get("comparative_world_consequence_receipts", []), *receipts]
    child["comparative_world_contact_extensions"] = [*child.get("comparative_world_contact_extensions", []), binding]
    child["active_comparative_world_contact_extension"] = binding
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Obtain the subject-requested consequence for the remaining catalogued world after the first comparison tied."}
    child["unresolved"] = "Does the remaining catalogued world distinguish the comparison without sacrificing the retained stake floor?"
    return p82.seal(child), binding


def preflight(root, p82, runtime, parent, result336, result334):
    root.mkdir(parents=True, exist_ok=True)
    request = parent["active_comparative_world_contact_request"]
    providers = provider_map(result334)
    receipts = [consequence_receipt(parent, request, providers[world_id], p82) for world_id in request["world_ids"]]
    compared = request["world_ids"]
    remaining = [row["world_id"] for row in result334["selection_history"][-1]["rows"] if row["world_id"] not in compared]
    extension = {"action": "extend-comparative-consequence", "world_ids": remaining, "rationale": "The authorized comparison ties; extend it to the remaining candidate."}
    revision = {"action": "request-stake-revision", "world_ids": [], "rationale": "Revise after directional consequence."}
    changed = copy.deepcopy(receipts)
    changed[1]["outcome_signature"]["scores"][0] = 3
    fake = {"decision": extension, "audit": {"patch_digest": "0" * 64}}
    child, binding = compile_extension(parent, fake, receipts, p82)
    altered_provider = copy.deepcopy(providers[compared[0]])
    altered_provider["package"]["world_id"] = "changed"
    altered_receipt = consequence_receipt(parent, request, altered_provider, p82)
    seed = seed_actor(root / "seed", parent, result334, receipts)
    corpus = "\n".join(path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file())
    sealed = [source for provider in providers.values() for source in provider["package"]["sealed_reference_sources"].values()]
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_open_parent": parent["artifact_digest"] == PARENT_DIGEST and result336["receipt_digest"] == OT336_RECEIPT and request["binding_digest"] == REQUEST_DIGEST and runtime.identity_conforms(parent),
        "request_precedes_two_valid_outcomes": len(receipts) == 2 and all(row["valid"] and row["selection_precedes_outcome"] and row["comparison_request_binding_digest"] == REQUEST_DIGEST for row in receipts),
        "same_world_protocol_ties": not directionally_distinguishes(receipts) and all(row["outcome_signature"] == receipts[0]["outcome_signature"] for row in receipts),
        "altered_or_unrequested_world_rejects": not altered_receipt["valid"],
        "tie_rejects_revision": not decision_semantic(revision, compared, remaining, receipts),
        "directional_fixture_permits_revision": decision_semantic(revision, compared, remaining, changed),
        "remaining_world_extension_valid": len(remaining) == 1 and decision_semantic(extension, compared, remaining, receipts),
        "extension_preserves_stake_and_opens": child["active_world_seeking_stake"] == parent["active_world_seeking_stake"] and binding["stake_changed"] is False and runtime.identity_conforms(child) and child["continuation"]["status"] == "open",
        "actor_seed_excludes_sealed_world": all(source not in corpus for source in sealed),
    }
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY + "-preflight", "source_subject_digest": parent["artifact_digest"], "source_ot0336_receipt_digest": result336["receipt_digest"], "compared_world_ids": compared, "remaining_world_ids": remaining, "fixture_receipts": receipts, "checks": checks}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", receipt)
    return receipt, receipts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, core, base130, parent, result336, result334 = setup(args)
    with tempfile.TemporaryDirectory() as directory:
        frozen, receipts = preflight(Path(directory), p82, runtime, parent, result336, result334)
    if args.preflight_only:
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0337 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", frozen)
    write_json(run / "comparative-world-consequences.json", receipts)
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0337 preflight failed")
    context = p35.base.base305.actor_context(runtime, core, base130, run, repo)
    actor = run_actor(context, run / "responder", parent, result334, receipts)
    operational = bool(actor["accepted"] and actor["decision"]["action"] == "extend-comparative-consequence")
    final, binding = compile_extension(parent, actor, receipts, p82) if operational else (parent, None)
    remaining = frozen["remaining_world_ids"]
    checks = {"preflight_passed": frozen["checks"]["passed"], "fresh_consequence_actor_clean": actor["accepted"], "tie_does_not_trigger_revision": operational, "actor_selects_remaining_world": operational and actor["decision"]["world_ids"] == remaining, "stake_byte_exact": final["active_world_seeking_stake"] == parent["active_world_seeking_stake"], "open_extension_successor": operational and final["active_comparative_world_contact_extension"] == binding and runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    body = {"authority": AUTHORITY, "source_subject_digest": parent["artifact_digest"], "source_ot0336_receipt_digest": result336["receipt_digest"], "world_consequence_receipts": receipts, "actor": actor, "extension_binding": binding, "checks": checks, "operational_transition_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "fresh_actor_count": 1}
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    if operational:
        write_json(run / "open-subject-awaiting-extended-comparison.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
