
"""Integrity helpers for stored DataForge artifacts."""

import hashlib
import hmac
from pathlib import Path

from ..exceptions import StorageError, ValidationError


def sha256_bytes(content):
    """Return the SHA-256 digest of bytes."""
    if not isinstance(content, bytes):
        raise ValidationError("Content must be bytes.")
    return hashlib.sha256(content).hexdigest()


def sha256_file(path, chunk_size=1024 * 1024):
    """Hash a file incrementally without loading it all into memory."""
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ValidationError("chunk_size must be a positive integer.")

    digest = hashlib.sha256()

    try:
        with Path(path).open("rb") as file:
            while chunk := file.read(chunk_size):
                digest.update(chunk)
    except OSError as exc:
        raise StorageError("Unable to calculate file hash.") from exc

    return digest.hexdigest()


def hashes_match(actual, expected):
    """Compare valid SHA-256 hexadecimal digests."""
    if not isinstance(actual, str) or not isinstance(expected, str):
        raise ValidationError("Hashes must be strings.")

    if len(actual) != 64 or len(expected) != 64:
        raise ValidationError("SHA-256 hashes must contain 64 hexadecimal characters.")

    try:
        bytes.fromhex(actual)
        bytes.fromhex(expected)
    except ValueError as exc:
        raise ValidationError("Hash contains invalid hexadecimal characters.") from exc

    return hmac.compare_digest(actual.lower(), expected.lower())
