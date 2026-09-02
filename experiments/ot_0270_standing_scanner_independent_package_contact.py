from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0269_dormant_feed_fourth_epoch_to_wait.py"
BASE_SHA256 = "76056c34f9fb0381650f1a28a0bbaf8edc26f418949958793ab20fe5f77769f9"
PARENT_DIGEST = "67fafa0734fb3ab9a06c56a767e0b15c004d008c9f7b2a980889650c2accf0c2"
OT269_RECEIPT = "9139f826f32251859894c5f3a098efce9508148e3549a3ebea70bedfc1f8de9a"
OT268_RECEIPT = "7026047afea9989082ac529770c934b3c63512ebc2de03d6c7d715d74c1743d1"
AUTHORITY = "ot-0270-standing-scanner-independent-package-contact"
PULSE = None
EXPECTED = ("wait-provider", "expand-environment")
ABI = "case-object-to-json-value-v1"
SCHEMA = REPO / "spec/ot-0242-environment-expansion.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0269 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0270_frozen_ot0269", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base269 = load_base()
base268 = base269.base268
base267 = base269.base267
base265 = base269.base265
base261 = base269.base261
base260 = base269.base260
base244 = base269.base244
base242 = base269.base245.base242
base236 = base268.base236
authority_base = base269.authority_base
PREDICATES = base242.PREDICATES
CONTACT_CORE = base242.CONTACT_CORE


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def setup(args):
    lineage = authority_base.guide_base.load_base()
    selector_base, base, base130 = lineage.selector_base, lineage.base, lineage.base130
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0270").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0269", "open-subject-at-third-standing-feed-wait.json"
    )
    result269 = selector_base.load_artifact(
        p82, repo, store, "OT-0269", "dormant-feed-fourth-epoch-to-wait-aggregate.json"
    )
    package = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-three-lantern-world-package.json"
    )
    result268 = selector_base.load_artifact(
        p82, repo, store, "OT-0268", "independent-world-package-aggregate.json"
    )
    return repo, run, p82, runtime, parent, result269, package, result268, base, base130


def public_package(package):
    return {
        "world_id": package["world_id"],
        "visible_sources": copy.deepcopy(package["visible_sources"]),
    }


def scan(subject, package, p82):
    return base267.scan_feed(subject, [public_package(package)], p82.digest)


def wait_satisfied(subject, observation):
    wait = subject.get("active_world_stream_wait")
    available = observation.get("available_world")
    return bool(
        isinstance(wait, dict)
        and wait.get("status") == "waiting"
        and wait.get("resume_condition") == "unseen-world-available"
        and observation.get("status") == "world-available"
        and isinstance(available, dict)
        and available.get("world_id") not in observation.get("seen_world_ids", [])
        and observation.get("cursor_digest") != wait.get("provider_cursor_digest")
    )


def compile_offer(subject, observation, p82):
    available = observation.get("available_world")
    existing = subject.get("active_streamed_world_offer")
    if (
        isinstance(existing, dict)
        and isinstance(available, dict)
        and existing.get("world_id") == available.get("world_id")
        and existing.get("package_digest") == available.get("package_digest")
    ):
        return subject, True
    if isinstance(existing, dict) and observation.get("status") == "empty":
        return subject, True
    if not wait_satisfied(subject, observation):
        return subject, False
    wait = subject["active_world_stream_wait"]
    raw_public = {
        "world_id": available["world_id"],
        "visible_sources": {
            relative: row["source"]
            for relative, row in available["visible_sources"].items()
        },
    }
    observation_body = {
        "authority": AUTHORITY + "-standing-scanner-observation",
        "source_subject_digest": subject["artifact_digest"],
        "standing_provider_transition_receipt_digest": subject[
            "active_standing_world_provider"
        ]["transition_receipt_digest"],
        "scanner_observation_receipt_digest": observation["receipt_digest"],
        "cursor_digest": observation["cursor_digest"],
        "world_id": available["world_id"],
        "package_digest": available["package_digest"],
        "public_package_digest": p82.digest(raw_public),
        "outcome": "unseen-world-available",
    }
    observation_receipt = {
        **observation_body,
        "receipt_digest": p82.digest(observation_body),
    }
    discharge_body = {
        "authority": AUTHORITY + "-wait-discharge",
        "source_subject_digest": subject["artifact_digest"],
        "wait_handle_digest": wait["wait_handle_digest"],
        "resume_condition": wait["resume_condition"],
        "scanner_observation_receipt_digest": observation["receipt_digest"],
        "available_world_id": available["world_id"],
        "outcome": "satisfied",
    }
    discharge = {**discharge_body, "receipt_digest": p82.digest(discharge_body)}
    offer_body = {
        "authority": AUTHORITY + "-visible-world-offer",
        "source_subject_digest": subject["artifact_digest"],
        "scanner_observation_receipt_digest": observation["receipt_digest"],
        "wait_discharge_receipt_digest": discharge["receipt_digest"],
        "world_id": available["world_id"],
        "package_digest": available["package_digest"],
        "public_package_digest": p82.digest(raw_public),
        "visible_sources": copy.deepcopy(available["visible_sources"]),
        "selection_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
        "actor_authority": False,
    }
    offer = {**offer_body, "offer_receipt_digest": p82.digest(offer_body)}
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    child["standing_world_feed_observation_receipts"] = [
        *child.get("standing_world_feed_observation_receipts", []),
        observation_receipt,
    ]
    child["world_stream_wait_discharge_receipts"] = [
        *child.get("world_stream_wait_discharge_receipts", []),
        discharge,
    ]
    child["active_world_stream_wait"] = None
    child["streamed_world_offer_receipts"] = [
        *child.get("streamed_world_offer_receipts", []),
        offer,
    ]
    child["active_streamed_world_offer"] = offer
    child["continuation"] = {
        **child["continuation"],
        "status": "open",
        "next_opening": "Inspect the newly visible world and choose one coherent bounded contact.",
    }
    child["continuation_liveness"] = {
        "authority": AUTHORITY,
        "status": "standing-feed-world-available",
        "wait_discharge_receipt_digest": discharge["receipt_digest"],
        "offer_receipt_digest": offer["offer_receipt_digest"],
        "resume_operation": "expand-environment",
    }
    child["unresolved"] = "Resume environment expansion from the standing-feed offer."
    return p82.seal(child), False


def derive(subject, p82):
    wait = subject.get("active_world_stream_wait")
    if isinstance(wait, dict) and wait.get("status") == "waiting":
        return "wait-provider"
    if isinstance(subject.get("active_streamed_world_offer"), dict):
        return "expand-environment"
    return base261.challenger(subject, p82)


def write_visible_world(root, offer):
    for relative, row in offer["visible_sources"].items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["source"])
        (path.parent / "__init__.py").write_text("")


def load_public_callable(root, relative, target):
    path = root / relative
    spec = importlib.util.spec_from_file_location(
        "ot0270_public_" + hashlib.sha256(path.read_bytes()).hexdigest()[:12], path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, target)


def template():
    return {
        "environment_id": "replace-environment",
        "region_rationale": "replace-rationale",
        "next_pursuit": "replace-pursuit",
        "next_contact": {
            "contact_id": "replace-contact",
            "target_path": "replace/path.py",
            "target_symbol": "replace-target",
            "abi": ABI,
            "stake": "replace-stake",
            "cases": [],
            "predicates": copy.deepcopy(PREDICATES),
        },
    }


def offered_pairs(subject):
    offer = subject.get("active_streamed_world_offer", {})
    return {
        (relative, target)
        for relative, row in offer.get("visible_sources", {}).items()
        for target in row.get("top_level_callables", [])
    }


def structural(decision, root, subject):
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
    contact = decision.get("next_contact")
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
    pair = (contact["target_path"], contact["target_symbol"])
    cases = contact.get("cases")
    if (
        path.is_absolute()
        or ".." in path.parts
        or len(path.parts) != 2
        or path.suffix != ".py"
        or contact["target_symbol"].startswith("_")
        or pair not in offered_pairs(subject)
        or contact["target_symbol"] in subject["local_frontier_ledger"]["targets"]
        or contact["predicates"] != PREDICATES
        or contact["abi"] != ABI
        or not isinstance(cases, list)
        or len(cases) != 4
        or len(
            {
                row.get("case_id")
                for row in cases
                if isinstance(row, dict)
                and isinstance(row.get("case_id"), str)
                and row["case_id"].strip()
            }
        )
        != 4
        or not all(
            isinstance(row, dict)
            and set(row) == {"case_id", "input"}
            and isinstance(row.get("input"), dict)
            for row in cases
        )
    ):
        return False
    try:
        return callable(load_public_callable(root, contact["target_path"], contact["target_symbol"]))
    except (OSError, AttributeError, SyntaxError):
        return False


def execute_public(root, decision):
    contact = decision["next_contact"]
    fn = load_public_callable(root, contact["target_path"], contact["target_symbol"])
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


CHECKER_SOURCE = (
    "import copy, hashlib, importlib.util, json\nfrom pathlib import Path\n"
    + "ABI = "
    + repr(ABI)
    + "\nPREDICATES = "
    + repr(PREDICATES)
    + "\nCONTACT_CORE = "
    + repr(CONTACT_CORE)
    + "\n"
    + inspect.getsource(load_public_callable)
    + inspect.getsource(offered_pairs)
    + inspect.getsource(structural)
    + inspect.getsource(execute_public)
    + '''
subject = json.loads(Path("exact-subject.json").read_text())
decision = json.loads(Path("environment-expansion.json").read_text())
valid = structural(decision, Path("."), subject)
public = execute_public(Path("."), decision) if valid else None
result = {"structural": valid, "public": public}
print(json.dumps(result, sort_keys=True))
raise SystemExit(0 if valid and public["all_valid"] else 2)
'''
)


def seed_actor(root, subject, decision):
    seed = root / "seed"
    seed.mkdir(parents=True)
    write_visible_world(seed, subject["active_streamed_world_offer"])
    write_json(seed / "exact-subject.json", subject)
    write_json(seed / "streamed-world-offer.json", subject["active_streamed_world_offer"])
    write_json(seed / "local-frontier-ledger.json", subject["local_frontier_ledger"])
    write_json(
        seed / "expansion-contract.json",
        {
            "authority": AUTHORITY + "-public-contact-contract",
            "contact_fields": sorted(CONTACT_CORE),
            "abi": ABI,
            "predicates": PREDICATES,
            "source_of_eligible_pairs": "streamed-world-offer-visible-sources",
            "sealed_consequence_available_to_actor": False,
        },
    )
    write_json(seed / "environment-expansion.json", decision)
    (seed / "check_expansion.py").write_text(CHECKER_SOURCE)
    package_files = sorted(subject["active_streamed_world_offer"]["visible_sources"])
    initializers = sorted({str(Path(relative).parent / "__init__.py") for relative in package_files})
    immutable = [
        "exact-subject.json",
        "streamed-world-offer.json",
        "local-frontier-ledger.json",
        "expansion-contract.json",
        "check_expansion.py",
        *initializers,
        *package_files,
        "mutation-envelope.json",
        "README.md",
    ]
    write_json(
        seed / "mutation-envelope.json",
        {"editable": ["environment-expansion.json"], "immutable": immutable},
    )
    (seed / "README.md").write_text(
        "Continue from the exact open subject under a content-free environment-expansion "
        "pulse. A standing-feed world offer is visible. Inspect its executable public "
        "sources and choose one coherent bounded contact that is not already in the "
        "ledger. No task, target, or preferred surface is assigned. Edit only "
        "environment-expansion.json, author four executable public cases, run python3 "
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


def evaluate_workspace(seed, workspace, subject):
    try:
        decision = json.loads((workspace / "environment-expansion.json").read_text())
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all(
            (workspace / name).read_bytes() == (seed / name).read_bytes()
            for name in immutable
        )
        semantic = immutable_ok and structural(decision, workspace, subject)
        public = execute_public(workspace, decision) if semantic else None
        semantic = bool(semantic and public and public["all_valid"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        decision, public, immutable_ok, semantic = None, None, False, False
    return {
        "decision": decision,
        "public": public,
        "immutable_ok": immutable_ok,
        "semantic": semantic,
    }


def run_actor(context, p82, root, subject):
    seed = seed_actor(root, subject, template())
    label = "standing-feed-package-contact-actor"
    output, base_audit, workspace, _ = context.run_actor(
        label, seed, SCHEMA, (seed / "README.md").read_text().strip()
    )
    evaluated = evaluate_workspace(seed, workspace, subject)
    transport = output_valid(output)
    audit = context.audit_actor(
        label,
        output,
        base_audit,
        evaluated["semantic"] and transport,
        ["environment-expansion.json"],
    )
    trace = (context.evidence(label) / "events.jsonl").read_text()
    normalized = base236.classify_retained(audit, trace)
    accepted = bool(evaluated["semantic"] and transport and base236.g10(normalized))
    binding = None
    if accepted:
        decision = evaluated["decision"]
        contact = decision["next_contact"]
        offer = subject["active_streamed_world_offer"]
        body = {
            "authority": AUTHORITY + "-actor-contact-binding",
            "source_subject_digest": subject["artifact_digest"],
            "pulse_content": PULSE,
            "derived_operation": "expand-environment",
            "world_id": offer["world_id"],
            "world_offer_receipt_digest": offer["offer_receipt_digest"],
            "public_package_digest": offer["public_package_digest"],
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
            "public_result": evaluated["public"],
            "selection_authority": False,
            "denial_provenance": normalized["provenance"],
        }
        binding = {**body, "binding_digest": p82.digest(body)}
        write_json(context.evidence(label) / "bound-standing-feed-contact.json", binding)
    return {
        "accepted": binding is not None,
        "binding": binding,
        "decision": evaluated["decision"],
        "public": evaluated["public"],
        "audit": audit,
        "g10_disposition": accepted,
        "output": output,
        "workspace_evaluation": {
            "immutable_ok": evaluated["immutable_ok"],
            "semantic": evaluated["semantic"],
        },
    }


def compile_intermediate(subject, action, pulse, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    decision = action["decision"]
    contact = copy.deepcopy(decision["next_contact"])
    target = contact["target_symbol"]
    path = contact["target_path"]
    offer = subject["active_streamed_world_offer"]
    sources = {
        relative: row["source"] for relative, row in offer["visible_sources"].items()
    }
    consumption_body = {
        "authority": AUTHORITY + "-offer-consumption",
        "source_subject_digest": subject["artifact_digest"],
        "offer_receipt_digest": offer["offer_receipt_digest"],
        "binding_digest": action["binding"]["binding_digest"],
        "world_id": offer["world_id"],
        "public_package_digest": offer["public_package_digest"],
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
        "world_id": offer["world_id"],
        "offer_receipt_digest": offer["offer_receipt_digest"],
        "visible_world_digest": p82.digest(sources),
        "public_package_digest": offer["public_package_digest"],
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
        "environment_id": offer["world_id"],
        "region_rationale": decision["region_rationale"],
        "selected_path": path,
        "selected_target": target,
        "visible_sources": copy.deepcopy(offer["visible_sources"]),
        "status": "actor-authored-contact-bound-from-standing-feed",
    }
    child["actor_authored_environment_epochs"] = [
        *child["actor_authored_environment_epochs"],
        epoch_row,
    ]
    extension = {
        "authority": AUTHORITY + "-extension",
        "source_subject_digest": subject["artifact_digest"],
        "binding_digest": action["binding"]["binding_digest"],
        "environment_id": offer["world_id"],
        "target_path": path,
        "target_symbol": target,
        "abi": contact["abi"],
        "installed_source": sources[path],
        "installed_source_digest": p82.digest(sources[path]),
        "status": "bound-from-standing-feed-package",
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
        "origin": "standing-feed-independent-package-selection",
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
        "status": "live-standing-feed-package-contact",
        "contact_identity": pending["contact_identity"],
        "binding_digest": pending["binding_digest"],
        "target_status": "verification-due",
    }
    child["unresolved"] = "Expose the standing-feed actor-selected contact to retained package consequence."
    return p82.seal(child)


def sealed_world(intermediate, action, package, result268, p82):
    evaluation = base268.evaluate_package(package, p82.digest)
    target = action["decision"]["next_contact"]["target_symbol"]
    path = evaluation["targets"].get(target) if evaluation.get("valid") else None
    if path != action["decision"]["next_contact"]["target_path"]:
        raise RuntimeError("selected target does not resolve in retained package")
    rows = evaluation["rows"][target]
    observed = {
        "case_count": len(rows),
        "all_valid": len(rows) == 6,
        "matches": sum(row["matches"] for row in rows),
        "rows": rows,
    }
    outcome = (
        "success"
        if observed["matches"] >= 4
        else ("surrender" if observed["matches"] == 0 else "unresolved")
    )
    body = {
        "authority": AUTHORITY + "-retained-package-sealed-world",
        "source_subject_digest": intermediate["artifact_digest"],
        "contact_binding_digest": action["binding"]["binding_digest"],
        "contact_identity": action["binding"]["contact_identity"],
        "world_id": package["world_id"],
        "target_path": path,
        "target_symbol": target,
        "ot0268_aggregate_receipt_digest": result268["receipt_digest"],
        "public_package_digest": evaluation["public_package_digest"],
        "full_package_digest": evaluation["full_package_digest"],
        "hidden_cases_digest": p82.digest(package["sealed_cases"][target]),
        "reference_source_digest": p82.digest(package["sealed_reference_sources"][path]),
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
        "status": "unresolved-independent-package-contact",
        "contact_identity": world["contact_identity"],
        "world_receipt_digest": world["receipt_digest"],
        "target_status": "unresolved",
    }
    child["unresolved"] = "Correct the actor-selected package contact from retained independent consequence."
    return p82.seal(child)


def fixture_decision(package, evaluation, target):
    path = evaluation["targets"][target]
    cases = [
        {
            "case_id": f"public-fixture-{index}",
            "input": copy.deepcopy(row["input"]),
        }
        for index, row in enumerate(package["sealed_cases"][target][:4], 1)
    ]
    return {
        "environment_id": package["world_id"],
        "region_rationale": "The offered public package exposes an executable unresolved surface.",
        "next_pursuit": "Test the selected visible policy against independent world consequence.",
        "next_contact": {
            "contact_id": f"fixture-{target}",
            "target_path": path,
            "target_symbol": target,
            "abi": ABI,
            "stake": "Determine whether the visible local policy survives independent consequence.",
            "cases": cases,
            "predicates": copy.deepcopy(PREDICATES),
        },
    }


def seed_excludes_sealed(seed, package, result268):
    files = [path for path in seed.rglob("*") if path.is_file()]
    corpus = "\n".join(path.read_text(errors="replace") for path in files)
    reference_sources_absent = all(
        source not in corpus for source in package["sealed_reference_sources"].values()
    )
    return (
        reference_sources_absent
        and json.dumps(package["sealed_cases"], sort_keys=True) not in corpus
        and result268["full_package_digest"] not in corpus
        and not any("sealed" in path.name.lower() for path in files)
    )


def prospective_path(root, offered, package, evaluation, result268, target, p82, runtime):
    decision = fixture_decision(package, evaluation, target)
    seed = seed_actor(root / "actor", offered, decision)
    checker = subprocess.run(
        ["python3", "check_expansion.py"], cwd=seed, capture_output=True
    )
    evaluated = evaluate_workspace(seed, seed, offered)
    action = {
        "decision": decision,
        "binding": {
            "binding_digest": "a" * 64,
            "contact_identity": "b" * 64,
        },
    }
    pulse = {
        "authority": AUTHORITY + "-fixture-pulse",
        "content": None,
        "source_subject_digest": offered["artifact_digest"],
        "derived_operation": "expand-environment",
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    intermediate = compile_intermediate(offered, action, pulse, p82)
    world = sealed_world(intermediate, action, package, result268, p82)
    final = compile_world(intermediate, world, p82)
    return {
        "target": target,
        "path": evaluation["targets"][target],
        "checker": checker.returncode == 0,
        "semantic": evaluated["semantic"],
        "public": bool(evaluated["public"] and evaluated["public"]["all_valid"]),
        "sealed_matches": world["result"]["matches"],
        "world_outcome": world["outcome"],
        "intermediate_conformant": runtime.identity_conforms(intermediate),
        "final_conformant": runtime.identity_conforms(final),
        "routes_correction": derive(final, p82) == "outward-correct",
    }


def negative_anchors(seed, offered, valid):
    contact = valid["next_contact"]
    pairs = sorted(offered_pairs(offered))
    other = next(pair for pair in pairs if pair != (contact["target_path"], contact["target_symbol"]))
    completed = copy.deepcopy(valid)
    completed_target = sorted(offered["local_frontier_ledger"]["targets"])[0]
    completed["next_contact"]["target_symbol"] = completed_target
    mismatch = copy.deepcopy(valid)
    mismatch["next_contact"]["target_symbol"] = other[1]
    absolute = copy.deepcopy(valid)
    absolute["next_contact"]["target_path"] = "/tmp/world.py"
    traversal = copy.deepcopy(valid)
    traversal["next_contact"]["target_path"] = "../world.py"
    wrong_predicates = copy.deepcopy(valid)
    wrong_predicates["next_contact"]["predicates"] = {}
    wrong_abi = copy.deepcopy(valid)
    wrong_abi["next_contact"]["abi"] = "unknown-abi"
    three_cases = copy.deepcopy(valid)
    three_cases["next_contact"]["cases"] = three_cases["next_contact"]["cases"][:3]
    duplicate = copy.deepcopy(valid)
    duplicate["next_contact"]["cases"][1]["case_id"] = duplicate["next_contact"]["cases"][0]["case_id"]
    missing = copy.deepcopy(valid)
    missing["next_contact"]["target_symbol"] = "not_present"
    return {
        "completed_target": not structural(completed, seed, offered),
        "mismatched_pair": not structural(mismatch, seed, offered),
        "absolute_path": not structural(absolute, seed, offered),
        "traversal_path": not structural(traversal, seed, offered),
        "wrong_predicates": not structural(wrong_predicates, seed, offered),
        "wrong_abi": not structural(wrong_abi, seed, offered),
        "three_cases": not structural(three_cases, seed, offered),
        "duplicate_cases": not structural(duplicate, seed, offered),
        "missing_function": not structural(missing, seed, offered),
        "template": not structural(template(), seed, offered),
    }


def preflight(run, p82, runtime, parent, result269, package, result268):
    fixture_root = run.parent / "OT-0270-preflight"
    shutil.rmtree(fixture_root, ignore_errors=True)
    fixture_root.mkdir(parents=True)
    evaluation = base268.evaluate_package(package, p82.digest)
    normalized_package_digest = base267.normalize_package(
        public_package(package), p82.digest
    )["package_digest"]
    observation = scan(parent, package, p82)
    offered, reused = compile_offer(parent, observation, p82)
    repeated_observation = scan(offered, package, p82)
    repeated, repeated_reused = compile_offer(offered, repeated_observation, p82)
    empty = base267.scan_feed(parent, [], p82.digest)
    malformed = public_package(package)
    first_path = sorted(malformed["visible_sources"])[0]
    malformed["visible_sources"][first_path] = "def broken(:\n"
    malformed_result = base267.scan_feed(parent, [malformed], p82.digest)
    seen = copy.deepcopy(parent)
    seen.pop("artifact_digest", None)
    seen["environment_stream_receipts"] = [
        *seen["environment_stream_receipts"],
        {"world_id": package["world_id"]},
    ]
    seen = p82.seal(seen)
    seen_result = scan(seen, package, p82)
    paths = [
        prospective_path(
            fixture_root / f"path-{index}",
            offered,
            package,
            evaluation,
            result268,
            target,
            p82,
            runtime,
        )
        for index, target in enumerate(sorted(evaluation.get("targets", {})), 1)
    ]
    valid = fixture_decision(package, evaluation, sorted(evaluation["targets"])[0])
    anchor_seed = seed_actor(fixture_root / "anchors", offered, valid)
    anchors = negative_anchors(anchor_seed, offered, valid)
    live_seed = seed_actor(fixture_root / "live-template", offered, template())
    route, identity = base265.floors(parent)
    script = Path(__file__).read_text()
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_third_wait": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and derive(parent, p82) == "wait-provider"
        and len(parent["world_stream_wait_receipts"]) == 3
        and runtime.identity_conforms(parent),
        "ot0269_exact_promotion": result269["observer_disposition"] == "promoted"
        and result269["receipt_digest"] == OT269_RECEIPT
        and result269["final_subject_digest"] == PARENT_DIGEST,
        "ot0268_exact_retained_package": result268["observer_disposition"] == "promoted"
        and result268["receipt_digest"] == OT268_RECEIPT
        and evaluation.get("valid")
        and result268["world_id"] == package["world_id"] == evaluation["world_id"]
        and result268["public_package_digest"] == evaluation["public_package_digest"]
        and result268["full_package_digest"] == evaluation["full_package_digest"],
        "standing_scanner_exact": parent["active_standing_world_provider"]["scanner_source_digest"]
        == p82.digest(base267.SCANNER_SOURCE),
        "empty_seen_malformed_controls": empty["status"] == "empty"
        and seen_result["status"] == "empty"
        and malformed_result["status"] == "invalid-feed",
        "scanner_finds_exact_unseen_package": observation["status"] == "world-available"
        and wait_satisfied(parent, observation)
        and observation["available_world"]["package_digest"]
        == normalized_package_digest,
        "actor_free_non_authoritative_offer": not reused
        and offered["active_world_stream_wait"] is None
        and offered["active_streamed_world_offer"]["world_id"] == package["world_id"]
        and offered["active_streamed_world_offer"]["package_digest"]
        == normalized_package_digest
        and offered["active_streamed_world_offer"]["public_package_digest"]
        == evaluation["public_package_digest"]
        and all(
            offered["active_streamed_world_offer"][key] is False
            for key in (
                "selection_authority",
                "scoring_authority",
                "admission_authority",
                "outcome_authority",
                "actor_authority",
            )
        )
        and offered["actor_authored_environment_epochs"]
        == parent["actor_authored_environment_epochs"]
        and offered["local_frontier_ledger"] == parent["local_frontier_ledger"],
        "third_wait_discharged_exactly_once": len(offered["world_stream_wait_discharge_receipts"])
        == len(parent["world_stream_wait_discharge_receipts"]) + 1
        and offered["world_stream_wait_discharge_receipts"][-1]["wait_handle_digest"]
        == parent["active_world_stream_wait"]["wait_handle_digest"],
        "repeated_offer_idempotent": repeated_observation["status"] == "empty"
        and repeated_reused
        and repeated["artifact_digest"] == offered["artifact_digest"],
        "all_three_paths_pass": len(paths) == 3
        and all(
            row["checker"]
            and row["semantic"]
            and row["public"]
            and row["sealed_matches"] == 2
            and row["world_outcome"] == "unresolved"
            and row["intermediate_conformant"]
            and row["final_conformant"]
            and row["routes_correction"]
            for row in paths
        ),
        "all_hard_anchors_reject": all(anchors.values()),
        "live_actor_seed_public_only": seed_excludes_sealed(live_seed, package, result268),
        "live_prompt_names_no_surface": not any(
            token in (live_seed / "README.md").read_text()
            for path, target in offered_pairs(offered)
            for token in (path, target)
        ),
        "dynamic_surface_not_hardcoded": not any(
            token in script
            for path, target in offered_pairs(offered)
            for token in (path, target)
        ),
        "offered_conformant": runtime.identity_conforms(offered),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    return {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "expected_operations": list(EXPECTED),
        "prospective_surface_count": len(paths),
        "path_rows": paths,
        "anchors": anchors,
        "checks": checks,
    }, route, identity


def advance(
    repo,
    run,
    p82,
    runtime,
    parent,
    package,
    result268,
    fixtures,
    route,
    identity,
    base,
    base130,
):
    results = sorted(run.glob("invocation-*-result.json")) if run.exists() else []
    checkpoint = run / "checkpoint-subject.json"
    if results and not checkpoint.exists():
        raise SystemExit("preserve failed OT-0270 invocation")
    if not run.exists():
        run.mkdir(parents=True)
        write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    if (run / "aggregate.json").exists():
        raise SystemExit("preserve completed OT-0270 evidence")
    subject = json.loads(checkpoint.read_text()) if checkpoint.exists() else parent
    if not runtime.identity_conforms(subject):
        raise SystemExit("serialized checkpoint invalid")
    index = len(results) + 1
    if index > len(EXPECTED):
        raise SystemExit("unexpected invocation count")
    operation = derive(subject, p82)
    root = run / f"invocation-{index:02d}"
    root.mkdir(parents=True)
    pulse = {
        "authority": AUTHORITY + "-pulse",
        "content": PULSE,
        "source_subject_digest": subject["artifact_digest"],
        "derived_operation": operation,
    }
    pulse["pulse_digest"] = p82.digest(pulse)
    actor = None
    world = None
    final = subject
    checks = {
        "content_free_expected_operation": pulse["content"] is None
        and operation == EXPECTED[index - 1]
    }
    if operation == "wait-provider":
        world = scan(subject, package, p82)
        final, reused = compile_offer(subject, world, p82)
        offer = final.get("active_streamed_world_offer")
        normalized_package_digest = base267.normalize_package(
            public_package(package), p82.digest
        )["package_digest"]
        checks.update(
            zero_fresh_actors=True,
            standing_scanner_found_package=world["status"] == "world-available"
            and world["available_world"]["package_digest"]
            == normalized_package_digest,
            exact_wait_satisfied=wait_satisfied(subject, world),
            exact_third_wait_discharged=not reused
            and final["active_world_stream_wait"] is None
            and final["world_stream_wait_discharge_receipts"][-1]["wait_handle_digest"]
            == subject["active_world_stream_wait"]["wait_handle_digest"],
            public_non_authoritative_offer=bool(
                offer
                and offer["world_id"] == package["world_id"]
                and offer["package_digest"] == normalized_package_digest
                and offer["public_package_digest"]
                == result268["public_package_digest"]
                and all(
                    offer[key] is False
                    for key in (
                        "selection_authority",
                        "scoring_authority",
                        "admission_authority",
                        "outcome_authority",
                        "actor_authority",
                    )
                )
            ),
            no_epoch_or_ledger_change=final["actor_authored_environment_epochs"]
            == subject["actor_authored_environment_epochs"]
            and final["local_frontier_ledger"] == subject["local_frontier_ledger"],
            next_is_expansion=derive(final, p82) == "expand-environment",
        )
    elif operation == "expand-environment":
        context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(
            base.typed.base.make_context(runtime, root, repo)
        )
        actor = run_actor(context, p82, root / "actor", subject)
        intermediate = (
            compile_intermediate(subject, actor, pulse, p82)
            if actor["accepted"]
            else subject
        )
        world = (
            sealed_world(intermediate, actor, package, result268, p82)
            if actor["accepted"]
            else None
        )
        final = compile_world(intermediate, world, p82) if world else intermediate
        if world:
            write_json(root / "world-receipt.json", world)
        selected = actor["decision"]["next_contact"] if actor.get("decision") else None
        pair = (
            (selected["target_path"], selected["target_symbol"])
            if selected
            else None
        )
        checks.update(
            one_fresh_actor=True,
            actor_accepted=actor["accepted"],
            selected_offered_surface=pair in offered_pairs(subject),
            g10_accepted=actor["g10_disposition"],
            public_four_cases=bool(
                actor["public"]
                and actor["public"]["all_valid"]
                and actor["public"]["case_count"] == 4
            ),
            actor_workspace_public_only=seed_excludes_sealed(
                root / "actor" / "seed", package, result268
            ),
            retained_package_sealed_2_of_6=bool(
                world
                and world["result"]["all_valid"]
                and world["result"]["matches"] == 2
                and world["ot0268_aggregate_receipt_digest"] == OT268_RECEIPT
                and world["public_package_digest"] == result268["public_package_digest"]
                and world["full_package_digest"] == result268["full_package_digest"]
            ),
            offer_consumed=final.get("active_streamed_world_offer") is None,
            one_new_epoch=len(final["actor_authored_environment_epochs"])
            == len(subject["actor_authored_environment_epochs"]) + 1,
            correction_before_refresh=base260.needs_refresh(final, p82)
            and derive(final, p82) == "outward-correct",
        )
    else:
        checks["known_operation"] = False
    checks["standing_scanner_preserved"] = (
        final["active_standing_world_provider"]
        == subject["active_standing_world_provider"]
    )
    checks["final_open_conformant"] = (
        final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final)
    )
    checks["passed"] = all(checks.values())
    result = {
        "authority": AUTHORITY + f"-invocation-{index:02d}",
        "invocation_index": index,
        "source_subject_digest": subject["artifact_digest"],
        "pulse": pulse,
        "actor": actor,
        "world": world,
        "checks": checks,
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1 if actor else 0,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / f"invocation-{index:02d}-result.json", result)
    write_json(run / f"invocation-{index:02d}-subject.json", final)
    if not checks["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    write_json(checkpoint, final)
    if index < len(EXPECTED):
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    all_results = [
        json.loads(path.read_text())
        for path in sorted(run.glob("invocation-*-result.json"))
    ]
    gates = {
        "preflight_passed": fixtures["checks"]["passed"],
        "two_same_entry_invocations": len(all_results) == 2
        and [row["pulse"]["derived_operation"] for row in all_results]
        == list(EXPECTED)
        and all(row["pulse"]["content"] is None for row in all_results),
        "all_invocation_gates_pass": all(row["checks"]["passed"] for row in all_results),
        "exactly_one_fresh_actor": sum(row["fresh_actor_count"] for row in all_results) == 1,
        "three_waits_three_discharges": final["world_stream_wait_receipts"]
        == parent["world_stream_wait_receipts"]
        and len(final["world_stream_wait_discharge_receipts"])
        == len(parent["world_stream_wait_discharge_receipts"]) + 1
        == 3,
        "independent_package_consumed_once": len(final["environment_stream_receipts"])
        == len(parent["environment_stream_receipts"]) + 1
        and final["environment_stream_receipts"][-1]["world_id"] == package["world_id"]
        and len(final["actor_authored_environment_epochs"])
        == len(parent["actor_authored_environment_epochs"]) + 1,
        "retained_package_owned_consequence": all_results[-1]["world"][
            "ot0268_aggregate_receipt_digest"
        ]
        == OT268_RECEIPT
        and all_results[-1]["world"]["result"]["matches"] == 2,
        "final_correction_before_refresh": base260.needs_refresh(final, p82)
        and derive(final, p82) == "outward-correct",
        "standing_scanner_preserved": final["active_standing_world_provider"]
        == parent["active_standing_world_provider"],
        "final_open_conformant": final["continuation"]["status"] == "open"
        and runtime.identity_conforms(final),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    gates["passed"] = all(gates.values())
    aggregate = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "ot0268_package_receipt_digest": OT268_RECEIPT,
        "invocation_receipt_digests": [row["receipt_digest"] for row in all_results],
        "checks": gates,
        "observer_disposition": "promoted" if gates["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "fresh_actor_count": 1,
        "invocation_count": 2,
    }
    aggregate["receipt_digest"] = p82.digest(aggregate)
    write_json(run / "aggregate.json", aggregate)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if gates["passed"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    (
        repo,
        run,
        p82,
        runtime,
        parent,
        result269,
        package,
        result268,
        base,
        base130,
    ) = setup(args)
    fixtures, route, identity = preflight(
        run, p82, runtime, parent, result269, package, result268
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return advance(
        repo,
        run,
        p82,
        runtime,
        parent,
        package,
        result268,
        fixtures,
        route,
        identity,
        base,
        base130,
    )


if __name__ == "__main__":
    raise SystemExit(main())
