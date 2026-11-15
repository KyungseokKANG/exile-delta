"""'옵션변경' 창: Ctrl+C 한 아이템의 옵션을 추가/삭제/수치 변경/켜고 끄며 DPS·EHP 변화를 바로 확인.

자동으로 닫히지 않는 항상-위 창. 변경 후 0.3초 뒤 PoB 로 재계산(현재 캐릭터 · 현재 장착 장비 대비).
"""
from __future__ import annotations

import copy
import html
import re
import sys

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QDoubleValidator, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QSizePolicy,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from itemmodel import ItemModel, Mod, badge, cat_scalar, compose_en, get_quality, scale_numbers, set_quality
from overlay import COL, DIM, SPIN, Overlay

NUM_RE = re.compile(r"\d+(?:\.\d+)?")  # 부호(+/-)는 글자로 남기고 숫자만 입력칸
RANGE_RE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")
KINDS = [("explicit", "일반 옵션 (접두/접미)"), ("implicit", "고정 (implicit)"), ("implicit:exarch", "작열의 총주교 implicit"),
         ("implicit:eater", "세계 포식자 implicit"), ("implicit:corrupted", "바알 (타락 implicit)"), ("crafted", "제작 옵션")]
FLAG_KO = {"Corrupted": "타락", "Searing Exarch Item": "작열의 총주교", "Eater of Worlds Item": "세계 포식자",
           "Shaper Item": "쉐이퍼", "Elder Item": "엘더", "Crusader Item": "십자군", "Hunter Item": "사냥꾼",
           "Redeemer Item": "대속자", "Warlord Item": "전쟁군주", "Synthesised Item": "결합된", "Fractured Item": "분열된",
           "작열의 총주교 아이템": "작열의 총주교", "세계 포식자 아이템": "세계 포식자", "쉐이퍼 아이템": "쉐이퍼",
           "엘더 아이템": "엘더", "십자군 아이템": "십자군", "사냥꾼 아이템": "사냥꾼", "대속자 아이템": "대속자",
           "전쟁군주 아이템": "전쟁군주", "결합된 아이템": "결합된", "분열된 아이템": "분열된"}
FLAG_COLOR = {"타락": "#e0644c", "작열의 총주교": "#e8a25a", "세계 포식자": "#9fb5ff"}
SUB_COLOR = {"exarch": "#e8a25a", "eater": "#9fb5ff", "eldritch": "#c8a96a", "corrupted": "#e0644c"}


def _send_copy_to(hwnd: int) -> bool:
    """hwnd(게임 창)를 앞으로 돌리고 Ctrl+C 를 보낸다. Windows 전용."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd):
            return False
        import os

        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            return False  # 이 프로그램 창이면 넘기지 않음 (프로그램 안에서 연 경우)
        kernel32 = ctypes.windll.kernel32
        my_tid = kernel32.GetCurrentThreadId()
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        attached = tid and tid != my_tid and user32.AttachThreadInput(my_tid, tid, True)
        user32.SetForegroundWindow(hwnd)
        if attached:
            user32.AttachThreadInput(my_tid, tid, False)
        return True
    except Exception:  # noqa: BLE001
        return False


def _foreground_other() -> int:
    """지금 앞에 있는 창이 다른 프로그램(게임)이면 그 hwnd, 아니면 0."""
    if sys.platform != "win32":
        return 0
    try:
        import ctypes
        import os

        user32 = ctypes.windll.user32
        fg = user32.GetForegroundWindow()
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        return fg if fg and pid.value != os.getpid() else 0
    except Exception:  # noqa: BLE001
        return 0


def _key_down(vk: int) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        # 0x8000 = 지금 눌림, 0x0001 = 지난 확인 이후 눌린 적 있음 (짧게 톡 누른 것도 잡기)
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8001)
    except Exception:  # noqa: BLE001
        return False


def _press_ctrl_c() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kb = ctypes.windll.user32.keybd_event
        VK_CONTROL, VK_C, UP = 0x11, 0x43, 0x0002
        kb(VK_CONTROL, 0x1D, 0, 0)
        kb(VK_C, 0x2E, 0, 0)
        kb(VK_C, 0x2E, UP, 0)
        kb(VK_CONTROL, 0x1D, UP, 0)
    except Exception:  # noqa: BLE001
        pass


class _Drag(QFrame):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self._off: QPoint | None = None

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            # 창 본체와 같은 방식(시스템 이동)으로 — 배율·다중 모니터에서도 커서와 어긋나지 않음
            if self.win.windowHandle() and self.win.windowHandle().startSystemMove():
                e.accept()
                return
            self._off = e.globalPosition().toPoint() - self.win.pos()

    def mouseMoveEvent(self, e):
        if self._off is not None:
            self.win.move(e.globalPosition().toPoint() - self._off)

    def mouseReleaseEvent(self, e):
        self._off = None


class FlowLayout(QLayout):
    """긴 옵션 문장이 줄바꿈되도록 위젯을 왼쪽부터 흘려 배치 (Qt 예제 FlowLayout 축약)."""

    def __init__(self, hspace=4, vspace=2):
        super().__init__()
        self._items = []
        self._h, self._v = hspace, vspace
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        for it in self._items:
            hint = it.sizeHint()
            nx = x + hint.width() + self._h
            if nx - self._h > rect.right() + 1 and line_h > 0:
                x, y = rect.x(), y + line_h + self._v
                nx, line_h = x + hint.width() + self._h, 0
            if not test:
                # 같은 줄 안에서 세로 가운데 정렬
                it.setGeometry(QRect(QPoint(x, y), hint))
            x = nx
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


class ModRow(QFrame):
    """옵션 한 줄: [켜기] [종류] 텍스트(수치는 입력칸) [✕]"""

    def __init__(self, mod: Mod, on_change, on_delete, scale_fn=None):
        super().__init__()
        self._scale_fn = scale_fn  # mod → 촉매 퀄리티 배율
        self.setObjectName("EditorRow")
        self.mod = mod
        self._on_change = on_change
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 3, 6, 3)
        h.setSpacing(4)
        self.chk = QCheckBox()
        self.chk.setChecked(mod.enabled)
        self.setProperty("off", not mod.enabled)
        self.chk.setToolTip("끄면 이 옵션 없이 계산")
        self.chk.toggled.connect(self._toggle)
        h.addWidget(self.chk)
        if mod.added:
            b = QLabel("추가")
            b.setObjectName("AddedBadge")
            b.setToolTip("옵션변경 창에서 새로 추가한 옵션")
            h.addWidget(b)
        self.mod_badge = QLabel("수정")
        self.mod_badge.setObjectName("EditedBadge")
        self.mod_badge.setToolTip(f"원래: {mod.orig}")
        self.mod_badge.setVisible(not mod.added and mod.text != mod.orig)
        h.addWidget(self.mod_badge)
        if badge(mod):
            b = QLabel(badge(mod))
            b.setObjectName("KindBadge")
            if mod.sub in SUB_COLOR:
                b.setStyleSheet(f"color: {SUB_COLOR[mod.sub]}; border-color: {SUB_COLOR[mod.sub]};")
            h.addWidget(b)
        self.parts: list = []  # str | QLineEdit
        last = 0
        for m in NUM_RE.finditer(mod.text):
            if m.start() > last:
                self.parts.append(mod.text[last:m.start()])
            ed = QLineEdit(m.group(0))
            ed.setObjectName("EditorNum")
            ed.setValidator(QDoubleValidator(0, 1e7, 2))
            ed.setFixedWidth(max(46, 13 * len(m.group(0)) + 20))
            ed.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ed.textEdited.connect(self._edited)
            self.parts.append(ed)
            last = m.end()
        if last < len(mod.text):
            self.parts.append(mod.text[last:])
        flow_host = QWidget()
        flow = FlowLayout()
        flow_host.setLayout(flow)
        flow_host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        for p in self.parts:
            if isinstance(p, str):
                # 단어 단위로 쪼개 줄바꿈 가능하게
                for w in re.findall(r"\S+\s*|\s+", p):
                    if w.strip():
                        lab = QLabel(w.strip())
                        lab.setTextFormat(Qt.TextFormat.PlainText)  # '<…>' 같은 글자가 HTML 로 먹혀 빈칸이 되지 않게
                        lab.setFixedHeight(30)
                        flow.addWidget(lab)
            else:
                p.setFixedHeight(30)
                flow.addWidget(p)
        h.addWidget(flow_host, 1)
        self.qlab = QLabel("")
        self.qlab.setTextFormat(Qt.TextFormat.RichText)
        h.addWidget(self.qlab)
        self.warn = QLabel("")
        self.warn.setStyleSheet(f"color: {COL['△']}; font-size: 10pt;")
        h.addWidget(self.warn)
        self._update_q()
        x = QPushButton("✕")
        x.setObjectName("RowDelete")
        x.setFixedWidth(26)
        x.setToolTip("옵션 삭제")
        x.clicked.connect(lambda: on_delete(self))
        h.addWidget(x)

    def _edited(self, _t: str) -> None:
        self.mod.text = "".join(p if isinstance(p, str) else (p.text() or "0") for p in self.parts)
        self.mod_badge.setVisible(not self.mod.added and self.mod.text != self.mod.orig)
        self._update_q()
        self._on_change()

    def _update_q(self) -> None:
        """촉매 특수 퀄리티가 이 옵션에 적용되면: 퀄리티 적용 후 실제 수치 표시."""
        s = self._scale_fn(self.mod) if self._scale_fn else 1.0
        if s == 1.0:
            self.qlab.setText("")
            self.qlab.setToolTip("")
            return
        pct = round((s - 1) * 100)
        if self.mod.base_vals:
            vals = [scale_numbers(p.text() or "0", s) for p in self.parts if not isinstance(p, str)]
            self.qlab.setText(f"<span style='color:#6fd0c4'>퀄리티 적용</span> "
                              f"<span style='color:#6fd0c4; font-weight:bold'>→ {html.escape(' / '.join(vals))}</span>")
            self.qlab.setToolTip(f"촉매 특수 퀄리티 +{pct}% 적용 후 실제 수치 (PoB 계산에 이 값을 씁니다).\n"
                                 "입력칸은 퀄리티 적용 전 기본 수치입니다.")
        else:
            self.qlab.setText(f"<span style='color:#6fd0c4'>퀄리티 포함</span>")
            self.qlab.setToolTip(f"게임 일반 복사(Ctrl+C) 수치는 이미 촉매 퀄리티 +{pct}% 가 적용된 값입니다.")

    @property
    def enabled(self) -> bool:
        return self.mod.enabled

    def _toggle(self, on: bool) -> None:
        self.mod.enabled = on
        self.setProperty("off", not on)
        self.style().unpolish(self)
        self.style().polish(self)
        self._on_change()


class ItemEditor(QWidget):
    """게임에서 Ctrl+C → 이 창이 뜬다 (자동으로 닫히지 않음, Esc / ✕ 로 닫기). 창 하나를 재사용."""

    def __init__(self, db, char_page):
        super().__init__(None)
        self.db = db
        self.char_page = char_page
        self.model: ItemModel | None = None
        self.original: ItemModel | None = None
        self.slot: str | None = None
        self.rows: list[ModRow] = []
        self._token = 0
        self._placed = False
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        # 반투명(layered) 창은 일부 PC(배율 125% 등)에서 크기가 바뀐 뒤 화면과 클릭 위치가 어긋남 → 불투명 창
        self.setObjectName("EditorWin")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # 게임 위에서도 잘 읽히게: 기본 글자 크게 · 밝게
        self.setStyleSheet(
            "#EditorWin { background: #0e0c09; }"
            "#EditorWin QLabel { font-size: 11.5pt; color: #f1e9d8; }"
            "#EditorWin QLineEdit, #EditorWin QComboBox { font-size: 11pt; }"
            "#EditorWin QLineEdit#EditorNum { font-size: 11.5pt; font-weight: bold; }"
            "#EditorWin QPushButton#OverlayEdit { font-size: 10.5pt; padding: 4px 10px; }"
            "#EditorWin QPushButton#SmallClose { font-size: 10pt; }"
            "#EditorWin QLabel#KindBadge { font-size: 10pt; color: #cfc4ae; }"
            "#EditorWin QLabel#AddedBadge, #EditorWin QLabel#EditedBadge { font-size: 9.5pt; }")
        self.setFixedWidth(720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = QFrame()
        box.setObjectName("Overlay")
        outer.addWidget(box)
        v = QVBoxLayout(box)
        v.setContentsMargins(14, 10, 14, 12)
        v.setSpacing(8)

        # 머리 (드래그로 이동)
        head = _Drag(self)
        hh = QHBoxLayout(head)
        hh.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel()
        self.title.setTextFormat(Qt.TextFormat.RichText)
        self.title.setWordWrap(True)
        # 서식 있는 라벨은 마우스 누름을 가로채서 끌기가 안 됨 → 클릭을 머리(드래그 영역)로 통과
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        hh.addWidget(self.title, 1)
        reset = QPushButton("원래대로")
        reset.setObjectName("OverlayEdit")
        reset.clicked.connect(self._reset)
        hh.addWidget(reset)
        close = QPushButton("✕")
        close.setObjectName("EditorClose")
        close.setFixedSize(32, 30)
        close.setToolTip("닫기 (Esc)")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.close)
        hh.addWidget(close)
        v.addWidget(head)
        hint = QLabel("수치를 고치거나 체크를 끄거나(✕ 삭제) 옵션을 추가하면 바로 다시 계산합니다. "
                      "빈 곳을 끌어 옮기고, Esc · ✕ · 닫기 로 닫습니다.")
        hint.setStyleSheet(f"color: {DIM}; font-size: 10pt;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        # 퀄리티 (무기·방어구만): 바꾸면 바로 다시 계산
        self.q_row = QWidget()
        qh = QHBoxLayout(self.q_row)
        qh.setContentsMargins(2, 0, 2, 0)
        qh.setSpacing(6)
        qlab = QLabel("퀄리티")
        qlab.setStyleSheet("color: #c8a96a; font-weight: bold;")
        qh.addWidget(qlab)
        self.q_spin = QSpinBox()
        self.q_spin.setRange(0, 100)
        self.q_spin.setSuffix(" %")
        self.q_spin.setFixedWidth(80)
        self.q_spin.setToolTip("이 아이템 퀄리티를 바꿔서 계산해봐요 (원래 값은 오른쪽에)")
        self.q_spin.valueChanged.connect(self._quality_changed)
        qh.addWidget(self.q_spin)
        self.q_orig = QLabel()
        self.q_orig.setStyleSheet(f"color: {DIM}; font-size: 10pt;")
        qh.addWidget(self.q_orig)
        qh.addStretch(1)
        for val in (20, 30):
            b = QPushButton(f"{val}%")
            b.setObjectName("OverlayEdit")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, val=val: self.q_spin.setValue(val))
            qh.addWidget(b)
        self.q_back = QPushButton("원래대로")
        self.q_back.setObjectName("OverlayEdit")
        self.q_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.q_back.clicked.connect(lambda: self.q_spin.setValue(self._q_orig or 0))
        qh.addWidget(self.q_back)
        self.q_row.hide()
        self._q_orig: int | None = None
        v.addWidget(self.q_row)

        # 옵션 목록
        self.list_host = QVBoxLayout()
        self.list_host.setSpacing(4)
        lw = QWidget()
        lw.setLayout(self.list_host)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(lw)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        v.addWidget(self.scroll)

        # 추가
        add = QHBoxLayout()
        add.setSpacing(6)
        self.kind_combo = QComboBox()
        for k, label in KINDS:
            self.kind_combo.addItem(label, k)
        self.add_btn = QPushButton("+ 옵션 검색 (제작 벤치 포함)")
        self.add_btn.setObjectName("OverlayEdit")
        self.add_btn.setToolTip("접두/접미 옵션과 제작 벤치 옵션을 티어별로 검색해서 추가")
        self.add_btn.clicked.connect(self._add_from_search)
        self.imp_btn = QPushButton("+ 총주교 · 포식자 · 바알")
        self.imp_btn.setObjectName("OverlayEdit")
        self.imp_btn.setToolTip("작열의 총주교 / 세계 포식자 / 바알(타락) implicit 을 등급별로 검색해서 추가 (PoB 데이터)")
        self.imp_btn.clicked.connect(self._add_implicit)
        add.addWidget(self.add_btn, 1)
        add.addWidget(self.imp_btn, 1)
        v.addLayout(add)
        free = QHBoxLayout()
        free.setSpacing(6)
        self.free = QLineEdit()
        self.free.setPlaceholderText("직접 입력 (예: 공격 속도 10% 증가 · 영문도 가능) → Enter")
        self.free.returnPressed.connect(self._add_free)
        free.addWidget(self.kind_combo)
        free.addWidget(self.free, 1)
        v.addLayout(free)

        # 결과 (높이 고정 + 스크롤: 결과가 바뀔 때 창 크기가 흔들리지 않도록)
        res = QFrame()
        res.setObjectName("OverlayPob")
        self.res_scroll = QScrollArea()
        self.res_scroll.setWidgetResizable(True)
        self.res_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.res_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.res_scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self.res_scroll.setWidget(res)
        rv = QVBoxLayout(res)
        rv.setContentsMargins(10, 8, 10, 8)
        self.res_title = QLabel()
        self.res_title.setTextFormat(Qt.TextFormat.RichText)
        rv.addWidget(self.res_title)
        self.changes = QLabel()
        self.changes.setTextFormat(Qt.TextFormat.RichText)
        self.changes.setWordWrap(True)
        rv.addWidget(self.changes)
        self.result = QLabel()
        self.result.setTextFormat(Qt.TextFormat.RichText)
        self.result.setWordWrap(True)
        rv.addWidget(self.result)
        # '왜 이렇게 바뀌나': 마우스를 올리면 요약, 누르면 옵션 줄마다 자세히 (결과가 나온 뒤 따로 계산)
        why_row = QHBoxLayout()
        why_row.setContentsMargins(0, 2, 0, 0)
        self.why_btn = QPushButton("ⓘ 왜 이렇게 바뀌나?")
        self.why_btn.setObjectName("OverlayEdit")
        self.why_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.why_btn.clicked.connect(self._toggle_why)
        self.why_btn.hide()
        why_row.addWidget(self.why_btn)
        why_row.addStretch(1)
        rv.addLayout(why_row)
        self.why_label = QLabel()
        self.why_label.setTextFormat(Qt.TextFormat.RichText)
        self.why_label.setWordWrap(True)
        self.why_label.hide()
        rv.addWidget(self.why_label)
        self._why: list | None = None  # [(슬롯 표시 이름, explain 결과)]
        self._why_dk = "FullDPS"
        self._why_open = False
        self._last_text = ""
        self.orig_label = QLabel()
        self.orig_label.setTextFormat(Qt.TextFormat.RichText)
        self.orig_label.setWordWrap(True)
        rv.addWidget(self.orig_label)
        rv.addStretch(1)
        v.addWidget(self.res_scroll)
        # 결과 글자 위에서도 창을 끌 수 있게 (라벨이 마우스 누름을 가로채지 않도록)
        for lab in (self.res_title, self.changes, self.result, self.why_label, self.orig_label, hint):
            lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 오른쪽 아래 작은 닫기 버튼
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 0, 0, 0)
        tip = QLabel("빈 곳을 끌어서 옮길 수 있습니다")
        tip.setStyleSheet(f"color: {DIM}; font-size: 9.5pt;")
        foot.addWidget(tip)
        foot.addStretch(1)
        close2 = QPushButton("닫기")
        close2.setObjectName("SmallClose")
        close2.setToolTip("닫기 (Esc)")
        close2.clicked.connect(self.close)
        foot.addWidget(close2)
        v.addLayout(foot)

        self._timer = QTimer(self, singleShot=True, interval=300, timeout=self._recompute)
        self._wait = QTimer(self, singleShot=True, interval=30000, timeout=self._timeout)
        self._spin = QTimer(self, interval=90, timeout=self._tick)
        self._spin_i = 0
        self._orig_summary: dict | None = None
        QShortcut(QKeySequence("Esc"), self, activated=self.close)
        # 이 창이 포커스를 쥔 채로 게임 아이템에 Ctrl+C → 게임으로 넘겨서 새 아이템이 바로 뜨게
        # (입력칸에서 글자를 고른 상태의 Ctrl+C 는 입력칸이 먼저 처리)
        QShortcut(QKeySequence.StandardKey.Copy, self, activated=self._forward_copy)
        self._esc_timer = QTimer(self, interval=40, timeout=self._poll_esc)
        self._esc_down = False
        self._loads = 0  # load() 횟수 (Ctrl+C 넘김 뒤 새 아이템이 왔는지 확인용)

    def load(self, model: ItemModel, slot: str | None) -> None:
        """새 아이템으로 내용 교체 (Ctrl+C 할 때마다)."""
        self._loads += 1
        self.model = copy.deepcopy(model)
        for m in self.model.mods:
            m.orig = m.text
        self.original = copy.deepcopy(self.model)
        self.slot = slot
        self._orig_summary = None
        slot_ko = self.db.slot_name(slot) if slot else ""
        flags = [FLAG_KO.get(f, f) for f in model.flags]
        flag_html = "".join(f" <span style='color:{FLAG_COLOR.get(f, DIM)}; font-size:10pt'>[{html.escape(f)}]</span>"
                            for f in flags)
        if model.catalyst:
            import ko2en

            flag_html += (f" <span style='color:#6fd0c4; font-size:10pt'>[{ko2en.CAT_KO.get(model.catalyst, '')}"
                          f" 퀄리티 +{model.cat_q}%]</span>")
        self.title.setText(
            f"<span style='color:#ead197; font-weight:bold'>{html.escape(model.name)}</span> "
            f"<span style='color:{DIM}'>{html.escape(model.base if model.base != model.name else '')}"
            f"{' · ' + html.escape(slot_ko) if slot_ko else ''}</span>{flag_html}")
        name = (self.char_page._cur() or {}).get("name", "")
        self.res_title.setText(f"<span style='color:#c8a96a; font-weight:bold'>장착 시 변화</span>"
                               f" <span style='color:{DIM}'>· {html.escape(name)} · 현재 장착 장비 대비</span>")
        self.add_btn.setEnabled(bool(slot))
        self.orig_label.setText("")
        self._sync_quality(reset_orig=True)
        self._rebuild_rows()
        self._fit()
        self._compute_original()
        self._recompute()

    # ------------------------------------------------------------ 목록
    def _rebuild_rows(self) -> None:
        while self.list_host.count():
            it = self.list_host.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()
        self.rows = []
        order = {"enchant": 0, "implicit": 1, "fractured": 2, "explicit": 3, "crafted": 4}
        for mod in sorted(self.model.mods, key=lambda m: order.get(m.kind, 3)):
            r = ModRow(mod, self._changed, self._delete, lambda m: cat_scalar(self.model, m))
            self.rows.append(r)
            self.list_host.addWidget(r)
        self.list_host.addStretch(1)

    def _fit(self) -> None:
        """창 크기는 아이템을 불러올 때 한 번만 정한다 (조작 중에는 크기가 바뀌지 않게, 넘치면 스크롤)."""
        n = max(1, len(self.rows)) + 1  # 옵션 하나 추가할 여유
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry().height()
        cap = max(260, int(avail * 0.45))
        self.scroll.setFixedHeight(min(52 * n + 8, cap))
        two = bool(self.slot) and ("Ring" in self.slot or "반지" in self.slot)
        jewel = self.model is not None and ("주얼" in (self.model.base or "") or "Jewel" in (self.model.base or ""))
        want = 380 if jewel else 300 if two else 210
        self.res_scroll.setFixedHeight(max(150, min(want, int(avail * (0.38 if jewel else 0.3)))))
        self.adjustSize()

    def _changed(self) -> None:
        self._timer.start()

    def _delete(self, row: ModRow) -> None:
        if row.mod in self.model.mods:
            self.model.mods.remove(row.mod)
        self._rebuild_rows()
        self._changed()

    def _reset(self) -> None:
        self.model = copy.deepcopy(self.original)
        self._sync_quality()
        self._rebuild_rows()
        self._changed()

    def _sync_quality(self, reset_orig: bool = False) -> None:
        """퀄리티 칸을 지금 아이템 값으로 (무기·방어구가 아니면 숨김)."""
        q = get_quality(self.model) if self.model is not None else None
        if reset_orig:
            self._q_orig = q
        self.q_row.setVisible(q is not None)
        if q is None:
            return
        self.q_spin.blockSignals(True)
        self.q_spin.setValue(q)
        self.q_spin.blockSignals(False)
        self.q_orig.setText(f"원래 {self._q_orig or 0}%")
        self.q_back.setEnabled(q != (self._q_orig or 0))

    def _quality_changed(self, q: int) -> None:
        if self.model is None or get_quality(self.model) is None:
            return
        set_quality(self.model, q)
        self.q_back.setEnabled(q != (self._q_orig or 0))
        self._changed()

    def _add_mod(self, text: str, kind: str, en: str = "") -> None:
        text = re.sub(r"\s+", " ", text).strip()
        if not text or self.model is None:
            return
        if self.model.lang == "en" and not re.fullmatch(r"[\x00-\x7f]+", text):
            import ko2en

            text = ko2en.translate_mod(text) or text
        kind, _, sub = kind.partition(":")
        mod = Mod(text, kind, added=True, orig=text, sub=sub, en=en, base_vals=True)  # 새 줄은 기본 수치 → 퀄리티 적용
        self.model.mods.append(mod)
        self._rebuild_rows()
        row = next((r for r in self.rows if r.mod is mod), None)
        if row is not None:  # 새 줄이 보이도록 (레이아웃 갱신 후)
            QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(row))
        self._changed()

    def _add_free(self) -> None:
        self._add_mod(self.free.text(), self.kind_combo.currentData())
        self.free.clear()

    def _add_implicit(self) -> None:
        if self.model is None:
            return
        from implicit_mods import groups_for
        from implicit_search import ImplicitSearchDialog
        from pob import installer

        inst = installer.installed()
        if not inst:
            self.result.setText(f"<span style='color:{COL['X']}'>PoB 엔진이 설치되어 있어야 목록을 불러올 수 있습니다.</span>")
            return
        groups = groups_for(inst[1], self.slot, self.model.lang)
        if not groups:
            self.result.setText(f"<span style='color:{DIM}'>이 장비 종류에 붙는 총주교/포식자/바알 implicit 이 없습니다.</span>")
            return
        start = self.kind_combo.currentData().partition(":")[2]
        dlg = ImplicitSearchDialog(groups, self.model.lang, self.db.slot_name(self.slot), start, self)
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        if not dlg.exec() or not dlg.selected_lines:
            return
        for shown, en in dlg.selected_pairs:
            self._add_mod(shown, f"implicit:{dlg.selected_sub}", en=en)

    def _forward_copy(self) -> None:
        """이 창에 포커스가 있을 때(값을 고치던 중) 게임 아이템 위에서 Ctrl+C → 창은 그대로 두고 '불러오는 중'
        표시, 게임에 Ctrl+C 를 넘김 → 새 아이템이 오면 내용이 바뀜. 안 오면 원래대로 + 안내."""
        if self.frameGeometry().contains(QCursor.pos()):
            return  # 커서가 이 창 위 → 복사할 게임 아이템 없음
        if not _send_copy_to(getattr(self, "_prev_fg", 0)):
            return
        loads = self._loads
        self._token += 1  # 계산 중이던 결과는 무시
        self._spin.stop()
        self._wait.stop()
        self.result.setText(f"<span style='color:#c8a96a'>◐</span> <span style='color:{DIM}'>게임에서 새 아이템 불러오는 중…</span>")
        QTimer.singleShot(150, _press_ctrl_c)

        def check():
            if self._loads == loads and self.model is not None:
                self._recompute()
                self.changes.setText(f"<span style='color:{COL['△']}; font-size:10pt'>새 아이템을 받지 못했습니다 — "
                                     f"게임 화면을 한 번 누른 뒤 아이템에 Ctrl+C 해 주세요</span>")
        QTimer.singleShot(1500, check)

    # ---- 창 끌기: 버튼/입력칸이 아닌 빈 곳 어디서나
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()
            e.accept()
            return
        super().mousePressEvent(e)

    def _add_from_search(self) -> None:
        from search import SearchDialog

        dlg = SearchDialog(self.db, self.slot, set(), self, with_craft=True)
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        if not dlg.exec() or not dlg.selected_key or not dlg.selected_tier:
            return
        # 선택한 티어의 최고 굴림 수치로 문장 생성 (제작 벤치 옵션은 제작 옵션으로)
        kind = "crafted" if (dlg.selected_entry or {}).get("crafted") else self.kind_combo.currentData()
        text = RANGE_RE.sub(lambda m: m.group(2), dlg.selected_tier["text"])
        for part in text.split(" / "):
            self._add_mod(part, kind)

    # ------------------------------------------------------------ 계산
    def _active_mods(self) -> list[Mod]:
        return [m for m in self.model.mods if m.enabled]

    def _compute_original(self) -> None:
        text, _ = compose_en(self.original)
        self.char_page.compare_for_overlay(text, self._got_original, lambda m: None)

    def _got_original(self, r: dict) -> None:
        self._orig_summary = r
        self._render_orig()

    def _render_orig(self) -> None:
        r = self._orig_summary
        if not r or r.get("error") or not r.get("slots"):
            self.orig_label.setText("")
            return
        base = r.get("base_stats") or {}
        dk = "FullDPS" if base.get("FullDPS") else "CombinedDPS"
        from overlay import slot_label

        def dps_gain(sl):
            a, b = (sl.get("base") or base).get(dk) or 0.0, (sl.get("stats") or {}).get(dk) or 0.0
            return (b - a) / a if a and a < 1e299 and b < 1e299 else -1e9

        slots = r["slots"]
        if len(slots) > 2:  # 주얼: 가장 좋은 자리 하나만
            slots = [max(slots, key=dps_gain)]
        cells = []
        for sl in slots:
            st, b0 = sl.get("stats") or {}, sl.get("base") or base
            parts = []
            for key, nm in ((dk, "DPS"), ("TotalEHP", "EHP")):
                a, b = b0.get(key) or 0.0, st.get(key) or 0.0
                if a and a < 1e299 and b < 1e299:
                    parts.append(f"{nm} {(b - a) / a * 100:+.1f}%")
            from statfmt import maxhit_html

            mh = maxhit_html(b0, st, "최대피격")
            if mh:
                parts.append(mh)
            cells.append(f"{html.escape(slot_label(sl))} {' · '.join(parts)}")
        self.orig_label.setText(f"<span style='color:{DIM}; font-size:10pt'>원본 아이템: {' / '.join(cells)}</span>")

    def _render_changes(self) -> None:
        ms = self.model.mods
        added = [m for m in ms if m.added and m.enabled]
        off = [m for m in ms if not m.enabled]
        edited = [m for m in ms if not m.added and m.enabled and m.text != m.orig]
        removed = len([m for m in self.original.mods]) - len([m for m in ms if not m.added])
        q_now, q_was = get_quality(self.model), get_quality(self.original)
        q_diff = q_now is not None and q_now != q_was
        if not (added or off or edited or removed or q_diff):
            self.changes.setText(f"<span style='color:{DIM}; font-size:10pt'>변경 없음 — 원본 아이템 그대로</span>")
            return
        parts = []
        if q_diff:
            parts.append(f"<span style='color:{COL['△']}'>퀄리티</span> {q_was or 0}% → {q_now}%")
        if added:
            parts.append(f"<span style='color:{COL['O']}'>추가</span> " + ", ".join(html.escape(m.text) for m in added))
        if edited:
            parts.append(f"<span style='color:{COL['△']}'>수정</span> " + ", ".join(
                f"{html.escape(m.orig)} → {html.escape(m.text)}" for m in edited))
        if off:
            parts.append(f"<span style='color:{COL['X']}'>끔</span> " + ", ".join(html.escape(m.text) for m in off))
        if removed:
            parts.append(f"<span style='color:{COL['X']}'>삭제</span> {removed}줄")
        self.changes.setText("<span style='font-size:10pt'>" + "<br>".join(parts) + "</span>")

    def _recompute(self) -> None:
        self._render_changes()
        mods = self._active_mods()
        text, miss = compose_en(self.model, mods)
        for r in self.rows:
            r.warn.setText("번역 불가 · 계산 제외" if r.enabled and r.mod.text in miss else "")
        self._token += 1
        tok = self._token
        self._last_text = text
        self._why = None
        self.why_btn.hide()
        self.why_label.hide()
        started = self.char_page.compare_for_overlay(
            text, lambda r, t=tok: self._show(t, r), lambda m, t=tok: self._show(t, None, m))
        if not started:
            self.result.setText(f"<span style='color:{DIM}'>캐릭터 탭에서 캐릭터를 등록하고 PoB 엔진이 실행 중이어야 합니다.</span>")
            return
        self._spin_i = 0
        self._spin.start()
        self._wait.start()
        self._tick()

    def _timeout(self) -> None:
        self._token += 1  # 늦게 오는 응답은 무시
        self._spin.stop()
        self.result.setText(f"<span style='color:{COL['X']}'>PoB 엔진이 30초 동안 응답하지 않습니다.</span> "
                            f"<span style='color:{DIM}'>옵션을 다시 바꾸거나, 캐릭터 탭에서 엔진을 다시 시작해 보세요.</span>")

    def _tick(self) -> None:
        self._spin_i = (self._spin_i + 1) % len(SPIN)
        self.result.setText(f"<span style='color:#c8a96a'>{SPIN[self._spin_i]}</span> "
                            f"<span style='color:{DIM}'>PoB 로 DPS · EHP 계산 중</span>")

    def _show(self, tok: int, r: dict | None, err: str | None = None) -> None:
        if tok != self._token:
            return
        self._spin.stop()
        self._wait.stop()
        try:
            if err:
                self.result.setText(f"<span style='color:{COL['X']}'>계산 실패: {html.escape(err)}</span>")
            else:
                self.result.setText(Overlay._pob_html(r or {}))
                self._start_why(tok, r or {})
        except Exception as e:  # noqa: BLE001 — '계산 중' 에 멈춰 있지 않도록
            self.result.setText(f"<span style='color:{COL['X']}'>결과 표시 실패: {html.escape(str(e))}</span>")

    # ------------------------------------------------------------ 왜 이렇게 바뀌나
    def _start_why(self, tok: int, r: dict) -> None:
        """비교 결과가 나오면 슬롯(최대 2개)마다 옵션 줄 기여도를 뒤에서 계산 (한 슬롯 0.2초 안팎)."""
        slots = r.get("slots") or []
        if r.get("error") or not slots or len(slots) > 2 or r.get("note") in ("flask", "cluster"):
            return
        base = r.get("base_stats") or {}
        self._why_dk = "FullDPS" if base.get("FullDPS") else "CombinedDPS"
        from overlay import slot_label

        got: list = [None] * len(slots)
        client = self.char_page.client

        def done(i, res):
            if tok != self._token:
                return
            sl = slots[i]
            got[i] = (f"{slot_label(sl)} ← {sl.get('replacing') or '빈 슬롯'}", res or {})
            if all(g is not None for g in got):
                self._why = [g for g in got if not g[1].get("error")]
                if self._why:
                    self._render_why()

        for i, sl in enumerate(slots):
            client.call("explain", {"text": self._last_text, "slot": sl.get("slot")},
                        lambda res, i=i: done(i, res), lambda m, i=i: done(i, {"error": m}))

    def _render_why(self) -> None:
        from explain import detail_html, summary_html

        try:
            self.why_btn.setToolTip(summary_html(self._why, self._why_dk))
            self.why_label.setText(detail_html(self._why, self._why_dk))
        except Exception as e:  # noqa: BLE001
            self.why_btn.setToolTip(f"설명 만들기 실패: {e}")
        self.why_btn.show()
        self.why_btn.setText("ⓘ 자세히 접기" if self._why_open else "ⓘ 왜 이렇게 바뀌나?")
        self.why_label.setVisible(self._why_open)

    def _toggle_why(self) -> None:
        if not self._why:
            return
        self._why_open = not self._why_open
        self._render_why()
        if self._why_open:
            QTimer.singleShot(0, lambda: self.res_scroll.ensureWidgetVisible(self.why_label))

    # ------------------------------------------------------------ 표시
    def show_near_cursor(self) -> None:
        """처음엔 커서 근처, 이후엔 사용자가 옮겨 둔 자리 그대로.
        포커스는 가져오지 않음 → 게임에 계속 Ctrl+C 가 가서 다른 아이템을 바로 이어서 볼 수 있음 (Esc 는 감시 타이머로)."""
        fg = _foreground_other()
        if fg:
            self._prev_fg = fg
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        if self._placed:
            # 옮겨 둔 자리가 (해상도 변경·모니터 분리 등으로) 화면 밖이면 안으로
            screen = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.screenAt(QCursor.pos()) \
                or QGuiApplication.primaryScreen()
            g = screen.availableGeometry()
            x = min(max(g.left(), self.x()), g.right() - self.width())
            y = min(max(g.top(), self.y()), g.bottom() - self.height())
            if (x, y) != (self.x(), self.y()):
                self.move(x, y)
        else:
            self._placed = True
            pos = QCursor.pos()
            screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
            g = screen.availableGeometry()
            x = min(max(g.left(), pos.x() - self.width() // 2), g.right() - self.width())
            y = min(max(g.top(), pos.y() - 40), g.bottom() - self.height() - 40)
            self.move(x, y)
        self.show()  # 항상 위 창이라 raise_/activate 없이도 게임 위에 보임 (포커스는 게임에 그대로)
        self._esc_down = True  # 뜨는 순간 눌려 있던 키는 무시
        self._esc_timer.start()

    def hideEvent(self, e):
        self._esc_timer.stop()
        super().hideEvent(e)

    def _poll_esc(self) -> None:
        """게임이 포커스를 쥐고 있을 때도 Esc 로 닫기 (이 창에 포커스가 있으면 단축키가 처리)."""
        if not self.isVisible() or self.isActiveWindow():
            return
        down = _key_down(0x1B)
        if down and not self._esc_down:
            self.close()
        self._esc_down = down
