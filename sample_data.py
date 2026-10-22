"""Sample clients for trying the app: Settings > Try with sample clients.

Creates a separate folder (Documents\\Client Intake sample\\Clients) - real client folders
are never touched. Dates are relative to today, so the Tracker always shows overdue items,
items due this week, upcoming renewals and quotes waiting.
"""
import datetime
import json
import os
import shutil
from pathlib import Path

import records

SAMPLE_ROOT = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents" / "Client Intake sample" / "Clients"


def _d(days):
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def _policy(line, status, insurer, number, start_days_ago, premium, plan="Monthly", method="Pre-authorized debit",
            coverage=""):
    eff = datetime.date.today() - datetime.timedelta(days=start_days_ago)
    exp = eff.replace(year=eff.year + 1) if not (eff.month == 2 and eff.day == 29) else eff + datetime.timedelta(days=365)
    p = {"line": line, "status": status, "insurer": insurer, "policy_number": number,
         "effective": eff.isoformat(), "expiry": exp.isoformat(), "premium": f"{premium:.2f}", "plan": plan,
         "method": method if status != "Quoted" else "", "coverage": coverage}
    if plan == "Monthly":
        p["monthly"] = f"{premium / 12:.2f}"
        p["payment_day"] = "1"
    if status in ("Bound", "Active", "Renewed"):
        p["bound_date"] = eff.isoformat()
    return p


CLIENTS = [
    ("Auto", "ERSIN TORUN", "T6680-23608-40904", "647-204-7270", [
        ("policies", _policy("Auto", "Active", "Intact Insurance", "AU4410293", 335, 2860,
                             coverage="$2M liability, collision $1,000 ded., comprehensive $500 ded., OPCF 20, 27, 44R")),
        ("vehicles", {"year": "2021", "make": "Toyota", "model": "RAV4 XLE", "vin": "2T3P1RFV5MC123456",
                      "principal_driver": "ERSIN TORUN", "use": "Commute", "km_year": "18000",
                      "lienholder": "Toyota Financial Services, Markham ON", "winter_tires": True}),
        ("notes", {"date": _d(-20), "method": "Phone", "text": "Reviewed optional accident benefits. Client took "
                   "income replacement $600/week, declined caregiver and housekeeping. Decline confirmed by email."}),
        ("reminders", {"due": _d(-2), "text": "Send updated pink card for winter tire endorsement"}),
    ]),
    ("Auto", "PRIYA SHARMA", "S4471-82290-15503", "416-555-0198", [
        ("policies", _policy("Auto", "Quoted", "Aviva", "", 0, 3420)),
        ("vehicles", {"year": "2024", "make": "Honda", "model": "Civic", "vin": "2HGFE2F59RH512345",
                      "principal_driver": "PRIYA SHARMA", "use": "Pleasure", "lienholder": "Honda Financial"}),
        ("notes", {"date": _d(-9), "method": "Email", "text": "Sent Aviva and Intact quotes. Waiting for client to choose."}),
    ]),
    ("Auto", "DANIEL OKAFOR", "O2210-55410-90812", "905-555-0144", [
        ("policies", _policy("Auto", "Bound", "Economical", "EC-77120", 3, 4150,
                             coverage="$1M liability, all perils $1,000 ded.")),
        ("reminders", {"due": _d(4), "text": "Collect void cheque and bill of sale"}),
        ("reminders", {"due": _d(9), "text": "Check winter tire photo received"}),
    ]),
    ("Home", "MARY BROWN", "B6620-11220-33015", "289-555-0110", [
        ("policies", _policy("Home", "Active", "Aviva", "HO998877", 320, 1850, plan="Annual", method="Credit card",
                             coverage="Comprehensive form, $2M liability, sewer backup $25k, overland water")),
        ("properties", {"address": "12 Main St, Waterdown ON", "kind": "House", "year_built": "1998",
                        "sq_ft": "1900", "construction": "Brick", "roof_year": "2019", "heating": "Gas furnace 2015",
                        "protection": "Monitored alarm, sump pump", "mortgagee": "TD Bank, Toronto ON, loan #4455-21"}),
        ("notes", {"date": _d(-40), "method": "In person", "text": "Recommended overland water; client accepted."}),
    ]),
    ("Home", "JAMES & LINDA CHEN", "C3310-20018-77420", "416-555-0177", [
        ("policies", _policy("Home", "Active", "Wawanesa", "WH-551203", 352, 2240,
                             coverage="Comprehensive, $2M liability, guaranteed replacement")),
        ("policies", _policy("Auto", "Active", "Wawanesa", "WA-551204", 352, 3980,
                             coverage="2 vehicles, $2M liability, multi-line discount")),
        ("vehicles", {"year": "2022", "make": "Hyundai", "model": "Tucson", "principal_driver": "LINDA CHEN"}),
        ("vehicles", {"year": "2019", "make": "Ford", "model": "F-150", "principal_driver": "JAMES CHEN", "use": "Commute"}),
        ("properties", {"address": "88 Maple Cres, Burlington ON", "kind": "House", "year_built": "2006",
                        "mortgagee": "RBC, Toronto ON"}),
    ]),
    ("Tenant", "ALI VELI", "V1120-33450-66019", "647-555-0133", [
        ("policies", _policy("Tenant", "Active", "Square One", "SQ-209981", 120, 264,
                             coverage="Contents $30k, $1M liability, sewer backup")),
        ("properties", {"address": "301-25 King St W, Hamilton ON", "kind": "Tenant / rental unit"}),
    ]),
    ("Tenant", "SOFIA ROSSI", "R5530-71200-28810", "905-555-0161", [
        ("policies", _policy("Tenant", "Quoted", "Square One", "", 0, 228, plan="Annual")),
        ("reminders", {"due": _d(1), "text": "Client moving in on the 1st - confirm start date"}),
    ]),
    ("Commercial", "ACME ROOFING INC", "A9910-42200-10101", "905-555-0102", [
        ("policies", _policy("Commercial", "Active", "Northbridge", "NB-CGL-30021", 340, 6200, plan="Annual",
                             method="Cheque", coverage="CGL $5M, tools floater $25k")),
        ("businesses", {"name": "ACME Roofing Inc", "operations": "Residential roofing and eavestroughs",
                        "address": "40 Industrial Rd, Hamilton ON", "revenue": "850000", "employees": "6", "years": "11"}),
        ("reminders", {"due": _d(12), "text": "Ask for updated payroll and revenue for renewal"}),
    ]),
    ("Commercial", "BRIGHT SMILES DENTAL", "", "416-555-0150", [
        ("policies", _policy("Commercial", "Cancelled", "Intact Insurance", "IC-88231", 200, 3100, plan="Annual")),
        ("businesses", {"name": "Bright Smiles Dental", "operations": "Dental clinic", "employees": "9"}),
        ("notes", {"date": _d(-30), "method": "Email", "text": "Client moved to another broker. Cancellation confirmed in writing."}),
    ]),
]


def create(root=SAMPLE_ROOT):
    """(Re)build the sample folder. Returns its path."""
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    for client_type, name, dln, phone, items in CLIENTS:
        folder = root / client_type / name
        folder.mkdir(parents=True)
        (folder / "client.json").write_text(json.dumps({
            "name": name, "dln": dln, "phone": phone, "type": client_type,
            "email": name.split()[0].lower() + "@example.com"}, indent=2), encoding="utf-8")
        for kind, item in items:
            records.save_item(folder, kind, item)
    return root
