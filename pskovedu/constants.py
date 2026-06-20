"""SDK-wide constants: Host enum, base paths, REMOTING action names, SSE event names."""

from __future__ import annotations

from enum import StrEnum

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class Host(StrEnum):
    """Logical host identifiers used in ``ClientConfig.hosts`` and ``BaseMethod.__host__``."""

    PORTAL = "portal"  # one.pskovedu.ru — main portal + Ext.Direct + X1
    PASSPORT = "passport"  # passport.pskovedu.ru — SSO / ESIA callback
    ESIA = "esia"  # esia.gosuslugi.ru — ESIA OAuth2 / QR SSE
    SFD = "sfd"  # sfd.gosuslugi.ru — ESIA session JWT endpoint


# Default base URLs for each logical host
DEFAULT_HOSTS: dict[Host, str] = {
    Host.PORTAL: "https://one.pskovedu.ru",
    Host.PASSPORT: "https://passport.pskovedu.ru",
    Host.ESIA: "https://esia.gosuslugi.ru",
    Host.SFD: "https://sfd.gosuslugi.ru",
}


PATH_EXT_DIRECT = "/extjs/direct"
PATH_X1_CALL = "/x1db/service/call"
PATH_SCHEDULE = "/schedule/index/schedule/grade/{grade_guid}/{date}"
PATH_SCHEDULE_CURRENT = "/schedule/index/current"
PATH_DIARY = "/edv/index/diary/{student_guid}"
PATH_PARTICIPANT = "/edv/index/participant"
PATH_SHELL = "/"  # GET / → HTML containing REMOTING_API + X1_CONFIG

# ESIA / passport paths
PATH_ESIA_REDIRECT = "/auth/esia/redirect"
PATH_ESIA_RETURN = "/auth/esia/return"
PATH_ESIA_OAUTH_AC = "/aas/oauth2/ac"
PATH_ESIA_AVATAR = "/esia-rs/api/public/v1/avatar/{uuid}"
PATH_QR_GENERATE = "/qr-delegate/qr/generate"
PATH_QR_CONFIRM = "/qr-delegate/qr/confirm"  # unverified
PATH_QR_SUBSCRIBE = "/qr-delegate/qr/subscribe/{uuid}"
PATH_SFD_SESSION = "/session"

# Utility / auth paths
PATH_CHECK_AUTH = "/common-api/check-auth"
PATH_OAUTH_CONFIG = "/aas/oauth2/config"

# EJE (electronic journal) read paths
PATH_EJE_HOMEWORK = "/eje/homework/teacher/"
PATH_EJE_JOURNAL_PLANNER = "/eje/journal-planner/journal/"
PATH_EJE_PARTICIPANTS = "/eje/participants-list/index/"
PATH_EJE_TOPICS = "/eje/topics/index/"
PATH_EJE_INTEGRATIONS = "/eje/integrations/list/"

# Source: window.REMOTING_API parsed from GET / HTML (html_pages.md)


class RemotingAction(StrEnum):
    """Ext.Direct action names exactly as they appear in ``window.REMOTING_API``."""

    X1API = "X1API"
    REPORTS = "Reports"
    SCHEDULER = "Scheduler"
    JOURNAL_SERVICE = "JournalService"
    RECEPTION = "Reception"
    MONITORING = "monitoring"
    REPORT_CONTROLLER = "ES\\Controller\\ReportController"


class RemotingMethod(StrEnum):
    """Ext.Direct method names (value = wire ``method`` field)."""

    # X1API
    X1_DIRECT = "direct"

    # Reports
    GET_GRADES = "getGrades"
    GET_YEARS = "getYears"
    GET_PERIODS = "getPeriods"
    GET_TEACHERS = "getTeachers"
    GET_GRADE_TYPES = "getGradeTypes"
    GET_MARK_TYPES = "getMarkTypes"
    GET_PARTICIPANTS = "getParticipants"

    # Scheduler
    SCHED_GET_GRADES = "getGrades"
    SCHED_GET_TEACHERS = "getTeachers"
    SCHED_GET_JOURNALS = "getJournals"

    # JournalService
    JOURNAL_READ = "read"
    JOURNAL_GET = "getJournal"
    JOURNAL_SAVE = "save"
    JOURNAL_DELETE = "deleteJournal"

    # Reception
    GET_RECEPTION = "getReception"

    # monitoring
    MONITORING_READ = "read"
    MONITORING_READ_SKIP = "readskip"

    # ES\Controller\ReportController
    SHOW_PERFORMANCE_BY_GRADE = "showPerformanceByGrade"


class SseEvent(StrEnum):
    """SSE event ``event:`` field values for the QR subscribe stream."""

    QR_AUTH_CONFIRMED = "qr-auth-confirmed"
    QR_ERROR = "qr-error"
    QR_PING = "ping"
    QR_WAITING = "waiting"
