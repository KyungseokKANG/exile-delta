"""탭 하나(검색 조건)의 편집 화면."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from data import fmt_num, tier_for_value, tier_range_text
from dialogs import confirm
from search import SearchDialog, gen_badge

VALUE_W = 104
TIER_W = 200
DEL_W = 30


class NoWheelSpin(QDoubleSpinBox):
    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class NoWheelCombo(QComboBox):
    def wheelEvent(self, e):
        if self.hasFocus() and self.view().isVisible():
            super().wheelEvent(e)
        else:
            e.ignore()


class OptionRow(QFrame):
    changed = Signal()
    removeRequested = Signal(object)

    def __init__(self, db, entry: dict, value: float, parent=None):
        super().__init__(parent)
        self.db = db
        self.entry = entry
        self.setObjectName("OptionRow")
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 8, 8, 8)
        h.setSpacing(10)

        h.addWidget(gen_badge(entry))
        if entry["inf"]:
            inf = QLabel(db.influence_name(entry["inf"]))
            inf.setObjectName("BadgeInf")
            h.addWidget(inf)

        text = QLabel(entry["ko"])
        text.setObjectName("OptText")
        text.setWordWrap(True)
        text.setToolTip(entry["en"])
        text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        h.addWidget(text, 1)

        self.spin = NoWheelSpin()
        self.spin.setObjectName("ValueSpin")
        self.spin.setDecimals(entry["decimals"])
        self.spin.setRange(-1_000_000, 1_000_000)
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.spin.setFixedWidth(VALUE_W)
        self.spin.setValue(value)
        if entry["metric"] == "avg2":
            self.spin.setPrefix("평균 ")
            self.spin.setToolTip("피해 범위 옵션은 (최소+최대)÷2 평균값으로 비교합니다\n예: 6~8 추가 → 평균 7")
        self.spin.valueChanged.connect(self._on_value)
        h.addWidget(self.spin)

        self.tier_btn = QToolButton()
        self.tier_btn.setObjectName("TierBtn")
        self.tier_btn.setFixedWidth(TIER_W)
        self.tier_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.tier_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        menu = QMenu(self.tier_btn)
        avg = entry["metric"] == "avg2"
        for t in entry["tiers"]:
            extra = f"  →  {tier_range_text(t, entry)}" if avg else ""
            act = menu.addAction(f"T{t['t']}    {t['text']}{extra}    (Lv {t['lv']} · {t['name']})")
            act.triggered.connect(lambda _=False, t=t: self.spin.setValue(t["lo"]))
        self.tier_btn.setMenu(menu)
        h.addWidget(self.tier_btn)

        dl = QToolButton()
        dl.setObjectName("RowDel")
        dl.setText("")
        dl.setToolTip("옵션 삭제")
        dl.setFixedSize(DEL_W, DEL_W)
        dl.setCursor(Qt.CursorShape.PointingHandCursor)
        dl.clicked.connect(lambda: self.removeRequested.emit(self))
        h.addWidget(dl)

        self._refresh()

    def value(self) -> float:
        return self.spin.value()

    def _on_value(self, _v) -> None:
        self._refresh()
        self.changed.emit()

    def _refresh(self) -> None:
        t = tier_for_value(self.entry, self.spin.value())
        if t is None:
            self.tier_btn.setText(f"불가  ·  최대 {fmt_num(self.entry['tiers'][0]['hi'])}")
            self.tier_btn.setProperty("state", "bad")
            self.tier_btn.setToolTip("이 수치는 어떤 티어로도 나올 수 없습니다. 클릭해서 티어를 선택하세요.")
        else:
            self.tier_btn.setText(f"최소 T{t['t']}  ·  {tier_range_text(t, self.entry)}")
            self.tier_btn.setProperty("state", "ok")
            self.tier_btn.setToolTip(
                f"T{t['t']} 이상이어야 {fmt_num(self.spin.value())} 이상이 나올 수 있습니다.\n클릭해서 티어 기준값 선택"
            )
        self.tier_btn.style().unpolish(self.tier_btn)
        self.tier_btn.style().polish(self.tier_btn)


class ProfileEditor(QWidget):
    changed = Signal()
    duplicateRequested = Signal()
    deleteRequested = Signal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.profile: dict | None = None
        self.rows: list[OptionRow] = []
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 14)
        root.setSpacing(12)

        # ---- 상단 카드: 탭 이름 / 장비 종류 / 복제 / 삭제 ----
        card = QFrame()
        card.setObjectName("HeaderCard")
        ch = QHBoxLayout(card)
        ch.setContentsMargins(16, 12, 16, 14)
        ch.setSpacing(14)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("탭 이름")
        self.name_edit.setMaxLength(40)
        self.name_edit.textEdited.connect(self._on_name)
        ch.addLayout(self._field("탭 이름", self.name_edit), 3)

        self.slot_combo = NoWheelCombo()
        self.slot_combo.setMaxVisibleItems(20)
        last_cat = None
        for s in db.slots:
            if last_cat is not None and s["category"] != last_cat:
                self.slot_combo.insertSeparator(self.slot_combo.count())
            last_cat = s["category"]
            self.slot_combo.addItem(f"{s['ko']}", s["id"])
        self.slot_combo.currentIndexChanged.connect(self._on_slot)
        ch.addLayout(self._field("장비 종류", self.slot_combo), 2)

        btns = QVBoxLayout()
        btns.addStretch(1)
        bh = QHBoxLayout()
        bh.setSpacing(8)
        dup = QPushButton("탭 복제")
        dup.setToolTip("이 탭의 모든 옵션을 복사해 새 탭을 만듭니다 (Ctrl+Shift+D)")
        dup.clicked.connect(self.duplicateRequested)
        dele = QPushButton("탭 삭제")
        dele.setObjectName("Danger")
        dele.clicked.connect(self.deleteRequested)
        bh.addWidget(dup)
        bh.addWidget(dele)
        btns.addLayout(bh)
        ch.addLayout(btns)
        root.addWidget(card)

        # ---- 컬럼 헤더 ----
        cols = QHBoxLayout()
        cols.setContentsMargins(13, 4, 9, 0)
        cols.setSpacing(10)
        self.count_label = QLabel()
        self.count_label.setObjectName("CountLabel")
        cols.addWidget(self.count_label, 1)
        for text, w in (("최소 수치", VALUE_W), ("필요 티어", TIER_W)):
            lb = QLabel(text)
            lb.setObjectName("SectionLabel")
            lb.setFixedWidth(w)
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cols.addWidget(lb)
        cols.addSpacing(DEL_W)
        root.addLayout(cols)

        # ---- 옵션 목록 ----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("ListHost")
        self.list_lay = QVBoxLayout(host)
        self.list_lay.setContentsMargins(0, 0, 6, 0)
        self.list_lay.setSpacing(6)
        self.empty = QLabel("아직 옵션이 없습니다.\n아래  + 옵션 추가  를 눌러 원하는 옵션을 검색하세요.")
        self.empty.setObjectName("EmptyLabel")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.list_lay.addWidget(self.empty)
        self.list_lay.addStretch(1)
        self.scroll.setWidget(host)
        root.addWidget(self.scroll, 1)

        self.add_btn = QPushButton("+   옵션 추가")
        self.add_btn.setObjectName("AddOptionBtn")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self.open_search)
        root.addWidget(self.add_btn)

    @staticmethod
    def _field(label: str, w: QWidget) -> QVBoxLayout:
        v = QVBoxLayout()
        v.setSpacing(5)
        lb = QLabel(label)
        lb.setObjectName("FieldLabel")
        v.addWidget(lb)
        v.addWidget(w)
        return v

    # ---- 프로필 바인딩 ----
    def set_profile(self, profile: dict) -> None:
        self._loading = True
        self.profile = profile
        self.name_edit.setText(profile["name"])
        self.slot_combo.setCurrentIndex(max(0, self.slot_combo.findData(profile["slot"])))
        self._rebuild_rows()
        self._loading = False

    def focus_name(self) -> None:
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _rebuild_rows(self) -> None:
        for r in self.rows:
            r.setParent(None)
            r.deleteLater()
        self.rows = []
        for o in self.profile["options"]:
            e = self.db.get(o["key"])
            if e:
                self._add_row(e, o["value"])
        self._update_count()

    def _add_row(self, entry: dict, value: float) -> OptionRow:
        row = OptionRow(self.db, entry, value)
        row.changed.connect(self._sync)
        row.removeRequested.connect(self._remove_row)
        self.list_lay.insertWidget(len(self.rows), row)
        self.rows.append(row)
        return row

    def _remove_row(self, row: OptionRow) -> None:
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._sync()

    def _update_count(self) -> None:
        n = len(self.rows)
        self.count_label.setText(f"옵션 {n}개" if n else "옵션")
        self.empty.setVisible(n == 0)

    def _sync(self) -> None:
        if self._loading or self.profile is None:
            return
        self.profile["options"] = [{"key": r.entry["key"], "value": r.value()} for r in self.rows]
        self._update_count()
        self.changed.emit()

    # ---- 이벤트 ----
    def _on_name(self, text: str) -> None:
        if self.profile is not None:
            self.profile["name"] = text.strip() or self.db.slot_name(self.profile["slot"])
            self.changed.emit()

    def _on_slot(self, idx: int) -> None:
        if self._loading or self.profile is None:
            return
        new, old = self.slot_combo.itemData(idx), self.profile["slot"]
        if not new or new == old:
            return
        remapped, dropped = [], 0
        for o in self.profile["options"]:
            nk = self.db.remap(o["key"], new)
            if nk:
                remapped.append({"key": nk, "value": o["value"]})
            else:
                dropped += 1
        if dropped and not confirm(
            self,
            "장비 종류 변경",
            f"{self.db.slot_name(new)}에는 없는 옵션 {dropped}개가 목록에서 제외됩니다.\n계속할까요?",
            "변경",
        ):
            self.slot_combo.blockSignals(True)
            self.slot_combo.setCurrentIndex(self.slot_combo.findData(old))
            self.slot_combo.blockSignals(False)
            return
        if self.profile["name"] == self.db.slot_name(old):
            self.profile["name"] = self.db.slot_name(new)
            self.name_edit.setText(self.profile["name"])
        self.profile["slot"] = new
        self.profile["options"] = remapped
        self._loading = True
        self._rebuild_rows()
        self._loading = False
        self.changed.emit()

    def open_search(self) -> None:
        if self.profile is None:
            return
        existing = {o["key"] for o in self.profile["options"]}
        dlg = SearchDialog(self.db, self.profile["slot"], existing, self.window())
        if not dlg.exec() or not dlg.selected_key:
            return
        e = self.db.get(dlg.selected_key)
        value = dlg.selected_value if dlg.selected_value is not None else e["tiers"][0]["lo"]
        row = self._add_row(e, value)
        self._sync()

        def focus():
            self.scroll.ensureWidgetVisible(row)
            row.spin.setFocus()
            row.spin.selectAll()

        QTimer.singleShot(30, focus)
