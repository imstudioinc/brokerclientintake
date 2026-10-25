"""Edit a client: new name / type means a new folder; files named after the client follow.

plan() works out what would change (shown to the broker before saving); apply() does it.
Reports from outside (DASH, MVR, quote) keep their contents - only file names change, and
only when the old client name is part of the file name.
"""
import re
import shutil
from pathlib import Path

import mvr_email

KEEP = {"client.json", "tracking.json"}


def files_with_name(folder, name):
    """Files in the client folder whose name contains the client's name (any case)."""
    if not name:
        return []
    pat = re.compile(re.escape(name), re.I)
    return sorted(p for p in Path(folder).iterdir() if p.is_file() and p.name not in KEEP and pat.search(p.name))


def renamed(path, old, new):
    return path.with_name(re.sub(re.escape(old), new.replace("\\", r"\\"), path.name, flags=re.I))


def plan(folder, new_folder, old_name, new_name):
    """[(file, new file name)] to rename inside the folder when the name changes."""
    if old_name.upper() == new_name.upper():
        return []
    out = []
    for p in files_with_name(folder, old_name):
        target = renamed(p, old_name, new_name)
        if target.name != p.name:
            out.append((p, target.name))
    return out


def apply(folder, new_folder, renames, details):
    """Move / rename the folder, rename the files, save the details. Returns the new folder.

    The folder is moved first: if Windows refuses (a file is open), nothing has changed yet.
    """
    folder, new_folder = Path(folder), Path(new_folder)
    if new_folder != folder:
        if new_folder.exists() and new_folder.resolve() != folder.resolve():
            raise FileExistsError(f"A client folder '{new_folder.name}' already exists in {new_folder.parent.name}.")
        new_folder.parent.mkdir(parents=True, exist_ok=True)
        try:
            if new_folder.resolve() == folder.resolve():      # only the letter case changes
                tmp = folder.with_name(folder.name + " .renaming")
                folder.rename(tmp)
                tmp.rename(new_folder)
            else:
                shutil.move(str(folder), str(new_folder))
        except OSError as e:
            raise OSError(f"Could not move the folder - close any file or window that has it open, then try again. "
                          f"({e.strerror or e})") from e
    done = []
    for old, new_name in renames:
        src = new_folder / old.name
        dest = src.with_name(new_name)
        if not src.exists():
            continue
        if dest.exists() and dest.resolve() != src.resolve():
            stem, n = dest.stem, 2
            while dest.exists():
                dest = dest.with_name(f"{stem} ({n}){dest.suffix}")
                n += 1
        try:
            src.rename(dest)
            done.append(dest.name)
        except OSError:
            pass   # an open file keeps its old name; everything else still goes through
    mvr_email.save_client(new_folder, **details)
    return new_folder, done
