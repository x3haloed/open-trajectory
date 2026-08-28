"""One-prediction fresh-process consumer for OT-0076.

The worker receives one public query and one bounded canonical projection on
standard input.  It has no task loader, outcome, prior response, trajectory
store, filesystem capability in the learner call graph, or evaluator score.
The small wrapper inspects only its empty current directory and the names (not
values) of its deliberately allowlisted process environment.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .ot0002 import canonical_json
from .ot0076_learning import LearningError, decode_state, encode_state, predict


EXPERIMENT_ID = "OT-0076"
SCHEMA_VERSION = 1
ALLOWED_ENVIRONMENT_NAMES = (
    "LANG",
    "LC_ALL",
    "OT0076_SURFACE",
    "PATH",
    "PYTHONHASHSEED",
    "PYTHONPATH",
    "__CF_USER_TEXT_ENCODING",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")


class WorkerError(ValueError):
    """Raised when a reset envelope is not the exact bounded surface."""


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
    if raw != canonical_json(envelope):
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
        "prediction": prediction,
        "prediction_operations": operations,
        "state_bytes": state_bytes,
        "candidate_count": candidate_count,
    }


def main() -> int:
    before = sorted(path.name for path in Path.cwd().iterdir())
    environment_names = sorted(os.environ)
    try:
        result = consume(sys.stdin.buffer.read(16_385))
        after = sorted(path.name for path in Path.cwd().iterdir())
        result.update(
            {
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
        sys.stdout.buffer.write(canonical_json(result))
        return 0
    except (LearningError, OSError, TypeError, ValueError) as error:
        sys.stderr.write(f"consumer rejected: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
