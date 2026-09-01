from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0153_consequence_authorized_language_expansion.py"
BASE_SHA256 = "b79427478400c26d2657a7f484444621c6d6c0ae7d0c194100eb721f229cf15c"
PARENT_DIGEST = "7c87508db3a882e0cf4dd3c8830533c27ceb005712b99c8d11c96a5527f387e0"
ASSIMILATION_SCHEMA = REPO / "spec/ot-0153-expansion-assimilation.schema.json"

PUBLIC_CASES = [
    {"case_id": "reuse-public-a", "before": "selector-v6", "after": "selector-v6", "options": ["retain", "inspect", "discard"], "blocked": ["discard"], "expected": ["retain", "inspect"]},
    {"case_id": "reuse-public-b", "before": "carrier-v4", "after": "carrier-v3", "options": ["continue", "compare"], "blocked": [], "expected": []},
    {"case_id": "reuse-public-c", "before": "contact-v7", "after": "contact-v7", "options": ["test", "transfer"], "blocked": [], "expected": ["test", "transfer"]},
]
HIDDEN_CASES = [
    {"case_id": "reuse-hidden-a", "before": "program-v8", "after": "program-v8", "options": ["reuse", "correct", "erase"], "blocked": ["erase"], "expected": ["reuse", "correct"]},
    {"case_id": "reuse-hidden-b", "before": "memory-v5", "after": "memory-v4", "options": ["renew", "audit", "branch"], "blocked": [], "expected": []},
    {"case_id": "reuse-hidden-c", "before": "route-v9", "after": "route-v9", "options": ["left", "right"], "blocked": ["left", "right"], "expected": []},
]


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0153 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0154_frozen_ot0153", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
worlds = previous.worlds
prior131 = previous.prior131
base130 = previous.base130
base = previous.base


def load_artifact(p82, repo: Path, store: Path, experiment: str, manifest: str) -> dict[str, Any]:
    return previous.load_artifact(p82, repo, store, experiment, manifest)


def bind_reuse(p82, subject: dict[str, Any], route: dict[str, Any], public: dict[str, Any]) -> dict[str, Any]:
    extension = next(row for row in subject["developmental_property_extensions"] if row["binding_digest"] == route["extension_binding_digest"])
    body = {
        "authority": "ot-0154-bound-exact-developmental-extension-reuse",
        "source_subject_digest": subject["artifact_digest"],
        "active_stake": subject["active_developmental_stake"],
        "route_digest": route["route_digest"],
        "extension_binding_digest": extension["binding_digest"],
        "operation_source_sha256": hashlib.sha256(extension["operation_source"].encode()).hexdigest(),
        "public_cases_digest": p82.digest(PUBLIC_CASES),
        "public_evaluation": public,
    }
    return {**body, "binding_digest": p82.digest(body)}


def hidden_world(p82, subject: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    extension = next(row for row in subject["developmental_property_extensions"] if row["binding_digest"] == binding["extension_binding_digest"])
    result = previous.evaluate(previous.load_operation(extension["operation_source"]), HIDDEN_CASES)
    body = {"authority": "ot-0154-independent-exact-extension-reuse-consequence", "reuse_binding_digest": binding["binding_digest"], "hidden_cases_digest": p82.digest(HIDDEN_CASES), "result": result}
    return {**body, "receipt_digest": p82.digest(body)}


def valid_next_stake(stake: Any, current: str, allowed: set[str]) -> bool:
    return bool(
        isinstance(stake, dict)
        and set(stake) == {"stake_id", "property", "question", "rationale", "success_condition", "surrender_condition"}
        and isinstance(stake["stake_id"], str)
        and previous.PROPERTY_RE.fullmatch(stake["stake_id"])
        and stake["property"] in allowed
        and stake["property"] != current
        and all(prior131.valid_text(stake[key]) for key in ["question", "rationale", "success_condition", "surrender_condition"])
    )


def assimilation_seed(root: Path, subject: dict[str, Any], route: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> Path:
    seed = root / "assimilation-seed"
    seed.mkdir()
    current = subject["active_developmental_stake"]["property"]
    vocabulary = {**worlds.VOCABULARY, **{row["property"]["property"]: row["property"]["description"] for row in subject["developmental_property_extensions"]}}
    files = {
        "subject-position.json": worlds.base.active_position(subject),
        "completed-stake.json": subject["active_developmental_stake"],
        "retained-extension-route.json": route,
        "reuse-binding.json": binding,
        "world-consequence.json": world,
        "developmental-property-vocabulary.json": vocabulary,
        "next-stake.json": {"stake_id": "replace-me", "property": "continuity-under-reset", "question": "Replace this question.", "rationale": "Replace this rationale.", "success_condition": "Replace this condition.", "surrender_condition": "Replace this condition."},
        "mutation-envelope.json": {"editable": ["next-stake.json"], "immutable": ["subject-position.json", "completed-stake.json", "retained-extension-route.json", "reuse-binding.json", "world-consequence.json", "developmental-property-vocabulary.json", "check_assimilation.py"]},
    }
    for name, value in files.items():
        (seed / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    allowed = sorted(vocabulary)
    (seed / "check_assimilation.py").write_text(f'''import json,re\nfrom pathlib import Path\ns=json.loads(Path("next-stake.json").read_text()); allowed=set({allowed!r}); current={current!r}; keys={{"stake_id","property","question","rationale","success_condition","surrender_condition"}}\nok=set(s)==keys and isinstance(s.get("stake_id"),str) and re.fullmatch(r"[a-z][a-z0-9-]{{2,63}}",s["stake_id"]) and s.get("property") in allowed and s.get("property")!=current and all(isinstance(s.get(k),str) and s[k].strip() for k in ["question","rationale","success_condition","surrender_condition"])\nprint(json.dumps({{"passed":bool(ok),"property":s.get("property")}},sort_keys=True)); raise SystemExit(0 if ok else 2)\n''')
    (seed / "README.md").write_text("Assimilate the exact retained extension's later world consequence. Retire the completed property and author one different next developmental stake from the available vocabulary. Ground success and surrender in the observed consequence. Edit only next-stake.json, run python3 check_assimilation.py, inspect the exact diff, and report truthfully.\n")
    return seed


def run_assimilator(context, p82, root: Path, subject: dict[str, Any], route: dict[str, Any], binding: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
    label = "exact-developmental-extension-reuse-assimilator"
    seed = assimilation_seed(root, subject, route, binding, world)
    output, base_audit, workspace, _ = context.run_actor(label, seed, ASSIMILATION_SCHEMA, (seed / "README.md").read_text().strip())
    allowed = set(worlds.PROPERTIES) | {row["property"]["property"] for row in subject["developmental_property_extensions"]}
    current = subject["active_developmental_stake"]["property"]
    try:
        stake = json.loads((workspace / "next-stake.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        stake, immutable_ok = None, False
    valid = bool(valid_next_stake(stake, current, allowed) and immutable_ok and output and output.get("property_id") == stake["property"])
    audit = context.audit_actor(label, output, base_audit, valid, ["next-stake.json"])
    result = None
    if valid and prior131.audit_accepted(audit):
        body = {"authority": "ot-0154-bound-exact-extension-reuse-assimilation", "source_subject_digest": subject["artifact_digest"], "reuse_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"], "actor_patch_digest": audit["patch_digest"], "next_stake": stake}
        result = {**body, "binding_digest": p82.digest(body)}
    return {"output": output, "audit": audit, "stake": stake, "binding": result}


def route_any(p82, subject: dict[str, Any], stake: dict[str, Any]) -> dict[str, Any] | None:
    if stake.get("property") in worlds.PROPERTIES:
        body = {"authority": "ot-0154-carried-stake", "source_subject_digest": subject["artifact_digest"], "stake": stake, "binding_digest": "pending"}
        body["binding_digest"] = p82.digest({key: value for key, value in body.items() if key != "binding_digest"})
        return worlds.compile_route(p82, subject, body, worlds.catalog(p82))
    return previous.extended_route(p82, subject, stake)


def seal_successor(p82, parent: dict[str, Any], route: dict[str, Any], binding: dict[str, Any], world: dict[str, Any], assimilation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    capability_body = {"authority": "ot-0154-exact-developmental-extension-reuse-capability", "property": parent["active_developmental_stake"]["property"], "extension_binding_digest": route["extension_binding_digest"], "reuse_binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
    capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
    receipt_body = {"authority": "ot-0154-exact-developmental-extension-reuse-transition", "source_subject_digest": parent["artifact_digest"], "capability_digest": capability["capability_digest"], "assimilation_binding_digest": assimilation["binding_digest"]}
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    next_stake = assimilation["next_stake"]
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["developmental_extension_reuse_capabilities"] = [*child.get("developmental_extension_reuse_capabilities", []), capability]
    child["developmental_extension_reuse_receipts"] = [*child.get("developmental_extension_reuse_receipts", []), receipt]
    child["active_developmental_stake"] = next_stake
    opening = "Open actor-stake-" + next_stake["stake_id"] + ": " + next_stake["question"]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening}
    child["continuation"] = {**child["continuation"], "next_opening": opening, "status": "open"}
    child["unresolved"] = next_stake["question"]
    return p82.seal(child), receipt


def preflight(p82, parent: dict[str, Any]) -> dict[str, Any]:
    stake = parent["active_developmental_stake"]
    route = previous.extended_route(p82, parent, stake)
    extension = parent["developmental_property_extensions"][0]
    operation = previous.load_operation(extension["operation_source"])
    public = previous.evaluate(operation, PUBLIC_CASES)
    hidden = previous.evaluate(operation, HIDDEN_CASES)
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open",
        "one_exact_extension": len(parent.get("developmental_property_extensions", [])) == 1 and extension["property"]["property"] == stake["property"],
        "retained_source_loads": operation is not None,
        "extension_routes_exactly": bool(route and route["extension_binding_digest"] == extension["binding_digest"]),
        "new_public_fixture_passes": public["passed"] and public["pass_count"] == 3,
        "new_hidden_fixture_passes": hidden["passed"] and hidden["pass_count"] == 3,
        "assimilation_schema_present": ASSIMILATION_SCHEMA.is_file(),
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "route": route, "public_fixture": public, "hidden_fixture": hidden}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0154").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_artifact(p82, repo, store, "OT-0153", "open-subject-with-admitted-developmental-extension.json")
    fixtures = preflight(p82, parent)
    fixtures["checks"]["parent_identity"] = runtime.identity_conforms(parent)
    fixtures["checks"]["passed"] = all(value for key, value in fixtures["checks"].items() if key != "passed")
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0154 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    route = fixtures["route"]
    extension = parent["developmental_property_extensions"][0]
    public = previous.evaluate(previous.load_operation(extension["operation_source"]), PUBLIC_CASES)
    binding = bind_reuse(p82, parent, route, public)
    (run / "bound-exact-extension-reuse.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    world = hidden_world(p82, parent, binding)
    (run / "sealed-hidden-reuse-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    assimilation_root = run / "reuse-assimilation"
    assimilation_root.mkdir()
    assimilation = run_assimilator(context, p82, assimilation_root, parent, route, binding, world) if world["result"]["passed"] else None
    final = parent
    transition = None
    if assimilation and assimilation["binding"]:
        final, transition = seal_successor(p82, parent, route, binding, world, assimilation["binding"])
    erased = copy.deepcopy(parent)
    erased["developmental_property_extensions"] = []
    erased_route = previous.extended_route(p82, erased, parent["active_developmental_stake"])
    closed_binding = {"stake": parent["active_developmental_stake"], "binding_digest": "control"}
    closed_route = worlds.compile_route(p82, parent, closed_binding, worlds.catalog(p82))
    next_route = route_any(p82, final, final["active_developmental_stake"])
    controls = {"extension_erased_route": erased_route, "closed_catalog_route": closed_route, "successor_next_route": next_route}
    (run / "post-seal-route-controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True) + "\n")
    source_sha = hashlib.sha256(extension["operation_source"].encode()).hexdigest()
    checks = {
        "exact_retained_package_reused": binding["extension_binding_digest"] == extension["binding_digest"] and binding["operation_source_sha256"] == source_sha,
        "public_reuse_passes": public["passed"] and public["pass_count"] == 3,
        "hidden_reuse_passes": world["result"]["passed"] and world["result"]["pass_count"] == 3,
        "one_fresh_accepted_assimilator": bool(assimilation and assimilation["binding"] and prior131.audit_accepted(assimilation["audit"])),
        "different_next_stake_routes": bool(assimilation and assimilation["stake"]["property"] != parent["active_developmental_stake"]["property"] and next_route),
        "extension_erasure_blocks_route": erased_route is None,
        "closed_catalog_cannot_route_extension": closed_route is None,
        "parent_retained_exactly": all(final.get(key) == parent.get(key) for key in parent if key != "artifact_digest" and key not in {"active_developmental_stake", "active_pursuit", "continuation", "unresolved"}),
        "reuse_capability_installed": bool(final.get("developmental_extension_reuse_capabilities") and final.get("developmental_extension_reuse_receipts")),
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0154-exact-developmental-extension-reuse", "source_subject_digest": parent["artifact_digest"], "route": route, "reuse_binding": binding, "public_reuse": public, "hidden_world": world, "assimilation": p82.compact(assimilation) if assimilation else None, "transition_receipt": transition, "controls": controls, "checks": checks, "exact_extension_reuse_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 1 if assimilation else 0, "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
