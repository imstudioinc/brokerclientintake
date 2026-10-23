"""Review a client file: quote vs MVR vs DASH, WellCare's quote rules, and eligibility by market.

load() reads the PDFs (slow: OCR); analyze() does the checks (fast, re-run after edits).
Check statuses: "bad" (fix the quote), "refer" (underwriter / approval), "warn" (check with the
client), "todo" (carrier to-do), "info" (note), "ok" (matches).
"""
import datetime
from pathlib import Path

import eligibility
import mvr
import quote

IMAGES = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp")
# the MVR can be a photo / screenshot (read with OCR); DASH and quote are read from their PDF text
DOC_PATTERNS = {"dash": ["DASH Report*.pdf", "*DASH*.pdf"],
                "mvr": ["*MVR*.pdf"] + [f"*MVR*{e}" for e in IMAGES],
                "quote": ["*Quote*.pdf"]}


def find_docs(folder):
    """{kind: [paths newest first]} for DASH, MVR and Quote PDFs in the client folder."""
    folder, out = Path(folder), {}
    for kind, patterns in DOC_PATTERNS.items():
        seen = {}
        for pat in patterns:
            for p in folder.glob(pat):
                seen[p] = p.stat().st_mtime
        out[kind] = sorted(seen, key=seen.get, reverse=True)
    return out


def load(dash_path=None, mvr_path=None, quote_path=None):
    """Read the documents. Each part is None when the document is missing; errors go to "errors"."""
    data = {"dash": None, "mvr": None, "quote": None, "errors": []}
    if quote_path:
        try:
            data["quote"] = quote.read(quote_path)
        except Exception as e:
            data["errors"].append(f"Could not read the quote: {e}")
    today = (data["quote"] or {}).get("effective") or datetime.date.today()
    if dash_path:
        try:
            data["dash"] = eligibility.read_dash_facts(dash_path, today=today)
        except Exception as e:
            data["errors"].append(f"Could not read the DASH report: {e}")
    if mvr_path:
        try:
            data["mvr"] = mvr.read(mvr_path)
        except Exception as e:
            data["errors"].append(f"Could not read the MVR: {e}")
    data["today"] = today
    return data


def _norm(text):
    return "".join(ch for ch in (text or "").upper() if ch.isalnum())


def _years(since, today):
    return round((today - since).days / 365.25, 1) if since else None


def _close(a, b, days):
    return a and b and abs((a - b).days) <= days


def facts_from(data):
    """Eligibility facts from the documents (DASH, MVR convictions, licence years)."""
    today = data["today"]
    if data["dash"]:
        facts, details, notes = data["dash"]
        facts, notes = dict(facts), list(notes)
    else:
        details = {"claims": [], "policies": [], "gaps": []}
        facts = {k: 0 for k in eligibility.FACTS if k not in eligibility.MANUAL}
        facts.update(years_licensed=None, age=None)
        notes = ["No DASH report: treated as no insurance history (a new driver for the rules)."]
    m = data["mvr"]
    if m:
        g1 = m["dates"].get("g1")
        if g1:
            years = _years(g1, today)
            if facts.get("years_licensed") is not None and abs(years - facts["years_licensed"]) >= 2:
                notes.append(f"Years licensed: DASH says {facts['years_licensed']}, the MVR G1 date gives {years:g} - "
                             "using the MVR.")
            facts["years_licensed"] = years
        if m.get("birth"):
            b = m["birth"]
            facts["age"] = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        recent = [c for c in m["convictions"] if c["date"] and (today - c["date"]).days <= 3 * 365.25]
        for cat in ("minor", "major", "serious"):
            facts[f"{cat}_convictions_3y"] = len([c for c in recent if c["category"] == cat])
        facts["alcohol_convictions_3y"] = len([c for c in recent if c["alcohol"]])
    return facts, details, notes


def _principal(q, m):
    if not q or not q["drivers"]:
        return None
    if m and m.get("licence"):
        for d in q["drivers"]:
            if _norm(d["licence"]) == _norm(m["licence"]):
                return d
    return q["drivers"][0]


def line_of(data, folder_type=""):
    """Auto / Commercial from the client folder, else from the quote's vehicles."""
    if folder_type in ("Auto", "Commercial"):
        return folder_type
    types = [v["type"].lower() for v in (data["quote"] or {}).get("vehicles", [])]
    if types:
        return "Commercial" if any("commercial" in t for t in types) else "Auto"
    return None


def carrier_message(text):
    """Status for one carrier message: refer, todo, or None (noise like the quote number)."""
    t = text.lower()
    if t.startswith("quote successfully rated") or "http" in t or "quote number" in t or t.startswith("review "):
        return None
    if "refer" in t or "approval required" in t or "decline" in t or "underwriter" in t:
        return "refer"
    return "todo"


def checks(data, mvr_class=None):
    """[(status, text)] - quote vs MVR vs DASH, and WellCare's quote rules.

    Status: bad = fix the quote, refer = underwriter / approval, warn = check with the client,
    todo = carrier to-do, info = note, ok = matches.
    """
    out = []
    add = lambda status, text: out.append((status, text))  # noqa: E731
    q, m, today = data["quote"], data["mvr"], data["today"]
    dash_facts, details, _ = data["dash"] if data["dash"] else ({}, {}, [])
    for e in data["errors"]:
        add("bad", e)
    if not data["dash"]:
        add("info", "No DASH report - treated as no insurance history.")
    if not m:
        add("warn", "No MVR - convictions and licence dates not checked.")
    d = _principal(q, m)
    cls = ((mvr_class or (m or {}).get("class") or "")).upper()

    if m:
        for p in m["problems"]:
            add("warn", p)
        if m.get("status") and m["status"] != "LICENCED":
            add("bad", f"MVR status: {m['status']} - not licensed.")
        for a in m.get("actions", []):
            add("warn", f"MVR action {a['date']}: {a['description']}")
        if m.get("demerits"):
            add("info", f"{m['demerits']} demerit points on the MVR.")
        if cls and cls != "G" and m.get("issue") and (today - m["issue"]).days > 5 * 365:
            add("warn", f"Holds a {cls} but the licence was issued {m['issue']:%Y} - ask about the licence history.")
        if m["dates"].get("note") and "birthday" in m["dates"]["note"]:
            add("warn", "MVR can't give the G1 date (expiry isn't on the birthday) - get the licence history.")
        if not q:
            for c in m["convictions"]:
                add("info", f"Conviction {c['date']}: {c['description'].capitalize()} ({c['category']})")
    if q and len(q["drivers"]) > 1:
        add("info", f"{len(q['drivers'])} drivers on the quote - only {d['name'].title()} is checked here.")

    # ---------- identity ----------
    if d and m and m.get("licence"):
        add("ok" if _norm(d["licence"]) == _norm(m["licence"]) else "bad",
            f"Licence number: quote {d['licence'] or '-'}, MVR {m['licence']}")
    births = {"quote": d["birth"] if d else None, "MVR": m.get("birth") if m else None,
              "DASH": eligibility._date(details.get("dob")) if details.get("dob") else None}
    known = {k: v for k, v in births.items() if v}
    if len(known) >= 2:
        add("ok" if len(set(known.values())) == 1 else "bad",
            "Birth date: " + ", ".join(f"{k} {v}" for k, v in known.items()))

    # ---------- licence class and dates ----------
    if d and m:
        if cls:
            add("ok" if cls == d.get("class") else "bad",
                f"Licence class: quote {d.get('class') or '-'}, MVR {cls}" if cls != d.get("class")
                else f"Licence class {cls}")
        dates = mvr.licence_dates(m, cls) if cls else m["dates"]
        for key, label in (("g1", "G1"), ("g2", "G2"), ("g", "G")):
            mine, theirs = dates.get(key), d.get(key)
            if mine and theirs and mine == theirs:
                add("ok", f"{label} date {theirs}")
            elif mine and theirs:
                add("bad" if key != "g" else "warn", f"{label} date: quote {theirs}, MVR {mine}")
            elif mine and not theirs:
                add("bad", f"{label} date missing on the quote - MVR gives {mine}")
        held = {"G1": ["g1"], "G2": ["g1", "g2"]}.get(cls)
        if held:
            for key, label in (("g2", "G2"), ("g", "G")):
                if key not in held and d.get(key):
                    add("bad", f"Quote has a {label} date ({d[key]}) but the MVR class is {cls} - remove it.")
        if d.get("training"):
            add("info", f"Driver training {d.get('training_date') or ''} - certificate copy needed.")

    # ---------- convictions ----------
    if d and m:
        recent = [c for c in m["convictions"] if c["date"] and (today - c["date"]).days <= 3 * 365.25]
        for c in recent:
            hit = any(_close(qc["date"], c["date"], 3) or _close(qc["date"], c.get("offence_date"), 3)
                      for qc in d["convictions"])
            what = f"{c['date']} {c['description'].capitalize()} ({c['category']}{', alcohol' if c['alcohol'] else ''})"
            add("ok" if hit else "bad", f"Conviction {what}" if hit else f"Add conviction {what}")
        for qc in d["convictions"]:
            if not any(_close(qc["date"], c["date"], 3) or _close(qc["date"], c.get("offence_date"), 3)
                       for c in m["convictions"]):
                add("warn", f"Quote conviction {qc['date']} {qc['description']} isn't on the MVR")
        if recent and q and any("conviction free" in x.lower() for c in q["carriers"] for x in c["discounts"]):
            add("bad", "Remove the 'Conviction Free' discount - the MVR has convictions.")
        if not m["convictions"] and not d["convictions"]:
            add("ok", "No convictions")

    # ---------- claims ----------
    if d and data["dash"]:
        for c in details["claims"]:
            if (today - c["date"]).days > 6 * 365.25:
                continue
            match = next((qc for qc in d["claims"] if _close(qc["date"], c["date"], 3)), None)
            at_fault = c["fault"] > 25 and c["at_wheel"] is not False
            what = f"{c['date']} {c['insurer'].split()[0]} {c['coverage'] or ''}, {c['fault']}% at fault"
            if c["at_wheel"] is False:
                add("info", f"Claim {what} - {c['driver'].title()} was driving")
            elif not match:
                unnamed = " - DASH names no driver, ask" if c["at_wheel"] is None and at_fault else ""
                add("bad" if at_fault else "warn", f"Add claim {what}" + (" (chargeable)" if at_fault else "") + unnamed)
            elif match["charged"] != at_fault:
                add("bad" if at_fault else "warn", f"Claim {what}: quote has it as " +
                    ("chargeable" if match["charged"] else "not chargeable"))
            else:
                add("ok", f"Claim {what}")
        for qc in d["claims"]:
            if not any(_close(qc["date"], c["date"], 3) for c in details["claims"]):
                add("warn", f"Quote claim {qc['date']} {qc['description']} isn't on the DASH")

    # ---------- lapses and dates insured ----------
    if d and data["dash"]:
        for g in details.get("gaps", []):
            hit = any(_close(l["from"], g["from"], 31) or _close(l["to"], g["to"], 31) for l in d["lapses"])
            add("ok" if hit else "bad", f"Lapse {g['from']} to {g['to']}" if hit
                else f"Add lapse {g['from']} to {g['to']} (gap on DASH) with the reason")
        for l in d["lapses"]:
            if not any(_close(l["from"], g["from"], 31) or _close(l["to"], g["to"], 31) for g in details.get("gaps", [])):
                add("warn", f"Quote lapse {l['from']} to {l['to']} ({l['description']}) isn't a gap on the DASH")
        starts = [p["start"] for p in details["policies"] if p["start"]]
        if starts and d.get("date_insured"):
            first = min(starts)
            add("ok" if _close(first, d["date_insured"], 31) else "warn",
                f"First insured {first}" if _close(first, d["date_insured"], 31)
                else f"First insured: quote {d['date_insured']}, DASH {first}")
    if data["dash"]:
        for p in details["policies"]:
            if "active" in p["rest"].lower():
                add("info", f"Insured now with {p['rest'].replace(' Active', '').replace('*OVERLAP*', '').strip()} "
                            f"until {p['end']}")
    if d and d.get("date_insured") and not data["dash"]:
        add("warn", f"Quote says insured since {d['date_insured']} - no DASH to prove it.")

    # ---------- address ----------
    codes = {"quote": (q["vehicles"][0]["postal"] if q and q["vehicles"] else "") or (q or {}).get("postal", ""),
             "MVR": (m or {}).get("postal", ""), "DASH": details.get("postal", "")}
    codes = {k: _norm(v) for k, v in codes.items() if v}
    if len(set(codes.values())) > 1:
        add("warn", "Address: " + ", ".join(f"{k} {v}" for k, v in codes.items()) + " - confirm where the car is kept")

    # ---------- the quote itself ----------
    if q:
        for c in q["carriers"]:
            for msg in c["messages"]:
                status = carrier_message(msg)
                if status:
                    add(status, f"{c['name']}: {msg}")
        for v in q["vehicles"]:
            add_vehicle_checks(v, today, add)
    return out


def add_vehicle_checks(v, today, add):
    """WellCare in-house quote rules (note 01) for one vehicle."""
    cov = {k.lower(): val for k, val in v["coverages"].items()}

    def ded(key):
        try:
            return int(str(cov.get(key)).replace(",", ""))
        except (TypeError, ValueError):
            return None
    phys = [k for k in ("all perils", "collision", "comprehensive", "specified perils") if k in cov]
    if v.get("annual_km") is not None and v["annual_km"] <= 8000:
        add("refer", f"Annual km {v['annual_km']:,} (8,000 or less) - WellCare refer")
    if any((ded(k) or 0) > 1000 for k in phys):
        add("refer", "Deductible over $1,000 - WellCare refer")
    if any(k.startswith("#28") for k in cov):
        add("refer", "OPCF 28/28A - refer to the insurer and WellCare")
    if (v.get("list_price") or 0) >= 150000:
        add("refer", f"Vehicle ${v['list_price']:,} ($150,000+) - WellCare refer")
    if ("all perils" in cov or "collision" in cov) and not any(k.startswith("#20") for k in cov):
        add("warn", "Offer OPCF 20 (loss of use, min $1,500)")
    if "accident waiver" not in cov:
        add("warn", "Offer the accident waiver (OPCF 39)")
    if (ded("direct compensation") or 0) > 0:
        add("warn", "DCPD deductible isn't $0")
    age = today.year - v["year"] if v.get("year") else None
    if age is not None and age < 2 and not any(k.startswith("#43") for k in cov):
        add("warn", "Offer OPCF 43 (vehicle under 2 years old)")
    if age is not None and age < 3 and not phys:
        add("warn", "New vehicle with liability only - confirm the client declined collision / comprehensive")
    if any(k.startswith("#23") for k in cov):
        add("info", "Lienholder (OPCF 23A) - get the lender's details and financing papers")
    if v.get("purchase_price") and v.get("list_price") and v["purchase_price"] > v["list_price"] * 1.1:
        add("warn", f"Purchase price ${v['purchase_price']:,} is above the list price new ${v['list_price']:,}")


def recommend(results, q):
    """Quoted carriers with the rules' verdict, and the markets that fit by the rules."""
    by_name = {r["market"].split()[0].lower(): r for r in results}
    quoted = []
    for c in (q or {}).get("carriers", []):
        r = next((r for key, r in by_name.items() if key in c["name"].lower()), None)
        quoted.append({"carrier": c["name"], "premium": c["premium"], "verdict": r["verdict"] if r else None,
                       "messages": len([m for m in c["messages"] if carrier_message(m)])})
    # standard markets first; non-standard only when no standard market fits
    # (a market that only needs a referral still counts - e.g. a new driver at Intact)
    for ok in (("Proceed", "Caution"), ("Refer to underwriter",)):
        for tier in ("standard", "non-standard", "commercial", ""):
            fits = [r for r in results if r.get("tier", "") == tier and r["verdict"] in ok]
            if fits:
                return quoted, fits
    return quoted, []
