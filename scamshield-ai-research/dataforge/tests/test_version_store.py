"""Tests for persistent immutable dataset version storage."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.datasets.version_store import DatasetVersionStore
from dataforge.exceptions import (
    ProvenanceError,
    StorageError,
    ValidationError,
)


class DatasetVersionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "versions"
        self.store = DatasetVersionStore(self.root)
        self.records = [
            {"text": "Hello there", "label": "ham"},
            {"text": "Claim your prize", "label": "spam"},
        ]

    def tearDown(self):
        self.temp.cleanup()

    def test_save_and_load_round_trip(self):
        version = self.store.save(self.records, dataset_name="messages")
        loaded = self.store.load(version["version_id"])
        self.assertEqual(loaded["version"], version)
        self.assertEqual(loaded["records"], self.records)

    def test_saved_file_is_inside_store(self):
        version = self.store.save(self.records)
        path = self.root / f'{version["version_id"]}.json'
        self.assertTrue(path.is_file())
        self.assertEqual(path.parent.resolve(), self.root.resolve())

    def test_identical_save_is_idempotent(self):
        first = self.store.save(self.records, dataset_name="messages")
        second = self.store.save(self.records, dataset_name="messages")
        self.assertEqual(first, second)
        self.assertEqual(len(self.store.list_versions()), 1)

    def test_changed_content_creates_new_version(self):
        first = self.store.save(self.records)
        changed = self.records + [{"text": "New message", "label": "ham"}]
        second = self.store.save(changed)
        self.assertNotEqual(first["version_id"], second["version_id"])
        self.assertEqual(len(self.store.list_versions()), 2)

    def test_synthetic_type_is_preserved(self):
        version = self.store.save(
            self.records,
            dataset_name="synthetic-messages",
            data_type="SYNTHETIC",
        )
        loaded = self.store.load(version["version_id"])
        self.assertEqual(loaded["version"]["data_type"], "SYNTHETIC")

    def test_listing_is_sorted(self):
        self.store.save([{"text": "Second", "label": "ham"}],
                        dataset_name="second")
        self.store.save([{"text": "First", "label": "ham"}],
                        dataset_name="first")
        ids = [v["version_id"] for v in self.store.list_versions()]
        self.assertEqual(ids, sorted(ids))

    def test_invalid_version_id_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.store.load("../outside")

    def test_missing_version_raises_storage_error(self):
        with self.assertRaises(StorageError):
            self.store.load("a" * 64)

    def test_corrupt_json_is_rejected(self):
        version = self.store.save(self.records)
        path = self.root / f'{version["version_id"]}.json'
        path.write_text("{not valid JSON", encoding="utf-8")
        with self.assertRaises(ProvenanceError):
            self.store.load(version["version_id"])

    def test_modified_records_are_detected(self):
        version = self.store.save(self.records)
        path = self.root / f'{version["version_id"]}.json'
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["records"][0]["text"] = "Tampered content"
        path.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaises(ProvenanceError):
            self.store.load(version["version_id"])

    def test_unknown_envelope_fields_are_rejected(self):
        version = self.store.save(self.records)
        path = self.root / f'{version["version_id"]}.json'
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["unexpected"] = True
        path.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaises(ProvenanceError):
            self.store.load(version["version_id"])

    def test_unknown_store_schema_is_rejected(self):
        version = self.store.save(self.records)
        path = self.root / f'{version["version_id"]}.json'
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["store_schema_version"] = "999"
        path.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaises(ProvenanceError):
            self.store.load(version["version_id"])

    def test_corrupt_existing_version_is_not_overwritten(self):
        version = self.store.save(self.records)
        path = self.root / f'{version["version_id"]}.json'
        path.write_text("corrupt", encoding="utf-8")
        with self.assertRaises(ProvenanceError):
            self.store.save(self.records)
        self.assertEqual(path.read_text(encoding="utf-8"), "corrupt")

    def test_invalid_json_filename_fails_closed_during_listing(self):
        (self.root / "invalid.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ProvenanceError):
            self.store.list_versions()

    def test_non_dictionary_record_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.store.save([{"text": "valid"}, "not-a-record"])

    def test_invalid_data_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.store.save(self.records, data_type="UNKNOWN")


if __name__ == "__main__":
    unittest.main()
