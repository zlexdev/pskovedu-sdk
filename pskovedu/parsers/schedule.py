"""Parse schedule and role-flag globals from the portal shell HTML.

The portal injects these variables as inline ``<script>`` assignments::

    window.schedule_subject_guid   = 'CF638B14EE9F5DBB6466B39F0FD4AF77';
    window.schedule_subject_type   = 'grade';
    window.journal_open_enabled    = 0;
    window.schedule_editor_enabled = 0;

``schedule_subject_guid`` is the GUID of the grade/teacher/room entity whose
schedule is displayed; ``schedule_subject_type`` distinguishes ``'grade'``,
``'teacher'``, ``'room'``.  The two ``_enabled`` flags are role-gates that
control UI affordances.

Usage::

    sg = parse_schedule_globals(html)
    print(sg.schedule_subject_guid)    # "CF638B14EE9F5DBB6466B39F0FD4AF77"
    print(sg.schedule_subject_type)    # "grade"
    print(sg.journal_open_enabled)     # False
    print(sg.schedule_editor_enabled)  # False
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..logging import get_logger

log = get_logger(__name__)

# window.<name> = <value>;
# value is either a quoted string or an integer literal
_VAR_STR_RE = re.compile(
    r"window\.(schedule_subject_guid|schedule_subject_type)\s*=\s*['\"]([^'\"]*)['\"]",
    re.IGNORECASE,
)
_VAR_INT_RE = re.compile(
    r"window\.(journal_open_enabled|schedule_editor_enabled)\s*=\s*([01])",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class ScheduleGlobals:
    """Parsed schedule-related globals from the portal shell HTML.

    Attributes:
        schedule_subject_guid: GUID of the schedule subject entity (grade /
            teacher / room), or ``None`` when not present on the page.
        schedule_subject_type: entity type string — typically ``'grade'``,
            ``'teacher'``, or ``'room'``; ``None`` when absent.
        journal_open_enabled: whether the current role may open the journal.
        schedule_editor_enabled: whether the current role may edit the schedule.
    """

    schedule_subject_guid: str | None
    schedule_subject_type: str | None
    journal_open_enabled: bool
    schedule_editor_enabled: bool


def parse_schedule_globals(html: str) -> ScheduleGlobals:
    """Extract schedule globals and role-flags from the portal shell HTML.

    Looks for ``window.schedule_subject_guid``, ``window.schedule_subject_type``,
    ``window.journal_open_enabled``, and ``window.schedule_editor_enabled`` in
    inline ``<script>`` blocks.  Missing variables are silently defaulted.

    Args:
        html: raw HTML text of ``GET /`` response.
    """
    str_vars: dict[str, str] = {}
    for m in _VAR_STR_RE.finditer(html):
        str_vars[m.group(1).lower()] = m.group(2)

    int_vars: dict[str, int] = {}
    for m in _VAR_INT_RE.finditer(html):
        int_vars[m.group(1).lower()] = int(m.group(2))

    guid = str_vars.get("schedule_subject_guid") or None
    stype = str_vars.get("schedule_subject_type") or None
    journal_enabled = bool(int_vars.get("journal_open_enabled", 0))
    sched_editor = bool(int_vars.get("schedule_editor_enabled", 0))

    log.debug(
        "schedule_globals.parsed",
        guid=guid,
        subject_type=stype,
        journal_open_enabled=journal_enabled,
        schedule_editor_enabled=sched_editor,
    )
    return ScheduleGlobals(
        schedule_subject_guid=guid,
        schedule_subject_type=stype,
        journal_open_enabled=journal_enabled,
        schedule_editor_enabled=sched_editor,
    )
