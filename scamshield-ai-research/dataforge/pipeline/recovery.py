"""Conservative, read-only recovery inspection for DataForge."""

import os
from datetime import datetime, timezone
from pathlib import Path

from ..exceptions import StorageError, ValidationError


TEMPORARY_PREFIXES = (".dataforge-", ".dataset-")
TEMPORARY_SUFFIX = ".tmp"


def inspect_interrupted_writes(root, older_than_seconds=300, now=None):
    """Report old DataForge temporary files without changing the filesystem.

    This function deliberately performs no automatic cleanup. File age alone
    cannot prove that a temporary file is abandoned or not being written.
    """
    if (
        not isinstance(older_than_seconds, (int, float))
        or isinstance(older_than_seconds, bool)
        or older_than_seconds < 0
    ):
        raise ValidationError("older_than_seconds must be non-negative.")

    if now is None:
        now = datetime.now(timezone.utc)

    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValidationError("now must be a timezone-aware datetime.")

    root = Path(root).resolve()

    if not root.exists() or not root.is_dir():
        raise ValidationError("Recovery root must be an existing directory.")

    cutoff_time = now.timestamp()
    scanned_files = 0
    candidates = []

    def walk_error(error):
        raise StorageError("Unable to inspect recovery directory.") from error

    try:
        for current_dir, directories, filenames in os.walk(
            root, topdown=True, followlinks=False, onerror=walk_error
        ):
            current_path = Path(current_dir)

            # Do not traverse directory symlinks.
            directories[:] = [
                name for name in directories
                if not (current_path / name).is_symlink()
            ]

            for filename in filenames:
                if not (
                    filename.startswith(TEMPORARY_PREFIXES)
                    and filename.endswith(TEMPORARY_SUFFIX)
                ):
                    continue

                path = current_path / filename

                # Never inspect or report symlinks as recovery candidates.
                if path.is_symlink():
                    continue

                try:
                    stat = path.stat()
                except FileNotFoundError:
                    # Another process may have finished its write meanwhile.
                    continue
                except OSError as exc:
                    raise StorageError(
                        "Unable to inspect a temporary file."
                    ) from exc

                if not path.is_file():
                    continue

                scanned_files += 1
                age_seconds = max(0.0, cutoff_time - stat.st_mtime)

                if age_seconds < older_than_seconds:
                    continue

                candidates.append({
                    "path": path.relative_to(root).as_posix(),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, timezone.utc
                    ).isoformat(),
                    "age_seconds": int(age_seconds),
                    "status": "REVIEW_REQUIRED",
                    "automatic_cleanup": False,
                })

    except StorageError:
        raise
    except OSError as exc:
        raise StorageError("Unable to scan recovery directory.") from exc

    candidates.sort(key=lambda item: item["path"])

    return {
        "root": str(root),
        "scanned_files": scanned_files,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "automatic_cleanup": False,
    }
