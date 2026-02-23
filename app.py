from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import font as tkfont, messagebox, ttk
from uuid import uuid4

import customtkinter as ctk
from PIL import Image

from pdf_generator import build_invoice_pdf
from storage import (
    delete_profile,
    load_history,
    load_profiles,
    load_settings,
    record_invoice_history,
    save_profile,
    save_settings,
    upsert_profile,
)

BASE_DIR = Path(__file__).resolve().parent
INVOICES_DIR = BASE_DIR / "invoices"
DONATION_QR_PATH = BASE_DIR / "QR.png"
WEBSITE_URL = "https://moorearcanum.com/"

PAYMENT_TYPE_LABELS = {
    "bank_domestic": "Domestic bank",
    "bank_international": "International bank",
    "paypal": "PayPal",
}

FIELD_DEFAULT_KEYS = {
    "service_category": "service_category",
    "service_title": "service_title",
    "client_reference": "student_name",
    "rate_per_hour": "rate_per_hour",
    "session_hours": "session_duration_hours",
    "extra_hours": "prep_hours",
    "session_start": "session_start",
    "terms": "terms_label",
    "due_days": "due_days",
    "currency": "currency",
    "extra_description": "prep_description",
    "open_on_generate": "open_on_generate",
}

TOOLTIPS = {
    "Provider": "Your business or personal profile shown as the invoice sender.",
    "Recipient": "The person or company receiving this invoice.",
    "Payment type": "Choose domestic bank transfer, international bank transfer, or PayPal.",
    "Payment profile": "Saved payout details used on this invoice.",
    "Service category": "Broad category for this work, e.g. Consulting or Design.",
    "Service title": "Specific short description of the service you are charging for.",
    "Client reference (optional)": "Optional reference code/name for the client or project.",
    "Rate per hour": "Your billable hourly rate for this invoice.",
    "Session/work hours": "Total billable hours to charge.",
    "Extra hours (not billed)": "Optional non-billed hours shown for context.",
    "Session start (YYYY-MM-DD HH:MM)": "Date and time of the service/session start.",
    "Terms label": "Payment terms label shown on invoice (e.g. Net 14).",
    "Due days": "Number of days after invoice date until payment is due.",
    "Currency": "Currency code used in amounts and payment section.",
    "Extra work description": "Additional context or notes for non-billed prep/admin.",
    "Open invoice after generation": "If enabled, opens the PDF immediately after creation.",
}

SUBWINDOW_TOOLTIPS = {
    "Name": "Display name used in dropdowns and invoice output.",
    "Address (comma-separated)": "Use commas to split address lines.",
    "Email": "Contact email shown on invoices.",
    "Client reference": "Optional code/name to identify client in your records.",
    "Profile label": "Friendly name for this saved payment profile.",
    "Account holder": "Name on the bank account.",
    "Bank name": "Financial institution name.",
    "Sort code (optional)": "Domestic routing code (if used in your country).",
    "Account number (optional)": "Domestic account number.",
    "IBAN": "International Bank Account Number used for cross-border transfers.",
    "BIC/SWIFT (optional)": "SWIFT/BIC identifier for international transfers.",
    "PayPal email": "PayPal account email that should receive payment.",
    "PayPal link": "Optional PayPal.Me or checkout link.",
    "Currency": "Currency code for this payment profile.",
}


def slugify(value: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in value).strip("-") or "recipient"


def open_file(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def float_steps(start: float, end: float, step: float) -> list[str]:
    values: list[str] = []
    current = start
    while current <= end + 1e-9:
        values.append(f"{current:.2f}".rstrip("0").rstrip("."))
        current += step
    return values


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None):
        if self.tip_window is not None:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#111111",
            foreground="#e9eef4",
            relief="solid",
            borderwidth=1,
            font=("Verdana", 10),
            padx=8,
            pady=6,
            wraplength=380,
        )
        lbl.pack()

    def hide(self, _event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class InvoiceApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Invoice Generator")
        self.geometry("1340x920")
        self.minsize(980, 740)

        self.settings = load_settings()
        self.profiles = self._normalize_loaded_profiles(load_profiles())

        self.provider_var = tk.StringVar()
        self.recipient_var = tk.StringVar()
        self.payment_type_var = tk.StringVar(value="bank_domestic")
        self.payment_var = tk.StringVar()

        defaults = self.settings.get("field_defaults", {})
        self.service_category_var = tk.StringVar(value=defaults.get("service_category", "Consulting"))
        self.service_title_var = tk.StringVar(value=defaults.get("service_title", "Professional service"))
        self.student_name_var = tk.StringVar(value=defaults.get("student_name", ""))
        self.rate_var = tk.StringVar(value=str(defaults.get("rate_per_hour", "75")))
        self.duration_var = tk.StringVar(value=str(defaults.get("session_duration_hours", "1.0")))
        self.prep_hours_var = tk.StringVar(value=str(defaults.get("prep_hours", "0.0")))
        self.prep_description_var = tk.StringVar(value=defaults.get("prep_description", "Preparation and admin (not billed)."))
        self.session_start_var = tk.StringVar(value=defaults.get("session_start", dt.datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.terms_var = tk.StringVar(value=defaults.get("terms_label", "Net 7"))
        self.due_days_var = tk.StringVar(value=str(defaults.get("due_days", "7")))
        self.currency_var = tk.StringVar(value=defaults.get("currency", "GBP"))
        self.open_on_generate_var = tk.BooleanVar(value=bool(defaults.get("open_on_generate", False)))

        self.history_cards: list[ctk.CTkFrame] = []
        self.donation_qr_image: ctk.CTkImage | None = None
        self.tooltips: list[Tooltip] = []

        self._setup_accessible_fonts_and_inputs()

        self._build_ui()
        self._load_defaults()
        self._refresh_history()
        self.after(120, self._maximize_window)

    def _normalize_loaded_profiles(self, profiles: dict) -> dict:
        for p in profiles.get("payment_method", []):
            if p.get("method_type") == "bank_transfer":
                details = p.get("details", {})
                p["method_type"] = "bank_international" if details.get("iban") else "bank_domestic"
        return profiles

    def _setup_accessible_fonts_and_inputs(self) -> None:
        base_font = tkfont.nametofont("TkDefaultFont")
        base_font.configure(family="Verdana", size=12)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "TCombobox",
            fieldbackground="#000000",
            background="#000000",
            foreground="#f0f2f4",
            bordercolor="#323232",
            lightcolor="#323232",
            darkcolor="#323232",
            arrowcolor="#f0f2f4",
            insertcolor="#f0f2f4",
            padding=4,
            font=("Verdana", 11),
        )

    def _style_button(self, parent, text: str, *, kind: str = "primary", width: int = 90, command=None):
        palette = {
            "primary": {"fg": "#1f6fb2", "hover": "#2a89d5"},
            "add": {"fg": "#4ca663", "hover": "#5fc77a"},
            "danger": {"fg": "#b33a3a", "hover": "#d34a4a"},
            "muted": {"fg": "#3c4a57", "hover": "#516274"},
        }
        c = palette[kind]
        return ctk.CTkButton(parent, text=text, width=width, fg_color=c["fg"], hover_color=c["hover"], command=command)

    def _maximize_window(self) -> None:
        try:
            if sys.platform.startswith("win"):
                self.state("zoomed")
            elif sys.platform == "darwin":
                self.geometry("1460x940")
            else:
                self.attributes("-zoomed", True)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=4, minsize=640)
        self.grid_columnconfigure(1, weight=1, minsize=320)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, corner_radius=12)
        right = ctk.CTkFrame(self, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(14, 7), pady=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 14), pady=14)
        left.grid_columnconfigure(1, weight=1, minsize=300)
        left.grid_columnconfigure(2, minsize=196)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        row = 0
        row = self._profile_row(left, row, "Provider", self.provider_var, "provider")
        row = self._profile_row(left, row, "Recipient", self.recipient_var, "recipient")

        lbl_payment_type = ctk.CTkLabel(left, text="Payment type")
        lbl_payment_type.grid(row=row, column=0, sticky="w", padx=10, pady=8)
        self._attach_tooltip(lbl_payment_type, TOOLTIPS["Payment type"])
        payment_frame = ctk.CTkFrame(left, fg_color="transparent")
        payment_frame.grid(row=row, column=1, sticky="w", padx=10)
        rb_dom = ctk.CTkRadioButton(payment_frame, text="Domestic bank", variable=self.payment_type_var, value="bank_domestic", command=self._on_payment_type_changed)
        rb_int = ctk.CTkRadioButton(payment_frame, text="International bank", variable=self.payment_type_var, value="bank_international", command=self._on_payment_type_changed)
        rb_paypal = ctk.CTkRadioButton(payment_frame, text="PayPal", variable=self.payment_type_var, value="paypal", command=self._on_payment_type_changed)
        rb_dom.pack(side=tk.LEFT, padx=(0, 10))
        rb_int.pack(side=tk.LEFT, padx=(0, 10))
        rb_paypal.pack(side=tk.LEFT)
        self._attach_tooltip(rb_dom, "Domestic transfer with local bank details; no IBAN required.")
        self._attach_tooltip(rb_int, "International transfer with IBAN/BIC details.")
        self._attach_tooltip(rb_paypal, "PayPal payment option.")
        row += 1

        row = self._profile_row(left, row, "Payment profile", self.payment_var, "payment_method")

        category_values = ["Consulting", "Tutoring", "Design", "Development", "Coaching", "Maintenance", "Admin support"]
        terms_values = ["Due on receipt", "Net 7", "Net 14", "Net 30"]
        currency_values = ["GBP", "EUR", "USD"]

        row = self._field_row(left, row, "Service category", self.service_category_var, "service_category", values=category_values)
        row = self._field_row(left, row, "Service title", self.service_title_var, "service_title")
        row = self._field_row(left, row, "Client reference (optional)", self.student_name_var, "client_reference")
        row = self._field_row(left, row, "Rate per hour", self.rate_var, "rate_per_hour", values=[str(v) for v in range(20, 151, 5)])
        row = self._field_row(left, row, "Session/work hours", self.duration_var, "session_hours", values=float_steps(0.25, 12.0, 0.25))
        row = self._field_row(left, row, "Extra hours (not billed)", self.prep_hours_var, "extra_hours", values=float_steps(0.0, 8.0, 0.25))
        row = self._field_row(left, row, "Session start (YYYY-MM-DD HH:MM)", self.session_start_var, "session_start")
        row = self._field_row(left, row, "Terms label", self.terms_var, "terms", values=terms_values)
        row = self._field_row(left, row, "Due days", self.due_days_var, "due_days", values=["7", "14", "30"])
        row = self._field_row(left, row, "Currency", self.currency_var, "currency", values=currency_values)

        lbl_extra = ctk.CTkLabel(left, text="Extra work description")
        lbl_extra.grid(row=row, column=0, sticky="nw", padx=10, pady=8)
        self._attach_tooltip(lbl_extra, TOOLTIPS["Extra work description"])
        self.prep_text = ctk.CTkTextbox(left, height=120, fg_color="#000000", text_color="#f0f2f4", border_color="#323232", border_width=1)
        self.prep_text.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        self.prep_text.insert("1.0", self.prep_description_var.get())
        self._attach_tooltip(self.prep_text, TOOLTIPS["Extra work description"])
        self._style_button(left, "Set default", kind="muted", width=90, command=lambda: self._set_default("extra_description", self.prep_text.get("1.0", "end").strip())).grid(row=row, column=2, padx=10, pady=8)

        row += 1
        chk_open = ctk.CTkCheckBox(left, text="Open invoice after generation", variable=self.open_on_generate_var)
        chk_open.grid(row=row, column=1, sticky="w", padx=10, pady=6)
        self._attach_tooltip(chk_open, TOOLTIPS["Open invoice after generation"])
        self._style_button(left, "Set default", kind="muted", width=90, command=lambda: self._set_default("open_on_generate", self.open_on_generate_var.get())).grid(row=row, column=2, padx=10, pady=6)

        row += 1
        self._style_button(left, "Generate Invoice PDF", kind="primary", width=220, command=self._generate_invoice).grid(row=row, column=0, columnspan=3, pady=20, padx=10, sticky="ew")

        ctk.CTkLabel(right, text="Recent invoices", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.history_frame = ctk.CTkScrollableFrame(right, corner_radius=10)
        self.history_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)

        donate_frame = ctk.CTkFrame(right)
        donate_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 10))
        donate_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(donate_frame, text="If this app is useful, buy me a coffee (£5) ☕", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=1, sticky="w", padx=10, pady=(10, 0))
        ctk.CTkLabel(donate_frame, text="Scan the QR code to support development.", text_color=("gray35", "gray70")).grid(row=1, column=1, sticky="w", padx=10, pady=(0, 8))

        if DONATION_QR_PATH.exists():
            self.donation_qr_image = ctk.CTkImage(light_image=Image.open(DONATION_QR_PATH), dark_image=Image.open(DONATION_QR_PATH), size=(96, 96))
            label = ctk.CTkLabel(donate_frame, text="", image=self.donation_qr_image)
            label.grid(row=0, column=0, rowspan=3, padx=10, pady=10)
            label.bind("<Button-1>", lambda _e: open_file(DONATION_QR_PATH))
            self._style_button(donate_frame, "Open QR image", kind="primary", width=120, command=lambda: open_file(DONATION_QR_PATH)).grid(row=2, column=1, sticky="w", padx=10, pady=(0, 6))
        else:
            ctk.CTkLabel(donate_frame, text="QR.png not found in project root.", text_color=("gray45", "gray70")).grid(row=2, column=1, sticky="w", padx=10, pady=(0, 6))

        self._style_button(donate_frame, "Visit my website", kind="primary", width=140, command=self._open_website).grid(row=3, column=1, sticky="w", padx=10, pady=(0, 10))

        self._style_button(right, "Open invoices folder", kind="primary", width=150, command=self._open_invoices_folder).grid(row=3, column=0, sticky="w", padx=10, pady=(0, 10))

    def _profile_row(self, parent, row: int, label: str, var: tk.StringVar, profile_type: str) -> int:
        lbl = ctk.CTkLabel(parent, text=label)
        lbl.grid(row=row, column=0, sticky="w", padx=10, pady=8)
        self._attach_tooltip(lbl, TOOLTIPS[label])

        combo = ttk.Combobox(parent, textvariable=var, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        self._attach_tooltip(combo, TOOLTIPS[label])

        if profile_type == "provider":
            self.provider_combo = combo
        elif profile_type == "recipient":
            self.recipient_combo = combo
        else:
            self.payment_combo = combo

        self._profile_actions(parent, row, profile_type)
        return row + 1

    def _profile_actions(self, parent, row: int, profile_type: str) -> None:
        action = ctk.CTkFrame(parent, fg_color="transparent")
        action.grid(row=row, column=2, padx=8, pady=6, sticky="e")
        action.grid_columnconfigure((0, 1), weight=1)

        add_btn = self._style_button(action, "Add", kind="add", width=88, command=lambda t=profile_type: self._add_profile_dialog(t))
        edit_btn = self._style_button(action, "Edit", kind="primary", width=88, command=lambda t=profile_type: self._edit_profile_dialog(t))
        del_btn = self._style_button(action, "Delete", kind="danger", width=88, command=lambda t=profile_type: self._delete_profile(t))
        def_btn = self._style_button(action, "Set default", kind="muted", width=88, command=lambda t=profile_type: self._set_default_profile(t))

        add_btn.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        edit_btn.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        del_btn.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        def_btn.grid(row=1, column=1, padx=2, pady=2, sticky="ew")

        self._attach_tooltip(add_btn, f"Create a new {profile_type.replace('_', ' ')} profile.")
        self._attach_tooltip(edit_btn, f"Edit selected {profile_type.replace('_', ' ')} profile.")
        self._attach_tooltip(del_btn, f"Delete selected {profile_type.replace('_', ' ')} profile.")
        self._attach_tooltip(def_btn, f"Use selected {profile_type.replace('_', ' ')} as default.")

    def _field_row(self, parent, row: int, label: str, var: tk.StringVar, key: str, values: list[str] | None = None) -> int:
        lbl = ctk.CTkLabel(parent, text=label)
        lbl.grid(row=row, column=0, sticky="w", padx=10, pady=8)
        self._attach_tooltip(lbl, TOOLTIPS[label])

        if values:
            widget = ttk.Combobox(parent, textvariable=var, values=values, state="normal", width=34)
            widget.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        else:
            widget = ctk.CTkEntry(parent, textvariable=var, height=34, fg_color="#000000", text_color="#f0f2f4", border_color="#323232", border_width=1)
            widget.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        self._attach_tooltip(widget, TOOLTIPS[label])

        self._style_button(parent, "Set default", kind="muted", width=90, command=lambda k=key, v=var: self._set_default(k, v.get())).grid(row=row, column=2, padx=10, pady=8)
        return row + 1

    def _attach_tooltip(self, widget, text: str) -> None:
        self.tooltips.append(Tooltip(widget, text))

    def _reload_combos(self) -> None:
        self.provider_combo["values"] = [p["display_name"] for p in self.profiles.get("provider", [])]
        self.recipient_combo["values"] = [r["display_name"] for r in self.profiles.get("recipient", [])]
        self._reload_payment_combo()

    def _load_defaults(self) -> None:
        self._reload_combos()
        selected = self.settings.get("selected_profiles", {})
        self._select_combo_by_id("provider", selected.get("provider_id"), self.provider_var)
        self._select_combo_by_id("recipient", selected.get("recipient_id"), self.recipient_var)

        default_payment_type = selected.get("payment_type")
        if default_payment_type in set(PAYMENT_TYPE_LABELS):
            self.payment_type_var.set(default_payment_type)
        self._reload_payment_combo()
        self._select_combo_by_id("payment_method", selected.get("payment_method_id"), self.payment_var)

    def _select_combo_by_id(self, profile_type: str, profile_id: str | None, target_var: tk.StringVar) -> None:
        items = self.profiles.get(profile_type, [])
        if not items:
            target_var.set("")
            return
        match = next((i for i in items if i.get("id") == profile_id), items[0])
        target_var.set(match.get("display_name") or match.get("label") or "")

    def _reload_payment_combo(self) -> None:
        method = self.payment_type_var.get()
        payments = [p for p in self.profiles.get("payment_method", []) if p.get("method_type") == method]
        self.payment_combo["values"] = [p.get("label", p["id"]) for p in payments]
        if self.payment_var.get() not in self.payment_combo["values"]:
            self.payment_var.set(self.payment_combo["values"][0] if self.payment_combo["values"] else "")

    def _on_payment_type_changed(self) -> None:
        self._reload_payment_combo()

    def _find_profile(self, type_name: str, display: str) -> dict:
        for item in self.profiles.get(type_name, []):
            key = item.get("display_name") or item.get("label")
            if key == display:
                return item
        raise ValueError(f"{type_name} profile not found: {display}")

    def _set_default_profile(self, profile_type: str) -> None:
        try:
            selected_profiles = self.settings.setdefault("selected_profiles", {})
            if profile_type == "provider":
                selected_profiles["provider_id"] = self._find_profile("provider", self.provider_var.get())["id"]
            elif profile_type == "recipient":
                selected_profiles["recipient_id"] = self._find_profile("recipient", self.recipient_var.get())["id"]
            else:
                selected_profiles["payment_method_id"] = self._find_profile("payment_method", self.payment_var.get())["id"]
                selected_profiles["payment_type"] = self.payment_type_var.get()
            save_settings(self.settings)
            messagebox.showinfo("Saved", "Default profile saved.")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _set_default(self, field_key: str, value: object) -> None:
        model_key = FIELD_DEFAULT_KEYS[field_key]
        self.settings.setdefault("field_defaults", {})[model_key] = value
        save_settings(self.settings)
        messagebox.showinfo("Saved", f"Default set for {field_key.replace('_', ' ')}")

    def _generate_invoice(self) -> None:
        try:
            provider = self._find_profile("provider", self.provider_var.get())
            recipient = self._find_profile("recipient", self.recipient_var.get())
            payment = self._find_profile("payment_method", self.payment_var.get())

            session_start = dt.datetime.strptime(self.session_start_var.get().strip(), "%Y-%m-%d %H:%M")
            invoice_date = dt.date.today()
            due_days = int(self.due_days_var.get().strip())

            recipient_slug = slugify(recipient["display_name"])
            year = str(invoice_date.year)
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            invoice_number = f"INV-{invoice_date.strftime('%Y%m%d')}-{timestamp[-4:]}"
            out_path = INVOICES_DIR / recipient_slug / year / f"{invoice_number}.pdf"

            invoice = {
                "provider": provider,
                "recipient": recipient,
                "payment_method": payment,
                "service_category": self.service_category_var.get().strip() or "General",
                "service_title": self.service_title_var.get().strip() or "Professional service",
                "student_name": self.student_name_var.get().strip() or recipient.get("student_name", ""),
                "rate_per_hour": float(self.rate_var.get().strip()),
                "session_duration_hours": float(self.duration_var.get().strip()),
                "prep_hours": float(self.prep_hours_var.get().strip()),
                "prep_description": self.prep_text.get("1.0", "end").strip(),
                "session_start": session_start,
                "invoice_date": invoice_date,
                "terms_label": self.terms_var.get().strip() or "Net 7",
                "due_days": due_days,
                "currency": self.currency_var.get().strip() or "GBP",
                "invoice_number": invoice_number,
            }
            build_invoice_pdf(invoice, out_path)

            record_invoice_history(
                {
                    "invoice_number": invoice_number,
                    "recipient": recipient["display_name"],
                    "recipient_id": recipient["id"],
                    "service_category": invoice["service_category"],
                    "output_path": str(out_path),
                    "created_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "payment_method": payment.get("method_type", "bank_domestic"),
                }
            )
            self._refresh_history()
            if self.open_on_generate_var.get():
                open_file(out_path)
            messagebox.showinfo("Success", f"Invoice saved:\n{out_path}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _refresh_history(self) -> None:
        for card in self.history_cards:
            card.destroy()
        self.history_cards.clear()

        entries = load_history(limit=25)
        for idx, entry in enumerate(entries, start=1):
            bubble = ctk.CTkFrame(self.history_frame, corner_radius=14)
            bubble.pack(fill="x", padx=8, pady=6)

            top = f"#{idx}  {entry.get('invoice_number', '')}"
            subtitle = f"{entry.get('recipient', 'Unknown')} • {entry.get('created_at', '')}"
            path = entry.get("output_path", "")

            ctk.CTkLabel(bubble, text=top, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(bubble, text=subtitle).pack(anchor="w", padx=10)
            ctk.CTkLabel(bubble, text=path, text_color=("gray35", "gray70"), wraplength=420, justify="left").pack(anchor="w", padx=10, pady=(0, 8))

            for widget in bubble.winfo_children():
                widget.bind("<Double-Button-1>", lambda _e, p=path: self._open_invoice_from_history(p))
            bubble.bind("<Double-Button-1>", lambda _e, p=path: self._open_invoice_from_history(p))
            self.history_cards.append(bubble)

    def _open_invoice_from_history(self, raw_path: str) -> None:
        p = Path(raw_path)
        if not p.exists():
            messagebox.showwarning("Missing file", f"File not found:\n{p}")
            return
        open_file(p)

    def _simple_record_dialog(self, title: str, fields: list[tuple[str, str]], initial: dict | None = None) -> dict | None:
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.grab_set()
        dialog.attributes("-topmost", True)

        vars_map: dict[str, tk.StringVar] = {}
        for i, (key, label) in enumerate(fields):
            lbl = ctk.CTkLabel(dialog, text=label)
            lbl.grid(row=i, column=0, sticky="w", padx=8, pady=6)
            self._attach_tooltip(lbl, SUBWINDOW_TOOLTIPS.get(label, f"Input for {label.lower()}."))
            var = tk.StringVar(value=(initial or {}).get(key, ""))
            vars_map[key] = var
            ent = ctk.CTkEntry(dialog, textvariable=var, width=360, fg_color="#000000", text_color="#f0f2f4", border_color="#323232", border_width=1)
            ent.grid(row=i, column=1, padx=8, pady=6)
            self._attach_tooltip(ent, SUBWINDOW_TOOLTIPS.get(label, f"Input for {label.lower()}."))

        result = {}

        def submit() -> None:
            for key in vars_map:
                result[key] = vars_map[key].get().strip()
            dialog.destroy()

        self._style_button(dialog, "Save", kind="primary", width=120, command=submit).grid(row=len(fields), column=0, columnspan=2, pady=8)
        self.wait_window(dialog)
        return result or None

    def _profile_current(self, profile_type: str) -> dict | None:
        try:
            if profile_type == "provider":
                return self._find_profile("provider", self.provider_var.get())
            if profile_type == "recipient":
                return self._find_profile("recipient", self.recipient_var.get())
            return self._find_profile("payment_method", self.payment_var.get())
        except Exception:
            return None

    def _add_profile_dialog(self, profile_type: str) -> None:
        if profile_type == "provider":
            fields = [("display_name", "Name"), ("address", "Address (comma-separated)"), ("email", "Email")]
            result = self._simple_record_dialog("Add provider", fields)
            if not result:
                return
            record = {
                "type": "provider",
                "id": f"provider-{uuid4().hex[:8]}",
                "display_name": result["display_name"],
                "address_lines": [x.strip() for x in result["address"].split(",") if x.strip()],
                "email": result["email"],
            }
        elif profile_type == "recipient":
            fields = [("display_name", "Name"), ("address", "Address (comma-separated)"), ("email", "Email"), ("student_name", "Client reference")]
            result = self._simple_record_dialog("Add recipient", fields)
            if not result:
                return
            record = {
                "type": "recipient",
                "id": f"recipient-{uuid4().hex[:8]}",
                "display_name": result["display_name"],
                "address_lines": [x.strip() for x in result["address"].split(",") if x.strip()],
                "email": result["email"],
                "student_name": result["student_name"],
            }
        else:
            method = self.payment_type_var.get()
            if method == "paypal":
                fields = [("label", "Profile label"), ("paypal_email", "PayPal email"), ("paypal_link", "PayPal link"), ("currency", "Currency")]
            elif method == "bank_international":
                fields = [
                    ("label", "Profile label"),
                    ("account_holder", "Account holder"),
                    ("bank_name", "Bank name"),
                    ("iban", "IBAN"),
                    ("bic", "BIC/SWIFT (optional)"),
                    ("currency", "Currency"),
                ]
            else:
                fields = [
                    ("label", "Profile label"),
                    ("account_holder", "Account holder"),
                    ("bank_name", "Bank name"),
                    ("sort_code", "Sort code (optional)"),
                    ("account_number", "Account number (optional)"),
                    ("currency", "Currency"),
                ]
            result = self._simple_record_dialog("Add payment method", fields)
            if not result:
                return
            details = {k: v for k, v in result.items() if k != "label"}
            if not details.get("currency"):
                details["currency"] = "GBP"
            record = {
                "type": "payment_method",
                "id": f"payment-{uuid4().hex[:8]}",
                "label": result["label"] or f"{PAYMENT_TYPE_LABELS.get(method, method)} profile",
                "method_type": method,
                "details": details,
            }

        save_profile(record)
        self.profiles = self._normalize_loaded_profiles(load_profiles())
        self._load_defaults()
        self._select_record(profile_type, record)

    def _edit_profile_dialog(self, profile_type: str) -> None:
        current = self._profile_current(profile_type)
        if not current:
            messagebox.showwarning("No selection", "Please select a profile first.")
            return

        if profile_type == "provider":
            fields = [("display_name", "Name"), ("address", "Address (comma-separated)"), ("email", "Email")]
            initial = {
                "display_name": current.get("display_name", ""),
                "address": ", ".join(current.get("address_lines", [])),
                "email": current.get("email", ""),
            }
            result = self._simple_record_dialog("Edit provider", fields, initial)
            if not result:
                return
            current.update({"display_name": result["display_name"], "address_lines": [x.strip() for x in result["address"].split(",") if x.strip()], "email": result["email"]})
        elif profile_type == "recipient":
            fields = [("display_name", "Name"), ("address", "Address (comma-separated)"), ("email", "Email"), ("student_name", "Client reference")]
            initial = {
                "display_name": current.get("display_name", ""),
                "address": ", ".join(current.get("address_lines", [])),
                "email": current.get("email", ""),
                "student_name": current.get("student_name", ""),
            }
            result = self._simple_record_dialog("Edit recipient", fields, initial)
            if not result:
                return
            current.update({"display_name": result["display_name"], "address_lines": [x.strip() for x in result["address"].split(",") if x.strip()], "email": result["email"], "student_name": result["student_name"]})
        else:
            method = current.get("method_type", "bank_domestic")
            details = current.get("details", {})
            if method == "paypal":
                fields = [("label", "Profile label"), ("paypal_email", "PayPal email"), ("paypal_link", "PayPal link"), ("currency", "Currency")]
                initial = {"label": current.get("label", ""), "paypal_email": details.get("paypal_email", ""), "paypal_link": details.get("paypal_link", ""), "currency": details.get("currency", "GBP")}
            elif method == "bank_international":
                fields = [
                    ("label", "Profile label"),
                    ("account_holder", "Account holder"),
                    ("bank_name", "Bank name"),
                    ("iban", "IBAN"),
                    ("bic", "BIC/SWIFT (optional)"),
                    ("currency", "Currency"),
                ]
                initial = {
                    "label": current.get("label", ""),
                    "account_holder": details.get("account_holder", ""),
                    "bank_name": details.get("bank_name", ""),
                    "iban": details.get("iban", ""),
                    "bic": details.get("bic", ""),
                    "currency": details.get("currency", "GBP"),
                }
            else:
                fields = [
                    ("label", "Profile label"),
                    ("account_holder", "Account holder"),
                    ("bank_name", "Bank name"),
                    ("sort_code", "Sort code (optional)"),
                    ("account_number", "Account number (optional)"),
                    ("currency", "Currency"),
                ]
                initial = {
                    "label": current.get("label", ""),
                    "account_holder": details.get("account_holder", ""),
                    "bank_name": details.get("bank_name", ""),
                    "sort_code": details.get("sort_code", ""),
                    "account_number": details.get("account_number", ""),
                    "currency": details.get("currency", "GBP"),
                }
            result = self._simple_record_dialog("Edit payment method", fields, initial)
            if not result:
                return
            current["label"] = result["label"]
            current["details"] = {k: v for k, v in result.items() if k != "label"}

        upsert_profile(current)
        self.profiles = self._normalize_loaded_profiles(load_profiles())
        self._load_defaults()
        self._select_record(profile_type, current)

    def _delete_profile(self, profile_type: str) -> None:
        current = self._profile_current(profile_type)
        if not current:
            messagebox.showwarning("No selection", "Please select a profile first.")
            return

        name = current.get("display_name") or current.get("label") or current["id"]
        if not messagebox.askyesno("Delete", f"Delete profile '{name}'?"):
            return

        delete_profile(current["id"], profile_type)
        self.profiles = self._normalize_loaded_profiles(load_profiles())
        self._load_defaults()

    def _select_record(self, profile_type: str, record: dict) -> None:
        key = record.get("display_name") or record.get("label") or ""
        if profile_type == "provider":
            self.provider_var.set(key)
        elif profile_type == "recipient":
            self.recipient_var.set(key)
        else:
            self.payment_type_var.set(record.get("method_type", "bank_domestic"))
            self._reload_payment_combo()
            self.payment_var.set(key)

    def _open_website(self) -> None:
        webbrowser.open(WEBSITE_URL)

    def _open_invoices_folder(self) -> None:
        INVOICES_DIR.mkdir(parents=True, exist_ok=True)
        open_file(INVOICES_DIR)


if __name__ == "__main__":
    app = InvoiceApp()
    app.mainloop()
