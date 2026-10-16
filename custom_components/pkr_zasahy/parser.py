"""Parser stránky Zásahy JPO z Portálu krizového řízení Středočeského kraje.

Modul nezávisí na Home Assistantu, takže jde testovat samostatně.
"""

from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

# Re-export for existing parser consumers and standalone parser tests.
try:
    from .models import ParseError, Zasah, rozdil
except ImportError:  # Standalone import without Home Assistant.
    from models import ParseError, Zasah, rozdil  # noqa: F401

TZ = ZoneInfo("Europe/Prague")

# Genitiv (jak ho stránka používá) i nominativ pro jistotu
MONTHS = {
    "ledna": 1,
    "února": 2,
    "března": 3,
    "dubna": 4,
    "května": 5,
    "června": 6,
    "července": 7,
    "srpna": 8,
    "září": 9,
    "října": 10,
    "listopadu": 11,
    "prosince": 12,
    "leden": 1,
    "únor": 2,
    "březen": 3,
    "duben": 4,
    "květen": 5,
    "červen": 6,
    "červenec": 7,
    "srpen": 8,
    "říjen": 10,
    "listopad": 11,
    "prosinec": 12,
}

DATE_RE = re.compile(r"(\d{1,2})\.\s*([^\s\d,]+)\s+(\d{4}),?\s*(\d{1,2}):(\d{2})")
OKRES_RE = re.compile(
    r'<li class="selected">\s*<a[^>]*title="(okres [^"]+)"', re.IGNORECASE
)


class _TableParser(HTMLParser):
    """Vytáhne buňky řádků z <table id="result_list"><tbody>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found_table = False
        self.rows: list[list[dict]] = []
        self._in_table = False
        self._in_tbody = False
        self._row: list[dict] | None = None
        self._cell: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "table" and a.get("id") == "result_list":
            self._in_table = True
            self.found_table = True
        elif not self._in_table:
            return
        elif tag == "tbody":
            self._in_tbody = True
        elif self._in_tbody and tag == "tr":
            self._row = []
        elif self._row is not None and tag in ("th", "td"):
            self._cell = {"text": [], "title": None}
        elif self._cell is not None:
            if tag == "br":
                self._cell["text"].append("\n")
            elif tag == "span" and a.get("title") and not self._cell["title"]:
                self._cell["title"] = a["title"]

    def handle_endtag(self, tag: str) -> None:
        if not self._in_table:
            return
        if tag == "table":
            self._in_table = False
        elif tag == "tbody":
            self._in_tbody = False
        elif tag in ("th", "td") and self._cell is not None and self._row is not None:
            self._row.append(
                {
                    "text": "".join(self._cell["text"]).strip(),
                    "title": self._cell["title"],
                }
            )
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell["text"].append(data)


def parse_datum(text: str) -> datetime:
    """'9. října 2026, 17:05' -> aware datetime v Europe/Prague."""
    m = DATE_RE.search(text)
    if not m:
        raise ParseError(f"Neznámý formát data: {text!r}")
    day, month_name, year, hour, minute = m.groups()
    month = MONTHS.get(month_name.lower())
    if month is None:
        raise ParseError(f"Neznámý měsíc: {month_name!r}")
    return datetime(int(year), month, int(day), int(hour), int(minute), tzinfo=TZ)


def _rozdel_nazev(nazev: str) -> tuple[str, str]:
    """'požár - lesní porost - Lubná' -> ('požár', 'lesní porost')."""
    parts = [p.strip() for p in nazev.split(" - ")]
    if len(parts) >= 3:
        return parts[0], " - ".join(parts[1:-1])
    return parts[0], ""


def parse_zasahy(html: str) -> list[Zasah]:
    """Vrátí seznam zásahů seřazený od nejnovějšího."""
    p = _TableParser()
    p.feed(html)
    p.close()
    if not p.found_table:
        raise ParseError("Tabulka result_list na stránce není")

    zasahy: list[Zasah] = []
    for cells in p.rows:
        if len(cells) < 6:
            continue
        nazev = " ".join(cells[0]["text"].split())
        kategorie, podtyp = _rozdel_nazev(nazev)
        misto = [line.strip() for line in cells[3]["text"].split("\n") if line.strip()]
        obec = misto[0] if misto else ""
        okres = next(
            (
                line.removeprefix("okres ").strip()
                for line in misto[1:]
                if line.startswith("okres ")
            ),
            None,
        )
        zasahy.append(
            Zasah(
                nazev=nazev,
                kategorie=kategorie,
                podtyp=podtyp,
                typ=cells[1]["title"] or kategorie,
                stav=" ".join(cells[2]["text"].split()),
                obec=obec,
                okres=okres,
                stupen=cells[4]["text"],
                cas=parse_datum(cells[5]["text"]),
            )
        )
    zasahy.sort(key=lambda z: z.cas, reverse=True)
    return zasahy


def parse_okres(html: str) -> str | None:
    """Název vybraného okresu z filtru, např. 'okres Rakovník'."""
    m = OKRES_RE.search(html)
    return m.group(1) if m else None
