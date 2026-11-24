"""PoB 계산 엔진 (lupa LuaJIT 안에서 Path of Building 원본 Lua 코드를 headless 로 실행).

이 모듈은 무거우므로(초기화 수 초, 메모리 수백 MB) GUI 프로세스가 아닌 별도 워커 프로세스에서 사용한다.
"""
from __future__ import annotations

import os
import sys
import time
import zlib
from pathlib import Path


def _lua_path(p: Path, rel: bytes | None = None) -> bytes:
    """Lua(LuaJIT, ANSI 파일 API)에 넘길 경로. 영문이면 그대로, 아니면 8.3 짧은 경로 → 상대 경로 → ANSI 인코딩 순."""
    s = str(p).replace("\\", "/").rstrip("/")
    if s.isascii():
        return s.encode()
    if sys.platform == "win32":
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(1024)
            n = ctypes.windll.kernel32.GetShortPathNameW(str(p), buf, 1024)
            short = buf.value.replace("\\", "/").rstrip("/") if 0 < n < 1024 else ""
            if short and short.isascii():
                return short.encode()
        except Exception:  # noqa: BLE001
            pass
    if rel is not None:
        return rel
    try:
        return s.encode("mbcs", "strict")  # 한국어 Windows 면 한글도 ANSI(cp949)로 표현됨
    except (LookupError, UnicodeError):
        return s.encode()


def _to_py(obj, depth=0):
    """Lua 테이블 → Python dict/list (bytes 는 utf-8 문자열로)."""
    from lupa import luajit21 as lj

    if isinstance(obj, bytes):
        return obj.decode("utf-8", "replace")
    if lj.lua_type(obj) == "table":
        if depth > 12:
            return None
        keys = list(obj.keys())
        if keys and all(isinstance(k, int) for k in keys) and sorted(keys) == list(range(1, len(keys) + 1)):
            return [_to_py(obj[k], depth + 1) for k in range(1, len(keys) + 1)]
        return {(_to_py(k) if isinstance(k, bytes) else k): _to_py(v, depth + 1) for k, v in obj.items()}
    return obj


class PobEngine:
    def __init__(self, src_dir: Path, user_dir: Path, log=None):
        from lupa import luajit21 as lj

        self.src = Path(src_dir)
        self.log = log or (lambda m: print(m, file=sys.stderr))
        user_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(self.src)  # PoB 는 상대경로로 모듈/데이터를 읽는다
        self.lua = lj.LuaRuntime(encoding=None, unpack_returned_tuples=True)
        g = self.lua.globals()
        # LuaJIT 의 파일 열기는 ANSI 경로라 한글 사용자 이름 등 비영문 경로를 못 엶 ("module 'xml' not found")
        # → 작업 폴더(src) 기준 상대 경로로, 절대 경로가 필요한 곳은 8.3 짧은 경로로 넘김
        g.package.path = b"./?.lua;../runtime/lua/?.lua;../runtime/lua/?/init.lua;" + g.package.path
        g._ES_SRC = _lua_path(self.src, b".") + b"/"
        g._ES_USER = _lua_path(Path(user_dir)) + b"/"
        g._ES_INFLATE = self._inflate
        g._ES_DEFLATE = self._deflate
        g._ES_LOG = lambda m: self.log(m.decode("utf-8", "replace") if isinstance(m, bytes) else str(m))
        t0 = time.perf_counter()
        g._ES_TIME = lambda: int((time.perf_counter() - t0) * 1000)
        boot = Path(__file__).with_name("headless.lua").read_bytes()
        self.lua.execute(boot)
        self.g = g

    # ---- zlib bridge ----
    @staticmethod
    def _inflate(data: bytes) -> bytes:
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS, zlib.MAX_WBITS | 32):
            try:
                return zlib.decompress(data, wbits)
            except zlib.error:
                continue
        return b""

    @staticmethod
    def _deflate(data: bytes) -> bytes:
        return zlib.compress(data, 9)

    # ---- API ----
    def load_xml(self, xml: str, name: str = "") -> dict:
        self.g.es_load_xml(xml.encode("utf-8"), name.encode("utf-8"))
        return self.summary()

    def load_character_json(self, js: str, prev_xml: str | None = None) -> dict:
        """prev_xml: 다시 가져오기 전 빌드 — 거기서 고른 Full DPS·젬 사용·설정·플라스크 등을 새 데이터에 다시 적용."""
        self.g.es_load_character_json(js.encode("utf-8"), prev_xml.encode("utf-8") if prev_xml else None)
        return self.summary()

    def vaal_defaults(self, keep: list[str] | None) -> bool:
        """바알 젬의 바알 쪽 스킬을 끔 — keep('장착 칸|젬 이름')에 든 것만 켬."""
        return bool(self.g.es_vaal_defaults("\n".join(keep or []).encode("utf-8")))

    def save_xml(self) -> str:
        return self.g.es_save_xml().decode("utf-8")

    def summary(self) -> dict:
        return _to_py(self.g.es_summary())

    def set_main_group(self, index: int) -> dict:
        self.g.es_set_main_group(index)
        return self.summary()

    def set_group(self, index: int, enabled=None, full_dps=None) -> dict:
        self.g.es_set_group(index, enabled, full_dps)
        return self.summary()

    @staticmethod
    def _lv(v):
        return v.encode("utf-8") if isinstance(v, str) else v

    def set_config(self, var: str, value) -> dict:
        self.g.es_set_config(var.encode("utf-8"), self._lv(value))
        return self.summary()

    def reset_config(self) -> dict:
        self.g.es_reset_config()
        return self.summary()

    def set_flask(self, slot: str, active: bool) -> dict:
        self.g.es_set_flask(slot.encode("utf-8"), bool(active))
        return self.summary()

    def set_active_skill(self, group: int, active: int) -> dict:
        self.g.es_set_active_skill(group, active)
        return self.summary()

    def set_skill_part(self, part: int) -> dict:
        self.g.es_set_skill_part(part)
        return self.summary()

    def set_level(self, level: int) -> dict:
        self.g.es_set_level(int(level))
        return self.summary()

    def set_skill_knob(self, group: int, active: int, key: str, value) -> dict:
        """단계 수(stage) · 활성 지뢰 수(mine) · 토템 수(count). value=None 이면 PoB 기본값으로."""
        self.g.es_set_skill_knob(int(group), int(active), key.encode("utf-8"), None if value is None else int(value))
        return self.summary()

    # ---- 장비 ----
    def equipment(self) -> dict:
        return _to_py(self.g.es_equipment())

    def equipment_impact(self, skip: int = 0, limit: int | None = None) -> dict:
        return _to_py(self.g.es_equipment_impact(int(skip), limit))

    def set_slot(self, slot: str, item_id: int) -> dict:
        return _to_py(self.g.es_set_slot(slot.encode("utf-8"), int(item_id or 0)))

    def flasks(self) -> dict:
        return _to_py(self.g.es_flasks())

    # ---- 버들가지 제웅 ----
    def wicker_catalog(self) -> list:
        return _to_py(self.g.es_wicker_catalog())

    def wicker_state(self) -> dict:
        return _to_py(self.g.es_wicker_state())

    def wicker_put(self, slot: str, raw: str) -> dict:
        return _to_py(self.g.es_wicker_put(slot.encode("utf-8"), (raw or "").encode("utf-8")))

    # ---- 아이템 만들기 ----
    def item_catalog(self, slot: str) -> dict:
        return _to_py(self.g.es_item_catalog(slot.encode("utf-8")))

    def draft_new(self, spec: dict) -> dict:
        import json

        return _to_py(self.g.es_draft_new(json.dumps(spec).encode("utf-8")))

    def draft_edit(self, spec: dict) -> dict:
        import json

        return _to_py(self.g.es_draft_edit(json.dumps(spec).encode("utf-8")))

    def draft_equip(self, slot: str) -> dict:
        return _to_py(self.g.es_draft_equip(slot.encode("utf-8")))

    def draft_replace(self, slot: str) -> dict:
        return _to_py(self.g.es_draft_replace(slot.encode("utf-8")))

    def optimize(self, spec: dict) -> dict:
        import json

        return _to_py(self.g.es_optimize(json.dumps(spec).encode("utf-8")))

    # ---- 스킬 젬 ----
    def set_gem(self, group: int, gem: int, level=None, quality=None, enabled=None, side=None) -> dict:
        """side: 바알 젬일 때 1 = 바알 쪽 스킬, 2 = 일반 쪽 스킬만 켜고 끔 (없으면 젬 전체)."""
        return _to_py(self.g.es_set_gem(int(group), int(gem), level, quality, enabled,
                                        int(side) if side else None))

    def gem_impact(self, skip: int = 0, limit: int | None = None) -> dict:
        return _to_py(self.g.es_gem_impact(int(skip), limit))

    # ---- 패시브 트리 ----
    def tree_layout(self) -> dict:
        return _to_py(self.g.es_tree_layout())

    def tree_state(self) -> dict:
        return _to_py(self.g.es_tree_state())

    def tree_preview(self, node_id: int) -> dict:
        return _to_py(self.g.es_tree_preview(int(node_id)))

    def tree_mastery_preview(self, node_id: int) -> dict:
        return _to_py(self.g.es_tree_mastery_preview(int(node_id)))

    def tree_click(self, node_id: int, effect=None) -> dict:
        return _to_py(self.g.es_tree_click(int(node_id), None if effect is None else int(effect)))

    def tree_restore(self, snap: dict) -> dict:
        import json

        return _to_py(self.g.es_tree_restore(json.dumps(snap).encode("utf-8")))

    def tree_reset(self) -> dict:
        return _to_py(self.g.es_tree_reset())

    def tree_import_url(self, url: str) -> dict:
        return _to_py(self.g.es_tree_import_url(url.strip().encode("utf-8")))

    def set_ascend(self, on: bool) -> dict:
        return _to_py(self.g.es_set_ascend(bool(on)))

    def set_minion(self, index: int) -> dict:
        return _to_py(self.g.es_set_minion(int(index)))

    def set_minion_skill(self, index: int) -> dict:
        return _to_py(self.g.es_set_minion_skill(int(index)))

    def set_minion_in_main(self, on: bool) -> dict:
        return _to_py(self.g.es_set_minion_in_main(bool(on)))

    def compare_item(self, item_text: str, nodef: list | None = None) -> dict:
        """nodef: 끈 고유 방어력 ['EnergyShield', 'Armour', …] (그 장비 몫을 0 으로)."""
        return _to_py(self.g.es_compare_item(item_text.encode("utf-8"), ",".join(nodef or []).encode("utf-8")))

    def explain_item(self, item_text: str, slot: str) -> dict:
        """옵션 줄마다 DPS/EHP 기여도 (새 아이템 줄 / 지금 장비 줄)."""
        return _to_py(self.g.es_explain_item(item_text.encode("utf-8"), slot.encode("utf-8")))

    def slot_variant(self, slot: str, off: list, contrib: bool = False, nodef: list | None = None) -> dict:
        """지금 장착한 아이템에서 off 줄([[목록 이름, 번호], …])을 빼고 nodef 고유 방어력을 끈 계산 결과 + 줄 목록.
        contrib: 줄마다(고유 방어력도) 그것만 뺐을 때 잃는 양(d)도."""
        spec = ",".join(f"{a}:{int(b)}" for a, b in off)
        return _to_py(self.g.es_slot_variant(slot.encode("utf-8"), spec.encode("utf-8"), bool(contrib),
                                             ",".join(nodef or []).encode("utf-8")))
