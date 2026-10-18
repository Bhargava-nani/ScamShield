"""Bounded retry helpers for approved collection operations."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ..config import MAX_RETRIES
from ..exceptions import ValidationError


def retry_call(
    operation: Callable[..., Any],
    *args: Any,
    max_retries: int = MAX_RETRIES,
    delay_seconds: float = 0.25,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
    retry_if: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> Any:
    """Run an operation with a bounded number of retries.

    max_retries counts retries after the first attempt.
    A retry predicate can further restrict which failures are retried.
    """
    if not callable(operation):
        raise ValidationError("operation must be callable.")

    if (
        isinstance(max_retries, bool)
        or not isinstance(max_retries, int)
        or not 0 <= max_retries <= MAX_RETRIES
    ):
        raise ValidationError(
            f"max_retries must be between 0 and {MAX_RETRIES}."
        )

    if (
        isinstance(delay_seconds, bool)
        or not isinstance(delay_seconds, (int, float))
        or delay_seconds < 0
        or delay_seconds > 30
    ):
        raise ValidationError("delay_seconds must be between 0 and 30.")

    if not isinstance(retry_exceptions, tuple) or not retry_exceptions:
        raise ValidationError("retry_exceptions must be a non-empty tuple.")

    if not all(
        isinstance(exc_type, type) and issubclass(exc_type, Exception)
        for exc_type in retry_exceptions
    ):
        raise ValidationError("retry_exceptions contains an invalid exception type.")

    if retry_if is not None and not callable(retry_if):
        raise ValidationError("retry_if must be callable or None.")

    if not callable(sleep):
        raise ValidationError("sleep must be callable.")

    attempt = 0
    while True:
        try:
            return operation(*args, **kwargs)
        except retry_exceptions as exc:
            if attempt >= max_retries:
                raise
            if retry_if is not None and not retry_if(exc):
                raise

            # Small capped exponential backoff; never an unbounded loop.
            sleep(min(float(delay_seconds) * (2 ** attempt), 30.0))
            attempt += 1
