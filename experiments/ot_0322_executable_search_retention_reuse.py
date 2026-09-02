from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path


sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0321_exact_weight_bound_reconstruction.py"
BASE_SHA256 = "95d250e066599fc3f412eaadd7dea0e8e2c38171f4fb98dfe5f6ab0bbbb8c8d8"
PARENT_DIGEST = "2ea4387273360d694805eeb3c52ce7e558ad13528391434551947d29d5d37d9a"
OT321_RECEIPT = "103e94a20b23ee3cbc5538cc6e49aca99a200979617f16e7e026c0367b6544c6"
SEARCH_RECEIPT = "155dadebc25c9efb4c50b719b010d910bd391ada9587201e58e296477549c5be"
SEARCH_SOURCE_DIGEST = "769eafde3e3acaa03d27df4b751da9c97be4fb3e2a48eb36a01ef5a24c3a09cf"
AUTHORITY = "ot-0322-executable-search-retention-reuse"
SCHEMA = REPO / "spec" / "ot-0314-stake-revision.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0321 changed")
    spec = importlib.util.spec_from_file_location("ot0322_frozen_ot0321", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
base320 = base.base
base319 = base320.base
b = base320.b
base236 = base320.base236
base314 = base.base314
base315 = base.base315
base316 = base.base316
write_json = base.write_json
SEARCH_SOURCE = base320.SEARCH_TOOL
ERASED_SEARCH = '''import json
print(json.dumps({"available":False,"reason":"executable-search-source-erased"},sort_keys=True))
raise SystemExit(0)
'''


def setup(args):
    (
        repo, store, _, p82, runtime, _, raw314, result318, _, _, _, _, selector,
    ) = base.setup(args)
    run = (args.evidence_root or store / "runs" / "OT-0322").resolve()
    parent = selector.load_artifact(
        p82, repo, store, "OT-0321", "open-subject-after-reachable-revision-search.json"
    )
    result321 = selector.load_artifact(
        p82, repo, store, "OT-0321", "exact-weight-bound-reconstruction-aggregate.json"
    )
    setup320 = base320.setup(args)
    core, base130 = setup320[-2], setup320[-1]
    return (
        repo, store, run, p82, runtime, parent, result321, selector, raw314,
        result318, core, base130,
    )


def token(seed, label):
    return hashlib.sha256(bytes.fromhex(seed) + label.encode()).hexdigest()


def equal_length_sources():
    useful = (
        'def route(case):\n'
        '    return ("harbor", "shelter", "clinic", "relay")[case["signal"]]\n'
    )
    decoy = (
        'def route(case):\n'
        '    return (lambda value: "harbor")((lambda value: "harbor")((lambda value: "harbor")(case)))\n'
    )
    target = max(len(useful.encode()), len(decoy.encode())) + 2
    def pad(source):
        missing = target - len(source.encode())
        return source + ("#" * (missing - 1)) + "\n"
    useful, decoy = pad(useful), pad(decoy)
    if len(useful.encode()) != len(decoy.encode()):
        raise RuntimeError("source padding failed")
    return useful, decoy


def descriptor(seed, label, useful):
    useful_source, decoy_source = equal_length_sources()
    source = useful_source if useful else decoy_source
    return {
        "world_id": "w-" + token(seed, label)[:16],
        "public_package_digest": hashlib.sha256(
            source.encode() + bytes.fromhex(token(seed, label))
        ).hexdigest(),
        "features": base314.base305.source_features(source),
    }, source


def episodes(seed, p82):
    rows = []
    contexts = [{"signal": value} for value in (0, 1, 2, 3)]
    for index in range(8):
        useful, useful_source = descriptor(seed, f"{index}-useful", True)
        decoy, decoy_source = descriptor(seed, f"{index}-decoy", False)
        catalog = sorted([useful, decoy], key=lambda row: row["world_id"])
        option = {
            useful["world_id"]: base314.executable_option_value(useful_source, contexts),
            decoy["world_id"]: base314.executable_option_value(decoy_source, contexts),
        }
        rows.append({
            "episode_id": "e-" + token(seed, str(index))[:16],
            "catalog": catalog,
            "sealed_contexts_digest": p82.digest(contexts),
            "option_value": option,
            "best_world_id": max(option, key=option.get),
        })
    return rows[:3], rows[3:]


def selection_contacts(stake, training, p82):
    rows = []
    for episode in training:
        choice = base316.select(stake, episode)
        selection_body = {
            "authority": AUTHORITY + "-bound-selection",
            "episode_id": episode["episode_id"],
            "catalog_digest": p82.digest(episode["catalog"]),
            "selected_world_id": choice["selected_world_id"],
            "supported": choice["supported"],
            "selection_precedes_outcome": True,
        }
        selection = {**selection_body, "receipt_digest": p82.digest(selection_body)}
        outcome_body = {
            "authority": AUTHORITY + "-call-option-value-world",
            "selection_receipt_digest": selection["receipt_digest"],
            "episode_id": episode["episode_id"],
            "catalog_digest": selection["catalog_digest"],
            "outcome_authority": True,
            "option_value": episode["option_value"],
            "best_world_id": episode["best_world_id"],
            "selected_option_value": episode["option_value"].get(choice["selected_world_id"]),
            "directional_error": choice["selected_world_id"] != episode["best_world_id"],
        }
        rows.append({
            "catalog": episode["catalog"],
            "selection": selection,
            "outcome": {**outcome_body, "receipt_digest": p82.digest(outcome_body)},
        })
    return rows


def capability(parent, p82, *, erased):
    receipt = parent["proposal_search_receipts"][-1]
    source = None if erased else SEARCH_SOURCE
    body = {
        "authority": AUTHORITY + ("-source-erased-capability" if erased else "-retained-capability"),
        "source_subject_digest": parent["artifact_digest"],
        "source_causal_receipt_digest": OT321_RECEIPT,
        "source_search_receipt_digest": receipt["receipt_digest"],
        "source_digest": SEARCH_SOURCE_DIGEST,
        "source": source,
        "source_available": not erased,
        "interface": {
            "inputs": ["stake-revision.json", "stake-revision-contract.json", "completed-selection-contacts.json"],
            "output": "complete bounded search with nearest improving candidates or no-improvement",
        },
        "applicability": {
            "requires_authoritative_outcomes": True,
            "invoke_when": "incumbent fails at least one available selection contact",
            "saturated_when": "no legal bounded candidate improves available-contact fitness",
        },
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def compile_capability_subject(parent, p82, *, erased):
    record = capability(parent, p82, erased=erased)
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["proposal_search_capabilities"] = [*child.get("proposal_search_capabilities", []), record]
    child["active_proposal_search_capability"] = record
    return p82.seal(child), record


def run_search(source, stake, contacts):
    with tempfile.TemporaryDirectory(prefix="ot0322-search-") as temporary:
        root = Path(temporary)
        write_json(root / "stake-revision.json", stake)
        write_json(root / "completed-selection-contacts.json", contacts)
        write_json(root / "stake-revision-contract.json", {"weight_integer_range": [-20, 20]})
        (root / "search_revisions.py").write_text(source)
        completed = subprocess.run(
            [sys.executable, "search_revisions.py"], cwd=root, text=True,
            capture_output=True, timeout=30, check=False,
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = None
    return {"returncode": completed.returncode, "parsed": parsed, "stderr": completed.stderr}


def mixed_score(stake, seed, p82):
    prior = base314.episodes(seed, p82)[1] + base316.episodes(seed, p82)[1]
    new = episodes(seed, p82)[1]
    return {
        "prior_floor": base319.score(stake, prior, p82),
        "new_regime": base319.score(stake, new, p82),
        "all_regimes": base319.score(stake, prior + new, p82),
    }


def seed_actor(root, subject, contacts, source):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "stake-revision.json", base316.stake_of(subject))
    write_json(seed / "completed-selection-contacts.json", contacts)
    write_json(seed / "proposal-search-capability.json", subject["active_proposal_search_capability"])
    write_json(seed / "stake-revision-contract.json", base315.contract_for(subject))
    write_json(seed / "subject-position.json", {
        "source_subject_digest": subject["artifact_digest"],
        "active_stake_binding_digest": subject["active_world_seeking_stake"]["binding_digest"],
        "active_capability_receipt_digest": subject["active_proposal_search_capability"]["receipt_digest"],
    })
    (seed / "search_revisions.py").write_text(source)
    (seed / "evaluate_revision.py").write_text(base319.WORKBENCH)
    (seed / "check_revision.py").write_text(base315.CORRECTED_CHECKER)
    immutable = [
        "completed-selection-contacts.json",
        "proposal-search-capability.json",
        "stake-revision-contract.json",
        "subject-position.json",
        "search_revisions.py",
        "evaluate_revision.py",
        "check_revision.py",
        "mutation-envelope.json",
        "README.md",
    ]
    write_json(seed / "mutation-envelope.json", {"editable": ["stake-revision.json"], "immutable": immutable})
    (seed / "README.md").write_text(
        "Continue from the exact subject after three new authoritative selection contacts. The "
        "active proposal-search capability and its applicability boundary are projected from the "
        "subject. Use the executable mechanisms actually available in this workspace to decide "
        "whether to revise or retain. No private world, held-out score, target weights, evaluator, "
        "sibling, or prescribed edit is supplied. Edit only stake-revision.json. You must run "
        "python3 search_revisions.py, python3 evaluate_revision.py, and python3 check_revision.py, "
        "then inspect the exact diff before returning the report.\n"
    )
    return seed


def named_command_succeeded(trace, name):
    return base320.named_command_succeeded(trace, name)


def run_actor(context, root, subject, contacts, source, label, *, source_available):
    seed = seed_actor(root, subject, contacts, source)
    output, audit0, workspace, _ = context.run_actor(
        label, seed, SCHEMA, (seed / "README.md").read_text().strip()
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    try:
        candidate = json.loads((workspace / "stake-revision.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        checker_ok = base315.corrected_accepts(
            base315.run_checker(base315.CORRECTED_CHECKER, candidate, base315.contract_for(subject))
        )
        replayed = base319.replay(candidate, contacts)
        searched = run_search(source, base316.stake_of(subject), contacts)
        search_ok = searched["returncode"] == 0 and searched["parsed"] is not None
        checker_invoked = named_command_succeeded(trace, "check_revision.py")
        workbench_invoked = named_command_succeeded(trace, "evaluate_revision.py")
        search_invoked = named_command_succeeded(trace, "search_revisions.py")
        changed = candidate != base316.stake_of(subject)
        candidate_from_search = bool(
            source_available and changed and searched["parsed"].get("available", True)
            and candidate["weights"] in [row["weights"] for row in searched["parsed"]["candidates"]]
        )
    except (OSError, ValueError, KeyError, TypeError):
        candidate, immutable_ok, checker_ok, replayed, searched = None, False, False, None, None
        search_ok = checker_invoked = workbench_invoked = search_invoked = changed = candidate_from_search = False
    semantic = bool(
        immutable_ok and checker_ok and search_ok and checker_invoked and workbench_invoked and search_invoked
        and base.corrected_accepts(subject, candidate) and base314.output_valid(output, changed)
        and (candidate_from_search if source_available and changed else True)
    )
    expected = ["stake-revision.json"] if changed else []
    audit = context.audit_actor(label, output, audit0, semantic, expected)
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(semantic and base236.g10(normalized))
    return {
        "accepted": accepted,
        "candidate_stake": candidate,
        "changed": changed,
        "output": output,
        "audit": audit,
        "g10_disposition": accepted,
        "search_result": searched["parsed"] if searched else None,
        "training_replay": replayed["parsed"] if replayed else None,
        "workspace_evaluation": {
            "immutable_ok": immutable_ok,
            "checker_ok": checker_ok,
            "search_ok": search_ok,
            "candidate_from_search": candidate_from_search,
            "checker_invoked": checker_invoked,
            "workbench_invoked": workbench_invoked,
            "search_invoked": search_invoked,
            "semantic": semantic,
        },
    }


def compile_child(subject, actor, contacts, evaluation, p82):
    old = subject["active_world_seeking_stake"]
    replay_body = {
        "authority": AUTHORITY + "-reuse-training-replay",
        "stake_digest": p82.digest(actor["candidate_stake"]),
        "capability_receipt_digest": subject["active_proposal_search_capability"]["receipt_digest"],
        "outcome_receipt_digests": [row["outcome"]["receipt_digest"] for row in contacts],
        "replay": actor["training_replay"],
    }
    replay_receipt = {**replay_body, "receipt_digest": p82.digest(replay_body)}
    body = {
        "authority": AUTHORITY + "-stake-reuse-binding",
        "source_subject_digest": subject["artifact_digest"],
        "prior_binding_digest": old["binding_digest"],
        "actor_patch_digest": actor["audit"]["patch_digest"],
        "stake": actor["candidate_stake"],
        "proposal_search_capability_receipt_digest": subject["active_proposal_search_capability"]["receipt_digest"],
        "training_outcome_receipt_digests": [row["outcome"]["receipt_digest"] for row in contacts],
        "training_replay_receipt_digest": replay_receipt["receipt_digest"],
        "heldout_score": evaluation,
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    binding = {**body, "binding_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["world_seeking_stake_revisions"] = [*child.get("world_seeking_stake_revisions", []), binding]
    child["active_world_seeking_stake"] = binding
    child["proposal_search_reuse_receipts"] = [*child.get("proposal_search_reuse_receipts", []), replay_receipt]
    return p82.seal(child), binding, replay_receipt


def preflight(root, p82, runtime, parent, result321):
    root.mkdir(parents=True, exist_ok=True)
    retained_subject, retained_capability = compile_capability_subject(parent, p82, erased=False)
    erased_subject, erased_capability = compile_capability_subject(parent, p82, erased=True)
    training, heldout = episodes("00" * 32, p82)
    contacts = selection_contacts(base316.stake_of(parent), training, p82)
    incumbent = base316.stake_of(parent)
    found = run_search(SEARCH_SOURCE, incumbent, contacts)["parsed"]
    erased = run_search(ERASED_SEARCH, incumbent, contacts)["parsed"]
    candidate = copy.deepcopy(incumbent)
    candidate["weights"] = found["candidates"][0]["weights"]
    candidate["rationale"] = "Candidate-free retained-search reuse fixture."
    candidate_score = mixed_score(candidate, "00" * 32, p82)
    incumbent_score = mixed_score(incumbent, "00" * 32, p82)
    useful_source, decoy_source = equal_length_sources()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "exact_parent_and_receipts": parent["artifact_digest"] == PARENT_DIGEST
        and result321["receipt_digest"] == OT321_RECEIPT
        and result321["observer_disposition"] == "promoted"
        and parent["proposal_search_receipts"][-1]["receipt_digest"] == SEARCH_RECEIPT,
        "exact_search_source_bound": hashlib.sha256(SEARCH_SOURCE.encode()).hexdigest() == SEARCH_SOURCE_DIGEST
        and parent["proposal_search_receipts"][-1]["search_tool_digest"] == SEARCH_SOURCE_DIGEST,
        "retained_subject_contains_source": retained_capability["source"] == SEARCH_SOURCE
        and retained_subject["active_proposal_search_capability"] == retained_capability
        and runtime.identity_conforms(retained_subject),
        "erased_subject_lacks_source": erased_capability["source"] is None
        and not erased_capability["source_available"] and runtime.identity_conforms(erased_subject),
        "world_sources_equal_length": len(useful_source.encode()) == len(decoy_source.encode()),
        "world_features_isolate_calls": all(
            row["catalog"][0]["features"][name] == row["catalog"][1]["features"][name]
            for row in training for name in ("branch_nodes", "comparison_nodes", "loop_nodes", "source_bytes")
        ) and all(
            row["catalog"][0]["features"]["call_nodes"] != row["catalog"][1]["features"]["call_nodes"]
            for row in training
        ),
        "incumbent_fails_0_of_3": base319.replay(incumbent, contacts)["parsed"]["pass_count"] == 0,
        "retained_search_finds_3_of_3": found["search_complete"] and found["current_pass_count"] == 0
        and found["best_pass_count"] == 3 and found["improvement_found"] and bool(found["candidates"]),
        "reported_candidates_legal_and_replay": all(
            base.corrected_accepts(parent, {**copy.deepcopy(incumbent), "weights": row["weights"], "rationale": "Fixture."})
            and base319.replay({**copy.deepcopy(incumbent), "weights": row["weights"], "rationale": "Fixture."}, contacts)["parsed"]["pass_count"] == 3
            for row in found["candidates"]
        ),
        "fixture_candidate_15_of_15": candidate_score["all_regimes"]["pass_count"] == 15
        and candidate_score["prior_floor"]["pass_count"] == 10,
        "incumbent_preserves_10_floor_and_fails_new": incumbent_score["prior_floor"]["pass_count"] == 10
        and incumbent_score["new_regime"]["pass_count"] == 0
        and incumbent_score["all_regimes"]["pass_count"] == 10,
        "erased_search_unavailable": erased == {"available": False, "reason": "executable-search-source-erased"},
        "tools_contain_no_private_target": all(
            term not in SEARCH_SOURCE for term in ("heldout", "private", '"call_nodes": -1', "target_weight")
        ),
        "exact_open_conformant": parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "fixture_seed_digest": p82.digest("00" * 32),
        "search_source_digest": hashlib.sha256(SEARCH_SOURCE.encode()).hexdigest(),
        "retained_capability_receipt_digest": retained_capability["receipt_digest"],
        "erased_capability_receipt_digest": erased_capability["receipt_digest"],
        "retained_search_result": found,
        "erased_search_result": erased,
        "fixture_candidate_score": candidate_score,
        "incumbent_score": incumbent_score,
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    (
        repo, store, run, p82, runtime, parent, result321, selector, raw314,
        result318, core, base130,
    ) = setup(args)
    retained = run / "preflight" / "fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(
        run / "preflight", p82, runtime, parent, result321
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0322 unavailable")

    retained_subject, retained_capability = compile_capability_subject(parent, p82, erased=False)
    erased_subject, erased_capability = compile_capability_subject(parent, p82, erased=True)
    write_json(run / "retained-capability-subject.json", retained_subject)
    write_json(run / "source-erased-capability-subject.json", erased_subject)

    seed = secrets.token_hex(32)
    write_json(run / "private-call-world-seed.json", {"seed": seed, "seed_digest": p82.digest(seed)})
    training, _ = episodes(seed, p82)
    contacts = selection_contacts(base316.stake_of(parent), training, p82)
    if not all(row["outcome"]["directional_error"] for row in contacts):
        raise RuntimeError("private training lacks directional errors")

    context = b.base274.context_for(core, base130, runtime, run / "actors", repo)
    actor = run_actor(
        context, run / "candidate", retained_subject, contacts, SEARCH_SOURCE,
        "retained-search-capability-reuser", source_available=True,
    )
    candidate_score = mixed_score(actor["candidate_stake"], seed, p82) if actor["accepted"] else None
    operational = bool(
        actor["accepted"] and actor["changed"] and actor["workspace_evaluation"]["candidate_from_search"]
        and actor["training_replay"]["pass_count"] == 3
        and candidate_score["prior_floor"]["pass_count"] == 10
        and candidate_score["new_regime"]["pass_count"] == 5
        and candidate_score["all_regimes"]["pass_count"] == 15
    )
    child, binding, replay_receipt = (
        compile_child(retained_subject, actor, contacts, candidate_score, p82)
        if operational else (parent, None, None)
    )
    write_json(run / "candidate-operational-subject.json", child)

    erased_actor = run_actor(
        context, run / "erased", erased_subject, contacts, ERASED_SEARCH,
        "retained-search-capability-reuser-source-erased", source_available=False,
    )
    erased_score = mixed_score(erased_actor["candidate_stake"], seed, p82) if erased_actor["accepted"] else None
    causal = bool(
        operational and erased_actor["accepted"]
        and erased_actor["search_result"] == {"available": False, "reason": "executable-search-source-erased"}
        and not (
            erased_actor["changed"] and erased_score is not None
            and erased_score["all_regimes"]["pass_count"] == 15
        )
    )
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "private_seed_postfreeze": True,
        "capability_compiled_before_contact": (run / "retained-capability-subject.json").exists(),
        "candidate_actor_clean": actor["accepted"],
        "candidate_uses_inherited_search": actor["accepted"] and actor["workspace_evaluation"]["candidate_from_search"],
        "candidate_replays_3_of_3": actor["accepted"] and actor["training_replay"]["pass_count"] == 3,
        "candidate_reaches_15_and_preserves_floor": operational,
        "operational_child_sealed_before_control": (run / "candidate-operational-subject.json").exists(),
        "erased_actor_clean": erased_actor["accepted"],
        "erased_search_unavailable": erased_actor["search_result"] == {"available": False, "reason": "executable-search-source-erased"},
        "source_erasure_removes_reuse_advantage": causal,
        "child_retains_executable_capability": not operational or (
            child["active_proposal_search_capability"]["source"] == SEARCH_SOURCE
            and binding["proposal_search_capability_receipt_digest"] == retained_capability["receipt_digest"]
            and child["proposal_search_reuse_receipts"][-1] == replay_receipt
        ),
        "child_open_conformant": child["continuation"]["status"] == "open" and runtime.identity_conforms(child),
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "source_causal_receipt": result321["receipt_digest"],
        "private_world_seed_digest": p82.digest(seed),
        "retained_capability": retained_capability,
        "erased_capability": erased_capability,
        "training_contacts": contacts,
        "candidate_actor": actor,
        "candidate_score": candidate_score,
        "stake_reuse_binding": binding,
        "reuse_replay_receipt": replay_receipt,
        "erased_actor": erased_actor,
        "erased_score": erased_score,
        "checks": checks,
        "operational_transition_passed": operational,
        "executable_search_retention_reuse_supported": causal,
        "observer_disposition": "promoted" if checks["passed"] else ("conditional" if operational else "rejected"),
        "subject_disposition": child["continuation"]["status"],
        "final_subject_digest": child["artifact_digest"],
        "fresh_actor_count": 2,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", child)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
