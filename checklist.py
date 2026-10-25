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

import records

# (id, title, hint, auto, can_be_na, action)
#   auto: key of an automatic check below, or None (ticked by hand)
#   action: what the step's button does in the app (None = no button)
AUTO_STEPS = [
    ("profile", "Client profile", "Name and driver's licence #. Phone and email can follow - add them when you get them.",
     "profile", False, "edit"),
    ("dash", "DASH report", "Pull the DASH report if the client has insurance history.", "dash", True, "dash"),
    ("quote", "First quote in ARS", "Quote in Applied Rating and save the Quote Information PDF in the folder.",
     "quote", False, None),
    ("mvr_request", "MVR request sent", "Email the branch manager for the MVR (address set in Settings).",
     "mvr_request", False, "mvr"),
    ("mvr", "MVR received", "Saved to the folder automatically when you download it from Outlook.", "mvr", False, None),
    ("requote", "Quote corrected and re-run", "Fix ARS with the DASH and MVR (Review quote shows what's wrong), "
     "then quote again.", None, False, "review"),
    ("documents", "Documents from the client", "Ownership, void cheque (most clients pay monthly), winter tire "
     "photos, bill of sale, financing papers - ask while you quote.", "documents", False, None),
    ("approved", "Client approved; quote exported to PowerBroker", "", None, False, None),
    ("pb_policy", "Policy set up in PowerBroker", "", None, False, None),
    ("pb_app", "Application created in PowerBroker", "Paste the REMARKS text from UW-Compass into the application.",
     None, False, None),
    ("uwc", "Application filled and submitted on UW-Compass", "Submit when everything looks fine.", None, False, None),
    ("referred", "Referred (if UW-Compass shows a refer message)", "Refer to head office or the insurer - "
     "mark N/A if there was nothing to refer.", None, True, None),
]


def steps_for(kind):
    return AUTO_STEPS if kind == "Auto" else []


def _load_ticks(folder):
    try:
        data = json.loads((Path(folder) / records.FILE).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data.get("checklist", {})


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


def status(folder, kind, docs, info, skip):
    """[(step, state, note)] - state: "done", "na", "todo"; note explains auto ticks / what's missing.

    docs: find_docs() result; info: client.json; skip: documents marked not needed.
    """
    ticks = _load_ticks(folder)
    out = []
    for step in steps_for(kind):
        sid, _, _, auto, _, _ = step
        tick = ticks.get(sid, {}).get("state")
        state, note = (tick, "") if tick else ("todo", "")
        if auto == "profile":
            missing = [w for w, k in (("phone", "phone"), ("email", "email")) if not info.get(k)]
            if info.get("dln"):
                state = "done"
            else:
                note = "Licence # missing - click Edit"
            if missing:
                note = f"{' and '.join(missing).capitalize()} still missing"
        elif auto == "dash" and docs.get("DASH report"):
            state, note = "done", "In the folder"
        elif auto == "quote" and docs.get("Quote (ARS)"):
            state, note = "done", "In the folder"
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
