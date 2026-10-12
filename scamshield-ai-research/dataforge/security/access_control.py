"""Deny-by-default authorization checks for DataForge operations.

These checks are not a replacement for authenticating the user or securing
the API. The calling application must obtain the role from a trusted,
authenticated identity—not from an untrusted request field.
"""

from ..exceptions import SecurityViolationError


ROLE_PERMISSIONS = {
    "viewer": frozenset({
        "dataset.read",
        "evaluation.read",
    }),
    "researcher": frozenset({
        "dataset.read",
        "evaluation.read",
        "dataset.validate",
        "model.train",
        "evaluation.run",
    }),
    "curator": frozenset({
        "dataset.read",
        "evaluation.read",
        "dataset.validate",
        "dataset.import",
        "dataset.quarantine",
        "source.approve",
        "model.train",
        "evaluation.run",
    }),
    "administrator": frozenset({
        "dataset.read",
        "evaluation.read",
        "dataset.validate",
        "dataset.import",
        "dataset.quarantine",
        "source.approve",
        "model.train",
        "evaluation.run",
        "model.promote",
        "audit.read",
        "configuration.manage",
    }),
}


def authorize(role, action):
    """Raise SecurityViolationError unless the role explicitly permits action."""
    if not isinstance(role, str) or not isinstance(action, str):
        raise SecurityViolationError("Role and action must be strings.")

    normalized_role = role.strip().lower()
    normalized_action = action.strip().lower()

    if not normalized_role or not normalized_action:
        raise SecurityViolationError("Role and action cannot be empty.")

    # This platform's live-execution safety setting remains disabled.
    # No role can override this authorization boundary.
    if normalized_action in {
        "production.execute",
        "live.execute",
        "live.enable",
    }:
        raise SecurityViolationError("Live execution is disabled.")

    permissions = ROLE_PERMISSIONS.get(normalized_role, frozenset())

    if normalized_action not in permissions:
        raise SecurityViolationError(
            f"Role '{normalized_role}' is not authorized for '{normalized_action}'."
        )

    return True