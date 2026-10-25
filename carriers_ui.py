"""Carrier pages: the underwriter call log, and carrier info (contacts, payment terms, where to
submit, tips, WellCare's payment options for clients).

When the quote has refer messages the broker calls the underwriter to confirm the client is
eligible, and must keep a note: date and time, who they spoke to, why, and the result. Calls
are saved in the client's tracking.json ("uw_calls") and tick the checklist step.
Carrier data comes from carriers.json in the notes folder (see carriers.py).
"""
import datetime
import os
import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

import carriers
import checklist
import records
from panel import Panel

WARN = ("#B45309", "#FBBF24")
WELLCARE = "WellCare - how clients pay"


def _ui(app):
    return sys.modules[type(app).__module__]


def copy(app, text, button=None):
    app.clipboard_clear()
    app.clipboard_append(text)
    if button is not None:
        old = button.cget("text")
        button.configure(text="Copied ✓")
        button.after(1200, lambda: button.winfo_exists() and button.configure(text=old))


def contact_rows(parent, app, lines, row=0):
    """One row per contact line; phones and emails get Copy (and Email) buttons. Returns next row."""
    ui = _ui(app)
    small = dict(height=26, font=ui.font(12), fg_color="transparent", border_width=1, border_color=ui.BORDER,
                 text_color=ui.TEXT, hover_color=ui.SURFACE_ALT)
    for line in lines:
        ctk.CTkLabel(parent, text=line, font=ui.font(13), text_color=ui.TEXT, anchor="w", justify="left",
                     wraplength=380).grid(row=row, column=0, sticky="w", padx=(2 * ui.SP, ui.SP), pady=2)
        btns = ctk.CTkFrame(parent, fg_color="transparent")
        btns.grid(row=row, column=1, sticky="e", padx=(0, 2 * ui.SP))
        for kind, value, _ in carriers.contacts([line]):
            b = ctk.CTkButton(btns, text="Copy", width=56, **small)
            b.configure(command=lambda v=value, b=b: copy(app, v, b))
            b.pack(side="left", padx=(4, 0))
            if kind == "email":
                ctk.CTkButton(btns, text="Email", width=56, command=lambda v=value: os.startfile(f"mailto:{v}"),
                              **small).pack(side="left", padx=(4, 0))
        row += 1
    return row


def _card(parent, app, title, row, column=0, columnspan=1):
    ui = _ui(app)
    card = ctk.CTkFrame(parent, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
    card.grid(row=row, column=column, columnspan=columnspan, sticky="new", padx=ui.SP, pady=(0, 2 * ui.SP))
    card.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(card, text=title.upper(), font=ui.font(11, "bold"), text_color=ui.MUTED, anchor="w") \
        .grid(row=0, column=0, columnspan=2, sticky="w", padx=2 * ui.SP, pady=(1.5 * ui.SP, ui.SP / 2))
    return card


def _pairs(card, app, pairs, row=1):
    ui = _ui(app)
    card.grid_columnconfigure(0, weight=0, minsize=150)
    card.grid_columnconfigure(1, weight=1)
    for key, value in pairs:
        if not value:
            continue
        ctk.CTkLabel(card, text=key, font=ui.font(13), text_color=ui.MUTED, anchor="nw") \
            .grid(row=row, column=0, sticky="nw", padx=(2 * ui.SP, ui.SP), pady=2)
        ctk.CTkLabel(card, text=value, font=ui.font(13), text_color=ui.TEXT, anchor="nw", justify="left",
                     wraplength=330).grid(row=row, column=1, sticky="nw", padx=(0, 2 * ui.SP), pady=2)
        row += 1
    return row


def _bottom(card, row, app):
    ctk.CTkFrame(card, fg_color="transparent", height=_ui(app).SP).grid(row=row, column=0)


def quote_carriers(app, folder):
    """{known carrier name: [refer messages]} for the carriers on the client's newest quote."""
    data = carriers.load(app.cfg)
    kind = app.client_type_of.get(folder, "")
    refers = checklist.quote_refers(folder, _ui(app).find_docs(folder, kind)) or {}
    out = {}
    for name, msgs in refers.items():
        out.setdefault(carriers.find(data, name) or name, []).extend(msgs)
    return out


def missing_file(parent, app, row=0):
    ui = _ui(app)
    ctk.CTkLabel(parent, text=f"Carrier details not found.\n\nThe app reads them from {carriers.FILE} in the "
                              f"Rules notes folder:\n{carriers.path(app.cfg)}\n\nCopy the file there, or point the "
                              "Rules tab at the folder that has it (Notes folder…).",
                 font=ui.font(13), text_color=ui.MUTED, justify="left", wraplength=560) \
        .grid(row=row, column=0, sticky="w", padx=3 * ui.SP, pady=3 * ui.SP)


# ---------------------------------------------------------------- carrier info
class CarrierInfoPage(Panel):
    def __init__(self, app, folder=None, carrier=None):
        super().__init__(app)
        self.app, ui = app, _ui(app)
        self.title("Carriers & payments")
        self.geometry("1180x840")
        self.data = carriers.load(app.cfg)
        names = sorted(self.data["carriers"])
        on_quote = list(quote_carriers(app, folder)) if folder else []
        default = carrier or next((n for n in on_quote if n in names), None) or WELLCARE
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=ui.SP, pady=(0, 2 * ui.SP))
        ctk.CTkLabel(top, text="Carrier", font=ui.font(13, "bold"), text_color=ui.TEXT).pack(side="left")
        self.choice = tk.StringVar(value=default)
        ctk.CTkOptionMenu(top, values=[WELLCARE] + names, variable=self.choice, width=280, height=34,
                          font=ui.font(13), fg_color=ui.SURFACE_ALT, button_color=ui.PRIMARY,
                          button_hover_color=ui.PRIMARY_HOVER, text_color=ui.TEXT,
                          command=lambda _: self.show()).pack(side="left", padx=ui.SP)
        if on_quote:
            ctk.CTkLabel(top, text="On the quote: " + ", ".join(on_quote), font=ui.font(12),
                         text_color=ui.MUTED).pack(side="left", padx=ui.SP)
        self.body = None
        self.show()

    def show(self):
        app, ui = self.app, _ui(self.app)
        if self.body is not None:
            self.body.destroy()
        self.body = body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure((0, 1), weight=1, uniform="cols")
        if not self.data["carriers"]:
            return missing_file(body, app)
        name = self.choice.get()
        if name == WELLCARE:
            return self._wellcare(body)
        c = self.data["carriers"].get(name, {})
        head = name + (f"      speed dial {c['speed_dial']}" if c.get("speed_dial") else "")
        ctk.CTkLabel(body, text=head, font=ui.font(20, "bold"), text_color=ui.TEXT, anchor="w") \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=ui.SP, pady=(0, 2 * ui.SP))
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=1, column=0, sticky="new")
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=1, column=1, sticky="new")
        for col in (left, right):
            col.grid_columnconfigure(0, weight=1)
        r = 0
        if c.get("payment"):
            card = _card(left, app, "Payment terms", r)
            _bottom(card, _pairs(card, app, c["payment"].items()), app)
            r += 1
        if c.get("submit"):
            card = _card(left, app, "Where to submit", r)
            _bottom(card, _pairs(card, app, c["submit"].items()), app)
            r += 1
        if c.get("tips"):
            card = _card(left, app, "Tips", r)
            for i, tip in enumerate(c["tips"], 1):
                ctk.CTkLabel(card, text="•  " + tip, font=ui.font(13), text_color=ui.TEXT, anchor="w",
                             justify="left", wraplength=470).grid(row=i, column=0, columnspan=2, sticky="w",
                                                                  padx=2 * ui.SP, pady=2)
            _bottom(card, len(c["tips"]) + 1, app)
        r = 0
        for key, title in (("underwriting", "Underwriting"), ("accounting", "Accounting"), ("claims", "Claims")):
            if c.get(key):
                card = _card(right, app, title, r)
                _bottom(card, contact_rows(card, app, c[key], 1), app)
                r += 1

    def _wellcare(self, body):
        app, ui = self.app, _ui(self.app)
        w = self.data.get("wellcare_payment") or {}
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=ui.SP, pady=(0, 2 * ui.SP))
        ctk.CTkLabel(head, text="How clients pay WellCare", font=ui.font(20, "bold"), text_color=ui.TEXT) \
            .pack(side="left")
        b = ctk.CTkButton(head, text="Copy for the client", height=34, font=ui.font(13, "bold"),
                          fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER)
        b.configure(command=lambda: copy(app, carriers.wellcare_payment_text(self.data), b))
        b.pack(side="right")
        if w.get("intro"):
            ctk.CTkLabel(body, text=w["intro"], font=ui.font(13), text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=900).grid(row=1, column=0, columnspan=2, sticky="w", padx=ui.SP,
                                              pady=(0, 2 * ui.SP))
        for i, (title, points) in enumerate(w.get("options", [])):
            card = _card(body, app, title, 2 + i // 2, column=i % 2)
            for j, p in enumerate(points, 1):
                ctk.CTkLabel(card, text="•  " + p, font=ui.font(13), text_color=ui.TEXT, anchor="w",
                             justify="left", wraplength=440).grid(row=j, column=0, sticky="w", padx=2 * ui.SP, pady=2)
            _bottom(card, len(points) + 1, app)


# ---------------------------------------------------------------- underwriter call
class UwCallPage(Panel):
    def __init__(self, app, folder):
        super().__init__(app)
        self.app, self.folder = app, Path(folder)
        ui = self.ui = _ui(app)
        self.title(f"Underwriter call - {self.folder.name}")
        self.geometry("1180x840")
        self.data = carriers.load(app.cfg)
        self.on_quote = quote_carriers(app, self.folder)
        names = [n for n in self.on_quote if self.on_quote[n]] + [n for n in self.on_quote if not self.on_quote[n]]
        names += sorted(n for n in self.data["carriers"] if n not in names)
        self._prefill = ""
        self._confirm = None
        self.grid_columnconfigure(0, weight=5, uniform="c")
        self.grid_columnconfigure(1, weight=6, uniform="c")
        self.grid_rowconfigure(0, weight=1)

        # ---- left: log a call ----
        form = ctk.CTkScrollableFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1,
                                      border_color=ui.BORDER)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, ui.SP))
        form.grid_columnconfigure((0, 1), weight=1, uniform="f")
        p = 2 * ui.SP
        ctk.CTkLabel(form, text="Log the call", font=ui.font(18, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=p, pady=(p, 0))
        ctk.CTkLabel(form, text="Refer messages on the quote: call, confirm the client is eligible, note the result.",
                     font=ui.font(12), text_color=ui.MUTED, wraplength=430, justify="left") \
            .grid(row=1, column=0, columnspan=2, sticky="w", padx=p)

        self._label(form, 2, 0, "Carrier")
        self.carrier = tk.StringVar(value=names[0] if names else "")
        ctk.CTkComboBox(form, values=names or [""], variable=self.carrier, height=36, font=ui.font(13),
                        border_color=ui.BORDER, button_color=ui.PRIMARY, button_hover_color=ui.PRIMARY_HOVER,
                        command=lambda _: self.carrier_changed()) \
            .grid(row=3, column=0, columnspan=2, sticky="ew", padx=p)
        now = datetime.datetime.now()
        self._label(form, 4, 0, "Date")
        self._label(form, 4, 1, "Time")
        self.date = self._entry(form, 5, 0, now.strftime("%Y-%m-%d"), "YYYY-MM-DD")
        self.time = self._entry(form, 5, 1, now.strftime("%I:%M %p").lstrip("0"), "2:30 PM")
        self._label(form, 6, 0, "Underwriter's name *")
        self._label(form, 6, 1, "Called on")
        self.underwriter = ctk.CTkComboBox(form, values=[""], height=36, font=ui.font(13), border_color=ui.BORDER,
                                           button_color=ui.SURFACE_ALT, command=lambda _: self.person_picked())
        self.underwriter.grid(row=7, column=0, sticky="ew", padx=(p, ui.SP / 2))
        self.contact = ctk.CTkComboBox(form, values=[""], height=36, font=ui.font(13), border_color=ui.BORDER,
                                       button_color=ui.SURFACE_ALT)
        self.contact.grid(row=7, column=1, sticky="ew", padx=(ui.SP / 2, p))
        self._label(form, 8, 0, "Reason for the call *", span=2)
        self.reason = ctk.CTkTextbox(form, height=96, font=ui.font(13), border_width=1, border_color=ui.BORDER,
                                     wrap="word")
        self.reason.grid(row=9, column=0, columnspan=2, sticky="ew", padx=p)
        self._label(form, 10, 0, "Result *")
        self.result = tk.StringVar(value="")
        ctk.CTkSegmentedButton(form, values=list(checklist.RESULTS), variable=self.result, height=34,
                               font=ui.font(12), selected_color=ui.PRIMARY, selected_hover_color=ui.PRIMARY_HOVER) \
            .grid(row=11, column=0, columnspan=2, sticky="ew", padx=p)
        self._label(form, 12, 0, "Notes (conditions, what the underwriter said)", span=2)
        self.notes = ctk.CTkTextbox(form, height=96, font=ui.font(13), border_width=1, border_color=ui.BORDER,
                                    wrap="word")
        self.notes.grid(row=13, column=0, columnspan=2, sticky="ew", padx=p)
        self.error = ctk.CTkLabel(form, text="", font=ui.font(12), text_color=ui.DANGER, wraplength=430,
                                  justify="left")
        self.error.grid(row=14, column=0, columnspan=2, sticky="w", padx=p, pady=(ui.SP, 0))
        ctk.CTkButton(form, text="Save call", height=40, width=150, font=ui.font(14, "bold"), fg_color=ui.PRIMARY,
                      hover_color=ui.PRIMARY_HOVER, command=self.save) \
            .grid(row=15, column=1, sticky="e", padx=p, pady=(ui.SP, p))

        # ---- right: who to call, refer messages, calls logged ----
        self.side = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.side.grid(row=0, column=1, sticky="nsew", padx=(ui.SP, 0))
        self.side.grid_columnconfigure(0, weight=1)
        self.bind("<Escape>", lambda e: self.destroy())
        self.carrier_changed()

    def _label(self, parent, row, col, text, span=1):
        ui = self.ui
        ctk.CTkLabel(parent, text=text, font=ui.font(13, "bold"), text_color=ui.TEXT) \
            .grid(row=row, column=col, columnspan=span, sticky="w", padx=(2 * ui.SP, 0) if col == 0 else (ui.SP / 2, 0),
                  pady=(1.5 * ui.SP, ui.SP / 2))

    def _entry(self, parent, row, col, value, placeholder):
        ui = self.ui
        e = ctk.CTkEntry(parent, height=36, font=ui.font(13), border_color=ui.BORDER, placeholder_text=placeholder)
        e.grid(row=row, column=col, sticky="ew", padx=(2 * ui.SP, ui.SP / 2) if col == 0 else (ui.SP / 2, 2 * ui.SP))
        e.insert(0, value)
        return e

    # ---- carrier picked: contacts, underwriters, reason ----
    def carrier_changed(self):
        name = self.carrier.get()
        c = self.data["carriers"].get(name, {})
        found = carriers.contacts(c.get("underwriting", []))
        phones = [v + (f" ext {carriers.ext_of(line)}" if carriers.ext_of(line) else "")
                  for kind, v, line in found if kind == "phone"]
        emails = [v for kind, v, _ in found if kind == "email"]
        self.contact.configure(values=phones + emails or [""])
        self.contact.set(phones[0] if phones else emails[0] if emails else "")
        people = c.get("underwriters", [])
        self.underwriter.configure(values=people or [""])
        if not self.underwriter.get() or self.underwriter.get() in self._people_before():
            self.underwriter.set("")
        self._people = people
        msgs = self.on_quote.get(name, [])
        text = "\n".join("• " + m for m in msgs)
        if self.reason.get("1.0", "end").strip() in ("", self._prefill.strip()):
            self.reason.delete("1.0", "end")
            self.reason.insert("1.0", text)
            self._prefill = text
        self.show_side()

    def person_picked(self):
        """A named underwriter: call their direct line (with extension) instead of the general one."""
        who = self.underwriter.get().strip().lower()
        c = self.data["carriers"].get(self.carrier.get(), {})
        for kind, value, line in carriers.contacts(c.get("underwriting", [])):
            if who and who in line.lower() and kind == "phone":
                ext = carriers.ext_of(line)
                self.contact.set(value + (f" ext {ext}" if ext else ""))
                return

    def _people_before(self):
        return getattr(self, "_people", [])

    def show_side(self):
        app, ui = self.app, self.ui
        for w in self.side.winfo_children():
            w.destroy()
        name = self.carrier.get()
        c = self.data["carriers"].get(name)
        r = 0
        if not self.data["carriers"]:
            missing_file(self.side, app, r)
            r += 1
        elif c:
            title = f"Underwriting - {name}" + (f"   ·   speed dial {c['speed_dial']}" if c.get("speed_dial") else "")
            card = _card(self.side, app, title, r)
            _bottom(card, contact_rows(card, app, c.get("underwriting") or ["No underwriting contact listed"], 1), app)
            r += 1
        msgs = self.on_quote.get(name, [])
        if msgs:
            card = _card(self.side, app, "Refer messages on the quote", r)
            for i, m in enumerate(msgs, 1):
                ctk.CTkLabel(card, text="•  " + m, font=ui.font(13), text_color=WARN, anchor="w", justify="left",
                             wraplength=520).grid(row=i, column=0, columnspan=2, sticky="w", padx=2 * ui.SP, pady=2)
            _bottom(card, len(msgs) + 1, app)
            r += 1
        others = [n for n, m in self.on_quote.items() if m and n != name]
        if others:
            ctk.CTkLabel(self.side, text="Also refer messages from: " + ", ".join(others), font=ui.font(12),
                         text_color=ui.MUTED).grid(row=r, column=0, sticky="w", padx=ui.SP, pady=(0, 2 * ui.SP))
            r += 1
        calls = sorted(records.load(self.folder).get("uw_calls", []), key=lambda x: x.get("at", ""), reverse=True)
        card = _card(self.side, app, f"Calls logged ({len(calls)})", r)
        if not calls:
            ctk.CTkLabel(card, text="No calls yet.", font=ui.font(13), text_color=ui.MUTED) \
                .grid(row=1, column=0, sticky="w", padx=2 * ui.SP, pady=(0, 1.5 * ui.SP))
        for i, call in enumerate(calls, 1):
            self._call_row(card, i, call)

    def _call_row(self, card, row, call):
        app, ui = self.app, self.ui
        box = ctk.CTkFrame(card, fg_color=ui.SURFACE_ALT, corner_radius=8)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", padx=2 * ui.SP, pady=(0, ui.SP))
        box.grid_columnconfigure(0, weight=1)
        color = {"Approved": ui.SUCCESS, "Approved with conditions": WARN, "Declined": ui.DANGER}.get(
            call.get("result"), ui.MUTED)
        top = ctk.CTkFrame(box, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=1.5 * ui.SP, pady=(ui.SP, 0))
        ctk.CTkLabel(top, text=f"{_when(call.get('at'))}  ·  {call.get('carrier', '')}", font=ui.font(13, "bold"),
                     text_color=ui.TEXT).pack(side="left")
        ctk.CTkLabel(top, text=call.get("result", ""), font=ui.font(12, "bold"), text_color=color) \
            .pack(side="right")
        lines = [f"{call.get('underwriter', '')}" + (f"  ·  {call['contact']}" if call.get("contact") else ""),
                 "Reason: " + call.get("reason", "").replace("\n", "  "),
                 ("Notes: " + call["notes"].replace("\n", "  ")) if call.get("notes") else "",
                 f"Logged by {call.get('by', '')}"]
        ctk.CTkLabel(box, text="\n".join(l for l in lines if l), font=ui.font(12), text_color=ui.TEXT,
                     anchor="w", justify="left", wraplength=460) \
            .grid(row=1, column=0, sticky="w", padx=1.5 * ui.SP, pady=(2, 0))
        btns = ctk.CTkFrame(box, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="w", padx=ui.SP, pady=(2, ui.SP))
        small = dict(height=26, font=ui.font(12), fg_color="transparent", hover_color=ui.SURFACE,
                     text_color=ui.MUTED)
        b = ctk.CTkButton(btns, text="Copy as note", width=100, **small)
        b.configure(command=lambda: copy(app, note_text(call), b))
        b.pack(side="left")
        d = ctk.CTkButton(btns, text="Delete", width=70, **small)
        d.configure(command=lambda: self.delete(call, d))
        d.pack(side="left")

    def delete(self, call, button):
        if self._confirm != call.get("id"):          # first click asks, second deletes
            self._confirm = call.get("id")
            button.configure(text="Delete? Click again", width=140, text_color=self.ui.DANGER)
            return
        records.delete_item(self.folder, "uw_calls", call["id"])
        self._confirm = None
        self.app.refresh_soon(100)
        self.show_side()

    def save(self):
        at = _parse_when(self.date.get(), self.time.get())
        item = {"carrier": self.carrier.get().strip(), "underwriter": self.underwriter.get().strip(),
                "contact": self.contact.get().strip(), "reason": self.reason.get("1.0", "end").strip(),
                "result": self.result.get(), "notes": self.notes.get("1.0", "end").strip()}
        problem = ("Pick the carrier." if not item["carrier"] else
                   "Date / time: use 2026-10-25 and 2:30 PM." if at is None else
                   "Enter the underwriter's name." if not item["underwriter"] else
                   "Enter the reason for the call." if not item["reason"] else
                   "Pick the result." if not item["result"] else "")
        if problem:
            self.error.configure(text=problem)
            return
        item["at"] = at
        saved = records.save_item(self.folder, "uw_calls", item)
        copy(self.app, note_text(saved))
        self.error.configure(text="✓ Saved - and copied as a note for PowerBroker.", text_color=self.ui.SUCCESS)
        self.notes.delete("1.0", "end")
        self.result.set("")
        self.app.refresh_soon(100)
        self.show_side()


def _parse_when(date_text, time_text):
    date_text, time_text = date_text.strip(), time_text.strip().upper().replace(".", "")
    for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %I:%M%p", "%Y-%m-%d %H:%M"):
        try:
            return datetime.datetime.strptime(f"{date_text} {time_text}", fmt).isoformat(timespec="minutes")
        except ValueError:
            pass
    return None


def _when(at):
    try:
        return datetime.datetime.fromisoformat(at).strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")
    except (TypeError, ValueError):
        return at or ""


def note_text(call):
    """The call as a file note (paste into PowerBroker / the client's notes)."""
    lines = [f"UW call - {_when(call.get('at'))} - {call.get('carrier', '')}",
             f"Spoke with: {call.get('underwriter', '')}" + (f" ({call['contact']})" if call.get("contact") else ""),
             f"Reason: {call.get('reason', '')}",
             f"Result: {call.get('result', '')}"]
    if call.get("notes"):
        lines.append(f"Notes: {call['notes']}")
    if call.get("by"):
        lines.append(f"By: {call['by']}")
    return "\n".join(lines)
