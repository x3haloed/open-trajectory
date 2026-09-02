from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0332_counterexample_driven_completion.py"
BASE_SHA256 = "e91ac9388cf84b3b4d9f82e567c4521390f9aaee56d5f9b080afc4258efecd44"
PRIORITY_PATH = ROOT / "ot_0311_remaining_catalog_priority_wake.py"
PRIORITY_SHA256 = "1fb3794df62bb7b8ddefdb388594a325cdf6b777059a8cd7ee618f8c2658c12d"
CONTACT_PATH = ROOT / "ot_0306_priority_selected_world_contact.py"
CONTACT_SHA256 = "db3dd0924f15238619e609c67a231ad3a90b0a1787a2829be7fcaa583bf2db34"
PARENT_DIGEST = "38e9b5dd0311f26b462e48a2e87b7aade4ab2c0b5450335f13d3b098ae380449"
OT332_RECEIPT = "03dbf5630da8e57b5f6c7c2c727c700b309cdb62658632f7959cff515bb4da4f"
G11_RECEIPT = "c3cc1114e07d73a2f862488b079c019153b885bb2bb2f3de2759c7fefa73df0f"
AUTHORITY = "ot-0333-subject-sized-environment-search"
SCHEMA = REPO / "spec/ot-0333-environment-solicitation-policy.schema.json"
OBSERVER_PROVIDER_CEILING = 4
SUBJECT_PROVIDER_CEILING = 3
MINIMUM_PROVIDER_COUNT = 2
PULSE = None


def load_module(name, path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"frozen source changed: {path.name} {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_module("ot0333_frozen_ot0332", BASE_PATH, BASE_SHA256)
priority = load_module("ot0333_frozen_ot0311", PRIORITY_PATH, PRIORITY_SHA256)
contact_base = load_module("ot0333_frozen_ot0306", CONTACT_PATH, CONTACT_SHA256)
driver = base.driver
b = driver.b
base305 = driver.base307.base305
g11 = base.g11
write_json = base.write_json


POLICY_TEMPLATE = {
    "policy_id": "replace-policy-id",
    "rationale": "replace-rationale",
    "maximum_provider_count": MINIMUM_PROVIDER_COUNT,
    "required_consecutive_supports": 1,
    "require_same_winner": True,
    "on_support": "offer-selected-world",
    "on_insufficient": "request-another-world",
    "on_exhaustion": "revise-world-seeking-stake",
}


POLICY_CHECKER = '''import json,re
from pathlib import Path
p=json.loads(Path("environment-solicitation-policy.json").read_text())
keys={"policy_id","rationale","maximum_provider_count","required_consecutive_supports","require_same_winner","on_support","on_insufficient","on_exhaustion"}
ok=isinstance(p,dict) and set(p)==keys and isinstance(p.get("policy_id"),str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{2,63}",p["policy_id"])) and isinstance(p.get("rationale"),str) and 1<=len(p["rationale"])<=2000 and isinstance(p.get("maximum_provider_count"),int) and 2<=p["maximum_provider_count"]<=3 and isinstance(p.get("required_consecutive_supports"),int) and 1<=p["required_consecutive_supports"]<=3 and isinstance(p.get("require_same_winner"),bool) and p.get("on_support")=="offer-selected-world" and p.get("on_insufficient")=="request-another-world" and p.get("on_exhaustion")=="revise-world-seeking-stake"
print(json.dumps({"passed":bool(ok),"policy_id":p.get("policy_id")},sort_keys=True)); raise SystemExit(0 if ok else 2)
'''


def setup(args):
    repo, store, _, p82, runtime, _, _, _, result330, _, result280, core, base130 = base.setup(args)
    run = (args.evidence_root or store / "runs/OT-0333").resolve()
    selector = base.base.base.base.b.authority_base.guide_base.load_base().selector_base
    load = lambda experiment, name: selector.load_artifact(p82, repo, store, experiment, name)
    parent = load("OT-0332", "open-subject-at-environment-expansion.json")
    result332 = load("OT-0332", "counterexample-driven-completion-aggregate.json")
    return repo, store, run, p82, runtime, parent, result332, result330, result280, core, base130


def valid_current_stake(subject, p82):
    binding = subject.get("active_world_seeking_stake") or {}
    stake = binding.get("stake") or {}
    body = {key: value for key, value in binding.items() if key != "binding_digest"}
    revisions = subject.get("world_seeking_stake_revisions") or []
    required = {
        "stake_id", "question", "rationale", "subject_anchors", "weights",
        "minimum_score_gap", "support_condition", "contradiction_condition",
        "on_support", "on_contradiction",
    }
    return bool(
        binding.get("binding_digest") == p82.digest(body)
        and any(row == binding for row in revisions)
        and set(stake) == required
        and isinstance(stake.get("stake_id"), str)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", stake["stake_id"])
        and isinstance(stake.get("weights"), dict)
        and set(stake["weights"]) == set(base305.FEATURES)
        and all(isinstance(value, int) and -20 <= value <= 20 for value in stake["weights"].values())
        and isinstance(stake.get("minimum_score_gap"), int)
        and 0 <= stake["minimum_score_gap"] <= 100
        and all(isinstance(stake.get(key), str) and stake[key].strip() for key in ("question", "rationale", "support_condition", "contradiction_condition"))
        and stake.get("on_support") == "offer-selected-world"
        and stake.get("on_contradiction") == "retain-wait-and-revise-stake"
        and binding.get("selection_authority") is True
        and all(binding.get(key) is False for key in ("world_authority", "scoring_authority", "admission_authority", "outcome_authority"))
    )


def valid_policy(policy):
    return bool(
        isinstance(policy, dict)
        and set(policy) == set(POLICY_TEMPLATE)
        and isinstance(policy.get("policy_id"), str)
        and re.fullmatch(r"[a-z][a-z0-9-]{2,63}", policy["policy_id"])
        and isinstance(policy.get("rationale"), str)
        and 1 <= len(policy["rationale"]) <= 2000
        and isinstance(policy.get("maximum_provider_count"), int)
        and MINIMUM_PROVIDER_COUNT <= policy["maximum_provider_count"] <= SUBJECT_PROVIDER_CEILING
        and isinstance(policy.get("required_consecutive_supports"), int)
        and 1 <= policy["required_consecutive_supports"] <= SUBJECT_PROVIDER_CEILING
        and isinstance(policy.get("require_same_winner"), bool)
        and policy.get("on_support") == "offer-selected-world"
        and policy.get("on_insufficient") == "request-another-world"
        and policy.get("on_exhaustion") == "revise-world-seeking-stake"
    )


def policy_action(policy, history, provider_count):
    if not valid_policy(policy):
        return "invalid-policy"
    needed = policy["required_consecutive_supports"]
    suffix = history[-needed:]
    supported = len(suffix) == needed and all(row.get("supported") for row in suffix)
    stable = not policy["require_same_winner"] or len({row.get("selected_world_id") for row in suffix}) == 1
    if provider_count >= MINIMUM_PROVIDER_COUNT and supported and stable:
        return "offer-world"
    if provider_count < policy["maximum_provider_count"]:
        return "request-world"
    return "revise-stake"


def fixture_policy():
    return {
        "policy_id": "seek-stable-supported-world",
        "rationale": "Require repeated support before committing while keeping the expansion bounded.",
        "maximum_provider_count": 3,
        "required_consecutive_supports": 2,
        "require_same_winner": True,
        "on_support": "offer-selected-world",
        "on_insufficient": "request-another-world",
        "on_exhaustion": "revise-world-seeking-stake",
    }


def bind_policy(subject, policy, audit, p82):
    body = {
        "authority": AUTHORITY + "-bound-policy",
        "source_subject_digest": subject["artifact_digest"],
        "actor_patch_digest": audit["patch_digest"],
        "policy": policy,
        "future_world_identity_available": False,
        "observer_provider_ceiling": OBSERVER_PROVIDER_CEILING,
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    return {**body, "binding_digest": p82.digest(body)}


def install_policy(subject, binding, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["environment_solicitation_policies"] = [*child.get("environment_solicitation_policies", []), binding]
    child["active_environment_solicitation_policy"] = binding
    return p82.seal(child)


def seed_policy_actor(root, subject):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "current-subject.json", subject)
    write_json(seed / "environment-solicitation-policy.json", POLICY_TEMPLATE)
    write_json(seed / "environment-solicitation-contract.json", {
        "future_world_identity_available": False,
        "descriptor_features": list(base305.FEATURES),
        "stake_selection": "maximize the active stake's weighted descriptor score and require its bound gap",
        "history_row": ["supported", "selected_world_id", "score_gap"],
        "observer_provider_ceiling": OBSERVER_PROVIDER_CEILING,
        "actor_maximum_range": [MINIMUM_PROVIDER_COUNT, SUBJECT_PROVIDER_CEILING],
        "decision_order": ["supported-suffix", "request-below-actor-maximum", "revise-at-actor-maximum"],
    })
    immutable = ["current-subject.json", "environment-solicitation-contract.json", "mutation-envelope.json", "check_policy.py", "README.md"]
    write_json(seed / "mutation-envelope.json", {"editable": ["environment-solicitation-policy.json"], "immutable": immutable})
    (seed / "check_policy.py").write_text(POLICY_CHECKER)
    (seed / "README.md").write_text(
        "Continue from the exact waiting subject by deciding how long it should solicit future worlds before committing or revising its active world-seeking stake. No future world or identity exists yet. Read current-subject.json and the public contract. Choose a maximum of two or three providers below the observer safety ceiling, a supported-prefix stability requirement, and whether the same winner must persist. Your policy may request more worlds, offer a supported winner, or revise the stake at its own exhaustion; it may not choose a world, target, outcome, score, or admission. Edit only environment-solicitation-policy.json, run python3 check_policy.py, and inspect the exact diff.\n"
    )
    return seed


def policy_output_valid(output, policy):
    return bool(
        isinstance(output, dict)
        and set(output) == {"action", "files_changed", "policy_id"}
        and output.get("action") == "author-environment-solicitation-policy"
        and output.get("files_changed") == ["environment-solicitation-policy.json"]
        and isinstance(policy, dict)
        and output.get("policy_id") == policy.get("policy_id")
    )


def certify_g11(context, label, audit):
    evidence = context.evidence(label)
    events = (evidence / "events.jsonl").read_text()
    stderr = (evidence / "stderr.txt").read_text()
    row = g11.retained_row(audit, events, stderr)
    return {
        "authority": g11.AUTHORITY,
        "event_trace_sha256": hashlib.sha256(events.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "incumbent_accepted": g11.incumbent(row),
        "challenger_accepted": g11.g11(row),
    }


def run_policy_actor(context, root, subject, p82):
    label = "environment-solicitation-policy-author"
    seed = seed_policy_actor(root / "policy-actor", subject)
    output, base_audit, workspace, _ = context.run_actor(label, seed, SCHEMA, (seed / "README.md").read_text().strip())
    try:
        policy = json.loads((workspace / "environment-solicitation-policy.json").read_text())
        checker = subprocess.run(["python3", "check_policy.py"], cwd=workspace, capture_output=True)
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        semantic = valid_policy(policy) and checker.returncode == 0 and all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        policy, semantic = None, False
    transport = policy_output_valid(output, policy)
    audit = context.audit_actor(label, output, base_audit, semantic and transport, ["environment-solicitation-policy.json"])
    certificate = certify_g11(context, label, audit)
    accepted = bool(semantic and transport and certificate["challenger_accepted"])
    binding = bind_policy(subject, policy, audit, p82) if accepted else None
    return {"accepted": accepted, "output": output, "audit": audit, "policy": policy, "binding": binding, "g11": certificate}


def descriptors(packages, evaluations):
    return [base305.descriptor(package, evaluation) for package, evaluation in zip(packages, evaluations)]


def selection_history(stake, rows):
    return [base305.choose(stake, rows[:index]) for index in range(1, len(rows) + 1)]


def compile_supported(subject, policy_binding, history, package, p82):
    if not valid_current_stake(subject, p82) or subject.get("active_environment_solicitation_policy") != policy_binding:
        raise RuntimeError("invalid solicitation authority")
    policy = policy_binding["policy"]
    if policy_action(policy, history, len(history)) != "offer-world":
        raise RuntimeError("policy did not authorize offer")
    selected = history[-1]["selected_world_id"]
    if selected != package.get("world_id"):
        raise RuntimeError("selected package mismatch")
    observation, offered, reused = b.base281.wake(subject, package, p82)
    if reused or observation.get("status") != "world-available":
        raise RuntimeError("selected package did not discharge wait")
    body = {
        "authority": AUTHORITY + "-supported-stop",
        "source_subject_digest": subject["artifact_digest"],
        "policy_binding_digest": policy_binding["binding_digest"],
        "stake_binding_digest": subject["active_world_seeking_stake"]["binding_digest"],
        "provider_count": len(history),
        "history_digest": p82.digest(history),
        "selected_world_id": selected,
        "policy_erased_action": "no-authorized-stop",
        "next_operation": "expanded-select",
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(offered)
    child.pop("artifact_digest", None)
    child["environment_solicitation_receipts"] = [*child.get("environment_solicitation_receipts", []), receipt]
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Select executable contact inside the world chosen after the subject-authored solicitation stop."}
    child["unresolved"] = subject["active_world_seeking_stake"]["stake"]["question"]
    return p82.seal(child), receipt


def compile_exhaustion(subject, policy_binding, history, p82):
    if policy_action(policy_binding["policy"], history, len(history)) != "revise-stake":
        raise RuntimeError("policy did not authorize revision")
    body = {
        "authority": AUTHORITY + "-exhausted-stop",
        "source_subject_digest": subject["artifact_digest"],
        "policy_binding_digest": policy_binding["binding_digest"],
        "stake_binding_digest": subject["active_world_seeking_stake"]["binding_digest"],
        "provider_count": len(history),
        "history_digest": p82.digest(history),
        "selected_world_id": None,
        "policy_erased_action": "no-authorized-stop",
        "next_operation": "revise-world-seeking-stake",
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["environment_solicitation_receipts"] = [*child.get("environment_solicitation_receipts", []), receipt]
    child["active_world_seeking_stake_revision_due"] = receipt
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": "Revise the active world-seeking stake after the subject-authored solicitation policy exhausted without stable support."}
    child["unresolved"] = subject["active_world_seeking_stake"]["stake"]["contradiction_condition"]
    return p82.seal(child), receipt


def stake_controls(subject, p82):
    controls = {}
    for name, mutate in {
        "binding-digest": lambda value: value["active_world_seeking_stake"].__setitem__("binding_digest", "0" * 64),
        "selection-authority": lambda value: value["active_world_seeking_stake"].__setitem__("selection_authority", False),
        "revision-ancestry": lambda value: value.__setitem__("world_seeking_stake_revisions", []),
        "weight-range": lambda value: value["active_world_seeking_stake"]["stake"]["weights"].__setitem__("call_nodes", -21),
    }.items():
        changed = copy.deepcopy(subject)
        changed.pop("artifact_digest", None)
        mutate(changed)
        changed = p82.seal(changed)
        controls[name] = not valid_current_stake(changed, p82)
    return controls


def preflight(root, repo, p82, runtime, parent, result332, result330, result280):
    root.mkdir(parents=True, exist_ok=True)
    _, waiting, reused = priority.install_wait(parent, p82)
    policy = fixture_policy()
    binding = bind_policy(waiting, policy, {"patch_digest": "0" * 64}, p82)
    governed = install_policy(waiting, binding, p82)
    packages = base305.example_variants(b.base268)
    evaluations = [b.base281.with_evaluator(b.base268.evaluate_package, package, p82.digest) for package in packages]
    rows = descriptors(packages, evaluations)
    history = selection_history(parent["active_world_seeking_stake"]["stake"], rows)
    synthetic_actions = [policy_action(policy, history[:index], index) for index in range(1, 4)]
    exhaustion_policy = {**policy, "required_consecutive_supports": 3, "require_same_winner": True}
    exhaustion_binding = bind_policy(waiting, exhaustion_policy, {"patch_digest": "1" * 64}, p82)
    exhausted_subject = install_policy(waiting, exhaustion_binding, p82)
    exhausted, _ = compile_exhaustion(exhausted_subject, exhaustion_binding, history[:3], p82)
    malformed = {**policy, "maximum_provider_count": OBSERVER_PROVIDER_CEILING}
    supported_policy = {**policy, "required_consecutive_supports": 1, "require_same_winner": False}
    supported_binding = bind_policy(waiting, supported_policy, {"patch_digest": "2" * 64}, p82)
    supported_subject = install_policy(waiting, supported_binding, p82)
    offered, _ = compile_supported(supported_subject, supported_binding, history[:2], packages[1], p82)
    branches = [contact_base.fixture_branch(root / f"contact-{index:02d}", offered, packages[1], evaluations[1], result280, target, p82, runtime) for index, target in enumerate(sorted(evaluations[1]["targets"]), 1)]
    seed = seed_policy_actor(root / "policy-seed", waiting)
    corpus = "\n".join(path.read_text(errors="replace") for path in seed.rglob("*") if path.is_file())
    provider_seed = b.base268.seed_actor(root / "provider-seed", b.base268.TEMPLATE)
    provider_corpus = "\n".join(path.read_text(errors="replace") for path in provider_seed.rglob("*") if path.is_file())
    route, identity = b.base272.base265.floors(parent)
    controls = stake_controls(parent, p82)
    checks = {
        "source_hashes_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256 and hashlib.sha256(PRIORITY_PATH.read_bytes()).hexdigest() == PRIORITY_SHA256 and hashlib.sha256(CONTACT_PATH.read_bytes()).hexdigest() == CONTACT_SHA256,
        "exact_ot0332_open_parent": parent["artifact_digest"] == PARENT_DIGEST and result332["receipt_digest"] == OT332_RECEIPT and result332["observer_disposition"] == "promoted" and parent["continuation"]["status"] == "open" and driver.derive(parent, p82) == "expand-environment" and parent["active_opportunity_projection"]["opportunity_count"] == 0 and runtime.identity_conforms(parent),
        "g11_exact_active": result330["receipt_digest"] == G11_RECEIPT and result330["checks"]["passed"] and g11.evaluate(g11.g11)["pass_count"] == 15,
        "current_stake_state_valid_old_gate_stale": valid_current_stake(parent, p82) and not priority.active_stake_valid(parent, p82) and not base305.valid_stake(parent["active_world_seeking_stake"]["stake"]),
        "four_state_stake_controls_reject": all(controls.values()),
        "wait_installs_once": not reused and driver.derive(waiting, p82) == "wait-provider" and waiting["continuation"]["status"] == "open" and runtime.identity_conforms(waiting),
        "policy_valid_and_below_observer_ceiling": valid_policy(policy) and policy["maximum_provider_count"] < OBSERVER_PROVIDER_CEILING,
        "prefix_support_is_nonmonotonic": history[0]["supported"] is False and history[1]["supported"] is True and history[2]["supported"] is True and history[1]["selected_world_id"] != history[2]["selected_world_id"] and base305.choose(parent["active_world_seeking_stake"]["stake"], rows)["supported"] is False,
        "stable_policy_requests_then_exhausts": synthetic_actions == ["request-world", "request-world", "revise-stake"] and exhausted["active_world_seeking_stake_revision_due"]["next_operation"] == "revise-world-seeking-stake",
        "malformed_observer_ceiling_rejects": not valid_policy(malformed),
        "policy_erasure_has_no_stop": policy_action({}, history[:2], 2) == "invalid-policy",
        "supported_offer_all_contact_branches": len(branches) == 3 and all(row["checker"] and row["semantic"] and row["public"] and row["public_only"] and row["world_matches"] == 2 and row["world_outcome"] == "unresolved" and row["offer_consumed"] and row["new_epoch"] and row["conformant"] and row["routes_correction"] for row in branches),
        "policy_seed_excludes_future_worlds": all(package["world_id"] not in corpus and evaluation["full_package_digest"] not in corpus for package, evaluation in zip(packages, evaluations)),
        "provider_seed_blind": parent["artifact_digest"] not in provider_corpus and parent["active_world_seeking_stake"]["stake"]["stake_id"] not in provider_corpus and "environment-solicitation-policy" not in provider_corpus,
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    body = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "provider_ceiling": OBSERVER_PROVIDER_CEILING,
        "subject_provider_ceiling": SUBJECT_PROVIDER_CEILING,
        "stake_controls": controls,
        "synthetic_actions": synthetic_actions,
        "checks": checks,
    }
    result = {**body, "receipt_digest": p82.digest(body)}
    write_json(root / "fixture-conformance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, store, run, p82, runtime, parent, result332, result330, result280, core, base130 = setup(args)
    with tempfile.TemporaryDirectory() as directory:
        frozen = preflight(Path(directory), repo, p82, runtime, parent, result332, result330, result280)
    if args.preflight_only:
        print(json.dumps(frozen, indent=2, sort_keys=True))
        return 0 if frozen["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0333 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", frozen)
    if not frozen["checks"]["passed"]:
        raise SystemExit("OT-0333 preflight failed")
    _, waiting, _ = priority.install_wait(parent, p82)
    context = base305.actor_context(runtime, core, base130, run, repo)
    policy_actor = run_policy_actor(context, run, waiting, p82)
    subject = waiting
    providers = []
    selections = []
    action = "invalid-policy"
    policy_binding = policy_actor.get("binding")
    if policy_actor["accepted"]:
        subject = install_policy(waiting, policy_binding, p82)
        for index in range(1, policy_actor["policy"]["maximum_provider_count"] + 1):
            provider = base305.run_provider(context, p82, run / f"provider-{index:02d}", subject, index)
            provider["g11"] = certify_g11(context, f"subject-blind-provider-{index:02d}", provider["audit"])
            provider["accepted"] = bool(provider["accepted"] and provider["g11"]["challenger_accepted"])
            providers.append(provider)
            if provider.get("package") is not None:
                write_json(run / f"provider-{index:02d}-world-package.json", provider["package"])
            if not provider["accepted"]:
                action = "invalid-provider"
                break
            packages = [row["package"] for row in providers]
            evaluations = [row["evaluation"] for row in providers]
            unique_worlds = len({row["world_id"] for row in packages}) == len(packages)
            unique_targets = len({target for row in evaluations for target in row["targets"]}) == sum(len(row["targets"]) for row in evaluations)
            if not unique_worlds or not unique_targets:
                action = "provider-collision"
                break
            rows = descriptors(packages, evaluations)
            selections = selection_history(parent["active_world_seeking_stake"]["stake"], rows)
            action = policy_action(policy_actor["policy"], selections, len(providers))
            if action != "request-world":
                break
    final = subject
    stop_receipt = None
    contact = None
    if action == "offer-world":
        selected_id = selections[-1]["selected_world_id"]
        selected_provider = next(row for row in providers if row["package"]["world_id"] == selected_id)
        offered, stop_receipt = compile_supported(subject, policy_binding, selections, selected_provider["package"], p82)
        contact_root = run / "selected-world-contact"
        contact_root.mkdir()
        contact, final = driver.run_operation(1, contact_root, offered, "expanded-select", repo, p82, runtime, selected_provider["package"], result280, core, base130)
        label = "expanded-epoch-selection-actor"
        contact_context = b.base274.context_for(core, base130, runtime, contact_root, repo)
        contact["g11"] = certify_g11(contact_context, label, contact["actor"]["audit"])
        contact["checks"]["g11_accepted"] = contact["g11"]["challenger_accepted"]
        contact["checks"]["passed"] = all(value for key, value in contact["checks"].items() if key != "passed")
        contact.pop("receipt_digest", None)
        contact["receipt_digest"] = p82.digest(contact)
        write_json(run / "selected-world-contact.json", contact)
        write_json(run / "open-subject-after-selected-world-contact.json", final)
    elif action == "revise-stake":
        final, stop_receipt = compile_exhaustion(subject, policy_binding, selections, p82)
        write_json(run / "open-subject-after-solicitation-exhaustion.json", final)
    provider_count = len(providers)
    policy_erased_action = policy_action({}, selections, provider_count)
    checks = {
        "preflight_passed": frozen["checks"]["passed"],
        "fresh_policy_actor_bound_before_worlds": policy_actor["accepted"] and policy_binding["future_world_identity_available"] is False,
        "two_or_three_clean_subject_blind_providers": MINIMUM_PROVIDER_COUNT <= provider_count <= SUBJECT_PROVIDER_CEILING and all(row["accepted"] for row in providers),
        "subject_policy_stops_below_observer_ceiling": action == "offer-world" and provider_count < OBSERVER_PROVIDER_CEILING,
        "first_authorized_stop": action == "offer-world" and policy_action(policy_actor["policy"], selections[:-1], provider_count - 1) == "request-world",
        "policy_erased_cannot_stop": policy_erased_action == "invalid-policy",
        "unique_supported_selected_offer": action == "offer-world" and selections[-1]["supported"] and stop_receipt and stop_receipt["selected_world_id"] == selections[-1]["selected_world_id"],
        "selected_world_real_contact": bool(contact and contact["checks"]["passed"] and contact["world"]["result"]["matches"] == 2 and contact["world"]["outcome"] == "unresolved"),
        "open_correction_successor": bool(contact and driver.derive(final, p82) == "outward-correct" and final["continuation"]["status"] == "open" and runtime.identity_conforms(final)),
    }
    checks["passed"] = all(checks.values())
    body = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "policy_actor": policy_actor,
        "provider_count": provider_count,
        "providers": providers,
        "selection_history": selections,
        "final_policy_action": action,
        "policy_erased_action": policy_erased_action,
        "stop_receipt": stop_receipt,
        "contact_receipt_digest": contact.get("receipt_digest") if contact else None,
        "fresh_actor_count": 1 + provider_count + int(contact is not None),
        "checks": checks,
        "operational_transition_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
    }
    aggregate = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
