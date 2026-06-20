"""Utility / auth response DTOs.

``AuthCheck`` — result of ``GET /common-api/check-auth``.
``OAuthConfig`` — result of ``GET /aas/oauth2/config`` (ESIA host).
The OAuth config surface has ~40 dot-separated keys; the handful of
commonly-used ones get typed aliases; the rest are accessible via
``model_extra`` thanks to ``extra="allow"``.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from ._base import EduObject


class AuthCheck(EduObject):
    """Token validity response from ``/common-api/check-auth``.

    The ``valid`` flag is the only guaranteed field; the real endpoint may
    return additional context keys whose shape is unverified — they are
    absorbed via the parent ``model_config`` (``strict=False`` not needed
    here because we declare only the one field we rely on).

    Args:
        valid: ``True`` when the supplied token is recognised as valid.
    """

    valid: bool


class OAuthConfig(EduObject):
    """OAuth2 / QR configuration returned by the ESIA host.

    The endpoint returns a flat JSON object with ~40 dotted-key entries
    (e.g. ``"qr.login": true``, ``"qr.time.refresh": 30``).  Pydantic v2
    cannot use a dot as a Python identifier, so frequently-needed keys are
    declared with ``alias`` and the remainder are captured in ``model_extra``
    (accessible as ``cfg.model_extra["some.dotted.key"]``).

    ``populate_by_name=True`` is inherited from :class:`~pskovedu.models._base.EduObject`
    so callers can also use the Python attribute names.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True, strict=True)

    qr_login: bool | None = Field(default=None, alias="qr.login")
    qr_time_refresh: int | None = Field(default=None, alias="qr.time.refresh")
