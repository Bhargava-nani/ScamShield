"""Tests for deterministic DataForge text normalization."""

import sys
import unittest
from pathlib import Path

# Add the directory containing the dataforge package to Python's import path.
DATAFORGE_PARENT = Path(__file__).resolve().parents[2]
if str(DATAFORGE_PARENT) not in sys.path:
    sys.path.insert(0, str(DATAFORGE_PARENT))

from dataforge.exceptions import ValidationError
from dataforge.processing.normalizer import normalize_record, normalize_text


class NormalizeTextTests(unittest.TestCase):
    def test_collapses_repeated_whitespace(self):
        self.assertEqual(normalize_text("hello   world"), "hello world")

    def test_normalizes_tabs_and_newlines(self):
        self.assertEqual(
            normalize_text("hello\tworld\r\nagain"),
            "hello world again",
        )

    def test_replaces_nonbreaking_spaces(self):
        self.assertEqual(normalize_text("hello\u00a0world"), "hello world")

    def test_normalizes_unicode_to_nfc(self):
        self.assertEqual(normalize_text("cafe\u0301"), "café")

    def test_preserves_case_and_punctuation(self):
        self.assertEqual(
            normalize_text("FREE!!! Call NOW."),
            "FREE!!! Call NOW.",
        )

    def test_is_idempotent(self):
        text = "  Hello\tworld!\r\nAgain  "
        normalized = normalize_text(text)
        self.assertEqual(normalize_text(normalized), normalized)

    def test_rejects_non_string(self):
        with self.assertRaises(ValidationError):
            normalize_text(123)

    def test_rejects_empty_string(self):
        with self.assertRaises(ValidationError):
            normalize_text("")

    def test_rejects_whitespace_only(self):
        with self.assertRaises(ValidationError):
            normalize_text(" \t\r\n ")

    def test_rejects_text_over_limit(self):
        with self.assertRaises(ValidationError):
            normalize_text("a" * 100_001)


class NormalizeRecordTests(unittest.TestCase):
    def test_normalizes_text_and_preserves_other_fields(self):
        record = {
            "record_id": "r1",
            "text": "  Hello   world! ",
            "label": "ham",
            "source_id": "source1",
        }

        result = normalize_record(record)

        self.assertEqual(result["text"], "Hello world!")
        self.assertEqual(result["label"], "ham")
        self.assertEqual(result["record_id"], "r1")
        self.assertEqual(result["source_id"], "source1")

    def test_does_not_modify_original_record(self):
        record = {"text": "  hello   world ", "label": "ham"}
        original = record.copy()

        normalize_record(record)

        self.assertEqual(record, original)

    def test_rejects_non_dictionary_record(self):
        with self.assertRaises(ValidationError):
            normalize_record("not a record")

    def test_rejects_missing_text_field(self):
        with self.assertRaises(ValidationError):
            normalize_record({"label": "ham"})

    def test_rejects_invalid_text_field(self):
        with self.assertRaises(ValidationError):
            normalize_record({"text": None})


if __name__ == "__main__":
    unittest.main()
