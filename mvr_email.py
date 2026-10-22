"""MVR request email (New or Classic Outlook draft) and per-client details (client.json)."""
import html
import json
import os
import re
import shutil
import subprocess
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

CLIENT_FILE = "client.json"


# ---------- client details saved in each client folder ----------
def load_client(folder):
    f = Path(folder) / CLIENT_FILE
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_client(folder, **values):
    data = load_client(folder)
    data.update({k: v for k, v in values.items() if v is not None})
    (Path(folder) / CLIENT_FILE).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def split_name(full):
    """'JOHN A SMITH' -> ('JOHN A', 'SMITH')."""
    parts = full.split()
    if len(parts) < 2:
        return full, ""
    return " ".join(parts[:-1]), parts[-1]


def format_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return (phone or "").strip()


# ---------- email ----------
def build_subject(dln, first, last):
    return f"MVR Request | {dln} | {first} {last}".strip()


def build_body_html(first, last, dln, phone, email):
    e = lambda s: html.escape(s or "")
    rows = [("Last Name", last), ("First Name", first), ("License Number", dln),
            ("Phone", phone), ("Email", email)]
    details = "".join(f"<b>{k}: {e(v)}</b><br>" for k, v in rows)
    return (
        '<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt">'
        "<p>Hello,</p>"
        "<p>Please find below the client details for <b>MVR request</b>.</p>"
        f"<p>{details}</p>"
        "<p>Please advise at your earliest convenience.</p>"
        "<p>Thank you,</p>"
        "</div>"
    )


class OutlookNotReady(Exception):
    pass


def create_new_outlook_draft(folder, to, cc, subject, body_html, attachments=()):
    """Write an unsent .eml into the client folder and open it in New Outlook as a draft.

    New Outlook (olk.exe) has no automation API, but opens an .eml with
    'X-Unsent: 1' as an editable draft with its attachments. It cannot read
    files under AppData, so the draft is kept in the client folder (also a record).
    """
    msg = EmailMessage()
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["X-Unsent"] = "1"
    msg["Message-ID"] = make_msgid()
    msg.set_content(re.sub(r"<[^>]+>", "", body_html.replace("<br>", "\n").replace("</p>", "\n\n")))
    msg.add_alternative(body_html, subtype="html")
    for path in attachments:
        path = Path(path)
        maintype, subtype = ("application", "pdf") if path.suffix.lower() == ".pdf" \
            else ("application", "octet-stream")
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)

    name = re.sub(r'[\\/:*?"<>|]', "", subject.split("|")[-1]).strip()
    out = Path(folder) / f"MVR Request - {name}.eml"
    out.write_bytes(bytes(msg))

    olk = shutil.which("olk.exe") or str(Path(os.environ.get("LOCALAPPDATA", "")) /
                                          "Microsoft" / "WindowsApps" / "olk.exe")
    if not Path(olk).exists():
        raise OutlookNotReady("New Outlook is not installed. Install it from the Microsoft Store, "
                              "or switch to Classic Outlook in Settings.")
    subprocess.Popen([olk, str(out)])
    return out


def _retry(fn, seconds=20):
    """Outlook rejects calls while it is starting up ('Call was rejected by callee')."""
    import time
    import pywintypes
    end = time.time() + seconds
    while True:
        try:
            return fn()
        except pywintypes.com_error as e:
            if e.hresult != -2147418111 or time.time() > end:  # RPC_E_CALL_REJECTED
                raise
            time.sleep(0.5)


def create_outlook_draft(to, cc, subject, body_html, attachments=(), display=True):
    """Open a Classic Outlook draft with the user's default signature kept at the bottom."""
    import win32com.client  # Windows + Classic Outlook only

    outlook = _retry(lambda: win32com.client.Dispatch("Outlook.Application"))
    try:
        accounts = _retry(lambda: outlook.Session.Accounts.Count)
    except Exception:
        accounts = 0
    if not accounts:
        raise OutlookNotReady("Classic Outlook has no email account yet. Open Outlook, "
                              "add your email account (File > Add Account), then try again.")

    mail = _retry(lambda: outlook.CreateItem(0))  # olMailItem
    if display:
        mail.Display()            # loads the default signature into HTMLBody
    signature_html = mail.HTMLBody or ""

    mail.To = to
    mail.CC = cc
    mail.Subject = subject
    m = re.search(r"<body[^>]*>", signature_html, re.I)
    if m:
        mail.HTMLBody = signature_html[: m.end()] + body_html + signature_html[m.end():]
    else:
        mail.HTMLBody = body_html + signature_html
    for path in attachments:
        mail.Attachments.Add(str(path))
    return mail
