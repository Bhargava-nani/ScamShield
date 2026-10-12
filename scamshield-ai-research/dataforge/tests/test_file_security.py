
"""Automated tests for DataForge file security utilities."""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

# Make the research directory importable without renaming it.
RESEARCH_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RESEARCH_DIR))

from dataforge.exceptions import SecurityViolationError, ValidationError
from dataforge.security.file_security import (
    calculate_sha256,
    validate_file_path,
    verify_sha256,
)


class FileSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sample = self.root / "message.txt"
        self.sample.write_text("ScamShield DataForge test", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_file(self):
        result = validate_file_path(
            self.sample,
            self.root,
            allowed_extensions={".txt"},
        )
        self.assertEqual(result, self.sample.resolve())

    def test_reject_path_outside_root(self):
        outside = self.root.parent / "outside.txt"
        try:
            outside.write_text("outside", encoding="utf-8")
            with self.assertRaises(SecurityViolationError):
                validate_file_path(outside, self.root)
        finally:
            outside.unlink(missing_ok=True)

    def test_reject_oversized_file(self):
        with self.assertRaises(SecurityViolationError):
            validate_file_path(self.sample, self.root, max_bytes=5)

    def test_reject_wrong_extension(self):
        with self.assertRaises(ValidationError):
            validate_file_path(
                self.sample,
                self.root,
                allowed_extensions={".csv"},
            )

    def test_reject_missing_file(self):
        with self.assertRaises(ValidationError):
            validate_file_path(self.root / "missing.txt", self.root)

    def test_sha256_matches_standard_library(self):
        actual = calculate_sha256(self.sample, self.root)
        expected = hashlib.sha256(self.sample.read_bytes()).hexdigest()
        self.assertEqual(actual, expected)

    def test_hash_verification(self):
        digest = hashlib.sha256(self.sample.read_bytes()).hexdigest()
        self.assertTrue(verify_sha256(digest, digest))
        self.assertFalse(verify_sha256(digest, "0" * 64))

    def test_reject_malformed_hash(self):
        with self.assertRaises(ValidationError):
            verify_sha256("invalid", "0" * 64)


if __name__ == "__main__":
    unittest.main()
