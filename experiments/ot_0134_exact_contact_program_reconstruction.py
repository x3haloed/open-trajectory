from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0133_transferable_contact_program.py"
BASE_SHA256 = "8ee832f2b3172dfb4833668e99149a7795be0809d391acbfae88dcf0646ae4e2"
PARENT_DIGEST = "172d512704c47e2ff1f54faf47889229110cd64cbede4ef1ddba7f364e604bb9"


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0133 implementation changed")
    spec = importlib.util.spec_from_file_location("ot0134_frozen_ot0133", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = load_base()
base130 = prior.base130
base = prior.base


def safe_extract(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive) as handle:
        members = handle.getmembers()
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise RuntimeError("unsafe retained archive member")
        handle.extractall(destination, members=members, filter="data")
    return destination / "OT-0133"


def corrected_valid_program(value: Any) -> bool:
    keys = {"question", "rationale", "target", "foreign_context_prefix", "high_offset", "low_offset", "control_mode", "surrender_condition"}
    if not isinstance(value, dict) or set(value) != keys:
        return False
    if value.get("target") not in prior.prior.TARGETS or value.get("control_mode") != "exactly midpoint":
        return False
    if not all(prior.valid_text(value.get(key)) for key in ("question", "rationale", "surrender_condition")):
        return False
    prefix = value.get("foreign_context_prefix")
    if not isinstance(prefix, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", prefix):
        return False
    for key in ("high_offset", "low_offset"):
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= 10:
            return False
    return True


def retained_audit_accepted(audit: dict[str, Any]) -> bool:
    denial = audit["denial_classification_v2"]
    return bool(
        audit["exact_changes"]
        and audit["truthful"]
        and audit["changed_paths"] == ["contact-program.json"]
        and audit["reported_paths"] == ["contact-program.json"]
        and audit["trace_regime"]["accepted"]
        and denial["accepted"]
        and not denial["protected_path_named"]
        and not denial["outside_file_changes"]
    )


def load_parent(p82, repo: Path, store: Path) -> dict[str, Any]:
    _, path = p82.materialize(repo, store, "OT-0132", "open-subject-after-originated-contact.json")
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    run = (args.evidence_root or store / "runs/OT-0134").resolve()
    prior92 = base.mechanism.load_prior()
    _, _, prior89, p82 = base.mechanism.prior_chain(prior92)
    runtime = p82.load_runtime(repo, store)
    parent = load_parent(p82, repo, store)
    selector = parent["allocation_machinery"][-1]["source"]
    _, archive = p82.materialize(repo, store, "OT-0133", "transferable-contact-program-validator-rejection-run.json")
    with tempfile.TemporaryDirectory() as directory:
        retained = safe_extract(archive, Path(directory))
        program_path = retained / "contact-program-author/actor-workspace/contact-program.json"
        audit_path = retained / "contact-program-author/actor-audit.json"
        output_path = retained / "contact-program-author/output.json"
        program = json.loads(program_path.read_text()) if program_path.is_file() else None
        audit = json.loads(audit_path.read_text()) if audit_path.is_file() else None
        output = json.loads(output_path.read_text()) if output_path.is_file() else None
        public = prior.evaluate_program(p82, program, prior.PUBLIC_BASES) if corrected_valid_program(program) else None
        checks = {
            "parent_exact_sounding_open": parent["artifact_digest"] == PARENT_DIGEST and runtime.identity_conforms(parent) and parent["continuation"]["status"] == "open",
            "retained_files_present": all(path.is_file() for path in (program_path, audit_path, output_path)),
            "corrected_program_valid": corrected_valid_program(program),
            "retained_audit_accepted": bool(audit and retained_audit_accepted(audit)),
            "retained_report_exact": bool(output and output.get("contact_target") == prior.prior.ACTIVE_TARGET and output.get("files_changed") == ["contact-program.json"]),
            "public_receipt_passes": bool(public and public["passed"] and len(public["cases"]) == 6),
            "program_target_aligned": bool(program and program["target"] == prior.prior.ACTIVE_TARGET),
        }
        checks["passed"] = all(checks.values())
        if args.preflight_only:
            print(json.dumps({"base_sha256": BASE_SHA256, "checks": checks, "public_receipt": public}, indent=2, sort_keys=True))
            return 0 if checks["passed"] else 2
        if run.exists():
            raise SystemExit("preserve existing OT-0134 evidence")
        run.mkdir(parents=True)
        (run / "fixture-conformance.json").write_text(json.dumps({"checks": checks, "public_receipt": public}, indent=2, sort_keys=True) + "\n")
        if not checks["passed"]:
            raise SystemExit("pre-reconstruction conformance failed")
        binding_body = {
            "authority": "ot-0134-corrected-transferable-contact-program-binding",
            "source_subject_digest": parent["artifact_digest"],
            "opening": parent["continuation"]["next_opening"],
            "actor_patch_digest": audit["patch_digest"],
            "public_receipt": public,
            "program": program,
        }
        binding = {**binding_body, "binding_digest": p82.digest(binding_body)}
        (run / "bound-retained-contact-program.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    started = time.time()
    world = prior.open_hidden_world(p82, run, binding)
    current = parent
    routed = None
    promotion = None
    operational = False
    if world["selected_branch"]["passed"]:
        context = base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime, run, repo))
        route_root = run / "consequence"
        route_root.mkdir()
        routed = prior.run_route_actor(context, p82, prior89, route_root, parent, selector, binding, world)
        if routed["binding"]:
            current, promotion = prior.prior22.promote(p82, parent, binding, world, routed["binding"])
        operational = bool(promotion and runtime.identity_conforms(current) and current["continuation"]["status"] == "open" and current["artifact_digest"] != parent["artifact_digest"])
    result = {
        "authority": "ot-0134-exact-contact-program-reconstruction-driver",
        "source_subject_digest": parent["artifact_digest"],
        "reconstruction_checks": checks,
        "program_binding": binding,
        "hidden_world": world,
        "consequence_route": p82.compact(routed) if routed else None,
        "promotion": promotion,
        "transferable_contact_program_passed": operational,
        "observer_disposition": "promoted" if operational else "rejected",
        "subject_disposition": current["continuation"]["status"],
        "final_subject_digest": current["artifact_digest"],
        "next_opening": current["continuation"]["next_opening"],
        "retained_actor_count": 1,
        "fresh_actor_count": 1 if routed else 0,
        "elapsed_seconds": round(time.time() - started, 3),
    }
    result["receipt_digest"] = p82.digest(result)
    (run / "aggregate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (run / "final-full-subject.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if operational else 2


if __name__ == "__main__":
    raise SystemExit(main())
