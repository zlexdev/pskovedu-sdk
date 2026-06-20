"""CircuitBreaker — per-(host, path) circuit breaker.

Protects gosuslugi.ru infrastructure (ESIA SSE, QR, SFD session) from
cascading failure storms.  After ``failure_threshold`` consecutive failures
the breaker opens for ``recovery_s`` seconds.  All requests during the open
state raise :exc:`~pskovedu.exceptions.BreakerOpen` immediately.

The breaker is keyed by ``(host, path)`` to allow fine-grained control.
``ClientConfig.breaker_hosts`` lists hosts that are enrolled by default
(``esia.gosuslugi.ru``, ``sfd.gosuslugi.ru``).

Usage::

    breaker = CircuitBreaker(failure_threshold=5, recovery_s=30)
    breaker.enroll("esia.gosuslugi.ru", "/qr-delegate/qr/subscribe")

    async def call():
        breaker.before_call("esia.gosuslugi.ru", "/qr-delegate/qr/subscribe")
        try:
            result = await transport.send(req)
            breaker.on_success("esia.gosuslugi.ru", "/qr-delegate/qr/subscribe")
            return result
        except Exception as exc:
            breaker.on_failure("esia.gosuslugi.ru", "/qr-delegate/qr/subscribe")
            raise
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from ..exceptions import BreakerOpen
from ..logging import get_logger

log = get_logger(__name__)


class _State(Enum):
    CLOSED = "closed"  # normal: requests pass through
    OPEN = "open"  # tripped: requests rejected immediately
    HALF_OPEN = "half_open"  # recovery probe: one request allowed


@dataclass
class _BreakerEntry:
    """Internal state for one (host, path) circuit."""

    state: _State = _State.CLOSED
    failure_count: int = 0
    last_failure_at: float = 0.0
    last_probe_at: float = 0.0


class CircuitBreaker:
    """Per-(host, path) circuit breaker with exponential-like open window.

    Thread-safe for single-threaded async use (no locks needed for
    ``asyncio`` coroutines on a single event loop).

    Args:
        failure_threshold: consecutive failures before opening the circuit.
        recovery_s: seconds to wait in OPEN state before allowing a probe.
        enrolled_hosts: set of hostnames whose paths are enrolled by default.
            Paths not explicitly enrolled are treated as CLOSED (pass-through).
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_s: float = 30.0,
        enrolled_hosts: frozenset[str] | None = None,
    ) -> None:
        self._threshold = failure_threshold
        self._recovery = recovery_s
        self._enrolled_hosts = enrolled_hosts or frozenset()
        self._circuits: dict[tuple[str, str], _BreakerEntry] = {}

    def enroll(self, host: str, path: str) -> None:
        """Enroll a ``(host, path)`` pair in the breaker (idempotent).

        Args:
            host: hostname (e.g. ``"esia.gosuslugi.ru"``).
            path: URL path prefix (e.g. ``"/qr-delegate"``).
        """
        key = (host, path)
        if key not in self._circuits:
            self._circuits[key] = _BreakerEntry()
            log.debug("breaker.enrolled", host=host, path=path)

    def _key_for(self, host: str, path: str) -> tuple[str, str] | None:
        """Return the registered ``(host, path)`` key matching this call, or ``None``."""
        # Exact match first
        key = (host, path)
        if key in self._circuits:
            return key
        # Prefix match (breaker registered for a path prefix)
        for registered_host, registered_path in self._circuits:
            if registered_host == host and path.startswith(registered_path):
                return (registered_host, registered_path)
        if host in self._enrolled_hosts:
            self.enroll(host, "/")
            return (host, "/")
        return None

    def before_call(self, host: str, path: str) -> None:
        """Check breaker state before a call.  Raises :exc:`BreakerOpen` if tripped.

        Args:
            host: target hostname.
            path: request path.

        Raises:
            BreakerOpen: when the circuit is OPEN and recovery time has not elapsed.
        """
        key = self._key_for(host, path)
        if key is None:
            return  # not enrolled — pass through

        entry = self._circuits[key]

        if entry.state == _State.OPEN:
            now = time.monotonic()
            if now - entry.last_failure_at >= self._recovery:
                # Transition to HALF_OPEN to allow one probe
                entry.state = _State.HALF_OPEN
                entry.last_probe_at = now
                log.info("breaker.half_open", host=host, path=path)
            else:
                remaining = self._recovery - (now - entry.last_failure_at)
                log.warning(
                    "breaker.open_reject", host=host, path=path, recovery_in_s=round(remaining, 1)
                )
                raise BreakerOpen(host=host, path=path)

        elif entry.state == _State.HALF_OPEN:
            now = time.monotonic()
            if now - entry.last_probe_at < self._recovery:
                # Still in probe window — allow (only one probe at a time)
                pass
            else:
                # Probe window expired without success; re-open
                entry.state = _State.OPEN
                entry.last_failure_at = now
                raise BreakerOpen(host=host, path=path)

    def on_success(self, host: str, path: str) -> None:
        """Record a successful call.  Resets failure count; closes circuit if HALF_OPEN.

        Args:
            host: target hostname.
            path: request path.
        """
        key = self._key_for(host, path)
        if key is None:
            return

        entry = self._circuits[key]
        if entry.state != _State.CLOSED:
            log.info("breaker.closed", host=host, path=path, was=entry.state.value)
        entry.state = _State.CLOSED
        entry.failure_count = 0

    def on_failure(self, host: str, path: str) -> None:
        """Record a failed call.  Opens the circuit if threshold is reached.

        Args:
            host: target hostname.
            path: request path.
        """
        key = self._key_for(host, path)
        if key is None:
            return

        entry = self._circuits[key]
        entry.failure_count += 1
        entry.last_failure_at = time.monotonic()

        if entry.failure_count >= self._threshold or entry.state == _State.HALF_OPEN:
            entry.state = _State.OPEN
            log.warning(
                "breaker.opened",
                host=host,
                path=path,
                failures=entry.failure_count,
                recovery_s=self._recovery,
            )

    def state(self, host: str, path: str) -> str:
        """Return the current breaker state string for ``(host, path)``.

        Returns ``"closed"`` when the pair is not enrolled.

        Args:
            host: target hostname.
            path: request path.
        """
        key = self._key_for(host, path)
        if key is None:
            return _State.CLOSED.value
        return self._circuits[key].state.value

    def reset(self, host: str, path: str) -> None:
        """Manually reset the circuit for ``(host, path)`` to CLOSED.

        Useful in tests and admin tooling.

        Args:
            host: target hostname.
            path: request path.
        """
        key = self._key_for(host, path)
        if key is not None:
            self._circuits[key] = _BreakerEntry()
            log.info("breaker.reset", host=host, path=path)
