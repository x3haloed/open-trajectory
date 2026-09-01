from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable


Subject = dict[str, Any]
Digest = Callable[[Any], str]
Seal = Callable[[Subject], Subject]


@dataclass(frozen=True)
class InvocationCallbacks:
    dispatch: Callable[[Subject], str]
    contact_world: Callable[[Subject], dict[str, Any]]
    compile_world: Callable[[Subject, dict[str, Any]], Subject]
    resolve_for_assimilation: Callable[[Subject], dict[str, Any]]
    assimilate: Callable[[Subject, dict[str, Any]], dict[str, Any]]
    compile_pending: Callable[[Subject, dict[str, Any]], Subject]
    observer_stop: Callable[[Subject], Subject]
    correct: Callable[[Subject, dict[str, Any]], tuple[Subject, dict[str, Any]]] | None = None


def pulse_eligible(subject: Subject) -> bool:
    try:
        state = subject["fixed_g6_recurrence_driver"]
        pending = subject["pending_contact_bearing_continuations"][-1]
        liveness = subject["continuation_liveness"]
        return bool(
            subject["continuation"]["status"] == "open"
            and state["phase"] == "observer-stop"
            and state["encounters"] == state["observation_limit"]
            and state["accepted_actors"] <= state["actor_limit"]
            and liveness["status"] == "live"
            and pending["consequence_status"] == "unreceipted"
            and pending["contact_identity"] == liveness["contact_identity"]
        )
    except (KeyError, IndexError, TypeError):
        return False


def apply_pulse(subject: Subject, digest: Digest, seal: Seal, authority: str, actor_allowance: int = 2) -> tuple[Subject, dict[str, Any]]:
    if not pulse_eligible(subject):
        raise ValueError("subject is not pulse-eligible")
    if actor_allowance < 1:
        raise ValueError("actor allowance must be positive")
    child = copy.deepcopy(subject)
    child.pop("artifact_digest", None)
    state = copy.deepcopy(subject["fixed_g6_recurrence_driver"])
    pending = subject["pending_contact_bearing_continuations"][-1]
    body = {
        "authority": authority,
        "source_subject_digest": subject["artifact_digest"],
        "from_phase": "observer-stop",
        "to_phase": "contact",
        "pending_contact_identity": pending["contact_identity"],
        "prior_observation_limit": state["observation_limit"],
        "prior_actor_limit": state["actor_limit"],
        "encounter_allowance": 1,
        "actor_allowance": actor_allowance,
        "content_supplied": False,
    }
    receipt = {**body, "receipt_digest": digest(body)}
    state["phase"] = "contact"
    state["observation_limit"] += 1
    state["actor_limit"] += actor_allowance
    state["invocations"] = state.get("invocations", 1) + 1
    child["fixed_g6_recurrence_driver"] = state
    child["cross_invocation_pulse_receipts"] = [*child.get("cross_invocation_pulse_receipts", []), receipt]
    return seal(child), receipt


def continue_once(subject: Subject, *, digest: Digest, seal: Seal, authority: str, callbacks: InvocationCallbacks) -> tuple[Subject, dict[str, Any]]:
    resumed, pulse = apply_pulse(subject, digest, seal, authority)
    if callbacks.dispatch(resumed) != "contact":
        return resumed, {"status": "invalid-dispatch", "pulse": pulse}
    world = callbacks.contact_world(resumed)
    current = callbacks.compile_world(resumed, world)
    correction_summary = None
    phase = callbacks.dispatch(current)
    if phase == "correct":
        if callbacks.correct is None:
            return current, {"status": "needs-correction", "pulse": pulse, "world": world}
        current, correction_summary = callbacks.correct(current, world)
        phase = callbacks.dispatch(current)
    if phase != "assimilate":
        return current, {"status": "nondecisive", "pulse": pulse, "world": world, "correction": correction_summary}
    resolved = callbacks.resolve_for_assimilation(current)
    assimilation = callbacks.assimilate(current, resolved)
    if not assimilation.get("accepted"):
        return current, {"status": "assimilation-rejected", "pulse": pulse, "world": world, "correction": correction_summary, "assimilation": assimilation}
    candidate = callbacks.compile_pending(current, assimilation)
    if callbacks.dispatch(candidate) != "contact":
        return candidate, {"status": "invalid-reopening", "pulse": pulse, "world": world, "correction": correction_summary, "assimilation": assimilation}
    final = callbacks.observer_stop(candidate)
    return final, {"status": "completed", "pulse": pulse, "world": world, "correction": correction_summary, "assimilation": assimilation}
