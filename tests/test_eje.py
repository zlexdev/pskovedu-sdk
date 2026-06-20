"""Tests for methods/eje.py — five EJE method-classes + EjeResult parsing."""

from __future__ import annotations

import pytest

from pskovedu.constants import (
    PATH_EJE_HOMEWORK,
    PATH_EJE_INTEGRATIONS,
    PATH_EJE_JOURNAL_PLANNER,
    PATH_EJE_PARTICIPANTS,
    PATH_EJE_TOPICS,
)
from pskovedu.methods.eje import (
    EjeHomework,
    EjeIntegrations,
    EjeJournalPlanner,
    EjeParticipants,
    EjeTopics,
)
from pskovedu.models.eje import EjeResult

from .conftest import json_response


def test_eje_result_defaults() -> None:
    r = EjeResult.model_validate({"success": True})
    assert r.success is True
    assert r.message is None
    assert r.data is None


def test_eje_result_with_list_data() -> None:
    payload = {"success": True, "message": "ok", "data": [{"id": 1}, {"id": 2}]}
    r = EjeResult.model_validate(payload)
    assert r.success is True
    assert r.message == "ok"
    assert isinstance(r.data, list)
    assert len(r.data) == 2


def test_eje_result_with_dict_data() -> None:
    payload = {"success": True, "data": {"count": 42, "items": []}}
    r = EjeResult.model_validate(payload)
    assert isinstance(r.data, dict)
    assert r.data["count"] == 42


def test_eje_result_with_null_data() -> None:
    payload = {"success": False, "message": "error", "data": None}
    r = EjeResult.model_validate(payload)
    assert r.success is False
    assert r.data is None


def test_eje_result_success_defaults_to_true() -> None:
    """success defaults to True when omitted from the response."""
    r = EjeResult.model_validate({})
    assert r.success is True


@pytest.mark.asyncio
async def test_eje_homework_url(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"success": True}))
    await fake_client(EjeHomework())
    req = fake_session.sent_requests[-1]
    assert PATH_EJE_HOMEWORK in req.url


@pytest.mark.asyncio
async def test_eje_journal_planner_url(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"success": True}))
    await fake_client(EjeJournalPlanner())
    req = fake_session.sent_requests[-1]
    assert PATH_EJE_JOURNAL_PLANNER in req.url


@pytest.mark.asyncio
async def test_eje_participants_url(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"success": True}))
    await fake_client(EjeParticipants())
    req = fake_session.sent_requests[-1]
    assert PATH_EJE_PARTICIPANTS in req.url


@pytest.mark.asyncio
async def test_eje_topics_url(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"success": True}))
    await fake_client(EjeTopics())
    req = fake_session.sent_requests[-1]
    assert PATH_EJE_TOPICS in req.url


@pytest.mark.asyncio
async def test_eje_integrations_url(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"success": True}))
    await fake_client(EjeIntegrations())
    req = fake_session.sent_requests[-1]
    assert PATH_EJE_INTEGRATIONS in req.url


@pytest.mark.parametrize(
    "cls",
    [EjeHomework, EjeJournalPlanner, EjeParticipants, EjeTopics, EjeIntegrations],
)
@pytest.mark.asyncio
async def test_eje_method_uses_get(cls, fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"success": True}))
    await fake_client(cls())
    req = fake_session.sent_requests[-1]
    assert req.method == "GET"


def test_eje_result_parses_full_envelope() -> None:
    """EjeResult model parses {success, message, data} correctly (unit-level)."""
    payload = {"success": True, "message": "all good", "data": [{"key": "value"}]}
    result = EjeResult.model_validate(payload)
    assert isinstance(result, EjeResult)
    assert result.success is True
    assert result.message == "all good"
    assert result.data == [{"key": "value"}]
