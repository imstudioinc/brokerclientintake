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
    `Documents\Docs\Insurance\Underwriting Knowledge\` (notes 01-12 + `00 Index.md` + `carriers.json`); on the remote
    desktop the folder sits on the Desktop next to `ClientIntake-windows`. No setting needed:
    `notes_search.notes_dir()` uses the chosen folder if it still exists, else `Underwriting Knowledge`
    next to the app or up to 2 folders above it, next to the Clients folder, or in Documents. Never
    put the notes in the repo or the release zip (`.gitignore` blocks `Underwriting Knowledge/`).
  - Known issue, owner informed: `templates/rules_ontario.json` (built-in eligibility rules,
    summarised from Intact / Jevco / Echelon manuals and WellCare rules) is in the public repo.
    Offered to move it out (read from a file on the shared drive); not decided yet.
  - **`carriers.json`** (carrier contacts incl. underwriters' direct lines, payment terms, where to
    submit, tips, WellCare's trust account / payment options) lives in the notes folder too, never
    the repo. Built from the owner's *Broker Resources (Branch Offices).xlsx* and *Wellcare - Premium
    Payment Options.pdf*; edit the JSON by hand when contacts change.
  - **`resources/`** (the carrier property manuals and guides the Home / Tenant / Commercial features were built from,
    ~75 MB) is in `.gitignore`: never commit it. The **carriers' property eligibility rules** are likewise data in the
    notes folder (`property_rules.json`, built by `build_property_rules.py` next to it), never in the repo; the repo only
    holds the engine (`property_risk.py`) and the form schema.
  - Never copy portal passwords or similar secrets anywhere (the spreadsheet has some - leave them out).
- **No paid / online AI in the app.** An AI chat tab (Claude API) was built and then removed: the
  API needs prepaid credits the owner didn't want. The replacement is the offline **Rules** search.
  Don't re-add an LLM feature unless asked.
- **Don't take screen captures of the owner's desktop while they work** (they may have client
  data open). For GUI checks, run the app off-screen (`geometry("+-4000+0")`) and measure widgets,
  or capture only the app's own window with `PrintWindow` (alpha 0).
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

- Per-computer settings: `%APPDATA%\ClientIntake\config.json` (`config.py`). The packaged exe also keeps a copy next to itself (`ClientIntake-settings.json`: updates only replace the exe and `_internal`, and the remote desktop may reset `%APPDATA%`); `load()` restores from it when `config.json` is missing / damaged, and a failed read never falls back to defaults. If the Clients folder is set but unreachable (shared drive not connected yet) the app keeps the setting, shows the path and rechecks every 4 s instead of asking for a new folder. Always save with
  `config.update(cfg, key=value)` - it re-reads the file and writes only changed keys. Read with
  `utf-8-sig` (a BOM once wiped the owner's settings: never edit this file with PowerShell
  `Set-Content`/`Out-File` defaults).
- Keys include `clients_root`, `client_types`, `email_app`, `mvr_to`/`mvr_cc`, signature fields
  (`sig_name` etc.), `mvr_autosave`, `sample_prev_root` (set while showing sample clients), `knowledge_dir` (Rules tab notes), `rules_file` (custom eligibility rules), `uw_email` (WellCare's in-house underwriter: typed once in the Email page, kept out of the public repo), `commercial_email` (the in-house commercial team: typed once the first time a `to: commercial` email is written, never in the repo).
- Clients folder (shared drive at work): `Clients\<Type>\<CLIENT NAME>\`. Types default to
  Auto, Home, Tenant, Commercial; folders directly in Clients show as "Other". Names are UPPERCASE.
- Per-client records: `<client folder>\tracking.json` (`records.py`) - policies, vehicles, property,
  business, notes, reminders, and `docs_not_needed`. Saves re-read the file and replace it
  atomically so two people don't overwrite each other.

## Code map

| File | What it does |
|---|---|
| `client_intake.pyw` | Main window (the client page has **one set of stage pages per client type**, `_sets` / `_pageset(key)` / `_use_set(key)`; document lists per type in `KIND_DOCS` / `STAGE_DOCS` / `BASE_DOCS`, extras in `CONDITIONAL_DOCS` only show when the property details need them): client list (paged; drawn from `_scan` + `_row_cache`, see Performance rules; line shows the client's stage) on the left with **+ New client**; selected client on the right (header with contact details + Open folder / Edit, a strip of the 3 stages, next-step card, then the chosen stage's buttons, steps and documents); dialogs (`ClientDialog` for new / edit, Settings, Signature, MVR request, Email, Import DASH); top bar Clients / Tracker / Rules views; design tokens |
| `panel.py` | `Panel`: a page inside the main window that replaces `CTkToplevel` for every dialog (Back bar, title, stacking, window-only calls ignored, forms centred / scrollable) |
| `property_risk.py`, `property_ui.py` | **Home / Tenant property file.** `property_risk`: the form schema (`SECTIONS` / `FIELDS`: ~80 questions in 9 sections, asked per kind of risk: owner / tenant / landlord / seasonal), `derive()` (ages, use), `completeness()`, `docs_needed()` (which questionnaires / certificates this property needs: alarm, oil tank, wood stove, sewer backup, rented dwelling, mortgage, letter of experience, photos, appraisal), `review()` (runs the rules from `property_rules.json` in the notes folder: per market Fits / check / refer / won't take + WellCare's own rules), `entry_sections()` (what to type into PowerBroker's habitational screens and Applied Quote, dates MM/DD/YYYY), `save()` (answers in `tracking.json` `property_intake`, and keeps the Tracker's Property record in step). `property_ui`: **Property details** form (collapsible sections, built on first open), **Review property**, **Entry sheet**; all read in a thread. Rule conditions: `[field, op, value]`, ops eq ne in ge gt le lt yes no notyes; an unanswered question never triggers a rule. **Never name a module `property`** (it shadows the built-in decorator) |
| `commercial_risk.py` | **Commercial details** schema (`SECTIONS` / `FIELDS`: business, operations, liquor / cooking, location, protection, vehicles, history, coverage wanted; built from WellCare's commercial application, the vehicle / fleet supplements and the restaurant questionnaire), `completeness()`, `docs_needed()` (vehicle supplement, fleet supplement at 5+ vehicles, CVOR, garage form, articles of incorporation, restaurant questionnaire, industry application, ULC certificate, subcontractor insurance, photos), `subject_line()`, `email_values()` (branch / PB code / binder / business name fill the commercial emails). Saved in `tracking.json` `commercial_intake`. `property_ui.PropertyDetailsPage` draws it too (`self.risk` = this module for Commercial clients; no Review page). No carrier rules in the repo |
| `property_quote.py` | Reads the ARS **property** "Quote Information" PDF (Home / Tenant): `quote.read` for carriers, premiums and messages plus the dwelling facts typed into PropertyRater (year built, roof / plumbing / electrical / heating / water heater years, sq ft, bedrooms, baths, contents, address); only free-form answers. The Property details page prefills EMPTY answers from it (`prefill`, never overwrites). Sample: a Tenant quote from Definity (rented-to-others = decline message) |
| `checklist.py` | One process per client type in `PROCESSES` (`Auto`, `Home`, `Tenant`, `Commercial`; `Other` = documents only): `steps_for(kind)`, `stages_for(kind)`, `email_for(kind, step)`, `waiting_for(kind)`, and `next_step / summary / current_stage(rows, kind)`. **Commercial** (20 steps) follows WellCare's commercial workflow (note 40): PowerBroker customer code + binder (name = policyholder), Commercial details, application, consent, supplements, **submission email to the in-house commercial team** (subject `B01 – Code X – Binder1234 – CGL (Business)`), quote, client decision within 3 days, quote accepted, binder complete, agency-bill invoice + premium before binding, documents to sign, signed documents back, **request to bind before the effective date** (never back-dated), subjectivities, COI, binder number -> policy number, policy documents. **Home** (20 steps) / **Tenant** (19) follow WellCare's property checklist + the PowerBroker Property Completion Guide (note 39): property details, consent (HITS + credit), HITS report, documents, EZITV, quote, review, UW call, quote accepted, PowerBroker policy, sewer / overland full limits written, application, documents to sign, signed docs + payment back, upload, head office, confirmation. Auto process: (23 steps in the owner's **3 stages** `STAGES`: 1 Intake = details & documents, 2 Quote = forms & quote, 3 Policy = the owner's bind process: quote accepted (saved to the Tracker), PowerBroker, documents to sign (auto application, consent, AB package, PAC), down payment requested / confirmed, Echelon billing email (N/A unless the policy is Echelon), upload + validate, submit to head office, temporary 1-month pink slip, head office confirms, 1-year pink slip + policy documents; `EMAIL_FOR_STEP` = the template each email step opens; `WAITING` steps (MVR received, client documents) don't hold up the next step): auto-ticks from folder / `client.json` (licence #, `mvr_requested`) and logged UW calls (`uw_call` step: done when a call is logged with a result, N/A by itself when the quote has no refer messages; the quote's refer messages are kept in `tracking.json` `quote_refers` keyed on file name + mtime so the client list never reads PDFs), manual ticks and N/A saved in `tracking.json` under `checklist`; `status()` / `summary()` feed the client panel and the list line |
| `client_edit.py` | Edit client: plan / apply a name or type change (move the folder first - if Windows refuses nothing has changed; then rename files containing the old name; save `client.json`) |
| `client_facts.py` | Reads the client's name, licence #, date of birth (quote + DASH + **MVR**; a DASH header that can't be read still gives licence # and birth), phone and email (quote page 1 only, the right-hand applicant block - the left block is the brokerage; DASH and MVR never have them). Fills EMPTY `client.json` fields only (never overwrites; `birth` saved as YYYY-MM-DD) and returns mismatch warnings (profile vs documents, quote vs DASH). Runs in `show_details`, so it re-checks whenever a document lands; PDFs cached by (path, mtime) |
| `carriers.py` | Loads `carriers.json` from the notes folder (`knowledge_dir`), cached by mtime; `find()` maps a quote's carrier name to an entry (aliases); `contacts()` pulls phones / emails out of contact lines |
| `carriers_ui.py` | **UW call** page (log the underwriter call: carrier, date / time, underwriter, number called, reason prefilled from the quote's refer messages, result, notes; saved in `tracking.json` `uw_calls`; copied as a PowerBroker note) and **Carriers & payments** page (contacts with Copy / Email, payment terms, where to submit, tips, WellCare payment options with "Copy for the client"). Opened from the client panel links, the next-step card, and the Rules tab |
| `fill_consent.py` | Fills WellCare's consent form (`templates/WellCare Consent Form.pdf`): client's name first, then other DASH drivers (up to 4); **no DASH needed**; built-in form is filled then **flattened** (fields removed); a custom template with `Driver License n` fields keeps the old behaviour. Ontario licence # format `A1234-12345-12345` |
| `tools/make_consent_template.py` | Rebuilds the consent template from a filled WellCare form: removes the printed name/date text (not just covers it - the repo is public), adds rows and fields. Dev-only (pypdf) |
| `dash_import.py` | Finds DASH reports in Downloads and moves them into the client folder |
| `mvr_email.py`, `mvr_watch.py` | MVR request email (Outlook draft with attachments); watches Downloads and files incoming MVR PDFs into the right client by licence # / name |
| `emails.py`, `templates/emails/` | Email templates (to the client, the underwriter, an insurer's billing team: quote requests, quote accepted / documents needed, confirmations, pink cards, UW approvals, billing) as Outlook drafts with the HTML signature. The page is called **Write email** (not "Email client": not every template goes to the client). **Edit this template** opens `TemplateEditor` (in `client_intake.pyw`): subject + message as plain text (blank line = paragraph, `- ` = bullet, `**bold**`; `emails.html_to_text` / `text_to_html`, HTML mode for anything else), click-to-insert fields, live preview, Reset; saves an edited copy in `%APPDATA%\ClientIntake\emails` (`emails.save_custom`, keeps `to` / `fields` / `attach`, remembers the original it was made from so an outdated copy is flagged; dropdown shows "(edited)"). `load_templates()` is cached by file times. **Write email shows only the templates for the client's quote**: `emails.lines_of(file)` reads the lines from the file name (`quote-auto-tenant.html` = auto + tenant; `AUTO_ONLY` = pink cards / auto UW emails; none = any quote), `emails.fits(file, kind, bundle)` filters: Auto clients see auto and auto + home / tenant, Home / Tenant clients only their own plus a **Bundle with Auto** checkbox that adds the auto ones, Commercial only commercial. A new template must carry its line in its file name. `to: commercial` sends it to the in-house commercial team (`commercial_email`; submission and request-to-bind emails, subject carries branch / code / binder from Commercial details). `to: underwriter` in a template's header sends it to WellCare's underwriter (`uw_email`) instead of the client, with the latest quote / DASH / MVR ticked: UW approval for < 1 yr insurance experience and deductibles over $1,000. Blanks are filled from the bound policy first (`policy_ui.email_values`), then the newest quote (`client_facts.quote_email_values`, read in a thread; several carriers = a picker, bindable ones first); blanks with `date` in the key get a calendar (`tracker_ui.DateField`); `{payment_options_html}` = WellCare's payment options from `carriers.json` (keys ending `_html` are not escaped) |
| `records.py`, `tracker_ui.py` | Client record dialog and the Tracker view (to-dos, renewals, policies; client phone / email from `client.json`, never retyped). The Tracker is editable: buttons + double-click open the policy / reminder behind a row in `RecordEditor` (`due_items` carry `record` + `id`), Add to-do / Add policy go through `ClientPicker`, Mark done works on reminders. `records.bound_policy()` = the newest bound policy |
| `policy_ui.py` | **Quote accepted / Policy details** page: carrier, premium, effective date and vehicles read from the newest quote and saved as the client's bound policy + vehicles (no retyping); down payment rule and 2-month suggestion from `carriers.json`; `email_values()` fills policy emails from the saved policies (each line's own `auto_` / `home_` / `tenant_policy_number`, plus `policy_number` for the main one) and `remember_policy_numbers()` saves a number typed into an email back onto the policy; `billing_email()` = the carrier's billing address from `carriers.json`, the one on the carrier's own domain when there are several (`to: billing` templates) |
| `notes_search.py`, `rules_ui.py` | **Rules** tab: offline search over the `.md` notes (sections by `##`, items = bullets / table rows; rare words weigh more, named carrier's notes first, small synonym list) |
| `eligibility.py` | DASH reader (facts, claims, policies, gaps) + rules engine (`if` / `when` conditions, verdicts Proceed / Caution / Refer to underwriter / Not eligible, market `tier` and `lines`) |
| `ars.py`, `ars_ui.py` | **ARS entry** page (client panel link): reads the newest DASH **and MVR** in the folder (either alone works): driver card from the MVR (name, birth, licence #, class, G1 / G2 / G dates), Convictions form (conviction date, description, Minor / Major / Serious; older than 3 years = don't enter; MVR licence actions = suspensions), claims, insurance history, lapses with **months**; "Copy all as text" covers all of it. DASH -> ARS Claims form per claim (Date MM/DD/YYYY, Description dropdown value from coverage / KOL codes, Vehicle, Chargeable, TP/BI / TP/PD / AB / Coll / Other PD = losses only; DCPD KOL16+18 go in Other PD) with Copy buttons; claims over 6 years listed as "don't enter"; insurance history (prior insurer, first insured, continuous since, lapses from `*POSSIBLE GAP*`, cancellations). `eligibility.read_dash_facts` claim details carry `kols`, `claim_no`, `vehicle`, `vehicle_loss` |
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
- **Everything in one window (owner's request): no separate windows.** Three views (Clients /
  Tracker / Rules) switched by `App.show_view`; every "dialog" subclasses `panel.Panel` (not
  `CTkToplevel`) and opens as a page over the view with a ← Back bar; pages stack; switching views
  closes them. Short forms set `FORM = True` (centred, scroll when the window is short); pages with
  their own scrolling must not. Only the tiny date picker (`CalendarPopup`) is still a popup.
- Background threads must not touch widgets: use `app.ui(func, *args)` (a queue drained every
  200 ms) or `after()` polling. Slow work (OCR, PDF reading) runs in a thread.
- The main window must stay fast: the client list caches document counts by folder mtime and only
  repaints rows that changed. Avoid reading files per row on every refresh.
- Tk tag fonts in text boxes use **negative sizes (pixels)** to match CTk fonts.
- Main screen is two columns (list | client). Document rows show only the buttons that fit their state.
- Panels with their own scrolling (the client page's `CTkScrollableFrame`) flush Tk's pending layout on every
  change (`CTkScrollbar._draw` calls `update_idletasks`), so fewer / cheaper widget changes matter more than anything.
- GUI screenshots for checking layout: capture the app's own window with `PrintWindow` (window set to
  alpha 0 so nothing appears on the owner's screen) - never grab the screen.
- **Readability (owner found the client panel "crowded and not readable")**: Settings > Text size
  (`text_size`: Normal / Large / Extra large = `ctk.set_widget_scaling` 1.0 / 1.15 / 1.3, default
  Large); plain Tk widgets (client list rows) size their fonts by the same factor. Body text 14,
  labels 12-13, never below 12. **Red (PRIMARY) only for the one main action on a screen** (the
  next-step button, Save / Create draft); "check this" text is amber `WARN`, not red; selected tabs
  are neutral `RAISED`. Each stage page holds only its own buttons (no long toolbar).
- An **empty CTkFrame is 200 px tall**: give containers that may be empty `height=1`, or
  `grid_remove()` them (this caused big gaps on the client panel and the Email page).
- Keep screens simple: the owner found a long flat list of checks "too complicated". Pattern that
  works: one verdict line at the top, short grouped items, details folded away (click to open).

## Performance rules (the owner found the app laggy; these made it smooth - keep them)

- **The window thread never reads client files.** Anything per client comes from a thread:
  the list line from `_compute_row` (via `_need_rows`, results posted with `app.ui`), the client page
  from `_gather` (via `_start_gather` / `_gathered`; PDFs are read there) and is drawn by
  `_render_details`, which only reads the finished bundle. The first draw uses the last bundle
  (`_bundles`) if there is one. `app.ui` queue is polled every 40 ms.
- **One directory listing, never `glob` per pattern** (`folder_files`, `find_docs`, `review.find_docs`,
  `scan_clients` use `os.scandir`; names are matched in memory with `fnmatch`). No per-client `stat`
  when the list is drawn: the Clients-folder scan already carries each folder's modified time, and that
  time is the cache key for the list line. So **every save into a client folder must be atomic**
  (temp file + `os.replace`, as `records._write`, `mvr_email.save_client` do) - that is what changes
  the folder's time.
- **Typing / filtering only redraws** (`refresh_soon(..., rescan=False)`). A change to one client calls
  `client_changed(folder)` (that client's line + page only). Full re-scans of the Clients folder happen at
  start-up, after Settings, on window focus (at most every 8 s), F5, new client and rename.
- **In render code use `self._set(widget, ...)` and `self._show(widget, visible)`** instead of
  `configure()` / `grid()`: every CTk configure redraws the widget, and the client page has ~150 of them.
  `font()` is memoized (one CTkFont per size / weight). Switching stage pages re-renders from the same bundle
  and reads nothing.
- `_prewarm` builds and draws every client type's pages off-screen at start-up (one type per 0.9 s): CTk's own `place()`
  refuses width / height, so it calls `tk.Place.place_configure` on the scroll frame's outer frame; a failure there once
  left pages showing, so the `finally` always `grid_remove()`s them to match what `_show()` believes.
- Heavy libraries load on first use (`_plumber()`, `_pypdf()`, `_pdfium()` in `fill_consent`, `ocr`,
  `eligibility`, `client_facts`, `mvr_watch`): keep imports of pdfplumber / pypdf / pypdfium2 out of
  module level (PyInstaller still finds imports inside functions). `_prewarm` draws the client page once,
  off-screen, shortly after start so the first click is quick; `sys.setswitchinterval(0.002)` lets the window
  run while a thread parses a PDF.
- The Tracker reloads only when it is showing (it also loads each time it is opened).
- To measure: count `os.scandir` / `open` calls and time `select` / `_pick_stage` / typing with a few hundred
  dummy client folders (the shared drive makes each file call slow, so call counts matter more than the
  local milliseconds).

## Domain rules built into the code (don't "fix" these)

- **`Quote (ARS)` never matches** a file with "application", "supplement" or "questionnaire" in its name (`Commercial Quote Application.pdf` is the application, not the quote).
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
