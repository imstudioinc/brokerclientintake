"""Home / tenant property file: what to collect, which extra documents it needs, and which markets will take it.

The facts about the property live in the client's tracking.json under "property_intake" (one flat dict of
strings, filled in on the Property details page). From them:

* completeness()  - what is still missing
* docs_needed()   - the questionnaires / certificates this property needs (oil tank, wood stove, alarm ...)
* review()        - markets that fit, with the reasons for a refer / decline, and WellCare's own rules

The carriers' rules are NOT in this file: the repo is public. They are read from property_rules.json in the
Underwriting Knowledge folder (like carriers.json); without that file the review still lists what is missing and
which documents are needed.
"""
import datetime
import json
import re
from pathlib import Path

import notes_search
import records

KEY = "property_intake"
RULES_FILE = "property_rules.json"

# ---------- choices (the rules file uses these exact words) ----------
DWELLING = ["House (owner lives there)", "Condo (owner lives there)", "Tenant (rents a home)",
            "Rental house (landlord)", "Rental condo (landlord)", "Seasonal / cottage", "Mobile / mini home"]
USE_OF = {DWELLING[0]: "owner", DWELLING[1]: "owner", DWELLING[2]: "tenant", DWELLING[3]: "landlord",
          DWELLING[4]: "landlord", DWELLING[5]: "seasonal", DWELLING[6]: "owner"}
STRUCTURE = ["Detached", "Semi-detached", "Row / townhouse", "Condo / apartment unit"]
STOREYS = ["1", "1.5", "2", "2.5", "3 or more"]
CONSTRUCTION = ["Frame / siding", "Brick / masonry", "Log", "Other / unusual"]
FOUNDATION = ["Poured concrete / block", "Open / piers / posts", "Wood", "Other"]
BASEMENT = ["No basement", "Unfinished", "25% finished", "50% finished", "75% finished", "100% finished"]
FORMS = ["Comprehensive", "Broad", "Basic / named perils"]
ROOF = ["Asphalt shingles", "Metal", "Tile / slate", "Flat (tar & gravel / membrane)", "Wood shakes", "Other"]
WIRING = ["Copper", "Aluminum", "Knob & tube", "Mixed / not sure"]
PANEL = ["Breakers", "Fuses", "Stab-Lok / other problem panel"]
AMPS = ["60 or less", "100", "125 to 150", "200 or more"]
PLUMBING = ["Copper", "PEX", "PVC / ABS", "Galvanized", "Poly-B", "Kitec", "Lead", "Cast iron", "Mixed / not sure"]
HEATING = ["Gas forced air", "Electric", "Oil", "Propane", "Heat pump / geothermal", "Hot water / radiant",
           "Wood or pellet stove", "Space heaters", "Other / not sure"]
AUX = ["None", "Wood stove", "Pellet stove", "Fireplace / insert", "Space heater", "Other"]
OIL_PLACE = ["No oil tank", "Inside", "Outside", "Underground"]
OIL_TYPE = ["Steel (single wall)", "Steel (double wall)", "Fibreglass"]
ALARM = ["None", "Local only", "Monitored"]
FIRE_HALL = ["Within 5 km", "5 to 13 km", "Over 13 km"]
GROW = ["No", "Past", "Current"]
MARITAL = ["Single", "Married / common-law", "Separated", "Divorced", "Widowed"]
GARAGE = ["None", "Attached", "Detached", "Carport"]
YN = ["Yes", "No"]

# (key, label, kind, options, uses, hint)   kind: text num year yn choice date money long
#   uses: which kinds of risk ask it - o owner, t tenant, l landlord, s seasonal ("" = all)
SECTIONS = [
    ("about", "The property", [
        ("dwelling", "What is being insured", "choice", DWELLING, "", ""),
        ("address", "Risk address", "text", None, "", "Must match the documents (address verification)"),
        ("postal", "Postal code", "text", None, "", "Sewer backup zone and fire protection depend on it"),
        ("structure", "Type of building", "choice", STRUCTURE, "", ""),
        ("year_built", "Year built", "year", None, "", ""),
        ("storeys", "Storeys", "choice", STOREYS, "ols", ""),
        ("sq_ft", "Living area (sq ft)", "num", None, "ols", "Excluding the basement"),
        ("construction", "Construction", "choice", CONSTRUCTION, "ols", ""),
        ("foundation", "Foundation", "choice", FOUNDATION, "ols", ""),
        ("basement_pct", "Basement", "choice", BASEMENT, "ols", ""),
        ("heritage", "Heritage-designated or century home", "yn", None, "ols", ""),
        ("reno", "Under construction or a major renovation now", "yn", None, "ols", ""),
        ("value", "Replacement cost ($)", "money", None, "ols", "From the EZITV; insured to 100%"),
        ("ezitv_date", "EZITV completed on", "date", None, "ols", "Within 30 days of the effective date"),
        ("form", "Coverage form wanted", "choice", FORMS, "", "Comprehensive is the one to advise"),
    ]),
    ("updates", "Updates and systems", [
        ("roof_type", "Roof covering", "choice", ROOF, "ols", ""),
        ("roof_year", "Roof replaced (year)", "year", None, "ols", "Original year if never replaced"),
        ("wiring", "Wiring", "choice", WIRING, "ols", ""),
        ("panel", "Electrical panel", "choice", PANEL, "ols", ""),
        ("amps", "Service (amps)", "choice", AMPS, "ols", ""),
        ("electrical_year", "Wiring updated (year)", "year", None, "ols", ""),
        ("plumbing", "Plumbing (supply pipes)", "choice", PLUMBING, "ols", ""),
        ("plumbing_year", "Plumbing updated (year)", "year", None, "ols", ""),
        ("heating", "Main heating", "choice", HEATING, "ols", ""),
        ("heating_year", "Heating replaced (year)", "year", None, "ols", ""),
        ("aux_heat", "Extra heat", "choice", AUX, "ols", "Wood stove / pellet stove: questionnaire + photo"),
        ("oil_place", "Oil tank", "choice", OIL_PLACE, "ols", ""),
        ("oil_type", "Oil tank type", "choice", OIL_TYPE, "ols", ""),
        ("oil_year", "Oil tank installed (year)", "year", None, "ols", "On the label"),
        ("water_heater_year", "Hot water tank (year)", "year", None, "ols", ""),
    ]),
    ("water", "Water protection", [
        ("sump_pump", "Sump pump", "yn", None, "ols", ""),
        ("sump_battery", "Sump pump has battery backup", "yn", None, "ols", ""),
        ("backwater_valve", "Backwater valve", "yn", None, "ols", "Professionally installed"),
        ("water_shutoff", "Automatic water shut-off", "yn", None, "ols", ""),
        ("wants_sewer", "Sewer backup wanted", "yn", None, "", ""),
        ("wants_overland", "Overland water wanted", "yn", None, "", ""),
    ]),
    ("safety", "Safety and location", [
        ("burglar_alarm", "Burglar alarm", "choice", ALARM, "", "Certificate needed for the credit"),
        ("fire_alarm", "Fire alarm", "choice", ALARM, "", "Certificate needed for the credit"),
        ("hydrant", "Hydrant within 300 m", "yn", None, "ols", ""),
        ("fire_hall", "Distance to the fire hall", "choice", FIRE_HALL, "ols", ""),
        ("road_access", "Fire trucks can reach it by road all year", "yn", None, "ols", ""),
    ]),
    ("occupancy", "Who lives there and what goes on", [
        ("vacant", "Vacant or empty now", "yn", None, "", ""),
        ("rented_units", "Other self-contained units rented out (basement apartment ...)", "num", None, "ol", ""),
        ("short_term", "Rented short term (Airbnb, VRBO)", "yn", None, "", ""),
        ("roomers", "Roomers / boarders", "num", None, "ol", ""),
        ("students", "Student rental", "yn", None, "ol", ""),
        ("home_business", "Business run from the home", "yn", None, "", ""),
        ("daycare", "Daycare / babysitting", "yn", None, "ol", ""),
        ("farm", "Farming or hobby farm", "yn", None, "ol", ""),
        ("grow_op", "Grow-op history", "choice", GROW, "ols", ""),
        ("cannabis", "Cannabis plants grown", "num", None, "ols", ""),
        ("pool", "Swimming pool", "yn", None, "ols", ""),
        ("trampoline", "Trampoline", "yn", None, "ols", ""),
        ("risky_dog", "Pit bull / Rottweiler (or mix), or a dog that has bitten", "yn", None, "", ""),
        ("smoker", "Anyone smokes", "yn", None, "", ""),
        ("solar_income", "Solar panels / wind turbine earning income", "yn", None, "ols", ""),
    ]),
    ("mortgage", "Mortgage", [
        ("mortgages", "Number of mortgages", "num", None, "ols", "A secured line of credit counts"),
        ("private_lender", "Private or non-bank lender", "yn", None, "ols", ""),
        ("lender", "Lender name and address", "text", None, "ols", "For the mortgagee on the policy"),
    ]),
    ("rental", "Tenant, landlord and stand-alone details", [
        ("standalone", "Stand-alone: no home policy with the same company", "yn", None, "tls", ""),
        ("contents_value", "Contents value ($)", "money", None, "t", ""),
        ("roommates", "Unrelated people living there", "num", None, "t", ""),
        ("lease_signed", "Lease signed by the insured", "yn", None, "t", ""),
        ("lease_months", "Lease length (months)", "num", None, "l", ""),
    ]),
    ("history", "Insurance history and claims", [
        ("insured_since", "Continuously insured since", "date", None, "", ""),
        ("prior_insurer", "Current / previous insurer", "text", None, "", ""),
        ("prior_policy", "Previous policy number", "text", None, "", ""),
        ("prior_expiry", "Previous policy expiry", "date", None, "", ""),
        ("no_prior", "No prior insurance at all", "yn", None, "", ""),
        ("first_time", "First-time buyer / renter, or leaving parents' home", "yn", None, "", ""),
        ("cancelled_5y", "Cancelled, declined or non-renewed in 5 years", "yn", None, "", ""),
        ("nonpay_3y", "Cancelled for non-payment in 3 years (how many)", "num", None, "", ""),
        ("lapse", "Any gap in coverage", "yn", None, "", ""),
        ("claims_5y", "Claims in 5 years (how many)", "num", None, "", "From the HITS report"),
        ("water_claims_5y", "Of those, water / sewer backup claims", "num", None, "", ""),
        ("open_claim", "Open claim", "yn", None, "", ""),
        ("claims_notes", "Claim details (date, what, amount)", "long", None, "", "Goes in the remarks"),
    ]),
    ("applicant", "Applicant (PowerBroker and the credit score need these)", [
        ("occupation", "Occupation", "text", None, "", ""),
        ("marital", "Marital status", "choice", MARITAL, "", ""),
        ("bathrooms", "Full bathrooms", "num", None, "ols", "Mandatory with many insurers"),
        ("half_baths", "Half bathrooms", "num", None, "ols", ""),
        ("kitchens", "Kitchens", "num", None, "ols", ""),
        ("bedrooms", "Bedrooms", "num", None, "ols", ""),
        ("garage", "Garage / carport", "choice", GARAGE, "ols", ""),
        ("occupancy_date", "Living at this address since", "date", None, "", "Prior address if under 3 years"),
        ("prior_address", "Previous address (if under 3 years here)", "text", None, "", ""),
    ]),
]
FIELDS = {f[0]: f for _, _, fields in SECTIONS for f in fields}
LABELS = {k: f[1] for k, f in FIELDS.items()}

# what must be filled before the details count as complete
REQUIRED = {
    "owner": ["dwelling", "address", "postal", "structure", "year_built", "sq_ft", "construction", "roof_type",
              "roof_year", "wiring", "panel", "amps", "plumbing", "heating", "claims_5y", "mortgages",
              "burglar_alarm", "occupation", "marital"],
    "landlord": ["dwelling", "address", "postal", "structure", "year_built", "sq_ft", "construction", "roof_type",
                 "roof_year", "wiring", "panel", "amps", "plumbing", "heating", "claims_5y", "lease_months",
                 "standalone", "occupation", "marital"],
    "seasonal": ["dwelling", "address", "postal", "year_built", "sq_ft", "construction", "roof_type", "wiring",
                 "panel", "plumbing", "heating", "claims_5y", "standalone", "occupation", "marital"],
    "tenant": ["dwelling", "address", "postal", "structure", "claims_5y", "contents_value", "roommates",
               "standalone", "occupation", "marital"],
}


def use_of(values):
    return USE_OF.get(values.get("dwelling", ""), "")


def fields_for(use):
    """[(section title, [field, ...])] asked for this kind of risk (all sections when use is unknown)."""
    code = {"owner": "o", "tenant": "t", "landlord": "l", "seasonal": "s"}.get(use)
    out = []
    for key, title, fields in SECTIONS:
        shown = [f for f in fields if not code or not f[4] or code in f[4]]
        if shown:
            out.append((key, title, shown))
    return out


# ---------- the facts the rules look at ----------
def _num(v):
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def derive(values, today=None):
    """The raw answers plus what follows from them (ages, use, flags). Blank answers are left out."""
    today = today or datetime.date.today()
    f = {k: v for k, v in values.items() if v not in (None, "")}
    f["use"] = use_of(values)
    f["condo"] = "Yes" if values.get("dwelling") in (DWELLING[1], DWELLING[4]) else "No"
    f["mobile"] = "Yes" if values.get("dwelling") == DWELLING[6] else "No"
    for key, out in (("year_built", "building_age"), ("roof_year", "roof_age"), ("electrical_year", "wiring_age"),
                     ("plumbing_year", "plumbing_age"), ("heating_year", "heating_age"),
                     ("oil_year", "oil_age"), ("water_heater_year", "water_heater_age")):
        y = _num(values.get(key))
        if y and 1800 < y <= today.year:
            f[out] = today.year - int(y)
    for key in ("sq_ft", "value", "contents_value", "mortgages", "nonpay_3y", "claims_5y", "water_claims_5y",
                "rented_units", "roomers", "cannabis", "lease_months", "roommates"):
        n = _num(values.get(key))
        if n is not None:
            f[key] = n
    if f.get("oil_place") == "No oil tank":
        f.pop("oil_type", None)
    since = _date(values.get("insured_since"))
    if since:
        f["insured_years"] = round((today - since).days / 365.25, 1)
    return f


def _date(text):
    return records.parse_date(text) if text else None


_OPS = {
    "eq": lambda a, b: str(a).lower() == str(b).lower(),
    "ne": lambda a, b: str(a).lower() != str(b).lower(),
    "in": lambda a, b: str(a).lower() in [str(x).lower() for x in b],
    "ge": lambda a, b: _num(a) is not None and _num(a) >= b,
    "gt": lambda a, b: _num(a) is not None and _num(a) > b,
    "le": lambda a, b: _num(a) is not None and _num(a) <= b,
    "lt": lambda a, b: _num(a) is not None and _num(a) < b,
}


def test(facts, cond):
    """One condition [field, op, value] against the facts. An unanswered question never triggers a rule."""
    field, op = cond[0], cond[1]
    value = facts.get(field)
    if op == "notyes":                       # not answered, or answered anything but Yes
        return str(value or "").lower() != "yes"
    if value in (None, ""):
        return False
    if op == "yes":
        return str(value).lower() == "yes"
    if op == "no":
        return str(value).lower() == "no"
    return _OPS[op](value, cond[2])


# ---------- completeness and documents ----------
def completeness(values):
    """(filled, total, [labels still missing]) for this kind of risk."""
    use = use_of(values)
    wanted = REQUIRED.get(use) or ["dwelling"]
    missing = [LABELS[k] for k in wanted if values.get(k) in (None, "")]
    return len(wanted) - len(missing), len(wanted), missing


def docs_needed(values):
    """{document label: why} for the questionnaires / certificates this property needs."""
    f = derive(values)
    need = {}
    if f.get("burglar_alarm") in ("Local only", "Monitored") or f.get("fire_alarm") in ("Local only", "Monitored"):
        need["Alarm certificate"] = "alarm credit is only applied once the certificate is in"
    if f.get("oil_place") in ("Inside", "Outside", "Underground") or f.get("heating") == "Oil":
        need["Oil tank questionnaire"] = "oil heat: questionnaire + photos of the tank and its label"
    if f.get("heating") == "Wood or pellet stove" or f.get("aux_heat") in ("Wood stove", "Pellet stove"):
        need["Wood stove questionnaire"] = "solid fuel heat: questionnaire + photo of the unit and its label"
    if f.get("wants_sewer") == "Yes" or f.get("wants_overland") == "Yes":
        need["Sewer backup questionnaire"] = "sewer backup up to $25,000 on a municipal sewer needs it signed"
    if f.get("use") == "landlord" or f.get("rented_units", 0) >= 1:
        need["Rented dwelling questionnaire"] = "rented unit: questionnaire, lease and photos of the unit"
    if f.get("mortgages", 0) >= 1 and f.get("use") in ("owner", "landlord"):
        need["Mortgage information"] = "lender name and address for the mortgagee clause"
    if f.get("insured_years", 0) >= 3 or f.get("prior_insurer"):
        need["Letter of experience"] = "proves claims-free years / continuous insurance (claims-free discount)"
    if f.get("use") == "landlord" or f.get("private_lender") == "Yes" or f.get("claims_5y", 0) >= 1:
        need["Photos"] = "insurers ask for photos on rentals, private lenders and files with claims"
    if f.get("value", 0) >= 1500000 or f.get("heritage") == "Yes":
        need["Appraisal"] = "high-value or heritage home: appraisal / high net worth submission"
    if f.get("use") == "tenant":
        for gone in ("Oil tank questionnaire", "Wood stove questionnaire", "Mortgage information", "Appraisal"):
            need.pop(gone, None)
    return need


# ---------- carrier rules (from the notes folder, never from the repo) ----------
_rules_cache = {}


def rules_path(cfg):
    return notes_search.notes_dir(cfg) / RULES_FILE


def load_rules(cfg):
    """The carriers' rules from property_rules.json, or {} when the file isn't there."""
    p = rules_path(cfg)
    try:
        key = (str(p), p.stat().st_mtime)
    except OSError:
        return {}
    if key not in _rules_cache:
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = {}
        _rules_cache.clear()
        _rules_cache[key] = data
    return _rules_cache[key]


LEVELS = ("decline", "refer", "caution")
RANK = {"decline": 3, "refer": 2, "caution": 1, "fits": 0}
VERDICT_TEXT = {"fits": "Fits", "caution": "Fits - check", "refer": "Refer first", "decline": "Won't take it"}


def _hits(rules_list, facts):
    out = []
    for r in rules_list:
        if r.get("uses") and facts.get("use") not in r["uses"]:
            continue
        if all(test(facts, c) for c in r.get("if", [])) and (r["level"], r["text"]) not in out:
            out.append((r["level"], r["text"]))
    return out


def review(values, rules):
    """{"wellcare": [(level, text)], "markets": [...], "missing": [...], "docs": {...}, "have_rules": bool}.

    Markets are sorted: fits first, then check / refer / won't take; standard markets before specialty ones.
    """
    facts = derive(values)
    done, total, missing = completeness(values)
    markets = []
    for name, c in (rules.get("carriers") or {}).items():
        if facts.get("use") and facts["use"] not in c.get("uses", ["owner", "tenant", "landlord", "seasonal"]):
            continue
        found = _hits(c.get("rules", []), facts)
        level = max((l for l, _ in found), key=lambda l: RANK[l], default="fits")
        markets.append({"name": name, "tier": c.get("tier", "standard"), "verdict": level, "findings": found,
                        "note": c.get("note", "")})
    markets.sort(key=lambda m: (RANK[m["verdict"]], m["tier"] != "standard", m["name"]))
    return {"wellcare": _hits((rules.get("wellcare") or {}).get("rules", []), facts), "markets": markets,
            "missing": missing, "filled": done, "total": total, "docs": docs_needed(values),
            "have_rules": bool(rules.get("carriers")), "facts": facts}


# ---------- saved with the client ----------
def load(folder):
    """The client's saved property answers ({} when none)."""
    data = records.load(folder).get(KEY)
    return dict(data) if isinstance(data, dict) else {}


def summary_record(values):
    """The Tracker's Property record built from the answers."""
    f = derive(values)
    heat = " ".join(x for x in (values.get("heating"), values.get("heating_year")) if x)
    bits = [x for x in (values.get("wiring"), values.get("plumbing")) if x]
    prot = ", ".join(x for x in (
        "burglar alarm " + values["burglar_alarm"].lower() if values.get("burglar_alarm") not in (None, "", "None") else "",
        "fire alarm " + values["fire_alarm"].lower() if values.get("fire_alarm") not in (None, "", "None") else "",
        "sump pump" if values.get("sump_pump") == "Yes" else "",
        "backwater valve" if values.get("backwater_valve") == "Yes" else "") if x)
    kind = {"owner": "House", "tenant": "Tenant / rental unit", "landlord": "Rented dwelling",
            "seasonal": "Seasonal"}.get(f.get("use"), "House")
    if values.get("dwelling") == DWELLING[1]:
        kind = "Condo"
    return {"address": values.get("address", ""), "kind": kind, "year_built": values.get("year_built", ""),
            "sq_ft": values.get("sq_ft", ""), "construction": values.get("construction", ""),
            "roof_year": values.get("roof_year", ""), "heating": heat,
            "electrical_plumbing": " / ".join(bits), "protection": prot,
            "mortgagee": values.get("lender", "")}


def save(folder, values):
    """Save the answers, and keep the Tracker's Property record in step (no retyping there)."""
    clean = {k: str(v).strip() for k, v in values.items() if k in FIELDS and str(v).strip()}
    data = records.load(folder)
    data[KEY] = clean
    records._write(folder, data)
    summary = summary_record(clean)
    if summary["address"]:
        existing = next((p for p in data.get("properties", []) if p.get("auto") == "intake"), None)
        records.save_item(folder, "properties", {**(existing or {}), **summary, "auto": "intake"})
    return clean


# ---------- the entry sheet: what to type where (PowerBroker habitational screens, Applied Quote) ----------
def _yn(v):
    return {"Yes": "Y", "No": "N"}.get(v, "")


def _upgrade(year):
    """PowerBroker wants C (complete) or P (partial) + the year; complete unless the client says otherwise."""
    return f"C  {year}" if year else ""


def pb_date(text):
    """PowerBroker and Applied Quote take dates as MM/DD/YYYY."""
    day = records.parse_date(text) if text else None
    return day.strftime("%m/%d/%Y") if day else (text or "")


def _count(n):
    return "" if n in (None, "") else str(int(n)) if float(n) == int(float(n)) else str(n)


def entry_sections(values, info=None, today=None):
    """[(screen title, [(label, value)])] for the entry sheet. Empty values show as a gap to fill in."""
    info = info or {}
    f = derive(values, today)
    use = f.get("use")
    families = 1 + int(f.get("rented_units", 0))
    pct = {"Copper": "% Copper 100", "PEX": "% PEX 100", "PVC / ABS": "% PVC 100", "Galvanized": "% Galvanized 100",
           "Poly-B": "% Poly-B 100", "Lead": "% Lead 100"}.get(values.get("plumbing", ""), values.get("plumbing", ""))
    phone = info.get("phone", "")
    out = [
        ("Customer screen", [
            ("Province", "ON  (not ONT)"), ("Home phone", phone), ("Cellular phone (Applied shows it as Mobile)", phone),
            ("Credit information consent", "as on the signed consent form")]),
        ("Supplementary screen", [
            ("Named insured", info.get("name", "")), ("Date of birth", pb_date(info.get("birth", ""))),
            ("Occupation", values.get("occupation", "")), ("Marital status", values.get("marital", "")),
            ("If several named insureds", "write their relationships in the application remarks")]),
        ("Habitational screen", [
            ("Prior insurer", values.get("prior_insurer", "")), ("Previous policy number", values.get("prior_policy", "")),
            ("Previous policy expiry", pb_date(values.get("prior_expiry", ""))),
            ("Claim history report date (HITS)", "the date the HITS report was run"),
            ("Continuously insured since", pb_date(values.get("insured_since", ""))),
            ("Applicant signed date", "the day the client signs"), ("Original binder date", "the day you bind")]),
    ]
    if use == "tenant":
        risk1 = [("Risk address", values.get("address", "")), ("Postal code", values.get("postal", "")),
                 ("Occupancy type", "Tenant"), ("Structure type", values.get("structure", "")),
                 ("Number of families", "1"), ("Smokers (Y/N)", _yn(values.get("smoker"))),
                 ("Contents value", values.get("contents_value", ""))]
    else:
        oil = " / ".join(x for x in (values.get("oil_year"), values.get("oil_place")) if x and x != "No oil tank")
        risk1 = [
            ("Risk address", values.get("address", "")), ("Postal code", values.get("postal", "")),
            ("Year built", values.get("year_built", "")), ("Number of storeys", values.get("storeys", "")),
            ("Total living area (sq ft)", values.get("sq_ft", "")), ("Number of families", str(families)),
            ("Smokers (Y/N)", _yn(values.get("smoker"))), ("Number of mortgages", values.get("mortgages", "")),
            ("Replacement cost evaluator", "EZITV (or the one used)"),
            ("Date evaluation completed", pb_date(values.get("ezitv_date", ""))),
            ("Replacement cost", values.get("value", "")), ("Structure type", values.get("structure", "")),
            ("Foundation type", values.get("foundation", "")), ("Finished basement", values.get("basement_pct", "")),
            ("Exterior wall", values.get("construction", "")),
            ("Upgrade - roof (C complete / P partial + year)", _upgrade(values.get("roof_year"))),
            ("Upgrade - electrical", _upgrade(values.get("electrical_year"))),
            ("Upgrade - heating", _upgrade(values.get("heating_year"))),
            ("Upgrade - plumbing", _upgrade(values.get("plumbing_year"))),
            ("Roof covering", values.get("roof_type", "")), ("Electrical wiring", values.get("wiring", "")),
            ("Electrical panel / service amps", " / ".join(x for x in (values.get("panel"), values.get("amps")) if x)),
            ("Primary heating", values.get("heating", "")), ("Plumbing type", pct), ("Oil tank: year / location", oil),
        ]
    out.append(("Risk 1 screen" if use != "tenant" else "Risk 1 screen (tenant)", risk1))
    if use != "tenant":
        sump = " / ".join(x for x in ("sump pump" if values.get("sump_pump") == "Yes" else "",
                                      "battery backup" if values.get("sump_battery") == "Yes" else "") if x)
        out.append(("Risk 2 screen", [
            ("Water heater year", values.get("water_heater_year", "")), ("Sump pump / auxiliary power", sump),
            ("Backup (backwater) valve", _yn(values.get("backwater_valve"))),
            ("Main water shut-off", _yn(values.get("water_shutoff"))),
            ("Sewer backup questionnaire attached", "Y if the client signed it, and its date"),
            ("Fire protection: hydrant within 300 m", _yn(values.get("hydrant"))),
            ("Fire hall distance", values.get("fire_hall", "")),
            ("Burglar alarm", values.get("burglar_alarm", "")), ("Fire alarm", values.get("fire_alarm", "")),
            ("Alarm certificate attached", "Y once the certificate is in the folder"),
            ("Full bathrooms / half bathrooms",
             " / ".join(x for x in (values.get("bathrooms"), values.get("half_baths")) if x)),
            ("Number of kitchens", values.get("kitchens", "")), ("Garage / carport", values.get("garage", ""))]))
        out.append(("Risk 3 screen", [
            ("Number of bedrooms", values.get("bedrooms", "")), ("Wood stoves", values.get("aux_heat", "")),
            ("Renewable energy", "yes: type, tied to grid, date, value" if values.get("solar_income") == "Yes" else "")]))
    out.append(("Risk 4 screen", [
        ("Mortgagee / loss payee", values.get("lender", "")),
        ("Nature of interest", "MG  Mortgagee" if values.get("lender") else ""),
        ("Occupancy date at this location", pb_date(values.get("occupancy_date", ""))),
        ("Previous address (if under 3 years here)", values.get("prior_address", "")),
        ("13. Liability: business at home", _yn(values.get("home_business"))),
        ("13. Rooms / units rented", _count(f.get("rented_units"))), ("13. Daycare", _yn(values.get("daycare"))),
        ("13. Trampoline", _yn(values.get("trampoline"))),
        ("13. Dogs / breeds of concern", _yn(values.get("risky_dog"))),
        ("13. Cannabis plants", _count(f.get("cannabis")))]))
    out.append(("Coverage screen", [
        ("Sewer Backup", "hand write the FULL POLICY LIMIT next to it" if values.get("wants_sewer") == "Yes" else ""),
        ("Overland water (Applied: Surface Water)",
         "hand write the FULL POLICY LIMIT next to it" if values.get("wants_overland") == "Yes" else ""),
        ("If not eligible for full limits", "a sign-off goes in with the application"),
        ("Claims", "check they migrated from Applied Quote")]))
    out.append(("Application remarks", [
        ("Claim details", values.get("claims_notes", "")),
        ("Always", "sign / effective / EZITV and HITS dates; address verification; UW approval name"),
        ("If the client pays by cheque / PAC", "DO NOT BIND UNTIL THE SIGNED APPLICATION WITH PAYMENT IS BACK")]))
    return out


def entry_text(sections):
    """The entry sheet as plain text for 'Copy all'."""
    lines = []
    for title, rows in sections:
        lines += [title.upper()] + [f"  {a}: {b}" for a, b in rows if b] + [""]
    return "\n".join(lines).strip()
