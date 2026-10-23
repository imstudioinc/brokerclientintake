"""Review window: the quote checked against the MVR and DASH, and eligibility by market.

Reads the client's DASH report, MVR and Applied Rating quote (any of them may be missing),
lists what doesn't match or breaks a rule, and shows which markets fit by the rules file.
"""
import os
import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import config
import eligibility
import review

WARN = ("#B45309", "#FBBF24")
WARN_BG = ("#FEF3C7", "#3A2E12")
CAUTION = ("#6B5B1E", "#E5D38A")
CAUTION_BG = ("#F5F0DC", "#2E2A1A")
GOOD_BG = ("#E8F5EC", "#16291D")
BAD_BG = ("#FDECEC", "#3A1D1D")
NONE = "(none)"
DOC_LABELS = {"dash": "DASH report", "mvr": "MVR", "quote": "Quote (Applied Rating)"}
CHECK_ORDER = ["bad", "refer", "warn", "info", "ok"]


class EligibilityDialog(ctk.CTkToplevel):
    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = sys.modules[type(app).__module__]
        self.title(f"Review quote & eligibility - {self.folder.name}")
        self.geometry("1240x820")
        self.minsize(1000, 640)
        self.configure(fg_color=ui.BG)
        self.transient(app)
        kind = app.client_type_of.get(self.folder, "")
        self.line = kind if kind in ("Auto", "Commercial") else None
        self.data = None
        self.colors = {"Proceed": (ui.SUCCESS, GOOD_BG), "Caution": (CAUTION, CAUTION_BG),
                       "Refer to underwriter": (WARN, WARN_BG), "Not eligible": (ui.DANGER, BAD_BG)}
        self.check_style = {"bad": ("✗", ui.DANGER), "refer": ("↗", WARN), "warn": ("!", WARN),
                            "info": ("i", ui.MUTED), "ok": ("✓", ui.SUCCESS)}

        self.grid_columnconfigure(0, weight=2, uniform="c")
        self.grid_columnconfigure(1, weight=3, uniform="c")
        self.grid_rowconfigure(0, weight=1)

        # ---------- left: documents and facts ----------
        left = ctk.CTkScrollableFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1,
                                      border_color=ui.BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=(16, 0))
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="Documents", font=ui.font(16, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 4))
        self.docs = review.find_docs(self.folder)
        self.doc_vars = {}
        r = 1
        for kind, label in DOC_LABELS.items():
            ctk.CTkLabel(left, text=label, font=ui.font(12), text_color=ui.MUTED, anchor="w") \
                .grid(row=r, column=0, columnspan=2, sticky="w", padx=16, pady=(6, 0))
            names = [p.name for p in self.docs[kind]] + [NONE]
            var = self.doc_vars[kind] = tk.StringVar(value=names[0])
            ctk.CTkOptionMenu(left, values=names, variable=var, height=30, font=ui.font(12),
                              fg_color=ui.SURFACE_ALT, button_color=ui.PRIMARY, button_hover_color=ui.PRIMARY_HOVER,
                              text_color=ui.TEXT, dynamic_resizing=False, command=lambda _: self.load()) \
                .grid(row=r + 1, column=0, columnspan=2, sticky="ew", padx=16)
            r += 2
        self.status = ctk.CTkLabel(left, text="", font=ui.font(12), text_color=ui.MUTED, anchor="w")
        self.status.grid(row=r, column=0, columnspan=2, sticky="w", padx=16, pady=(6, 0))
        r += 1

        ctk.CTkLabel(left, text="Licence class (MVR)", font=ui.font(13), text_color=ui.TEXT, anchor="w") \
            .grid(row=r, column=0, sticky="w", padx=(16, 8), pady=(10, 3))
        self.class_entry = ctk.CTkEntry(left, width=70, height=30, font=ui.font(13), justify="center")
        self.class_entry.grid(row=r, column=1, sticky="e", padx=(0, 16), pady=(10, 3))
        self.class_entry.bind("<KeyRelease>", lambda ev: self.show_results())
        r += 1

        ctk.CTkLabel(left, text="Client facts", font=ui.font(16, "bold"), text_color=ui.TEXT) \
            .grid(row=r, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 0))
        ctk.CTkLabel(left, text="Read from the documents - correct anything that looks wrong.",
                     font=ui.font(12), text_color=ui.MUTED).grid(row=r + 1, column=0, columnspan=2, sticky="w", padx=16)
        r += 2
        self.entries = {}
        for key, label in eligibility.FACTS.items():
            if key == eligibility.MANUAL[0]:
                ctk.CTkLabel(left, text="Convictions (from the MVR)", font=ui.font(13, "bold"), text_color=ui.TEXT) \
                    .grid(row=r, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 2))
                r += 1
            ctk.CTkLabel(left, text=label, font=ui.font(13), text_color=ui.TEXT, anchor="w") \
                .grid(row=r, column=0, sticky="w", padx=(16, 8), pady=3)
            e = ctk.CTkEntry(left, width=70, height=30, font=ui.font(13), justify="center",
                             border_color=ui.PRIMARY if key in eligibility.MANUAL else ui.BORDER)
            e.grid(row=r, column=1, sticky="e", padx=(0, 16), pady=3)
            e.bind("<KeyRelease>", lambda ev: self.show_results(checks=False))
            self.entries[key] = e
            r += 1
        ctk.CTkLabel(left, text="Worth a look", font=ui.font(13, "bold"), text_color=ui.TEXT) \
            .grid(row=r, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 2))
        self.notes = ctk.CTkLabel(left, text="", font=ui.font(12), text_color=WARN, justify="left",
                                  anchor="w", wraplength=380)
        self.notes.grid(row=r + 1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 16))

        # ---------- right: quote review, checks, markets ----------
        self.results = ctk.CTkScrollableFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1,
                                              border_color=ui.BORDER)
        self.results.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(16, 0))
        self.results.grid_columnconfigure(0, weight=1)
        self.checks_box = ctk.CTkFrame(self.results, fg_color="transparent")
        self.checks_box.grid(row=0, column=0, sticky="ew")
        self.checks_box.grid_columnconfigure(0, weight=1)
        self.markets_box = ctk.CTkFrame(self.results, fg_color="transparent")
        self.markets_box.grid(row=1, column=0, sticky="ew")
        self.markets_box.grid_columnconfigure(0, weight=1)

        # ---------- bottom: rules file ----------
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=12)
        self.rules_label = ctk.CTkLabel(bottom, text="", font=ui.font(12), text_color=ui.MUTED, anchor="w")
        self.rules_label.pack(side="left")
        app.secondary_button(bottom, "Close", self.destroy, width=90).pack(side="right")
        app.secondary_button(bottom, "Open rules file", self.open_rules, width=130).pack(side="right", padx=8)
        app.secondary_button(bottom, "Choose rules file…", self.choose_rules, width=150).pack(side="right")
        app.secondary_button(bottom, "Create my rules file…", self.create_rules, width=170).pack(side="right", padx=8)
        self.bind("<Escape>", lambda e: self.destroy())

        self.load_rules()
        self.after(50, self.load)

    # ---------- rules file ----------
    def load_rules(self):
        self.rules, self.rules_path = eligibility.load_rules(self.app.cfg.get("rules_file"))
        builtin = self.rules_path == eligibility.BUILTIN_RULES
        self.rules_label.configure(
            text=("Rules: built in - Intact, Jevco, Echelon and WellCare rules from the underwriting notes (Oct 2026)"
                  if builtin else f"Rules: {self.rules_path}"),
            text_color=self.ui.MUTED)

    def create_rules(self):
        p = filedialog.asksaveasfilename(parent=self, title="Save your rules file (put it on the shared drive)",
                                         defaultextension=".json", initialfile="Underwriting rules.json",
                                         filetypes=[("Rules file", "*.json")])
        if p:
            shutil.copy(eligibility.BUILTIN_RULES, p)
            config.update(self.app.cfg, rules_file=str(Path(p)))
            self.load_rules()
            self.show_results(checks=False)
            os.startfile(p)

    def choose_rules(self):
        p = filedialog.askopenfilename(parent=self, title="Choose the rules file", filetypes=[("Rules file", "*.json")])
        if p:
            config.update(self.app.cfg, rules_file=str(Path(p)))
            self.load_rules()
            self.show_results(checks=False)

    def open_rules(self):
        os.startfile(self.rules_path)

    # ---------- documents ----------
    def _path(self, kind):
        return next((p for p in self.docs[kind] if p.name == self.doc_vars[kind].get()), None)

    def load(self):
        """Read the chosen documents in the background (the MVR needs OCR, about a second)."""
        self.status.configure(text="Reading documents…", text_color=self.ui.MUTED)
        paths = {k: self._path(k) for k in DOC_LABELS}
        result = {}

        def work():
            result["data"] = review.load(paths["dash"], paths["mvr"], paths["quote"])

        t = threading.Thread(target=work, daemon=True)
        t.start()

        def wait():
            if t.is_alive():
                self.after(100, wait)
                return
            if not self.winfo_exists():
                return
            self.data = result["data"]
            self.status.configure(text="")
            self.fill_facts()
            self.show_results()
        wait()

    def fill_facts(self):
        facts, _, notes = review.facts_from(self.data)
        for key, e in self.entries.items():
            e.delete(0, "end")
            if facts.get(key) is not None:
                e.insert(0, f"{facts[key]:g}" if isinstance(facts[key], float) else str(facts[key]))
        m = self.data["mvr"]
        self.class_entry.delete(0, "end")
        if m and m.get("class"):
            self.class_entry.insert(0, m["class"])
        if not m:
            notes.append("No MVR: type the convictions in from the MVR, or add the MVR to the folder.")
        self.notes.configure(text="\n\n".join("• " + n for n in notes) or "Nothing unusual found.")

    def facts(self):
        out = {}
        for key, e in self.entries.items():
            t = e.get().strip()
            try:
                out[key] = float(t) if t else None
            except ValueError:
                out[key] = None
        return out

    # ---------- results ----------
    def _clear(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _card(self, parent, row, title, badge=None, colors=None):
        ui = self.ui
        card = ctk.CTkFrame(parent, fg_color=ui.SURFACE_ALT, corner_radius=10, border_width=1, border_color=ui.BORDER)
        card.grid(row=row, column=0, sticky="ew", padx=16, pady=6)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, font=ui.font(14, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
        if badge:
            ctk.CTkLabel(card, text=f"  {badge}  ", font=ui.font(13, "bold"), text_color=colors[0],
                         fg_color=colors[1], corner_radius=6).grid(row=0, column=1, sticky="e", padx=14, pady=(12, 0))
        return card

    def _line(self, card, row, text, color, size=12):
        ctk.CTkLabel(card, text=text, font=self.ui.font(size), text_color=color, anchor="w", justify="left",
                     wraplength=600).grid(row=row, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 0))

    def show_results(self, checks=True):
        if self.data is None:
            return
        ui = self.ui
        results = eligibility.evaluate(self.facts(), self.rules, self.line)
        if checks:
            self._clear(self.checks_box)
            row = 0
            q = self.data["quote"]
            quoted, fits = review.recommend(results, q)
            # quote summary and recommendation
            if q:
                card = self._card(self.checks_box, row, "Quote")
                row += 1
                n = 1
                eff = f" - effective {q['effective']}" if q.get("effective") else ""
                self._line(card, n, f"{len(q['drivers'])} driver(s), {len(q['vehicles'])} vehicle(s){eff}", ui.MUTED)
                n += 1
                for c in quoted:
                    verdict = c["verdict"] or "no rules for this carrier in the rules file - check its manual"
                    color = self.colors.get(c["verdict"], (ui.TEXT,))[0]
                    msgs = f", {c['messages']} message(s) below" if c["messages"] else ""
                    prem = f"${c['premium']:,.0f}" if c["premium"] else "not rated"
                    self._line(card, n, f"{c['carrier']}: {prem} - {verdict}{msgs}", color, 13)
                    n += 1
                ctk.CTkLabel(card, text="").grid(row=n, column=0, pady=2)
            if fits:
                card = self._card(self.checks_box, row, "Markets that fit by the rules")
                row += 1
                for n, r in enumerate(fits, 1):
                    self._line(card, n, f"{r['market']}: {r['verdict']}" +
                               (f" - {r['reasons'][0][1]}" if r["reasons"] else ""), self.colors[r["verdict"]][0], 13)
                quoted_names = [c["carrier"].lower() for c in quoted]
                missing = [r["market"] for r in fits if not any(r["market"].split()[0].lower() in qn
                                                                 for qn in quoted_names)]
                if q and missing:
                    self._line(card, len(fits) + 1, "Not on this quote: " + ", ".join(missing) +
                               " - consider quoting it.", ui.TEXT)
                ctk.CTkLabel(card, text="").grid(row=len(fits) + 2, column=0, pady=2)
            elif results:
                card = self._card(self.checks_box, row, "Markets that fit by the rules", "None",
                                  self.colors["Not eligible"])
                row += 1
                self._line(card, 1, "No market in the rules file fits - check other carriers' manuals or the "
                                    "Facility Association.", ui.TEXT)
                ctk.CTkLabel(card, text="").grid(row=2, column=0, pady=2)
            # checks
            items = sorted(review.checks(self.data, self.class_entry.get().strip() or None),
                           key=lambda c: CHECK_ORDER.index(c[0]))
            problems = len([c for c in items if c[0] in ("bad", "refer")])
            badge = ("All good" if not problems else f"{problems} to fix / refer")
            card = self._card(self.checks_box, row, "Checks: quote vs MVR and DASH", badge,
                              (ui.SUCCESS, GOOD_BG) if not problems else (ui.DANGER, BAD_BG))
            for n, (status, text) in enumerate(items, 1):
                icon, color = self.check_style[status]
                self._line(card, n, f"{icon}  {'Refer: ' if status == 'refer' else ''}{text}",
                           ui.MUTED if status == "ok" else color)
            ctk.CTkLabel(card, text="").grid(row=len(items) + 1, column=0, pady=2)

        # markets
        self._clear(self.markets_box)
        ctk.CTkLabel(self.markets_box, text="Result by market", font=ui.font(16, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        for i, res in enumerate(results):
            badge = res["verdict"] + (" so far" if res["incomplete"] and res["verdict"] != "Not eligible" else "")
            card = self._card(self.markets_box, i + 1, res["market"], badge, self.colors[res["verdict"]])
            lines = list(res["reasons"]) or [("Proceed", "No rule in the rules file is broken.", "")]
            if res["incomplete"] and res["verdict"] != "Not eligible":
                lines.append(("", "Not fully checked - enter: " + ", ".join(res["unknown"]), ""))
            for j, (sev, text, src) in enumerate(lines):
                self._line(card, j + 1, f"• {text}" + (f"   ({src})" if src else ""),
                           self.colors.get(sev, (ui.MUTED, None))[0])
            if res.get("note"):
                ctk.CTkLabel(card, text=res["note"], font=ui.font(11), text_color=ui.MUTED, anchor="w",
                             justify="left", wraplength=600) \
                    .grid(row=len(lines) + 1, column=0, columnspan=2, sticky="w", padx=14)
            ctk.CTkLabel(card, text="").grid(row=len(lines) + 2, column=0, pady=2)
        ctk.CTkLabel(self.markets_box, text="Guidance only - based on the rules file and the reports. Confirm anything "
                                            "amber or outside your binding authority with the underwriter or your "
                                            "principal broker before binding.",
                     font=ui.font(11), text_color=ui.MUTED, justify="left", wraplength=560) \
            .grid(row=99, column=0, sticky="w", padx=16, pady=(8, 16))
