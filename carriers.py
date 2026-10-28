"""Carrier contacts, payment terms, where to submit and tips.

Read from carriers.json in the Underwriting Knowledge folder (the Rules tab's notes folder), NOT
from the repo: the repo is public and the file has underwriters' direct lines and WellCare's trust
account. Without the file the pages say where to put it.
"""
import json
import re
from pathlib import Path

import notes_search

FILE = "carriers.json"
PHONE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_cache = {}


def path(cfg):
    return notes_search.notes_dir(cfg) / FILE


def load(cfg):
    """{"carriers": {name: {...}}, "wellcare_payment": {...}} - empty dicts when the file is missing."""
    p = path(cfg)
    try:
        key = (str(p), p.stat().st_mtime)
    except OSError:
        return {"carriers": {}, "wellcare_payment": {}}
    if key not in _cache:
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = {}
        data.setdefault("carriers", {})
        data.setdefault("wellcare_payment", {})
        _cache.clear()
        _cache[key] = data
    return _cache[key]


def find(data, text):
    """The carrier named in text (e.g. "Coachman" or "Intact Insurance"), or None."""
    t = (text or "").lower()
    for name, c in data.get("carriers", {}).items():
        if name.lower() in t or any(re.search(r"\b" + re.escape(a), t) for a in c.get("aliases", [])):
            return name
    return None


def contacts(lines):
    """Phones and emails found in contact lines, in order: [("phone" | "email", value, line)]."""
    out = []
    for line in lines:
        for m in sorted(list(PHONE.finditer(line)) + list(EMAIL.finditer(line)), key=lambda m: m.start()):
            out.append(("email" if "@" in m.group() else "phone", m.group(), line))
    return out


def ext_of(line):
    m = re.search(r"\bext\.?:?\s*(\d+)", line, re.I)
    return m.group(1) if m else ""


def wellcare_payment_text(data):
    """WellCare's payment options as plain text to paste into an email to the client."""
    w = data.get("wellcare_payment") or {}
    if not w:
        return ""
    lines = ["How to pay your premium", ""]
    for title, points in w.get("options", []):
        lines.append(title)
        lines += [f"- {p}" for p in points]
        lines.append("")
    if w.get("intro"):
        lines.append(w["intro"])
    return "\n".join(lines).strip()
