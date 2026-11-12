from __future__ import annotations
import tkinter as tk
from tkinter import messagebox, ttk

from app.common import SHEET_VISITORS, VISITOR_HEADERS, parse_price
from app.income_screen import IncomeTab
from app.storage import BudgetStore, StorageError
from app.visitor_dialog import VisitorDialog


class VisitorsTab(IncomeTab):
    def __init__(self, parent: tk.Misc, store: BudgetStore):
        super().__init__(parent, store, sheet_name=SHEET_VISITORS,
                         total_label="Totale inkomsten fourage & bezoekers",
                         default_headers=VISITOR_HEADERS,
                         selectmode="extended")
        self._by_row: dict[int, tuple[str, str, float, bool, bool, bool]] = {}

        toolbar = tk.Frame(self, bg="white", padx=8, pady=8)
        toolbar.pack(fill="x", before=self.table)
        ttk.Button(toolbar, text="➕ Persoon toevoegen", command=self._add_person).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="✏️ Bewerken", command=self._edit_selected).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="🗑️ Verwijderen", command=self._delete_selected).pack(side="left")

        tree = self.table.tree
        tree.bind("<Double-1>", self._on_double_click_row, add="+")
        tree.bind("<Delete>", lambda _e: self._delete_selected(), add="+")
        tree.bind("<Control-a>", self._select_all, add="+")

    def refresh(self) -> None:
        super().refresh()
        try:
            _, rows = self.store.read_table(self.sheet_name)
        except StorageError:
            return
        self._by_row = {}
        for excel_row, values in rows:
            self._by_row[excel_row] = (
                str(values[0] if len(values) > 0 and values[0] is not None else "").strip(),
                str(values[1] if len(values) > 1 and values[1] is not None else "").strip(),
                parse_price(values[2]) or 0.0 if len(values) > 2 else 0.0,
                str(values[3] if len(values) > 3 and values[3] is not None else "").strip().lower() == "ja",
                str(values[4] if len(values) > 4 and values[4] is not None else "").strip().lower() == "ja",
                str(values[5] if len(values) > 5 and values[5] is not None else "").strip().lower() == "ja",
            )

    def _add_person(self) -> None:
        dlg = VisitorDialog(self, title="Persoon toevoegen")
        self.wait_window(dlg)
        if not dlg.result:
            return
        try:
            voornaam, achternaam, prijs, betaald, alcohol, sterke_drank = dlg.result
            self.store.add_visitor(voornaam, achternaam, prijs, betaald, alcohol, sterke_drank)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Fout", f"Opslaan mislukt: {exc}", parent=self)
            return
        self.refresh()

    def _edit_selected(self) -> None:
        selected = self.table.tree.selection()
        if len(selected) != 1:
            messagebox.showwarning("Waarschuwing", "Selecteer één persoon om te bewerken.", parent=self)
            return
        row_id = int(selected[0])
        visitor = self._by_row.get(row_id)
        if visitor is None:
            return
        dlg = VisitorDialog(self, title="Persoon bewerken", visitor=visitor)
        self.wait_window(dlg)
        if not dlg.result:
            return
        try:
            voornaam, achternaam, prijs, betaald, alcohol, sterke_drank = dlg.result
            self.store.update_visitor(row_id, voornaam, achternaam, prijs, betaald, alcohol, sterke_drank)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Fout", f"Bewerken mislukt: {exc}", parent=self)
            return
        self.refresh()

    def _delete_selected(self) -> None:
        selected = self.table.tree.selection()
        if not selected:
            messagebox.showwarning("Waarschuwing", "Selecteer een persoon om te verwijderen.", parent=self)
            return
        n = len(selected)
        question = ("Weet je zeker dat je deze persoon wilt verwijderen?" if n == 1
                    else f"Weet je zeker dat je deze {n} personen wilt verwijderen?")
        if not messagebox.askyesno("Bevestigen", question, parent=self):
            return
        try:
            self.store.delete_visitors([int(i) for i in selected])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Fout", f"Verwijderen mislukt: {exc}", parent=self)
            return
        self.refresh()

    def _on_double_click_row(self, event: tk.Event) -> None:
        tree = self.table.tree
        if tree.identify_region(event.x, event.y) in ("heading", "separator"):
            return
        if tree.identify_row(event.y):
            self._edit_selected()
            return "break"

    def _select_all(self, _event: tk.Event) -> str:
        tree = self.table.tree
        tree.selection_set(tree.get_children())
        return "break"
