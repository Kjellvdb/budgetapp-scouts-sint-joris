"""Gedeelde constanten, parsers en datamodellen (geen tkinter, geen Excel)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

SHEET_MEMBERS = "Ledenlijst"
SHEET_EXPENSES = "Uitgaven"
SHEET_VISITORS = "Fourage & Bezoekerslijst"
SHEET_BUDGET = "Overzicht"

CATEGORIES = ["Algemeen", "Alcohol", "Sterke Drank", "Persoonlijk"]
AI_CATEGORIES = CATEGORIES[:3]  # 'Persoonlijk' kiest de gebruiker zelf

MEMBER_HEADERS = ["Voornaam", "Achternaam", "Takken", "Kostprijs weekend/kamp", "Weekend/kamp betaald?",
                  "Alcohol gedronken?", "Sterke drank gedronken?"]
VISITOR_HEADERS = ["Voornaam", "Achternaam", "Kostprijs weekend/kamp", "Weekend/kamp betaald?",
                   "Alcohol gedronken?", "Sterke drank gedronken?"]
EXPENSE_HEADERS = ["Datum", "Item", "Aantal", "Totale prijs", "Categorie", "Naam", "Betaald?"]

DATE_FORMAT = "%d/%m/%Y"
_DATE_PARSE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y",
    "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
)

# Kolomkop -> veld (eerste match wint)
_FIELD_KEYWORDS = (
    ("datum", ("datum",)),
    ("item", ("item",)),
    ("aantal", ("aantal",)),
    ("prijs", ("prijs", "totaal")),
    ("categorie", ("categorie",)),
    ("naam", ("naam",)),
    ("betaald", ("betaald",)),
)


def field_for_header(header: Any) -> Optional[str]:
    h = str(header).strip().lower() if header is not None else ""
    for field, keywords in _FIELD_KEYWORDS:
        if any(k in h for k in keywords):
            return field
    return None


def parse_date(value: Any) -> Optional[datetime]:
    """Zet tekst/datum om naar een datetime zonder tijdsdeel; None als het niet lukt."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    if not text:
        return None
    for fmt in _DATE_PARSE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            continue
    return None


def parse_price(value: Any) -> Optional[float]:
    """Leest '€2.50', '2,50', '1.234,50', '1,234.50' of een getal; None als het niet lukt."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace("€", "").replace(" ", "").replace(" ", "").strip()
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def format_money(value: float) -> str:
    """1234.5 -> '€ 1.234,50' (Belgische notatie)."""
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {text}"


def format_quantity(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


@dataclass
class Expense:
    datum: Optional[datetime]
    item: str
    aantal: str = "1"
    prijs: float = 0.0
    categorie: str = "Algemeen"
    naam: str = ""
    row: Optional[int] = None      # Excel-rijnummer (None = nog niet opgeslagen)
    datum_text: str = ""           # ruwe tekst als de datum niet te lezen was
    betaald: bool = False          # enkel relevant voor Persoonlijk + naam

    @property
    def datum_display(self) -> str:
        return self.datum.strftime(DATE_FORMAT) if self.datum else self.datum_text

    @property
    def counts_in_total(self) -> bool:
        """
        Persoonlijke uitgaven tellen WEL mee in de totale groepsuitgaven zolang ze NIET betaald zijn.
        Zodra ze op betaald (Ja) staan, hoeft de groep dit niet meer te dragen en gaan ze van het totaal af.
        """
        if self.categorie.strip().lower() == "persoonlijk":
            return not self.betaald
        return True

    @property
    def is_personal(self) -> bool:
        """Persoonlijk item met een naam: hiervan wordt bijgehouden of het al betaald is."""
        return self.categorie.strip().lower() == "persoonlijk" and bool(self.naam.strip())


EXPENSE_COLUMNS = list(EXPENSE_HEADERS)


def expense_row_values(e: Expense) -> list[str]:
    """Waarden zoals ze in een tabel getoond worden (zelfde volgorde als EXPENSE_COLUMNS)."""
    paid = ("✔ Ja" if e.betaald else "❌ Nee") if e.is_personal else ""
    return [e.datum_display, e.item, e.aantal, format_money(e.prijs), e.categorie, e.naam, paid]
