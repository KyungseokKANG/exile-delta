"""검색 조건(탭) 저장/불러오기."""
from __future__ import annotations

import copy
import json
import os
import uuid
from pathlib import Path

from paths import ROAMING

APP_DIR = ROAMING
STATE_FILE = APP_DIR / "profiles.json"
FORMAT = "exile-delta/1"


SETTINGS_FILE = APP_DIR / "settings.json"


def load_settings() -> dict:
    try:
        d = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(d: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, SETTINGS_FILE)


def new_tab(name: str, slot: str) -> dict:
    return {"id": uuid.uuid4().hex, "name": name, "slot": slot, "options": []}


def clone_tab(tab: dict, suffix: str = " (복사)") -> dict:
    t = copy.deepcopy(tab)
    t["id"] = uuid.uuid4().hex
    t["name"] = f"{tab['name']}{suffix}"
    return t


def clean_tab(raw: dict, db) -> dict | None:
    if not isinstance(raw, dict) or not db.has_slot(raw.get("slot", "")):
        return None
    opts = []
    for o in raw.get("options", []):
        try:
            if db.get(o["key"]):
                opts.append({"key": o["key"], "value": float(o["value"])})
        except (KeyError, TypeError, ValueError):
            continue
    return {
        "id": raw.get("id") or uuid.uuid4().hex,
        "name": str(raw.get("name") or db.slot_name(raw["slot"])),
        "slot": raw["slot"],
        "options": opts,
    }


class Store:
    def __init__(self, db):
        self.db = db

    def load(self) -> dict:
        state: dict = {"tabs": [], "current": 0}
        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            state["tabs"] = [t for t in (clean_tab(x, self.db) for x in raw.get("tabs", [])) if t]
            state["current"] = int(raw.get("current", 0))
            state["window"] = raw.get("window")
        except (OSError, ValueError, TypeError):
            pass
        if not state["tabs"]:
            slot = self.db.slots[0]["id"] if self.db.slots else ""
            for s in ("Gloves", "Helmet"):
                if self.db.has_slot(s):
                    slot = s
                    break
            state["tabs"] = [new_tab(self.db.slot_name(slot), slot)]
        state["current"] = max(0, min(state["current"], len(state["tabs"]) - 1))
        return state

    def save(self, state: dict) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        data = {"format": FORMAT, **state}
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, STATE_FILE)

    # ---- 파일 내보내기/가져오기 ----
    @staticmethod
    def export_tabs(path: str, tabs: list[dict]) -> None:
        Path(path).write_text(
            json.dumps({"format": FORMAT, "tabs": tabs}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def import_tabs(self, path: str) -> list[dict]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        items = raw.get("tabs", [raw]) if isinstance(raw, dict) else raw
        out = []
        for x in items if isinstance(items, list) else []:
            t = clean_tab(x, self.db)
            if t:
                t["id"] = uuid.uuid4().hex
                out.append(t)
        return out
