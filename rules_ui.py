"""Rules view: search the underwriting notes, inside the main window (next to Clients and Tracker).

Results are read in the app: long run-on lines of the notes are split into a lead and short bullets
(notes_search.split_item), and a click on a result opens the whole note in a page of its own (NotePage),
not in Notepad.
"""
import os
import re
import sys
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import carriers_ui
import config
import notes_search
from panel import Panel

EXAMPLES = ["intact G2 at-fault", "pembridge oil tank", "echelon monthly payment", "motorcycle M1 course",
            "jevco minor accident", "OPCF 43", "winter tire discount", "nsf fee", "uber turo"]

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
    tb.tag_configure("h1", font=(ui.FONT, px(22), "bold"), spacing3=int(6 * scale))
    recolor(tb, ui)


def recolor(tb, ui):
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


def render_item(tb, item, pattern):
    """One note line as a lead + short bullets (or a single bullet)."""
    lead, parts = notes_search.split_item(item)
    if lead:
        insert_marked(tb, lead + "\n", "lead", pattern)
        for part in parts:
            insert_marked(tb, "•  " + part + "\n", "sub", pattern)
    else:
        insert_marked(tb, "•  " + parts[0] + "\n", "bullet", pattern)
        for part in parts[1:]:
            insert_marked(tb, "–  " + part + "\n", "sub", pattern)


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
        ctk.CTkLabel(head, text="Search the rules", font=ui.font(16, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, sticky="w", padx=2 * SP, pady=(1.5 * SP, 0))
        btns = ctk.CTkFrame(head, fg_color="transparent")
        btns.grid(row=0, column=1, sticky="e", padx=2 * SP, pady=(1.5 * SP, 0))
        app.secondary_button(btns, "Notes folder…", self.choose_notes, width=120).pack(side="right")
        app.secondary_button(btns, "Reload notes", self.reload, width=110).pack(side="right", padx=SP)
        app.secondary_button(btns, "Carriers & payments", lambda: carriers_ui.CarrierInfoPage(app), width=160) \
            .pack(side="right")
        self.query = ctk.CTkEntry(head, height=40, font=ui.font(15),
                                  placeholder_text="Type a question or a few words: carrier, situation, rule…")
        self.query.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2 * SP, pady=(SP, SP / 2))
        self.query.bind("<KeyRelease>", self._on_key)
        self.query.bind("<Return>", lambda e: self.search())
        self.query.bind("<Escape>", lambda e: (self.query.delete(0, "end"), self.search()))
        self.notes_label = ctk.CTkLabel(head, text="", font=ui.font(12), text_color=ui.MUTED, anchor="w")
        self.notes_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=2 * SP, pady=(0, 1.5 * SP))

        # ---------- results ----------
        body = app.card(self, row=1, column=0, pady=(1.5 * SP, 0))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.out = ctk.CTkTextbox(body, font=ui.font(14), wrap="word", fg_color=ui.SURFACE, text_color=ui.TEXT,
                                  border_width=0, cursor="arrow")
        self.out.grid(row=0, column=0, sticky="nsew", padx=SP, pady=SP)
        self.scale = ctk.ScalingTracker.get_widget_scaling(self)
        setup_tags(self.out._textbox, ui, self.scale)
        ctk.CTkLabel(self, text="Searches your notes only (no internet). Click a result's title to read that "
                                "note. Notes are a summary - check the carrier manual before quoting exact rates.",
                     font=ui.font(12), text_color=ui.MUTED).grid(row=2, column=0, sticky="w", pady=(SP / 2, 0))
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
        self.search()

    def load(self):
        """Called each time the view is shown."""
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
            results = self.index.search(q) if self.index else []
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
                    render_item(tb, item, pattern)
                if r["more"] > 0:
                    more = f"link_more{i}"
                    tb.insert("end", f"Read the whole section  (+ {r['more']} more)  →\n", ("more", more))
                    self._link(tb, more, lambda r=r: self.open_note(r["note"], r["heading"]))
        self.out.configure(state="disabled")
        self.out.yview_moveto(0)

    def _show_start(self):
        tb = self.out._textbox
        tb.insert("end", "Type above to search the underwriting notes - results show as you type.\n\n", "meta")
        tb.insert("end", "Try: ", "meta")
        for i, ex in enumerate(EXAMPLES):
            tag = f"link_ex{i}"
            tb.insert("end", ex, ("more", tag))
            self._link(tb, tag, lambda ex=ex: (self.query.delete(0, "end"), self.query.insert(0, ex), self.search()))
            tb.insert("end", "     ", "meta")
        if self.index and self.index.notes:
            tb.insert("end", "\n\nAll notes (click to read)\n", "title")
            for i, name in enumerate(self.index.notes):
                tag = f"link_n{i}"
                tb.insert("end", "•  " + Path(name).stem + "\n", ("bullet", tag))
                self._link(tb, tag, lambda n=name: self.open_note(n))


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
