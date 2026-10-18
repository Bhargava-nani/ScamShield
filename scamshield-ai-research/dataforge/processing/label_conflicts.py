
"""Detection of conflicting labels for equivalent message text."""

from ..exceptions import ValidationError
from .normalizer import normalize_text
from .validator import validate_record


def find_label_conflicts(records: object) -> list[dict]:
    """Find normalized message groups containing different labels.

    Records in a conflict group are reported, not deleted or relabeled.
    Group order follows the first appearance of each conflicting message.
    Record order within each group follows the input order.
    """
    if not isinstance(records, (list, tuple)):
        raise ValidationError("records must be a list or tuple.")

    groups = {}

    for index, candidate in enumerate(records):
        record = validate_record(candidate)
        normalized_text = normalize_text(record["text"])

        if normalized_text not in groups:
            groups[normalized_text] = {
                "first_index": index,
                "records": [],
                "labels": set(),
            }

        groups[normalized_text]["records"].append({
            "index": index,
            "record": record,
        })
        groups[normalized_text]["labels"].add(record["label"])

    conflicts = []

    for normalized_text, group in groups.items():
        if len(group["labels"]) < 2:
            continue

        conflicts.append({
            "normalized_text": normalized_text,
            "labels": sorted(group["labels"]),
            "records": group["records"],
        })

    return conflicts
