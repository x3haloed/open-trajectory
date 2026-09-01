from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ot0095", ROOT / "experiments/ot_0095_normalized_boundary_self_allocation.py")
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OT0095BoundaryTests(unittest.TestCase):
    def test_nested_pythonpath_resolves_inside(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); (root / "observations/a").mkdir(parents=True)
            result = module.classify_command("cd observations/a && PYTHONPATH=../.. python3 check.py", root)
        self.assertTrue(result["accepted"], result)

    def test_unpaired_traversal_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.assertFalse(module.classify_command("PYTHONPATH=../.. python3 check.py", root)["accepted"])
            self.assertFalse(module.classify_command("sed -n 1,20p ../secret", root)["accepted"])

    def test_outside_resolving_pair_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); (root / "nested").mkdir()
            result = module.classify_command("cd nested && PYTHONPATH=../../.. python3 check.py", root)
        self.assertFalse(result["accepted"], result)

    def test_frozen_world_and_live_frontier_still_pass(self):
        b93 = module.base.base
        prior92 = b93.load_prior(); _, _, _, p82 = b93.prior_chain(prior92)
        parent = b93.load_parent(p82, ROOT, ROOT / ".evidence")
        with tempfile.TemporaryDirectory() as directory:
            result = module.base.fixture_conformance(prior92, p82, parent, Path(directory))
        self.assertTrue(result["passed"], result)


if __name__ == "__main__":
    unittest.main()
