from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, Sequence

APP_TITLE = "Budgetapp Scouts Sint-Joris"
EXCEL_GREEN = "#217346"
EXCEL_GREEN_DARK = "#185C37"
RIBBON_BG = "#F3F3F3"
GRID_LINE = "#D4D4D4"
ERROR_RED = "#B00020"
ROW_ODD = "white"
ROW_EVEN = "#F5F9F2"
ROW_HOVER = "#E8F0FE"
ROW_SELECTED = "#CDE6D6"
ROW_PAID = "#E2F4E6"
ROW_UNPAID = "#FBE3E3"
ROW_PAID_HOVER = "#C9EBD2"
ROW_UNPAID_HOVER = "#F5C6C6"
BG_PAGE = "#F7F7F7"
TEXT_MUTED = "#666666"
TEXT_DISABLED = "#AAAAAA"
TABLE_HEADER_BG = "#E8F3EC"

FONT = "Calibri"
FONT_XS = (FONT, 11)
FONT_SM = (FONT, 12)
FONT_BASE = (FONT, 14)
FONT_H3 = (FONT, 16, "bold")
FONT_H2 = (FONT, 18, "bold")
FONT_H1 = (FONT, 22, "bold")
FONT_HERO = (FONT, 26, "bold")

def apply_styles(root: tk.Misc) -> None:
    style = ttk.Style(root)
    style.configure("TButton", font=(FONT, 14))
    style.configure("TLabel", font=(FONT, 14))
    style.configure("TNotebook.Tab", font=(FONT, 14), padding=(20, 6))
    style.configure("Treeview", font=(FONT, 14), rowheight=28)
    style.configure("Treeview.Heading", font=(FONT, 14, "bold"))
    style.configure("Big.TButton", background="white", foreground=EXCEL_GREEN_DARK, padding=(20, 16), font=(FONT, 14, "bold"), bordercolor=EXCEL_GREEN)

    def fixed_map(option: str):
        return [e for e in style.map("Treeview", query_opt=option) if e[:2] != ("!disabled", "!selected")]

    style.map("Treeview", foreground=[("selected", "black")] + fixed_map("foreground"), background=[("selected", ROW_SELECTED)] + fixed_map("background"))

def center_on_parent(win: tk.Toplevel, parent: tk.Misc, width: int, height: int) -> None:
    parent = parent.winfo_toplevel()
    parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    win.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

class DataTree(tk.Frame):
    def __init__(self, parent: tk.Misc, selectmode: str = "browse", autofit: bool = False):
        super().__init__(parent, bg="white")
        self._autofit = autofit
        self.tree = ttk.Treeview(self, show="tree headings", selectmode=selectmode)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("odd", background=ROW_ODD)
        self.tree.tag_configure("even", background=ROW_EVEN)
        self.tree.tag_configure("hover", background=ROW_HOVER)

        self._hovered: Optional[str] = None
        self.tree.bind("<Motion>", self._on_motion, add="+")
        self.tree.bind("<Leave>", self._on_leave, add="+")
        self.tree.bind("<Configure>", self._on_configure, add="+")
        self._reset_number_column()

    def _reset_number_column(self) -> None:
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=46, minwidth=46, anchor="center", stretch=False)

    def configure_columns(self, headers: Sequence[str], widths: Optional[Sequence[int]] = None, default_width: int = 150) -> None:
        ids = [f"c{i}" for i in range(len(headers))]
        self.tree["columns"] = ids
        self._reset_number_column()
        for i, (col_id, header) in enumerate(zip(ids, headers)):
            width = widths[i] if widths and i < len(widths) else default_width
            self.tree.heading(col_id, text=header)
            self.tree.column(col_id, width=width, minwidth=50, anchor="w", stretch=True)

    def fit_columns(self) -> None:
        cols = self.tree["columns"]
        if not cols:
            return
        avail = self.tree.winfo_width() - int(self.tree.column("#0", "width"))
        widths = [int(self.tree.column(c, "width")) for c in cols]
        total = sum(widths)
        if avail <= 50 * len(cols) or total <= 0 or abs(total - avail) <= 1:
            return
        new = [max(50, int(w * avail / total)) for w in widths]
        new[-1] = max(50, new[-1] + avail - sum(new))
        for c, w in zip(cols, new):
            self.tree.column(c, width=w)

    def _on_configure(self, _event: tk.Event) -> None:
        if self._autofit:
            self.fit_columns()

    def fill(self, rows: Sequence[tuple[str, Sequence[str]]]) -> None:
        self._hovered = None
        self.tree.delete(*self.tree.get_children())
        for i, (iid, values) in enumerate(rows):
            self.tree.insert("", "end", iid=iid, text=str(i + 1), values=list(values), tags=("even" if i % 2 == 0 else "odd",))

    def _base_tag(self, iid: str) -> str:
        return "even" if self.tree.index(iid) % 2 == 0 else "odd"

    def _on_motion(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y) or None
        if iid == self._hovered:
            return
        if self._hovered and self.tree.exists(self._hovered):
            self.tree.item(self._hovered, tags=(self._base_tag(self._hovered),))
        self._hovered = iid
        if iid and self.tree.exists(iid):
            self.tree.item(iid, tags=(self._base_tag(iid), "hover"))

    def _on_leave(self, _event: tk.Event) -> None:
        if self._hovered and self.tree.exists(self._hovered):
            self.tree.item(self._hovered, tags=(self._base_tag(self._hovered),))
        self._hovered = None
