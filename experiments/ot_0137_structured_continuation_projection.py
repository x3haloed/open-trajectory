from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0136_consequence_corrected_contact_program.py"
BASE_SHA256 = "c2d695da46f0d8524652232a59849de308e9eafb63a202db3601dcc30acaf5fc"
PARENT_DIGEST = "60576efe0d9fa7aef6c6455b092ec2b358a61d536fe38946c2a9dfc8f1fe42c3"
COMPILER_VERSION = "ot-0137-structured-v1"
PREFIX = re.compile(r"^Open\s+[a-z][a-z0-9-]{2,127}:\s*", re.IGNORECASE)
QUESTION = re.compile(r"^(.+?remains unresolved\.)", re.IGNORECASE)


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0136 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0137_frozen_ot0136", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base130 = prior.base130
base = prior.base


def normalize_question(value: str) -> str | None:
    candidate = value.strip()
    while PREFIX.match(candidate):
        candidate = PREFIX.sub("", candidate, count=1).strip()
    match = QUESTION.match(candidate)
    if not match:
        return None
    question = match.group(1).strip()
    question = question[0].upper() + question[1:]
    if PREFIX.search(question) or " open continuation-" in question.lower():
        return None
    return question


def evidence_scope(aggregate: dict[str, Any]) -> dict[str, Any]:
    return {
        "authority": "ot-0137-evidence-scope-projection",
        "parent_failure": {
            "program_digest": aggregate["failure_receipt"]["world_evaluation"]["program_digest"],
            "distinguishing": aggregate["failure_receipt"]["world_evaluation"]["distinguishing_count"],
            "adversarial": aggregate["failure_receipt"]["world_evaluation"]["adversarial_count"],
            "receipt_digest": aggregate["failure_receipt"]["receipt_digest"],
        },
        "corrected_quantized": {
            "program_digest": aggregate["quantized_correction_receipt"]["selected_branch"]["program_digest"],
            "distinguishing": aggregate["quantized_correction_receipt"]["selected_branch"]["distinguishing_count"],
            "adversarial": aggregate["quantized_correction_receipt"]["selected_branch"]["adversarial_count"],
            "receipt_digest": aggregate["quantized_correction_receipt"]["receipt_digest"],
        },
        "raw_no_regression": {
            "distinguishing": aggregate["raw_no_regression_receipt"]["selected_branch"]["distinguishing_count"],
            "adversarial": aggregate["raw_no_regression_receipt"]["selected_branch"]["adversarial_count"],
            "receipt_digest": aggregate["raw_no_regression_receipt"]["receipt_digest"],
        },
        "later_reuse": {
            "distinguishing": aggregate["post_seal_reuse"]["distinguishing_count"],
            "adversarial": aggregate["post_seal_reuse"]["adversarial_count"],
            "bases_digest": aggregate["post_seal_reuse"]["bases_digest"],
        },
    }


def reconstruct(p82, parent: dict[str, Any], aggregate: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    route_binding = aggregate["consequence_route"]["binding"]
    route = route_binding["route_assimilation"]
    original = route["remaining_uncertainty"]
    question = normalize_question(original)
    if not question:
        return None, {"question_parsed": False}
    old_action = route_binding["continuation_action"]
    action = {**old_action, "expected_information": question}
    projected_route = {**route, "remaining_uncertainty": question}
    opening = base130.previous.compile_opening(projected_route, action)
    scope = evidence_scope(aggregate)
    receipt_body = {
        "authority": "ot-0137-structured-continuation-projection",
        "source_subject_digest": parent["artifact_digest"],
        "source_route_binding_digest": route_binding["binding_digest"],
        "compiler_version": COMPILER_VERSION,
        "original_remaining_uncertainty": original,
        "question": question,
        "evidence_scope": scope,
        "action_target": action["action_target"],
        "projected_opening": opening,
    }
    receipt = {**receipt_body, "receipt_digest": p82.digest(receipt_body)}
    child = copy.deepcopy(parent)
    child.pop("artifact_digest", None)
    child["canonical_continuation_projections"] = [*child.get("canonical_continuation_projections", []), receipt]
    child["active_pursuit"] = {**child["active_pursuit"], "next_pursuit": opening["next_opening"]}
    child["continuation"] = {**child["continuation"], "next_opening": opening["next_opening"]}
    child["unresolved"] = opening["continuation_after_contact"]
    child = p82.seal(child)
    checks = {
        "question_parsed": True,
        "question_has_no_lifecycle_prefix": "open continuation-" not in question.lower(),
        "question_retains_frontier": all(term in question.lower() for term in ("three or more", "foreign-context", "remains unresolved")),
        "live_opening_single_prefix": child["continuation"]["next_opening"].lower().count("open continuation-") == 1,
        "historical_route_exact": child["pursuit_assimilations"][-1]["assimilation"] == parent["pursuit_assimilations"][-1]["assimilation"],
        "historical_opening_exact": child["actor_originated_pursuit_openings"][-1] == parent["actor_originated_pursuit_openings"][-1],
        "capability_exact": child["contact_program_capabilities"][-1] == parent["contact_program_capabilities"][-1],
        "scope_exact": scope["parent_failure"]["distinguishing"] == 0 and scope["corrected_quantized"]["distinguishing"] == 6 and scope["raw_no_regression"]["distinguishing"] == 4 and scope["later_reuse"]["distinguishing"] == 2,
    }
    checks["passed"] = all(checks.values())
    return child, {"checks": checks, "receipt": receipt, "action": action, "opening": opening}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0137").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = prior.prior135.load_json_artifact(p82, repo, store, "OT-0136", "open-subject-with-corrected-contact-program.json")
    aggregate = prior.prior135.load_json_artifact(p82, repo, store, "OT-0136", "consequence-corrected-contact-program-aggregate.json")
    child, reconstruction = reconstruct(p82, parent, aggregate)
    original_route = aggregate["consequence_route"]["binding"]["route_assimilation"]
    original_action = aggregate["consequence_route"]["binding"]["continuation_action"]
    ablated = base130.previous.compile_opening(original_route, original_action)
    checks = {
        "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
        "source_aggregate_passed": aggregate["consequence_corrected_program_passed"] and aggregate["final_subject_digest"] == parent["artifact_digest"],
        "reconstruction_passed": bool(child and reconstruction["checks"]["passed"]),
        "child_sounding_open": bool(child and runtime.identity_conforms(child) and child["continuation"]["status"] == "open"),
        "normalization_erased_reproduces_nested": ablated["next_opening"].lower().count("open continuation-") == 2,
        "structured_projection_is_valid_successor": prior89.valid_successor(reconstruction["opening"]) if child else False,
    }
    checks["passed"] = all(checks.values())
    result = {
        "authority": "ot-0137-structured-continuation-projection-driver",
        "source_subject_digest": parent["artifact_digest"],
        "checks": checks,
        "projection": reconstruction,
        "normalization_erased_opening": ablated,
        "structured_projection_passed": checks["passed"],
        "observer_disposition": "promoted" if checks["passed"] else "rejected",
        "subject_disposition": child["continuation"]["status"] if child else parent["continuation"]["status"],
        "final_subject_digest": child["artifact_digest"] if checks["passed"] else parent["artifact_digest"],
        "next_opening": child["continuation"]["next_opening"] if checks["passed"] else parent["continuation"]["next_opening"],
    }
    result["receipt_digest"] = p82.digest(result)
    if args.preflight_only:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if checks["passed"] else 2
    if run.exists():
        raise SystemExit("preserve existing OT-0137 evidence")
    run.mkdir(parents=True)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(child if checks["passed"] else parent, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
