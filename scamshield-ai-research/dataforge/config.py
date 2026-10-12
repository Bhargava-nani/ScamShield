
"""Central configuration for ScamShield DataForge."""

from pathlib import Path


# DataForge package directory.
DATAFORGE_DIR = Path(__file__).resolve().parent

# Existing research project directory.
RESEARCH_DIR = DATAFORGE_DIR.parent

# Main ScamShield project directory.
PROJECT_DIR = RESEARCH_DIR.parent

# All DataForge-managed storage stays inside this module.
DATAFORGE_DATA_DIR = DATAFORGE_DIR / "data"

# Storage areas for future pipeline stages.
RAW_DATA_DIR = DATAFORGE_DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATAFORGE_DATA_DIR / "processed"
QUARANTINE_DIR = DATAFORGE_DATA_DIR / "quarantine"
MANIFESTS_DIR = DATAFORGE_DATA_DIR / "manifests"

# Conservative defaults. These are configuration limits,
# not proof that an input file is safe.
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024  # 25 MiB
MAX_ARCHIVE_FILES = 500
MAX_TEXT_LENGTH = 5000
DEFAULT_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3

# DataForge must not automatically promote a model.
AUTO_MODEL_PROMOTION = False

# DataForge must not access live execution or trading systems.
LIVE_EXECUTION_ENABLED = False
