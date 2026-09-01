from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0159_exact_selector_abi_reconstruction.py"
BASE_SHA256 = "6e5f96afcde808f5cc4332bdb73b5e26d46c61b851de8148ca2ca1681e7fd193"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
SOURCE_SHA256 = "64bbbf05603bf23e47678d6d11b24de62619a8fcc5b7653c1a12c0cf5663f518"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0159 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0160_frozen_ot0159", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
selector_base = previous.previous
base = previous.base


def load_selector(source: str) -> Callable[..., Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    exact_import = (
        len(imports) == 1
        and isinstance(imports[0], ast.Import)
        and len(imports[0].names) == 1
        and imports[0].names[0].name == "re"
        and imports[0].names[0].asname is None
    )
    forbidden = (ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.Try, ast.Raise)
    if not exact_import or any(isinstance(node, forbidden) for node in ast.walk(tree)):
        return None
    if any(isinstance(node, ast.Name) and node.id.startswith("__") for node in ast.walk(tree)):
        return None
    if any(isinstance(node, ast.Attribute) and node.attr.startswith("__") for node in ast.walk(tree)):
        return None
    builtins = {
        **selector_base.SAFE_BUILTINS,
        "__import__": previous.constrained_import,
        "next": next,
    }
    namespace: dict[str, Any] = {"__builtins__": builtins}
    try:
        exec(compile(tree, "<mechanism-selector>", "exec"), namespace)
    except Exception:
        return None
    function = namespace.get("choose_mechanism")
    return function if callable(function) else None


def installed_choice(subject: dict[str, Any], stake: dict[str, Any], candidates: list[dict[str, Any]]) -> str | None:
    binding = subject.get("active_developmental_mechanism_selector")
    if not isinstance(binding, dict):
        return None
    selector = load_selector(binding.get("selector_source", ""))
    if selector is None:
        return None
    try:
        return selector(copy.deepcopy(stake), copy.deepcopy(candidates))
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0160").resolve()

    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(
        p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json"
    )
    failure = selector_base.load_artifact(
        p82, repo, store, "OT-0157", "property-only-selection-falsifier-aggregate.json"
    )
    rejected_158 = selector_base.load_artifact(
        p82, repo, store, "OT-0158", "dependency-aware-mechanism-selector-aggregate.json"
    )
    rejected_159 = selector_base.load_artifact(
        p82, repo, store, "OT-0159", "exact-selector-abi-reconstruction-aggregate.json"
    )
    diagnostic_159 = selector_base.load_artifact(
        p82, repo, store, "OT-0159", "selector-runtime-abi-diagnostic.json"
    )
    source_manifest, source_path = p82.materialize(
        repo, store, "OT-0158", "exact-public-valid-selector-source.json"
    )
    source = source_path.read_text()
    audit_path = store / "runs/OT-0158/dependency-aware-mechanism-selector-corrector/actor-audit.json"
    audit = json.loads(audit_path.read_text())
    public, hidden = selector_base.portfolios(parent["active_developmental_stake"])
    old_public = selector_base.evaluate(selector_base.property_only, public)
    old_hidden = selector_base.evaluate(selector_base.property_only, hidden)
    rejected_public = selector_base.evaluate(previous.load_selector(source), public)
    selector = load_selector(source)
    corrected_public = selector_base.evaluate(selector, public)
    bad_sources = {
        "other_import": "import os\ndef choose_mechanism(stake, candidates):\n    return None\n",
        "from_import": "from re import findall\ndef choose_mechanism(stake, candidates):\n    return None\n",
        "mixed_import": "import re, os\ndef choose_mechanism(stake, candidates):\n    return None\n",
        "alias_import": "import re as regex\ndef choose_mechanism(stake, candidates):\n    return None\n",
    }
    base_runtime_names = {*selector_base.SAFE_BUILTINS, "__import__"}
    corrected_runtime_names = {*base_runtime_names, "next"}
    fixtures = {
        "checks": {
            "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST
            and parent["continuation"]["status"] == "open"
            and runtime.identity_conforms(parent),
            "failure_exact": failure["source_subject_digest"] == parent["artifact_digest"]
            and failure["property_only_selection_falsified"],
            "prior_rejections_preserved": rejected_158["hidden_world"] is None
            and rejected_159["hidden_world"] is None
            and rejected_159["observer_disposition"] == "rejected",
            "ot0159_diagnosis_exact": diagnostic_159["exception_type"] == "NameError"
            and diagnostic_159["exception_message"] == "name 'next' is not defined"
            and not diagnostic_159["hidden_portfolio_opened"],
            "exact_source_identity": source_manifest["sha256"] == SOURCE_SHA256
            and hashlib.sha256(source.encode()).hexdigest() == SOURCE_SHA256,
            "exact_actor_audit_clean": previous.exact_actor_audit_clean(audit),
            "ot0159_public_reproduced_0_of_4": rejected_public["pass_count"] == 0
            and not rejected_public["passed"],
            "corrected_public_4_of_4": corrected_public["pass_count"] == 4
            and corrected_public["passed"],
            "runtime_delta_exactly_next": corrected_runtime_names - base_runtime_names == {"next"},
            "non_re_imports_rejected": all(load_selector(value) is None for value in bad_sources.values()),
            "old_selector_public_partial": old_public["pass_count"] == 2 and not old_public["passed"],
            "old_selector_hidden_balanced": old_hidden["pass_count"] == 3 and not old_hidden["passed"],
            "authorized_selector_replacement_explicit": parent.get("active_developmental_mechanism_selector") is None,
        }
    }
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "base_sha256": BASE_SHA256,
                    "source_sha256": SOURCE_SHA256,
                    "fixtures": fixtures,
                    "rejected_public": rejected_public,
                    "corrected_public": corrected_public,
                    "old_public": old_public,
                    "old_hidden": old_hidden,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if fixtures["checks"]["passed"] else 2

    if run.exists():
        raise SystemExit("preserve existing OT-0160 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    public_result = selector_base.evaluate(selector, public)
    binding_body = {
        "authority": "ot-0158-bound-dependency-aware-mechanism-selector",
        "source_subject_digest": parent["artifact_digest"],
        "failure_receipt_digest": failure["receipt_digest"],
        "actor_patch_digest": audit["patch_digest"],
        "selector_source": source,
        "public_result": public_result,
    }
    binding = {**binding_body, "binding_digest": p82.digest(binding_body)} if public_result["passed"] else None
    hidden_result = selector_base.evaluate(selector, hidden) if binding else None
    world = None
    if hidden_result:
        world_body = {
            "authority": "ot-0158-independent-selector-consequence",
            "selector_binding_digest": binding["binding_digest"],
            "hidden_portfolios_digest": p82.digest(hidden),
            "result": hidden_result,
        }
        world = {**world_body, "receipt_digest": p82.digest(world_body)}
        (run / "sealed-hidden-selector-world.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")

    final = parent
    capability = None
    if world and world["result"]["passed"]:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        capability_body = {
            "authority": "ot-0158-dependency-aware-selector-capability",
            "selector_binding_digest": binding["binding_digest"],
            "world_receipt_digest": world["receipt_digest"],
        }
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_mechanism_selector_capabilities"] = [
            *child.get("developmental_mechanism_selector_capabilities", []),
            capability,
        ]
        child["active_developmental_mechanism_selector"] = binding
        final = p82.seal(child)

    property_control = selector_base.evaluate(selector_base.property_only, hidden)
    erased = copy.deepcopy(final)
    erased["active_developmental_mechanism_selector"] = None
    erased_choice = installed_choice(erased, parent["active_developmental_stake"], selector_base.CANDIDATES)
    installed_current_choice = installed_choice(final, parent["active_developmental_stake"], selector_base.CANDIDATES)
    authorized_changes = {
        "artifact_digest",
        "active_developmental_mechanism_selector",
        "developmental_mechanism_selector_capabilities",
    }
    retained_parent = all(final.get(key) == parent.get(key) for key in parent if key not in authorized_changes)
    expected_capabilities = [*parent.get("developmental_mechanism_selector_capabilities", []), capability]
    checks = {
        "exact_source_and_audit_reused": fixtures["checks"]["exact_source_identity"]
        and fixtures["checks"]["exact_actor_audit_clean"],
        "runtime_delta_exactly_next": fixtures["checks"]["runtime_delta_exactly_next"],
        "public_reconstructed_4_of_4": public_result["passed"] and public_result["pass_count"] == 4,
        "hidden_6_of_6": bool(world and world["result"]["passed"] and world["result"]["pass_count"] == 6),
        "old_selector_3_of_6": property_control["pass_count"] == 3 and not property_control["passed"],
        "selector_erasure_blocks_dependency_route": erased_choice is None,
        "installed_selector_routes_current_stake": installed_current_choice == "corrected-identity-gated-extension",
        "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"],
        "unauthorized_parent_state_retained": retained_parent,
        "selector_capability_appended_exactly": capability is not None
        and final.get("developmental_mechanism_selector_capabilities") == expected_capabilities,
        "selector_installed": binding is not None and final.get("active_developmental_mechanism_selector") == binding,
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0160-complete-selector-runtime-reconstruction",
        "source_subject_digest": parent["artifact_digest"],
        "source_selector_sha256": SOURCE_SHA256,
        "apparatus_repair": {
            "runtime_builtin_added": "next",
            "authorized_replacement_field": "active_developmental_mechanism_selector",
            "authorized_append_field": "developmental_mechanism_selector_capabilities",
            "new_actor_count": 0,
        },
        "reconstructed_binding": binding,
        "public_result": public_result,
        "hidden_world": world,
        "post_seal_property_only_control": property_control,
        "selector_erasure_control": {"observed": erased_choice, "passed": erased_choice is None},
        "checks": checks,
        "selector_reconstruction_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": final["continuation"]["status"],
        "final_subject_digest": final["artifact_digest"],
        "next_opening": final["continuation"]["next_opening"],
        "fresh_actor_count": 0,
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
