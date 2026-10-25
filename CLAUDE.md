# Client Intake - notes for Claude Code

Read this first. It records how this project works, the owner's standing rules, and decisions
already made, so they don't have to be repeated in every session. Keep it up to date when a
decision changes (edit the section, don't append contradictions).

## Who it's for

- The owner is an **Ontario P&C insurance broker (RIBO Level 1) at WellCare Insurance**. Day to day:
  quotes in **Applied Rating Services (ARS)**, binds in **PowerBroker**, pulls **DASH** reports and
  **MVRs** (driver abstracts, requested by email from the branch manager), emails clients through
  **Outlook** (New Outlook by default; Classic Outlook supported).
- The **work computer is a remote desktop where Python can't be installed** - the app runs there as
  a packaged exe (PyInstaller) and updates itself from GitHub Releases. Development happens on a
  normal PC with Python (3.14 at the time of writing).
- Explain things in plain, short English; the owner reads quickly and wants practical results.

## Standing rules (owner's instructions)

- **Never publish a release on your own.** No `release.py` / `release.bat`, no `version.py` bump,
  unless the owner says to release. Commit and push are fine (and expected) after each finished,
  tested change.
- Template files must not be named `Client Consent*.pdf` -
  `.gitignore` blocks that pattern; the consent template is `templates/WellCare Consent Form.pdf`.
- **Never commit client documents or data.** `.gitignore` covers DASH / consent / MVR / quote PDFs,
  `tracking.json`, `client.json`. Test with copies in the temp/scratch folder, not in the repo.
- **Both GitHub repos are public**: code `imstudioinc/brokerclientintake`, downloads
  `imstudioinc/brokerclientintake-releases`. Don't put confidential material in either:
  - The **Underwriting Knowledge notes** (carrier manuals, WellCare in-house rules, payments,
    contacts) stay **out of the repo**. On this dev PC they are in
    `Documents\Docs\Insurance\Underwriting Knowledge\` (10 notes + `00 Index.md`); on the remote
    desktop the owner copied the folder locally and points the Rules tab at it (Notes folder…).
  - Known issue, owner informed: `templates/rules_ontario.json` (built-in eligibility rules,
    summarised from Intact / Jevco / Echelon manuals and WellCare rules) is in the public repo.
    Offered to move it out (read from a file on the shared drive); not decided yet.
  - Never copy portal passwords or similar secrets anywhere.
- **No paid / online AI in the app.** An AI chat tab (Claude API) was built and then removed: the
  API needs prepaid credits the owner didn't want. The replacement is the offline **Rules** search.
  Don't re-add an LLM feature unless asked.
- **Don't take screen captures of the owner's desktop while they work** (they may have client
  data open). For GUI checks, run the app off-screen (`geometry("+-4000+0")`) and measure widgets,
  or screenshot only the app's own window when it is clearly in front.
- Ask before anything hard to undo or outward-facing (rewriting git history, deleting files the
  owner made, sending email). Deleting your own generated files is fine.

## Running, building, releasing

- Run from source: `python client_intake.pyw`. `install.bat` sets up any PC that has Python
  (installs requirements, creates shortcuts).
- Dependencies: `requirements.txt` (customtkinter, pypdf, pdfplumber, pywin32, pypdfium2, and the
  `winrt-*` packages for Windows OCR). reportlab is NOT a dependency.
- Build the exe: `build.bat` -> `release\ClientIntake\ClientIntake.exe` + `ClientIntake-windows.zip`.
  PyInstaller flags that matter: `--collect-data customtkinter`, `--collect-data pdfminer`,
  `--collect-data pypdfium2_raw`, `--collect-submodules winrt` (OCR works in the frozen exe - tested),
  `--hidden-import win32com.client`, `--add-data "templates;templates"`.
- Release (only when told): `release.bat` / `python release.py X.Y.Z` bumps `version.py`, builds,
  publishes the zip to the releases repo. Installed apps see it on start and offer "Update now".
- Updater (`updater.py`): no scripts (work PCs block them). The running app downloads + extracts to
  `<install>\_update\new`, starts the NEW exe with `--finish-update`, which swaps `_internal` and
  the exe, restarts, logs to `_update\update.log`.
- Version history: v1.4.1 was the last release (2026-10-23). Unreleased since then: void cheque in
  auto documents + scrollable details panel (commit 78327d2) - check `git log` for newer.

## Settings and data

- Per-computer settings: `%APPDATA%\ClientIntake\config.json` (`config.py`). Always save with
  `config.update(cfg, key=value)` - it re-reads the file and writes only changed keys. Read with
  `utf-8-sig` (a BOM once wiped the owner's settings: never edit this file with PowerShell
  `Set-Content`/`Out-File` defaults).
- Keys include `clients_root`, `client_types`, `email_app`, `mvr_to`/`mvr_cc`, signature fields
  (`sig_name` etc.), `mvr_autosave`, `sample_prev_root` (set while showing sample clients), `knowledge_dir` (Rules tab notes), `rules_file` (custom eligibility rules).
- Clients folder (shared drive at work): `Clients\<Type>\<CLIENT NAME>\`. Types default to
  Auto, Home, Tenant, Commercial; folders directly in Clients show as "Other". Names are UPPERCASE.
- Per-client records: `<client folder>\tracking.json` (`records.py`) - policies, vehicles, property,
  business, notes, reminders, and `docs_not_needed`. Saves re-read the file and replace it
  atomically so two people don't overwrite each other.

## Code map

| File | What it does |
|---|---|
| `client_intake.pyw` | Main window: new client form, client list (paged, cached), details panel (documents + actions), dialogs (Settings, Signature, MVR request, Email, Import DASH), top bar Clients / Tracker / Rules views, design tokens |
| `fill_consent.py` | Fills WellCare's consent form (`templates/WellCare Consent Form.pdf`): client's name first, then other DASH drivers (up to 4); **no DASH needed**; built-in form is filled then **flattened** (fields removed); a custom template with `Driver License n` fields keeps the old behaviour. Ontario licence # format `A1234-12345-12345` |
| `tools/make_consent_template.py` | Rebuilds the consent template from a filled WellCare form: removes the printed name/date text (not just covers it - the repo is public), adds rows and fields. Dev-only (pypdf) |
| `dash_import.py` | Finds DASH reports in Downloads and moves them into the client folder |
| `mvr_email.py`, `mvr_watch.py` | MVR request email (Outlook draft with attachments); watches Downloads and files incoming MVR PDFs into the right client by licence # / name |
| `emails.py`, `templates/emails/` | Client email templates (quote requests, quote accepted / documents needed, confirmations, pink card) as Outlook drafts with the HTML signature |
| `records.py`, `tracker_ui.py` | Client record dialog and the Tracker view (to-dos, renewals, policies) |
| `notes_search.py`, `rules_ui.py` | **Rules** tab: offline search over the `.md` notes (sections by `##`, items = bullets / table rows; rare words weigh more, named carrier's notes first, small synonym list) |
| `eligibility.py` | DASH reader (facts, claims, policies, gaps) + rules engine (`if` / `when` conditions, verdicts Proceed / Caution / Refer to underwriter / Not eligible, market `tier` and `lines`) |
| `templates/rules_ontario.json` | Built-in rules: Intact (standard), Jevco (non-standard), Echelon (commercial, Commercial clients only), WellCare in-house rules (`applies_to_all`) |
| `ocr.py` | PDF text layer, else Windows built-in OCR (`Windows.Media.Ocr` via winrt) - no internet, nothing to install |
| `mvr.py` | MVR reader (PDF text, scanned PDF or photo/screenshot) |
| `quote.py` | Applied Rating "Quote Information" PDF reader |
| `review.py`, `eligibility_ui.py` | **Review quote & eligibility** window: quote vs MVR vs DASH checks, WellCare quote rules, markets that fit |
| `sample_data.py` | Fake sample clients for trying the Tracker (never real data) |
| `release.py`, `updater.py`, `version.py`, `build.bat`, `install.bat`, `update.bat`, `create_shortcuts.ps1` | Packaging and updates |

## UI conventions

- customtkinter; colours are `(light, dark)` tuples defined at the top of `client_intake.pyw`
  (`BG, SURFACE, SURFACE_ALT, BORDER, TEXT, MUTED, PRIMARY (WellCare red #C8102E), SUCCESS, DANGER`).
  `font(size, weight)` uses Segoe UI; spacing unit `SP = 8`; helpers `app.card()`,
  `app.secondary_button()`. Other modules get these via `sys.modules[type(app).__module__]`.
- One main window with three views (Clients / Tracker / Rules) switched by `App.show_view`; views
  are built on first use. Dialogs are `CTkToplevel` with `transient(app)`.
- Background threads must not touch widgets: use `app.ui(func, *args)` (a queue drained every
  200 ms) or `after()` polling. Slow work (OCR, PDF reading) runs in a thread.
- The main window must stay fast: the client list caches document counts by folder mtime and only
  repaints rows that changed. Avoid reading files per row on every refresh.
- Tk tag fonts in text boxes use **negative sizes (pixels)** to match CTk fonts.
- Keep screens simple: the owner found a long flat list of checks "too complicated". Pattern that
  works: one verdict line at the top, short grouped items, details folded away (click to open).

## Domain rules built into the code (don't "fix" these)

- **Documents tracked** per client: Client consent, DASH report, Quote (ARS), MVR. **Auto clients
  also**: Driver's licence, Ownership, Bill of sale, Winter tire photo, Void cheque, Financing / lease.
  The last four (and bill of sale) can be marked **N/A** per client. Any document may be a PDF **or
  a photo** (jpg/png/heic/…); found by words in the file name; **Add…** copies a file in with a
  standard name (`Ownership - NAME.jpg`). Watch for false matches (`*lien*` matched "Client";
  `*lease*` matched "Release" - patterns are word-start now).
- **DASH**: at-fault claims count only when **this driver was at the wheel** (claim detail page
  "First Party Driver"), like DASH's own summary; claims driven by others / unnamed are shown to
  check. At-fault = fault > 25%. Gaps come from `*POSSIBLE GAP*` lines between policies.
  Intact's lapse rule applies only to gaps in the last 12 months (or uninsured now).
- **No DASH report** = no insurance history (treated as a new driver).
- **MVR** (dates DD/MM/YYYY; offence dates YYYY/MM/DD): the **conviction date (left column) is the
  one that counts**, not the offence date. If the **expiry date has the same day/month as the
  birth date, the issue date is the G1 date**; G2 = G1 + 1 year if the class is G2 or G; G = G2 + 1
  year only if the class is G. Otherwise ask for the licence history.
  OCR skips "G\*\*\*": the class is read by OCRing each character inside a made-up word
  (char + "ARAGE"), only real Ontario classes accepted, majority vote across passes; photos are
  read three ways and merged; small images (< ~1,100 px wide) get a "too small" warning.
- **Convictions** classed per the Intact / Jevco lists: hand-held device, 50-59 km/h over, stunt,
  no insurance, novice condition breaches = **major**; careless, impaired / alcohol, 60+ over,
  racing, driving while suspended, fail to remain = **serious**; everything else **minor**.
- **ARS quote PDF**: each row of values is printed ABOVE its row of labels; dates MM/DD/YYYY;
  carrier messages start with "■", discounts with "●". Messages with "Refer" / "Approval required"
  = refer; quote numbers and URLs are noise.
- **WellCare in-house quote rules** (from the notes): refer if annual km ≤ 8,000, deductible
  > $1,000, OPCF 28/28A, vehicle ≥ $150,000; caution / offer: OPCF 20 with physical damage,
  accident waiver, OPCF 43 on vehicles < 2 yrs, DCPD deductible $0, liability-only on new cars,
  lienholder papers for OPCF 23A.
- Recommendations prefer **standard markets (Intact)**, then non-standard (Jevco); Echelon only for
  Commercial clients (or commercial vehicles on the quote).

## Testing habits that worked

- Pure functions (`eligibility`, `mvr`, `quote`, `review`, `notes_search`) are tested directly with
  real sample PDFs the owner provides (kept outside the repo).
- GUI smoke tests: load `client_intake.pyw` with `importlib`, create `App()`, set
  `App._first_run = lambda self: None`, point `app.cfg["clients_root"]` at a temp folder **in
  memory only** (never save test paths into the owner's config), drive methods directly, count
  `report_callback_exception` errors.
- Frozen-exe check for new native deps: build a tiny PyInstaller test exe in the scratch folder
  with the same flags and run it.
- Python's `-I` flag hides user site-packages on this PC (pypdf etc. live there) - run own scripts
  without it.
