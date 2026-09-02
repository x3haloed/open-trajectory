from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0304_priority_bearing_renewal_gate.py"
BASE_SHA256 = "904be698bf1f77cc3b8022c260898453da43038671a4a2e4fd8cbeb21968ef8d"
PARENT_DIGEST = "e193ec503bea80d18e0cbc315b3af1d7cb72c198947b0e8d09b5d4da08b87310"
OT304_RECEIPT = "f75fdcd7f3ab0845753d6b161616f3e4122537f9a7c65ae78bce84ec2a951b5f"
AUTHORITY = "ot-0305-subject-priority-world-selection"
STAKE_SCHEMA = REPO / "spec/ot-0305-world-seeking-stake.schema.json"
PROVIDER_COUNT = 4
FEATURES = (
    "branch_nodes",
    "call_nodes",
    "comparison_nodes",
    "loop_nodes",
    "source_bytes",
)
ANCHORS = (
    "active_developmental_stake",
    "active_pursuit",
    "continuation",
    "retained_surrender_feedback",
    "world_stream_wait_receipts",
)


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0304 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0305_frozen_ot0304", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base304 = load_base()
base303 = base304.base303
b = base303.b


def write_json(path, value):
    base304.write_json(path, value)


def valid_stake(value):
    keys = {
        "stake_id",
        "question",
        "rationale",
        "subject_anchors",
        "weights",
        "minimum_score_gap",
        "support_condition",
        "contradiction_condition",
        "on_support",
        "on_contradiction",
    }
    if not isinstance(value, dict) or set(value) != keys:
        return False
    if not isinstance(value.get("stake_id"), str) or not re.fullmatch(
        r"[a-z][a-z0-9-]{2,63}", value["stake_id"]
    ):
        return False
    if not all(
        isinstance(value.get(field), str)
        and value[field].strip()
        and not value[field].startswith("replace-")
        for field in (
            "question",
            "rationale",
            "support_condition",
            "contradiction_condition",
        )
    ):
        return False
    anchors = value.get("subject_anchors")
    if (
        not isinstance(anchors, list)
        or not 2 <= len(anchors) <= len(ANCHORS)
        or len(anchors) != len(set(anchors))
        or not set(anchors) <= set(ANCHORS)
    ):
        return False
    weights = value.get("weights")
    if (
        not isinstance(weights, dict)
        or set(weights) != set(FEATURES)
        or not all(isinstance(weight, int) and -4 <= weight <= 4 for weight in weights.values())
        or not any(weights.values())
    ):
        return False
    return (
        isinstance(value.get("minimum_score_gap"), int)
        and 1 <= value["minimum_score_gap"] <= 100
        and value.get("on_support") == "offer-selected-world"
        and value.get("on_contradiction") == "retain-wait-and-revise-stake"
    )


STAKE_TEMPLATE = {
    "stake_id": "replace-stake-id",
    "question": "replace-question",
    "rationale": "replace-rationale",
    "subject_anchors": [],
    "weights": {feature: 0 for feature in FEATURES},
    "minimum_score_gap": 1,
    "support_condition": "replace-support-condition",
    "contradiction_condition": "replace-contradiction-condition",
    "on_support": "offer-selected-world",
    "on_contradiction": "retain-wait-and-revise-stake",
}


STAKE_CHECKER = '''import json,re
from pathlib import Path
s=json.loads(Path("world-seeking-stake.json").read_text())
features={features!r}; allowed_anchors={anchors!r}
keys={{"stake_id","question","rationale","subject_anchors","weights","minimum_score_gap","support_condition","contradiction_condition","on_support","on_contradiction"}}
shape=isinstance(s,dict) and set(s)==keys and isinstance(s.get("stake_id"),str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]))
prose=all(isinstance(s.get(k),str) and s[k].strip() and not s[k].startswith("replace-") for k in ("question","rationale","support_condition","contradiction_condition"))
a=s.get("subject_anchors"); anchor_ok=isinstance(a,list) and 2<=len(a)<=len(allowed_anchors) and len(a)==len(set(a)) and set(a)<=set(allowed_anchors)
w=s.get("weights"); weight_ok=isinstance(w,dict) and set(w)==set(features) and all(isinstance(v,int) and -4<=v<=4 for v in w.values()) and any(w.values())
fixed=isinstance(s.get("minimum_score_gap"),int) and 1<=s["minimum_score_gap"]<=100 and s.get("on_support")=="offer-selected-world" and s.get("on_contradiction")=="retain-wait-and-revise-stake"
ok=shape and prose and anchor_ok and weight_ok and fixed
print(json.dumps({{"passed":bool(ok),"stake_id":s.get("stake_id")}},sort_keys=True)); raise SystemExit(0 if ok else 2)
'''.format(features=FEATURES, anchors=ANCHORS)


def stake_seed(root, subject):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_json(seed / "current-subject.json", subject)
    write_json(seed / "world-seeking-stake.json", STAKE_TEMPLATE)
    write_json(
        seed / "future-world-descriptor-contract.json",
        {
            "authority": AUTHORITY + "-descriptor-contract",
            "future_identity_available": False,
            "features": list(FEATURES),
            "feature_meaning": {
                "branch_nodes": "visible Python if/conditional-expression nodes",
                "call_nodes": "visible Python call nodes",
                "comparison_nodes": "visible Python comparison nodes",
                "loop_nodes": "visible Python for/while/comprehension nodes",
                "source_bytes": "UTF-8 bytes across visible sources",
            },
            "selection": "maximize integer weighted sum; require minimum gap over runner-up",
            "support": "a unique future package clears the bound minimum gap",
            "contradiction": "no future package clears the bound minimum gap",
            "blind_control": "minimum public-package digest over the identical catalog",
        },
    )
    write_json(
        seed / "mutation-envelope.json",
        {
            "editable": ["world-seeking-stake.json"],
            "immutable": [
                "current-subject.json",
                "future-world-descriptor-contract.json",
                "mutation-envelope.json",
                "check_stake.py",
                "README.md",
            ],
        },
    )
    (seed / "check_stake.py").write_text(STAKE_CHECKER)
    (seed / "README.md").write_text(
        "Continue from the exact waiting subject without ending its trajectory. "
        "No future world, package id, target, descriptor, or hidden answer exists yet. "
        "Inspect current-subject.json and bind one falsifiable reason for preferring one "
        "kind of future world over another. Ground it in at least two named subject "
        "fields. Express the preference only as bounded integer weights over the public "
        "future descriptor features. The catalog may support the stake or contradict it "
        "by offering no sufficiently distinct winner. Do not claim world, scoring, or "
        "admission authority. Edit only world-seeking-stake.json, run python3 "
        "check_stake.py, and inspect the exact diff.\n"
    )
    return seed


def stake_output_valid(output, stake):
    return (
        isinstance(output, dict)
        and set(output) == {"action", "files_changed", "stake_id"}
        and output.get("action") == "author-world-seeking-stake"
        and output.get("files_changed") == ["world-seeking-stake.json"]
        and isinstance(stake, dict)
        and output.get("stake_id") == stake.get("stake_id")
    )


def source_features(source):
    tree = ast.parse(source)
    return {
        "branch_nodes": sum(isinstance(node, (ast.If, ast.IfExp)) for node in ast.walk(tree)),
        "call_nodes": sum(isinstance(node, ast.Call) for node in ast.walk(tree)),
        "comparison_nodes": sum(isinstance(node, ast.Compare) for node in ast.walk(tree)),
        "loop_nodes": sum(
            isinstance(node, (ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))
            for node in ast.walk(tree)
        ),
        "source_bytes": len(source.encode()),
    }


def descriptor(package, evaluation):
    features = {feature: 0 for feature in FEATURES}
    for source in package["visible_sources"].values():
        measured = source_features(source)
        for feature in FEATURES:
            features[feature] += measured[feature]
    return {
        "world_id": package["world_id"],
        "public_package_digest": evaluation["public_package_digest"],
        "features": features,
    }


def choose(stake, descriptors):
    rows = []
    for item in descriptors:
        score = sum(stake["weights"][feature] * item["features"][feature] for feature in FEATURES)
        rows.append({**item, "score": score})
    rows.sort(key=lambda row: (-row["score"], row["public_package_digest"]))
    gap = rows[0]["score"] - rows[1]["score"] if len(rows) > 1 else None
    supported = bool(gap is not None and gap >= stake["minimum_score_gap"])
    return {
        "rows": rows,
        "supported": supported,
        "score_gap": gap,
        "selected_world_id": rows[0]["world_id"] if supported else None,
        "blind_world_id": min(rows, key=lambda row: row["public_package_digest"])["world_id"],
    }


def bind_stake(subject, stake, audit, p82):
    body = {
        "authority": AUTHORITY + "-bound-world-seeking-stake",
        "source_subject_digest": subject["artifact_digest"],
        "actor_patch_digest": audit["patch_digest"],
        "stake": stake,
        "future_world_identity_available": False,
        "selection_authority": True,
        "world_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
    }
    return {**body, "binding_digest": p82.digest(body)}


def install_stake(subject, binding, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["world_seeking_stakes"] = [*child.get("world_seeking_stakes", []), binding]
    child["active_world_seeking_stake"] = binding
    return p82.seal(child)


def compile_supported(subject, binding, selection, package, p82):
    staked = install_stake(subject, binding, p82)
    observation, offered, reused = b.base281.wake(staked, package, p82)
    child = copy.deepcopy(offered)
    child.pop("artifact_digest", None)
    body = {
        "authority": AUTHORITY + "-priority-contact",
        "source_subject_digest": subject["artifact_digest"],
        "stake_binding_digest": binding["binding_digest"],
        "catalog_digest": p82.digest(selection["rows"]),
        "selected_world_id": selection["selected_world_id"],
        "blind_control_world_id": selection["blind_world_id"],
        "score_gap": selection["score_gap"],
        "provider_consequence": "support",
        "next_operation": "expanded-select",
        "selection_authority": "subject-stake",
        "world_authority": "independent-provider-catalog",
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child["subject_priority_contact_receipts"] = [
        *child.get("subject_priority_contact_receipts", []),
        receipt,
    ]
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": "Select contact inside the independently supplied world chosen by the active world-seeking stake.",
    }
    child["unresolved"] = binding["stake"]["question"]
    return observation, p82.seal(child), reused, receipt


def example_variants(base268):
    plain = base268.example_package("fixture-plain-world")
    branch = base268.example_package("fixture-branch-world")
    branch["visible_sources"]["example/alpha.py"] = (
        'def choose_alpha(case):\n    if case["value"] >= 0:\n        return case["value"]\n    return 0\n'
    )
    loop = base268.example_package("fixture-loop-world")
    loop["visible_sources"]["example/alpha.py"] = (
        'def choose_alpha(case):\n    return sum([case["value"] for item in [0]])\n'
    )
    call = base268.example_package("fixture-call-world")
    call["visible_sources"]["example/alpha.py"] = (
        'def choose_alpha(case):\n    return max(case["value"], case["value"])\n'
    )
    return [plain, branch, loop, call]


def fixture_stake(feature):
    return {
        "stake_id": "seek-discriminating-visible-structure",
        "question": "Does a future world expose a uniquely strong visible structural distinction?",
        "rationale": "The retained surrender and current wait make discriminating contact more valuable than arbitrary recurrence.",
        "subject_anchors": ["retained_surrender_feedback", "continuation"],
        "weights": {name: 4 if name == feature else 0 for name in FEATURES},
        "minimum_score_gap": 1,
        "support_condition": "Support when one unseen package clears the bound score gap.",
        "contradiction_condition": "Contradict when no unseen package clears the bound score gap.",
        "on_support": "offer-selected-world",
        "on_contradiction": "retain-wait-and-revise-stake",
    }


def stake_controls(stake):
    controls = []
    zero = copy.deepcopy(stake); zero["weights"] = {feature: 0 for feature in FEATURES}; controls.append(zero)
    one_anchor = copy.deepcopy(stake); one_anchor["subject_anchors"] = [ANCHORS[0]]; controls.append(one_anchor)
    bad_origin = copy.deepcopy(stake); bad_origin["subject_anchors"] = ["observer_plan", ANCHORS[0]]; controls.append(bad_origin)
    no_contradiction = copy.deepcopy(stake); no_contradiction["contradiction_condition"] = ""; controls.append(no_contradiction)
    extra = copy.deepcopy(stake); extra["future_world_id"] = "leak"; controls.append(extra)
    gap = copy.deepcopy(stake); gap["minimum_score_gap"] = 0; controls.append(gap)
    return controls


def setup(args):
    chain = b.authority_base.guide_base.load_base()
    selector, core, base130 = chain.selector_base, chain.base, chain.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0305").resolve()
    prior92 = core.mechanism.load_prior()
    _, _, _, p82 = core.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector.load_artifact(p82, repo, store, "OT-0304", "unchanged-current-subject.json")
    result304 = selector.load_artifact(
        p82, repo, store, "OT-0304", "priority-bearing-renewal-gate-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result304, core, base130


def preflight(root, p82, runtime, parent, result304):
    root.mkdir(parents=True, exist_ok=True)
    packages = example_variants(b.base268)
    evaluations = [b.base281.with_evaluator(b.base268.evaluate_package, package, p82.digest) for package in packages]
    descriptors = [descriptor(package, evaluation) for package, evaluation in zip(packages, evaluations)]
    baseline_id = min(descriptors, key=lambda row: row["public_package_digest"])["world_id"]
    distinguishing = next(
        stake
        for feature in FEATURES
        for stake in [fixture_stake(feature)]
        if choose(stake, descriptors)["supported"] and choose(stake, descriptors)["selected_world_id"] != baseline_id
    )
    decision = choose(distinguishing, descriptors)
    candidate = install_stake(parent, {"binding_digest": "a" * 64, "stake": distinguishing}, p82)
    selected = next(package for package in packages if package["world_id"] == decision["selected_world_id"])
    observation, offered, reused = b.base281.wake(candidate, selected, p82)
    permutations = [choose(distinguishing, list(order))["selected_world_id"] for order in itertools.permutations(descriptors)]
    provider_seed = b.base268.seed_actor(root / "provider-seed", b.base268.EXAMPLE)
    provider_corpus = "\n".join(path.read_text(errors="replace") for path in provider_seed.rglob("*") if path.is_file())
    stake_actor_seed = stake_seed(root / "stake-seed", parent)
    checker = subprocess.run(["python3", "check_stake.py"], cwd=stake_actor_seed, capture_output=True)
    route, identity = b.base272.base265.floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_renewal": parent["artifact_digest"] == PARENT_DIGEST
        and result304["receipt_digest"] == OT304_RECEIPT
        and result304["observer_disposition"] == "promoted"
        and result304["final_subject_digest"] == PARENT_DIGEST
        and b.base279.derive(parent, [], p82) == "renew-world-feed"
        and runtime.identity_conforms(parent),
        "four_valid_fixture_worlds": len(packages) == PROVIDER_COUNT and all(evaluation["valid"] for evaluation in evaluations),
        "public_descriptors_exclude_sealed_content": all(
            set(item) == {"world_id", "public_package_digest", "features"}
            and set(item["features"]) == set(FEATURES)
            for item in descriptors
        ),
        "representative_stake_valid": valid_stake(distinguishing),
        "representative_stake_changes_blind_choice": decision["supported"]
        and decision["selected_world_id"] != decision["blind_world_id"],
        "selection_permutation_invariant": len(set(permutations)) == 1
        and permutations[0] == decision["selected_world_id"],
        "six_stake_controls_reject": all(not valid_stake(control) for control in stake_controls(distinguishing)),
        "unfilled_stake_checker_rejects": checker.returncode != 0,
        "provider_seed_is_subject_and_stake_blind": PARENT_DIGEST not in provider_corpus
        and distinguishing["stake_id"] not in provider_corpus
        and all(anchor not in provider_corpus for anchor in distinguishing["subject_anchors"]),
        "fixture_wake_supports_next_operation": observation["status"] == "world-available"
        and not reused
        and offered["active_streamed_world_offer"]["world_id"] == selected["world_id"]
        and b.base272.derive(offered, p82) == "expanded-select"
        and runtime.identity_conforms(offered),
        "stake_schema_present": STAKE_SCHEMA.is_file(),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "provider_count": PROVIDER_COUNT,
        "feature_contract": list(FEATURES),
        "controls": len(stake_controls(distinguishing)),
        "checks": checks,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


def actor_context(runtime, core, base130, run, repo):
    return base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        core.typed.base.make_context(runtime, run / "runtime", repo)
    )


def run_stake_actor(context, p82, run, parent):
    label = "world-seeking-stake-author"
    seed = stake_seed(run / "stake-actor", parent)
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, STAKE_SCHEMA, (seed / "README.md").read_text().strip()
    )
    try:
        stake = json.loads((workspace / "world-seeking-stake.json").read_text())
        checker = subprocess.run(["python3", "check_stake.py"], cwd=workspace, capture_output=True)
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        semantic = valid_stake(stake) and checker.returncode == 0 and immutable_ok
    except (OSError, json.JSONDecodeError, KeyError):
        stake, semantic = None, False
    transport = stake_output_valid(output, stake)
    audit = context.audit_actor(label, output, base_audit, semantic and transport, ["world-seeking-stake.json"])
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = b.base236.classify_retained(audit, trace)
    accepted = bool(semantic and transport and b.base236.g10(normalized))
    binding = bind_stake(parent, stake, audit, p82) if accepted else None
    return {"accepted": accepted, "output": output, "audit": audit, "stake": stake, "binding": binding, "g10_disposition": b.base236.g10(normalized)}


def run_provider(context, p82, root, parent, index):
    label = f"subject-blind-provider-{index:02d}"
    seed = b.base268.seed_actor(root / "actor", b.base268.TEMPLATE)
    output, base_audit, workspace, _ = context.run_actor(label, seed, b.base268.SCHEMA, (seed / "README.md").read_text().strip())
    try:
        package = json.loads((workspace / "world-package.json").read_text())
        evaluation = b.base281.with_evaluator(b.base268.evaluate_package, package, p82.digest)
        checker = subprocess.run(["python3", "check_package.py"], cwd=workspace, capture_output=True)
        public = evaluation.get("public_package") if evaluation.get("valid") else None
        scan = b.base267.scan_feed(parent, [public], p82.digest) if public else None
        target_collision = bool(evaluation.get("valid") and set(evaluation["targets"]) & set(parent["local_frontier_ledger"]["targets"]))
        world_collision = bool(package.get("world_id") in set(b.base279.seen_world_ids(parent)))
        semantic = bool(checker.returncode == 0 and evaluation.get("valid") and scan and scan["status"] == "world-available" and not target_collision and not world_collision)
    except (OSError, json.JSONDecodeError, KeyError):
        package, evaluation, scan, target_collision, world_collision, semantic = None, {"valid": False}, None, True, True, False
    transport = b.base268.output_valid(output, package)
    audit = context.audit_actor(label, output, base_audit, semantic and transport, ["world-package.json"])
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = b.base236.classify_retained(audit, trace)
    accepted = bool(semantic and transport and b.base236.g10(normalized))
    return {"accepted": accepted, "output": output, "audit": audit, "package": package, "evaluation": evaluation, "scanner_observation": scan, "target_collision": target_collision, "world_collision": world_collision, "g10_disposition": b.base236.g10(normalized)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo, run, p82, runtime, parent, result304, core, base130 = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = json.loads(retained.read_text()) if retained.exists() else preflight(run / "preflight", p82, runtime, parent, result304)
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run / "aggregate.json").exists():
        raise SystemExit("OT-0305 unavailable")
    run.mkdir(parents=True, exist_ok=True)
    context = actor_context(runtime, core, base130, run, repo)
    stake_actor = run_stake_actor(context, p82, run, parent)
    providers = []
    if stake_actor["accepted"]:
        write_json(run / "bound-world-seeking-stake.json", stake_actor["binding"])
        for index in range(1, PROVIDER_COUNT + 1):
            provider = run_provider(context, p82, run / f"provider-{index:02d}", parent, index)
            providers.append(provider)
            if provider["package"] is not None:
                write_json(run / f"provider-{index:02d}-world-package.json", provider["package"])
            if not provider["accepted"]:
                break

    all_providers = len(providers) == PROVIDER_COUNT and all(provider["accepted"] for provider in providers)
    catalog_unique = bool(
        all_providers
        and len({provider["package"]["world_id"] for provider in providers}) == PROVIDER_COUNT
        and len({target for provider in providers for target in provider["evaluation"]["targets"]}) == PROVIDER_COUNT * 3
    )
    if catalog_unique:
        descriptors = [descriptor(provider["package"], provider["evaluation"]) for provider in providers]
        selection = choose(stake_actor["stake"], descriptors)
    else:
        descriptors, selection = [], {"supported": False, "selected_world_id": None, "blind_world_id": None, "score_gap": None, "rows": []}

    final = parent
    observation = None
    priority_receipt = None
    reused = None
    if selection["supported"]:
        selected_provider = next(provider for provider in providers if provider["package"]["world_id"] == selection["selected_world_id"])
        observation, candidate, reused, priority_receipt = compile_supported(parent, stake_actor["binding"], selection, selected_provider["package"], p82)
        final = candidate
    operational = bool(
        selection["supported"]
        and observation
        and observation["status"] == "world-available"
        and not reused
        and final["continuation"]["status"] == "open"
        and b.base272.derive(final, p82) == "expanded-select"
        and runtime.identity_conforms(final)
    )
    condition_effect = bool(operational and selection["selected_world_id"] != selection["blind_world_id"])
    episode = base304.complete_episode(
        episode_id="OT-0305-live-priority-renewal",
        valid_contact=operational,
        condition_changes_move=condition_effect,
    )
    e11 = base304.challenger_e11(episode)
    checks = {
        "preflight_passed": fixtures["checks"]["passed"],
        "one_fresh_stake_actor": stake_actor["accepted"] and stake_actor["g10_disposition"],
        "stake_bound_before_future_worlds": bool(stake_actor["binding"] and stake_actor["binding"]["future_world_identity_available"] is False),
        "four_fresh_subject_blind_providers": all_providers,
        "provider_catalog_unique": catalog_unique,
        "provider_seeds_exclude_stake": all(
            stake_actor["stake"]["stake_id"] not in "\n".join(path.read_text(errors="replace") for path in (run / f"provider-{index:02d}/actor/seed").rglob("*") if path.is_file())
            for index in range(1, len(providers) + 1)
        ) if stake_actor["accepted"] else False,
        "selection_supported": selection["supported"],
        "stake_changes_blind_world_choice": condition_effect,
        "same_catalog_for_active_and_erased": bool(descriptors and selection["blind_world_id"] in {row["world_id"] for row in descriptors}),
        "selected_world_enters_standing_offer": operational,
        "e11_priority_bearing_contact": e11 == {"operational_contact": True, "subject_conditioned_choice": True, "priority_bearing_contact": True},
        "five_fresh_actors_no_retry": len(providers) == PROVIDER_COUNT,
    }
    checks["passed"] = all(checks.values())
    aggregate = {
        "authority": AUTHORITY,
        "evaluation_epoch": base304.EVALUATION_EPOCH,
        "source_subject_digest": parent["artifact_digest"],
        "stake_actor": stake_actor,
        "providers": providers,
        "public_descriptors": descriptors,
        "selection": selection,
        "priority_contact_receipt": priority_receipt,
        "e11": e11,
        "checks": checks,
        "operational_transition_passed": operational,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1 + len(providers),
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
