"""Tests for public Client API surface (task X2).

Coverage:
- Snapshot a few pre-existing Client method signatures via inspect.signature.
- Assert two whitelisted changes are present:
    * AuthManager.login_with_qr(client, *, display_cb=...)
    * Client.__call__ returns a non-coroutine handle (_MethodCall).
- T-CALL regression: `async for x in client(DiaryPages(...))` streams items
  by iterating the PageIterator returned by the paginated method.
"""

from __future__ import annotations

import inspect
import json
from datetime import date
from typing import Any

from pskovedu.protocol.base import RawResponse

from .conftest import json_response

_PARTICIPANT_GUID = "ABCD1234EFAB1234EFAB1234EFAB1234"


def test_get_diary_signature() -> None:
    """get_diary(participant_guid, *, date=None) — shape must not regress."""
    from pskovedu.client import Client

    sig = inspect.signature(Client.get_diary)
    params = sig.parameters

    assert "participant_guid" in params, "get_diary must have participant_guid param"
    assert "date" in params, "get_diary must have date keyword param"
    assert params["date"].default is None, "date default must be None"
    # date is keyword-only
    assert params["date"].kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def test_get_schedule_signature() -> None:
    """get_schedule(grade_guid, *, date=None) — shape must not regress."""
    from pskovedu.client import Client

    sig = inspect.signature(Client.get_schedule)
    params = sig.parameters

    assert "grade_guid" in params, "get_schedule must have grade_guid param"
    assert "date" in params, "get_schedule must have date keyword param"
    assert params["date"].default is None


def test_get_marks_report_signature() -> None:
    """get_marks_report(participant_guid, *, with_dates=False) — shape must not regress."""
    from pskovedu.client import Client

    sig = inspect.signature(Client.get_marks_report)
    params = sig.parameters

    assert "participant_guid" in params
    assert "with_dates" in params
    assert params["with_dates"].default is False


def test_auth_manager_login_with_qr_has_display_cb() -> None:
    """AuthManager.login_with_qr must accept (client, *, display_cb=None)."""
    from pskovedu.auth.manager import AuthManager

    sig = inspect.signature(AuthManager.login_with_qr)
    params = sig.parameters

    assert "display_cb" in params, (
        "AuthManager.login_with_qr must have display_cb keyword param"
    )
    assert params["display_cb"].default is None, "display_cb default must be None"
    assert params["display_cb"].kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def test_client_login_with_qr_has_display_cb() -> None:
    """Client.login_with_qr must accept *, display_cb=None (delegating to AuthManager)."""
    from pskovedu.client import Client

    sig = inspect.signature(Client.login_with_qr)
    params = sig.parameters

    assert "display_cb" in params
    assert params["display_cb"].default is None


def test_client_call_returns_non_coroutine(fake_client, enqueue_response) -> None:
    """Client.__call__ must return a _MethodCall (not a coroutine/awaitable directly).

    The handle must be awaitable AND async-iterable — but it is not a coroutine object.
    """
    import inspect as _inspect

    from pskovedu.methods.util import CheckAuth

    # __call__ should return synchronously without needing a response enqueued
    handle = fake_client(CheckAuth(value="test"))

    assert not _inspect.iscoroutine(handle), (
        "Client.__call__ must return a _MethodCall handle, not a bare coroutine"
    )
    assert hasattr(handle, "__await__"), "Handle must be awaitable"
    assert hasattr(handle, "__aiter__"), "Handle must be async-iterable"


async def test_client_call_awaitable(fake_client, enqueue_response) -> None:
    """await client(method) still works — backward-compatible with existing call sites."""
    from pskovedu.methods.util import CheckAuth

    enqueue_response(json_response({"valid": True}))
    result = await fake_client(CheckAuth(value="tok"))
    from pskovedu.models.util import AuthCheck

    assert isinstance(result, AuthCheck)
    assert result.valid is True


def _diary_week_payload(
    entries: list[dict],
    week_start: date = date(2025, 9, 1),
    week_end: date = date(2025, 9, 7),
) -> dict:
    """Build a minimal DiaryWeek wire payload with real ``date`` objects.

    DateWindow fields are ``date`` typed on an EduObject with strict=True, so
    Pydantic requires actual ``date`` instances — ISO strings are rejected in
    strict mode.  We pass native ``date`` objects directly in the json_body dict
    (RestProtocol uses json_body for model_validate, not the text/content bytes).
    """
    return {
        "participant_guid": _PARTICIPANT_GUID,
        "entries": entries,
        "date_window": {"start": week_start, "end": week_end},
    }


def _diary_raw_response(payload: dict) -> RawResponse:
    """Build a RawResponse whose json_body contains native Python date objects.

    ``json.dumps`` cannot serialise ``date``; we serialise the content separately
    using isoformat() for the wire bytes while keeping the original dict (with
    real ``date`` objects) in json_body so ``model_validate`` receives the right types.
    """

    def _default(obj: Any) -> Any:
        if isinstance(obj, date):
            return obj.isoformat()
        raise TypeError(f"Not serialisable: {obj!r}")

    raw_bytes = json.dumps(payload, default=_default, ensure_ascii=False).encode()
    return RawResponse(
        status=200,
        headers={"content-type": "application/json"},
        content=raw_bytes,
        text=raw_bytes.decode(),
        json_body=payload,
    )


def _entry(subject: str, entry_date: str = "01.09.2025") -> dict:
    return {
        "subject": subject,
        "entry_date": entry_date,
        "homework": None,
        "topic": None,
        "remark": None,
    }


async def test_t_call_diary_pages_streams_items(fake_client, enqueue_response) -> None:
    """async for x in client(DiaryPages(...)) yields DiaryEntry items.

    Enqueue two pages: the first page contains entries; the second is empty
    so _advance() returns None and iteration stops.
    """
    from pskovedu.methods.diary import DiaryPages
    from pskovedu.models.diary import DiaryEntry

    # Page 1: two entries
    page1 = _diary_week_payload(
        [_entry("Математика", "01.09.2025"), _entry("Физика", "02.09.2025")],
        week_start=date(2025, 9, 1),
        week_end=date(2025, 9, 7),
    )
    # Page 2: empty entries → _advance returns None → iteration stops
    page2 = _diary_week_payload([], week_start=date(2025, 9, 8), week_end=date(2025, 9, 14))

    enqueue_response(_diary_raw_response(page1))
    enqueue_response(_diary_raw_response(page2))

    collected: list[DiaryEntry] = []
    async for item in fake_client(DiaryPages(participant_guid=_PARTICIPANT_GUID)):
        collected.append(item)

    assert len(collected) == 2
    subjects = {e.subject for e in collected}
    assert subjects == {"Математика", "Физика"}
    assert all(isinstance(e, DiaryEntry) for e in collected)


async def test_t_call_custom_paginated_method_async_iter(
    fake_client, enqueue_response
) -> None:
    """Prove the __call__ async-iter path works for any PaginatedMethod subclass.

    Construct a tiny dummy PaginatedMethod that pages over a list of strings,
    exercising the _MethodCall.__aiter__ path without coupling to DiaryPages.
    """
    from pskovedu.methods._base import PaginatedMethod

    # We need a real API method for _first() / _advance(). Re-use CheckAuth
    # returning a two-element list. Because PaginatedMethod.emit() returns a
    # PageIterator that calls client() recursively, we stub _extract to return
    # items from the AuthCheck response and _advance to stop after one page.

    class _OnePageMethod(PaginatedMethod[str]):
        """Single-page dummy: fetches CheckAuth, extracts ["ok"] once, stops."""

        def _first(self):  # type: ignore[override]
            from pskovedu.methods.util import CheckAuth

            return CheckAuth(value="x")

        def _extract(self, page: Any) -> list[str]:
            return ["ok"] if getattr(page, "valid", False) else []

        def _advance(self, page: Any):  # type: ignore[override]
            return None  # stop after one page

    enqueue_response(json_response({"valid": True}))

    items: list[str] = []
    async for item in fake_client(_OnePageMethod()):
        items.append(item)

    assert items == ["ok"], f"Expected ['ok'], got {items!r}"


async def test_t_call_empty_paginated_method_yields_nothing(
    fake_client, enqueue_response
) -> None:
    """async for on a PaginatedMethod that extracts nothing yields no items."""
    from pskovedu.methods.diary import DiaryPages

    # Single page with no entries, _advance returns None.
    enqueue_response(_diary_raw_response(_diary_week_payload([], week_start=date(2025, 9, 1), week_end=date(2025, 9, 7))))

    items: list = []
    async for item in fake_client(DiaryPages(participant_guid=_PARTICIPANT_GUID)):
        items.append(item)

    assert items == []
