
"""Small filesystem transaction helper for DataForge."""

import os
import tempfile
from pathlib import Path

from ..exceptions import StorageError, ValidationError


def atomic_write_bytes(destination, content):
    """Atomically replace a destination file with bytes.

    The temporary file is created in the destination directory so replacement
    occurs on the same filesystem.
    """
    if not isinstance(content, bytes):
        raise ValidationError("Transaction content must be bytes.")

    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".dataforge-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temporary_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temporary_path, destination)
        temporary_path = None
        return destination

    except OSError as exc:
        raise StorageError("Atomic file write failed.") from exc

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
