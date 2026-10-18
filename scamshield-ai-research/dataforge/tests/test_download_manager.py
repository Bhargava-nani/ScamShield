"""Security and behavior tests for DataForge's bounded download manager."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.collection import download_manager as dm
from dataforge.exceptions import SecurityViolationError, ValidationError


class FakeResponse:
    def __init__(self, body=b"safe test data", status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = {
            "Content-Length": str(len(body)),
            "Content-Type": "text/plain",
        }
        if headers:
            self.headers.update(headers)
        self.offset = 0

    def getheader(self, name):
        return self.headers.get(name)

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self.body) - self.offset
        result = self.body[self.offset:self.offset + size]
        self.offset += len(result)
        return result


class FakeConnection:
    response = FakeResponse()
    last_request = None
    closed = False

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        type(self).closed = False

    def request(self, method, target, headers):
        type(self).last_request = (method, target, headers)

    def getresponse(self):
        return type(self).response

    def close(self):
        type(self).closed = True


class DownloadManagerTests(unittest.TestCase):
    def setUp(self):
        self.approved_domains = {"datasets.example.org"}
        self.source = {
            "source_id": "test-source",
            "source_url": "https://datasets.example.org/data.csv",
            "permission_confirmed": True,
            "license_status": "approved",
        }
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.connection_patch = patch.object(
            dm, "_PinnedHTTPSConnection", FakeConnection
        )
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.dns_patch = patch.object(
            dm, "_resolve_public_addresses", return_value=["93.184.216.34"]
        )
        self.dns_patch.start()
        self.addCleanup(self.dns_patch.stop)
        FakeConnection.response = FakeResponse()
        FakeConnection.last_request = None

    def download(self, **kwargs):
        return dm.download_source(
            self.source,
            self.approved_domains,
            storage_dir=self.temp_dir.name,
            **kwargs,
        )

    def test_download_saves_bytes_and_returns_hash_metadata(self):
        result = self.download()

        self.assertEqual(result["source_id"], "test-source")
        self.assertEqual(result["size_bytes"], len(b"safe test data"))
        self.assertEqual(len(result["sha256"]), 64)
        self.assertEqual(result["approval_status"], "VALIDATED")
        self.assertTrue(Path(result["artifact_path"]).is_file())
        self.assertEqual(
            Path(result["artifact_path"]).read_bytes(),
            b"safe test data",
        )

    def test_uses_https_get_and_does_not_forward_credentials(self):
        self.download()

        method, target, headers = FakeConnection.last_request
        self.assertEqual(method, "GET")
        self.assertEqual(target, "/data.csv")
        self.assertEqual(headers["Accept-Encoding"], "identity")
        self.assertNotIn("Authorization", headers)

    def test_rejects_redirect(self):
        FakeConnection.response = FakeResponse(
            b"",
            status=302,
            headers={"Location": "https://datasets.example.org/other.csv"},
        )

        with self.assertRaises(SecurityViolationError):
            self.download()

    def test_rejects_non_success_status(self):
        FakeConnection.response = FakeResponse(b"not found", status=404)

        with self.assertRaises(dm.DownloadError):
            self.download()

    def test_rejects_declared_oversize_before_reading_body(self):
        FakeConnection.response = FakeResponse(
            b"x",
            headers={"Content-Length": "1000"},
        )

        with self.assertRaises(dm.DownloadError):
            self.download(max_bytes=10)

    def test_rejects_streamed_oversize_body(self):
        FakeConnection.response = FakeResponse(b"x" * 100)

        with self.assertRaises(dm.DownloadError):
            self.download(max_bytes=10)

    def test_rejects_invalid_limits(self):
        with self.assertRaises(ValidationError):
            self.download(max_bytes=0)
        with self.assertRaises(ValidationError):
            self.download(timeout_seconds=0)
        with self.assertRaises(ValidationError):
            self.download(timeout_seconds=121)

    def test_rejects_non_public_dns_result(self):
        with patch.object(
            dm,
            "_resolve_public_addresses",
            side_effect=SecurityViolationError("non-public destination"),
        ):
            with self.assertRaises(SecurityViolationError):
                self.download()

    def test_rejects_empty_response(self):
        FakeConnection.response = FakeResponse(b"")

        with self.assertRaises(dm.DownloadError):
            self.download()

    def test_connection_is_closed_after_redirect_rejection(self):
        FakeConnection.response = FakeResponse(b"", status=301)

        with self.assertRaises(SecurityViolationError):
            self.download()

        self.assertTrue(FakeConnection.closed)


if __name__ == "__main__":
    unittest.main()
