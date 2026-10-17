import sys
import unittest
from pathlib import Path

from flask import Flask, jsonify

RESEARCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH_DIR))

from rate_limit import rate_limit  # noqa: E402


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

        @self.app.get("/limited")
        @rate_limit(limit=2, window_seconds=60)
        def limited():
            return jsonify({"ok": True})

        self.client = self.app.test_client()

    def test_requests_within_limit_are_allowed(self):
        self.assertEqual(self.client.get("/limited").status_code, 200)
        self.assertEqual(self.client.get("/limited").status_code, 200)

    def test_excess_request_is_rejected(self):
        self.client.get("/limited")
        self.client.get("/limited")
        response = self.client.get("/limited")

        self.assertEqual(response.status_code, 429)
        self.assertTrue(int(response.headers["Retry-After"]) >= 1)

    def test_separate_client_ip_has_separate_limit(self):
        self.client.get("/limited", environ_base={"REMOTE_ADDR": "192.0.2.1"})
        self.client.get("/limited", environ_base={"REMOTE_ADDR": "192.0.2.1"})

        response = self.client.get(
            "/limited",
            environ_base={"REMOTE_ADDR": "192.0.2.2"},
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            rate_limit(limit=0)

        with self.assertRaises(ValueError):
            rate_limit(limit=True)

        with self.assertRaises(ValueError):
            rate_limit(window_seconds=0)


if __name__ == "__main__":
    unittest.main()
