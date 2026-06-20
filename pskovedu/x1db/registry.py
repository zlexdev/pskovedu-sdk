"""X1ModelRegistry — build and query the NAME↔SYS_GUID map from ``X1_CONFIG``.

The X1 ORM uses opaque ``SYS_GUID`` strings as model identifiers in API calls.
These GUIDs are installation-specific and change between deployments.  The portal
shell page exposes the full mapping via ``window.X1_CONFIG.meta.models``.

:class:`X1ModelRegistry` is built from the parsed ``models`` list of a
:class:`~pskovedu.models.session.ShellConfig` and provides O(1) lookup in
both directions.

Usage::

    from pskovedu.x1db.registry import X1ModelRegistry
    from pskovedu.x1db.constants import X1Model

    shell = parse_shell(html)
    reg = X1ModelRegistry.from_shell(shell)

    guid = reg.guid(X1Model.JOURNAL)   # "9DB33AD685B04DF8A6A73F32FFE78F08"
    name = reg.name(guid)              # "JOURNAL"
    all_models = reg.all()             # [("JOURNAL", "9DB33…"), ...]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging import get_logger

if TYPE_CHECKING:
    from ..models.session import ShellConfig, X1ModelRef

log = get_logger(__name__)


class X1ModelRegistry:
    """Runtime NAME↔SYS_GUID registry built from ``X1_CONFIG.meta.models``.

    Populated once from the parsed shell config; all lookups are O(1) dict
    accesses.  Names are stored as-is (typically uppercase ASCII).

    Args:
        models: iterable of :class:`~pskovedu.models.session.X1ModelRef` entries
            from ``ShellConfig.models``.
    """

    def __init__(self, models: list[X1ModelRef]) -> None:
        self._by_name: dict[str, str] = {}  # NAME → SYS_GUID
        self._by_guid: dict[str, str] = {}  # SYS_GUID → NAME
        duplicate_names: list[str] = []

        for ref in models:
            n = ref.name
            g = ref.sys_guid
            if n in self._by_name:
                duplicate_names.append(n)
            self._by_name[n] = g
            self._by_guid[g] = n

        if duplicate_names:
            log.warning("x1db.registry.duplicate_names", names=duplicate_names)

        log.debug("x1db.registry.built", model_count=len(self._by_name))

    @classmethod
    def from_shell(cls, shell: ShellConfig) -> X1ModelRegistry:
        """Build a registry from a parsed :class:`~pskovedu.models.session.ShellConfig`.

        Args:
            shell: parsed shell config containing ``models`` list.
        """
        return cls(shell.models)

    def guid(self, name: str) -> str | None:
        """Return the ``SYS_GUID`` for a given model ``NAME``.

        Args:
            name: model name (e.g. ``"JOURNAL"`` or ``X1Model.JOURNAL``).
        """
        return self._by_name.get(name)

    def name(self, sys_guid: str) -> str | None:
        """Return the model ``NAME`` for a given ``SYS_GUID``.

        Args:
            sys_guid: opaque system GUID (case-sensitive, as stored in config).
        """
        return self._by_guid.get(sys_guid)

    def all(self) -> list[tuple[str, str]]:
        """Return all ``(NAME, SYS_GUID)`` pairs in insertion order."""
        return list(self._by_name.items())

    def __len__(self) -> int:
        """Number of registered models."""
        return len(self._by_name)

    def __contains__(self, name: object) -> bool:
        """``True`` when *name* is a registered model NAME."""
        return name in self._by_name

    def __repr__(self) -> str:
        return f"X1ModelRegistry({len(self._by_name)} models)"
