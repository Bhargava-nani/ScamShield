# ScamShield — AI-Based SMS Scam Detection

## 1. Project Overview

ScamShield is a beginner-friendly cybersecurity project that analyses SMS messages using a machine-learning model and provides safety guidance.

The goal is to help users recognise suspicious messages and encourage safer decisions before clicking links, sharing OTPs, or sending money.

**Important:** ScamShield is a prototype for educational and research purposes. It cannot guarantee that a message is safe or fraudulent.

## 2. Current Features

- Web interface for entering SMS messages.
- Machine-learning classification using TF-IDF and Logistic Regression.
- Local Flask API connecting the website to the saved model.
- Model confidence display with an explanatory warning.
- Safety advice for suspicious and apparently legitimate messages.
- Additional phrase-based warning indicators.
- Input validation and a 5,000-character message limit.
- Error handling for invalid JSON and unsupported request formats.
- Local-only development server.

## 3. Technology Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python and Flask
- **Machine learning:** scikit-learn
- **Model storage:** joblib
- **Dataset:** UCI SMS Spam Collection

## 4. Model and Dataset

The baseline model uses TF-IDF text features and Logistic Regression.

Dataset size: 5,574 messages.

- Ham (labelled non-spam): 4,827
- Spam: 747
- Training set: 4,459 messages
- Test set: 1,115 messages

### Initial baseline evaluation

- Accuracy: 98.39%
- True negatives: 957
- False positives: 9
- False negatives: 9
- True positives: 140

These are initial results, not proof of real-world scam detection performance.

**Evaluation limitation:** Exact duplicate messages were found across the training and test sets. This overlap can make performance appear better than it would on genuinely unseen messages. A duplicate-aware evaluation is a planned improvement.

The dataset focuses on SMS spam and does not represent every type of modern scam, phishing message, malicious link, or financial fraud.

Dataset source: https://archive.ics.uci.edu/dataset/228/sms+spam+collection

Check the dataset's official documentation and licence before redistributing the dataset.

## 5. Run ScamShield Locally

Requirements: Windows, Python, and VS Code.

From the project root, activate the existing virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start the backend:

```powershell
.\.venv\Scripts\python.exe .\scamshield-ai-research\app.py
```

Open this address in your browser:

http://127.0.0.1:5000

Keep the backend terminal running while using the website.

## 6. API Endpoints

### Health check

`GET /api/health`

Confirms that the local API is running and the model is loaded.

### Message analysis

`POST /api/analyse`

Accepts a JSON object containing a message and returns the model prediction, model confidence, and safety advice.

## 7. Tests Completed

- Website opens and the Analyse and Clear buttons work.
- Suspicious sample SMS classified as spam.
- Ordinary sample SMS classified as ham.
- Empty message rejected by the interface.
- Health endpoint returned a successful response.
- Oversized message rejected with HTTP 413.
- Malformed JSON rejected with HTTP 400.
- Unsupported content type rejected with HTTP 415.
- Saved model reloaded and reproduced the expected test predictions.

These are initial manual and integration tests, not comprehensive security testing.

## 8. Known Limitations

- Model predictions can be wrong.
- Model confidence is not a calibrated probability of fraud or safety.
- Training data is limited to a particular SMS spam dataset.
- Duplicate overlap must be addressed in evaluation.
- Near-duplicate leakage has not yet been assessed.
- Real-time threat intelligence and URL reputation checks are not implemented.
- The Flask development server is for local demonstration, not public production deployment.
- No claim of guaranteed scam detection or prevention is made.

## 9. Planned Improvements

1. Duplicate-aware model evaluation.
2. Repeatable automated tests.
3. Improved detection explanations and interface design.
4. More diverse, appropriately licensed datasets.
5. URL and phishing analysis with safe handling.
6. Security review and privacy assessment.
7. Demo documentation and presentation.

## 10. Responsible Use

Use fictional or appropriately anonymised examples during demonstrations. Do not submit real OTPs, passwords, banking details, or other sensitive information.

A message classified as legitimate may still be malicious. Verify important requests independently through official channels.

---

**Project status:** Functional educational prototype with a trained baseline model, local API integration, and initial safety tests. Further evaluation and security work are required before any real-world deployment.