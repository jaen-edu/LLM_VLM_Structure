from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RetryError(RuntimeError):
    """Raised when retry attempts are exhausted."""


def call_with_retry(
    func: Callable[[], T],
    *,
    retries: int,
    delay_seconds: float,
    backoff: float = 1.5,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
    operation_name: str = "operation",
    logger: logging.Logger | None = None,
) -> T:
    """Execute a callable with retry semantics."""
    if retries < 1:
        raise ValueError("retries must be >= 1")

    attempt = 1
    wait = max(0.0, delay_seconds)
    while True:
        try:
            return func()
        except retry_exceptions as exc:
            if attempt >= retries:
                raise RetryError(f"{operation_name} failed after {attempt} attempts") from exc

            if logger is not None:
                logger.warning(
                    "%s failed on attempt %s/%s: %s. Retrying in %.2fs",
                    operation_name,
                    attempt,
                    retries,
                    exc,
                    wait,
                )

            time.sleep(wait)
            wait *= backoff
            attempt += 1
