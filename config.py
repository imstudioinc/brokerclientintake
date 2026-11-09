"""Per-computer settings, stored in %APPDATA%\\ClientIntake\\config.json.

A second copy is kept next to the packaged exe (ClientIntake-settings.json): an update only replaces
the exe and _internal, and a remote desktop can reset %APPDATA%, so if config.json is missing or
unreadable the settings come back from that copy. Settings are never replaced by defaults just
because a read failed.
"""
import json
import os
import sys
from pathlib import Path

CONFIG_FILE = Path(os.environ.get("APPDATA", Path.home())) / "ClientIntake" / "config.json"
BACKUP_NAME = "ClientIntake-settings.json"

DEFAULTS = {
    "clients_root": "",
    "consent_template": "",   # empty = the built-in form in templates/
    "appearance": "System",   # System | Light | Dark
    "text_size": "Large",     # Normal | Large | Extra large (client_intake.TEXT_SIZES)
    "mvr_to": "",             # branch manager, e.g. name@brokerage.ca
    "mvr_cc": "",             # separate several with ;
    "email_app": "New Outlook",  # New Outlook | Classic Outlook
    "client_types": "Auto, Home, Tenant, Commercial",  # sub-folders of the Clients folder
    "last_type": "Auto",
    "mvr_autosave": True,     # file MVR PDFs from Downloads into client folders
    "knowledge_dir": "",      # Rules tab notes; empty = found by notes_search.notes_dir()
    "brokers": {},            # broker profiles (brokers.py): name -> details + salted PIN hash
    "current_broker": "",     # who signed in last / is signed in now
    "broker_prompted": False,  # the "make your profile" page has been shown once
}


def backup_file():
    """The copy next to the packaged exe; None when run from source (nothing is written to the repo)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / BACKUP_NAME
    return None


def _read(path):
    """The settings saved in path, or None if it is missing, empty or unreadable."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))   # -sig: tolerate a BOM
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data else None


def _write(path, cfg):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.replace(tmp, path)           # one step: a reader never sees a half-written file


def load():
    cfg = dict(DEFAULTS)
    data = _read(CONFIG_FILE)
    backup = backup_file()
    spare = _read(backup) if backup else None
    if spare:
        # keep every setting the spare copy has that config.json lost; config.json wins otherwise
        data = {**spare, **data} if data else spare
        if data != _read(CONFIG_FILE):
            try:
                _write(CONFIG_FILE, data)
            except OSError:
                pass
    elif data and backup:
        try:
            _write(backup, data)    # first start with this feature: make the copy
        except OSError:
            pass
    if data:
        cfg.update(data)
    return cfg


def save(cfg):
    _write(CONFIG_FILE, cfg)
    backup = backup_file()
    if backup:
        try:
            _write(backup, cfg)
        except OSError:
            pass                    # a read-only install folder must not stop settings from saving


def update(cfg, **changes):
    """Save only the changed keys on top of what is on disk now.

    Another open window of the app may have saved newer settings since this
    one started; writing the whole in-memory copy would wipe them.
    """
    current = load()
    current.update(changes)
    save(current)
    cfg.clear()
    cfg.update(current)
    return cfg
