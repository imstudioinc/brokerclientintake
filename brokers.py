"""Broker profiles: who is using this computer, and the details that follow them into every form.

Each broker has a profile (name, branch number, signature details, MVR request addresses) and an optional PIN.
Profiles live in the per-computer settings (config.json, key "brokers"): never in the repo, never on the shared
drive. Signing in copies the broker's details into the settings the rest of the app already reads (the email
signature `sig_*`, `mvr_to` / `mvr_cc`), so emails, the MVR request and the records' "by" name follow the broker
without every screen being changed. The Commercial application takes the broker name and branch number from here.

The PIN is a convenience lock, not strong security: it is stored salted and hashed (PBKDF2), but the settings file
sits on the same computer, so it only keeps one broker from opening another's profile by accident.
"""
import hashlib
import hmac
import os

import config

# (key, label, hint). branch_no = the branch number on forms (B01); branch = the line in the email signature
FIELDS = [("name", "Name", "e.g. Jordan Example"),
          ("title", "Title", "e.g. Insurance Broker"),
          ("phone", "Phone", "e.g. +1 (437) 555-0100"),
          ("email", "Email", "e.g. name@wellcareinsurance.ca"),
          ("address1", "Address line 1", "e.g. Unit 2-427 Dundas St E"),
          ("address2", "Address line 2", "e.g. Waterdown, ON L8B 0K4"),
          ("branch", "Branch (email signature)", "e.g. Branch #24"),
          ("branch_no", "Branch number (on forms)", "e.g. B01"),
          ("mvr_to", "MVR requests go to", "branch manager's email"),
          ("mvr_cc", "MVR requests copy to", "optional; separate several with ;")]
SIGNATURE_KEYS = ["name", "title", "phone", "email", "address1", "address2", "branch"]
ITERATIONS = 200_000


def _hash(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, ITERATIONS).hex()


def profiles(cfg):
    data = cfg.get("brokers")
    return data if isinstance(data, dict) else {}


def names(cfg):
    return sorted(profiles(cfg), key=str.lower)


def current(cfg):
    """The signed-in broker's profile ({} when nobody is signed in)."""
    name = cfg.get("current_broker") or ""
    return dict(profiles(cfg).get(name) or {})


def has_pin(profile):
    return bool(profile.get("pin_hash"))


def check_pin(profile, pin):
    if not has_pin(profile):
        return True
    try:
        salt = bytes.fromhex(profile["pin_salt"])
    except (KeyError, ValueError):
        return False
    return hmac.compare_digest(_hash(str(pin or ""), salt), profile["pin_hash"])


def save_profile(cfg, profile, pin=None, old_name=None):
    """Add / replace a profile. pin None = keep the old PIN, "" = no PIN, anything else = the new PIN."""
    data = dict(profiles(cfg))
    name = profile["name"].strip()
    previous = data.get(old_name or name) or {}
    clean = {k: str(profile.get(k, "")).strip() for k, _l, _h in FIELDS}
    clean["name"] = name
    if pin is None:
        for k in ("pin_salt", "pin_hash"):
            if previous.get(k):
                clean[k] = previous[k]
    elif pin:
        salt = os.urandom(16)
        clean["pin_salt"], clean["pin_hash"] = salt.hex(), _hash(pin, salt)
    if old_name and old_name != name:
        data.pop(old_name, None)
    data[name] = clean
    changes = {"brokers": data}
    if cfg.get("current_broker") in (old_name, name):
        changes["current_broker"] = name
    config.update(cfg, **changes)
    if changes.get("current_broker"):
        sign_in(cfg, name)                      # the signature / MVR settings follow the edited profile
    return clean


def delete_profile(cfg, name):
    data = dict(profiles(cfg))
    data.pop(name, None)
    changes = {"brokers": data}
    if cfg.get("current_broker") == name:
        changes["current_broker"] = ""
    config.update(cfg, **changes)


def sign_in(cfg, name):
    """Make this broker the one using the app: their details become the signature / MVR settings."""
    p = profiles(cfg).get(name)
    if not p:
        return False
    changes = {"current_broker": name, "mvr_to": p.get("mvr_to", ""), "mvr_cc": p.get("mvr_cc", "")}
    changes.update({f"sig_{k}": p.get(k, "") for k in SIGNATURE_KEYS})
    config.update(cfg, **changes)
    return True


def sign_out(cfg):
    config.update(cfg, current_broker="")


def sync_signature(cfg):
    """The Email signature page was saved: keep the signed-in broker's profile in step with it."""
    name = cfg.get("current_broker") or ""
    data = dict(profiles(cfg))
    if name in data:
        data[name] = {**data[name], **{k: cfg.get(f"sig_{k}", "") for k in SIGNATURE_KEYS}}
        config.update(cfg, brokers=data)


def defaults(cfg):
    """What forms prefill from the signed-in broker: {broker_name, branch}."""
    p = current(cfg)
    out = {}
    if p.get("name"):
        out["broker_name"] = p["name"]
    if p.get("branch_no"):
        out["branch"] = p["branch_no"]
    return out


def apply_defaults(cfg, values):
    """values with the broker's name / branch number filled in where the form has none."""
    values = dict(values)
    for k, v in defaults(cfg).items():
        if not values.get(k):
            values[k] = v
    return values
