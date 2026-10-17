import sys
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH_DIR))

import app as scamshield_app


class AnalysisRateLimitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = scamshield_app.app.test_client()
        self.test_ip = "198.51.100.77"

    def test_analysis_endpoint_blocks_request_21(self):
        for request_number in range(20):
            response = self.client.post(
                "/api/analyse",
                json={},
                environ_base={"REMOTE_ADDR": self.test_ip},
            )
            self.assertNotEqual(
                response.status_code,
                429,
                f"Request {request_number + 1} was unexpectedly rate-limited.",
            )

        response = self.client.post(
            "/api/analyse",
            json={},
            environ_base={"REMOTE_ADDR": self.test_ip},
        )

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)


if __name__ == "__main__":
    unittest.main()
