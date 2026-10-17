
"""Transparent quality reporting for DataForge processing results."""

from collections import Counter

from ..exceptions import ValidationError


def build_quality_report(result: object) -> dict:
    """Build a deterministic summary from a deduplication result.

    Counts are derived from the actual result lists rather than trusting
    caller-supplied count fields. This function does not modify its input.
    """
    if not isinstance(result, dict):
        raise ValidationError("Deduplication result must be a dictionary.")

    required_lists = ("records", "duplicates", "conflicts", "rejected")
    for field in required_lists:
        if not isinstance(result.get(field), list):
            raise ValidationError(
                f"Deduplication result field '{field}' must be a list."
            )

    records = result["records"]
    duplicates = result["duplicates"]
    conflicts = result["conflicts"]
    rejected = result["rejected"]

    label_counts = Counter()
    data_type_counts = Counter()

    for record in records:
        if not isinstance(record, dict):
            raise ValidationError("Retained records must contain dictionaries.")

        label = record.get("label")
        data_type = record.get("data_type")

        if isinstance(label, str):
            label_counts[label] += 1

        if isinstance(data_type, str):
            data_type_counts[data_type] += 1

    conflict_record_count = 0
    for conflict in conflicts:
        if not isinstance(conflict, dict):
            raise ValidationError("Conflict entries must be dictionaries.")

        conflict_records = conflict.get("records")
        if not isinstance(conflict_records, list):
            raise ValidationError("Each conflict must contain a records list.")

        conflict_record_count += len(conflict_records)

    input_count = (
        len(records) + len(duplicates) + len(rejected)
    )

    # Conflict records are retained in records, so do not add them again.
    valid_count = len(records) + len(duplicates)

    return {
        "input_count": input_count,
        "valid_count": valid_count,
        "rejected_count": len(rejected),
        "retained_count": len(records),
        "duplicate_count": len(duplicates),
        "conflict_group_count": len(conflicts),
        "conflict_record_count": conflict_record_count,
        "label_counts": dict(sorted(label_counts.items())),
        "data_type_counts": dict(sorted(data_type_counts.items())),
        "requires_review": bool(rejected or conflicts),
        "review_reasons": [
            reason
            for condition, reason in (
                (bool(rejected), "INVALID_RECORDS"),
                (bool(conflicts), "CONFLICTING_LABELS"),
            )
            if condition
        ],
    }
