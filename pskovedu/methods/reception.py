"""Reception method-classes (Ext.Direct ``Reception`` action).

REMOTING_API::

    "Reception": [{"name": "getReception", "params": ["start", "end", "type"]}]
"""

from __future__ import annotations

from pydantic import Field

from ..constants import RemotingAction, RemotingMethod
from ..models.common import EduPage
from ..models.enums import ReceptionAudience
from ..models.reception import ReceptionSlot
from ._bases import ExtDirectMethod


class GetReception(ExtDirectMethod[EduPage[ReceptionSlot]]):
    """Fetch reception slots within a date range.

    Ext.Direct: ``Reception.getReception`` with positional args ``[start, end, type]``.

    Args:
        start: start date string ``"DD.MM.YYYY"``.
        end: end date string ``"DD.MM.YYYY"``.
        audience_type: target audience filter (default ``ReceptionAudience.ALL``).
    """

    __action__ = RemotingAction.RECEPTION
    __rpc_method__ = RemotingMethod.GET_RECEPTION
    __arg_order__ = ("start", "end", "type")

    start: str
    end: str
    type: ReceptionAudience = Field(default=ReceptionAudience.ALL, alias="type")
