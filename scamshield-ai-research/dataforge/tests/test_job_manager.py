"""Focused tests for persistent DataForge job tracking."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import StorageError, ValidationError
from dataforge.pipeline.job_manager import JobManager


class JobManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp.name) / "jobs.json"
        self.manager = JobManager(self.state_path)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_job_starts_pending_without_execution(self):
        job = self.manager.create_job("dataset_import", {"source": "test-fixture"})

        self.assertEqual(job["status"], "PENDING")
        self.assertEqual(job["job_type"], "dataset_import")
        self.assertTrue(self.state_path.exists())
        self.assertEqual(len(self.manager.list_jobs()), 1)

    def test_job_persists_after_manager_restarts(self):
        job = self.manager.create_job("validation")
        reloaded = JobManager(self.state_path)

        self.assertEqual(reloaded.get_job(job["job_id"])["status"], "PENDING")

    def test_valid_status_transitions(self):
        job = self.manager.create_job("validation")
        self.manager.update_status(job["job_id"], "RUNNING")
        self.manager.update_status(job["job_id"], "SUCCEEDED")

        self.assertEqual(
            self.manager.get_job(job["job_id"])["status"], "SUCCEEDED"
        )

    def test_failed_job_requires_error(self):
        job = self.manager.create_job("validation")
        self.manager.update_status(job["job_id"], "RUNNING")

        with self.assertRaises(ValidationError):
            self.manager.update_status(job["job_id"], "FAILED")

        failed = self.manager.update_status(
            job["job_id"], "FAILED", error="Fixture validation failed"
        )
        self.assertEqual(failed["error"], "Fixture validation failed")

    def test_rejects_invalid_transition(self):
        job = self.manager.create_job("validation")
        self.manager.update_status(job["job_id"], "RUNNING")
        self.manager.update_status(job["job_id"], "SUCCEEDED")

        with self.assertRaises(ValidationError):
            self.manager.update_status(job["job_id"], "RUNNING")

    def test_rejects_invalid_job_type_and_metadata(self):
        for job_type, metadata in [
            ("", {}),
            (" " * 2, {}),
            ("validation", ["not", "a", "dictionary"]),
            ("validation", {"bad": object()}),
        ]:
            with self.subTest(job_type=job_type, metadata_type=type(metadata).__name__):
                with self.assertRaises(ValidationError):
                    self.manager.create_job(job_type, metadata)

    def test_unknown_job_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.manager.get_job("not-a-real-job")

    def test_status_filter(self):
        first = self.manager.create_job("one")
        self.manager.create_job("two")
        self.manager.update_status(first["job_id"], "RUNNING")

        self.assertEqual(len(self.manager.list_jobs("PENDING")), 1)
        self.assertEqual(len(self.manager.list_jobs("RUNNING")), 1)

    def test_recovery_marks_running_jobs_only_when_requested(self):
        job = self.manager.create_job("validation")
        self.manager.update_status(job["job_id"], "RUNNING")

        # Constructing another manager does not silently change persisted state.
        reloaded = JobManager(self.state_path)
        self.assertEqual(reloaded.get_job(job["job_id"])["status"], "RUNNING")

        self.assertEqual(reloaded.recover_interrupted_jobs(), 1)
        self.assertEqual(
            reloaded.get_job(job["job_id"])["status"], "INTERRUPTED"
        )
        self.assertEqual(reloaded.recover_interrupted_jobs(), 0)

    def test_corrupt_state_file_is_rejected(self):
        self.state_path.write_text("{broken json", encoding="utf-8")

        with self.assertRaises(StorageError):
            JobManager(self.state_path)

    def test_returns_copies_not_mutable_internal_records(self):
        job = self.manager.create_job("validation", {"source": "fixture"})
        job["metadata"]["source"] = "changed"
        self.assertEqual(
            self.manager.get_job(job["job_id"])["metadata"]["source"],
            "fixture",
        )


if __name__ == "__main__":
    unittest.main()
