from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audit import audit_repository
from .evidence import EVIDENCE_CLASSES, EvidenceError, record_artifact, verify_artifact


def _repo(value: str) -> Path:
    return Path(value).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ot-evidence")
    parser.add_argument("--repo", default=".", help="repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record", help="store bytes externally and publish a safe manifest")
    record.add_argument("--input", required=True, type=Path)
    record.add_argument("--experiment", required=True)
    record.add_argument("--artifact-id", required=True)
    record.add_argument("--kind", required=True)
    record.add_argument("--evidence-class", choices=sorted(EVIDENCE_CLASSES), default="exploratory-only")
    record.add_argument("--recipe")
    record.add_argument("--public-url")
    record.add_argument("--limitation", action="append", default=[])
    record.add_argument("--input-manifest", action="append", default=[])
    record.add_argument("--store", type=Path)

    verify = subparsers.add_parser("verify", help="validate a manifest and matching bytes")
    verify.add_argument("manifest", type=Path)
    verify.add_argument("--artifact", type=Path)
    verify.add_argument("--store", type=Path)

    subparsers.add_parser("audit", help="fail on privacy or repository-size violations")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = _repo(args.repo)
    try:
        if args.command == "record":
            manifest = record_artifact(
                repo=repo,
                input_path=args.input,
                experiment_id=args.experiment,
                artifact_id=args.artifact_id,
                kind=args.kind,
                evidence_class=args.evidence_class,
                recipe=args.recipe,
                public_url=args.public_url,
                limitations=args.limitation,
                input_manifests=args.input_manifest,
                store=args.store,
            )
            print(manifest.relative_to(repo))
            return 0
        if args.command == "verify":
            valid, message = verify_artifact(
                repo=repo,
                manifest_path=args.manifest,
                artifact_path=args.artifact,
                store=args.store,
            )
            print(message)
            return 0 if valid else 2
        if args.command == "audit":
            errors = audit_repository(repo)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print("privacy and repository-size audit passed")
            return 0
    except (EvidenceError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 1

