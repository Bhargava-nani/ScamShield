"""Regression tests for DataForge's dataset repository."""

import json
import sys
import tempfile
import unittest
from pathlib import Path


RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import (
    DuplicateConflictError,
    StorageError,
    ValidationError,
)
from dataforge.storage.repository import DatasetRepository


def make_record(**overrides):
    """Build a valid dataset record for tests."""
    record = {
        "record_id": "record-001",
        "text": "Please review this message.",
        "label": "ham",
        "source_id": "test-source",
        "data_type": "REAL",
    }
    record.update(overrides)
    return record


class DatasetRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repository = DatasetRepository(self.root / "dataset.jsonl")

    def tearDown(self):
        self.temp.cleanup()

    def test_add_record_and_load_it(self):
        result = self.repository.add_records([make_record()])

        self.assertEqual(result["total_records"], 1)
        self.assertEqual(result["added_records"], 1)
        self.assertEqual(self.repository.load_records(), [make_record()])

    def test_reimporting_identical_record_is_idempotent(self):
        record = make_record()

        self.repository.add_records([record])
        original_bytes = self.repository.path.read_bytes()

        result = self.repository.add_records([record])

        self.assertEqual(result["total_records"], 1)
        self.assertEqual(result["added_records"], 0)
        self.assertEqual(self.repository.path.read_bytes(), original_bytes)

    def test_conflicting_existing_id_aborts_without_changing_file(self):
        self.repository.add_records([make_record()])
        original_bytes = self.repository.path.read_bytes()

        conflict = make_record(text="Different content")

        with self.assertRaises(DuplicateConflictError):
            self.repository.add_records([make_record(record_id="record-002"), conflict])

        self.assertEqual(self.repository.path.read_bytes(), original_bytes)
        self.assertEqual(len(self.repository.load_records()), 1)

    def test_invalid_later_record_does_not_commit_earlier_record(self):
        invalid = make_record(record_id="record-002", label=["spam"])

        with self.assertRaises(ValidationError):
            self.repository.add_records([make_record(), invalid])

        self.assertFalse(self.repository.path.exists())

    def test_rejects_unknown_fields(self):
        record = make_record(unexpected_field="not allowed")

        with self.assertRaises(ValidationError):
            self.repository.add_records([record])

        self.assertFalse(self.repository.path.exists())

    def test_rejects_overlong_record_id(self):
        with self.assertRaises(ValidationError):
            self.repository.add_records([make_record(record_id="x" * 129)])

    def test_rejects_overlong_source_id(self):
        with self.assertRaises(ValidationError):
            self.repository.add_records([make_record(source_id="x" * 129)])

    def test_rejects_overlong_language(self):
        with self.assertRaises(ValidationError):
            self.repository.add_records([make_record(language="e" * 33)])

    def test_rejects_malformed_sha256(self):
        with self.assertRaises(ValidationError):
            self.repository.add_records([make_record(content_sha256="not-a-hash")])

    def test_rejects_datetime_without_timezone(self):
        with self.assertRaises(ValidationError):
            self.repository.add_records(
                [make_record(collected_at="2026-10-12T12:00:00")]
            )

    def test_accepts_optional_fields_when_valid(self):
        record = make_record(
            language="en",
            collected_at="2026-10-12T12:00:00+00:00",
            content_sha256="a" * 64,
        )

        self.repository.add_records([record])

        self.assertEqual(self.repository.load_records(), [record])

    def test_load_rejects_malformed_json_line(self):
        self.repository.path.parent.mkdir(parents=True, exist_ok=True)
        self.repository.path.write_text("{invalid json}\n", encoding="utf-8")

        with self.assertRaises(StorageError):
            self.repository.load_records()

    def test_load_rejects_conflicting_duplicate_ids(self):
        first = make_record()
        second = make_record(text="Conflicting message")

        self.repository.path.parent.mkdir(parents=True, exist_ok=True)
        self.repository.path.write_text(
            json.dumps(first) + "\n" + json.dumps(second) + "\n",
            encoding="utf-8",
        )

        with self.assertRaises(DuplicateConflictError):
            self.repository.load_records()

    def test_load_collapses_identical_duplicate_ids(self):
        record = make_record()

        self.repository.path.parent.mkdir(parents=True, exist_ok=True)
        self.repository.path.write_text(
            json.dumps(record) + "\n" + json.dumps(record) + "\n",
            encoding="utf-8",
        )

        self.assertEqual(self.repository.load_records(), [record])

    def test_empty_batch_does_not_create_repository(self):
        result = self.repository.add_records([])

        self.assertEqual(result, {"total_records": 0, "added_records": 0})
        self.assertFalse(self.repository.path.exists())


if __name__ == "__main__":
    unittest.main()