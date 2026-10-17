"""Tests for the DataForge candidate training milestone."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import joblib

from dataforge.exceptions import ValidationError
from dataforge.training.trainer import train_candidate


def make_records():
    records = []
    for index in range(60):
        if index % 2 == 0:
            label = "ham"
            text = (
                f"family message number {index} "
                f"meeting schedule update code {index}"
            )
        else:
            label = "spam"
            text = (
                f"claim prize number {index} "
                f"urgent click offer code {index}"
            )

        records.append({
            "record_id": f"test-{index}",
            "text": text,
            "label": label,
            "source_id": "unit-test-fixtures",
            "data_type": "SYNTHETIC",
        })
    return records


class CandidateTrainingTests(unittest.TestCase):
    def test_trains_saves_model_and_report_without_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            result = train_candidate(make_records(), output_dir=directory, seed=42)

            self.assertEqual(result["status"], "CANDIDATE_TRAINED")
            self.assertTrue(Path(result["model_path"]).is_file())
            self.assertTrue(Path(result["report_path"]).is_file())

            report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
            self.assertIn("accuracy", report["metrics"])
            self.assertIn("spam_precision", report["metrics"])
            self.assertIn("spam_recall", report["metrics"])
            self.assertIn("spam_f1", report["metrics"])
            self.assertIn("confusion_matrix", report["metrics"])
            self.assertEqual(report["promotion_status"], "NOT_PROMOTED")
            self.assertFalse(report["live_execution_enabled"])

            loaded_model = joblib.load(result["model_path"])
            prediction = loaded_model.predict(["urgent prize claim click now"])
            self.assertEqual(len(prediction), 1)

    def test_rejects_too_few_records(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValidationError):
                train_candidate(make_records()[:10], output_dir=directory)

    def test_rejects_single_class_dataset(self):
        records = make_records()
        for record in records:
            record["label"] = "ham"

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValidationError):
                train_candidate(records, output_dir=directory)

    def test_rejects_conflicting_duplicate_text(self):
        records = make_records()
        records[1]["text"] = records[0]["text"]
        records[1]["label"] = "spam"

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValidationError):
                train_candidate(records, output_dir=directory)

    def test_does_not_mutate_input_records(self):
        records = make_records()
        before = [record.copy() for record in records]

        with tempfile.TemporaryDirectory() as directory:
            train_candidate(records, output_dir=directory)

        self.assertEqual(records, before)


if __name__ == "__main__":
    unittest.main()
