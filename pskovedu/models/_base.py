"""EduObject — Pydantic v2 base for all SDK response DTOs that carry a client reference.

The session funnel calls ``result.as_(client)`` on every decoded response that
is an ``EduObject`` subclass, enabling bound methods such as::

    week = await client.get_diary(guid)
    await week.next_week()   # works because week._client is set
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ConfigDict, PrivateAttr

from ..exceptions import ModelNotBoundError

if TYPE_CHECKING:
    pass


class EduObject(BaseModel):
    """Pydantic v2 base for SDK response DTOs with optional client binding.

    Subclasses expose bound action methods (e.g. ``diary.next_week()``) that
    return method-class instances with the client pre-attached.  Models
    constructed by hand (tests, replay tooling) have no client and raise
    :exc:`~pskovedu.exceptions.ModelNotBoundError` when bound methods are called.
    """

    model_config = ConfigDict(populate_by_name=True, strict=True)

    __arg_order__: ClassVar[tuple[str, ...]] = ()

    _client: Any = PrivateAttr(default=None)

    def as_(self, client: Any) -> EduObject:
        """Attach *client* and return ``self`` for fluent chaining.

        Recursively binds any nested ``EduObject`` fields and list items so that
        ``diary.entries[0].some_action()`` works without manual binding.

        Args:
            client: a ``Client`` instance to attach.

        Raises:
            ModelNotBoundError: when *client* is falsy (``None`` or empty).
        """
        if not client:
            raise ModelNotBoundError(type(self).__name__)
        self._client = client
        # Recurse into nested EduObject fields
        for field_name in type(self).model_fields:
            value = getattr(self, field_name, None)
            if isinstance(value, EduObject):
                value.as_(client)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, EduObject):
                        item.as_(client)
        return self

    def _require_client(self) -> Any:
        """Return the bound client or raise :exc:`ModelNotBoundError`."""
        if self._client is None:
            raise ModelNotBoundError(type(self).__name__)
        return self._client

    @property
    def client(self) -> Any:
        """The bound client, or ``None`` if the model was constructed by hand."""
        return self._client


class HtmlParsed(EduObject):
    """Marker base for models whose wire representation is raw HTML text.

    ``RestProtocol.decode_response`` detects this base and passes the raw
    response text to the method's registered parser function instead of
    attempting ``model_validate`` on JSON.

    Subclasses must not add ``model_config`` that would prevent assignment of
    the ``raw_html`` field used internally by parsers.
    """

    raw_html: str = ""
