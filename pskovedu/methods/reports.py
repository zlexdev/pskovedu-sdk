"""Reports method-classes (Ext.Direct ``Reports`` + ``ReportController`` actions).

All methods use ``POST /extjs/direct`` with zero positional args (``len=0`` in
REMOTING_API) — ``__arg_order__`` inherits the empty tuple from ``ExtDirectMethod``.
"""

from __future__ import annotations

from typing import ClassVar

from ..constants import RemotingAction, RemotingMethod
from ..models.common import EduPage
from ..models.reports import (
    Grade,
    GradeType,
    MarkType,
    ParticipantRef,
    Performance,
    Period,
    Teacher,
    Year,
)
from ._bases import ExtDirectMethod


class GetGrades(ExtDirectMethod[EduPage[Grade]]):
    """Fetch all grades (classes) available to the current user.

    Ext.Direct: ``Reports.getGrades`` (``len=0``, no args).
    """

    __action__: ClassVar[str] = RemotingAction.REPORTS
    __rpc_method__: ClassVar[str] = RemotingMethod.GET_GRADES


class GetYears(ExtDirectMethod[EduPage[Year]]):
    """Fetch all academic years available to the current user.

    Ext.Direct: ``Reports.getYears`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.REPORTS
    __rpc_method__: ClassVar[str] = RemotingMethod.GET_YEARS


class GetPeriods(ExtDirectMethod[EduPage[Period]]):
    """Fetch all academic periods available to the current user.

    Ext.Direct: ``Reports.getPeriods`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.REPORTS
    __rpc_method__: ClassVar[str] = RemotingMethod.GET_PERIODS


class GetTeachers(ExtDirectMethod[EduPage[Teacher]]):
    """Fetch all teachers available to the current user.

    Ext.Direct: ``Reports.getTeachers`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.REPORTS
    __rpc_method__: ClassVar[str] = RemotingMethod.GET_TEACHERS


class GetGradeTypes(ExtDirectMethod[EduPage[GradeType]]):
    """Fetch all grade/mark types (типы учебных отметок).

    Ext.Direct: ``Reports.getGradeTypes`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.REPORTS
    __rpc_method__: ClassVar[str] = RemotingMethod.GET_GRADE_TYPES


class GetMarkTypes(ExtDirectMethod[EduPage[MarkType]]):
    """Fetch all mark value types (значения оценок).

    Ext.Direct: ``Reports.getMarkTypes`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.REPORTS
    __rpc_method__: ClassVar[str] = RemotingMethod.GET_MARK_TYPES


class GetParticipants(ExtDirectMethod[EduPage[ParticipantRef]]):
    """Fetch all participants (students) visible to the current user.

    Ext.Direct: ``Reports.getParticipants`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.REPORTS
    __rpc_method__: ClassVar[str] = RemotingMethod.GET_PARTICIPANTS


class ShowPerformanceByGrade(ExtDirectMethod[EduPage[Performance]]):
    """Fetch performance/grade analytics for a grade.

    Ext.Direct: ``ES\\Controller\\ReportController.showPerformanceByGrade`` (``len=0``).
    """

    __action__: ClassVar[str] = RemotingAction.REPORT_CONTROLLER
    __rpc_method__: ClassVar[str] = RemotingMethod.SHOW_PERFORMANCE_BY_GRADE
