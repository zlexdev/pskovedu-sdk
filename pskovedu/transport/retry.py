"""RetryPolicy — exponential backoff with jitter for transient failures.

Reads ``protocol.is_idempotent(method)`` to decide whether to retry.
Non-idempotent methods (POST writes) are never retried.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..exceptions import TransportError
from ..logging import get_logger

if TYPE_CHECKING:
    from ..methods._base import BaseMethod
    from ..protocol.base import Protocol

log = get_logger(__name__)

# Transient HTTP status codes that are safe to retry
_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


@dataclass
class RetryPolicy:
    """Configurable exponential-backoff retry policy.

    Args:
        max_retries: maximum number of retry attempts (0 = no retries).
        base_delay_s: initial backoff delay in seconds.
        max_delay_s: cap on backoff delay in seconds.
        jitter: when ``True``, adds ``random * base_delay_s`` to each delay
            so concurrent clients don't thunderherd on the same retry window.
        retryable_statuses: HTTP status codes considered transient.
    """

    max_retries: int = 2
    base_delay_s: float = 1.0
    max_delay_s: float = 30.0
    jitter: bool = True
    retryable_statuses: frozenset[int] = field(
        default_factory=lambda: frozenset(_RETRYABLE_STATUSES)
    )

    def is_retryable(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        protocol: Protocol,
        status: int | None = None,
        exc: BaseException | None = None,
    ) -> bool:
        """Return ``True`` when this request/failure combination may be retried.

        A request is retryable only when ALL of:
        1. The method is idempotent (``protocol.is_idempotent(method)``).
        2. The failure is a transient HTTP status OR a network-level exception.

        Args:
            method: the method instance being retried.
            protocol: the protocol instance to query for idempotency.
            status: HTTP status code of the failed response, or ``None``.
            exc: the exception raised, or ``None`` if status-based.
        """
        if not protocol.is_idempotent(method):
            return False
        if status is not None and status in self.retryable_statuses:
            return True
        return bool(
            exc is not None and isinstance(exc, (TransportError, OSError, asyncio.TimeoutError))
        )

    async def wait(self, attempt: int) -> None:
        """Sleep for the backoff duration for *attempt* (0-indexed).

        Args:
            attempt: the attempt number (0 = first retry after the initial try).
        """
        delay = min(self.base_delay_s * (2**attempt), self.max_delay_s)
        if self.jitter:
            delay += random.uniform(0, self.base_delay_s)
        log.debug(
            "retry.backoff",
            attempt=attempt + 1,
            delay_s=round(delay, 3),
        )
        await asyncio.sleep(delay)
