"""ARS entry page: the DASH report and the MVR turned into what to type into Applied Rating.

One section at a time (tabs): Driver (licence number, class, G1 / G2 / G dates), Claims, Convictions and
Gaps & history. Every record is a small card of label / value pairs: click a value to copy it. Amber boxes
only where something needs checking; items too old to enter are folded away. Works with only a DASH or only
an MVR too. See ars.py for the rules.
"""
import sys
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

import ui_kit

import ars
import eligibility
import mvr
import review
from carriers_ui import copy
from panel import Panel

WARN = ("#B45309", "#FBBF24")
WARN_SOFT = ("#FEF6E7", "#2E2717")
DANGER_SOFT = ("#FDECEC", "#2D1A1A")
GOOD_SOFT = ("#E8F5EC", "#16291D")
TAB_ON = ("#FFFFFF", "#44566B")          # the open tab: clearly lighter than the others


class ArsEntryPage(Panel):
    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = sys.modules[type(app).__module__]
        self.title(f"ARS entry - {self.folder.name}")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.text, self.data, self.tab_names, self.body = "", {}, {}, None

        # ----- top bar: which DASH, which MVR, and the one main action
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
        found = review.find_docs(self.folder)
        self.dashes, self.mvrs = found["dash"], found["mvr"]
        ctk.CTkLabel(top, text="DASH", font=ui.font(13, "bold"), text_color=ui.MUTED).pack(side="left")
        self.choice = tk.StringVar(value=self.dashes[0].name if self.dashes else "(none in the folder)")
        ctk.CTkOptionMenu(top, values=[p.name for p in self.dashes] or ["(none in the folder)"],
                          variable=self.choice, width=380, height=34, font=ui.font(12), fg_color=ui.SURFACE_ALT,
                          button_color=ui.SURFACE_ALT, button_hover_color=ui.BORDER, text_color=ui.TEXT,
                          dynamic_resizing=False, command=lambda _: self.load()).pack(side="left", padx=(ui.SP, 2 * ui.SP))
        self.mvr_label = ctk.CTkLabel(top, text="", font=ui.font(12), text_color=ui.MUTED)
        self.mvr_label.pack(side="left")
        self.copy_all = ctk.CTkButton(top, text="Copy everything as text", height=34, width=190,
                                      font=ui.font(13, "bold"), fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER,
                                      command=lambda: self.text and copy(app, self.text, self.copy_all))
        self.copy_all.pack(side="right")

        # ----- tabs (filled when the documents are read) and a one-line hint
        self.tab_bar = ui_kit.Segmented(
            self, values=["Reading…"], height=38, font=ui.font(14, "bold"), selected_color=TAB_ON,
            selected_hover_color=TAB_ON, unselected_color=ui.SURFACE_ALT, unselected_hover_color=ui.BORDER,
            text_color=ui.TEXT, command=self.draw_tab)
        self.tab_bar.grid(row=1, column=0, sticky="w", padx=ui.SP, pady=(0, ui.SP))
        self.hint = ctk.CTkLabel(self, text="", font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left")
        self.hint.grid(row=2, column=0, sticky="ew", padx=ui.SP * 1.5, pady=(0, ui.SP))
        self.bind("<Escape>", lambda e: self.destroy())
        self.load()

    # ---------- loading ----------
    def _new_body(self):
        if self.body is not None:
            self.body.destroy()
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=3, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)

    def _message(self, text, color=None):
        ui = self.ui
        self.tab_bar.grid_remove()
        self.hint.configure(text="")
        self._new_body()
        ctk.CTkLabel(self.body, text=text, font=ui.font(14), text_color=color or ui.MUTED, justify="left",
                     anchor="w", wraplength=760).grid(row=0, column=0, sticky="w", padx=2 * ui.SP, pady=2 * ui.SP)

    def load(self):
        path = next((p for p in self.dashes if p.name == self.choice.get()), None)
        mvr_path = self.mvrs[0] if self.mvrs else None
        self.mvr_label.configure(text=f"MVR: {mvr_path.name}" if mvr_path else "No MVR in the folder")
        if path is None and mvr_path is None:
            self.text = ""
            return self._message("No DASH report or MVR in the client folder. Use Import DASH and Request MVR first.")
        self._message("Reading the DASH report and the MVR…")
        result = {}

        def work():
            try:
                v = {"claims": None, "hist": None, "drv": None, "convs": None, "susp": None}
                details = None
                if path is not None:
                    _, details, _ = eligibility.read_dash_facts(str(path))
                    v["claims"], v["hist"] = ars.claims(details), ars.history(details)
                if mvr_path is not None:
                    m = mvr.read(str(mvr_path))
                    v["drv"], v["convs"], v["susp"] = ars.driver(m, details), ars.convictions(m), ars.suspensions(m)
                result["v"] = v
            except Exception as e:
                result["error"] = e

        t = threading.Thread(target=work, daemon=True)
        t.start()

        def wait():
            if t.is_alive():
                return self.after(100, wait)
            if not self.winfo_exists():
                return
            if "error" in result:
                self.text = ""
                return self._message(f"Could not read the documents: {result['error']}", self.ui.DANGER)
            self.show(**result["v"])
        wait()

    # ---------- building blocks ----------
    def _heading(self, row, text, sub=""):
        ui = self.ui
        box = ctk.CTkFrame(self.body, fg_color="transparent")
        box.grid(row=row, column=0, sticky="ew", padx=ui.SP, pady=(ui.SP, ui.SP))
        ctk.CTkLabel(box, text=text, font=ui.font(18, "bold"), text_color=ui.TEXT, anchor="w").pack(anchor="w")
        if sub:
            ctk.CTkLabel(box, text=sub, font=ui.font(13), text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=800).pack(anchor="w")

    def _card(self, row, parent=None):
        ui = self.ui
        card = ctk.CTkFrame(parent or self.body, fg_color=ui.SURFACE, corner_radius=12, border_width=1,
                            border_color=ui.BORDER)
        card.grid(row=row, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP * 1.5))
        card.grid_columnconfigure((0, 1), weight=1, uniform="cell")
        return card

    def _pill(self, parent, text, kind):
        """A small status label: bad (red), good (green), warn (amber), plain."""
        ui = self.ui
        bg, fg = {"bad": (DANGER_SOFT, ui.DANGER), "good": (GOOD_SOFT, ui.SUCCESS),
                  "warn": (WARN_SOFT, WARN)}.get(kind, (ui.SURFACE_ALT, ui.MUTED))
        return ctk.CTkLabel(parent, text=f" {text} ", font=ui.font(12, "bold"), text_color=fg, fg_color=bg,
                            corner_radius=8, height=24)

    def _record(self, row, title, badge=None, kind="plain", sub="", fields=(), notes=(), footer="", parent=None):
        """One card: title + status pill, a muted line, label / value pairs (click a value to copy), amber notes."""
        ui = self.ui
        card = self._card(row, parent)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=2 * ui.SP, pady=(1.5 * ui.SP, 0))
        ctk.CTkLabel(head, text=title, font=ui.font(16, "bold"), text_color=ui.TEXT, anchor="w").pack(side="left")
        if badge:
            self._pill(head, badge, kind).pack(side="left", padx=ui.SP)
        r = 1
        if sub:
            ctk.CTkLabel(card, text=sub, font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=780).grid(row=r, column=0, columnspan=2, sticky="w", padx=2 * ui.SP)
            r += 1
        ctk.CTkFrame(card, fg_color=ui.BORDER, height=1).grid(row=r, column=0, columnspan=2, sticky="ew",
                                                              padx=2 * ui.SP, pady=(ui.SP, ui.SP / 2))
        r += 1
        for i, (label, value, color) in enumerate(fields):
            cell = ctk.CTkFrame(card, fg_color="transparent")
            cell.grid(row=r + i // 2, column=i % 2, sticky="ew", padx=(2 * ui.SP, ui.SP), pady=(ui.SP / 2, 0))
            ctk.CTkLabel(cell, text=label, font=ui.font(12), text_color=ui.MUTED, anchor="w").pack(anchor="w", padx=(6, 0))
            self._value(cell, label, value, color).pack(anchor="w", fill="x")
        r += (len(fields) + 1) // 2
        if footer:
            ctk.CTkLabel(card, text=footer, font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=780).grid(row=r, column=0, columnspan=2, sticky="w", padx=2 * ui.SP,
                                              pady=(ui.SP, 0))
            r += 1
        if notes:
            box = ctk.CTkFrame(card, fg_color=WARN_SOFT, corner_radius=8)
            box.grid(row=r, column=0, columnspan=2, sticky="ew", padx=2 * ui.SP, pady=(ui.SP, 0))
            for n in notes:
                ctk.CTkLabel(box, text="•  " + n, font=ui.font(13), text_color=WARN, anchor="w", justify="left",
                             wraplength=760).pack(anchor="w", padx=ui.SP * 1.5, pady=(ui.SP / 2, ui.SP / 2))
            r += 1
        ctk.CTkFrame(card, fg_color="transparent", height=ui.SP * 1.5, width=1).grid(row=r, column=0)
        return card

    def _value(self, parent, label, value, color=None):
        """The value is a button: click it to copy (money without commas)."""
        ui = self.ui
        text = value or "(not read)"
        b = ctk.CTkButton(parent, text=text, anchor="w", height=32, font=ui.font(15, "bold"),
                          fg_color="transparent", hover_color=ui.SURFACE_ALT, text_color=color or ui.TEXT,
                          corner_radius=6, border_width=0, cursor="hand2")
        if value:
            copy_text = value.replace(",", "") if label.endswith("$") else value
            b.configure(command=lambda: copy(self.app, copy_text, b))
        return b

    def _empty(self, row, text, good=True):
        ui = self.ui
        box = ctk.CTkFrame(self.body, fg_color=GOOD_SOFT if good else ui.SURFACE_ALT, corner_radius=10)
        box.grid(row=row, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP * 1.5))
        ctk.CTkLabel(box, text=text, font=ui.font(14), text_color=ui.SUCCESS if good else ui.MUTED, anchor="w",
                     justify="left", wraplength=780).pack(anchor="w", padx=2 * ui.SP, pady=1.5 * ui.SP)

    def _fold(self, row, title, lines):
        """A closed list ('older than N years - don't enter'); click the title to open it."""
        ui = self.ui
        wrap = ctk.CTkFrame(self.body, fg_color="transparent")
        wrap.grid(row=row, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
        body = ctk.CTkFrame(wrap, fg_color=ui.SURFACE, corner_radius=10, border_width=1, border_color=ui.BORDER)
        for text in lines:
            ctk.CTkLabel(body, text=text, font=ui.font(13), text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=780).pack(anchor="w", padx=2 * ui.SP, pady=(ui.SP / 2, ui.SP / 2))
        state = {"open": False}
        head = ctk.CTkButton(wrap, text=f"▸   {title}", anchor="w", height=36, font=ui.font(13, "bold"),
                             fg_color="transparent", hover_color=ui.SURFACE_ALT, text_color=ui.MUTED,
                             border_width=0, cursor="hand2")

        def toggle():
            state["open"] = not state["open"]
            head.configure(text=("▾   " if state["open"] else "▸   ") + title)
            if state["open"]:
                body.grid(row=1, column=0, sticky="ew")
            else:
                body.grid_remove()
        head.configure(command=toggle)
        head.grid(row=0, column=0, sticky="ew")
        wrap.grid_columnconfigure(0, weight=1)

    # ---------- the tabs ----------
    def show(self, claims, hist, drv, convs, susp):
        self.data = {"claims": claims, "hist": hist, "drv": drv, "convs": convs, "susp": susp}
        self.text = ars.as_text(claims, hist, drv, convs, susp)
        names = {}
        if drv is not None:
            names["Driver"] = "driver"
        if claims is not None:
            n = len([c for c in claims if not c["old"]])
            names[f"Claims  {n}" if n else "Claims"] = "claims"
        if convs is not None:
            n = len([c for c in convs if not c["old"]])
            names[f"Convictions  {n}" if n else "Convictions"] = "convictions"
        if hist is not None:
            n = len(hist["lapses"])
            names[f"Gaps & history  {n}" if n else "Gaps & history"] = "history"
        self.tab_names = names
        missing = []
        if claims is None:
            missing.append("No DASH report in the folder, so no claims or gaps")
        if drv is None:
            missing.append("No MVR in the folder, so no driver details or convictions")
        self.hint.configure(text="Click any value to copy it.   " + ("   ·   ".join(missing) if missing else ""))
        self.tab_bar.configure(values=list(names))
        self.tab_bar.grid()
        first = next(iter(names))
        self.tab_bar.set(first)
        self.draw_tab(first)

    def draw_tab(self, name):
        key = self.tab_names.get(name)
        self._new_body()
        self.hint_visible = True
        {"driver": self._tab_driver, "claims": self._tab_claims, "convictions": self._tab_convictions,
         "history": self._tab_history}[key]()

    def _tab_driver(self):
        d = self.data["drv"]
        self._heading(0, "Driver", "From the MVR. Type these on the ARS driver screen.")
        fields = [("First name", d["first"], None), ("Last name", d["last"], None),
                  ("Date of birth", d["birth"], None), ("Licence #", d["licence"], None),
                  ("Licence class", d["class"], None)]
        if d.get("out_of_province"):                 # the licence dates are entered differently: see the note below
            fields.append(("Out of province experience", "Turn ON", self.ui.WARN))
            fields.append(("G date", d["g"], None))
            fields.append(("G1 / G2 dates", "Leave blank", self.ui.WARN))
        else:
            for label, key in (("G1 date", "g1"), ("G2 date", "g2"), ("G date", "g")):
                if d[key]:
                    fields.append((label, d[key], None))
        notes = list(d["notes"])
        if d["demerits"]:
            notes.insert(0, f"{d['demerits']} demerit points on the licence.")
        self._record(1, f"{d['first']} {d['last']}".strip() or "Driver",
                     badge=d["status"].capitalize() if d["status"] else None,
                     kind="good" if d["status"] == "LICENCED" else "bad", fields=fields, notes=notes)

    def _tab_claims(self):
        ui = self.ui
        entries = self.data["claims"]
        recent = [e for e in entries if not e["old"]]
        old = [e for e in entries if e["old"]]
        faults = sum(1 for e in recent if e["chargeable"] == "At-Fault")
        self._heading(0, f"{len(recent)} claim{'s' if len(recent) != 1 else ''} to enter",
                      (f"{faults} at-fault, {len(recent) - faults} non-responsible. " if recent else "") +
                      f"Claims form on the ARS driver screen, last {ars.LOOKBACK_YEARS} years.")
        if not recent:
            self._empty(1, f"No claims on the DASH in the last {ars.LOOKBACK_YEARS} years.")
        row = 1
        for i, e in enumerate(recent, 1):
            at_fault = e["chargeable"] == "At-Fault"
            sub = "   ·   ".join(x for x in (e["insurer"], f"claim # {e['claim_no']}" if e["claim_no"] else "",
                                             e["coverage"], e["status"],
                                             f"driver {e['driver']}" if e["driver"] else "") if x)
            fields = [("Date", e["date"], None), ("Description", e["description"], None),
                      ("Vehicle involved", e["vehicle"] or "(not on the DASH)", None),
                      ("Chargeable", e["chargeable"], ui.DANGER if at_fault else ui.SUCCESS)]
            fields += [(label, e["amounts"][k], None) for k, label in ars.AMOUNTS if e["amounts"][k]]
            blank = [label for k, label in ars.AMOUNTS if not e["amounts"][k]]
            self._record(row, f"Claim {i}", "At-fault" if at_fault else "Non-responsible",
                         "bad" if at_fault else "good", sub, fields, e["notes"],
                         footer=("Leave blank: " + ", ".join(blank)) if blank else "")
            row += 1
        if old:
            self._fold(row, f"Older than {ars.LOOKBACK_YEARS} years - don't enter ({len(old)})",
                       [f"{e['date']}   {e['description']}  ({e['chargeable']})   {e['insurer']}" for e in old])

    def _tab_convictions(self):
        convs, susp = self.data["convs"], self.data["susp"]
        recent = [c for c in convs if not c["old"]]
        old = [c for c in convs if c["old"]]
        self._heading(0, f"{len(recent)} conviction{'s' if len(recent) != 1 else ''} to enter",
                      f"From the MVR, last {ars.CONVICTION_YEARS} years. The conviction date counts, not the offence date.")
        if not recent:
            self._empty(1, f"No convictions on the MVR in the last {ars.CONVICTION_YEARS} years.")
        row = 1
        ui = self.ui
        for i, c in enumerate(recent, 1):
            bad = c["category"] in ("Major", "Serious")
            self._record(row, f"Conviction {i}", c["category"], "bad" if bad else "plain",
                         sub=f"Offence date {c['offence']}" if c["offence"] else "",
                         fields=[("Date (conviction)", c["date"], None), ("Description", c["description"], None),
                                 ("Seriousness", c["category"], ui.DANGER if bad else None)],
                         notes=c["notes"])
            row += 1
        if susp:
            self._record(row, "Licence actions on the MVR", "check", "warn",
                         fields=[(s["date"], s["description"], ui.TEXT) for s in susp],
                         notes=["Suspensions and cancellations: ask the client about them."])
            row += 1
        if old:
            self._fold(row, f"Older than {ars.CONVICTION_YEARS} years - don't enter ({len(old)})",
                       [f"{c['date']}   {c['description']}  ({c['category']})" for c in old])

    def _tab_history(self):
        ui = self.ui
        hist = self.data["hist"]
        lapses = hist["lapses"]
        self._heading(0, f"{len(lapses)} gap{'s' if len(lapses) != 1 else ''} in coverage" if lapses
                      else "No gaps in coverage",
                      "From the DASH. Enter the reason the client gives for each gap.")
        row = 1
        if not lapses and not hist["uninsured_since"]:
            self._empty(row, "No gaps on the DASH.")
            row += 1
        for i, g in enumerate(lapses, 1):
            self._record(row, f"Gap {i}", f"{g['days']} days", "warn",
                         fields=[("From", g["from"], None), ("To", g["to"], None), ("Months", str(g["months"]), None)])
            row += 1
        if hist["uninsured_since"]:
            self._record(row, "Not insured now", "since " + hist["uninsured_since"], "bad",
                         notes=["The latest policy has ended. Ask when the client is insured from."])
            row += 1

        self._heading(row, "Prior insurance", "For the driver / prior insurance screen.")
        row += 1
        cur = hist["current"]
        if not cur:
            self._empty(row, "No policies on the DASH: no insurance history (treated as a new driver).", good=False)
            row += 1
        else:
            fields = [("Prior insurer", cur["insurer"], None), ("Effective", ars.ars_date(cur["start"]), None),
                      ("Expiry", ars.ars_date(cur["end"]), None), ("First insured", hist["first_insured"], None)]
            if hist["continuous_since"]:
                fields.append(("Continuous since", hist["continuous_since"], None))
            active = (cur["status"] or "").lower() == "active"
            self._record(row, cur["insurer"], cur["status"] or "status unknown", "good" if active else "plain",
                         fields=fields)
            row += 1

        cancels = hist["cancellations"]
        if cancels:
            self._heading(row, f"{len(cancels)} cancellation{'s' if len(cancels) != 1 else ''}")
            row += 1
            for c in cancels:
                bad = "non-pay" in c["reason"].lower()
                self._record(row, c["insurer"], c["reason"] or "cancelled", "bad" if bad else "warn",
                             fields=[("Date", c["date"], None)])
                row += 1
        if hist["policies"]:
            self._fold(row, f"All policies on the DASH ({len(hist['policies'])})",
                       [f"{ars.ars_date(p['start'])} - {ars.ars_date(p['end'])}   {p['insurer']}   ({p['status'] or '?'})"
                        for p in hist["policies"]])
