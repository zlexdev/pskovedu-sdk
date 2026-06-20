"""ChallengeSolver ABC — protocol for pluggable auth challenge resolvers.

A :class:`ChallengeSolver` is any object that can resolve an authentication
challenge and return an ``X1_SSO`` cookie value.  Implementations include:

- :class:`~pskovedu.auth.solvers.qr.QrSolver` — drives the SSE QR stream.
- Custom CAPTCHA solvers — subclass and implement :meth:`solve`.

Usage::

    class MyCaptchaSolver(ChallengeSolver):
        async def solve(self, client: Any) -> str:
            token = await my_captcha_api.resolve(...)
            return token

    manager = AuthManager(...)
    await manager.login_with_qr(client, solver=MyCaptchaSolver())
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ChallengeSolver(ABC):
    """Abstract base for authentication challenge solvers.

    Implementations receive the bound ``Client`` instance so they can call
    SDK methods (e.g. subscribe to the QR stream) and return the resulting
    ``X1_SSO`` cookie value on success.
    """

    @abstractmethod
    async def solve(self, client: Any) -> str:
        """Resolve the authentication challenge and return an ``X1_SSO`` value.

        Args:
            client: the ``Client`` instance.  Implementations may use it to
                issue SDK calls (e.g. call the QR subscribe stream method) or
                access ``client.config`` for host URLs.

        Raises:
            AuthError: when the challenge cannot be resolved.
            ChallengeRequired: when a nested challenge (e.g. CAPTCHA) blocks
                the solver and the caller must switch strategy.
        """
