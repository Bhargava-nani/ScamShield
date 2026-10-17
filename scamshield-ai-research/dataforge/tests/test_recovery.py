"""Tests for conservative DataForge recovery inspection."""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ValidationError
from dataforge.pipeline.recovery import inspect_interrupted_writes


class RecoveryInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def make_temp_file(self, relative_path, content=b"unfinished"):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        old_timestamp = self.now.timestamp() - 600
        os.utime(path, (old_timestamp, old_timestamp))
        return path

    def test_reports_old_known_temporary_file(self):
        path = self.make_temp_file("processed/.dataset-test.tmp")

        result = inspect_interrupted_writes(
            self.root, older_than_seconds=300, now=self.now
        )

        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(
            result["candidates"][0]["path"], "processed/.dataset-test.tmp"
        )
        self.assertEqual(result["candidates"][0]["size_bytes"], len(b"unfinished"))
        self.assertFalse(result["automatic_cleanup"])
        self.assertTrue(path.exists())

    def test_ignores_recent_temporary_file(self):
        path = self.root / ".dataforge-recent.tmp"
        path.write_bytes(b"still writing")
        os.utime(path, (self.now.timestamp(), self.now.timestamp()))

        result = inspect_interrupted_writes(
            self.root, older_than_seconds=300, now=self.now
        )

        self.assertEqual(result["candidate_count"], 0)
        self.assertTrue(path.exists())

    def test_ignores_unrelated_files(self):
        unrelated = self.root / "important.txt"
        unrelated.write_text("keep", encoding="utf-8")
        self.make_temp_file("other.tmp")

        result = inspect_interrupted_writes(
            self.root, older_than_seconds=300, now=self.now
        )

        self.assertEqual(result["candidate_count"], 0)
        self.assertTrue(unrelated.exists())

    def test_scans_nested_directories(self):
        self.make_temp_file("a/b/.dataforge-orphan.tmp")

        result = inspect_interrupted_writes(
            self.root, older_than_seconds=300, now=self.now
        )

        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(
            result["candidates"][0]["path"], "a/b/.dataforge-orphan.tmp"
        )

    def test_does_not_modify_candidate_content(self):
        path = self.make_temp_file(".dataset-orphan.tmp")
        original = path.read_bytes()

        inspect_interrupted_writes(
            self.root, older_than_seconds=300, now=self.now
        )

        self.assertEqual(path.read_bytes(), original)

    def test_rejects_invalid_age_threshold(self):
        for threshold in (-1, True, "300"):
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValidationError):
                    inspect_interrupted_writes(
                        self.root, older_than_seconds=threshold, now=self.now
                    )

    def test_rejects_naive_clock(self):
        with self.assertRaises(ValidationError):
            inspect_interrupted_writes(
                self.root,
                now=datetime(2026, 10, 17, 12, 0),
            )

    def test_rejects_missing_root(self):
        with self.assertRaises(ValidationError):
            inspect_interrupted_writes(
                self.root / "missing", now=self.now
            )


if __name__ == "__main__":
    unittest.main()
