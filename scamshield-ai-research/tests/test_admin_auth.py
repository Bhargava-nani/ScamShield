import os
import sys
import unittest
from pathlib import Path

from flask import Flask, jsonify

RESEARCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH_DIR))

from admin_auth import admin_required, admin_token_is_valid  # noqa: E402


class AdminAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.previous_token = os.environ.get("SCAMSHIELD_ADMIN_TOKEN")
        os.environ["SCAMSHIELD_ADMIN_TOKEN"] = "T" * 48

        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

        @self.app.get("/admin/test")
        @admin_required
        def protected_route():
            return jsonify({"ok": True})

        self.client = self.app.test_client()

    def tearDown(self):
        if self.previous_token is None:
            os.environ.pop("SCAMSHIELD_ADMIN_TOKEN", None)
        else:
            os.environ["SCAMSHIELD_ADMIN_TOKEN"] = self.previous_token

    def test_valid_token_is_accepted(self):
        response = self.client.get(
            "/admin/test",
            headers={"Authorization": "Bearer " + ("T" * 48)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_missing_token_is_rejected(self):
        response = self.client.get("/admin/test")
        self.assertEqual(response.status_code, 401)

    def test_wrong_token_is_rejected(self):
        response = self.client.get(
            "/admin/test",
            headers={"Authorization": "Bearer " + ("X" * 48)},
        )
        self.assertEqual(response.status_code, 401)

    def test_non_bearer_authentication_is_rejected(self):
        response = self.client.get(
            "/admin/test",
            headers={"Authorization": "Basic abc"},
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_server_token_fails_closed(self):
        os.environ.pop("SCAMSHIELD_ADMIN_TOKEN", None)
        response = self.client.get(
            "/admin/test",
            headers={"Authorization": "Bearer " + ("T" * 48)},
        )
        self.assertEqual(response.status_code, 503)

    def test_short_server_token_fails_closed(self):
        os.environ["SCAMSHIELD_ADMIN_TOKEN"] = "short"
        response = self.client.get(
            "/admin/test",
            headers={"Authorization": "Bearer short"},
        )
        self.assertEqual(response.status_code, 503)

    def test_token_helper_rejects_wrong_values(self):
        self.assertTrue(admin_token_is_valid("T" * 48))
        self.assertFalse(admin_token_is_valid("wrong"))
        self.assertFalse(admin_token_is_valid(""))
        self.assertFalse(admin_token_is_valid(None))


if __name__ == "__main__":
    unittest.main()
