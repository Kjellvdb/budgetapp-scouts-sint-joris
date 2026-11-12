from __future__ import annotations

from contextlib import contextmanager
from copy import copy
from pathlib import Path
from typing import Any, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

from app.common import EXPENSE_HEADERS, MEMBER_HEADERS, SHEET_EXPENSES, SHEET_MEMBERS, SHEET_VISITORS, SHEET_BUDGET, VISITOR_HEADERS, Expense, field_for_header, format_quantity, parse_date, parse_price

DATE_NUMBER_FORMAT = "DD/MM/YYYY"
MONEY_NUMBER_FORMAT = '"€" #,##0.00'

_EXPENSE_FIELDS = (
    ("datum", "Datum", 15),
    ("item", "Item", 30),
    ("aantal", "Aantal", 10),
    ("prijs", "Totale prijs", 15),
    ("categorie", "Categorie", 16),
    ("naam", "Naam", 24),
    ("betaald", "Betaald?", 12),
)

FILL_PAID   = PatternFill("solid", fgColor="E2F4E6")
FILL_UNPAID = PatternFill("solid", fgColor="FBE3E3")

class StorageError(Exception):
    pass

def _number_or_text(text: Any) -> Any:
    s = str(text).strip() if text is not None else ""
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return s

class BudgetStore:
    REST_COL = 11

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _open(self, data_only: bool = True):
        try:
            return load_workbook(self.path, data_only=data_only)
        except PermissionError as exc:
            raise StorageError("Geen toegang tot het Excel-bestand. Sluit het in Excel en probeer opnieuw.") from exc
        except FileNotFoundError as exc:
            raise StorageError(f"Bestand niet gevonden: {self.path}") from exc
        except Exception as exc:
            raise StorageError(f"Kan het Excel-bestand niet lezen: {exc}") from exc

    @contextmanager
    def _edit(self):
        wb = self._open(data_only=False)
        try:
            yield wb
            try:
                wb.save(self.path)
            except PermissionError as exc:
                raise StorageError("Het Excel-bestand is geopend in een ander programma. Sluit het en probeer opnieuw.") from exc
        finally:
            wb.close()

    def check(self) -> None:
        wb = self._open()
        try:
            if SHEET_MEMBERS not in wb.sheetnames:
                raise StorageError(f"Dit is geen geldige budgettering: tabblad '{SHEET_MEMBERS}' ontbreekt.")
        finally:
            wb.close()

    def read_table(self, sheet_name: str) -> tuple[list[str], list[tuple[int, list[Any]]]]:
        wb = self._open()
        try:
            if sheet_name not in wb.sheetnames:
                return [], []
            all_rows = list(wb[sheet_name].iter_rows(values_only=True))
        finally:
            wb.close()
        if not all_rows:
            return [], []
        headers = [str(c).strip() if c is not None else "" for c in all_rows[0]]
        rows = [(r, list(values)) for r, values in enumerate(all_rows[1:], start=2) if not all(v in (None, "") for v in values)]
        return headers, rows

    def set_column_value(self, sheet_name: str, rows: list[int], col: int, value: Any, number_format: Optional[str] = None) -> None:
        with self._edit() as wb:
            ws = wb[sheet_name]
            for r in rows:
                cell = ws.cell(row=r, column=col, value=value)
                if number_format:
                    cell.number_format = number_format

    def set_cell(self, sheet_name: str, row: int, col: int, value: Any, isBetaling: bool = False, number_format: Optional[str] = None) -> None:
        with self._edit() as wb:
            cell = wb[sheet_name].cell(row=row, column=col, value=value)
            if number_format:
                cell.number_format = number_format
            if isBetaling:
                cell.fill = FILL_PAID if str(value).lower() == "ja" else FILL_UNPAID

    def member_names(self) -> list[str]:
        names: set[str] = set()
        wb = self._open()
        try:
            for sheet_name in wb.sheetnames:
                if sheet_name.lower() == SHEET_EXPENSES.lower():
                    continue
                rows = list(wb[sheet_name].iter_rows(values_only=True))
                if len(rows) < 2:
                    continue
                headers = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
                first = last = full = -1
                for idx, h in enumerate(headers):
                    if "voornaam" in h:
                        first = idx
                    elif "achternaam" in h or "familienaam" in h:
                        last = idx
                    elif "naam" in h or "lid" in h:
                        full = idx

                def cell(row, idx):
                    return str(row[idx]).strip() if 0 <= idx < len(row) and row[idx] else ""

                for row in rows[1:]:
                    if first != -1 and last != -1:
                        name = f"{cell(row, first)} {cell(row, last)}".strip()
                    else:
                        name = cell(row, full)
                    if name and name.lower() != "none":
                        names.add(name)
        finally:
            wb.close()
        return sorted(names, key=str.lower)

    @staticmethod
    def _make_visitors_sheet(wb):
        ws = wb.create_sheet(SHEET_VISITORS)
        ws.append(VISITOR_HEADERS)
        for letter, width in zip("ABCDEF", (16, 20, 24, 24, 22, 26)):
            ws.column_dimensions[letter].width = width
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        return ws

    def add_visitor(self, voornaam: str, achternaam: str, kostprijs: float, betaald: bool, alcohol: bool = False, sterke_drank: bool = False) -> None:
        with self._edit() as wb:
            ws = wb[SHEET_VISITORS] if SHEET_VISITORS in wb.sheetnames else self._make_visitors_sheet(wb)
            row = self._last_data_row(ws) + 1
            ws.cell(row=row, column=1, value=voornaam or None)
            ws.cell(row=row, column=2, value=achternaam or None)
            ws.cell(row=row, column=3, value=float(kostprijs)).number_format = MONEY_NUMBER_FORMAT
            ws.cell(row=row, column=4, value="Ja" if betaald else "Nee")
            ws.cell(row=row, column=5, value="Ja" if alcohol else "Nee")
            ws.cell(row=row, column=6, value="Ja" if sterke_drank else "Nee")
            ws.cell(row=row, column=4).fill = FILL_PAID if betaald else FILL_UNPAID

    def update_visitor(self, row: int, voornaam: str, achternaam: str, kostprijs: float, betaald: bool, alcohol: bool = False, sterke_drank: bool = False) -> None:
        with self._edit() as wb:
            ws = wb[SHEET_VISITORS]
            old_voornaam = str(ws.cell(row=row, column=1).value or "").strip()
            old_achternaam = str(ws.cell(row=row, column=2).value or "").strip()
            old_name = f"{old_voornaam} {old_achternaam}".strip()

            ws.cell(row=row, column=1, value=voornaam or None)
            ws.cell(row=row, column=2, value=achternaam or None)
            ws.cell(row=row, column=3, value=float(kostprijs)).number_format = MONEY_NUMBER_FORMAT
            ws.cell(row=row, column=4, value="Ja" if betaald else "Nee")
            ws.cell(row=row, column=5, value="Ja" if alcohol else "Nee")
            ws.cell(row=row, column=6, value="Ja" if sterke_drank else "Nee")
            ws.cell(row=row, column=4).fill = FILL_PAID if betaald else FILL_UNPAID

        new_name = f"{voornaam} {achternaam}".strip()
        if old_name and old_name.lower() != new_name.lower():
            expenses = self.read_expenses()
            for e in expenses:
                if e.naam.strip().lower() == old_name.lower():
                    e.naam = new_name
                    self.update_expense(e)

    def delete_visitors(self, rows: list[int]) -> None:
        deleted_names = set()
        wb = self._open()
        try:
            if SHEET_VISITORS in wb.sheetnames:
                ws = wb[SHEET_VISITORS]
                for r in set(rows):
                    v = str(ws.cell(row=r, column=1).value or "").strip()
                    a = str(ws.cell(row=r, column=2).value or "").strip()
                    name = f"{v} {a}".strip()
                    if name:
                        deleted_names.add(name.lower())
        finally:
            wb.close()

        with self._edit() as wb:
            ws = wb[SHEET_VISITORS]
            for r in sorted(set(rows), reverse=True):
                ws.delete_rows(r)

        if deleted_names:
            expenses = self.read_expenses()
            for e in expenses:
                if e.naam.strip().lower() in deleted_names:
                    e.categorie = "Algemeen"
                    e.naam = ""
                    e.betaald = False
                    self.update_expense(e)

    @staticmethod
    def _get_expense_sheet(wb):
        if SHEET_EXPENSES in wb.sheetnames:
            return wb[SHEET_EXPENSES]
        ws = wb.create_sheet(SHEET_EXPENSES)
        ws.append(EXPENSE_HEADERS)
        for idx, (_f, _h, width) in enumerate(_EXPENSE_FIELDS, start=1):
            ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width
        return ws

    @staticmethod
    def _ensure_expense_columns(ws) -> dict[str, int]:
        cols: dict[str, int] = {}
        last_used = 0
        for idx, cell in enumerate(ws[1], start=1):
            if cell.value not in (None, ""):
                last_used = idx
            field = field_for_header(cell.value)
            if field and field not in cols:
                cols[field] = idx
        for field, header, width in _EXPENSE_FIELDS:
            if field in cols:
                continue
            last_used += 1
            new = ws.cell(row=1, column=last_used, value=header)
            if last_used > 1:
                new._style = copy(ws.cell(row=1, column=last_used - 1)._style)
            ws.column_dimensions[new.column_letter].width = width
            cols[field] = last_used
        return cols

    @staticmethod
    def _last_data_row(ws) -> int:
        for r in range(ws.max_row, 1, -1):
            if any(c.value not in (None, "") for c in ws[r]):
                return r
        return 1

    @staticmethod
    def _write_expense(ws, cols: dict[str, int], row: int, e: Expense) -> None:
        values = {
            "datum": e.datum if e.datum else (e.datum_text or None),
            "item": e.item or None,
            "aantal": _number_or_text(e.aantal),
            "prijs": float(e.prijs),
            "categorie": e.categorie or None,
            "naam": e.naam.strip() if e.naam else "",
            "betaald": ("Ja" if e.betaald else "Nee") if e.is_personal else None,
        }
        for field, col in cols.items():
            cell = ws.cell(row=row, column=col, value=values[field])
            if field == "datum" and e.datum:
                cell.number_format = DATE_NUMBER_FORMAT
            elif field == "prijs":
                cell.number_format = MONEY_NUMBER_FORMAT
        betaald_col = cols.get("betaald")
        if betaald_col:
            cell = ws.cell(row=row, column=betaald_col)
            if e.is_personal:
                cell.fill = FILL_PAID if e.betaald else FILL_UNPAID
            else:
                cell.fill = PatternFill()

    def read_expenses(self) -> list[Expense]:
        headers, rows = self.read_table(SHEET_EXPENSES)
        cols: dict[str, int] = {}
        for idx, h in enumerate(headers):
            field = field_for_header(h)
            if field and field not in cols:
                cols[field] = idx

        def get(values: list[Any], field: str) -> Any:
            idx = cols.get(field)
            return values[idx] if idx is not None and idx < len(values) else None

        result = []
        for row, values in rows:
            raw_date = get(values, "datum")
            parsed = parse_date(raw_date)
            categorie = get(values, "categorie")
            naam = get(values, "naam")
            result.append(Expense(
                datum=parsed,
                datum_text="" if parsed or raw_date is None else str(raw_date).strip(),
                item="" if get(values, "item") is None else str(get(values, "item")).strip(),
                aantal=format_quantity(get(values, "aantal")),
                prijs=parse_price(get(values, "prijs")) or 0.0,
                categorie="" if categorie is None else str(categorie).strip(),
                naam="" if naam is None else str(naam).strip(),
                betaald=str(get(values, "betaald") or "").strip().lower() == "ja",
                row=row,
            ))
        return result

    def add_expenses(self, expenses: list[Expense]) -> None:
        with self._edit() as wb:
            ws = self._get_expense_sheet(wb)
            cols = self._ensure_expense_columns(ws)
            row = self._last_data_row(ws) + 1
            for e in expenses:
                self._write_expense(ws, cols, row, e)
                row += 1

    def update_expense(self, expense: Expense) -> None:
        if not expense.row:
            raise StorageError("Deze uitgave heeft geen rijnummer.")
        with self._edit() as wb:
            ws = self._get_expense_sheet(wb)
            cols = self._ensure_expense_columns(ws)
            self._write_expense(ws, cols, expense.row, expense)

    def delete_expenses(self, rows: list[int]) -> None:
        with self._edit() as wb:
            ws = wb[SHEET_EXPENSES]
            for r in sorted(set(rows), reverse=True):
                ws.delete_rows(r)

    def read_persons_with_drinks(self) -> list[dict]:
        result = []
        for sheet_name in (SHEET_MEMBERS, SHEET_VISITORS):
            headers, rows = self.read_table(sheet_name)
            if not headers:
                continue
            low = [h.lower() for h in headers]
            kost_idx = next((i for i, h in enumerate(low) if "kostprijs" in h), -1)
            first_idx = next((i for i, h in enumerate(low) if h == "voornaam"), -1)
            last_idx = next((i for i, h in enumerate(low) if "achternaam" in h or "familienaam" in h), -1)
            full_idx = next((i for i, h in enumerate(low) if "naam" in h and i not in (first_idx, last_idx)), -1)
            takken_idx = next((i for i, h in enumerate(low) if "takken" in h), -1)
            alcohol_idx = next((i for i, h in enumerate(low) if "alcohol" in h), -1)
            sterke_idx = next((i for i, h in enumerate(low) if "sterke" in h), -1)

            def _cell(values, idx):
                return str(values[idx]).strip() if 0 <= idx < len(values) and values[idx] not in (None, "") else ""

            for _row, values in rows:
                if first_idx != -1 and last_idx != -1:
                    naam = f"{_cell(values, first_idx)} {_cell(values, last_idx)}".strip()
                elif first_idx != -1:
                    naam = _cell(values, first_idx)
                else:
                    naam = _cell(values, full_idx)
                if not naam or naam.lower() == "none":
                    continue
                kostprijs = parse_price(values[kost_idx]) or 0.0 if 0 <= kost_idx < len(values) else 0.0
                takken = _cell(values, takken_idx).lower() if takken_idx != -1 else ""
                branch_parts = [p.strip() for p in takken.split(",")]
                is_leiding = "leiding" in branch_parts

                if sheet_name == SHEET_MEMBERS and not is_leiding:
                    alcohol = False
                    sterke_drank = False
                else:
                    alcohol = _cell(values, alcohol_idx).lower() == "ja" if alcohol_idx != -1 else False
                    sterke_drank = _cell(values, sterke_idx).lower() == "ja" if sterke_idx != -1 else False

                result.append({
                    "naam": naam,
                    "kostprijs": kostprijs,
                    "alcohol": alcohol,
                    "sterke_drank": sterke_drank,
                    "takken": takken,
                    "sheet": sheet_name,
                })
        return result

    @staticmethod
    def create_new(file_path: Path | str, members: list[list[str]]) -> None:
        wb = Workbook()
        ws_m = wb.active
        ws_m.title = SHEET_MEMBERS
        ws_m.append(MEMBER_HEADERS)
        for voornaam, achternaam, takken in members:
            ws_m.append([voornaam, achternaam, takken, 0.0, "Nee", "Nee", "Nee"])
            ws_m.cell(row=ws_m.max_row, column=4).number_format = MONEY_NUMBER_FORMAT
            ws_m.cell(row=ws_m.max_row, column=5).fill = FILL_UNPAID

        for col in ws_m.columns:
            longest = max((len(str(c.value)) for c in col if c.value is not None), default=0)
            ws_m.column_dimensions[col[0].column_letter].width = max(longest + 4, 12)

        BudgetStore._make_visitors_sheet(wb)

        ws_e = wb.create_sheet(SHEET_EXPENSES)
        ws_e.append(EXPENSE_HEADERS)
        for idx, (_f, _h, width) in enumerate(_EXPENSE_FIELDS, start=1):
            ws_e.column_dimensions[ws_e.cell(row=1, column=idx).column_letter].width = width

        for ws in (ws_m, ws_e):
            for cell in ws[1]:
                cell.font = Font(bold=True)
            ws.freeze_panes = "A2"

        try:
            wb.save(file_path)
        except PermissionError as exc:
            raise StorageError("Kan het bestand niet opslaan. Is het geopend in een ander programma?") from exc
        finally:
            wb.close()

    def write_summary(self, s, person_rows) -> None:
        with self._edit() as wb:
            if SHEET_BUDGET in wb.sheetnames:
                del wb[SHEET_BUDGET]
            ws = wb.create_sheet(SHEET_BUDGET)

            bold = Font(bold=True)
            bold_white = Font(bold=True, color="FFFFFF")
            green_fill = PatternFill("solid", fgColor="185C37")
            red_fill = PatternFill("solid", fgColor="B00020")
            header_fill = PatternFill("solid", fgColor="E8F3EC")
            right = Alignment(horizontal="right")

            ws.column_dimensions["A"].width = 30
            ws.column_dimensions["B"].width = 18

            def section(label, fill):
                ws.append([label])
                cell = ws.cell(row=ws.max_row, column=1)
                cell.font = bold_white
                cell.fill = fill
                ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=2)

            def line(label, value, bold_row=False, fg_color=None):
                ws.append([label, value])
                r = ws.max_row
                lc = ws.cell(row=r, column=1)
                vc = ws.cell(row=r, column=2)
                vc.number_format = MONEY_NUMBER_FORMAT
                vc.alignment = right
                if bold_row:
                    lc.font = Font(bold=True, color=fg_color or "000000")
                    vc.font = Font(bold=True, color=fg_color or "000000")
                if fg_color and not bold_row:
                    lc.font = Font(color=fg_color)
                    vc.font = Font(color=fg_color)

            ws.append(["Budgetering"])
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=16, color="185C37")
            ws.append([])

            section("Inkomsten", green_fill)
            line("Leden", s.leden)
            line("Leiding", s.leiding)
            line("Fourage & bezoekers", s.fourage)
            line("Totale inkomsten", s.inkomsten, bold_row=True, fg_color="185C37")
            ws.append([])

            section("Uitgaven", red_fill)
            line("Algemeen", s.algemeen)
            line("Alcohol", s.alcohol)
            line("Sterke drank", s.sterke_drank)
            line("Totale uitgaven", s.uitgaven, bold_row=True, fg_color="B00020")
            ws.append([])

            omzet_color = "185C37" if s.omzet >= 0 else "B00020"
            line("Totaal omzet", s.omzet, bold_row=True, fg_color=omzet_color)
            ws.append([])
            ws.append([])

            ws.append(["Kostprijs per persoon"])
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=14, color="185C37")
            ws.append([])

            for col_letter, width in zip("CDEFGHIJK", (24, 18, 14, 14, 14, 14, 14, 14, 14)):
                ws.column_dimensions[col_letter].width = width

            headers = ["Naam", "Groep", "Basis", "Drank", "Persoonlijk", "Totaal", "Nog te betalen", "Basis betaald?", "Rest betaald?"]
            header_row = ws.max_row + 1
            for i, h in enumerate(headers, start=3):
                cell = ws.cell(row=header_row, column=i, value=h)
                cell.font = bold
                cell.fill = header_fill
                cell.alignment = right if i > 4 else Alignment(horizontal="left")
            ws.append([])

            from app.common import SHEET_MEMBERS
            for pr in person_rows:
                groep = "Leiding" if pr.sheet == SHEET_MEMBERS else "Fourage/Bezoeker"
                drank = pr.alcohol_aandeel + pr.sterke_aandeel
                data_row = ws.max_row + 1
                ws.cell(row=data_row, column=3, value=pr.naam)
                ws.cell(row=data_row, column=4, value=groep)
                for col, val in zip([5, 6, 7, 8], [pr.kostprijs_base, drank, pr.persoonlijk_aandeel, pr.kostprijs_totaal]):
                    cell = ws.cell(row=data_row, column=col, value=val)
                    cell.number_format = MONEY_NUMBER_FORMAT
                    cell.alignment = right
                ws.cell(row=data_row, column=8).font = bold

                ntb_cell = ws.cell(row=data_row, column=9, value=pr.nog_te_betalen)
                ntb_cell.number_format = MONEY_NUMBER_FORMAT
                ntb_cell.alignment = right

                betaald_tekst = "Ja" if pr.basis_betaald else "Nee"
                betaald_cell = ws.cell(row=data_row, column=10, value=betaald_tekst)
                betaald_cell.font = Font(bold=False, color="1F6B3A" if pr.basis_betaald else "C00000")
                betaald_cell.alignment = Alignment(horizontal="center")

                self._style_rest_cell(ws.cell(row=data_row, column=self.REST_COL), pr.rest_betaald)

                ws.append([])

            if person_rows:
                total_row = ws.max_row + 1
                ws.cell(row=total_row, column=3, value="Totaal").font = bold
                ws.cell(row=total_row, column=3).fill = header_fill
                for col, val in zip([5, 6, 7, 8], [
                    sum(p.kostprijs_base for p in person_rows),
                    sum(p.alcohol_aandeel + p.sterke_aandeel for p in person_rows),
                    sum(p.persoonlijk_aandeel for p in person_rows),
                    sum(p.kostprijs_totaal for p in person_rows),
                ]):
                    cell = ws.cell(row=total_row, column=col, value=val)
                    cell.number_format = MONEY_NUMBER_FORMAT
                    cell.alignment = right
                    cell.font = bold
                    cell.fill = header_fill
                total_ntb = sum(p.nog_te_betalen for p in person_rows)
                ntb_total = ws.cell(row=total_row, column=9, value=total_ntb)
                ntb_total.number_format = MONEY_NUMBER_FORMAT
                ntb_total.alignment = right
                ntb_total.font = bold
                ntb_total.fill = header_fill
                ws.cell(row=total_row, column=10).fill = header_fill
                ws.cell(row=total_row, column=self.REST_COL).fill = header_fill
                ws.append([])

    @staticmethod
    def _style_rest_cell(cell, betaald: bool) -> None:
        cell.value = "Ja" if betaald else "Nee"
        cell.fill = FILL_PAID if betaald else FILL_UNPAID
        cell.font = Font(color="1F6B3A" if betaald else "C00000")
        cell.alignment = Alignment(horizontal="center")

    def read_rest_betaald(self) -> dict[str, bool]:
        wb = self._open()
        try:
            if SHEET_BUDGET not in wb.sheetnames:
                return {}
            rows = list(wb[SHEET_BUDGET].iter_rows(values_only=True))
        finally:
            wb.close()
        result: dict[str, bool] = {}
        in_table = False
        for values in rows:
            naam = values[2] if len(values) > 2 else None
            if not in_table:
                in_table = (naam == "Naam")
                continue
            if naam in (None, ""):
                continue
            if str(naam).strip() == "Totaal":
                break
            flag = values[self.REST_COL - 1] if len(values) >= self.REST_COL else None
            result[str(naam).strip().lower()] = str(flag or "").strip().lower() == "ja"
        return result

    def set_rest_betaald(self, naam: str, betaald: bool) -> None:
        with self._edit() as wb:
            if SHEET_BUDGET not in wb.sheetnames:
                return
            ws = wb[SHEET_BUDGET]
            in_table = False
            for r in range(1, ws.max_row + 1):
                c = ws.cell(row=r, column=3).value
                if not in_table:
                    in_table = (c == "Naam")
                    continue
                if c in (None, ""):
                    continue
                if str(c).strip() == "Totaal":
                    break
                if str(c).strip().lower() == naam.strip().lower():
                    self._style_rest_cell(ws.cell(row=r, column=self.REST_COL), betaald)
