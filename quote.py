"""Applied Rating Services "Quote Information" PDF reader.

The printout puts each row of values ABOVE its row of labels, and dates are MM/DD/YYYY.
Reads drivers (licence dates, claims, convictions, lapses), vehicles (use, km, price,
coverages) and every carrier's premium with its warning messages.
"""
import datetime
import re

import ocr

MDY = r"(\d{2}/\d{2}/\d{4})"
POSTAL = r"\b([A-Z]\d[A-Z])\s?(\d[A-Z]\d)\b"
SECTIONS = ("Claims", "Convictions", "Lapses", "Suspensions", "Cancellations")


def mdy(text):
    try:
        return datetime.datetime.strptime(text, "%m/%d/%Y").date()
    except (TypeError, ValueError):
        return None


def money(text):
    try:
        return float(text.replace("$", "").replace(",", ""))
    except (AttributeError, ValueError):
        return None


def _blocks(lines, start_pattern):
    """Split lines into blocks that start at lines matching start_pattern."""
    out, cur = [], None
    for line in lines:
        if re.match(start_pattern, line):
            cur = [line]
            out.append(cur)
        elif cur is not None:
            if re.match(r"^(Driver|Vehicle) \d+ of \d+ \|", line) or line.startswith("Disclaimer"):
                cur = None
            else:
                cur.append(line)
    return out


def _value_row(block, label_start):
    """The values row printed just above the label row that starts with label_start."""
    for i, line in enumerate(block):
        if line.startswith(label_start) and i > 0:
            return block[i - 1]
    return ""


def _driver(block):
    name = re.sub(r"^(Mr|Mrs|Ms|Miss|Dr)\.?\s+", "", block[0].split("|", 1)[1].strip())
    d = {"name": name, "claims": [], "convictions": [], "lapses": [], "suspensions": []}
    birth = re.match(r"^" + MDY, block[1] if len(block) > 1 else "")
    d["birth"] = mdy(birth.group(1)) if birth else None
    lic = _value_row(block, "Driver Training")
    m = re.match(r"^(Yes|No)\s+(?:" + MDY + r"\s+)?(Yes|No)\s+([A-Z][A-Z0-9]?)\b\s*(.*)$", lic)
    if m:
        d["training"], d["training_date"], d["class"] = m.group(1) == "Yes", mdy(m.group(2)), m.group(4)
        dates = [mdy(x) for x in re.findall(MDY, m.group(5))]
        # printed as: Date G, Date G2, Date G1 - only the ones the class has
        keys = {"G": ["g", "g2", "g1"], "G2": ["g2", "g1"], "G1": ["g1"]}.get(d["class"], ["g", "g2", "g1"])
        if len(dates) < len(keys):
            keys = keys[len(keys) - len(dates):]
        d.update(zip(keys, dates))
    num = next((re.match(r"^([A-Z]\d{14})\b", l) for l in block if re.match(r"^[A-Z]\d{14}\b", l)), None)
    d["licence"] = num.group(1) if num else ""
    ins = re.search(MDY, _value_row(block, "Date Insured"))
    d["date_insured"] = mdy(ins.group(1)) if ins else None

    section = None
    for line in block:
        if line in SECTIONS:
            section = line
            continue
        if section is None or line.startswith(("Description", "TP/BI", "Disclaimer", "Prepared", "Provided")):
            continue
        if section == "Claims":
            m = re.match(r"^(.*?)\s+" + MDY + r"\s+(Yes|No)\b\s*(.*)$", line)
            if m:
                d["claims"].append({"description": m.group(1), "date": mdy(m.group(2)),
                                    "charged": m.group(3) == "Yes", "vehicle": m.group(4)})
        elif section == "Convictions":
            m = re.match(r"^(.*?)\s+" + MDY, line)
            if m:
                d["convictions"].append({"description": m.group(1), "date": mdy(m.group(2))})
        elif section == "Lapses":
            m = re.match(r"^(.*?)\s+" + MDY + r"\s+(\d+)\s+" + MDY, line)
            if m:
                d["lapses"].append({"description": m.group(1), "from": mdy(m.group(2)),
                                    "months": int(m.group(3)), "to": mdy(m.group(4))})
        elif section == "Suspensions":
            m = re.match(r"^(.*?)\s+" + MDY, line)
            if m:
                d["suspensions"].append({"description": m.group(1), "date": mdy(m.group(2))})
    return d


def _vehicle(block):
    head = re.match(r"^Vehicle \d+ of \d+ \|\s*(.*?)\s+-\s+(\d{4})\s+(.*?)(?:\s+\((\w+)\))?$", block[0])
    v = {"type": head.group(1) if head else "", "year": int(head.group(2)) if head else None,
         "description": (head.group(2) + " " + head.group(3)) if head else block[0]}
    vin = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", _value_row(block, "Vehicle Type"))
    v["vin"] = vin.group(1) if vin else ""
    use = _value_row(block, "Primary Use").split()
    v["use"] = use[0] if use else ""
    nums = [int(x) for x in use[1:] if x.isdigit()]
    v["annual_km"] = nums[0] if nums else None
    garage = re.search(POSTAL, _value_row(block, "Garaging Location").replace(" ", " "))
    g2 = re.search(r"([A-Z]\d[A-Z]\d[A-Z]\d)", _value_row(block, "Garaging Location"))
    v["postal"] = (garage.group(1) + garage.group(2)) if garage else (g2.group(1) if g2 else "")
    p = re.match(r"^(New|Used|Demo)\s+" + MDY + r"\s+(\d+)\s+(\d+)\s+(\d+)\s+(Yes|No)", _value_row(block, "Purchase"))
    if p:
        v.update(condition=p.group(1), purchase_date=mdy(p.group(2)), km_at_purchase=int(p.group(3)),
                 list_price=int(p.group(4)), purchase_price=int(p.group(5)), winter_tires=p.group(6) == "Yes")
    cov, on = {}, False
    for line in block:
        if line == "Coverages":
            on = True
            continue
        if on:
            if line.startswith(("Driver", "Disclaimer", "Prepared", "Provided")):
                break
            m = re.match(r"^(.*?)\s*(?:\(([\d,]+|Standard|[A-Za-z ]+)\))?$", line)
            if m and m.group(1):
                cov[m.group(1).strip()] = m.group(2)
    v["coverages"] = cov
    return v


def _carriers(lines):
    out = []
    for i, line in enumerate(lines[1:], 1):
        m = re.match(r"^(\S+) \| ([A-Za-z ]+) \| Effective Date: " + MDY, line)
        if not m:
            continue
        c = {"name": lines[i - 1].strip(), "reference": m.group(1), "kind": m.group(2), "messages": [],
             "discounts": [], "premium": None}
        out.append(c)
        c["_start"] = i
    for n, c in enumerate(out):
        end = out[n + 1]["_start"] - 1 if n + 1 < len(out) else len(lines)
        block = lines[c.pop("_start") + 1:end]
        for line in block:
            m = re.match(r"^Total Premium \$([\d,]+\.\d\d)", line)
            if m and c["premium"] is None:
                c["premium"] = money(m.group(1))
        target = None
        for line in block:
            if line.startswith("■"):
                c["messages"].append(line.lstrip("■ ").strip())
                target = c["messages"]
            elif line.startswith("●"):
                c["discounts"].append(line.lstrip("● ").strip(" -"))
                target = c["discounts"]
            elif target is not None and line[:1].islower():
                target[-1] += " " + line.strip()                   # wrapped message line
            elif target is c["discounts"] and line.strip() in ("Prn", "Occ"):
                target[-1] += " " + line.strip()
            else:
                target = None
    return out


def read(pdf_path):
    lines = [l.strip() for l in ocr.text_lines(pdf_path)]
    q = {"drivers": [_driver(b) for b in _blocks(lines, r"^Driver \d+ of \d+ \|")],
         "vehicles": [_vehicle(b) for b in _blocks(lines, r"^Vehicle \d+ of \d+ \|")],
         "carriers": _carriers(lines)}
    eff = re.search(r"Effective Date:\s*" + MDY, "\n".join(lines))
    q["effective"] = mdy(eff.group(1)) if eff else None
    first_page = "\n".join(lines[:15])
    codes = ["".join(m) for m in re.findall(POSTAL, first_page)]
    q["postal"] = codes[-1] if len(codes) > 1 else ""   # first one is the brokerage's
    q["problems"] = [] if q["drivers"] else ["No drivers found - is this an Applied Rating 'Quote Information' PDF?"]
    return q
