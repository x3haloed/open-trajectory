from __future__ import annotations

import unittest
import inspect
from pathlib import Path
from unittest.mock import patch

from open_trajectory_harness import ot0062
from open_trajectory_harness.ot0059 import reference_source
from open_trajectory_harness.ot0002 import canonical_json, load_json, sha256_bytes
from open_trajectory_harness.ot0061 import require_hosted_schema
from open_trajectory_harness.ot0062 import (
    actor_surface_authority,
    build_task,
    execute_worker,
    expected_task_seed,
    literal_deleted_source,
    source_novelty,
    validate_task,
)


class OT0062Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = build_task(expected_task_seed("6" * 40))

    def test_private_task_and_actor_surface_are_mechanical(self) -> None:
        validate_task(self.task)
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])
        self.assertNotEqual(
            sha256_bytes(canonical_json(self.task)),
            load_json(Path("spec/ot-0062-acceptance.json"))["retired_task_sha256"],
        )

    def test_repaired_schema_is_supported(self) -> None:
        schema = load_json(Path("fixtures/ot-0061/actor-output.schema.json"))
        self.assertTrue(require_hosted_schema(schema)["pass"])

    def test_preflight_precedes_workspace_and_backend(self) -> None:
        source = inspect.getsource(ot0062.run)
        self.assertLess(source.index("require_hosted_schema"), source.index("workspace.mkdir"))
        self.assertLess(source.index("workspace.mkdir"), source.index("SanitizedResponsesProxy"))

    def test_literal_deletion_removes_actor_literal(self) -> None:
        source = '"opaque" in event["on_flags"]'
        deleted = literal_deleted_source(source)
        self.assertNotIn("opaque", deleted)
        self.assertIn("on_flags", deleted)

    def test_hidden_reference_synthetic_worker_realizes_frozen_gates(self) -> None:
        calls = iter(self.task["world"]["regimes"])

        def fake_turn(**kwargs):
            regime = next(calls)
            source = reference_source(regime["target_flag"], regime["polarity"])
            return ({"parse_error": None}, source, [])

        with patch.object(ot0062, "run_actor_turn", side_effect=fake_turn):
            _, result, _ = execute_worker(
                repo=Path.cwd(),
                task=self.task,
                worker="worker-1",
                client=object(),
                proxy=object(),
                model="synthetic",
                workspace_root=Path("unused"),
                prompt_template="unused",
                orientation="unused",
                schema={},
            )
        self.assertTrue(result["pass"])
        self.assertEqual(result["candidate_errors"], [0, 0, 0])
        self.assertEqual(result["pre_update_errors"][:2], [4, 8])
        self.assertTrue(all(item["novelty"]["pass"] for item in result["regimes"]))

    def test_reference_source_is_not_in_actor_surface(self) -> None:
        regime = self.task["world"]["regimes"][0]
        source = reference_source(regime["target_flag"], regime["polarity"])
        novelty = source_novelty(Path.cwd(), source, ot0062.initial_snapshot())
        self.assertTrue(novelty["pass"])


if __name__ == "__main__":
    unittest.main()
