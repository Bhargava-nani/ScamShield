"""Fail-closed authentication for administrative Flask API routes.

Admin credentials must be configured on the server, never in frontend code.
Use HTTPS in any non-local deployment.
"""

import hmac
import os
from functools import wraps

from flask import jsonify, request


ADMIN_TOKEN_ENV = "SCAMSHIELD_ADMIN_TOKEN"


def admin_token_is_valid(provided_token):
    """Validate an admin bearer token using a constant-time comparison."""
    expected_token = os.environ.get(ADMIN_TOKEN_ENV, "")

    # Fail closed when server-side authentication is not configured.
    if not expected_token or len(expected_token) < 32:
        return False

    if not isinstance(provided_token, str) or not provided_token:
        return False

    return hmac.compare_digest(expected_token, provided_token)


def admin_required(view_function):
    """Protect a Flask route with server-configured bearer authentication."""

    @wraps(view_function)
    def wrapped(*args, **kwargs):
        expected_token = os.environ.get(ADMIN_TOKEN_ENV, "")

        if not expected_token or len(expected_token) < 32:
            return jsonify({
                "error": "Administrative authentication is not configured."
            }), 503

        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")

        if (
            not separator
            or scheme.lower() != "bearer"
            or not token
            or not admin_token_is_valid(token)
        ):
            response = jsonify({"error": "Authentication required."})
            response.status_code = 401
            response.headers["WWW-Authenticate"] = "Bearer"
            return response

        return view_function(*args, **kwargs)

    return wrapped
