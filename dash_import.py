"""Find DASH reports in Downloads and move them into a client folder."""
import ctypes
import re
import shutil
import uuid
from pathlib import Path

from fill_consent import read_dash

DASH_PATTERN = "DASH Report*.pdf"


def downloads_dir():
    """The user's Downloads folder, even if it was moved (e.g. to another drive or OneDrive)."""
    try:
        folder_id = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")  # FOLDERID_Downloads
        guid = (ctypes.c_byte * 16)(*folder_id.bytes_le)
        path = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(guid, 0, None, ctypes.byref(path)) == 0:
            result = Path(path.value)
            ctypes.windll.ole32.CoTaskMemFree(path)
            return result
    except (AttributeError, OSError):
        pass
    return Path.home() / "Downloads"


def _name_from_filename(path):
    """'DASH Report - Ersin Torun - 2026-10-21 ... .pdf' -> 'ERSIN TORUN'."""
    parts = path.stem.split(" - ")
    return parts[1].strip().upper() if len(parts) > 1 else ""


def find_dash_downloads(folder=None):
    """Return DASH reports in Downloads, newest first: [{path, name, dln, mtime}]."""
    folder = Path(folder or downloads_dir())
    if not folder.exists():
        return []
    reports = []
    for path in folder.glob(DASH_PATTERN):
        try:
            driver = read_dash(path)
        except Exception:
            driver = None
        name, dln = driver if driver else (_name_from_filename(path), "")
        reports.append({"path": path, "name": name, "dln": dln, "mtime": path.stat().st_mtime})
    return sorted(reports, key=lambda r: r["mtime"], reverse=True)


def names_match(client_name, dash_name):
    """True when every word of the shorter name appears in the longer one.

    Handles middle names and order: 'ERSIN TORUN' matches 'TORUN ERSIN' and 'ERSIN A TORUN'.
    """
    a = set(re.findall(r"[A-Z0-9']+", client_name.upper()))
    b = set(re.findall(r"[A-Z0-9']+", dash_name.upper()))
    if not a or not b:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 2 and short <= long_ or short == long_


def import_reports(paths, client_folder):
    """Move DASH reports into the client folder. Returns the new paths.

    A file with the same name already in the folder is left as is, and the
    Downloads copy is removed (it is the same report).
    """
    client_folder = Path(client_folder)
    moved = []
    for src in map(Path, paths):
        dest = client_folder / src.name
        if dest.exists():
            if dest.stat().st_size == src.stat().st_size:
                src.unlink()
                moved.append(dest)
                continue
            dest = client_folder / f"{src.stem} (2){src.suffix}"
        shutil.move(str(src), str(dest))
        moved.append(dest)
    return moved
