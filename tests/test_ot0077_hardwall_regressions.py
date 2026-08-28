from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from open_trajectory_harness.ot0002 import canonical_json
from open_trajectory_harness.ot0077 import (
    ACCEPTANCE_PATH,
    ANCHOR_JOURNAL_RELATIVE_PATH,
    COMPLETION_RELATIVE_PATH,
    DEFAULT_RUN_ID,
    EXPERIMENT_ID,
    RAW_RELATIVE_PATH,
    RUN_LOCK_PATH,
    _AUTHORITY_GROUP_ENV,
    _assert_preparation_boundary,
    _authority_root_identity,
    _communicate_bounded,
    _journal_stage_binding_bounded,
    _logical,
    _manifest_binding_bounded,
    _materialize_raw_transaction,
    _open_authority_root,
    _output_paths,
    _pinned_publication_snapshot,
    _publication_completion,
    _publication_completion_ready,
    _quarantine_encounter_journal,
    _quarantine_publication,
    _quarantine_raw_transaction,
    _quarantine_reconstruction_root,
    _read_leaf_bounded_at,
    _record_artifact_bounded,
    _recover_incomplete_startup,
    _run_exec_consumer,
    _run_calibration_bounded,
    _secure_manifest_install,
    _secure_object_install,
    _write_contract_store_sealed_bytes,
    decode_raw,
    encode_raw,
    output_contract,
    sha256_bytes,
    validate_acceptance,
    validate_run_lock,
    verify_fresh_root,
    run,
    ProtocolError,
)


IMPLEMENTATION_COMMIT = "1" * 40
EXECUTION_COMMIT = "2" * 40
MODULE = "open_trajectory_harness.ot0077"


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _contract(repo: Path, store: Path) -> dict[str, object]:
    with mock.patch(f"{MODULE}._store", return_value=store):
        return _output_paths(repo)


def _completion_fixture(
    repo: Path,
    store: Path,
) -> tuple[
    dict[str, Path],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    contract = _contract(repo, store)
    journal_binding: dict[str, object] = {
        "scientific_sha256": "a" * 64,
    }
    raw = {
        "execution_git_commit": EXECUTION_COMMIT,
        "scientific": {
            "execution_git_commit": EXECUTION_COMMIT,
            "encounter_journal": journal_binding,
        },
    }
    encoded_raw = encode_raw(raw)
    raw_manifest_bytes = b"raw manifest"
    promotion_bytes = canonical_json({"disposition": "promoted"})
    promotion_manifest_bytes = b"promotion manifest"
    raw_manifest = {
        "manifest_bytes": len(raw_manifest_bytes),
        "manifest_sha256": sha256_bytes(raw_manifest_bytes),
    }
    promotion_manifest = {
        "manifest_bytes": len(promotion_manifest_bytes),
        "manifest_sha256": sha256_bytes(promotion_manifest_bytes),
    }
    completion = _publication_completion(
        contract,
        execution_commit=EXECUTION_COMMIT,
        encoded_raw=encoded_raw,
        raw_manifest=raw_manifest,
        encoded_promotion=promotion_bytes,
        promotion_manifest=promotion_manifest,
        journal_binding=journal_binding,
    )
    for path, payload in (
        (contract["raw"], encoded_raw),
        (contract["manifest"], raw_manifest_bytes),
        (contract["promotion"], promotion_bytes),
        (contract["promotion_manifest"], promotion_manifest_bytes),
        (contract["completion"], canonical_json(completion)),
    ):
        _write(path, payload)
    return contract, journal_binding, raw_manifest, promotion_manifest


def _stage_binding(journal: dict[str, object]) -> dict[str, object]:
    return {"sealed": True, "torn_tail": False, "binding": journal}


class RawMaterializationHardWallTests(unittest.TestCase):
    def _run_materialization(
        self,
        repo: Path,
        store: Path,
        response: object,
    ) -> dict[str, object]:
        store.mkdir(parents=True, exist_ok=True)
        with (
            mock.patch(f"{MODULE}._store", return_value=store),
            mock.patch(f"{MODULE}._communicate_bounded", side_effect=response),
        ):
            return _run_calibration_bounded(
                repo,
                {"purpose": "anchor"},
                execution_commit=EXECUTION_COMMIT,
                clean_private_reconstruction=False,
                run_verification_commands=False,
                deadline=10_000_000.0,
                journal_root=store / ANCHOR_JOURNAL_RELATIVE_PATH,
                journal_logical_path=_logical(ANCHOR_JOURNAL_RELATIVE_PATH),
                materialize_raw=True,
                implementation_commit=IMPLEMENTATION_COMMIT,
            )

    def test_worker_stdout_must_exactly_match_installed_raw_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            target = store / RAW_RELATIVE_PATH

            def response(*_args: object, **_kwargs: object) -> dict[str, object]:
                _write(target, b"installed raw")
                return {
                    "status": "completed",
                    "returncode": 0,
                    "stdout": b"different worker response",
                    "stderr": b"",
                }

            with (
                mock.patch(f"{MODULE}.decode_raw") as decode,
                self.assertRaisesRegex(
                    ProtocolError,
                    "raw file differs from the supervised worker response",
                ),
            ):
                self._run_materialization(repo, store, response)
            decode.assert_not_called()

    def test_installed_raw_is_bounded_before_it_is_read_or_decoded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            target = store / RAW_RELATIVE_PATH

            def response(*_args: object, **_kwargs: object) -> dict[str, object]:
                _write(target, b"123456789")
                return {
                    "status": "completed",
                    "returncode": 0,
                    "stdout": b"12345678",
                    "stderr": b"",
                }

            with (
                mock.patch(f"{MODULE}.MAX_RAW_BYTES", 8),
                mock.patch(f"{MODULE}.decode_raw") as decode,
                self.assertRaisesRegex(ProtocolError, "materialized raw file identity"),
            ):
                self._run_materialization(repo, store, response)
            decode.assert_not_called()

    def test_expired_staging_write_never_installs_authoritative_raw(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            store.mkdir(parents=True)
            contract = _contract(repo, store)
            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(f"{MODULE}.encode_raw", return_value=b"encoded"),
                mock.patch(
                    f"{MODULE}.time.monotonic",
                    side_effect=(0.0, 2.0),
                ),
                self.assertRaisesRegex(
                    ProtocolError,
                    "raw staging write exceeded the calibration deadline",
                ),
            ):
                _materialize_raw_transaction(repo, {}, deadline=1.0)

            self.assertFalse(contract["raw"].exists())
            self.assertTrue(contract["raw_staging"].exists())
            contract["raw_staging"].chmod(0o600)
            summary = _quarantine_raw_transaction(contract)
            self.assertFalse(contract["raw_staging"].exists())
            self.assertTrue(contract["failed_raw_staging"].exists())
            self.assertTrue(summary["staging"]["quarantined"])

    def test_publication_reread_rejects_oversized_raw_before_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            contract = _contract(repo, store)
            seed = store / "private" / EXPERIMENT_ID / "seed.bin"
            _write(seed, b"s" * 32)

            def execute(*_args: object, **_kwargs: object) -> dict[str, object]:
                _write(contract["raw"], b"123456789")
                return {"summary": {"disposition": "pending-reconstruction"}}

            with (
                mock.patch(f"{MODULE}._recover_incomplete_startup", return_value=False),
                mock.patch(f"{MODULE}.output_contract", return_value=contract),
                mock.patch(
                    f"{MODULE}.locked_context",
                    return_value=(
                        EXECUTION_COMMIT,
                        {"implementation_git_commit": IMPLEMENTATION_COMMIT},
                        {"purpose": "anchor"},
                        {"experiment_id": EXPERIMENT_ID},
                    ),
                ),
                mock.patch(f"{MODULE}._execute_locked_raw", side_effect=execute),
                mock.patch(f"{MODULE}.seed_path", return_value=seed),
                mock.patch(
                    f"{MODULE}.verify_fresh_root",
                    return_value={"pass": True, "status": "passed"},
                ),
                mock.patch(f"{MODULE}.MAX_RAW_BYTES", 8),
                mock.patch(
                    f"{MODULE}._record_artifact_bounded",
                    side_effect=AssertionError(
                        "publication advanced past oversized authoritative raw"
                    ),
                ) as record,
                mock.patch(f"{MODULE}._invalidate_publication") as invalidate,
                self.assertRaisesRegex(RuntimeError, "raw publication read failed"),
            ):
                run(repo)

            record.assert_not_called()
            self.assertEqual(
                invalidate.call_args.kwargs["code"],
                "raw_publication_read_failed",
            )


class LockedInputHardWallTests(unittest.TestCase):
    def test_oversized_acceptance_is_rejected_before_identity_hashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            _write(repo / ACCEPTANCE_PATH, b"123456789")

            with (
                mock.patch(f"{MODULE}.MAX_ACCEPTANCE_BYTES", 8),
                mock.patch(
                    f"{MODULE}.sha256_file",
                    side_effect=AssertionError(
                        "acceptance identity hashing read oversized input"
                    ),
                ) as identity_hash,
                self.assertRaisesRegex(ProtocolError, "bounded regular file"),
            ):
                validate_acceptance(repo)

            identity_hash.assert_not_called()

    def test_oversized_run_lock_is_rejected_before_lock_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            _write(repo / RUN_LOCK_PATH, b"123456789")

            with (
                mock.patch(f"{MODULE}.MAX_RUN_LOCK_BYTES", 8),
                mock.patch(
                    f"{MODULE}._exact",
                    side_effect=AssertionError(
                        "run-lock validation received oversized input"
                    ),
                ) as exact,
                self.assertRaisesRegex(ProtocolError, "bounded regular file"),
            ):
                validate_run_lock(
                    repo,
                    EXECUTION_COMMIT,
                    allow_regeneration=False,
                )

            exact.assert_not_called()


class AuthorityProcessGroupTests(unittest.TestCase):
    class _CompletedProcess:
        pid = 1234
        returncode = 0

        def communicate(
            self,
            *,
            input: bytes,
            timeout: float,
        ) -> tuple[bytes, bytes]:
            del input, timeout
            return b"", b""

    class _TimedOutProcess:
        pid = 1234
        returncode = None

        def communicate(self, *, input: bytes, timeout: float) -> tuple[bytes, bytes]:
            del input
            raise subprocess.TimeoutExpired("nested", timeout)

    @unittest.skipUnless(os.name == "posix", "process-group contract is POSIX-only")
    def test_forged_marker_cannot_claim_membership_in_authority_session(self) -> None:
        process = self._CompletedProcess()
        with (
            mock.patch.dict(os.environ, {_AUTHORITY_GROUP_ENV: "1"}),
            mock.patch(f"{MODULE}.time.monotonic", return_value=10.0),
            mock.patch(f"{MODULE}.os.getpgrp", return_value=101),
            mock.patch(f"{MODULE}.os.getsid", return_value=202),
            mock.patch(f"{MODULE}.subprocess.Popen", return_value=process) as popen,
            mock.patch(
                f"{MODULE}._capture_process_bounded",
                return_value={
                    "status": "completed",
                    "returncode": 0,
                    "stdout": b"",
                    "stderr": b"",
                },
            ) as capture,
        ):
            result = _communicate_bounded(
                ["synthetic-worker"],
                repo=Path.cwd(),
                deadline=20.0,
                environment={},
            )

        self.assertEqual(result["status"], "completed")
        self.assertIs(popen.call_args.kwargs["start_new_session"], True)
        self.assertEqual(
            popen.call_args.kwargs["env"][_AUTHORITY_GROUP_ENV],
            "1",
        )
        self.assertIs(
            capture.call_args.kwargs["inside_authority_group"],
            False,
        )

    @unittest.skipUnless(os.name == "posix", "process-group contract is POSIX-only")
    def test_nested_timeout_kills_the_single_inherited_authority_group(self) -> None:
        process = self._TimedOutProcess()

        def capture_timeout(
            captured_process: object,
            **kwargs: object,
        ) -> dict[str, object]:
            self.assertIs(captured_process, process)
            self.assertIs(kwargs["inside_authority_group"], True)
            os.killpg(os.getpgrp(), signal.SIGKILL)
            kill_child(captured_process)
            return {
                "status": "timeout",
                "returncode": None,
                "stdout": b"",
                "stderr": b"",
            }

        with (
            mock.patch.dict(os.environ, {_AUTHORITY_GROUP_ENV: "1"}),
            mock.patch(f"{MODULE}.time.monotonic", return_value=10.0),
            mock.patch(f"{MODULE}.os.getpgrp", return_value=101),
            mock.patch(f"{MODULE}.os.getsid", return_value=101),
            mock.patch(f"{MODULE}.subprocess.Popen", return_value=process) as popen,
            mock.patch(f"{MODULE}.os.killpg") as killpg,
            mock.patch(f"{MODULE}._kill_process_group") as kill_child,
            mock.patch(
                f"{MODULE}._capture_process_bounded",
                side_effect=capture_timeout,
            ),
        ):
            result = _communicate_bounded(
                ["synthetic-nested-worker"],
                repo=Path.cwd(),
                deadline=20.0,
                environment={},
            )

        self.assertEqual(result["status"], "timeout")
        self.assertIs(popen.call_args.kwargs["start_new_session"], False)
        killpg.assert_called_once_with(101, signal.SIGKILL)
        kill_child.assert_called_once_with(process)


class ProcessCaptureHardWallTests(unittest.TestCase):
    def test_stdout_and_stderr_overflow_kill_without_returning_oversized_bytes(
        self,
    ) -> None:
        for descriptor, constant in (
            (1, "MAX_PROCESS_STDOUT_BYTES"),
            (2, "MAX_PROCESS_STDERR_BYTES"),
        ):
            with self.subTest(descriptor=descriptor):
                started = time.monotonic()
                with mock.patch(f"{MODULE}.{constant}", 8):
                    result = _communicate_bounded(
                        [
                            sys.executable,
                            "-c",
                            (
                                "import os,time;"
                                f"os.write({descriptor},b'123456789');"
                                "time.sleep(5)"
                            ),
                        ],
                        repo=Path.cwd(),
                        deadline=started + 2.0,
                        environment={},
                    )
                self.assertEqual(result["status"], "output-limit")
                self.assertEqual(result["stdout"], b"")
                self.assertEqual(result["stderr"], b"")
                self.assertLess(time.monotonic() - started, 1.0)

    def test_spawn_delay_cannot_reuse_pre_spawn_remaining_time(self) -> None:
        real_popen = subprocess.Popen

        def delayed_popen(*args: object, **kwargs: object) -> object:
            time.sleep(0.06)
            return real_popen(*args, **kwargs)

        started = time.monotonic()
        with mock.patch(
            f"{MODULE}.subprocess.Popen",
            side_effect=delayed_popen,
        ):
            result = _communicate_bounded(
                [sys.executable, "-c", "import time;time.sleep(5)"],
                repo=Path.cwd(),
                deadline=started + 0.02,
                environment={},
            )
        self.assertEqual(result["status"], "timeout")
        self.assertLess(time.monotonic() - started, 1.0)

    def test_one_exec_consumer_uses_the_same_streaming_ceiling(self) -> None:
        real_popen = subprocess.Popen

        def oversized_worker(
            _command: object,
            **kwargs: object,
        ) -> object:
            return real_popen(
                [
                    sys.executable,
                    "-c",
                    "import os,time;os.write(1,b'123456789');time.sleep(5)",
                ],
                **kwargs,
            )

        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch(
                f"{MODULE}.subprocess.Popen",
                side_effect=oversized_worker,
            ),
            mock.patch(f"{MODULE}.MAX_CONSUMER_STDOUT_BYTES", 8),
        ):
            repo = Path(temporary).resolve()
            result = _run_exec_consumer(
                repo,
                request=b"{}",
                workspace=repo,
                deadline=time.monotonic() + 2.0,
                timeout_seconds=2.0,
            )
        self.assertEqual(result["status"], "output-limit")
        self.assertEqual(result["stdout"], b"")
        self.assertEqual(result["stderr"], b"")

    @unittest.skipUnless(os.name == "posix", "process-group contract is POSIX-only")
    def test_output_overflow_kills_a_same_group_grandchild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            ready = repo / "grandchild-ready"
            escaped = repo / "grandchild-escaped"
            pid_path = repo / "grandchild-pid"
            grandchild = (
                "import os,pathlib,sys,time;"
                "pathlib.Path(sys.argv[1]).write_text('ready');"
                "pathlib.Path(sys.argv[3]).write_text(str(os.getpid()));"
                "time.sleep(0.35);"
                "pathlib.Path(sys.argv[2]).write_text('retained');"
                "time.sleep(5)"
            )
            parent = (
                "import os,pathlib,subprocess,sys,time;"
                f"subprocess.Popen([sys.executable,'-S','-c',{grandchild!r},"
                f"{str(ready)!r},{str(escaped)!r},{str(pid_path)!r}]);"
                f"ready=pathlib.Path({str(ready)!r});"
                "deadline=time.monotonic()+2;"
                "\nwhile not ready.exists() and time.monotonic()<deadline:"
                " time.sleep(0.005)"
                "\nos.write(1,b'123456789');time.sleep(5)"
            )
            try:
                with (
                    mock.patch.dict(
                        os.environ,
                        {_AUTHORITY_GROUP_ENV: "0"},
                    ),
                    mock.patch(f"{MODULE}.MAX_PROCESS_STDOUT_BYTES", 8),
                ):
                    result = _communicate_bounded(
                        [sys.executable, "-S", "-c", parent],
                        repo=repo,
                        deadline=time.monotonic() + 3.0,
                        environment={"PATH": os.defpath},
                    )

                self.assertEqual(result["status"], "output-limit")
                time.sleep(0.55)
                self.assertFalse(
                    escaped.exists(),
                    "same-group grandchild survived supervised output overflow",
                )
            finally:
                if pid_path.exists():
                    try:
                        os.kill(int(pid_path.read_text()), signal.SIGKILL)
                    except (OSError, ValueError):
                        pass


class StartupRecoveryHardWallTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_symlinked_private_parent_blocks_the_pre_unseal_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = (repo / ".evidence").resolve()
            outside = base / "outside"
            store.mkdir(parents=True)
            outside.mkdir()
            (store / "private").symlink_to(outside, target_is_directory=True)

            def git_output(_repo: Path, *args: str) -> str:
                if args == ("status", "--porcelain=v1"):
                    return ""
                if args == ("rev-parse", "HEAD"):
                    return IMPLEMENTATION_COMMIT
                raise AssertionError(args)

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(f"{MODULE}.git_output", side_effect=git_output),
                mock.patch(f"{MODULE}.assert_protocol_unchanged"),
                mock.patch(
                    f"{MODULE}.validate_acceptance",
                    return_value={"experiment_id": EXPERIMENT_ID},
                ),
                self.assertRaisesRegex(RuntimeError, "evidence root"),
            ):
                _assert_preparation_boundary(repo, IMPLEMENTATION_COMMIT)

            self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipUnless(os.name == "posix", "symlink collision is POSIX-only")
    def test_dangling_failure_symlink_blocks_the_pre_unseal_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            contract = _contract(repo, store)
            contract["failed_raw"].parent.mkdir(parents=True, exist_ok=True)
            contract["failed_raw"].symlink_to(repo / "absent-target")

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                self.assertRaisesRegex(RuntimeError, "failure authority exists"),
            ):
                output_contract(repo, allow_manifest=False)

    def test_partial_prior_recovery_finishes_once_and_then_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            contract = _contract(repo, store)

            # This is the state after a prior process moved raw but died before
            # moving staging, the journal, and the managed reconstruction root.
            _write(contract["failed_raw"], b"retained raw")
            _write(contract["raw_staging"], b"pending raw")
            contract["journal"].mkdir(parents=True)
            _write(contract["journal"] / "partial.otj", b"partial journal")
            contract["reconstruction_root"].mkdir(parents=True)
            _write(
                contract["reconstruction_root"] / "partial.bin",
                b"partial reconstruction",
            )

            with mock.patch(f"{MODULE}._store", return_value=store):
                self.assertTrue(_recover_incomplete_startup(repo))
                self.assertFalse(_recover_incomplete_startup(repo))

            for active in ("raw", "raw_staging", "journal", "reconstruction_root"):
                self.assertFalse(contract[active].exists())
            for retained in (
                "failed_raw",
                "failed_raw_staging",
                "failed_journal",
                "failed_reconstruction_root",
                "failure",
            ):
                self.assertTrue(contract[retained].exists())

            contract["failure"].chmod(0o600)
            failure = json.loads(contract["failure"].read_bytes())
            self.assertEqual(
                failure["operational_failure"],
                "interrupted_calibration_recovered_at_startup",
            )
            self.assertTrue(failure["raw_transaction"]["raw"]["quarantined"])
            self.assertTrue(failure["raw_transaction"]["staging"]["quarantined"])
            self.assertEqual(
                failure["reconstruction_transaction"],
                {"status": "retained", "quarantined": True},
            )
            self.assertTrue(failure["encounter_journal"]["quarantined"])

    def test_startup_attempts_every_failure_surface_after_an_earlier_error(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            contract = _contract(repo, store)
            _write(contract["raw"], b"interrupted raw")

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(
                    f"{MODULE}._publication_completion_ready",
                    return_value=False,
                ),
                mock.patch(
                    f"{MODULE}._quarantine_publication",
                    side_effect=OSError("first preservation failed"),
                ) as publication,
                mock.patch(
                    f"{MODULE}._quarantine_raw_transaction",
                    return_value={"raw": {"quarantined": True}},
                ) as raw,
                mock.patch(
                    f"{MODULE}._quarantine_reconstruction_root",
                    return_value={"status": "absent", "quarantined": False},
                ) as reconstruction,
                mock.patch(
                    f"{MODULE}._quarantine_encounter_journal",
                    return_value={"status": "absent", "quarantined": False},
                ) as journal,
                mock.patch(f"{MODULE}._failure") as failure,
                self.assertRaisesRegex(OSError, "first preservation failed"),
            ):
                _recover_incomplete_startup(repo)

            publication.assert_called_once()
            raw.assert_called_once()
            reconstruction.assert_called_once()
            journal.assert_called_once()
            failure.assert_called_once()

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_startup_never_accepts_a_symlink_as_a_failure_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            contract = _contract(repo, store)
            _write(contract["raw"], b"interrupted raw")
            outside = repo / "outside-failure.json"
            _write(outside, b"not an OT-0077 failure receipt")
            contract["failure"].parent.mkdir(parents=True, exist_ok=True)
            contract["failure"].symlink_to(outside)

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(
                    f"{MODULE}._publication_completion_ready",
                    return_value=False,
                ),
                mock.patch(f"{MODULE}._quarantine_publication"),
                mock.patch(
                    f"{MODULE}._quarantine_raw_transaction",
                    return_value={},
                ),
                mock.patch(
                    f"{MODULE}._quarantine_reconstruction_root",
                    return_value={"status": "absent", "quarantined": False},
                ),
                mock.patch(
                    f"{MODULE}._quarantine_encounter_journal",
                    return_value={"status": "absent", "quarantined": False},
                ),
                self.assertRaisesRegex(RuntimeError, "sealed output already exists"),
            ):
                _recover_incomplete_startup(repo)

            self.assertTrue(contract["failure"].is_symlink())
            self.assertEqual(outside.read_bytes(), b"not an OT-0077 failure receipt")

    def test_startup_rejects_a_canonical_but_context_unrelated_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            contract = _contract(repo, store)
            _write(contract["raw"], b"interrupted raw")
            unrelated = {
                "schema_version": 1,
                "experiment_id": EXPERIMENT_ID,
                "run_id": DEFAULT_RUN_ID,
                "operational_failure": "unrelated_valid_failure",
                "public_manifest_retained": False,
                "authoritative_raw_retained": False,
                "encounter_journal": None,
                "raw_transaction": None,
                "reconstruction_transaction": None,
                "authorized_actor_candidate_count": 0,
            }
            _write(contract["failure"], canonical_json(unrelated))
            contract["failure"].chmod(0o400)

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(
                    f"{MODULE}._publication_completion_ready",
                    return_value=False,
                ),
                mock.patch(f"{MODULE}._quarantine_publication"),
                mock.patch(
                    f"{MODULE}._quarantine_raw_transaction",
                    return_value={},
                ),
                mock.patch(
                    f"{MODULE}._quarantine_reconstruction_root",
                    return_value={"status": "absent", "quarantined": False},
                ),
                mock.patch(
                    f"{MODULE}._quarantine_encounter_journal",
                    return_value={"status": "absent", "quarantined": False},
                ),
                self.assertRaisesRegex(RuntimeError, "sealed output already exists"),
            ):
                _recover_incomplete_startup(repo)

    @unittest.skipUnless(os.name == "posix", "directory-FD rename is POSIX-only")
    def test_journal_parent_swap_cannot_substitute_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            store = base / "store"
            source = store / "runs" / EXPERIMENT_ID / "race.journal"
            target = store / "failures" / EXPERIMENT_ID / "race.journal"
            source.mkdir(parents=True)
            _write(source / "identity.bin", b"genuine journal")
            wrong_parent = base / "wrong-parent"
            wrong = wrong_parent / source.name
            wrong.mkdir(parents=True)
            _write(wrong / "identity.bin", b"substitute journal")
            displaced_parent = base / "displaced-source-parent"
            real_rename = os.rename
            swapped = False

            def swap_parent_then_rename(
                src: str,
                dst: str,
                *args: object,
                **kwargs: object,
            ) -> None:
                nonlocal swapped
                if not swapped and kwargs.get("src_dir_fd") is not None:
                    swapped = True
                    real_rename(source.parent, displaced_parent)
                    source.parent.symlink_to(
                        wrong_parent,
                        target_is_directory=True,
                    )
                real_rename(src, dst, *args, **kwargs)

            with (
                mock.patch(f"{MODULE}.os.rename", side_effect=swap_parent_then_rename),
                self.assertRaisesRegex(
                    ProtocolError,
                    "journal quarantine (chain|generation) changed",
                ),
            ):
                _quarantine_encounter_journal(source, target)

            self.assertTrue(swapped)
            self.assertEqual(
                (target / "identity.bin").read_bytes(),
                b"genuine journal",
            )
            self.assertEqual(
                (source / "identity.bin").read_bytes(),
                b"substitute journal",
            )

    @unittest.skipUnless(os.name == "posix", "directory-FD rename is POSIX-only")
    def test_reconstruction_quarantine_cannot_report_a_deleted_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            contract = _contract(repo, store)
            contract["reconstruction_root"].mkdir(parents=True)
            store_identity = _authority_root_identity(store, "evidence store")
            real_open = _open_authority_root
            opens = 0

            def delete_target_during_final_rebind(
                path: Path,
                identity: object,
                label: str,
            ) -> int:
                nonlocal opens
                opens += 1
                if opens == 2:
                    contract["failed_reconstruction_root"].rmdir()
                return real_open(path, identity, label)

            with (
                mock.patch(
                    f"{MODULE}._open_authority_root",
                    side_effect=delete_target_during_final_rebind,
                ),
                self.assertRaises((FileNotFoundError, ProtocolError)),
            ):
                _quarantine_reconstruction_root(
                    contract["reconstruction_root"],
                    contract["failed_reconstruction_root"],
                    expected_store_identity=store_identity,
                )

            self.assertFalse(contract["reconstruction_root"].exists())
            self.assertFalse(contract["failed_reconstruction_root"].exists())


@unittest.skipUnless(os.name == "posix", "directory-FD publication is POSIX-only")
class SecurePublicationPrimitiveTests(unittest.TestCase):
    def test_changed_authority_root_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "store"
            root.mkdir()
            identity = _authority_root_identity(root, "evidence store")
            root.rename(base / "original-store")
            root.mkdir()

            with self.assertRaisesRegex(ProtocolError, "identity changed"):
                _open_authority_root(root, identity, "evidence store")

    def test_manifest_install_is_strictly_no_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            destination = (
                repo
                / "evidence"
                / "manifests"
                / EXPERIMENT_ID
                / f"{DEFAULT_RUN_ID}.json"
            )
            sentinel = b"existing manifest must not be replaced"
            _write(destination, sentinel)
            repo_descriptor = os.open(
                repo,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                with self.assertRaisesRegex(ProtocolError, "destination is occupied"):
                    _secure_manifest_install(
                        repo_descriptor,
                        artifact_id=DEFAULT_RUN_ID,
                        encoded=b"replacement",
                    )
            finally:
                os.close(repo_descriptor)

            self.assertEqual(destination.read_bytes(), sentinel)

    def test_bounded_secure_read_preserves_owner_readable_sealed_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent_path = Path(temporary).resolve()
            leaf = parent_path / "sealed.bin"
            _write(leaf, b"sealed authority")
            leaf.chmod(0o400)
            parent = os.open(
                parent_path,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                payload = _read_leaf_bounded_at(
                    parent,
                    leaf.name,
                    limit=1024,
                    label="sealed test authority",
                )
            finally:
                os.close(parent)

            self.assertEqual(payload, b"sealed authority")
            self.assertEqual(stat.S_IMODE(leaf.stat().st_mode), 0o400)

    def test_bounded_secure_read_rejects_unreadable_sealed_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent_path = Path(temporary).resolve()
            leaf = parent_path / "sealed.bin"
            _write(leaf, b"sealed authority")
            leaf.chmod(0)
            parent = os.open(
                parent_path,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                with (
                    mock.patch(f"{MODULE}.os.open", wraps=os.open) as open_file,
                    self.assertRaisesRegex(ProtocolError, "file identity differs"),
                ):
                    _read_leaf_bounded_at(
                        parent,
                        leaf.name,
                        limit=1024,
                        label="sealed test authority",
                    )
                open_file.assert_not_called()
            finally:
                os.close(parent)

            self.assertEqual(stat.S_IMODE(leaf.stat().st_mode), 0)

    def test_exact_existing_object_reuse_fsyncs_destination_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary).resolve()
            payload = b"exact existing content-addressed object"
            digest = sha256_bytes(payload)
            source = store / "source.bin"
            destination = store / "objects" / "sha256" / digest[:2] / digest
            _write(source, payload)
            _write(destination, payload)
            destination.chmod(0o400)
            original = destination.stat()
            store_descriptor = os.open(
                store,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0),
            )
            source_descriptor = os.open(
                source,
                os.O_RDONLY | getattr(os, "O_CLOEXEC", 0),
            )
            real_fsync = os.fsync
            synced_directories: list[tuple[int, int]] = []

            def observe_fsync(descriptor: int) -> None:
                observed = os.fstat(descriptor)
                if stat.S_ISDIR(observed.st_mode):
                    synced_directories.append((observed.st_dev, observed.st_ino))
                real_fsync(descriptor)

            try:
                with mock.patch(f"{MODULE}.os.fsync", side_effect=observe_fsync):
                    _secure_object_install(
                        store_descriptor,
                        source_descriptor,
                        artifact_sha256=digest,
                        artifact_bytes=len(payload),
                    )
            finally:
                os.close(source_descriptor)
                os.close(store_descriptor)

            current = destination.stat()
            self.assertEqual(
                (current.st_dev, current.st_ino),
                (original.st_dev, original.st_ino),
            )
            self.assertEqual(destination.read_bytes(), payload)
            self.assertTrue(synced_directories)

    def test_exact_post_link_residue_is_recovered_without_replacing_object(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary).resolve()
            payload = b"post-link crash residue"
            digest = sha256_bytes(payload)
            source = store / "source.bin"
            destination = store / "objects" / "sha256" / digest[:2] / digest
            staging = destination.with_suffix(".partial")
            _write(source, payload)
            _write(destination, payload)
            os.link(destination, staging)
            original = destination.stat()
            store_descriptor = os.open(
                store,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0),
            )
            source_descriptor = os.open(
                source,
                os.O_RDONLY | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                _secure_object_install(
                    store_descriptor,
                    source_descriptor,
                    artifact_sha256=digest,
                    artifact_bytes=len(payload),
                )
            finally:
                os.close(source_descriptor)
                os.close(store_descriptor)

            current = destination.stat()
            self.assertEqual(
                (current.st_dev, current.st_ino),
                (original.st_dev, original.st_ino),
            )
            self.assertEqual(destination.read_bytes(), payload)
            self.assertFalse(staging.exists())

    def test_contract_store_write_rejects_an_intermediate_parent_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            repo.mkdir()
            store.mkdir()
            contract = _contract(repo, store)
            outside = base / "outside"
            outside.mkdir()
            promotion_parent = Path(contract["promotion"]).parent
            promotion_parent.parent.mkdir(parents=True)
            promotion_parent.symlink_to(outside, target_is_directory=True)

            with self.assertRaises(ProtocolError):
                _write_contract_store_sealed_bytes(
                    contract,
                    "promotion",
                    b"must remain inside the pinned store",
                    limit=1024,
                )

            self.assertEqual(list(outside.iterdir()), [])

    def test_pinned_journal_worker_reads_one_real_sealed_stage(self) -> None:
        from tests.test_ot0077_journal import (
            SCIENTIFIC_SHA256,
            build_chain,
            create_stage,
            write_chain,
        )

        with tempfile.TemporaryDirectory() as temporary:
            repo = (Path(temporary) / "repo").resolve()
            store = repo / ".evidence"
            journal = store / ANCHOR_JOURNAL_RELATIVE_PATH
            repo.mkdir()
            (repo / "src").symlink_to(
                Path(__file__).resolve().parents[1] / "src",
                target_is_directory=True,
            )
            journal.parent.mkdir(parents=True)
            chain = build_chain(0, horizon=1)
            stage = create_stage(
                journal,
                case_count=1,
                segment_count=1,
                encounter_count=1,
            )
            write_chain(stage, chain)
            binding = stage.seal(scientific_sha256=SCIENTIFIC_SHA256)

            result = _journal_stage_binding_bounded(
                repo,
                store=store,
                journal=journal,
                expected_scientific_sha256=SCIENTIFIC_SHA256,
                repo_identity=_authority_root_identity(repo, "repository"),
                store_identity=_authority_root_identity(store, "evidence store"),
                deadline=time.monotonic() + 10.0,
            )

            self.assertEqual(result["binding"], binding)
            self.assertTrue(result["sealed"])
            self.assertFalse(result["torn_tail"])


class PublicationQuarantineHardWallTests(unittest.TestCase):
    def test_quarantine_rejects_a_store_root_rebound_after_contract_creation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            repo.mkdir()
            store.mkdir()
            contract = _contract(repo, store)
            promotion = Path(contract["promotion"])
            _write(promotion, b"authority in the original store")
            displaced = base / "displaced-store"
            store.rename(displaced)
            store.mkdir()

            with self.assertRaisesRegex(RuntimeError, "public authority"):
                _quarantine_publication(contract)

            displaced_promotion = displaced / promotion.relative_to(store)
            self.assertEqual(
                displaced_promotion.read_bytes(),
                b"authority in the original store",
            )
            self.assertEqual(list(store.iterdir()), [])

    def test_conflicting_failure_copy_never_authorizes_source_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            store = repo / ".evidence"
            repo.mkdir(exist_ok=True)
            store.mkdir()
            contract = _contract(repo, store)
            manifest = Path(contract["manifest"])
            failed_manifest = Path(contract["failed_manifest"])
            _write(manifest, b"current manifest evidence")
            _write(failed_manifest, b"older conflicting evidence")

            with self.assertRaises(RuntimeError):
                _quarantine_publication(contract)

            self.assertEqual(manifest.read_bytes(), b"current manifest evidence")
            self.assertEqual(
                failed_manifest.read_bytes(),
                b"older conflicting evidence",
            )

    @unittest.skipUnless(os.name == "posix", "directory-FD publication is POSIX-only")
    def test_secure_record_and_bind_complete_the_intended_publication_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = (Path(temporary) / "repo").resolve()
            store = repo / ".evidence"
            (repo / "src").mkdir(parents=True)
            source_root = Path(__file__).resolve().parents[1] / "src"
            for package in ("open_trajectory_harness", "open_trajectory_evidence"):
                (repo / "src" / package).symlink_to(
                    source_root / package,
                    target_is_directory=True,
                )
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            _write(repo / "anchor.txt", b"publication test anchor\n")
            subprocess.run(["git", "add", "anchor.txt"], cwd=repo, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Open Trajectory",
                    "-c",
                    "user.email=invalid",
                    "commit",
                    "-qm",
                    "publication anchor",
                ],
                cwd=repo,
                check=True,
            )
            execution_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            artifact = store / "synthetic-raw.bin"
            payload = b"authoritative raw"
            _write(artifact, payload)
            digest = sha256_bytes(payload)

            manifest = _record_artifact_bounded(
                repo,
                input_path=artifact,
                store=store,
                artifact_id=DEFAULT_RUN_ID,
                kind="e14-anchor-prepublication-raw",
                artifact_sha256=digest,
                artifact_bytes=len(payload),
                recipe=None,
                limitations=[],
                input_manifests=[],
                deadline=time.monotonic() + 10.0,
            )
            binding = _manifest_binding_bounded(
                repo,
                path=manifest,
                artifact_id=DEFAULT_RUN_ID,
                kind="e14-anchor-prepublication-raw",
                artifact_sha256=digest,
                artifact_bytes=len(payload),
                execution_commit=execution_commit,
                store=store,
                recipe=None,
                input_manifests=[],
                limitations=[],
                environment_dirty=True,
                deadline=time.monotonic() + 10.0,
            )

            self.assertEqual(binding["artifact_sha256"], digest)
            self.assertEqual(binding["artifact_bytes"], len(payload))
            self.assertEqual(
                binding["readback_status"],
                "manifest and evidence bytes verified",
            )

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_manifest_bind_rejects_an_indirect_object_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            (repo / "src").mkdir(parents=True)
            (repo / "src" / "open_trajectory_harness").symlink_to(
                Path(__file__).resolve().parents[1]
                / "src"
                / "open_trajectory_harness",
                target_is_directory=True,
            )
            (repo / "src" / "open_trajectory_evidence").symlink_to(
                Path(__file__).resolve().parents[1]
                / "src"
                / "open_trajectory_evidence",
                target_is_directory=True,
            )
            payload = b"authoritative raw"
            digest = sha256_bytes(payload)
            outside = base / "outside-objects"
            outside_object = outside / "sha256" / digest[:2] / digest
            _write(outside_object, payload)
            store.mkdir()
            (store / "objects").symlink_to(outside, target_is_directory=True)
            manifest = {
                "schema_version": 1,
                "experiment_id": EXPERIMENT_ID,
                "artifact_id": DEFAULT_RUN_ID,
                "kind": "e14-anchor-prepublication-raw",
                "media_type": "application/octet-stream",
                "sha256": digest,
                "bytes": len(payload),
                "evidence_class": "private-reproducible",
                "availability": {"local_object": True},
                "reconstruction": {
                    "recipe": None,
                    "expected_output": f"artifact:{DEFAULT_RUN_ID}",
                },
                "environment": {
                    "git": {"commit": EXECUTION_COMMIT, "dirty": False},
                },
                "input_manifests": [],
                "limitations": [],
            }
            manifest_path = (
                repo
                / "evidence"
                / "manifests"
                / EXPERIMENT_ID
                / f"{DEFAULT_RUN_ID}.json"
            )
            _write(
                manifest_path,
                (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
            )

            with self.assertRaises((ProtocolError, RuntimeError)):
                _manifest_binding_bounded(
                    repo,
                    path=manifest_path,
                    artifact_id=DEFAULT_RUN_ID,
                    kind="e14-anchor-prepublication-raw",
                    artifact_sha256=digest,
                    artifact_bytes=len(payload),
                    execution_commit=EXECUTION_COMMIT,
                    store=store,
                    recipe=None,
                    input_manifests=[],
                    limitations=[],
                    environment_dirty=False,
                    deadline=time.monotonic() + 5.0,
                )

            self.assertEqual(outside_object.read_bytes(), payload)

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_record_worker_rejects_an_object_staging_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            artifact = store / "synthetic-raw.bin"
            payload = b"authoritative raw"
            _write(artifact, payload)
            (repo / "src").symlink_to(
                Path(__file__).resolve().parents[1] / "src",
                target_is_directory=True,
            )
            digest = sha256_bytes(payload)
            object_target = store / "objects" / "sha256" / digest[:2] / digest
            object_target.parent.mkdir(parents=True)
            outside = base / "outside-staging-target.bin"
            _write(outside, b"unrelated outside bytes")
            object_target.with_suffix(".partial").symlink_to(outside)

            with self.assertRaises((ProtocolError, RuntimeError)):
                _record_artifact_bounded(
                    repo,
                    input_path=artifact,
                    store=store,
                    artifact_id=DEFAULT_RUN_ID,
                    kind="e14-anchor-prepublication-raw",
                    recipe=None,
                    limitations=[],
                    input_manifests=[],
                    deadline=time.monotonic() + 5.0,
                )

            self.assertEqual(outside.read_bytes(), b"unrelated outside bytes")

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_record_worker_rejects_an_existing_object_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            artifact = store / "synthetic-raw.bin"
            payload = b"authoritative raw"
            _write(artifact, payload)
            (repo / "src").symlink_to(
                Path(__file__).resolve().parents[1] / "src",
                target_is_directory=True,
            )
            digest = sha256_bytes(payload)
            object_target = store / "objects" / "sha256" / digest[:2] / digest
            object_target.parent.mkdir(parents=True)
            outside = base / "outside-exact-object.bin"
            _write(outside, payload)
            object_target.symlink_to(outside)

            with self.assertRaises((ProtocolError, RuntimeError)):
                _record_artifact_bounded(
                    repo,
                    input_path=artifact,
                    store=store,
                    artifact_id=DEFAULT_RUN_ID,
                    kind="e14-anchor-prepublication-raw",
                    recipe=None,
                    limitations=[],
                    input_manifests=[],
                    deadline=time.monotonic() + 5.0,
                )

            self.assertEqual(outside.read_bytes(), payload)

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_record_worker_rejects_a_replaced_input_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            artifact = store / RAW_RELATIVE_PATH
            artifact.parent.mkdir(parents=True)
            outside = base / "outside-raw.bin"
            _write(outside, b"outside bytes must not become authority")
            artifact.symlink_to(outside)
            (repo / "src").symlink_to(
                Path(__file__).resolve().parents[1] / "src",
                target_is_directory=True,
            )

            with self.assertRaises((ProtocolError, RuntimeError)):
                _record_artifact_bounded(
                    repo,
                    input_path=artifact,
                    store=store,
                    artifact_id=DEFAULT_RUN_ID,
                    kind="e14-anchor-prepublication-raw",
                    recipe=None,
                    limitations=[],
                    input_manifests=[],
                    deadline=time.monotonic() + 5.0,
                )

            self.assertEqual(
                outside.read_bytes(),
                b"outside bytes must not become authority",
            )

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_record_worker_rejects_a_replaced_object_store_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            artifact = store / "synthetic-raw.bin"
            _write(artifact, b"authoritative raw")
            (repo / "src").symlink_to(
                Path(__file__).resolve().parents[1] / "src",
                target_is_directory=True,
            )
            outside = base / "outside-objects"
            outside.mkdir()
            (store / "objects").symlink_to(outside, target_is_directory=True)

            with self.assertRaises((ProtocolError, RuntimeError)):
                _record_artifact_bounded(
                    repo,
                    input_path=artifact,
                    store=store,
                    artifact_id=DEFAULT_RUN_ID,
                    kind="e14-anchor-prepublication-raw",
                    recipe=None,
                    limitations=[],
                    input_manifests=[],
                    deadline=time.monotonic() + 5.0,
                )

            self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_record_worker_rejects_a_replaced_manifest_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            artifact = store / "synthetic-raw.bin"
            _write(artifact, b"authoritative raw")
            (repo / "src").symlink_to(
                Path(__file__).resolve().parents[1] / "src",
                target_is_directory=True,
            )
            outside = base / "outside-manifests"
            outside.mkdir()
            outside_manifest = outside / f"{DEFAULT_RUN_ID}.json"
            _write(outside_manifest, b"unrelated outside bytes")
            manifest_parent = repo / "evidence" / "manifests" / EXPERIMENT_ID
            manifest_parent.parent.mkdir(parents=True)
            manifest_parent.symlink_to(outside, target_is_directory=True)

            with self.assertRaises((ProtocolError, RuntimeError)):
                _record_artifact_bounded(
                    repo,
                    input_path=artifact,
                    store=store,
                    artifact_id=DEFAULT_RUN_ID,
                    kind="e14-anchor-prepublication-raw",
                    recipe=None,
                    limitations=[],
                    input_manifests=[],
                    deadline=time.monotonic() + 5.0,
                )

            self.assertEqual(
                outside_manifest.read_bytes(),
                b"unrelated outside bytes",
            )

    @unittest.skipUnless(os.name == "posix", "symlink quarantine is POSIX-only")
    def test_startup_recovery_unlinks_an_active_public_leaf_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            contract = _contract(repo, store)
            unrelated = repo / "unrelated.bin"
            _write(unrelated, b"must not be read as publication authority")
            contract["promotion"].parent.mkdir(parents=True, exist_ok=True)
            contract["promotion"].symlink_to(unrelated)

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                self.assertRaisesRegex(
                    RuntimeError,
                    "publication quarantine was not fully preserved",
                ),
            ):
                _recover_incomplete_startup(repo)

            self.assertFalse(contract["promotion"].exists())
            self.assertFalse(contract["promotion"].is_symlink())
            self.assertEqual(
                unrelated.read_bytes(),
                b"must not be read as publication authority",
            )

    @unittest.skipUnless(os.name == "posix", "symlink quarantine is POSIX-only")
    def test_quarantine_never_reads_or_unlinks_through_manifest_parent_symlink(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            contract = _contract(repo, repo / ".evidence")
            _write(contract["manifest"], b"outside bytes must remain untouched")
            manifest_parent = contract["manifest"].parent
            outside_parent = base / "outside-manifests"
            manifest_parent.rename(outside_parent)
            manifest_parent.symlink_to(outside_parent, target_is_directory=True)
            outside_manifest = outside_parent / contract["manifest"].name

            try:
                _quarantine_publication(contract)
            except RuntimeError:
                pass

            self.assertTrue(outside_manifest.exists())
            self.assertEqual(
                outside_manifest.read_bytes(),
                b"outside bytes must remain untouched",
            )
            self.assertFalse(contract["failed_manifest"].exists())

    @unittest.skipUnless(os.name == "posix", "symlink quarantine is POSIX-only")
    def test_quarantine_parent_replacement_after_ancestry_check_is_contained(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            contract = _contract(repo, repo / ".evidence")
            _write(contract["manifest"], b"outside bytes must remain untouched")
            manifest_parent = contract["manifest"].parent
            outside_parent = base / "outside-manifests"
            outside_manifest = outside_parent / contract["manifest"].name

            def replace_parent_after_check(_contract: dict[str, Path]) -> bool:
                manifest_parent.rename(outside_parent)
                manifest_parent.symlink_to(outside_parent, target_is_directory=True)
                return True

            with mock.patch(
                f"{MODULE}._publication_contract_ancestry_ready",
                side_effect=replace_parent_after_check,
            ):
                try:
                    _quarantine_publication(contract)
                except RuntimeError:
                    pass

            self.assertTrue(outside_manifest.exists())
            self.assertEqual(
                outside_manifest.read_bytes(),
                b"outside bytes must remain untouched",
            )
            self.assertFalse(contract["failed_manifest"].exists())

    def test_oversized_public_surface_is_unlinked_without_copying_its_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            contract = _contract(repo, (repo / ".evidence").resolve())
            _write(contract["promotion"], b"123456789")

            with (
                mock.patch(f"{MODULE}.MAX_PROMOTION_BYTES", 8),
                self.assertRaisesRegex(
                    RuntimeError,
                    "publication quarantine was not fully preserved",
                ),
            ):
                _quarantine_publication(contract)

            self.assertFalse(contract["promotion"].exists())
            self.assertFalse(contract["failed_promotion"].exists())

    def test_symlink_public_surface_is_unlinked_without_reading_its_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            contract = _contract(repo, (repo / ".evidence").resolve())
            unrelated = repo / "unrelated.bin"
            _write(unrelated, b"must not enter failure evidence")
            contract["promotion"].parent.mkdir(parents=True, exist_ok=True)
            contract["promotion"].symlink_to(unrelated)

            with (
                mock.patch.object(
                    Path,
                    "read_bytes",
                    autospec=True,
                    side_effect=AssertionError(
                        "quarantine followed an untrusted publication symlink"
                    ),
                ),
                self.assertRaisesRegex(
                    RuntimeError,
                    "publication quarantine was not fully preserved",
                ),
            ):
                _quarantine_publication(contract)

            self.assertFalse(contract["promotion"].exists())
            self.assertFalse(contract["promotion"].is_symlink())
            self.assertFalse(contract["failed_promotion"].exists())
            self.assertEqual(unrelated.read_bytes(), b"must not enter failure evidence")


class CompletionWitnessHardWallTests(unittest.TestCase):
    @unittest.skipUnless(Path("/dev/fd").exists(), "descriptor inventory unavailable")
    def test_snapshot_initialization_failure_closes_both_authority_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve() / "repo"
            contract, _journal, _raw_manifest, _promotion_manifest = (
                _completion_fixture(repo, repo / ".evidence")
            )
            completion = json.loads(contract["completion"].read_bytes())
            repo_identity = _authority_root_identity(repo, "repository")
            store_identity = _authority_root_identity(
                contract["store"],
                "evidence store",
            )
            before = set(os.listdir("/dev/fd"))

            with (
                mock.patch(
                    f"{MODULE}._stat_generation",
                    side_effect=OSError("injected snapshot initialization failure"),
                ),
                self.assertRaisesRegex(
                    OSError,
                    "injected snapshot initialization failure",
                ),
            ):
                with _pinned_publication_snapshot(
                    contract,
                    completion,
                    repo_identity=repo_identity,
                    store_identity=store_identity,
                ):
                    self.fail("snapshot initialization unexpectedly succeeded")

            self.assertEqual(set(os.listdir("/dev/fd")), before)

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_completion_rejects_manifest_parent_replaced_by_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            contract, journal, raw_manifest, promotion_manifest = (
                _completion_fixture(repo, repo / ".evidence")
            )
            manifest_parent = contract["manifest"].parent
            outside = base / "outside-manifests"
            manifest_parent.rename(outside)
            manifest_parent.symlink_to(outside, target_is_directory=True)

            with (
                mock.patch(
                    f"{MODULE}._manifest_binding_bounded",
                    side_effect=(raw_manifest, promotion_manifest),
                ),
                mock.patch(
                    f"{MODULE}._journal_stage_binding_bounded",
                    return_value=_stage_binding(journal),
                ),
            ):
                self.assertFalse(_publication_completion_ready(contract))

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_completion_cannot_be_supplied_by_a_transient_parent_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            contract, journal, raw_manifest, promotion_manifest = (
                _completion_fixture(repo, repo / ".evidence")
            )
            completion_bytes = contract["completion"].read_bytes()
            contract["completion"].unlink()
            runs_parent = contract["completion"].parent
            retained_runs = base / "retained-runs"
            outside_runs = base / "outside-runs"
            _write(outside_runs / contract["completion"].name, completion_bytes)
            real_read = __import__(
                MODULE,
                fromlist=["_read_regular_file_bounded"],
            )._read_regular_file_bounded

            def transient_read(path: Path, limit: int) -> bytes:
                if path != contract["completion"]:
                    return real_read(path, limit)
                runs_parent.rename(retained_runs)
                runs_parent.symlink_to(outside_runs, target_is_directory=True)
                try:
                    return real_read(path, limit)
                finally:
                    runs_parent.unlink()
                    retained_runs.rename(runs_parent)

            with (
                mock.patch(
                    f"{MODULE}._read_regular_file_bounded",
                    side_effect=transient_read,
                ),
                mock.patch(
                    f"{MODULE}._manifest_binding_bounded",
                    side_effect=(raw_manifest, promotion_manifest),
                ),
                mock.patch(
                    f"{MODULE}._journal_stage_binding_bounded",
                    return_value=_stage_binding(journal),
                ),
            ):
                self.assertFalse(_publication_completion_ready(contract))

            self.assertFalse(contract["completion"].exists())

    @unittest.skipUnless(os.name == "posix", "directory replacement is POSIX-only")
    def test_completion_binds_one_store_root_identity_for_every_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            contract, journal, raw_manifest, promotion_manifest = (
                _completion_fixture(repo, store)
            )
            completion_bytes = contract["completion"].read_bytes()
            contract["completion"].unlink()
            retained_store = base / "retained-store"
            replacement_store = base / "replacement-store"
            _write(
                replacement_store / COMPLETION_RELATIVE_PATH,
                completion_bytes,
            )
            real_read = __import__(
                MODULE,
                fromlist=["_read_publication_authority_bounded"],
            )._read_publication_authority_bounded

            def transient_store_read(
                observed_contract: dict[str, Path],
                path: Path,
                limit: int,
            ) -> bytes:
                if path != contract["completion"]:
                    return real_read(observed_contract, path, limit)
                store.rename(retained_store)
                replacement_store.rename(store)
                try:
                    return real_read(observed_contract, path, limit)
                finally:
                    store.rename(replacement_store)
                    retained_store.rename(store)

            with (
                mock.patch(
                    f"{MODULE}._read_publication_authority_bounded",
                    side_effect=transient_store_read,
                ),
                mock.patch(
                    f"{MODULE}._manifest_binding_bounded",
                    side_effect=(raw_manifest, promotion_manifest),
                ),
                mock.patch(
                    f"{MODULE}._journal_stage_binding_bounded",
                    return_value=_stage_binding(journal),
                ),
            ):
                self.assertFalse(_publication_completion_ready(contract))

            self.assertFalse(contract["completion"].exists())

    @unittest.skipUnless(os.name == "posix", "directory replacement is POSIX-only")
    def test_completion_journal_read_uses_the_bound_store_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = repo / ".evidence"
            contract, journal, raw_manifest, promotion_manifest = (
                _completion_fixture(repo, store)
            )
            retained_store = base / "retained-store"
            replacement_store = base / "replacement-store"
            (replacement_store / ANCHOR_JOURNAL_RELATIVE_PATH).mkdir(
                parents=True,
            )
            real_stage_binding = __import__(
                MODULE,
                fromlist=["_journal_stage_binding_bounded"],
            )._journal_stage_binding_bounded

            def transient_stage_read(
                *args: object,
                **kwargs: object,
            ) -> dict[str, object]:
                store.rename(retained_store)
                replacement_store.rename(store)
                try:
                    return real_stage_binding(*args, **kwargs)
                finally:
                    store.rename(replacement_store)
                    retained_store.rename(store)

            with (
                mock.patch(
                    f"{MODULE}._manifest_binding_bounded",
                    side_effect=(raw_manifest, promotion_manifest),
                ),
                mock.patch(
                    f"{MODULE}._journal_stage_binding_bounded",
                    side_effect=transient_stage_read,
                ),
            ):
                self.assertFalse(_publication_completion_ready(contract))

            self.assertFalse(contract["journal"].exists())

    def test_startup_completion_wall_begins_before_raw_decode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            contract, journal, raw_manifest, promotion_manifest = (
                _completion_fixture(repo, repo / ".evidence")
            )
            decoded = False

            def clock() -> float:
                return 1_000.0 if decoded else 0.0

            def decode(payload: bytes) -> dict[str, object]:
                nonlocal decoded
                value = decode_raw(payload)
                decoded = True
                return value

            with (
                mock.patch(f"{MODULE}.time.monotonic", side_effect=clock),
                mock.patch(f"{MODULE}.decode_raw", side_effect=decode),
                mock.patch(
                    f"{MODULE}._manifest_binding_bounded",
                    side_effect=(raw_manifest, promotion_manifest),
                ) as bind,
                mock.patch(
                    f"{MODULE}._journal_stage_binding_bounded",
                    return_value=_stage_binding(journal),
                ),
            ):
                self.assertFalse(_publication_completion_ready(contract))

            bind.assert_not_called()

    def test_deleted_completion_witness_never_authorizes_startup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            contract = _contract(repo, repo / ".evidence")
            self.assertFalse(_publication_completion_ready(contract))

    def test_oversized_completion_witness_is_rejected_before_semantic_rebind(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            contract = _contract(repo, repo / ".evidence")
            _write(contract["completion"], b"123456789")
            with (
                mock.patch(f"{MODULE}.MAX_COMPLETION_BYTES", 8),
                mock.patch(f"{MODULE}._manifest_binding_bounded") as bind,
            ):
                self.assertFalse(_publication_completion_ready(contract))
            bind.assert_not_called()

    def test_deleted_artifact_store_binding_invalidates_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            contract, _journal, _raw_manifest, _promotion_manifest = (
                _completion_fixture(repo, repo / ".evidence")
            )
            with mock.patch(
                f"{MODULE}._manifest_binding_bounded",
                side_effect=RuntimeError("artifact-store object missing"),
            ) as bind:
                self.assertFalse(_publication_completion_ready(contract))
            bind.assert_called_once()

    def test_completion_rebind_cannot_outlive_the_original_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            contract, journal, raw_manifest, promotion_manifest = (
                _completion_fixture(repo, repo / ".evidence")
            )
            with (
                mock.patch(
                    f"{MODULE}._manifest_binding_bounded",
                    side_effect=(raw_manifest, promotion_manifest),
                ) as bind,
                mock.patch(
                    f"{MODULE}._journal_stage_binding_bounded",
                    return_value=_stage_binding(journal),
                ),
                mock.patch(
                    f"{MODULE}.time.monotonic",
                    side_effect=(0.0, 0.0, 2.0),
                ),
            ):
                self.assertFalse(
                    _publication_completion_ready(contract, deadline=1.0)
                )

            self.assertEqual(bind.call_count, 2)
            self.assertEqual(
                [call.kwargs["deadline"] for call in bind.call_args_list],
                [1.0, 1.0],
            )


class ManagedReconstructionHardWallTests(unittest.TestCase):
    @unittest.skipUnless(Path("/dev/fd").exists(), "descriptor inventory unavailable")
    def test_authoritative_raw_open_failure_closes_the_store_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            authoritative = store / RAW_RELATIVE_PATH
            _write(authoritative, b"authoritative raw")
            authoritative.chmod(0o400)
            before = set(os.listdir("/dev/fd"))

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(
                    f"{MODULE}._open_relative_regular",
                    side_effect=ProtocolError("injected authoritative open failure"),
                ),
                self.assertRaisesRegex(
                    ProtocolError,
                    "injected authoritative open failure",
                ),
            ):
                verify_fresh_root(
                    repo,
                    implementation=IMPLEMENTATION_COMMIT,
                    seed_bytes=b"s" * 32,
                    authoritative_raw=authoritative,
                )

            self.assertEqual(set(os.listdir("/dev/fd")), before)

    @unittest.skipUnless(Path("/dev/fd").exists(), "descriptor inventory unavailable")
    def test_chain_initialization_failure_closes_the_store_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            authoritative = store / RAW_RELATIVE_PATH
            _write(authoritative, b"authoritative raw")
            authoritative.chmod(0o400)
            before = set(os.listdir("/dev/fd"))

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(
                    f"{MODULE}._stat_generation",
                    side_effect=OSError("injected chain initialization failure"),
                ),
                self.assertRaisesRegex(
                    OSError,
                    "injected chain initialization failure",
                ),
            ):
                verify_fresh_root(
                    repo,
                    implementation=IMPLEMENTATION_COMMIT,
                    seed_bytes=b"s" * 32,
                    authoritative_raw=authoritative,
                )

            self.assertEqual(set(os.listdir("/dev/fd")), before)

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX-only")
    def test_symlinked_reconstruction_parent_cannot_escape_evidence_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            repo = base / "repo"
            store = (repo / ".evidence").resolve()
            outside = base / "outside"
            store.mkdir(parents=True)
            outside.mkdir()
            (store / "reconstruction").symlink_to(
                outside,
                target_is_directory=True,
            )
            authoritative = repo / "authoritative.raw"
            _write(authoritative, b"authoritative raw")

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(f"{MODULE}.child_environment", return_value={}),
                mock.patch(
                    f"{MODULE}._communicate_bounded",
                    side_effect=AssertionError(
                        "escaped reconstruction worker was started"
                    ),
                ) as communicate,
                self.assertRaisesRegex(
                    ProtocolError,
                    "fresh-root reconstruction directory cannot be pinned",
                ),
            ):
                verify_fresh_root(
                    repo,
                    implementation=IMPLEMENTATION_COMMIT,
                    seed_bytes=b"s" * 32,
                    authoritative_raw=authoritative,
                )

            communicate.assert_not_called()
            self.assertEqual(list(outside.iterdir()), [])

    def test_reconstruction_never_receives_a_replaced_oversized_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            store.mkdir(parents=True)
            contract = _contract(repo, store)
            seed = store / "private" / EXPERIMENT_ID / "seed.bin"
            _write(seed, b"s" * 33)

            def execute(*_args: object, **_kwargs: object) -> dict[str, object]:
                _write(contract["raw"], b"bounded raw")
                return {"summary": {"disposition": "pending-reconstruction"}}

            with (
                mock.patch(f"{MODULE}._recover_incomplete_startup", return_value=False),
                mock.patch(f"{MODULE}.output_contract", return_value=contract),
                mock.patch(
                    f"{MODULE}.locked_context",
                    return_value=(
                        EXECUTION_COMMIT,
                        {"implementation_git_commit": IMPLEMENTATION_COMMIT},
                        {"purpose": "anchor"},
                        {"experiment_id": EXPERIMENT_ID},
                    ),
                ),
                mock.patch(f"{MODULE}._execute_locked_raw", side_effect=execute),
                mock.patch(f"{MODULE}.seed_path", return_value=seed),
                mock.patch(
                    f"{MODULE}.verify_fresh_root",
                    side_effect=AssertionError(
                        "oversized seed reached reconstruction"
                    ),
                ) as verify,
                mock.patch(
                    f"{MODULE}._quarantine_reconstruction_root",
                    return_value={"status": "absent", "quarantined": False},
                ),
                mock.patch(
                    f"{MODULE}._quarantine_raw_transaction",
                    return_value={},
                ),
                mock.patch(
                    f"{MODULE}._quarantine_encounter_journal",
                    return_value={},
                ),
                mock.patch(f"{MODULE}._failure"),
                self.assertRaisesRegex(
                    RuntimeError,
                    "fresh-root private reconstruction failed",
                ),
            ):
                run(repo)

            verify.assert_not_called()

    def test_timeout_quarantines_the_exact_managed_reconstruction_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            store.mkdir(parents=True)
            contract = _contract(repo, store)
            authoritative = repo / "authoritative.raw"
            _write(authoritative, b"authoritative raw")

            def timeout(
                _command: list[str],
                *,
                repo: Path,
                deadline: float,
                environment: dict[str, str],
            ) -> dict[str, object]:
                del repo, deadline
                observed_root = Path(environment["OT_EVIDENCE_ROOT"])
                self.assertEqual(
                    observed_root,
                    contract["reconstruction_root"].resolve(),
                )
                _write(observed_root / "partial.bin", b"partial reconstruction")
                return {
                    "status": "timeout",
                    "returncode": None,
                    "stdout": b"",
                    "stderr": b"",
                }

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(f"{MODULE}.child_environment", return_value={}),
                mock.patch(f"{MODULE}._communicate_bounded", side_effect=timeout),
            ):
                result = verify_fresh_root(
                    repo,
                    implementation=IMPLEMENTATION_COMMIT,
                    seed_bytes=b"s" * 32,
                    authoritative_raw=authoritative,
                )

            self.assertEqual(
                result,
                {"pass": False, "status": "reconstruction_timeout"},
            )
            self.assertFalse(contract["reconstruction_root"].exists())
            self.assertTrue(contract["failed_reconstruction_root"].exists())
            self.assertEqual(
                (
                    contract["failed_reconstruction_root"] / "partial.bin"
                ).read_bytes(),
                b"partial reconstruction",
            )

    def test_success_rejects_a_replacement_created_during_final_store_rebind(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            store.mkdir(parents=True)
            contract = _contract(repo, store)
            authoritative = repo / "authoritative.raw"
            payload = b"exact reconstructed raw"
            _write(authoritative, payload)
            real_open = _open_authority_root
            state = {"saw_root": False, "injected": False}

            def reconstruct_process(
                _command: list[str],
                *,
                repo: Path,
                deadline: float,
                environment: dict[str, str],
            ) -> dict[str, object]:
                del repo, deadline
                reconstructed = Path(environment["OT_EVIDENCE_ROOT"]) / RAW_RELATIVE_PATH
                _write(reconstructed, payload)
                reconstructed.chmod(0o400)
                return {
                    "status": "completed",
                    "returncode": 0,
                    "stdout": b"",
                    "stderr": b"",
                }

            def replace_after_cleanup(
                path: Path,
                identity: object,
                label: str,
            ) -> int:
                root = contract["reconstruction_root"]
                if root.exists():
                    state["saw_root"] = True
                elif state["saw_root"] and not state["injected"]:
                    root.mkdir(parents=True)
                    _write(root / "replacement.bin", b"replacement authority")
                    state["injected"] = True
                return real_open(path, identity, label)

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(f"{MODULE}.child_environment", return_value={}),
                mock.patch(
                    f"{MODULE}._communicate_bounded",
                    side_effect=reconstruct_process,
                ),
                mock.patch(
                    f"{MODULE}._open_authority_root",
                    side_effect=replace_after_cleanup,
                ),
                self.assertRaisesRegex(
                    ProtocolError,
                    "cleanup left active authority",
                ),
            ):
                verify_fresh_root(
                    repo,
                    implementation=IMPLEMENTATION_COMMIT,
                    seed_bytes=b"s" * 32,
                    authoritative_raw=authoritative,
                )

            self.assertTrue(state["injected"])
            self.assertEqual(
                (contract["reconstruction_root"] / "replacement.bin").read_bytes(),
                b"replacement authority",
            )

    def test_timeout_rejects_active_replacement_during_final_store_rebind(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            store = (repo / ".evidence").resolve()
            store.mkdir(parents=True)
            contract = _contract(repo, store)
            authoritative = repo / "authoritative.raw"
            _write(authoritative, b"authoritative raw")
            real_open = _open_authority_root
            state = {"injected": False}

            def replace_after_quarantine(
                path: Path,
                identity: object,
                label: str,
            ) -> int:
                if (
                    contract["failed_reconstruction_root"].exists()
                    and not contract["reconstruction_root"].exists()
                    and not state["injected"]
                ):
                    contract["reconstruction_root"].mkdir(parents=True)
                    state["injected"] = True
                return real_open(path, identity, label)

            with (
                mock.patch(f"{MODULE}._store", return_value=store),
                mock.patch(f"{MODULE}.child_environment", return_value={}),
                mock.patch(
                    f"{MODULE}._communicate_bounded",
                    return_value={
                        "status": "timeout",
                        "returncode": None,
                        "stdout": b"",
                        "stderr": b"",
                    },
                ),
                mock.patch(
                    f"{MODULE}._open_authority_root",
                    side_effect=replace_after_quarantine,
                ),
                self.assertRaisesRegex(
                    ProtocolError,
                    "survived quarantine",
                ),
            ):
                verify_fresh_root(
                    repo,
                    implementation=IMPLEMENTATION_COMMIT,
                    seed_bytes=b"s" * 32,
                    authoritative_raw=authoritative,
                )

            self.assertTrue(state["injected"])
            self.assertTrue(contract["failed_reconstruction_root"].exists())
            self.assertTrue(contract["reconstruction_root"].exists())


if __name__ == "__main__":
    unittest.main()
