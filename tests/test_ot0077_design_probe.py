from __future__ import annotations

import copy
import unittest
from unittest import mock

from open_trajectory_harness.ot0077_design_probe import (
    DesignProbeError,
    EXPECTED_BASE_TASK_SHA256S,
    EXPECTED_ROW_COUNT,
    EXPECTED_VECTOR_BYTES,
    EXPECTED_VECTOR_SHA256,
    EXPECTED_WRAPPED_TASK_SHA256S,
    HARD_SEVERING_ORDER,
    REFERENCE_ORDER,
    ROW_KEYS,
    TRUE_NO_LEARNING_VALUE_KEYS,
    assert_public_design,
    build_public_design_vector,
    canonical_design_vector,
    canonical_json,
    sha256_bytes,
    verify_public_design,
)
from open_trajectory_harness.ot0077_protocol import HORIZON


class OT0077DesignProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = build_public_design_vector()
        cls.payload = canonical_design_vector(cls.rows)

    def test_exact_schema_and_order_match_the_repaired_frozen_identity(self) -> None:
        self.assertEqual(len(self.rows), EXPECTED_ROW_COUNT)
        self.assertEqual(
            [
                (row["design_seed"], row["case_index"], row["reference_id"])
                for row in self.rows
            ],
            [
                (design_seed, case_index, reference_id)
                for design_seed in range(4)
                for case_index in range(16)
                for reference_id in REFERENCE_ORDER
            ],
        )
        self.assertTrue(all(set(row) == ROW_KEYS for row in self.rows))
        self.assertEqual(len(self.payload), EXPECTED_VECTOR_BYTES)
        self.assertEqual(sha256_bytes(self.payload), EXPECTED_VECTOR_SHA256)

    def test_frozen_digest_used_a_non_schema_withholding_alias(self) -> None:
        diagnostic = copy.deepcopy(self.rows)
        for row in diagnostic:
            value = row["true_no_learning"].pop("consequence-withholding")
            row["true_no_learning"]["withholding"] = value
        payload = canonical_json(diagnostic)
        self.assertEqual(len(payload), 126_413)
        self.assertEqual(
            sha256_bytes(payload),
            "ec69c3fc99c062a7430ea95d46f93827008605cceec5ae1c1c118f4a3090ed7b",
        )
        self.assertNotEqual(set(diagnostic[0]["true_no_learning"]), set(HARD_SEVERING_ORDER))

    def test_builder_uses_fresh_ordered_process_aggregation(self) -> None:
        module = "open_trajectory_harness.ot0077_design_probe"
        executor = mock.MagicMock()
        executor.__enter__.return_value = executor
        observed_jobs: list[list[tuple[int, int]]] = []

        def ordered_map(
            function: object,
            jobs: object,
            *,
            chunksize: int,
        ) -> list[tuple[dict[str, object], ...]]:
            self.assertEqual(
                getattr(function, "__name__", None),
                "_build_public_design_case_rows",
            )
            self.assertEqual(chunksize, 1)
            job_list = list(jobs)
            observed_jobs.append(
                [(seed, case["case_index"]) for seed, case in job_list]
            )
            return [
                tuple(self.rows[offset : offset + 2])
                for offset in range(0, len(self.rows), 2)
            ]

        executor.map.side_effect = ordered_map
        fake_task = {
            "cases": [{"case_index": case_index} for case_index in range(16)]
        }
        with (
            mock.patch(f"{module}.build_design_task", return_value=fake_task),
            mock.patch(f"{module}.validate_task", side_effect=lambda task: task),
            mock.patch(
                f"{module}.ProcessPoolExecutor",
                return_value=executor,
            ) as pool,
        ):
            self.assertEqual(build_public_design_vector(), self.rows)
            self.assertEqual(build_public_design_vector(), self.rows)

        expected_jobs = [
            (design_seed, case_index)
            for design_seed in range(4)
            for case_index in range(16)
        ]
        self.assertEqual(observed_jobs, [expected_jobs, expected_jobs])
        self.assertEqual(
            pool.call_args_list,
            [mock.call(max_workers=8), mock.call(max_workers=8)],
        )

    def test_every_reference_has_matched_margin_and_stale_loss(self) -> None:
        for row in self.rows:
            self.assertTrue(row["matched_margin_pass"])
            self.assertGreaterEqual(20 * row["live_lift"], HORIZON)
            self.assertTrue(row["stale_two_thirds_loss_pass"])
            self.assertLessEqual(
                3 * row["stale_residual_lift"],
                row["live_lift"],
            )
            self.assertTrue(row["stale_practical_margin_pass"])
            self.assertGreaterEqual(
                20 * (row["stale_errors"] - row["live_errors"]),
                HORIZON,
            )
            self.assertGreaterEqual(row["stale_accepted_updates"], 1)
            self.assertTrue(row["stale_active_projection_changed"])

    def test_hard_severings_match_the_exact_frozen_trace(self) -> None:
        for row in self.rows:
            severings = row["true_no_learning"]
            self.assertEqual(set(severings), set(HARD_SEVERING_ORDER))
            for value in severings.values():
                self.assertEqual(set(value), TRUE_NO_LEARNING_VALUE_KEYS)
                self.assertEqual(value["errors"], row["matched_frozen_errors"])
                self.assertTrue(value["prediction_status_trace_equal"])
                self.assertTrue(value["consumed_projection_trace_equal"])
                self.assertTrue(value["terminal_projection_equal"])

            self.assertEqual(
                severings["update-without-projection"]["accepted_updates"],
                HORIZON,
            )
            self.assertTrue(
                severings["update-without-projection"]["candidate_changed"]
            )
            for intervention_id in (
                "consequence-withholding",
                "projection-without-update",
            ):
                self.assertEqual(severings[intervention_id]["accepted_updates"], 0)
                self.assertFalse(severings[intervention_id]["candidate_changed"])

    def test_controller_verdict_has_exact_bounded_fail_closed_schema(self) -> None:
        task_digests = {
            "base": EXPECTED_BASE_TASK_SHA256S,
            "wrapped": EXPECTED_WRAPPED_TASK_SHA256S,
        }
        with (
            mock.patch(
                "open_trajectory_harness.ot0077_design_probe.public_task_digests",
                return_value=task_digests,
            ),
            mock.patch(
                "open_trajectory_harness.ot0077_design_probe.build_public_design_vector",
                return_value=self.rows,
            ),
        ):
            result = verify_public_design()
        self.assertEqual(
            set(result),
            {"canonical_bytes", "pass", "row_count", "sha256", "task_sha256s"},
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["row_count"], EXPECTED_ROW_COUNT)
        self.assertEqual(result["canonical_bytes"], 127_949)
        self.assertEqual(
            result["sha256"],
            "a645282da3986557ce10dfdc9a550482107fea0f7ccaab0748deedafccb1d603",
        )

        with (
            mock.patch(
                "open_trajectory_harness.ot0077_design_probe.public_task_digests",
                return_value=task_digests,
            ),
            mock.patch(
                "open_trajectory_harness.ot0077_design_probe.build_public_design_vector",
                return_value=self.rows,
            ),
        ):
            self.assertEqual(assert_public_design(), self.payload)

    def test_assertion_fails_closed_on_any_identity_mismatch(self) -> None:
        wrong = {
            "canonical_bytes": EXPECTED_VECTOR_BYTES,
            "pass": False,
            "row_count": EXPECTED_ROW_COUNT,
            "sha256": EXPECTED_VECTOR_SHA256,
            "task_sha256s": {
                "base": EXPECTED_BASE_TASK_SHA256S,
                "wrapped": EXPECTED_WRAPPED_TASK_SHA256S,
            },
        }
        with mock.patch(
            "open_trajectory_harness.ot0077_design_probe._run_public_design_probe",
            return_value=(wrong, self.payload),
        ):
            with self.assertRaises(DesignProbeError):
                assert_public_design()


if __name__ == "__main__":
    unittest.main()
