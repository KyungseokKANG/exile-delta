"""테마에 맞춘 프레임리스 확인/알림 다이얼로그."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget


class SearchEdit(QLineEdit):
    """검색칸: 한글 조합 중인 마지막 글자까지 바로 검색 + Enter 로 창이 닫히거나 선택되지 않음.

    QLineEdit 의 text()/textChanged 는 한글 입력기가 아직 조합 중인 글자(예: '체지' 의 '지')를 빼고 줘서
    마지막 글자가 띄어쓰기나 포커스 이동으로 확정되기 전까지 검색이 한 글자 늦음 → 조합 중 글자를 끼워 넣어 알림.
    """

    searchChanged = Signal(str)

    def __init__(self, parent=None, swallow_enter: bool = True):
        super().__init__(parent)
        self._preedit = ""
        self._swallow_enter = swallow_enter
        self.textChanged.connect(lambda _t: self._emit())

    def live_text(self) -> str:
        """지금 보이는 글자 그대로 (조합 중인 글자 포함)."""
        t = self.text()
        if not self._preedit:
            return t
        c = self.cursorPosition()
        return t[:c] + self._preedit + t[c:]

    def _emit(self) -> None:
        self.searchChanged.emit(self.live_text())

    def inputMethodEvent(self, e):
        super().inputMethodEvent(e)
        pre = e.preeditString()
        if pre != self._preedit or e.commitString():
            self._preedit = pre
            self._emit()

    def focusOutEvent(self, e):
        self._preedit = ""
        super().focusOutEvent(e)

    def keyPressEvent(self, e):
        super().keyPressEvent(e)
        if self._swallow_enter and e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            e.accept()  # 대화상자 기본 버튼(추가/선택)으로 넘어가지 않게


class DragHeader(QWidget):
    """눌러서 끌면 상위 창이 이동하는 헤더."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DialogHeader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()
        super().mousePressEvent(e)


class FramelessDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Dialog")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame()
        self.frame.setObjectName("DialogFrame")
        outer.addWidget(self.frame)


class MessageDialog(FramelessDialog):
    def __init__(self, parent, title: str, text: str, ok_text: str, cancel_text: str | None, danger: bool):
        super().__init__(parent)
        self.setMinimumWidth(380)
        v = QVBoxLayout(self.frame)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(12)
        t = QLabel(title)
        t.setObjectName("DialogTitle")
        v.addWidget(t)
        m = QLabel(text)
        m.setObjectName("DialogText")
        m.setWordWrap(True)
        v.addWidget(m)
        v.addSpacing(6)
        h = QHBoxLayout()
        h.addStretch(1)
        if cancel_text:
            c = QPushButton(cancel_text)
            c.clicked.connect(self.reject)
            h.addWidget(c)
        ok = QPushButton(ok_text)
        ok.setObjectName("DangerSolid" if danger else "Primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        h.addWidget(ok)
        v.addLayout(h)


def confirm(parent, title: str, text: str, ok_text: str = "확인", danger: bool = False) -> bool:
    return MessageDialog(parent, title, text, ok_text, "취소", danger).exec() == QDialog.DialogCode.Accepted


def info(parent, title: str, text: str) -> None:
    MessageDialog(parent, title, text, "확인", None, False).exec()
