"""URL validation helpers for ScamShield DataForge."""

import ipaddress
from urllib.parse import urlsplit, urlunsplit

from ..exceptions import SecurityViolationError, ValidationError


def validate_url(url, require_https=True):
    """Validate URL syntax and reject obvious unsafe destinations.

    This function does not make a network request and is not, by itself,
    sufficient protection against DNS rebinding or SSRF.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValidationError("A non-empty URL is required.")

    if url != url.strip() or any(ord(ch) < 32 for ch in url):
        raise ValidationError("URL contains invalid whitespace or control characters.")

    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ValidationError("URL format is invalid.") from exc

    allowed_schemes = {"https"} if require_https else {"http", "https"}

    if parts.scheme.lower() not in allowed_schemes:
        raise SecurityViolationError("URL scheme is not permitted.")

    if not hostname:
        raise ValidationError("URL must contain a hostname.")

    if parts.username is not None or parts.password is not None:
        raise SecurityViolationError("URLs containing credentials are not allowed.")

    if port is not None and not 1 <= port <= 65535:
        raise ValidationError("URL port is invalid.")

    host = hostname.rstrip(".").lower()

    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise SecurityViolationError("Local destinations are not permitted.")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None

    if address is not None and not address.is_global:
        raise SecurityViolationError("Non-public IP destinations are not permitted.")

    if not host or any(ch.isspace() for ch in host):
        raise ValidationError("Hostname is invalid.")

    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc,
        parts.path or "/",
        parts.query,
        "",  # Fragments are not sent to servers.
    ))