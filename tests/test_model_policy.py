import unittest

from colony.model_policy import choose_model


class ModelPolicyTests(unittest.TestCase):
    def test_routine_work_starts_with_luna(self):
        selection = choose_model({}, "engineer", "author")
        self.assertEqual(selection["model"], "gpt-6-luna")
        self.assertEqual(selection["reasoning_effort"], "medium")
        self.assertIn("Small model first", selection["reason"])

    def test_failed_revisions_escalate_to_a_bounded_stronger_tier(self):
        selected = [choose_model({}, "engineer", "author", revision=number)["model"]
                    for number in (0, 1, 2, 100)]
        self.assertEqual(selected, ["gpt-6-luna", "gpt-6-sol", "gpt-6.1-sol", "gpt-6.1-sol"])
        self.assertIn("failed attempt", choose_model({}, "engineer", "author", revision=1)["reason"])

    def test_trust_critical_review_uses_stronger_independent_model(self):
        review = choose_model({}, "reviewer", "review", trust_critical=True)
        self.assertEqual(review["model"], "gpt-6-sol")
        self.assertEqual(review["reasoning_effort"], "high")
        self.assertIn("independent review", review["reason"])
        self.assertEqual(choose_model({}, "reviewer", "review", revision=2, trust_critical=True)["model"], "gpt-6.1-sol")

    def test_owner_can_bound_routing_to_one_model(self):
        policy = {"model_tiers": [{"model": "configured-small-model", "reasoning_effort": "low"}]}
        selected = choose_model(policy, "reviewer", "review", revision=100, trust_critical=True)
        self.assertEqual(selected["model"], "configured-small-model")

    def test_unsupported_reasoning_and_invalid_revision_are_rejected(self):
        for effort in ("ultra", "max", "none", None):
            with self.assertRaises(ValueError):
                choose_model({"model_tiers": [{"model": "gpt-6-luna", "reasoning_effort": effort}]}, "engineer", "author")
        for revision in (-1, True, 1.5, "1"):
            with self.assertRaises(ValueError):
                choose_model({}, "engineer", "author", revision=revision)
        for tiers in ([], [{"model": "", "reasoning_effort": "high"}], [{"model": "x", "reasoning_effort": "high"}] * 4):
            with self.assertRaises(ValueError):
                choose_model({"model_tiers": tiers}, "engineer", "author")


if __name__ == "__main__":
    unittest.main()
