
"use strict";

const messageInput = document.getElementById("messageInput");
const analyseButton = document.getElementById("analyseButton");
const clearButton = document.getElementById("clearButton");
const result = document.getElementById("result");
const characterCount = document.getElementById("characterCount");
const currentCount = document.getElementById("currentCount");

const MAX_MESSAGE_LENGTH = 5000;

const warningCategories = {
    "Urgency": [
        "urgent action required",
        "act immediately",
        "send money immediately"
    ],
    "Account warnings": [
        "verify your account",
        "account will be blocked",
        "your account is suspended"
    ],
    "OTP requests": [
        "share your otp",
        "send your otp",
        "tell me your otp"
    ],
    "Prize claims": [
        "claim your prize",
        "you have won",
        "you won a free prize"
    ],
    "Link warnings": [
        "click this link"
    ]
};

// Enforce the limit and update the counter.
function updateCharacterCount() {
    if (messageInput.value.length > MAX_MESSAGE_LENGTH) {
        const cursorPosition = Math.min(
            messageInput.selectionStart,
            MAX_MESSAGE_LENGTH
        );

        messageInput.value = messageInput.value.slice(
            0,
            MAX_MESSAGE_LENGTH
        );

        messageInput.setSelectionRange(
            cursorPosition,
            cursorPosition
        );
    }

    const length = messageInput.value.length;

    currentCount.textContent = String(length);

    characterCount.classList.toggle(
        "near-limit",
        length >= MAX_MESSAGE_LENGTH * 0.8 &&
        length < MAX_MESSAGE_LENGTH
    );

    characterCount.classList.toggle(
        "at-limit",
        length >= MAX_MESSAGE_LENGTH
    );

    messageInput.setAttribute("aria-invalid", "false");
}

function makeElement(tag, className, text) {
    const element = document.createElement(tag);

    if (className) {
        element.className = className;
    }

    if (text !== undefined) {
        element.textContent = text;
    }

    return element;
}

function showNotice(title, message, isError = false) {
    result.replaceChildren();

    const card = makeElement(
        "div",
        isError ? "result-card result-error" : "result-placeholder"
    );

    const icon = makeElement(
        "span",
        "placeholder-icon",
        isError ? "!" : "i"
    );

    icon.setAttribute("aria-hidden", "true");

    const content = document.createElement("div");

    content.append(
        makeElement("strong", "", title),
        makeElement("p", "", message)
    );

    card.append(icon, content);
    result.append(card);
}

function findWarnings(message) {
    const lowerMessage = message.toLowerCase();
    const warnings = [];

    for (const [category, phrases] of Object.entries(warningCategories)) {
        const matches = phrases.filter(
            phrase => lowerMessage.includes(phrase)
        );

        if (matches.length > 0) {
            warnings.push({ category, phrases: matches });
        }
    }

    return warnings;
}

// Display short, plain-language results.
function renderAnalysis(data, message) {
    result.replaceChildren();

    const isSpam = data.prediction === "spam";
    const warnings = findWarnings(message);
    const confidence = Number(data.model_confidence);

    const card = makeElement(
        "article",
        isSpam
            ? "result-card result-risk"
            : "result-card result-safe-label"
    );

    card.append(
        makeElement("span", "result-symbol", isSpam ? "⚠" : "✓"),
        makeElement(
            "span",
            "result-label",
            isSpam ? "HIGHER CONCERN" : "NO STRONG SPAM PATTERN"
        ),
        makeElement(
            "h3",
            "",
            isSpam
                ? "Be careful! This message may be spam."
                : "No strong spam signs detected."
        ),
        makeElement(
            "p",
            "",
            isSpam
                ? "Risk: You could lose money or expose personal information if this message is fraudulent."
                : "Risk: Uncertain. A genuine-looking message can still be a scam."
        ),
        makeElement("h4", "", "What to do"),
        makeElement(
            "p",
            "",
            isSpam
                ? "Don't click links, send money, or share OTPs or passwords. Verify the sender independently."
                : "Check the sender. Verify unexpected links, payment requests, or requests for personal details."
        )
    );

    if (warnings.length > 0) {
        const reasons = warnings
            .map(item => item.category)
            .join(", ");

        card.append(
            makeElement("h4", "", "Warning signs"),
            makeElement("p", "", reasons + " detected.")
        );
    }

    if (
        Number.isFinite(confidence) &&
        confidence >= 0 &&
        confidence <= 1
    ) {
        card.append(
            makeElement(
                "p",
                "result-footnote",
                `Model confidence: ${(confidence * 100).toFixed(1)}%. This is confidence in the model's prediction, not a guarantee of safety or fraud.`
            )
        );
    }

    card.append(
        makeElement(
            "p",
            "result-footnote",
            "When in doubt, don't pay or share sensitive details. Verify through an official channel."
        )
    );

    result.append(card);
}

// Enforce the limit for typing, paste and mobile input.
messageInput.addEventListener("input", updateCharacterCount);
messageInput.addEventListener("change", updateCharacterCount);

messageInput.addEventListener("paste", function () {
    // Run after the browser processes the paste.
    setTimeout(updateCharacterCount, 0);
});

// Analyse the message using the local Flask model.
analyseButton.addEventListener("click", async function () {
    const message = messageInput.value.trim();

    if (!message) {
        showNotice(
            "Enter a message first",
            "Paste or type the SMS you want ScamShield to check."
        );

        messageInput.focus();
        return;
    }

    if (message.length > MAX_MESSAGE_LENGTH) {
        updateCharacterCount();

        showNotice(
            "Message is too long",
            "Please keep your message within 5,000 characters.",
            true
        );

        return;
    }

    analyseButton.disabled = true;
    analyseButton.textContent = "Checking message...";

    showNotice(
        "Checking your message",
        "ScamShield is analysing the text."
    );

    try {
        const response = await fetch("/api/analyse", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(
                data.error ||
                `The request failed (HTTP ${response.status}).`
            );
        }

        if (
            !data ||
            !["spam", "ham"].includes(data.prediction) ||
            typeof data.model_confidence !== "number"
        ) {
            throw new Error("The server returned an unexpected result.");
        }

        renderAnalysis(data, message);
    } catch (error) {
        showNotice(
            "We couldn't check this message",
            "Check that the ScamShield backend is running, then try again. " +
                (error instanceof Error
                    ? error.message
                    : "Unknown error."),
            true
        );
    } finally {
        analyseButton.disabled = false;
        analyseButton.textContent = "⌕ Check this message";
    }
});

// Clear the message and reset the result.
clearButton.addEventListener("click", function () {
    messageInput.value = "";
    updateCharacterCount();

    result.replaceChildren();

    const placeholder = makeElement("div", "result-placeholder");
    const icon = makeElement("span", "placeholder-icon", "✓");

    icon.setAttribute("aria-hidden", "true");

    const content = document.createElement("div");

    content.append(
        makeElement("strong", "", "Your result will appear here"),
        makeElement(
            "p",
            "",
            "Enter a message above and select “Check this message”."
        )
    );

    placeholder.append(icon, content);
    result.append(placeholder);

    messageInput.focus();
});

// Initialise the counter when the page loads.
updateCharacterCount();
