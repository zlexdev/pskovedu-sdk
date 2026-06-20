"""Domain enums — all StrEnum/IntEnum for the pskovedu SDK.

Every domain enum lives here.  Domain model files import from this module;
no inline enum definitions in model files.  (X1Model stays in x1db/constants.py.)

Wire values match the portal's observed state codes and type strings.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class JournalState(StrEnum):
    """Journal record lifecycle states (``SYS_STATE`` field in X1 ORM).

    Transitions are validated via :data:`JOURNAL_TRANSITIONS` and
    :func:`~pskovedu.models.journal.assert_journal_transition`.
    """

    DRAFT = "1"
    """Черновик — initial state, not yet submitted."""

    ACTIVE = "2"
    """Активен — submitted / published."""

    ARCHIVED = "3"
    """Архив — archived / closed."""

    DELETED = "4"
    """Удалён — soft-deleted."""


class AbsenceKind(StrEnum):
    """Kind of student absence recorded in the monitoring system.

    Wire values match the portal's ``TYPE`` field in absence records.
    """

    SICK = "н/б"
    """Болезнь / sick leave."""

    UNEXCUSED = "н"
    """Без причины / unexcused absence."""

    EXCUSED = "у"
    """Уважительная причина / excused absence."""

    LATE = "оп"
    """Опоздание / late arrival."""


class ReceptionStatus(StrEnum):
    """Reception slot booking status.

    Reflects the ``SYS_STATE`` of a reception record.
    """

    OPEN = "1"
    """Свободен — slot is open for booking."""

    BOOKED = "2"
    """Занят — slot is booked."""

    COMPLETED = "3"
    """Завершён — appointment completed."""

    CANCELLED = "4"
    """Отменён — booking cancelled."""


class ReceptionAudience(StrEnum):
    """Target audience for a reception slot.

    Maps to the ``TYPE`` field in reception records and the ``type``
    query parameter of :class:`~pskovedu.methods.reception.GetReception`.
    """

    PARENT = "parent"
    """Родители / parents."""

    STUDENT = "student"
    """Ученики / students."""

    ALL = "all"
    """Все / all audiences."""


class PerformanceKind(StrEnum):
    """Type of performance/progress report.

    Used by :class:`~pskovedu.methods.reports.ShowPerformanceByGrade`.
    """

    CURRENT = "current"
    """Текущая успеваемость."""

    PERIODIC = "periodic"
    """Итоговая за период."""

    YEAR = "year"
    """Годовая."""


class NotificationKind(StrEnum):
    """Portal notification/announcement type.

    Wire value is the ``TYPE`` field from ``USER_NOTIFICATION`` X1 records
    and the ``ExtJsDirectResponse`` notification envelope.
    """

    ANNOUNCEMENT = "1"
    """Объявление — general announcement (``TYPE="1"``)."""

    ALERT = "2"
    """Предупреждение — alert / warning."""

    INFO = "3"
    """Информация — informational message."""


class LessonKind(StrEnum):
    """Kind of lesson for schedule display.

    Observed in schedule LESSONS array (fields not fully captured in HAR).
    """

    REGULAR = "regular"
    """Обычный урок."""

    ELECTIVE = "elective"
    """Факультатив."""

    EXTRACURRICULAR = "extracurricular"
    """Внеурочная деятельность."""


class MarkKind(StrEnum):
    """Grade/mark type classification.

    Maps to ``GRADETYPES`` X1 model ``TYPE`` field.
    """

    CURRENT = "current"
    """Текущая оценка."""

    PERIODIC = "periodic"
    """Итоговая за период."""

    ANNUAL = "annual"
    """Годовая."""

    EXAM = "exam"
    """Экзаменационная."""


class HomeworkDisplayMode(StrEnum):
    """Homework display mode for diary filter.

    Wire values match the portal's ``homework-mode`` dropdown.
    """

    CURRENT = "current"
    """Задано на этом уроке."""

    PREVIOUS = "previous"
    """Задано на предыдущем уроке."""

    ALL = "all"
    """Показать все."""


class QrEventKind(StrEnum):
    """SSE event ``event:`` field values for the QR authentication stream.

    Source: ``constants.py`` SseEvent; ``security/auth.md`` §QR flow.
    """

    QR_AUTH_CONFIRMED = "qr-auth-confirmed"
    """QR code was scanned and authentication confirmed."""

    QR_ERROR = "qr-error"
    """QR authentication failed or timed out."""

    PING = "ping"
    """Server-sent keepalive."""

    WAITING = "waiting"
    """Stream is open, waiting for QR scan."""


class X1State(IntEnum):
    """Generic SYS_STATE values for X1 ORM records.

    Many models share these numeric state codes.
    """

    INACTIVE = 0
    ACTIVE = 1
    PUBLISHED = 2
    ARCHIVED = 3
    DELETED = 4
    BLOCKED = 5
    DRAFT = 6


class ReportBase(StrEnum):
    """Base path segment for portal report endpoints.

    Used in :data:`REPORT_FORM_META` to resolve the full report URL.
    """

    MONITOR = "/monitor"
    """Monitoring reports — served under ``/monitor/{tail}``."""

    REPORT = "/report"
    """Print/xls reports — served under ``/report/{tail}``."""


class ReportForm(StrEnum):
    """Enumeration of every known report form.

    Values are the URL tail segments as observed in the portal.  Each member
    maps to a ``(ReportBase, supports_xls)`` tuple via :data:`REPORT_FORM_META`.
    """

    FORM1 = "reportForm1"
    FORM2 = "reportForm2"
    FORM3 = "reportForm3"
    FORM4 = "reportForm4"
    FORM10 = "reportForm10"
    FORM12 = "reportForm12"
    FORM13 = "reportForm13"
    MONITORING_QUARANTINE = "reportmonitoringquarantine"
    MONITORING_SCHOOL = "reportmonitoringschool"
    MONITORING_SCHOOL_SKIP = "reportmonitoringschoolskip"
    CHILD_MARKS = "reportChildMarks"
    CHILD_MARKS_ALL = "reportChildMarksAll"
    TEACHERS_LIST = "reportTeachersList"


# Mapping: form → (base_path, supports_xls)
# reportForm* / reportmonitoring* → /monitor, xls supported
# reportChildMarks* / reportTeachersList → /report, xls supported
REPORT_FORM_META: dict[ReportForm, tuple[ReportBase, bool]] = {
    ReportForm.FORM1: (ReportBase.MONITOR, True),
    ReportForm.FORM2: (ReportBase.MONITOR, True),
    ReportForm.FORM3: (ReportBase.MONITOR, True),
    ReportForm.FORM4: (ReportBase.MONITOR, True),
    ReportForm.FORM10: (ReportBase.MONITOR, True),
    ReportForm.FORM12: (ReportBase.MONITOR, True),
    ReportForm.FORM13: (ReportBase.MONITOR, True),
    ReportForm.MONITORING_QUARANTINE: (ReportBase.MONITOR, True),
    ReportForm.MONITORING_SCHOOL: (ReportBase.MONITOR, True),
    ReportForm.MONITORING_SCHOOL_SKIP: (ReportBase.MONITOR, True),
    ReportForm.CHILD_MARKS: (ReportBase.REPORT, True),
    ReportForm.CHILD_MARKS_ALL: (ReportBase.REPORT, True),
    ReportForm.TEACHERS_LIST: (ReportBase.REPORT, True),
}


class ReportFmt(StrEnum):
    """Output format requested from :meth:`~pskovedu.client.Client.get_report`."""

    HTML = "html"
    XLS = "xls"
