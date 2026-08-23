from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVIDENCE_CLASSES = {
    "public-reconstructible",
    "private-reproducible",
    "exploratory-only",
}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEYS = {
    "cwd",
    "env",
    "environment_variables",
    "home",
    "hostname",
    "original_path",
    "password",
    "secret",
    "source_path",
    "token",
    "username",
}
HOME_PATHS = (
    re.compile(r"/Users/[^/\s]+"),
    re.compile(r"/home/[^/\s]+"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\s]+", re.IGNORECASE),
    re.compile("file:" + "//", re.IGNORECASE),
)


class EvidenceError(ValueError):
    pass


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def default_store(repo: Path) -> Path:
    configured = os.environ.get("OT_EVIDENCE_ROOT")
    return Path(configured) if configured else repo / ".evidence"


def object_path(store: Path, digest: str) -> Path:
    return store / "objects" / "sha256" / digest[:2] / digest


def _git_fingerprint(repo: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"commit": None, "dirty": None}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return result
    result["commit"] = commit if SHA256.fullmatch(commit) else commit
    result["dirty"] = bool(dirty)
    return result


def safe_environment(repo: Path) -> dict[str, Any]:
    return {
        "os_family": platform.system(),
        "architecture": platform.machine(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "git": _git_fingerprint(repo),
    }


def validate_identifier(label: str, value: str) -> None:
    if not IDENTIFIER.fullmatch(value):
        raise EvidenceError(f"{label} is not a safe logical identifier: {value!r}")


def _check_values(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                raise EvidenceError(f"forbidden manifest key at {location}.{key}")
            _check_values(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_values(child, f"{location}[{index}]")
    elif isinstance(value, str):
        for pattern in HOME_PATHS:
            if pattern.search(value):
                raise EvidenceError(f"machine-local path in {location}")


def validate_manifest(manifest: dict[str, Any]) -> None:
    expected = {
        "schema_version",
        "experiment_id",
        "artifact_id",
        "kind",
        "media_type",
        "sha256",
        "bytes",
        "evidence_class",
        "availability",
        "reconstruction",
        "environment",
        "input_manifests",
        "limitations",
    }
    missing = expected - manifest.keys()
    extra = manifest.keys() - expected
    if missing:
        raise EvidenceError(f"missing manifest keys: {sorted(missing)}")
    if extra:
        raise EvidenceError(f"unknown manifest keys: {sorted(extra)}")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError("unsupported schema_version")
    validate_identifier("experiment_id", manifest["experiment_id"])
    validate_identifier("artifact_id", manifest["artifact_id"])
    validate_identifier("kind", manifest["kind"])
    if not SHA256.fullmatch(manifest["sha256"]):
        raise EvidenceError("sha256 must be 64 lowercase hexadecimal characters")
    if not isinstance(manifest["bytes"], int) or manifest["bytes"] < 0:
        raise EvidenceError("bytes must be a non-negative integer")
    if manifest["evidence_class"] not in EVIDENCE_CLASSES:
        raise EvidenceError("invalid evidence_class")
    if not isinstance(manifest["input_manifests"], list):
        raise EvidenceError("input_manifests must be a list")
    if not isinstance(manifest["limitations"], list):
        raise EvidenceError("limitations must be a list")
    _check_values(manifest)


def record_artifact(
    *,
    repo: Path,
    input_path: Path,
    experiment_id: str,
    artifact_id: str,
    kind: str,
    evidence_class: str,
    recipe: str | None,
    public_url: str | None,
    limitations: list[str],
    input_manifests: list[str],
    store: Path | None = None,
) -> Path:
    repo = repo.resolve()
    input_path = input_path.resolve(strict=True)
    validate_identifier("experiment_id", experiment_id)
    validate_identifier("artifact_id", artifact_id)
    validate_identifier("kind", kind)
    if evidence_class not in EVIDENCE_CLASSES:
        raise EvidenceError("invalid evidence_class")
    if public_url and not public_url.startswith("https://"):
        raise EvidenceError("public_url must use HTTPS")
    if evidence_class == "public-reconstructible" and not (recipe or public_url):
        raise EvidenceError("public-reconstructible evidence needs a recipe or public_url")

    digest, size = sha256_file(input_path)
    store = (store or default_store(repo)).resolve()
    destination = object_path(store, digest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing_digest, existing_size = sha256_file(destination)
        if existing_digest != digest or existing_size != size:
            raise EvidenceError("content-addressed destination contains mismatched bytes")
    else:
        temporary = destination.with_suffix(".partial")
        shutil.copyfile(input_path, temporary)
        copied_digest, copied_size = sha256_file(temporary)
        if copied_digest != digest or copied_size != size:
            temporary.unlink(missing_ok=True)
            raise EvidenceError("artifact changed while being copied")
        temporary.replace(destination)

    media_type = mimetypes.guess_type(input_path.name)[0] or "application/octet-stream"
    availability: dict[str, Any] = {"local_object": True}
    if public_url:
        availability["public_url"] = public_url
    reconstruction = {
        "recipe": recipe,
        "expected_output": f"artifact:{artifact_id}",
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "artifact_id": artifact_id,
        "kind": kind,
        "media_type": media_type,
        "sha256": digest,
        "bytes": size,
        "evidence_class": evidence_class,
        "availability": availability,
        "reconstruction": reconstruction,
        "environment": safe_environment(repo),
        "input_manifests": input_manifests,
        "limitations": limitations,
    }
    validate_manifest(manifest)

    manifest_path = repo / "evidence" / "manifests" / experiment_id / f"{artifact_id}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(encoded, encoding="utf-8")
    return manifest_path


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot read manifest: {error}") from error
    if not isinstance(value, dict):
        raise EvidenceError("manifest root must be an object")
    validate_manifest(value)
    return value


def verify_artifact(
    *,
    repo: Path,
    manifest_path: Path,
    artifact_path: Path | None = None,
    store: Path | None = None,
) -> tuple[bool, str]:
    manifest = load_manifest(manifest_path)
    if artifact_path is None:
        store = (store or default_store(repo)).resolve()
        candidate = object_path(store, manifest["sha256"])
        if not candidate.exists():
            return False, "manifest valid; evidence bytes unavailable"
    else:
        candidate = artifact_path
    digest, size = sha256_file(candidate)
    if digest != manifest["sha256"] or size != manifest["bytes"]:
        return False, "evidence bytes do not match manifest"
    return True, "manifest and evidence bytes verified"
