"""Dialoog om één uitgave toe te voegen of te bewerken, met naam-autocomplete voor 'Persoonlijk'."""
from __future__ import annotations

import difflib
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Optional, Sequence

from app.common import CATEGORIES, DATE_FORMAT, Expense, format_money, parse_date, parse_price
from app.ui import EXCEL_GREEN_DARK, FONT_BASE, FONT_H3, FONT_SM, GRID_LINE, ROW_SELECTED, center_on_parent


class NameAutocomplete(ttk.Entry):
    """Tekstveld dat tijdens het typen de 3 best passende namen toont als klikbare lijst."""

    def __init__(self, parent: tk.Misc, textvariable: tk.StringVar, names: Sequence[str],
                 max_suggestions: int = 3, **kw):
        super().__init__(parent, textvariable=textvariable, **kw)
        self.var = textvariable
        self.names = list(names)
        self.max_suggestions = max_suggestions
        self._listbox: Optional[tk.Listbox] = None

        self.bind("<KeyRelease>", self._on_key_release, add="+")
        self.bind("<Down>", lambda e: self._move(+1), add="+")
        self.bind("<Up>", lambda e: self._move(-1), add="+")
        self.bind("<Return>", self._on_return, add="+")
        self.bind("<Escape>", self._on_escape, add="+")
        self.bind("<FocusOut>", lambda e: self.after(150, self._hide_if_unfocused), add="+")

    # --------------------------------------------------------------- zoeken
    def best_matches(self, text: str) -> list[str]:
        t = text.strip().lower()
        if not t:
            return []
        scored = []
        for name in self.names:
            nl = name.lower()
            words = nl.split()
            if nl.startswith(t):
                score = 0.0
            elif any(w.startswith(t) for w in words):
                score = 1.0
            elif t in nl:
                score = 2.0
            else:
                ratio = max([difflib.SequenceMatcher(None, t, nl).ratio()]
                            + [difflib.SequenceMatcher(None, t, w).ratio() for w in words])
                if ratio < 0.7:
                    continue
                score = 3.0 + (1.0 - ratio)
            scored.append((score, nl, name))
        scored.sort()
        return [name for _s, _n, name in scored[: self.max_suggestions]]

    # ------------------------------------------------------------ keuzelijst
    def _ensure_listbox(self) -> tk.Listbox:
        if self._listbox is None:
            self._listbox = tk.Listbox(
                self.winfo_toplevel(), height=self.max_suggestions, font=FONT_BASE,
                activestyle="none", exportselection=False, takefocus=0,
                highlightthickness=1, highlightbackground=GRID_LINE,
                selectbackground=ROW_SELECTED, selectforeground="black",
            )
            self._listbox.bind("<Button-1>", self._on_click)
        return self._listbox

    def _show(self, suggestions: list[str]) -> None:
        lb = self._ensure_listbox()
        lb.delete(0, "end")
        for s in suggestions:
            lb.insert("end", s)
        lb.configure(height=len(suggestions))
        top = self.winfo_toplevel()
        x = self.winfo_rootx() - top.winfo_rootx()
        y = self.winfo_rooty() - top.winfo_rooty() + self.winfo_height()
        lb.place(x=x, y=y, width=self.winfo_width())
        lb.lift()

    def hide(self) -> None:
        if self._listbox is not None:
            self._listbox.place_forget()

    def _visible(self) -> bool:
        return self._listbox is not None and self._listbox.winfo_ismapped()

    def _hide_if_unfocused(self) -> None:
        try:
            if self.focus_get() is not self._listbox:
                self.hide()
        except (KeyError, tk.TclError):
            self.hide()

    def _choose(self, name: str) -> None:
        self.var.set(name)
        self.hide()
        self.focus_set()
        self.icursor("end")

    # ------------------------------------------------------------ gebeurtenissen
    def _on_key_release(self, event: tk.Event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab", "Left", "Right",
                            "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        text = self.var.get()
        matches = self.best_matches(text)
        if not matches or (len(matches) == 1 and matches[0].lower() == text.strip().lower()):
            self.hide()
        else:
            self._show(matches)

    def _move(self, step: int):
        if not self._visible():
            return None
        lb = self._listbox
        cur = lb.curselection()
        nxt = 0 if not cur else min(max(cur[0] + step, 0), lb.size() - 1)
        lb.selection_clear(0, "end")
        lb.selection_set(nxt)
        return "break"

    def _on_return(self, _event: tk.Event):
        if self._visible():
            cur = self._listbox.curselection()
            self._choose(self._listbox.get(cur[0] if cur else 0))
            return "break"
        return None

    def _on_escape(self, _event: tk.Event):
        if self._visible():
            self.hide()
            return "break"
        return None

    def _on_click(self, event: tk.Event):
        idx = self._listbox.nearest(event.y)
        if 0 <= idx < self._listbox.size():
            self._choose(self._listbox.get(idx))
        return "break"


class ExpenseDialog(tk.Toplevel):
    """Na wait_window() bevat `result` een Expense, of None bij annuleren."""

    WIDTH, HEIGHT = 540, 580

    def __init__(self, parent: tk.Misc, title: str, expense: Optional[Expense] = None,
                 member_names: Optional[Sequence[str]] = None):
        owner = parent.winfo_toplevel()
        super().__init__(owner)
        self.title(title)
        self.configure(bg="white")
        self.transient(owner)
        self.resizable(False, False)

        self.result: Optional[Expense] = None
        self._row = expense.row if expense else None
        member_names = list(member_names or [])

        e = expense
        self.v_datum = tk.StringVar(value=(e.datum_display if e and e.datum_display else datetime.now().strftime(DATE_FORMAT)))
        self.v_item = tk.StringVar(value=e.item if e else "")
        self.v_aantal = tk.StringVar(value=e.aantal if e and e.aantal else "1")
        self.v_prijs = tk.StringVar(value=format_money(e.prijs if e else 0.0))
        self.v_categorie = tk.StringVar(value=e.categorie if e and e.categorie in CATEGORIES else "Algemeen")
        self.v_naam = tk.StringVar(value=e.naam if e else "")
        self.v_betaald = tk.StringVar(value="Ja" if e and e.betaald else "Nee")

        tk.Label(self, text=title, bg="white", fg=EXCEL_GREEN_DARK, font=FONT_H3).pack(pady=10)
        form = tk.Frame(self, bg="white", padx=20)
        form.pack(fill="x", expand=True)

        def row(label: str) -> tk.Frame:
            frame = tk.Frame(form, bg="white", pady=4)
            frame.pack(fill="x")
            tk.Label(frame, text=label, bg="white", width=22, anchor="w", font=FONT_BASE).pack(side="left")
            return frame

        font = FONT_SM
        ttk.Entry(row("Datum:"), textvariable=self.v_datum, font=font).pack(side="right", fill="x", expand=True)
        self.entry_item = ttk.Entry(row("Item:"), textvariable=self.v_item, font=font)
        self.entry_item.pack(side="right", fill="x", expand=True)
        ttk.Entry(row("Aantal:"), textvariable=self.v_aantal, font=font).pack(side="right", fill="x", expand=True)
        ttk.Entry(row("Totale prijs:"), textvariable=self.v_prijs, font=font).pack(side="right", fill="x", expand=True)

        combo = ttk.Combobox(row("Categorie:"), textvariable=self.v_categorie, values=CATEGORIES,
                             state="readonly", font=font)
        combo.pack(side="right", fill="x", expand=True)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._toggle_name_field())

        self.name_row = row("Naam (indien Persoonlijk):")
        self.name_entry = NameAutocomplete(self.name_row, self.v_naam, member_names, font=font)
        self.name_entry.pack(side="right", fill="x", expand=True)

        self.betaald_row = row("Betaald?")
        ttk.Combobox(self.betaald_row, textvariable=self.v_betaald, values=["Ja", "Nee"],
                     state="readonly", font=font).pack(side="right", fill="x", expand=True)

        btn_box = tk.Frame(self, bg="white", pady=15, padx=20)
        btn_box.pack(fill="x", side="bottom")
        ttk.Button(btn_box, text="Opslaan", command=self._save).pack(side="right")
        ttk.Button(btn_box, text="Annuleren", command=self.destroy).pack(side="right", padx=8)

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())

        self._toggle_name_field(focus=False)
        center_on_parent(self, owner, self.WIDTH, self.HEIGHT)
        self.wait_visibility()
        self.grab_set()
        self.entry_item.focus_set()

    def _toggle_name_field(self, focus: bool = True) -> None:
        if self.v_categorie.get() == "Persoonlijk":
            self.name_row.pack(fill="x", pady=4)
            self.betaald_row.pack(fill="x", pady=4)
            if focus:
                self.name_entry.focus_set()
        else:
            self.name_entry.hide()
            self.name_row.pack_forget()
            self.betaald_row.pack_forget()
            self.v_naam.set("")
            self.v_betaald.set("Nee")

    def _save(self) -> None:
        categorie = self.v_categorie.get()
        naam = self.v_naam.get().strip() if categorie == "Persoonlijk" else ""

        item = self.v_item.get().strip()
        if not item:
            messagebox.showwarning("Waarschuwing", "Vul een item in.", parent=self)
            return
        datum = parse_date(self.v_datum.get())
        if datum is None:
            messagebox.showwarning("Waarschuwing", "Ongeldige datum. Gebruik het formaat DD/MM/JJJJ.", parent=self)
            return
        prijs = parse_price(self.v_prijs.get())
        if prijs is None:
            messagebox.showwarning("Waarschuwing", "Ongeldige prijs. Gebruik bv. 2.50 of €2,50.", parent=self)
            return
        if categorie == "Persoonlijk" and not naam:
            messagebox.showwarning("Waarschuwing", "Selecteer of vul een naam in voor de categorie Persoonlijk.", parent=self)
            return

        self.result = Expense(
            datum=datum, item=item, aantal=self.v_aantal.get().strip() or "1",
            prijs=prijs, categorie=categorie, naam=naam, row=self._row,
            betaald=bool(naam) and self.v_betaald.get() == "Ja",
        )
        self.destroy()
