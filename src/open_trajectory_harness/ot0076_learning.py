"""Unchanged OT-0075 learning mechanisms used by the OT-0076 evaluator repair.

OT-0076 changes only the causal counterfactual, receipt ancestry, and scoring
regime.  Keeping this thin, explicit re-export makes that mechanism identity
auditable while giving the new lifecycle a separately hashed import surface.
"""

from typing import Any

from .ot0075_learning import *  # noqa: F401,F403
from .ot0075_learning import (
    COMPACT_REFERENCE,
    LOG_REFERENCE,
    LearningError,
    UpdateResult,
    __all__ as _BASE_ALL,
    compact_update,
    decode_state,
    log_update,
)


def update_from_authoritative_state(
    mechanism: str,
    state_bytes: bytes,
    public_query: object,
    released_outcome: object,
) -> UpdateResult:
    """Apply an outcome-only reference update to the exact receipted state.

    The positive reference updaters do not use their actor prediction.  This
    entrypoint exists solely for OT-0076's update-without-projection cut, where
    the actor predicts from a deliberately frozen projection while the updater
    must continue from its separately receipted authoritative state.
    """

    if mechanism not in {COMPACT_REFERENCE, LOG_REFERENCE}:
        raise LearningError(
            "OT-0076 authoritative-state update is limited to positive references"
        )
    state: dict[str, Any] = decode_state(mechanism, state_bytes)
    if mechanism == COMPACT_REFERENCE:
        return compact_update(state, public_query, released_outcome)
    return log_update(state, public_query, released_outcome)


__all__ = [*_BASE_ALL, "update_from_authoritative_state"]
