"""Tests for methods/util.py — CheckAuth + GetOAuthConfig."""

from __future__ import annotations

import pytest

from pskovedu.constants import PATH_CHECK_AUTH, PATH_OAUTH_CONFIG, Host
from pskovedu.methods.util import CheckAuth, GetOAuthConfig
from pskovedu.models.util import AuthCheck, OAuthConfig

from .conftest import json_response


@pytest.mark.asyncio
async def test_check_auth_url(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"valid": True}))
    await fake_client(CheckAuth(value="mytoken"))
    req = fake_session.sent_requests[-1]
    assert PATH_CHECK_AUTH in req.url


@pytest.mark.asyncio
async def test_check_auth_sends_value_as_query_param(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"valid": True}))
    await fake_client(CheckAuth(value="mytoken"))
    req = fake_session.sent_requests[-1]
    assert req.params.get("value") == "mytoken"


@pytest.mark.asyncio
async def test_check_auth_uses_get(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"valid": True}))
    await fake_client(CheckAuth(value="tok"))
    req = fake_session.sent_requests[-1]
    assert req.method == "GET"


@pytest.mark.asyncio
async def test_check_auth_returns_auth_check(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"valid": True}))
    result = await fake_client(CheckAuth(value="tok"))
    assert isinstance(result, AuthCheck)
    assert result.valid is True


@pytest.mark.asyncio
async def test_check_auth_valid_false(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"valid": False}))
    result = await fake_client(CheckAuth(value="badtoken"))
    assert result.valid is False


@pytest.mark.asyncio
async def test_check_auth_different_tokens(fake_client, fake_session) -> None:
    for token in ("alpha", "beta", "gamma"):
        fake_session.enqueue(json_response({"valid": True}))
        await fake_client(CheckAuth(value=token))
        req = fake_session.sent_requests[-1]
        assert req.params.get("value") == token


@pytest.mark.asyncio
async def test_get_oauth_config_url(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"qr.login": True}))
    await fake_client(GetOAuthConfig())
    req = fake_session.sent_requests[-1]
    assert PATH_OAUTH_CONFIG in req.url


@pytest.mark.asyncio
async def test_get_oauth_config_hits_esia_host(fake_client, fake_session) -> None:
    """GetOAuthConfig.__host__ must be Host.ESIA so the URL targets esia.gosuslugi.ru."""
    esia_url = fake_client.config.hosts[Host.ESIA]
    fake_session.enqueue(json_response({"qr.login": True}))
    await fake_client(GetOAuthConfig())
    req = fake_session.sent_requests[-1]
    assert req.url.startswith(esia_url)


@pytest.mark.asyncio
async def test_get_oauth_config_uses_get(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"qr.login": False}))
    await fake_client(GetOAuthConfig())
    req = fake_session.sent_requests[-1]
    assert req.method == "GET"


@pytest.mark.asyncio
async def test_get_oauth_config_returns_oauth_config(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"qr.login": True, "qr.time.refresh": 30}))
    result = await fake_client(GetOAuthConfig())
    assert isinstance(result, OAuthConfig)


@pytest.mark.asyncio
async def test_get_oauth_config_typed_qr_login(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"qr.login": True, "qr.time.refresh": 30}))
    result = await fake_client(GetOAuthConfig())
    assert result.qr_login is True
    assert result.qr_time_refresh == 30


@pytest.mark.asyncio
async def test_get_oauth_config_qr_login_false(fake_client, fake_session) -> None:
    fake_session.enqueue(json_response({"qr.login": False}))
    result = await fake_client(GetOAuthConfig())
    assert result.qr_login is False


@pytest.mark.asyncio
async def test_get_oauth_config_extra_dotted_keys_in_model_extra(
    fake_client, fake_session
) -> None:
    """Extra dotted keys not declared as typed fields must land in model_extra."""
    payload = {
        "qr.login": True,
        "qr.time.refresh": 60,
        "some.other.key": "value",
        "another.extra": 42,
    }
    fake_session.enqueue(json_response(payload))
    result = await fake_client(GetOAuthConfig())
    # model_extra captures all undeclared keys
    assert result.model_extra is not None
    assert result.model_extra.get("some.other.key") == "value"
    assert result.model_extra.get("another.extra") == 42


@pytest.mark.asyncio
async def test_get_oauth_config_missing_optional_fields_default_none(
    fake_client, fake_session
) -> None:
    """Optional typed fields default to None when absent from the response."""
    fake_session.enqueue(json_response({}))
    result = await fake_client(GetOAuthConfig())
    assert result.qr_login is None
    assert result.qr_time_refresh is None
