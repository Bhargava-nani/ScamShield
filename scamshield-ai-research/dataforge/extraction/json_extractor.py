"""Bounded JSON record extraction for ScamShield DataForge."""

import json

from ..config import MAX_DOWNLOAD_BYTES
from ..exceptions import ExtractionError, ValidationError


def _decode_json_content(content, max_bytes):
    """Decode JSON content while enforcing a byte limit."""
    if isinstance(content, bytes):
        raw = content
    elif isinstance(content, str):
        raw = content.encode("utf-8")
    else:
        raise ValidationError("JSON content must be str or bytes.")

    if max_bytes < 1:
        raise ValidationError("max_bytes must be positive.")

    if len(raw) > max_bytes:
        raise ExtractionError("JSON content exceeds the permitted size.")

    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError("JSON content must use UTF-8 encoding.") from exc


def extract_json_records(content, max_bytes=MAX_DOWNLOAD_BYTES):
    """Extract JSON objects as a list of dictionary records.

    Accepts a single JSON object or a JSON array of objects.
    Does not read files or perform network requests.
    """
    text = _decode_json_content(content, max_bytes)

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ExtractionError("JSON content is malformed or too deeply nested.") from exc

    if isinstance(parsed, dict):
        records = [parsed]
    elif isinstance(parsed, list):
        records = parsed
    else:
        raise ExtractionError(
            "JSON must contain an object or an array of objects."
        )

    if not all(isinstance(record, dict) for record in records):
        raise ExtractionError("Every JSON record must be an object.")

    return records