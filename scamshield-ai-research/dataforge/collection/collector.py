"""Orchestration for one approved DataForge source."""

from __future__ import annotations

from pathlib import Path

from ..config import DEFAULT_TIMEOUT_SECONDS, MAX_DOWNLOAD_BYTES, MAX_RETRIES
from ..exceptions import ValidationError
from .download_manager import DownloadError, download_source
from .retry_manager import retry_call


def _is_transient_download_error(error: Exception) -> bool:
    """Retry only errors explicitly classified as temporary network failures."""
    if not isinstance(error, DownloadError):
        return False

    message = str(error)
    return message in {
        "HTTPS download failed.",
        "Could not resolve the approved source hostname.",
    }


def collect_source(
    source: dict,
    approved_domains,
    storage_dir: str | Path | None = None,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = MAX_RETRIES,
) -> dict:
    """Validate and download one source using the existing secure download layer.

    Security, provenance and input-validation failures are never retried.
    This function does not extract, parse, train on, or promote downloaded data.
    """
    if not isinstance(source, dict):
        raise ValidationError("Source configuration must be a dictionary.")

    if (
        isinstance(max_bytes, bool)
        or not isinstance(max_bytes, int)
        or max_bytes < 1
    ):
        raise ValidationError("max_bytes must be a positive integer.")

    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not 0 < timeout_seconds <= 120
    ):
        raise ValidationError(
            "timeout_seconds must be greater than 0 and at most 120."
        )

    return retry_call(
        download_source,
        source,
        approved_domains,
        storage_dir=storage_dir,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_exceptions=(DownloadError,),
        retry_if=_is_transient_download_error,
    )
