from __future__ import annotations

import unittest

from open_trajectory_harness.ot0046 import AuthorityController, evaluate_scenario, oracle_petition


class OT0046Tests(unittest.TestCase):
    def test_complete_authority_path(self) -> None:
        result = evaluate_scenario(0)
        self.assertTrue(result["pass"])
        self.assertEqual(result["scores"], {"adaptive": 15, "narrow": 5, "broad": 0})

    def test_excessive_and_bypass_fail_closed(self) -> None:
        target = "svc-control"; petition = oracle_petition(target); petition["delta"].append("broad-admin")
        controller = AuthorityController()
        self.assertFalse(controller.petition(petition, {"sealed": True, "independent": True, "gain": 10}))
        self.assertFalse(controller.act(f"repair:{target}", target=target))
        self.assertEqual(controller.ledger[-1]["kind"], "action")


if __name__ == "__main__": unittest.main()
