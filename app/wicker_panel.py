"""캐릭터 화면의 '버들가지 제웅' 탭: 머리 / 몸통 / 팔 / 다리 부위를 골라 PoB 의 Wickerman 칸에 끼운다.

계정 가져오기(공개 API)에는 제웅이 안 들어오므로 여기서 직접 넣는다. 넣은 부위는 빌드에 저장되고
다시 가져오기를 해도 유지된다 (headless.lua 의 prefs).
"""
from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

import ko2en

DIM = "#968b7a"
SLOTS = (("Head", "머리"), ("Body", "몸통"), ("Arm", "팔"), ("Leg", "다리"))
TIERS = {1: "하급", 2: "일반", 3: "상급"}
RANGE_RE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _skel(line: str) -> str:
    """숫자·범위를 지운 옵션 뼈대 (지금 낀 아이템 줄 ↔ 목록 옵션 짝짓기용)."""
    return NUM_RE.sub("#", RANGE_RE.sub("#", line)).replace("+#", "#")


def _fmt(v: float) -> str:
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else f"{v:g}"


class _Row:
    """부위 하나: 부위 선택 · 옵션(등급) 선택 · 수치 칸."""

    def __init__(self, card: "WickerCard", slot: str, label: str, grid: QGridLayout, r: int):
        self.card, self.slot = card, slot
        self.entries: list[dict] = []  # 이 칸에 들어갈 수 있는 목록 전체
        self.spins: list = []
        lab = QLabel(label)
        lab.setStyleSheet("color:#ead197; font-size:10.5pt; font-weight:600;")
        lab.setMinimumWidth(44)
        grid.addWidget(lab, r, 0, Qt.AlignmentFlag.AlignTop)
        self.base = QComboBox()
        self.base.setMinimumWidth(240)
        self.base.setMaxVisibleItems(24)
        # 글자를 쳐서 찾기 (머리 부위만 60 개가 넘음): 한글·영문 이름 어디든 들어 있으면 보임
        self.base.setEditable(True)
        self.base.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.base.lineEdit().setPlaceholderText("부위 이름 검색")
        comp = self.base.completer()
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCompletionMode(comp.CompletionMode.PopupCompletion)
        self.base.currentIndexChanged.connect(self._on_base)
        grid.addWidget(self.base, r, 1, Qt.AlignmentFlag.AlignTop)
        self.opt = QComboBox()
        self.opt.setMinimumWidth(320)
        self.opt.currentIndexChanged.connect(self._on_opt)
        grid.addWidget(self.opt, r, 2, Qt.AlignmentFlag.AlignTop)
        self.vals_host = QWidget()
        self.vals = QVBoxLayout(self.vals_host)
        self.vals.setContentsMargins(0, 0, 0, 0)
        self.vals.setSpacing(3)
        grid.addWidget(self.vals_host, r, 3, Qt.AlignmentFlag.AlignTop)
        self._apply_t = QTimer(singleShot=True, interval=450, timeout=self._apply)
        self._quiet = False

    # ---------------------------------------------------------------- 목록
    def set_catalog(self, entries: list[dict]) -> None:
        self.entries = [e for e in entries if e.get("slot") == self.slot]
        bases: dict[str, str] = {}
        for e in self.entries:
            bases.setdefault(e["base"], ko2en.name_ko(e["base"]) or e["base"])
        self._quiet = True
        self.base.clear()
        self.base.addItem("(비어 있음)", "")
        for en, ko in sorted(bases.items(), key=lambda kv: kv[1]):
            self.base.addItem(f"{ko}  ·  {en}" if ko != en else en, en)
        self._quiet = False
        self._fill_opts()

    def _opts(self) -> list[dict]:
        b = self.base.currentData() or ""
        return sorted((e for e in self.entries if e["base"] == b), key=lambda e: -int(e.get("tier") or 2))

    def _fill_opts(self, pick: int = 0) -> None:
        self._quiet = True
        self.opt.clear()
        for e in self._opts():
            txt = " / ".join(ko2en.mod_ko(m) for m in e["mods"])
            self.opt.addItem(f"{TIERS.get(int(e.get('tier') or 2), '')} — {txt}", e)
        self.opt.setEnabled(self.opt.count() > 0)
        if self.opt.count():
            self.opt.setCurrentIndex(min(pick, self.opt.count() - 1))
        self._quiet = False
        self._fill_vals()

    def _fill_vals(self, values: list[float] | None = None) -> None:
        while self.vals.count():
            w = self.vals.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.spins = []
        e = self.opt.currentData()
        if not e:
            return
        it = iter(values or [])
        for line in e["mods"]:
            ranges = RANGE_RE.findall(line)
            if not ranges:
                continue
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            for lo_s, hi_s in ranges:
                lo, hi = float(lo_s), float(hi_s)
                dec = max(len(s.split(".")[1]) if "." in s else 0 for s in (lo_s, hi_s))
                if dec:
                    sp = QDoubleSpinBox()
                    sp.setDecimals(dec)
                    sp.setSingleStep(10 ** -dec)
                else:
                    sp = QSpinBox()
                sp.setRange(min(lo, hi), max(lo, hi)) if dec else sp.setRange(int(min(lo, hi)), int(max(lo, hi)))
                v = next(it, None)
                v = max(lo, hi) if v is None else v  # 처음 고르면 최대값
                sp.setValue(v if dec else int(round(v)))
                sp.setFixedWidth(72)
                sp.setToolTip(f"{_fmt(min(lo, hi))} ~ {_fmt(max(lo, hi))}")
                sp.valueChanged.connect(lambda _v: self._apply_t.start())
                h.addWidget(sp)
                self.spins.append(sp)
            short = ko2en.mod_ko(line)
            t = QLabel(html.escape(short))
            t.setStyleSheet(f"color:{DIM}; font-size:9pt;")
            h.addWidget(t, 1)
            self.vals.addWidget(row)

    # ---------------------------------------------------------------- 변경
    def _on_base(self, _i: int) -> None:
        if self._quiet:
            return
        self._fill_opts()
        self._apply()

    def _on_opt(self, _i: int) -> None:
        if self._quiet:
            return
        self._fill_vals()
        self._apply()

    def raw(self) -> str:
        e = self.opt.currentData() if self.base.currentData() else None
        if not e:
            return ""
        vals = iter(sp.value() for sp in self.spins)
        lines = [RANGE_RE.sub(lambda _m: _fmt(next(vals)), m) for m in e["mods"]]
        return "\n".join(["Rarity: RARE", e["name"], e["base"], f"Implicits: {len(lines)}", *lines])

    def _apply(self) -> None:
        self._apply_t.stop()
        self.card.put(self.slot, self.raw())

    # ---------------------------------------------------------------- 지금 낀 것 표시
    def show_item(self, item: dict | None) -> None:
        """엔진의 현재 상태로 칸을 맞춤 (사용자가 만든 것과 같으면 건드리지 않음 — 입력 중 포커스 유지)."""
        if self._apply_t.isActive():
            return
        if not item:
            if self.base.currentData():
                self._quiet = True
                self.base.setCurrentIndex(0)
                self._quiet = False
                self._fill_opts()
            return
        lines = list(item.get("lines") or [])
        sk = [_skel(x) for x in lines]
        opts_for = sorted((e for e in self.entries if e["base"] == item.get("base")),
                          key=lambda e: -int(e.get("tier") or 2))
        pick = next((i for i, e in enumerate(opts_for)
                     if e["name"] == item.get("name") and [_skel(m) for m in e["mods"]] == sk), None)
        if pick is None:
            pick = next((i for i, e in enumerate(opts_for) if [_skel(m) for m in e["mods"]] == sk), None)
        if pick is None:
            return
        e = opts_for[pick]
        vals: list[float] = []
        for m, cur in zip(e["mods"], lines):
            # 범위가 있던 자리의 숫자만 (뼈대가 같으므로 숫자 순서가 같음)
            toks = re.findall(r"R|-?\d+(?:\.\d+)?", RANGE_RE.sub("R", m))
            cur_nums = [float(x) for x in NUM_RE.findall(cur)]
            vals += [cur_nums[i] for i, tok in enumerate(toks) if tok == "R" and i < len(cur_nums)]
        bi = self.base.findData(item.get("base"))
        if bi < 0:
            return
        if (self.base.currentIndex() == bi and self.opt.currentIndex() == pick
                and len(self.spins) == len(vals) and all(abs(sp.value() - v) < 1e-6 for sp, v in zip(self.spins, vals))):
            return  # 이미 같은 상태
        self._quiet = True
        self.base.setCurrentIndex(bi)
        self._quiet = False
        self._fill_opts(pick)
        self._fill_vals(vals)


class WickerCard:
    def __init__(self, page, host: QVBoxLayout):
        self.page = page
        self.client = page.client
        self.cid = None
        self.visible = False
        self.catalog: list[dict] | None = None
        self._busy = False
        self._again = False

        self.info = QLabel()
        self.info.setObjectName("SectionLabel")
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.TextFormat.RichText)
        self.info.setText(
            "게임에서 버들가지 제웅에 붙인 부위를 여기서 골라 주세요. 계정에서 가져올 때는 제웅이 안 들어와서 "
            "직접 넣어야 계산에 들어가요. 넣은 부위는 다시 가져오기를 해도 그대로 남아요.")
        host.addWidget(self.info)
        self.state_lbl = QLabel()
        self.state_lbl.setObjectName("DefLine")
        self.state_lbl.setWordWrap(True)
        self.state_lbl.setTextFormat(Qt.TextFormat.RichText)
        host.addWidget(self.state_lbl)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#2c251c;")
        host.addWidget(line)
        gw = QWidget()
        grid = QGridLayout(gw)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(3, 1)
        self.rows = [_Row(self, s, lab, grid, i) for i, (s, lab) in enumerate(SLOTS)]
        host.addWidget(gw)
        bar = QHBoxLayout()
        bar.addStretch(1)
        clr = QPushButton("모두 빼기")
        clr.setToolTip("제웅 부위 4칸을 모두 비웁니다 (되돌리기로 취소 가능)")
        clr.clicked.connect(self.clear_all)
        bar.addWidget(clr)
        host.addLayout(bar)
        self._set_enabled(False)

    def _set_enabled(self, on: bool) -> None:
        for r in self.rows:
            for w in (r.base, r.opt, r.vals_host):
                w.setEnabled(on)

    # ---------------------------------------------------------------- 상태
    def on_summary(self, cid: str) -> None:
        self.cid = cid
        if self.visible:
            self.refresh()

    def on_shown(self, shown: bool) -> None:
        self.visible = shown
        if shown:
            self.refresh()

    def refresh(self) -> None:
        c = self.page._cur()
        if c is None or self.client.state != "ready":
            self.state_lbl.setText(f"<span style='color:{DIM}'>PoB 엔진을 준비하는 중이에요…</span>")
            return
        if self._busy:
            self._again = True
            return
        self._busy = True
        cid = c["id"]
        self.page._ensure_loaded()

        def ok(r):
            self._busy = False
            if self.catalog is None and r.get("catalog"):
                self.catalog = r["catalog"] or []
                for row in self.rows:
                    row.set_catalog(self.catalog)
            if self._again:
                self._again = False
                return self.refresh()
            cur = self.page._cur()
            if not cur or cur["id"] != cid:
                return
            st = r.get("state") or {}
            active = bool(st.get("active"))
            self._set_enabled(active and bool(self.catalog))
            if not active:
                self.state_lbl.setText(
                    f"<span style='color:#e0a24c'>이 빌드는 3.30 이전 패시브 트리라서 제웅 칸이 계산에 안 들어가요.</span>")
            else:
                slots = st.get("slots") or {}
                n = sum(1 for s, _ in SLOTS if slots.get(s))
                self.state_lbl.setText(f"<span style='color:{DIM}'>지금 붙인 부위 {n} / 4</span>")
            for row in self.rows:
                row.show_item((st.get("slots") or {}).get(row.slot))

        def err(m):
            self._busy = False
            self._again = False
            self.state_lbl.setText(f"제웅 정보를 읽지 못했어요: {html.escape(str(m))}")

        self.client.call("wicker", {"catalog": self.catalog is None}, ok, err)

    # ---------------------------------------------------------------- 넣기 / 빼기
    def put(self, slot: str, raw: str) -> None:
        c = self.page._cur()
        if c is None or self.client.state != "ready":
            return
        ko = dict(SLOTS).get(slot, slot)
        self.page._call("wicker_put", {"slot": slot, "raw": raw},
                        f"버들가지 제웅 {ko} {'바꿈' if raw else '뺌'}")

    def clear_all(self) -> None:
        for row in self.rows:
            if row.base.currentData():
                row._quiet = True
                row.base.setCurrentIndex(0)
                row._quiet = False
                row._fill_opts()
                self.put(row.slot, "")
