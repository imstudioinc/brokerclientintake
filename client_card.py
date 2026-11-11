"""The "details to copy" card on the client page: the people in the file (main client + household), their licence
numbers and birth dates, the cars with their VINs, and the bound policy. Every value is copied with one click, so the
broker never opens a file just to copy a number again.

`build()` only uses what the client page has already read (client.json + tracking.json): no file is opened here.
"""
import datetime

import records


def mdy(value):
    """'1983-03-20' -> '03/20/1983' (ARS and PowerBroker want MM/DD/YYYY); anything else is returned as it is."""
    try:
        return datetime.date.fromisoformat(str(value)).strftime("%m/%d/%Y")
    except (TypeError, ValueError):
        return str(value or "")


def _chip(label, value, copy=None):
    """A value the broker can copy: (label, shown text, copied text)."""
    value = str(value or "").strip()
    return (label, value, (copy if copy is not None else value)) if value else None


def build(folder_name, info, data, format_dln=lambda s: s):
    """{"people": [{name, relation, main, chips}], "cars": [{label, roles, chips}], "policy": {title, chips}}"""
    raw = (data or {}).get("household")
    raw = raw if isinstance(raw, dict) else {}
    people = [{"id": "main", "name": folder_name.upper(), "relation": "Main client", "main": True,
               "chips": [c for c in (_chip("Phone", info.get("phone")), _chip("Email", info.get("email")),
                                     _chip("Licence", format_dln(info.get("dln") or "")),
                                     _chip("Born", mdy(info.get("birth")))) if c]}]
    for p in raw.get("people") or []:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        chips = [c for c in (_chip("Licence", format_dln(p.get("dln") or "")), _chip("Born", mdy(p.get("birth")))) if c]
        people.append({"id": p.get("id"), "name": str(p["name"]).upper(), "relation": p.get("relation") or "",
                       "main": False, "chips": chips})

    names = {p["id"]: p["name"].title() for p in people}
    cars = []
    roles = raw.get("roles") or {}
    for car in raw.get("cars") or []:
        if not isinstance(car, dict) or not car.get("label"):
            continue
        by = roles.get(car.get("id")) or {}
        said = []
        for role in ("Principal", "Occasional"):
            who = [names[i] for i, r in by.items() if r == role and i in names]
            if who:
                said.append(f"{role}: {', '.join(who)}")
        cars.append({"label": car["label"], "roles": "   ·   ".join(said),
                     "chips": [c for c in (_chip("VIN", (car.get("vin") or "").upper()),) if c]})
    if not cars:      # no household cars: the vehicles saved on the client's record
        for v in (data or {}).get("vehicles", []):
            label = " ".join(str(v.get(k) or "") for k in ("year", "make", "model")).strip()
            if not label:
                continue
            cars.append({"label": label, "roles": f"Principal: {v['principal_driver'].title()}"
                         if v.get("principal_driver") else "",
                         "chips": [c for c in (_chip("VIN", (v.get("vin") or "").upper()),) if c]})

    policy = None
    p = records.bound_policy(data or {})
    if p:
        chips = [c for c in (_chip("Policy #", p.get("policy_number")),
                             _chip("Effective", mdy(p.get("effective"))),
                             _chip("Expiry", mdy(p.get("expiry"))),
                             _chip("Premium", f"${records.money(p.get('premium')):,.2f}" if records.money(p.get("premium"))
                                   else "", copy=f"{records.money(p.get('premium')):.2f}"
                                   if records.money(p.get("premium")) else "")) if c]
        policy = {"title": " ".join(x for x in (p.get("insurer"), p.get("line")) if x) or "Policy", "chips": chips}
    return {"people": people, "cars": cars, "policy": policy}


def as_text(card):
    """Everything on the card as plain text (for 'Copy all')."""
    lines = []
    for p in card["people"]:
        lines.append(p["name"].title() + (f" ({p['relation']})" if p["relation"] and not p["main"] else ""))
        lines += [f"  {label}: {copy}" for label, _, copy in p["chips"]]
    for c in card["cars"]:
        lines.append(c["label"] + (f" - {c['roles']}" if c["roles"] else ""))
        lines += [f"  {label}: {copy}" for label, _, copy in c["chips"]]
    if card["policy"]:
        lines.append(card["policy"]["title"])
        lines += [f"  {label}: {copy}" for label, _, copy in card["policy"]["chips"]]
    return "\n".join(lines)
