
"""Safe file validation and integrity utilities for ScamShield DataForge."""

import hashlib
import hmac
import re
from pathlib import Path

from ..config import MAX_DOWNLOAD_BYTES
from ..exceptions import SecurityViolationError, ValidationError


def validate_file_path(
    candidate,
    allowed_root,
    max_bytes=MAX_DOWNLOAD_BYTES,
    allowed_extensions=None,
):
    """Validate a file's location, type, and size before processing."""
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 0:
        raise ValidationError("max_bytes must be a non-negative integer.")

    try:
        root = Path(allowed_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValidationError("Allowed root does not exist or cannot be accessed.") from exc

    if not root.is_dir():
        raise ValidationError("Allowed root must be a directory.")

    path = Path(candidate)

    if path.is_symlink():
        raise SecurityViolationError("Symbolic links are not allowed.")

    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise ValidationError("File does not exist or cannot be accessed.") from exc

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SecurityViolationError(
            "File is outside the permitted directory."
        ) from exc

    if not resolved.is_file():
        raise ValidationError("The supplied path is not a regular file.")

    if allowed_extensions is not None:
        allowed = {
            str(ext).lower() if str(ext).startswith(".")
            else f".{str(ext).lower()}"
            for ext in allowed_extensions
        }
        if resolved.suffix.lower() not in allowed:
            raise ValidationError("File extension is not permitted.")

    try:
        file_size = resolved.stat().st_size
    except OSError as exc:
        raise ValidationError("Unable to determine file size.") from exc

    if file_size > max_bytes:
        raise SecurityViolationError("File exceeds the permitted size.")

    return resolved


def calculate_sha256(
    candidate,
    allowed_root,
    max_bytes=MAX_DOWNLOAD_BYTES,
    chunk_size=1024 * 1024,
):
    """Calculate SHA-256 without loading the entire file into memory."""
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")

    path = validate_file_path(
        candidate,
        allowed_root,
        max_bytes=max_bytes,
    )

    digest = hashlib.sha256()

    try:
        with path.open("rb") as file:
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as exc:
        raise ValidationError("Unable to read file for SHA-256 calculation.") from exc

    return digest.hexdigest()


def verify_sha256(actual_hash, expected_hash):
    """Compare two SHA-256 hashes after validating their format."""
    pattern = re.compile(r"^[a-fA-F0-9]{64}$")

    if not isinstance(actual_hash, str) or not isinstance(expected_hash, str):
        raise ValidationError("Hashes must be strings.")

    if not pattern.fullmatch(actual_hash):
        raise ValidationError("Actual SHA-256 hash is malformed.")

    if not pattern.fullmatch(expected_hash):
        raise ValidationError("Expected SHA-256 hash is malformed.")

    return hmac.compare_digest(
        actual_hash.lower(),
        expected_hash.lower(),
    )
