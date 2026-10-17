"""Focused tests for the controlled local import manager."""

import sys
from pathlib import Path

DATAFORGE_PARENT = Path(__file__).resolve().parents[2]
if str(DATAFORGE_PARENT) not in sys.path:
    sys.path.insert(0, str(DATAFORGE_PARENT))

import hashlib
import unittest
from unittest.mock import Mock

from dataforge.pipeline.import_manager import import_local_records
from dataforge.exceptions import ProvenanceError, ValidationError
from dataforge.storage.manifest import create_manifest


class ImportManagerTests(unittest.TestCase):
    def setUp(self):
        self.artifact = b"fictional local dataset fixture"
        self.manifest = create_manifest(
            source_id="fixture-source",
            source_url="https://example.com/dataset.json",
            sha256=hashlib.sha256(self.artifact).hexdigest(),
            size_bytes=len(self.artifact),
            license_status="public_domain",
            permission_confirmed=True,
            data_type="REAL",
        )
        self.repository = Mock()
        self.repository.add_records.return_value = {
            "total_records": 1,
            "added_records": 1,
        }
        self.records = [
            {
                "record_id": "record-001",
                "text": "A fictional test message.",
                "label": "ham",
                "source_id": "fixture-source",
                "data_type": "REAL",
            }
        ]

    def run_import(self, **overrides):
        args = {
            "artifact_bytes": self.artifact,
            "records": self.records,
            "manifest": self.manifest,
            "approved_domains": {"example.com"},
            "repository": self.repository,
        }
        args.update(overrides)
        return import_local_records(**args)

    def test_valid_batch_is_imported(self):
        result = self.run_import()

        self.assertEqual(result["status"], "IMPORTED")
        self.assertTrue(result["persisted"])
        self.assertFalse(result["requires_review"])
        self.repository.add_records.assert_called_once()

    def test_artifact_hash_mismatch_is_rejected(self):
        with self.assertRaises(ProvenanceError):
            self.run_import(artifact_bytes=b"different content")

        self.repository.add_records.assert_not_called()

    def test_unapproved_domain_is_rejected(self):
        with self.assertRaises(Exception):
            self.run_import(approved_domains={"other.example"})

        self.repository.add_records.assert_not_called()

    def test_mismatched_record_source_is_rejected(self):
        records = [dict(self.records[0], source_id="other-source")]

        with self.assertRaises(ValidationError):
            self.run_import(records=records)

        self.repository.add_records.assert_not_called()

    def test_mismatched_record_data_type_is_rejected(self):
        records = [dict(self.records[0], data_type="SYNTHETIC")]

        with self.assertRaises(ValidationError):
            self.run_import(records=records)

        self.repository.add_records.assert_not_called()

    def test_invalid_record_batch_requires_review(self):
        records = [
            dict(self.records[0], text=""),
        ]

        result = self.run_import(records=records)

        self.assertTrue(result["requires_review"])
        self.assertIn("INVALID_RECORDS", result["review_reasons"])
        self.assertFalse(result["persisted"])
        self.repository.add_records.assert_not_called()

    def test_conflicting_labels_require_review(self):
        records = [
            self.records[0],
            dict(
                self.records[0],
                record_id="record-002",
                label="spam",
            ),
        ]

        result = self.run_import(records=records)

        self.assertTrue(result["requires_review"])
        self.assertIn(
            "CONFLICTING_LABELS",
            result["review_reasons"],
        )
        self.assertFalse(result["persisted"])
        self.repository.add_records.assert_not_called()

    def test_duplicate_records_are_deduplicated(self):
        records = [
            self.records[0],
            dict(
                self.records[0],
                record_id="record-002",
            ),
        ]

        result = self.run_import(records=records)

        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["retained_count"], 1)
        self.assertTrue(result["persisted"])
        self.repository.add_records.assert_called_once()

    def test_empty_batch_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.run_import(records=[])

        self.repository.add_records.assert_not_called()


if __name__ == "__main__":
    unittest.main()