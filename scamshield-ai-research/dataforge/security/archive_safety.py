"""Archive inspection without extracting untrusted archive contents."""

import stat
import tarfile
import zipfile
from pathlib import PurePosixPath

from ..config import MAX_ARCHIVE_FILES, MAX_DOWNLOAD_BYTES
from ..exceptions import ExtractionError, SecurityViolationError
from .file_security import validate_file_path


MAX_UNCOMPRESSED_BYTES = MAX_DOWNLOAD_BYTES * 10
MAX_COMPRESSION_RATIO = 200


def _validate_member_name(name):
    """Reject absolute paths, traversal paths, and Windows drive paths."""
    if not isinstance(name, str) or not name or "\x00" in name:
        raise SecurityViolationError("Archive contains an invalid member name.")

    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)

    if (
        normalized.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or (path.parts and ":" in path.parts[0])
    ):
        raise SecurityViolationError(
            "Archive contains an unsafe path."
        )


def inspect_archive(
    candidate,
    allowed_root,
    max_files=MAX_ARCHIVE_FILES,
    max_uncompressed_bytes=MAX_UNCOMPRESSED_BYTES,
):
    """Inspect ZIP or TAR metadata. Never extracts archive contents."""
    if max_files < 1 or max_uncompressed_bytes < 0:
        raise ValueError("Archive limits are invalid.")

    archive_path = validate_file_path(
        candidate,
        allowed_root,
        max_bytes=MAX_DOWNLOAD_BYTES,
    )

    try:
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path) as archive:
                members = archive.infolist()

                if len(members) > max_files:
                    raise SecurityViolationError(
                        "Archive contains too many entries."
                    )

                total_size = 0

                for member in members:
                    _validate_member_name(member.filename)

                    unix_mode = member.external_attr >> 16
                    if stat.S_ISLNK(unix_mode):
                        raise SecurityViolationError(
                            "Symbolic links inside archives are not permitted."
                        )

                    if member.flag_bits & 0x1:
                        raise ExtractionError(
                            "Encrypted ZIP entries are not supported."
                        )

                    if member.file_size < 0 or member.compress_size < 0:
                        raise ExtractionError("Archive contains invalid size metadata.")

                    total_size += member.file_size

                    if total_size > max_uncompressed_bytes:
                        raise SecurityViolationError(
                            "Archive exceeds the uncompressed-size limit."
                        )

                    if member.file_size > 0:
                        if member.compress_size == 0:
                            raise SecurityViolationError(
                                "Archive contains suspicious compression metadata."
                            )

                        ratio = member.file_size / member.compress_size
                        if ratio > MAX_COMPRESSION_RATIO:
                            raise SecurityViolationError(
                                "Archive compression ratio exceeds the safety limit."
                            )

                return {
                    "format": "zip",
                    "entry_count": len(members),
                    "uncompressed_bytes": total_size,
                    "extracted": False,
                }

        if tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, mode="r:*") as archive:
                members = archive.getmembers()

                if len(members) > max_files:
                    raise SecurityViolationError(
                        "Archive contains too many entries."
                    )

                total_size = 0

                for member in members:
                    _validate_member_name(member.name)

                    if member.issym() or member.islnk():
                        raise SecurityViolationError(
                            "Links inside archives are not permitted."
                        )

                    if not (member.isfile() or member.isdir()):
                        raise SecurityViolationError(
                            "Special archive entries are not permitted."
                        )

                    if member.size < 0:
                        raise ExtractionError("Archive contains invalid size metadata.")

                    total_size += member.size

                    if total_size > max_uncompressed_bytes:
                        raise SecurityViolationError(
                            "Archive exceeds the uncompressed-size limit."
                        )

                return {
                    "format": "tar",
                    "entry_count": len(members),
                    "uncompressed_bytes": total_size,
                    "extracted": False,
                }

    except (SecurityViolationError, ExtractionError):
        raise
    except (OSError, EOFError, ValueError, zipfile.BadZipFile, tarfile.TarError) as exc:
        raise ExtractionError("Archive is malformed or cannot be inspected.") from exc

    raise ExtractionError("Unsupported archive format; ZIP and TAR are supported.")