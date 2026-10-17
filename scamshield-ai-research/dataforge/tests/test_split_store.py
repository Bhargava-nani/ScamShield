
"""Tests for immutable dataset split persistence and lineage."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.datasets.split_manager import split_dataset
from dataforge.datasets.split_store import DatasetSplitStore
from dataforge.datasets.version_store import DatasetVersionStore
from dataforge.exceptions import (
    ProvenanceError,
    StorageError,
    ValidationError,
)


def make_record(record_id, text, label="ham", data_type="REAL"):
    return {
        "record_id": record_id,
        "text": text,
        "label": label,
        "source_id": f"source-{record_id}",
        "data_type": data_type,
    }


class DatasetSplitStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.parent_store = DatasetVersionStore(self.base / "parents")
        self.split_store = DatasetSplitStore(
            root_dir=self.base / "splits",
            dataset_store=self.parent_store,
        )
        self.records = [
            make_record(
                str(index),
                f"unique message number {index}",
                "spam" if index % 2 else "ham",
            )
            for index in range(20)
        ]
        self.parent = self.parent_store.save(
            self.records,
            dataset_name="test-messages",
            data_type="REAL",
        )
        self.split_result = split_dataset(self.records, seed=42)

    def tearDown(self):
        self.temp.cleanup()

    def test_save_and_load_round_trip(self):
        saved = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        loaded = self.split_store.load(saved["split_set_id"])
        self.assertEqual(loaded, saved)
        self.assertEqual(
            loaded["metadata"]["parent_version_id"],
            self.parent["version_id"],
        )
        self.assertEqual(loaded["metadata"]["data_type"], "REAL")

    def test_identical_save_is_idempotent(self):
        first = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        second = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        self.assertEqual(first, second)
        self.assertEqual(
            len(list((self.base / "splits").glob("*.json"))), 1
        )

    def test_split_artifact_is_inside_store(self):
        saved = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        path = self.base / "splits" / f'{saved["split_set_id"]}.json'
        self.assertTrue(path.is_file())
        self.assertEqual(
            path.resolve().parent,
            (self.base / "splits").resolve(),
        )

    def test_metadata_preserves_seed_ratios_and_counts(self):
        saved = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        metadata = saved["metadata"]
        self.assertEqual(metadata["seed"], 42)
        self.assertEqual(metadata["ratios"], self.split_result["ratios"])
        self.assertEqual(
            metadata["split_counts"],
            self.split_result["split_counts"],
        )
        self.assertEqual(metadata["record_count"], len(self.records))

    def test_synthetic_lineage_is_preserved(self):
        synthetic = [
            make_record(
                str(i),
                f"synthetic message {i}",
                "ham",
                "SYNTHETIC",
            )
            for i in range(8)
        ]
        parent = self.parent_store.save(
            synthetic,
            dataset_name="synthetic-fixture",
            data_type="SYNTHETIC",
        )
        result = split_dataset(synthetic, seed=7)
        saved = self.split_store.save(result, parent["version_id"])
        loaded = self.split_store.load(saved["split_set_id"])
        self.assertEqual(loaded["metadata"]["data_type"], "SYNTHETIC")
        self.assertEqual(
            loaded["metadata"]["parent_version_id"],
            parent["version_id"],
        )

    def test_conflicting_labels_cannot_be_persisted(self):
        records = [
            make_record("a", "same message", "ham"),
            make_record("b", "same   message", "spam"),
        ]
        parent = self.parent_store.save(
            records,
            dataset_name="conflict-fixture",
        )
        result = split_dataset(records)
        self.assertTrue(result["requires_review"])
        with self.assertRaises(ValidationError):
            self.split_store.save(result, parent["version_id"])

    def test_review_required_result_cannot_be_persisted(self):
        result = dict(self.split_result)
        result["requires_review"] = True

        with self.assertRaises(ValidationError):
            self.split_store.save(result, self.parent["version_id"])

    def test_missing_status_cannot_be_persisted(self):
        result = dict(self.split_result)
        result.pop("status", None)

        with self.assertRaises(ValidationError):
            self.split_store.save(result, self.parent["version_id"])

    def test_invalid_status_cannot_be_persisted(self):
        result = dict(self.split_result)
        result["status"] = "UNKNOWN"

        with self.assertRaises(ValidationError):
            self.split_store.save(result, self.parent["version_id"])

    def test_missing_parent_is_rejected(self):
        with self.assertRaises(StorageError):
            self.split_store.save(self.split_result, "a" * 64)

    def test_invalid_parent_id_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.split_store.save(self.split_result, "../outside")

    def test_added_split_record_is_rejected(self):
        changed = {
            **self.split_result,
            "splits": {
                name: list(records)
                for name, records in self.split_result["splits"].items()
            },
        }
        changed["splits"]["train"].append(
            make_record("extra", "not in parent dataset")
        )

        with self.assertRaises(ProvenanceError):
            self.split_store.save(changed, self.parent["version_id"])

    def test_removed_split_record_is_rejected(self):
        changed = {
            **self.split_result,
            "splits": {
                name: list(records)
                for name, records in self.split_result["splits"].items()
            },
        }
        changed["splits"]["train"].pop()

        with self.assertRaises(ProvenanceError):
            self.split_store.save(changed, self.parent["version_id"])

    def test_modified_saved_record_is_detected(self):
        saved = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        path = self.base / "splits" / f'{saved["split_set_id"]}.json'
        envelope = json.loads(path.read_text(encoding="utf-8"))

        for name in ("train", "validation", "test"):
            if envelope["splits"][name]:
                envelope["splits"][name][0]["text"] = "tampered message"
                break

        path.write_text(json.dumps(envelope), encoding="utf-8")

        with self.assertRaises(ProvenanceError):
            self.split_store.load(saved["split_set_id"])

    def test_modified_metadata_is_detected(self):
        saved = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        path = self.base / "splits" / f'{saved["split_set_id"]}.json'
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["metadata"]["seed"] = 999
        path.write_text(json.dumps(envelope), encoding="utf-8")

        with self.assertRaises(ProvenanceError):
            self.split_store.load(saved["split_set_id"])

    def test_corrupt_json_is_rejected(self):
        saved = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        path = self.base / "splits" / f'{saved["split_set_id"]}.json'
        path.write_text("{broken", encoding="utf-8")

        with self.assertRaises(StorageError):
            self.split_store.load(saved["split_set_id"])

    def test_unknown_envelope_field_is_rejected(self):
        saved = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        path = self.base / "splits" / f'{saved["split_set_id"]}.json'
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["unexpected"] = True
        path.write_text(json.dumps(envelope), encoding="utf-8")

        with self.assertRaises(ProvenanceError):
            self.split_store.load(saved["split_set_id"])

    def test_unknown_schema_is_rejected(self):
        saved = self.split_store.save(
            self.split_result, self.parent["version_id"]
        )
        path = self.base / "splits" / f'{saved["split_set_id"]}.json'
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["store_schema_version"] = "999"
        path.write_text(json.dumps(envelope), encoding="utf-8")

        with self.assertRaises(ProvenanceError):
            self.split_store.load(saved["split_set_id"])

    def test_invalid_split_id_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.split_store.load("../outside")

    def test_missing_split_version_is_rejected(self):
        with self.assertRaises(StorageError):
            self.split_store.load("a" * 64)

    def test_invalid_ratios_are_rejected(self):
        changed = dict(self.split_result)
        changed["ratios"] = {
            "train": 0.8,
            "validation": 0.1,
            "test": 0.2,
        }

        with self.assertRaises(ValidationError):
            self.split_store.save(changed, self.parent["version_id"])

    def test_reported_counts_must_match(self):
        changed = dict(self.split_result)
        changed["split_counts"] = {
            "train": 999,
            "validation": 0,
            "test": 0,
        }

        with self.assertRaises(ProvenanceError):
            self.split_store.save(changed, self.parent["version_id"])

    def test_empty_dataset_can_be_saved(self):
        empty_parent = self.parent_store.save(
            [],
            dataset_name="empty-fixture",
        )
        result = split_dataset([])
        saved = self.split_store.save(
            result,
            empty_parent["version_id"],
        )
        loaded = self.split_store.load(saved["split_set_id"])

        self.assertEqual(loaded["metadata"]["record_count"], 0)
        self.assertEqual(
            loaded["metadata"]["split_counts"],
            {"train": 0, "validation": 0, "test": 0},
        )


if __name__ == "__main__":
    unittest.main()
