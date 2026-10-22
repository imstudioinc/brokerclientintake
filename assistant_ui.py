"""Ask view: chat about underwriting rules, inside the main window (next to Clients and Tracker)."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog

import anthropic
import customtkinter as ctk

import assistant
import config

EXAMPLES = ("e.g. \"Can Intact take a G2 driver with one at-fault accident in 2024?\"  ·  "
            "\"What does Pembridge need for a 30-year-old oil tank?\"  ·  \"Echelon payment plan rules?\"")


class AssistantView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        ui = self.ui = sys.modules[type(app).__module__]
        self.chat = None
        self.busy = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        SP = ui.SP

        # ---------- header ----------
        head = app.card(self, row=0, column=0)
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Ask about underwriting", font=ui.font(16, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, sticky="w", padx=2 * SP, pady=(1.5 * SP, 0))
        self.notes_label = ctk.CTkLabel(head, text="", font=ui.font(12), text_color=ui.MUTED, anchor="w")
        self.notes_label.grid(row=1, column=0, sticky="w", padx=2 * SP, pady=(0, 1.5 * SP))
        btns = ctk.CTkFrame(head, fg_color="transparent")
        btns.grid(row=0, column=1, rowspan=2, sticky="e", padx=2 * SP)
        app.secondary_button(btns, "New chat", self.new_chat, width=96).pack(side="right")
        app.secondary_button(btns, "Notes folder…", self.choose_notes, width=120).pack(side="right", padx=SP)
        app.secondary_button(btns, "API key…", self.show_key_setup, width=90).pack(side="right")

        # ---------- API key setup (only shown when needed) ----------
        self.setup = ctk.CTkFrame(self, fg_color=ui.WARN_BG, corner_radius=10)
        self.setup.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.setup, text="Anthropic API key", font=ui.font(13, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, sticky="w", padx=(2 * SP, SP), pady=SP)
        self.key_entry = ctk.CTkEntry(self.setup, show="•", height=34, font=ui.font(13),
                                      placeholder_text="sk-ant-...  (from console.anthropic.com > API keys)")
        self.key_entry.grid(row=0, column=1, sticky="ew", pady=SP)
        self.key_entry.bind("<Return>", lambda e: self.save_key())
        ctk.CTkButton(self.setup, text="Save", width=80, height=34, font=ui.font(13, "bold"), fg_color=ui.PRIMARY,
                      hover_color=ui.PRIMARY_HOVER, command=self.save_key).grid(row=0, column=2, padx=SP, pady=SP)
        ctk.CTkLabel(self.setup, text="Saved only on this computer (your Windows profile). Questions and any client "
                                      "record you attach are sent to Anthropic to answer them.",
                     font=ui.font(11), text_color=ui.MUTED).grid(row=1, column=0, columnspan=3, sticky="w",
                                                                  padx=2 * SP, pady=(0, SP))

        # ---------- transcript ----------
        body = app.card(self, row=2, column=0, pady=(1.5 * SP, 0))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.log = ctk.CTkTextbox(body, font=ui.font(14), wrap="word", fg_color=ui.SURFACE, text_color=ui.TEXT,
                                  border_width=0, activate_scrollbars=True)
        self.log.grid(row=0, column=0, sticky="nsew", padx=SP, pady=SP)
        tb = self.log._textbox
        # negative sizes are pixels, the same unit CTk fonts use
        tb.tag_configure("you", font=(ui.FONT, -15, "bold"), spacing1=14)
        tb.tag_configure("who", font=(ui.FONT, -12, "bold"), spacing1=14)
        tb.tag_configure("meta", font=(ui.FONT, -12))
        tb.tag_configure("error", font=(ui.FONT, -13, "bold"))
        self._color_tags()

        # ---------- question box ----------
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", pady=(1.5 * SP, 0))
        bottom.grid_columnconfigure(0, weight=1)
        self.client_var = tk.BooleanVar(value=False)
        self.client_check = ctk.CTkCheckBox(bottom, text="", variable=self.client_var, font=ui.font(12),
                                            text_color=ui.TEXT, fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER)
        self.client_check.grid(row=0, column=0, sticky="w", pady=(0, SP))
        self.entry = ctk.CTkTextbox(bottom, height=72, font=ui.font(13), wrap="word", fg_color=ui.SURFACE,
                                    border_width=1, border_color=ui.BORDER, text_color=ui.TEXT)
        self.entry.grid(row=1, column=0, sticky="ew")
        self.entry.bind("<Return>", self._on_enter)
        self.send_btn = ctk.CTkButton(bottom, text="Ask", width=96, height=72, font=ui.font(14, "bold"),
                                      fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER, command=self.send)
        self.send_btn.grid(row=1, column=1, sticky="ns", padx=(SP, 0))
        ctk.CTkLabel(bottom, text="Enter to ask, Shift+Enter for a new line.  Guidance only - confirm anything "
                                  "borderline with the underwriter before binding.",
                     font=ui.font(11), text_color=ui.MUTED).grid(row=2, column=0, columnspan=2, sticky="w",
                                                                 pady=(SP / 2, 0))
        self.load()

    # ---------- state ----------
    def _key(self):
        return self.app.cfg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")

    def load(self):
        """Called each time the view is shown."""
        notes = assistant.load_notes(assistant.notes_dir(self.app.cfg))
        folder = assistant.notes_dir(self.app.cfg)
        if notes:
            self.notes_label.configure(text=f"{len(notes)} notes from {self.ui.shorten_path(folder, 80)}",
                                       text_color=self.ui.MUTED)
        else:
            self.notes_label.configure(text=f"No notes found in {self.ui.shorten_path(folder, 70)} - choose the "
                                            "Notes folder", text_color=self.ui.DANGER)
        if not self._key():
            self.show_key_setup()
        sel = self.app.selected
        if sel:
            self.client_check.configure(text=f"Include client record: {sel.name}", state="normal")
        else:
            self.client_var.set(False)
            self.client_check.configure(text="Include client record (select a client on the Clients tab first)",
                                        state="disabled")
        if not self.log.get("1.0", "end").strip():
            self._write("Ask about eligibility, underwriting rules, endorsements or payments for the carriers "
                        "in your notes.\n" + EXAMPLES + "\n", "meta")
        self.entry.focus_set()

    def _color_tags(self):
        tb, c = self.log._textbox, (lambda pair: pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0])
        tb.tag_configure("who", foreground=c(self.ui.PRIMARY))
        tb.tag_configure("meta", foreground=c(self.ui.MUTED))
        tb.tag_configure("error", foreground=c(self.ui.DANGER))

    def _write(self, text, tag=None):
        self.log.configure(state="normal")
        self.log._textbox.insert("end", text, tag or ())
        self.log.configure(state="disabled")
        self.log.see("end")

    def new_chat(self):
        if self.busy:
            return
        self.chat = None
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.load()

    def choose_notes(self):
        p = filedialog.askdirectory(parent=self, title="Choose the Underwriting Knowledge folder (.md notes)",
                                    initialdir=str(assistant.notes_dir(self.app.cfg)))
        if p:
            config.update(self.app.cfg, knowledge_dir=p)
            self.chat = None   # next question starts with the new notes
            self.load()

    def show_key_setup(self):
        self.setup.grid(row=1, column=0, sticky="ew", pady=(1.5 * self.ui.SP, 0))
        self.key_entry.focus_set()

    def save_key(self):
        key = self.key_entry.get().strip()
        if not key:
            return
        config.update(self.app.cfg, anthropic_api_key=key)
        self.key_entry.delete(0, "end")
        self.setup.grid_forget()
        self.chat = None
        self.entry.focus_set()

    # ---------- asking ----------
    def _on_enter(self, event):
        if event.state & 0x1:   # Shift+Enter: new line
            return None
        self.send()
        return "break"

    def send(self):
        question = self.entry.get("1.0", "end").strip()
        if not question or self.busy:
            return
        if not self._key():
            self.show_key_setup()
            return
        notes = assistant.load_notes(assistant.notes_dir(self.app.cfg))
        if not notes:
            self._write("\nNo notes to answer from - choose the Notes folder first.\n", "error")
            return
        if self.chat is None:
            self.chat = assistant.Chat(self._key(), notes)
        folder = self.app.selected if self.client_var.get() else None
        kind = self.app.client_type_of.get(folder, "") if folder else ""
        self.entry.delete("1.0", "end")
        self._write(f"\n{question}\n", "you")
        if folder:
            self._write(f"with {folder.name}'s record\n", "meta")
        self._write("\nAnswer\n", "who")
        self._set_busy(True)
        threading.Thread(target=self._ask, args=(question, folder, kind), daemon=True).start()

    def _ask(self, question, folder, kind):
        ui = self.app.ui   # widgets only change on the window's thread
        try:
            context = assistant.client_context(folder, kind) if folder else None
            final = self.chat.ask(question, lambda t: ui(self._write, t), context)
            if final.stop_reason == "refusal":
                ui(self._write, "\n[Not answered - try rewording the question.]\n", "error")
            elif final.stop_reason == "max_tokens":
                ui(self._write, "\n[Answer cut off - ask it to continue.]\n", "meta")
        except anthropic.AuthenticationError:
            ui(self._write, "\nThe API key was not accepted. Enter it again (API key…).\n", "error")
            ui(self.show_key_setup)
        except anthropic.PermissionDeniedError:
            ui(self._write, "\nThis API key is not allowed to use the model. Check it in console.anthropic.com.\n",
               "error")
        except anthropic.RateLimitError:
            ui(self._write, "\nToo many requests right now - wait a minute and ask again.\n", "error")
        except anthropic.APIConnectionError:
            ui(self._write, "\nCan't reach api.anthropic.com. Check the internet connection - a work network may "
                            "block it.\n", "error")
        except anthropic.APIStatusError as e:
            ui(self._write, f"\nThe service returned an error ({e.status_code}). Try again shortly.\n", "error")
        except Exception as e:
            ui(self._write, f"\nSomething went wrong: {e}\n", "error")
        finally:
            ui(self._set_busy, False)

    def _set_busy(self, busy):
        self.busy = busy
        self.send_btn.configure(state="disabled" if busy else "normal", text="…" if busy else "Ask")
