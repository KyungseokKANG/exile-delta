"""목걸이 성유(Anoint) 검색 · 선택 대화상자 — 패시브 이름 / 효과 / 성유 이름으로 검색."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
)

from anoint import Anoint
from dialogs import DragHeader, FramelessDialog, SearchEdit

CHIPS = [("", "전체"), ("tree", "트리 패시브"), ("blight", "성유 전용 패시브")]
OIL_COLOR = {
    "Clear Oil": "#d8d8d8", "Sepia Oil": "#b08a5a", "Amber Oil": "#e0a040", "Verdant Oil": "#6fbf5f",
    "Teal Oil": "#4fb8a8", "Azure Oil": "#5fa0e8", "Indigo Oil": "#6f6fe0", "Violet Oil": "#b070e0",
    "Crimson Oil": "#e05050", "Black Oil": "#9a9a9a", "Opalescent Oil": "#e8d8f8", "Silver Oil": "#e8e8f0",
    "Golden Oil": "#f0c850", "Prismatic Oil": "#f0a0f0", "Tainted Oil": "#c04040", "Reflective Oil": "#a0e0ff",
}


def oils_html(a: Anoint, sep: str = " + ") -> str:
    return sep.join(f"<span style='color:{OIL_COLOR.get(e, '#ddd')}'>{html.escape(k)}</span>"
                    for e, k in zip(a.oils_en, a.oils_ko))


class AnointSearchDialog(FramelessDialog):
    def __init__(self, items: list[Anoint], current: str | None = None, parent=None):
        super().__init__(parent)
        self.items = items
        self.selected: Anoint | None = None
        self.resize(1040, 640)
        v = QVBoxLayout(self.frame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = DragHeader()
        hh = QHBoxLayout(header)
        hh.setContentsMargins(18, 0, 0, 0)
        title = QLabel("성유 옵션")
        title.setObjectName("DialogTitle")
        sub = QLabel("·  목걸이  ·  성유로 배정할 패시브 고르기")
        sub.setObjectName("DialogSub")
        hh.addWidget(title)
        hh.addSpacing(6)
        hh.addWidget(sub)
        hh.addStretch(1)
        close = QToolButton()
        close.setObjectName("WinClose")
        close.setFixedSize(46, 40)
        close.clicked.connect(self.reject)
        hh.addWidget(close)
        v.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(18, 14, 18, 12)
        body.setSpacing(10)
        v.addLayout(body, 1)

        self.search = SearchEdit()
        self.search.setPlaceholderText("검색 — 패시브 이름 · 효과 · 성유 (예: 체질, 저주, 생명력, 금빛 성유, Constitution)")
        self.search.setClearButtonEnabled(True)
        self.search.searchChanged.connect(lambda _t: self._filter())
        body.addWidget(self.search)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        for i, (_key, label) in enumerate(CHIPS):
            b = QPushButton(label)
            b.setObjectName("FilterChip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.chip_group.addButton(b, i)
            chips.addWidget(b)
            if i == 0:
                b.setChecked(True)
        self.chip_group.idClicked.connect(lambda _: self._filter())
        chips.addStretch(1)
        if current:
            cur = QLabel(f"지금 성유: <b>{html.escape(current)}</b> (고르면 바뀜)")
            cur.setTextFormat(Qt.TextFormat.RichText)
            cur.setStyleSheet("color: #7fc7d7;")
            chips.addWidget(cur)
            chips.addSpacing(14)
        self.count = QLabel()
        self.count.setObjectName("CountLabel")
        chips.addWidget(self.count)
        body.addLayout(chips)

        split = QHBoxLayout()
        split.setSpacing(14)
        body.addLayout(split, 1)
        self.table = QTableWidget(len(items), 3)
        self.table.setObjectName("TierTable")
        self.table.setHorizontalHeaderLabels(["패시브", "효과", "필요 성유"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)  # 효과가 길면 … 대신 줄바꿈
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(2, 220)
        for r, a in enumerate(items):
            name = QTableWidgetItem(a.ko + ("  ◇" if a.blighted else ""))
            name.setToolTip(a.en + ("\n성유로만 얻는 패시브 (트리에는 없음)" if a.blighted else ""))
            name.setData(Qt.ItemDataRole.UserRole, r)
            self.table.setItem(r, 0, name)
            eff = QTableWidgetItem(" / ".join(a.stats_ko))
            eff.setToolTip("\n".join(a.stats_ko) + "\n\n" + "\n".join(a.stats_en))
            self.table.setItem(r, 1, eff)
            # 표에선 '성유' 를 빼고 짧게 (청록빛 + 보랏빛 + 금빛)
            oil = QTableWidgetItem(" + ".join(k.removesuffix(" 성유") for k in a.oils_ko))
            oil.setToolTip(" + ".join(a.oils_ko) + "\n" + " + ".join(a.oils_en))
            self.table.setItem(r, 2, oil)
        self.table.currentCellChanged.connect(lambda *_: self._show())
        # 열 폭이 정해진 뒤 줄 높이를 다시 (줄바꿈된 효과가 다 보이게)
        self.table.horizontalHeader().sectionResized.connect(lambda *_: self.table.resizeRowsToContents())
        self.table.cellDoubleClicked.connect(lambda *_: self._accept())
        split.addWidget(self.table, 3)

        detail = QFrame()
        detail.setObjectName("DetailCard")
        detail.setFixedWidth(330)
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(16, 14, 16, 14)
        dv.setSpacing(8)
        self.d_title = QLabel()
        self.d_title.setObjectName("DetailTitle")
        self.d_title.setWordWrap(True)
        self.d_en = QLabel()
        self.d_en.setObjectName("DetailEn")
        self.d_en.setWordWrap(True)
        self.d_stats = QLabel()
        self.d_stats.setTextFormat(Qt.TextFormat.RichText)
        self.d_stats.setWordWrap(True)
        oil_h = QLabel("필요 성유 3개 (순서 상관없음)")
        oil_h.setStyleSheet("color: #c8a96a; font-weight: bold; margin-top: 6px;")
        self.d_oils = QLabel()
        self.d_oils.setTextFormat(Qt.TextFormat.RichText)
        self.d_oils.setWordWrap(True)
        for w in (self.d_title, self.d_en, self.d_stats, oil_h, self.d_oils):
            dv.addWidget(w)
        dv.addStretch(1)
        note = QLabel("고르면 목걸이의 성유 줄이 이 패시브로 바뀌고, 바로 DPS · EHP 가 다시 계산돼요.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #8a8070; font-size: 9.5pt;")
        dv.addWidget(note)
        self.add_btn = QPushButton("이 패시브로 성유 바르기")
        self.add_btn.setObjectName("Primary")
        self.add_btn.clicked.connect(self._accept)
        dv.addWidget(self.add_btn)
        split.addWidget(detail)
        self._filter()

    def showEvent(self, e):
        super().showEvent(e)
        self.table.resizeRowsToContents()

    def _filter(self) -> None:
        q = self.search.live_text().strip().lower()
        chip = CHIPS[max(0, self.chip_group.checkedId())][0]
        n, first = 0, -1
        for r in range(self.table.rowCount()):
            a = self.items[self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)]
            ok = (not chip or (chip == "blight") == a.blighted) and (not q or all(w in a.search_text() for w in q.split()))
            self.table.setRowHidden(r, not ok)
            if ok:
                n += 1
                if first < 0:
                    first = r
        self.count.setText(f"{n}개")
        self.table.resizeRowsToContents()
        cur = self.table.currentRow()
        if first >= 0 and (cur < 0 or self.table.isRowHidden(cur)):
            self.table.setCurrentCell(first, 0)
        self._show()

    def _cur(self) -> Anoint | None:
        r = self.table.currentRow()
        if r < 0 or self.table.isRowHidden(r):
            return None
        return self.items[self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)]

    def _show(self) -> None:
        a = self._cur()
        self.add_btn.setEnabled(a is not None)
        if a is None:
            for w in (self.d_title, self.d_en, self.d_stats, self.d_oils):
                w.setText("")
            return
        self.d_title.setText(a.ko)
        self.d_title.setStyleSheet("color: #7fc7d7;")
        self.d_en.setText(a.en + ("  · 성유로만 얻는 패시브" if a.blighted else ""))
        self.d_stats.setText("<br>".join(f"• {html.escape(s)}" for s in a.stats_ko))
        self.d_oils.setText(oils_html(a, "<br>"))

    def _accept(self) -> None:
        a = self._cur()
        if a is None:
            return
        self.selected = a
        self.accept()
