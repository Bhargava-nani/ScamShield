"""Metrics for binary ham/spam classification."""

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)


def calculate_classification_metrics(y_true, y_pred):
    """Return JSON-compatible binary and per-class evaluation metrics."""
    labels = ["ham", "spam"]

    if len(y_true) == 0 or len(y_true) != len(y_pred):
        raise ValueError("True and predicted labels must be non-empty and equal in length.")

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        zero_division=0,
    )

    spam_precision, spam_recall, spam_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        average="binary",
        pos_label="spam",
        zero_division=0,
    )

    matrix = confusion_matrix(y_true, y_pred, labels=labels)

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "spam_precision": float(spam_precision),
        "spam_recall": float(spam_recall),
        "spam_f1": float(spam_f1),
        "confusion_matrix": {
            "labels": labels,
            "rows_actual_columns_predicted": matrix.tolist(),
        },
        "per_class": {
            label: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index, label in enumerate(labels)
        },
        "evaluated_records": len(y_true),
    }
