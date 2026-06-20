"""EJE (electronic journal) read method-classes.

All five endpoints are simple ``GET`` requests that return an :class:`EjeResult`
envelope.  Response shapes are **unverified** — bodies have not been captured
in HAR; the model is intentionally permissive (see decision D7 in
00-decisions.md and the ``# unverified shape`` markers below).
"""

from __future__ import annotations

from ..constants import (
    PATH_EJE_HOMEWORK,
    PATH_EJE_INTEGRATIONS,
    PATH_EJE_JOURNAL_PLANNER,
    PATH_EJE_PARTICIPANTS,
    PATH_EJE_TOPICS,
)
from ..models.eje import EjeResult
from ._bases import RestMethod


# unverified shape
class _Eje(RestMethod[EjeResult]):
    """Shared base for all EJE read endpoints.

    Pins ``__http_method__ = "GET"`` and ``__returning__ = EjeResult``.
    Concrete subclasses only set ``__url__``.
    """

    __http_method__ = "GET"


# unverified shape
class EjeHomework(_Eje):
    """Fetch homework data from the EJE module.

    REST: ``GET /eje/homework/teacher/``
    """

    __url__ = PATH_EJE_HOMEWORK


# unverified shape
class EjeJournalPlanner(_Eje):
    """Fetch journal planner data from the EJE module.

    REST: ``GET /eje/journal-planner/journal/``
    """

    __url__ = PATH_EJE_JOURNAL_PLANNER


# unverified shape
class EjeParticipants(_Eje):
    """Fetch participants list from the EJE module.

    REST: ``GET /eje/participants-list/index/``
    """

    __url__ = PATH_EJE_PARTICIPANTS


# unverified shape
class EjeTopics(_Eje):
    """Fetch topics index from the EJE module.

    REST: ``GET /eje/topics/index/``
    """

    __url__ = PATH_EJE_TOPICS


# unverified shape
class EjeIntegrations(_Eje):
    """Fetch integrations list from the EJE module.

    REST: ``GET /eje/integrations/list/``
    """

    __url__ = PATH_EJE_INTEGRATIONS
