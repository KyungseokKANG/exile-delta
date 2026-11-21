"""옵션 검색 다이얼로그."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
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
    QWidget,
)

from data import tier_range_text
from dialogs import DragHeader, FramelessDialog, SearchEdit


def gen_badge(entry: dict) -> QLabel:
    b = QLabel("접두" if entry["gen"] == "prefix" else "접미")
    b.setObjectName("BadgePrefix" if entry["gen"] == "prefix" else "BadgeSuffix")
    b.setAlignment(Qt.AlignmentFlag.AlignCenter)
    b.setFixedWidth(38)
    return b


class ResultRow(QWidget):
    def __init__(self, db, entry: dict, added: bool):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 12, 6)
        h.setSpacing(8)
        h.addWidget(gen_badge(entry))
        if entry.get("crafted"):
            c = QLabel("제작")
            c.setObjectName("BadgeInf")
            c.setStyleSheet("color: #b9e0ff;")
            h.addWidget(c)
        if entry["inf"]:
            inf = QLabel(db.influence_name(entry["inf"]))
            inf.setObjectName("BadgeInf")
            h.addWidget(inf)
        t = QLabel(entry["ko"])
        t.setObjectName("ResText")
        h.addWidget(t, 1)
        if added:
            a = QLabel("추가됨")
            a.setObjectName("AddedTag")
            h.addWidget(a)
        r = QLabel(f"T1 {tier_range_text(entry['tiers'][0], entry)}  ·  {len(entry['tiers'])}단계")
        r.setObjectName("ResRange")
        h.addWidget(r)


class SearchDialog(FramelessDialog):
    def __init__(self, db, slot: str, existing: set[str], parent=None, with_craft: bool = False):
        super().__init__(parent)
        self.db = db
        self.selected_key: str | None = None
        self.selected_value: float | None = None
        self.selected_tier: dict | None = None
        self.selected_entry: dict | None = None
        self._cur_entry: dict | None = None
        self.entries = db.options(slot) + (db.craft_options(slot) if with_craft else [])
        self.resize(980, 640)

        v = QVBoxLayout(self.frame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 헤더
        header = DragHeader()
        hh = QHBoxLayout(header)
        hh.setContentsMargins(18, 0, 0, 0)
        title = QLabel("옵션 검색")
        title.setObjectName("DialogTitle")
        sub = QLabel(f"·  {db.slot_name(slot)}")
        sub.setObjectName("DialogSub")
        hh.addWidget(title)
        hh.addSpacing(6)
        hh.addWidget(sub)
        hh.addStretch(1)
        close = QToolButton()
        close.setObjectName("WinClose")
        close.setText("")
        close.setFixedSize(46, 40)
        close.clicked.connect(self.reject)
        hh.addWidget(close)
        v.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(18, 14, 18, 12)
        body.setSpacing(10)
        v.addLayout(body, 1)

        self.search = SearchEdit()
        self.search.setPlaceholderText("옵션 이름 검색  —  예: 생명력, 화염 저항, 공격 속도, life")
        self.search.setClearButtonEnabled(True)
        self.search.searchChanged.connect(lambda _t: self._filter())
        self.search.installEventFilter(self)
        body.addWidget(self.search)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        for i, label in enumerate(["전체", "접두", "접미", "영향력"] + (["제작 벤치"] if with_craft else [])):
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
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setUniformItemSizes(True)
        for e in self.entries:
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, e["key"])
            it.setSizeHint(QSize(0, 36))
            it.setToolTip(e["en"])
            self.list.addItem(it)
            self.list.setItemWidget(it, ResultRow(db, e, e["key"] in existing))
        self.list.currentRowChanged.connect(self._show_detail)
        self.list.itemDoubleClicked.connect(lambda _: self._accept_current())
        split.addWidget(self.list, 3)

        detail = QFrame()
        detail.setObjectName("DetailCard")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(16, 14, 16, 14)
        dv.setSpacing(6)
        self.d_title = QLabel()
        self.d_title.setObjectName("DetailTitle")
        self.d_title.setWordWrap(True)
        self.d_en = QLabel()
        self.d_en.setObjectName("DetailEn")
        self.d_en.setWordWrap(True)
        dv.addWidget(self.d_title)
        dv.addWidget(self.d_en)
        dv.addSpacing(6)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("TierTable")
        self.table.setHorizontalHeaderLabels(["티어", "수치", "레벨"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setCursor(Qt.CursorShape.PointingHandCursor)
        self.table.setToolTip("클릭: 이 티어 기준으로 선택  ·  더블클릭: 바로 추가")
        self.table.itemSelectionChanged.connect(self._update_add_btn)
        self.table.cellDoubleClicked.connect(lambda *_: self._accept_current())
        self.table.setWordWrap(True)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        dv.addWidget(self.table, 1)
        self.add_btn = QPushButton("이 옵션 추가")
        self.add_btn.setObjectName("Primary")
        self.add_btn.clicked.connect(self._accept_current)
        dv.addWidget(self.add_btn)
        split.addWidget(detail, 2)

        hint = QLabel("↑↓ 옵션 이동  ·  Ctrl+↑↓ 티어 선택  ·  티어 클릭 후 Enter / 더블클릭 추가  ·  Esc 닫기")
        hint.setObjectName("SectionLabel")
        body.addWidget(hint)

        self._filter()
        self.search.setFocus()

    # ---- 동작 ----
    def _filter(self) -> None:
        words = self.search.live_text().lower().split()
        mode = self.chip_group.checkedId()
        shown = 0
        for i, e in enumerate(self.entries):
            ok = all(w in e["_hay"] for w in words)
            if mode == 1:
                ok = ok and e["gen"] == "prefix" and not e["inf"]
            elif mode == 2:
                ok = ok and e["gen"] == "suffix" and not e["inf"]
            elif mode == 3:
                ok = ok and bool(e["inf"])
            elif mode == 4:
                ok = ok and bool(e.get("crafted"))
            self.list.item(i).setHidden(not ok)
            shown += ok
        self.count.setText(f"{shown}개 옵션")
        cur = self.list.currentItem()
        if cur is None or cur.isHidden():
            self._select_next(0, 1)
        self.add_btn.setEnabled(shown > 0)
        if shown == 0:
            self._show_detail(-1)

    def _select_next(self, start: int, step: int) -> None:
        i = start
        while 0 <= i < self.list.count():
            if not self.list.item(i).isHidden():
                self.list.setCurrentRow(i)
                return
            i += step

    def _show_detail(self, row: int) -> None:
        if row < 0 or row >= len(self.entries) or self.list.item(row).isHidden():
            self._cur_entry = None
            self.d_title.setText("검색 결과가 없습니다")
            self.d_en.setText("")
            self.table.setRowCount(0)
            self._update_add_btn()
            return
        e = self.entries[row]
        self._cur_entry = e
        prefix = self.db.influence_name(e["inf"]) + " · " if e["inf"] else ""
        self.d_title.setText(e["ko"])
        avg = "  ·  평균값 (최소+최대)÷2 로 비교" if e["metric"] == "avg2" else ""
        if e.get("crafted"):
            prefix = "제작 벤치 · "
        self.d_en.setText(f"{prefix}{'접두' if e['gen'] == 'prefix' else '접미'}  ·  {e['en']}{avg}")
        self.table.setRowCount(len(e["tiers"]))
        for r, t in enumerate(e["tiers"]):
            second = t["name"]
            if e["metric"] == "avg2":
                second = f"{t['name']}  ·  {tier_range_text(t, e)}"
            items = [
                QTableWidgetItem(f"T{t['t']}"),
                QTableWidgetItem(f"{t['text']}\n{second}"),
                QTableWidgetItem(f"Lv {t['lv']}"),
            ]
            items[1].setToolTip(t["text"])
            for c, it in enumerate(items):
                it.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c, it)
        self.table.resizeRowsToContents()
        self.table.selectRow(0)
        self.table.scrollToTop()
        self._update_add_btn()

    def _selected_tier(self) -> dict | None:
        if not self._cur_entry:
            return None
        rows = self.table.selectionModel().selectedRows()
        r = rows[0].row() if rows else 0
        tiers = self._cur_entry["tiers"]
        return tiers[r] if 0 <= r < len(tiers) else None

    def _update_add_btn(self) -> None:
        t = self._selected_tier()
        if t is None:
            self.add_btn.setText("이 옵션 추가")
            self.add_btn.setEnabled(False)
            return
        self.add_btn.setEnabled(True)
        lo = tier_range_text({"lo": t["lo"], "hi": t["lo"]}, self._cur_entry)
        self.add_btn.setText(f"T{t['t']} 기준으로 추가  ·  {lo} 이상")

    def _accept_current(self) -> None:
        it = self.list.currentItem()
        t = self._selected_tier()
        if it is None or it.isHidden() or t is None:
            return
        self.selected_key = it.data(Qt.ItemDataRole.UserRole)
        self.selected_value = t["lo"]
        self.selected_tier = t
        self.selected_entry = self._cur_entry
        self.accept()

    def eventFilter(self, obj, ev):
        if obj is self.search and ev.type() == QEvent.Type.KeyPress:
            k = ev.key()
            if k in (Qt.Key.Key_Down, Qt.Key.Key_Up) and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
                step = 1 if k == Qt.Key.Key_Down else -1
                rows = self.table.selectionModel().selectedRows()
                r = (rows[0].row() if rows else 0) + step
                if 0 <= r < self.table.rowCount():
                    self.table.selectRow(r)
                return True
            if k in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                step = 1 if k == Qt.Key.Key_Down else -1
                self._select_next(self.list.currentRow() + step, step)
                return True
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                return True  # 습관적으로 Enter 쳐도 창이 닫히거나 옵션이 추가되지 않게 (추가는 버튼 · 더블클릭)
        return super().eventFilter(obj, ev)
