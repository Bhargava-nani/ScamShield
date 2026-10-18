
"""Tests for deterministic dataset splitting."""

import sys
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ValidationError
from dataforge.datasets.split_manager import split_dataset


def make_record(record_id, text, label="ham"):
    return {
        "record_id": record_id,
        "text": text,
        "label": label,
        "source_id": f"source-{record_id}",
        "data_type": "REAL",
    }


class SplitManagerTests(unittest.TestCase):
    def make_records(self, count=20):
        return [
            make_record(
                str(index),
                f"unique message number {index}",
                "spam" if index % 2 else "ham",
            )
            for index in range(count)
        ]

    def test_default_split_counts_cover_all_records(self):
        records = self.make_records()
        result = split_dataset(records)

        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(
            sum(result["split_counts"].values()),
            len(records),
        )

    def test_fixed_seed_is_reproducible(self):
        records = self.make_records()
        first = split_dataset(records, seed=123)
        second = split_dataset(records, seed=123)

        self.assertEqual(first, second)

    def test_each_record_appears_exactly_once(self):
        records = self.make_records()
        result = split_dataset(records)

        all_ids = [
            record["record_id"]
            for split_records in result["splits"].values()
            for record in split_records
        ]
        self.assertCountEqual(
            all_ids,
            [record["record_id"] for record in records],
        )
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_identical_text_stays_in_one_split(self):
        records = [
            make_record("1", "same message"),
            make_record("2", "same   message"),
            make_record("3", "another message"),
            make_record("4", "third message"),
        ]
        result = split_dataset(records)

        locations = {}
        for split_name, split_records in result["splits"].items():
            for record in split_records:
                if record["record_id"] in {"1", "2"}:
                    locations[record["record_id"]] = split_name

        self.assertEqual(locations["1"], locations["2"])
        self.assertFalse(result["leakage_report"]["requires_review"])

    def test_conflicting_labels_require_review(self):
        records = [
            make_record("1", "same message", "ham"),
            make_record("2", "same   message", "spam"),
        ]
        result = split_dataset(records)

        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertTrue(result["requires_review"])
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertEqual(
            sum(result["split_counts"].values()),
            0,
        )

    def test_rejects_invalid_ratios(self):
        with self.assertRaises(ValidationError):
            split_dataset(
                self.make_records(),
                ratios={"train": 0.8, "validation": 0.1, "test": 0.2},
            )

    def test_rejects_missing_ratio_names(self):
        with self.assertRaises(ValidationError):
            split_dataset(
                self.make_records(),
                ratios={"train": 0.8, "test": 0.2},
            )

    def test_rejects_invalid_seed(self):
        with self.assertRaises(ValidationError):
            split_dataset(self.make_records(), seed=True)

    def test_rejects_invalid_record(self):
        with self.assertRaises(ValidationError):
            split_dataset([{"record_id": "incomplete"}])

    def test_does_not_mutate_input(self):
        records = self.make_records()
        original = [record.copy() for record in records]

        split_dataset(records)

        self.assertEqual(records, original)

    def test_empty_input(self):
        result = split_dataset([])

        self.assertEqual(result["split_counts"], {
            "train": 0,
            "validation": 0,
            "test": 0,
        })
        self.assertFalse(result["requires_review"])


if __name__ == "__main__":
    unittest.main()
