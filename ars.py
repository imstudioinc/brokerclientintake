"""What to type into Applied Rating (ARS) from a DASH report: the Claims form, one entry per
claim, and the insurance history (prior insurer, first insured, lapses, cancellations).

ARS Claims form: Date, Description (dropdown), Vehicle Involved, Chargeable (At-Fault /
Non-Responsible), TP/BI $, TP/PD $, AB $, Coll $, Other PD $. Amounts are losses only (no expenses).
Guidance only - the broker checks each entry against the DASH.
"""
import datetime
import re

LOOKBACK_YEARS = 6               # claims
CONVICTION_YEARS = 3             # convictions (the conviction date counts, not the offence date)
AMOUNTS = (("tp_bi", "TP/BI $"), ("tp_pd", "TP/PD $"), ("ab", "AB $"), ("coll", "Coll $"), ("other_pd", "Other PD $"))
AB_CODES = set(range(40, 50)) | set(range(80, 90))
DCPD_CODES = {16, 18}
STATUS = re.compile(r"\s*(?:\*OVERLAP\*\s*)?(Active|Expired|Cancelled.*|Not available)\s*$", re.I)


def ars_date(d):
    """ARS dates are MM/DD/YYYY."""
    return d.strftime("%m/%d/%Y") if d else ""


def money(x):
    return f"{x:,.0f}" if x else ""


def _bucket(k):
    """Which ARS amount field a DASH KOL line goes in."""
    what = k["what"].lower()
    if k["code"] in AB_CODES:
        return "ab"
    if k["code"] == 20 or what.startswith("collision"):
        return "coll"
    if "bodily injury" in what:
        return "tp_bi"
    if "property damage" in what and "insured vehicle" not in what:
        return "tp_pd"
    return "other_pd"


def vehicle_name(text):
    """'2019 HYUNDAI - ELANTRA LUXURY 4DR / ELANTRA ULTIMATE 4DR - KMHD84LF1KU864872'
    -> ('2019 Hyundai Elantra Luxury 4DR', 'KMHD84LF1KU864872')."""
    vin = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", text or "")
    rest = (text or "").replace(vin.group(1), "") if vin else (text or "")
    parts = [p.strip() for p in rest.split(" - ") if p.strip(" -")]
    year_make = parts[0] if parts else ""
    model = parts[1].split(" / ")[0] if len(parts) > 1 else ""
    words = [w.capitalize() if w.isalpha() and len(w) > 3 else w for w in f"{year_make} {model}".split()]
    name, vin = " ".join(words).strip(" -"), vin.group(1) if vin else ""
    if vin and not re.search(r"[A-Za-z]", name):        # DASH gave only the year and VIN
        name = f"{name} VIN {vin}".strip()
    return name, vin


def _description(c, amounts):
    """The ARS Description dropdown value for a claim."""
    codes = {k["code"] for k in c["kols"]}
    whats = " ".join(k["what"].lower() for k in c["kols"])
    cov = c["coverage"].upper()
    if c["fault"] > 0:
        third = amounts["tp_pd"] or amounts["tp_bi"] or cov in ("TP-BI", "TP-PD")
        own = amounts["coll"] or cov in ("CL", "AP") and not third
        if own and third:
            return "Liability & Collision"
        return "Collision" if own else "Liability"
    if codes & DCPD_CODES or cov == "DCPD":
        return "Non-resp Direct Compensation"
    if amounts["coll"] or 20 in codes:
        return "Non-responsible Collision"
    if (codes and codes <= AB_CODES) or cov == "AB":
        return "Non-responsible Accident Ben."
    if "glass" in whats or 26 in codes:
        return "Glass Breakage"
    if "theft" in whats:
        whole = "entire" in whats or c["vehicle_loss"].lower() == "total" and "contents" not in whats
        return "Theft - Entire Vehicle" if whole else "Theft"
    if "vandal" in whats or "mischief" in whats:
        return "Vandalism"
    if "fire" in whats:
        return "Fire"
    if "hail" in whats:
        return "Hail"
    return "Other non-responsible Comp/SP"


def _same_person(a, b):
    a, b = set(a.upper().replace(",", "").split()), set(b.upper().replace(",", "").split())
    return bool(a) and bool(b) and (a <= b or b <= a)


def claims(details, today=None):
    """One ARS Claims entry per claim on the DASH, newest first."""
    today = today or datetime.date.today()
    try:
        cutoff = today.replace(year=today.year - LOOKBACK_YEARS)
    except ValueError:
        cutoff = today.replace(year=today.year - LOOKBACK_YEARS, day=28)
    dates = [c["date"] for c in details["claims"]]
    out = []
    for c in details["claims"]:
        amounts = {key: 0.0 for key, _ in AMOUNTS}
        for k in c["kols"]:
            amounts[_bucket(k)] += k["loss"]
        vehicle, vin = vehicle_name(c["vehicle"])
        notes = []
        old = c["date"] < cutoff
        if old:
            notes.append(f"Older than {LOOKBACK_YEARS} years - don't enter it.")
        if c["status"].lower() == "open":
            notes.append("Still OPEN - amounts may go up.")
        if any(k["reserve"] for k in c["kols"]):
            notes.append("Amount includes a RESERVE (not paid yet).")
        driver = c["driver"] if c["driver"] and c["driver"].lower() != "not available" else ""
        if not driver and c["fault"] > 0:
            notes.append("DASH names no driver - ask who was driving.")
        elif driver and details.get("driver") and not _same_person(driver, details["driver"]):
            notes.append(f"{driver.title()} was driving, not this client - check how the insurer wants it entered.")
        if 0 < c["fault"] < 100:
            notes.append(f"Partly at fault ({c['fault']}%).")
        if not c["kols"]:
            notes.append("No payment lines on the DASH - amounts left blank.")
        elif not any(amounts.values()):
            notes.append("Nothing paid ($0).")
        if amounts["ab"] and any(k["expense"] for k in c["kols"] if _bucket(k) == "ab"):
            total = sum(k["loss"] + k["expense"] for k in c["kols"] if _bucket(k) == "ab")
            notes.append(f"AB loss + expense = ${total:,.0f} (if the insurer wants the total).")
        if dates.count(c["date"]) > 1:
            notes.append("Another claim has the same date of loss - may be the same accident; enter it once.")
        out.append({
            "date": ars_date(c["date"]), "description": _description(c, amounts), "vehicle": vehicle, "vin": vin,
            "chargeable": "At-Fault" if c["fault"] > 0 else "Non-Responsible",
            "amounts": {key: money(v) for key, v in amounts.items()},
            "insurer": c["insurer"], "claim_no": c["claim_no"], "coverage": c["coverage"], "fault": c["fault"],
            "status": c["status"], "driver": driver.title(), "old": old, "notes": notes,
            "expense": money(sum(k["expense"] for k in c["kols"])),
        })
    out.sort(key=lambda e: e["old"])          # still newest first within each group
    return out


def _insurer_status(rest):
    m = STATUS.search(rest)
    return (rest[:m.start()].replace("*OVERLAP*", "").strip(), m.group(1).strip()) if m else (rest.strip(), "")


def history(details, today=None):
    """Insurance history for the ARS driver / prior-insurance screens."""
    today = today or datetime.date.today()
    pols = [dict(p, insurer=_insurer_status(p["rest"])[0], status=_insurer_status(p["rest"])[1])
            for p in details["policies"] if p["start"]]
    out = {"current": None, "first_insured": "", "continuous_since": "", "lapses": [], "cancellations": [],
           "policies": pols, "uninsured_since": ""}
    if not pols:
        return out
    newest = pols[0]
    out["current"] = newest
    out["first_insured"] = ars_date(min(p["start"] for p in pols))
    active = newest["status"].lower() == "active" or (newest["end"] and newest["end"] >= today)
    if not active:
        out["uninsured_since"] = ars_date(newest["end"])
    # continuous run: newest policy back to the first gap the DASH marks
    gap_after = {g["to"] for g in details["gaps"]}
    since = newest["start"]
    for older, newer in zip(pols[1:], pols):
        if newer["start"] in gap_after:
            break
        since = min(since, older["start"])
    out["continuous_since"] = ars_date(since) if active else ""
    for g in details["gaps"]:
        days = (g["to"] - g["from"]).days if g["to"] and g["from"] else 0
        out["lapses"].append({"from": ars_date(g["from"]), "to": ars_date(g["to"]), "days": days,
                              "months": max(1, round(days / 30.4)) if days else 0})
    for p in pols:
        if p["status"].lower().startswith("cancel"):
            reason = p["status"].split("-", 1)[1].strip() if "-" in p["status"] else ""
            out["cancellations"].append({"date": ars_date(p["end"]), "insurer": p["insurer"], "reason": reason})
    return out


# ---------- from the MVR: the driver, the convictions, the suspensions ----------
def _nice_name(name):
    """'DOE, JOHN ALEX' -> ('John Alex', 'Doe')."""
    if "," in (name or ""):
        last, first = [x.strip() for x in name.split(",", 1)]
    else:
        parts = (name or "").split()
        first, last = " ".join(parts[:-1]), parts[-1] if parts else ""
    return first.title(), last.title()


def licence_text(number):
    """A1234-12345-12345 (the number as Ontario prints it)."""
    n = re.sub(r"[^A-Z0-9]", "", (number or "").upper())
    return f"{n[0]}{n[1:5]}-{n[5:10]}-{n[10:15]}" if len(n) == 15 else number or ""


def driver(m, details=None):
    """The driver's licence facts for the ARS driver screen, from the MVR (and the DASH for the name)."""
    details = details or {}
    first, last = _nice_name(m.get("name") or details.get("driver") or "")
    dates = m.get("dates") or {}
    out = {"first": first, "last": last, "birth": ars_date(m.get("birth")), "licence": licence_text(m.get("licence")),
           "class": m.get("class") or "", "status": m.get("status") or "", "demerits": m.get("demerits"),
           "issue": ars_date(m.get("issue")), "expiry": ars_date(m.get("expiry")),
           "g1": ars_date(dates.get("g1")), "g2": ars_date(dates.get("g2")), "g": ars_date(dates.get("g")),
           "notes": []}
    if dates.get("note"):
        out["notes"].append(dates["note"])
    for problem in m.get("problems", []):
        out["notes"].append(problem)
    if out["status"] and out["status"] != "LICENCED":
        out["notes"].append(f"MVR status is {out['status']} - not licensed.")
    return out


def convictions(m, today=None):
    """One ARS Convictions entry per MVR conviction, newest first; older than 3 years = don't enter."""
    today = today or datetime.date.today()
    try:
        cutoff = today.replace(year=today.year - CONVICTION_YEARS)
    except ValueError:
        cutoff = today.replace(year=today.year - CONVICTION_YEARS, day=28)
    out = []
    for c in sorted(m.get("convictions", []), key=lambda c: c["date"] or datetime.date.min, reverse=True):
        old = bool(c["date"] and c["date"] < cutoff)
        notes = []
        if old:
            notes.append(f"Older than {CONVICTION_YEARS} years - don't enter it.")
        if old:
            pass
        elif c.get("alcohol"):
            notes.append("Alcohol / drug related - insurers count these separately.")
        if old:
            pass
        elif c["category"] == "major":
            notes.append("MAJOR conviction - most standard markets refer or decline.")
        elif c["category"] == "serious" and not old:
            notes.append("SERIOUS conviction - refer to the underwriter.")
        out.append({"date": ars_date(c["date"]), "description": c["description"].capitalize(),
                    "category": c["category"].capitalize(), "offence": ars_date(c.get("offence_date")),
                    "old": old, "notes": notes})
    return out


def suspensions(m):
    """Licence actions on the MVR (suspensions, cancellations ...), for the Suspensions form."""
    return [{"date": ars_date(a["date"]), "description": a["description"].capitalize()} for a in m.get("actions", [])]


def as_text(entries, hist, drv=None, convs=None, susp=None):
    """Plain text of everything (for a note or to paste somewhere). entries / hist None = no DASH,
    drv / convs None = no MVR (those sections are left out)."""
    lines = []
    if drv:
        lines += ["DRIVER (MVR)", f"{drv['first']} {drv['last']} - born {drv['birth']} - licence {drv['licence']}",
                  f"Class {drv['class']} - G1 {drv['g1'] or '?'}, G2 {drv['g2'] or '-'}, G {drv['g'] or '-'}", ""]
    if entries is not None:
        lines.append("CLAIMS (ARS)")
        shown = [e for e in entries if not e["old"]]
        for i, e in enumerate(shown, 1):
            amts = ", ".join(f"{label} {e['amounts'][k]}" for k, label in AMOUNTS if e["amounts"][k])
            lines.append(f"{i}. {e['date']} - {e['description']} - {e['chargeable']} - {e['vehicle']}"
                         + (f" - {amts}" if amts else "") + f" ({e['insurer']}, claim {e['claim_no'] or '?'})")
        if not shown:
            lines.append(f"None in the last {LOOKBACK_YEARS} years.")
        lines.append("")
    if convs is not None:
        lines.append("CONVICTIONS (ARS)")
        shown = [c for c in convs if not c["old"]]
        for i, c in enumerate(shown, 1):
            lines.append(f"{i}. {c['date']} - {c['description']} ({c['category']})")
        if not shown:
            lines.append(f"None in the last {CONVICTION_YEARS} years.")
        for s in susp or []:
            lines.append(f"Licence action {s['date']}: {s['description']}")
        lines.append("")
    if hist is not None:
        lines.append("INSURANCE HISTORY")
        cur = hist["current"]
        if cur:
            lines.append(f"Latest policy: {cur['insurer']} {ars_date(cur['start'])} to {ars_date(cur['end'])} ({cur['status']})")
            lines.append(f"First insured: {hist['first_insured']}")
            if hist["continuous_since"]:
                lines.append(f"Continuously insured since: {hist['continuous_since']}")
            if hist["uninsured_since"]:
                lines.append(f"Not insured since: {hist['uninsured_since']}")
        else:
            lines.append("No policies on the DASH (no insurance history).")
        for g in hist["lapses"]:
            lines.append(f"Lapse: {g['from']} to {g['to']} ({g['months']} months, {g['days']} days)")
        for c in hist["cancellations"]:
            lines.append(f"Cancelled {c['date']} by {c['insurer']}" + (f" - {c['reason']}" if c["reason"] else ""))
    return "\n".join(lines).strip()
