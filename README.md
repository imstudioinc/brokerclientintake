# Client Intake

Windows desktop app for setting up a new insurance client.

- Creates the client's folder inside your **Clients** folder
- Fills the **Client Consent** form (name, date, driver and licence #)
- Copies the licence # to the clipboard, ready to paste into DASH
- Shows which documents each client already has: Consent, DASH, Quote, MVR
- Refills the consent form from saved DASH reports (up to 3 drivers)

## Install

1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/).
   During setup, tick **"Add python.exe to PATH"**.
2. Download this repo: **Code → Download ZIP** and unzip it somewhere permanent
   (e.g. `Documents\ClientIntake`), or `git clone https://github.com/imstudioinc/brokerclientintake`.
3. Double-click **install.bat**. It installs the packages and adds a
   **Client Intake** shortcut to the desktop and Start menu.
4. Open the app and choose your Clients folder.

## Update

- Cloned with git: double-click **update.bat**.
- Downloaded as ZIP: download the new ZIP, unzip over the old folder, run **install.bat**.

## Settings

Click **Settings** in the app to change the Clients folder, the consent form
template, or light/dark mode. Settings are saved per computer in
`%APPDATA%\ClientIntake\config.json`.

## File names the app recognises

| Document | File name starts with / contains |
|---|---|
| Consent | `Client Consent…` |
| DASH | `DASH Report…` (the DASH portal's default name) |
| Quote | contains `Quote` |
| MVR | contains `MVR` |

## Privacy

This repo holds code and the blank consent template only. Client files stay in
your Clients folder and are never committed (see `.gitignore`).
