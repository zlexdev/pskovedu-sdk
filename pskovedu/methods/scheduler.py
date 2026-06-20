"""Scheduler method-classes (Ext.Direct ``Scheduler`` action).

REMOTING_API: ``Scheduler: [getGrades(len=0), getTeachers(len=0), getJournals(len=0)]``
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import ConfigDict, Field

from ..constants import RemotingAction, RemotingMethod
from ..models._base import EduObject
from ..models.common import EduPage
from ..models.reports import Grade, Teacher
from ._bases import ExtDirectMethod


class JournalRef(EduObject):
    """A journal reference entry returned by ``Scheduler.getJournals``.

    Lightweight — contains only identifying metadata.  Use
    :class:`~pskovedu.methods.journal.ReadJournal` to fetch full journal data.

    Attributes:
        guid: journal GUID.
        name: journal display name.
        grade_name: associated grade/class name, or ``None``.
        subject_name: subject name, or ``None``.
        teacher_name: teacher name, or ``None``.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="guid")
    name: str = Field(..., alias="name")
    grade_name: str | None = Field(None, alias="gradeName")
    subject_name: str | None = Field(None, alias="subjectName")
    teacher_name: str | None = Field(None, alias="teacherName")


class SchedGetGrades(ExtDirectMethod[EduPage[Grade]]):
    """Fetch grades available for schedule/journal operations.

    Ext.Direct: ``Scheduler.getGrades`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.SCHEDULER
    __rpc_method__: ClassVar[str] = RemotingMethod.SCHED_GET_GRADES


class SchedGetTeachers(ExtDirectMethod[EduPage[Teacher]]):
    """Fetch teachers available for schedule/journal operations.

    Ext.Direct: ``Scheduler.getTeachers`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.SCHEDULER
    __rpc_method__: ClassVar[str] = RemotingMethod.SCHED_GET_TEACHERS


class GetJournals(ExtDirectMethod[EduPage[JournalRef]]):
    """Fetch journals available for the current user.

    Ext.Direct: ``Scheduler.getJournals`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.SCHEDULER
    __rpc_method__: ClassVar[str] = RemotingMethod.SCHED_GET_JOURNALS
