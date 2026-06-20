"""pskovedu.x1db — X1 ORM model registry and well-known name constants.

Public API::

    from pskovedu.x1db.registry import X1ModelRegistry
    from pskovedu.x1db.constants import X1Model
"""

from __future__ import annotations

from .constants import X1Model
from .registry import X1ModelRegistry

__all__ = ["X1Model", "X1ModelRegistry"]
