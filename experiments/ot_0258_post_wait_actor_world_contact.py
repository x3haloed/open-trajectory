from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0257_provider_extension_wakes_waiting_subject.py"
BASE_SHA256 = "c443ece73ab730f49cd9fa419c956df92ce93febce6ba3cf039d3cf8d572f913"
PARENT_DIGEST = "f818c68ef8a77503af38b4f89483edaf419dabb3a22878eb10c51eab4abd136a"
OT257_RECEIPT = "80df5a664818470daf4576a6bfd03f9f23d5951ea722e5b1e4d0408ebca9a585"
AUTHORITY = "ot-0258-post-wait-actor-world-contact"
PULSE = None
ABI = "case-object-to-ordered-identifier-list-v1"
SCHEMA = REPO / "spec/ot-0242-environment-expansion.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0257 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0258_frozen_ot0257", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base257 = load_base()
base256 = base257.base256
base248 = base257.base248
base247 = base257.base247
base236 = base247.base236
base242 = base247.base242
authority_base = base257.authority_base
WORLD_ID = base257.WORLD_ID
WORLD_SOURCES = base257.WORLD_SOURCES
PREDICATES = base242.PREDICATES
CONTACT_CORE = base242.CONTACT_CORE

REFERENCE_HEAD = '''def _best(items, capacity, value):
    candidates = []
    for mask in __import__("itertools").product((0, 1), repeat=len(items)):
        selected = [item for item, take in zip(items, mask) if take]
        if sum(item["effort"] for item in selected) > capacity:
            continue
        score = sum(value(item) for item in selected)
        identities = tuple(sorted(item["id"] for item in selected))
        candidates.append((score, len(selected), tuple(reversed(identities)), identities))
    return list(max(candidates)[-1])
'''

CANDIDATES = {
    "assign_relay_windows": (
        "coordination/radio.py",
        "windows",
        "urgency",
        "outage_hours",
        "dependency_risk",
    ),
    "sequence_repair_crews": (
        "coordination/crews.py",
        "repairs",
        "people_blocked",
        "delay_hours",
        "cascade_risk",
    ),
    "route_supply_convoys": (
        "coordination/supplies.py",
        "routes",
        "households",
        "delay_hours",
        "access_risk",
    ),
}

REFERENCE_SOURCES = {
    "coordination/radio.py": REFERENCE_HEAD
    + '''
def assign_relay_windows(case):
    return _best(case["windows"], case["capacity"], lambda row: row["urgency"] * row["outage_hours"] * row["dependency_risk"])
''',
    "coordination/crews.py": REFERENCE_HEAD
    + '''
def sequence_repair_crews(case):
    return _best(case["repairs"], case["capacity"], lambda row: row["people_blocked"] * row["delay_hours"] * row["cascade_risk"])
''',
    "coordination/supplies.py": REFERENCE_HEAD
    + '''
def route_supply_convoys(case):
    return _best(case["routes"], case["capacity"], lambda row: row["households"] * row["delay_hours"] * row["access_risk"])
''',
}

CHECKER = base247.CHECKER.replace('p.parts[0]=="resilience"', 'p.parts[0]=="coordination"')


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(
        name + hashlib.sha256(path.read_bytes()).hexdigest()[:10], path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_world(root, reference=False):
    for relative, source in WORLD_SOURCES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        (path.parent / "__init__.py").write_text("")
    if reference:
        for relative, source in REFERENCE_SOURCES.items():
            path = root / "sealed-reference" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)


def hidden_cases(target):
    _, collection, magnitude, duration, risk = CANDIDATES[target]
    values = [
        (3, [(10, 1, 0.2, 3), (6, 8, 0.9, 3)]),
        (4, [(10, 1, 0.2, 4), (7, 7, 0.8, 2), (6, 6, 0.9, 2)]),
        (5, [(10, 1, 0.2, 5), (8, 6, 0.8, 3), (7, 5, 0.9, 2)]),
        (2, [(8, 8, 0.8, 2), (10, 1, 0.2, 2)]),
        (4, [(9, 5, 0.9, 2), (5, 2, 0.5, 2)]),
        (4, [(8, 4, 0.8, 2), (7, 3, 0.7, 2)]),
    ]
    rows = []
    for index, (capacity, items) in enumerate(values, 1):
        rows.append(
            {
                "case_id": f"sealed-{target}-{index}",
                "input": {
                    "capacity": capacity,
                    collection: [
                        {
                            "id": chr(103 + item_index),
                            magnitude: size,
                            duration: span,
                            risk: probability,
                            "effort": effort,
                        }
                        for item_index, (size, span, probability, effort) in enumerate(items)
                    ],
                },
            }
        )
    return rows


HIDDEN_CASES = {target: hidden_cases(target) for target in CANDIDATES}


def fixture_decision(target):
    path, collection, magnitude, duration, risk = CANDIDATES[target]
    cases = []
    for index in range(4):
        cases.append(
            {
                "case_id": f"fixture-{index}",
                "input": {
                    "capacity": 2 + index,
                    collection: [
                        {
                            "id": "a",
                            magnitude: 2 + index,
                            duration: 1 + index,
                            risk: 0.2 + index / 10,
                            "effort": 1,
                        },
                        {
                            "id": "b",
                            magnitude: 1,
                            duration: 3,
                            risk: 0.8,
                            "effort": 2,
                        },
                    ],
                },
            }
        )
    return {
        "environment_id": WORLD_ID,
        "region_rationale": "This offered world exposes an executable coordination boundary.",
        "next_pursuit": "Test whether magnitude-only coordination survives independent consequence.",
        "next_contact": {
            "contact_id": f"fixture-{target}",
            "target_path": path,
            "target_symbol": target,
            "abi": ABI,
            "stake": "Determine whether the inherited local rule preserves the best feasible coordination set.",
            "cases": cases,
            "predicates": copy.deepcopy(PREDICATES),
        },
    }


def template():
    return {
        "environment_id": "replace-environment",
        "region_rationale": "replace-rationale",
        "next_pursuit": "replace-pursuit",
        "next_contact": {
            "contact_id": "replace-contact",
            "target_path": "replace-path",
            "target_symbol": "replace-target",
            "abi": ABI,
            "stake": "replace-stake",
            "cases": [],
            "predicates": copy.deepcopy(PREDICATES),
        },
    }


def structural(decision, root, ledger):
    if (
        not isinstance(decision, dict)
        or set(decision)
        != {"environment_id", "region_rationale", "next_pursuit", "next_contact"}
        or not all(
            isinstance(decision.get(key), str)
            and decision[key].strip()
            and not decision[key].startswith("replace-")
            for key in ("environment_id", "region_rationale", "next_pursuit")
        )
    ):
        return False
    contact = decision["next_contact"]
    if not isinstance(contact, dict) or set(contact) != CONTACT_CORE:
        return False
    if not all(
        isinstance(contact.get(key), str)
        and contact[key].strip()
        and not contact[key].startswith("replace-")
        for key in ("contact_id", "target_path", "target_symbol", "abi", "stake")
    ):
        return False
    path = Path(contact["target_path"])
    cases = contact.get("cases")
    if (
        path.is_absolute()
        or ".." in path.parts
        or len(path.parts) != 2
        or path.parts[0] != "coordination"
        or path.suffix != ".py"
        or contact["target_symbol"].startswith("_")
        or contact["target_symbol"] in ledger["targets"]
        or contact["predicates"] != PREDICATES
        or not isinstance(cases, list)
        or len(cases) != 4
        or len({row.get("case_id") for row in cases if isinstance(row, dict)}) != 4
        or not all(
            isinstance(row, dict)
            and set(row) == {"case_id", "input"}
            and isinstance(row["input"], dict)
            for row in cases
        )
    ):
        return False
    try:
        fn = getattr(load_module(root / path, "structural_"), contact["target_symbol"])
    except (OSError, AttributeError):
        return False
    return callable(fn)


def execute_public(root, decision):
    contact = decision["next_contact"]
    fn = getattr(
        load_module(root / contact["target_path"], "public_"),
        contact["target_symbol"],
    )
    rows = []
    for case in contact["cases"]:
        try:
            observed = fn(copy.deepcopy(case["input"]))
            json.dumps(observed)
            rows.append({"case_id": case["case_id"], "valid": True, "observed": observed})
        except Exception as error:
            rows.append(
                {
                    "case_id": case.get("case_id"),
                    "valid": False,
                    "error_type": type(error).__name__,
                }
            )
    return {
        "case_count": len(rows),
        "all_valid": len(rows) == 4 and all(row["valid"] for row in rows),
        "rows": rows,
    }


def execute_hidden(root, target):
    relative = CANDIDATES[target][0]
    installed = getattr(load_module(root / relative, "installed_"), target)
    reference = getattr(
        load_module(root / "sealed-reference" / relative, "reference_"), target
    )
    rows = []
    for case in HIDDEN_CASES[target]:
        try:
            observed = installed(copy.deepcopy(case["input"]))
            expected = reference(copy.deepcopy(case["input"]))
            rows.append(
                {
                    "case_id": case["case_id"],
                    "valid": True,
                    "observed": observed,
                    "expected": expected,
                    "matches": observed == expected,
                }
            )
        except Exception as error:
            rows.append(
                {
                    "case_id": case["case_id"],
                    "valid": False,
                    "matches": False,
                    "error_type": type(error).__name__,
                }
            )
    return {
        "case_count": len(rows),
        "all_valid": all(row["valid"] for row in rows),
        "matches": sum(row["matches"] for row in rows),
        "rows": rows,
    }


def seed_actor(root, subject, decision):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_world(seed)
    write_json(seed / "exact-subject.json", subject)
    write_json(seed / "streamed-world-offer.json", subject["active_streamed_world_offer"])
    write_json(seed / "local-frontier-ledger.json", subject["local_frontier_ledger"])
    write_json(
        seed / "expansion-contract.json",
        {
            "authority": AUTHORITY,
            "contact_fields": sorted(CONTACT_CORE),
            "predicates": PREDICATES,
        },
    )
    write_json(seed / "environment-expansion.json", decision)
    (seed / "check_expansion.py").write_text(CHECKER)
    immutable = [
        "exact-subject.json",
        "streamed-world-offer.json",
        "local-frontier-ledger.json",
        "expansion-contract.json",
        "check_expansion.py",
        "coordination/__init__.py",
        *sorted(WORLD_SOURCES),
        "mutation-envelope.json",
        "README.md",
    ]
    write_json(
        seed / "mutation-envelope.json",
        {"editable": ["environment-expansion.json"], "immutable": immutable},
    )
    (seed / "README.md").write_text(
        "Continue from the exact open subject under a content-free environment-expansion pulse. "
        "The retained streamed-world offer is now available. Inspect its executable sources and "
        "choose one coherent bounded contact. No task or target is assigned; do not invent contact "
        "merely to avoid stopping. Edit only environment-expansion.json, run python3 "
        "check_expansion.py, and inspect the exact diff. Hidden consequence is unavailable.\n"
    )
    return seed


def output_valid(output):
    return (
        isinstance(output, dict)
        and set(output) == {"action", "files_changed", "selected_target"}
        and output.get("action") == "expand-environment"
        and output.get("files_changed") == ["environment-expansion.json"]
        and isinstance(output.get("selected_target"), str)
        and bool(output["selected_target"].strip())
    )


def run_actor(context, p82, root, subject):
    seed = seed_actor(root, subject, template())
    label = "post-wait-expansion-actor"
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, SCHEMA, (seed / "README.md").read_text().strip()
    )
    try:
        decision = json.loads((workspace / "environment-expansion.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())[
            "immutable"
        ]
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in immutable
        )
        structural_ok = structural(decision, workspace, subject["local_frontier_ledger"])
        contact = decision["next_contact"] if structural_ok else None
        target = contact["target_symbol"] if contact else None
        candidate = CANDIDATES.get(target) if target else None
        semantic = bool(
            immutable_ok and candidate and candidate[0] == contact["target_path"]
        )
        public = execute_public(workspace, decision) if semantic else None
        semantic = bool(semantic and public and public["all_valid"])
    except (OSError, json.JSONDecodeError, KeyError):
        decision, public, target, semantic = None, None, None, False
    transport = output_valid(output)
    audit = context.audit_actor(
        label,
        output,
        base_audit,
        semantic and transport,
        ["environment-expansion.json"],
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(semantic and transport and base236.g10(normalized))
    binding = None
    if accepted:
        contact = decision["next_contact"]
        body = {
            "authority": AUTHORITY + "-binding",
            "source_subject_digest": subject["artifact_digest"],
            "pulse_content": PULSE,
            "derived_operation": "expand-environment",
            "world_id": WORLD_ID,
            "world_offer_receipt_digest": subject["active_streamed_world_offer"][
                "offer_receipt_digest"
            ],
            "actor_patch_digest": audit["patch_digest"],
            "decision": decision,
            "contact_identity": p82.digest(
                {
                    "target_path": contact["target_path"],
                    "target_symbol": contact["target_symbol"],
                    "abi": contact["abi"],
                    "cases": contact["cases"],
                    "predicates": contact["predicates"],
                }
            ),
            "public_result": public,
            "denial_provenance": normalized["provenance"],
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-post-wait-expansion.json", binding)
    return {
        "accepted": binding is not None,
        "binding": binding,
        "decision": decision,
        "public": public,
        "audit": audit,
        "g10_disposition": accepted,
        "output": output,
    }


def compile_intermediate(subject, action, pulse, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    decision = action["decision"]
    contact = copy.deepcopy(decision["next_contact"])
    target = contact["target_symbol"]
    path = contact["target_path"]
    offer = subject["active_streamed_world_offer"]
    consumption_body = {
        "authority": AUTHORITY + "-offer-consumption",
        "source_subject_digest": subject["artifact_digest"],
        "offer_receipt_digest": offer["offer_receipt_digest"],
        "binding_digest": action["binding"]["binding_digest"],
        "world_id": WORLD_ID,
        "outcome": "actor-contact-bound",
    }
    consumption = {**consumption_body, "receipt_digest": p82.digest(consumption_body)}
    child["streamed_world_offer_consumption_receipts"] = [
        *child.get("streamed_world_offer_consumption_receipts", []),
        consumption,
    ]
    child["active_streamed_world_offer"] = None
    provider_body = {
        "authority": AUTHORITY + "-world-stream-consumption",
        "source_subject_digest": subject["artifact_digest"],
        "pulse_digest": pulse["pulse_digest"],
        "world_id": WORLD_ID,
        "offer_receipt_digest": offer["offer_receipt_digest"],
        "visible_world_digest": p82.digest(WORLD_SOURCES),
    }
    provider = {**provider_body, "receipt_digest": p82.digest(provider_body)}
    child["environment_stream_receipts"] = [
        *child.get("environment_stream_receipts", []),
        provider,
    ]
    epoch_row = {
        "authority": AUTHORITY + "-environment-epoch",
        "source_subject_digest": subject["artifact_digest"],
        "provider_receipt_digest": provider["receipt_digest"],
        "offer_consumption_receipt_digest": consumption["receipt_digest"],
        "binding_digest": action["binding"]["binding_digest"],
        "environment_id": WORLD_ID,
        "region_rationale": decision["region_rationale"],
        "selected_path": path,
        "selected_target": target,
        "visible_sources": copy.deepcopy(offer["visible_sources"]),
        "status": "actor-authored-contact-bound-after-wait",
    }
    child["actor_authored_environment_epochs"] = [
        *child["actor_authored_environment_epochs"],
        epoch_row,
    ]
    extension = {
        "authority": AUTHORITY + "-extension",
        "source_subject_digest": subject["artifact_digest"],
        "binding_digest": action["binding"]["binding_digest"],
        "environment_id": WORLD_ID,
        "target_path": path,
        "target_symbol": target,
        "abi": contact["abi"],
        "installed_source": WORLD_SOURCES[path],
        "installed_source_digest": p82.digest(WORLD_SOURCES[path]),
        "status": "bound-in-post-wait-streamed-world",
    }
    child["actor_authored_environment_extensions"] = [
        *child["actor_authored_environment_extensions"],
        extension,
    ]
    child["subject_originated_world_stakes"] = [
        *child.get("subject_originated_world_stakes", []),
        action["binding"],
    ]
    pending = {
        "authority": AUTHORITY + "-pending-contact",
        "binding_digest": action["binding"]["binding_digest"],
        "contact_identity": action["binding"]["contact_identity"],
        "package": contact,
        "package_digest": p82.digest(contact),
        "consequence_status": "unreceipted",
    }
    child["pending_contact_bearing_continuations"] = [
        *child["pending_contact_bearing_continuations"],
        pending,
    ]
    ledger = copy.deepcopy(child["local_frontier_ledger"])
    ledger["targets"][target] = {
        "status": "verification-due",
        "admitted_capability_receipts": [],
        "correction_receipts": [],
        "independent_success_receipts": [],
        "latest_world_receipt_digest": None,
        "latest_world_outcome": None,
        "origin": "post-wait-streamed-world-selection",
    }
    child["local_frontier_ledger"] = ledger
    state = copy.deepcopy(child["fixed_g6_recurrence_driver"])
    state.update(
        phase="contact",
        last_target=target,
        accepted_actors=state["accepted_actors"] + 1,
    )
    child["fixed_g6_recurrence_driver"] = state
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": decision["next_pursuit"],
    }
    child["continuation_liveness"] = {
        "authority": AUTHORITY,
        "status": "live-post-wait-world-contact",
        "contact_identity": pending["contact_identity"],
        "binding_digest": pending["binding_digest"],
        "target_status": "verification-due",
    }
    child["unresolved"] = "Expose the post-wait actor-selected contact to independent consequence."
    return p82.seal(child)


def sealed_world(intermediate, action, p82, root):
    target = action["decision"]["next_contact"]["target_symbol"]
    write_world(root, True)
    observed = execute_hidden(root, target)
    outcome = (
        "success"
        if observed["matches"] >= 4
        else ("surrender" if observed["matches"] == 0 else "unresolved")
    )
    path = CANDIDATES[target][0]
    body = {
        "authority": AUTHORITY + "-sealed-world",
        "source_subject_digest": intermediate["artifact_digest"],
        "contact_binding_digest": action["binding"]["binding_digest"],
        "contact_identity": action["binding"]["contact_identity"],
        "world_id": WORLD_ID,
        "target_path": path,
        "target_symbol": target,
        "hidden_cases_digest": p82.digest(HIDDEN_CASES[target]),
        "reference_source_digest": p82.digest(REFERENCE_SOURCES[path]),
        "result": observed,
        "outcome": outcome,
    }
    return {**body, "receipt_digest": p82.digest(body)}


def compile_world(subject, world, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    pending = copy.deepcopy(child["pending_contact_bearing_continuations"])
    pending[-1] = {
        **pending[-1],
        "consequence_status": world["outcome"],
        "world_receipt_digest": world["receipt_digest"],
    }
    child["pending_contact_bearing_continuations"] = pending
    child["cross_epoch_world_receipts"] = [
        *child.get("cross_epoch_world_receipts", []),
        world,
    ]
    target = world["target_symbol"]
    ledger = copy.deepcopy(child["local_frontier_ledger"])
    ledger["targets"][target].update(
        status="unresolved",
        latest_world_receipt_digest=world["receipt_digest"],
        latest_world_outcome=world["outcome"],
    )
    child["local_frontier_ledger"] = ledger
    state = copy.deepcopy(child["fixed_g6_recurrence_driver"])
    state["phase"] = "correct"
    state["encounters"] += 1
    state["history"] = [
        *state["history"],
        {
            "encounter": state["encounters"],
            "target": target,
            "outcome": world["outcome"],
            "receipt_digest": world["receipt_digest"],
        },
    ]
    child["fixed_g6_recurrence_driver"] = state
    child["continuation_liveness"] = {
        "authority": AUTHORITY,
        "status": "unresolved-post-wait-world-contact",
        "contact_identity": world["contact_identity"],
        "world_receipt_digest": world["receipt_digest"],
        "target_status": "unresolved",
    }
    child["unresolved"] = "Correct the post-wait actor-selected contact from receipted contradiction."
    return p82.seal(child)


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0258").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0257", "open-subject-with-resumed-world-offer.json"
    )
    result257 = selector_base.load_artifact(
        p82, repo, store, "OT-0257", "provider-extension-wake-aggregate.json"
    )
    fixture = run.parent / "OT-0258-preflight"
    shutil.rmtree(fixture, ignore_errors=True)
    fixture.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": parent["artifact_digest"],
        "derived_operation": "expand-environment",
        "offer_receipt_digest": parent["active_streamed_world_offer"][
            "offer_receipt_digest"
        ],
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    rows, hidden, prospective = {}, {}, {}
    for target in sorted(CANDIDATES):
        decision = fixture_decision(target)
        seed = seed_actor(fixture / target, parent, decision)
        checker = subprocess.run(
            ["python3", "check_expansion.py"], cwd=seed, capture_output=True
        )
        structural_ok = structural(decision, seed, parent["local_frontier_ledger"])
        public = execute_public(seed, decision) if structural_ok else None
        action = {
            "decision": decision,
            "binding": {"binding_digest": "a" * 64, "contact_identity": "b" * 64},
        }
        intermediate = compile_intermediate(parent, action, pulse, p82)
        world = sealed_world(intermediate, action, p82, fixture / f"world-{target}")
        final = compile_world(intermediate, world, p82)
        rows[target] = {
            "checker": checker.returncode == 0,
            "structural": structural_ok,
            "public": bool(public and public["all_valid"]),
        }
        hidden[target] = world["result"]
        prospective[target] = runtime.identity_conforms(
            intermediate
        ) and runtime.identity_conforms(final)
    prompt_seed = seed_actor(fixture / "prompt", parent, template())
    prompt = (prompt_seed / "README.md").read_text()
    route = (
        base248.base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(
            parent["active_executable_routing_selector"]["route"],
            parent["actor_authored_contact_mechanisms"][-1]["expression"],
        )
    )
    identity = authority_base.reuse.extension_base.evaluate(
        authority_base.reuse.extension_base.load_operation(
            parent["developmental_property_extensions"][0]["operation_source"]
        ),
        authority_base.reuse.accumulated_floor(),
    )
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
        == BASE_SHA256,
        "parent_exact_open_offer": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and parent["continuation_liveness"]["status"]
        == "world-stream-extension-available"
        and parent["active_streamed_world_offer"]["world_id"] == WORLD_ID
        and runtime.identity_conforms(parent),
        "ot0257_exact_promotion": result257["observer_disposition"] == "promoted"
        and result257["receipt_digest"] == OT257_RECEIPT
        and result257["final_subject_digest"] == PARENT_DIGEST,
        "null_pulse_uses_retained_offer": PULSE is None
        and pulse["offer_receipt_digest"]
        == parent["active_streamed_world_offer"]["offer_receipt_digest"],
        "three_candidates_three_modules": len(CANDIDATES) == 3
        and len(WORLD_SOURCES) == 3,
        "prompt_names_no_candidate_or_module": not any(
            name in prompt for name in [*CANDIDATES, *WORLD_SOURCES]
        ),
        "all_checkers_structural_public": all(
            row["checker"] and row["structural"] and row["public"]
            for row in rows.values()
        ),
        "all_hidden_2_of_6": all(
            row["all_valid"] and row["matches"] == 2 for row in hidden.values()
        ),
        "all_prospective_states_conform": all(prospective.values()),
        "template_rejected": not structural(
            template(), prompt_seed, parent["local_frontier_ledger"]
        ),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "rows": rows,
        "hidden": hidden,
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0258 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not checks["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
        base.typed.base.make_context(runtime, run, repo)
    )
    action = run_actor(context, p82, run / "expansion", parent)
    intermediate = (
        compile_intermediate(parent, action, pulse, p82) if action["accepted"] else parent
    )
    world = None
    final = intermediate
    if action["accepted"] and runtime.identity_conforms(intermediate):
        world = sealed_world(intermediate, action, p82, run / "world")
        write_json(run / "hidden-world-receipt.json", world)
        final = compile_world(intermediate, world, p82)
    target = (
        action["decision"]["next_contact"]["target_symbol"]
        if action["accepted"]
        else None
    )
    gates = {
        "preflight_passed": checks["passed"],
        "one_content_free_post_wait_pulse": pulse["content"] is None,
        "one_fresh_actor": True,
        "fresh_actor_accepted": action["accepted"],
        "selected_real_offered_candidate": target in CANDIDATES if target else False,
        "g10_accepted": action["g10_disposition"],
        "public_executable": bool(action["public"] and action["public"]["all_valid"]),
        "offer_consumed_after_acceptance": bool(
            action["accepted"]
            and intermediate["active_streamed_world_offer"] is None
            and intermediate["streamed_world_offer_consumption_receipts"][-1][
                "offer_receipt_digest"
            ]
            == parent["active_streamed_world_offer"]["offer_receipt_digest"]
        ),
        "wait_history_preserved": bool(
            action["accepted"]
            and intermediate["world_stream_wait_receipts"]
            == parent["world_stream_wait_receipts"]
            and intermediate["world_stream_wait_discharge_receipts"]
            == parent["world_stream_wait_discharge_receipts"]
        ),
        "new_epoch_bound_from_offer": bool(
            action["accepted"]
            and intermediate["actor_authored_environment_epochs"][-1][
                "environment_id"
            ]
            == WORLD_ID
            and intermediate["actor_authored_environment_epochs"][:-1]
            == parent["actor_authored_environment_epochs"]
        ),
        "independent_world_2_of_6": bool(
            world
            and world["result"]["all_valid"]
            and world["result"]["matches"] == 2
        ),
        "new_target_unresolved": bool(
            world and final["local_frontier_ledger"]["targets"][target]["status"] == "unresolved"
        ),
        "final_open_correct": final["continuation"]["status"] == "open"
        and final["fixed_g6_recurrence_driver"]["phase"] == "correct"
        and runtime.identity_conforms(final),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "pulse": pulse,
        "expansion": action,
        "world": world,
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
