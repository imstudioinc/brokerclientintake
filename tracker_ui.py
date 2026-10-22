"""Client record window (per client) and Tracker window (all clients)."""
import datetime
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import customtkinter as ctk

import records

# Meaning colours for statuses and due dates (light, dark)
GOOD = ("#15803D", "#4ADE80")
WARN = ("#B45309", "#FBBF24")
LIVE = ("Bound", "Active", "Renewed")
ENDED = ("Cancelled", "Lapsed", "Lost")


def _ui(app):
    """The main app module (colours, fonts, helpers) without a circular import."""
    return sys.modules[type(app).__module__]


def _c(pair):
    return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]


def style_tables(ui):
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Rec.Treeview", background=_c(ui.SURFACE), fieldbackground=_c(ui.SURFACE),
                foreground=_c(ui.TEXT), rowheight=34, borderwidth=0, font=(ui.FONT, 11))
    s.configure("Rec.Treeview.Heading", background=_c(ui.SURFACE), foreground=_c(ui.MUTED),
                font=(ui.FONT, 10, "bold"), borderwidth=0, relief="flat", padding=(8, 8))
    s.map("Rec.Treeview.Heading", background=[("active", _c(ui.SURFACE_ALT))])
    s.map("Rec.Treeview", background=[("selected", _c(ui.SELECTED))],
          foreground=[("selected", _c(ui.TEXT))])
    s.layout("Rec.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # no outer border


def make_table(parent, ui, columns, widths=None, height=10, right=(), tree_col=False):
    """columns: [(key, label)]. right: keys aligned right (money). tree_col: show group rows."""
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    tree = ttk.Treeview(frame, columns=[c for c, _ in columns], show="tree headings" if tree_col else "headings",
                        style="Rec.Treeview", height=height, selectmode="browse")
    if tree_col:
        tree.column("#0", width=22, minwidth=22, stretch=False)
    for key, label in columns:
        anchor = "e" if key in right else "w"
        tree.heading(key, text=label, anchor=anchor, command=lambda k=key: _sort(tree, k))
        tree.column(key, width=(widths or {}).get(key, 120), anchor=anchor, stretch=True)
    bar = ctk.CTkScrollbar(frame, command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    tree.tag_configure("odd", background=_c(ui.SURFACE_ALT))
    tree.tag_configure("overdue", foreground=_c(ui.DANGER))
    tree.tag_configure("soon", foreground=_c(WARN))
    tree.tag_configure("good", foreground=_c(GOOD))
    tree.tag_configure("muted", foreground=_c(ui.MUTED))
    tree.tag_configure("group", font=(ui.FONT, 11, "bold"), background=_c(ui.BG), foreground=_c(ui.TEXT))
    return frame, tree


def _sort(tree, key):
    rows = [(tree.set(i, key), i) for i in tree.get_children("")]
    desc = getattr(tree, "_sort_desc", {}).get(key, False)

    def k(v):
        t = v[0].replace("$", "").replace(",", "")
        try:
            return (0, float(t))
        except ValueError:
            return (1, t.lower())
    rows.sort(key=k, reverse=desc)
    for n, (_, i) in enumerate(rows):
        tree.move(i, "", n)
        _zebra(tree, i, n)
    tree._sort_desc = {key: not desc}


def _zebra(tree, iid, n):
    tags = [t for t in tree.item(iid, "tags") if t != "odd"]
    tree.item(iid, tags=tags + (["odd"] if n % 2 else []))


def nice_date(value):
    d = records.parse_date(value) if isinstance(value, str) else value
    return d.strftime("%b %d, %Y").replace(" 0", " ") if d else (value or "")


def when_text(d, today=None):
    """'3 days overdue', 'Today', 'Tomorrow', 'In 5 days', or the date for later items."""
    today = today or datetime.date.today()
    days = (d - today).days
    if days < -1:
        return f"{-days} days overdue"
    if days == -1:
        return "Yesterday"
    if days == 0:
        return "Today"
    if days == 1:
        return "Tomorrow"
    if days <= 14:
        return f"In {days} days"
    return nice_date(d)


def show_value(kind, key, value):
    field = next((f for f in records.KINDS[kind]["fields"] if f[0] == key), None)
    if field and field[2] == "money" and value not in (None, ""):
        return f"${records.money(value):,.2f}"
    if field and field[2] == "bool":
        return "Yes" if value else ""
    if field and field[2] == "date":
        return nice_date(value)
    text = " ".join(str(value or "").split())
    return text if len(text) < 90 else text[:87] + "…"


# ================================================================= date picker
DATE_FMT = "%b %d, %Y"   # shown in fields, e.g. "Oct 22, 2026" (saved as 2026-10-22)


def show_date(d):
    return d.strftime(DATE_FMT).replace(" 0", " ")


class CalendarPopup(ctk.CTkToplevel):
    """Month calendar that drops down under a DateField. Click a day to pick it."""

    def __init__(self, field):
        super().__init__(field)
        self.field = field
        ui = self.ui = field.ui
        self.overrideredirect(True)
        self.configure(fg_color=ui.BORDER)
        picked = records.parse_date(field.get())
        self.picked = picked
        self.month = (picked or datetime.date.today()).replace(day=1)

        inner = ctk.CTkFrame(self, fg_color=ui.SURFACE, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(8, 4))
        nav = dict(width=32, height=30, font=ui.font(16, "bold"), fg_color="transparent",
                   hover_color=ui.SURFACE_ALT, text_color=ui.TEXT)
        ctk.CTkButton(head, text="‹", command=lambda: self.shift(-1), **nav).pack(side="left")
        ctk.CTkButton(head, text="›", command=lambda: self.shift(1), **nav).pack(side="right")
        self.title_label = ctk.CTkLabel(head, text="", font=ui.font(14, "bold"), text_color=ui.TEXT)
        self.title_label.pack(side="left", expand=True)

        grid = tk.Frame(inner, bg=_c(ui.SURFACE))
        grid.pack(padx=8)
        for col, name in enumerate(("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")):
            tk.Label(grid, text=name, width=4, font=(ui.FONT, 9, "bold"), bg=_c(ui.SURFACE),
                     fg=_c(ui.MUTED)).grid(row=0, column=col, pady=(0, 2))
        self.cells = []
        for r in range(6):
            for col in range(7):
                cell = tk.Label(grid, width=4, height=1, font=(ui.FONT, 10), cursor="hand2", pady=4)
                cell.grid(row=r + 1, column=col, padx=1, pady=1)
                cell.bind("<Button-1>", lambda e, c=cell: self.pick(c.day) if c.day else None)
                cell.bind("<Enter>", lambda e, c=cell: c.day and c.configure(bg=_c(ui.SURFACE_ALT))
                          if c.day not in (self.picked,) else None)
                cell.bind("<Leave>", lambda e, c=cell: self.paint(c))
                cell.day = None
                self.cells.append(cell)

        foot = ctk.CTkFrame(inner, fg_color="transparent")
        foot.pack(fill="x", padx=8, pady=8)
        link = dict(height=28, font=ui.font(12), fg_color="transparent", hover_color=ui.SURFACE_ALT,
                    text_color=ui.TEXT, border_width=1, border_color=ui.BORDER)
        ctk.CTkButton(foot, text="Today", width=70, command=lambda: self.pick(datetime.date.today()), **link) \
            .pack(side="left")
        ctk.CTkButton(foot, text="Clear", width=70, command=self.clear, **link).pack(side="right")

        self.draw()
        self.update_idletasks()
        x = field.winfo_rootx()
        y = field.winfo_rooty() + field.winfo_height() + 2
        if y + self.winfo_reqheight() > self.winfo_screenheight() - 40:   # no room below: open above
            y = field.winfo_rooty() - self.winfo_reqheight() - 2
        self.geometry(f"+{x}+{y}")
        self.lift()
        self.prev_grab = self.grab_current()   # the editor is modal; take over clicks while open
        self._grab()
        self.focus_force()
        self.bind("<Escape>", lambda e: self.close())
        self.bind("<Button-1>", self._click_outside, add="+")

    def _grab(self, tries=10):
        try:
            self.grab_set()
        except tk.TclError:   # window not on screen yet
            if tries:
                self.after(30, lambda: self._grab(tries - 1))

    def _click_outside(self, event):
        x, y = event.x_root, event.y_root
        if not (self.winfo_rootx() <= x <= self.winfo_rootx() + self.winfo_width()
                and self.winfo_rooty() <= y <= self.winfo_rooty() + self.winfo_height()):
            self.close()

    def shift(self, months):
        m = self.month.month - 1 + months
        self.month = self.month.replace(year=self.month.year + m // 12, month=m % 12 + 1)
        self.draw()

    def draw(self):
        self.title_label.configure(text=self.month.strftime("%B %Y"))
        first = self.month - datetime.timedelta(days=(self.month.weekday() + 1) % 7)   # Sunday on/before the 1st
        for i, cell in enumerate(self.cells):
            day = first + datetime.timedelta(days=i)
            cell.day = day
            cell.configure(text=str(day.day))
            self.paint(cell)

    def paint(self, cell):
        ui, day = self.ui, cell.day
        if day == self.picked:
            cell.configure(bg=_c(ui.PRIMARY), fg="#FFFFFF", font=(ui.FONT, 10, "bold"))
        elif day == datetime.date.today():
            cell.configure(bg=_c(ui.SELECTED), fg=_c(ui.TEXT), font=(ui.FONT, 10, "bold"))
        else:
            cell.configure(bg=_c(ui.SURFACE), font=(ui.FONT, 10),
                           fg=_c(ui.TEXT) if day.month == self.month.month else _c(ui.MUTED))

    def pick(self, day):
        self.field.set_date(day)
        self.close()

    def clear(self):
        self.field.set_date(None)
        self.close()

    def close(self):
        try:
            self.grab_release()
            if self.prev_grab and self.prev_grab.winfo_exists():
                self.prev_grab.grab_set()
        finally:
            self.destroy()


class DateField(ctk.CTkFrame):
    """Text box + calendar button. Typing still works; the button opens the calendar.
    Behaves like a CTkEntry for get/insert/delete/bind."""

    def __init__(self, parent, ui, on_change=None):
        super().__init__(parent, fg_color="transparent")
        self.ui, self.on_change = ui, on_change
        self.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(self, height=34, font=ui.font(13), border_color=ui.BORDER,
                                  placeholder_text="Pick a date")
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Button-1>", lambda e: self.after(10, self.open) if not self.entry.get() else None)
        self.entry.bind("<Alt-Down>", lambda e: self.open())
        ctk.CTkButton(self, text="▾  Calendar", width=104, height=34, font=ui.font(12),
                      fg_color="transparent", border_width=1, border_color=ui.BORDER, text_color=ui.TEXT,
                      hover_color=ui.SURFACE_ALT, command=self.open).grid(row=0, column=1, padx=(6, 0))

    def open(self):
        CalendarPopup(self)

    def set_date(self, day):
        self.entry.delete(0, "end")
        if day:
            self.entry.insert(0, show_date(day))
        if self.on_change:
            self.on_change()

    # CTkEntry-compatible bits used by the editor
    def get(self):
        return self.entry.get()

    def delete(self, *a):
        self.entry.delete(*a)

    def insert(self, index, value):
        d = records.parse_date(value) if isinstance(value, str) else None
        self.entry.insert(index, show_date(d) if d else value)

    def bind(self, *a, **kw):
        return self.entry.bind(*a, **kw)


def status_tag(status):
    """Only statuses that need attention are coloured: quotes amber, ended policies grey."""
    return "soon" if status == "Quoted" else "muted" if status in ENDED else ""


class Counter(ctk.CTkFrame):
    """A number with a label underneath; clicking it applies a filter."""

    def __init__(self, parent, ui, label, color, command):
        super().__init__(parent, fg_color=ui.SURFACE, corner_radius=10, border_width=2, border_color=ui.SURFACE,
                         cursor="hand2")
        self.ui = ui
        self.number = ctk.CTkLabel(self, text="–", font=ui.font(28, "bold"), text_color=color, cursor="hand2")
        self.number.pack(anchor="w", padx=16, pady=(10, 0))
        self.label = ctk.CTkLabel(self, text=label, font=ui.font(13), text_color=ui.MUTED, cursor="hand2")
        self.label.pack(anchor="w", padx=16, pady=(0, 10))
        for w in (self, self.number, self.label):
            w.bind("<Button-1>", lambda e: command())

    def set(self, n, active=False):
        self.number.configure(text=str(n))
        self.configure(border_color=self.ui.PRIMARY if active else self.ui.SURFACE)


# ====================================================================== editor
class RecordEditor(ctk.CTkToplevel):
    """Add / edit one record; the form is generated from records.KINDS."""

    def __init__(self, parent, app, folder, kind, item=None, on_saved=None):
        super().__init__(parent)
        self.app, self.folder, self.kind, self.item, self.on_saved = app, folder, kind, item or {}, on_saved
        ui = self.ui = _ui(app)
        spec = records.KINDS[kind]
        self.title(f"{'Edit' if item else 'Add'} {spec['singular']} - {folder.name}")
        self.geometry("560x680")
        self.configure(fg_color=ui.BG)
        self.transient(parent)
        self.grab_set()

        body = ctk.CTkScrollableFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1,
                                      border_color=ui.BORDER)
        body.pack(fill="both", expand=True, padx=16, pady=(16, 0))
        body.grid_columnconfigure(0, weight=1)
        self.inputs = {}
        r = 0
        for key, label, ftype, options in spec["fields"]:
            value = self.item.get(key, "")
            if ftype == "bool":
                var = tk.BooleanVar(value=bool(value))
                ctk.CTkCheckBox(body, text=label, variable=var, font=ui.font(13), text_color=ui.TEXT,
                                fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER) \
                    .grid(row=r, column=0, sticky="w", padx=16, pady=(14, 0))
                self.inputs[key] = ("bool", var)
                r += 1
                continue
            ctk.CTkLabel(body, text=label, font=ui.font(13, "bold"), text_color=ui.TEXT) \
                .grid(row=r, column=0, sticky="w", padx=16, pady=(12, 4))
            r += 1
            if ftype == "choice":
                var = tk.StringVar(value=value or (options[0] if key in ("line", "status", "plan") else ""))
                w = ctk.CTkOptionMenu(body, values=([""] if key not in ("line", "status", "plan") else []) + options,
                                      variable=var, height=34, font=ui.font(13), fg_color=ui.SURFACE_ALT,
                                      button_color=ui.PRIMARY, button_hover_color=ui.PRIMARY_HOVER,
                                      text_color=ui.TEXT, dynamic_resizing=False)
                self.inputs[key] = ("choice", var)
            elif ftype == "long":
                w = ctk.CTkTextbox(body, height=90, font=ui.font(13), border_width=1, border_color=ui.BORDER)
                w.insert("1.0", value or "")
                self.inputs[key] = ("long", w)
            elif ftype == "date":
                w = DateField(body, ui, on_change=(self._policy_defaults if kind == "policies" else None))
                if value not in (None, ""):
                    w.insert(0, str(value))
                elif key in ("date", "bound_date") and not item:
                    w.insert(0, records.today())
                self.inputs[key] = (ftype, w)
            else:
                w = ctk.CTkEntry(body, height=34, font=ui.font(13), border_color=ui.BORDER)
                if value not in (None, ""):
                    w.insert(0, str(value))
                elif ftype == "date" and key in ("date", "bound_date") and not item:
                    w.insert(0, records.today())
                self.inputs[key] = (ftype, w)
            w.grid(row=r, column=0, sticky="ew", padx=16)
            r += 1
        ctk.CTkLabel(body, text="").grid(row=r, column=0)

        if kind == "policies":  # handy defaults: expiry = effective + 1 year, monthly = premium / 12
            self.inputs["effective"][1].bind("<FocusOut>", lambda e: self._policy_defaults())
            self.inputs["premium"][1].bind("<FocusOut>", lambda e: self._policy_defaults())

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=16)
        ctk.CTkButton(bottom, text="Save", width=110, height=38, font=ui.font(14, "bold"), fg_color=ui.PRIMARY,
                      hover_color=ui.PRIMARY_HOVER, command=self.save).pack(side="right")
        app.secondary_button(bottom, "Cancel", self.destroy, width=96).pack(side="right", padx=(0, 8))
        self.error = ctk.CTkLabel(bottom, text="", font=ui.font(12), text_color=ui.DANGER)
        self.error.pack(side="left")
        self.bind("<Escape>", lambda e: self.destroy())

    def _get(self, key):
        ftype, w = self.inputs[key]
        if ftype in ("bool", "choice"):
            return w.get()
        if ftype == "long":
            return w.get("1.0", "end").strip()
        return w.get().strip()

    def _set_if_empty(self, key, value):
        ftype, w = self.inputs[key]
        if not w.get().strip():
            w.delete(0, "end")
            w.insert(0, value)

    def _policy_defaults(self):
        eff = records.parse_date(self._get("effective"))
        if eff:
            try:
                self._set_if_empty("expiry", show_date(eff.replace(year=eff.year + 1)))
            except ValueError:  # Feb 29
                self._set_if_empty("expiry", show_date(eff + datetime.timedelta(days=365)))
        prem = records.money(self._get("premium"))
        if prem and self.inputs["plan"][1].get() == "Monthly":
            self._set_if_empty("monthly", f"{prem / 12:.2f}")

    def save(self):
        item = dict(self.item)
        for key, (ftype, _) in self.inputs.items():
            value = self._get(key)
            if ftype == "date" and value:
                d = records.parse_date(value)
                if not d:
                    self.error.configure(text=f"Date not recognised: {value} - use the calendar")
                    return
                value = d.isoformat()
            if ftype == "money" and value:
                value = f"{records.money(value):.2f}"
            item[key] = value
        if self.kind == "policies" and not (item.get("insurer") or item.get("policy_number")):
            self.error.configure(text="Enter at least the insurance company or policy number.")
            return
        if self.kind in ("notes", "reminders") and not item.get("text"):
            self.error.configure(text="Write the note / reminder text.")
            return
        try:
            records.save_item(self.folder, self.kind, item)
        except OSError as e:
            self.error.configure(text=f"Could not save (is the shared drive available?) {e}")
            return
        self.destroy()
        if self.on_saved:
            self.on_saved()


SHORT = {"by": "Added by", "insurer": "Insurer", "policy_number": "Policy #", "effective": "Effective",
         "expiry": "Expiry", "premium": "Premium", "plan": "Plan", "principal_driver": "Driver",
         "lienholder": "Lender", "year_built": "Built", "mortgagee": "Mortgagee", "operations": "Operations",
         "text": "Note", "due": "Due", "method": "How"}


# ============================================================== client record
class ClientRecordDialog(ctk.CTkToplevel):
    """Everything about one client: policies, vehicles, property, business, notes, reminders."""

    def __init__(self, app, folder, tab="Policies"):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = _ui(app)
        style_tables(ui)
        self.title(f"Client record - {self.folder.name}")
        self.geometry("1100x700")
        self.minsize(880, 560)
        self.configure(fg_color=ui.BG)
        self.transient(app)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(18, 0))
        ctk.CTkLabel(head, text=self.folder.name, font=ui.font(22, "bold"), text_color=ui.TEXT).pack(side="left")
        app.secondary_button(head, "Open folder", lambda: os.startfile(self.folder), width=110).pack(side="right")

        # Facts a broker looks for first, in one readable sentence-sized row
        facts = ctk.CTkFrame(self, fg_color="transparent")
        facts.pack(fill="x", padx=20, pady=(10, 0))
        self.facts = {}
        for key, label in (("active", "Active policies"), ("premium", "Annual premium"),
                           ("monthly", "Monthly payments"), ("todo", "To do")):
            box = ctk.CTkFrame(facts, fg_color=ui.SURFACE, corner_radius=10)
            box.pack(side="left", padx=(0, 10))
            value = ctk.CTkLabel(box, text="–", font=ui.font(20, "bold"), text_color=ui.TEXT)
            value.pack(anchor="w", padx=16, pady=(8, 0))
            ctk.CTkLabel(box, text=label, font=ui.font(12), text_color=ui.MUTED).pack(anchor="w", padx=16, pady=(0, 8))
            self.facts[key] = value

        self.tabs = ctk.CTkTabview(self, fg_color=ui.SURFACE, segmented_button_selected_color=ui.SELECTED,
                                   segmented_button_selected_hover_color=ui.SELECTED,
                                   segmented_button_fg_color=ui.SURFACE_ALT,
                                   segmented_button_unselected_color=ui.SURFACE_ALT,
                                   segmented_button_unselected_hover_color=ui.BORDER,
                                   text_color=ui.TEXT, border_width=0, corner_radius=12)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(14, 20))
        self.tabs._segmented_button.configure(font=ui.font(13), height=34)
        self.trees = {}
        for kind, spec in records.KINDS.items():
            tab = self.tabs.add(spec["title"])
            cols = [(k, SHORT.get(k) or next(f[1] for f in spec["fields"] if f[0] == k).split(" (")[0])
                    for k in spec["columns"]]
            frame, tree = make_table(tab, ui, cols, right=("premium", "revenue"),
                                     widths={"text": 420, "address": 260, "vin": 190, "lienholder": 220})
            frame.pack(fill="both", expand=True, padx=6, pady=(6, 0))
            tree.bind("<Double-1>", lambda e, k=kind: self.edit(k))
            bar = ctk.CTkFrame(tab, fg_color="transparent")
            bar.pack(fill="x", padx=6, pady=10)
            ctk.CTkButton(bar, text=f"Add {spec['singular']}", height=36, font=ui.font(13, "bold"),
                          fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER,
                          command=lambda k=kind: self.add(k)).pack(side="left")
            app.secondary_button(bar, "Edit", lambda k=kind: self.edit(k), width=80).pack(side="left", padx=8)
            app.secondary_button(bar, "Delete", lambda k=kind: self.delete(k), width=80).pack(side="left")
            if kind == "reminders":
                app.secondary_button(bar, "Mark done", self.mark_done, width=100).pack(side="left", padx=8)
            ctk.CTkLabel(bar, text="Double-click a row to edit it.", font=ui.font(12), text_color=ui.MUTED) \
                .pack(side="right")
            self.trees[kind] = tree
        self.tabs.set(tab if tab in [s["title"] for s in records.KINDS.values()] else "Policies")
        self.bind("<Escape>", lambda e: self.destroy())
        self.reload()

    def reload(self):
        self.data = records.load(self.folder)
        for kind, tree in self.trees.items():
            tree.delete(*tree.get_children())
            items = self.data[kind]
            if kind == "notes":
                items = sorted(items, key=lambda x: x.get("date") or "", reverse=True)
            elif kind == "reminders":
                items = sorted(items, key=lambda x: (bool(x.get("done")), x.get("due") or ""))
            elif kind == "policies":
                items = sorted(items, key=lambda x: (x.get("status") in ENDED, x.get("expiry") or ""))
            for n, it in enumerate(items):
                tags = []
                if kind == "policies":
                    tags.append(status_tag(it.get("status")))
                if kind == "reminders" and it.get("done"):
                    tags.append("muted")
                if n % 2:
                    tags.append("odd")
                tree.insert("", "end", iid=it["id"], tags=[t for t in tags if t],
                            values=[show_value(kind, k, it.get(k)) for k in records.KINDS[kind]["columns"]])
        live = [p for p in self.data["policies"] if p.get("status") in LIVE]
        monthly = sum(records.money(p.get("monthly")) for p in live if p.get("plan") == "Monthly")
        due = records.due_items(self.folder, self.data)
        now = sum(1 for d in due if d["due"] <= datetime.date.today())
        self.facts["active"].configure(text=str(len(live)))
        self.facts["premium"].configure(text=f"${sum(records.money(p.get('premium')) for p in live):,.0f}")
        self.facts["monthly"].configure(text=f"${monthly:,.2f}" if monthly else "None")
        self.facts["todo"].configure(text=f"{len(due)}" + (f"  ({now} due now)" if now else ""),
                                     text_color=self.ui.DANGER if now else self.ui.TEXT)

    def _selected(self, kind):
        sel = self.trees[kind].selection()
        if not sel:
            messagebox.showinfo("Client record", "Select a row first.", parent=self)
            return None
        return next((x for x in self.data[kind] if x.get("id") == sel[0]), None)

    def add(self, kind):
        RecordEditor(self, self.app, self.folder, kind, on_saved=self.saved)

    def edit(self, kind):
        item = self._selected(kind)
        if item:
            RecordEditor(self, self.app, self.folder, kind, item=item, on_saved=self.saved)

    def delete(self, kind):
        item = self._selected(kind)
        if item and messagebox.askyesno("Delete", f"Delete this {records.KINDS[kind]['singular']}?", parent=self):
            records.delete_item(self.folder, kind, item["id"])
            self.saved()

    def mark_done(self):
        item = self._selected("reminders")
        if item:
            records.save_item(self.folder, "reminders", {**item, "done": True})
            self.saved()

    def saved(self):
        self.reload()
        if hasattr(self.app, "tracker_changed"):
            self.app.tracker_changed()


# ==================================================================== tracker
TODO_KIND = {"Reminder": "Reminder", "Renewal": "Renewal", "Quote": "Quote follow-up", "Missing info": "Missing info"}


class TrackerView(ctk.CTkFrame):
    """All clients: what needs doing, every policy, and premium totals.
    Shown inside the main window (Clients | Tracker switch), not as a separate window."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        ui = self.ui = _ui(app)
        style_tables(ui)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=0, pady=(0, 0))
        ctk.CTkLabel(head, text="Tracker", font=ui.font(24, "bold"), text_color=ui.TEXT).pack(side="left")
        self.status = ctk.CTkLabel(head, text="Loading…", font=ui.font(13), text_color=ui.MUTED)
        self.status.pack(side="left", padx=16, pady=(6, 0))
        app.secondary_button(head, "Refresh", self.load, width=90).pack(side="right")

        # Counters double as filters for the To do list
        self.view = "all"
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=0, pady=(12, 0))
        self.counters = {}
        for key, label, color in (("now", "Due now", ui.DANGER), ("soon", "Next 14 days", WARN),
                                  ("Renewal", "Renewals", ui.TEXT), ("Quote", "Quotes waiting", ui.TEXT),
                                  ("all", "Everything", ui.MUTED)):
            c = Counter(row, ui, label, color, lambda k=key: self.set_view(k))
            c.pack(side="left", padx=(0, 10))
            self.counters[key] = c

        self.tabs = ctk.CTkTabview(self, fg_color=ui.SURFACE, segmented_button_selected_color=ui.SELECTED,
                                   segmented_button_selected_hover_color=ui.SELECTED,
                                   segmented_button_fg_color=ui.SURFACE_ALT,
                                   segmented_button_unselected_color=ui.SURFACE_ALT,
                                   segmented_button_unselected_hover_color=ui.BORDER,
                                   text_color=ui.TEXT, corner_radius=12)
        self.tabs.pack(fill="both", expand=True, padx=0, pady=(14, 0))
        self.tabs._segmented_button.configure(font=ui.font(13), height=34)

        # --- To do (grouped: due now / next 14 days / later)
        t = self.tabs.add("To do")
        frame, self.todo = make_table(t, ui, [("when", "When"), ("client", "Client"), ("kind", "Type"), ("what", "What to do")],
                                      widths={"when": 150, "client": 200, "kind": 130, "what": 600}, height=14,
                                      tree_col=True)
        frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.todo.bind("<Double-1>", lambda e: self.open_client(self.todo, "Reminders"))
        ctk.CTkLabel(t, text="Renewals appear 45 days before expiry. Quotes get a follow-up after 7 days. "
                             "Double-click a row to open the client.",
                     font=ui.font(12), text_color=ui.MUTED).pack(anchor="w", padx=8, pady=(0, 8))

        # --- Policies
        t = self.tabs.add("Policies")
        filters = ctk.CTkFrame(t, fg_color="transparent")
        filters.pack(fill="x", padx=6, pady=(6, 0))
        self.f_status = tk.StringVar(value="Bound / Active")
        self.f_line = tk.StringVar(value="All lines")
        self.f_month = tk.StringVar(value="All months")
        menu = dict(width=170, height=34, font=ui.font(13), fg_color=ui.SURFACE_ALT, button_color=ui.SURFACE_ALT,
                    button_hover_color=ui.BORDER, text_color=ui.TEXT, dropdown_font=ui.font(13),
                    command=lambda _: self.fill_policies())
        ctk.CTkOptionMenu(filters, values=["Bound / Active", "All statuses"] + records.STATUSES,
                          variable=self.f_status, **menu).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(filters, values=["All lines"] + records.LINES, variable=self.f_line, **menu) \
            .pack(side="left", padx=(0, 8))
        self.month_menu = ctk.CTkOptionMenu(filters, values=["All months"], variable=self.f_month, **menu)
        self.month_menu.pack(side="left")
        cols = [("client", "Client"), ("line", "Line"), ("status", "Status"), ("insurer", "Insurer"),
                ("policy_number", "Policy #"), ("effective", "Effective"), ("expiry", "Expiry"),
                ("premium", "Premium"), ("plan", "Plan"), ("by", "Added by")]
        frame, self.pol = make_table(t, ui, cols, right=("premium",),
                                     widths={"client": 190, "premium": 110, "effective": 120, "expiry": 120},
                                     height=14)
        self.totals = ctk.CTkLabel(t, text="", font=ui.font(14, "bold"), text_color=ui.TEXT, anchor="e")
        self.totals.pack(side="bottom", fill="x", padx=12, pady=(0, 10))  # pinned below the table
        frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.pol.bind("<Double-1>", lambda e: self.open_client(self.pol, "Policies"))

        self.items, self.todo_rows = [], []
        self.load()

    # ----- data
    def load(self):
        self.status.configure(text="Loading…")
        folders = list(self.app.client_type_of)

        def work():  # reading many files on a shared drive happens off the window's thread
            result = records.scan_all(folders)
            self.app.ui(lambda: self._loaded(result))
        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, result):
        if not self.winfo_exists():
            return
        self.items = result
        self.todo_rows = sorted(((d["due"], folder, d) for folder, data in result
                                 for d in records.due_items(folder, data)), key=lambda x: x[0])
        months = sorted({(p.get("effective") or "")[:7] for _, data in result for p in data["policies"]
                         if p.get("effective")}, reverse=True)
        self.month_menu.configure(values=["All months"] + months)
        self.status.configure(text=f"{len(result)} clients with records, updated "
                                   f"{datetime.datetime.now():%I:%M %p}".replace(" 0", " "))
        self.fill_todo()
        self.fill_policies()

    # ----- To do
    def _bucket(self, due, today):
        return "now" if due <= today else "soon" if due <= today + datetime.timedelta(days=14) else "later"

    def set_view(self, key):
        self.view = "all" if self.view == key else key
        self.tabs.set("To do")
        self.fill_todo()

    def fill_todo(self):
        today = datetime.date.today()
        rows = self.todo_rows
        counts = {"now": 0, "soon": 0, "Renewal": 0, "Quote": 0, "all": len(rows)}
        for due, _, d in rows:
            counts[self._bucket(due, today)] = counts.get(self._bucket(due, today), 0) + 1
            if d["kind"] in counts:
                counts[d["kind"]] += 1
        for key, c in self.counters.items():
            c.set(counts.get(key, 0), active=(key == self.view))

        if self.view in ("now", "soon"):
            rows = [r for r in rows if self._bucket(r[0], today) == self.view]
        elif self.view in ("Renewal", "Quote"):
            rows = [r for r in rows if r[2]["kind"] == self.view]

        tree = self.todo
        tree.delete(*tree.get_children())
        self._todo_folders = {}
        groups = (("now", "Due now"), ("soon", "Next 14 days"), ("later", "Later"))
        for key, title in groups:
            members = [r for r in rows if self._bucket(r[0], today) == key]
            if not members:
                continue
            parent = tree.insert("", "end", iid=f"g-{key}", open=True, tags=("group",),
                                 values=[f"{title} ({len(members)})", "", "", ""])
            for n, (due, folder, d) in enumerate(members):
                iid = f"{key}-{n}"
                tag = {"now": "overdue", "soon": "soon"}.get(key, "")
                tree.insert(parent, "end", iid=iid, tags=[t for t in (tag, "odd" if n % 2 else "") if t],
                            values=[when_text(due, today), folder.name, TODO_KIND.get(d["kind"], d["kind"]),
                                    d["what"]])
                self._todo_folders[iid] = folder
        if not rows:
            tree.insert("", "end", iid="empty", tags=("muted",),
                        values=["", "Nothing to do here.", "", "Add reminders from a client's record."])

    # ----- Policies
    def fill_policies(self):
        self.pol.delete(*self.pol.get_children())
        status, line, month = self.f_status.get(), self.f_line.get(), self.f_month.get()
        total, by_line, count = 0.0, {}, 0
        self._pol_folders = {}
        rows = []
        for folder, data in self.items:
            for p in data["policies"]:
                if status == "Bound / Active" and p.get("status") not in LIVE:
                    continue
                if status not in ("Bound / Active", "All statuses") and p.get("status") != status:
                    continue
                if line != "All lines" and p.get("line") != line:
                    continue
                if month != "All months" and not (p.get("effective") or "").startswith(month):
                    continue
                rows.append((p.get("expiry") or "", folder, p))
        for n, (_, folder, p) in enumerate(sorted(rows, key=lambda r: r[0])):
            iid = f"{folder}|{p['id']}"
            self._pol_folders[iid] = folder
            tags = [t for t in (status_tag(p.get("status")), "odd" if n % 2 else "") if t]
            self.pol.insert("", "end", iid=iid, tags=tags, values=[folder.name] + [
                show_value("policies", k, p.get(k)) for k in
                ("line", "status", "insurer", "policy_number", "effective", "expiry", "premium", "plan", "by")])
            amount = records.money(p.get("premium"))
            total += amount
            by_line[p.get("line") or "Other"] = by_line.get(p.get("line") or "Other", 0) + amount
            count += 1
        parts = [f"{k} ${v:,.0f}" for k, v in sorted(by_line.items(), key=lambda kv: -kv[1])]
        self.totals.configure(text=("     ".join(parts) + "        " if len(parts) > 1 else "")
                                   + f"{count} polic{'y' if count == 1 else 'ies'}, ${total:,.2f} total premium")

    def open_client(self, tree, tab):
        sel = tree.selection()
        if not sel:
            return
        folder = (self._todo_folders if tree is self.todo else self._pol_folders).get(sel[0])
        if folder:
            if folder in self.app.client_type_of:
                self.app.select(folder)
            ClientRecordDialog(self.app, folder, tab=tab)
