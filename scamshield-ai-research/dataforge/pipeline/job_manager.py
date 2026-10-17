"""Persistent, conservative job tracking for DataForge.

Job tracking only: this module does not execute jobs or enable live operations.
The state file is intended for a single coordinating process; atomic replacement
does not provide cross-process locking.
"""

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from ..exceptions import StorageError, ValidationError
from ..storage.transactions import atomic_write_bytes


STATUSES = {"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "INTERRUPTED"}

ALLOWED_TRANSITIONS = {
    "PENDING": {"RUNNING", "FAILED", "INTERRUPTED"},
    "RUNNING": {"SUCCEEDED", "FAILED", "INTERRUPTED"},
    "SUCCEEDED": set(),
    "FAILED": set(),
    "INTERRUPTED": set(),
}


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def _validate_job_type(job_type):
    if (
        not isinstance(job_type, str)
        or not job_type.strip()
        or len(job_type) > 100
    ):
        raise ValidationError("job_type must be a non-empty string of at most 100 characters.")
    return job_type.strip()


def _validate_metadata(metadata):
    if metadata is None:
        return {}

    if not isinstance(metadata, dict):
        raise ValidationError("metadata must be a dictionary.")

    try:
        # Copy and validate JSON compatibility so callers cannot mutate stored data.
        return json.loads(json.dumps(metadata, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValidationError("metadata must contain valid JSON-compatible values.") from exc


class JobManager:
    """Persist job records without executing them."""

    def __init__(self, state_path):
        self.state_path = Path(state_path).resolve()
        self.state = {"schema_version": 1, "jobs": []}

        if self.state_path.exists():
            self._load()

    def _load(self):
        try:
            raw = self.state_path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise StorageError("Unable to read the job state file.") from exc

        self._validate_state(loaded)
        self.state = loaded

    @staticmethod
    def _validate_state(state):
        if (
            not isinstance(state, dict)
            or state.get("schema_version") != 1
            or not isinstance(state.get("jobs"), list)
        ):
            raise StorageError("Job state file has an unsupported or invalid structure.")

        seen_ids = set()
        required = {
            "job_id", "job_type", "status", "created_at",
            "updated_at", "metadata", "error",
        }

        for job in state["jobs"]:
            if not isinstance(job, dict) or not required.issubset(job):
                raise StorageError("Job state contains an invalid job record.")

            job_id = job["job_id"]
            if (
                not isinstance(job_id, str)
                or not job_id
                or job_id in seen_ids
            ):
                raise StorageError("Job state contains a missing or duplicate job ID.")
            seen_ids.add(job_id)

            if not isinstance(job["job_type"], str) or not job["job_type"].strip():
                raise StorageError("Job state contains an invalid job type.")

            if job["status"] not in STATUSES:
                raise StorageError("Job state contains an invalid status.")

            if not isinstance(job["created_at"], str) or not isinstance(job["updated_at"], str):
                raise StorageError("Job state contains invalid timestamps.")

            if not isinstance(job["metadata"], dict):
                raise StorageError("Job state contains invalid metadata.")

            if job["error"] is not None and not isinstance(job["error"], str):
                raise StorageError("Job state contains an invalid error field.")

    def _save(self):
        try:
            content = json.dumps(
                self.state,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValidationError("Job state cannot be serialized.") from exc

        atomic_write_bytes(self.state_path, content)

    def create_job(self, job_type, metadata=None):
        """Create a PENDING record. This does not execute the job."""
        job_type = _validate_job_type(job_type)
        metadata = _validate_metadata(metadata)
        now = _timestamp()

        job = {
            "job_id": uuid.uuid4().hex,
            "job_type": job_type,
            "status": "PENDING",
            "created_at": now,
            "updated_at": now,
            "metadata": metadata,
            "error": None,
        }

        self.state["jobs"].append(job)
        try:
            self._save()
        except Exception:
            self.state["jobs"].pop()
            raise

        return deepcopy(job)

    def get_job(self, job_id):
        """Return a copy of a job record, or raise ValidationError."""
        if not isinstance(job_id, str) or not job_id:
            raise ValidationError("job_id must be a non-empty string.")

        for job in self.state["jobs"]:
            if job["job_id"] == job_id:
                return deepcopy(job)

        raise ValidationError("Job was not found.")

    def list_jobs(self, status=None):
        """Return copied job records, optionally filtered by status."""
        if status is not None and status not in STATUSES:
            raise ValidationError("Unknown job status.")

        jobs = self.state["jobs"]
        if status is not None:
            jobs = [job for job in jobs if job["status"] == status]

        return deepcopy(jobs)

    def update_status(self, job_id, new_status, error=None):
        """Apply a valid state transition and persist it."""
        if new_status not in STATUSES:
            raise ValidationError("Unknown job status.")

        if error is not None and not isinstance(error, str):
            raise ValidationError("error must be a string or None.")

        job = None
        for candidate in self.state["jobs"]:
            if candidate["job_id"] == job_id:
                job = candidate
                break

        if job is None:
            raise ValidationError("Job was not found.")

        if new_status not in ALLOWED_TRANSITIONS[job["status"]]:
            raise ValidationError(
                f"Invalid job transition: {job['status']} -> {new_status}."
            )

        if new_status == "FAILED":
            if error is None or not error.strip():
                raise ValidationError("A non-empty error is required for FAILED jobs.")
        elif error is not None:
            raise ValidationError("error may only be supplied when marking a job FAILED.")

        previous = deepcopy(job)
        job["status"] = new_status
        job["updated_at"] = _timestamp()
        job["error"] = error

        try:
            self._save()
        except Exception:
            job.clear()
            job.update(previous)
            raise

        return deepcopy(job)

    def recover_interrupted_jobs(self):
        """Explicitly mark RUNNING records as INTERRUPTED after a restart.

        This is never performed automatically during manager initialization.
        """
        changed = []

        for job in self.state["jobs"]:
            if job["status"] == "RUNNING":
                previous = deepcopy(job)
                job["status"] = "INTERRUPTED"
                job["updated_at"] = _timestamp()
                job["error"] = None
                changed.append((job, previous))

        if not changed:
            return 0

        try:
            self._save()
        except Exception:
            for job, previous in changed:
                job.clear()
                job.update(previous)
            raise

        return len(changed)
