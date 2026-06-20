"""Avatar method-class — REST GET for ESIA user avatar.

Returns raw ``bytes`` of the avatar image (JPEG/PNG) or empty bytes when
no avatar is set.

Wire: ``GET esia.gosuslugi.ru/esia-rs/api/public/v1/avatar/{uuid}``
Host key: ``"esia"`` (maps to ``https://esia.gosuslugi.ru`` in DEFAULT_HOSTS).
"""

from __future__ import annotations

from ..constants import PATH_ESIA_AVATAR, Host
from ..models.common import Uuid
from ._bases import RestMethod


class GetAvatar(RestMethod[bytes]):
    """Fetch the ESIA avatar image for a user by UUID.

    REST: ``GET esia.gosuslugi.ru/esia-rs/api/public/v1/avatar/{uuid}``

    The response body is raw image bytes (``image/jpeg`` or ``image/png``).
    An empty body or ``null`` JSON response means no avatar is set.

    Args:
        uuid: ESIA user UUID (RFC 4122 format).
    """

    __host__ = Host.ESIA
    __http_method__ = "GET"
    __url__ = PATH_ESIA_AVATAR
    __path_fields__ = frozenset({"uuid"})

    uuid: Uuid
