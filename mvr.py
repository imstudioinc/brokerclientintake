"""Ontario MVR (driver abstract) reader: licence details, licence dates and convictions.

MVR PDFs saved from the abstracts site are usually images, so they are read with OCR
(ocr.py). Dates on the MVR are DD/MM/YYYY; "OFFENCE DATE" lines are YYYY/MM/DD.
The conviction date (left column) is the date that counts, not the offence date.
"""
import datetime
import re

from PIL import Image, ImageDraw, ImageFont

import ocr

DATE = r"(\d{2}/\d{2}/\d{4})"
VALID_CLASS = r"(?:A|B|C|D|E|F|G|G1|G2|M|M1|M2)(?:Z|M|M1|M2)?"   # Ontario licence classes

# Conviction categories, from the Intact / Jevco manuals (notes 05 and 08). First match wins.
SERIOUS = ["CARELESS", "DANGEROUS", "IMPAIRED", "OVER 80", "80 MG", "BREATH", "BLOOD", "ALCOHOL", "RACING",
           "RACE", "CONTEST", "CRIMINAL", "NEGLIGENCE", "MANSLAUGHTER", "FAIL TO REMAIN", "LEAVE SCENE",
           "WHILE SUSP", "UNDER SUSP", "SUSPENDED", "DISQUALIF", "DUE CARE", "INTERLOCK", "PROHIBITED",
           "B.A.C", " BAC ", "ABOVE ZERO"]
MAJOR = ["FAIL TO REPORT", "FAIL TO GIVE", "SCHOOL BUS", "SCHOOL ZONE", "PLAYGROUND", "NO INSURANCE",
         "WITHOUT INSURANCE", "UNINSURED", "FALSE", "STUNT", "HAND-HELD", "HAND HELD", "HANDHELD", "WIRELESS",
         "DISPLAY SCREEN", "DISTRACTED", "POLICE", "NOVICE", "G1 ", "G2 ", "M1 ", "M2 ", "UNACCOMPANIED",
         "ACCOMPANYING"]
ALCOHOL = ["IMPAIRED", "OVER 80", "80 MG", "BREATH", "BLOOD", "ALCOHOL", "LIQUOR", "B.A.C", " BAC ",
           "ABOVE ZERO"]
ACTIONS = ["SUSPENSION", "REINSTAT", "CANCELLED", "CANCELED", "DISCHARGE", "WARNING LETTER", "INTERVIEW",
           "LICENCE SUSP", "REMEDIAL", "MEDICAL"]


def _d(text, fmt="%d/%m/%Y"):
    try:
        return datetime.datetime.strptime(text, fmt).date()
    except (TypeError, ValueError):
        return None


def add_year(d):
    try:
        return d.replace(year=d.year + 1)
    except ValueError:   # Feb 29
        return d.replace(year=d.year + 1, day=28)


def classify(description):
    """(category, alcohol) for one conviction - category is minor / major / serious."""
    t = " " + re.sub(r"\s+", " ", description.upper()) + " "
    m = re.search(r"(\d{2,3})\s*KM.{0,8}?\bIN\b.{0,4}?(\d{2,3})\s*KM", t)          # "SPEEDING 110 KM/H IN 50 KM/H"
    over = int(m.group(1)) - int(m.group(2)) if m else None
    m2 = re.search(r"(\d{2,3})\s*KM.{0,6}?OVER", t)                                 # "50 KM/H OVER"
    over = int(m2.group(1)) if m2 and over is None else over
    alcohol = any(k in t for k in ALCOHOL) and "OPEN" not in t   # "open liquor" is not an alcohol conviction
    if over is not None and over >= 60:
        return "serious", alcohol
    if any(k in t for k in SERIOUS) and not ("FAIL TO STOP" in t and "SCENE" not in t and "REMAIN" not in t
                                             and "POLICE" not in t and "SUSP" not in t):
        return "serious", alcohol
    if over is not None and over >= 50:
        return "major", alcohol
    if any(k in t for k in MAJOR):
        return "major", alcohol
    return "minor", alcohol


# ---------- licence class: OCR skips "G***", so read the letters from the image ----------
def _glyphs(im):
    """Boxes of separate marks in a one-line black-on-white image, left to right."""
    w, h = im.size
    px = im.load()
    cols = [any(px[c, r] < 128 for r in range(h)) for c in range(w)]
    out, start = [], None
    for c, ink in enumerate(cols + [False]):
        if ink and start is None:
            start = c
        elif not ink and start is not None:
            rs = [r for r in range(h) if any(px[cc, r] < 128 for cc in range(start, c))]
            out.append((start, min(rs), c, max(rs) + 1))
            start = None
    return out


def _read_mark(line, box):
    """OCR one character. Windows OCR skips a lone letter, so read it at the start of a made-up
    word (the mark followed by "ARAGE"), then keep the first character."""
    font = ImageFont.truetype("cour.ttf", max(10, line.height - 10))
    mark = line.crop((box[0] - 2, 0, box[2] + 2, line.height))
    t = Image.new("L", (mark.width + 16 * 6, line.height), 255)
    t.paste(mark, (0, 0))
    ImageDraw.Draw(t).text((mark.width + 1, 1), "ARAGE", font=font, fill=0)
    t = t.point(lambda v: 0 if v < 160 else 255)
    big = Image.new("L", (t.width * 3 + 300, t.height * 3 + 300), 255)
    big.paste(t.resize((t.width * 3, t.height * 3)), (150, 150))
    found = "".join(w[-1] for w in sorted(ocr.words(big)))
    return found[:1].upper().replace("O", "0") if found else ""


def read_class(img, label_box):
    """Licence class next to the "Class:" label, e.g. G, G1, G2, M. Returns (class, sure)."""
    x, y, w, h = label_box
    line = img.crop((int(x) - 10, int(y - h * 0.6), int(x + w * 6), int(y + h * 1.6)))
    boxes = _glyphs(line)
    if not boxes:
        return "", False
    tallest = max(b[3] - b[1] for b in boxes)
    bottom = max(b[3] for b in boxes)
    marks = [b for b in boxes if not ((b[3] - b[1]) < 0.75 * tallest and b[3] < bottom - 0.2 * tallest)]  # no '*'
    value, prev = [], None
    for b in marks[6:]:                     # after the 6 marks of "Class:"
        if prev and b[0] - prev[2] > 2.5 * (prev[2] - prev[0]):
            break                           # the next field
        value.append(b)
        prev = b
    chars = "".join(_read_mark(line, b) for b in value[:2])
    chars = chars[:1].replace("0", "G") + chars[1:].replace("I", "1").replace("L", "1").replace("Z", "2", 1 if chars[:1] == "G" else 0)
    sure = bool(chars) and all(c.isalnum() for c in chars) and len(chars) == len(value[:2])
    return chars, sure


# ---------- convictions ----------
OCR_DIGITS = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "L": "1", "|": "1"})   # what OCR mistakes for a digit
_LAX_DATE = r"([0-9OIL|]{2})\s*/\s*([0-9OIL|]{2})\s*/\s*([0-9OIL|]{4})"           # DD/MM/YYYY with OCR slips (text is upper-cased)
_LAX_OFFENCE = r"OFFEN[CS]E\s*DATE\W*([0-9OIL|]{4})\s*/\s*([0-9OIL|]{2})\s*/\s*([0-9OIL|]{2})"
_END = ("SEARCH SUCC", "END OF RE", "ABSTRACT FOUND", "NO PUBLIC RECORD")


def _lax(a, b, c, order="dmy"):
    """A date from three OCR'd parts (letters that look like digits are fixed); None when it is not a date."""
    a, b, c = (x.translate(OCR_DIGITS) for x in (a, b, c))
    try:
        return datetime.date(int(c), int(b), int(a)) if order == "dmy" else datetime.date(int(a), int(b), int(c))
    except ValueError:
        return None


def _is_header(u):
    """The "DATE  CONVICTIONS, DISCHARGES AND OTHER ACTIONS" line, however OCR spelled it."""
    if re.match(r"^\W{0,3}" + _LAX_DATE, u):    # "05/03/2026 DISCHARGE OF PROBATION" is an entry, not the heading
        return False
    letters = re.sub(r"[^A-Z]", "", u.translate(str.maketrans("015", "OIS")))   # OCR: C0NVICT1ONS, ACT1ONS
    if "NUMBEROF" in letters:                  # "Number of Convictions: 2" is not the list's heading
        return False
    return "OTHERACTION" in letters or ("CONVICT" in letters and ("DISCHARG" in letters or "ACTION" in letters))


def parse_convictions(lines):
    """([convictions], [other actions]) from the MVR's lines.

    An entry is a date and a description ("22/08/2024 DISOBEY LEGAL SIGN") followed by "OFFENCE DATE 2023/07/27".
    Convictions are told from licence actions (suspensions, discharges...) by that OFFENCE DATE line: an entry with
    one is a conviction even if its description says "SUSPENSION" (DRIVE WHILE UNDER SUSPENSION is a conviction).
    Works without the heading line too (OCR can garble it) and with the offence date on the same line or the next."""
    entries, current, in_list = [], None, False
    lines = [re.sub(r"\s+", " ", l).strip() for l in lines]
    for i, line in enumerate(lines):
        u = line.upper()
        if _is_header(u):
            in_list = True
            continue
        if any(k in u for k in _END):
            in_list, current = False, None      # a photo is read several times: look for the next copy
            continue
        off = re.search(_LAX_OFFENCE, u)
        start = re.match(r"^\W{0,3}" + _LAX_DATE + r"\s*(.*)$", u)
        if start:
            tail = start.group(4)
            has_offence = bool(off) or any(re.search(_LAX_OFFENCE, x.upper()) for x in lines[i + 1:i + 3]
                                           if not re.match(r"^\W{0,3}" + _LAX_DATE, x.upper()))
            d = _lax(*start.group(1, 2, 3))
            if d and (in_list or has_offence):          # (the description may be on the next row: OCR splits rows)
                desc = re.sub(r"OFFEN[CS]E\s*DATE.*$", "", tail).strip(" -,.")
                current = {"date": d, "description": desc, "offence_date": None}
                entries.append(current)
                if off:
                    current["offence_date"] = _lax(*off.group(1, 2, 3), order="ymd")
                    current = None              # complete: what follows is not part of it
                continue
        if off and current:
            current["offence_date"] = _lax(*off.group(1, 2, 3), order="ymd")
            current = None
        elif current and u and not re.match(r"^[-,.\W]+$", u):
            current["description"] = (current["description"] + " " + u).strip()   # a description wrapped onto the next line
    convictions, actions = [], []
    for e in entries:
        if e["offence_date"] or not any(k in e["description"].upper() for k in ACTIONS):
            convictions.append(e)
        else:
            actions.append(e)
    unique = {}
    for c in convictions:                       # the same conviction read from several copies of a photo
        key = (c["date"], c.get("offence_date") or c["description"][:4])   # OCR typos differ between passes
        if key not in unique or len(c["description"]) > len(unique[key]["description"]):
            unique[key] = c
    convictions = sorted(unique.values(), key=lambda c: c["date"] or datetime.date.min)
    for c in convictions:
        c["category"], c["alcohol"] = classify(c["description"])
    return convictions, actions


# ---------- reading ----------
def read(pdf_path):
    """Everything useful on the MVR. Returns dict; "problems" lists anything that could not be read."""
    lines = ocr.text_lines(pdf_path)
    cls, cls_sure, used_ocr, votes = "", False, False, []
    if not any("Licence" in l or "Birth" in l for l in lines):
        used_ocr = True
        lines = []
        for img in ocr.page_images(pdf_path):
            ws = ocr.words(img)
            lines += ocr.rows(ws)
            label = next(((x, y, w, h) for x, y, w, h, t in ws if t.startswith("Class")), None)
            if label:
                found, sure = read_class(img, label)
                if re.fullmatch(VALID_CLASS, found or ""):
                    votes.append(found)
        if votes:     # a photo is read several ways: take the class most readings agree on
            cls = max(set(votes), key=votes.count)
            longer = [v for v in votes if len(v) > len(cls) and v.startswith(cls)]
            if longer:     # a second character (G2) can fail to read in one pass, but is never invented
                cls = max(set(longer), key=longer.count)
            cls_sure = votes.count(cls) >= 2 or (len(votes) == 1 and not ocr.is_image(pdf_path))
    text = "\n".join(lines)
    flat = re.sub(r"\s+", " ", text)
    squeezed = re.sub(r"(?<=[A-Za-z]) (?=[a-z])", "", flat)   # OCR splits words: "Li cence", "Sta tus"

    def grab(label, pattern=DATE):
        m = re.search(label + r"\s*:?\s*" + pattern, squeezed, re.I)
        return m.group(1) if m else ""

    out = {"ocr": used_ocr, "problems": []}
    lic = re.search(r"\b([A-Z])\s?(\d{4})\s?-?\s?(\d{5})\s?-?\s?(\d{5})\b", flat.replace("O", "0").replace("HO", "H0"))
    m = re.search(r"\b([A-Z])(\d{14})\b", flat)
    out["licence"] = (m.group(1) + m.group(2)) if m else (
        (lic.group(1) + lic.group(2) + lic.group(3) + lic.group(4)) if lic else "")
    name = re.search(r"Name\s*:\s*([A-Z][A-Z' ,-]+?)\s*(?:Birth|Gender|,?\s*$)", squeezed)
    out["name"] = re.sub(r"\s*,\s*", ", ", name.group(1)).strip(" ,") if name else ""
    # OCR of photos sometimes drops or garbles "Date": try the exact label, then a looser one
    out["birth"] = _d(grab(r"Birth\s*Date") or grab(r"Bir\w*\s*(?:Da\w{1,3})?"))
    out["expiry"] = _d(grab(r"Expiry\s*Date") or grab(r"Exp\w*\s*(?:Da\w{1,3})?"))
    out["issue"] = _d(grab(r"Issue\s*Date") or grab(r"I\W?s\W?s\w*\s*(?:Da\w{1,3})?")
                      or grab(r"LICENCED\W{0,3}(?:\S{1,8}\s*){0,2}?"))   # the issue date shares the status row
    status = re.search(r"Status\s*:\s*([A-Z]+)", squeezed)
    out["status"] = status.group(1) if status else ""
    pts = re.search(r"Demerit\s*Points\s*:\s*([0-9Oo]{1,2})", squeezed)
    out["demerits"] = int(pts.group(1).replace("O", "0").replace("o", "0")) if pts else None
    if not cls:
        c = re.search(r"Class\s*:\s*([A-Z][A-Z0-9]?)\*", squeezed)
        cls, cls_sure = (c.group(1), True) if c else ("", False)
    out["class"], out["class_sure"] = cls, cls_sure
    m = re.search(r"Postal|([A-Z]\d[A-Z])\s?(\d\s?[A-Z]\s?\d)\b", flat)
    pc = re.findall(r"\b([A-Z]\d[A-Z])\s?(\d)\s?([A-Z])\s?(\d)\b", flat.replace("YB", "Y9"))
    out["postal"] = "".join(pc[0]) if pc else ""

    n = re.search(r"Number\s*of\s*Convict\w*\s*:?\s*([0-9OoIl]{1,2})\b", flat)
    out["conviction_count"] = int(n.group(1).translate(OCR_DIGITS)) if n else None
    convictions, actions = parse_convictions(lines)
    out["convictions"], out["actions"] = convictions, actions
    out["unread_convictions"] = max(0, (out["conviction_count"] or 0) - len(convictions))
    if out["unread_convictions"]:
        out["problems"].append(f"The MVR says {out['conviction_count']} conviction(s) but only {len(convictions)} could "
                               "be read - open the MVR and enter the others by hand.")
    elif out["conviction_count"] is not None and len(convictions) > out["conviction_count"]:
        out["problems"].append(f"The MVR says {out['conviction_count']} conviction(s) but {len(convictions)} were read "
                               "- check the MVR.")
    for key, label in (("birth", "birth date"), ("expiry", "expiry date"), ("issue", "issue date"),
                       ("licence", "licence number")):
        if not out[key]:
            out["problems"].append(f"Could not read the {label} from the MVR.")
    if ocr.is_image(pdf_path):
        from PIL import Image
        with Image.open(pdf_path) as im:
            small = im.width < 1100
        if small:
            out["problems"].insert(0, "The MVR picture is too small to read reliably - the dates and class below "
                                      "may be wrong. Zoom the page in (150%+) before the screenshot, or save the "
                                      "MVR as a PDF.")
    if used_ocr and out["class"] and not out["class_sure"]:
        out["problems"].append(f"Licence class read as {out['class']} - check it on the MVR (correct it if needed).")
    out["dates"] = licence_dates(out)
    return out


def licence_dates(m, cls=None):
    """G1 / G2 / G dates from the MVR.

    When the expiry date has the same day and month as the birth date, the issue date is the G1
    date; G2 is a year later (if the class is G2 or G) and G a year after that (only if the class is G).
    """
    cls = (cls if cls is not None else m.get("class") or "").upper()
    b, e, i = m.get("birth"), m.get("expiry"), m.get("issue")
    if not (b and e and i):
        return {"note": "Licence dates can't be worked out - birth, expiry or issue date missing on the MVR."}
    if (b.month, b.day) != (e.month, e.day):
        return {"note": "Expiry date isn't on the birthday, so the issue date isn't the G1 date - "
                        "get the licence history to confirm G1 / G2 / G dates."}
    out = {"g1": i, "note": ""}
    if cls.startswith("G") and cls != "G1":
        out["g2"] = add_year(i)
        if cls == "G":
            out["g"] = add_year(out["g2"])
    return out
