"""Reports domain models (Ext.Direct ``Reports`` + ``ES\\Controller\\ReportController``).

All list-type results are wrapped in :class:`~pskovedu.models.common.EduPage`
at the method level; the individual domain objects here are ``EduObject``
subclasses with strict camelCase/UPPER_CASE alias mapping.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import ConfigDict, Field

from ._base import EduObject
from .common import MarkWeight
from .enums import PerformanceKind


class Grade(EduObject):
    """A school grade (класс) reference record.

    Returned by ``Reports.getGrades`` and ``Scheduler.getGrades``.

    Attributes:
        guid: grade GUID.
        name: grade display name, e.g. ``"11У"``.
        school_name: owning school name.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="guid")
    name: str = Field(..., alias="name")
    school_name: str | None = Field(None, alias="schoolName")


class Year(EduObject):
    """An academic year record.

    Returned by ``Reports.getYears``.

    Attributes:
        guid: year GUID.
        name: year display name, e.g. ``"2025-2026"``.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="guid")
    name: str = Field(..., alias="name")


class Period(EduObject):
    """An academic period reference (quarter / trimester / year).

    Returned by ``Reports.getPeriods``.

    Attributes:
        guid: period GUID.
        name: period name, e.g. ``"Первый квартал"``.
        parent_guid: parent period GUID, or ``None`` for year-level periods.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="guid")
    name: str = Field(..., alias="name")
    parent_guid: str | None = Field(None, alias="parentGuid")


class Teacher(EduObject):
    """A teacher reference record.

    Returned by ``Reports.getTeachers`` and ``Scheduler.getTeachers``.

    Attributes:
        guid: teacher GUID.
        full_name: full name (ФИО).
        subject: primary subject name, or ``None``.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="guid")
    full_name: str = Field(..., alias="fullName")
    subject: str | None = Field(None, alias="subject")


class GradeType(EduObject):
    """A grade/mark type (тип учебных отметок).

    Returned by ``Reports.getGradeTypes``.

    Attributes:
        guid: grade type GUID.
        name: display name.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="guid")
    name: str = Field(..., alias="name")


class MarkType(EduObject):
    """A mark value type definition (значения оценок).

    Returned by ``Reports.getMarkTypes``.

    Attributes:
        guid: mark type GUID.
        name: mark display value, e.g. ``"5"``, ``"н"``, ``"пт"``.
        numeric_value: numeric equivalent for averaging, or ``None``.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="guid")
    name: str = Field(..., alias="name")
    numeric_value: MarkWeight | None = Field(None, alias="numericValue")


class ParticipantRef(EduObject):
    """A participant reference from ``Reports.getParticipants``.

    Attributes:
        guid: participant GUID.
        full_name: student full name (ФИО).
        grade_name: class label.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="guid")
    full_name: str = Field(..., alias="fullName")
    grade_name: str | None = Field(None, alias="gradeName")


class Performance(EduObject):
    """A performance/grade record for a student in a period.

    Returned by ``ES\\Controller\\ReportController.showPerformanceByGrade``.

    Attributes:
        student_name: student full name.
        subject: subject name.
        mark: mark string.
        weight: mark weight (Decimal).
        period_name: academic period name.
        kind: performance report kind (:class:`~pskovedu.models.enums.PerformanceKind`).
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    student_name: str = Field(..., alias="studentName")
    subject: str = Field(..., alias="subject")
    mark: str = Field(..., alias="mark")
    weight: MarkWeight = Field(default=Decimal("1"), alias="weight")
    period_name: str | None = Field(None, alias="periodName")
    kind: PerformanceKind | None = Field(None, alias="kind")
