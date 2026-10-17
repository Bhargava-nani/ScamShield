
"""Tests for DataForge dataset leakage checks."""

import sys
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ValidationError
from dataforge.datasets.leakage_checks import check_split_leakage


def record(record_id, text, label="ham"):
    return {
        "record_id": record_id,
        "text": text,
        "label": label,
        "source_id": f"source-{record_id}",
        "data_type": "REAL",
    }


class LeakageCheckTests(unittest.TestCase):
    def test_clean_splits_pass(self):
        result = check_split_leakage({
            "train": [record("1", "hello there")],
            "test": [record("2", "different message")],
        })
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["requires_review"])
        self.assertEqual(result["overlap_group_count"], 0)

    def test_detects_exact_text_overlap_across_splits(self):
        result = check_split_leakage({
            "train": [record("1", "Pay now")],
            "test": [record("2", "Pay now")],
        })
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["overlap_group_count"], 1)
        self.assertEqual(result["overlaps"][0]["splits"], ["test", "train"])

    def test_detects_overlap_after_whitespace_normalization(self):
        result = check_split_leakage({
            "train": [record("1", "hello   world")],
            "test": [record("2", "hello world")],
        })
        self.assertTrue(result["requires_review"])

    def test_same_split_duplicates_are_not_cross_split_leakage(self):
        result = check_split_leakage({
            "train": [
                record("1", "same message"),
                record("2", "same message"),
            ],
            "test": [record("3", "different message")],
        })
        self.assertFalse(result["requires_review"])

    def test_empty_splits_mapping(self):
        result = check_split_leakage({})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["split_count"], 0)

    def test_rejects_non_mapping_input(self):
        with self.assertRaises(ValidationError):
            check_split_leakage([])

    def test_rejects_invalid_record(self):
        with self.assertRaises(ValidationError):
            check_split_leakage({"train": ["not a record"]})

    def test_rejects_missing_text(self):
        with self.assertRaises(ValidationError):
            check_split_leakage({"train": [{"record_id": "1"}]})

    def test_result_is_deterministic(self):
        splits = {
            "test": [record("2", "duplicate")],
            "train": [record("1", "duplicate")],
        }
        self.assertEqual(
            check_split_leakage(splits),
            check_split_leakage(splits),
        )


if __name__ == "__main__":
    unittest.main()
