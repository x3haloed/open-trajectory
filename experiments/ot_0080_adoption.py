from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

from open_trajectory_evidence.evidence import (
    load_manifest,
    object_path,
    verify_artifact,
)


EXPERIMENT = "OT-0080"
MANIFEST_NAMES = {
    "bundle": "continuing-subject-e120-e128-bundle.json",
    "subject": "e128-open-subject.json",
    "aggregate": "e128-aggregate.json",
    "harness": "continuing-subject-harness.json",
}
REQUIRED_BUNDLE_MEMBERS = {
    "harness.py",
    "tests/test_harness.py",
    "work-frontier.md",
    *{f"experiments/e{number}/protocol.md" for number in range(120, 129)},
    *{f"experiments/e{number}/result.md" for number in range(120, 129)},
    "experiments/e128/run/aggregate.json",
    "experiments/e128/run/final-full-subject.json",
}
IDENTITY_KEYS = {
    "grammar_digest",
    "revision_grammar_digest",
    "rule_digest",
    "vocabulary_digest",
    "state_digest",
}


def digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def subject_digest(subject: dict[str, Any]) -> str:
    body = copy.deepcopy(subject)
    claimed = body.pop("artifact_digest")
    return claimed if digest(body) == claimed else "invalid"


def identity_conforms(subject: dict[str, Any]) -> bool:
    grammar = subject["opening_grammar"]
    body = {
        key: copy.deepcopy(value)
        for key, value in grammar.items()
        if key not in IDENTITY_KEYS and key != "existing_feature_vocabulary"
    }
    rule_digest = digest(body)
    vocabulary_digest = digest(sorted(grammar["existing_feature_vocabulary"]))
    state_digest = digest(
        {"rule_digest": rule_digest, "vocabulary_digest": vocabulary_digest}
    )
    return all(
        (
            grammar["rule_digest"] == rule_digest,
            grammar["vocabulary_digest"] == vocabulary_digest,
            grammar["state_digest"] == state_digest,
            grammar["grammar_digest"] == state_digest,
        )
    )


def read_object(repo: Path, store: Path, manifest_name: str) -> tuple[dict[str, Any], bytes]:
    manifest_path = repo / "evidence" / "manifests" / EXPERIMENT / manifest_name
    manifest = load_manifest(manifest_path)
    valid, message = verify_artifact(
        repo=repo, manifest_path=manifest_path, store=store
    )
    if not valid:
        raise RuntimeError(f"{manifest_name}: {message}")
    return manifest, object_path(store, manifest["sha256"]).read_bytes()


def verify_adoption(repo: Path, store: Path) -> dict[str, Any]:
    repo, store = repo.resolve(), store.resolve()
    manifests: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    for label, name in MANIFEST_NAMES.items():
        manifests[label], payloads[label] = read_object(repo, store, name)

    bundle_path = object_path(store, manifests["bundle"]["sha256"])
    with tarfile.open(bundle_path) as archive:
        names = set(archive.getnames())
    bundle_complete = REQUIRED_BUNDLE_MEMBERS <= names
    bundle_excludes_duplicate_workspaces = not any(
        part in name.split("/")
        for name in names
        for part in ("actor-workspace", ".git", ".actor-runtime", "__pycache__")
    )

    subject = json.loads(payloads["subject"])
    aggregate = json.loads(payloads["aggregate"])
    internal_digest = subject_digest(subject)
    exact_subject = all(
        (
            internal_digest != "invalid",
            aggregate["final_subject_digest"] == internal_digest,
            aggregate["candidate_passed"],
            aggregate["subject_transition_passed"],
            aggregate["causal_pending_correction_effect_passed"],
            aggregate["control_full_suite_pass_count"] == 0,
            aggregate["capability_delta"] == 2,
            identity_conforms(subject),
        )
    )
    open_subject = all(
        (
            subject["continuation"]["status"] == "open",
            subject["runtime"] == "sounding",
            subject["continuation"]["next_opening"]
            == "execute-subject-owned-challenge-machinery",
            subject["pending_challenge_machinery"] is None,
            subject["challenge_machinery"][-1].get("version") == 2,
            subject["executable_capabilities"][-1]["version"] == 4,
        )
    )
    result = {
        "authority": "ot-0080-post-hoc-evidence-adoption",
        "manifest_count": len(manifests),
        "all_manifest_bytes_verified": len(manifests) == len(MANIFEST_NAMES),
        "bundle_complete": bundle_complete,
        "bundle_excludes_duplicate_workspaces": bundle_excludes_duplicate_workspaces,
        "subject_internal_digest": internal_digest,
        "exact_subject_verified": exact_subject,
        "subject_disposition": "open" if open_subject else "lost",
        "next_opening": subject["continuation"]["next_opening"],
        "observer_disposition": "conditional",
        "claim_scopes": ["operational-transition", "causal-observation"],
        "adoption_passed": all(
            (bundle_complete, bundle_excludes_duplicate_workspaces, exact_subject, open_subject)
        ),
    }
    result["receipt_digest"] = digest(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--store", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    store = args.store or args.repo / ".evidence"
    result = verify_adoption(args.repo, store)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded)
    print(encoded, end="")
    return 0 if result["adoption_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
