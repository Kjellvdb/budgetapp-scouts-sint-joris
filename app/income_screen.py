"""Tabblad 'Ledenlijst': ledenlijst met kostprijs en betaalstatus."""
from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Optional, Sequence

from app.common import DATE_FORMAT, SHEET_MEMBERS, SHEET_VISITORS, format_money, parse_price
from app.storage import MONEY_NUMBER_FORMAT, BudgetStore, StorageError
from app.ui import EXCEL_GREEN_DARK, FONT_BASE, FONT_SM, FONT_XS, GRID_LINE, RIBBON_BG, ROW_PAID, ROW_PAID_HOVER, ROW_UNPAID, ROW_UNPAID_HOVER, DataTree


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime(DATE_FORMAT)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class IncomeTab(tk.Frame):
    def __init__(self, parent: tk.Misc, store: BudgetStore, sheet_name: str = SHEET_MEMBERS,
                 total_label: str = "Totale inkomsten weekend/kamp", default_headers: Sequence[str] = (),
                 selectmode: str = "none"):
        super().__init__(parent, bg="white")
        self.store = store
        self.sheet_name = sheet_name
        self.total_label = total_label
        self.default_headers = list(default_headers)
        self.headers: list[str] = []
        self._configured_headers: Optional[list[str]] = None
        self.kost_idx = -1
        self.betaald_idx = -1
        self.alcohol_idx = -1
        self.sterke_idx = -1
        self._editor: Optional[tk.Widget] = None
        self._editor_commit: Optional[Any] = None
        self._hover_iid: Optional[str] = None
        self._row_tag: dict[str, str] = {}

        bottom = tk.Frame(self, bg=RIBBON_BG, highlightthickness=1, highlightbackground=GRID_LINE)
        bottom.pack(fill="x", side="bottom")
        self.lbl_total = tk.Label(bottom, text=f"{total_label}: € 0,00", bg=RIBBON_BG,
                                  font=(*FONT_BASE, "bold"), fg=EXCEL_GREEN_DARK, padx=12, pady=6)
        self.lbl_total.pack(side="right", padx=10)

        tk.Label(bottom, text="Klik op 'betaald' om te wijzigen · dubbelklik op de kostprijs om te bewerken",
                 bg=RIBBON_BG, fg="#666", font=FONT_XS, padx=12).pack(side="left")

        # Tabel eerst aanmaken zodat we er naar kunnen verwijzen
        self.table = DataTree(self, selectmode=selectmode, autofit=True)
        self.table.pack(fill="both", expand=True)

        toolbar = tk.Frame(self, bg="white", padx=8, pady=8)
        toolbar.pack(fill="x", before=self.table)
        ttk.Button(toolbar, text="💶 Alle kostprijzen instellen", command=self._set_all_kostprijs).pack(side="left")

        tree = self.table.tree
        tree.bind("<Button-1>", self._on_click, add="+")
        tree.bind("<Double-1>", self._on_double_click, add="+")
        tree.bind("<Motion>", self._update_cursor, add="+")

        # Workaround voor Tk 8.6.9: tag-kleuren worden anders genegeerd
        style = ttk.Style()
        def _fixed_map(option: str):
            return [e for e in style.map("Treeview", query_opt=option) if e[:2] != ("!disabled", "!selected")]
        style.map("Treeview", foreground=_fixed_map("foreground"), background=_fixed_map("background"))

        tree.tag_configure("paid", background=ROW_PAID)
        tree.tag_configure("unpaid", background=ROW_UNPAID)
        tree.tag_configure("hover_paid", background=ROW_PAID_HOVER)
        tree.tag_configure("hover_unpaid", background=ROW_UNPAID_HOVER)
        tree.bind("<Leave>", lambda _e: self._clear_hover(), add="+")

    # ------------------------------------------------------------------ laden
    def refresh(self) -> None:
        self._close_editor()
        try:
            headers, rows = self.store.read_table(self.sheet_name)
        except StorageError as exc:
            messagebox.showerror("Fout", str(exc), parent=self)
            return

        headers = headers or list(self.default_headers)
        self.headers = headers
        lowered = [h.lower() for h in headers]
        self.kost_idx = next((i for i, h in enumerate(lowered) if "kostprijs" in h), -1)
        self.betaald_idx = next((i for i, h in enumerate(lowered) if "betaald" in h), -1)
        self.alcohol_idx = next((i for i, h in enumerate(lowered) if "alcohol" in h), -1)
        self.sterke_idx = next((i for i, h in enumerate(lowered) if "sterke" in h), -1)
        takken_idx = next((i for i, h in enumerate(lowered) if "takken" in h), -1)

        total = 0.0
        table_rows = []
        paid_flags: list[bool] = []
        self._row_is_leiding: dict[str, bool] = {}

        for excel_row, values in rows:
            iid = str(excel_row)
            if self.sheet_name == SHEET_VISITORS:
                is_editable_drink = True
            else:
                branch = str(values[takken_idx] or "").strip().lower() if 0 <= takken_idx < len(values) else ""
                branch_parts = [p.strip() for p in branch.split(",")]
                is_editable_drink = "leiding" in branch_parts
            self._row_is_leiding[iid] = is_editable_drink

            shown = []
            for idx in range(len(headers)):
                value = values[idx] if idx < len(values) else None
                if idx == self.betaald_idx:
                    is_paid = str(value or "").strip().lower() == "ja"
                    shown.append("✔ Ja" if is_paid else "❌ Nee")
                elif idx in (self.alcohol_idx, self.sterke_idx) and not is_editable_drink:
                    shown.append("")  # Leeg voor gewone leden
                elif idx == self.alcohol_idx or idx == self.sterke_idx:
                    is_yes = str(value or "").strip().lower() == "ja"
                    shown.append("✔ Ja" if is_yes else "❌ Nee")
                elif idx == self.kost_idx:
                    price = parse_price(value)
                    total += price or 0.0
                    shown.append(format_money(price) if price is not None else _display(value))
                else:
                    shown.append(_display(value))
            paid_flags.append(str(values[self.betaald_idx] if 0 <= self.betaald_idx < len(values) else "").strip().lower() == "ja")
            table_rows.append((iid, shown))

        if headers != self._configured_headers:  # niet bij elke refresh: bewaart de kolombreedtes
            self.table.configure_columns(headers, default_width=170)
            self._configured_headers = list(headers)
            self.table.fit_columns()
        self._hover_iid = None
        self.table.fill(table_rows)
        tree = self.table.tree
        self._row_tag = {}
        for iid, paid in zip(tree.get_children(), paid_flags):
            tag = "paid" if paid else "unpaid"
            self._row_tag[iid] = tag
            tree.item(iid, tags=(tag,))
        self.lbl_total.config(text=f"{self.total_label}: {format_money(total)}")

    # -------------------------------------------------------------- bewerken
    def _close_editor(self) -> None:
        if self._editor is not None:
            try:
                self._editor.destroy()
            except tk.TclError:
                pass
            self._editor = None
        self._editor_commit = None

    def _commit_editor(self) -> None:
        if self._editor is not None and self._editor_commit is not None:
            self._editor_commit()

    def _cell_at(self, event: tk.Event) -> Optional[tuple[str, int]]:
        tree = self.table.tree
        if tree.identify_region(event.x, event.y) != "cell":
            return None
        iid = tree.identify_row(event.y)
        col = int(tree.identify_column(event.x).lstrip("#")) - 1
        return (iid, col) if iid and col >= 0 else None

    def _is_yesno_col(self, iid: str, col: int) -> bool:
        """True als de kolom een klikbaar Ja/Nee-veld is."""
        if col == self.betaald_idx and col != -1:
            return True
        if col in (self.alcohol_idx, self.sterke_idx) and col != -1:
            return self._row_is_leiding.get(iid, False) # Alleen klikbaar als het leiding is
        return False

    def _update_cursor(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        clickable = bool(cell and self._is_yesno_col(cell[0], cell[1]))
        self.table.tree.configure(cursor="hand2" if clickable else "")
        self._update_hover(event)

    def _update_hover(self, event: tk.Event) -> None:
        tree = self.table.tree
        iid = tree.identify_row(event.y) or None
        if iid == self._hover_iid:
            return
        self._clear_hover()
        if iid and iid in self._row_tag:
            self._hover_iid = iid
            tree.item(iid, tags=("hover_" + self._row_tag[iid],))

    def _clear_hover(self) -> None:
        if self._hover_iid is not None:
            try:
                base = self._row_tag.get(self._hover_iid)
                if base:
                    self.table.tree.item(self._hover_iid, tags=(base,))
            except tk.TclError:
                pass  # rij bestaat niet meer (na refresh)
            self._hover_iid = None

    def _on_click(self, event: tk.Event) -> None:
        self._commit_editor()
        cell = self._cell_at(event)
        if cell and self._is_yesno_col(cell[0], cell[1]):
            self._choose_paid(event, *cell)

    def _choose_paid(self, event: tk.Event, iid: str, col: int) -> None:
        menu = tk.Menu(self, tearoff=0, font=FONT_BASE)
        menu.add_command(label="✔ Ja", command=lambda: self._save_cell(iid, col, "Ja"))
        menu.add_command(label="❌ Nee", command=lambda: self._save_cell(iid, col, "Nee"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_double_click(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        if cell and cell[1] == self.kost_idx:
            self._edit_price(*cell)

    def _edit_price(self, iid: str, col: int) -> None:
        self._close_editor()
        tree = self.table.tree
        bbox = tree.bbox(iid, f"#{col + 1}")
        if not bbox:
            return
        x, y, width, height = bbox
        current = parse_price(tree.set(iid, f"c{col}"))
        var = tk.StringVar(value=f"{current:.2f}" if current is not None else "0.00")

        entry = ttk.Entry(tree, textvariable=var, font=FONT_SM)
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()
        entry.select_range(0, tk.END)
        self._editor = entry
        finished = {"done": False}

        def commit(_e: Optional[tk.Event] = None) -> None:
            if finished["done"]:
                return
            finished["done"] = True
            text = var.get()
            self._close_editor()
            value = parse_price(text)
            if value is None:
                messagebox.showwarning("Ongeldig bedrag", "Vul een geldig bedrag in, bv. 25 of 25,50.", parent=self)
                return
            self._save_cell(iid, col, value, number_format=MONEY_NUMBER_FORMAT)

        def cancel(_e: Optional[tk.Event] = None) -> None:
            finished["done"] = True
            self._close_editor()

        self._editor_commit = commit
        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", cancel)

    def _save_cell(self, iid: str, col: int, value: Any, number_format: Optional[str] = None) -> None:
        try:
            is_betaling = (col == self.betaald_idx)
            self.store.set_cell(self.sheet_name, int(iid), col + 1, value, is_betaling, number_format)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Fout", f"Opslaan mislukt: {exc}", parent=self)
            return
        self.refresh()

    def _set_all_kostprijs(self) -> None:
        if self.kost_idx == -1:
            messagebox.showwarning("Let op", "Kolom 'Kostprijs' niet gevonden.", parent=self)
            return
        val = simpledialog.askfloat("Alle kostprijzen instellen",
                                    "Voer de nieuwe kostprijs in voor iedereen:",
                                    minvalue=0.0, parent=self)
        if val is None:
            return
        try:
            _, rows = self.store.read_table(self.sheet_name)
            self.store.set_column_value(self.sheet_name, [r for r, _ in rows],
                                        self.kost_idx + 1, val, MONEY_NUMBER_FORMAT)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Fout", f"Instellen mislukt: {exc}", parent=self)
            return
        self.refresh()
