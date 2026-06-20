from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .client import Client
from .config import ClientConfig

if TYPE_CHECKING:
    from .methods._base import BaseMethod

__all__ = ["SyncClient"]


class SyncClient:
    """Synchronous wrapper around the async :class:`~pskovedu.client.Client`.

    Spins up a private ``asyncio`` event loop so blocking callers (scripts,
    REPL, pytest without ``pytest-asyncio``) can use the SDK without ``await``.

    Example::

        with SyncClient.from_cookie(x1_sso="<value>") as c:
            shell = c.get_shell()
            grades = c(GetGrades())
    """

    def __init__(self, client: Client) -> None:
        self._client = client
        self._loop = asyncio.new_event_loop()

    @classmethod
    def from_cookie(
        cls,
        x1_sso: str,
        *,
        session_file: str | Path | None = None,
        config: ClientConfig | None = None,
    ) -> SyncClient:
        return cls(Client.from_cookie(x1_sso=x1_sso, session_file=session_file, config=config))

    def __enter__(self) -> SyncClient:
        self._loop.run_until_complete(self._client.__aenter__())
        return self

    def __exit__(self, *exc: Any) -> None:
        self._loop.run_until_complete(self._client.__aexit__(*exc))
        self._loop.close()

    def __call__(self, method: BaseMethod[Any]) -> Any:
        return self._loop.run_until_complete(self._client(method))

    def get_shell(self) -> Any:
        return self._loop.run_until_complete(self._client.get_shell())
