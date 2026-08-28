from __future__ import annotations

import copy
import unittest

from open_trajectory_harness.ot0076_design_probe import (
    EXPECTED_BASE_TASK_SHA256S,
    EXPECTED_WRAPPED_TASK_SHA256S,
    public_task_digests,
)
from open_trajectory_harness.ot0076_protocol import (
    ANCHOR_DOMAIN,
    BASE_EXPERIMENT_ID,
    DESIGN_DOMAIN,
    EXPERIMENT_ID,
    FUTURE_CANDIDATE_DOMAIN,
    ProtocolError,
    build_design_task,
    derive_task,
    validate_task,
)


class OT0076ProtocolTests(unittest.TestCase):
    def test_wrapper_changes_only_experiment_identity(self) -> None:
        from open_trajectory_harness.ot0075_protocol import (
            build_design_task as build_base_design_task,
        )

        for index in range(4):
            wrapped = build_design_task(index)
            base = build_base_design_task(index)
            self.assertEqual(wrapped["experiment_id"], EXPERIMENT_ID)
            self.assertEqual(base["experiment_id"], BASE_EXPERIMENT_ID)
            wrapped_as_base = copy.deepcopy(wrapped)
            wrapped_as_base["experiment_id"] = BASE_EXPERIMENT_ID
            self.assertEqual(wrapped_as_base, base)
            self.assertIs(validate_task(wrapped), wrapped)

    def test_base_and_wrapped_public_task_digests_are_exact(self) -> None:
        digests = public_task_digests()
        self.assertEqual(digests["base"], EXPECTED_BASE_TASK_SHA256S)
        self.assertEqual(digests["wrapped"], EXPECTED_WRAPPED_TASK_SHA256S)

    def test_private_derivation_is_deterministic_and_implementation_bound(self) -> None:
        seed = b"a" * 32
        first = derive_task(seed, "1" * 40, purpose="anchor")
        repeated = derive_task(seed, "1" * 40, purpose="anchor")
        changed = derive_task(seed, "2" * 40, purpose="anchor")
        self.assertEqual(first, repeated)
        self.assertNotEqual(first["cases"], changed["cases"])
        self.assertEqual(first["experiment_id"], EXPERIMENT_ID)
        self.assertEqual(first["domain"], ANCHOR_DOMAIN)

    def test_domains_remain_separated(self) -> None:
        self.assertEqual(len({DESIGN_DOMAIN, ANCHOR_DOMAIN, FUTURE_CANDIDATE_DOMAIN}), 3)

    def test_wrong_or_extra_identity_fails_closed(self) -> None:
        task = build_design_task(0)
        wrong = copy.deepcopy(task)
        wrong["experiment_id"] = BASE_EXPERIMENT_ID
        with self.assertRaises(ProtocolError):
            validate_task(wrong)

        extra = copy.deepcopy(task)
        extra["candidate_surface"] = "forbidden"
        with self.assertRaises(ProtocolError):
            validate_task(extra)


if __name__ == "__main__":
    unittest.main()
