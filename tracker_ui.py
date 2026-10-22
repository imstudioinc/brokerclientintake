"""Client record window (per client) and Tracker window (all clients)."""
import datetime
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import customtkinter as ctk

import records


def _ui(app):
    """The main app module (colours, fonts, helpers) without a circular import."""
    return sys.modules[type(app).__module__]


def _c(pair):
    return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]


def style_tables(ui):
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Rec.Treeview", background=_c(ui.SURFACE), fieldbackground=_c(ui.SURFACE),
                foreground=_c(ui.TEXT), rowheight=28, borderwidth=0, font=(ui.FONT, 10))
    s.configure("Rec.Treeview.Heading", background=_c(ui.SURFACE_ALT), foreground=_c(ui.MUTED),
                font=(ui.FONT, 9, "bold"), borderwidth=0, relief="flat")
    s.map("Rec.Treeview", background=[("selected", _c(ui.SELECTED))],
          foreground=[("selected", _c(ui.TEXT))])


def make_table(parent, ui, columns, widths=None, height=10):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    tree = ttk.Treeview(frame, columns=[c for c, _ in columns], show="headings", style="Rec.Treeview",
                        height=height, selectmode="browse")
    for key, label in columns:
        tree.heading(key, text=label, command=lambda k=key: _sort(tree, k))
        tree.column(key, width=(widths or {}).get(key, 120), anchor="w", stretch=True)
    bar = ctk.CTkScrollbar(frame, command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    tree.tag_configure("overdue", foreground=_c(ui.DANGER))
    tree.tag_configure("soon", foreground="#B45309")
    tree.tag_configure("muted", foreground=_c(ui.MUTED))
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
    tree._sort_desc = {key: not desc}


def show_value(kind, key, value):
    field = next((f for f in records.KINDS[kind]["fields"] if f[0] == key), None)
    if field and field[2] == "money" and value not in (None, ""):
        return f"${records.money(value):,.2f}"
    if field and field[2] == "bool":
        return "Yes" if value else ""
    if key == "by":
        return value or ""
    text = str(value or "")
    return text if len(text) < 80 else text[:77] + "…"


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
            else:
                w = ctk.CTkEntry(body, height=34, font=ui.font(13), border_color=ui.BORDER,
                                 placeholder_text="YYYY-MM-DD" if ftype == "date" else "")
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
                self._set_if_empty("expiry", eff.replace(year=eff.year + 1).isoformat())
            except ValueError:  # Feb 29
                self._set_if_empty("expiry", (eff + datetime.timedelta(days=365)).isoformat())
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
                    self.error.configure(text=f"Date not recognised: {value} (use YYYY-MM-DD)")
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


# ============================================================== client record
class ClientRecordDialog(ctk.CTkToplevel):
    """Everything about one client: policies, vehicles, property, business, notes, reminders."""

    def __init__(self, app, folder, tab="Policies"):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = _ui(app)
        style_tables(ui)
        self.title(f"Client record - {self.folder.name}")
        self.geometry("1060x640")
        self.minsize(860, 520)
        self.configure(fg_color=ui.BG)
        self.transient(app)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(head, text=self.folder.name, font=ui.font(18, "bold"), text_color=ui.TEXT).pack(side="left")
        self.summary = ctk.CTkLabel(head, text="", font=ui.font(13), text_color=ui.MUTED)
        self.summary.pack(side="left", padx=16)
        app.secondary_button(head, "Open folder", lambda: __import__("os").startfile(self.folder), width=110) \
            .pack(side="right")

        self.tabs = ctk.CTkTabview(self, fg_color=ui.SURFACE, segmented_button_selected_color=ui.PRIMARY,
                                   segmented_button_selected_hover_color=ui.PRIMARY_HOVER,
                                   border_width=1, border_color=ui.BORDER)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=16)
        self.trees = {}
        for kind, spec in records.KINDS.items():
            tab = self.tabs.add(spec["title"])
            cols = [(k, next(f[1] for f in spec["fields"] if f[0] == k) if k != "by" else "Added by")
                    for k in spec["columns"]]
            cols = [(k, l.split(" (")[0]) for k, l in cols]
            frame, tree = make_table(tab, ui, cols, widths={"text": 380, "address": 240, "coverage": 240})
            frame.pack(fill="both", expand=True, padx=8, pady=(8, 0))
            tree.bind("<Double-1>", lambda e, k=kind: self.edit(k))
            bar = ctk.CTkFrame(tab, fg_color="transparent")
            bar.pack(fill="x", padx=8, pady=8)
            ctk.CTkButton(bar, text=f"Add {spec['singular']}", height=34, font=ui.font(13, "bold"),
                          fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER,
                          command=lambda k=kind: self.add(k)).pack(side="left")
            app.secondary_button(bar, "Edit", lambda k=kind: self.edit(k), width=80).pack(side="left", padx=8)
            app.secondary_button(bar, "Delete", lambda k=kind: self.delete(k), width=80).pack(side="left")
            if kind == "reminders":
                app.secondary_button(bar, "Mark done", self.mark_done, width=100).pack(side="left", padx=8)
            self.trees[kind] = tree
        self.tabs.set(tab if tab in [s["title"] for s in records.KINDS.values()] else "Policies")
        self.bind("<Escape>", lambda e: self.destroy())
        self.reload()

    def reload(self):
        self.data = records.load(self.folder)
        for kind, tree in self.trees.items():
            tree.delete(*tree.get_children())
            items = self.data[kind]
            if kind in ("notes", "reminders"):
                items = sorted(items, key=lambda x: x.get("date") or x.get("due") or "", reverse=kind == "notes")
            for it in items:
                tags = ("muted",) if (kind == "reminders" and it.get("done")) or \
                    (kind == "policies" and it.get("status") in ("Cancelled", "Lapsed", "Lost")) else ()
                tree.insert("", "end", iid=it["id"], tags=tags,
                            values=[show_value(kind, k, it.get(k)) for k in records.KINDS[kind]["columns"]])
        live = [p for p in self.data["policies"] if p.get("status") in ("Bound", "Active", "Renewed")]
        total = sum(records.money(p.get("premium")) for p in live)
        due = records.due_items(self.folder, self.data)
        overdue = sum(1 for d in due if d["due"] <= datetime.date.today())
        self.summary.configure(text=f"{len(live)} active polic{'y' if len(live) == 1 else 'ies'}  ·  "
                                    f"${total:,.2f} / year  ·  {len(due)} to do" + (f" ({overdue} due now)" if overdue else ""))

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
class TrackerWindow(ctk.CTkToplevel):
    """All clients: what needs doing, every policy, and premium totals."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        ui = self.ui = _ui(app)
        style_tables(ui)
        self.title("Tracker")
        self.geometry("1180x700")
        self.minsize(900, 560)
        self.configure(fg_color=ui.BG)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(head, text="Tracker", font=ui.font(20, "bold"), text_color=ui.TEXT).pack(side="left")
        self.status = ctk.CTkLabel(head, text="Loading…", font=ui.font(13), text_color=ui.MUTED)
        self.status.pack(side="left", padx=16)
        app.secondary_button(head, "Refresh", self.load, width=90).pack(side="right")

        self.tabs = ctk.CTkTabview(self, fg_color=ui.SURFACE, segmented_button_selected_color=ui.PRIMARY,
                                   segmented_button_selected_hover_color=ui.PRIMARY_HOVER,
                                   border_width=1, border_color=ui.BORDER)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=16)

        # --- To do
        t = self.tabs.add("To do")
        frame, self.todo = make_table(t, ui, [("due", "Due"), ("client", "Client"), ("kind", "Type"), ("what", "What")],
                                      widths={"due": 110, "client": 200, "kind": 110, "what": 560}, height=16)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        self.todo.bind("<Double-1>", lambda e: self.open_client(self.todo, "Reminders"))
        ctk.CTkLabel(t, text="Red = due or overdue, amber = within 14 days. Renewals show 45 days ahead; "
                             "quotes get a follow-up after 7 days. Double-click to open the client.",
                     font=ui.font(12), text_color=ui.MUTED).pack(anchor="w", padx=8, pady=(0, 8))

        # --- Policies
        t = self.tabs.add("Policies")
        filters = ctk.CTkFrame(t, fg_color="transparent")
        filters.pack(fill="x", padx=8, pady=(8, 0))
        self.f_status = tk.StringVar(value="Bound / Active")
        self.f_line = tk.StringVar(value="All lines")
        self.f_month = tk.StringVar(value="All months")
        for var, values in ((self.f_status, ["Bound / Active", "All statuses"] + records.STATUSES),
                            (self.f_line, ["All lines"] + records.LINES)):
            ctk.CTkOptionMenu(filters, values=values, variable=var, width=170, height=32, font=ui.font(13),
                              fg_color=ui.SURFACE_ALT, button_color=ui.PRIMARY, text_color=ui.TEXT,
                              button_hover_color=ui.PRIMARY_HOVER, command=lambda _: self.fill_policies()) \
                .pack(side="left", padx=(0, 8))
        self.month_menu = ctk.CTkOptionMenu(filters, values=["All months"], variable=self.f_month, width=170,
                                            height=32, font=ui.font(13), fg_color=ui.SURFACE_ALT,
                                            button_color=ui.PRIMARY, text_color=ui.TEXT,
                                            button_hover_color=ui.PRIMARY_HOVER,
                                            command=lambda _: self.fill_policies())
        self.month_menu.pack(side="left")
        self.totals = ctk.CTkLabel(filters, text="", font=ui.font(13, "bold"), text_color=ui.TEXT)
        self.totals.pack(side="right")
        cols = [("client", "Client"), ("line", "Line"), ("status", "Status"), ("insurer", "Insurer"),
                ("policy_number", "Policy #"), ("effective", "Effective"), ("expiry", "Expiry"),
                ("premium", "Premium"), ("plan", "Plan"), ("by", "Added by")]
        frame, self.pol = make_table(t, ui, cols, widths={"client": 190, "premium": 100}, height=16)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        self.pol.bind("<Double-1>", lambda e: self.open_client(self.pol, "Policies"))

        self.items = []
        self.bind("<Escape>", lambda e: self.destroy())
        self.load()

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
        today = datetime.date.today()
        self.todo.delete(*self.todo.get_children())
        todo = []
        for folder, data in result:
            for d in records.due_items(folder, data):
                todo.append((d["due"], folder, d))
        todo.sort(key=lambda x: x[0])
        for n, (due, folder, d) in enumerate(todo):
            tag = "overdue" if due <= today else "soon" if due <= today + datetime.timedelta(days=14) else ""
            self.todo.insert("", "end", iid=f"{n}", tags=(tag,) if tag else (),
                             values=[due.isoformat(), folder.name, d["kind"], d["what"]])
        self._todo_folders = {f"{n}": folder for n, (_, folder, _) in enumerate(todo)}
        months = sorted({(p.get("effective") or "")[:7] for _, data in result for p in data["policies"]
                         if p.get("effective")}, reverse=True)
        self.month_menu.configure(values=["All months"] + months)
        overdue = sum(1 for due, _, _ in todo if due <= today)
        self.status.configure(text=f"{len(result)} clients with records  ·  {len(todo)} to do"
                                   + (f"  ·  {overdue} due now" if overdue else ""))
        self.fill_policies()

    def fill_policies(self):
        self.pol.delete(*self.pol.get_children())
        status, line, month = self.f_status.get(), self.f_line.get(), self.f_month.get()
        total, count = 0.0, 0
        self._pol_folders = {}
        for folder, data in self.items:
            for p in data["policies"]:
                if status == "Bound / Active" and p.get("status") not in ("Bound", "Active", "Renewed"):
                    continue
                if status not in ("Bound / Active", "All statuses") and p.get("status") != status:
                    continue
                if line != "All lines" and p.get("line") != line:
                    continue
                if month != "All months" and not (p.get("effective") or "").startswith(month):
                    continue
                iid = f"{folder}|{p['id']}"
                self._pol_folders[iid] = folder
                self.pol.insert("", "end", iid=iid, values=[folder.name] + [
                    show_value("policies", k, p.get(k)) for k in
                    ("line", "status", "insurer", "policy_number", "effective", "expiry", "premium", "plan", "by")])
                total += records.money(p.get("premium"))
                count += 1
        self.totals.configure(text=f"{count} polic{'y' if count == 1 else 'ies'}  ·  ${total:,.2f} premium")

    def open_client(self, tree, tab):
        sel = tree.selection()
        if not sel:
            return
        folder = (self._todo_folders if tree is self.todo else self._pol_folders).get(sel[0])
        if folder:
            if folder in self.app.client_type_of:
                self.app.select(folder)
            ClientRecordDialog(self.app, folder, tab=tab)
