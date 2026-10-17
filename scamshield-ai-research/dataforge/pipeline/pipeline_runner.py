
"""Local, review-gated DataForge pipeline orchestration.

This runner processes caller-supplied records only. It does not download data,
execute arbitrary jobs, train models, or promote models.
"""

from ..exceptions import ValidationError
from ..processing.deduplicator import deduplicate_records
from ..processing.quality_report import build_quality_report
from ..storage.repository import DatasetRepository


class PipelineRunner:
    """Coordinate validation, normalization, deduplication, review and storage."""

    def __init__(self, repository, job_manager):
        if not isinstance(repository, DatasetRepository):
            raise ValidationError("repository must be a DatasetRepository.")
        if not callable(getattr(job_manager, "create_job", None)):
            raise ValidationError("job_manager must support job creation.")
        if not callable(getattr(job_manager, "update_status", None)):
            raise ValidationError("job_manager must support status updates.")

        self.repository = repository
        self.job_manager = job_manager

    def run_records(self, records, metadata=None):
        """Process records and persist only when the quality gate passes.

        Invalid records or conflicting labels require review. In that case,
        nothing from this batch is committed to the repository.
        """
        if not isinstance(records, (list, tuple)):
            raise ValidationError("records must be a list or tuple.")

        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValidationError("metadata must be a dictionary.")

        # Caller metadata is allowed, but cannot override trusted audit fields.
        job_metadata = {
            **metadata,
            "input_count": len(records),
            "mode": "LOCAL_REVIEW_GATED",
        }

        job = self.job_manager.create_job(
            "dataset_processing",
            job_metadata,
        )
        job_id = job["job_id"]
        self.job_manager.update_status(job_id, "RUNNING")

        try:
            processed = deduplicate_records(records)
            quality = build_quality_report(processed)

            if quality["requires_review"]:
                reasons = ", ".join(quality["review_reasons"])
                message = (
                    f"Human review required: {reasons}. "
                    "No records from this batch were persisted."
                )
                failed_job = self.job_manager.update_status(
                    job_id, "FAILED", error=message
                )
                return {
                    "job": failed_job,
                    "quality_report": quality,
                    "storage": None,
                    "persisted": False,
                    "review_required": True,
                    "review_reasons": quality["review_reasons"],
                }

            storage_result = self.repository.add_records(processed["records"])
            succeeded_job = self.job_manager.update_status(
                job_id, "SUCCEEDED"
            )

            return {
                "job": succeeded_job,
                "quality_report": quality,
                "storage": storage_result,
                "persisted": True,
                "review_required": False,
                "review_reasons": [],
            }

        except Exception as exc:
            # Preserve the original failure if status persistence also fails.
            try:
                current = self.job_manager.get_job(job_id)
                if current["status"] in {"PENDING", "RUNNING"}:
                    self.job_manager.update_status(
                        job_id,
                        "FAILED",
                        error=f"{type(exc).__name__}: {exc}"[:1000],
                    )
            except Exception:
                pass
            raise
