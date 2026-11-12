from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Optional

from app.common import EXPENSE_COLUMNS, Expense, expense_row_values, format_money
from app.expense_dialog import ExpenseDialog
from app.storage import BudgetStore, StorageError
from app.ticket_dialog import TicketDialog
from app.ui import ERROR_RED, FONT_BASE, FONT_SM, RIBBON_BG, GRID_LINE, TEXT_MUTED, DataTree

class ExpensesTab(tk.Frame):
    COLUMN_WIDTHS = [110, 300, 80, 130, 140, 220, 110]

    def __init__(self, parent: tk.Misc, store: BudgetStore):
        super().__init__(parent, bg="white")
        self.store = store
        self._by_row: dict[int, Expense] = {}

        toolbar = tk.Frame(self, bg="white", padx=8, pady=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="➕ Nieuw ticket toevoegen (AI)", command=self._add_from_ticket).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="➕ Handmatig toevoegen", command=self._add_manual).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="✏️ Bewerken", command=self._edit_selected).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="🗑️ Verwijderen", command=self._delete_selected).pack(side="left")

        bottom = tk.Frame(self, bg=RIBBON_BG, highlightthickness=1, highlightbackground=GRID_LINE)
        bottom.pack(fill="x", side="bottom")
        self.lbl_total = tk.Label(bottom, text="Totale uitgaven: € 0,00", bg=RIBBON_BG, font=(*FONT_BASE, "bold"), fg=ERROR_RED, padx=12, pady=6)
        self.lbl_total.pack(side="right", padx=10)
        self.lbl_personal = tk.Label(bottom, text="", bg=RIBBON_BG, fg=TEXT_MUTED, font=FONT_SM, padx=12)
        self.lbl_personal.pack(side="left")

        self.table = DataTree(self, selectmode="extended")
        self.table.configure_columns(EXPENSE_COLUMNS, widths=self.COLUMN_WIDTHS)
        self.table.pack(fill="both", expand=True)

        tree = self.table.tree
        tree.bind("<Double-1>", self._on_double_click)
        tree.bind("<Delete>", lambda _e: self._delete_selected())
        tree.bind("<Control-a>", self._select_all)

        self.betaald_idx = EXPENSE_COLUMNS.index("Betaald?")
        tree.bind("<Button-1>", self._on_click, add="+")
        tree.bind("<Motion>", self._update_cursor, add="+")

    def refresh(self) -> None:
        try:
            expenses = self.store.read_expenses()
        except StorageError as exc:
            messagebox.showerror("Fout", str(exc), parent=self)
            return
        expenses.sort(key=lambda e: (e.datum or datetime.min, e.row or 0))
        self._by_row = {e.row: e for e in expenses if e.row}
        self.table.fill([(str(e.row), expense_row_values(e)) for e in expenses])
        counted = sum(e.prijs for e in expenses if e.counts_in_total)
        self.lbl_total.config(text=f"Totale uitgaven: {format_money(counted)}")

    def _member_names(self) -> list[str]:
        try:
            return self.store.member_names()
        except StorageError:
            return []

    def _add_manual(self) -> None:
        dlg = ExpenseDialog(self, "Handmatig uitgave toevoegen", member_names=self._member_names())
        self.wait_window(dlg)
        if not dlg.result:
            return
        try:
            self.store.add_expenses([dlg.result])
        except Exception as exc:
            messagebox.showerror("Fout", f"Opslaan mislukt: {exc}", parent=self)
            return
        self.refresh()

    def _add_from_ticket(self) -> None:
        dlg = TicketDialog(self, self.store, self._member_names())
        self.wait_window(dlg)
        if dlg.saved:
            self.refresh()

    def _edit_selected(self) -> None:
        selected = self.table.tree.selection()
        if len(selected) != 1:
            messagebox.showwarning("Waarschuwing", "Selecteer één uitgave om te bewerken.", parent=self)
            return
        expense = self._by_row.get(int(selected[0]))
        if expense is None:
            return
        dlg = ExpenseDialog(self, "Uitgave bewerken", expense=expense, member_names=self._member_names())
        self.wait_window(dlg)
        if not dlg.result:
            return
        try:
            self.store.update_expense(dlg.result)
        except Exception as exc:
            messagebox.showerror("Fout", f"Bewerken mislukt: {exc}", parent=self)
            return
        self.refresh()

    def _delete_selected(self) -> None:
        selected = self.table.tree.selection()
        if not selected:
            messagebox.showwarning("Waarschuwing", "Selecteer een uitgave om te verwijderen.", parent=self)
            return
        n = len(selected)
        question = ("Weet je zeker dat je deze uitgave wilt verwijderen?" if n == 1 else f"Weet je zeker dat je deze {n} uitgaven wilt verwijderen?")
        if not messagebox.askyesno("Bevestigen", question, parent=self):
            return
        try:
            self.store.delete_expenses([int(i) for i in selected])
        except Exception as exc:
            messagebox.showerror("Fout", f"Verwijderen mislukt: {exc}", parent=self)
            return
        self.refresh()

    def _on_double_click(self, event: tk.Event) -> None:
        tree = self.table.tree
        if tree.identify_region(event.x, event.y) in ("heading", "separator"):
            return
        if tree.identify_row(event.y):
            self._edit_selected()

    def _select_all(self, _event: tk.Event) -> str:
        tree = self.table.tree
        tree.selection_set(tree.get_children())
        return "break"

    def _paid_cell(self, event: tk.Event) -> Optional[Expense]:
        tree = self.table.tree
        if tree.identify_region(event.x, event.y) != "cell":
            return None
        if int(tree.identify_column(event.x).lstrip("#")) - 1 != self.betaald_idx:
            return None
        iid = tree.identify_row(event.y)
        expense = self._by_row.get(int(iid)) if iid else None
        return expense if expense is not None and expense.is_personal else None

    def _update_cursor(self, event: tk.Event) -> None:
        self.table.tree.configure(cursor="hand2" if self._paid_cell(event) else "")

    def _on_click(self, event: tk.Event) -> None:
        expense = self._paid_cell(event)
        if expense is None:
            return
        menu = tk.Menu(self, tearoff=0, font=FONT_BASE)
        menu.add_command(label="✔ Ja", command=lambda: self._set_paid(expense, True))
        menu.add_command(label="❌ Nee", command=lambda: self._set_paid(expense, False))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _set_paid(self, expense: Expense, paid: bool) -> None:
        try:
            self.store.update_expense(replace(expense, betaald=paid))
        except Exception as exc:
            messagebox.showerror("Fout", f"Opslaan mislukt: {exc}", parent=self)
            return
        self.refresh()
