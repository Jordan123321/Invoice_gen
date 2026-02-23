from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SEED_FILE = DATA_DIR / "seed_profiles.jsonl"
LOCAL_FILE = DATA_DIR / "profiles.local.jsonl"
HISTORY_FILE = DATA_DIR / "history.local.jsonl"
SETTINGS_FILE = DATA_DIR / "defaults.local.json"


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            rows.append(json.loads(raw))
    return rows


def _write_jsonl(path: Path, records: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_profiles() -> Dict[str, List[dict]]:
    """Load committed seed profiles and overlay local profiles by id."""
    items_by_id: Dict[str, dict] = {}
    for row in _read_jsonl(SEED_FILE) + _read_jsonl(LOCAL_FILE):
        if "id" not in row or "type" not in row:
            continue
        items_by_id[row["id"]] = row

    grouped: Dict[str, List[dict]] = {"provider": [], "recipient": [], "payment_method": []}
    for item in items_by_id.values():
        if item.get("_deleted"):
            continue
        grouped.setdefault(item["type"], []).append(item)

    for bucket in grouped.values():
        bucket.sort(key=lambda x: x.get("display_name") or x.get("label") or x.get("id", ""))
    return grouped


def save_profile(record: dict) -> None:
    _append_jsonl(LOCAL_FILE, record)


def upsert_profile(record: dict) -> None:
    save_profile(record)


def delete_profile(profile_id: str, profile_type: str) -> None:
    save_profile({"id": profile_id, "type": profile_type, "_deleted": True})


def record_invoice_history(record: dict) -> None:
    _append_jsonl(HISTORY_FILE, record)


def load_history(limit: int = 30) -> List[dict]:
    items = _read_jsonl(HISTORY_FILE)
    return list(reversed(items[-limit:]))


def load_history_all() -> List[dict]:
    return _read_jsonl(HISTORY_FILE)


def save_history(items: List[dict]) -> None:
    _write_jsonl(HISTORY_FILE, items)


def prune_missing_history_files() -> int:
    items = _read_jsonl(HISTORY_FILE)
    kept: List[dict] = []
    removed = 0
    for item in items:
        path = item.get("output_path")
        if not path or Path(path).exists():
            kept.append(item)
        else:
            removed += 1
    if removed:
        _write_jsonl(HISTORY_FILE, kept)
    return removed


def remove_history_entry(output_path: str) -> None:
    items = _read_jsonl(HISTORY_FILE)
    kept = [i for i in items if i.get("output_path") != output_path]
    _write_jsonl(HISTORY_FILE, kept)


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {"selected_profiles": {}, "field_defaults": {}}
    with SETTINGS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
