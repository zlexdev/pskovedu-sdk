"""pskovedu.parsers — HTML extraction layer.

Public API::

    from pskovedu.parsers.shell import parse_shell
    from pskovedu.parsers.participant import parse_participant
    from pskovedu.parsers.schedule import parse_schedule_globals
    from pskovedu.parsers.bundles import parse_bundle_urls
"""

from __future__ import annotations

from .bundles import parse_bundle_urls
from .participant import ParticipantInfo, parse_participant
from .schedule import ScheduleGlobals, parse_schedule_globals
from .shell import parse_shell

__all__ = [
    "parse_shell",
    "parse_participant",
    "ParticipantInfo",
    "parse_schedule_globals",
    "ScheduleGlobals",
    "parse_bundle_urls",
]
