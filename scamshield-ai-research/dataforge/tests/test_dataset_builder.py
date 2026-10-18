
"""Tests for the in-memory DataForge dataset builder."""

import sys
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ValidationError
from dataforge.datasets.dataset_builder import build_dataset


def make_record(record_id, text, label="ham"):
    return {
        "record_id": record_id,
        "text": text,
        "label": label,
        "source_id": "test-source",
        "data_type": "REAL",
    }


class DatasetBuilderTests(unittest.TestCase):
    def test_builds_clean_dataset(self):
        result = build_dataset([
            make_record("r1", "First message"),
            make_record("r2", "Second message", "spam"),
        ])

        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(len(result["records"]), 2)
        self.assertFalse(result["quality_report"]["requires_review"])

    def test_flags_conflicting_labels_for_review(self):
        result = build_dataset([
            make_record("r1", "Conflicting message", "ham"),
            make_record("r2", "Conflicting message", "spam"),
        ])

        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(len(result["conflicts"]), 1)

    def test_flags_rejected_records_for_review(self):
        result = build_dataset([
            make_record("r1", "Valid message"),
            {"record_id": "invalid"},
        ])

        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(len(result["rejected"]), 1)

    def test_deduplicates_safe_repeats(self):
        result = build_dataset([
            make_record("r1", "Repeated message"),
            make_record("r2", "Repeated   message"),
        ])

        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["quality_report"]["duplicate_count"], 1)

    def test_rejects_non_batch_input(self):
        with self.assertRaises(ValidationError):
            build_dataset("not a dataset")

    def test_does_not_modify_input_records(self):
        records = [make_record("r1", "  Original   text ")]
        original = [record.copy() for record in records]

        build_dataset(records)

        self.assertEqual(records, original)

    def test_empty_dataset_is_validated(self):
        result = build_dataset([])

        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["quality_report"]["input_count"], 0)


if __name__ == "__main__":
    unittest.main()
