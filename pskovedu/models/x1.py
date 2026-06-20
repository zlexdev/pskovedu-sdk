"""X1 ORM domain models — generic record and page wrappers for SDK use.

These are the SDK-level DTOs for X1 queries.  The raw
:class:`~pskovedu.protocol.x1.X1Record` / :class:`~pskovedu.protocol.x1.X1Page`
protocol types are protocol-internal; these models are what the caller receives
after the session funnel decodes an X1 method response.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from ._base import EduObject


class X1ModelRef(EduObject):
    """A reference to an X1 ORM model entry (NAME + SYS_GUID pair).

    Used to expose the model catalog to callers without leaking the raw
    registry internals.

    Attributes:
        name: model name key (e.g. ``"JOURNAL"``).
        sys_guid: opaque system GUID for the model.
        alias: Russian display name, or ``None``.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    name: str = Field(..., alias="NAME")
    sys_guid: str = Field(..., alias="SYS_GUID")
    alias: str | None = Field(None, alias="ALIAS")


class X1RecordModel(EduObject):
    """A single X1 ORM record with standard SYS_* prefix fields.

    All field values are strings on the wire (X1 stores everything as VARCHAR).
    Domain-specific parsing is the caller's responsibility.

    Attributes:
        sys_guid: primary key GUID.
        sys_guidfk: foreign key GUID, or ``None``.
        sys_state: record state string.
        sys_rev: revision counter string.
        sys_parentguid: parent record GUID, or ``None``.
        extra: additional domain-specific fields from the record.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False, extra="allow")

    sys_guid: str = Field(..., alias="SYS_GUID")
    sys_guidfk: str | None = Field(None, alias="SYS_GUIDFK")
    sys_state: str | None = Field(None, alias="SYS_STATE")
    sys_rev: str | None = Field(None, alias="SYS_REV")
    sys_parentguid: str | None = Field(None, alias="SYS_PARENTGUID")

    def get(self, key: str, default: Any = None) -> Any:
        """Access an extra domain field by name.

        Args:
            key: field name (UPPER_CASE convention for X1 fields).
            default: value to return when the field is absent.
        """
        return self.model_extra.get(key, default) if self.model_extra else default


class X1PageModel(EduObject):
    """A page of X1 ORM records returned by query methods.

    Attributes:
        records: list of :class:`X1RecordModel` entries.
        total: total server-side record count, or ``None`` when not provided.
        model_name: the X1 model name queried (``X1Model`` enum value or raw string).
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    records: list[X1RecordModel] = Field(default_factory=list)
    total: int | None = None
    model_name: str | None = None

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Any:
        return iter(self.records)
