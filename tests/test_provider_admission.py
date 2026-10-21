"""Provider state and model-call reservation share one admission boundary."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from colony.autonomy_store import AutonomyStore
from colony.network import NetworkUnavailable
from colony.pipeline import Pipeline
from colony.store import Store


class ProviderAdmissionTests(unittest.TestCase):
    def test_failure_cannot_interleave_provider_check_and_call_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = Store(root / "state.db").initialize()
            autonomy = AutonomyStore(tasks.path).initialize()
            tasks.seed([{"id": name, "title": "Scoped " + name, "role": "researcher"}
                        for name in ("ADMITTED", "OUTAGE")])
            admitted = autonomy.create_cycle("ADMITTED", "researcher")
            admitted = autonomy.update_cycle(admitted["id"], worktree=str(root))
            outage = autonomy.create_cycle("OUTAGE", "researcher")
            executor = Mock(return_value={"status": "completed", "summary": "Bounded result",
                                          "elapsed_seconds": 1})
            policy = {"max_daily_seconds": 100, "max_daily_attempts": 10, "max_concurrency": 2,
                      "network_backoff_base_seconds": 900, "network_backoff_max_seconds": 900}
            pipeline = Pipeline(root, tasks, autonomy, policy, executor=executor)
            reservation_entered = threading.Event()
            contender_probed = threading.Event()
            contender_acquired = []
            offline_at_reservation = []
            reserve = autonomy.reserve_attempt

            def controlled_reservation(*args, **kwargs):
                reservation_entered.set()
                if not contender_probed.wait(5):
                    raise AssertionError("Outage contender did not reach the admission boundary")
                offline_at_reservation.append(bool(autonomy.get_cycle(outage["id"]).get("provider_network_offline")))
                return reserve(*args, **kwargs)

            def record_outage():
                if not reservation_entered.wait(5):
                    raise AssertionError("Model call did not reach reservation")
                acquired = pipeline._provider_lock.acquire(blocking=False)
                contender_acquired.append(acquired)
                if acquired:
                    # This branch deterministically exposes the former gap:
                    # record the outage before allowing reservation to proceed.
                    try:
                        pipeline._provider_failed(outage)
                    finally:
                        pipeline._provider_lock.release()
                        contender_probed.set()
                else:
                    contender_probed.set()
                    pipeline._provider_failed(outage)

            with patch.object(autonomy, "reserve_attempt", side_effect=controlled_reservation):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    call = pool.submit(pipeline._job, admitted, "author:0", "Scoped work", 10, "read-only")
                    failure = pool.submit(record_outage)
                    self.assertEqual(call.result(timeout=10)["status"], "completed")
                    failure.result(timeout=10)

            self.assertEqual(contender_acquired, [False])
            self.assertEqual(offline_at_reservation, [False])
            self.assertTrue(autonomy.get_cycle(outage["id"])["provider_network_offline"])
            before = autonomy.list_attempts()
            self.assertEqual(len(before), 1)
            with patch("colony.pipeline.probe_model_connectivity") as probe:
                with self.assertRaises(NetworkUnavailable):
                    pipeline._job(admitted, "author:1", "Must wait", 10, "read-only")
                probe.assert_not_called()
            self.assertEqual(autonomy.list_attempts(), before)
            self.assertEqual(executor.call_count, 1)


if __name__ == "__main__":
    unittest.main()
