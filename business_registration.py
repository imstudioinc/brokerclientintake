"""Reads the Ontario "Registration Information of a Business Name" PDF (Ministry of Public and Business Service Delivery)
and turns it into Commercial details answers: legal and operating name, BIN / OCN, address, NAICS code + activity,
and the person who authorised the registration (first contact).

Every value is printed on the line under its label ("Business Name:" then the name), so the reader walks the text lines.
Only EMPTY answers are filled (`prefill`), never overwritten. No client file is kept in the repo.
"""
import fnmatch
import os
import re
from pathlib import Path

PATTERNS = ["*registration information*", "*business name registration*", "*business registration*"]

PROVINCES = {"ontario": "ON", "alberta": "AB", "british columbia": "BC", "manitoba": "MB", "new brunswick": "NB",
             "newfoundland and labrador": "NL", "nova scotia": "NS", "northwest territories": "NT", "nunavut": "NU",
             "prince edward island": "PE", "quebec": "QC", "québec": "QC", "saskatchewan": "SK", "yukon": "YT"}

LABELS = {"business name": "business_name", "business identification number (bin)": "bin",
          "address of principal place of business": "address", "activity (naics code)": "activity",
          "effective date of filing": "effective", "original registration date": "original",
          "expiry date": "expiry", "registrant information": "registrant",
          "person authorizing registration": "person", "type of filing": "filing"}


def find(folder):
    """The newest registration PDF in the client folder (one directory listing), or None."""
    try:
        with os.scandir(folder) as entries:
            files = [(e.name, e.stat().st_mtime) for e in entries
                     if e.is_file() and e.name.lower().endswith(".pdf")]
    except OSError:
        return None
    hits = [(m, n) for n, m in files if any(fnmatch.fnmatchcase(n.lower(), p) for p in PATTERNS)]
    return Path(folder) / max(hits)[1] if hits else None


def _lines(path):
    import ocr
    lines = ocr.text_lines(str(path))
    if not lines:                                       # a scanned copy: Windows OCR
        try:
            lines = [" ".join(w[4] for w in row) for row in ocr.rows(
                [w for img in ocr.page_images(str(path)) for w in ocr.words(img)])]
        except Exception:
            lines = []
    return [l.strip() for l in lines if l.strip()]


def _sections(lines):
    """{label key: [value lines]} - a label is a line that ends with ':' and is one of the known headings."""
    out, current = {}, None
    for line in lines:
        key = LABELS.get(line.rstrip(":").strip().lower()) if line.endswith(":") else None
        if key:
            current = key
            out.setdefault(key, [])
        elif current and not line.startswith(("The Registration Information", "Certified a true copy", "Director/Registrar")) \
                and not line.startswith("Effective Date of Filing:"):
            out[current].append(line)
    return out


def _split_address(text):
    """'255 Lancing Drive, Unit 5, Hamilton, Ontario, L8W3W8, Canada' -> street, city, province, postal, country."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    out = {}
    if parts and parts[-1].lower() in ("canada", "can"):
        out["country"] = "Canada"
        parts.pop()
    if parts and re.fullmatch(r"[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d", parts[-1]):
        raw = parts.pop().replace(" ", "").upper()
        out["postal"] = f"{raw[:3]} {raw[3:]}"
    if parts and (parts[-1].lower() in PROVINCES or parts[-1].upper() in PROVINCES.values()):
        p = parts.pop()
        out["province"] = PROVINCES.get(p.lower(), p.upper())
    if len(parts) >= 2:
        out["city"] = parts.pop()
    if parts:
        out["address"] = ", ".join(parts)
    return out


def read(path):
    """{field: value} found in the registration PDF; {} when it is not one."""
    s = _sections(_lines(path))
    if not s.get("business_name") and not s.get("activity"):
        return {}
    facts = {}
    first = lambda k: s[k][0] if s.get(k) else ""
    if first("business_name"):
        facts["trade_name"] = first("business_name")
    if re.fullmatch(r"\d{6,}", first("bin")):
        facts["bin"] = first("bin")
    m = re.match(r"(\d{4,6})\s*[-–]\s*(.+)", first("activity"))
    if m:
        facts["naics"], facts["naics_title"] = m.group(1), m.group(2).strip()
    facts.update(_split_address(first("address")))
    reg = " ".join(s.get("registrant", []))
    m = re.search(r"Name:\s*(.+?)(?:,\s*OCN:\s*(\d+))?\s*$", reg)
    if m:
        facts["legal_name"] = m.group(1).strip().rstrip(",")
        if m.group(2):
            facts["ocn"] = m.group(2)
    filing = first("filing").lower()
    if "corporation" in filing or facts.get("ocn"):
        facts["entity"] = "Corporation"
    elif "partnership" in filing:
        facts["entity"] = "Partnership"
    elif "proprietor" in filing:
        facts["entity"] = "Sole proprietor"
    person = s.get("person", [])
    if person:
        name = person[0]
        first_name, _, last = name.title().rpartition(" ")
        facts["person_first"], facts["person_last"] = (first_name, last) if first_name else ("", last)
        if len(person) > 1 and not re.search(r"\d|,", person[-1]) and len(person) > 2:
            facts["person_position"] = person[-1]
    for key in ("effective", "original", "expiry"):
        if first(key):
            facts[f"reg_{key}"] = first(key)
    return facts


def prefill(values, facts):
    """Copy the facts into EMPTY answers only. Returns (new values, list of field labels that were filled)."""
    values = dict(values)
    filled = []

    def put(key, text, label):
        if text and not str(values.get(key, "")).strip():
            values[key] = text
            filled.append(label)
    put("legal_name", facts.get("legal_name"), "registered name")
    put("trade_name", facts.get("trade_name"), "operating name")
    for key, label in (("address", "address"), ("city", "city"), ("province", "province"), ("postal", "postal code"),
                       ("country", "country"), ("bin", "BIN"), ("ocn", "corporation number"),
                       ("naics", "NAICS code"), ("naics_title", "business activity"), ("entity", "client type")):
        put(key, facts.get(key), label)
    put("description", facts.get("naics_title"), "description of operations")
    if not any(values.get(f"contact1_{k}") for k in ("first", "last")) and facts.get("person_last"):
        put("contact1_first", facts.get("person_first"), "contact 1")
        put("contact1_last", facts.get("person_last"), "contact 1")
        put("contact1_position", facts.get("person_position"), "contact 1")
    return values, list(dict.fromkeys(filled))
