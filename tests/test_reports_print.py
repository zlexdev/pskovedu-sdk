"""Tests for methods/reports_print.py — GetReportXls, GetReportHtml, ReportFormatError guard."""

from __future__ import annotations

import pytest

from pskovedu.exceptions import ReportFormatError
from pskovedu.methods.reports_print import GetReportHtml, GetReportXls, _ReportHtml
from pskovedu.models.enums import REPORT_FORM_META, ReportBase, ReportForm

from .conftest import bytes_response, html_response


def _expected_url(form: ReportForm) -> str:
    """Build the expected URL path for a given form."""
    base, _ = REPORT_FORM_META[form]
    return f"{base.value}/{form.value}"


def test_report_form_has_13_members() -> None:
    assert len(ReportForm) == 13


@pytest.mark.asyncio
async def test_get_report_xls_returns_bytes(fake_client, fake_session) -> None:
    xls_data = b"PK\x03\x04fakeexcel"
    fake_session.enqueue(bytes_response(xls_data))

    result = await fake_client(GetReportXls(form=ReportForm.FORM1))

    assert isinstance(result, bytes)
    assert result == xls_data


@pytest.mark.asyncio
async def test_get_report_xls_url_contains_monitor_for_form1(fake_client, fake_session) -> None:
    fake_session.enqueue(bytes_response(b"data"))

    await fake_client(GetReportXls(form=ReportForm.FORM1))

    req = fake_session.sent_requests[-1]
    assert "/monitor/reportForm1" in req.url


@pytest.mark.asyncio
async def test_get_report_xls_adds_format_xls_param(fake_client, fake_session) -> None:
    fake_session.enqueue(bytes_response(b"data"))

    await fake_client(GetReportXls(form=ReportForm.FORM1))

    req = fake_session.sent_requests[-1]
    assert req.params.get("format") == "xls"


@pytest.mark.asyncio
async def test_get_report_xls_url_contains_report_for_child_marks(fake_client, fake_session) -> None:
    fake_session.enqueue(bytes_response(b"data"))

    await fake_client(GetReportXls(form=ReportForm.CHILD_MARKS))

    req = fake_session.sent_requests[-1]
    assert "/report/reportChildMarks" in req.url


@pytest.mark.asyncio
async def test_get_report_xls_extra_params_forwarded(fake_client, fake_session) -> None:
    fake_session.enqueue(bytes_response(b"data"))

    await fake_client(GetReportXls(form=ReportForm.FORM2, params={"date": "2024-01-01"}))

    req = fake_session.sent_requests[-1]
    assert req.params.get("date") == "2024-01-01"


@pytest.mark.asyncio
async def test_get_report_html_returns_report_html(fake_client, fake_session) -> None:
    html = "<html><body>Report content</body></html>"
    fake_session.enqueue(html_response(html))

    result = await fake_client(GetReportHtml(form=ReportForm.FORM1))

    assert isinstance(result, _ReportHtml)
    assert result.raw_html == html


@pytest.mark.asyncio
async def test_get_report_html_url_monitor(fake_client, fake_session) -> None:
    fake_session.enqueue(html_response("<html/>"))

    await fake_client(GetReportHtml(form=ReportForm.MONITORING_SCHOOL))

    req = fake_session.sent_requests[-1]
    assert "/monitor/reportmonitoringschool" in req.url


@pytest.mark.asyncio
async def test_get_report_html_url_report_base(fake_client, fake_session) -> None:
    fake_session.enqueue(html_response("<html/>"))

    await fake_client(GetReportHtml(form=ReportForm.TEACHERS_LIST))

    req = fake_session.sent_requests[-1]
    assert "/report/reportTeachersList" in req.url


def test_report_format_error_is_value_error() -> None:
    """ReportFormatError must be a ValueError subclass."""
    assert issubclass(ReportFormatError, ValueError)


def test_get_report_xls_raises_when_form_not_in_meta() -> None:
    """All 13 forms in REPORT_FORM_META have supports_xls=True currently.
    Verify that constructing GetReportXls for a form that maps to supports_xls=False
    raises ReportFormatError. We monkey-patch the meta to simulate a False entry.
    """
    from pskovedu.models import enums as enums_module

    # Save original
    original = enums_module.REPORT_FORM_META[ReportForm.FORM1]
    # Patch to supports_xls=False
    enums_module.REPORT_FORM_META[ReportForm.FORM1] = (ReportBase.MONITOR, False)
    try:
        with pytest.raises(ReportFormatError) as exc_info:
            GetReportXls(form=ReportForm.FORM1)
        assert exc_info.value.form == ReportForm.FORM1
    finally:
        enums_module.REPORT_FORM_META[ReportForm.FORM1] = original


@pytest.mark.parametrize("form", list(ReportForm))
@pytest.mark.asyncio
async def test_every_report_form_html_builds_url(form: ReportForm, fake_client, fake_session) -> None:
    fake_session.enqueue(html_response("<html/>"))
    await fake_client(GetReportHtml(form=form))

    req = fake_session.sent_requests[-1]
    expected_path = _expected_url(form)
    assert expected_path in req.url


@pytest.mark.parametrize("form", list(ReportForm))
@pytest.mark.asyncio
async def test_every_report_form_xls_builds_url(form: ReportForm, fake_client, fake_session) -> None:
    base, supports_xls = REPORT_FORM_META[form]
    if not supports_xls:
        with pytest.raises(ReportFormatError):
            GetReportXls(form=form)
        return

    fake_session.enqueue(bytes_response(b"data"))
    await fake_client(GetReportXls(form=form))

    req = fake_session.sent_requests[-1]
    expected_path = _expected_url(form)
    assert expected_path in req.url
    assert req.params.get("format") == "xls"
