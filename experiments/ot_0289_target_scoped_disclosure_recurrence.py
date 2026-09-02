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
BASE_PATH = ROOT / "ot_0288_current_disclosure_recurrence.py"
BASE_SHA256 = "d08e3b7527524d492993e261a8f104fba2f59f90bdf1508ae84363c65c46d5db"
OT288_PREFLIGHT_RECEIPT = "80db500ae22e4e89715861cfe080fcf5828f3e47317bec17967f84c099fcf63c"
AUTHORITY = "ot-0289-target-scoped-disclosure-recurrence"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0288 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0289_frozen_ot0288", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base288 = load_base()
base287 = base288.base287
b = base288.b
base287.AUTHORITY = AUTHORITY
b.AUTHORITY = AUTHORITY
b.base274.AUTHORITY = AUTHORITY


def write_json(path, value):
    base288.write_json(path, value)


def target_scoped_undisclosed(subject, package, p82):
    examples = b.base274.all_examples(subject, package, p82)
    selected = b.base274.selected(subject)[4]
    disclosure = subject.get("active_correction_disclosure") or {}
    if (
        b.base274.feedback_mode(subject)
        and disclosure.get("target_symbol") == selected
        and disclosure.get("status") == "awaiting-revision"
    ):
        visible = disclosure["cases"]
    else:
        visible = examples[:4]
    disclosed = {p82.digest(row["input"]) for row in visible}
    return [row for row in examples if p82.digest(row["input"]) not in disclosed]


base288.undisclosed_examples = target_scoped_undisclosed
b.correction_variant = base288.current_correction_variant


def setup(args):
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    forwarded = copy.copy(args)
    forwarded.evidence_root = (
        args.evidence_root or store / "runs/OT-0289"
    ).resolve()
    values = base288.setup(forwarded)
    _, _, p82, _, _, _, _, _, _, _, _ = values
    lineage = b.authority_base.guide_base.load_base()
    rejected288 = lineage.selector_base.load_artifact(
        p82,
        repo,
        store,
        "OT-0288",
        "rejected-current-disclosure-recurrence-preflight.json",
    )
    return (*values, rejected288)


def preflight(
    root, p82, runtime, parent, result286, package, result280, rejected287, rejected288
):
    result = base288.preflight(
        root,
        p82,
        runtime,
        parent,
        result286,
        package,
        result280,
        rejected287,
    )
    current = target_scoped_undisclosed(parent, package, p82)
    completed, _ = base288.current_correction_variant(
        parent, 0, package, result280, p82, runtime
    )
    refreshed = b.base264.refresh_projection_only(completed, p82)
    next_target = refreshed["active_opportunity_projection"]["opportunities"][0][
        "target_symbol"
    ]
    selection = b.base272.selection_fixture(
        root / "target-scope-control",
        refreshed,
        package,
        result280,
        next_target,
        p82,
        runtime,
    )
    fresh = target_scoped_undisclosed(selection["final"], package, p82)
    result["checks"]["base_hash_exact"] = (
        hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256
    )
    result["checks"]["ot0288_rejection_preserved"] = (
        rejected288["receipt_digest"] == OT288_PREFLIGHT_RECEIPT
        and rejected288["checks"]["passed"] is False
        and rejected288["checks"]["all_reachable_branches_pass"] is False
    )
    result["checks"]["active_scope_one_remaining"] = len(current) == 1
    result["checks"]["fresh_scope_two_remaining"] = (
        len(fresh) == 2
        and selection["final"]["active_correction_disclosure"]["target_symbol"]
        != next_target
        and selection["final"]["active_correction_disclosure"]["status"]
        != "awaiting-revision"
    )
    result["checks"]["passed"] = all(result["checks"].values())
    result["authority"] = AUTHORITY + "-preflight"
    result["rejected_predecessor_receipt_digest"] = rejected288[
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
        rejected288,
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
            rejected288,
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
