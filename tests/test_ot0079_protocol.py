import unittest

from open_trajectory_harness import ot0079_protocol as protocol


class OT0079ProtocolTests(unittest.TestCase):
    def test_frozen_worlds_are_valid_and_copied(self) -> None:
        protocol.validate_protocol()
        public = protocol.public_world("a_train")
        public["candidates"][0]["id"] = "changed"
        self.assertEqual(
            protocol.public_world("a_train")["candidates"][0]["id"], "aegis"
        )

    def test_public_world_withholds_requirements(self) -> None:
        self.assertNotIn("required", protocol.public_world("b_train"))
        self.assertEqual(protocol.authority_world("b_train")["required"], ["p", "q"])

    def test_prompt_does_not_name_the_candidate_operation(self) -> None:
        prompt = protocol.CHILD1_PROMPT.lower()
        for forbidden in ("marginal", "coverage", "overlap", "top-n", "stopping"):
            self.assertNotIn(forbidden, prompt)


if __name__ == "__main__":
    unittest.main()
