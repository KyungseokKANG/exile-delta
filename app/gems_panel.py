"""캐릭터 화면의 '스킬 젬' 탭: 끼고 있는 젬 목록, 레벨·퀄리티·사용 여부 변경, 젬마다 레벨 ±1 / 퀄리티 +5 영향.

바꾼 값은 PoB 빌드에 저장되고(다른 수정과 같음) 맨 위 계산 결과에 바로 반영된다.
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QRadioButton, QSpinBox, QVBoxLayout, QWidget)

from pob import config_ko

POS, NEG, DIM = "#7fc46a", "#e0644c", "#968b7a"


def gem_ko(name: str) -> str:
    ko = config_ko._load_names().get(name, "")
    return f"{ko} <span style='color:{DIM}; font-size:9pt'>{html.escape(name)}</span>" if ko and ko != name else html.escape(name)


class GemsCard:
    def __init__(self, page, host: QVBoxLayout):
        self.page = page
        self.client = page.client
        self.impact: dict | None = None
        self.impact_stale = True
        self.busy_impact = False
        self.cid = None
        self.visible = False
        self._gen = 0  # 빌드가 바뀔 때마다 +1 (나눠 계산하는 도중 바뀌면 그 결과는 버림)

        top = QHBoxLayout()
        self.info = QLabel()
        self.info.setObjectName("SectionLabel")
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.TextFormat.RichText)
        top.addWidget(self.info, 1)
        self.btn = QPushButton("레벨·퀄리티 영향 다시 계산")
        self.btn.setToolTip("젬마다 레벨 +1 / -1, 퀄리티 +5 했을 때 DPS·EHP 변화를 계산합니다 (몇 초 걸림)")
        self.btn.clicked.connect(self.compute_impact)
        top.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignTop)
        host.addLayout(top)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(4)
        host.addWidget(self.grid_host)
        self._auto = QTimer(singleShot=True, interval=900, timeout=self._auto_impact)

    # ------------------------------------------------------------ 상태
    def on_summary(self, cid: str) -> None:
        """계산 결과가 바뀔 때마다 (목록 다시 그림, 영향값은 '예전 값' 표시 후 탭이 보이면 다시 계산)."""
        if cid != self.cid:
            self.cid = cid
            self.impact = None
        self.impact_stale = True
        self._gen += 1
        self.render()
        if self.visible:
            self._auto.start()

    def on_shown(self, shown: bool) -> None:
        self.visible = shown
        if shown:
            self.render()
            if self.impact is None or self.impact_stale:
                self._auto.start()

    def _auto_impact(self) -> None:
        if self.visible and self.impact_stale:
            self.compute_impact()

    def compute_impact(self) -> None:
        c = self.page._cur()
        if c is None or self.client.state != "ready" or self.busy_impact:
            return
        self.busy_impact = True
        self.btn.setEnabled(False)
        self.btn.setText("계산 중…")
        cid = c["id"]
        gen = self._gen
        self.page._ensure_loaded()

        def ok(r):
            self.busy_impact = False
            self.btn.setEnabled(True)
            self.btn.setText("레벨·퀄리티 영향 다시 계산")
            if cid != self.cid:
                return
            self.impact = r
            self.impact_stale = False
            self.render()

        def err(m):
            self.busy_impact = False
            self.btn.setEnabled(True)
            self.btn.setText("레벨·퀄리티 영향 다시 계산")
            if m is None:  # 도중에 빌드가 바뀜 → 잠시 뒤 처음부터
                if self.visible and self.impact_stale:
                    self._auto.start()
                return
            self.info.setText(f"영향 계산 실패: {html.escape(m)}")

        # 젬 2개씩 나눠 계산 (조각 사이에 Ctrl+C 비교·장비 변경이 먼저 처리됨)
        self.client.call_chunks("gem_impact", {}, 2, ok, err,
                                alive=lambda: self._gen == gen and self.cid == cid)

    # ------------------------------------------------------------ 표시
    def _delta(self, base: dict, out: dict | None, label: str) -> str:
        if not out:
            return ""
        dk = "FullDPS" if base.get("FullDPS") else "CombinedDPS"
        cells = []
        for key, nm in ((dk, "DPS"), ("TotalEHP", "EHP")):
            a, b = base.get(key) or 0.0, out.get(key) or 0.0
            if not a or a >= 1e299 or b >= 1e299:
                continue
            p = (b - a) / a * 100
            if abs(p) < 0.05:
                continue
            col = POS if p > 0 else NEG
            cells.append(f"{nm} <b style='color:{col}'>{p:+.1f}%</b>")
        from statfmt import maxhit_cells

        mh = maxhit_cells(base, out)
        if mh:
            cells.append(f"<span style='color:{DIM}'>최대피격</span> " + " ".join(mh))
        if not cells:
            return ""
        return f"<span style='color:#c8a96a'>{label}</span> " + " &nbsp;".join(cells)

    @staticmethod
    def _clear(lay) -> None:
        """레이아웃 비우기 — 안에 든 하위 레이아웃(레벨·퀄리티·단계 칸 묶음)의 위젯까지 지움."""
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.deleteLater()
            elif it.layout():
                GemsCard._clear(it.layout())
                it.layout().deleteLater()

    def render(self) -> None:
        # 다시 그려도 스크롤 위치 그대로: 입력 중인 칸이 지워지면 포커스가 다른 칸(맨 밑 등)으로 넘어가며
        # 스크롤이 따라가고, 내용이 잠깐 비면서 위치도 줄어듦 → 포커스를 먼저 빼고, 다 그린 뒤 위치 복원
        sb = self.page.scroll.verticalScrollBar()
        pos = sb.value()
        host = self.grid.parentWidget()
        fw = QApplication.focusWidget()
        if fw is not None and host is not None and host.isAncestorOf(fw):
            fw.clearFocus()
        try:
            self._render()
        finally:
            sb.setValue(pos)
            QTimer.singleShot(0, lambda: sb.setValue(pos))

    def _render(self) -> None:
        self._clear(self.grid)
        c = self.page._cur() or {}
        s = c.get("summary") or {}
        groups = s.get("groups") or []
        ready = self.client.state == "ready"
        main = s.get("mainSocketGroup")
        imp = {(e["group"], e["gem"]): e for e in (self.impact or {}).get("gems") or []}
        base = (self.impact or {}).get("base") or {}
        stale = (f" &nbsp;<span style='color:#e8b65a'>· 값이 바뀌어 영향값을 다시 계산하는 중입니다</span>"
                 if self.impact and self.impact_stale else "")
        self.info.setText(
            "◉ = 주 스킬 · 레벨·퀄리티를 바꾸면 바로 계산되어 위 결과에 반영 · 젬 체크 해제 = 그 젬을 끈 상태"
            f"<br><span style='color:{DIM}'>오른쪽: 레벨 +1 / -1, 퀄리티 +5 했을 때 변화 "
            f"(Full DPS 가 있으면 Full DPS 기준)</span>{stale}")
        row = 0
        for gi, g in enumerate(groups, start=1):
            gems = g.get("gems") or []
            if not gems:
                continue
            actives = [x["name"] for x in gems if not x.get("support")]
            tags = []
            if gi == main:
                tags.append("<span style='color:#ead197'>주 스킬</span>")
            if g.get("includeInFullDPS"):
                tags.append("<span style='color:#c8a96a'>Full DPS</span>")
            if not g.get("enabled", True):
                tags.append(f"<span style='color:{NEG}'>그룹 꺼짐</span>")
            import skillnames
            from overlay import SLOT_KO

            title = html.escape(skillnames.group_label(g.get("label") or ", ".join(actives)) or "(빈 그룹)")
            slot_ko = SLOT_KO.get(g.get("slot") or "", g.get("slot") or "")
            # 그룹 머리줄: 주 스킬(라디오) · 제목 · 사용 · Full DPS 포함
            h = QWidget()
            hl = QHBoxLayout(h)
            hl.setContentsMargins(0, 2, 0, 2)
            hl.setSpacing(8)
            rb = QRadioButton()
            rb.setChecked(gi == main)
            rb.setEnabled(ready and bool(actives))
            rb.setToolTip("주 스킬로 선택 (위쪽 DPS 계산 대상)")
            rb.toggled.connect(lambda on, gi=gi: on and self.page._set_main(gi))
            hl.addWidget(rb)
            tl = QLabel(f"<b>{title}</b> <span style='color:{DIM}'>· {html.escape(slot_ko or '아이템/기타')}</span>"
                        + (" &nbsp;" + " · ".join(tags) if tags else ""))
            tl.setTextFormat(Qt.TextFormat.RichText)
            tl.setObjectName("ConfigSub")
            hl.addWidget(tl, 1)
            en = QCheckBox("그룹 사용")
            en.setToolTip("이 소켓 그룹 사용 여부 (오라·버프 등은 EHP/DPS 에 영향)")
            en.setChecked(bool(g.get("enabled", True)))
            en.setEnabled(ready)
            en.toggled.connect(lambda on, gi=gi: self.page._set_group(gi, enabled=on))
            fd = QCheckBox("Full DPS 포함")
            fd.setToolTip("Full DPS 합산에 포함 (여러 스킬을 같이 쓰는 빌드)")
            fd.setChecked(bool(g.get("includeInFullDPS")))
            fd.setEnabled(ready and bool(actives))
            fd.toggled.connect(lambda on, gi=gi: self.page._set_group(gi, full_dps=on))
            hl.addWidget(en)
            hl.addWidget(fd)
            if row > 0:
                # 소켓 그룹(메인 스킬) 사이 여백 + 옅은 구분선
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet("color: #2c251c; background: #2c251c; max-height: 1px; margin: 0;")
                self.grid.setRowMinimumHeight(row, 26)
                self.grid.addWidget(sep, row, 0, 1, 5, Qt.AlignmentFlag.AlignVCenter)
                row += 1
            self.grid.addWidget(h, row, 0, 1, 5)
            row += 1
            knobs = g.get("knobs") or []
            if isinstance(knobs, dict):  # (Lua 표 → 번호 키 dict 로 올 때)
                knobs = [knobs[k] for k in sorted(knobs, key=lambda x: int(x))]
            for ii, under, orphan, sk in self._order(g, gems):
                gem = gems[ii - 1]
                from_item = bool(gem.get("fromItem"))
                chk = QCheckBox()
                chk.setChecked(bool(gem.get("enabled", True)))
                chk.setEnabled(ready and not from_item)
                chk.toggled.connect(lambda on, gi=gi, ii=ii: self._set(gi, ii, enabled=on))
                self.grid.addWidget(chk, row, 0)
                if under:
                    label = "&nbsp;&nbsp;&nbsp;└ " + gem_ko(gem["name"])
                elif orphan:
                    label = (gem_ko(gem["name"]) +
                             f" <span style='color:{DIM}; font-size:9pt'>(붙는 스킬 없음)</span>")
                else:
                    label = gem_ko(gem["name"])
                name = QLabel(label)
                name.setTextFormat(Qt.TextFormat.RichText)
                name.setStyleSheet(f"color: {'#9fb5ff' if gem.get('support') else '#ddd5c6'};")
                if under:
                    name.setToolTip("위 스킬에 붙는 보조젬 (같은 보조젬이 여러 스킬에 붙으면 스킬마다 보여요 — 한 곳에서 바꾸면 같이 바뀜)")
                self.grid.addWidget(name, row, 1)
                lv = QSpinBox()
                lv.setRange(1, 40)
                lv.setValue(int(gem.get("level") or 1))
                lv.setPrefix("Lv ")
                lv.setToolTip(f"젬 레벨 (일반 최대 {gem.get('maxLevel') or 20}, 타락으로 +1)")
                lv.setEnabled(ready and not from_item)
                lv.setFixedWidth(84)
                qu = QSpinBox()
                qu.setRange(0, 40)
                qu.setValue(int(gem.get("quality") or 0))
                qu.setSuffix(" %")
                qu.setToolTip("젬 퀄리티 (일반 최대 20%, 타락 23%)")
                qu.setEnabled(ready and not from_item)
                qu.setFixedWidth(76)
                # 화살표·입력 모두: 마지막 값만 잠시 뒤에 계산 (연속 클릭 시 여러 번 계산하지 않게)
                lv.valueChanged.connect(lambda v, gi=gi, ii=ii, cur=gem.get("level"): self._later(
                    (gi, ii, "level"), lambda: v != cur and self._set(gi, ii, level=v)))
                qu.valueChanged.connect(lambda v, gi=gi, ii=ii, cur=gem.get("quality"): self._later(
                    (gi, ii, "quality"), lambda: v != cur and self._set(gi, ii, quality=v)))
                box = QHBoxLayout()
                box.setSpacing(6)
                box.addWidget(lv)
                box.addWidget(qu)
                # 단계 수 · 활성 지뢰 수 · 토템 수 — 상단 주 스킬 줄과 같은 값 (한쪽 바꾸면 같이 바뀜)
                kn = knobs[sk - 1] if 0 < sk <= len(knobs) and isinstance(knobs[sk - 1], dict) else None
                import skill_knobs
                for key, val, lo, hi in skill_knobs.spins(kn):
                    sp = skill_knobs.make_spin(
                        key, val, lo, hi, lambda k, v, gi=gi, sk=sk: self.page.set_skill_knob(gi, sk, k, v), kn)
                    sp.setPrefix(skill_knobs.label(key, kn) + " ")
                    sp.setEnabled(ready)
                    box.addWidget(sp)
                self.grid.addLayout(box, row, 2)
                e = imp.get((gi, ii))
                if e:
                    # 변화가 있는 것만 한 줄씩 (Lv+1 / Lv-1 / 퀄+5) — 최대 피격 5속성까지 넣으면 길어서 줄을 나눔
                    lines = [x for x in (self._delta(base, e.get("up"), "Lv+1"),
                                         self._delta(base, e.get("down"), "Lv-1"),
                                         self._delta(base, e.get("qual"), "퀄+5")) if x]
                    txt = "<br>".join(lines) if lines else f"<span style='color:{DIM}'>레벨·퀄리티 바꿔도 변화 없음</span>"
                    style = "opacity:0.5;" if self.impact_stale else ""
                    txt = f"<span style='{style}'>{txt}</span>"
                elif from_item:
                    txt = f"<span style='color:{DIM}'>아이템이 주는 스킬</span>"
                elif not gem.get("enabled", True) or not g.get("enabled", True):
                    txt = f"<span style='color:{DIM}'>꺼져 있음</span>"
                else:
                    txt = f"<span style='color:{DIM}'>{'계산 중…' if self.busy_impact else ''}</span>"
                lab = QLabel(txt)
                lab.setTextFormat(Qt.TextFormat.RichText)
                lab.setWordWrap(True)
                self.grid.addWidget(lab, row, 3)
                row += 1
        self.grid.setColumnStretch(3, 1)
        if not groups:
            self.grid.addWidget(QLabel("PoB 엔진에서 스킬을 읽는 중…"), 0, 0, 1, 4)

    @staticmethod
    def _order(g: dict, gems: list[dict]) -> list[tuple[int, bool, bool]]:
        """보여줄 순서 [(젬 번호 1부터, 액티브 밑의 보조젬인지, 붙는 스킬 없는 보조젬인지)].
        액티브마다 그 스킬에 실제로 붙는 보조젬을 바로 밑에 (PoB 판정 links). 같은 보조젬이 여러 액티브에 붙으면
        액티브마다 한 번씩. 어디에도 안 붙은 젬(꺼진 액티브 등)은 원래 순서로 뒤에."""
        links = g.get("links") or []
        if isinstance(links, dict):  # (빈 Lua 표는 {} 로 옴)
            links = list(links.values())
        if not links:
            return [(i, False, False, 0) for i in range(1, len(gems) + 1)]
        out, used = [], set()
        for ln in links:
            a = int(ln.get("active") or 0)
            if not 1 <= a <= len(gems):
                continue
            out.append((a, False, False, int(ln.get("skill") or 0)))
            used.add(a)
            sups = ln.get("supports") or []
            if isinstance(sups, dict):
                sups = list(sups.values())
            for sidx in sups:
                sidx = int(sidx)
                if 1 <= sidx <= len(gems):
                    out.append((sidx, True, False, 0))
                    used.add(sidx)
        rest = [i for i in range(1, len(gems) + 1) if i not in used]
        has_active_left = any(not gems[i - 1].get("support") for i in rest)
        for i in rest:
            sup = bool(gems[i - 1].get("support"))
            # 꺼진 액티브가 남아 있으면 그 밑으로 (원래 순서), 아니면 어디에도 안 붙는 보조젬
            out.append((i, sup and has_active_left, sup and not has_active_left, 0))
        return out

    def _later(self, key, fn) -> None:
        """연속 클릭은 마지막 값만, 단 젬·항목별로 따로 모아 한꺼번에 (다른 젬 변경이 덮이지 않게)."""
        if not hasattr(self, "_pending"):
            self._pending = {}
        self._pending[key] = fn
        if not hasattr(self, "_deb"):
            self._deb = QTimer(singleShot=True, interval=600, timeout=self._flush)
        self._deb.start()

    def _flush(self) -> None:
        fns, self._pending = list(self._pending.values()), {}
        for fn in fns:
            fn()

    def _set(self, group: int, gem: int, level=None, quality=None, enabled=None) -> None:
        args = {"group": group, "gem": gem}
        if level is not None:
            args["level"] = level
        if quality is not None:
            args["quality"] = quality
        if enabled is not None:
            args["enabled"] = enabled
        what = "레벨" if level is not None else "퀄리티" if quality is not None else "사용 여부"
        self.page._call("set_gem", args, f"젬 {what} 변경됨")
