from __future__ import annotations

import copy
import gc
import hashlib
import os
import struct
import tempfile
import threading
import unittest
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from open_trajectory_harness.ot0002 import canonical_json, sha256_bytes
from open_trajectory_harness import ot0077_journal as journal
from open_trajectory_harness.ot0077_journal import (
    JournalError,
    SCOPES,
    SegmentedEncounterJournal,
    read_segment,
    read_stage,
    reassemble_chain,
)
from open_trajectory_harness.ot0077_receipts import (
    ENVIRONMENT_KEYS,
    SENTINEL_CHANNELS,
    ReceiptChainBuilder,
    derive_identity,
    make_consumer_facts,
    strict_online_surface,
    validate_chain,
)


TASK_SHA256 = derive_identity("journal-test-task")
SCIENTIFIC_SHA256 = derive_identity("journal-test-scientific")
EXECUTION_GIT_COMMIT = "a" * 40
RUN_ID = "ot-0077-journal-test-001"
LOGICAL_PATH = "$EVIDENCE/tests/OT-0077/journal-test-001"


def environment() -> dict[str, object]:
    value = {
        "architecture": "arm64",
        "git_commit": EXECUTION_GIT_COMMIT,
        "git_dirty": False,
        "os_family": "Darwin",
        "python_implementation": "CPython",
        "python_version": "3.13.7",
    }
    assert set(value) == ENVIRONMENT_KEYS
    return value


def consumer(label: str) -> dict[str, object]:
    nonce = derive_identity("journal-test-sentinel-nonce", label)
    return make_consumer_facts(
        process_challenge_sha256=derive_identity("journal-test-process", label),
        workspace_challenge_sha256=derive_identity("journal-test-workspace", label),
        response_bytes=canonical_json({"test_response": label}),
        descriptor_audit_pass=False,
        attempt_status="completed",
        failure_code=None,
        prediction_status="valid",
        process_boundary="in-process",
        process_started=False,
        fresh_process_verified=False,
        workspace_observed=True,
        environment_fingerprint=environment(),
        sentinel_results=[
            {
                "channel": channel,
                "checked": True,
                "observed": False,
                "planted": True,
                "sentinel_sha256": derive_identity(
                    "journal-test-sentinel", nonce, channel
                ),
            }
            for channel in SENTINEL_CHANNELS
        ],
    )


def query(case_index: int, encounter_index: int) -> dict[str, object]:
    return {
        "episode_start": encounter_index == 0,
        "feature_bits": format((case_index + encounter_index) % 4095 + 1, "012b"),
        "query_id": derive_identity(
            "journal-test-query", case_index, encounter_index
        ),
        "schema_version": 1,
    }


def build_chain(case_index: int, *, horizon: int = 2) -> dict[str, object]:
    label = f"case-{case_index}"
    initial_state = f"state-{case_index}-0".encode()
    builder = ReceiptChainBuilder(
        task_sha256=TASK_SHA256,
        case_id=derive_identity("journal-test-case", case_index),
        case_index=case_index,
        horizon=horizon,
        condition_id=derive_identity("journal-test-condition", case_index),
        display_label=label,
        lineage_class="online-positive-surrogate",
        branch_token="genesis",
        surface=strict_online_surface(),
        initial_state=initial_state,
        initial_projection=initial_state,
        first_consumer_facts=consumer(f"{label}-0"),
    )
    authoritative_state = initial_state
    for encounter_index in range(horizon):
        post_state = f"state-{case_index}-{encounter_index + 1}".encode()
        outcome = (case_index + encounter_index) & 1
        builder.append_encounter(
            public_query=query(case_index, encounter_index),
            episode_index=0,
            prediction=outcome,
            outcome=outcome,
            update_decision="update",
            authoritative_pre_state=authoritative_state,
            update_payload=f"update-{case_index}-{encounter_index}".encode(),
            post_state=post_state,
            next_projection=post_state,
            next_consumer_facts=consumer(f"{label}-{encounter_index + 1}"),
        )
        authoritative_state = post_state
    chain = builder.finish()
    validate_chain(chain)
    return chain


def expected_counts(*, segments: int, encounters: int) -> dict[str, dict[str, int]]:
    return {
        scope: {
            "segments": segments if scope == "main" else 0,
            "encounters": encounters if scope == "main" else 0,
        }
        for scope in SCOPES
    }


def create_stage(
    root: Path, *, case_count: int, segment_count: int, encounter_count: int
) -> SegmentedEncounterJournal:
    return SegmentedEncounterJournal.create(
        root,
        run_id=RUN_ID,
        logical_path=LOGICAL_PATH,
        purpose="design",
        task_sha256=TASK_SHA256,
        execution_git_commit=EXECUTION_GIT_COMMIT,
        expected_case_count=case_count,
        expected_scope_counts=expected_counts(
            segments=segment_count, encounters=encounter_count
        ),
    )


def open_chain_writer(
    stage: SegmentedEncounterJournal, chain: dict[str, object]
):
    receipts = chain["receipt_order"]
    assert isinstance(receipts, list)
    validation = validate_chain(chain)
    lineage = receipts[2]["payload"]
    case = receipts[0]["payload"]
    return stage.open_segment(
        scope="main",
        case_id=validation.case_id,
        case_index=case["case_index"],
        condition_id=lineage["condition_id"],
        lineage_id=validation.lineage_id,
        branch_id=validation.branch_id,
        encounter_start=validation.encounter_start,
        encounter_count=validation.encounter_count,
        initial_receipts=receipts[:5],
    )


def append_chain(
    writer,
    chain: dict[str, object],
    *,
    through_encounters: int | None = None,
    terminal_consumer: bool = True,
) -> None:
    receipts = chain["receipt_order"]
    assert isinstance(receipts, list)
    encounter_count = chain["encounter_count"]
    encounter_start = chain["encounter_start"]
    assert isinstance(encounter_count, int)
    assert isinstance(encounter_start, int)
    if through_encounters is None:
        through_encounters = encounter_count
    cursor = 5
    for offset in range(through_encounters):
        writer.append_consumer(receipts[cursor])
        cursor += 1
        writer.append_encounter(
            encounter_start + offset,
            receipts[cursor : cursor + 8],
        )
        cursor += 8
    if through_encounters == encounter_count and terminal_consumer:
        writer.append_consumer(receipts[cursor])


def write_chain(
    stage: SegmentedEncounterJournal,
    chain: dict[str, object],
    *,
    barrier: threading.Barrier | None = None,
) -> None:
    writer = open_chain_writer(stage, chain)
    try:
        if barrier is not None:
            barrier.wait(timeout=10)
        append_chain(writer, chain)
        writer.seal(chain)
    finally:
        writer.abort()


def only_segment(root: Path) -> Path:
    entries = list((root / journal.SEGMENT_DIRECTORY_NAME).iterdir())
    if len(entries) != 1:
        raise AssertionError(f"expected one segment, got {len(entries)}")
    return entries[0]


class PrefixLinearizationTests(unittest.TestCase):
    def test_incremental_prefix_validation_matches_the_full_graph_reference(
        self,
    ) -> None:
        chain = build_chain(0, horizon=4)
        valid = copy.deepcopy(chain["receipt_order"])
        missing_parent = copy.deepcopy(valid)
        del missing_parent[3]
        forward_parent = copy.deepcopy(valid)
        forward_parent[5], forward_parent[6] = (
            forward_parent[6],
            forward_parent[5],
        )
        duplicate = [*copy.deepcopy(valid), copy.deepcopy(valid[-1])]

        def legacy_outcome(receipts):
            seen = set()
            try:
                for receipt in receipts:
                    receipt_sha256 = receipt["receipt_sha256"]
                    if receipt_sha256 in seen:
                        raise JournalError("journal receipt identity is duplicated")
                    for parent in receipt["parents"]:
                        if parent["receipt_sha256"] not in seen:
                            raise JournalError(
                                "journal receipt parent is absent from its causal prefix"
                            )
                    seen.add(receipt_sha256)
            except JournalError as error:
                return ("error", str(error))
            return ("ok", frozenset(seen))

        def incremental_outcome(receipts, width):
            seen = set()
            try:
                for start in range(0, len(receipts), width):
                    additions = journal._validate_prefix_extension(
                        seen, receipts[start : start + width]
                    )
                    seen.update(additions)
            except JournalError as error:
                return ("error", str(error))
            return ("ok", frozenset(seen))

        for label, receipts in (
            ("valid", valid),
            ("missing-parent", missing_parent),
            ("forward-parent", forward_parent),
            ("duplicate", duplicate),
        ):
            expected = legacy_outcome(receipts)
            for width in (1, 2, 7, 19, len(receipts) + 1):
                with self.subTest(label=label, width=width):
                    self.assertEqual(
                        incremental_outcome(receipts, width), expected
                    )

    def test_incremental_writer_preserves_exact_frame_and_chain_identity(self) -> None:
        chain = build_chain(0, horizon=5)
        receipts = chain["receipt_order"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=5
            )
            writer = open_chain_writer(stage, chain)
            opened = copy.deepcopy(writer._opened)
            expected_records = [copy.deepcopy(opened)]
            cursor = 5
            for offset in range(chain["encounter_count"]):
                encounter_index = chain["encounter_start"] + offset
                consumer_receipt = copy.deepcopy(receipts[cursor])
                cursor += 1
                expected_records.append(
                    {
                        "branch_id": opened["branch_id"],
                        "case_id": opened["case_id"],
                        "condition_id": opened["condition_id"],
                        "encounter_index": encounter_index,
                        "experiment_id": journal.EXPERIMENT_ID,
                        "lineage_id": opened["lineage_id"],
                        "mode": "prediction",
                        "receipt": consumer_receipt,
                        "record_kind": "consumer-checkpoint",
                        "schema_version": journal.SCHEMA_VERSION,
                        "scope": opened["scope"],
                    }
                )
                writer.append_consumer(consumer_receipt)
                committed = copy.deepcopy(receipts[cursor : cursor + 8])
                cursor += 8
                expected_records.append(
                    {
                        "branch_id": opened["branch_id"],
                        "case_id": opened["case_id"],
                        "condition_id": opened["condition_id"],
                        "encounter_index": encounter_index,
                        "experiment_id": journal.EXPERIMENT_ID,
                        "lineage_id": opened["lineage_id"],
                        "receipt_count": 8,
                        "receipts": committed,
                        "record_kind": "encounter-commit",
                        "schema_version": journal.SCHEMA_VERSION,
                        "scope": opened["scope"],
                    }
                )
                writer.append_encounter(encounter_index, committed)

            terminal_consumer = copy.deepcopy(receipts[cursor])
            expected_records.append(
                {
                    "branch_id": opened["branch_id"],
                    "case_id": opened["case_id"],
                    "condition_id": opened["condition_id"],
                    "encounter_index": None,
                    "experiment_id": journal.EXPERIMENT_ID,
                    "lineage_id": opened["lineage_id"],
                    "mode": "terminal-audit",
                    "receipt": terminal_consumer,
                    "record_kind": "consumer-checkpoint",
                    "schema_version": journal.SCHEMA_VERSION,
                    "scope": opened["scope"],
                }
            )
            writer.append_consumer(terminal_consumer)
            expected_seal = {
                "branch_id": opened["branch_id"],
                "case_id": opened["case_id"],
                "case_receipt_sha256": chain["case_receipt_sha256"],
                "condition_id": opened["condition_id"],
                "encounter_count": opened["encounter_count"],
                "encounter_start": opened["encounter_start"],
                "experiment_id": journal.EXPERIMENT_ID,
                "lineage_id": opened["lineage_id"],
                "lineage_receipt_sha256": chain["lineage_receipt_sha256"],
                "receipt_order_sha256": sha256_bytes(canonical_json(receipts)),
                "record_kind": "lineage-seal",
                "schema_version": journal.SCHEMA_VERSION,
                "scope": opened["scope"],
                "summary": copy.deepcopy(chain["summary"]),
                "terminal_audit_receipt_sha256": chain[
                    "terminal_audit_receipt_sha256"
                ],
                "trace_sha256": chain["trace_sha256"],
            }
            self.assertEqual(writer.seal(chain), expected_seal)
            expected_records.append(expected_seal)

            expected_bytes = b"".join(
                journal._encode_frame(record) for record in expected_records
            )
            segment_path = only_segment(root)
            self.assertEqual(segment_path.read_bytes(), expected_bytes)
            restored = read_segment(segment_path)
            self.assertEqual(list(restored.records), expected_records)
            self.assertEqual(reassemble_chain(restored), chain)

    def test_prefix_validation_visits_scale_exactly_with_new_receipts(self) -> None:
        def measured_visits(horizon):
            chain = build_chain(0, horizon=horizon)
            receipt_count = len(chain["receipt_order"])
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "journal"
                stage = create_stage(
                    root,
                    case_count=1,
                    segment_count=1,
                    encounter_count=horizon,
                )
                original = journal._validate_prefix_extension
                writer_visits = 0

                def count_writer(receipt_ids, additions):
                    nonlocal writer_visits
                    writer_visits += len(additions)
                    return original(receipt_ids, additions)

                with mock.patch.object(
                    journal,
                    "_validate_prefix_extension",
                    side_effect=count_writer,
                ), mock.patch.object(journal, "_sync_fd", return_value=None):
                    writer = open_chain_writer(stage, chain)
                    append_chain(writer, chain)
                    writer.seal(chain)

                reader_visits = 0

                def count_reader(receipt_ids, additions):
                    nonlocal reader_visits
                    reader_visits += len(additions)
                    return original(receipt_ids, additions)

                with mock.patch.object(
                    journal,
                    "_validate_prefix_extension",
                    side_effect=count_reader,
                ):
                    restored = read_segment(only_segment(root))
                self.assertEqual(reassemble_chain(restored), chain)
            return receipt_count, writer_visits, reader_visits

        small = measured_visits(4)
        large = measured_visits(64)
        for receipt_count, writer_visits, reader_visits in (small, large):
            # The five roots are checked once by the stage and once by the
            # writer/reader.  Every later receipt is visited exactly once.
            self.assertEqual(writer_visits, receipt_count + 5)
            self.assertEqual(reader_visits, receipt_count + 5)
        self.assertEqual(large[1] - small[1], large[0] - small[0])
        self.assertEqual(large[2] - small[2], large[0] - small[0])


class EncounterCheckpointTests(unittest.TestCase):
    def test_encounter_commit_syncs_eight_receipts_before_next_consumer(self) -> None:
        chain = build_chain(0, horizon=2)
        receipts = chain["receipt_order"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=2
            )
            with mock.patch.object(
                journal, "_sync_fd", wraps=journal._sync_fd
            ) as sync:
                writer = open_chain_writer(stage, chain)
                self.assertEqual(sync.call_count, 1)  # lineage-open
                writer.append_consumer(receipts[5])
                self.assertEqual(sync.call_count, 2)
                writer.append_encounter(0, receipts[6:14])
                self.assertEqual(sync.call_count, 3)
                writer.abort()  # consumer_1 never returned

            retained = read_segment(only_segment(root), allow_incomplete=True)
            self.assertFalse(retained.sealed)
            self.assertFalse(retained.torn_tail)
            self.assertEqual(retained.completed_encounter_count, 1)
            self.assertEqual(list(retained.receipt_order), receipts[:14])
            self.assertEqual(retained.receipt_order[-1]["kind"], "projection")
            self.assertEqual(
                retained.receipt_order[-1]["context"]["encounter_index"], 1
            )
            with self.assertRaisesRegex(JournalError, "unsealed"):
                read_segment(only_segment(root))
            with self.assertRaisesRegex(JournalError, "unsealed"):
                stage.seal(scientific_sha256=SCIENTIFIC_SHA256)
            self.assertFalse((root / journal.STAGE_SEAL_NAME).exists())

            incomplete = read_stage(root, allow_incomplete=True)
            self.assertFalse(incomplete.sealed)
            self.assertEqual(
                incomplete.segments[0].completed_encounter_count, 1
            )

    def test_terminal_consumer_is_its_own_checkpoint_before_seal(self) -> None:
        chain = build_chain(0, horizon=1)
        receipts = chain["receipt_order"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=1
            )
            writer = open_chain_writer(stage, chain)
            append_chain(writer, chain, terminal_consumer=False)
            prefix = read_segment(only_segment(root), allow_incomplete=True)
            self.assertEqual(list(prefix.receipt_order), receipts[:-1])
            self.assertEqual(prefix.receipt_order[-1]["kind"], "projection")
            with self.assertRaisesRegex(JournalError, "terminal consumer"):
                writer.seal(chain)
            writer.append_consumer(receipts[-1])
            with_terminal = read_segment(only_segment(root), allow_incomplete=True)
            self.assertEqual(list(with_terminal.receipt_order), receipts)
            self.assertFalse(with_terminal.sealed)
            writer.seal(chain)
            complete = read_segment(only_segment(root))
            self.assertEqual(reassemble_chain(complete), chain)


class FrameFailureTests(unittest.TestCase):
    def test_torn_seal_retains_all_completed_receipts_but_not_success(self) -> None:
        chain = build_chain(0, horizon=2)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=2
            )
            write_chain(stage, chain)
            segment_path = only_segment(root)
            os.chmod(segment_path, 0o600)
            raw = segment_path.read_bytes()
            segment_path.write_bytes(raw[:-7])

            retained = read_segment(segment_path, allow_incomplete=True)
            self.assertTrue(retained.torn_tail)
            self.assertFalse(retained.sealed)
            self.assertEqual(retained.completed_encounter_count, 2)
            self.assertEqual(list(retained.receipt_order), chain["receipt_order"])
            with self.assertRaisesRegex(JournalError, "frame payload"):
                read_segment(segment_path)

    def test_complete_corruption_and_noncanonical_json_fail_even_in_prefix_mode(self) -> None:
        chain = build_chain(0, horizon=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=1
            )
            write_chain(stage, chain)
            segment_path = only_segment(root)
            os.chmod(segment_path, 0o600)
            raw = bytearray(segment_path.read_bytes())
            raw[12] ^= 1  # first complete frame's retained raw SHA-256
            segment_path.write_bytes(raw)
            with self.assertRaisesRegex(JournalError, "content identity"):
                read_segment(segment_path, allow_incomplete=True)

        noncanonical = b'{"b":1, "a":2}\n'
        compressed = zlib.compress(noncanonical, level=1)
        header = struct.pack(
            ">4sII32s",
            journal.FRAME_MAGIC,
            len(noncanonical),
            len(compressed),
            hashlib.sha256(noncanonical).digest(),
        )
        with self.assertRaisesRegex(JournalError, "not canonical"):
            journal._decode_frame(header, compressed)

    def test_complete_frame_after_lineage_seal_is_rejected(self) -> None:
        chain = build_chain(0, horizon=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=1
            )
            write_chain(stage, chain)
            segment_path = only_segment(root)
            os.chmod(segment_path, 0o600)
            with segment_path.open("ab") as handle:
                handle.write(journal._encode_frame({"record_kind": "trailing"}))
                handle.flush()
                os.fsync(handle.fileno())
            with self.assertRaisesRegex(JournalError, "ceiling"):
                read_segment(segment_path, allow_incomplete=True)

    def test_alternate_zlib_encoding_is_not_a_canonical_frame(self) -> None:
        record = {"payload": "abcde" * 2_000}
        raw = canonical_json(record)
        compressed = zlib.compress(raw, level=9)
        self.assertNotEqual(compressed, zlib.compress(raw, level=1))
        header = struct.pack(
            ">4sII32s",
            journal.FRAME_MAGIC,
            len(raw),
            len(compressed),
            hashlib.sha256(raw).digest(),
        )
        with self.assertRaisesRegex(JournalError, "compression is not canonical"):
            journal._decode_frame(header, compressed)


class ExclusivityAndLayoutTests(unittest.TestCase):
    def test_duplicate_deterministic_segment_is_exclusive_and_retained(self) -> None:
        chain = build_chain(0, horizon=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=1
            )
            writer = open_chain_writer(stage, chain)
            before = only_segment(root).read_bytes()
            with self.assertRaisesRegex(JournalError, "already exists"):
                open_chain_writer(SegmentedEncounterJournal.open(root), chain)
            self.assertEqual(only_segment(root).read_bytes(), before)
            writer.abort()

    def test_abandoned_writer_destructor_closes_without_erasing_prefix(self) -> None:
        chain = build_chain(0, horizon=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=1
            )
            writer = open_chain_writer(stage, chain)
            writer.append_consumer(chain["receipt_order"][5])
            descriptor = writer._fd
            del writer
            gc.collect()
            with self.assertRaises(OSError):
                os.fstat(descriptor)
            retained = read_segment(only_segment(root), allow_incomplete=True)
            self.assertEqual(
                [item["kind"] for item in retained.receipt_order[-2:]],
                ["projection", "consumer"],
            )

    def test_stage_ceiling_rejects_extra_entries_before_segment_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            SegmentedEncounterJournal.create(
                root,
                run_id=RUN_ID,
                logical_path=LOGICAL_PATH,
                purpose="design",
                task_sha256=TASK_SHA256,
                execution_git_commit=EXECUTION_GIT_COMMIT,
                expected_case_count=1,
                expected_scope_counts=expected_counts(segments=0, encounters=0),
            )
            (root / journal.SEGMENT_DIRECTORY_NAME / "unexpected.tmp").touch()
            with mock.patch.object(
                journal, "read_segment", side_effect=AssertionError("must not read")
            ) as reader:
                with self.assertRaisesRegex(JournalError, "entry ceiling"):
                    read_stage(root, allow_incomplete=True)
                reader.assert_not_called()

    def test_segment_byte_ceiling_is_derived_from_declared_encounters(self) -> None:
        chain = build_chain(0, horizon=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=1
            )
            writer = open_chain_writer(stage, chain)
            writer.abort()
            segment_path = only_segment(root)
            declared_ceiling = (2 * 1 + 3) * journal.MAX_ENCODED_FRAME_BYTES
            with segment_path.open("r+b") as handle:
                handle.truncate(declared_ceiling + 1)
            with self.assertRaisesRegex(JournalError, "byte ceiling"):
                read_stage(root, allow_incomplete=True)

    def test_unexpected_segment_entry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            create_stage(root, case_count=1, segment_count=1, encounter_count=1)
            (root / journal.SEGMENT_DIRECTORY_NAME / "unexpected.tmp").touch()
            with self.assertRaisesRegex(JournalError, "unexpected entry"):
                read_stage(root, allow_incomplete=True)

    def test_logical_identity_never_serializes_physical_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=1, encounter_count=1
            )
            encoded = canonical_json(stage.stage_open)
            self.assertNotIn(str(root).encode(), encoded)
            self.assertIn(LOGICAL_PATH.encode(), encoded)


class StageBindingTests(unittest.TestCase):
    def test_stage_binding_is_independent_of_segment_completion_order(self) -> None:
        chains = [build_chain(index, horizon=2) for index in range(3)]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = create_stage(
                base / "first",
                case_count=3,
                segment_count=3,
                encounter_count=6,
            )
            second = create_stage(
                base / "second",
                case_count=3,
                segment_count=3,
                encounter_count=6,
            )
            for chain in chains:
                write_chain(first, chain)
            for chain in reversed(chains):
                write_chain(second, chain)

            first_binding = first.seal(scientific_sha256=SCIENTIFIC_SHA256)
            second_binding = second.seal(scientific_sha256=SCIENTIFIC_SHA256)
            self.assertEqual(first_binding, second_binding)
            self.assertNotIn(str(base), canonical_json(first_binding).decode())

            restored = read_stage(
                base / "first",
                expected_scientific_sha256=SCIENTIFIC_SHA256,
            )
            self.assertTrue(restored.sealed)
            self.assertEqual(restored.binding, first_binding)
            self.assertEqual(restored.stage_seal["segment_count"], 3)
            self.assertEqual(
                restored.stage_seal["completed_encounter_count"], 6
            )
            self.assertEqual(
                restored.stage_seal["receipt_count"],
                sum(len(chain["receipt_order"]) for chain in chains),
            )
            with self.assertRaisesRegex(JournalError, "different scientific"):
                read_stage(
                    base / "first",
                    expected_scientific_sha256=derive_identity(
                        "different-scientific"
                    ),
                )

    def test_concurrent_condition_threads_produce_one_verified_stage(self) -> None:
        chains = [build_chain(index, horizon=1) for index in range(8)]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=8, segment_count=8, encounter_count=8
            )
            barrier = threading.Barrier(len(chains))
            with ThreadPoolExecutor(max_workers=len(chains)) as executor:
                futures = [
                    executor.submit(write_chain, stage, chain, barrier=barrier)
                    for chain in chains
                ]
                for future in futures:
                    future.result(timeout=20)

            binding = stage.seal(scientific_sha256=SCIENTIFIC_SHA256)
            restored = read_stage(root)
            self.assertEqual(restored.binding, binding)
            self.assertEqual(len(restored.segments), 8)
            self.assertEqual(len(set(restored.segment_relative_paths)), 8)
            self.assertTrue(all(segment.sealed for segment in restored.segments))
            self.assertEqual(
                binding["scope_counts"]["main"],
                {"encounters": 8, "receipts": 120, "segments": 8},
            )

    def test_stage_seal_refuses_wrong_frozen_counts(self) -> None:
        chain = build_chain(0, horizon=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "journal"
            stage = create_stage(
                root, case_count=1, segment_count=2, encounter_count=2
            )
            write_chain(stage, chain)
            with self.assertRaisesRegex(JournalError, "counts differ"):
                stage.seal(scientific_sha256=SCIENTIFIC_SHA256)
            self.assertFalse((root / journal.STAGE_SEAL_NAME).exists())


if __name__ == "__main__":
    unittest.main()
