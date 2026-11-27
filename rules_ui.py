"""Rules view: the underwriting notes, inside the main window (next to Clients and Tracker).

Three sections (tabs): Search (home tiles, then result cards), and one tab per guide (ride sharing, billing by company).
A guide is a note of the notes folder with a "## Compare" table: it is shown as a comparison table (one row per insurer,
colour-coded Yes / No / Ask pills) and a click on a row opens that insurer's short fact sheet. Long notes open in a page of
their own (NotePage), never in Notepad.
"""
import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import carriers_ui
import config
import notes_search
import ui_kit
from panel import Panel

EXAMPLES = ["intact G2 at-fault", "pembridge oil tank", "echelon monthly payment", "motorcycle M1 course",
            "jevco minor accident", "OPCF 43", "winter tire discount", "nsf fee", "uber turo"]

# The sections of the Rules view: Search, and one tab for each guide.
# (tab text, word in the guide's file name, what to call the note when it is missing, what the home tile says)
TABS = [("Search", "", "", ""),
        ("Ride sharing", "ride sharing", "Ride sharing and car sharing - by insurer",
         "Who accepts Uber, Lyft, Turo and delivery apps - and what to add to the policy"),
        ("Billing by company", "billing", "Billing and payment policy - by insurer",
         "Monthly payments, down payment, NSF fee and agency bill for every insurer")]
TAB_ON = ("#FFFFFF", "#44566B")          # the open tab: clearly lighter than the others
SELECTED = ("#E8F0FE", "#1F2D45")       # the open row / item


def _pick(pair):
    return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]


def setup_tags(tb, ui, scale):
    """Tags for a text box that shows notes. Sizes are pixels (negative), the unit CTk fonts use, times the
    text-size setting so the text is as large as the rest of the app."""
    px = lambda n: -int(round(n * scale))  # noqa: E731
    tb.tag_configure("gap", font=(ui.FONT, px(10)))          # empty line between two results (not in the title bar)
    tb.tag_configure("title", font=(ui.FONT, px(18), "bold"), spacing1=int(6 * scale), spacing3=2,
                     lmargin1=10, lmargin2=10)
    tb.tag_configure("source", font=(ui.FONT, px(13)), spacing3=int(8 * scale), lmargin1=10, lmargin2=10)
    tb.tag_configure("lead", font=(ui.FONT, px(15), "bold"), spacing1=int(12 * scale), lmargin1=14, lmargin2=14)
    tb.tag_configure("bullet", font=(ui.FONT, px(15)), spacing1=int(8 * scale), lmargin1=14, lmargin2=34)
    tb.tag_configure("sub", font=(ui.FONT, px(15)), spacing1=int(5 * scale), lmargin1=34, lmargin2=54)
    tb.tag_configure("hit", font=(ui.FONT, px(15), "bold"))
    tb.tag_configure("more", font=(ui.FONT, px(14), "bold"), spacing1=int(10 * scale), lmargin1=14)
    tb.tag_configure("meta", font=(ui.FONT, px(14)), spacing1=4)
    tb.tag_configure("h1", font=(ui.FONT, px(22), "bold"), spacing3=int(10 * scale))
    # a fact row: "Label" in a narrow muted column, the value beside it; a wrapped value lines up under the value
    label_w = int(168 * scale)
    tb.tag_configure("kv", tabs=(label_w,), lmargin1=14, lmargin2=14 + label_w, spacing1=int(9 * scale))
    tb.tag_configure("kvlabel", font=(ui.FONT, px(13), "bold"))
    tb.tag_configure("kvvalue", font=(ui.FONT, px(15)))
    tb.tag_configure("kvlink", font=(ui.FONT, px(15), "bold"))
    for tone in ("ok", "no", "ask"):
        tb.tag_configure("kvlabel_" + tone, font=(ui.FONT, px(13), "bold"))
        tb.tag_configure("pill_" + tone, font=(ui.FONT, px(13), "bold"))
    recolor(tb, ui)


# the verdict colours: soft background + strong text, always with the word in it (never colour alone)
TONES = {"ok": (("#DCF2E3", "#1B3A28"), ("#11713A", "#7FE0A4")),
         "no": (("#FBE3E1", "#4A1F1D"), ("#B3261E", "#FF9C93")),
         "ask": (("#FDF0D5", "#4A3A14"), ("#8A5300", "#F6C45F"))}


def fit_width(tb, width, scale, max_px=900):
    """Keep lines a readable length (about 100 characters): the text stops `max_px` from the left even in a wide window."""
    right = max(24, int(width - max_px * scale))
    for tag in ("lead", "bullet", "sub", "kv", "meta", "more", "title", "source"):
        tb.tag_configure(tag, rmargin=right if tag not in ("title", "source") else 0)


def recolor(tb, ui):
    for tone, (bg, fg) in TONES.items():
        tb.tag_configure("pill_" + tone, background=_pick(bg), foreground=_pick(fg))
        tb.tag_configure("kvlabel_" + tone, foreground=_pick(fg))
    tb.tag_configure("kvlabel", foreground=_pick(ui.MUTED))
    tb.tag_configure("kvvalue", foreground=_pick(ui.TEXT))
    tb.tag_configure("kvlink", foreground=_pick(ui.ACCENT))
    tb.tag_configure("title", foreground=_pick(ui.TEXT), background=_pick(BAND))
    tb.tag_configure("source", foreground=_pick(ui.MUTED), background=_pick(BAND))
    tb.tag_configure("lead", foreground=_pick(ui.TEXT))
    tb.tag_configure("bullet", foreground=_pick(ui.TEXT))
    tb.tag_configure("sub", foreground=_pick(ui.TEXT))
    tb.tag_configure("hit", background=_pick(HIT_BG), foreground=_pick(ui.TEXT))
    tb.tag_configure("more", foreground=_pick(ui.ACCENT))
    tb.tag_configure("meta", foreground=_pick(ui.MUTED))
    tb.tag_configure("h1", foreground=_pick(ui.TEXT))


def insert_marked(tb, text, base, pattern):
    """Insert text with the question's words marked."""
    pos = 0
    for m in pattern.finditer(text) if pattern else ():
        tb.insert("end", text[pos:m.start()], base)
        tb.insert("end", m.group(0), (base, "hit"))
        pos = m.end()
    tb.insert("end", text[pos:], base)


def render_item(tb, item, pattern, focus=False):
    """One note line as a lead + short bullets (or a single bullet).

    focus=True (search results): of a long run-on line only the bullets that mention what was searched for are shown,
    at most 3, and the rest is counted ("+ 9 more") - the whole line is one click away in the note."""
    lead, parts = notes_search.split_item(item)
    hidden = 0
    if focus and pattern and len(parts) > 3:
        hits = [p for p in parts if pattern.search(p)]
        shown = (hits or parts)[:3]
        hidden = len(parts) - len(shown)
        parts = shown
    if lead:
        insert_marked(tb, lead + "\n", "lead", pattern)
        for part in parts:
            insert_marked(tb, "•  " + part + "\n", "sub", pattern)
    else:
        insert_marked(tb, "•  " + parts[0] + "\n", "bullet", pattern)
        for part in parts[1:]:
            insert_marked(tb, "–  " + part + "\n", "sub", pattern)
    if hidden:
        tb.insert("end", f"+ {hidden} more in this line\n", ("sub", "meta"))


PILL_WORDS = {"yes": "ok", "accepted": "ok", "no": "no", "declined": "no", "ask": "ask", "fleet": "ask", "partly": "ask"}


def tone_of(text):
    """ok / no / ask for a pill's text (Yes / No / Ask / Fleet policy / Partly), None for anything else."""
    first = re.sub(r"[^a-z]", "", (text or "").strip().split(" ")[0].lower())
    return PILL_WORDS.get(first)


def make_pill(parent, ui, text, width=112):
    """A coloured status label: soft background + strong text, always with the word in it (never colour alone)."""
    tone = tone_of(text)
    bg, fg = TONES[tone] if tone else (ui.SURFACE_ALT, ui.TEXT)
    return ctk.CTkLabel(parent, text=text, width=width, height=28, corner_radius=8, fg_color=bg, text_color=fg,
                        font=ui.font(13, "bold"))


def on_click(widget, command, cursor="hand2"):
    """Make a whole group of widgets clickable (the widget and everything inside it)."""
    try:
        widget.bind("<Button-1>", lambda e: command())
        widget.configure(cursor=cursor)
    except (tk.TclError, ValueError, NotImplementedError):
        pass
    for child in widget.winfo_children():
        on_click(child, command, cursor)


def snippet(text, n=170):
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    return cut + "…"


class _Pane(ctk.CTkScrollableFrame):
    """A scrolling pane whose long-text labels wrap to the pane's width."""

    def __init__(self, master, app, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app
        self.ui = sys.modules[type(app).__module__]
        self.grid_columnconfigure(0, weight=1)
        self.wrapped = []                    # (label, pixels taken from the pane's width - or a function of the width)
        self._wrap_job = None
        self._width = 0
        self.bind("<Configure>", self._on_resize, add="+")

    def _on_resize(self, event):
        if abs(event.width - self._width) < 30:
            return
        self._width = event.width
        if self._wrap_job:
            self.after_cancel(self._wrap_job)
        self._wrap_job = self.after(120, self.rewrap)

    def rewrap(self):
        self._wrap_job = None
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        for label, taken in self.wrapped:
            if label.winfo_exists():
                label.configure(wraplength=self._wrap_for(taken, self._width / scale))

    def clear(self):
        for w in self.winfo_children():
            w.destroy()
        self.wrapped = []

    @staticmethod
    def _wrap_for(taken, width):
        return max(110, int(taken(width)) if callable(taken) else max(160, int(width) - taken))

    def add_wrapped(self, label, taken):
        self.wrapped.append((label, taken))
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        label.configure(wraplength=self._wrap_for(taken, (self._width or 1000) / scale))


# ---------------------------------------------------------------------------- home (Search with nothing typed)
class HomePane(_Pane):
    """What the Search section shows before anything is typed: a tile for each guide, example searches, all notes."""

    def build(self, view):
        ui, SP = self.ui, self.ui.SP
        self.clear()
        tiles = ctk.CTkFrame(self, fg_color="transparent")
        tiles.grid(row=0, column=0, sticky="ew", padx=SP, pady=(SP, 0))
        tiles.grid_columnconfigure((0, 1), weight=1, uniform="tile")
        for col, (name, key, _title, subtitle) in enumerate(TABS[1:]):
            found = view.guide_note(key) is not None
            card = ctk.CTkFrame(tiles, fg_color=ui.SURFACE, corner_radius=14, border_width=1, border_color=ui.BORDER)
            card.grid(row=0, column=col, sticky="nsew", padx=(0, SP) if col == 0 else (SP, 0))
            ctk.CTkLabel(card, text=name, font=ui.font(20, "bold"), text_color=ui.TEXT, anchor="w") \
                .pack(fill="x", padx=2 * SP, pady=(2 * SP, 2))
            body = ctk.CTkLabel(card, text=subtitle if found else "Not in your notes folder yet - open it to see what to copy.",
                                font=ui.font(14), text_color=ui.MUTED, anchor="w", justify="left", wraplength=380)
            body.pack(fill="x", padx=2 * SP)
            ctk.CTkLabel(card, text="Open  ›", font=ui.font(14, "bold"), text_color=ui.ACCENT, anchor="w") \
                .pack(fill="x", padx=2 * SP, pady=(SP, 2 * SP))
            on_click(card, lambda n=name: view.show_tab(n))
        ctk.CTkLabel(self, text="Try a search", font=ui.font(14, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=1, column=0, sticky="w", padx=SP, pady=(3 * SP, SP / 2))
        chips = ctk.CTkFrame(self, fg_color="transparent")
        chips.grid(row=2, column=0, sticky="w", padx=SP)
        for i, ex in enumerate(EXAMPLES):
            ctk.CTkButton(chips, text=ex, height=32, corner_radius=16, font=ui.font(13), fg_color=ui.SURFACE,
                          border_width=1, border_color=ui.BORDER, text_color=ui.TEXT, hover_color=ui.SURFACE_ALT,
                          width=len(ex) * 8 + 30, command=lambda ex=ex: view.search_for(ex)) \
                .grid(row=i // 5, column=i % 5, padx=(0, SP), pady=(0, SP))
        if view.index and view.index.notes:
            ctk.CTkLabel(self, text=f"All notes ({len(view.index.notes)})", font=ui.font(14, "bold"),
                         text_color=ui.TEXT, anchor="w").grid(row=3, column=0, sticky="w", padx=SP, pady=(2 * SP, SP / 2))
            grid = ctk.CTkFrame(self, fg_color="transparent")
            grid.grid(row=4, column=0, sticky="ew", padx=SP, pady=(0, 2 * SP))
            grid.grid_columnconfigure((0, 1), weight=1, uniform="n")
            for i, name in enumerate(view.index.notes):
                ctk.CTkButton(grid, text=ui.shorten(Path(name).stem, 52), anchor="w", height=34, corner_radius=8,
                              font=ui.font(13), fg_color="transparent", text_color=ui.TEXT, hover_color=ui.SURFACE,
                              command=lambda n=name: view.open_note(n)) \
                    .grid(row=i // 2, column=i % 2, sticky="ew", padx=2, pady=1)


# ---------------------------------------------------------------------------- search results as cards
class ResultsPane(_Pane):
    """Search results as cards: the section, which note it is from, and only the few lines that matter."""

    def show(self, results, words, view):
        ui, SP = self.ui, self.ui.SP
        self.clear()
        if not results:
            ctk.CTkLabel(self, text="Nothing found.\nTry fewer or different words - a carrier name plus one or two "
                                    "key words works best.", font=ui.font(15), text_color=ui.MUTED, anchor="w",
                         justify="left").grid(row=0, column=0, sticky="w", padx=2 * SP, pady=2 * SP)
            return
        pattern = re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\w*", re.I) if words else None
        for i, r in enumerate(results):
            card = ctk.CTkFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
            card.grid(row=i, column=0, sticky="ew", padx=SP, pady=(0, SP))
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=r["heading"] or r["title"], font=ui.font(17, "bold"), text_color=ui.TEXT,
                         anchor="w").grid(row=0, column=0, sticky="w", padx=(2 * SP, SP), pady=(1.5 * SP, 0))
            ctk.CTkLabel(card, text=r["title"], font=ui.font(12), text_color=ui.MUTED, anchor="w") \
                .grid(row=1, column=0, sticky="w", padx=2 * SP)
            lines, hidden = [], r["more"]
            for item in r["items"]:
                lead, parts = notes_search.split_item(item)
                if pattern and len(parts) > 3:
                    hits = [p for p in parts if pattern.search(p)]
                    keep = (hits or parts)[:3]
                    hidden += len(parts) - len(keep)
                    parts = keep
                lines += [(lead + " " + p) if lead else p for p in parts]
            shown = lines[:4]
            hidden += len(lines) - len(shown)
            for k, text in enumerate(shown):
                lab = ctk.CTkLabel(card, text="•  " + snippet(text), font=ui.font(14), text_color=ui.TEXT, anchor="w",
                                   justify="left")
                lab.grid(row=2 + k, column=0, sticky="w", padx=2 * SP, pady=(SP / 2 if k == 0 else 2, 0))
                self.add_wrapped(lab, 150)
            foot = ctk.CTkFrame(card, fg_color="transparent", height=1)
            foot.grid(row=2 + len(shown), column=0, sticky="ew", padx=2 * SP, pady=(SP / 2, SP))
            ctk.CTkLabel(foot, text=f"+ {hidden} more" if hidden > 0 else "", font=ui.font(12), text_color=ui.MUTED) \
                .pack(side="left")
            ctk.CTkLabel(foot, text="Read the note  ›", font=ui.font(13, "bold"), text_color=ui.ACCENT).pack(side="right")
            on_click(card, lambda r=r: view.open_note(r["note"], r["heading"]))


# ---------------------------------------------------------------------------- a guide: comparison table + insurer sheet
def read_guide(path):
    """(tips, header, rows, sections) of a guide note: the "## Compare" section's tips (- lines) and table, and the
    insurers' own "##" sections."""
    text = path.read_text(encoding="utf-8-sig")
    tips, header, rows = [], [], []
    m = re.search(r"^##\s+Compare\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    for line in (m.group(1).splitlines() if m else []):
        s = line.strip()
        if s.startswith("|"):
            cells = [notes_search.clean(c) for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cells):
                continue
            if not header:
                header = cells
            else:
                rows.append((cells + [""] * len(header))[:len(header)])
        elif s.startswith("- "):
            tip = re.sub(r"^Tip:\s*", "", notes_search.clean(s[2:]), flags=re.I)
            tips.append(tip[:1].upper() + tip[1:])
    sections = [s for s in notes_search.parse(path.name, text)
                if s["heading"] and s["items"] and s["heading"].strip().lower() != "compare"]
    return tips, header, rows, sections


class GuideView(ctk.CTkFrame):
    """One guide: a comparison table (insurer rows, status pills, short text), and a click on a row opens that insurer's
    short fact sheet with Back / Previous / Next. Says what to copy where when the note is missing."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        ui = self.ui = sys.modules[type(app).__module__]
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.table = _Pane(self, app)
        self.table.grid(row=0, column=0, sticky="nsew")
        self.detail = ctk.CTkFrame(self, fg_color="transparent")
        self.detail.grid_columnconfigure(0, weight=1)
        self.detail.grid_rowconfigure(1, weight=1)
        self.detail.grid(row=0, column=0, sticky="nsew")
        self.detail.grid_remove()
        self.tips, self.header, self.rows, self.sections = [], [], [], []
        self.stamp, self.open_index = None, None

    # ---- loading
    def load(self, path, title, folder):
        try:
            stamp = (str(path), path.stat().st_mtime) if path else None
        except OSError:
            stamp = None
        if stamp and stamp == self.stamp:
            self.close_detail()
            return
        self.stamp = stamp
        self.close_detail()
        ui = self.ui
        self.table.clear()
        if not stamp:
            box = ctk.CTkFrame(self.table, fg_color=ui.SURFACE, corner_radius=14, border_width=1, border_color=ui.BORDER)
            box.grid(row=0, column=0, sticky="ew", padx=ui.SP, pady=ui.SP)
            ctk.CTkLabel(box, text="This guide is not in your notes folder yet", font=ui.font(20, "bold"),
                         text_color=ui.TEXT, anchor="w").pack(fill="x", padx=3 * ui.SP, pady=(3 * ui.SP, 4))
            ctk.CTkLabel(box, text=f"Copy the note called \"{title}\" (a .md file) into this folder, then press "
                                   "Reload notes:", font=ui.font(14), text_color=ui.MUTED, anchor="w", justify="left") \
                .pack(fill="x", padx=3 * ui.SP)
            ctk.CTkLabel(box, text=str(folder), font=ui.font(14, "bold"), text_color=ui.TEXT, anchor="w",
                         justify="left", wraplength=800).pack(fill="x", padx=3 * ui.SP, pady=(ui.SP, 3 * ui.SP))
            return
        try:
            self.tips, self.header, self.rows, self.sections = read_guide(path)
        except OSError:
            self.tips, self.header, self.rows, self.sections = [], [], [], []
        if not self.rows:                    # a note without a Compare table: one row per section
            self.header = ["Name", "Summary"]
            self.rows = [[s["heading"], notes_search.clean((s["items"][0] if s["items"] else "")[:140])]
                         for s in self.sections]
        self.build_table()

    def section_for(self, name):
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        for s in self.sections:
            if re.sub(r"[^a-z0-9]", "", s["heading"].lower()) == key:
                return s
        for s in self.sections:
            head = re.sub(r"[^a-z0-9]", "", s["heading"].lower())
            if head.startswith(key[:6]) or key.startswith(head[:6]):
                return s
        return None

    # ---- the comparison table
    def build_table(self):
        ui, SP = self.ui, self.ui.SP
        t = self.table
        t.clear()
        r0 = 0
        if self.tips:
            note = ctk.CTkFrame(t, fg_color=SELECTED, corner_radius=10)
            note.grid(row=0, column=0, sticky="ew", padx=SP, pady=(SP, SP))
            for tip in self.tips:
                lab = ctk.CTkLabel(note, text="•  " + tip, font=ui.font(14), text_color=ui.TEXT, anchor="w", justify="left")
                lab.pack(fill="x", padx=2 * SP, pady=(SP if tip is self.tips[0] else 2, SP if tip is self.tips[-1] else 0))
                t.add_wrapped(lab, 130)
            r0 = 1
        grid = ctk.CTkFrame(t, fg_color=ui.SURFACE, corner_radius=14, border_width=1, border_color=ui.BORDER)
        grid.grid(row=r0, column=0, sticky="ew", padx=SP, pady=(0, SP))
        pills = [h.endswith("[pill]") for h in self.header]
        heads = [h.replace("[pill]", "").strip() for h in self.header]
        ncols = len(heads)
        for c in range(ncols):
            grid.grid_columnconfigure(c, weight=(0 if c == 0 or pills[c] else 1),
                                      minsize=210 if c == 0 else 128 if pills[c] else 0)
        grid.grid_columnconfigure(ncols, weight=0, minsize=34)
        for c, h in enumerate(heads):
            ctk.CTkLabel(grid, text=h.upper(), font=ui.font(12, "bold"), text_color=ui.MUTED, anchor="w" if not pills[c] else "center") \
                .grid(row=0, column=c, sticky="ew", padx=(2 * SP if c == 0 else SP, SP), pady=(1.5 * SP, SP))
        n_text = max(1, sum(1 for p in pills[1:] if not p))
        n_pill = sum(1 for p in pills if p)
        share = lambda width: (width - 210 - 34 - 70 - 128 * n_pill) / n_text - 26      # noqa: E731
        for i, row in enumerate(self.rows):
            r = 1 + i * 2
            ctk.CTkFrame(grid, fg_color=ui.BORDER, height=1).grid(row=r, column=0, columnspan=ncols + 1, sticky="ew")
            cells = []
            for c, value in enumerate(row):
                if c == 0:
                    w = ctk.CTkLabel(grid, text=value, font=ui.font(15, "bold"), text_color=ui.TEXT, anchor="w")
                    w.grid(row=r + 1, column=c, sticky="w", padx=(2 * SP, SP), pady=SP)
                elif pills[c]:
                    w = make_pill(grid, ui, value)
                    w.grid(row=r + 1, column=c, padx=SP, pady=SP)
                else:
                    w = ctk.CTkLabel(grid, text=value or "", font=ui.font(14), text_color=ui.TEXT, anchor="w", justify="left")
                    w.grid(row=r + 1, column=c, sticky="w", padx=SP, pady=SP)
                    t.add_wrapped(w, share)
                cells.append(w)
            arrow = ctk.CTkLabel(grid, text="›", font=ui.font(20), text_color=ui.MUTED)
            arrow.grid(row=r + 1, column=ncols, padx=(0, SP))
            cells.append(arrow)
            for w in cells:
                on_click(w, lambda i=i: self.open_row(i))
        ctk.CTkFrame(grid, fg_color="transparent", height=SP).grid(row=2 + 2 * len(self.rows), column=0)

    # ---- one insurer
    def close_detail(self):
        self.open_index = None
        self.detail.grid_remove()
        self.table.grid()

    def open_row(self, i):
        ui, SP = self.ui, self.ui.SP
        self.open_index = i
        row = self.rows[i]
        name = row[0]
        sec = self.section_for(name)
        self.table.grid_remove()
        for w in self.detail.winfo_children():
            w.destroy()
        self.detail.grid()
        bar = ctk.CTkFrame(self.detail, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=SP, pady=(SP, SP))
        self.app.secondary_button(bar, "‹  All insurers", self.close_detail, width=130).pack(side="left")
        ctk.CTkLabel(bar, text=name, font=ui.font(24, "bold"), text_color=ui.TEXT).pack(side="left", padx=(2 * SP, SP))
        verdict = next((x.split(":", 1)[1].strip() for x in (sec["items"] if sec else []) if x.lower().startswith("verdict:")), "")
        if verdict:
            make_pill(bar, ui, verdict, width=0).pack(side="left", padx=SP)
        nav = ctk.CTkFrame(bar, fg_color="transparent")
        nav.pack(side="right")
        self.app.secondary_button(nav, "Next  ›", lambda: self.open_row((i + 1) % len(self.rows)), width=96).pack(side="right")
        self.app.secondary_button(nav, "‹  Previous", lambda: self.open_row((i - 1) % len(self.rows)), width=110) \
            .pack(side="right", padx=(0, SP))
        body = _Pane(self.detail, self.app)
        body.grid(row=1, column=0, sticky="nsew")
        facts = [x for x in (sec["items"] if sec else []) if not x.lower().startswith("verdict:")]
        if not facts:                         # no sheet of its own: the table row, with its column names
            facts = [f"{h.replace('[pill]', '').strip()}: {v}" for h, v in zip(self.header[1:], row[1:]) if v and v != "-"]
        for k, item in enumerate(facts):
            m = re.match(r"^([^:;]{2,26}):\s+(.+)$", item, re.S)
            label, value = (m.group(1), m.group(2)) if m else ("", item)
            value = value[:1].upper() + value[1:]
            card = ctk.CTkFrame(body, fg_color=ui.SURFACE, corner_radius=10, border_width=1, border_color=ui.BORDER)
            card.grid(row=k, column=0, sticky="ew", padx=SP, pady=(0, SP / 2 + 1))
            card.grid_columnconfigure(1, weight=1)
            if label:
                ctk.CTkLabel(card, text=label, width=190, anchor="nw", justify="left", font=ui.font(14, "bold"),
                             text_color=ui.MUTED).grid(row=0, column=0, sticky="nw", padx=(2 * SP, SP), pady=(1.5 * SP, 1.5 * SP))
            if label and "contact" in label.lower():           # phone / email: one click copies it
                chips = ctk.CTkFrame(card, fg_color="transparent")
                chips.grid(row=0, column=1, sticky="w", pady=SP)
                for part in [x.strip() for x in value.split(";") if x.strip()]:
                    b = ctk.CTkButton(chips, text=part, height=32, corner_radius=8, font=ui.font(14), fg_color=ui.SURFACE_ALT,
                                      text_color=ui.TEXT, hover_color=ui.BORDER, border_width=1, border_color=ui.BORDER,
                                      width=len(part) * 8 + 24)
                    b.configure(command=lambda p=part, b=b: self.copy(p, b))
                    b.pack(side="left", padx=(0, SP))
                continue
            lab = ctk.CTkLabel(card, text=value, font=ui.font(16), text_color=ui.TEXT, anchor="w", justify="left")
            lab.grid(row=0, column=1 if label else 0, columnspan=1 if label else 2, sticky="w", padx=(0, 2 * SP) if label else 2 * SP,
                     pady=1.5 * SP)
            body.add_wrapped(lab, 330 if label else 150)

    def copy(self, text, button):
        self.app.clipboard_clear()
        self.app.clipboard_append(text)
        old = button.cget("text")
        button.configure(text="Copied  ✓")
        button.after(1500, lambda: button.winfo_exists() and button.configure(text=old))


class RulesView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        ui = self.ui = sys.modules[type(app).__module__]
        self.index = None
        self._job = None
        self.tab = "Search"
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        SP = ui.SP

        # ---------- header: title, the sections, the search box ----------
        head = app.card(self, row=0, column=0)
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Rules", font=ui.font(16, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, sticky="w", padx=2 * SP, pady=(1.5 * SP, 0))
        btns = ctk.CTkFrame(head, fg_color="transparent")
        btns.grid(row=0, column=1, sticky="e", padx=2 * SP, pady=(1.5 * SP, 0))
        app.secondary_button(btns, "Notes folder…", self.choose_notes, width=120).pack(side="right")
        app.secondary_button(btns, "Reload notes", self.reload, width=110).pack(side="right", padx=SP)
        app.secondary_button(btns, "Carriers & payments", lambda: carriers_ui.CarrierInfoPage(app), width=160) \
            .pack(side="right")
        self.tabs = ui_kit.Segmented(head, values=[t[0] for t in TABS], height=38, font=ui.font(14, "bold"),
                                     selected_color=TAB_ON, selected_hover_color=TAB_ON,
                                     unselected_color=ui.SURFACE_ALT, unselected_hover_color=ui.BORDER,
                                     text_color=ui.TEXT, command=self.show_tab)
        self.tabs.grid(row=1, column=0, columnspan=2, sticky="w", padx=2 * SP, pady=(SP, 0))
        self.query = ctk.CTkEntry(head, height=40, font=ui.font(15),
                                  placeholder_text="Type a question or a few words: carrier, situation, rule…")
        self.query.grid(row=2, column=0, columnspan=2, sticky="ew", padx=2 * SP, pady=(SP, SP / 2))
        self.query.bind("<KeyRelease>", self._on_key)
        self.query.bind("<Return>", lambda e: self.search())
        self.query.bind("<Escape>", lambda e: (self.query.delete(0, "end"), self.search()))
        self.notes_label = ctk.CTkLabel(head, text="", font=ui.font(12), text_color=ui.MUTED, anchor="w")
        self.notes_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=2 * SP, pady=(SP / 2, 1.5 * SP))

        # ---------- the three panes: home, results, guide (one shows at a time) ----------
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", pady=(SP, 0))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.home = HomePane(self.content, app)
        self.results = ResultsPane(self.content, app)
        self.guide = GuideView(self.content, app)
        for pane in (self.home, self.results, self.guide):
            pane.grid(row=0, column=0, sticky="nsew")
            pane.grid_remove()
        self.footer = ctk.CTkLabel(self, text="", font=ui.font(12), text_color=ui.MUTED)
        self.footer.grid(row=2, column=0, sticky="w", pady=(SP / 2, 0))
        self.reload()

    # ---------- notes ----------
    def reload(self):
        folder = notes_search.notes_dir(self.app.cfg)
        self.index = notes_search.Index(folder)
        if self.index.notes:
            self.notes_label.configure(text=f"{len(self.index.notes)} notes in {self.ui.shorten_path(folder, 90)}",
                                       text_color=self.ui.MUTED)
        else:
            self.notes_label.configure(text=f"No notes (.md files) in {self.ui.shorten_path(folder, 80)} - choose "
                                            "the Notes folder", text_color=self.ui.DANGER)
        self.guide.stamp = None                       # read the guides again
        self.show_tab(self.tab)

    def guide_note(self, key):
        """The note (file name) of a guide: the one in the notes folder whose name has the key words, else None."""
        return next((n for n in (self.index.notes if self.index else []) if key in n.lower()), None)

    def load(self):
        """Called each time the view is shown."""
        if self.tab == "Search":
            self.query.focus_set()

    def choose_notes(self):
        p = filedialog.askdirectory(parent=self, title="Choose the Underwriting Knowledge folder (.md notes)")
        if p:
            config.update(self.app.cfg, knowledge_dir=p)
            self.reload()

    def open_note(self, name, heading=""):
        """Read a note. A guide opens in its own tab (and at the insurer, when the section is one); any other note
        opens as a page."""
        for label, key, _title, _sub in TABS[1:]:
            if self.guide_note(key) == name:
                self.show_tab(label)
                row = next((i for i, r in enumerate(self.guide.rows) if heading and r[0].lower().startswith(heading.lower()[:6])), None)
                if row is not None:
                    self.guide.open_row(row)
                return
        NotePage(self.app, self.index.folder / name, heading)

    # ---------- the sections ----------
    def show_tab(self, name):
        self.tab = name
        if self.tabs.get() != name:
            self.tabs.set(name)
        label, key, title, _sub = next((t for t in TABS if t[0] == name), TABS[0])
        if key:                                       # a guide
            self.query.grid_remove()
            self.home.grid_remove()
            self.results.grid_remove()
            self.guide.grid()
            note = self.guide_note(key)
            folder = self.index.folder if self.index else notes_search.notes_dir(self.app.cfg)
            self.guide.load(folder / note if note else None, title, folder)
            self.footer.configure(text="A summary of your notes: click an insurer for its sheet. Check the carrier "
                                       "before binding.")
            return
        self.guide.grid_remove()
        self.query.grid()
        self.search()
        self.query.focus_set()

    # ---------- search ----------
    def _on_key(self, event):
        if self._job:
            self._job = self.after_cancel(self._job)
        self._job = self.after(250, self.search)   # search as you type, once typing pauses

    def search_for(self, text):
        self.query.delete(0, "end")
        self.query.insert(0, text)
        self.search()

    def search(self):
        self._job = None
        if self.tab != "Search":
            return
        q = self.query.get().strip()
        if not q:
            self.results.grid_remove()
            self.home.grid()
            self.home.build(self)
            self.footer.configure(text="Searches your notes only (no internet). Notes are a summary - check the carrier "
                                       "manual before quoting exact rates.")
            return
        self.home.grid_remove()
        self.results.grid()
        found = self.index.search(q, limit=6, per_section=5) if self.index else []
        self.results.show(found, self.index.highlight_words(q) if found else [], self)
        self.footer.configure(text="Click a card to read that note.")



class NotePage(Panel):
    """One whole note, read inside the app: sections with short bullets; opens at the section that was clicked."""

    def __init__(self, app, path, heading=""):
        super().__init__(app)
        self.app, self.path = app, Path(path)
        ui = self.ui = sys.modules[type(app).__module__]
        self.geometry("1180x840")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        try:
            sections = notes_search.parse(self.path.name, self.path.read_text(encoding="utf-8-sig"))
        except OSError:
            sections = []
        title = sections[0]["title"] if sections else self.path.stem
        self.title(title)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
        names = [s["heading"] or s["title"] for s in sections if s["items"] or s["heading"]]
        self.jump_var = ctk.StringVar(value=heading or (names[0] if names else ""))
        if names:
            ctk.CTkLabel(top, text="Go to", font=ui.font(13, "bold"), text_color=ui.TEXT).pack(side="left")
            ctk.CTkOptionMenu(top, values=names, variable=self.jump_var, width=420, height=34, font=ui.font(13),
                              fg_color=ui.SURFACE_ALT, button_color=ui.BORDER, button_hover_color=ui.MUTED,
                              text_color=ui.TEXT, dynamic_resizing=False, command=self.jump).pack(side="left", padx=ui.SP)
        app.secondary_button(top, "Open in Notepad", lambda: os.startfile(self.path), width=140).pack(side="right")

        card = app.card(self, row=1, column=0)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)
        self.out = ctk.CTkTextbox(card, font=ui.font(14), wrap="word", fg_color=ui.SURFACE, text_color=ui.TEXT,
                                  border_width=0, cursor="arrow")
        self.out.grid(row=0, column=0, sticky="nsew", padx=ui.SP, pady=ui.SP)
        tb = self.out._textbox
        setup_tags(tb, ui, ctk.ScalingTracker.get_widget_scaling(self))
        tb.insert("end", title + "\n", "h1")
        self.marks = {}
        for i, s in enumerate(sections):
            if not (s["items"] or s["heading"]):
                continue
            name = s["heading"] or s["title"]
            mark = f"sec{i}"
            tb.mark_set(mark, "end-1c")
            tb.mark_gravity(mark, "left")
            self.marks[name] = mark
            if s["heading"]:
                tb.insert("end", "\n", "gap")
                tb.insert("end", s["heading"] + "\n", ("title",))
            for item in s["items"]:
                render_item(tb, item, None)
        self.out.configure(state="disabled")
        self.after(80, lambda: self.jump(heading) if heading else None)

    def jump(self, name):
        mark = self.marks.get(name)
        if mark:
            self.out._textbox.yview(mark)
