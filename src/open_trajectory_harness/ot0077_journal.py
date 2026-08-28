"""Crash-durable, segmented encounter journals for OT-0077.

The calibration controller owns these journals.  Their physical paths are
never placed in a scientific payload or a consumer request.  A lineage file
has exactly one writer, is created exclusively, and durably records causal
prefixes at the points where they become knowable:

* five lineage-root receipts in ``lineage-open``;
* one consumer receipt in ``consumer-checkpoint``;
* eight outcome-through-projection receipts in ``encounter-commit``; and
* one final terminal consumer receipt before ``lineage-seal``.

Consequently, failure while starting the next fresh consumer cannot erase the
preceding encounter's outcome, update, state, or projection.  A torn or
unsealed file is evidence of an incomplete attempt, never a resumable success.
The reader can retain its verified prefix, but only a complete, independently
validated receipt chain can contribute to a sealed stage binding.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import struct
import threading
import zlib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Iterator, Mapping, Sequence

from .ot0002 import canonical_json, sha256_bytes
from .ot0077_receipts import EXPERIMENT_ID, SCHEMA_VERSION, validate_chain

try:  # POSIX is required by the OT-0077 execution protocol.
    import fcntl
except ImportError:  # pragma: no cover - a fail-closed portability fallback.
    fcntl = None  # type: ignore[assignment]


JOURNAL_FORMAT: Final = "ot0077-segmented-encounter-journal-v1"
FRAME_MAGIC: Final = b"OTJ1"
FRAME_HEADER: Final = struct.Struct(">4sII32s")
MAX_FRAME_RAW_BYTES: Final = 1_048_576
MAX_FRAME_COMPRESSED_BYTES: Final = 1_114_112
MAX_ENCODED_FRAME_BYTES: Final = FRAME_HEADER.size + MAX_FRAME_COMPRESSED_BYTES
MAX_STAGE_SEGMENTS: Final = 4_096
MAX_STAGE_ENCOUNTERS: Final = 1_000_000
MAX_SEGMENT_ENCOUNTERS: Final = 4_096

STAGE_OPEN_NAME: Final = "stage-open.otj"
STAGE_SEAL_NAME: Final = "stage-seal.otj"
SEGMENT_DIRECTORY_NAME: Final = "segments"

SCOPES: Final = (
    "main",
    "rollback-parent-replay",
    "rollback-rewind",
    "rollback-alternate",
)
_SCOPE_ORDINAL: Final = {scope: index for index, scope in enumerate(SCOPES)}

_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_SAFE_ID = re.compile(r"[a-z0-9][a-z0-9_.+-]{0,79}")
_LOGICAL_COMPONENT = re.compile(r"[A-Za-z0-9_.+-]{1,80}")
_SEGMENT_NAME = re.compile(
    r"(?P<ordinal>[0-9]{2})-(?P<case_index>[0-9]{6})-"
    r"(?P<condition_id>[0-9a-f]{64})-(?P<branch_id>[0-9a-f]{64})\.otj"
)

_ROOT_RECEIPT_KINDS: Final = (
    "case",
    "reachable-surface",
    "lineage",
    "state",
    "projection",
)
_ENCOUNTER_RECEIPT_KINDS: Final = (
    "encounter",
    "query",
    "pre-state",
    "prediction",
    "outcome",
    "update",
    "state",
    "projection",
)
_RECEIPT_KEYS: Final = {
    "context",
    "experiment_id",
    "kind",
    "parents",
    "payload",
    "receipt_sha256",
    "schema_version",
}
_CONTEXT_KEYS: Final = {
    "branch_id",
    "case_id",
    "encounter_index",
    "episode_index",
    "lineage_id",
}
_PARENT_KEYS: Final = {"receipt_sha256", "role"}

_LINEAGE_OPEN_KEYS: Final = {
    "branch_id",
    "case_id",
    "case_index",
    "condition_id",
    "encounter_count",
    "encounter_start",
    "execution_git_commit",
    "experiment_id",
    "initial_receipts",
    "journal_format",
    "lineage_id",
    "purpose",
    "record_kind",
    "run_id",
    "schema_version",
    "scope",
    "task_sha256",
}
_CHECKPOINT_KEYS: Final = {
    "branch_id",
    "case_id",
    "condition_id",
    "encounter_index",
    "experiment_id",
    "lineage_id",
    "mode",
    "receipt",
    "record_kind",
    "schema_version",
    "scope",
}
_ENCOUNTER_COMMIT_KEYS: Final = {
    "branch_id",
    "case_id",
    "condition_id",
    "encounter_index",
    "experiment_id",
    "lineage_id",
    "receipt_count",
    "receipts",
    "record_kind",
    "schema_version",
    "scope",
}
_LINEAGE_SEAL_KEYS: Final = {
    "branch_id",
    "case_id",
    "case_receipt_sha256",
    "condition_id",
    "encounter_count",
    "encounter_start",
    "experiment_id",
    "lineage_id",
    "lineage_receipt_sha256",
    "receipt_order_sha256",
    "record_kind",
    "schema_version",
    "scope",
    "summary",
    "terminal_audit_receipt_sha256",
    "trace_sha256",
}
_STAGE_OPEN_KEYS: Final = {
    "execution_git_commit",
    "expected_case_count",
    "expected_scope_counts",
    "experiment_id",
    "journal_format",
    "logical_path",
    "purpose",
    "record_kind",
    "run_id",
    "schema_version",
    "task_sha256",
}
_STAGE_SEAL_KEYS: Final = {
    "completed_encounter_count",
    "execution_git_commit",
    "experiment_id",
    "journal_format",
    "journal_sha256",
    "logical_path",
    "purpose",
    "receipt_count",
    "record_kind",
    "run_id",
    "schema_version",
    "scope_counts",
    "scientific_sha256",
    "segment_count",
    "segment_index_sha256",
    "segments",
    "stage_open_sha256",
    "task_sha256",
}
_SEGMENT_IDENTITY_KEYS: Final = {
    "branch_id",
    "byte_count",
    "case_id",
    "case_index",
    "completed_encounter_count",
    "condition_id",
    "encounter_count",
    "encounter_start",
    "file_sha256",
    "lineage_id",
    "receipt_count",
    "relative_path",
    "scope",
    "trace_sha256",
}


class JournalError(ValueError):
    """Fail-closed journal rejection with a path-free diagnostic."""


@dataclass(frozen=True)
class SegmentRead:
    """Validated contents of one lineage segment."""

    records: tuple[dict[str, Any], ...]
    receipt_order: tuple[dict[str, Any], ...]
    chain: dict[str, Any] | None
    sealed: bool
    torn_tail: bool
    completed_encounter_count: int
    file_sha256: str
    byte_count: int

    @property
    def open_record(self) -> dict[str, Any]:
        return self.records[0]


@dataclass(frozen=True)
class StageRead:
    """Validated stage state, including incomplete retained prefixes."""

    stage_open: dict[str, Any]
    segments: tuple[SegmentRead, ...]
    segment_relative_paths: tuple[str, ...]
    stage_seal: dict[str, Any] | None
    binding: dict[str, Any] | None
    sealed: bool
    torn_tail: bool


def _exact_dict(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise JournalError(f"{label} keys differ from the journal schema")
    return value


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise JournalError(f"{label} is not a lowercase SHA-256 identity")
    return value


def _commit(value: object) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        raise JournalError("execution commit is not a lowercase Git identity")
    return value


def _safe_id(value: object, label: str) -> str:
    if type(value) is not str or _SAFE_ID.fullmatch(value) is None:
        raise JournalError(f"{label} is not bounded path-free text")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise JournalError(f"{label} is not an integer at least {minimum}")
    return value


def _logical_path(value: object) -> str:
    if type(value) is not str or len(value) > 512 or not value.startswith("$EVIDENCE/"):
        raise JournalError("logical journal path must be rooted at $EVIDENCE")
    if "\\" in value or "//" in value or "\x00" in value:
        raise JournalError("logical journal path is noncanonical")
    parts = value.split("/")
    if parts[0] != "$EVIDENCE" or any(
        part in {"", ".", ".."} or _LOGICAL_COMPONENT.fullmatch(part) is None
        for part in parts[1:]
    ):
        raise JournalError("logical journal path has an unsafe component")
    return value


def _scope(value: object) -> str:
    if value not in SCOPES:
        raise JournalError("journal scope is unavailable")
    return str(value)


def _base_identity(value: Mapping[str, Any]) -> None:
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("experiment_id") != EXPERIMENT_ID
    ):
        raise JournalError("journal record identity differs")


def _copy_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(value))


def _encode_frame(record: Mapping[str, Any]) -> bytes:
    if type(record) is not dict:
        raise JournalError("journal record must be a dictionary")
    raw = canonical_json(record)
    if not 1 <= len(raw) <= MAX_FRAME_RAW_BYTES:
        raise JournalError("canonical journal frame exceeds its byte budget")
    compressed = zlib.compress(raw, level=1)
    if not 1 <= len(compressed) <= MAX_FRAME_COMPRESSED_BYTES:
        raise JournalError("compressed journal frame exceeds its byte budget")
    return FRAME_HEADER.pack(
        FRAME_MAGIC,
        len(raw),
        len(compressed),
        hashlib.sha256(raw).digest(),
    ) + compressed


def _decode_frame(header: bytes, payload: bytes) -> dict[str, Any]:
    try:
        magic, raw_length, compressed_length, expected_digest = FRAME_HEADER.unpack(
            header
        )
    except struct.error as error:  # Defensive: callers require exact header size.
        raise JournalError("journal frame header is malformed") from error
    if magic != FRAME_MAGIC:
        raise JournalError("journal frame magic differs")
    if not 1 <= raw_length <= MAX_FRAME_RAW_BYTES:
        raise JournalError("journal frame raw length exceeds its byte budget")
    if not 1 <= compressed_length <= MAX_FRAME_COMPRESSED_BYTES:
        raise JournalError("journal frame compressed length exceeds its byte budget")
    if len(payload) != compressed_length:
        raise JournalError("journal frame payload length differs")
    decompressor = zlib.decompressobj()
    try:
        raw = decompressor.decompress(payload, MAX_FRAME_RAW_BYTES + 1)
    except zlib.error as error:
        raise JournalError("journal frame compression is invalid") from error
    if (
        len(raw) > MAX_FRAME_RAW_BYTES
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise JournalError("journal frame compression is noncanonical or over budget")
    if len(raw) != raw_length or hashlib.sha256(raw).digest() != expected_digest:
        raise JournalError("journal frame content identity differs")
    if zlib.compress(raw, level=1) != payload:
        raise JournalError("journal frame compression is not canonical")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise JournalError("journal frame JSON is invalid") from error
    if type(value) is not dict or canonical_json(value) != raw:
        raise JournalError("journal frame JSON is not canonical")
    return value


def _open_readonly(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise JournalError("journal artifact cannot be opened safely") from error
    os.set_inheritable(fd, False)
    try:
        mode = os.fstat(fd).st_mode
        if not stat.S_ISREG(mode):
            raise JournalError("journal artifact is not a regular file")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_frames(
    path: Path,
    *,
    allow_incomplete: bool,
    max_frames: int,
    max_byte_count: int,
) -> tuple[list[dict[str, Any]], bool]:
    _integer(max_frames, "journal frame ceiling", minimum=1)
    _integer(max_byte_count, "journal byte ceiling", minimum=1)
    fd = _open_readonly(path)
    records: list[dict[str, Any]] = []
    torn_tail = False
    try:
        if os.fstat(fd).st_size > max_byte_count:
            raise JournalError("journal artifact exceeds its deterministic byte ceiling")
        with os.fdopen(fd, "rb", closefd=True) as handle:
            consumed = 0
            while True:
                header = handle.read(FRAME_HEADER.size)
                if header == b"":
                    break
                consumed += len(header)
                if consumed > max_byte_count or len(records) >= max_frames:
                    raise JournalError(
                        "journal artifact exceeds its deterministic frame or byte ceiling"
                    )
                if len(header) != FRAME_HEADER.size:
                    if allow_incomplete:
                        torn_tail = True
                        break
                    raise JournalError("journal ends within a frame header")
                try:
                    magic, raw_length, compressed_length, _ = FRAME_HEADER.unpack(header)
                except struct.error as error:
                    raise JournalError("journal frame header is malformed") from error
                if magic != FRAME_MAGIC:
                    raise JournalError("journal frame magic differs")
                if not 1 <= raw_length <= MAX_FRAME_RAW_BYTES:
                    raise JournalError("journal frame raw length exceeds its byte budget")
                if not 1 <= compressed_length <= MAX_FRAME_COMPRESSED_BYTES:
                    raise JournalError(
                        "journal frame compressed length exceeds its byte budget"
                    )
                payload = handle.read(compressed_length)
                consumed += len(payload)
                if consumed > max_byte_count:
                    raise JournalError(
                        "journal artifact exceeds its deterministic byte ceiling"
                    )
                if len(payload) != compressed_length:
                    if allow_incomplete:
                        torn_tail = True
                        break
                    raise JournalError("journal ends within a frame payload")
                records.append(_decode_frame(header, payload))
    except OSError as error:
        raise JournalError("journal artifact could not be read") from error
    return records, torn_tail


def _file_identity(path: Path, *, max_byte_count: int) -> tuple[str, int]:
    _integer(max_byte_count, "journal identity byte ceiling", minimum=1)
    fd = _open_readonly(path)
    digest = hashlib.sha256()
    count = 0
    try:
        if os.fstat(fd).st_size > max_byte_count:
            raise JournalError("journal artifact exceeds its deterministic byte ceiling")
        with os.fdopen(fd, "rb", closefd=True) as handle:
            while True:
                chunk = handle.read(1 << 20)
                if not chunk:
                    break
                digest.update(chunk)
                count += len(chunk)
                if count > max_byte_count:
                    raise JournalError(
                        "journal artifact exceeds its deterministic byte ceiling"
                    )
    except OSError as error:
        raise JournalError("journal artifact identity could not be read") from error
    return digest.hexdigest(), count


def _write_all(fd: int, raw: bytes) -> None:
    view = memoryview(raw)
    while view:
        try:
            written = os.write(fd, view)
        except InterruptedError:
            continue
        except OSError as error:
            raise JournalError("journal frame write failed") from error
        if written <= 0:
            raise JournalError("journal frame write made no progress")
        view = view[written:]


def _sync_fd(fd: int) -> None:
    try:
        if hasattr(os, "fdatasync"):
            os.fdatasync(fd)
        else:  # pragma: no cover - all supported evaluation platforms have it.
            os.fsync(fd)
    except OSError as error:
        raise JournalError("journal durability sync failed") from error


def _sync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise JournalError("journal directory cannot be opened for durability") from error
    os.set_inheritable(fd, False)
    try:
        os.fsync(fd)
    except OSError as error:
        raise JournalError("journal directory durability sync failed") from error
    finally:
        os.close(fd)


def _create_append_file(path: Path) -> int:
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise JournalError("journal artifact already exists; attempt is quarantined") from error
    except OSError as error:
        raise JournalError("journal artifact could not be created exclusively") from error
    os.set_inheritable(fd, False)
    return fd


def _write_single_record(path: Path, record: Mapping[str, Any]) -> None:
    fd = _create_append_file(path)
    try:
        _write_all(fd, _encode_frame(record))
        _sync_fd(fd)
    finally:
        os.close(fd)
    _sync_directory(path.parent)


def _read_single_record(
    path: Path, *, allow_incomplete: bool
) -> tuple[dict[str, Any] | None, bool]:
    records, torn = _read_frames(
        path,
        allow_incomplete=allow_incomplete,
        max_frames=1,
        max_byte_count=MAX_ENCODED_FRAME_BYTES,
    )
    if len(records) > 1:
        raise JournalError("single-record journal artifact has trailing records")
    if not records:
        if torn and allow_incomplete:
            return None, True
        raise JournalError("single-record journal artifact is empty")
    return records[0], torn


def _read_first_frame(path: Path) -> dict[str, Any]:
    """Read only a segment's bounded first frame to derive later ceilings."""

    fd = _open_readonly(path)
    try:
        with os.fdopen(fd, "rb", closefd=True) as handle:
            header = handle.read(FRAME_HEADER.size)
            if len(header) != FRAME_HEADER.size:
                raise JournalError("lineage segment has no complete open frame")
            try:
                magic, raw_length, compressed_length, _ = FRAME_HEADER.unpack(
                    header
                )
            except struct.error as error:
                raise JournalError("journal frame header is malformed") from error
            if magic != FRAME_MAGIC:
                raise JournalError("journal frame magic differs")
            if not 1 <= raw_length <= MAX_FRAME_RAW_BYTES:
                raise JournalError("journal frame raw length exceeds its byte budget")
            if not 1 <= compressed_length <= MAX_FRAME_COMPRESSED_BYTES:
                raise JournalError(
                    "journal frame compressed length exceeds its byte budget"
                )
            payload = handle.read(compressed_length)
            if len(payload) != compressed_length:
                raise JournalError("lineage segment has no complete open frame")
    except OSError as error:
        raise JournalError("lineage segment open frame could not be read") from error
    return _decode_frame(header, payload)


def _validate_receipt(value: object, expected_kind: str) -> dict[str, Any]:
    receipt = _exact_dict(value, _RECEIPT_KEYS, f"{expected_kind} receipt")
    _base_identity(receipt)
    if receipt["kind"] != expected_kind:
        raise JournalError("receipt kind differs from its journal position")
    context = _exact_dict(receipt["context"], _CONTEXT_KEYS, "receipt context")
    _digest(context["case_id"], "receipt case")
    for name in ("lineage_id", "branch_id"):
        if context[name] is not None:
            _digest(context[name], f"receipt {name}")
    for name in ("encounter_index", "episode_index"):
        if context[name] is not None:
            _integer(context[name], f"receipt {name}")
    if type(receipt["payload"]) is not dict:
        raise JournalError("receipt payload is not a dictionary")
    parents = receipt["parents"]
    if type(parents) is not list:
        raise JournalError("receipt parents are not a list")
    for parent in parents:
        item = _exact_dict(parent, _PARENT_KEYS, "receipt parent")
        _digest(item["receipt_sha256"], "parent receipt")
        if type(item["role"]) is not str or not 1 <= len(item["role"]) <= 80:
            raise JournalError("receipt parent role is malformed")
    claimed = _digest(receipt["receipt_sha256"], "receipt")
    body = {key: receipt[key] for key in receipt if key != "receipt_sha256"}
    if claimed != sha256_bytes(canonical_json(body)):
        raise JournalError("receipt content identity differs")
    return receipt


def _validate_prefix_extension(
    receipt_ids: set[str], receipts: Sequence[dict[str, Any]]
) -> tuple[str, ...]:
    """Validate only newly appended receipts against an exact accepted prefix.

    ``receipt_ids`` is the writer or reader's authoritative index of the
    already-validated prefix.  This function never mutates it: callers may
    durably append a frame before committing the returned identities to their
    in-memory index.  Parents may name earlier receipts in the same extension,
    preserving the exact ordered-graph semantics of a full-prefix scan.
    """

    additions: list[str] = []
    addition_ids: set[str] = set()
    for receipt in receipts:
        digest = receipt["receipt_sha256"]
        if digest in receipt_ids or digest in addition_ids:
            raise JournalError("journal receipt identity is duplicated")
        for parent in receipt["parents"]:
            parent_digest = parent["receipt_sha256"]
            if parent_digest not in receipt_ids and parent_digest not in addition_ids:
                raise JournalError(
                    "journal receipt parent is absent from its causal prefix"
                )
        addition_ids.add(digest)
        additions.append(digest)
    return tuple(additions)


def _validate_prefix_graph(receipts: Sequence[dict[str, Any]]) -> None:
    _validate_prefix_extension(set(), receipts)


def _validate_common_context(
    receipt: dict[str, Any],
    *,
    case_id: str,
    lineage_id: str,
    branch_id: str,
) -> None:
    context = receipt["context"]
    if (
        context["case_id"] != case_id
        or context["lineage_id"] != lineage_id
        or context["branch_id"] != branch_id
    ):
        raise JournalError("receipt lineage context differs from the segment")


def _validate_stage_counts(value: object, *, expected: bool) -> dict[str, Any]:
    counts = _exact_dict(value, set(SCOPES), "stage scope counts")
    item_keys = {"encounters", "segments"} if expected else {
        "encounters",
        "receipts",
        "segments",
    }
    result: dict[str, Any] = {}
    for scope in SCOPES:
        item = _exact_dict(counts[scope], item_keys, "stage scope count")
        checked = {
            "encounters": _integer(item["encounters"], "scope encounter count"),
            "segments": _integer(item["segments"], "scope segment count"),
        }
        if not expected:
            checked["receipts"] = _integer(item["receipts"], "scope receipt count")
        result[scope] = checked
    return result


def _validate_stage_open(value: object) -> dict[str, Any]:
    record = _exact_dict(value, _STAGE_OPEN_KEYS, "stage-open record")
    _base_identity(record)
    if record["record_kind"] != "stage-open" or record["journal_format"] != JOURNAL_FORMAT:
        raise JournalError("stage-open record identity differs")
    _safe_id(record["run_id"], "run id")
    if record["purpose"] not in {"design", "anchor"}:
        raise JournalError("journal purpose is unavailable")
    _digest(record["task_sha256"], "task")
    _commit(record["execution_git_commit"])
    _logical_path(record["logical_path"])
    _integer(record["expected_case_count"], "expected case count", minimum=1)
    counts = _validate_stage_counts(record["expected_scope_counts"], expected=True)
    total_segments = sum(item["segments"] for item in counts.values())
    total_encounters = sum(item["encounters"] for item in counts.values())
    if (
        total_segments > MAX_STAGE_SEGMENTS
        or total_encounters > MAX_STAGE_ENCOUNTERS
        or any(
            (item["segments"] == 0) != (item["encounters"] == 0)
            or item["encounters"] < item["segments"]
            for item in counts.values()
        )
    ):
        raise JournalError("expected stage scope counts exceed journal ceilings")
    return record


def _segment_filename(
    *, scope: str, case_index: int, condition_id: str, branch_id: str
) -> str:
    if case_index > 999_999:
        raise JournalError("case index exceeds its filename budget")
    return (
        f"{_SCOPE_ORDINAL[scope]:02d}-{case_index:06d}-"
        f"{condition_id}-{branch_id}.otj"
    )


def _validate_lineage_open(value: object) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    record = _exact_dict(value, _LINEAGE_OPEN_KEYS, "lineage-open record")
    _base_identity(record)
    if record["record_kind"] != "lineage-open" or record["journal_format"] != JOURNAL_FORMAT:
        raise JournalError("lineage-open record identity differs")
    _safe_id(record["run_id"], "run id")
    if record["purpose"] not in {"design", "anchor"}:
        raise JournalError("journal purpose is unavailable")
    task_sha = _digest(record["task_sha256"], "task")
    _commit(record["execution_git_commit"])
    _scope(record["scope"])
    case_id = _digest(record["case_id"], "case")
    case_index = _integer(record["case_index"], "case index")
    condition_id = _digest(record["condition_id"], "condition")
    lineage_id = _digest(record["lineage_id"], "lineage")
    branch_id = _digest(record["branch_id"], "branch")
    encounter_start = _integer(record["encounter_start"], "encounter start")
    encounter_count = _integer(record["encounter_count"], "encounter count", minimum=1)
    raw_receipts = record["initial_receipts"]
    if type(raw_receipts) is not list or len(raw_receipts) != len(_ROOT_RECEIPT_KINDS):
        raise JournalError("lineage-open must contain exactly five root receipts")
    receipts = [
        _validate_receipt(raw, kind)
        for raw, kind in zip(raw_receipts, _ROOT_RECEIPT_KINDS, strict=True)
    ]
    case = receipts[0]
    if (
        case["context"]
        != {
            "branch_id": None,
            "case_id": case_id,
            "encounter_index": None,
            "episode_index": None,
            "lineage_id": None,
        }
        or case["payload"].get("case_index") != case_index
        or case["payload"].get("task_sha256") != task_sha
    ):
        raise JournalError("case root differs from lineage-open metadata")
    for receipt in receipts[1:4]:
        _validate_common_context(
            receipt, case_id=case_id, lineage_id=lineage_id, branch_id=branch_id
        )
        if receipt["context"]["encounter_index"] is not None:
            raise JournalError("nonprojection root has an encounter context")
    projection = receipts[4]
    _validate_common_context(
        projection, case_id=case_id, lineage_id=lineage_id, branch_id=branch_id
    )
    if projection["context"]["encounter_index"] != encounter_start:
        raise JournalError("initial projection target differs from encounter start")
    lineage_payload = receipts[2]["payload"]
    if (
        lineage_payload.get("condition_id") != condition_id
        or lineage_payload.get("lineage_id") != lineage_id
        or lineage_payload.get("branch_id") != branch_id
        or lineage_payload.get("encounter_start") != encounter_start
    ):
        raise JournalError("lineage root differs from lineage-open metadata")
    horizon = case["payload"].get("horizon")
    if type(horizon) is not int or encounter_start + encounter_count != horizon:
        raise JournalError("segment encounter range differs from the case horizon")
    _validate_prefix_graph(receipts)
    return record, receipts


def _validate_checkpoint(
    value: object,
    *,
    opened: dict[str, Any],
    expected_encounter: int | None,
    expected_mode: str,
) -> dict[str, Any]:
    record = _exact_dict(value, _CHECKPOINT_KEYS, "consumer-checkpoint record")
    _base_identity(record)
    if record["record_kind"] != "consumer-checkpoint":
        raise JournalError("consumer checkpoint kind differs")
    for name in ("scope", "case_id", "condition_id", "lineage_id", "branch_id"):
        if record[name] != opened[name]:
            raise JournalError("consumer checkpoint identity differs from the segment")
    if record["encounter_index"] != expected_encounter or record["mode"] != expected_mode:
        raise JournalError("consumer checkpoint is in the wrong causal slot")
    receipt = _validate_receipt(record["receipt"], "consumer")
    _validate_common_context(
        receipt,
        case_id=opened["case_id"],
        lineage_id=opened["lineage_id"],
        branch_id=opened["branch_id"],
    )
    if (
        receipt["context"]["encounter_index"] != expected_encounter
        or receipt["payload"].get("mode") != expected_mode
        or receipt["payload"].get("target_encounter_index") != expected_encounter
    ):
        raise JournalError("consumer receipt differs from its checkpoint slot")
    return receipt


def _validate_encounter_commit(
    value: object,
    *,
    opened: dict[str, Any],
    expected_encounter: int,
) -> list[dict[str, Any]]:
    record = _exact_dict(value, _ENCOUNTER_COMMIT_KEYS, "encounter-commit record")
    _base_identity(record)
    if record["record_kind"] != "encounter-commit":
        raise JournalError("encounter commit kind differs")
    for name in ("scope", "case_id", "condition_id", "lineage_id", "branch_id"):
        if record[name] != opened[name]:
            raise JournalError("encounter commit identity differs from the segment")
    if record["encounter_index"] != expected_encounter or record["receipt_count"] != 8:
        raise JournalError("encounter commit count or index differs")
    raw_receipts = record["receipts"]
    if type(raw_receipts) is not list or len(raw_receipts) != 8:
        raise JournalError("encounter commit must contain exactly eight receipts")
    receipts = [
        _validate_receipt(raw, kind)
        for raw, kind in zip(raw_receipts, _ENCOUNTER_RECEIPT_KINDS, strict=True)
    ]
    for receipt in receipts:
        _validate_common_context(
            receipt,
            case_id=opened["case_id"],
            lineage_id=opened["lineage_id"],
            branch_id=opened["branch_id"],
        )
    for receipt in receipts[:-1]:
        if receipt["context"]["encounter_index"] != expected_encounter:
            raise JournalError("encounter receipt index differs from its commit")
    terminal = expected_encounter == (
        opened["encounter_start"] + opened["encounter_count"] - 1
    )
    expected_projection_target = None if terminal else expected_encounter + 1
    if receipts[-1]["context"]["encounter_index"] != expected_projection_target:
        raise JournalError("projection target differs from encounter completion")
    return receipts


def _chain_from_seal(
    opened: dict[str, Any], receipts: Sequence[dict[str, Any]], seal: object
) -> dict[str, Any]:
    record = _exact_dict(seal, _LINEAGE_SEAL_KEYS, "lineage-seal record")
    _base_identity(record)
    if record["record_kind"] != "lineage-seal":
        raise JournalError("lineage seal kind differs")
    for name in ("scope", "case_id", "condition_id", "lineage_id", "branch_id"):
        if record[name] != opened[name]:
            raise JournalError("lineage seal identity differs from the segment")
    if (
        record["encounter_start"] != opened["encounter_start"]
        or record["encounter_count"] != opened["encounter_count"]
        or record["receipt_order_sha256"]
        != sha256_bytes(canonical_json(list(receipts)))
    ):
        raise JournalError("lineage seal range or receipt identity differs")
    chain = {
        "case_receipt_sha256": record["case_receipt_sha256"],
        "encounter_count": record["encounter_count"],
        "encounter_start": record["encounter_start"],
        "experiment_id": EXPERIMENT_ID,
        "lineage_receipt_sha256": record["lineage_receipt_sha256"],
        "receipt_order": copy.deepcopy(list(receipts)),
        "schema_version": SCHEMA_VERSION,
        "summary": copy.deepcopy(record["summary"]),
        "terminal_audit_receipt_sha256": record[
            "terminal_audit_receipt_sha256"
        ],
        "trace_sha256": record["trace_sha256"],
    }
    try:
        validation = validate_chain(chain)
    except ValueError as error:
        raise JournalError("sealed lineage receipt chain is invalid") from error
    if (
        validation.case_id != opened["case_id"]
        or validation.lineage_id != opened["lineage_id"]
        or validation.branch_id != opened["branch_id"]
        or validation.encounter_start != opened["encounter_start"]
        or validation.encounter_count != opened["encounter_count"]
        or validation.trace_sha256 != record["trace_sha256"]
    ):
        raise JournalError("sealed lineage validation differs from segment metadata")
    return chain


def _validate_segment_records(
    records: Sequence[dict[str, Any]], *, require_seal: bool
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, int]:
    if not records:
        raise JournalError("lineage segment has no open record")
    opened, receipts = _validate_lineage_open(records[0])
    receipt_ids = {receipt["receipt_sha256"] for receipt in receipts}
    next_encounter = opened["encounter_start"]
    end = next_encounter + opened["encounter_count"]
    has_consumer = False
    chain: dict[str, Any] | None = None
    completed = 0
    for index, record in enumerate(records[1:], start=1):
        kind = record.get("record_kind") if type(record) is dict else None
        if chain is not None:
            raise JournalError("lineage segment has records after its seal")
        if kind == "consumer-checkpoint":
            if has_consumer:
                raise JournalError("lineage segment duplicates a consumer checkpoint")
            expected_index = next_encounter if next_encounter < end else None
            expected_mode = "prediction" if next_encounter < end else "terminal-audit"
            consumer = _validate_checkpoint(
                record,
                opened=opened,
                expected_encounter=expected_index,
                expected_mode=expected_mode,
            )
            additions = _validate_prefix_extension(receipt_ids, (consumer,))
            receipts.append(consumer)
            receipt_ids.update(additions)
            has_consumer = True
        elif kind == "encounter-commit":
            if not has_consumer or next_encounter >= end:
                raise JournalError("encounter commit has no preceding consumer slot")
            committed = _validate_encounter_commit(
                record, opened=opened, expected_encounter=next_encounter
            )
            additions = _validate_prefix_extension(receipt_ids, committed)
            receipts.extend(committed)
            receipt_ids.update(additions)
            next_encounter += 1
            completed += 1
            has_consumer = False
        elif kind == "lineage-seal":
            if index != len(records) - 1:
                raise JournalError("lineage seal is not the final record")
            if next_encounter != end or not has_consumer:
                raise JournalError("lineage seal precedes the terminal consumer")
            chain = _chain_from_seal(opened, receipts, record)
        else:
            raise JournalError("lineage segment record kind is unavailable")
    if require_seal and chain is None:
        raise JournalError("lineage segment is unsealed")
    return receipts, chain, completed


def read_segment(
    path: str | os.PathLike[str],
    *,
    allow_incomplete: bool = False,
    _maximum_encounter_count: int | None = None,
) -> SegmentRead:
    """Read and validate a segment, optionally retaining an incomplete prefix.

    ``allow_incomplete`` tolerates only an absent seal or a physically torn last
    frame.  Any fully written malformed frame, invalid receipt, bad ordering,
    or record after a seal remains a hard error.
    """

    target = Path(path)
    first = _read_first_frame(target)
    opened, _ = _validate_lineage_open(first)
    encounter_ceiling = (
        MAX_SEGMENT_ENCOUNTERS
        if _maximum_encounter_count is None
        else _integer(
            _maximum_encounter_count,
            "stage encounter ceiling",
            minimum=1,
        )
    )
    if opened["encounter_count"] > encounter_ceiling:
        raise JournalError("lineage segment exceeds its stage encounter ceiling")
    max_frames = 2 * opened["encounter_count"] + 3
    max_byte_count = max_frames * MAX_ENCODED_FRAME_BYTES
    records, torn = _read_frames(
        target,
        allow_incomplete=allow_incomplete,
        max_frames=max_frames,
        max_byte_count=max_byte_count,
    )
    receipts, chain, completed = _validate_segment_records(
        records, require_seal=not allow_incomplete
    )
    file_sha256, byte_count = _file_identity(
        target, max_byte_count=max_byte_count
    )
    return SegmentRead(
        records=tuple(copy.deepcopy(records)),
        receipt_order=tuple(copy.deepcopy(receipts)),
        chain=copy.deepcopy(chain),
        sealed=chain is not None,
        torn_tail=torn,
        completed_encounter_count=completed,
        file_sha256=file_sha256,
        byte_count=byte_count,
    )


def reassemble_chain(segment: SegmentRead) -> dict[str, Any]:
    """Return the exact validated chain represented by a sealed segment."""

    if type(segment) is not SegmentRead or not segment.sealed or segment.chain is None:
        raise JournalError("an unsealed segment has no complete receipt chain")
    return copy.deepcopy(segment.chain)


class LineageSegmentWriter:
    """Exclusive append-only writer for one sequential lineage."""

    def __init__(self, path: Path, open_record: dict[str, Any]) -> None:
        opened, receipts = _validate_lineage_open(open_record)
        self._path = path
        self._opened = copy.deepcopy(opened)
        self._receipts = copy.deepcopy(receipts)
        self._receipt_ids = {receipt["receipt_sha256"] for receipt in receipts}
        self._next_encounter = opened["encounter_start"]
        self._end = self._next_encounter + opened["encounter_count"]
        self._has_consumer = False
        self._sealed = False
        self._closed = False
        self._lock = threading.Lock()
        self._fd = _create_append_file(path)
        try:
            self._append_record(open_record)
            _sync_directory(path.parent)
        except BaseException:
            os.close(self._fd)
            self._closed = True
            raise

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def closed(self) -> bool:
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise JournalError("lineage segment writer is closed")
        if self._sealed:
            raise JournalError("lineage segment is already sealed")

    def _append_record(self, record: Mapping[str, Any]) -> None:
        _write_all(self._fd, _encode_frame(record))
        _sync_fd(self._fd)

    def append_consumer(self, receipt: Mapping[str, Any]) -> None:
        """Durably append the consumer receipt for the current causal slot."""

        with self._lock:
            self._ensure_open()
            if self._has_consumer:
                raise JournalError("current segment slot already has a consumer")
            encounter_index = (
                self._next_encounter if self._next_encounter < self._end else None
            )
            mode = (
                "prediction" if self._next_encounter < self._end else "terminal-audit"
            )
            record = {
                "branch_id": self._opened["branch_id"],
                "case_id": self._opened["case_id"],
                "condition_id": self._opened["condition_id"],
                "encounter_index": encounter_index,
                "experiment_id": EXPERIMENT_ID,
                "lineage_id": self._opened["lineage_id"],
                "mode": mode,
                "receipt": _copy_dict(receipt),
                "record_kind": "consumer-checkpoint",
                "schema_version": SCHEMA_VERSION,
                "scope": self._opened["scope"],
            }
            checked = _validate_checkpoint(
                record,
                opened=self._opened,
                expected_encounter=encounter_index,
                expected_mode=mode,
            )
            additions = _validate_prefix_extension(self._receipt_ids, (checked,))
            self._append_record(record)
            self._receipts.append(checked)
            self._receipt_ids.update(additions)
            self._has_consumer = True

    def append_encounter(
        self, encounter_index: int, receipts: Sequence[Mapping[str, Any]]
    ) -> None:
        """Durably commit eight receipts through the encounter's projection."""

        with self._lock:
            self._ensure_open()
            if not self._has_consumer:
                raise JournalError("encounter has no durable consumer checkpoint")
            if encounter_index != self._next_encounter or encounter_index >= self._end:
                raise JournalError("encounter commit is out of sequence")
            copied = [_copy_dict(receipt) for receipt in receipts]
            record = {
                "branch_id": self._opened["branch_id"],
                "case_id": self._opened["case_id"],
                "condition_id": self._opened["condition_id"],
                "encounter_index": encounter_index,
                "experiment_id": EXPERIMENT_ID,
                "lineage_id": self._opened["lineage_id"],
                "receipt_count": len(copied),
                "receipts": copied,
                "record_kind": "encounter-commit",
                "schema_version": SCHEMA_VERSION,
                "scope": self._opened["scope"],
            }
            checked = _validate_encounter_commit(
                record, opened=self._opened, expected_encounter=self._next_encounter
            )
            additions = _validate_prefix_extension(self._receipt_ids, checked)
            self._append_record(record)
            self._receipts.extend(checked)
            self._receipt_ids.update(additions)
            self._next_encounter += 1
            self._has_consumer = False

    def seal(self, chain: Mapping[str, Any]) -> dict[str, Any]:
        """Validate, durably seal, and close this lineage segment."""

        with self._lock:
            self._ensure_open()
            if self._next_encounter != self._end or not self._has_consumer:
                raise JournalError("lineage cannot seal before its terminal consumer")
            if type(chain) is not dict:
                raise JournalError("lineage chain must be a dictionary")
            supplied_receipts = chain.get("receipt_order")
            if (
                type(supplied_receipts) is not list
                or canonical_json(supplied_receipts) != canonical_json(self._receipts)
            ):
                raise JournalError("lineage chain differs from durable receipt order")
            try:
                validation = validate_chain(chain)
            except ValueError as error:
                raise JournalError("lineage chain is invalid") from error
            if (
                validation.case_id != self._opened["case_id"]
                or validation.lineage_id != self._opened["lineage_id"]
                or validation.branch_id != self._opened["branch_id"]
            ):
                raise JournalError("lineage chain identity differs from its segment")
            record = {
                "branch_id": self._opened["branch_id"],
                "case_id": self._opened["case_id"],
                "case_receipt_sha256": chain["case_receipt_sha256"],
                "condition_id": self._opened["condition_id"],
                "encounter_count": self._opened["encounter_count"],
                "encounter_start": self._opened["encounter_start"],
                "experiment_id": EXPERIMENT_ID,
                "lineage_id": self._opened["lineage_id"],
                "lineage_receipt_sha256": chain["lineage_receipt_sha256"],
                "receipt_order_sha256": sha256_bytes(
                    canonical_json(self._receipts)
                ),
                "record_kind": "lineage-seal",
                "schema_version": SCHEMA_VERSION,
                "scope": self._opened["scope"],
                "summary": copy.deepcopy(chain["summary"]),
                "terminal_audit_receipt_sha256": chain[
                    "terminal_audit_receipt_sha256"
                ],
                "trace_sha256": chain["trace_sha256"],
            }
            rebuilt = _chain_from_seal(self._opened, self._receipts, record)
            if canonical_json(rebuilt) != canonical_json(chain):
                raise JournalError("lineage seal does not reconstruct the supplied chain")
            self._append_record(record)
            self._sealed = True
            try:
                os.fchmod(self._fd, 0o400)
                _sync_fd(self._fd)
            except BaseException:
                self._closed = True
                os.close(self._fd)
                raise
            self._closed = True
            os.close(self._fd)
            return copy.deepcopy(record)

    def abort(self) -> None:
        """Close without a seal; already-synced prefix frames remain retained."""

        with self._lock:
            if not self._closed:
                self._closed = True
                os.close(self._fd)

    def __del__(self) -> None:
        """Best-effort descriptor close; synced prefix frames remain untouched."""

        try:
            if not getattr(self, "_closed", True):
                self._closed = True
                os.close(self._fd)
        except BaseException:
            pass

    def __enter__(self) -> LineageSegmentWriter:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if not self._closed:
            self.abort()


def _segment_identity(relative_path: str, segment: SegmentRead) -> dict[str, Any]:
    if not segment.sealed or segment.chain is None:
        raise JournalError("unsealed segment has no stage identity")
    opened = segment.open_record
    identity = {
        "branch_id": opened["branch_id"],
        "byte_count": segment.byte_count,
        "case_id": opened["case_id"],
        "case_index": opened["case_index"],
        "completed_encounter_count": segment.completed_encounter_count,
        "condition_id": opened["condition_id"],
        "encounter_count": opened["encounter_count"],
        "encounter_start": opened["encounter_start"],
        "file_sha256": segment.file_sha256,
        "lineage_id": opened["lineage_id"],
        "receipt_count": len(segment.receipt_order),
        "relative_path": relative_path,
        "scope": opened["scope"],
        "trace_sha256": segment.chain["trace_sha256"],
    }
    _exact_dict(identity, _SEGMENT_IDENTITY_KEYS, "segment identity")
    return identity


def _stage_actual_counts(identities: Sequence[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        scope: {"encounters": 0, "receipts": 0, "segments": 0}
        for scope in SCOPES
    }
    for identity in identities:
        item = counts[identity["scope"]]
        item["segments"] += 1
        item["encounters"] += identity["completed_encounter_count"]
        item["receipts"] += identity["receipt_count"]
    return counts


def _stage_binding(seal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "completed_encounter_count": seal["completed_encounter_count"],
        "execution_git_commit": seal["execution_git_commit"],
        "journal_format": seal["journal_format"],
        "journal_sha256": seal["journal_sha256"],
        "logical_path": seal["logical_path"],
        "purpose": seal["purpose"],
        "receipt_count": seal["receipt_count"],
        "schema_version": seal["schema_version"],
        "scope_counts": copy.deepcopy(seal["scope_counts"]),
        "scientific_sha256": seal["scientific_sha256"],
        "sealed": True,
        "segment_count": seal["segment_count"],
        "segment_index_sha256": seal["segment_index_sha256"],
        "stage_open_sha256": seal["stage_open_sha256"],
        "task_sha256": seal["task_sha256"],
    }


def _build_stage_seal(
    opened: Mapping[str, Any],
    *,
    scientific_sha256: str,
    stage_open_sha256: str,
    identities: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    ordered = copy.deepcopy(sorted(identities, key=lambda item: item["relative_path"]))
    counts = _stage_actual_counts(ordered)
    body = {
        "completed_encounter_count": sum(
            item["completed_encounter_count"] for item in ordered
        ),
        "execution_git_commit": opened["execution_git_commit"],
        "experiment_id": EXPERIMENT_ID,
        "journal_format": JOURNAL_FORMAT,
        "logical_path": opened["logical_path"],
        "purpose": opened["purpose"],
        "receipt_count": sum(item["receipt_count"] for item in ordered),
        "record_kind": "stage-seal",
        "run_id": opened["run_id"],
        "schema_version": SCHEMA_VERSION,
        "scope_counts": counts,
        "scientific_sha256": scientific_sha256,
        "segment_count": len(ordered),
        "segment_index_sha256": sha256_bytes(canonical_json(ordered)),
        "segments": ordered,
        "stage_open_sha256": stage_open_sha256,
        "task_sha256": opened["task_sha256"],
    }
    return {**body, "journal_sha256": sha256_bytes(canonical_json(body))}


def _validate_segment_identity(value: object) -> dict[str, Any]:
    item = _exact_dict(value, _SEGMENT_IDENTITY_KEYS, "segment identity")
    _scope(item["scope"])
    _digest(item["case_id"], "segment case")
    _digest(item["condition_id"], "segment condition")
    _digest(item["lineage_id"], "segment lineage")
    _digest(item["branch_id"], "segment branch")
    _digest(item["file_sha256"], "segment file")
    _digest(item["trace_sha256"], "segment trace")
    _integer(item["case_index"], "segment case index")
    _integer(item["encounter_start"], "segment encounter start")
    _integer(item["encounter_count"], "segment encounter count", minimum=1)
    _integer(
        item["completed_encounter_count"], "segment completed encounter count"
    )
    _integer(item["receipt_count"], "segment receipt count", minimum=1)
    _integer(item["byte_count"], "segment byte count", minimum=1)
    expected = (
        f"{SEGMENT_DIRECTORY_NAME}/"
        + _segment_filename(
            scope=item["scope"],
            case_index=item["case_index"],
            condition_id=item["condition_id"],
            branch_id=item["branch_id"],
        )
    )
    if item["relative_path"] != expected:
        raise JournalError("segment identity relative path differs")
    return item


def _validate_stage_seal(value: object) -> dict[str, Any]:
    record = _exact_dict(value, _STAGE_SEAL_KEYS, "stage-seal record")
    _base_identity(record)
    if record["record_kind"] != "stage-seal" or record["journal_format"] != JOURNAL_FORMAT:
        raise JournalError("stage-seal record identity differs")
    _safe_id(record["run_id"], "run id")
    if record["purpose"] not in {"design", "anchor"}:
        raise JournalError("journal purpose is unavailable")
    _digest(record["task_sha256"], "task")
    _commit(record["execution_git_commit"])
    _logical_path(record["logical_path"])
    for name in (
        "scientific_sha256",
        "stage_open_sha256",
        "segment_index_sha256",
        "journal_sha256",
    ):
        _digest(record[name], name)
    for name in (
        "segment_count",
        "completed_encounter_count",
        "receipt_count",
    ):
        _integer(record[name], name)
    _validate_stage_counts(record["scope_counts"], expected=False)
    if type(record["segments"]) is not list:
        raise JournalError("stage segment index is not a list")
    for identity in record["segments"]:
        _validate_segment_identity(identity)
    if record["segments"] != sorted(
        record["segments"], key=lambda item: item["relative_path"]
    ):
        raise JournalError("stage segment index is not in canonical order")
    body = {key: record[key] for key in record if key != "journal_sha256"}
    if record["journal_sha256"] != sha256_bytes(canonical_json(body)):
        raise JournalError("stage journal identity differs")
    return record


def _ensure_real_directory(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise JournalError(f"{label} is unavailable") from error
    if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
        raise JournalError(f"{label} is not a real directory")


def _stage_layout(root: Path) -> tuple[Path, Path, Path]:
    _ensure_real_directory(root, "journal root")
    stage_open = root / STAGE_OPEN_NAME
    segments = root / SEGMENT_DIRECTORY_NAME
    stage_seal = root / STAGE_SEAL_NAME
    _ensure_real_directory(segments, "journal segment directory")
    try:
        names = {entry.name for entry in root.iterdir()}
    except OSError as error:
        raise JournalError("journal root cannot be enumerated") from error
    allowed = {STAGE_OPEN_NAME, SEGMENT_DIRECTORY_NAME, STAGE_SEAL_NAME}
    if STAGE_OPEN_NAME not in names or not names <= allowed:
        raise JournalError("journal root layout contains an unexpected artifact")
    for candidate, label in (
        (stage_open, "stage-open artifact"),
        (stage_seal, "stage-seal artifact"),
    ):
        if candidate.name not in names:
            continue
        try:
            mode = candidate.lstat().st_mode
        except OSError as error:
            raise JournalError(f"{label} is unavailable") from error
        if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
            raise JournalError(f"{label} is not a regular file")
    return stage_open, segments, stage_seal


@contextmanager
def _stage_file_lock(stage_open_path: Path, *, exclusive: bool) -> Iterator[None]:
    fd = _open_readonly(stage_open_path)
    try:
        if fcntl is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            except OSError as error:
                raise JournalError("stage journal lock could not be acquired") from error
        yield
    finally:
        if fcntl is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)


def _read_segment_directory(
    segments_path: Path,
    *,
    stage_open: Mapping[str, Any],
    allow_incomplete: bool,
) -> tuple[list[str], list[SegmentRead]]:
    expected = stage_open["expected_scope_counts"]
    expected_segment_count = sum(item["segments"] for item in expected.values())
    expected_segment_bytes = sum(
        (2 * item["encounters"] + 3 * item["segments"])
        * MAX_ENCODED_FRAME_BYTES
        for item in expected.values()
    )
    entries: list[Path] = []
    try:
        with os.scandir(segments_path) as iterator:
            for entry in iterator:
                if len(entries) >= expected_segment_count:
                    raise JournalError(
                        "journal segment directory exceeds its stage entry ceiling"
                    )
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    raise JournalError(
                        "journal segment directory has an unexpected entry"
                    )
                if _SEGMENT_NAME.fullmatch(entry.name) is None:
                    raise JournalError(
                        "journal segment directory has an unexpected entry"
                    )
                entries.append(segments_path / entry.name)
    except OSError as error:
        raise JournalError("journal segment directory cannot be enumerated") from error
    entries.sort(key=lambda path: path.name)
    relative_paths: list[str] = []
    segments: list[SegmentRead] = []
    observed_bytes = 0
    for path in entries:
        match = _SEGMENT_NAME.fullmatch(path.name)
        if match is None:  # Already checked before any segment content was read.
            raise JournalError("journal segment filename is malformed")
        ordinal = int(match.group("ordinal"))
        if not 0 <= ordinal < len(SCOPES):
            raise JournalError("journal segment scope ordinal is unavailable")
        filename_scope = SCOPES[ordinal]
        scope_encounter_ceiling = expected[filename_scope]["encounters"]
        if scope_encounter_ceiling < 1:
            raise JournalError("journal segment exists in an unallocated scope")
        segment = read_segment(
            path,
            allow_incomplete=allow_incomplete,
            _maximum_encounter_count=scope_encounter_ceiling,
        )
        observed_bytes += segment.byte_count
        if observed_bytes > expected_segment_bytes:
            raise JournalError("journal segments exceed their stage byte ceiling")
        opened = segment.open_record
        if opened["scope"] != filename_scope:
            raise JournalError("lineage segment scope differs from its filename")
        for name in (
            "run_id",
            "purpose",
            "task_sha256",
            "execution_git_commit",
        ):
            if opened[name] != stage_open[name]:
                raise JournalError("lineage segment differs from stage identity")
        expected_name = _segment_filename(
            scope=opened["scope"],
            case_index=opened["case_index"],
            condition_id=opened["condition_id"],
            branch_id=opened["branch_id"],
        )
        if path.name != expected_name:
            raise JournalError("lineage segment filename differs from its metadata")
        relative_paths.append(f"{SEGMENT_DIRECTORY_NAME}/{path.name}")
        segments.append(segment)
    return relative_paths, segments


def _verify_expected_stage(
    opened: Mapping[str, Any], identities: Sequence[dict[str, Any]]
) -> None:
    actual = _stage_actual_counts(identities)
    expected = opened["expected_scope_counts"]
    for scope in SCOPES:
        if {
            "segments": actual[scope]["segments"],
            "encounters": actual[scope]["encounters"],
        } != expected[scope]:
            raise JournalError("sealed segment counts differ from stage expectation")
    main_cases = {
        (identity["case_index"], identity["case_id"])
        for identity in identities
        if identity["scope"] == "main"
    }
    by_index = {case_index: case_id for case_index, case_id in main_cases}
    by_id = {case_id: case_index for case_index, case_id in main_cases}
    if (
        len(main_cases) != opened["expected_case_count"]
        or len(by_index) != len(main_cases)
        or len(by_id) != len(main_cases)
    ):
        raise JournalError("main case identities differ from stage expectation")


class SegmentedEncounterJournal:
    """Controller-only stage journal supporting concurrent lineage writers."""

    def __init__(self, root: Path, stage_open: dict[str, Any]) -> None:
        self._root = root
        self._stage_open = copy.deepcopy(stage_open)
        self._thread_lock = threading.Lock()

    @classmethod
    def create(
        cls,
        root: str | os.PathLike[str],
        *,
        run_id: str,
        logical_path: str,
        purpose: str,
        task_sha256: str,
        execution_git_commit: str,
        expected_case_count: int,
        expected_scope_counts: Mapping[str, Mapping[str, int]],
    ) -> SegmentedEncounterJournal:
        """Create a fresh stage root; an existing root is never reused."""

        target = Path(root)
        record = {
            "execution_git_commit": execution_git_commit,
            "expected_case_count": expected_case_count,
            "expected_scope_counts": copy.deepcopy(dict(expected_scope_counts)),
            "experiment_id": EXPERIMENT_ID,
            "journal_format": JOURNAL_FORMAT,
            "logical_path": logical_path,
            "purpose": purpose,
            "record_kind": "stage-open",
            "run_id": run_id,
            "schema_version": SCHEMA_VERSION,
            "task_sha256": task_sha256,
        }
        _validate_stage_open(record)
        try:
            target.mkdir(mode=0o700, parents=False, exist_ok=False)
        except FileExistsError as error:
            raise JournalError("journal root already exists; attempt is quarantined") from error
        except OSError as error:
            raise JournalError("journal root could not be created") from error
        try:
            (target / SEGMENT_DIRECTORY_NAME).mkdir(mode=0o700)
            _write_single_record(target / STAGE_OPEN_NAME, record)
            _sync_directory(target)
            _sync_directory(target.parent)
        except BaseException:
            # The partially created root is retained as failure evidence.
            raise
        return cls(target, record)

    @classmethod
    def open(cls, root: str | os.PathLike[str]) -> SegmentedEncounterJournal:
        """Open an existing unsealed stage from a controller worker."""

        target = Path(root)
        stage_open_path, _, stage_seal_path = _stage_layout(target)
        if stage_seal_path.exists():
            raise JournalError("sealed journal stage cannot accept new segments")
        record, torn = _read_single_record(stage_open_path, allow_incomplete=False)
        if torn or record is None:
            raise JournalError("stage-open artifact is incomplete")
        return cls(target, _validate_stage_open(record))

    @property
    def stage_open(self) -> dict[str, Any]:
        return copy.deepcopy(self._stage_open)

    def open_segment(
        self,
        *,
        scope: str,
        case_id: str,
        case_index: int,
        condition_id: str,
        lineage_id: str,
        branch_id: str,
        encounter_start: int,
        encounter_count: int,
        initial_receipts: Sequence[Mapping[str, Any]],
    ) -> LineageSegmentWriter:
        """Create one deterministic O_EXCL lineage segment."""

        checked_scope = _scope(scope)
        checked_case = _digest(case_id, "case")
        checked_case_index = _integer(case_index, "case index")
        checked_condition = _digest(condition_id, "condition")
        checked_lineage = _digest(lineage_id, "lineage")
        checked_branch = _digest(branch_id, "branch")
        checked_start = _integer(encounter_start, "encounter start")
        checked_count = _integer(encounter_count, "encounter count", minimum=1)
        allocated = self._stage_open["expected_scope_counts"][checked_scope]
        if allocated["segments"] == 0 or checked_count > allocated["encounters"]:
            raise JournalError("lineage segment exceeds its allocated stage scope")
        record = {
            "branch_id": checked_branch,
            "case_id": checked_case,
            "case_index": checked_case_index,
            "condition_id": checked_condition,
            "encounter_count": checked_count,
            "encounter_start": checked_start,
            "execution_git_commit": self._stage_open["execution_git_commit"],
            "experiment_id": EXPERIMENT_ID,
            "initial_receipts": [_copy_dict(item) for item in initial_receipts],
            "journal_format": JOURNAL_FORMAT,
            "lineage_id": checked_lineage,
            "purpose": self._stage_open["purpose"],
            "record_kind": "lineage-open",
            "run_id": self._stage_open["run_id"],
            "schema_version": SCHEMA_VERSION,
            "scope": checked_scope,
            "task_sha256": self._stage_open["task_sha256"],
        }
        _validate_lineage_open(record)
        name = _segment_filename(
            scope=checked_scope,
            case_index=checked_case_index,
            condition_id=checked_condition,
            branch_id=checked_branch,
        )
        stage_open_path, segment_directory, stage_seal_path = _stage_layout(self._root)
        with self._thread_lock, _stage_file_lock(stage_open_path, exclusive=False):
            if stage_seal_path.exists():
                raise JournalError("sealed journal stage cannot accept a segment")
            return LineageSegmentWriter(segment_directory / name, record)

    def seal(self, *, scientific_sha256: str) -> dict[str, Any]:
        """Atomically publish a deterministic binding over all sealed segments."""

        checked_scientific = _digest(scientific_sha256, "scientific payload")
        stage_open_path, segment_directory, stage_seal_path = _stage_layout(self._root)
        with self._thread_lock, _stage_file_lock(stage_open_path, exclusive=True):
            if stage_seal_path.exists():
                raise JournalError("journal stage already has a seal artifact")
            relative_paths, segments = _read_segment_directory(
                segment_directory,
                stage_open=self._stage_open,
                allow_incomplete=False,
            )
            identities = [
                _segment_identity(relative_path, segment)
                for relative_path, segment in zip(
                    relative_paths, segments, strict=True
                )
            ]
            _verify_expected_stage(self._stage_open, identities)
            stage_open_sha256, _ = _file_identity(
                stage_open_path, max_byte_count=MAX_ENCODED_FRAME_BYTES
            )
            seal = _build_stage_seal(
                self._stage_open,
                scientific_sha256=checked_scientific,
                stage_open_sha256=stage_open_sha256,
                identities=identities,
            )
            _validate_stage_seal(seal)
            _write_single_record(stage_seal_path, seal)
            _sync_directory(self._root)
        return _stage_binding(seal)


def read_stage(
    root: str | os.PathLike[str],
    *,
    allow_incomplete: bool = False,
    expected_scientific_sha256: str | None = None,
) -> StageRead:
    """Read a stage and verify its deterministic segment index and binding."""

    target = Path(root)
    stage_open_path, segment_directory, stage_seal_path = _stage_layout(target)
    stage_open, open_torn = _read_single_record(
        stage_open_path, allow_incomplete=allow_incomplete
    )
    if stage_open is None:
        raise JournalError("stage-open artifact has no verified record")
    opened = _validate_stage_open(stage_open)
    seal_exists = stage_seal_path.exists()
    stage_seal: dict[str, Any] | None = None
    seal_torn = False
    if seal_exists:
        raw_seal, seal_torn = _read_single_record(
            stage_seal_path, allow_incomplete=allow_incomplete
        )
        if raw_seal is not None:
            stage_seal = _validate_stage_seal(raw_seal)
    if not allow_incomplete and stage_seal is None:
        raise JournalError("journal stage is unsealed")
    relative_paths, segments = _read_segment_directory(
        segment_directory,
        stage_open=opened,
        allow_incomplete=stage_seal is None and allow_incomplete,
    )
    binding: dict[str, Any] | None = None
    if stage_seal is not None:
        identities = [
            _segment_identity(relative_path, segment)
            for relative_path, segment in zip(relative_paths, segments, strict=True)
        ]
        _verify_expected_stage(opened, identities)
        stage_open_sha256, _ = _file_identity(
            stage_open_path, max_byte_count=MAX_ENCODED_FRAME_BYTES
        )
        expected = _build_stage_seal(
            opened,
            scientific_sha256=stage_seal["scientific_sha256"],
            stage_open_sha256=stage_open_sha256,
            identities=identities,
        )
        if canonical_json(expected) != canonical_json(stage_seal):
            raise JournalError("stage seal differs from reconstructed journal identity")
        if (
            expected_scientific_sha256 is not None
            and _digest(expected_scientific_sha256, "expected scientific payload")
            != stage_seal["scientific_sha256"]
        ):
            raise JournalError("stage seal is bound to a different scientific payload")
        binding = _stage_binding(stage_seal)
    elif expected_scientific_sha256 is not None:
        _digest(expected_scientific_sha256, "expected scientific payload")
    return StageRead(
        stage_open=copy.deepcopy(opened),
        segments=tuple(segments),
        segment_relative_paths=tuple(relative_paths),
        stage_seal=copy.deepcopy(stage_seal),
        binding=copy.deepcopy(binding),
        sealed=stage_seal is not None,
        torn_tail=open_torn or seal_torn or any(item.torn_tail for item in segments),
    )


__all__ = [
    "JOURNAL_FORMAT",
    "JournalError",
    "LineageSegmentWriter",
    "SCOPES",
    "SegmentRead",
    "SegmentedEncounterJournal",
    "StageRead",
    "read_segment",
    "read_stage",
    "reassemble_chain",
]
