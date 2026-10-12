
from pathlib import Path
import json
import joblib
import sklearn

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

BASE_DIR = Path(__file__).parent
DATASET = BASE_DIR / "data" / "SMSSpamCollection"
MODEL_DIR = BASE_DIR / "models"

MODEL_DIR.mkdir(exist_ok=True)

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

print("Training the reproducible baseline...")
model.fit(X_train, y_train)

original_predictions = model.predict(X_test)

model_path = MODEL_DIR / "scamshield_baseline.joblib"
metadata_path = MODEL_DIR / "scamshield_baseline_metadata.json"

# Save only a locally trained, trusted model.
joblib.dump(model, model_path)

# Reload the locally created model.
loaded_model = joblib.load(model_path)
reloaded_predictions = loaded_model.predict(X_test)

predictions_match = (
    original_predictions.tolist()
    == reloaded_predictions.tolist()
)

metadata = {
    "model_name": "ScamShield TF-IDF Logistic Regression baseline",
    "dataset": "UCI SMS Spam Collection",
    "dataset_messages": len(messages),
    "training_messages": len(X_train),
    "test_messages": len(X_test),
    "split": "80/20 stratified",
    "random_state": 42,
    "vectorizer": {
        "ngram_range": [1, 2],
        "max_features": 20000,
        "lowercase": True,
        "strip_accents": "unicode",
    },
    "classifier": "LogisticRegression",
    "max_iter": 1000,
    "class_weight": "balanced",
    "scikit_learn_version": sklearn.__version__,
    "reload_predictions_match": predictions_match,
    "intended_use": "Local research prototype; not verified scam detection",
    "known_evaluation_warning": (
        "Exact message texts overlap between train and test; "
        "evaluate with duplicate-group-aware splitting."
    ),
}

with metadata_path.open("w", encoding="utf-8") as file:
    json.dump(metadata, file, indent=2)

print("\n=== MODEL SAVE AND RELOAD CHECK ===")
print(f"Model saved: {model_path}")
print(f"Metadata saved: {metadata_path}")
print(f"Original test predictions: {len(original_predictions)}")
print(f"Reloaded predictions match: {predictions_match}")

if not predictions_match:
    raise SystemExit("ERROR: Reloaded predictions do not match.")

print("Model save/reload verification passed.")
