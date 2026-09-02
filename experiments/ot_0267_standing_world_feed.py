from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0266_second_wake_to_live_contact.py"
BASE_SHA256 = "b27e70de778de884bcb75c94c976fc4ff7b0afdc4e92a2b60920881944e23aa6"
PARENT_DIGEST = "d3ef7b3362c8f4f89eb6f0522610d1642740c1e55a38770accfd0c58f404270c"
OT266_RECEIPT = "316a0d03404e56770919e4874e2ef2f53cc21fe3862f80ed3c254bcdc47fe4af"
AUTHORITY = "ot-0267-standing-world-feed"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0266 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0267_frozen_ot0266", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base266 = load_base()
base265 = base266.base265
base261 = base266.base261
base260 = base266.base260
authority_base = base266.authority_base


def write_json(path, value):
    authority_base.guide_base.write_json(path, value)


def valid_world_id(value):
    return (
        isinstance(value, str)
        and 3 <= len(value) <= 64
        and value[0].isalnum()
        and value[-1].isalnum()
        and all(character.isalnum() or character in "-_" for character in value)
    )


def normalize_package(package, digest):
    if not isinstance(package, dict) or set(package) != {"world_id", "visible_sources"}:
        return None
    world_id = package.get("world_id")
    sources = package.get("visible_sources")
    if not valid_world_id(world_id) or not isinstance(sources, dict) or not 2 <= len(sources) <= 8:
        return None
    normalized_sources = {}
    for relative, source in sorted(sources.items()):
        if not isinstance(relative, str) or not isinstance(source, str) or not source or len(source.encode()) > 10000:
            return None
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 2 or path.suffix != ".py":
            return None
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        callables = sorted(
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        )
        if not callables:
            return None
        normalized_sources[relative] = {
            "source": source,
            "source_digest": digest(source),
            "top_level_callables": callables,
        }
    body = {"world_id": world_id, "visible_sources": normalized_sources}
    return {**body, "package_digest": digest(body)}


def scan_feed(subject, packages, digest):
    if not isinstance(packages, list):
        return {"status": "invalid-feed", "reason": "catalog-not-list"}
    normalized = [normalize_package(package, digest) for package in packages]
    if any(package is None for package in normalized):
        return {"status": "invalid-feed", "reason": "invalid-package"}
    ids = [package["world_id"] for package in normalized]
    if len(ids) != len(set(ids)):
        return {"status": "invalid-feed", "reason": "duplicate-world-id"}
    seen = {
        row["world_id"]
        for row in subject.get("environment_stream_receipts", [])
        if isinstance(row, dict) and isinstance(row.get("world_id"), str)
    }
    offer = subject.get("active_streamed_world_offer")
    if isinstance(offer, dict) and isinstance(offer.get("world_id"), str):
        seen.add(offer["world_id"])
    catalog = sorted(normalized, key=lambda package: package["world_id"])
    unseen = [package for package in catalog if package["world_id"] not in seen]
    body = {
        "authority": AUTHORITY + "-observation",
        "source_subject_digest": subject["artifact_digest"],
        "catalog": [
            {"world_id": package["world_id"], "package_digest": package["package_digest"]}
            for package in catalog
        ],
        "seen_world_ids": sorted(seen),
        "cursor_digest": digest(
            {
                "catalog": [
                    (package["world_id"], package["package_digest"])
                    for package in catalog
                ],
                "seen": sorted(seen),
            }
        ),
        "status": "world-available" if unseen else "empty",
        "available_world": unseen[0] if unseen else None,
        "selection_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
        "actor_authority": False,
    }
    return {**body, "receipt_digest": digest(body)}


SCANNER_SOURCE = (
    inspect.getsource(valid_world_id)
    + inspect.getsource(normalize_package)
    + inspect.getsource(scan_feed)
)


def install(subject, p82):
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    body = {
        "authority": AUTHORITY + "-interface",
        "source_subject_digest": subject["artifact_digest"],
        "logical_feed_root": "$WORLD_FEED",
        "package_schema": {
            "required": ["world_id", "visible_sources"],
            "source_count": [2, 8],
            "source_path": "relative-two-component-python",
            "source_semantics": "parseable-with-public-top-level-callable",
        },
        "scanner_source": SCANNER_SOURCE,
        "scanner_source_digest": p82.digest(SCANNER_SOURCE),
        "selection_authority": False,
        "scoring_authority": False,
        "admission_authority": False,
        "outcome_authority": False,
        "actor_authority": False,
    }
    transition = {**body, "transition_receipt_digest": p82.digest(body)}
    child["standing_world_provider_transitions"] = [
        *child.get("standing_world_provider_transitions", []),
        transition,
    ]
    child["active_standing_world_provider"] = transition
    child["streamed_world_interface_transitions"] = [
        *child.get("streamed_world_interface_transitions", []),
        transition,
    ]
    child["active_streamed_world_interface"] = copy.deepcopy(transition)
    return p82.seal(child)


PACKAGE_A = {
    "world_id": "fixture-alpha-v1",
    "visible_sources": {
        "bridges/repair.py": "def choose_repairs(case):\n    return []\n",
        "bridges/inspect.py": "def rank_inspections(case):\n    return []\n",
    },
}
PACKAGE_B = {
    "world_id": "fixture-beta-v1",
    "visible_sources": {
        "energy/store.py": "def allocate_storage(case):\n    return []\n",
        "energy/route.py": "async def route_energy(case):\n    return []\n",
        "energy/share.py": "def share_capacity(case):\n    return []\n",
    },
}
HELDOUT = {
    "world_id": "heldout-standing-world-v1",
    "visible_sources": {
        "habitat/air.py": "def allocate_scrubbers(case):\n    return []\n",
        "habitat/heat.py": "def stage_heaters(case):\n    return []\n",
    },
}


def invalid_packages():
    huge = "def valid(case):\n    return []\n" + "#" * 10001
    return [
        {},
        {"world_id": "x", "visible_sources": PACKAGE_A["visible_sources"]},
        {**PACKAGE_A, "extra": True},
        {"world_id": "bad id", "visible_sources": PACKAGE_A["visible_sources"]},
        {"world_id": "empty-v1", "visible_sources": {}},
        {"world_id": "one-v1", "visible_sources": {"one/a.py": "def a():\n    pass\n"}},
        {"world_id": "absolute-v1", "visible_sources": {"/tmp/a.py": "def a():\n    pass\n", "x/b.py": "def b():\n    pass\n"}},
        {"world_id": "traversal-v1", "visible_sources": {"../a.py": "def a():\n    pass\n", "x/b.py": "def b():\n    pass\n"}},
        {"world_id": "deep-v1", "visible_sources": {"x/y/a.py": "def a():\n    pass\n", "x/b.py": "def b():\n    pass\n"}},
        {"world_id": "text-v1", "visible_sources": {"x/a.txt": "def a():\n    pass\n", "x/b.py": "def b():\n    pass\n"}},
        {"world_id": "syntax-v1", "visible_sources": {"x/a.py": "def a(:\n", "x/b.py": "def b():\n    pass\n"}},
        {"world_id": "private-v1", "visible_sources": {"x/a.py": "def _a():\n    pass\n", "x/b.py": "def b():\n    pass\n"}},
        {"world_id": "huge-v1", "visible_sources": {"x/a.py": huge, "x/b.py": "def b():\n    pass\n"}},
    ]


def operational_core(subject):
    ignored = {
        "artifact_digest",
        "active_streamed_world_interface",
        "streamed_world_interface_transitions",
        "active_standing_world_provider",
        "standing_world_provider_transitions",
    }
    return {key: value for key, value in subject.items() if key not in ignored}


def main():
    lineage = authority_base.guide_base.load_base()
    selector_base, base = lineage.selector_base, lineage.base
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0267").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0266", "open-subject-at-fourth-epoch-contradiction.json"
    )
    result266 = selector_base.load_artifact(
        p82, repo, store, "OT-0266", "second-wake-to-live-contact-aggregate.json"
    )
    successor = install(parent, p82)
    positive_a = scan_feed(parent, [PACKAGE_A], p82.digest)
    positive_b = scan_feed(parent, [PACKAGE_B], p82.digest)
    ordered = scan_feed(parent, [PACKAGE_A, PACKAGE_B], p82.digest)
    reversed_order = scan_feed(parent, [PACKAGE_B, PACKAGE_A], p82.digest)
    seen = copy.deepcopy(parent)
    seen.pop("artifact_digest", None)
    seen["environment_stream_receipts"] = [
        *seen["environment_stream_receipts"],
        {"world_id": PACKAGE_A["world_id"]},
        {"world_id": PACKAGE_B["world_id"]},
    ]
    seen = p82.seal(seen)
    offered = copy.deepcopy(parent)
    offered.pop("artifact_digest", None)
    offered["active_streamed_world_offer"] = {"world_id": PACKAGE_A["world_id"]}
    offered = p82.seal(offered)
    old_provider = base266.provider_observation(parent, p82, extended=True)
    heldout = scan_feed(parent, [HELDOUT], p82.digest)
    invalid = [scan_feed(parent, [package], p82.digest) for package in invalid_packages()]
    duplicate = scan_feed(parent, [PACKAGE_A, copy.deepcopy(PACKAGE_A)], p82.digest)
    route, identity = base265.floors(parent)
    checks = {
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
        "parent_exact_open_correction": parent["artifact_digest"] == PARENT_DIGEST
        and parent["continuation"]["status"] == "open"
        and base260.needs_refresh(parent, p82)
        and base261.challenger(parent, p82) == "outward-correct"
        and runtime.identity_conforms(parent),
        "ot0266_exact_promotion": result266["observer_disposition"] == "promoted"
        and result266["receipt_digest"] == OT266_RECEIPT
        and result266["final_subject_digest"] == PARENT_DIGEST,
        "positive_structural_variation": positive_a["status"] == "world-available"
        and positive_b["status"] == "world-available"
        and positive_a["available_world"]["world_id"] == PACKAGE_A["world_id"]
        and positive_b["available_world"]["world_id"] == PACKAGE_B["world_id"],
        "catalog_order_invariant": ordered == reversed_order,
        "lexical_unseen_selection": ordered["available_world"]["world_id"] == PACKAGE_A["world_id"],
        "seen_catalog_empty": scan_feed(seen, [PACKAGE_A, PACKAGE_B], p82.digest)["status"] == "empty",
        "active_offer_not_reoffered": scan_feed(offered, [PACKAGE_A], p82.digest)["status"] == "empty",
        "all_malformed_fail_closed": all(row["status"] == "invalid-feed" for row in invalid),
        "duplicate_id_fails_closed": duplicate == {"status": "invalid-feed", "reason": "duplicate-world-id"},
        "matched_visibility_gain": old_provider["result"] == "empty"
        and heldout["status"] == "world-available"
        and heldout["available_world"]["world_id"] == HELDOUT["world_id"],
        "false_external_authorities": not any(
            heldout[key]
            for key in (
                "selection_authority",
                "scoring_authority",
                "admission_authority",
                "outcome_authority",
                "actor_authority",
            )
        ),
        "scanner_exactly_retained": successor["active_standing_world_provider"]["scanner_source_digest"] == p82.digest(SCANNER_SOURCE)
        and successor["active_standing_world_provider"]["logical_feed_root"] == "$WORLD_FEED",
        "operational_core_preserved": operational_core(parent) == operational_core(successor),
        "current_correction_route_preserved": base260.needs_refresh(successor, p82)
        and base261.challenger(successor, p82) == "outward-correct",
        "successor_conformant": runtime.identity_conforms(successor),
        "route_floor_16_of_16": route["pass_count"] == 16,
        "identity_floor_18_of_18": identity["pass_count"] == 18,
    }
    checks["passed"] = all(checks.values())
    fixtures = {
        "authority": AUTHORITY + "-preflight",
        "source_subject_digest": parent["artifact_digest"],
        "checks": checks,
    }
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0267 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    result = {
        "authority": AUTHORITY,
        "source_subject_digest": parent["artifact_digest"],
        "checks": checks,
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": successor["continuation"]["status"] if checks["passed"] else parent["continuation"]["status"],
        "final_subject_digest": successor["artifact_digest"] if checks["passed"] else parent["artifact_digest"],
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", successor if checks["passed"] else parent)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
