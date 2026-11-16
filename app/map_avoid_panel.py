"""캐릭터 화면 '비선호 지도' 탭: 피하고 싶은 지도 옵션 체크 (settings.json 'map_avoid' 에 저장).

지도에 Ctrl+C 하면 map_warn.MapWarn 이 여기서 고른 옵션이 있는지 알려 준다.
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

import mapcheck
from storage import load_settings, save_settings

T17 = "#d77fe0"


class MapAvoidCard:
    def __init__(self, page, v):
        self.page = page
        self.avoid: set[str] = set(load_settings().get("map_avoid") or [])
        info = QLabel("지도에 Ctrl+C 하면 여기서 체크한 옵션이 붙어 있는지 바로 알려줘요. "
                      "티어마다 수치만 다른 옵션은 하나로 묶여 있어서, 하나만 체크해도 모든 티어(17티어 포함)에 걸려요.")
        info.setObjectName("SectionLabel")
        info.setWordWrap(True)
        v.addWidget(info)

        fr = QHBoxLayout()
        fr.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("옵션 검색 (예: 회복, 반사, 저항)")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(280)
        self.search.setMaximumWidth(340)
        self.search.textChanged.connect(lambda _t: self._layout())
        fr.addWidget(self.search)
        self.which = QComboBox()
        for label, key in (("전체", ""), ("일반 지도에 나오는 것", "map"), ("17티어에만 나오는 것", "t17only")):
            self.which.addItem(label, key)
        self.which.currentIndexChanged.connect(lambda _i: self._layout())
        fr.addWidget(self.which)
        self.only = QCheckBox("고른 것만")
        self.only.toggled.connect(lambda _on: self._layout())
        fr.addWidget(self.only)
        fr.addStretch(1)
        self.count = QLabel()
        self.count.setObjectName("DefLine")
        fr.addWidget(self.count)
        clear = QPushButton("전부 해제")
        clear.clicked.connect(self._clear)
        fr.addWidget(clear)
        v.addLayout(fr)

        host = QWidget()
        self.grid = QGridLayout(host)
        self.grid.setContentsMargins(0, 4, 0, 0)
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(4)
        v.addWidget(host)
        self.empty = QLabel()
        self.empty.setObjectName("DefLine")
        v.addWidget(self.empty)

        self.boxes: list[tuple[dict, QCheckBox]] = []
        for e in mapcheck.catalog():
            only17 = e["tiers"] == ["t17"]
            cb = QCheckBox(e["ko"] + ("   ◆17티어" if only17 else ""))
            if only17:
                cb.setStyleSheet(f"QCheckBox {{ color: {T17}; }}")
            where = " · ".join(mapcheck.TIER_KO[t] for t in e["tiers"])
            cb.setToolTip(f"{e['en']}\n나오는 곳: {where}")
            cb.setChecked(e["key"] in self.avoid)
            cb.toggled.connect(lambda on, k=e["key"]: self._toggled(k, on))
            self.boxes.append((e, cb))
        self._layout()

    def _layout(self) -> None:
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().hide()
        q = self.search.text().strip().lower()
        which = self.which.currentData()
        shown = []
        for e, cb in self.boxes:
            if q and q not in e["ko"].lower() and q not in e["en"].lower():
                continue
            if which == "map" and "map" not in e["tiers"]:
                continue
            if which == "t17only" and e["tiers"] != ["t17"]:
                continue
            if self.only.isChecked() and not cb.isChecked():
                continue
            shown.append(cb)
        half = (len(shown) + 1) // 2
        for i, cb in enumerate(shown):
            self.grid.addWidget(cb, i % half if half else 0, i // half if half else 0)
            cb.show()
        if not mapcheck.catalog():
            self.empty.setText("지도 옵션 목록 파일(data/map_mods.json)이 없어요.")
        else:
            self.empty.setText("" if shown else "조건에 맞는 옵션이 없어요.")
        self.empty.setVisible(not shown)
        self.count.setText(f"{len(self.avoid)}개 고름")

    def _toggled(self, key: str, on: bool) -> None:
        if on:
            self.avoid.add(key)
        else:
            self.avoid.discard(key)
        s = load_settings()
        s["map_avoid"] = sorted(self.avoid)
        save_settings(s)
        self.count.setText(f"{len(self.avoid)}개 고름")
        if self.only.isChecked() and not on:
            self._layout()

    def _clear(self) -> None:
        if not self.avoid:
            return
        for _e, cb in self.boxes:
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self.avoid.clear()
        s = load_settings()
        s["map_avoid"] = []
        save_settings(s)
        self._layout()
