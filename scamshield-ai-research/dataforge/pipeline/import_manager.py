"""Controlled local import of records with verified provenance.

No downloads, external-code execution, model training, or model promotion.
"""

import hashlib

from ..collection.source_validator import validate_source
from ..exceptions import ValidationError
from ..processing.deduplicator import deduplicate_records
from ..processing.quality_report import build_quality_report
from ..storage.provenance import verify_manifest


def import_local_records(
    *,
    artifact_bytes,
    records,
    manifest,
    approved_domains,
    repository,
):
    """Verify provenance, validate records, and import an approved batch."""
    if not isinstance(artifact_bytes, bytes):
        raise ValidationError("artifact_bytes must be bytes.")

    if not isinstance(records, list) or not records:
        raise ValidationError("records must be a non-empty list.")

    if not isinstance(manifest, dict):
        raise ValidationError("manifest must be a dictionary.")

    if repository is None or not callable(
        getattr(repository, "add_records", None)
    ):
        raise ValidationError(
            "repository must provide an add_records method."
        )

    digest = hashlib.sha256(artifact_bytes).hexdigest()

    # Check the manifest's approval, licensing, hash and artifact size.
    verify_manifest(
        manifest,
        actual_sha256=digest,
        actual_size=len(artifact_bytes),
    )

    # Apply the explicit domain allowlist and source policy.
    source = validate_source(
        {
            "source_id": manifest["source_id"],
            "source_url": manifest["source_url"],
            "permission_confirmed": manifest["permission_confirmed"],
            "license_status": manifest["license_status"],
            "provider": manifest.get("provider"),
            "data_type": manifest.get("data_type"),
        },
        approved_domains=approved_domains,
    )

    if source["approval_status"] != "VALIDATED":
        raise ValidationError("Source has not passed source approval.")

    if (
        source["source_id"] != manifest["source_id"]
        or source["source_url"] != manifest["source_url"]
        or source["data_type"] != manifest["data_type"]
    ):
        raise ValidationError(
            "Validated source metadata does not match the manifest."
        )

    # Do not allow records to be attributed to a different source or type.
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValidationError(
                f"Record at index {index} must be a dictionary."
            )

        if record.get("source_id") != manifest["source_id"]:
            raise ValidationError(
                f"Record at index {index} has a mismatched source_id."
            )

        if record.get("data_type") != manifest["data_type"]:
            raise ValidationError(
                f"Record at index {index} has a mismatched data_type."
            )

    deduplication = deduplicate_records(records)
    quality = build_quality_report(deduplication)

    report = {
        "status": "REVIEW_REQUIRED",
        "artifact_sha256": digest,
        "artifact_size_bytes": len(artifact_bytes),
        "source_id": manifest["source_id"],
        "input_count": quality["input_count"],
        "valid_count": quality["valid_count"],
        "retained_count": quality["retained_count"],
        "duplicate_count": quality["duplicate_count"],
        "conflict_group_count": quality["conflict_group_count"],
        "conflict_record_count": quality["conflict_record_count"],
        "rejected_count": quality["rejected_count"],
        "requires_review": quality["requires_review"],
        "review_reasons": quality["review_reasons"],
        "persisted": False,
        "storage_result": None,
    }

    # Reject the entire batch from persistence if review is needed.
    if quality["requires_review"]:
        return report

    storage_result = repository.add_records(deduplication["records"])

    report["status"] = "IMPORTED"
    report["persisted"] = True
    report["storage_result"] = storage_result
    return report