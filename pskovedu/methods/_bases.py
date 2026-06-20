"""Per-protocol base method-classes — pin ``__protocol__`` once.

Domain method-classes inherit from one of these bases and only declare
what differs (operation + returning).  Protocol assignment is never repeated
on individual endpoint classes.

Ext.Direct, X1, and SSE protocols are lazy-imported inside
``__init_subclass__`` so the import only fires when a concrete subclass of
each base is defined (not at package import time).
"""

from __future__ import annotations

from typing import Any, ClassVar, TypeVar

from ..protocol.rest import RestProtocol
from ._base import BaseMethod

T = TypeVar("T")


class RestMethod[T](BaseMethod[T]):
    """Base for all REST endpoints.

    Pins ``__protocol__ = RestProtocol``.  Subclasses declare
    ``__http_method__``, ``__url__``, and optionally ``__path_fields__``,
    ``__query_fields__``, ``__body_fields__``.

    Default host: ``"portal"`` (one.pskovedu.ru).
    """

    __protocol__: ClassVar[type] = RestProtocol
    __host__: ClassVar[str] = "portal"


class ExtDirectMethod[T](BaseMethod[T]):
    """Base for all Ext.Direct RPC methods (``POST /extjs/direct``).

    ``__protocol__`` is set to ``ExtDirectProtocol`` when a concrete subclass
    is defined (lazy import inside ``__init_subclass__``).

    Subclasses declare:
    - ``__action__``: Ext.Direct action name (e.g. ``"Reports"``).
    - ``__rpc_method__``: method name (e.g. ``"getGrades"``).
    - ````: tuple of field names mapped to positional ``data[]`` args.

    Default host: ``"portal"`` (one.pskovedu.ru).
    """

    # Temporary protocol — overridden below and on every concrete subclass
    __protocol__: ClassVar[type] = RestProtocol  # replaced in __init_subclass__
    __host__: ClassVar[str] = "portal"
    __action__: ClassVar[str | None] = None
    __rpc_method__: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Lazily wire the real protocol before BaseMethod.__init_subclass__ runs
        try:
            from ..protocol.ext_direct import ExtDirectProtocol

            cls.__protocol__ = ExtDirectProtocol
        except ImportError:
            pass  # ext_direct not yet written — downstream; keep RestProtocol stub
        super().__init_subclass__(**kwargs)


# Patch the base itself now that the import guard is in place
try:
    from ..protocol.ext_direct import ExtDirectProtocol as _EdP

    ExtDirectMethod.__protocol__ = _EdP
except ImportError:
    pass


class X1Method[T](BaseMethod[T]):
    """Base for all X1 ORM methods (``POST /x1db/service/call``).

    ``__protocol__`` is set to ``X1Protocol`` lazily.

    Subclasses declare:
    - ``__x1_service__``: X1 service name.
    - ``__x1_method__``: X1 method name.
    - ``__x1_model__``: model NAME string (resolved to SYS_GUID via registry at
      request time).

    Default host: ``"portal"`` (one.pskovedu.ru).
    """

    __protocol__: ClassVar[type] = RestProtocol  # replaced in __init_subclass__
    __host__: ClassVar[str] = "portal"
    __x1_service__: ClassVar[str | None] = None
    __x1_method__: ClassVar[str | None] = None
    __x1_model__: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        try:
            from ..protocol.x1 import X1Protocol

            cls.__protocol__ = X1Protocol
        except ImportError:
            pass
        super().__init_subclass__(**kwargs)


try:
    from ..protocol.x1 import X1Protocol as _X1P

    X1Method.__protocol__ = _X1P
except ImportError:
    pass


class SseSubscription[T](BaseMethod[T]):
    """Base for Server-Sent Event subscriptions (requires ``[sse]`` extra).

    ``__protocol__`` is set to ``SseProtocol`` lazily.

    Subclasses declare:
    - ``__url__``: SSE endpoint path template.
    - ``__event_model__``: Pydantic model for individual events.
    - ``__terminal_event__``: event name that signals end of stream.

    Default host: ``"esia"`` (esia.gosuslugi.ru, where QR SSE lives).
    """

    __protocol__: ClassVar[type] = RestProtocol  # replaced in __init_subclass__
    __host__: ClassVar[str] = "esia"
    __event_model__: ClassVar[type | None] = None
    __terminal_event__: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        try:
            from ..protocol.sse import SseProtocol

            cls.__protocol__ = SseProtocol
        except ImportError:
            pass
        super().__init_subclass__(**kwargs)


try:
    from ..protocol.sse import SseProtocol as _SseP

    SseSubscription.__protocol__ = _SseP
except ImportError:
    pass
