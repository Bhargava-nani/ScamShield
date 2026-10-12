
import csv
import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline


# Paths
BASE_DIR = Path(__file__).parent
DATASET_PATH = BASE_DIR / "data" / "SMSSpamCollection"
OUTPUT_DIR = BASE_DIR / "experiments"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

messages = []
labels = []

# Load the dataset and validate each row.
with DATASET_PATH.open("r", encoding="utf-8") as file:
    for line in file:
        parts = line.rstrip("\r\n").split("\t", maxsplit=1)

        if len(parts) != 2:
            continue

        label, message = parts

        if label not in {"ham", "spam"} or not message.strip():
            continue

        messages.append(message)
        labels.append(label)

if len(messages) < 5:
    raise ValueError("Not enough valid messages to evaluate.")

# Use the exact message text as the group.
# Identical messages cannot appear in both training and test sets.
groups = messages

# Create a roughly 80/20 split while attempting to preserve
# the class balance and keeping duplicate messages together.
splitter = StratifiedGroupKFold(
    n_splits=5,
    shuffle=True,
    random_state=42,
)

train_indices, test_indices = next(
    splitter.split(messages, labels, groups=groups)
)

X_train = [messages[i] for i in train_indices]
X_test = [messages[i] for i in test_indices]
y_train = [labels[i] for i in train_indices]
y_test = [labels[i] for i in test_indices]

train_texts = set(X_train)
test_texts = set(X_test)
overlap = train_texts.intersection(test_texts)

# Build the same baseline pipeline.
model = Pipeline([
    (
        "tfidf",
        TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            max_features=20000,
        ),
    ),
    (
        "classifier",
        LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        ),
    ),
])

print("Training duplicate-aware baseline...")
model.fit(X_train, y_train)

predictions = model.predict(X_test)

accuracy = accuracy_score(y_test, predictions)

report = classification_report(
    y_test,
    predictions,
    labels=["ham", "spam"],
    output_dict=True,
    zero_division=0,
)

matrix = confusion_matrix(
    y_test,
    predictions,
    labels=["ham", "spam"],
)

# Identify incorrect predictions.
errors = []

for message, actual, predicted in zip(
    X_test, y_test, predictions
):
    if actual != predicted:
        errors.append({
            "actual_label": actual,
            "predicted_label": predicted,
            "error_type": (
                "false_positive"
                if actual == "ham"
                else "false_negative"
            ),
            "message": message,
        })

# Save incorrect predictions for manual inspection.
errors_path = OUTPUT_DIR / "evaluation_errors.csv"

with errors_path.open(
    "w", newline="", encoding="utf-8-sig"
) as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "actual_label",
            "predicted_label",
            "error_type",
            "message",
        ],
    )
    writer.writeheader()
    writer.writerows(errors)

# Save machine-readable metrics.
results = {
    "dataset": DATASET_PATH.name,
    "split_method": "StratifiedGroupKFold",
    "random_state": 42,
    "train_messages": len(X_train),
    "test_messages": len(X_test),
    "train_unique_texts": len(train_texts),
    "test_unique_texts": len(test_texts),
    "exact_text_overlap": len(overlap),
    "accuracy": accuracy,
    "classification_report": report,
    "confusion_matrix": matrix.tolist(),
    "confusion_matrix_label_order": ["ham", "spam"],
    "incorrect_predictions": len(errors),
    "note": (
        "Exact-text duplicates are kept in one split. "
        "This is one evaluation split, not proof of "
        "performance on every real-world scam."
    ),
}

results_path = OUTPUT_DIR / "duplicate_aware_results.json"

with results_path.open("w", encoding="utf-8") as file:
    json.dump(results, file, indent=2, ensure_ascii=False)

# Display results.
print("\n--- Duplicate-Aware Evaluation ---")
print(f"Training messages: {len(X_train)}")
print(f"Test messages: {len(X_test)}")
print(f"Unique training texts: {len(train_texts)}")
print(f"Unique test texts: {len(test_texts)}")
print(f"Exact-text overlap: {len(overlap)}")
print(f"Accuracy: {accuracy:.4f}")

print("\nClassification report:")
print(classification_report(
    y_test,
    predictions,
    labels=["ham", "spam"],
    zero_division=0,
))

print("Confusion matrix (rows = actual, columns = predicted)")
print("Label order: ham, spam")
print(matrix)

print(f"\nIncorrect predictions: {len(errors)}")
print(f"Metrics saved to: {results_path}")
print(f"Errors saved to: {errors_path}")
print("\nEvaluation complete. The production model was not changed.")
