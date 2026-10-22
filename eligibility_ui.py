"""Check eligibility window: DASH facts (+ MVR convictions typed in) against the rules file."""
import os
import shutil
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import config
import eligibility

WARN = ("#B45309", "#FBBF24")
WARN_BG = ("#FEF3C7", "#3A2E12")
CAUTION = ("#6B5B1E", "#E5D38A")
CAUTION_BG = ("#F5F0DC", "#2E2A1A")
GOOD_BG = ("#E8F5EC", "#16291D")
BAD_BG = ("#FDECEC", "#3A1D1D")


class EligibilityDialog(ctk.CTkToplevel):
    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = sys.modules[type(app).__module__]
        self.title(f"Check eligibility - {self.folder.name}")
        self.geometry("1120x760")
        self.minsize(960, 620)
        self.configure(fg_color=ui.BG)
        self.transient(app)

        self.grid_columnconfigure(0, weight=2, uniform="c")
        self.grid_columnconfigure(1, weight=3, uniform="c")
        self.grid_rowconfigure(0, weight=1)

        # ---------- left: facts ----------
        left = ctk.CTkScrollableFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1,
                                      border_color=ui.BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=(16, 0))
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="Client facts", font=ui.font(16, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 0))

        self.dash_files = sorted(self.folder.glob("DASH Report*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        self.dash_var = tk.StringVar(value=self.dash_files[0].name if self.dash_files else "No DASH report in folder")
        ctk.CTkOptionMenu(left, values=[p.name for p in self.dash_files] or ["No DASH report in folder"],
                          variable=self.dash_var, height=32, font=ui.font(12), fg_color=ui.SURFACE_ALT,
                          button_color=ui.PRIMARY, button_hover_color=ui.PRIMARY_HOVER, text_color=ui.TEXT,
                          dynamic_resizing=False, command=lambda _: self.load_dash()) \
            .grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 4))
        ctk.CTkLabel(left, text="Read from the DASH report - correct anything that looks wrong.",
                     font=ui.font(12), text_color=ui.MUTED).grid(row=2, column=0, columnspan=2, sticky="w", padx=16)

        self.entries = {}
        r = 3
        for key, label in eligibility.FACTS.items():
            if key in eligibility.MANUAL and key == eligibility.MANUAL[0]:
                ctk.CTkLabel(left, text="From the MVR (type in)", font=ui.font(13, "bold"), text_color=ui.TEXT) \
                    .grid(row=r, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 2))
                r += 1
            ctk.CTkLabel(left, text=label, font=ui.font(13), text_color=ui.TEXT, anchor="w") \
                .grid(row=r, column=0, sticky="w", padx=(16, 8), pady=3)
            e = ctk.CTkEntry(left, width=70, height=30, font=ui.font(13), justify="center",
                             border_color=ui.PRIMARY if key in eligibility.MANUAL else ui.BORDER)
            e.grid(row=r, column=1, sticky="e", padx=(0, 16), pady=3)
            e.bind("<KeyRelease>", lambda ev: self.evaluate())
            self.entries[key] = e
            r += 1

        ctk.CTkLabel(left, text="Worth a look", font=ui.font(13, "bold"), text_color=ui.TEXT) \
            .grid(row=r, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 2))
        self.notes = ctk.CTkLabel(left, text="", font=ui.font(12), text_color=WARN, justify="left",
                                  anchor="w", wraplength=360)
        self.notes.grid(row=r + 1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 16))

        # ---------- right: results ----------
        self.results = ctk.CTkScrollableFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1,
                                              border_color=ui.BORDER)
        self.results.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(16, 0))
        self.results.grid_columnconfigure(0, weight=1)

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
        self.load_dash()

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
            self.evaluate()
            os.startfile(p)

    def choose_rules(self):
        p = filedialog.askopenfilename(parent=self, title="Choose the rules file", filetypes=[("Rules file", "*.json")])
        if p:
            config.update(self.app.cfg, rules_file=str(Path(p)))
            self.load_rules()
            self.evaluate()

    def open_rules(self):
        os.startfile(self.rules_path)

    # ---------- facts ----------
    def load_dash(self):
        facts, notes = {}, []
        path = next((p for p in self.dash_files if p.name == self.dash_var.get()), None)
        if path:
            try:
                facts, _, notes = eligibility.read_dash_facts(path)
            except Exception as e:
                notes = [f"Could not read the DASH report: {e}"]
        else:
            notes = ["No DASH report in this client's folder - use Import DASH first, or type the facts in."]
        for key, e in self.entries.items():
            if key in eligibility.MANUAL and e.get():
                continue  # keep what the broker typed from the MVR
            e.delete(0, "end")
            if facts.get(key) is not None:
                e.insert(0, str(facts[key]))
        self.notes.configure(text="\n\n".join("• " + n for n in notes) or "Nothing unusual found.")
        self.evaluate()

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
    def evaluate(self):
        ui = self.ui
        for w in self.results.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.results, text="Result by market", font=ui.font(16, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        colors = {"Proceed": (ui.SUCCESS, GOOD_BG), "Caution": (CAUTION, CAUTION_BG),
                  "Refer to underwriter": (WARN, WARN_BG), "Not eligible": (ui.DANGER, BAD_BG)}
        for i, res in enumerate(eligibility.evaluate(self.facts(), self.rules)):
            fg, bg = colors[res["verdict"]]
            card = ctk.CTkFrame(self.results, fg_color=ui.SURFACE_ALT, corner_radius=10, border_width=1,
                                border_color=ui.BORDER)
            card.grid(row=i + 1, column=0, sticky="ew", padx=16, pady=6)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=res["market"], font=ui.font(14, "bold"), text_color=ui.TEXT, anchor="w") \
                .grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
            badge = res["verdict"] + (" so far" if res["incomplete"] and res["verdict"] != "Not eligible" else "")
            ctk.CTkLabel(card, text=f"  {badge}  ", font=ui.font(13, "bold"), text_color=fg,
                         fg_color=bg, corner_radius=6).grid(row=0, column=1, sticky="e", padx=14, pady=(12, 0))
            lines = list(res["reasons"]) or [("Proceed", "No rule in the rules file is broken.", "")]
            if res["incomplete"] and res["verdict"] != "Not eligible":
                lines.append(("", "Not fully checked - enter: " + ", ".join(res["unknown"]), ""))
            for j, (sev, text, src) in enumerate(lines):
                color = colors.get(sev, (ui.MUTED, None))[0]
                ctk.CTkLabel(card, text=f"• {text}" + (f"   ({src})" if src else ""), font=ui.font(12),
                             text_color=color, anchor="w", justify="left", wraplength=560) \
                    .grid(row=j + 1, column=0, columnspan=2, sticky="w", padx=14, pady=(4 if j == 0 else 0, 0))
            if res.get("note"):
                ctk.CTkLabel(card, text=res["note"], font=ui.font(11), text_color=ui.MUTED, anchor="w",
                             justify="left", wraplength=560) \
                    .grid(row=len(lines) + 1, column=0, columnspan=2, sticky="w", padx=14)
            ctk.CTkLabel(card, text="").grid(row=len(lines) + 2, column=0, pady=2)
        ctk.CTkLabel(self.results, text="Guidance only - based on the rules file and the reports. Confirm anything "
                                        "amber or outside your binding authority with the underwriter or your "
                                        "principal broker before binding.",
                     font=ui.font(11), text_color=ui.MUTED, justify="left", wraplength=520) \
            .grid(row=99, column=0, sticky="w", padx=16, pady=(8, 16))
