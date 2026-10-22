"""Per-computer settings, stored in %APPDATA%\\ClientIntake\\config.json."""
import json
import os
from pathlib import Path

APP_DIR = Path(__file__).parent
CONFIG_FILE = Path(os.environ.get("APPDATA", Path.home())) / "ClientIntake" / "config.json"

DEFAULTS = {
    "clients_root": "",
    "consent_template": str(APP_DIR / "templates" / "New Client Consent Form.pdf"),
    "appearance": "System",   # System | Light | Dark
}


def load():
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            pass
    return cfg


def save(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
