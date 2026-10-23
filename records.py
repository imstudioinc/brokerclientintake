"""Client records: policies, risk details, activity notes and reminders.

Stored per client in <client folder>\\tracking.json, so everyone who can open the
(shared) Clients folder sees the same records. Every save re-reads the file and
changes only the one record being edited, then replaces the file in one step, so two
people editing different records of the same client do not overwrite each other.
"""
import datetime
import getpass
import json
import os
import uuid
from pathlib import Path

FILE = "tracking.json"

# ---------- schema: (key, label, kind, options) ----------
# kinds: text, date (YYYY-MM-DD), money, choice, bool, long
LINES = ["Auto", "Home", "Condo", "Tenant", "Commercial", "Other"]
STATUSES = ["Quoted", "Bound", "Active", "Renewed", "Cancelled", "Lapsed", "Lost"]
PLANS = ["Annual", "Monthly"]
METHODS = ["Pre-authorized debit", "Credit card", "Cheque", "Insurer direct bill", "Other"]

KINDS = {
    "policies": {
        "title": "Policies", "singular": "policy",
        "fields": [
            ("line", "Line", "choice", LINES),
            ("status", "Status", "choice", STATUSES),
            ("insurer", "Insurance company", "text", None),
            ("policy_number", "Policy number", "text", None),
            ("effective", "Effective date", "date", None),
            ("expiry", "Expiry / renewal date", "date", None),
            ("premium", "Annual premium ($)", "money", None),
            ("plan", "Payment plan", "choice", PLANS),
            ("monthly", "Monthly payment ($)", "money", None),
            ("method", "Payment method", "choice", METHODS),
            ("payment_day", "Payment day of month", "text", None),
            ("bound_date", "Date bound", "date", None),
            ("coverage", "Coverage notes (limits, deductibles, endorsements)", "long", None),
        ],
        "columns": ["line", "status", "insurer", "policy_number", "effective", "expiry", "premium", "plan"],
    },
    "vehicles": {
        "title": "Vehicles", "singular": "vehicle",
        "fields": [
            ("year", "Year", "text", None),
            ("make", "Make", "text", None),
            ("model", "Model", "text", None),
            ("vin", "VIN", "text", None),
            ("principal_driver", "Principal driver", "text", None),
            ("use", "Use", "choice", ["Pleasure", "Commute", "Business", "Commercial"]),
            ("km_year", "Km per year", "text", None),
            ("lienholder", "Financed / leased by (lender name & address)", "text", None),
            ("winter_tires", "Winter tires", "bool", None),
            ("notes", "Notes", "long", None),
        ],
        "columns": ["year", "make", "model", "vin", "principal_driver", "lienholder"],
    },
    "properties": {
        "title": "Property", "singular": "property",
        "fields": [
            ("address", "Address", "text", None),
            ("kind", "Type", "choice", ["House", "Condo", "Tenant / rental unit", "Rented dwelling", "Seasonal"]),
            ("year_built", "Year built", "text", None),
            ("sq_ft", "Living area (sq ft)", "text", None),
            ("construction", "Construction / exterior", "text", None),
            ("roof_year", "Roof updated (year)", "text", None),
            ("heating", "Heating (type, year)", "text", None),
            ("electrical_plumbing", "Electrical / plumbing updates", "text", None),
            ("protection", "Alarm, sump pump, backwater valve", "text", None),
            ("mortgagee", "Mortgagee (lender, address, loan #)", "text", None),
            ("notes", "Notes", "long", None),
        ],
        "columns": ["address", "kind", "year_built", "mortgagee"],
    },
    "businesses": {
        "title": "Business", "singular": "business",
        "fields": [
            ("name", "Business name", "text", None),
            ("operations", "Operations (what they do)", "text", None),
            ("address", "Location", "text", None),
            ("revenue", "Annual revenue ($)", "money", None),
            ("employees", "Employees", "text", None),
            ("years", "Years in business", "text", None),
            ("notes", "Notes", "long", None),
        ],
        "columns": ["name", "operations", "address", "revenue"],
    },
    "notes": {
        "title": "Activity notes", "singular": "note",
        "fields": [
            ("date", "Date", "date", None),
            ("method", "How", "choice", ["Phone", "Email", "In person", "Text", "Other"]),
            ("text", "Note (asked, offered, recommended, chosen, declined, next steps)", "long", None),
        ],
        "columns": ["date", "method", "text", "by"],
    },
    "reminders": {
        "title": "Reminders", "singular": "reminder",
        "fields": [
            ("due", "Due date", "date", None),
            ("text", "What to do", "text", None),
            ("done", "Done", "bool", None),
        ],
        "columns": ["due", "text", "done", "by"],
    },
}


def who():
    """Name shown on records: the signature name if set, else the Windows user."""
    try:
        import config
        name = config.load().get("sig_name")
    except Exception:
        name = ""
    return name or getpass.getuser()


def today():
    return datetime.date.today().isoformat()


def parse_date(text):
    """Accept 2026-10-22, 22/10/2026, Oct 22 2026, October 22, 2026 -> date or None."""
    text = (text or "").strip().replace(",", "")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def money(value):
    try:
        return float(str(value).replace("$", "").replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


# ---------- file access ----------
def load(folder):
    f = Path(folder) / FILE
    try:
        data = json.loads(f.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        data = {}
    for kind in KINDS:
        data.setdefault(kind, [])
    return data


def _write(folder, data):
    f = Path(folder) / FILE
    tmp = f.with_name(f".{FILE}.{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)  # one step: readers never see a half-written file


def save_item(folder, kind, item):
    """Add or update one record (matched by id). Returns the saved item."""
    data = load(folder)  # re-read: someone else may have saved meanwhile
    item = dict(item)
    now = datetime.datetime.now().isoformat(timespec="minutes")
    if not item.get("id"):
        item.update(id=uuid.uuid4().hex[:12], by=who(), created=now)
        data[kind].append(item)
    else:
        item.update(edited_by=who(), edited=now)
        for i, old in enumerate(data[kind]):
            if old.get("id") == item["id"]:
                data[kind][i] = {**old, **item}
                break
        else:
            data[kind].append(item)
    _write(folder, data)
    return item


def docs_not_needed(folder):
    """Document labels marked "not needed" for this client (e.g. no financing, no winter tires)."""
    try:
        data = json.loads((Path(folder) / FILE).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return set()
    return set(data.get("docs_not_needed", []))


def set_doc_needed(folder, label, needed):
    data = load(folder)  # re-read: someone else may have saved meanwhile
    labels = set(data.get("docs_not_needed", []))
    (labels.discard if needed else labels.add)(label)
    data["docs_not_needed"] = sorted(labels)
    _write(folder, data)


def delete_item(folder, kind, item_id):
    data = load(folder)
    data[kind] = [x for x in data[kind] if x.get("id") != item_id]
    _write(folder, data)


# ---------- tracker: everything that needs attention ----------
def due_items(folder, data, horizon_days=45, quote_follow_up_days=7):
    """Reminders for one client: manual ones plus ones worked out from the policies."""
    out = []
    now = datetime.date.today()
    for r in data["reminders"]:
        d = parse_date(r.get("due"))
        if not r.get("done") and d:
            out.append({"due": d, "what": r.get("text", ""), "kind": "Reminder", "id": r.get("id")})
    for p in data["policies"]:
        status = p.get("status", "")
        label = f"{p.get('line', '')} {p.get('insurer', '')} {p.get('policy_number', '')}".strip()
        exp = parse_date(p.get("expiry"))
        if exp and status in ("Bound", "Active", "Renewed") and exp <= now + datetime.timedelta(days=horizon_days):
            what = "Policy expired - renew or close" if exp < now else "Renewal coming up - review / re-market"
            out.append({"due": exp, "what": f"{what}: {label}", "kind": "Renewal"})
        if status == "Quoted":
            created = parse_date((p.get("created") or "")[:10]) or now
            follow = created + datetime.timedelta(days=quote_follow_up_days)
            out.append({"due": follow, "what": f"Follow up on quote: {label}", "kind": "Quote"})
        if status == "Bound" and p.get("line") == "Auto" and not data["vehicles"]:
            out.append({"due": parse_date(p.get("bound_date")) or now,
                        "what": f"Add vehicle details for {label}", "kind": "Missing info"})
    return out


def scan_all(client_folders):
    """[(folder, data)] for every client that has records."""
    result = []
    for folder in client_folders:
        if (Path(folder) / FILE).exists():
            result.append((Path(folder), load(folder)))
    return result
