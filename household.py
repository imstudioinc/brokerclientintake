"""The household behind one policy file: the people who drive and the cars they drive.

One client folder = one household. The folder is named after the main client; the others (spouse, children, a parent, anyone,
with any surname) are listed here, so their documents live in the same folder and nothing is copied between folders.

Saved in tracking.json under "household":
    {"people": [{id, name, relation, dln, birth}],        # the main client is NOT stored: id "main", name = the folder name
     "cars":   [{id, label, vin}],
     "roles":  {car id: {person id: "Principal" | "Occasional" | "Excluded"}}}     # a missing role = not a driver of that car

Rules checked by `problems()`: every car needs exactly one principal driver, and every person should drive at least one car.
Documents (DASH / MVR) belong to the person whose name or licence # they show (`assign_docs`, reads PDFs: use a thread).
"""
import uuid
from pathlib import Path

import records

KEY = "household"
MAIN = "main"
ROLES = ["Principal", "Occasional", "Excluded"]
RELATIONS = ["Spouse / partner", "Son", "Daughter", "Parent", "Brother / sister", "Other family", "Other"]


def _clean_name(text):
    return " ".join(str(text or "").split()).upper()


def load(folder):
    """{"people": [...], "cars": [...], "roles": {...}} with the main client first in people (always present)."""
    folder = Path(folder)
    raw = records.load(folder).get(KEY)
    raw = raw if isinstance(raw, dict) else {}
    info = records.client_info(folder)
    main = {"id": MAIN, "name": folder.name.upper(), "relation": "Main client", "dln": info.get("dln", ""),
            "birth": info.get("birth", "")}
    people = [main] + [dict(p) for p in raw.get("people", []) if isinstance(p, dict) and p.get("id") != MAIN]
    roles = {c: dict(r) for c, r in (raw.get("roles") or {}).items() if isinstance(r, dict)}
    return {"people": people, "cars": [dict(c) for c in raw.get("cars", []) if isinstance(c, dict)], "roles": roles}


def save(folder, data):
    """Save people (except the main client), cars and roles. Atomic, re-reads the file so other changes are kept."""
    people = []
    for p in data.get("people", []):
        if p.get("id") == MAIN or not _clean_name(p.get("name")):
            continue
        people.append({"id": p.get("id") or uuid.uuid4().hex[:8], "name": _clean_name(p["name"]),
                       "relation": p.get("relation", ""), "dln": (p.get("dln") or "").strip().upper(),
                       "birth": (p.get("birth") or "").strip()})
    ids = {MAIN} | {p["id"] for p in people}
    cars = [{"id": c.get("id") or uuid.uuid4().hex[:8], "label": " ".join(str(c.get("label", "")).split()),
             "vin": (c.get("vin") or "").strip().upper()} for c in data.get("cars", []) if str(c.get("label", "")).strip()]
    car_ids = {c["id"] for c in cars}
    roles = {}
    for car, by_person in (data.get("roles") or {}).items():
        if car in car_ids:
            kept = {pid: r for pid, r in by_person.items() if pid in ids and r in ROLES}
            if kept:
                roles[car] = kept
    folder_data = records.load(folder)
    folder_data[KEY] = {"people": people, "cars": cars, "roles": roles}
    records._write(folder, folder_data)
    return load(folder)


def is_household(data):
    """More than one person or car recorded (a one-person, one-car file needs none of this)."""
    return len(data["people"]) > 1 or len(data["cars"]) > 1


def problems(data):
    """Short sentences about what is missing or odd in the roles."""
    out = []
    people = {p["id"]: p for p in data["people"]}
    for car in data["cars"]:
        by = data["roles"].get(car["id"], {})
        principals = [people[i]["name"].title() for i, r in by.items() if r == "Principal" and i in people]
        if not principals:
            out.append(f"{car['label']}: no principal driver yet.")
        elif len(principals) > 1:
            out.append(f"{car['label']}: more than one principal driver ({', '.join(principals)}).")
    if data["cars"]:
        for p in data["people"]:
            if not any(data["roles"].get(c["id"], {}).get(p["id"]) in ("Principal", "Occasional") for c in data["cars"]):
                out.append(f"{p['name'].title()} is not a driver on any car (set Excluded if that is on purpose).")
    return out


def summary(data):
    """'3 people, 2 cars' (empty for a plain one-person file)."""
    if not is_household(data):
        return ""
    n, c = len(data["people"]), len(data["cars"])
    return f"{n} {'person' if n == 1 else 'people'}" + (f", {c} car{'s' if c != 1 else ''}" if c else "")


def summary_raw(tracking):
    """The same summary from an already loaded tracking.json dict (no file read: the client page has it in hand)."""
    raw = (tracking or {}).get(KEY)
    if not isinstance(raw, dict):
        return ""
    people, cars = 1 + len(raw.get("people") or []), len(raw.get("cars") or [])
    if people < 2 and cars < 2:
        return ""
    return f"{people} {'person' if people == 1 else 'people'}" + (f", {cars} car{'s' if cars != 1 else ''}" if cars else "")


def role_of(data, person_id, car_id):
    return data["roles"].get(car_id, {}).get(person_id, "")


def cars_of(data, person_id):
    """[(car, role)] for the cars this person drives (not Excluded)."""
    return [(c, role_of(data, person_id, c["id"])) for c in data["cars"]
            if role_of(data, person_id, c["id"]) in ("Principal", "Occasional")]


def as_text(data):
    """Plain text of who drives what (for a note or to paste into PowerBroker)."""
    if not data["cars"]:
        return "\n".join(f"{p['name'].title()} ({p.get('relation') or 'person'})" for p in data["people"])
    lines = []
    for car in data["cars"]:
        by = data["roles"].get(car["id"], {})
        lines.append(car["label"])
        for role in ("Principal", "Occasional", "Excluded"):
            names = [p["name"].title() for p in data["people"] if by.get(p["id"]) == role]
            if names:
                lines.append(f"   {role}: {', '.join(names)}")
    return "\n".join(lines)


# ---------- from the ARS quote ----------
def from_quote(folder, data):
    """(new data, what was added): drivers and vehicles of the newest ARS quote that are not listed yet. Reads a PDF."""
    import client_facts
    import review
    import quote
    quotes = review.find_docs(folder)["quote"]
    if not quotes:
        return data, []
    q = quote.read(str(quotes[0]))
    data = {"people": [dict(p) for p in data["people"]], "cars": [dict(c) for c in data["cars"]],
            "roles": {c: dict(r) for c, r in data["roles"].items()}}
    added = []
    for d in q.get("drivers", []):
        name = _clean_name(d.get("name"))
        if not name or any(_same_name(name, p["name"]) for p in data["people"]):
            continue
        data["people"].append({"id": uuid.uuid4().hex[:8], "name": name, "relation": "",
                               "dln": client_facts.format_dln(d.get("licence") or ""),
                               "birth": d["birth"].isoformat() if d.get("birth") else ""})
        added.append(name.title())
    for v in q.get("vehicles", []):
        label = client_facts._car(v.get("description") or "")
        vin = (v.get("vin") or "").upper()
        if not label or any((vin and vin == c.get("vin")) or label.upper() == c["label"].upper() for c in data["cars"]):
            continue
        data["cars"].append({"id": uuid.uuid4().hex[:8], "label": label, "vin": vin})
        added.append(label)
    return data, added


def _same_name(a, b):
    ta, tb = set(_clean_name(a).replace(",", " ").split()), set(_clean_name(b).replace(",", " ").split())
    return bool(ta and tb) and (ta <= tb or tb <= ta)


# ---------- documents per person ----------
def _name_in_file(person, file_name):
    tokens = _clean_name(person["name"]).replace(",", " ").split()
    upper = file_name.upper()
    return len(tokens) >= 2 and all(t in upper for t in tokens)


def assign_docs(folder, data, found=None):
    """{person id: {"dash": [paths], "mvr": [paths]}} - each DASH / MVR goes to the person it is for: the name in the
    file name first, else the name / licence # inside the PDF; a file nobody claims belongs to the main client.
    Reads PDFs (cached): call it from a thread."""
    import client_facts
    import fill_consent
    import review
    found = found or review.find_docs(folder)
    people = data["people"]
    out = {p["id"]: {"dash": [], "mvr": []} for p in people}
    for kind, reader in (("dash", client_facts.read_dash), ("mvr", client_facts.read_mvr)):
        for path in found.get(kind, []):
            owner = next((p["id"] for p in people if _name_in_file(p, path.name)), None)
            if owner is None:
                try:
                    inside = client_facts._cached(path, reader) or []
                except Exception:
                    inside = []
                for who in inside:
                    owner = next((p["id"] for p in people
                                  if fill_consent._same_person(p["name"], who["name"], p.get("dln", ""), who["dln"])), None)
                    if owner:
                        break
            out[owner or MAIN][kind].append(path)
    return out
