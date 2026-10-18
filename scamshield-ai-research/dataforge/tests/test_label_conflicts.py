
"""Tests for DataForge label-conflict detection."""

import sys
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ValidationError
from dataforge.processing.label_conflicts import find_label_conflicts


def make_record(record_id, text, label):
    return {
        "record_id": record_id,
        "text": text,
        "label": label,
        "source_id": "test-source",
        "data_type": "REAL",
    }


class LabelConflictTests(unittest.TestCase):
    def test_detects_conflicting_labels(self):
        records = [
            make_record("r1", "Your account is locked", "ham"),
            make_record("r2", "Your   account is locked", "spam"),
        ]

        conflicts = find_label_conflicts(records)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["labels"], ["ham", "spam"])
        self.assertEqual(len(conflicts[0]["records"]), 2)

    def test_does_not_flag_same_label_duplicates(self):
        records = [
            make_record("r1", "Hello there", "ham"),
            make_record("r2", "Hello   there", "ham"),
        ]

        self.assertEqual(find_label_conflicts(records), [])

    def test_does_not_mutate_input(self):
        records = [make_record("r1", "Hello there", "ham")]
        original = [record.copy() for record in records]

        find_label_conflicts(records)

        self.assertEqual(records, original)

    def test_rejects_invalid_record(self):
        with self.assertRaises(ValidationError):
            find_label_conflicts([{"text": "missing required fields"}])

    def test_conflict_order_is_deterministic(self):
        records = [
            make_record("r1", "First", "ham"),
            make_record("r2", "Second", "ham"),
            make_record("r3", "First", "spam"),
            make_record("r4", "Second", "spam"),
        ]

        first = find_label_conflicts(records)
        second = find_label_conflicts(records)

        self.assertEqual(first, second)
        self.assertEqual(
            [item["normalized_text"] for item in first],
            ["First", "Second"],
        )


if __name__ == "__main__":
    unittest.main()
