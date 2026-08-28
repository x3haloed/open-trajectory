from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from unittest import mock

from open_trajectory_evidence.evidence import safe_environment
from open_trajectory_harness.ot0002 import canonical_json
from open_trajectory_harness.ot0077 import (
    ANCHOR_JOURNAL_RELATIVE_PATH,
    CLAIM_LIMIT,
    DEFAULT_RUN_ID,
    EXPERIMENT_ID,
    EXPECTED_PUBLIC_SCORE_SHA256,
    FAILED_ANCHOR_JOURNAL_RELATIVE_PATH,
    FAILURE_RELATIVE_PATH,
    RAW_RELATIVE_PATH,
    PROMOTION_ARTIFACT_ID,
    PUBLIC_CAUSAL_DESIGN_INDEX,
    PUBLIC_JOURNAL_RELATIVE_PATH,
    RAW_INPUT_MANIFESTS,
    RAW_LIMITATIONS,
    RECONSTRUCTION_SECONDS,
    RECONSTRUCTION_RECIPE,
    ProtocolError,
    _assert_preparation_boundary,
    _assert_public_design_bounded,
    _bounded_zlib_decompress,
    _bounded_command,
    _causal_evidence_ready,
    _descriptor_identity,
    _evidence_operation_bounded,
    _execute_locked_raw,
    _expected_public_causal_summary,
    _invalidate_publication,
    _learner_surface_audit,
    _manifest_binding_bounded,
    _post_raw_record_verification,
    _prepublication_summary,
    _publication_verification_passed,
    _quarantine_encounter_journal,
    _quarantine_publication,
    _journal_prefix_summary,
    _scientific_ready_except_reconstruction,
    _validate_public_checkpoint_receipt,
    decode_raw,
    encode_raw,
    finalize_after_reconstruction,
    prepare,
    run,
    build_run_lock,
    validate_run_lock,
    verify_fresh_root,
)
from open_trajectory_harness.ot0077_journal import (
    JOURNAL_FORMAT,
    SCOPES,
    STAGE_OPEN_NAME,
    SegmentedEncounterJournal,
)
from open_trajectory_harness.ot0077_design_probe import (
    EXPECTED_ROW_COUNT,
    EXPECTED_VECTOR_BYTES,
    EXPECTED_VECTOR_SHA256,
)
from open_trajectory_harness.ot0077_protocol import build_design_task, derive_task
from open_trajectory_harness.ot0077_scoring import (
    CONDITION_INVENTORY,
    metamorphic_variants,
    score_bundle,
)
from open_trajectory_harness.ot0077_shadow_scoring import score_bundle_shadow
from tests.test_ot0077_scoring import passing_bundle


COMMIT = "1" * 40
EXECUTION_COMMIT = "2" * 40


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _exact_trace_inventory(
    bundle: dict[str, object],
    primary: dict[str, object],
    shadow: dict[str, object],
) -> dict[str, dict[str, object]]:
    primary_sha256 = _sha(canonical_json(primary))
    shadow_sha256 = _sha(canonical_json(shadow))
    agreement = canonical_json(primary) == canonical_json(shadow)
    result: dict[str, dict[str, object]] = {}
    # The scoring suite separately executes every variant through both
    # independent scorers.  This lifecycle fixture needs the exact production
    # inventory, not another expensive duplicate of that scoring proof.
    for name in metamorphic_variants(bundle):
        result[name] = {
            "pass": agreement,
            "primary_sha256": primary_sha256,
            "shadow_sha256": shadow_sha256,
        }
    return result


def _prepublication_scientific() -> dict[str, object]:
    task = derive_task(b"a" * 32, COMMIT, purpose="anchor")
    task_digest = _sha(canonical_json(task))
    bundle = passing_bundle(purpose="anchor")
    for scorer_case, task_case in zip(bundle["cases"], task["cases"], strict=True):
        events = [
            event
            for episode in task_case["episodes"]
            for event in episode["events"]
        ]
        new_outcomes = [event["outcome"] for event in events]
        new_query_ids = [event["public_query"]["query_id"] for event in events]
        dwells = [episode["dwell"] for episode in task_case["episodes"]]
        episode_starts: list[int] = []
        cursor = 0
        for dwell in dwells:
            episode_starts.append(cursor)
            cursor += dwell

        for condition in scorer_case["conditions"].values():
            role = condition["role"]
            mechanism = condition["mechanism_id"]
            reference = condition["reference_id"]
            intervention = condition["intervention_id"]
            if role == "positive-reference":
                recoveries = (
                    (6, 7, 1, 8, 1, 1)
                    if mechanism == "compact-cached-affine-version-space"
                    else (7, 8, 0, 7, 1, 1)
                )
                errors = {
                    start + offset
                    for start, recovery in zip(
                        episode_starts, recoveries, strict=True
                    )
                    for offset in range(recovery)
                }
            elif role == "required-control":
                errors = set(
                    range(
                        {
                            "no-persistence": 121,
                            "immutable-seed": 120,
                            "encounter-index-clock": 130,
                            "offline-best-fixed-rule": 80,
                        }[mechanism]
                    )
                )
            elif role == "matched-frozen-control":
                errors = set(range(120))
            elif role == "adaptive-comparator":
                stride = 5 if mechanism == "recent-verbatim-world-row-window" else 6
                errors = set(range(0, len(events), stride))
            elif intervention == "one-step-stale-consequence":
                errors = set(range(100))
            elif intervention == "wrong-lineage-projection":
                errors = set(range(len(events)))
            elif role == "causal-intervention":
                errors = set(range(120))
            elif role == "recurrence-intervention":
                recoveries = (
                    (6, 7, 1, 8, 1, 1)
                    if reference == "compact-cached-affine-version-space"
                    else (7, 8, 0, 7, 1, 1)
                )
                errors = {
                    start + offset
                    for start, recovery in zip(
                        episode_starts, recoveries, strict=True
                    )
                    for offset in range(recovery)
                }
                for episode_index in (2, 4, 5):
                    errors.update(
                        range(
                            episode_starts[episode_index],
                            episode_starts[episode_index] + 4,
                        )
                    )
            else:
                errors = set(range(120))

            statuses = list(condition["prediction_statuses"])
            condition["query_ids"] = list(new_query_ids)
            condition["outcomes"] = list(new_outcomes)
            condition["predictions"] = [
                None if status != "valid" else outcome ^ int(index in errors)
                for index, (status, outcome) in enumerate(
                    zip(statuses, new_outcomes, strict=True)
                )
            ]
        by_descriptor = {
            (
                condition["role"],
                condition["mechanism_id"],
                condition["reference_id"],
                condition["intervention_id"],
            ): condition
            for condition in scorer_case["conditions"].values()
        }
        scorer_case["conditions"] = {
            _descriptor_identity(task_digest, task_case["case_id"], descriptor): (
                by_descriptor[descriptor]
            )
            for descriptor in CONDITION_INVENTORY
        }
        scorer_case["case_id"] = task_case["case_id"]
        scorer_case["case_index"] = task_case["case_index"]
        scorer_case["episodes"] = [
            {
                "episode_index": episode["episode_index"],
                "dwell": episode["dwell"],
            }
            for episode in task_case["episodes"]
        ]
        scorer_case["world_query_ids"] = new_query_ids
        scorer_case["world_outcomes"] = new_outcomes

    bundle["execution_gates"]["clean_private_reconstruction"] = False
    primary = score_bundle(bundle)
    shadow = score_bundle_shadow(bundle)
    primary_sha = _sha(canonical_json(primary))
    shadow_sha = _sha(canonical_json(shadow))
    trace_inventory = _exact_trace_inventory(bundle, primary, shadow)
    lineages = sorted(
        [
            {
                "case_id": case["case_id"],
                "case_index": case["case_index"],
                "condition_id": condition_id,
                "condition": copy.deepcopy(condition),
            }
            for case in bundle["cases"]
            for condition_id, condition in case["conditions"].items()
        ],
        key=lambda item: (item["case_index"], item["condition_id"]),
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "purpose": "anchor",
        "execution_git_commit": EXECUTION_COMMIT,
        "task": task,
        "task_sha256": task_digest,
        "candidate_outputs": False,
        "actor_turns": 0,
        "actor_tool_calls": 0,
        "hosted_model_calls": 0,
        "lineages": lineages,
        "rollback_evidence": {},
        "operational_evidence": {
            "schema_version": 1,
            "prediction_timeout_count": 0,
            "prediction_missing_count": 0,
            "condition_failure_count": 0,
            "terminal_audit_failures": [],
            "rollback_operational_failures": [],
            "verification_failures": [],
            "stage_deadline_exhausted": False,
            "globally_invalidated": False,
        },
        "gate_evidence": {
            "authority_defect_rejections": copy.deepcopy(
                bundle["authority_defect_rejections"]
            ),
            "causal_path_gates": copy.deepcopy(bundle["causal_path_gates"]),
            "rollback_replay_gates": copy.deepcopy(
                bundle["rollback_replay_gates"]
            ),
            "base_execution_gates": {
                name: bundle["execution_gates"][name]
                for name in (
                    "online_reference_authority",
                    "control_authority",
                    "adaptive_comparator_authority",
                    "state_projection_budgets",
                    "operation_budgets",
                    "fresh_reset_receipts",
                    "candidate_free",
                )
            },
        },
        "scorer_bundle": bundle,
        "primary_score": primary,
        "shadow_score": shadow,
        "scorer_independence": {
            "task_level": {
                "task_query_id_alpha_renaming": True,
                "task_case_order_reversal": True,
            },
            "trace_level": trace_inventory,
            "metamorphic_pass": all(
                result["pass"] is True for result in trace_inventory.values()
            ),
            "primary_shadow_agreement": canonical_json(primary)
            == canonical_json(shadow),
            "primary_sha256": primary_sha,
            "shadow_sha256": shadow_sha,
        },
        "verification": {
            "tests": {"status": "passed", "returncode": 0},
            "audit": {"status": "passed", "returncode": 0},
        },
        "within_wall_budget": True,
        "calibration_pass": False,
        "disposition": "invalidated",
        "authorized_actor_candidate_count": 0,
        "claim_limit": CLAIM_LIMIT,
        "encounter_journal": {},
    }


def _prepublication_raw() -> tuple[dict[str, object], bytes]:
    bundle = passing_bundle(purpose="anchor")
    bundle["execution_gates"]["clean_private_reconstruction"] = False
    primary = score_bundle(bundle)
    shadow = score_bundle_shadow(bundle)
    task = derive_task(b"a" * 32, COMMIT, purpose="anchor")
    scientific = {
        "execution_git_commit": EXECUTION_COMMIT,
        "task": task,
        "task_sha256": _sha(canonical_json(task)),
        "scorer_bundle": bundle,
        "primary_score": primary,
        "shadow_score": shadow,
    }
    raw = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "run_id": "ot-0077-e14-public-vector-identity-repair-001",
        "implementation_git_commit": COMMIT,
        "execution_git_commit": EXECUTION_COMMIT,
        "evidence_class": "private-prepublication",
        "summary": _prepublication_summary(scientific, ready=True),
        "scientific": scientific,
    }
    return raw, encode_raw(raw)


def _raw_manifest(encoded: bytes) -> dict[str, object]:
    return {
        "path": f"evidence/manifests/{EXPERIMENT_ID}/ot-0077-e14-public-vector-identity-repair-001.json",
        "manifest_bytes": 1024,
        "manifest_sha256": "4" * 64,
        "artifact_bytes": len(encoded),
        "artifact_sha256": _sha(encoded),
        "evidence_class": "private-reproducible",
        "environment_git_commit": EXECUTION_COMMIT,
        "environment_git_dirty": False,
        "readback_status": "manifest and evidence bytes verified",
    }


def _post_record_verification() -> dict[str, object]:
    return {
        "tests": {"status": "passed", "returncode": 0},
        "audit": {"status": "passed", "returncode": 0},
        "raw_manifest_readback": {
            "pass": True,
            "status": "manifest and evidence bytes verified",
        },
        "within_wall_budget": True,
    }


def _publication_contract(root: Path) -> dict[str, Path]:
    store = root / ".evidence"
    return {
        "repo": root,
        "store": store,
        "raw": store / "runs" / EXPERIMENT_ID / "raw.json.zlib",
        "raw_staging": store / "runs" / EXPERIMENT_ID / ".raw.json.zlib.pending",
        "failed_raw": store / "failures" / EXPERIMENT_ID / "raw.json.zlib",
        "failed_raw_staging": (
            store / "failures" / EXPERIMENT_ID / "raw-staging.bin"
        ),
        "completion": store / "runs" / EXPERIMENT_ID / "complete.json",
        "failed_completion": (
            store / "failures" / EXPERIMENT_ID / "complete.json"
        ),
        "reconstruction_root": store / "reconstruction" / EXPERIMENT_ID / "root",
        "failed_reconstruction_root": (
            store / "failures" / EXPERIMENT_ID / "reconstruction-root"
        ),
        "manifest": (
            root
            / "evidence"
            / "manifests"
            / EXPERIMENT_ID
            / f"{DEFAULT_RUN_ID}.json"
        ),
        "promotion": (
            store / "runs" / EXPERIMENT_ID / f"{PROMOTION_ARTIFACT_ID}.json"
        ),
        "promotion_manifest": (
            root
            / "evidence"
            / "manifests"
            / EXPERIMENT_ID
            / f"{PROMOTION_ARTIFACT_ID}.json"
        ),
        "failure": store / "failures" / EXPERIMENT_ID / "failure.json",
        "failed_manifest": (
            store / "failures" / EXPERIMENT_ID / "raw-manifest.json"
        ),
        "failed_promotion_manifest": (
            store / "failures" / EXPERIMENT_ID / "promotion-manifest.json"
        ),
        "failed_promotion": (
            store / "failures" / EXPERIMENT_ID / "promotion.json"
        ),
    }


def _write_test_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _create_unsealed_anchor_journal(root: Path) -> SegmentedEncounterJournal:
    root.parent.mkdir(parents=True, exist_ok=True)
    return SegmentedEncounterJournal.create(
        root,
        run_id=f"{DEFAULT_RUN_ID}-anchor",
        logical_path="$EVIDENCE/" + ANCHOR_JOURNAL_RELATIVE_PATH.as_posix(),
        purpose="anchor",
        task_sha256="a" * 64,
        execution_git_commit=EXECUTION_COMMIT,
        expected_case_count=1,
        expected_scope_counts={
            scope: {"segments": 0, "encounters": 0} for scope in SCOPES
        },
    )


class PublicCheckpointLifecycleTests(unittest.TestCase):
    def test_preparation_rejects_an_in_repository_non_evidence_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            unsafe_root = repo / "tracked-evidence"
            with (
                mock.patch.dict(
                    os.environ,
                    {"OT_EVIDENCE_ROOT": str(unsafe_root)},
                ),
                self.assertRaisesRegex(RuntimeError, "must be .evidence"),
            ):
                _assert_preparation_boundary(repo, COMMIT)

    def test_public_checkpoint_failure_precedes_every_private_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = repo / ".evidence"

            def fake_git(_repo: Path, *args: str) -> str:
                if args == ("status", "--porcelain=v1"):
                    return ""
                if args == ("rev-parse", "HEAD"):
                    return COMMIT
                raise AssertionError(args)

            with (
                mock.patch("open_trajectory_harness.ot0077.git_output", fake_git),
                mock.patch("open_trajectory_harness.ot0077._store", return_value=store),
                mock.patch("open_trajectory_harness.ot0077.assert_protocol_unchanged"),
                mock.patch(
                    "open_trajectory_harness.ot0077.validate_acceptance",
                    return_value={"experiment_id": EXPERIMENT_ID},
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.assert_public_checkpoint",
                    side_effect=ProtocolError("public checkpoint rejected"),
                ) as checkpoint,
                mock.patch(
                    "open_trajectory_harness.ot0077._write_sealed_bytes"
                ) as write_bytes,
                mock.patch("open_trajectory_harness.ot0077.derive") as derive,
                mock.patch(
                    "open_trajectory_harness.ot0077._write_tracked_once"
                ) as write_lock,
            ):
                with self.assertRaisesRegex(ProtocolError, "public checkpoint"):
                    prepare(repo)

            checkpoint.assert_called_once()
            write_bytes.assert_not_called()
            derive.assert_not_called()
            write_lock.assert_not_called()

    def test_post_checkpoint_destination_race_precedes_every_private_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = repo / ".evidence"
            raced_raw = (
                store
                / "runs"
                / EXPERIMENT_ID
                / f"{DEFAULT_RUN_ID}.json.zlib"
            )

            def fake_git(_repo: Path, *args: str) -> str:
                if args == ("status", "--porcelain=v1"):
                    return ""
                if args == ("rev-parse", "HEAD"):
                    return COMMIT
                raise AssertionError(args)

            def race_checkpoint(*_args: object, **_kwargs: object) -> dict[str, object]:
                # The second preparation-boundary check must observe a private
                # destination created while the long public checkpoint ran.
                _write_test_bytes(raced_raw, b"raced")
                return {"encounter_journal": {}}

            with (
                mock.patch("open_trajectory_harness.ot0077.git_output", fake_git),
                mock.patch("open_trajectory_harness.ot0077._store", return_value=store),
                mock.patch("open_trajectory_harness.ot0077.assert_protocol_unchanged"),
                mock.patch(
                    "open_trajectory_harness.ot0077.validate_acceptance",
                    return_value={"experiment_id": EXPERIMENT_ID},
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.assert_public_checkpoint",
                    side_effect=race_checkpoint,
                ) as checkpoint,
                mock.patch(
                    "open_trajectory_harness.ot0077._write_sealed_bytes"
                ) as write_bytes,
                mock.patch("open_trajectory_harness.ot0077.derive") as derive,
                mock.patch(
                    "open_trajectory_harness.ot0077._write_tracked_once"
                ) as write_lock,
                self.assertRaisesRegex(RuntimeError, "raw output exists"),
            ):
                prepare(repo)

            self.assertTrue(raced_raw.exists())
            checkpoint.assert_called_once()
            write_bytes.assert_not_called()
            derive.assert_not_called()
            write_lock.assert_not_called()

    def test_public_checkpoint_receipt_is_content_addressed_and_exact(self) -> None:
        task_sha = _sha(canonical_json(build_design_task(PUBLIC_CAUSAL_DESIGN_INDEX)))
        body = {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "implementation_git_commit": COMMIT,
            "design_seed_index": PUBLIC_CAUSAL_DESIGN_INDEX,
            "design_task_sha256": task_sha,
            "public_vector_bytes": EXPECTED_VECTOR_BYTES,
            "public_vector_row_count": EXPECTED_ROW_COUNT,
            "public_vector_sha256": EXPECTED_VECTOR_SHA256,
            "public_calibration_sha256": "2" * 64,
            "primary_score_sha256": EXPECTED_PUBLIC_SCORE_SHA256,
            "shadow_score_sha256": EXPECTED_PUBLIC_SCORE_SHA256,
            "encounter_journal": {
                "completed_encounter_count": 1,
                "execution_git_commit": COMMIT,
                "journal_format": JOURNAL_FORMAT,
                "journal_sha256": "4" * 64,
                "logical_path": "$EVIDENCE/"
                + PUBLIC_JOURNAL_RELATIVE_PATH.as_posix(),
                "purpose": "design",
                "receipt_count": 1,
                "schema_version": 1,
                "scope_counts": {
                    scope: {
                        "encounters": 1 if scope == "main" else 0,
                        "receipts": 1 if scope == "main" else 0,
                        "segments": 1 if scope == "main" else 0,
                    }
                    for scope in SCOPES
                },
                "scientific_sha256": "5" * 64,
                "sealed": True,
                "segment_count": 1,
                "segment_index_sha256": "6" * 64,
                "stage_open_sha256": "7" * 64,
                "task_sha256": task_sha,
            },
            "causal_summary": _expected_public_causal_summary(),
            "tests_status": "passed",
            "audit_status": "passed",
            "within_wall_budget": True,
            "pass": True,
        }
        receipt = {**body, "receipt_sha256": _sha(canonical_json(body))}
        self.assertEqual(
            _validate_public_checkpoint_receipt(receipt, implementation=COMMIT),
            receipt,
        )
        mutant = copy.deepcopy(receipt)
        mutant["tests_status"] = "tests_failed"
        with self.assertRaises(ProtocolError):
            _validate_public_checkpoint_receipt(mutant, implementation=COMMIT)
        arbitrary = copy.deepcopy(body)
        arbitrary["primary_score_sha256"] = "3" * 64
        arbitrary["shadow_score_sha256"] = "3" * 64
        arbitrary_receipt = {
            **arbitrary,
            "receipt_sha256": _sha(canonical_json(arbitrary)),
        }
        with self.assertRaises(ProtocolError):
            _validate_public_checkpoint_receipt(
                arbitrary_receipt,
                implementation=COMMIT,
            )

    def test_public_design_supervisor_fails_closed_without_running_the_vector(self) -> None:
        outcomes = (
            (
                {
                    "status": "timeout",
                    "returncode": None,
                    "stdout": b"",
                    "stderr": b"",
                },
                "timed out",
            ),
            (
                {
                    "status": "spawn-failed",
                    "returncode": None,
                    "stdout": b"",
                    "stderr": b"",
                },
                "process failed",
            ),
            (
                {
                    "status": "completed",
                    "returncode": 0,
                    "stdout": b"wrong public vector",
                    "stderr": b"",
                },
                "bytes differ",
            ),
        )
        for process, message in outcomes:
            with (
                self.subTest(status=process["status"], message=message),
                mock.patch(
                    "open_trajectory_harness.ot0077._communicate_bounded",
                    return_value=process,
                ) as communicate,
                self.assertRaisesRegex(ProtocolError, message),
            ):
                _assert_public_design_bounded(
                    Path.cwd(),
                    deadline=time.monotonic() + 10,
                )
            communicate.assert_called_once()

    def test_surface_audit_reaches_and_exactly_binds_base_learner(self) -> None:
        result = _learner_surface_audit(Path.cwd())
        self.assertTrue(result["pass"])
        self.assertEqual(result["relative_imports"], ["ot0075_learning"])
        self.assertTrue(result["inherited_identity_pass"])
        self.assertEqual(result["forbidden_relative_imports"], [])

    def test_package_import_does_not_eagerly_load_hosted_backend_authority(self) -> None:
        environment = {
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": os.defpath,
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": str(Path.cwd() / "src"),
        }
        process = subprocess.run(
            [
                sys.executable,
                "-S",
                "-c",
                (
                    "import sys; import open_trajectory_harness; "
                    "assert 'open_trajectory_harness.app_server' not in sys.modules; "
                    "assert 'subprocess' not in sys.modules"
                ),
            ],
            cwd=Path.cwd(),
            env=environment,
            capture_output=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr.decode())


class EncounterJournalLifecycleTests(unittest.TestCase):
    def test_locked_execution_rebinds_the_retained_public_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = repo / ".evidence"
            seed_bytes = b"s" * 32
            receipt = {
                "seed_sha256": _sha(seed_bytes),
                "task_sha256": "a" * 64,
            }
            public_checkpoint = {
                "encounter_journal": {
                    "scientific_sha256": "b" * 64,
                }
            }
            tree = "3" * 40

            def fake_git(_repo: Path, *args: str) -> str:
                if args == ("rev-parse", f"{COMMIT}^{{tree}}"):
                    return tree
                if args == ("rev-parse", f"{EXECUTION_COMMIT}^"):
                    return COMMIT
                if args == (
                    "diff",
                    "--name-status",
                    f"{COMMIT}..{EXECUTION_COMMIT}",
                ):
                    return "A\tspec/ot-0077-run-lock.json"
                raise AssertionError(args)

            with (
                mock.patch(
                    "open_trajectory_harness.ot0077.fixed_input_paths",
                    return_value={},
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._validate_public_checkpoint_receipt",
                    side_effect=lambda value, **_kwargs: value,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._public_journal_binding_ready",
                    return_value=True,
                ),
                mock.patch("open_trajectory_harness.ot0077.git_output", fake_git),
            ):
                lock = build_run_lock(
                    repo,
                    COMMIT,
                    receipt,
                    public_checkpoint,
                )

            # Simulate deletion after the successful preparation boundary.  The
            # run lock still carries the original binding, but the canonical
            # public journal itself is absent before private execution.
            self.assertFalse((store / PUBLIC_JOURNAL_RELATIVE_PATH).exists())
            with (
                mock.patch("open_trajectory_harness.ot0077._store", return_value=store),
                mock.patch(
                    "open_trajectory_harness.ot0077._read_json_bounded",
                    return_value=(lock, canonical_json(lock)),
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.fixed_input_paths",
                    return_value={},
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._validate_public_checkpoint_receipt",
                    side_effect=lambda value, **_kwargs: value,
                ),
                mock.patch("open_trajectory_harness.ot0077.git_output", fake_git),
                mock.patch(
                    "open_trajectory_harness.ot0077.assert_protocol_unchanged"
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.validate_acceptance",
                    return_value={"experiment_id": EXPERIMENT_ID},
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.ensure_derivation",
                    return_value=({}, receipt, seed_bytes),
                ),
                self.assertRaisesRegex(
                    ProtocolError,
                    "public checkpoint journal|public journal|journal binding",
                ),
            ):
                validate_run_lock(
                    repo,
                    EXECUTION_COMMIT,
                    allow_regeneration=False,
                )

    def test_orphaned_anchor_journal_is_quarantined_before_startup_returns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = repo / ".evidence"
            journal_root = store / ANCHOR_JOURNAL_RELATIVE_PATH
            failed_journal = store / FAILED_ANCHOR_JOURNAL_RELATIVE_PATH
            failure_path = store / FAILURE_RELATIVE_PATH
            _create_unsealed_anchor_journal(journal_root)
            before = _journal_prefix_summary(journal_root)

            with (
                mock.patch("open_trajectory_harness.ot0077._store", return_value=store),
                self.assertRaises((ProtocolError, RuntimeError)),
            ):
                run(repo)

            self.assertFalse(journal_root.exists())
            self.assertTrue(failed_journal.exists())
            self.assertEqual(_journal_prefix_summary(failed_journal), before)
            self.assertTrue(failure_path.exists())
            failure_path.chmod(0o600)
            failure = json.loads(failure_path.read_bytes())
            self.assertEqual(
                failure["encounter_journal"],
                {**before, "quarantined": True},
            )
            self.assertEqual(failure["authorized_actor_candidate_count"], 0)

    def test_journal_quarantine_fsyncs_both_rename_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            source = store / "runs" / EXPERIMENT_ID / "attempt.journal"
            target = store / "failures" / EXPERIMENT_ID / "attempt.journal"
            _create_unsealed_anchor_journal(source)
            before = _journal_prefix_summary(source)
            directory_sync_count = 0
            real_fsync = os.fsync

            def observe_fsync(descriptor: int) -> None:
                nonlocal directory_sync_count
                if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    directory_sync_count += 1
                real_fsync(descriptor)

            with mock.patch(
                "open_trajectory_harness.ot0077_journal.os.fsync",
                side_effect=observe_fsync,
            ):
                summary = _quarantine_encounter_journal(source, target)

            self.assertFalse(source.exists())
            self.assertTrue(target.exists())
            self.assertEqual(_journal_prefix_summary(target), before)
            self.assertEqual(summary, {**before, "quarantined": True})
            self.assertGreaterEqual(directory_sync_count, 2)

    def test_journal_quarantine_summary_never_reads_the_live_target_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            source = store / "runs" / EXPERIMENT_ID / "attempt.journal"
            target = store / "failures" / EXPERIMENT_ID / "attempt.journal"
            decoy = store / "decoy" / "attempt.journal"
            _create_unsealed_anchor_journal(source)
            decoy.parent.mkdir(parents=True)
            SegmentedEncounterJournal.create(
                decoy,
                run_id=f"{DEFAULT_RUN_ID}-anchor",
                logical_path="$EVIDENCE/" + ANCHOR_JOURNAL_RELATIVE_PATH.as_posix(),
                purpose="anchor",
                task_sha256="b" * 64,
                execution_git_commit=EXECUTION_COMMIT,
                expected_case_count=1,
                expected_scope_counts={
                    scope: {"segments": 0, "encounters": 0} for scope in SCOPES
                },
            )
            before = _journal_prefix_summary(source)
            decoy_stage_open = (decoy / STAGE_OPEN_NAME).read_bytes()
            real_summary = _journal_prefix_summary
            live_path_reads = 0

            def transient_decoy(root: Path) -> dict[str, object]:
                nonlocal live_path_reads
                if root == target:
                    live_path_reads += 1
                    stage_open = target / STAGE_OPEN_NAME
                    genuine = stage_open.read_bytes()
                    stage_open.write_bytes(decoy_stage_open)
                    try:
                        return real_summary(root)
                    finally:
                        stage_open.write_bytes(genuine)
                return real_summary(root)

            with mock.patch(
                "open_trajectory_harness.ot0077._journal_prefix_summary",
                side_effect=transient_decoy,
            ):
                summary = _quarantine_encounter_journal(source, target)

            self.assertEqual(live_path_reads, 0)
            self.assertEqual(summary, {**before, "quarantined": True})
            self.assertEqual(_journal_prefix_summary(target), before)

    def test_journal_quarantine_rejects_reversible_in_place_leaf_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            source = store / "runs" / EXPERIMENT_ID / "attempt.journal"
            target = store / "failures" / EXPERIMENT_ID / "attempt.journal"
            decoy = store / "decoy" / "attempt.journal"
            _create_unsealed_anchor_journal(source)
            decoy.parent.mkdir(parents=True)
            SegmentedEncounterJournal.create(
                decoy,
                run_id=f"{DEFAULT_RUN_ID}-anchor",
                logical_path="$EVIDENCE/" + ANCHOR_JOURNAL_RELATIVE_PATH.as_posix(),
                purpose="anchor",
                task_sha256="b" * 64,
                execution_git_commit=EXECUTION_COMMIT,
                expected_case_count=1,
                expected_scope_counts={
                    scope: {"segments": 0, "encounters": 0} for scope in SCOPES
                },
            )
            genuine = (source / STAGE_OPEN_NAME).read_bytes()
            decoy_bytes = (decoy / STAGE_OPEN_NAME).read_bytes()
            real_read = __import__(
                "open_trajectory_harness.ot0077",
                fromlist=["_read_regular_descriptor_bounded"],
            )._read_regular_descriptor_bounded
            swaps = 0

            def transient_leaf_bytes(
                descriptor: int,
                *,
                limit: int,
                label: str,
            ) -> bytes:
                nonlocal swaps
                if label == "journal snapshot artifact":
                    swaps += 1
                    stage_open = target / STAGE_OPEN_NAME
                    stage_open.write_bytes(decoy_bytes)
                    try:
                        return real_read(descriptor, limit=limit, label=label)
                    finally:
                        stage_open.write_bytes(genuine)
                return real_read(descriptor, limit=limit, label=label)

            with (
                mock.patch(
                    "open_trajectory_harness.ot0077._read_regular_descriptor_bounded",
                    side_effect=transient_leaf_bytes,
                ),
                self.assertRaisesRegex(
                    ProtocolError,
                    "journal snapshot artifact changed during capture",
                ),
            ):
                _quarantine_encounter_journal(source, target)

            self.assertEqual(swaps, 1)
            self.assertEqual((target / STAGE_OPEN_NAME).read_bytes(), genuine)

    def test_final_audit_cannot_remove_the_bound_journal_and_still_promote(
        self,
    ) -> None:
        from tests.test_ot0077_journal import build_chain, write_chain

        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            contract = _publication_contract(repo)
            contract["journal"] = (
                contract["store"] / ANCHOR_JOURNAL_RELATIVE_PATH
            )
            contract["failed_journal"] = (
                contract["store"] / FAILED_ANCHOR_JOURNAL_RELATIVE_PATH
            )
            chain = build_chain(0, horizon=1)
            task_sha256 = chain["receipt_order"][0]["payload"]["task_sha256"]
            contract["journal"].parent.mkdir(parents=True, exist_ok=True)
            stage = SegmentedEncounterJournal.create(
                contract["journal"],
                run_id=f"{DEFAULT_RUN_ID}-anchor",
                logical_path="$EVIDENCE/"
                + ANCHOR_JOURNAL_RELATIVE_PATH.as_posix(),
                purpose="anchor",
                task_sha256=task_sha256,
                execution_git_commit=EXECUTION_COMMIT,
                expected_case_count=1,
                expected_scope_counts={
                    scope: {
                        "segments": 1 if scope == "main" else 0,
                        "encounters": 1 if scope == "main" else 0,
                    }
                    for scope in SCOPES
                },
            )
            write_chain(stage, chain)
            journal_binding = stage.seal(scientific_sha256="c" * 64)

            seed = repo / "seed.bin"
            _write_test_bytes(seed, b"s" * 32)
            seed.chmod(0o400)
            raw = {
                "summary": {"disposition": "pending-reconstruction"},
                "scientific": {"encounter_journal": journal_binding},
            }
            _write_test_bytes(contract["raw"], encode_raw(raw))
            contract["raw"].chmod(0o400)
            publication = {"disposition": "promoted"}

            def record_manifest(_repo: Path, **kwargs: object) -> Path:
                artifact_id = kwargs["artifact_id"]
                path = (
                    contract["manifest"]
                    if artifact_id == DEFAULT_RUN_ID
                    else contract["promotion_manifest"]
                )
                _write_test_bytes(path, str(artifact_id).encode("ascii"))
                return path

            def bind_manifest(_repo: Path, **kwargs: object) -> dict[str, object]:
                return {
                    "artifact_bytes": kwargs["artifact_bytes"],
                    "artifact_sha256": kwargs["artifact_sha256"],
                    "readback_status": "manifest and evidence bytes verified",
                }

            def remove_stage_seal(
                _command: list[str],
                _repo: Path,
                _deadline: float,
                label: str,
            ) -> dict[str, object]:
                self.assertEqual(label, "final_publication_audit")
                (contract["journal"] / "stage-seal.otj").unlink()
                return {"status": "passed", "returncode": 0}

            with (
                mock.patch(
                    "open_trajectory_harness.ot0077._recover_incomplete_startup",
                    return_value=False,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.output_contract",
                    return_value=contract,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.locked_context",
                    return_value=(
                        EXECUTION_COMMIT,
                        {"implementation_git_commit": COMMIT},
                        {},
                        {},
                    ),
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._execute_locked_raw",
                    return_value=raw,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.seed_path",
                    return_value=seed,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.verify_fresh_root",
                    return_value={"pass": True, "status": "passed"},
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._record_artifact_bounded",
                    side_effect=record_manifest,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._manifest_binding_bounded",
                    side_effect=bind_manifest,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._post_raw_record_verification",
                    return_value=_post_record_verification(),
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.finalize_after_reconstruction",
                    return_value=publication,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._encounter_journal_ready",
                    side_effect=lambda *_args, **_kwargs: (
                        contract["journal"] / "stage-seal.otj"
                    ).exists(),
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._bounded_command",
                    side_effect=remove_stage_seal,
                ) as final_audit,
                self.assertRaises(RuntimeError),
            ):
                run(repo)

            final_audit.assert_called_once()
            for name in ("manifest", "promotion", "promotion_manifest"):
                self.assertFalse(contract[name].exists())
            self.assertFalse(contract["journal"].exists())
            self.assertTrue(contract["failed_journal"].exists())
            self.assertTrue(contract["failure"].exists())


class EvidencePublicationBoundaryTests(unittest.TestCase):
    def test_encode_raw_uses_the_production_canonical_compression(self) -> None:
        raw = {
            "schema_version": 1,
            "payload": "open-trajectory-canonical-compression-" * 4096,
        }
        canonical = canonical_json(raw)
        encoded = encode_raw(raw)
        self.assertEqual(encoded, zlib.compress(canonical, level=9))
        self.assertEqual(decode_raw(encoded), raw)

        noncanonical = zlib.compress(canonical, level=1)
        self.assertNotEqual(noncanonical, encoded)
        with self.assertRaisesRegex(ProtocolError, "compression is not canonical"):
            decode_raw(noncanonical)

    def test_bounded_decompression_rejects_an_expansion_bomb(self) -> None:
        decoded = b"x" * 65_536
        encoded = zlib.compress(decoded, level=9)
        self.assertLess(len(encoded), 1_024)
        with self.assertRaisesRegex(
            ProtocolError,
            "framing or expansion differs",
        ):
            _bounded_zlib_decompress(encoded, limit=1_024)

    def test_bounded_command_classifies_timeout_and_spawn_failure(self) -> None:
        for process, expected in (
            (
                {
                    "status": "timeout",
                    "returncode": None,
                    "stdout": b"",
                    "stderr": b"",
                },
                {"status": "fixture_timeout", "returncode": None},
            ),
            (
                {
                    "status": "spawn-failed",
                    "returncode": None,
                    "stdout": b"",
                    "stderr": b"",
                },
                {"status": "fixture_failed", "returncode": None},
            ),
        ):
            with (
                self.subTest(status=process["status"]),
                mock.patch(
                    "open_trajectory_harness.ot0077._communicate_bounded",
                    return_value=process,
                ),
            ):
                self.assertEqual(
                    _bounded_command(
                        ["unused"],
                        Path.cwd(),
                        time.monotonic() + 10,
                        "fixture",
                    ),
                    expected,
                )

    def test_evidence_operation_rejects_timeout_spawn_and_noncanonical_output(
        self,
    ) -> None:
        outcomes = (
            (
                {
                    "status": "timeout",
                    "returncode": None,
                    "stdout": b"",
                    "stderr": b"",
                },
                "timed out",
            ),
            (
                {
                    "status": "spawn-failed",
                    "returncode": None,
                    "stdout": b"",
                    "stderr": b"",
                },
                "operation failed",
            ),
            (
                {
                    "status": "completed",
                    "returncode": 0,
                    "stdout": b"{ }",
                    "stderr": b"",
                },
                "not canonical",
            ),
        )
        for process, message in outcomes:
            with (
                self.subTest(status=process["status"], message=message),
                mock.patch(
                    "open_trajectory_harness.ot0077._communicate_bounded",
                    return_value=process,
                ),
                self.assertRaisesRegex(ProtocolError, message),
            ):
                _evidence_operation_bounded(
                    Path.cwd(),
                    {"mode": "test"},
                    deadline=time.monotonic() + 10,
                )

    def test_bounded_manifest_binding_rejects_an_arbitrary_worker_response(
        self,
    ) -> None:
        repo = Path.cwd()
        manifest = (
            repo
            / "evidence"
            / "manifests"
            / EXPERIMENT_ID
            / f"{DEFAULT_RUN_ID}.json"
        )
        with (
            mock.patch(
                "open_trajectory_harness.ot0077._evidence_operation_bounded",
                return_value={},
            ),
            self.assertRaisesRegex(ProtocolError, "binding response differs"),
        ):
            _manifest_binding_bounded(
                repo,
                path=manifest,
                artifact_id=DEFAULT_RUN_ID,
                kind="e14-anchor-prepublication-raw",
                artifact_sha256="a" * 64,
                artifact_bytes=17,
                execution_commit=EXECUTION_COMMIT,
                store=repo / ".evidence",
                recipe=RECONSTRUCTION_RECIPE,
                input_manifests=list(RAW_INPUT_MANIFESTS),
                limitations=list(RAW_LIMITATIONS),
                environment_dirty=False,
                deadline=time.monotonic() + 10,
            )

    def test_manifest_binding_requires_exact_recipe_inputs_limits_and_git_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            (repo / "src").symlink_to(
                Path(__file__).resolve().parents[1] / "src",
                target_is_directory=True,
            )
            path = (
                repo
                / "evidence"
                / "manifests"
                / EXPERIMENT_ID
                / f"{DEFAULT_RUN_ID}.json"
            )
            artifact_payload = b"manifest artifact"
            artifact_sha256 = _sha(artifact_payload)
            artifact_bytes = len(artifact_payload)
            store = repo / ".evidence"
            object_path = (
                store
                / "objects"
                / "sha256"
                / artifact_sha256[:2]
                / artifact_sha256
            )
            _write_test_bytes(object_path, artifact_payload)
            environment = safe_environment(repo)
            environment["git"] = {
                "commit": EXECUTION_COMMIT,
                "dirty": False,
            }
            manifest = {
                "schema_version": 1,
                "experiment_id": EXPERIMENT_ID,
                "artifact_id": DEFAULT_RUN_ID,
                "kind": "e14-anchor-prepublication-raw",
                "media_type": "application/octet-stream",
                "sha256": artifact_sha256,
                "bytes": artifact_bytes,
                "evidence_class": "private-reproducible",
                "availability": {"local_object": True},
                "reconstruction": {
                    "recipe": RECONSTRUCTION_RECIPE,
                    "expected_output": f"artifact:{DEFAULT_RUN_ID}",
                },
                "input_manifests": list(RAW_INPUT_MANIFESTS),
                "limitations": list(RAW_LIMITATIONS),
                "environment": environment,
            }

            def bind(value: dict[str, object]) -> dict[str, object]:
                _write_test_bytes(
                    path,
                    (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(),
                )
                return _manifest_binding_bounded(
                    repo,
                    path=path,
                    artifact_id=DEFAULT_RUN_ID,
                    kind="e14-anchor-prepublication-raw",
                    artifact_sha256=artifact_sha256,
                    artifact_bytes=artifact_bytes,
                    execution_commit=EXECUTION_COMMIT,
                    store=store,
                    recipe=RECONSTRUCTION_RECIPE,
                    input_manifests=list(RAW_INPUT_MANIFESTS),
                    limitations=list(RAW_LIMITATIONS),
                    environment_dirty=False,
                    deadline=time.monotonic() + 5.0,
                )

            result = bind(manifest)
            self.assertEqual(result["artifact_sha256"], artifact_sha256)
            self.assertFalse(result["environment_git_dirty"])

            historical_environment = copy.deepcopy(manifest)
            historical_environment["environment"].update(
                {
                    "os_family": "historical-os",
                    "architecture": "historical-architecture",
                    "python_implementation": "historical-python",
                    "python_version": "0.0.0-historical",
                }
            )
            historical_result = bind(historical_environment)
            self.assertEqual(
                historical_result["artifact_sha256"],
                artifact_sha256,
            )

            mutants: dict[str, dict[str, object]] = {}
            changed = copy.deepcopy(manifest)
            changed["reconstruction"]["recipe"] = "different recipe"
            mutants["recipe"] = changed
            changed = copy.deepcopy(manifest)
            changed["input_manifests"] = []
            mutants["inputs"] = changed
            changed = copy.deepcopy(manifest)
            changed["limitations"] = []
            mutants["limitations"] = changed
            changed = copy.deepcopy(manifest)
            changed["environment"]["git"]["dirty"] = True
            mutants["dirty"] = changed
            for name, mutant in mutants.items():
                with self.subTest(field=name), self.assertRaisesRegex(
                    ProtocolError,
                    "publication evidence operation failed",
                ):
                    bind(mutant)

    def test_post_record_readback_failure_cannot_pass_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            with (
                mock.patch(
                    "open_trajectory_harness.ot0077._bounded_command",
                    return_value={"status": "passed", "returncode": 0},
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._manifest_binding_bounded",
                    side_effect=ProtocolError("worker readback failed"),
                ),
            ):
                result = _post_raw_record_verification(
                    repo,
                    manifest=(
                        repo
                        / "evidence"
                        / "manifests"
                        / EXPERIMENT_ID
                        / f"{DEFAULT_RUN_ID}.json"
                    ),
                    store=repo / ".evidence",
                    expected_binding={"never": "trusted"},
                    artifact_sha256="a" * 64,
                    artifact_bytes=17,
                    execution_commit=EXECUTION_COMMIT,
                    recipe=RECONSTRUCTION_RECIPE,
                    input_manifests=list(RAW_INPUT_MANIFESTS),
                    limitations=list(RAW_LIMITATIONS),
                    deadline=time.monotonic() + 10,
                )
            self.assertEqual(
                result["raw_manifest_readback"],
                {"pass": False, "status": "exact manifest readback failed"},
            )
            self.assertFalse(_publication_verification_passed(result))

    def test_record_failure_after_manifest_install_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            contract = _publication_contract(repo)
            seed = repo / "seed.bin"
            _write_test_bytes(seed, b"s" * 32)
            seed.chmod(0o400)
            raw = {"summary": {"disposition": "pending-reconstruction"}}
            _write_test_bytes(contract["raw"], encode_raw(raw))
            contract["raw"].chmod(0o400)
            manifest_payload = b"recorded raw manifest"
            state = {"manifest_recorded": False}

            def record_manifest(_repo: Path, **kwargs: object) -> Path:
                self.assertEqual(kwargs["artifact_id"], DEFAULT_RUN_ID)
                _write_test_bytes(contract["manifest"], manifest_payload)
                state["manifest_recorded"] = True
                raise OSError("record worker failed after manifest install")

            with (
                mock.patch(
                    "open_trajectory_harness.ot0077._recover_incomplete_startup",
                    return_value=False,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.output_contract",
                    return_value=contract,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.locked_context",
                    return_value=(
                        EXECUTION_COMMIT,
                        {"implementation_git_commit": COMMIT},
                        {},
                        {},
                    ),
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._execute_locked_raw",
                    return_value=raw,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.seed_path",
                    return_value=seed,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.verify_fresh_root",
                    return_value={"pass": True, "status": "passed"},
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._record_artifact_bounded",
                    side_effect=record_manifest,
                ) as recorder,
                self.assertRaisesRegex(RuntimeError, "raw artifact recording failed"),
            ):
                run(repo)

            recorder.assert_called_once()
            self.assertTrue(state["manifest_recorded"])
            self.assertFalse(contract["manifest"].exists())
            contract["failed_manifest"].chmod(0o600)
            self.assertEqual(contract["failed_manifest"].read_bytes(), manifest_payload)
            contract["failure"].chmod(0o600)
            failure = json.loads(contract["failure"].read_bytes())
            self.assertEqual(failure["operational_failure"], "raw_manifest_record_failed")
            self.assertFalse(failure["public_manifest_retained"])
            self.assertTrue(failure["authoritative_raw_retained"])

    def test_final_audit_manifest_replacement_is_rejected_and_quarantined(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            contract = _publication_contract(repo)
            seed = repo / "seed.bin"
            _write_test_bytes(seed, b"s" * 32)
            seed.chmod(0o400)
            raw = {"summary": {"disposition": "pending-reconstruction"}}
            _write_test_bytes(contract["raw"], encode_raw(raw))
            contract["raw"].chmod(0o400)
            raw_manifest_payload = b"raw manifest before final audit"
            promotion_manifest_payload = b"promotion manifest before final audit"
            replacement_payload = b"raw manifest replaced by final audit"
            observed_raw_payloads: list[bytes] = []

            def record_manifest(_repo: Path, **kwargs: object) -> Path:
                artifact_id = kwargs["artifact_id"]
                if artifact_id == DEFAULT_RUN_ID:
                    path, payload = contract["manifest"], raw_manifest_payload
                elif artifact_id == PROMOTION_ARTIFACT_ID:
                    path = contract["promotion_manifest"]
                    payload = promotion_manifest_payload
                else:
                    raise AssertionError(artifact_id)
                _write_test_bytes(path, payload)
                return path

            def bind_manifest(_repo: Path, **kwargs: object) -> dict[str, object]:
                path = kwargs["path"]
                payload = path.read_bytes()
                if path == contract["manifest"]:
                    observed_raw_payloads.append(payload)
                    if payload != raw_manifest_payload:
                        raise ProtocolError("raw manifest was replaced")
                elif path == contract["promotion_manifest"]:
                    if payload != promotion_manifest_payload:
                        raise ProtocolError("promotion manifest was replaced")
                else:
                    raise AssertionError(path)
                return {
                    "artifact_bytes": kwargs["artifact_bytes"],
                    "artifact_sha256": kwargs["artifact_sha256"],
                    "readback_status": "manifest and evidence bytes verified",
                }

            def replace_during_audit(
                _command: list[str],
                _repo: Path,
                _deadline: float,
                label: str,
            ) -> dict[str, object]:
                self.assertEqual(label, "final_publication_audit")
                replacement = contract["manifest"].with_suffix(".replacement")
                _write_test_bytes(replacement, replacement_payload)
                replacement.replace(contract["manifest"])
                return {"status": "passed", "returncode": 0}

            publication = {"disposition": "promoted"}
            with (
                mock.patch(
                    "open_trajectory_harness.ot0077._recover_incomplete_startup",
                    return_value=False,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.output_contract",
                    return_value=contract,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.locked_context",
                    return_value=(
                        EXECUTION_COMMIT,
                        {"implementation_git_commit": COMMIT},
                        {},
                        {},
                    ),
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._execute_locked_raw",
                    return_value=raw,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.seed_path",
                    return_value=seed,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.verify_fresh_root",
                    return_value={"pass": True, "status": "passed"},
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._record_artifact_bounded",
                    side_effect=record_manifest,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._manifest_binding_bounded",
                    side_effect=bind_manifest,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._post_raw_record_verification",
                    return_value=_post_record_verification(),
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.finalize_after_reconstruction",
                    return_value=publication,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077._bounded_command",
                    side_effect=replace_during_audit,
                ) as final_audit,
                self.assertRaisesRegex(
                    RuntimeError,
                    "final publication manifest rebind failed",
                ),
            ):
                run(repo)

            final_audit.assert_called_once()
            self.assertEqual(
                observed_raw_payloads,
                [raw_manifest_payload, replacement_payload],
            )
            for name in ("manifest", "promotion", "promotion_manifest"):
                self.assertFalse(contract[name].exists())
            contract["failed_manifest"].chmod(0o600)
            self.assertEqual(
                contract["failed_manifest"].read_bytes(),
                replacement_payload,
            )
            contract["failure"].chmod(0o600)
            failure = json.loads(contract["failure"].read_bytes())
            self.assertEqual(
                failure["operational_failure"],
                "final_publication_verification_failed",
            )
            self.assertFalse(failure["public_manifest_retained"])

    def test_invalidation_removes_both_public_artifacts_before_failure_receipt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            contract = _publication_contract(Path(temporary))
            payloads = {
                "manifest": b"raw manifest",
                "promotion": b"promotion decision",
                "promotion_manifest": b"promotion manifest",
            }
            for name, payload in payloads.items():
                _write_test_bytes(contract[name], payload)
            _write_test_bytes(contract["raw"], b"authoritative raw")

            _invalidate_publication(
                contract,
                code="transaction_failed",
                authoritative_raw=contract["raw"],
            )

            for name in ("manifest", "promotion", "promotion_manifest"):
                self.assertFalse(contract[name].exists())
            for public_name, failed_name in (
                ("manifest", "failed_manifest"),
                ("promotion", "failed_promotion"),
                ("promotion_manifest", "failed_promotion_manifest"),
            ):
                contract[failed_name].chmod(0o600)
                self.assertEqual(
                    contract[failed_name].read_bytes(),
                    payloads[public_name],
                )
            contract["failure"].chmod(0o600)
            failure = json.loads(contract["failure"].read_bytes())
            self.assertEqual(failure["operational_failure"], "transaction_failed")
            self.assertFalse(failure["public_manifest_retained"])
            self.assertEqual(failure["authorized_actor_candidate_count"], 0)

    def test_quarantine_attempts_every_authority_removal_after_one_unlink_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            contract = _publication_contract(Path(temporary))
            sources = [
                contract["promotion_manifest"],
                contract["manifest"],
                contract["promotion"],
            ]
            for index, source in enumerate(sources):
                _write_test_bytes(source, f"surface-{index}".encode("ascii"))

            blocked = contract["manifest"]
            attempted: list[Path] = []

            def flaky_unlink(
                parent_descriptor: int,
                name: str,
                source: Path,
            ) -> None:
                attempted.append(source)
                if source == blocked:
                    raise OSError("blocked unlink")
                os.unlink(name, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)

            with (
                mock.patch(
                    "open_trajectory_harness.ot0077._unlink_publication_source",
                    side_effect=flaky_unlink,
                ),
                self.assertRaisesRegex(RuntimeError, "authority could not be removed"),
            ):
                _quarantine_publication(contract)

            self.assertEqual(set(attempted), set(sources))
            self.assertTrue(blocked.exists())
            self.assertFalse(contract["promotion"].exists())
            self.assertFalse(contract["promotion_manifest"].exists())


class ReconstructionPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary_only_scientific = _prepublication_scientific()

    def test_locked_execution_never_preasserts_reconstruction(self) -> None:
        captured: dict[str, object] = {}

        def fake_calibration(*_args: object, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"phase": "prepublication"}

        with mock.patch(
            "open_trajectory_harness.ot0077._run_calibration_bounded",
            side_effect=fake_calibration,
        ):
            result = _execute_locked_raw(
                Path.cwd(),
                COMMIT,
                {"implementation_git_commit": "2" * 40},
                {"purpose": "anchor"},
                {"experiment_id": EXPERIMENT_ID},
            )
        self.assertEqual(result, {"phase": "prepublication"})
        self.assertIs(captured["clean_private_reconstruction"], False)
        self.assertIs(captured["materialize_raw"], True)
        self.assertEqual(captured["implementation_commit"], "2" * 40)

    def test_fresh_root_hash_completion_cannot_outlive_the_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            authoritative = repo / "authoritative.json.zlib"
            authoritative_bytes = b"exact reconstructed artifact"
            _write_test_bytes(authoritative, authoritative_bytes)
            authoritative.chmod(0o400)
            state = {"hash_completed": False}

            def reconstruct_process(
                _command: list[str],
                *,
                repo: Path,
                deadline: float,
                environment: dict[str, str],
            ) -> dict[str, object]:
                self.assertEqual(repo, Path(temporary).resolve())
                self.assertGreater(deadline, 100.0)
                reconstructed = Path(environment["OT_EVIDENCE_ROOT"]) / RAW_RELATIVE_PATH
                _write_test_bytes(reconstructed, authoritative_bytes)
                reconstructed.chmod(0o400)
                return {
                    "status": "completed",
                    "returncode": 0,
                    "stdout": b"",
                    "stderr": b"",
                }

            def hash_reconstructed(value: bytes) -> str:
                self.assertEqual(value, authoritative_bytes)
                state["hash_completed"] = True
                return _sha(value)

            def clock() -> float:
                if state["hash_completed"]:
                    return 100.0 + RECONSTRUCTION_SECONDS + 1.0
                return 100.0

            with (
                mock.patch(
                    "open_trajectory_harness.ot0077._communicate_bounded",
                    side_effect=reconstruct_process,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.sha256_bytes",
                    side_effect=hash_reconstructed,
                ),
                mock.patch(
                    "open_trajectory_harness.ot0077.time.monotonic",
                    side_effect=clock,
                ),
            ):
                result = verify_fresh_root(
                    repo,
                    implementation=COMMIT,
                    seed_bytes=b"s" * 32,
                    authoritative_raw=authoritative,
                )

            self.assertTrue(state["hash_completed"])
            self.assertEqual(
                result,
                {"pass": False, "status": "reconstruction_timeout"},
            )

    def test_summary_only_causal_evidence_is_rejected(self) -> None:
        scientific = copy.deepcopy(self.summary_only_scientific)
        self.assertTrue(all("chain" not in lineage for lineage in scientific["lineages"]))
        self.assertFalse(
            _causal_evidence_ready(
                scientific,
                repo=Path.cwd(),
                task=scientific["task"],
                deadline=None,
            )
        )

    def test_invented_metamorphic_inventory_is_rejected(self) -> None:
        scientific = copy.deepcopy(self.summary_only_scientific)
        exact_variants = {
            name: {}
            for name in scientific["scorer_independence"]["trace_level"]
        }
        with (
            mock.patch(
                "open_trajectory_harness.ot0077.score_bundle",
                return_value=scientific["primary_score"],
            ),
            mock.patch(
                "open_trajectory_harness.ot0077.score_bundle_shadow",
                return_value=scientific["shadow_score"],
            ),
            mock.patch(
                "open_trajectory_harness.ot0077.metamorphic_variants",
                return_value=exact_variants,
            ),
            mock.patch(
                "open_trajectory_harness.ot0077._task_metamorphic_gates",
                return_value=scientific["scorer_independence"]["task_level"],
            ),
            mock.patch(
                "open_trajectory_harness.ot0077._causal_evidence_ready",
                return_value=True,
            ),
            mock.patch(
                "open_trajectory_harness.ot0077._encounter_journal_ready",
                return_value=True,
            ),
        ):
            self.assertTrue(
                _scientific_ready_except_reconstruction(
                    scientific,
                    purpose="anchor",
                )
            )
            invented = copy.deepcopy(scientific)
            invented["scorer_independence"]["trace_level"] = {
                "fixture": {
                    "pass": True,
                    "primary_sha256": invented["scorer_independence"][
                        "primary_sha256"
                    ],
                    "shadow_sha256": invented["scorer_independence"][
                        "shadow_sha256"
                    ],
                }
            }
            self.assertFalse(
                _scientific_ready_except_reconstruction(
                    invented,
                    purpose="anchor",
                )
            )

    def test_summary_level_prepublication_mutants_fail_closed(self) -> None:
        scientific = copy.deepcopy(self.summary_only_scientific)
        self.assertFalse(scientific["primary_score"]["promotion_gates"]["execution"])
        self.assertFalse(scientific["primary_score"]["anchor_promotion_pass"])
        exact_variants = {
            name: {}
            for name in scientific["scorer_independence"]["trace_level"]
        }
        with (
            mock.patch(
                "open_trajectory_harness.ot0077.score_bundle",
                return_value=scientific["primary_score"],
            ),
            mock.patch(
                "open_trajectory_harness.ot0077.score_bundle_shadow",
                return_value=scientific["shadow_score"],
            ),
            mock.patch(
                "open_trajectory_harness.ot0077.metamorphic_variants",
                return_value=exact_variants,
            ),
            mock.patch(
                "open_trajectory_harness.ot0077._task_metamorphic_gates",
                return_value=scientific["scorer_independence"]["task_level"],
            ),
            mock.patch(
                "open_trajectory_harness.ot0077._causal_evidence_ready",
                return_value=True,
            ),
            mock.patch(
                "open_trajectory_harness.ot0077._encounter_journal_ready",
                return_value=True,
            ),
        ):
            stale = copy.deepcopy(scientific)
            stale["scorer_bundle"]["authority_defect_rejections"].update(
                {
                    next(
                        iter(stale["scorer_bundle"]["authority_defect_rejections"])
                    ): False
                }
            )
            self.assertFalse(
                _scientific_ready_except_reconstruction(stale, purpose="anchor")
            )
            stale = copy.deepcopy(scientific)
            stale["gate_evidence"]["base_execution_gates"][
                "online_reference_authority"
            ] = False
            self.assertFalse(
                _scientific_ready_except_reconstruction(stale, purpose="anchor")
            )
            candidate = copy.deepcopy(scientific)
            candidate["candidate_outputs"] = True
            self.assertFalse(
                _scientific_ready_except_reconstruction(candidate, purpose="anchor")
            )

    def test_finalization_occurs_after_exact_match_without_mutating_raw(self) -> None:
        raw, encoded = _prepublication_raw()
        original = copy.deepcopy(raw)
        reconstruction = {
            "pass": True,
            "status": "passed",
            "bytes": len(encoded),
            "sha256": _sha(encoded),
        }
        with mock.patch(
            "open_trajectory_harness.ot0077._calibration_ready_except_reconstruction",
            return_value=True,
        ):
            publication = finalize_after_reconstruction(
                raw,
                reconstruction,
                encoded_raw=encoded,
                raw_manifest=_raw_manifest(encoded),
                post_record_verification=_post_record_verification(),
            )
        self.assertEqual(raw, original)
        self.assertTrue(publication["calibration_pass"])
        self.assertEqual(publication["disposition"], "promoted")
        self.assertEqual(publication["authorized_actor_candidate_count"], 1)
        self.assertEqual(publication["prepublication_raw_sha256"], _sha(encoded))

    def test_finalization_rejects_absent_or_mismatched_reconstruction(self) -> None:
        raw, encoded = _prepublication_raw()
        for reconstruction in (
            {"pass": False, "status": "raw_mismatch"},
            {
                "pass": True,
                "status": "passed",
                "bytes": len(encoded),
                "sha256": "0" * 64,
            },
        ):
            with (
                mock.patch(
                    "open_trajectory_harness.ot0077._calibration_ready_except_reconstruction",
                    return_value=True,
                ),
                self.assertRaises(ProtocolError),
            ):
                finalize_after_reconstruction(
                    raw,
                    reconstruction,
                    encoded_raw=encoded,
                    raw_manifest=_raw_manifest(encoded),
                    post_record_verification=_post_record_verification(),
                )

    def test_raw_execution_cannot_diverge_from_scientific_execution(self) -> None:
        raw, _ = _prepublication_raw()
        raw["execution_git_commit"] = "3" * 40
        encoded = encode_raw(raw)
        reconstruction = {
            "pass": True,
            "status": "passed",
            "bytes": len(encoded),
            "sha256": _sha(encoded),
        }
        with (
            mock.patch(
                "open_trajectory_harness.ot0077._calibration_ready_except_reconstruction",
                return_value=True,
            ),
            self.assertRaisesRegex(
                ProtocolError,
                "prepublication raw identity differs",
            ),
        ):
            finalize_after_reconstruction(
                raw,
                reconstruction,
                encoded_raw=encoded,
                raw_manifest=_raw_manifest(encoded),
                post_record_verification=_post_record_verification(),
            )

    def test_finalization_rejects_unrelated_encoded_bytes_or_unverified_manifest(self) -> None:
        raw, encoded = _prepublication_raw()
        reconstruction = {
            "pass": True,
            "status": "passed",
            "bytes": len(encoded),
            "sha256": _sha(encoded),
        }
        with (
            mock.patch(
                "open_trajectory_harness.ot0077._calibration_ready_except_reconstruction",
                return_value=True,
            ),
            self.assertRaises(ProtocolError),
        ):
            finalize_after_reconstruction(
                raw,
                reconstruction,
                encoded_raw=b"unrelated",
                raw_manifest=_raw_manifest(encoded),
                post_record_verification=_post_record_verification(),
            )
        unverified = _post_record_verification()
        unverified["raw_manifest_readback"]["pass"] = False
        with (
            mock.patch(
                "open_trajectory_harness.ot0077._calibration_ready_except_reconstruction",
                return_value=True,
            ),
            self.assertRaises(ProtocolError),
        ):
            finalize_after_reconstruction(
                raw,
                reconstruction,
                encoded_raw=encoded,
                raw_manifest=_raw_manifest(encoded),
                post_record_verification=unverified,
            )


if __name__ == "__main__":
    unittest.main()
