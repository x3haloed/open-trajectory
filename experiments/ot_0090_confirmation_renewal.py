from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
PRIOR_PATH = ROOT / "ot_0089_derived_liveness.py"
PRIOR_SHA256 = "e2897f8b67601f8970b1744e9e828148bb68d3c25049d942ed17d67e715dc9c0"
PARENT_DIGEST = "b3cd03e3ea34f60514d80d20b02f3f11ceaae56ab5139ad52b120c06ac12e626"
INHERITED_OPENING = "Verify coverage selection against realized coverage-weighted scores, including tie behavior."
COVERAGE_SOURCE_DIGEST = "0eeedd10d43508a69a6eafa0531eccb37f6058f153988b52c70cde89e3443fa3"
ACTOR_SCHEMA = REPO / "spec/ot-0090-successor.schema.json"
PLACEHOLDER = "__REPLACE__"
VERIFIER_KEYS = {"selected_id", "max_score", "maximizing_ids", "tie_rule_preserved"}


WORLD_SOURCE = '''def score_coverage(context, option):
    """Realized value after contributor coverage and coordination cost."""
    return option["base_value"] + context["coverage_weight"] * option["coverage_units"] - option["coordination_cost"]
'''

VERIFIER_SEED = '''from studio.coverage import choose_coverage
from studio.world import score_coverage


def assess(context, options):
    """Return exactly selected_id, max_score, maximizing_ids, tie_rule_preserved.

    maximizing_ids is the sorted list of ids tied at the greatest realized
    score. tie_rule_preserved is true exactly when the selected id is the
    greatest id among those maxima. Values must be JSON-compatible.
    """
    raise NotImplementedError("implement the retained opening")
'''

REFERENCE_VERIFIER = '''from studio.coverage import choose_coverage
from studio.world import score_coverage


def assess(context, options):
    """Verify realized-score maximization and retained option-id tie breaking."""
    selected_id = choose_coverage(context, options)
    scores = {option["id"]: score_coverage(context, option) for option in options}
    max_score = max(scores.values())
    maximizing_ids = sorted(option_id for option_id, score in scores.items() if score == max_score)
    return {
        "selected_id": selected_id,
        "max_score": max_score,
        "maximizing_ids": maximizing_ids,
        "tie_rule_preserved": selected_id == maximizing_ids[-1],
    }
'''


def option(option_id: str, base: float, coverage: float, cost: float = 0.0) -> dict[str, Any]:
    return {"id": option_id, "base_value": base, "coverage_units": coverage, "coordination_cost": cost}


PUBLIC_CASES = [
    {"case_id": "public-unique", "context": {"coverage_weight": 2.0}, "options": [option("local", 12, 1), option("broad", 8, 4)]},
    {"case_id": "public-tie-forward", "context": {"coverage_weight": 2.0}, "options": [option("amber", 10, 2), option("violet", 8, 3)]},
    {"case_id": "public-tie-reversed", "context": {"coverage_weight": 2.0}, "options": [option("violet", 8, 3), option("amber", 10, 2)]},
]

HIDDEN_CASES = [
    {"case_id": "hidden-two-way", "context": {"coverage_weight": 3.0}, "options": [option("quartz", 5, 4), option("jade", 8, 3)]},
    {"case_id": "hidden-three-way", "context": {"coverage_weight": 2.0}, "options": [option("zinc", 4, 5), option("amber", 10, 2), option("cobalt", 8, 3)]},
    {"case_id": "hidden-near-tie", "context": {"coverage_weight": 1.0}, "options": [option("zulu", 10.0, 0), option("alpha", 10.1, 0)]},
    {"case_id": "hidden-cost-tie", "context": {"coverage_weight": 2.0}, "options": [option("north", 9, 4, 1), option("south", 10, 3, 0)]},
]

OBSERVE_SOURCE = '''import json
from studio.coverage import choose_coverage
from studio.public_cases import CASES
from studio.world import score_coverage

for case in CASES:
    context, options = case["context"], case["options"]
    scores = {item["id"]: score_coverage(context, item) for item in options}
    print(json.dumps({"case_id": case["case_id"], "input_order": [item["id"] for item in options],
                      "scores": scores, "selected_id": choose_coverage(context, options)}, sort_keys=True))
'''

PUBLIC_TEST_SOURCE = '''import unittest
from studio.coverage import choose_coverage
from studio.public_cases import CASES
from studio.world import score_coverage
from verify_coverage import assess


class PublicTests(unittest.TestCase):
    def test_policy_and_verifier_match_realized_oracle(self):
        for case in CASES:
            context, options = case["context"], case["options"]
            oracle = max(options, key=lambda item: (score_coverage(context, item), item["id"]))["id"]
            self.assertEqual(choose_coverage(context, options), oracle)
            report = assess(context, options)
            self.assertEqual(set(report), {"selected_id", "max_score", "maximizing_ids", "tie_rule_preserved"})
            self.assertEqual(report["selected_id"], oracle)
            self.assertTrue(report["tie_rule_preserved"])


if __name__ == "__main__":
    unittest.main()
'''

EVALUATOR_SOURCE = '''import importlib.util
import json
import sys
from pathlib import Path
from studio.coverage import choose_coverage
from studio.world import score_coverage

config = json.loads(Path("_config.json").read_text())
spec = importlib.util.spec_from_file_location("candidate_verifier", Path(config["verifier"]))
module = importlib.util.module_from_spec(spec)
sys.modules["candidate_verifier"] = module
spec.loader.exec_module(module)
rows = []
valid = True
for case in config["cases"]:
    context, options = case["context"], case["options"]
    scores = {item["id"]: score_coverage(context, item) for item in options}
    max_score = max(scores.values())
    maximizing_ids = sorted(key for key, value in scores.items() if value == max_score)
    oracle = maximizing_ids[-1]
    try:
        report = module.assess(context, options)
        row_valid = (set(report) == {"selected_id", "max_score", "maximizing_ids", "tie_rule_preserved"}
                     and report["selected_id"] == choose_coverage(context, options) == oracle
                     and isinstance(report["max_score"], (int, float)) and abs(report["max_score"] - max_score) < 1e-9
                     and report["maximizing_ids"] == maximizing_ids
                     and report["tie_rule_preserved"] is True)
        rows.append({"case_id": case["case_id"], "valid": row_valid, "selected_id": report.get("selected_id"),
                     "oracle": oracle, "maximizing_ids": report.get("maximizing_ids")})
        valid = valid and row_valid
    except Exception as error:
        valid = False
        rows.append({"case_id": case["case_id"], "valid": False, "error_type": type(error).__name__})
print(json.dumps({"valid": valid, "rows": rows}, sort_keys=True))
'''


def load_prior():
    if hashlib.sha256(PRIOR_PATH.read_bytes()).hexdigest() != PRIOR_SHA256:
        raise RuntimeError("OT-0089 implementation identity changed")
    name = "ot0090_frozen_ot0089"
    spec = importlib.util.spec_from_file_location(name, PRIOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def prior82(prior89):
    prior87 = prior89.load_prior(REPO)
    prior86 = prior87.load_prior(REPO)
    prior85 = prior86.load_prior(REPO)
    prior84 = prior85.load_prior(REPO)
    prior83 = prior84.load_prior(REPO)
    return prior83.load_prior(REPO)


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = p82.materialize(repo, store, "OT-0089", "open-subject-after-derived-liveness.json")
    return json.loads(path.read_text())


def retained_coverage(parent: dict[str, Any]) -> dict[str, Any]:
    matches = [row for row in parent.get("environmental_capabilities", []) if row.get("target_path") == "studio/coverage.py"]
    if not matches:
        raise RuntimeError("coverage capability missing")
    return matches[-1]


def successor_template(prior89) -> dict[str, str]:
    return prior89.successor_template()


def write_environment(root: Path, coverage_source: str, verifier_source: str = VERIFIER_SEED) -> None:
    files = {
        "studio/__init__.py": "",
        "studio/world.py": WORLD_SOURCE,
        "studio/coverage.py": coverage_source,
        "studio/public_cases.py": "CASES = " + repr(PUBLIC_CASES) + "\n",
        "verify_coverage.py": verifier_source,
        "observe.py": OBSERVE_SOURCE,
        "tests/__init__.py": "",
        "tests/test_public.py": PUBLIC_TEST_SOURCE,
    }
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def evaluate(p82, root: Path, verifier_source: str, cases: list[dict[str, Any]], evidence: Path, label: str) -> dict[str, Any]:
    workspace = evidence / label
    write_environment(workspace, (root / "studio/coverage.py").read_text(), verifier_source)
    (workspace / "_config.json").write_text(json.dumps({"cases": cases, "verifier": "verify_coverage.py"}, sort_keys=True) + "\n")
    (workspace / "_evaluate.py").write_text(EVALUATOR_SOURCE)
    completed = subprocess.run(["python3", "_evaluate.py"], cwd=workspace, text=True, capture_output=True, timeout=30)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result = {"valid": False, "rows": []}
    body = {"authority": "ot-0090-bound-coverage-verifier-evaluation", "cases_digest": p82.digest(cases),
            "verifier_digest": p82.digest(verifier_source), "returncode": completed.returncode,
            "stderr_digest": hashlib.sha256(completed.stderr.encode()).hexdigest(), "valid": completed.returncode == 0 and bool(result.get("valid")),
            "rows": result.get("rows", [])}
    return {**body, "receipt_digest": p82.digest(body)}


def fixture_conformance(prior89, p82, parent: dict[str, Any], root: Path) -> dict[str, Any]:
    capability = retained_coverage(parent)
    seed = root / "seed"
    write_environment(seed, capability["source"])
    observe = subprocess.run(["python3", "observe.py"], cwd=seed, text=True, capture_output=True, timeout=30)
    public_reference = evaluate(p82, seed, REFERENCE_VERIFIER, PUBLIC_CASES, root, "public-reference")
    hidden_reference = evaluate(p82, seed, REFERENCE_VERIFIER, HIDDEN_CASES, root, "hidden-reference")
    public_seed = evaluate(p82, seed, VERIFIER_SEED, PUBLIC_CASES, root, "public-placeholder")
    representative = prior89.representative_successor()
    distinct = {**representative, "next_opening": "Probe whether coordination cost creates a new coverage boundary."}
    result = {
        "parent_bound": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["next_opening"] == INHERITED_OPENING,
        "coverage_bound": capability["source_digest"] == COVERAGE_SOURCE_DIGEST and p82.digest(capability["source"]) == COVERAGE_SOURCE_DIGEST,
        "public_observation_passed": observe.returncode == 0 and len(observe.stdout.splitlines()) == len(PUBLIC_CASES),
        "public_reference": public_reference,
        "hidden_reference": hidden_reference,
        "placeholder_rejected": not public_seed["valid"],
        "successor_valid": prior89.valid_successor(distinct) and distinct["next_opening"] != INHERITED_OPENING,
        "actor_schema_digest": hashlib.sha256(ACTOR_SCHEMA.read_bytes()).hexdigest(),
    }
    result["passed"] = all((result["parent_bound"], result["coverage_bound"], result["public_observation_passed"],
                            public_reference["valid"], hidden_reference["valid"], result["placeholder_rejected"], result["successor_valid"]))
    return result


def actor_seed(prior89, run: Path, parent: dict[str, Any]) -> Path:
    seed = run / "successor-seed"
    seed.mkdir()
    capability = retained_coverage(parent)
    write_environment(seed, capability["source"])
    position = {"subject_digest": parent["artifact_digest"], "runtime": parent["runtime"],
                "continuation": parent["continuation"], "active_pursuit": parent["active_pursuit"],
                "unresolved": parent["unresolved"], "latest_actor_opening": parent["actor_originated_pursuit_openings"][-1]}
    (seed / "subject-position.json").write_text(json.dumps(position, indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening.json").write_text(json.dumps(successor_template(prior89), indent=2, sort_keys=True) + "\n")
    (seed / "successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(), indent=2, sort_keys=True) + "\n")
    (seed / "mutation-envelope.json").write_text(json.dumps({"editable": ["verify_coverage.py", "successor-opening.json"],
        "immutable": ["studio/coverage.py"], "source_subject_digest": parent["artifact_digest"]}, indent=2, sort_keys=True) + "\n")
    (seed / "README.md").write_text("Continue the exact subject's current opening through this complete public world. Preserve studio/coverage.py. Implement the visible verifier ABI, author a distinct substantive successor opening, run useful checks, inspect the exact diff, and leave hidden consequence to the world.\n")
    return seed


def promote(p82, parent: dict[str, Any], binding: dict[str, Any], world: dict[str, Any], audit: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    opening = binding["successor_opening"]
    body = {"authority": "world-promoted-confirmation-renewal", "source_subject_digest": parent["artifact_digest"],
            "binding_digest": binding["binding_digest"], "world_receipt_digest": world["receipt_digest"],
            "verifier_digest": binding["verifier_digest"]}
    receipt = {**body, "receipt_digest": p82.digest(body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["confirmation_receipts"] = [*child.get("confirmation_receipts", []), receipt]
    child["environmental_capabilities"] = [*child.get("environmental_capabilities", []),
        {"target_path": "verify_coverage.py", "target_symbol": "assess", "source": binding["verifier_source"],
         "source_digest": binding["verifier_digest"], "world_receipt_digest": world["receipt_digest"]}]
    child["actor_originated_pursuit_openings"] = [*child.get("actor_originated_pursuit_openings", []),
        {"authority": "fresh-confirmation-successor-opening", "binding_digest": binding["binding_digest"], "opening": opening}]
    child["tool_world_capabilities"] = [*child["tool_world_capabilities"],
        {"selected_area": "verify_coverage.py", "pursuit": opening["next_opening"], "patch_digest": audit["patch_digest"],
         "world_receipt_digest": world["receipt_digest"], "contact_program_digest": binding["verifier_digest"]}]
    child["active_pursuit"] = {"authority": "fresh-confirmation-successor-opening", "selected_area": "verify_coverage.py",
        "next_pursuit": opening["next_opening"], "world_receipt_digest": world["receipt_digest"]}
    child["continuation"] = {**child["continuation"], "status": "open", "next_opening": opening["next_opening"]}
    child["runtime"] = "sounding"
    child["unresolved"] = opening["continuation_after_contact"]
    return p82.seal(child), receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0090").resolve()
    prior89 = load_prior()
    p82 = prior82(prior89)
    runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    if runtime.seal(parent)["artifact_digest"] != parent["artifact_digest"] or not runtime.identity_conforms(parent):
        raise SystemExit("invalid OT-0089 parent")
    if args.preflight_only:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_conformance(prior89, p82, parent, Path(directory))
        result = {"parent_digest": parent["artifact_digest"], "prior_implementation_sha256": PRIOR_SHA256, "fixture_conformance": fixtures}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if fixtures["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0090 evidence")
    run.mkdir(parents=True)
    fixtures = fixture_conformance(prior89, p82, parent, run / "fixture-conformance")
    if not fixtures["passed"]:
        raise SystemExit("pre-actor conformance failed")
    context = runtime.Context(run, repo)
    started = time.time()
    seed = actor_seed(prior89, run, parent)
    prompt = "Continue the exact open subject through its current confirmation contact. Use ordinary tools, preserve the admitted coverage policy, implement the reusable verifier, author a distinct substantive next opening, run useful checks, inspect the exact diff, and return the required report."
    output, base_audit, workspace, _ = context.run_actor("successor", seed, ACTOR_SCHEMA, prompt)
    try:
        verifier_source = (workspace / "verify_coverage.py").read_text()
        opening = json.loads((workspace / "successor-opening.json").read_text())
        coverage_source = (workspace / "studio/coverage.py").read_text()
    except (OSError, json.JSONDecodeError):
        verifier_source, opening, coverage_source = "", None, ""
    compiled = subprocess.run(["python3", "-m", "py_compile", "verify_coverage.py"], cwd=workspace, capture_output=True)
    artifact_valid = bool(compiled.returncode == 0 and verifier_source != VERIFIER_SEED and prior89.valid_successor(opening)
                          and opening["next_opening"] != INHERITED_OPENING and p82.digest(coverage_source) == COVERAGE_SOURCE_DIGEST)
    audit = context.audit_actor("successor", output, base_audit, artifact_valid, ["successor-opening.json", "verify_coverage.py"])
    binding = None
    if audit["conformant"]:
        body = {"authority": "ot-0090-pre-hidden-confirmation-binding", "source_subject_digest": parent["artifact_digest"],
                "actor_patch_digest": audit["patch_digest"], "coverage_source_digest": p82.digest(coverage_source),
                "verifier_source": verifier_source, "verifier_digest": p82.digest(verifier_source), "successor_opening": opening}
        binding = {**body, "binding_digest": p82.digest(body)}
        (context.evidence("successor") / "bound-confirmation.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    public = evaluate(p82, workspace, verifier_source, PUBLIC_CASES, context.evidence("successor"), "public") if binding else None
    hidden = evaluate(p82, workspace, verifier_source, HIDDEN_CASES, context.evidence("successor"), "hidden") if binding else None
    admitted = bool(public and hidden and public["valid"] and hidden["valid"])
    world_body = {"authority": "ot-0090-sealed-confirmation-contact", "source_subject_digest": parent["artifact_digest"],
                  "binding_digest": binding["binding_digest"] if binding else None, "public": public, "hidden": hidden,
                  "developmentally_admitted": admitted}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    (context.evidence("successor") / "world-receipt.json").write_text(json.dumps(world, indent=2, sort_keys=True) + "\n")
    current, promotion = parent, None
    if admitted and binding:
        current, promotion = promote(p82, parent, binding, world, audit)
    operational = bool(promotion and runtime.identity_conforms(current) and current["runtime"] == "sounding"
                       and current["continuation"]["status"] == "open"
                       and current["continuation"]["next_opening"] == opening["next_opening"]
                       and len(current["environmental_capabilities"]) == len(parent["environmental_capabilities"]) + 1)
    result = {"authority": "ot-0090-confirmation-renewal-driver", "source_subject_digest": parent["artifact_digest"],
              "prior_implementation_sha256": PRIOR_SHA256, "fixture_conformance": fixtures, "output": output,
              "audit": audit, "binding": p82.compact(binding) if binding else None, "world": world,
              "promotion_receipt": promotion, "operational_transition_passed": operational,
              "observer_disposition": "promoted" if operational else "rejected",
              "subject_disposition": "open" if current["continuation"]["status"] == "open" else "lost",
              "final_subject_digest": current["artifact_digest"], "next_opening": current["continuation"]["next_opening"],
              "elapsed_seconds": round(time.time() - started, 3)}
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
