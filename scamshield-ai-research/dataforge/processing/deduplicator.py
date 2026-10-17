
"""Deterministic, auditable dataset deduplication."""

from ..exceptions import ValidationError
from .label_conflicts import find_label_conflicts
from .normalizer import normalize_record
from .validator import validate_records


def deduplicate_records(records: object) -> dict:
    """Deduplicate equivalent text without concealing label conflicts.

    Policy:
    - Invalid records are reported as rejected.
    - Text is normalized before comparison.
    - If equivalent text has multiple labels, retain every record.
    - Otherwise, retain the first record and report later duplicates.
    - Input order is preserved; no source record is mutated.

    The returned records contain normalized text. This function performs no
    file writes and does not change the original dataset or model.
    """
    validation = validate_records(records)

    normalized_records = [
        normalize_record(record)
        for record in validation["valid_records"]
    ]

    conflicts = find_label_conflicts(normalized_records)

    conflicting_texts = {
        conflict["normalized_text"]
        for conflict in conflicts
    }

    retained_records = []
    duplicate_records = []
    first_record_by_text = {}

    for record in normalized_records:
        normalized_text = record["text"]

        # Conflicting groups are preserved in full for human review.
        if normalized_text in conflicting_texts:
            retained_records.append(record)
            continue

        if normalized_text not in first_record_by_text:
            first_record_by_text[normalized_text] = record
            retained_records.append(record)
            continue

        first_record = first_record_by_text[normalized_text]
        duplicate_records.append({
            "record": record,
            "duplicate_of": first_record["record_id"],
            "reason": "same_normalized_text_and_label",
        })

    return {
        "input_count": validation["input_count"],
        "valid_count": validation["valid_count"],
        "rejected_count": validation["rejected_count"],
        "retained_count": len(retained_records),
        "duplicate_count": len(duplicate_records),
        "conflict_count": len(conflicts),
        "records": retained_records,
        "duplicates": duplicate_records,
        "conflicts": conflicts,
        "rejected": validation["rejected_records"],
    }
