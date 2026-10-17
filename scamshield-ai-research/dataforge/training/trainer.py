"""Train and save a reviewed, non-promoted candidate classifier."""

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from dataforge.datasets.split_manager import split_dataset
from dataforge.evaluation.evaluator import evaluate_model
from dataforge.exceptions import ValidationError
from dataforge.processing.deduplicator import deduplicate_records
from dataforge.training.training_config import (
    DEFAULT_RANDOM_SEED,
    EXPECTED_LABELS,
    MAX_FEATURES,
    MAX_ITERATIONS,
    MINIMUM_RECORDS,
    MODEL_NAME,
    MODEL_VERSION,
)


def _atomic_json_write(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_model_write(model, path):
    fd, temporary_name = tempfile.mkstemp(
        prefix="candidate_",
        suffix=".tmp",
        dir=str(path.parent),
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        joblib.dump(model, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def train_candidate(records, output_dir=None, seed=DEFAULT_RANDOM_SEED):
    """Train, evaluate, and save a candidate without promoting it.

    `records` must contain validated DataForge records. The test split is
    not used to fit the vectorizer or classifier.
    """
    if not isinstance(records, (list, tuple)):
        raise ValidationError("Records must be supplied as a list or tuple.")

    if output_dir is None:
        output_dir = Path(__file__).resolve().parents[2] / "data" / "candidates"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dedup = deduplicate_records(list(records))
    clean_records = dedup.get("records", [])
    rejected = dedup.get("rejected", [])
    conflicts = dedup.get("conflicts", [])

    if rejected:
        raise ValidationError(
            f"Training blocked: {len(rejected)} invalid record(s) were rejected."
        )
    if conflicts:
        raise ValidationError(
            f"Training blocked: {len(conflicts)} conflicting duplicate group(s) need review."
        )

    if len(clean_records) < MINIMUM_RECORDS:
        raise ValidationError(
            f"Training requires at least {MINIMUM_RECORDS} unique valid records; "
            f"received {len(clean_records)}."
        )

    labels = {record.get("label") for record in clean_records}
    if not set(EXPECTED_LABELS).issubset(labels):
        raise ValidationError("Training requires examples of both ham and spam.")

    split_result = split_dataset(clean_records, seed=seed)
    if split_result.get("requires_review"):
        raise ValidationError("Dataset split requires review; training was blocked.")

    splits = split_result.get("splits", {})
    train_records = splits.get("train", [])
    test_records = splits.get("test", [])

    if not train_records or not test_records:
        raise ValidationError("Training and test splits must both contain records.")

    train_labels = {record.get("label") for record in train_records}
    test_labels = {record.get("label") for record in test_records}

    if not set(EXPECTED_LABELS).issubset(train_labels):
        raise ValidationError(
            "The training split does not contain both classes. "
            "More or better-balanced data is needed."
        )

    if not set(EXPECTED_LABELS).issubset(test_labels):
        raise ValidationError(
            "The test split does not contain both classes. "
            "Accuracy would not provide a sufficiently balanced evaluation."
        )

    model = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                min_df=1,
                max_features=MAX_FEATURES,
                strip_accents="unicode",
                sublinear_tf=True,
            ),
        ),
        (
            "classifier",
            LogisticRegression(
                max_iter=MAX_ITERATIONS,
                class_weight="balanced",
                random_state=seed,
            ),
        ),
    ])

    model.fit(
        [record["text"] for record in train_records],
        [record["label"] for record in train_records],
    )

    metrics = evaluate_model(model, test_records)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    unique_id = uuid.uuid4().hex[:8]
    stem = f"candidate_{timestamp}_{unique_id}"
    model_path = output_dir / f"{stem}.joblib"
    report_path = output_dir / f"{stem}.json"

    # Save only after validation, fitting, and evaluation have succeeded.
    _atomic_model_write(model, model_path)
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()

    split_counts = {
        name: len(items)
        for name, items in splits.items()
    }

    report = {
        "status": "CANDIDATE_TRAINED",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "algorithm": "TF-IDF + Logistic Regression",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "dataset": {
            "input_records": len(records),
            "unique_records_used": len(clean_records),
            "duplicates_reported": len(dedup.get("duplicates", [])),
            "split_counts": split_counts,
            "split_class_counts": split_result.get("class_counts", {}),
        },
        "metrics": metrics,
        "artifact": {
            "filename": model_path.name,
            "sha256": digest,
        },
        "promotion_status": "NOT_PROMOTED",
        "live_execution_enabled": False,
        "limitations": [
            "Metrics describe this dataset and split, not guaranteed real-world performance.",
            "A ham prediction is not proof that a message is safe.",
            "Review data provenance, licensing, and representativeness before approval.",
        ],
    }

    _atomic_json_write(report_path, report)

    return {
        "status": report["status"],
        "model_path": str(model_path),
        "report_path": str(report_path),
        "report": report,
    }
