
"""Record validation for ScamShield DataForge."""

import re
from datetime import datetime

from ..config import MAX_TEXT_LENGTH
from ..constants import DATA_REAL, DATA_SYNTHETIC, LABEL_HAM, LABEL_SPAM
from ..exceptions import ValidationError


REQUIRED_FIELDS = frozenset({
    "record_id",
    "text",
    "label",
    "source_id",
    "data_type",
})

OPTIONAL_FIELDS = frozenset({
    "language",
    "collected_at",
    "content_sha256",
})

ALLOWED_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
ALLOWED_LABELS = frozenset({LABEL_HAM, LABEL_SPAM})
ALLOWED_DATA_TYPES = frozenset({DATA_REAL, DATA_SYNTHETIC})
SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def _is_timezone_aware_datetime(value: object) -> bool:
    """Return True only for a valid timezone-aware ISO-8601 datetime."""
    if not isinstance(value, str) or not value.strip():
        return False

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False

    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def validate_record(record: object) -> dict:
    """Validate one dataset record and return a shallow copy.

    Raises:
        ValidationError: If the record violates DataForge's record contract.

    This function does not modify the input record or verify that its source
    has legal permission to be used.
    """
    if not isinstance(record, dict):
        raise ValidationError("Dataset record must be a dictionary.")

    missing = REQUIRED_FIELDS - record.keys()
    if missing:
        raise ValidationError(
            "Dataset record is missing required fields: "
            + ", ".join(sorted(missing))
        )

    extra = record.keys() - ALLOWED_FIELDS
    if extra:
        raise ValidationError(
            "Dataset record contains unsupported fields: "
            + ", ".join(sorted(str(field) for field in extra))
        )

    record_id = record["record_id"]
    if (
        not isinstance(record_id, str)
        or not record_id.strip()
        or len(record_id) > 128
    ):
        raise ValidationError(
            "record_id must be a non-empty string of at most 128 characters."
        )

    text = record["text"]
    if (
        not isinstance(text, str)
        or not text.strip()
        or len(text) > MAX_TEXT_LENGTH
    ):
        raise ValidationError(
            f"text must be non-empty and at most {MAX_TEXT_LENGTH} characters."
        )

    label = record["label"]
    if not isinstance(label, str) or label not in ALLOWED_LABELS:
        raise ValidationError("label must be either 'ham' or 'spam'.")

    source_id = record["source_id"]
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or len(source_id) > 128
    ):
        raise ValidationError(
            "source_id must be a non-empty string of at most 128 characters."
        )

    data_type = record["data_type"]
    if not isinstance(data_type, str) or data_type not in ALLOWED_DATA_TYPES:
        raise ValidationError("data_type must be 'REAL' or 'SYNTHETIC'.")

    if "language" in record:
        language = record["language"]
        if language is not None and (
            not isinstance(language, str) or len(language) > 32
        ):
            raise ValidationError(
                "language must be null or a string of at most 32 characters."
            )

    if "collected_at" in record:
        collected_at = record["collected_at"]
        if collected_at is not None and not _is_timezone_aware_datetime(
            collected_at
        ):
            raise ValidationError(
                "collected_at must be null or a timezone-aware ISO-8601 datetime."
            )

    if "content_sha256" in record:
        content_sha256 = record["content_sha256"]
        if content_sha256 is not None and (
            not isinstance(content_sha256, str)
            or SHA256_PATTERN.fullmatch(content_sha256) is None
        ):
            raise ValidationError(
                "content_sha256 must be null or a 64-character hexadecimal SHA-256."
            )

    return dict(record)


def validate_records(records: object) -> dict:
    """Validate a batch and report accepted and rejected records.

    Invalid records are reported individually. The function does not write
    files, mutate the input, or silently discard rejected records.
    """
    if not isinstance(records, (list, tuple)):
        raise ValidationError("records must be a list or tuple.")

    valid_records = []
    rejected_records = []

    for index, record in enumerate(records):
        try:
            valid_records.append(validate_record(record))
        except ValidationError as exc:
            rejected_records.append({
                "index": index,
                "error": str(exc),
                "record": record,
            })

    return {
        "input_count": len(records),
        "valid_records": valid_records,
        "rejected_records": rejected_records,
        "valid_count": len(valid_records),
        "rejected_count": len(rejected_records),
    }
