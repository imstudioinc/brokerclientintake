"""Client Intake - desktop app for new client setup.

Creates the client folder, fills the consent form, and shows which
documents (Consent, DASH, Quote, MVR) each client folder already has.
"""
import datetime
import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import config
from fill_consent import fill, format_dln, is_valid_dln, read_dash
import mvr_email

# ---------- Design tokens (light, dark) ----------
BG = ("#F3F5F8", "#0F1419")
SURFACE = ("#FFFFFF", "#1A2027")
SURFACE_ALT = ("#F8FAFC", "#202832")
BORDER = ("#E2E6EB", "#2C3540")
TEXT = ("#111827", "#E6EAF0")
MUTED = ("#5B6472", "#9AA4B2")
PRIMARY = ("#C8102E", "#D42A44")
PRIMARY_HOVER = ("#A50D26", "#B5213A")
SELECTED = ("#FDECEF", "#3A1F26")
SUCCESS = ("#15803D", "#4ADE80")
SUCCESS_BG = ("#E8F5EC", "#16291D")
DANGER = ("#B91C1C", "#F87171")
WARN_BG = ("#F1F3F6", "#252D37")

FONT = "Segoe UI"
DLN_HELP = "Ontario licence #. Copied to your clipboard for DASH."
SP = 8  # spacing unit

# Documents tracked per client: (label, glob patterns)
DOCUMENTS = [
    ("Client consent", ["Client Consent*.pdf"]),
    ("DASH report", ["DASH Report*.pdf"]),
    ("Quote (ARS)", ["*Quote*.pdf", "*quote*.pdf"]),
    ("MVR", ["*MVR*.pdf", "*mvr*.pdf"]),
]


def clean_name(name):
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(".")
    return name.upper()


def find_docs(folder):
    """Return {label: [files]} for the tracked documents in a client folder."""
    found = {}
    for label, patterns in DOCUMENTS:
        files = {p for pat in patterns for p in folder.glob(pat)}
        found[label] = sorted(files, key=lambda p: p.stat().st_mtime)
    return found


def shorten(text, n):
    return text if len(text) <= n else text[: n - 1] + "…"


def shorten_path(path, n=70):
    path = str(path)
    return path if len(path) <= n else path[:20] + "…" + path[-(n - 21):]


def font(size=14, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Settings")
        self.geometry("560x520")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.transient(app)
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=12, border_width=1, border_color=BORDER)
        body.pack(fill="both", expand=True, padx=2 * SP, pady=2 * SP)
        body.grid_columnconfigure(0, weight=1)

        self.root_var = tk.StringVar(value=app.cfg["clients_root"])
        self.tpl_var = tk.StringVar(value=app.cfg["consent_template"])
        self.mode_var = tk.StringVar(value=app.cfg["appearance"])
        self.to_var = tk.StringVar(value=app.cfg["mvr_to"])
        self.cc_var = tk.StringVar(value=app.cfg["mvr_cc"])

        self._path_row(body, 0, "Clients folder", self.root_var, folder=True)
        self._path_row(body, 2, "Consent form template", self.tpl_var, folder=False)

        ctk.CTkLabel(body, text="Appearance", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=4, column=0, sticky="w", padx=2 * SP, pady=(2 * SP, SP / 2))
        ctk.CTkSegmentedButton(body, values=["System", "Light", "Dark"], variable=self.mode_var,
                               font=font(13), selected_color=PRIMARY, selected_hover_color=PRIMARY_HOVER) \
            .grid(row=5, column=0, sticky="w", padx=2 * SP)

        self._text_row(body, 6, "MVR request: To", self.to_var, "branch manager's email")
        self._text_row(body, 8, "MVR request: CC", self.cc_var, "optional; separate several with ;")

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=10, column=0, sticky="e", padx=2 * SP, pady=2 * SP)
        ctk.CTkButton(btns, text="Cancel", width=96, height=36, font=font(13), fg_color="transparent",
                      border_width=1, border_color=BORDER, text_color=TEXT, hover_color=SURFACE_ALT,
                      command=self.destroy).pack(side="left", padx=(0, SP))
        ctk.CTkButton(btns, text="Save", width=96, height=36, font=font(13, "bold"),
                      fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=self.save).pack(side="left")
        self.bind("<Escape>", lambda e: self.destroy())

    def _text_row(self, parent, row, label, var, hint):
        ctk.CTkLabel(parent, text=label, font=font(13, "bold"), text_color=TEXT) \
            .grid(row=row, column=0, sticky="w", padx=2 * SP, pady=(2 * SP, SP / 2))
        ctk.CTkLabel(parent, text=hint, font=font(12), text_color=MUTED) \
            .grid(row=row, column=0, sticky="e", padx=2 * SP, pady=(2 * SP, SP / 2))
        ctk.CTkEntry(parent, textvariable=var, height=36, font=font(13), border_color=BORDER) \
            .grid(row=row + 1, column=0, sticky="ew", padx=2 * SP)

    def _path_row(self, parent, row, label, var, folder):
        ctk.CTkLabel(parent, text=label, font=font(13, "bold"), text_color=TEXT) \
            .grid(row=row, column=0, sticky="w", padx=2 * SP, pady=(2 * SP, SP / 2))
        line = ctk.CTkFrame(parent, fg_color="transparent")
        line.grid(row=row + 1, column=0, sticky="ew", padx=2 * SP)
        line.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(line, textvariable=var, height=36, font=font(13), border_color=BORDER) \
            .grid(row=0, column=0, sticky="ew", padx=(0, SP))

        def browse():
            if folder:
                p = filedialog.askdirectory(parent=self, title=label, initialdir=var.get() or None)
            else:
                p = filedialog.askopenfilename(parent=self, title=label, filetypes=[("PDF", "*.pdf")])
            if p:
                var.set(str(Path(p)))

        ctk.CTkButton(line, text="Browse", width=88, height=36, font=font(13), fg_color="transparent",
                      border_width=1, border_color=BORDER, text_color=TEXT, hover_color=SURFACE_ALT,
                      command=browse).grid(row=0, column=1)

    def save(self):
        self.app.cfg.update(clients_root=self.root_var.get().strip(),
                            consent_template=self.tpl_var.get().strip(),
                            appearance=self.mode_var.get(),
                            mvr_to=self.to_var.get().strip(),
                            mvr_cc=self.cc_var.get().strip())
        config.save(self.app.cfg)
        ctk.set_appearance_mode(self.app.cfg["appearance"])
        self.app.on_settings_changed()
        self.destroy()


class MvrDialog(ctk.CTkToplevel):
    """Collects the MVR request details and opens a Classic Outlook draft."""

    ATTACHABLE = ["DASH report", "Client consent", "Quote (ARS)"]

    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, folder
        self.title(f"Request MVR - {folder.name.upper()}")
        self.geometry("520x720")
        self.resizable(False, True)
        self.configure(fg_color=BG)
        self.transient(app)
        self.grab_set()

        info = mvr_email.load_client(folder)
        docs = find_docs(folder)
        dash = docs["DASH report"]
        dash_driver = read_dash(dash[0]) if dash else None
        name = (info.get("name") or (dash_driver[0] if dash_driver else folder.name)).upper()
        first, last = mvr_email.split_name(name)
        dln = info.get("dln") or (dash_driver[1] if dash_driver else "")

        body = ctk.CTkScrollableFrame(self, fg_color=SURFACE, corner_radius=12,
                                      border_width=1, border_color=BORDER)
        body.pack(fill="both", expand=True, padx=2 * SP, pady=(2 * SP, 0))
        body.grid_columnconfigure((0, 1), weight=1, uniform="c")
        p = 2 * SP

        ctk.CTkLabel(body, text="Client details", font=font(15, "bold"), text_color=TEXT) \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=p, pady=(p, 0))
        self.first = self._field(body, 1, 0, "First name *", first)
        self.last = self._field(body, 1, 1, "Last name *", last)
        self.dln = self._field(body, 3, 0, "Licence # *", dln, span=2)
        self.phone = self._field(body, 5, 0, "Phone", info.get("phone", ""), placeholder="647-555-0123")
        self.email = self._field(body, 5, 1, "Email", info.get("email", ""), placeholder="client@email.com",
                                 upper=False)

        self.error = ctk.CTkLabel(body, text="", font=font(12), text_color=DANGER, justify="left")
        self.error.grid(row=7, column=0, columnspan=2, sticky="w", padx=p)

        ctk.CTkLabel(body, text="Attach", font=font(15, "bold"), text_color=TEXT) \
            .grid(row=8, column=0, columnspan=2, sticky="w", padx=p, pady=(SP, SP / 2))
        self.attach = []
        self.attach_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.attach_frame.grid(row=9, column=0, columnspan=2, sticky="ew", padx=p)
        for label in self.ATTACHABLE:
            for f in docs[label]:
                self._add_attachment(f)
        self.no_files = None
        if not self.attach:
            self.no_files = ctk.CTkLabel(self.attach_frame, font=font(12), text_color=MUTED,
                                         text="No DASH, consent or Quote Information files in this folder yet.")
            self.no_files.pack(anchor="w")
        app.secondary_button(body, "Add file…", self.browse_file, width=100) \
            .grid(row=10, column=0, sticky="w", padx=p, pady=(SP, 0))
        r = 11

        to, cc = app.cfg.get("mvr_to", ""), app.cfg.get("mvr_cc", "")
        if to:
            rcpt = f"To: {to}" + (f"\nCC: {cc}" if cc else "")
        else:
            rcpt = "No recipient set. Add the branch manager's email in Settings."
        ctk.CTkLabel(body, text=rcpt, font=font(12), text_color=MUTED if to else DANGER,
                     justify="left").grid(row=r, column=0, columnspan=2, sticky="w", padx=p, pady=p)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=2 * SP, pady=2 * SP)
        self.go = ctk.CTkButton(btns, text="Create Outlook draft", height=40, font=font(14, "bold"),
                                fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=self.submit)
        self.go.pack(side="right")
        app.secondary_button(btns, "Cancel", self.destroy, width=96).pack(side="right", padx=(0, SP))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.submit())

    def _add_attachment(self, path):
        if any(f == path for _, f in self.attach):
            return
        var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.attach_frame, text=shorten(Path(path).name, 52), variable=var, font=font(13),
                        text_color=TEXT, fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                        border_color=MUTED).pack(anchor="w", pady=SP / 2)
        self.attach.append((var, Path(path)))

    def browse_file(self):
        paths = filedialog.askopenfilenames(parent=self, title="Attach files", initialdir=self.folder)
        if paths and self.no_files:
            self.no_files.destroy()
            self.no_files = None
        for p in paths:
            self._add_attachment(Path(p))

    def _field(self, parent, row, col, label, value, span=1, placeholder="", upper=True):
        if span == 2:
            padx = 2 * SP
        else:
            padx = (2 * SP, SP) if col == 0 else (SP, 2 * SP)
        ctk.CTkLabel(parent, text=label, font=font(13, "bold"), text_color=TEXT) \
            .grid(row=row, column=col, columnspan=span, sticky="w", padx=padx, pady=(1.5 * SP, SP / 2))
        e = ctk.CTkEntry(parent, height=38, font=font(14), border_color=BORDER, placeholder_text=placeholder)
        e.grid(row=row + 1, column=col, columnspan=span, sticky="ew", padx=padx)
        if value:
            e.insert(0, value)
        if upper:
            e.bind("<KeyRelease>", lambda ev: self._upper(e))
        return e

    @staticmethod
    def _upper(e):
        t = e.get()
        if t != t.upper():
            pos = e._entry.index("insert")
            e.delete(0, "end")
            e.insert(0, t.upper())
            e._entry.icursor(pos)

    def values(self):
        return dict(first=self.first.get().strip().upper(), last=self.last.get().strip().upper(),
                    dln=format_dln(self.dln.get()), phone=mvr_email.format_phone(self.phone.get()),
                    email=self.email.get().strip().lower())

    def submit(self, display=True):
        v = self.values()
        problems = []
        if not v["first"] or not v["last"]:
            problems.append("Enter first and last name.")
        if not is_valid_dln(v["dln"]):
            problems.append("Licence # must be 1 letter + 14 digits.")
        if v["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v["email"]):
            problems.append("Email address doesn't look right.")
        if not self.app.cfg.get("mvr_to"):
            problems.append("Set the branch manager's email in Settings first.")
        if problems:
            self.error.configure(text="\n".join(problems))
            return None

        mvr_email.save_client(self.folder, name=f"{v['first']} {v['last']}", dln=v["dln"],
                              phone=v["phone"], email=v["email"])
        self.go.configure(state="disabled", text="Opening Outlook…")
        self.update_idletasks()
        try:
            mail = mvr_email.create_outlook_draft(
                to=self.app.cfg["mvr_to"], cc=self.app.cfg.get("mvr_cc", ""),
                subject=mvr_email.build_subject(v["dln"], v["first"], v["last"]),
                body_html=mvr_email.build_body_html(v["first"], v["last"], v["dln"], v["phone"], v["email"]),
                attachments=[f for var, f in self.attach if var.get()],
                display=display)
        except mvr_email.OutlookNotReady as e:
            self.go.configure(state="normal", text="Create Outlook draft")
            self.error.configure(text=str(e))
            return None
        except Exception as e:
            self.go.configure(state="normal", text="Create Outlook draft")
            self.error.configure(text=f"Could not open Classic Outlook.\n{e}")
            return None
        if display:
            self.destroy()
        return mail


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg = config.load()
        ctk.set_appearance_mode(self.cfg["appearance"])
        self.title("Client Intake")
        self.geometry("1100x680")
        self.minsize(980, 600)
        self.configure(fg_color=BG)
        self.selected = None
        self.row_buttons = {}

        self._build_topbar()
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=3 * SP, pady=(0, 3 * SP))
        body.grid_columnconfigure(0, minsize=330)
        body.grid_columnconfigure(1, weight=1, minsize=280)
        body.grid_columnconfigure(2, weight=2, minsize=320)
        body.grid_rowconfigure(0, weight=1)

        self._build_new_client(body)
        self._build_client_list(body)
        self._build_details(body)

        self.bind("<Control-n>", lambda e: self.name_entry.focus_set())
        self.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self.bind("<F5>", lambda e: self.refresh_list())
        self.bind("<FocusIn>", self._on_focus)

        self.after(100, self._first_run)

    # ---------- helpers ----------
    @property
    def clients_root(self):
        return Path(self.cfg["clients_root"]) if self.cfg["clients_root"] else None

    def card(self, parent, **grid):
        c = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=12, border_width=1, border_color=BORDER)
        c.grid(sticky="nsew", **grid)
        return c

    def secondary_button(self, parent, text, command, **kw):
        return ctk.CTkButton(parent, text=text, command=command, height=36, font=font(13),
                             fg_color="transparent", border_width=1, border_color=BORDER,
                             text_color=TEXT, hover_color=SURFACE_ALT, **kw)

    def clear_entry(self, entry):
        entry.delete(0, "end")
        # CTkEntry only redraws its placeholder on focus-out
        if self.focus_get() is not entry._entry:
            entry._activate_placeholder()

    def _on_focus(self, event):
        # Refresh when returning to the app, so files saved elsewhere show up
        if event.widget is self:
            self.refresh_list(keep_scroll=True)

    def _first_run(self):
        if self.clients_root and self.clients_root.exists():
            self.refresh_list()
            return
        p = filedialog.askdirectory(parent=self, title="Choose your Clients folder")
        if p:
            self.cfg["clients_root"] = str(Path(p))
            config.save(self.cfg)
        self.on_settings_changed()

    def on_settings_changed(self):
        root = self.clients_root
        self.root_label.configure(text=shorten_path(root) if root else "No Clients folder set")
        self.refresh_list()

    # ---------- top bar ----------
    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent", height=64)
        bar.pack(fill="x", padx=3 * SP, pady=(2 * SP, 2 * SP))
        mark = ctk.CTkFrame(bar, width=10, height=28, corner_radius=3, fg_color=PRIMARY)
        mark.pack(side="left", padx=(0, 1.5 * SP))
        titles = ctk.CTkFrame(bar, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Client Intake", font=font(20, "bold"), text_color=TEXT, height=26) \
            .pack(anchor="w")
        self.root_label = ctk.CTkLabel(titles, text=shorten_path(self.cfg["clients_root"]) if self.cfg["clients_root"] else "No Clients folder set",
                                       font=font(12), text_color=MUTED, height=18)
        self.root_label.pack(anchor="w")
        self.secondary_button(bar, "Settings", lambda: SettingsDialog(self), width=96) \
            .pack(side="right")

    # ---------- column 1: new client ----------
    def _build_new_client(self, parent):
        c = self.card(parent, row=0, column=0, padx=(0, 2 * SP))
        c.grid_columnconfigure(0, weight=1)
        p = 2.5 * SP

        ctk.CTkLabel(c, text="New client", font=font(16, "bold"), text_color=TEXT) \
            .grid(row=0, column=0, sticky="w", padx=p, pady=(p, 0))
        ctk.CTkLabel(c, text="Creates the folder and fills the consent form.", font=font(12),
                     text_color=MUTED).grid(row=1, column=0, sticky="w", padx=p)

        ctk.CTkLabel(c, text="Client name *", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=2, column=0, sticky="w", padx=p, pady=(2.5 * SP, SP / 2))
        self.name_entry = ctk.CTkEntry(c, height=40, font=font(14),
                                       border_color=BORDER, placeholder_text="e.g. JOHN SMITH")
        self.name_entry.grid(row=3, column=0, sticky="ew", padx=p)
        self.name_error = ctk.CTkLabel(c, text="", font=font(12), text_color=DANGER, height=18)
        self.name_error.grid(row=4, column=0, sticky="w", padx=p)
        self.name_entry.bind("<KeyRelease>", lambda e: self._on_type(e, self.name_entry))

        ctk.CTkLabel(c, text="Driver's licence # *", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=5, column=0, sticky="w", padx=p, pady=(SP, SP / 2))
        dln_entry = self.dln_entry = ctk.CTkEntry(c, height=40, font=font(14),
                                 border_color=BORDER, placeholder_text="A1234-12345-12345")
        dln_entry.grid(row=6, column=0, sticky="ew", padx=p)
        self.dln_help = ctk.CTkLabel(c, text=DLN_HELP, font=font(12), text_color=MUTED,
                                     justify="left", anchor="w")
        self.dln_help.grid(row=7, column=0, sticky="w", padx=p, pady=(SP / 2, 0))
        dln_entry.bind("<KeyRelease>", lambda e: self._on_type(e, dln_entry))

        self.create_btn = ctk.CTkButton(c, text="Create client", height=44, font=font(14, "bold"),
                                        fg_color=PRIMARY, hover_color=PRIMARY_HOVER, corner_radius=8,
                                        command=self.create)
        self.create_btn.grid(row=8, column=0, sticky="ew", padx=p, pady=(3 * SP, SP))
        ctk.CTkLabel(c, text="Enter to create  ·  Ctrl+N new  ·  Ctrl+F search", font=font(11),
                     text_color=MUTED).grid(row=9, column=0, padx=p)

        self.banner = ctk.CTkFrame(c, fg_color=SUCCESS_BG, corner_radius=8)
        self.banner_text = ctk.CTkLabel(self.banner, text="", font=font(13), text_color=SUCCESS,
                                        justify="left", anchor="w", wraplength=260)
        self.banner_text.pack(fill="x", padx=1.5 * SP, pady=1.5 * SP)

        for w in (self.name_entry, dln_entry):
            w.bind("<Return>", lambda e: self.create())

    def _on_type(self, event, entry):
        """Uppercase as you type and clear that field's error."""
        if event.keysym == "Return":
            return
        text = entry.get()
        if text != text.upper():
            pos = entry._entry.index("insert")
            entry.delete(0, "end")
            entry.insert(0, text.upper())
            entry._entry.icursor(pos)
        if entry is self.name_entry:
            self.name_error.configure(text="")
            self.name_entry.configure(border_color=BORDER)
        else:
            self.dln_help.configure(text=DLN_HELP, text_color=MUTED)
            self.dln_entry.configure(border_color=BORDER)

    def _field_error(self, entry, label, text):
        label.configure(text=text, text_color=DANGER)
        entry.configure(border_color=DANGER)
        entry.focus_set()

    def _show_banner(self, text, ok=True):
        self.banner.configure(fg_color=SUCCESS_BG if ok else WARN_BG)
        self.banner_text.configure(text=text, text_color=SUCCESS if ok else DANGER)
        self.banner.grid(row=10, column=0, sticky="ew", padx=2.5 * SP, pady=(2 * SP, 0))

    def create(self):
        name = clean_name(self.name_entry.get())
        root = self.clients_root
        dln = self.dln_entry.get().strip()
        if not name:
            self._field_error(self.name_entry, self.name_error, "Enter the client's name.")
            return
        if not dln:
            self._field_error(self.dln_entry, self.dln_help, "Enter the driver's licence #.")
            return
        if not is_valid_dln(dln):
            self._field_error(self.dln_entry, self.dln_help,
                              "Licence # must be 1 letter + 14 digits,\ne.g. A1234-12345-12345.")
            return
        if not root or not root.exists():
            self._show_banner("Clients folder not found. Set it in Settings.", ok=False)
            return

        folder = root / name
        if folder.exists():
            self.name_error.configure(text=f"'{name}' already exists. Selected it in the list.")
            self.name_entry.configure(border_color=DANGER)
            self.clear_entry(self.search_entry)
            self.refresh_list()
            self.select(folder)
            return

        self.create_btn.configure(state="disabled", text="Creating…")
        self.update_idletasks()
        folder.mkdir()
        mvr_email.save_client(folder, name=name, dln=format_dln(dln))
        lines = [f"Created {name}"]
        ok = True
        try:
            fill(folder, dln, self.cfg["consent_template"])
            lines.append("Consent form filled")
        except Exception as e:
            lines.append(f"Consent form not filled: {e}")
            ok = False
        self.clipboard_clear()
        self.clipboard_append(format_dln(dln))
        lines.append("Licence # copied for DASH")
        self.create_btn.configure(state="normal", text="Create client")

        self._show_banner(("✓ " if ok else "") + "\n".join(lines), ok=ok)
        self.clear_entry(self.name_entry)
        self.clear_entry(self.dln_entry)
        self.clear_entry(self.search_entry)
        self.refresh_list()
        self.select(folder)
        self.name_entry.focus_set()
        os.startfile(folder)

    # ---------- column 2: client list ----------
    def _build_client_list(self, parent):
        c = self.card(parent, row=0, column=1, padx=(0, 2 * SP))
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(2, weight=1)
        p = 2 * SP

        head = ctk.CTkFrame(c, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=p, pady=(2.5 * SP, 0))
        ctk.CTkLabel(head, text="Clients", font=font(16, "bold"), text_color=TEXT).pack(side="left")
        self.count_label = ctk.CTkLabel(head, text="", font=font(12), text_color=MUTED)
        self.count_label.pack(side="right")

        self.search_entry = ctk.CTkEntry(c, height=36, font=font(13),
                                         border_color=BORDER, placeholder_text="Search clients")
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=p, pady=SP * 1.5)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh_list())

        self.list_frame = ctk.CTkScrollableFrame(c, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=SP, pady=(0, SP))
        self.list_frame.grid_columnconfigure(0, weight=1)

    def refresh_list(self, keep_scroll=False):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.row_buttons = {}
        root = self.clients_root
        if not root or not root.exists():
            self.count_label.configure(text="")
            self._empty_list("Set your Clients folder in Settings.")
            self.show_details(None)
            return

        q = self.search_entry.get().lower().strip()
        folders = sorted((p for p in root.iterdir() if p.is_dir()),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        shown = [p for p in folders if q in p.name.lower()]
        self.count_label.configure(text=f"{len(shown)} of {len(folders)}" if q else f"{len(folders)}")
        if not shown:
            self._empty_list("No clients match your search." if q else "No clients yet.")

        for i, folder in enumerate(shown[:300]):
            docs = find_docs(folder)
            have = sum(1 for v in docs.values() if v)
            when = datetime.datetime.fromtimestamp(folder.stat().st_mtime).strftime("%b %d, %Y")
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent", corner_radius=8, cursor="hand2")
            row.grid(row=i, column=0, sticky="ew", pady=1)
            ctk.CTkLabel(row, text=shorten(folder.name, 34), font=font(14, "bold"), text_color=TEXT,
                         anchor="w", height=20).pack(fill="x", padx=1.5 * SP, pady=(SP, 0))
            ctk.CTkLabel(row, text=f"{when}  ·  {have} of {len(DOCUMENTS)} documents", font=font(12),
                         text_color=MUTED, anchor="w", height=18).pack(fill="x", padx=1.5 * SP, pady=(0, SP))
            for w in (row, *row.winfo_children()):
                w.bind("<Button-1>", lambda e, f=folder: self.select(f))
                w.bind("<Double-Button-1>", lambda e, f=folder: os.startfile(f))
                w.bind("<Enter>", lambda e, f=folder, r=row: self.selected != f and r.configure(fg_color=SURFACE_ALT))
                w.bind("<Leave>", lambda e, f=folder, r=row: self.selected != f and r.configure(fg_color="transparent"))
            self.row_buttons[folder] = row

        if self.selected and self.selected in self.row_buttons:
            self.select(self.selected)
        else:
            self.show_details(None)

    def _empty_list(self, text):
        ctk.CTkLabel(self.list_frame, text=text, font=font(13), text_color=MUTED) \
            .grid(row=0, column=0, pady=4 * SP)

    def select(self, folder):
        for f, b in self.row_buttons.items():
            b.configure(fg_color=SELECTED if f == folder else "transparent")
        self.selected = folder
        self.show_details(folder)

    # ---------- column 3: details ----------
    def _build_details(self, parent):
        self.details = self.card(parent, row=0, column=2)
        self.details.grid_columnconfigure(0, weight=1)

    def show_details(self, folder):
        d = self.details
        for w in d.winfo_children():
            w.destroy()
        p = 2.5 * SP
        if not folder or not folder.exists():
            ctk.CTkLabel(d, text="Select a client", font=font(16, "bold"), text_color=TEXT) \
                .grid(row=0, column=0, pady=(10 * SP, SP))
            ctk.CTkLabel(d, text="Their documents and actions will show here.", font=font(13),
                         text_color=MUTED).grid(row=1, column=0)
            return

        ctk.CTkLabel(d, text=shorten(folder.name, 40), font=font(18, "bold"), text_color=TEXT, anchor="w") \
            .grid(row=0, column=0, sticky="ew", padx=p, pady=(p, 0))
        ctk.CTkLabel(d, text="Documents", font=font(12, "bold"), text_color=MUTED) \
            .grid(row=1, column=0, sticky="w", padx=p, pady=(2 * SP, SP))

        docs = find_docs(folder)
        lst = ctk.CTkFrame(d, fg_color="transparent")
        lst.grid(row=2, column=0, sticky="ew", padx=p)
        lst.grid_columnconfigure(0, weight=1)
        for i, (label, _) in enumerate(DOCUMENTS):
            files = docs[label]
            row = ctk.CTkFrame(lst, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
            row.grid(row=i, column=0, sticky="ew", pady=SP / 2)
            row.grid_columnconfigure(1, weight=1)

            dot = ctk.CTkFrame(row, width=10, height=10, corner_radius=5,
                               fg_color=SUCCESS if files else BORDER)
            dot.grid(row=0, column=0, rowspan=2, padx=(1.5 * SP, SP))
            ctk.CTkLabel(row, text=label, font=font(14, "bold"), text_color=TEXT, anchor="w", height=20) \
                .grid(row=0, column=1, sticky="w", pady=(SP, 0))
            if files:
                status = shorten(files[-1].name, 44) if len(files) == 1 else f"{len(files)} files"
            else:
                status = "Missing"
            ctk.CTkLabel(row, text=status, font=font(12), anchor="w", height=18,
                         text_color=MUTED if files else DANGER) \
                .grid(row=1, column=1, sticky="w", pady=(0, SP))
            open_btn = self.secondary_button(row, "Open", lambda fs=files: [os.startfile(f) for f in fs],
                                             width=72, state="normal" if files else "disabled")
            open_btn.grid(row=0, column=2, rowspan=2, padx=1.5 * SP)

        ctk.CTkLabel(d, text="Actions", font=font(12, "bold"), text_color=MUTED) \
            .grid(row=3, column=0, sticky="w", padx=p, pady=(3 * SP, SP))
        acts = ctk.CTkFrame(d, fg_color="transparent")
        acts.grid(row=4, column=0, sticky="ew", padx=p)
        ctk.CTkButton(acts, text="Request MVR", height=36, width=120, font=font(13, "bold"),
                      fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                      command=lambda: MvrDialog(self, folder)).pack(side="left", padx=(0, SP))
        self.secondary_button(acts, "Open folder", lambda: os.startfile(folder), width=110) \
            .pack(side="left", padx=(0, SP))
        refill = self.secondary_button(acts, "Refill consent from DASH", lambda: self.refill(folder),
                                       state="normal" if docs["DASH report"] else "disabled")
        refill.pack(side="left")
        if not docs["DASH report"]:
            ctk.CTkLabel(d, text="Save the DASH report(s) here to refill the consent with every driver.",
                         font=font(12), text_color=MUTED, wraplength=380, justify="left") \
                .grid(row=5, column=0, sticky="w", padx=p, pady=(SP, 0))
        self.detail_msg = ctk.CTkLabel(d, text="", font=font(13), text_color=SUCCESS,
                                       justify="left", anchor="w", wraplength=380)
        self.detail_msg.grid(row=6, column=0, sticky="w", padx=p, pady=(SP, 0))

    def refill(self, folder):
        try:
            _, drivers = fill(folder, template=self.cfg["consent_template"])
        except Exception as e:
            self.detail_msg.configure(text=f"Could not refill: {e}", text_color=DANGER)
            return
        self.refresh_list(keep_scroll=True)
        self.select(folder)
        names = "\n".join(f"{n}   {d}" for n, d in drivers)
        self.detail_msg.configure(text=f"✓ Consent refilled with:\n{names}", text_color=SUCCESS)


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    App().mainloop()
