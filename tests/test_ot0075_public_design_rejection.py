from __future__ import annotations

import unittest

from open_trajectory_harness.ot0075_learning import (
    COMPACT_REFERENCE,
    IMMUTABLE_SEED_CONTROL,
    encode_state,
    initial_state,
    predict,
    update,
)
from open_trajectory_harness.ot0075_protocol import build_design_task
from open_trajectory_harness.ot0075_scoring import (
    CAUSAL_INTERVENTIONS,
    RECURRENCE_INTERVENTION,
    REQUIRED_CONTROLS,
    _metric_summary,
    _reference_gate,
)


def _events(case: dict[str, object]) -> list[dict[str, object]]:
    return [
        event
        for episode in case["episodes"]
        for event in episode["events"]
    ]


def _predictions(
    mechanism: str,
    events: list[dict[str, object]],
    *,
    deliver_updates: bool,
) -> list[int]:
    projection = encode_state(mechanism, initial_state(mechanism))
    predictions = []
    for event in events:
        public_query = event["public_query"]
        prediction = predict(mechanism, projection, public_query).prediction
        predictions.append(prediction)
        if deliver_updates:
            projection = encode_state(
                mechanism,
                update(
                    mechanism,
                    projection,
                    public_query,
                    prediction,
                    event["outcome"],
                ).state,
            )
    return predictions


def _metrics(
    predictions: list[int],
    outcomes: list[int],
    episodes: list[dict[str, int]],
) -> dict[str, object]:
    return _metric_summary(
        {
            "outcomes": outcomes,
            "predictions": predictions,
            "prediction_statuses": ["valid"] * len(outcomes),
        },
        episodes,
    )


class OT0075PublicDesignRejectionTests(unittest.TestCase):
    def test_case_11_fixed_initial_ablation_fails_frozen_causal_rule(self) -> None:
        case = build_design_task(0)["cases"][11]
        events = _events(case)
        outcomes = [event["outcome"] for event in events]
        episodes = [
            {
                "dwell": episode["dwell"],
                "episode_index": episode["episode_index"],
            }
            for episode in case["episodes"]
        ]

        live = _metrics(
            _predictions(COMPACT_REFERENCE, events, deliver_updates=True),
            outcomes,
            episodes,
        )
        immutable = _metrics(
            _predictions(IMMUTABLE_SEED_CONTROL, events, deliver_updates=False),
            outcomes,
            episodes,
        )
        withheld = _metrics(
            _predictions(COMPACT_REFERENCE, events, deliver_updates=False),
            outcomes,
            episodes,
        )

        # Supply the scorer's complete reference-gate inventory. Only the
        # consequence-withholding entry is the witness under test; its metrics
        # above come directly from the actual fixed-initial ablation semantics.
        scorer_metrics = {
            ("positive-reference", COMPACT_REFERENCE, COMPACT_REFERENCE, None): live,
            **{
                ("required-control", control, None, None): immutable
                for control in REQUIRED_CONTROLS
            },
            **{
                (
                    "causal-intervention",
                    intervention,
                    COMPACT_REFERENCE,
                    intervention,
                ): withheld
                for intervention in CAUSAL_INTERVENTIONS
            },
            (
                "recurrence-intervention",
                RECURRENCE_INTERVENTION,
                COMPACT_REFERENCE,
                RECURRENCE_INTERVENTION,
            ): live,
        }
        result = _reference_gate(COMPACT_REFERENCE, scorer_metrics)
        withholding = next(
            item
            for item in result["causal_interventions"]
            if item["intervention_id"] == "consequence-withholding"
        )

        self.assertEqual(immutable["errors"], 132)
        self.assertEqual(live["errors"], 19)
        self.assertEqual(withheld["errors"], 115)
        self.assertEqual(result["live_advantage"], 113)
        self.assertEqual(withholding["surviving_advantage"], 17)
        self.assertGreater(10 * 17, 113)
        self.assertFalse(withholding["causal_loss_pass"])
        self.assertFalse(result["gates"]["causal_interventions"])
        self.assertFalse(result["pass"])


if __name__ == "__main__":
    unittest.main()
