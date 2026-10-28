"""The client's own details read from the quote and the DASH report.

The quote has the name, licence #, date of birth, phone and email (top right of page 1);
the DASH report has the name, licence # and date of birth. Missing profile details are filled
from them (never overwritten), and anything that doesn't match the profile - or that the quote
and DASH disagree on - becomes a warning. Runs each time the client is shown, so details appear
as soon as a new document lands in the folder. Each PDF is read once per change (cached).
"""
import datetime
import re

import pdfplumber

import quote
from fill_consent import _raw, _same_person, format_dln

FIELDS = (("dln", "licence #"), ("birth", "date of birth"), ("phone", "phone"), ("email", "email"))
_cache = {}      # (path, mtime) -> what was read


def _cached(path, reader):
    try:
        key = (str(path), path.stat().st_mtime)
    except OSError:
        return None
    if key not in _cache:
        try:
            _cache[key] = reader(path)
        except Exception:
            _cache[key] = None
    return _cache[key]


def _phone(text):
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 10 else ""


def read_dash(path):
    """[{name, dln, birth}] - one driver per DASH report."""
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    name = re.search(r"DRIVER REPORT\s*\n(.+?)\s+Report Date:", text)
    if not name:
        return []
    name = name.group(1).strip().upper()
    if "," in name:                                  # "LAST, FIRST" -> "FIRST LAST"
        last, first = name.split(",", 1)
        name = f"{first.strip()} {last.strip()}"
    dln = re.search(r"DLN:\s*([A-Z0-9-]+)", text)
    birth = re.search(r"Date of Birth:\s*(\d{4}-\d{2}-\d{2})", text)
    return [{"name": name, "dln": format_dln(dln.group(1)) if dln else "",
             "birth": birth.group(1) if birth else ""}]


def _quote_contact(path):
    """Phone and email from the applicant's block, top right of page 1 (the left one is the brokerage)."""
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        stop = next((w["top"] for w in words if w["text"] == "Policy" and w["x0"] < page.width / 3), 200)
        lines = {}
        for w in words:
            if w["x0"] > page.width / 2 and w["top"] < stop:
                lines.setdefault(round(w["top"]), []).append(w["text"])
    lines = [" ".join(v) for _, v in sorted(lines.items())]
    phones = {}
    for line in lines:
        m = re.match(r"^(\w+):\s*(.+)$", line)
        if m and _phone(m.group(2)):
            phones.setdefault(m.group(1).lower(), _phone(m.group(2)))
    phone = next((phones[k] for k in ("mobile", "cell", "phone", "home") if k in phones),
                 next(iter(phones.values()), ""))
    email = next((l.lower() for l in lines if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", l)), "")
    return phone, email


def read_quote(path):
    """[{name, dln, birth, phone, email}] - one per driver; phone / email belong to the applicant (driver 1)."""
    q = quote.read(str(path))
    phone, email = _quote_contact(path)
    out = []
    for i, d in enumerate(q.get("drivers", [])):
        out.append({"name": (d.get("name") or "").upper(), "dln": format_dln(d.get("licence") or ""),
                    "birth": d["birth"].isoformat() if d.get("birth") else "",
                    "phone": phone if i == 0 else "", "email": email if i == 0 else ""})
    return out


def _the_client(people, name, dln):
    """The client among a document's drivers: same licence #, else a matching name, else the
    applicant (first) when nothing else fits."""
    if not people:
        return None
    if dln:
        same = [p for p in people if p["dln"] and _raw(p["dln"]) == _raw(dln)]
        if same:
            return same[0]
    named = [p for p in people if _same_person(name, p["name"])]
    return named[0] if named else people[0]


def _same_name(a, b):
    ta, tb = set(a.upper().split()), set(b.upper().split())
    return bool(ta and tb) and (ta <= tb or tb <= ta)      # a middle name on one side is fine


def check(folder, docs, info):
    """Read the newest quote and the client's DASH report.

    Returns (fill, warnings): fill = {field: (value, source)} for profile details that are empty
    but found in a document; warnings = lines for details that don't match.
    """
    name, dln = folder.name, info.get("dln", "")
    found = []           # (source, person)
    quotes = docs.get("Quote (ARS)") or []
    if quotes:
        person = _the_client(_cached(quotes[-1], read_quote) or [], name, dln)
        if person:
            found.append(("quote", person))
    dash_people = [p for f in docs.get("DASH report") or [] for p in (_cached(f, read_dash) or [])]
    person = _the_client(dash_people, name, dln)
    if person and (len(dash_people) == 1 or _same_person(name, person["name"], dln, person["dln"])):
        found.append(("DASH", person))

    fill, warnings = {}, []
    differ = {}                                   # (label, shown value, profile value) -> sources
    for source, p in found:
        if p["name"] and not _same_name(name, p["name"]):
            differ.setdefault(("Name", p["name"], name), []).append(source)
    for key, label in FIELDS:
        values = [(s, p[key]) for s, p in found if p.get(key)]
        if not values:
            continue
        mine = info.get(key, "")
        norm = (lambda v: _raw(v)) if key == "dln" else (lambda v: re.sub(r"\D", "", v)) if key == "phone" \
            else (lambda v: v.strip().lower())
        if mine:
            for s, v in values:
                if norm(v) != norm(mine):
                    differ.setdefault((label.capitalize(), _show(key, v), _show(key, mine)), []).append(s)
        else:
            fill[key] = values[0][1], values[0][0]
            for s, v in values[1:]:
                if norm(v) != norm(values[0][1]):
                    warnings.append(f"{label.capitalize()}: {values[0][0]} says {_show(key, values[0][1])}, "
                                    f"{s} says {_show(key, v)}")
    warnings = [f"{label} on the {' and '.join(sources)}: {theirs}  (profile: {mine})"
                for (label, theirs, mine), sources in differ.items()] + warnings
    return fill, warnings


def _show(key, value):
    if key == "birth":
        try:
            return datetime.date.fromisoformat(value).strftime("%b %d, %Y")
        except ValueError:
            pass
    return value


def apply(folder, docs, info, save):
    """Fill empty profile details from the documents. Returns (filled labels with source, warnings)."""
    fill, warnings = check(folder, docs, info)
    if fill:
        save(folder, **{k: v for k, (v, _) in fill.items()})
        info.update({k: v for k, (v, _) in fill.items()})
    labels = dict(FIELDS)
    filled = [f"{labels[k]} ({s})" for k, (_, s) in fill.items()]
    return filled, warnings


def _month(d):
    return d.strftime("%b %Y")


def _car(text):
    """'2019 HONDA CIVIC LX 4DR' -> '2019 Honda Civic LX 4DR' (short codes stay in capitals)."""
    return " ".join(w.capitalize() if w.isalpha() and len(w) > 3 else w for w in text.split())


def quote_email_values(folder, client_name=""):
    """Email template blanks read from the newest quote: {"common": {key: value},
    "carriers": [{"insurer", "quote_number", "premium", "declined"}]} - None without a readable quote."""
    import review
    quotes = review.find_docs(folder)["quote"]
    q = _cached(quotes[0], lambda p: quote.read(str(p))) if quotes else None
    if not q or not q.get("drivers"):
        return None
    named = [d for d in q["drivers"] if client_name and _same_name(client_name, d.get("name") or "")]
    d = named[0] if named else q["drivers"][0]
    common = {}
    if q.get("effective"):
        common["effective_date"] = q["effective"].strftime("%b %d, %Y").replace(" 0", " ")
    vehicles = q.get("vehicles", [])
    if vehicles:
        common["vehicle"] = "; ".join(_car(v["description"]) for v in vehicles)
        cov = {k.lower(): v for k, v in vehicles[0]["coverages"].items()}
        ded = [f"${cov[k]} {k}" for k in ("all perils", "collision", "comprehensive", "specified perils")
               if cov.get(k)]
        common["deductible"] = " / ".join(ded) if ded else "No physical damage (liability only)"
        if not any(k.startswith("#23") for v in vehicles for k in v["coverages"]):
            common["lienholder"] = "None"
    if d.get("class"):
        dates = [f"{k.upper()} {_month(d[k])}" for k in ("g1", "g2", "g") if d.get(k)]
        common["licence"] = d["class"] + (f" ({', '.join(dates)})" if dates else "")
    since = d.get("date_insured")
    if since:
        months = ((q.get("effective") or datetime.date.today()) - since).days // 30
        common["experience"] = f"Insured since {since:%B %Y}" + (f" (about {months} months)" if months < 24 else "")
        if d.get("lapses"):
            common["experience"] += f"; {len(d['lapses'])} lapse(s) on the quote"
    else:
        common["experience"] = "No prior insurance"
    carriers = [{"insurer": c["name"], "quote_number": c.get("reference") or "",
                 "premium": f"${c['premium']:,.0f}" if c.get("premium") else "",
                 "declined": any(review.carrier_message(m) == "decline" for m in c.get("messages", []))}
                for c in q.get("carriers", [])]
    carriers.sort(key=lambda c: (c["declined"], not c["premium"]))     # bindable quotes first
    return {"common": common, "carriers": carriers}
