"""게임 위에 뜨는 판정 오버레이.

포커스를 뺏지 않는 항상-위 도구 창. 마우스 커서 근처에 뜨고, 일정 시간 뒤(마우스가 올라가 있지 않으면) 사라진다.
클릭하면 닫힌다. PoE 는 '창 모드 전체 화면(Windowed Fullscreen)' 이어야 위에 보인다.
"""
from __future__ import annotations

import html

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from itemcheck import ParsedItem, TabResult, fmt_val

COL = {"O": "#7fc46a", "△": "#e8c15a", "X": "#e0644c"}
RARITY_KO = {"Normal": "일반", "Magic": "마법", "Rare": "희귀", "Unique": "고유"}
SLOT_KO = {
    "Weapon 1": "무기 1", "Weapon 2": "무기 2 (보조)", "Weapon 1 Swap": "교체 무기 1", "Weapon 2 Swap": "교체 무기 2",
    "Helmet": "투구", "Body Armour": "갑옷", "Gloves": "장갑", "Boots": "장화", "Amulet": "목걸이",
    "Ring 1": "반지 1", "Ring 2": "반지 2", "Ring 3": "반지 3", "Belt": "허리띠",
}
DIM = "#b5aa95"


def slot_label(sl: dict) -> str:
    """PoB 슬롯 → 한글 이름 (주얼 슬롯은 트리 순서 번호, 심연 소켓은 어느 장비인지)."""
    s = sl.get("slot") or ""
    if sl.get("jewel"):
        return f"주얼 슬롯 {sl['jewel']}"
    if "Abyssal Socket" in s:
        owner, _, n = s.partition(" Abyssal Socket ")
        return f"{SLOT_KO.get(owner, owner)} 심연 소켓 {n}"
    if s.startswith("Flask "):
        return f"{s[6:]}번 플라스크"
    return SLOT_KO.get(s, sl.get("label") or s)
HIDE_MS = 12000
SPIN = "◐◓◑◒"


def fmt_big(v: float) -> str:
    a = abs(v)
    if a >= 1e6:
        return f"{v / 1e6:.2f}M"
    if a >= 1e4:
        return f"{v / 1e3:.1f}K"
    return f"{v:,.0f}"


class Overlay(QWidget):
    editRequested = Signal()

    def __init__(self, db):
        super().__init__(None)
        self.db = db
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.box = QFrame()
        self.box.setObjectName("Overlay")
        outer.addWidget(self.box)
        self.v = QVBoxLayout(self.box)
        self.v.setContentsMargins(14, 10, 14, 12)
        self.v.setSpacing(6)
        self.setFixedWidth(470)
        self._timer = QTimer(self, singleShot=True, timeout=self._maybe_hide)
        self.pob_label: QLabel | None = None
        self._token = 0
        self._spin = QTimer(self, interval=90, timeout=self._tick_spin)
        self._spin_i = 0
        self._spin_text = ""

    # ------------------------------------------------------------ 내용
    def _clear(self) -> None:
        while self.v.count():
            it = self.v.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.deleteLater()
            elif it.layout():
                lay = it.layout()
                while lay.count():
                    c = lay.takeAt(0)
                    if c.widget():
                        c.widget().hide()
                        c.widget().deleteLater()
                lay.deleteLater()

    def _label(self, text: str, obj: str = "", rich: bool = True) -> QLabel:
        lab = QLabel(text)
        if obj:
            lab.setObjectName(obj)
        lab.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
        lab.setWordWrap(True)
        return lab

    def show_item(self, item: ParsedItem, results: list[TabResult], pob_note: str | None,
                  char_name: str = "", loading: bool = False) -> int:
        """판정 표시. 반환값 token 은 이후 PoB 결과를 붙일 때 확인용."""
        self._token += 1
        self._clear()
        slot_ko = self.db.slot_name(item.slot) if item.slot else item.class_label
        head = QHBoxLayout()
        title = self._label(
            f"<span style='color:#ead197; font-weight:bold'>{html.escape(item.name)}</span>"
            + (f" <span style='color:{DIM}'>{html.escape(item.base)}</span>" if item.base != item.name else "")
            + f"<br><span style='color:{DIM}; font-size:10pt'>{html.escape(slot_ko)} · "
              f"{html.escape(RARITY_KO.get(item.rarity, item.rarity))}</span>",
            "OverlayTitle")
        head.addWidget(title, 1)
        edit = QPushButton("옵션변경")
        edit.setObjectName("OverlayEdit")
        edit.setCursor(Qt.CursorShape.PointingHandCursor)
        edit.setToolTip("이 아이템의 옵션을 추가·삭제·수정하며 DPS/EHP 변화를 확인하는 창을 엽니다")
        edit.clicked.connect(self.editRequested.emit)
        head.addWidget(edit, 0, Qt.AlignmentFlag.AlignTop)
        x = QLabel("✕")
        x.setObjectName("OverlayClose")
        head.addWidget(x, 0, Qt.AlignmentFlag.AlignTop)
        self.v.addLayout(head)

        if not item.slot:
            self.v.addWidget(self._label(f"<span style='color:{DIM}'>필터 대상이 아닌 아이템 종류입니다 "
                                         f"({html.escape(item.class_label)})</span>"))
        elif not results:
            self.v.addWidget(self._label(f"<span style='color:{DIM}'>옵션이 설정된 '{html.escape(slot_ko)}' 필터 탭이 없습니다. "
                                         f"아이템 필터에서 탭을 만들고 옵션을 추가해 주세요.</span>"))
        for r in results:
            c = r.counts
            vcol = COL[r.verdict]
            self.v.addWidget(self._label(
                f"<span style='color:{vcol}; font-size:15pt; font-weight:bold'>{r.verdict}</span>"
                f"&nbsp; <b>{html.escape(r.tab_name)}</b>"
                f"&nbsp; <span style='color:{DIM}'>O {c['O']} · △ {c['△']} · X {c['X']}</span>", "OverlayTab"))
            for o in r.options:
                e = self.db.get(o.key) or {}
                m = e.get("metric", "first")
                if o.got is None:
                    detail = f"<span style='color:{DIM}'>없음 · 기준 {fmt_val(m, o.want)}</span>"
                else:
                    tier = f" (T{o.got_tier})" if o.got_tier else ""
                    sign = "≥" if o.verdict == "O" else "&lt;"
                    detail = f"<b>{fmt_val(m, o.got)}</b>{tier} {sign} {fmt_val(m, o.want)}"
                row = self._label(
                    f"<span style='color:{COL[o.verdict]}; font-weight:bold'>{o.verdict}</span>&nbsp; "
                    f"{html.escape(o.text)} &nbsp;<span style='font-size:10pt'>{detail}</span>", "OverlayRow")
                self.v.addWidget(row)
        self.pob_label = None
        self._spin.stop()
        if pob_note is not None:
            box = QFrame()
            box.setObjectName("OverlayPob")
            pv = QVBoxLayout(box)
            pv.setContentsMargins(10, 8, 10, 8)
            pv.setSpacing(4)
            self.pob_title = self._label(
                f"<span style='color:#c8a96a; font-weight:bold'>장착 시 변화</span>"
                + (f" <span style='color:{DIM}'>· {html.escape(char_name)}</span>" if char_name else ""))
            pv.addWidget(self.pob_title)
            self.pob_label = self._label(f"<span style='color:{DIM}'>{html.escape(pob_note)}</span>", "OverlayRow")
            pv.addWidget(self.pob_label)
            self.v.addWidget(box)
            if loading:
                self._spin_text = pob_note
                self._spin_i = 0
                self._spin.start()
        self._place()
        return self._token

    def _tick_spin(self) -> None:
        if self.pob_label is None:
            self._spin.stop()
            return
        self._spin_i = (self._spin_i + 1) % len(SPIN)
        self.pob_label.setText(f"<span style='color:#c8a96a'>{SPIN[self._spin_i]}</span> "
                               f"<span style='color:{DIM}'>{html.escape(self._spin_text)}</span>")

    def set_pob(self, token: int, char_name: str, r: dict | None, err: str | None = None,
                untranslated: list[str] | None = None) -> None:
        if token != self._token or self.pob_label is None:
            return
        self._spin.stop()
        if err:
            self.pob_label.setText(f"<span style='color:{COL['X']}'>DPS/EHP 계산 실패: {html.escape(err)}</span>")
        else:
            body = self._pob_html(r or {})
            if untranslated:
                body += (f"<br><span style='color:{COL['△']}; font-size:10pt'>영문 변환 못 한 옵션 "
                         f"{len(untranslated)}줄은 계산에서 빠졌습니다: "
                         f"{html.escape(' / '.join(untranslated[:3]))}</span>")
            self.pob_label.setText(body)
        self._place(keep=True)

    @staticmethod
    def _maxhit_line(base: dict, st: dict) -> str:
        """최대 피격(PoB Max Hit): 물리 / 원소(화염·냉기·번개 중 최저) / 카오스 — 지금 → 바꾼 후 (변화율)."""
        from statfmt import MH, maxhit, pct

        a, b = maxhit(base), maxhit(st)
        parts = []
        for k, _key, ncol in MH:
            if k not in a or k not in b:
                continue
            p = pct(a[k], b[k])
            if p is None:
                continue
            if abs(p) >= 0.05:
                col = COL["O"] if p > 0 else COL["X"]
                parts.append(f"<span style='color:{ncol}'>{k}</span> {fmt_big(b[k])} "
                             f"<b style='color:{col}'>{p:+.1f}%</b>")
            else:
                parts.append(f"<span style='color:{ncol}'>{k}</span> <span style='color:{DIM}'>{fmt_big(b[k])}</span>")
        if not parts:
            return ""
        # 5개라 한 줄이 길어서: 최대 피격 머리말 + 다음 줄에 속성별
        return (f"<span style='color:{DIM}'>최대 피격</span><br>&nbsp;&nbsp;<span style='font-size:10pt'>"
                + " &nbsp;·&nbsp; ".join(parts) + "</span>")

    @staticmethod
    def _compact_html(base: dict, slots: list, dps_key: str) -> str:
        """주얼처럼 비교할 슬롯이 많을 때: 슬롯마다 한 줄, DPS 이득 큰 순."""

        def pct(st, key, b0):
            a, b = b0.get(key) or 0.0, st.get(key) or 0.0
            if a >= 1e299 or b >= 1e299 or not a:
                return None
            return (b - a) / a * 100

        def cell(v, name, big=False):
            if v is None:
                return f"<span style='color:{DIM}'>{name} —</span>"
            col = COL["O"] if v > 0.05 else COL["X"] if v < -0.05 else DIM
            size = "font-size:12.5pt; " if big else ""
            return f"<span style='color:{DIM}'>{name}</span> <span style='{size}color:{col}; font-weight:bold'>{v:+.1f}%</span>"

        rows = []
        for sl in slots:
            st, b0 = sl.get("stats") or {}, sl.get("base") or base
            rows.append((pct(st, dps_key, b0), pct(st, "TotalEHP", b0), sl))
        rows.sort(key=lambda t: -(t[0] if t[0] is not None else -1e9))
        head = ("플라스크 칸마다 바꿔 끼고 사용했을 때 (지금 플라스크도 사용 중 기준 · DPS 이득 큰 순)"
                if slots and slots[0].get("flask") else "끼고 있는 자리마다 바꿨을 때 (DPS 이득 큰 순)")
        out = [f"<span style='color:{DIM}; font-size:10pt'>{head}</span>"]
        for i, (d, e, sl) in enumerate(rows):
            st, b0 = sl.get("stats") or {}, sl.get("base") or base
            life = (st.get("Life") or 0) - (b0.get("Life") or 0)
            extra = ""
            if abs(life) >= 0.5:
                extra = f" · <span style='color:{DIM}'>생명력</span> <span style='color:{COL['O'] if life > 0 else COL['X']}'>{life:+.0f}</span>"
            from statfmt import maxhit_html

            mh = maxhit_html(b0, st, "최대피격")
            if mh:
                extra += f"<br>&nbsp;&nbsp;<span style='font-size:10pt'>{mh}</span>"
            rep = sl.get("replacing") or "빈 슬롯"
            star = "★ " if i == 0 and d is not None and d > 0.05 else ""
            out.append(f"<span style='color:#c8a96a'>{star}{html.escape(slot_label(sl))}</span>"
                       f" <span style='color:{DIM}; font-size:10pt'>← {html.escape(rep)}</span><br>"
                       f"&nbsp;&nbsp;{cell(d, 'DPS', True)} &nbsp;·&nbsp; {cell(e, 'EHP')}{extra}")
        return "<br>".join(out)

    @staticmethod
    def _pob_html(r: dict) -> str:
        if r.get("error"):
            return f"<span style='color:{DIM}'>PoB 가 이 아이템을 해석하지 못했습니다.</span>"
        base = r.get("base_stats") or {}
        slots = r.get("slots") or []
        if not slots:
            return f"<span style='color:{DIM}'>이 캐릭터에 장착할 수 있는 슬롯이 없습니다.</span>"
        dps_key = "FullDPS" if base.get("FullDPS") else "CombinedDPS"
        dps_name = "Full DPS" if dps_key == "FullDPS" else "DPS"
        if len(slots) > 2:
            out = Overlay._compact_html(base, slots, dps_key)
            if r.get("note") == "cluster":
                out = (f"<span style='color:{COL['△']}; font-size:10pt'>클러스터 주얼은 안의 패시브를 찍어야 효과가 나서, "
                       f"여기 값은 기본 옵션만 반영한 값입니다.</span><br>") + out
            return out
        out = []
        if r.get("note") == "flask":
            out.append(f"<span style='color:{DIM}; font-size:10pt'>플라스크는 사용 중일 때만 효과가 있어서, "
                       f"지금 플라스크와 이 플라스크를 둘 다 사용하는 상태로 비교합니다.</span>")
        for sl in slots:
            st = sl.get("stats") or {}
            b0 = sl.get("base") or base  # 플라스크: 지금 플라스크도 켠 상태 기준
            rep = sl.get("replacing") or "빈 슬롯"
            slot_name = slot_label(sl)
            lines = [f"<span style='color:#c8a96a'>{html.escape(slot_name)}</span>"
                     f" <span style='color:{DIM}; font-size:10pt'>← {html.escape(rep)}</span>"]
            from statfmt import swap_warnings
            lines += swap_warnings(b0, st)
            for key, name in ((dps_key, dps_name), ("TotalEHP", "EHP")):
                a, b = b0.get(key) or 0.0, st.get(key) or 0.0
                if a >= 1e299 or b >= 1e299:
                    lines.append(f"{name} <span style='color:{DIM}'>∞</span>")
                    continue
                d = b - a
                col = COL["O"] if d > 1e-6 else COL["X"] if d < -1e-6 else DIM
                pct = f"{d / a * 100:+.1f}%" if a else ("+∞" if d > 0 else "0%")
                lines.append(
                    f"<span style='color:{DIM}'>{name}</span> {fmt_big(a)} → <b>{fmt_big(b)}</b> "
                    f"<span style='color:{col}; font-size:14pt; font-weight:bold'>&nbsp;{pct}</span>")
            mh = Overlay._maxhit_line(b0, st)
            if mh:
                lines.append(mh)
            from statfmt import regen_cell

            rg = regen_cell(b0, st)
            if rg:
                lines.append(f"<span style='font-size:10.5pt'>{rg}</span>")
            cells = []
            for key, name in (("Life", "생명력"), ("EnergyShield", "에너지 보호막"), ("Mana", "마나"),
                              ("FireResist", "화염 저항"), ("ColdResist", "냉기 저항"),
                              ("LightningResist", "번개 저항"), ("ChaosResist", "카오스 저항")):
                a, b = b0.get(key) or 0.0, st.get(key) or 0.0
                d = b - a
                if abs(d) >= 0.5:
                    col = COL["O"] if d > 0 else COL["X"]
                    unit = "%" if "Resist" in key else ""
                    cells.append(f"{name} <span style='color:{col}'>{d:+.0f}{unit}</span>")
                elif "Resist" in key and key != "ChaosResist":
                    # 상한이라 저항 값은 그대로지만 넘친 양이 바뀜 (RF·화염 숙련처럼 '제한 없는 저항'을 쓰는 경우 중요)
                    oc = key.replace("Resist", "ResistOverCap")
                    do = (st.get(oc) or 0) - (b0.get(oc) or 0)
                    if abs(do) >= 0.5:
                        col = COL["O"] if do > 0 else COL["X"]
                        cells.append(f"{name} 초과분 <span style='color:{col}'>{do:+.0f}%</span>")
            if cells:
                lines.append(f"<span style='font-size:10pt'>{' · '.join(cells)}</span>")
            out.append("<br>".join(lines))
        return "<br><br>".join(out)

    # ------------------------------------------------------------ 표시/숨김
    def _place(self, keep: bool = False) -> None:
        self.v.activate()
        self.layout().activate()
        h = self.layout().heightForWidth(self.width())
        self.resize(self.width(), h if h > 0 else self.sizeHint().height())
        if not keep or not self.isVisible():
            pos = QCursor.pos()
            screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
            g = screen.availableGeometry()
            x = pos.x() + 24
            y = pos.y() - 20
            if x + self.width() > g.right():
                x = pos.x() - self.width() - 24
            x = max(g.left(), x)
            y = max(g.top(), min(y, g.bottom() - self.height()))
            self.move(QPoint(x, y))
        self.show()
        self.raise_()
        self._timer.start(HIDE_MS)

    def _maybe_hide(self) -> None:
        if self.geometry().contains(QCursor.pos()):
            self._timer.start(1500)
        else:
            self.hide()

    def mousePressEvent(self, e):
        self.hide()
