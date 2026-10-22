# Client Intake

Windows desktop app for setting up a new insurance client.

- Creates the client's folder inside your **Clients** folder, under its type:
  `Clients\Auto`, `Clients\Home`, `Clients\Tenant` or `Clients\Commercial` (type folders are
  created when first needed; names can be changed in **Settings > Client types**)
- Client list shows every type with **All / Auto / Home / Tenant / Commercial** filters;
  older folders kept directly in Clients show as **Other**
- Fills the **Client Consent** form (name, date, driver and licence #)
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
| Consent | `Client Consent…` |
| DASH | `DASH Report…` (the DASH portal's default name) |
| Quote | contains `Quote` (e.g. `Quote Information.pdf`) |
| MVR | contains `MVR` |

## Privacy

This repo holds code and the blank consent template only. Client files stay in
your Clients folder and are never committed (see `.gitignore`).

## Publishing an update

On the computer with Python and this repo, double-click **release.bat**, enter the
new version (e.g. `1.0.1`) and a one-line note. It bumps `version.py`, builds the exe,
commits, tags, and publishes the zip to
[brokerclientintake-releases](https://github.com/imstudioinc/brokerclientintake-releases).
Installed apps offer the update the next time they open.

`build.bat` alone only builds `release\ClientIntake` and the zip, without publishing.
