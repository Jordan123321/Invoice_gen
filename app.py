from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
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


class InvoiceApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Invoice Generator")
        self.geometry("1320x900")
        self.minsize(1180, 820)

        self.settings = load_settings()
        self.profiles = load_profiles()

        self.provider_var = tk.StringVar()
        self.recipient_var = tk.StringVar()
        self.payment_type_var = tk.StringVar(value="bank_transfer")
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

        self._build_ui()
        self._load_defaults()
        self._refresh_history()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, corner_radius=12)
        right = ctk.CTkFrame(self, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(14, 7), pady=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 14), pady=14)
        left.grid_columnconfigure(1, weight=1)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        row = 0
        ctk.CTkLabel(left, text="Provider").grid(row=row, column=0, sticky="w", padx=10, pady=8)
        self.provider_combo = ttk.Combobox(left, textvariable=self.provider_var, state="readonly")
        self.provider_combo.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        self._profile_actions(left, row, "provider")

        row += 1
        ctk.CTkLabel(left, text="Recipient").grid(row=row, column=0, sticky="w", padx=10, pady=8)
        self.recipient_combo = ttk.Combobox(left, textvariable=self.recipient_var, state="readonly")
        self.recipient_combo.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        self._profile_actions(left, row, "recipient")

        row += 1
        ctk.CTkLabel(left, text="Payment type").grid(row=row, column=0, sticky="w", padx=10, pady=8)
        payment_frame = ctk.CTkFrame(left, fg_color="transparent")
        payment_frame.grid(row=row, column=1, sticky="w", padx=10)
        ctk.CTkRadioButton(payment_frame, text="Bank transfer", variable=self.payment_type_var, value="bank_transfer", command=self._on_payment_type_changed).pack(side=tk.LEFT, padx=(0, 12))
        ctk.CTkRadioButton(payment_frame, text="PayPal", variable=self.payment_type_var, value="paypal", command=self._on_payment_type_changed).pack(side=tk.LEFT)

        row += 1
        ctk.CTkLabel(left, text="Payment profile").grid(row=row, column=0, sticky="w", padx=10, pady=8)
        self.payment_combo = ttk.Combobox(left, textvariable=self.payment_var, state="readonly")
        self.payment_combo.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        self._profile_actions(left, row, "payment_method")

        category_values = ["Consulting", "Tutoring", "Design", "Development", "Coaching", "Maintenance", "Admin support"]
        terms_values = ["Due on receipt", "Net 7", "Net 14", "Net 30"]
        currency_values = ["GBP", "EUR", "USD"]

        row = self._field_row(left, row + 1, "Service category", self.service_category_var, "service_category", values=category_values)
        row = self._field_row(left, row, "Service title", self.service_title_var, "service_title")
        row = self._field_row(left, row, "Client reference (optional)", self.student_name_var, "client_reference")
        row = self._field_row(left, row, "Rate per hour", self.rate_var, "rate_per_hour", values=[str(v) for v in range(20, 151, 5)])
        row = self._field_row(left, row, "Session/work hours", self.duration_var, "session_hours", values=float_steps(0.25, 12.0, 0.25))
        row = self._field_row(left, row, "Extra hours (not billed)", self.prep_hours_var, "extra_hours", values=float_steps(0.0, 8.0, 0.25))
        row = self._field_row(left, row, "Session start (YYYY-MM-DD HH:MM)", self.session_start_var, "session_start")
        row = self._field_row(left, row, "Terms label", self.terms_var, "terms", values=terms_values)
        row = self._field_row(left, row, "Due days", self.due_days_var, "due_days", values=["7", "14", "30"])
        row = self._field_row(left, row, "Currency", self.currency_var, "currency", values=currency_values)

        ctk.CTkLabel(left, text="Extra work description").grid(row=row, column=0, sticky="nw", padx=10, pady=8)
        self.prep_text = ctk.CTkTextbox(left, height=120)
        self.prep_text.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        self.prep_text.insert("1.0", self.prep_description_var.get())
        ctk.CTkButton(left, text="Set default", width=90, command=lambda: self._set_default("extra_description", self.prep_text.get("1.0", "end").strip())).grid(row=row, column=2, padx=10, pady=8)

        row += 1
        ctk.CTkCheckBox(left, text="Open invoice after generation", variable=self.open_on_generate_var).grid(row=row, column=1, sticky="w", padx=10, pady=6)
        ctk.CTkButton(left, text="Set default", width=90, command=lambda: self._set_default("open_on_generate", self.open_on_generate_var.get())).grid(row=row, column=2, padx=10, pady=6)

        row += 1
        ctk.CTkButton(left, text="Generate Invoice PDF", height=44, command=self._generate_invoice).grid(row=row, column=0, columnspan=3, pady=20, padx=10, sticky="ew")

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
            ctk.CTkButton(donate_frame, text="Open QR image", width=120, command=lambda: open_file(DONATION_QR_PATH)).grid(row=2, column=1, sticky="w", padx=10, pady=(0, 10))
        else:
            ctk.CTkLabel(donate_frame, text="QR.png not found in project root.", text_color=("gray45", "gray70")).grid(row=2, column=1, sticky="w", padx=10, pady=(0, 10))

        ctk.CTkButton(right, text="Open invoices folder", command=self._open_invoices_folder).grid(row=3, column=0, sticky="w", padx=10, pady=(0, 10))

    def _profile_actions(self, parent: ctk.CTkBaseClass, row: int, profile_type: str) -> None:
        action = ctk.CTkFrame(parent, fg_color="transparent")
        action.grid(row=row, column=2, padx=10, pady=6, sticky="e")
        ctk.CTkButton(action, text="Add", width=52, command=lambda t=profile_type: self._add_profile_dialog(t)).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(action, text="Edit", width=52, command=lambda t=profile_type: self._edit_profile_dialog(t)).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(action, text="Delete", width=58, fg_color="#b33a3a", hover_color="#8f2d2d", command=lambda t=profile_type: self._delete_profile(t)).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(action, text="Set default", width=85, command=lambda t=profile_type: self._set_default_profile(t)).pack(side=tk.LEFT, padx=2)

    def _field_row(self, parent: ctk.CTkBaseClass, row: int, label: str, var: tk.StringVar, key: str, values: list[str] | None = None) -> int:
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=8)
        if values:
            widget = ttk.Combobox(parent, textvariable=var, values=values, state="normal")
            widget.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        else:
            ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=10, pady=8)
        ctk.CTkButton(parent, text="Set default", width=90, command=lambda k=key, v=var: self._set_default(k, v.get())).grid(row=row, column=2, padx=10, pady=8)
        return row + 1

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
        if default_payment_type in {"bank_transfer", "paypal"}:
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
                    "payment_method": payment.get("method_type", "bank_transfer"),
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
            ctk.CTkLabel(bubble, text=path, text_color=("gray35", "gray70"), wraplength=440, justify="left").pack(anchor="w", padx=10, pady=(0, 8))

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
            ctk.CTkLabel(dialog, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=6)
            var = tk.StringVar(value=(initial or {}).get(key, ""))
            vars_map[key] = var
            ctk.CTkEntry(dialog, textvariable=var, width=360).grid(row=i, column=1, padx=8, pady=6)

        result = {}

        def submit() -> None:
            for key in vars_map:
                result[key] = vars_map[key].get().strip()
            dialog.destroy()

        ctk.CTkButton(dialog, text="Save", command=submit).grid(row=len(fields), column=0, columnspan=2, pady=8)
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
            else:
                fields = [
                    ("label", "Profile label"),
                    ("account_holder", "Account holder"),
                    ("bank_name", "Bank name"),
                    ("sort_code", "Sort code (optional)"),
                    ("account_number", "Account number (optional)"),
                    ("iban", "IBAN (for international payments)"),
                    ("bic", "BIC/SWIFT (optional)"),
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
                "label": result["label"] or f"{method} profile",
                "method_type": method,
                "details": details,
            }

        save_profile(record)
        self.profiles = load_profiles()
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
            method = current.get("method_type", "bank_transfer")
            details = current.get("details", {})
            if method == "paypal":
                fields = [("label", "Profile label"), ("paypal_email", "PayPal email"), ("paypal_link", "PayPal link"), ("currency", "Currency")]
                initial = {"label": current.get("label", ""), "paypal_email": details.get("paypal_email", ""), "paypal_link": details.get("paypal_link", ""), "currency": details.get("currency", "GBP")}
            else:
                fields = [
                    ("label", "Profile label"),
                    ("account_holder", "Account holder"),
                    ("bank_name", "Bank name"),
                    ("sort_code", "Sort code (optional)"),
                    ("account_number", "Account number (optional)"),
                    ("iban", "IBAN (for international payments)"),
                    ("bic", "BIC/SWIFT (optional)"),
                    ("currency", "Currency"),
                ]
                initial = {
                    "label": current.get("label", ""),
                    "account_holder": details.get("account_holder", ""),
                    "bank_name": details.get("bank_name", ""),
                    "sort_code": details.get("sort_code", ""),
                    "account_number": details.get("account_number", ""),
                    "iban": details.get("iban", ""),
                    "bic": details.get("bic", ""),
                    "currency": details.get("currency", "GBP"),
                }
            result = self._simple_record_dialog("Edit payment method", fields, initial)
            if not result:
                return
            current["label"] = result["label"]
            current["details"] = {k: v for k, v in result.items() if k != "label"}

        upsert_profile(current)
        self.profiles = load_profiles()
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
        self.profiles = load_profiles()
        self._load_defaults()

    def _select_record(self, profile_type: str, record: dict) -> None:
        key = record.get("display_name") or record.get("label") or ""
        if profile_type == "provider":
            self.provider_var.set(key)
        elif profile_type == "recipient":
            self.recipient_var.set(key)
        else:
            self.payment_type_var.set(record.get("method_type", "bank_transfer"))
            self._reload_payment_combo()
            self.payment_var.set(key)

    def _open_invoices_folder(self) -> None:
        INVOICES_DIR.mkdir(parents=True, exist_ok=True)
        open_file(INVOICES_DIR)


if __name__ == "__main__":
    app = InvoiceApp()
    app.mainloop()
