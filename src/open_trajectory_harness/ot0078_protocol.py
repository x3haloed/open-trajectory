"""P-frozen OT-0078 wrapper around the preserved OT-0076 task family.

OT-0078 prospectively repairs only operational authority after OT-0077's public
checkpoint timed out and its oversized failure journal exceeded an unrelated
raw-artifact snapshot bound. This module gives every task the new experiment
identity while delegating seed expansion and structural validation to the exact
P-frozen OT-0076 task protocol. It contains no learner, scorer, receipt builder,
execution path, deadline, or journal policy.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Final

from . import ot0076_protocol as _base


EXPERIMENT_ID: Final = "OT-0078"
BASE_EXPERIMENT_ID: Final = _base.EXPERIMENT_ID
BASE_PROTOCOL_SHA256: Final = (
    "dd17c5b8e7296a21cd266ae10c52833feaab79d83dc96a9d615ab30d0a6b9359"
)
ACCEPTANCE_PATH: Final = Path("spec/ot-0078-acceptance.json")
EXPERIMENT_PATH: Final = Path(
    "experiments/OT-0078-e14-operational-authority-repair.md"
)

SCHEMA_VERSION: Final = _base.SCHEMA_VERSION
DIMENSION: Final = _base.DIMENSION
SEED_BYTES: Final = _base.SEED_BYTES
ANCHOR_CASE_COUNT: Final = _base.ANCHOR_CASE_COUNT
DESIGN_CASE_COUNT: Final = _base.DESIGN_CASE_COUNT
EPISODE_SCHEDULE: Final = _base.EPISODE_SCHEDULE
DWELL_LENGTHS: Final = _base.DWELL_LENGTHS
HORIZON: Final = _base.HORIZON
MIN_MASK_WEIGHT: Final = _base.MIN_MASK_WEIGHT
MAX_MASK_WEIGHT: Final = _base.MAX_MASK_WEIGHT
RECURRENCE_DISAMBIGUATION_PREFIX: Final = (
    _base.RECURRENCE_DISAMBIGUATION_PREFIX
)

# The world family remains byte-identical.  A fresh seed and clean-I binding
# make the private anchor new; preserving the family isolates the operational
# authority repair.
DESIGN_DOMAIN: Final = _base.DESIGN_DOMAIN
ANCHOR_DOMAIN: Final = _base.ANCHOR_DOMAIN
FUTURE_CANDIDATE_DOMAIN: Final = "open-trajectory/e14/post-ot-0078-candidate/v1"

ProtocolError = _base.ProtocolError
parse_bits = _base.parse_bits
parity = _base.parity
design_seed = _base.design_seed


def _with_experiment_identity(task: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    result = copy.deepcopy(task)
    result["experiment_id"] = experiment_id
    return result


def derive_task(
    seed: bytes,
    implementation_commit: str,
    *,
    purpose: str,
) -> dict[str, Any]:
    task = _base.derive_task(seed, implementation_commit, purpose=purpose)
    wrapped = _with_experiment_identity(task, EXPERIMENT_ID)
    validate_task(wrapped)
    return wrapped


def build_design_task(index: int) -> dict[str, Any]:
    return derive_task(design_seed(index), "0" * 40, purpose="design")


def validate_task(task: object) -> dict[str, Any]:
    if type(task) is not dict or task.get("experiment_id") != EXPERIMENT_ID:
        raise ProtocolError("OT-0078 task experiment identity differs")
    base_task = _with_experiment_identity(task, BASE_EXPERIMENT_ID)
    checked = _base.validate_task(base_task)
    expected = _with_experiment_identity(checked, EXPERIMENT_ID)
    if expected != task:
        raise ProtocolError("OT-0078 wrapped task differs from the frozen family")
    return task


__all__ = [
    "ACCEPTANCE_PATH",
    "ANCHOR_CASE_COUNT",
    "ANCHOR_DOMAIN",
    "BASE_EXPERIMENT_ID",
    "BASE_PROTOCOL_SHA256",
    "DESIGN_CASE_COUNT",
    "DESIGN_DOMAIN",
    "DIMENSION",
    "DWELL_LENGTHS",
    "EPISODE_SCHEDULE",
    "EXPERIMENT_ID",
    "EXPERIMENT_PATH",
    "FUTURE_CANDIDATE_DOMAIN",
    "HORIZON",
    "MAX_MASK_WEIGHT",
    "MIN_MASK_WEIGHT",
    "ProtocolError",
    "RECURRENCE_DISAMBIGUATION_PREFIX",
    "SCHEMA_VERSION",
    "SEED_BYTES",
    "build_design_task",
    "derive_task",
    "design_seed",
    "parity",
    "parse_bits",
    "validate_task",
]
