"""BaseMethod[T] — aiogram-style typed endpoint base class.

Every SDK endpoint is a Pydantic v2 model class.  The instance IS the request
bundle.  Awaiting it executes through the bound client.

Three execution surfaces, one funnel:
1. ``await client.get_session()``         — flat Client sugar
2. ``await client(GetSession())``         — universal __call__
3. ``await session.next_week()``          — bound method on an EduObject
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Self, TypeVar, get_args

from pydantic import BaseModel, ConfigDict, PrivateAttr

from ..exceptions import MethodDeclarationError, MethodNotBoundError

if TYPE_CHECKING:
    from ..protocol.base import Protocol  # noqa: F401 — used in ClassVar annotation

T = TypeVar("T")


class BaseMethod[T](BaseModel):
    """Aiogram-style typed endpoint.  Awaiting executes through the bound client.

    Subclasses declare their wire intent via class-vars; the actual encoding is
    delegated to ``__protocol__``.

    Common class-vars (all protocols):

    - ``__host__``: logical host key from ``ClientConfig.hosts`` (default ``"portal"``).
    - ``__returning__``: Pydantic model to validate the response into (auto-resolved
      from Generic[T] if not set explicitly).
    - ``__protocol__``: ``Protocol`` class; default ``RestProtocol``.
    - ``__breaker_path__``: optional path override for the circuit-breaker key.

    REST-specific class-vars (read by ``RestProtocol``):

    - ``__http_method__``: HTTP verb string.
    - ``__url__``: path template with optional ``{name}`` placeholders.
    - ``__path_fields__``: frozenset of field names that fill path placeholders.
    - ``__query_fields__``: optional frozenset override for query-string fields.
    - ``__body_fields__``: optional frozenset override for JSON body fields.

    Two-step binding:

    - Client public methods / universal ``__call__`` / model bound methods
      call ``method.as_(client)`` then ``await method``.
    - Naked ``await SomeMethod()`` without binding → ``MethodNotBoundError``.
    """

    model_config = ConfigDict(strict=True, populate_by_name=True)

    __host__: ClassVar[str] = "portal"
    __returning__: ClassVar[type[BaseModel] | type[bytes] | type[str] | None] = None
    __breaker_path__: ClassVar[str | None] = None
    # __protocol__ default is RestProtocol, set lazily after RestProtocol is
    # importable to avoid a circular import at class definition time.
    # Per-protocol bases (_bases.py) override this with the correct protocol.
    # We store it as a plain ClassVar; the actual RestProtocol object is patched
    # in at the bottom of this module after the class body is defined.
    __protocol__: ClassVar[type]  # patched below

    # REST-specific class-vars (ignored by non-REST protocols)
    __http_method__: ClassVar[str | None] = None
    __url__: ClassVar[str | None] = None
    __path_fields__: ClassVar[frozenset[str]] = frozenset()
    __query_fields__: ClassVar[frozenset[str] | None] = None
    __body_fields__: ClassVar[frozenset[str] | None] = None

    # Ext.Direct class-vars (ignored by non-ExtDirect protocols)
    __action__: ClassVar[str | None] = None
    __rpc_method__: ClassVar[str | None] = None

    __x1_service__: ClassVar[str | None] = None
    __x1_method__: ClassVar[str | None] = None
    __x1_model__: ClassVar[str | None] = None

    # SSE class-vars
    __event_model__: ClassVar[type[BaseModel] | None] = None
    __terminal_event__: ClassVar[str | None] = None

    _client: Any = PrivateAttr(default=None)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        # Guard against the old-style __path__ name (Python reserves __path__ for packages)
        if "__path__" in cls.__dict__:
            raise MethodDeclarationError(
                f"{cls.__name__}: use __url__, not __path__ "
                "(Python uses __path__ for namespace packages)."
            )

        cls.__returning__ = cls._resolve_returning()

        # Delegate protocol-specific class-var validation.
        # Use getattr with a default to handle the window between BaseMethod
        # class creation and the RestProtocol patch below.
        protocol_cls = getattr(cls, "__protocol__", None)
        if protocol_cls is not None and hasattr(protocol_cls, "validate_subclass"):
            protocol_cls.validate_subclass(cls)

    @classmethod
    def _resolve_returning(cls) -> type[BaseModel] | type[bytes] | type[str] | None:
        """Reconcile Generic[T] with the explicit ``__returning__`` class-var.

        Four legal cases:
        1. ``BaseMethod[Order]`` + no ``__returning__`` → auto-bind to ``Order``.
        2. ``BaseMethod[Order]`` + ``__returning__ = Order`` → match, keep.
        3. ``BaseMethod[None]``  + no ``__returning__`` → fire-and-forget (``None``).
        4. ``BaseMethod[bytes]`` or ``BaseMethod[str]`` → kept as raw-bytes/text passthrough.

        PEP 695 note: ``class Foo[T](RestMethod[T])`` causes Python 3.12+ to create
        a real parameterized class for each concrete instantiation (e.g. ``RestMethod[bytes]``).
        ``typing.get_args()`` returns ``()`` for these materialized classes, so we fall back
        to ``__pydantic_generic_metadata__['args']`` on ``cls.__bases__``.

        Raises:
            MethodDeclarationError: when ``__returning__`` contradicts Generic[T].
        """
        from_generic: type[BaseModel] | type[bytes] | type[str] | None = None

        # Primary path: standard typing.get_args on __orig_bases__
        # (works for old-style Generic[T] subclasses)
        for base in getattr(cls, "__orig_bases__", ()):
            args = get_args(base)
            if args:
                arg0 = args[0]
                if isinstance(arg0, type) and (
                    arg0 is bytes
                    or arg0 is str
                    or issubclass(arg0, BaseModel)
                ):
                    from_generic = arg0
                    break

        # Fallback path: PEP 695 parameterized bases expose args via Pydantic's
        # __pydantic_generic_metadata__ because get_args() returns () for them.
        if from_generic is None:
            for base in cls.__bases__:
                meta = getattr(base, "__pydantic_generic_metadata__", None)
                if meta and meta.get("args"):
                    arg0 = meta["args"][0]
                    if isinstance(arg0, type) and (
                        arg0 is bytes
                        or arg0 is str
                        or issubclass(arg0, BaseModel)
                    ):
                        from_generic = arg0
                        break

        explicit = cls.__dict__.get("__returning__", None)

        if explicit is not None and from_generic is not None and explicit is not from_generic:
            explicit_name = getattr(explicit, "__name__", repr(explicit))
            from_name = getattr(from_generic, "__name__", repr(from_generic))
            raise MethodDeclarationError(
                f"{cls.__name__}: __returning__={explicit_name!r} contradicts "
                f"Generic parameter T={from_name!r}. Pick one."
            )

        return explicit if explicit is not None else from_generic

    def as_(self, client: Any) -> Self:
        """Attach *client* and return ``self`` for fluent chaining.

        Idempotent: calling twice with the same client is a no-op; calling with
        a different client overwrites the binding.

        Args:
            client: a ``Client`` instance to attach.
        """
        self._client = client
        return self

    async def emit(self, client: Any) -> T:
        """Execute through the session funnel and return the typed response.

        Args:
            client: the ``Client`` to use for the request.
        """
        result: T = await client.session.make_request(client, self)
        return result

    def __await__(self) -> Any:
        if self._client is None:
            raise MethodNotBoundError(type(self).__name__)
        return self.emit(self._client).__await__()


# Patch the default __protocol__ on BaseMethod now that RestProtocol is importable.
# This avoids a circular import during class body execution above.
from ..protocol.rest import RestProtocol as _RestProtocol  # noqa: E402

BaseMethod.__protocol__ = _RestProtocol

from ..pagination.iterator import PageIterator  # noqa: E402


class PaginatedMethod[T](BaseMethod[Any]):
    """Method that returns an auto-fetching ``PageIterator`` when executed.

    Subclasses define :meth:`_first` (initial page method), :meth:`_extract`
    (page → items) and :meth:`_advance` (page → next method or ``None``).  The
    client just runs the method; the paginator is built here, not at the call
    site.  ``__protocol__`` is ``None`` so no wire-protocol validation runs —
    :meth:`emit` is overridden and never touches the request funnel directly.
    """

    __protocol__ = None  # type: ignore[assignment]

    def _first(self) -> BaseMethod[Any]:
        raise NotImplementedError

    def _extract(self, page: Any) -> list[T]:
        raise NotImplementedError

    def _advance(self, page: Any) -> BaseMethod[Any] | None:
        raise NotImplementedError

    async def emit(self, client: Any) -> PageIterator[T]:
        return PageIterator(client, self._first(), extract=self._extract, advance=self._advance)
