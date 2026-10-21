import unittest

from colony.network_recovery import due, retry_delay, schedule_retry


class NetworkRecoveryTests(unittest.TestCase):
    def test_bounded_exponential_backoff(self):
        self.assertEqual([retry_delay(i, 4, 10) for i in range(1, 6)], [4, 8, 10, 10, 10])

    def test_schedule_persists_resume_phase_and_retry_time(self):
        cycle = {"id": "c", "phase": "publishing", "network_retry_count": 1}
        updated = schedule_retry(cycle, lambda c, phase, **data: dict(c, phase=phase, **data), now=100,
                                 base_seconds=5, max_seconds=60)
        self.assertEqual(updated["phase"], "waiting_network")
        self.assertEqual(updated["resume_phase"], "publishing")
        self.assertEqual(updated["next_retry_at"], 110)
        self.assertFalse(due(updated, 109))
        self.assertTrue(due(updated, 110))


if __name__ == "__main__":
    unittest.main()
