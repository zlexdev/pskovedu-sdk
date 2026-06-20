"""Monitoring method-classes (Ext.Direct ``monitoring`` action).

The ``monitoring`` action (lowercase, matching the REMOTING_API key exactly)
provides attendance/absence data for grades.

REMOTING_API::

    "monitoring": [
        {"name": "read",     "params": ["grades"]},
        {"name": "readskip", "params": ["part"]}
    ]
"""

from __future__ import annotations

from ..constants import RemotingAction, RemotingMethod
from ..models.monitoring import MonitoringResult
from ._bases import ExtDirectMethod


class MonitoringRead(ExtDirectMethod[MonitoringResult]):
    """Read attendance/absence records for a list of grades.

    Ext.Direct: ``monitoring.read`` with positional arg ``grades``.

    Args:
        grades: list of grade GUIDs to query.
    """

    __action__ = RemotingAction.MONITORING
    __rpc_method__ = RemotingMethod.MONITORING_READ
    __arg_order__ = ("grades",)

    grades: list[str]


class MonitoringReadSkip(ExtDirectMethod[MonitoringResult]):
    """Read skipped lesson records (пропуски) for a participant.

    Ext.Direct: ``monitoring.readskip`` with positional arg ``part``.

    Args:
        part: participant GUID to query skipped lessons for.
    """

    __action__ = RemotingAction.MONITORING
    __rpc_method__ = RemotingMethod.MONITORING_READ_SKIP
    __arg_order__ = ("part",)

    part: str
