"""Tabblad 'Budgetering': overzicht van inkomsten, uitgaven, omzet en kostprijs per persoon."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import NamedTuple

from app.common import SHEET_MEMBERS, SHEET_VISITORS, format_money, parse_price
from app.storage import BudgetStore, StorageError
from app.ui import BG_PAGE, ERROR_RED, EXCEL_GREEN_DARK, FONT_BASE, FONT_H1, FONT_H2, FONT_H3, FONT_SM, FONT_XS, GRID_LINE, ROW_EVEN, ROW_ODD, ROW_PAID, ROW_UNPAID, TABLE_HEADER_BG, TEXT_DISABLED, TEXT_MUTED

LEIDING = "leiding"
_COL_WEIGHTS = (4, 3, 2, 2, 3, 2, 3, 3, 3)

def _apply_columns(frame: tk.Frame) -> None:
    for i, w in enumerate(_COL_WEIGHTS):
        frame.columnconfigure(i, weight=w, uniform="pcol")


@dataclass
class Summary:
    leden: float = 0.0
    leiding: float = 0.0
    fourage: float = 0.0
    algemeen: float = 0.0
    alcohol: float = 0.0
    sterke_drank: float = 0.0

    @property
    def inkomsten(self) -> float:
        return self.leden + self.leiding + self.fourage

    @property
    def uitgaven(self) -> float:
        return self.algemeen + self.alcohol + self.sterke_drank

    @property
    def omzet(self) -> float:
        return self.inkomsten - self.uitgaven


class PersonRow(NamedTuple):
    naam: str
    sheet: str          # SHEET_MEMBERS of SHEET_VISITORS
    kostprijs_base: float
    alcohol_aandeel: float
    sterke_aandeel: float
    persoonlijk_aandeel: float
    basis_betaald: bool = False
    rest_betaald: bool = False

    @property
    def kostprijs_totaal(self) -> float:
        return self.kostprijs_base + self.alcohol_aandeel + self.sterke_aandeel + self.persoonlijk_aandeel

    @property
    def nog_te_betalen(self) -> float:
        basis = 0.0 if self.basis_betaald else self.kostprijs_base
        return basis + self.alcohol_aandeel + self.sterke_aandeel + self.persoonlijk_aandeel


def compute_summary(store: BudgetStore) -> tuple[Summary, list[PersonRow]]:
    s = Summary()
    expenses = store.read_expenses()

    # ---- Onbetaalde persoonlijke uitgaven per persoon (op basis van naam) ----
    unpaid_personal_by_name: dict[str, float] = {}
    for e in expenses:
        if e.categorie.strip().lower() == "persoonlijk" and not e.betaald and e.naam.strip():
            name_key = e.naam.strip().lower()
            unpaid_personal_by_name[name_key] = unpaid_personal_by_name.get(name_key, 0.0) + e.prijs

    # ---- Inkomsten van leden (basis kostprijs + persoonlijke onbetaalde uitgaven) ----
    headers, rows = store.read_table(SHEET_MEMBERS)
    low = [h.lower() for h in headers]
    kost = next((i for i, h in enumerate(low) if "kostprijs" in h), -1)
    takken = next((i for i, h in enumerate(low) if "takken" in h), -1)
    betaald_idx = next((i for i, h in enumerate(low) if "betaald" in h), -1)
    first_idx = next((i for i, h in enumerate(low) if h == "voornaam"), -1)
    last_idx = next((i for i, h in enumerate(low) if "achternaam" in h or "familienaam" in h), -1)
    full_idx = next((i for i, h in enumerate(low) if "naam" in h and i not in (first_idx, last_idx)), -1)

    def _cell(values, idx):
        return str(values[idx]).strip() if 0 <= idx < len(values) and values[idx] not in (None, "") else ""

    basis_betaald_by_name: dict[str, bool] = {}

    for _row, values in rows:
        if first_idx != -1 and last_idx != -1:
            naam = f"{_cell(values, first_idx)} {_cell(values, last_idx)}".strip()
        elif first_idx != -1:
            naam = _cell(values, first_idx)
        else:
            naam = _cell(values, full_idx)

        price = parse_price(values[kost]) if 0 <= kost < len(values) else None
        base_price = price or 0.0
        personal_price = unpaid_personal_by_name.get(naam.lower(), 0.0) if naam else 0.0
        total_person_price = base_price + personal_price

        betaald_raw = _cell(values, betaald_idx)
        if naam:
            basis_betaald_by_name[naam.lower()] = betaald_raw.lower() in ("ja", "yes", "true", "1")

        branch = str(values[takken] or "").strip().lower() if 0 <= takken < len(values) else ""
        branch_parts = [p.strip() for p in branch.split(",")]
        if "leiding" in branch_parts:
            s.leiding += total_person_price
        else:
            s.leden += total_person_price

    headers, rows = store.read_table(SHEET_VISITORS)
    low = [h.lower() for h in headers]
    kost = next((i for i, h in enumerate(low) if "kostprijs" in h), -1)
    betaald_idx = next((i for i, h in enumerate(low) if "betaald" in h), -1)
    first_idx = next((i for i, h in enumerate(low) if h == "voornaam"), -1)
    last_idx = next((i for i, h in enumerate(low) if "achternaam" in h or "familienaam" in h), -1)
    full_idx = next((i for i, h in enumerate(low) if "naam" in h and i not in (first_idx, last_idx)), -1)

    for _row, values in rows:
        if first_idx != -1 and last_idx != -1:
            naam = f"{_cell(values, first_idx)} {_cell(values, last_idx)}".strip()
        elif first_idx != -1:
            naam = _cell(values, first_idx)
        else:
            naam = _cell(values, full_idx)

        price = parse_price(values[kost]) if 0 <= kost < len(values) else None
        base_price = price or 0.0
        personal_price = unpaid_personal_by_name.get(naam.lower(), 0.0) if naam else 0.0
        total_person_price = base_price + personal_price

        betaald_raw = _cell(values, betaald_idx)
        if naam:
            basis_betaald_by_name[naam.lower()] = betaald_raw.lower() in ("ja", "yes", "true", "1")

        s.fourage += total_person_price

    # ---- Uitgaven opsplitsen ----
    for e in expenses:
        cat = e.categorie.strip().lower()
        if not e.counts_in_total:
            continue
        if cat == "alcohol":
            s.alcohol += e.prijs
        elif cat == "sterke drank":
            s.sterke_drank += e.prijs
        else:
            s.algemeen += e.prijs

    # ---- Per-persoon drankverrekening en toevoeging aan inkomsten leiding/fourage ----
    persons = store.read_persons_with_drinks()
    
    active_persons = [
        p for p in persons
        if p["sheet"] == SHEET_VISITORS or (p["sheet"] == SHEET_MEMBERS and "leiding" in [x.strip() for x in p["takken"].split(",")])
    ]

    n_alcohol = sum(1 for p in active_persons if p["alcohol"])
    n_sterke = sum(1 for p in active_persons if p["sterke_drank"])
    per_alcohol = (s.alcohol / n_alcohol) if n_alcohol else 0.0
    per_sterke = (s.sterke_drank / n_sterke) if n_sterke else 0.0
    rest_map = store.read_rest_betaald()

    person_rows: list[PersonRow] = []
    for p in active_persons:
        alcohol_share = per_alcohol if p["alcohol"] else 0.0
        sterke_share = per_sterke if p["sterke_drank"] else 0.0
        drink_share = alcohol_share + sterke_share

        # Voeg drankprijs toe aan inkomsten van leiding of fourage
        if p["sheet"] == SHEET_MEMBERS:
            s.leiding += drink_share
        else:
            s.fourage += drink_share

        personal_price = unpaid_personal_by_name.get(p["naam"].strip().lower(), 0.0)
        betaald = basis_betaald_by_name.get(p["naam"].strip().lower(), False)
        rest_betaald = rest_map.get(p["naam"].strip().lower(), False)

        person_rows.append(
            PersonRow(
                naam=p["naam"],
                sheet=p["sheet"],
                kostprijs_base=p["kostprijs"],
                alcohol_aandeel=alcohol_share,
                sterke_aandeel=sterke_share,
                persoonlijk_aandeel=personal_price,
                basis_betaald=betaald,
                rest_betaald=rest_betaald
            )
        )

    person_rows.sort(key=lambda r: (0 if r.sheet == SHEET_MEMBERS else 1, r.naam.lower()))

    return s, person_rows


class SummaryTab(tk.Frame):
    def __init__(self, parent: tk.Misc, store: BudgetStore):
        super().__init__(parent, bg=BG_PAGE)
        self.store = store
        self._values: dict[str, tk.Label] = {}

        # ---- twee kolommen naast elkaar ----
        left = tk.Frame(self, bg=BG_PAGE)
        left.pack(side="left", fill="both", expand=False, padx=(24, 12), pady=24)

        right = tk.Frame(self, bg=BG_PAGE)
        right.pack(side="left", fill="both", expand=True, padx=(0, 24), pady=24)

        # ---- linkerkaart: financieel overzicht ----
        card = tk.Frame(left, bg="white", highlightthickness=1, highlightbackground=GRID_LINE, padx=36, pady=28)
        card.pack(fill="both", expand=True)
        card.columnconfigure(0, weight=1)

        tk.Label(card, text="Budgetering", bg="white", fg=EXCEL_GREEN_DARK,
                 font=FONT_H1).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self._r = 1
        self._section("Inkomsten", EXCEL_GREEN_DARK, card)
        self._line("leden", "Leden", card)
        self._line("leiding", "Leiding", card)
        self._line("fourage", "Fourage & bezoekers", card)
        self._line("inkomsten", "Totale inkomsten", card, bold=True, fg=EXCEL_GREEN_DARK, rule=True)

        self._section("Uitgaven", ERROR_RED, card, top=18)
        self._line("algemeen", "Algemeen", card)
        self._line("alcohol", "Alcohol", card)
        self._line("sterke_drank", "Sterke drank", card)
        self._line("uitgaven", "Totale uitgaven", card, bold=True, fg=ERROR_RED, rule=True)

        self._line("omzet", "Totaal omzet", card, bold=True, font_override=FONT_H3, rule=True, top=18)

        # ---- rechterkaart: kostprijs per persoon ----
        pcard = tk.Frame(right, bg="white", highlightthickness=1, highlightbackground=GRID_LINE, padx=0, pady=0)
        pcard.pack(fill="both", expand=True)

        header_frame = tk.Frame(pcard, bg="white", padx=24, pady=16)
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="Kostprijs per persoon", bg="white", fg=EXCEL_GREEN_DARK,
                 font=FONT_H2).pack(side="left")
        self.lbl_drink_info = tk.Label(header_frame, text="", bg="white", fg=TEXT_MUTED,
                                       font=FONT_XS)
        self.lbl_drink_info.pack(side="left", padx=(16, 0))

        # scrollbaar gebied eerst aanmaken (we hebben de breedte van de scrollbalk nodig voor de kop)
        scroll_frame = tk.Frame(pcard, bg="white")
        canvas = tk.Canvas(scroll_frame, bg="white", highlightthickness=0)
        vsb = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        # tabel-header (zelfde kolomverhouding als de rijen + spacer ter grootte van de scrollbalk)
        col_frame = tk.Frame(pcard, bg=GRID_LINE)
        col_frame.pack(fill="x", padx=1)
        col_inner = tk.Frame(col_frame, bg=TABLE_HEADER_BG)
        col_inner.pack(fill="x", padx=0, pady=1)
        _apply_columns(col_inner)
        col_inner.columnconfigure(len(_COL_WEIGHTS), weight=0, minsize=vsb.winfo_reqwidth())
        font_hdr = (*FONT_SM, "bold")
        for i, (title, anchor) in enumerate([
            ("Naam", "w"), ("Groep", "w"), ("Basis", "e"), ("Drank", "e"), ("Persoonlijk", "e"),
            ("Totaal", "e"), ("Nog te betalen", "e"), ("Basis betaald?", "center"), ("Rest betaald?", "center"),
        ]):
            tk.Label(col_inner, text=title, bg=TABLE_HEADER_BG, font=font_hdr, anchor=anchor,
                     padx=8, pady=4).grid(row=0, column=i, sticky="ew")
        tk.Label(col_inner, text="", bg=TABLE_HEADER_BG).grid(row=0, column=len(_COL_WEIGHTS), sticky="ew")

        scroll_frame.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._persons_canvas = canvas
        self._persons_inner = tk.Frame(canvas, bg="white")
        self._persons_window = canvas.create_window((0, 0), window=self._persons_inner, anchor="nw")
        self._persons_inner.bind("<Configure>", self._on_inner_configure)
        canvas.bind("<Configure>", self._on_canvas_configure)
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ----------------------------------------------------------------- helpers kaart
    def _section(self, text: str, color: str, card: tk.Frame, top: int = 6) -> None:
        tk.Label(card, text=text, bg="white", fg=color, font=(*FONT_BASE, "bold")).grid(
            row=self._r, column=0, columnspan=2, sticky="w", pady=(top, 4))
        self._r += 1

    def _line(self, key: str, label: str, card: tk.Frame, bold: bool = False, fg: str = "black",
              font_override = None, rule: bool = False, top: int = 0) -> None:
        if rule:
            tk.Frame(card, bg=GRID_LINE, height=1).grid(row=self._r, column=0, columnspan=2, sticky="ew",
                                                         pady=(top or 4, 4))
            self._r += 1
        font = font_override or (*FONT_BASE, "bold" if bold else "normal")
        tk.Label(card, text=label, bg="white", fg=fg, font=font, anchor="w").grid(
            row=self._r, column=0, sticky="w", padx=(12 if not bold else 0, 0), pady=2)
        value = tk.Label(card, text=format_money(0.0), bg="white", fg=fg, font=font, anchor="e")
        value.grid(row=self._r, column=1, sticky="e", pady=2)
        self._values[key] = value
        self._r += 1

    def _choose_rest(self, event: tk.Event, naam: str) -> None:
        menu = tk.Menu(self, tearoff=0, font=FONT_BASE)
        menu.add_command(label="✔ Ja", command=lambda: self._save_rest(naam, True))
        menu.add_command(label="❌ Nee", command=lambda: self._save_rest(naam, False))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _save_rest(self, naam: str, value: bool) -> None:
        try:
            self.store.set_rest_betaald(naam, value)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Fout", f"Opslaan mislukt: {exc}", parent=self)
            return
        self.refresh(keep_scroll=True)

    # ----------------------------------------------------------------- scroll
    def _on_inner_configure(self, _event) -> None:
        self._persons_inner.update_idletasks()
        self._persons_canvas.configure(scrollregion=self._persons_canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self._persons_canvas.itemconfigure(self._persons_window, width=event.width)

    # ----------------------------------------------------------------- personen tabel
    def _build_persons_table(self, person_rows: list[PersonRow]) -> None:
        inner = self._persons_inner
        for w in inner.winfo_children():
            w.destroy()
        _apply_columns(inner)

        font_n = FONT_SM
        font_b = (*FONT_SM, "bold")

        for i, pr in enumerate(person_rows):
            bg = ROW_EVEN if i % 2 == 0 else ROW_ODD
            groep = "Leiding" if pr.sheet == SHEET_MEMBERS else "Fourage/Bezoeker"
            drank = pr.alcohol_aandeel + pr.sterke_aandeel
            tk.Label(inner, text=pr.naam, bg=bg, font=font_n, anchor="w", padx=8, pady=3).grid(
                row=i, column=0, sticky="ew")
            tk.Label(inner, text=groep, bg=bg, font=font_n, anchor="w", padx=4, pady=3).grid(
                row=i, column=1, sticky="ew")
            tk.Label(inner, text=format_money(pr.kostprijs_base), bg=bg, font=font_n, anchor="e", padx=8).grid(
                row=i, column=2, sticky="ew")
            drank_fg = EXCEL_GREEN_DARK if drank > 0 else TEXT_DISABLED
            tk.Label(inner, text=format_money(drank), bg=bg, font=font_n, anchor="e", padx=8,
                     fg=drank_fg).grid(row=i, column=3, sticky="ew")
            pers_fg = EXCEL_GREEN_DARK if pr.persoonlijk_aandeel > 0 else TEXT_DISABLED
            tk.Label(inner, text=format_money(pr.persoonlijk_aandeel), bg=bg, font=font_n, anchor="e", padx=8,
                     fg=pers_fg).grid(row=i, column=4, sticky="ew")
            tk.Label(inner, text=format_money(pr.kostprijs_totaal), bg=bg, font=font_b, anchor="e", padx=8).grid(
                row=i, column=5, sticky="ew")
            tk.Label(inner, text=format_money(pr.nog_te_betalen), bg=bg, font=font_n, anchor="e", padx=8).grid(
                row=i, column=6, sticky="ew")
            betaald_tekst = "Ja" if pr.basis_betaald else "Nee"
            betaald_fg = EXCEL_GREEN_DARK if pr.basis_betaald else ERROR_RED
            tk.Label(inner, text=betaald_tekst, bg=bg, font=font_n, anchor="center", padx=8,
                     fg=betaald_fg).grid(row=i, column=7, sticky="ew")
            rest = pr.rest_betaald
            lbl = tk.Label(inner, text="✔ Ja" if rest else "❌ Nee", font=font_n, anchor="center", padx=8,
                           bg=ROW_PAID if rest else ROW_UNPAID, cursor="hand2")
            lbl.grid(row=i, column=8, sticky="ew")
            lbl.bind("<Button-1>", lambda e, n=pr.naam: self._choose_rest(e, n))

        # totaalrij
        if person_rows:
            tk.Frame(inner, bg=GRID_LINE, height=1).grid(
                row=len(person_rows), column=0, columnspan=9, sticky="ew", pady=(4, 2))
            totaal_row = len(person_rows) + 1
            total_basis = sum(p.kostprijs_base for p in person_rows)
            total_drank = sum(p.alcohol_aandeel + p.sterke_aandeel for p in person_rows)
            total_pers = sum(p.persoonlijk_aandeel for p in person_rows)
            total_all = sum(p.kostprijs_totaal for p in person_rows)
            bg = TABLE_HEADER_BG
            tk.Label(inner, text="Totaal", bg=bg, font=font_b, anchor="w", padx=8, pady=4).grid(
                row=totaal_row, column=0, columnspan=2, sticky="ew")
            tk.Label(inner, text=format_money(total_basis), bg=bg, font=font_b, anchor="e", padx=8).grid(
                row=totaal_row, column=2, sticky="ew")
            tk.Label(inner, text=format_money(total_drank), bg=bg, font=font_b, anchor="e", padx=8).grid(
                row=totaal_row, column=3, sticky="ew")
            tk.Label(inner, text=format_money(total_pers), bg=bg, font=font_b, anchor="e", padx=8).grid(
                row=totaal_row, column=4, sticky="ew")
            tk.Label(inner, text=format_money(total_all), bg=bg, font=font_b, anchor="e", padx=8).grid(
                row=totaal_row, column=5, sticky="ew")
            total_ntb = sum(p.nog_te_betalen for p in person_rows)
            tk.Label(inner, text=format_money(total_ntb), bg=bg, font=font_b, anchor="e", padx=8).grid(
                row=totaal_row, column=6, sticky="ew")
            tk.Label(inner, text="", bg=bg).grid(row=totaal_row, column=7, sticky="ew")
            tk.Label(inner, text="", bg=bg).grid(row=totaal_row, column=8, sticky="ew")

    # ------------------------------------------------------------------ laden
    def refresh(self, keep_scroll: bool = False) -> None:
        pos = self._persons_canvas.yview()[0] if keep_scroll else 0.0
        try:
            s, person_rows = compute_summary(self.store)
        except StorageError as exc:
            messagebox.showerror("Fout", str(exc), parent=self)
            return
        for key, label in self._values.items():
            label.config(text=format_money(getattr(s, key)))
        self._values["omzet"].config(fg=EXCEL_GREEN_DARK if s.omzet >= 0 else ERROR_RED)

        # drankinfo
        n_alcohol = sum(1 for p in person_rows if p.alcohol_aandeel > 0)
        n_sterke = sum(1 for p in person_rows if p.sterke_aandeel > 0)
        parts = []
        if s.alcohol:
            parts.append(f"alcohol ÷ {n_alcohol} drinkers")
        if s.sterke_drank:
            parts.append(f"sterke drank ÷ {n_sterke} drinkers")
        self.lbl_drink_info.config(text=",  ".join(parts) if parts else "")

        self._build_persons_table(person_rows)
        self._persons_canvas.update_idletasks()
        self._persons_canvas.yview_moveto(pos)

        try:
            self.store.write_summary(s, person_rows)
        except Exception as exc:
            messagebox.showerror("Fout", f"Opslaan overzicht mislukt: {exc}", parent=self)
