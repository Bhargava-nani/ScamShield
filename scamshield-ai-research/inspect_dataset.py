
from pathlib import Path
from collections import Counter

# Find the dataset relative to this Python file.
dataset_path = Path(__file__).parent / "data" / "SMSSpamCollection"

if not dataset_path.exists():
    print("ERROR: Dataset file not found.")
    print("Check that SMSSpamCollection is inside the data folder.")
    raise SystemExit(1)

labels = Counter()
total_messages = 0

with dataset_path.open("r", encoding="utf-8") as file:
    for line_number, line in enumerate(file, start=1):
        parts = line.rstrip("\r\n").split("\t", maxsplit=1)

        if len(parts) != 2:
            print(f"Skipped malformed line: {line_number}")
            continue

        label, message = parts

        if label not in {"ham", "spam"}:
            print(f"Unexpected label on line {line_number}: {label}")
            continue

        if not message.strip():
            print(f"Empty message on line {line_number}")
            continue

        labels[label] += 1
        total_messages += 1

print("\n--- ScamShield Dataset Inspection ---")
print(f"Valid messages: {total_messages}")
print(f"Legitimate-labelled (ham): {labels['ham']}")
print(f"Spam-labelled: {labels['spam']}")
print("Dataset inspection complete.")
print("Note: spam is not the same as every type of scam.")