"""Source approval and provenance policy for DataForge."""

from urllib.parse import urlsplit

from ..exceptions import ProvenanceError, SecurityViolationError
from .url_safety import validate_url


APPROVED_LICENSE_STATUSES = {
    "approved",
    "public_domain",
    "permission_granted",
}


def validate_source(
    source_url,
    approved_domains,
    permission_confirmed,
    license_status,
):
    """Validate a source before collection begins.

    approved_domains must be explicitly configured by the application owner.
    This function does not independently verify legal rights or ownership.
    """
    if not permission_confirmed:
        raise ProvenanceError(
            "Source permission must be confirmed before collection."
        )

    if not isinstance(license_status, str):
        raise ProvenanceError("A documented license status is required.")

    status = license_status.strip().lower()

    if status not in APPROVED_LICENSE_STATUSES:
        raise ProvenanceError(
            "Source license or permission status is not approved."
        )

    safe_url = validate_url(source_url, require_https=True)
    hostname = urlsplit(safe_url).hostname

    if not isinstance(approved_domains, (set, frozenset, list, tuple)):
        raise ProvenanceError("An explicit approved-domain list is required.")

    normalized_domains = {
        str(domain).strip().lower().rstrip(".")
        for domain in approved_domains
        if isinstance(domain, str) and domain.strip()
    }

    if not hostname or hostname.lower().rstrip(".") not in normalized_domains:
        raise SecurityViolationError(
            "Source domain is not on the approved-domain list."
        )

    return {
        "url": safe_url,
        "domain": hostname.lower().rstrip("."),
        "license_status": status,
        "permission_confirmed": True,
        "approval_status": "VALIDATED",
    }