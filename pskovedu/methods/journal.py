"""Journal method-classes (Ext.Direct ``JournalService`` action).

Write methods (``SaveJournal``, ``DeleteJournal``) check
``ClientConfig.allow_mutations`` and raise
:exc:`~pskovedu.exceptions.MutationsDisabled` before any network call when
mutations are disabled (the default: ``allow_mutations=False``).

REMOTING_API::

    "JournalService": [
        {"name": "read",          "params": ["grades"]},
        {"name": "getJournal",    "len": 1},
        {"name": "save",          "len": 0},
        {"name": "deleteJournal", "len": 0}
    ]
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..constants import RemotingAction, RemotingMethod
from ..exceptions import MutationsDisabled
from ..models.common import EduPage
from ..models.enums import JournalState
from ..models.journal import Journal
from ._bases import ExtDirectMethod


class ReadJournal(ExtDirectMethod[EduPage[Journal]]):
    """Read journals for a list of grades.

    Ext.Direct: ``JournalService.read`` with positional arg ``grades``.

    Args:
        grades: list of grade GUIDs to read journals for.
    """

    __action__ = RemotingAction.JOURNAL_SERVICE
    __rpc_method__ = RemotingMethod.JOURNAL_READ
    __arg_order__ = ("grades",)

    grades: list[str]


class GetJournal(ExtDirectMethod[Journal]):
    """Fetch a single journal by GUID.

    Ext.Direct: ``JournalService.getJournal`` (``len=1``, positional arg = journal GUID).

    Args:
        journal_guid: GUID of the journal to fetch.
    """

    __action__ = RemotingAction.JOURNAL_SERVICE
    __rpc_method__ = RemotingMethod.JOURNAL_GET
    __arg_order__ = ("journal_guid",)

    journal_guid: str


class SaveJournal(ExtDirectMethod[Journal]):
    """Save (create or update) a journal record.

    Ext.Direct: ``JournalService.save`` (``len=0`` — full body as single arg).

    Raises :exc:`~pskovedu.exceptions.MutationsDisabled` before any network
    call when ``ClientConfig.allow_mutations`` is ``False``.

    Args:
        journal_guid: GUID of the journal to save.
        state: target lifecycle state (:class:`~pskovedu.models.enums.JournalState`).
        rows: updated journal row list, or empty list to save without row changes.
    """

    __action__ = RemotingAction.JOURNAL_SERVICE
    __rpc_method__ = RemotingMethod.JOURNAL_SAVE
    __arg_order__ = ("journal_guid", "state", "rows")

    journal_guid: str = Field(..., alias="SYS_GUID")
    state: JournalState = Field(JournalState.ACTIVE, alias="SYS_STATE")
    rows: list[dict[str, Any]] = Field(default_factory=list, alias="rows")

    async def emit(self, client: Any) -> Journal:
        """Guard mutations before delegating to the session funnel."""
        config = getattr(client, "config", None)
        if config is not None and not getattr(config, "allow_mutations", False):
            raise MutationsDisabled(type(self).__name__)
        return await super().emit(client)


class DeleteJournal(ExtDirectMethod[None]):
    """Delete a journal record.

    Ext.Direct: ``JournalService.deleteJournal`` (``len=0``).

    Raises :exc:`~pskovedu.exceptions.MutationsDisabled` before any network
    call when ``ClientConfig.allow_mutations`` is ``False``.

    Args:
        journal_guid: GUID of the journal to delete.
    """

    __action__ = RemotingAction.JOURNAL_SERVICE
    __rpc_method__ = RemotingMethod.JOURNAL_DELETE
    __arg_order__ = ("journal_guid",)

    journal_guid: str = Field(..., alias="SYS_GUID")

    async def emit(self, client: Any) -> None:
        """Guard mutations before delegating to the session funnel."""
        config = getattr(client, "config", None)
        if config is not None and not getattr(config, "allow_mutations", False):
            raise MutationsDisabled(type(self).__name__)
        await super().emit(client)
