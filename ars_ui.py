"""ARS entry page: the DASH report and the MVR turned into what to type into Applied Rating - the driver
(licence number, class, G1 / G2 / G dates), the Claims form (one card per claim, Copy next to each value), the
Convictions, and the insurance history (first insured, continuous since, lapses with months, cancellations).
Works with only a DASH or only an MVR too. See ars.py for the rules.
"""
import sys
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

import ars
import eligibility
import mvr
import review
from carriers_ui import copy
from panel import Panel

WARN = ("#B45309", "#FBBF24")


class ArsEntryPage(Panel):
    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = sys.modules[type(app).__module__]
        self.title(f"ARS entry from DASH and MVR - {self.folder.name}")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.text = ""

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=ui.SP, pady=(0, 2 * ui.SP))
        found = review.find_docs(self.folder)
        self.dashes, self.mvrs = found["dash"], found["mvr"]
        ctk.CTkLabel(top, text="DASH report", font=ui.font(13, "bold"), text_color=ui.TEXT).pack(side="left")
        self.choice = tk.StringVar(value=self.dashes[0].name if self.dashes else "(none in the folder)")
        ctk.CTkOptionMenu(top, values=[p.name for p in self.dashes] or ["(none in the folder)"],
                          variable=self.choice, width=420, height=34, font=ui.font(12), fg_color=ui.SURFACE_ALT,
                          button_color=ui.PRIMARY, button_hover_color=ui.PRIMARY_HOVER, text_color=ui.TEXT,
                          dynamic_resizing=False, command=lambda _: self.load()).pack(side="left", padx=ui.SP)
        self.copy_all = ctk.CTkButton(top, text="Copy all as text", height=34, width=150, font=ui.font(13, "bold"),
                                      fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER,
                                      command=lambda: self.text and copy(app, self.text, self.copy_all))
        self.copy_all.pack(side="right")
        self.mvr_label = ctk.CTkLabel(top, text="", font=ui.font(12), text_color=ui.MUTED)
        self.mvr_label.pack(side="right", padx=ui.SP)
        self.body = None
        self.bind("<Escape>", lambda e: self.destroy())
        self.load()

    # ---------- loading ----------
    def _message(self, text, color=None):
        ui = self.ui
        self._new_body()
        ctk.CTkLabel(self.body, text=text, font=ui.font(13), text_color=color or ui.MUTED, justify="left",
                     anchor="w", wraplength=760).grid(row=0, column=0, sticky="w", padx=2 * ui.SP, pady=2 * ui.SP)

    def _new_body(self):
        if self.body is not None:
            self.body.destroy()
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=3, uniform="cols")
        self.body.grid_columnconfigure(1, weight=2, uniform="cols")

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

    # ---------- drawing ----------
    def _card(self, parent, row, title, column=0):
        ui = self.ui
        card = ctk.CTkFrame(parent, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
        card.grid(row=row, column=column, sticky="new", padx=ui.SP, pady=(0, 2 * ui.SP))
        card.grid_columnconfigure(1, weight=1)
        if title:
            ctk.CTkLabel(card, text=title.upper(), font=ui.font(11, "bold"), text_color=ui.MUTED, anchor="w") \
                .grid(row=0, column=0, columnspan=3, sticky="w", padx=2 * ui.SP, pady=(1.5 * ui.SP, ui.SP / 2))
        return card

    def _field(self, card, row, label, value, color=None, wrap=380):
        """Label | value | Copy."""
        ui = self.ui
        ctk.CTkLabel(card, text=label, font=ui.font(13), text_color=ui.MUTED, anchor="w") \
            .grid(row=row, column=0, sticky="w", padx=(2 * ui.SP, ui.SP), pady=1)
        ctk.CTkLabel(card, text=value, font=ui.font(13, "bold"), text_color=color or ui.TEXT, anchor="w",
                     justify="left", wraplength=wrap).grid(row=row, column=1, sticky="w", pady=1)
        b = ctk.CTkButton(card, text="Copy", width=56, height=24, font=ui.font(12), fg_color="transparent",
                          border_width=1, border_color=ui.BORDER, text_color=ui.TEXT, hover_color=ui.SURFACE_ALT)
        b.configure(command=lambda: copy(self.app, value.replace(",", "") if label.endswith("$") else value, b))
        b.grid(row=row, column=2, sticky="e", padx=(ui.SP, 2 * ui.SP), pady=1)
        return row + 1

    def _notes(self, card, row, notes, wrap=520):
        ui = self.ui
        for n in notes:
            ctk.CTkLabel(card, text="•  " + n, font=ui.font(12), text_color=WARN, anchor="w", justify="left",
                         wraplength=wrap).grid(row=row, column=0, columnspan=3, sticky="w", padx=2 * ui.SP, pady=1)
            row += 1
        return row

    def show(self, claims, hist, drv, convs, susp):
        ui = self.ui
        self.text = ars.as_text(claims, hist, drv, convs, susp)
        self._new_body()
        left = ctk.CTkFrame(self.body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="new")
        left.grid_columnconfigure(0, weight=1)
        right = ctk.CTkFrame(self.body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="new")
        right.grid_columnconfigure(0, weight=1)
        row = 0
        if claims is not None:
            box = ctk.CTkFrame(left, fg_color="transparent")
            box.grid(row=0, column=0, sticky="new")
            box.grid_columnconfigure(0, weight=1)
            self._claims(box, claims)
            row = 1
        else:
            self._missing(left, 0, "No DASH report in the folder - no claims or insurance history to show.")
            row = 1
        if convs is not None:
            box = ctk.CTkFrame(left, fg_color="transparent")
            box.grid(row=row, column=0, sticky="new")
            box.grid_columnconfigure(0, weight=1)
            self._convictions(box, convs, susp)
        else:
            self._missing(left, row, "No MVR in the folder - no convictions or licence dates to show.")
        base = 0
        if drv is not None:
            self._driver(right, drv)
            base = 2
        if hist is not None:
            self._history(right, hist, base)

    def _missing(self, parent, row, text):
        ui = self.ui
        ctk.CTkLabel(parent, text=text, font=ui.font(13), text_color=ui.MUTED, anchor="w", justify="left",
                     wraplength=520).grid(row=row, column=0, sticky="w", padx=ui.SP, pady=(0, 2 * ui.SP))

    def _driver(self, right, drv):
        ui = self.ui
        ctk.CTkLabel(right, text="Driver (from the MVR)", font=ui.font(17, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=0, column=0, sticky="w", padx=ui.SP, pady=(0, ui.SP))
        card = self._card(right, 1, "Licence details")
        r = self._field(card, 1, "First name", drv["first"], wrap=200)
        r = self._field(card, r, "Last name", drv["last"], wrap=200)
        r = self._field(card, r, "Date of birth", drv["birth"] or "(not read)", wrap=200)
        r = self._field(card, r, "Licence #", drv["licence"] or "(not read)", wrap=200)
        r = self._field(card, r, "Licence class", drv["class"] or "(not read)", wrap=200)
        for label, key in (("G1 date", "g1"), ("G2 date", "g2"), ("G date", "g")):
            if drv[key]:
                r = self._field(card, r, label, drv[key], wrap=200)
        if drv["demerits"]:
            ctk.CTkLabel(card, text=f"{drv['demerits']} demerit points", font=ui.font(12), text_color=WARN,
                         anchor="w").grid(row=r, column=0, columnspan=3, sticky="w", padx=2 * ui.SP)
            r += 1
        r = self._notes(card, r, drv["notes"], wrap=340)
        ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=r, column=0)

    def _convictions(self, left, convs, susp):
        ui = self.ui
        recent = [c for c in convs if not c["old"]]
        old = [c for c in convs if c["old"]]
        head = f"Convictions form - {len(recent)} to enter" if recent else "Convictions form - nothing to enter"
        ctk.CTkLabel(left, text=head, font=ui.font(17, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=0, column=0, sticky="w", padx=ui.SP, pady=(0, ui.SP))
        if not recent:
            ctk.CTkLabel(left, text=f"No convictions on the MVR in the last {ars.CONVICTION_YEARS} years.",
                         font=ui.font(13), text_color=ui.SUCCESS, anchor="w") \
                .grid(row=1, column=0, sticky="w", padx=ui.SP, pady=(0, 2 * ui.SP))
        for i, c in enumerate(recent, 1):
            card = self._card(left, i, "")
            color = ui.DANGER if c["category"] in ("Major", "Serious") else ui.TEXT
            ctk.CTkLabel(card, text=f"Conviction {i}", font=ui.font(15, "bold"), text_color=ui.TEXT, anchor="w") \
                .grid(row=0, column=0, columnspan=2, sticky="w", padx=2 * ui.SP, pady=(1.5 * ui.SP, ui.SP))
            r = self._field(card, 1, "Date (conviction)", c["date"])
            r = self._field(card, r, "Description", c["description"])
            r = self._field(card, r, "Seriousness", c["category"], color)
            if c["offence"]:
                ctk.CTkLabel(card, text=f"Offence date {c['offence']} - the conviction date is the one that counts",
                             font=ui.font(12), text_color=ui.MUTED, anchor="w").grid(
                    row=r, column=0, columnspan=3, sticky="w", padx=2 * ui.SP)
                r += 1
            r = self._notes(card, r, c["notes"])
            ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=r, column=0)
        n = len(recent) + 1
        if susp:
            card = self._card(left, n, "Licence actions on the MVR (suspensions)")
            for j, s in enumerate(susp, 1):
                ctk.CTkLabel(card, text=f"{s['date']}  {s['description']}", font=ui.font(13), text_color=WARN,
                             anchor="w").grid(row=j, column=0, columnspan=3, sticky="w", padx=2 * ui.SP, pady=1)
            ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=len(susp) + 1, column=0)
            n += 1
        if old:
            card = self._card(left, n, f"Older than {ars.CONVICTION_YEARS} years - don't enter")
            for j, c in enumerate(old, 1):
                ctk.CTkLabel(card, text=f"{c['date']}  {c['description']} ({c['category']})", font=ui.font(12),
                             text_color=ui.MUTED, anchor="w").grid(row=j, column=0, columnspan=3, sticky="w",
                                                                   padx=2 * ui.SP, pady=1)
            ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=len(old) + 1, column=0)

    def _claims(self, left, entries):
        ui = self.ui
        recent = [e for e in entries if not e["old"]]
        old = [e for e in entries if e["old"]]
        head = f"Claims form - {len(recent)} to enter" if recent else "Claims form - nothing to enter"
        ctk.CTkLabel(left, text=head, font=ui.font(17, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=0, column=0, sticky="w", padx=ui.SP, pady=(0, ui.SP))
        if not recent:
            ctk.CTkLabel(left, text=f"No claims on the DASH in the last {ars.LOOKBACK_YEARS} years.",
                         font=ui.font(13), text_color=ui.MUTED, anchor="w") \
                .grid(row=1, column=0, sticky="w", padx=ui.SP, pady=(0, 2 * ui.SP))
        for i, e in enumerate(recent, 1):
            card = self._card(left, i, "")
            charge_color = ui.DANGER if e["chargeable"] == "At-Fault" else ui.SUCCESS
            ctk.CTkLabel(card, text=f"Claim {i}", font=ui.font(15, "bold"), text_color=ui.TEXT, anchor="w") \
                .grid(row=0, column=0, columnspan=2, sticky="w", padx=2 * ui.SP, pady=(1.5 * ui.SP, 0))
            sub = "  ·  ".join(x for x in (e["insurer"], f"claim # {e['claim_no']}" if e["claim_no"] else "",
                                            e["coverage"], e["status"],
                                            f"driver {e['driver']}" if e["driver"] else "") if x)
            ctk.CTkLabel(card, text=sub, font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=520).grid(row=1, column=0, columnspan=3, sticky="w", padx=2 * ui.SP,
                                              pady=(0, ui.SP))
            r = self._field(card, 2, "Date", e["date"])
            r = self._field(card, r, "Description", e["description"])
            r = self._field(card, r, "Vehicle involved", e["vehicle"] or "(not on the DASH)")
            r = self._field(card, r, "Chargeable", e["chargeable"], charge_color)
            filled = [(label, e["amounts"][k]) for k, label in ars.AMOUNTS if e["amounts"][k]]
            for label, value in filled:
                r = self._field(card, r, label, value)
            blank = [label for k, label in ars.AMOUNTS if not e["amounts"][k]]
            ctk.CTkLabel(card, text="Leave blank: " + ", ".join(blank), font=ui.font(12), text_color=ui.MUTED,
                         anchor="w").grid(row=r, column=0, columnspan=3, sticky="w", padx=2 * ui.SP, pady=(2, 0))
            r = self._notes(card, r + 1, e["notes"])
            ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=r, column=0)
        if old:
            card = self._card(left, len(recent) + 1, f"Older than {ars.LOOKBACK_YEARS} years - don't enter")
            for j, e in enumerate(old, 1):
                ctk.CTkLabel(card, text=f"{e['date']}  {e['description']} ({e['chargeable']}) - {e['insurer']}",
                             font=ui.font(12), text_color=ui.MUTED, anchor="w") \
                    .grid(row=j, column=0, columnspan=3, sticky="w", padx=2 * ui.SP, pady=1)
            ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=len(old) + 1, column=0)


    def _history(self, right, hist, base):
        ui = self.ui
        ctk.CTkLabel(right, text="Insurance history", font=ui.font(17, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=base, column=0, sticky="w", padx=ui.SP, pady=(0, ui.SP))
        card = self._card(right, base + 1, "For the driver / prior insurance")
        cur = hist["current"]
        if not cur:
            ctk.CTkLabel(card, text="No policies on the DASH - no insurance history (new driver).",
                         font=ui.font(13), text_color=ui.TEXT, anchor="w", wraplength=380, justify="left") \
                .grid(row=1, column=0, columnspan=3, sticky="w", padx=2 * ui.SP, pady=(0, ui.SP))
        else:
            r = self._field(card, 1, "Prior insurer", cur["insurer"], wrap=200)
            r = self._field(card, r, "Effective", ars.ars_date(cur["start"]), wrap=200)
            r = self._field(card, r, "Expiry", ars.ars_date(cur["end"]), wrap=200)
            ctk.CTkLabel(card, text=f"Status on the DASH: {cur['status'] or '?'}", font=ui.font(12),
                         text_color=ui.MUTED, anchor="w").grid(row=r, column=0, columnspan=3, sticky="w",
                                                               padx=2 * ui.SP, pady=(0, ui.SP))
            r = self._field(card, r + 1, "First insured", hist["first_insured"], wrap=200)
            if hist["continuous_since"]:
                r = self._field(card, r, "Continuous since", hist["continuous_since"], wrap=200)
            if hist["uninsured_since"]:
                r = self._field(card, r, "Not insured since", hist["uninsured_since"], ui.DANGER, wrap=200)
            ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=r, column=0)

        card = self._card(right, base + 2, "Lapses (gaps in coverage)")
        r = 1
        if not hist["lapses"] and not hist["uninsured_since"]:
            ctk.CTkLabel(card, text="No gaps on the DASH.", font=ui.font(13), text_color=ui.SUCCESS, anchor="w") \
                .grid(row=r, column=0, columnspan=3, sticky="w", padx=2 * ui.SP)
            r += 1
        for g in hist["lapses"]:
            r = self._field(card, r, "From", g["from"], wrap=200)
            r = self._field(card, r, "To", g["to"], wrap=200)
            r = self._field(card, r, "Months", str(g["months"]), wrap=200)
            ctk.CTkLabel(card, text=f"{g['days']} days - enter the reason the client gives", font=ui.font(12),
                         text_color=WARN, anchor="w").grid(row=r, column=0, columnspan=3, sticky="w",
                                                           padx=2 * ui.SP, pady=(0, ui.SP))
            r += 1
        ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=r, column=0)

        card = self._card(right, base + 3, "Cancellations")
        r = 1
        if not hist["cancellations"]:
            ctk.CTkLabel(card, text="None on the DASH.", font=ui.font(13), text_color=ui.SUCCESS, anchor="w") \
                .grid(row=r, column=0, columnspan=3, sticky="w", padx=2 * ui.SP)
            r += 1
        for c in hist["cancellations"]:
            bad = "non-pay" in c["reason"].lower()
            r = self._field(card, r, c["date"], f"{c['insurer']}" + (f" - {c['reason']}" if c["reason"] else ""),
                            ui.DANGER if bad else None, wrap=200)
        ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=r, column=0)

        card = self._card(right, base + 4, "All policies on the DASH")
        for j, p in enumerate(hist["policies"], 1):
            ctk.CTkLabel(card, text=f"{ars.ars_date(p['start'])} - {ars.ars_date(p['end'])}   {p['insurer']}"
                                    f"   ({p['status'] or '?'})", font=ui.font(12), text_color=ui.TEXT, anchor="w",
                         justify="left", wraplength=420) \
                .grid(row=j, column=0, columnspan=3, sticky="w", padx=2 * ui.SP, pady=1)
        ctk.CTkFrame(card, fg_color="transparent", width=1, height=ui.SP).grid(row=len(hist["policies"]) + 1, column=0)
