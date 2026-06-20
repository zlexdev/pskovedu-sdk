"""SSE transport — async Server-Sent Event stream parser.

Provides :class:`SseStream`, an async context manager that yields parsed
:class:`SseEvent` instances from an httpx streaming response.

The SSE wire format (RFC 8895 / W3C EventSource):
- Lines starting with ``data:`` carry event payload.
- Lines starting with ``event:`` name the event type.
- Lines starting with ``id:`` carry the last-event-id.
- Empty lines (``\\n``) dispatch the accumulated event.
- Lines starting with ``:`` are comments and are ignored.

Usage::

    async with SseStream(response, event_model=QrAuthEvent, terminal_event="qr-auth-confirmed") as stream:
        async for event in stream:
            if isinstance(event.parsed, QrAuthEvent):
                handle(event.parsed)
            # stream auto-closes when terminal event is received
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from ..logging import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class SseEvent:
    """A single parsed SSE event dispatched from the wire stream.

    Attributes:
        event: event type name from ``event:`` line, or ``"message"`` if absent.
        data: raw string data from ``data:`` line(s) joined with ``\\n``.
        id: last-event-id from ``id:`` line, or ``None``.
        retry: reconnection delay (ms) from ``retry:`` line, or ``None``.
        parsed: Pydantic model parsed from ``data`` as JSON, or ``None`` if
            parsing fails or no model is bound.
    """

    event: str = "message"
    data: str = ""
    id: str | None = None
    retry: int | None = None
    parsed: Any = None


class EventStream[T: BaseModel]:
    """Typed wrapper returned by :class:`SseStream` context manager.

    Iterating this yields :class:`SseEvent` instances where ``parsed`` is
    validated into ``T`` (when ``event_model`` is provided).

    **Not constructed directly** — obtain via ``async with SseStream(...) as stream``.
    """

    def __init__(
        self,
        _stream: SseStream[T],
    ) -> None:
        self._stream = _stream

    def __aiter__(self) -> AsyncIterator[SseEvent]:
        return self._stream._iter_events()


class SseStream[T: BaseModel]:
    """Async context manager that parses an httpx streaming response as SSE.

    Yields :class:`SseEvent` instances.  When ``terminal_event`` is set, the
    stream stops after yielding the matching event (inclusive) and the
    underlying HTTP response is closed cleanly.

    ``Always`` closes the response on exit, even when the caller breaks out
    of the async-for loop early.

    Args:
        response: an ``httpx.Response`` opened with ``stream=True``
            (i.e. entered as ``async with client.stream(...) as r``).
        event_model: optional Pydantic model to parse ``data`` JSON into.
            When ``None``, ``event.parsed`` is always ``None``.
        terminal_event: event ``type`` name that signals stream end.
            When matched, iteration stops after yielding that event.
    """

    def __init__(
        self,
        response: Any,  # httpx.Response in streaming mode
        event_model: type[T] | None = None,
        terminal_event: str | None = None,
    ) -> None:
        self._response = response
        self._event_model = event_model
        self._terminal_event = terminal_event
        self._closed = False

    async def __aenter__(self) -> EventStream[T]:
        return EventStream(self)

    async def __aexit__(self, *_: Any) -> None:
        await self._close()

    async def _close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                await self._response.aclose()
            except Exception:  # noqa: BLE001 — best-effort close
                log.warning("sse.close_error", response=repr(self._response))

    async def _iter_events(self) -> AsyncIterator[SseEvent]:
        """Yield parsed :class:`SseEvent` objects from the wire stream."""
        # Accumulated fields for the current event
        event_type: str = "message"
        data_lines: list[str] = []
        last_id: str | None = None
        retry: int | None = None

        try:
            async for raw_line in self._response.aiter_lines():
                line: str = raw_line.rstrip("\r\n")

                if not line:
                    # Empty line = dispatch event (if we have data)
                    if data_lines:
                        data = "\n".join(data_lines)
                        parsed = self._parse_data(data, event_type)

                        event = SseEvent(
                            event=event_type,
                            data=data,
                            id=last_id,
                            retry=retry,
                            parsed=parsed,
                        )

                        log.debug(
                            "sse.event",
                            event_type=event_type,
                            data_len=len(data),
                        )

                        yield event

                        if self._terminal_event and event_type == self._terminal_event:
                            log.info("sse.terminal", event_type=event_type)
                            return

                    # Reset for next event
                    event_type = "message"
                    data_lines = []
                    retry = None
                    continue

                if line.startswith(":"):
                    # Comment — ignore
                    continue

                if ":" in line:
                    field_name, _, value = line.partition(":")
                    value = value.lstrip(" ")  # strip exactly one leading space
                else:
                    field_name = line
                    value = ""

                match field_name:
                    case "event":
                        event_type = value
                    case "data":
                        data_lines.append(value)
                    case "id":
                        last_id = value
                    case "retry":
                        with contextlib.suppress(ValueError):
                            retry = int(value)
                    case _:
                        pass  # unknown field — ignore per spec

        finally:
            await self._close()

    def _parse_data(self, data: str, event_type: str) -> T | None:
        """Attempt to parse *data* as JSON into ``event_model``.

        Returns ``None`` when there is no model, data is empty, or
        JSON parsing / model validation fails.
        """
        if not self._event_model or not data:
            return None

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            log.debug("sse.data_not_json", event_type=event_type, data=data[:200])
            return None

        try:
            return self._event_model.model_validate(payload, strict=False)
        except Exception as exc:  # noqa: BLE001 — parse best-effort
            log.debug(
                "sse.model_validate_failed",
                event_type=event_type,
                model=self._event_model.__name__,
                error=str(exc),
            )
            return None
