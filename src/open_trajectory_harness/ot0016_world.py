from __future__ import annotations

from typing import Any

from .ot0004_world import validate_task_manifest as validate_ot0004_manifest
from .ot0005_world import generate_task_manifest as generate_ot0005_manifest
from .ot0016_power import (
    CONSTRAINED_MANIFEST_GATE,
    CONSTRAINED_MAX_ATTEMPTS,
    analyze_manifest,
    constrained_manifest_gates,
)


EXPERIMENT_ID = "OT-0016"


def _as_inherited(manifest: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    inherited = {
        key: value for key, value in manifest.items() if key != "sampling_receipt"
    }
    inherited["experiment_id"] = experiment_id
    return inherited


def generate_task_manifest(
    *, max_attempts: int = CONSTRAINED_MAX_ATTEMPTS
) -> dict[str, Any]:
    if max_attempts <= 0:
        raise ValueError("maximum attempts must be positive")
    rejected_sha256: list[str] = []
    for attempt in range(1, max_attempts + 1):
        inherited = generate_ot0005_manifest()
        analysis = analyze_manifest(inherited)
        gates = constrained_manifest_gates(analysis)
        if all(gates.values()):
            manifest = dict(inherited)
            manifest["experiment_id"] = EXPERIMENT_ID
            manifest["sampling_receipt"] = {
                "sampler": "constrained-world-sampler-v1",
                "attempts": attempt,
                "maximum_attempts": max_attempts,
                "gate": CONSTRAINED_MANIFEST_GATE,
                "observed": {
                    "dynamic_advantage": analysis["dynamic_advantage"],
                    "contact_choice_regret": analysis["contact_choice_regret"],
                    "harm_and_contact_recovery_transitions": analysis[
                        "harm_and_contact_recovery_transitions"
                    ],
                    "contact_advantage_over_best_static": analysis["best_static_total"]
                    - analysis["contact_selected_total"],
                },
                "gates": gates,
                "rejected_manifest_sha256": rejected_sha256,
            }
            validate_task_manifest(manifest)
            return manifest
        rejected_sha256.append(analysis["task_manifest_sha256"])
    raise RuntimeError("OT-0016 constrained task generation exhausted its attempt budget")


def validate_task_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1 or manifest.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("invalid OT-0016 task-manifest identity")
    receipt = manifest.get("sampling_receipt")
    expected_receipt_keys = {
        "sampler",
        "attempts",
        "maximum_attempts",
        "gate",
        "observed",
        "gates",
        "rejected_manifest_sha256",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected_receipt_keys:
        raise ValueError("OT-0016 task manifest omits its exact sampling receipt")
    if (
        receipt["sampler"] != "constrained-world-sampler-v1"
        or receipt["maximum_attempts"] != CONSTRAINED_MAX_ATTEMPTS
        or not isinstance(receipt["attempts"], int)
        or not 1 <= receipt["attempts"] <= receipt["maximum_attempts"]
        or receipt["gate"] != CONSTRAINED_MANIFEST_GATE
        or not isinstance(receipt["rejected_manifest_sha256"], list)
        or len(receipt["rejected_manifest_sha256"]) != receipt["attempts"] - 1
        or not isinstance(receipt["gates"], dict)
        or not all(receipt["gates"].values())
    ):
        raise ValueError("OT-0016 sampling receipt violates its frozen generator contract")
    validate_ot0004_manifest(_as_inherited(manifest, "OT-0004"))
    analysis = analyze_manifest(_as_inherited(manifest, "OT-0005"))
    gates = constrained_manifest_gates(analysis)
    observed = {
        "dynamic_advantage": analysis["dynamic_advantage"],
        "contact_choice_regret": analysis["contact_choice_regret"],
        "harm_and_contact_recovery_transitions": analysis[
            "harm_and_contact_recovery_transitions"
        ],
        "contact_advantage_over_best_static": analysis["best_static_total"]
        - analysis["contact_selected_total"],
    }
    if receipt["observed"] != observed or receipt["gates"] != gates or not all(gates.values()):
        raise ValueError("OT-0016 task manifest fails its constrained-world gate")


__all__ = ["generate_task_manifest", "validate_task_manifest"]
