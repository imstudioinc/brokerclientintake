"""Review window: the quote checked against the MVR and DASH, and eligibility by market.

Reads the client's DASH report, MVR and Applied Rating quote (any of them may be missing).
Shows one verdict at the top, then what to fix, refer and check, then the markets.
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
from panel import Panel
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

# check status -> (section title, open by default)
SECTIONS = [("decline", "Declined by the carrier", True), ("bad", "Fix in the quote", True), ("refer", "Refer / get approval", True),
            ("warn", "Check with the client", True), ("todo", "Carrier to-dos", False),
            ("info", "Notes", False), ("ok", "Matches", False)]


class EligibilityDialog(Panel):
    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = sys.modules[type(app).__module__]
        self.title(f"Review quote & eligibility - {self.folder.name}")
        self.geometry("1180x840")
        self.minsize(980, 640)
        self.configure(fg_color=ui.BG)
        self.transient(app)
        self.folder_type = app.client_type_of.get(self.folder, "")
        self.data = None
        self.open_sections = {key: is_open for key, _, is_open in SECTIONS}
        self.open_markets = set()
        self.colors = {"Proceed": (ui.SUCCESS, GOOD_BG), "Caution": (CAUTION, CAUTION_BG),
                       "Refer to underwriter": (WARN, WARN_BG), "Not eligible": (ui.DANGER, BAD_BG)}
        self.status_color = {"decline": ui.DANGER, "bad": ui.DANGER, "refer": WARN, "warn": CAUTION, "todo": ui.TEXT,
                             "info": ui.MUTED, "ok": ui.SUCCESS}

        self.grid_columnconfigure(0, weight=0, minsize=330)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------- left: documents, client summary, facts ----------
        left = ctk.CTkScrollableFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1,
                                      border_color=ui.BORDER, width=300)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=(16, 0))
        left.grid_columnconfigure(0, weight=1)
        self.left = left
        ctk.CTkLabel(left, text="Documents", font=ui.font(15, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(14, 2))
        self.docs = review.find_docs(self.folder)
        self.doc_vars = {}
        r = 1
        for kind, label in DOC_LABELS.items():
            ctk.CTkLabel(left, text=label, font=ui.font(12), text_color=ui.MUTED, anchor="w") \
                .grid(row=r, column=0, columnspan=2, sticky="w", padx=14, pady=(6, 0))
            names = [p.name for p in self.docs[kind]] + [NONE]
            var = self.doc_vars[kind] = tk.StringVar(value=names[0])
            ctk.CTkOptionMenu(left, values=names, variable=var, height=30, font=ui.font(12),
                              fg_color=ui.SURFACE_ALT, button_color=ui.PRIMARY, button_hover_color=ui.PRIMARY_HOVER,
                              text_color=ui.TEXT, dynamic_resizing=False, command=lambda _: self.load()) \
                .grid(row=r + 1, column=0, columnspan=2, sticky="ew", padx=14)
            r += 2
        self.status = ctk.CTkLabel(left, text="", font=ui.font(12), text_color=ui.MUTED, anchor="w")
        self.status.grid(row=r, column=0, columnspan=2, sticky="w", padx=14, pady=(4, 0))
        r += 1

        ctk.CTkLabel(left, text="Client", font=ui.font(15, "bold"), text_color=ui.TEXT) \
            .grid(row=r, column=0, columnspan=2, sticky="w", padx=14, pady=(14, 2))
        self.summary = ctk.CTkLabel(left, text="", font=ui.font(13), text_color=ui.TEXT, justify="left",
                                    anchor="w", wraplength=280)
        self.summary.grid(row=r + 1, column=0, columnspan=2, sticky="w", padx=14)
        ctk.CTkLabel(left, text="Licence class (MVR)", font=ui.font(13), text_color=ui.TEXT, anchor="w") \
            .grid(row=r + 2, column=0, sticky="w", padx=(14, 8), pady=(10, 0))
        self.class_entry = ctk.CTkEntry(left, width=64, height=30, font=ui.font(13), justify="center")
        self.class_entry.grid(row=r + 2, column=1, sticky="e", padx=(0, 14), pady=(10, 0))
        self.class_entry.bind("<KeyRelease>", lambda ev: self.show_results())
        self.facts_btn = app.secondary_button(left, "Edit facts ▾", self.toggle_facts)
        self.facts_btn.grid(row=r + 3, column=0, columnspan=2, sticky="ew", padx=14, pady=(12, 4))
        r += 4

        self.facts_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.facts_frame.grid_columnconfigure(0, weight=1)
        self.facts_row = r
        self.entries = {}
        fr = 0
        for key, label in eligibility.FACTS.items():
            if key == eligibility.MANUAL[0]:
                ctk.CTkLabel(self.facts_frame, text="Convictions (from the MVR)", font=ui.font(13, "bold"),
                             text_color=ui.TEXT).grid(row=fr, column=0, columnspan=2, sticky="w", pady=(10, 2))
                fr += 1
            ctk.CTkLabel(self.facts_frame, text=label.strip(), font=ui.font(12), text_color=ui.TEXT, anchor="w",
                         wraplength=210, justify="left").grid(row=fr, column=0, sticky="w", pady=2)
            e = ctk.CTkEntry(self.facts_frame, width=60, height=28, font=ui.font(12), justify="center")
            e.grid(row=fr, column=1, sticky="e", pady=2)
            e.bind("<KeyRelease>", lambda ev: self.show_results(checks=False))
            self.entries[key] = e
            fr += 1

        # ---------- right: verdict, sections, markets ----------
        self.results = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.results.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(16, 0))
        self.results.grid_columnconfigure(0, weight=1)
        self.checks_box = ctk.CTkFrame(self.results, fg_color="transparent")
        self.checks_box.grid(row=0, column=0, sticky="ew")
        self.checks_box.grid_columnconfigure(0, weight=1)
        self.markets_box = ctk.CTkFrame(self.results, fg_color="transparent")
        self.markets_box.grid(row=1, column=0, sticky="ew")
        self.markets_box.grid_columnconfigure(0, weight=1)

        # ---------- bottom ----------
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=12)
        self.rules_label = ctk.CTkLabel(bottom, text="", font=ui.font(11), text_color=ui.MUTED, anchor="w")
        self.rules_label.pack(side="left")
        app.secondary_button(bottom, "Close", self.destroy, width=90).pack(side="right")
        app.secondary_button(bottom, "Rules file…", self.rules_menu, width=110).pack(side="right", padx=8)
        self.bind("<Escape>", lambda e: self.destroy())

        self.load_rules()
        self.after(50, self.load)

    # ---------- rules file ----------
    def load_rules(self):
        self.rules, self.rules_path = eligibility.load_rules(self.app.cfg.get("rules_file"))
        builtin = self.rules_path == eligibility.BUILTIN_RULES
        self.rules_label.configure(text="Rules: built in (Intact, Jevco, Echelon, WellCare - Oct 2026)" if builtin
                                   else f"Rules: {self.rules_path}")

    def rules_menu(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Open rules file", command=lambda: os.startfile(self.rules_path))
        menu.add_command(label="Choose rules file…", command=self.choose_rules)
        menu.add_command(label="Create my rules file (editable copy)…", command=self.create_rules)
        menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

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

    # ---------- documents ----------
    def _path(self, kind):
        return next((p for p in self.docs[kind] if p.name == self.doc_vars[kind].get()), None)

    def load(self):
        """Read the chosen documents in the background (the MVR may need OCR, about a second)."""
        self.status.configure(text="Reading documents…")
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
        facts, _, self.notes = review.facts_from(self.data)
        for key, e in self.entries.items():
            e.delete(0, "end")
            if facts.get(key) is not None:
                e.insert(0, f"{facts[key]:g}" if isinstance(facts[key], float) else str(facts[key]))
        m = self.data["mvr"]
        self.class_entry.delete(0, "end")
        if m and m.get("class"):
            self.class_entry.insert(0, m["class"])

    def toggle_facts(self):
        if self.facts_frame.winfo_ismapped():
            self.facts_frame.grid_remove()
            self.facts_btn.configure(text="Edit facts ▾")
        else:
            self.facts_frame.grid(row=self.facts_row, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14))
            self.facts_btn.configure(text="Hide facts ▴")

    def facts(self):
        out = {}
        for key, e in self.entries.items():
            t = e.get().strip()
            try:
                out[key] = float(t) if t else None
            except ValueError:
                out[key] = None
        return out

    def _summary(self, f):
        """A few plain lines about the client, from the facts."""
        def n(key):
            v = f.get(key)
            return None if v is None else (int(v) if float(v).is_integer() else v)
        cls = self.class_entry.get().strip()
        lines = []
        if n("years_licensed") is not None:
            lines.append(f"Licensed {n('years_licensed')} yrs" + (f" ({cls})" if cls else ""))
        if n("years_insured") is not None:
            lines.append(f"Insured {n('years_insured')} yrs" if n("years_insured") else "No insurance history")
        if n("age") is not None:
            lines.append(f"Age {n('age')}")
        conv = [f"{n(k)} {w}" for k, w in (("minor_convictions_3y", "minor"), ("major_convictions_3y", "major"),
                                            ("serious_convictions_3y", "serious")) if n(k)]
        lines.append("Convictions: " + (", ".join(conv) if conv else "none") if self.data["mvr"] else
                     "Convictions: no MVR")
        lines.append(f"At-fault claims (6 yrs): {n('at_fault_claims_6y') or 0}")
        if n("nonpay_cancellations_3y"):
            lines.append(f"Non-pay cancellations (3 yrs): {n('nonpay_cancellations_3y')}")
        if n("gap_last_12m"):
            lines.append("Gap in the last 12 months")
        return "\n".join(lines)

    # ---------- results ----------
    def _clear(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _text(self, parent, row, text, color, size=13, bold=False, pad=(2, 0), padx=18, wrap=640):
        ctk.CTkLabel(parent, text=text, font=self.ui.font(size, "bold" if bold else "normal"), text_color=color,
                     anchor="w", justify="left", wraplength=wrap).grid(row=row, column=0, columnspan=2, sticky="w",
                                                                       padx=padx, pady=pad)

    def _section(self, row, key, title, items):
        """A card with a clickable header; its lines show when it is open."""
        ui = self.ui
        color = self.status_color[key]
        card = ctk.CTkFrame(self.checks_box, fg_color=ui.SURFACE, corner_radius=10, border_width=1,
                            border_color=ui.BORDER)
        card.grid(row=row, column=0, sticky="ew", pady=5)
        card.grid_columnconfigure(0, weight=1)
        is_open = self.open_sections[key]
        head = ctk.CTkButton(card, text=f"{'▾' if is_open else '▸'}  {title}  ({len(items)})", anchor="w",
                             font=ui.font(14, "bold"), text_color=color, fg_color="transparent",
                             hover_color=ui.SURFACE_ALT, height=36, command=lambda: self._toggle(key))
        head.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 6 if not is_open else 0))
        if is_open:
            for i, text in enumerate(items):
                self._text(card, i + 1, "•  " + text, ui.TEXT if key not in ("info", "ok") else ui.MUTED,
                           pad=(1, 6 if i == len(items) - 1 else 1))

    def _toggle(self, key):
        self.open_sections[key] = not self.open_sections[key]
        self.show_results(checks=True, keep=True)

    def show_results(self, checks=True, keep=False):
        if self.data is None:
            return
        ui = self.ui
        facts = self.facts()
        self.summary.configure(text=self._summary(facts))
        line = review.line_of(self.data, self.folder_type)
        results = eligibility.evaluate(facts, self.rules, line)
        q = self.data["quote"]
        quoted, fits = review.recommend(results, q)
        if checks or keep:
            self.items = review.checks(self.data, self.class_entry.get().strip() or None)
            self.items += [("info", n) for n in getattr(self, "notes", [])
                           if not n.startswith(("At-fault claim", "Claim ", "Coverage gap", "No DASH"))]
        self._clear(self.checks_box)
        groups = {key: [t for s, t in self.items if s == key] for key, _, _ in SECTIONS}

        # ---------- verdict ----------
        declined = [c["carrier"] for c in quoted if c.get("declined")]
        if declined and len(declined) == len(quoted):
            head, color, bg = f"Declined by {', '.join(declined)} - try another market", ui.DANGER, BAD_BG
        elif groups["bad"]:
            head, color, bg = "Fix the quote before sending", ui.DANGER, BAD_BG
        elif groups["refer"]:
            head, color, bg = "Refer before binding", WARN, WARN_BG
        elif groups["warn"]:
            head, color, bg = "Check a few things with the client", CAUTION, CAUTION_BG
        else:
            head, color, bg = "Looks good", ui.SUCCESS, GOOD_BG
        card = ctk.CTkFrame(self.checks_box, fg_color=bg, corner_radius=12)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        card.grid_columnconfigure(0, weight=1)
        self._text(card, 0, head, color, 18, True, pad=(14, 2))
        counts = [f"{len(groups[k])} {w}" for k, w in (("decline", "declined"), ("bad", "to fix"), ("refer", "to refer"),
                                                         ("warn", "to check")) if groups[k]]
        if counts:
            self._text(card, 1, " · ".join(counts), ui.TEXT, 13)
        r = 2
        for c in quoted:
            prem = f"${c['premium']:,.0f}" if c["premium"] else "not rated"
            self._text(card, r, f"Quoted: {c['carrier']} {prem}" + (" - DECLINED (risk not written)"
                                                                    if c.get("declined") else ""),
                       ui.DANGER if c.get("declined") else ui.TEXT, 14, True, pad=(8, 0))
            r += 1
        if fits:
            names = ", ".join(f"{f['market'].split(' (')[0]}" + ("" if f["verdict"] == "Proceed"
                                                                 else f" ({f['verdict'].lower()})") for f in fits)
            quoted_names = " ".join(c["carrier"].lower() for c in quoted)
            missing = [f["market"].split(" (")[0] for f in fits if f["market"].split()[0].lower() not in quoted_names]
            self._text(card, r, f"Fits the rules: {names}" + (f" - not quoted yet" if q and missing else ""),
                       ui.TEXT, 13)
        elif results:
            self._text(card, r, "No market in the rules fits - try other carriers or the Facility Association.",
                       ui.TEXT, 13)
        ctk.CTkLabel(card, text="").grid(row=r + 1, column=0, pady=2)

        # ---------- sections ----------
        row = 1
        for key, title, _ in SECTIONS:
            if groups[key]:
                self._section(row, key, title, groups[key])
                row += 1

        # ---------- markets ----------
        self._clear(self.markets_box)
        card = ctk.CTkFrame(self.markets_box, fg_color=ui.SURFACE, corner_radius=10, border_width=1,
                            border_color=ui.BORDER)
        card.grid(row=0, column=0, sticky="ew", pady=(5, 5))
        card.grid_columnconfigure(0, weight=1)
        self._text(card, 0, "Markets", ui.TEXT, 14, True, pad=(12, 4))
        r = 1
        for res in results:
            name = res["market"]
            fg, bg = self.colors[res["verdict"]]
            badge = res["verdict"] + (" so far" if res["incomplete"] and res["verdict"] != "Not eligible" else "")
            rowf = ctk.CTkFrame(card, fg_color="transparent")
            rowf.grid(row=r, column=0, sticky="ew", padx=10, pady=2)
            rowf.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(rowf, text=f"  {badge}  ", font=ui.font(12, "bold"), text_color=fg, fg_color=bg,
                         corner_radius=6, width=150).grid(row=0, column=0, sticky="w")
            is_open = name in self.open_markets
            first = res["reasons"][0][1] if res["reasons"] else "No rule broken"
            ctk.CTkButton(rowf, text=f"{name.split(' (')[0]} - {first}" if not is_open else name, anchor="w",
                          font=ui.font(13), text_color=ui.TEXT, fg_color="transparent", hover_color=ui.SURFACE_ALT,
                          height=30, command=lambda n=name: self._toggle_market(n)) \
                .grid(row=0, column=1, sticky="ew", padx=(8, 0))
            r += 1
            if is_open:
                lines = [t for _, t, _ in res["reasons"]] or ["No rule in the rules file is broken."]
                if res["incomplete"] and res["verdict"] != "Not eligible":
                    lines.append("Not fully checked - enter: " + ", ".join(res["unknown"]))
                for t in lines:
                    self._text(card, r, "•  " + t, ui.TEXT, 12, padx=40, wrap=600)
                    r += 1
                if res.get("note"):
                    self._text(card, r, res["note"], ui.MUTED, 11, padx=40, wrap=600)
                    r += 1
        self._text(card, r, "Click a market for all its reasons. Guidance only - confirm with the underwriter "
                            "before binding.", ui.MUTED, 11, pad=(8, 12))

    def _toggle_market(self, name):
        self.open_markets ^= {name}
        self.show_results(checks=False, keep=True)
