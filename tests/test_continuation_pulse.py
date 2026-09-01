import copy
import hashlib
import json
import unittest

from open_trajectory_harness.continuation_pulse import InvocationCallbacks, continue_once, pulse_eligible


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def seal(value):
    value = copy.deepcopy(value)
    value.pop("artifact_digest", None)
    value["artifact_digest"] = digest(value)
    return value


def subject():
    return seal({
        "continuation": {"status": "open"},
        "continuation_liveness": {"status": "live", "contact_identity": "contact-a"},
        "pending_contact_bearing_continuations": [{"contact_identity": "contact-a", "consequence_status": "unreceipted", "package": {"target_symbol": "a"}}],
        "fixed_g6_recurrence_driver": {"phase": "observer-stop", "encounters": 1, "observation_limit": 1, "accepted_actors": 1, "actor_limit": 1, "invocations": 1},
    })


def callbacks(world_outcome="success", accepted=True):
    def dispatch(value): return value["fixed_g6_recurrence_driver"]["phase"]
    def contact(value): return {"outcome": world_outcome, "target_symbol": "a", "receipt_digest": "world"}
    def compile_world(value, world):
        value = copy.deepcopy(value); value.pop("artifact_digest", None); state = value["fixed_g6_recurrence_driver"]; state["encounters"] += 1; state["phase"] = "assimilate" if world["outcome"] == "success" else "correct"; return seal(value)
    def resolve(value): return {"target_symbol": "a", "receipt_digest": "world"}
    def assimilate(value, resolved): return {"accepted": accepted, "decision": {"next_contact": {"target_symbol": "b"}}, "binding": {"projected_contact_identity": "contact-b"}}
    def compile_pending(value, action):
        value = copy.deepcopy(value); value.pop("artifact_digest", None); value["pending_contact_bearing_continuations"].append({"contact_identity": "contact-b", "consequence_status": "unreceipted", "package": action["decision"]["next_contact"]}); value["continuation_liveness"] = {"status": "live", "contact_identity": "contact-b"}; value["fixed_g6_recurrence_driver"]["accepted_actors"] += 1; value["fixed_g6_recurrence_driver"]["phase"] = "contact"; return seal(value)
    def stop(value): value = copy.deepcopy(value); value.pop("artifact_digest", None); value["fixed_g6_recurrence_driver"]["phase"] = "observer-stop"; return seal(value)
    return InvocationCallbacks(dispatch, contact, compile_world, resolve, assimilate, compile_pending, stop)


class ContinuationPulseTests(unittest.TestCase):
    def test_success_is_reusable_on_its_own_output(self):
        first, one = continue_once(subject(), digest=digest, seal=seal, authority="pulse", callbacks=callbacks())
        self.assertEqual(one["status"], "completed")
        self.assertTrue(pulse_eligible(first))
        second, two = continue_once(first, digest=digest, seal=seal, authority="pulse", callbacks=callbacks())
        self.assertEqual(two["status"], "completed")
        self.assertTrue(pulse_eligible(second))
        self.assertEqual(second["fixed_g6_recurrence_driver"]["encounters"], 3)

    def test_unresolved_without_correction_preserves_typed_stop(self):
        result, trace = continue_once(subject(), digest=digest, seal=seal, authority="pulse", callbacks=callbacks("unresolved"))
        self.assertEqual(trace["status"], "needs-correction")
        self.assertEqual(result["fixed_g6_recurrence_driver"]["phase"], "correct")

    def test_rejected_assimilation_preserves_post_world_subject(self):
        result, trace = continue_once(subject(), digest=digest, seal=seal, authority="pulse", callbacks=callbacks(accepted=False))
        self.assertEqual(trace["status"], "assimilation-rejected")
        self.assertEqual(result["fixed_g6_recurrence_driver"]["phase"], "assimilate")

    def test_ineligible_subject_rejects(self):
        value = subject(); value["continuation"]["status"] = "closed"
        with self.assertRaises(ValueError):
            continue_once(value, digest=digest, seal=seal, authority="pulse", callbacks=callbacks())


if __name__ == "__main__":
    unittest.main()
