from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from app.ui import EXCEL_GREEN_DARK, FONT_H3, FONT_HERO, GRID_LINE, BG_PAGE, TEXT_MUTED


class StartScreen(tk.Frame):
    def __init__(self, parent: tk.Misc, app_controller):
        super().__init__(parent, bg=BG_PAGE)
        self.app_controller = app_controller

        card = tk.Frame(self, bg="white", highlightthickness=1, highlightbackground=GRID_LINE, padx=50, pady=36)
        card.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(card, text="Budgetapp", bg="white", fg=EXCEL_GREEN_DARK, font=FONT_HERO).pack()
        tk.Label(card, text="Wat wil je doen?", bg="white", fg=TEXT_MUTED, font=FONT_H3).pack(pady=(2, 24))

        ttk.Button(card, text="📄  Nieuwe budgettering aanmaken", style="Big.TButton",
                   command=self.app_controller.show_new_budget_screen, width=34).pack(pady=(0, 12))
        ttk.Button(card, text="📂  Bestaande budgettering openen", style="Big.TButton",
                   command=self.open_existing_budget, width=34).pack()

    def open_existing_budget(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self, title="Budgettering openen", filetypes=[("Excel-bestand", "*.xlsx")])
        if file_path:
            self.app_controller.open_budget(Path(file_path))
