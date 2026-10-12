
"""Manifest creation, structural validation, and JSON serialization."""

import json
import re
from datetime import datetime, timezone

from ..exceptions import (
    ProvenanceError,
    SecurityViolationError,
    ValidationError,
)
from ..security.url_safety import validate_url


APPROVED_LICENSE_STATUSES = {
    "approved",
    "public_domain",
    "permission_granted",
}

APPROVAL_STATUSES = {
    "PENDING",
    "VALIDATED",
    "REJECTED",
    "QUARANTINED",
}

DATA_TYPES = {"REAL", "SYNTHETIC"}

REQUIRED_FIELDS = {
    "source_id",
    "source_url",
    "permission_confirmed",
    "license_status",
    "approval_status",
    "retrieved_at",
}

OPTIONAL_FIELDS = {
    "provider",
    "retrieved_sha256",
    "retrieved_bytes",
    "data_type",
    "processing_history",
}

ALLOWED_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def _is_timezone_aware_datetime(value):
    if not isinstance(value, str) or not value.strip():
        return False

    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False

    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def validate_manifest_structure(manifest):
    """Validate a manifest against the supported schema constraints.

    This validates structure and basic URL safety. It does not prove that a
    source owner granted permission or that a license claim is truthful.
    """
    if not isinstance(manifest, dict):
        raise ProvenanceError("Manifest must be a JSON object.")

    missing = REQUIRED_FIELDS - manifest.keys()
    if missing:
        raise ProvenanceError(
            "Manifest is missing required fields: "
            + ", ".join(sorted(missing))
        )

    extra = manifest.keys() - ALLOWED_FIELDS
    if extra:
        raise ProvenanceError(
            "Manifest contains unsupported fields: "
            + ", ".join(sorted(str(field) for field in extra))
        )

    source_id = manifest["source_id"]
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or len(source_id) > 128
    ):
        raise ProvenanceError(
            "source_id must be a non-empty string of at most 128 characters."
        )

    source_url = manifest["source_url"]
    if not isinstance(source_url, str) or not source_url.strip():
        raise ProvenanceError("source_url must be a non-empty URL.")

    try:
        validate_url(source_url, require_https=True)
    except (
        ValidationError,
        ProvenanceError,
        SecurityViolationError,
    ) as exc:
        raise ProvenanceError("Manifest source_url is not permitted.") from exc

    permission = manifest["permission_confirmed"]
    if not isinstance(permission, bool):
        raise ProvenanceError("permission_confirmed must be a boolean.")

    license_status = manifest["license_status"]
    if (
        not isinstance(license_status, str)
        or not license_status.strip()
        or len(license_status) > 128
    ):
        raise ProvenanceError(
            "license_status must be a non-empty string of at most 128 characters."
        )

    approval_status = manifest["approval_status"]
    if (
        not isinstance(approval_status, str)
        or approval_status not in APPROVAL_STATUSES
    ):
        raise ProvenanceError("Manifest approval_status is invalid.")

    if not _is_timezone_aware_datetime(manifest["retrieved_at"]):
        raise ProvenanceError(
            "retrieved_at must be a timezone-aware ISO-8601 datetime."
        )

    if "provider" in manifest:
        provider = manifest["provider"]
        if provider is not None and (
            not isinstance(provider, str) or len(provider) > 256
        ):
            raise ProvenanceError(
                "provider must be null or a string of at most 256 characters."
            )

    if "retrieved_sha256" in manifest:
        digest = manifest["retrieved_sha256"]
        if digest is not None and (
            not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
        ):
            raise ProvenanceError("retrieved_sha256 is malformed.")

    if "retrieved_bytes" in manifest:
        size = manifest["retrieved_bytes"]
        if size is not None and (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            raise ProvenanceError("retrieved_bytes must be null or non-negative.")

    if "data_type" in manifest:
        data_type = manifest["data_type"]
        if not isinstance(data_type, str) or data_type not in DATA_TYPES:
            raise ProvenanceError("Manifest data_type is invalid.")

    if "processing_history" in manifest:
        history = manifest["processing_history"]

        if not isinstance(history, list):
            raise ProvenanceError("processing_history must be a list.")

        for index, entry in enumerate(history):
            if not isinstance(entry, dict):
                raise ProvenanceError(
                    f"Processing history entry {index} must be an object."
                )

            if set(entry) - {"operation", "timestamp", "details"}:
                raise ProvenanceError(
                    f"Processing history entry {index} has unsupported fields."
                )

            operation = entry.get("operation")
            if not isinstance(operation, str) or not operation.strip():
                raise ProvenanceError(
                    f"Processing history entry {index} needs an operation."
                )

            if not _is_timezone_aware_datetime(entry.get("timestamp")):
                raise ProvenanceError(
                    f"Processing history entry {index} has an invalid timestamp."
                )

            if "details" in entry and not isinstance(entry["details"], dict):
                raise ProvenanceError(
                    f"Processing history entry {index} details must be an object."
                )

    return True


def create_manifest(
    source_id,
    source_url,
    sha256,
    size_bytes,
    license_status,
    permission_confirmed,
    data_type="REAL",
):
    """Create a validated provenance manifest for an approved source."""
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or len(source_id.strip()) > 128
    ):
        raise ValidationError(
            "source_id must be a non-empty string of at most 128 characters."
        )

    if not isinstance(source_url, str) or not source_url.strip():
        raise ValidationError("source_url is required.")

    try:
        safe_url = validate_url(source_url.strip(), require_https=True)
    except (
        ValidationError,
        ProvenanceError,
        SecurityViolationError,
    ) as exc:
        raise ProvenanceError("Source URL is not permitted.") from exc

    if (
        not isinstance(sha256, str)
        or SHA256_PATTERN.fullmatch(sha256) is None
    ):
        raise ValidationError("A valid SHA-256 digest is required.")

    if (
        not isinstance(size_bytes, int)
        or isinstance(size_bytes, bool)
        or size_bytes < 0
    ):
        raise ValidationError("size_bytes must be a non-negative integer.")

    if permission_confirmed is not True:
        raise ProvenanceError("Source permission must be confirmed.")

    if not isinstance(license_status, str):
        raise ProvenanceError("A documented approved license status is required.")

    normalized_license = license_status.strip().lower()
    if normalized_license not in APPROVED_LICENSE_STATUSES:
        raise ProvenanceError("Source license or permission status is not approved.")

    if not isinstance(data_type, str) or data_type not in DATA_TYPES:
        raise ValidationError("data_type must be REAL or SYNTHETIC.")

    manifest = {
        "source_id": source_id.strip(),
        "source_url": safe_url,
        "permission_confirmed": True,
        "license_status": normalized_license,
        "approval_status": "VALIDATED",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "retrieved_sha256": sha256.lower(),
        "retrieved_bytes": size_bytes,
        "data_type": data_type,
        "processing_history": [],
    }

    validate_manifest_structure(manifest)
    return manifest


def serialize_manifest(manifest):
    """Validate and serialize a manifest deterministically."""
    validate_manifest_structure(manifest)

    try:
        return json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValidationError("Manifest contains unsupported values.") from exc


def _reject_duplicate_keys(pairs):
    """Prevent ambiguous JSON objects containing duplicate property names."""
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key.")
        result[key] = value

    return result


def parse_manifest(content):
    """Parse and structurally validate JSON manifest content."""
    if not isinstance(content, (str, bytes, bytearray)):
        raise ProvenanceError("Manifest content must be JSON text or bytes.")

    try:
        manifest = json.loads(
            content,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ProvenanceError("Manifest JSON is invalid.") from exc

    validate_manifest_structure(manifest)
    return manifest
