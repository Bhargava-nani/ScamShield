
"""Tests for DataForge quality reports."""

import sys
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ValidationError
from dataforge.processing.deduplicator import deduplicate_records
from dataforge.processing.quality_report import build_quality_report


def make_record(record_id, text, label="ham", data_type="REAL"):
    return {
        "record_id": record_id,
        "text": text,
        "label": label,
        "source_id": "test-source",
        "data_type": data_type,
    }


class QualityReportTests(unittest.TestCase):
    def test_counts_records_duplicates_and_rejections(self):
        result = deduplicate_records([
            make_record("r1", "Hello"),
            make_record("r2", "Hello  "),
            {"record_id": "invalid"},
        ])

        report = build_quality_report(result)

        self.assertEqual(report["input_count"], 3)
        self.assertEqual(report["valid_count"], 2)
        self.assertEqual(report["retained_count"], 1)
        self.assertEqual(report["duplicate_count"], 1)
        self.assertEqual(report["rejected_count"], 1)
        self.assertTrue(report["requires_review"])

    def test_counts_conflict_group_records_without_double_counting(self):
        result = deduplicate_records([
            make_record("r1", "Suspicious link", "ham"),
            make_record("r2", "Suspicious link", "spam"),
        ])

        report = build_quality_report(result)

        self.assertEqual(report["input_count"], 2)
        self.assertEqual(report["retained_count"], 2)
        self.assertEqual(report["conflict_group_count"], 1)
        self.assertEqual(report["conflict_record_count"], 2)
        self.assertEqual(report["duplicate_count"], 0)
        self.assertEqual(report["review_reasons"], ["CONFLICTING_LABELS"])

    def test_label_and_data_type_counts_are_deterministic(self):
        result = deduplicate_records([
            make_record("r1", "One", "ham", "REAL"),
            make_record("r2", "Two", "spam", "SYNTHETIC"),
        ])

        report = build_quality_report(result)

        self.assertEqual(
            report["label_counts"],
            {"ham": 1, "spam": 1},
        )
        self.assertEqual(
            report["data_type_counts"],
            {"REAL": 1, "SYNTHETIC": 1},
        )

    def test_clean_batch_does_not_require_review(self):
        result = deduplicate_records([
            make_record("r1", "One"),
            make_record("r2", "Two", "spam"),
        ])

        report = build_quality_report(result)

        self.assertFalse(report["requires_review"])
        self.assertEqual(report["review_reasons"], [])

    def test_rejects_invalid_result_shape(self):
        with self.assertRaises(ValidationError):
            build_quality_report({"records": []})

    def test_empty_result(self):
        report = build_quality_report(deduplicate_records([]))

        self.assertEqual(report["input_count"], 0)
        self.assertEqual(report["retained_count"], 0)
        self.assertFalse(report["requires_review"])


if __name__ == "__main__":
    unittest.main()
