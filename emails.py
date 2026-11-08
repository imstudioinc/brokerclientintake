"""Email templates (to the client, the underwriter, the insurer's billing team): templates/emails/*.html,
with your own edited copies in %APPDATA%\\ClientIntake\\emails taking priority (same file name).

Template file format:
    <!--
    name: Auto policy confirmation
    group: 3. Policy confirmations
    order: 30
    subject: Your Auto Insurance Policy - Confirmation | {CLIENT_NAME}
    fields: insurer = Insurance company; auto_policy_number = Auto policy number
    attach: Policy documents and pink card(s)
    to: underwriter          (optional: sent to WellCare's underwriter, not the client;
                              "billing" = the policy carrier's billing team, from carriers.json)
    -->
    <p>Hi {first_name}, ...</p>  {{include:policy_reminders}}

{first_name}, {CLIENT_NAME}, {client_name} and {broker_name} are filled automatically;
names listed under "fields" are asked for in the app.
"""
import hashlib
import html
import os
import re
import uuid
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
    outdated: bool = False                       # an edited copy made from an older original
    to: str = ""                   # "underwriter" = WellCare's underwriter, "billing" = carrier billing, else the client


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
    outdated = bool(custom and meta.get("based_on") and (BUILT_IN / path.name).exists()
                    and meta["based_on"] != original_stamp(path.name))
    return Template(file=path.name, name=meta.get("name", path.stem), group=meta.get("group", "Other"),
                    order=int(meta.get("order", 99)), subject=meta.get("subject", path.stem), body=text.strip(),
                    fields=fields, attach=meta.get("attach", ""), custom=custom,
                    outdated=outdated, to=meta.get("to", "").lower())


def original_stamp(file):
    """A short fingerprint of the built-in template (an edited copy remembers which original it came from)."""
    try:
        return hashlib.md5((BUILT_IN / file).read_bytes()).hexdigest()[:8]
    except OSError:
        return ""


_cache = {"key": None, "templates": []}


def _stamp(folder):
    try:
        with os.scandir(folder) as entries:
            return tuple(sorted((e.name, e.stat().st_mtime) for e in entries if e.name.endswith(".html")))
    except OSError:
        return ()


def load_templates():
    """All templates, your edited copies replacing the originals. Cached until a template file changes."""
    key = (_stamp(BUILT_IN), _stamp(USER_DIR))
    if key == _cache["key"]:
        return list(_cache["templates"])
    files = {p.name: (p, False) for p in BUILT_IN.glob("*.html")}
    if USER_DIR.exists():
        files.update({p.name: (p, True) for p in USER_DIR.glob("*.html")})
    templates = []
    for path, custom in files.values():
        try:
            templates.append(_parse(path, custom))
        except Exception:
            continue  # a broken custom file must not break the app
    templates.sort(key=lambda t: (t.group, t.order, t.name))
    _cache.update(key=key, templates=templates)
    return list(templates)


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
    """Return (subject, body_html). Values are HTML-escaped (except keys ending in _html, which are
    ready-made HTML from the app); unknown {names} stay visible."""
    body = re.sub(r"\{\{include:([\w-]+)\}\}", lambda m: _block(m.group(1)), template.body)

    def fill(text, escape):
        def sub(m):
            key = m.group(1)
            if key not in values or values[key] in (None, ""):
                return m.group(0)
            return html.escape(str(values[key])) if escape and not key.endswith("_html") else str(values[key])
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


# ---------- editing a template in the app ----------
# The editor shows the body as plain text: a blank line starts a new paragraph, a line starting with "- " is
# a bullet, **bold** is bold, and {{include:name}} (a shared paragraph) stays on a line of its own.
# Templates only use <p>, <b>, <ul> and <li>; a body with other markup is edited as HTML instead.
_ALONE = r"\{\{include:[\w-]+\}\}|\{\w+_html\}"          # a shared paragraph, or a ready-made HTML block
_BLOCK = re.compile(r"\s*(<p>(.*?)</p>|<ul>(.*?)</ul>|(" + _ALONE + "))", re.S)


def _inline_to_text(s):
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</?b>", "**", s)
    if re.search(r"</?\w", s):
        raise ValueError("other markup")
    return html.unescape(s).strip()


def html_to_text(body):
    """The body as editor text, or None when it uses markup the plain text can't hold."""
    rest, pos, blocks = body.strip(), 0, []
    try:
        while pos < len(rest):
            m = _BLOCK.match(rest, pos)
            if not m:
                return None
            pos = m.end()
            if m.group(2) is not None:
                blocks.append(_inline_to_text(m.group(2)))
            elif m.group(3) is not None:
                if re.sub(r"<li>.*?</li>|\s", "", m.group(3), flags=re.S):
                    return None
                items = re.findall(r"<li>(.*?)</li>", m.group(3), re.S)
                blocks.append("\n".join("- " + _inline_to_text(i) for i in items))
            else:
                blocks.append(m.group(4))
    except ValueError:
        return None
    return "\n\n".join(blocks)


def _text_to_inline(s):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(s.strip(), quote=False))


def text_to_html(text):
    """Editor text -> the HTML the template file holds."""
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue
        if len(lines) == 1 and re.fullmatch(_ALONE, lines[0]):
            out.append(lines[0])
        elif all(l.startswith(("- ", "• ")) for l in lines):
            out.append("<ul>\n" + "\n".join(f"  <li>{_text_to_inline(l[2:])}</li>" for l in lines) + "\n</ul>")
        else:
            out.append("<p>" + "<br>".join(_text_to_inline(l) for l in lines) + "</p>")
    return "\n".join(out)


def _write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def save_custom(template, subject, body_html):
    """Save your edited copy of a template (same file name: it replaces the original in the app)."""
    subject = " ".join(subject.split()) or template.subject
    head = ["name: " + template.name, "group: " + template.group, f"order: {template.order}",
            "subject: " + subject]
    if template.fields:
        head.append("fields: " + "; ".join(f"{k} = {label}" for k, label in template.fields))
    if template.attach:
        head.append("attach: " + template.attach)
    if template.to:
        head.append("to: " + template.to)
    head.append("based_on: " + original_stamp(template.file))
    _write_atomic(USER_DIR / template.file, "<!--\n" + "\n".join(head) + "\n-->\n" + body_html.strip() + "\n")


def reset_custom(template):
    """Go back to the original wording: delete your edited copy."""
    (USER_DIR / template.file).unlink(missing_ok=True)


# ---------- which templates belong to which quote ----------
LINES = ("auto", "home", "tenant", "commercial")
AUTO_ONLY = {"pink-card.html", "temp-pink-card.html", "ab-optional-declined.html",
             "uw-new-driver.html", "uw-high-deductible.html"}


def lines_of(file):
    """The lines of business a template is about, from its file name: {"auto"}, {"tenant"}, {"auto", "tenant"} ...
    Empty = fits any quote (down payment, billing)."""
    if file in AUTO_ONLY:
        return {"auto"}
    return {w for w in re.split(r"[-.]", file) if w in LINES}


def fits(file, kind, bundle=False):
    """Does this template belong on a `kind` client's Write email page?
    Auto: auto and auto + home / tenant. Home / Tenant: that line only, plus the auto bundle when `bundle`.
    Commercial: commercial only. Other / unknown kinds see everything."""
    kind = (kind or "").lower()
    lines = lines_of(file)
    if kind not in LINES or not lines:
        return True
    if kind == "auto":
        return "auto" in lines
    if kind == "commercial":
        return lines == {"commercial"}
    return lines == {kind} or (bundle and "auto" in lines and lines <= {"auto", kind})
