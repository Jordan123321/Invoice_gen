from __future__ import annotations

import datetime as dt
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from uuid import uuid4

from pdf_generator import build_invoice_pdf
from storage import load_history, load_profiles, record_invoice_history, save_profile

BASE_DIR = Path(__file__).resolve().parent
INVOICES_DIR = BASE_DIR / "invoices"


def slugify(value: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in value).strip("-") or "recipient"


class InvoiceApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Invoice Generator")
        self.geometry("980x680")

        self.profiles = load_profiles()
        self.provider_var = tk.StringVar()
        self.recipient_var = tk.StringVar()
        self.payment_type_var = tk.StringVar(value="bank_transfer")
        self.payment_var = tk.StringVar()

        self.service_title_var = tk.StringVar(value="Tutoring session")
        self.student_name_var = tk.StringVar(value="")
        self.rate_var = tk.StringVar(value="75")
        self.duration_var = tk.StringVar(value="1.0")
        self.prep_hours_var = tk.StringVar(value="1.0")
        self.prep_description_var = tk.StringVar(value="Preparation (not billed): reviewing notes.")
        self.session_start_var = tk.StringVar(value=dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
        self.terms_var = tk.StringVar(value="Net 7")
        self.due_days_var = tk.StringVar(value="7")
        self.currency_var = tk.StringVar(value="GBP")

        self._build_ui()
        self._load_defaults()
        self._refresh_history()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)

        left = ttk.Frame(self, padding=12)
        right = ttk.Frame(self, padding=12)
        left.grid(row=0, column=0, sticky="nsew")
        right.grid(row=0, column=1, sticky="nsew")
        left.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(left, text="Provider").grid(row=row, column=0, sticky="w")
        self.provider_combo = ttk.Combobox(left, textvariable=self.provider_var, state="readonly")
        self.provider_combo.grid(row=row, column=1, sticky="ew")
        ttk.Button(left, text="Add", command=self._add_provider_dialog).grid(row=row, column=2, padx=6)

        row += 1
        ttk.Label(left, text="Recipient").grid(row=row, column=0, sticky="w")
        self.recipient_combo = ttk.Combobox(left, textvariable=self.recipient_var, state="readonly")
        self.recipient_combo.grid(row=row, column=1, sticky="ew")
        ttk.Button(left, text="Add", command=self._add_recipient_dialog).grid(row=row, column=2, padx=6)

        row += 1
        ttk.Label(left, text="Payment type").grid(row=row, column=0, sticky="w")
        payment_frame = ttk.Frame(left)
        payment_frame.grid(row=row, column=1, sticky="w")
        ttk.Radiobutton(payment_frame, text="Bank transfer", variable=self.payment_type_var, value="bank_transfer", command=self._on_payment_type_changed).pack(side=tk.LEFT)
        ttk.Radiobutton(payment_frame, text="PayPal", variable=self.payment_type_var, value="paypal", command=self._on_payment_type_changed).pack(side=tk.LEFT)

        row += 1
        ttk.Label(left, text="Payment profile").grid(row=row, column=0, sticky="w")
        self.payment_combo = ttk.Combobox(left, textvariable=self.payment_var, state="readonly")
        self.payment_combo.grid(row=row, column=1, sticky="ew")
        ttk.Button(left, text="Add", command=self._add_payment_dialog).grid(row=row, column=2, padx=6)

        fields = [
            ("Service title", self.service_title_var),
            ("Student name", self.student_name_var),
            ("Rate per hour", self.rate_var),
            ("Session hours", self.duration_var),
            ("Prep hours", self.prep_hours_var),
            ("Session start (YYYY-MM-DD HH:MM)", self.session_start_var),
            ("Terms label", self.terms_var),
            ("Due days", self.due_days_var),
            ("Currency", self.currency_var),
        ]
        for label, var in fields:
            row += 1
            ttk.Label(left, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(left, textvariable=var).grid(row=row, column=1, columnspan=2, sticky="ew")

        row += 1
        ttk.Label(left, text="Prep description").grid(row=row, column=0, sticky="nw")
        self.prep_text = tk.Text(left, height=4, width=40)
        self.prep_text.grid(row=row, column=1, columnspan=2, sticky="ew")
        self.prep_text.insert("1.0", self.prep_description_var.get())

        row += 1
        ttk.Button(left, text="Generate Invoice PDF", command=self._generate_invoice).grid(row=row, column=0, columnspan=3, pady=14)

        ttk.Label(right, text="Recent invoices", font=("Arial", 12, "bold")).pack(anchor="w")
        self.history_list = tk.Listbox(right, height=30)
        self.history_list.pack(fill="both", expand=True, pady=8)

        ttk.Button(right, text="Open invoices folder", command=self._open_invoices_folder).pack(anchor="w")

    def _load_defaults(self) -> None:
        self.provider_combo["values"] = [p["display_name"] for p in self.profiles.get("provider", [])]
        self.recipient_combo["values"] = [r["display_name"] for r in self.profiles.get("recipient", [])]
        self._reload_payment_combo()

        if self.provider_combo["values"]:
            self.provider_var.set(self.provider_combo["values"][0])
        if self.recipient_combo["values"]:
            self.recipient_var.set(self.recipient_combo["values"][0])
        if self.payment_combo["values"]:
            self.payment_var.set(self.payment_combo["values"][0])

    def _reload_payment_combo(self) -> None:
        method = self.payment_type_var.get()
        payments = [p for p in self.profiles.get("payment_method", []) if p.get("method_type") == method]
        self.payment_combo["values"] = [p.get("label", p["id"]) for p in payments]
        if self.payment_combo["values"]:
            self.payment_var.set(self.payment_combo["values"][0])
        else:
            self.payment_var.set("")

    def _on_payment_type_changed(self) -> None:
        self._reload_payment_combo()

    def _find_profile(self, type_name: str, display: str) -> dict:
        for item in self.profiles.get(type_name, []):
            key = item.get("display_name") or item.get("label")
            if key == display:
                return item
        raise ValueError(f"{type_name} profile not found: {display}")

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
                "service_title": self.service_title_var.get().strip() or "Service",
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
                    "output_path": str(out_path),
                    "created_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "payment_method": payment.get("method_type", "bank_transfer"),
                }
            )
            self._refresh_history()
            messagebox.showinfo("Success", f"Invoice saved:\n{out_path}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _refresh_history(self) -> None:
        self.history_list.delete(0, tk.END)
        grouped = {}
        for item in load_history(limit=50):
            grouped.setdefault(item.get("recipient", "Unknown"), []).append(item)
        for recipient, items in grouped.items():
            self.history_list.insert(tk.END, f"[{recipient}]")
            for entry in items[:10]:
                self.history_list.insert(tk.END, f"  {entry.get('created_at', '')} - {entry.get('invoice_number', '')}")
                self.history_list.insert(tk.END, f"    {entry.get('output_path', '')}")

    def _simple_record_dialog(self, title: str, fields: list[tuple[str, str]]) -> dict | None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.grab_set()
        vars_map: dict[str, tk.StringVar] = {}
        for i, (key, label) in enumerate(fields):
            ttk.Label(dialog, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=6)
            var = tk.StringVar()
            vars_map[key] = var
            ttk.Entry(dialog, textvariable=var, width=40).grid(row=i, column=1, padx=8, pady=6)

        result = {}

        def submit():
            for key in vars_map:
                result[key] = vars_map[key].get().strip()
            dialog.destroy()

        ttk.Button(dialog, text="Save", command=submit).grid(row=len(fields), column=0, columnspan=2, pady=8)
        self.wait_window(dialog)
        return result or None

    def _add_provider_dialog(self) -> None:
        result = self._simple_record_dialog("Add provider", [("display_name", "Name"), ("address", "Address (comma-separated)"), ("email", "Email")])
        if not result:
            return
        record = {
            "type": "provider",
            "id": f"provider-{uuid4().hex[:8]}",
            "display_name": result["display_name"],
            "address_lines": [x.strip() for x in result["address"].split(",") if x.strip()],
            "email": result["email"],
        }
        save_profile(record)
        self.profiles = load_profiles()
        self._load_defaults()
        self.provider_var.set(record["display_name"])

    def _add_recipient_dialog(self) -> None:
        result = self._simple_record_dialog("Add recipient", [("display_name", "Name"), ("address", "Address (comma-separated)"), ("email", "Email"), ("student_name", "Student name")])
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
        save_profile(record)
        self.profiles = load_profiles()
        self._load_defaults()
        self.recipient_var.set(record["display_name"])

    def _add_payment_dialog(self) -> None:
        method = self.payment_type_var.get()
        if method == "paypal":
            fields = [("label", "Profile label"), ("paypal_email", "PayPal email"), ("paypal_link", "PayPal link"), ("currency", "Currency")]
        else:
            fields = [
                ("label", "Profile label"),
                ("account_holder", "Account holder"),
                ("bank_name", "Bank name"),
                ("sort_code", "Sort code"),
                ("account_number", "Account number"),
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
        self.payment_type_var.set(method)
        self._reload_payment_combo()
        self.payment_var.set(record["label"])

    def _open_invoices_folder(self) -> None:
        INVOICES_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(INVOICES_DIR) if hasattr(os, "startfile") else messagebox.showinfo("Invoices", str(INVOICES_DIR))


if __name__ == "__main__":
    app = InvoiceApp()
    app.mainloop()
