from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SEED_FILE = DATA_DIR / "seed_profiles.jsonl"
LOCAL_FILE = DATA_DIR / "profiles.local.jsonl"
HISTORY_FILE = DATA_DIR / "history.local.jsonl"


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
        grouped.setdefault(item["type"], []).append(item)

    for bucket in grouped.values():
        bucket.sort(key=lambda x: x.get("display_name") or x.get("label") or x.get("id", ""))
    return grouped


def save_profile(record: dict) -> None:
    _append_jsonl(LOCAL_FILE, record)


def record_invoice_history(record: dict) -> None:
    _append_jsonl(HISTORY_FILE, record)


def load_history(limit: int = 30) -> List[dict]:
    items = _read_jsonl(HISTORY_FILE)
    return list(reversed(items[-limit:]))
