"""X1Protocol — X1 ORM wire protocol (experimental).

Resolves the ``__x1_model__`` NAME to a ``SYS_GUID`` at request time via
:class:`~pskovedu.x1db.registry.X1ModelRegistry`, then POSTs to
``/x1db/service/call`` with the X1 ORM envelope.

.. warning::
    X1 ORM is an internal/undocumented API.  Field shapes and error envelopes
    were reverse-engineered from HAR captures and may change without notice.
    Use the ``experimental`` docstring marker as a signal that this protocol
    may require updates after portal upgrades.

**Experimental** — not covered by the SDK's stability guarantee.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..exceptions import MethodDeclarationError, ProtocolError, X1Error
from .base import PreparedRequest, Protocol, RawResponse

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..methods._base import BaseMethod


class X1Record(dict):  # type: ignore[type-arg]
    """A single raw X1 ORM record (key-value dict with SYS_* prefix fields).

    Thin subclass of ``dict`` so callers can detect X1 records vs plain dicts.
    Typical keys: ``SYS_GUID``, ``SYS_STATE``, ``SYS_REV``, domain field names.

    **Experimental.**
    """


class X1Page:
    """A paginated page of X1 ORM records.

    Attributes:
        records: list of :class:`X1Record` instances.
        total: total record count server-side (``None`` when not provided).

    **Experimental.**
    """

    __slots__ = ("records", "total")

    def __init__(self, records: list[X1Record], total: int | None = None) -> None:
        self.records = records
        self.total = total

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Any:
        return iter(self.records)

    def __repr__(self) -> str:
        return f"X1Page(records={len(self.records)}, total={self.total!r})"


class X1Protocol(Protocol):
    """Wire protocol for ``POST /x1db/service/call`` (X1 ORM).

    The X1 ORM envelope wraps X1API Ext.Direct calls::

        POST /x1db/service/call
        {
            "action": "X1API",
            "method": "direct",
            "data": [{
                "service": "<x1_service>",
                "method":  "<x1_method>",
                "params":  { "model": "<SYS_GUID>", ...where/limit args... },
                "ctx":     {}
            }],
            "type": "rpc",
            "tid": <int>
        }

    The ``__x1_model__`` NAME is resolved to ``SYS_GUID`` via the client's
    :class:`~pskovedu.x1db.registry.X1ModelRegistry` at call time.

    Response decoding follows the same Ext.Direct envelope conventions:

    - ``{"type": "rpc", "result": [...records...]}`` → :class:`X1Page`.
    - ``{"type": "exception", ...}`` → :exc:`~pskovedu.exceptions.X1Error`.

    **Experimental** — not covered by the SDK's stability guarantee.
    """

    @classmethod
    def validate_subclass(cls, method_cls: type[BaseMethod]) -> None:  # type: ignore[type-arg]
        """Ensure ``__x1_service__`` and ``__x1_method__`` are declared.

        Args:
            method_cls: the ``X1Method`` subclass.

        Raises:
            MethodDeclarationError: when required class-vars are missing.
        """
        x1_service = getattr(method_cls, "__x1_service__", None)
        x1_method = getattr(method_cls, "__x1_method__", None)

        # Abstract bases leave these as None — skip
        if x1_service is None and x1_method is None:
            return

        for attr_name, value in (("__x1_service__", x1_service), ("__x1_method__", x1_method)):
            if value is not None and not isinstance(value, str):
                raise MethodDeclarationError(
                    f"{method_cls.__name__}: {attr_name} must be a str, got {type(value).__name__}."
                )

    def build_request(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        config: ClientConfig,
        host: str,
    ) -> PreparedRequest:
        """Build a ``POST /x1db/service/call`` request.

        Resolves ``__x1_model__`` NAME → ``SYS_GUID`` via the registry stored
        on the bound client.  Field values other than the model name become
        the ``params`` dict passed to the X1 service method.

        Args:
            method: bound ``X1Method`` instance.
            config: active client configuration.
            host: base URL for the portal host.

        Raises:
            ProtocolError: when ``__x1_service__`` or ``__x1_method__`` is missing,
                or when the model name cannot be resolved to a GUID.
        """
        x1_service: str | None = getattr(method, "__x1_service__", None)
        x1_method_name: str | None = getattr(method, "__x1_method__", None)
        x1_model_name: str | None = getattr(method, "__x1_model__", None)

        if not x1_service or not x1_method_name:
            raise ProtocolError(
                f"{type(method).__name__} is missing __x1_service__ or __x1_method__."
            )

        # Resolve model NAME → SYS_GUID via registry on the bound client
        model_guid: str | None = None
        if x1_model_name:
            client = getattr(method, "_client", None)
            registry = getattr(client, "registry", None) if client is not None else None
            if registry is not None:
                model_guid = registry.guid(x1_model_name)
            if model_guid is None:
                raise ProtocolError(
                    f"{type(method).__name__}: cannot resolve X1 model name "
                    f"{x1_model_name!r} to a SYS_GUID — registry returned None. "
                    "Ensure bootstrap() was called and the model exists in X1_CONFIG."
                )

        all_fields: dict[str, Any] = method.model_dump(by_alias=False, exclude_none=True)
        params: dict[str, Any] = dict(all_fields)
        if model_guid is not None:
            params["model"] = model_guid

        client = getattr(method, "_client", None)
        tid: int = client._next_tid() if client is not None and hasattr(client, "_next_tid") else 0

        envelope: dict[str, Any] = {
            "action": "X1API",
            "method": "direct",
            "data": [
                {
                    "service": x1_service,
                    "method": x1_method_name,
                    "params": params,
                    "ctx": {},
                }
            ],
            "type": "rpc",
            "tid": tid,
        }

        from ..constants import PATH_X1_CALL

        full_url = host.rstrip("/") + PATH_X1_CALL

        headers: dict[str, str] = {
            "User-Agent": config.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        return PreparedRequest(
            method="POST",
            url=full_url,
            headers=headers,
            params={},
            body=envelope,
            timeout_s=config.request_timeout_s,
        )

    def decode_response(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        raw: RawResponse,
    ) -> X1Page:
        """Decode the X1 ORM response envelope into an :class:`X1Page`.

        Follows the same Ext.Direct envelope conventions:

        - ``{"type": "rpc", "result": [...]}`` → :class:`X1Page`.
        - ``{"type": "exception", ...}`` → :exc:`~pskovedu.exceptions.X1Error`.

        Args:
            method: the method instance (for error context).
            raw: raw HTTP response.

        Raises:
            X1Error: when the server returns an exception envelope.
            ProtocolError: on unexpected envelope shape or JSON parse failure.
        """
        x1_model_name: str = getattr(method, "__x1_model__", None) or "?"

        data = raw.json_body
        if data is None:
            if raw.text:
                try:
                    data = json.loads(raw.text)
                except json.JSONDecodeError as exc:
                    raise ProtocolError(
                        f"X1({x1_model_name}): failed to parse JSON: {exc}"
                    ) from exc
            else:
                raise ProtocolError(
                    f"X1({x1_model_name}): empty response body (HTTP {raw.status})."
                )

        if not isinstance(data, dict):
            raise ProtocolError(
                f"X1({x1_model_name}): expected JSON object, got {type(data).__name__}."
            )

        resp_type = data.get("type")

        if resp_type == "exception":
            msg = data.get("message") or data.get("msg") or str(data)
            raise X1Error(model=x1_model_name, server_msg=str(msg))

        if resp_type != "rpc":
            raise ProtocolError(
                f"X1({x1_model_name}): unexpected envelope type {resp_type!r}; "
                f"expected 'rpc'. Body: {str(data)[:300]}"
            )

        result = data.get("result")
        total: int | None = None

        if isinstance(result, dict):
            # Some X1 methods wrap in {data: [...], total: N}
            records_raw = result.get("data", result.get("records", []))
            total_raw = result.get("total")
            if isinstance(total_raw, int):
                total = total_raw
        elif isinstance(result, list):
            records_raw = result
        else:
            records_raw = []

        records = [X1Record(r) for r in (records_raw or []) if isinstance(r, dict)]
        return X1Page(records=records, total=total)

    def is_idempotent(self, method: BaseMethod) -> bool:  # type: ignore[type-arg]
        """Return ``True`` for X1 query/get operations.

        A method is considered idempotent when its ``__x1_method__`` is a
        read-only operation (``"query"``, ``"get"``, ``"list"``, ``"read"``).

        Args:
            method: the method instance.
        """
        x1_method: str | None = getattr(method, "__x1_method__", None)
        if not x1_method:
            return False
        lower = x1_method.lower()
        return lower in {"query", "get", "list", "read", "select", "find"}
