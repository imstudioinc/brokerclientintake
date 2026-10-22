"""Self-update for the packaged exe from GitHub Releases.

The finished zips are published to a public repo (RELEASES_REPO) so work
computers can download them without a GitHub login.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from version import __version__

RELEASES_REPO = "imstudioinc/brokerclientintake-releases"
ASSET_NAME = "ClientIntake-windows.zip"
LATEST_URL = f"https://api.github.com/repos/{RELEASES_REPO}/releases/latest"


def parse_version(text):
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3]) or (0,)


def is_packaged():
    return bool(getattr(sys, "frozen", False))


def check_for_update(timeout=10):
    """Return {'version', 'url', 'notes'} when a newer release exists, else None."""
    req = urllib.request.Request(LATEST_URL, headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": "ClientIntake"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        release = json.load(resp)
    latest = release.get("tag_name", "")
    if parse_version(latest) <= parse_version(__version__):
        return None
    asset = next((a for a in release.get("assets", []) if a["name"] == ASSET_NAME), None)
    if not asset:
        return None
    return {"version": latest.lstrip("v"), "url": asset["browser_download_url"],
            "notes": release.get("body") or ""}


def download_and_install(update, progress=None):
    """Download the new zip, then hand over to a small script that swaps the files
    once this app has closed and starts the new version. Caller must exit right after.
    """
    work = Path(tempfile.gettempdir()) / "ClientIntake-update"
    if work.exists():
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(work)], capture_output=True)
    work.mkdir(parents=True)

    zip_path = work / ASSET_NAME
    req = urllib.request.Request(update["url"], headers={"User-Agent": "ClientIntake"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(zip_path, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 16):
            out.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(work / "new")
    src = work / "new" / "ClientIntake"
    if not (src / "ClientIntake.exe").exists() or not (src / "_internal").exists():
        raise RuntimeError("The downloaded update is incomplete.")

    install = Path(sys.executable).parent
    # Only the app's own files are replaced (_internal and the exe), never anything
    # else in the install folder.
    script = work / "apply-update.cmd"
    script.write_text(f"""@echo off
:wait
tasklist /FI "PID eq {os.getpid()}" 2>nul | find "{os.getpid()}" >nul && (timeout /t 1 /nobreak >nul & goto wait)
robocopy "{src / '_internal'}" "{install / '_internal'}" /MIR /R:10 /W:1 /NFL /NDL /NJH /NJS >nul
copy /Y "{src / 'ClientIntake.exe'}" "{install / 'ClientIntake.exe'}" >nul
start "" "{install / 'ClientIntake.exe'}"
""", encoding="mbcs")
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=subprocess.CREATE_NO_WINDOW,
                     close_fds=True)
