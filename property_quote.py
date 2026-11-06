"""Applied Rating Services (ARS) property quote - Home / Tenant / Commercial "Quote Information" PDF.

Carriers, premiums and the carrier messages come from quote.read (same layout as the auto quote).
This adds the dwelling facts the broker typed into PropertyRater, so the Property details form can
start filled in. Like the auto quote, each row of values is printed ABOVE its row of labels.
Only free-form answers (year, number, money, date, text) are returned, never dropdown choices.
"""
import re

import ocr
import quote

SQFT = r"([\d,]+)\s*sq\.?\s*ft"
MONEY = r"\$[\d,]+"


def _row(lines, label_start):
    """The values line printed just above the labels line that starts with label_start."""
    for i, line in enumerate(lines):
        if i and line.startswith(label_start):
            return lines[i - 1]
    return ""


def _after(lines, header):
    return lines[lines.index(header) + 1:] if header in lines else []


def _dwelling(lines):
    out = {}
    part = _after(lines, "Dwelling Information")
    if not part:
        return out
    m = re.match(r"^(?:Yes|No)\s+(?:Yes|No)\s+(\d{4})\s+" + quote.MDY + r"\b", _row(part, "Tenant Occupied"))
    if m:
        out["year_built"] = m.group(1)
        d = quote.mdy(m.group(2))
        out["occupancy_date"] = d.strftime("%Y-%m-%d") if d else ""
    m = re.match(r"^\S+\s+(\d+)\s+", _row(part, "Construction"))
    if m:
        out["bedrooms"] = m.group(1)
    for key, start in (("roof_year", "Year of Roof"), ("plumbing_year", "Year of Plumbing")):
        m = re.match(r"^(\d{4})\b", _row(part, start))
        if m:
            out[key] = m.group(1)
    row = _row(part, "Year of Electrical")
    m = re.match(r"^(\d{4})\b.*?\s(\d+)\s+" + SQFT, row)
    if m:
        out["electrical_year"] = m.group(1)
        out["sq_ft"] = m.group(3).replace(",", "")
    elif (m := re.search(SQFT, row)):
        out["sq_ft"] = m.group(1).replace(",", "")
    m = re.search(r"(\d+)\s+(\d+)\s*$", _row(part, "Basement Area"))
    if m:
        out["bathrooms"], out["half_baths"] = m.group(1), m.group(2)
    m = re.match(r"^(\d{4})\b", _row(part, "Water Heater"))
    if m:
        out["water_heater_year"] = m.group(1)
    m = re.match(r"^(?:Yes|No)\s+(\d{4})\b", _row(part, "Approved Year"))
    if m:
        out["heating_year"] = m.group(1)
    return out


def _contents(lines):
    out = {}
    part = _after(lines, "Coverages")[:12]
    amounts = [x for l in part for x in re.findall(MONEY, l)]
    row = _row(part, "Coverage Type")
    m = re.search(MONEY + r"\s+(" + MONEY + ")", row)
    if m:
        out["contents_value"] = m.group(1).replace("$", "").replace(",", "")
    elif amounts:
        out["contents_value"] = amounts[-1].replace("$", "").replace(",", "")
    return out


def is_property(lines):
    return any(l.startswith("Dwelling Information") for l in lines)


def read(pdf_path):
    """{"property": bool, "answers": {form key: value}, "address", "postal", + quote.read's keys}."""
    lines = [l.strip() for l in ocr.text_lines(pdf_path)]
    q = quote.read(pdf_path)
    q["property"] = is_property(lines)
    if q["property"]:
        q["problems"] = []
        answers = {**_dwelling(lines), **_contents(lines)}
        for i, line in enumerate(lines):
            m = re.match(r"^(\d[^|]*?),\s*([A-Z ]+),\s*(?:ON,?\s*)?([A-Z]\d[A-Z]\s?\d[A-Z]\d)$", line)
            if m and "address" not in answers and i > 20:
                answers["address"] = m.group(1).title()
                answers["postal"] = m.group(3).replace(" ", "")
        if "address" not in answers:
            for line in lines:
                m = re.search(r"\d+ of \d+ \|.* - (\d.+?), [A-Z ]+, ([A-Z]\d[A-Z]\s?\d[A-Z]\d)$", line)
                if m:
                    answers["address"], answers["postal"] = m.group(1).title(), m.group(2).replace(" ", "")
                    break
        q["answers"] = answers
    else:
        q["answers"] = {}
    return q


def prefill(values, answers):
    """values + the quote's answers for questions that are still empty (never overwrites)."""
    out = dict(values)
    for k, v in answers.items():
        if v and not str(out.get(k, "")).strip():
            out[k] = v
    return out
