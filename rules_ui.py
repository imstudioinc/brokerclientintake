"""Rules view: search the underwriting notes, inside the main window (next to Clients and Tracker).

Results are read in the app: long run-on lines of the notes are split into a lead and short bullets
(notes_search.split_item), and a click on a result opens the whole note in a page of its own (NotePage),
not in Notepad.
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

# The sections of the Rules view: Search, and one tab for each guide. A guide is a note of the notes folder with one "##"
# section per insurer (or topic); (tab text, word in the note's file name, what to call it when it is missing).
TABS = [("Search", "", ""), ("Ride sharing", "ride sharing", "Ride sharing and car sharing - by insurer"),
        ("Billing by company", "billing", "Billing and payment policy - by insurer")]
TAB_ON = ("#FFFFFF", "#44566B")          # the open tab: clearly lighter than the others
SELECTED = ("#E8F0FE", "#1F2D45")       # the open insurer in a guide's list

BAND = ("#EEF2F7", "#26303C")          # the bar behind a result's title
HIT_BG = ("#FFF1B8", "#5A4A12")         # a word that matches the question


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


class RulesView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        ui = self.ui = sys.modules[type(app).__module__]
        self.index = None
        self._job = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        SP = ui.SP

        # ---------- header: search box ----------
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
        # the sections of the Rules view: Search, and a tab for each guide (ride sharing, billing by company)
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

        # ---------- search results ----------
        body = self.results_card = app.card(self, row=1, column=0, pady=(1.5 * SP, 0))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.out = ctk.CTkTextbox(body, font=ui.font(14), wrap="word", fg_color=ui.SURFACE, text_color=ui.TEXT,
                                  border_width=0, cursor="arrow")
        self.out.grid(row=0, column=0, sticky="nsew", padx=SP, pady=SP)
        self.scale = ctk.ScalingTracker.get_widget_scaling(self)
        setup_tags(self.out._textbox, ui, self.scale)
        self.out.bind("<Configure>", lambda e: fit_width(self.out._textbox, e.width, self.scale), add="+")
        # ---------- a guide: the list of insurers on the left, the open one on the right ----------
        self.guide_card = app.card(self, row=1, column=0, pady=(1.5 * SP, 0))
        self.guide_card.grid_columnconfigure(0, weight=1)
        self.guide_card.grid_rowconfigure(0, weight=1)
        self.guide = GuidePane(self.guide_card, app)
        self.guide.grid(row=0, column=0, sticky="nsew")
        self.guide_card.grid_remove()
        self.footer = ctk.CTkLabel(self, text="", font=ui.font(12), text_color=ui.MUTED)
        self.footer.grid(row=2, column=0, sticky="w", pady=(SP / 2, 0))
        self.tab = "Search"
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
        self.show_tab(self.tab)
        self.search()

    def _guide_note(self, key):
        """The note (file name) of a guide: the one in the notes folder whose name has the key words, else None."""
        return next((n for n in (self.index.notes if self.index else []) if key in n.lower()), None)

    def show_tab(self, name):
        """Switch the section of the Rules view: Search, or a guide (a list of insurers and what the open one says)."""
        self.tab = name
        if self.tabs.get() != name:
            self.tabs.set(name)
        label, key, title = next((t for t in TABS if t[0] == name), TABS[0])
        if not key:                                   # Search
            self.guide_card.grid_remove()
            self.results_card.grid()
            self.query.grid()
            self.footer.configure(text="Searches your notes only (no internet). Click a result's title to read that "
                                       "note. Notes are a summary - check the carrier manual before quoting exact rates.")
            self.query.focus_set()
            return
        self.results_card.grid_remove()
        self.query.grid_remove()
        self.guide_card.grid()
        note = self._guide_note(key)
        folder = self.index.folder if self.index else notes_search.notes_dir(self.app.cfg)
        self.guide.load(folder / note if note else None, title, folder)
        self.footer.configure(text="One section per insurer: pick one on the left. A summary of your notes - check the "
                                   "carrier before binding.")

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
        NotePage(self.app, self.index.folder / name, heading)

    # ---------- search ----------
    def _on_key(self, event):
        if self._job:
            self._job = self.after_cancel(self._job)
        self._job = self.after(250, self.search)   # search as you type, once typing pauses

    def _link(self, tb, tag, command):
        tb.tag_bind(tag, "<Button-1>", lambda e: command())
        tb.tag_bind(tag, "<Enter>", lambda e: tb.configure(cursor="hand2"))
        tb.tag_bind(tag, "<Leave>", lambda e: tb.configure(cursor="arrow"))

    def search(self):
        self._job = None
        q = self.query.get().strip()
        tb = self.out._textbox
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        for tag in tb.tag_names():
            if tag.startswith("link"):
                tb.tag_delete(tag)
        recolor(tb, self.ui)
        if not q:
            self._show_start()
        else:
            results = self.index.search(q, limit=6, per_section=5) if self.index else []
            if not results:
                tb.insert("end", "Nothing found. Try fewer or different words (a carrier name plus one or two "
                                 "key words works best).\n", "meta")
            words = self.index.highlight_words(q) if results else []
            pattern = re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\w*", re.I) if words else None
            for i, r in enumerate(results):
                link = f"link{i}"
                # the title bar: the section, and under it which note it comes from
                tb.insert("end", "\n", "gap")
                tb.insert("end", (r["heading"] or r["title"]) + "\n", ("title", link))
                tb.insert("end", r["title"] + "\n", ("source", link))
                self._link(tb, link, lambda r=r: self.open_note(r["note"], r["heading"]))
                for item in r["items"]:
                    render_item(tb, item, pattern, focus=True)
                if r["more"] > 0:
                    more = f"link_more{i}"
                    tb.insert("end", f"Read the whole section  (+ {r['more']} more)  →\n", ("more", more))
                    self._link(tb, more, lambda r=r: self.open_note(r["note"], r["heading"]))
        self.out.configure(state="disabled")
        self.out.yview_moveto(0)

    def _show_start(self):
        tb = self.out._textbox
        tb.insert("end", "Type above to search the underwriting notes - results show as you type.\n\n", "meta")
        tb.insert("end", "Guides: ", "meta")
        for i, (label, key, _) in enumerate(TABS[1:]):
            tag = f"link_g{i}"
            tb.insert("end", label, ("more", tag))
            self._link(tb, tag, lambda n=label: self.show_tab(n))
            tb.insert("end", "     ", "meta")
        tb.insert("end", chr(10) * 2, "meta")
        tb.insert("end", "Try: ", "meta")
        for i, ex in enumerate(EXAMPLES):
            tag = f"link_ex{i}"
            tb.insert("end", ex, ("more", tag))
            self._link(tb, tag, lambda ex=ex: (self.query.delete(0, "end"), self.query.insert(0, ex), self.search()))
            tb.insert("end", "     ", "meta")
        if self.index and self.index.notes:
            tb.insert("end", "\n", "meta")
            tb.insert("end", "\n", "gap")
            tb.insert("end", "All notes (click to read)\n", "title")
            for i, name in enumerate(self.index.notes):
                tag = f"link_n{i}"
                tb.insert("end", "•  " + Path(name).stem + "\n", ("bullet", tag))
                self._link(tb, tag, lambda n=name: self.open_note(n))


VERDICT_LOOK = {   # first word of "Verdict:" -> (pill tag, list mark, list heading)
    "accepted": ("pill_ok", "✓", "Accepted"), "declined": ("pill_no", "✕", "Declined")}
ASK_LOOK = ("pill_ask", "?", "Ask the underwriter")


def verdict_look(verdict):
    return VERDICT_LOOK.get((verdict or "").split(" ")[0].lower(), ASK_LOOK)


class GuidePane(ctk.CTkFrame):
    """One guide inside the Rules view. The insurers (the note's "##" sections) are a list on the left, grouped by
    verdict when the note gives one; the open one is a short fact sheet on the right: a verdict pill and "Label  value"
    rows (a note line written as "Label: value"), not paragraphs. "At a glance" sections list who is in each group, with
    the names as links. Says what to copy where when the note is missing."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        ui = self.ui = sys.modules[type(app).__module__]
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.list = ctk.CTkScrollableFrame(self, width=250, fg_color=ui.SURFACE_ALT, corner_radius=10)
        self.list.grid(row=0, column=0, sticky="ns", padx=(ui.SP, 0), pady=ui.SP)
        self.text = ctk.CTkTextbox(self, font=ui.font(14), wrap="word", fg_color=ui.SURFACE, text_color=ui.TEXT,
                                   border_width=0, cursor="arrow")
        self.text.grid(row=0, column=1, sticky="nsew", padx=ui.SP, pady=ui.SP)
        self.scale = ctk.ScalingTracker.get_widget_scaling(self)
        setup_tags(self.text._textbox, ui, self.scale)
        self.text.bind("<Configure>", lambda e: fit_width(self.text._textbox, e.width, self.scale), add="+")
        self.sections, self.widgets, self.buttons, self.stamp = [], [], {}, None

    def load(self, path, title, folder):
        """Show the guide in `path` (None = it is not in the notes folder: say what to do)."""
        try:
            stamp = (str(path), path.stat().st_mtime) if path else None
        except OSError:
            stamp = None
        if stamp and stamp == self.stamp:
            return
        self.stamp = stamp
        for w in self.widgets:
            w.destroy()
        self.widgets, self.buttons, self.sections = [], {}, []
        tb = self.text._textbox
        recolor(tb, self.ui)
        if not stamp:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            tb.insert("end", "This guide is not in your notes folder yet\n", "h1")
            tb.insert("end", f"Copy the note called \"{title}\" (a .md file) into this folder, then press Reload notes:\n\n",
                      "meta")
            tb.insert("end", f"{folder}\n", "lead")
            self.text.configure(state="disabled")
            return
        try:
            sections = notes_search.parse(path.name, path.read_text(encoding="utf-8-sig"))
        except OSError:
            sections = []
        self.sections = [s for s in sections if s["heading"] and s["items"]]
        for s in self.sections:
            first = s["items"][0]
            s["verdict"] = first.split(":", 1)[1].strip() if first.lower().startswith("verdict:") else ""
            s["facts"] = [i for i in s["items"] if not i.lower().startswith("verdict:")]
        self._build_list()
        if self.sections:
            self.select(0)

    def _build_list(self):
        """The insurers on the left: grouped by verdict (Accepted / Ask / Declined) when the note gives verdicts."""
        ui = self.ui
        grouped = any(s["verdict"] for s in self.sections)

        def add_group(name):
            lab = ctk.CTkLabel(self.list, text=name.upper(), font=ui.font(12, "bold"), text_color=ui.MUTED, anchor="w")
            lab.pack(fill="x", padx=8, pady=(10, 2))
            self.widgets.append(lab)

        def add_button(i, s):
            mark = verdict_look(s["verdict"])[1] + "  " if s["verdict"] else ""
            b = ctk.CTkButton(self.list, text=mark + ui.shorten(s["heading"], 28), anchor="w", height=34, corner_radius=8,
                              font=ui.font(14), fg_color="transparent", text_color=ui.TEXT, hover_color=ui.BORDER,
                              command=lambda i=i: self.select(i))
            b.pack(fill="x", pady=1)
            self.widgets.append(b)
            self.buttons[i] = b

        order = list(range(len(self.sections)))
        if not grouped:
            for i in order:
                add_button(i, self.sections[i])
            return
        for i in order:                                     # "at a glance" and other sections without a verdict first
            if not self.sections[i]["verdict"]:
                add_button(i, self.sections[i])
        for heading in ("Accepted", "Ask the underwriter", "Declined"):
            members = [i for i in order if self.sections[i]["verdict"] and verdict_look(self.sections[i]["verdict"])[2] == heading]
            if members:
                add_group(heading)
                for i in members:
                    add_button(i, self.sections[i])

    def _jump_to(self, name):
        """The section an insurer's name in an "at a glance" row stands for."""
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        for i, s in enumerate(self.sections):
            head = re.sub(r"[^a-z0-9]", "", s["heading"].lower())
            if head.startswith(key) or key.startswith(head[:5]) and len(key) >= 4 and head[:5] == key[:5]:
                return i
        # an insurer with no section of its own is in the "Not in the notes" section
        return next((i for i, s in enumerate(self.sections) if s["heading"].lower().startswith("not in the")), None)

    def select(self, i):
        for k, b in self.buttons.items():
            b.configure(fg_color=SELECTED if k == i else "transparent")
        s = self.sections[i]
        tb = self.text._textbox
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for tag in tb.tag_names():
            if tag.startswith("gl"):
                tb.tag_delete(tag)
        recolor(tb, self.ui)
        tb.insert("end", s["heading"], "h1")
        if s["verdict"]:
            tb.insert("end", "     ", "h1")
            tb.insert("end", f"  {s['verdict'].upper()}  ", verdict_look(s["verdict"])[0])
        tb.insert("end", "\n", "h1")
        glance = "glance" in s["heading"].lower()
        for k, item in enumerate(s["facts"]):
            m = re.match(r"^([^:;]{2,22}):\s+(.+)$", item, re.S)     # a longer label would run into its value: a bullet
            if not m:
                insert_marked(tb, "•  " + item + "\n", "bullet", None)
                continue
            label, value = m.group(1), m.group(2)
            value = value[:1].upper() + value[1:]
            look = verdict_look(label)[0] if glance and label.split(" ")[0].lower() in ("accepted", "declined", "ask", "fleet") else None
            tb.insert("end", label, ("kv", "kvlabel" if not look else "kvlabel_" + look[5:]))
            tb.insert("end", "\t", "kv")
            if glance and ";" in value and look:
                for n, name in enumerate(x.strip() for x in value.split(";")):
                    target = self._jump_to(name)
                    tags = ("kv", "kvvalue")
                    if target is not None:
                        tag = f"gl{k}_{n}"
                        tags = ("kv", "kvlink", tag)
                        tb.tag_bind(tag, "<Button-1>", lambda e, t=target: self.select(t))
                        tb.tag_bind(tag, "<Enter>", lambda e: tb.configure(cursor="hand2"))
                        tb.tag_bind(tag, "<Leave>", lambda e: tb.configure(cursor="arrow"))
                    tb.insert("end", name, tags)
                    if n < value.count(";"):
                        tb.insert("end", "   ·   ", ("kv", "kvvalue"))
                tb.insert("end", "\n", "kv")
            else:
                tb.insert("end", value + "\n", ("kv", "kvvalue"))
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)


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
