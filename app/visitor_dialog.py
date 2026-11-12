"""Dialoog om één persoon aan de fourage- en bezoekerslijst toe te voegen."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from app.common import format_money, parse_price
from app.ui import EXCEL_GREEN_DARK, FONT_BASE, FONT_H3, center_on_parent


class VisitorDialog(tk.Toplevel):
    """Na wait_window() bevat `result` (voornaam, achternaam, kostprijs, betaald) of None bij annuleren."""

    WIDTH, HEIGHT = 520, 520

    def __init__(self, parent: tk.Misc, title: str = "Persoon toevoegen",
                 visitor: Optional[tuple[str, str, float, bool, bool, bool]] = None):
        owner = parent.winfo_toplevel()
        super().__init__(owner)
        self.title(title)
        self.configure(bg="white")
        self.transient(owner)
        self.resizable(False, False)
        self.result: Optional[tuple[str, str, float, bool, bool, bool]] = None

        self.v_voornaam = tk.StringVar(value=visitor[0] if visitor else "")
        self.v_achternaam = tk.StringVar(value=visitor[1] if visitor else "")
        self.v_prijs = tk.StringVar(value=format_money(visitor[2]) if visitor else format_money(0.0))
        self.v_betaald = tk.StringVar(value="Ja" if visitor and visitor[3] else "Nee")
        self.v_alcohol = tk.StringVar(value="Ja" if visitor and visitor[4] else "Nee")
        self.v_sterke_drank = tk.StringVar(value="Ja" if visitor and visitor[5] else "Nee")

        tk.Label(self, text="Persoon toevoegen", bg="white", fg=EXCEL_GREEN_DARK,
                 font=FONT_H3).pack(pady=10)
        form = tk.Frame(self, bg="white", padx=20)
        form.pack(fill="x", expand=True)

        def row(label: str) -> tk.Frame:
            frame = tk.Frame(form, bg="white", pady=4)
            frame.pack(fill="x")
            tk.Label(frame, text=label, bg="white", width=22, anchor="w", font=FONT_BASE).pack(side="left")
            return frame

        font = FONT_BASE
        self.entry_first = ttk.Entry(row("Voornaam:"), textvariable=self.v_voornaam, font=font)
        self.entry_first.pack(side="right", fill="x", expand=True)
        ttk.Entry(row("Achternaam:"), textvariable=self.v_achternaam, font=font).pack(side="right", fill="x", expand=True)
        ttk.Entry(row("Kostprijs weekend/kamp:"), textvariable=self.v_prijs, font=font).pack(
            side="right", fill="x", expand=True)
        ttk.Combobox(row("Weekend/kamp betaald?"), textvariable=self.v_betaald, values=["Ja", "Nee"],
                     state="readonly", font=font).pack(side="right", fill="x", expand=True)
        ttk.Combobox(row("Alcohol gedronken?"), textvariable=self.v_alcohol, values=["Ja", "Nee"],
                     state="readonly", font=font).pack(side="right", fill="x", expand=True)
        ttk.Combobox(row("Sterke drank gedronken?"), textvariable=self.v_sterke_drank, values=["Ja", "Nee"],
                     state="readonly", font=font).pack(side="right", fill="x", expand=True)

        btn_box = tk.Frame(self, bg="white", pady=15, padx=20)
        btn_box.pack(fill="x", side="bottom")
        ttk.Button(btn_box, text="Opslaan", command=self._save).pack(side="right")
        ttk.Button(btn_box, text="Annuleren", command=self.destroy).pack(side="right", padx=8)

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())

        center_on_parent(self, owner, self.WIDTH, self.HEIGHT)
        self.wait_visibility()
        self.grab_set()
        self.entry_first.focus_set()

    def _save(self) -> None:
        voornaam = self.v_voornaam.get().strip()
        achternaam = self.v_achternaam.get().strip()
        if not voornaam and not achternaam:
            messagebox.showwarning("Waarschuwing", "Vul minstens een voornaam of achternaam in.", parent=self)
            return
        prijs = parse_price(self.v_prijs.get())
        if prijs is None:
            messagebox.showwarning("Waarschuwing", "Ongeldige prijs. Gebruik bv. 25 of €25,50.", parent=self)
            return
        self.result = (voornaam, achternaam, prijs,
                       self.v_betaald.get() == "Ja",
                       self.v_alcohol.get() == "Ja",
                       self.v_sterke_drank.get() == "Ja")
        self.destroy()
