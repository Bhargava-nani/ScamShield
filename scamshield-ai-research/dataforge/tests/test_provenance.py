"""Regression tests for DataForge manifest and provenance validation."""

import hashlib
import json
import sys
import unittest
from pathlib import Path


RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import ProvenanceError, ValidationError
from dataforge.storage.manifest import (
    create_manifest,
    parse_manifest,
    serialize_manifest,
)
from dataforge.storage.provenance import verify_manifest


CONTENT = b"approved dataset content"
DIGEST = hashlib.sha256(CONTENT).hexdigest()


def make_manifest(**overrides):
    manifest = create_manifest(
        source_id="test-source",
        source_url="https://example.com/dataset.txt",
        sha256=DIGEST,
        size_bytes=len(CONTENT),
        license_status="approved",
        permission_confirmed=True,
        data_type="REAL",
    )
    manifest.update(overrides)
    return manifest


class ManifestTests(unittest.TestCase):
    def test_create_and_verify_manifest(self):
        manifest = make_manifest()

        self.assertTrue(
            verify_manifest(
                manifest,
                actual_sha256=DIGEST,
                actual_size=len(CONTENT),
            )
        )

    def test_serialize_and_parse_round_trip(self):
        manifest = make_manifest()

        serialized = serialize_manifest(manifest)
        parsed = parse_manifest(serialized)

        self.assertEqual(parsed, manifest)

    def test_rejects_missing_required_field(self):
        manifest = make_manifest()
        del manifest["source_id"]

        with self.assertRaises(ProvenanceError):
            serialize_manifest(manifest)

    def test_rejects_unknown_manifest_field(self):
        manifest = make_manifest()
        manifest["unexpected"] = "value"

        with self.assertRaises(ProvenanceError):
            serialize_manifest(manifest)

    def test_rejects_duplicate_json_keys(self):
        manifest = make_manifest()
        content = json.dumps(manifest)
        content = content[:-1] + ',"source_id":"different-source"}'

        with self.assertRaises(ProvenanceError):
            parse_manifest(content)

    def test_rejects_invalid_url(self):
        manifest = make_manifest(source_url="http://example.com/data.txt")

        with self.assertRaises(ProvenanceError):
            serialize_manifest(manifest)

    def test_rejects_credentials_in_url(self):
        manifest = make_manifest(
            source_url="https://user:password@example.com/data.txt"
        )

        with self.assertRaises(ProvenanceError):
            serialize_manifest(manifest)

    def test_rejects_unapproved_license(self):
        with self.assertRaises(ProvenanceError):
            create_manifest(
                source_id="test-source",
                source_url="https://example.com/dataset.txt",
                sha256=DIGEST,
                size_bytes=len(CONTENT),
                license_status="unknown",
                permission_confirmed=True,
            )

    def test_rejects_unconfirmed_permission(self):
        with self.assertRaises(ProvenanceError):
            create_manifest(
                source_id="test-source",
                source_url="https://example.com/dataset.txt",
                sha256=DIGEST,
                size_bytes=len(CONTENT),
                license_status="approved",
                permission_confirmed=False,
            )

    def test_rejects_naive_timestamp(self):
        manifest = make_manifest(retrieved_at="2026-10-12T10:00:00")

        with self.assertRaises(ProvenanceError):
            serialize_manifest(manifest)

    def test_rejects_malformed_hash(self):
        manifest = make_manifest(retrieved_sha256="not-a-hash")

        with self.assertRaises(ProvenanceError):
            serialize_manifest(manifest)

    def test_rejects_negative_size(self):
        manifest = make_manifest(retrieved_bytes=-1)

        with self.assertRaises(ProvenanceError):
            serialize_manifest(manifest)

    def test_rejects_boolean_size(self):
        manifest = make_manifest(retrieved_bytes=True)

        with self.assertRaises(ProvenanceError):
            serialize_manifest(manifest)

    def test_rejects_unvalidated_manifest(self):
        manifest = make_manifest(approval_status="PENDING")

        with self.assertRaises(ProvenanceError):
            verify_manifest(manifest)

    def test_rejects_hash_mismatch(self):
        manifest = make_manifest()

        with self.assertRaises(ProvenanceError):
            verify_manifest(manifest, actual_sha256="0" * 64)

    def test_rejects_size_mismatch(self):
        manifest = make_manifest()

        with self.assertRaises(ProvenanceError):
            verify_manifest(manifest, actual_size=len(CONTENT) + 1)

    def test_rejects_missing_artifact_hash_during_verification(self):
        manifest = make_manifest()
        manifest["retrieved_sha256"] = None

        with self.assertRaises(ProvenanceError):
            verify_manifest(manifest)

    def test_rejects_missing_artifact_size_during_verification(self):
        manifest = make_manifest()
        manifest["retrieved_bytes"] = None

        with self.assertRaises(ProvenanceError):
            verify_manifest(manifest)

    def test_accepts_valid_processing_history(self):
        manifest = make_manifest(
            processing_history=[
                {
                    "operation": "initial_validation",
                    "timestamp": "2026-10-12T10:00:00+00:00",
                    "details": {"result": "passed"},
                }
            ]
        )

        self.assertTrue(verify_manifest(manifest))

    def test_rejects_invalid_processing_history_timestamp(self):
        manifest = make_manifest(
            processing_history=[
                {
                    "operation": "initial_validation",
                    "timestamp": "not-a-timestamp",
                }
            ]
        )

        with self.assertRaises(ProvenanceError):
            serialize_manifest(manifest)


if __name__ == "__main__":
    unittest.main()