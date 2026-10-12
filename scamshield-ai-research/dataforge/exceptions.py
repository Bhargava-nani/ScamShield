
"""Custom exceptions for ScamShield DataForge."""


class DataForgeError(Exception):
    """Base exception for DataForge errors."""


class ConfigurationError(DataForgeError):
    """Raised when configuration is missing or invalid."""


class ValidationError(DataForgeError):
    """Raised when input data fails validation."""


class UnsafeInputError(DataForgeError):
    """Raised when an input violates a safety rule."""


class CollectionError(DataForgeError):
    """Raised when collecting data fails."""


class ExtractionError(DataForgeError):
    """Raised when safe data extraction fails."""


class StorageError(DataForgeError):
    """Raised when storing or retrieving data fails."""


class ProvenanceError(DataForgeError):
    """Raised when source provenance cannot be verified."""


class DuplicateConflictError(DataForgeError):
    """Raised when duplicate records have conflicting labels."""


class SecurityViolationError(DataForgeError):
    """Raised when a security policy is violated."""
