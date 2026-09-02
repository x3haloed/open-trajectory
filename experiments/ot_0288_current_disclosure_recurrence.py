from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0287_post_invalidity_tideglass_recurrence.py"
BASE_SHA256 = "dda4aa8b3fe1634cea76f14833e1d8ef56d272609327911933da1f441054b878"
OT287_PREFLIGHT_RECEIPT = "c2c55f373685fbee9eb65345f06213a9592e25272f9c98bc98951954b8e92244"
AUTHORITY = "ot-0288-current-disclosure-recurrence"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0287 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0288_frozen_ot0287", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base287 = load_base()
b = base287.b
base287.AUTHORITY = AUTHORITY
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def write_json(path, value):
    base287.write_json(path, value)


def undisclosed_examples(subject, package, p82):
    examples = b.base274.all_examples(subject, package, p82)
    disclosed = {
        p82.digest(row["input"])
        for row in subject.get("active_correction_disclosure", {}).get("cases", [])
    }
    return [row for row in examples if p82.digest(row["input"]) not in disclosed]


def current_correction_variant(subject, failures, package, result280, p82, runtime):
    target = b.base274.selected(subject)[5]
    reference = package["sealed_reference_sources"][target]
    feedback = []
    for _ in range(failures):
        available = undisclosed_examples(subject, package, p82)
        if not available:
            raise RuntimeError("unresolved consequence has no undisclosed input class")
        chosen = sorted(available, key=lambda row: row["case_id"])[0]
        source = b.base274.sabotage(reference, chosen["input"])
        actor = b.base274.fixture_action(subject, source, p82)
        public_cases = (
            subject["active_correction_disclosure"]["cases"]
            if b.base274.feedback_mode(subject)
            else b.base274.all_examples(subject, package, p82)[:4]
        )
        public = b.base271.compare_source(
            source, b.base274.selected(subject)[4], public_cases
        )
        world = b.base271.sealed_followup(
            subject, actor, package, result280, p82
        )
        subject, receipt = b.base274.compile_unresolved_feedback(
            subject, actor, world, package, p82
        )
        feedback.append(
            public["matches"] == len(public_cases)
            and world["result"]["matches"] < 6
            and receipt["counterexample"]["case_id"] == chosen["case_id"]
            and runtime.identity_conforms(subject)
        )
    actor = b.base274.fixture_action(subject, reference, p82)
    public_cases = (
        subject["active_correction_disclosure"]["cases"]
        if b.base274.feedback_mode(subject)
        else b.base274.all_examples(subject, package, p82)[:4]
    )
    public = b.base271.compare_source(
        reference, b.base274.selected(subject)[4], public_cases
    )
    world = b.base271.sealed_followup(subject, actor, package, result280, p82)
    corrected = (
        b.base273.compile_success(subject, actor, world, p82)
        if b.base274.feedback_mode(subject)
        else b.base271.compile_correction(subject, actor, world, p82)
    )
    return corrected, {
        "failures": failures,
        "feedback_passed": all(feedback),
        "success_public": public["matches"] == len(public_cases),
        "success_6_2": world["result"]["matches"] == 6
        and world["unchanged_control"]["matches"] == 2,
        "conformant": runtime.identity_conforms(corrected),
        "routes_refresh": b.base272.derive(corrected, p82)
        == "refresh-opportunity-projection",
    }


b.correction_variant = current_correction_variant


def setup(args):
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    forwarded = copy.copy(args)
    forwarded.evidence_root = (
        args.evidence_root or store / "runs/OT-0288"
    ).resolve()
    values = base287.setup(forwarded)
    _, _, p82, _, _, _, _, _, _, _ = values
    lineage = b.authority_base.guide_base.load_base()
    rejected287 = lineage.selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0287",
        "rejected-post-invalidity-tideglass-preflight.json",
    )
    return (*values, rejected287)


def preflight(
    root, p82, runtime, parent, result286, package, result280, rejected287
):
    result = base287.preflight(
        root, p82, runtime, parent, result286, package, result280
    )
    active = parent["active_correction_disclosure"]["target_symbol"]
    available = undisclosed_examples(parent, package, p82)
    exhausted, _ = current_correction_variant(
        parent, len(available), package, result280, p82, runtime
    )
    exhausted_fails = False
    try:
        current_correction_variant(
            exhausted, 1, package, result280, p82, runtime
        )
    except RuntimeError:
        exhausted_fails = True
    result["checks"]["base_hash_exact"] = (
        hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256
    )
    result["checks"]["ot0287_rejection_preserved"] = (
        rejected287["receipt_digest"] == OT287_PREFLIGHT_RECEIPT
        and rejected287["checks"]["passed"] is False
        and rejected287["checks"]["all_reachable_branches_pass"] is False
    )
    result["checks"]["current_remaining_class_exact"] = (
        len(available) == 1
        and active in package["sealed_cases"]
    )
    result["checks"]["exhausted_fails_closed"] = exhausted_fails
    result["checks"]["passed"] = all(result["checks"].values())
    result["authority"] = AUTHORITY + "-preflight"
    result["rejected_predecessor_receipt_digest"] = rejected287[
        "receipt_digest"
    ]
    result.pop("receipt_digest", None)
    result["receipt_digest"] = p82.digest(result)
    write_json(root / "fixture-conformance.json", result)
    return result


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
        result286,
        package,
        result280,
        core,
        base130,
        rejected287,
    ) = setup(args)
    retained = run / "preflight/fixture-conformance.json"
    fixtures = (
        json.loads(retained.read_text())
        if retained.exists()
        else preflight(
            run / "preflight",
            p82,
            runtime,
            parent,
            result286,
            package,
            result280,
            rejected287,
        )
    )
    if args.preflight_only:
        print(json.dumps(fixtures, indent=2, sort_keys=True))
        return 0 if fixtures["checks"]["passed"] else 2
    return base287.advance(
        repo,
        run,
        p82,
        runtime,
        parent,
        package,
        result280,
        fixtures,
        core,
        base130,
    )


if __name__ == "__main__":
    raise SystemExit(main())
