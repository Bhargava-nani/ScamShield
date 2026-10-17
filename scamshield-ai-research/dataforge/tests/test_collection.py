"""Regression tests for collection orchestration and bounded retries."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.collection import collector, retry_manager
from dataforge.collection.download_manager import DownloadError
from dataforge.exceptions import SecurityViolationError, ValidationError


class RetryManagerTests(unittest.TestCase):
    def test_returns_first_success(self):
        operation = Mock(return_value={"ok": True})
        result = retry_manager.retry_call(
            operation,
            max_retries=2,
            retry_exceptions=(DownloadError,),
            sleep=lambda _: None,
        )
        self.assertEqual(result, {"ok": True})
        operation.assert_called_once()

    def test_retries_then_succeeds(self):
        operation = Mock(
            side_effect=[
                DownloadError("HTTPS download failed."),
                {"ok": True},
            ]
        )
        result = retry_manager.retry_call(
            operation,
            max_retries=2,
            retry_exceptions=(DownloadError,),
            retry_if=lambda exc: str(exc) == "HTTPS download failed.",
            sleep=lambda _: None,
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(operation.call_count, 2)

    def test_stops_after_retry_limit(self):
        operation = Mock(side_effect=DownloadError("HTTPS download failed."))
        with self.assertRaises(DownloadError):
            retry_manager.retry_call(
                operation,
                max_retries=2,
                retry_exceptions=(DownloadError,),
                retry_if=lambda exc: True,
                sleep=lambda _: None,
            )
        self.assertEqual(operation.call_count, 3)

    def test_does_not_retry_unapproved_failure(self):
        operation = Mock(side_effect=SecurityViolationError("blocked"))
        with self.assertRaises(SecurityViolationError):
            retry_manager.retry_call(
                operation,
                max_retries=2,
                retry_exceptions=(DownloadError,),
                sleep=lambda _: None,
            )
        operation.assert_called_once()

    def test_rejects_retry_count_above_configured_limit(self):
        with self.assertRaises(ValidationError):
            retry_manager.retry_call(lambda: None, max_retries=100)


class CollectorTests(unittest.TestCase):
    def test_returns_download_metadata(self):
        expected = {
            "source_id": "test-source",
            "sha256": "a" * 64,
            "size_bytes": 12,
            "artifact_path": "example.bin",
        }
        with patch.object(collector, "download_source", return_value=expected):
            result = collector.collect_source(
                {"source_id": "test-source"},
                {"example.org"},
                max_retries=0,
            )
        self.assertEqual(result, expected)

    def test_retries_transient_network_failure(self):
        expected = {"source_id": "test-source", "sha256": "b" * 64}
        with patch.object(
            collector,
            "download_source",
            side_effect=[
                DownloadError("HTTPS download failed."),
                expected,
            ],
        ) as mocked:
            result = collector.collect_source(
                {"source_id": "test-source"},
                {"example.org"},
                max_retries=1,
            )
        self.assertEqual(result, expected)
        self.assertEqual(mocked.call_count, 2)

    def test_does_not_retry_security_failure(self):
        with patch.object(
            collector,
            "download_source",
            side_effect=SecurityViolationError("blocked"),
        ) as mocked:
            with self.assertRaises(SecurityViolationError):
                collector.collect_source(
                    {"source_id": "test-source"},
                    {"example.org"},
                    max_retries=2,
                )
        mocked.assert_called_once()

    def test_does_not_retry_non_transient_download_error(self):
        with patch.object(
            collector,
            "download_source",
            side_effect=DownloadError("Source returned HTTP status 404; expected 200."),
        ) as mocked:
            with self.assertRaises(DownloadError):
                collector.collect_source(
                    {"source_id": "test-source"},
                    {"example.org"},
                    max_retries=2,
                )
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
