"""Fill WellCare's Commercial Insurance Application (templates/WellCare Commercial Application.pdf).

The answers come from the client's Commercial details (tracking.json "commercial_intake", see commercial_risk.py).
The application is an Acrobat "dynamic" form: its **Liability Only** box runs a script that throws away the
location / construction / protection / property pages and adds one short liability page (template T7); unticked,
it adds pages T3-T6. Here the same thing is done without the script: the output holds

    cover page + liability page + (property pages T3-T6 | the liability-only page T7) [+ extra location pages]

so a liability-only application never shows (or asks for) the property side. The answers are written onto the
pages as text and tick marks and the form fields / script are dropped, so it looks the same in every viewer and
nothing re-arranges itself when opened. Boxes are found in the template by their field names / positions.
"""
import datetime
import re
from pathlib import Path

import commercial_risk as risk
import records

TEMPLATE = Path(__file__).parent / "templates" / "WellCare Commercial Application.pdf"
HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556,
        556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667,
        556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556,
        556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722,
        500, 500, 500, 334, 260, 334, 584]                       # Helvetica widths for ASCII 32..126

# ---- where each answer goes. Text boxes: answer key -> field name on that page; tick boxes: (key, option) -> field name
P1_TEXT = {"broker_name": "BrokerName", "branch": "BrokerNo", "pb_code": "Client Code", "effective_date": "Effective Date",
           "legal_name": "Name2", "address": "Address", "city": "City", "province": "Province", "country": "Country",
           "postal": "Postal Code", "phone": "Phone", "email": "Email", "website": "Web Site",
           "description": "Description of business operations", "known_month": "I have known this client since",
           "known_year": "month", "supporting_business": "Supporting Business"}
for _r in range(1, 5):
    for _k, _n in (("last", "Last Name"), ("first", "First Name"), ("title", "MrMs"), ("position", "Position"),
                   ("phone", "Phone"), ("email", "Email"), ("other", "Other")):
        P1_TEXT[f"contact{_r}_{_k}"] = f"{_n}Row{_r}"
P1_CHECK = {("liability_only", "Yes"): "Check Box70", ("entity", "Sole proprietor"): "Check Box1",
            ("entity", "Corporation"): "Check Box2"}

P2_TEXT = {"in_business_since": "In business since", "employees_ft": "Employees ft", "employees_pt": "Employees pt",
           "years_experience": "Related prior experience Number of years", "receipts": "Annual gross receipts",
           "pct_internet": "Internet", "pct_subtrades": "Subtrades", "pct_canada": "Canadian", "pct_us": "US",
           "pct_foreign": "Foreign", "payroll": "Annual Payroll", "receipts_liquor": "Liquor", "receipts_food": "Food",
           "receipts_other": "Other", "claims_notes": "Prior claims unknown", "occupancy_other": "Other_2",
           "prior_type": "TypeRow1_2", "prior_insurer": "InsurerRow1", "prior_effective": "EffectiveRow1",
           "prior_expiry": "ExpiryRow1", "prior_terminated": "Reason terminatedRow1",
           "prior_cancelled": "Reason cancelledRow1",
           "exposure_left_distance": "aaa", "exposure_left_occupancy": "a", "exposure_right_distance": "bbb",
           "exposure_right_occupancy": "b", "exposure_behind_distance": "ccc", "exposure_behind_occupancy": "bv",
           "exposure_front_distance": "ddd", "exposure_front_occupancy": "vvv"}
P2_CHECK = {("wcb", "Yes"): "Check Box265", ("liquor", "Yes"): "Check Box3", ("liquor", "No"): "Check Box4",
            ("liquor_plan", "Yes"): "Check Box5", ("liquor_plan", "No"): "Check Box6",
            ("no_claims", "Yes"): "Check Box7", ("claims_unknown", "Yes"): "Check Box8",
            ("no_prev_policies", "Yes"): "Check Box9", ("prior_carrier_unknown", "Yes"): "Check Box10",
            ("occupancy", "Retail strip plaza"): "Check Box11", ("occupancy", "Industrial plaza"): "Check Box12",
            ("occupancy", "Enclosed mall"): "Check Box13", ("exposure_types", risk.EXPOSURE_TYPES[0]): "Check Box14",
            ("exposure_types", risk.EXPOSURE_TYPES[1]): "Check Box15"}
# the claims grid (rows run down the page, so they are found by position): column -> x of its boxes
CLAIM_COLUMNS = {"date": 26, "type": 84, "description": 192, "paid": 453, "reserve": 503, "status": 548}

# the location page (T3, and the extra "location" pages): General + Construction
LOC_TEXT = {"loc_number": "Location number", "loc_visit_date": "Date visited byproducer", "loc_address": "Address_2",
            "loc_city": "City_2", "loc_province": "Province_2", "loc_country": "Country_2",
            "loc_postal": "Postal Code_2", "loc_inspect_date": "Date risk was inspected", "loc_inspector": "Inspected by",
            "storeys": "Stories", "year_built": "Year Built", "sq_ft": "Total Area"}


def _boxes(key, options, numbers):
    return {(key, o): (n if isinstance(n, str) else f"Check Box{n}") for o, n in zip(options, numbers)}


LOC_CHECK = {("loc_visited", "Yes"): "Check Box16", ("loc_visited", "No"): "Check Box17",
             ("loc_not_inspected", "Yes"): "Check Box18"}
LOC_CHECK.update(_boxes("loc_rating", risk.RATING, [19, 20, 21, 22, 23, 24]))
LOC_CHECK.update(_boxes("area_unit", risk.AREA_UNIT, [25, 26]))
LOC_CHECK.update(_boxes("walls", risk.WALLS, [27, 31, 35, 39, 28, 32, 36, 40, 29, 33, 37, 41, 30, 34, 38, 42]))
LOC_CHECK.update(_boxes("floors", risk.FLOORS, [43, 46, 49, 52, 44, 47, 50, 53, 45, 48, 51]))
LOC_CHECK.update(_boxes("basement", risk.BASEMENT, [54, 57, 60, 63, 55, 58, 61, 64, 56, 59, 62]))
LOC_CHECK.update(_boxes("roof", risk.ROOF, [65, 67, 69, 71, 66, 68]))
LOC_CHECK.update(_boxes("roof_cover", risk.ROOF_COVER, [72, 74, 76, 78, 73, 75]))
LOC_CHECK.update(_boxes("electrical", risk.ELECTRICAL, [79, 80, 81]))
LOC_CHECK.update(_boxes("plumbing", risk.PLUMBING, [83, 85, 87, 89, 84, 86]))
LOC_CHECK.update(_boxes("heating", risk.HEATING, [90, 93, 96, 99, 91, 94, 97, 100, 92, 95, 98]))
LOC_CHECK.update(_boxes("fuel", risk.FUEL, [102, 104, 106, 107, 103]))

# T4: renovations, fire and crime protection
T4_TEXT = {"wiring_year": "7", "wiring_extent": "3", "plumbing_year": "8", "plumbing_extent": "4",
           "heating_year": "9", "heating_extent": "5", "roof_year": "10", "roof_extent": "6"}
T4_CHECK = {("reno_none", "Yes"): "Check Box108"}
T4_CHECK.update(_boxes("hydrant", risk.HYDRANT, [113, 115, 117, 119]))
T4_CHECK.update(_boxes("fire_hall", risk.FIRE_HALL, [114, 116, 118, 120]))
T4_CHECK.update(_boxes("extinguishing", risk.EXTINGUISHING, [121, "Check Box123.0", 124, 125, 122]))
T4_CHECK.update(_boxes("agent", risk.AGENT, [126, 128, 130, 131, 127, 129]))
T4_CHECK.update(_boxes("fire_alarm", risk.FIRE_ALARM, [132, 133, 134, 135]))
T4_CHECK.update(_boxes("crime_types", risk.CRIME_TYPES, [136, 137, 138, 139, 140, 148, 155, 162, 141, 149, 156, 163,
                                                         142, 150, 157, 164, 143, 151, 158, 165, 144, 152, 159, 166,
                                                         145, 153, 160, 167, 146, "Check Box154.0", 161, 168, 147]))
T4_CHECK.update(_boxes("burglar_alarm", risk.BURGLAR_ALARM, [169, 171, 173, 175, 170, 172, 174, 176]))
T4_CHECK.update(_boxes("safe_type", risk.SAFE_TYPE, [177, 179, 181, 183]))
T4_CHECK.update(_boxes("safe_class", risk.SAFE_CLASS, [178, 180, 182, 184, 185, 186]))
RENO_BOXES = {"wiring": "Check Box109", "plumbing": "Check Box110", "heating": "Check Box111", "roof": "Check Box112"}
# a ticked "Other (describe)" box with its words written after it:  (answer key, option) -> the key holding the words
WORDS_AFTER = {("extinguishing", "Other"): "extinguishing_other", ("crime_types", "Other"): "crime_other",
               ("safe_class", "Other"): "safe_class_other"}

MONEY_KEYS = {"receipts", "payroll", "receipts_liquor", "receipts_food", "receipts_other"}
DATE_KEYS = {"effective_date": "%b %d, %Y", "app_date": "%B %d, %Y", "loc_visit_date": "%m/%d/%Y",
             "loc_inspect_date": "%m/%d/%Y", "prior_effective": "%m/%d/%Y", "prior_expiry": "%m/%d/%Y"}


# ---------------------------------------------------------------- reading the template
def _pypdf():
    import pypdf
    return pypdf


def _fullname(annot):
    names, node = [], annot
    while node is not None:
        if "/T" in node:
            names.append(str(node["/T"]))
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return ".".join(reversed(names))


def _widgets(page):
    """[(name, kind, x0, y0, x1, y1)] of the form boxes on a page (kind: Tx, Btn, Ch)."""
    out = []
    for a in page.get("/Annots", []):
        a = a.get_object()
        if a.get("/Subtype") != "/Widget":
            continue
        ft = a.get("/FT")
        if ft is None and "/Parent" in a:
            ft = a["/Parent"].get_object().get("/FT")
        x0, y0, x1, y1 = (float(v) for v in a["/Rect"])
        out.append((_fullname(a), str(ft).lstrip("/"), min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    return out


class Template:
    """The blank application, split into the pages Acrobat's script would put together."""

    def __init__(self, path=TEMPLATE):
        pypdf = _pypdf()
        self.reader = pypdf.PdfReader(str(path))
        names = self.reader.trailer["/Root"]["/Names"]["/Templates"]["/Names"]
        self.templates = {str(names[i]): names[i + 1].get_object() for i in range(0, len(names), 2)}
        self.pages = {"P1": self.reader.pages[0], "P2": self.reader.pages[1]}
        self.pages.update({k: v for k, v in self.templates.items()})
        self._cache = {}

    def page_object(self, page_id):
        """A real page for the writer (the templates are page-like dictionaries without /Type /Page)."""
        pypdf = _pypdf()
        from pypdf.generic import NameObject
        src = self.pages[page_id]
        if page_id in ("P1", "P2"):
            return src
        page = pypdf.PageObject(self.reader)
        for k, v in src.items():
            page[NameObject(k)] = v
        page[NameObject("/Type")] = NameObject("/Page")
        return page

    def widgets(self, page_id):
        if page_id not in self._cache:
            self._cache[page_id] = _widgets(self.pages[page_id])
        return self._cache[page_id]

    def named(self, page_id, name):
        """The first box with this field name, as (x0, y0, x1, y1), or None."""
        for n, _k, x0, y0, x1, y1 in self.widgets(page_id):
            if n == name:
                return (x0, y0, x1, y1)
        return None

    def column(self, page_id, x, kinds=("Tx", "Ch"), band=(0, 792)):
        """Boxes whose left edge is near x, top to bottom (one distinct box per row); band = distance from the page top."""
        found = sorted((w for w in self.widgets(page_id) if w[1] in kinds and abs(w[2] - x) < 3
                        and band[0] <= 792 - w[5] <= band[1]), key=lambda w: -w[5])
        rows = []
        for w in found:
            if not rows or abs(rows[-1][5] - w[5]) > 6:
                rows.append(w)
        return [(w[2], w[3], w[4], w[5]) for w in rows]

    def schedule_rows(self, page_id):
        """The rows of a schedule of coverages page, top to bottom: {inc, basis_text, basis_boxes, ded, limit, desc}."""
        rows = []
        for w in sorted(self.widgets(page_id), key=lambda w: -w[5]):
            for row in rows:
                if abs(row["y"] - w[5]) < 6:
                    row["w"].append(w)
                    break
            else:
                rows.append({"y": w[5], "w": [w]})
        out = []
        for row in rows:
            ws = row["w"]
            rect = lambda w: (w[2], w[3], w[4], w[5])  # noqa: E731
            ded = [w for w in ws if w[1] == "Tx" and 380 < w[2] < 400]
            lim = [w for w in ws if w[1] == "Tx" and w[2] > 460]
            if not ded or not lim:
                continue                                          # broker notes, buttons ...
            inc = [w for w in ws if w[1] == "Btn" and w[2] < 100]
            bn = sorted((w for w in ws if w[1] == "Btn" and 260 < w[2] < 340), key=lambda w: w[2])
            basis = [w for w in ws if w[1] == "Tx" and 260 < w[2] < 330]
            desc = [w for w in ws if w[1] == "Tx" and w[2] < 100]
            out.append({"inc": rect(inc[0]) if inc else None, "bn": [rect(w) for w in bn],
                        "basis": rect(basis[0]) if basis else None, "ded": rect(ded[0]), "limit": rect(lim[0]),
                        "desc": rect(desc[0]) if desc else None})
        return out


# ---------------------------------------------------------------- drawing
def _width(text, size):
    return sum(HELV[ord(c) - 32] if 32 <= ord(c) <= 126 else 556 for c in text) * size / 1000.0


def _escape(text):
    data = text.encode("cp1252", "replace").decode("latin-1")
    return data.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text, size, width):
    lines = []
    for para in str(text).replace("\r", "").split("\n"):
        line = ""
        for word in para.split(" "):
            trial = (line + " " + word).strip() if line else word
            if line and _width(trial, size) > width:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    return lines


class Canvas:
    """The text and tick marks for one page, as PDF drawing operators."""

    def __init__(self):
        self.ops = []

    def text(self, rect, text, size=9.0, pad=2.0):
        text = " ".join(str(text).split())
        if not text:
            return
        x0, y0, x1, y1 = rect
        room = max(10.0, x1 - x0 - 2 * pad)
        size = min(size, max(6.0, (y1 - y0) * 0.78))
        if _width(text, size) > room:
            size = max(5.5, size * room / _width(text, size))
        y = y0 + (y1 - y0 - size) / 2 + size * 0.22
        self.ops.append(f"q {x0:.2f} {y0 - 1:.2f} {x1 - x0:.2f} {y1 - y0 + 2:.2f} re W n BT /HvOv {size:.2f} Tf "
                        f"{x0 + pad:.2f} {y:.2f} Td ({_escape(text)}) Tj ET Q")

    def area(self, rect, text, size=9.0, pad=3.0, min_size=5.5):
        """Wrapped text from the top of a tall box, shrunk until it fits."""
        text = str(text).strip()
        if not text:
            return
        x0, y0, x1, y1 = rect
        room, height = x1 - x0 - 2 * pad, y1 - y0 - 2 * pad
        while True:
            lines = _wrap(text, size, room)
            if len(lines) * size * 1.18 <= height or size <= min_size:
                break
            size -= 0.5
        lines = lines[:max(1, int(height // (size * 1.18)))]
        y = y1 - pad - size
        body = "".join(f"1 0 0 1 {x0 + pad:.2f} {y - i * size * 1.18:.2f} Tm ({_escape(line)}) Tj " for i, line in enumerate(lines))
        self.ops.append(f"q {x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f} re W n BT /HvOv {size:.2f} Tf {body}ET Q")

    def tick(self, rect):
        x0, y0, x1, y1 = rect
        inset = 2.2
        a, b, c, d = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        self.ops.append(f"q 0 0 0 RG 1.3 w {a:.2f} {b:.2f} m {c:.2f} {d:.2f} l S {a:.2f} {d:.2f} m {c:.2f} {b:.2f} l S Q")

    def data(self):
        return ("\n".join(self.ops) + "\n").encode("latin-1")


# ---------------------------------------------------------------- the answers -> drawing
def _money(v):
    n = records.money(v)
    return f"${n:,.0f}" if n else str(v)


def _shown(key, value):
    value = str(value or "").strip()
    if not value:
        return ""
    if key in DATE_KEYS:
        day = records.parse_date(value)
        return day.strftime(DATE_KEYS[key]).replace(" 0", " ") if day else value
    if key in MONEY_KEYS or re.fullmatch(r"claim\d_(paid|reserve)", key) or re.fullmatch(r"misc\d+_limit", key):
        return _money(value)
    if re.fullmatch(r"claim\d_date", key):                 # typed as mm/dd/yyyy: kept as typed; a calendar date is converted
        day = records.parse_date(value) if "/" not in value else None
        return day.strftime("%m/%d/%Y") if day else value
    return value


def _loc_values(values, n):
    """Location n's answers under the plain names (location 1 falls back to the business address)."""
    p = "" if n == 1 else f"l{n}_"
    out = {k: values.get(p + k, "") for k in set(LOC_TEXT) | {k for k, _o in LOC_CHECK}}
    if n == 1:
        for k, src in (("loc_address", "address"), ("loc_city", "city"), ("loc_province", "province"),
                       ("loc_country", "country"), ("loc_postal", "postal")):
            out[k] = out.get(k) or values.get(src, "")
    return out


def _draw_checks(canvas, tpl, page_id, table, values, extra_text=None):
    for (key, option), name in table.items():
        v = values.get(key, "")
        if not v:
            continue
        on = (option in risk.multi_values(v)) if key in MULTI_KEYS else (v == option)
        rect = tpl.named(page_id, name) if on else None
        if rect:
            canvas.tick(rect)
            words = WORDS_AFTER.get((key, option))
            if words and values.get(words):
                canvas.text((232, rect[1] - 1, 575, rect[3] + 1), values[words], size=9)    # after the printed "Other (describe)"


MULTI_KEYS = {k for k, f in risk.FIELDS.items() if f[2] == "multi"} | {"walls", "floors", "basement", "roof",
                                                                      "roof_cover", "plumbing", "heating", "fuel",
                                                                      "crime_types", "agent", "safe_type"}


def _draw_texts(canvas, tpl, page_id, table, values, area=("description", "claims_notes", "broker_notes")):
    for key, name in table.items():
        text = _shown(key, values.get(key, ""))
        rect = tpl.named(page_id, name) if text else None
        if not rect:
            continue
        if key in area:
            canvas.area(rect, text)
        else:
            canvas.text(rect, text)


def _page_one(canvas, tpl, values):
    _draw_texts(canvas, tpl, "P1", P1_TEXT, values)
    _draw_checks(canvas, tpl, "P1", P1_CHECK, values)


def _page_two(canvas, tpl, values):
    _draw_texts(canvas, tpl, "P2", P2_TEXT, values)
    _draw_checks(canvas, tpl, "P2", P2_CHECK, values)
    for column, x in CLAIM_COLUMNS.items():
        for row, rect in enumerate(tpl.column("P2", x, band=(295, 375)), start=1):
            if row > 5:
                break
            text = _shown(f"claim{row}_{column}", values.get(f"claim{row}_{column}", ""))
            if text:
                canvas.text(rect, text, size=8)
    mortgage = [l for l in str(values.get("mortgagee", "")).replace("\r", "").split("\n") if l.strip()]
    if len(mortgage) == 1 and len(mortgage[0]) > 95:                      # one long line: wrap it over the three lines
        mortgage = _wrap(mortgage[0], 8.5, 480)
    for i, line in enumerate(mortgage[:3], start=1):
        rect = tpl.named("P2", f"Mortgage {i}")
        if rect:
            canvas.text(rect, line, size=9)


def _location_page(canvas, tpl, page_id, values, n):
    v = _loc_values(values, n)
    _draw_texts(canvas, tpl, page_id, LOC_TEXT, v)
    _draw_checks(canvas, tpl, page_id, LOC_CHECK, v)


def _page_four(canvas, tpl, values):
    _draw_texts(canvas, tpl, "T4", T4_TEXT, values)
    _draw_checks(canvas, tpl, "T4", T4_CHECK, values)
    for part, name in RENO_BOXES.items():          # a renovation line is ticked when it has a year or an extent
        if values.get(f"{part}_year") or values.get(f"{part}_extent"):
            rect = tpl.named("T4", name)
            if rect:
                canvas.tick(rect)


def _schedule(canvas, tpl, page_id, values, groups):
    """The schedule rows of one page: they run top to bottom in the same order as risk.SCHEDULE (restricted to groups)."""
    wanted = [r for r in risk.SCHEDULE if r[3] in groups]
    for (row_key, _label, basis, _group), geo in zip(wanted, tpl.schedule_rows(page_id)):
        keys = risk.schedule_keys(row_key)
        got = {k: values.get(keys[k], "") for k in keys}
        if not any(got[k] for k in got if k != "inc") and got["inc"] != "Yes":
            continue
        if geo["inc"]:
            canvas.tick(geo["inc"])
        if got.get("desc") and geo["desc"]:
            canvas.text(geo["desc"], got["desc"], size=8)
        if got["basis"]:
            if geo["bn"]:                                  # Broad / Named (or Broad / Robbery) boxes
                for rect, name in zip(geo["bn"], risk.BASIS_CHOICES.get(basis, [])):
                    if got["basis"].strip().lower().startswith(name.lower()):
                        canvas.tick(rect)
            elif geo["basis"]:                             # a written-in basis
                canvas.text(geo["basis"], got["basis"], size=8)
        if got["ded"]:
            canvas.text(geo["ded"], got["ded"], size=8.5)
        if got["limit"]:
            canvas.text(geo["limit"], got["limit"], size=8.5)


def _page_six(canvas, tpl, page_id, values):
    for key, name in (("broker_notes", "BROKER NOTES"),):
        rect = tpl.named(page_id, name)
        if rect and values.get(key):
            canvas.area(rect, values[key])
    rect = tpl.named(page_id, "Date2_af_date")
    text = _shown("app_date", values.get("app_date", ""))
    if rect and text:
        canvas.text(rect, text, size=10)


def _misc_items(canvas, tpl, values):
    cols = {"item": 32, "desc": 74, "limit": 496}
    for column, x in cols.items():
        for row, rect in enumerate(tpl.column("T6", x), start=1):
            if row > 16:
                break
            text = _shown(f"misc{row}_{column}", values.get(f"misc{row}_{column}", ""))
            if text:
                canvas.text(rect, text, size=8.5)


def has_location(values, n):
    """True when an extra location (2 or 3) has any answer."""
    p = f"l{n}_"
    return any(v for k, v in values.items() if k.startswith(p))


def pages_for(values):
    """The template pages of this application, in order."""
    if risk.is_liability_only(values):
        return ["P1", "P2", "T7"]
    pages = ["P1", "P2", "T3", "T4", "T5", "T6"]
    pages += [f"location {n}" for n in (2, 3) if has_location(values, n)]
    return pages


def build(values, template=TEMPLATE):
    """The filled application as a pypdf writer (nothing is written to disk here)."""
    pypdf = _pypdf()
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject
    tpl = Template(template)
    values = dict(values)
    day = records.parse_date(values.get("known_since", ""))        # "known since" is one date; the form has month + year
    if day:
        values["known_month"], values["known_year"] = day.strftime("%B"), str(day.year)
    writer = pypdf.PdfWriter()
    order = pages_for(values)
    extra = 0
    for page_id in order:
        canvas = Canvas()
        if page_id == "P1":
            _page_one(canvas, tpl, values)
        elif page_id == "P2":
            _page_two(canvas, tpl, values)
        elif page_id == "T3":
            _location_page(canvas, tpl, "T3", values, 1)
        elif page_id == "T4":
            _page_four(canvas, tpl, values)
        elif page_id == "T5":
            _schedule(canvas, tpl, "T5", values, {r[3] for r in risk.SCHEDULE})
        elif page_id == "T6":
            _misc_items(canvas, tpl, values)
            _page_six(canvas, tpl, "T6", values)
        elif page_id == "T7":
            _schedule(canvas, tpl, "T7", values, {"Liability"})
            _page_six(canvas, tpl, "T7", values)
        else:                                                       # an extra location page
            extra += 1
            _location_page(canvas, tpl, page_id, values, extra + 1)
        writer.add_page(tpl.page_object(page_id))
        page = writer.pages[-1]
        # the overlay: the page as it was (wrapped in q / Q) + our text, with Helvetica added to its fonts
        if "/Resources" not in page:
            page[NameObject("/Resources")] = DictionaryObject()
        res = page["/Resources"].get_object()
        fonts = res.get("/Font")
        fonts = fonts.get_object() if fonts is not None else DictionaryObject()
        fonts[NameObject("/HvOv")] = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"), NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
        res[NameObject("/Font")] = fonts
        content = page.get_contents()
        old = content.get_data() if content is not None else b""
        from pypdf.generic import ContentStream
        stream = ContentStream(None, writer)
        stream.set_data(b"q\n" + old + b"\nQ\n" + canvas.data())
        page.replace_contents(stream)
        if "/Annots" in page:
            del page["/Annots"]
    root = writer._root_object
    for k in ("/AcroForm", "/Names", "/OpenAction", "/AA"):
        if k in root:
            del root[k]
    return writer


def client_label(folder, values):
    return (values.get("legal_name") or Path(folder).name).strip().upper()


def filename(folder, values):
    safe = re.sub(r'[\\/:*?"<>|]', "", client_label(folder, values)).strip(" .")
    return f"WellCare Commercial Application - {safe}{' (Liability only)' if risk.is_liability_only(values) else ''}.pdf"


def fill(folder, values=None, out=None):
    """Write the filled application into the client folder (or to `out`); returns the path."""
    folder = Path(folder)
    values = risk.load(folder) if values is None else values
    out = Path(out) if out else folder / filename(folder, values)
    writer = build(values)
    tmp = out.with_name(out.name + ".tmp")
    with open(tmp, "wb") as f:
        writer.write(f)
    import os
    os.replace(tmp, out)                       # atomic: the folder's time changes at once, never a half-written file
    return out
