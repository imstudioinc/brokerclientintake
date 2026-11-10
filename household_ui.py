"""Household page: who drives, what they drive. One client folder = one household (see household.py).

Three cards: People (the main client is first and fixed; add a spouse, children, a parent, anyone), Cars, and a table
"Who drives what" (person x car: Principal / Occasional / Excluded) with the problems it finds (a car without a principal
driver ...). "Fill from the ARS quote" adds the drivers and vehicles the newest quote lists. Save sits at the bottom.
"""
import sys
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

import household
import records
import tracker_ui
from carriers_ui import copy
from panel import Panel


class HouseholdPage(Panel):
    def __init__(self, app, folder, on_saved=None):
        super().__init__(app)
        self.app, self.folder, self.on_saved = app, Path(folder), on_saved
        ui = self.ui = sys.modules[type(app).__module__]
        self.title(f"Household - {self.folder.name}")
        self.geometry("1100x800")
        self.data = {"people": [], "cars": [], "roles": {}}
        self.rows_people, self.rows_cars, self.role_vars = [], [], {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.body, text="Loading…", font=ui.font(14), text_color=ui.MUTED).grid(row=0, column=0, padx=16, pady=16)

        bar = ctk.CTkFrame(self, fg_color="transparent", height=1)           # fixed at the bottom, never scrolls away
        bar.grid(row=1, column=0, sticky="ew", pady=(ui.SP, 0))
        bar.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(bar, text="", font=ui.font(13), text_color=ui.MUTED, anchor="w", justify="left",
                                   wraplength=520)
        self.status.grid(row=0, column=0, sticky="w", padx=ui.SP)
        self.copy_btn = app.secondary_button(bar, "Copy who drives what", self.copy_text, width=190)
        self.copy_btn.grid(row=0, column=1, padx=(0, ui.SP))
        self.quote_btn = app.secondary_button(bar, "Fill from the ARS quote", self.fill_from_quote, width=200)
        self.quote_btn.grid(row=0, column=2, padx=(0, ui.SP))
        self.save_btn = ctk.CTkButton(bar, text="Save", width=110, height=36, font=ui.font(14, "bold"),
                                      fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER, command=self.save)
        self.save_btn.grid(row=0, column=3)
        self.bind("<Escape>", lambda e: self.destroy())
        threading.Thread(target=lambda: app.ui(self._loaded, household.load(self.folder)), daemon=True).start()

    # ---------- building the page from self.data ----------
    def _loaded(self, data):
        if self.winfo_exists():
            self.data = data
            self.build()

    def _card(self, row, title, hint=""):
        ui = self.ui
        card = ctk.CTkFrame(self.body, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
        card.grid(row=row, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
        ctk.CTkLabel(card, text=title, font=ui.font(16, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=0, column=0, columnspan=6, sticky="w", padx=2 * ui.SP, pady=(ui.SP + 2, 0))
        if hint:
            ctk.CTkLabel(card, text=hint, font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left", wraplength=900) \
                .grid(row=1, column=0, columnspan=6, sticky="w", padx=2 * ui.SP)
        return card

    def _entry(self, parent, value, width, placeholder="", upper=False):
        ui = self.ui
        e = ctk.CTkEntry(parent, width=width, height=34, font=ui.font(13), border_color=ui.BORDER,
                         placeholder_text=placeholder)
        if value:
            e.insert(0, value)
        if upper:
            def typed(_e):
                text = e.get()
                if text != text.upper():
                    pos = e._entry.index("insert")
                    e.delete(0, "end")
                    e.insert(0, text.upper())
                    e._entry.icursor(pos)
            e.bind("<KeyRelease>", typed)
        return e

    def _menu(self, parent, values, var, width):
        ui = self.ui
        return ctk.CTkOptionMenu(parent, values=values, variable=var, width=width, height=34, font=ui.font(13),
                                 dropdown_font=ui.font(13), fg_color=ui.SURFACE_ALT, button_color=ui.SURFACE_ALT,
                                 button_hover_color=ui.BORDER, text_color=ui.TEXT, dynamic_resizing=False)

    def build(self):
        ui = self.ui
        for w in self.body.winfo_children():
            w.destroy()
        self.rows_people, self.rows_cars, self.role_vars = [], [], {}
        pad = 2 * ui.SP

        # ----- people
        card = self._card(0, "People", "The main client is the folder's name. Add everyone who drives or is insured with "
                                       "them: spouse, children, a parent. Surnames can differ. Each person's DASH and MVR "
                                       "go in this same folder (their name is in the file name or on the report).")
        for c, text in enumerate(["Name", "Relationship", "Licence #", "Date of birth"]):
            ctk.CTkLabel(card, text=text, font=ui.font(12, "bold"), text_color=ui.MUTED, anchor="w") \
                .grid(row=2, column=c, sticky="w", padx=(pad if c == 0 else 4, 4), pady=(ui.SP, 0))
        for r, p in enumerate(self.data["people"], start=3):
            main = p["id"] == household.MAIN
            name = self._entry(card, p["name"], 270, upper=True)
            if main:
                name.configure(state="disabled")
            rel = tk.StringVar(value="Main client" if main else (p.get("relation") or ""))
            if main:
                relw = ctk.CTkLabel(card, text="Main client", font=ui.font(13), text_color=ui.MUTED, width=170, anchor="w")
            else:
                relw = self._menu(card, [""] + household.RELATIONS, rel, 170)
            dln = self._entry(card, p.get("dln", ""), 210, "A1234-12345-12345", upper=True)
            dln.bind("<FocusOut>", lambda e, w=dln: self._format_dln(w), add="+")
            born = tracker_ui.DateField(card, ui, compact=True, height=34)
            day = records.parse_date(p.get("birth", "")) if p.get("birth") else None
            if day:
                born.insert(0, day.strftime("%b %d, %Y").replace(" 0", " "))
            name.grid(row=r, column=0, sticky="w", padx=(pad, 4), pady=3)
            relw.grid(row=r, column=1, sticky="w", padx=4, pady=3)
            dln.grid(row=r, column=2, sticky="w", padx=4, pady=3)
            born.grid(row=r, column=3, sticky="w", padx=4, pady=3)
            if not main:
                ctk.CTkButton(card, text="✕", width=34, height=34, font=ui.font(13), fg_color="transparent",
                              border_width=1, border_color=ui.BORDER, text_color=ui.MUTED, hover_color=ui.SURFACE_ALT,
                              command=lambda i=p["id"]: self.remove_person(i)).grid(row=r, column=4, padx=(4, pad), pady=3)
            self.rows_people.append({"id": p["id"], "name": name, "rel": rel, "dln": dln, "born": born})
        self.app.secondary_button(card, "+  Add person", self.add_person, width=150) \
            .grid(row=3 + len(self.data["people"]), column=0, sticky="w", padx=pad, pady=(ui.SP, ui.SP + 2))

        # ----- cars
        card = self._card(1, "Cars", "Every car on the policy. A car needs exactly one principal driver.")
        for c, text in enumerate(["Car (year make model)", "VIN (optional)"]):
            ctk.CTkLabel(card, text=text, font=ui.font(12, "bold"), text_color=ui.MUTED, anchor="w") \
                .grid(row=2, column=c, sticky="w", padx=(pad if c == 0 else 4, 4), pady=(ui.SP, 0))
        for r, car in enumerate(self.data["cars"], start=3):
            label = self._entry(card, car["label"], 330, "2019 Honda Civic")
            vin = self._entry(card, car.get("vin", ""), 230, "", upper=True)
            label.grid(row=r, column=0, sticky="w", padx=(pad, 4), pady=3)
            vin.grid(row=r, column=1, sticky="w", padx=4, pady=3)
            ctk.CTkButton(card, text="✕", width=34, height=34, font=ui.font(13), fg_color="transparent", border_width=1,
                          border_color=ui.BORDER, text_color=ui.MUTED, hover_color=ui.SURFACE_ALT,
                          command=lambda i=car["id"]: self.remove_car(i)).grid(row=r, column=2, padx=(4, pad), pady=3)
            self.rows_cars.append({"id": car["id"], "label": label, "vin": vin})
        self.app.secondary_button(card, "+  Add car", self.add_car, width=130) \
            .grid(row=3 + len(self.data["cars"]), column=0, sticky="w", padx=pad, pady=(ui.SP, ui.SP + 2))

        # ----- who drives what
        card = self._card(2, "Who drives what",
                          "Pick the role of each person on each car. Leave it empty when the person does not drive that car.")
        if not self.data["cars"]:
            ctk.CTkLabel(card, text="Add a car above to set the roles.", font=ui.font(13), text_color=ui.MUTED) \
                .grid(row=2, column=0, sticky="w", padx=pad, pady=(ui.SP, ui.SP + 2))
        else:
            for c, car in enumerate(self.data["cars"], start=1):
                ctk.CTkLabel(card, text=car["label"] or "(car)", font=ui.font(12, "bold"), text_color=ui.MUTED, anchor="w",
                             wraplength=170, justify="left").grid(row=2, column=c, sticky="w", padx=4, pady=(ui.SP, 0))
            for r, p in enumerate(self.data["people"], start=3):
                ctk.CTkLabel(card, text=p["name"].title(), font=ui.font(13, "bold"), text_color=ui.TEXT, anchor="w",
                             width=210).grid(row=r, column=0, sticky="w", padx=(pad, 4), pady=3)
                for c, car in enumerate(self.data["cars"], start=1):
                    var = tk.StringVar(value=household.role_of(self.data, p["id"], car["id"]))
                    var.trace_add("write", lambda *a: self.refresh_problems())
                    self.role_vars[(car["id"], p["id"])] = var
                    self._menu(card, [""] + household.ROLES, var, 165).grid(row=r, column=c, sticky="w", padx=4, pady=3)
            ctk.CTkFrame(card, fg_color="transparent", height=ui.SP).grid(row=3 + len(self.data["people"]), column=0)
        self.refresh_problems()

    def _format_dln(self, entry):
        import fill_consent
        text = entry.get().strip()
        if text:
            entry.delete(0, "end")
            entry.insert(0, fill_consent.format_dln(text))

    # ---------- reading the page back ----------
    def snapshot(self):
        """The data as typed on the page (people, cars, roles)."""
        people = []
        for p in self.rows_people:
            old = next((x for x in self.data["people"] if x["id"] == p["id"]), {})
            day = records.parse_date(p["born"].get()) if p["born"].get() else None
            people.append({"id": p["id"], "name": old["name"] if p["id"] == household.MAIN else p["name"].get().strip(),
                           "relation": "" if p["id"] == household.MAIN else p["rel"].get(),
                           "dln": p["dln"].get().strip(), "birth": day.isoformat() if day else p["born"].get().strip()})
        cars = [{"id": c["id"], "label": c["label"].get().strip(), "vin": c["vin"].get().strip()} for c in self.rows_cars]
        roles = {}
        for (car, person), var in self.role_vars.items():
            if var.get():
                roles.setdefault(car, {})[person] = var.get()
        return {"people": people, "cars": cars, "roles": roles}

    def refresh_problems(self):
        if not self.winfo_exists() or not self.rows_people:
            return
        found = household.problems(self.snapshot())
        self.status.configure(text="\n".join(found[:3]) + ("\n…" if len(found) > 3 else "") if found else "", text_color=self.ui.WARN)

    # ---------- changes ----------
    def add_person(self):
        self.data = self.snapshot()
        self.data["people"].append({"id": household.uuid.uuid4().hex[:8], "name": "", "relation": "", "dln": "", "birth": ""})
        self.build()

    def remove_person(self, pid):
        self.data = self.snapshot()
        self.data["people"] = [p for p in self.data["people"] if p["id"] != pid]
        self.build()

    def add_car(self):
        self.data = self.snapshot()
        self.data["cars"].append({"id": household.uuid.uuid4().hex[:8], "label": "", "vin": ""})
        self.build()

    def remove_car(self, cid):
        self.data = self.snapshot()
        self.data["cars"] = [c for c in self.data["cars"] if c["id"] != cid]
        self.data["roles"].pop(cid, None)
        self.build()

    def copy_text(self):
        copy(self.app, household.as_text(self.snapshot()), self.copy_btn)

    def fill_from_quote(self):
        self.data = self.snapshot()
        data, ui = self.data, self.ui
        self.status.configure(text="Reading the quote…", text_color=ui.MUTED)

        def work():
            try:
                new, added = household.from_quote(self.folder, data)
            except Exception as e:
                self.app.ui(lambda: self.winfo_exists() and self.status.configure(
                    text=f"Could not read the quote: {e}", text_color=ui.DANGER))
                return
            self.app.ui(self._quote_done, new, added)
        threading.Thread(target=work, daemon=True).start()

    def _quote_done(self, data, added):
        if not self.winfo_exists():
            return
        self.data = data
        self.build()
        self.status.configure(
            text=("✓ Added from the quote: " + ", ".join(added) + ". Set who drives what, then Save.") if added else
                 "Nothing new on the quote (no quote in the folder, or everyone is already listed).",
            text_color=self.ui.SUCCESS if added else self.ui.MUTED)

    # ---------- save ----------
    def save(self):
        data = self.snapshot()
        self.save_btn.configure(state="disabled", text="Saving…")

        def work():
            try:
                saved = household.save(self.folder, data)
            except OSError as e:
                self.app.ui(self._failed, str(e))
                return
            self.app.ui(self._saved, saved)
        threading.Thread(target=work, daemon=True).start()

    def _failed(self, message):
        if self.winfo_exists():
            self.save_btn.configure(state="normal", text="Save")
            self.status.configure(text=f"Could not save: {message}", text_color=self.ui.DANGER)

    def _saved(self, saved):
        if self.on_saved:
            self.on_saved(saved)
        if not self.winfo_exists():
            return
        self.data = saved
        self.save_btn.configure(state="normal", text="Save")
        self.build()
        left = household.problems(saved)
        self.status.configure(text="✓ Saved" + (f". Still to check: {left[0]}" if left else ""),
                              text_color=self.ui.WARN if left else self.ui.SUCCESS)
