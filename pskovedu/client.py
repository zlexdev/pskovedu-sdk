"""Client — primary surface for the pskovedu SDK.

Owns ``__init__``, the ``session`` property, the universal ``__call__`` funnel,
and a flat method per endpoint; paginated endpoints expose ``iter_*`` helpers
that return an auto-fetching :class:`~pskovedu.pagination.iterator.PageIterator`.
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast

from .config import ClientConfig
from .logging import get_logger
from .sessions.httpx_session import HttpxSession
from .storage.base import BaseStorage
from .storage.memory import MemoryStorage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Generator
    from datetime import date, datetime, timedelta

    from .auth.manager import AuthManager
    from .auth.solvers.qr import DisplayCallback
    from .breaker.breaker import CircuitBreaker
    from .methods._base import BaseMethod
    from .methods.reports_print import _ReportHtml
    from .methods.scheduler import JournalRef
    from .models.common import EduPage
    from .models.diary import DiaryEntry, DiaryWeek, MarksReport
    from .models.eje import EjeResult
    from .models.enums import JournalState, ReceptionAudience, ReportForm, ReportFmt
    from .models.journal import Journal
    from .models.monitoring import MonitoringResult
    from .models.notifications import UserNotification
    from .models.reception import ReceptionSlot
    from .models.reports import (
        Grade,
        GradeType,
        MarkType,
        ParticipantRef,
        Performance,
        Period,
        Teacher,
        Year,
    )
    from .models.schedule import ScheduleDay
    from .models.session import Session, ShellConfig
    from .models.types import JournalCellValue, X1Filter
    from .models.util import AuthCheck, OAuthConfig
    from .models.x1 import X1PageModel, X1RecordModel
    from .pagination.iterator import PageIterator
    from .rate_limit.token_bucket import HostRateLimiter
    from .reactive.bell import LessonBell
    from .reactive.events import ReactiveEvent
    from .sessions.base import BaseSession
    from .storage.base import BaseStorage
    from .transport.sse import SseEvent

log = get_logger(__name__)

T = TypeVar("T")


class _MethodCall[T]:
    """Awaitable + async-iterable handle returned by :meth:`Client.__call__`.

    ``await``-ing it runs the method through the funnel and yields the typed
    result (unchanged from the original coroutine behaviour).  ``async for``-ing
    it iterates that result when the method produces an async-iterable — a
    :class:`~pskovedu.pagination.iterator.PageIterator` from a
    :class:`~pskovedu.methods._base.PaginatedMethod` — so callers can stream
    items directly with ``async for x in client(SomePages(...))``.  For a
    non-streaming method a ``TypeError`` points the caller back to ``await``.
    """

    __slots__ = ("_client", "_method")

    def __init__(self, client: Client, method: BaseMethod[T]) -> None:
        self._client = client
        self._method = method

    def __await__(self) -> Generator[Any, None, T]:
        return self._method.emit(self._client).__await__()

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[Any]:
        result = await self._method.emit(self._client)
        if not hasattr(result, "__aiter__"):
            raise TypeError(
                f"{type(self._method).__name__} is not streamable — its result "
                f"({type(result).__name__}) is not async-iterable; "
                f"use `await client(method)` instead of `async for`."
            )
        async for item in cast("AsyncIterator[Any]", result):
            yield item


# noinspection PyArgumentList
class Client:
    """Primary SDK surface — facade over all pskovedu API endpoints.

    Construction:

    ```python
    # Minimal — pre-set X1_SSO cookie (works immediately, no login needed)
    client = Client.from_cookie(x1_sso="<cookie-value>")
    session = await client.get_session()

    # Full async context manager (bootstrap + auth on enter, save + close on exit)
    async with Client.from_cookie(x1_sso="...") as client:
        session = await client.get_session()
    ```

    Args:
        config: ``ClientConfig`` instance; defaults to ``ClientConfig()`` when ``None``.
        shared: optional ``SharedInfra`` for multi-account transport sharing.
        storage: token + cookie persistence; defaults to ``MemoryStorage``.
        session_file: path to a JSON session file; auto-loads on enter, auto-saves
            on exit (convenience wrapper over ``FileStorage``).
    """

    def __init__(
        self,
        config: ClientConfig | None = None,
        *,
        shared: Any | None = None,
        storage: BaseStorage[Any] | None = None,
        session: BaseSession | None = None,
        session_file: str | Path | None = None,
        key_builder: Callable[[str], str] | None = None,
    ) -> None:
        self.config: ClientConfig = config or ClientConfig()
        self._storage: BaseStorage[Any] = storage or MemoryStorage()
        self._session_file = Path(session_file) if session_file else None
        self._shared = shared
        self._session: BaseSession = session or HttpxSession()
        self._auth_manager: AuthManager | None = None
        self._cookies: dict[str, str] = {}
        self._rate_limiter: HostRateLimiter | None = None
        self._breaker: CircuitBreaker | None = None
        self._shell: ShellConfig | None = None
        self._key: Callable[[str], str] = key_builder or (lambda k: k)

        if session_file is not None:
            from .storage.file import FileStorage

            self._storage = FileStorage(session_file)

    @property
    def session(self) -> BaseSession:
        """The underlying ``BaseSession`` that owns the ``make_request`` funnel."""
        return self._session

    @classmethod
    def from_cookie(
        cls,
        x1_sso: str,
        *,
        session_file: str | Path | None = None,
        config: ClientConfig | None = None,
        key_builder: Callable[[str], str] | None = None,
    ) -> Client:
        """Construct a ``Client`` pre-loaded with an X1_SSO cookie.

        The cookie is injected into every request via the minimal cookie path
        in ``BaseSession.make_request`` before a full ``AuthManager`` is wired.

        Args:
            x1_sso: value of the ``X1_SSO`` cookie from a browser session.
            session_file: optional path to a JSON session file for persistence.
            config: optional ``ClientConfig`` override.
            key_builder: optional callable that namespaces storage keys
                (e.g. ``lambda k: f"account_{uid}_{k}"`` for multi-account setups).
        """
        client = cls(config=config, session_file=session_file, key_builder=key_builder)
        client._cookies["X1_SSO"] = x1_sso
        log.info("client.from_cookie", host=client.config.hosts)
        return client

    async def __aenter__(self) -> Client:
        """Bootstrap + restore saved cookies on entry."""
        saved: dict[str, str] | None = await self._storage.get(self._key("_session_cookies"))
        if saved:
            self._cookies.update(saved)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Save session to storage and close the transport on exit."""
        await self.save()
        await self._session.close()

    async def save(self) -> None:
        """Persist the current cookie jar to storage under the namespaced key."""
        if self._cookies:
            await self._storage.set(self._key("_session_cookies"), self._cookies)

    def __call__(self, method: BaseMethod[T]) -> _MethodCall[T]:
        """Universal executor — route any ``BaseMethod[T]`` through the funnel.

        Returns a dual-mode handle:

        - ``await client(method)`` runs the method once and returns its typed
          result (identical to the previous coroutine behaviour — every
          ``await self(...)`` call site is unaffected).
        - ``async for item in client(method)`` iterates the result when the
          method streams; e.g. ``async for entry in client(DiaryPages(...))``
          walks every item across auto-fetched pages without an explicit
          ``iter_*`` helper.
        """
        method.as_(self)
        return _MethodCall(self, method)

    async def login_with_qr(self, *, display_cb: DisplayCallback | None = None) -> Session:
        """Authenticate via the QR SSE flow and return the resulting session.

        Lazily constructs an :class:`~pskovedu.auth.manager.AuthManager` if
        one is not already attached to this client, drives the full QR flow
        (generate → display → subscribe → confirm → cookie injection), then
        returns the current portal session via :meth:`get_session`.

        Args:
            display_cb: optional callable invoked with the QR URL string so
                the caller can display it (e.g. print to terminal or render
                as an image).  May be sync or async.

        Returns:
            The :class:`~pskovedu.models.session.Session` obtained after
            successful authentication.
        """
        if self._auth_manager is None:
            from .auth.manager import AuthManager

            self._auth_manager = AuthManager()

        await self._auth_manager.login_with_qr(self, display_cb=display_cb)
        return await self.get_session()

    async def get_session(self) -> Session:
        from .methods.session import GetSession

        return await self(GetSession())

    async def get_shell(self) -> ShellConfig:
        """Fetch the app-shell HTML and parse it into a typed ``ShellConfig``.

        Convenience over ``GetShell`` + ``parsers.shell.parse_shell``: returns
        the extracted ``REMOTING_API`` (Ext.Direct catalogue) and ``X1_CONFIG``
        (role meta + X1 model registry) instead of the raw HTML.
        """
        from .constants import Host
        from .methods.session import GetShell
        from .parsers.shell import parse_shell

        shell = await self(GetShell())
        portal_url = self.config.hosts.get(Host.PORTAL, "https://one.pskovedu.ru/")
        return parse_shell(shell.raw_html, url=portal_url)

    async def get_diary(self, participant_guid: str, *, date: str | None = None) -> DiaryWeek:
        from .methods.diary import GetDiary

        if date is None:
            return await self(GetDiary(participant_guid=participant_guid))
        return await self(GetDiary(participant_guid=participant_guid, date=date))

    async def get_marks_report(
        self, participant_guid: str, *, with_dates: bool = False
    ) -> MarksReport:
        from .methods.diary import GetMarksReport

        return await self(GetMarksReport(participant_guid=participant_guid, with_dates=with_dates))

    async def get_diary_xls(self, participant_guid: str, *, date: str | None = None) -> bytes:
        from .methods.diary import GetDiaryXls

        if date is None:
            return await self(GetDiaryXls(participant_guid=participant_guid))
        return await self(GetDiaryXls(participant_guid=participant_guid, date=date))

    async def iter_diary(
        self,
        participant_guid: str,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> PageIterator[DiaryEntry]:
        from .methods.diary import DiaryPages

        result: PageIterator[DiaryEntry] = await self(
            DiaryPages(participant_guid=participant_guid, start=start, end=end)
        )
        return result

    async def get_schedule(self, grade_guid: str, *, date: str | None = None) -> ScheduleDay:
        from .methods.schedule import GetSchedule

        if date is None:
            return await self(GetSchedule(grade_guid=grade_guid))
        return await self(GetSchedule(grade_guid=grade_guid, date_str=date))

    async def get_current_schedule(self) -> ScheduleDay:
        from .methods.schedule import GetCurrentSchedule

        return await self(GetCurrentSchedule())

    async def iter_schedule(
        self, grade_guid: str, *, start: date, end: date
    ) -> PageIterator[ScheduleDay]:
        from .methods.schedule import SchedulePages

        result: PageIterator[ScheduleDay] = await self(
            SchedulePages(grade_guid=grade_guid, start=start, end=end)
        )
        return result

    async def get_grades(self) -> EduPage[Grade]:
        from .methods.reports import GetGrades

        return await self(GetGrades())

    async def get_years(self) -> EduPage[Year]:
        from .methods.reports import GetYears

        return await self(GetYears())

    async def get_periods(self) -> EduPage[Period]:
        from .methods.reports import GetPeriods

        return await self(GetPeriods())

    async def get_teachers(self) -> EduPage[Teacher]:
        from .methods.reports import GetTeachers

        return await self(GetTeachers())

    async def get_grade_types(self) -> EduPage[GradeType]:
        from .methods.reports import GetGradeTypes

        return await self(GetGradeTypes())

    async def get_mark_types(self) -> EduPage[MarkType]:
        from .methods.reports import GetMarkTypes

        return await self(GetMarkTypes())

    async def get_participants(self) -> EduPage[ParticipantRef]:
        from .methods.reports import GetParticipants

        return await self(GetParticipants())

    async def show_performance_by_grade(self) -> EduPage[Performance]:
        from .methods.reports import ShowPerformanceByGrade

        return await self(ShowPerformanceByGrade())

    async def sched_get_grades(self) -> EduPage[Grade]:
        from .methods.scheduler import SchedGetGrades

        return await self(SchedGetGrades())

    async def sched_get_teachers(self) -> EduPage[Teacher]:
        from .methods.scheduler import SchedGetTeachers

        return await self(SchedGetTeachers())

    async def get_journals(self) -> EduPage[JournalRef]:
        from .methods.scheduler import GetJournals

        return await self(GetJournals())

    async def read_journal(self, grades: list[str]) -> EduPage[Journal]:
        from .methods.journal import ReadJournal

        return await self(ReadJournal(grades=grades))

    async def get_journal(self, journal_guid: str) -> Journal:
        from .methods.journal import GetJournal

        return await self(GetJournal(journal_guid=journal_guid))

    async def save_journal(
        self,
        journal_guid: str,
        *,
        state: JournalState | None = None,
        rows: list[dict[str, JournalCellValue]] | None = None,
    ) -> Journal:
        from .methods.journal import SaveJournal
        from .models.enums import JournalState

        return await self(
            SaveJournal(
                journal_guid=journal_guid,
                state=state if state is not None else JournalState.ACTIVE,
                rows=rows or [],
            )
        )

    async def delete_journal(self, journal_guid: str) -> None:
        from .methods.journal import DeleteJournal

        return await self(DeleteJournal(journal_guid=journal_guid))

    async def monitoring_read(self, grades: list[str]) -> MonitoringResult:
        from .methods.monitoring import MonitoringRead

        return await self(MonitoringRead(grades=grades))

    async def monitoring_read_skip(self, part: str) -> MonitoringResult:
        from .methods.monitoring import MonitoringReadSkip

        return await self(MonitoringReadSkip(part=part))

    async def get_user_notifications(
        self, *, where: X1Filter | None = None, limit: int | None = None
    ) -> EduPage[UserNotification]:
        from .methods.notifications import GetUserNotifications

        return await self(GetUserNotifications(where=where or {}, limit=limit))

    async def get_reception(
        self, start: str, end: str, *, audience: ReceptionAudience | None = None
    ) -> EduPage[ReceptionSlot]:
        from .methods.reception import GetReception
        from .models.enums import ReceptionAudience

        return await self(
            GetReception(
                start=start,
                end=end,
                type=audience if audience is not None else ReceptionAudience.ALL,
            )
        )

    async def get_avatar(self, uuid: str) -> bytes:
        from .methods.avatar import GetAvatar

        return await self(GetAvatar(uuid=uuid))

    async def x1_query(
        self, model: str, *, where: X1Filter | None = None, limit: int | None = None
    ) -> X1PageModel:
        from .methods.x1 import X1Query

        return await self(X1Query(model=model, where=where or {}, limit=limit))

    async def x1_get(self, model: str, guid: str) -> X1RecordModel:
        from .methods.x1 import X1Get

        return await self(X1Get(model=model, guid=guid))

    async def get_report(
        self, form: ReportForm, *, fmt: ReportFmt | None = None, **params: str
    ) -> bytes | _ReportHtml:
        if fmt == "xls" or fmt is not None and fmt.value == "xls":
            from .methods.reports_print import GetReportXls

            return await self(GetReportXls(form=form, params=params))
        from .methods.reports_print import GetReportHtml

        return await self(GetReportHtml(form=form, params=params))

    async def eje_homework(self) -> EjeResult:
        from .methods.eje import EjeHomework

        return await self(EjeHomework())

    async def eje_journal_planner(self) -> EjeResult:
        from .methods.eje import EjeJournalPlanner

        return await self(EjeJournalPlanner())

    async def eje_participants(self) -> EjeResult:
        from .methods.eje import EjeParticipants

        return await self(EjeParticipants())

    async def eje_topics(self) -> EjeResult:
        from .methods.eje import EjeTopics

        return await self(EjeTopics())

    async def eje_integrations(self) -> EjeResult:
        from .methods.eje import EjeIntegrations

        return await self(EjeIntegrations())

    async def check_auth(self, token: str) -> AuthCheck:
        from .methods.util import CheckAuth

        return await self(CheckAuth(value=token))

    async def get_oauth_config(self) -> OAuthConfig:
        from .methods.util import GetOAuthConfig

        return await self(GetOAuthConfig())

    async def subscribe_qr(self, uuid: str) -> AsyncIterator[SseEvent]:
        """Open the QR-auth SSE stream and yield events until confirmation.

        Streams ``GET esia.gosuslugi.ru/qr-delegate/qr/subscribe/{uuid}`` and
        yields each :class:`~pskovedu.transport.sse.SseEvent` (``event`` name +
        raw ``data``) until the terminal ``qr-auth-confirmed`` event arrives,
        after which the connection is closed automatically.  Breaking out of the
        loop early also closes the stream.

        Args:
            uuid: QR session UUID to subscribe to.
        """
        from .methods.qr import QrAuthEvent

        stream = await self._session.open_stream(self, QrAuthEvent(uuid=uuid))
        async for event in stream:
            yield event


    def watch_marks(
        self,
        participant_guid: str,
        *,
        interval: float = 30.0,
        backoff_max: float = 300.0,
        storage: BaseStorage[Any] | None = None,
    ) -> AsyncIterator[ReactiveEvent]:
        """Return an async-iterator that polls marks and emits change events.

        Args:
            participant_guid: GUID of the diary participant to watch.
            interval: seconds between successful polls (default ``30.0``).
            backoff_max: maximum back-off ceiling on transient errors (default ``300.0``).
            storage: optional state store for dedup across restarts.
        """
        from .reactive.watchers import MarkWatcher

        return MarkWatcher(
            self, participant_guid, interval=interval, backoff_max=backoff_max, storage=storage
        ).events()

    def watch_homework(
        self,
        participant_guid: str,
        *,
        interval: float = 30.0,
        backoff_max: float = 300.0,
        storage: BaseStorage[Any] | None = None,
    ) -> AsyncIterator[ReactiveEvent]:
        """Return an async-iterator that polls the diary and emits new-homework events.

        Args:
            participant_guid: GUID of the diary participant to watch.
            interval: seconds between successful polls (default ``30.0``).
            backoff_max: maximum back-off ceiling on transient errors (default ``300.0``).
            storage: optional state store for dedup across restarts.
        """
        from .reactive.watchers import HomeworkWatcher

        return HomeworkWatcher(
            self, participant_guid, interval=interval, backoff_max=backoff_max, storage=storage
        ).events()

    def watch_schedule(
        self,
        grade_guid: str,
        *,
        interval: float = 30.0,
        backoff_max: float = 300.0,
        storage: BaseStorage[Any] | None = None,
    ) -> AsyncIterator[ReactiveEvent]:
        """Return an async-iterator that polls the schedule and emits change events.

        Args:
            grade_guid: GUID of the grade whose schedule to watch.
            interval: seconds between successful polls (default ``30.0``).
            backoff_max: maximum back-off ceiling on transient errors (default ``300.0``).
            storage: optional state store for dedup across restarts.
        """
        from .reactive.watchers import ScheduleWatcher

        return ScheduleWatcher(
            self, grade_guid, interval=interval, backoff_max=backoff_max, storage=storage
        ).events()

    def watch_reception(
        self,
        start: str,
        end: str,
        *,
        audience: ReceptionAudience | None = None,
        interval: float = 30.0,
        backoff_max: float = 300.0,
        storage: BaseStorage[Any] | None = None,
    ) -> AsyncIterator[ReactiveEvent]:
        """Return an async-iterator that polls reception slots and emits new-slot events.

        Args:
            start: date range start in ``"DD.MM.YYYY"`` format.
            end: date range end in ``"DD.MM.YYYY"`` format.
            audience: optional audience filter
                (:class:`~pskovedu.models.enums.ReceptionAudience`).
            interval: seconds between successful polls (default ``30.0``).
            backoff_max: maximum back-off ceiling on transient errors (default ``300.0``).
            storage: optional state store for dedup across restarts.
        """
        from .reactive.watchers import ReceptionWatcher

        return ReceptionWatcher(
            self, start, end, audience, interval=interval, backoff_max=backoff_max, storage=storage
        ).events()

    def lesson_bell(
        self,
        schedule: ScheduleDay,
        *,
        lead: timedelta | None = None,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> LessonBell:
        """Construct a :class:`~pskovedu.reactive.bell.LessonBell` for *schedule*.

        Args:
            schedule: a :class:`~pskovedu.models.schedule.ScheduleDay` to drive.
            lead: how far before lesson start to emit
                :class:`~pskovedu.reactive.events.LessonStarting`
                (default ``timedelta(minutes=5)``).
            now: zero-arg callable returning the current datetime
                (default: ``datetime.now``; local-naive).
            sleep: async callable accepting seconds; defaults to ``asyncio.sleep``.
        """
        from .reactive.bell import LessonBell as _LessonBell

        kwargs: dict[str, Any] = {}
        if lead is not None:
            kwargs["lead"] = lead
        if now is not None:
            kwargs["now"] = now
        if sleep is not None:
            kwargs["sleep"] = sleep
        return _LessonBell(schedule, **kwargs)
