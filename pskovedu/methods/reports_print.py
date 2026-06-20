"""Print/monitor report method-classes for the pskovedu SDK.

Two concrete request classes share a common ``_ReportBase``:

- :class:`GetReportXls` — downloads the raw Excel bytes (``RestMethod[bytes]``).
- :class:`GetReportHtml` — fetches the HTML render (``RestMethod[_ReportHtml]``).

URL is resolved from :data:`~pskovedu.models.enums.REPORT_FORM_META`:
``{base}/{tail}`` where ``base`` is ``/monitor`` or ``/report`` and ``tail``
is the form's wire value (e.g. ``reportForm1``).

Report-specific query parameters (date ranges, grade GUIDs, etc.) are passed
via the ``params`` dict and are forwarded verbatim as query-string key/value
pairs.

Guard: constructing :class:`GetReportXls` for a form whose meta entry has
``supports_xls=False`` raises :exc:`~pskovedu.exceptions.ReportFormatError`
immediately — before any network call is made.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import model_serializer, model_validator

from ..exceptions import ReportFormatError
from ..models._base import HtmlParsed
from ..models.enums import REPORT_FORM_META, ReportForm
from ._bases import RestMethod


class _ReportHtml(HtmlParsed):
    """Raw HTML report DTO.

    ``RestProtocol.decode_response`` detects the :class:`~pskovedu.models._base.HtmlParsed`
    base and passes the raw response text in ``raw_html``; no JSON parsing occurs.
    """


class _ReportBase(RestMethod[Any]):
    """Shared base for print/monitor report requests.

    Resolves ``{base}/{tail}`` from :data:`~pskovedu.models.enums.REPORT_FORM_META`
    and routes ``params`` as flat query-string pairs via a custom serializer.

    Class-vars:
        __http_method__: always ``"GET"``.
        __url__: ``"{base}/{tail}"`` — placeholders filled from ``base``/``tail`` fields.
        __path_fields__: ``{"base", "tail"}`` — consumed by ``RestProtocol.build_request``.

    Instance fields:
        form: which report form to request.
        params: report-specific query parameters (dates, GUIDs, …).
        base: URL base segment — derived from ``form`` via ``REPORT_FORM_META``.
        tail: URL tail segment — the wire value of ``form``.
    """

    __http_method__ = "GET"
    __url__ = "{base}/{tail}"
    __path_fields__: ClassVar[frozenset[str]] = frozenset({"base", "tail"})

    form: ReportForm
    params: dict[str, str] = {}

    # Derived path segments — populated by the model validator below.
    # They MUST be Pydantic fields so model_dump() includes them for the protocol.
    base: str = ""
    tail: str = ""

    @model_validator(mode="after")
    def _resolve_url_segments(self) -> _ReportBase:
        """Fill ``base`` and ``tail`` from ``REPORT_FORM_META[form]``."""
        meta_base, _ = REPORT_FORM_META[self.form]
        self.base = meta_base.value
        self.tail = self.form.value
        return self

    @model_serializer(mode="wrap")
    def _flat_dump(self, handler: Any) -> dict[str, Any]:
        """Produce a flat dict for the REST protocol.

        - ``form`` is structural-only; excluded so it does not appear in the
          query string.
        - ``params`` is expanded inline so each entry becomes its own
          query-string key (``{"date": "2024-01-01"}`` → ``?date=2024-01-01``).
        - ``base`` and ``tail`` remain for path-field resolution.
        """
        raw: dict[str, Any] = handler(self)
        raw.pop("form", None)
        extra: dict[str, str] = raw.pop("params", {}) or {}
        raw.update(extra)
        return raw


class GetReportXls(_ReportBase, RestMethod[bytes]):
    """Download a report as a raw Excel file.

    Adds ``?format=xls`` to the query string and returns the response body as
    raw :class:`bytes` via the A1pre bytes passthrough path.

    Guard: raises :exc:`~pskovedu.exceptions.ReportFormatError` at construction
    time if ``REPORT_FORM_META[form].supports_xls`` is ``False``.

    Args:
        form: report form to fetch.
        params: additional query parameters (dates, GUIDs, …).

    Raises:
        ReportFormatError: if the selected form does not support XLS export.
    """

    def __init__(self, **data: Any) -> None:
        # Guard fires BEFORE Pydantic validation so it surfaces as
        # ReportFormatError directly — not wrapped in ValidationError.
        form = data.get("form")
        if form is not None and form in REPORT_FORM_META:
            _, supports_xls = REPORT_FORM_META[form]
            if not supports_xls:
                raise ReportFormatError(form)
        super().__init__(**data)

    @model_serializer(mode="wrap")
    def _flat_dump_xls(self, handler: Any) -> dict[str, Any]:
        """Extend the base flat serializer to inject ``format=xls``.

        Chains through ``_ReportBase._flat_dump`` so that structural fields
        are excluded and ``params`` is expanded before ``format`` is added.
        """
        raw: dict[str, Any] = _ReportBase._flat_dump(self, handler)
        raw["format"] = "xls"
        return raw


class GetReportHtml(_ReportBase, RestMethod[_ReportHtml]):
    """Fetch a report rendered as HTML.

    Returns a :class:`_ReportHtml` instance whose ``raw_html`` field holds the
    full response text.

    Args:
        form: report form to fetch.
        params: additional query parameters (dates, GUIDs, …).
    """
