"""Self-update for the packaged exe from GitHub Releases.

The finished zips are published to a public repo (RELEASES_REPO) so work
computers can download them without a GitHub login.

How an update is applied (no scripts - work computers often block them):
1. The running app downloads the zip and extracts it into <install>\\_update\\new.
2. It starts the NEW ClientIntake.exe from there with --finish-update and closes.
3. The new exe waits for the old one to exit, swaps <install>\\_internal and
   ClientIntake.exe, starts the installed app, and exits.
Every step is logged to <install>\\_update\\update.log.
"""
import ctypes
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from version import __version__

RELEASES_REPO = "imstudioinc/brokerclientintake-releases"
ASSET_NAME = "ClientIntake-windows.zip"
LATEST_URL = f"https://api.github.com/repos/{RELEASES_REPO}/releases/latest"
EXE = "ClientIntake.exe"
THEME_FILE = "customtkinter/assets/themes/blue.json"  # a file the app can't start without


def parse_version(text):
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3]) or (0,)


def is_packaged():
    return bool(getattr(sys, "frozen", False))


def install_dir():
    return Path(sys.executable).parent


def update_dir(install=None):
    return Path(install or install_dir()) / "_update"


def log(message, install=None):
    try:
        folder = update_dir(install)
        folder.mkdir(exist_ok=True)
        with open(folder / "update.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {message}\n")
    except OSError:
        pass


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


def _count_files(folder):
    return sum(1 for p in Path(folder).rglob("*") if p.is_file())


def _rmtree(path):
    shutil.rmtree(path, ignore_errors=True)


def download_and_install(update, progress=None):
    """Step 1-2: download + extract next to the app, then hand over to the new exe.
    The caller must close the app right after this returns."""
    install = install_dir()
    work = update_dir(install)
    for leftover in ("new", ASSET_NAME, "failed.txt"):
        p = work / leftover
        _rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
    work.mkdir(exist_ok=True)
    log(f"--- update {__version__} -> {update['version']} ---")

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
    log(f"downloaded {zip_path.stat().st_size} bytes")

    with zipfile.ZipFile(zip_path) as z:
        expected = sum(1 for i in z.infolist() if not i.is_dir() and "/_internal/" in i.filename)
        z.extractall(work / "new")
    zip_path.unlink(missing_ok=True)
    src = work / "new" / "ClientIntake"
    if (not (src / EXE).exists() or not (src / "_internal" / THEME_FILE).exists()
            or _count_files(src / "_internal") != expected):
        raise RuntimeError("The downloaded update is incomplete.")
    log("extracted; starting the new version to finish")

    subprocess.Popen([str(src / EXE), "--finish-update", str(install), str(os.getpid())],
                     cwd=str(src), close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


def _wait_for_exit(pid, seconds=60):
    SYNCHRONIZE = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if handle:
        ctypes.windll.kernel32.WaitForSingleObject(handle, seconds * 1000)
        ctypes.windll.kernel32.CloseHandle(handle)
    time.sleep(1)  # let Windows release the file locks


def _retry(action, what, install, attempts=15):
    for i in range(attempts):
        try:
            return action()
        except OSError as e:
            if i == attempts - 1:
                raise
            log(f"{what}: {e} - retrying", install)
            time.sleep(1)


def finish_update(install, old_pid):
    """Step 3 - runs inside the NEW exe (from <install>\\_update\\new\\ClientIntake)."""
    install = Path(install)
    src = Path(sys.executable).parent
    log(f"finishing: new version {__version__} from {src}", install)
    _wait_for_exit(int(old_pid))

    internal, old_internal = install / "_internal", install / "_internal.old"
    staged = install / "_internal.new"
    exe, old_exe = install / EXE, install / "ClientIntake.old.exe"
    try:
        # copy the new files next to the old ones first and check them: on a network drive a copy
        # can stop half way, and the app must never be left with half of its files
        _rmtree(staged)
        shutil.copytree(src / "_internal", staged)
        if _count_files(staged) != _count_files(src / "_internal") or not (staged / THEME_FILE).exists():
            raise RuntimeError("the new files did not copy completely")
        _rmtree(old_internal)
        old_exe.unlink(missing_ok=True)
        _retry(lambda: internal.rename(old_internal), "move old files", install)
        _retry(lambda: staged.rename(internal), "put new files in place", install)
        _retry(lambda: exe.rename(old_exe), "move old exe", install)
        shutil.copy2(src / EXE, exe)
        for extra in src.iterdir():  # e.g. READ ME FIRST.txt
            if extra.is_file() and extra.name != EXE:
                shutil.copy2(extra, install / extra.name)
        log("files replaced", install)
    except Exception as e:
        log(f"FAILED: {e!r} - restoring the previous version", install)
        try:
            if old_internal.exists():
                if internal.exists():
                    _retry(lambda: internal.rename(install / "_internal.bad"), "set aside new files", install)
                _retry(lambda: old_internal.rename(internal), "restore old files", install)
            if old_exe.exists():
                exe.unlink(missing_ok=True)
                _retry(lambda: old_exe.rename(exe), "restore old exe", install)
        except Exception as e2:
            log(f"RESTORE FAILED: {e2!r}", install)
        _rmtree(staged)
        _rmtree(install / "_internal.bad")
        (update_dir(install) / "failed.txt").write_text(str(e), encoding="utf-8")

    subprocess.Popen([str(exe)], cwd=str(install), close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    log("started the app", install)


def cleanup_after_update():
    """Runs in the installed app at startup: remove leftovers, report a failed update."""
    install = install_dir()
    failed = update_dir(install) / "failed.txt"
    reason = failed.read_text(encoding="utf-8") if failed.exists() else None
    for _ in range(20):  # the finishing exe may still be exiting
        _rmtree(install / "_internal.old")
        try:
            (install / "ClientIntake.old.exe").unlink(missing_ok=True)
        except OSError:
            pass
        _rmtree(update_dir(install) / "new")
        if not (install / "_internal.old").exists() and not (update_dir(install) / "new").exists():
            break
        time.sleep(1)
    failed.unlink(missing_ok=True)
    return reason
