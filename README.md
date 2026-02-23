# Invoice_gen Desktop App

Simple desktop invoice generator for non-technical users.

## What it does

- Loads saved profiles from JSONL files.
- Uses dropdowns for provider and recipient.
- Lets you switch payment method with radio buttons (Bank transfer / PayPal).
- Generates invoice PDFs grouped by recipient folder.
- Shows recent invoices grouped by recipient.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Data files

Committed seed data (safe fake defaults):

- `data/seed_profiles.jsonl`

Local private files (ignored by git):

- `data/profiles.local.jsonl`
- `data/history.local.jsonl`

Generated invoices:

- `invoices/<recipient>/<year>/<invoice-number>.pdf`

## Packaging a Windows EXE

```bash
pip install pyinstaller
pyinstaller --name InvoiceApp --onefile --windowed app.py
```

The executable will be available in `dist/InvoiceApp.exe`.

## Notes

- The app reuses ReportLab for PDF generation.
- Fake test profiles include a Joe Bloggs style setup.
- Real PII stays in local ignored files.
