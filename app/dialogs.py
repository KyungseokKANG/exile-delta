"""테마에 맞춘 프레임리스 확인/알림 다이얼로그."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


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
