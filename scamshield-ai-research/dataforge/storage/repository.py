"""JSON Lines repository for validated dataset records.

The repository validates records before committing them and uses atomic
replacement to avoid leaving a partially written JSONL file after a failure.

Note:
Atomic replacement does not provide cross-process locking. Concurrent writers
must be serialized by a higher-level coordinator.
"""

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from ..config import MAX_TEXT_LENGTH, PROCESSED_DATA_DIR
from ..exceptions import (
    DuplicateConflictError,
    StorageError,
    ValidationError,
)


ALLOWED_LABELS = {"ham", "spam"}
ALLOWED_DATA_TYPES = {"REAL", "SYNTHETIC"}

REQUIRED_FIELDS = {
    "record_id",
    "text",
    "label",
    "source_id",
    "data_type",
}

OPTIONAL_FIELDS = {
    "language",
    "collected_at",
    "content_sha256",
}

ALLOWED_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def _validate_datetime(value):
    """Return whether value is a timezone-aware ISO-8601 datetime."""
    if not isinstance(value, str) or not value.strip():
        return False

    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False

    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _validate_record(record):
    """Validate a record against the dataset-record schema's constraints."""
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
        if collected_at is not None and not _validate_datetime(collected_at):
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

    # Return a shallow copy so callers' dictionaries are not modified.
    return dict(record)


class DatasetRepository:
    """Persist validated records as JSON Lines with conflict detection."""

    def __init__(self, path=None):
        self.path = Path(
            path if path is not None else PROCESSED_DATA_DIR / "dataset.jsonl"
        ).resolve()

    def load_records(self):
        """Load and validate records, rejecting malformed or conflicting data."""
        if not self.path.exists():
            return []

        records = []
        seen = {}

        try:
            with self.path.open("r", encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    if not line.strip():
                        continue

                    try:
                        decoded = json.loads(line)
                        record = _validate_record(decoded)
                    except (json.JSONDecodeError, ValidationError) as exc:
                        raise StorageError(
                            f"Invalid dataset record at line {line_number}."
                        ) from exc

                    record_id = record["record_id"]

                    if record_id in seen:
                        if seen[record_id] != record:
                            raise DuplicateConflictError(
                                f"Conflicting record_id at line {line_number}."
                            )

                        # Repeated identical records do not create duplicates.
                        continue

                    seen[record_id] = record
                    records.append(record)

        except (OSError, UnicodeError) as exc:
            raise StorageError(
                "Unable to read dataset repository."
            ) from exc

        return records

    def add_records(self, incoming_records):
        """Add records idempotently; abort without writing on any conflict."""
        if not isinstance(incoming_records, (list, tuple)):
            raise ValidationError("incoming_records must be a list or tuple.")

        current = self.load_records()
        by_id = {record["record_id"]: record for record in current}
        added = 0

        # Validate the entire incoming batch before writing anything.
        for incoming in incoming_records:
            record = _validate_record(incoming)
            record_id = record["record_id"]

            if record_id in by_id:
                if by_id[record_id] != record:
                    raise DuplicateConflictError(
                        f"Record ID '{record_id}' already exists "
                        "with different content."
                    )
                continue

            by_id[record_id] = record
            current.append(record)
            added += 1

        # An empty or fully idempotent batch needs no disk write.
        if added == 0:
            return {
                "total_records": len(current),
                "added_records": 0,
            }

        temporary_name = None

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.path.parent,
                prefix=".dataset-",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temporary_name = temp_file.name

                for record in current:
                    serialized = json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        allow_nan=False,
                        separators=(",", ":"),
                    )
                    temp_file.write(serialized + "\n")

                temp_file.flush()
                os.fsync(temp_file.fileno())

            os.replace(temporary_name, self.path)
            temporary_name = None

        except (OSError, ValueError, TypeError) as exc:
            raise StorageError("Unable to commit dataset records.") from exc

        finally:
            if temporary_name is not None:
                try:
                    Path(temporary_name).unlink(missing_ok=True)
                except OSError:
                    # Preserve the original storage error.
                    pass

        return {
            "total_records": len(current),
            "added_records": added,
        }