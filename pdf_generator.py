from __future__ import annotations

import datetime as dt
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


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
    if value is None:
        return []
    if isinstance(value, str):
        return [] if value.strip() == "" else [value.strip()]
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]


def safe_para(text: str, style: ParagraphStyle) -> Paragraph:
    s = escape(str(text) if text is not None else "")
    for k, v in {
        "&lt;b&gt;": "<b>",
        "&lt;/b&gt;": "</b>",
        "&lt;br/&gt;": "<br/>",
        "&lt;br&gt;": "<br/>",
    }.items():
        s = s.replace(k, v)
    s = s.replace("\n", "<br/>")
    return Paragraph(s, style)


def payment_rows(payment_method: dict, reference: str, currency: str) -> list[list[str]]:
    method_type = payment_method.get("method_type", "bank_transfer")
    details = payment_method.get("details", {})
    rows = [["Payment method", payment_method.get("label", method_type.title())], ["Payment currency", details.get("currency", currency)]]
    if method_type == "paypal":
        rows += [
            ["PayPal email", details.get("paypal_email", "")],
            ["PayPal link", details.get("paypal_link", "")],
            ["Reference", reference],
        ]
    else:
        rows += [
            ["Account holder", details.get("account_holder", "")],
            ["Bank", details.get("bank_name", "")],
            ["Sort code", details.get("sort_code", "")],
            ["Account number", details.get("account_number", "")],
            ["IBAN", details.get("iban", "")],
            ["BIC/SWIFT", details.get("bic", "")],
            ["Reference", reference],
        ]
    return rows


def build_invoice_pdf(invoice: dict, output_path: Path) -> Path:
    session_start: dt.datetime = invoice["session_start"]
    session_duration_hours = float(invoice["session_duration_hours"])
    session_end = session_start + dt.timedelta(hours=session_duration_hours)

    invoice_date: dt.date = invoice["invoice_date"]
    due_days = int(invoice.get("due_days", 7))
    due_date = invoice_date + dt.timedelta(days=due_days)
    invoice_number = invoice["invoice_number"]

    provider = invoice["provider"]
    recipient = invoice["recipient"]
    student_name = invoice.get("student_name", "")

    label = student_name if student_name.strip() else recipient.get("display_name", "Client")
    reference = invoice.get("reference") or f"Tut-{initials(label)}-{session_start.strftime('%d%m%y')}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title = ParagraphStyle(name="Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=6)
    normal = ParagraphStyle(name="Normal", parent=styles["Normal"], fontName="Helvetica", fontSize=11, leading=14)
    small = ParagraphStyle(name="Small", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=colors.black)
    bold = ParagraphStyle(name="Bold", parent=normal, fontName="Helvetica-Bold")
    right = ParagraphStyle(name="Right", parent=normal, alignment=TA_RIGHT)
    wrap = ParagraphStyle(name="Wrap", parent=normal, wordWrap="CJK")
    wrap_small = ParagraphStyle(name="WrapSmall", parent=small, wordWrap="CJK")

    doc = SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    story = [Paragraph("INVOICE", title), Spacer(1, 6)]

    from_lines = [f"<b>{provider['display_name']}</b>"] + normalise_lines(provider.get("address_lines", ""))
    if (provider.get("email") or "").strip():
        from_lines.append(provider["email"].strip())

    bill_lines = ["<b>Bill To:</b>", recipient["display_name"]] + normalise_lines(recipient.get("address_lines", ""))
    if (recipient.get("email") or "").strip():
        bill_lines.append(recipient["email"].strip())

    hdr = Table([[safe_para("\n".join(from_lines), small), safe_para("\n".join(bill_lines), small)]], colWidths=[92 * mm, 78 * mm])
    hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [hdr, Spacer(1, 10)]

    currency = invoice.get("currency", "GBP")
    service_category = invoice.get("service_category", "General")
    service_title = invoice.get("service_title", "Professional service")
    prep_hours = float(invoice.get("prep_hours", 0.0))
    prep_description = invoice.get("prep_description", "Preparation (not billed)")
    rate = float(invoice.get("rate_per_hour", 0.0))
    prep_rate = float(invoice.get("prep_rate", 0.0))
    billed = session_duration_hours * rate

    session_label = f"{fmt_date(session_start.date())}  {fmt_time(session_start)}–{fmt_time(session_end)}"
    meta = Table(
        [["Invoice #", invoice_number, "Invoice date", fmt_date(invoice_date)], ["Terms", invoice.get("terms_label", "Net 7"), "Due date", fmt_date(due_date)], ["Service type", service_category, "Session", session_label], ["Client reference", student_name or "-", "", ""]],
        colWidths=[24 * mm, 62 * mm, 24 * mm, 60 * mm],
    )
    meta.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke), ("BOX", (0, 0), (-1, -1), 0.5, colors.grey), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 10)]))
    story += [meta, Spacer(1, 12)]

    col_desc, col_qty, col_rate, col_amt = 95 * mm, 20 * mm, 25 * mm, 30 * mm
    items = [
        [safe_para("<b>Description</b>", wrap), safe_para("<b>Hours</b>", right), safe_para(f"<b>Rate ({currency})</b>", right), safe_para(f"<b>Amount ({currency})</b>", right)],
        [safe_para(f"{service_title}\nSession date/time: {session_label}", wrap), safe_para(f"{session_duration_hours:.2f}", right), safe_para(money(rate), right), safe_para(money(billed), right)],
        [safe_para(f"Preparation (not billed): {prep_hours:.2f} hours\n{prep_description}", wrap_small), safe_para(f"{prep_hours:.2f}", right), safe_para(money(prep_rate), right), safe_para(money(0.00), right)],
    ]
    li = Table(items, colWidths=[col_desc, col_qty, col_rate, col_amt], repeatRows=1)
    li.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("BOX", (0, 0), (-1, -1), 0.5, colors.grey), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
    story += [li, Spacer(1, 10)]

    totals = Table([["", safe_para("<b>Subtotal</b>", right), safe_para(money(billed), right)], ["", safe_para("<b>Total</b>", right), safe_para(money(billed), right)]], colWidths=[col_desc + col_qty, col_rate, col_amt])
    totals.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("LINEABOVE", (1, 0), (2, 0), 0.5, colors.black), ("LINEBELOW", (1, 1), (2, 1), 1.0, colors.black)]))
    story += [totals, Spacer(1, 14), safe_para("<b>Payment details</b>", bold)]

    pay_rows = payment_rows(invoice["payment_method"], reference, currency)
    pd_table = Table([[safe_para(k, small), safe_para(v, wrap_small)] for k, v in pay_rows], colWidths=[48 * mm, 122 * mm])
    pd_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.grey), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]))
    story += [pd_table, Spacer(1, 10), safe_para("Thank you. Please use the payment reference shown above.", wrap_small)]

    doc.build(story)
    return output_path
