from __future__ import annotations

import ctypes
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Callable, Optional
import os, subprocess, platform

from app.budget_screen import BudgetScreen
from app.new_budget_screen import NewBudgetScreen
from app.start_screen import StartScreen
from app.storage import BudgetStore, StorageError
from app.ui import APP_TITLE, EXCEL_GREEN, FONT_BASE, apply_styles

class BudgetApp(tk.Tk):
    def __init__(self) -> None:
        self._enable_dpi_awareness()  # moet vóór het aanmaken van het venster
        super().__init__()
        self.title(APP_TITLE)
        self.minsize(1400, 800)
        self.configure(bg="white")
        if platform.system() == "Windows":
            self.state("zoomed")
        elif platform.system() == "Darwin":
            self.attributes("-zoomed", True)
        else:
            self.attributes("-zoomed", True)

        self.path: Optional[Path] = None
        apply_styles(self)
        self._build_title_bar()

        self.container = tk.Frame(self, bg="white")
        self.container.pack(fill=tk.BOTH, expand=True)

        self.current_screen: Optional[tk.Frame] = None
        self.show_start_screen()

    @staticmethod
    def _enable_dpi_awareness() -> None:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # geen Windows of niet ondersteund
            pass

    def _build_title_bar(self) -> None:
        bar = tk.Frame(self, bg=EXCEL_GREEN, height=34)
        bar.pack(fill="x")
        self.lbl_title = tk.Label(bar, text=APP_TITLE, bg=EXCEL_GREEN, fg="white",
                                  font=(*FONT_BASE, "bold"), anchor="w", padx=12)
        self.lbl_title.pack(fill="both", expand=True, pady=6)

    def _show(self, build: Callable[[], tk.Frame], subtitle: str) -> None:
        screen = build()  # eerst bouwen: als dat mislukt blijft het vorige scherm staan
        if self.current_screen is not None:
            self.current_screen.destroy()
        self.current_screen = screen
        self.lbl_title.configure(text=f"{APP_TITLE}   |   {subtitle}")
        screen.pack(fill=tk.BOTH, expand=True)

    def show_start_screen(self) -> None:
        self.path = None
        self._show(lambda: StartScreen(self.container, self), "Geen budgettering geopend")

    def open_excel_file(self) -> None:
        if self.path is None:
            messagebox.showerror("Geen budgettering geopend", "Er is geen budgettering geopend om in Excel te openen.", parent=self)
            return
        try:
            if platform.system() == "Windows":
                os.startfile(self.path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.path])
            else:
                subprocess.Popen(["xdg-open", self.path])
        except Exception as exc:
            messagebox.showerror("Fout", f"Kan bestand niet openen: {exc}", parent=self)

    def show_new_budget_screen(self) -> None:
        self._show(lambda: NewBudgetScreen(self.container, self), "Nieuw budget aanmaken")

    def open_budget(self, path: Path, tab: str = "income") -> None:
        """Opent een bestaand budget. tab = 'income' of 'expenses'."""
        path = Path(path)
        try:
            BudgetStore(path).check()
        except StorageError as exc:
            messagebox.showerror("Kan bestand niet openen", str(exc), parent=self)
            return
        self.path = path
        self._show(lambda: BudgetScreen(self.container, self, path, tab), path.name)
