"""Rules view: search the underwriting notes, inside the main window (next to Clients and Tracker)."""
import os
import re
import sys
from tkinter import filedialog

import customtkinter as ctk

import carriers_ui
import config
import notes_search

EXAMPLES = ["intact G2 at-fault", "pembridge oil tank", "echelon monthly payment", "motorcycle M1 course",
            "jevco minor accident", "OPCF 43", "winter tire discount", "nsf fee"]


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
        tb = self.out._textbox
        # negative sizes are pixels, the same unit CTk fonts use
        tb.tag_configure("title", font=(ui.FONT, -15, "bold"), spacing1=16, spacing3=2)
        tb.tag_configure("note", font=(ui.FONT, -12), spacing3=4)
        tb.tag_configure("item", lmargin1=12, lmargin2=26, spacing1=3)
        tb.tag_configure("hit", font=(ui.FONT, -14, "bold"))
        tb.tag_configure("meta", font=(ui.FONT, -12))
        ctk.CTkLabel(self, text="Searches your notes only (no internet). Click a result's title to open that "
                                "note. Notes are a summary - check the carrier manual before quoting exact rates.",
                     font=ui.font(11), text_color=ui.MUTED).grid(row=2, column=0, sticky="w", pady=(SP / 2, 0))
        self.reload()

    # ---------- notes ----------
    def reload(self):
        folder = notes_search.Path(self.app.cfg.get("knowledge_dir") or notes_search.DEFAULT_NOTES)
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

    # ---------- search ----------
    def _on_key(self, event):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(250, self.search)   # search as you type, once typing pauses

    def _colors(self):
        c = (lambda pair: pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0])
        tb = self.out._textbox
        tb.tag_configure("title", foreground=c(self.ui.TEXT))
        tb.tag_configure("note", foreground=c(self.ui.MUTED))
        tb.tag_configure("meta", foreground=c(self.ui.MUTED))
        tb.tag_configure("hit", foreground=c(self.ui.PRIMARY))

    def search(self):
        self._job = None
        q = self.query.get().strip()
        tb = self.out._textbox
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        for tag in tb.tag_names():
            if tag.startswith("link"):
                tb.tag_delete(tag)
        self._colors()
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
                tb.insert("end", (r["heading"] or r["title"]) + "\n", ("title", link))
                tb.insert("end", r["title"] + "\n", ("note", link))
                path = self.index.folder / r["note"]
                tb.tag_bind(link, "<Button-1>", lambda e, p=path: os.startfile(p))
                tb.tag_bind(link, "<Enter>", lambda e: tb.configure(cursor="hand2"))
                tb.tag_bind(link, "<Leave>", lambda e: tb.configure(cursor="arrow"))
                for item in r["items"]:
                    self._insert_marked("• " + item + "\n", pattern)
                if r["more"] > 0:
                    tb.insert("end", f"   + {r['more']} more in this section (click the title)\n", ("meta", "item"))
        self.out.configure(state="disabled")
        self.out.yview_moveto(0)

    def _insert_marked(self, text, pattern):
        tb, pos = self.out._textbox, 0
        for m in pattern.finditer(text) if pattern else ():
            tb.insert("end", text[pos:m.start()], "item")
            tb.insert("end", m.group(0), ("item", "hit"))
            pos = m.end()
        tb.insert("end", text[pos:], "item")

    def _show_start(self):
        tb = self.out._textbox
        tb.insert("end", "Type above to search the underwriting notes - results show as you type.\n\n", "meta")
        tb.insert("end", "Try: ", "meta")
        for i, ex in enumerate(EXAMPLES):
            tag = f"link_ex{i}"
            tb.insert("end", ex, ("hit", tag))
            tb.tag_bind(tag, "<Button-1>", lambda e, ex=ex: (self.query.delete(0, "end"),
                                                              self.query.insert(0, ex), self.search()))
            tb.insert("end", "   ")
        if self.index and self.index.notes:
            tb.insert("end", "\n\nNotes searched:\n", "title")
            for i, name in enumerate(self.index.notes):
                tag = f"link_n{i}"
                tb.insert("end", "• " + notes_search.Path(name).stem + "\n", ("item", tag))
                tb.tag_bind(tag, "<Button-1>", lambda e, p=self.index.folder / name: os.startfile(p))
