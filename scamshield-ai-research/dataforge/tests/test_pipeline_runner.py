
"""Focused tests for the review-gated DataForge pipeline runner."""

import sys
import tempfile
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ValidationError
from dataforge.pipeline.job_manager import JobManager
from dataforge.pipeline.pipeline_runner import PipelineRunner
from dataforge.storage.repository import DatasetRepository


def record(record_id, text, label="ham"):
    return {
        "record_id": record_id,
        "text": text,
        "label": label,
        "source_id": "test-fixture",
        "data_type": "SYNTHETIC",
    }


class PipelineRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.repository = DatasetRepository(root / "dataset.jsonl")
        self.jobs = JobManager(root / "jobs.json")
        self.runner = PipelineRunner(self.repository, self.jobs)

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_batch_is_processed_and_persisted(self):
        result = self.runner.run_records([
            record("r1", "  Hello   there "),
            record("r2", "A different message"),
        ])

        self.assertTrue(result["persisted"])
        self.assertFalse(result["review_required"])
        self.assertEqual(result["job"]["status"], "SUCCEEDED")
        self.assertEqual(result["storage"]["added_records"], 2)
        saved = self.repository.load_records()
        self.assertEqual(saved[0]["text"], "Hello there")

    def test_exact_duplicate_is_reported_and_deduplicated(self):
        result = self.runner.run_records([
            record("r1", "Hello there"),
            record("r2", " Hello   there "),
        ])

        self.assertTrue(result["persisted"])
        self.assertEqual(result["quality_report"]["duplicate_count"], 1)
        self.assertEqual(len(self.repository.load_records()), 1)

    def test_invalid_record_requires_review_and_writes_nothing(self):
        invalid = record("r1", "Hello")
        invalid["unexpected_field"] = "not allowed"

        result = self.runner.run_records([
            record("r2", "Valid message"),
            invalid,
        ])

        self.assertFalse(result["persisted"])
        self.assertTrue(result["review_required"])
        self.assertIn("INVALID_RECORDS", result["review_reasons"])
        self.assertEqual(result["job"]["status"], "FAILED")
        self.assertEqual(self.repository.load_records(), [])

    def test_conflicting_labels_require_review_and_write_nothing(self):
        result = self.runner.run_records([
            record("r1", "Verify your account", "ham"),
            record("r2", " Verify   your account ", "spam"),
        ])

        self.assertFalse(result["persisted"])
        self.assertTrue(result["review_required"])
        self.assertIn("CONFLICTING_LABELS", result["review_reasons"])
        self.assertEqual(result["quality_report"]["conflict_group_count"], 1)
        self.assertEqual(self.repository.load_records(), [])

    def test_empty_batch_is_allowed(self):
        result = self.runner.run_records([])

        self.assertTrue(result["persisted"])
        self.assertEqual(result["quality_report"]["input_count"], 0)
        self.assertEqual(result["job"]["status"], "SUCCEEDED")

    def test_non_list_input_is_rejected_before_job_creation(self):
        with self.assertRaises(ValidationError):
            self.runner.run_records("not a batch")

        self.assertEqual(self.jobs.list_jobs(), [])

    def test_metadata_must_be_a_dictionary(self):
        with self.assertRaises(ValidationError):
            self.runner.run_records([], metadata=["invalid"])

        self.assertEqual(self.jobs.list_jobs(), [])

    def test_metadata_cannot_override_trusted_job_fields(self):
        result = self.runner.run_records(
            [record("r1", "A fictional test message")],
            metadata={
                "input_count": 999,
                "mode": "UNSAFE_OVERRIDE",
                "source": "regression-test",
            },
        )

        job_metadata = result["job"]["metadata"]

        self.assertEqual(job_metadata["input_count"], 1)
        self.assertEqual(job_metadata["mode"], "LOCAL_REVIEW_GATED")
        self.assertEqual(job_metadata["source"], "regression-test")

    def test_repository_conflict_fails_job_without_overwriting_existing_data(self):
        self.repository.add_records([record("same-id", "Original message")])

        with self.assertRaises(Exception):
            self.runner.run_records([
                record("same-id", "Different message"),
            ])

        saved = self.repository.load_records()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["text"], "Original message")
        self.assertEqual(self.jobs.list_jobs("FAILED")[0]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
