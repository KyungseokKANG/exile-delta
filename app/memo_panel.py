"""메모 탭 + 항상 위에 떠 있는 메모 창.

- 탭에서 글을 쓰고 '메모 띄우기' → 테두리 없는 창이 항상 위에 뜸 (끌어서 이동, 가장자리를 끌어서 크기 조절).
- '메모 고정하기' → 마우스가 메모를 그냥 통과함 (클릭 · 마우스 올림이 아래 게임으로 감, 이 프로그램이 앞으로 안 옴).
  고정은 이 탭의 '고정 풀기'로만 풀 수 있음.
- 글 · 위치 · 크기 · 글자 크기 · 배경 진하기 · 띄움/고정 상태는 settings.json 의 "memo" 에 저장 → 다음에 켜도 그대로.
"""
from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from storage import load_settings, save_settings

PLACEHOLDER = ("예시)\n"
               "경악 : 비참 / 선망 / 불안 / 멸시\n"
               "수송 그라비시우스 / 연구 보리치 / 조정 힐록")
EDGE = 8  # 가장자리 몇 px 안쪽을 끌면 크기 조절


def _load() -> dict:
    m = load_settings().get("memo")
    return m if isinstance(m, dict) else {}


def _save(**kv) -> None:
    s = load_settings()
    m = s.get("memo") if isinstance(s.get("memo"), dict) else {}
    m.update(kv)
    s["memo"] = m
    try:
        save_settings(s)
    except OSError:
        pass


def _win_topmost(w: QWidget, click_through: bool) -> None:
    """Windows: 맨 위로 다시 올리고, 고정이면 마우스 통과 + 활성화 안 됨 스타일을 확실히 붙임."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(w.winId())
        u = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = 0x80000, 0x20, 0x8000000, 0x80
        get = getattr(u, "GetWindowLongPtrW", u.GetWindowLongW)
        put = getattr(u, "SetWindowLongPtrW", u.SetWindowLongW)
        ex = get(hwnd, GWL_EXSTYLE)
        want = ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        want = (want | WS_EX_LAYERED | WS_EX_TRANSPARENT) if click_through else (want & ~WS_EX_TRANSPARENT)
        if want != ex:
            put(hwnd, GWL_EXSTYLE, want)
        # HWND_TOPMOST, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED(스타일 바뀐 경우)
        u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x2 | 0x1 | 0x10 | (0x20 if want != ex else 0))
    except Exception:  # noqa: BLE001 - 실패해도 Qt 플래그로 동작
        pass


class MemoPopup(QWidget):
    """항상 위 메모 창. 고정 전에는 끌어서 이동 · 가장자리로 크기 조절."""

    def __init__(self, on_geom):
        super().__init__(None)
        self._on_geom = on_geom
        self.pinned = False
        self.alpha = 200
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._apply_flags()
        self.setMouseTracking(True)
        self.setMinimumSize(160, 60)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 12)
        v.setSpacing(4)
        self.hint = QLabel("끌어서 이동 · 가장자리를 끌어서 크기 조절")
        self.hint.setStyleSheet("color: #8a7f6c; font-size: 8pt; background: transparent;")
        v.addWidget(self.hint)
        self.body = QLabel()
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.body.setWordWrap(True)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.set_font_size(12)
        v.addWidget(self.body, 1)
        for lb in (self.hint, self.body):
            lb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._geom_timer = QTimer(self, singleShot=True, interval=400, timeout=self._emit_geom)
        # 게임(창 모드 전체 화면)이 앞으로 와도 메모가 밑에 깔리지 않게 가끔 맨 위로
        self._top_timer = QTimer(self, interval=1500, timeout=lambda: _win_topmost(self, self.pinned))

    # ------------------------------------------------------------ 상태
    def _apply_flags(self) -> None:
        f = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
             | Qt.WindowType.WindowDoesNotAcceptFocus)
        if self.pinned:
            f |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(f)

    def set_pinned(self, on: bool) -> None:
        if on == self.pinned:
            return
        vis = self.isVisible()
        g = self.geometry()
        self.pinned = on
        self._apply_flags()  # 플래그를 바꾸면 창이 숨겨짐 → 다시 띄움
        self.hint.setVisible(not on)
        self.setGeometry(g)
        if vis:
            self.show_memo()
        self.update()

    def set_text(self, text: str) -> None:
        self.body.setText(text)

    def set_font_size(self, pt: int) -> None:
        # 앱 전체 스타일시트가 QLabel 글자 크기를 정해 둬서 setFont 는 무시됨 → 스타일시트로 지정
        self.body.setStyleSheet(f"color: #f1e6cf; background: transparent; font-size: {int(pt)}pt;")

    def set_alpha(self, a: int) -> None:
        self.alpha = max(0, min(255, a))
        self.update()

    def show_memo(self) -> None:
        self.show()
        _win_topmost(self, self.pinned)
        self._top_timer.start()

    def hide_memo(self) -> None:
        self._top_timer.stop()
        self.hide()

    # ------------------------------------------------------------ 그리기
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.setBrush(QColor(14, 12, 9, self.alpha))
        if self.pinned:
            p.setPen(QPen(QColor(134, 112, 74, min(self.alpha, 120)), 1))
        else:
            p.setPen(QPen(QColor("#c8a96a"), 1.5, Qt.PenStyle.DashLine))
        p.drawRoundedRect(r, 8, 8)

    # ------------------------------------------------------------ 이동 · 크기 조절
    def _edges(self, pos) -> Qt.Edge:
        e = Qt.Edge(0)
        if pos.x() <= EDGE:
            e |= Qt.Edge.LeftEdge
        elif pos.x() >= self.width() - EDGE:
            e |= Qt.Edge.RightEdge
        if pos.y() <= EDGE:
            e |= Qt.Edge.TopEdge
        elif pos.y() >= self.height() - EDGE:
            e |= Qt.Edge.BottomEdge
        return e

    def mouseMoveEvent(self, e):
        ed = self._edges(e.position().toPoint())
        L, R, T, B = Qt.Edge.LeftEdge, Qt.Edge.RightEdge, Qt.Edge.TopEdge, Qt.Edge.BottomEdge
        if ed in (L | T, R | B):
            c = Qt.CursorShape.SizeFDiagCursor
        elif ed in (R | T, L | B):
            c = Qt.CursorShape.SizeBDiagCursor
        elif ed & (L | R):
            c = Qt.CursorShape.SizeHorCursor
        elif ed & (T | B):
            c = Qt.CursorShape.SizeVerCursor
        else:
            c = Qt.CursorShape.SizeAllCursor
        self.setCursor(c)
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.windowHandle() and not self.pinned:
            ed = self._edges(e.position().toPoint())
            if ed:
                self.windowHandle().startSystemResize(ed)
            else:
                self.windowHandle().startSystemMove()
            e.accept()
            return
        super().mousePressEvent(e)

    def moveEvent(self, e):
        super().moveEvent(e)
        self._geom_timer.start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._geom_timer.start()

    def _emit_geom(self) -> None:
        g = self.geometry()
        self._on_geom({"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()})


class MemoCard:
    """캐릭터 화면 '메모' 탭 내용."""

    def __init__(self, page, v: QVBoxLayout):
        self.page = page
        m = _load()
        info = QLabel("게임하면서 간단히 볼 내용을 적어 두세요. 에센스 · 바알 바를 때, 준(배신) 정리할 때처럼요.<br>"
                      "<b>메모 띄우기</b> → 항상 위에 뜨는 메모 창이 생겨요. 끌어서 옮기고, 가장자리를 끌어서 크기를 맞춰요.<br>"
                      "<b>메모 고정하기</b> → 메모가 클릭 · 마우스를 그냥 통과해요. 메모 위를 눌러도 게임이 눌리고 이 프로그램은 앞으로 안 와요. "
                      "다시 옮기려면 여기서 <b>고정 풀기</b>.")
        info.setObjectName("SectionLabel")
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(info)

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText(PLACEHOLDER)
        self.edit.setPlainText(str(m.get("text") or ""))
        self.edit.setMinimumHeight(260)
        v.addWidget(self.edit)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.show_btn = QPushButton()
        self.pin_btn = QPushButton()
        for b in (self.show_btn, self.pin_btn):
            b.setMinimumWidth(130)
            row.addWidget(b)
        row.addSpacing(16)
        row.addWidget(QLabel("글자 크기"))
        self.size = QSpinBox()
        self.size.setRange(7, 40)
        self.size.setValue(int(m.get("font") or 12))
        self.size.setSuffix(" pt")
        row.addWidget(self.size)
        row.addSpacing(12)
        row.addWidget(QLabel("배경 진하기"))
        self.alpha = QSlider(Qt.Orientation.Horizontal)
        self.alpha.setRange(0, 255)
        self.alpha.setValue(int(m.get("alpha", 200)))
        self.alpha.setFixedWidth(160)
        row.addWidget(self.alpha)
        row.addStretch(1)
        v.addLayout(row)

        self.popup = MemoPopup(lambda g: _save(geom=g))
        self.popup.set_text(self.edit.toPlainText())
        self._apply_font(self.size.value())
        self.popup.set_alpha(self.alpha.value())
        g = m.get("geom") or {}
        rect = QRect(g.get("x", 80), g.get("y", 80), g.get("w", 360), g.get("h", 180))
        if g and QApplication.screenAt(rect.center()) is None:  # 모니터 구성이 바뀌어 화면 밖이면 기본 위치
            rect.moveTo(80, 80)
        self.popup.setGeometry(rect)
        if m.get("pinned"):
            self.popup.set_pinned(True)

        self._text_timer = QTimer(singleShot=True, interval=500, timeout=lambda: _save(text=self.edit.toPlainText()))
        self.edit.textChanged.connect(self._on_text)
        self.show_btn.clicked.connect(self._toggle_show)
        self.pin_btn.clicked.connect(self._toggle_pin)
        self.size.valueChanged.connect(lambda n: (self._apply_font(n), _save(font=n)))
        self.alpha.valueChanged.connect(lambda a: (self.popup.set_alpha(a), _save(alpha=a)))
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._quit)
        if m.get("shown"):
            QTimer.singleShot(0, self.popup.show_memo)
        QTimer.singleShot(0, self._sync)

    def _apply_font(self, pt: int) -> None:
        """글자 크기: 입력칸과 띄운 메모에 똑같이."""
        self.edit.setStyleSheet(f"QPlainTextEdit {{ font-size: {int(pt)}pt; }}")
        self.popup.set_font_size(pt)

    def _on_text(self) -> None:
        self.popup.set_text(self.edit.toPlainText())
        self._text_timer.start()

    def _toggle_show(self) -> None:
        if self.popup.isVisible():
            self.popup.hide_memo()
            if self.popup.pinned:  # 닫으면 고정도 풀림 → 다음에 띄우면 바로 옮길 수 있게
                self.popup.set_pinned(False)
                _save(pinned=False)
        else:
            self.popup.show_memo()
        _save(shown=self.popup.isVisible())
        self._sync()

    def _toggle_pin(self) -> None:
        on = not self.popup.pinned
        self.popup.set_pinned(on)
        if on and not self.popup.isVisible():
            self.popup.show_memo()
            _save(shown=True)
        _save(pinned=on)
        self._sync()

    def _sync(self) -> None:
        shown = self.popup.isVisible() or bool(_load().get("shown"))
        self.show_btn.setText("메모 닫기" if shown else "메모 띄우기")
        self.pin_btn.setText("고정 풀기" if self.popup.pinned else "메모 고정하기")
        self.pin_btn.setToolTip("고정하면 메모가 클릭을 그냥 통과시켜요 (게임 조작에 방해 안 됨). 다시 옮기려면 고정 풀기."
                                if not self.popup.pinned else "메모를 다시 끌어서 옮기고 크기를 바꿀 수 있게 해요")

    def _quit(self) -> None:
        if self._text_timer.isActive():
            self._text_timer.stop()
            _save(text=self.edit.toPlainText())
        self.popup.hide_memo()
        self.popup.close()
