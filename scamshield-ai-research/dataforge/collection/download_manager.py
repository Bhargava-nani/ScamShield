"""Secure, bounded HTTPS downloads for approved DataForge sources.

Redirects are deliberately rejected. DNS results are checked and the TCP
connection is pinned to a checked IP while TLS verifies the original hostname.
This module does not parse downloaded content or trust its MIME type.
"""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import socket
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from ..config import MAX_DOWNLOAD_BYTES
from ..exceptions import SecurityViolationError, ValidationError
from ..security.source_policy import validate_source as validate_source_policy
from ..storage.raw_store import store_raw_bytes


class DownloadError(RuntimeError):
    """Raised when a source cannot be downloaded safely."""


DEFAULT_TIMEOUT_SECONDS = 15
_READ_CHUNK_BYTES = 64 * 1024


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to an already-validated IP address."""

    def __init__(self, hostname: str, ip_address: str, port: int, timeout: float):
        super().__init__(
            host=hostname,
            port=port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._pinned_ip = ip_address
        self._tls_hostname = hostname

    def connect(self):
        # Connect to the validated IP, not a second DNS resolution of hostname.
        sock = socket.create_connection(
            (self._pinned_ip, self.port),
            timeout=self.timeout,
            source_address=self.source_address,
        )
        try:
            self.sock = self._context.wrap_socket(
                sock,
                server_hostname=self._tls_hostname,
            )
        except Exception:
            sock.close()
            raise


def _resolve_public_addresses(hostname: str, port: int) -> list[str]:
    """Resolve a hostname and reject the whole result if any IP is non-public."""
    try:
        results = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise DownloadError("Could not resolve the approved source hostname.") from exc

    addresses = []
    for result in results:
        raw_address = result[4][0]
        try:
            parsed = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise SecurityViolationError(
                "DNS returned an invalid destination address."
            ) from exc

        if not parsed.is_global:
            raise SecurityViolationError(
                "Source hostname resolves to a non-public IP address."
            )

        normalized = str(parsed)
        if normalized not in addresses:
            addresses.append(normalized)

    if not addresses:
        raise DownloadError("Source hostname did not resolve to an IP address.")

    return addresses


def download_source(
    source: dict,
    approved_domains,
    storage_dir: str | Path | None = None,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Download one approved source and save its bytes to immutable raw storage.

    The source dictionary must satisfy collection.source_validator's schema.
    The result contains metadata only; downloaded bytes remain in raw storage.
    No redirects, retries, archive extraction, or content parsing occur here.
    """
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValidationError("max_bytes must be a positive integer.")

    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds <= 0
        or timeout_seconds > 120
    ):
        raise ValidationError("timeout_seconds must be greater than 0 and at most 120.")

    # Validate permission, licence, HTTPS, and exact hostname allowlisting first.
    from .source_validator import validate_source

    validated = validate_source(source, approved_domains)
    parsed = urlsplit(validated["source_url"])

    if parsed.scheme != "https" or not parsed.hostname:
        raise SecurityViolationError("Only valid HTTPS source URLs are accepted.")

    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise SecurityViolationError("Source URL contains an invalid port.") from exc

    # Explicitly prohibit unusual ports unless the source policy is extended
    # deliberately in a future change.
    if port != 443:
        raise SecurityViolationError("Downloads are restricted to HTTPS port 443.")

    hostname = parsed.hostname.rstrip(".").lower()
    addresses = _resolve_public_addresses(hostname, port)

    # A single public IP is pinned for the complete connection. Redirects are
    # never followed, even if the redirect target appears to be another safe URL.
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query

    host_header = hostname
    connection = None
    content = bytearray()

    try:
        connection = _PinnedHTTPSConnection(
            hostname=hostname,
            ip_address=addresses[0],
            port=port,
            timeout=float(timeout_seconds),
        )
        connection.request(
            "GET",
            target,
            headers={
                "Host": host_header,
                "User-Agent": "ScamShield-DataForge/1.0",
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        response = connection.getresponse()

        if response.status in (301, 302, 303, 307, 308):
            raise SecurityViolationError(
                "Source returned a redirect; redirects are disabled."
            )

        if response.status != 200:
            raise DownloadError(
                f"Source returned HTTP status {response.status}; expected 200."
            )

        content_length = response.getheader("Content-Length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except (TypeError, ValueError) as exc:
                raise DownloadError("Source returned an invalid Content-Length.") from exc

            if declared_size < 0:
                raise DownloadError("Source returned a negative Content-Length.")
            if declared_size > max_bytes:
                raise DownloadError("Download exceeds the configured size limit.")

        while True:
            # Read one byte beyond the remaining allowance to detect overflow.
            remaining_plus_one = max_bytes - len(content) + 1
            chunk = response.read(min(_READ_CHUNK_BYTES, remaining_plus_one))
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > max_bytes:
                raise DownloadError("Download exceeds the configured size limit.")

    except (DownloadError, SecurityViolationError, ValidationError):
        raise
    except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError) as exc:
        raise DownloadError("HTTPS download failed.") from exc
    finally:
        if connection is not None:
            connection.close()

    if not content:
        raise DownloadError("Source returned an empty response body.")

    raw_bytes = bytes(content)
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    # Raw storage owns atomic publication and content-addressed immutability.
    artifact_path = store_raw_bytes(
        raw_bytes,
        storage_dir=storage_dir,
        max_bytes=max_bytes,
    )

    return {
        "source_id": validated["source_id"],
        "source_url": validated["source_url"],
        "domain": validated["domain"],
        "approval_status": validated["approval_status"],
        "permission_confirmed": validated["permission_confirmed"],
        "license_status": validated["license_status"],
        "provider": validated["provider"],
        "data_type": validated["data_type"],
        "artifact_path": artifact_path["path"],
        "sha256": sha256,
        "size_bytes": len(raw_bytes),
        "content_type": response.getheader("Content-Type"),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
