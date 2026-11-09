"""Broker sign-in and profile pages (see brokers.py)."""
import sys
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import brokers
from panel import Panel


def _ui(app):
    return sys.modules[type(app).__module__]


def _hide_back(page):
    """The sign-in page is a gate: no ← Back button."""
    try:
        bar = page._wrapper.winfo_children()[0]
        bar.winfo_children()[0].pack_forget()
    except Exception:
        pass


class SignInPage(Panel):
    """Pick your name, enter your PIN. Shown when the app starts."""
    FORM = True

    def __init__(self, app, on_done=None):
        super().__init__(app)
        self.app, self.on_done = app, on_done
        ui = self.ui = _ui(app)
        self.title("Sign in")
        self.geometry("480x420")
        _hide_back(self)
        names = brokers.names(app.cfg)
        last = app.cfg.get("current_broker")
        body = ctk.CTkFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
        body.pack(fill="both", expand=True, padx=2 * ui.SP, pady=2 * ui.SP)
        body.grid_columnconfigure(0, weight=1)
        p = 3 * ui.SP
        ctk.CTkLabel(body, text="Who is using Client Intake?", font=ui.font(18, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, sticky="w", padx=p, pady=(p, 0))
        ctk.CTkLabel(body, text="Your details (name, branch number, signature) are filled in for you.",
                     font=ui.font(12), text_color=ui.MUTED).grid(row=1, column=0, sticky="w", padx=p)
        ctk.CTkLabel(body, text="Broker", font=ui.font(13, "bold"), text_color=ui.TEXT) \
            .grid(row=2, column=0, sticky="w", padx=p, pady=(1.5 * ui.SP, ui.SP / 2))
        self.who = tk.StringVar(value=last if last in names else names[0])
        ctk.CTkOptionMenu(body, values=names, variable=self.who, height=38, font=ui.font(14), dropdown_font=ui.font(14),
                          fg_color=ui.SURFACE_ALT, button_color=ui.SURFACE_ALT, button_hover_color=ui.BORDER,
                          text_color=ui.TEXT, command=lambda _: self.changed()) \
            .grid(row=3, column=0, sticky="ew", padx=p)
        self.pin_label = ctk.CTkLabel(body, text="PIN", font=ui.font(13, "bold"), text_color=ui.TEXT)
        self.pin_label.grid(row=4, column=0, sticky="w", padx=p, pady=(1.5 * ui.SP, ui.SP / 2))
        self.pin = ctk.CTkEntry(body, show="•", height=38, font=ui.font(14), border_color=ui.BORDER)
        self.pin.grid(row=5, column=0, sticky="ew", padx=p)
        self.error = ctk.CTkLabel(body, text="", font=ui.font(12), text_color=ui.DANGER, anchor="w")
        self.error.grid(row=6, column=0, sticky="w", padx=p, pady=(ui.SP, 0))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=7, column=0, sticky="ew", padx=p, pady=(ui.SP, p))
        ctk.CTkButton(row, text="Sign in", width=140, height=42, font=ui.font(14, "bold"), fg_color=ui.PRIMARY,
                      hover_color=ui.PRIMARY_HOVER, command=self.submit).pack(side="right")
        app.secondary_button(row, "New broker", self.new_broker, width=120, height=42).pack(side="left")
        self.pin.bind("<Return>", lambda e: self.submit())
        self.changed()
        self.after(150, self.pin.focus_set)

    def changed(self):
        locked = brokers.has_pin(brokers.profiles(self.app.cfg).get(self.who.get()) or {})
        self.pin_label.configure(text="PIN" if locked else "No PIN for this profile - just sign in")
        self.pin.configure(state="normal" if locked else "disabled")
        self.error.configure(text="")

    def submit(self):
        profile = brokers.profiles(self.app.cfg).get(self.who.get()) or {}
        if not brokers.check_pin(profile, self.pin.get()):
            self.pin.delete(0, "end")
            self.error.configure(text="That PIN doesn't match.")
            return
        brokers.sign_in(self.app.cfg, self.who.get())
        self.finish()

    def new_broker(self):
        self.destroy()
        ProfilePage(self.app, None, on_done=self.on_done, first=True)

    def finish(self):
        app, done = self.app, self.on_done
        self.destroy()
        app.broker_changed()
        if done:
            done()


class ProfilePage(Panel):
    """Create or edit a broker profile (two columns so it fits the window without scrolling)."""

    def __init__(self, app, name=None, on_done=None, first=False):
        super().__init__(app)
        self.app, self.name, self.on_done, self.first = app, name, on_done, first
        ui = self.ui = _ui(app)
        editing = bool(name)
        self.title("Broker profile" if editing else "New broker profile")
        self.geometry("1000x700")
        if first and not brokers.names(app.cfg):
            _hide_back(self)
        profile = dict(brokers.profiles(app.cfg).get(name) or {}) if editing else self.starting_values(app)
        body = ctk.CTkFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
        body.pack(fill="both", expand=True, padx=2 * ui.SP, pady=(2 * ui.SP, 0))
        body.grid_columnconfigure((0, 1, 2), weight=1, uniform="cols")
        p = 2 * ui.SP
        ctk.CTkLabel(body, text=("Your details are saved on this computer only. They fill the email signature, the MVR "
                                 "request and the broker name / branch number on forms such as the commercial application."),
                     font=ui.font(12), text_color=ui.MUTED, justify="left", wraplength=880, anchor="w") \
            .grid(row=0, column=0, columnspan=3, sticky="w", padx=p, pady=(p, 0))

        def field(i, label, widget_factory):
            row, col = 1 + 2 * (i // 3), i % 3
            ctk.CTkLabel(body, text=label, font=ui.font(13, "bold"), text_color=ui.TEXT) \
                .grid(row=row, column=col, sticky="w", padx=p, pady=(1.5 * ui.SP, ui.SP / 2))
            w = widget_factory()
            w.grid(row=row + 1, column=col, sticky="ew", padx=p)
            return w

        self.entries = {}
        for i, (key, label, hint) in enumerate(brokers.FIELDS):
            e = field(i, label + (" *" if key == "name" else ""), lambda hint=hint: ctk.CTkEntry(
                body, height=36, font=ui.font(13), border_color=ui.BORDER, placeholder_text=hint))
            if profile.get(key):
                e.insert(0, profile[key])
            self.entries[key] = e
        n = len(brokers.FIELDS)
        had_pin = brokers.has_pin(profile)
        self.pin = field(n, "New PIN" + (" (empty = keep the current one)" if had_pin else " (optional)"),
                         lambda: ctk.CTkEntry(body, show="•", height=36, font=ui.font(13), border_color=ui.BORDER))
        self.pin2 = field(n + 1, "Repeat the PIN",
                          lambda: ctk.CTkEntry(body, show="•", height=36, font=ui.font(13), border_color=ui.BORDER))
        self.no_pin = tk.BooleanVar(value=False)
        if had_pin:
            ctk.CTkCheckBox(body, text="Remove the PIN", variable=self.no_pin, font=ui.font(13), text_color=ui.TEXT,
                            fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER) \
                .grid(row=1 + 2 * ((n + 2) // 3 + 1), column=0, sticky="w", padx=p, pady=(ui.SP, p))
        self.error = ctk.CTkLabel(self, text="", font=ui.font(13), text_color=ui.DANGER, anchor="w", wraplength=500, justify="left")
        self.error.pack(fill="x", padx=3 * ui.SP)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=2 * ui.SP, pady=2 * ui.SP)
        ctk.CTkButton(btns, text="Save", width=110, height=40, font=ui.font(14, "bold"), fg_color=ui.PRIMARY,
                      hover_color=ui.PRIMARY_HOVER, command=self.save).pack(side="right")
        if editing:
            app.secondary_button(btns, "Delete profile", self.delete, width=130, height=40).pack(side="left")

    @staticmethod
    def starting_values(app):
        """A first profile starts from what this computer already has (signature, MVR addresses)."""
        cfg = app.cfg
        if brokers.names(cfg):                       # another broker's profile starts empty
            return {}
        import mvr_email
        out = dict(mvr_email.signature_values(cfg))  # the signature as it is today (incl. the owner's defaults)
        out.update(mvr_to=cfg.get("mvr_to", ""), mvr_cc=cfg.get("mvr_cc", ""))
        return out

    def save(self):
        values = {k: e.get().strip() for k, e in self.entries.items()}
        name = values["name"]
        if not name:
            self.error.configure(text="Enter your name.")
            return
        if name != self.name and name in brokers.profiles(self.app.cfg):
            self.error.configure(text=f"There is already a broker called {name}.")
            return
        pin, pin2 = self.pin.get(), self.pin2.get()
        if pin != pin2:
            self.error.configure(text="The two PINs are different.")
            return
        if pin and (len(pin) < 4):
            self.error.configure(text="Use a PIN of at least 4 characters.")
            return
        keep = None if not pin else pin
        if self.no_pin.get():
            keep = ""
        brokers.save_profile(self.app.cfg, values, pin=keep, old_name=self.name)
        app, done, first = self.app, self.on_done, self.first
        if first or self.app.cfg.get("current_broker") in ("", None):
            brokers.sign_in(app.cfg, name)
        self.destroy()
        app.broker_changed()
        if done:
            done()

    def delete(self):
        if messagebox.askyesno("Delete profile", f"Delete the profile of {self.name}? Client files are not touched.",
                               parent=self.app):
            brokers.delete_profile(self.app.cfg, self.name)
            app = self.app
            self.destroy()
            app.broker_changed()
            app.start_sign_in()
