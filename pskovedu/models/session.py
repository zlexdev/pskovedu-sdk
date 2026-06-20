"""Session-related models: JWT Session, RoleMeta, ShellConfig.

Source: auth.md §Step 8 — JWT payload fields; html_pages.md §X1_CONFIG.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from ._base import EduObject


class Session(EduObject):
    """Decoded portal JWT session.

    Obtained via ``GET /session``; the response body is a raw HS256 JWT which
    the SDK decodes (no signature verify) into this DTO.

    Fields map directly to the JWT payload observed in auth.md §Step 8:
    ``sessionId``, ``exp``, ``iat``, ``jti``.

    Args:
        session_id: 64-hex session identifier (``payload.sessionId``).
        exp: token expiry — UTC tz-aware datetime (``payload.exp`` unix ts).
        iat: token issue time — UTC tz-aware datetime (``payload.iat`` unix ts).
        jti: JWT ID — RFC 4122 UUID (``payload.jti``).
    """

    session_id: str = Field(..., alias="sessionId")
    exp: datetime
    iat: datetime
    jti: UUID

    @field_validator("exp", "iat", mode="before")
    @classmethod
    def _coerce_unix_ts(cls, v: int | float | datetime) -> datetime:
        """Accept unix-epoch integers and coerce them to UTC-aware datetimes."""
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=UTC)
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v
        raise ValueError(f"Cannot coerce {v!r} to datetime")

    @property
    def expired(self) -> bool:
        """``True`` when the token's expiry has passed relative to UTC now."""
        return datetime.now(tz=UTC) >= self.exp


class RoleMeta(EduObject):
    """Current user's role metadata extracted from ``X1_CONFIG.meta.au``.

    Fields use the X1 ORM wire names (uppercase) so ``populate_by_name=True``
    lets Python code access them by snake_case aliases if desired.

    Args:
        sys_guid: GUID of the role record.
        sys_guidfk: foreign-key GUID (e.g. parent role).
        sys_state: numeric state string.
        name: human-readable role name (e.g. ``"Электронный журнал"``).
    """

    sys_guid: str = Field(..., alias="SYS_GUID")
    sys_guidfk: str | None = Field(None, alias="SYS_GUIDFK")
    sys_state: str | None = Field(None, alias="SYS_STATE")
    sys_fldorder: str | None = Field(None, alias="SYS_FLDORDER")
    sys_rev: str | None = Field(None, alias="SYS_REV")
    sys_parentguid: str | None = Field(None, alias="SYS_PARENTGUID")
    name: str = Field(..., alias="NAME")


class X1ModelRef(EduObject):
    """A single entry from ``X1_CONFIG.meta.models``.

    Holds the mapping from a human-readable model ``NAME`` (e.g. ``"JOURNAL"``)
    to its opaque system GUID used in X1 ORM calls.

    Args:
        sys_guid: opaque system GUID for the model.
        name: model name key (e.g. ``"JOURNAL"``, ``"SUBJECTS"``).
        alias: Russian display name (e.g. ``"Журнал"``).
    """

    sys_guid: str = Field(..., alias="SYS_GUID")
    name: str = Field(..., alias="NAME")
    alias: str | None = Field(None, alias="ALIAS")


class ShellConfig(EduObject):
    """Parsed result of bootstrapping ``GET /``.

    Contains the two critical globals injected into the app shell HTML:
    ``window.REMOTING_API`` and the model catalogue from ``window.X1_CONFIG``.

    Args:
        remoting_api_url: ``REMOTING_API.url`` (e.g. ``"/extjs/direct"``).
        remoting_actions: raw actions dict from ``REMOTING_API.actions``
            mapping action-name → list of method descriptors.
        role_meta: ``X1_CONFIG.meta.au`` parsed as :class:`RoleMeta`.
        models: list of :class:`X1ModelRef` from ``X1_CONFIG.meta.models``.
    """

    remoting_api_url: str = Field(default="/extjs/direct")
    remoting_actions: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    role_meta: RoleMeta | None = None
    models: list[X1ModelRef] = Field(default_factory=list)

    def model_guid(self, name: str) -> str | None:
        """Look up a model's SYS_GUID by its NAME.

        Args:
            name: X1 model name (e.g. ``"JOURNAL"``).
        """
        for ref in self.models:
            if ref.name == name:
                return ref.sys_guid
        return None
