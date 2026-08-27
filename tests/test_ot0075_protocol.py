from __future__ import annotations

import copy
import unittest

from open_trajectory_harness.ot0002 import canonical_json
from open_trajectory_harness.ot0075_protocol import (
    ANCHOR_CASE_COUNT,
    ANCHOR_DOMAIN,
    DESIGN_CASE_COUNT,
    DESIGN_DOMAIN,
    DIMENSION,
    DWELL_LENGTHS,
    EPISODE_SCHEDULE,
    FUTURE_CANDIDATE_DOMAIN,
    HORIZON,
    RECURRENCE_DISAMBIGUATION_PREFIX,
    ProtocolError,
    _rank,
    build_design_task,
    derive_task,
    design_seed,
    parse_bits,
    validate_task,
)


class OT0075ProtocolTests(unittest.TestCase):
    def test_derivation_is_exact_domain_separated_and_implementation_bound(
        self,
    ) -> None:
        seed = b"a" * 32
        first = derive_task(seed, "1" * 40, purpose="anchor")
        second = derive_task(seed, "1" * 40, purpose="anchor")
        changed_seed = derive_task(b"b" * 32, "1" * 40, purpose="anchor")
        changed_implementation = derive_task(seed, "2" * 40, purpose="anchor")
        design = derive_task(seed, "1" * 40, purpose="design")

        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertNotEqual(canonical_json(first), canonical_json(changed_seed))
        self.assertNotEqual(
            first["cases"],
            changed_implementation["cases"],
        )
        self.assertNotEqual(first["domain"], design["domain"])
        self.assertEqual(
            len({DESIGN_DOMAIN, ANCHOR_DOMAIN, FUTURE_CANDIDATE_DOMAIN}),
            3,
        )

    def test_anchor_world_has_long_variable_recurrent_hidden_streams(
        self,
    ) -> None:
        task = derive_task(b"c" * 32, "3" * 40, purpose="anchor")
        self.assertEqual(task["case_count"], ANCHOR_CASE_COUNT)
        for case in task["cases"]:
            self.assertEqual(case["horizon"], HORIZON)
            self.assertEqual(
                [episode["semantic_rule"] for episode in case["episodes"]],
                list(EPISODE_SCHEDULE),
            )
            self.assertEqual(
                sorted(episode["dwell"] for episode in case["episodes"]),
                list(DWELL_LENGTHS),
            )
            features = []
            for episode in case["episodes"]:
                prefix = [
                    parse_bits(event["public_query"]["feature_bits"], "feature")
                    for event in episode["events"][:DIMENSION]
                ]
                self.assertEqual(_rank(prefix), DIMENSION)
                recurrence_signatures = {
                    tuple(
                        (mask & feature).bit_count() & 1
                        for feature in prefix[
                            :RECURRENCE_DISAMBIGUATION_PREFIX
                        ]
                    )
                    for mask in (
                        parse_bits(value, "hidden mask")
                        for value in case["hidden_masks"]
                    )
                }
                self.assertEqual(len(recurrence_signatures), 3)
                for local_index, event in enumerate(episode["events"]):
                    query = event["public_query"]
                    self.assertEqual(
                        set(query),
                        {
                            "episode_start",
                            "feature_bits",
                            "query_id",
                            "schema_version",
                        },
                    )
                    self.assertIs(query["episode_start"], local_index == 0)
                    self.assertNotIn("outcome", query)
                    self.assertNotIn("semantic_rule", query)
                    features.append(query["feature_bits"])
            self.assertEqual(len(features), len(set(features)))

    def test_public_design_worlds_are_fixed_and_distinct_from_private_anchors(
        self,
    ) -> None:
        tasks = [build_design_task(index) for index in range(4)]
        self.assertTrue(
            all(task["case_count"] == DESIGN_CASE_COUNT for task in tasks)
        )
        self.assertEqual(len({task["seed_sha256"] for task in tasks}), 4)
        self.assertTrue(all(task["domain"] == DESIGN_DOMAIN for task in tasks))
        self.assertNotEqual(DESIGN_DOMAIN, ANCHOR_DOMAIN)
        self.assertNotEqual(ANCHOR_DOMAIN, FUTURE_CANDIDATE_DOMAIN)

    def test_tampering_with_world_truth_or_public_surface_fails_closed(self) -> None:
        task = derive_task(design_seed(0), "0" * 40, purpose="design")
        wrong_outcome = copy.deepcopy(task)
        wrong_outcome["cases"][0]["episodes"][0]["events"][0]["outcome"] ^= 1
        with self.assertRaises(ProtocolError):
            validate_task(wrong_outcome)

        leaked_rule = copy.deepcopy(task)
        leaked_rule["cases"][0]["episodes"][0]["events"][0][
            "public_query"
        ]["semantic_rule"] = 0
        with self.assertRaises(ProtocolError):
            validate_task(leaked_rule)

        reused_feature = copy.deepcopy(task)
        first = reused_feature["cases"][0]["episodes"][0]["events"][0][
            "public_query"
        ]["feature_bits"]
        reused_feature["cases"][0]["episodes"][1]["events"][0][
            "public_query"
        ]["feature_bits"] = first
        with self.assertRaises(ProtocolError):
            validate_task(reused_feature)

    def test_seed_commit_purpose_and_cardinality_fail_closed(self) -> None:
        with self.assertRaises(ProtocolError):
            derive_task(b"short", "0" * 40, purpose="anchor")
        with self.assertRaises(ProtocolError):
            derive_task(b"d" * 32, "short", purpose="anchor")
        with self.assertRaises(ProtocolError):
            derive_task(b"d" * 32, "0" * 40, purpose="candidate")

        wrong_cardinality = derive_task(
            b"d" * 32,
            "0" * 40,
            purpose="anchor",
        )
        wrong_cardinality["case_count"] -= 1
        wrong_cardinality["cases"].pop()
        with self.assertRaises(ProtocolError):
            validate_task(wrong_cardinality)


if __name__ == "__main__":
    unittest.main()
