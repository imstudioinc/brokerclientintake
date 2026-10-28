"""Rules search: finds the lines in the underwriting notes (.md files) that match a question.

No AI and no internet: the notes are split into sections (## headings) and items
(bullet points, paragraphs, table rows); sections are ranked by how many of the
question's words they contain, rare words counting more, and the carrier named in the
question pulls that carrier's notes up.
"""
import math
import re
from pathlib import Path

import sys

FOLDER = "Underwriting Knowledge"
DEFAULT_NOTES = Path.home() / "Documents" / "Docs" / "Insurance" / FOLDER
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent


def _has_notes(folder):
    try:
        return folder.is_dir() and any(folder.glob("*.md"))
    except OSError:
        return False


def notes_dir(cfg):
    """The notes folder, found without any setting: the folder chosen in the Rules tab (if it still
    exists), else an "Underwriting Knowledge" folder next to the app or up to two folders above it
    (e.g. Desktop next to ClientIntake-windows/ClientIntake/ClientIntake.exe; in the project folder
    it is git-ignored - the repo is public), next to the Clients folder, or in Documents."""
    chosen = cfg.get("knowledge_dir")
    if chosen and _has_notes(Path(chosen)):
        return Path(chosen)
    places = [APP_DIR / FOLDER, APP_DIR.parent / FOLDER, APP_DIR.parent.parent / FOLDER]
    if cfg.get("clients_root"):
        places.append(Path(cfg["clients_root"]).parent / FOLDER)
    places.append(DEFAULT_NOTES)
    return next((p for p in places if _has_notes(p)), Path(chosen) if chosen else DEFAULT_NOTES)

CARRIERS = ("intact", "jevco", "pembridge", "echelon", "pafco", "wellcare", "economical", "aviva")

STOP = set("""a an the and or of to in on at for by with from as is are be been was were it its this that these
those i we you my our your me can could would should will shall may might do does did done have has had
not no yes if then than so what which who whom whose when where why how any all some each every about into
over under between there here also just only very much many more most less other such same get gets
take takes taking client clients customer need needs needed want ok okay please tell know one""".split())

# question word -> extra words to look for (matched at lower weight)
SYNONYMS = {
    "accident": ["fault", "collision", "claim"], "accidents": ["fault", "collision", "claim"],
    "crash": ["accident", "fault", "collision"], "claim": ["accident", "loss"],
    "ticket": ["conviction", "speeding", "minor"], "tickets": ["conviction", "speeding", "minor"],
    "conviction": ["ticket", "minor", "major", "serious"], "speeding": ["speed", "conviction"],
    "dui": ["impaired", "serious", "criminal"], "impaired": ["dui", "criminal", "serious"],
    "bike": ["motorcycle"], "motorbike": ["motorcycle"], "scooter": ["motorcycle", "moped"],
    "house": ["home", "dwelling", "homeowner"], "home": ["dwelling", "homeowner", "property"],
    "renter": ["tenant"], "rent": ["tenant", "rented"], "apartment": ["tenant", "condo"],
    "truck": ["commercial", "pickup"], "van": ["commercial"], "business": ["commercial"],
    "pay": ["payment", "monthly", "instalment"], "payment": ["pay", "monthly", "instalment", "nsf"],
    "monthly": ["payment", "instalment", "pac"], "nsf": ["payment", "bounced"],
    "cancel": ["cancellation", "cancelled"], "cancellation": ["cancel", "cancelled"],
    "lapse": ["gap", "lapsed"], "gap": ["lapse"], "deductible": ["ded"],
    "new": ["newly", "licensed"], "young": ["underage", "age"], "teen": ["underage", "age"],
    "ev": ["electric", "hybrid"], "electric": ["ev", "hybrid"], "theft": ["stolen", "anti"],
    "uber": ["rideshare", "delivery"], "doordash": ["delivery"], "rideshare": ["uber", "delivery"],
    "discount": ["discounts"], "surcharge": ["surcharges"], "refer": ["referral", "underwriter"],
    "decline": ["ineligible", "declined", "not"], "eligible": ["eligibility", "ineligible"],
}

_HEAD = re.compile(r"^(#{1,6})\s+(.*)")
_BULLET = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)")
_WORD = re.compile(r"[a-z0-9]+")


def clean(text):
    """Markdown -> plain text for display."""
    text = re.sub(r"\*\*|__|`", "", text)
    text = re.sub(r"\[\[([^\]]+)\]\]|\[([^\]]+)\]\([^)]*\)", lambda m: m.group(1) or m.group(2), text)
    return text.replace("\\|", "|").strip()


def stem(word):
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ses", "xes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def words(text):
    return [stem(w) for w in _WORD.findall(text.lower()) if w not in STOP]


def _cells(line):
    return [clean(c) for c in line.strip().strip("|").split("|")]


def parse(name, text):
    """One note -> [{note, title, heading, items: [display text]}] (one per section)."""
    title = Path(name).stem
    sections = []
    cur = {"note": name, "title": title, "heading": "", "items": []}
    header = None   # current table's column names

    def start(heading):
        nonlocal cur
        if cur["items"] or cur["heading"]:
            sections.append(cur)
        cur = {"note": name, "title": title, "heading": heading, "items": []}

    for raw in text.splitlines():
        line = raw.rstrip()
        m = _HEAD.match(line)
        if m:
            header = None
            if len(m.group(1)) == 1:
                title = cur["title"] = clean(m.group(2))
            else:
                start(clean(m.group(2)))
            continue
        if line.lstrip().startswith("|"):
            cells = _cells(line)
            if all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cells):
                continue                      # the |---|---| separator
            if header is None:
                header = cells
                continue
            first, rest = cells[0], cells[1:]
            pairs = [f"{h}: {v}" if h else v for h, v in zip(header[1:], rest) if v and v != "-"]
            cur["items"].append((f"{first} - " if first else "") + "; ".join(pairs))
            continue
        header = None
        if not line.strip():
            continue
        b = _BULLET.match(line)
        if b and len(b.group(1)) >= 2 and cur["items"]:
            cur["items"][-1] += "\n    • " + clean(b.group(2))   # sub-point: keep with its parent
        elif b:
            cur["items"].append(clean(b.group(2)))
        elif raw.startswith((" ", "\t")) and cur["items"]:
            cur["items"][-1] += " " + clean(line)               # wrapped line of the item above
        else:
            cur["items"].append(clean(line))
    start("")
    return sections


class Index:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.sections = []
        files = sorted(p for p in self.folder.glob("*.md") if "index" not in p.stem.lower())             if self.folder.is_dir() else []
        self.notes = [p.name for p in files]
        for p in files:
            self.sections += parse(p.name, p.read_text(encoding="utf-8-sig"))
        for s in self.sections:
            s["head_words"] = set(words(s["heading"]))
            s["item_words"] = [set(words(i)) for i in s["items"]]
            s["all_words"] = s["head_words"].union(*s["item_words"]) if s["item_words"] else s["head_words"]
        n = len(self.sections) or 1
        df = {}
        for s in self.sections:
            for w in s["all_words"]:
                df[w] = df.get(w, 0) + 1
        self.idf = {w: math.log(1 + n / c) for w, c in df.items()}

    def search(self, query, limit=8, per_section=8):
        """[{note, title, heading, items: [text], terms}] best first."""
        terms = {}   # stemmed word -> weight
        for w in words(query):
            terms[w] = 1.0
        for raw in _WORD.findall(query.lower()):
            for syn in SYNONYMS.get(raw, []):
                terms.setdefault(stem(syn), 0.5)
        carriers = [c for c in CARRIERS if c in terms]
        terms = {w: wt for w, wt in terms.items() if w in self.idf}
        if not terms:
            return []
        main = [w for w, wt in terms.items() if wt == 1.0] or list(terms)
        results = []
        for s in self.sections:
            found = s["all_words"] & terms.keys()
            if not found:
                continue
            score = sum(terms[w] * self.idf[w] for w in found)
            score += sum(terms[w] * self.idf[w] for w in s["head_words"] & terms.keys())
            covered = len(found & set(main)) / len(main)
            score *= 0.4 + covered          # sections with all the question's words first
            note = s["note"].lower()
            if carriers:
                score *= 2.5 if any(c in note for c in carriers) else 0.6
            hits = []
            for i, (text, iw) in enumerate(zip(s["items"], s["item_words"])):
                m = iw & terms.keys()
                if m:
                    hits.append((sum(terms[w] * self.idf[w] for w in m), i, text))
            if not hits and not (s["head_words"] & terms.keys()):
                continue
            best = sorted(hits, reverse=True)[:per_section]
            items = [t for _, _, t in sorted(best, key=lambda h: h[1])] or s["items"][:per_section]
            results.append({"note": s["note"], "title": s["title"], "heading": s["heading"],
                            "items": items, "score": score, "more": len(s["items"]) - len(items)})
        results.sort(key=lambda r: -r["score"])
        return results[:limit]

    def highlight_words(self, query):
        """Words to highlight in results (question words and their synonyms)."""
        out = set(words(query))
        for raw in _WORD.findall(query.lower()):
            out.update(stem(s) for s in SYNONYMS.get(raw, []))
        return sorted((w for w in out if len(w) > 1), key=len, reverse=True)
