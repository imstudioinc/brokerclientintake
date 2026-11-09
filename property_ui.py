"""Home / tenant pages: Property details (the form), Review property (who will take it) and the Entry sheet.

All three read the client's saved answers (tracking.json "property_intake", see property_risk.py) in a thread -
the window never reads client files itself.
"""
import sys
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

import carriers_ui
import mvr_email
import commercial_risk
import property_risk as risk
import records
import tracker_ui
from panel import Panel

FIELD_W = 380            # every text box and drop-down in a form column is this wide, so the edges line up
LEVEL_WORD = {"decline": "Won't take it", "refer": "Refer", "caution": "Check"}


def _ui(app):
    return sys.modules[type(app).__module__]


def _kind(app, folder):
    return app.client_type_of.get(Path(folder), "Home")


def _card(parent, ui, row, title=None, column=0, pady=(0, 2 * 8)):
    card = ctk.CTkFrame(parent, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
    card.grid(row=row, column=column, sticky="new", padx=ui.SP, pady=pady)
    card.grid_columnconfigure(0, weight=1)
    if title:
        ctk.CTkLabel(card, text=title.upper(), font=ui.font(11, "bold"), text_color=ui.MUTED, anchor="w") \
            .grid(row=0, column=0, sticky="w", padx=2 * ui.SP, pady=(1.5 * ui.SP, ui.SP / 2))
    return card


# ============================================================ property details (the form)
class PropertyDetailsPage(Panel):
    """What the client's property is like. The review, the documents list and the entry sheet use these answers."""

    def __init__(self, app, folder, on_saved=None):
        super().__init__(app)
        self.app, self.folder, self.on_saved = app, Path(folder), on_saved
        ui = self.ui = _ui(app)
        self.kind = _kind(app, folder)
        self.risk = commercial_risk if self.kind == "Commercial" else risk       # the questions asked
        self.title({"Tenant": "Tenant details", "Commercial": "Commercial details"}.get(self.kind, "Property details")
                   + f" - {self.folder.name}")
        self.geometry("1000x820")
        self.values, self.inputs, self.open, self.built = {}, {}, {}, {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
        top.grid(row=0, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text=getattr(self.risk, "PICK_LABEL", "What is being insured"), font=ui.font(13, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, sticky="w", padx=(2 * ui.SP, ui.SP), pady=ui.SP)
        self.dwelling = tk.StringVar(value="")
        ctk.CTkOptionMenu(top, values=self.risk.DWELLING, variable=self.dwelling, width=300, height=34, font=ui.font(13),
                          dropdown_font=ui.font(13), fg_color=ui.SURFACE_ALT, button_color=ui.SURFACE_ALT,
                          button_hover_color=ui.BORDER, text_color=ui.TEXT, dynamic_resizing=False,
                          command=lambda _: self.kind_changed()).grid(row=0, column=1, sticky="w", pady=ui.SP)
        self.count = ctk.CTkLabel(top, text="Loading…", font=ui.font(13), text_color=ui.MUTED, anchor="e")
        self.count.grid(row=0, column=2, sticky="e", padx=2 * ui.SP)
        bar = ctk.CTkFrame(top, fg_color="transparent")
        bar.grid(row=0, column=3, sticky="e", padx=(0, 2 * ui.SP))
        if self.kind != "Commercial":
            app.secondary_button(bar, "Save and review", lambda: self.save(review=True), width=140).pack(side="left", padx=(0, ui.SP))
        self.save_btn = ctk.CTkButton(bar, text="Save", width=100, height=36, font=ui.font(14, "bold"),
                                      fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER, command=self.save)
        self.save_btn.pack(side="left")

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self.error = ctk.CTkLabel(self, text="", font=ui.font(13), text_color=ui.DANGER, anchor="w")
        self.error.grid(row=2, column=0, sticky="ew", padx=ui.SP * 2)
        self.bind("<Escape>", lambda e: self.destroy())
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        values = self.risk.load(self.folder)
        try:                                   # start from what the ARS quote already says (empty answers only)
            import property_quote, review
            quotes = review.find_docs(self.folder)["quote"] if self.kind != "Commercial" else []
            if quotes:
                q = property_quote.read(str(quotes[0]))
                values = property_quote.prefill(values, q.get("answers", {}))
        except Exception:
            pass
        self.app.ui(self._loaded, values)

    def _loaded(self, values):
        if not self.winfo_exists():
            return
        self.values = values
        if not values.get("dwelling"):
            self.values["dwelling"] = ("" if self.kind == "Commercial" else
                                       self.risk.DWELLING[2] if self.kind == "Tenant" else self.risk.DWELLING[0])
        self.dwelling.set(self.values["dwelling"])
        self.open = {"about": True}
        self.build()

    # ----- sections
    def kind_changed(self):
        self.collect()
        self.values["dwelling"] = self.dwelling.get()
        self.build()

    def build(self):
        ui = self.ui
        for w in self.body.winfo_children():
            w.destroy()
        self.inputs, self.sections = {}, {}
        use = self.risk.use_of(self.values)
        for r, (key, title, fields) in enumerate(self.risk.fields_for(use)):
            fields = [f for f in fields if f[0] != "dwelling"]          # the picker at the top is that question
            wrap = ctk.CTkFrame(self.body, fg_color="transparent")
            wrap.grid(row=r, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
            wrap.grid_columnconfigure(0, weight=1)
            head = ctk.CTkButton(wrap, text="", anchor="w", height=40, font=ui.font(14, "bold"), text_color=ui.TEXT,
                                 fg_color=ui.SURFACE, hover_color=ui.SURFACE_ALT, border_width=1,
                                 border_color=ui.BORDER, corner_radius=10,
                                 command=lambda k=key: self.toggle(k))
            head.grid(row=0, column=0, sticky="ew")
            box = ctk.CTkFrame(wrap, fg_color=ui.SURFACE, corner_radius=10, border_width=1, border_color=ui.BORDER)
            box.grid_columnconfigure((0, 1), weight=1, uniform="cell")
            self.sections[key] = {"head": head, "box": box, "title": title, "fields": fields, "built": False}
            self.show_section(key)
        self.refresh_count()

    def toggle(self, key):
        self.collect()
        self.open[key] = not self.open.get(key, False)
        self.show_section(key)

    def show_section(self, key):
        ui, s = self.ui, self.sections[key]
        opened = self.open.get(key, False)
        answered = sum(1 for f in s["fields"] if self.values.get(f[0]) not in (None, ""))
        s["head"].configure(text=f"{'▾' if opened else '▸'}   {s['title']}      {answered} of {len(s['fields'])}")
        if opened:
            if not s["built"]:
                self.fill_section(key)
            s["box"].grid(row=1, column=0, sticky="ew", pady=(ui.SP / 2, 0))
        else:
            s["box"].grid_remove()

    def fill_section(self, key):
        ui, s = self.ui, self.sections[key]
        s["built"] = True
        for i, (k, label, kind, options, _uses, hint) in enumerate(s["fields"]):
            cell = ctk.CTkFrame(s["box"], fg_color="transparent")
            cell.grid(row=i // 2, column=i % 2, sticky="new", padx=(2 * ui.SP, 2 * ui.SP), pady=(1.5 * ui.SP, 0))
            cell.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(cell, text=label, font=ui.font(13), text_color=ui.TEXT, anchor="w", justify="left",
                         wraplength=380).grid(row=0, column=0, sticky="w")
            value = self.values.get(k, "")
            self.inputs[k] = self.control(cell, kind, options, value)
            self.inputs[k][3].grid(row=1, column=0, sticky="w", pady=(2, 0))
            if hint:
                ctk.CTkLabel(cell, text=hint, font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left",
                             wraplength=380).grid(row=2, column=0, sticky="w")
        ctk.CTkFrame(s["box"], fg_color="transparent", height=ui.SP).grid(row=len(s["fields"]) // 2 + 1, column=0)

    def control(self, parent, kind, options, value):
        """(kind, getter, setter, widget) for one question."""
        ui = self.ui
        if kind == "choice":
            var = tk.StringVar(value=value)
            w = ctk.CTkOptionMenu(parent, values=[""] + list(options), variable=var, width=FIELD_W, height=36,
                                  corner_radius=8, font=ui.font(13), dropdown_font=ui.font(13), fg_color=ui.SURFACE_ALT,
                                  button_color=ui.SURFACE_ALT, button_hover_color=ui.BORDER, text_color=ui.TEXT,
                                  dynamic_resizing=False)
            return kind, var.get, var.set, w
        if kind == "yn":
            import ui_kit
            w = ui_kit.YesNo(parent, ui, value)               # Yes green with a tick, No slate with a cross
            return kind, w.get, w.set, w
        if kind == "date":
            w = tracker_ui.DateField(parent, ui)
            day = records.parse_date(value) if value else None
            if day:
                w.insert(0, day.strftime("%b %d, %Y").replace(" 0", " "))
            return kind, w.get, lambda v: (w.delete(0, "end"), w.insert(0, v)), w
        if kind == "long":
            w = ctk.CTkTextbox(parent, width=620, height=78, font=ui.font(13), border_width=1, border_color=ui.BORDER,
                               wrap="word")
            w.insert("1.0", value)
            return kind, lambda: w.get("1.0", "end").strip(), lambda v: (w.delete("1.0", "end"), w.insert("1.0", v)), w
        width = {"text": FIELD_W, "num": 150, "year": 150, "money": 190}.get(kind, 200)
        w = ctk.CTkEntry(parent, width=width, height=36, corner_radius=8, font=ui.font(13), border_color=ui.BORDER)
        if value:
            w.insert(0, value)
        return kind, lambda: w.get().strip(), lambda v: (w.delete(0, "end"), w.insert(0, v)), w

    def collect(self):
        """Copy what is typed into the form into self.values (sections never opened keep their saved answers)."""
        for key, (kind, get, _set, _w) in self.inputs.items():
            v = get()
            if kind == "date" and v:
                day = records.parse_date(v)
                v = day.isoformat() if day else v
            if kind == "money" and v:
                v = f"{records.money(v):.0f}" if records.money(v) else v
            self.values[key] = v
        self.values["dwelling"] = self.dwelling.get() or self.values.get("dwelling", "")

    def refresh_count(self):
        done, total, missing = self.risk.completeness(self.values)
        self.count.configure(text=f"{done} of {total} answered" + ("" if not missing else f" - still: {missing[0].lower()}"
                                                                    + (" ..." if len(missing) > 1 else "")),
                             text_color=self.ui.SUCCESS if not missing else self.ui.MUTED)

    # ----- save
    def save(self, review=False):
        self.collect()
        year = self.values.get("year_built", "")
        if year and not (year.isdigit() and 1700 < int(year) <= 2100):
            self.error.configure(text=f"Year built should be a year like 1985 (got {year}).")
            return
        self.error.configure(text="")
        self.save_btn.configure(state="disabled", text="Saving…")
        values = dict(self.values)

        def work():
            try:
                saved = self.risk.save(self.folder, values)
            except OSError as e:
                self.app.ui(self._failed, str(e))
                return
            self.app.ui(self._saved, saved, review)
        threading.Thread(target=work, daemon=True).start()

    def _failed(self, message):
        if self.winfo_exists():
            self.save_btn.configure(state="normal", text="Save")
            self.error.configure(text=f"Could not save (is the shared drive available?) {message}")

    def _saved(self, values, review):
        done, total, _ = self.risk.completeness(values)
        app, folder, callback = self.app, self.folder, self.on_saved
        if self.winfo_exists():
            self.destroy()
        app.client_changed(folder)
        app.tracker_changed()
        app.show_note(folder, f"✓ {'Commercial' if self.kind == 'Commercial' else 'Property'} details saved ({done} of {total} answered)", _ui(app).SUCCESS)
        if callback:
            callback()
        if review and self.kind != "Commercial":
            PropertyReviewPage(app, folder)


# ============================================================ review property
class PropertyReviewPage(Panel):
    """Which markets will take this property, what to refer, and what is still needed."""

    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = _ui(app)
        self.kind = _kind(app, folder)
        self.title(f"Review property - {self.folder.name}")
        self.geometry("1100x820")
        self.grid_columnconfigure(0, weight=3, uniform="c")
        self.grid_columnconfigure(1, weight=2, uniform="c")
        self.grid_rowconfigure(1, weight=1)
        self.text = ""

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
        top.grid_columnconfigure(0, weight=1)
        self.verdict = ctk.CTkLabel(top, text="Reading the property details…", font=ui.font(16, "bold"),
                                    text_color=ui.TEXT, anchor="w", justify="left", wraplength=640)
        self.verdict.grid(row=0, column=0, sticky="w")
        app.secondary_button(top, "Edit details", self.edit, width=120).grid(row=0, column=1, padx=(ui.SP, 0))
        self.copy_btn = app.secondary_button(top, "Copy summary", lambda: self.text and carriers_ui.copy(
            app, self.text, self.copy_btn), width=130)
        self.copy_btn.grid(row=0, column=2, padx=(ui.SP, 0))

        self.left = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.left.grid(row=1, column=0, sticky="nsew")
        self.left.grid_columnconfigure(0, weight=1)
        self.right = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.right.grid(row=1, column=1, sticky="nsew")
        self.right.grid_columnconfigure(0, weight=1)
        self.bind("<Escape>", lambda e: self.destroy())
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        values = risk.load(self.folder)
        result = risk.review(values, risk.load_rules(self.app.cfg))
        docs = self.ui.find_docs(self.folder, self.kind)
        self.app.ui(self._show, values, result, docs)

    def edit(self):
        self.destroy()
        PropertyDetailsPage(self.app, self.folder)

    def _show(self, values, r, docs):
        if not self.winfo_exists():
            return
        ui = self.ui
        if not values:
            self.verdict.configure(text="No property details yet - fill them in first.")
            self.app.secondary_button(self.left, "Fill in the property details", self.edit, width=240) \
                .grid(row=0, column=0, pady=3 * ui.SP)
            return
        markets = r["markets"]
        counts = {k: sum(1 for m in markets if m["verdict"] == k) for k in risk.RANK}
        if r["have_rules"]:
            fit = counts["fits"] + counts["caution"]
            self.verdict.configure(
                text=f"{fit} of {len(markets)} markets can take it as it stands"
                     f"   ·   {counts['refer']} to refer first   ·   {counts['decline']} won't take it",
                text_color=ui.SUCCESS if fit else ui.WARN)
        else:
            self.verdict.configure(text="The carriers' rules file wasn't found - only the checks on the right are shown.",
                                   text_color=ui.WARN)
        lines = [f"Property review - {self.folder.name}"]
        row = 0
        for m in markets:
            row = self._market(row, m)
            lines.append(f"{m['name']}: {risk.VERDICT_TEXT[m['verdict']]}" + "".join(
                f"\n   - {LEVEL_WORD[l]}: {t}" for l, t in m["findings"]))
        if not r["have_rules"]:
            card = _card(self.left, ui, 0, "Carrier rules")
            ctk.CTkLabel(card, text="Put property_rules.json in the Underwriting Knowledge folder:\n"
                         + str(risk.rules_path(self.app.cfg)), font=ui.font(13), text_color=ui.MUTED, anchor="w",
                         justify="left", wraplength=520).grid(row=1, column=0, sticky="w", padx=2 * ui.SP, pady=(0, ui.SP))
        self.text = "\n".join(lines)
        self._checks(r, docs)

    def _market(self, row, m):
        ui = self.ui
        color = {"fits": ui.SUCCESS, "caution": ui.WARN, "refer": ui.WARN, "decline": ui.DANGER}[m["verdict"]]
        card = _card(self.left, ui, row, pady=(0, ui.SP))
        card.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=2 * ui.SP, pady=(ui.SP, 2))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text=m["name"], font=ui.font(15, "bold"), text_color=ui.TEXT).grid(row=0, column=0, sticky="w")
        if m["tier"] != "standard":
            ctk.CTkLabel(head, text="specialty market", font=ui.font(12), text_color=ui.MUTED) \
                .grid(row=0, column=1, sticky="w", padx=ui.SP)
        ctk.CTkLabel(head, text=risk.VERDICT_TEXT[m["verdict"]], font=ui.font(13, "bold"), text_color=color) \
            .grid(row=0, column=2, sticky="e")
        r = 1
        for level, text in m["findings"]:
            c = {"decline": ui.DANGER, "refer": ui.WARN, "caution": ui.MUTED}[level]
            ctk.CTkLabel(card, text=f"{LEVEL_WORD[level]}:  {text}", font=ui.font(13), text_color=c, anchor="w",
                         justify="left", wraplength=540).grid(row=r, column=0, sticky="w", padx=2 * ui.SP, pady=1)
            r += 1
        if m["note"] and m["verdict"] in ("fits", "caution"):
            ctk.CTkLabel(card, text=m["note"], font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=540).grid(row=r, column=0, sticky="w", padx=2 * ui.SP, pady=(2, 0))
            r += 1
        ctk.CTkFrame(card, fg_color="transparent", height=ui.SP / 2).grid(row=r, column=0)
        return row + 1

    def _checks(self, r, docs):
        ui = self.ui
        n = 0
        card = _card(self.right, ui, n, "WellCare's own rules")
        if r["wellcare"]:
            for i, (level, text) in enumerate(r["wellcare"], start=1):
                c = {"decline": ui.DANGER, "refer": ui.WARN, "caution": ui.WARN}[level]
                ctk.CTkLabel(card, text=f"{LEVEL_WORD[level]}:  {text}", font=ui.font(13), text_color=c, anchor="w",
                             justify="left", wraplength=380).grid(row=i, column=0, sticky="w", padx=2 * ui.SP, pady=1)
            ctk.CTkFrame(card, fg_color="transparent", height=ui.SP).grid(row=len(r["wellcare"]) + 1, column=0)
        else:
            ctk.CTkLabel(card, text="Nothing to flag.", font=ui.font(13), text_color=ui.MUTED, anchor="w") \
                .grid(row=1, column=0, sticky="w", padx=2 * ui.SP, pady=(0, ui.SP))
        n += 1
        card = _card(self.right, ui, n, f"Still to answer ({r['filled']} of {r['total']} done)")
        if r["missing"]:
            ctk.CTkLabel(card, text="•  " + "\n•  ".join(r["missing"]), font=ui.font(13), text_color=ui.WARN, anchor="w",
                         justify="left", wraplength=380).grid(row=1, column=0, sticky="w", padx=2 * ui.SP)
            self.app.secondary_button(card, "Fill in", self.edit, width=90, height=30).grid(
                row=2, column=0, sticky="w", padx=2 * ui.SP, pady=ui.SP)
        else:
            ctk.CTkLabel(card, text="All answered.", font=ui.font(13), text_color=ui.SUCCESS, anchor="w") \
                .grid(row=1, column=0, sticky="w", padx=2 * ui.SP, pady=(0, ui.SP))
        n += 1
        card = _card(self.right, ui, n, "Documents this property needs")
        need = r["docs"]
        if need:
            for i, (label, why) in enumerate(need.items(), start=1):
                have = bool(docs.get(label))
                ctk.CTkLabel(card, text=("✓  " if have else "○  ") + label, font=ui.font(13, "bold"),
                             text_color=ui.SUCCESS if have else ui.TEXT, anchor="w").grid(
                    row=2 * i - 1, column=0, sticky="w", padx=2 * ui.SP, pady=(ui.SP / 2, 0))
                ctk.CTkLabel(card, text=why, font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left",
                             wraplength=380).grid(row=2 * i, column=0, sticky="w", padx=(4 * ui.SP, 2 * ui.SP))
            ctk.CTkFrame(card, fg_color="transparent", height=ui.SP).grid(row=2 * len(need) + 1, column=0)
        else:
            ctk.CTkLabel(card, text="Nothing extra for what is filled in so far.", font=ui.font(13),
                         text_color=ui.MUTED, anchor="w").grid(row=1, column=0, sticky="w", padx=2 * ui.SP,
                                                                  pady=(0, ui.SP))


# ============================================================ entry sheet
class PropertyEntryPage(Panel):
    """What to type where: Applied Quote and the PowerBroker habitational screens, from the saved answers."""

    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = _ui(app)
        self.title(f"Entry sheet - {self.folder.name}")
        self.geometry("1000x820")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.text = ""
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
        top.grid_columnconfigure(0, weight=1)
        self.note = ctk.CTkLabel(top, text="Reading the property details…", font=ui.font(13), text_color=ui.MUTED,
                                 anchor="w", justify="left", wraplength=620)
        self.note.grid(row=0, column=0, sticky="w")
        app.secondary_button(top, "Edit details", self.edit, width=120).grid(row=0, column=1, padx=(ui.SP, 0))
        self.copy_all = ctk.CTkButton(top, text="Copy all as text", height=34, width=150, font=ui.font(13, "bold"),
                                      fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER,
                                      command=lambda: self.text and carriers_ui.copy(app, self.text, self.copy_all))
        self.copy_all.grid(row=0, column=2, padx=(ui.SP, 0))
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self.bind("<Escape>", lambda e: self.destroy())
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        values = risk.load(self.folder)
        info = mvr_email.load_client(self.folder)
        self.app.ui(self._show, values, risk.entry_sections(values, info))

    def edit(self):
        self.destroy()
        PropertyDetailsPage(self.app, self.folder)

    def _show(self, values, sections):
        if not self.winfo_exists():
            return
        ui = self.ui
        self.text = risk.entry_text(sections)
        gaps = sum(1 for _, rows in sections for _, v in rows if not v)
        self.note.configure(text=("The property details are empty - fill them in first." if not values else
                                  "Type these into Applied Quote and PowerBroker, screen by screen. Amber = not answered yet."))
        for r, (title, rows) in enumerate(sections):
            card = _card(self.body, ui, r, title)
            card.grid_columnconfigure(1, weight=1)
            for i, (label, value) in enumerate(rows, start=1):
                ctk.CTkLabel(card, text=label, font=ui.font(13), text_color=ui.MUTED, anchor="w", justify="left",
                             wraplength=330).grid(row=i, column=0, sticky="w", padx=(2 * ui.SP, ui.SP), pady=1)
                ctk.CTkLabel(card, text=value or "—", font=ui.font(13, "bold"),
                             text_color=ui.TEXT if value else ui.WARN, anchor="w", justify="left",
                             wraplength=400).grid(row=i, column=1, sticky="w", pady=1)
                if value:
                    b = ctk.CTkButton(card, text="Copy", width=56, height=24, font=ui.font(12), fg_color="transparent",
                                      border_width=1, border_color=ui.BORDER, text_color=ui.TEXT,
                                      hover_color=ui.SURFACE_ALT)
                    b.configure(command=lambda v=value, b=b: carriers_ui.copy(self.app, v, b))
                    b.grid(row=i, column=2, sticky="e", padx=(ui.SP, 2 * ui.SP), pady=1)
            ctk.CTkFrame(card, fg_color="transparent", height=ui.SP / 2).grid(row=len(rows) + 1, column=0)
