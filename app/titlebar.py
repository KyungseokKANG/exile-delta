"""커스텀 타이틀바: 로고 | 섹션 전환(캐릭터/아이템 필터) | 섹션별 탭 | 메뉴·창 버튼."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QToolButton,
    QWidget,
)

from icon import make_pixmap

TITLE_H = 44
GLYPH_MIN, GLYPH_MAX, GLYPH_RESTORE, GLYPH_CLOSE, GLYPH_MORE, GLYPH_ADD = (
    "", "", "", "", "", "",
)


def _start_move(w: QWidget) -> None:
    h = w.window().windowHandle()
    if h:
        h.startSystemMove()


def _toggle_max(w: QWidget) -> None:
    win = w.window()
    win.showNormal() if win.isMaximized() else win.showMaximized()


class DragArea(QWidget):
    """빈 공간: 드래그로 창 이동, 더블클릭으로 최대화."""

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            _start_move(self)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            _toggle_max(self)
            e.accept()
            return
        super().mouseDoubleClickEvent(e)


class AutoHideTabBar(QTabBar):
    """탭이 없으면 숨겨서 [+] 버튼이 왼쪽에 붙도록."""

    def tabInserted(self, index):
        super().tabInserted(index)
        self.setVisible(True)

    def tabRemoved(self, index):
        super().tabRemoved(index)
        self.setVisible(self.count() > 0)


class TabStrip(DragArea):
    """타이틀바 안에 들어가는 탭 + [+] 버튼 묶음 (섹션마다 하나)."""

    addRequested = Signal()
    closeTabRequested = Signal(int)

    def __init__(self, add_tip: str, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.tabs = AutoHideTabBar()
        self.tabs.setObjectName("MainTabs")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.tabs.setVisible(False)
        h.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignBottom)
        self.add_btn = QToolButton()
        self.add_btn.setObjectName("AddTabBtn")
        self.add_btn.setText(GLYPH_ADD)
        self.add_btn.setToolTip(add_tip)
        self.add_btn.setFixedSize(30, 28)
        self.add_btn.clicked.connect(self.addRequested)
        h.addSpacing(4)
        h.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addStretch(1)

    def add_tab(self, text: str, index: int | None = None) -> int:
        i = self.tabs.insertTab(self.tabs.count() if index is None else index, text)
        btn = QToolButton()
        btn.setObjectName("TabClose")
        btn.setText(GLYPH_CLOSE)
        btn.setFixedSize(18, 18)
        btn.setToolTip("탭 닫기")
        btn.clicked.connect(lambda: self._close_clicked(btn))
        self.tabs.setTabButton(i, QTabBar.ButtonPosition.RightSide, btn)
        return i

    def _close_clicked(self, btn: QToolButton) -> None:
        for i in range(self.tabs.count()):
            if self.tabs.tabButton(i, QTabBar.ButtonPosition.RightSide) is btn:
                self.closeTabRequested.emit(i)
                return


class TitleBar(DragArea):
    sectionChanged = Signal(int)

    def __init__(self, win, sections: list[str]):
        super().__init__(win)
        self.win = win
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(TITLE_H)

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 0, 0, 0)
        h.setSpacing(0)

        logo = QLabel()
        logo.setPixmap(make_pixmap(18))
        h.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addSpacing(9)
        title = QLabel("EXILE DELTA")
        title.setObjectName("AppTitle")
        h.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addSpacing(16)

        # 섹션 전환 (세그먼트 버튼)
        seg = QFrame()
        seg.setObjectName("NavSeg")
        sh = QHBoxLayout(seg)
        sh.setContentsMargins(3, 3, 3, 3)
        sh.setSpacing(2)
        self.nav = QButtonGroup(self)
        for i, name in enumerate(sections):
            b = QToolButton()
            b.setObjectName("NavBtn")
            b.setText(name)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav.addButton(b, i)
            sh.addWidget(b)
        self.nav.idClicked.connect(self.sectionChanged)
        h.addWidget(seg, 0, Qt.AlignmentFlag.AlignVCenter)
        seg.setVisible(len(sections) > 1)  # 섹션이 하나뿐이면 전환 버튼 숨김
        h.addSpacing(14)

        # 섹션별 탭 묶음
        self.strips = QStackedWidget()
        self.strips.setFixedHeight(TITLE_H)
        self.strips.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        h.addWidget(self.strips, 1)

        self.menu_btn = self._win_btn(GLYPH_MORE, "메뉴")
        self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.min_btn = self._win_btn(GLYPH_MIN, "최소화")
        self.max_btn = self._win_btn(GLYPH_MAX, "최대화")
        self.close_btn = self._win_btn(GLYPH_CLOSE, "닫기", "WinClose")
        self.min_btn.clicked.connect(win.showMinimized)
        self.max_btn.clicked.connect(lambda: _toggle_max(self))
        self.close_btn.clicked.connect(win.close)
        h.addSpacing(8)
        for b in (self.menu_btn, self.min_btn, self.max_btn, self.close_btn):
            h.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)

    @staticmethod
    def _win_btn(glyph: str, tip: str, name: str = "WinBtn") -> QToolButton:
        b = QToolButton()
        b.setObjectName(name)
        b.setText(glyph)
        b.setToolTip(tip)
        b.setFixedSize(46, TITLE_H)
        return b

    def add_strip(self, strip: TabStrip) -> None:
        self.strips.addWidget(strip)

    def set_section(self, i: int) -> None:
        self.nav.button(i).setChecked(True)
        self.strips.setCurrentIndex(i)

    def update_max_glyph(self) -> None:
        m = self.win.isMaximized()
        self.max_btn.setText(GLYPH_RESTORE if m else GLYPH_MAX)
        self.max_btn.setToolTip("이전 크기로" if m else "최대화")
