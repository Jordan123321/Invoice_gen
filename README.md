# Invoice_gen Desktop App

Simple modern desktop invoice generator for non-technical users.

## What it does

- Loads saved profiles from JSONL files.
- Uses dropdowns for provider and recipient.
- Uses 3 payment radio options:
  - Domestic bank transfer
  - International bank transfer
  - PayPal
- International payments support IBAN and BIC/SWIFT; domestic bank profiles are intentionally simpler (no IBAN required).
- Uses generalized service fields (service category + service title), not tutoring-only wording.
- Add, edit, delete, and set default provider/recipient/payment profiles.
- "Set default" buttons for invoice form fields (for example rate per hour).
- Tickbox to optionally open the generated PDF immediately (default off).
- Invoice date field defaults to today and supports calendar/date picker shortcuts (Today, Yesterday, Tomorrow, absolute date).
- Session start also supports calendar-based date selection while preserving time.
- Recent invoices shown as numbered bubble cards; double-click a card to open the PDF in the default viewer.
- Recent invoices include in-app actions: Open, Delete file, Remove from list, plus a Refresh button to resync if files are removed manually during a session.
- Rate/hour fields support both: typing custom values and choosing useful dropdown values.
  - Rate per hour suggestions: every £5 from 20 to 150.
  - Hours suggestions: every 0.25 increment.
- Dark, unified input style (black input backgrounds for text and dropdown inputs).
- Improved readability styling and hover tooltips on main form + profile dialogs.
- Donation panel in the app with caption + QR support (`QR.png` in repo root) and website link.
- Generates invoice PDFs grouped by recipient folder.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The app uses `tkcalendar` for date-picking widgets.

## Data files

Committed seed data (safe fake defaults):

- `data/seed_profiles.jsonl`

Local private files (ignored by git):

- `data/profiles.local.jsonl`
- `data/history.local.jsonl`
- `data/defaults.local.json`

Generated invoices:

- `invoices/<recipient>/<year>/<invoice-number>.pdf`

## Donation QR

- Add `QR.png` at the project root.
- The app will show it in the donation panel with a caption:
  - **"If this app is useful, buy me a coffee (£5) ☕"**
- Includes a **Visit my website** button linking to `https://moorearcanum.com/`.

## Packaging a Windows EXE

```bash
pip install pyinstaller
pyinstaller --name InvoiceApp --onefile --windowed app.py
```

The executable will be available in `dist/InvoiceApp.exe`.

## Packaging a macOS app

Run this on macOS:

```bash
pip install pyinstaller
pyinstaller --name InvoiceApp --windowed app.py
```

The app bundle will be available at `dist/InvoiceApp.app`.
