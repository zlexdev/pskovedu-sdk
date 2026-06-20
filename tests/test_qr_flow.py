"""Tests for the QR authentication flow on FakeSession.

Coverage:
- Import/attribute sanity (no AttributeError/ImportError from qr or solver).
- QrGenerate / QrConfirm / QrEvent model parsing.
- GenerateQr POST via FakeSession -> correct URL + model.
- ConfirmQr POST via FakeSession -> correct URL + body + model.
- SSE stream open_stream yields raw SseEvent frames.
- End-to-end login_with_qr using the normal FakeSession (both source defects
  fixed in auth/solvers/qr.py and transport/sse.py).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from pskovedu.client import Client
from pskovedu.config import ClientConfig
from pskovedu.models.enums import QrEventKind
from pskovedu.models.esia import QrConfirm, QrEvent, QrGenerate
from pskovedu.protocol.base import RawResponse

from .conftest import FakeSession, json_response, sse_lines_for_qr_confirmed

_VALID_QR_ID = "11111111-2222-3333-4444-555555555555"


def _make_generate_response(qr_id: str = _VALID_QR_ID) -> RawResponse:
    return json_response({"qrId": qr_id})


def _make_confirm_response(x1_sso: str = "fake-x1-sso-token") -> RawResponse:
    return json_response({"x1_sso": x1_sso})


def _patch_auth_network(monkeypatch: Any, x1_sso_token: str = "fake-x1-sso-token") -> None:
    """Patch out the two network calls that happen outside FakeSession.

    1. AuthManager._obtain_jwt makes a real httpx call to GET /session for a JWT.
       We stub it to a no-op (COOKIE_ONLY state is enough for our tests).
    2. Client.get_shell (called at the end of login_with_qr) makes a
       make_request call that goes through the AuthManager ensure path again.
       We stub it to return a minimal ShellConfig-like object so the call succeeds.
    """
    from pskovedu.auth import manager as auth_manager_mod

    async def _noop_obtain_jwt(self: Any, client: Any) -> None:
        pass

    monkeypatch.setattr(auth_manager_mod.AuthManager, "_obtain_jwt", _noop_obtain_jwt)

    import types

    fake_shell_obj = types.SimpleNamespace(role_meta=None)

    async def _fake_get_shell(self: Any) -> Any:
        return fake_shell_obj

    import pskovedu.client as client_mod

    monkeypatch.setattr(client_mod.Client, "get_shell", _fake_get_shell)


def test_qr_module_importable() -> None:
    import pskovedu.methods.qr as qr_module  # noqa: F401

    assert hasattr(qr_module, "GenerateQr")
    assert hasattr(qr_module, "ConfirmQr")
    assert hasattr(qr_module, "QrAuthEvent")
    assert hasattr(qr_module, "SubscribeQr")


def test_qr_solver_importable() -> None:
    from pskovedu.auth.solvers.qr import QrSolver  # noqa: F401

    assert QrSolver is not None


def test_display_callback_type_importable() -> None:
    from pskovedu.auth.solvers.qr import DisplayCallback  # noqa: F401

    assert DisplayCallback is not None


def test_qr_auth_event_has_event_model() -> None:
    from pskovedu.methods.qr import QrAuthEvent
    from pskovedu.models.esia import QrEvent

    assert QrAuthEvent.__event_model__ is QrEvent


def test_qr_auth_event_terminal_event() -> None:
    from pskovedu.methods.qr import QrAuthEvent

    assert QrAuthEvent.__terminal_event__ == "qr-auth-confirmed"


def test_subscribe_qr_is_alias_for_qr_auth_event() -> None:
    from pskovedu.methods.qr import QrAuthEvent, SubscribeQr

    assert SubscribeQr is QrAuthEvent


def test_confirm_qr_body_fields() -> None:
    from pskovedu.methods.qr import ConfirmQr

    assert "code" in ConfirmQr.__body_fields__


def test_qr_generate_parses_qr_id() -> None:
    gen = QrGenerate.model_validate({"qrId": _VALID_QR_ID})
    assert gen.qr_id == _VALID_QR_ID


def test_qr_confirm_parses_x1_sso() -> None:
    confirm = QrConfirm.model_validate({"x1_sso": "my-sso-token"})
    assert confirm.x1_sso == "my-sso-token"


def test_qr_confirm_x1_sso_none_by_default() -> None:
    confirm = QrConfirm.model_validate({})
    assert confirm.x1_sso is None


def test_qr_event_confirmed_lax() -> None:
    """QrEvent parses correctly in lax (non-strict) mode from JSON strings."""
    event = QrEvent.model_validate(
        {"kind": "qr-auth-confirmed", "data": "", "code": "MYCODE"}, strict=False
    )
    assert event.kind == QrEventKind.QR_AUTH_CONFIRMED
    assert event.code == "MYCODE"
    assert event.is_confirmed is True
    assert event.is_error is False


def test_qr_event_error_lax() -> None:
    event = QrEvent.model_validate({"kind": "qr-error", "data": "timeout"}, strict=False)
    assert event.kind == QrEventKind.QR_ERROR
    assert event.is_error is True


def test_qr_event_ping_lax() -> None:
    event = QrEvent.model_validate({"kind": "ping", "data": ""}, strict=False)
    assert event.kind == QrEventKind.PING


def test_qr_event_waiting_lax() -> None:
    event = QrEvent.model_validate({"kind": "waiting", "data": ""}, strict=False)
    assert event.kind == QrEventKind.WAITING


def test_qr_event_from_enum_instance() -> None:
    """QrEvent validates correctly when kind is already a QrEventKind instance."""
    event = QrEvent.model_validate({"kind": QrEventKind.QR_AUTH_CONFIRMED, "data": "", "code": "X"})
    assert event.kind == QrEventKind.QR_AUTH_CONFIRMED
    assert event.code == "X"


@pytest.mark.asyncio
async def test_generate_qr_request(fake_client, fake_session) -> None:
    """GenerateQr POST to /qr/generate returns QrGenerate."""
    from pskovedu.methods.qr import GenerateQr

    fake_session.enqueue(_make_generate_response(qr_id=_VALID_QR_ID))
    result = await fake_client(GenerateQr())

    req = fake_session.sent_requests[-1]
    assert "/qr/generate" in req.url
    assert req.method == "POST"
    assert isinstance(result, QrGenerate)
    assert result.qr_id == _VALID_QR_ID


@pytest.mark.asyncio
async def test_confirm_qr_request(fake_client, fake_session) -> None:
    """ConfirmQr POST to /qr/confirm returns QrConfirm with x1_sso."""
    from pskovedu.methods.qr import ConfirmQr

    fake_session.enqueue(_make_confirm_response(x1_sso="sso-from-confirm"))
    result = await fake_client(ConfirmQr(code="TESTCODE"))

    req = fake_session.sent_requests[-1]
    assert "/qr/confirm" in req.url
    assert req.method == "POST"
    assert isinstance(result, QrConfirm)
    assert result.x1_sso == "sso-from-confirm"


@pytest.mark.asyncio
async def test_confirm_qr_body_has_code(fake_client, fake_session) -> None:
    """ConfirmQr includes 'code' in the request body."""
    from pskovedu.methods.qr import ConfirmQr

    fake_session.enqueue(_make_confirm_response())
    await fake_client(ConfirmQr(code="MY_CODE"))

    req = fake_session.sent_requests[-1]
    assert req.body is not None
    body_str = json.dumps(req.body) if isinstance(req.body, dict) else str(req.body)
    assert "MY_CODE" in body_str


@pytest.mark.asyncio
async def test_open_stream_yields_sse_events(fake_client, fake_session) -> None:
    """FakeSession open_stream yields at least one SseEvent with event name set."""
    from pskovedu.methods.qr import SubscribeQr

    fake_session.enqueue_sse(sse_lines_for_qr_confirmed(code="ACODE"))
    stream = await fake_client.session.open_stream(fake_client, SubscribeQr(uuid=_VALID_QR_ID))

    events = []
    async for event in stream:
        events.append(event)

    assert events, "Expected at least one SseEvent from the stream"
    event_names = [e.event for e in events]
    assert "qr-auth-confirmed" in event_names


@pytest.mark.asyncio
async def test_open_stream_subscribe_url_contains_uuid(fake_client, fake_session) -> None:
    """The SSE subscription request URL must contain the QR UUID."""
    from pskovedu.methods.qr import SubscribeQr

    fake_session.enqueue_sse([])
    await fake_client.session.open_stream(fake_client, SubscribeQr(uuid=_VALID_QR_ID))

    req = fake_session.sent_requests[-1]
    assert _VALID_QR_ID in req.url


@pytest.mark.asyncio
async def test_login_with_qr_full_flow(monkeypatch) -> None:
    """Full generate -> SSE -> confirm -> cookie flow on FakeSession (no monkeypatch for solver)."""
    _patch_auth_network(monkeypatch)

    qr_id = _VALID_QR_ID
    x1_sso_token = "x1-sso-e2e-token"
    code = "E2E_CODE_123"

    session = FakeSession()
    session.enqueue(_make_generate_response(qr_id=qr_id))
    session.enqueue_sse(sse_lines_for_qr_confirmed(code=code))
    session.enqueue(_make_confirm_response(x1_sso=x1_sso_token))

    client = Client(config=ClientConfig())
    client._session = session

    display_calls: list[str] = []

    def display_cb(url: str) -> None:
        display_calls.append(url)

    await client.login_with_qr(display_cb=display_cb)

    # display_cb was called with a string URL
    assert len(display_calls) == 1
    assert isinstance(display_calls[0], str)

    # X1_SSO cookie was injected into the auth manager's jar
    assert client._auth_manager is not None
    jar_cookies = client._auth_manager.jar.to_dict()
    assert jar_cookies.get("X1_SSO") == x1_sso_token

    # GenerateQr and ConfirmQr requests were made
    urls = [r.url for r in session.sent_requests]
    assert any("/qr/generate" in u for u in urls)
    assert any("/qr/confirm" in u for u in urls)


@pytest.mark.asyncio
async def test_login_with_qr_no_display_cb(monkeypatch) -> None:
    """login_with_qr works with display_cb=None."""
    _patch_auth_network(monkeypatch)

    session = FakeSession()
    session.enqueue(_make_generate_response())
    session.enqueue_sse(sse_lines_for_qr_confirmed())
    session.enqueue(_make_confirm_response())

    client = Client(config=ClientConfig())
    client._session = session

    await client.login_with_qr(display_cb=None)
    assert client._auth_manager is not None
    jar_cookies = client._auth_manager.jar.to_dict()
    assert jar_cookies.get("X1_SSO") == "fake-x1-sso-token"


@pytest.mark.asyncio
async def test_login_with_qr_async_display_cb(monkeypatch) -> None:
    """Async display_cb is awaited without error."""
    _patch_auth_network(monkeypatch)

    session = FakeSession()
    session.enqueue(_make_generate_response())
    session.enqueue_sse(sse_lines_for_qr_confirmed())
    session.enqueue(_make_confirm_response())

    client = Client(config=ClientConfig())
    client._session = session

    calls: list[str] = []

    async def async_cb(url: str) -> None:
        calls.append(url)

    await client.login_with_qr(display_cb=async_cb)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_login_with_qr_subscribe_url_contains_qr_id(monkeypatch) -> None:
    """The SSE subscription request URL embeds the QR UUID."""
    _patch_auth_network(monkeypatch)

    qr_id = "12345678-1234-5678-1234-567812345678"

    session = FakeSession()
    session.enqueue(_make_generate_response(qr_id=qr_id))
    session.enqueue_sse(sse_lines_for_qr_confirmed())
    session.enqueue(_make_confirm_response())

    client = Client(config=ClientConfig())
    client._session = session

    await client.login_with_qr()

    subscribe_reqs = [r for r in session.sent_requests if "/qr/subscribe" in r.url]
    assert subscribe_reqs, "Subscribe request not found"
    assert qr_id in subscribe_reqs[0].url
