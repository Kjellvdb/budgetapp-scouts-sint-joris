from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from app.expenses_screen import ExpensesTab
from app.income_screen import IncomeTab
from app.storage import BudgetStore
from app.summary_screen import SummaryTab
from app.visitor_screen import VisitorsTab
from app.ui import GRID_LINE, RIBBON_BG

class BudgetScreen(tk.Frame):
    def __init__(self, parent: tk.Misc, app_controller, path: Path, start_tab: str = "income"):
        super().__init__(parent, bg="white")
        self.app_controller = app_controller
        self.store = BudgetStore(path)

        ribbon = tk.Frame(self, bg=RIBBON_BG, highlightthickness=1, highlightbackground=GRID_LINE)
        ribbon.pack(fill="x")
        ttk.Button(ribbon, text="🏠 Startscherm", command=app_controller.show_start_screen).pack(side="left", padx=(8, 0), pady=4)
        ttk.Button(ribbon, text="📊 Open in Excel", command=app_controller.open_excel_file).pack(side="left", padx=(8, 0), pady=4)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=4, pady=4)

        self.income_tab = IncomeTab(self.notebook, self.store)
        self.expenses_tab = ExpensesTab(self.notebook, self.store)
        self.visitors_tab = VisitorsTab(self.notebook, self.store)
        self.summary_tab = SummaryTab(self.notebook, self.store)
        self.notebook.add(self.income_tab, text="Ledenlijst")
        self.notebook.add(self.visitors_tab, text="Fourage & Bezoekerslijst")
        self.notebook.add(self.expenses_tab, text="Uitgaven")
        self.notebook.add(self.summary_tab, text="Budgetering")

        active = self.expenses_tab if start_tab == "expenses" else self.income_tab
        self.notebook.select(active)
        active.refresh()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, _event: tk.Event) -> None:
        tab = self.nametowidget(self.notebook.select())
        tab.refresh()
