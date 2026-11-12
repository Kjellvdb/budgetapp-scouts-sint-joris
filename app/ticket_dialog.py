"""Venster om een ticketfoto door de AI te laten uitlezen, het resultaat na te kijken en op te slaan."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Sequence

from app.common import EXPENSE_COLUMNS, Expense, expense_row_values
from app.expense_dialog import ExpenseDialog
from app.storage import BudgetStore
from app.ticket_ai import MAX_IMAGES, TicketCancelled, extract_expenses_from_image
from app import ticket_ai
from app.ui import ERROR_RED, EXCEL_GREEN_DARK, FONT_BASE, FONT_H2, FONT_SM, TEXT_MUTED, DataTree, center_on_parent


class TicketDialog(tk.Toplevel):
    """Na wait_window() geeft `saved` aan of er uitgaven naar Excel geschreven zijn."""

    def __init__(self, parent: tk.Misc, store: BudgetStore, member_names: Sequence[str]):
        owner = parent.winfo_toplevel()
        super().__init__(owner)
        self.title("Ticket toevoegen via AI")
        self.configure(bg="white")
        self.transient(owner)

        self.store = store
        self.member_names = list(member_names)
        self.rows: list[Expense] = []
        self.saved = False
        self._queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._busy = False
        self._progress = ""
        self._cancel = threading.Event()

        tk.Label(self, text="🤖 Ticket Scannen & Bewerken", bg="white", fg=EXCEL_GREEN_DARK,
                 font=FONT_H2).pack(anchor="w", padx=20, pady=(15, 5))

        btn_box = tk.Frame(self, bg="white", padx=20, pady=15)
        btn_box.pack(fill="x", side="bottom")
        ttk.Button(btn_box, text="💾 Opslaan", command=self._save).pack(side="right")
        ttk.Button(btn_box, text="Annuleren", command=self.destroy).pack(side="right", padx=8)

        file_frame = tk.Frame(self, bg="white", padx=20)
        file_frame.pack(fill="x")
        self.var_path = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.var_path, state="readonly", font=FONT_SM).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_pick = ttk.Button(file_frame, text="📷 Foto's kiezen...", command=self._pick_image)
        self.btn_pick.pack(side="right")

        self.lbl_status = tk.Label(self, text="Selecteer één of meerdere foto's van het ticket om de AI-analyse te starten.",
                                   bg="white", fg=TEXT_MUTED, font=FONT_SM)
        self.lbl_status.pack(anchor="w", padx=20, pady=(8, 0))

        frame = tk.LabelFrame(self, text=" Preview", bg="white", font=(*FONT_BASE, "bold"), padx=10, pady=10)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.table = DataTree(frame, selectmode="extended")
        self.table.configure_columns(EXPENSE_COLUMNS, widths=[100, 220, 70, 110, 120, 140], default_width=120)
        self.table.pack(side="left", fill="both", expand=True)
        tree = self.table.tree
        tree.bind("<Double-1>", self._on_double_click)
        tree.bind("<Delete>", lambda _e: self._delete_rows())

        actions = tk.Frame(frame, bg="white", padx=10)
        actions.pack(side="right", fill="y")
        ttk.Button(actions, text="➕ Rij toevoegen", command=self._add_row).pack(fill="x", pady=2)
        ttk.Button(actions, text="✏️ Bewerken", command=self._edit_row).pack(fill="x", pady=2)
        ttk.Button(actions, text="🗑️ Verwijderen", command=self._delete_rows).pack(fill="x", pady=2)

        center_on_parent(self, owner, 1200, 600)
        self.wait_visibility()
        self.grab_set()

    # ------------------------------------------------------------------- sluiten
    def destroy(self) -> None:
        self._cancel.set()   # stop het uitlezen zodra het venster of de hele app sluit
        super().destroy()

    # ------------------------------------------------------------------ tabel
    def _refresh(self) -> None:
        self.table.fill([(str(i), expense_row_values(e)) for i, e in enumerate(self.rows)])

    def _add_row(self) -> None:
        dlg = ExpenseDialog(self, "Rij toevoegen", member_names=self.member_names)
        self.wait_window(dlg)
        if dlg.result:
            self.rows.append(dlg.result)
            self._refresh()

    def _edit_row(self) -> None:
        selected = self.table.tree.selection()
        if len(selected) != 1:
            messagebox.showwarning("Waarschuwing", "Selecteer één rij om te bewerken.", parent=self)
            return
        idx = int(selected[0])
        dlg = ExpenseDialog(self, "Rij bewerken", expense=self.rows[idx], member_names=self.member_names)
        self.wait_window(dlg)
        if dlg.result:
            self.rows[idx] = dlg.result
            self._refresh()

    def _delete_rows(self) -> None:
        selected = self.table.tree.selection()
        if not selected:
            messagebox.showwarning("Waarschuwing", "Selecteer een rij om te verwijderen.", parent=self)
            return
        for idx in sorted((int(i) for i in selected), reverse=True):
            del self.rows[idx]
        self._refresh()

    def _on_double_click(self, event: tk.Event) -> None:
        tree = self.table.tree
        if tree.identify_region(event.x, event.y) in ("heading", "separator"):
            return
        if tree.identify_row(event.y):
            self._edit_row()

    # --------------------------------------------------------------------- AI
    def _pick_image(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self, title="Selecteer ticketfoto's (meerdere mogelijk met Ctrl/Shift)",
            filetypes=[("Afbeeldingen", "*.png *.jpg *.jpeg")],
        )
        if not paths:
            return
        paths = sorted(paths, key=lambda p: Path(p).name.lower())
        if len(paths) > MAX_IMAGES:
            messagebox.showwarning("Te veel foto's", f"Kies maximaal {MAX_IMAGES} foto's per ticket.", parent=self)
            return

        names = ", ".join(Path(p).name for p in paths)
        self.var_path.set(f"{len(paths)} foto's: {names}" if len(paths) > 1 else paths[0])
        self.lbl_status.config(
            text=f"⏳ AI-agent leest {len(paths)} foto('s) als één ticket uit...", fg=EXCEL_GREEN_DARK)
        self.btn_pick.state(["disabled"])
        self._busy = True
        self._progress = ""

        cancel = self._cancel = threading.Event()   # nieuw signaal per uitlezing

        def work() -> None:
            try:
                self._queue.put(("ok", extract_expenses_from_image(
                    list(paths), progress=self._set_progress, cancel=cancel)))
            except TicketCancelled:
                pass  # venster is gesloten: niets meer doen
            except Exception as exc:  # noqa: BLE001 - elke fout moet bij de gebruiker terechtkomen
                self._queue.put(("err", str(exc) or exc.__class__.__name__))

        threading.Thread(target=work, daemon=False).start()
        self._poll()

    def _set_progress(self, text: str) -> None:
        self._progress = text  # wordt vanuit de achtergrondthread gezet en door _poll getoond

    def _poll(self) -> None:
        """Wacht op het resultaat van de achtergrondthread (alleen de hoofdthread raakt de UI aan)."""
        try:
            if not self.winfo_exists():
                return
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                if self._busy:
                    if self._progress:
                        self.lbl_status.config(text=self._progress, fg=EXCEL_GREEN_DARK)
                    self.after(150, self._poll)
                return
            self._busy = False
            self.btn_pick.state(["!disabled"])
            if kind == "ok":
                self.rows = list(payload)  # type: ignore[arg-type]
                self._refresh()
                warning = ticket_ai.LAST_WARNING
                if warning:
                    self.lbl_status.config(text=f"⚠ {len(self.rows)} items uitgelezen. {warning}", fg=ERROR_RED)
                else:
                    self.lbl_status.config(text=f"✔ {len(self.rows)} items succesvol uitgelezen!", fg=EXCEL_GREEN_DARK)
            else:
                self.lbl_status.config(text="✖ Fout bij AI-analyse.", fg=ERROR_RED)
                messagebox.showerror("AI Fout", f"Kan ticket niet automatisch uitlezen:\n{payload}", parent=self)
        except tk.TclError:
            pass  # venster werd gesloten tijdens het analyseren

    # ---------------------------------------------------------------- opslaan
    def _save(self) -> None:
        if not self.rows:
            messagebox.showerror("Fout", "Geen items gevonden om op te slaan.", parent=self)
            return
        try:
            self.store.add_expenses(self.rows)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Fout", f"Opslaan mislukt: {exc}", parent=self)
            return
        self.saved = True
        self.destroy()
