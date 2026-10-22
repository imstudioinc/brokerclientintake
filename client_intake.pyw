"""Client Intake - desktop app for new client setup.

Creates the client folder, fills the consent form, and shows which
documents (Consent, DASH, Quote, MVR) each client folder already has.
"""
import datetime
import os
import queue
import re
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import config
from fill_consent import fill, format_dln, is_valid_dln, read_consent, read_dash
import dash_import
import emails
import mvr_email
import mvr_watch
import updater
from version import __version__

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


def parse_types(text):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def scan_clients(root, types):
    """[(folder, type)] for Clients/<Type>/<client>, plus older client folders kept
    directly in Clients (type "Other")."""
    wanted = {t.lower(): t for t in types}
    found = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        t = wanted.get(child.name.lower())
        if t:
            found += [(c, t) for c in child.iterdir() if c.is_dir()]
        else:
            found.append((child, "Other"))
    return found


def type_folder(root, client_type):
    """The existing Clients/<Type> folder (any capitalisation), or the one to create."""
    for child in root.iterdir():
        if child.is_dir() and child.name.lower() == client_type.lower():
            return child
    return root / client_type


def font(size=14, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Settings")
        self.geometry("580x730")
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
        self._path_row(body, 2, "Consent form template (empty = built-in form)", self.tpl_var, folder=False)

        ctk.CTkLabel(body, text="Appearance", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=4, column=0, sticky="w", padx=2 * SP, pady=(2 * SP, SP / 2))
        ctk.CTkSegmentedButton(body, values=["System", "Light", "Dark"], variable=self.mode_var,
                               font=font(13), selected_color=PRIMARY, selected_hover_color=PRIMARY_HOVER) \
            .grid(row=5, column=0, sticky="w", padx=2 * SP)

        self._text_row(body, 6, "MVR request: To", self.to_var, "branch manager's email")
        self._text_row(body, 8, "MVR request: CC", self.cc_var, "optional; separate several with ;")

        self.mail_var = tk.StringVar(value=app.cfg.get("email_app", "New Outlook"))
        ctk.CTkLabel(body, text="Email app", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=10, column=0, sticky="w", padx=2 * SP, pady=(2 * SP, SP / 2))
        ctk.CTkSegmentedButton(body, values=["New Outlook", "Classic Outlook"], variable=self.mail_var,
                               font=font(13), selected_color=PRIMARY, selected_hover_color=PRIMARY_HOVER) \
            .grid(row=11, column=0, sticky="w", padx=2 * SP)
        app.secondary_button(body, "Email signature…", lambda: SignatureDialog(self, app), width=150) \
            .grid(row=11, column=0, sticky="e", padx=2 * SP)

        self.types_var = tk.StringVar(value=app.cfg.get("client_types", ""))
        self._text_row(body, 12, "Client types", self.types_var, "folders inside Clients, separated by commas")

        self.autosave_var = tk.BooleanVar(value=app.cfg.get("mvr_autosave", True))
        ctk.CTkSwitch(body, text="Auto-save MVRs: file MVR PDFs from Downloads into the client's folder",
                      variable=self.autosave_var, font=font(13), text_color=TEXT, progress_color=PRIMARY) \
            .grid(row=14, column=0, sticky="w", padx=2 * SP, pady=(2 * SP, 0))

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=15, column=0, sticky="e", padx=2 * SP, pady=2 * SP)
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
        config.update(self.app.cfg,
                      clients_root=self.root_var.get().strip(),
                      consent_template=self.tpl_var.get().strip(),
                      appearance=self.mode_var.get(),
                      mvr_to=self.to_var.get().strip(),
                      mvr_cc=self.cc_var.get().strip(),
                      email_app=self.mail_var.get(),
                      mvr_autosave=self.autosave_var.get(),
                      client_types=", ".join(parse_types(self.types_var.get())) or config.DEFAULTS["client_types"])
        ctk.set_appearance_mode(self.app.cfg["appearance"])
        self.app.on_settings_changed()
        self.app.reload_types()
        self.destroy()


class SignatureDialog(ctk.CTkToplevel):
    """Per-computer email signature details (logo, website and notice come from templates/)."""

    FIELDS = [("name", "Your name", "e.g. Ilkin Mammadzada"),
              ("title", "Title", "e.g. Insurance Broker"),
              ("phone", "Phone", "e.g. +1 (437) 421-3210"),
              ("email", "Email", "e.g. name@wellcareinsurance.ca"),
              ("address1", "Address line 1", "e.g. Unit 2-427 Dundas St E"),
              ("address2", "Address line 2", "e.g. Waterdown, ON L8B 0K4"),
              ("branch", "Branch", "e.g. Branch #24")]

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Email signature")
        self.geometry("520x660")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.grab_set()

        body = ctk.CTkScrollableFrame(self, fg_color=SURFACE, corner_radius=12,
                                      border_width=1, border_color=BORDER)
        body.pack(fill="both", expand=True, padx=2 * SP, pady=(2 * SP, 0))
        body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(body, text="Added to the bottom of every email the app creates (New and Classic Outlook).\n"
                                "Logo, website and confidentiality notice are added automatically.\n"
                                "Leave your name empty for no signature.",
                     font=font(12), text_color=MUTED, justify="left") \
            .grid(row=0, column=0, sticky="w", padx=2 * SP, pady=(2 * SP, 0))

        self.entries = {}
        for i, (key, label, hint) in enumerate(self.FIELDS):
            ctk.CTkLabel(body, text=label, font=font(13, "bold"), text_color=TEXT) \
                .grid(row=1 + 2 * i, column=0, sticky="w", padx=2 * SP, pady=(1.5 * SP, SP / 2))
            e = ctk.CTkEntry(body, height=36, font=font(13), border_color=BORDER, placeholder_text=hint)
            e.grid(row=2 + 2 * i, column=0, sticky="ew", padx=2 * SP)
            value = app.cfg.get(f"sig_{key}") or ("Insurance Broker" if key == "title" else "")
            if value:
                e.insert(0, value)
            self.entries[key] = e
        ctk.CTkLabel(body, text="").grid(row=99, column=0)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=2 * SP, pady=2 * SP)
        ctk.CTkButton(btns, text="Save", width=96, height=36, font=font(13, "bold"),
                      fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=self.save).pack(side="right")
        app.secondary_button(btns, "Cancel", self.destroy, width=96).pack(side="right", padx=(0, SP))
        self.bind("<Escape>", lambda e: self.destroy())

    def save(self):
        config.update(self.app.cfg, **{f"sig_{k}": e.get().strip() for k, e in self.entries.items()})
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
        # Prefill from: saved client details -> consent form -> DASH report -> folder name
        sources = [(info.get("name", ""), info.get("dln", ""))]
        sources += [read_consent(f) for f in docs["Client consent"][:1]]
        sources += [read_dash(f) for f in docs["DASH report"][:1]]
        sources = [s for s in sources if s]
        name = next((n for n, _ in sources if n), folder.name).upper()
        dln = next((d for _, d in sources if d), "")
        first, last = mvr_email.split_name(name)

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

        if app.cfg.get("mvr_autosave", True):
            ctk.CTkLabel(body, text="When the reply arrives, click Download on the MVR in Outlook - "
                                    "Client Intake files it into this client's folder automatically.",
                         font=font(12), text_color=SUCCESS, justify="left", wraplength=440) \
                .grid(row=98, column=0, columnspan=2, sticky="w", padx=p, pady=(SP, 0))

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
                              phone=v["phone"], email=v["email"],
                              mvr_requested=datetime.datetime.now().isoformat(timespec="minutes"))
        self.go.configure(state="disabled", text="Opening Outlook…")
        self.update_idletasks()
        email = dict(
            to=self.app.cfg["mvr_to"], cc=self.app.cfg.get("mvr_cc", ""),
            subject=mvr_email.build_subject(v["dln"], v["first"], v["last"]),
            body_html=mvr_email.build_body_html(v["first"], v["last"], v["dln"], v["phone"], v["email"]),
            attachments=[f for var, f in self.attach if var.get()])
        classic = self.app.cfg.get("email_app") == "Classic Outlook"
        try:
            if classic:
                mail = mvr_email.create_outlook_draft(
                    display=display, signature_html=mvr_email.build_signature(self.app.cfg), **email)
            else:
                mail = mvr_email.create_new_outlook_draft(
                    self.folder, signature_html=mvr_email.build_signature(self.app.cfg), **email)
        except mvr_email.OutlookNotReady as e:
            self.go.configure(state="normal", text="Create Outlook draft")
            self.error.configure(text=str(e))
            return None
        except Exception as e:
            self.go.configure(state="normal", text="Create Outlook draft")
            self.error.configure(text=f"Could not open {'Classic' if classic else 'New'} Outlook.\n{e}")
            return None
        if display:
            self.destroy()
        return mail


class EmailDialog(ctk.CTkToplevel):
    """Pick a client email template, fill the blanks, attach files, open an Outlook draft."""

    ATTACHABLE = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".doc", ".docx", ".xlsx"}

    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, folder
        self.title(f"Email client - {folder.name.upper()}")
        self.geometry("1040x720")
        self.minsize(900, 600)
        self.configure(fg_color=BG)
        self.transient(app)
        self.grab_set()

        self.info = mvr_email.load_client(folder)
        self.client = (self.info.get("name") or folder.name).upper()
        self.saved_fields = dict(self.info.get("email_fields", {}))
        self.templates = emails.load_templates()
        self.by_label = {f"{t.group[3:]}  ·  {t.name}" if t.group[:1].isdigit() else t.name: t
                         for t in self.templates}

        self.grid_columnconfigure(0, weight=2, uniform="cols")
        self.grid_columnconfigure(1, weight=3, uniform="cols")
        self.grid_rowconfigure(0, weight=1)
        p = 2 * SP

        # ----- left: template, recipient, blanks, attachments -----
        left = ctk.CTkScrollableFrame(self, fg_color=SURFACE, corner_radius=12, border_width=1, border_color=BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(2 * SP, SP), pady=(2 * SP, 0))
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Template", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=0, column=0, sticky="w", padx=p, pady=(p, SP / 2))
        ctype = app.client_type_of.get(folder, "").lower()
        start = next((l for l, t in self.by_label.items() if t.file == f"quote-{ctype}.html"),
                     next(iter(self.by_label)))
        self.choice = tk.StringVar(value=start)
        ctk.CTkOptionMenu(left, values=list(self.by_label), variable=self.choice, height=36, font=font(13),
                          dropdown_font=font(13), fg_color=SURFACE_ALT, button_color=PRIMARY,
                          button_hover_color=PRIMARY_HOVER, text_color=TEXT, dynamic_resizing=False,
                          command=lambda _: self.on_template()) \
            .grid(row=1, column=0, sticky="ew", padx=p)

        ctk.CTkLabel(left, text="To (client email) *", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=2, column=0, sticky="w", padx=p, pady=(1.5 * SP, SP / 2))
        self.to = ctk.CTkEntry(left, height=36, font=font(13), border_color=BORDER,
                               placeholder_text="client@email.com")
        self.to.grid(row=3, column=0, sticky="ew", padx=p)
        if self.info.get("email"):
            self.to.insert(0, self.info["email"])

        ctk.CTkLabel(left, text="Greeting name", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=4, column=0, sticky="w", padx=p, pady=(1.5 * SP, SP / 2))
        self.greeting = ctk.CTkEntry(left, height=36, font=font(13), border_color=BORDER)
        self.greeting.grid(row=5, column=0, sticky="ew", padx=p)
        self.greeting.insert(0, emails.first_name(self.client))
        self.greeting.bind("<KeyRelease>", lambda e: self.refresh_preview())

        self.fields_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.fields_frame.grid(row=6, column=0, sticky="ew", padx=p)
        self.fields_frame.grid_columnconfigure(0, weight=1)
        self.field_entries = {}

        ctk.CTkLabel(left, text="Attach", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=7, column=0, sticky="w", padx=p, pady=(2 * SP, 0))
        self.attach_note = ctk.CTkLabel(left, text="", font=font(12), text_color=MUTED,
                                        justify="left", wraplength=340)
        self.attach_note.grid(row=8, column=0, sticky="w", padx=p)
        self.attach_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.attach_frame.grid(row=9, column=0, sticky="ew", padx=p)
        self.attach = []
        for f in sorted(folder.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
            if f.is_file() and f.suffix.lower() in self.ATTACHABLE:
                self._add_attachment(f, checked=False)
        app.secondary_button(left, "Add file…", self.browse_file, width=100) \
            .grid(row=10, column=0, sticky="w", padx=p, pady=(SP, p))

        # ----- right: preview -----
        right = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=12, border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(SP, 2 * SP), pady=(2 * SP, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(right, text="Subject", font=font(12, "bold"), text_color=MUTED) \
            .grid(row=0, column=0, sticky="w", padx=p, pady=(p, 0))
        self.subject_label = ctk.CTkLabel(right, text="", font=font(14, "bold"), text_color=TEXT,
                                          justify="left", anchor="w", wraplength=560)
        self.subject_label.grid(row=1, column=0, sticky="ew", padx=p)
        ctk.CTkLabel(right, text="Preview (your signature is added at the bottom)", font=font(12, "bold"),
                     text_color=MUTED).grid(row=2, column=0, sticky="w", padx=p, pady=(1.5 * SP, SP / 2))
        self.preview = ctk.CTkTextbox(right, font=font(13), wrap="word", fg_color=SURFACE_ALT,
                                      border_width=1, border_color=BORDER, text_color=TEXT)
        self.preview.grid(row=3, column=0, sticky="nsew", padx=p, pady=(0, p))

        # ----- bottom bar -----
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2 * SP, pady=2 * SP)
        # buttons are packed first so a long message can never push them off-screen
        self.go = ctk.CTkButton(bottom, text="Create Outlook draft", height=40, font=font(14, "bold"),
                                fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=self.submit)
        self.go.pack(side="right")
        app.secondary_button(bottom, "Cancel", self.destroy, width=96).pack(side="right", padx=(0, SP))
        app.secondary_button(bottom, "Edit this template", self.edit_template, width=150).pack(side="left")
        self.error = ctk.CTkLabel(bottom, text="", font=font(12), text_color=DANGER, justify="left",
                                  anchor="w", wraplength=560)
        self.error.pack(side="left", fill="x", expand=True, padx=2 * SP)
        self.bind("<Escape>", lambda e: self.destroy())

        self.on_template()

    # ----- template + fields -----
    @property
    def template(self):
        return self.by_label[self.choice.get()]

    def on_template(self):
        for w in self.fields_frame.winfo_children():
            w.destroy()
        self.field_entries = {}
        for i, (key, label) in enumerate(self.template.fields):
            ctk.CTkLabel(self.fields_frame, text=label, font=font(13, "bold"), text_color=TEXT, anchor="w") \
                .grid(row=2 * i, column=0, sticky="w", pady=(1.5 * SP, SP / 2))
            e = ctk.CTkEntry(self.fields_frame, height=36, font=font(13), border_color=BORDER)
            e.grid(row=2 * i + 1, column=0, sticky="ew")
            if self.saved_fields.get(key):
                e.insert(0, self.saved_fields[key])
            e.bind("<KeyRelease>", lambda ev: self.refresh_preview())
            self.field_entries[key] = e
        note = self.template.attach
        self.attach_note.configure(text=f"Suggested: {note}" if note else "Nothing needed for this email.")
        self.error.configure(text="")
        self.refresh_preview()

    def values(self):
        v = {"first_name": self.greeting.get().strip(), "CLIENT_NAME": self.client,
             "client_name": self.client.title(), "broker_name": self.app.cfg.get("sig_name", "")}
        v.update({k: e.get().strip() for k, e in self.field_entries.items()})
        return v

    def refresh_preview(self):
        if self.error.cget("text").startswith("Fill in"):
            self.error.configure(text="")
        subject, body = emails.render(self.template, self.values())
        self.subject_label.configure(text=subject)
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", emails.to_text(body))
        self.preview.configure(state="disabled")

    # ----- attachments -----
    def _add_attachment(self, path, checked=True):
        if any(f == path for _, f in self.attach):
            return
        var = tk.BooleanVar(value=checked)
        ctk.CTkCheckBox(self.attach_frame, text=shorten(Path(path).name, 46), variable=var, font=font(13),
                        text_color=TEXT, fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                        border_color=MUTED).pack(anchor="w", pady=SP / 2)
        self.attach.append((var, Path(path)))

    def browse_file(self):
        for p in filedialog.askopenfilenames(parent=self, title="Attach files", initialdir=self.folder):
            self._add_attachment(Path(p))

    def edit_template(self):
        path = emails.edit_copy(self.template)
        os.startfile(path)
        self.error.configure(text=f"Editing your copy: {path.name}. Save it, then reopen this window.",
                             text_color=MUTED)

    # ----- create -----
    def submit(self):
        to = self.to.get().strip()
        if not re.fullmatch(r"[^@\s;]+@[^@\s;]+\.[^@\s;]+", to):
            self.error.configure(text="Enter the client's email address.", text_color=DANGER)
            self.to.focus_set()
            return
        values = self.values()
        missing = emails.missing_fields(self.template, values)
        if missing:
            labels = dict(self.template.fields)
            names = ", ".join(re.sub(r"\s*\(.*\)", "", labels.get(m, m)) for m in missing)
            self.error.configure(text=f"Fill in: {names}", text_color=DANGER)
            return
        subject, body = emails.render(self.template, values)

        self.saved_fields.update({k: e.get().strip() for k, e in self.field_entries.items() if e.get().strip()})
        mvr_email.save_client(self.folder, email=to.lower(), email_fields=self.saved_fields)

        self.go.configure(state="disabled", text="Opening Outlook…")
        self.update_idletasks()
        attachments = [f for var, f in self.attach if var.get()]
        try:
            if self.app.cfg.get("email_app") == "Classic Outlook":
                mvr_email.create_outlook_draft(to=to, cc="", subject=subject, body_html=body,
                                               attachments=attachments,
                                               signature_html=mvr_email.build_signature(self.app.cfg))
            else:
                mvr_email.create_new_outlook_draft(
                    self.folder, to=to, cc="", subject=subject, body_html=body, attachments=attachments,
                    signature_html=mvr_email.build_signature(self.app.cfg), label=self.template.name)
        except mvr_email.OutlookNotReady as e:
            self.go.configure(state="normal", text="Create Outlook draft")
            self.error.configure(text=str(e), text_color=DANGER)
            return
        except Exception as e:
            self.go.configure(state="normal", text="Create Outlook draft")
            self.error.configure(text=f"Could not open Outlook.\n{e}", text_color=DANGER)
            return
        self.destroy()
        self.app.show_note(self.folder, f"✓ Draft opened: {self.template.name}", SUCCESS)


class ImportDashDialog(ctk.CTkToplevel):
    """Pick DASH reports from Downloads and move them into the client folder."""

    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, folder
        self.title(f"Import DASH - {folder.name.upper()}")
        self.geometry("560x520")
        self.configure(fg_color=BG)
        self.transient(app)
        self.grab_set()

        self.downloads = dash_import.downloads_dir()
        reports = dash_import.find_dash_downloads(self.downloads)
        client = (mvr_email.load_client(folder).get("name") or folder.name).upper()

        body = ctk.CTkScrollableFrame(self, fg_color=SURFACE, corner_radius=12,
                                      border_width=1, border_color=BORDER)
        body.pack(fill="both", expand=True, padx=2 * SP, pady=(2 * SP, 0))
        body.grid_columnconfigure(0, weight=1)
        p = 2 * SP

        ctk.CTkLabel(body, text="DASH reports in Downloads", font=font(15, "bold"), text_color=TEXT) \
            .grid(row=0, column=0, sticky="w", padx=p, pady=(p, 0))
        ctk.CTkLabel(body, text=f"Reports matching {client} are ticked. Tick other drivers on the "
                                "same policy too.\nThey are moved into the client folder and the "
                                "consent form is refilled.",
                     font=font(12), text_color=MUTED, justify="left", wraplength=480) \
            .grid(row=1, column=0, sticky="w", padx=p, pady=(SP / 2, SP))

        self.rows = []
        for i, r in enumerate(reports):
            var = tk.BooleanVar(value=dash_import.names_match(client, r["name"]))
            when = datetime.datetime.fromtimestamp(r["mtime"]).strftime("%b %d, %I:%M %p")
            row = ctk.CTkFrame(body, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
            row.grid(row=2 + i, column=0, sticky="ew", padx=p, pady=SP / 2)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkCheckBox(row, text="", variable=var, width=24, fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                            border_color=MUTED).grid(row=0, column=0, rowspan=2, padx=(1.5 * SP, SP))
            ctk.CTkLabel(row, text=r["name"] or r["path"].name, font=font(14, "bold"), text_color=TEXT,
                         anchor="w", height=20).grid(row=0, column=1, sticky="w", pady=(SP, 0))
            ctk.CTkLabel(row, text=f"{r['dln'] or 'Licence # not found'}  ·  downloaded {when}",
                         font=font(12), text_color=MUTED, anchor="w", height=18) \
                .grid(row=1, column=1, sticky="w", pady=(0, SP))
            self.rows.append((var, r))

        if not reports:
            ctk.CTkLabel(body, text="No DASH reports found in Downloads.\n"
                                    "Download the report from the DASH portal first.",
                         font=font(13), text_color=MUTED, justify="center") \
                .grid(row=2, column=0, pady=5 * SP)
        self.error = ctk.CTkLabel(body, text="", font=font(12), text_color=DANGER)
        self.error.grid(row=99, column=0, sticky="w", padx=p, pady=(SP, p))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=2 * SP, pady=2 * SP)
        app.secondary_button(btns, "Open Downloads", lambda: os.startfile(self.downloads), width=130) \
            .pack(side="left")
        self.go = ctk.CTkButton(btns, text="Import selected", height=40, font=font(14, "bold"),
                                fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=self.submit,
                                state="normal" if reports else "disabled")
        self.go.pack(side="right")
        app.secondary_button(btns, "Cancel", self.destroy, width=96).pack(side="right", padx=(0, SP))
        self.bind("<Escape>", lambda e: self.destroy())

    def submit(self):
        chosen = [r for var, r in self.rows if var.get()]
        if not chosen:
            self.error.configure(text="Tick at least one report.")
            return
        try:
            moved = dash_import.import_reports([r["path"] for r in chosen], self.folder)
        except OSError as e:
            self.error.configure(text=f"Could not move the file (is it open in another program?)\n{e}")
            return
        info = mvr_email.load_client(self.folder)
        if not info.get("dln") and chosen[0]["dln"]:
            mvr_email.save_client(self.folder, dln=chosen[0]["dln"])
        self.destroy()
        n = len(moved)
        self.app.refill(self.folder, prefix=f"✓ Imported {n} DASH report{'s' if n > 1 else ''}.\n")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg = config.load()
        ctk.set_appearance_mode(self.cfg["appearance"])
        icon = Path(__file__).parent / "templates" / "app.ico"
        if icon.exists():
            self.after(250, lambda: self.iconbitmap(str(icon)))  # after CTk sets its own icon
        self.title("Client Intake")
        self.geometry("1120x780")
        self.minsize(980, 720)
        self.configure(fg_color=BG)
        self.selected = None
        self.note = None
        self.client_type_of = {}
        self.ui_queue = queue.Queue()  # created before any background thread starts
        self._drain_ui()
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
    def client_types(self):
        return parse_types(self.cfg.get("client_types")) or ["Auto", "Home", "Tenant", "Commercial"]

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
            config.update(self.cfg, clients_root=str(Path(p)))
        self.on_settings_changed()

    def reload_types(self):
        types = self.client_types
        self.type_buttons.configure(values=types)
        if self.type_var.get() not in types:
            self.type_var.set(types[0])
        self.refresh_list()

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
        name_line = ctk.CTkFrame(titles, fg_color="transparent")
        name_line.pack(anchor="w")
        ctk.CTkLabel(name_line, text="Client Intake", font=font(20, "bold"), text_color=TEXT, height=26) \
            .pack(side="left")
        ctk.CTkLabel(name_line, text=f"  v{__version__}", font=font(12), text_color=MUTED, height=26) \
            .pack(side="left", anchor="s")
        self.root_label = ctk.CTkLabel(titles, text=shorten_path(self.cfg["clients_root"]) if self.cfg["clients_root"] else "No Clients folder set",
                                       font=font(12), text_color=MUTED, height=18)
        self.root_label.pack(anchor="w")
        self.secondary_button(bar, "Settings", lambda: SettingsDialog(self), width=96) \
            .pack(side="right")

        # Shown only when a newer version is published
        self.update_bar = ctk.CTkFrame(bar, fg_color=SUCCESS_BG, corner_radius=8)
        self.update_text = ctk.CTkLabel(self.update_bar, text="", font=font(13), text_color=SUCCESS)
        self.update_text.pack(side="left", padx=(1.5 * SP, SP), pady=SP)
        self.update_btn = ctk.CTkButton(self.update_bar, text="Update now", height=32, width=110,
                                        font=font(13, "bold"), fg_color=SUCCESS, hover_color=SUCCESS,
                                        text_color=("#FFFFFF", "#0F1419"), command=self.install_update)
        self.update_btn.pack(side="left", padx=(0, SP), pady=SP)
        self.pending_update = None
        if updater.is_packaged():
            threading.Thread(target=self._check_update, daemon=True).start()

        # Toast for things that happen in the background (MVR filed)
        self.toast = ctk.CTkFrame(bar, fg_color=SUCCESS_BG, corner_radius=8)
        self.toast_text = ctk.CTkLabel(self.toast, text="", font=font(13), text_color=SUCCESS)
        self.toast_text.pack(side="left", padx=(1.5 * SP, SP), pady=SP)
        self.toast_btn = ctk.CTkButton(self.toast, text="Open", height=30, width=80, font=font(13, "bold"),
                                       fg_color=SUCCESS, hover_color=SUCCESS, text_color=("#FFFFFF", "#0F1419"))
        self.toast_btn.pack(side="left", padx=(0, SP / 2), pady=SP)
        ctk.CTkButton(self.toast, text="✕", width=30, height=30, font=font(13), fg_color="transparent",
                      hover_color=SURFACE_ALT, text_color=MUTED, command=self.hide_toast) \
            .pack(side="left", padx=(0, SP / 2))
        self._toast_job = None
        self.mvr_watcher = mvr_watch.Watcher(dash_import.downloads_dir())
        threading.Thread(target=self._watch_mvrs, daemon=True).start()

    # ---------- background threads -> window ----------
    def ui(self, func, *args):
        """Run func on the window's thread. Background threads must not touch widgets."""
        self.ui_queue.put((func, args))

    def _drain_ui(self):
        while True:
            try:
                func, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                func(*args)
            except Exception:
                pass
        self.after(200, self._drain_ui)

    # ---------- MVR auto-save ----------
    def _watch_mvrs(self):
        import time
        while True:
            time.sleep(4)
            if not self.cfg.get("mvr_autosave", True):
                continue
            try:
                events = self.mvr_watcher.poll(list(self.client_type_of))
            except Exception:
                continue  # a bad file must never stop the watcher
            # warnings last, so a success message never hides them
            for ev in sorted(events, key=lambda ev: ev[0] == "unmatched"):
                self.ui(lambda ev=ev: self._on_mvr_event(ev))

    def _on_mvr_event(self, ev):
        if ev[0] == "filed":
            _, dest, folder, how = ev
            kind = self.client_type_of.get(folder, "")
            self.show_toast(f"✓ MVR saved for {folder.name}" + (f" ({kind})" if kind else ""),
                            "Open", lambda: os.startfile(dest), ok=True)
            self.refresh_list(keep_scroll=True)
            if self.selected == folder:
                self.show_note(folder, f"✓ MVR received and saved: {dest.name}", SUCCESS)
        else:
            _, path, reason = ev
            self.show_toast(f"MVR in Downloads not filed ({reason}): {shorten(path.name, 40)}",
                            "Show", lambda: os.startfile(path.parent), ok=False)

    def show_toast(self, text, button, command, ok=True):
        self.toast.configure(fg_color=SUCCESS_BG if ok else WARN_BG)
        self.toast_text.configure(text=text, text_color=SUCCESS if ok else DANGER)
        self.toast_btn.configure(text=button, command=command,
                                 fg_color=SUCCESS if ok else DANGER, hover_color=SUCCESS if ok else DANGER)
        self.toast.pack(side="right", padx=(0, 2 * SP))
        if self._toast_job:
            self.after_cancel(self._toast_job)
        self._toast_job = self.after(20000 if ok else 60000, self.hide_toast)

    def hide_toast(self):
        self.toast.pack_forget()
        self._toast_job = None

    # ---------- updates ----------
    def _check_update(self):
        try:
            found = updater.check_for_update()
        except Exception:
            return  # offline or GitHub unreachable: try again next launch
        if found:
            self.ui(lambda: self._show_update(found))

    def _show_update(self, found):
        self.pending_update = found
        self.update_text.configure(text=f"Version {found['version']} is available")
        self.update_bar.pack(side="right", padx=(0, 2 * SP))

    def install_update(self):
        self.update_btn.configure(state="disabled", text="Downloading…")
        self.update_text.configure(text=f"Updating to {self.pending_update['version']}…")

        def progress(fraction):
            self.ui(lambda: self.update_btn.configure(text=f"{int(fraction * 100)}%"))

        def work():
            try:
                updater.download_and_install(self.pending_update, progress)
            except Exception as e:
                self.ui(lambda: (self.update_text.configure(text=f"Update failed: {e}", text_color=DANGER),
                                       self.update_btn.configure(state="normal", text="Try again")))
                return
            self.ui(self.destroy)  # the update script waits for this window to close

        threading.Thread(target=work, daemon=True).start()

    # ---------- column 1: new client ----------
    def _build_new_client(self, parent):
        c = self.card(parent, row=0, column=0, padx=(0, 2 * SP))
        c.grid_columnconfigure(0, weight=1)
        p = 2.5 * SP

        ctk.CTkLabel(c, text="New client", font=font(16, "bold"), text_color=TEXT) \
            .grid(row=0, column=0, sticky="w", padx=p, pady=(p, 0))
        top = ctk.CTkFrame(c, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=p)
        ctk.CTkLabel(top, text="Creates the folder and fills the consent form.", font=font(12),
                     text_color=MUTED).pack(anchor="w")
        ctk.CTkLabel(top, text="Type *", font=font(13, "bold"), text_color=TEXT) \
            .pack(anchor="w", pady=(2 * SP, SP / 2))
        last = self.cfg.get("last_type")
        self.type_var = tk.StringVar(value=last if last in self.client_types else self.client_types[0])
        self.type_buttons = ctk.CTkSegmentedButton(top, values=self.client_types, variable=self.type_var,
                                                   font=font(13), height=34, selected_color=PRIMARY,
                                                   selected_hover_color=PRIMARY_HOVER)
        self.type_buttons.pack(anchor="w", fill="x")

        ctk.CTkLabel(c, text="Client name *", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=2, column=0, sticky="w", padx=p, pady=(1.5 * SP, SP / 2))
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

        contact = ctk.CTkFrame(c, fg_color="transparent")
        contact.grid(row=8, column=0, sticky="ew", padx=p, pady=(1.5 * SP, 0))
        contact.grid_columnconfigure((0, 1), weight=1, uniform="contact")
        ctk.CTkLabel(contact, text="Phone", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=0, column=0, sticky="w", pady=(0, SP / 2))
        ctk.CTkLabel(contact, text="Email", font=font(13, "bold"), text_color=TEXT) \
            .grid(row=0, column=1, sticky="w", padx=(SP, 0), pady=(0, SP / 2))
        self.phone_entry = ctk.CTkEntry(contact, height=36, font=font(13), border_color=BORDER,
                                        placeholder_text="optional")
        self.phone_entry.grid(row=1, column=0, sticky="ew")
        self.email_entry = ctk.CTkEntry(contact, height=36, font=font(13), border_color=BORDER,
                                        placeholder_text="optional")
        self.email_entry.grid(row=1, column=1, sticky="ew", padx=(SP, 0))

        self.create_btn = ctk.CTkButton(c, text="Create client", height=44, font=font(14, "bold"),
                                        fg_color=PRIMARY, hover_color=PRIMARY_HOVER, corner_radius=8,
                                        command=self.create)
        self.create_btn.grid(row=9, column=0, sticky="ew", padx=p, pady=(2.5 * SP, SP))
        ctk.CTkLabel(c, text="Enter to create  ·  Ctrl+N new  ·  Ctrl+F search", font=font(11),
                     text_color=MUTED).grid(row=10, column=0, padx=p)

        self.banner = ctk.CTkFrame(c, fg_color=SUCCESS_BG, corner_radius=8)
        self.banner_text = ctk.CTkLabel(self.banner, text="", font=font(13), text_color=SUCCESS,
                                        justify="left", anchor="w", wraplength=260)
        self.banner_text.pack(fill="x", padx=1.5 * SP, pady=1.5 * SP)

        for w in (self.name_entry, dln_entry, self.phone_entry, self.email_entry):
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
        self.banner.grid(row=11, column=0, sticky="ew", padx=2.5 * SP, pady=(1.5 * SP, 0))

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

        client_type = self.type_var.get()
        folder = type_folder(root, client_type) / name
        if folder.exists():
            self.name_error.configure(text=f"'{name}' already exists in {client_type}. Selected it in the list.")
            self.name_entry.configure(border_color=DANGER)
            self.clear_entry(self.search_entry)
            self.filter_var.set("All")
            self.refresh_list()
            self.select(folder)
            return
        elsewhere = sorted({t for f, t in scan_clients(root, self.client_types)
                            if f.name.upper() == name and t != client_type})

        self.create_btn.configure(state="disabled", text="Creating…")
        self.update_idletasks()
        folder.mkdir(parents=True)
        if self.cfg.get("last_type") != client_type:
            config.update(self.cfg, last_type=client_type)
        mvr_email.save_client(folder, name=name, type=client_type, dln=format_dln(dln),
                              phone=mvr_email.format_phone(self.phone_entry.get()) or None,
                              email=self.email_entry.get().strip().lower() or None)
        lines = [f"Created {name} in {client_type}"]
        if elsewhere:
            lines.append(f"(also has a folder in {', '.join(elsewhere)})")
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
        self.clear_entry(self.phone_entry)
        self.clear_entry(self.email_entry)
        self.clear_entry(self.search_entry)
        if self.filter_var.get() not in ("All", client_type):
            self.filter_var.set("All")
        self.refresh_list()
        self.select(folder)
        self.name_entry.focus_set()
        os.startfile(folder)

    # ---------- column 2: client list ----------
    def _build_client_list(self, parent):
        c = self.card(parent, row=0, column=1, padx=(0, 2 * SP))
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(3, weight=1)
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

        self.filter_var = tk.StringVar(value="All")
        self.filter_buttons = ctk.CTkSegmentedButton(c, values=["All"] + self.client_types,
                                                     variable=self.filter_var, font=font(11), height=30,
                                                     selected_color=PRIMARY, selected_hover_color=PRIMARY_HOVER,
                                                     command=lambda _: self.refresh_list())
        self.filter_buttons.grid(row=2, column=0, sticky="ew", padx=p, pady=(0, SP))

        self.list_frame = ctk.CTkScrollableFrame(c, fg_color="transparent")
        self.list_frame.grid(row=3, column=0, sticky="nsew", padx=SP, pady=(0, SP))
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
        types = self.client_types
        clients = sorted(scan_clients(root, types), key=lambda ft: ft[0].stat().st_mtime, reverse=True)
        self.client_type_of = dict(clients)
        values = ["All"] + types + (["Other"] if any(t == "Other" for _, t in clients) else [])
        if list(self.filter_buttons.cget("values")) != values:
            self.filter_buttons.configure(values=values)
        if self.filter_var.get() not in values:
            self.filter_var.set("All")
        kind = self.filter_var.get()
        shown = [(f, t) for f, t in clients if q in f.name.lower() and kind in ("All", t)]
        filtered = bool(q) or kind != "All"
        self.count_label.configure(text=f"{len(shown)} of {len(clients)}" if filtered else f"{len(clients)}")
        if not shown:
            self._empty_list("No clients match your search." if filtered else "No clients yet.")

        for i, (folder, ftype) in enumerate(shown[:300]):
            docs = find_docs(folder)
            have = sum(1 for v in docs.values() if v)
            when = datetime.datetime.fromtimestamp(folder.stat().st_mtime).strftime("%b %d, %Y")
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent", corner_radius=8, cursor="hand2")
            row.grid(row=i, column=0, sticky="ew", pady=1)
            ctk.CTkLabel(row, text=shorten(folder.name, 34), font=font(14, "bold"), text_color=TEXT,
                         anchor="w", height=20).pack(fill="x", padx=1.5 * SP, pady=(SP, 0))
            ctk.CTkLabel(row, text=f"{ftype}  ·  {when}  ·  {have} of {len(DOCUMENTS)} docs", font=font(12),
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
        if folder != self.selected:
            self.note = None  # result messages belong to one client
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

        ctk.CTkLabel(d, text=shorten(folder.name, 40) + f"   ·   {self.client_type_of.get(folder, '')}".rstrip(" ·"),
                     font=font(18, "bold"), text_color=TEXT, anchor="w") \
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
        # two equal columns so the buttons always fit the panel
        acts = ctk.CTkFrame(d, fg_color="transparent")
        acts.grid(row=4, column=0, sticky="ew", padx=p)
        acts.grid_columnconfigure((0, 1), weight=1, uniform="acts")
        buttons = [
            ctk.CTkButton(acts, text="Request MVR", height=36, font=font(13, "bold"),
                          fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=lambda: MvrDialog(self, folder)),
            self.secondary_button(acts, "Email client…", lambda: EmailDialog(self, folder)),
            self.secondary_button(acts, "Import DASH", lambda: ImportDashDialog(self, folder)),
            self.secondary_button(acts, "Refill consent", lambda: self.refill(folder),
                                  state="normal" if docs["DASH report"] else "disabled"),
            self.secondary_button(acts, "Open folder", lambda: os.startfile(folder)),
        ]
        for i, b in enumerate(buttons):
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, SP) if i % 2 == 0 else 0, pady=(0, SP))
        self.detail_msg = ctk.CTkLabel(d, text="", font=font(13), text_color=SUCCESS,
                                       justify="left", anchor="w", wraplength=380)
        self.detail_msg.grid(row=6, column=0, sticky="w", padx=p, pady=(1.5 * SP, 0))
        if self.note and self.note[0] == folder:
            self.detail_msg.configure(text=self.note[1], text_color=self.note[2])

    def refill(self, folder, prefix=""):
        try:
            _, drivers = fill(folder, template=self.cfg["consent_template"])
        except Exception as e:
            self.show_note(folder, f"{prefix}Could not refill consent: {e}", DANGER)
            return
        self.refresh_list(keep_scroll=True)
        self.select(folder)
        names = "\n".join(f"{n}   {d}" for n, d in drivers)
        self.show_note(folder, f"{prefix}✓ Consent refilled with:\n{names}", SUCCESS)

    def show_note(self, folder, text, color):
        """Result message under the actions; survives list refreshes."""
        self.note = (folder, text, color)
        if self.selected == folder:
            self.detail_msg.configure(text=text, text_color=color)


def ensure_desktop_shortcut():
    """Packaged exe only: add a desktop shortcut the first time it runs."""
    if not getattr(sys, "frozen", False):
        return
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        lnk = Path(shell.SpecialFolders("Desktop")) / "Client Intake.lnk"
        if lnk.exists():
            return
        sc = shell.CreateShortcut(str(lnk))
        sc.TargetPath = sys.executable
        sc.WorkingDirectory = str(Path(sys.executable).parent)
        sc.IconLocation = sys.executable
        sc.Save()
    except Exception:
        pass  # a missing shortcut must never stop the app


def selftest():
    """`ClientIntake.exe --selftest`: check PDF and email features without the UI or settings.

    Writes the result to %TEMP%\\ClientIntake-selftest.txt.
    """
    import tempfile
    import traceback
    from fill_consent import read_consent
    lines = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "TEST CLIENT"
            folder.mkdir()
            out, _ = fill(folder, "A12345678901234")
            lines.append(f"consent: {read_consent(out)}")
            msg = mvr_email.build_signature({"sig_name": "Test"})
            lines.append(f"signature: {len(msg)} chars")
            eml_body = mvr_email.build_body_html("TEST", "CLIENT", "A1234-56789-01234", "", "")
            lines.append(f"email body: {len(eml_body)} chars")
            lines.append(f"downloads: {dash_import.downloads_dir()}")
            for arg in sys.argv[2:]:  # optional DASH report(s) to read
                lines.append(f"dash {Path(arg).name}: {read_dash(Path(arg))}")
        lines.append("OK")
    except Exception:
        lines.append(traceback.format_exc())
    Path(tempfile.gettempdir(), "ClientIntake-selftest.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    ensure_desktop_shortcut()
    App().mainloop()
