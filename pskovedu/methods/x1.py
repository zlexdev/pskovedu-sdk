"""X1 ORM method-classes (Ext.Direct ``X1API`` action via X1Protocol).

These methods use :class:`~pskovedu.protocol.x1.X1Protocol` which posts to
``/x1db/service/call`` and resolves model NAME → SYS_GUID at request time.

**Experimental** — X1 ORM is an internal undocumented API.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..models.x1 import X1PageModel, X1RecordModel
from ._bases import X1Method


class X1Query(X1Method[X1PageModel]):
    """Query X1 ORM records for a model with optional filter and limit.

    X1 Protocol: ``POST /x1db/service/call`` with ``service="query"``,
    ``method="select"``, ``params={model: <SYS_GUID>, where: ..., limit: ...}``.

    The ``__x1_model__`` NAME is resolved to ``SYS_GUID`` at request time via
    the client's :class:`~pskovedu.x1db.registry.X1ModelRegistry`.

    Args:
        model: X1 model name (use :class:`~pskovedu.x1db.constants.X1Model` enum).
        where: optional filter dict passed to the X1 service.
        limit: maximum number of records to return (``None`` = server default).
    """

    __x1_service__ = "query"
    __x1_method__ = "select"

    model: str
    where: dict[str, Any] = Field(default_factory=dict)
    limit: int | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    @property
    def __x1_model__(self) -> str:  # type: ignore[override]
        return self.model


class X1Get(X1Method[X1RecordModel]):
    """Fetch a single X1 ORM record by GUID.

    X1 Protocol: ``POST /x1db/service/call`` with ``service="query"``,
    ``method="get"``, ``params={model: <SYS_GUID>, guid: <record_guid>}``.

    Args:
        model: X1 model name (use :class:`~pskovedu.x1db.constants.X1Model` enum).
        guid: record GUID to fetch.
    """

    __x1_service__ = "query"
    __x1_method__ = "get"

    model: str
    guid: str

    @property
    def __x1_model__(self) -> str:  # type: ignore[override]
        return self.model
