"""Eligibility check: facts from a DASH report (+ convictions typed in from the MVR),
compared with a rules table per market. No AI - plain, repeatable rules.

Result per market: "Proceed", "Caution", "Refer to underwriter" or "Not eligible", with the
reasons. This is guidance only; the binding decision stays with the broker / underwriter.
"""
import datetime
import json
import re
from pathlib import Path

import pdfplumber

BUILTIN_RULES = Path(__file__).parent / "templates" / "rules_ontario.json"

# Facts the rules can use: key -> label shown to the broker
FACTS = {
    "years_licensed": "Years licensed",
    "years_insured": "Years since first insured",
    "years_continuous_insurance": "Years of continuous insurance",
    "age": "Driver age",
    "at_fault_claims_6y": "At-fault claims, driver at the wheel (6 yrs)",
    "at_fault_claims_3y": "At-fault claims, driver at the wheel (3 yrs)",
    "claims_6y": "All claims on the report (6 yrs)",
    "claims_3y": "All claims on the report (3 yrs)",
    "ab_claims_6y": "Accident Benefits claims (6 yrs)",
    "ab_over_10k_6y": "AB claims over $10,000 (6 yrs)",
    "ab_claims_10y": "Accident Benefits claims (10 yrs)",
    "open_claims": "Open claims",
    "nonpay_cancellations_3y": "Non-payment cancellations (3 yrs)",
    "nonpay_cancellations_5y": "Non-payment cancellations (5 yrs)",
    "possible_gaps": "Possible gaps in coverage",
    "gap_last_12m": "Gap in the last 12 months / uninsured now",
    "minor_convictions_3y": "Minor convictions (3 yrs)",
    "major_convictions_3y": "Major convictions (3 yrs)",
    "serious_convictions_3y": "Serious / criminal convictions (3 yrs)",
    "alcohol_convictions_3y": "   of those, alcohol-related",
}
MANUAL = ("minor_convictions_3y", "major_convictions_3y", "serious_convictions_3y", "alcohol_convictions_3y")


def _sum(facts, *keys):
    vals = [facts.get(k) for k in keys]
    return None if any(v is None or v == "" for v in vals) else sum(float(v) for v in vals)


# Worked out from the facts above, for rules on combined counts
DERIVED = {
    "major_serious_3y": ("Major + serious convictions (3 yrs)",
                         lambda f: _sum(f, "major_convictions_3y", "serious_convictions_3y")),
    "all_convictions_3y": ("All convictions (3 yrs)",
                           lambda f: _sum(f, "minor_convictions_3y", "major_convictions_3y", "serious_convictions_3y")),
}

VERDICTS = ["Proceed", "Caution", "Refer to underwriter", "Not eligible"]   # in order of severity


def _date(text):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _years_ago(d, today, years):
    try:
        cutoff = today.replace(year=today.year - years)
    except ValueError:  # Feb 29
        cutoff = today.replace(year=today.year - years, day=28)
    return d >= cutoff


def _same_person(a, b):
    a, b = set(a.upper().replace(",", "").split()), set(b.upper().replace(",", "").split())
    return bool(a) and bool(b) and (a <= b or b <= a)


def _field(block, label):
    m = re.search(label + r":\s*(.+?)(?:\s+(?:Coverage|Date Reported|Claim Status|Expiry Date)\b|$)", block, re.M)
    return m.group(1).strip() if m else ""


def read_dash_facts(pdf_path, today=None, at_fault_over=25):
    """Pull the facts out of a DASH driver report. Returns (facts, details, notes)."""
    today = today or datetime.date.today()
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    # Sections of page 1: summary, then the "Policies" list, then "Claims", then "Previous Inquiries"
    first, _, rest = text.partition("\nPolicies\n")
    policy_list, _, rest = rest.partition("\nClaims\n")
    claim_list = rest.split("Previous Inquiries", 1)[0]
    name = re.search(r"DRIVER REPORT\s*\n(.+?)\s+Report Date:", text)
    driver = name.group(1).strip() if name else ""

    def num(label):
        m = re.search(label + r"\s*:\s*(\d+)", first)
        return int(m.group(1)) if m else None

    facts, notes = {}, []
    facts["years_licensed"] = num("Years Licensed")
    facts["years_continuous_insurance"] = num("Years of Continuous Insurance")
    dob = re.search(r"Date of Birth:\s*(\d{4}-\d{2}-\d{2})", first)
    if dob and _date(dob.group(1)):
        b = _date(dob.group(1))
        facts["age"] = today.year - b.year - ((today.month, today.day) < (b.month, b.day))

    # Claim detail pages: "Claim #2 Date of Loss ..." with Coverage, Claim Status, Total Loss, First Party Driver
    detail = {}
    for block in re.split(r"\n(?=Claim #\d+ Date of Loss)", text)[1:]:
        n = int(re.match(r"Claim #(\d+)", block).group(1))
        loss = re.search(r"Total Loss:\s*\$([\d,.]+)", block)
        detail.setdefault(n, {"coverage": _field(block, "Coverage"), "status": _field(block, "Claim Status"),
                              "driver": _field(block, "First Party Driver"),
                              "loss": float(loss.group(1).replace(",", "")) if loss else 0.0})

    # Claims list: "#2 Date of Loss 2024-12-27 CAA Insurance Company At-Fault : 100%"
    claims = []
    seen = set()
    for m in re.finditer(r"#(\d+)\s+Date of Loss\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\s+At-Fault\s*:\s*(\d+)%", claim_list):
        d = _date(m.group(2))
        key = (m.group(2), m.group(3).strip(), m.group(4))
        if d and key not in seen:  # each claim once, even if repeated on detail pages
            seen.add(key)
            c = {"number": int(m.group(1)), "date": d, "insurer": m.group(3).strip(), "fault": int(m.group(4)),
                 **detail.get(int(m.group(1)), {"coverage": "", "status": "", "driver": "", "loss": 0.0})}
            named = c["driver"] and c["driver"].lower() != "not available"
            c["at_wheel"] = _same_person(c["driver"], driver) if named and driver else None   # None = unknown
            claims.append(c)

    def within(c, years):
        return _years_ago(c["date"], today, years)

    # At-fault claims count against this driver only when they were driving (as DASH's own summary does)
    at_fault = [c for c in claims if c["fault"] > at_fault_over]
    own = [c for c in at_fault if c["at_wheel"]]
    facts["at_fault_claims_6y"] = len([c for c in own if within(c, 6)])
    facts["at_fault_claims_3y"] = len([c for c in own if within(c, 3)])
    facts["claims_6y"] = len([c for c in claims if within(c, 6)])
    facts["claims_3y"] = len([c for c in claims if within(c, 3)])
    ab = [c for c in claims if c["coverage"].upper() == "AB"]
    facts["ab_claims_6y"] = len([c for c in ab if within(c, 6)])
    facts["ab_over_10k_6y"] = len([c for c in ab if within(c, 6) and c["loss"] > 10000])
    facts["ab_claims_10y"] = len([c for c in ab if within(c, 10)])
    facts["open_claims"] = len([c for c in claims if c["status"].lower() == "open"])

    for c in at_fault:
        if not within(c, 6):
            continue
        if c["at_wheel"] is False:
            notes.append(f"At-fault claim {c['date']} ({c['insurer']}, {c['fault']}%) - {c['driver'].title()} was "
                         "driving, so it is not counted against this driver. Insurers may still ask about it.")
        elif c["at_wheel"] is None:
            notes.append(f"At-fault claim {c['date']} ({c['insurer']}, {c['fault']}%, {c['coverage'] or 'coverage ?'}) "
                         "names no driver - not counted. Ask who was driving; if it was this driver, add 1 to "
                         "the at-fault counts.")
    for c in claims:
        if c["status"].lower() == "open":
            notes.append(f"Claim {c['date']} ({c['insurer']}, {c['coverage'] or '?'}) is still OPEN.")
    summary_af = num("Number of At-Fault Claims in Last 6 Years")
    if summary_af is not None and summary_af != facts["at_fault_claims_6y"]:
        notes.append(f"DASH summary says {summary_af} at-fault claim(s) in 6 years, but the claims with this driver "
                     f"at the wheel show {facts['at_fault_claims_6y']} - check with the insurer / underwriter.")

    # Policies list: "#2 2025-10-21 to 2026-02-05 Coachman Insurance Company Cancelled - non-payment"
    # newest first; a "*POSSIBLE GAP*" line sits between the two policies it separates
    policies, gaps, gap_pending = [], [], False
    for line in policy_list.splitlines():
        m = re.match(r"#\d+\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\s+(.+)$", line.strip())
        if m:
            p = {"start": _date(m.group(1)), "end": _date(m.group(2)), "rest": m.group(3).strip()}
            if gap_pending and policies:
                gaps.append({"from": p["end"], "to": policies[-1]["start"]})   # older policy's end -> newer's start
            gap_pending = False
            policies.append(p)
        elif "POSSIBLE GAP" in line:
            gap_pending = True
    nonpay = [p for p in policies if re.search(r"non-?payment", p["rest"], re.I) and p["end"]]
    facts["nonpay_cancellations_3y"] = len([p for p in nonpay if _years_ago(p["end"], today, 3)])
    facts["nonpay_cancellations_5y"] = len([p for p in nonpay if _years_ago(p["end"], today, 5)])
    facts["possible_gaps"] = len(re.findall(r"POSSIBLE GAP", policy_list))
    recent = [g for g in gaps if g["to"] and (today - g["to"]).days <= 365]
    uninsured = bool(policies) and not any("active" in p["rest"].lower() or (p["end"] and p["end"] >= today)
                                           for p in policies)
    facts["gap_last_12m"] = len(recent) + (1 if uninsured else 0)
    for g in gaps:
        months = round(((g["to"] - g["from"]).days if g["to"] and g["from"] else 0) / 30.4)
        notes.append(f"Coverage gap {g['from']} to {g['to']} (about {months} months) - make sure the quote shows "
                     "it as a lapse with the reason.")
    if uninsured:
        notes.append("No active policy on the DASH report - the client is not insured right now.")
    starts = [p["start"] for p in policies if p["start"]]
    facts["years_insured"] = round((today - min(starts)).days / 365.25, 1) if starts else 0
    if not starts:
        notes.append("No policies on the DASH report - no insurance history (new driver).")

    # Things a broker should notice even if no rule mentions them
    holders = set(n.strip().upper().replace(",", "") for n in re.findall(r"Policyholder Name:\s*(.+?)\s+Expiry", text))
    if driver:
        others = [h for h in holders if not _same_person(h, driver)]
        if others:
            notes.append(f"Listed on a policy held by someone else ({', '.join(sorted(others))}) - "
                         "ask about the relationship and who owns / drives the vehicle.")
    inquiries = [_date(d) for d in re.findall(r"^(\d{4}-\d{2}-\d{2})\s+\S", text.split("Previous Inquiries", 1)[-1], re.M)]
    recent_inq = [d for d in inquiries if d and (today - d).days <= 30]
    if len(recent_inq) >= 3:
        notes.append(f"{len(recent_inq)} other DASH inquiries in the last 30 days - the client is shopping around.")

    details = {"claims": claims, "policies": policies, "gaps": gaps, "driver": driver, "dob": dob.group(1) if dob else "",
               "dln": (re.search(r"DLN:\s*([A-Z0-9-]+)", first) or [None, ""])[1],
               "postal": (re.search(r"Address:.*?([A-Z]\d[A-Z]\s?\d[A-Z]\d)\b", first) or [None, ""])[1]}
    return facts, details, notes


def load_rules(path=None):
    path = Path(path) if path else BUILTIN_RULES
    if not path.exists():
        path = BUILTIN_RULES
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data, path


def _label(key):
    return FACTS.get(key, "").strip() or DERIVED.get(key, (key,))[0]


def _check(facts, conds):
    """True (all conditions met), False (one is not met) or the set of missing facts (the rest are met)."""
    missing = set()
    for key, lim in conds.items():
        v = DERIVED[key][1](facts) if key in DERIVED else facts.get(key)
        if v is None or v == "":
            missing.add(_label(key))
            continue
        v = float(v)
        if ("min" in lim and v < lim["min"]) or ("max" in lim and v > lim["max"]):
            return False
    return missing or True


def evaluate(facts, rules, line=None):
    """Return [{market, verdict, reasons:[(severity, text, source)], unknown:[labels], incomplete, note}].

    Rule forms in the rules file:
      {"if": {fact: {"min": n, "max": n}, ...}, "when": {...}, "then": verdict, "text": "...", "source": "..."}
        - triggers when every condition in "if" and "when" is met (min/max inclusive)
      {"fact": key, "max": n, "if_over": verdict, "min": n, "if_under": verdict, "source": "..."}  (older form)
    """
    results = []
    always = [m for m in rules.get("markets", []) if m.get("applies_to_all")]
    markets = [m for m in rules.get("markets", []) if not m.get("applies_to_all")]
    if line and any(line in m.get("lines", []) for m in markets):
        markets = [m for m in markets if not m.get("lines") or line in m["lines"]]   # only this client's line
    for market in markets:
        reasons, unknown = [], set()
        for rule_set in [market] + always:
            for r in rule_set.get("rules", []):
                src = r.get("source") or rule_set.get("name", "")
                if "if" in r or "when" in r:
                    ok = _check(facts, {**r.get("when", {}), **r.get("if", {})})
                    if ok is True:
                        reasons.append((r.get("then", "Refer to underwriter"), r.get("text") or "Rule met", src))
                    elif ok:
                        unknown |= ok   # could apply: depends on facts not entered yet
                    continue
                key = r["fact"]
                value = facts.get(key)
                label = _label(key)
                if value is None or value == "":
                    unknown.add(label)
                    continue
                value = float(value)
                if "max" in r and value > r["max"]:
                    reasons.append((r.get("if_over", "Refer to underwriter"),
                                    f"{label}: {value:g} (limit {r['max']:g})", src))
                if "min" in r and value < r["min"]:
                    reasons.append((r.get("if_under", "Refer to underwriter"),
                                    f"{label}: {value:g} (minimum {r['min']:g})", src))
        # each line once; for limits on the same fact keep only the most serious one
        best = {}
        for sev, text, src in reasons:
            key = (text.split(":")[0], src)
            if key not in best or VERDICTS.index(sev) > VERDICTS.index(best[key][0]):
                best[key] = (sev, text, src)
        reasons = sorted(best.values(), key=lambda x: -VERDICTS.index(x[0]) if x[0] in VERDICTS else 0)
        worst = max([VERDICTS.index(s) for s, _, _ in reasons if s in VERDICTS] or [0])
        results.append({"market": market.get("name", "?"), "verdict": VERDICTS[worst], "reasons": reasons,
                        "unknown": sorted(unknown), "incomplete": bool(unknown), "note": market.get("note", ""),
                        "tier": market.get("tier", "")})
    return results
