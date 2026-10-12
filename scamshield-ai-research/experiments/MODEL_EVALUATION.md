# ScamShield — Baseline Model Evaluation

## 1. Project objective

ScamShield is a cybersecurity awareness prototype that analyses text messages for patterns resembling spam. It provides a model prediction and safety advice to help users make more informed decisions.

## 2. Dataset

- Dataset: UCI SMS Spam Collection
- Total messages: 5,574
- Ham messages: 4,827
- Spam messages: 747
- Scope: Traditional SMS spam classification
- Limitation: This dataset does not represent every modern phishing or scam scenario.

## 3. Duplicate-aware evaluation

The model was evaluated using a grouped train/test split so that identical message texts do not appear in both training and test sets.

| Metric | Result |
|---|---:|
| Training messages | 4,459 |
| Test messages | 1,115 |
| Exact-text overlap | 0 |
| Accuracy | 97.76% |
| Spam precision | 87% |
| Spam recall | 97% |
| Spam F1-score | 0.92 |

### Confusion matrix

| Actual / Predicted | Ham | Spam |
|---|---:|---:|
| Ham | 944 | 21 |
| Spam | 4 | 146 |

## 4. Understanding the errors

- **21 false positives:** Legitimate messages incorrectly classified as spam.
- **4 false negatives:** Spam messages incorrectly classified as legitimate.
- Total incorrect test predictions: 25.

These errors show why model predictions should be treated as assistance rather than proof that a message is safe or fraudulent.

## 5. Security testing

The Flask application passed 13 automated security tests covering:

- Security response headers.
- API health and frontend file delivery.
- Invalid JSON and incorrect content types.
- Missing, empty, and non-text messages.
- Message-length and request-body limits.
- Expected fields in valid analysis responses.

These tests verify selected behaviours; they are not a complete security audit.

## 6. Limitations

1. Evaluation is limited to the SMS spam dataset used in this experiment.
2. High accuracy does not guarantee reliable detection of new or sophisticated scams.
3. Model confidence is not a calibrated probability that a message is safe or fraudulent.
4. Duplicate-aware splitting reduces exact-text overlap but does not eliminate every possible source of dataset bias or leakage.
5. Performance on real-world messages must be evaluated separately before making broader claims.

## 7. Safety advice

Users should not share OTPs, passwords, or banking credentials in response to unexpected messages. They should verify requests through an organisation's official app, website, or independently obtained contact details.

## 8. Current project status

The baseline model, Flask analysis API, frontend, duplicate-aware evaluation, error analysis, and selected automated security tests are implemented.

**This is a research prototype, not a certified scam detector.** Further testing on representative, independently collected data is required before making real-world performance claims.