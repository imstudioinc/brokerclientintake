"""Auto-file MVRs: watch Downloads for MVR PDFs and move each into its client's folder.

New Outlook cannot be read by other programs, so the broker clicks Download on the
branch manager's MVR attachment; this module does the rest. A PDF is treated as an
MVR only if its file name or text looks like one, then matched to a client by the
licence number printed on it (or, failing that, the client's full name).
"""
import datetime
import json
import re
import shutil
import time
from pathlib import Path


from fill_consent import read_consent
from mvr_email import load_client, save_client

MVR_WORDS = re.compile(r"\bMVR\b|DRIVER'?S?\s+RECORD|DRIVER\s+ABSTRACT|DRIVING\s+RECORD|"
                       r"MINISTRY\s+OF\s+TRANSPORTATION|SERVICEONTARIO", re.I)
# Our own documents also carry licence numbers - never treat them as an MVR
SKIP_NAMES = re.compile(r"^(DASH Report|Client Consent|New Client Consent)|consent form|quote", re.I)
DLN_IN_TEXT = re.compile(r"\b([A-Z])[\s-]?(\d{4})[\s-]?(\d{5})[\s-]?(\d{5})\b")


def _plumber():
    """pdfplumber, loaded when a PDF is first opened (it takes ~0.2 s to import: not at startup)."""
    import pdfplumber
    return pdfplumber


def _raw_dln(dln):
    return re.sub(r"[^A-Z0-9]", "", (dln or "").upper())


def _household_people(folder):
    """[(raw licence #, NAME)] of the household members saved in the client's tracking.json (the main client is not in it)."""
    try:
        raw = json.loads((Path(folder) / "tracking.json").read_text(encoding="utf-8-sig"))
        people = (raw.get("household") or {}).get("people") or []
    except (OSError, ValueError, AttributeError):
        return []
    return [(_raw_dln(p.get("dln")), " ".join(str(p.get("name", "")).split()).upper())
            for p in people if isinstance(p, dict) and p.get("name")]


class ClientIndex:
    """Licence # and name -> client folder, cached per folder. Each folder lists its people: the main client first,
    then the household members (their MVRs go into the same folder)."""

    def __init__(self):
        self._cache = {}  # folder -> (mtime, [(dln_raw, name)])

    def build(self, folders):
        index = {}
        for folder in folders:
            try:
                mtime = folder.stat().st_mtime
            except OSError:
                continue
            cached = self._cache.get(folder)
            if not cached or cached[0] != mtime:
                info = load_client(folder)
                dln, name = info.get("dln", ""), info.get("name", "") or folder.name
                if not dln:  # older clients: the licence # is on the consent form
                    for consent in [*folder.glob("*Client Consent*.pdf"), *folder.glob("*Consent Form*.pdf")]:
                        found = read_consent(consent)
                        if found and found[1]:
                            dln = found[1]
                            break
                cached = (mtime, [(_raw_dln(dln), name.upper())] + _household_people(folder))
                self._cache[folder] = cached
            index[folder] = cached[1]
        return index


def read_pdf_text(path, pages=2):
    try:
        with _plumber().open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages[:pages])
    except Exception:
        return ""


def match_client(path, text, index):
    """Return (folder, how, who) for the client this MVR belongs to: who = the household member's name when it is
    not the main client's (None = the main client), or (None, reason, None)."""
    haystack = f"{path.stem}\n{text}".upper()
    found_dlns = {"".join(m) for m in DLN_IN_TEXT.findall(haystack)}
    by_dln = {f: next(i for i, (dln, _) in enumerate(ents) if dln and dln in found_dlns)
              for f, ents in index.items() if any(dln and dln in found_dlns for dln, _ in ents)}
    if by_dln:     # several folders = the same person in different types: newest folder wins
        f = max(by_dln, key=lambda x: x.stat().st_mtime) if len(by_dln) > 1 else next(iter(by_dln))
        i = by_dln[f]
        return f, "licence #", (index[f][i][1] if i else None)
    words = set(re.findall(r"[A-Z']+", haystack))
    by_name = {}
    for f, ents in index.items():
        for i, (_, name) in enumerate(ents):
            if len(name.split()) >= 2 and set(name.split()) <= words:
                by_name.setdefault(f, i)
                break
    if len(by_name) == 1:
        f, i = next(iter(by_name.items()))
        return f, "name", (index[f][i][1] if i else None)
    return None, "several clients match" if by_name else "no client matches", None


def file_mvr(path, folder, who=None):
    """Move the MVR into the client folder as 'MVR - NAME.pdf' (never overwrites). `who` = a household member's name."""
    name = (who or load_client(folder).get("name") or folder.name).upper()
    dest = folder / f"MVR - {name}.pdf"
    if dest.exists():
        dest = folder / f"MVR - {name} {datetime.date.today():%Y-%m-%d}.pdf"
        n = 2
        while dest.exists():
            dest = folder / f"MVR - {name} {datetime.date.today():%Y-%m-%d} ({n}).pdf"
            n += 1
    shutil.move(str(path), str(dest))
    save_client(folder, mvr_received=datetime.datetime.now().isoformat(timespec="minutes"))
    return dest


class Watcher:
    """Call poll() every few seconds (from a worker thread). Returns a list of events:
    ("filed", path, folder, how) or ("unmatched", path, reason)."""

    def __init__(self, downloads, started=None):
        self.downloads = Path(downloads)
        # files already in Downloads when the app starts are only considered if recent
        self.since = (started or time.time()) - 15 * 60
        self.sizes = {}      # path -> last size, to wait until a download has finished
        self.done = set()    # (path, mtime) already handled
        self.index = ClientIndex()

    def poll(self, client_folders):
        events = []
        if not self.downloads.exists():
            return events
        for path in self.downloads.glob("*.pdf"):
            try:
                st = path.stat()
            except OSError:
                continue
            key = (path, st.st_mtime)
            if st.st_mtime < self.since or key in self.done or SKIP_NAMES.search(path.name):
                continue
            if self.sizes.get(path) != st.st_size:  # still downloading, or first sight
                self.sizes[path] = st.st_size
                continue
            self.done.add(key)
            text = read_pdf_text(path)
            if not (MVR_WORDS.search(path.name) or MVR_WORDS.search(text)):
                continue
            folder, how, who = match_client(path, text, self.index.build(client_folders))
            if folder is None:
                events.append(("unmatched", path, how))
                continue
            try:
                dest = file_mvr(path, folder, who)
            except OSError as e:
                events.append(("unmatched", path, f"could not move it ({e})"))
                continue
            events.append(("filed", dest, folder, how))
        return events
