"""PageIterator — async item iterator that auto-fetches successive pages.

Wraps a first method plus two closures: ``extract`` (page → items) and
``advance`` (page → next method, or ``None`` to stop).  Iterating yields each
item; when a page is exhausted the next page is fetched transparently and
iteration continues until ``advance`` returns ``None``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..methods._base import BaseMethod


class PageIterator[T](AsyncIterator[T]):
    """Async iterator that flattens items across auto-fetched pages.

    Args:
        client: the executor (``Client``) the page methods are routed through.
        first: the method that fetches the first page, or ``None`` for empty.
        extract: maps a fetched page to its list of items.
        advance: maps a fetched page to the next method, or ``None`` to stop.
    """

    def __init__(
        self,
        client: Any,
        first: BaseMethod[Any] | None,
        *,
        extract: Callable[[Any], list[T]],
        advance: Callable[[Any], BaseMethod[Any] | None],
    ) -> None:
        self._client = client
        self._next = first
        self._extract = extract
        self._advance = advance
        self._buf: list[T] = []
        self._pos = 0

    def __aiter__(self) -> PageIterator[T]:
        return self

    async def __anext__(self) -> T:
        while self._pos >= len(self._buf):
            if self._next is None:
                raise StopAsyncIteration
            page = await self._client(self._next)
            self._next = self._advance(page)
            self._buf = list(self._extract(page))
            self._pos = 0
        item = self._buf[self._pos]
        self._pos += 1
        return item
