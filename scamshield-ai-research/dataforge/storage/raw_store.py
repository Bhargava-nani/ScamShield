
"""Safe raw artifact storage using content-addressed filenames."""

import os
import tempfile
from pathlib import Path

from ..config import RAW_DATA_DIR, MAX_DOWNLOAD_BYTES
from ..exceptions import StorageError, ValidationError
from ..security.file_security import calculate_sha256


def store_raw_bytes(content, storage_dir=None, max_bytes=MAX_DOWNLOAD_BYTES):
    """Store bytes atomically under their SHA-256 digest.

    The returned filename is derived from the content hash, not user input.
    Existing files are rehashed before being reused.
    """
    if not isinstance(content, bytes):
        raise ValidationError("Raw content must be bytes.")

    if len(content) > max_bytes:
        raise ValidationError("Raw content exceeds the permitted size.")

    root = Path(storage_dir or RAW_DATA_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)

    digest = __import__("hashlib").sha256(content).hexdigest()
    destination = root / f"{digest}.blob"

    if destination.exists():
        existing_digest = calculate_sha256(destination, root, max_bytes=max_bytes)
        if existing_digest != digest:
            raise StorageError("Existing content-addressed file failed integrity verification.")
        return {
            "path": str(destination),
            "sha256": digest,
            "size_bytes": len(content),
            "created": False,
        }

    temp_name = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=root,
            prefix=".dataforge-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        # Atomic creation without replacing an existing destination.
        try:
            os.link(temp_name, destination)
            created = True
        except FileExistsError:
            created = False

        if not created:
            existing_digest = calculate_sha256(
                destination, root, max_bytes=max_bytes
            )
            if existing_digest != digest:
                raise StorageError("Concurrent artifact failed integrity verification.")

        return {
            "path": str(destination),
            "sha256": digest,
            "size_bytes": len(content),
            "created": created,
        }

    except OSError as exc:
        raise StorageError("Unable to store raw artifact safely.") from exc

    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
