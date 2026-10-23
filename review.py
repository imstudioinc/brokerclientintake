"""Review a client file: quote vs MVR vs DASH, WellCare's quote rules, and eligibility by market.

load() reads the PDFs (slow: OCR); analyze() does the checks (fast, re-run after edits).
Check statuses: "ok", "info", "warn" (check / caution), "bad" (wrong or missing - fix the quote),
"refer" (needs an underwriter).
"""
import datetime
from pathlib import Path

import eligibility
import mvr
import quote

DOC_PATTERNS = {"dash": ["DASH Report*.pdf", "*DASH*.pdf"], "mvr": ["*MVR*.pdf", "*mvr*.pdf"],
                "quote": ["*Quote*.pdf", "*quote*.pdf"]}


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


def checks(data, mvr_class=None):
    """[(status, text)] - quote vs MVR vs DASH, and WellCare's quote rules."""
    out = []
    add = lambda status, text: out.append((status, text))  # noqa: E731
    q, m, today = data["quote"], data["mvr"], data["today"]
    dash_facts, details, _ = data["dash"] if data["dash"] else ({}, {}, [])
    for e in data["errors"]:
        add("bad", e)
    if not data["dash"]:
        add("info", "No DASH report - treated as no insurance history. If the client was insured in Canada or the "
                    "US before, pull the DASH (the quote would then need the claims and dates insured).")
    if not m:
        add("warn", "No MVR - convictions, licence class and licence dates are not checked.")
    if not q:
        add("info", "No quote - only eligibility by market is checked.")
    d = _principal(q, m)
    if m:
        for p in m["problems"]:
            add("warn", p)
        if m.get("status") and m["status"] != "LICENCED":
            add("bad", f"MVR licence status is {m['status']} - not licensed.")
        if m.get("demerits"):
            add("info", f"{m['demerits']} demerit point(s) on the MVR.")
        for a in m.get("actions", []):
            add("warn", f"MVR action {a['date']}: {a['description']} - check for a suspension.")
        cls = (mvr_class or m.get("class") or "").upper()
        if cls and cls != "G":
            add("info", f"MVR class {cls} - not a full G licence" +
                (f", although the licence was issued {m['issue']} - ask about the licence history (an expired G2 "
                 "means starting over)." if m.get("issue") and (today - m["issue"]).days > 5 * 365 else "."))
        if not q:
            if m["dates"].get("note"):
                add("warn", m["dates"]["note"] + (f" DASH says {dash_facts['years_licensed']} year(s) licensed."
                                                  if dash_facts.get("years_licensed") is not None else ""))
            for c in m["convictions"]:
                add("info", f"MVR conviction {c['date']} {c['description']} ({c['category']}"
                            f"{', alcohol' if c['alcohol'] else ''})")
    if q and len(q["drivers"]) > 1:
        add("info", f"The quote has {len(q['drivers'])} drivers - these checks use {d['name']}'s MVR / DASH. "
                    "Check the other drivers' reports too.")

    # ---------- identity ----------
    if d and m and m.get("licence"):
        add("ok" if _norm(d["licence"]) == _norm(m["licence"]) else "bad",
            f"Licence number: quote {d['licence'] or '-'}, MVR {m['licence']}")
    if d and details.get("dln") and not m:
        add("ok" if _norm(d["licence"]) == _norm(details["dln"]) else "bad",
            f"Licence number: quote {d['licence'] or '-'}, DASH {details['dln']}")
    births = {"quote": d["birth"] if d else None, "MVR": m.get("birth") if m else None,
              "DASH": eligibility._date(details.get("dob")) if details.get("dob") else None}
    known = {k: v for k, v in births.items() if v}
    if len(known) >= 2:
        add("ok" if len(set(known.values())) == 1 else "bad",
            "Birth date: " + ", ".join(f"{k} {v}" for k, v in known.items()))

    # ---------- licence class and dates ----------
    if d and m:
        cls = (mvr_class or m.get("class") or "").upper()
        if cls:
            add("ok" if cls == d.get("class") else "bad", f"Licence class: quote {d.get('class') or '-'}, MVR {cls}")
        dates = mvr.licence_dates(m, cls) if cls else m["dates"]
        if dates.get("note"):
            add("info", dates["note"])
        for key, label in (("g1", "G1"), ("g2", "G2"), ("g", "G")):
            mine, theirs = dates.get(key), d.get(key)
            if mine and theirs:
                if mine == theirs:
                    add("ok", f"{label} date: quote {theirs} matches the MVR")
                else:
                    how = {"g1": "the MVR issue date", "g2": "G1 + 1 year", "g": "G2 + 1 year"}[key]
                    add("bad" if key != "g" else "warn",
                        f"{label} date: quote {theirs}, MVR gives {mine} ({how}) - correct the quote or confirm with "
                        "the licence history (an earlier date can lower the rate).")
            elif mine and not theirs:
                add("bad", f"{label} date missing on the quote - MVR gives {mine}.")
            elif theirs and not mine and dates.get("g1") and key != "g1":
                add("warn", f"Quote has a {label} date ({theirs}) but the MVR class is {cls} - check.")
        if d.get("training"):
            add("info", f"Driver training on the quote ({d.get('training_date') or 'no date'}) - the certificate "
                        "copy is required (Intact honours it for 3 years).")

    # ---------- convictions ----------
    if d and m:
        recent = [c for c in m["convictions"] if c["date"] and (today - c["date"]).days <= 3 * 365.25]
        for c in recent:
            hit = any(_close(qc["date"], c["date"], 3) or _close(qc["date"], c.get("offence_date"), 3)
                      for qc in d["convictions"])
            tag = c["category"] + (", alcohol" if c["alcohol"] else "")
            add("ok" if hit else "bad", f"MVR conviction {c['date']} {c['description']} ({tag})" +
                ("" if hit else " is not on the quote - add it."))
        for qc in d["convictions"]:
            if not any(_close(qc["date"], c["date"], 3) or _close(qc["date"], c.get("offence_date"), 3)
                       for c in m["convictions"]):
                add("warn", f"Quote conviction {qc['date']} {qc['description']} is not on the MVR - check.")
        if recent and q and any("conviction free" in x.lower() for c in q["carriers"] for x in c["discounts"]):
            add("bad", "Quote gives a 'Conviction Free' discount, but the MVR has convictions in the last 3 years.")
        if not m["convictions"] and not d["convictions"]:
            add("ok", "Convictions: none on the MVR or the quote")

    # ---------- claims ----------
    if d and data["dash"]:
        for c in details["claims"]:
            if (today - c["date"]).days > 6 * 365.25:
                continue
            match = next((qc for qc in d["claims"] if _close(qc["date"], c["date"], 3)), None)
            at_fault = c["fault"] > 25 and c["at_wheel"] is not False
            label = f"DASH claim {c['date']} {c['insurer']} ({c['fault']}% at fault, {c['coverage'] or '?'})"
            if c["at_wheel"] is False:
                add("info", f"{label}: {c['driver'].title()} was driving - not this driver's claim.")
            elif not match:
                add("bad" if at_fault else "warn", f"{label} is not on the quote - add it" +
                    (" as at-fault." if at_fault else " (not at fault)."))
            elif match["charged"] != at_fault:
                add("bad" if at_fault else "warn", f"{label}: the quote has it as " +
                    ("chargeable" if match["charged"] else "not chargeable") + " - check.")
            else:
                add("ok", f"{label} is on the quote")
        for qc in d["claims"]:
            if not any(_close(qc["date"], c["date"], 3) for c in details["claims"]):
                add("warn", f"Quote claim {qc['date']} {qc['description']} is not on the DASH report - check.")

    # ---------- lapses and dates insured ----------
    if d and data["dash"]:
        for g in details.get("gaps", []):
            hit = any(_close(l["from"], g["from"], 31) or _close(l["to"], g["to"], 31) for l in d["lapses"])
            add("ok" if hit else "bad", f"DASH gap {g['from']} to {g['to']}" +
                (" is on the quote as a lapse" if hit else " is not on the quote - add the lapse and its reason."))
        starts = [p["start"] for p in details["policies"] if p["start"]]
        if starts and d.get("date_insured"):
            first = min(starts)
            add("ok" if _close(first, d["date_insured"], 31) else "warn",
                f"Date first insured: quote {d['date_insured']}, DASH {first}")
    if data["dash"]:
        active = [p for p in details["policies"] if "active" in p["rest"].lower()]
        for p in active:
            add("info", f"Insured now: {p['rest'].replace(' Active', '')} until {p['end']} (DASH).")
    if d and d.get("date_insured") and not data["dash"]:
        add("warn", f"The quote says insured since {d['date_insured']}, but there is no DASH report to prove it.")

    # ---------- address ----------
    codes = {"quote": (q or {}).get("postal") or (q["vehicles"][0]["postal"] if q and q["vehicles"] else ""),
             "MVR": (m or {}).get("postal", ""), "DASH": details.get("postal", "")}
    codes = {k: _norm(v) for k, v in codes.items() if v}
    if len(set(codes.values())) > 1:
        add("warn", "Postal codes differ: " + ", ".join(f"{k} {v}" for k, v in codes.items()) +
            " - confirm where the car is garaged (it sets the territory). An MVR address change is due within 6 days of moving.")

    # ---------- the quote itself ----------
    if q:
        for c in q["carriers"]:
            for msg in c["messages"]:
                if msg.lower().startswith("quote successfully rated"):
                    continue
                add("refer" if msg.lower().startswith("refer") else "warn", f"{c['name']} message: {msg}")
        for v in q["vehicles"]:
            add_vehicle_checks(v, today, add)
    return out


def add_vehicle_checks(v, today, add):
    """WellCare in-house quote rules (note 01) for one vehicle."""
    cov = {k.lower(): val for k, val in v["coverages"].items()}
    name = v["description"]

    def ded(key):
        val = cov.get(key)
        try:
            return int(str(val).replace(",", ""))
        except (TypeError, ValueError):
            return None
    phys = [k for k in ("all perils", "collision", "comprehensive", "specified perils") if k in cov]
    if v.get("annual_km") is not None and v["annual_km"] <= 8000:
        add("refer", f"{name}: annual km {v['annual_km']} (8,000 or less) - refer to the in-house underwriter.")
    if any((ded(k) or 0) > 1000 for k in phys):
        add("refer", f"{name}: deductible over $1,000 - refer in-house (unless the insurer requires it).")
    if any(k.startswith("#28") for k in cov):
        add("refer", f"{name}: OPCF 28/28A on the quote - refer to the insurer's and the in-house underwriter.")
    if (v.get("list_price") or 0) >= 150000:
        add("refer", f"{name}: list price ${v['list_price']:,} ($150,000+) - refer in-house.")
    if ("all perils" in cov or "collision" in cov) and not any(k.startswith("#20") for k in cov):
        add("warn", f"{name}: physical damage without OPCF 20 (loss of use, min $1,500) - offer it.")
    if "accident waiver" not in cov:
        add("warn", f"{name}: no accident waiver / OPCF 39 - offer it.")
    if (ded("direct compensation") or 0) > 0:
        add("warn", f"{name}: DCPD deductible isn't $0.")
    age = today.year - v["year"] if v.get("year") else None
    if age is not None and age < 2 and not any(k.startswith("#43") for k in cov):
        add("warn", f"{name}: under 2 years old without OPCF 43 (waiver of depreciation) - offer it.")
    if age is not None and age < 3 and not phys:
        add("warn", f"{name}: under 3 years old with liability only - confirm the client declined physical damage.")
    if any(k.startswith("#23") for k in cov):
        add("info", f"{name}: OPCF 23A lienholder on the quote - get the lender's name and address and the "
                    "financing papers.")
    if v.get("purchase_price") and v.get("list_price") and v["purchase_price"] > v["list_price"] * 1.1:
        add("warn", f"{name}: purchase price ${v['purchase_price']:,} is above the list price new "
                    f"${v['list_price']:,} - check both.")


def recommend(results, q):
    """Quoted carriers with the rules' verdict, and the markets that fit by the rules."""
    by_name = {r["market"].split()[0].lower(): r for r in results}
    quoted = []
    for c in (q or {}).get("carriers", []):
        r = next((r for key, r in by_name.items() if key in c["name"].lower()), None)
        quoted.append({"carrier": c["name"], "premium": c["premium"], "verdict": r["verdict"] if r else None,
                       "messages": len([m for m in c["messages"] if not m.lower().startswith("quote successfully")])})
    # standard markets first; non-standard only when no standard market fits
    # (a market that only needs a referral still counts - e.g. a new driver at Intact)
    for ok in (("Proceed", "Caution"), ("Refer to underwriter",)):
        for tier in ("standard", "non-standard", "commercial", ""):
            fits = [r for r in results if r.get("tier", "") == tier and r["verdict"] in ok]
            if fits:
                return quoted, fits
    return quoted, []
