"""'장착템 옵션' 창: 옵션변경 창 옆에 붙는 작은 창. 지금 끼고 있는 장비의 옵션을 끄고 켜며 DPS · EHP 변화를 본다.

- 비교 대상 슬롯(반지면 반지 1 / 2)은 위 콤보에서 고름
- 줄마다 오른쪽에 '이 줄만 빼면' 잃는 양 (처음 한 번 계산)
- 체크를 끄면 0.3초 뒤 그 줄들을 뺀 장비로 다시 계산 → 옵션변경 창의 비교 기준(그 칸)을 이 상태로 바꿈
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from overlay import COL, DIM, SPIN, slot_label

KIND_TAG = {"enchant": "인챈트", "implicit": "고정"}
DEF_KO = {"Armour": "방어도", "Evasion": "회피", "EnergyShield": "에너지 보호막", "Ward": "수호"}


def _ko(line: str) -> str:
    try:
        import ko2en

        return ko2en.passive_ko(line)
    except Exception:  # noqa: BLE001
        return line


def _pct(d: dict, base: dict, key: str) -> float | None:
    a = base.get(key)
    v = d.get(key)
    if v is None or not a or abs(a) >= 1e299:
        return None
    return v / a * 100


class EquippedPanel(QWidget):
    def __init__(self, editor):
        super().__init__(None)
        self.editor = editor
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setObjectName("EditorWin")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(editor.styleSheet())
        self.setFixedWidth(500)
        self.slots: list[str] = []
        self.data: dict | None = None  # 처음 계산 (줄 목록 · 줄마다 기여도)
        self.off: set[tuple[str, int]] = set()
        self.nodef: set[str] = set()  # 끈 고유 방어력 (Armour / Evasion / EnergyShield / Ward)
        self._token = 0
        self._dk = "CombinedDPS"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = QFrame()
        box.setObjectName("Overlay")
        outer.addWidget(box)
        v = QVBoxLayout(box)
        v.setContentsMargins(14, 10, 14, 12)
        v.setSpacing(8)

        head = QHBoxLayout()
        t = QLabel("<span style='color:#c8a96a; font-weight:bold'>지금 끼고 있는 장비</span>")
        t.setTextFormat(Qt.TextFormat.RichText)
        head.addWidget(t)
        self.slot_combo = QComboBox()
        self.slot_combo.currentIndexChanged.connect(self._slot_changed)
        head.addWidget(self.slot_combo, 1)
        x = QPushButton("✕")
        x.setObjectName("EditorClose")
        x.setFixedSize(32, 30)
        x.setToolTip("닫기")
        x.clicked.connect(self.close_panel)
        head.addWidget(x)
        v.addLayout(head)

        self.name = QLabel()
        self.name.setTextFormat(Qt.TextFormat.RichText)
        self.name.setWordWrap(True)
        v.addWidget(self.name)
        hint = QLabel("체크를 끄면 그 옵션이 빠진 상태가 내 기준이 돼서, 옵션변경 창의 아이템을 그 기준과 비교해요. "
                      "오른쪽 숫자는 그 줄 하나만 뺐을 때 잃는 양이에요.")
        hint.setStyleSheet(f"color: {DIM}; font-size: 10pt;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.list_host = QVBoxLayout()
        self.list_host.setSpacing(3)
        lw = QWidget()
        lw.setLayout(self.list_host)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(lw)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        v.addWidget(self.scroll)

        btns = QHBoxLayout()
        self.all_on = QPushButton("전부 켜기")
        self.all_on.setObjectName("OverlayEdit")
        self.all_on.clicked.connect(self._all_on)
        btns.addWidget(self.all_on)
        btns.addStretch(1)
        v.addLayout(btns)

        res = QFrame()
        res.setObjectName("OverlayPob")
        rv = QVBoxLayout(res)
        rv.setContentsMargins(10, 8, 10, 8)
        self.result = QLabel()
        self.result.setTextFormat(Qt.TextFormat.RichText)
        self.result.setWordWrap(True)
        rv.addWidget(self.result)
        rv.addStretch(1)
        self.res_scroll = QScrollArea()
        self.res_scroll.setWidgetResizable(True)
        self.res_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.res_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.res_scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self.res_scroll.setWidget(res)
        v.addWidget(self.res_scroll)

        self._timer = QTimer(self, singleShot=True, interval=300, timeout=self._recompute)
        self._spin = QTimer(self, interval=90, timeout=self._tick)
        self._spin_i = 0
        self._spin_target: QLabel | None = None

    # ------------------------------------------------------------ 열기 / 위치
    def open_for(self, slots: list[dict]) -> None:
        """비교 결과의 슬롯 목록으로 채우고 옵션변경 창 옆에 띄움."""
        names = [s.get("slot") for s in slots if s.get("slot")]
        self.slot_combo.blockSignals(True)
        self.slot_combo.clear()
        for s in slots:
            if s.get("slot"):
                rep = s.get("replacing") or "빈 칸"
                self.slot_combo.addItem(f"{slot_label(s)} · {rep}", s["slot"])
        self.slot_combo.blockSignals(False)
        self.slot_combo.setVisible(len(names) > 1)
        self.slots = names
        self.follow()
        self.show()
        self._load()

    def follow(self) -> None:
        """옵션변경 창 오른쪽(자리 없으면 왼쪽)에 붙임."""
        ed = self.editor
        screen = QGuiApplication.screenAt(ed.geometry().center()) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        x = ed.x() + ed.width() + 6
        if x + self.width() > g.right():
            x = ed.x() - self.width() - 6
        x = max(g.left(), x)
        n = len((self.data or {}).get("lines") or []) or 5
        self.scroll.setFixedHeight(max(120, min(47 * n + 8, int(g.height() * 0.4))))
        self.res_scroll.setFixedHeight(max(160, min(290, int(g.height() * 0.3))))
        self.adjustSize()
        y = min(max(g.top(), ed.y()), g.bottom() - self.height())
        self.move(x, y)

    def close_panel(self) -> None:
        self.hide()
        self.editor.equip_closed()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()
            e.accept()
            return
        super().mousePressEvent(e)

    # ------------------------------------------------------------ 계산
    def _slot(self) -> str | None:
        return self.slot_combo.currentData() or (self.slots[0] if self.slots else None)

    def _slot_changed(self, _i: int) -> None:
        self._load()

    def _client(self):
        return self.editor.char_page.client

    def _start_spin(self, lab: QLabel) -> None:
        self._spin_target = lab
        self._spin_i = 0
        self._spin.start()
        self._tick()

    def _tick(self) -> None:
        if self._spin_target is None:
            return
        self._spin_i = (self._spin_i + 1) % len(SPIN)
        self._spin_target.setText(f"<span style='color:#c8a96a'>{SPIN[self._spin_i]}</span> "
                                  f"<span style='color:{DIM}'>PoB 로 계산 중</span>")

    def _load(self) -> None:
        """슬롯을 바꾸거나 새로 열 때: 줄 목록 + 줄마다 기여도."""
        slot = self._slot()
        self.off = set()
        self.nodef = set()
        self.data = None
        self.editor.set_equip_base(None)
        self._clear_rows()
        self._token += 1
        tok = self._token
        if not slot:
            self.name.setText(f"<span style='color:{DIM}'>비교할 칸이 없어요</span>")
            self.result.setText("")
            return
        self.name.setText("")
        self._start_spin(self.result)
        self._client().call("slot_variant", {"slot": slot, "off": [], "contrib": True},
                            lambda r: self._got_lines(tok, r), lambda m: self._err(tok, m))

    def _err(self, tok: int, msg: str) -> None:
        if tok != self._token:
            return
        self._spin.stop()
        self._spin_target = None
        if msg == "empty":
            self.name.setText(f"<span style='color:{DIM}'>이 칸은 비어 있어요</span>")
            self.result.setText("")
        else:
            self.result.setText(f"<span style='color:{COL['X']}'>계산 실패: {html.escape(str(msg))}</span>")

    def _got_lines(self, tok: int, r: dict) -> None:
        if tok != self._token:
            return
        self._spin.stop()
        self._spin_target = None
        if not r or r.get("error"):
            self._err(tok, (r or {}).get("error") or "?")
            return
        self.data = r
        base = r.get("base") or {}
        self._dk = "FullDPS" if base.get("FullDPS") else "CombinedDPS"
        q = r.get("quality")
        self.name.setText(f"<span style='color:#ead197; font-weight:bold'>{html.escape(r.get('name') or '')}</span>"
                          + (f" <span style='color:{DIM}; font-size:10pt'>퀄리티 {q}%</span>" if q else ""))
        self._build_rows()
        self._render(None)
        self.follow()  # 줄 수에 맞게 높이

    def _clear_rows(self) -> None:
        while self.list_host.count():
            it = self.list_host.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()

    def _rows_spec(self) -> list[dict]:
        """표시할 줄: 고유 방어력(방어구만) 먼저, 그다음 옵션 줄. key = ('def', 종류) 또는 (목록, 번호)."""
        out = []
        data = self.data or {}
        defs = data.get("defences") or {}
        for k in ("Armour", "Evasion", "EnergyShield", "Ward"):
            if defs.get(k):
                out.append({"key": ("def", k), "tag": "고유 방어", "text": f"{DEF_KO[k]} {defs[k]:,.0f}",
                            "tip": f"이 장비의 {DEF_KO[k]} 전체 (+수치 · % 증가 · 퀄리티 포함).\n"
                                   "끄면 그 몫을 통째로 빼고 계산해요.",
                            "d": (data.get("def_d") or {}).get(k) or {}})
        for ln in data.get("lines") or []:
            tag = "제작" if ln.get("crafted") else "분열" if ln.get("fractured") else KIND_TAG.get(ln.get("kind"), "")
            out.append({"key": (ln["list"], int(ln["idx"])), "tag": tag, "text": _ko(ln["line"]), "tip": ln["line"],
                        "d": ln.get("d") or {}, "unsupported": ln.get("unsupported")})
        return out

    def _build_rows(self) -> None:
        self._clear_rows()
        base = (self.data or {}).get("base") or {}
        for spec in self._rows_spec():
            key = spec["key"]
            row = QFrame()
            row.setObjectName("EditorRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(6, 3, 6, 3)
            h.setSpacing(6)
            chk = QCheckBox()
            chk.setChecked(key not in self.off)
            chk.toggled.connect(lambda on, key=key, row=row: self._toggle(key, on, row))
            h.addWidget(chk)
            if spec["tag"]:
                b = QLabel(spec["tag"])
                b.setObjectName("KindBadge")
                if key[0] == "def":
                    b.setStyleSheet("color: #c8a96a; border-color: #c8a96a;")
                h.addWidget(b)
            txt = QLabel(html.escape(spec["text"]))
            txt.setTextFormat(Qt.TextFormat.RichText)
            txt.setWordWrap(True)
            txt.setToolTip(spec["tip"])
            h.addWidget(txt, 1)
            d = spec["d"]
            cells = []
            for k, nm in ((self._dk, "DPS"), ("TotalEHP", "EHP")):
                p = _pct(d, base, k)
                if p is not None and abs(p) >= 0.05:
                    # d = 이 줄이 주는 몫 → 빼면 -p
                    col = COL["X"] if p > 0 else COL["O"]
                    cells.append(f"<span style='color:{DIM}'>{nm}</span> <span style='color:{col}'>{-p:+.1f}%</span>")
            rg = self._regen_loss(d, base)
            if rg is not None and abs(rg) >= 0.5:
                col = COL["X"] if rg > 0 else COL["O"]
                cells.append(f"<span style='color:{DIM}'>{self._regen_name}</span> <span style='color:{col}'>{-rg:+,.1f}/초</span>")
            if spec.get("unsupported"):
                cells.append(f"<span style='color:{COL['△']}'>PoB 미지원</span>")
            info = QLabel("<span style='font-size:9.5pt'>" + (" ".join(cells) or f"<span style='color:{DIM}'>변화 없음</span>")
                          + "</span>")
            info.setTextFormat(Qt.TextFormat.RichText)
            info.setToolTip("이 줄 하나만 빼면 이만큼 바뀌어요 (나머지는 다 켠 상태 기준)")
            h.addWidget(info)
            row.setProperty("off", key in self.off)
            self.list_host.addWidget(row)
        self.list_host.addStretch(1)

    _regen_name = "체젠"

    def _regen_loss(self, d: dict, base: dict) -> float | None:
        """이 줄이 주는 재생 몫. RF 등 지속 피해가 있으면 그걸 받는 쪽의 순 회복 기준 (PoB Net* 값)."""
        from statfmt import _pool, degen_pools, has_degen

        if has_degen(base):
            p = (degen_pools(base) or ["Life"])[0]
            self._regen_name = "순회복" if p == "Life" else f"순회복({_pool(p)[0]})"
            v = d.get(f"Net{p}Regen")
            return v if v is not None else d.get(f"{p}RegenRecovery")
        self._regen_name = "체젠"
        return d.get("LifeRegenRecovery")

    def _toggle(self, key, on: bool, row: QFrame) -> None:
        if on:
            self.off.discard(key)
        else:
            self.off.add(key)
        row.setProperty("off", not on)
        row.style().unpolish(row)
        row.style().polish(row)
        self._timer.start()

    def _all_on(self) -> None:
        if not self.off:
            return
        self.off = set()
        self._token += 1  # 계산 중이던 결과는 버림
        self._spin.stop()
        self._spin_target = None
        self.editor.set_equip_base(None)
        self._build_rows()
        self._render(None)

    def _recompute(self) -> None:
        slot = self._slot()
        if not slot or self.data is None:
            return
        if not self.off:
            self._token += 1
            self._spin.stop()
            self._spin_target = None
            self.editor.set_equip_base(None)
            self._render(None)
            return
        self._token += 1
        tok = self._token
        self._start_spin(self.result)
        lines = [list(k) for k in sorted(self.off) if k[0] != "def"]
        nodef = sorted(k[1] for k in self.off if k[0] == "def")
        self._client().call("slot_variant", {"slot": slot, "off": lines, "nodef": nodef},
                            lambda r: self._got_variant(tok, r), lambda m: self._err(tok, m))

    def _got_variant(self, tok: int, r: dict) -> None:
        if tok != self._token:
            return
        self._spin.stop()
        self._spin_target = None
        if not r or r.get("error"):
            self._err(tok, (r or {}).get("error") or "?")
            return
        # 옵션변경 창의 비교 기준을 '이 옵션들을 뺀 지금 장비'로 바꿈
        self.editor.set_equip_base(self._slot(), r.get("stats") or {}, "옵션 뺀 상태")
        self._render(r)

    def _render(self, r: dict | None) -> None:
        if r is None:
            self.result.setText(f"<span style='color:{DIM}'>옵션을 다 켠 지금 상태예요. 체크를 끄면 그 옵션이 빠진 상태를 "
                                f"내 기준으로 삼아서, 옵션변경 창의 아이템과 비교해요.</span>")
            return
        names = []
        for spec in self._rows_spec():
            if spec["key"] in self.off:
                names.append(f"고유 {DEF_KO[spec['key'][1]]}" if spec["key"][0] == "def" else spec["text"])
        from statfmt import change_cells

        cells = change_cells(r.get("base") or {}, r.get("stats") or {})
        self.result.setText(
            f"<span style='color:{COL['X']}; font-size:10pt'>끈 것</span> "
            f"<span style='font-size:10pt'>{html.escape(', '.join(names))}</span><br>"
            f"<span style='color:#c8a96a; font-size:10pt'>옵션변경 창은 이제 이 상태를 기준으로 비교해요.</span><br>"
            f"<span style='color:{DIM}; font-size:10pt'>원래 장착 상태와 비교하면</span> "
            f"<span style='font-size:10pt'>{' · '.join(cells) or '변화 없음'}</span>")
