"""모드 DB 로딩과 티어 계산."""
from __future__ import annotations

import json
import sys
from pathlib import Path


UPDATABLE = {"data/ko_en.json", "data/names_ko.json"}


def updated_data_dir() -> Path:
    """앱이 자동으로 새로 만든 번역 사전 위치 (%APPDATA%\\ExileDelta\\data)."""
    from paths import ROAMING

    return ROAMING / "data"


DICT_VERSION = 2  # dict_builder 출력 형식이 바뀌면 올림 → 예전 형식의 자동 갱신본은 무시


def _updated_ok() -> bool:
    try:
        meta = json.loads((updated_data_dir() / "meta.json").read_text(encoding="utf-8"))
        return meta.get("version") == DICT_VERSION
    except (OSError, ValueError):
        return False


def resource_path(rel: str) -> Path:
    if rel in UPDATABLE and _updated_ok():
        p = updated_data_dir() / Path(rel).name
        if p.exists():
            return p
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel


def fmt_num(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def tier_range_text(t: dict, entry: dict | None = None) -> str:
    """티어 수치 범위. entry 가 평균 비교 옵션이면 '평균 ' 접두."""
    if abs(t["lo"] - t["hi"]) < 1e-9:
        s = fmt_num(t["lo"])
    else:
        s = f"{fmt_num(t['lo'])}~{fmt_num(t['hi'])}"
    return f"평균 {s}" if entry and entry.get("metric") == "avg2" else s


def tier_for_value(entry: dict, value: float) -> dict | None:
    """value 이상을 굴릴 수 있는 가장 낮은 티어(=최소 요구 티어). 없으면 None."""
    ok = [t for t in entry["tiers"] if t["hi"] >= value - 1e-9]
    if not ok:
        return None
    return max(ok, key=lambda t: t["t"])


class ModDB:
    def __init__(self, path: Path | None = None):
        path = path or resource_path("data/mods_ko.json")
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        self.built: str = d["built"]
        self.source: str = d["source"]
        self.influences: dict[str, str] = d["influences"]
        self.slots: list[dict] = d["slots"]
        self.mods: dict[str, list[dict]] = d["mods"]
        self._slot_by_id = {s["id"]: s for s in self.slots}
        self._by_key = {e["key"]: e for lst in self.mods.values() for e in lst}
        for lst in self.mods.values():
            for e in lst:
                inf = self.influences.get(e["inf"], "")
                e["_hay"] = f"{e['ko']} {e['en']} {inf}".lower()

    @property
    def total(self) -> int:
        return len(self._by_key)

    def has_slot(self, slot: str) -> bool:
        return slot in self._slot_by_id

    def slot_name(self, slot: str) -> str:
        s = self._slot_by_id.get(slot)
        return s["ko"] if s else slot

    def influence_name(self, inf: str) -> str:
        return self.influences.get(inf, inf)

    def options(self, slot: str) -> list[dict]:
        return self.mods.get(slot, [])

    def get(self, key: str) -> dict | None:
        return self._by_key.get(key)

    def remap(self, key: str, new_slot: str) -> str | None:
        """같은 옵션을 다른 장비 종류의 키로 변환. 없으면 None."""
        rest = key.split("|", 1)[1] if "|" in key else ""
        nk = f"{new_slot}|{rest}"
        return nk if nk in self._by_key else None
