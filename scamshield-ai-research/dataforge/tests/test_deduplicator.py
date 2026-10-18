
"""Tests for deterministic and auditable dataset deduplication."""

import sys
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.processing.deduplicator import deduplicate_records


def make_record(record_id, text, label="ham"):
    return {
        "record_id": record_id,
        "text": text,
        "label": label,
        "source_id": "test-source",
        "data_type": "REAL",
    }


class DeduplicatorTests(unittest.TestCase):
    def test_removes_same_text_same_label_duplicate(self):
        result = deduplicate_records([
            make_record("r1", "Hello there"),
            make_record("r2", "Hello   there"),
        ])

        self.assertEqual(result["retained_count"], 1)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["records"][0]["record_id"], "r1")
        self.assertEqual(result["duplicates"][0]["duplicate_of"], "r1")

    def test_preserves_all_records_with_conflicting_labels(self):
        result = deduplicate_records([
            make_record("r1", "Suspicious link", "ham"),
            make_record("r2", "Suspicious   link", "spam"),
        ])

        self.assertEqual(result["retained_count"], 2)
        self.assertEqual(result["duplicate_count"], 0)
        self.assertEqual(result["conflict_count"], 1)

    def test_reports_invalid_records(self):
        result = deduplicate_records([
            make_record("r1", "Valid message"),
            {"record_id": "invalid"},
        ])

        self.assertEqual(result["valid_count"], 1)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["index"], 1)

    def test_preserves_input_order(self):
        result = deduplicate_records([
            make_record("r1", "First"),
            make_record("r2", "Second"),
            make_record("r3", "Third"),
        ])

        self.assertEqual(
            [record["record_id"] for record in result["records"]],
            ["r1", "r2", "r3"],
        )

    def test_does_not_modify_input(self):
        records = [
            make_record("r1", "  Hello   there  "),
            make_record("r2", "Hello there"),
        ]
        original = [record.copy() for record in records]

        deduplicate_records(records)

        self.assertEqual(records, original)

    def test_empty_batch(self):
        result = deduplicate_records([])

        self.assertEqual(result["input_count"], 0)
        self.assertEqual(result["retained_count"], 0)
        self.assertEqual(result["duplicate_count"], 0)
        self.assertEqual(result["conflict_count"], 0)

    def test_results_are_deterministic(self):
        records = [
            make_record("r1", "Repeated message"),
            make_record("r2", "Repeated   message"),
        ]

        self.assertEqual(
            deduplicate_records(records),
            deduplicate_records(records),
        )

    def test_preserves_three_record_label_conflict(self):
        result = deduplicate_records([
            make_record("r1", "Check this message", "ham"),
            make_record("r2", "Check this message", "spam"),
            make_record("r3", "Check this message", "spam"),
        ])

        self.assertEqual(result["retained_count"], 3)
        self.assertEqual(result["duplicate_count"], 0)
        self.assertEqual(result["conflict_count"], 1)


if __name__ == "__main__":
    unittest.main()
