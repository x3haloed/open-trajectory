from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from open_trajectory_harness import ot0055
from open_trajectory_harness.ot0048 import complete_contact
from open_trajectory_harness.ot0049_world import INITIAL_WEIGHTS, counterbalanced_split
from open_trajectory_harness.ot0055 import (
    actor_surface_authority,
    build_task,
    descriptive_rule,
    equal_state_projections,
    execute_worker,
    expected_task_seed,
    validate_task,
)
from open_trajectory_harness.ot0048 import weighted_selections
from open_trajectory_harness.ot0002 import canonical_json, sha256_bytes


class OT0055Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = build_task(expected_task_seed("9" * 40))

    def test_task_and_surface_are_mechanical(self) -> None:
        validate_task(self.task)
        self.assertTrue(actor_surface_authority(Path.cwd())["pass"])

    def test_descriptive_projection_is_byte_equal_and_non_executable(self) -> None:
        regime = self.task["regimes"][0]
        contact = counterbalanced_split(regime["contact"], "worker-1")
        choices = weighted_selections(INITIAL_WEIGHTS, contact)
        receipt = complete_contact(contact, choices)
        projections = equal_state_projections(
            task_seed=self.task["task_seed"],
            regime_index=1,
            relation=tuple(regime["relation"]),
            polarity=regime["polarity"],
            contact=contact,
            choices=choices,
            receipt=receipt,
            byte_limit=16000,
        )
        self.assertEqual(
            len({len(canonical_json(item)) for item in projections.values()}), 1
        )
        rule = descriptive_rule(tuple(regime["relation"]), regime["polarity"])
        self.assertNotIn("x[", rule)
        self.assertNotIn("*", rule)

    def test_synthetic_application_controls_realize_gate_shape(self) -> None:
        def fake_turn(**kwargs):
            if kwargs["condition"] == "reference":
                errors = 0
            else:
                errors = 8
            result = {
                "condition": kwargs["condition"],
                "errors": errors,
                "encounter_sha256": sha256_bytes(
                    canonical_json(kwargs["view"]["pairs"])
                ),
            }
            return result, []

        with patch.object(ot0055, "run_application_turn", side_effect=fake_turn):
            _, mechanism, _ = execute_worker(
                task=self.task,
                worker="worker-1",
                client=object(),
                proxy=object(),
                model="synthetic",
                workspace_root=Path("unused"),
                prompt_template="unused",
                schema={},
                byte_limit=16000,
            )
        self.assertEqual(mechanism["reference_errors"], [0, 0, 0])
        self.assertEqual(mechanism["opaque_errors"], [8, 8, 8])
        self.assertEqual(mechanism["verbatim_errors"], [8, 8, 8])


if __name__ == "__main__":
    unittest.main()
