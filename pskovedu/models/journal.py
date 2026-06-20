"""Journal domain models (Ext.Direct ``JournalService`` action).

The journal is the core grade-entry surface.  The lifecycle of a journal
record is governed by ``JournalState`` with allowed transitions declared in
:data:`JOURNAL_TRANSITIONS` and enforced via :func:`assert_journal_transition`.

Write methods (:class:`~pskovedu.methods.journal.SaveJournal`,
:class:`~pskovedu.methods.journal.DeleteJournal`) respect
``ClientConfig.allow_mutations`` — they raise
:exc:`~pskovedu.exceptions.MutationsDisabled` before any network call when
mutations are disabled (the default).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import ConfigDict, Field

from ._base import EduObject
from .common import Guid, MarkWeight
from .enums import JournalState

if TYPE_CHECKING:
    from ..methods.journal import SaveJournal


#: Allowed target states for each current state.
#: Immutable at runtime — transitions are only checked, never mutated.
JOURNAL_TRANSITIONS: dict[JournalState, frozenset[JournalState]] = {
    JournalState.DRAFT: frozenset({JournalState.ACTIVE}),
    JournalState.ACTIVE: frozenset({JournalState.ARCHIVED, JournalState.DRAFT}),
    JournalState.ARCHIVED: frozenset({JournalState.ACTIVE}),
    JournalState.DELETED: frozenset(),  # terminal state
}


def assert_journal_transition(current: JournalState, target: JournalState) -> None:
    """Assert that transitioning from *current* to *target* is valid.

    Args:
        current: current :class:`~pskovedu.models.enums.JournalState`.
        target: desired target :class:`~pskovedu.models.enums.JournalState`.

    Raises:
        :exc:`~pskovedu.exceptions.InvalidStateTransition`: when the transition
            is not in :data:`JOURNAL_TRANSITIONS`.
    """
    from ..exceptions import InvalidStateTransition

    allowed = JOURNAL_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidStateTransition(
            current=str(current),
            target=str(target),
            allowed=frozenset(str(s) for s in allowed),
        )


class JournalRow(EduObject):
    """A single row (student mark entry) within a journal.

    Attributes:
        guid: row GUID.
        student_name: student full name.
        student_guid: student GUID.
        mark: mark string (``"5"``, ``"н"``, ``"пт"``, etc.).
        weight: mark weight (Decimal).
        lesson_date: lesson date ``"DD.MM.YYYY"``.
        lesson_number: lesson slot number.
        topic: lesson topic, or ``None``.
        homework: homework text, or ``None``.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="SYS_GUID")
    student_name: str = Field(..., alias="studentName")
    student_guid: str = Field(..., alias="studentGuid")
    mark: str = Field(default="", alias="mark")
    weight: MarkWeight = Field(default=Decimal("1"), alias="weight")
    lesson_date: str = Field(..., alias="lessonDate")
    lesson_number: int | None = Field(None, alias="lessonNumber")
    topic: str | None = Field(None, alias="topic")
    homework: str | None = Field(None, alias="homework")


class Journal(EduObject):
    """A grade journal with bound save/state-transition methods.

    Obtained from :class:`~pskovedu.methods.journal.GetJournal` or
    :class:`~pskovedu.methods.journal.ReadJournal`.  Provides a bound
    :meth:`save` method that enforces the state machine via
    :func:`assert_journal_transition`.

    Attributes:
        guid: journal GUID.
        name: journal display name.
        state: current lifecycle state (:class:`~pskovedu.models.enums.JournalState`).
        grade_name: class label.
        subject_name: subject name.
        teacher_name: teacher name.
        rows: list of :class:`JournalRow` entries.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: Guid = Field(..., alias="SYS_GUID")
    name: str = Field(..., alias="name")
    state: JournalState = Field(JournalState.DRAFT, alias="SYS_STATE")
    grade_name: str | None = Field(None, alias="gradeName")
    subject_name: str | None = Field(None, alias="subjectName")
    teacher_name: str | None = Field(None, alias="teacherName")
    rows: list[JournalRow] = Field(default_factory=list, alias="rows")

    def save(self, target_state: JournalState | None = None) -> SaveJournal:
        """Return a bound :class:`~pskovedu.methods.journal.SaveJournal` method.

        If *target_state* is given, validates the transition via
        :func:`assert_journal_transition` before constructing the method.

        Args:
            target_state: desired new state, or ``None`` to keep current state.

        Raises:
            :exc:`~pskovedu.exceptions.InvalidStateTransition`: when *target_state*
                is not a valid transition from the current state.
            :exc:`~pskovedu.exceptions.MutationsDisabled`: when ``allow_mutations``
                is ``False`` on the bound client config.
        """
        from ..methods.journal import SaveJournal

        new_state = target_state or self.state
        if target_state is not None and target_state != self.state:
            assert_journal_transition(self.state, target_state)

        return SaveJournal(
            journal_guid=self.guid,
            state=new_state,
        ).as_(self._require_client())
