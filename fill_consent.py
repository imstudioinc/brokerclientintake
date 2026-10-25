"""Copy the Client Consent form into a client folder and fill it.

Usage:
    python fill_consent.py "<client folder>" [--dln T1234-12345-12345] [--template form.pdf]

The client (folder name) is always the first person; other drivers come from DASH reports
in the folder. No DASH report is needed: the form is filled from the client's name alone.
The built-in form is WellCare's Personal Information Client Consent Form (made from a filled
copy by tools/make_consent_template.py); it is filled and flattened, so it looks the same in
every viewer. A custom template with "Driver License n" fields still gets licence numbers.
"""
import argparse
import datetime
import difflib
import re
import sys
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter

DEFAULT_TEMPLATE = Path(__file__).parent / "templates" / "WellCare Consent Form.pdf"


def format_dln(dln):
    """Ontario licence: 1 letter + 14 digits -> A1234-12345-12345."""
    raw = re.sub(r"[^A-Za-z0-9]", "", dln or "").upper()
    if re.fullmatch(r"[A-Z]\d{14}", raw):
        return f"{raw[:5]}-{raw[5:10]}-{raw[10:]}"
    return (dln or "").strip()


def is_valid_dln(dln):
    """True for an Ontario licence #: 1 letter + 14 digits (dashes/spaces ignored)."""
    return bool(re.fullmatch(r"[A-Z]\d{14}", re.sub(r"[^A-Za-z0-9]", "", dln or "").upper()))


def read_dash(pdf_path):
    """Return (name, dln) from the header of a DASH driver report."""
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    name = re.search(r"DRIVER REPORT\s*\n(.+?)\s+Report Date:", text)
    dln = re.search(r"DLN:\s*([A-Z0-9-]+)", text)
    if not name:
        return None
    return name.group(1).strip().upper(), format_dln(dln.group(1) if dln else "")


def read_consent(pdf_path):
    """Return (name, dln) of the first driver on a filled consent form, or None."""
    try:
        reader = PdfReader(pdf_path)
        fields = reader.get_fields() or {}
    except Exception:
        return None
    value = lambda k: str((fields.get(k) or {}).get("/V") or "").strip()  # noqa: E731
    name, dln = value("Name 1") or value("Client(s) Name"), value("Driver License 1")
    if not name:   # flattened WellCare form: "AND: JOHN SMITH (the "Client")"
        try:
            with pdfplumber.open(pdf_path) as pdf:     # reads by position: name sits between AND: and (the
                m = re.search(r"AND:\s*(.+?)\s*\(the", pdf.pages[0].extract_text() or "")
            name = m.group(1).strip() if m else ""
        except Exception:
            name = ""
    return (name.upper(), format_dln(dln)) if name or dln else None


# where name rows 2-4 sit on the built-in form (see tools/make_consent_template.py): underline
# position from the top of the page, and the name / signature / date columns. Row 1's lines are
# printed on the form; the others are drawn only when used, at the same weight (0.75 pt as printed).
EXTRA_ROWS = {2: 568.6, 3: 594.6, 4: 620.6}
ROW_COLUMNS = [(44.0, 233.1), (243.1, 453.2), (463.2, 558.0)]


def _same_person(a, b, dln_a="", dln_b=""):
    """Same driver: same licence #, or names that match allowing a small spelling difference
    (the client's name may have been corrected after the DASH report was pulled)."""
    if dln_a and dln_b:
        return _raw(dln_a) == _raw(dln_b)
    ta, tb = a.upper().replace(",", " ").split(), b.upper().replace(",", " ").split()
    if not ta or not tb:
        return False
    if set(ta) <= set(tb) or set(tb) <= set(ta):
        return True
    return difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio() >= 0.85


def _raw(dln):
    return re.sub(r"[^A-Z0-9]", "", (dln or "").upper())


def fill(client_folder, dln=None, template=None):
    folder = Path(client_folder)
    # Empty or missing custom template -> the built-in form
    template = Path(template) if template and Path(template).exists() else DEFAULT_TEMPLATE
    if not template.exists():
        raise FileNotFoundError(f"Consent template not found: {template}")
    client_name = folder.name.upper()
    if not dln:    # saved when the client was created
        try:
            import mvr_email
            dln = mvr_email.load_client(folder).get("dln", "")
        except Exception:
            dln = ""

    reader = PdfReader(template)
    slots = sum(1 for k in (reader.get_fields() or {}) if re.fullmatch(r"Name \d+", k)) or 3
    dash_files = sorted(folder.glob("DASH Report*.pdf"), key=lambda p: p.stat().st_mtime)
    dash = [d for d in (read_dash(p) for p in dash_files) if d]
    # the client first (with the licence # from their DASH if there is one), then the other drivers
    own = next((d for d in dash if _same_person(d[0], client_name, d[1], dln)), None)
    drivers = [(client_name, own[1] if own else format_dln(dln))]
    for d in dash:
        if d is own:
            continue
        if not any(_same_person(d[0], x[0], d[1], x[1]) for x in drivers):
            last, _, first = d[0].partition(",")      # DASH writes "LAST, FIRST"
            drivers.append(((first.strip() + " " + last.strip()).strip() if first else d[0], d[1]))
    drivers = drivers[:slots]

    values = {
        "Client(s) Name": client_name,
        "Date1_af_date": datetime.date.today().strftime("%B %d, %Y").replace(" 0", " "),
    }
    fields = reader.get_fields() or {}
    for i, (name, licence) in enumerate(drivers, start=1):
        values[f"Name {i}"] = name
        if f"Driver License {i}" in fields:
            values[f"Driver License {i}"] = licence

    writer = PdfWriter(clone_from=reader)
    if template == DEFAULT_TEMPLATE:
        # draw the values into the page and drop the fields: looks the same in every viewer
        writer.update_page_form_field_values(writer.pages[0], values, auto_regenerate=False, flatten=True)
        lines = "".join(f"{x0} {792 - top} m {x1} {792 - top} l S\n"
                        for i, top in EXTRA_ROWS.items() if i <= len(drivers) for x0, x1 in ROW_COLUMNS)
        if lines:   # underline only the extra rows that have a name
            content = writer.pages[0].get_contents()
            content.set_data(content.get_data() + f"\nq 0 0 0 RG 0.75 w\n{lines}Q\n".encode())
            writer.pages[0].replace_contents(content)
        for page in writer.pages:
            if "/Annots" in page:
                del page["/Annots"]
        if "/AcroForm" in writer._root_object:
            del writer._root_object["/AcroForm"]
    else:
        writer.update_page_form_field_values(writer.pages[0], values, auto_regenerate=False)
        writer.set_need_appearances_writer(True)

    out = folder / f"Client Consent - {client_name}.pdf"
    with open(out, "wb") as f:
        writer.write(f)
    return out, drivers


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("client_folder")
    ap.add_argument("--dln", default="")
    ap.add_argument("--template", default=None)
    args = ap.parse_args()
    try:
        out, drivers = fill(args.client_folder, args.dln, args.template)
    except FileNotFoundError as e:
        sys.exit(str(e))
    print(out)
    for name, licence in drivers:
        print(f"  {name}  {licence}")
