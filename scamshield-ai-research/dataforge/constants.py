
"""Shared constants for ScamShield DataForge."""

# Dataset and import lifecycle statuses
STATUS_PENDING = "PENDING"
STATUS_VALIDATED = "VALIDATED"
STATUS_REJECTED = "REJECTED"
STATUS_QUARANTINED = "QUARANTINED"
STATUS_PROCESSED = "PROCESSED"

# Data provenance and trust labels
SOURCE_UNVERIFIED = "UNVERIFIED"
SOURCE_VERIFIED = "VERIFIED"
DATA_REAL = "REAL"
DATA_SYNTHETIC = "SYNTHETIC"

# Binary message classification labels
LABEL_HAM = "ham"
LABEL_SPAM = "spam"

# Safety defaults
DEFAULT_SAFE_MODE = True
ALLOW_AUTO_MODEL_PROMOTION = False
ALLOW_LIVE_EXECUTION = False
