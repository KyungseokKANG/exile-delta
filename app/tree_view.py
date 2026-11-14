"""패시브 트리 창: PoB Tree 탭처럼 노드를 찍고/빼면서 DPS·EHP 변화를 바로 확인.

노드 배치·경로·마스터리·계산은 모두 PoB 엔진(PassiveSpec/PassiveTree)이 하고,
여기서는 그림(QGraphicsView)과 조작만 담당한다.
"""
from __future__ import annotations

import html
import math
import re

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import ko2en
from character_page import DELTA_STATS, DIM, NEG, POS, fmt_big
from dialogs import confirm
from storage import load_settings, save_settings

TYPE_KO = {
    "Normal": "일반", "Notable": "주요 패시브", "Keystone": "핵심 패시브", "Mastery": "마스터리",
    "Socket": "주얼 슬롯", "ClassStart": "시작 지점", "AscendClassStart": "전직 시작",
}
RADIUS = {"Normal": 26, "Notable": 42, "Keystone": 60, "Mastery": 40, "Socket": 42,
          "ClassStart": 90, "AscendClassStart": 30}

C_EDGE = QColor("#3b342a")
C_EDGE_ALLOC = QColor("#c9a356")
C_EDGE_ADD = QColor("#6fd36f")
C_EDGE_DEL = QColor("#e0644c")
C_NODE = QColor("#26221c")
C_NODE_PEN = QColor("#5e5444")
C_REACH_PEN = QColor("#a08c62")
C_ALLOC = QColor("#c9a356")
C_ALLOC_PEN = QColor("#f4dc9c")
C_MASTERY_ALLOC = QColor("#7fc4b0")
C_SOCKET_PEN = QColor("#6f9fe0")
C_SOCKET_FILL = QColor("#4b78c0")
C_GRANTED = QColor("#a983e0")
C_ADD_FILL = QColor("#3f7a3a")
C_DEL_FILL = QColor("#a8402c")
C_MATCH = QColor("#4fd8e8")

# 노드 툴팁·결과에 보여줄 핵심 스탯
TIP_KEYS = ["FullDPS", "CombinedDPS", "TotalDPS", "TotalEHP", "Life", "EnergyShield", "Mana", "Ward",
            "FireResist", "ColdResist", "LightningResist", "ChaosResist", "Armour", "Evasion",
            "EffectiveSpellSuppressionChance", "EffectiveBlockChance", "EffectiveSpellBlockChance",
            "Str", "Dex", "Int"]
STAT_META = {k: (label, kind) for k, label, kind in DELTA_STATS}


def _shape(t: str, r: float) -> QPainterPath:
    p = QPainterPath()
    if t == "Mastery":
        p.moveTo(0, -r)
        p.lineTo(r, 0)
        p.lineTo(0, r)
        p.lineTo(-r, 0)
        p.closeSubpath()
    elif t == "Socket":
        pts = [QPointF(r * math.cos(math.pi / 8 + i * math.pi / 4), r * math.sin(math.pi / 8 + i * math.pi / 4))
               for i in range(8)]
        p.moveTo(pts[0])
        for q in pts[1:]:
            p.lineTo(q)
        p.closeSubpath()
    else:
        p.addEllipse(QPointF(0, 0), r, r)
    return p


def translate_lines(lines: list[str]) -> list[str]:
    """노드 효과 줄 → 한글. PoB 가 한 문장을 여러 줄로 나눈 경우 이어붙여서 다시 시도."""
    out, i = [], 0
    while i < len(lines):
        a = lines[i]
        k = ko2en.passive_ko(a)
        if k == a and i + 1 < len(lines):
            b = lines[i + 1]
            for joined in (a + "\n" + b, a + " " + b):
                kk = ko2en.passive_ko(joined)
                if kk != joined:
                    out.append(kk.replace("\n", " "))
                    i += 2
                    break
            else:
                out.append(k)
                i += 1
            continue
        out.append(k.replace("\n", " "))
        i += 1
    return out


def delta_cells(base: dict, new: dict, limit: int = 9) -> list[str]:
    cells = []
    for key in TIP_KEYS:
        label, kind = STAT_META.get(key, (key, "num"))
        a, b = base.get(key), new.get(key)
        if a is None and b is None:
            continue
        a, b = a or 0.0, b or 0.0
        if key == "FullDPS" and not a and not b:
            continue
        d = b - a
        if abs(d) < 1e-6 or abs(a) >= 1e299 or abs(b) >= 1e299:
            continue
        col = POS if d > 0 else NEG
        if kind == "pct":
            ds = f"{d:+.0f}%"
        elif kind == "big":
            pct = f" ({d / a * 100:+.1f}%)" if a else ""
            ds = f"{'+' if d >= 0 else '-'}{fmt_big(abs(d))}{pct}"
        else:
            ds = f"{d:+,.0f}"
        cells.append(f"{label} <span style='color:{col}'><b>{ds}</b></span>")
        if len(cells) >= limit:
            break
    from statfmt import maxhit_cells

    mh = maxhit_cells(base, new)
    if mh:
        cells.append("<br>최대피격 " + " ".join(mh))
    return cells


class NodeItem(QGraphicsPathItem):
    def __init__(self, n: dict):
        self.r = RADIUS.get(n["t"], 26)
        super().__init__(_shape(n["t"], self.r))
        self.n = n
        self.setPos(n["x"], n["y"])
        self.setZValue(2 if n["t"] in ("Normal", "Mastery") else 3)


class TreeCanvas(QGraphicsView):
    def __init__(self, win: "TreeWindow"):
        super().__init__()
        self.win = win
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setBackgroundBrush(QColor("#0d0b09"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self._press = None
        self._dragging = False
        self._last = None
        self.hover_id = None

    # ---- 확대/이동 ----
    def scale_now(self) -> float:
        return self.transform().m11()

    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120
        f = 1.18 ** steps
        s = self.scale_now()
        f = max(0.015 / s, min(1.6 / s, f))
        self.scale(f, f)
        self.win.on_zoom()

    def mousePressEvent(self, e):
        if e.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._press = (e.position(), e.button())
            self._last = e.position()
            self._dragging = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press is not None:
            if (e.position() - self._press[0]).manhattanLength() > 5:
                self._dragging = True
            if self._dragging:
                d = e.position() - self._last
                self._last = e.position()
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(d.x()))
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(d.y()))
                self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                return
        nid = self.node_at(e.position())
        if nid != self.hover_id:
            self.hover_id = nid
            self.win.on_hover(nid)
        if nid is not None:
            self.win.move_tip(e.position())
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if nid is not None else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._press is not None and not self._dragging:
            nid = self.node_at(e.position())
            if nid is not None:
                self.win.on_click(nid, self._press[1], e.globalPosition().toPoint())
        self._press = None
        self._dragging = False
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(e)

    def leaveEvent(self, e):
        if self.hover_id is not None:
            self.hover_id = None
            self.win.on_hover(None)
        super().leaveEvent(e)

    def node_at(self, pos) -> int | None:
        sp = self.mapToScene(pos.toPoint())
        s = self.scale_now()
        r = max(10.0 / s, 30.0)
        best, bd = None, None
        for it in self.scene().items(QRectF(sp.x() - r - 60, sp.y() - r - 60, 2 * r + 120, 2 * r + 120)):
            if isinstance(it, NodeItem):
                d = math.hypot(it.n["x"] - sp.x(), it.n["y"] - sp.y())
                lim = max(it.r * 1.1, r if it.n["t"] != "Mastery" else it.r)
                if d <= lim and (bd is None or d < bd):
                    best, bd = it.n["id"], d
        return best


class TreeWindow(QWidget):
    def __init__(self, page, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.page = page
        self.client = page.client
        self.setObjectName("TreeWin")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("#TreeWin { background: #15120e; }"
                           "#TreeSide { background: #1b1712; border-left: 1px solid #2c251c; }"
                           "#TreeTip { background: rgba(14,12,9,238); border: 1px solid #86704a; border-radius: 6px; }"
                           "#TreeTip QLabel { font-size: 10.5pt; }"
                           "#TreeSide QLabel { font-size: 10.5pt; }")
        self.setWindowTitle("패시브 트리")
        self.cid: str | None = None
        self.layout_key = None
        self.nodes: dict[int, NodeItem] = {}
        self.edges: list[tuple[QGraphicsPathItem, int, int, bool]] = []
        self.labels: list[QGraphicsSimpleTextItem] = []
        self.extras: list = []
        self.state: dict = {}
        self.alloc: set[int] = set()
        self.granted: set[int] = set()
        self.matches: list[int] = []
        self.match_i = -1
        self.undo: list[dict] = []
        self.busy = False
        self.pv_cache: dict[int, dict] = {}
        self.pv_inflight = False
        self.pv_want: int | None = None
        self.hl_add: set[int] = set()
        self.hl_del: set[int] = set()

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.view = TreeCanvas(self)
        root.addWidget(self.view, 1)

        side = QFrame()
        side.setObjectName("TreeSide")
        side.setFixedWidth(340)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(16, 14, 16, 14)
        sv.setSpacing(10)
        self.h_name = QLabel()
        self.h_name.setObjectName("CharName")
        self.h_sub = QLabel()
        self.h_sub.setObjectName("CharSub")
        self.h_pts = QLabel()
        self.h_pts.setTextFormat(Qt.TextFormat.RichText)
        sv.addWidget(self.h_name)
        sv.addWidget(self.h_sub)
        sv.addWidget(self.h_pts)

        self.search = QLineEdit()
        self.search.setPlaceholderText("노드 검색 (이름·효과, 한글/영문)")
        self.search.textChanged.connect(self._on_search)
        self.search.returnPressed.connect(self._next_match)
        self.s_info = QLabel()
        self.s_info.setObjectName("SectionLabel")
        sv.addWidget(self.search)
        sv.addWidget(self.s_info)

        t = QLabel("원래 트리 대비")
        t.setObjectName("CardTitle")
        sv.addWidget(t)
        self.stats_lab = QLabel()
        self.stats_lab.setTextFormat(Qt.TextFormat.RichText)
        self.stats_lab.setWordWrap(True)
        sv.addWidget(self.stats_lab)

        row = QHBoxLayout()
        self.undo_btn = QPushButton("되돌리기")
        self.undo_btn.setToolTip("마지막 변경 취소 (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.do_undo)
        self.orig_btn = QPushButton("원래 트리로")
        self.orig_btn.setToolTip("처음 불러온(또는 기준으로 정한) 트리로 되돌립니다")
        self.orig_btn.clicked.connect(self.do_orig)
        row.addWidget(self.undo_btn)
        row.addWidget(self.orig_btn)
        sv.addLayout(row)
        row2 = QHBoxLayout()
        base_btn = QPushButton("기준으로 정하기")
        base_btn.setToolTip("비교 기준(원래 트리)을 지금 트리로 바꿉니다")
        base_btn.clicked.connect(self.set_baseline)
        url_btn = QPushButton("트리 링크 불러오기")
        url_btn.setToolTip("pathofexile.com 패시브 트리 링크(또는 PoB 트리 링크)를 붙여넣어 그 트리로 바꿉니다")
        url_btn.clicked.connect(self.import_url)
        row2.addWidget(base_btn)
        row2.addWidget(url_btn)
        sv.addLayout(row2)
        reset_btn = QPushButton("트리 전체 초기화")
        reset_btn.setObjectName("Danger")
        reset_btn.clicked.connect(self.do_reset)
        sv.addWidget(reset_btn)

        help_lab = QLabel(
            f"<span style='color:{DIM}'>좌클릭: 찍기 / 해제 (경로 자동)<br>"
            "마스터리: 클릭해서 효과 선택<br>드래그: 이동 · 휠: 확대/축소<br>"
            "노드에 마우스를 올리면 찍었을 때 변화를 계산합니다.<br><br>"
            "여기서 바꾼 트리는 바로 저장되고, Ctrl+C 아이템 비교도 이 트리 기준으로 계산됩니다.</span>")
        help_lab.setTextFormat(Qt.TextFormat.RichText)
        help_lab.setWordWrap(True)
        sv.addWidget(help_lab)
        sv.addStretch(1)
        self.status = QLabel()
        self.status.setObjectName("SectionLabel")
        self.status.setWordWrap(True)
        sv.addWidget(self.status)
        root.addWidget(side)

        self.tip = QFrame(self.view.viewport())
        self.tip.setObjectName("TreeTip")
        tv = QVBoxLayout(self.tip)
        tv.setContentsMargins(12, 10, 12, 10)
        self.tip_lab = QLabel()
        self.tip_lab.setTextFormat(Qt.TextFormat.RichText)
        self.tip_lab.setWordWrap(True)
        self.tip_lab.setFixedWidth(380)
        self.tip_lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.tip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        tv.addWidget(self.tip_lab)
        self.tip.hide()
        self._tip_pos = QPointF(0, 0)

        self.pv_timer = QTimer(self)
        self.pv_timer.setSingleShot(True)
        self.pv_timer.setInterval(110)
        self.pv_timer.timeout.connect(self._request_preview)
        QShortcut(QKeySequence("Ctrl+Z"), self, self.do_undo)
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: (self.search.setFocus(), self.search.selectAll()))
        self._restore_geometry()

    # ================================================================ 창
    def _restore_geometry(self) -> None:
        g = (load_settings().get("tree_window") or {})
        scr = QApplication.primaryScreen().availableGeometry()
        w, h = min(g.get("w", 1400), scr.width() - 40), min(g.get("h", 900), scr.height() - 40)
        self.resize(max(900, w), max(600, h))
        x, y = g.get("x"), g.get("y")
        if x is not None and y is not None and any(s.availableGeometry().contains(x + 50, y + 20) for s in QApplication.screens()):
            self.move(x, y)
        else:
            self.move(scr.center().x() - self.width() // 2, scr.center().y() - self.height() // 2)

    def closeEvent(self, e):
        try:
            s = load_settings()
            g = self.geometry()
            s["tree_window"] = {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}
            save_settings(s)
        except OSError:
            pass
        super().closeEvent(e)

    def _char(self) -> dict | None:
        return next((x for x in self.page.store.chars if x["id"] == self.cid), None)

    def bind(self, c: dict) -> None:
        """캐릭터 연결 (창을 열 때 / 캐릭터 탭이 바뀔 때)."""
        if c is None:
            return
        same = c["id"] == self.cid
        self.cid = c["id"]
        self.setWindowTitle(f"패시브 트리 — {c['name']}")
        if not same:
            self.undo.clear()
            self.layout_key = None
        self.page._ensure_loaded()
        self.status.setText("트리 불러오는 중…")
        cid = self.cid
        self.client.call("tree_layout", {}, lambda r: self._on_layout(cid, r, fit=not same),
                         lambda m: self.status.setText(f"트리 불러오기 실패: {m}"))

    # ================================================================ 그리기
    def _on_layout(self, cid: str, r: dict, fit: bool = True) -> None:
        if cid != self.cid:
            return
        lay = r.get("layout") or {}
        st = r.get("state") or {}
        self._build_scene(lay)
        self.layout_key = st.get("key")
        c = self._char()
        if c is not None and not c.get("tree_orig"):
            c["tree_orig"] = {"snap": st.get("snapshot"), "stats": (c.get("summary") or {}).get("stats") or {}}
            self.page.store.save()
        self._apply_state(st)
        if fit:
            self._fit()
        self.status.setText("")

    def _build_scene(self, lay: dict) -> None:
        sc = self.view.scene()
        sc.clear()
        self.nodes.clear()
        self.edges.clear()
        self.labels.clear()
        self.extras.clear()
        radii = lay.get("orbitRadii") or [0, 82, 162, 335, 493, 662, 846]
        nodes = lay.get("nodes") or []
        byid = {n["id"]: n for n in nodes}
        for n in nodes:
            n["ko"] = translate_lines(n.get("sd") or [])
            n["search"] = (n["name"] + "\n" + "\n".join(n.get("sd") or []) + "\n" + "\n".join(n["ko"])).lower()
        # 전직 영역 배경
        for n in nodes:
            if n.get("ascStart"):
                rad = 720 if not n.get("bloodline") else 760
                e = sc.addEllipse(QRectF(n["gx"] - rad, n["gy"] - rad, 2 * rad, 2 * rad),
                                  QPen(QColor("#4a3d2a"), 10), QBrush(QColor("#17130e")))
                e.setZValue(-2)
                t = sc.addSimpleText(n.get("asc") or "")
                f = QFont("Malgun Gothic")
                f.setPixelSize(70)
                t.setFont(f)
                t.setBrush(QColor("#86704a"))
                br = t.boundingRect()
                t.setPos(n["gx"] - br.width() / 2, n["gy"] - rad - br.height() - 20)
                self.extras.append(t)
        # 연결선
        seen = set()
        for n in nodes:
            if n["t"] == "Mastery":
                continue
            for oid in n.get("l") or []:
                o = byid.get(oid)
                if o is None or o["t"] == "Mastery":
                    continue
                key = (min(n["id"], oid), max(n["id"], oid))
                if key in seen or (n.get("asc") or "") != (o.get("asc") or ""):
                    continue
                if n["t"] == "ClassStart" or o["t"] == "ClassStart":
                    continue
                seen.add(key)
                path = QPainterPath(QPointF(n["x"], n["y"]))
                same_orbit = (n.get("o") and n.get("o") == o.get("o") and n.get("gx") == o.get("gx")
                              and n.get("gy") == o.get("gy") and n.get("a") is not None and o.get("a") is not None)
                if same_orbit:
                    rr = radii[n["o"]] if n["o"] < len(radii) else 0
                    a1, a2 = n["a"], o["a"]
                    d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
                    steps = max(4, int(abs(d) * rr / 30))
                    for i in range(1, steps + 1):
                        a = a1 + d * i / steps
                        path.lineTo(n["gx"] + math.sin(a) * rr, n["gy"] - math.cos(a) * rr)
                else:
                    path.lineTo(o["x"], o["y"])
                it = QGraphicsPathItem(path)
                it.setZValue(0)
                sc.addItem(it)
                self.edges.append((it, n["id"], oid, bool(n.get("asc"))))
        # 노드
        f = QFont("Malgun Gothic")
        f.setPixelSize(36)
        fk = QFont("Malgun Gothic")
        fk.setPixelSize(48)
        fk.setBold(True)
        for n in nodes:
            if n["t"] == "ClassStart":
                continue
            it = NodeItem(n)
            sc.addItem(it)
            self.nodes[n["id"]] = it
            if n["t"] in ("Notable", "Keystone") or (n.get("asc") and n["t"] != "AscendClassStart" and n["sd"]):
                if n["t"] == "Normal":
                    continue
                lab = QGraphicsSimpleTextItem(n["name"])
                lab.setFont(fk if n["t"] == "Keystone" else f)
                lab.setBrush(QColor("#d8c79d") if n["t"] == "Keystone" else QColor("#b9ab8c"))
                br = lab.boundingRect()
                lab.setPos(n["x"] - br.width() / 2, n["y"] + it.r + 8)
                lab.setZValue(4)
                lab.setData(0, n["t"])
                lab.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                sc.addItem(lab)
                self.labels.append(lab)
        # 시작 지점 (클래스)
        self.class_starts = [n for n in nodes if n["t"] == "ClassStart"]
        self._start_items = []
        rect = sc.itemsBoundingRect().adjusted(-1500, -1500, 1500, 1500)
        sc.setSceneRect(rect)
        self.on_zoom()

    def _draw_starts(self) -> None:
        sc = self.view.scene()
        for it in self._start_items:
            sc.removeItem(it)
        self._start_items = []
        start = self.state.get("startId")
        f = QFont("Malgun Gothic")
        f.setPixelSize(64)
        f.setBold(True)
        for n in self.class_starts:
            cur = n["id"] == start
            rad = 150 if cur else 110
            e = sc.addEllipse(QRectF(n["x"] - rad, n["y"] - rad, 2 * rad, 2 * rad),
                              QPen(QColor("#e8c27a" if cur else "#4a4032"), 18 if cur else 10),
                              QBrush(QColor("#3a2e1c" if cur else "#1a1712")))
            e.setZValue(1)
            self._start_items.append(e)
            if cur:
                t = sc.addSimpleText(self.state.get("className") or n["name"])
                t.setFont(f)
                t.setBrush(QColor("#ead197"))
                br = t.boundingRect()
                t.setPos(n["x"] - br.width() / 2, n["y"] - br.height() / 2)
                t.setZValue(5)
                self._start_items.append(t)

    def on_zoom(self) -> None:
        s = self.view.scale_now()
        for lab in self.labels:
            lab.setVisible(s >= (0.11 if lab.data(0) == "Keystone" else 0.28))
        self._restyle()

    def _restyle(self) -> None:
        s = max(self.view.scale_now(), 1e-3)
        w_edge = max(9.0, 1.3 / s)
        w_alloc = max(16.0, 2.6 / s)
        w_hl = max(18.0, 3.0 / s)
        alloc, add, dele = self.alloc, self.hl_add, self.hl_del
        start = self.state.get("startId")
        for it, a, b, _asc in self.edges:
            in_a = a in alloc or a == start
            in_b = b in alloc or b == start
            if (a in dele and in_b) or (b in dele and in_a) or (a in dele and b in dele):
                pen = QPen(C_EDGE_DEL, w_hl)
            elif in_a and in_b:
                pen = QPen(C_EDGE_ALLOC, w_alloc)
            elif (a in add or in_a) and (b in add or in_b) and (a in add or b in add):
                pen = QPen(C_EDGE_ADD, w_hl)
            else:
                pen = QPen(C_EDGE, w_edge)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            it.setPen(pen)
        w_node = max(5.0, 1.2 / s)
        w_match = max(12.0, 3.0 / s)
        match = set(self.matches)
        for nid, it in self.nodes.items():
            n = it.n
            t = n["t"]
            is_alloc = nid in alloc
            reach = not is_alloc and any(l in alloc or l == start for l in n.get("l") or [])
            if nid in dele:
                fill, pen = C_DEL_FILL, QPen(C_EDGE_DEL, w_node * 1.6)
            elif nid in add:
                fill, pen = C_ADD_FILL, QPen(C_EDGE_ADD, w_node * 1.6)
            elif is_alloc:
                if t == "Mastery":
                    fill = C_MASTERY_ALLOC
                elif t == "Socket":
                    fill = C_SOCKET_FILL
                else:
                    fill = C_ALLOC
                pen = QPen(C_ALLOC_PEN, w_node * 1.3)
            elif nid in self.granted:
                fill, pen = C_GRANTED, QPen(QColor("#d6c0ff"), w_node)
            else:
                fill = C_NODE if t != "Mastery" else QColor("#1c1a17")
                pc = C_SOCKET_PEN if t == "Socket" else (C_REACH_PEN if reach else C_NODE_PEN)
                pen = QPen(pc, w_node)
            if nid in match:
                pen = QPen(C_MATCH, w_match)
            it.setBrush(QBrush(fill))
            it.setPen(pen)

    def _fit(self) -> None:
        pts = [self.nodes[i].n for i in self.alloc if i in self.nodes and not self.nodes[i].n.get("asc")]
        if not pts:
            st = next((n for n in self.class_starts if n["id"] == self.state.get("startId")), None)
            pts = [st] if st else [it.n for it in self.nodes.values()]
        xs, ys = [p["x"] for p in pts], [p["y"] for p in pts]
        r = QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)).adjusted(-900, -900, 900, 900)
        self.view.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)
        self.on_zoom()

    # ================================================================ 상태
    def _apply_state(self, st: dict) -> None:
        self.state = st
        self.alloc = set(int(x) for x in st.get("alloc") or [])
        self.granted = set(int(x) for x in st.get("granted") or [])
        self.pv_cache.clear()
        self.hl_add, self.hl_del = set(), set()
        self._draw_starts()
        self._restyle()
        self._render_side()
        if self.view.hover_id is not None:
            self.on_hover(self.view.hover_id)

    def _render_side(self) -> None:
        c = self._char() or {}
        s = c.get("summary") or {}
        st = self.state
        self.h_name.setText(c.get("name", ""))
        asc = st.get("ascendName") or ""
        cls = st.get("className") or ""
        self.h_sub.setText(f"Lv {s.get('level', '?')}  ·  {asc + ' (' + cls + ')' if asc and asc != 'None' else cls}")
        used, mx = st.get("used", 0), st.get("usedMax", 0)
        col = NEG if used > mx else "#ead197"
        au, am = st.get("ascUsed", 0), st.get("ascMax", 8)
        self.h_pts.setText(f"패시브 포인트 <b style='color:{col}'>{used}</b> / {mx}"
                           f" &nbsp;·&nbsp; 전직 <b style='color:{NEG if au > am else '#ead197'}'>{au}</b> / {am}")
        cur = s.get("stats") or {}
        base = (c.get("tree_orig") or {}).get("stats") or {}
        rows = []
        for key in ("FullDPS", "CombinedDPS", "TotalDPS", "TotalEHP", "Life", "EnergyShield", "Mana",
                    "FireResist", "ColdResist", "LightningResist", "ChaosResist"):
            label, kind = STAT_META.get(key, (key, "num"))
            v = cur.get(key)
            if v is None or (key == "FullDPS" and not v and not base.get(key)):
                continue
            if key in ("EnergyShield", "Mana") and not v and not base.get(key):
                continue
            a = base.get(key)
            vs = f"{v:.0f}%" if kind == "pct" else fmt_big(v)
            ds = ""
            if a is not None and abs(v - a) > 1e-6 and abs(a) < 1e299 and abs(v) < 1e299:
                d = v - a
                colr = POS if d > 0 else NEG
                if kind == "pct":
                    ds = f"{d:+.0f}%"
                elif kind == "big":
                    ds = f"{'+' if d >= 0 else '-'}{fmt_big(abs(d))}" + (f" ({d / a * 100:+.1f}%)" if a else "")
                else:
                    ds = f"{d:+,.0f}"
                ds = f" &nbsp;<span style='color:{colr}'>{ds}</span>"
            rows.append(f"<tr><td style='color:{DIM}; padding-right:10px'>{label}</td>"
                        f"<td><b>{vs}</b>{ds}</td></tr>")
        from statfmt import MH, maxhit, pct

        ma, mb = maxhit(base), maxhit(cur)
        for k, _key, _c in MH:
            if k not in mb:
                continue
            ds = ""
            p = pct(ma.get(k), mb[k])
            if p is not None and abs(p) >= 0.05:
                ds = f" &nbsp;<span style='color:{POS if p > 0 else NEG}'>{p:+.1f}%</span>"
            rows.append(f"<tr><td style='color:{DIM}; padding-right:10px'>최대 피격 {k}</td>"
                        f"<td><b>{fmt_big(mb[k])}</b>{ds}</td></tr>")
        self.stats_lab.setText("<table cellspacing='0' cellpadding='2'>" + "".join(rows) + "</table>")
        self.undo_btn.setEnabled(bool(self.undo))

    def on_summary(self) -> None:
        self._render_side()

    # ================================================================ 마우스
    def on_hover(self, nid: int | None) -> None:
        self.hl_add, self.hl_del = set(), set()
        if nid is None or nid not in self.nodes:
            self.tip.hide()
            self._restyle()
            return
        pv = self.pv_cache.get(nid)
        if pv:
            self._show_preview(pv)
        else:
            self._restyle()
            self.pv_want = nid
            self.pv_timer.start()
        self._render_tip(nid, pv)

    def _request_preview(self) -> None:
        if self.pv_inflight or self.pv_want is None or self.busy:
            return
        nid = self.pv_want
        if nid in self.pv_cache:
            return
        self.pv_inflight = True
        key = self.layout_key

        def ok(r):
            self.pv_inflight = False
            if key == self.layout_key and isinstance(r, dict) and not r.get("error"):
                self.pv_cache[nid] = r
                if self.view.hover_id == nid:
                    self._show_preview(r)
                    self._render_tip(nid, r)
            if self.pv_want is not None and self.pv_want not in self.pv_cache and self.view.hover_id == self.pv_want:
                self._request_preview()

        def err(_m):
            self.pv_inflight = False

        self.client.call("tree_preview", {"id": nid}, ok, err)

    def _show_preview(self, pv: dict) -> None:
        if pv.get("alloc"):
            self.hl_add, self.hl_del = set(), set(int(x) for x in pv.get("depends") or [])
        else:
            self.hl_add, self.hl_del = set(int(x) for x in pv.get("pathIds") or []), set()
        self._restyle()

    def _render_tip(self, nid: int, pv: dict | None) -> None:
        it = self.nodes.get(nid)
        if it is None:
            return
        n = it.n
        t = n["t"]
        kind = TYPE_KO.get(t, t)
        if n.get("asc"):
            kind = f"전직 ({n['asc']})" if t != "Notable" else f"전직 주요 패시브 ({n['asc']})"
        parts = [f"<b style='color:#ead197; font-size:12pt'>{html.escape(n['name'])}</b>"
                 f" &nbsp;<span style='color:{DIM}'>{kind}</span>"]
        lines = list(n["ko"])
        if t == "Mastery":
            eid = (self.state.get("mastery") or {}).get(str(nid))
            if nid in self.alloc and eid is not None:
                ef = next((e for e in n.get("effects") or [] if e["id"] == eid), None)
                lines = translate_lines(ef["stats"]) if ef else lines
            else:
                lines = ["클릭해서 효과 선택:"] + [
                    "· " + " / ".join(translate_lines(e["stats"])) for e in n.get("effects") or []]
        jew = (self.state.get("jewels") or {}).get(str(nid))
        if jew:
            lines.append(f"<span style='color:#8fb5ff'>장착 주얼: {html.escape(jew)}</span>")
        body = "<br>".join(l if l.startswith("<span") else html.escape(l) for l in lines)
        if body:
            parts.append(f"<span style='color:#c9c1f0'>{body}</span>")
        if pv is None:
            parts.append(f"<span style='color:{DIM}'>변화 계산 중…</span>")
        elif pv.get("unreachable"):
            parts.append(f"<span style='color:{DIM}'>지금 트리와 연결할 경로가 없습니다</span>")
        else:
            base = pv.get("base") or {}
            if pv.get("alloc"):
                head1, head2 = "이 노드를 빼면", f"이 노드와 연결된 {len(pv.get('depends') or [])}개를 빼면"
            elif pv.get("granted"):
                head1, head2 = "아이템이 주는 노드 — 없애면", ""
            else:
                head1, head2 = "이 노드만 찍으면", f"경로 포함 {len(pv.get('pathIds') or [])}포인트 찍으면"
            if t == "Mastery" and not pv.get("alloc"):
                head1 = ""
            for head, key in ((head1, "node"), (head2, "path")):
                if not head or not pv.get(key):
                    continue
                cells = delta_cells(base, pv[key])
                txt = " &nbsp;·&nbsp; ".join(cells) if cells else f"<span style='color:{DIM}'>변화 없음</span>"
                parts.append(f"<span style='color:#c8a96a'>{head}</span><br>{txt}")
        self.tip_lab.setText("<br>".join(parts))
        self.tip.adjustSize()
        self.tip.show()
        self.tip.raise_()
        self._place_tip()

    def move_tip(self, pos) -> None:
        self._tip_pos = pos
        if self.tip.isVisible():
            self._place_tip()

    def _place_tip(self) -> None:
        vp = self.view.viewport().rect()
        x, y = int(self._tip_pos.x()) + 22, int(self._tip_pos.y()) + 18
        if x + self.tip.width() > vp.width() - 6:
            x = int(self._tip_pos.x()) - self.tip.width() - 16
        if y + self.tip.height() > vp.height() - 6:
            y = max(6, vp.height() - self.tip.height() - 6)
        self.tip.move(max(6, x), max(6, y))

    def on_click(self, nid: int, button, gpos) -> None:
        if self.busy:
            self.status.setText("계산 중… 잠시만요")
            return
        it = self.nodes.get(nid)
        if it is None:
            return
        n = it.n
        if n["t"] in ("ClassStart", "AscendClassStart"):
            return
        if n["t"] == "Mastery":
            self._mastery_menu(nid, gpos)
            return
        if button != Qt.MouseButton.LeftButton:
            return
        if nid not in self.alloc and nid in self.pv_cache and self.pv_cache[nid].get("unreachable"):
            self.status.setText("지금 트리와 연결할 경로가 없는 노드입니다")
            return
        self._change("tree_click", {"id": nid}, "노드 해제됨" if nid in self.alloc else "노드 찍음")

    def _mastery_menu(self, nid: int, gpos) -> None:
        n = self.nodes[nid].n
        effects = n.get("effects") or []
        if not effects:
            return
        if nid not in self.alloc and not any(l in self.alloc for l in n.get("l") or []):
            # 마스터리는 같은 묶음의 노드가 하나라도 찍혀 있어야 선택 가능 (PoB 와 동일: path 가 있어야 함)
            pv = self.pv_cache.get(nid)
            if pv and pv.get("unreachable"):
                self.status.setText("이 마스터리 묶음의 노드를 먼저 찍어야 합니다")
                return
        cur = (self.state.get("mastery") or {}).get(str(nid)) if nid in self.alloc else None
        taken = {v for k, v in (self.state.get("mastery") or {}).items() if k != str(nid)}
        m = QMenu(self)
        m.setStyleSheet("QMenu { font-size: 10.5pt; } QMenu::item { padding: 6px 18px; }")
        acts = {}
        for e in effects:
            txt = " / ".join(translate_lines(e["stats"]))
            a = m.addAction(txt)
            a.setCheckable(True)
            a.setChecked(e["id"] == cur)
            if e["id"] in taken:
                a.setEnabled(False)
                a.setText(txt + "   (다른 마스터리에서 선택됨)")
            a.triggered.connect(lambda _=False, eid=e["id"]: self._change(
                "tree_click", {"id": nid, "effect": eid}, "마스터리 선택됨"))
            acts[e["id"]] = (a, txt)
        if nid in self.alloc:
            m.addSeparator()
            m.addAction("마스터리 해제", lambda: self._change("tree_click", {"id": nid}, "마스터리 해제됨"))

        def ok(r):
            base = r.get("base") or {}
            for e in r.get("effects") or []:
                a = acts.get(e.get("id"))
                if a and e.get("stats_out"):
                    cells = delta_cells(base, e["stats_out"], limit=3)
                    plain = "  ·  ".join(
                        re.sub(r"<[^>]+>", "", c) for c in cells) if cells else "변화 없음"
                    try:
                        a[0].setText(f"{a[1]}      →  {plain}")
                    except RuntimeError:
                        pass

        if not self.busy:
            self.client.call("tree_mastery_preview", {"id": nid}, ok, lambda _m: None)
        m.exec(gpos)

    # ================================================================ 변경
    def _change(self, cmd: str, args: dict, msg: str, push_undo: bool = True) -> None:
        c = self._char()
        if c is None or self.busy:
            return
        if self.client.state != "ready":
            self.status.setText("PoB 엔진이 준비되지 않았습니다")
            return
        self.page._ensure_loaded()
        prev = self.state.get("snapshot")
        self.busy = True
        self.status.setText("계산 중…")
        cid = self.cid

        def ok(r):
            self.busy = False
            if push_undo and prev:
                self.undo.append(prev)
                del self.undo[:-100]
            self.page._apply_result(cid, r, msg)
            if cid != self.cid:
                return
            st = r.get("state") or {}
            if st.get("key") != self.layout_key:
                self.client.call("tree_layout", {}, lambda rr: self._on_layout(cid, rr, fit=False),
                                 lambda m: self.status.setText(f"트리 불러오기 실패: {m}"))
            else:
                self._apply_state(st)
            self.status.setText(msg)

        def err(m):
            self.busy = False
            self.status.setText(f"실패: {m}")

        self.client.call(cmd, args, ok, err)

    def do_undo(self) -> None:
        if not self.undo or self.busy:
            return
        snap = self.undo.pop()
        self._change("tree_restore", {"snap": snap}, "되돌림", push_undo=False)

    def do_orig(self) -> None:
        orig = (self._char() or {}).get("tree_orig") or {}
        if orig.get("snap"):
            self._change("tree_restore", {"snap": orig["snap"]}, "원래 트리로 되돌림")

    def do_reset(self) -> None:
        if confirm(self, "트리 초기화", "찍은 패시브를 모두 해제할까요?\n(되돌리기 / 원래 트리로 버튼으로 복구할 수 있습니다)",
                   "초기화", danger=True):
            self._change("tree_reset", {}, "트리 초기화됨")

    def set_baseline(self) -> None:
        c = self._char()
        if c is None:
            return
        c["tree_orig"] = {"snap": self.state.get("snapshot"), "stats": (c.get("summary") or {}).get("stats") or {}}
        self.page.store.save()
        self._render_side()
        self.status.setText("지금 트리를 비교 기준으로 정했습니다")

    def import_url(self) -> None:
        text = QApplication.clipboard().text().strip()
        if "passive-skill-tree" not in text and "/tree/" not in text:
            text = ""
        url, ok = QInputDialog.getText(self, "트리 링크 불러오기",
                                       "pathofexile.com 패시브 트리 링크를 붙여넣으세요:", QLineEdit.EchoMode.Normal, text)
        if ok and url.strip():
            self._change("tree_import_url", {"url": url.strip()}, "트리 링크 불러옴")

    # ================================================================ 검색
    def _on_search(self, text: str) -> None:
        q = text.strip().lower()
        if len(q) < 2:
            self.matches = []
            self.s_info.setText("")
        else:
            self.matches = [nid for nid, it in self.nodes.items() if q in it.n.get("search", "")]
            self.matches.sort(key=lambda i: (self.nodes[i].n["t"] not in ("Keystone", "Notable"), i))
            self.s_info.setText(f"{len(self.matches)}개 찾음 — Enter 로 차례대로 이동" if self.matches else "찾은 노드 없음")
        self.match_i = -1
        self._restyle()

    def _next_match(self) -> None:
        if not self.matches:
            return
        self.match_i = (self.match_i + 1) % len(self.matches)
        n = self.nodes[self.matches[self.match_i]].n
        if self.view.scale_now() < 0.25:
            s = 0.35 / self.view.scale_now()
            self.view.scale(s, s)
            self.on_zoom()
        self.view.centerOn(n["x"], n["y"])
        self.s_info.setText(f"{self.match_i + 1} / {len(self.matches)} — {n['name']}")
