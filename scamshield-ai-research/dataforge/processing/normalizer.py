
"""Deterministic text normalization for DataForge dataset records."""

import unicodedata

from ..exceptions import ValidationError


MAX_TEXT_LENGTH = 100_000


def normalize_text(text: str) -> str:
    """Normalize text deterministically without changing its meaning intentionally.

    Applies Unicode NFC normalization, converts line endings to LF, replaces
    non-breaking spaces with ordinary spaces, and collapses consecutive
    whitespace. It does not lowercase text, remove punctuation, or alter labels.
    """
    if not isinstance(text, str):
        raise ValidationError("Text must be a string.")

    if not text:
        raise ValidationError("Text must not be empty.")

    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(
            f"Text exceeds the maximum length of {MAX_TEXT_LENGTH} characters."
        )

    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00a0", " ")
    normalized = " ".join(normalized.split())

    if not normalized:
        raise ValidationError("Text must contain non-whitespace characters.")

    return normalized


def normalize_record(record: dict) -> dict:
    """Return a normalized copy of a dataset record.

    Only the text field is changed. The original mapping and all other fields
    are preserved. Missing or invalid text is rejected.
    """
    if not isinstance(record, dict):
        raise ValidationError("Record must be a dictionary.")

    if "text" not in record:
        raise ValidationError("Record is missing the required text field.")

    normalized_record = record.copy()
    normalized_record["text"] = normalize_text(record["text"])
    return normalized_record
