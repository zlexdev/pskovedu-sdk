"""Parse participant identity from the portal shell HTML.

The portal server-renders participant info into two HTML elements::

    <div id="participant"
         data-guid="B22275F0B52B8A7663899CA8BF970212"
         data-role="participant">
    </div>

    <div class="one-participant">
        Иванов Александр Романович,
        11У класс,
        МАОУ "Лицей экономики и основ предпринимательства №10"
    </div>

``#participant[data-guid]`` carries the GUID used as the primary key for diary
API calls; ``#participant[data-role]`` distinguishes participant / teacher /
admin roles; ``.one-participant`` contains the display string with FIO, grade,
and school separated by commas.

Usage::

    info = parse_participant(html)
    print(info.guid)      # "B22275F0B52B8A7663899CA8BF970212"
    print(info.full_name) # "Иванов Александр Романович"
    print(info.grade)     # "11У"
    print(info.school)    # 'МАОУ "Лицей экономики и основ предпринимательства №10"'
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from selectolax.parser import HTMLParser

from ..exceptions import HtmlParseError
from ..logging import get_logger

log = get_logger(__name__)

# Grade ends with "класс" (sometimes capitalised)
_GRADE_RE = re.compile(r"(\S+)\s+класс", re.IGNORECASE)


@dataclass(slots=True, frozen=True)
class ParticipantInfo:
    """Парсед participant identity from the portal shell HTML.

    Attributes:
        guid: hex GUID of the participant.
        role: role string from ``data-role`` (``"participant"``, ``"teacher"``, ``"admin"``).
        full_name: FIO from ``.one-participant`` (first comma-delimited segment).
        grade: grade label (e.g. ``"11У"``), or ``None`` for teachers/admins.
        school: school name (last comma-delimited segment), or ``None``.
        display_text: raw text content of ``.one-participant`` (stripped).
    """

    guid: str
    role: str
    full_name: str | None
    grade: str | None
    school: str | None
    display_text: str


def _parse_one_participant(text: str) -> tuple[str | None, str | None, str | None]:
    """Split ``.one-participant`` display string into (full_name, grade, school)."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    full_name: str | None = parts[0] if parts else None
    grade: str | None = None
    school: str | None = None

    for part in parts[1:]:
        gm = _GRADE_RE.search(part)
        if gm:
            grade = gm.group(1)
        else:
            school = part

    return full_name, grade, school


def parse_participant(html: str, url: str = "https://one.pskovedu.ru/") -> ParticipantInfo:
    """Parse participant identity elements from the portal shell HTML.

    Args:
        html: raw HTML text of ``GET /`` response.
        url: canonical URL of the page (used in error messages).

    Raises:
        HtmlParseError: when ``#participant`` with a ``data-guid`` attribute cannot be found.
    """
    tree = HTMLParser(html)

    div = tree.css_first("#participant")
    if not div:
        raise HtmlParseError("#participant div", url)

    guid = (div.attributes.get("data-guid") or "").upper()
    if not guid:
        raise HtmlParseError("#participant[data-guid]", url)

    role = div.attributes.get("data-role") or "participant"

    op = tree.css_first(".one-participant")
    display_text = ""
    full_name: str | None = None
    grade: str | None = None
    school: str | None = None

    if op:
        display_text = (op.text(deep=True, separator="") or "").strip()
        full_name, grade, school = _parse_one_participant(display_text)
    else:
        log.warning("participant.one_participant_missing", url=url)

    log.debug("participant.parsed", guid=guid, role=role, grade=grade)
    return ParticipantInfo(
        guid=guid,
        role=role,
        full_name=full_name,
        grade=grade,
        school=school,
        display_text=display_text,
    )
