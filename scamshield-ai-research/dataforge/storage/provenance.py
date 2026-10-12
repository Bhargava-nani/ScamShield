"""Strict provenance verification for DataForge manifests and artifacts."""

from ..exceptions import ProvenanceError, ValidationError
from .integrity import hashes_match
from .manifest import (
    APPROVED_LICENSE_STATUSES,
    validate_manifest_structure,
)


def verify_manifest(manifest, actual_sha256=None, actual_size=None):
    """Verify that a manifest is structurally valid and approved for trust.

    If actual_sha256 or actual_size is supplied, it must match the recorded
    artifact metadata. This function does not independently prove legal
    permission or replace network-time SSRF/redirect protections.
    """
    validate_manifest_structure(manifest)

    if manifest["permission_confirmed"] is not True:
        raise ProvenanceError("Source permission is not confirmed.")

    if manifest["approval_status"] != "VALIDATED":
        raise ProvenanceError("Source manifest has not been validated.")

    license_status = manifest["license_status"].strip().lower()
    if license_status not in APPROVED_LICENSE_STATUSES:
        raise ProvenanceError("Source license or permission status is not approved.")

    if "data_type" not in manifest:
        raise ProvenanceError("Manifest data_type is required for verification.")

    recorded_hash = manifest.get("retrieved_sha256")
    if not isinstance(recorded_hash, str):
        raise ProvenanceError("Manifest is missing its retrieved SHA-256 digest.")

    recorded_size = manifest.get("retrieved_bytes")
    if (
        not isinstance(recorded_size, int)
        or isinstance(recorded_size, bool)
        or recorded_size < 0
    ):
        raise ProvenanceError("Manifest is missing a valid retrieved byte count.")

    if actual_sha256 is not None:
        if not hashes_match(recorded_hash, actual_sha256):
            raise ProvenanceError(
                "Stored content does not match its manifest hash."
            )

    if actual_size is not None:
        if (
            not isinstance(actual_size, int)
            or isinstance(actual_size, bool)
            or actual_size < 0
        ):
            raise ValidationError("Actual artifact size must be a non-negative integer.")

        if recorded_size != actual_size:
            raise ProvenanceError(
                "Stored content size does not match its manifest."
            )

    return True