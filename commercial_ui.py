"""Commercial details page: every question on WellCare's Commercial Insurance Application, and the button that fills the
application PDF from the answers (commercial_app.py).

It is the Property details page (property_ui.PropertyDetailsPage: top bar, loading and saving in threads, collapsible
sections) with a few additions: grids for the contacts / claims / exposures / items, the schedule of coverages, tick-lists
for the form's check boxes, and the **Liability only** switch. While that switch is on, the property side of the
application (locations, construction, renovations, protection, property coverage, items) is hidden here exactly as the
PDF drops those pages, those answers are kept but not counted or printed.
"""
import os
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

import brokers
import commercial_app
import commercial_risk as risk
import property_ui


def fill_application(app, folder, values=None):
    """Fill the application PDF from the saved answers (in a thread) and tell the owner; opens the PDF."""
    folder = Path(folder)
    ui = property_ui._ui(app)

    def work():
        try:
            data = brokers.apply_defaults(app.cfg, risk.load(folder) if values is None else values)
            path = commercial_app.fill(folder, data)
        except Exception as e:                                   # a locked file, the shared drive gone ...
            app.ui(lambda: app.show_note(folder, f"Could not fill the application: {e}", ui.DANGER))
            return
        liability = risk.is_liability_only(data)
        pages = 3 if liability else 6 + sum(1 for n in (2, 3) if commercial_app.has_location(data, n))
        app.ui(done, path, pages, liability)

    def done(path, pages, liability):
        app.client_changed(folder)
        app.show_note(folder, f"✓ Application filled: {path.name}\n{pages} pages"
                              + (" (liability only: no property pages)" if liability else "")
                              + " - check it, then print and sign it.", ui.SUCCESS)
        try:
            os.startfile(path)
        except OSError:
            pass
    threading.Thread(target=work, daemon=True).start()


class CommercialDetailsPage(property_ui.PropertyDetailsPage):
    """The Commercial details form (see the module note)."""

    def __init__(self, app, folder, on_saved=None):
        self.fill_after = False
        self.sections = {}
        super().__init__(app, folder, on_saved)
        ui = self.ui
        top = self.count.master
        self.liab = tk.BooleanVar(value=False)
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.grid(row=1, column=0, columnspan=4, sticky="ew", padx=2 * ui.SP, pady=(0, ui.SP))
        self.liab_switch = ctk.CTkSwitch(row, text="Liability only", variable=self.liab, font=ui.font(13, "bold"),
                                         text_color=ui.TEXT, command=self.liability_changed, progress_color=ui.ACCENT)
        self.liab_switch.pack(side="left")
        self.liab_note = ctk.CTkLabel(row, text="", font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left")
        self.liab_note.pack(side="left", padx=(2 * ui.SP, 0))
        bar = self.save_btn.master
        app.secondary_button(bar, "Save and fill application", self.save_and_fill, width=200).pack(
            side="left", padx=(0, ui.SP), before=self.save_btn)

    # ----- loading
    def _loaded(self, values):
        if not self.winfo_exists():
            return
        self.values = brokers.apply_defaults(self.app.cfg, values)       # broker name / branch number from the profile
        self.dwelling.set(values.get("dwelling", ""))
        self.liab.set(risk.is_liability_only(values))
        self.open = {"about": True}
        self.build()

    # ----- the liability-only switch
    def liability_changed(self):
        self.collect()
        self.values["liability_only"] = "Yes" if self.liab.get() else ""
        self.apply_liability()
        self.refresh_count()

    def apply_liability(self):
        on = risk.is_liability_only(self.values)
        for key, s in self.sections.items():
            if risk.section_visible(s["flags"], self.values):
                s["wrap"].grid()
            else:
                s["wrap"].grid_remove()
        self.liab_note.configure(
            text=("Locations, construction, renovations, protection, property coverage and items are hidden and left off "
                  "the application (it keeps the cover page, the liability page and the liability schedule)." if on else
                  "Tick this when only liability is being insured: the application then has no property pages."))

    # ----- sections
    def build(self):
        ui = self.ui
        for w in self.body.winfo_children():
            w.destroy()
        self.inputs, self.sections = {}, {}
        for r, (key, title, items, flags) in enumerate(risk.SECTIONS):
            items = [i for i in items if not (isinstance(i, tuple) and i[0] == "dwelling")]   # the picker at the top
            wrap = ctk.CTkFrame(self.body, fg_color="transparent")
            wrap.grid(row=r, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
            wrap.grid_columnconfigure(0, weight=1)
            head = ctk.CTkButton(wrap, text="", anchor="w", height=40, font=ui.font(14, "bold"), text_color=ui.TEXT,
                                 fg_color=ui.SURFACE, hover_color=ui.SURFACE_ALT, border_width=1,
                                 border_color=ui.BORDER, corner_radius=10, command=lambda k=key: self.toggle(k))
            head.grid(row=0, column=0, sticky="ew")
            box = ctk.CTkFrame(wrap, fg_color=ui.SURFACE, corner_radius=10, border_width=1, border_color=ui.BORDER)
            box.grid_columnconfigure((0, 1), weight=1, uniform="cell")
            self.sections[key] = {"head": head, "box": box, "title": title, "items": items, "flags": flags,
                                  "wrap": wrap, "keys": risk.section_keys(items), "built": False}
            self.show_section(key)
        self.apply_liability()
        self.refresh_count()

    def show_section(self, key):
        ui, s = self.ui, self.sections[key]
        opened = self.open.get(key, False)
        answered = sum(1 for k in s["keys"] if risk.is_answered(self.values, k))
        s["head"].configure(text=f"{'▾' if opened else '▸'}   {s['title']}      {answered} of {len(s['keys'])}")
        if opened:
            if not s["built"]:
                self.fill_section(key)
            s["box"].grid(row=1, column=0, sticky="ew", pady=(ui.SP / 2, 0))
        else:
            s["box"].grid_remove()

    def fill_section(self, key):
        ui, s = self.ui, self.sections[key]
        s["built"] = True
        box, row, col = s["box"], 0, 0
        for item in s["items"]:
            if isinstance(item, tuple):
                k, label, kind, options, _uses, hint = item
                wide = kind in ("multi", "long")
                if wide and col:
                    row, col = row + 1, 0
                cell = ctk.CTkFrame(box, fg_color="transparent")
                cell.grid(row=row, column=col, columnspan=2 if wide else 1, sticky="new",
                          padx=(2 * ui.SP, 2 * ui.SP), pady=(1.5 * ui.SP, 0))
                cell.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(cell, text=label, font=ui.font(13), text_color=ui.TEXT, anchor="w", justify="left",
                             wraplength=760 if wide else 380).grid(row=0, column=0, sticky="w")
                self.inputs[k] = self.control(cell, kind, options, self.values.get(k, ""))
                self.inputs[k][3].grid(row=1, column=0, sticky="w", pady=(2, 0))
                if k in risk.UPPER_KEYS:                          # codes and postal codes are always capitals
                    self.make_upper(self.inputs[k][3])
                if hint:
                    ctk.CTkLabel(cell, text=hint, font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left",
                                 wraplength=760 if wide else 380).grid(row=2, column=0, sticky="w")
                if wide:
                    row, col = row + 1, 0
                else:
                    row, col = (row + 1, 0) if col else (row, 1)
                continue
            if col:
                row, col = row + 1, 0
            frame = ctk.CTkFrame(box, fg_color="transparent")
            frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=2 * ui.SP, pady=(ui.SP, 0))
            if "table" in item:
                self.draw_table(frame, item)
            else:
                self.draw_schedule(frame, item)
            row += 1
        ctk.CTkFrame(box, fg_color="transparent", height=ui.SP).grid(row=row + 1, column=0)

    # ----- grids
    def cell(self, parent, kind, options, value, width):
        """(kind, getter, setter, widget) for one box of a grid."""
        ui = self.ui
        if kind == "check":
            var = tk.BooleanVar(value=value == "Yes")
            w = ctk.CTkCheckBox(parent, text="", variable=var, width=24, checkbox_width=22, checkbox_height=22)
            return kind, lambda: "Yes" if var.get() else "", lambda v: var.set(v == "Yes"), w
        if kind == "date":                                        # a date picker in a grid cell (small ▾ button)
            import tracker_ui
            w = tracker_ui.DateField(parent, self.ui, compact=True)
            w.entry.configure(width=max(80, width - 44), height=30)
            if value:
                w.insert(0, value)
            return kind, w.get, lambda v: (w.delete(0, "end"), w.insert(0, v)), w
        if kind == "choice":
            var = tk.StringVar(value=value)
            w = ctk.CTkOptionMenu(parent, values=[""] + list(options), variable=var, width=width, height=30,
                                  font=ui.font(12), dropdown_font=ui.font(13), fg_color=ui.SURFACE_ALT,
                                  button_color=ui.SURFACE_ALT, button_hover_color=ui.BORDER, text_color=ui.TEXT,
                                  dynamic_resizing=False)
            return kind, var.get, var.set, w
        w = ctk.CTkEntry(parent, width=width, height=30, font=ui.font(12), border_color=ui.BORDER)
        if value:
            w.insert(0, value)
        return kind, lambda: w.get().strip(), lambda v: (w.delete(0, "end"), w.insert(0, v)), w

    def draw_table(self, frame, item):
        ui = self.ui
        ctk.CTkLabel(frame, text=item["title"], font=ui.font(13, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=0, column=0, columnspan=len(item["cols"]) + 1, sticky="w")
        labelled = item["table"].endswith("_")                    # named rows (left / right ...) vs numbered rows
        for c, col in enumerate(item["cols"], start=1):
            ctk.CTkLabel(frame, text=col[1], font=ui.font(12, "bold"), text_color=ui.MUTED, anchor="w") \
                .grid(row=1, column=c, sticky="w", padx=2)
        for r, (rk, rlabel) in enumerate(item["rows"], start=2):
            ctk.CTkLabel(frame, text=rlabel if labelled else rk, font=ui.font(12), text_color=ui.MUTED, anchor="w",
                         width=120 if labelled else 18).grid(row=r, column=0, sticky="w", padx=(0, 4), pady=1)
            for c, (suffix, _h, kind, options, width) in enumerate(item["cols"], start=1):
                k = f"{item['table']}{rk}_{suffix}"
                self.inputs[k] = self.cell(frame, "text" if kind == "money" else kind, options,
                                           self.values.get(k, ""), width)
                self.inputs[k][3].grid(row=r, column=c, padx=2, pady=1, sticky="w")

    def draw_schedule(self, frame, item):
        ui = self.ui
        ctk.CTkLabel(frame, text=item["title"], font=ui.font(13, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=0, column=0, columnspan=5, sticky="w")
        for c, text in enumerate(["", "", "Broad / Named / basis", "Deductible", "Limit"]):
            ctk.CTkLabel(frame, text=text, font=ui.font(12, "bold"), text_color=ui.MUTED, anchor="w") \
                .grid(row=1, column=c, sticky="w", padx=2)
        r = 2
        for row_key, label, basis, group in risk.SCHEDULE:
            if group != item["schedule"]:
                continue
            keys = risk.schedule_keys(row_key)
            self.inputs[keys["inc"]] = self.cell(frame, "check", None, self.values.get(keys["inc"], ""), 24)
            self.inputs[keys["inc"]][3].grid(row=r, column=0, padx=(0, 4), pady=1)
            if "desc" in keys:
                self.inputs[keys["desc"]] = self.cell(frame, "text", None, self.values.get(keys["desc"], ""), 300)
                self.inputs[keys["desc"]][3].grid(row=r, column=1, padx=2, pady=1, sticky="w")
            else:
                ctk.CTkLabel(frame, text=label, font=ui.font(13), text_color=ui.TEXT, anchor="w", width=300) \
                    .grid(row=r, column=1, sticky="w", padx=2, pady=1)
            choices = risk.BASIS_CHOICES.get(basis)
            self.inputs[keys["basis"]] = self.cell(frame, "choice" if choices else "text", choices,
                                                   self.values.get(keys["basis"], ""), 190)
            self.inputs[keys["basis"]][3].grid(row=r, column=2, padx=2, pady=1, sticky="w")
            self.inputs[keys["ded"]] = self.cell(frame, "text", None, self.values.get(keys["ded"], ""), 110)
            self.inputs[keys["ded"]][3].grid(row=r, column=3, padx=2, pady=1, sticky="w")
            self.inputs[keys["limit"]] = self.cell(frame, "text", None, self.values.get(keys["limit"], ""), 140)
            self.inputs[keys["limit"]][3].grid(row=r, column=4, padx=2, pady=1, sticky="w")
            r += 1

    # ----- one question
    def control(self, parent, kind, options, value):
        ui = self.ui
        if kind == "multi":                                       # the form's check boxes: any number can be ticked
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            chosen = set(risk.multi_values(value))
            vars_ = []
            for i, option in enumerate(options):
                var = tk.BooleanVar(value=option in chosen)
                vars_.append((option, var))
                ctk.CTkCheckBox(frame, text=option, variable=var, font=ui.font(12), text_color=ui.TEXT,
                                checkbox_width=20, checkbox_height=20).grid(row=i // 2, column=i % 2, sticky="w",
                                                                           padx=(0, 18), pady=2)

            def get():
                return risk.MULTI_SEP.join(o for o, v in vars_ if v.get())

            def put(text):
                picked = set(risk.multi_values(text))
                for o, v in vars_:
                    v.set(o in picked)
            return kind, get, put, frame
        return super().control(parent, kind, options, value)

    def make_upper(self, entry):
        def typed(_event):
            text = entry.get()
            if text != text.upper():
                pos = entry._entry.index("insert")
                entry.delete(0, "end")
                entry.insert(0, text.upper())
                entry._entry.icursor(pos)
        entry.bind("<KeyRelease>", typed)

    def collect(self):
        super().collect()
        self.values["liability_only"] = "Yes" if self.liab.get() else ""
        for k in risk.UPPER_KEYS:
            if self.values.get(k):
                self.values[k] = self.values[k].upper()

    def save(self, review=False):
        self.collect()
        bad = risk.bad_emails(self.values)
        if bad:
            self.fill_after = False
            self.error.configure(text="That doesn't look like an email address: " + ", ".join(bad))
            return
        super().save(review)

    # ----- save (and fill)
    def save_and_fill(self):
        self.fill_after = True
        self.save()

    def _failed(self, message):
        self.fill_after = False
        super()._failed(message)

    def _saved(self, values, review):
        fill, app, folder = self.fill_after, self.app, self.folder
        super()._saved(values, review)
        if fill:
            fill_application(app, folder, values)
