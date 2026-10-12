"""Bounded plain-text extraction for ScamShield DataForge."""

from ..config import MAX_DOWNLOAD_BYTES, MAX_TEXT_LENGTH
from ..exceptions import ExtractionError, ValidationError


def extract_text_lines(
    content,
    max_bytes=MAX_DOWNLOAD_BYTES,
    max_line_length=MAX_TEXT_LENGTH,
):
    """Convert UTF-8 text into numbered, non-empty records.

    Blank lines are ignored. Original text content is not silently truncated.
    """
    if isinstance(content, bytes):
        raw = content
    elif isinstance(content, str):
        raw = content.encode("utf-8")
    else:
        raise ValidationError("Text content must be str or bytes.")

    if max_bytes < 1 or max_line_length < 1:
        raise ValidationError("Text extraction limits must be positive.")

    if len(raw) > max_bytes:
        raise ExtractionError("Text content exceeds the permitted size.")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError("Text content must use UTF-8 encoding.") from exc

    records = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        cleaned = line.strip()

        if not cleaned:
            continue

        if len(cleaned) > max_line_length:
            raise ExtractionError(
                f"Line {line_number} exceeds the permitted text length."
            )

        records.append({
            "line_number": line_number,
            "text": cleaned,
        })

    return records