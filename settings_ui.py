"""Settings page and the Setup guide (for a broker who is new to the app).

Settings is grouped into plain cards (where the files are, email, how the app looks, extras), every setting has one
sentence saying what it is for, and Save / Cancel stay at the bottom of the window instead of at the end of a long scroll.
The Setup guide lists the few things a new broker has to do once (profile, Clients folder, MVR address ...) with a button
for each, and ticks them off by itself. It opens by itself the first time, and a banner under the top bar stays until
everything is done (or the broker dismisses it).
"""
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import ui_kit

import brokers
import config
from panel import Panel


def _ui(app):
    return sys.modules[type(app).__module__]


def _card(parent, ui, title=None, row=0):
    if title:
        ctk.CTkLabel(parent, text=title.upper(), font=ui.font(12, "bold"), text_color=ui.MUTED, anchor="w") \
            .grid(row=row, column=0, sticky="w", padx=ui.SP, pady=(2 * ui.SP, ui.SP / 2))
    card = ctk.CTkFrame(parent, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
    card.grid(row=row + 1, column=0, sticky="ew", padx=ui.SP)
    card.grid_columnconfigure(0, weight=1, minsize=700)
    return card


def _setting(card, ui, index, title, help_text, build):
    """One setting: bold name, a sentence about it, then its control (build(frame) fills the frame).
    Four grid rows each (separator, name, help, control) so nothing is drawn on top of anything else."""
    base = 4 * index
    if index:
        ctk.CTkFrame(card, height=1, fg_color=ui.BORDER).grid(row=base, column=0, sticky="ew", padx=2 * ui.SP)
    ctk.CTkLabel(card, text=title, font=ui.font(14, "bold"), text_color=ui.TEXT, anchor="w")         .grid(row=base + 1, column=0, sticky="w", padx=2 * ui.SP, pady=(1.5 * ui.SP, 0))
    ctk.CTkLabel(card, text=help_text, font=ui.font(12), text_color=ui.MUTED, anchor="w", justify="left",
                 wraplength=680).grid(row=base + 2, column=0, sticky="w", padx=2 * ui.SP, pady=(2, ui.SP))
    box = ctk.CTkFrame(card, fg_color="transparent")
    box.grid(row=base + 3, column=0, sticky="ew", padx=2 * ui.SP, pady=(0, 1.5 * ui.SP))
    box.grid_columnconfigure(0, weight=1)
    build(box)


# ============================================================ settings
class SettingsDialog(Panel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        ui = self.ui = _ui(app)
        self.title("Settings")
        self.geometry("1000x800")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.root_var = tk.StringVar(value=app.cfg["clients_root"])
        self.tpl_var = tk.StringVar(value=app.cfg["consent_template"])
        self.mode_var = tk.StringVar(value=app.cfg["appearance"])
        self.size_var = tk.StringVar(value=app.cfg.get("text_size") or "Large")
        self.to_var = tk.StringVar(value=app.cfg["mvr_to"])
        self.cc_var = tk.StringVar(value=app.cfg["mvr_cc"])
        self.mail_var = tk.StringVar(value=app.cfg.get("email_app", "New Outlook"))
        self.types_var = tk.StringVar(value=app.cfg.get("client_types", ""))
        self.autosave_var = tk.BooleanVar(value=app.cfg.get("mvr_autosave", True))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        page = ctk.CTkFrame(scroll, fg_color="transparent")
        page.grid(row=0, column=0, sticky="n")           # one readable column, not stretched across a wide window
        page.grid_columnconfigure(0, weight=1)

        # ---- you
        c = _card(page, ui, "You", 0)
        broker = brokers.current(app.cfg)
        _setting(c, ui, 0, "Your broker profile",
                 "Your name, branch number and email signature. They fill in forms and emails for you. Each broker has "
                 "their own profile on this computer.",
                 lambda f: self.row_buttons(f, broker.get("name") or "No profile yet", [
                     ("Edit my profile" if broker else "Create my profile", self.edit_profile)]))
        _setting(c, ui, 1, "Setup guide", "The short list of things to set up once. It ticks them off for you.",
                 lambda f: self.row_buttons(f, "", [("Open the setup guide", self.open_guide)]))

        # ---- files
        c = _card(page, ui, "Your files", 2)
        _setting(c, ui, 0, "Clients folder",
                 "The folder that holds all your clients (inside it: Auto, Home, Tenant, Commercial). Usually on the "
                 "shared drive. Choose it once.",
                 lambda f: self.path_row(f, self.root_var, True))
        _setting(c, ui, 1, "Auto-save MVRs",
                 "When an MVR arrives in your Downloads folder, the app files it into the right client's folder for you.",
                 lambda f: ctk.CTkSwitch(f, text="On", variable=self.autosave_var, font=ui.font(13), text_color=ui.TEXT,
                                         progress_color=ui.ACCENT).grid(row=0, column=0, sticky="w"))

        # ---- email
        c = _card(page, ui, "Email", 4)
        _setting(c, ui, 0, "Email program",
                 "Which Outlook the app uses to make email drafts. Not sure? Pick New Outlook; if drafts do not open, try "
                 "Classic Outlook.",
                 lambda f: ui_kit.Segmented(f, values=["New Outlook", "Classic Outlook"], variable=self.mail_var,
                                                  font=ui.font(13), height=34).grid(row=0, column=0, sticky="w"))
        _setting(c, ui, 1, "MVR requests go to",
                 "The email address that receives your MVR requests (usually your branch manager).",
                 lambda f: self.entry_row(f, self.to_var, "name@brokerage.ca"))
        _setting(c, ui, 2, "MVR requests copy to", "Optional. Several addresses: separate them with a semicolon (;).",
                 lambda f: self.entry_row(f, self.cc_var, "optional"))
        _setting(c, ui, 3, "Email signature",
                 "The details at the bottom of every email the app makes. They come from your profile; change them here.",
                 lambda f: self.row_buttons(f, "", [("Edit signature…", lambda: ui.SignatureDialog(self, app))]))

        # ---- look
        c = _card(page, ui, "How the app looks", 6)
        _setting(c, ui, 0, "Appearance", "Light, dark, or follow Windows.",
                 lambda f: ui_kit.Segmented(f, values=["System", "Light", "Dark"], variable=self.mode_var,
                                                  font=ui.font(13), height=34).grid(row=0, column=0, sticky="w"))
        _setting(c, ui, 1, "Text size", "Make everything bigger if the text is hard to read.",
                 lambda f: ui_kit.Segmented(f, values=list(ui.TEXT_SIZES), variable=self.size_var,
                                                  font=ui.font(13), height=34).grid(row=0, column=0, sticky="w"))

        # ---- advanced
        c = _card(page, ui, "Advanced", 8)
        _setting(c, ui, 0, "Client types",
                 "The sub-folders inside the Clients folder, separated by commas. Leave as it is unless your folders are "
                 "named differently.",
                 lambda f: self.entry_row(f, self.types_var, "Auto, Home, Tenant, Commercial"))
        _setting(c, ui, 1, "Consent form template",
                 "Leave empty to use the built-in WellCare consent form. Only fill this in to use your own PDF.",
                 lambda f: self.path_row(f, self.tpl_var, False))
        if app.cfg.get("sample_prev_root") is not None:
            text, cmd = "Back to my Clients folder", lambda: (self.destroy(), app.leave_sample())
        else:
            text, cmd = "Try with sample clients", lambda: (self.destroy(), app.use_sample())
        _setting(c, ui, 2, "Sample clients",
                 "Fills the app with made-up clients so you can try it. Your real clients are not touched.",
                 lambda f: self.row_buttons(f, "", [(text, cmd)]))
        ctk.CTkFrame(page, fg_color="transparent", height=2 * ui.SP).grid(row=20, column=0)

        # ---- Save / Cancel stay in view
        bar = ctk.CTkFrame(self, fg_color=ui.SURFACE, corner_radius=0, border_width=0)
        bar.grid(row=1, column=0, sticky="ew")
        ctk.CTkFrame(bar, height=1, fg_color=ui.BORDER).pack(fill="x")
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=3 * ui.SP, pady=1.5 * ui.SP)
        ctk.CTkButton(inner, text="Save settings", width=140, height=40, font=ui.font(14, "bold"), fg_color=ui.PRIMARY,
                      hover_color=ui.PRIMARY_HOVER, command=self.save).pack(side="right")
        app.secondary_button(inner, "Cancel", self.destroy, width=100, height=40).pack(side="right", padx=ui.SP)
        self.bind("<Escape>", lambda e: self.destroy())

    # ----- small builders
    def row_buttons(self, frame, text, buttons):
        ui = self.ui
        col = 0
        if text:
            ctk.CTkLabel(frame, text=text, font=ui.font(13), text_color=ui.TEXT, anchor="w").grid(row=0, column=0, sticky="w")
            col = 1
            frame.grid_columnconfigure(0, weight=1)
        for i, (label, command) in enumerate(buttons):
            self.app.secondary_button(frame, label, command, width=170, height=36).grid(row=0, column=col + i, sticky="e", padx=(ui.SP, 0))

    def entry_row(self, frame, var, placeholder):
        ctk.CTkEntry(frame, textvariable=var, height=38, font=self.ui.font(13), placeholder_text=placeholder) \
            .grid(row=0, column=0, sticky="ew")

    def path_row(self, frame, var, folder):
        ui = self.ui
        ctk.CTkEntry(frame, textvariable=var, height=38, font=ui.font(13)).grid(row=0, column=0, sticky="ew", padx=(0, ui.SP))

        def browse():
            if folder:
                p = filedialog.askdirectory(parent=self, title="Choose the Clients folder", initialdir=var.get() or None)
            else:
                p = filedialog.askopenfilename(parent=self, title="Choose a consent form (PDF)", filetypes=[("PDF", "*.pdf")])
            if p:
                var.set(str(Path(p)))
        self.app.secondary_button(frame, "Browse…", browse, width=110, height=38).grid(row=0, column=1)

    def edit_profile(self):
        import broker_ui
        name = self.app.cfg.get("current_broker") or None
        broker_ui.ProfilePage(self.app, name, first=not name)

    def open_guide(self):
        SetupGuidePage(self.app)

    def save(self):
        ui, app = self.ui, self.app
        config.update(app.cfg,
                      clients_root=self.root_var.get().strip(),
                      consent_template=self.tpl_var.get().strip(),
                      appearance=self.mode_var.get(),
                      text_size=self.size_var.get(),
                      mvr_to=self.to_var.get().strip(),
                      mvr_cc=self.cc_var.get().strip(),
                      email_app=self.mail_var.get(),
                      mvr_autosave=self.autosave_var.get(),
                      client_types=", ".join(ui.parse_types(self.types_var.get())) or config.DEFAULTS["client_types"])
        ctk.set_appearance_mode(app.cfg["appearance"])
        ctk.set_widget_scaling(ui.TEXT_SIZES.get(app.cfg["text_size"], 1.15))
        app.on_settings_changed()
        app.reload_types()
        app.refresh_setup_bar()
        self.destroy()


# ============================================================ setup guide
def setup_steps(app):
    """[(key, title, help, done, button text)] - what a new broker has to do once."""
    cfg = app.cfg
    broker = brokers.current(cfg)
    root = cfg.get("clients_root") or ""
    return [
        ("profile", "Create your broker profile",
         "Your name and branch number. They fill in forms (like the commercial application) so you never retype them.",
         bool(broker.get("name") and broker.get("branch_no")), "Open my profile"),
        ("folder", "Choose your Clients folder",
         "The shared folder where your clients' files are kept. Ask your branch manager if you do not know where it is.",
         bool(root) and Path(root).exists(), "Choose the folder…"),
        ("signature", "Add your email details",
         "Your phone and email go at the bottom of every email the app makes for you.",
         bool(broker.get("phone") and broker.get("email")), "Open my profile"),
        ("mvr", "Set where MVR requests go",
         "The email address of the person who orders MVRs for you (usually your branch manager).",
         bool((cfg.get("mvr_to") or "").strip()), "Open my profile"),
    ]


def setup_left(app):
    return [s for s in setup_steps(app) if not s[3]]


class SetupGuidePage(Panel):
    """A checklist for a new broker: each item says why, shows whether it is done, and has a button that does it."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        ui = self.ui = _ui(app)
        self.title("Setup guide")
        self.geometry("1000x780")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.page = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.page.grid(row=0, column=0, sticky="n")
        self.page.grid_columnconfigure(0, weight=1)
        self.bind("<Escape>", lambda e: self.destroy())
        config.update(app.cfg, setup_seen=True)
        self.draw()

    def draw(self):
        ui, app = self.ui, self.app
        for w in self.page.winfo_children():
            w.destroy()
        steps = setup_steps(app)
        left = [s for s in steps if not s[3]]
        ctk.CTkLabel(self.page, text="Welcome to Client Intake", font=ui.font(22, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=0, column=0, sticky="w", padx=ui.SP, pady=(ui.SP, 0))
        ctk.CTkLabel(self.page, text=("Four quick things to set up once. After that the app fills your details in for you."
                                      if left else "Everything is set up. You are ready to work."),
                     font=ui.font(14), text_color=ui.MUTED, anchor="w") \
            .grid(row=1, column=0, sticky="w", padx=ui.SP, pady=(2, 2 * ui.SP))
        for i, (key, title, help_text, done, button) in enumerate(steps):
            card = ctk.CTkFrame(self.page, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
            card.grid(row=2 + i, column=0, sticky="ew", padx=ui.SP, pady=(0, ui.SP))
            card.grid_columnconfigure(1, weight=1, minsize=480)
            badge = ctk.CTkFrame(card, width=36, height=36, corner_radius=18,
                                 fg_color=("#15803D", "#1B8F46") if done else ("#64748B", "#475569"))
            badge.grid(row=0, column=0, rowspan=2, padx=(2 * ui.SP, ui.SP), pady=2 * ui.SP, sticky="n")
            badge.grid_propagate(False)
            badge.grid_rowconfigure(0, weight=1)
            badge.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(badge, text="✓" if done else str(i + 1), font=ui.font(15, "bold"), text_color="#FFFFFF",
                         fg_color="transparent").grid(row=0, column=0)
            ctk.CTkLabel(card, text=title, font=ui.font(15, "bold"), text_color=ui.TEXT, anchor="w") \
                .grid(row=0, column=1, sticky="sw", pady=(2 * ui.SP, 0))
            ctk.CTkLabel(card, text=help_text, font=ui.font(13), text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=480).grid(row=1, column=1, sticky="nw", pady=(2, 2 * ui.SP))
            if done:
                ctk.CTkLabel(card, text="Done", font=ui.font(13, "bold"), text_color=ui.SUCCESS) \
                    .grid(row=0, column=2, rowspan=2, padx=2 * ui.SP)
            else:
                first = key == next(s[0] for s in steps if not s[3])        # only the next thing to do is red
                kw = {} if first else dict(fg_color="transparent", border_width=1, border_color=ui.BORDER,
                                           text_color=ui.TEXT, hover_color=ui.SURFACE_ALT)
                ctk.CTkButton(card, text=button, width=170, height=38, font=ui.font(13, "bold"),
                              command=lambda k=key: self.do(k), **kw).grid(row=0, column=2, rowspan=2, padx=2 * ui.SP)
        tips = ctk.CTkFrame(self.page, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
        tips.grid(row=2 + len(steps), column=0, sticky="ew", padx=ui.SP, pady=(ui.SP, 0))
        ctk.CTkLabel(tips, text="HOW THE APP WORKS", font=ui.font(12, "bold"), text_color=ui.MUTED, anchor="w") \
            .grid(row=0, column=0, sticky="w", padx=2 * ui.SP, pady=(2 * ui.SP, ui.SP / 2))
        lines = ["+ New client creates the client's folder and fills the consent form.",
                 "Click a client to see the Next step card: it tells you what to do and has the button to do it.",
                 "Tracker shows what is due (to-dos, renewals, policies). Rules searches the underwriting notes.",
                 "Settings has everything on this page and more. You can open this guide again from Settings."]
        for i, line in enumerate(lines, start=1):
            ctk.CTkLabel(tips, text="•  " + line, font=ui.font(13), text_color=ui.TEXT, anchor="w", justify="left",
                         wraplength=620).grid(row=i, column=0, sticky="w", padx=2 * ui.SP, pady=(0, ui.SP / 2))
        ctk.CTkFrame(tips, fg_color="transparent", height=ui.SP).grid(row=len(lines) + 1, column=0)
        ctk.CTkButton(self.page, text="Close" if left else "Start working", width=170, height=42,
                      font=ui.font(14, "bold"), fg_color=ui.PRIMARY if not left else ("#64748B", "#475569"),
                      hover_color=ui.PRIMARY_HOVER, command=self.destroy).grid(
            row=3 + len(steps), column=0, sticky="e", padx=ui.SP, pady=2 * ui.SP)

    def do(self, key):
        app = self.app
        if key == "folder":
            p = filedialog.askdirectory(parent=app, title="Choose your Clients folder")
            if p:
                config.update(app.cfg, clients_root=str(Path(p)))
                app.on_settings_changed()
                self.draw()
            return
        import broker_ui
        name = app.cfg.get("current_broker") or None
        broker_ui.ProfilePage(app, name, first=not name, on_done=self.draw_if_alive)

    def draw_if_alive(self):
        if self.winfo_exists():
            self.draw()

    def destroy(self):
        app = self.app
        super().destroy()
        try:
            app.refresh_setup_bar()
        except Exception:
            pass
