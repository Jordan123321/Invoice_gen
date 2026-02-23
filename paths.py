from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Invoice_gen"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parent


def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return project_root()


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def user_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    target = base / APP_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def invoices_dir() -> Path:
    docs = Path.home() / "Documents"
    target = docs / APP_NAME / "invoices"
    target.mkdir(parents=True, exist_ok=True)
    return target


def bundled_seed_profiles_path() -> Path:
    return bundle_root() / "data" / "seed_profiles.jsonl"


def resolve_qr_path() -> Path | None:
    candidates = [
        user_data_dir() / "QR.png",
        executable_dir() / "QR.png",
        bundle_root() / "QR.png",
        project_root() / "QR.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
