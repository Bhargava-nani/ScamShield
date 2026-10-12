
from pathlib import Path
import csv
import json
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, confusion_matrix

BASE_DIR = Path(__file__).parent
DATASET = BASE_DIR / "data" / "SMSSpamCollection"
EXPERIMENTS = BASE_DIR / "experiments"

EXPERIMENTS.mkdir(exist_ok=True)

messages = []
labels = []

with DATASET.open("r", encoding="utf-8") as file:
    for line in file:
        parts = line.rstrip("\r\n").split("\t", maxsplit=1)

        if len(parts) != 2:
            continue

        label, message = parts

        if label in {"ham", "spam"} and message.strip():
            messages.append(message)
            labels.append(label)

# Reproduce the original held-out split exactly.
X_train, X_test, y_train, y_test = train_test_split(
    messages,
    labels,
    test_size=0.20,
    random_state=42,
    stratify=labels,
)

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

print("Training the same baseline for error analysis...")
model.fit(X_train, y_train)
predictions = model.predict(X_test)

matrix = confusion_matrix(
    y_test, predictions, labels=["ham", "spam"]
)
tn, fp, fn, tp = matrix.ravel()

# Save errors separately. Message text is intentionally excluded
# from the report to reduce unnecessary exposure of message content.
error_counts = Counter()
error_rows = []

for index, (actual, predicted) in enumerate(
    zip(y_test, predictions)
):
    if actual != predicted:
        error_type = (
            "false_positive" if predicted == "spam"
            else "false_negative"
        )
        error_counts[error_type] += 1

        error_rows.append({
            "test_index": index,
            "actual_label": actual,
            "predicted_label": predicted,
            "error_type": error_type,
            "message_length": len(X_test[index]),
        })

errors_path = EXPERIMENTS / "error_analysis.csv"

with errors_path.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "test_index",
            "actual_label",
            "predicted_label",
            "error_type",
            "message_length",
        ],
    )
    writer.writeheader()
    writer.writerows(error_rows)

# Count exact duplicate messages across the full dataset.
message_counts = Counter(messages)
duplicate_groups = sum(
    1 for count in message_counts.values() if count > 1
)
duplicate_extra_rows = sum(
    count - 1 for count in message_counts.values() if count > 1
)

# Check whether exact text appears in both train and test.
train_texts = set(X_train)
test_texts = set(X_test)
overlap_texts = train_texts.intersection(test_texts)

report = {
    "dataset_messages": len(messages),
    "training_messages": len(X_train),
    "test_messages": len(X_test),
    "accuracy": round(float(accuracy_score(y_test, predictions)), 6),
    "true_negatives": int(tn),
    "false_positives": int(fp),
    "false_negatives": int(fn),
    "true_positives": int(tp),
    "exact_duplicate_groups": duplicate_groups,
    "duplicate_extra_rows": duplicate_extra_rows,
    "unique_texts_shared_between_train_and_test": len(overlap_texts),
    "split": "80/20 stratified; random_state=42",
    "model": "TF-IDF (1,2 grams; max_features=20000) + LogisticRegression",
    "message_text_saved": False,
}

report_path = EXPERIMENTS / "error_analysis_report.json"

with report_path.open("w", encoding="utf-8") as file:
    json.dump(report, file, indent=2)

print("\n=== ERROR ANALYSIS RESULTS ===")
print(f"Accuracy: {report['accuracy']:.4f}")
print(f"False positives: {fp}")
print(f"False negatives: {fn}")
print(f"True negatives: {tn}")
print(f"True positives: {tp}")
print(f"Exact duplicate groups: {duplicate_groups}")
print(f"Extra rows from exact duplicates: {duplicate_extra_rows}")
print(f"Train/test shared exact message texts: {len(overlap_texts)}")
print(f"\nSaved report: {report_path}")
print(f"Saved error counts: {errors_path}")
print("Message text was not written to either report.")
