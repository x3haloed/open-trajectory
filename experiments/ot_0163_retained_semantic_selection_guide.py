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
BASE_PATH = ROOT / "ot_0162_relational_dependency_selector_correction.py"
BASE_SHA256 = "7173d89d3d862b315e5eac39113c71b72e5f9deb01fc6e16aa68e50a7110ab18"
PARENT_DIGEST = "11939f321c268875791ffcc6c6d0b0522d003477d61a72f58e5de1e6e403dbdd"
GUIDE_SCHEMA = REPO / "spec/ot-0163-semantic-guide.schema.json"
CHOICE_SCHEMA = REPO / "spec/ot-0163-semantic-choice.schema.json"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0162 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0163_frozen_ot0162", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = None


def selection_requests(parent: dict[str, Any], selector_base) -> list[dict[str, Any]]:
    c = selector_base.CANDIDATES
    stake = selector_base.stake
    return [
        {"case_id": "semantic-current-carried-stake", "class": "dependency", "stake": parent["active_developmental_stake"], "candidates": [c[0], c[3], c[1], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "semantic-revive-accepted-policy", "class": "dependency", "stake": stake("revive-accepted-policy", "continuity-under-reset", "Following a restart, revive the accepted admission policy together with every behavior its evidence already protects."), "candidates": [c[2], c[0], c[1], c[3]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "semantic-supersede-membership", "class": "dependency", "stake": stake("supersede-membership", "correction-from-error", "Supersede the obsolete membership outcome using the later admitted policy, without invalidating its prior confirmations."), "candidates": [c[2], c[3], c[0], c[1]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "semantic-open-through-admission", "class": "dependency", "stake": stake("open-through-admission", "option-expansion", "Open every viable choice through the previously admitted membership policy while carrying forward all established checks."), "candidates": [c[1], c[0], c[3], c[2]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "semantic-carry-repaired-policy", "class": "dependency", "stake": stake("carry-repaired-policy", "continuity-under-reset", "Carry the repaired branch-admission policy through reset with the full body of behavior it has already demonstrated."), "candidates": [c[3], c[1], c[2], c[0]], "expected": "corrected-identity-gated-extension"},
        {"case_id": "semantic-ordinary-learned-token", "class": "ordinary", "stake": stake("ordinary-learned-token", "continuity-under-reset", "Preserve one learned token across reset."), "candidates": [c[1], c[3], c[0], c[2]], "expected": "reset-carrier"},
        {"case_id": "semantic-ordinary-admission-list", "class": "ordinary", "stake": stake("ordinary-admission-list", "option-expansion", "List the options passing one current admission check."), "candidates": [c[0], c[1], c[2], c[3]], "expected": "viable-branch-carrier"},
        {"case_id": "semantic-ordinary-repaired-number", "class": "ordinary", "stake": stake("ordinary-repaired-number", "correction-from-error", "Repair one obsolete numerical estimate using its observed value."), "candidates": [c[3], c[0], c[2], c[1]], "expected": "prediction-corrector"},
        {"case_id": "semantic-ordinary-compatible-flag", "class": "ordinary", "stake": stake("ordinary-compatible-flag", "correction-from-error", "Replace a stale compatible flag with the measured boolean."), "candidates": [c[1], c[2], c[3], c[0]], "expected": "prediction-corrector"},
        {"case_id": "semantic-ordinary-retained-options", "class": "ordinary", "stake": stake("ordinary-retained-options", "option-expansion", "Return all retained unblocked options in the current set."), "candidates": [c[2], c[3], c[1], c[0]], "expected": "viable-branch-carrier"},
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def guide_seed(root: Path, selector_base, parent: dict[str, Any], history: list[dict[str, Any]], consequences: list[dict[str, Any]]) -> Path:
    seed = root / "guide-seed"
    seed.mkdir()
    write_json(seed / "subject-position.json", selector_base.worlds.base.active_position(parent))
    write_json(seed / "candidate-mechanisms.json", selector_base.CANDIDATES)
    write_json(seed / "selection-history.json", history)
    write_json(seed / "consequence-lineage.json", consequences)
    write_json(seed / "mutation-envelope.json", {"editable": ["selection-guide.md"], "immutable": ["subject-position.json", "candidate-mechanisms.json", "selection-history.json", "consequence-lineage.json"]})
    (seed / "selection-guide.md").write_text("# Semantic mechanism selection\n\nUse the full substantive stake, not merely its coarse property.\n")
    (seed / "README.md").write_text(
        "Author a compact semantic mechanism-selection guide for fresh successor actors. Edit only selection-guide.md. "
        "Derive it from the complete consequence history. Preserve when coarse property routing is sufficient, explain when a stake depends on already admitted or corrected composed machinery and its earned floor, and guard against individual cue words causing false overrides. "
        "The guide must support unfamiliar paraphrases rather than enumerate case answers, and must be at most 5,000 UTF-8 bytes. Inspect the exact diff and report truthfully.\n"
    )
    return seed


def choice_seed(root: Path, selector_base, parent: dict[str, Any], request: dict[str, Any], guide: str | None) -> Path:
    seed = root / "choice-seed"
    seed.mkdir()
    visible = {key: copy.deepcopy(value) for key, value in request.items() if key != "expected"}
    write_json(seed / "subject-position.json", selector_base.worlds.base.active_position(parent))
    write_json(seed / "selection-request.json", visible)
    write_json(seed / "candidate-mechanisms.json", request["candidates"])
    write_json(seed / "choice.json", {"mechanism_id": "__CHOOSE__", "rationale": "__CHOOSE__"})
    immutable = ["subject-position.json", "selection-request.json", "candidate-mechanisms.json"]
    if guide is not None:
        (seed / "selection-guide.md").write_text(guide)
        immutable.append("selection-guide.md")
    write_json(seed / "mutation-envelope.json", {"editable": ["choice.json"], "immutable": immutable})
    (seed / "README.md").write_text(
        "Choose the presented mechanism that best satisfies the full substantive selection request. The coarse property is a default only when it is sufficient. "
        "Use selection-guide.md if present. Do not invent candidates or inspect outside this workspace. Edit only choice.json with exactly mechanism_id and a nonempty rationale, then report the same mechanism_id truthfully.\n"
    )
    return seed


def main() -> int:
    global previous
    previous = load_base()
    runtime_base = previous.runtime_base
    selector_base = previous.selector_base
    base = previous.base
    prior131 = previous.prior131
    base130 = previous.base130
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0163").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = selector_base.load_artifact(p82, repo, store, "OT-0156", "open-subject-after-exact-corrected-extension-reuse.json")
    result_160 = selector_base.load_artifact(p82, repo, store, "OT-0160", "complete-selector-runtime-reconstruction-aggregate.json")
    result_161 = selector_base.load_artifact(p82, repo, store, "OT-0161", "consequence-corrected-mechanism-selector-aggregate.json")
    result_162 = selector_base.load_artifact(p82, repo, store, "OT-0162", "relational-dependency-selector-correction-aggregate.json")
    original_public, original_hidden = selector_base.portfolios(parent["active_developmental_stake"])
    history = [*original_public, *original_hidden, *previous.previous.hidden_portfolios(), *previous.hidden_portfolios()]
    requests = selection_requests(parent, selector_base)
    fixtures = {"checks": {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and parent["continuation"]["status"] == "open" and runtime.identity_conforms(parent),
        "history_has_28_open_cases": len(history) == 28 and len({row["case_id"] for row in history}) == 28,
        "three_consequences_exact": result_160["hidden_world"]["result"]["pass_count"] == 4 and result_161["hidden_world"]["result"]["pass_count"] == 6 and result_162["hidden_world"]["result"]["pass_count"] == 4,
        "requests_balanced_5_and_5": len(requests) == 10 and sum(row["class"] == "dependency" for row in requests) == 5 and sum(row["class"] == "ordinary" for row in requests) == 5,
        "request_ids_unseen": not ({row["case_id"] for row in requests} & {row["case_id"] for row in history}),
        "schemas_present": GUIDE_SCHEMA.is_file() and CHOICE_SCHEMA.is_file(),
    }}
    fixtures["checks"]["passed"] = all(fixtures["checks"].values())
    if args.preflight_only:
        print(json.dumps({"base_sha256": BASE_SHA256, "fixtures": fixtures, "history_digest": p82.digest(history), "requests_digest": p82.digest(requests)}, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0163 evidence")
    run.mkdir(parents=True)
    write_json(run / "fixture-conformance.json", fixtures)
    if not fixtures["checks"]["passed"]:
        raise SystemExit("preflight failed")
    context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))

    guide_root = run / "semantic-guide-authoring"
    guide_root.mkdir()
    consequences = [result_160["hidden_world"], result_161["hidden_world"], result_162["hidden_world"]]
    seed = guide_seed(guide_root, selector_base, parent, history, consequences)
    guide_label = "semantic-selection-guide-author"
    guide_output, guide_base_audit, guide_workspace, _ = context.run_actor(guide_label, seed, GUIDE_SCHEMA, (seed / "README.md").read_text().strip())
    try:
        guide = (guide_workspace / "selection-guide.md").read_text()
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        guide_immutable_ok = all((guide_workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
    except (OSError, json.JSONDecodeError, KeyError):
        guide, guide_immutable_ok = "", False
    guide_valid = bool(200 <= len(guide.encode()) <= 5000 and guide != (seed / "selection-guide.md").read_text() and guide_immutable_ok and guide_output and guide_output.get("action") == "author-semantic-selection-guide")
    guide_audit = context.audit_actor(guide_label, guide_output, guide_base_audit, guide_valid, ["selection-guide.md"])
    guide_binding = None
    if guide_valid and prior131.audit_accepted(guide_audit):
        body = {"authority": "ot-0163-bound-semantic-selection-guide", "source_subject_digest": parent["artifact_digest"], "consequence_receipt_digests": [row["receipt_digest"] for row in consequences], "history_digest": p82.digest(history), "actor_patch_digest": guide_audit["patch_digest"], "guide_text": guide}
        guide_binding = {**body, "binding_digest": p82.digest(body)}

    choices: dict[str, dict[str, Any]] = {"active": {}, "erased": {}}
    actor_audits = []
    if guide_binding:
        for index, request in enumerate(requests):
            order = ["active", "erased"] if index % 2 == 0 else ["erased", "active"]
            for branch in order:
                label = f"semantic-choice-{index + 1:02d}-{branch}"
                root = run / label
                root.mkdir()
                choice_workspace_seed = choice_seed(root, selector_base, parent, request, guide if branch == "active" else None)
                prompt = (choice_workspace_seed / "README.md").read_text().strip()
                output, base_audit, workspace, _ = context.run_actor(label, choice_workspace_seed, CHOICE_SCHEMA, prompt)
                try:
                    choice = json.loads((workspace / "choice.json").read_text())
                    immutable = json.loads((choice_workspace_seed / "mutation-envelope.json").read_text())["immutable"]
                    immutable_ok = all((workspace / name).read_bytes() == (choice_workspace_seed / name).read_bytes() for name in immutable)
                except (OSError, json.JSONDecodeError, KeyError):
                    choice, immutable_ok = None, False
                ids = {row["mechanism_id"] for row in request["candidates"]}
                valid = bool(isinstance(choice, dict) and set(choice) == {"mechanism_id", "rationale"} and choice.get("mechanism_id") in ids and isinstance(choice.get("rationale"), str) and choice["rationale"].strip() and immutable_ok and output and output.get("mechanism_id") == choice["mechanism_id"])
                audit = context.audit_actor(label, output, base_audit, valid, ["choice.json"])
                actor_audits.append(audit)
                body = {"authority": "ot-0163-bound-semantic-choice", "source_subject_digest": parent["artifact_digest"], "case_digest": p82.digest({key: value for key, value in request.items() if key != "expected"}), "guide_binding_digest": guide_binding["binding_digest"] if branch == "active" else None, "actor_patch_digest": audit.get("patch_digest"), "mechanism_id": choice.get("mechanism_id") if isinstance(choice, dict) else None}
                choices[branch][request["case_id"]] = {"binding": {**body, "binding_digest": p82.digest(body)} if valid and prior131.audit_accepted(audit) else None, "output": output, "audit": audit, "choice": choice}

    all_bound = bool(guide_binding and all(choices[branch].get(row["case_id"], {}).get("binding") for branch in ["active", "erased"] for row in requests))
    active_rows = []
    erased_rows = []
    if all_bound:
        for request in requests:
            for branch, rows in [("active", active_rows), ("erased", erased_rows)]:
                observed = choices[branch][request["case_id"]]["binding"]["mechanism_id"]
                rows.append({"case_id": request["case_id"], "class": request["class"], "observed": observed, "expected": request["expected"], "passed": observed == request["expected"]})
    def scored(rows):
        return {"rows": rows, "pass_count": sum(row["passed"] for row in rows), "case_count": len(rows), "dependency_pass_count": sum(row["passed"] for row in rows if row["class"] == "dependency"), "ordinary_pass_count": sum(row["passed"] for row in rows if row["class"] == "ordinary"), "passed": bool(rows and all(row["passed"] for row in rows))}
    active_result, erased_result = scored(active_rows), scored(erased_rows)
    world_body = {"authority": "ot-0163-independent-semantic-selection-consequence", "guide_binding_digest": guide_binding["binding_digest"] if guide_binding else None, "requests_digest": p82.digest(requests), "active_result": active_result, "erased_result": erased_result}
    world = {**world_body, "receipt_digest": p82.digest(world_body)}
    write_json(run / "sealed-semantic-selection-world.json", world)

    advantage = active_result["pass_count"] - erased_result["pass_count"]
    causal = bool(active_result["pass_count"] == 10 and active_result["dependency_pass_count"] == 5 and active_result["ordinary_pass_count"] == 5 and erased_result["pass_count"] <= 8 and advantage >= 2)
    final = parent
    capability = correction = None
    if all_bound and causal and prior131.audit_accepted(guide_audit) and all(prior131.audit_accepted(audit) for audit in actor_audits):
        child = copy.deepcopy(parent)
        child.pop("artifact_digest", None)
        active_selector = {**guide_binding, "selector_kind": "fresh-actor-semantic-guide", "selection_world_receipt_digest": world["receipt_digest"]}
        active_selector["binding_digest"] = p82.digest({key: value for key, value in active_selector.items() if key != "binding_digest"})
        correction_body = {"authority": "ot-0163-semantic-selector-correction-ancestry", "parent_selector_binding_digest": result_162["correction"]["binding"]["binding_digest"], "semantic_guide_binding_digest": guide_binding["binding_digest"], "contradiction_receipt_digest": result_162["hidden_world"]["receipt_digest"]}
        correction = {**correction_body, "correction_digest": p82.digest(correction_body)}
        capability_body = {"authority": "ot-0163-semantic-selection-capability", "semantic_selector_binding_digest": active_selector["binding_digest"], "world_receipt_digest": world["receipt_digest"]}
        capability = {**capability_body, "capability_digest": p82.digest(capability_body)}
        child["developmental_semantic_selection_guides"] = [*child.get("developmental_semantic_selection_guides", []), guide_binding]
        child["developmental_mechanism_selector_corrections"] = [*child.get("developmental_mechanism_selector_corrections", []), correction]
        child["developmental_mechanism_selector_capabilities"] = [*child.get("developmental_mechanism_selector_capabilities", []), capability]
        child["active_developmental_mechanism_selector"] = active_selector
        final = p82.seal(child)

    authorized = {"artifact_digest", "active_developmental_mechanism_selector", "developmental_semantic_selection_guides", "developmental_mechanism_selector_capabilities", "developmental_mechanism_selector_corrections"}
    current_row = next((row for row in active_rows if row["case_id"] == "semantic-current-carried-stake"), None)
    checks = {"guide_actor_accepted": bool(guide_binding and prior131.audit_accepted(guide_audit)), "twenty_fresh_choices_bound": all_bound and len(actor_audits) == 20 and all(prior131.audit_accepted(audit) for audit in actor_audits), "active_10_of_10": active_result["pass_count"] == 10, "active_dependencies_5_of_5": active_result["dependency_pass_count"] == 5, "active_ordinary_5_of_5": active_result["ordinary_pass_count"] == 5, "erased_at_most_8_of_10": erased_result["pass_count"] <= 8, "active_advantage_at_least_2": advantage >= 2, "current_stake_routes_to_extension": bool(current_row and current_row["passed"]), "active_stake_retained_exactly": final["active_developmental_stake"] == parent["active_developmental_stake"], "unauthorized_parent_state_retained": all(final.get(key) == parent.get(key) for key in parent if key not in authorized), "semantic_selector_installed": final.get("active_developmental_mechanism_selector", {}).get("selector_kind") == "fresh-actor-semantic-guide", "final_subject_sounding_open": runtime.identity_conforms(final) and final["continuation"]["status"] == "open"}
    checks["passed"] = all(checks.values())
    result = {"authority": "ot-0163-retained-semantic-selection-guide", "source_subject_digest": parent["artifact_digest"], "guide": {"output": guide_output, "audit": guide_audit, "binding": guide_binding}, "choice_bindings": choices, "world": world, "checks": checks, "semantic_guide_causal_passed": checks["passed"], "observer_disposition": "promoted" if checks["passed"] else "rejected", "subject_disposition": final["continuation"]["status"], "final_subject_digest": final["artifact_digest"], "next_opening": final["continuation"]["next_opening"], "fresh_actor_count": 21}
    result["receipt_digest"] = p82.digest(result)
    write_json(run / "aggregate.json", result)
    write_json(run / "final-full-subject.json", final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
