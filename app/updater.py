"""자동 업데이트.

1) PoB 엔진: GitHub 최신 릴리스를 '받기만' 한 뒤, 별도 워커 프로세스로 자체 점검
   (캐릭터 불러오기 → DPS/EHP 계산 → 패시브 트리 → 장비 → 아이템 비교).
   통과하면 새 버전으로 전환하고, 실패하면 그 버전을 '호환 안 됨'으로 기록하고 지금 버전을 계속 쓴다.
2) 번역 사전(ko_en.json / names_ko.json): RePoE · Awakened PoE Trade 데이터가 바뀌었으면
   앱 안에서 다시 만들어 %APPDATA%\\ExileDelta\\data 에 둔다 (exe 를 다시 받지 않아도 새 리그 옵션 번역).
"""
from __future__ import annotations

import json
import os
import time

from PySide6.QtCore import QObject, QTimer, Signal

from asyncjob import run_async
from pob import installer
from pob.client import PobClient
from storage import load_settings, save_settings

DICT_EVERY = 3 * 86400
TEST_TIMEOUT_MS = 240_000
TEST_RING = ("Item Class: Rings\nRarity: Rare\nSelftest Loop\nGold Ring\n--------\nItem Level: 80\n--------\n"
             "+60 to maximum Life\n+40% to Fire Resistance\n12% increased Attack Speed")


class Updater(QObject):
    message = Signal(str)

    def __init__(self, client, page, parent=None):
        super().__init__(parent)
        self.client = client
        self.page = page
        self.pob_running = False
        self.dict_running = False
        self.test: PobClient | None = None
        self.checks = None  # 시작 점검 패널 (main 에서 붙임)
        self._timeout = QTimer(self, singleShot=True, interval=TEST_TIMEOUT_MS, timeout=lambda: self._fail("시간 초과"))

    def _stamp(self, key: str) -> None:
        s = load_settings()
        s[key] = time.time()
        save_settings(s)

    def _pob_step(self, state: str, detail: str = "", done: int = 0, total: int = 0) -> None:
        if self.checks is not None:
            self.checks.step("pob", "PoB 새 버전 확인", state, detail, done, total)

    def _dict_step(self, state: str, detail: str = "") -> None:
        if self.checks is not None:
            self.checks.step("dict", "번역 데이터 확인", state, detail)

    def auto(self) -> None:
        s = load_settings()
        now = time.time()
        if installer.installed():  # PoB 새 버전은 켤 때마다 확인 (리그 시작·패치 날 바로 반영)
            self.check_pob(manual=False)
        else:
            self._pob_step("ok", "PoB 엔진을 처음 설치해요 (아래 안내 참고)")
        if now - float(s.get("dict_update_at", 0)) > DICT_EVERY:
            self.update_dict(manual=False)
        else:
            self._dict_step("ok", "최근에 확인함 (3일마다 확인)")

    # ================================================================ PoB
    def check_pob(self, manual: bool = True) -> None:
        if self.pob_running:
            if manual:
                self.message.emit("PoB 업데이트 확인이 이미 진행 중입니다")
            return
        if not installer.installed():
            self.page.install_engine()
            return
        self.pob_running = True
        self._pob_step("run", "GitHub 에서 최신 PoB 버전 확인 중…")
        if manual:
            self.message.emit("PoB 최신 버전 확인 중…")

        def job(progress):
            tag = installer.latest_tag()
            cur = installer.installed()
            if cur and cur[0] == tag:
                return ("latest", tag)
            bad = installer.bad_tags()
            if tag in bad and not manual:
                return ("bad", tag)
            if not installer.is_complete(tag):
                installer.install(tag, progress, activate_now=False)
            return ("test", tag)

        def on_progress(d, t, m):
            self._pob_step("run", f"새 버전 받는 중 — {m}  (지금 버전으로 계속 써도 돼요)", d, t)
            if manual or d == 0:
                self.message.emit(m)

        def done(res):
            kind, tag = res
            self._stamp("pob_update_at")
            if kind == "latest":
                self.pob_running = False
                self._pob_step("ok", f"최신 버전이에요 ({tag})")
                if manual:
                    self.message.emit(f"PoB {tag} — 이미 최신 버전입니다")
            elif kind == "bad":
                self.pob_running = False
                cur = installer.installed()
                self._pob_step("warn", f"{tag} 는 아직 이 앱과 안 맞아서 {cur[0] if cur else '지금'} 버전을 써요")
            else:
                self.message.emit(f"PoB {tag} 받음 — 호환성 점검 중 (지금 버전은 그대로 사용 가능)")
                self._pob_step("run", f"{tag} 받기 완료 — 내 캐릭터로 계산 점검 중… (1~2분, 지금 버전으로 계속 써도 돼요)")
                self._selftest(tag)

        def fail(msg):
            self.pob_running = False
            self._pob_step("warn", f"확인 실패 — 지금 버전으로 계속 써요 ({msg})")
            if manual:
                self.message.emit(f"PoB 업데이트 확인 실패: {msg}")

        run_async(job, done, fail, on_progress, with_progress=True)

    def _selftest(self, tag: str) -> None:
        self.tag = tag
        src = installer.BASE / tag / "src"
        self.test = PobClient(self, override=(tag, src), log=installer.BASE.parent / "pob_selftest.log")
        self.test.stateChanged.connect(self._test_state)
        self._timeout.start()
        self.test.start()

    def _test_state(self, st: str, msg: str) -> None:
        if self.test is None:
            return
        if st == "ready":
            self._run_steps()
        elif st in ("error", "missing"):
            self._fail(msg or st)

    def _run_steps(self) -> None:
        t = self.test
        c = self.page._cur()
        xml = self.page.store.xml(c["id"]) if c else None

        def need(cond, what):
            if not cond:
                raise RuntimeError(what)

        def step_tree(_r=None):
            def ok(r):
                try:
                    need(len((r.get("layout") or {}).get("nodes") or []) > 1000, "패시브 트리를 읽지 못함")
                    need((r.get("state") or {}).get("key"), "트리 상태 없음")
                except RuntimeError as e:
                    return self._fail(str(e))
                if xml:
                    step_equipment()
                else:
                    self._pass()
            t.call("tree_layout", {}, ok, self._fail)

        def step_equipment():
            def ok(r):
                try:
                    need(isinstance(r.get("slots"), list), "장비 목록을 읽지 못함")
                except RuntimeError as e:
                    return self._fail(str(e))
                step_compare()
            t.call("equipment", {}, ok, self._fail)

        def step_compare():
            def ok(r):
                try:
                    need(not r.get("error"), f"아이템 해석 실패: {r.get('error')}")
                    need(r.get("slots"), "아이템 비교 결과 없음")
                    need((r.get("base_stats") or {}).get("TotalEHP"), "비교 계산값 없음")
                except RuntimeError as e:
                    return self._fail(str(e))
                self._pass()
            t.call("compare", {"text": TEST_RING}, ok, self._fail)

        if xml:
            def loaded(r):
                st = (r.get("summary") or {}).get("stats") or {}
                try:
                    need(st.get("TotalEHP") and st.get("Life") is not None, "DPS/EHP 계산값이 비어 있음")
                    need(((r.get("summary") or {}).get("config") or {}).get("sections"), "Configuration 을 읽지 못함")
                except RuntimeError as e:
                    return self._fail(str(e))
                step_tree()
            t.call("load_xml", {"xml": xml, "name": c["name"]}, loaded, self._fail)
        else:
            step_tree()

    def _end_test(self) -> None:
        self._timeout.stop()
        if self.test is not None:
            self.test.stateChanged.disconnect(self._test_state)
            self.test.stop()
            self.test.deleteLater()
            self.test = None
        self.pob_running = False

    def _pass(self) -> None:
        tag = self.tag
        self._end_test()
        try:
            installer.activate(tag)
        except OSError as e:
            self._pob_step("warn", f"{tag} 전환 실패 — 지금 버전으로 계속 써요 ({e})")
            self.message.emit(f"PoB {tag} 전환 실패: {e}")
            return
        self._pob_step("ok", f"{tag} 로 업데이트했어요 (점검 통과) — 엔진 다시 켜는 중")
        self.message.emit(f"PoB {tag} 로 자동 업데이트됨 (점검 통과) — 엔진 다시 시작")
        self.client.start()

    def _fail(self, msg: str) -> None:
        if self.test is None:
            return
        tag = self.tag
        self._end_test()
        installer.mark_bad(tag, str(msg))
        cur = installer.installed()
        self._pob_step("warn", f"{tag} 는 아직 이 앱과 안 맞아서 {cur[0] if cur else '지금'} 버전을 계속 써요")
        self.message.emit(f"PoB {tag} 는 아직 이 앱과 호환되지 않아 {cur[0] if cur else '지금'} 버전을 계속 씁니다 ({msg})")

    def rollback(self) -> None:
        prev = installer.rollback()
        if prev:
            self.message.emit(f"PoB {prev} 로 되돌림 — 엔진 다시 시작")
            self.client.start()
        else:
            self.message.emit("되돌릴 이전 버전이 없습니다")

    # ================================================================ 번역 사전
    def update_dict(self, manual: bool = True) -> None:
        if self.dict_running:
            return
        self.dict_running = True
        self._dict_step("run", "새 리그 옵션 번역이 바뀌었는지 확인 중… (처음엔 몇 분 걸릴 수 있어요)")
        if manual:
            self.message.emit("번역 데이터 갱신 확인 중… (처음에는 약 90MB 를 받습니다)")

        def job():
            import dict_builder
            from data import DICT_VERSION, _updated_ok, updated_data_dir

            out = updated_data_dir()
            stage = out.parent / "data_new"
            dict_builder.CACHE = out.parent / "datacache"
            dict_builder.OUT_DIR = stage
            dict_builder.CHANGED.clear()
            first = not _updated_ok()
            dict_builder.main(refresh=True)
            if not dict_builder.CHANGED and not first:
                return False
            d = json.loads((stage / "ko_en.json").read_text(encoding="utf-8"))
            if len(d.get("stats") or []) < 10000 or len(d.get("bases") or {}) < 1000:
                raise RuntimeError("새 번역 데이터가 비정상적으로 작음 — 적용 안 함")
            n = json.loads((stage / "names_ko.json").read_text(encoding="utf-8"))
            if len(n.get("names") or {}) < 500:
                raise RuntimeError("새 명칭 데이터가 비정상적으로 작음 — 적용 안 함")
            out.mkdir(parents=True, exist_ok=True)
            for f in ("ko_en.json", "names_ko.json"):
                os.replace(stage / f, out / f)
            (out / "meta.json").write_text(json.dumps({"version": DICT_VERSION, "at": time.time(),
                                                       "changed": dict_builder.CHANGED}), encoding="utf-8")
            return True

        def done(changed):
            self.dict_running = False
            self._stamp("dict_update_at")
            if changed:
                import ko2en

                ko2en.reload()
                self._dict_step("ok", "새 리그 옵션 번역을 반영했어요")
                self.message.emit("번역 데이터 새로 갱신됨 (새 리그 옵션 반영)")
            else:
                self._dict_step("ok", "바뀐 내용 없음 (최신)")
                if manual:
                    self.message.emit("번역 데이터 — 바뀐 내용 없음 (최신)")

        def fail(msg):
            self.dict_running = False
            self._dict_step("warn", f"확인 실패 — 지금 데이터로 계속 써요 ({msg})")
            if manual:
                self.message.emit(f"번역 데이터 갱신 실패: {msg}")

        run_async(job, done, fail)
