"""ExtDirectProtocol — Ext.Direct RPC wire protocol.

Encodes method-classes into the ``{action, method, data, type:"rpc", tid}``
envelope sent to ``POST /extjs/direct``.  Decodes ``{type:"rpc", result}``
success envelopes and raises :exc:`~pskovedu.exceptions.ExtDirectError` on
``{type:"exception"}`` responses.

Transaction IDs (``tid``) are monotonically increasing per-client counters.
The counter lives on the bound client and is incremented here via
``client._next_tid()``.  Unbound calls default to ``tid=0`` (rare in practice).

Idempotency: methods whose ``__rpc_method__`` begins with ``"get"`` or ``"read"``
are considered idempotent and safe to retry.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from ..exceptions import ExtDirectError, MethodDeclarationError, ProtocolError
from .base import PreparedRequest, Protocol, RawResponse

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..methods._base import BaseMethod

# Ext.Direct method name prefixes that indicate safe-to-retry read operations
_READ_PREFIXES: tuple[str, ...] = ("get", "read", "show", "list", "fetch", "load")


class ExtDirectProtocol(Protocol):
    """Wire protocol for ``POST /extjs/direct`` (Ext.Direct RPC).

    Encodes fields declared via ``__action__``, ``__rpc_method__``, and
    ```` into the standard Ext.Direct envelope::

        {
            "action": "Reports",
            "method": "getGrades",
            "data": [arg0, arg1, ...],
            "type": "rpc",
            "tid": <monotonic int>
        }

    The ``data`` array is built by iterating ```` and extracting
    the corresponding field values from the method instance (positional mapping).
    Fields NOT listed in ```` are ignored — Ext.Direct methods pass
    all context as positional args, not keyword args.

    Response decoding:

    - ``{"type": "rpc", "result": ...}`` → validate into ``__returning__``.
    - ``{"type": "exception", "message": ..., ...}`` → raise
      :exc:`~pskovedu.exceptions.ExtDirectError`.
    - Any other shape → raise :exc:`~pskovedu.exceptions.ProtocolError`.
    """

    @classmethod
    def validate_subclass(cls, method_cls: type[BaseMethod]) -> None:  # type: ignore[type-arg]
        """Ensure ``__action__`` and ``__rpc_method__`` are declared.

        Skips abstract bases that leave these as ``None``.

        Args:
            method_cls: the concrete ``ExtDirectMethod`` subclass.

        Raises:
            MethodDeclarationError: when required class-vars are missing.
        """
        action = getattr(method_cls, "__action__", None)
        rpc_method = getattr(method_cls, "__rpc_method__", None)

        # Abstract bases may leave both as None — skip
        if action is None and rpc_method is None:
            return

        if action is not None and not isinstance(action, str):
            raise MethodDeclarationError(
                f"{method_cls.__name__}: __action__ must be a str, got {type(action).__name__}."
            )
        if rpc_method is not None and not isinstance(rpc_method, str):
            raise MethodDeclarationError(
                f"{method_cls.__name__}: __rpc_method__ must be a str, "
                f"got {type(rpc_method).__name__}."
            )

    def build_request(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        config: ClientConfig,
        host: str,
    ) -> PreparedRequest:
        """Build an Ext.Direct ``POST /extjs/direct`` request.

        Constructs the envelope ``{action, method, data, type, tid}``  where
        ``data`` is a positional array built from ````.

        Args:
            method: bound ``ExtDirectMethod`` instance.
            config: active client configuration.
            host: base URL for the portal host.

        Raises:
            ProtocolError: when ``__action__`` or ``__rpc_method__`` is missing.
        """
        action: str | None = getattr(method, "__action__", None)
        rpc_method: str | None = getattr(method, "__rpc_method__", None)
        arg_order: tuple[str, ...] = getattr(method, "__arg_order__", ())

        if not action or not rpc_method:
            raise ProtocolError(f"{type(method).__name__} is missing __action__ or __rpc_method__.")

        all_fields: dict[str, Any] = method.model_dump(by_alias=False, exclude_none=False)
        data_args: list[Any] = [all_fields.get(name) for name in arg_order]

        # Obtain tid from client counter; fall back to 0 for unbound calls
        client = getattr(method, "_client", None)
        tid: int = client._next_tid() if client is not None and hasattr(client, "_next_tid") else 0

        envelope: dict[str, Any] = {
            "action": action,
            "method": rpc_method,
            "data": data_args,
            "type": "rpc",
            "tid": tid,
        }

        from ..constants import PATH_EXT_DIRECT

        full_url = host.rstrip("/") + PATH_EXT_DIRECT

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
    ) -> Any:
        """Decode the Ext.Direct response envelope.

        Handles success (``type="rpc"``) and exception (``type="exception"``)
        envelopes.  Validates the decoded result into ``method.__returning__``.

        Args:
            method: the method instance (provides ``__returning__``, ``__action__``,
                ``__rpc_method__``, and the ``tid`` echoed for error context).
            raw: raw HTTP response from the transport layer.

        Raises:
            ExtDirectError: when the server returns ``type="exception"``.
            ProtocolError: on unexpected envelope shape or JSON parse failure.
        """
        data = raw.json_body
        if data is None:
            if raw.text:
                try:
                    data = json.loads(raw.text)
                except json.JSONDecodeError as exc:
                    raise ProtocolError(
                        f"Ext.Direct: failed to parse JSON from {raw.status} response: {exc}"
                    ) from exc
            else:
                raise ProtocolError(f"Ext.Direct: empty response body (HTTP {raw.status}).")

        resp_type = data.get("type") if isinstance(data, dict) else None

        if resp_type == "exception":
            action = data.get("action", getattr(method, "__action__", "?"))
            rpc_method = data.get("method", getattr(method, "__rpc_method__", "?"))
            tid = data.get("tid", 0)
            msg = data.get("message") or data.get("msg") or str(data)
            raise ExtDirectError(action=action, method=rpc_method, tid=tid, server_msg=msg)

        if resp_type != "rpc":
            raise ProtocolError(
                f"Ext.Direct: unexpected envelope type {resp_type!r}; "
                f"expected 'rpc'. Full body: {str(data)[:300]}"
            )

        returning: type[BaseModel] | None = getattr(method, "__returning__", None)
        if returning is None:
            return None

        result = data.get("result")
        # result may be a list (most Ext.Direct calls return list of records)
        # or a single object — __returning__ defines the shape
        try:
            return returning.model_validate(result)
        except Exception as exc:
            raise ProtocolError(
                f"Ext.Direct: failed to validate result into {returning.__name__}: {exc}"
            ) from exc

    def is_idempotent(self, method: BaseMethod) -> bool:  # type: ignore[type-arg]
        """Return ``True`` for read-only Ext.Direct methods.

        A method is considered idempotent when its ``__rpc_method__`` starts
        with one of ``get``, ``read``, ``show``, ``list``, ``fetch``, ``load``.

        Args:
            method: the method instance.
        """
        rpc_method: str | None = getattr(method, "__rpc_method__", None)
        if not rpc_method:
            return False
        lower = rpc_method.lower()
        return any(lower.startswith(prefix) for prefix in _READ_PREFIXES)
