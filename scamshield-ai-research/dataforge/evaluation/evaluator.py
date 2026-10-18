"""Evaluate a fitted classifier against records kept out of training."""

from dataforge.evaluation.metrics import calculate_classification_metrics


def evaluate_model(model, records):
    if not records:
        raise ValueError("Cannot evaluate a model on an empty dataset.")

    texts = [record["text"] for record in records]
    actual = [record["label"] for record in records]
    predicted = model.predict(texts).tolist()

    return calculate_classification_metrics(actual, predicted)
