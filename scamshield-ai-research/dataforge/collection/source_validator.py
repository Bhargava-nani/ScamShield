"""Validate source metadata before DataForge collection begins.

This module performs no network requests and does not download content.
Network-time SSRF and redirect protections belong in the download layer.
"""

from ..constants import DATA_REAL, DATA_SYNTHETIC
from ..exceptions import ProvenanceError, ValidationError
from ..security.source_policy import validate_source as validate_source_policy


_REQUIRED_FIELDS = frozenset({
    "source_id",
    "source_url",
    "permission_confirmed",
    "license_status",
})

_OPTIONAL_FIELDS = frozenset({
    "provider",
    "data_type",
})

_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS
_ALLOWED_DATA_TYPES = frozenset({DATA_REAL, DATA_SYNTHETIC})


def validate_source(source, approved_domains):
    """Validate and normalize one source configuration.

    Args:
        source: Dictionary containing source_id, source_url,
            permission_confirmed, and license_status. Optional fields are
            provider and data_type.
        approved_domains: Explicit allowlist of approved hostnames.

    Returns:
        A normalized dictionary with source identity, URL, approval metadata,
        provider, and data type.

    Raises:
        ValidationError: If the source configuration has invalid structure
            or field types.
        ProvenanceError: If permission, licensing, or source policy fails.
        SecurityViolationError: If the URL or domain violates security policy.

    This function does not prove that a permission claim is truthful.
    """
    if not isinstance(source, dict):
        raise ValidationError("Source configuration must be a dictionary.")

    missing = _REQUIRED_FIELDS - source.keys()
    if missing:
        raise ValidationError(
            "Source configuration is missing fields: "
            + ", ".join(sorted(missing))
        )

    extra = source.keys() - _ALLOWED_FIELDS
    if extra:
        raise ValidationError(
            "Source configuration contains unsupported fields: "
            + ", ".join(sorted(str(field) for field in extra))
        )

    source_id = source["source_id"]
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or len(source_id.strip()) > 128
    ):
        raise ValidationError(
            "source_id must contain 1 to 128 non-whitespace characters."
        )

    source_url = source["source_url"]
    if not isinstance(source_url, str) or not source_url:
        raise ValidationError("source_url must be a non-empty string.")

    permission_confirmed = source["permission_confirmed"]
    if not isinstance(permission_confirmed, bool):
        raise ValidationError("permission_confirmed must be a boolean.")

    license_status = source["license_status"]
    if not isinstance(license_status, str) or not license_status.strip():
        raise ValidationError("license_status must be a non-empty string.")

    provider = source.get("provider")
    if provider is not None and (
        not isinstance(provider, str)
        or not provider.strip()
        or len(provider) > 256
    ):
        raise ValidationError(
            "provider must be null or a non-empty string of at most 256 characters."
        )

    data_type = source.get("data_type", DATA_REAL)
    if not isinstance(data_type, str) or data_type not in _ALLOWED_DATA_TYPES:
        raise ValidationError("data_type must be REAL or SYNTHETIC.")

    # Require an explicit domain allowlist. Never silently approve a source.
    if not isinstance(approved_domains, (set, frozenset, list, tuple)):
        raise ValidationError(
            "approved_domains must be an explicit list, tuple, or set."
        )

    policy_result = validate_source_policy(
        source_url=source_url,
        approved_domains=approved_domains,
        permission_confirmed=permission_confirmed,
        license_status=license_status,
    )

    return {
        "source_id": source_id.strip(),
        "source_url": policy_result["url"],
        "domain": policy_result["domain"],
        "permission_confirmed": True,
        "license_status": policy_result["license_status"],
        "approval_status": policy_result["approval_status"],
        "provider": provider.strip() if provider is not None else None,
        "data_type": data_type,
    }
