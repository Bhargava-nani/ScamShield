"""High-level safe file operations for DataForge."""

from ..exceptions import ValidationError
from .file_security import calculate_sha256, validate_file_path


def validate_input_file(
    candidate,
    allowed_root,
    allowed_extensions,
    max_bytes,
):
    """Validate a permitted input file before parsing or processing."""
    if allowed_extensions is None:
        raise ValidationError("Allowed file extensions must be specified.")

    if not isinstance(allowed_extensions, (set, frozenset, list, tuple)):
        raise ValidationError("Allowed extensions must be a collection.")

    return validate_file_path(
        candidate=candidate,
        allowed_root=allowed_root,
        max_bytes=max_bytes,
        allowed_extensions=allowed_extensions,
    )


def fingerprint_file(candidate, allowed_root, max_bytes):
    """Return a validated file path and its SHA-256 fingerprint."""
    path = validate_file_path(
        candidate=candidate,
        allowed_root=allowed_root,
        max_bytes=max_bytes,
    )

    digest = calculate_sha256(
        candidate=path,
        allowed_root=allowed_root,
        max_bytes=max_bytes,
    )

    return {
        "path": str(path),
        "sha256": digest,
        "size_bytes": path.stat().st_size,
    }