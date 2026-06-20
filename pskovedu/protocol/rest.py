"""RestProtocol — default wire protocol for the pskovedu SDK.

Handles path-template resolution, query/body routing by HTTP verb,
JSON decode → model_validate, and HtmlParsed passthrough.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from ..exceptions import MethodDeclarationError, ProtocolError
from .base import PreparedRequest, Protocol, RawResponse

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..methods._base import BaseMethod

# HTTP verbs that carry no body — all fields route to query string by default
_BODYLESS_VERBS: frozenset[str] = frozenset({"GET", "HEAD", "DELETE", "OPTIONS"})

# HTTP verbs that are idempotent for retry purposes
_IDEMPOTENT_VERBS: frozenset[str] = frozenset({"GET", "HEAD"})


class RestProtocol(Protocol):
    """Default REST protocol: resolves path templates, routes fields by verb,
    decodes JSON responses into Pydantic models.

    Method-class class-vars used by this protocol:
    - ``__http_method__``: HTTP verb string (required).
    - ``__url__``: path template with optional ``{name}`` placeholders (required).
    - ``__path_fields__``: frozenset of field names that fill path placeholders.
    - ``__query_fields__``: optional frozenset override for query-string fields.
    - ``__body_fields__``: optional frozenset override for body fields.
    - ``__returning__``: Pydantic model class or ``None`` for fire-and-forget.
    """

    @classmethod
    def validate_subclass(cls, method_cls: type[BaseMethod]) -> None:  # type: ignore[type-arg]
        """Ensure the method-class declares ``__http_method__`` and ``__url__``.

        Called at import time by ``BaseMethod.__init_subclass__``.

        Raises:
            MethodDeclarationError: when required class-vars are missing.
        """
        # Only validate direct concrete subclasses that have fixed class-vars.
        # Abstract intermediate bases (RestMethod, etc.) may leave them as None.
        http_method = getattr(method_cls, "__http_method__", None)
        url = getattr(method_cls, "__url__", None)

        # Skip validation for abstract bases that leave these as None
        if http_method is None and url is None:
            return

        if http_method is not None and not isinstance(http_method, str):
            raise MethodDeclarationError(
                f"{method_cls.__name__}: __http_method__ must be a str, "
                f"got {type(http_method).__name__}."
            )
        if url is not None and not isinstance(url, str):
            raise MethodDeclarationError(
                f"{method_cls.__name__}: __url__ must be a str, got {type(url).__name__}."
            )

    def build_request(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        config: ClientConfig,
        host: str,
    ) -> PreparedRequest:
        """Build a ``PreparedRequest`` from a REST method instance.

        Path placeholders in ``__url__`` (e.g. ``{grade_guid}``) are filled
        from fields listed in ``__path_fields__``.  Remaining fields are routed
        to the query string (bodyless verbs) or JSON body.

        Args:
            method: REST method instance.
            config: active client configuration.
            host: base URL for the target host.

        Raises:
            ProtocolError: when ``__url__`` or ``__http_method__`` is missing.
        """
        http_verb: str | None = getattr(method, "__http_method__", None)
        url_template: str | None = getattr(method, "__url__", None)

        if not http_verb or not url_template:
            raise ProtocolError(f"{type(method).__name__} is missing __http_method__ or __url__.")

        http_verb = http_verb.upper()

        # Collect all field values from the method instance
        all_fields: dict[str, Any] = method.model_dump(by_alias=False, exclude_none=False)

        path_fields: frozenset[str] = getattr(method, "__path_fields__", frozenset())
        path_values: dict[str, str] = {}
        for name in path_fields:
            value = all_fields.get(name)
            if value is None:
                raise ProtocolError(
                    f"{type(method).__name__}: path field {name!r} is None; cannot build URL."
                )
            path_values[name] = str(value)

        resolved_path = url_template.format(**path_values)
        full_url = host.rstrip("/") + resolved_path

        non_path = {k: v for k, v in all_fields.items() if k not in path_fields}

        # Route non-path fields to query or body
        query_fields_override: frozenset[str] | None = getattr(method, "__query_fields__", None)
        body_fields_override: frozenset[str] | None = getattr(method, "__body_fields__", None)

        params: dict[str, str] = {}
        body: Any = None

        if http_verb in _BODYLESS_VERBS:
            if query_fields_override is not None:
                for k in query_fields_override:
                    if non_path.get(k) is not None:
                        params[k] = str(non_path[k])
            else:
                for k, v in non_path.items():
                    if v is not None:
                        params[k] = str(v)
        else:
            # Body verb: explicit overrides win; default → everything to body
            if body_fields_override is not None:
                body_dict = {
                    k: non_path[k]
                    for k in body_fields_override
                    if k in non_path and non_path[k] is not None
                }
                body = body_dict or None
            else:
                body_dict = {k: v for k, v in non_path.items() if v is not None}
                body = body_dict or None

            if query_fields_override is not None:
                for k in query_fields_override:
                    if non_path.get(k) is not None:
                        params[k] = str(non_path[k])
                        # Remove from body to avoid duplication
                        if isinstance(body, dict):
                            body.pop(k, None)

        returning = getattr(method, "__returning__", None)
        accept_header = "*/*" if returning is bytes else "application/json"
        headers: dict[str, str] = {
            "User-Agent": config.user_agent,
            "Accept": accept_header,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        return PreparedRequest(
            method=http_verb,
            url=full_url,
            headers=headers,
            params=params,
            body=body,
            timeout_s=config.request_timeout_s,
        )

    def decode_response(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        raw: RawResponse,
    ) -> Any:
        """Decode the raw HTTP response into the method's ``__returning__`` type.

        - If ``__returning__`` is a subclass of ``HtmlParsed``: return the raw
          text (caller's parser function will handle it).
        - If ``__returning__`` is ``None``: return ``None`` (fire-and-forget).
        - Otherwise: parse JSON body and call ``model_validate``.

        Args:
            method: the method instance.
            raw: raw HTTP response.

        Raises:
            ProtocolError: on JSON parse failure or model validation failure.
        """
        from ..models._base import HtmlParsed

        returning: type[BaseModel] | type[bytes] | type[str] | None = getattr(method, "__returning__", None)

        if returning is None:
            return None

        # Raw bytes passthrough (e.g. GetAvatar, GetDiaryXls)
        if returning is bytes:
            return raw.content

        # Raw text passthrough
        if returning is str:
            return raw.text

        # HtmlParsed marker → pass raw text through to parser
        if isinstance(returning, type) and issubclass(returning, HtmlParsed):
            return returning(raw_html=raw.text)

        data = raw.json_body
        if data is None:
            # Try to parse from text if json_body wasn't pre-parsed
            if raw.text:
                try:
                    data = json.loads(raw.text)
                except json.JSONDecodeError as exc:
                    raise ProtocolError(
                        f"Failed to parse JSON from {raw.status} response: {exc}"
                    ) from exc
            else:
                raise ProtocolError(
                    f"Empty response body from {raw.status} response; "
                    f"expected {returning.__name__}."
                )

        if not (isinstance(returning, type) and issubclass(returning, BaseModel)):
            raise ProtocolError(
                f"{type(method).__name__}: __returning__={returning!r} is not a BaseModel "
                "subclass; cannot decode JSON response."
            )

        try:
            return returning.model_validate(data)
        except Exception as exc:
            raise ProtocolError(
                f"Failed to validate response into {returning.__name__}: {exc}"
            ) from exc

    def is_idempotent(self, method: BaseMethod) -> bool:  # type: ignore[type-arg]
        """Return ``True`` for ``GET`` and ``HEAD`` requests; ``False`` otherwise."""
        http_verb: str | None = getattr(method, "__http_method__", None)
        if http_verb is None:
            return False
        return http_verb.upper() in _IDEMPOTENT_VERBS
