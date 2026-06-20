"""ClientConfig — SDK-wide configuration model."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import DEFAULT_HOSTS, DEFAULT_UA, Host


def default_hosts() -> dict[Host, str]:
    """Return a fresh copy of the default host → base-URL mapping."""
    return dict(DEFAULT_HOSTS)


class ClientConfig(BaseSettings):
    """Immutable SDK configuration.

    All fields have safe defaults; override only what differs from the standard
    pskovedu.ru deployment.

    Args:
        hosts: logical host → base URL mapping. Override to point at a test proxy.
        jwt_refresh_skew_s: seconds before JWT expiry at which to proactively refresh.
        allow_mutations: when ``False`` (default), journal write methods raise
            :exc:`~pskovedu.exceptions.MutationsDisabled` before any network call.
        cache_ttl_s: TTL in seconds for reference-data cache (grades, teachers, …).
            ``0`` disables the cache.
        rate_limit_rps: per-host request rate cap in requests-per-second.
            ``None`` disables rate limiting.
        breaker_hosts: hostnames that have the circuit breaker enabled by default
            (gosuslugi.ru infrastructure).
        request_timeout_s: per-request network timeout in seconds.
        retries: number of retries for idempotent requests on transient failures.
        user_agent: ``User-Agent`` header sent with every HTTP request.
    """

    model_config = SettingsConfigDict(env_prefix="PSKOVEDU_")

    hosts: dict[Host, str] = Field(default_factory=default_hosts)
    jwt_refresh_skew_s: int = 300
    allow_mutations: bool = False
    cache_ttl_s: int = 3600
    rate_limit_rps: float | None = 4.0
    breaker_hosts: frozenset[str] = frozenset({"esia.gosuslugi.ru", "sfd.gosuslugi.ru"})
    request_timeout_s: float = 30.0
    retries: int = 2
    user_agent: str = DEFAULT_UA
