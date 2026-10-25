"""The broker's step-by-step checklist for a client (Auto for now).

Some steps tick themselves from what is in the client folder (DASH, quote, MVR, documents) or
in client.json (licence #, MVR request sent). The rest - PowerBroker, UW-Compass - the broker
ticks. Ticks are saved in the client's tracking.json under "checklist" (shared folder: everyone
sees them). A step can also be marked N/A where that makes sense (no DASH for a new driver,
no referral needed).
"""
import datetime
import json
from pathlib import Path

import quote
import records
import review

# (id, title, hint, auto, can_be_na, action)
#   auto: key of an automatic check below, or None (ticked by hand)
#   action: what the step's button does in the app (None = no button)
AUTO_STEPS = [
    ("profile", "Client profile", "Name and driver's licence #. Phone and email can follow - add them when you get them.",
     "profile", False, "edit"),
    ("dash", "DASH report", "Pull the DASH report if the client has insurance history.", "dash", True, "dash"),
    ("quote", "First quote in ARS", "Quote in Applied Rating and save the Quote Information PDF in the folder.",
     "quote", False, None),
    ("uw_call", "Refer messages confirmed with the underwriter", "The quote has refer messages: call the "
     "underwriter, confirm the client is eligible, and log the call (who, when, why, result).", "uw_call", True,
     "uwcall"),
    ("mvr_request", "MVR request sent", "Email the branch manager for the MVR (address set in Settings).",
     "mvr_request", False, "mvr"),
    ("mvr", "MVR received", "Saved to the folder automatically when you download it from Outlook.", "mvr", False, None),
    ("requote", "Quote corrected and re-run", "Fix ARS with the DASH and MVR (Review quote shows what's wrong), "
     "then quote again.", None, False, "review"),
    ("documents", "Documents from the client", "Ownership, void cheque (most clients pay monthly), winter tire "
     "photos, bill of sale, financing papers - ask while you quote.", "documents", False, None),
    ("approved", "Client approved; quote exported to PowerBroker", "Agree how the client pays: the carrier's "
     "payment terms and WellCare's payment options are on the Carriers page.", None, False, "payments"),
    ("pb_policy", "Policy set up in PowerBroker", "", None, False, None),
    ("pb_app", "Application created in PowerBroker", "Paste the REMARKS text from UW-Compass into the application.",
     None, False, None),
    ("uwc", "Application filled and submitted on UW-Compass", "Submit when everything looks fine.", None, False, None),
    ("referred", "Referred (if UW-Compass shows a refer message)", "Refer to head office or the insurer - "
     "mark N/A if there was nothing to refer.", None, True, None),
]


# the steps in three stages; a finished stage folds into one line in the app
PHASES = [("Intake", ["profile", "dash", "quote", "uw_call", "mvr_request", "mvr"]),
          ("Quote", ["requote", "documents"]),
          ("Bind", ["approved", "pb_policy", "pb_app", "uwc", "referred"])]


def steps_for(kind):
    return AUTO_STEPS if kind == "Auto" else []


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


def status(folder, kind, docs, info, skip, read_quote=True):
    """[(step, state, note)] - state: "done", "na", "todo"; note explains auto ticks / what's missing.

    docs: find_docs() result; info: client.json; skip: documents marked not needed;
    read_quote: False for the client list (only uses refer messages already read).
    """
    data = _load(folder)
    ticks = data.get("checklist", {})
    out = []
    for step in steps_for(kind):
        sid, _, _, auto, _, _ = step
        tick = ticks.get(sid, {}).get("state")
        state, note = (tick, "") if tick else ("todo", "")
        if auto == "profile":
            missing = [w for w in ("licence #", "phone", "email")
                       if not info.get({"licence #": "dln"}.get(w, w))]
            if info.get("dln"):
                state = "done"
            if missing:
                note = f"{', '.join(missing).capitalize()} missing".replace(", " + missing[-1], " and " + missing[-1])                     if len(missing) > 1 else f"{missing[0].capitalize()} missing"
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
            wanted = [k for k in ("Driver's licence", "Ownership", "Bill of sale", "Winter tire photo", "Void cheque",
                                  "Financing / lease") if k in docs and k not in skip]
            have = [k for k in wanted if docs[k]]
            if wanted and len(have) == len(wanted):
                state, note = "done", "All received"
            elif state == "todo":
                missing = [k for k in wanted if not docs[k]]
                note = "Missing: " + ", ".join(k.lower() for k in missing)
        if tick and auto and state != "done" and tick in ("done", "na"):
            state = tick              # ticked by hand (e.g. DASH N/A for a new driver)
        out.append((step, state, note))
    return out


def summary(rows):
    """(done, total, next step title or None)."""
    done = sum(1 for _, s, _ in rows if s in ("done", "na"))
    nxt = next((st[1] for st, s, _ in rows if s == "todo" and st[0] != "documents"), None)
    return done, len(rows), nxt
