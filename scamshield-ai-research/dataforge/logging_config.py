
"""Logging configuration for ScamShield DataForge."""

import logging
import os


LOGGER_NAME = "scamshield.dataforge"
DEFAULT_LOG_LEVEL = "INFO"


def configure_logging():
    """Configure DataForge logging without changing the root logger."""
    logger = logging.getLogger(LOGGER_NAME)

    level_name = os.environ.get(
        "DATAFORGE_LOG_LEVEL",
        DEFAULT_LOG_LEVEL,
    ).upper()

    level = getattr(logging, level_name, None)

    if not isinstance(level, int) or level < 0:
        raise ValueError(
            f"Invalid DATAFORGE_LOG_LEVEL: {level_name}"
        )

    logger.setLevel(level)
    logger.propagate = False

    # Avoid adding duplicate handlers if called repeatedly.
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )
        )
        logger.addHandler(handler)

    return logger
