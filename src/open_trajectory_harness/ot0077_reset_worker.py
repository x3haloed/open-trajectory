"""One-prediction fresh-process consumer for OT-0077.

The worker receives one public query and one bounded canonical projection
through either a one-exec stdin boundary or a post-fork, child-only bootstrap
pipe.  It has no task loader, outcome, prior response, trajectory store,
filesystem capability in the learner call graph, or evaluator score.  The
small wrapper inspects only its empty current directory and the names (not
values) of its deliberately allowlisted process environment.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

from .ot0077_learning import LearningError, decode_state, encode_state, predict


EXPERIMENT_ID = "OT-0077"
SCHEMA_VERSION = 1
ALLOWED_ENVIRONMENT_NAMES = (
    "LANG",
    "LC_ALL",
    "OT0077_SURFACE",
    "PATH",
    "PYTHONHASHSEED",
    "PYTHONPATH",
    "__CF_USER_TEXT_ENCODING",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_IMPORT_PROCESS_ID = os.getpid()


class WorkerError(ValueError):
    """Raised when a reset envelope is not the exact bounded surface."""


def _canonical_json(value: Any) -> bytes:
    """Encode the reset envelope without importing controller dependencies."""

    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise WorkerError(f"{label} keys differ from the frozen schema")
    return value


def _identity(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise WorkerError(f"{label} is not a lowercase SHA-256 identity")
    return value


def _projection(value: object) -> bytes:
    if type(value) is not str:
        raise WorkerError("projection encoding is not text")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise WorkerError("projection encoding is not RFC 4648 base64") from error
    if base64.b64encode(raw).decode("ascii") != value:
        raise WorkerError("projection encoding is not canonical")
    if len(raw) > 2_048:
        raise WorkerError("projection exceeds 2048 bytes")
    return raw


def consume(raw: bytes) -> dict[str, Any]:
    if len(raw) > 16_384:
        raise WorkerError("consumer envelope exceeds the input bound")
    try:
        envelope = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkerError("consumer envelope is not UTF-8 JSON") from error
    if raw != _canonical_json(envelope):
        raise WorkerError("consumer envelope is not canonical JSON")
    value = _exact(
        envelope,
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
            "public_query",
            "projection_base64",
        },
        "consumer envelope",
    )
    if value["schema_version"] != SCHEMA_VERSION or value["experiment_id"] != EXPERIMENT_ID:
        raise WorkerError("consumer envelope identity differs")
    case_id = _identity(value["case_id"], "case identity")
    condition_id = _identity(value["condition_id"], "condition identity")
    lineage_id = _identity(value["lineage_id"], "lineage identity")
    consumer_id = _identity(value["consumer_id"], "consumer identity")
    encounter_index = value["encounter_index"]
    if type(encounter_index) is not int or not 0 <= encounter_index <= 242:
        raise WorkerError("encounter index is unavailable")
    mechanism = value["mechanism_id"]
    if type(mechanism) is not str:
        raise WorkerError("mechanism identity is unavailable")
    mode = value["mode"]
    if mode not in {"prediction", "terminal-audit"}:
        raise WorkerError("consumer mode is unavailable")
    projection = _projection(value["projection_base64"])
    if mode == "prediction":
        if encounter_index >= 242 or type(value["public_query"]) is not dict:
            raise WorkerError("prediction consumer query or index differs")
        result = predict(mechanism, projection, value["public_query"])
        prediction: int | None = result.prediction
        operations = result.operations
        state_bytes = result.state_bytes
        candidate_count = result.candidate_count
    else:
        if encounter_index != 242 or value["public_query"] is not None:
            raise WorkerError("terminal audit query or index differs")
        state = decode_state(mechanism, projection)
        if encode_state(mechanism, state) != projection:
            raise WorkerError("terminal audit projection did not round trip")
        prediction = None
        operations = 0
        state_bytes = len(projection)
        candidate_count = 0
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "mechanism_id": mechanism,
        "mode": mode,
        "case_id": case_id,
        "condition_id": condition_id,
        "lineage_id": lineage_id,
        "consumer_id": consumer_id,
        "encounter_index": encounter_index,
        "projection_sha256": hashlib.sha256(projection).hexdigest(),
        "public_query_sha256": (
            hashlib.sha256(_canonical_json(value["public_query"])).hexdigest()
            if mode == "prediction"
            else None
        ),
        "prediction": prediction,
        "prediction_operations": operations,
        "state_bytes": state_bytes,
        "candidate_count": candidate_count,
    }


def _exec_descriptor_audit() -> bool:
    """Prove that the one-exec boundary exposes only standard streams."""

    return _open_file_descriptors() == {0, 1, 2}


def _open_file_descriptors() -> set[int]:
    """Return only currently open descriptor numbers without broad inspection."""

    for directory in ("/dev/fd", "/proc/self/fd"):
        try:
            names = os.listdir(directory)
        except OSError:
            continue
        result: set[int] = set()
        for name in names:
            if not name.isdigit():
                continue
            descriptor = int(name)
            try:
                os.fstat(descriptor)
            except OSError:
                continue
            result.add(descriptor)
        return result
    raise WorkerError("fresh consumer descriptor audit is unavailable")


def _isolate_forked_child(
    *,
    response_descriptor: int,
    workspace: str,
    environment: dict[str, str],
) -> bool:
    """Audit opaque bootstrap controls and cut their learner visibility."""

    if type(workspace) is not str or type(environment) is not dict:
        raise WorkerError("forked consumer isolation inputs differ")
    if sorted(environment) != list(ALLOWED_ENVIRONMENT_NAMES) or any(
        type(key) is not str or type(value) is not str
        for key, value in environment.items()
    ):
        raise WorkerError("forked consumer environment differs")

    # The forkserver and its bootstrap pipe never receive the task envelope.
    # Once this already-forked child has unpickled its one envelope, rebind
    # stdio.  CPython still needs three opaque control descriptors after the
    # target returns (forkserver-alive, resource-tracker, parent sentinel), so
    # audit their exact identity rather than closing them and corrupting the
    # process bootstrap.  None is passed to consume or the learner call graph.
    null_descriptor = os.open(os.devnull, os.O_RDWR)
    try:
        for descriptor in (0, 1, 2):
            os.dup2(null_descriptor, descriptor)
    finally:
        if null_descriptor > 2 and null_descriptor != response_descriptor:
            os.close(null_descriptor)
    from multiprocessing import forkserver, process, resource_tracker

    parent_process = process.parent_process()
    inherited = forkserver._forkserver._inherited_fds  # type: ignore[attr-defined]
    if (
        parent_process is None
        or inherited is None
        or set(inherited) != {response_descriptor}
    ):
        raise WorkerError("forked consumer bootstrap descriptors differ")
    allowed_descriptors = {
        0,
        1,
        2,
        response_descriptor,
        forkserver._forkserver._forkserver_alive_fd,  # type: ignore[attr-defined]
        resource_tracker._resource_tracker._fd,  # type: ignore[attr-defined]
        parent_process.sentinel,
    }
    if None in allowed_descriptors:
        raise WorkerError("forked consumer retained an undeclared descriptor")
    extras = _open_file_descriptors() - allowed_descriptors
    # forkserver.main and BaseProcess._bootstrap each call _close_stdin(), whose
    # closefd=False wrapper leaves one /dev/null character descriptor behind.
    # Rebind Python stdin to fd 0 and close exactly those two known residues.
    if len(extras) != 2 or any(
        not stat.S_ISCHR(os.fstat(descriptor).st_mode)
        for descriptor in extras
    ):
        raise WorkerError("forked consumer retained an undeclared descriptor")
    sys.stdin = open(0, encoding="utf-8", closefd=False)
    for descriptor in extras:
        os.close(descriptor)
    if _open_file_descriptors() != allowed_descriptors:
        raise WorkerError("forked consumer retained an undeclared descriptor")

    os.environ.clear()
    os.environ.update(environment)
    os.chdir(workspace)
    return True


def forkserver_probe(response: Any) -> None:
    """Prove that the immutable worker module was loaded before this child fork."""

    packet = {
        "preloaded": _IMPORT_PROCESS_ID != os.getpid(),
        "worker_pid": os.getpid(),
    }
    try:
        response.send_bytes(_canonical_json(packet))
    finally:
        response.close()


def forkserver_descriptor_probe(response: Any) -> None:
    """Return bounded structural facts about CPython's forkserver controls."""

    from multiprocessing import forkserver, process, resource_tracker

    response_descriptor = response.fileno()
    parent_process = process.parent_process()
    inherited = forkserver._forkserver._inherited_fds or []  # type: ignore[attr-defined]
    declared = {
        0,
        1,
        2,
        response_descriptor,
        forkserver._forkserver._forkserver_alive_fd,  # type: ignore[attr-defined]
        resource_tracker._resource_tracker._fd,  # type: ignore[attr-defined]
        None if parent_process is None else parent_process.sentinel,
        *inherited,
    }
    open_descriptors = _open_file_descriptors()
    extras = open_descriptors - (declared - {None})
    import stat

    extra_kinds = {
        "character": 0,
        "fifo": 0,
        "other": 0,
        "regular": 0,
        "socket": 0,
    }
    for descriptor in extras:
        try:
            mode = os.fstat(descriptor).st_mode
        except OSError:
            extra_kinds["other"] += 1
            continue
        if stat.S_ISFIFO(mode):
            extra_kinds["fifo"] += 1
        elif stat.S_ISSOCK(mode):
            extra_kinds["socket"] += 1
        elif stat.S_ISCHR(mode):
            extra_kinds["character"] += 1
        elif stat.S_ISREG(mode):
            extra_kinds["regular"] += 1
        else:
            extra_kinds["other"] += 1
    packet = {
        "declared_count": len(declared - {None}),
        "declared_match": open_descriptors == declared - {None},
        "extra_kinds": extra_kinds,
        "inherited_count": len(inherited),
        "missing_count": len((declared - {None}) - open_descriptors),
        "open_count": len(open_descriptors),
        "parent_present": parent_process is not None,
        "response_inherited": response_descriptor in inherited,
    }
    try:
        response.send_bytes(_canonical_json(packet))
    finally:
        response.close()


def forkserver_consume(
    raw: bytes,
    workspace: str,
    environment: dict[str, str],
    response: Any,
) -> None:
    """Consume exactly one post-fork envelope and emit one canonical packet."""

    response_descriptor = response.fileno()
    stdout = b""
    stderr = b""
    returncode = 2
    fd_audit_pass = False
    try:
        fd_audit_pass = _isolate_forked_child(
            response_descriptor=response_descriptor,
            workspace=workspace,
            environment=environment,
        )
        before = sorted(path.name for path in Path.cwd().iterdir())
        result = consume(raw)
        after = sorted(path.name for path in Path.cwd().iterdir())
        result.update(
            {
                "descriptor_audit_pass": fd_audit_pass,
                "workspace_empty_before": before == [],
                "workspace_empty_after": after == [],
                "environment_names": sorted(os.environ),
                "environment_allowlist_pass": sorted(os.environ)
                == list(ALLOWED_ENVIRONMENT_NAMES),
                "response_chain_absent": True,
            }
        )
        if not (
            result["workspace_empty_before"]
            and result["workspace_empty_after"]
            and result["environment_allowlist_pass"]
        ):
            raise WorkerError("fresh-process reset facts differ")
        stdout = _canonical_json(result)
        returncode = 0
    except LearningError:
        stderr = b"consumer rejected: learning-error\n"
    except (OSError, TypeError, ValueError):
        stderr = b"consumer rejected: worker-error\n"
    packet = {
        "fd_audit_pass": fd_audit_pass,
        "preloaded": _IMPORT_PROCESS_ID != os.getpid(),
        "returncode": returncode,
        "stderr_base64": base64.b64encode(stderr).decode("ascii"),
        "stdout_base64": base64.b64encode(stdout).decode("ascii"),
        "worker_pid": os.getpid(),
    }
    try:
        response.send_bytes(_canonical_json(packet))
    finally:
        response.close()


def main() -> int:
    before = sorted(path.name for path in Path.cwd().iterdir())
    environment_names = sorted(os.environ)
    descriptor_audit_pass = False
    try:
        descriptor_audit_pass = _exec_descriptor_audit()
        if not descriptor_audit_pass:
            raise WorkerError("fresh consumer descriptors differ")
        result = consume(sys.stdin.buffer.read(16_385))
        after = sorted(path.name for path in Path.cwd().iterdir())
        result.update(
            {
                "descriptor_audit_pass": descriptor_audit_pass,
                "workspace_empty_before": before == [],
                "workspace_empty_after": after == [],
                "environment_names": environment_names,
                "environment_allowlist_pass": environment_names
                == list(ALLOWED_ENVIRONMENT_NAMES),
                "response_chain_absent": True,
            }
        )
        if not (
            result["workspace_empty_before"]
            and result["workspace_empty_after"]
            and result["environment_allowlist_pass"]
        ):
            raise WorkerError("fresh-process reset facts differ")
        sys.stdout.buffer.write(_canonical_json(result))
        return 0
    except LearningError:
        # The inherited learner deliberately retains its OT-0075 diagnostics.
        # Do not make the OT-0077 controller parse those mutable prose details;
        # expose one typed adapter outcome instead.
        sys.stdout.buffer.write(
            _canonical_json({"descriptor_audit_pass": descriptor_audit_pass})
        )
        sys.stderr.write("consumer rejected: learning-error\n")
        return 2
    except (OSError, TypeError, ValueError) as error:
        sys.stderr.write(f"consumer rejected: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
