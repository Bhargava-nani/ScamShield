"""Regression tests for deterministic dataset versioning."""

import copy
import sys
import unittest
from pathlib import Path


RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ProvenanceError, ValidationError
from dataforge.datasets.dataset_versioning import (
    create_dataset_version,
    verify_dataset_version,
)


RECORDS = [
    {"text": "First message", "label": "ham"},
    {"text": "Suspicious message", "label": "spam"},
]


class DatasetVersioningTests(unittest.TestCase):
    def test_creates_version_descriptor(self):
        version = create_dataset_version(RECORDS)

        self.assertEqual(version["schema_version"], "1.0")
        self.assertEqual(version["record_count"], 2)
        self.assertEqual(len(version["content_sha256"]), 64)
        self.assertEqual(len(version["version_id"]), 64)

    def test_identical_content_produces_identical_version(self):
        first = create_dataset_version(RECORDS)
        second = create_dataset_version(copy.deepcopy(RECORDS))

        self.assertEqual(first, second)

    def test_dictionary_key_order_does_not_change_hash(self):
        first = [{"text": "hello", "label": "ham"}]
        second = [{"label": "ham", "text": "hello"}]

        self.assertEqual(
            create_dataset_version(first)["content_sha256"],
            create_dataset_version(second)["content_sha256"],
        )

    def test_record_order_changes_hash(self):
        forward = create_dataset_version(RECORDS)
        reversed_records = create_dataset_version(list(reversed(RECORDS)))

        self.assertNotEqual(
            forward["content_sha256"],
            reversed_records["content_sha256"],
        )

    def test_dataset_name_changes_version_id(self):
        first = create_dataset_version(RECORDS, dataset_name="alpha")
        second = create_dataset_version(RECORDS, dataset_name="beta")

        self.assertEqual(
            first["content_sha256"],
            second["content_sha256"],
        )
        self.assertNotEqual(first["version_id"], second["version_id"])

    def test_synthetic_data_is_explicitly_labelled(self):
        version = create_dataset_version(
            RECORDS,
            data_type="SYNTHETIC",
        )

        self.assertEqual(version["data_type"], "SYNTHETIC")

    def test_valid_version_verifies(self):
        version = create_dataset_version(RECORDS)

        self.assertTrue(verify_dataset_version(RECORDS, version))

    def test_changed_content_is_rejected(self):
        version = create_dataset_version(RECORDS)
        changed = copy.deepcopy(RECORDS)
        changed[0]["text"] = "Modified message"

        with self.assertRaises(ProvenanceError):
            verify_dataset_version(changed, version)

    def test_changed_record_count_is_rejected(self):
        version = create_dataset_version(RECORDS)

        with self.assertRaises(ProvenanceError):
            verify_dataset_version(RECORDS[:1], version)

    def test_tampered_version_id_is_rejected(self):
        version = create_dataset_version(RECORDS)
        version["version_id"] = "0" * 64

        with self.assertRaises(ProvenanceError):
            verify_dataset_version(RECORDS, version)

    def test_unknown_version_fields_are_rejected(self):
        version = create_dataset_version(RECORDS)
        version["unexpected"] = "value"

        with self.assertRaises(ProvenanceError):
            verify_dataset_version(RECORDS, version)

    def test_invalid_records_are_rejected(self):
        with self.assertRaises(ValidationError):
            create_dataset_version("not a record list")

        with self.assertRaises(ValidationError):
            create_dataset_version([{"text": object()}])

    def test_invalid_data_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            create_dataset_version(RECORDS, data_type="UNKNOWN")

    def test_invalid_dataset_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            create_dataset_version(RECORDS, dataset_name=" ")

    def test_input_records_are_not_modified(self):
        original = copy.deepcopy(RECORDS)

        create_dataset_version(RECORDS)

        self.assertEqual(RECORDS, original)


if __name__ == "__main__":
    unittest.main()