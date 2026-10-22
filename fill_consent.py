"""Copy the Client Consent form into a client folder and fill it.

Usage:
    python fill_consent.py "<client folder>" [--dln T1234-12345-12345] [--template form.pdf]

Drivers come from DASH reports already in the client folder (up to 3).
If there are none, the client folder name and --dln are used instead.
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter

DEFAULT_TEMPLATE = Path(__file__).parent / "templates" / "New Client Consent Form.pdf"


def format_dln(dln):
    """Ontario licence: 1 letter + 14 digits -> A1234-12345-12345."""
    raw = re.sub(r"[^A-Za-z0-9]", "", dln or "").upper()
    if re.fullmatch(r"[A-Z]\d{14}", raw):
        return f"{raw[:5]}-{raw[5:10]}-{raw[10:]}"
    return (dln or "").strip()


def read_dash(pdf_path):
    """Return (name, dln) from the header of a DASH driver report."""
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    name = re.search(r"DRIVER REPORT\s*\n(.+?)\s+Report Date:", text)
    dln = re.search(r"DLN:\s*([A-Z0-9-]+)", text)
    if not name:
        return None
    return name.group(1).strip(), format_dln(dln.group(1) if dln else "")


def fill(client_folder, dln=None, template=None):
    folder = Path(client_folder)
    template = Path(template or DEFAULT_TEMPLATE)
    if not template.exists():
        raise FileNotFoundError(f"Consent template not found: {template}")
    client_name = folder.name

    dash_files = sorted(folder.glob("DASH Report*.pdf"), key=lambda p: p.stat().st_mtime)
    drivers = [d for d in (read_dash(p) for p in dash_files) if d][:3]
    if not drivers:
        drivers = [(client_name, format_dln(dln))]

    values = {
        "Client(s) Name": client_name,
        "Date1_af_date": datetime.date.today().strftime("%B %d, %Y").replace(" 0", " "),
    }
    for i, (name, licence) in enumerate(drivers, start=1):
        values[f"Name {i}"] = name
        values[f"Driver License {i}"] = licence

    writer = PdfWriter(clone_from=PdfReader(template))
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
