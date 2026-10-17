"""Tests for DataForge source validation."""

import sys
import unittest
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parents[2]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.collection.source_validator import validate_source
from dataforge.constants import DATA_REAL, DATA_SYNTHETIC
from dataforge.exceptions import (
    ProvenanceError,
    SecurityViolationError,
    ValidationError,
)


class SourceValidatorTests(unittest.TestCase):
    def setUp(self):
        self.approved_domains = {"datasets.example.org"}
        self.source = {
            "source_id": "approved-dataset",
            "source_url": "https://datasets.example.org/data.csv",
            "permission_confirmed": True,
            "license_status": "approved",
        }

    def test_valid_source_is_normalized(self):
        result = validate_source(self.source, self.approved_domains)

        self.assertEqual(result["source_id"], "approved-dataset")
        self.assertEqual(
            result["source_url"],
            "https://datasets.example.org/data.csv",
        )
        self.assertEqual(result["domain"], "datasets.example.org")
        self.assertEqual(result["approval_status"], "VALIDATED")
        self.assertEqual(result["data_type"], DATA_REAL)
        self.assertIsNone(result["provider"])

    def test_source_input_is_not_mutated(self):
        original = dict(self.source)
        validate_source(self.source, self.approved_domains)
        self.assertEqual(self.source, original)

    def test_synthetic_type_is_preserved(self):
        source = {**self.source, "data_type": DATA_SYNTHETIC}
        result = validate_source(source, self.approved_domains)
        self.assertEqual(result["data_type"], DATA_SYNTHETIC)

    def test_provider_is_normalized(self):
        source = {**self.source, "provider": "  Example Provider  "}
        result = validate_source(source, self.approved_domains)
        self.assertEqual(result["provider"], "Example Provider")

    def test_reject_non_dictionary(self):
        with self.assertRaises(ValidationError):
            validate_source([], self.approved_domains)

    def test_reject_missing_required_field(self):
        source = dict(self.source)
        del source["source_id"]

        with self.assertRaises(ValidationError):
            validate_source(source, self.approved_domains)

    def test_reject_unknown_field(self):
        source = {**self.source, "secret_override": True}

        with self.assertRaises(ValidationError):
            validate_source(source, self.approved_domains)

    def test_reject_blank_source_id(self):
        source = {**self.source, "source_id": "   "}

        with self.assertRaises(ValidationError):
            validate_source(source, self.approved_domains)

    def test_reject_non_boolean_permission(self):
        source = {**self.source, "permission_confirmed": 1}

        with self.assertRaises(ValidationError):
            validate_source(source, self.approved_domains)

    def test_reject_unconfirmed_permission(self):
        source = {**self.source, "permission_confirmed": False}

        with self.assertRaises(ProvenanceError):
            validate_source(source, self.approved_domains)

    def test_reject_unapproved_license(self):
        source = {**self.source, "license_status": "unknown"}

        with self.assertRaises(ProvenanceError):
            validate_source(source, self.approved_domains)

    def test_reject_unapproved_domain(self):
        source = {
            **self.source,
            "source_url": "https://unapproved.example.net/data.csv",
        }

        with self.assertRaises(SecurityViolationError):
            validate_source(source, self.approved_domains)

    def test_reject_http_url(self):
        source = {
            **self.source,
            "source_url": "http://datasets.example.org/data.csv",
        }

        with self.assertRaises(SecurityViolationError):
            validate_source(source, self.approved_domains)

    def test_reject_url_credentials(self):
        source = {
            **self.source,
            "source_url": "https://user:password@datasets.example.org/data.csv",
        }

        with self.assertRaises(SecurityViolationError):
            validate_source(source, self.approved_domains)

    def test_reject_local_destination(self):
        source = {
            **self.source,
            "source_url": "https://localhost/private",
        }

        with self.assertRaises(SecurityViolationError):
            validate_source(source, self.approved_domains)

    def test_reject_missing_domain_allowlist(self):
        with self.assertRaises(ValidationError):
            validate_source(self.source, None)

    def test_reject_invalid_data_type(self):
        source = {**self.source, "data_type": "UNKNOWN"}

        with self.assertRaises(ValidationError):
            validate_source(source, self.approved_domains)

    def test_reject_invalid_provider(self):
        source = {**self.source, "provider": "   "}

        with self.assertRaises(ValidationError):
            validate_source(source, self.approved_domains)


if __name__ == "__main__":
    unittest.main()
