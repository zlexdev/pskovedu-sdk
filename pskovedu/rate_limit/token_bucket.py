"""TokenBucket — per-host async token-bucket rate limiter.

One bucket per logical host name (from ``ClientConfig.hosts`` keys).
Rate is set by ``ClientConfig.rate_limit_rps``; ``None`` disables limiting.

The bucket refills continuously at ``rate_rps`` tokens per second.
``acquire()`` is called before every outgoing request; it blocks (``asyncio.sleep``)
until a token is available.

Usage::

    limiter = HostRateLimiter(rate_rps=4.0)
    await limiter.acquire("portal")  # before every request to the portal host
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from ..logging import get_logger

log = get_logger(__name__)


@dataclass
class _Bucket:
    """Internal token-bucket state for one host."""

    rate_rps: float  # tokens per second
    capacity: float  # max tokens (burst = 1 second of rate)
    tokens: float  # current available tokens
    last_refill: float = field(default_factory=time.monotonic)

    def refill(self) -> None:
        """Add tokens earned since the last call."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_rps)
        self.last_refill = now

    def consume(self) -> float:
        """Consume one token and return the wait time in seconds (0 if available)."""
        self.refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return 0.0
        return (1.0 - self.tokens) / self.rate_rps


class HostRateLimiter:
    """Async per-host token-bucket rate limiter.

    Maintains a separate bucket per host key.  Hosts not in the bucket map
    get a bucket lazily on first ``acquire()`` call.

    Args:
        rate_rps: default requests-per-second rate.  ``None`` disables rate
            limiting globally (all ``acquire()`` calls return immediately).
        host_overrides: optional ``{host: rps}`` dict to set per-host rates
            different from the default.
    """

    def __init__(
        self,
        rate_rps: float | None = 4.0,
        host_overrides: dict[str, float] | None = None,
    ) -> None:
        self._default_rps = rate_rps
        self._overrides = host_overrides or {}
        self._buckets: dict[str, _Bucket] = {}

    def _bucket_for(self, host: str) -> _Bucket | None:
        """Return (and lazily create) the bucket for *host*, or ``None`` when disabled."""
        rps = self._overrides.get(host, self._default_rps)
        if rps is None:
            return None
        if host not in self._buckets:
            self._buckets[host] = _Bucket(
                rate_rps=rps,
                capacity=max(1.0, rps),  # burst = 1 second worth of rate
                tokens=max(1.0, rps),  # start full
            )
        return self._buckets[host]

    async def acquire(self, host: str) -> None:
        """Acquire a token for *host*, sleeping until one is available.

        A no-op when rate limiting is disabled (``rate_rps=None``).

        Args:
            host: logical host key (e.g. ``"portal"``, ``"esia"``).
        """
        bucket = self._bucket_for(host)
        if bucket is None:
            return

        wait = bucket.consume()
        if wait > 0.0:
            log.debug("rate_limit.waiting", host=host, wait_s=round(wait, 3))
            await asyncio.sleep(wait)
            # After sleeping, consume the token that is now available
            bucket.consume()

    def set_rate(self, host: str, rps: float) -> None:
        """Update the rate for *host* at runtime.

        Replaces the bucket (resets token count to the new capacity).

        Args:
            host: logical host key.
            rps: new requests-per-second rate.
        """
        self._overrides[host] = rps
        self._buckets.pop(host, None)  # will be recreated on next acquire
        log.info("rate_limit.rate_updated", host=host, rps=rps)

    def disable(self, host: str | None = None) -> None:
        """Disable rate limiting for *host* (or globally when ``host=None``).

        Args:
            host: specific host to disable, or ``None`` to disable globally.
        """
        if host is None:
            self._default_rps = None
            self._buckets.clear()
        else:
            self._overrides[host] = None  # type: ignore[assignment]
            self._buckets.pop(host, None)
