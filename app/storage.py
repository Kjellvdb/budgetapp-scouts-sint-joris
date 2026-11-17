from __future__ import annotations
from typing import Any
from datetime import date
from dataclasses import dataclass, field

import openpyxl
import csv
import io

from app import session_store
from app.session_store import get_workbook

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SHEET_MEMBERS   = "Ledenlijst"
SHEET_VISITORS  = "Fourage"
SHEET_EXPENSES  = "Uitgaven"
SHEET_SUMMARY   = "Overzicht"

MEMBER_HEADERS  = [
    "Naam", 
    "Tak", 
    "Kostprijs weekend/kamp", 
    "Weekend/kamp betaald?", 
    "Alcohol gedronken?", 
    "Sterke drank gedronken?"
]
VISITOR_HEADERS = [
    "Naam", 
    "Kostprijs weekend/kamp", "Weekend/kamp betaald?", 
    "Alcohol gedronken?", "Sterke drank gedronken?"
]
EXPENSE_HEADERS = [
    "Datum", "Item", "Aantal", "Totale prijs", "Categorie", "Persoon", "Betaald?"
]

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
@dataclass
class Summary:
    leden: float = 0.0
    leiding: float = 0.0
    fourage: float = 0.0
    algemeen: float = 0.0
    alcohol: float = 0.0
    sterke_drank: float = 0.0
    persoonlijk: float = 0.0
    uitgaven_per_categorie: dict[str, float] = field(default_factory=dict)
    inkomsten_per_categorie: dict[str, float] = field(default_factory=dict)

    @property
    def inkomsten(self) -> float:
        return self.leden + self.leiding + self.fourage

    @property
    def uitgaven(self) -> float:
        return self.algemeen + self.alcohol + self.sterke_drank + self.persoonlijk

    @property
    def omzet(self) -> float:
        return self.inkomsten - self.uitgaven

@dataclass
class Person:
    naam: str
    sheet: str
    kostprijs_basis: float
    alcohol_aandeel: float
    sterke_aandeel: float
    persoonlijk_aandeel: float
    basis_betaald: bool = False
    rest_betaald: bool = False

    @property
    def kostprijs_totaal(self) -> float:
        return self.kostprijs_basis + self.alcohol_aandeel + self.sterke_aandeel + self.persoonlijk_aandeel

    @property
    def nog_te_betalen(self) -> float:
        basis = 0.0 if self.basis_betaald else self.kostprijs_basis
        return basis + self.alcohol_aandeel + self.sterke_aandeel + self.persoonlijk_aandeel

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
def get_sheet(sheet_name: str):
    workbook = get_workbook()
    sheetnames = workbook.sheetnames
    if sheet_name not in sheetnames:
        raise KeyError(f"Blad '{sheet_name}' niet gevonden. Beschikbare bladen: {sheetnames}")
    return workbook[sheet_name]


def update_cell(sheet_name: str, row: int, col: int, value: Any) -> None:
    sheet = get_sheet(sheet_name)
    sheet.cell(row=row, column=col, value=value)
    session_store.save_current()

def append_row(sheet_name: str, values: list[Any]) -> int:
    sheet = get_sheet(sheet_name)
    sheet.append(values)
    session_store.save_current()
    return sheet.max_row


def create_new_budget(budget_name: str, csv_bytes: bytes) -> bytes:
    workbook = openpyxl.Workbook()
    default_sheet = workbook.active
    if default_sheet is not None:
        workbook.remove(default_sheet)
    sheet_members = workbook.create_sheet(title=SHEET_MEMBERS)
    sheet_members.append(MEMBER_HEADERS)
    decoded_content = csv_bytes.decode('utf-8-sig', errors='ignore')
    delimiter = ';' if ';' in decoded_content else ','
    reader = csv.DictReader(io.StringIO(decoded_content), delimiter=delimiter)
    for row in reader:
        row_lower = {str(key).strip().lower(): value for key, value in row.items() if key}
        voornaam = ""
        for key in ["voornaam", "first_name", "naam"]:
            if key in row_lower:
                voornaam = row_lower[key].strip()
                break
        achternaam = ""
        for key in ["achternaam", "last_name", "familienaam"]:
            if key in row_lower:
                achternaam = row_lower[key].strip()
                break
        takken = ""
        for key in ["takken", "tak", "groep", "section"]:
            if key in row_lower:
                takken = row_lower[key].strip()
                break
        if not voornaam and not achternaam and "naam" in row_lower:
            volledige_naam = row_lower["naam"].strip()
        else:
            volledige_naam = f"{voornaam} {achternaam}".strip()
        if not volledige_naam:
            continue
        sheet_members.append([
            volledige_naam,
            takken,
            "",
            "Nee",
            "Nee",
            "Nee"
        ])
    sheet_visitors = workbook.create_sheet(title=SHEET_VISITORS)
    sheet_visitors.append(VISITOR_HEADERS)
    sheet_expenses = workbook.create_sheet(title=SHEET_EXPENSES)
    sheet_expenses.append(EXPENSE_HEADERS)
    sheet_summary = workbook.create_sheet(title=SHEET_SUMMARY)
    sheet_summary.append(["Budget Naam", budget_name])
    buf = io.BytesIO()
    workbook.save(buf)
    buf.seek(0)
    return buf.read()


def get_members() -> list[dict]:
    sheet = get_sheet(SHEET_MEMBERS)
    rows = []
    for row in range(2, sheet.max_row + 1):
        naam = sheet.cell(row=row, column=1).value
        tak = sheet.cell(row=row, column=2).value
        kostprijs = sheet.cell(row=row, column=3).value
        betaald = sheet.cell(row=row, column=4).value
        alcohol = sheet.cell(row=row, column=5).value
        sterke = sheet.cell(row=row, column=6).value
        if not any([naam, tak, kostprijs, betaald, alcohol, sterke]):
            continue
        rows.append({
            "_excel_row": row,
            "Naam": naam or "",
            "Tak": tak or "",
            "Kostprijs": kostprijs if kostprijs is not None else 0.0,
            "Betaald?": betaald or "Nee",
            "Alcohol?": alcohol or "Nee",
            "Sterke?": sterke or "Nee"
        })
    return rows


def get_visitors():
    sheet = get_sheet(SHEET_VISITORS)
    rows = []
    for row in range(2, sheet.max_row + 1):
        naam = sheet.cell(row=row, column=1).value
        kostprijs = sheet.cell(row=row, column=2).value
        betaald = sheet.cell(row=row, column=3).value
        alcohol = sheet.cell(row=row, column=4).value
        sterke = sheet.cell(row=row, column=5).value
        if not any([naam, kostprijs, betaald, alcohol, sterke]):
            continue
        rows.append({
            "_excel_row": row,
            "Naam": naam or "",
            "Kostprijs": kostprijs if kostprijs is not None else 0.0,
            "Betaald?": betaald or "Nee",
            "Alcohol?": alcohol or "Nee",
            "Sterke?": sterke or "Nee"
        })
    return rows

def add_visitor(values: list):
    sheet = get_sheet(SHEET_VISITORS)
    sheet.append(values)
    session_store.save_current()

def update_visitor(excel_row: int, field: str, value):
    sheet = get_sheet(SHEET_VISITORS)
    if excel_row <= 1:
        return
    field_to_col = {
        "naam": 1,
        "kost": 2,
        "betaald": 3,
        "alcohol": 4,
        "sterke": 5
    }
    col_idx = field_to_col.get(field)
    if col_idx:
        sheet.cell(row=excel_row, column=col_idx, value=value)
        session_store.save_current()

def delete_visitors(excel_rows: list[int]):
    sheet = get_sheet(SHEET_VISITORS)
    for row in sorted(excel_rows, reverse=True):
        if row > 1:
            sheet.delete_rows(row)
    session_store.save_current()


def get_expenses() -> list[dict]:
    sheet = get_sheet(SHEET_EXPENSES)
    rows = []
    for row in range(2, sheet.max_row + 1):
        datum = sheet.cell(row=row, column=1).value
        item = sheet.cell(row=row, column=2).value
        aantal = sheet.cell(row=row, column=3).value
        prijs = sheet.cell(row=row, column=4).value
        categorie = sheet.cell(row=row, column=5).value
        persoon = sheet.cell(row=row, column=6).value
        betaald = sheet.cell(row=row, column=7).value
        if not any([datum, item, aantal, prijs, categorie]):
            continue
        categorie_str = str(categorie or "Algemeen").strip()
        is_persoonlijk = categorie_str == "Persoonlijk"
        datum_str = ""
        if datum:
            if hasattr(datum, "strftime"):
                datum_str = datum.strftime("%Y-%m-%d")
            else:
                raw_str = str(datum).strip()[:10]
                if "/" in raw_str:
                    parts = raw_str.split("/")
                    if len(parts) == 3:
                        datum_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
                    else:
                        datum_str = raw_str
                else:
                    datum_str = raw_str
        rows.append({
            "_excel_row": row,
            "Datum": datum_str,
            "Item": item or "",
            "Aantal": int(float(aantal)) if aantal is not None else 1,
            "Prijs": prijs if prijs is not None else 0.0,
            "Categorie": categorie_str,
            "Persoon": str(persoon or "") if is_persoonlijk else "",
            "Betaald?": str(betaald or "Nee") if is_persoonlijk else (str(betaald or "Nee") if betaald else "Nee")
        })
    rows.sort(key=lambda row: row["Datum"] if row["Datum"] else "9999-12-31")
    return rows

def add_expense(row_data: list[Any]) -> int:
    return append_row(SHEET_EXPENSES, row_data)

def add_expenses_bulk(rows: list[list[Any]]) -> None:
    if not rows:
        return
    sheet = get_sheet(SHEET_EXPENSES)
    for row_data in rows:
        sheet.append(row_data)
    session_store.save_current()

def update_expense(excel_row: int, field: str, value):
    sheet = get_sheet(SHEET_EXPENSES)
    if excel_row <= 1:
        return
    field_to_col = {
        "datum": 1,
        "item": 2,
        "aantal": 3,
        "prijs": 4,
        "categorie": 5,
        "persoon": 6,
        "betaald": 7
    }
    col_idx = field_to_col.get(field)
    if col_idx:
        if field == "datum" and isinstance(value, str) and value:
            try:
                if "/" in value:
                    parts = value.split("/")
                    if len(parts) == 3:
                        value = date(int(parts[2]), int(parts[1]), int(parts[0]))
                elif "-" in value:
                    parts = value.split("-")
                    if len(parts) == 3 and len(parts[0]) != 4:
                        value = date(int(parts[2]), int(parts[1]), int(parts[0]))
            except (ValueError, IndexError):
                pass
        elif field == "aantal":
            try:
                value = int(float(value))
            except (ValueError, TypeError):
                value = 1
        sheet.cell(row=excel_row, column=col_idx, value=value)
        session_store.save_current()

def delete_expenses(excel_rows: list[int]):
    sheet = get_sheet(SHEET_EXPENSES)
    for row in sorted(excel_rows, reverse=True):
        if row > 1:
            sheet.delete_rows(row)
    session_store.save_current()


def get_summary() -> tuple[Summary, list[Person]]:
    summary = Summary()
    expenses = get_expenses()
    unpaid_persons_by_name: dict[str, float] = {}
    for expense in expenses:
        categorie = str(expense.get("Categorie", "")).strip().lower()
        betaald = str(expense.get("Betaald?", "")).strip().lower()
        persoon = str(expense.get("Persoon", "")).strip()
        prijs = float(expense.get("Prijs") or 0.0)
        if categorie == "persoonlijk" and betaald != "ja" and persoon:
            name_key = persoon.lower()
            unpaid_persons_by_name[name_key] = unpaid_persons_by_name.get(name_key, 0.0) + prijs
    members = get_members()
    basis_betaald_by_name: dict[str, bool] = {}
    member_data = []
    for member in members:
        naam = str(member.get("Naam", "")).strip()
        if not naam:
            continue
        kost = float(member.get("Kostprijs") or 0.0)
        betaald_raw = str(member.get("Betaald?", "")).strip().lower()
        is_paid = betaald_raw in ("ja", "yes", "true", "1")
        basis_betaald_by_name[naam.lower()] = is_paid
        tak = str(member.get("Tak", "")).strip().lower()
        tak_parts = [part.strip() for part in tak.split(",")]
        is_leader = any("leiding" in part for part in tak_parts)
        personal_price = unpaid_persons_by_name.get(naam.lower(), 0.0)
        total_person_price = kost + personal_price
        if is_leader:
            summary.leiding += total_person_price
        else:
            summary.leden += total_person_price
        member_data.append({
            "naam": naam,
            "sheet": SHEET_MEMBERS,
            "kostprijs": kost,
            "betaald": is_paid,
            "is_leader": is_leader,
            "alcohol": str(member.get("Alcohol?", "")).strip().lower() in ("ja", "yes", "true", "1"),
            "sterke_drank": str(member.get("Sterke?", "")).strip().lower() in ("ja", "yes", "true", "1")
        })
    visitors = get_visitors()
    visitor_data = []
    for visitor in visitors:
        naam = str(visitor.get("Naam", "")).strip()
        if not naam:
            continue
        kost = float(visitor.get("Kostprijs") or 0.0)
        betaald_raw = str(visitor.get("Betaald?", "")).strip().lower()
        is_paid = betaald_raw in ("ja", "yes", "true", "1")
        basis_betaald_by_name[naam.lower()] = is_paid
        personal_price = unpaid_persons_by_name.get(naam.lower(), 0.0)
        total_person_price = kost + personal_price
        summary.fourage += total_person_price
        visitor_data.append({
            "naam": naam,
            "sheet": SHEET_VISITORS,
            "kostprijs": kost,
            "betaald": is_paid,
            "is_leader": True,
            "alcohol": str(visitor.get("Alcohol?", "")).strip().lower() in ("ja", "yes", "true", "1"),
            "sterke_drank": str(visitor.get("Sterke?", "")).strip().lower() in ("ja", "yes", "true", "1")
        })
    for expense in expenses:
        categorie = str(expense.get("Categorie", "")).strip().lower()
        betaald = str(expense.get("Betaald?", "")).strip().lower()
        prijs = float(expense.get("Prijs") or 0.0)
        if categorie == "alcohol":
            summary.alcohol += prijs
        elif categorie == "sterke drank":
            summary.sterke_drank += prijs
        elif categorie == "persoonlijk":
            if betaald not in ("ja", "yes", "true", "1"):
                summary.persoonlijk += prijs
        else:
            summary.algemeen += prijs
    all_persons = member_data + visitor_data
    active_persons = [
        person for person in all_persons
        if person["sheet"] == SHEET_VISITORS or (person["sheet"] == SHEET_MEMBERS and person["is_leader"])
    ]
    total_alcohol_drinkers = sum(1 for person in active_persons if person["alcohol"])
    total_sterke_drinkers = sum(1 for person in active_persons if person["sterke_drank"])
    per_alcohol = (summary.alcohol / total_alcohol_drinkers) if total_alcohol_drinkers else 0.0
    per_sterke = (summary.sterke_drank / total_sterke_drinkers) if total_sterke_drinkers else 0.0
    rest_map = get_rest_betaald()
    person_rows: list[Person] = []
    for persoon in active_persons:
        alcohol_aandeel = per_alcohol if persoon["alcohol"] else 0.0
        sterke_aandeel = per_sterke if persoon["sterke_drank"] else 0.0
        totaal_aandeel = alcohol_aandeel + sterke_aandeel
        if persoon["sheet"] == SHEET_MEMBERS:
            summary.leiding += totaal_aandeel
        else:
            summary.fourage += totaal_aandeel
        personal_price = unpaid_persons_by_name.get(persoon["naam"].strip().lower(), 0.0)
        betaald = basis_betaald_by_name.get(persoon["naam"].strip().lower(), False)
        rest_betaald = rest_map.get(persoon["naam"].strip().lower(), False)
        person_rows.append(
            Person(
                naam=persoon["naam"],
                sheet=persoon["sheet"],
                kostprijs_basis=persoon["kostprijs"],
                alcohol_aandeel=alcohol_aandeel,
                sterke_aandeel=sterke_aandeel,
                persoonlijk_aandeel=personal_price,
                basis_betaald=betaald,
                rest_betaald=rest_betaald
            )
        )
    person_rows.sort(key=lambda row: (0 if row.sheet == SHEET_MEMBERS else 1, row.naam.lower()))
    uitgaven_dict = {}
    for expense in expenses:
        categorie = str(expense.get("Categorie", "")).strip() or "Algemeen"
        betaald = str(expense.get("Betaald?", "")).strip().lower()
        if categorie.lower() == "persoonlijk" and betaald in ("ja", "yes", "true", "1"):
            continue
        prijs = float(expense.get("Prijs") or 0.0)
        uitgaven_dict[categorie] = uitgaven_dict.get(categorie, 0.0) + prijs
    summary.uitgaven_per_categorie = uitgaven_dict
    summary.inkomsten_per_categorie = {
        "Leden": summary.leden,
        "Leiding": summary.leiding,
        "Fourage & bezoekers": summary.fourage
    }
    return summary, person_rows

def get_rest_betaald() -> dict[str, bool]:
    try:
        sheet = get_sheet(SHEET_SUMMARY)
    except KeyError:
        return {}
    rest_map = {}
    reading_rest = False
    for row in sheet.iter_rows(values_only=True):
        if not row or row[0] is None:
            continue
        val = str(row[0]).strip()
        if val == "--- REST BETAALD ---":
            reading_rest = True
            continue
        if reading_rest and len(row) >= 2 and row[0] is not None:
            name = str(row[0]).strip().lower()
            is_paid = str(row[1]).strip().lower() in ("ja", "yes", "true", "1")
            rest_map[name] = is_paid
    return rest_map

def set_rest_betaald(naam: str, value: bool) -> None:
    sheet = get_sheet(SHEET_SUMMARY)
    name_lower = naam.strip().lower()
    header_row_idx = None
    rows = list(sheet.iter_rows(values_only=False))
    for row_index, row in enumerate(rows, start=1):
        if row[0].value == "--- REST BETAALD ---":
            header_row_idx = row_index
            break
    if header_row_idx is None:
        sheet.append([])
        sheet.append(["--- REST BETAALD ---", ""])
        header_row_idx = sheet.max_row
    found = False
    for row_index in range(header_row_idx + 1, sheet.max_row + 1):
        cell_name = sheet.cell(row=row_index, column=1).value
        if cell_name and str(cell_name).strip().lower() == name_lower:
            sheet.cell(row=row_index, column=2, value="Ja" if value else "Nee")
            found = True
            break
    if not found:
        sheet.append([naam, "Ja" if value else "Nee"])
    session_store.save_current()

def save_summary_to_excel() -> None:
    workbook = get_workbook()
    summary, person_rows = get_summary()
    if SHEET_SUMMARY in workbook.sheetnames:
        del workbook[SHEET_SUMMARY]
    sheet = workbook.create_sheet(title=SHEET_SUMMARY)
    sheet.append(["--- INKOMSTEN ---", ""])
    sheet.append(["Leden", summary.leden])
    sheet.append(["Leiding", summary.leiding])
    sheet.append(["Fourage & bezoekers", summary.fourage])
    sheet.append(["Totale inkomsten", summary.inkomsten])
    sheet.append([])
    sheet.append(["--- UITGAVEN PER CATEGORIE ---", ""])
    if summary.uitgaven_per_categorie:
        for categorie, bedrag in summary.uitgaven_per_categorie.items():
            sheet.append([categorie, bedrag])
    sheet.append(["Totale uitgaven", summary.uitgaven])
    sheet.append([])
    sheet.append(["--- FINANCIEEL RESULTAAT ---", ""])
    sheet.append(["Totaal Omzet", summary.omzet])
    sheet.append([])
    sheet.append(["--- REST BETAALD ---", ""])
    for pr in person_rows:
        sheet.append([pr.naam, "Ja" if pr.rest_betaald else "Nee"])
    session_store.save_current()
