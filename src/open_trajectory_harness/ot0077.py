"""Authoritative lifecycle and evaluator orchestration for OT-0077.

The P-frozen world derivation lives in :mod:`ot0077_protocol`.  This module is
the implementation-phase controller: it freezes the clean implementation
identity before private derivation, enforces the one-attempt lock, executes the
candidate-free reference paths, and publishes only after exact private
reconstruction.
"""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import json
import mimetypes
import multiprocessing
import os
import platform
import re
import secrets
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final, Iterator

from open_trajectory_evidence.evidence import (
    default_store,
    safe_environment,
    validate_identifier,
    validate_manifest,
)

from .ot0002 import (
    canonical_json,
    child_environment,
    git_output,
    sha256_bytes,
    sha256_file,
)
from .ot0077_learning import (
    COMPACT_REFERENCE,
    IMMUTABLE_SEED_CONTROL,
    LOG_REFERENCE,
    LearningError,
    decode_state,
    encode_state,
    initial_state,
    offline_best_fixed_rule,
    predict,
    update,
    update_from_authoritative_state,
)
from .ot0077_protocol import (
    EPISODE_SCHEDULE,
    build_design_task,
    derive_task,
    validate_task,
)
from .ot0077_design_probe import (
    EXPECTED_ROW_COUNT,
    EXPECTED_VECTOR_BYTES,
    EXPECTED_VECTOR_SHA256,
)
from .ot0077_receipts import (
    EPISODE_RESET_TRANSITION,
    ONLINE_POSITIVE,
    POST_STATE_PROJECTION,
    UPDATE_WITHOUT_PROJECTION,
    ChainValidation,
    ReceiptChainBuilder,
    ReceiptError,
    consumer_runtime_ready,
    causal_path_gates,
    checkpoint,
    decode_blob,
    derive_identity,
    expected_mutation_code,
    make_consumer_facts,
    SENTINEL_CHANNELS,
    rollback_gates,
    seeded_authority_defect_gates,
    strict_online_surface,
    validate_chain,
    validate_chain_collection,
    validate_projection_consumer_substitution_rejection,
)
from .ot0077_journal import (
    JOURNAL_FORMAT,
    MAX_STAGE_SEGMENTS,
    SCOPES,
    SEGMENT_DIRECTORY_NAME,
    STAGE_OPEN_NAME,
    STAGE_SEAL_NAME,
    JournalError,
    SegmentedEncounterJournal,
    read_stage,
    reassemble_chain,
)
from .ot0077_scoring import (
    AUTHORITY_DEFECTS,
    CAUSAL_PATH_GATES,
    CONDITION_INVENTORY,
    EXECUTION_GATES,
    ROLLBACK_REPLAY_GATES,
    metamorphic_variants,
    score_bundle,
)
from .ot0077_shadow_scoring import score_bundle_shadow
from .ot0077_reset_worker import forkserver_consume, forkserver_probe


EXPERIMENT_ID: Final = "OT-0077"
PROTOCOL_ORIGIN_COMMIT: Final = "668b9021f22db4ffb6672e2b5e3af15b708218b1"
ACCEPTANCE_PATH: Final = Path("spec/ot-0077-acceptance.json")
EXPERIMENT_PATH: Final = Path(
    "experiments/OT-0077-e14-public-vector-identity-repair.md"
)
PROTOCOL_PATH: Final = Path("src/open_trajectory_harness/ot0077_protocol.py")
RUN_LOCK_PATH: Final = Path("spec/ot-0077-run-lock.json")

ACCEPTANCE_SHA256: Final = (
    "4a79e7cc4b82ec40d7f2a37de32716b79e4049a4af1fcc45f8551dd16a63965d"
)
EXPERIMENT_SHA256: Final = (
    "bae447edbe3cd80e7e8c3a2e4ff4e9defb8acc65e9ccc58c2976a9d065de2035"
)
PROTOCOL_SHA256: Final = (
    "7deb8a7b01ecdf57716958956f810f67487bd24b88e98073055d2d55e1c41b48"
)

DEFAULT_RUN_ID: Final = "ot-0077-e14-public-vector-identity-repair-001"
DERIVATION_ID: Final = "ot-0077-private-anchor-derivation-001"
ATTEMPT_RELATIVE_PATH: Final = Path("attempts/OT-0077/anchor-attempt-001.json")
SEED_RELATIVE_PATH: Final = Path("private/OT-0077/anchor-seed-001.bin")
TASK_RELATIVE_PATH: Final = Path("tasks/OT-0077/anchor-task-001.json")
DERIVATION_RELATIVE_PATH: Final = Path(
    "derivations/OT-0077/anchor-derivation-001.json"
)
RAW_RELATIVE_PATH: Final = Path("runs/OT-0077") / f"{DEFAULT_RUN_ID}.json.zlib"
RAW_STAGING_RELATIVE_PATH: Final = RAW_RELATIVE_PATH.with_name(
    f".{RAW_RELATIVE_PATH.name}.pending"
)
PUBLIC_JOURNAL_RELATIVE_PATH: Final = (
    Path("public/OT-0077") / f"{DEFAULT_RUN_ID}-design.journal"
)
ANCHOR_JOURNAL_RELATIVE_PATH: Final = (
    Path("runs/OT-0077") / f"{DEFAULT_RUN_ID}.journal"
)
FAILED_ANCHOR_JOURNAL_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{DEFAULT_RUN_ID}.journal"
)
FAILED_PUBLIC_JOURNAL_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{DEFAULT_RUN_ID}-design.journal"
)
PUBLIC_FAILURE_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{DEFAULT_RUN_ID}-design-failure.json"
)
PROMOTION_ARTIFACT_ID: Final = f"{DEFAULT_RUN_ID}-promotion-decision"
PROMOTION_RELATIVE_PATH: Final = (
    Path("runs/OT-0077") / f"{PROMOTION_ARTIFACT_ID}.json"
)
FAILURE_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{DEFAULT_RUN_ID}-failure.json"
)
FAILED_MANIFEST_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{DEFAULT_RUN_ID}-manifest.json"
)
FAILED_PROMOTION_MANIFEST_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{PROMOTION_ARTIFACT_ID}-manifest.json"
)
FAILED_PROMOTION_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{PROMOTION_ARTIFACT_ID}.json"
)
FAILED_RAW_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{DEFAULT_RUN_ID}-unpublished-raw.json.zlib"
)
FAILED_RAW_STAGING_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{DEFAULT_RUN_ID}-raw-staging.bin"
)
COMPLETION_RELATIVE_PATH: Final = (
    Path("runs/OT-0077") / f"{DEFAULT_RUN_ID}-publication-complete.json"
)
FAILED_COMPLETION_RELATIVE_PATH: Final = (
    Path("failures/OT-0077")
    / f"{DEFAULT_RUN_ID}-publication-complete.json"
)
RECONSTRUCTION_ROOT_RELATIVE_PATH: Final = (
    Path("reconstruction/OT-0077") / f"{DEFAULT_RUN_ID}-fresh-root"
)
FAILED_RECONSTRUCTION_ROOT_RELATIVE_PATH: Final = (
    Path("failures/OT-0077") / f"{DEFAULT_RUN_ID}-fresh-root"
)

CALIBRATION_SECONDS: Final = 900
RECONSTRUCTION_SECONDS: Final = 900
EXECUTOR_DRAIN_SECONDS: Final = 30
PUBLIC_CAUSAL_DESIGN_INDEX: Final = 0
MAX_RAW_BYTES: Final = 134_217_728
MAX_UNCOMPRESSED_RAW_BYTES: Final = 1_073_741_824
MAX_COMPLETION_BYTES: Final = 262_144
MAX_MANIFEST_BYTES: Final = 1_048_576
MAX_PROMOTION_BYTES: Final = 8_388_608
PRIVATE_SEED_BYTES: Final = 32
MAX_ATTEMPT_BYTES: Final = 65_536
MAX_DERIVATION_TASK_BYTES: Final = 1_048_576
MAX_DERIVATION_RECEIPT_BYTES: Final = 65_536
MAX_ACCEPTANCE_BYTES: Final = 65_536
MAX_RUN_LOCK_BYTES: Final = 1_048_576
MAX_PROCESS_STDOUT_BYTES: Final = MAX_RAW_BYTES
MAX_PROCESS_STDERR_BYTES: Final = 1_048_576
MAX_CONSUMER_STDOUT_BYTES: Final = 1_048_576
MAX_CONSUMER_STDERR_BYTES: Final = 65_536
RECONSTRUCTION_RECIPE: Final = (
    "At environment.git.commit, place the controller-private seed at "
    "$EVIDENCE/private/OT-0077/anchor-seed-001.bin. Reconstruction mode "
    "deterministically regenerates the canonical attempt marker from the run "
    "lock's implementation_git_commit (the direct parent of that execution "
    "commit) before deriving the task and receipt. Then run "
    "OT_EVIDENCE_ROOT=$EVIDENCE PYTHONPATH=src python3 -m "
    "open_trajectory_harness.ot0077 --reconstruct-only"
)
PROMOTION_RECONSTRUCTION_RECIPE: Final = (
    "At environment.git.commit, restore the prepublication raw artifact named "
    "by the first input manifest and its controller-private seed, execute the "
    "OT-0077 fresh-root reconstruction, rerun the complete tests and evidence "
    "audit, and apply finalize_after_reconstruction to reproduce this decision"
)
RAW_INPUT_MANIFESTS: Final = (
    "evidence/manifests/OT-0073/ot-0073-fresh-root-reconstruction-calibration-001.json",
)
RAW_LIMITATIONS: Final = (
    "This raw artifact is a prepublication calibration record and carries zero learner authority by itself.",
    "OT-0077 is candidate-free evaluator calibration, not base-model learning evidence.",
    "The private anchor establishes one bounded hidden semi-Markov parity opportunity only.",
    "Both positive paths are controller references with fixed learning machinery.",
)
PROMOTION_LIMITATIONS: Final = (
    "This decision promotes only the candidate-free E14 evaluator opportunity.",
    "It authorizes at most one separately frozen actor-bearing experiment.",
    "It is not evidence of actor learning, machinery invention, or cross-domain transfer.",
)

EXPECTED_PUBLIC_SCORE_SHA256: Final = (
    "9ad2d6cedfefdd3606785a9febaaf68f0dcfa85b41b379ca33bcb9e00b178e5b"
)
CLAIM_LIMIT: Final = "candidate-free evaluator-visible surrogate calibration only"

INHERITED_SOURCE_SHA256S: Final = {
    "experiments/OT-0076-e14-matched-counterfactual-evaluator-repair.md": (
        "97b4bfcb533e332cdbedd89697b99e8e664d0cc084e1ace1fdfd8d0600f58e84"
    ),
    "spec/ot-0076-acceptance.json": (
        "86b34d38fce63f36d103fc72d4f67197361fb5d3847d0f70ba4de46d8f1f6174"
    ),
    "src/open_trajectory_harness/ot0075_protocol.py": (
        "7c208df7fc2571f5128af908eb01c81c635968d59633ab390845bbacc87587de"
    ),
    "src/open_trajectory_harness/ot0076_protocol.py": (
        "dd17c5b8e7296a21cd266ae10c52833feaab79d83dc96a9d615ab30d0a6b9359"
    ),
    "src/open_trajectory_harness/ot0075_learning.py": (
        "be659009fb9d5103f53a7b379ad73329fc19f282e280c019562b8110420abbe6"
    ),
    "src/open_trajectory_harness/ot0076_design_probe.py": (
        "d4a989b8d86f59636ee8a9c6b176f0c4e3b59e09a86b995971af963720496f1f"
    ),
    "experiments/OT-0076-e14-matched-counterfactual-evaluator-repair-result.md": (
        "bf083e6990eed795ef5999f65a9cd131c31e720f18813dc9a43fdbffb6887919"
    ),
}

_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_FORKSERVER_LOCK = threading.Lock()
_FORKSERVER_PROCESS_LOCK = threading.Lock()
_FORKSERVER_CONTEXT: Any | None = None
_FORKSERVER_READY = False
_FORK_CONTEXT_UNSET = object()
_AUTHORITY_GROUP_ENV: Final = "OPEN_TRAJECTORY_OT0077_AUTHORITY_GROUP"


class ProtocolError(ValueError):
    """Raised when an OT-0077 identity or authority contract differs."""


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ProtocolError(f"{label} keys differ from the frozen schema")
    return value


def _commit(value: object, label: str = "commit") -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        raise ProtocolError(f"{label} is not a full Git identity")
    return value


def _sha(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProtocolError(f"{label} is not a lowercase SHA-256")
    return value


def _logical(path: Path) -> str:
    return "$EVIDENCE/" + path.as_posix()


def _store(repo: Path) -> Path:
    return default_store(repo.resolve()).resolve()


def _confined_child(root: Path, relative: Path, authority: str) -> Path:
    root = root.resolve()
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"{authority} path is not relative")
    lexical = root / relative
    # Let the caller's leaf-presence gate classify a leaf symlink as the
    # corresponding occupied authority surface.  Indirect parent ancestry is
    # still rejected here before any read or write.
    if lexical.is_symlink():
        return lexical
    resolved = lexical.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise RuntimeError(f"{authority} path leaves its root") from error
    if resolved != lexical:
        raise RuntimeError(f"{authority} path has indirect ancestry")
    return lexical


def _store_path(repo: Path, relative: Path) -> Path:
    return _confined_child(_store(repo), relative, "evidence root")


def _repository_path(repo: Path, relative: Path) -> Path:
    return _confined_child(repo.resolve(), relative, "repository")


def _public_manifest_root(repo: Path) -> Path:
    root = _repository_path(repo, Path("evidence"))
    if root.is_symlink() or root.resolve() != root:
        raise RuntimeError("public manifest root has indirect ancestry")
    return root


def attempt_path(repo: Path) -> Path:
    return _store_path(repo, ATTEMPT_RELATIVE_PATH)


def seed_path(repo: Path) -> Path:
    return _store_path(repo, SEED_RELATIVE_PATH)


def task_path(repo: Path) -> Path:
    return _store_path(repo, TASK_RELATIVE_PATH)


def receipt_path(repo: Path) -> Path:
    return _store_path(repo, DERIVATION_RELATIVE_PATH)


def raw_path(repo: Path) -> Path:
    return _store_path(repo, RAW_RELATIVE_PATH)


def manifest_path(repo: Path) -> Path:
    return _confined_child(
        _public_manifest_root(repo),
        Path("manifests") / EXPERIMENT_ID / f"{DEFAULT_RUN_ID}.json",
        "public manifest root",
    )


def promotion_path(repo: Path) -> Path:
    return _store_path(repo, PROMOTION_RELATIVE_PATH)


def promotion_manifest_path(repo: Path) -> Path:
    return _confined_child(
        _public_manifest_root(repo),
        Path("manifests") / EXPERIMENT_ID / f"{PROMOTION_ARTIFACT_ID}.json",
        "public manifest root",
    )


def _write_sealed_bytes(path: Path, value: bytes) -> None:
    if path.exists():
        raise RuntimeError(f"sealed output already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            written = handle.write(value)
            if written != len(value):
                raise OSError("sealed output write was incomplete")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise RuntimeError(f"sealed output already exists: {path.name}") from error
    path.chmod(0o400)
    _fsync_directory(path.parent)


def _read_regular_file_bounded(path: Path, limit: int) -> bytes:
    """Read one non-symlink regular file without allocating beyond its bound."""

    if type(limit) is not int or limit < 1:
        raise ProtocolError("bounded file limit is unavailable")
    initial = path.lstat()
    if (
        not stat.S_ISREG(initial.st_mode)
        or not initial.st_mode & stat.S_IRUSR
        or not 0 < initial.st_size <= limit
    ):
        raise ProtocolError("bounded regular file identity differs")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != initial.st_dev
            or opened.st_ino != initial.st_ino
            or opened.st_size != initial.st_size
        ):
            raise ProtocolError("bounded file changed before read")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1_048_576, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) != opened.st_size or len(payload) > limit:
            raise ProtocolError("bounded file changed during read")
        return payload
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _authority_identity_from_stat(value: os.stat_result) -> dict[str, int]:
    return {"device": value.st_dev, "inode": value.st_ino}


def _authority_root_identity(path: Path, label: str) -> dict[str, int]:
    try:
        observed = path.stat(follow_symlinks=False)
    except OSError as error:
        raise ProtocolError(f"{label} authority root is unavailable") from error
    if not stat.S_ISDIR(observed.st_mode) or path.is_symlink():
        raise ProtocolError(f"{label} authority root is not a directory")
    return _authority_identity_from_stat(observed)


def _validated_authority_identity(value: object, label: str) -> dict[str, int]:
    identity = _exact(value, {"device", "inode"}, f"{label} identity")
    if any(type(identity[key]) is not int or identity[key] < 0 for key in identity):
        raise ProtocolError(f"{label} identity differs")
    return identity


def _directory_open_flags() -> int:
    required = ("O_DIRECTORY", "O_NOFOLLOW")
    if any(not hasattr(os, name) for name in required):
        raise ProtocolError("pinned directory traversal is unavailable")
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _open_authority_root(
    path: Path,
    expected_identity: object,
    label: str,
) -> int:
    identity = _validated_authority_identity(expected_identity, label)
    try:
        descriptor = os.open(path, _directory_open_flags())
    except OSError as error:
        raise ProtocolError(f"{label} authority root cannot be pinned") from error
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or _authority_identity_from_stat(observed) != identity
        ):
            raise ProtocolError(f"{label} authority root identity changed")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _available_authority_identity(
    path: Path,
    label: str,
) -> dict[str, int] | None:
    if not path.exists() and not path.is_symlink():
        return None
    return _authority_root_identity(path, label)


def _contract_authority_identity(
    contract: dict[str, Any],
    root_name: str,
    label: str,
) -> dict[str, int]:
    path = contract.get(root_name)
    if not isinstance(path, Path):
        raise ProtocolError(f"{label} authority path differs")
    identity_name = f"{root_name}_identity"
    identity = contract.get(identity_name)
    if identity is None:
        identity = _authority_root_identity(path, label)
        contract[identity_name] = identity
        return identity
    return _validated_authority_identity(identity, label)


def _relative_authority_parts(relative: Path, label: str) -> tuple[str, ...]:
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ProtocolError(f"{label} authority path differs")
    parts = tuple(relative.parts)
    if any(part in {"", ".", os.sep} for part in parts):
        raise ProtocolError(f"{label} authority path differs")
    return parts


def _open_directory_at(
    parent_descriptor: int,
    name: str,
    *,
    create: bool,
    label: str,
) -> int:
    flags = _directory_open_flags()
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
    except FileNotFoundError:
        if not create:
            raise
        try:
            os.mkdir(name, mode=0o755, dir_fd=parent_descriptor)
            os.fsync(parent_descriptor)
        except FileExistsError:
            pass
        except OSError as error:
            raise ProtocolError(f"{label} directory cannot be created") from error
        try:
            descriptor = os.open(name, flags, dir_fd=parent_descriptor)
        except OSError as error:
            raise ProtocolError(f"{label} directory cannot be pinned") from error
    except OSError as error:
        raise ProtocolError(f"{label} directory cannot be pinned") from error
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISDIR(observed.st_mode):
            raise ProtocolError(f"{label} directory identity differs")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _open_directory_chain(
    root_descriptor: int,
    parts: tuple[str, ...],
    *,
    create: bool,
    label: str,
) -> int:
    current = os.dup(root_descriptor)
    try:
        for part in parts:
            child = _open_directory_at(
                current,
                part,
                create=create,
                label=label,
            )
            os.close(current)
            current = child
        return current
    except Exception:
        os.close(current)
        raise


def _open_relative_regular(
    root_descriptor: int,
    relative: Path,
    *,
    limit: int,
    label: str,
) -> int:
    parts = _relative_authority_parts(relative, label)
    parent = _open_directory_chain(
        root_descriptor,
        parts[:-1],
        create=False,
        label=label,
    )
    try:
        descriptor = os.open(
            parts[-1],
            os.O_RDONLY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent,
        )
    except OSError as error:
        raise ProtocolError(f"{label} file cannot be pinned") from error
    finally:
        os.close(parent)
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_size < 0
            or observed.st_size > limit
        ):
            raise ProtocolError(f"{label} file identity differs")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


@contextmanager
def _open_relative_regular_temporarily_readable(
    root_descriptor: int,
    relative: Path,
    *,
    limit: int,
    label: str,
) -> Iterator[int]:
    """Pin an owner-readable sealed leaf without mutating its namespace."""

    parent, name = _open_relative_parent(
        root_descriptor,
        relative,
        create=False,
        label=label,
    )
    descriptor: int | None = None
    try:
        try:
            initial = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except OSError as error:
            raise ProtocolError(f"{label} file is unavailable") from error
        if (
            not stat.S_ISREG(initial.st_mode)
            or not initial.st_mode & stat.S_IRUSR
            or initial.st_size < 0
            or initial.st_size > limit
        ):
            raise ProtocolError(f"{label} file identity differs")
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=parent,
            )
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_dev != initial.st_dev
                or opened.st_ino != initial.st_ino
                or opened.st_size != initial.st_size
            ):
                raise ProtocolError(f"{label} file changed before read")
            yield descriptor
        finally:
            if descriptor is not None:
                os.close(descriptor)
    finally:
        os.close(parent)


def _hash_regular_descriptor(
    descriptor: int,
    *,
    limit: int,
    label: str,
) -> tuple[str, int]:
    initial = os.fstat(descriptor)
    if not stat.S_ISREG(initial.st_mode) or initial.st_size > limit:
        raise ProtocolError(f"{label} file identity differs")
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(descriptor, min(1_048_576, limit - size + 1))
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise ProtocolError(f"{label} file exceeds its bound")
        digest.update(chunk)
    final = os.fstat(descriptor)
    if (
        size != initial.st_size
        or final.st_dev != initial.st_dev
        or final.st_ino != initial.st_ino
        or final.st_size != initial.st_size
    ):
        raise ProtocolError(f"{label} file changed during read")
    return digest.hexdigest(), size


def _read_regular_descriptor_bounded(
    descriptor: int,
    *,
    limit: int,
    label: str,
) -> bytes:
    initial = os.fstat(descriptor)
    if not stat.S_ISREG(initial.st_mode) or initial.st_size > limit:
        raise ProtocolError(f"{label} file identity differs")
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = os.read(descriptor, min(1_048_576, limit - size + 1))
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise ProtocolError(f"{label} file exceeds its bound")
        chunks.append(chunk)
    final = os.fstat(descriptor)
    if (
        size != initial.st_size
        or final.st_dev != initial.st_dev
        or final.st_ino != initial.st_ino
        or final.st_size != initial.st_size
    ):
        raise ProtocolError(f"{label} file changed during read")
    return b"".join(chunks)


def _write_all_descriptor(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("sealed descriptor write was incomplete")
        offset += written


def _secure_object_install(
    store_descriptor: int,
    input_descriptor: int,
    *,
    artifact_sha256: str,
    artifact_bytes: int,
) -> None:
    parent = _open_directory_chain(
        store_descriptor,
        ("objects", "sha256", artifact_sha256[:2]),
        create=True,
        label="content-addressed object",
    )
    destination = artifact_sha256
    staging = f"{artifact_sha256}.partial"
    try:
        try:
            existing = os.open(
                destination,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=parent,
            )
        except FileNotFoundError:
            existing = None
        except OSError as error:
            raise ProtocolError("content-addressed object cannot be pinned") from error
        if existing is not None:
            try:
                digest, size = _hash_regular_descriptor(
                    existing,
                    limit=MAX_RAW_BYTES,
                    label="content-addressed object",
                )
                if digest == artifact_sha256 and size == artifact_bytes:
                    os.fsync(existing)
                existing_identity = _authority_identity_from_stat(
                    os.fstat(existing)
                )
            finally:
                os.close(existing)
            if digest != artifact_sha256 or size != artifact_bytes:
                raise ProtocolError("content-addressed object bytes differ")
            try:
                residue = os.open(
                    staging,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=parent,
                )
            except FileNotFoundError:
                residue = None
            except OSError as error:
                raise ProtocolError(
                    "content-addressed staging path is occupied"
                ) from error
            if residue is not None:
                try:
                    if (
                        _authority_identity_from_stat(os.fstat(residue))
                        != existing_identity
                    ):
                        raise ProtocolError(
                            "content-addressed staging path is occupied"
                        )
                    os.fsync(residue)
                finally:
                    os.close(residue)
                os.unlink(staging, dir_fd=parent)
            os.fsync(parent)
            return

        try:
            os.stat(staging, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProtocolError("content-addressed staging path is occupied")

        try:
            staging_descriptor = os.open(
                staging,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                0o400,
                dir_fd=parent,
            )
        except OSError as error:
            raise ProtocolError("content-addressed staging cannot be created") from error
        installed = False
        try:
            os.lseek(input_descriptor, 0, os.SEEK_SET)
            copied_digest = hashlib.sha256()
            copied_size = 0
            while True:
                chunk = os.read(input_descriptor, 1_048_576)
                if not chunk:
                    break
                copied_size += len(chunk)
                if copied_size > MAX_RAW_BYTES:
                    raise ProtocolError("publication input exceeds its bound")
                copied_digest.update(chunk)
                _write_all_descriptor(staging_descriptor, chunk)
            if (
                copied_digest.hexdigest() != artifact_sha256
                or copied_size != artifact_bytes
            ):
                raise ProtocolError("publication input changed during object copy")
            os.fchmod(staging_descriptor, 0o400)
            os.fsync(staging_descriptor)
            staging_identity = _authority_identity_from_stat(
                os.fstat(staging_descriptor)
            )
            try:
                os.link(
                    staging,
                    destination,
                    src_dir_fd=parent,
                    dst_dir_fd=parent,
                    follow_symlinks=False,
                )
                installed = True
            except FileExistsError:
                installed = False
            if installed:
                final_descriptor = os.open(
                    destination,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=parent,
                )
                try:
                    if (
                        _authority_identity_from_stat(os.fstat(final_descriptor))
                        != staging_identity
                    ):
                        raise ProtocolError("installed object identity differs")
                finally:
                    os.close(final_descriptor)
            else:
                existing = os.open(
                    destination,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=parent,
                )
                try:
                    digest, size = _hash_regular_descriptor(
                        existing,
                        limit=MAX_RAW_BYTES,
                        label="content-addressed object",
                    )
                    if digest == artifact_sha256 and size == artifact_bytes:
                        os.fsync(existing)
                finally:
                    os.close(existing)
                if digest != artifact_sha256 or size != artifact_bytes:
                    raise ProtocolError("raced content-addressed object bytes differ")
        finally:
            os.close(staging_descriptor)
            try:
                os.unlink(staging, dir_fd=parent)
            except FileNotFoundError:
                pass
            os.fsync(parent)
    finally:
        os.close(parent)


def _secure_manifest_install(
    repo_descriptor: int,
    *,
    artifact_id: str,
    encoded: bytes,
) -> Path:
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ProtocolError("publication manifest exceeds its bound")
    parent = _open_directory_chain(
        repo_descriptor,
        ("evidence", "manifests", EXPERIMENT_ID),
        create=True,
        label="public manifest",
    )
    name = f"{artifact_id}.json"
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                0o444,
                dir_fd=parent,
            )
        except OSError as error:
            raise ProtocolError("public manifest destination is occupied") from error
        try:
            _write_all_descriptor(descriptor, encoded)
            os.fchmod(descriptor, 0o444)
            os.fsync(descriptor)
        except Exception:
            os.close(descriptor)
            descriptor = None
            try:
                os.unlink(name, dir_fd=parent)
            finally:
                os.fsync(parent)
            raise
        os.close(descriptor)
        descriptor = None
        os.fsync(parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)
    return Path("evidence") / "manifests" / EXPERIMENT_ID / name


def _open_relative_parent(
    root_descriptor: int,
    relative: Path,
    *,
    create: bool,
    label: str,
) -> tuple[int, str]:
    parts = _relative_authority_parts(relative, label)
    parent = _open_directory_chain(
        root_descriptor,
        parts[:-1],
        create=create,
        label=label,
    )
    return parent, parts[-1]


def _write_sealed_bytes_at(
    root_descriptor: int,
    relative: Path,
    value: bytes,
    *,
    limit: int,
    label: str,
) -> None:
    if type(value) is not bytes or not value or len(value) > limit:
        raise ProtocolError(f"{label} sealed payload differs")
    parent, name = _open_relative_parent(
        root_descriptor,
        relative,
        create=True,
        label=label,
    )
    descriptor: int | None = None
    try:
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise RuntimeError(f"sealed output already exists: {name}")
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                0o600,
                dir_fd=parent,
            )
        except FileExistsError as error:
            raise RuntimeError(f"sealed output already exists: {name}") from error
        except OSError as error:
            raise ProtocolError(f"{label} sealed output cannot be created") from error
        _write_all_descriptor(descriptor, value)
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
        os.close(descriptor)
        descriptor = None
        os.fsync(parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def _write_contract_store_sealed_bytes(
    contract: dict[str, Any],
    path_name: str,
    value: bytes,
    *,
    limit: int,
) -> None:
    store = contract.get("store")
    path = contract.get(path_name)
    if not isinstance(store, Path) or not isinstance(path, Path):
        raise ProtocolError("publication store authority path differs")
    try:
        relative = path.relative_to(store)
    except ValueError as error:
        raise ProtocolError("publication store output leaves its authority") from error
    identity = _contract_authority_identity(
        contract,
        "store",
        "evidence store",
    )
    root_descriptor = _open_authority_root(
        store,
        identity,
        "evidence store",
    )
    try:
        _write_sealed_bytes_at(
            root_descriptor,
            relative,
            value,
            limit=limit,
            label=f"publication {path_name}",
        )
    finally:
        os.close(root_descriptor)


def _read_leaf_bounded_at(
    parent_descriptor: int,
    name: str,
    *,
    limit: int,
    label: str,
) -> bytes:
    try:
        initial = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as error:
        raise ProtocolError(f"{label} file is unavailable") from error
    if (
        not stat.S_ISREG(initial.st_mode)
        or not initial.st_mode & stat.S_IRUSR
        or not 0 <= initial.st_size <= limit
    ):
        raise ProtocolError(f"{label} file identity differs")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_descriptor,
        )
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != initial.st_dev
            or opened.st_ino != initial.st_ino
            or opened.st_size != initial.st_size
        ):
            raise ProtocolError(f"{label} file changed before read")
        return _read_regular_descriptor_bounded(
            descriptor,
            limit=limit,
            label=label,
        )
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _install_failure_bytes_at(
    store_descriptor: int,
    relative: Path,
    payload: bytes,
    *,
    limit: int,
) -> bool:
    if type(payload) is not bytes or len(payload) > limit:
        raise ProtocolError("failure preservation payload differs")
    parent, name = _open_relative_parent(
        store_descriptor,
        relative,
        create=True,
        label="failure preservation",
    )
    descriptor: int | None = None
    try:
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            retained = _read_leaf_bounded_at(
                parent,
                name,
                limit=limit,
                label="failure preservation",
            )
            return retained == payload
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                0o400,
                dir_fd=parent,
            )
        except OSError as error:
            raise ProtocolError("failure preservation cannot be installed") from error
        _write_all_descriptor(descriptor, payload)
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
        os.close(descriptor)
        descriptor = None
        os.fsync(parent)
        return True
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def _unlink_publication_source(
    parent_descriptor: int,
    name: str,
    source: Path,
) -> None:
    del source
    os.unlink(name, dir_fd=parent_descriptor)
    os.fsync(parent_descriptor)


def _read_private_seed(repo: Path) -> bytes:
    seed_bytes = _read_regular_file_bounded(
        seed_path(repo),
        PRIVATE_SEED_BYTES,
    )
    if len(seed_bytes) != PRIVATE_SEED_BYTES:
        raise ProtocolError("private anchor derivation material is not 256 bits")
    return seed_bytes


def _read_json_bounded(path: Path, limit: int) -> tuple[dict[str, Any], bytes]:
    payload = _read_regular_file_bounded(path, limit)
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("bounded sealed JSON is invalid") from error
    if type(value) is not dict or canonical_json(value) != payload:
        raise ProtocolError("bounded sealed JSON is not canonical")
    return value, payload


def _load_json_bounded(path: Path, limit: int) -> dict[str, Any]:
    payload = _read_regular_file_bounded(path, limit)
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("bounded JSON is invalid") from error
    if type(value) is not dict:
        raise ProtocolError("bounded JSON is not an object")
    return value


def _write_tracked_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(canonical_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except FileExistsError as error:
        raise RuntimeError(f"tracked output already exists: {path.name}") from error


def validate_acceptance(repo: Path) -> dict[str, Any]:
    acceptance = _load_json_bounded(
        repo / ACCEPTANCE_PATH,
        MAX_ACCEPTANCE_BYTES,
    )
    observed = {
        "acceptance": sha256_file(repo / ACCEPTANCE_PATH),
        "experiment": sha256_file(repo / EXPERIMENT_PATH),
        "protocol": sha256_file(repo / PROTOCOL_PATH),
    }
    expected = {
        "acceptance": ACCEPTANCE_SHA256,
        "experiment": EXPERIMENT_SHA256,
        "protocol": PROTOCOL_SHA256,
    }
    if observed != expected:
        raise ProtocolError("OT-0077 P-frozen bytes differ")
    inherited = {
        logical: sha256_file(repo / logical)
        for logical in INHERITED_SOURCE_SHA256S
    }
    if inherited != INHERITED_SOURCE_SHA256S:
        raise ProtocolError("OT-0077 inherited protocol or learner bytes differ")
    if (
        acceptance.get("schema_version") != 1
        or acceptance.get("experiment_id") != EXPERIMENT_ID
        or acceptance.get("candidate_outputs") is not False
        or acceptance.get("actor_turns") != 0
        or acceptance.get("hosted_model_calls") != 0
        or acceptance.get("derivation", {}).get("anchor_case_count") != 8
        or acceptance.get("derivation", {}).get("authoritative_anchor_attempts") != 1
    ):
        raise ProtocolError("OT-0077 acceptance identity differs")
    return acceptance


def protocol_frozen_paths() -> tuple[Path, ...]:
    return ACCEPTANCE_PATH, EXPERIMENT_PATH, PROTOCOL_PATH


def assert_protocol_unchanged(repo: Path, commit: str) -> None:
    commit = _commit(commit)
    try:
        git_output(
            repo,
            "merge-base",
            "--is-ancestor",
            PROTOCOL_ORIGIN_COMMIT,
            commit,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ProtocolError("OT-0077 implementation does not descend from P") from error
    changed = git_output(
        repo,
        "diff",
        "--name-only",
        f"{PROTOCOL_ORIGIN_COMMIT}..{commit}",
        "--",
        *(path.as_posix() for path in protocol_frozen_paths()),
    )
    if changed:
        raise ProtocolError(f"OT-0077 protocol changed after P: {changed}")


def build_attempt_marker(implementation: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "derivation_id": DERIVATION_ID,
        "attempt_ordinal": 1,
        "implementation_git_commit": _commit(implementation, "implementation"),
        "reseed_permitted": False,
    }


def build_derivation_receipt(
    implementation: str,
    seed_bytes: bytes,
    task_bytes: bytes,
) -> dict[str, Any]:
    implementation = _commit(implementation, "implementation")
    if type(seed_bytes) is not bytes or len(seed_bytes) != 32:
        raise ProtocolError("private anchor derivation material is not 256 bits")
    try:
        task = json.loads(task_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("private anchor task bytes are not JSON") from error
    if canonical_json(task) != task_bytes:
        raise ProtocolError("private anchor task bytes are not canonical")
    validate_task(task)
    if (
        task["purpose"] != "anchor"
        or task["implementation_git_commit"] != implementation
        or task["seed_sha256"] != sha256_bytes(seed_bytes)
    ):
        raise ProtocolError("private anchor task derivation binding differs")
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "derivation_id": DERIVATION_ID,
        "attempt_ordinal": 1,
        "implementation_git_commit": implementation,
        "seed_path": _logical(SEED_RELATIVE_PATH),
        "seed_sha256": sha256_bytes(seed_bytes),
        "seed_bytes": len(seed_bytes),
        "task_path": _logical(TASK_RELATIVE_PATH),
        "task_sha256": sha256_bytes(task_bytes),
        "task_bytes": len(task_bytes),
        "reseed_permitted": False,
    }


def derive(
    repo: Path,
    implementation: str,
    seed_bytes: bytes,
    *,
    write_seed: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    implementation = _commit(implementation, "implementation")
    if type(seed_bytes) is not bytes or len(seed_bytes) != 32:
        raise ProtocolError("private anchor derivation material is not 256 bits")
    task = derive_task(seed_bytes, implementation, purpose="anchor")
    task_bytes = canonical_json(task)
    receipt = build_derivation_receipt(implementation, seed_bytes, task_bytes)
    if write_seed:
        _write_sealed_bytes(seed_path(repo), seed_bytes)
    _write_sealed_bytes(task_path(repo), canonical_json(task))
    _write_sealed_bytes(receipt_path(repo), canonical_json(receipt))
    return task, receipt


def read_derivation(
    repo: Path, implementation: str
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    seed_bytes = _read_private_seed(repo)
    task, task_bytes = _read_json_bounded(
        task_path(repo),
        MAX_DERIVATION_TASK_BYTES,
    )
    receipt, receipt_bytes = _read_json_bounded(
        receipt_path(repo),
        MAX_DERIVATION_RECEIPT_BYTES,
    )
    expected = build_derivation_receipt(implementation, seed_bytes, task_bytes)
    if receipt != expected or receipt_bytes != canonical_json(expected):
        raise ProtocolError("private anchor derivation receipt differs")
    return task, receipt, seed_bytes


def ensure_derivation(
    repo: Path,
    implementation: str,
    *,
    allow_regeneration: bool,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    marker_exists = attempt_path(repo).exists()
    seed_exists = seed_path(repo).exists()
    task_exists = task_path(repo).exists()
    receipt_exists = receipt_path(repo).exists()
    if not seed_exists:
        raise ProtocolError("private attempt marker or derivation material is absent")
    if not marker_exists:
        if not allow_regeneration:
            raise ProtocolError("private attempt marker or derivation material is absent")
        _write_sealed_bytes(
            attempt_path(repo),
            canonical_json(build_attempt_marker(implementation)),
        )
    marker, marker_bytes = _read_json_bounded(
        attempt_path(repo),
        MAX_ATTEMPT_BYTES,
    )
    expected_marker = build_attempt_marker(implementation)
    if marker != expected_marker or marker_bytes != canonical_json(expected_marker):
        raise ProtocolError("private attempt marker differs")
    if task_exists != receipt_exists:
        raise ProtocolError("private task and derivation receipt presence differ")
    if not task_exists:
        if not allow_regeneration:
            raise ProtocolError("authoritative private task and receipt are absent")
        derive(
            repo,
            implementation,
            _read_private_seed(repo),
            write_seed=False,
        )
    return read_derivation(repo, implementation)


def _fixed_input_paths_for_tests(test_paths: list[Path]) -> dict[str, Path]:
    paths: dict[str, Path] = {
        "acceptance_sha256": ACCEPTANCE_PATH,
        "experiment_sha256": EXPERIMENT_PATH,
        "protocol_sha256": PROTOCOL_PATH,
        "ot0075_protocol_sha256": Path(
            "src/open_trajectory_harness/ot0075_protocol.py"
        ),
        "ot0076_protocol_sha256": Path(
            "src/open_trajectory_harness/ot0076_protocol.py"
        ),
        "ot0075_learning_sha256": Path(
            "src/open_trajectory_harness/ot0075_learning.py"
        ),
        "ot0076_plan_sha256": Path(
            "experiments/OT-0076-e14-matched-counterfactual-evaluator-repair.md"
        ),
        "ot0076_acceptance_sha256": Path("spec/ot-0076-acceptance.json"),
        "ot0076_public_probe_sha256": Path(
            "src/open_trajectory_harness/ot0076_design_probe.py"
        ),
        "ot0076_rejection_result_sha256": Path(
            "experiments/OT-0076-e14-matched-counterfactual-evaluator-repair-result.md"
        ),
        "target_sha256": Path("TARGET.md"),
        "red_lines_sha256": Path("RED_LINES.md"),
        "program_sha256": Path("PROGRAM.md"),
        "epoch_sha256": Path("docs/LONGITUDINAL_CONTINUAL_LEARNING_EPOCH.md"),
        "evidence_contract_sha256": Path("docs/EVIDENCE.md"),
        "workflow_sha256": Path("docs/WORKFLOW.md"),
        "research_landscape_sha256": Path("docs/RESEARCH_LANDSCAPE.md"),
        "controller_sha256": Path("src/open_trajectory_harness/ot0077.py"),
        "package_init_sha256": Path("src/open_trajectory_harness/__init__.py"),
        "design_probe_sha256": Path(
            "src/open_trajectory_harness/ot0077_design_probe.py"
        ),
        "learning_sha256": Path("src/open_trajectory_harness/ot0077_learning.py"),
        "receipts_sha256": Path("src/open_trajectory_harness/ot0077_receipts.py"),
        "journal_sha256": Path("src/open_trajectory_harness/ot0077_journal.py"),
        "reset_worker_sha256": Path(
            "src/open_trajectory_harness/ot0077_reset_worker.py"
        ),
        "scorer_sha256": Path("src/open_trajectory_harness/ot0077_scoring.py"),
        "shadow_scorer_sha256": Path(
            "src/open_trajectory_harness/ot0077_shadow_scoring.py"
        ),
        "canonical_helper_sha256": Path("src/open_trajectory_harness/ot0002.py"),
        "sealed_helper_sha256": Path("src/open_trajectory_harness/ot0003.py"),
        "evidence_recorder_sha256": Path(
            "src/open_trajectory_evidence/evidence.py"
        ),
        "evidence_audit_sha256": Path("src/open_trajectory_evidence/audit.py"),
        "evidence_cli_sha256": Path("src/open_trajectory_evidence/cli.py"),
        "dependency_lock_sha256": Path("requirements-test.lock"),
    }
    for relative in sorted(test_paths):
        key = "test_" + relative.as_posix().replace("/", "_").replace(".", "_")
        paths[key + "_sha256"] = relative
    return paths


def fixed_input_paths(repo: Path | None = None) -> dict[str, Path]:
    repo = (repo or Path.cwd()).resolve()
    paths = _fixed_input_paths_for_tests([
        test.relative_to(repo)
        for test in (repo / "tests").glob("test_*.py")
    ])
    missing = [path.as_posix() for path in paths.values() if not (repo / path).is_file()]
    if missing:
        raise ProtocolError(f"fixed implementation inputs are absent: {missing}")
    return paths


def build_run_lock(
    repo: Path,
    implementation: str,
    receipt: dict[str, Any],
    public_checkpoint: dict[str, Any],
) -> dict[str, Any]:
    implementation = _commit(implementation, "implementation")
    fixed = {
        name: sha256_file(repo / path)
        for name, path in fixed_input_paths(repo).items()
    }
    marker_bytes = canonical_json(build_attempt_marker(implementation))
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "protocol_origin_git_commit": PROTOCOL_ORIGIN_COMMIT,
        "implementation_git_commit": implementation,
        "implementation_git_tree": git_output(
            repo, "rev-parse", f"{implementation}^{{tree}}"
        ),
        "derivation_id": DERIVATION_ID,
        "attempt_path": _logical(ATTEMPT_RELATIVE_PATH),
        "attempt_sha256": sha256_bytes(marker_bytes),
        "seed_path": _logical(SEED_RELATIVE_PATH),
        "seed_sha256": _sha(receipt["seed_sha256"], "seed digest"),
        "task_path": _logical(TASK_RELATIVE_PATH),
        "task_sha256": _sha(receipt["task_sha256"], "task digest"),
        "receipt_path": _logical(DERIVATION_RELATIVE_PATH),
        "receipt_sha256": sha256_bytes(canonical_json(receipt)),
        "run_id": DEFAULT_RUN_ID,
        "raw_path": _logical(RAW_RELATIVE_PATH),
        "public_journal_path": _logical(PUBLIC_JOURNAL_RELATIVE_PATH),
        "manifest_path": (
            f"evidence/manifests/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json"
        ),
        "promotion_path": _logical(PROMOTION_RELATIVE_PATH),
        "promotion_manifest_path": (
            f"evidence/manifests/{EXPERIMENT_ID}/{PROMOTION_ARTIFACT_ID}.json"
        ),
        "failure_path": _logical(FAILURE_RELATIVE_PATH),
        "reconstruction_recipe": RECONSTRUCTION_RECIPE,
        "public_checkpoint": _validate_public_checkpoint_receipt(
            public_checkpoint,
            implementation=implementation,
        ),
        "fixed_inputs": fixed,
    }


def _preparation_destinations(repo: Path) -> list[Path]:
    return [
        attempt_path(repo),
        seed_path(repo),
        task_path(repo),
        receipt_path(repo),
        _repository_path(repo, RUN_LOCK_PATH),
        _store_path(repo, PUBLIC_JOURNAL_RELATIVE_PATH),
        _store_path(repo, FAILED_PUBLIC_JOURNAL_RELATIVE_PATH),
        _store_path(repo, PUBLIC_FAILURE_RELATIVE_PATH),
        _store_path(repo, ANCHOR_JOURNAL_RELATIVE_PATH),
        _store_path(repo, FAILED_ANCHOR_JOURNAL_RELATIVE_PATH),
        raw_path(repo),
        _store_path(repo, RAW_STAGING_RELATIVE_PATH),
        _store_path(repo, FAILED_RAW_RELATIVE_PATH),
        _store_path(repo, FAILED_RAW_STAGING_RELATIVE_PATH),
        _store_path(repo, COMPLETION_RELATIVE_PATH),
        _store_path(repo, FAILED_COMPLETION_RELATIVE_PATH),
        _store_path(repo, RECONSTRUCTION_ROOT_RELATIVE_PATH),
        _store_path(repo, FAILED_RECONSTRUCTION_ROOT_RELATIVE_PATH),
        manifest_path(repo),
        promotion_path(repo),
        promotion_manifest_path(repo),
        _store_path(repo, FAILURE_RELATIVE_PATH),
        _store_path(repo, FAILED_MANIFEST_RELATIVE_PATH),
        _store_path(repo, FAILED_PROMOTION_MANIFEST_RELATIVE_PATH),
        _store_path(repo, FAILED_PROMOTION_RELATIVE_PATH),
    ]


def _path_present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _journal_prefix_summary(root: Path) -> dict[str, Any]:
    """Return a bounded, path-free identity for a sealed or incomplete stage."""

    stage = read_stage(root, allow_incomplete=True)
    segment_index = []
    for relative_path, segment in zip(
        stage.segment_relative_paths,
        stage.segments,
        strict=True,
    ):
        segment_index.append(
            {
                "relative_path": relative_path,
                "file_sha256": segment.file_sha256,
                "byte_count": segment.byte_count,
                "sealed": segment.sealed,
                "torn_tail": segment.torn_tail,
                "completed_encounter_count": segment.completed_encounter_count,
                "receipt_prefix_sha256": sha256_bytes(
                    canonical_json(list(segment.receipt_order))
                ),
                "receipt_prefix_count": len(segment.receipt_order),
            }
        )
    relative_files = ["stage-open.otj", *stage.segment_relative_paths]
    if (root / "stage-seal.otj").exists():
        relative_files.append("stage-seal.otj")
    artifact_index = []
    for relative_path in sorted(relative_files):
        path = root / relative_path
        artifact_index.append(
            {
                "relative_path": relative_path,
                "byte_count": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "status": "sealed" if stage.sealed else "incomplete",
        "sealed": stage.sealed,
        "torn_tail": stage.torn_tail,
        "stage_seal_present": stage.stage_seal is not None,
        "segment_count": len(stage.segments),
        "sealed_segment_count": sum(item.sealed for item in stage.segments),
        "completed_encounter_count": sum(
            item.completed_encounter_count for item in stage.segments
        ),
        "receipt_prefix_count": sum(
            len(item.receipt_order) for item in stage.segments
        ),
        "segment_prefix_sha256": sha256_bytes(canonical_json(segment_index)),
        "artifact_file_count": len(artifact_index),
        "artifact_bytes": sum(item["byte_count"] for item in artifact_index),
        "artifact_sha256": sha256_bytes(canonical_json(artifact_index)),
    }


@contextmanager
def _pinned_journal_artifact_snapshot(
    root_descriptor: int,
) -> Iterator[dict[str, bytes]]:
    """Hold every bounded journal leaf through summary and final authority bind."""

    root_generation = _stat_generation(os.fstat(root_descriptor))
    root_names = set(os.listdir(root_descriptor))
    allowed = {STAGE_OPEN_NAME, SEGMENT_DIRECTORY_NAME, STAGE_SEAL_NAME}
    if (
        STAGE_OPEN_NAME not in root_names
        or SEGMENT_DIRECTORY_NAME not in root_names
        or not root_names <= allowed
    ):
        raise JournalError("journal snapshot layout differs")
    segment_descriptor = _open_directory_at(
        root_descriptor,
        SEGMENT_DIRECTORY_NAME,
        create=False,
        label="journal snapshot segments",
    )
    leaf_pins: list[tuple[int, str, int, tuple[int, ...]]] = []
    try:
        segment_generation = _stat_generation(os.fstat(segment_descriptor))
        segment_names = sorted(os.listdir(segment_descriptor))
        if len(segment_names) > MAX_STAGE_SEGMENTS:
            raise JournalError("journal snapshot segment inventory exceeds its bound")
        artifacts: dict[str, bytes] = {}
        remaining = MAX_RAW_BYTES

        def capture(parent: int, name: str, relative: str) -> None:
            nonlocal remaining
            initial = os.stat(name, dir_fd=parent, follow_symlinks=False)
            initial_generation = _stat_generation(initial)
            if (
                not stat.S_ISREG(initial.st_mode)
                or not initial.st_mode & stat.S_IRUSR
                or not 0 <= initial.st_size <= remaining
            ):
                raise ProtocolError("journal snapshot artifact identity differs")
            descriptor = os.open(
                name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=parent,
            )
            try:
                if _stat_generation(os.fstat(descriptor)) != initial_generation:
                    raise ProtocolError("journal snapshot artifact changed while pinning")
                payload = _read_regular_descriptor_bounded(
                    descriptor,
                    limit=remaining,
                    label="journal snapshot artifact",
                )
                if _stat_generation(os.fstat(descriptor)) != initial_generation:
                    raise ProtocolError("journal snapshot artifact changed during capture")
            except Exception:
                os.close(descriptor)
                raise
            leaf_pins.append((parent, name, descriptor, initial_generation))
            artifacts[relative] = payload
            remaining -= len(payload)

        capture(root_descriptor, STAGE_OPEN_NAME, STAGE_OPEN_NAME)
        if STAGE_SEAL_NAME in root_names:
            capture(root_descriptor, STAGE_SEAL_NAME, STAGE_SEAL_NAME)
        for name in segment_names:
            capture(
                segment_descriptor,
                name,
                f"{SEGMENT_DIRECTORY_NAME}/{name}",
            )
        if (
            set(os.listdir(root_descriptor)) != root_names
            or sorted(os.listdir(segment_descriptor)) != segment_names
            or _stat_generation(os.fstat(root_descriptor)) != root_generation
            or _stat_generation(os.fstat(segment_descriptor)) != segment_generation
        ):
            raise ProtocolError("journal snapshot changed during capture")
        yield artifacts
        if (
            set(os.listdir(root_descriptor)) != root_names
            or sorted(os.listdir(segment_descriptor)) != segment_names
            or _stat_generation(os.fstat(root_descriptor)) != root_generation
            or _stat_generation(os.fstat(segment_descriptor)) != segment_generation
        ):
            raise ProtocolError("journal snapshot changed after capture")
        for parent, name, descriptor, expected in leaf_pins:
            if (
                _stat_generation(os.fstat(descriptor)) != expected
                or _stat_generation(
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                )
                != expected
            ):
                raise ProtocolError("journal snapshot artifact changed after capture")
    finally:
        for _parent, _name, descriptor, _expected in reversed(leaf_pins):
            os.close(descriptor)
        os.close(segment_descriptor)


def _journal_prefix_summary_from_artifacts(
    artifacts: dict[str, bytes],
) -> dict[str, Any]:
    """Interpret an immutable private copy of descriptor-captured journal bytes."""

    with tempfile.TemporaryDirectory(prefix="ot0077-journal-snapshot-") as temporary:
        root = Path(temporary) / "journal"
        (root / SEGMENT_DIRECTORY_NAME).mkdir(parents=True)
        for relative, payload in sorted(artifacts.items()):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        return _journal_prefix_summary(root)


def _fsync_directory(path: Path) -> None:
    """Durably commit a directory-entry transition on POSIX filesystems."""

    if os.name != "posix":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _quarantine_encounter_journal(
    source: Path,
    target: Path,
    *,
    expected_store_identity: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Move the exact journal directory through pinned evidence-store authority."""

    if (
        not source.is_absolute()
        or not target.is_absolute()
        or len(source.parents) < 3
        or len(target.parents) < 3
    ):
        raise ProtocolError("journal quarantine path identity differs")
    store = source.parents[2]
    if target.parents[2] != store:
        raise ProtocolError("journal quarantine store identity differs")
    source_relative = source.relative_to(store)
    target_relative = target.relative_to(store)
    if (
        len(source_relative.parts) != 3
        or source_relative.parts[0] not in {"runs", "public"}
        or source_relative.parts[1] != EXPERIMENT_ID
        or len(target_relative.parts) != 3
        or target_relative.parts[:2] != ("failures", EXPERIMENT_ID)
        or source_relative.name != target_relative.name
    ):
        raise ProtocolError("journal quarantine path identity differs")
    store_identity = (
        _authority_root_identity(store, "evidence store")
        if expected_store_identity is None
        else _validated_authority_identity(
            expected_store_identity,
            "evidence store",
        )
    )
    store_descriptor = _open_authority_root(
        store,
        store_identity,
        "evidence store",
    )
    chain_descriptors: list[int] = []
    chain_pins: list[tuple[int, str, int, dict[str, int]]] = []
    source_descriptor: int | None = None
    target_descriptor: int | None = None

    def open_pinned_parent(relative: Path, label: str) -> tuple[int, str]:
        parts = _relative_authority_parts(relative, label)
        current = store_descriptor
        for component in parts[:-1]:
            child = _open_directory_at(
                current,
                component,
                create=True,
                label=label,
            )
            try:
                identity = _authority_identity_from_stat(os.fstat(child))
                if _authority_identity_from_stat(
                    os.stat(component, dir_fd=current, follow_symlinks=False)
                ) != identity:
                    raise ProtocolError(f"{label} directory changed while pinning")
            except Exception:
                os.close(child)
                raise
            chain_descriptors.append(child)
            chain_pins.append((current, component, child, identity))
            current = child
        return current, parts[-1]

    def rebind_chains(generations: dict[int, tuple[int, ...]]) -> None:
        for parent, name, child, identity in chain_pins:
            if (
                _authority_identity_from_stat(os.fstat(child)) != identity
                or _authority_identity_from_stat(
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                )
                != identity
            ):
                raise ProtocolError("journal quarantine chain changed")
        for descriptor, expected in generations.items():
            if _stat_generation(os.fstat(descriptor)) != expected:
                raise ProtocolError("journal quarantine generation changed")

    def summarize_retained(
        *,
        target_parent: int,
        target_name: str,
        target_identity: dict[str, int],
        generations: dict[int, tuple[int, ...]],
    ) -> dict[str, Any]:
        assert target_descriptor is not None

        def bind_target() -> None:
            rebind_chains(generations)
            rebound_store = _open_authority_root(
                store,
                store_identity,
                "evidence store",
            )
            os.close(rebound_store)
            final_target = os.stat(
                target_name,
                dir_fd=target_parent,
                follow_symlinks=False,
            )
            if (
                _authority_identity_from_stat(final_target) != target_identity
                or _authority_identity_from_stat(os.fstat(target_descriptor))
                != target_identity
            ):
                raise ProtocolError("journal quarantine target identity changed")

        retained = {"status": "unreadable", "sealed": False}
        try:
            snapshot = _pinned_journal_artifact_snapshot(target_descriptor)
            with snapshot as artifacts:
                try:
                    retained = _journal_prefix_summary_from_artifacts(artifacts)
                except (JournalError, OSError, ValueError):
                    pass
                bind_target()
        except JournalError:
            pass
        bind_target()
        return {**retained, "quarantined": True}

    try:
        source_parent, source_name = open_pinned_parent(
            source_relative,
            "journal quarantine source",
        )
        target_parent, target_name = open_pinned_parent(
            target_relative,
            "journal quarantine target",
        )
        try:
            source_stat = os.stat(
                source_name,
                dir_fd=source_parent,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            try:
                target_stat = os.stat(
                    target_name,
                    dir_fd=target_parent,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                return {
                    "status": "absent",
                    "sealed": False,
                    "quarantined": False,
                }
            if not stat.S_ISDIR(target_stat.st_mode):
                raise ProtocolError("journal quarantine target is not a directory")
            target_descriptor = _open_directory_at(
                target_parent,
                target_name,
                create=False,
                label="journal quarantine target",
            )
            target_identity = _authority_identity_from_stat(
                os.fstat(target_descriptor)
            )
            if target_identity != _authority_identity_from_stat(target_stat):
                raise ProtocolError("journal quarantine target changed")
            generations = {
                store_descriptor: _stat_generation(os.fstat(store_descriptor)),
                **{
                    descriptor: _stat_generation(os.fstat(descriptor))
                    for descriptor in chain_descriptors
                },
                target_descriptor: _stat_generation(os.fstat(target_descriptor)),
            }
            return summarize_retained(
                target_parent=target_parent,
                target_name=target_name,
                target_identity=target_identity,
                generations=generations,
            )
        if not stat.S_ISDIR(source_stat.st_mode):
            raise ProtocolError("journal quarantine source is not a directory")
        source_descriptor = _open_directory_at(
            source_parent,
            source_name,
            create=False,
            label="journal quarantine source",
        )
        source_identity = _authority_identity_from_stat(os.fstat(source_descriptor))
        if source_identity != _authority_identity_from_stat(source_stat):
            raise ProtocolError("journal quarantine source changed")
        try:
            os.stat(target_name, dir_fd=target_parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise RuntimeError("journal quarantine destination exists")
        pre_move_generations = {
            store_descriptor: _stat_generation(os.fstat(store_descriptor)),
            **{
                descriptor: _stat_generation(os.fstat(descriptor))
                for descriptor in chain_descriptors
            },
            source_descriptor: _stat_generation(os.fstat(source_descriptor)),
        }
        rebind_chains(pre_move_generations)
        if _authority_identity_from_stat(
            os.stat(source_name, dir_fd=source_parent, follow_symlinks=False)
        ) != source_identity:
            raise ProtocolError("journal quarantine source changed")
        try:
            os.rename(
                source_name,
                target_name,
                src_dir_fd=source_parent,
                dst_dir_fd=target_parent,
            )
        except OSError as error:
            raise RuntimeError("encounter journal could not be quarantined") from error
        os.fsync(source_parent)
        os.fsync(target_parent)
        target_descriptor = _open_directory_at(
            target_parent,
            target_name,
            create=False,
            label="journal quarantine target",
        )
        target_identity = _authority_identity_from_stat(os.fstat(target_descriptor))
        if target_identity != source_identity:
            raise ProtocolError("journal quarantine target identity differs")
        try:
            os.stat(source_name, dir_fd=source_parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProtocolError("encounter journal survived quarantine")
        generations = {
            store_descriptor: _stat_generation(os.fstat(store_descriptor)),
            **{
                descriptor: _stat_generation(os.fstat(descriptor))
                for descriptor in chain_descriptors
            },
            source_descriptor: _stat_generation(os.fstat(source_descriptor)),
            target_descriptor: _stat_generation(os.fstat(target_descriptor)),
        }
        return summarize_retained(
            target_parent=target_parent,
            target_name=target_name,
            target_identity=target_identity,
            generations=generations,
        )
    finally:
        if target_descriptor is not None:
            os.close(target_descriptor)
        if source_descriptor is not None:
            os.close(source_descriptor)
        for descriptor in reversed(chain_descriptors):
            os.close(descriptor)
        os.close(store_descriptor)


def _raw_file_summary(path: Path) -> dict[str, Any]:
    """Return a bounded, path-free identity for one unpublished raw file."""

    stat = path.lstat()
    if not path.is_file() or path.is_symlink():
        return {
            "status": "non-regular",
            "byte_count": stat.st_size,
        }
    if stat.st_size > MAX_RAW_BYTES:
        return {
            "status": "oversize",
            "byte_count": stat.st_size,
        }
    return {
        "status": "retained",
        "byte_count": stat.st_size,
        "sha256": sha256_file(path),
    }


def _quarantine_unpublished_raw_file(source: Path, target: Path) -> dict[str, Any]:
    if not source.exists() and not source.is_symlink():
        if target.exists() and not target.is_symlink():
            try:
                retained = _raw_file_summary(target)
            except OSError:
                retained = {"status": "unreadable"}
            return {**retained, "quarantined": True}
        return {"status": "absent", "quarantined": False}
    if target.exists() or target.is_symlink():
        raise RuntimeError("raw quarantine destination exists")
    try:
        before = _raw_file_summary(source)
    except OSError:
        before = {"status": "unreadable"}
    target.parent.mkdir(parents=True, exist_ok=True)
    _fsync_directory(target.parent)
    try:
        source.rename(target)
    except OSError as error:
        raise RuntimeError("unpublished raw file could not be quarantined") from error
    for parent in {source.parent.resolve(), target.parent.resolve()}:
        _fsync_directory(parent)
    if before["status"] != "unreadable":
        after = _raw_file_summary(target)
        if after != before:
            raise RuntimeError("unpublished raw file changed during quarantine")
    return {**before, "quarantined": True}


def _quarantine_raw_transaction(contract: dict[str, Path]) -> dict[str, Any]:
    """Remove both raw surfaces through one pinned evidence-store authority."""

    store = contract.get("store")
    if not isinstance(store, Path):
        raise ProtocolError("raw quarantine store authority differs")
    store_identity = _contract_authority_identity(
        contract,
        "store",
        "evidence store",
    )
    store_descriptor = _open_authority_root(
        store,
        store_identity,
        "evidence store",
    )
    results: dict[str, Any] = {}
    errors: list[Exception] = []

    def relative(name: str) -> Path:
        path = contract.get(name)
        if not isinstance(path, Path):
            raise ProtocolError("raw quarantine path authority differs")
        try:
            return path.relative_to(store)
        except ValueError as error:
            raise ProtocolError("raw quarantine path leaves its store") from error

    def quarantine_leaf(source_relative: Path, target_relative: Path) -> dict[str, Any]:
        source_parent, source_name = _open_relative_parent(
            store_descriptor,
            source_relative,
            create=True,
            label="raw quarantine source",
        )
        try:
            target_parent, target_name = _open_relative_parent(
                store_descriptor,
                target_relative,
                create=True,
                label="raw quarantine target",
            )
        except Exception:
            os.close(source_parent)
            raise
        target_descriptor: int | None = None
        target_generation: tuple[int, ...] | None = None
        try:
            source_parent_identity = _authority_identity_from_stat(
                os.fstat(source_parent)
            )
            target_parent_identity = _authority_identity_from_stat(
                os.fstat(target_parent)
            )
            try:
                source_stat = os.stat(
                    source_name,
                    dir_fd=source_parent,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                try:
                    retained = _read_leaf_bounded_at(
                        target_parent,
                        target_name,
                        limit=MAX_RAW_BYTES,
                        label="retained raw failure evidence",
                    )
                except FileNotFoundError:
                    return {"status": "absent", "quarantined": False}
                except ProtocolError:
                    try:
                        os.stat(
                            target_name,
                            dir_fd=target_parent,
                            follow_symlinks=False,
                        )
                    except FileNotFoundError:
                        return {"status": "absent", "quarantined": False}
                    raise
                return {
                    "status": "retained",
                    "byte_count": len(retained),
                    "sha256": sha256_bytes(retained),
                    "quarantined": True,
                }
            source_generation = _stat_generation(source_stat)
            preservable = bool(
                stat.S_ISREG(source_stat.st_mode)
                and source_stat.st_mode & stat.S_IRUSR
                and 0 <= source_stat.st_size <= MAX_RAW_BYTES
            )
            if preservable:
                payload = _read_leaf_bounded_at(
                    source_parent,
                    source_name,
                    limit=MAX_RAW_BYTES,
                    label="raw failure evidence",
                )
                if not _install_failure_bytes_at(
                    store_descriptor,
                    target_relative,
                    payload,
                    limit=MAX_RAW_BYTES,
                ):
                    raise ProtocolError("raw failure evidence copy differs")
                if (
                    _read_leaf_bounded_at(
                        target_parent,
                        target_name,
                        limit=MAX_RAW_BYTES,
                        label="raw failure evidence copy",
                    )
                    != payload
                ):
                    raise ProtocolError("raw failure evidence readback differs")
                target_descriptor = os.open(
                    target_name,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=target_parent,
                )
                target_generation = _stat_generation(
                    os.fstat(target_descriptor)
                )
                target_digest, target_bytes = _hash_regular_descriptor(
                    target_descriptor,
                    limit=MAX_RAW_BYTES,
                    label="raw failure evidence copy",
                )
                if (
                    target_digest != sha256_bytes(payload)
                    or target_bytes != len(payload)
                ):
                    raise ProtocolError("raw failure evidence pinned copy differs")
                os.fsync(target_descriptor)
                result = {
                    "status": "retained",
                    "byte_count": len(payload),
                    "sha256": sha256_bytes(payload),
                    "quarantined": True,
                }
            else:
                result = {
                    "status": (
                        "oversize"
                        if stat.S_ISREG(source_stat.st_mode)
                        and source_stat.st_size > MAX_RAW_BYTES
                        else "non-regular"
                    ),
                    "byte_count": source_stat.st_size,
                    "quarantined": False,
                }
            rebound_source = os.stat(
                source_name,
                dir_fd=source_parent,
                follow_symlinks=False,
            )
            if _stat_generation(rebound_source) != source_generation:
                raise ProtocolError("raw failure source changed before removal")
            os.unlink(source_name, dir_fd=source_parent)
            os.fsync(source_parent)
            os.fsync(target_parent)
            rebound_source_parent, rebound_source_name = _open_relative_parent(
                store_descriptor,
                source_relative,
                create=False,
                label="raw quarantine source",
            )
            rebound_target_parent, rebound_target_name = _open_relative_parent(
                store_descriptor,
                target_relative,
                create=False,
                label="raw quarantine target",
            )
            try:
                if (
                    rebound_source_name != source_name
                    or rebound_target_name != target_name
                    or _authority_identity_from_stat(os.fstat(rebound_source_parent))
                    != source_parent_identity
                    or _authority_identity_from_stat(os.fstat(rebound_target_parent))
                    != target_parent_identity
                ):
                    raise ProtocolError("raw quarantine parent identity changed")
                try:
                    os.stat(
                        source_name,
                        dir_fd=rebound_source_parent,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    pass
                else:
                    raise ProtocolError("raw authority survived quarantine")
                if preservable:
                    assert target_generation is not None
                    try:
                        current_target = os.stat(
                            target_name,
                            dir_fd=rebound_target_parent,
                            follow_symlinks=False,
                        )
                    except FileNotFoundError:
                        current_target = None
                    if (
                        current_target is None
                        or _stat_generation(current_target) != target_generation
                    ):
                        if current_target is not None:
                            os.unlink(
                                target_name,
                                dir_fd=rebound_target_parent,
                            )
                            os.fsync(rebound_target_parent)
                        if not _install_failure_bytes_at(
                            store_descriptor,
                            target_relative,
                            payload,
                            limit=MAX_RAW_BYTES,
                        ):
                            raise ProtocolError(
                                "raw failure evidence could not be restored"
                            )
                        if target_descriptor is not None:
                            os.close(target_descriptor)
                            target_descriptor = None
                        target_descriptor = os.open(
                            target_name,
                            os.O_RDONLY
                            | os.O_NOFOLLOW
                            | getattr(os, "O_CLOEXEC", 0),
                            dir_fd=rebound_target_parent,
                        )
                        target_generation = _stat_generation(
                            os.fstat(target_descriptor)
                        )
                    final_target = os.stat(
                        target_name,
                        dir_fd=rebound_target_parent,
                        follow_symlinks=False,
                    )
                    if (
                        target_descriptor is None
                        or _stat_generation(os.fstat(target_descriptor))
                        != target_generation
                        or _stat_generation(final_target) != target_generation
                    ):
                        raise ProtocolError(
                            "raw failure evidence changed after source removal"
                        )
                    os.lseek(target_descriptor, 0, os.SEEK_SET)
                    final_digest, final_bytes = _hash_regular_descriptor(
                        target_descriptor,
                        limit=MAX_RAW_BYTES,
                        label="raw failure evidence final copy",
                    )
                    if (
                        final_digest != sha256_bytes(payload)
                        or final_bytes != len(payload)
                    ):
                        raise ProtocolError(
                            "raw failure evidence final bytes differ"
                        )
                    os.fsync(target_descriptor)
            finally:
                os.close(rebound_target_parent)
                os.close(rebound_source_parent)
            return result
        finally:
            if target_descriptor is not None:
                os.close(target_descriptor)
            os.close(target_parent)
            os.close(source_parent)

    try:
        for label, source_key, target_key in (
            ("raw", "raw", "failed_raw"),
            ("staging", "raw_staging", "failed_raw_staging"),
        ):
            try:
                results[label] = quarantine_leaf(
                    relative(source_key),
                    relative(target_key),
                )
            except Exception as error:
                errors.append(error)
                results[label] = {
                    "status": "quarantine-failed",
                    "quarantined": False,
                }
        rebound_store = _open_authority_root(
            store,
            store_identity,
            "evidence store",
        )
        os.close(rebound_store)
        remaining = False
        for source_key in ("raw", "raw_staging"):
            parent: int | None = None
            try:
                parent, name = _open_relative_parent(
                    store_descriptor,
                    relative(source_key),
                    create=False,
                    label="raw quarantine source",
                )
                try:
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    remaining = True
            except FileNotFoundError:
                pass
            finally:
                if parent is not None:
                    os.close(parent)
        if remaining:
            raise RuntimeError("unpublished raw authority could not be removed")
        if errors:
            raise RuntimeError(
                "unpublished raw failure evidence was not fully preserved"
            ) from ExceptionGroup("raw quarantine errors", errors)
        return results
    finally:
        os.close(store_descriptor)


def _quarantine_reconstruction_root(
    source: Path,
    target: Path,
    *,
    expected_store_identity: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Move the exact pinned reconstruction root into failure authority."""

    store = source
    for _part in RECONSTRUCTION_ROOT_RELATIVE_PATH.parts:
        store = store.parent
    expected_source = store / RECONSTRUCTION_ROOT_RELATIVE_PATH
    expected_target = store / FAILED_RECONSTRUCTION_ROOT_RELATIVE_PATH
    if source != expected_source or target != expected_target:
        raise ProtocolError("fresh-root quarantine path identity differs")
    store_identity = (
        _authority_root_identity(store, "evidence store")
        if expected_store_identity is None
        else _validated_authority_identity(
            expected_store_identity,
            "evidence store",
        )
    )
    store_descriptor = _open_authority_root(
        store,
        store_identity,
        "evidence store",
    )
    source_parent: int | None = None
    target_parent: int | None = None
    source_descriptor: int | None = None
    target_descriptor: int | None = None
    chain_descriptors: list[int] = []
    chain_pins: list[tuple[int, str, int, dict[str, int]]] = []

    def open_pinned_parent(relative: Path, label: str) -> tuple[int, str]:
        parts = _relative_authority_parts(relative, label)
        current = store_descriptor
        for component in parts[:-1]:
            child = _open_directory_at(
                current,
                component,
                create=True,
                label=label,
            )
            try:
                identity = _authority_identity_from_stat(os.fstat(child))
                if _authority_identity_from_stat(
                    os.stat(component, dir_fd=current, follow_symlinks=False)
                ) != identity:
                    raise ProtocolError(f"{label} directory changed while pinning")
            except Exception:
                os.close(child)
                raise
            chain_descriptors.append(child)
            chain_pins.append((current, component, child, identity))
            current = child
        return current, parts[-1]

    def rebind_chains() -> None:
        for parent, name, child, identity in chain_pins:
            if (
                _authority_identity_from_stat(os.fstat(child)) != identity
                or _authority_identity_from_stat(
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                )
                != identity
            ):
                raise ProtocolError("fresh-root quarantine chain changed")

    try:
        source_parent, source_name = open_pinned_parent(
            RECONSTRUCTION_ROOT_RELATIVE_PATH,
            "fresh-root reconstruction source",
        )
        target_parent, target_name = open_pinned_parent(
            FAILED_RECONSTRUCTION_ROOT_RELATIVE_PATH,
            "fresh-root reconstruction quarantine",
        )
        try:
            source_stat = os.stat(
                source_name,
                dir_fd=source_parent,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            try:
                retained = os.stat(
                    target_name,
                    dir_fd=target_parent,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                return {"status": "absent", "quarantined": False}
            if not stat.S_ISDIR(retained.st_mode):
                raise ProtocolError(
                    "fresh-root reconstruction quarantine identity differs"
                )
            target_descriptor = _open_directory_at(
                target_parent,
                target_name,
                create=False,
                label="fresh-root reconstruction quarantine",
            )
            target_identity = _authority_identity_from_stat(
                os.fstat(target_descriptor)
            )
            if target_identity != _authority_identity_from_stat(retained):
                raise ProtocolError(
                    "fresh-root reconstruction quarantine identity differs"
                )
            rebind_chains()
            rebound_store = _open_authority_root(
                store,
                store_identity,
                "evidence store",
            )
            os.close(rebound_store)
            final_target = os.stat(
                target_name,
                dir_fd=target_parent,
                follow_symlinks=False,
            )
            if (
                _authority_identity_from_stat(final_target) != target_identity
                or _authority_identity_from_stat(os.fstat(target_descriptor))
                != target_identity
            ):
                raise ProtocolError(
                    "fresh-root reconstruction quarantine identity differs"
                )
            return {"status": "retained", "quarantined": True}
        if not stat.S_ISDIR(source_stat.st_mode):
            raise ProtocolError("fresh-root reconstruction source is not a directory")
        source_descriptor = _open_directory_at(
            source_parent,
            source_name,
            create=False,
            label="fresh-root reconstruction source",
        )
        source_identity = _authority_identity_from_stat(
            os.fstat(source_descriptor)
        )
        if source_identity != _authority_identity_from_stat(source_stat):
            raise ProtocolError("fresh-root reconstruction source changed")
        try:
            os.stat(
                target_name,
                dir_fd=target_parent,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise RuntimeError("fresh-root reconstruction quarantine exists")
        rebind_chains()
        rebound_source = os.stat(
            source_name,
            dir_fd=source_parent,
            follow_symlinks=False,
        )
        if _authority_identity_from_stat(rebound_source) != source_identity:
            raise ProtocolError("fresh-root reconstruction source changed")
        os.rename(
            source_name,
            target_name,
            src_dir_fd=source_parent,
            dst_dir_fd=target_parent,
        )
        os.fsync(source_parent)
        os.fsync(target_parent)
        try:
            os.stat(
                source_name,
                dir_fd=source_parent,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise ProtocolError("fresh-root source survived quarantine")
        retained = os.stat(
            target_name,
            dir_fd=target_parent,
            follow_symlinks=False,
        )
        if _authority_identity_from_stat(retained) != source_identity:
            raise ProtocolError("fresh-root quarantine identity differs")
        target_descriptor = _open_directory_at(
            target_parent,
            target_name,
            create=False,
            label="fresh-root reconstruction quarantine",
        )
        if _authority_identity_from_stat(os.fstat(target_descriptor)) != source_identity:
            raise ProtocolError("fresh-root quarantine identity differs")
        rebind_chains()
        rebound_store = _open_authority_root(
            store,
            store_identity,
            "evidence store",
        )
        os.close(rebound_store)
        final_target = os.stat(
            target_name,
            dir_fd=target_parent,
            follow_symlinks=False,
        )
        if (
            _authority_identity_from_stat(final_target) != source_identity
            or _authority_identity_from_stat(os.fstat(target_descriptor))
            != source_identity
        ):
            raise ProtocolError("fresh-root quarantine identity differs")
        return {"status": "retained", "quarantined": True}
    finally:
        if target_descriptor is not None:
            os.close(target_descriptor)
        if source_descriptor is not None:
            os.close(source_descriptor)
        for descriptor in reversed(chain_descriptors):
            os.close(descriptor)
        os.close(store_descriptor)


def _public_journal_binding_ready(
    repo: Path,
    binding: object,
) -> bool:
    try:
        if type(binding) is not dict:
            return False
        stage = read_stage(
            _store_path(repo, PUBLIC_JOURNAL_RELATIVE_PATH),
            expected_scientific_sha256=binding["scientific_sha256"],
        )
        return bool(
            stage.sealed
            and not stage.torn_tail
            and stage.binding == binding
            and stage.stage_open["purpose"] == "design"
            and stage.stage_open["logical_path"]
            == _logical(PUBLIC_JOURNAL_RELATIVE_PATH)
        )
    except (JournalError, KeyError, TypeError, ValueError, OSError):
        return False


def _write_public_checkpoint_failure(
    repo: Path,
    *,
    code: str,
    journal_summary: dict[str, Any],
) -> None:
    _write_sealed_bytes(
        _store_path(repo, PUBLIC_FAILURE_RELATIVE_PATH),
        canonical_json({
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "run_id": DEFAULT_RUN_ID,
            "operational_failure": code,
            "encounter_journal": copy.deepcopy(journal_summary),
            "private_derivation_started": False,
            "authorized_actor_candidate_count": 0,
        }),
    )


def _assert_preparation_boundary(
    repo: Path,
    implementation: str,
    *,
    expected_public_journal: dict[str, Any] | None = None,
    expected_authorities: dict[str, dict[str, int] | None] | None = None,
    allowed_destinations: frozenset[Path] = frozenset(),
) -> dict[str, dict[str, int] | None]:
    """Recheck every public/private boundary immediately before unsealing."""

    # Apply the same evidence-root confinement as execution before any private
    # destination is considered.  This rejects tracked in-repository roots
    # outside the ignored .evidence subtree.
    contract = output_contract(repo, allow_manifest=False)
    store_identity = contract.get("store_identity")
    authorities: dict[str, dict[str, int] | None] = {
        "repo": _contract_authority_identity(
            contract,
            "repo",
            "repository",
        ),
        "store": (
            None
            if store_identity is None
            else _validated_authority_identity(
                store_identity,
                "evidence store",
            )
        ),
    }
    if expected_authorities is not None and authorities != expected_authorities:
        raise RuntimeError("OT-0077 preparation authority root changed")
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0077 preparation requires clean I")
    if _commit(git_output(repo, "rev-parse", "HEAD"), "implementation") != implementation:
        raise RuntimeError("OT-0077 implementation changed during preparation")
    assert_protocol_unchanged(repo, implementation)
    validate_acceptance(repo)
    destinations = _preparation_destinations(repo)
    public_journal = _store_path(repo, PUBLIC_JOURNAL_RELATIVE_PATH)
    allowed = set(allowed_destinations)
    if expected_public_journal is not None:
        if authorities["store"] is None:
            raise RuntimeError("OT-0077 public evidence store is unavailable")
        allowed.add(public_journal)
    collision_paths = [path for path in destinations if path not in allowed]
    if any(_path_present(path) for path in collision_paths):
        raise RuntimeError("OT-0077 preparation destination exists")
    if expected_public_journal is not None:
        if not _public_journal_binding_ready(repo, expected_public_journal):
            raise RuntimeError(
                "OT-0077 public journal binding changed during preparation"
            )
        if (
            _authority_root_identity(contract["repo"], "repository")
            != authorities["repo"]
            or _authority_root_identity(contract["store"], "evidence store")
            != authorities["store"]
            or not _public_journal_binding_ready(repo, expected_public_journal)
        ):
            raise RuntimeError(
                "OT-0077 public boundary changed during preparation"
            )
    return authorities


def prepare(repo: Path) -> tuple[Path, Path, Path, Path]:
    """Consume OT-0077's sole private derivation attempt from a clean I."""

    repo = repo.resolve()
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0077 preparation requires clean I")
    implementation = _commit(git_output(repo, "rev-parse", "HEAD"), "implementation")
    _assert_preparation_boundary(repo, implementation)
    acceptance = validate_acceptance(repo)
    destinations = _preparation_destinations(repo)
    if any(_path_present(path) for path in destinations):
        raise RuntimeError("OT-0077 preparation destination exists")

    # This complete candidate-free checkpoint is deliberately after every
    # read-only collision check and before the first private write.
    public_checkpoint = assert_public_checkpoint(
        repo,
        implementation=implementation,
        acceptance=acceptance,
    )

    # The checkpoint is deliberately long.  Do not let a concurrent checkout,
    # edit, unsafe evidence-root change, or destination creation move the
    # private boundary while the public oracle is running.
    authorities = _assert_preparation_boundary(
        repo,
        implementation,
        expected_public_journal=public_checkpoint["encounter_journal"],
    )

    marker = build_attempt_marker(implementation)
    _write_sealed_bytes(attempt_path(repo), canonical_json(marker))
    marker_only = frozenset({attempt_path(repo)})
    _assert_preparation_boundary(
        repo,
        implementation,
        expected_public_journal=public_checkpoint["encounter_journal"],
        expected_authorities=authorities,
        allowed_destinations=marker_only,
    )
    seed_bytes = secrets.token_bytes(32)
    _assert_preparation_boundary(
        repo,
        implementation,
        expected_public_journal=public_checkpoint["encounter_journal"],
        expected_authorities=authorities,
        allowed_destinations=marker_only,
    )
    _task, receipt = derive(
        repo,
        implementation,
        seed_bytes,
        write_seed=True,
    )
    private_derivation = frozenset({
        attempt_path(repo),
        seed_path(repo),
        task_path(repo),
        receipt_path(repo),
    })
    _assert_preparation_boundary(
        repo,
        implementation,
        expected_public_journal=public_checkpoint["encounter_journal"],
        expected_authorities=authorities,
        allowed_destinations=private_derivation,
    )
    lock = build_run_lock(repo, implementation, receipt, public_checkpoint)
    _assert_preparation_boundary(
        repo,
        implementation,
        expected_public_journal=public_checkpoint["encounter_journal"],
        expected_authorities=authorities,
        allowed_destinations=private_derivation,
    )
    run_lock = _repository_path(repo, RUN_LOCK_PATH)
    _write_tracked_once(run_lock, lock)
    return attempt_path(repo), seed_path(repo), task_path(repo), run_lock


def validate_run_lock(
    repo: Path,
    execution: str,
    *,
    allow_regeneration: bool,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    lock, _lock_bytes = _read_json_bounded(
        _repository_path(repo, RUN_LOCK_PATH),
        MAX_RUN_LOCK_BYTES,
    )
    required = {
        "schema_version",
        "experiment_id",
        "protocol_origin_git_commit",
        "implementation_git_commit",
        "implementation_git_tree",
        "derivation_id",
        "attempt_path",
        "attempt_sha256",
        "seed_path",
        "seed_sha256",
        "task_path",
        "task_sha256",
        "receipt_path",
        "receipt_sha256",
        "run_id",
        "raw_path",
        "public_journal_path",
        "manifest_path",
        "promotion_path",
        "promotion_manifest_path",
        "failure_path",
        "reconstruction_recipe",
        "public_checkpoint",
        "fixed_inputs",
    }
    _exact(lock, required, "run lock")
    if (
        lock["schema_version"] != 1
        or lock["experiment_id"] != EXPERIMENT_ID
        or lock["protocol_origin_git_commit"] != PROTOCOL_ORIGIN_COMMIT
        or lock["derivation_id"] != DERIVATION_ID
        or lock["run_id"] != DEFAULT_RUN_ID
        or lock["attempt_path"] != _logical(ATTEMPT_RELATIVE_PATH)
        or lock["seed_path"] != _logical(SEED_RELATIVE_PATH)
        or lock["task_path"] != _logical(TASK_RELATIVE_PATH)
        or lock["receipt_path"] != _logical(DERIVATION_RELATIVE_PATH)
        or lock["raw_path"] != _logical(RAW_RELATIVE_PATH)
        or lock["public_journal_path"] != _logical(PUBLIC_JOURNAL_RELATIVE_PATH)
        or lock["manifest_path"]
        != f"evidence/manifests/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json"
        or lock["promotion_path"] != _logical(PROMOTION_RELATIVE_PATH)
        or lock["promotion_manifest_path"]
        != f"evidence/manifests/{EXPERIMENT_ID}/{PROMOTION_ARTIFACT_ID}.json"
        or lock["failure_path"] != _logical(FAILURE_RELATIVE_PATH)
        or lock["reconstruction_recipe"] != RECONSTRUCTION_RECIPE
    ):
        raise ProtocolError("run lock fixed identity differs")
    implementation = _commit(lock["implementation_git_commit"], "implementation")
    _validate_public_checkpoint_receipt(
        lock["public_checkpoint"],
        implementation=implementation,
    )
    if not allow_regeneration and not _public_journal_binding_ready(
        repo, lock["public_checkpoint"]["encounter_journal"]
    ):
        raise ProtocolError("public checkpoint journal no longer matches the run lock")
    execution = _commit(execution, "execution")
    if git_output(
        repo,
        "rev-list",
        "--parents",
        "-n",
        "1",
        execution,
    ).split() != [execution, implementation]:
        raise ProtocolError("L is not the sole direct child of I")
    if (
        git_output(repo, "rev-parse", f"{implementation}^{{tree}}")
        != lock["implementation_git_tree"]
    ):
        raise ProtocolError("I tree differs from lock")
    if (
        git_output(repo, "diff", "--name-status", f"{implementation}..{execution}")
        != f"A\t{RUN_LOCK_PATH.as_posix()}"
    ):
        raise ProtocolError("L differs from I by more than the run lock")
    assert_protocol_unchanged(repo, execution)
    validate_acceptance(repo)
    observed = {
        name: sha256_file(repo / path)
        for name, path in fixed_input_paths(repo).items()
    }
    if observed != lock["fixed_inputs"]:
        raise ProtocolError("fixed implementation inputs differ from lock")
    task, receipt, seed_bytes = ensure_derivation(
        repo,
        implementation,
        allow_regeneration=allow_regeneration,
    )
    marker_bytes = canonical_json(build_attempt_marker(implementation))
    if (
        lock["attempt_sha256"] != sha256_bytes(marker_bytes)
        or lock["seed_sha256"] != sha256_bytes(seed_bytes)
        or lock["task_sha256"] != receipt["task_sha256"]
        or lock["receipt_sha256"] != sha256_bytes(canonical_json(receipt))
    ):
        raise ProtocolError("private derivation identity differs from lock")
    return lock, task, seed_bytes


def _git_blob_bounded(
    repo: Path,
    revision: str,
    path: Path,
    *,
    limit: int,
    label: str,
) -> bytes:
    try:
        result = subprocess.run(
            ["git", "show", f"{revision}:{path.as_posix()}"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ProtocolError(f"{label} historical bytes are unavailable") from error
    if len(result.stdout) > limit:
        raise ProtocolError(f"{label} historical bytes exceed their bound")
    return result.stdout


def _validate_historical_execution_provenance(
    repo: Path,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Bind a durable completion to the exact historical P -> I -> L chain."""

    implementation = _commit(
        raw.get("implementation_git_commit"),
        "historical implementation",
    )
    execution = _commit(
        raw.get("execution_git_commit"),
        "historical execution",
    )
    assert_protocol_unchanged(repo, implementation)
    assert_protocol_unchanged(repo, execution)
    parents = git_output(
        repo,
        "rev-list",
        "--parents",
        "-n",
        "1",
        execution,
    ).split()
    if parents != [execution, implementation]:
        raise ProtocolError("L is not the sole direct child of I")
    if (
        git_output(repo, "diff", "--name-status", f"{implementation}..{execution}")
        != f"A\t{RUN_LOCK_PATH.as_posix()}"
    ):
        raise ProtocolError("historical L differs from I by more than the run lock")
    lock_bytes = _git_blob_bounded(
        repo,
        execution,
        RUN_LOCK_PATH,
        limit=MAX_RUN_LOCK_BYTES,
        label="run lock",
    )
    try:
        lock = json.loads(lock_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("historical run lock is invalid") from error
    required = {
        "schema_version",
        "experiment_id",
        "protocol_origin_git_commit",
        "implementation_git_commit",
        "implementation_git_tree",
        "derivation_id",
        "attempt_path",
        "attempt_sha256",
        "seed_path",
        "seed_sha256",
        "task_path",
        "task_sha256",
        "receipt_path",
        "receipt_sha256",
        "run_id",
        "raw_path",
        "public_journal_path",
        "manifest_path",
        "promotion_path",
        "promotion_manifest_path",
        "failure_path",
        "reconstruction_recipe",
        "public_checkpoint",
        "fixed_inputs",
    }
    _exact(lock, required, "historical run lock")
    if canonical_json(lock) != lock_bytes:
        raise ProtocolError("historical run lock encoding differs")
    if (
        lock["schema_version"] != 1
        or lock["experiment_id"] != EXPERIMENT_ID
        or lock["protocol_origin_git_commit"] != PROTOCOL_ORIGIN_COMMIT
        or lock["implementation_git_commit"] != implementation
        or lock["implementation_git_tree"]
        != git_output(repo, "rev-parse", f"{implementation}^{{tree}}")
        or lock["derivation_id"] != DERIVATION_ID
        or lock["run_id"] != DEFAULT_RUN_ID
        or lock["attempt_path"] != _logical(ATTEMPT_RELATIVE_PATH)
        or lock["seed_path"] != _logical(SEED_RELATIVE_PATH)
        or lock["task_path"] != _logical(TASK_RELATIVE_PATH)
        or lock["receipt_path"] != _logical(DERIVATION_RELATIVE_PATH)
        or lock["raw_path"] != _logical(RAW_RELATIVE_PATH)
        or lock["public_journal_path"] != _logical(PUBLIC_JOURNAL_RELATIVE_PATH)
        or lock["manifest_path"]
        != f"evidence/manifests/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json"
        or lock["promotion_path"] != _logical(PROMOTION_RELATIVE_PATH)
        or lock["promotion_manifest_path"]
        != f"evidence/manifests/{EXPERIMENT_ID}/{PROMOTION_ARTIFACT_ID}.json"
        or lock["failure_path"] != _logical(FAILURE_RELATIVE_PATH)
        or lock["reconstruction_recipe"] != RECONSTRUCTION_RECIPE
    ):
        raise ProtocolError("historical run lock identity differs")
    for key in ("attempt_sha256", "seed_sha256", "task_sha256", "receipt_sha256"):
        _sha(lock[key], f"historical {key}")
    _validate_public_checkpoint_receipt(
        lock["public_checkpoint"],
        implementation=implementation,
    )
    historical_test_listing = git_output(
        repo,
        "ls-tree",
        "-r",
        "--name-only",
        implementation,
        "--",
        "tests",
    ).splitlines()
    test_paths = [
        Path(item)
        for item in historical_test_listing
        if Path(item).parent == Path("tests")
        and Path(item).name.startswith("test_")
        and Path(item).suffix == ".py"
    ]
    fixed_paths = _fixed_input_paths_for_tests(test_paths)
    if type(lock["fixed_inputs"]) is not dict or set(lock["fixed_inputs"]) != set(
        fixed_paths
    ):
        raise ProtocolError("historical fixed-input inventory differs")
    observed_fixed = {
        name: sha256_bytes(
            _git_blob_bounded(
                repo,
                implementation,
                path,
                limit=MAX_UNCOMPRESSED_RAW_BYTES,
                label="fixed implementation input",
            )
        )
        for name, path in fixed_paths.items()
    }
    if observed_fixed != lock["fixed_inputs"]:
        raise ProtocolError("historical fixed implementation bytes differ")
    if (
        lock["task_sha256"] != raw["scientific"].get("task_sha256")
        or raw["scientific"].get("task", {}).get("implementation_git_commit")
        != implementation
    ):
        raise ProtocolError("historical run-lock task binding differs")
    return lock


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _output_paths(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    store = _store(repo).resolve()
    if _is_relative_to(store, repo) and not _is_relative_to(
        store, (repo / ".evidence").resolve()
    ):
        raise RuntimeError("in-repository evidence root must be .evidence")
    contract: dict[str, Any] = {
        "repo": repo,
        "store": store,
        "raw": raw_path(repo),
        "raw_staging": _confined_child(
            store, RAW_STAGING_RELATIVE_PATH, "evidence root"
        ),
        "failed_raw": _confined_child(
            store, FAILED_RAW_RELATIVE_PATH, "evidence root"
        ),
        "failed_raw_staging": _confined_child(
            store, FAILED_RAW_STAGING_RELATIVE_PATH, "evidence root"
        ),
        "completion": _confined_child(
            store, COMPLETION_RELATIVE_PATH, "evidence root"
        ),
        "failed_completion": _confined_child(
            store, FAILED_COMPLETION_RELATIVE_PATH, "evidence root"
        ),
        "reconstruction_root": _confined_child(
            store, RECONSTRUCTION_ROOT_RELATIVE_PATH, "evidence root"
        ),
        "failed_reconstruction_root": _confined_child(
            store,
            FAILED_RECONSTRUCTION_ROOT_RELATIVE_PATH,
            "evidence root",
        ),
        "manifest": manifest_path(repo),
        "promotion": promotion_path(repo),
        "promotion_manifest": promotion_manifest_path(repo),
        "journal": _confined_child(
            store, ANCHOR_JOURNAL_RELATIVE_PATH, "evidence root"
        ),
        "failed_journal": _confined_child(
            store, FAILED_ANCHOR_JOURNAL_RELATIVE_PATH, "evidence root"
        ),
        "failure": _confined_child(
            store, FAILURE_RELATIVE_PATH, "evidence root"
        ),
        "failed_manifest": _confined_child(
            store, FAILED_MANIFEST_RELATIVE_PATH, "evidence root"
        ),
        "failed_promotion_manifest": _confined_child(
            store,
            FAILED_PROMOTION_MANIFEST_RELATIVE_PATH,
            "evidence root",
        ),
        "failed_promotion": _confined_child(
            store, FAILED_PROMOTION_RELATIVE_PATH, "evidence root"
        ),
    }
    contract["repo_identity"] = _available_authority_identity(
        repo,
        "repository",
    )
    contract["store_identity"] = _available_authority_identity(
        store,
        "evidence store",
    )
    return contract


def output_contract(repo: Path, *, allow_manifest: bool) -> dict[str, Any]:
    contract = _output_paths(repo)
    if _path_present(contract["raw"]):
        raise RuntimeError("raw output exists")
    if _path_present(contract["raw_staging"]):
        raise RuntimeError("raw staging output exists")
    if _path_present(contract["completion"]):
        raise RuntimeError("publication completion witness exists")
    if _path_present(contract["reconstruction_root"]):
        raise RuntimeError("fresh-root reconstruction transaction exists")
    if _path_present(contract["manifest"]) and not allow_manifest:
        raise RuntimeError("public manifest exists")
    if _path_present(contract["promotion"]):
        raise RuntimeError("promotion decision exists")
    if _path_present(contract["promotion_manifest"]) and not allow_manifest:
        raise RuntimeError("promotion manifest exists")
    if _path_present(contract["journal"]):
        raise RuntimeError("encounter journal exists")
    if (
        _path_present(contract["failure"])
        or _path_present(contract["failed_raw"])
        or _path_present(contract["failed_raw_staging"])
        or _path_present(contract["failed_completion"])
        or _path_present(contract["failed_reconstruction_root"])
        or _path_present(contract["failed_journal"])
        or _path_present(contract["failed_manifest"])
        or _path_present(contract["failed_promotion_manifest"])
        or _path_present(contract["failed_promotion"])
    ):
        raise RuntimeError("failure authority exists")
    return contract


def _failure_journal_summary_ready(value: object) -> bool:
    if value is None:
        return True
    if type(value) is not dict:
        return False
    status = value.get("status")
    if status in {"absent", "unreadable"}:
        return bool(
            set(value) == {"status", "sealed", "quarantined"}
            and value["sealed"] is False
            and type(value["quarantined"]) is bool
        )
    keys = {
        "status",
        "sealed",
        "torn_tail",
        "stage_seal_present",
        "segment_count",
        "sealed_segment_count",
        "completed_encounter_count",
        "receipt_prefix_count",
        "segment_prefix_sha256",
        "artifact_file_count",
        "artifact_bytes",
        "artifact_sha256",
        "quarantined",
    }
    return bool(
        status in {"sealed", "incomplete"}
        and set(value) == keys
        and value["sealed"] is (status == "sealed")
        and all(
            type(value[name]) is bool
            for name in ("torn_tail", "stage_seal_present", "quarantined")
        )
        and value["quarantined"] is True
        and all(
            type(value[name]) is int and value[name] >= 0
            for name in (
                "segment_count",
                "sealed_segment_count",
                "completed_encounter_count",
                "receipt_prefix_count",
                "artifact_file_count",
                "artifact_bytes",
            )
        )
        and all(
            type(value[name]) is str and _SHA256.fullmatch(value[name]) is not None
            for name in ("segment_prefix_sha256", "artifact_sha256")
        )
    )


def _failure_raw_item_ready(value: object) -> bool:
    if type(value) is not dict or type(value.get("status")) is not str:
        return False
    status = value["status"]
    if status in {"absent", "quarantine-failed"}:
        return bool(
            set(value) == {"status", "quarantined"}
            and type(value["quarantined"]) is bool
        )
    if status == "retained":
        return bool(
            set(value) == {"status", "byte_count", "sha256", "quarantined"}
            and type(value["byte_count"]) is int
            and value["byte_count"] >= 0
            and type(value["sha256"]) is str
            and _SHA256.fullmatch(value["sha256"]) is not None
            and value["quarantined"] is True
        )
    if status in {"oversize", "non-regular"}:
        return bool(
            set(value) == {"status", "byte_count", "quarantined"}
            and type(value["byte_count"]) is int
            and value["byte_count"] >= 0
            and value["quarantined"] is False
        )
    return False


def _failure_raw_transaction_ready(value: object) -> bool:
    return bool(
        value is None
        or (
            type(value) is dict
            and set(value) == {"raw", "staging"}
            and _failure_raw_item_ready(value["raw"])
            and _failure_raw_item_ready(value["staging"])
        )
    )


def _failure_reconstruction_transaction_ready(value: object) -> bool:
    return bool(
        value is None
        or (
            type(value) is dict
            and set(value) == {"status", "quarantined"}
            and value["status"] in {"absent", "retained"}
            and type(value["quarantined"]) is bool
            and value["quarantined"] is (value["status"] == "retained")
        )
    )


def _failure_receipt_ready(
    contract: dict[str, Any],
    *,
    expected_code: str,
) -> bool:
    """Accept only a context-exact, descriptor-read failure receipt."""

    if type(expected_code) is not str or not 0 < len(expected_code) <= 128:
        return False
    store = contract.get("store")
    failure = contract.get("failure")
    if not isinstance(store, Path) or not isinstance(failure, Path):
        return False
    try:
        relative = failure.relative_to(store)
        store_identity = _contract_authority_identity(
            contract,
            "store",
            "evidence store",
        )
        store_descriptor = _open_authority_root(
            store,
            store_identity,
            "evidence store",
        )
        try:
            descriptor = _open_relative_regular(
                store_descriptor,
                relative,
                limit=MAX_COMPLETION_BYTES,
                label="failure receipt",
            )
            try:
                encoded = _read_regular_descriptor_bounded(
                    descriptor,
                    limit=MAX_COMPLETION_BYTES,
                    label="failure receipt",
                )
            finally:
                os.close(descriptor)
        finally:
            os.close(store_descriptor)
        value = json.loads(encoded)
        receipt = _exact(
            value,
            {
                "schema_version",
                "experiment_id",
                "run_id",
                "operational_failure",
                "public_manifest_retained",
                "authoritative_raw_retained",
                "encounter_journal",
                "raw_transaction",
                "reconstruction_transaction",
                "authorized_actor_candidate_count",
            },
            "failure receipt",
        )
        if canonical_json(receipt) != encoded:
            return False
        return bool(
            receipt["schema_version"] == 1
            and receipt["experiment_id"] == EXPERIMENT_ID
            and receipt["run_id"] == DEFAULT_RUN_ID
            and receipt["operational_failure"] == expected_code
            and receipt["public_manifest_retained"] is False
            and type(receipt["authoritative_raw_retained"]) is bool
            and _failure_journal_summary_ready(receipt["encounter_journal"])
            and _failure_raw_transaction_ready(receipt["raw_transaction"])
            and _failure_reconstruction_transaction_ready(
                receipt["reconstruction_transaction"]
            )
            and receipt["authorized_actor_candidate_count"] == 0
        )
    except (
        KeyError,
        OSError,
        ProtocolError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return False


def _recover_incomplete_startup(repo: Path) -> bool:
    """Finish any interrupted calibration or publication quarantine."""

    contract = _output_paths(repo)
    authority_sources = (
        contract["journal"],
        contract["raw"],
        contract["raw_staging"],
        contract["manifest"],
        contract["promotion"],
        contract["promotion_manifest"],
        contract["completion"],
        contract["reconstruction_root"],
    )
    recovery_outputs = (
        contract["failed_journal"],
        contract["failed_raw"],
        contract["failed_raw_staging"],
        contract["failed_manifest"],
        contract["failed_promotion"],
        contract["failed_promotion_manifest"],
        contract["failed_completion"],
        contract["failed_reconstruction_root"],
        contract["failure"],
    )
    if not any(
        path.exists() or path.is_symlink()
        for path in (*authority_sources, *recovery_outputs)
    ):
        return False
    if _publication_completion_ready(contract):
        return False
    publication_interrupted = any(
        path.exists() or path.is_symlink()
        for path in (
            contract["manifest"],
            contract["promotion"],
            contract["promotion_manifest"],
            contract["completion"],
            contract["failed_manifest"],
            contract["failed_promotion"],
            contract["failed_promotion_manifest"],
            contract["failed_completion"],
        )
    )
    recovery_code = (
        "interrupted_publication_recovered_at_startup"
        if publication_interrupted
        else "interrupted_calibration_recovered_at_startup"
    )
    if _failure_receipt_ready(
        contract,
        expected_code=recovery_code,
    ) and not any(
        path.exists() or path.is_symlink() for path in authority_sources
    ):
        return False
    errors: list[Exception] = []
    raw_transaction: dict[str, Any] | None = None
    reconstruction_transaction: dict[str, Any] | None = None
    journal_summary: dict[str, Any] | None = None
    try:
        _quarantine_publication(contract)
    except Exception as error:
        errors.append(error)
    try:
        raw_transaction = _quarantine_raw_transaction(contract)
    except Exception as error:
        errors.append(error)
    try:
        reconstruction_transaction = _quarantine_reconstruction_root(
            contract["reconstruction_root"],
            contract["failed_reconstruction_root"],
            expected_store_identity=_contract_authority_identity(
                contract,
                "store",
                "evidence store",
            ),
        )
    except Exception as error:
        errors.append(error)
    try:
        journal_summary = _quarantine_encounter_journal(
            contract["journal"],
            contract["failed_journal"],
            expected_store_identity=_contract_authority_identity(
                contract,
                "store",
                "evidence store",
            ),
        )
    except Exception as error:
        errors.append(error)
    try:
        if not _failure_receipt_ready(contract, expected_code=recovery_code):
            _failure(
                contract,
                code=recovery_code,
                authoritative_raw=contract["raw"],
                journal_summary=journal_summary,
                raw_transaction=raw_transaction,
                reconstruction_transaction=reconstruction_transaction,
            )
    except Exception as error:
        errors.append(error)
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise RuntimeError(
            "startup recovery evidence was not fully preserved"
        ) from ExceptionGroup("startup recovery errors", errors)
    return True


def locked_context(
    repo: Path,
    *,
    allow_regeneration: bool,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    if git_output(repo, "status", "--porcelain=v1"):
        raise RuntimeError("OT-0077 execution requires clean L")
    execution = _commit(git_output(repo, "rev-parse", "HEAD"), "execution")
    acceptance = validate_acceptance(repo)
    lock, task, _seed = validate_run_lock(
        repo,
        execution,
        allow_regeneration=allow_regeneration,
    )
    return execution, lock, task, acceptance


# The scientific execution functions are defined below the implementation
# helpers.  Keeping lifecycle identity above them makes the P/I/L boundary easy
# to audit and lets unit tests exercise private derivation without running the
# full 242-encounter calibration.


def _flatten_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for episode in case["episodes"]:
        for event in episode["events"]:
            events.append(
                {
                    "episode_index": episode["episode_index"],
                    "encounter_index": event["encounter_index"],
                    "public_query": copy.deepcopy(event["public_query"]),
                    "outcome": event["outcome"],
                }
            )
    if len(events) != case["horizon"]:
        raise ProtocolError("case event flattening differs from the frozen horizon")
    return events


def _descriptor_identity(
    task_digest: str,
    case_id: str,
    descriptor: tuple[str, str, str | None, str | None],
) -> str:
    return derive_identity("condition", task_digest, case_id, *descriptor)


def _mechanism_for(
    descriptor: tuple[str, str, str | None, str | None],
) -> str | None:
    role, mechanism_id, reference_id, _intervention_id = descriptor
    if role in {"positive-reference", "required-control", "adaptive-comparator"}:
        if mechanism_id == "offline-best-fixed-rule":
            return None
        return mechanism_id
    if role == "matched-frozen-control":
        if reference_id not in {COMPACT_REFERENCE, LOG_REFERENCE}:
            raise ProtocolError("matched-frozen reference is unavailable")
        return reference_id
    if role in {"causal-intervention", "recurrence-intervention"}:
        return reference_id
    if role == "identity-placebo":
        return IMMUTABLE_SEED_CONTROL
    raise ProtocolError("condition role is unavailable")


def _lineage_class(role: str) -> str:
    return {
        "positive-reference": ONLINE_POSITIVE,
        "required-control": "required-nonlearning-control",
        "matched-frozen-control": "required-nonlearning-control",
        "adaptive-comparator": "adaptive-comparator",
        "causal-intervention": "causal-intervention",
        "recurrence-intervention": "causal-intervention",
        "identity-placebo": "identity-placebo",
    }[role]


def _environment_fingerprint(execution_commit: str) -> dict[str, Any]:
    return {
        "architecture": platform.machine(),
        "git_commit": _commit(execution_commit, "execution"),
        "git_dirty": False,
        "os_family": platform.system(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }


def _consumer_facts(
    *,
    execution_commit: str,
    task_digest: str,
    case_id: str,
    condition_id: str,
    branch_token: str,
    encounter_index: int,
    mode: str,
) -> dict[str, Any]:
    identities = _consumer_challenge_identities(
        execution_commit=execution_commit,
        task_digest=task_digest,
        case_id=case_id,
        condition_id=condition_id,
        branch_token=branch_token,
        encounter_index=encounter_index,
        mode=mode,
    )
    return {
        "environment_fingerprint": _environment_fingerprint(execution_commit),
        **identities,
    }


def _consumer_challenge_identities(
    *,
    execution_commit: str,
    task_digest: str,
    case_id: str,
    condition_id: str,
    branch_token: str,
    encounter_index: int,
    mode: str,
) -> dict[str, Any]:
    """Derive every runtime challenge from the exact consumer context."""

    process_challenge = derive_identity(
        "process-instance",
        execution_commit,
        task_digest,
        case_id,
        condition_id,
        branch_token,
        encounter_index,
        mode,
    )
    workspace_challenge = derive_identity(
        "workspace-instance",
        process_challenge,
        "empty-before-after",
    )
    nonce = derive_identity(
        "forbidden-channel-nonce",
        task_digest,
        case_id,
        condition_id,
        branch_token,
        encounter_index,
        mode,
    )
    return {
        "process_challenge_sha256": process_challenge,
        "sentinel_challenges": [
            {
                "channel": channel,
                "sentinel_sha256": derive_identity("sentinel", nonce, channel),
            }
            for channel in SENTINEL_CHANNELS
        ],
        "workspace_challenge_sha256": workspace_challenge,
    }


def _unexecuted_sentinel_results(challenge: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "channel": item["channel"],
            "checked": False,
            "observed": False,
            "planted": False,
            "sentinel_sha256": item["sentinel_sha256"],
        }
        for item in challenge["sentinel_challenges"]
    ]


class _ForbiddenSentinelPlant:
    """Plant seven parent-only channel values and check the child surface once."""

    def __init__(self, challenge: dict[str, Any], root: Path) -> None:
        self._challenge = challenge
        self._root = root
        self._values = {
            item["channel"]: bytes.fromhex(item["sentinel_sha256"])
            for item in challenge["sentinel_challenges"]
        }
        self._planted = {channel: False for channel in SENTINEL_CHANNELS}
        self._cache: bytearray | None = None
        self._filesystem: Path | None = None
        self._network: tuple[socket.socket, socket.socket] | None = None
        self._response_chain: list[bytes] | None = None
        self._subprocess_pipe: tuple[int, int] | None = None
        self._task_loader: dict[str, bytes] | None = None
        self._tool: Any | None = None

    def __enter__(self) -> _ForbiddenSentinelPlant:
        try:
            self._cache = bytearray(self._values["controller-cache"])
            self._planted["controller-cache"] = True
        except OSError:
            pass
        try:
            self._filesystem = self._root / "forbidden-filesystem-sentinel.bin"
            self._filesystem.write_bytes(self._values["filesystem"])
            self._planted["filesystem"] = True
        except OSError:
            pass
        try:
            reader, writer = socket.socketpair()
            reader.set_inheritable(False)
            writer.set_inheritable(False)
            writer.sendall(self._values["network"])
            self._network = (reader, writer)
            self._planted["network"] = True
        except OSError:
            if "reader" in locals():
                reader.close()
            if "writer" in locals():
                writer.close()
        try:
            self._response_chain = [self._values["response-chain"]]
            self._planted["response-chain"] = True
        except OSError:
            pass
        try:
            read_descriptor, write_descriptor = os.pipe()
            os.set_inheritable(read_descriptor, False)
            os.set_inheritable(write_descriptor, False)
            os.write(write_descriptor, self._values["subprocess"])
            self._subprocess_pipe = (read_descriptor, write_descriptor)
            self._planted["subprocess"] = True
        except OSError:
            for descriptor in (
                locals().get("read_descriptor"),
                locals().get("write_descriptor"),
            ):
                if type(descriptor) is int:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
        try:
            self._task_loader = {"opaque": self._values["task-loader"]}
            self._planted["task-loader"] = True
        except OSError:
            pass
        try:
            tool_value = self._values["tools"]
            self._tool = lambda: tool_value
            self._planted["tools"] = True
        except OSError:
            pass
        return self

    @property
    def ready(self) -> bool:
        return all(self._planted.values())

    @staticmethod
    def _representations(value: bytes) -> tuple[bytes, ...]:
        standard = base64.b64encode(value)
        urlsafe = base64.urlsafe_b64encode(value)
        candidates = (
            value,
            value.hex().encode("ascii"),
            value.hex().upper().encode("ascii"),
            standard,
            standard.rstrip(b"="),
            urlsafe,
            urlsafe.rstrip(b"="),
        )
        return tuple(dict.fromkeys(item for item in candidates if item))

    @staticmethod
    def _socket_value(endpoint: socket.socket, expected: int) -> bytes:
        endpoint.settimeout(0.1)
        chunks = bytearray()
        while len(chunks) < expected:
            chunk = endpoint.recv(expected - len(chunks))
            if not chunk:
                break
            chunks.extend(chunk)
        return bytes(chunks)

    @staticmethod
    def _pipe_value(descriptor: int, expected: int) -> bytes:
        os.set_blocking(descriptor, False)
        chunks = bytearray()
        while len(chunks) < expected:
            try:
                chunk = os.read(descriptor, expected - len(chunks))
            except BlockingIOError:
                break
            if not chunk:
                break
            chunks.extend(chunk)
        return bytes(chunks)

    def results(
        self,
        *,
        request: bytes,
        stdout: bytes,
        stderr: bytes,
    ) -> list[dict[str, Any]]:
        checked = {channel: False for channel in SENTINEL_CHANNELS}
        try:
            checked["controller-cache"] = (
                self._cache is not None
                and bytes(self._cache) == self._values["controller-cache"]
            )
        except (OSError, ValueError):
            pass
        try:
            checked["filesystem"] = (
                self._filesystem is not None
                and self._filesystem.read_bytes() == self._values["filesystem"]
            )
        except (OSError, ValueError):
            pass
        try:
            if self._network is not None:
                checked["network"] = (
                    self._socket_value(
                        self._network[0], len(self._values["network"])
                    )
                    == self._values["network"]
                )
        except (OSError, ValueError):
            pass
        try:
            checked["response-chain"] = (
                self._response_chain == [self._values["response-chain"]]
            )
        except (OSError, ValueError):
            pass
        try:
            if self._subprocess_pipe is not None:
                checked["subprocess"] = (
                    self._pipe_value(
                        self._subprocess_pipe[0], len(self._values["subprocess"])
                    )
                    == self._values["subprocess"]
                )
        except (OSError, ValueError):
            pass
        try:
            checked["task-loader"] = (
                self._task_loader == {"opaque": self._values["task-loader"]}
            )
        except (OSError, ValueError):
            pass
        try:
            checked["tools"] = (
                self._tool is not None
                and self._tool() == self._values["tools"]
            )
        except (OSError, ValueError):
            pass
        exposed = request + stdout + stderr
        challenge_by_channel = {
            item["channel"]: item["sentinel_sha256"]
            for item in self._challenge["sentinel_challenges"]
        }
        return [
            {
                "channel": channel,
                "checked": checked[channel],
                "observed": any(
                    representation in exposed
                    for representation in self._representations(self._values[channel])
                ),
                "planted": self._planted[channel],
                "sentinel_sha256": challenge_by_channel[channel],
            }
            for channel in SENTINEL_CHANNELS
        ]

    def __exit__(self, *_args: object) -> None:
        if self._network is not None:
            for endpoint in self._network:
                endpoint.close()
        if self._subprocess_pipe is not None:
            for descriptor in self._subprocess_pipe:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _finalize_consumer_observation(
    challenge: dict[str, Any],
    consumer: dict[str, Any],
) -> dict[str, Any]:
    """Bind a retained attempt to runtime-produced receipt facts."""

    facts = make_consumer_facts(
        process_challenge_sha256=challenge["process_challenge_sha256"],
        workspace_challenge_sha256=challenge["workspace_challenge_sha256"],
        response_bytes=consumer["response_bytes"],
        descriptor_audit_pass=consumer["descriptor_audit_pass"],
        attempt_status=consumer["attempt_status"],
        failure_code=consumer["failure_code"],
        prediction_status=consumer["prediction_status"],
        process_boundary=consumer["process_boundary"],
        process_started=consumer["process_started"],
        fresh_process_verified=consumer["fresh_process_verified"],
        workspace_observed=consumer["workspace_empty_after"] is True,
        environment_fingerprint=challenge["environment_fingerprint"],
        sentinel_results=consumer["sentinel_results"],
    )
    return {**consumer, "consumer_facts": facts}


def _ensure_consumer_observation(
    challenge: dict[str, Any],
    consumer: dict[str, Any],
) -> dict[str, Any]:
    if "consumer_facts" in consumer:
        return consumer
    value = dict(consumer)
    value.setdefault("descriptor_audit_pass", False)
    value.setdefault("sentinel_results", _unexecuted_sentinel_results(challenge))
    return _finalize_consumer_observation(challenge, value)


def _worker_environment(repo: Path) -> dict[str, str]:
    python_paths = [str(repo.resolve() / "src")]
    for item in sys.path:
        if not item:
            continue
        candidate = Path(item).resolve()
        if (
            candidate.is_dir()
            and any(part in {"site-packages", "dist-packages"} for part in candidate.parts)
            and str(candidate) not in python_paths
        ):
            python_paths.append(str(candidate))
    return {
        "LANG": "C",
        "LC_ALL": "C",
        "OT0077_SURFACE": "strict-online-v1",
        "PATH": os.defpath,
        "PYTHONHASHSEED": "0",
        # The controller subprocess needs locked test/audit dependencies even
        # under -S.  Consumers expose only environment names, and the learner
        # call graph receives neither this mapping nor its values.
        "PYTHONPATH": os.pathsep.join(python_paths),
        "__CF_USER_TEXT_ENCODING": "0x0:0:0",
    }


def _payload_blind_forkserver(repo: Path) -> Any | None:
    """Start one immutable-code-only forkserver before any encounter sentinel.

    CPython sends only file descriptors to the server.  The serialized Process
    object (including an encounter envelope) is written to a dedicated child
    bootstrap pipe after the server has forked.  The preload-PID handshake
    makes silent preload failure fail closed instead of importing on demand.
    """

    global _FORKSERVER_CONTEXT, _FORKSERVER_READY
    # Python's hash secret is fixed at interpreter start, so clearing a child
    # environment after fork is too late.  macOS rewrites the value of
    # __CF_USER_TEXT_ENCODING at process launch; compare every other frozen
    # value and independently compare this interpreter's hash result to a
    # fresh PYTHONHASHSEED=0 probe.  Ordinary developer/test shells take the
    # semantically equal one-exec fallback.
    expected_environment = _worker_environment(repo)
    controller_environment = dict(expected_environment)
    if os.environ.get(_AUTHORITY_GROUP_ENV) == "1":
        controller_environment[_AUTHORITY_GROUP_ENV] = "1"
    if (
        os.name != "posix"
        or "forkserver" not in multiprocessing.get_all_start_methods()
        or set(os.environ) != set(controller_environment)
        or any(
            os.environ[name] != value
            for name, value in controller_environment.items()
            if name != "__CF_USER_TEXT_ENCODING"
        )
    ):
        return None
    probe_text = "OT-0077-deterministic-forkserver-probe"
    hash_probe = _communicate_bounded(
        [
            sys.executable,
            "-S",
            "-c",
            f"print(hash({probe_text!r}))",
        ],
        repo=repo,
        deadline=time.monotonic() + 5,
        environment=expected_environment,
    )
    if (
        hash_probe["status"] != "completed"
        or hash_probe["returncode"] != 0
        or hash_probe["stderr"]
        or hash_probe["stdout"] != f"{hash(probe_text)}\n".encode("ascii")
    ):
        return None
    with _FORKSERVER_LOCK:
        if _FORKSERVER_READY:
            return _FORKSERVER_CONTEXT
        context = multiprocessing.get_context("forkserver")
        context.set_forkserver_preload(
            ["open_trajectory_harness.ot0077_reset_worker"]
        )
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(
            target=forkserver_probe,
            args=(sender,),
            daemon=False,
            name="ot0077-payload-blind-preload-probe",
        )
        started = False
        try:
            with _FORKSERVER_PROCESS_LOCK:
                process.start()
                started = True
            sender.close()
            if not receiver.poll(10):
                with _FORKSERVER_PROCESS_LOCK:
                    if process.is_alive():
                        try:
                            process.kill()
                        except OSError:
                            pass
                    process.join(5)
                raise ProtocolError("payload-blind forkserver probe timed out")
            payload = receiver.recv_bytes(4_096)
            with _FORKSERVER_PROCESS_LOCK:
                process.join(5)
                process_alive = process.is_alive()
                if process_alive:
                    try:
                        process.kill()
                    except OSError:
                        pass
                    process.join(5)
                    process_alive = process.is_alive()
                process_exitcode = process.exitcode
                process_pid = process.pid
            if process_alive:
                raise ProtocolError("payload-blind forkserver probe did not exit")
            try:
                probe = json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ProtocolError("payload-blind forkserver probe is invalid") from error
            if (
                process_exitcode != 0
                or type(probe) is not dict
                or set(probe) != {"preloaded", "worker_pid"}
                or canonical_json(probe) != payload
                or probe["preloaded"] is not True
                or type(probe["worker_pid"]) is not int
                or probe["worker_pid"] != process_pid
            ):
                raise ProtocolError("payload-blind forkserver preload differs")
        except (OSError, EOFError, RuntimeError, ValueError) as error:
            if started:
                with _FORKSERVER_PROCESS_LOCK:
                    if process.is_alive():
                        try:
                            process.kill()
                        except OSError:
                            pass
                    process.join(5)
            raise ProtocolError("payload-blind forkserver startup failed") from error
        finally:
            if not started:
                sender.close()
            receiver.close()
            if started:
                with _FORKSERVER_PROCESS_LOCK:
                    if process.is_alive():
                        try:
                            process.kill()
                        except OSError:
                            pass
                        process.join(5)
                    if not process.is_alive():
                        process.close()
        _FORKSERVER_CONTEXT = context
        _FORKSERVER_READY = True
        return context


def _decode_forkserver_packet(
    payload: bytes,
    *,
    process_pid: int,
) -> dict[str, Any]:
    try:
        packet = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("forked consumer packet is invalid") from error
    if (
        type(packet) is not dict
        or set(packet)
        != {
            "fd_audit_pass",
            "preloaded",
            "returncode",
            "stderr_base64",
            "stdout_base64",
            "worker_pid",
        }
        or canonical_json(packet) != payload
        or packet["fd_audit_pass"] is not True
        or packet["preloaded"] is not True
        or packet["returncode"] not in {0, 2}
        or packet["worker_pid"] != process_pid
    ):
        raise ProtocolError("forked consumer packet identity differs")
    try:
        stdout = base64.b64decode(packet["stdout_base64"], validate=True)
        stderr = base64.b64decode(packet["stderr_base64"], validate=True)
    except (TypeError, ValueError) as error:
        raise ProtocolError("forked consumer packet encoding differs") from error
    if (
        base64.b64encode(stdout).decode("ascii") != packet["stdout_base64"]
        or base64.b64encode(stderr).decode("ascii") != packet["stderr_base64"]
        or len(stdout) > 65_536
        or len(stderr) > 1_024
        or (packet["returncode"] == 0 and (not stdout or stderr))
        or (packet["returncode"] == 2 and (stdout or not stderr))
    ):
        raise ProtocolError("forked consumer packet output differs")
    return {
        "descriptor_audit_pass": True,
        "fresh_process_verified": True,
        "process_boundary": "payload-blind-forkserver",
        "status": "completed",
        "returncode": packet["returncode"],
        "stdout": stdout,
        "stderr": stderr,
    }


def _run_forked_consumer(
    context: Any,
    *,
    request: bytes,
    workspace: Path,
    environment: dict[str, str],
    deadline: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run one child while serializing CPython's global Process bookkeeping."""

    return _run_forked_consumer_slot(
        context,
        request=request,
        workspace=workspace,
        environment=environment,
        deadline=deadline,
        timeout_seconds=timeout_seconds,
    )


def _run_forked_consumer_slot(
    context: Any,
    *,
    request: bytes,
    workspace: Path,
    environment: dict[str, str],
    deadline: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Fork, deliver one envelope post-fork, receive once, and reap."""

    remaining = min(timeout_seconds, deadline - time.monotonic())
    if remaining <= 0:
        return {"status": "timeout", "returncode": None, "stdout": b"", "stderr": b""}
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=forkserver_consume,
        args=(request, str(workspace), environment, sender),
        daemon=False,
        name="ot0077-one-encounter-consumer",
    )
    started = False
    try:
        try:
            with _FORKSERVER_PROCESS_LOCK:
                process.start()
                started = True
        except (OSError, RuntimeError, ValueError):
            return {
                "status": "spawn-failed",
                "returncode": None,
                "stdout": b"",
                "stderr": b"",
            }
        finally:
            sender.close()
        remaining = min(timeout_seconds, deadline - time.monotonic())
        if remaining <= 0 or not receiver.poll(remaining):
            with _FORKSERVER_PROCESS_LOCK:
                if process.is_alive():
                    try:
                        process.kill()
                    except OSError:
                        pass
                process.join(5)
            return {
                "status": "timeout",
                "returncode": None,
                "stdout": b"",
                "stderr": b"",
            }
        try:
            payload = receiver.recv_bytes(69_632)
        except (EOFError, OSError):
            with _FORKSERVER_PROCESS_LOCK:
                process.join(5)
            return {
                "status": "io-failed",
                "returncode": None,
                "stdout": b"",
                "stderr": b"",
            }
        with _FORKSERVER_PROCESS_LOCK:
            process.join(max(0.0, min(5.0, deadline - time.monotonic())))
            process_alive = process.is_alive()
            if process_alive:
                try:
                    process.kill()
                except OSError:
                    pass
                process.join(5)
                process_alive = process.is_alive()
            process_exitcode = process.exitcode
            process_pid = process.pid
        if process_alive:
            return {
                "status": "timeout",
                "returncode": None,
                "stdout": b"",
                "stderr": b"",
            }
        if not receiver.poll(0):
            return {
                "status": "io-failed",
                "returncode": None,
                "stdout": b"",
                "stderr": b"",
            }
        try:
            receiver.recv_bytes(1)
        except EOFError:
            pass
        except OSError:
            return {
                "status": "io-failed",
                "returncode": None,
                "stdout": b"",
                "stderr": b"",
            }
        else:
            return {
                "status": "io-failed",
                "returncode": None,
                "stdout": b"",
                "stderr": b"",
            }
        if process_exitcode != 0 or process_pid is None:
            return {
                "status": "child-failed",
                "returncode": process_exitcode,
                "stdout": b"",
                "stderr": b"",
            }
        return _decode_forkserver_packet(payload, process_pid=process_pid)
    finally:
        receiver.close()
        if not started:
            try:
                sender.close()
            except OSError:
                pass
        if started:
            with _FORKSERVER_PROCESS_LOCK:
                if process.is_alive():
                    try:
                        process.kill()
                    except OSError:
                        pass
                    process.join(5)
                if not process.is_alive():
                    process.close()


def _run_exec_consumer(
    repo: Path,
    *,
    request: bytes,
    workspace: Path,
    deadline: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Portable one-exec fallback; it remains semantically fresh but slower."""

    consumer_deadline = min(
        deadline,
        time.monotonic() + max(0.001, timeout_seconds),
    )
    inside_authority_group = bool(
        os.name == "posix"
        and os.environ.get(_AUTHORITY_GROUP_ENV) == "1"
        and os.getpgrp() == os.getsid(0)
    )
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-S",
                "-m",
                "open_trajectory_harness.ot0077_reset_worker",
            ],
            cwd=workspace,
            env=_worker_environment(repo),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == "posix" and not inside_authority_group,
        )
    except OSError:
        return {
            "fresh_process_verified": False,
            "process_boundary": "unstarted",
            "status": "spawn-failed",
            "returncode": None,
            "stdout": b"",
            "stderr": b"",
        }
    captured = _capture_process_bounded(
        process,
        input_bytes=request,
        deadline=consumer_deadline,
        stdout_limit=MAX_CONSUMER_STDOUT_BYTES,
        stderr_limit=MAX_CONSUMER_STDERR_BYTES,
        inside_authority_group=inside_authority_group,
        invalidate_authority_group=False,
    )
    return {
        "fresh_process_verified": True,
        "process_boundary": "one-exec",
        **captured,
    }


def _validate_worker_response(
    value: object,
    *,
    mechanism: str,
    case_id: str,
    condition_id: str,
    lineage_id: str,
    consumer_id: str,
    encounter_index: int,
    mode: str,
    public_query: dict[str, Any] | None,
    projection: bytes,
) -> dict[str, Any]:
    response = _exact(
        value,
        {
            "schema_version",
            "experiment_id",
            "mechanism_id",
            "mode",
            "case_id",
            "condition_id",
            "lineage_id",
            "consumer_id",
            "encounter_index",
            "projection_sha256",
            "public_query_sha256",
            "prediction",
            "prediction_operations",
            "state_bytes",
            "candidate_count",
            "descriptor_audit_pass",
            "workspace_empty_before",
            "workspace_empty_after",
            "environment_names",
            "environment_allowlist_pass",
            "response_chain_absent",
        },
        "fresh consumer response",
    )
    if (
        response["schema_version"] != 1
        or response["experiment_id"] != EXPERIMENT_ID
        or response["descriptor_audit_pass"] is not True
        or response["mechanism_id"] != mechanism
        or response["mode"] != mode
        or response["case_id"] != case_id
        or response["condition_id"] != condition_id
        or response["lineage_id"] != lineage_id
        or response["consumer_id"] != consumer_id
        or response["encounter_index"] != encounter_index
        or response["projection_sha256"] != sha256_bytes(projection)
        or response["public_query_sha256"]
        != (
            sha256_bytes(canonical_json(public_query))
            if mode == "prediction"
            else None
        )
        or response["workspace_empty_before"] is not True
        or response["workspace_empty_after"] is not True
        or response["environment_allowlist_pass"] is not True
        or response["response_chain_absent"] is not True
        or response["environment_names"]
        != [
            "LANG",
            "LC_ALL",
            "OT0077_SURFACE",
            "PATH",
            "PYTHONHASHSEED",
            "PYTHONPATH",
            "__CF_USER_TEXT_ENCODING",
        ]
    ):
        raise ProtocolError("fresh consumer response identity differs")
    prediction = response["prediction"]
    if mode == "prediction":
        if type(prediction) is not int or prediction not in {0, 1}:
            raise ProtocolError("fresh consumer prediction is not a bit")
    elif prediction is not None:
        raise ProtocolError("terminal audit emitted a prediction")
    for name in ("prediction_operations", "state_bytes", "candidate_count"):
        if type(response[name]) is not int or response[name] < 0:
            raise ProtocolError(f"fresh consumer {name} is malformed")
    return response


def run_fresh_consumer(
    repo: Path,
    *,
    mechanism: str,
    case_id: str,
    condition_id: str,
    lineage_id: str,
    encounter_index: int,
    mode: str,
    public_query: dict[str, Any] | None,
    projection: bytes,
    facts: dict[str, Any],
    timeout_seconds: float = 2.0,
    allow_learning_rejection: bool = False,
    deadline: float | None = None,
    cancel_event: threading.Event | None = None,
    fork_context: Any = _FORK_CONTEXT_UNSET,
    worker_environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute exactly one prediction or terminal audit in a new process."""

    if fork_context is _FORK_CONTEXT_UNSET:
        fork_context = _payload_blind_forkserver(repo)
    if worker_environment is None:
        worker_environment = _worker_environment(repo)
    consumer_id = facts["process_challenge_sha256"]
    envelope = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "mechanism_id": mechanism,
        "mode": mode,
        "case_id": case_id,
        "condition_id": condition_id,
        "lineage_id": lineage_id,
        "consumer_id": consumer_id,
        "encounter_index": encounter_index,
        "public_query": public_query,
        "projection_base64": base64.b64encode(projection).decode("ascii"),
    }
    request = canonical_json(envelope)
    if deadline is None:
        deadline = time.monotonic() + timeout_seconds
    if cancel_event is None:
        cancel_event = threading.Event()

    def absent(
        status: str,
        code: str,
        *,
        process_started: bool,
        workspace_empty_after: bool | None,
        process_boundary: str,
        fresh_process_verified: bool,
        descriptor_audit_pass: bool,
        sentinel_results: list[dict[str, Any]],
        response_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        if response_bytes is None:
            response_bytes = canonical_json(
                {
                    "consumer_request_sha256": sha256_bytes(request),
                    "failure_code": code,
                    "status": status,
                }
            )
        result = {
            "attempt_status": status,
            "failure_code": code,
            "prediction_status": status,
            "prediction": None,
            "prediction_operations": 0,
            "state_bytes": len(projection),
            "candidate_count": 0,
            "response_bytes": response_bytes,
            "response_sha256": sha256_bytes(response_bytes),
            "learning_rejected": False,
            "process_boundary": process_boundary,
            "process_started": process_started,
            "fresh_process_verified": fresh_process_verified,
            "descriptor_audit_pass": descriptor_audit_pass,
            "sentinel_results": sentinel_results,
            "workspace_empty_after": workspace_empty_after,
            "sentinel_absent": all(
                item["observed"] is False for item in sentinel_results
            ),
        }
        return _finalize_consumer_observation(facts, result)

    remaining = deadline - time.monotonic()
    if cancel_event.is_set() or remaining <= 0:
        return absent(
            "missing",
            "stage-deadline-unstarted",
            process_started=False,
            workspace_empty_after=None,
            process_boundary="unstarted",
            fresh_process_verified=False,
            descriptor_audit_pass=False,
            sentinel_results=_unexecuted_sentinel_results(facts),
        )
    with tempfile.TemporaryDirectory(prefix="ot0077-consumer-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        workspace.mkdir()
        with _ForbiddenSentinelPlant(facts, root) as sentinel_plant:
            if not sentinel_plant.ready:
                sentinel_results = sentinel_plant.results(
                    request=request,
                    stdout=b"",
                    stderr=b"",
                )
                return absent(
                    "missing",
                    "sentinel-runtime-incomplete",
                    process_started=False,
                    workspace_empty_after=True,
                    process_boundary="unstarted",
                    fresh_process_verified=False,
                    descriptor_audit_pass=False,
                    sentinel_results=sentinel_results,
                )
            process = (
                _run_forked_consumer(
                    fork_context,
                    request=request,
                    workspace=workspace,
                    environment=worker_environment,
                    deadline=deadline,
                    timeout_seconds=timeout_seconds,
                )
                if fork_context is not None
                else _run_exec_consumer(
                    repo,
                    request=request,
                    workspace=workspace,
                    deadline=deadline,
                    timeout_seconds=timeout_seconds,
                )
            )
            sentinel_results = sentinel_plant.results(
                request=request,
                stdout=process["stdout"],
                stderr=process["stderr"],
            )
        process_started = process["status"] != "spawn-failed"
        process_boundary = process.get(
            "process_boundary",
            "payload-blind-forkserver"
            if fork_context is not None and process_started
            else ("one-exec" if process_started else "unstarted"),
        )
        fresh_process_verified = process.get(
            "fresh_process_verified",
            process_started,
        )
        descriptor_audit_pass = process.get("descriptor_audit_pass", False)
        workspace_empty = not any(workspace.iterdir())
        if process["status"] == "timeout":
            if not workspace_empty:
                raise ProtocolError("timed-out fresh consumer changed its workspace")
            return absent(
                "timeout",
                "consumer-timeout",
                process_started=True,
                workspace_empty_after=True,
                process_boundary=process_boundary,
                fresh_process_verified=fresh_process_verified,
                descriptor_audit_pass=descriptor_audit_pass,
                sentinel_results=sentinel_results,
            )
        if process["status"] != "completed":
            if not workspace_empty:
                raise ProtocolError("missing fresh consumer changed its workspace")
            return absent(
                "missing",
                "consumer-missing",
                process_started=process_started,
                workspace_empty_after=True,
                process_boundary=process_boundary,
                fresh_process_verified=fresh_process_verified,
                descriptor_audit_pass=descriptor_audit_pass,
                sentinel_results=sentinel_results,
                response_bytes=process["stdout"] + process["stderr"],
            )
        observed_sentinel = any(item["observed"] for item in sentinel_results)
        incomplete_sentinel = not all(
            item["planted"] is True and item["checked"] is True
            for item in sentinel_results
        )
        if observed_sentinel or incomplete_sentinel:
            return absent(
                "missing",
                (
                    "forbidden-sentinel-observed"
                    if observed_sentinel
                    else "sentinel-runtime-incomplete"
                ),
                process_started=process_started,
                workspace_empty_after=workspace_empty,
                process_boundary=process_boundary,
                fresh_process_verified=fresh_process_verified,
                descriptor_audit_pass=descriptor_audit_pass,
                sentinel_results=sentinel_results,
                response_bytes=process["stdout"] + process["stderr"],
            )
        if process["returncode"] != 0 or process["stderr"]:
            exec_audit = canonical_json({"descriptor_audit_pass": True})
            expected_rejection = (
                allow_learning_rejection
                and process["returncode"] == 2
                and process["stdout"] in (b"", exec_audit)
                and process["stderr"] == b"consumer rejected: learning-error\n"
                and (
                    process_boundary != "one-exec"
                    or process["stdout"] == exec_audit
                )
            )
            if not expected_rejection:
                if not workspace_empty:
                    raise ProtocolError("failed fresh consumer changed its workspace")
                return absent(
                    "missing",
                    "consumer-missing",
                    process_started=True,
                    workspace_empty_after=True,
                    process_boundary=process_boundary,
                    fresh_process_verified=fresh_process_verified,
                    descriptor_audit_pass=descriptor_audit_pass,
                    sentinel_results=sentinel_results,
                    response_bytes=process["stderr"],
                )
            if not workspace_empty:
                raise ProtocolError("rejected fresh consumer changed its workspace")
            result = {
                "attempt_status": "completed",
                "failure_code": None,
                "prediction_status": "invalid",
                "prediction": None,
                "prediction_operations": 0,
                "state_bytes": len(projection),
                "candidate_count": 0,
                "response_bytes": process["stderr"],
                "response_sha256": sha256_bytes(process["stderr"]),
                "learning_rejected": True,
                "process_boundary": process_boundary,
                "process_started": True,
                "fresh_process_verified": fresh_process_verified,
                "descriptor_audit_pass": (
                    descriptor_audit_pass or process["stdout"] == exec_audit
                ),
                "sentinel_results": sentinel_results,
                "workspace_empty_after": True,
                "sentinel_absent": True,
            }
            return _finalize_consumer_observation(facts, result)
        if not workspace_empty:
            raise ProtocolError("fresh consumer changed its empty workspace")
        try:
            response = json.loads(process["stdout"])
        except (UnicodeDecodeError, json.JSONDecodeError):
            return absent(
                "missing",
                "consumer-missing",
                process_started=True,
                workspace_empty_after=True,
                process_boundary=process_boundary,
                fresh_process_verified=fresh_process_verified,
                descriptor_audit_pass=descriptor_audit_pass,
                sentinel_results=sentinel_results,
                response_bytes=process["stdout"],
            )
        if process["stdout"] != canonical_json(response):
            raise ProtocolError("fresh consumer response is not canonical")
        checked = _validate_worker_response(
            response,
            mechanism=mechanism,
            case_id=case_id,
            condition_id=condition_id,
            lineage_id=lineage_id,
            consumer_id=consumer_id,
            encounter_index=encounter_index,
            mode=mode,
            public_query=public_query,
            projection=projection,
        )
        result = {
            **checked,
            "attempt_status": "completed",
            "failure_code": None,
            "prediction_status": "valid",
            "response_bytes": process["stdout"],
            "response_sha256": sha256_bytes(process["stdout"]),
            "learning_rejected": False,
            "process_boundary": process_boundary,
            "process_started": True,
            "fresh_process_verified": fresh_process_verified,
            "descriptor_audit_pass": checked["descriptor_audit_pass"],
            "sentinel_results": sentinel_results,
            "workspace_empty_after": True,
            "sentinel_absent": True,
        }
        return _finalize_consumer_observation(facts, result)


def _run_in_process_consumer(
    *,
    mechanism: str,
    projection: bytes,
    public_query: dict[str, Any] | None,
    mode: str,
) -> dict[str, Any]:
    if mode == "terminal-audit":
        state = decode_state(mechanism, projection)
        if encode_state(mechanism, state) != projection:
            raise ProtocolError("in-process terminal projection did not round trip")
        response_bytes = canonical_json(
            {
                "mode": "terminal-audit",
                "projection_sha256": sha256_bytes(projection),
                "runtime": "in-process",
            }
        )
        return {
            "attempt_status": "completed",
            "failure_code": None,
            "prediction_status": "valid",
            "prediction": None,
            "prediction_operations": 0,
            "state_bytes": len(projection),
            "candidate_count": 0,
            "response_bytes": response_bytes,
            "response_sha256": sha256_bytes(response_bytes),
            "learning_rejected": False,
            "process_boundary": "in-process",
            "process_started": False,
            "fresh_process_verified": False,
            "descriptor_audit_pass": False,
            "workspace_empty_after": None,
            "sentinel_absent": True,
        }
    if public_query is None:
        raise ProtocolError("in-process prediction query is absent")
    result = predict(mechanism, projection, public_query)
    response_bytes = canonical_json(
        {
            "mechanism_id": mechanism,
            "prediction": result.prediction,
            "projection_sha256": sha256_bytes(projection),
            "public_query_sha256": sha256_bytes(canonical_json(public_query)),
            "runtime": "in-process",
        }
    )
    return {
        "attempt_status": "completed",
        "failure_code": None,
        "prediction_status": "valid",
        "prediction": result.prediction,
        "prediction_operations": result.operations,
        "state_bytes": result.state_bytes,
        "candidate_count": result.candidate_count,
        "response_bytes": response_bytes,
        "response_sha256": sha256_bytes(response_bytes),
        "learning_rejected": False,
        "process_boundary": "in-process",
        "process_started": False,
        "fresh_process_verified": False,
        "descriptor_audit_pass": False,
        "workspace_empty_after": None,
        "sentinel_absent": True,
    }


def _controller_absence(
    *,
    projection: bytes,
    condition_id: str,
    encounter_index: int,
    mode: str,
    status: str = "missing",
    failure_code: str = "stage-deadline-unstarted",
) -> dict[str, Any]:
    response_bytes = canonical_json(
        {
            "condition_id": condition_id,
            "encounter_index": encounter_index,
            "failure_code": failure_code,
            "mode": mode,
            "projection_sha256": sha256_bytes(projection),
            "status": status,
        }
    )
    return {
        "attempt_status": status,
        "failure_code": failure_code,
        "prediction_status": status,
        "prediction": None,
        "prediction_operations": 0,
        "state_bytes": len(projection),
        "candidate_count": 0,
        "response_bytes": response_bytes,
        "response_sha256": sha256_bytes(response_bytes),
        "learning_rejected": False,
        "process_boundary": "unstarted",
        "process_started": False,
        "fresh_process_verified": False,
        "descriptor_audit_pass": False,
        "workspace_empty_after": None,
        "sentinel_absent": True,
    }


def _consumer_attempt_record(
    consumer: dict[str, Any],
    *,
    encounter_index: int,
    mode: str,
) -> dict[str, Any]:
    return {
        "attempt_status": consumer["attempt_status"],
        "descriptor_audit_pass": consumer["descriptor_audit_pass"],
        "encounter_index": encounter_index,
        "failure_code": consumer["failure_code"],
        "fresh_process_verified": consumer["fresh_process_verified"],
        "mode": mode,
        "process_boundary": consumer["process_boundary"],
        "process_started": consumer["process_started"],
        "response_sha256": consumer["response_sha256"],
        "sentinel_absent": consumer["sentinel_absent"],
        "workspace_empty_after": consumer["workspace_empty_after"],
    }


def _execute_online_condition(
    repo: Path,
    *,
    execution_commit: str,
    task_digest: str,
    case: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
    use_fresh_processes: bool,
    deadline: float | None = None,
    cancel_event: threading.Event | None = None,
    fork_context: Any = _FORK_CONTEXT_UNSET,
    worker_environment: dict[str, str] | None = None,
    journal: SegmentedEncounterJournal | None = None,
    journal_scope: str = "main",
) -> dict[str, Any]:
    role, mechanism_id, reference_id, intervention_id = descriptor
    mechanism = _mechanism_for(descriptor)
    if mechanism is None or intervention_id == "wrong-lineage-projection":
        raise ProtocolError("condition is not an online executable lineage")
    condition_id = _descriptor_identity(task_digest, case["case_id"], descriptor)
    if deadline is None:
        deadline = time.monotonic() + CALIBRATION_SECONDS
    if cancel_event is None:
        cancel_event = threading.Event()
    if fork_context is _FORK_CONTEXT_UNSET:
        fork_context = _payload_blind_forkserver(repo) if use_fresh_processes else None
    if worker_environment is None:
        worker_environment = _worker_environment(repo)
    lineage_id = derive_identity("lineage", case["case_id"], condition_id)
    branch_token = "genesis"
    events = _flatten_case(case)
    initial_projection = encode_state(mechanism, initial_state(mechanism))
    # OT-0077 keeps updater authority and actor-visible inheritance explicit.
    # They coincide for ordinary lineages and intentionally diverge only for
    # the declared update-without-projection causal cut.
    authoritative_state = initial_projection
    active_projection = initial_projection
    builder = ReceiptChainBuilder(
        task_sha256=task_digest,
        case_id=case["case_id"],
        case_index=case["case_index"],
        horizon=case["horizon"],
        condition_id=condition_id,
        display_label=(intervention_id or mechanism_id)[:80],
        lineage_class=_lineage_class(role),
        branch_token=branch_token,
        surface=strict_online_surface(),
        initial_state=initial_projection,
        initial_projection=initial_projection,
        projection_mode=(
            UPDATE_WITHOUT_PROJECTION
            if intervention_id == "update-without-projection"
            else POST_STATE_PROJECTION
        ),
    )
    journal_writer = None
    if journal is not None:
        journal_writer = journal.open_segment(
            scope=journal_scope,
            case_id=case["case_id"],
            case_index=case["case_index"],
            condition_id=condition_id,
            lineage_id=lineage_id,
            branch_id=derive_identity("branch", lineage_id, branch_token),
            encounter_start=0,
            encounter_count=len(events),
            initial_receipts=builder.initial_receipts(),
        )
    predictions: list[int | None] = []
    statuses: list[str] = []
    projection_sha256s: list[str] = []
    worker_response_sha256s: list[str] = []
    consumer_attempts: list[dict[str, Any]] = []
    operational_failures: list[dict[str, Any]] = []
    maximum_projection_bytes = len(active_projection)
    maximum_prediction_operations = 0
    maximum_update_operations = 0
    prior_outcome = 0

    for offset, event in enumerate(events):
        facts = _consumer_facts(
            execution_commit=execution_commit,
            task_digest=task_digest,
            case_id=case["case_id"],
            condition_id=condition_id,
            branch_token=branch_token,
            encounter_index=offset,
            mode="prediction",
        )
        if use_fresh_processes:
            consumer = run_fresh_consumer(
                repo,
                mechanism=mechanism,
                case_id=case["case_id"],
                condition_id=condition_id,
                lineage_id=lineage_id,
                encounter_index=offset,
                mode="prediction",
                public_query=event["public_query"],
                projection=active_projection,
                facts=facts,
                allow_learning_rejection=(
                    intervention_id == "one-step-stale-consequence"
                ),
                deadline=deadline,
                cancel_event=cancel_event,
                fork_context=fork_context,
                worker_environment=worker_environment,
            )
        else:
            if cancel_event.is_set() or time.monotonic() >= deadline:
                consumer = _controller_absence(
                    projection=active_projection,
                    condition_id=condition_id,
                    encounter_index=offset,
                    mode="prediction",
                )
            else:
                try:
                    consumer = _run_in_process_consumer(
                        mechanism=mechanism,
                        projection=active_projection,
                        public_query=event["public_query"],
                        mode="prediction",
                    )
                except LearningError:
                    if intervention_id != "one-step-stale-consequence":
                        raise
                    response_bytes = canonical_json(
                        {
                            "condition_id": condition_id,
                            "encounter_index": offset,
                            "projection_sha256": sha256_bytes(active_projection),
                            "runtime": "in-process-learning-rejection",
                        }
                    )
                    consumer = {
                        "attempt_status": "completed",
                        "failure_code": None,
                        "prediction_status": "invalid",
                        "prediction": None,
                        "prediction_operations": 0,
                        "state_bytes": len(active_projection),
                        "candidate_count": 0,
                        "response_bytes": response_bytes,
                        "response_sha256": sha256_bytes(response_bytes),
                        "learning_rejected": True,
                        "process_boundary": "in-process",
                        "process_started": False,
                        "fresh_process_verified": False,
                        "descriptor_audit_pass": False,
                        "workspace_empty_after": None,
                        "sentinel_absent": True,
                    }
        consumer = _ensure_consumer_observation(facts, consumer)
        consumer_receipt = builder.attach_consumer(
            facts=consumer["consumer_facts"],
            mode="prediction",
        )
        if journal_writer is not None:
            journal_writer.append_consumer(consumer_receipt)
        prediction = consumer["prediction"]
        prediction_status = consumer["prediction_status"]
        prediction_nonvalid = prediction_status != "valid"
        if prediction_nonvalid:
            if prediction is not None:
                raise ProtocolError("nonvalid online consumer emitted a prediction")
        elif type(prediction) is not int or prediction not in {0, 1}:
            raise ProtocolError("online consumer returned no scored prediction")
        predictions.append(prediction)
        statuses.append(prediction_status)
        projection_sha256s.append(sha256_bytes(active_projection))
        attempt = _consumer_attempt_record(
            consumer,
            encounter_index=offset,
            mode="prediction",
        )
        consumer_attempts.append(attempt)
        if consumer["attempt_status"] == "completed":
            worker_response_sha256s.append(consumer["response_sha256"])
        else:
            operational_failures.append(copy.deepcopy(attempt))
        maximum_projection_bytes = max(maximum_projection_bytes, len(active_projection))
        maximum_prediction_operations = max(
            maximum_prediction_operations,
            consumer["prediction_operations"],
        )

        consequence_binding = "current"
        delivered_outcome: int | None = event["outcome"]
        update_decision = "update"
        update_operations = 0
        authoritative_pre_state = authoritative_state
        candidate_post = authoritative_pre_state
        update_rejected = False
        if prediction_nonvalid:
            consequence_binding = "withheld"
            delivered_outcome = None
            update_decision = "no-op"
            update_rejected = True
        elif intervention_id == "consequence-withholding":
            consequence_binding = "withheld"
            delivered_outcome = None
            update_decision = "no-op"
        elif intervention_id == "projection-without-update":
            update_decision = "no-op"
        elif role == "matched-frozen-control":
            # This is the reference's exact no-learning counterfactual.  It
            # observes the same world stream but never grants updater authority.
            update_decision = "no-op"
        else:
            if intervention_id == "one-step-stale-consequence":
                consequence_binding = "one-step-stale"
                delivered_outcome = prior_outcome
            assert delivered_outcome is not None
            try:
                if intervention_id == "update-without-projection":
                    transition = update_from_authoritative_state(
                        mechanism,
                        authoritative_pre_state,
                        event["public_query"],
                        delivered_outcome,
                    )
                else:
                    transition = update(
                        mechanism,
                        authoritative_pre_state,
                        event["public_query"],
                        prediction,
                        delivered_outcome,
                    )
            except LearningError:
                if intervention_id != "one-step-stale-consequence":
                    raise
                # The stale-label intervention may make an otherwise valid
                # affine substrate internally inconsistent.  Preserve that
                # fail-closed rejection as a receipted no-op and retain the
                # complete prediction denominator.
                update_decision = "no-op"
                update_rejected = True
            else:
                candidate_post = encode_state(mechanism, transition.state)
                update_operations = transition.operations
                maximum_update_operations = max(
                    maximum_update_operations, update_operations
                )

        if update_decision == "no-op":
            receipt_post = authoritative_pre_state
            delivered_next = active_projection
        else:
            receipt_post = candidate_post
            delivered_next = candidate_post
        if intervention_id == "update-without-projection":
            delivered_next = active_projection
        next_event = events[offset + 1] if offset + 1 < len(events) else None
        episode_reset_applied = (
            not prediction_nonvalid
            and
            intervention_id == "cross-episode-state-reset"
            and next_event is not None
            and next_event["public_query"]["episode_start"] is True
        )
        if episode_reset_applied:
            # The reset intervention cuts inherited state itself, not merely
            # its rendering.  Both authority and projection return to genesis.
            receipt_post = initial_projection
            delivered_next = initial_projection
        maximum_projection_bytes = max(
            maximum_projection_bytes,
            len(delivered_next),
        )

        update_payload = (
            b""
            if prediction_nonvalid
            else canonical_json(
                {
                    "schema_version": 1,
                    "decision": update_decision,
                    "intervention_id": intervention_id,
                    "candidate_post_sha256": sha256_bytes(candidate_post),
                    "delivered_projection_sha256": sha256_bytes(delivered_next),
                    "episode_reset_applied": episode_reset_applied,
                    "update_operations": update_operations,
                    "update_rejected": update_rejected,
                }
            )
        )
        committed_receipts = builder.append_encounter(
            public_query=event["public_query"],
            episode_index=event["episode_index"],
            prediction=prediction,
            outcome=event["outcome"],
            update_decision=update_decision,
            authoritative_pre_state=authoritative_pre_state,
            update_payload=update_payload,
            post_state=receipt_post,
            next_projection=delivered_next,
            prediction_status=prediction_status,
            consequence_binding=consequence_binding,
            delivered_outcome=delivered_outcome,
            state_transition=(
                EPISODE_RESET_TRANSITION if episode_reset_applied else None
            ),
            candidate_post_state=(candidate_post if episode_reset_applied else None),
            reset_next_episode_index=(
                next_event["episode_index"] if episode_reset_applied else None
            ),
        )
        if journal_writer is not None:
            journal_writer.append_encounter(offset, committed_receipts)
        terminal = offset == len(events) - 1
        audit_consumer: dict[str, Any] | None = None
        audit_facts: dict[str, Any] | None = None
        if terminal:
            audit_facts = _consumer_facts(
                execution_commit=execution_commit,
                task_digest=task_digest,
                case_id=case["case_id"],
                condition_id=condition_id,
                branch_token=branch_token,
                encounter_index=242,
                mode="terminal-audit",
            )
            if use_fresh_processes:
                audit_consumer = run_fresh_consumer(
                    repo,
                    mechanism=mechanism,
                    case_id=case["case_id"],
                    condition_id=condition_id,
                    lineage_id=lineage_id,
                    encounter_index=242,
                    mode="terminal-audit",
                    public_query=None,
                    projection=delivered_next,
                    facts=audit_facts,
                    deadline=deadline,
                    cancel_event=cancel_event,
                    fork_context=fork_context,
                    worker_environment=worker_environment,
                )
            else:
                if cancel_event.is_set() or time.monotonic() >= deadline:
                    audit_consumer = _controller_absence(
                        projection=delivered_next,
                        condition_id=condition_id,
                        encounter_index=242,
                        mode="terminal-audit",
                    )
                else:
                    audit_consumer = _run_in_process_consumer(
                        mechanism=mechanism,
                        projection=delivered_next,
                        public_query=None,
                        mode="terminal-audit",
                    )
            audit_consumer = _ensure_consumer_observation(
                audit_facts,
                audit_consumer,
            )
            audit_attempt = _consumer_attempt_record(
                audit_consumer,
                encounter_index=242,
                mode="terminal-audit",
            )
            consumer_attempts.append(audit_attempt)
            if audit_consumer["attempt_status"] == "completed":
                worker_response_sha256s.append(audit_consumer["response_sha256"])
            else:
                operational_failures.append(copy.deepcopy(audit_attempt))
        if terminal:
            assert audit_consumer is not None
            terminal_receipt = builder.attach_consumer(
                facts=audit_consumer["consumer_facts"],
                mode="terminal-audit",
            )
            if journal_writer is not None:
                journal_writer.append_consumer(terminal_receipt)
        active_projection = delivered_next
        authoritative_state = receipt_post
        # World time advances even when the prediction consumer is invalid.
        # The frozen stale intervention receives the immediately preceding
        # encounter outcome, not the preceding *valid-prediction* outcome.
        prior_outcome = event["outcome"]

    chain = builder.finish()
    if journal_writer is not None:
        journal_writer.seal(chain)
    validation = validate_chain(
        chain,
        require_online_admissible=role == "positive-reference",
    )
    condition = {
        "role": role,
        "mechanism_id": mechanism_id,
        "reference_id": reference_id,
        "intervention_id": intervention_id,
        "query_ids": [event["public_query"]["query_id"] for event in events],
        "outcomes": [event["outcome"] for event in events],
        "predictions": predictions,
        "prediction_statuses": statuses,
        "causal_evidence": _causal_evidence_from_validation(validation),
    }
    return {
        "condition_id": condition_id,
        "condition": condition,
        "chain": chain,
        "chain_validation": {
            "authority_eligible": (
                validation.authority_eligible and not operational_failures
            ),
            "encounter_count": validation.encounter_count,
            "errors": validation.errors,
            "terminal_audit_receipt_sha256": validation.terminal_audit_receipt_sha256,
            "trace_sha256": validation.trace_sha256,
            "episode_reset_count": validation.episode_reset_count,
        },
        "episode_reset_evidence": _episode_resets_from_validation(
            chain,
            validation,
        ),
        "initial_projection_sha256": sha256_bytes(initial_projection),
        "projection_sha256s": projection_sha256s,
        "worker_response_sha256s": worker_response_sha256s,
        "consumer_attempts": consumer_attempts,
        "operational_failures": operational_failures,
        "operational_complete": not operational_failures,
        "terminal_audit_completed": (
            bool(consumer_attempts)
            and consumer_attempts[-1]["mode"] == "terminal-audit"
            and consumer_attempts[-1]["attempt_status"] == "completed"
        ),
        "maximum_projection_bytes": maximum_projection_bytes,
        "maximum_prediction_operations": maximum_prediction_operations,
        "maximum_update_operations": maximum_update_operations,
        "fresh_processes": use_fresh_processes,
    }


def _offline_condition(
    task_digest: str,
    case: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
) -> dict[str, Any]:
    events = _flatten_case(case)
    result = offline_best_fixed_rule(
        [
            {
                "encounter_index": event["encounter_index"],
                "public_query": event["public_query"],
                "outcome": event["outcome"],
            }
            for event in events
        ]
    )
    condition_id = _descriptor_identity(task_digest, case["case_id"], descriptor)
    unavailable_projection = derive_identity(
        "offline-future-access-has-no-online-projection",
        task_digest,
        case["case_id"],
        condition_id,
    )
    return {
        "condition_id": condition_id,
        "condition": {
            "role": "required-control",
            "mechanism_id": "offline-best-fixed-rule",
            "reference_id": None,
            "intervention_id": None,
            "query_ids": [event["public_query"]["query_id"] for event in events],
            "outcomes": [event["outcome"] for event in events],
            "predictions": list(result.predictions),
            "prediction_statuses": ["valid"] * len(events),
            "causal_evidence": {
                "consumed_projection_sha256s": [unavailable_projection] * len(events),
                "terminal_projection_sha256": unavailable_projection,
                "accepted_updates": 0,
                "candidate_state_changed": False,
                "active_projection_changed": False,
            },
        },
        "chain": None,
        "chain_validation": {
            "authority_eligible": False,
            "reason": "offline complete-stream future access",
        },
        "offline_mask": format(result.mask, "012b"),
        "offline_errors": result.errors,
        "offline_operations": result.operations,
        "fresh_processes": False,
    }


def _wrong_lineage_condition(
    task_digest: str,
    case: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
    *,
    active_chain: dict[str, Any],
    donor_chain: dict[str, Any],
) -> dict[str, Any]:
    events = _flatten_case(case)
    condition_id = _descriptor_identity(task_digest, case["case_id"], descriptor)
    rejection = validate_projection_consumer_substitution_rejection(
        active_chain,
        donor_chain,
        producer_encounter_index=0,
    )
    donor_projection = checkpoint(donor_chain, 0)["projection"]["sha256"]
    return {
        "condition_id": condition_id,
        "condition": {
            "role": "causal-intervention",
            "mechanism_id": "wrong-lineage-projection",
            "reference_id": descriptor[2],
            "intervention_id": "wrong-lineage-projection",
            "query_ids": [event["public_query"]["query_id"] for event in events],
            "outcomes": [event["outcome"] for event in events],
            "predictions": [None] * len(events),
            "prediction_statuses": ["invalid"] * len(events),
            "causal_evidence": {
                "consumed_projection_sha256s": [donor_projection] * len(events),
                "terminal_projection_sha256": donor_projection,
                "accepted_updates": 0,
                "candidate_state_changed": False,
                "active_projection_changed": False,
            },
        },
        "chain": None,
        "chain_validation": {
            "authority_eligible": False,
            "rejection_code": "sibling-branch-substitution",
            "rejected_before_prediction_count": len(events),
        },
        "wrong_lineage_rejection": rejection,
        "fresh_processes": False,
    }


def _missing_online_condition(
    task_digest: str,
    case: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
    *,
    failure_code: str,
    use_fresh_processes: bool,
) -> dict[str, Any]:
    """Retain every denominator slot for a condition that never started."""

    role, mechanism_id, reference_id, intervention_id = descriptor
    mechanism = _mechanism_for(descriptor)
    if mechanism is None:
        raise ProtocolError("missing fallback requested for an offline condition")
    events = _flatten_case(case)
    condition_id = _descriptor_identity(task_digest, case["case_id"], descriptor)
    initial_projection = encode_state(mechanism, initial_state(mechanism))
    projection_sha256 = sha256_bytes(initial_projection)
    attempts = [
        _consumer_attempt_record(
            _controller_absence(
                projection=initial_projection,
                condition_id=condition_id,
                encounter_index=index,
                mode="prediction",
                failure_code=failure_code,
            ),
            encounter_index=index,
            mode="prediction",
        )
        for index in range(len(events))
    ]
    terminal = _consumer_attempt_record(
        _controller_absence(
            projection=initial_projection,
            condition_id=condition_id,
            encounter_index=len(events),
            mode="terminal-audit",
            failure_code=failure_code,
        ),
        encounter_index=len(events),
        mode="terminal-audit",
    )
    attempts.append(terminal)
    return {
        "condition_id": condition_id,
        "condition": {
            "role": role,
            "mechanism_id": mechanism_id,
            "reference_id": reference_id,
            "intervention_id": intervention_id,
            "query_ids": [event["public_query"]["query_id"] for event in events],
            "outcomes": [event["outcome"] for event in events],
            "predictions": [None] * len(events),
            "prediction_statuses": ["missing"] * len(events),
            "causal_evidence": {
                "consumed_projection_sha256s": [projection_sha256] * len(events),
                "terminal_projection_sha256": projection_sha256,
                "accepted_updates": 0,
                "candidate_state_changed": False,
                "active_projection_changed": False,
            },
        },
        "chain": None,
        "chain_validation": {
            "authority_eligible": False,
            "encounter_count": len(events),
            "errors": len(events),
            "reason": failure_code,
        },
        "episode_reset_evidence": {
            "episode_reset_count": 0,
            "resets": [],
        },
        "initial_projection_sha256": projection_sha256,
        "projection_sha256s": [projection_sha256] * len(events),
        "worker_response_sha256s": [],
        "consumer_attempts": attempts,
        "operational_failures": copy.deepcopy(attempts),
        "operational_complete": False,
        "terminal_audit_completed": False,
        "maximum_projection_bytes": len(initial_projection),
        "maximum_prediction_operations": 0,
        "maximum_update_operations": 0,
        "fresh_processes": use_fresh_processes,
    }


def _execute_all_conditions(
    repo: Path,
    *,
    execution_commit: str,
    task: dict[str, Any],
    use_fresh_processes: bool,
    max_workers: int = 24,
    deadline: float | None = None,
    fork_context: Any = _FORK_CONTEXT_UNSET,
    journal: SegmentedEncounterJournal | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Execute the exact scorer inventory with isolated state per condition."""

    validate_task(task)
    if deadline is None:
        deadline = time.monotonic() + CALIBRATION_SECONDS
    work_deadline = deadline - EXECUTOR_DRAIN_SECONDS
    cancel_event = threading.Event()
    if fork_context is _FORK_CONTEXT_UNSET:
        fork_context = _payload_blind_forkserver(repo) if use_fresh_processes else None
    worker_environment = _worker_environment(repo)
    task_digest = sha256_bytes(canonical_json(task))
    results: dict[
        tuple[int, tuple[str, str, str | None, str | None]], dict[str, Any]
    ] = {}
    futures: dict[Any, tuple[int, tuple[str, str, str | None, str | None]]] = {}
    executor = ThreadPoolExecutor(max_workers=max_workers)
    fatal_error: BaseException | None = None
    try:
        for case in task["cases"]:
            for descriptor in CONDITION_INVENTORY:
                mechanism = _mechanism_for(descriptor)
                if mechanism is None:
                    results[(case["case_index"], descriptor)] = _offline_condition(
                        task_digest,
                        case,
                        descriptor,
                    )
                elif descriptor[3] == "wrong-lineage-projection":
                    # Admission is attempted only after the two real sibling
                    # chains exist, below.  No prediction consumer is started.
                    continue
                else:
                    future = executor.submit(
                        _execute_online_condition,
                        repo,
                        execution_commit=execution_commit,
                        task_digest=task_digest,
                        case=case,
                        descriptor=descriptor,
                        use_fresh_processes=use_fresh_processes,
                        deadline=work_deadline,
                        cancel_event=cancel_event,
                        fork_context=fork_context,
                        worker_environment=worker_environment,
                        journal=journal,
                        journal_scope="main",
                    )
                    futures[future] = (case["case_index"], descriptor)
        done, pending = wait(
            futures,
            timeout=max(0.0, work_deadline - time.monotonic()),
            return_when=FIRST_EXCEPTION,
        )
        for future in done:
            error = future.exception()
            if error is not None and fatal_error is None:
                fatal_error = error
        if pending or fatal_error is not None:
            cancel_event.set()
            for future in pending:
                future.cancel()
            wait(
                [future for future in pending if not future.cancelled()],
                timeout=max(0.0, deadline - time.monotonic()),
            )
        for future, key in futures.items():
            if future.done() and not future.cancelled() and future.exception() is None:
                results[key] = future.result()
                continue
            case_index, descriptor = key
            results[key] = _missing_online_condition(
                task_digest,
                task["cases"][case_index],
                descriptor,
                failure_code=(
                    "fatal-peer-condition"
                    if fatal_error is not None
                    else "stage-deadline-unstarted"
                ),
                use_fresh_processes=use_fresh_processes,
            )
    finally:
        cancel_event.set()
        executor.shutdown(wait=True, cancel_futures=True)
    if fatal_error is not None:
        raise fatal_error

    for case in task["cases"]:
        case_index = case["case_index"]
        for reference in (COMPACT_REFERENCE, LOG_REFERENCE):
            descriptor = (
                "causal-intervention",
                "wrong-lineage-projection",
                reference,
                "wrong-lineage-projection",
            )
            active_descriptor = (
                "positive-reference",
                reference,
                reference,
                None,
            )
            donor_descriptor = (
                "matched-frozen-control",
                f"{reference}--matched-frozen-initial",
                reference,
                None,
            )
            active_result = results[(case_index, active_descriptor)]
            donor_result = results[(case_index, donor_descriptor)]
            if (
                active_result.get("operational_complete") is True
                and donor_result.get("operational_complete") is True
                and active_result.get("chain") is not None
                and donor_result.get("chain") is not None
                and time.monotonic() < deadline
            ):
                results[(case_index, descriptor)] = _wrong_lineage_condition(
                    task_digest,
                    case,
                    descriptor,
                    active_chain=active_result["chain"],
                    donor_chain=donor_result["chain"],
                )
            else:
                results[(case_index, descriptor)] = _missing_online_condition(
                    task_digest,
                    case,
                    descriptor,
                    failure_code="wrong-lineage-donor-incomplete",
                    use_fresh_processes=use_fresh_processes,
                )

    scorer_cases: list[dict[str, Any]] = []
    raw_lineages: list[dict[str, Any]] = []
    for case in task["cases"]:
        case_results = [
            results[(case["case_index"], descriptor)]
            for descriptor in CONDITION_INVENTORY
        ]
        conditions = {
            result["condition_id"]: result["condition"] for result in case_results
        }
        if len(conditions) != len(CONDITION_INVENTORY):
            raise ProtocolError("opaque condition identities collided")
        immutable = next(
            result
            for result, descriptor in zip(
                case_results, CONDITION_INVENTORY, strict=True
            )
            if descriptor
            == ("required-control", "immutable-seed", None, None)
        )
        placebo = next(
            result
            for result, descriptor in zip(
                case_results, CONDITION_INVENTORY, strict=True
            )
            if descriptor[0] == "identity-placebo"
        )
        placebo_projection_identity = (
            immutable.get("initial_projection_sha256")
            == placebo.get("initial_projection_sha256")
            and immutable.get("projection_sha256s")
            == placebo.get("projection_sha256s")
        )
        events = _flatten_case(case)
        scorer_cases.append(
            {
                "case_id": case["case_id"],
                "case_index": case["case_index"],
                "episodes": [
                    {
                        "episode_index": episode["episode_index"],
                        "dwell": episode["dwell"],
                    }
                    for episode in case["episodes"]
                ],
                "world_query_ids": [
                    event["public_query"]["query_id"] for event in events
                ],
                "world_outcomes": [event["outcome"] for event in events],
                "conditions": {
                    condition_id: conditions[condition_id]
                    for condition_id in sorted(conditions)
                },
                "placebo_projection_bytes_identical": placebo_projection_identity,
            }
        )
        raw_lineages.extend(
            {
                "case_id": case["case_id"],
                "case_index": case["case_index"],
                **result,
            }
            for result in case_results
        )
    raw_lineages.sort(key=lambda item: (item["case_index"], item["condition_id"]))
    return scorer_cases, raw_lineages


def _reference_trace_in_process(task: dict[str, Any]) -> dict[str, dict[str, list[int]]]:
    """Execute the two positive mechanisms with isolated state for task anchors."""

    validate_task(task)
    traces: dict[str, dict[str, list[int]]] = {}
    for case in task["cases"]:
        by_reference: dict[str, list[int]] = {}
        for mechanism in (COMPACT_REFERENCE, LOG_REFERENCE):
            projection = encode_state(mechanism, initial_state(mechanism))
            predictions: list[int] = []
            for event in _flatten_case(case):
                prediction = predict(mechanism, projection, event["public_query"]).prediction
                predictions.append(prediction)
                transition = update(
                    mechanism,
                    projection,
                    event["public_query"],
                    prediction,
                    event["outcome"],
                )
                projection = encode_state(mechanism, transition.state)
            by_reference[mechanism] = predictions
        traces[case["case_id"]] = by_reference
    return traces


def _task_metamorphic_gates(task: dict[str, Any]) -> dict[str, bool]:
    baseline = _reference_trace_in_process(task)
    alpha = copy.deepcopy(task)
    ordinal = 0
    for case in alpha["cases"]:
        for episode in case["episodes"]:
            for event in episode["events"]:
                old = event["public_query"]["query_id"]
                event["public_query"]["query_id"] = hashlib.sha256(
                    f"ot-0077-task-alpha:{ordinal}:{old}".encode("ascii")
                ).hexdigest()
                ordinal += 1
    validate_task(alpha)
    alpha_equal = _reference_trace_in_process(alpha) == baseline

    reversed_task = copy.deepcopy(task)
    reversed_task["cases"].reverse()
    # Task validation freezes serialized case order, so case-order metamorphism
    # executes the already validated cases in reverse while retaining identity.
    reversed_traces: dict[str, dict[str, list[int]]] = {}
    for case in reversed_task["cases"]:
        isolated = copy.deepcopy(task)
        isolated["cases"] = [case]
        # Execute directly because the P task validator correctly insists on
        # the original complete case inventory and indices.
        by_reference: dict[str, list[int]] = {}
        for mechanism in (COMPACT_REFERENCE, LOG_REFERENCE):
            projection = encode_state(mechanism, initial_state(mechanism))
            predictions = []
            for event in _flatten_case(case):
                prediction = predict(mechanism, projection, event["public_query"]).prediction
                predictions.append(prediction)
                transition = update(
                    mechanism,
                    projection,
                    event["public_query"],
                    prediction,
                    event["outcome"],
                )
                projection = encode_state(mechanism, transition.state)
            by_reference[mechanism] = predictions
        reversed_traces[case["case_id"]] = by_reference
    return {
        "task_query_id_alpha_renaming": alpha_equal,
        "task_case_order_reversal": reversed_traces == baseline,
    }


def _lineage_by_descriptor(
    lineages: list[dict[str, Any]],
    case_index: int,
    descriptor: tuple[str, str, str | None, str | None],
) -> dict[str, Any]:
    role, mechanism_id, reference_id, intervention_id = descriptor
    matches = [
        item
        for item in lineages
        if item["case_index"] == case_index
        and item["condition"]["role"] == role
        and item["condition"]["mechanism_id"] == mechanism_id
        and item["condition"]["reference_id"] == reference_id
        and item["condition"]["intervention_id"] == intervention_id
    ]
    if len(matches) != 1:
        raise ProtocolError("lineage descriptor did not resolve exactly once")
    return matches[0]


def _rollback_suffix_events(
    case: dict[str, Any],
    *,
    start: int,
    alternate_first_outcome: bool,
) -> list[dict[str, Any]]:
    """Derive the exact frozen suffix, including the declared alternate fork."""

    events = copy.deepcopy(_flatten_case(case)[start:])
    if alternate_first_outcome:
        if not events:
            raise ProtocolError("alternate rollback suffix is empty")
        event = events[0]
        feature = int(event["public_query"]["feature_bits"], 2) ^ 1
        if feature == 0:
            feature = 2
        event["public_query"]["feature_bits"] = format(feature, "012b")
        event["public_query"]["query_id"] = derive_identity(
            "alternate-query",
            case["case_id"],
            start,
            feature,
        )
        semantic_rule = case["episodes"][event["episode_index"]]["semantic_rule"]
        active_mask = int(case["hidden_masks"][semantic_rule], 2)
        event["outcome"] = (active_mask & feature).bit_count() & 1
    return events


def _execute_suffix_branch(
    repo: Path,
    *,
    execution_commit: str,
    task_digest: str,
    case: dict[str, Any],
    condition_id: str,
    parent_chain: dict[str, Any],
    checkpoint_index: int,
    branch_token: str,
    branch_role: str,
    alternate_first_outcome: bool,
    use_fresh_processes: bool,
    deadline: float,
    cancel_event: threading.Event,
    fork_context: Any,
    worker_environment: dict[str, str],
    journal: SegmentedEncounterJournal | None = None,
    journal_scope: str = "rollback-rewind",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    point = checkpoint(parent_chain, checkpoint_index)
    state = decode_blob(point["state"], limit=2_048, label="checkpoint state")
    projection = decode_blob(
        point["projection"], limit=2_048, label="checkpoint projection"
    )
    start = checkpoint_index + 1
    events = _rollback_suffix_events(
        case,
        start=start,
        alternate_first_outcome=alternate_first_outcome,
    )
    lineage_id = derive_identity("lineage", case["case_id"], condition_id)
    builder = ReceiptChainBuilder(
        task_sha256=task_digest,
        case_id=case["case_id"],
        case_index=case["case_index"],
        horizon=case["horizon"],
        condition_id=condition_id,
        display_label=branch_role,
        lineage_class=ONLINE_POSITIVE,
        branch_token=branch_token,
        surface=strict_online_surface(),
        initial_state=state,
        initial_projection=projection,
        branch_role=branch_role,
        fork_parent_state_sha256=point["state_receipt_sha256"],
        fork_parent_projection_sha256=point["projection_receipt_sha256"],
        encounter_start=start,
        encounter_count=len(events),
    )
    journal_writer = None
    if journal is not None:
        journal_writer = journal.open_segment(
            scope=journal_scope,
            case_id=case["case_id"],
            case_index=case["case_index"],
            condition_id=condition_id,
            lineage_id=lineage_id,
            branch_id=derive_identity("branch", lineage_id, branch_token),
            encounter_start=start,
            encounter_count=len(events),
            initial_receipts=builder.initial_receipts(),
        )
    authoritative_state = state
    active_projection = projection
    operational_failures: list[dict[str, Any]] = []
    for local_offset, event in enumerate(events):
        absolute_index = start + local_offset
        facts = _consumer_facts(
            execution_commit=execution_commit,
            task_digest=task_digest,
            case_id=case["case_id"],
            condition_id=condition_id,
            branch_token=branch_token,
            encounter_index=absolute_index,
            mode="prediction",
        )
        if use_fresh_processes:
            consumer = run_fresh_consumer(
                repo,
                mechanism=COMPACT_REFERENCE,
                case_id=case["case_id"],
                condition_id=condition_id,
                lineage_id=lineage_id,
                encounter_index=absolute_index,
                mode="prediction",
                public_query=event["public_query"],
                projection=active_projection,
                facts=facts,
                deadline=deadline,
                cancel_event=cancel_event,
                fork_context=fork_context,
                worker_environment=worker_environment,
            )
        else:
            consumer = (
                _controller_absence(
                    projection=active_projection,
                    condition_id=condition_id,
                    encounter_index=absolute_index,
                    mode="prediction",
                )
                if cancel_event.is_set() or time.monotonic() >= deadline
                else _run_in_process_consumer(
                    mechanism=COMPACT_REFERENCE,
                    projection=active_projection,
                    public_query=event["public_query"],
                    mode="prediction",
                )
            )
        consumer = _ensure_consumer_observation(facts, consumer)
        consumer_receipt = builder.attach_consumer(
            facts=consumer["consumer_facts"],
            mode="prediction",
        )
        if journal_writer is not None:
            journal_writer.append_consumer(consumer_receipt)
        prediction = consumer["prediction"]
        prediction_status = consumer["prediction_status"]
        prediction_nonvalid = prediction_status != "valid"
        if prediction_nonvalid and prediction is not None:
            raise ProtocolError("nonvalid rollback consumer emitted a prediction")
        attempt = _consumer_attempt_record(
            consumer,
            encounter_index=absolute_index,
            mode="prediction",
        )
        if consumer["attempt_status"] != "completed":
            operational_failures.append(attempt)
        outcome = event["outcome"]
        if prediction_nonvalid:
            post = authoritative_state
            delivered_next = active_projection
            update_decision = "no-op"
            update_payload = b""
            consequence_binding = "withheld"
            delivered_outcome = None
        else:
            transition = update(
                COMPACT_REFERENCE,
                authoritative_state,
                event["public_query"],
                prediction,
                outcome,
            )
            post = encode_state(COMPACT_REFERENCE, transition.state)
            delivered_next = post
            update_decision = "update"
            consequence_binding = "current"
            delivered_outcome = outcome
            update_payload = canonical_json(
                {
                    "schema_version": 1,
                    "decision": "update",
                    "intervention_id": None,
                    "candidate_post_sha256": sha256_bytes(post),
                    "delivered_projection_sha256": sha256_bytes(post),
                    "episode_reset_applied": False,
                    "update_operations": transition.operations,
                    "update_rejected": False,
                }
            )
        committed_receipts = builder.append_encounter(
            public_query=event["public_query"],
            episode_index=event["episode_index"],
            prediction=prediction,
            outcome=outcome,
            update_decision=update_decision,
            authoritative_pre_state=authoritative_state,
            update_payload=update_payload,
            post_state=post,
            next_projection=delivered_next,
            prediction_status=prediction_status,
            consequence_binding=consequence_binding,
            delivered_outcome=delivered_outcome,
        )
        if journal_writer is not None:
            journal_writer.append_encounter(absolute_index, committed_receipts)
        terminal = local_offset == len(events) - 1
        terminal_consumer: dict[str, Any] | None = None
        terminal_facts: dict[str, Any] | None = None
        if terminal:
            terminal_facts = _consumer_facts(
                execution_commit=execution_commit,
                task_digest=task_digest,
                case_id=case["case_id"],
                condition_id=condition_id,
                branch_token=branch_token,
                encounter_index=242,
                mode="terminal-audit",
            )
            if use_fresh_processes:
                terminal_consumer = run_fresh_consumer(
                    repo,
                    mechanism=COMPACT_REFERENCE,
                    case_id=case["case_id"],
                    condition_id=condition_id,
                    lineage_id=lineage_id,
                    encounter_index=242,
                    mode="terminal-audit",
                    public_query=None,
                    projection=delivered_next,
                    facts=terminal_facts,
                    deadline=deadline,
                    cancel_event=cancel_event,
                    fork_context=fork_context,
                    worker_environment=worker_environment,
                )
            else:
                terminal_consumer = (
                    _controller_absence(
                        projection=delivered_next,
                        condition_id=condition_id,
                        encounter_index=242,
                        mode="terminal-audit",
                    )
                    if cancel_event.is_set() or time.monotonic() >= deadline
                    else _run_in_process_consumer(
                        mechanism=COMPACT_REFERENCE,
                        projection=delivered_next,
                        public_query=None,
                        mode="terminal-audit",
                    )
                )
            terminal_consumer = _ensure_consumer_observation(
                terminal_facts,
                terminal_consumer,
            )
            terminal_attempt = _consumer_attempt_record(
                terminal_consumer,
                encounter_index=242,
                mode="terminal-audit",
            )
            if terminal_consumer["attempt_status"] != "completed":
                operational_failures.append(terminal_attempt)
        if terminal:
            assert terminal_consumer is not None
            terminal_receipt = builder.attach_consumer(
                facts=terminal_consumer["consumer_facts"],
                mode="terminal-audit",
            )
            if journal_writer is not None:
                journal_writer.append_consumer(terminal_receipt)
        authoritative_state = post
        active_projection = delivered_next
    chain = builder.finish()
    if journal_writer is not None:
        journal_writer.seal(chain)
    validate_chain(chain)
    return chain, operational_failures


def _execute_rollback_suite(
    repo: Path,
    *,
    execution_commit: str,
    task: dict[str, Any],
    lineages: list[dict[str, Any]],
    use_fresh_processes: bool,
    deadline: float,
    fork_context: Any = _FORK_CONTEXT_UNSET,
    journal: SegmentedEncounterJournal | None = None,
) -> tuple[dict[str, bool], dict[str, Any]]:
    task_digest = sha256_bytes(canonical_json(task))
    work_deadline = deadline - EXECUTOR_DRAIN_SECONDS
    case = task["cases"][0]
    descriptor = (
        "positive-reference",
        COMPACT_REFERENCE,
        COMPACT_REFERENCE,
        None,
    )
    parent_result = _lineage_by_descriptor(lineages, 0, descriptor)
    parent = parent_result.get("chain")
    if (
        parent is None
        or parent_result.get("operational_complete") is not True
        or parent_result.get("terminal_audit_completed") is not True
        or time.monotonic() >= work_deadline
    ):
        return {name: False for name in ROLLBACK_REPLAY_GATES}, {
            "status": "skipped",
            "failure_code": "rollback-parent-or-deadline-unavailable",
            "operational_failures": [],
        }
    cancel_event = threading.Event()
    if fork_context is _FORK_CONTEXT_UNSET:
        fork_context = _payload_blind_forkserver(repo) if use_fresh_processes else None
    worker_environment = _worker_environment(repo)
    replay_result = _execute_online_condition(
        repo,
        execution_commit=execution_commit,
        task_digest=task_digest,
        case=case,
        descriptor=descriptor,
        use_fresh_processes=use_fresh_processes,
        deadline=work_deadline,
        cancel_event=cancel_event,
        fork_context=fork_context,
        worker_environment=worker_environment,
        journal=journal,
        journal_scope="rollback-parent-replay",
    )
    parent_replay = replay_result["chain"]
    replay_failures = copy.deepcopy(replay_result["operational_failures"])
    if (
        parent_replay is None
        or replay_result.get("operational_complete") is not True
        or replay_result.get("terminal_audit_completed") is not True
    ):
        return {name: False for name in ROLLBACK_REPLAY_GATES}, {
            "status": "failed",
            "failure_code": "rollback-parent-replay-incomplete",
            "parent_replay": parent_replay,
            "operational_failures": replay_failures,
        }
    checkpoint_index = 120
    rewind, rewind_failures = _execute_suffix_branch(
        repo,
        execution_commit=execution_commit,
        task_digest=task_digest,
        case=case,
        condition_id=parent_result["condition_id"],
        parent_chain=parent,
        checkpoint_index=checkpoint_index,
        branch_token="rewind-replay",
        branch_role="rewind-replay",
        alternate_first_outcome=False,
        use_fresh_processes=use_fresh_processes,
        deadline=work_deadline,
        cancel_event=cancel_event,
        fork_context=fork_context,
        worker_environment=worker_environment,
        journal=journal,
        journal_scope="rollback-rewind",
    )
    alternate, alternate_failures = _execute_suffix_branch(
        repo,
        execution_commit=execution_commit,
        task_digest=task_digest,
        case=case,
        condition_id=parent_result["condition_id"],
        parent_chain=parent,
        checkpoint_index=checkpoint_index,
        branch_token="alternate",
        branch_role="alternate",
        alternate_first_outcome=True,
        use_fresh_processes=use_fresh_processes,
        deadline=work_deadline,
        cancel_event=cancel_event,
        fork_context=fork_context,
        worker_environment=worker_environment,
        journal=journal,
        journal_scope="rollback-alternate",
    )
    gates = rollback_gates(
        parent,
        parent_replay,
        rewind,
        alternate,
        checkpoint_index=checkpoint_index,
    )
    operational_failures = (
        replay_failures + rewind_failures + alternate_failures
    )
    if operational_failures or time.monotonic() > deadline:
        gates = {name: False for name in ROLLBACK_REPLAY_GATES}
    return gates, {
        "status": "passed" if all(gates.values()) else "failed",
        "failure_code": None if all(gates.values()) else "rollback-operational-failure",
        "checkpoint_index": checkpoint_index,
        "parent_trace_sha256": parent["trace_sha256"],
        "parent_replay": parent_replay,
        "rewind_branch": rewind,
        "alternate_branch": alternate,
        "operational_failures": operational_failures,
    }


def _learner_surface_audit(repo: Path) -> dict[str, Any]:
    logical_sources = (
        "src/open_trajectory_harness/ot0077_learning.py",
        "src/open_trajectory_harness/ot0075_learning.py",
    )
    allowed_roots = {
        "__future__",
        "base64",
        "binascii",
        "json",
        "re",
        "dataclasses",
        "typing",
    }
    imports: list[str] = []
    relative_imports: list[str] = []
    forbidden_calls: list[str] = []
    forbidden_names = {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "globals",
        "locals",
    }
    sources: dict[str, str] = {}
    for logical in logical_sources:
        source = (repo / logical).read_text(encoding="utf-8")
        sources[logical] = source
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    relative_imports.append(module)
                else:
                    imports.append(module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in forbidden_names:
                    forbidden_calls.append(node.func.id)
    forbidden_relative_imports = sorted(
        module for module in set(relative_imports) if module != "ot0075_learning"
    )
    forbidden_imports = sorted(set(imports) - allowed_roots)
    prohibited_text = sorted(
        token
        for token in (
            "derive_task",
            "hidden_masks",
            "hidden_schedule",
            "subprocess",
            "socket",
            "pathlib",
            "urllib",
            "requests",
            "task_loader",
        )
        if any(token in source for source in sources.values())
    )
    module_sha256s = {
        logical: sha256_file(repo / logical) for logical in logical_sources
    }
    inherited_identity_pass = (
        module_sha256s[logical_sources[1]]
        == INHERITED_SOURCE_SHA256S[logical_sources[1]]
    )
    passed = not (
        forbidden_relative_imports
        or forbidden_imports
        or forbidden_calls
        or prohibited_text
    ) and inherited_identity_pass
    return {
        "pass": passed,
        "module_sha256s": module_sha256s,
        "import_roots": sorted(set(imports)),
        "relative_imports": sorted(set(relative_imports)),
        "forbidden_relative_imports": forbidden_relative_imports,
        "forbidden_imports": forbidden_imports,
        "forbidden_calls": sorted(set(forbidden_calls)),
        "prohibited_symbols": prohibited_text,
        "inherited_identity_pass": inherited_identity_pass,
    }


def _and_gate_maps(
    maps: list[dict[str, bool]], expected: tuple[str, ...]
) -> dict[str, bool]:
    if not maps or any(set(item) != set(expected) for item in maps):
        raise ProtocolError("gate map collection differs from the frozen schema")
    return {name: all(item[name] for item in maps) for name in expected}


def _scientific_gate_evidence(
    repo: Path,
    *,
    lineages: list[dict[str, Any]],
    rollback_map: dict[str, bool],
    use_fresh_processes: bool,
) -> dict[str, Any]:
    chains = [item["chain"] for item in lineages if item["chain"] is not None]
    positive_results = [
        item
        for item in lineages
        if item["condition"]["role"] == "positive-reference"
    ]
    positive_trace_ids = [
        item["chain"]["trace_sha256"]
        for item in positive_results
        if item.get("chain") is not None
        and item.get("operational_complete") is True
        and item.get("terminal_audit_completed") is True
        and item.get("chain_validation", {}).get("authority_eligible") is True
    ]
    collection = (
        validate_chain_collection(
            chains,
            online_admissible_trace_ids=positive_trace_ids,
        )
        if chains
        else {
            "case_count": 0,
            "chain_count": 0,
            "encounter_count": 0,
            "fresh_consumer_count": 0,
            "trace_sha256s": [],
            "receipt_sha256": derive_identity("empty-chain-collection"),
        }
    )
    causal_maps: list[dict[str, bool]] = []
    for item in positive_results:
        if item.get("chain") is None:
            causal_maps.append({name: False for name in CAUSAL_PATH_GATES})
            continue
        gates = causal_path_gates(item["chain"], require_online_admissible=False)
        if item.get("operational_complete") is not True:
            gates["next_fresh_process_consumes_exact_projection"] = False
            gates["fresh_process_workspace_receipts"] = False
        if item.get("terminal_audit_completed") is not True:
            gates["terminal_projection_has_audit_consumer"] = False
            gates["fresh_process_workspace_receipts"] = False
        causal_maps.append(gates)
    causal = _and_gate_maps(causal_maps, CAUSAL_PATH_GATES)
    surface_audit = _learner_surface_audit(repo)
    for name in (
        "next_fresh_process_consumes_exact_projection",
        "fresh_process_workspace_receipts",
        "forbidden_continuity_channel_sentinels",
    ):
        causal[name] = causal[name] and use_fresh_processes
    causal["online_reference_reachable_surface_audit"] = (
        causal["online_reference_reachable_surface_audit"]
        and surface_audit["pass"]
    )

    compact = next(
        item
        for item in positive_results
        if item["case_index"] == 0
        and item["condition"]["mechanism_id"] == COMPACT_REFERENCE
    )
    defects = (
        seeded_authority_defect_gates(compact["chain"])
        if compact.get("chain") is not None
        else {name: False for name in AUTHORITY_DEFECTS}
    )
    if set(defects) != set(AUTHORITY_DEFECTS):
        raise ProtocolError("authority defect gate inventory differs")
    wrong_lineage_results = [
        item
        for item in lineages
        if item["condition"]["intervention_id"] == "wrong-lineage-projection"
    ]
    wrong_lineage_pass = bool(wrong_lineage_results) and all(
        item.get("wrong_lineage_rejection", {}).get("substitution_rejected") is True
        and item.get("wrong_lineage_rejection", {}).get(
            "observed_rejection_code"
        )
        == "sibling-branch-substitution"
        and item["chain_validation"].get("rejected_before_prediction_count") == 242
        for item in wrong_lineage_results
    )
    defects["sibling-branch-substitution"] = (
        defects["sibling-branch-substitution"] and wrong_lineage_pass
    )

    online_reference_authority = all(
        item["chain_validation"]["authority_eligible"] is True
        and item.get("operational_complete") is True
        and item.get("terminal_audit_completed") is True
        for item in positive_results
    )
    controls = [
        item
        for item in lineages
        if item["condition"]["role"] == "required-control"
    ]
    control_authority = all(
        item["chain_validation"]["authority_eligible"] is False
        for item in controls
    )
    comparators = [
        item
        for item in lineages
        if item["condition"]["role"] == "adaptive-comparator"
    ]
    adaptive_authority = all(
        item["chain_validation"]["authority_eligible"] is False
        for item in comparators
    )
    online = [item for item in lineages if item["chain"] is not None]
    operationally_incomplete = [
        item
        for item in lineages
        if "operational_complete" in item
        and item["operational_complete"] is not True
    ]
    reset_lineages = [
        item
        for item in lineages
        if item["condition"]["intervention_id"] == "cross-episode-state-reset"
    ]
    expected_resets = len(EPISODE_SCHEDULE) - 1
    episode_reset_transition_pass = bool(reset_lineages) and all(
        item["chain_validation"].get("episode_reset_count") == expected_resets
        and item.get("episode_reset_evidence", {}).get("episode_reset_count")
        == expected_resets
        for item in reset_lineages
    )
    state_budget = all(
        item.get("maximum_projection_bytes", 0) <= 2_048 for item in online
    )
    operation_budget = all(
        item.get("maximum_prediction_operations", 0) <= 131_072
        and item.get("maximum_update_operations", 0) <= 131_072
        for item in online
    )
    reset_receipts = (
        use_fresh_processes
        and not operationally_incomplete
        and episode_reset_transition_pass
        and collection["fresh_consumer_count"]
        == sum(item["chain_validation"]["encounter_count"] + 1 for item in online)
        and all(
            len(item["worker_response_sha256s"])
            == item["chain_validation"]["encounter_count"] + 1
            for item in online
        )
    )
    return {
        "authority_defect_rejections": defects,
        "causal_path_gates": causal,
        "rollback_replay_gates": {
            name: rollback_map[name] for name in ROLLBACK_REPLAY_GATES
        },
        "collection_receipt": collection,
        "surface_audit": surface_audit,
        "wrong_lineage_rejections": [
            copy.deepcopy(item["wrong_lineage_rejection"])
            for item in wrong_lineage_results
        ],
        "episode_reset_transitions": [
            copy.deepcopy(item["episode_reset_evidence"])
            for item in reset_lineages
        ],
        "base_execution_gates": {
            "online_reference_authority": online_reference_authority,
            "control_authority": control_authority,
            "adaptive_comparator_authority": adaptive_authority,
            "state_projection_budgets": state_budget,
            "operation_budgets": operation_budget,
            "fresh_reset_receipts": reset_receipts,
            "candidate_free": True,
        },
        "authority_defect_expected_codes": {
            defect: expected_mutation_code(defect) for defect in AUTHORITY_DEFECTS
        },
    }


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    """Kill and reap one supervised process and all of its descendants."""

    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except OSError:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _capture_process_bounded(
    process: subprocess.Popen[bytes],
    *,
    input_bytes: bytes,
    deadline: float,
    stdout_limit: int,
    stderr_limit: int,
    inside_authority_group: bool,
    invalidate_authority_group: bool,
) -> dict[str, Any]:
    """Stream one process response without allocating past either ceiling."""

    if (
        type(stdout_limit) is not int
        or stdout_limit < 1
        or type(stderr_limit) is not int
        or stderr_limit < 1
    ):
        _kill_process_group(process)
        return {
            "status": "io-failed",
            "returncode": None,
            "stdout": b"",
            "stderr": b"",
        }
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_done = threading.Event()
    stderr_done = threading.Event()
    writer_done = threading.Event()
    overflow = threading.Event()
    io_failed = threading.Event()
    stopping = threading.Event()
    changed = threading.Event()

    def read_pipe(
        descriptor: int,
        limit: int,
        chunks: list[bytes],
        done: threading.Event,
    ) -> None:
        total = 0
        try:
            while True:
                chunk = os.read(
                    descriptor,
                    max(1, min(65_536, limit - total + 1)),
                )
                if not chunk:
                    return
                if len(chunk) > limit - total:
                    overflow.set()
                    changed.set()
                    return
                chunks.append(chunk)
                total += len(chunk)
        except OSError:
            if not stopping.is_set():
                io_failed.set()
                changed.set()
        finally:
            done.set()
            changed.set()

    def write_input() -> None:
        remaining = memoryview(input_bytes)
        try:
            while remaining:
                written = os.write(process.stdin.fileno(), remaining)
                if written <= 0:
                    raise OSError("supervised stdin write made no progress")
                remaining = remaining[written:]
        except BrokenPipeError:
            pass
        except OSError:
            if not stopping.is_set() and process.poll() is None:
                io_failed.set()
                changed.set()
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass
            writer_done.set()
            changed.set()

    threads = (
        threading.Thread(
            target=read_pipe,
            args=(
                process.stdout.fileno(),
                stdout_limit,
                stdout_chunks,
                stdout_done,
            ),
            daemon=True,
        ),
        threading.Thread(
            target=read_pipe,
            args=(
                process.stderr.fileno(),
                stderr_limit,
                stderr_chunks,
                stderr_done,
            ),
            daemon=True,
        ),
        threading.Thread(target=write_input, daemon=True),
    )
    for thread in threads:
        thread.start()

    status = "completed"
    while True:
        if overflow.is_set():
            status = "output-limit"
            break
        if io_failed.is_set():
            status = "io-failed"
            break
        if time.monotonic() > deadline:
            status = "timeout"
            break
        returncode = process.poll()
        if (
            returncode is not None
            and stdout_done.is_set()
            and stderr_done.is_set()
            and writer_done.is_set()
        ):
            break
        changed.wait(max(0.001, min(0.02, deadline - time.monotonic())))
        changed.clear()

    if status != "completed":
        stopping.set()
        if (
            os.name == "posix"
            and inside_authority_group
            and invalidate_authority_group
        ):
            os.killpg(os.getpgrp(), signal.SIGKILL)
        _kill_process_group(process)
    elif time.monotonic() > deadline:
        status = "timeout"
        stopping.set()
        _kill_process_group(process)

    for thread in threads:
        thread.join(timeout=0.1)
    for pipe in (process.stdout, process.stderr):
        try:
            pipe.close()
        except OSError:
            pass
    if status != "completed":
        return {
            "status": status,
            "returncode": None,
            "stdout": b"",
            "stderr": b"",
        }
    return {
        "status": "completed",
        "returncode": process.returncode,
        "stdout": b"".join(stdout_chunks),
        "stderr": b"".join(stderr_chunks),
    }


def _communicate_bounded(
    command: list[str],
    *,
    repo: Path,
    deadline: float,
    input_bytes: bytes = b"",
    environment: dict[str, str] | None = None,
    stdout_limit: int | None = None,
    stderr_limit: int | None = None,
) -> dict[str, Any]:
    """Run a killable process group under one absolute controller deadline."""

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return {
            "status": "timeout",
            "returncode": None,
            "stdout": b"",
            "stderr": b"",
        }
    inside_authority_group = bool(
        os.name == "posix"
        and os.environ.get(_AUTHORITY_GROUP_ENV) == "1"
        and os.getpgrp() == os.getsid(0)
    )
    child_env = dict(environment or child_environment(repo))
    child_env[_AUTHORITY_GROUP_ENV] = "1"
    try:
        process = subprocess.Popen(
            command,
            cwd=repo,
            env=child_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Exactly one session/process group owns the whole authority tree.
            # Nested supervisors inherit it so an outer kill cannot strand a
            # detached grandchild.
            start_new_session=os.name == "posix" and not inside_authority_group,
        )
    except OSError:
        return {
            "status": "spawn-failed",
            "returncode": None,
            "stdout": b"",
            "stderr": b"",
        }
    return _capture_process_bounded(
        process,
        input_bytes=input_bytes,
        deadline=deadline,
        stdout_limit=(
            MAX_PROCESS_STDOUT_BYTES if stdout_limit is None else stdout_limit
        ),
        stderr_limit=(
            MAX_PROCESS_STDERR_BYTES if stderr_limit is None else stderr_limit
        ),
        inside_authority_group=inside_authority_group,
        invalidate_authority_group=True,
    )


def _bounded_command(
    command: list[str],
    repo: Path,
    deadline: float,
    stage: str,
) -> dict[str, Any]:
    process = _communicate_bounded(
        command,
        repo=repo,
        deadline=deadline,
        environment=child_environment(repo),
    )
    if process["status"] == "timeout":
        return {"status": f"{stage}_timeout", "returncode": None}
    if process["status"] != "completed":
        return {"status": f"{stage}_failed", "returncode": None}
    return {
        "status": "passed" if process["returncode"] == 0 else f"{stage}_failed",
        "returncode": process["returncode"],
    }


def _operational_evidence(
    *,
    lineages: list[dict[str, Any]],
    rollback_evidence: dict[str, Any],
    tests: dict[str, Any],
    audit: dict[str, Any],
    deadline_exhausted: bool,
) -> dict[str, Any]:
    prediction_timeout_count = 0
    prediction_missing_count = 0
    terminal_audit_failures: list[dict[str, Any]] = []
    condition_failure_count = 0
    for item in lineages:
        statuses = item["condition"]["prediction_statuses"]
        prediction_timeout_count += statuses.count("timeout")
        prediction_missing_count += statuses.count("missing")
        failures = item.get("operational_failures", [])
        condition_failure_count += len(failures)
        terminal_audit_failures.extend(
            {
                "attempt_status": failure["attempt_status"],
                "case_index": item["case_index"],
                "condition_id": item["condition_id"],
                "failure_code": failure["failure_code"],
            }
            for failure in failures
            if failure["mode"] == "terminal-audit"
        )
    rollback_failures = copy.deepcopy(
        rollback_evidence.get("operational_failures", [])
        if type(rollback_evidence) is dict
        else []
    )
    verification_failures = [
        {"stage": stage, "status": result.get("status")}
        for stage, result in (("tests", tests), ("audit", audit))
        if result.get("status") != "passed"
    ]
    globally_invalidated = bool(
        prediction_timeout_count
        or prediction_missing_count
        or terminal_audit_failures
        or condition_failure_count
        or rollback_failures
        or verification_failures
        or deadline_exhausted
    )
    return {
        "schema_version": 1,
        "prediction_timeout_count": prediction_timeout_count,
        "prediction_missing_count": prediction_missing_count,
        "condition_failure_count": condition_failure_count,
        "terminal_audit_failures": terminal_audit_failures,
        "rollback_operational_failures": rollback_failures,
        "verification_failures": verification_failures,
        "stage_deadline_exhausted": deadline_exhausted,
        "globally_invalidated": globally_invalidated,
    }


def _score_with_independence(
    bundle: dict[str, Any],
    *,
    task_metamorphic: dict[str, bool],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    working = copy.deepcopy(bundle)
    working["execution_gates"]["metamorphic_dispositions"] = True
    working["execution_gates"]["primary_shadow_agreement"] = True
    primary = score_bundle(working)
    shadow = score_bundle_shadow(working)
    scorer_agreement = canonical_json(primary) == canonical_json(shadow)
    trace_variant_results: dict[str, Any] = {}
    trace_variants_pass = True
    for name, variant in metamorphic_variants(working).items():
        variant_primary = score_bundle(variant)
        variant_shadow = score_bundle_shadow(variant)
        primary_equal = canonical_json(variant_primary) == canonical_json(primary)
        shadow_equal = canonical_json(variant_shadow) == canonical_json(shadow)
        cross_equal = canonical_json(variant_primary) == canonical_json(variant_shadow)
        passed = primary_equal and shadow_equal and cross_equal
        trace_variants_pass = trace_variants_pass and passed
        trace_variant_results[name] = {
            "pass": passed,
            "primary_sha256": sha256_bytes(canonical_json(variant_primary)),
            "shadow_sha256": sha256_bytes(canonical_json(variant_shadow)),
        }
    metamorphic_pass = trace_variants_pass and all(task_metamorphic.values())
    working["execution_gates"]["metamorphic_dispositions"] = metamorphic_pass
    working["execution_gates"]["primary_shadow_agreement"] = scorer_agreement
    primary = score_bundle(working)
    shadow = score_bundle_shadow(working)
    final_agreement = canonical_json(primary) == canonical_json(shadow)
    if final_agreement != scorer_agreement:
        raise ProtocolError("primary/shadow agreement changed after final gate binding")
    return primary, shadow, {
        "task_level": task_metamorphic,
        "trace_level": trace_variant_results,
        "metamorphic_pass": metamorphic_pass,
        "primary_shadow_agreement": final_agreement,
        "primary_sha256": sha256_bytes(canonical_json(primary)),
        "shadow_sha256": sha256_bytes(canonical_json(shadow)),
        "scorer_bundle": working,
    }


def run_calibration(
    repo: Path,
    task: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    execution_commit: str,
    use_fresh_processes: bool,
    clean_private_reconstruction: bool,
    run_verification_commands: bool,
    deadline: float | None = None,
    journal_root: Path | None = None,
    journal_logical_path: str | None = None,
) -> dict[str, Any]:
    """Execute one complete design or private-anchor evaluator workload."""

    repo = repo.resolve()
    validate_task(task)
    execution_commit = _commit(execution_commit, "calibration execution")
    if acceptance.get("experiment_id") != EXPERIMENT_ID:
        raise ProtocolError("calibration acceptance identity differs")
    if deadline is None:
        deadline = time.monotonic() + CALIBRATION_SECONDS
    purpose = task["purpose"]
    fork_context = _payload_blind_forkserver(repo) if use_fresh_processes else None
    journal: SegmentedEncounterJournal | None = None
    if use_fresh_processes and journal_root is None and journal_logical_path is None:
        raise ProtocolError("fresh calibration requires a durable encounter journal")
    if journal_root is not None or journal_logical_path is not None:
        if (
            journal_root is None
            or journal_logical_path is None
            or not use_fresh_processes
        ):
            raise ProtocolError("encounter journal authority inputs differ")
        horizons = {case["horizon"] for case in task["cases"]}
        if len(horizons) != 1:
            raise ProtocolError("journal task horizons differ")
        horizon = next(iter(horizons))
        online_per_case = sum(
            _mechanism_for(descriptor) is not None
            and descriptor[3] != "wrong-lineage-projection"
            for descriptor in CONDITION_INVENTORY
        )
        main_segments = task["case_count"] * online_per_case
        expected_scope_counts = {
            "main": {
                "segments": main_segments,
                "encounters": main_segments * horizon,
            },
            "rollback-parent-replay": {
                "segments": 1,
                "encounters": horizon,
            },
            "rollback-rewind": {
                "segments": 1,
                "encounters": horizon - 121,
            },
            "rollback-alternate": {
                "segments": 1,
                "encounters": horizon - 121,
            },
        }
        journal = SegmentedEncounterJournal.create(
            journal_root,
            run_id=f"{DEFAULT_RUN_ID}-{purpose}",
            logical_path=journal_logical_path,
            purpose=purpose,
            task_sha256=sha256_bytes(canonical_json(task)),
            execution_git_commit=execution_commit,
            expected_case_count=task["case_count"],
            expected_scope_counts=expected_scope_counts,
        )
    scorer_cases, lineages = _execute_all_conditions(
        repo,
        execution_commit=execution_commit,
        task=task,
        use_fresh_processes=use_fresh_processes,
        deadline=deadline,
        fork_context=fork_context,
        journal=journal,
    )
    rollback_map, rollback_evidence = _execute_rollback_suite(
        repo,
        execution_commit=execution_commit,
        task=task,
        lineages=lineages,
        use_fresh_processes=use_fresh_processes,
        deadline=deadline,
        fork_context=fork_context,
        journal=journal,
    )
    gate_evidence = _scientific_gate_evidence(
        repo,
        lineages=lineages,
        rollback_map=rollback_map,
        use_fresh_processes=use_fresh_processes,
    )
    task_metamorphic = _task_metamorphic_gates(task)

    if run_verification_commands:
        tests = _bounded_command(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            repo,
            deadline,
            "tests",
        )
        audit = _bounded_command(
            [sys.executable, "-m", "open_trajectory_evidence", "audit"],
            repo,
            deadline,
            "audit",
        )
    else:
        tests = {"status": "not-run", "returncode": None, "mode": "omitted"}
        audit = {"status": "not-run", "returncode": None, "mode": "omitted"}
    execution_gates = {
        **gate_evidence["base_execution_gates"],
        "metamorphic_dispositions": True,
        "primary_shadow_agreement": True,
        "clean_private_reconstruction": clean_private_reconstruction,
        "tests": tests["status"] == "passed",
        "evidence_audit": audit["status"] == "passed",
        "privacy_audit": audit["status"] == "passed",
        # Bound provisionally for scorer construction, then bind the observed
        # value only after primary, shadow, metamorphic, and operational work.
        "within_wall_budget": True,
    }
    if set(execution_gates) != set(EXECUTION_GATES):
        raise ProtocolError("execution gate inventory differs")
    bundle = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": purpose,
        "case_count": task["case_count"],
        "cases": scorer_cases,
        "authority_defect_rejections": gate_evidence[
            "authority_defect_rejections"
        ],
        "causal_path_gates": gate_evidence["causal_path_gates"],
        "rollback_replay_gates": gate_evidence["rollback_replay_gates"],
        "execution_gates": execution_gates,
    }
    primary, shadow, scorer_evidence = _score_with_independence(
        bundle,
        task_metamorphic=task_metamorphic,
    )
    authoritative_bundle = scorer_evidence.pop("scorer_bundle")
    operational_evidence = _operational_evidence(
        lineages=lineages,
        rollback_evidence=rollback_evidence,
        tests=tests,
        audit=audit,
        deadline_exhausted=False,
    )
    within_wall_budget = time.monotonic() <= deadline
    if not within_wall_budget:
        authoritative_bundle["execution_gates"]["within_wall_budget"] = False
        primary = score_bundle(copy.deepcopy(authoritative_bundle))
        shadow = score_bundle_shadow(copy.deepcopy(authoritative_bundle))
        scorer_evidence["primary_shadow_agreement"] = (
            canonical_json(primary) == canonical_json(shadow)
        )
        scorer_evidence["primary_sha256"] = sha256_bytes(canonical_json(primary))
        scorer_evidence["shadow_sha256"] = sha256_bytes(canonical_json(shadow))
        operational_evidence = _operational_evidence(
            lineages=lineages,
            rollback_evidence=rollback_evidence,
            tests=tests,
            audit=audit,
            deadline_exhausted=True,
        )
    promoted = (
        purpose == "anchor"
        and primary["anchor_promotion_pass"] is True
        and shadow["anchor_promotion_pass"] is True
    )
    design_pass = (
        purpose == "design"
        and primary["trace_gate_pass"] is True
        and shadow["trace_gate_pass"] is True
    )
    scientific = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": purpose,
        "execution_git_commit": execution_commit,
        "task": task,
        "task_sha256": sha256_bytes(canonical_json(task)),
        "candidate_outputs": False,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_model_calls": 0,
        "lineages": lineages,
        "rollback_evidence": rollback_evidence,
        "operational_evidence": operational_evidence,
        "gate_evidence": gate_evidence,
        "scorer_bundle": authoritative_bundle,
        "primary_score": primary,
        "shadow_score": shadow,
        "scorer_independence": scorer_evidence,
        "verification": {"tests": tests, "audit": audit},
        "within_wall_budget": within_wall_budget,
        "calibration_pass": promoted or design_pass,
        "disposition": (
            "promoted"
            if promoted
            else "design-passed"
            if design_pass
            else "invalidated"
        ),
        "authorized_actor_candidate_count": 1 if promoted else 0,
        "claim_limit": "candidate-free evaluator-visible surrogate calibration only",
    }
    if journal is not None:
        binding = journal.seal(
            scientific_sha256=sha256_bytes(canonical_json(scientific))
        )
        scientific = {**scientific, "encounter_journal": binding}
    return scientific


def _calibration_worker_entry() -> int:
    """Execute the scientific stage inside a killable authority boundary."""

    try:
        payload = sys.stdin.buffer.read(67_108_865)
        if len(payload) > 67_108_864:
            raise ProtocolError("calibration worker envelope exceeds its bound")
        envelope = json.loads(payload)
        if canonical_json(envelope) != payload:
            raise ProtocolError("calibration worker envelope is not canonical")
        _exact(
            envelope,
            {
                "schema_version",
                "experiment_id",
                "task",
                "execution_commit",
                "clean_private_reconstruction",
                "run_verification_commands",
                "deadline_milliseconds",
                "journal_root",
                "journal_logical_path",
                "output_mode",
                "implementation_commit",
                "store_identity",
            },
            "calibration worker envelope",
        )
        milliseconds = envelope["deadline_milliseconds"]
        if (
            envelope["schema_version"] != 1
            or envelope["experiment_id"] != EXPERIMENT_ID
            or type(milliseconds) is not int
            or not 0 < milliseconds <= CALIBRATION_SECONDS * 1_000
            or type(envelope["clean_private_reconstruction"]) is not bool
            or type(envelope["run_verification_commands"]) is not bool
            or type(envelope["journal_root"]) is not str
            or type(envelope["journal_logical_path"]) is not str
            or envelope["output_mode"] not in {"scientific", "sealed-raw"}
        ):
            raise ProtocolError("calibration worker identity differs")
        if (
            envelope["output_mode"] == "scientific"
            and (
                envelope["implementation_commit"] is not None
                or envelope["store_identity"] is not None
            )
        ):
            raise ProtocolError("scientific worker received raw authority")
        if envelope["output_mode"] == "sealed-raw":
            _commit(envelope["implementation_commit"], "worker implementation")
            _validated_authority_identity(
                envelope["store_identity"],
                "evidence store",
            )
            if (
                envelope["task"].get("purpose") != "anchor"
                or envelope["clean_private_reconstruction"] is not False
            ):
                raise ProtocolError("raw worker purpose or reconstruction gate differs")
        repo = Path.cwd().resolve()
        journal_root = Path(envelope["journal_root"])
        if not journal_root.is_absolute():
            raise ProtocolError("calibration journal path is not absolute")
        journal_root = journal_root.resolve()
        evidence_root = _store(repo)
        try:
            journal_root.relative_to(evidence_root)
        except ValueError as error:
            raise ProtocolError("calibration journal leaves the evidence root") from error
        expected_logical = _logical(
            PUBLIC_JOURNAL_RELATIVE_PATH
            if envelope["task"].get("purpose") == "design"
            else ANCHOR_JOURNAL_RELATIVE_PATH
        )
        if envelope["journal_logical_path"] != expected_logical:
            raise ProtocolError("calibration journal logical identity differs")
        worker_deadline = time.monotonic() + milliseconds / 1_000
        execution_commit = _commit(
            envelope["execution_commit"],
            "calibration worker execution",
        )
        scientific = run_calibration(
            repo,
            envelope["task"],
            validate_acceptance(repo),
            execution_commit=execution_commit,
            use_fresh_processes=True,
            clean_private_reconstruction=envelope["clean_private_reconstruction"],
            run_verification_commands=envelope["run_verification_commands"],
            deadline=worker_deadline,
            journal_root=journal_root,
            journal_logical_path=envelope["journal_logical_path"],
        )
        if envelope["output_mode"] == "sealed-raw":
            raw = build_raw(
                implementation_commit=envelope["implementation_commit"],
                execution_commit=execution_commit,
                scientific=scientific,
                repo=repo,
                deadline=worker_deadline,
            )
            encoded = _materialize_raw_transaction(
                repo,
                raw,
                deadline=worker_deadline,
                expected_store_identity=envelope["store_identity"],
            )
        else:
            scientific_bytes = canonical_json(scientific)
            if len(scientific_bytes) > MAX_UNCOMPRESSED_RAW_BYTES:
                raise ProtocolError(
                    "calibration worker output exceeds its decoded bound"
                )
            encoded = zlib.compress(scientific_bytes, level=9)
            if len(encoded) > MAX_RAW_BYTES:
                raise ProtocolError("calibration worker output exceeds its bound")
        sys.stdout.buffer.write(encoded)
        return 0
    except (OSError, RuntimeError, TypeError, ValueError, zlib.error):
        # Never echo a private task, path, exception, or partial trace.
        sys.stderr.write("OT-0077 calibration worker failed\n")
        return 2


def _bounded_zlib_decompress(
    encoded: bytes,
    *,
    limit: int = MAX_UNCOMPRESSED_RAW_BYTES,
) -> bytes:
    """Decode one complete zlib member without permitting expansion past limit."""

    if type(encoded) is not bytes or type(limit) is not int or limit < 1:
        raise ProtocolError("bounded compressed input is unavailable")
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(encoded, limit + 1)
    except zlib.error as error:
        raise ProtocolError("bounded compressed input is invalid") from error
    if (
        len(raw) > limit
        or decoder.unconsumed_tail
        or not decoder.eof
        or decoder.unused_data
    ):
        raise ProtocolError("bounded compressed input framing or expansion differs")
    return raw


def _decode_scientific_payload(encoded: bytes) -> dict[str, Any]:
    if not encoded or len(encoded) > MAX_RAW_BYTES:
        raise ProtocolError("bounded calibration output size differs")
    try:
        raw = _bounded_zlib_decompress(encoded)
        value = json.loads(raw)
    except (ProtocolError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("bounded calibration output is invalid") from error
    if type(value) is not dict or canonical_json(value) != raw:
        raise ProtocolError("bounded calibration output is not canonical")
    return value


def _run_calibration_bounded(
    repo: Path,
    task: dict[str, Any],
    *,
    execution_commit: str,
    clean_private_reconstruction: bool,
    run_verification_commands: bool,
    deadline: float,
    journal_root: Path,
    journal_logical_path: str,
    materialize_raw: bool = False,
    implementation_commit: str | None = None,
    expected_store_identity: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Supervise all threads and descendants behind a hard process boundary."""

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProtocolError("calibration authority deadline expired")
    journal_root = journal_root.resolve()
    evidence_root = _store(repo)
    try:
        journal_root.relative_to(evidence_root)
    except ValueError as error:
        raise ProtocolError("calibration journal leaves the evidence root") from error
    expected_logical = _logical(
        PUBLIC_JOURNAL_RELATIVE_PATH
        if task.get("purpose") == "design"
        else ANCHOR_JOURNAL_RELATIVE_PATH
    )
    if journal_logical_path != expected_logical:
        raise ProtocolError("calibration journal logical identity differs")
    if materialize_raw:
        if (
            task.get("purpose") != "anchor"
            or clean_private_reconstruction is not False
            or implementation_commit is None
        ):
            raise ProtocolError("bounded raw materialization authority differs")
        implementation_commit = _commit(
            implementation_commit,
            "materialization implementation",
        )
        if expected_store_identity is None:
            expected_store_identity = _authority_root_identity(
                evidence_root,
                "evidence store",
            )
        else:
            expected_store_identity = _validated_authority_identity(
                expected_store_identity,
                "evidence store",
            )
        pinned_store = _open_authority_root(
            evidence_root,
            expected_store_identity,
            "evidence store",
        )
        os.close(pinned_store)
        raw_target = (evidence_root / RAW_RELATIVE_PATH).resolve()
        raw_staging = (evidence_root / RAW_STAGING_RELATIVE_PATH).resolve()
        try:
            raw_target.relative_to(evidence_root)
            raw_staging.relative_to(evidence_root)
        except ValueError as error:
            raise ProtocolError("raw materialization leaves the evidence root") from error
        if (
            raw_target.exists()
            or raw_target.is_symlink()
            or raw_staging.exists()
            or raw_staging.is_symlink()
        ):
            raise ProtocolError("raw materialization destination exists")
    elif implementation_commit is not None or expected_store_identity is not None:
        raise ProtocolError("scientific calibration received raw implementation authority")
    journal_root.parent.mkdir(parents=True, exist_ok=True)
    if journal_root.exists() or journal_root.is_symlink():
        raise ProtocolError("calibration journal root already exists")
    envelope = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "task": task,
        "execution_commit": _commit(execution_commit, "execution"),
        "clean_private_reconstruction": clean_private_reconstruction,
        "run_verification_commands": run_verification_commands,
        "deadline_milliseconds": max(1, min(int(remaining * 1_000) - 1, 900_000)),
        "journal_root": str(journal_root),
        "journal_logical_path": journal_logical_path,
        "output_mode": "sealed-raw" if materialize_raw else "scientific",
        "implementation_commit": implementation_commit,
        "store_identity": expected_store_identity,
    }
    command = (
        "import sys; from open_trajectory_harness.ot0077 import "
        "_calibration_worker_entry; raise SystemExit(_calibration_worker_entry())"
    )
    process = _communicate_bounded(
        [sys.executable, "-S", "-c", command],
        repo=repo,
        deadline=deadline,
        input_bytes=canonical_json(envelope),
        environment=_worker_environment(repo),
    )
    if process["status"] == "timeout":
        raise ProtocolError("calibration authority process timed out")
    if (
        process["status"] != "completed"
        or process["returncode"] != 0
        or process["stderr"]
    ):
        raise ProtocolError("calibration authority process failed")
    if materialize_raw:
        if (
            not process["stdout"]
            or len(process["stdout"]) > MAX_RAW_BYTES
        ):
            raise ProtocolError("raw materialization transaction did not commit exactly")
        assert expected_store_identity is not None
        store_descriptor = _open_authority_root(
            evidence_root,
            expected_store_identity,
            "evidence store",
        )
        raw_descriptor: int | None = None
        staging_parent: int | None = None
        try:
            raw_descriptor = _open_relative_regular(
                store_descriptor,
                RAW_RELATIVE_PATH,
                limit=MAX_RAW_BYTES,
                label="materialized raw",
            )
            encoded = _read_regular_descriptor_bounded(
                raw_descriptor,
                limit=MAX_RAW_BYTES,
                label="materialized raw",
            )
            staging_parent, staging_name = _open_relative_parent(
                store_descriptor,
                RAW_STAGING_RELATIVE_PATH,
                create=False,
                label="raw staging",
            )
            try:
                os.stat(
                    staging_name,
                    dir_fd=staging_parent,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise ProtocolError(
                    "raw materialization transaction did not commit exactly"
                )
        finally:
            if staging_parent is not None:
                os.close(staging_parent)
            if raw_descriptor is not None:
                os.close(raw_descriptor)
            os.close(store_descriptor)
        rebound_store = _open_authority_root(
            evidence_root,
            expected_store_identity,
            "evidence store",
        )
        os.close(rebound_store)
        if encoded != process["stdout"]:
            raise ProtocolError("raw file differs from the supervised worker response")
        raw = decode_raw(encoded)
        checked = _validate_prepublication_raw(
            raw,
            encoded_raw=encoded,
            repo=repo,
            deadline=deadline,
        )
        if (
            checked["implementation_git_commit"] != implementation_commit
            or checked["execution_git_commit"] != execution_commit
            or checked["scientific"]["execution_git_commit"] != execution_commit
        ):
            raise ProtocolError("materialized raw identity differs")
        if time.monotonic() > deadline:
            raise ProtocolError("raw materialization process exceeded its deadline")
        return checked
    scientific = _decode_scientific_payload(process["stdout"])
    if time.monotonic() > deadline:
        raise ProtocolError("calibration authority process exceeded its deadline")
    return scientific


def _causal_evidence_from_validation(
    validation: ChainValidation,
) -> dict[str, Any]:
    return {
        "accepted_updates": validation.accepted_updates,
        "active_projection_changed": validation.active_projection_changed,
        "candidate_state_changed": validation.candidate_state_changed,
        "consumed_projection_sha256s": list(
            validation.consumed_projection_sha256s
        ),
        "terminal_projection_sha256": validation.terminal_projection_sha256,
    }


def _condition_from_validated_chain(
    chain: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
    validation: ChainValidation,
) -> dict[str, Any]:
    """Reconstruct the scorer trace from one already validated chain."""

    query_ids: list[str] = []
    outcomes: list[int] = []
    predictions: list[int | None] = []
    statuses: list[str] = []
    for offset in range(validation.encounter_count):
        base = 6 + 9 * offset
        query = chain["receipt_order"][base + 1]["payload"]["public_query"]
        prediction = chain["receipt_order"][base + 3]["payload"]
        outcome = chain["receipt_order"][base + 4]["payload"]
        query_ids.append(query["query_id"])
        predictions.append(prediction["prediction"])
        statuses.append(prediction["status"])
        outcomes.append(outcome["outcome"])
    role, mechanism_id, reference_id, intervention_id = descriptor
    return {
        "role": role,
        "mechanism_id": mechanism_id,
        "reference_id": reference_id,
        "intervention_id": intervention_id,
        "query_ids": query_ids,
        "outcomes": outcomes,
        "predictions": predictions,
        "prediction_statuses": statuses,
        "causal_evidence": _causal_evidence_from_validation(validation),
    }


def _condition_from_chain(
    chain: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
) -> dict[str, Any]:
    """Reconstruct the scorer trace from validated causal receipts."""

    validation = validate_chain(
        chain,
        require_online_admissible=descriptor[0] == "positive-reference",
    )
    return _condition_from_validated_chain(chain, descriptor, validation)


def _chain_runtime_identity_from_validation(
    chain: dict[str, Any],
    validation: ChainValidation,
    *,
    mechanism: str,
    execution_commit: str,
) -> bool:
    receipts = chain["receipt_order"]
    case_receipt = receipts[0]
    lineage_receipt = receipts[2]
    consumers = [item for item in receipts if item["kind"] == "consumer"]
    projections = [receipts[4]["payload"]["blob"]]
    projections.extend(
        receipts[6 + 9 * offset + 7]["payload"]["blob"]
        for offset in range(validation.encounter_count)
    )
    if len(consumers) != validation.encounter_count + 1:
        return False
    execution_commit = _commit(execution_commit, "retained execution")
    task_digest = case_receipt["payload"]["task_sha256"]
    condition_id = lineage_receipt["payload"]["condition_id"]
    branch_token = lineage_receipt["payload"]["branch_token"]
    sentinel_ids: set[str] = set()
    for offset, (consumer, projection) in enumerate(zip(consumers, projections)):
        facts = consumer["payload"]["facts"]
        mode = (
            "terminal-audit"
            if offset == validation.encounter_count
            else "prediction"
        )
        encounter_index = (
            case_receipt["payload"]["horizon"]
            if mode == "terminal-audit"
            else validation.encounter_start + offset
        )
        expected = _consumer_challenge_identities(
            execution_commit=execution_commit,
            task_digest=task_digest,
            case_id=validation.case_id,
            condition_id=condition_id,
            branch_token=branch_token,
            encounter_index=encounter_index,
            mode=mode,
        )
        observed = facts["forbidden_channel_sentinels"]
        observed_identities = [
            {
                "channel": item["channel"],
                "sentinel_sha256": item["sentinel_sha256"],
            }
            for item in observed
        ]
        current_ids = {item["sentinel_sha256"] for item in observed}
        if (
            facts["environment_fingerprint"]
            != _environment_fingerprint(execution_commit)
            or facts["process_challenge_sha256"]
            != expected["process_challenge_sha256"]
            or facts["workspace_challenge_sha256"]
            != expected["workspace_challenge_sha256"]
            or observed_identities != expected["sentinel_challenges"]
            or len(current_ids) != len(SENTINEL_CHANNELS)
            or sentinel_ids.intersection(current_ids)
            or not consumer_runtime_ready(facts)
        ):
            return False
        sentinel_ids.update(current_ids)
        if facts["prediction_status"] == "valid":
            response_bytes = base64.b64decode(
                facts["response_base64"], validate=True
            )
            response = json.loads(response_bytes)
            if (
                canonical_json(response) != response_bytes
                or response.get("mechanism_id") != mechanism
                or response.get("descriptor_audit_pass") is not True
                or response.get("state_bytes") != projection["byte_count"]
            ):
                return False
        elif facts["prediction_status"] != "invalid":
            return False
    return True


def _chain_runtime_identity_ready(
    chain: dict[str, Any],
    *,
    mechanism: str,
    execution_commit: str,
) -> bool:
    """Recompute process, workspace, sentinel, and response identity in a chain."""

    try:
        validation = validate_chain(chain)
        return _chain_runtime_identity_from_validation(
            chain,
            validation,
            mechanism=mechanism,
            execution_commit=execution_commit,
        )
    except (
        ReceiptError,
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return False


def _online_prediction_metrics(
    chain: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
    encounter_count: int,
) -> tuple[bool, int]:
    """Replay the fixed predictor over every exact consumed projection."""

    mechanism = _mechanism_for(descriptor)
    if mechanism is None:
        return False, 0
    receipts = chain["receipt_order"]
    if receipts[2]["payload"]["branch_role"] == "genesis":
        expected_initial = encode_state(mechanism, initial_state(mechanism))
        try:
            retained_initial_state = decode_blob(
                receipts[3]["payload"]["blob"],
                limit=2_048,
                label="semantic inherited seed state",
            )
            retained_initial_projection = decode_blob(
                receipts[4]["payload"]["blob"],
                limit=2_048,
                label="semantic inherited seed projection",
            )
        except (ReceiptError, KeyError, TypeError, ValueError):
            return False, 0
        if (
            retained_initial_state != expected_initial
            or retained_initial_projection != expected_initial
        ):
            return False, 0
    projections = [receipts[4]["payload"]["blob"]]
    projections.extend(
        receipts[6 + 9 * offset + 7]["payload"]["blob"]
        for offset in range(encounter_count)
    )
    consumers = [item for item in receipts if item["kind"] == "consumer"]
    if len(consumers) != encounter_count + 1 or len(projections) != len(consumers):
        return False, 0
    maximum = 0
    try:
        for offset in range(encounter_count):
            base = 6 + 9 * offset
            projection = decode_blob(
                projections[offset],
                limit=2_048,
                label="semantic replay projection",
            )
            query = receipts[base + 1]["payload"]["public_query"]
            prediction = receipts[base + 3]["payload"]
            facts = consumers[offset]["payload"]["facts"]
            response_bytes = base64.b64decode(
                facts["response_base64"], validate=True
            )
            try:
                expected = predict(mechanism, projection, query)
            except LearningError:
                if (
                    descriptor[3] != "one-step-stale-consequence"
                    or prediction["status"] != "invalid"
                    or prediction["prediction"] is not None
                    or facts["prediction_status"] != "invalid"
                    or response_bytes != b"consumer rejected: learning-error\n"
                ):
                    return False, 0
                continue
            if (
                prediction["status"] != "valid"
                or prediction["prediction"] != expected.prediction
                or facts["prediction_status"] != "valid"
            ):
                return False, 0
            response = json.loads(response_bytes)
            if (
                canonical_json(response) != response_bytes
                or response["mechanism_id"] != mechanism
                or response["prediction"] != expected.prediction
                or response["prediction_operations"] != expected.operations
                or response["state_bytes"] != expected.state_bytes
                or response["candidate_count"] != expected.candidate_count
            ):
                return False, 0
            maximum = max(maximum, expected.operations)

        terminal_projection = decode_blob(
            projections[-1],
            limit=2_048,
            label="semantic terminal projection",
        )
        terminal_state = decode_state(mechanism, terminal_projection)
        if encode_state(mechanism, terminal_state) != terminal_projection:
            return False, 0
        terminal_facts = consumers[-1]["payload"]["facts"]
        terminal_bytes = base64.b64decode(
            terminal_facts["response_base64"], validate=True
        )
        terminal_response = json.loads(terminal_bytes)
        if (
            canonical_json(terminal_response) != terminal_bytes
            or terminal_facts["prediction_status"] != "valid"
            or terminal_response["mechanism_id"] != mechanism
            or terminal_response["mode"] != "terminal-audit"
            or terminal_response["prediction"] is not None
            or terminal_response["prediction_operations"] != 0
            or terminal_response["state_bytes"] != len(terminal_projection)
            or terminal_response["candidate_count"] != 0
        ):
            return False, 0
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        LearningError,
    ):
        return False, 0
    return True, maximum


def _online_update_metrics(
    chain: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
    encounter_count: int,
) -> tuple[bool, int]:
    """Replay the fixed updater and every declared causal intervention exactly."""

    mechanism = _mechanism_for(descriptor)
    if mechanism is None:
        return False, 0
    maximum = 0
    expected_keys = {
        "candidate_post_sha256",
        "decision",
        "delivered_projection_sha256",
        "episode_reset_applied",
        "intervention_id",
        "schema_version",
        "update_operations",
        "update_rejected",
    }
    receipts = chain["receipt_order"]
    try:
        authoritative_state = decode_blob(
            receipts[3]["payload"]["blob"],
            limit=2_048,
            label="semantic initial state",
        )
        initial_projection = decode_blob(
            receipts[4]["payload"]["blob"],
            limit=2_048,
            label="semantic initial projection",
        )
    except (ReceiptError, KeyError, TypeError, ValueError):
        return False, 0
    active_projection = initial_projection
    prior_outcome = 0
    for offset in range(encounter_count):
        base = 6 + 9 * offset
        query = receipts[base + 1]["payload"]["public_query"]
        prediction = receipts[base + 3]["payload"]
        outcome = receipts[base + 4]["payload"]["outcome"]
        update_receipt = receipts[base + 5]["payload"]
        post_state_blob = receipts[base + 6]["payload"]["blob"]
        projection_blob = receipts[base + 7]["payload"]["blob"]
        raw = decode_blob(
            update_receipt["update_payload"],
            limit=2_048,
            label="controller update payload",
        )
        consequence_binding = "current"
        delivered_outcome: int | None = outcome
        decision = "update"
        operations = 0
        candidate_post = authoritative_state
        update_rejected = False
        if prediction["status"] != "valid":
            consequence_binding = "withheld"
            delivered_outcome = None
            decision = "no-op"
            update_rejected = True
        elif descriptor[3] == "consequence-withholding":
            consequence_binding = "withheld"
            delivered_outcome = None
            decision = "no-op"
        elif descriptor[3] == "projection-without-update":
            decision = "no-op"
        elif descriptor[0] == "matched-frozen-control":
            decision = "no-op"
        else:
            if descriptor[3] == "one-step-stale-consequence":
                consequence_binding = "one-step-stale"
                delivered_outcome = prior_outcome
            if delivered_outcome is None:
                return False, 0
            try:
                transition_result = (
                    update_from_authoritative_state(
                        mechanism,
                        authoritative_state,
                        query,
                        delivered_outcome,
                    )
                    if descriptor[3] == "update-without-projection"
                    else update(
                        mechanism,
                        authoritative_state,
                        query,
                        prediction["prediction"],
                        delivered_outcome,
                    )
                )
            except LearningError:
                if descriptor[3] != "one-step-stale-consequence":
                    return False, 0
                decision = "no-op"
                update_rejected = True
            else:
                candidate_post = encode_state(mechanism, transition_result.state)
                operations = transition_result.operations

        expected_post = (
            authoritative_state if decision == "no-op" else candidate_post
        )
        expected_projection = (
            active_projection if decision == "no-op" else candidate_post
        )
        if descriptor[3] == "update-without-projection":
            expected_projection = active_projection
        next_query = (
            receipts[base + 10]["payload"]["public_query"]
            if offset + 1 < encounter_count
            else None
        )
        reset_applied = bool(
            prediction["status"] == "valid"
            and descriptor[3] == "cross-episode-state-reset"
            and next_query is not None
            and next_query["episode_start"] is True
        )
        if reset_applied:
            expected_post = initial_projection
            expected_projection = initial_projection

        transition = update_receipt["state_transition"]
        candidate = transition.get("candidate_post_state")
        try:
            retained_candidate = decode_blob(
                candidate,
                limit=2_048,
                label="semantic candidate state",
            )
            retained_post = decode_blob(
                post_state_blob,
                limit=2_048,
                label="semantic post state",
            )
            retained_projection = decode_blob(
                projection_blob,
                limit=2_048,
                label="semantic delivered projection",
            )
        except (ReceiptError, KeyError, TypeError, ValueError):
            return False, 0
        if prediction["status"] != "valid":
            control = None
            if raw != b"":
                return False, 0
        else:
            try:
                control = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return False, 0
            expected_control = {
                "schema_version": 1,
                "decision": decision,
                "intervention_id": descriptor[3],
                "candidate_post_sha256": sha256_bytes(candidate_post),
                "delivered_projection_sha256": sha256_bytes(expected_projection),
                "episode_reset_applied": reset_applied,
                "update_operations": operations,
                "update_rejected": update_rejected,
            }
            if (
                type(control) is not dict
                or set(control) != expected_keys
                or canonical_json(control) != raw
                or control != expected_control
            ):
                return False, 0
        if (
            update_receipt["decision"] != decision
            or update_receipt["consequence_binding"] != consequence_binding
            or update_receipt["delivered_outcome"] != delivered_outcome
            or update_receipt["authoritative_pre_state_sha256"]
            != sha256_bytes(authoritative_state)
            or (transition.get("kind") == EPISODE_RESET_TRANSITION)
            is not reset_applied
            or retained_candidate != candidate_post
            or retained_post != expected_post
            or retained_projection != expected_projection
        ):
            return False, 0
        maximum = max(maximum, operations)
        authoritative_state = expected_post
        active_projection = expected_projection
        prior_outcome = outcome
    return True, maximum


def _chain_world_from_validation(
    chain: dict[str, Any],
    validation: ChainValidation,
    *,
    task_digest: str,
    case: dict[str, Any],
    expected_events: list[dict[str, Any]],
) -> bool:
    """Bind one validated chain to the frozen task's exact world."""

    try:
        receipts = chain["receipt_order"]
        case_payload = receipts[0]["payload"]
        if (
            validation.case_id != case["case_id"]
            or case_payload
            != {
                "case_index": case["case_index"],
                "horizon": case["horizon"],
                "task_sha256": task_digest,
            }
            or validation.encounter_count != len(expected_events)
            or validation.encounter_start
            != expected_events[0]["encounter_index"]
            or validation.encounter_start + validation.encounter_count
            != case["horizon"]
        ):
            return False
        for offset, event in enumerate(expected_events):
            base = 6 + 9 * offset
            encounter_payload = receipts[base]["payload"]
            query_payload = receipts[base + 1]["payload"]
            outcome_payload = receipts[base + 4]["payload"]
            expected_query = event["public_query"]
            if (
                encounter_payload
                != {
                    "encounter_index": event["encounter_index"],
                    "episode_index": event["episode_index"],
                    "episode_start": expected_query["episode_start"],
                    "query_id": expected_query["query_id"],
                }
                or query_payload["public_query"] != expected_query
                or outcome_payload["outcome"] != event["outcome"]
            ):
                return False
    except (ReceiptError, KeyError, TypeError, ValueError, IndexError):
        return False
    return True


def _chain_world_ready(
    chain: dict[str, Any],
    *,
    task_digest: str,
    case: dict[str, Any],
    expected_events: list[dict[str, Any]],
) -> bool:
    """Bind a retained chain to the frozen task's exact world, not only IDs."""

    try:
        validation = validate_chain(chain)
    except (ReceiptError, KeyError, TypeError, ValueError, IndexError):
        return False
    return _chain_world_from_validation(
        chain,
        validation,
        task_digest=task_digest,
        case=case,
        expected_events=expected_events,
    )


def _episode_resets_from_validation(
    chain: dict[str, Any],
    validation: ChainValidation,
) -> dict[str, Any]:
    resets: list[dict[str, Any]] = []
    for offset in range(validation.encounter_count):
        base = 6 + 9 * offset
        update_receipt = chain["receipt_order"][base + 5]
        transition = update_receipt["payload"]["state_transition"]
        if transition["kind"] != EPISODE_RESET_TRANSITION:
            continue
        post_state = chain["receipt_order"][base + 6]
        projection = chain["receipt_order"][base + 7]
        resets.append(
            {
                "candidate_post_state_sha256": transition[
                    "candidate_post_state"
                ]["sha256"],
                "encounter_index": update_receipt["context"]["encounter_index"],
                "post_state_receipt_sha256": post_state["receipt_sha256"],
                "post_state_sha256": post_state["payload"]["blob"]["sha256"],
                "reset_authority": transition["reset_authority"],
                "reset_target_projection_receipt_sha256": transition[
                    "reset_target_projection_receipt_sha256"
                ],
                "reset_target_state_receipt_sha256": transition[
                    "reset_target_state_receipt_sha256"
                ],
                "target_encounter_index": transition["target_encounter_index"],
                "target_episode_index": transition["target_episode_index"],
                "target_projection_sha256": projection["payload"]["blob"][
                    "sha256"
                ],
                "update_receipt_sha256": update_receipt["receipt_sha256"],
            }
        )
    if len(resets) != validation.episode_reset_count:
        raise ProtocolError("validated reset count differs")
    body = {
        "episode_reset_count": len(resets),
        "resets": resets,
        "trace_sha256": validation.trace_sha256,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def _online_lineage_ready(
    lineage: dict[str, Any],
    descriptor: tuple[str, str, str | None, str | None],
    *,
    execution_commit: str,
    task_digest: str,
    case: dict[str, Any],
) -> bool:
    expected_keys = {
        "case_id",
        "case_index",
        "condition_id",
        "condition",
        "chain",
        "chain_validation",
        "episode_reset_evidence",
        "initial_projection_sha256",
        "projection_sha256s",
        "worker_response_sha256s",
        "consumer_attempts",
        "operational_failures",
        "operational_complete",
        "terminal_audit_completed",
        "maximum_projection_bytes",
        "maximum_prediction_operations",
        "maximum_update_operations",
        "fresh_processes",
    }
    if type(lineage) is not dict or set(lineage) != expected_keys:
        return False
    chain = lineage["chain"]
    if type(chain) is not dict:
        return False
    try:
        validation = validate_chain(
            chain,
            require_online_admissible=descriptor[0] == "positive-reference",
        )
    except (ReceiptError, KeyError, TypeError, ValueError):
        return False
    expected_condition_id = _descriptor_identity(
        task_digest,
        case["case_id"],
        descriptor,
    )
    lineage_payload = chain["receipt_order"][2]["payload"]
    expected_projection_mode = (
        UPDATE_WITHOUT_PROJECTION
        if descriptor[3] == "update-without-projection"
        else POST_STATE_PROJECTION
    )
    if (
        lineage.get("case_id") != case["case_id"]
        or lineage.get("case_index") != case["case_index"]
        or lineage.get("condition_id") != expected_condition_id
        or lineage_payload["condition_id"] != expected_condition_id
        or lineage_payload["lineage_id"]
        != derive_identity("lineage", case["case_id"], expected_condition_id)
        or lineage_payload["lineage_class"] != _lineage_class(descriptor[0])
        or lineage_payload["projection_mode"] != expected_projection_mode
        or lineage_payload["display_label"]
        != (descriptor[3] or descriptor[1])[:80]
        or lineage_payload["branch_token"] != "genesis"
        or lineage_payload["branch_role"] != "genesis"
        or lineage_payload["encounter_start"] != 0
        or lineage_payload["fork_parent_state_sha256"] is not None
        or lineage_payload["fork_parent_projection_sha256"] is not None
    ):
        return False
    if not _chain_world_from_validation(
        chain,
        validation,
        task_digest=task_digest,
        case=case,
        expected_events=_flatten_case(case),
    ):
        return False
    expected_validation = {
        "authority_eligible": validation.authority_eligible,
        "encounter_count": validation.encounter_count,
        "errors": validation.errors,
        "terminal_audit_receipt_sha256": validation.terminal_audit_receipt_sha256,
        "trace_sha256": validation.trace_sha256,
        "episode_reset_count": validation.episode_reset_count,
    }
    attempts = lineage["consumer_attempts"]
    if type(attempts) is not list or len(attempts) != validation.encounter_count + 1:
        return False
    projections = [chain["receipt_order"][4]["payload"]["blob"]]
    projections.extend(
        chain["receipt_order"][6 + 9 * offset + 7]["payload"]["blob"]
        for offset in range(validation.encounter_count)
    )
    consumers = [
        receipt
        for receipt in chain["receipt_order"]
        if receipt["kind"] == "consumer"
    ]
    if len(consumers) != len(projections):
        return False
    case_receipt = chain["receipt_order"][0]
    lineage_receipt = chain["receipt_order"][2]
    task_digest = case_receipt["payload"]["task_sha256"]
    branch_token = lineage_receipt["payload"]["branch_token"]
    mechanism = _mechanism_for(descriptor)
    if mechanism is None:
        return False
    try:
        runtime_ready = _chain_runtime_identity_from_validation(
            chain,
            validation,
            mechanism=mechanism,
            execution_commit=execution_commit,
        )
    except (
        ReceiptError,
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return False
    if not runtime_ready:
        return False
    expected_attempts: list[dict[str, Any]] = []
    expected_worker_hashes: list[str] = []
    maximum_prediction_operations = 0
    for index, (consumer, projection) in enumerate(zip(consumers, projections)):
        facts = consumer["payload"]["facts"]
        mode = "terminal-audit" if index == validation.encounter_count else "prediction"
        encounter_index = (
            case_receipt["payload"]["horizon"]
            if mode == "terminal-audit"
            else validation.encounter_start + index
        )
        expected_challenges = _consumer_challenge_identities(
            execution_commit=execution_commit,
            task_digest=task_digest,
            case_id=validation.case_id,
            condition_id=lineage_receipt["payload"]["condition_id"],
            branch_token=branch_token,
            encounter_index=encounter_index,
            mode=mode,
        )
        expected_sentinels = expected_challenges["sentinel_challenges"]
        observed_sentinels = facts["forbidden_channel_sentinels"]
        if (
            facts["environment_fingerprint"]
            != _environment_fingerprint(execution_commit)
            or facts["process_challenge_sha256"]
            != expected_challenges["process_challenge_sha256"]
            or facts["workspace_challenge_sha256"]
            != expected_challenges["workspace_challenge_sha256"]
            or [
                {
                    "channel": item["channel"],
                    "sentinel_sha256": item["sentinel_sha256"],
                }
                for item in observed_sentinels
            ]
            != expected_sentinels
            or not consumer_runtime_ready(facts)
            or facts["prediction_status"] not in {"valid", "invalid"}
        ):
            return False
        expected_attempts.append(
            {
                "attempt_status": facts["attempt_status"],
                "descriptor_audit_pass": facts["descriptor_audit_pass"],
                "encounter_index": encounter_index,
                "failure_code": facts["failure_code"],
                "fresh_process_verified": facts["fresh_process_verified"],
                "mode": mode,
                "process_boundary": facts["process_boundary"],
                "process_started": facts["process_started"],
                "response_sha256": facts["response_sha256"],
                "sentinel_absent": all(
                    item["observed"] is False for item in observed_sentinels
                ),
                "workspace_empty_after": (
                    facts["workspace_observed"] is True
                    and facts["workspace_entries_after"] == []
                ),
            }
        )
        expected_worker_hashes.append(facts["response_sha256"])
        if facts["prediction_status"] != "valid":
            continue
        try:
            response_bytes = base64.b64decode(
                facts["response_base64"], validate=True
            )
            response = json.loads(response_bytes)
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        if (
            canonical_json(response) != response_bytes
            or response.get("mechanism_id") != mechanism
            or response.get("descriptor_audit_pass") is not True
            or response.get("state_bytes") != projection["byte_count"]
            or type(response.get("prediction_operations")) is not int
            or response["prediction_operations"] < 0
        ):
            return False
        maximum_prediction_operations = max(
            maximum_prediction_operations,
            response["prediction_operations"],
        )
    if attempts != expected_attempts:
        return False
    prediction_ready, replayed_prediction_operations = _online_prediction_metrics(
        chain,
        descriptor,
        validation.encounter_count,
    )
    if (
        not prediction_ready
        or replayed_prediction_operations != maximum_prediction_operations
    ):
        return False
    update_ready, maximum_update_operations = _online_update_metrics(
        chain,
        descriptor,
        validation.encounter_count,
    )
    if not update_ready:
        return False
    maximum_projection_bytes = max(item["byte_count"] for item in projections)
    causal = _causal_evidence_from_validation(validation)
    try:
        expected_condition = _condition_from_validated_chain(
            chain,
            descriptor,
            validation,
        )
        expected_resets = _episode_resets_from_validation(chain, validation)
    except (KeyError, TypeError, ValueError, ProtocolError):
        return False
    return bool(
        lineage["condition"] == expected_condition
        and lineage["chain_validation"] == expected_validation
        and lineage["episode_reset_evidence"] == expected_resets
        and lineage["initial_projection_sha256"] == projections[0]["sha256"]
        and lineage["projection_sha256s"]
        == causal["consumed_projection_sha256s"]
        and lineage["worker_response_sha256s"]
        == expected_worker_hashes
        and lineage["operational_failures"] == []
        and lineage["operational_complete"] is True
        and lineage["terminal_audit_completed"] is True
        and lineage["maximum_projection_bytes"] == maximum_projection_bytes
        and maximum_projection_bytes <= 2_048
        and lineage["maximum_prediction_operations"]
        == maximum_prediction_operations
        and maximum_prediction_operations <= 131_072
        and lineage["maximum_update_operations"] == maximum_update_operations
        and maximum_update_operations <= 131_072
        and lineage["fresh_processes"] is True
    )


def _rollback_map_from_evidence(
    lineages: list[dict[str, Any]],
    value: object,
    *,
    execution_commit: str,
    task_digest: str,
    case: dict[str, Any],
) -> dict[str, bool] | None:
    expected_keys = {
        "status",
        "failure_code",
        "checkpoint_index",
        "parent_trace_sha256",
        "parent_replay",
        "rewind_branch",
        "alternate_branch",
        "operational_failures",
    }
    if (
        type(value) is not dict
        or set(value) != expected_keys
        or value["status"] != "passed"
        or value["failure_code"] is not None
        or value["checkpoint_index"] != 120
        or value["operational_failures"] != []
    ):
        return None
    descriptor = (
        "positive-reference",
        COMPACT_REFERENCE,
        COMPACT_REFERENCE,
        None,
    )
    parent_result = _lineage_by_descriptor(lineages, 0, descriptor)
    parent = parent_result.get("chain")
    if (
        type(parent) is not dict
        or value["parent_trace_sha256"] != parent.get("trace_sha256")
        or any(
            type(value[name]) is not dict
            for name in ("parent_replay", "rewind_branch", "alternate_branch")
        )
    ):
        return None
    runtime_chains = [
        parent,
        value["parent_replay"],
        value["rewind_branch"],
        value["alternate_branch"],
    ]
    if not all(
        _chain_runtime_identity_ready(
            chain,
            mechanism=COMPACT_REFERENCE,
            execution_commit=execution_commit,
        )
        for chain in runtime_chains
    ):
        return None
    expected_worlds = (
        (parent, _flatten_case(case)),
        (value["parent_replay"], _flatten_case(case)),
        (
            value["rewind_branch"],
            _rollback_suffix_events(
                case,
                start=value["checkpoint_index"] + 1,
                alternate_first_outcome=False,
            ),
        ),
        (
            value["alternate_branch"],
            _rollback_suffix_events(
                case,
                start=value["checkpoint_index"] + 1,
                alternate_first_outcome=True,
            ),
        ),
    )
    if not all(
        _chain_world_ready(
            chain,
            task_digest=task_digest,
            case=case,
            expected_events=events,
        )
        for chain, events in expected_worlds
    ):
        return None
    for chain in runtime_chains:
        validation = validate_chain(chain)
        prediction_ready, _ = _online_prediction_metrics(
            chain,
            descriptor,
            validation.encounter_count,
        )
        update_ready, _ = _online_update_metrics(
            chain,
            descriptor,
            validation.encounter_count,
        )
        if not prediction_ready or not update_ready:
            return None
    try:
        # The frozen parent replay is intentionally byte-identical, including
        # deterministic receipt identities.  Freshness is re-executed and
        # independently observed, but only the two new fork branches must have
        # distinct logical reset identities within this evidence collection.
        validate_chain_collection(
            [parent, value["rewind_branch"], value["alternate_branch"]]
        )
    except ReceiptError:
        return None
    gates = rollback_gates(
        parent,
        value["parent_replay"],
        value["rewind_branch"],
        value["alternate_branch"],
        checkpoint_index=value["checkpoint_index"],
    )
    return gates if set(gates) == set(ROLLBACK_REPLAY_GATES) else None


def _causal_evidence_ready(
    scientific: dict[str, Any],
    *,
    repo: Path,
    task: dict[str, Any],
    deadline: float | None,
) -> bool:
    """Validate raw causal evidence instead of trusting copied summaries."""

    if deadline is not None and time.monotonic() > deadline:
        return False
    try:
        execution_commit = _commit(
            scientific.get("execution_git_commit"),
            "scientific execution",
        )
    except ProtocolError:
        return False
    lineages = scientific.get("lineages")
    if (
        type(lineages) is not list
        or len(lineages) != task["case_count"] * len(CONDITION_INVENTORY)
        or any(type(item) is not dict for item in lineages)
        or lineages
        != sorted(lineages, key=lambda item: (item.get("case_index"), item.get("condition_id")))
    ):
        return False
    task_digest = sha256_bytes(canonical_json(task))
    by_key: dict[tuple[int, str], dict[str, Any]] = {}
    for lineage in lineages:
        key = (lineage.get("case_index"), lineage.get("condition_id"))
        if key in by_key:
            return False
        by_key[key] = lineage

    for case in task["cases"]:
        for descriptor in CONDITION_INVENTORY:
            condition_id = _descriptor_identity(task_digest, case["case_id"], descriptor)
            lineage = by_key.get((case["case_index"], condition_id))
            if (
                lineage is None
                or lineage.get("case_id") != case["case_id"]
                or lineage.get("case_index") != case["case_index"]
                or lineage.get("condition_id") != condition_id
            ):
                return False
            mechanism = _mechanism_for(descriptor)
            if mechanism is None:
                expected = {
                    "case_id": case["case_id"],
                    "case_index": case["case_index"],
                    **_offline_condition(task_digest, case, descriptor),
                }
                if lineage != expected:
                    return False
            elif descriptor[3] != "wrong-lineage-projection":
                if not _online_lineage_ready(
                    lineage,
                    descriptor,
                    execution_commit=execution_commit,
                    task_digest=task_digest,
                    case=case,
                ):
                    return False

    # Reconstruct every wrong-lineage rejection from the two actual sibling
    # chains; a claimed rejection object has no authority on its own.
    for case in task["cases"]:
        for reference in (COMPACT_REFERENCE, LOG_REFERENCE):
            descriptor = (
                "causal-intervention",
                "wrong-lineage-projection",
                reference,
                "wrong-lineage-projection",
            )
            active_descriptor = (
                "positive-reference",
                reference,
                reference,
                None,
            )
            donor_descriptor = (
                "matched-frozen-control",
                f"{reference}--matched-frozen-initial",
                reference,
                None,
            )
            condition_id = _descriptor_identity(task_digest, case["case_id"], descriptor)
            active = by_key[
                (
                    case["case_index"],
                    _descriptor_identity(task_digest, case["case_id"], active_descriptor),
                )
            ]["chain"]
            donor = by_key[
                (
                    case["case_index"],
                    _descriptor_identity(task_digest, case["case_id"], donor_descriptor),
                )
            ]["chain"]
            expected = {
                "case_id": case["case_id"],
                "case_index": case["case_index"],
                **_wrong_lineage_condition(
                    task_digest,
                    case,
                    descriptor,
                    active_chain=active,
                    donor_chain=donor,
                ),
            }
            if by_key[(case["case_index"], condition_id)] != expected:
                return False

    rollback_map = _rollback_map_from_evidence(
        lineages,
        scientific.get("rollback_evidence"),
        execution_commit=execution_commit,
        task_digest=task_digest,
        case=task["cases"][0],
    )
    if rollback_map is None or any(value is not True for value in rollback_map.values()):
        return False
    recomputed_gates = _scientific_gate_evidence(
        repo,
        lineages=lineages,
        rollback_map=rollback_map,
        use_fresh_processes=True,
    )
    if scientific.get("gate_evidence") != recomputed_gates:
        return False
    return deadline is None or time.monotonic() <= deadline


def _scientific_without_journal(scientific: dict[str, Any]) -> dict[str, Any]:
    """Return the journal-free scientific core named by the stage seal."""

    if type(scientific) is not dict or "encounter_journal" not in scientific:
        raise ProtocolError("scientific journal binding is absent")
    core = copy.deepcopy(scientific)
    del core["encounter_journal"]
    return core


def _journal_chain_identity(
    scope: str,
    chain: dict[str, Any],
) -> tuple[str, int, str, str]:
    validation = validate_chain(chain)
    receipts = chain["receipt_order"]
    case_index = receipts[0]["payload"]["case_index"]
    condition_id = receipts[2]["payload"]["condition_id"]
    branch_id = validation.branch_id
    return scope, case_index, condition_id, branch_id


def _encounter_journal_ready(
    scientific: dict[str, Any],
    *,
    repo: Path,
    purpose: str,
    journal_root: Path | None,
    deadline: float | None,
) -> bool:
    """Cross-bind every durable segment to its exact retained scientific chain."""

    if deadline is not None and time.monotonic() > deadline:
        return False
    relative_path = (
        PUBLIC_JOURNAL_RELATIVE_PATH
        if purpose == "design"
        else ANCHOR_JOURNAL_RELATIVE_PATH
    )
    try:
        store = _store(repo)
        if journal_root is None:
            root = _store_path(repo, relative_path)
        else:
            supplied_root = Path(journal_root)
            relative_root = supplied_root.relative_to(store)
            root = _confined_child(
                store,
                relative_root,
                "encounter journal root",
            )
            if root != supplied_root or root.is_symlink():
                return False
        execution_commit = _commit(
            scientific["execution_git_commit"],
            "scientific journal execution",
        )
        core_sha256 = sha256_bytes(
            canonical_json(_scientific_without_journal(scientific))
        )
        stage = read_stage(
            root,
            allow_incomplete=False,
            expected_scientific_sha256=core_sha256,
        )
        if (
            not stage.sealed
            or stage.torn_tail
            or stage.binding != scientific["encounter_journal"]
            or stage.stage_open["purpose"] != purpose
            or stage.stage_open["task_sha256"] != scientific["task_sha256"]
            or stage.stage_open["execution_git_commit"] != execution_commit
            or stage.stage_open["logical_path"] != _logical(relative_path)
            or stage.stage_open["expected_case_count"]
            != scientific["task"]["case_count"]
        ):
            return False

        expected: dict[tuple[str, int, str, str], dict[str, Any]] = {}

        def retain(scope: str, chain: object) -> bool:
            if type(chain) is not dict:
                return False
            key = _journal_chain_identity(scope, chain)
            if key in expected:
                return False
            expected[key] = chain
            return True

        for lineage in scientific["lineages"]:
            condition = lineage["condition"]
            descriptor = (
                condition["role"],
                condition["mechanism_id"],
                condition["reference_id"],
                condition["intervention_id"],
            )
            if (
                _mechanism_for(descriptor) is not None
                and descriptor[3] != "wrong-lineage-projection"
                and not retain("main", lineage.get("chain"))
            ):
                return False

        rollback = scientific["rollback_evidence"]
        for scope, name in (
            ("rollback-parent-replay", "parent_replay"),
            ("rollback-rewind", "rewind_branch"),
            ("rollback-alternate", "alternate_branch"),
        ):
            if not retain(scope, rollback.get(name)):
                return False

        observed: dict[tuple[str, int, str, str], dict[str, Any]] = {}
        for segment in stage.segments:
            if not segment.sealed:
                return False
            chain = reassemble_chain(segment)
            key = _journal_chain_identity(segment.open_record["scope"], chain)
            if key in observed:
                return False
            opened = segment.open_record
            if (
                opened["case_index"] != key[1]
                or opened["condition_id"] != key[2]
                or opened["branch_id"] != key[3]
                or opened["execution_git_commit"] != execution_commit
            ):
                return False
            observed[key] = chain
        if set(observed) != set(expected):
            return False
        if any(
            canonical_json(observed[key]) != canonical_json(expected[key])
            for key in expected
        ):
            return False
    except (
        JournalError,
        ProtocolError,
        ReceiptError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
    ):
        return False
    return deadline is None or time.monotonic() <= deadline


def _scientific_ready_except_reconstruction(
    scientific: dict[str, Any],
    *,
    purpose: str,
    repo: Path | None = None,
    deadline: float | None = None,
    journal_root: Path | None = None,
) -> bool:
    """Return whether reconstruction is the sole unsatisfied trace gate."""

    expected_scientific_keys = {
        "schema_version",
        "experiment_id",
        "purpose",
        "execution_git_commit",
        "task",
        "task_sha256",
        "candidate_outputs",
        "actor_turns",
        "actor_tool_calls",
        "hosted_model_calls",
        "lineages",
        "rollback_evidence",
        "operational_evidence",
        "gate_evidence",
        "scorer_bundle",
        "primary_score",
        "shadow_score",
        "scorer_independence",
        "verification",
        "within_wall_budget",
        "calibration_pass",
        "disposition",
        "authorized_actor_candidate_count",
        "claim_limit",
        "encounter_journal",
    }
    repo = (repo or Path.cwd()).resolve()
    try:
        if (
            type(scientific) is not dict
            or set(scientific) != expected_scientific_keys
            or purpose not in {"design", "anchor"}
            or scientific["schema_version"] != 1
            or scientific["experiment_id"] != EXPERIMENT_ID
            or scientific["purpose"] != purpose
            or scientific["execution_git_commit"]
            != _commit(scientific["execution_git_commit"], "scientific execution")
            or scientific["candidate_outputs"] is not False
            or scientific["actor_turns"] != 0
            or scientific["actor_tool_calls"] != 0
            or scientific["hosted_model_calls"] != 0
            or scientific["calibration_pass"] is not False
            or scientific["disposition"] != "invalidated"
            or scientific["authorized_actor_candidate_count"] != 0
            or scientific["within_wall_budget"] is not True
            or scientific["claim_limit"] != CLAIM_LIMIT
        ):
            return False

        task = scientific["task"]
        validate_task(task)
        if (
            task["purpose"] != purpose
            or scientific["task_sha256"] != sha256_bytes(canonical_json(task))
        ):
            return False
        if not _encounter_journal_ready(
            scientific,
            repo=repo,
            purpose=purpose,
            journal_root=journal_root,
            deadline=deadline,
        ):
            return False

        bundle = scientific["scorer_bundle"]
        primary = scientific["primary_score"]
        shadow = scientific["shadow_score"]
        independence = scientific["scorer_independence"]
        if not all(type(item) is dict for item in (bundle, primary, shadow, independence)):
            return False
        recomputed_primary = score_bundle(copy.deepcopy(bundle))
        recomputed_shadow = score_bundle_shadow(copy.deepcopy(bundle))
        if (
            canonical_json(primary) != canonical_json(recomputed_primary)
            or canonical_json(shadow) != canonical_json(recomputed_shadow)
            or canonical_json(primary) != canonical_json(shadow)
        ):
            return False

        execution = bundle.get("execution_gates")
        if type(execution) is not dict or set(execution) != set(EXECUTION_GATES):
            return False
        if execution.get("clean_private_reconstruction") is not False:
            return False
        if any(
            execution.get(name) is not True
            for name in EXECUTION_GATES
            if name != "clean_private_reconstruction"
        ):
            return False
        if (
            bundle.get("purpose") != purpose
            or bundle.get("case_count") != task["case_count"]
        ):
            return False

        expected_promotion_gates = {
            "every_stream",
            "paired_control_wins",
            "familywise_sign_bound",
            "adaptive_comparators_reported",
            "authority_defects_rejected",
            "causal_path",
            "rollback_replay",
            "execution",
        }
        for score in (primary, shadow):
            gates = score.get("promotion_gates")
            if type(gates) is not dict or set(gates) != expected_promotion_gates:
                return False
            if gates.get("execution") is not False or any(
                gates.get(name) is not True
                for name in expected_promotion_gates
                if name != "execution"
            ):
                return False
            if (
                score.get("trace_gate_pass") is not False
                or score.get("anchor_promotion_pass") is not False
                or score.get("authorized_actor_candidate_count") != 0
            ):
                return False

        if set(independence) != {
            "task_level",
            "trace_level",
            "metamorphic_pass",
            "primary_shadow_agreement",
            "primary_sha256",
            "shadow_sha256",
        }:
            return False
        task_level = independence["task_level"]
        trace_level = independence["trace_level"]
        expected_task_level = _task_metamorphic_gates(task)
        expected_trace_level: dict[str, dict[str, Any]] = {}
        trace_variants = metamorphic_variants(bundle)
        for name, variant in trace_variants.items():
            variant_primary = score_bundle(copy.deepcopy(variant))
            variant_shadow = score_bundle_shadow(copy.deepcopy(variant))
            expected_trace_level[name] = {
                "pass": (
                    canonical_json(variant_primary) == canonical_json(primary)
                    and canonical_json(variant_shadow) == canonical_json(shadow)
                    and canonical_json(variant_primary)
                    == canonical_json(variant_shadow)
                ),
                "primary_sha256": sha256_bytes(canonical_json(variant_primary)),
                "shadow_sha256": sha256_bytes(canonical_json(variant_shadow)),
            }
        if (
            type(task_level) is not dict
            or task_level != expected_task_level
            or any(value is not True for value in expected_task_level.values())
            or type(trace_level) is not dict
            or trace_level != expected_trace_level
            or set(trace_level) != set(trace_variants)
            or independence["metamorphic_pass"] is not True
            or independence["primary_shadow_agreement"] is not True
            or independence["primary_sha256"]
            != sha256_bytes(canonical_json(primary))
            or independence["shadow_sha256"]
            != sha256_bytes(canonical_json(shadow))
        ):
            return False
        for result in trace_level.values():
            if (
                type(result) is not dict
                or set(result) != {"pass", "primary_sha256", "shadow_sha256"}
                or result["pass"] is not True
                or _sha(result["primary_sha256"], "metamorphic primary")
                != result["primary_sha256"]
                or _sha(result["shadow_sha256"], "metamorphic shadow")
                != result["shadow_sha256"]
            ):
                return False

        verification = scientific["verification"]
        if (
            type(verification) is not dict
            or set(verification) != {"tests", "audit"}
            or verification["tests"] != {"status": "passed", "returncode": 0}
            or verification["audit"] != {"status": "passed", "returncode": 0}
        ):
            return False

        lineages = scientific["lineages"]
        if (
            type(lineages) is not list
            or len(lineages) != task["case_count"] * len(CONDITION_INVENTORY)
            or any(type(item) is not dict for item in lineages)
        ):
            return False
        scorer_cases = bundle.get("cases")
        if type(scorer_cases) is not list or len(scorer_cases) != task["case_count"]:
            return False
        for scorer_case, task_case in zip(scorer_cases, task["cases"], strict=True):
            task_events = _flatten_case(task_case)
            if (
                scorer_case.get("case_id") != task_case["case_id"]
                or scorer_case.get("case_index") != task_case["case_index"]
                or scorer_case.get("episodes")
                != [
                    {
                        "episode_index": episode["episode_index"],
                        "dwell": episode["dwell"],
                    }
                    for episode in task_case["episodes"]
                ]
                or scorer_case.get("world_query_ids")
                != [event["public_query"]["query_id"] for event in task_events]
                or scorer_case.get("world_outcomes")
                != [event["outcome"] for event in task_events]
            ):
                return False
        conditions_by_case = {
            case["case_index"]: case["conditions"] for case in scorer_cases
        }
        lineage_keys: set[tuple[int, str]] = set()
        for lineage in lineages:
            key = (lineage.get("case_index"), lineage.get("condition_id"))
            if (
                type(key[0]) is not int
                or type(key[1]) is not str
                or key in lineage_keys
                or key[0] not in conditions_by_case
                or key[1] not in conditions_by_case[key[0]]
                or lineage.get("condition") != conditions_by_case[key[0]][key[1]]
            ):
                return False
            lineage_keys.add(key)

        gate_evidence = scientific["gate_evidence"]
        expected_base_execution_gates = {
            "online_reference_authority",
            "control_authority",
            "adaptive_comparator_authority",
            "state_projection_budgets",
            "operation_budgets",
            "fresh_reset_receipts",
            "candidate_free",
        }
        base_execution_gates = gate_evidence.get("base_execution_gates")
        if (
            type(gate_evidence) is not dict
            or gate_evidence.get("authority_defect_rejections")
            != bundle.get("authority_defect_rejections")
            or gate_evidence.get("causal_path_gates")
            != bundle.get("causal_path_gates")
            or gate_evidence.get("rollback_replay_gates")
            != bundle.get("rollback_replay_gates")
            or type(base_execution_gates) is not dict
            or set(base_execution_gates) != expected_base_execution_gates
            or any(
                base_execution_gates[name] is not execution[name]
                for name in expected_base_execution_gates
            )
            or type(scientific["rollback_evidence"]) is not dict
        ):
            return False
        operational = scientific["operational_evidence"]
        if (
            type(operational) is not dict
            or set(operational)
            != {
                "schema_version",
                "prediction_timeout_count",
                "prediction_missing_count",
                "condition_failure_count",
                "terminal_audit_failures",
                "rollback_operational_failures",
                "verification_failures",
                "stage_deadline_exhausted",
                "globally_invalidated",
            }
            or operational
            != {
                "schema_version": 1,
                "prediction_timeout_count": 0,
                "prediction_missing_count": 0,
                "condition_failure_count": 0,
                "terminal_audit_failures": [],
                "rollback_operational_failures": [],
                "verification_failures": [],
                "stage_deadline_exhausted": False,
                "globally_invalidated": False,
            }
            or operational
            != _operational_evidence(
                lineages=lineages,
                rollback_evidence=scientific["rollback_evidence"],
                tests=verification["tests"],
                audit=verification["audit"],
                deadline_exhausted=False,
            )
        ):
            return False
        if not _causal_evidence_ready(
            scientific,
            repo=repo,
            task=task,
            deadline=deadline,
        ):
            return False
    except (KeyError, TypeError, ValueError):
        return False
    return deadline is None or time.monotonic() <= deadline


def _public_causal_summary(scientific: dict[str, Any]) -> dict[str, int]:
    """Return a bounded, independently checkable summary of the public run."""

    lineages = scientific["lineages"]
    return {
        "case_count": scientific["task"]["case_count"],
        "condition_count_per_case": len(CONDITION_INVENTORY),
        "lineage_count": len(lineages),
        "positive_lineage_count": sum(
            item["condition"]["role"] == "positive-reference" for item in lineages
        ),
        "wrong_lineage_rejection_count": sum(
            item["condition"]["intervention_id"] == "wrong-lineage-projection"
            for item in lineages
        ),
        "episode_reset_lineage_count": sum(
            item["condition"]["intervention_id"] == "cross-episode-state-reset"
            for item in lineages
        ),
        "episode_reset_transition_count": sum(
            item.get("episode_reset_evidence", {}).get("episode_reset_count", 0)
            for item in lineages
        ),
        "authority_defect_rejection_count": sum(
            scientific["scorer_bundle"]["authority_defect_rejections"].values()
        ),
        "causal_path_gate_count": sum(
            scientific["scorer_bundle"]["causal_path_gates"].values()
        ),
        "rollback_replay_gate_count": sum(
            scientific["scorer_bundle"]["rollback_replay_gates"].values()
        ),
    }


def _expected_public_causal_summary() -> dict[str, int]:
    case_count = build_design_task(PUBLIC_CAUSAL_DESIGN_INDEX)["case_count"]
    return {
        "case_count": case_count,
        "condition_count_per_case": len(CONDITION_INVENTORY),
        "lineage_count": case_count * len(CONDITION_INVENTORY),
        "positive_lineage_count": case_count * 2,
        "wrong_lineage_rejection_count": case_count * 2,
        "episode_reset_lineage_count": case_count * 2,
        "episode_reset_transition_count": case_count * 2 * (len(EPISODE_SCHEDULE) - 1),
        "authority_defect_rejection_count": len(AUTHORITY_DEFECTS),
        "causal_path_gate_count": len(CAUSAL_PATH_GATES),
        "rollback_replay_gate_count": len(ROLLBACK_REPLAY_GATES),
    }


def _validate_public_checkpoint_receipt(
    value: object,
    *,
    implementation: str,
) -> dict[str, Any]:
    receipt = _exact(
        value,
        {
            "schema_version",
            "experiment_id",
            "implementation_git_commit",
            "design_seed_index",
            "design_task_sha256",
            "public_vector_bytes",
            "public_vector_row_count",
            "public_vector_sha256",
            "public_calibration_sha256",
            "primary_score_sha256",
            "shadow_score_sha256",
            "encounter_journal",
            "causal_summary",
            "tests_status",
            "audit_status",
            "within_wall_budget",
            "pass",
            "receipt_sha256",
        },
        "public checkpoint receipt",
    )
    body = {key: item for key, item in receipt.items() if key != "receipt_sha256"}
    journal = receipt.get("encounter_journal")
    journal_keys = {
        "completed_encounter_count",
        "execution_git_commit",
        "journal_format",
        "journal_sha256",
        "logical_path",
        "purpose",
        "receipt_count",
        "schema_version",
        "scope_counts",
        "scientific_sha256",
        "sealed",
        "segment_count",
        "segment_index_sha256",
        "stage_open_sha256",
        "task_sha256",
    }
    scope_counts_ready = bool(
        type(journal) is dict
        and type(journal.get("scope_counts")) is dict
        and set(journal["scope_counts"]) == set(SCOPES)
        and all(
            type(journal["scope_counts"][scope]) is dict
            and set(journal["scope_counts"][scope])
            == {"encounters", "receipts", "segments"}
            and all(
                type(journal["scope_counts"][scope][name]) is int
                and journal["scope_counts"][scope][name] >= 0
                for name in ("encounters", "receipts", "segments")
            )
            for scope in SCOPES
        )
    )
    if (
        receipt["schema_version"] != 1
        or receipt["experiment_id"] != EXPERIMENT_ID
        or receipt["implementation_git_commit"]
        != _commit(implementation, "implementation")
        or receipt["design_seed_index"] != PUBLIC_CAUSAL_DESIGN_INDEX
        or receipt["design_task_sha256"]
        != sha256_bytes(canonical_json(build_design_task(PUBLIC_CAUSAL_DESIGN_INDEX)))
        or receipt["public_vector_bytes"] != EXPECTED_VECTOR_BYTES
        or receipt["public_vector_row_count"] != EXPECTED_ROW_COUNT
        or receipt["public_vector_sha256"] != EXPECTED_VECTOR_SHA256
        or receipt["primary_score_sha256"] != EXPECTED_PUBLIC_SCORE_SHA256
        or receipt["shadow_score_sha256"] != EXPECTED_PUBLIC_SCORE_SHA256
        or type(journal) is not dict
        or set(journal) != journal_keys
        or journal["schema_version"] != 1
        or journal["journal_format"] != JOURNAL_FORMAT
        or not scope_counts_ready
        or journal["execution_git_commit"] != implementation
        or journal["logical_path"] != _logical(PUBLIC_JOURNAL_RELATIVE_PATH)
        or journal["purpose"] != "design"
        or journal["sealed"] is not True
        or journal["task_sha256"] != receipt["design_task_sha256"]
        or type(journal["completed_encounter_count"]) is not int
        or journal["completed_encounter_count"] <= 0
        or type(journal["receipt_count"]) is not int
        or journal["receipt_count"] <= 0
        or type(journal["segment_count"]) is not int
        or journal["segment_count"] <= 0
        or receipt["causal_summary"] != _expected_public_causal_summary()
        or receipt["tests_status"] != "passed"
        or receipt["audit_status"] != "passed"
        or receipt["within_wall_budget"] is not True
        or receipt["pass"] is not True
        or receipt["receipt_sha256"] != sha256_bytes(canonical_json(body))
    ):
        raise ProtocolError("public checkpoint receipt differs")
    for name in (
        "design_task_sha256",
        "public_vector_sha256",
        "public_calibration_sha256",
        "primary_score_sha256",
        "shadow_score_sha256",
        "receipt_sha256",
    ):
        _sha(receipt[name], f"public checkpoint {name}")
    for name in (
        "journal_sha256",
        "scientific_sha256",
        "segment_index_sha256",
        "stage_open_sha256",
    ):
        _sha(journal[name], f"public checkpoint journal {name}")
    if receipt["primary_score_sha256"] != receipt["shadow_score_sha256"]:
        raise ProtocolError("public checkpoint scorers disagree")
    return receipt


def _assert_public_design_bounded(
    repo: Path,
    *,
    deadline: float,
) -> bytes:
    command = (
        "import sys; "
        "from open_trajectory_harness.ot0077_design_probe import "
        "assert_public_design; "
        "sys.stdout.buffer.write(assert_public_design())"
    )
    process = _communicate_bounded(
        [sys.executable, "-S", "-c", command],
        repo=repo,
        deadline=deadline,
        environment=_worker_environment(repo),
    )
    if process["status"] == "timeout":
        raise ProtocolError("public design checkpoint timed out")
    if (
        process["status"] != "completed"
        or process["returncode"] != 0
        or process["stderr"]
    ):
        raise ProtocolError("public design checkpoint process failed")
    payload = process["stdout"]
    if (
        len(payload) != EXPECTED_VECTOR_BYTES
        or sha256_bytes(payload) != EXPECTED_VECTOR_SHA256
    ):
        raise ProtocolError("public design checkpoint bytes differ")
    return payload


def assert_public_checkpoint(
    repo: Path,
    *,
    implementation: str,
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    """Run the complete public oracle before any private destination is written."""

    repo = repo.resolve()
    implementation = _commit(implementation, "implementation")
    deadline = time.monotonic() + CALIBRATION_SECONDS
    task = build_design_task(PUBLIC_CAUSAL_DESIGN_INDEX)
    journal_root = _store_path(repo, PUBLIC_JOURNAL_RELATIVE_PATH)
    failed_journal = _store_path(repo, FAILED_PUBLIC_JOURNAL_RELATIVE_PATH)
    public_failure = _store_path(repo, PUBLIC_FAILURE_RELATIVE_PATH)
    if journal_root.exists() or failed_journal.exists() or public_failure.exists():
        raise ProtocolError("public checkpoint journal or failure authority exists")
    try:
        payload = _assert_public_design_bounded(repo, deadline=deadline)
        scientific = _run_calibration_bounded(
            repo,
            task,
            execution_commit=implementation,
            clean_private_reconstruction=False,
            run_verification_commands=True,
            deadline=deadline,
            journal_root=journal_root,
            journal_logical_path=_logical(PUBLIC_JOURNAL_RELATIVE_PATH),
        )
        if not _scientific_ready_except_reconstruction(
            scientific,
            purpose="design",
            repo=repo,
            deadline=deadline,
            journal_root=journal_root,
        ):
            raise ProtocolError(
                "public causal checkpoint did not pass every applicable gate"
            )
        verification = scientific["verification"]
        body = {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "implementation_git_commit": implementation,
            "design_seed_index": PUBLIC_CAUSAL_DESIGN_INDEX,
            "design_task_sha256": sha256_bytes(canonical_json(task)),
            "public_vector_bytes": len(payload),
            "public_vector_row_count": EXPECTED_ROW_COUNT,
            "public_vector_sha256": sha256_bytes(payload),
            "public_calibration_sha256": sha256_bytes(canonical_json(scientific)),
            "primary_score_sha256": sha256_bytes(
                canonical_json(scientific["primary_score"])
            ),
            "shadow_score_sha256": sha256_bytes(
                canonical_json(scientific["shadow_score"])
            ),
            "encounter_journal": copy.deepcopy(
                scientific["encounter_journal"]
            ),
            "causal_summary": _public_causal_summary(scientific),
            "tests_status": verification["tests"]["status"],
            "audit_status": verification["audit"]["status"],
            "within_wall_budget": scientific["within_wall_budget"],
            "pass": True,
        }
        receipt = _validate_public_checkpoint_receipt(
            {**body, "receipt_sha256": sha256_bytes(canonical_json(body))},
            implementation=implementation,
        )
        if time.monotonic() > deadline:
            raise ProtocolError("public checkpoint exceeded its wall budget")
        return receipt
    except Exception as error:
        try:
            journal_summary = _quarantine_encounter_journal(
                journal_root,
                failed_journal,
            )
            _write_public_checkpoint_failure(
                repo,
                code="public_checkpoint_failed",
                journal_summary=journal_summary,
            )
        except Exception as preservation_error:
            raise RuntimeError(
                "public checkpoint failure evidence could not be preserved"
            ) from preservation_error
        raise error


def build_raw(
    *,
    implementation_commit: str,
    execution_commit: str,
    scientific: dict[str, Any],
    repo: Path | None = None,
    deadline: float | None = None,
) -> dict[str, Any]:
    checked_execution = _commit(execution_commit, "execution")
    if scientific.get("execution_git_commit") != checked_execution:
        raise ProtocolError("scientific execution differs from the raw envelope")
    ready = _calibration_ready_except_reconstruction(
        scientific,
        repo=repo,
        deadline=deadline,
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": DEFAULT_RUN_ID,
        "implementation_git_commit": _commit(
            implementation_commit, "implementation"
        ),
        "execution_git_commit": checked_execution,
        "evidence_class": "private-prepublication" if ready else "exploratory-only",
        "summary": _prepublication_summary(scientific, ready=ready),
        "scientific": scientific,
    }


def _prepublication_summary(
    scientific: dict[str, Any],
    *,
    ready: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "candidate_outputs": False,
        "actor_turns": 0,
        "hosted_model_calls": 0,
        "calibration_pass": False,
        "promotion_ready_except_reconstruction": ready,
        "disposition": "pending-reconstruction" if ready else "invalidated",
        "authorized_actor_candidate_count": 0,
        "primary_score_sha256": sha256_bytes(
            canonical_json(scientific["primary_score"])
        ),
        "shadow_score_sha256": sha256_bytes(
            canonical_json(scientific["shadow_score"])
        ),
        "scientific_payload_sha256": sha256_bytes(canonical_json(scientific)),
        "claim_limit": CLAIM_LIMIT,
    }


def _calibration_ready_except_reconstruction(
    scientific: dict[str, Any],
    *,
    repo: Path | None = None,
    deadline: float | None = None,
) -> bool:
    return _scientific_ready_except_reconstruction(
        scientific,
        purpose="anchor",
        repo=repo,
        deadline=deadline,
    )


def _validate_prepublication_raw(
    raw: object,
    *,
    encoded_raw: bytes,
    repo: Path | None = None,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Validate the complete immutable raw envelope and its exact bytes."""

    if type(raw) is not dict or set(raw) != {
        "schema_version",
        "experiment_id",
        "run_id",
        "implementation_git_commit",
        "execution_git_commit",
        "evidence_class",
        "summary",
        "scientific",
    }:
        raise ProtocolError("prepublication raw schema differs")
    decoded = decode_raw(encoded_raw, verify_canonical_compression=False)
    if decoded != raw:
        raise ProtocolError("encoded prepublication raw does not equal the supplied raw")
    scientific = raw["scientific"]
    if not _calibration_ready_except_reconstruction(
        scientific,
        repo=repo,
        deadline=deadline,
    ):
        raise ProtocolError("prepublication calibration is not promotion-ready")
    if (
        raw["schema_version"] != 1
        or raw["experiment_id"] != EXPERIMENT_ID
        or raw["run_id"] != DEFAULT_RUN_ID
        or raw["evidence_class"] != "private-prepublication"
        or raw["implementation_git_commit"]
        != _commit(raw["implementation_git_commit"], "implementation")
        or raw["execution_git_commit"]
        != _commit(raw["execution_git_commit"], "execution")
        or scientific.get("execution_git_commit")
        != raw["execution_git_commit"]
        or scientific.get("task", {}).get("implementation_git_commit")
        != raw["implementation_git_commit"]
        or raw["summary"] != _prepublication_summary(scientific, ready=True)
    ):
        raise ProtocolError("prepublication raw identity differs")
    return raw


def finalize_after_reconstruction(
    raw: dict[str, Any],
    reconstruction: dict[str, Any],
    *,
    encoded_raw: bytes,
    raw_manifest: dict[str, Any],
    post_record_verification: dict[str, Any],
    repo: Path | None = None,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Issue the promotion decision after, and only after, exact comparison.

    The prepublication raw bytes are never rewritten.  This decision binds the
    observed reconstruction identity, flips only the frozen reconstruction
    gate in a copy of the completed scorer bundle, and reruns both scorers.
    """

    checked_raw = _validate_prepublication_raw(
        raw,
        encoded_raw=encoded_raw,
        repo=repo,
        deadline=deadline,
    )
    if repo is not None:
        _validate_historical_execution_provenance(repo.resolve(), checked_raw)
    if (
        type(reconstruction) is not dict
        or set(reconstruction) != {"pass", "status", "bytes", "sha256"}
        or reconstruction.get("pass") is not True
        or reconstruction.get("status") != "passed"
        or reconstruction.get("bytes") != len(encoded_raw)
        or reconstruction.get("sha256") != sha256_bytes(encoded_raw)
    ):
        raise ProtocolError("exact private reconstruction was not observed")
    if (
        type(raw_manifest) is not dict
        or set(raw_manifest)
        != {
            "path",
            "manifest_bytes",
            "manifest_sha256",
            "artifact_bytes",
            "artifact_sha256",
            "evidence_class",
            "environment_git_commit",
            "environment_git_dirty",
            "readback_status",
        }
        or raw_manifest["path"]
        != f"evidence/manifests/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json"
        or raw_manifest["artifact_bytes"] != len(encoded_raw)
        or raw_manifest["artifact_sha256"] != sha256_bytes(encoded_raw)
        or raw_manifest["evidence_class"] != "private-reproducible"
        or raw_manifest["environment_git_commit"]
        != checked_raw["execution_git_commit"]
        or raw_manifest["environment_git_dirty"] is not False
        or raw_manifest["readback_status"]
        != "manifest and evidence bytes verified"
        or type(raw_manifest["manifest_bytes"]) is not int
        or raw_manifest["manifest_bytes"] <= 0
        or _sha(raw_manifest["manifest_sha256"], "raw manifest")
        != raw_manifest["manifest_sha256"]
    ):
        raise ProtocolError("raw manifest identity or readback differs")
    if (
        type(post_record_verification) is not dict
        or set(post_record_verification)
        != {"tests", "audit", "raw_manifest_readback", "within_wall_budget"}
        or post_record_verification["tests"]
        != {"status": "passed", "returncode": 0}
        or post_record_verification["audit"]
        != {"status": "passed", "returncode": 0}
        or post_record_verification["raw_manifest_readback"]
        != {
            "pass": True,
            "status": "manifest and evidence bytes verified",
        }
        or post_record_verification["within_wall_budget"] is not True
    ):
        raise ProtocolError("post-record verification did not pass")

    bundle = copy.deepcopy(checked_raw["scientific"]["scorer_bundle"])
    if bundle["execution_gates"]["clean_private_reconstruction"] is not False:
        raise ProtocolError("prepublication reconstruction gate is not false")
    bundle["execution_gates"]["clean_private_reconstruction"] = True
    primary = score_bundle(bundle)
    shadow = score_bundle_shadow(bundle)
    if (
        canonical_json(primary) != canonical_json(shadow)
        or primary.get("anchor_promotion_pass") is not True
        or shadow.get("anchor_promotion_pass") is not True
        or primary.get("authorized_actor_candidate_count") != 1
        or shadow.get("authorized_actor_candidate_count") != 1
    ):
        raise ProtocolError("post-reconstruction scorers did not promote")
    if deadline is not None and time.monotonic() > deadline:
        raise ProtocolError("promotion finalization exceeded its wall budget")
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": DEFAULT_RUN_ID,
        "implementation_git_commit": checked_raw["implementation_git_commit"],
        "execution_git_commit": checked_raw["execution_git_commit"],
        "evidence_class": "private-reproducible",
        "candidate_outputs": False,
        "actor_turns": 0,
        "hosted_model_calls": 0,
        "calibration_pass": True,
        "disposition": "promoted",
        "authorized_actor_candidate_count": 1,
        "prepublication_raw_bytes": len(encoded_raw),
        "prepublication_raw_sha256": sha256_bytes(encoded_raw),
        "prepublication_scientific_sha256": sha256_bytes(
            canonical_json(checked_raw["scientific"])
        ),
        "reconstruction": copy.deepcopy(reconstruction),
        "raw_manifest": copy.deepcopy(raw_manifest),
        "post_record_verification": copy.deepcopy(post_record_verification),
        "primary_score_sha256": sha256_bytes(canonical_json(primary)),
        "shadow_score_sha256": sha256_bytes(canonical_json(shadow)),
        "claim_limit": CLAIM_LIMIT,
    }
    return {**body, "decision_sha256": sha256_bytes(canonical_json(body))}


def encode_raw(raw: dict[str, Any]) -> bytes:
    encoded = canonical_json(raw)
    if len(encoded) > MAX_UNCOMPRESSED_RAW_BYTES:
        raise RuntimeError("raw artifact exceeds the decoded implementation bound")
    compressed = zlib.compress(encoded, level=9)
    if len(compressed) > MAX_RAW_BYTES:
        raise RuntimeError("compressed raw artifact exceeds the implementation bound")
    return compressed


def decode_raw(
    encoded: bytes,
    *,
    verify_canonical_compression: bool = True,
) -> dict[str, Any]:
    if len(encoded) > MAX_RAW_BYTES:
        raise ProtocolError("compressed raw artifact exceeds the implementation bound")
    try:
        raw_bytes = _bounded_zlib_decompress(encoded)
        value = json.loads(raw_bytes)
    except (ProtocolError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("compressed raw artifact is invalid") from error
    if type(value) is not dict or canonical_json(value) != raw_bytes:
        raise ProtocolError("raw artifact is not canonical JSON before compression")
    if verify_canonical_compression and zlib.compress(raw_bytes, level=9) != encoded:
        raise ProtocolError("raw artifact compression is not canonical")
    return value


def write_sealed_raw(path: Path, raw: dict[str, Any]) -> None:
    _write_sealed_bytes(path, encode_raw(raw))


def _materialize_raw_transaction(
    repo: Path,
    raw: dict[str, Any],
    *,
    deadline: float,
    expected_store_identity: dict[str, int] | None = None,
) -> bytes:
    """Encode and atomically install raw through one pinned evidence root."""

    evidence_root = _store(repo)
    if expected_store_identity is None:
        # Authoritative callers pass the identity captured before the worker
        # starts.  This creation path exists only for isolated direct use.
        evidence_root.mkdir(parents=True, exist_ok=True)
        store_identity = _authority_root_identity(
            evidence_root,
            "evidence store",
        )
    else:
        store_identity = _validated_authority_identity(
            expected_store_identity,
            "evidence store",
        )
    store_descriptor = _open_authority_root(
        evidence_root,
        store_identity,
        "evidence store",
    )
    target_parent: int | None = None
    staging_parent: int | None = None
    staging_descriptor: int | None = None
    installed = False
    committed = False
    target_name = ""
    staging_name = ""
    staging_identity: dict[str, int] | None = None

    def require_absent(parent: int, name: str) -> None:
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise ProtocolError("raw transaction destination exists")

    def rebind_transaction(*, expect_staging: bool) -> None:
        assert target_parent is not None and staging_parent is not None
        rebound_target, rebound_target_name = _open_relative_parent(
            store_descriptor,
            RAW_RELATIVE_PATH,
            create=False,
            label="raw authority",
        )
        rebound_staging: int | None = None
        try:
            rebound_staging, rebound_staging_name = _open_relative_parent(
                store_descriptor,
                RAW_STAGING_RELATIVE_PATH,
                create=False,
                label="raw staging",
            )
            if (
                rebound_target_name != target_name
                or rebound_staging_name != staging_name
                or _authority_identity_from_stat(os.fstat(rebound_target))
                != _authority_identity_from_stat(os.fstat(target_parent))
                or _authority_identity_from_stat(os.fstat(rebound_staging))
                != _authority_identity_from_stat(os.fstat(staging_parent))
            ):
                raise ProtocolError("raw transaction parent identity changed")
            observed_target = os.stat(
                target_name,
                dir_fd=target_parent,
                follow_symlinks=False,
            )
            if (
                staging_identity is None
                or _authority_identity_from_stat(observed_target)
                != staging_identity
            ):
                raise ProtocolError("raw authority identity changed")
            assert staging_descriptor is not None
            os.fsync(staging_descriptor)
            try:
                observed_staging = os.stat(
                    staging_name,
                    dir_fd=staging_parent,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                observed_staging = None
            if expect_staging:
                if (
                    observed_staging is None
                    or staging_identity is None
                    or _authority_identity_from_stat(observed_staging)
                    != staging_identity
                ):
                    raise ProtocolError("raw staging identity changed")
            elif observed_staging is not None:
                raise ProtocolError("raw staging authority survived commit")
        finally:
            if rebound_staging is not None:
                os.close(rebound_staging)
            os.close(rebound_target)
        rebound_store = _open_authority_root(
            evidence_root,
            store_identity,
            "evidence store",
        )
        os.close(rebound_store)

    try:
        encoded = encode_raw(raw)
        if time.monotonic() > deadline:
            raise ProtocolError("raw encoding exceeded the calibration deadline")
        target_parent, target_name = _open_relative_parent(
            store_descriptor,
            RAW_RELATIVE_PATH,
            create=True,
            label="raw authority",
        )
        staging_parent, staging_name = _open_relative_parent(
            store_descriptor,
            RAW_STAGING_RELATIVE_PATH,
            create=True,
            label="raw staging",
        )
        require_absent(target_parent, target_name)
        require_absent(staging_parent, staging_name)
        try:
            staging_descriptor = os.open(
                staging_name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                0o600,
                dir_fd=staging_parent,
            )
        except OSError as error:
            raise ProtocolError("raw staging cannot be created") from error
        _write_all_descriptor(staging_descriptor, encoded)
        os.fsync(staging_descriptor)
        os.fchmod(staging_descriptor, 0o400)
        staging_identity = _authority_identity_from_stat(
            os.fstat(staging_descriptor)
        )
        os.fsync(staging_parent)
        if time.monotonic() > deadline:
            raise ProtocolError(
                "raw staging write exceeded the calibration deadline"
            )
        try:
            os.link(
                staging_name,
                target_name,
                src_dir_fd=staging_parent,
                dst_dir_fd=target_parent,
                follow_symlinks=False,
            )
        except FileExistsError as error:
            raise ProtocolError(
                "raw authority destination raced materialization"
            ) from error
        installed = True
        os.fsync(target_parent)
        rebind_transaction(expect_staging=True)
        if time.monotonic() > deadline:
            raise ProtocolError("raw installation exceeded the calibration deadline")
        os.unlink(staging_name, dir_fd=staging_parent)
        os.fsync(staging_parent)
        # The target is now the sole durable copy.  From this point onward it
        # must survive any failed rebind/deadline check so the outer failure
        # transaction can preserve it as negative evidence.
        committed = True
        rebind_transaction(expect_staging=False)
        if time.monotonic() > deadline:
            raise ProtocolError("raw transaction exceeded the calibration deadline")
        return encoded
    finally:
        if staging_descriptor is not None:
            os.close(staging_descriptor)
        cleanup_error: Exception | None = None
        if installed and not committed and target_parent is not None:
            try:
                os.unlink(target_name, dir_fd=target_parent)
                os.fsync(target_parent)
            except FileNotFoundError:
                pass
            except Exception as error:
                cleanup_error = error
        if staging_parent is not None:
            os.close(staging_parent)
        if target_parent is not None:
            os.close(target_parent)
        os.close(store_descriptor)
        if cleanup_error is not None:
            raise RuntimeError("failed raw authority could not be removed") from cleanup_error


def read_sealed_raw(path: Path) -> tuple[dict[str, Any], bytes]:
    encoded = _read_regular_file_bounded(path, MAX_RAW_BYTES)
    return decode_raw(encoded), encoded


def _execute_locked_raw(
    repo: Path,
    execution: str,
    lock: dict[str, Any],
    task: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    store_identity: dict[str, int] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + CALIBRATION_SECONDS
    return _run_calibration_bounded(
        repo,
        task,
        execution_commit=execution,
        clean_private_reconstruction=False,
        run_verification_commands=True,
        deadline=deadline,
        journal_root=_store_path(repo, ANCHOR_JOURNAL_RELATIVE_PATH),
        journal_logical_path=_logical(ANCHOR_JOURNAL_RELATIVE_PATH),
        materialize_raw=True,
        implementation_commit=lock["implementation_git_commit"],
        expected_store_identity=store_identity,
    )


def reconstruct(repo: Path) -> tuple[Path, dict[str, Any]]:
    repo = repo.resolve()
    if _recover_incomplete_startup(repo):
        raise RuntimeError("interrupted reconstruction transaction was quarantined")
    contract = output_contract(repo, allow_manifest=True)
    execution, lock, task, acceptance = locked_context(
        repo,
        allow_regeneration=True,
    )
    try:
        raw = _execute_locked_raw(
            repo,
            execution,
            lock,
            task,
            acceptance,
            store_identity=_contract_authority_identity(
                contract,
                "store",
                "evidence store",
            ),
        )
    except Exception as error:
        _preserve_prepublication_failure(
            contract,
            code="reconstruction_calibration_process_failed",
        )
        raise RuntimeError("reconstruction OT-0077 calibration failed") from error
    return contract["raw"], raw["summary"]


def _failure(
    contract: dict[str, Any],
    *,
    code: str,
    authoritative_raw: Path,
    journal_summary: dict[str, Any] | None = None,
    raw_transaction: dict[str, Any] | None = None,
    reconstruction_transaction: dict[str, Any] | None = None,
) -> None:
    retained_raw = bool(
        authoritative_raw.exists()
        or (
            type(raw_transaction) is dict
            and type(raw_transaction.get("raw")) is dict
            and raw_transaction["raw"].get("status") == "retained"
            and raw_transaction["raw"].get("quarantined") is True
        )
    )
    encoded = canonical_json({
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "run_id": DEFAULT_RUN_ID,
            "operational_failure": code,
            "public_manifest_retained": False,
            "authoritative_raw_retained": retained_raw,
            "encounter_journal": copy.deepcopy(journal_summary),
            "raw_transaction": copy.deepcopy(raw_transaction),
            "reconstruction_transaction": copy.deepcopy(
                reconstruction_transaction
            ),
            "authorized_actor_candidate_count": 0,
        })
    _write_contract_store_sealed_bytes(
        contract,
        "failure",
        encoded,
        limit=MAX_COMPLETION_BYTES,
    )


def _preserve_prepublication_failure(
    contract: dict[str, Any],
    *,
    code: str,
    quarantine_reconstruction: bool = False,
) -> None:
    """Attempt every independent failure-preservation surface exactly once."""

    errors: list[Exception] = []
    reconstruction_transaction: dict[str, Any] | None = None
    raw_transaction: dict[str, Any] | None = None
    journal_summary: dict[str, Any] | None = None
    if quarantine_reconstruction:
        try:
            reconstruction_transaction = _quarantine_reconstruction_root(
                contract["reconstruction_root"],
                contract["failed_reconstruction_root"],
                expected_store_identity=_contract_authority_identity(
                    contract,
                    "store",
                    "evidence store",
                ),
            )
        except Exception as error:
            errors.append(error)
    try:
        raw_transaction = _quarantine_raw_transaction(contract)
    except Exception as error:
        errors.append(error)
    try:
        journal_summary = _quarantine_encounter_journal(
            contract["journal"],
            contract["failed_journal"],
            expected_store_identity=_contract_authority_identity(
                contract,
                "store",
                "evidence store",
            ),
        )
    except Exception as error:
        errors.append(error)
    try:
        if not _failure_receipt_ready(contract, expected_code=code):
            _failure(
                contract,
                code=code,
                authoritative_raw=contract["raw"],
                journal_summary=journal_summary,
                raw_transaction=raw_transaction,
                reconstruction_transaction=reconstruction_transaction,
            )
    except Exception as error:
        errors.append(error)
    if errors:
        raise RuntimeError(
            "prepublication failure evidence was not fully preserved"
        ) from ExceptionGroup("failure preservation errors", errors)


def _remove_directory_contents_at(
    descriptor: int,
    *,
    remaining_budget: list[int],
) -> None:
    """Remove a bounded directory tree without following any link."""

    for name in os.listdir(descriptor):
        remaining_budget[0] -= 1
        if remaining_budget[0] < 0:
            raise ProtocolError("fresh-root cleanup inventory exceeds its bound")
        observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISDIR(observed.st_mode):
            child = _open_directory_at(
                descriptor,
                name,
                create=False,
                label="fresh-root cleanup",
            )
            try:
                if _authority_identity_from_stat(os.fstat(child)) != (
                    _authority_identity_from_stat(observed)
                ):
                    raise ProtocolError("fresh-root cleanup child changed")
                _remove_directory_contents_at(
                    child,
                    remaining_budget=remaining_budget,
                )
            finally:
                os.close(child)
            os.rmdir(name, dir_fd=descriptor)
        else:
            os.unlink(name, dir_fd=descriptor)
    os.fsync(descriptor)


def verify_fresh_root(
    repo: Path,
    *,
    implementation: str,
    seed_bytes: bytes,
    authoritative_raw: Path,
    expected_store_identity: dict[str, int] | None = None,
) -> dict[str, Any]:
    repo = repo.resolve()
    _commit(implementation, "reconstruction implementation")
    if type(seed_bytes) is not bytes or len(seed_bytes) != 32:
        raise ProtocolError("reconstruction seed identity differs")
    deadline = time.monotonic() + RECONSTRUCTION_SECONDS
    store = _store(repo)
    identity_was_supplied = expected_store_identity is not None
    if not identity_was_supplied and not store.exists() and not store.is_symlink():
        store.mkdir(parents=True, exist_ok=False)
        _fsync_directory(store.parent)
    store_identity = (
        _authority_root_identity(store, "evidence store")
        if expected_store_identity is None
        else _validated_authority_identity(
            expected_store_identity,
            "evidence store",
        )
    )
    store_descriptor = _open_authority_root(
        store,
        store_identity,
        "evidence store",
    )
    try:
        try:
            authoritative_relative = authoritative_raw.relative_to(store)
        except ValueError:
            if identity_was_supplied:
                raise ProtocolError("authoritative raw leaves the evidence store")
            authoritative_bytes = _read_regular_file_bounded(
                authoritative_raw,
                MAX_RAW_BYTES,
            )
        else:
            authoritative_descriptor = _open_relative_regular(
                store_descriptor,
                authoritative_relative,
                limit=MAX_RAW_BYTES,
                label="authoritative reconstruction raw",
            )
            try:
                authoritative_bytes = _read_regular_descriptor_bounded(
                    authoritative_descriptor,
                    limit=MAX_RAW_BYTES,
                    label="authoritative reconstruction raw",
                )
            finally:
                os.close(authoritative_descriptor)
    except Exception:
        os.close(store_descriptor)
        raise
    if time.monotonic() > deadline:
        os.close(store_descriptor)
        return {"pass": False, "status": "reconstruction_timeout"}
    root_parent: int | None = None
    failed_parent: int | None = None
    root_descriptor: int | None = None
    reconstructed_descriptor: int | None = None
    root_name = ""
    failed_name = ""
    root_identity: dict[str, int] | None = None
    chain_descriptors: list[int] = []
    chain_pins: list[tuple[int, str, int, dict[str, int]]] = []
    try:
        initial_store_generation = _stat_generation(os.fstat(store_descriptor))
    except Exception:
        os.close(store_descriptor)
        raise
    chain_generations: dict[int, tuple[int, ...]] = {
        store_descriptor: initial_store_generation
    }

    def open_pinned_parent(relative: Path, label: str) -> tuple[int, str]:
        parts = _relative_authority_parts(relative, label)
        current = store_descriptor
        for component in parts[:-1]:
            child = _open_directory_at(
                current,
                component,
                create=True,
                label=label,
            )
            try:
                identity = _authority_identity_from_stat(os.fstat(child))
                observed = os.stat(
                    component,
                    dir_fd=current,
                    follow_symlinks=False,
                )
                if _authority_identity_from_stat(observed) != identity:
                    raise ProtocolError(f"{label} directory changed while pinning")
            except Exception:
                os.close(child)
                raise
            chain_descriptors.append(child)
            chain_pins.append((current, component, child, identity))
            current = child
        return current, parts[-1]

    def refresh_chain_generations() -> None:
        chain_generations.clear()
        chain_generations[store_descriptor] = _stat_generation(
            os.fstat(store_descriptor)
        )
        for _parent, _name, child, _identity in chain_pins:
            chain_generations[child] = _stat_generation(os.fstat(child))

    def rebind_chains() -> None:
        for parent, name, child, identity in chain_pins:
            if (
                _authority_identity_from_stat(os.fstat(child)) != identity
                or _authority_identity_from_stat(
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                )
                != identity
            ):
                raise ProtocolError("fresh-root reconstruction chain changed")
        for descriptor, expected in chain_generations.items():
            if _stat_generation(os.fstat(descriptor)) != expected:
                raise ProtocolError(
                    "fresh-root reconstruction parent generation changed"
                )

    def rebind_root() -> None:
        assert root_parent is not None and root_identity is not None
        rebind_chains()
        rebound = _open_directory_at(
            root_parent,
            root_name,
            create=False,
            label="fresh-root reconstruction",
        )
        try:
            if _authority_identity_from_stat(os.fstat(rebound)) != root_identity:
                raise ProtocolError("fresh-root reconstruction identity changed")
        finally:
            os.close(rebound)
        rebound_store = _open_authority_root(
            store,
            store_identity,
            "evidence store",
        )
        os.close(rebound_store)

    def rebind_store() -> None:
        rebind_chains()
        rebound_store = _open_authority_root(
            store,
            store_identity,
            "evidence store",
        )
        os.close(rebound_store)

    def quarantine_pinned() -> None:
        assert root_parent is not None and failed_parent is not None
        assert root_identity is not None
        rebind_root()
        try:
            os.stat(failed_name, dir_fd=failed_parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProtocolError("fresh-root reconstruction quarantine exists")
        os.rename(
            root_name,
            failed_name,
            src_dir_fd=root_parent,
            dst_dir_fd=failed_parent,
        )
        os.fsync(root_parent)
        os.fsync(failed_parent)
        refresh_chain_generations()
        retained = os.stat(
            failed_name,
            dir_fd=failed_parent,
            follow_symlinks=False,
        )
        if _authority_identity_from_stat(retained) != root_identity:
            raise ProtocolError("fresh-root quarantine identity differs")
        rebind_store()
        final_retained = os.stat(
            failed_name,
            dir_fd=failed_parent,
            follow_symlinks=False,
        )
        try:
            os.stat(root_name, dir_fd=root_parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProtocolError("fresh-root reconstruction survived quarantine")
        if _authority_identity_from_stat(final_retained) != root_identity:
            raise ProtocolError("fresh-root quarantine identity differs")

    def fail(status: str) -> dict[str, Any]:
        quarantine_pinned()
        return {"pass": False, "status": status}

    try:
        root_parent, root_name = open_pinned_parent(
            RECONSTRUCTION_ROOT_RELATIVE_PATH,
            "fresh-root reconstruction",
        )
        failed_parent, failed_name = open_pinned_parent(
            FAILED_RECONSTRUCTION_ROOT_RELATIVE_PATH,
            "fresh-root reconstruction quarantine",
        )
        for parent, name in (
            (root_parent, root_name),
            (failed_parent, failed_name),
        ):
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ProtocolError("fresh-root reconstruction transaction exists")
        os.mkdir(root_name, mode=0o700, dir_fd=root_parent)
        os.fsync(root_parent)
        root_descriptor = _open_directory_at(
            root_parent,
            root_name,
            create=False,
            label="fresh-root reconstruction",
        )
        root_identity = _authority_identity_from_stat(os.fstat(root_descriptor))
        refresh_chain_generations()
        rebind_root()
        _write_sealed_bytes_at(
            root_descriptor,
            SEED_RELATIVE_PATH,
            seed_bytes,
            limit=PRIVATE_SEED_BYTES,
            label="reconstruction seed",
        )
        root = store / RECONSTRUCTION_ROOT_RELATIVE_PATH
        environment = child_environment(repo)
        environment["OT_EVIDENCE_ROOT"] = str(root)
        process = _communicate_bounded(
            [
                sys.executable,
                "-m",
                "open_trajectory_harness.ot0077",
                "--reconstruct-only",
            ],
            repo=repo,
            deadline=deadline,
            environment=environment,
        )
        if process["status"] == "timeout":
            return fail("reconstruction_timeout")
        if (
            process["status"] != "completed"
            or process["returncode"] != 0
            or process["stderr"]
        ):
            return fail("reconstruction_failed")
        rebind_root()
        try:
            reconstructed_descriptor = _open_relative_regular(
                root_descriptor,
                RAW_RELATIVE_PATH,
                limit=MAX_RAW_BYTES,
                label="reconstructed raw",
            )
            reconstructed_bytes = _read_regular_descriptor_bounded(
                reconstructed_descriptor,
                limit=MAX_RAW_BYTES,
                label="reconstructed raw",
            )
        except (OSError, ProtocolError):
            return fail("reconstruction_failed")
        rebind_root()
        if time.monotonic() > deadline:
            return fail("reconstruction_timeout")
        exact = reconstructed_bytes == authoritative_bytes
        reconstructed_length = len(reconstructed_bytes)
        reconstructed_sha256 = sha256_bytes(reconstructed_bytes)
        if time.monotonic() > deadline:
            return fail("reconstruction_timeout")
        if not exact:
            quarantine_pinned()
            return {
                "pass": False,
                "status": "raw_mismatch",
                "bytes": reconstructed_length,
                "sha256": reconstructed_sha256,
            }
        rebind_root()
        _remove_directory_contents_at(
            root_descriptor,
            remaining_budget=[1_000_000],
        )
        rebind_root()
        os.rmdir(root_name, dir_fd=root_parent)
        os.fsync(root_parent)
        refresh_chain_generations()
        try:
            os.stat(root_name, dir_fd=root_parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProtocolError("fresh-root cleanup left active authority")
        rebind_store()
        try:
            os.stat(root_name, dir_fd=root_parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProtocolError("fresh-root cleanup left active authority")
        if time.monotonic() > deadline:
            return {"pass": False, "status": "reconstruction_timeout"}
        return {
            "pass": True,
            "status": "passed",
            "bytes": reconstructed_length,
            "sha256": reconstructed_sha256,
        }
    finally:
        if reconstructed_descriptor is not None:
            os.close(reconstructed_descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)
        for descriptor in reversed(chain_descriptors):
            os.close(descriptor)
        os.close(store_descriptor)


def _secure_record_artifact(
    repo: Path,
    *,
    repo_descriptor: int,
    store_descriptor: int,
    input_relative_path: Path,
    artifact_id: str,
    kind: str,
    artifact_sha256: str,
    artifact_bytes: int,
    recipe: str | None,
    input_manifests: list[str],
    limitations: list[str],
) -> Path:
    validate_identifier("artifact_id", artifact_id)
    validate_identifier("kind", kind)
    _sha(artifact_sha256, "publication artifact")
    if (
        type(artifact_bytes) is not int
        or artifact_bytes < 0
        or artifact_bytes > MAX_RAW_BYTES
    ):
        raise ProtocolError("publication artifact byte identity differs")
    with _open_relative_regular_temporarily_readable(
        store_descriptor,
        input_relative_path,
        limit=MAX_RAW_BYTES,
        label="publication input",
    ) as input_descriptor:
        observed_sha256, observed_bytes = _hash_regular_descriptor(
            input_descriptor,
            limit=MAX_RAW_BYTES,
            label="publication input",
        )
        if (
            observed_sha256 != artifact_sha256
            or observed_bytes != artifact_bytes
        ):
            raise ProtocolError("publication input identity differs")
        _secure_object_install(
            store_descriptor,
            input_descriptor,
            artifact_sha256=artifact_sha256,
            artifact_bytes=artifact_bytes,
        )

    media_type = (
        mimetypes.guess_type(input_relative_path.name)[0]
        or "application/octet-stream"
    )
    manifest = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "artifact_id": artifact_id,
        "kind": kind,
        "media_type": media_type,
        "sha256": artifact_sha256,
        "bytes": artifact_bytes,
        "evidence_class": "private-reproducible",
        "availability": {"local_object": True},
        "reconstruction": {
            "recipe": recipe,
            "expected_output": f"artifact:{artifact_id}",
        },
        "environment": safe_environment(repo),
        "input_manifests": input_manifests,
        "limitations": limitations,
    }
    validate_manifest(manifest)
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    return _secure_manifest_install(
        repo_descriptor,
        artifact_id=artifact_id,
        encoded=encoded,
    )


def _manifest_binding(
    repo: Path,
    *,
    repo_descriptor: int,
    store_descriptor: int,
    path: Path,
    artifact_id: str,
    kind: str,
    artifact_sha256: str,
    artifact_bytes: int,
    execution_commit: str,
    store: Path,
    recipe: str | None,
    input_manifests: list[str],
    limitations: list[str],
    environment_dirty: bool,
) -> dict[str, Any]:
    expected_path = (
        repo
        / "evidence"
        / "manifests"
        / EXPERIMENT_ID
        / f"{artifact_id}.json"
    )
    if path != expected_path:
        raise ProtocolError("recorded manifest path identity differs")
    manifest_relative = path.relative_to(repo)
    manifest_descriptor = _open_relative_regular(
        repo_descriptor,
        manifest_relative,
        limit=MAX_MANIFEST_BYTES,
        label="public manifest",
    )
    try:
        manifest_bytes = _read_regular_descriptor_bounded(
            manifest_descriptor,
            limit=MAX_MANIFEST_BYTES,
            label="public manifest",
        )
    finally:
        os.close(manifest_descriptor)
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("recorded manifest is invalid") from error
    if type(manifest) is not dict:
        raise ProtocolError("recorded manifest root differs")
    validate_manifest(manifest)
    if manifest_bytes != (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode():
        raise ProtocolError("recorded manifest encoding differs")
    object_relative = (
        Path("objects")
        / "sha256"
        / manifest["sha256"][:2]
        / manifest["sha256"]
    )
    object_descriptor = _open_relative_regular(
        store_descriptor,
        object_relative,
        limit=MAX_RAW_BYTES,
        label="content-addressed object",
    )
    try:
        object_sha256, object_bytes = _hash_regular_descriptor(
            object_descriptor,
            limit=MAX_RAW_BYTES,
            label="content-addressed object",
        )
    finally:
        os.close(object_descriptor)
    git_identity = manifest.get("environment", {}).get("git", {})
    expected_input = (
        RAW_RELATIVE_PATH
        if kind == "e14-anchor-prepublication-raw"
        else PROMOTION_RELATIVE_PATH
        if kind == "e14-promotion-decision"
        else None
    )
    if expected_input is None:
        raise ProtocolError("recorded manifest kind has no media identity")
    recorded_environment = manifest.get("environment")
    environment_keys = {
        "os_family",
        "architecture",
        "python_implementation",
        "python_version",
        "git",
    }
    environment_shape_ready = bool(
        type(recorded_environment) is dict
        and set(recorded_environment) == environment_keys
        and all(
            type(recorded_environment[key]) is str
            and 0 < len(recorded_environment[key]) <= 256
            for key in environment_keys - {"git"}
        )
        and recorded_environment["git"]
        == {"commit": execution_commit, "dirty": environment_dirty}
    )
    expected_media_type = (
        mimetypes.guess_type(expected_input.name)[0]
        or "application/octet-stream"
    )
    if (
        object_sha256 != manifest["sha256"]
        or object_bytes != manifest["bytes"]
        or manifest.get("experiment_id") != EXPERIMENT_ID
        or manifest.get("artifact_id") != artifact_id
        or manifest.get("kind") != kind
        or manifest.get("sha256") != artifact_sha256
        or manifest.get("bytes") != artifact_bytes
        or manifest.get("evidence_class") != "private-reproducible"
        or manifest.get("media_type") != expected_media_type
        or manifest.get("availability") != {"local_object": True}
        or not environment_shape_ready
        or manifest.get("reconstruction")
        != {
            "recipe": recipe,
            "expected_output": f"artifact:{artifact_id}",
        }
        or manifest.get("input_manifests") != input_manifests
        or manifest.get("limitations") != limitations
        or git_identity.get("commit") != execution_commit
        or git_identity.get("dirty") is not environment_dirty
    ):
        raise ProtocolError("recorded manifest identity or artifact readback differs")
    return {
        "path": str(path.relative_to(repo)),
        "manifest_bytes": len(manifest_bytes),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "artifact_bytes": artifact_bytes,
        "artifact_sha256": artifact_sha256,
        "evidence_class": manifest["evidence_class"],
        "environment_git_commit": git_identity["commit"],
        "environment_git_dirty": git_identity["dirty"],
        "readback_status": "manifest and evidence bytes verified",
    }


def _evidence_worker_entry() -> int:
    """Record or bind one artifact behind a killable publication boundary."""

    repo_descriptor: int | None = None
    store_descriptor: int | None = None
    journal_descriptor: int | None = None
    try:
        payload = sys.stdin.buffer.read(1_048_577)
        if len(payload) > 1_048_576:
            raise ProtocolError("evidence worker envelope exceeds its bound")
        envelope = json.loads(payload)
        if canonical_json(envelope) != payload or type(envelope) is not dict:
            raise ProtocolError("evidence worker envelope is not canonical")
        mode = envelope.get("mode")
        repo = Path.cwd().resolve()
        if mode == "record":
            _exact(
                envelope,
                {
                    "mode",
                    "input_relative_path",
                    "store_path",
                    "repo_identity",
                    "store_identity",
                    "artifact_id",
                    "kind",
                    "artifact_sha256",
                    "artifact_bytes",
                    "recipe",
                    "limitations",
                    "input_manifests",
                },
                "record worker envelope",
            )
            store_path = Path(envelope["store_path"])
            if not store_path.is_absolute():
                raise ProtocolError("record worker store path differs")
            repo_descriptor = _open_authority_root(
                Path("."),
                envelope["repo_identity"],
                "repository",
            )
            store_descriptor = _open_authority_root(
                store_path,
                envelope["store_identity"],
                "evidence store",
            )
            manifest = _secure_record_artifact(
                repo,
                repo_descriptor=repo_descriptor,
                store_descriptor=store_descriptor,
                input_relative_path=Path(envelope["input_relative_path"]),
                artifact_id=envelope["artifact_id"],
                kind=envelope["kind"],
                artifact_sha256=envelope["artifact_sha256"],
                artifact_bytes=envelope["artifact_bytes"],
                recipe=envelope["recipe"],
                limitations=envelope["limitations"],
                input_manifests=envelope["input_manifests"],
            )
            result: dict[str, Any] = {"manifest_path": str(manifest)}
        elif mode == "bind":
            _exact(
                envelope,
                {
                    "mode",
                    "path",
                    "store_path",
                    "repo_identity",
                    "store_identity",
                    "artifact_id",
                    "kind",
                    "artifact_sha256",
                    "artifact_bytes",
                    "execution_commit",
                    "recipe",
                    "input_manifests",
                    "limitations",
                    "environment_dirty",
                },
                "binding worker envelope",
            )
            store_path = Path(envelope["store_path"])
            if not store_path.is_absolute():
                raise ProtocolError("binding worker store path differs")
            repo_descriptor = _open_authority_root(
                Path("."),
                envelope["repo_identity"],
                "repository",
            )
            store_descriptor = _open_authority_root(
                store_path,
                envelope["store_identity"],
                "evidence store",
            )
            result = _manifest_binding(
                repo,
                repo_descriptor=repo_descriptor,
                store_descriptor=store_descriptor,
                path=repo / envelope["path"],
                artifact_id=envelope["artifact_id"],
                kind=envelope["kind"],
                artifact_sha256=envelope["artifact_sha256"],
                artifact_bytes=envelope["artifact_bytes"],
                execution_commit=envelope["execution_commit"],
                store=Path(envelope["store_path"]),
                recipe=envelope["recipe"],
                input_manifests=envelope["input_manifests"],
                limitations=envelope["limitations"],
                environment_dirty=envelope["environment_dirty"],
            )
        elif mode == "journal-bind":
            _exact(
                envelope,
                {
                    "mode",
                    "store_path",
                    "repo_identity",
                    "store_identity",
                    "journal_relative_path",
                    "expected_scientific_sha256",
                },
                "journal binding worker envelope",
            )
            store_path = Path(envelope["store_path"])
            if not store_path.is_absolute():
                raise ProtocolError("journal binding store path differs")
            repo_descriptor = _open_authority_root(
                Path("."),
                envelope["repo_identity"],
                "repository",
            )
            store_descriptor = _open_authority_root(
                store_path,
                envelope["store_identity"],
                "evidence store",
            )
            journal_parts = _relative_authority_parts(
                Path(envelope["journal_relative_path"]),
                "encounter journal",
            )
            journal_descriptor = _open_directory_chain(
                store_descriptor,
                journal_parts,
                create=False,
                label="encounter journal",
            )
            os.fchdir(journal_descriptor)
            stage = read_stage(
                Path("."),
                expected_scientific_sha256=envelope[
                    "expected_scientific_sha256"
                ],
            )
            result = {
                "binding": stage.binding,
                "sealed": stage.sealed,
                "torn_tail": stage.torn_tail,
            }
        else:
            raise ProtocolError("evidence worker mode is unavailable")
        sys.stdout.buffer.write(canonical_json(result))
        return 0
    except (OSError, TypeError, ValueError):
        sys.stderr.write("OT-0077 evidence worker failed\n")
        return 2
    finally:
        if journal_descriptor is not None:
            os.close(journal_descriptor)
        if store_descriptor is not None:
            os.close(store_descriptor)
        if repo_descriptor is not None:
            os.close(repo_descriptor)


def _evidence_operation_bounded(
    repo: Path,
    envelope: dict[str, Any],
    *,
    deadline: float,
) -> dict[str, Any]:
    command = (
        "import sys; from open_trajectory_harness.ot0077 import "
        "_evidence_worker_entry; raise SystemExit(_evidence_worker_entry())"
    )
    process = _communicate_bounded(
        [sys.executable, "-S", "-c", command],
        repo=repo,
        deadline=deadline,
        input_bytes=canonical_json(envelope),
        environment=_worker_environment(repo),
    )
    if process["status"] == "timeout":
        raise ProtocolError("publication evidence operation timed out")
    if (
        process["status"] != "completed"
        or process["returncode"] != 0
        or process["stderr"]
    ):
        raise ProtocolError("publication evidence operation failed")
    try:
        result = json.loads(process["stdout"])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("publication evidence response is invalid") from error
    if type(result) is not dict or canonical_json(result) != process["stdout"]:
        raise ProtocolError("publication evidence response is not canonical")
    if time.monotonic() > deadline:
        raise ProtocolError("publication evidence operation exceeded its deadline")
    return result


def _record_artifact_bounded(
    repo: Path,
    *,
    input_path: Path,
    store: Path,
    artifact_id: str,
    kind: str,
    artifact_sha256: str | None = None,
    artifact_bytes: int | None = None,
    recipe: str | None,
    limitations: list[str],
    input_manifests: list[str],
    deadline: float,
    repo_identity: dict[str, int] | None = None,
    store_identity: dict[str, int] | None = None,
) -> Path:
    repo = repo.resolve()
    if not store.is_absolute() or not input_path.is_absolute():
        raise ProtocolError("publication authority paths must be absolute")
    if repo_identity is None:
        repo_identity = _authority_root_identity(repo, "repository")
    else:
        repo_identity = _validated_authority_identity(
            repo_identity,
            "repository",
        )
        descriptor = _open_authority_root(repo, repo_identity, "repository")
        os.close(descriptor)
    if store_identity is None:
        store_identity = _authority_root_identity(store, "evidence store")
    else:
        store_identity = _validated_authority_identity(
            store_identity,
            "evidence store",
        )
        descriptor = _open_authority_root(
            store,
            store_identity,
            "evidence store",
        )
        os.close(descriptor)
    try:
        input_relative = input_path.relative_to(store)
    except ValueError as error:
        raise ProtocolError("publication input leaves the evidence store") from error
    _relative_authority_parts(input_relative, "publication input")
    if (artifact_sha256 is None) != (artifact_bytes is None):
        raise ProtocolError("publication input expected identity is incomplete")
    if artifact_sha256 is None:
        store_descriptor = _open_authority_root(
            store,
            store_identity,
            "evidence store",
        )
        try:
            with _open_relative_regular_temporarily_readable(
                store_descriptor,
                input_relative,
                limit=MAX_RAW_BYTES,
                label="publication input",
            ) as input_descriptor:
                artifact_sha256, artifact_bytes = _hash_regular_descriptor(
                    input_descriptor,
                    limit=MAX_RAW_BYTES,
                    label="publication input",
                )
        finally:
            os.close(store_descriptor)
    assert artifact_sha256 is not None and artifact_bytes is not None
    _sha(artifact_sha256, "publication artifact")
    if type(artifact_bytes) is not int or not 0 <= artifact_bytes <= MAX_RAW_BYTES:
        raise ProtocolError("publication artifact byte identity differs")
    result = _evidence_operation_bounded(
        repo,
        {
            "mode": "record",
            "input_relative_path": input_relative.as_posix(),
            "store_path": str(store),
            "repo_identity": repo_identity,
            "store_identity": store_identity,
            "artifact_id": artifact_id,
            "kind": kind,
            "artifact_sha256": artifact_sha256,
            "artifact_bytes": artifact_bytes,
            "recipe": recipe,
            "limitations": limitations,
            "input_manifests": input_manifests,
        },
        deadline=deadline,
    )
    if set(result) != {"manifest_path"} or type(result["manifest_path"]) is not str:
        raise ProtocolError("recorded manifest path response differs")
    expected = Path("evidence") / "manifests" / EXPERIMENT_ID / f"{artifact_id}.json"
    if Path(result["manifest_path"]) != expected:
        raise ProtocolError("recorded manifest path differs")
    return repo / expected


def _manifest_binding_bounded(
    repo: Path,
    *,
    path: Path,
    artifact_id: str,
    kind: str,
    artifact_sha256: str,
    artifact_bytes: int,
    execution_commit: str,
    store: Path,
    recipe: str | None,
    input_manifests: list[str],
    limitations: list[str],
    environment_dirty: bool,
    deadline: float,
    repo_identity: dict[str, int] | None = None,
    store_identity: dict[str, int] | None = None,
) -> dict[str, Any]:
    repo = repo.resolve()
    if not store.is_absolute():
        raise ProtocolError("binding evidence store path must be absolute")
    if repo_identity is None:
        repo_identity = _authority_root_identity(repo, "repository")
    else:
        repo_identity = _validated_authority_identity(
            repo_identity,
            "repository",
        )
        descriptor = _open_authority_root(repo, repo_identity, "repository")
        os.close(descriptor)
    if store_identity is None:
        store_identity = _authority_root_identity(store, "evidence store")
    else:
        store_identity = _validated_authority_identity(
            store_identity,
            "evidence store",
        )
        descriptor = _open_authority_root(
            store,
            store_identity,
            "evidence store",
        )
        os.close(descriptor)
    result = _evidence_operation_bounded(
        repo,
        {
            "mode": "bind",
            "path": str(path.relative_to(repo)),
            "store_path": str(store),
            "repo_identity": repo_identity,
            "store_identity": store_identity,
            "artifact_id": artifact_id,
            "kind": kind,
            "artifact_sha256": artifact_sha256,
            "artifact_bytes": artifact_bytes,
            "execution_commit": execution_commit,
            "recipe": recipe,
            "input_manifests": input_manifests,
            "limitations": limitations,
            "environment_dirty": environment_dirty,
        },
        deadline=deadline,
    )
    expected_path = str(path.relative_to(repo))
    if (
        set(result)
        != {
            "path",
            "manifest_bytes",
            "manifest_sha256",
            "artifact_bytes",
            "artifact_sha256",
            "evidence_class",
            "environment_git_commit",
            "environment_git_dirty",
            "readback_status",
        }
        or result.get("path") != expected_path
        or type(result.get("manifest_bytes")) is not int
        or result["manifest_bytes"] <= 0
        or type(result.get("manifest_sha256")) is not str
        or _sha(result["manifest_sha256"], "bounded manifest")
        != result["manifest_sha256"]
        or result.get("artifact_bytes") != artifact_bytes
        or result.get("artifact_sha256") != artifact_sha256
        or result.get("evidence_class") != "private-reproducible"
        or result.get("environment_git_commit") != execution_commit
        or result.get("environment_git_dirty") is not environment_dirty
        or result.get("readback_status")
        != "manifest and evidence bytes verified"
    ):
        raise ProtocolError("bounded manifest binding response differs")
    return result


def _journal_stage_binding_bounded(
    repo: Path,
    *,
    store: Path,
    journal: Path,
    expected_scientific_sha256: str,
    repo_identity: dict[str, int],
    store_identity: dict[str, int],
    deadline: float,
) -> dict[str, Any]:
    repo = repo.resolve()
    _sha(expected_scientific_sha256, "journal scientific payload")
    repo_identity = _validated_authority_identity(
        repo_identity,
        "repository",
    )
    store_identity = _validated_authority_identity(
        store_identity,
        "evidence store",
    )
    try:
        journal_relative = journal.relative_to(store)
    except ValueError as error:
        raise ProtocolError("encounter journal leaves the evidence store") from error
    _relative_authority_parts(journal_relative, "encounter journal")
    result = _evidence_operation_bounded(
        repo,
        {
            "mode": "journal-bind",
            "store_path": str(store),
            "repo_identity": repo_identity,
            "store_identity": store_identity,
            "journal_relative_path": journal_relative.as_posix(),
            "expected_scientific_sha256": expected_scientific_sha256,
        },
        deadline=deadline,
    )
    if (
        set(result) != {"binding", "sealed", "torn_tail"}
        or result.get("sealed") is not True
        or result.get("torn_tail") is not False
        or type(result.get("binding")) is not dict
        or result["binding"].get("scientific_sha256")
        != expected_scientific_sha256
    ):
        raise ProtocolError("bounded encounter journal binding differs")
    return result


def _post_raw_record_verification(
    repo: Path,
    *,
    manifest: Path,
    store: Path,
    expected_binding: dict[str, Any],
    artifact_sha256: str,
    artifact_bytes: int,
    execution_commit: str,
    recipe: str | None,
    input_manifests: list[str],
    limitations: list[str],
    deadline: float,
    repo_identity: dict[str, int] | None = None,
    store_identity: dict[str, int] | None = None,
) -> dict[str, Any]:
    tests = _bounded_command(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        repo,
        deadline,
        "post_record_tests",
    )
    audit = _bounded_command(
        [sys.executable, "-m", "open_trajectory_evidence", "audit"],
        repo,
        deadline,
        "post_record_audit",
    )
    try:
        observed_binding = _manifest_binding_bounded(
            repo,
            path=manifest,
            artifact_id=DEFAULT_RUN_ID,
            kind="e14-anchor-prepublication-raw",
            artifact_sha256=artifact_sha256,
            artifact_bytes=artifact_bytes,
            execution_commit=execution_commit,
            store=store,
            recipe=recipe,
            input_manifests=input_manifests,
            limitations=limitations,
            environment_dirty=False,
            deadline=deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
        verified = observed_binding == expected_binding
        status = (
            "manifest and evidence bytes verified"
            if verified
            else "exact manifest binding differs"
        )
    except (OSError, RuntimeError, ValueError):
        verified, status = False, "exact manifest readback failed"
    return {
        "tests": tests,
        "audit": audit,
        "raw_manifest_readback": {"pass": verified, "status": status},
        "within_wall_budget": time.monotonic() <= deadline,
    }


def _publication_verification_passed(value: dict[str, Any]) -> bool:
    return (
        value.get("tests") == {"status": "passed", "returncode": 0}
        and value.get("audit") == {"status": "passed", "returncode": 0}
        and value.get("raw_manifest_readback")
        == {
            "pass": True,
            "status": "manifest and evidence bytes verified",
        }
        and value.get("within_wall_budget") is True
    )


def _publication_completion(
    contract: dict[str, Path],
    *,
    execution_commit: str,
    encoded_raw: bytes,
    raw_manifest: dict[str, Any],
    encoded_promotion: bytes,
    promotion_manifest: dict[str, Any],
    journal_binding: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": DEFAULT_RUN_ID,
        "execution_git_commit": _commit(execution_commit, "completion execution"),
        "raw_bytes": len(encoded_raw),
        "raw_sha256": sha256_bytes(encoded_raw),
        "raw_manifest_bytes": raw_manifest["manifest_bytes"],
        "raw_manifest_sha256": raw_manifest["manifest_sha256"],
        "promotion_bytes": len(encoded_promotion),
        "promotion_sha256": sha256_bytes(encoded_promotion),
        "promotion_manifest_bytes": promotion_manifest["manifest_bytes"],
        "promotion_manifest_sha256": promotion_manifest["manifest_sha256"],
        "encounter_journal": copy.deepcopy(journal_binding),
        "complete": True,
    }
    return {**body, "completion_sha256": sha256_bytes(canonical_json(body))}


def _publication_contract_ancestry_ready(contract: dict[str, Path]) -> bool:
    try:
        current = _output_paths(contract["repo"])
    except (KeyError, OSError, RuntimeError):
        return False
    paths_match = all(
        contract.get(name) == path
        for name, path in current.items()
        if name not in {"repo", "store", "repo_identity", "store_identity"}
    )
    if not paths_match:
        return False
    for root_name in ("repo", "store"):
        expected = contract.get(f"{root_name}_identity")
        if expected is not None and expected != current[f"{root_name}_identity"]:
            return False
    return True


def _read_publication_authority_bounded(
    contract: dict[str, Path],
    path: Path,
    limit: int,
    *,
    repo_identity: dict[str, int] | None = None,
    store_identity: dict[str, int] | None = None,
) -> bytes:
    repo = contract["repo"]
    store = contract["store"]
    try:
        relative = path.relative_to(store)
        root = store
        label = "evidence store"
        expected_identity = store_identity
    except ValueError:
        relative = path.relative_to(repo)
        root = repo
        label = "repository"
        expected_identity = repo_identity
    identity = (
        _authority_root_identity(root, label)
        if expected_identity is None
        else _validated_authority_identity(expected_identity, label)
    )
    root_descriptor = _open_authority_root(root, identity, label)
    parent: int | None = None
    try:
        parent, name = _open_relative_parent(
            root_descriptor,
            relative,
            create=False,
            label="publication authority",
        )
        payload = _read_leaf_bounded_at(
            parent,
            name,
            limit=limit,
            label="publication authority",
        )
        first_parent_identity = _authority_identity_from_stat(os.fstat(parent))
        rebound_parent, rebound_name = _open_relative_parent(
            root_descriptor,
            relative,
            create=False,
            label="publication authority",
        )
        try:
            if (
                rebound_name != name
                or _authority_identity_from_stat(os.fstat(rebound_parent))
                != first_parent_identity
                or _read_leaf_bounded_at(
                    rebound_parent,
                    rebound_name,
                    limit=limit,
                    label="publication authority",
                )
                != payload
            ):
                raise ProtocolError("publication authority changed during read")
        finally:
            os.close(rebound_parent)
        return payload
    finally:
        if parent is not None:
            os.close(parent)
        os.close(root_descriptor)


def _stat_generation(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        stat.S_IMODE(value.st_mode),
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


@contextmanager
def _pinned_publication_snapshot(
    contract: dict[str, Any],
    completion: dict[str, Any],
    *,
    repo_identity: dict[str, int],
    store_identity: dict[str, int],
) -> Iterator[None]:
    """Hold every publication leaf and parent through the final decision."""

    repo_descriptor = _open_authority_root(
        contract["repo"],
        repo_identity,
        "repository",
    )
    try:
        store_descriptor = _open_authority_root(
            contract["store"],
            store_identity,
            "evidence store",
        )
    except Exception:
        os.close(repo_descriptor)
        raise
    owned_directories: list[int] = []
    parent_generations: dict[int, tuple[int, ...]] = {}
    leaf_pins: list[tuple[int, str, int, tuple[int, ...]]] = []
    directory_pins: list[tuple[int, str, int, tuple[int, ...]]] = []
    try:
        parent_generations[repo_descriptor] = _stat_generation(
            os.fstat(repo_descriptor)
        )
        parent_generations[store_descriptor] = _stat_generation(
            os.fstat(store_descriptor)
        )
    except Exception:
        os.close(store_descriptor)
        os.close(repo_descriptor)
        raise

    def own_directory(descriptor: int) -> int:
        owned_directories.append(descriptor)
        parent_generations[descriptor] = _stat_generation(os.fstat(descriptor))
        return descriptor

    def pin_leaf_at(
        parent: int,
        name: str,
        *,
        label: str,
        expected_sha256: str | None = None,
        expected_bytes: int | None = None,
        limit: int | None = None,
    ) -> None:
        try:
            initial = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except OSError as error:
            raise ProtocolError(f"{label} leaf is unavailable") from error
        if (
            not stat.S_ISREG(initial.st_mode)
            or not initial.st_mode & stat.S_IRUSR
            or initial.st_size < 0
        ):
            raise ProtocolError(f"{label} leaf identity differs")
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=parent,
            )
        except OSError as error:
            raise ProtocolError(f"{label} leaf cannot be pinned") from error
        try:
            observed = os.fstat(descriptor)
            if _stat_generation(observed) != _stat_generation(initial):
                raise ProtocolError(f"{label} leaf changed while pinning")
            if expected_sha256 is not None:
                assert expected_bytes is not None and limit is not None
                digest, byte_count = _hash_regular_descriptor(
                    descriptor,
                    limit=limit,
                    label=label,
                )
                if digest != expected_sha256 or byte_count != expected_bytes:
                    raise ProtocolError(f"{label} pinned bytes differ")
                os.lseek(descriptor, 0, os.SEEK_SET)
            leaf_pins.append(
                (parent, name, descriptor, _stat_generation(os.fstat(descriptor)))
            )
        except Exception:
            os.close(descriptor)
            raise

    def pin_relative_leaf(
        root: int,
        relative: Path,
        *,
        label: str,
        expected_sha256: str,
        expected_bytes: int,
        limit: int,
    ) -> None:
        parts = _relative_authority_parts(relative, label)
        parent = root
        for component in parts[:-1]:
            parent = pin_child_directory(parent, component, label)
        pin_leaf_at(
            parent,
            parts[-1],
            label=label,
            expected_sha256=expected_sha256,
            expected_bytes=expected_bytes,
            limit=limit,
        )

    def pin_child_directory(parent: int, name: str, label: str) -> int:
        try:
            initial = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except OSError as error:
            raise ProtocolError(f"{label} directory is unavailable") from error
        descriptor = _open_directory_at(
            parent,
            name,
            create=False,
            label=label,
        )
        try:
            if _stat_generation(os.fstat(descriptor)) != _stat_generation(initial):
                raise ProtocolError(f"{label} directory changed while pinning")
        except Exception:
            os.close(descriptor)
            raise
        own_directory(descriptor)
        directory_pins.append(
            (parent, name, descriptor, _stat_generation(os.fstat(descriptor)))
        )
        return descriptor

    try:
        fixed_leaves = (
            (
                store_descriptor,
                RAW_RELATIVE_PATH,
                "publication raw",
                completion["raw_sha256"],
                completion["raw_bytes"],
                MAX_RAW_BYTES,
            ),
            (
                repo_descriptor,
                contract["manifest"].relative_to(contract["repo"]),
                "publication raw manifest",
                completion["raw_manifest_sha256"],
                completion["raw_manifest_bytes"],
                MAX_MANIFEST_BYTES,
            ),
            (
                store_descriptor,
                PROMOTION_RELATIVE_PATH,
                "publication promotion",
                completion["promotion_sha256"],
                completion["promotion_bytes"],
                MAX_PROMOTION_BYTES,
            ),
            (
                repo_descriptor,
                contract["promotion_manifest"].relative_to(contract["repo"]),
                "publication promotion manifest",
                completion["promotion_manifest_sha256"],
                completion["promotion_manifest_bytes"],
                MAX_MANIFEST_BYTES,
            ),
            (
                store_descriptor,
                COMPLETION_RELATIVE_PATH,
                "publication completion",
                sha256_bytes(canonical_json(completion)),
                len(canonical_json(completion)),
                MAX_COMPLETION_BYTES,
            ),
        )
        for root, relative, label, digest, byte_count, limit in fixed_leaves:
            pin_relative_leaf(
                root,
                relative,
                label=label,
                expected_sha256=digest,
                expected_bytes=byte_count,
                limit=limit,
            )
        for label, digest, byte_count in (
            ("raw content-addressed object", completion["raw_sha256"], completion["raw_bytes"]),
            (
                "promotion content-addressed object",
                completion["promotion_sha256"],
                completion["promotion_bytes"],
            ),
        ):
            pin_relative_leaf(
                store_descriptor,
                Path("objects") / "sha256" / digest[:2] / digest,
                label=label,
                expected_sha256=digest,
                expected_bytes=byte_count,
                limit=MAX_RAW_BYTES,
            )

        journal_relative = contract["journal"].relative_to(contract["store"])
        journal_parts = _relative_authority_parts(
            journal_relative,
            "encounter journal",
        )
        journal_descriptor = store_descriptor
        for component in journal_parts:
            journal_descriptor = pin_child_directory(
                journal_descriptor,
                component,
                "encounter journal",
            )
        names = set(os.listdir(journal_descriptor))
        required_names = {
            STAGE_OPEN_NAME,
            SEGMENT_DIRECTORY_NAME,
            STAGE_SEAL_NAME,
        }
        if names != required_names:
            raise ProtocolError("encounter journal pinned layout differs")
        pin_leaf_at(
            journal_descriptor,
            STAGE_OPEN_NAME,
            label="journal stage-open",
        )
        pin_leaf_at(
            journal_descriptor,
            STAGE_SEAL_NAME,
            label="journal stage-seal",
        )
        segment_descriptor = pin_child_directory(
            journal_descriptor,
            SEGMENT_DIRECTORY_NAME,
            "journal segments",
        )
        segment_names = sorted(os.listdir(segment_descriptor))
        if not segment_names or len(segment_names) > MAX_STAGE_SEGMENTS:
            raise ProtocolError("encounter journal segment inventory differs")
        for name in segment_names:
            pin_leaf_at(
                segment_descriptor,
                name,
                label="journal segment",
            )

        yield

        for parent, name, descriptor, expected in leaf_pins:
            if (
                _stat_generation(os.fstat(descriptor)) != expected
                or _stat_generation(
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                )
                != expected
            ):
                raise ProtocolError("publication pinned leaf changed")
        for parent, name, descriptor, expected in directory_pins:
            if (
                _stat_generation(os.fstat(descriptor)) != expected
                or _stat_generation(
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                )
                != expected
            ):
                raise ProtocolError("publication pinned directory changed")
        for descriptor, expected in parent_generations.items():
            if _stat_generation(os.fstat(descriptor)) != expected:
                raise ProtocolError("publication parent generation changed")
        rebound_repo: int | None = None
        rebound_store: int | None = None
        try:
            rebound_repo = _open_authority_root(
                contract["repo"],
                repo_identity,
                "repository",
            )
            rebound_store = _open_authority_root(
                contract["store"],
                store_identity,
                "evidence store",
            )
        finally:
            if rebound_store is not None:
                os.close(rebound_store)
            if rebound_repo is not None:
                os.close(rebound_repo)
    finally:
        for _parent, _name, descriptor, _expected in reversed(leaf_pins):
            os.close(descriptor)
        for descriptor in reversed(owned_directories):
            os.close(descriptor)
        os.close(store_descriptor)
        os.close(repo_descriptor)


def _publication_completion_ready(
    contract: dict[str, Any],
    *,
    deadline: float | None = None,
) -> bool:
    try:
        repo_identity = _contract_authority_identity(
            contract,
            "repo",
            "repository",
        )
        store_identity = _contract_authority_identity(
            contract,
            "store",
            "evidence store",
        )
        if not _publication_contract_ancestry_ready(contract):
            return False
        binding_deadline = (
            deadline
            if deadline is not None
            else time.monotonic() + CALIBRATION_SECONDS
        )
        if time.monotonic() > binding_deadline:
            return False
        completion_bytes = _read_publication_authority_bounded(
            contract,
            contract["completion"],
            MAX_COMPLETION_BYTES,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
        value = json.loads(completion_bytes)
        required = {
            "schema_version",
            "experiment_id",
            "run_id",
            "execution_git_commit",
            "raw_bytes",
            "raw_sha256",
            "raw_manifest_bytes",
            "raw_manifest_sha256",
            "promotion_bytes",
            "promotion_sha256",
            "promotion_manifest_bytes",
            "promotion_manifest_sha256",
            "encounter_journal",
            "complete",
            "completion_sha256",
        }
        _exact(value, required, "publication completion")
        body = {key: value[key] for key in required - {"completion_sha256"}}
        if (
            value["schema_version"] != 1
            or value["experiment_id"] != EXPERIMENT_ID
            or value["run_id"] != DEFAULT_RUN_ID
            or value["complete"] is not True
            or completion_bytes != canonical_json(value)
            or _commit(value["execution_git_commit"], "completion execution")
            != value["execution_git_commit"]
            or value["completion_sha256"] != sha256_bytes(canonical_json(body))
        ):
            return False
        paths = (
            (contract["raw"], "raw_bytes", "raw_sha256", MAX_RAW_BYTES),
            (
                contract["manifest"],
                "raw_manifest_bytes",
                "raw_manifest_sha256",
                MAX_MANIFEST_BYTES,
            ),
            (
                contract["promotion"],
                "promotion_bytes",
                "promotion_sha256",
                MAX_PROMOTION_BYTES,
            ),
            (
                contract["promotion_manifest"],
                "promotion_manifest_bytes",
                "promotion_manifest_sha256",
                MAX_MANIFEST_BYTES,
            ),
        )
        payloads: dict[Path, bytes] = {}
        for path, byte_key, sha_key, limit in paths:
            if not _publication_contract_ancestry_ready(contract):
                return False
            payload = _read_publication_authority_bounded(
                contract,
                path,
                limit,
                repo_identity=repo_identity,
                store_identity=store_identity,
            )
            if (
                type(value[byte_key]) is not int
                or value[byte_key] <= 0
                or value[byte_key] > limit
                or len(payload) != value[byte_key]
                or sha256_bytes(payload) != _sha(value[sha_key], sha_key)
            ):
                return False
            payloads[path] = payload
        if not _publication_contract_ancestry_ready(contract):
            return False
        encoded = payloads[contract["raw"]]
        raw = decode_raw(encoded)
        if time.monotonic() > binding_deadline:
            return False
        if (
            len(encoded) != value["raw_bytes"]
            or raw.get("execution_git_commit") != value["execution_git_commit"]
            or raw.get("scientific", {}).get("execution_git_commit")
            != value["execution_git_commit"]
            or raw.get("scientific", {}).get("encounter_journal")
            != value["encounter_journal"]
        ):
            return False
        raw_inputs = list(RAW_INPUT_MANIFESTS)
        promotion_inputs = [
            f"evidence/manifests/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json",
            *raw_inputs,
        ]
        raw_binding = _manifest_binding_bounded(
            contract["repo"],
            path=contract["manifest"],
            artifact_id=DEFAULT_RUN_ID,
            kind="e14-anchor-prepublication-raw",
            artifact_sha256=value["raw_sha256"],
            artifact_bytes=value["raw_bytes"],
            execution_commit=value["execution_git_commit"],
            store=contract["store"],
            recipe=RECONSTRUCTION_RECIPE,
            input_manifests=raw_inputs,
            limitations=list(RAW_LIMITATIONS),
            environment_dirty=False,
            deadline=binding_deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
        promotion_binding = _manifest_binding_bounded(
            contract["repo"],
            path=contract["promotion_manifest"],
            artifact_id=PROMOTION_ARTIFACT_ID,
            kind="e14-promotion-decision",
            artifact_sha256=value["promotion_sha256"],
            artifact_bytes=value["promotion_bytes"],
            execution_commit=value["execution_git_commit"],
            store=contract["store"],
            recipe=PROMOTION_RECONSTRUCTION_RECIPE,
            input_manifests=promotion_inputs,
            limitations=list(PROMOTION_LIMITATIONS),
            environment_dirty=True,
            deadline=binding_deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
        if (
            raw_binding["manifest_bytes"] != value["raw_manifest_bytes"]
            or raw_binding["manifest_sha256"] != value["raw_manifest_sha256"]
            or promotion_binding["manifest_bytes"]
            != value["promotion_manifest_bytes"]
            or promotion_binding["manifest_sha256"]
            != value["promotion_manifest_sha256"]
        ):
            return False
        if time.monotonic() > binding_deadline:
            return False
        if not _publication_contract_ancestry_ready(contract):
            return False
        promotion_bytes = payloads[contract["promotion"]]
        promotion = json.loads(promotion_bytes)
        if canonical_json(promotion) != promotion_bytes:
            return False
        expected_promotion = finalize_after_reconstruction(
            raw,
            promotion["reconstruction"],
            encoded_raw=encoded,
            raw_manifest=raw_binding,
            post_record_verification=promotion["post_record_verification"],
            repo=contract["repo"],
            deadline=binding_deadline,
        )
        if promotion != expected_promotion:
            return False
        initial_stage = _journal_stage_binding_bounded(
            contract["repo"],
            store=contract["store"],
            journal=contract["journal"],
            expected_scientific_sha256=value["encounter_journal"][
                "scientific_sha256"
            ],
            repo_identity=repo_identity,
            store_identity=store_identity,
            deadline=binding_deadline,
        )
        stable_payloads = all(
            _read_publication_authority_bounded(
                contract,
                path,
                limit,
                repo_identity=repo_identity,
                store_identity=store_identity,
            )
            == payloads[path]
            for path, _byte_key, _sha_key, limit in paths
        )
        stable_completion = (
            _read_publication_authority_bounded(
                contract,
                contract["completion"],
                MAX_COMPLETION_BYTES,
                repo_identity=repo_identity,
                store_identity=store_identity,
            )
            == completion_bytes
        )
        if not stable_payloads or not stable_completion:
            return False
        with _pinned_publication_snapshot(
            contract,
            value,
            repo_identity=repo_identity,
            store_identity=store_identity,
        ):
            final_raw_binding = _manifest_binding_bounded(
                contract["repo"],
                path=contract["manifest"],
                artifact_id=DEFAULT_RUN_ID,
                kind="e14-anchor-prepublication-raw",
                artifact_sha256=value["raw_sha256"],
                artifact_bytes=value["raw_bytes"],
                execution_commit=value["execution_git_commit"],
                store=contract["store"],
                recipe=RECONSTRUCTION_RECIPE,
                input_manifests=raw_inputs,
                limitations=list(RAW_LIMITATIONS),
                environment_dirty=False,
                deadline=binding_deadline,
                repo_identity=repo_identity,
                store_identity=store_identity,
            )
            final_promotion_binding = _manifest_binding_bounded(
                contract["repo"],
                path=contract["promotion_manifest"],
                artifact_id=PROMOTION_ARTIFACT_ID,
                kind="e14-promotion-decision",
                artifact_sha256=value["promotion_sha256"],
                artifact_bytes=value["promotion_bytes"],
                execution_commit=value["execution_git_commit"],
                store=contract["store"],
                recipe=PROMOTION_RECONSTRUCTION_RECIPE,
                input_manifests=promotion_inputs,
                limitations=list(PROMOTION_LIMITATIONS),
                environment_dirty=True,
                deadline=binding_deadline,
                repo_identity=repo_identity,
                store_identity=store_identity,
            )
            final_stage = _journal_stage_binding_bounded(
                contract["repo"],
                store=contract["store"],
                journal=contract["journal"],
                expected_scientific_sha256=value["encounter_journal"][
                    "scientific_sha256"
                ],
                repo_identity=repo_identity,
                store_identity=store_identity,
                deadline=binding_deadline,
            )
            ready = bool(
                _publication_contract_ancestry_ready(contract)
                and _authority_root_identity(contract["repo"], "repository")
                == repo_identity
                and _authority_root_identity(contract["store"], "evidence store")
                == store_identity
                and final_raw_binding == raw_binding
                and final_promotion_binding == promotion_binding
                and initial_stage == final_stage
                and final_stage["sealed"]
                and not final_stage["torn_tail"]
                and final_stage["binding"] == value["encounter_journal"]
                and time.monotonic() <= binding_deadline
            )
        return ready
    except (
        JournalError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return False


def _quarantine_publication(contract: dict[str, Any]) -> None:
    """Durably and idempotently remove every public authority surface."""

    # This remains an advisory/rebinding check; every destructive operation
    # below independently pins its root and walks parents without following
    # links.  It therefore cannot become a check/use authorization token.
    _publication_contract_ancestry_ready(contract)

    pairs = (
        (
            contract["completion"],
            contract["failed_completion"],
            MAX_COMPLETION_BYTES,
        ),
        (
            contract["promotion_manifest"],
            contract["failed_promotion_manifest"],
            MAX_MANIFEST_BYTES,
        ),
        (contract["manifest"], contract["failed_manifest"], MAX_MANIFEST_BYTES),
        (
            contract["promotion"],
            contract["failed_promotion"],
            MAX_PROMOTION_BYTES,
        ),
    )
    errors: list[str] = []
    repo_descriptor: int | None = None
    store_descriptor: int | None = None
    remaining = False
    try:
        repo = contract["repo"]
        store = contract["store"]
        repo_identity = _contract_authority_identity(
            contract,
            "repo",
            "repository",
        )
        repo_descriptor = _open_authority_root(
            repo,
            repo_identity,
            "repository",
        )
        expected_store_identity = contract.get("store_identity")
        if expected_store_identity is not None:
            store_identity = _validated_authority_identity(
                expected_store_identity,
                "evidence store",
            )
            store_descriptor = _open_authority_root(
                store,
                store_identity,
                "evidence store",
            )
        else:
            try:
                store_identity = _authority_root_identity(store, "evidence store")
                store_descriptor = _open_authority_root(
                    store,
                    store_identity,
                    "evidence store",
                )
            except ProtocolError:
                if store.parent != repo or store.name != ".evidence":
                    raise
                store_descriptor = _open_directory_at(
                    repo_descriptor,
                    store.name,
                    create=True,
                    label="evidence store",
                )
                store_identity = _authority_identity_from_stat(
                    os.fstat(store_descriptor)
                )
            contract["store_identity"] = store_identity

        def authority_relative(path: Path) -> tuple[int, Path]:
            try:
                return store_descriptor, path.relative_to(store)
            except ValueError:
                try:
                    return repo_descriptor, path.relative_to(repo)
                except ValueError as error:
                    raise ProtocolError(
                        "publication quarantine path leaves its authority root"
                    ) from error

        def pin_parent_chain(
            root_descriptor: int,
            relative: Path,
            *,
            create: bool,
            label: str,
        ) -> tuple[int, str, list[tuple[int, str, int, dict[str, int]]]]:
            parts = _relative_authority_parts(relative, label)
            current = root_descriptor
            pins: list[tuple[int, str, int, dict[str, int]]] = []
            try:
                for component in parts[:-1]:
                    child = _open_directory_at(
                        current,
                        component,
                        create=create,
                        label=label,
                    )
                    identity = _authority_identity_from_stat(os.fstat(child))
                    if _authority_identity_from_stat(
                        os.stat(
                            component,
                            dir_fd=current,
                            follow_symlinks=False,
                        )
                    ) != identity:
                        os.close(child)
                        raise ProtocolError(f"{label} chain changed while pinning")
                    pins.append((current, component, child, identity))
                    current = child
                return current, parts[-1], pins
            except Exception:
                for _parent, _name, descriptor, _identity in reversed(pins):
                    os.close(descriptor)
                raise

        def rebind_chain(
            pins: list[tuple[int, str, int, dict[str, int]]],
        ) -> None:
            for parent, name, descriptor, identity in pins:
                if (
                    _authority_identity_from_stat(os.fstat(descriptor))
                    != identity
                    or _authority_identity_from_stat(
                        os.stat(name, dir_fd=parent, follow_symlinks=False)
                    )
                    != identity
                ):
                    raise ProtocolError("publication quarantine chain changed")

        # Preserve a durable failure copy before unlinking.  If interrupted
        # between install and unlink, the next pass verifies the exact retained
        # bytes and completes the unlink through the same pinned parent.
        for source, target, limit in pairs:
            source_parent: int | None = None
            target_parent: int | None = None
            target_descriptor: int | None = None
            source_pins: list[tuple[int, str, int, dict[str, int]]] = []
            target_pins: list[tuple[int, str, int, dict[str, int]]] = []
            try:
                source_root, source_relative = authority_relative(source)
                source_parent, source_name, source_pins = pin_parent_chain(
                    source_root,
                    source_relative,
                    create=False,
                    label="publication quarantine source",
                )
                try:
                    source_stat = os.stat(
                        source_name,
                        dir_fd=source_parent,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    continue
                payload: bytes | None = None
                source_is_preservable = bool(
                    stat.S_ISREG(source_stat.st_mode)
                    and 0 <= source_stat.st_size <= limit
                )
                can_unlink = not source_is_preservable
                if source_is_preservable:
                    try:
                        payload = _read_leaf_bounded_at(
                            source_parent,
                            source_name,
                            limit=limit,
                            label="publication quarantine source",
                        )
                    except (OSError, ProtocolError):
                        errors.append("quarantine-source-rejected")
                else:
                    errors.append("quarantine-source-rejected")
                if payload is not None:
                    try:
                        target_relative = target.relative_to(store)
                        target_parent, target_name, target_pins = pin_parent_chain(
                            store_descriptor,
                            target_relative,
                            create=True,
                            label="publication quarantine target",
                        )
                        can_unlink = _install_failure_bytes_at(
                            store_descriptor,
                            target_relative,
                            payload,
                            limit=limit,
                        )
                        if not can_unlink:
                            errors.append("quarantine-destination-differs")
                        elif (
                            _read_leaf_bounded_at(
                                target_parent,
                                target_name,
                                limit=limit,
                                label="publication quarantine target",
                            )
                            != payload
                        ):
                            can_unlink = False
                            errors.append("quarantine-destination-differs")
                        else:
                            target_descriptor = os.open(
                                target_name,
                                os.O_RDONLY
                                | os.O_NOFOLLOW
                                | getattr(os, "O_CLOEXEC", 0),
                                dir_fd=target_parent,
                            )
                            os.fsync(target_descriptor)
                    except (OSError, ProtocolError, ValueError):
                        can_unlink = False
                        errors.append("quarantine-preservation-failed")

                if can_unlink:
                    rebind_chain(source_pins)
                    rebind_chain(target_pins)
                    try:
                        _unlink_publication_source(
                            source_parent,
                            source_name,
                            source,
                        )
                    except OSError:
                        errors.append("quarantine-unlink-failed")
                    if payload is not None and target_parent is not None:
                        expected_digest = sha256_bytes(payload)
                        try:
                            retained = _read_leaf_bounded_at(
                                target_parent,
                                target_name,
                                limit=limit,
                                label="publication quarantine final target",
                            )
                        except (OSError, ProtocolError):
                            retained = None
                        if retained != payload:
                            try:
                                os.unlink(target_name, dir_fd=target_parent)
                                os.fsync(target_parent)
                            except FileNotFoundError:
                                pass
                            except OSError:
                                errors.append("quarantine-target-restore-failed")
                            try:
                                restored = _install_failure_bytes_at(
                                    store_descriptor,
                                    target_relative,
                                    payload,
                                    limit=limit,
                                )
                            except (OSError, ProtocolError):
                                restored = False
                            if not restored:
                                errors.append("quarantine-target-restore-failed")
                        try:
                            final_payload = _read_leaf_bounded_at(
                                target_parent,
                                target_name,
                                limit=limit,
                                label="publication quarantine final target",
                            )
                        except (OSError, ProtocolError):
                            final_payload = None
                        if (
                            final_payload != payload
                            or final_payload is None
                            or sha256_bytes(final_payload) != expected_digest
                        ):
                            errors.append("quarantine-final-target-differs")
                        rebind_chain(target_pins)
            except FileNotFoundError:
                continue
            except (OSError, ProtocolError):
                errors.append("quarantine-source-ancestry-rejected")
            finally:
                if target_descriptor is not None:
                    os.close(target_descriptor)
                for _parent, _name, descriptor, _identity in reversed(target_pins):
                    os.close(descriptor)
                for _parent, _name, descriptor, _identity in reversed(source_pins):
                    os.close(descriptor)

        for source, _target, _limit in pairs:
            parent: int | None = None
            try:
                root_descriptor, relative = authority_relative(source)
                parent, name = _open_relative_parent(
                    root_descriptor,
                    relative,
                    create=False,
                    label="publication quarantine readback",
                )
                try:
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    remaining = True
            except FileNotFoundError:
                pass
            except (OSError, ProtocolError):
                remaining = True
            finally:
                if parent is not None:
                    os.close(parent)
    except (KeyError, OSError, ProtocolError):
        remaining = True
        errors.append("quarantine-authority-root-rejected")
    finally:
        if store_descriptor is not None:
            os.close(store_descriptor)
        if repo_descriptor is not None:
            os.close(repo_descriptor)
    if remaining:
        raise RuntimeError("public authority could not be removed")
    if errors:
        raise RuntimeError("publication quarantine was not fully preserved")


def _invalidate_publication(
    contract: dict[str, Path],
    *,
    code: str,
    authoritative_raw: Path,
) -> None:
    quarantine_error: Exception | None = None
    journal_summary: dict[str, Any] | None = None
    journal_source = contract.get("journal")
    journal_target = contract.get("failed_journal")
    if journal_source is not None and journal_target is not None:
        try:
            journal_summary = _quarantine_encounter_journal(
                journal_source,
                journal_target,
                expected_store_identity=_contract_authority_identity(
                    contract,
                    "store",
                    "evidence store",
                ),
            )
        except Exception as error:
            quarantine_error = error
    try:
        _quarantine_publication(contract)
    except Exception as error:  # continue to the independent failure receipt
        if quarantine_error is None:
            quarantine_error = error
    failure_error: Exception | None = None
    try:
        if not _failure_receipt_ready(contract, expected_code=code):
            _failure(
                contract,
                code=code,
                authoritative_raw=authoritative_raw,
                journal_summary=journal_summary,
            )
    except Exception as error:
        failure_error = error
    if any(
        contract[name].exists()
        for name in ("manifest", "promotion", "promotion_manifest")
    ):
        raise RuntimeError("publication invalidation left public authority")
    if quarantine_error is not None or failure_error is not None:
        raise RuntimeError("publication invalidation could not preserve all failure evidence")


def run(repo: Path) -> tuple[Path, dict[str, Any]]:
    repo = repo.resolve()
    if _recover_incomplete_startup(repo):
        raise RuntimeError("interrupted authoritative transaction was quarantined")
    contract = output_contract(repo, allow_manifest=False)
    store_identity = _contract_authority_identity(
        contract,
        "store",
        "evidence store",
    )
    execution, lock, task, acceptance = locked_context(
        repo,
        allow_regeneration=False,
    )
    try:
        raw = _execute_locked_raw(
            repo,
            execution,
            lock,
            task,
            acceptance,
            store_identity=store_identity,
        )
    except Exception as error:
        _preserve_prepublication_failure(
            contract,
            code="authoritative_calibration_process_failed",
        )
        raise RuntimeError("authoritative OT-0077 calibration failed") from error
    if raw["summary"]["disposition"] != "pending-reconstruction":
        _preserve_prepublication_failure(
            contract,
            code="authoritative_calibration_failed",
        )
        raise RuntimeError("authoritative OT-0077 calibration invalidated")
    try:
        reconstruction = verify_fresh_root(
            repo,
            implementation=lock["implementation_git_commit"],
            seed_bytes=_read_private_seed(repo),
            authoritative_raw=contract["raw"],
            expected_store_identity=store_identity,
        )
    except Exception as error:
        _preserve_prepublication_failure(
            contract,
            code="fresh_root_reconstruction_process_failed",
            quarantine_reconstruction=True,
        )
        raise RuntimeError("fresh-root private reconstruction failed") from error
    if reconstruction.get("pass") is not True:
        _preserve_prepublication_failure(
            contract,
            code=str(reconstruction.get("status")),
            quarantine_reconstruction=True,
        )
        raise RuntimeError("fresh-root private reconstruction failed")
    publication_deadline = time.monotonic() + CALIBRATION_SECONDS
    try:
        repo_identity = _contract_authority_identity(
            contract,
            "repo",
            "repository",
        )
        store_identity = _contract_authority_identity(
            contract,
            "store",
            "evidence store",
        )
        authoritative_encoded = _read_publication_authority_bounded(
            contract,
            contract["raw"],
            MAX_RAW_BYTES,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
        raw_sha256 = sha256_bytes(authoritative_encoded)
        if time.monotonic() > publication_deadline:
            raise ProtocolError("raw publication read exceeded its deadline")
    except Exception as error:
        _invalidate_publication(
            contract,
            code="raw_publication_read_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("raw publication read failed") from error
    raw_inputs = list(RAW_INPUT_MANIFESTS)
    raw_limitations = list(RAW_LIMITATIONS)
    promotion_inputs = [
        f"evidence/manifests/{EXPERIMENT_ID}/{DEFAULT_RUN_ID}.json",
        *raw_inputs,
    ]
    promotion_limitations = list(PROMOTION_LIMITATIONS)
    try:
        manifest = _record_artifact_bounded(
            repo,
            input_path=contract["raw"],
            store=contract["store"],
            artifact_id=DEFAULT_RUN_ID,
            kind="e14-anchor-prepublication-raw",
            artifact_sha256=raw_sha256,
            artifact_bytes=len(authoritative_encoded),
            recipe=RECONSTRUCTION_RECIPE,
            limitations=raw_limitations,
            input_manifests=raw_inputs,
            deadline=publication_deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
    except Exception as error:
        _invalidate_publication(
            contract,
            code="raw_manifest_record_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("raw artifact recording failed") from error

    try:
        raw_manifest = _manifest_binding_bounded(
            repo,
            path=manifest,
            artifact_id=DEFAULT_RUN_ID,
            kind="e14-anchor-prepublication-raw",
            artifact_sha256=raw_sha256,
            artifact_bytes=len(authoritative_encoded),
            execution_commit=execution,
            store=contract["store"],
            recipe=RECONSTRUCTION_RECIPE,
            input_manifests=raw_inputs,
            limitations=raw_limitations,
            environment_dirty=False,
            deadline=publication_deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
    except (OSError, RuntimeError, ValueError) as error:
        _invalidate_publication(
            contract,
            code="raw_manifest_readback_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("raw manifest readback failed") from error

    try:
        post_record = _post_raw_record_verification(
            repo,
            manifest=manifest,
            store=contract["store"],
            expected_binding=raw_manifest,
            artifact_sha256=raw_sha256,
            artifact_bytes=len(authoritative_encoded),
            execution_commit=execution,
            recipe=RECONSTRUCTION_RECIPE,
            input_manifests=raw_inputs,
            limitations=raw_limitations,
            deadline=publication_deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
    except Exception as error:
        _invalidate_publication(
            contract,
            code="post_raw_record_verification_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("post-record verification failed") from error
    if not _publication_verification_passed(post_record):
        _invalidate_publication(
            contract,
            code="post_raw_record_verification_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("post-record tests, audit, or readback failed")

    try:
        publication = finalize_after_reconstruction(
            raw,
            reconstruction,
            encoded_raw=authoritative_encoded,
            raw_manifest=raw_manifest,
            post_record_verification=post_record,
            repo=repo,
            deadline=publication_deadline,
        )
        promotion_encoded = canonical_json(publication)
        _write_contract_store_sealed_bytes(
            contract,
            "promotion",
            promotion_encoded,
            limit=MAX_PROMOTION_BYTES,
        )
        promotion_manifest = _record_artifact_bounded(
            repo,
            input_path=contract["promotion"],
            store=contract["store"],
            artifact_id=PROMOTION_ARTIFACT_ID,
            kind="e14-promotion-decision",
            artifact_sha256=sha256_bytes(promotion_encoded),
            artifact_bytes=len(promotion_encoded),
            recipe=PROMOTION_RECONSTRUCTION_RECIPE,
            limitations=promotion_limitations,
            input_manifests=promotion_inputs,
            deadline=publication_deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
        promotion_binding = _manifest_binding_bounded(
            repo,
            path=promotion_manifest,
            artifact_id=PROMOTION_ARTIFACT_ID,
            kind="e14-promotion-decision",
            artifact_sha256=sha256_bytes(promotion_encoded),
            artifact_bytes=len(promotion_encoded),
            execution_commit=execution,
            store=contract["store"],
            recipe=PROMOTION_RECONSTRUCTION_RECIPE,
            input_manifests=promotion_inputs,
            limitations=promotion_limitations,
            environment_dirty=True,
            deadline=publication_deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
    except Exception as error:
        _invalidate_publication(
            contract,
            code="promotion_decision_record_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("durable promotion decision recording failed") from error

    try:
        final_audit = _bounded_command(
            [sys.executable, "-m", "open_trajectory_evidence", "audit"],
            repo,
            publication_deadline,
            "final_publication_audit",
        )
    except Exception as error:
        _invalidate_publication(
            contract,
            code="final_publication_verification_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("final publication audit failed") from error
    try:
        final_raw_binding = _manifest_binding_bounded(
            repo,
            path=manifest,
            artifact_id=DEFAULT_RUN_ID,
            kind="e14-anchor-prepublication-raw",
            artifact_sha256=raw_sha256,
            artifact_bytes=len(authoritative_encoded),
            execution_commit=execution,
            store=contract["store"],
            recipe=RECONSTRUCTION_RECIPE,
            input_manifests=raw_inputs,
            limitations=raw_limitations,
            environment_dirty=False,
            deadline=publication_deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
        final_promotion_binding = _manifest_binding_bounded(
            repo,
            path=promotion_manifest,
            artifact_id=PROMOTION_ARTIFACT_ID,
            kind="e14-promotion-decision",
            artifact_sha256=sha256_bytes(promotion_encoded),
            artifact_bytes=len(promotion_encoded),
            execution_commit=execution,
            store=contract["store"],
            recipe=PROMOTION_RECONSTRUCTION_RECIPE,
            input_manifests=promotion_inputs,
            limitations=promotion_limitations,
            environment_dirty=True,
            deadline=publication_deadline,
            repo_identity=repo_identity,
            store_identity=store_identity,
        )
    except Exception as error:
        _invalidate_publication(
            contract,
            code="final_publication_verification_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("final publication manifest rebind failed") from error
    final_journal_ready = _encounter_journal_ready(
        raw["scientific"],
        repo=repo,
        purpose="anchor",
        journal_root=contract["journal"],
        deadline=publication_deadline,
    )
    if (
        final_audit != {"status": "passed", "returncode": 0}
        or final_raw_binding != raw_manifest
        or final_promotion_binding != promotion_binding
        or final_journal_ready is not True
        or promotion_binding.get("readback_status")
        != "manifest and evidence bytes verified"
        or promotion_binding.get("artifact_sha256")
        != sha256_bytes(promotion_encoded)
        or promotion_binding.get("artifact_bytes") != len(promotion_encoded)
        or time.monotonic() > publication_deadline
    ):
        _invalidate_publication(
            contract,
            code="final_publication_verification_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("final promotion manifest audit or readback failed")
    try:
        completion = _publication_completion(
            contract,
            execution_commit=execution,
            encoded_raw=authoritative_encoded,
            raw_manifest=raw_manifest,
            encoded_promotion=promotion_encoded,
            promotion_manifest=promotion_binding,
            journal_binding=raw["scientific"]["encounter_journal"],
        )
        _write_contract_store_sealed_bytes(
            contract,
            "completion",
            canonical_json(completion),
            limit=MAX_COMPLETION_BYTES,
        )
        if (
            not _publication_completion_ready(
                contract,
                deadline=publication_deadline,
            )
            or time.monotonic() > publication_deadline
        ):
            raise ProtocolError("publication completion witness did not rebind")
    except Exception as error:
        _invalidate_publication(
            contract,
            code="publication_completion_failed",
            authoritative_raw=contract["raw"],
        )
        raise RuntimeError("publication completion failed") from error
    return promotion_manifest, publication


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0077-harness")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-authoritative", action="store_true")
    modes.add_argument("--reconstruct-only", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.prepare_authoritative:
            attempt, _seed, task, lock = prepare(repo)
            payload = {
                "attempt": _logical(attempt.relative_to(_store(repo))),
                "task": _logical(task.relative_to(_store(repo))),
                "run_lock": str(lock.relative_to(repo)),
                "private_seed_retained": True,
            }
        else:
            operation = reconstruct if args.reconstruct_only else run
            path, summary = operation(repo)
            payload = {
                "output" if args.reconstruct_only else "manifest": (
                    _logical(path.relative_to(_store(repo)))
                    if args.reconstruct_only
                    else str(path.relative_to(repo))
                ),
                "summary": summary,
            }
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
