
"""Tests for DataForge record validation."""

import sys
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ValidationError
from dataforge.processing.validator import validate_record, validate_records


def make_record(**overrides):
    record = {
        "record_id": "record-001",
        "text": "Please review this message.",
        "label": "ham",
        "source_id": "test-source",
        "data_type": "REAL",
    }
    record.update(overrides)
    return record


class ValidateRecordTests(unittest.TestCase):
    def test_accepts_valid_record(self):
        record = make_record()
        self.assertEqual(validate_record(record), record)

    def test_does_not_modify_input(self):
        record = make_record(text="  Original   message  ")
        original = record.copy()

        validate_record(record)

        self.assertEqual(record, original)

    def test_rejects_non_dictionary(self):
        with self.assertRaises(ValidationError):
            validate_record("not a record")

    def test_rejects_missing_required_field(self):
        record = make_record()
        del record["source_id"]

        with self.assertRaises(ValidationError):
            validate_record(record)

    def test_rejects_unknown_field(self):
        with self.assertRaises(ValidationError):
            validate_record(make_record(extra="not allowed"))

    def test_rejects_invalid_label(self):
        with self.assertRaises(ValidationError):
            validate_record(make_record(label="unknown"))

    def test_rejects_invalid_data_type(self):
        with self.assertRaises(ValidationError):
            validate_record(make_record(data_type="UNKNOWN"))

    def test_rejects_whitespace_only_text(self):
        with self.assertRaises(ValidationError):
            validate_record(make_record(text="   \t "))

    def test_rejects_text_over_limit(self):
        with self.assertRaises(ValidationError):
            validate_record(make_record(text="x" * 5001))

    def test_accepts_valid_optional_fields(self):
        record = make_record(
            language="en",
            collected_at="2026-10-12T12:00:00Z",
            content_sha256="a" * 64,
        )
        self.assertEqual(validate_record(record), record)

    def test_rejects_datetime_without_timezone(self):
        with self.assertRaises(ValidationError):
            validate_record(
                make_record(collected_at="2026-10-12T12:00:00")
            )

    def test_rejects_invalid_hash(self):
        with self.assertRaises(ValidationError):
            validate_record(make_record(content_sha256="invalid"))

    def test_batch_reports_invalid_record_position(self):
        result = validate_records([
            make_record(),
            make_record(record_id="bad", label="unknown"),
            make_record(record_id="record-003"),
        ])

        self.assertEqual(result["input_count"], 3)
        self.assertEqual(result["valid_count"], 2)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(result["rejected_records"][0]["index"], 1)

    def test_batch_rejects_non_list_input(self):
        with self.assertRaises(ValidationError):
            validate_records("not a batch")


if __name__ == "__main__":
    unittest.main()
