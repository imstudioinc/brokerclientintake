"""The broker's step-by-step checklist for a client (Auto, Home, Tenant and Commercial).

Some steps tick themselves from what is in the client folder (DASH, quote, MVR, documents) or
in client.json (licence #, MVR request sent). The rest - PowerBroker, UW-Compass - the broker
ticks. Ticks are saved in the client's tracking.json under "checklist" (shared folder: everyone
sees them). A step can also be marked N/A where that makes sense (no DASH for a new driver,
no referral needed).
"""
import datetime
import json
from pathlib import Path

import property_risk
import quote
import records
import review

# (id, title, hint, auto, can_be_na, action)
#   auto: key of an automatic check below, or None (ticked by hand)
#   action: what the step's button does in the app (None = no button)
AUTO_STEPS = [
    # 1. Intake: the client's details and documents
    ("profile", "Client profile", "Name and driver's licence #. Phone and email can follow - add them when you get them.",
     "profile", False, "edit"),
    ("consent", "Consent form filled", "Fill WellCare's consent form and have the client sign it.", "consent", False,
     "consent"),
    ("dash", "DASH report", "Pull the DASH report if the client has insurance history.", "dash", True, "dash"),
    ("mvr_request", "MVR request sent", "Email the branch manager for the MVR (address set in Settings).",
     "mvr_request", False, "mvr"),
    ("mvr", "MVR received", "Saved to the folder automatically when you download it from Outlook.", "mvr", False, None),
    ("documents", "Documents from the client", "Ownership, void cheque (most clients pay monthly), winter tire "
     "photos, bill of sale, financing papers.", "documents", False, None),
    # 2. Quote: fill the forms and get the quote
    ("quote", "Quote in ARS", "Quote in Applied Rating (ARS entry has the DASH claims and gaps ready to type) and "
     "save the Quote Information PDF in the folder.", "quote", False, "ars"),
    ("uw_call", "Refer messages confirmed with the underwriter", "The quote has refer messages: call the "
     "underwriter, confirm the client is eligible, and log the call (who, when, why, result).", "uw_call", True,
     "uwcall"),
    ("requote", "Quote checked with the DASH and MVR", "Review quote shows what doesn't match - fix ARS and quote "
     "again if needed.", None, False, "review"),
    # 3. Policy: after the client accepts the quote
    ("approved", "Quote accepted - policy saved to the Tracker", "Pick the carrier the client chose: the "
     "policy, premium and vehicles go to the Tracker from the quote. Agree how the client pays.", "policy", False,
     "accept"),
    ("pb_policy", "Quote exported; policy set up in PowerBroker", "", None, False, None),
    ("pb_app", "Application created in PowerBroker", "Paste the REMARKS text from UW-Compass into the application.",
     None, False, None),
    ("sign_docs", "Documents sent to the client to sign", "Auto application, consent form, AB form package and "
     "PAC form (with a void cheque).", None, False, "email"),
    ("down_payment", "Down payment requested", "Ask the client for the down payment - mark N/A if the carrier "
     "takes none.", None, True, "email"),
    ("signed", "Signed documents back from the client", "", None, False, None),
    ("paid", "Client confirmed the down payment", "The client sends you the payment confirmation.", None, True, None),
    ("billing", "Echelon billing asked to use the client's credit card", "Once the down payment is done, email "
     "Echelon's billing team to update the down payment method to the insured's credit card.", "billing", True,
     "email"),
    ("uploaded", "Signed documents uploaded and validated", "Upload them to the system and validate.", None, False,
     "folder"),
    ("uwc", "All documents submitted to head office", "Submit on UW-Compass when everything looks fine.", None, False,
     None),
    ("referred", "Referred (if UW-Compass shows a refer message)", "Refer to head office or the insurer - "
     "mark N/A if there was nothing to refer.", None, True, None),
    ("temp_pink", "Temporary pink slip (1 month) sent", "Send it once the documents are with head office.", None,
     False, "email"),
    ("ho_confirm", "Head office confirmed the policy", "", None, False, None),
    ("sent", "1-year pink slip and policy documents sent", "Confirmation email with the policy number, the policy "
     "documents and the 1-year pink card(s).", None, False, "email"),
]

# ---------- Home, Tenant and Commercial: the same three stages, their own steps ----------
# Built from WellCare's Property Underwriting Checklist, the PowerBroker Property Completion Guide and the
# commercial quote application (notes 01 and 39). The owner can reshape any of these; Auto stays as it was.
_PROPERTY_COMMON_QUOTE = [
    ("review", "Checked against the markets", "Review property shows which insurers will take it, what to refer and "
     "which documents it needs. Run it again if the answers change.", None, False, "preview"),
    ("uw_call", "Refer messages confirmed with the underwriter", "The quote has refer messages: call the "
     "underwriter, confirm the client is eligible, and log the call (who, when, why, result).", "uw_call", True,
     "uwcall"),
]


def _policy_steps(sign_hint, uwc_hint, sent_title="Policy documents sent to the client", sent_hint=
                  "Confirmation email with the policy number and the policy documents."):
    return [
        ("approved", "Quote accepted - policy saved to the Tracker", "Pick the carrier the client chose: the policy "
         "and premium go to the Tracker. Agree how the client pays: full payment, or a signed PAC form with a void "
         "cheque (the Carriers page has each insurer's terms).", "policy", False, "accept"),
        ("pb_policy", "Policy set up in PowerBroker", "Customer, Supplementary, Habitational and Risk screens: the "
         "PowerBroker entry sheet lists every field. Province ON; phone numbers the same as in Applied Quote.", None,
         False, "pentry"),
        ("pb_limits", "Sewer backup and overland: full limits written", "Hand write the FULL policy limits next to "
         "Sewer Backup and Overland Water. If the property doesn't qualify for full limits, a sign-off must go in "
         "with the application.", "limits", True, None),
        ("pb_app", "Application created in PowerBroker", "Print the CSIO habitational application; PowerBroker lists "
         "anything missed. Remarks: sign / effective / EZITV and HITS dates, address verification, claim details, "
         "UW approval.", None, False, None),
        ("sign_docs", "Documents sent to the client to sign", sign_hint, None, False, "email"),
        ("signed", "Signed documents and payment back from the client", "Do not bind until the signed application "
         "with payment is back.", "signed_docs", False, None),
        ("uploaded", "Signed documents uploaded and validated", "Upload them to the system and validate.", None, False,
         "folder"),
        ("uwc", "All documents submitted to head office", uwc_hint, None, False, None),
        ("referred", "Referred (if UW-Compass shows a refer message)", "Refer to head office or the insurer - "
         "mark N/A if there was nothing to refer.", None, True, None),
        ("ho_confirm", "Head office confirmed the policy", "", None, False, None),
        ("sent", sent_title, sent_hint, None, False, "email"),
    ]


_UWC_PROPERTY = ("Mandatory: signed consent (HITS), signed application, quote, EZITV within 30 days, PAC form + void "
                 "cheque, credit consent. If applicable: alarm certificate, mortgage information, rented dwelling / "
                 "sewer backup / oil tank / wood stove questionnaires, letter of experience, photos, appraisal.")

HOME_STEPS = [
    # 1. Intake: the client's details and documents
    ("profile", "Client profile", "Name, phone and email. Occupation and marital status go in the property details "
     "(PowerBroker needs them).", "profile_pc", False, "edit"),
    ("property", "Property details", "Year built, updates, heating, water protection, mortgage, insurance history and "
     "claims. The review, the documents list and the PowerBroker entry sheet all use them.", "property", False,
     "property"),
    ("consent", "Consent form filled", "Consent to order HITS and the credit score: fill it and have the client sign.",
     "consent", False, "consent"),
    ("hits", "HITS report", "Order HITS in PowerBroker once the consent is signed and save the PDF in the folder. It "
     "gives the claims history.", "hits", True, None),
    ("documents", "Documents from the client", "Photos, mortgage details, alarm certificate and the questionnaires "
     "this property needs.", "documents_prop", False, None),
    ("ezitv", "Replacement cost (EZITV) done", "Every building needs one, within 30 days of the effective date. The "
     "amount goes on the quote and the application.", "ezitv", False, None),
    # 2. Quote
    ("quote", "Quote in Applied Quote", "Quote with the property details (the entry sheet lists every field) and "
     "save the Quote Information PDF in the folder.", "quote", False, "pentry"),
] + _PROPERTY_COMMON_QUOTE + _policy_steps(
    "Application, consent and credit consent, PAC form with a void cheque, and the questionnaires this property "
    "needs.", _UWC_PROPERTY)

TENANT_STEPS = [
    ("profile", "Client profile", "Name, phone and email. Occupation and marital status go in the details "
     "(PowerBroker needs them).", "profile_pc", False, "edit"),
    ("property", "Tenant details", "Address, unit, contents value, roommates, prior insurance and claims. The review "
     "and the PowerBroker entry sheet use them.", "property", False, "property"),
    ("consent", "Consent form filled", "Consent to order HITS and the credit score: fill it and have the client sign.",
     "consent", False, "consent"),
    ("hits", "HITS report", "Order HITS in PowerBroker once the consent is signed and save the PDF in the folder.",
     "hits", True, None),
    ("documents", "Documents from the client", "Alarm certificate and letter of experience if they apply.",
     "documents_prop", False, None),
    ("quote", "Quote in Applied Quote", "Quote with the details (the entry sheet lists every field) and save the "
     "Quote Information PDF in the folder.", "quote", False, "pentry"),
] + _PROPERTY_COMMON_QUOTE + _policy_steps(
    "Application, consent and credit consent, and a PAC form with a void cheque.",
    "Mandatory: signed consent (HITS), signed application, quote, PAC form + void cheque, credit consent. If "
    "applicable: alarm certificate, letter of experience.")

COMMERCIAL_STEPS = [
    ("profile", "Client profile", "Business name, contact, phone and email.", "profile_pc", False, "edit"),
    ("application", "Commercial quote application", "Fill WellCare's commercial quote application with the client "
     "(one form per location: operations, claims, construction and updates, protection, revenue) and save it in the "
     "folder.", "commercial_app", False, None),
    ("consent", "Consent form filled", "Fill the consent form and have the client sign it.", "consent", False,
     "consent"),
    ("documents", "Documents from the client", "Photos of the location, ULC alarm certificate, prior insurance and "
     "claims history, restaurant supplement, subcontractors' proof of insurance.", "documents", False, None),
    ("quote", "Quote", "Submit to the markets and save the quote in the folder. The Carriers page has each insurer's "
     "contacts and where to submit.", "quote", False, None),
    ("uw_call", "Underwriter confirmed", "Confirm eligibility with the underwriter and log the call (who, when, why, "
     "result).", "uw_call", True, "uwcall"),
    ("approved", "Quote accepted - policy saved to the Tracker", "Pick the carrier the client chose. Agree how the "
     "client pays.", "policy", False, "accept"),
    ("pb_policy", "Policy set up in PowerBroker", "Enter the policy and attach the application.", None, False, None),
    ("sign_docs", "Documents sent to the client to sign", "Signed application, consent and a PAC form with a void "
     "cheque.", None, False, "email"),
    ("signed", "Signed documents and payment back from the client", "Do not bind until the signed application with "
     "payment is back.", "signed_docs", False, None),
    ("uploaded", "Signed documents uploaded and validated", "Upload them to the system and validate.", None, False,
     "folder"),
    ("uwc", "All documents submitted to head office", "Signed application, quote, consent, PAC form + void cheque; "
     "photos and ULC certificates if applicable.", None, False, None),
    ("referred", "Referred (if UW-Compass shows a refer message)", "Refer to head office or the insurer - mark N/A if "
     "there was nothing to refer.", None, True, None),
    ("ho_confirm", "Head office confirmed the policy", "", None, False, None),
    ("sent", "Policy documents sent to the client", "Confirmation email with the policy number and the policy "
     "documents.", None, False, "email"),
]

STAGES = [("Intake", "Details & documents", ["profile", "consent", "dash", "mvr_request", "mvr", "documents"]),
          ("Quote", "Forms & quote", ["quote", "uw_call", "requote"]),
          ("Policy", "Bind, upload, send", ["approved", "pb_policy", "pb_app", "sign_docs", "down_payment",
                                            "signed", "paid", "billing", "uploaded", "uwc", "referred",
                                            "temp_pink", "ho_confirm", "sent"])]
_HOME_STAGES = [("Intake", "Details & documents", ["profile", "property", "consent", "hits", "documents", "ezitv"]),
                ("Quote", "Forms & quote", ["quote", "review", "uw_call"]),
                ("Policy", "Bind, upload, send", ["approved", "pb_policy", "pb_limits", "pb_app", "sign_docs", "signed",
                                                  "uploaded", "uwc", "referred", "ho_confirm", "sent"])]
_TENANT_STAGES = [("Intake", "Details & documents", ["profile", "property", "consent", "hits", "documents"]),
                  _HOME_STAGES[1], _HOME_STAGES[2]]
_COMMERCIAL_STAGES = [("Intake", "Details & documents", ["profile", "application", "consent", "documents"]),
                      ("Quote", "Forms & quote", ["quote", "uw_call"]),
                      ("Policy", "Bind, upload, send", ["approved", "pb_policy", "sign_docs", "signed", "uploaded",
                                                        "uwc", "referred", "ho_confirm", "sent"])]

# the email template each email step opens ({type} = the client type, e.g. confirm-auto.html)
EMAIL_FOR_STEP = {"sign_docs": "sign-auto.html", "down_payment": "down-payment.html",
                  "billing": "billing-credit-card.html", "temp_pink": "temp-pink-card.html",
                  "sent": "confirm-{type}.html"}
# steps that wait on someone else: they don't hold up the next step
WAITING = {"mvr", "documents"}

PROCESSES = {
    "Auto": {"steps": AUTO_STEPS, "stages": STAGES, "email": EMAIL_FOR_STEP, "waiting": WAITING},
    "Home": {"steps": HOME_STEPS, "stages": _HOME_STAGES, "waiting": {"documents", "hits", "signed"},
             "email": {"sign_docs": "sign-home.html", "sent": "confirm-home.html"}},
    "Tenant": {"steps": TENANT_STEPS, "stages": _TENANT_STAGES, "waiting": {"documents", "hits", "signed"},
               "email": {"sign_docs": "sign-tenant.html", "sent": "confirm-tenant.html"}},
    "Commercial": {"steps": COMMERCIAL_STEPS, "stages": _COMMERCIAL_STAGES, "waiting": {"documents", "signed"},
                   "email": {"sign_docs": "sign-commercial.html", "sent": "confirm-commercial.html"}},
}
# the optional client documents each process asks for in its "documents" step
CLIENT_DOCS = {"Auto": ("Driver's licence", "Ownership", "Bill of sale", "Winter tire photo", "Void cheque",
                        "Financing / lease"),
               "Commercial": ("Photos of the location", "Alarm certificate (ULC)", "Prior insurance and claims",
                              "Restaurant supplement", "Subcontractor insurance")}


def process(kind):
    """The steps / stages / emails of this client type, or None (Other: documents only)."""
    return PROCESSES.get(kind)


def steps_for(kind):
    p = process(kind)
    return p["steps"] if p else []


def stages_for(kind):
    """[(name, subtitle, [step ids])] - always three; Auto's when the type has no process."""
    p = process(kind)
    return p["stages"] if p else STAGES


def email_for(kind, step_id):
    p = process(kind)
    return (p["email"] if p else EMAIL_FOR_STEP).get(step_id)


def waiting_for(kind):
    p = process(kind)
    return p["waiting"] if p else WAITING


def load(folder):
    """The client's tracking.json (an empty dict when there is none)."""
    return _load(folder)


def _load(folder):
    try:
        return json.loads((Path(folder) / records.FILE).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def quote_refers(folder, docs, data=None, read=True):
    """{carrier: [refer messages]} on the newest quote, or None (no quote / not read yet).

    Reading a quote takes a moment, so the result is kept in tracking.json ("quote_refers", keyed
    on the file's name + time); the client list only uses the kept result (read=False).
    """
    quotes = docs.get("Quote (ARS)") or []
    if not quotes:
        return None
    q = quotes[-1]
    try:
        key = f"{q.name}|{int(q.stat().st_mtime)}"
    except OSError:
        return None
    data = _load(folder) if data is None else data
    kept = data.get("quote_refers") or {}
    if kept.get("key") == key:
        return kept.get("carriers", {})
    if not read:
        return None
    try:
        carriers = {c["name"]: [m for m in c["messages"] if review.carrier_message(m) == "refer"]
                    for c in quote.read(str(q)).get("carriers", [])}
    except Exception:
        return None
    fresh = records.load(folder)
    fresh["quote_refers"] = {"key": key, "carriers": carriers}
    records._write(folder, fresh)
    return carriers


RESULTS = ("Approved", "Approved with conditions", "Declined", "Call back")


def set_tick(folder, step_id, state):
    """state: "done", "na" or None (untick). Re-reads the file so others' ticks are kept."""
    data = records.load(folder)
    ticks = data.setdefault("checklist", {})
    if state is None:
        ticks.pop(step_id, None)
    else:
        ticks[step_id] = {"state": state, "by": records.who(),
                          "at": datetime.datetime.now().isoformat(timespec="minutes")}
    records._write(folder, data)


def status(folder, kind, docs, info, skip, read_quote=True, by_hand=None, data=None):
    """[(step, state, note)] - state: "done", "na", "todo"; note explains auto ticks / what's missing.

    docs: find_docs() result; info: client.json; skip: documents marked not needed;
    read_quote: False for the client list (only uses refer messages already read);
    by_hand: a set to collect the ids whose done / N/A comes from the broker's own tick (those can
    be unticked; ones the app ticked itself can't).
    data: the client's tracking.json if it was read already (saves a file read).
    """
    data = _load(folder) if data is None else data
    ticks = data.get("checklist", {})
    out = []
    for step in steps_for(kind):
        sid, _, _, auto, _, _ = step
        tick = ticks.get(sid, {}).get("state")
        state, note = "todo", ""
        if auto == "profile":
            missing = [w for w in ("licence #", "phone", "email")
                       if not info.get({"licence #": "dln"}.get(w, w))]
            if info.get("dln"):
                state = "done"
            if missing:
                note = f"{', '.join(missing).capitalize()} missing".replace(", " + missing[-1], " and " + missing[-1])                     if len(missing) > 1 else f"{missing[0].capitalize()} missing"
        elif auto == "policy" and records.bound_policy(data):
            p = records.bound_policy(data)
            state = "done"
            note = " ".join(x for x in (p.get("insurer"), p.get("policy_number")) if x)
        elif auto == "billing":
            p = records.bound_policy(data)
            if not p or "echelon" not in (p.get("insurer") or "").lower():
                state, note = "na", "Only for Echelon policies"
        elif auto == "consent" and docs.get("Client consent"):
            state, note = "done", "In the folder"
        elif auto == "dash" and docs.get("DASH report"):
            state, note = "done", "In the folder"
        elif auto == "quote" and docs.get("Quote (ARS)"):
            state, note = "done", "In the folder"
        elif auto == "uw_call":
            calls = sorted(data.get("uw_calls", []), key=lambda c: c.get("at", ""))
            refers = quote_refers(folder, docs, data, read_quote) if docs.get("Quote (ARS)") else None
            if calls:
                last = calls[-1]
                if last.get("result") == "Call back":
                    note = f"Waiting for {last.get('carrier', 'the underwriter')} to call back"
                else:
                    state = "done"
                    note = f"{last.get('carrier', '')}: {last.get('result', '')}".strip(": ") +                         (f" - {last['underwriter']}" if last.get("underwriter") else "")
            elif refers is not None and not any(refers.values()) and not tick:
                state, note = "na", "No refer messages on the quote"
            elif refers:
                note = "Refer: " + ", ".join(c for c, m in refers.items() if m)
        elif auto == "mvr_request" and (info.get("mvr_requested") or docs.get("MVR")):
            state = "done"
            note = f"Sent {info['mvr_requested'][:10]}" if info.get("mvr_requested") else "MVR already received"
        elif auto == "mvr" and docs.get("MVR"):
            state, note = "done", "In the folder"
        elif auto == "documents":
            wanted = [k for k in CLIENT_DOCS.get(kind, ()) if k in docs and k not in skip]
            have = [k for k in wanted if docs[k]]
            if wanted and len(have) == len(wanted):
                state, note = "done", "All received"
            elif state == "todo":
                missing = [k for k in wanted if not docs[k]]
                note = "Missing: " + ", ".join(k.lower() for k in missing)
        elif auto == "profile_pc":
            missing = [w for w in ("phone", "email") if not info.get(w)]
            if info.get("name") or info.get("phone") or info.get("email"):
                state = "done" if not missing else "todo"
            if missing:
                note = " and ".join(missing).capitalize() + " missing"
        elif auto == "property":
            values = data.get(property_risk.KEY) or {}
            filled, total, lacking = property_risk.completeness(values)
            if values and not lacking:
                state, note = "done", "All answered"
            elif values:
                note = f"{filled} of {total} answered - missing: " + ", ".join(l.lower() for l in lacking[:4]) + \
                    ("..." if len(lacking) > 4 else "")
            else:
                note = "Not filled in yet"
        elif auto == "hits" and docs.get("HITS report"):
            state, note = "done", "In the folder"
        elif auto == "ezitv" and docs.get("EZITV (replacement cost)"):
            state, note = "done", "In the folder"
        elif auto == "commercial_app" and docs.get("Commercial application"):
            state, note = "done", "In the folder"
        elif auto == "documents_prop":
            values = data.get(property_risk.KEY) or {}
            if not values:
                note = "Fill in the property details to see what is needed"
            else:
                need = [k for k in property_risk.docs_needed(values) if k in docs and k not in skip]
                have = [k for k in need if docs[k]]
                if len(have) == len(need):
                    state, note = "done", "All received" if need else "Nothing extra needed"
                else:
                    note = "Missing: " + ", ".join(k for k in need if not docs[k])
        elif auto == "signed_docs":
            wanted = [k for k in ("Signed application", "PAC form + void cheque") if k in docs]
            missing = [k for k in wanted if not docs[k]]
            if wanted and not missing:
                state, note = "done", "In the folder"
            elif state == "todo" and wanted:
                note = "Missing: " + ", ".join(missing)
        elif auto == "limits":
            values = data.get(property_risk.KEY) or {}
            if values.get("wants_sewer") == "No" and values.get("wants_overland") == "No" and not tick:
                state, note = "na", "No sewer backup or overland water wanted"
        if tick in ("done", "na") and state == "todo":
            state = tick              # ticked by hand (e.g. DASH N/A for a new driver)
            if by_hand is not None:
                by_hand.add(sid)
        out.append((step, state, note))
    return out


def next_step(rows, kind):
    """The first step still to do, skipping the ones that wait on someone else (MVR, client documents)."""
    waiting = waiting_for(kind)
    return next(((st, s, note) for st, s, note in rows if s == "todo" and st[0] not in waiting), None)


def stage_of(step_id, kind):
    return next(i for i, (_, _, ids) in enumerate(stages_for(kind)) if step_id in ids)


def summary(rows, kind):
    """(done, total, next step title or None)."""
    done = sum(1 for _, s, _ in rows if s in ("done", "na"))
    nxt = next_step(rows, kind)
    return done, len(rows), nxt[0][1] if nxt else None


def current_stage(rows, kind):
    """Index of the stage the client is in (the next step's), or None when every step is done."""
    nxt = next_step(rows, kind)
    if nxt:
        return stage_of(nxt[0][0], kind)
    todo = next((st for st, s, _ in rows if s == "todo"), None)
    return stage_of(todo[0], kind) if todo else None
