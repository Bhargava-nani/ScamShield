
from pathlib import Path

import joblib
from flask import Flask, jsonify, request, send_from_directory
from rate_limit import rate_limit

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
MODEL_PATH = BASE_DIR / "models" / "scamshield_baseline.joblib"
MAX_MESSAGE_LENGTH = 5000

if not MODEL_PATH.is_file():
    raise RuntimeError(
        f"Saved model not found: {MODEL_PATH}. "
        "Run save_model.py first."
    )

# Only load the model artifact created by your own trusted script.
model = joblib.load(MODEL_PATH)

app = Flask(__name__, static_folder=None)
# Reject excessively large HTTP request bodies.
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # 16 KiB

@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(413)
def request_too_large(error):
    return jsonify({
        "error": "Request too large. Please shorten the message."
    }), 413


@app.get("/")
def home():
    return send_from_directory(PROJECT_DIR, "index.html")


@app.get("/style.css")
def stylesheet():
    return send_from_directory(PROJECT_DIR, "style.css")


@app.get("/script.js")
def javascript():
    return send_from_directory(PROJECT_DIR, "script.js")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "model_loaded": True})


@app.post("/api/analyse")
@rate_limit(limit=20, window_seconds=60)
def analyse():
    if not request.is_json:
        return jsonify({"error": "Send a JSON request."}), 415

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON object."}), 400

    message = data.get("message")

    if not isinstance(message, str):
        return jsonify({"error": "Message must be text."}), 400

    message = message.strip()

    if not message:
        return jsonify({"error": "Please enter a message."}), 400

    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({
            "error": f"Message is too long. Maximum {MAX_MESSAGE_LENGTH} characters."
        }), 413

    # This is a model prediction, not proof that a message is a scam.
    prediction = str(model.predict([message])[0])

    probabilities = model.predict_proba([message])[0]
    classes = list(model.classes_)
    confidence = float(probabilities[classes.index(prediction)])

    if prediction == "spam":
        category = "spam-like"
        advice = (
            "Treat this message cautiously. Do not click links, "
            "share OTPs, or send money based on the message. "
            "Verify through the organisation's official app or website."
        )
    else:
        category = "legitimate-labelled"
        advice = (
            "The model classified this as resembling legitimate "
            "messages in its training dataset. This does not prove "
            "the message is safe. Verify unexpected requests independently."
        )

    return jsonify({
        "prediction": prediction,
        "category": category,
        "model_confidence": round(confidence, 4),
        "confidence_note": (
            "Model confidence is not a calibrated probability of safety "
            "or fraud."
        ),
        "advice": advice,
        "model": "ScamShield SMS baseline",
    })


if __name__ == "__main__":
    # Local-only development server. Do not expose it to the network.
    app.run(host="127.0.0.1", port=5000, debug=False)