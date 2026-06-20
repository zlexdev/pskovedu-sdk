"""Test harness — FakeSession + fixtures for the pskovedu SDK test suite.

FakeSession is a drop-in BaseSession replacement that:
- _send(): returns canned RawResponse objects from a FIFO queue or a
  url-substring keyed dict.
- _open_sse(): returns a fake async streaming response that yields canned
  SSE text lines from an enqueued list.
- close(): no-op.

Fixtures:
- fake_session:       a fresh FakeSession per test.
- fake_client:        a Client whose _session is the fake_session.
- enqueue_response:   helper — push a canned RawResponse for the next _send call.
- enqueue_keyed:      helper — key a canned RawResponse by url-substring.
- enqueue_sse_lines:  helper — push canned SSE text lines for the next _open_sse call.
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any

import pytest

from pskovedu.client import Client
from pskovedu.config import ClientConfig
from pskovedu.protocol.base import PreparedRequest, RawResponse
from pskovedu.sessions.base import BaseSession


class _FakeSseResponse:
    """Mimics an httpx streaming response for SseStream consumption."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self.status_code = 200
        self._closed = False

    async def aiter_lines(self):  # type: ignore[override]
        for line in self._lines:
            yield line

    async def aclose(self) -> None:
        self._closed = True


class FakeSession(BaseSession):
    """Test-double for BaseSession.

    Responses can be enqueued in two ways:
    1. FIFO: push a RawResponse via enqueue(response).
    2. Keyed: register a RawResponse for a url-substring via enqueue_for(key, response).
       Key lookup takes priority over FIFO.

    SSE frames are enqueued via enqueue_sse(lines) — a list of raw line strings
    in SSE wire format (e.g. ["event: ping", "data: {}", "", "event: qr-auth-confirmed", ...]).
    """

    def __init__(self) -> None:
        super().__init__()
        self._fifo: deque[RawResponse] = deque()
        self._keyed: dict[str, RawResponse] = {}
        self._sse_fifo: deque[list[str]] = deque()

        # Recording for assertions
        self.sent_requests: list[PreparedRequest] = []

    def enqueue(self, response: RawResponse) -> None:
        """Push a RawResponse onto the FIFO queue."""
        self._fifo.append(response)

    def enqueue_for(self, url_key: str, response: RawResponse) -> None:
        """Register a RawResponse keyed by url-substring match."""
        self._keyed[url_key] = response

    def enqueue_sse(self, lines: list[str]) -> None:
        """Push a list of SSE text lines for the next _open_sse call."""
        self._sse_fifo.append(lines)

    async def _send(self, prepared: PreparedRequest, config: Any) -> RawResponse:
        self.sent_requests.append(prepared)

        # Check keyed responses first
        for key, resp in self._keyed.items():
            if key in prepared.url:
                return resp

        # Fall back to FIFO
        if self._fifo:
            return self._fifo.popleft()

        raise RuntimeError(
            f"FakeSession has no canned response for URL: {prepared.url!r}. "
            "Use enqueue() or enqueue_for() before making the call."
        )

    async def _open_sse(self, prepared: PreparedRequest) -> _FakeSseResponse:
        self.sent_requests.append(prepared)

        lines = self._sse_fifo.popleft() if self._sse_fifo else []
        return _FakeSseResponse(lines)

    async def close(self) -> None:
        pass


def json_response(payload: Any, status: int = 200) -> RawResponse:
    """Build a RawResponse with a JSON body."""
    body = json.dumps(payload).encode()
    return RawResponse(
        status=status,
        headers={"content-type": "application/json"},
        content=body,
        text=body.decode(),
        json_body=payload,
    )


def bytes_response(data: bytes, status: int = 200) -> RawResponse:
    """Build a RawResponse with a raw bytes body."""
    return RawResponse(
        status=status,
        headers={"content-type": "application/octet-stream"},
        content=data,
        text="",
        json_body=None,
    )


def html_response(html: str, status: int = 200) -> RawResponse:
    """Build a RawResponse with an HTML body."""
    return RawResponse(
        status=status,
        headers={"content-type": "text/html"},
        content=html.encode(),
        text=html,
        json_body=None,
    )


def sse_lines_for_qr_confirmed(code: str = "TESTCODE123") -> list[str]:
    """Build SSE wire lines for a qr-auth-confirmed event followed by stream end.

    The QrEvent DTO requires a ``kind`` field; we emit it in the data payload.
    """
    data = json.dumps({"kind": "qr-auth-confirmed", "data": "", "code": code})
    return [
        "event: ping",
        'data: {"kind": "ping", "data": ""}',
        "",
        "event: qr-auth-confirmed",
        f"data: {data}",
        "",
    ]


@pytest.fixture()
def fake_session() -> FakeSession:
    """Fresh FakeSession for each test."""
    return FakeSession()


@pytest.fixture()
def fake_client(fake_session: FakeSession) -> Client:
    """Client with _session wired to fake_session; no auth manager."""
    client = Client(config=ClientConfig())
    client._session = fake_session
    # Pre-set a cookie so the minimal cookie path injects X1_SSO without hitting auth
    client._cookies["X1_SSO"] = "fake-x1-sso"
    return client


@pytest.fixture()
def enqueue_response(fake_session: FakeSession):
    """Helper: push a RawResponse onto the fake session FIFO queue."""
    def _enqueue(response: RawResponse) -> None:
        fake_session.enqueue(response)
    return _enqueue


@pytest.fixture()
def enqueue_keyed(fake_session: FakeSession):
    """Helper: register a RawResponse keyed by url-substring."""
    def _enqueue(key: str, response: RawResponse) -> None:
        fake_session.enqueue_for(key, response)
    return _enqueue


@pytest.fixture()
def enqueue_sse(fake_session: FakeSession):
    """Helper: push SSE wire lines for the next open_stream call."""
    def _enqueue(lines: list[str]) -> None:
        fake_session.enqueue_sse(lines)
    return _enqueue
