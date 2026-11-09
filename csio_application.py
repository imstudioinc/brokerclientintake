"""Reads a filled CSIO **Habitational Insurance Application** (CA2001e: the Home / Tenant application PowerBroker prints) and
turns it into answers for the Property details page plus the client's phone / email / birth date.

The PDF is flat (no form fields). The typed answers are 8-point text, the printed labels 6-7 point, so each answer is
found by the label to its left on the same line (or by a label word for the tick boxes). A tick box sits just BEFORE its
YES / NO label ("[ ] YES [X] NO"). Anything not found is simply left out; `prefill` only fills EMPTY answers.
Client documents are never kept in the repo (.gitignore covers application PDFs).
"""
import os
import re
from pathlib import Path

SKIP_WORDS = ("quote", "dash", "consent", "mvr", "licen", "cheque", "check", "ownership", "bill of sale", "lease",
              "commercial", "registration", "tire", "financ", "binder")
_found = {}            # (path, mtime) -> bool: is this PDF a CSIO habitational application


def _plumber():
    import pdfplumber
    return pdfplumber


def is_application(path):
    """True when the PDF's first page is a CSIO Habitational Insurance Application (cached by file time)."""
    try:
        key = (str(path), Path(path).stat().st_mtime)
    except OSError:
        return False
    if key not in _found:
        try:
            with _plumber().open(path) as pdf:
                text = (pdf.pages[0].extract_text() or "")
            _found[key] = "HABITATIONAL INSURANCE APPLICATION" in text.upper()
        except Exception:
            _found[key] = False
    return _found[key]


def find(folder):
    """The newest habitational application PDF in the client folder (one listing; first pages are read once), or None."""
    try:
        with os.scandir(folder) as entries:
            pdfs = [(e.stat().st_mtime, e.name) for e in entries
                    if e.is_file() and e.name.lower().endswith(".pdf")
                    and not any(w in e.name.lower() for w in SKIP_WORDS)]
    except OSError:
        return None
    for _m, name in sorted(pdfs, reverse=True):
        if is_application(Path(folder) / name):
            return Path(folder) / name
    return None


# ---------- reading one page: value runs (8 pt) and label words (smaller) ----------
def _page(pg):
    ws = pg.extract_words(extra_attrs=["size"], x_tolerance=1.5)
    labels = [w for w in ws if w["size"] < 7.9]
    vals = sorted((w for w in ws if 7.9 <= w["size"] < 8.7 and not re.fullmatch(r"\d+\.", w["text"])),
                  key=lambda w: w["top"])
    lines = []                                                # printed lines first, then left to right inside each
    for w in vals:
        if lines and abs(lines[-1][0] - w["top"]) < 3:
            lines[-1][1].append(w)
        else:
            lines.append([w["top"], [w]])
    runs = []
    for _top, line in lines:
        start = len(runs)
        for w in sorted(line, key=lambda w: w["x0"]):
            if len(runs) > start and 0 <= w["x0"] - runs[-1]["x1"] < 6:
                runs[-1]["text"] += " " + w["text"]
                runs[-1]["x1"] = w["x1"]
            else:
                runs.append({"text": w["text"], "x0": w["x0"], "x1": w["x1"], "top": w["top"]})
    for r in runs:
        left = [l for l in labels if abs(l["top"] - r["top"]) < 5 and l["x1"] <= r["x0"] + 1 and r["x0"] - l["x1"] < 90]
        r["left"] = " ".join(l["text"] for l in sorted(left, key=lambda l: l["x0"]))
    return {"labels": labels, "runs": runs}


def _run(page, left_re, xmin=0, xmax=9999, top=(0, 9999)):
    """The first value run whose left label ends with / matches left_re, inside the x range."""
    for r in page["runs"]:
        if xmin <= r["x0"] < xmax and top[0] <= r["top"] <= top[1] and re.search(left_re, r["left"], re.I) \
                and r["text"].strip() not in ("", "X"):
            return r["text"].strip()
    return ""


def _label(page, word_re, xmin=0, xmax=9999, top=(0, 9999)):
    return next((l for l in page["labels"] if re.fullmatch(word_re, l["text"].strip(",?:"), re.I)
                 and xmin <= l["x0"] < xmax and top[0] <= l["top"] <= top[1]), None)


def _digits_on_row(page, ref_top, xmin, xmax, tol=6):
    """Numbers printed in a row of boxes (YYYY MM DD): ['1991', '8', '3']."""
    out = []
    for r in sorted(page["runs"], key=lambda r: r["x0"]):
        if abs(r["top"] - ref_top) <= tol and xmin <= r["x0"] < xmax:
            out += re.findall(r"\d+", r["text"])
    return out


def _date(parts):
    if len(parts) >= 3 and len(parts[0]) == 4:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if 1900 < y < 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            pass
    return ""


def _yesno(page, anchor, xmin=0, xmax=9999, reach=26):
    """'Yes' / 'No' / '' for the tick box on the row of the label word `anchor` (a regex) in that column."""
    a = _label(page, anchor, xmin, xmax)
    if not a:
        return ""
    for r in page["runs"]:
        if r["text"].strip() != "X" or abs(r["top"] - a["top"]) > 9 or not (xmin <= r["x0"] < xmax):
            continue
        for l in sorted(page["labels"], key=lambda l: l["x0"]):
            if l["text"].strip().upper() in ("YES", "NO") and abs(l["top"] - r["top"]) < 9 \
                    and 0 <= l["x0"] - r["x1"] <= reach:
                return "Yes" if l["text"].strip().upper() == "YES" else "No"
    return ""


def _number(page, anchor, xmin, xmax):
    """The number printed at the end of the row of label `anchor` (a regex), inside the column."""
    a = _label(page, anchor, 0, xmax)
    if not a:
        return ""
    best = None
    for r in page["runs"]:
        if xmin <= r["x0"] < xmax and abs(r["top"] - a["top"]) <= 7 and re.fullmatch(r"[\d.]+", r["text"].strip()):
            if best is None or abs(r["top"] - a["top"]) < abs(best["top"] - a["top"]):
                best = r
    return best["text"].strip() if best else ""


def _phone(text):
    digits = re.sub(r"\D", "", text or "")
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 10 else ""


def _option(options, text):
    """The dropdown option that says what the application says ('Asphalt Shingles' -> 'Asphalt shingles')."""
    t = (text or "").strip().lower()
    return next((o for o in options if o.lower() == t), "")


def _title(text):
    return " ".join(w.capitalize() if not re.search(r"\d", w) or w.isalpha() else w for w in text.split())


# ---------- the whole application ----------
def read(path):
    """{"application": bool, "client": {name, phone, email, birth}, "answers": {property form key: value},
    "effective": ISO date, "carrier"} - {} when the PDF is not a habitational application."""
    import property_risk as risk
    opts = lambda k: risk.FIELDS[k][3] or []
    with _plumber().open(path) as pdf:
        if "HABITATIONAL INSURANCE APPLICATION" not in (pdf.pages[0].extract_text() or "").upper():
            return {}
        pages = [_page(pdf.pages[i]) for i in range(min(3, len(pdf.pages)))]
        texts = [(pdf.pages[i].extract_text() or "") for i in range(len(pdf.pages))]
    p1, p2, p3 = (pages + [{"labels": [], "runs": []}] * 3)[:3]
    out = {"application": True, "client": {}, "answers": {}}
    a, c = out["answers"], out["client"]

    # --- page 1: applicant, contact, period, history
    name = _run(p1, r"APPLICANT 1$", 0, 300) or _run(p1, r"NAME$", 0, 300, (110, 130))
    if "," in name and not _run(p1, r"APPLICANT 1$", 0, 300):
        last, first = name.split(",", 1)
        name = f"{first.strip()} {last.strip()}"
    c["name"] = name.upper()
    cell, home = _phone(_run(p1, r"CELL$", 0, 300)), _phone(_run(p1, r"HOME$", 0, 300))
    c["phone"] = cell or home
    email = _run(p1, r"EMAIL$", 0, 300)
    c["email"] = email.lower() if "@" in email else ""
    bl = _label(p1, r"BIRTH", 0, 300, (340, 400))
    c["birth"] = _date(_digits_on_row(p1, bl["top"] + 2, 100, 300)) if bl else ""
    el = _label(p1, r"EFFECTIVE", 0, 300, (290, 330))
    out["effective"] = _date(_digits_on_row(p1, el["top"] + 3, 100, 200)) if el else ""
    out["carrier"] = _run(p1, r"^$", 0, 200, (70, 95))
    occupation = _run(p1, r"OCCUPATION$", 0, 300)
    a["occupation"] = occupation

    if _yesno(p1, r"LOSSES", 0, 700) == "No":
        a["claims_5y"] = "0"
    if _yesno(p1, r"DECLINED", 0, 700) == "No":
        a["cancelled_5y"] = "No"
    first_time = _label(p1, r"FIRST", 300, 700, (500, 560))
    if first_time and any(r["text"].strip() == "X" and abs(r["top"] - first_time["top"]) < 9
                          and 0 <= first_time["x0"] - r["x1"] < 20 for r in p1["runs"]):
        a["first_time"] = a["no_prior"] = "Yes"

    # --- page 2: the building
    a["address"] = _title(_run(p2, r"ADDRESS$", 0, 300, (70, 95)))
    a["postal"] = _run(p2, r"POSTAL CODE$", 400, 700, (70, 95)).replace(" ", "")
    a["year_built"] = _run(p2, r"BUILT", 0, 100, (100, 125))
    st = re.sub(r"[()]", "", _run(p2, r"STORY", 100, 200, (100, 125)))
    try:
        v = float(st)
        a["storeys"] = "3 or more" if v >= 3 else ("%g" % v if v % 1 else str(int(v)))
        a["storeys"] = _option(opts("storeys"), a["storeys"])
    except ValueError:
        pass
    area = _run(p2, r"AREA$", 280, 400, (100, 125))
    if area.isdigit():
        metric = any(r["text"].strip() == "X" and 330 < r["x0"] < 350 and r["top"] > 113 for r in p2["runs"])
        a["sq_ft"] = str(round(int(area) * 10.764)) if metric else area
    kind = _run(p2, r"STRUCTURE TYPE$", 0, 300).lower()
    if kind:
        a["structure"] = ("Row / townhouse" if re.search(r"town|row", kind) else "Semi-detached" if "semi" in kind else
                          "Condo / apartment unit" if re.search(r"condo|apartment|unit", kind) else
                          "Detached" if "detach" in kind else "")
    hyd = _run(p2, r"DISTANCE TO HYDRANT$", 380, 700).lower()
    if hyd:
        a["hydrant"] = "Yes" if hyd.startswith("within") else "No" if re.search(r"over|beyond|unprot", hyd) else ""
    hall = _run(p2, r"FIRE HALL$", 380, 700, (230, 270)).lower()
    m = re.search(r"(within|over)\s+(\d+)", hall)
    if m:
        km = int(m.group(2))
        a["fire_hall"] = ("Within 5 km" if m.group(1) == "within" and km <= 5 else
                          "5 to 13 km" if m.group(1) == "within" and km <= 13 else "Over 13 km")
    for key, label in (("fire_alarm", r"FIRE$"), ("burglar_alarm", r"BURGLARY$")):
        t = _run(p2, label, 380, 700, (280, 340)).lower()
        if t:
            a[key] = "Monitored" if t.startswith("monitored") else "Local only" if "local" in t else \
                "None" if t.startswith("none") else ""
    smoker = _run(p2, r"SMOKERS\?$", 500, 700)
    if smoker:
        a["smoker"] = "Yes" if smoker.upper().startswith("Y") else "No"
    for key, label in (("roof_year", r"ROOF$"), ("electrical_year", r"ELECTRICAL$"),
                       ("heating_year", r"HEATING$"), ("plumbing_year", r"PLUMBING$")):
        y = _run(p2, label, 100, 330, (430, 500))
        if re.fullmatch(r"(19|20)\d\d", y):
            a[key] = y
    wh = _run(p2, r"WATER HEATER YEAR$", 250, 400)
    if re.fullmatch(r"(19|20)\d\d", wh):
        a["water_heater_year"] = wh
    a["roof_type"] = _option(opts("roof_type"), _run(p2, r"ROOF COVERING TYPE$", 0, 300))
    a["wiring"] = _option(opts("wiring"), _run(p2, r"ELECTRICAL WIRING TYPE$", 0, 300))
    apparatus = _run(p2, r"APPARATUS$", 0, 200, (580, 610)).lower()
    fuel = _run(p2, r"FUEL$", 0, 200, (600, 630)).lower()
    if apparatus or fuel:
        both = f"{apparatus} {fuel}"
        a["heating"] = ("Heat pump / geothermal" if re.search(r"geotherm|heat pump", both) else
                        "Hot water / radiant" if re.search(r"boiler|radiant", both) else
                        "Wood or pellet stove" if re.search(r"wood|pellet", both) else
                        "Gas forced air" if "natural gas" in fuel and "furnace" in apparatus else
                        "Oil" if "oil" in fuel else "Propane" if "propane" in fuel else
                        "Electric" if "electric" in both else "")
    full = _run(p2, r"NO\. OF FULL$", 450, 560)
    half = _run(p2, r"NO\. OF HALF$", 540, 700)
    kitchens = _run(p2, r"KITCHENS$", 400, 700)
    for key, v in (("bathrooms", full), ("half_baths", half), ("kitchens", kitchens)):
        if v.isdigit():
            a[key] = v
    garage = _run(p2, r"GARAGE TYPE$", 400, 700).lower()
    if garage:
        a["garage"] = ("Attached" if re.search(r"built|attach", garage) else "Detached" if "detach" in garage else
                       "Carport" if "carport" in garage else "")

    # --- page 3: address history, liability exposures
    od = _label(p3, r"OCCUPANCY", 100, 400, (320, 345))
    a["occupancy_date"] = _date(_digits_on_row(p3, od["top"] + 5, 200, 330)) if od else ""
    for key, anchor, lo, hi in (("trampoline", r"TRAMPOLINE", 0, 330), ("home_business", r"OPERATION", 330, 700)):
        a[key] = _yesno(p3, anchor, lo, hi)
    if _number(p3, r"DOGS", 500, 700) == "0":
        a["risky_dog"] = "No"
    daycare = _number(p3, r"DAYCARE", 200, 330)
    if daycare == "0":
        a["daycare"] = "No"
    if _number(p3, r"CANNABIS", 500, 700) != "":
        a["cannabis"] = _number(p3, r"CANNABIS", 500, 700)

    # --- the text pages: coverages and the remarks the broker's system adds
    page_text = "\n".join(texts)
    m = re.search(r"PERSONAL PROPERTY\s+REQUESTED\s+\$([\d,]+)", page_text)
    if m:
        a["contents_value"] = m.group(1).replace(",", "")
    m = re.search(r"COVERAGE FORM TYPE\s+\d+\s*-\s*(\w+)", page_text)
    if m:
        a["form"] = _option(opts("form"), m.group(1)) or ("Basic / named perils" if m.group(1).lower() == "basic" else "")
    if re.search(r"Sewer Backup:\s*declined", page_text, re.I):
        a["wants_sewer"] = "No"
    if re.search(r"Coverage declined:[^\n]*Overland", page_text, re.I):
        a["wants_overland"] = "No"
    m = re.search(r"Claims \(5 Years\):\s*(yes|no)", page_text, re.I)
    if m and m.group(1).lower() == "no":
        a["claims_5y"] = "0"
    m = re.search(r"Combined Policy:\s*yes", page_text, re.I)
    if m:
        a["standalone"] = "No"
    m = re.search(r"Address 1:\s*(.+?)\s*\|", page_text)
    if m:
        a["prior_address"] = m.group(1).strip()
    out["answers"] = {k: v for k, v in a.items() if str(v).strip()}
    out["client"] = {k: v for k, v in c.items() if v}
    return out


def prefill(values, answers):
    """values + the application's answers for questions that are still empty (never overwrites)."""
    out = dict(values)
    for k, v in answers.items():
        if v and not str(out.get(k, "")).strip():
            out[k] = v
    return out
