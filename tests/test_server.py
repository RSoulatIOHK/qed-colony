import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from colony.server import make_server
from colony.store import Store


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.assets = self.root / "dist"
        self.assets.mkdir()
        (self.assets / "index.html").write_text("<h1>Observatory</h1>", encoding="utf-8")
        (self.root / "secret.txt").write_text("must not be served", encoding="utf-8")
        (self.assets / "outside.txt").symlink_to(self.root / "secret.txt")
        self.store = Store(self.root / "state.db").initialize()
        self.store.seed([{"id": "a", "title": "Actual task", "role": "engineer"}])
        self.server = make_server(self.store, port=0, static_dir=self.assets)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.temp.cleanup()

    def request(self, path, method="GET"):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_live_snapshot_and_security_headers(self):
        status, headers, body = self.request("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        snapshot = json.loads(body)
        self.assertEqual(snapshot["mode"], "live")
        self.assertEqual(snapshot["tasks"][0]["title"], "Actual task")
        self.assertEqual(snapshot["benchmarks"], [])
        self.assertNotIn(str(self.root), body.decode())

    def test_static_assets_and_head(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Observatory", body)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        status, headers, body = self.request("/", "HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_parallel_reservations_are_visible_without_private_cycle_context(self):
        from colony.autonomy_store import AutonomyStore
        policy = {"max_daily_seconds": 28800, "max_daily_attempts": 144,
                  "max_concurrency": 4, "timezone": "Europe/Paris"}
        self.store.autonomy_policy = policy
        autonomy = AutonomyStore(self.store.path).initialize()
        cycle_ids = []
        for index in range(3):
            cycle = autonomy.create_cycle("parallel-%s" % index, "engineer")
            autonomy.update_cycle(cycle["id"], worktree=str(self.root / "private-cycle"))
            autonomy.reserve_attempt(cycle["id"], "author:0", 480, policy)
            cycle_ids.append(cycle["id"])
        status, _, body = self.request("/api/state")
        self.assertEqual(status, 200)
        budget = json.loads(body)["autonomy"]["budget"]
        self.assertEqual(budget["active_attempts"], 3)
        self.assertEqual(set(budget["active_cycle_ids"]), set(cycle_ids))
        self.assertEqual(budget["concurrency_limit"], 4)
        self.assertEqual(budget["reserved_seconds"], 1440)
        self.assertNotIn(str(self.root), body.decode())
        self.assertNotIn("worktree", body.decode())

    def test_path_traversal_symlinks_hidden_files_and_database_are_denied(self):
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/outside.txt", "/.colony/colony.db", "/state.db"):
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertIn(status, (403, 404))
                self.assertNotIn(b"must not be served", body)
        (self.assets / "copy.db").write_bytes(b"SQLite data")
        self.assertEqual(self.request("/copy.db")[0], 404)

    def test_http_is_read_only(self):
        before = self.store.snapshot()
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(self.request("/api/state", method)[0], 405)
        after = self.store.snapshot()
        self.assertEqual(before["tasks"], after["tasks"])
        self.assertEqual(before["events"], after["events"])


if __name__ == "__main__":
    unittest.main()
