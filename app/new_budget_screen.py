from __future__ import annotations

import csv
import io
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from app.storage import BudgetStore, StorageError
from app.ui import ERROR_RED, EXCEL_GREEN_DARK, FONT_BASE, GRID_LINE, BG_PAGE, TEXT_MUTED, FONT_H1

REQUIRED_COLUMNS = ("voornaam", "achternaam", "takken")

class NewBudgetScreen(tk.Frame):
    def __init__(self, parent: tk.Misc, app_controller):
        super().__init__(parent, bg=BG_PAGE)
        self.app_controller = app_controller
        self.members: Optional[list[list[str]]] = None
        self.var_csv = tk.StringVar()

        card = tk.Frame(self, bg="white", highlightthickness=1, highlightbackground=GRID_LINE, padx=40, pady=30)
        card.place(relx=0.5, rely=0.45, anchor="center", width=620)

        tk.Label(card, text="Nieuwe budgettering aanmaken", bg="white", fg=EXCEL_GREEN_DARK, font=FONT_H1).pack(anchor="w", pady=(0, 15))
        tk.Label(card, text="Kies het CSV-bestand met de ledenlijst:", bg="white", font=(*FONT_BASE, "bold")).pack(anchor="w", pady=(5, 5))

        row = tk.Frame(card, bg="white")
        row.pack(fill="x", pady=(0, 10))
        ttk.Entry(row, textvariable=self.var_csv, state="readonly", font=FONT_BASE).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(row, text="Bladeren…", command=self._browse).pack(side="right")

        self.lbl_info = tk.Label(card, text="Nog geen bestand gekozen.", bg="white", fg=TEXT_MUTED, font=FONT_BASE, justify="left", wraplength=540)
        self.lbl_info.pack(anchor="w", pady=(0, 20))

        buttons = tk.Frame(card, bg="white")
        buttons.pack(fill="x")
        ttk.Button(buttons, text="⬅ Ga terug", command=self.app_controller.show_start_screen).pack(side="left")
        self.btn_ok = ttk.Button(buttons, text="Budget aanmaken & opslaan", command=self._create_budget, state="disabled")
        self.btn_ok.pack(side="right")

    @staticmethod
    def _read_members(path: Path) -> list[list[str]]:
        raw = path.read_bytes()
        text = None
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("Kan bestand niet lezen.")

        first_line = next((line for line in text.splitlines() if line.strip()), "")
        delimiter = max(";,\t", key=first_line.count) if first_line else ";"

        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]
        if not rows:
            raise ValueError("CSV is leeg.")

        header = [h.strip().lower() for h in rows[0]]
        indices = []
        for column in REQUIRED_COLUMNS:
            if column not in header:
                raise ValueError(f"Verplichte kolom '{column.capitalize()}' ontbreekt in het CSV-bestand.")
            indices.append(header.index(column))

        members = []
        for r in rows[1:]:
            values = [r[i] if i < len(r) else "" for i in indices]
            if values[0] or values[1]:
                members.append(values)
        if not members:
            raise ValueError("Er staan geen leden in het CSV-bestand.")
        return members

    def _browse(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Ledenlijst kiezen", filetypes=[("CSV-bestand", "*.csv")])
        if not path:
            return
        self.var_csv.set(path)
        try:
            self.members = self._read_members(Path(path))
        except Exception as exc:
            self.members = None
            self.btn_ok.configure(state="disabled")
            self.lbl_info.configure(text=f"✖ Fout: {exc}", fg=ERROR_RED)
            return
        self.btn_ok.configure(state="normal")
        self.lbl_info.configure(text=f"✔ {len(self.members)} leden ingelezen", fg=EXCEL_GREEN_DARK)

    def _create_budget(self) -> None:
        if not self.members:
            return
        file_path = filedialog.asksaveasfilename(parent=self, title="Nieuwe budgettering opslaan als", defaultextension=".xlsx", filetypes=[("Excel-bestand", "*.xlsx")], initialfile="Budget.xlsx")
        if not file_path:
            return
        try:
            BudgetStore.create_new(file_path, self.members)
        except (StorageError, OSError) as exc:
            messagebox.showerror("Fout", f"Aanmaken mislukt:\n\n{exc}", parent=self)
            return
        self.app_controller.open_budget(Path(file_path))
