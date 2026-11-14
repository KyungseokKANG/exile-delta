"""등록된 캐릭터 저장소. 목록은 characters.json, 빌드(PoB XML)는 characters/<id>.xml."""
from __future__ import annotations

import json
import os
import time
import uuid

from storage import APP_DIR

CHAR_DIR = APP_DIR / "characters"
INDEX = APP_DIR / "characters.json"


def _atomic_write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class CharacterStore:
    def __init__(self):
        self.chars: list[dict] = []
        self.current = 0
        try:
            raw = json.loads(INDEX.read_text(encoding="utf-8"))
            self.chars = [c for c in raw.get("chars", []) if isinstance(c, dict) and c.get("id")]
            self.current = int(raw.get("current", 0))
        except (OSError, ValueError, TypeError):
            pass
        self.current = max(0, min(self.current, len(self.chars) - 1))

    def save(self) -> None:
        _atomic_write(INDEX, json.dumps({"current": self.current, "chars": self.chars}, ensure_ascii=False, indent=1))

    def xml(self, cid: str) -> str | None:
        try:
            return (CHAR_DIR / f"{cid}.xml").read_text(encoding="utf-8")
        except OSError:
            return None

    def set_xml(self, cid: str, xml: str) -> None:
        _atomic_write(CHAR_DIR / f"{cid}.xml", xml)

    def orig_xml(self, cid: str) -> str | None:
        """마지막으로 가져온(가공 전) 빌드 — '가져온 상태로' 되돌리기 기준."""
        try:
            return (CHAR_DIR / f"{cid}.orig.xml").read_text(encoding="utf-8")
        except OSError:
            return None

    def set_orig(self, cid: str, xml: str) -> None:
        _atomic_write(CHAR_DIR / f"{cid}.orig.xml", xml)

    def add(self, name: str, source: dict, xml: str, summary: dict | None = None) -> dict:
        c = {"id": uuid.uuid4().hex, "name": name, "source": source, "summary": summary or {}, "updated": time.time()}
        self.chars.append(c)
        self.set_xml(c["id"], xml)
        self.save()
        return c

    def remove(self, index: int) -> dict:
        c = self.chars.pop(index)
        for suffix in (".xml", ".orig.xml"):
            try:
                (CHAR_DIR / f"{c['id']}{suffix}").unlink()
            except OSError:
                pass
        self.current = max(0, min(self.current, len(self.chars) - 1))
        self.save()
        return c
