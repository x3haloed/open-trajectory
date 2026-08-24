from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


REPO = Path(__file__).resolve().parents[1]
BASE_SCHEMA_PATH = REPO / "spec" / "encounter-run.schema.json"
OT0002_SCHEMA_PATH = REPO / "spec" / "ot-0002-run.schema.json"
OT0011_SCHEMA_PATH = REPO / "spec" / "ot-0011-run.schema.json"
PROMOTED_OT1_SCHEMA_PATH = REPO / "spec" / "ot-1-promoted-run.schema.json"
VALID_FIXTURE_PATH = REPO / "fixtures" / "encounter-specs" / "ot-0002-valid.json"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object in {path.name}")
    return value


class EncounterSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_schema = load_json(BASE_SCHEMA_PATH)
        cls.ot0002_schema = load_json(OT0002_SCHEMA_PATH)
        cls.ot0011_schema = load_json(OT0011_SCHEMA_PATH)
        cls.promoted_ot1_schema = load_json(PROMOTED_OT1_SCHEMA_PATH)
        cls.valid = load_json(VALID_FIXTURE_PATH)

        for schema in (
            cls.base_schema,
            cls.ot0002_schema,
            cls.ot0011_schema,
            cls.promoted_ot1_schema,
        ):
            Draft202012Validator.check_schema(schema)

        registry = Registry().with_resource(
            cls.base_schema["$id"],
            Resource.from_contents(cls.base_schema),
        )
        cls.base_validator = Draft202012Validator(cls.base_schema, registry=registry)
        cls.ot0002_validator = Draft202012Validator(cls.ot0002_schema, registry=registry)
        cls.ot0011_validator = Draft202012Validator(cls.ot0011_schema, registry=registry)
        cls.promoted_ot1_validator = Draft202012Validator(
            cls.promoted_ot1_schema,
            registry=registry,
        )

    def assert_valid(self, validator: Draft202012Validator, instance: dict) -> None:
        errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
        self.assertEqual([error.message for error in errors], [])

    def assert_invalid(self, validator: Draft202012Validator, instance: dict) -> None:
        self.assertTrue(list(validator.iter_errors(instance)))

    def test_complete_ot0002_fixture_validates(self) -> None:
        self.assert_valid(self.base_validator, self.valid)
        self.assert_valid(self.ot0002_validator, self.valid)

    def test_ot0011_schema_accepts_the_frozen_boundary_shape(self) -> None:
        instance = copy.deepcopy(self.valid)
        instance["experiment_id"] = "OT-0011"
        self.assert_valid(self.ot0011_validator, instance)

    def test_resumed_thread_is_invalid(self) -> None:
        instance = copy.deepcopy(self.valid)
        instance["reset"]["fresh_thread"] = False
        instance["reset"]["resume_allowed"] = True
        self.assert_invalid(self.base_validator, instance)

    def test_dirty_implementation_is_invalid(self) -> None:
        instance = copy.deepcopy(self.valid)
        instance["provenance"]["implementation_dirty"] = True
        self.assert_invalid(self.base_validator, instance)

    def test_symbolic_git_ref_is_invalid(self) -> None:
        instance = copy.deepcopy(self.valid)
        instance["provenance"]["implementation_git_commit"] = "main"
        self.assert_invalid(self.base_validator, instance)

    def test_escaping_workspace_is_invalid(self) -> None:
        instance = copy.deepcopy(self.valid)
        instance["workspace"]["logical_root"] = "$EVIDENCE/sandboxes/run-001/../../hidden"
        self.assert_invalid(self.base_validator, instance)

    def test_unexpected_tool_or_field_is_invalid(self) -> None:
        instance = copy.deepcopy(self.valid)
        instance["workspace"]["undeclared_tool"] = "shell"
        self.assert_invalid(self.base_validator, instance)

    def test_allowlisted_network_is_representable_but_invalid_for_ot0002(self) -> None:
        instance = copy.deepcopy(self.valid)
        instance["workspace"]["network_policy"]["mode"] = "allowlisted"
        self.assert_valid(self.base_validator, instance)
        self.assert_invalid(self.ot0002_validator, instance)

    def test_promoted_ot1_accepts_immutable_model_revision(self) -> None:
        self.assert_invalid(self.promoted_ot1_validator, self.valid)
        instance = copy.deepcopy(self.valid)
        instance["model"]["stability"] = "immutable-revision"
        instance["model"]["revision"] = "snapshot-0123456789abcdef"
        self.assert_valid(self.promoted_ot1_validator, instance)

    def test_promoted_ot1_accepts_complete_hosted_deployment_epoch(self) -> None:
        instance = copy.deepcopy(self.valid)
        instance["model"]["stability"] = "hosted-deployment-epoch"
        instance["model"]["revision"] = "receipted-deployment-epoch"
        instance["model"]["deployment_epoch"] = {
            "requested_model": "model-under-test",
            "effective_model": "effective-model-under-test",
            "catalog_etag_sha256": "1" * 64,
            "catalog_payload_sha256": "2" * 64,
            "receipt_protocol_sha256": "3" * 64,
            "response_receipts_sha256": "4" * 64,
            "response_count": 26,
            "condition_order_sha256": "5" * 64,
            "max_window_seconds": 1800,
            "observed_window_seconds": 300.5,
            "epoch_consistent": True,
        }
        self.assert_valid(self.promoted_ot1_validator, instance)

    def test_promoted_ot1_rejects_incomplete_hosted_deployment_epoch(self) -> None:
        instance = copy.deepcopy(self.valid)
        instance["model"]["stability"] = "hosted-deployment-epoch"
        instance["model"]["revision"] = "receipted-deployment-epoch"
        self.assert_invalid(self.promoted_ot1_validator, instance)


if __name__ == "__main__":
    unittest.main()
