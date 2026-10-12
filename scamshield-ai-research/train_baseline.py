
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

# Locate the dataset.
dataset_path = Path(__file__).parent / "data" / "SMSSpamCollection"

messages = []
labels = []

# Load the labelled messages.
with dataset_path.open("r", encoding="utf-8") as file:
    for line in file:
        parts = line.rstrip("\r\n").split("\t", maxsplit=1)

        if len(parts) != 2:
            continue

        label, message = parts

        if label not in {"ham", "spam"} or not message.strip():
            continue

        messages.append(message)
        labels.append(label)

# Keep a separate test set for evaluation.
X_train, X_test, y_train, y_test = train_test_split(
    messages,
    labels,
    test_size=0.20,
    random_state=42,
    stratify=labels,
)

# Build a lightweight text-classification pipeline.
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

print("Training the baseline model...")
model.fit(X_train, y_train)

# Evaluate only on the held-out test set.
predictions = model.predict(X_test)

print("\n--- ScamShield Baseline Evaluation ---")
print(f"Training messages: {len(X_train)}")
print(f"Test messages: {len(X_test)}")
print(f"Accuracy: {accuracy_score(y_test, predictions):.4f}")

print("\nClassification report:")
print(classification_report(
    y_test,
    predictions,
    labels=["ham", "spam"],
    zero_division=0,
))

print("Confusion matrix (rows = actual, columns = predicted)")
print("Label order: ham, spam")
print(confusion_matrix(
    y_test,
    predictions,
    labels=["ham", "spam"],
))

print("\nExperiment complete. No model file was saved.")
