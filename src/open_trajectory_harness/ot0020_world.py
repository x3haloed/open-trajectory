from __future__ import annotations

import json
import secrets
from typing import Any

from .ot0004_world import validate_task_manifest as validate_ot0004_manifest
from .ot0017_regime import construct_direct_manifest


EXPERIMENT_ID = "OT-0020"
EVALUATION_EPOCH = "E4"
PROMOTION_MANIFEST = (
    "evidence/manifests/OT-0019/ot-0019-full-suffix-e4-calibration-001.json"
)


def _json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _inherited(manifest: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    inherited = {
        key: value
        for key, value in manifest.items()
        if key != "e4_construction_receipt"
    }
    inherited["experiment_id"] = experiment_id
    return inherited


def generate_task_manifest(seed: str | None = None) -> dict[str, Any]:
    seed = seed or secrets.token_hex(16)
    constructed = construct_direct_manifest(seed)
    if not constructed["receipt"]["success"] or constructed["manifest"] is None:
        raise RuntimeError("OT-0020 direct E4 task construction failed")
    manifest = _json_value(constructed["manifest"])
    manifest["experiment_id"] = EXPERIMENT_ID
    manifest["e4_construction_receipt"] = {
        "evaluation_epoch": EVALUATION_EPOCH,
        "promotion_manifest": PROMOTION_MANIFEST,
        **_json_value(constructed["receipt"]),
    }
    validate_task_manifest(manifest)
    return manifest


def validate_task_manifest(manifest: dict[str, Any]) -> None:
    if (
        manifest.get("schema_version") != 1
        or manifest.get("experiment_id") != EXPERIMENT_ID
    ):
        raise ValueError("invalid OT-0020 task-manifest identity")
    receipt = manifest.get("e4_construction_receipt")
    if not isinstance(receipt, dict):
        raise ValueError("OT-0020 task manifest omits its E4 construction receipt")
    if (
        receipt.get("evaluation_epoch") != EVALUATION_EPOCH
        or receipt.get("promotion_manifest") != PROMOTION_MANIFEST
        or receipt.get("success") is not True
        or not isinstance(receipt.get("seed"), str)
        or not receipt["seed"]
        or receipt.get("schema_valid") is not True
        or receipt.get("split_queries_separated") is not True
        or not isinstance(receipt.get("planned_witness"), dict)
        or receipt["planned_witness"].get("passes") is not True
        or not isinstance(receipt.get("exact_witness"), dict)
        or receipt["exact_witness"].get("passes") is not True
    ):
        raise ValueError("OT-0020 E4 construction receipt failed its frozen gates")
    validate_ot0004_manifest(_inherited(manifest, "OT-0004"))
    reconstructed = construct_direct_manifest(receipt["seed"])
    if not reconstructed["receipt"]["success"] or reconstructed["manifest"] is None:
        raise ValueError("OT-0020 E4 task does not reconstruct")
    expected_manifest = _json_value(reconstructed["manifest"])
    observed_manifest = _inherited(manifest, "OT-0005")
    if observed_manifest != expected_manifest:
        raise ValueError("OT-0020 task differs from its direct construction seed")
    expected_receipt = {
        "evaluation_epoch": EVALUATION_EPOCH,
        "promotion_manifest": PROMOTION_MANIFEST,
        **_json_value(reconstructed["receipt"]),
    }
    if receipt != expected_receipt:
        raise ValueError("OT-0020 E4 construction receipt does not replay exactly")


__all__ = ["generate_task_manifest", "validate_task_manifest"]
