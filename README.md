# Client Intake

Windows desktop app for setting up a new insurance client.

- Creates the client's folder inside your **Clients** folder, under its type:
  `Clients\Auto`, `Clients\Home`, `Clients\Tenant` or `Clients\Commercial` (type folders are
  created when first needed; names can be changed in **Settings > Client types**)
- Client list shows every type with **All / Auto / Home / Tenant / Commercial** filters;
  older folders kept directly in Clients show as **Other**
- Fills WellCare's **Personal Information Client Consent Form** (client's name, date, and the other
  drivers from the DASH reports if there are any). **No DASH report is needed**: the form is filled as
  soon as the client is created, and **Fill consent** fills one for any client that has none.
- Names are saved in CAPITALS; an Ontario licence # is required
- Copies the licence # to the clipboard, ready to paste into DASH
- Shows which documents each client already has: Consent, DASH, Quote, MVR
- **MVR auto-save**: when the branch manager replies, click Download on the MVR in Outlook.
  While the app is open it spots the MVR in Downloads, matches it to the client by the
  licence # printed on it (or the name), and moves it to that client's folder as
  `MVR - NAME.pdf`. Only PDFs that look like an MVR are touched; DASH reports, consent forms
  and quotes are ignored. Turn off in Settings.
- **Import DASH from Downloads**: moves the client's DASH report(s) from Downloads into
  their folder (matching names pre-ticked) and refills the consent form
- Refills the consent form from saved DASH reports (up to 3 drivers)
- **Email client…**: ready-made client emails, opened as an Outlook draft with your signature:
  - Quote requests: Auto, Homeowner, Tenant, Auto + Home, Auto + Tenant
  - Quote accepted (documents & coverage choices): Auto, Home, Tenant, Auto + Home, Auto + Tenant
  - Policy confirmations: Auto, Home, Tenant, Auto + Home, Auto + Tenant
  - Auto pink card
- **Request MVR**: opens an Outlook draft to the branch manager with the client's
  details and the DASH, consent and Quote Information PDFs attached. You review and send.

## Clients screen

- Left: the client list (search, type filter) and **+ New client** (Ctrl+N), which opens a small
  window: type, name, licence #, phone, email.
- Right: the selected client - name, type, phone / email / licence (click to edit), documents with a
  progress bar (each row shows only what you can do: Open, Add…, Fill, Import, Request, Not needed),
  and the actions.
- **Edit** (or click a contact detail): change the name, type, licence #, phone or email. If the name
  or type changes, the window shows what follows: the folder is renamed / moved, files named after
  the client can be renamed (e.g. `Ownership - OLD NAME.jpg`), and the consent form can be refilled
  with the new name. Reports from outside (DASH, MVR, quote) are never changed inside.

## Checklist (Auto clients)

The selected Auto client shows the process step by step, with the next step highlighted:

1. Client profile (name, licence #; phone / email can follow - shown in red until added)
2. DASH report (N/A for a client with no insurance history)
3. First quote in ARS
4. MVR request sent (the branch manager's email is set in Settings)
5. MVR received
6. Quote corrected and re-run (Review quote shows what's wrong)
7. Documents from the client: ownership, void cheque, winter tire photos, bill of sale, financing papers
8. Client approved; quote exported to PowerBroker
9. Policy set up in PowerBroker
10. Application created in PowerBroker (REMARKS from UW-Compass pasted in)
11. Application filled and submitted on UW-Compass
12. Referred to head office / insurer if UW-Compass shows a refer message (N/A otherwise)

Steps 1-5 and 7 tick themselves from the folder and the client's details; the others you tick.
Ticks are saved in the client's `tracking.json` (everyone on the shared folder sees them), and the
client list shows each client's step (`Step 5/12`) and any missing phone / email.

## Client records & Tracker

- **Client record…** (on each client): tabs for **Policies** (line, status, insurer, policy #,
  effective/expiry, premium, payment plan, monthly amount, payment method/day, coverage notes),
  **Vehicles**, **Property**, **Business**, **Activity notes** (dated file notes for E&O) and
  **Reminders**. Expiry defaults to effective + 1 year; monthly payment to premium / 12.
- **Tracker** (top bar): every client at once.
  - **To do**: your reminders plus automatic ones - renewals 45 days ahead (or expired),
    quote follow-ups after 7 days, bound auto policies with no vehicle details. Red = due now.
  - **Policies**: all policies with status / line / month filters and premium totals.
- Saved per client in `tracking.json` inside the client folder, so everyone using the shared
  Clients folder sees the same records. Each save re-reads the file and changes only that one
  record, and every record shows who added / edited it.

## Rules (search the underwriting notes)

- **Rules** (top bar): type a question or a few words (`intact G2 at-fault`, `pembridge oil tank`,
  `echelon monthly payment`) and the matching rules show as you type, best section first, with
  the words highlighted. Click a result's title to open that note.
- Searches the notes folder (`.md` files; default `Documents\Docs\Insurance\Underwriting Knowledge`,
  change it with **Notes folder…**; **Reload notes** after editing them). On another computer,
  copy that folder there or to the shared drive and point **Notes folder…** at it.
- Free and offline: no AI, no account, no internet. A carrier name in the question puts that
  carrier's notes first; common words have synonyms (ticket → conviction, bike → motorcycle).
- Notes are a summary: check the carrier manual before quoting exact rates or binding.

## Review quote & eligibility

- **Review quote & eligibility…** (on each client): reads the **DASH report**, the **MVR** and the
  Applied Rating **Quote Information** PDF in the client folder (pick another file, or "(none)").
  Any of them can be missing: no DASH = no insurance history (treated as a new driver).
- The window opens with one verdict (Fix the quote / Refer before binding / Check with the client /
  Looks good), then the items grouped under **Fix in the quote**, **Refer / get approval** and
  **Check with the client**; carrier to-dos, notes and what matches are folded away (click to open).
- **What is checked** - licence number, birth date, class; G1 / G2 / G dates (when the
  MVR expiry is on the birthday, the issue date is G1, +1 year G2, +1 year G - only for the class
  held); MVR convictions missing from the quote (conviction date, not offence date); DASH claims
  missing or charged wrongly; DASH gaps not shown as lapses; date first insured; postal codes;
  every carrier message on the quote (Refer ones first); WellCare's quote rules (km, deductibles,
  OPCF 20 / 28 / 39 / 43, high value, liability only on a new car, lienholder papers).
- **Markets that fit by the rules** - standard markets first (Intact), then non-standard (Jevco),
  and which of them aren't on the quote yet. **Result by market** shows each market's reasons.
- The MVR is read with Windows' built-in OCR (no internet). Convictions are classed minor / major /
  serious from the Intact / Jevco lists and fill in the conviction counts; the licence class is
  shown so you can correct it.
- At-fault claims count only when this driver was at the wheel (DASH's own rule); others are
  listed under **Worth a look**.
- Driving-record rules only: vehicle and use rules still need the manual. **Create my rules file…**
  copies the rules to a file you can edit (and share on the shared drive).

## Install on a computer without Python (work / remote desktop)

1. Download **ClientIntake-windows.zip** from
   [brokerclientintake-releases](https://github.com/imstudioinc/brokerclientintake-releases/releases/latest) (no login needed).
2. Unzip it somewhere permanent, e.g. `Documents\ClientIntake`. Keep the `_internal`
   folder next to `ClientIntake.exe`.
3. Double-click **ClientIntake.exe**. The first run adds a desktop shortcut and asks
   for your Clients folder. Nothing is installed and no admin rights are needed.

If Windows shows "Windows protected your PC", click **More info > Run anyway**.
If your IT blocks unsigned programs, ask them to allow `ClientIntake.exe`.

**Updates install themselves.** When a new version is published, the app shows
**Update now** at the top; one click downloads it and restarts. Settings and client
files are kept (settings live in `%APPDATA%\ClientIntake`).

Troubleshooting: `ClientIntake.exe --selftest` writes `%TEMP%\ClientIntake-selftest.txt`.

## Install with Python (development)

1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/).
   During setup, tick **"Add python.exe to PATH"**.
2. Download this repo: **Code → Download ZIP** and unzip it somewhere permanent
   (e.g. `Documents\ClientIntake`), or `git clone https://github.com/imstudioinc/brokerclientintake`.
3. Double-click **install.bat**. It installs the packages and adds a
   **Client Intake** shortcut to the desktop and Start menu.
4. Open the app and choose your Clients folder.

## Email (Request MVR)

Works with **New Outlook** (default) or **Classic Outlook**: choose in **Settings > Email app**.
Set the branch manager's email (To / CC) in **Settings** first.

- **New Outlook**: the app saves `MVR Request - <NAME>.eml` in the client folder and opens it
  in New Outlook as a draft with the attachments and your email signature
  (set it once in **Settings > Email signature…**). Review it, then Send.
- **Classic Outlook**: the draft opens directly with your default signature. Needs your work
  account added in Classic Outlook (File > Add Account).

## Update

- Cloned with git: double-click **update.bat**.
- Downloaded as ZIP: download the new ZIP, unzip over the old folder, run **install.bat**.

## Email templates

Templates live in `templates/emails/` (shared blocks in `templates/emails/_blocks/`).
In the app, **Email client… > Edit this template** makes your own copy in
`%APPDATA%\ClientIntake\emails` and opens it; your copy is used from then on.
Placeholders like `{insurer}` listed on the template's `fields:` line are asked for in the
app and remembered per client (e.g. the policy number is reused for the pink card email).
Every draft is also saved in the client's `Emails` folder as a record.

## Settings

Click **Settings** in the app to change the Clients folder, the consent form
template, the MVR request recipients (To / CC), or light/dark mode. Settings are saved per computer in
`%APPDATA%\ClientIntake\config.json`.

## File names the app recognises

| Document | File name starts with / contains |
|---|---|
| Consent | contains `Client Consent` or `Consent Form` (e.g. `Consent Form - NAME.pdf`) |
| DASH | `DASH Report…` (the DASH portal's default name) |
| Quote | contains `Quote` (e.g. `Quote Information.pdf`) |
| MVR | contains `MVR` |

Consent, DASH, quote and MVR count as received whether they are a PDF or a photo (jpg, png, heic…).
The review reads an MVR photo / screenshot with OCR (zoom the page in before the screenshot); DASH and
quote are read from their PDFs.

**Auto clients** also need these (photos or PDFs). **Add…** on each row copies the file into the
client folder with the standard name; **N/A** marks one as not needed for this client (saved in the
client's `tracking.json`, so everyone sees it).

| Document | File name contains | Added as |
|---|---|---|
| Driver's licence | `licence` / `license` | `Driver Licence - NAME.jpg` |
| Ownership | `ownership`, `registration` or `permit` | `Ownership - NAME.pdf` |
| Bill of sale (N/A possible) | `bill of sale` | `Bill of Sale - NAME.pdf` |
| Winter tire photo (N/A possible) | `winter`, `tire` or `tyre` | `Winter Tires - NAME.jpg` |
| Void cheque (N/A possible - only for pre-authorized monthly payments) | `void`, `cheque`, `direct deposit` or `PAD form` | `Void Cheque - NAME.jpg` |
| Financing / lease (N/A possible) | `financ`, `lease` (as a word), `loan`, `lienholder` | `Financing Papers - NAME.pdf` |

## Privacy

This repo holds code and the blank consent template only. Client files stay in
your Clients folder and are never committed (see `.gitignore`).
The **Rules** tab searches the notes on this computer; nothing is sent anywhere.

## Publishing an update

On the computer with Python and this repo, double-click **release.bat**, enter the
new version (e.g. `1.0.1`) and a one-line note. It bumps `version.py`, builds the exe,
commits, tags, and publishes the zip to
[brokerclientintake-releases](https://github.com/imstudioinc/brokerclientintake-releases).
Installed apps offer the update the next time they open.

`build.bat` alone only builds `release\ClientIntake` and the zip, without publishing.

## Sample clients

**Settings > Try with sample clients** builds a separate sample folder
(`Documents\Client Intake sample\Clients`) with Auto, Home, Tenant and Commercial clients and
policies, and switches to it so you can try the Tracker. **Back to my Clients folder** returns
to your real folder; real clients are never touched.
