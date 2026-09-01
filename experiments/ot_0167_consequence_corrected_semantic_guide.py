from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0166_single_authority_semantic_guide_test.py"
BASE_SHA256 = "cd1ae5b33a635f7e1566be16cf32fe8d0e9a80f0c9e39d127644a403ebfcb136"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
PARENT_GUIDE_BINDING_DIGEST = "ebb819e30399dfce72457aa45c8af6a723e9952341b554c92b24ad26f96a02c2"
CORRECTION_SCHEMA = REPO / "spec/ot-0167-semantic-guide-correction.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0166 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0167_frozen_ot0166", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_base()
comparison_base = previous.comparison_base
guide_base = previous.guide_base


def hidden_cases(selector_base) -> list[dict[str, Any]]:
    c = selector_base.CANDIDATES
    stake = selector_base.stake
    return [
        {"case_id": "corrected-guide-restore-equivalence", "class": "dependency", "stake": stake("restore-equivalence", "continuity-under-reset", "Restore the previously admitted equivalence policy after reset and retain every trial it had already passed."), "candidates": [c[0], c[2], c[1], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "corrected-guide-amended-boundary", "class": "dependency", "stake": stake("amended-boundary", "correction-from-error", "Use the amended identity boundary to revise the stale choice while preserving all guarantees earned by that boundary."), "candidates": [c[2], c[0], c[3], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "corrected-guide-learned-filter", "class": "dependency", "stake": stake("learned-filter", "option-expansion", "Enumerate choices through the learned compatibility filter and keep its entire established regression suite."), "candidates": [c[1], c[3], c[2], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "corrected-guide-carry-membership-operation", "class": "dependency", "stake": stake("carry-membership-operation", "continuity-under-reset", "Carry the corrected membership operation through restart together with every certified outcome it already protects."), "candidates": [c[3], c[1], c[0], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "corrected-guide-repair-through-composition", "class": "dependency", "stake": stake("repair-through-composition", "correction-from-error", "Repair the decision through the accepted composed gate while preserving all prior passes and blocked cases."), "candidates": [c[0], c[3], c[2], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "corrected-guide-ordinary-retained-compatible-options", "class": "ordinary", "stake": stake("ordinary-retained-compatible-options", "option-expansion", "Return every retained compatible option that is currently unblocked."), "candidates": [c[3], c[0], c[1], c[2]], "expected": "viable-branch-carrier"},
        {"case_id": "corrected-guide-ordinary-learned-identity-flag", "class": "ordinary", "stake": stake("ordinary-learned-identity-flag", "correction-from-error", "Update one learned identity flag to the observed boolean."), "candidates": [c[1], c[2], c[0], c[3]], "expected": "prediction-corrector"},
        {"case_id": "corrected-guide-ordinary-membership-token", "class": "ordinary", "stake": stake("ordinary-membership-token", "continuity-under-reset", "Carry one corrected membership token across reset."), "candidates": [c[2], c[3], c[0], c[1]], "expected": "reset-carrier"},
        {"case_id": "corrected-guide-ordinary-equivalence-labels", "class": "ordinary", "stake": stake("ordinary-equivalence-labels", "option-expansion", "List every certified equivalence label that is currently permitted."), "candidates": [c[0], c[1], c[3], c[2]], "expected": "viable-branch-carrier"},
        {"case_id": "corrected-guide-ordinary-filter-checksum", "class": "ordinary", "stake": stake("ordinary-filter-checksum", "continuity-under-reset", "Preserve one accepted filter checksum after restart."), "candidates": [c[3], c[2], c[1], c[0]], "expected": "reset-carrier"},
    ]


def correction_seed(root: Path, parent: dict[str, Any], guide: str, known: list[dict[str, Any]], consequence: dict[str, Any], choices: dict[str, Any]) -> Path:
    seed = root / "guide-seed"
    seed.mkdir()
    guide_base.write_json(seed / "subject-position.json", {"source_subject_digest": parent["artifact_digest"], "active_developmental_stake": parent["active_developmental_stake"], "continuation": parent["continuation"]})
    guide_base.write_json(seed / "known-cases.json", known)
    guide_base.write_json(seed / "guide-consequence.json", consequence)
    guide_base.write_json(seed / "active-choice-rationales.json", {key: value["choice"] for key, value in choices["active"].items()})
    guide_base.write_json(seed / "erased-choice-rationales.json", {key: value["choice"] for key, value in choices["erased"].items()})
    guide_base.write_json(seed / "mutation-envelope.json", {"editable": ["selection-guide.md"], "immutable": ["subject-position.json", "known-cases.json", "guide-consequence.json", "active-choice-rationales.json", "erased-choice-rationales.json"]})
    (seed / "selection-guide.md").write_text(guide)
    (seed / "README.md").write_text(
        "Correct the retained semantic selection guide from its objective sole-stake consequence. Edit only selection-guide.md and keep it at most 5,000 UTF-8 bytes. "
        "Preserve its demonstrated dependency gain, but prevent false overrides by requiring the active stake itself to explicitly depend on a prior composed mechanism and its earned floor. "
        "Never infer an unstated prior composition, history, or floor from cue words, a single value/token/flag/checksum, or an ordinary current list. "
        "Inspect the complete known cases and rationales, inspect the exact diff, and report truthfully.\n"
    )
    return seed


def run_choices(context, prior131, p82, run: Path, staging_name: str, label_prefix: str, selector_base, parent: dict[str, Any], portfolio: list[dict[str, Any]], branches: list[tuple[str, str | None, str | None]]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    staging = run / staging_name
    staging.mkdir()
    choices: dict[str, dict[str, Any]] = {name: {} for name, _, _ in branches}
    audits = []
    for index, case in enumerate(portfolio):
        order = branches if index % 2 == 0 else list(reversed(branches))
        for branch, guide, guide_digest in order:
            label = f"{label_prefix}-{index + 1:02d}-{branch}"
            root = staging / label
            root.mkdir()
            seed = previous.choice_seed(root, selector_base, parent, case, guide)
            output, base_audit, workspace, _ = context.run_actor(label, seed, guide_base.CHOICE_SCHEMA, (seed / "README.md").read_text().strip())
            try:
                choice = json.loads((workspace / "choice.json").read_text())
                immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
                immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
            except (OSError, json.JSONDecodeError, KeyError):
                choice, immutable_ok = None, False
            ids = {row["mechanism_id"] for row in case["candidates"]}
            valid = bool(isinstance(choice, dict) and set(choice) == {"mechanism_id", "rationale"} and choice.get("mechanism_id") in ids and isinstance(choice.get("rationale"), str) and choice["rationale"].strip() and immutable_ok and output and output.get("mechanism_id") == choice["mechanism_id"])
            audit = context.audit_actor(label, output, base_audit, valid, ["choice.json"])
            audits.append(audit)
            body = {"authority": "ot-0167-bound-semantic-guide-choice", "source_subject_digest": parent["artifact_digest"], "projection_digest": p82.digest(previous.subject_projection(parent, case)), "guide_binding_digest": guide_digest, "actor_patch_digest": audit.get("patch_digest"), "mechanism_id": choice.get("mechanism_id") if isinstance(choice, dict) else None}
            choices[branch][case["case_id"]] = {"binding": {**body, "binding_digest": p82.digest(body)} if valid and prior131.audit_accepted(audit) else None, "output": output, "audit": audit, "choice": choice}
    return choices, audits


def score_choices(choices: dict[str, dict[str, Any]], branch: str, portfolio: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in portfolio:
        binding = choices.get(branch, {}).get(case["case_id"], {}).get("binding")
        if not binding:
            continue
        observed = binding["mechanism_id"]
        rows.append({"case_id": case["case_id"], "class": case["class"], "observed": observed, "expected": case["expected"], "passed": observed == case["expected"]})
    return comparison_base.scored(rows)


def main() -> int:
    selector_lineage = guide_base.load_base()
    selector_base = selector_lineage.selector_base
    base = selector_lineage.base
    prior131 = selector_lineage.prior131
    base130 = selector_lineage.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0167").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    prior_result = selector_base.load_artifact(p82, repo, store, "OT-0166", "single-authority-semantic-guide-test-aggregate.json")
    lexical_result = selector_base.load_artifact(p82, repo, store, "OT-0162", "relational-dependency-selector-correction-aggregate.json")
    parent_binding = prior_result["guide_binding"]
    parent_guide = parent_binding["guide_text"]
    known = previous.cases(parent, selector_base)
    hidden = hidden_cases(selector_base)
    fixtures = {"checks": {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "exact_parent_guide": parent_binding["binding_digest"] == PARENT_GUIDE_BINDING_DIGEST,
        "causal_gain_and_harm_exact": prior_result["world"]["active_result"]["pass_count"] == 8 and prior_result["world"]["active_result"]["dependency_pass_count"] == 5 and prior_result["world"]["active_result"]["ordinary_pass_count"] == 3 and prior_result["world"]["erased_result"]["pass_count"] == 6,
        "known_exact_10": len(known) == 10,
        "hidden_balanced": len(hidden) == 10 and sum(row["class"] == "dependency" for row in hidden) == 5 and sum(row["class"] == "ordinary" for row in hidden) == 5,
        "hidden_ids_fresh": not ({row["case_id"] for row in hidden} & {row["case_id"] for row in known}),
        "schemas_present": CORRECTION_SCHEMA.is_file() and guide_base.CHOICE_SCHEMA.is_file(),
    }}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "known_digest": p82.digest(known), "hidden_digest": p82.digest(hidden)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0167 evidence")
    run.mkdir(parents=True)
    guide_base.write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))

    correction_root = run / "guide-correction-staging"
    correction_root.mkdir()
    seed = correction_seed(correction_root, parent, parent_guide, known, prior_result["world"], prior_result["choice_bindings"])
    correction_label = "semantic-guide-consequence-corrector"
    output, base_audit, workspace, _ = context.run_actor(correction_label, seed, CORRECTION_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        corrected_guide = (workspace / "selection-guide.md").read_text()
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        corrected_guide, immutable_ok = "", False
    correction_valid = bool(200 <= len(corrected_guide.encode()) <= 5000 and corrected_guide != parent_guide and immutable_ok and output and output.get("action") == "correct-semantic-selection-guide")
    correction_audit = context.audit_actor(correction_label, output, base_audit, correction_valid, ["selection-guide.md"])
    provisional_binding = None
    if correction_valid and prior131.audit_accepted(correction_audit):
        body = {"authority": "ot-0167-provisional-corrected-semantic-guide", "source_subject_digest": parent["artifact_digest"], "parent_guide_binding_digest": parent_binding["binding_digest"], "contradiction_receipt_digest": prior_result["world"]["receipt_digest"], "actor_patch_digest": correction_audit["patch_digest"], "guide_text": corrected_guide}
        provisional_binding = {**body, "binding_digest": p82.digest(body)}

    public_choices, public_audits = ({"corrected": {}}, [])
    public_result = comparison_base.scored([])
    corrected_binding = None
    if provisional_binding:
        public_choices, public_audits = run_choices(context, prior131, p82, run, "known-choice-staging", "known-guide-choice", selector_base, parent, known, [("corrected", corrected_guide, provisional_binding["binding_digest"])])
        public_result = score_choices(public_choices, "corrected", known)
        if public_result["pass_count"] == 10 and len(public_audits) == 10 and all(prior131.audit_accepted(audit) for audit in public_audits):
            body = {"authority": "ot-0167-bound-consequence-corrected-semantic-guide", "provisional_binding_digest": provisional_binding["binding_digest"], "source_subject_digest": parent["artifact_digest"], "parent_guide_binding_digest": parent_binding["binding_digest"], "contradiction_receipt_digest": prior_result["world"]["receipt_digest"], "actor_patch_digest": correction_audit["patch_digest"], "guide_text": corrected_guide, "known_result": public_result}
            corrected_binding = {**body, "binding_digest": p82.digest(body)}

    hidden_choices: dict[str, dict[str, Any]] = {"corrected": {}, "unchanged": {}}
    hidden_audits: list[dict[str, Any]] = []
    corrected_hidden = unchanged_hidden = comparison_base.scored([])
    if corrected_binding:
        hidden_choices, hidden_audits = run_choices(context, prior131, p82, run, "hidden-choice-staging", "hidden-guide-choice", selector_base, parent, hidden, [("corrected", corrected_guide, corrected_binding["binding_digest"]), ("unchanged", parent_guide, parent_binding["binding_digest"])])
        corrected_hidden = score_choices(hidden_choices, "corrected", hidden)
        unchanged_hidden = score_choices(hidden_choices, "unchanged", hidden)
    world_body = {"authority": "ot-0167-independent-corrected-semantic-guide-consequence", "corrected_guide_binding_digest": corrected_binding["binding_digest"] if corrected_binding else None, "unchanged_guide_binding_digest": parent_binding["binding_digest"], "hidden_digest": p82.digest(hidden), "corrected_result": corrected_hidden, "unchanged_result": unchanged_hidden}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    guide_base.write_json(run / "sealed-corrected-semantic-guide-world.json", world)
    advantage = corrected_hidden["pass_count"] - unchanged_hidden["pass_count"]
    promoted = bool(corrected_binding and corrected_hidden["pass_count"] == 10 and corrected_hidden["dependency_pass_count"] == 5 and corrected_hidden["ordinary_pass_count"] == 5 and unchanged_hidden["pass_count"] <= 8 and advantage >= 2 and len(hidden_audits) == 20 and all(prior131.audit_accepted(audit) for audit in hidden_audits))
    final = parent
    if promoted:
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        selector_body = {**corrected_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digest": world["receipt_digest"]}
        selector_body.pop("binding_digest", None)
        active_selector = {**selector_body, "binding_digest": p82.digest(selector_body)}
        correction_body = {"authority": "ot-0167-semantic-guide-correction-ancestry", "parent_guide": parent_binding, "corrected_guide_binding_digest": corrected_binding["binding_digest"], "contradiction_receipt_digest": prior_result["world"]["receipt_digest"], "failed_lexical_parent_binding_digest": lexical_result["correction"]["binding"]["binding_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0167-consequence-corrected-semantic-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), corrected_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        final = p82.seal(child)
    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "developmental_semantic_selection_guides", "developmental_mechanism_selector_capabilities", "developmental_mechanism_selector_corrections"}
    current_public = next((row for row in public_result["rows"] if row["case_id"] == "sole-current-stake"), None)
    checks = {"fresh_guide_corrector_accepted": bool(provisional_binding and prior131.audit_accepted(correction_audit)), "guide_changed": corrected_guide != parent_guide, "known_10_of_10": public_result["pass_count"] == 10, "ten_known_actors_accepted": len(public_audits) == 10 and all(prior131.audit_accepted(audit) for audit in public_audits), "corrected_hidden_10_of_10": corrected_hidden["pass_count"] == 10, "corrected_dependencies_5_of_5": corrected_hidden["dependency_pass_count"] == 5, "corrected_ordinary_5_of_5": corrected_hidden["ordinary_pass_count"] == 5, "unchanged_at_most_8_of_10": unchanged_hidden["pass_count"] <= 8, "corrected_advantage_at_least_2": advantage >= 2, "twenty_hidden_actors_accepted": len(hidden_audits) == 20 and all(prior131.audit_accepted(audit) for audit in hidden_audits), "current_stake_routes_to_extension": bool(current_public and current_public["passed"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "corrected_semantic_selector_installed": final.get("active_developmental_mechanism_selector", {}).get("selector_kind") == "fresh-actor-semantic-guide", "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0167-consequence-corrected-semantic-guide", "source_subject_digest": parent["artifact_digest"], "correction": {"output": output, "audit": correction_audit, "provisional_binding": provisional_binding, "binding": corrected_binding, "known_choices": public_choices, "known_result": public_result}, "hidden_choices": hidden_choices, "world": world, "checks": checks, "semantic_guide_correction_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 31}
    result["receipt_digest"] = p82.digest(result)
    guide_base.write_json(run / "aggregate.json", result)
    guide_base.write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
