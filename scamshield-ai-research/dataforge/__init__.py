
"""ScamShield DataForge package initializer."""

from .config import (
    AUTO_MODEL_PROMOTION,
    LIVE_EXECUTION_ENABLED,
    PROJECT_DIR,
    RESEARCH_DIR,
    DATAFORGE_DIR,
)

from .constants import (
    DEFAULT_SAFE_MODE,
    DATA_REAL,
    DATA_SYNTHETIC,
)

__version__ = "0.1.0"

__all__ = [
    "AUTO_MODEL_PROMOTION",
    "LIVE_EXECUTION_ENABLED",
    "PROJECT_DIR",
    "RESEARCH_DIR",
    "DATAFORGE_DIR",
    "DEFAULT_SAFE_MODE",
    "DATA_REAL",
    "DATA_SYNTHETIC",
    "__version__",
]
