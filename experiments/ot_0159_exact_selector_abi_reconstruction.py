from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0158_dependency_aware_mechanism_selector.py"
BASE_SHA256 = "a25f769229d34e7f1871b2adc12d1f95071eae4477e3b8ee96c5026d127feba7"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
SOURCE_SHA256 = "64bbbf05603bf23e47678d6d11b24de62619a8fcc5b7653c1a12c0cf5663f518"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0158 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0159_frozen_ot0158", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
base = previous.base
prior131 = previous.prior131


def constrained_import(
    name: str,
    globals_value: dict[str, Any] | None = None,
    locals_value: dict[str, Any] | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
):
    del globals_value, locals_value
    if name == "re" and level == 0 and not fromlist:
        return re
    raise ImportError("selector source may import only re")


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
    builtins = {**previous.SAFE_BUILTINS, "__import__": constrained_import}
    namespace: dict[str, Any] = {"__builtins__": builtins}
    try:
        exec(compile(tree, "<mechanism-selector>", "exec"), namespace)
    except Exception:
        return None
    function = namespace.get("choose_mechanism")
    return function if callable(function) else None


def exact_actor_audit_clean(audit: dict[str, Any]) -> bool:
    return bool(
        audit.get("changed_paths") == ["selector.py"]
        and audit.get("reported_paths") == ["selector.py"]
        and audit.get("exact_changes")
        and audit.get("truthful")
        and audit.get("denial_classification_v2", {}).get("accepted")
        and audit.get("denial_classification_v2", {}).get("classification") == "clean"
        and audit.get("trace_regime", {}).get("accepted")
        and audit.get("trace_regime", {}).get("classification") == "clean-complete"
    )


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
    run = (args.evidence_root or store / "runs/OT-0159").resolve()

    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = previous.load_artifact(
        p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json"
    )
    failure = previous.load_artifact(
        p82, repo, store, "OT-0157", "property-only-selection-falsifier-aggregate.json"
    )
    rejected = previous.load_artifact(
        p82, repo, store, "OT-0158", "dependency-aware-mechanism-selector-aggregate.json"
    )
    source_manifest, source_path = p82.materialize(
        repo, store, "OT-0158", "exact-public-valid-selector-source.json"
    )
    source = source_path.read_text()
    audit_path = store / "runs/OT-0158/dependency-aware-mechanism-selector-corrector/actor-audit.json"
    audit = json.loads(audit_path.read_text())
    public, hidden = previous.portfolios(parent["active_developmental_stake"])
    old_public = previous.evaluate(previous.property_only, public)
    old_hidden = previous.evaluate(previous.property_only, hidden)

    selector = load_selector(source)
    bad_sources = {
        "other_import": "import os\ndef choose_mechanism(stake, candidates):\n    return None\n",
        "from_import": "from re import findall\ndef choose_mechanism(stake, candidates):\n    return None\n",
        "mixed_import": "import re, os\ndef choose_mechanism(stake, candidates):\n    return None\n",
        "alias_import": "import re as regex\ndef choose_mechanism(stake, candidates):\n    return None\n",
    }
    fixtures = {
        "checks": {
            "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST
            and parent["continuation"]["status"] == "open"
            and runtime.identity_conforms(parent),
            "failure_exact": failure["source_subject_digest"] == parent["artifact_digest"]
            and failure["property_only_selection_falsified"],
            "ot0158_rejected_before_hidden": rejected["selector"]["binding"] is None
            and rejected["hidden_world"] is None
            and rejected["observer_disposition"] == "rejected",
            "exact_source_identity": source_manifest["sha256"] == SOURCE_SHA256
            and hashlib.sha256(source.encode()).hexdigest() == SOURCE_SHA256,
            "exact_actor_audit_clean": exact_actor_audit_clean(audit),
            "exact_source_loads": selector is not None,
            "non_re_imports_rejected": all(load_selector(value) is None for value in bad_sources.values()),
            "old_selector_public_partial": old_public["pass_count"] == 2 and not old_public["passed"],
            "old_selector_hidden_balanced": old_hidden["pass_count"] == 3 and not old_hidden["passed"],
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
                    "old_public": old_public,
                    "old_hidden": old_hidden,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if fixtures["checks"]["passed"] else 2

    if run.exists():
        raise SystemExit("preserve existing OT-0159 evidence")
    run.mkdir(parents=True)
    (run / "fixture-conformance.json").write_text(json.dumps(fixtures, indent=2, sort_keys=True) + "\n")
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")

    public_result = previous.evaluate(selector, public)
    binding_body = {
        "authority": "ot-0158-bound-dependency-aware-mechanism-selector",
        "source_subject_digest": parent["artifact_digest"],
        "failure_receipt_digest": failure["receipt_digest"],
        "actor_patch_digest": audit["patch_digest"],
        "selector_source": source,
        "public_result": public_result,
    }
    binding = {**binding_body, "binding_digest": p82.digest(binding_body)} if public_result["passed"] else None
    hidden_result = previous.evaluate(selector, hidden) if binding else None
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

    property_control = previous.evaluate(previous.property_only, hidden)
    erased = copy.deepcopy(final)
    erased["active_developmental_mechanism_selector"] = None
    erased_choice = installed_choice(
        erased, parent["active_developmental_stake"], previous.CANDIDATES
    )
    installed_current_choice = installed_choice(
        final, parent["active_developmental_stake"], previous.CANDIDATES
    )
    checks = {
        "exact_source_and_audit_reused": fixtures["checks"]["exact_source_identity"]
        and fixtures["checks"]["exact_actor_audit_clean"],
        "constrained_importer_exact": fixtures["checks"]["exact_source_loads"]
        and fixtures["checks"]["non_re_imports_rejected"],
        "public_reconstructed_4_of_4": public_result["passed"] and public_result["pass_count"] == 4,
        "hidden_6_of_6": bool(world and world["result"]["passed"] and world["result"]["pass_count"] == 6),
        "old_selector_3_of_6": property_control["pass_count"] == 3 and not property_control["passed"],
        "selector_erasure_blocks_dependency_route": erased_choice is None,
        "installed_selector_routes_current_stake": installed_current_choice == "corrected-identity-gated-extension",
        "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"],
        "parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key != "artifact_digest"),
        "selector_installed": final.get("active_developmental_mechanism_selector") == binding,
        "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open",
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0159-exact-selector-abi-reconstruction",
        "source_subject_digest": parent["artifact_digest"],
        "source_selector_sha256": SOURCE_SHA256,
        "apparatus_repair": {
            "admitted_import": "import re",
            "rejected_import_cases": sorted(bad_sources),
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
