"""작열의 총주교 / 세계 포식자 / 바알(타락) implicit 검색·추가 대화상자."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
)

from dialogs import DragHeader, FramelessDialog, SearchEdit
from implicit_mods import SUB_NAME, Group, tier_lines, tier_pairs
from itemmodel import PRESENCE_RE

CHIPS = [("", "전체"), ("exarch", "작열의 총주교"), ("eater", "세계 포식자"), ("corrupted", "바알 (타락)")]
SUB_COLOR = {"exarch": "#e8a25a", "eater": "#9fb5ff", "corrupted": "#e0644c"}


class ImplicitSearchDialog(FramelessDialog):
    def __init__(self, groups: list[Group], lang: str, slot_name: str, start_sub: str = "", parent=None):
        super().__init__(parent)
        self.groups = groups
        self.lang = lang
        self.selected_lines: list[str] | None = None
        self.selected_sub = ""
        self.resize(980, 620)
        v = QVBoxLayout(self.frame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = DragHeader()
        hh = QHBoxLayout(header)
        hh.setContentsMargins(18, 0, 0, 0)
        title = QLabel("implicit 추가")
        title.setObjectName("DialogTitle")
        sub = QLabel(f"·  {slot_name}  ·  총주교 / 포식자 / 바알")
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
        self.search.setPlaceholderText("검색 — 예: 공격 속도, 화염, 생명력, attack speed")
        self.search.setClearButtonEnabled(True)
        self.search.searchChanged.connect(lambda _t: self._filter())
        body.addWidget(self.search)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        for i, (key, label) in enumerate(CHIPS):
            b = QPushButton(label)
            b.setObjectName("FilterChip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.chip_group.addButton(b, i)
            chips.addWidget(b)
            if key == start_sub:
                b.setChecked(True)
        self.chip_group.idClicked.connect(lambda _: self._filter())
        chips.addStretch(1)
        self.count = QLabel()
        self.count.setObjectName("CountLabel")
        chips.addWidget(self.count)
        body.addLayout(chips)

        split = QHBoxLayout()
        split.setSpacing(14)
        body.addLayout(split, 1)
        self.list = QListWidget()
        self.list.setObjectName("ResultList")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for i, g in enumerate(groups):
            it = QListWidgetItem(f"[{SUB_NAME[g.sub]}]  {g.title_ko}")
            it.setData(Qt.ItemDataRole.UserRole, i)
            it.setForeground(Qt.GlobalColor.white)
            it.setToolTip(g.title_en)
            it.setSizeHint(QSize(0, 32))
            self.list.addItem(it)
        self.list.currentRowChanged.connect(self._show)
        self.list.itemDoubleClicked.connect(lambda _: self._accept())
        split.addWidget(self.list, 3)

        detail = QFrame()
        detail.setObjectName("DetailCard")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(16, 14, 16, 14)
        self.d_title = QLabel()
        self.d_title.setObjectName("DetailTitle")
        self.d_title.setWordWrap(True)
        self.d_en = QLabel()
        self.d_en.setObjectName("DetailEn")
        self.d_en.setWordWrap(True)
        dv.addWidget(self.d_title)
        dv.addWidget(self.d_en)
        self.table = QTableWidget(0, 2)
        self.table.setObjectName("TierTable")
        self.table.setHorizontalHeaderLabels(["등급", "수치 (최고 굴림)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(lambda *_: self._accept())
        dv.addWidget(self.table, 1)
        self.add_btn = QPushButton("이 등급으로 추가")
        self.add_btn.setObjectName("Primary")
        self.add_btn.clicked.connect(self._accept)
        dv.addWidget(self.add_btn)
        split.addWidget(detail, 2)
        self._filter()

    def _cur_sub(self) -> str:
        return CHIPS[max(0, self.chip_group.checkedId())][0]

    def _filter(self) -> None:
        q = self.search.live_text().strip().lower()
        sub = self._cur_sub()
        n = 0
        first = -1
        for r in range(self.list.count()):
            it = self.list.item(r)
            g = self.groups[it.data(Qt.ItemDataRole.UserRole)]
            hay = f"{g.title_ko} {g.title_en}".lower()
            show = (not sub or g.sub == sub) and (not q or all(w in hay for w in q.split()))
            it.setHidden(not show)
            if show:
                n += 1
                if first < 0:
                    first = r
        self.count.setText(f"{n}개")
        if first >= 0 and (self.list.currentRow() < 0 or self.list.currentItem().isHidden()):
            self.list.setCurrentRow(first)

    def _group(self) -> Group | None:
        it = self.list.currentItem()
        return self.groups[it.data(Qt.ItemDataRole.UserRole)] if it and not it.isHidden() else None

    def _show(self, _row: int) -> None:
        g = self._group()
        self.table.setRowCount(0)
        if g is None:
            return
        self.d_title.setText(f"{SUB_NAME[g.sub]} · {g.title_ko}")
        self.d_title.setStyleSheet(f"color: {SUB_COLOR.get(g.sub, '#ead197')};")
        self.d_en.setText(g.title_en)
        tiers = list(reversed(g.tiers))  # 높은 등급 먼저
        self.table.setRowCount(len(tiers))
        for r, t in enumerate(tiers):
            self.table.setItem(r, 0, QTableWidgetItem(t.label))
            full = " / ".join(tier_lines(t, self.lang))
            short = PRESENCE_RE.sub("", full)  # '고유 적이 접근해 있는 동안,' 은 제목에 있으니 생략
            it = QTableWidgetItem(short)
            it.setToolTip(full)
            self.table.setItem(r, 1, it)
        self.table.setWordWrap(True)
        self.table.resizeRowsToContents()
        self.table.selectRow(0)

    def _accept(self) -> None:
        g = self._group()
        rows = self.table.selectionModel().selectedRows()
        if g is None or not rows:
            return
        t = list(reversed(g.tiers))[rows[0].row()]
        self.selected_pairs = tier_pairs(t, self.lang)
        self.selected_lines = [s for s, _ in self.selected_pairs]
        self.selected_sub = g.sub
        self.accept()
