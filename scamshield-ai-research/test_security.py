
import json
import unittest

from app import app


class ScamShieldSecurityTests(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["model_loaded"])

    def test_security_headers(self):
        response = self.client.get("/api/health")

        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
            "Permissions-Policy",
            "Content-Security-Policy",
            "Cache-Control",
        ]

        for header in expected_headers:
            with self.subTest(header=header):
                self.assertIn(header, response.headers)

        self.assertEqual(
            response.headers["X-Frame-Options"], "DENY"
        )
        self.assertEqual(
            response.headers["X-Content-Type-Options"], "nosniff"
        )
        self.assertEqual(
            response.headers["Cache-Control"], "no-store"
        )

    
    def test_frontend_files_load(self):
        for path in ["/", "/style.css", "/script.js"]:
            with self.subTest(path=path):
                response = self.client.get(path)
            try:
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.get_data())
            finally:
                response.close()


    def test_non_json_request_rejected(self):
        response = self.client.post(
            "/api/analyse",
            data="message=hello",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)

    def test_malformed_json_rejected(self):
        response = self.client.post(
            "/api/analyse",
            data="{invalid json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_json_array_rejected(self):
        response = self.client.post(
            "/api/analyse",
            data=json.dumps(["hello"]),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_missing_message_rejected(self):
        response = self.client.post(
            "/api/analyse",
            json={},
        )

        self.assertEqual(response.status_code, 400)

    def test_non_string_message_rejected(self):
        response = self.client.post(
            "/api/analyse",
            json={"message": 12345},
        )

        self.assertEqual(response.status_code, 400)

    def test_empty_message_rejected(self):
        response = self.client.post(
            "/api/analyse",
            json={"message": "   "},
        )

        self.assertEqual(response.status_code, 400)

    def test_5001_character_message_rejected(self):
        response = self.client.post(
            "/api/analyse",
            json={"message": "a" * 5001},
        )

        self.assertEqual(response.status_code, 413)

    def test_oversized_request_body_rejected(self):
        response = self.client.post(
            "/api/analyse",
            data="x" * (17 * 1024),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 413)

    def test_valid_message_returns_expected_fields(self):
        response = self.client.post(
            "/api/analyse",
            json={"message": "Hello, are we meeting today?"},
        )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertIn(data["prediction"], ["spam", "ham"])
        self.assertIsInstance(data["model_confidence"], float)
        self.assertGreaterEqual(data["model_confidence"], 0.0)
        self.assertLessEqual(data["model_confidence"], 1.0)
        self.assertIn("advice", data)
        self.assertIn("confidence_note", data)

    def test_error_responses_have_security_headers(self):
        response = self.client.post(
            "/api/analyse",
            data="not json",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn(
            "Content-Security-Policy", response.headers
        )
        self.assertEqual(
            response.headers["Cache-Control"], "no-store"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
