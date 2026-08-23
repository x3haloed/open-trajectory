from __future__ import annotations

import getpass
import platform
import re
import subprocess
from pathlib import Path

from .evidence import EvidenceError, load_manifest


MAX_FILE_BYTES = 1024 * 1024
MAX_TREE_BYTES = 20 * 1024 * 1024
MAX_BINARY_FIXTURE_BYTES = 64 * 1024
FORBIDDEN_DIR_PARTS = {".evidence", "artifacts", "checkpoints", "data", "datasets"}
FORBIDDEN_EVIDENCE_PARTS = {"objects", "private", "runs"}
HEAVY_EXTENSIONS = {
    ".arrow", ".bin", ".ckpt", ".gguf", ".h5", ".hdf5", ".npy",
    ".npz", ".onnx", ".parquet", ".pt", ".pth", ".safetensors",
    ".sqlite", ".sqlite3", ".tar", ".tgz", ".zip",
}
TEXT_LEAK_PATTERNS = {
    "macOS home path": re.compile(b"/" + rb"Users/[A-Za-z0-9._-]+"),
    "Linux home path": re.compile(b"/" + rb"home/[A-Za-z0-9._-]+"),
    "Windows home path": re.compile(rb"[A-Za-z]:\\\\Users\\\\[^\\\r\n\t ]+", re.I),
    "file URI": re.compile(b"file:" + b"//", re.I),
    "OpenAI-style secret": re.compile(rb"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "GitHub token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "Hugging Face token": re.compile(rb"\bhf_[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def _tracked_files(repo: Path) -> list[Path]:
    try:
        output = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=repo,
            check=True,
            capture_output=True,
        ).stdout
        names = [name for name in output.split(b"\0") if name]
        return [repo / name.decode("utf-8", errors="strict") for name in names]
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        return [path for path in repo.rglob("*") if path.is_file() and ".git" not in path.parts]


def _is_binary(data: bytes) -> bool:
    return b"\0" in data[:8192]


def _local_identity_tokens(repo: Path) -> list[bytes]:
    candidates = {Path.home().name, getpass.getuser(), platform.node()}
    for key in ("user.name", "user.email"):
        try:
            value = subprocess.run(
                ["git", "config", "--get", key],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        candidates.add(value)
    return sorted(
        {value.encode("utf-8").lower() for value in candidates if len(value.strip()) >= 4},
        key=len,
        reverse=True,
    )


def audit_repository(repo: Path) -> list[str]:
    repo = repo.resolve()
    errors: list[str] = []
    total = 0
    identity_tokens = _local_identity_tokens(repo)
    for path in _tracked_files(repo):
        if not path.exists() or not path.is_file():
            continue
        relative = path.relative_to(repo)
        parts = set(relative.parts)
        size = path.stat().st_size
        total += size

        if parts & FORBIDDEN_DIR_PARTS:
            errors.append(f"forbidden tracked storage location: {relative}")
        if "evidence" in parts and parts & FORBIDDEN_EVIDENCE_PARTS:
            errors.append(f"forbidden tracked evidence location: {relative}")
        if path.suffix.lower() in HEAVY_EXTENSIONS or path.name.lower().endswith(".tar.gz"):
            errors.append(f"forbidden heavyweight extension: {relative}")
        if size > MAX_FILE_BYTES:
            errors.append(f"tracked file exceeds 1 MiB: {relative} ({size} bytes)")

        data = path.read_bytes()
        binary = _is_binary(data)
        if binary:
            if "fixtures" not in parts:
                errors.append(f"binary file outside fixtures/: {relative}")
            if size > MAX_BINARY_FIXTURE_BYTES:
                errors.append(f"binary fixture exceeds 64 KiB: {relative}")
            continue

        for label, pattern in TEXT_LEAK_PATTERNS.items():
            if pattern.search(data):
                errors.append(f"{label} detected in {relative}")
        lowered = data.lower()
        if any(token in lowered for token in identity_tokens):
            errors.append(f"local identity token detected in {relative}")

        if relative.parts[:2] == ("evidence", "manifests") and path.suffix == ".json":
            try:
                load_manifest(path)
            except EvidenceError as error:
                errors.append(f"invalid evidence manifest {relative}: {error}")

    if total > MAX_TREE_BYTES:
        errors.append(f"tracked tree exceeds 20 MiB: {total} bytes")
    return sorted(set(errors))
