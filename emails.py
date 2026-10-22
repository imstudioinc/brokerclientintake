"""Client email templates: templates/emails/*.html, with your own edited copies in
%APPDATA%\\ClientIntake\\emails taking priority (same file name).

Template file format:
    <!--
    name: Auto policy confirmation
    group: 3. Policy confirmations
    order: 30
    subject: Your Auto Insurance Policy - Confirmation | {CLIENT_NAME}
    fields: insurer = Insurance company; auto_policy_number = Auto policy number
    attach: Policy documents and pink card(s)
    -->
    <p>Hi {first_name}, ...</p>  {{include:policy_reminders}}

{first_name}, {CLIENT_NAME}, {client_name} and {broker_name} are filled automatically;
names listed under "fields" are asked for in the app.
"""
import html
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

BUILT_IN = Path(__file__).parent / "templates" / "emails"
USER_DIR = Path(os.environ.get("APPDATA", Path.home())) / "ClientIntake" / "emails"
AUTO_FIELDS = {"first_name", "client_name", "CLIENT_NAME", "broker_name"}


@dataclass
class Template:
    file: str
    name: str
    group: str
    order: int
    subject: str
    body: str
    fields: list = field(default_factory=list)   # [(key, label)]
    attach: str = ""
    custom: bool = False                         # an edited copy in USER_DIR


def _parse(path, custom):
    text = path.read_text(encoding="utf-8-sig")
    m = re.match(r"\s*<!--(.*?)-->", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        text = text[m.end():]
    fields = []
    for part in filter(None, (p.strip() for p in meta.get("fields", "").split(";"))):
        key, _, label = part.partition("=")
        fields.append((key.strip(), label.strip() or key.strip()))
    return Template(path.name, meta.get("name", path.stem), meta.get("group", "Other"),
                    int(meta.get("order", 99)), meta.get("subject", path.stem), text.strip(),
                    fields, meta.get("attach", ""), custom)


def load_templates():
    files = {p.name: (p, False) for p in BUILT_IN.glob("*.html")}
    if USER_DIR.exists():
        files.update({p.name: (p, True) for p in USER_DIR.glob("*.html")})
    templates = []
    for path, custom in files.values():
        try:
            templates.append(_parse(path, custom))
        except Exception:
            continue  # a broken custom file must not break the app
    return sorted(templates, key=lambda t: (t.group, t.order, t.name))


def _block(name):
    for base in (USER_DIR / "_blocks", BUILT_IN / "_blocks"):
        f = base / f"{name}.html"
        if f.exists():
            return f.read_text(encoding="utf-8-sig")
    return ""


def first_name(full):
    first = (full or "").split()[0] if (full or "").split() else ""
    return first.capitalize()


def render(template, values):
    """Return (subject, body_html). Values are HTML-escaped; unknown {names} stay visible."""
    body = re.sub(r"\{\{include:([\w-]+)\}\}", lambda m: _block(m.group(1)), template.body)

    def fill(text, escape):
        def sub(m):
            key = m.group(1)
            if key not in values or values[key] in (None, ""):
                return m.group(0)
            return html.escape(str(values[key])) if escape else str(values[key])
        return re.sub(r"\{(\w+)\}", sub, text)

    body_html = ('<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt">'
                 + fill(body, True) + "</div>")
    return fill(template.subject, False), body_html


def missing_fields(template, values):
    """Placeholders still unfilled after rendering (to warn before creating the draft)."""
    subject, body = render(template, values)
    return sorted(set(re.findall(r"\{(\w+)\}", subject + body)))


def to_text(body_html):
    """Rough plain-text preview of the HTML body."""
    t = re.sub(r">\s+<", "><", body_html)
    t = re.sub(r"<ul[^>]*><li", "\n<li", t)
    t = re.sub(r"<li[^>]*>", "  • ", t)
    t = re.sub(r"</p>", "\n\n", t)
    t = re.sub(r"</(li|ul|div)>|<br\s*/?>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def edit_copy(template):
    """Make (or reuse) an editable copy of a template in USER_DIR and return its path."""
    USER_DIR.mkdir(parents=True, exist_ok=True)
    dest = USER_DIR / template.file
    if not dest.exists():
        shutil.copy(BUILT_IN / template.file, dest)
    return dest
