from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0103_normalized_recurrence_continuation.py"
BASE_SHA256 = "6296cf2237b3e0a58d0c5f6a8ac65b842d85909d4a7e43f737a73595228f74a4"
PARENT_OBJECT_SHA256 = "39f7450e965f752604ed4b2b795cd76e0e1212a6d6e242da0c72355fecfce883"
PARENT_DIGEST = "5537d3e7c1e0326fe6bb4140746df2ae9419e99398bb2da09a899365cb47c172"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0103 implementation identity changed")
    name = "ot0104_frozen_ot0103"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base = prior.base


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    manifest, path = p82.materialize(repo, store, "OT-0103", "open-subject-after-two-cycle-recurrence.json")
    if manifest["sha256"] != PARENT_OBJECT_SHA256:
        raise RuntimeError("wrong OT-0103 subject object identity")
    return json.loads(path.read_text())


def extract_action(p82, subject: dict[str, Any]) -> dict[str, Any] | None:
    openings = subject.get("actor_originated_pursuit_openings", [])
    if not openings:
        return None
    retained = openings[-1]
    next_interface = retained.get("next_interface")
    if not base.valid_next_interface(next_interface):
        return None
    if subject.get("active_pursuit", {}).get("selected_area") != next_interface["interface_id"]:
        return None
    if subject.get("continuation", {}).get("next_opening") != retained.get("opening", {}).get("next_opening"):
        return None
    body = {
        "authority": "ot-0104-subject-bound-interface",
        "source_subject_digest": subject["artifact_digest"],
        "assimilation_binding_digest": retained["binding_digest"],
        "next_interface": next_interface,
    }
    return {**body, "binding_digest": p82.digest(body)}


def erased_binding_subject(subject: dict[str, Any]) -> dict[str, Any]:
    erased = json.loads(json.dumps(subject))
    erased["actor_originated_pursuit_openings"][-1].pop("next_interface", None)
    erased["active_pursuit"] = {**erased["active_pursuit"], "selected_area": "opaque"}
    return erased


def fixture_conformance(p82, parent: dict[str, Any]) -> dict[str, Any]:
    inherited = base.fixture_conformance(p82, parent)
    action = extract_action(p82, parent)
    erased = extract_action(p82, erased_binding_subject(parent))
    result = {
        "inherited_interfaces": inherited,
        "active_action_derived": bool(action and action["next_interface"]["interface_id"] == "allocator-challenge"),
        "binding_erasure_stops_action": erased is None,
        "active_binding_digest": action["binding_digest"] if action else None,
    }
    result["passed"] = bool(
        inherited["passed"] and result["active_action_derived"] and result["binding_erasure_stops_action"]
    )
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
    run = (args.evidence_root or store / "runs/OT-0104").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    if (
        parent["artifact_digest"] != PARENT_DIGEST or not runtime.identity_conforms(parent)
        or parent["runtime"] != "sounding" or parent["continuation"]["status"] != "open"
    ):
        raise SystemExit("wrong OT-0103 parent")
    fixtures = fixture_conformance(p82, parent)
    if args.preflight_only:
        result = {
            "parent_digest": parent["artifact_digest"], "parent_object_sha256": PARENT_OBJECT_SHA256,
            "base_implementation_sha256": BASE_SHA256, "fixture_conformance": fixtures,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0104 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    selection = extract_action(p82, parent)
    (run / "bound-subject-action.json").write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n")
    context = prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
    started = time.time()
    cycle = base.run_cycle(prior89, p82, runtime, context, run, 3, parent, selection)
    operational = cycle["operational_transition_passed"]
    current = cycle["current"] if operational else parent
    if operational:
        (run / "sealed-operational-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    result = {
        "authority": "ot-0104-bound-cross-interface-recurrence-driver",
        "source_subject_digest": parent["artifact_digest"],
        "bound_action": selection,
        "binding_erasure_stops_action": extract_action(p82, erased_binding_subject(parent)) is None,
        "cross_interface_cycle": p82.compact({key: value for key, value in cycle.items() if key != "current"}),
        "cross_interface_operational_recurrence_passed": operational,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
        "final_subject_digest": current["artifact_digest"],
        "next_interface": current["actor_originated_pursuit_openings"][-1].get("next_interface"),
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
