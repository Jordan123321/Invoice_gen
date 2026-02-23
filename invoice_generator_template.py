#!/usr/bin/env python3
"""
Public template: tutoring/service invoice generator (ReportLab).

✅ No personal data included. Replace the placeholders under GLOBAL CONFIG.

Usage:
    python invoice_generator_template.py [output_filename.pdf]

Dependencies:
    pip install reportlab
"""

import sys
import datetime as dt
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib import colors


# ============================================================
# GLOBAL CONFIG (PLACEHOLDERS — EDIT THESE)
# ============================================================

# --- Parties ---
PROVIDER = {
    "display_name": "Your Company Ltd",            # e.g. "MooreArcanum Limited"
    "address_lines": ["Address line 1", "Town/City, POSTCODE", "United Kingdom"],  # optional
    "email": "your.email@example.com",             # optional
}

CLIENT = {
    "display_name": "Client Name",                 # e.g. parent/guardian or company
    "address_lines": "",                           # optional: "" or ["Line 1", ...]
    "email": "",                                   # optional
}

STUDENT_NAME = "Student Name"                      # optional label (can be "")

# --- Session / work ---
SERVICE_TITLE = "Tutoring session (Topic)"
SESSION_START = dt.datetime(2026, 2, 21, 10, 0)       # YYYY, M, D, H, M
SESSION_DURATION_HOURS = 1.0                          # auto-computes SESSION_END
PREP_HOURS = 1.0                                      # shown but not billed
PREP_DESCRIPTION = "Preparation (not billed): reviewing questions and drafting notes."

# --- Pricing ---
CURRENCY = "GBP"
RATE_PER_HOUR = 75.00
PREP_RATE = 0.00                                      # keep at 0.00 to show effort only

# --- Invoice terms ---
INVOICE_DATE = dt.date.today()                        # auto: today
TERMS_LABEL = "Net 7"
DUE_DAYS = 7                                          # Net 7
INVOICE_PREFIX = "TUT"                              # used for invoice number

# --- Payment details (placeholders) ---
PAYMENT = {
    "currency": "GBP",
    "account_holder": "Your Company Ltd",
    "bank_name": "Your Bank",
    "sort_code": "00-00-00",
    "account_number": "00000000",
    # Set to None to auto-generate (e.g. "Tut-SN-210226"), or hardcode a reference string
    "reference": None,
}

# ============================================================
# Helpers
# ============================================================

def initials(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "XX"
    return "".join(p[0].upper() for p in parts[:2])

def fmt_date(d: dt.date) -> str:
    return d.strftime("%d-%m-%Y")

def fmt_time(t: dt.datetime) -> str:
    return t.strftime("%H:%M")

def money(x: float) -> str:
    return f"{x:,.2f}"

def normalise_lines(value):
    """Normalise optional address/email inputs."""
    if value is None:
        return []
    if isinstance(value, str):
        return [] if value.strip() == "" else [value.strip()]
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]

def safe_para(text: str, style: ParagraphStyle) -> Paragraph:
    """
    Escape user text but allow a tiny safe subset of tags: <b>, </b>, <br/>.
    Prevents '<b>' showing verbatim while still blocking arbitrary HTML.
    """
    if text is None:
        text = ""
    s = escape(str(text))
    for k, v in {
        "&lt;b&gt;": "<b>",
        "&lt;/b&gt;": "</b>",
        "&lt;br/&gt;": "<br/>",
        "&lt;br&gt;": "<br/>",
    }.items():
        s = s.replace(k, v)
    s = s.replace("\n", "<br/>")
    return Paragraph(s, style)


# ============================================================
# Build invoice
# ============================================================

def build_invoice(output_path: str) -> None:
    session_end = SESSION_START + dt.timedelta(hours=float(SESSION_DURATION_HOURS))
    due_date = INVOICE_DATE + dt.timedelta(days=int(DUE_DAYS))

    # Simple invoice number; for production, consider a persistent incrementing sequence.
    invoice_number = f"{INVOICE_PREFIX}-{INVOICE_DATE.strftime('%Y%m%d')}-01"

    # Default payment reference
    ref = PAYMENT.get("reference")
    if not ref:
        label = STUDENT_NAME if STUDENT_NAME.strip() else CLIENT["display_name"]
        ref = f"Tut-{initials(label)}-{SESSION_START.strftime('%d%m%y')}"

    # Default filename if none provided
    if not output_path:
        safe_label = (STUDENT_NAME or "Client").replace(" ", "")
        output_path = f"Invoice_{safe_label}_{INVOICE_DATE.isoformat()}.pdf"

    # Styles
    styles = getSampleStyleSheet()
    Title = ParagraphStyle(
        name="Title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        spaceAfter=6,
    )
    Normal = ParagraphStyle(
        name="Normal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
    )
    Small = ParagraphStyle(
        name="Small",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.black,
    )
    Bold = ParagraphStyle(
        name="Bold",
        parent=Normal,
        fontName="Helvetica-Bold",
    )
    Right = ParagraphStyle(
        name="Right",
        parent=Normal,
        alignment=TA_RIGHT,
    )
    Wrap = ParagraphStyle(
        name="Wrap",
        parent=Normal,
        wordWrap="CJK",
    )
    WrapSmall = ParagraphStyle(
        name="WrapSmall",
        parent=Small,
        wordWrap="CJK",
    )

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    story = []
    story.append(Paragraph("INVOICE", Title))
    story.append(Spacer(1, 6))

    # Header blocks
    from_lines = [f"<b>{PROVIDER['display_name']}</b>"]
    from_lines += normalise_lines(PROVIDER.get("address_lines", ""))
    if (PROVIDER.get("email") or "").strip():
        from_lines.append(PROVIDER["email"].strip())

    billto_lines = ["<b>Bill To:</b>", CLIENT["display_name"]]
    billto_lines += normalise_lines(CLIENT.get("address_lines", ""))
    if (CLIENT.get("email") or "").strip():
        billto_lines.append(CLIENT["email"].strip())

    hdr = Table(
        [[safe_para("\n".join(from_lines), Small), safe_para("\n".join(billto_lines), Small)]],
        colWidths=[92 * mm, 78 * mm],
    )
    hdr.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(hdr)
    story.append(Spacer(1, 10))

    # Meta
    session_label = f"{fmt_date(SESSION_START.date())}  {fmt_time(SESSION_START)}–{fmt_time(session_end)}"
    meta_rows = [
        ["Invoice #", invoice_number, "Invoice date", fmt_date(INVOICE_DATE)],
        ["Terms", TERMS_LABEL, "Due date", fmt_date(due_date)],
        ["Student", STUDENT_NAME or "-", "Session", session_label],
    ]
    meta = Table(meta_rows, colWidths=[24 * mm, 62 * mm, 24 * mm, 60 * mm])
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(meta)
    story.append(Spacer(1, 12))

    # Line items
    hours = float(SESSION_DURATION_HOURS)
    billed_amount = hours * float(RATE_PER_HOUR)

    col_desc, col_qty, col_rate, col_amt = 95 * mm, 20 * mm, 25 * mm, 30 * mm
    items = [
        [
            safe_para("<b>Description</b>", Wrap),
            safe_para("<b>Hours</b>", Right),
            safe_para(f"<b>Rate ({CURRENCY})</b>", Right),
            safe_para(f"<b>Amount ({CURRENCY})</b>", Right),
        ],
        [
            safe_para(f"{SERVICE_TITLE}\nSession date/time: {session_label}", Wrap),
            safe_para(f"{hours:.2f}", Right),
            safe_para(money(RATE_PER_HOUR), Right),
            safe_para(money(billed_amount), Right),
        ],
        [
            safe_para(f"Preparation (not billed): {float(PREP_HOURS):.2f} hours\n{PREP_DESCRIPTION}", WrapSmall),
            safe_para(f"{float(PREP_HOURS):.2f}", Right),
            safe_para(money(PREP_RATE), Right),
            safe_para(money(0.00), Right),
        ],
    ]

    li = Table(items, colWidths=[col_desc, col_qty, col_rate, col_amt], repeatRows=1)
    li.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(li)
    story.append(Spacer(1, 10))

    # Totals
    subtotal = billed_amount
    total = subtotal

    tot = Table(
        [
            ["", safe_para("<b>Subtotal</b>", Right), safe_para(money(subtotal), Right)],
            ["", safe_para("<b>Total</b>", Right), safe_para(money(total), Right)],
        ],
        colWidths=[col_desc + col_qty, col_rate, col_amt],
    )
    tot.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("LINEABOVE", (1, 0), (2, 0), 0.5, colors.black),
                ("LINEBELOW", (1, 1), (2, 1), 1.0, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(tot)
    story.append(Spacer(1, 14))

    # Payment details
    story.append(safe_para("<b>Payment details</b>", Bold))
    payment_rows = [
        ["Payment currency", PAYMENT.get("currency", CURRENCY)],
        ["Account holder", PAYMENT.get("account_holder", "")],
        ["Bank", PAYMENT.get("bank_name", "")],
        ["Sort code", PAYMENT.get("sort_code", "")],
        ["Account number", PAYMENT.get("account_number", "")],
        ["Reference", ref],
    ]
    pd_table = Table(
        [[safe_para(k, Small), safe_para(v, WrapSmall)] for k, v in payment_rows],
        colWidths=[48 * mm, 122 * mm],
    )
    pd_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(pd_table)
    story.append(Spacer(1, 10))

    story.append(safe_para("Thank you. Please use the payment reference shown above.", WrapSmall))

    doc.build(story)
    print(f"Invoice saved: {output_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else ""
    build_invoice(out)
