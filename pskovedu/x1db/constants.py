"""Well-known X1 ORM model names as a :class:`StrEnum`.

Values are the ``NAME`` field from ``X1_CONFIG.meta.models`` — the same
strings used as keys in :class:`~pskovedu.x1db.registry.X1ModelRegistry`.

These names are stable identifiers assigned by the portal backend; they do
not change between deployments.  The corresponding ``SYS_GUID`` values *do*
change between installations, which is why they are resolved at runtime via
:class:`~pskovedu.x1db.registry.X1ModelRegistry` rather than hardcoded here.

Source: ``html_pages.md`` §X1_CONFIG — ``meta.models`` catalog (60+ entries).
"""

from __future__ import annotations

from enum import StrEnum


class X1Model(StrEnum):
    """Well-known X1 ORM model names from ``X1_CONFIG.meta.models``.

    Use these constants anywhere a model ``NAME`` string is expected, e.g.::

        registry.guid(X1Model.JOURNAL)  # → "9DB33AD685B04DF8A6A73F32FFE78F08"
    """

    # Core academic models
    JOURNAL = "JOURNAL"
    """Электронный журнал — grade journal / lesson records."""

    SUBJECTS = "SUBJECTS"
    """Предметы — academic subjects catalog."""

    MARKVALS = "MARKVALS"
    """Значения оценок — valid mark values (e.g. 1–5, «н», «пт»)."""

    GRADETYPES = "GRADETYPES"
    """Типы учебных отметок — grade/mark type definitions."""

    MARKWEIGHTS = "MARKWEIGHTS"
    """Веса оценок — mark weight coefficients for grade averaging."""

    EDUTOPICS = "EDUTOPICS"
    """Учебные темы — educational topic assignments per lesson."""

    ABSENCE = "ABSENCE"
    """Мониторинг посещаемости — student attendance / absence records."""

    LESSONTYPES = "LESSONTYPES"
    """Типы уроков — lesson type classifications."""

    # Schedule / timetable
    UCH_ZAN = "UCH_ZAN"
    """Расписание звонков — bell schedule (period start/end times)."""

    # Institutional
    SCHOOLS = "SCHOOLS"
    """Реестр учреждений — school / institution registry."""

    EDYEAR = "EDYEAR"
    """Учебный год — academic year definition."""

    ROLES = "ROLES"
    """Роли — user role definitions."""

    # Users and notifications
    USER_NOTIFICATION = "USER_NOTIFICATION"
    """Оповещения — user notification records."""

    # Participants / diary
    PARTICIPANTS = "PARTICIPANTS"
    """Участники — participant records (students in a grade)."""

    GRADEBOOK = "GRADEBOOK"
    """Классный журнал — class grade book."""

    # Report / analytics models
    REPORT_PERFORMANCE = "REPORT_PERFORMANCE"
    """Успеваемость — performance / grade analytics."""

    # Calendar / periods
    PERIODS = "PERIODS"
    """Учебные периоды — academic periods (quarters, semesters)."""

    HOLIDAYS = "HOLIDAYS"
    """Каникулы — holiday calendar entries."""

    # Reception / appointments
    RECEPTION = "RECEPTION"
    """Приём граждан — reception appointment slots."""

    # Monitoring
    MONITORING = "MONITORING"
    """Мониторинг — general monitoring data."""
