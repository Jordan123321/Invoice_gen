# Invoice_gen (v1.0)

A desktop invoice generator focused on speed, repeatability, and clean PDF output for solo professionals and small service businesses.

> ✅ **Status:** v1.0 is now generated successfully.

## Download

- **Latest release (recommended):**
  - Windows `.exe`, macOS package, Linux build artifacts:  
    `https://github.com/jordan123321/Invoice_gen/releases/latest`
- **Build pipeline page (if you want CI artifacts from a run):**  
  `https://github.com/jordan123321/Invoice_gen/actions`

> Tip: Use **Releases** for stable downloads. Use **Actions artifacts** for testing/preview builds.

---

## Why this app exists

Invoice_gen is designed for people who need to create professional invoices quickly without maintaining complicated accounting software.

It emphasizes:
- reusable profile data,
- fast invoice form entry,
- practical date controls,
- and a straightforward output/history workflow.

---

## Key features

### Profiles & defaults
- Provider, recipient, and payment profiles stored locally.
- Add, edit, delete, and set defaults for common selections.
- Form-level “Set default” actions for repeat invoice fields.

### Smart invoice date controls
- Relative and absolute invoice date modes.
- Relative picker includes quick offsets from **-7 to +7**.
- Relative display style is semantic + explicit date (example: `yesterday (2026-02-22)`).
- Absolute mode displays a fixed `YYYY-MM-DD` date.

### Session date/time
- Calendar picker plus explicit HH:MM selection.
- Quick “Use selected” flow for clean date confirmation.

### PDF output quality
- Clean invoice layout with sender/recipient, metadata, line items, totals, and payment details.
- Non-billed preparation line is automatically omitted if extra/prep hours are `0`.
- Files are saved under recipient/year folders for organization.

### History workflow
- Recent invoices shown as actionable cards.
- Card actions: Open, Delete file, Remove from list.
- Refresh resyncs against filesystem changes.
- History is constrained to:
  - last **14 days**, and
  - maximum **15 entries** displayed.

### UI & usability
- Dark-friendly input styling.
- Clear tooltips throughout primary form and profile dialogs.
- Optional auto-open PDF after generation.
- Optional donation panel with QR and website link.

---

## Project structure

- `app.py` — main desktop UI and workflow orchestration.
- `pdf_generator.py` — invoice PDF layout and render logic.
- `storage.py` — local data read/write for profiles/history/defaults.
- `invoice_generator_template.py` — invoice templating support file.
- `data/seed_profiles.jsonl` — versioned seed profile examples.
- `%APPDATA%/Invoice_gen/*` (Windows) or platform-equivalent app-data dir — user-local runtime data (profiles/history/defaults).
- `invoices/` — generated PDF output tree.

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Dependencies include `customtkinter`, `reportlab`, `Pillow`, and `tkcalendar`.

---

## Data and persistence

### Seed data (committed)
- `data/seed_profiles.jsonl`

### Local data (not committed)
Stored in the per-user app data folder (not the EXE temp extraction path):
- `profiles.local.jsonl`
- `history.local.jsonl`
- `defaults.local.json`

### Generated files
- `~/Documents/Invoice_gen/invoices/<recipient>/<year>/<invoice-number>.pdf`

---

## Donations (optional)

This software is free to use.

If it helps you, optional support is welcome:
- place `QR.png` in one of these locations (first match wins):
  1. user app-data folder (`.../Invoice_gen/QR.png`)
  2. next to the executable
  3. bundled in the EXE via PyInstaller `--add-data`
- use the in-app website link (`https://moorearcanum.com/`).

---

## Licensing summary

This repository uses a **custom license** (see [`LICENSE`](./LICENSE)).

In plain language:
- You may use, copy, and modify this software for free.
- Donations are optional.
- If you want to sell this software, bundle it into paid software/services, or use it in a commercial paid offering, you must obtain prior written permission and agree royalty terms with the author.

For exact terms, read the full license text.

---

## Packaging notes

### Windows EXE (onefile, with bundled seed data + QR + startup splash)
```bash
pip install pyinstaller
pyinstaller --name InvoiceApp --onefile --windowed \
  --splash "Loading.png" \
  --add-data "data/seed_profiles.jsonl;data" \
  --add-data "QR.png;." \
  app.py
```

### macOS app bundle
```bash
pip install pyinstaller
pyinstaller --name InvoiceApp --windowed \
  --add-data "data/seed_profiles.jsonl:data" \
  --add-data "QR.png:." \
  app.py
```

> Note: PyInstaller splash support is primarily used for onefile startup UX on Windows.

Outputs appear under `dist/`. For reproducible builds, use `InvoiceApp.spec`.

---

## How to use (quick wiki)

### 1) First launch setup
1. Open the app.
2. Add at least one **Provider** profile.
3. Add at least one **Recipient** profile.
4. Add at least one **Payment profile** (Domestic/International/PayPal).

### 2) Generate your first invoice
1. Select Provider, Recipient, and Payment profile.
2. Fill service details (category/title/hours/rate).
3. Choose session date/time.
4. Choose invoice date mode:
   - **Relative** (today ± offset), or
   - **Absolute** (fixed date).
5. Click **Generate Invoice PDF**.

### 3) Find output files
- PDFs are saved under:  
  `~/Documents/Invoice_gen/invoices/<recipient>/<year>/...`

### 4) Use history panel
- Use **Open** to view PDF.
- Use **Delete file** to delete disk file + remove from list.
- Use **Remove from list** to keep disk file but remove history entry.
- Use **Refresh** to resync with filesystem.

### 5) Defaults and persistence
- “Set default” buttons save your preferred values.
- Profiles/history/defaults persist in platform app-data (not temp extraction folders).

### 6) Donation QR behavior
`QR.png` is resolved in this order:
1. user app-data folder
2. next to executable
3. bundled asset
4. project root (source mode)
