"""Quote accepted -> the policy and vehicles saved to the client's record (the Tracker), with no retyping.

The accepted quote's carrier, premium, effective date and vehicles are read from the newest ARS quote;
the broker picks the carrier, the payment plan and (later) types the policy number. The same page
edits the saved policy afterwards. The saved policy then fills the policy emails (documents to sign,
down payment request, pink slips, confirmation) and the insurer billing email.
"""
import datetime
import re
import sys
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

import ui_kit

import carriers
import client_facts
import quote
import records
import review
from panel import Panel

LINE_FOR_TYPE = {"Auto": "Auto", "Home": "Home", "Tenant": "Tenant", "Commercial": "Commercial"}


def _ui(app):
    return sys.modules[type(app).__module__]


# ---------- reading the quote ----------
def quote_for_policy(folder):
    """What a policy needs from the newest quote: {"file", "effective", "carriers": [{name, premium,
    reference, declined}], "vehicles": [vehicle records]} - None without a quote."""
    quotes = review.find_docs(folder)["quote"]
    if not quotes:
        return None
    q = quote.read(str(quotes[0]))
    out = {"file": quotes[0].name, "effective": q.get("effective"), "carriers": [], "vehicles": []}
    for c in q.get("carriers", []):
        out["carriers"].append({"name": c["name"], "premium": c.get("premium"), "reference": c.get("reference", ""),
                                "declined": any(review.carrier_message(m) == "decline" for m in c.get("messages", []))})
    out["carriers"].sort(key=lambda c: (c["declined"], not c["premium"]))      # bindable quotes first
    for v in q.get("vehicles", []):
        words = client_facts._car(v["description"]).split()
        out["vehicles"].append({
            "year": str(v.get("year") or (words[0] if words else "")),
            "make": words[1] if len(words) > 1 else "", "model": " ".join(words[2:]),
            "vin": v.get("vin", ""), "use": {"Pleasure": "Pleasure", "Commute": "Commute",
                                              "Business": "Business"}.get(v.get("use"), ""),
            "km_year": str(v["annual_km"]) if v.get("annual_km") else "",
            "winter_tires": bool(v.get("winter_tires"))})
    return out


# ---------- carrier payment terms ----------
def down_payment_rule(cfg, insurer):
    """The carrier's down payment rule from carriers.json (e.g. "2 months"), or ""."""
    data = carriers.load(cfg)
    name = carriers.find(data, insurer)
    if not name:
        return ""
    return (data["carriers"][name].get("payment") or {}).get("Down payment", "")


def suggest_down_payment(rule, premium):
    """Two months of premium when the rule says so - a starting figure, the carrier's papers decide."""
    if premium and re.search(r"\b2 months\b", rule or "", re.I) and not re.match(r"none", rule or "", re.I):
        return round(premium / 12 * 2, 2)
    return None


def billing_email(cfg, insurer):
    """The carrier's billing / accounts email from carriers.json, or ""."""
    data = carriers.load(cfg)
    name = carriers.find(data, insurer)
    if not name:
        return ""
    entry = data["carriers"][name]

    def emails(kind):
        return [v for k, v, _ in carriers.contacts(entry.get(kind) or []) if k == "email"]
    found = emails("accounting")
    # several billing addresses: the one on the carrier's own domain (the same as its underwriting / claims)
    own = {a.split("@")[1].lower() for a in emails("underwriting") + emails("claims")}
    return next((a for a in found if a.split("@")[1].lower() in own), found[0] if found else "")


# ---------- email blanks from the saved policy ----------
def _nice(d):
    return d.strftime("%b %d, %Y").replace(" 0", " ")


NUMBER_KEY = {"Auto": "auto", "Home": "home", "Condo": "home", "Tenant": "tenant"}      # line -> blank prefix
KEY_LINES = {"auto_policy_number": ("Auto",), "home_policy_number": ("Home", "Condo"),
             "tenant_policy_number": ("Tenant",)}


def email_values(folder):
    """Email template blanks from the client's bound policies (and vehicles): {key: value}.
    Insurer, dates and premium come from the auto policy (else the newest one); every bound policy
    gives its own number (auto_ / home_ / tenant_policy_number), and policy_number is the main one."""
    data = records.load(folder)
    p = records.bound_policy(data, "Auto") or records.bound_policy(data)
    if not p:
        return {}
    v = {"insurer": p.get("insurer", "")}
    for line, key in NUMBER_KEY.items():
        other = records.bound_policy(data, line)
        if other and other.get("policy_number"):
            v.setdefault(f"{key}_policy_number", other["policy_number"])
    if p.get("policy_number"):
        v["policy_number"] = p["policy_number"]
    eff = records.parse_date(p.get("effective"))
    if eff:
        v["effective_date"] = _nice(eff)
        v["valid_until_date"] = _nice(eff + datetime.timedelta(days=30))
    if p.get("plan") == "Monthly" and records.money(p.get("monthly")):
        v["premium"] = f"${records.money(p['monthly']):,.2f} / month"
    elif records.money(p.get("premium")):
        v["premium"] = f"${records.money(p['premium']):,.2f} / year"
    if records.money(p.get("down_payment")):
        v["down_payment"] = f"${records.money(p['down_payment']):,.2f}"
    if p.get("quote_number"):
        v["quote_number"] = p["quote_number"]
    cars = [" ".join(x for x in (c.get("year"), c.get("make"), c.get("model")) if x) for c in data["vehicles"]]
    if any(cars):
        v["vehicle"] = "; ".join(c for c in cars if c)
    return v


def remember_policy_numbers(folder, typed):
    """Save policy numbers typed into an email ({blank key: value}) onto the matching bound policy, so
    they are typed once and every later email (and the Tracker) has them. Returns how many were saved."""
    saved = 0
    for key, value in typed.items():
        value = (value or "").strip()
        if not value or not key.endswith("policy_number"):
            continue
        data = records.load(folder)
        lines = KEY_LINES.get(key)
        p = next((records.bound_policy(data, line) for line in lines or () if records.bound_policy(data, line)),
                 None) if lines else records.bound_policy(data, "Auto") or records.bound_policy(data)
        if p and p.get("policy_number") != value:
            records.save_item(folder, "policies", {**p, "policy_number": value})
            saved += 1
    return saved


def save_accepted(folder, kind, policy, vehicles):
    """Save the policy (new, or update the bound one) and add the quote's vehicles that aren't on file."""
    data = records.load(folder)
    records.save_item(folder, "policies", policy)
    have = {(c.get("vin") or "").upper() for c in data["vehicles"]} | \
           {f"{c.get('year')} {c.get('make')} {c.get('model')}".upper() for c in data["vehicles"]}
    added = 0
    for car in vehicles:
        key = (car.get("vin") or "").upper() or f"{car['year']} {car['make']} {car['model']}".upper()
        if key and key not in have:
            records.save_item(folder, "vehicles", car)
            added += 1
    return added


# ---------- the page ----------
class AcceptQuotePage(Panel):
    """Pick the accepted carrier from the quote; the policy and vehicles go to the client record."""
    FORM = True

    def __init__(self, app, folder, on_saved=None):
        super().__init__(app)
        self.app, self.folder, self.on_saved = app, Path(folder), on_saved
        ui = self.ui = _ui(app)
        self.kind = app.client_type_of.get(self.folder, "Auto")
        self.existing = records.bound_policy(records.load(self.folder)) or {}
        self.title(("Policy details" if self.existing else "Quote accepted") + f" - {self.folder.name}")
        self.geometry("640x760")
        self.q = None
        p = 2 * ui.SP

        card = ctk.CTkFrame(self, fg_color=ui.SURFACE, corner_radius=12, border_width=1, border_color=ui.BORDER)
        card.pack(fill="x")
        card.grid_columnconfigure((0, 1), weight=1, uniform="f")
        ctk.CTkLabel(card, text="Save the policy to the Tracker", font=ui.font(18, "bold"), text_color=ui.TEXT) \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=p, pady=(p, 0))
        self.source = ctk.CTkLabel(card, text="Reading the quote…", font=ui.font(13), text_color=ui.MUTED,
                                   wraplength=560, justify="left", anchor="w")
        self.source.grid(row=1, column=0, columnspan=2, sticky="w", padx=p)

        self._label(card, 2, 0, "Insurance company *", span=2)
        self.insurer = ctk.CTkComboBox(card, values=[""], height=36, font=ui.font(14), border_color=ui.BORDER,
                                       button_color=ui.SURFACE_ALT, command=lambda _: self.carrier_picked())
        self.insurer.grid(row=3, column=0, columnspan=2, sticky="ew", padx=p)
        self.insurer.bind("<FocusOut>", lambda e: self.show_rule())
        self._label(card, 4, 0, "Policy number")
        self._label(card, 4, 1, "Effective date *")
        self.number = self._entry(card, 5, 0, "Add it when you have it")
        import tracker_ui
        self.effective = tracker_ui.DateField(card, ui)
        self.effective.grid(row=5, column=1, sticky="ew", padx=(ui.SP / 2, p))
        self._label(card, 6, 0, "Annual premium ($) *")
        self._label(card, 6, 1, "Payment plan")
        self.premium = self._entry(card, 7, 0, "e.g. 2666.00")
        self.premium.bind("<FocusOut>", lambda e: self.fill_money())
        self.plan = tk.StringVar(value="Monthly")
        ui_kit.Segmented(card, values=records.PLANS, variable=self.plan, height=36, font=ui.font(13),
                               command=lambda _: self.fill_money()) \
            .grid(row=7, column=1, sticky="ew", padx=(ui.SP / 2, p))
        self._label(card, 8, 0, "Monthly payment ($)")
        self._label(card, 8, 1, "Down payment ($)")
        self.monthly = self._entry(card, 9, 0, "")
        self.down = self._entry(card, 9, 1, "")
        self.rule = ctk.CTkLabel(card, text="", font=ui.font(13), text_color=ui.WARN, wraplength=560,
                                 justify="left", anchor="w")
        self.rule.grid(row=10, column=0, columnspan=2, sticky="w", padx=p, pady=(ui.SP, 0))
        self._label(card, 11, 0, "Payment method")
        self.method = tk.StringVar(value="Pre-authorized debit")
        ctk.CTkOptionMenu(card, values=records.METHODS, variable=self.method, height=36, font=ui.font(13),
                          fg_color=ui.SURFACE_ALT, button_color=ui.SURFACE_ALT, button_hover_color=ui.BORDER,
                          text_color=ui.TEXT, dynamic_resizing=False) \
            .grid(row=12, column=0, sticky="ew", padx=(p, ui.SP / 2))
        self.cars = ctk.CTkLabel(card, text="", font=ui.font(13), text_color=ui.MUTED, wraplength=560,
                                 justify="left", anchor="w")
        self.cars.grid(row=13, column=0, columnspan=2, sticky="w", padx=p, pady=(1.5 * ui.SP, 0))
        self.error = ctk.CTkLabel(card, text="", font=ui.font(13), text_color=ui.DANGER, wraplength=560,
                                  justify="left", anchor="w")
        self.error.grid(row=14, column=0, columnspan=2, sticky="w", padx=p, pady=(ui.SP, 0))
        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.grid(row=15, column=0, columnspan=2, sticky="e", padx=p, pady=p)
        app.secondary_button(bar, "Cancel", self.destroy, width=96).pack(side="left", padx=(0, ui.SP))
        ctk.CTkButton(bar, text="Save to the Tracker", height=40, width=190, font=ui.font(14, "bold"),
                      fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER, command=self.save).pack(side="left")
        self.bind("<Escape>", lambda e: self.destroy())

        self._fill_existing()
        self._read()

    def _label(self, parent, row, col, text, span=1):
        ui = self.ui
        ctk.CTkLabel(parent, text=text, font=ui.font(13, "bold"), text_color=ui.TEXT) \
            .grid(row=row, column=col, columnspan=span, sticky="w",
                  padx=(2 * ui.SP, 0) if col == 0 else (ui.SP / 2, 0), pady=(1.5 * ui.SP, ui.SP / 2))

    def _entry(self, parent, row, col, hint):
        ui = self.ui
        e = ctk.CTkEntry(parent, height=36, font=ui.font(14), border_color=ui.BORDER, placeholder_text=hint)
        e.grid(row=row, column=col, sticky="ew", padx=(2 * ui.SP, ui.SP / 2) if col == 0 else (ui.SP / 2, 2 * ui.SP))
        return e

    @staticmethod
    def _put(entry, value):
        entry.delete(0, "end")
        if value not in (None, ""):
            entry.insert(0, str(value))

    def _fill_existing(self):
        e = self.existing
        if not e:
            return
        self.insurer.set(e.get("insurer", ""))
        self._put(self.number, e.get("policy_number"))
        self._put(self.effective, e.get("effective"))
        self._put(self.premium, e.get("premium"))
        self.plan.set(e.get("plan") or "Monthly")
        self._put(self.monthly, e.get("monthly"))
        self._put(self.down, e.get("down_payment"))
        self.method.set(e.get("method") or "Pre-authorized debit")
        self.show_rule()

    # ----- quote -----
    def _read(self):
        result = {}

        def work():
            try:
                result["q"] = quote_for_policy(self.folder)
            except Exception as e:
                result["err"] = f"Could not read the quote: {e}"
        t = threading.Thread(target=work, daemon=True)
        t.start()

        def wait():
            if t.is_alive():
                self.after(100, wait)
            elif self.winfo_exists():
                self._quote_read(result.get("q"), result.get("err"))
        wait()

    def _quote_read(self, q, err):
        self.q = q
        if err or not q:
            self.source.configure(text=err or "No quote in the folder - type the details in.")
            return
        names = [self._carrier_label(c) for c in q["carriers"]]
        self.insurer.configure(values=names or [""])
        self.source.configure(text=f"From {q['file']} - pick the company the client accepted. "
                                   "Check the figures against the carrier's papers.")
        if not self.existing:
            if q["effective"]:
                self._put(self.effective, q["effective"].isoformat())
            if names:
                self.insurer.set(names[0])
                self.carrier_picked()
        cars = q["vehicles"]
        self.cars.configure(text=("Vehicles from the quote (added to the record if not there yet): "
                                  + "; ".join(f"{c['year']} {c['make']} {c['model']}" for c in cars))
                            if cars else "")

    @staticmethod
    def _carrier_label(c):
        price = f"  -  ${c['premium']:,.2f}" if c.get("premium") else ""
        return c["name"] + price + ("  (declined)" if c["declined"] else "")

    def _insurer_name(self):
        return re.split(r"\s+-\s+\$|\s+\(declined\)", self.insurer.get().strip())[0].strip()

    def _carrier(self):
        name = self._insurer_name()
        return next((c for c in (self.q or {}).get("carriers", []) if c["name"] == name), None)

    def carrier_picked(self):
        c = self._carrier()
        if c and c.get("premium"):
            self._put(self.premium, f"{c['premium']:.2f}")
            self._put(self.monthly, "")
            self._put(self.down, "")
        self.insurer.set(self._insurer_name())
        self.fill_money()

    def show_rule(self):
        rule = down_payment_rule(self.app.cfg, self._insurer_name())
        self.rule.configure(text=f"{self._insurer_name()} down payment: {rule}" if rule else "")
        return rule

    def fill_money(self):
        prem = records.money(self.premium.get())
        monthly = self.plan.get() == "Monthly"
        if prem and monthly and not self.monthly.get().strip():
            self._put(self.monthly, f"{prem / 12:.2f}")
        rule = self.show_rule()
        down = suggest_down_payment(rule, prem) if monthly else None
        if down and not self.down.get().strip():
            self._put(self.down, f"{down:.2f}")

    # ----- save -----
    def save(self):
        insurer = self._insurer_name()
        eff = records.parse_date(self.effective.get())
        prem = records.money(self.premium.get())
        if not insurer:
            self.error.configure(text="Pick the insurance company.")
            return
        if not eff:
            self.error.configure(text="Enter the effective date (use the calendar).")
            return
        if not prem:
            self.error.configure(text="Enter the annual premium.")
            return
        try:
            expiry = eff.replace(year=eff.year + 1)
        except ValueError:                                   # Feb 29
            expiry = eff + datetime.timedelta(days=365)
        c = self._carrier()
        policy = dict(self.existing)
        policy.update(
            line=self.existing.get("line") or LINE_FOR_TYPE.get(self.kind, "Other"),
            status=self.existing.get("status") or "Bound", insurer=insurer,
            policy_number=self.number.get().strip(), effective=eff.isoformat(),
            expiry=self.existing.get("expiry") if self.existing.get("effective") == eff.isoformat()
            and self.existing.get("expiry") else expiry.isoformat(),
            premium=f"{prem:.2f}", plan=self.plan.get(),
            monthly=f"{records.money(self.monthly.get()):.2f}" if records.money(self.monthly.get()) else "",
            down_payment=f"{records.money(self.down.get()):.2f}" if records.money(self.down.get()) else "",
            method=self.method.get(), bound_date=self.existing.get("bound_date") or records.today(),
            quote_number=self.existing.get("quote_number") or (c or {}).get("reference", ""))
        try:
            added = save_accepted(self.folder, self.kind, policy, (self.q or {}).get("vehicles", []))
        except OSError as e:
            self.error.configure(text=f"Could not save (is the shared drive available?) {e}")
            return
        msg = f"✓ {insurer} policy saved to the Tracker" + (f", {added} vehicle{'s' if added > 1 else ''} added"
                                                             if added else "")
        self.destroy()
        if self.on_saved:
            self.on_saved(msg)
