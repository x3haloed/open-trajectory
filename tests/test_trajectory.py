from __future__ import annotations

import json
import pickle
import unittest

from open_trajectory_harness.ot0002 import canonical_json, sha256_bytes
from open_trajectory_harness.trajectory import (
    ACTOR_SOURCE,
    CONTROLLER_SOURCE,
    MAX_RECORD_BYTES,
    PROJECTION_BYTE_LIMIT,
    TrajectoryStore,
    WORLD_SOURCE,
    bootstrap_trajectory_store,
)


class TrajectoryStoreTests(unittest.TestCase):
    def test_bootstrap_separates_store_local_opaque_capabilities(self) -> None:
        store, actor, world, controller = bootstrap_trajectory_store()
        other, other_actor, _, _ = bootstrap_trajectory_store()

        with self.assertRaises(TypeError):
            TrajectoryStore()
        for attribute in (
            "actor_channel",
            "world_channel",
            "controller_channel",
        ):
            self.assertFalse(hasattr(store, attribute))
            self.assertNotIn(attribute, dir(store))
        public_values = [
            getattr(store, name)
            for name in dir(store)
            if not name.startswith("_")
        ]
        for capability in (actor, world, controller):
            self.assertTrue(all(value is not capability for value in public_values))

        with self.assertRaises(PermissionError):
            store.append(ACTOR_SOURCE, {"record": "forged"})
        with self.assertRaises(PermissionError):
            store.append(object(), {"record": "forged"})
        with self.assertRaises(PermissionError):
            other.append(actor, {"record": "cross-store"})
        with self.assertRaises(PermissionError):
            store.append(other_actor, {"record": "cross-store"})
        with self.assertRaises(TypeError):
            canonical_json(actor)
        with self.assertRaises(TypeError):
            pickle.dumps(actor)

        actor_id = store.append(
            actor,
            {"record": "spoof", "source": WORLD_SOURCE},
        )
        controller_id = store.append(
            controller,
            {"record": "spoof", "source": ACTOR_SOURCE},
        )
        self.assertEqual(store.get(actor_id)["source"], ACTOR_SOURCE)
        self.assertEqual(
            store.get(controller_id)["source"], CONTROLLER_SOURCE
        )

    def test_record_identity_parent_validation_and_canonical_order(self) -> None:
        store, actor, world, controller = bootstrap_trajectory_store()
        first = store.append(actor, {"record": "first"})
        second = store.append(world, {"record": "second"})
        child = store.append(
            controller,
            {"record": "child"},
            [second, first, second],
        )
        record = store.get(child)

        self.assertEqual(record["parents"], sorted([first, second]))
        self.assertEqual(child, sha256_bytes(canonical_json(record)))
        self.assertEqual(
            child,
            store.append(
                controller,
                {"record": "child"},
                [first, second],
            ),
        )
        with self.assertRaises(KeyError):
            store.append(actor, {}, ["0" * 64])
        with self.assertRaises(ValueError):
            store.append(actor, {}, ["A" * 64])
        with self.assertRaises(TypeError):
            store.append(actor, {}, first)

    def test_exact_duplicates_deduplicate_and_records_are_immutable(self) -> None:
        store, actor, world, _ = bootstrap_trajectory_store()
        payload = {"nested": {"values": [1, 2]}}
        record_id = store.append(actor, payload)
        payload["nested"]["values"].append(3)

        detached = store.get(record_id)
        detached["payload"]["nested"]["values"].append(4)
        self.assertEqual(
            store.get(record_id)["payload"],
            {"nested": {"values": [1, 2]}},
        )
        self.assertEqual(
            store.append(
                actor,
                {"nested": {"values": [1, 2]}},
            ),
            record_id,
        )
        self.assertEqual(len(store), 1)
        self.assertNotEqual(
            store.append(
                world,
                {"nested": {"values": [1, 2]}},
            ),
            record_id,
        )

        projection = store.full_projection()
        projection["records"][0]["record"]["payload"] = {"changed": True}
        self.assertEqual(
            store.get(record_id)["payload"],
            {"nested": {"values": [1, 2]}},
        )

    def test_payload_must_be_an_ordinary_finite_json_object(self) -> None:
        store, actor, _, _ = bootstrap_trajectory_store()
        with self.assertRaises(TypeError):
            store.append(actor, ["not", "an", "object"])
        with self.assertRaises(TypeError):
            store.append(actor, {"bad": object()})
        with self.assertRaises(TypeError):
            store.append(actor, {1: "non-string key"})
        with self.assertRaises(ValueError):
            store.append(actor, {"bad": float("nan")})
        cycle: dict[str, object] = {}
        cycle["cycle"] = cycle
        with self.assertRaises(ValueError):
            store.append(actor, cycle)

    def test_record_limit_counts_exact_canonical_bytes(self) -> None:
        store, actor, _, _ = bootstrap_trajectory_store()
        empty_record = {
            "source": ACTOR_SOURCE,
            "parents": [],
            "payload": {"padding": ""},
        }
        padding_length = MAX_RECORD_BYTES - len(canonical_json(empty_record))
        exact_payload = {"padding": "x" * padding_length}
        exact_id = store.append(actor, exact_payload)
        self.assertEqual(len(canonical_json(store.get(exact_id))), MAX_RECORD_BYTES)

        with self.assertRaises(ValueError):
            store.append(
                actor,
                {"padding": "x" * (padding_length + 1)},
            )

    def test_projection_is_exact_address_selected_and_reports_external_parents(
        self,
    ) -> None:
        store, actor, world, _ = bootstrap_trajectory_store()
        active = store.append(actor, {"record": "active"})
        proposal = store.append(
            actor,
            {"record": "proposal"},
            [active],
        )
        trial = store.append(
            world,
            {"record": "trial", "proposal_id": proposal},
            [proposal],
        )
        unrelated = store.append(actor, {"record": "unrelated"})

        projection = store.project([trial, proposal, trial])
        self.assertEqual(
            set(projection),
            {"schema_version", "record_ids", "records", "external_parents"},
        )
        self.assertEqual(projection["schema_version"], 1)
        self.assertEqual(projection["record_ids"], sorted([proposal, trial]))
        self.assertEqual(
            [entry["record_id"] for entry in projection["records"]],
            sorted([proposal, trial]),
        )
        self.assertTrue(
            all(set(entry) == {"record_id", "record"} for entry in projection["records"])
        )
        self.assertEqual(projection["external_parents"], [active])
        self.assertNotIn(unrelated, projection["record_ids"])
        self.assertNotIn(active, projection["record_ids"])
        self.assertEqual(
            store.serialize_projection([trial, proposal]),
            canonical_json(projection),
        )

        projected_lookup = {
            entry["record_id"]: entry["record"]
            for entry in json.loads(store.serialize_projection([proposal]))[
                "records"
            ]
        }
        self.assertNotIn(active, projected_lookup)
        self.assertNotIn(trial, projected_lookup)

    def test_unknown_records_fail_closed(self) -> None:
        store, _, _, _ = bootstrap_trajectory_store()
        missing = "f" * 64
        with self.assertRaises(KeyError):
            store.get(missing)
        with self.assertRaises(KeyError):
            store.project([missing])
        with self.assertRaises(ValueError):
            store.get("not-an-identity")

    def test_full_serialization_uses_projection_schema_without_budget(self) -> None:
        store, actor, _, _ = bootstrap_trajectory_store()
        empty_record = {
            "source": ACTOR_SOURCE,
            "parents": [],
            "payload": {"padding": ""},
        }
        padding_length = MAX_RECORD_BYTES - len(canonical_json(empty_record))
        large = store.append(
            actor,
            {"padding": "x" * padding_length},
        )

        with self.assertRaises(ValueError):
            store.serialize_projection([large])
        with self.assertRaises(ValueError):
            store.project([large], byte_limit=PROJECTION_BYTE_LIMIT + 1)

        raw = store.serialize_full()
        full = json.loads(raw)
        self.assertGreater(len(raw), PROJECTION_BYTE_LIMIT)
        self.assertEqual(raw, canonical_json(store.full_projection()))
        self.assertEqual(full["record_ids"], [large])
        self.assertEqual(full["external_parents"], [])
        self.assertEqual(
            set(full),
            {"schema_version", "record_ids", "records", "external_parents"},
        )


if __name__ == "__main__":
    unittest.main()
