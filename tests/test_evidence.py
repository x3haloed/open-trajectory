from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from open_trajectory_evidence.evidence import (
    EvidenceError,
    record_artifact,
    verify_artifact,
)


class EvidenceTests(unittest.TestCase):
    def test_record_copies_bytes_and_publishes_no_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            store = root / "private-store"
            source = root / "sensitive-name" / "result.json"
            repo.mkdir()
            source.parent.mkdir()
            source.write_text('{"score": 0.75}\n', encoding="utf-8")

            manifest_path = record_artifact(
                repo=repo,
                input_path=source,
                experiment_id="OT-0001",
                artifact_id="control-result",
                kind="test-result",
                evidence_class="private-reproducible",
                recipe=None,
                public_url=None,
                limitations=["private input corpus"],
                input_manifests=[],
                store=store,
            )

            encoded = manifest_path.read_text(encoding="utf-8")
            self.assertNotIn(str(source), encoded)
            self.assertNotIn("sensitive-name", encoded)
            valid, message = verify_artifact(
                repo=repo,
                manifest_path=manifest_path,
                store=store,
            )
            self.assertTrue(valid, message)

    def test_reprovided_bytes_verify_without_original_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            store = root / "store"
            source = root / "result.txt"
            repo.mkdir()
            source.write_text("external discrepancy\n", encoding="utf-8")
            manifest = record_artifact(
                repo=repo,
                input_path=source,
                experiment_id="OT-0001",
                artifact_id="receipt",
                kind="test-result",
                evidence_class="public-reconstructible",
                recipe="python -m experiment.run",
                public_url=None,
                limitations=[],
                input_manifests=[],
                store=store,
            )
            valid, message = verify_artifact(
                repo=repo,
                manifest_path=manifest,
                artifact_path=source,
            )
            self.assertTrue(valid, message)

    def test_public_evidence_requires_reconstruction_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            source = root / "result.txt"
            repo.mkdir()
            source.write_text("result", encoding="utf-8")
            with self.assertRaises(EvidenceError):
                record_artifact(
                    repo=repo,
                    input_path=source,
                    experiment_id="OT-0001",
                    artifact_id="receipt",
                    kind="test-result",
                    evidence_class="public-reconstructible",
                    recipe=None,
                    public_url=None,
                    limitations=[],
                    input_manifests=[],
                    store=root / "store",
                )


if __name__ == "__main__":
    unittest.main()

