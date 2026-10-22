"""Per-computer settings, stored in %APPDATA%\\ClientIntake\\config.json."""
import json
import os
from pathlib import Path

CONFIG_FILE = Path(os.environ.get("APPDATA", Path.home())) / "ClientIntake" / "config.json"

DEFAULTS = {
    "clients_root": "",
    "consent_template": "",   # empty = the built-in form in templates/
    "appearance": "System",   # System | Light | Dark
    "mvr_to": "",             # branch manager, e.g. name@brokerage.ca
    "mvr_cc": "",             # separate several with ;
    "email_app": "New Outlook",  # New Outlook | Classic Outlook
    "client_types": "Auto, Home, Tenant, Commercial",  # sub-folders of the Clients folder
    "last_type": "Auto",
    "mvr_autosave": True,     # file MVR PDFs from Downloads into client folders
    "knowledge_dir": "",      # Ask tab notes; empty = Documents\Docs\Insurance\Underwriting Knowledge
    "anthropic_api_key": "",  # Ask tab; empty = use the ANTHROPIC_API_KEY environment variable
}


def load():
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig")))  # -sig: tolerate a BOM
        except (ValueError, OSError):
            pass
    return cfg


def save(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


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
