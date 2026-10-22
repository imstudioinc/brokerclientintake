"""Eligibility check: facts from a DASH report (+ convictions typed in from the MVR),
compared with a rules table per market. No AI - plain, repeatable rules.

Result per market: "Proceed", "Refer to underwriter" or "Not eligible", with the reasons.
This is guidance only; the binding decision stays with the broker / underwriter.
"""
import datetime
import json
import re
from pathlib import Path

import pdfplumber

EXAMPLE_RULES = Path(__file__).parent / "templates" / "rules_example.json"

# Facts the rules can use: key -> label shown to the broker
FACTS = {
    "years_licensed": "Years licensed",
    "years_continuous_insurance": "Years of continuous insurance",
    "age": "Driver age",
    "at_fault_claims_6y": "At-fault claims (last 6 years)",
    "claims_6y": "All claims (last 6 years)",
    "nonpay_cancellations_3y": "Cancellations for non-payment (last 3 years)",
    "possible_gaps": "Possible gaps in coverage",
    "minor_convictions_3y": "Minor convictions (last 3 years)",
    "major_convictions_3y": "Major convictions (last 3 years)",
    "serious_convictions_3y": "Serious / criminal convictions (last 3 years)",
}
MANUAL = ("minor_convictions_3y", "major_convictions_3y", "serious_convictions_3y")  # from the MVR

VERDICTS = ["Proceed", "Refer to underwriter", "Not eligible"]   # in order of severity


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


def read_dash_facts(pdf_path, today=None, at_fault_over=25):
    """Pull the facts out of a DASH driver report. Returns (facts, details, notes)."""
    today = today or datetime.date.today()
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    # Sections of page 1: summary, then the "Policies" list, then "Claims", then "Previous Inquiries"
    first, _, rest = text.partition("\nPolicies\n")
    policy_list, _, rest = rest.partition("\nClaims\n")
    claim_list = rest.split("Previous Inquiries", 1)[0]

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

    # Claims list: "#2 Date of Loss 2024-12-27 CAA Insurance Company At-Fault : 100%"
    claims = []
    seen = set()
    for m in re.finditer(r"Date of Loss\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\s+At-Fault\s*:\s*(\d+)%", claim_list):
        d = _date(m.group(1))
        key = (m.group(1), m.group(2).strip(), m.group(3))
        if d and key not in seen:  # each claim once, even if repeated on detail pages
            seen.add(key)
            claims.append({"date": d, "insurer": m.group(2).strip(), "fault": int(m.group(3))})
    recent = [c for c in claims if _years_ago(c["date"], today, 6)]
    at_fault = [c for c in recent if c["fault"] > at_fault_over]
    facts["claims_6y"] = len(recent)
    facts["at_fault_claims_6y"] = len(at_fault)
    summary_af = num("Number of At-Fault Claims in Last 6 Years")
    if summary_af is not None and summary_af != len(at_fault):
        notes.append(f"DASH summary says {summary_af} at-fault claim(s), but its claims list shows "
                     f"{len(at_fault)} over {at_fault_over}% fault - check with the insurer / underwriter.")

    # Policies list: "#2 2025-10-21 to 2026-02-05 Coachman Insurance Company Cancelled - non-payment"
    policies = []
    for m in re.finditer(r"^#\d+\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\s+(.+)$",
                         policy_list, re.M):
        policies.append({"start": _date(m.group(1)), "end": _date(m.group(2)), "rest": m.group(3).strip()})
    nonpay = [p for p in policies if re.search(r"non-?payment", p["rest"], re.I)
              and p["end"] and _years_ago(p["end"], today, 3)]
    facts["nonpay_cancellations_3y"] = len(nonpay)
    facts["possible_gaps"] = len(re.findall(r"POSSIBLE GAP", policy_list))

    # Things a broker should notice even if no rule mentions them
    holders = set(n.strip().upper().replace(",", "") for n in re.findall(r"Policyholder Name:\s*(.+?)\s+Expiry", text))
    name = re.search(r"DRIVER REPORT\s*\n(.+?)\s+Report Date:", text)
    if name:
        driver = name.group(1).strip().upper()
        others = [h for h in holders if set(h.split()) != set(driver.split())]
        if others:
            notes.append(f"Listed on a policy held by someone else ({', '.join(sorted(others))}) - "
                         "ask about the relationship and who owns / drives the vehicle.")
    inquiries = [_date(d) for d in re.findall(r"^(\d{4}-\d{2}-\d{2})\s+\S", text.split("Previous Inquiries", 1)[-1], re.M)]
    recent_inq = [d for d in inquiries if d and (today - d).days <= 30]
    if len(recent_inq) >= 3:
        notes.append(f"{len(recent_inq)} other DASH inquiries in the last 30 days - the client is shopping around.")

    details = {"claims": claims, "policies": policies}
    return facts, details, notes


def load_rules(path=None):
    path = Path(path) if path else EXAMPLE_RULES
    if not path.exists():
        path = EXAMPLE_RULES
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data, path


def evaluate(facts, rules):
    """Return [{market, verdict, reasons:[(severity, text, source)], unknown:[labels]}]."""
    results = []
    always = [m for m in rules.get("markets", []) if m.get("applies_to_all")]
    for market in [m for m in rules.get("markets", []) if not m.get("applies_to_all")]:
        reasons, unknown = [], set()
        for rule_set in [market] + always:
            for r in rule_set.get("rules", []):
                key = r["fact"]
                value = facts.get(key)
                label = FACTS.get(key, key)
                if value is None or value == "":
                    unknown.add(label)
                    continue
                value = float(value)
                src = r.get("source") or rule_set.get("name", "")
                if "max" in r and value > r["max"]:
                    reasons.append((r.get("if_over", "Refer to underwriter"),
                                    f"{label}: {value:g} (limit {r['max']:g})", src))
                if "min" in r and value < r["min"]:
                    reasons.append((r.get("if_under", "Refer to underwriter"),
                                    f"{label}: {value:g} (minimum {r['min']:g})", src))
        # one line per fact per rule set: keep only the most serious broken limit
        best = {}
        for sev, text, src in reasons:
            key = (text.split(":")[0], src)
            if key not in best or VERDICTS.index(sev) > VERDICTS.index(best[key][0]):
                best[key] = (sev, text, src)
        reasons = list(best.values())
        worst = max([VERDICTS.index(s) for s, _, _ in reasons if s in VERDICTS] or [0])
        verdict = VERDICTS[worst]
        if verdict == "Proceed" and unknown:
            verdict = "Refer to underwriter"
            reasons.append(("Refer to underwriter", "Some facts are missing: " + ", ".join(sorted(unknown)), ""))
        reasons.sort(key=lambda x: -VERDICTS.index(x[0]) if x[0] in VERDICTS else 0)
        results.append({"market": market.get("name", "?"), "verdict": verdict,
                        "reasons": reasons, "unknown": sorted(unknown), "note": market.get("note", "")})
    return results
