"""Client Intake - desktop app for new client setup.

Creates the client folder, fills the consent form, and shows which
documents (Consent, DASH, Quote, MVR) each client folder already has.
"""
import datetime
import os
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
import mvr_email
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


def font(size=14, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Settings")
        self.geometry("560x600")
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

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=12, column=0, sticky="e", padx=2 * SP, pady=2 * SP)
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
                      email_app=self.mail_var.get())
        ctk.set_appearance_mode(self.app.cfg["appearance"])
        self.app.on_settings_changed()
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
        ctk.CTkLabel(body, text="Added to the bottom of MVR request emails (New Outlook).\n"
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
        email = dict(
            to=self.app.cfg["mvr_to"], cc=self.app.cfg.get("mvr_cc", ""),
            subject=mvr_email.build_subject(v["dln"], v["first"], v["last"]),
            body_html=mvr_email.build_body_html(v["first"], v["last"], v["dln"], v["phone"], v["email"]),
            attachments=[f for var, f in self.attach if var.get()])
        classic = self.app.cfg.get("email_app") == "Classic Outlook"
        try:
            if classic:
                mail = mvr_email.create_outlook_draft(display=display, **email)
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
        self.geometry("1100x680")
        self.minsize(980, 600)
        self.configure(fg_color=BG)
        self.selected = None
        self.note = None
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
            config.update(self.cfg, clients_root=str(Path(p)))
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

    # ---------- updates ----------
    def _check_update(self):
        try:
            found = updater.check_for_update()
        except Exception:
            return  # offline or GitHub unreachable: try again next launch
        if found:
            self.after(0, lambda: self._show_update(found))

    def _show_update(self, found):
        self.pending_update = found
        self.update_text.configure(text=f"Version {found['version']} is available")
        self.update_bar.pack(side="right", padx=(0, 2 * SP))

    def install_update(self):
        self.update_btn.configure(state="disabled", text="Downloading…")
        self.update_text.configure(text=f"Updating to {self.pending_update['version']}…")

        def progress(fraction):
            self.after(0, lambda: self.update_btn.configure(text=f"{int(fraction * 100)}%"))

        def work():
            try:
                updater.download_and_install(self.pending_update, progress)
            except Exception as e:
                self.after(0, lambda: (self.update_text.configure(text=f"Update failed: {e}", text_color=DANGER),
                                       self.update_btn.configure(state="normal", text="Try again")))
                return
            self.after(0, self.destroy)  # the update script waits for this window to close

        threading.Thread(target=work, daemon=True).start()

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
        acts2 = ctk.CTkFrame(d, fg_color="transparent")
        acts2.grid(row=5, column=0, sticky="ew", padx=p, pady=(SP, 0))
        self.secondary_button(acts2, "Import DASH from Downloads", lambda: ImportDashDialog(self, folder)) \
            .pack(side="left", padx=(0, SP))
        refill = self.secondary_button(acts2, "Refill consent from DASH", lambda: self.refill(folder),
                                       state="normal" if docs["DASH report"] else "disabled")
        refill.pack(side="left")
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
